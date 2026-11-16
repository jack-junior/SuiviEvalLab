# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 GAYI Komi Selassi and SANOUSSI Moudjibou

"""JSON-RPC methods of the work plan, budget, accountability, learning and
evaluation registers (modules M9, M10 and M11)."""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from typing import TYPE_CHECKING, Any

from . import reception, workplan
from . import registers as rg
from .project import Project
from .rpc import Server

if TYPE_CHECKING:
    from .service import Service


def state(p: Project, day: str | None = None) -> dict[str, Any]:
    """The part of the snapshot this module owns, with what is worked out from the records."""
    day = day or reception.today()
    cats = rg.categories(p.meta())
    feedback = []
    for f in p.records("feedback"):
        deadline = rg.feedback_deadline(f, cats)
        feedback.append({**f, "deadline": deadline, "overdue": f["status"] in rg.FEEDBACK_OPEN and deadline < day})
    recs = []
    for r in p.records("recommendation"):
        late = [a["id"] for a in r["actions"] if a["status"] != "done" and a["due"] and a["due"] < day]
        recs.append({**r, "status": rg.recommendation_status(r), "late_actions": late})
    risks = []
    for r in p.records("risk"):
        due = rg.risk_review_due(r)
        risks.append({**r, "level": rg.risk_level(r), "review_due": due, "review_late": bool(due and due < day)})
    return {
        "activities": workplan.activities_view(p, day),
        "budget_lines": p.records("budget_line"),
        "expenses": p.records("expense"),
        "workplan": workplan.summary(p, day),
        "feedback": feedback,
        "feedback_categories": cats,
        "recommendations": recs,
        "risks": risks,
        "learning_questions": p.records("learning_question"),
        "lessons": p.records("lesson"),
        "meetings": p.records("meeting"),
        "evaluations": p.records("evaluation"),
        "qual_notes": p.records("qual_note"),
        "qual_themes": p.records("qual_theme"),
    }


def feedback_stats(p: Project, day: str) -> dict[str, Any]:
    """Counts anyone may see, without the content of any case."""
    st = state(p, day)
    fb = st["feedback"]
    answered = [f for f in fb if f.get("answered_at")]
    on_time = [f for f in answered if f["answered_at"][:10] <= f["deadline"]]
    return {
        "total": len(fb),
        "open": sum(1 for f in fb if f["status"] in rg.FEEDBACK_OPEN),
        "overdue": sum(1 for f in fb if f["overdue"]),
        "sensitive": sum(1 for f in fb if f["sensitive"]),
        "by_category": dict(Counter(f["category"] for f in fb)),
        "by_channel": dict(Counter(f["channel"] for f in fb)),
        "by_status": dict(Counter(f["status"] for f in fb)),
        "on_time": len(on_time) / len(answered) if answered else None,
    }


def register_registers(server: Server, svc: Service) -> None:
    def project() -> Project:
        return svc.project

    def done(created: str | None = None) -> dict[str, Any]:
        snap = svc.snapshot()
        return {**snap, "created": created} if created else snap

    def save(table: str, params: dict[str, Any], spec: dict[str, Any]) -> dict[str, Any]:
        p = project()
        own = params.get("id")
        if own:
            p.update_record(table, own, spec)
            return done(own)
        return done(p.insert_record(table, spec))

    def current(table: str, params: dict[str, Any]) -> dict[str, Any] | None:
        return project().record(table, params["id"]) if params.get("id") else None

    # ----- M9 -------------------------------------------------------------------------------------

    @server.method("activity.save")
    def activity_save(params: dict[str, Any]) -> dict[str, Any]:
        p = project()
        cur = current("activity", params)
        spec = rg.validate_activity(params.get("activity"), p.records("activity"), params.get("id"))
        if cur and cur.get("origin") and not spec["origin"]:
            spec["origin"] = cur["origin"]
        return save("activity", params, spec)

    @server.method("activity.delete")
    def activity_delete(params: dict[str, Any]) -> dict[str, Any]:
        p = project()
        own = params.get("id")
        p.record("activity", own)
        for a in p.records("activity"):
            if a.get("parent_id") == own:
                p.delete_record("activity", a["id"])
        for ln in p.records("budget_line"):
            if ln.get("activity_id") == own:
                p.update_record("budget_line", ln["id"], {**ln, "activity_id": None})
        p.delete_record("activity", own)
        return done()

    @server.method("activity.move")
    def activity_move(params: dict[str, Any]) -> dict[str, Any]:
        project().move_record("activity", params.get("id"), params.get("direction"))
        return done()

    @server.method("activity.generate_me")
    def activity_generate(params: dict[str, Any]) -> dict[str, Any]:
        """Add the M&E activities the monitoring plan implies, once each."""
        p = project()
        have = {a.get("origin") for a in p.records("activity") if a.get("origin")}
        added = 0
        lang = "en" if params.get("lang") == "en" else "fr"
        for a in workplan.me_activities(p, lang):
            if a["origin"] in have:
                continue
            p.insert_record("activity", rg.validate_activity(a, []))
            added += 1
        return {**done(), "added": added}

    @server.method("workplan.summary")
    def workplan_summary(params: dict[str, Any]) -> dict[str, Any]:
        return workplan.summary(project(), params.get("today") or reception.today())

    @server.method("budget_line.save")
    def line_save(params: dict[str, Any]) -> dict[str, Any]:
        codes = {x["code"] for x in project().records("period")}
        return save("budget_line", params, rg.validate_budget_line(params.get("line"), codes))

    @server.method("budget_line.delete")
    def line_delete(params: dict[str, Any]) -> dict[str, Any]:
        p = project()
        own = params.get("id")
        p.record("budget_line", own)
        for e in p.records("expense"):
            if e["line_id"] == own:
                p.delete_record("expense", e["id"])
        p.delete_record("budget_line", own)
        return done()

    @server.method("expense.save")
    def expense_save(params: dict[str, Any]) -> dict[str, Any]:
        ids = {ln["id"] for ln in project().records("budget_line")}
        return save("expense", params, rg.validate_expense(params.get("expense"), ids))

    @server.method("expense.delete")
    def expense_delete(params: dict[str, Any]) -> dict[str, Any]:
        project().delete_record("expense", params.get("id"))
        return done()

    @server.method("expense.inspect")
    def expense_inspect(params: dict[str, Any]) -> dict[str, Any]:
        from . import datasets

        path = Path(str(params.get("path") or ""))
        if not path.is_file():
            raise rg._err("No file chosen", "invalid_params")
        info = datasets.inspect(path, params.get("sheet"))
        return {k: info[k] for k in ("file_name", "columns", "sample", "sheets", "sheet")}

    @server.method("expense.import")
    def expense_import(params: dict[str, Any]) -> dict[str, Any]:
        path = Path(str(params.get("path") or ""))
        if not path.is_file():
            raise rg._err("No file chosen", "invalid_params")
        cols = params.get("columns") if isinstance(params.get("columns"), dict) else {}
        commit = bool(params.get("commit"))
        result = workplan.read_expenses(project(), path, params.get("sheet"), cols, commit)
        return {**(done() if commit else {}), "import": result}

    # ----- M11 ------------------------------------------------------------------------------------

    @server.method("feedback.categories")
    def feedback_categories(params: dict[str, Any]) -> dict[str, Any]:
        p = project()
        cats = rg.validate_categories(params.get("categories"))
        used = {f["category"] for f in p.records("feedback")}
        gone = used - {c["key"] for c in cats}
        if gone:
            raise rg._err("A category in use cannot be removed", "category_in_use")
        p.set_meta("feedback_categories", json.dumps(cats, ensure_ascii=False))
        return done()

    @server.method("feedback.save")
    def feedback_save(params: dict[str, Any]) -> dict[str, Any]:
        p = project()
        key = reception.person_key(p)
        spec = rg.validate_feedback(
            params.get("feedback"),
            rg.categories(p.meta()),
            current("feedback", params),
            lambda raw: reception.pseudonym(key, raw),
        )
        return save("feedback", params, spec)

    @server.method("feedback.delete")
    def feedback_delete(params: dict[str, Any]) -> dict[str, Any]:
        project().delete_record("feedback", params.get("id"))
        return done()

    @server.method("feedback.stats")
    def feedback_stats_rpc(params: dict[str, Any]) -> dict[str, Any]:
        return feedback_stats(project(), params.get("today") or reception.today())

    @server.method("recommendation.save")
    def rec_save(params: dict[str, Any]) -> dict[str, Any]:
        spec = rg.validate_recommendation(params.get("recommendation"), current("recommendation", params))
        return save("recommendation", params, spec)

    @server.method("recommendation.delete")
    def rec_delete(params: dict[str, Any]) -> dict[str, Any]:
        project().delete_record("recommendation", params.get("id"))
        return done()

    @server.method("risk.save")
    def risk_save(params: dict[str, Any]) -> dict[str, Any]:
        return save("risk", params, rg.validate_risk(params.get("risk"), current("risk", params)))

    @server.method("risk.delete")
    def risk_delete(params: dict[str, Any]) -> dict[str, Any]:
        project().delete_record("risk", params.get("id"))
        return done()

    @server.method("risk.review")
    def risk_review(params: dict[str, Any]) -> dict[str, Any]:
        p = project()
        risk = p.record("risk", params.get("id"))
        review = rg.validate_review(params.get("review"))
        reviews = sorted([*risk.get("reviews", []), review], key=lambda r: r["date"])[-100:]
        p.update_record(
            "risk",
            risk["id"],
            {**risk, "reviews": reviews, "probability": review["probability"], "impact": review["impact"]},
        )
        return done()

    @server.method("risk.from_assumptions")
    def risk_from_assumptions(params: dict[str, Any]) -> dict[str, Any]:
        """One assumption per line of the logframe column, for the results that have some."""
        p = project()
        have = {(r.get("node_id"), r["title"].casefold()) for r in p.records("risk")}
        added = 0
        for node in p.framework():
            for line in (node.get("assumptions") or "").splitlines():
                title = line.strip(" -*\t")[:300]
                if not title or (node["id"], title.casefold()) in have:
                    continue
                p.insert_record(
                    "risk", rg.validate_risk({"kind": "assumption", "node_id": node["id"], "title": title}, None)
                )
                have.add((node["id"], title.casefold()))
                added += 1
        return {**done(), "added": added}

    for table, key, validate in (
        ("learning_question", "question", rg.validate_learning_question),
        ("lesson", "lesson", rg.validate_lesson),
        ("meeting", "meeting", rg.validate_meeting),
        ("evaluation", "evaluation", rg.validate_evaluation),
        ("qual_theme", "theme", rg.validate_theme),
    ):
        _simple(server, table, key, validate, save, project, done)

    @server.method("qual_note.save")
    def note_save(params: dict[str, Any]) -> dict[str, Any]:
        themes = {t["id"] for t in project().records("qual_theme")}
        return save("qual_note", params, rg.validate_note(params.get("note"), themes))

    @server.method("qual_note.delete")
    def note_delete(params: dict[str, Any]) -> dict[str, Any]:
        project().delete_record("qual_note", params.get("id"))
        return done()


def _simple(server: Server, table: str, key: str, validate, save, project, done) -> None:
    def save_method(params: dict[str, Any]) -> dict[str, Any]:
        return save(table, params, validate(params.get(key)))

    def delete_method(params: dict[str, Any]) -> dict[str, Any]:
        p = project()
        own = params.get("id")
        p.record(table, own)
        if table == "qual_theme":
            for n in p.records("qual_note"):
                if any(own in x["theme_ids"] for x in n["excerpts"]):
                    for x in n["excerpts"]:
                        x["theme_ids"] = [t for t in x["theme_ids"] if t != own]
                    p.update_record("qual_note", n["id"], n)
        if table == "evaluation":
            for r in p.records("recommendation"):
                if r.get("evaluation_id") == own:
                    p.update_record("recommendation", r["id"], {**r, "evaluation_id": None})
            for n in p.records("qual_note"):
                if n.get("evaluation_id") == own:
                    p.update_record("qual_note", n["id"], {**n, "evaluation_id": None})
        p.delete_record(table, own)
        return done()

    server.method(f"{table}.save")(save_method)
    server.method(f"{table}.delete")(delete_method)
