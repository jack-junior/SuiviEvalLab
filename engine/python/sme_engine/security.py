# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 GAYI Komi Selassi and SANOUSSI Moudjibou

"""Identity, signatures, encryption and audit (section 8 and 7.3).

- Identity: each computer has a member identity, a key pair kept in the user
  folder (never in a project). Its public key is what other copies know.
- Signatures: Ed25519, over the exact bytes signed.
- Encryption: AES-256-GCM. A password gives a key through scrypt.
- Encrypted project file: magic, salt, nonce, then the SQLite file encrypted.
  While open, the project lives in a private working copy in the user folder,
  written back encrypted regularly and on close.
- Audit: an append-only table, each entry chained to the previous one by its
  hash; SQLite refuses any change or deletion of an entry.
"""

from __future__ import annotations

import base64
import hashlib
import json
import os
import secrets
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from cryptography.exceptions import InvalidSignature, InvalidTag
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey, Ed25519PublicKey
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.scrypt import Scrypt
from cryptography.hazmat.primitives.serialization import Encoding, NoEncryption, PrivateFormat, PublicFormat

from .rpc import INVALID_PARAMS, RpcError

FILE_MAGIC = b"SMEENC1\x00"
MIN_PASSWORD = 8


def _err(message: str, key: str) -> RpcError:
    return RpcError(message, INVALID_PARAMS, data={"key": key})


def b64(data: bytes) -> str:
    return base64.b64encode(data).decode("ascii")


def unb64(text: str) -> bytes:
    return base64.b64decode(text.encode("ascii"))


def folder() -> Path:
    from . import trust

    return trust.path().parent


# ----- identity of this computer ------------------------------------------------------------------


def identity(name: str | None = None) -> dict[str, Any]:
    """The member identity of this computer, made the first time it is needed."""
    file = folder() / "identity.json"
    try:
        data = json.loads(file.read_text(encoding="utf-8"))
        if data.get("id") and data.get("private"):
            if name and name != data.get("name"):
                data["name"] = name
                _write_private(file, data)
            return data
    except (OSError, ValueError):
        pass
    key = Ed25519PrivateKey.generate()
    data = {
        "id": uuid.uuid4().hex,
        "name": name or "",
        "private": b64(key.private_bytes(Encoding.Raw, PrivateFormat.Raw, NoEncryption())),
        "public": b64(key.public_key().public_bytes(Encoding.Raw, PublicFormat.Raw)),
        "created_at": datetime.now(UTC).isoformat(timespec="seconds"),
    }
    _write_private(file, data)
    return data


def public_identity() -> dict[str, str]:
    me = identity()
    return {"id": me["id"], "name": me["name"], "public_key": me["public"], "fingerprint": fingerprint(me["public"])}


def fingerprint(public_b64: str) -> str:
    """A short code people can read to each other to check a key."""
    h = hashlib.sha256(unb64(public_b64)).hexdigest()[:20].upper()
    return " ".join(h[i : i + 4] for i in range(0, 20, 4))


def _write_private(file: Path, data: dict[str, Any]) -> None:
    file.parent.mkdir(parents=True, exist_ok=True)
    tmp = file.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, indent=1), encoding="utf-8")
    try:
        os.chmod(tmp, 0o600)
    except OSError:
        pass
    tmp.replace(file)


def sign(data: bytes) -> str:
    key = Ed25519PrivateKey.from_private_bytes(unb64(identity()["private"]))
    return b64(key.sign(data))


def verify(public_b64: str, data: bytes, signature_b64: str) -> bool:
    try:
        Ed25519PublicKey.from_public_bytes(unb64(public_b64)).verify(unb64(signature_b64), data)
        return True
    except (InvalidSignature, ValueError):
        return False


def canonical(obj: Any) -> bytes:
    return json.dumps(obj, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode("utf-8")


# ----- symmetric encryption ---------------------------------------------------------------------------


def password_key(password: str, salt: bytes) -> bytes:
    return Scrypt(salt=salt, length=32, n=2**15, r=8, p=1).derive(password.encode("utf-8"))


def seal(key: bytes, plaintext: bytes, aad: bytes = b"") -> bytes:
    nonce = secrets.token_bytes(12)
    return nonce + AESGCM(key).encrypt(nonce, plaintext, aad or None)


def unseal(key: bytes, blob: bytes, aad: bytes = b"") -> bytes:
    try:
        return AESGCM(key).decrypt(blob[:12], blob[12:], aad or None)
    except (InvalidTag, ValueError):
        raise _err("Wrong password or damaged file", "password_wrong") from None


def check_password(password: Any) -> str:
    if not isinstance(password, str) or len(password) < MIN_PASSWORD:
        raise _err(f"The password needs at least {MIN_PASSWORD} characters", "password_short")
    return password


def is_encrypted(path: Path) -> bool:
    try:
        with path.open("rb") as fh:
            return fh.read(len(FILE_MAGIC)) == FILE_MAGIC
    except OSError:
        return False


def encrypt_file(
    plain: Path, target: Path, password: str | None = None, key_salt: tuple[bytes, bytes] | None = None
) -> None:
    """Write `plain` (a SQLite file) encrypted to `target`, atomically."""
    if key_salt is None:
        salt = secrets.token_bytes(16)
        key = password_key(check_password(password), salt)
    else:
        key, salt = key_salt
    blob = FILE_MAGIC + salt + seal(key, plain.read_bytes(), FILE_MAGIC)
    tmp = target.with_name(target.name + ".tmp")
    tmp.write_bytes(blob)
    tmp.replace(target)


def decrypt_file(source: Path, password: str) -> tuple[bytes, bytes, bytes]:
    """(plain bytes, key, salt) of an encrypted project file."""
    data = source.read_bytes()
    if not data.startswith(FILE_MAGIC):
        raise _err("This project is not encrypted", "project_not_encrypted")
    salt = data[len(FILE_MAGIC) : len(FILE_MAGIC) + 16]
    key = password_key(password or "", salt)
    return unseal(key, data[len(FILE_MAGIC) + 16 :], FILE_MAGIC), key, salt


def work_folder() -> Path:
    d = folder() / "work"
    d.mkdir(parents=True, exist_ok=True)
    try:
        os.chmod(d, 0o700)
    except OSError:
        pass
    return d


def work_path(real: Path) -> Path:
    """Where the decrypted copy of an encrypted project lives while it is open."""
    digest = hashlib.sha256(str(real.resolve()).encode("utf-8")).hexdigest()[:24]
    return work_folder() / f"{digest}.sme"


# ----- audit trail -------------------------------------------------------------------------------------

AUDIT_SCHEMA = """
CREATE TABLE IF NOT EXISTS audit (
    seq     INTEGER PRIMARY KEY AUTOINCREMENT,
    at      TEXT NOT NULL,
    member  TEXT NOT NULL,
    name    TEXT NOT NULL,
    action  TEXT NOT NULL,
    object  TEXT NOT NULL,
    detail  TEXT NOT NULL,
    prev    TEXT NOT NULL,
    hash    TEXT NOT NULL
);
CREATE TRIGGER IF NOT EXISTS audit_no_update BEFORE UPDATE ON audit
BEGIN SELECT RAISE(ABORT, 'audit is append-only'); END;
CREATE TRIGGER IF NOT EXISTS audit_no_delete BEFORE DELETE ON audit
BEGIN SELECT RAISE(ABORT, 'audit is append-only'); END;
"""


def _entry_hash(prev: str, at: str, member: str, action: str, obj: str, detail: str) -> str:
    return hashlib.sha256("\x1f".join((prev, at, member, action, obj, detail)).encode("utf-8")).hexdigest()


def audit(conn: Any, action: str, obj: str = "", detail: Any = "") -> None:
    me = identity()
    text = detail if isinstance(detail, str) else json.dumps(detail, ensure_ascii=False, sort_keys=True)
    row = conn.execute("SELECT hash FROM audit ORDER BY seq DESC LIMIT 1").fetchone()
    prev = row[0] if row else ""
    at = datetime.now(UTC).isoformat(timespec="seconds")
    h = _entry_hash(prev, at, me["id"], action, obj, text[:4000])
    with conn:
        conn.execute(
            "INSERT INTO audit(at, member, name, action, object, detail, prev, hash) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (at, me["id"], me["name"], action, obj[:200], text[:4000], prev, h),
        )


def audit_list(conn: Any, limit: int = 500) -> dict[str, Any]:
    rows = conn.execute(
        "SELECT seq, at, member, name, action, object, detail, prev, hash FROM audit ORDER BY seq"
    ).fetchall()
    ok, prev = True, ""
    for r in rows:
        if r[7] != prev or _entry_hash(prev, r[1], r[2], r[4], r[5], r[6]) != r[8]:
            ok = False
            break
        prev = r[8]
    entries = [
        {"seq": r[0], "at": r[1], "member": r[2], "name": r[3], "action": r[4], "object": r[5], "detail": r[6]}
        for r in rows[-limit:]
    ]
    return {"entries": list(reversed(entries)), "intact": ok, "count": len(rows)}
