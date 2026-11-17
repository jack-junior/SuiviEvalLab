# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 GAYI Komi Selassi and SANOUSSI Moudjibou

"""JSON-RPC methods of working together, security and supporting documents
(sections 7 and 8)."""

from __future__ import annotations

import json
import sqlite3
import tempfile
from pathlib import Path
from typing import TYPE_CHECKING, Any

from . import attachments, security, sync
from .project import Project
from .rpc import Server

if TYPE_CHECKING:
    from .service import Service

PERSONAL_TABLES_PARTNER_DROPS = (
    "feedback",
    "recommendation",
    "risk",
    "budget_line",
    "expense",
    "meeting",
    "lesson",
    "learning_question",
    "qual_note",
    "qual_theme",
    "evaluation",
    "report_doc",
    "connection",
    "task",
    "event",
    "conflict",
    "quality_review",
    "gap_comment",
    "justification",
    "dataset",
    "cleaning_rule",
    "analysis",
    "saved_test",
    "activity",
)


def _err(message: str, key: str) -> Exception:
    return security._err(message, key)


def has_sensitive(p: Project) -> bool:
    if any(f.get("sensitive") for f in p.records("feedback")):
        return True
    return p.conn.execute("SELECT 1 FROM person LIMIT 1").fetchone() is not None


def require_encryption(p: Project) -> None:
    """Sensitive feedback and people's identifiers need an encrypted project (section 8)."""
    if not p.encrypted:
        raise _err("Protect the project with a password first", "encryption_required")


def team_state(p: Project) -> dict[str, Any]:
    meta = p.meta()
    me = security.public_identity()
    on = sync.team_on(p)
    cfg = sync.config(meta.get("uid", ""))
    return {
        "on": on,
        "me": me,
        "roles": sorted(sync.my_roles(p)),
        "owner": meta.get("owner", ""),
        "trusted": sync.members_trusted(p) if on else True,
        "members": [
            {**m, "fingerprint": security.fingerprint(m["public_key"]), "me": m["id"] == me["id"]}
            for m in sync.members(p)
        ],
        "conflicts": sync.conflicts(p) if on else [],
        "folder": cfg.get("folder", ""),
        "server": cfg.get("server", ""),
        "last_run": cfg.get("last_run", ""),
        "encrypted": p.encrypted,
        "sensitive": has_sensitive(p),
        "retention_months": int(meta.get("retention_months") or 0),
    }


def mask(p: Project, feedback: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Sensitive cases are seen only by an administrator or the feedback manager."""
    if {"admin", "feedback"} & sync.my_roles(p):
        return feedback
    return [
        {**f, "summary": "", "detail": "", "response": "", "person": "", "masked": True} if f.get("sensitive") else f
        for f in feedback
    ]


def _need(p: Project, role: str = "admin") -> None:
    if role not in sync.my_roles(p) and "admin" not in sync.my_roles(p):
        raise _err("Your role does not allow this", "not_allowed")


def _join_copy(p: Project, member: dict[str, Any], target: Path) -> None:
    """A copy of the project for a new member; a partner gets only its own data."""
    p.conn.commit()
    with sqlite3.connect(target) as dst:
        p.conn.backup(dst)
    conn = sqlite3.connect(target)
    try:
        for (name,) in conn.execute(
            "SELECT name FROM sqlite_master WHERE type = 'trigger' AND name LIKE 'sync_%'"
        ).fetchall():
            conn.execute(f"DROP TRIGGER {name}")
        if set(member["roles"]) == {"partner"}:
            mine = set(member.get("partner_ids") or [])
            # A partner gets the keys of its own partners, never the office key.
            office = security.unb64(p.meta()["office_key"])
            conn.execute("DELETE FROM meta WHERE key = 'office_key' OR key LIKE 'partner_key:%'")
            conn.executemany(
                "INSERT INTO meta(key, value) VALUES (?, ?)",
                [(f"partner_key:{pid}", security.b64(sync.partner_key(office, pid))) for pid in sorted(mine)],
            )
            for t in PERSONAL_TABLES_PARTNER_DROPS:
                conn.execute(f"DELETE FROM {t}") if conn.execute(
                    "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?", (t,)
                ).fetchone() else None
            keep = [
                r[0]
                for r in conn.execute("SELECT id, spec FROM submission").fetchall()
                if json.loads(r[1]).get("partner_id") in mine
            ]
            marks = ",".join("?" * len(keep)) or "''"
            conn.execute(f"DELETE FROM submission WHERE id NOT IN ({marks})", keep)
            conn.execute(f"DELETE FROM value WHERE submission_id NOT IN ({marks})", keep)
            conn.execute(f"DELETE FROM person WHERE submission_id NOT IN ({marks})", keep)
            conn.execute(
                "DELETE FROM attachment WHERE json_extract(spec, '$.owner_kind') <> 'submission' "
                f"OR json_extract(spec, '$.owner_id') NOT IN ({marks})",
                keep,
            )
        conn.execute("DELETE FROM measure_cache")
        conn.execute("DELETE FROM conflict")
        conn.commit()
        conn.execute("VACUUM")
    finally:
        conn.close()


def register_team(server: Server, svc: Service) -> None:
    def project() -> Project:
        return svc.project

    def path_of(params: dict[str, Any], name: str = "path") -> Path:
        value = params.get(name)
        if not isinstance(value, str) or not value:
            raise _err("No file chosen", "invalid_params")
        return Path(value)

    def reload_after_sync(result: dict[str, Any]) -> dict[str, Any]:
        svc.reset_caches()
        return {**svc.snapshot(), "sync": result}

    # ----- identity and team ------------------------------------------------------------------------

    @server.method("identity.get")
    def identity_get(_: dict[str, Any]) -> dict[str, Any]:
        return security.public_identity()

    @server.method("identity.set_name")
    def identity_name(params: dict[str, Any]) -> dict[str, Any]:
        name = str(params.get("name") or "").strip()[:120]
        if not name:
            raise _err("Give your name", "field_required")
        security.identity(name)
        return security.public_identity()

    @server.method("identity.export")
    def identity_export(params: dict[str, Any]) -> dict[str, Any]:
        me = security.public_identity()
        target = path_of(params)
        if target.suffix.lower() != ".smeid":
            target = target.with_suffix(".smeid")
        target.write_text(
            json.dumps({"format": "suivievallab-identity", **me}, ensure_ascii=False, indent=1), encoding="utf-8"
        )
        return {"path": str(target), **me}

    @server.method("team.start")
    def team_start(params: dict[str, Any]) -> dict[str, Any]:
        p = project()
        sync.start_team(p, str(params.get("name") or "").strip()[:120])
        # Everything already in the project becomes the first changes the others receive.
        for table, cols in sync.shared_tables(p.conn).items():
            key = sync._key_expr(table, cols, "t")
            if table == "meta":
                rows = p.conn.execute(
                    f"SELECT {key} FROM {table} t WHERE t.key NOT IN ({','.join('?' * len(sync.LOCAL_META))}) "
                    "AND t.key NOT LIKE 'rev:%' AND t.key NOT LIKE 'partner_key:%'",
                    sync.LOCAL_META,
                ).fetchall()
            else:
                rows = p.conn.execute(f"SELECT {key} FROM {table} t").fetchall()
            for (pk,) in rows:
                if not p.conn.execute("SELECT 1 FROM changes WHERE tbl = ? AND pk = ?", (table, pk)).fetchone():
                    p.conn.execute(
                        "INSERT INTO changes(tbl, pk, op, hlc, origin) VALUES (?, ?, 'u', ?, ?)",
                        (table, pk, p.clock.tick(), p.clock.origin),
                    )
        p.conn.commit()
        return svc.snapshot()

    @server.method("member.add")
    def member_add(params: dict[str, Any]) -> dict[str, Any]:
        p = project()
        _need(p)
        try:
            ident = json.loads(path_of(params).read_text(encoding="utf-8"))
        except (OSError, ValueError):
            raise _err("The identity file is not valid", "identity_invalid") from None
        if ident.get("format") != "suivievallab-identity" or not ident.get("id"):
            raise _err("The identity file is not valid", "identity_invalid")
        partners = {x["id"] for x in p.records("partner")}
        spec = sync.validate_member(
            {
                "name": params.get("name") or ident.get("name"),
                "roles": params.get("roles"),
                "partner_ids": params.get("partner_ids"),
                "public_key": ident.get("public_key"),
            },
            partners,
        )
        spec["added_at"] = sync.now()
        position = p.conn.execute("SELECT COALESCE(MAX(position), 0) + 1 FROM member").fetchone()[0]
        p.conn.execute(
            "INSERT OR REPLACE INTO member(id, position, spec) VALUES (?, ?, ?)",
            (ident["id"], position, json.dumps(spec, ensure_ascii=False)),
        )
        p.conn.commit()
        sync.sign_members(p)
        security.audit(p.conn, "member_added", ident["id"], {"name": spec["name"], "roles": spec["roles"]})
        return svc.snapshot()

    @server.method("member.update")
    def member_update(params: dict[str, Any]) -> dict[str, Any]:
        p = project()
        _need(p)
        current = p.record("member", params.get("id"))
        if current["id"] == p.meta().get("owner") and "admin" not in (params.get("roles") or []):
            raise _err("The project's owner stays administrator", "not_allowed")
        partners = {x["id"] for x in p.records("partner")}
        spec = sync.validate_member(
            {**current, **{k: params[k] for k in ("roles", "partner_ids", "active", "name") if k in params}}, partners
        )
        p.update_record("member", current["id"], {**spec, "added_at": current.get("added_at", "")})
        sync.sign_members(p)
        security.audit(p.conn, "member_changed", current["id"], {"roles": spec["roles"], "active": spec["active"]})
        return svc.snapshot()

    @server.method("team.join_file")
    def team_join_file(params: dict[str, Any]) -> dict[str, Any]:
        """The file a new member opens to get their copy, protected by a password given to them."""
        p = project()
        _need(p)
        member = next((m for m in sync.members(p) if m["id"] == params.get("member_id")), None)
        if member is None:
            raise _err("Unknown member", "member_not_found")
        password = security.check_password(params.get("password"))
        target = path_of(params)
        if target.suffix.lower() != ".smejoin":
            target = target.with_suffix(".smejoin")
        with tempfile.TemporaryDirectory() as tmp:
            copy = Path(tmp) / "copy.sme"
            _join_copy(p, member, copy)
            salt = security.secrets.token_bytes(16)
            key = security.password_key(password, salt)
            target.write_bytes(sync.JOIN_MAGIC + salt + security.seal(key, copy.read_bytes(), sync.JOIN_MAGIC))
        security.audit(p.conn, "join_file_written", member["id"], {"name": member["name"]})
        return {"path": str(target)}

    @server.method("team.join")
    def team_join(params: dict[str, Any]) -> dict[str, Any]:
        """Open a join file: the copy becomes this member's project."""
        source, target = path_of(params), path_of(params, "target")
        blob = source.read_bytes()
        if not blob.startswith(sync.JOIN_MAGIC):
            raise _err("This file is not an invitation to a project", "join_invalid")
        salt = blob[len(sync.JOIN_MAGIC) : len(sync.JOIN_MAGIC) + 16]
        plain = security.unseal(
            security.password_key(str(params.get("password") or ""), salt),
            blob[len(sync.JOIN_MAGIC) + 16 :],
            sync.JOIN_MAGIC,
        )
        if target.suffix.lower() != ".sme":
            target = target.with_suffix(".sme")
        with tempfile.TemporaryDirectory() as tmp:
            copy = Path(tmp) / "copy.sme"
            copy.write_bytes(plain)
            with sqlite3.connect(copy) as conn:
                me = security.identity()["id"]
                if not conn.execute("SELECT 1 FROM member WHERE id = ?", (me,)).fetchone():
                    raise _err("This invitation was made for another person", "join_not_member")
                sensitive = (
                    conn.execute("SELECT 1 FROM person LIMIT 1").fetchone()
                    or conn.execute(
                        "SELECT 1 FROM feedback WHERE json_extract(spec, '$.sensitive') = 1 LIMIT 1"
                    ).fetchone()
                )
            new_password = params.get("new_password")
            if sensitive and not new_password:
                raise _err("This project holds sensitive data: choose a password for your copy", "encryption_required")
            if new_password:
                security.encrypt_file(copy, target, security.check_password(new_password))
            else:
                target.write_bytes(plain)
        svc.ws.set(Project.open(target, new_password or None))
        svc.reset_caches()
        security.audit(svc.project.conn, "joined", security.identity()["id"], {})
        return {**svc.snapshot(), "path": str(target)}

    # ----- moving the changes -----------------------------------------------------------------------

    @server.method("sync.package")
    def sync_package(params: dict[str, Any]) -> dict[str, Any]:
        p = project()
        blob, n = sync.package_for(p, params.get("member_id"))
        target = path_of(params)
        if target.suffix.lower() != ".smesync":
            target = target.with_suffix(".smesync")
        target.write_bytes(blob)
        return {"path": str(target), "ops": n}

    @server.method("sync.receive")
    def sync_receive(params: dict[str, Any]) -> dict[str, Any]:
        p = project()
        return reload_after_sync(sync.receive(p, p.clock, path_of(params).read_bytes()))

    @server.method("sync.folder")
    def sync_folder(params: dict[str, Any]) -> dict[str, Any]:
        p = project()
        folder = params.get("path") or sync.config(p.meta().get("uid", "")).get("folder")
        if not folder:
            raise _err("Choose the shared folder", "folder_missing")
        if set(sync.my_roles(p)) == {"partner"}:
            raise _err("Partner focal points exchange packages", "not_allowed")
        return reload_after_sync(sync.folder_run(p, p.clock, Path(folder)))

    @server.method("sync.server")
    def sync_server(params: dict[str, Any]) -> dict[str, Any]:
        p = project()
        url = params.get("url") or sync.config(p.meta().get("uid", "")).get("server")
        if not url or not params.get("secret"):
            raise _err("Set the server address and its access key", "server_secret_missing")
        return reload_after_sync(sync.server_run(p, p.clock, str(url), str(params["secret"])))

    @server.method("conflict.resolve")
    def conflict_resolve(params: dict[str, Any]) -> dict[str, Any]:
        p = project()
        sync.resolve(p, p.clock, params.get("id"), params.get("accept") is True)
        svc.reset_caches()
        return svc.snapshot()

    # ----- encryption, audit, personal data ---------------------------------------------------------------

    @server.method("project.encrypt")
    def project_encrypt(params: dict[str, Any]) -> dict[str, Any]:
        p = project()
        if p.encrypted:
            raise _err("The project is already protected", "project_encrypted")
        password = security.check_password(params.get("password"))
        real = p.path
        p.conn.commit()
        svc.ws.close()
        security.encrypt_file(real, real, password)
        svc.ws.set(Project.open(real, password))
        svc.reset_caches()
        security.audit(svc.project.conn, "encrypted", str(real.name), "")
        return svc.snapshot()

    @server.method("project.change_password")
    def project_change_password(params: dict[str, Any]) -> dict[str, Any]:
        p = project()
        if not p.encrypted:
            raise _err("The project is not protected", "project_not_encrypted")
        security.decrypt_file(p.path, str(params.get("old") or ""))  # checks the current password
        password = security.check_password(params.get("password"))
        salt = security.secrets.token_bytes(16)
        p.key = (security.password_key(password, salt), salt)
        p.flush()
        security.audit(p.conn, "password_changed", str(p.path.name), "")
        return svc.snapshot()

    @server.method("project.decrypt")
    def project_decrypt(params: dict[str, Any]) -> dict[str, Any]:
        p = project()
        if not p.encrypted:
            raise _err("The project is not protected", "project_not_encrypted")
        security.decrypt_file(p.path, str(params.get("password") or ""))
        if has_sensitive(p):
            raise _err("Sensitive data must stay protected", "encryption_required")
        security.audit(p.conn, "decrypted", str(p.path.name), "")
        p.conn.commit()
        real, work = p.path, p.work
        p.key = None  # no write back: the clear file replaces the encrypted one
        p.conn.close()
        tmp = real.with_name(real.name + ".tmp")
        tmp.write_bytes(work.read_bytes())
        tmp.replace(real)
        work.unlink(missing_ok=True)
        svc.ws.project = None
        svc.ws.set(Project.open(real))
        svc.reset_caches()
        return svc.snapshot()

    @server.method("project.flush")
    def project_flush(_: dict[str, Any]) -> dict[str, Any]:
        p = svc.ws.project
        if p is not None:
            p.flush()
        return {"ok": True}

    @server.method("audit.list")
    def audit_list(_: dict[str, Any]) -> dict[str, Any]:
        p = project()
        _need(p)
        return security.audit_list(p.conn)

    @server.method("feedback.reveal")
    def feedback_reveal(params: dict[str, Any]) -> dict[str, Any]:
        """The content of a sensitive case; every reading is written in the audit trail."""
        p = project()
        if not ({"admin", "feedback"} & sync.my_roles(p)):
            raise _err("Only the feedback manager sees sensitive cases", "not_allowed")
        f = p.record("feedback", params.get("id"))
        security.audit(p.conn, "sensitive_viewed", f["id"], {"category": f["category"]})
        return {"feedback": f}

    @server.method("privacy.settings")
    def privacy_settings(params: dict[str, Any]) -> dict[str, Any]:
        p = project()
        _need(p)
        months = params.get("retention_months")
        if not isinstance(months, int) or not 0 <= months <= 240:
            raise _err("Give a number of months between 0 and 240", "number_out_of_range")
        p.set_meta("retention_months", str(months))
        return svc.snapshot()

    @server.method("privacy.purge")
    def privacy_purge(params: dict[str, Any]) -> dict[str, Any]:
        """Remove the personal data of closed feedback older than the retention period."""
        p = project()
        _need(p, "feedback")
        n = 0
        for f in purgeable(p, params.get("today")):
            p.update_record("feedback", f["id"], {**f, "person": "", "detail": "", "purged_at": sync.now()})
            n += 1
        security.audit(p.conn, "personal_data_removed", "feedback", {"cases": n})
        return {**svc.snapshot(), "purged": n}

    # ----- supporting documents ----------------------------------------------------------------------------

    @server.method("attachment.add")
    def attachment_add(params: dict[str, Any]) -> dict[str, Any]:
        p = project()
        created = attachments.add(
            p, params.get("owner_kind"), params.get("owner_id"), path_of(params), params.get("description")
        )
        return {**svc.snapshot(), "created": created}

    @server.method("attachment.list")
    def attachment_list(params: dict[str, Any]) -> dict[str, Any]:
        return {"attachments": attachments.listing(project(), params.get("owner_kind"), params.get("owner_id"))}

    @server.method("attachment.delete")
    def attachment_delete(params: dict[str, Any]) -> dict[str, Any]:
        p = project()
        a = p.record("attachment", params.get("id"))
        p.delete_record("attachment", a["id"])
        security.audit(p.conn, "document_removed", a["id"], {"name": a["name"], "sha256": a["sha256"]})
        return svc.snapshot()

    @server.method("attachment.save_as")
    def attachment_save(params: dict[str, Any]) -> dict[str, Any]:
        return attachments.save_as(project(), params.get("id"), path_of(params))


def purgeable(p: Project, day: str | None = None) -> list[dict[str, Any]]:
    from datetime import date

    from .schedule import _add_months

    months = int(p.meta().get("retention_months") or 0)
    if not months:
        return []
    today = date.fromisoformat(day) if day else date.today()
    limit = _add_months(today, -months).isoformat()
    return [
        f
        for f in p.records("feedback")
        if f["status"] == "closed" and f["received"] < limit and (f.get("person") or f.get("detail"))
    ]
