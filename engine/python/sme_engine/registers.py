# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 GAYI Komi Selassi and SANOUSSI Moudjibou

"""Registers kept around the monitoring (modules M9, M10 and M11).

Each register is a list of positioned JSON records of the project:

    activity        work plan (M9): project activities and M&E activities
    budget_line     planned amounts by period (M9)
    expense         amounts spent on a budget line (M9)
    feedback        feedback and complaints (M11)
    recommendation  recommendations and the follow-up given (M11)
    risk            risks and assumptions (M11)
    learning_question, lesson, meeting   learning (M11)
    evaluation      evaluations: sheet, questions, matrix, steps (M10)
    qual_note, qual_theme                qualitative data and its coding (M10)

This module checks the records; agenda.py turns their dates into deadlines and
tasks, and workplan.py works out the progress of the work plan and the budget.
"""

from __future__ import annotations

import json
import uuid
from datetime import date
from typing import Any

from .rpc import INVALID_PARAMS, RpcError

TABLES = (
    "activity",
    "budget_line",
    "expense",
    "feedback",
    "recommendation",
    "risk",
    "learning_question",
    "lesson",
    "meeting",
    "evaluation",
    "qual_note",
    "qual_theme",
    "report_format",
    "report_doc",
)

SCHEMA = "".join(
    f"""
CREATE TABLE IF NOT EXISTS {t} (
    id          TEXT PRIMARY KEY,
    position    INTEGER NOT NULL,
    spec        TEXT NOT NULL            -- JSON, see registers.py
);"""
    for t in TABLES
)

ACTIVITY_STATES = ("not_started", "in_progress", "done", "postponed", "cancelled")
FAMILIES = ("project", "me")
ME_KINDS = ("", "collection", "dqa", "review", "evaluation", "mission", "other")
CHANNELS = ("box", "hotline", "meeting", "in_person", "sms", "other")
FEEDBACK_STATES = ("received", "forwarded", "in_progress", "answered", "closed")
FEEDBACK_OPEN = ("received", "forwarded", "in_progress")
SENSITIVITY = ("", "sea", "fraud", "safety", "other")
REC_SOURCES = ("evaluation", "mission", "review", "audit", "other")
RESPONSES = ("pending", "accepted", "partial", "rejected")
ACTION_STATES = ("todo", "doing", "done")
RISK_KINDS = ("risk", "assumption")
RISK_STATES = ("active", "closed")
REVIEW_MONTHS = (0, 1, 3, 6, 12)
EVAL_KINDS = ("midterm", "final", "thematic", "ex_post", "other")
EVAL_STEPS = ("tor", "recruitment", "collection", "draft", "final")
CRITERIA = ("relevance", "coherence", "effectiveness", "efficiency", "impact", "sustainability")
NOTE_KINDS = ("interview", "fgd", "observation", "other")
QUESTION_STATES = ("open", "answered")
MEETING_KINDS = ("review", "quarterly", "learning", "steering", "other")

# Feedback categories offered in a new project, with the days allowed for an answer.
DEFAULT_CATEGORIES = [
    {"key": "info_request", "name": "", "days": 14, "sensitive": False},
    {"key": "assistance_request", "name": "", "days": 14, "sensitive": False},
    {"key": "service_complaint", "name": "", "days": 14, "sensitive": False},
    {"key": "staff_conduct", "name": "", "days": 7, "sensitive": True},
    {"key": "sea", "name": "", "days": 1, "sensitive": True},
    {"key": "fraud", "name": "", "days": 3, "sensitive": True},
    {"key": "thanks", "name": "", "days": 30, "sensitive": False},
    {"key": "other", "name": "", "days": 14, "sensitive": False},
]


def _err(message: str, key: str, **info: Any) -> RpcError:
    return RpcError(message, INVALID_PARAMS, data={"key": key, **info})


def _text(value: Any, n: int) -> str:
    return str(value or "").strip()[:n]


def _day(value: Any, name: str, required: bool = False) -> str:
    if value in (None, ""):
        if required:
            raise _err(f"{name} is required", "field_required", field=name)
        return ""
    try:
        return date.fromisoformat(str(value).strip()[:10]).isoformat()
    except ValueError:
        raise _err(f"{name} is not a valid date", "date_invalid", field=name) from None


def _choice(value: Any, allowed: tuple, default: Any) -> Any:
    return value if value in allowed else default


def _number(value: Any, name: str, low: float | None = None, high: float | None = None) -> float | None:
    if value in (None, ""):
        return None
    try:
        x = float(str(value).replace(",", ".").replace(" ", "").replace(" ", ""))
    except ValueError:
        raise _err(f"{name} is not a number", "number_invalid", field=name) from None
    if x != x or (low is not None and x < low) or (high is not None and x > high):
        raise _err(f"{name} is out of range", "number_out_of_range", field=name)
    return x


def _ids(value: Any, n: int = 500) -> list[str]:
    if not isinstance(value, list):
        return []
    return [_text(v, 80) for v in value[:n] if isinstance(v, str) and v.strip()]


def _obj(spec: Any, what: str) -> dict[str, Any]:
    if not isinstance(spec, dict):
        raise _err(f"The {what} must be an object", "invalid_params")
    return spec


def _title(spec: dict[str, Any], field: str = "title", n: int = 300) -> str:
    title = _text(spec.get(field), n)
    if not title:
        raise _err(f"{field} is required", "field_required", field=field)
    return title


def _dates(start: str, end: str) -> None:
    if start and end and end < start:
        raise _err("The end comes before the start", "dates_order")


def _sub_id(value: Any) -> str:
    return _text(value, 40) or uuid.uuid4().hex[:12]


# ----- M9 work plan and budget -------------------------------------------------------------------


def validate_activity(spec: Any, others: list[dict[str, Any]], own_id: str | None = None) -> dict[str, Any]:
    s = _obj(spec, "activity")
    start, end = _day(s.get("start"), "start"), _day(s.get("end"), "end")
    _dates(start, end)
    actual_start, actual_end = _day(s.get("actual_start"), "actual_start"), _day(s.get("actual_end"), "actual_end")
    _dates(actual_start, actual_end)
    status = _choice(s.get("status"), ACTIVITY_STATES, "not_started")
    progress = _number(s.get("progress"), "progress", 0, 100) or 0.0
    if status == "done":
        progress = 100.0
    parent = _text(s.get("parent_id"), 80) or None
    if parent:
        by_id = {a["id"]: a for a in others}
        if parent not in by_id or parent == own_id:
            raise _err("Unknown parent activity", "activity_not_found")
        if by_id[parent].get("parent_id"):
            raise _err("A sub-activity cannot have sub-activities", "activity_too_deep")
        if own_id and any(a.get("parent_id") == own_id for a in others):
            raise _err("An activity with sub-activities cannot become one", "activity_too_deep")
    family = _choice(s.get("family"), FAMILIES, "project")
    return {
        "title": _title(s),
        "code": _text(s.get("code"), 30),
        "family": family,
        "me_kind": _choice(s.get("me_kind"), ME_KINDS, "") if family == "me" else "",
        "node_id": _text(s.get("node_id"), 80) or None,
        "parent_id": parent,
        "start": start,
        "end": end,
        "actual_start": actual_start,
        "actual_end": actual_end,
        "status": status,
        "progress": progress,
        "responsible": _text(s.get("responsible"), 120),
        "place_ids": _ids(s.get("place_ids")),
        "partner_id": _text(s.get("partner_id"), 80) or None,
        "milestone": bool(s.get("milestone")),
        "comment": _text(s.get("comment"), 4000),
        "origin": _text(s.get("origin"), 120),
    }


def validate_budget_line(spec: Any, period_codes: set[str]) -> dict[str, Any]:
    s = _obj(spec, "budget line")
    planned_in = s.get("planned") if isinstance(s.get("planned"), dict) else {}
    planned = {}
    for code, amount in planned_in.items():
        if code not in period_codes:
            raise _err(f"Unknown period: {code}", "period_not_found", period=code)
        x = _number(amount, "planned", 0)
        if x:
            planned[code] = x
    return {
        "code": _text(s.get("code"), 40),
        "name": _title(s, "name"),
        "activity_id": _text(s.get("activity_id"), 80) or None,
        "planned": planned,
        "note": _text(s.get("note"), 2000),
    }


def validate_expense(spec: Any, line_ids: set[str]) -> dict[str, Any]:
    s = _obj(spec, "expense")
    line = _text(s.get("line_id"), 80)
    if line not in line_ids:
        raise _err("Unknown budget line", "budget_line_not_found")
    amount = _number(s.get("amount"), "amount")
    if amount is None:
        raise _err("amount is required", "field_required", field="amount")
    return {
        "line_id": line,
        "date": _day(s.get("date"), "date", required=True),
        "amount": amount,
        "label": _text(s.get("label"), 300),
        "ref": _text(s.get("ref"), 80),
    }


# ----- M11 accountability and learning ----------------------------------------------------------------


def categories(meta: dict[str, str]) -> list[dict[str, Any]]:
    try:
        cats = json.loads(meta.get("feedback_categories", ""))
        if isinstance(cats, list) and cats:
            return cats
    except ValueError:
        pass
    return [dict(c) for c in DEFAULT_CATEGORIES]


def validate_categories(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list) or not value:
        raise _err("Give at least one category", "field_required", field="categories")
    out, seen = [], set()
    for c in value[:60]:
        c = _obj(c, "category")
        key = _text(c.get("key"), 40) or f"c_{uuid.uuid4().hex[:8]}"
        if key in seen:
            continue
        seen.add(key)
        name = _text(c.get("name"), 120)
        if key.startswith("c_") and not name:
            raise _err("A new category needs a name", "field_required", field="name")
        days = _number(c.get("days"), "days", 0, 365)
        out.append(
            {
                "key": key,
                "name": name,
                "days": int(days if days is not None else 14),
                "sensitive": bool(c.get("sensitive")),
            }
        )
    return out


def validate_feedback(spec: Any, cats: list[dict[str, Any]], current: dict[str, Any] | None, pseudo) -> dict[str, Any]:
    s = _obj(spec, "feedback")
    received = _day(s.get("received"), "received", required=True)
    cat_key = _text(s.get("category"), 40)
    cat = next((c for c in cats if c["key"] == cat_key), None)
    if cat is None:
        raise _err("Unknown category", "category_not_found")
    status = _choice(s.get("status"), FEEDBACK_STATES, "received")
    sensitivity = _choice(s.get("sensitivity"), SENSITIVITY, "")
    if cat_key in ("sea", "fraud") and not sensitivity:
        sensitivity = cat_key
    prev = current or {}
    history = list(prev.get("history", []))
    from .reception import now

    stamp = now()
    if not history or history[-1]["status"] != status:
        history.append({"status": status, "at": stamp, "note": _text(s.get("status_note"), 1000)})
    raw_person = _text(s.get("person"), 200)
    return {
        "received": received,
        "channel": _choice(s.get("channel"), CHANNELS, "other"),
        "place_id": _text(s.get("place_id"), 80) or None,
        "category": cat_key,
        "sensitive": bool(s.get("sensitive")) or cat["sensitive"] or bool(sensitivity),
        "sensitivity": sensitivity,
        # The person is never kept as typed: only its pseudonym under the project key.
        "person": pseudo(raw_person) if raw_person else prev.get("person", ""),
        "summary": _title(s, "summary", 300),
        "detail": _text(s.get("detail"), 8000),
        "response": _text(s.get("response"), 8000),
        "status": status,
        "history": history[-50:],
        "answered_at": prev.get("answered_at") or (stamp if status in ("answered", "closed") else None),
        "closed_at": stamp if status == "closed" and not prev.get("closed_at") else prev.get("closed_at"),
    }


def feedback_deadline(fb: dict[str, Any], cats: list[dict[str, Any]]) -> str:
    from datetime import timedelta

    cat = next((c for c in cats if c["key"] == fb["category"]), {"days": 14})
    return (date.fromisoformat(fb["received"]) + timedelta(days=int(cat["days"]))).isoformat()


def validate_recommendation(spec: Any, current: dict[str, Any] | None) -> dict[str, Any]:
    s = _obj(spec, "recommendation")
    from .reception import now

    old = {a["id"]: a for a in (current or {}).get("actions", [])}
    actions = []
    for a in (s.get("actions") if isinstance(s.get("actions"), list) else [])[:50]:
        a = _obj(a, "action")
        aid = _sub_id(a.get("id"))
        status = _choice(a.get("status"), ACTION_STATES, "todo")
        done_at = old.get(aid, {}).get("done_at") if status == "done" else None
        actions.append(
            {
                "id": aid,
                "text": _title(a, "text", 1000),
                "responsible": _text(a.get("responsible"), 120),
                "due": _day(a.get("due"), "due"),
                "status": status,
                "done_at": done_at or (now() if status == "done" else None),
            }
        )
    response = _choice(s.get("response"), RESPONSES, "pending")
    if response == "rejected" and not _text(s.get("response_reason"), 10):
        raise _err("Say why the recommendation is rejected", "field_required", field="response_reason")
    return {
        "source": _choice(s.get("source"), REC_SOURCES, "other"),
        "evaluation_id": _text(s.get("evaluation_id"), 80) or None,
        "source_ref": _text(s.get("source_ref"), 300),
        "date": _day(s.get("date"), "date"),
        "text": _title(s, "text", 4000),
        "response": response,
        "response_reason": _text(s.get("response_reason"), 4000),
        "actions": actions,
    }


def recommendation_status(r: dict[str, Any]) -> str:
    if r["response"] == "rejected":
        return "rejected"
    if r["response"] == "pending":
        return "pending"
    if r["actions"] and all(a["status"] == "done" for a in r["actions"]):
        return "done"
    return "in_progress"


def validate_risk(spec: Any, current: dict[str, Any] | None) -> dict[str, Any]:
    s = _obj(spec, "risk")
    from .reception import now

    months = s.get("review_months")
    try:
        months = int(months)
    except (TypeError, ValueError):
        months = 3
    return {
        "kind": _choice(s.get("kind"), RISK_KINDS, "risk"),
        "node_id": _text(s.get("node_id"), 80) or None,
        "title": _title(s),
        "description": _text(s.get("description"), 4000),
        "probability": int(_number(s.get("probability"), "probability", 1, 5) or 3),
        "impact": int(_number(s.get("impact"), "impact", 1, 5) or 3),
        "measures": _text(s.get("measures"), 4000),
        "responsible": _text(s.get("responsible"), 120),
        "review_months": months if months in REVIEW_MONTHS else 3,
        "status": _choice(s.get("status"), RISK_STATES, "active"),
        "reviews": (current or {}).get("reviews", []),
        "created_at": (current or {}).get("created_at") or now(),
    }


def risk_level(r: dict[str, Any]) -> str:
    score = r["probability"] * r["impact"]
    return "high" if score >= 15 else "medium" if score >= 6 else "low"


def risk_review_due(r: dict[str, Any]) -> str:
    from .schedule import _add_months

    if r["status"] != "active" or not r["review_months"]:
        return ""
    last = r["reviews"][-1]["date"] if r.get("reviews") else r["created_at"][:10]
    return _add_months(date.fromisoformat(last), r["review_months"]).isoformat()


def validate_review(spec: Any) -> dict[str, Any]:
    s = _obj(spec, "review")
    return {
        "date": _day(s.get("date"), "date", required=True),
        "probability": int(_number(s.get("probability"), "probability", 1, 5) or 3),
        "impact": int(_number(s.get("impact"), "impact", 1, 5) or 3),
        "note": _text(s.get("note"), 4000),
    }


def validate_learning_question(spec: Any) -> dict[str, Any]:
    s = _obj(spec, "learning question")
    return {
        "text": _title(s, "text", 1000),
        "status": _choice(s.get("status"), QUESTION_STATES, "open"),
        "answer": _text(s.get("answer"), 8000),
        "node_id": _text(s.get("node_id"), 80) or None,
    }


def validate_lesson(spec: Any) -> dict[str, Any]:
    s = _obj(spec, "lesson")
    return {
        "date": _day(s.get("date"), "date"),
        "title": _title(s),
        "context": _text(s.get("context"), 4000),
        "finding": _text(s.get("finding"), 4000),
        "lesson": _text(s.get("lesson"), 4000),
        "use": _text(s.get("use"), 4000),
        "question_id": _text(s.get("question_id"), 80) or None,
        "tags": [t for t in (_text(x, 40) for x in (s.get("tags") or [])[:20]) if t]
        if isinstance(s.get("tags"), list)
        else [],
    }


def validate_meeting(spec: Any) -> dict[str, Any]:
    s = _obj(spec, "meeting")
    decisions = []
    for d in (s.get("decisions") if isinstance(s.get("decisions"), list) else [])[:50]:
        d = _obj(d, "decision")
        decisions.append(
            {
                "id": _sub_id(d.get("id")),
                "text": _title(d, "text", 1000),
                "responsible": _text(d.get("responsible"), 120),
                "due": _day(d.get("due"), "due"),
                "as_task": bool(d.get("as_task")),
                "status": _choice(d.get("status"), ACTION_STATES, "todo"),
            }
        )
    return {
        "date": _day(s.get("date"), "date", required=True),
        "title": _title(s),
        "kind": _choice(s.get("kind"), MEETING_KINDS, "review"),
        "participants": _text(s.get("participants"), 2000),
        "notes": _text(s.get("notes"), 20000),
        "decisions": decisions,
    }


# ----- M10 evaluations and qualitative data -------------------------------------------------------


def validate_evaluation(spec: Any) -> dict[str, Any]:
    s = _obj(spec, "evaluation")
    start, end = _day(s.get("start"), "start"), _day(s.get("end"), "end")
    _dates(start, end)
    steps_in = s.get("steps") if isinstance(s.get("steps"), dict) else {}
    steps = {}
    for k in EVAL_STEPS:
        st = steps_in.get(k) if isinstance(steps_in.get(k), dict) else {}
        steps[k] = {"date": _day(st.get("date"), f"steps.{k}"), "done": bool(st.get("done"))}
    questions = []
    for q in (s.get("questions") if isinstance(s.get("questions"), list) else [])[:100]:
        q = _obj(q, "question")
        questions.append(
            {
                "id": _sub_id(q.get("id")),
                "criterion": _choice(q.get("criterion"), CRITERIA, "effectiveness"),
                "text": _title(q, "text", 1000),
                "indicator_ids": _ids(q.get("indicator_ids")),
                "sources": _text(q.get("sources"), 2000),
                "methods": _text(q.get("methods"), 2000),
                "analysis_ids": _ids(q.get("analysis_ids")),
                "findings": _text(q.get("findings"), 8000),
                "conclusion": _text(q.get("conclusion"), 8000),
            }
        )
    return {
        "title": _title(s),
        "kind": _choice(s.get("kind"), EVAL_KINDS, "midterm"),
        "start": start,
        "end": end,
        "evaluator": _text(s.get("evaluator"), 300),
        "budget": _number(s.get("budget"), "budget", 0),
        "tor": _text(s.get("tor"), 20000),
        "steps": steps,
        "questions": questions,
        "conclusions": _text(s.get("conclusions"), 20000),
    }


def validate_theme(spec: Any) -> dict[str, Any]:
    s = _obj(spec, "theme")
    return {"name": _title(s, "name", 120), "description": _text(s.get("description"), 2000)}


def validate_note(spec: Any, themes: set[str]) -> dict[str, Any]:
    s = _obj(spec, "note")
    text = _text(s.get("text"), 200_000)
    excerpts = []
    for x in (s.get("excerpts") if isinstance(s.get("excerpts"), list) else [])[:2000]:
        x = _obj(x, "excerpt")
        try:
            start, end = int(x.get("start")), int(x.get("end"))
        except (TypeError, ValueError):
            raise _err("An excerpt needs its place in the text", "invalid_params") from None
        if not 0 <= start < end <= len(text):
            raise _err("The excerpt is outside the text", "excerpt_outside")
        excerpts.append(
            {
                "id": _sub_id(x.get("id")),
                "start": start,
                "end": end,
                "text": text[start:end],
                "theme_ids": [t for t in _ids(x.get("theme_ids")) if t in themes],
                "question_id": _text(x.get("question_id"), 40) or None,
                "memo": _text(x.get("memo"), 2000),
            }
        )
    return {
        "title": _title(s),
        "kind": _choice(s.get("kind"), NOTE_KINDS, "interview"),
        "evaluation_id": _text(s.get("evaluation_id"), 80) or None,
        "date": _day(s.get("date"), "date"),
        "place": _text(s.get("place"), 200),
        "participants": _text(s.get("participants"), 1000),
        "text": text,
        "excerpts": sorted(excerpts, key=lambda e: e["start"]),
    }
