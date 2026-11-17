# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 GAYI Komi Selassi and SANOUSSI Moudjibou

"""Acceptance paths of the specification (section 11), played through the engine.

1. A three-year project, four partners, thirty sites, forty indicators, quarterly
   reports: design, targets, twelve quarters of data by entry and by Excel form,
   validation, locking, quarterly, annual and final reports. Every figure of the
   tracking table is computed again here, independently, from the values sent.
2. A team of three members and two partners synchronised by packages, a shared
   folder and the relay server, with conflicts provoked.
3. A portfolio of five projects of different donors: dashboard and indicators
   common to several projects.

The evaluation path (mid-term and final on public survey data, difference in
differences) is played by test_flow.py on the real files.
"""

from __future__ import annotations

import io
import json
import random
import sys
import threading
from pathlib import Path

import pytest

from sme_engine.methods import register
from sme_engine.r_bridge import RBridge
from sme_engine.rpc import Server

sys.path.insert(0, str(Path(__file__).parent))
from test_team import _invite, team  # noqa: E402, F401  (the fixture is used by name)

ROOT = Path(__file__).resolve().parents[3]


@pytest.fixture()
def call():
    bridge = RBridge()
    server = Server(stdin=io.StringIO(), stdout=io.StringIO())
    register(server, bridge)

    def _call(method, params=None):
        resp = server.handle_line(json.dumps({"jsonrpc": "2.0", "id": 1, "method": method, "params": params or {}}))
        if "error" in resp:
            raise RuntimeError(resp["error"]["data"]["key"] + ": " + resp["error"]["message"])
        return resp["result"]

    yield _call
    bridge.stop()


# ----- 1. a three-year project ------------------------------------------------------------------


def _design(call, path: Path, donors=("Union européenne",), sector="Éducation", n_ind=40, n_sites=30):
    call(
        "project.create",
        {
            "path": str(path),
            "name": path.stem,
            "profile": {
                "start": "2026-01-01",
                "end": "2028-12-31",
                "frequency": "quarterly",
                "reporting_by": "partner",
                "donors": [{"name": d} for d in donors],
                "sector": sector,
                "country": "Togo",
            },
            "disaggregations": ["sex"],
        },
    )
    sites = [call("place.save", {"place": {"name": f"Site {k:02d}"}})["created"] for k in range(n_sites)]
    partners = [
        call(
            "partner.save",
            {"partner": {"name": f"ONG {c}", "acronym": c, "place_ids": sites[k::4]}},
        )["created"]
        for k, c in enumerate("ABCD")
    ]
    impact = call("framework.add", {"level": "impact", "title": "Les enfants achèvent le primaire"})["created"]
    outcomes = [call("framework.add", {"title": f"Effet {k + 1}", "parent_id": impact})["created"] for k in range(4)]
    inds = []
    for k in range(n_ind):
        kind = ("count", "percent", "count", "milestone")[k % 4]
        spec = {
            "name": f"Indicateur {k + 1:02d}",
            "unit": kind,
            "source_type": "routine",
            "frequency": "quarterly",
        }
        if kind == "count":
            spec |= {"breakdowns": ["sex"], "target": 4000}
        elif kind == "percent":
            spec |= {"baseline_manual": 0.4, "target": 0.8}
        iid = call("indicator.save", {"node_id": outcomes[k % 4], "indicator": spec})["saved"]
        inds.append((iid, kind))
    periods = [p["code"] for p in call("project.get")["periods"]]
    # Targets by period for the counts: 4000 over twelve quarters.
    for iid, kind in inds:
        if kind == "count":
            for code in periods:
                call("target.set", {"indicator_id": iid, "period": code, "value": 4000 / 12})
    return periods, partners, inds


def _values(rnd, inds, q):
    out, sent = [], {}
    for iid, kind in inds:
        if kind == "count":
            f, m = rnd.randint(40, 50), rnd.randint(35, 45)
            out += [
                {"indicator_id": iid, "cats": {"sex": "f"}, "value": f},
                {"indicator_id": iid, "cats": {"sex": "m"}, "value": m},
                {"indicator_id": iid, "value": f + m},
            ]
            sent[iid] = (f + m, None, None)
        elif kind == "percent":
            den = rnd.randint(95, 105)
            num = int(den * (0.5 + q * 0.02)) + rnd.randint(-1, 1)
            out.append({"indicator_id": iid, "numerator": num, "denominator": den})
            sent[iid] = (None, num, den)
        else:
            done = 1 if q >= 6 else 0
            out.append({"indicator_id": iid, "value": done})
            sent[iid] = (done, None, None)
    return out, sent


def _expected(inds, sent, periods, upto):
    """The tracking figures computed again, from the values sent, without the engine."""
    exp = {}
    for iid, kind in inds:
        cells = [sent[(p, part)][iid] for p in periods[: upto + 1] for part in sent["partners"] if (p, part) in sent]
        last = [sent[(periods[upto], part)][iid] for part in sent["partners"]]
        if kind == "count":  # summed over partners, cumulated over time
            exp[iid] = (sum(c[0] for c in last), sum(c[0] for c in cells))
        elif kind == "percent":  # numerators and denominators added, the latest period stands
            ratio = sum(c[1] for c in last) / sum(c[2] for c in last)
            exp[iid] = (ratio, ratio)
        else:  # a milestone is reached when every partner reached it
            v = 1.0 if all(c[0] == 1 for c in last) else 0.0
            exp[iid] = (v, v)
    return exp


def test_three_year_project_of_four_partners(call, tmp_path):
    from docx import Document
    from openpyxl import load_workbook

    path = tmp_path / "trois-ans.sme"
    periods, partners, inds = _design(call, path)
    assert len(periods) == 12 and len(inds) == 40
    rnd = random.Random(11)
    sent: dict = {"partners": partners}
    folder = tmp_path / "canevas"
    folder.mkdir()
    for q, code in enumerate(periods):
        for k, part in enumerate(partners):
            values, cells = _values(rnd, inds, q)
            sent[(code, part)] = cells
            if k == 0 and q in (2, 7):
                # This partner sends the Excel form for two quarters.
                files = call("canevas.write", {"path": str(folder), "period": code})["files"]
                file = folder / next(f for f in files if f.endswith("-A.xlsx"))
                wb = load_workbook(file)
                ws = wb["Saisie"]
                by_line = {}
                for row in range(9, ws.max_row + 1):
                    name, cat = ws.cell(row=row, column=2).value, ws.cell(row=row, column=3).value
                    if name:
                        by_line[(name, cat)] = row
                names = {iid: f"Indicateur {i + 1:02d}" for i, (iid, _k) in enumerate(inds)}
                for v in values:
                    sex = (v.get("cats") or {}).get("sex")
                    if sex is None and (names[v["indicator_id"]], "Femme") in by_line:
                        continue  # broken down: the total is the sum of the categories
                    row = by_line[(names[v["indicator_id"]], {"f": "Femme", "m": "Homme"}.get(sex, "Total"))]
                    if "numerator" in v:
                        ws.cell(row=row, column=5).value = v["numerator"]
                        ws.cell(row=row, column=6).value = v["denominator"]
                    else:
                        ws.cell(row=row, column=4).value = v["value"]
                wb.save(file)
                res = call("canevas.receive", {"path": str(file)})
                assert res["applied"]
                sid = next(s["id"] for s in res["submissions"] if s["partner_id"] == part and s["period"] == code)
            else:
                sid = call("submission.open", {"period": code, "partner_id": part})["created"]
                call("submission.save", {"id": sid, "values": values})
                call("submission.act", {"id": sid, "action": "submit"})
            call("submission.act", {"id": sid, "action": "validate"})
        period = next(p for p in call("project.get")["periods"] if p["code"] == code)
        call("period.set_state", {"id": period["id"], "state": "locked"})

        # The tracking table of the quarter against the independent computation.
        if q in (0, 3, 11):
            table = {r["indicator_id"]: r for r in call("tracking.table", {"period": code})["rows"]}
            for iid, (in_period, to_date) in _expected(inds, sent, periods, q).items():
                assert table[iid]["value_period"] == pytest.approx(in_period), (q, iid)
                assert table[iid]["to_date"] == pytest.approx(to_date), (q, iid)

    snap = call("project.get")
    assert all(p["state"] == "locked" for p in snap["periods"])
    assert all(s["status"] == "locked" for s in snap["submissions"])
    # Quarterly, annual and final reports.
    for name, frm, to in [
        ("trimestre", periods[11], periods[11]),
        ("annuel", periods[8], periods[11]),
        ("final", periods[0], periods[11]),
    ]:
        out = tmp_path / f"{name}.docx"
        call("reports.generate", {"path": str(out), "format": "eu", "from": frm, "to": to, "lang": "fr"})
        doc = Document(str(out))
        cells = "\n".join(c.text for t in doc.tables for r in t.rows for c in r.cells)
        assert "Indicateur 01" in cells and "Indicateur 40" in cells


# ----- 2. a team of three members and two partners -----------------------------------------------


def test_team_of_three_and_two_partners_by_the_three_ways(team, tmp_path):  # noqa: F811
    sys.path.insert(0, str(ROOT / "server"))
    import sqlite3

    import relay

    admin, officer, validator = team("Aïcha"), team("Koffi"), team("Mariam")
    focal_a, focal_b = team("Point focal A"), team("Point focal B")
    admin(
        "project.create",
        {
            "path": str(tmp_path / "admin.sme"),
            "name": "Projet d'équipe",
            "profile": {"start": "2026-01-01", "end": "2026-12-31", "reporting_by": "partner"},
        },
    )
    node = admin("framework.add", {"title": "Effet"})["created"]
    ind = admin(
        "indicator.save", {"node_id": node, "indicator": {"name": "Formés", "unit": "count", "source_type": "routine"}}
    )["saved"]
    a = admin("partner.save", {"partner": {"name": "ONG A"}})["created"]
    b = admin("partner.save", {"partner": {"name": "ONG B"}})["created"]
    admin("team.start", {"name": "Aïcha"})
    copies = {}
    for who, roles, scope, name in [
        (officer, ["officer"], [], "koffi"),
        (validator, ["validator"], [], "mariam"),
        (focal_a, ["partner"], [a], "focal-a"),
        (focal_b, ["partner"], [b], "focal-b"),
    ]:
        mid, join = _invite(admin, who, tmp_path, roles, scope)
        target = tmp_path / f"{name}.sme"
        who("team.join", {"path": join, "password": "secret partagé", "target": str(target)})
        copies[name] = mid

    shared = tmp_path / "partage"
    shared.mkdir()
    uid = sqlite3.connect(tmp_path / "admin.sme").execute("SELECT value FROM meta WHERE key='uid'").fetchone()[0]
    data = tmp_path / "relais"
    data.mkdir()
    (data / "keys.txt").write_text(f"{uid} cle\n", encoding="utf-8")
    httpd = relay.serve(data, "127.0.0.1", 0)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    url = f"http://127.0.0.1:{httpd.server_address[1]}"
    try:
        # Partner A by package, partner B by the server, the office by the shared folder.
        sa = focal_a("submission.open", {"period": "T1-2026", "partner_id": a})["created"]
        focal_a("submission.save", {"id": sa, "values": [{"indicator_id": ind, "value": 7}]})
        focal_a("submission.act", {"id": sa, "action": "submit"})
        owner = admin("project.get")["team"]["owner"]
        pkg = focal_a("sync.package", {"member_id": owner, "path": str(tmp_path / "de-a")})
        admin("sync.receive", {"path": pkg["path"]})
        sb = focal_b("submission.open", {"period": "T1-2026", "partner_id": b})["created"]
        focal_b("submission.save", {"id": sb, "values": [{"indicator_id": ind, "value": 5}]})
        focal_b("submission.act", {"id": sb, "action": "submit"})
        focal_b("sync.server", {"url": url, "secret": "cle"})
        admin("sync.server", {"url": url, "secret": "cle"})
        admin("sync.folder", {"path": str(shared)})
        got = validator("sync.folder", {"path": str(shared)})
        assert {s["id"]: s["status"] for s in got["submissions"]} == {sa: "submitted", sb: "submitted"}
        # The validator validates; the officer and the administrator change the same result meanwhile.
        validator("submission.act", {"id": sa, "action": "validate"})
        validator("submission.act", {"id": sb, "action": "validate"})
        officer("sync.folder", {"path": str(shared)})
        officer("framework.update", {"id": node, "title": "Effet selon Koffi"})
        admin("framework.update", {"id": node, "title": "Effet selon Aïcha"})
        for who in (validator, officer):
            who("sync.folder", {})
        snap = admin("sync.folder", {})
        assert {s["id"]: s["status"] for s in snap["submissions"]} == {sa: "validated", sb: "validated"}
        assert next(n for n in snap["framework"] if n["id"] == node)["title"] == "Effet selon Aïcha"
        assert [c["kind"] for c in snap["team"]["conflicts"]] == ["conflict"]
        # A partner never changes a validated submission: its edit becomes a request.
        admin("sync.server", {"url": url, "secret": "cle"})
        back = admin("sync.package", {"member_id": copies["focal-a"], "path": str(tmp_path / "pour-a")})
        snap = focal_a("sync.receive", {"path": back["path"]})
        assert {s["id"]: s["status"] for s in snap["submissions"]} == {sa: "validated"}  # its scope only
        with pytest.raises(RuntimeError, match="submission_validated"):
            focal_a("submission.save", {"id": sa, "values": [{"indicator_id": ind, "value": 70}]})
        # Every copy ends with the same figures.
        snap = focal_b("sync.server", {"url": url, "secret": "cle"})
        assert {s["id"]: s["status"] for s in snap["submissions"]} == {sb: "validated"}
        total = admin("tracking.table", {"period": "T1-2026"})["rows"][0]["value_period"]
        assert total == 12
        assert validator("tracking.table", {"period": "T1-2026"})["rows"][0]["value_period"] == 12
    finally:
        httpd.shutdown()


# ----- 3. a portfolio of five projects -----------------------------------------------------------


def test_portfolio_of_five_projects_of_different_donors(call, tmp_path):
    donors = ["Union européenne", "USAID", "AFD", "UNICEF", "Banque mondiale"]
    paths = []
    for k, donor in enumerate(donors):
        path = tmp_path / f"projet-{k + 1}.sme"
        periods, partners, inds = _design(call, path, donors=(donor,), n_ind=1, n_sites=8)
        # The first indicator is common to all projects: children enrolled.
        iid = inds[0][0]
        node = call("project.get")["indicators"][0]["node_id"]
        call(
            "indicator.save",
            {
                "id": iid,
                "node_id": node,
                "indicator": {
                    "name": "Enfants inscrits",
                    "unit": "count",
                    "source_type": "routine",
                    "target": 4000,
                    "library_id": "education.enrolled",
                },
            },
        )
        for code in periods[:4]:
            sid = call("submission.open", {"period": code, "partner_id": partners[0]})["created"]
            call("submission.save", {"id": sid, "values": [{"indicator_id": iid, "value": 100 * (k + 1)}]})
            call("submission.act", {"id": sid, "action": "submit"})
            call("submission.act", {"id": sid, "action": "validate"})
        call("project.close")
        paths.append(str(path))
    dash = call("portfolio.dashboard", {"paths": paths, "today": "2027-01-15"})
    assert len(dash["cards"]) == 5
    assert sorted(d["name"] for c in dash["cards"] for d in c["profile"]["donors"]) == sorted(donors)
    common = next(c for c in dash["common"] if c["library_id"] == "education.enrolled")
    # Four quarters in each project: 400 + 800 + 1200 + 1600 + 2000.
    assert common["total"] == 6000 and len(common["projects"]) == 5
    assert common["double_count_possible"]  # people may be counted by two projects
    agenda = call("workspace.agenda", {"paths": paths, "start": "2027-01-01", "end": "2027-03-31", "lang": "fr"})
    assert agenda["events"]  # the reporting deadlines of the five projects
