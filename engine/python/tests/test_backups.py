# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 GAYI Komi Selassi and SANOUSSI Moudjibou

"""Automatic copies at opening, and restoring one."""

from __future__ import annotations

import io
import json

import pytest

from sme_engine import backups
from sme_engine.methods import register
from sme_engine.r_bridge import RBridge
from sme_engine.rpc import Server


@pytest.fixture()
def call():
    bridge = RBridge()
    server = Server(stdin=io.StringIO(), stdout=io.StringIO())
    register(server, bridge)

    def _call(method, params=None):
        resp = server.handle_line(json.dumps({"jsonrpc": "2.0", "id": 1, "method": method, "params": params or {}}))
        if "error" in resp:
            raise RuntimeError(resp["error"]["data"]["key"])
        return resp["result"]

    yield _call
    bridge.stop()


def test_copy_at_opening_and_restore(call, tmp_path, backup_dir):
    path = str(tmp_path / "p.sme")
    call("project.create", {"path": path, "name": "Projet"})
    call("framework.add", {"level": "impact", "title": "Impact A"})
    call("project.close")

    call("project.open", {"path": path})  # first copy: one framework node
    call("project.open", {"path": path})  # nothing changed: no new copy
    assert len(call("project.backups", {"path": path})["backups"]) == 1

    snap = call("project.get")
    call("framework.delete", {"id": snap["framework"][0]["id"]})  # the mistake
    first = call("project.backups", {"path": path})["backups"][0]["id"]
    restored = call("project.restore", {"path": path, "backup": first})
    assert [n["title"] for n in restored["framework"]] == ["Impact A"]
    # The state before the restore was copied too, so the restore can be undone.
    states = call("project.backups", {"path": path})["backups"]
    assert any(len(b) and b["id"] != first for b in states)
    assert all(p.parent.parent == backup_dir for p in backup_dir.rglob("*.sme"))


def test_unknown_backup_refused(call, tmp_path):
    path = str(tmp_path / "q.sme")
    call("project.create", {"path": path, "name": "Q"})
    for bad in ["../../etc/passwd", "x.sme", "20260101-000000.sme"]:
        with pytest.raises(RuntimeError, match="backup_not_found"):
            call("project.restore", {"path": path, "backup": bad})


def test_keeps_the_last_copies(tmp_path):
    import sqlite3

    from sme_engine.project import Project

    path = tmp_path / "k.sme"
    p = Project.create(path, "K")
    for i in range(backups.KEEP + 3):
        with p.conn:
            p.conn.execute("UPDATE meta SET value = ? WHERE key = 'updated_at'", (f"2026-01-01T00:00:{i:02d}",))
        backups.snapshot(p.conn, path)
    kept = backups.listing(path)
    assert len(kept) == backups.KEEP
    assert kept[0]["updated_at"] == f"2026-01-01T00:00:{backups.KEEP + 2:02d}"  # the newest are kept
    p.close()
    assert sqlite3.connect(path).execute("SELECT value FROM meta WHERE key='name'").fetchone()[0] == "K"


def test_damaged_file_found_at_opening_and_not_copied(call, tmp_path, backup_dir):
    path = tmp_path / "d.sme"
    call("project.create", {"path": str(path), "name": "D"})
    for k in range(200):
        call("framework.add", {"level": "impact", "title": f"Impact {k}" * 20})
    call("project.close")
    snap = call("project.open", {"path": str(path)})
    backups.wait(path)
    assert call("project.get")["project"]["integrity"] == "ok"
    call("project.close")
    copies = len(backups.listing(path))
    # Damage a page of an index not read when opening (a disk error, a copy cut short).
    import sqlite3

    conn = sqlite3.connect(path)
    size = conn.execute("PRAGMA page_size").fetchone()[0]
    page = conn.execute(
        "SELECT pageno FROM dbstat WHERE name = 'sqlite_autoindex_framework_node_1' AND pagetype = 'leaf'"
    ).fetchone()[0]
    conn.close()
    raw = bytearray(path.read_bytes())
    raw[(page - 1) * size : page * size] = b"\xff" * size
    path.write_bytes(bytes(raw))
    call("project.open", {"path": str(path)})
    backups.wait(path)
    assert call("project.get")["project"]["integrity"] == "damaged"
    assert len(backups.listing(path)) == copies  # the good copies are kept as they were
    assert snap["project"]["name"] == "D"
