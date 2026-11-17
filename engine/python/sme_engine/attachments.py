# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 GAYI Komi Selassi and SANOUSSI Moudjibou

"""Supporting documents (pièces justificatives) attached to a submission, an
activity, a piece of feedback, a recommendation, a task or an evaluation.

The file is kept inside the project with its SHA-256 fingerprint, so a value
always points to its proof and the proof travels with the project.
"""

from __future__ import annotations

import hashlib
import mimetypes
from pathlib import Path
from typing import Any

from . import reception, security
from .project import Project
from .rpc import INVALID_PARAMS, RpcError

OWNERS = ("submission", "activity", "feedback", "recommendation", "task", "evaluation", "expense", "meeting")
MAX_FILE = 50 * 1024 * 1024
MAX_TOTAL = 2 * 1024 * 1024 * 1024


def _err(message: str, key: str) -> RpcError:
    return RpcError(message, INVALID_PARAMS, data={"key": key})


def add(p: Project, owner_kind: Any, owner_id: Any, path: Path, description: Any = "") -> str:
    if owner_kind not in OWNERS:
        raise _err("Unknown kind of object", "invalid_params")
    p.record(owner_kind, owner_id)  # the object exists
    if not path.is_file():
        raise _err("No file chosen", "invalid_params")
    size = path.stat().st_size
    if size > MAX_FILE:
        raise _err("The file is larger than 50 MB", "attachment_too_large")
    used = p.conn.execute("SELECT COALESCE(SUM(LENGTH(data)), 0) FROM attachment").fetchone()[0]
    if used + size > MAX_TOTAL:
        raise _err("The project already holds 2 GB of documents", "attachments_full")
    data = path.read_bytes()
    spec = {
        "owner_kind": owner_kind,
        "owner_id": owner_id,
        "name": path.name[:200],
        "size": size,
        "sha256": hashlib.sha256(data).hexdigest(),
        "mime": mimetypes.guess_type(path.name)[0] or "application/octet-stream",
        "description": str(description or "")[:500],
        "added_at": reception.now(),
        "added_by": security.identity()["name"] or security.identity()["id"][:8],
    }
    return p.insert_record("attachment", spec, data=data)


def listing(p: Project, owner_kind: Any = None, owner_id: Any = None) -> list[dict[str, Any]]:
    return [
        a
        for a in p.records("attachment")
        if (owner_kind is None or a["owner_kind"] == owner_kind) and (owner_id is None or a["owner_id"] == owner_id)
    ]


def counts(p: Project) -> dict[str, int]:
    out: dict[str, int] = {}
    for a in p.records("attachment"):
        key = f"{a['owner_kind']}:{a['owner_id']}"
        out[key] = out.get(key, 0) + 1
    return out


def save_as(p: Project, attachment_id: Any, target: Path) -> dict[str, Any]:
    spec = p.record("attachment", attachment_id)
    data = p.blob("attachment", "data", attachment_id)
    if hashlib.sha256(data).hexdigest() != spec["sha256"]:
        raise _err("The document is damaged", "attachment_damaged")
    target.write_bytes(data)
    return {"path": str(target), "name": spec["name"]}
