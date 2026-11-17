# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 GAYI Komi Selassi and SANOUSSI Moudjibou

"""Working together (section 7) and security (section 8), with two or three
computers simulated in one process: each has its own user folder, so its own
identity, and its own engine."""

from __future__ import annotations

import io
import json
import sqlite3
import sys
import threading
from pathlib import Path

import pytest

from sme_engine.methods import register
from sme_engine.r_bridge import RBridge
from sme_engine.rpc import Server

ROOT = Path(__file__).resolve().parents[3]


class Computer:
    def __init__(self, home: Path, monkeypatch):
        self.home = home
        self.mp = monkeypatch
        self.bridge = RBridge()
        self.server = Server(stdin=io.StringIO(), stdout=io.StringIO())
        register(self.server, self.bridge)

    def __call__(self, method, params=None):
        self.mp.setenv("SME_TRUST_DIR", str(self.home))
        resp = self.server.handle_line(
            json.dumps({"jsonrpc": "2.0", "id": 1, "method": method, "params": params or {}})
        )
        if "error" in resp:
            raise RuntimeError(resp["error"]["data"]["key"] + ": " + resp["error"]["message"])
        return resp["result"]


@pytest.fixture()
def team(tmp_path, monkeypatch):
    made = []

    def make(name):
        c = Computer(tmp_path / f"home-{name}", monkeypatch)
        c("identity.set_name", {"name": name})
        made.append(c)
        return c

    yield make
    for c in made:
        c.bridge.stop()


def _setup(admin, tmp_path):
    admin(
        "project.create",
        {
            "path": str(tmp_path / "admin.sme"),
            "name": "Projet",
            "profile": {"start": "2026-01-01", "end": "2026-12-31"},
        },
    )
    node = admin("framework.add", {"title": "Effet"})["created"]
    ind = admin(
        "indicator.save", {"node_id": node, "indicator": {"name": "Formés", "unit": "count", "source_type": "routine"}}
    )["saved"]
    admin("team.start", {"name": "Aïcha"})
    return node, ind


def _invite(admin, member, tmp_path, roles, partner_ids=None):
    ident = member("identity.export", {"path": str(tmp_path / f"{len(roles)}{roles[0]}.smeid")})
    snap = admin("member.add", {"path": ident["path"], "roles": roles, "partner_ids": partner_ids or []})
    mid = next(m["id"] for m in snap["team"]["members"] if m["id"] == ident["id"])
    join = admin(
        "team.join_file", {"member_id": mid, "path": str(tmp_path / f"{mid}.smejoin"), "password": "secret partagé"}
    )
    return mid, join["path"]


def test_shared_folder_sync_conflicts_and_protected_data(team, tmp_path):
    admin, officer = team("Aïcha"), team("Koffi")
    node, ind = _setup(admin, tmp_path)
    assert admin("project.get")["team"]["roles"] == ["admin"]
    _mid, join = _invite(admin, officer, tmp_path, ["officer"])
    with pytest.raises(RuntimeError, match="password_wrong"):
        officer("team.join", {"path": join, "password": "pas le bon", "target": str(tmp_path / "koffi.sme")})
    snap = officer("team.join", {"path": join, "password": "secret partagé", "target": str(tmp_path / "koffi.sme")})
    assert snap["team"]["roles"] == ["officer"] and snap["indicators"][0]["name"] == "Formés"

    shared = tmp_path / "partage"
    shared.mkdir()
    # Koffi adds a result; Aïcha renames the indicator. Both arrive on the other side.
    officer("framework.add", {"title": "Produit de Koffi", "parent_id": node})
    admin(
        "indicator.save",
        {
            "id": ind,
            "node_id": node,
            "indicator": {"name": "Personnes formées", "unit": "count", "source_type": "routine"},
        },
    )
    out = officer("sync.folder", {"path": str(shared)})
    assert out["sync"]["written"] >= 1
    got = admin("sync.folder", {"path": str(shared)})
    assert any(n["title"] == "Produit de Koffi" for n in got["framework"])
    got = officer("sync.folder", {})
    assert got["indicators"][0]["name"] == "Personnes formées"
    # Both change the same indicator before syncing: the later wins, the other is kept as a conflict.
    officer(
        "indicator.save",
        {"id": ind, "node_id": node, "indicator": {"name": "Version Koffi", "unit": "count", "source_type": "routine"}},
    )
    admin(
        "indicator.save",
        {"id": ind, "node_id": node, "indicator": {"name": "Version Aïcha", "unit": "count", "source_type": "routine"}},
    )
    officer("sync.folder", {})
    snap = admin("sync.folder", {})
    assert snap["indicators"][0]["name"] == "Version Aïcha"
    conflicts = snap["team"]["conflicts"]
    assert len(conflicts) == 1 and conflicts[0]["kind"] == "conflict"
    # The administrator can take the other version after all.
    snap = admin("conflict.resolve", {"id": conflicts[0]["id"], "accept": True})
    assert snap["indicators"][0]["name"] == "Version Koffi" and snap["team"]["conflicts"] == []
    # The choice reaches the other copy, which had kept its own conflict.
    admin("sync.folder", {})
    snap = officer("sync.folder", {})
    assert snap["indicators"][0]["name"] == "Version Koffi"
    # A later edit that builds on what was received is not a conflict.
    officer(
        "indicator.save",
        {"id": ind, "node_id": node, "indicator": {"name": "Suite", "unit": "count", "source_type": "routine"}},
    )
    officer("sync.folder", {})
    snap = admin("sync.folder", {})
    assert snap["indicators"][0]["name"] == "Suite" and snap["team"]["conflicts"] == []

    # Validated data: a later change from an officer becomes a request, never applied.
    sub = admin("submission.open", {"period": "T1-2026"})["created"]
    admin("submission.save", {"id": sub, "values": [{"indicator_id": ind, "value": 12}]})
    admin("submission.act", {"id": sub, "action": "submit"})
    admin("submission.act", {"id": sub, "action": "validate"})
    admin("sync.folder", {})
    officer("sync.folder", {})
    # Koffi edits the validated values directly in his copy (as an old copy would).
    officer_path = tmp_path / "koffi.sme"
    officer("project.close")
    conn = sqlite3.connect(officer_path)
    from sme_engine import sync

    officer.mp.setenv("SME_TRUST_DIR", str(officer.home))
    sync.attach(conn)
    conn.execute("UPDATE value SET value = 99 WHERE submission_id = ?", (sub,))
    conn.commit()
    conn.close()
    officer("project.open", {"path": str(officer_path)})
    officer("sync.folder", {})
    snap = admin("sync.folder", {})
    requests = [c for c in snap["team"]["conflicts"] if c["kind"] == "request"]
    assert requests and requests[0]["table"] == "value"
    detail = admin("submission.get", {"id": sub})
    assert detail["cells"][ind][""][0] == 12


def test_partner_scope_signatures_and_packages(team, tmp_path):
    admin, focal = team("Aïcha"), team("Point focal")
    node, ind = _setup(admin, tmp_path)
    a = admin("partner.save", {"partner": {"name": "ONG A"}})["created"]
    b = admin("partner.save", {"partner": {"name": "ONG B"}})["created"]
    admin("profile.set", {"profile": {"start": "2026-01-01", "end": "2026-12-31", "reporting_by": "partner"}})
    sub_b = admin("submission.open", {"period": "T1-2026", "partner_id": b})["created"]
    admin("submission.save", {"id": sub_b, "values": [{"indicator_id": ind, "value": 5}]})
    admin("feedback.save", {"feedback": {"received": "2026-02-01", "category": "info_request", "summary": "Question"}})
    mid, join = _invite(admin, focal, tmp_path, ["partner"], [a])
    snap = focal("team.join", {"path": join, "password": "secret partagé", "target": str(tmp_path / "focal.sme")})
    # The partner gets the design and nothing of the other partner nor the feedback.
    assert snap["indicators"] and snap["submissions"] == [] and snap["feedback"] == []
    sub_a = focal("submission.open", {"period": "T1-2026", "partner_id": a})["created"]
    focal("submission.save", {"id": sub_a, "values": [{"indicator_id": ind, "value": 7}]})
    focal("submission.act", {"id": sub_a, "action": "submit"})
    # A change outside its scope is refused by the administrator's copy.
    focal("partner.save", {"id": b, "partner": {"name": "Renommé par A"}})
    pkg = focal(
        "sync.package", {"member_id": admin("project.get")["team"]["owner"], "path": str(tmp_path / "pour-admin")}
    )
    got = admin("sync.receive", {"path": pkg["path"]})
    assert got["sync"]["refused"] >= 1
    assert {s["id"] for s in got["submissions"]} == {sub_a, sub_b}
    assert next(x for x in got["partners"] if x["id"] == b)["name"] == "ONG B"
    # Package back to the partner: only its own data.
    admin("submission.act", {"id": sub_a, "action": "return", "comment": "Vérifier le registre"})
    back = admin("sync.package", {"member_id": mid, "path": str(tmp_path / "pour-a")})
    snap = focal("sync.receive", {"path": back["path"]})
    assert {s["id"]: s["status"] for s in snap["submissions"]} == {sub_a: "returned"}
    # A tampered file is refused.
    raw = bytearray(Path(back["path"]).read_bytes())
    raw[-5] ^= 0xFF
    bad = tmp_path / "abime.smesync"
    bad.write_bytes(bytes(raw))
    with pytest.raises(RuntimeError, match="sync_other_project|password_wrong"):
        focal("sync.receive", {"path": str(bad)})
    # A stranger cannot add members.
    with pytest.raises(RuntimeError, match="not_allowed"):
        focal("member.update", {"id": mid, "roles": ["admin"]})


def test_relay_server_carries_files_it_cannot_read(team, tmp_path):
    sys.path.insert(0, str(ROOT / "server"))
    import relay

    admin, officer = team("Aïcha"), team("Koffi")
    _setup(admin, tmp_path)
    _mid, join = _invite(admin, officer, tmp_path, ["officer"])
    officer("team.join", {"path": join, "password": "secret partagé", "target": str(tmp_path / "k.sme")})
    uid = admin("project.get")["project"].get("uid") or json.loads("{}").get("x")
    uid = sqlite3.connect(tmp_path / "admin.sme").execute("SELECT value FROM meta WHERE key='uid'").fetchone()[0]
    data = tmp_path / "relay"
    data.mkdir()
    (data / "keys.txt").write_text(f"{uid} cle-du-projet\n", encoding="utf-8")
    httpd = relay.serve(data, "127.0.0.1", 0)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    url = f"http://127.0.0.1:{httpd.server_address[1]}"
    try:
        with pytest.raises(RuntimeError, match="server_auth"):
            admin("sync.server", {"url": url, "secret": "mauvaise"})
        admin("framework.add", {"title": "Par le serveur"})
        admin("sync.server", {"url": url, "secret": "cle-du-projet"})
        got = officer("sync.server", {"url": url, "secret": "cle-du-projet"})
        assert any(n["title"] == "Par le serveur" for n in got["framework"])
        stored = b"".join(f.read_bytes() for f in (data / uid).glob("*.smesync"))
        assert b"Par le serveur" not in stored  # encrypted at rest on the server
    finally:
        httpd.shutdown()


def test_encryption_audit_documents_and_personal_data(team, tmp_path):
    admin = team("Aïcha")
    node, ind = _setup(admin, tmp_path)
    path = tmp_path / "admin.sme"
    # Sensitive data needs a protected project.
    with pytest.raises(RuntimeError, match="encryption_required"):
        admin("feedback.save", {"feedback": {"received": "2026-02-01", "category": "sea", "summary": "Cas"}})
    with pytest.raises(RuntimeError, match="password_short"):
        admin("project.encrypt", {"password": "court"})
    admin("project.encrypt", {"password": "mot de passe long"})
    assert path.read_bytes().startswith(b"SMEENC1")
    fb = admin(
        "feedback.save",
        {
            "feedback": {
                "received": "2025-01-01",
                "category": "sea",
                "summary": "Cas confidentiel de Kara",
                "detail": "Détail",
                "person": "X",
            }
        },
    )
    fid = fb["feedback"][0]["id"]
    admin("project.close")
    with pytest.raises(RuntimeError, match="password_required"):
        admin("project.open", {"path": str(path)})
    with pytest.raises(RuntimeError, match="password_wrong"):
        admin("project.open", {"path": str(path), "password": "faux mot de passe"})
    snap = admin("project.open", {"path": str(path), "password": "mot de passe long"})
    assert snap["feedback"][0]["summary"] == "Cas confidentiel de Kara"
    assert b"Cas confidentiel de Kara" not in path.read_bytes()
    # Sensitive data cannot leave the protection.
    with pytest.raises(RuntimeError, match="encryption_required"):
        admin("project.decrypt", {"password": "mot de passe long"})
    # Reading a sensitive case is written in the audit trail.
    admin("feedback.reveal", {"id": fid})
    trail = admin("audit.list")
    assert trail["intact"] and [e["action"] for e in trail["entries"]][:2] == ["sensitive_viewed", "encrypted"]
    # Supporting document, kept with its fingerprint.
    doc = tmp_path / "pv.pdf"
    doc.write_bytes(b"%PDF-1.4 proces-verbal")
    sub = admin("submission.open", {"period": "T1-2026"})["created"]
    snap = admin("attachment.add", {"owner_kind": "submission", "owner_id": sub, "path": str(doc), "description": "PV"})
    assert snap["attachments"] == {f"submission:{sub}": 1}
    att = admin("attachment.list", {"owner_kind": "submission", "owner_id": sub})["attachments"][0]
    out = admin("attachment.save_as", {"id": att["id"], "path": str(tmp_path / "copie.pdf")})
    assert Path(out["path"]).read_bytes() == doc.read_bytes()
    # Retention: closed cases older than the limit lose their personal data.
    admin("privacy.settings", {"retention_months": 6})
    fb = admin("project.get")["feedback"][0]
    admin("feedback.save", {"id": fid, "feedback": {**fb, "person": "", "status": "closed"}})
    assert "privacy" in {t["kind"] for t in admin("today.project", {"today": "2026-03-01"})["tasks"]}
    snap = admin("privacy.purge", {"today": "2026-03-01"})
    assert snap["purged"] == 1 and snap["feedback"][0]["person"] == "" and snap["feedback"][0]["detail"] == ""
    # The audit trail cannot be changed, even by hand.
    admin("project.close")
    admin("project.open", {"path": str(path), "password": "mot de passe long"})
    work = next((tmp_path / "home-Aïcha" / "work").glob("*.sme"))
    conn = sqlite3.connect(work)
    with pytest.raises(sqlite3.DatabaseError, match="append-only"):
        conn.execute("DELETE FROM audit")
    conn.close()
