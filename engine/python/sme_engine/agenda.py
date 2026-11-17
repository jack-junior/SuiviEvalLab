# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 GAYI Komi Selassi and SANOUSSI Moudjibou

"""Agenda and tasks of a project, and its "today" (sections M2 and M14).

What is planned becomes a deadline, and a deadline becomes a task. Deadlines
and generated tasks are not stored: they are worked out from the project each
time, so a generated task disappears by itself once its action is done (the
data received, the submission validated, the gap explained, the report sent).
Tasks and events typed by the user are stored:

    task:  {"title", "due": "2026-04-10", "priority": "low" | "normal" | "high",
            "status": "todo" | "doing" | "waiting" | "done", "note", "assignee",
            "recurrence": "" | "monthly" | "quarterly", "link": {"kind", "id"} | null,
            "created_at", "done_at"}
    event: {"title", "kind": "meeting" | "mission" | "training" | "workshop" | "absence"
            | "collection" | "other", "start": "2026-04-10" or "2026-04-10T09:00",
            "end", "place", "note"}
"""

from __future__ import annotations

import re
import uuid
from datetime import date, datetime, timedelta
from typing import Any

from . import monitoring, reception
from .project import Project
from .rpc import INVALID_PARAMS, RpcError
from .schedule import _add_months

PRIORITIES = ("low", "normal", "high")
TASK_STATES = ("todo", "doing", "waiting", "done")
RECURRENCES = ("", "monthly", "quarterly")
EVENT_KINDS = ("meeting", "mission", "training", "workshop", "absence", "collection", "other")
VERIFY_DAYS = 7
SOON = 7


def _err(message: str, key: str, **info: Any) -> RpcError:
    return RpcError(message, INVALID_PARAMS, data={"key": key, **info})


def _day(value: Any, name: str, required: bool = False) -> str:
    if value in (None, ""):
        if required:
            raise _err(f"{name} is required", "field_required", field=name)
        return ""
    text = str(value).strip()
    try:
        if "T" in text:
            return datetime.fromisoformat(text[:16]).isoformat(timespec="minutes")
        return date.fromisoformat(text[:10]).isoformat()
    except ValueError:
        raise _err(f"{name} is not a valid date", "date_invalid", field=name) from None


def _text(value: Any, n: int) -> str:
    return str(value or "").strip()[:n]


# ----- stored tasks and events ------------------------------------------------------------


def validate_task(spec: Any, current: dict[str, Any] | None = None) -> dict[str, Any]:
    if not isinstance(spec, dict):
        raise _err("The task must be an object", "invalid_params")
    title = _text(spec.get("title"), 300)
    if not title:
        raise _err("The task needs a title", "field_required", field="title")
    status = spec.get("status") if spec.get("status") in TASK_STATES else "todo"
    link = spec.get("link") if isinstance(spec.get("link"), dict) else None
    out = {
        "title": title,
        "due": _day(spec.get("due"), "due"),
        "priority": spec.get("priority") if spec.get("priority") in PRIORITIES else "normal",
        "status": status,
        "note": _text(spec.get("note"), 4000),
        "assignee": _text(spec.get("assignee"), 120),
        "recurrence": spec.get("recurrence") if spec.get("recurrence") in RECURRENCES else "",
        "link": {"kind": _text(link.get("kind"), 30), "id": _text(link.get("id"), 80)} if link else None,
        "created_at": (current or {}).get("created_at") or reception.now(),
        "done_at": (current or {}).get("done_at"),
    }
    if status == "done" and not out["done_at"]:
        out["done_at"] = reception.now()
    if status != "done":
        out["done_at"] = None
    return out


def next_occurrence(task: dict[str, Any]) -> dict[str, Any] | None:
    """The next task of a recurring one marked done."""
    if not task.get("recurrence") or not task.get("due"):
        return None
    months = 1 if task["recurrence"] == "monthly" else 3
    due = _add_months(date.fromisoformat(task["due"][:10]), months).isoformat()
    return {**task, "due": due, "status": "todo", "done_at": None, "created_at": reception.now()}


def validate_event(spec: Any) -> dict[str, Any]:
    if not isinstance(spec, dict):
        raise _err("The event must be an object", "invalid_params")
    title = _text(spec.get("title"), 300)
    if not title:
        raise _err("The event needs a title", "field_required", field="title")
    start = _day(spec.get("start"), "start", required=True)
    end = _day(spec.get("end"), "end") or start
    if end[:10] < start[:10]:
        raise _err("The event ends before it starts", "dates_order")
    return {
        "title": title,
        "kind": spec.get("kind") if spec.get("kind") in EVENT_KINDS else "other",
        "start": start,
        "end": end,
        "place": _text(spec.get("place"), 200),
        "note": _text(spec.get("note"), 4000),
    }


# ----- worked out from the project ------------------------------------------------------------


def _unit_name(view: reception.View, unit: dict[str, str], lang: str) -> str:
    partner = next((p for p in view.partners if p["id"] == unit.get("partner_id")), None)
    place = next((p for p in view.places if p["id"] == unit.get("place_id")), None)
    parts = [x for x in ((partner or {}).get("acronym") or (partner or {}).get("name"), (place or {}).get("name")) if x]
    return ", ".join(parts)


def derived(view: reception.View, day: str, lang: str = "fr") -> dict[str, list[dict[str, Any]]]:
    """Deadlines and generated tasks of the project on a given day."""
    events: list[dict[str, Any]] = []
    tasks: list[dict[str, Any]] = []
    label = (lambda p: p["label_en"]) if lang == "en" else (lambda p: p["label_fr"])

    for p in view.periods:
        events.append(
            {
                "id": f"auto:data_due:{p['code']}",
                "auto": True,
                "kind": "data_due",
                "start": p["data_due"],
                "end": p["data_due"],
                "period": p["code"],
                "label": label(p),
            }
        )
        events.append(
            {
                "id": f"auto:report_due:{p['code']}",
                "auto": True,
                "kind": "report_due",
                "start": p["report_due"],
                "end": p["report_due"],
                "period": p["code"],
                "label": label(p),
                "done": bool(p.get("reported_at")),
            }
        )

    has_entry = bool(view.entry)
    units = view.units()
    subs = list(view.subs.values())
    received = ("submitted", "review", "validated", "locked")
    for p in view.periods:
        ended = p["end"] < day
        if not ended:
            continue
        # Data expected and not received, from a week before it is due.
        if has_entry and p["data_due"] <= (date.fromisoformat(day) + timedelta(days=SOON)).isoformat():
            for u in units:
                sub = reception.find(view, p["code"], u["place_id"], u["partner_id"])
                if sub is None or sub["status"] not in received:
                    tasks.append(
                        {
                            "id": f"auto:chase:{p['code']}:{monitoring.unit_key(u['place_id'], u['partner_id'])}",
                            "auto": True,
                            "kind": "chase",
                            "due": p["data_due"],
                            "period": p["code"],
                            "label": label(p),
                            "unit": u,
                            "unit_name": _unit_name(view, u, lang),
                            "submission_id": sub["id"] if sub else None,
                        }
                    )
        # The report of the period, until it is marked as sent.
        if not p.get("reported_at"):
            tasks.append(
                {
                    "id": f"auto:report:{p['code']}",
                    "auto": True,
                    "kind": "report",
                    "due": p["report_due"],
                    "period": p["code"],
                    "label": label(p),
                }
            )

    for s in subs:
        per = next((p for p in view.periods if p["code"] == s["period"]), None)
        if per is None:
            continue
        if s["status"] in ("submitted", "review"):
            due = (
                date.fromisoformat(max(per["data_due"], (s.get("submitted_at") or day)[:10]))
                + timedelta(days=VERIFY_DAYS)
            ).isoformat()
            tasks.append(
                {
                    "id": f"auto:verify:{s['id']}",
                    "auto": True,
                    "kind": "verify",
                    "due": due,
                    "period": s["period"],
                    "label": label(per),
                    "submission_id": s["id"],
                    "unit_name": _unit_name(view, s, lang),
                }
            )
        if s["status"] == "returned":
            tasks.append(
                {
                    "id": f"auto:returned:{s['id']}",
                    "auto": True,
                    "kind": "returned",
                    "due": per["data_due"],
                    "period": s["period"],
                    "label": label(per),
                    "submission_id": s["id"],
                    "unit_name": _unit_name(view, s, lang),
                    "comment": s.get("comment", ""),
                }
            )

    # Gaps to explain: indicators late in a period whose report is still to send.
    if has_entry and view.periods:
        gaps = {(g["indicator_id"], g["period"]) for g in view.p.records("gap_comment")}
        open_periods = [i for i, p in enumerate(view.periods) if p["end"] < day and not p.get("reported_at")]
        for i in open_periods[-2:]:
            p = view.periods[i]
            track = reception.track_all(view, {"period": p["code"], "today": day})
            for row in track["rows"]:
                if row["status"] == "late" and (row["indicator_id"], p["code"]) not in gaps:
                    ind = next(x for x in view.entry if x["id"] == row["indicator_id"])
                    tasks.append(
                        {
                            "id": f"auto:gap:{p['code']}:{ind['id']}",
                            "auto": True,
                            "kind": "gap",
                            "due": p["report_due"],
                            "period": p["code"],
                            "label": label(p),
                            "indicator_id": ind["id"],
                            "indicator": ind["name"],
                        }
                    )

    # Indicator sheets to complete (section M4).
    for ind in view.indicators:
        missing = []
        if not (ind.get("definition") or "").strip():
            missing.append("definition")
        if not (ind.get("source") or "").strip():
            missing.append("source")
        if ind.get("target") is None:
            missing.append("target")
        if reception.is_entry(ind) and monitoring.baseline(ind) is None:
            missing.append("baseline")
        if missing:
            tasks.append(
                {
                    "id": f"auto:sheet:{ind['id']}",
                    "auto": True,
                    "kind": "sheet",
                    "due": "",
                    "indicator_id": ind["id"],
                    "indicator": ind["name"],
                    "missing": missing,
                }
            )

    # Data quality reviews more than a year old (section M7).
    a_year_ago = (date.fromisoformat(day) - timedelta(days=365)).isoformat()
    for ind in view.indicators:
        reviews = view.p.records("quality_review", ind["id"])
        if reviews and max(r["date"] for r in reviews) < a_year_ago:
            last = max(r["date"] for r in reviews)
            tasks.append(
                {
                    "id": f"auto:dqa:{ind['id']}",
                    "auto": True,
                    "kind": "dqa",
                    "due": (date.fromisoformat(last) + timedelta(days=365)).isoformat(),
                    "indicator_id": ind["id"],
                    "indicator": ind["name"],
                }
            )

    _registers(view.p, day, events, tasks)

    for t in tasks:
        t["priority"] = "high" if t["due"] and t["due"] < day else ("low" if t["kind"] == "sheet" else "normal")
        t["status"] = "todo"
    return {"events": events, "tasks": tasks}


def _registers(p: Project, day: str, events: list[dict[str, Any]], tasks: list[dict[str, Any]]) -> None:
    """Deadlines and tasks from the work plan, evaluations, feedback, recommendations,
    risks and meetings (modules M9, M10 and M11)."""
    from . import registers as rg
    from . import workplan

    soon = (date.fromisoformat(day) + timedelta(days=SOON)).isoformat()
    for a in p.records("activity"):
        if a.get("start") and a.get("end") and a["status"] != "cancelled":
            events.append(
                {
                    "id": f"auto:activity:{a['id']}",
                    "auto": True,
                    "kind": "milestone" if a.get("milestone") else "activity",
                    "start": a["end"] if a.get("milestone") else a["start"],
                    "end": a["end"],
                    "name": a["title"],
                    "activity_id": a["id"],
                    "done": a["status"] == "done",
                }
            )
        late = workplan.lateness(a, day)
        if late:
            tasks.append(
                {
                    "id": f"auto:{late}:{a['id']}",
                    "auto": True,
                    "kind": f"activity_{late}",
                    "due": a["end"] if late == "late_end" else a["start"],
                    "name": a["title"],
                    "activity_id": a["id"],
                    "assignee": a.get("responsible", ""),
                }
            )

    for ev in p.records("evaluation"):
        for step in rg.EVAL_STEPS:
            st = ev["steps"][step]
            if not st["date"]:
                continue
            events.append(
                {
                    "id": f"auto:eval:{ev['id']}:{step}",
                    "auto": True,
                    "kind": "evaluation_step",
                    "start": st["date"],
                    "end": st["date"],
                    "name": ev["title"],
                    "step": step,
                    "evaluation_id": ev["id"],
                    "done": st["done"],
                }
            )
            if not st["done"] and st["date"] <= soon:
                tasks.append(
                    {
                        "id": f"auto:eval:{ev['id']}:{step}",
                        "auto": True,
                        "kind": "evaluation_step",
                        "due": st["date"],
                        "name": ev["title"],
                        "step": step,
                        "evaluation_id": ev["id"],
                    }
                )

    cats = rg.categories(p.meta())
    for f in p.records("feedback"):
        if f["status"] not in rg.FEEDBACK_OPEN:
            continue
        tasks.append(
            {
                "id": f"auto:feedback:{f['id']}",
                "auto": True,
                "kind": "feedback",
                "due": rg.feedback_deadline(f, cats),
                # A sensitive case is named by its category only.
                "name": "" if f["sensitive"] else f["summary"],
                "category": f["category"],
                "feedback_id": f["id"],
            }
        )

    for r in p.records("recommendation"):
        if r["response"] == "rejected":
            continue
        for act in r["actions"]:
            if act["status"] == "done":
                continue
            if act["due"]:
                events.append(
                    {
                        "id": f"auto:rec:{act['id']}",
                        "auto": True,
                        "kind": "recommendation_due",
                        "start": act["due"],
                        "end": act["due"],
                        "name": act["text"],
                        "recommendation_id": r["id"],
                    }
                )
            tasks.append(
                {
                    "id": f"auto:rec:{act['id']}",
                    "auto": True,
                    "kind": "recommendation",
                    "due": act["due"],
                    "name": act["text"],
                    "recommendation_id": r["id"],
                    "assignee": act["responsible"],
                }
            )

    for r in p.records("risk"):
        due = rg.risk_review_due(r)
        if not due:
            continue
        events.append(
            {
                "id": f"auto:risk:{r['id']}",
                "auto": True,
                "kind": "risk_review",
                "start": due,
                "end": due,
                "name": r["title"],
                "risk_id": r["id"],
            }
        )
        if due <= soon:
            tasks.append(
                {
                    "id": f"auto:risk:{r['id']}",
                    "auto": True,
                    "kind": "risk_review",
                    "due": due,
                    "name": r["title"],
                    "risk_id": r["id"],
                    "assignee": r.get("responsible", ""),
                }
            )

    from . import team_rpc

    old = team_rpc.purgeable(p, day)
    if old:
        tasks.append({"id": "auto:privacy", "auto": True, "kind": "privacy", "due": day, "name": str(len(old))})

    for m in p.records("meeting"):
        for d in m["decisions"]:
            if d["as_task"] and d["status"] != "done":
                tasks.append(
                    {
                        "id": f"auto:decision:{d['id']}",
                        "auto": True,
                        "kind": "decision",
                        "due": d["due"],
                        "name": d["text"],
                        "meeting_id": m["id"],
                        "assignee": d["responsible"],
                    }
                )


def _sort_tasks(tasks: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rank = {"high": 0, "normal": 1, "low": 2}
    return sorted(tasks, key=lambda t: (t.get("due") or "9999", rank.get(t.get("priority", "normal"), 1)))


def agenda(p: Project, start: str, end: str, lang: str = "fr", day: str | None = None) -> dict[str, Any]:
    """Events and tasks between two dates (tasks without date are left out)."""
    day = day or reception.today()
    view = reception.View(p)
    d = derived(view, day, lang)
    events = [e for e in d["events"] if start <= e["start"][:10] <= end]
    for e in p.records("event"):
        if e["start"][:10] <= end and e["end"][:10] >= start:
            events.append({**e, "auto": False})
    tasks = [t for t in d["tasks"] if t["due"] and start <= t["due"] <= end]
    for t in p.records("task"):
        if t["due"] and start <= t["due"][:10] <= end:
            tasks.append({**t, "auto": False})
    events.sort(key=lambda e: e["start"])
    return {"events": events, "tasks": _sort_tasks(tasks)}


def today(p: Project, lang: str = "fr", day: str | None = None) -> dict[str, Any]:
    """What to do on this project (section M2). Empty lists when nothing is to do."""
    day = day or reception.today()
    view = reception.View(p)
    d = derived(view, day, lang)
    manual = [{**t, "auto": False} for t in p.records("task") if t["status"] != "done"]
    horizon = (date.fromisoformat(day) + timedelta(days=60)).isoformat()
    deadlines = [
        {**e, "days": (date.fromisoformat(e["start"][:10]) - date.fromisoformat(day)).days}
        for e in d["events"]
        if day <= e["start"][:10] <= horizon and not e.get("done")
    ]
    deadlines.sort(key=lambda e: e["start"])
    upcoming = [
        {**e, "auto": False}
        for e in p.records("event")
        if day <= e["start"][:10] <= (date.fromisoformat(day) + timedelta(days=7)).isoformat()
        or e["start"][:10] <= day <= e["end"][:10]
    ]
    # Open alerts of the submissions not validated yet.
    just = set(reception.justified(p))
    alerts = 0
    for s in view.subs.values():
        if s["status"] in monitoring.EDITABLE:
            alerts += len([a for a in reception.alerts(view, s) if a["severity"] != "info" and a["key"] not in just])
    late = []
    if view.periods and view.entry:
        track = reception.track_all(view, {"today": day})
        names = {i["id"]: i["name"] for i in view.entry}
        late = [
            {
                "indicator_id": r["indicator_id"],
                "indicator": names[r["indicator_id"]],
                "period": r["period"],
                "rate": r["rate_to_date"],
            }
            for r in track["rows"]
            if r["status"] == "late"
        ]
    since = p.meta().get("previous_open", "")
    changes = []
    for c in reception.changes_since(view, since):
        c["unit_name"] = _unit_name(view, c, lang)
        per = next((x for x in view.periods if x["code"] == c["period"]), None)
        c["label"] = (per["label_en"] if lang == "en" else per["label_fr"]) if per else c["period"]
        changes.append(c)
    from . import registers_rpc

    reg = registers_rpc.state(p, day)
    late_activities = [
        {"id": a["id"], "title": a["title"], "late": a["late"], "end": a["end"], "progress": a["progress"]}
        for a in reg["activities"]
        if a["late"]
    ]
    overdue_feedback = [
        {
            "id": f["id"],
            "summary": "" if f["sensitive"] else f["summary"],
            "category": f["category"],
            "deadline": f["deadline"],
        }
        for f in reg["feedback"]
        if f["overdue"]
    ]
    overdue_recommendations = [
        {"id": r["id"], "text": r["text"], "late": len(r["late_actions"])}
        for r in reg["recommendations"]
        if r["late_actions"]
    ]
    return {
        "late_activities": late_activities,
        "overdue_feedback": overdue_feedback,
        "overdue_recommendations": overdue_recommendations,
        "day": day,
        "since": since,
        "changes": changes,
        "deadlines": deadlines[:8],
        "events": sorted(upcoming, key=lambda e: e["start"]),
        "tasks": _sort_tasks(d["tasks"] + manual),
        "alerts": alerts,
        "late": late,
    }


# ----- iCalendar ---------------------------------------------------------------------------------


def _ics_escape(text: str) -> str:
    return text.replace("\\", "\\\\").replace(";", "\\;").replace(",", "\\,").replace("\n", "\\n")


def _ics_date(value: str) -> tuple[str, str]:
    if "T" in value:
        return "", datetime.fromisoformat(value).strftime("%Y%m%dT%H%M00")
    return ";VALUE=DATE", value.replace("-", "")


def to_ics(project_name: str, events: list[dict[str, Any]], titles: dict[str, str]) -> str:
    """An iCalendar file of the events, for Outlook or Google Calendar."""
    lines = ["BEGIN:VCALENDAR", "VERSION:2.0", "PRODID:-//SuiviEvalLab//Agenda//FR", "CALSCALE:GREGORIAN"]
    stamp = datetime.now().strftime("%Y%m%dT%H%M%SZ")
    for e in events:
        title = e.get("title") or titles.get(e["kind"], e["kind"]).format(period=e.get("label", ""))
        start_p, start = _ics_date(e["start"])
        end_value = e.get("end") or e["start"]
        if "T" not in end_value:
            end_value = (date.fromisoformat(end_value[:10]) + timedelta(days=1)).isoformat()
        end_p, end = _ics_date(end_value)
        lines += [
            "BEGIN:VEVENT",
            f"UID:{e.get('id', uuid.uuid4().hex)}@suivievallab",
            f"DTSTAMP:{stamp}",
            f"DTSTART{start_p}:{start}",
            f"DTEND{end_p}:{end}",
            f"SUMMARY:{_ics_escape(f'{project_name}: {title}')}",
        ]
        if e.get("place"):
            lines.append(f"LOCATION:{_ics_escape(e['place'])}")
        if e.get("note"):
            lines.append(f"DESCRIPTION:{_ics_escape(e['note'])}")
        lines.append("END:VEVENT")
    lines.append("END:VCALENDAR")
    # Lines of at most 75 octets, continued with a space (RFC 5545).
    out = []
    for line in lines:
        while len(line.encode("utf-8")) > 75:
            cut = 75
            while len(line[:cut].encode("utf-8")) > 75:
                cut -= 1
            out.append(line[:cut])
            line = " " + line[cut:]
        out.append(line)
    return "\r\n".join(out) + "\r\n"


def _ics_value(raw: str) -> str:
    return raw.replace("\\n", "\n").replace("\\N", "\n").replace("\\,", ",").replace("\\;", ";").replace("\\\\", "\\")


def from_ics(text: str) -> list[dict[str, Any]]:
    """Events of an iCalendar file, as event specs."""
    unfolded = re.sub(r"\r?\n[ \t]", "", text)
    out = []
    current: dict[str, str] | None = None
    for line in unfolded.splitlines():
        if line == "BEGIN:VEVENT":
            current = {}
        elif line == "END:VEVENT" and current is not None:
            out.append(current)
            current = None
        elif current is not None and ":" in line:
            name, value = line.split(":", 1)
            current[name.split(";", 1)[0].upper()] = value

    def when(v: str | None) -> str | None:
        if not v:
            return None
        v = v.rstrip("Z")
        if "T" in v:
            return datetime.strptime(v[:15], "%Y%m%dT%H%M%S").isoformat(timespec="minutes")
        return date(int(v[:4]), int(v[4:6]), int(v[6:8])).isoformat()

    events = []
    for e in out[:2000]:
        start = when(e.get("DTSTART"))
        if not start or not e.get("SUMMARY"):
            continue
        end = when(e.get("DTEND")) or start
        if "T" not in end and "T" not in start and end > start:
            end = (date.fromisoformat(end) - timedelta(days=1)).isoformat()  # DTEND of a day is exclusive
        events.append(
            {
                "title": _ics_value(e["SUMMARY"])[:300],
                "kind": "other",
                "start": start,
                "end": end,
                "place": _ics_value(e.get("LOCATION", ""))[:200],
                "note": _ics_value(e.get("DESCRIPTION", ""))[:4000],
            }
        )
    return events
