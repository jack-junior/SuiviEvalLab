"""Automatic copies of a project file, made each time it is opened.

The project file is written at every change, with no save button, so a wrong
deletion is saved at once. A copy taken when the project is opened lets the user
go back to how it was at the start of a session. Copies live in the user's
application folder, not next to the project, so they do not clutter shared
folders. The last KEEP copies of each project are kept; a copy is skipped when
nothing changed since the previous one.

    <SME_BACKUP_DIR>/<project name>-<hash of its path>/<YYYYMMDD-HHMMSS>.sme
"""

from __future__ import annotations

import hashlib
import os
import re
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any

from .rpc import INVALID_PARAMS, RpcError

KEEP = 10
ID = re.compile(r"^\d{8}-\d{6}(-\d+)?\.sme$")


def base_dir() -> Path:
    env = os.environ.get("SME_BACKUP_DIR")
    return Path(env) if env else Path.home() / ".suivievallab" / "backups"


def folder(project: Path) -> Path:
    key = hashlib.sha1(str(project.resolve()).lower().encode()).hexdigest()[:10]
    slug = re.sub(r"[^\w-]+", "_", project.stem)[:40] or "projet"
    return base_dir() / f"{slug}-{key}"


def _meta(path: Path) -> dict[str, str]:
    conn = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    try:
        return {k: v for k, v in conn.execute("SELECT key, value FROM meta")}
    finally:
        conn.close()


def _copies(project: Path) -> list[Path]:
    d = folder(project)
    if not d.is_dir():
        return []

    def order(p: Path) -> tuple[str, int]:
        m = ID.match(p.name)
        return p.name[:15], int(m.group(1)[1:]) if m and m.group(1) else 0

    return sorted((p for p in d.glob("*.sme") if ID.match(p.name)), key=order, reverse=True)


def snapshot(conn: sqlite3.Connection, project: Path, force: bool = False) -> Path | None:
    """Copy the open project (consistent copy through SQLite). Skipped if unchanged since the last copy."""
    updated = conn.execute("SELECT value FROM meta WHERE key = 'updated_at'").fetchone()
    updated_at = updated[0] if updated else ""
    copies = _copies(project)
    if copies and not force:
        try:
            if _meta(copies[0]).get("updated_at") == updated_at:
                return None
        except sqlite3.DatabaseError:
            pass
    d = folder(project)
    d.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    same = [p for p in d.glob(f"{stamp}*.sme") if ID.match(p.name)]
    # Several copies in the same second are numbered after the highest one, even if older ones were pruned.
    n = max((int(m.group(1)[1:]) if (m := ID.match(p.name)) and m.group(1) else 0 for p in same), default=-1) + 1
    target = d / (f"{stamp}.sme" if n == 0 else f"{stamp}-{n}.sme")
    dst = sqlite3.connect(target)
    try:
        conn.backup(dst)
    finally:
        dst.close()
    for old in _copies(project)[KEEP:]:
        old.unlink(missing_ok=True)
    return target


def listing(project: Path) -> list[dict[str, Any]]:
    out = []
    for p in _copies(project):
        try:
            meta = _meta(p)
            conn = sqlite3.connect(f"file:{p}?mode=ro", uri=True)
            try:
                indicators = conn.execute("SELECT COUNT(*) FROM indicator").fetchone()[0]
                datasets = conn.execute("SELECT COUNT(*) FROM dataset").fetchone()[0]
            finally:
                conn.close()
        except sqlite3.DatabaseError:
            continue
        stamp = datetime.strptime(p.name[:15], "%Y%m%d-%H%M%S")
        out.append(
            {
                "id": p.name,
                "taken_at": stamp.isoformat(timespec="seconds"),
                "updated_at": meta.get("updated_at"),
                "name": meta.get("name"),
                "indicators": indicators,
                "datasets": datasets,
                "bytes": p.stat().st_size,
            }
        )
    return out


def restore(project: Path, backup_id: str) -> None:
    """Put a copy back in place of the project file, after copying the current state too."""
    if not isinstance(backup_id, str) or not ID.match(backup_id):
        raise RpcError("Unknown backup", INVALID_PARAMS, data={"key": "backup_not_found"})
    source = folder(project) / backup_id
    if not source.is_file():
        raise RpcError("Unknown backup", INVALID_PARAMS, data={"key": "backup_not_found"})
    content = source.read_bytes()  # read first: the copy below may prune the oldest copies
    if project.is_file():
        conn = sqlite3.connect(project)
        try:
            snapshot(conn, project, force=True)  # the restore itself can be undone
        finally:
            conn.close()
    tmp = project.with_suffix(".sme.restoring")
    tmp.write_bytes(content)
    os.replace(tmp, project)
