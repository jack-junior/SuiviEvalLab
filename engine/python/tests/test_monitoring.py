# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 GAYI Komi Selassi and SANOUSSI Moudjibou

"""Rules of calculation (section 6), reception of submissions, checks, locking."""

from __future__ import annotations

import io
import json
import sqlite3

import pytest

from sme_engine import monitoring as m
from sme_engine.methods import register
from sme_engine.r_bridge import RBridge
from sme_engine.rpc import Server

M = m.Measure


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


# ----- section 6.1 and 6.2: types and aggregation ----------------------------------------


def test_fractions_add_numerators_and_denominators_never_percentages():
    pct = {"unit": "percent"}
    # 10/20 and 90/100: 100/120, not the mean of 50 % and 90 %.
    out = m.combine(pct, [M(0.5, 10, 20), M(0.9, 90, 100)])
    assert out.value == pytest.approx(100 / 120) and out.num == 100 and out.den == 120
    # Without denominators, refused and explained.
    refused = m.combine(pct, [M(0.5), M(0.9)])
    assert refused.value is None and refused.reason == "no_denominator"
    # A single value is used as it is.
    assert m.combine(pct, [M(0.5)]).value == 0.5
    # Rates per 1 000 keep their base.
    rate = {"unit": "rate", "multiplier": 1000}
    assert m.combine(rate, [M(None, 3, 1000), M(None, 1, 1000)]).value == pytest.approx(2.0)


def test_counts_means_levels_and_milestones():
    assert m.combine({"unit": "count"}, [M(3), M(4)]).value == 7
    mean = {"unit": "mean"}
    assert m.combine(mean, [M(10, None, 1), M(20, None, 3)]).value == pytest.approx(17.5)
    assert m.combine(mean, [M(10), M(20)]).reason == "no_weights"
    assert m.combine({"unit": "median"}, [M(3), M(4)]).reason == "not_additive"
    ms = {"unit": "milestone"}
    assert m.combine(ms, [M(1), M(0)]).value == 0 and m.combine(ms, [M(1), M(1)]).value == 1


def test_aggregation_in_time():
    count = {"unit": "count", "aggregation": "sum"}
    assert m.over_time(count, [M(3), M(None), M(4)]).value == 7
    pct = {"unit": "percent", "aggregation": "sum"}
    assert m.over_time(pct, [M(0.5, 5, 10), M(1.0, 10, 10)]).value == pytest.approx(0.75)
    assert m.over_time({"unit": "percent", "aggregation": "last"}, [M(0.5), M(0.7)]).value == 0.7
    assert m.over_time({"unit": "count", "aggregation": "max"}, [M(5), M(9), M(7)]).value == 9
    assert m.over_time({"unit": "score", "aggregation": "mean"}, [M(2), M(4)]).value == 3


def test_typed_cells():
    pct = {"unit": "percent"}
    assert m.clean_cell(pct, {"numerator": "45", "denominator": "60"}) == (0.75, 45, 60)
    assert m.clean_cell(pct, {"value": "45 %"})[0] == pytest.approx(0.45)
    assert m.clean_cell({"unit": "count"}, {"value": "1 250,5"})[0] == 1250.5
    with pytest.raises(Exception, match="milestone"):
        m.clean_cell({"unit": "milestone"}, {"value": 2})


# ----- section 6.5: targets to date, achievement, status ------------------------------------

PERIODS = [
    {"code": "T1", "start": "2026-01-01", "end": "2026-03-31"},
    {"code": "T2", "start": "2026-04-01", "end": "2026-06-30"},
    {"code": "T3", "start": "2026-07-01", "end": "2026-09-30"},
    {"code": "T4", "start": "2026-10-01", "end": "2026-12-31"},
]


def test_targets_to_date():
    count = {"unit": "count", "aggregation": "sum", "target": 100}
    assert m.target_to_date(count, PERIODS, 1, {"T1": 20, "T2": 30}, None, None) == (50, False)
    pct = {"unit": "percent", "aggregation": "last", "target": 0.8}
    assert m.target_to_date(pct, PERIODS, 2, {"T1": 0.5, "T2": 0.6}, None, None) == (0.6, False)
    # No targets by period: straight line from the baseline, flagged.
    pct["baseline_manual"] = 0.4
    t, interpolated = m.target_to_date(pct, PERIODS, 1, {}, "2026-01-01", "2026-12-31")
    assert interpolated and t == pytest.approx(0.4 + 0.4 * 180 / 364)


def test_rate_and_status_follow_the_direction():
    up = {"unit": "count", "aggregation": "sum", "target": 100}
    assert m.rate(up, 45, 50) == 0.9 and m.status(up, 45, 50, True) == "on_track"
    assert m.status(up, 40, 50, True) == "late" and m.status(up, 100, 50, True) == "achieved"
    assert m.status(up, None, 50, True) == "no_data" and m.status(up, None, 50, False) == "not_started"
    # Decrease: from a baseline of 40 % to a target of 20 %; at 30 % against 30 % to date.
    down = {"unit": "percent", "direction": "decrease", "baseline_manual": 0.4, "target": 0.2}
    assert m.rate(down, 0.3, 0.3) == pytest.approx(1.0)
    assert m.status(down, 0.35, 0.3, True) == "late" and m.status(down, 0.2, 0.3, True) == "achieved"


# ----- reception ---------------------------------------------------------------------------


def _project(call, tmp_path, **profile):
    prof = {"start": "2026-01-01", "end": "2026-12-31", "frequency": "quarterly", **profile}
    call(
        "project.create",
        {"path": str(tmp_path / "p.sme"), "name": "P", "profile": prof, "disaggregations": ["sex"]},
    )
    node = call("framework.add", {"title": "Effet"})["created"]
    return node


def test_reception_flow_checks_and_validation(call, tmp_path):
    node = _project(call, tmp_path)
    vacc = call(
        "indicator.save",
        {
            "node_id": node,
            "indicator": {
                "name": "Enfants vaccinés",
                "unit": "percent",
                "source_type": "routine",
                "breakdowns": ["sex"],
                "baseline_manual": 0.5,
                "target": 0.9,
            },
        },
    )["saved"]
    sub = call("submission.open", {"period": "T1-2026"})["created"]
    # Opening again gives the same submission.
    assert call("submission.open", {"period": "T1-2026"})["created"] == sub
    res = call(
        "submission.save",
        {
            "id": sub,
            "values": [
                {"indicator_id": vacc, "numerator": 50, "denominator": 100},
                {"indicator_id": vacc, "cats": {"sex": "f"}, "numerator": 30, "denominator": 50},
                {"indicator_id": vacc, "cats": {"sex": "m"}, "numerator": 30, "denominator": 40},
            ],
        },
    )
    checks = {a["check"]: a for a in res["alerts"]}
    assert "total_mismatch" in checks and checks["total_mismatch"]["severity"] == "review"
    with pytest.raises(RuntimeError, match="alerts_open"):
        call("submission.act", {"id": sub, "action": "validate"})
    # A numerator above its denominator blocks; a justification does not lift it.
    res = call(
        "submission.save",
        {"id": sub, "values": [{"indicator_id": vacc, "cats": {"sex": "f"}, "numerator": 60, "denominator": 50}]},
    )
    assert any(a["check"] == "num_gt_den" and a["severity"] == "blocking" for a in res["alerts"])
    # Corrected: the total is left out, the cells make it.
    res = call(
        "submission.save",
        {
            "id": sub,
            "values": [
                {"indicator_id": vacc, "cats": {"sex": "f"}, "numerator": 40, "denominator": 50},
                {"indicator_id": vacc, "cats": {"sex": "m"}, "numerator": 30, "denominator": 50},
            ],
        },
    )
    assert not [a for a in res["alerts"] if a["severity"] != "info"]
    call("submission.act", {"id": sub, "action": "submit"})
    with pytest.raises(RuntimeError, match="comment_required"):
        call("submission.act", {"id": sub, "action": "return"})
    res = call("submission.act", {"id": sub, "action": "return", "comment": "Vérifier le registre de Kara"})
    assert res["submission"]["status"] == "returned" and res["submission"]["comment"].startswith("Vérifier")
    call("submission.act", {"id": sub, "action": "submit"})
    res = call("submission.act", {"id": sub, "action": "validate"})
    assert res["submission"]["status"] == "validated"
    assert [h["action"] for h in res["submission"]["history"]] == [
        "create",
        "submit",
        "return",
        "submit",
        "validate",
    ]
    # Validated values cannot change until reopened with a reason.
    with pytest.raises(RuntimeError, match="submission_validated"):
        call("submission.save", {"id": sub, "values": []})

    table = call("tracking.table", {"period": "T1-2026", "today": "2026-04-15"})
    row = table["rows"][0]
    assert row["value_period"] == pytest.approx(0.7) and row["to_date"] == pytest.approx(0.7)
    assert row["interpolated"] is True  # no targets by period: straight line to 90 %
    women = call("tracking.breakdown", {"indicator_id": vacc, "key": "sex", "period": "T1-2026"})
    assert women["values"]["f"] == pytest.approx(0.8) and women["values"]["m"] == pytest.approx(0.6)

    # Locking the period locks its submissions; reopening needs a reason.
    period = next(p for p in res["periods"] if p["code"] == "T1-2026")
    snap = call("period.set_state", {"id": period["id"], "state": "locked"})
    assert snap["submissions"][0]["status"] == "locked"
    with pytest.raises(RuntimeError, match="period_locked"):
        call("submission.act", {"id": sub, "action": "reopen", "comment": "x"})
    with pytest.raises(RuntimeError, match="comment_required"):
        call("period.set_state", {"id": period["id"], "state": "open"})
    snap = call("period.set_state", {"id": period["id"], "state": "open", "reason": "Erreur de saisie à Kara"})
    assert snap["submissions"][0]["status"] == "validated"
    res = call("submission.act", {"id": sub, "action": "reopen", "comment": "Erreur de saisie"})
    assert res["submission"]["status"] == "draft"


def test_period_lock_needs_validated_submissions(call, tmp_path):
    node = _project(call, tmp_path)
    ind = call(
        "indicator.save",
        {"node_id": node, "indicator": {"name": "Formés", "unit": "count", "source_type": "routine"}},
    )["saved"]
    sub = call("submission.open", {"period": "T1-2026"})["created"]
    snap = call("submission.save", {"id": sub, "values": [{"indicator_id": ind, "value": 10}]})
    period = snap["periods"][0]
    with pytest.raises(RuntimeError, match="period_unvalidated"):
        call("period.set_state", {"id": period["id"], "state": "locked"})


def test_partners_provisional_values_and_justified_alerts(call, tmp_path):
    node = _project(call, tmp_path, reporting_by="partner")
    a = call("partner.save", {"partner": {"name": "ONG A"}})["created"]
    b = call("partner.save", {"partner": {"name": "ONG B"}})["created"]
    snap = call("partner.save", {"partner": {"name": "Bailleur", "role": "funding"}})
    assert [u["partner_id"] for u in snap["units"]] == [a, b]  # the funder does not report
    ind = call(
        "indicator.save",
        {
            "node_id": node,
            "indicator": {
                "name": "Personnes formées",
                "unit": "count",
                "source_type": "routine",
                "target": 400,
                "bounds": {"max": 150},
            },
        },
    )["saved"]
    call("target.set", {"indicator_id": ind, "period": "T1-2026", "value": 100})
    sa = call("submission.open", {"period": "T1-2026", "partner_id": a})["created"]
    res = call("submission.save", {"id": sa, "values": [{"indicator_id": ind, "value": 200}]})
    bounds = next(x for x in res["alerts"] if x["check"] == "bounds")
    res = call("alert.justify", {"key": bounds["key"], "text": "Deux sessions de formation ce trimestre"})
    assert res["alerts"][0]["justification"].startswith("Deux sessions")
    call("submission.act", {"id": sa, "action": "validate"})
    sb = call("submission.open", {"period": "T1-2026", "partner_id": b})["created"]
    call("submission.save", {"id": sb, "values": [{"indicator_id": ind, "value": 50}]})
    final = call("tracking.table", {"period": "T1-2026", "today": "2026-04-15"})["rows"][0]
    assert final["value_period"] == 200 and not final["provisional"]
    prov = call("tracking.table", {"period": "T1-2026", "today": "2026-04-15", "provisional": True})["rows"][0]
    assert prov["value_period"] == 250 and prov["provisional"]
    assert prov["status"] == "on_track" and prov["rate_to_date"] == pytest.approx(2.5)
    only_b = call("tracking.table", {"period": "T1-2026", "provisional": True, "partner_id": b})["rows"][0]
    assert only_b["value_period"] == 50
    # A draft can be deleted, a validated submission cannot.
    with pytest.raises(RuntimeError, match="submission_validated"):
        call("submission.delete", {"id": sa})
    call("submission.delete", {"id": sb})


def test_gap_comments(call, tmp_path):
    node = _project(call, tmp_path)
    ind = call(
        "indicator.save",
        {"node_id": node, "indicator": {"name": "Formés", "unit": "count", "source_type": "routine"}},
    )["saved"]
    snap = call("gap.save", {"indicator_id": ind, "period": "T1-2026", "text": "Retard des fournitures"})
    assert snap["gap_comments"][ind][0]["text"] == "Retard des fournitures"
    snap = call("gap.save", {"indicator_id": ind, "period": "T1-2026", "text": ""})
    assert snap["gap_comments"] == {}


def test_secondary_sources_and_new_types(call, tmp_path):
    node = _project(call, tmp_path)
    with pytest.raises(RuntimeError, match="unit_entry_only"):
        call("indicator.save", {"node_id": node, "indicator": {"name": "x", "unit": "median"}})
    ms = call(
        "indicator.save",
        {
            "node_id": node,
            "indicator": {"name": "Politique adoptée", "unit": "milestone", "source_type": "secondary", "target": 1},
        },
    )["saved"]
    sub = call("submission.open", {"period": "T2-2026", "channel": "secondary"})["created"]
    call("submission.save", {"id": sub, "values": [{"indicator_id": ms, "value": 1}], "source_ref": "Journal officiel"})
    res = call("submission.act", {"id": sub, "action": "validate"})
    assert res["submission"]["source_ref"] == "Journal officiel"
    row = call("tracking.table", {"period": "T2-2026", "today": "2026-07-15"})["rows"][0]
    assert row["status"] == "achieved"


# ----- reprise of 0.5 routine values -------------------------------------------------------


def test_routine_values_of_version_5_are_migrated(call, tmp_path):
    path = tmp_path / "old.sme"
    call("project.create", {"path": str(path), "name": "Old"})
    node = call("framework.add", {"title": "Produit"})["created"]
    ind = call(
        "indicator.save",
        {
            "node_id": node,
            "indicator": {
                "name": "Formés",
                "unit": "count",
                "source_type": "routine",
                "categories": ["Femmes", "Hommes"],
                "target": 100,
            },
        },
    )["saved"]
    call("project.close")
    conn = sqlite3.connect(path)
    rows = [
        {"period": "2025-T3", "end": "2025-09-30", "achieved": 20, "planned": 25, "by": {"Femmes": 12, "Hommes": 8}},
        {"period": "2025-T4", "end": "2025-12-31", "achieved": 30, "planned": 25, "by": {}},
        {"period": "Avant", "end": None, "achieved": 5, "planned": None, "by": {}},
    ]
    for i, r in enumerate(rows, start=1):
        conn.execute(
            "INSERT INTO routine_value(id, indicator_id, position, spec) VALUES (?, ?, ?, ?)",
            (f"r{i}", ind, i, json.dumps(r)),
        )
    conn.execute("PRAGMA user_version = 5")
    conn.commit()
    conn.close()

    snap = call("project.open", {"path": str(path)})
    assert [p["code"] for p in snap["periods"]] == ["2025-T3", "2025-T4"]
    assert snap["periods"][0]["start"] == "2025-07-01" and snap["periods"][1]["start"] == "2025-10-01"
    assert len(snap["submissions"]) == 2 and {s["status"] for s in snap["submissions"]} == {"validated"}
    dis = snap["disaggregations"][0]
    assert dis["key"] == "repartition_1" and [c["fr"] for c in dis["categories"]] == ["Femmes", "Hommes"]
    assert snap["indicators"][0]["breakdowns"] == ["repartition_1"]
    assert sorted(t["value"] for t in snap["targets"][ind]) == [25, 25]
    an = call("analysis.indicator", {"id": ind})
    assert an["current"] == 50 and an["by_total"] == {"Femmes": 12, "Hommes": 8}
    # The row without a date could not be placed: it is kept and listed.
    conn = sqlite3.connect(path)
    assert conn.execute("SELECT COUNT(*) FROM routine_value").fetchone()[0] == 3
    unplaced = json.loads(conn.execute("SELECT value FROM meta WHERE key = 'routine_unplaced'").fetchone()[0])
    assert unplaced == [{"indicator_id": ind, "period": "Avant"}]
    conn.close()


# ----- agenda, tasks, today ------------------------------------------------------------------


def test_generated_tasks_close_themselves(call, tmp_path):
    node = _project(call, tmp_path, reporting_by="partner")
    a = call("partner.save", {"partner": {"name": "ONG A", "acronym": "ONGA"}})["created"]
    ind = call(
        "indicator.save",
        {
            "node_id": node,
            "indicator": {"name": "Formés", "unit": "count", "source_type": "routine", "target": 400},
        },
    )["saved"]
    call("target.set", {"indicator_id": ind, "period": "T1-2026", "value": 100})
    day = "2026-04-12"  # T1 data were due on 10 April
    today = call("today.project", {"today": day})
    kinds = sorted(t["kind"] for t in today["tasks"])
    assert kinds == ["chase", "report", "sheet"]
    chase = next(t for t in today["tasks"] if t["kind"] == "chase")
    assert chase["unit_name"] == "ONGA" and chase["priority"] == "high" and chase["due"] == "2026-04-10"
    sheet = next(t for t in today["tasks"] if t["kind"] == "sheet")
    assert sheet["missing"] == ["definition", "source"]
    assert today["deadlines"][0]["kind"] == "report_due" and today["deadlines"][0]["days"] == 18

    # Received: the chase becomes a verification.
    sub = call("submission.open", {"period": "T1-2026", "partner_id": a})["created"]
    call("submission.save", {"id": sub, "values": [{"indicator_id": ind, "value": 60}]})
    call("submission.act", {"id": sub, "action": "submit"})
    kinds = sorted(t["kind"] for t in call("today.project", {"today": day})["tasks"])
    assert kinds == ["report", "sheet", "verify"]
    # Validated and late against its target: a gap to explain.
    call("submission.act", {"id": sub, "action": "validate"})
    today = call("today.project", {"today": day})
    gap = next(t for t in today["tasks"] if t["kind"] == "gap")
    assert gap["indicator"] == "Formés" and today["late"][0]["indicator"] == "Formés"
    call("gap.save", {"indicator_id": ind, "period": "T1-2026", "text": "Formateurs arrivés en mars"})
    # Report sent: no task left for T1 but the sheet.
    snap = call("period.mark_reported", {"id": next(p["id"] for p in call("project.get")["periods"])})
    assert snap["periods"][0]["reported_at"]
    kinds = sorted(t["kind"] for t in call("today.project", {"today": day})["tasks"])
    assert kinds == ["sheet"]


def test_manual_tasks_events_and_calendar_files(call, tmp_path):
    _project(call, tmp_path)
    snap = call(
        "task.save",
        {"task": {"title": "Relancer les partenaires", "due": "2026-01-31", "recurrence": "monthly"}},
    )
    task = snap["tasks"][0]
    snap = call("task.save", {"id": task["id"], "task": {**task, "status": "done"}})
    assert [t["due"] for t in snap["tasks"]] == ["2026-01-31", "2026-02-28"]
    assert snap["tasks"][0]["done_at"] and snap["tasks"][1]["status"] == "todo"
    with pytest.raises(RuntimeError, match="dates_order"):
        call("event.save", {"event": {"title": "x", "start": "2026-02-10", "end": "2026-02-09"}})
    call(
        "event.save",
        {
            "event": {
                "title": "Mission à Kara, suivi des sites",
                "kind": "mission",
                "start": "2026-02-10",
                "end": "2026-02-12",
                "place": "Kara",
            }
        },
    )
    call("event.save", {"event": {"title": "Revue trimestrielle", "kind": "meeting", "start": "2026-03-30T09:00"}})
    ag = call("agenda.list", {"start": "2026-02-01", "end": "2026-04-30"})
    kinds = [e["kind"] for e in ag["events"]]
    assert kinds == ["mission", "meeting", "data_due", "report_due"]
    # The manual task, and the T1 report still to send (today is after T1).
    assert [(t["due"], t["auto"]) for t in ag["tasks"]] == [("2026-02-28", False), ("2026-04-30", True)]

    ics = tmp_path / "agenda.ics"
    out = call("agenda.export_ics", {"path": str(ics), "start": "2026-02-01", "end": "2026-04-30"})
    text = ics.read_bytes().decode("utf-8")
    assert out["events"] == 4 and "DTSTART;VALUE=DATE:20260210" in text and "DTEND;VALUE=DATE:20260213" in text
    assert "SUMMARY:P: Données de T1 2026 attendues" in text and "DTSTART:20260330T090000" in text
    assert [line for line in text.split("\r\n") if len(line.encode()) > 75] == []
    # Read back into another project: the same events, typed by hand.
    call("project.create", {"path": str(tmp_path / "q.sme"), "name": "Q"})
    snap = call("agenda.import_ics", {"path": str(ics)})
    assert snap["imported"] == 4
    mission = next(e for e in snap["events"] if "Mission" in e["title"])
    assert mission["start"] == "2026-02-10" and mission["end"] == "2026-02-12" and mission["place"] == "Kara"
    assert any(e["start"] == "2026-03-30T09:00" for e in snap["events"])


# ----- Excel templates ----------------------------------------------------------------------------


def test_excel_template_round_trip(call, tmp_path):
    from openpyxl import load_workbook

    node = _project(call, tmp_path, reporting_by="partner")
    a = call("partner.save", {"partner": {"name": "ONG Lumière", "acronym": "OL"}})["created"]
    call("partner.save", {"partner": {"name": "ONG Espoir"}})
    trained = call(
        "indicator.save",
        {
            "node_id": node,
            "indicator": {"name": "Formés", "unit": "count", "source_type": "routine", "breakdowns": ["sex"]},
        },
    )["saved"]
    cover = call(
        "indicator.save",
        {"node_id": node, "indicator": {"name": "Couverture", "unit": "percent", "source_type": "routine"}},
    )["saved"]
    done = call(
        "indicator.save",
        {"node_id": node, "indicator": {"name": "Comité créé", "unit": "milestone", "source_type": "routine"}},
    )["saved"]
    folder = tmp_path / "out"
    folder.mkdir()
    out = call("canevas.write", {"path": str(folder), "period": "T1-2026"})
    assert sorted(out["files"]) == ["T1-2026-OL.xlsx", "T1-2026-ONG-Espoir.xlsx"]
    file = folder / "T1-2026-OL.xlsx"
    wb = load_workbook(file)
    ws = wb["Saisie"]
    assert ws.protection.sheet and wb["_sme"].sheet_state == "hidden"
    # Lines: Formés by sex (women, men, not specified), coverage, milestone.
    assert [ws.cell(row=9 + i, column=3).value for i in range(5)] == [
        "Femme",
        "Homme",
        "Non précisé",
        "Total",
        "Total",
    ]
    ws.cell(row=9, column=4).value = 12
    ws.cell(row=10, column=4).value = 8
    ws.cell(row=12, column=5).value = 45
    ws.cell(row=12, column=6).value = 60
    ws.cell(row=13, column=4).value = "Fait"
    ws.cell(row=15, column=2).value = "Registres des centres, mars 2026"
    wb.save(file)

    res = call("canevas.receive", {"path": str(file)})
    assert res["applied"] and res["saved"] == 4
    sub = next(s for s in res["submissions"] if s["partner_id"] == a)
    assert sub["status"] == "submitted" and sub["channel"] == "excel"
    assert sub["source_ref"] == "Registres des centres, mars 2026"
    detail = call("submission.get", {"id": sub["id"]})
    assert detail["cells"][trained]["sex=f"][0] == 12 and detail["cells"][cover][""][0] == pytest.approx(0.75)
    assert detail["cells"][done][""][0] == 1

    # Sent back again once validated: a revision, shown, not applied.
    call("submission.act", {"id": sub["id"], "action": "validate"})
    wb = load_workbook(file)
    wb["Saisie"].cell(row=9, column=4).value = 15
    wb.save(file)
    res = call("canevas.receive", {"path": str(file)})
    assert res["revision"] and not res["applied"]
    assert res["changes"] == [
        {"indicator_id": trained, "cats": {"sex": "f"}, "before": [12, None, None], "after": [15, None, None]}
    ]
    with pytest.raises(RuntimeError, match="comment_required"):
        call("canevas.receive", {"path": str(file), "apply": True})
    res = call("canevas.receive", {"path": str(file), "apply": True, "reason": "Registre corrigé"})
    assert res["revised"] and res["applied"]
    assert call("submission.get", {"id": sub["id"]})["cells"][trained]["sex=f"][0] == 15
    call("submission.act", {"id": sub["id"], "action": "validate"})

    # A line moved: refused.
    wb = load_workbook(file)
    ws = wb["Saisie"]
    ws.cell(row=9, column=2).value, ws.cell(row=12, column=2).value = "Couverture", "Formés"
    wb.save(file)
    with pytest.raises(RuntimeError, match="canevas_changed"):
        call("canevas.receive", {"path": str(file)})
    # A new indicator since: the template is outdated.
    call(
        "indicator.save", {"node_id": node, "indicator": {"name": "Nouveau", "unit": "count", "source_type": "routine"}}
    )
    with pytest.raises(RuntimeError, match="canevas_outdated"):
        call("canevas.receive", {"path": str(folder / "T1-2026-ONG-Espoir.xlsx")})
    # Another project's template.
    call("project.create", {"path": str(tmp_path / "other.sme"), "name": "Autre"})
    with pytest.raises(RuntimeError, match="canevas_other_project"):
        call("canevas.receive", {"path": str(file)})


def test_workspace_today_and_personal_items(call, tmp_path, monkeypatch):
    monkeypatch.setenv("SME_TRUST_DIR", str(tmp_path / "home"))
    node = _project(call, tmp_path)
    call(
        "indicator.save", {"node_id": node, "indicator": {"name": "Formés", "unit": "count", "source_type": "routine"}}
    )
    path = call("project.get")["project"]["path"]
    out = call("workspace.summaries", {"paths": [path], "today": "2026-04-12"})["projects"][0]
    kinds = sorted(t["kind"] for t in out["today"]["tasks"])
    assert kinds == ["chase", "report", "sheet"]
    data = call("personal.task_save", {"task": {"title": "Préparer la mission", "due": "2026-04-20"}})
    assert data["tasks"][0]["title"] == "Préparer la mission"
    tid = data["tasks"][0]["id"]
    data = call("personal.task_save", {"id": tid, "task": {**data["tasks"][0], "status": "done"}})
    assert data["tasks"][0]["status"] == "done"
    data = call("personal.event_save", {"event": {"title": "Congé", "kind": "absence", "start": "2026-05-01"}})
    assert call("personal.get")["events"][0]["title"] == "Congé"
    data = call("personal.task_save", {"id": tid, "delete": True})
    assert data["tasks"] == []


def test_workspace_agenda(call, tmp_path, monkeypatch):
    monkeypatch.setenv("SME_TRUST_DIR", str(tmp_path / "home"))
    _project(call, tmp_path)
    call("event.save", {"event": {"title": "Atelier", "kind": "workshop", "start": "2026-02-03"}})
    path = call("project.get")["project"]["path"]
    call("personal.event_save", {"event": {"title": "Congé", "kind": "absence", "start": "2026-02-05"}})
    out = call("workspace.agenda", {"paths": [path], "start": "2026-02-01", "end": "2026-02-28"})
    assert [(e["title"], e.get("project"), bool(e.get("personal"))) for e in out["events"]] == [
        ("Atelier", "P", False),
        ("Congé", None, True),
    ]


# ----- crosstab, quality reviews, expected indicators, changes ----------------------------------


def test_crosstab_by_place_partner_period_and_category(call, tmp_path):
    node = _project(call, tmp_path, reporting_by="partner_place")
    kara = call("place.save", {"place": {"name": "Kara"}})["created"]
    lome = call("place.save", {"place": {"name": "Lomé"}})["created"]
    a = call("partner.save", {"partner": {"name": "ONG A", "acronym": "A", "place_ids": [kara, lome]}})["created"]
    ind = call(
        "indicator.save",
        {
            "node_id": node,
            "indicator": {"name": "Formés", "unit": "count", "source_type": "routine", "breakdowns": ["sex"]},
        },
    )["saved"]
    for period, place, f, m_ in (("T1-2026", kara, 10, 5), ("T1-2026", lome, 3, 2), ("T2-2026", kara, 4, 6)):
        sid = call("submission.open", {"period": period, "place_id": place, "partner_id": a})["created"]
        call(
            "submission.save",
            {
                "id": sid,
                "values": [
                    {"indicator_id": ind, "cats": {"sex": "f"}, "value": f},
                    {"indicator_id": ind, "cats": {"sex": "m"}, "value": m_},
                ],
            },
        )
        call("submission.act", {"id": sid, "action": "validate"})
    out = call("tracking.crosstab", {"indicator_id": ind, "rows": "place", "cols": "sex", "period": "T2-2026"})
    kara_row = next(r for r in out["rows"] if r["label"] == "Kara")
    assert kara_row["values"][:2] == [14, 11] and kara_row["total"] == 25
    assert out["col_totals"][:2] == [17, 13] and out["total"] == 30
    by_period = call(
        "tracking.crosstab", {"indicator_id": ind, "rows": "period", "cols": "partner", "period": "T2-2026"}
    )
    assert [r["values"][0] for r in by_period["rows"]] == [20, 10]
    assert by_period["rows"][0]["total"] == 20  # one partner column plus the empty one
    with pytest.raises(RuntimeError, match="invalid_params"):
        call("tracking.crosstab", {"indicator_id": ind, "rows": "age"})


def test_annual_indicator_is_expected_once_a_year(call, tmp_path):
    node = _project(call, tmp_path)
    call(
        "indicator.save",
        {
            "node_id": node,
            "indicator": {
                "name": "Enquête de satisfaction",
                "unit": "percent",
                "source_type": "routine",
                "frequency": "annual",
            },
        },
    )
    q = call(
        "indicator.save",
        {
            "node_id": node,
            "indicator": {"name": "Formés", "unit": "count", "source_type": "routine", "frequency": "quarterly"},
        },
    )["saved"]
    sub = call("submission.open", {"period": "T1-2026"})["created"]
    res = call("submission.save", {"id": sub, "values": [{"indicator_id": q, "value": 3}]})
    assert [a["check"] for a in res["alerts"]] == []  # the annual one is not due in Q1
    sub = call("submission.open", {"period": "T4-2026"})["created"]
    res = call("submission.save", {"id": sub, "values": [{"indicator_id": q, "value": 3}]})
    assert [a["check"] for a in res["alerts"]] == ["missing"]


def test_quality_review_reminder_and_changes_since_last_opening(call, tmp_path):
    node = _project(call, tmp_path)
    ind = call(
        "indicator.save",
        {
            "node_id": node,
            "indicator": {
                "name": "Formés",
                "unit": "count",
                "source_type": "routine",
                "definition": "d",
                "source": "s",
                "target": 10,
            },
        },
    )["saved"]
    snap = call(
        "quality.save",
        {
            "indicator_id": ind,
            "review": {
                "date": "2025-01-15",
                "scores": {"validity": "met", "timeliness": "partly", "x": "met"},
                "conclusions": "Registres incomplets à Kara",
            },
        },
    )
    review = snap["quality_reviews"][ind][0]
    assert review["scores"] == {
        "validity": "met",
        "reliability": "",
        "timeliness": "partly",
        "precision": "",
        "integrity": "",
    }
    today = call("today.project", {"today": "2026-03-01"})
    dqa = next(t for t in today["tasks"] if t["kind"] == "dqa")
    assert dqa["due"] == "2026-01-15" and dqa["priority"] == "high"
    # Reopened: what was received since the last opening is listed.
    sub = call("submission.open", {"period": "T1-2026"})["created"]
    call("submission.save", {"id": sub, "values": [{"indicator_id": ind, "value": 3}]})
    call("submission.act", {"id": sub, "action": "submit"})
    path = call("project.get")["project"]["path"]
    call("project.close")
    call("project.open", {"path": path})
    assert call("today.project", {})["changes"] == []  # nothing new since this opening
    call("project.close")
    import sqlite3 as _s

    conn = _s.connect(path)
    conn.execute("UPDATE meta SET value = '2026-01-01T00:00:00+00:00' WHERE key = 'opened_at'")
    conn.commit()
    conn.close()
    call("project.open", {"path": path})
    changes = call("today.project", {})["changes"]
    assert [c["action"] for c in changes] == ["submit"] and changes[0]["label"] == "T1 2026"


# ----- unique people (section 6.4) ----------------------------------------------------------------


def test_unique_people_are_counted_once(call, tmp_path):
    node = _project(call, tmp_path, reporting_by="partner")
    a = call("partner.save", {"partner": {"name": "A"}})["created"]
    b = call("partner.save", {"partner": {"name": "B"}})["created"]
    ind = call(
        "indicator.save",
        {
            "node_id": node,
            "indicator": {
                "name": "Personnes formées",
                "unit": "count",
                "source_type": "routine",
                "people": "unique",
                "target": 10,
            },
        },
    )["saved"]
    contacts = call(
        "indicator.save",
        {
            "node_id": node,
            "indicator": {
                "name": "Séances",
                "unit": "count",
                "source_type": "routine",
                "people": "unique",
                "target": 10,
            },
        },
    )["saved"]

    def send(period, partner, ids):
        sid = call("submission.open", {"period": period, "partner_id": partner})["created"]
        res = call("people.save", {"id": sid, "indicator_id": ind, "ids": ids})
        call("submission.save", {"id": sid, "values": [{"indicator_id": contacts, "value": 4}]})
        call("submission.act", {"id": sid, "action": "validate"})
        return res

    res = send("T1-2026", a, ["TG-001", "TG-002", " tg-001 ", "TG-003"])
    assert res["people"] == 3 and res["cells"][ind][""][0] == 3  # the same card typed twice
    send("T1-2026", b, ["TG-003", "TG-004"])  # TG-003 also trained by partner B
    send("T2-2026", a, ["TG-001", "TG-005"])  # TG-001 trained again
    rows = {r["indicator_id"]: r for r in call("tracking.table", {"period": "T2-2026", "today": "2026-07-15"})["rows"]}
    row = rows[ind]
    assert [s["value"] for s in row["series"][:2]] == [4, 2]
    assert [s["to_date"] for s in row["series"][:2]] == [4, 5]  # not 4 + 2
    assert row["to_date"] == 5 and row["duplicates_possible"] is False
    # Counted without identifiers: duplicates possible, said so.
    assert rows[contacts]["duplicates_possible"] is True and rows[contacts]["to_date"] == 12
    # The identifiers never reach the project file.
    raw = open(call("project.get")["project"]["path"], "rb").read()
    assert b"TG-001" not in raw and b"tg-001" not in raw
    with pytest.raises(RuntimeError, match="people_not_unique"):
        other = call(
            "indicator.save", {"node_id": node, "indicator": {"name": "x", "unit": "count", "source_type": "routine"}}
        )["saved"]
        sid = call("submission.open", {"period": "T3-2026", "partner_id": a})["created"]
        call("people.save", {"id": sid, "indicator_id": other, "ids": ["1"]})
