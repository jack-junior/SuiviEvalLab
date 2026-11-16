# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 GAYI Komi Selassi and SANOUSSI Moudjibou

"""Project profile, calendar, places, partners, disaggregations and targets."""

from __future__ import annotations

import io
import json
import sqlite3

import pytest

from sme_engine import frameworks, schedule
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
            raise RuntimeError(resp["error"]["data"]["key"] + ": " + resp["error"]["message"])
        return resp["result"]

    yield _call
    bridge.stop()


PROFILE = {
    "code": "PSE-01",
    "start": "2026-02-15",
    "end": "2027-06-30",
    "frequency": "quarterly",
    "donors": [{"name": "Union européenne", "agreement": "CSO-2026/01", "frequency": "semiannual"}],
    "countries": ["Togo"],
    "currency": "xof",
    "budget": "1500000",
}


# ----- calendar ------------------------------------------------------------------


def test_periods_follow_the_fiscal_year():
    p = schedule.validate_profile({**PROFILE, "fiscal_start_month": 7})
    periods = schedule.generate(p)
    assert periods[0] == {
        "code": "T3-2025-26",
        "label_fr": "T3 2025-26",
        "label_en": "Q3 2025-26",
        "start": "2026-02-15",
        "end": "2026-03-31",
        "data_due": "2026-04-10",
        "report_due": "2026-04-30",
        "state": "open",
    }
    assert periods[-1]["code"] == "T4-2026-27" and periods[-1]["end"] == "2027-06-30"
    assert len(periods) == 6


def test_monthly_semiannual_and_annual_calendars():
    base = {"start": "2026-01-01", "end": "2026-12-31"}
    assert len(schedule.generate(schedule.validate_profile({**base, "frequency": "monthly"}))) == 12
    semi = schedule.generate(schedule.validate_profile({**base, "frequency": "semiannual"}))
    assert [x["label_en"] for x in semi] == ["H1 2026", "H2 2026"]
    year = schedule.generate(schedule.validate_profile({**base, "frequency": "annual", "fiscal_start_month": 4}))
    assert [x["code"] for x in year] == ["A-2025-26", "A-2026-27"]
    assert year[0]["start"] == "2026-01-01" and year[0]["end"] == "2026-03-31"


def test_profile_is_checked():
    p = schedule.validate_profile(PROFILE)
    assert p["currency"] == "XOF" and p["budget"] == 1500000.0 and p["donors"][0]["frequency"] == "semiannual"
    with pytest.raises(Exception, match="ends before"):
        schedule.validate_profile({"start": "2026-05-01", "end": "2026-01-01"})
    with pytest.raises(Exception, match="frequency"):
        schedule.validate_profile({"frequency": "weekly"})
    with pytest.raises(Exception, match="start and end"):
        schedule.generate(schedule.default_profile())


def test_project_created_with_profile_calendar_and_disaggregations(call, tmp_path):
    snap = call(
        "project.create",
        {
            "path": str(tmp_path / "p.sme"),
            "name": "P",
            "model": {"id": "ifrc"},
            "profile": PROFILE,
            "disaggregations": ["sex", "age"],
        },
    )
    assert snap["profile"]["code"] == "PSE-01"
    assert [x["code"] for x in snap["periods"]][:2] == ["T1-2026", "T2-2026"]
    assert snap["periods"][0]["start"] == "2026-02-15"
    assert [d["key"] for d in snap["disaggregations"]] == ["sex", "age"]
    assert snap["project"]["framework_model"]["levels"][0]["fr"] == "Objectif global"


def test_hand_made_periods_and_locking(call, tmp_path):
    call("project.create", {"path": str(tmp_path / "p.sme"), "name": "P"})
    call("period.save", {"period": {"code": "P2", "start": "2026-07-01", "end": "2026-12-31"}})
    snap = call("period.save", {"period": {"code": "P1", "start": "2026-01-01", "end": "2026-06-30"}})
    assert [x["code"] for x in snap["periods"]] == ["P1", "P2"]  # kept in date order
    with pytest.raises(RuntimeError, match="periods_overlap"):
        call("period.save", {"period": {"code": "P3", "start": "2026-12-01", "end": "2027-03-31"}})
    p1 = snap["periods"][0]["id"]
    snap = call("period.set_state", {"id": p1, "state": "locked"})
    assert snap["periods"][0]["state"] == "locked"
    with pytest.raises(RuntimeError, match="period_locked"):
        call("period.delete", {"id": p1})


# ----- targets -------------------------------------------------------------------


def _indicator(call, **extra):
    node = call("framework.add", {"title": "Objectif"})["created"]
    spec = {"name": "Enfants vaccinés", "unit": "count", **extra}
    snap = call("indicator.save", {"node_id": node, "indicator": spec})
    return snap["indicators"][0]["id"]


def test_percentage_targets_and_older_end_targets(call, tmp_path):
    call("project.create", {"path": str(tmp_path / "p.sme"), "name": "P", "profile": PROFILE})
    ind = _indicator(call, unit="percent", target=0.8, breakdowns=["sex", "age"])
    with pytest.raises(RuntimeError, match="invalid_share"):
        call("target.set", {"indicator_id": ind, "period": "T1-2026", "value": 80})
    # The end target typed in 0.5 counts as the first value: changing it needs a reason.
    with pytest.raises(RuntimeError, match="target_reason_required"):
        call("target.set", {"indicator_id": ind, "period": "total", "value": 0.7})
    snap = call("target.set", {"indicator_id": ind, "period": "total", "value": 0.7, "reason": "Revue à mi-parcours"})
    assert snap["indicators"][0]["target"] == 0.7 and snap["indicators"][0]["breakdowns"] == ["sex", "age"]
    assert snap["targets"][ind][0]["history"][0]["value"] == 0.8
    snap = call("target.clear", {"indicator_id": ind, "period": "total"})
    assert snap["indicators"][0]["target"] is None


def test_targets_keep_their_history(call, tmp_path):
    call("project.create", {"path": str(tmp_path / "p.sme"), "name": "P", "profile": PROFILE})
    ind = _indicator(call)
    snap = call("target.set", {"indicator_id": ind, "period": "T1-2026", "value": "1 200"})
    assert snap["targets"][ind][0]["value"] == 1200
    with pytest.raises(RuntimeError, match="target_reason_required"):
        call("target.set", {"indicator_id": ind, "period": "T1-2026", "value": 1000})
    snap = call("target.set", {"indicator_id": ind, "period": "T1-2026", "value": 1000, "reason": "Rupture de vaccins"})
    t = snap["targets"][ind][0]
    assert t["value"] == 1000 and t["history"][0]["value"] == 1200 and t["history"][0]["reason"] == "Rupture de vaccins"
    snap = call("target.set", {"indicator_id": ind, "period": "total", "value": 5000})
    assert snap["indicators"][0]["target"] == 5000
    snap = call("target.set", {"indicator_id": ind, "period": "total", "value": 4500, "reason": "Budget réduit"})
    assert snap["indicators"][0]["target"] == 4500
    with pytest.raises(RuntimeError, match="period_not_found"):
        call("target.set", {"indicator_id": ind, "period": "T9-2030", "value": 1})
    # A period holding targets cannot disappear when the calendar is rebuilt.
    call("profile.set", {"profile": {**PROFILE, "start": "2026-04-01"}})
    with pytest.raises(RuntimeError, match="periods_in_use"):
        call("period.generate")
    # Deleting the indicator deletes its targets.
    snap = call("indicator.delete", {"id": ind})
    assert snap["targets"] == {}


def test_regenerating_keeps_locked_state(call, tmp_path):
    snap = call("project.create", {"path": str(tmp_path / "p.sme"), "name": "P", "profile": PROFILE})
    call("period.set_state", {"id": snap["periods"][1]["id"], "state": "locked"})
    snap = call("profile.set", {"profile": {**PROFILE, "end": "2027-12-31"}, "generate_periods": True})
    assert snap["periods"][1]["state"] == "locked" and snap["periods"][-1]["code"] == "T4-2027"


# ----- places, partners, disaggregations ---------------------------------------------


def test_places_tree_and_import(call, tmp_path):
    call("project.create", {"path": str(tmp_path / "p.sme"), "name": "P"})
    kara = call("place.save", {"place": {"name": "Kara", "code": "TG-K"}})["created"]
    snap = call("place.save", {"place": {"name": "Kozah", "parent_id": kara}})
    assert snap["places"][1]["level"] == 1
    with pytest.raises(RuntimeError, match="place_duplicate"):
        call("place.save", {"place": {"name": "kozah", "parent_id": kara}})
    with pytest.raises(RuntimeError, match="place_code_duplicate"):
        call("place.save", {"place": {"name": "Savanes", "code": "TG-K"}})
    snap = call(
        "place.import",
        {"rows": [["Kara", "Kozah", "Lama"], ["Kara", "Kozah", "Pya"], ["Savanes", "Tône"], ["", "x"]]},
    )
    assert snap["added"] == 4  # Lama, Pya, Savanes, Tône: Kara and Kozah already exist
    names = {x["name"]: x for x in snap["places"]}
    assert names["Pya"]["parent_id"] == names["Kozah"]["id"] and names["Pya"]["level"] == 2
    with pytest.raises(RuntimeError, match="place_has_children"):
        call("place.delete", {"id": kara})
    snap = call("partner.save", {"partner": {"name": "ONG Lumière", "role": "implementing", "place_ids": [kara, "x"]}})
    assert snap["partners"][0]["place_ids"] == [kara]
    snap = call("place.delete", {"id": names["Tône"]["id"]})
    assert "Tône" not in {x["name"] for x in snap["places"]}


def test_disaggregations(call, tmp_path):
    call("project.create", {"path": str(tmp_path / "p.sme"), "name": "P"})
    presets = call("disaggregation.presets")
    assert {"sex", "age", "age_health", "disability", "status", "area"} <= {x["key"] for x in presets["presets"]}
    call("disaggregation.save", {"disaggregation": {"preset": "disability"}})
    with pytest.raises(RuntimeError, match="disaggregation_duplicate"):
        call("disaggregation.save", {"disaggregation": {"preset": "disability"}})
    snap = call(
        "disaggregation.save",
        {"disaggregation": {"name_fr": "Type d'école", "categories": [{"fr": "Publique"}, {"fr": "Privée"}]}},
    )
    d = snap["disaggregations"][1]
    assert d["key"] == "type_d_ecole" and [c["code"] for c in d["categories"]] == ["publique", "privee"]
    with pytest.raises(RuntimeError, match="categories_too_few"):
        call("disaggregation.save", {"disaggregation": {"name_fr": "X", "categories": [{"fr": "Seule"}]}})


# ----- framework models and migration ----------------------------------------------


def test_models_of_version_1():
    assert len(frameworks.validate({"id": "usaid"})["levels"]) == 5
    wb = frameworks.validate({"id": "worldbank"})
    assert [lv["indicators"] for lv in wb["levels"]] == [True, False, True, False]
    custom = frameworks.validate({"id": "custom", "levels": [{"fr": str(i)} for i in range(5)]})
    assert len(custom["levels"]) == 5
    with pytest.raises(Exception, match="2 to 5"):
        frameworks.validate({"id": "custom", "levels": [{"fr": str(i)} for i in range(6)]})


def test_migration_from_version_4(call, tmp_path):
    """A 0.5 project: four-level CHECK, two-level World Bank model, no calendar tables."""
    path = tmp_path / "old.sme"
    call("project.create", {"path": str(path), "name": "Old", "model": {"id": "standard"}})
    top = call("framework.add", {"title": "PDO"})["created"]
    ir = call("framework.add", {"parent_id": top, "title": "IR 1"})["created"]
    call("indicator.save", {"node_id": ir, "indicator": {"name": "Routes", "unit": "count"}})
    call("project.close")
    conn = sqlite3.connect(path)
    conn.execute("PRAGMA foreign_keys = OFF")
    conn.executescript(
        """
        CREATE TABLE fn4 (id TEXT PRIMARY KEY, parent_id TEXT REFERENCES framework_node(id) ON DELETE CASCADE,
          level TEXT NOT NULL CHECK (level IN ('impact', 'outcome', 'output', 'activity')), title TEXT NOT NULL,
          description TEXT NOT NULL DEFAULT '', assumptions TEXT NOT NULL DEFAULT '', position INTEGER NOT NULL);
        INSERT INTO fn4 SELECT * FROM framework_node;
        DROP TABLE framework_node;
        ALTER TABLE fn4 RENAME TO framework_node;
        DROP TABLE period; DROP TABLE place; DROP TABLE partner; DROP TABLE disaggregation; DROP TABLE target;
        UPDATE meta SET value = '{"id": "worldbank"}' WHERE key = 'framework_model';
        PRAGMA user_version = 4;
        """
    )
    conn.commit()
    conn.close()
    snap = call("project.open", {"path": str(path)})
    model = snap["project"]["framework_model"]
    assert model["id"] == "custom" and [lv["fr"] for lv in model["levels"]] == [
        "Objectif de développement du projet",
        "Résultat intermédiaire",
    ]
    assert len(snap["indicators"]) == 1 and len(snap["framework"]) == 2
    assert snap["periods"] == [] and snap["targets"] == {}
    conn = sqlite3.connect(path)
    assert conn.execute("PRAGMA user_version").fetchone()[0] == 5
    assert conn.execute("PRAGMA foreign_key_check").fetchall() == []
    sql = conn.execute("SELECT sql FROM sqlite_master WHERE name = 'indicator'").fetchone()[0]
    assert "REFERENCES framework_node(id)" in sql
    conn.close()
    # The fifth level can now be stored.
    call("framework.set_model", {"model": {"id": "usaid"}})
    a = call("framework.add", {"parent_id": ir, "title": "Sub"})["created"]
    b = call("framework.add", {"parent_id": a, "title": "Act"})["created"]
    c = call("framework.add", {"parent_id": b, "title": "Act 2"})
    assert c["framework"][-1]["level"] == "detail"
