# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 GAYI Komi Selassi and SANOUSSI Moudjibou

"""Work plan and budget (M9), evaluations (M10), accountability and learning (M11)."""

from __future__ import annotations

import io
import json

import pytest

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


def _project(call, tmp_path):
    call(
        "project.create",
        {
            "path": str(tmp_path / "p.sme"),
            "name": "P",
            "profile": {"start": "2026-01-01", "end": "2026-12-31", "frequency": "quarterly", "currency": "EUR"},
        },
    )
    return call("framework.add", {"title": "Effet"})["created"]


def test_work_plan_progress_and_lateness(call, tmp_path):
    node = _project(call, tmp_path)
    a = call(
        "activity.save",
        {"activity": {"title": "Former les agents", "node_id": node, "start": "2026-01-01", "end": "2026-03-31"}},
    )["created"]
    sub = call(
        "activity.save",
        {
            "activity": {
                "title": "Session 1",
                "parent_id": a,
                "start": "2026-01-01",
                "end": "2026-01-31",
                "progress": 50,
            }
        },
    )["created"]
    # A sub-activity cannot have its own sub-activities, nor can an activity be its own parent.
    with pytest.raises(RuntimeError, match="activity_too_deep"):
        call("activity.save", {"activity": {"title": "x", "parent_id": sub}})
    with pytest.raises(RuntimeError, match="dates_order"):
        call("activity.save", {"activity": {"title": "x", "start": "2026-02-01", "end": "2026-01-01"}})
    call(
        "activity.save",
        {
            "activity": {
                "title": "Session 2",
                "parent_id": a,
                "start": "2026-02-01",
                "end": "2026-03-31",
                "status": "done",
            }
        },
    )
    snap = call("project.get", {"today": "2026-02-15"})
    acts = {x["title"]: x for x in snap["activities"]}
    assert acts["Session 2"]["progress"] == 100  # done means complete
    assert acts["Session 1"]["late"] == "late_end"
    # The parent counts through its sub-activities: (31 * 0.5 + 59 * 1) / 90 days.
    wp = call("project.get", {})["workplan"]
    assert wp["physical"] == pytest.approx((31 * 0.5 + 59) / 90)
    # Late activities reach the project's today and its tasks.
    today = call("today.project", {"today": "2026-02-15"})
    assert [x["title"] for x in today["late_activities"]] == ["Session 1"]
    assert "activity_late_end" in {t["kind"] for t in today["tasks"]}
    # Deleting the parent removes its sub-activities.
    call("activity.delete", {"id": a})
    assert call("project.get", {})["activities"] == []


def test_me_activities_come_from_the_plan_once(call, tmp_path):
    node = _project(call, tmp_path)
    call(
        "indicator.save",
        {"node_id": node, "indicator": {"name": "Vaccinés", "unit": "count", "source_type": "routine"}},
    )
    first = call("activity.generate_me", {"lang": "fr"})
    # A collection and a review per quarter, and one data quality review for the year.
    assert first["added"] == 9
    assert call("activity.generate_me", {"lang": "fr"})["added"] == 0
    kinds = sorted({a["me_kind"] for a in first["activities"]})
    assert kinds == ["collection", "dqa", "review"]


def test_budget_execution_and_expense_import(call, tmp_path):
    _project(call, tmp_path)
    line = call(
        "budget_line.save",
        {"line": {"code": "1.1", "name": "Formations", "planned": {"T1-2026": 1000, "T2-2026": 1000, "T3-2026": 2000}}},
    )["created"]
    with pytest.raises(RuntimeError, match="period_not_found"):
        call("budget_line.save", {"line": {"name": "x", "planned": {"T9-2030": 5}}})
    call("expense.save", {"expense": {"line_id": line, "date": "2026-02-10", "amount": "600,50"}})
    export = tmp_path / "compta.csv"
    export.write_text(
        "Date;Compte;Libellé;Montant;Pièce\n"
        "15/03/2026;1.1;Salle;1 399,50;P-1\n"
        "15/03/2026;Formations;Repas;100;P-2\n"
        "16/03/2026;9.9;Inconnu;50;P-3\n"
        "pas une date;1.1;x;10;P-4\n",
        encoding="utf-8",
    )
    cols = {"date": "Date", "amount": "Montant", "line": "Compte", "label": "Libellé", "ref": "Pièce"}
    check = call("expense.import", {"path": str(export), "columns": cols})["import"]
    assert check["read"] == 2 and check["bad"] == 1 and check["unknown_lines"] == [{"line": "9.9", "rows": 1}]
    assert "expenses" not in call("expense.import", {"path": str(export), "columns": cols})  # a preview writes nothing
    done = call("expense.import", {"path": str(export), "columns": cols, "commit": True})
    # Read again, the same rows are recognised and not counted twice.
    again = call("expense.import", {"path": str(export), "columns": cols})["import"]
    assert again["read"] == 0 and again["duplicates"] == 2
    b = call("workplan.summary", {"today": "2026-05-01"})["budget"]
    assert b["planned"] == 4000 and b["spent"] == pytest.approx(2100.0)
    assert b["planned_to_date"] == 2000  # T1 and T2 have started
    assert b["financial"] == pytest.approx(2100 / 4000)
    assert len(done["expenses"]) == 3
    # Removing the line removes its expenses.
    assert call("budget_line.delete", {"id": line})["expenses"] == []


def test_feedback_circuit_deadlines_and_pseudonyms(call, tmp_path):
    _project(call, tmp_path)
    call("project.encrypt", {"password": "un mot de passe"})
    fb = call(
        "feedback.save",
        {
            "feedback": {
                "received": "2026-03-01",
                "channel": "hotline",
                "category": "service_complaint",
                "summary": "Distribution en retard",
                "person": "Aïcha Diallo 0612",
            }
        },
    )
    rec = fb["feedback"][0]
    assert rec["deadline"] == "2026-03-15" and rec["person"] != "Aïcha Diallo 0612" and len(rec["person"]) == 24
    assert rec["sensitive"] is False
    # The same person gives the same pseudonym.
    other = call(
        "feedback.save",
        {
            "feedback": {
                "received": "2026-03-02",
                "category": "sea",
                "summary": "Cas signalé",
                "person": "aïcha  diallo 0612",
            }
        },
    )["feedback"][1]
    assert other["person"] == rec["person"] and other["sensitive"] and other["sensitivity"] == "sea"
    today = call("today.project", {"today": "2026-03-20"})
    overdue = {f["category"]: f for f in today["overdue_feedback"]}
    assert set(overdue) == {"service_complaint", "sea"}
    assert overdue["sea"]["summary"] == ""  # a sensitive case is never shown in the lists
    feedback_tasks = [t for t in today["tasks"] if t["kind"] == "feedback"]
    assert {t["name"] for t in feedback_tasks} == {"Distribution en retard", ""}
    # Answering closes the task and keeps the history.
    call(
        "feedback.save",
        {"id": rec["id"], "feedback": {**rec, "person": "", "status": "answered", "response": "Livré le 18"}},
    )
    snap = call("project.get", {"today": "2026-03-20"})
    answered = next(f for f in snap["feedback"] if f["id"] == rec["id"])
    assert answered["person"] == rec["person"] and [h["status"] for h in answered["history"]] == [
        "received",
        "answered",
    ]
    stats = call("feedback.stats", {"today": "2026-03-20"})
    assert stats["total"] == 2 and stats["open"] == 1 and stats["sensitive"] == 1
    # Categories in use cannot be removed.
    with pytest.raises(RuntimeError, match="category_in_use"):
        call("feedback.categories", {"categories": [{"key": "other", "days": 10}]})


def test_recommendations_actions_become_tasks(call, tmp_path):
    _project(call, tmp_path)
    ev = call("evaluation.save", {"evaluation": {"title": "Évaluation à mi-parcours", "kind": "midterm"}})["created"]
    with pytest.raises(RuntimeError, match="field_required"):
        call("recommendation.save", {"recommendation": {"text": "x", "response": "rejected"}})
    r = call(
        "recommendation.save",
        {
            "recommendation": {
                "source": "evaluation",
                "evaluation_id": ev,
                "text": "Renforcer la supervision",
                "response": "accepted",
                "actions": [
                    {"text": "Recruter un superviseur", "due": "2026-04-30", "responsible": "RH"},
                    {"text": "Plan de supervision", "due": "2026-06-30"},
                ],
            }
        },
    )
    rec = r["recommendations"][0]
    assert rec["status"] == "in_progress"
    today = call("today.project", {"today": "2026-05-15"})
    assert today["overdue_recommendations"][0]["late"] == 1
    assert sorted(t["name"] for t in today["tasks"] if t["kind"] == "recommendation") == [
        "Plan de supervision",
        "Recruter un superviseur",
    ]
    actions = [{**a, "status": "done"} for a in rec["actions"]]
    snap = call("recommendation.save", {"id": rec["id"], "recommendation": {**rec, "actions": actions}})
    assert snap["recommendations"][0]["status"] == "done"
    assert all(a["done_at"] for a in snap["recommendations"][0]["actions"])
    # Deleting the evaluation keeps the recommendation.
    assert call("evaluation.delete", {"id": ev})["recommendations"][0]["evaluation_id"] is None


def test_risks_reviews_and_assumptions_of_the_logframe(call, tmp_path):
    node = _project(call, tmp_path)
    call(
        "framework.update",
        {"id": node, "title": "Effet", "assumptions": "Sécurité stable\n- Prix du carburant stable\n"},
    )
    first = call("risk.from_assumptions", {})
    assert first["added"] == 2 and call("risk.from_assumptions", {})["added"] == 0
    risk = call(
        "risk.save", {"risk": {"title": "Saison des pluies", "probability": 4, "impact": 4, "review_months": 3}}
    )["created"]
    snap = call("project.get", {"today": "2026-01-10"})
    r = next(x for x in snap["risks"] if x["id"] == risk)
    assert r["level"] == "high" and r["review_due"]
    call("risk.review", {"id": risk, "review": {"date": "2026-02-01", "probability": 2, "impact": 3, "note": "Digues"}})
    r = next(x for x in call("project.get", {})["risks"] if x["id"] == risk)
    assert r["review_due"] == "2026-05-01" and r["level"] == "medium" and r["probability"] == 2
    ag = call("agenda.list", {"start": "2026-04-01", "end": "2026-05-31"})
    assert any(e["kind"] == "risk_review" and e["name"] == "Saison des pluies" for e in ag["events"])


def test_evaluation_steps_meetings_and_qualitative_coding(call, tmp_path):
    _project(call, tmp_path)
    ev = call(
        "evaluation.save",
        {
            "evaluation": {
                "title": "Évaluation finale",
                "kind": "final",
                "start": "2026-09-01",
                "end": "2026-12-15",
                "steps": {"tor": {"date": "2026-06-01", "done": True}, "draft": {"date": "2026-11-15"}},
                "questions": [{"criterion": "effectiveness", "text": "Les résultats sont-ils atteints ?"}],
            }
        },
    )
    evaluation = ev["evaluations"][0]
    q = evaluation["questions"][0]["id"]
    ag = call("agenda.list", {"start": "2026-06-01", "end": "2026-11-30"})
    steps = {e["step"]: e["done"] for e in ag["events"] if e["kind"] == "evaluation_step"}
    assert steps == {"tor": True, "draft": False}
    assert "evaluation_step" in {t["kind"] for t in call("today.project", {"today": "2026-11-10"})["tasks"]}

    theme = call("qual_theme.save", {"theme": {"name": "Accès"}})["created"]
    text = "Le centre est loin. Les femmes viennent moins pendant les pluies."
    note = call(
        "qual_note.save",
        {
            "note": {
                "title": "Groupe de discussion, femmes",
                "kind": "fgd",
                "evaluation_id": evaluation["id"],
                "text": text,
                "excerpts": [{"start": 20, "end": len(text), "theme_ids": [theme, "inconnu"], "question_id": q}],
            }
        },
    )
    x = note["qual_notes"][0]["excerpts"][0]
    assert x["text"].startswith("Les femmes") and x["theme_ids"] == [theme]
    with pytest.raises(RuntimeError, match="excerpt_outside"):
        call("qual_note.save", {"note": {"title": "x", "text": "abc", "excerpts": [{"start": 1, "end": 9}]}})
    assert call("qual_theme.delete", {"id": theme})["qual_notes"][0]["excerpts"][0]["theme_ids"] == []

    call(
        "meeting.save",
        {
            "meeting": {
                "date": "2026-04-05",
                "title": "Revue trimestrielle",
                "decisions": [
                    {"text": "Relancer le partenaire B", "as_task": True, "due": "2026-04-15"},
                    {"text": "Info"},
                ],
            }
        },
    )
    tasks = call("today.project", {"today": "2026-04-10"})["tasks"]
    assert [t["name"] for t in tasks if t["kind"] == "decision"] == ["Relancer le partenaire B"]
    call("lesson.save", {"lesson": {"title": "Saison des pluies", "lesson": "Prévoir les distributions avant juin"}})
    call("learning_question.save", {"question": {"text": "Quels freins à la fréquentation ?"}})
    snap = call("project.get", {})
    assert len(snap["lessons"]) == 1 and snap["learning_questions"][0]["status"] == "open"


def test_periodic_reports_in_every_donor_format(call, tmp_path):
    from docx import Document

    from sme_engine import donor_formats

    snap = call("project.create", {"path": str(tmp_path / "ex.sme"), "name": "Exemple", "example": True})
    codes = [p["code"] for p in snap["periods"]]
    node = snap["framework"][-1]["id"]
    call(
        "activity.save",
        {
            "activity": {
                "title": "Former les relais",
                "node_id": node,
                "start": snap["periods"][0]["start"],
                "end": snap["periods"][1]["end"],
            }
        },
    )
    line = call("budget_line.save", {"line": {"name": "Formations", "planned": {codes[0]: 500}}})["created"]
    call("expense.save", {"expense": {"line_id": line, "date": snap["periods"][0]["start"], "amount": 120}})
    call("project.encrypt", {"password": "un mot de passe"})
    call(
        "feedback.save", {"feedback": {"received": snap["periods"][0]["start"], "category": "sea", "summary": "Secret"}}
    )
    call("risk.save", {"risk": {"title": "Saison des pluies"}})

    formats = call("reports.formats", {})["formats"]
    assert len([f for f in formats if f["builtin"]]) == 23
    # Text written for a report is kept for the next generation of the same report.
    call("report_doc.save", {"format": "eu", "from": codes[0], "to": codes[3], "texts": {"summary": "Bonne année."}})
    got = call("report_doc.get", {"format": "eu", "from": codes[0], "to": codes[3]})
    assert got["texts"] == {"summary": "Bonne année."} and got["from"] == codes[0]
    for f in formats:
        out = tmp_path / f"{f['id']}.docx"
        call("reports.generate", {"path": str(out), "format": f["id"], "from": codes[0], "to": codes[3], "lang": "fr"})
        text = "\n".join(p.text for p in Document(str(out)).paragraphs)
        cells = "\n".join(c.text for t in Document(str(out)).tables for r in t.rows for c in r.cells)
        for i, sec in enumerate(f["sections"], start=1):
            assert f"{i}. {sec['fr']}" in text, (f["id"], sec["fr"])
        assert "Secret" not in text + cells  # a sensitive case never reaches a report
    eu = Document(str(tmp_path / "eu.docx"))
    body = "\n".join(p.text for p in eu.paragraphs)
    assert "Bonne année." in body and "Section à rédiger" in body
    tables = "\n".join(c.text for t in eu.tables for r in t.rows for c in r.cells)
    assert "Former les relais" in tables and "Formations" in tables
    # A custom format, then in English.
    custom = call(
        "report_format.save",
        {
            "format": {
                "name": "Mon canevas",
                "sections": [
                    {"kind": "text", "key": "intro", "label": "Intro"},
                    {"kind": "tracking", "label": "Suivi"},
                ],
            }
        },
    )["created"]
    out = tmp_path / "custom.docx"
    call("reports.generate", {"path": str(out), "format": custom, "lang": "en"})
    assert "2. Suivi" in "\n".join(p.text for p in Document(str(out)).paragraphs)
    assert set(donor_formats.KINDS) >= {s["kind"] for f in formats for s in f["sections"]}


def test_exports_tracking_values_and_data_pack(call, tmp_path):
    import openpyxl

    from sme_engine import exports

    node = _project(call, tmp_path)
    call("disaggregation.save", {"disaggregation": {"preset": "sex"}})
    ind = call(
        "indicator.save",
        {
            "node_id": node,
            "indicator": {
                "name": "Agents formés",
                "unit": "count",
                "source_type": "routine",
                "breakdowns": ["sex"],
                "target": 100,
                "people": "unique",
            },
        },
    )["saved"]
    sub = call("submission.open", {"period": "T1-2026"})["created"]
    call(
        "submission.save",
        {
            "id": sub,
            "values": [
                {"indicator_id": ind, "cats": {"sex": "f"}, "value": 12},
                {"indicator_id": ind, "cats": {"sex": "m"}, "value": 8},
            ],
        },
    )
    call("submission.act", {"id": sub, "action": "submit"})
    call("submission.act", {"id": sub, "action": "validate"})
    call("gap.save", {"indicator_id": ind, "period": "T1-2026", "text": "Formation reportée"})

    out = call("export.tracking", {"path": str(tmp_path / "suivi.xlsx"), "period": "T1-2026"})
    ws = openpyxl.load_workbook(out["path"])["Suivi"]
    cells = [c for row in ws.iter_rows(values_only=True) for c in row if c is not None]
    assert "Agents formés" in cells and 20 in cells and "Formation reportée" in cells

    xl = call("export.values", {"path": str(tmp_path / "valeurs.xlsx")})
    assert xl["rows"] == 2
    csvf = call("export.values", {"path": str(tmp_path / "valeurs"), "kind": "csv"})
    text = open(csvf["path"], encoding="utf-8-sig").read()
    assert csvf["path"].endswith(".csv") and "Agents formés" in text and ";12" in text

    packed = call("export.pack", {"path": str(tmp_path / "paquet")})
    data = exports.read_pack(tmp_path / "paquet.smepack")
    assert packed["indicators"] == 1 and data["project"]["profile"]["currency"] == "EUR"
    assert data["indicators"][0]["to_date"] == 20
    # No personal data travels in a pack.
    raw = json.dumps(data)
    assert "person" not in raw and "summary" not in raw
    with pytest.raises(Exception, match="pack"):
        bad = tmp_path / "x.smepack"
        bad.write_text("nope")
        exports.read_pack(bad)


def _routine_project(call, path, name, achieved):
    call(
        "project.create",
        {
            "path": str(path),
            "name": name,
            "profile": {"start": "2026-01-01", "end": "2026-12-31", "frequency": "quarterly"},
        },
    )
    node = call("framework.add", {"title": "Effet"})["created"]
    ind = call(
        "indicator.save",
        {
            "node_id": node,
            "indicator": {
                "name": "Personnes formées",
                "unit": "count",
                "source_type": "routine",
                "target": 100,
                "library_id": "x.trained",
            },
        },
    )["saved"]
    call("target.set", {"indicator_id": ind, "period": "T1-2026", "value": 25})
    sub = call("submission.open", {"period": "T1-2026"})["created"]
    call("submission.save", {"id": sub, "values": [{"indicator_id": ind, "value": achieved}]})
    call("submission.act", {"id": sub, "action": "submit"})
    call("submission.act", {"id": sub, "action": "validate"})
    call("activity.save", {"activity": {"title": "Atelier", "start": "2026-01-10", "end": "2026-02-10"}})
    call("project.close", {})


def test_portfolio_dashboard_common_indicators_packs_and_models(call, tmp_path):
    from docx import Document

    a, b = tmp_path / "a.sme", tmp_path / "b.sme"
    _routine_project(call, a, "Projet A", 30)
    _routine_project(call, b, "Projet B", 5)
    day = "2026-05-01"
    dash = call("portfolio.dashboard", {"paths": [str(a), str(b)], "today": day})
    cards = {c["name"]: c for c in dash["cards"]}
    assert cards["Projet A"]["indicators_on_track"] == 1 and cards["Projet B"]["indicators_on_track"] == 0
    assert cards["Projet B"]["status"] == "difficulty" and "indicators_low" in cards["Projet B"]["reasons"]
    assert cards["Projet A"]["late_activities"] == 1
    common = dash["common"][0]
    assert common["total"] == 35 and common["target"] == 200 and common["double_count_possible"]
    # Archived projects leave the dashboard.
    assert len(call("portfolio.dashboard", {"paths": [str(a), str(b)], "archived": [str(b)]})["cards"]) == 1
    # Thresholds of the organisation.
    with pytest.raises(RuntimeError, match="number_out_of_range"):
        call("portfolio.settings", {"settings": {"indicators_on_track": 2}})
    # Exports: note and page.
    note = call(
        "portfolio.export",
        {"kind": "note", "target": str(tmp_path / "note.docx"), "paths": [str(a), str(b)], "today": day},
    )
    text = "\n".join(p.text for p in Document(note["path"]).paragraphs)
    assert "2 projets" in text and "Projet B" in text
    page = call("portfolio.export", {"kind": "html", "target": str(tmp_path / "tdb"), "paths": [str(a)], "today": day})
    assert "Projet A" in open(page["path"], encoding="utf-8").read()
    # A pack from another office joins the dashboard; the project's own file wins over its pack.
    call("project.open", {"path": str(b)})
    call("export.pack", {"path": str(tmp_path / "b.smepack")})
    call("project.close", {})
    call("portfolio.import_pack", {"path": str(tmp_path / "b.smepack")})
    names = [c["name"] for c in call("portfolio.dashboard", {"paths": [str(a)], "today": day})["cards"]]
    assert sorted(names) == ["Projet A", "Projet B"]
    assert len(call("portfolio.dashboard", {"paths": [str(a), str(b)], "today": day})["cards"]) == 2
    # A project as the model of a new one: the design stays, the data go.
    model = tmp_path / "c.sme"
    call("project.duplicate_model", {"source": str(a), "target": str(model), "name": "Projet C"})
    snap = call("project.open", {"path": str(model)})
    assert snap["project"]["name"] == "Projet C" and len(snap["indicators"]) == 1
    assert snap["submissions"] == [] and snap["activities"][0]["status"] == "not_started"
    assert snap["targets"]
