# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 GAYI Komi Selassi and SANOUSSI Moudjibou

"""Progress of the work plan and of the budget (module M9).

Three measures of progress are put side by side, each between 0 and 1:

- time: share of the project duration gone by;
- physical: progress of the activities, each weighted by its planned length
  (cancelled activities left out; sub-activities count through their parent
  only when the parent has none of its own);
- financial: amount spent over the amount planned.

The budget is a simple follow-up, not accounting: planned amounts by budget
line and period, expenses typed or read from an accounting export.
"""

from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import Any

from . import schedule
from .project import Project
from .registers import _err

CLOSED = ("done", "cancelled")


def _days(a: str, b: str) -> int:
    return (date.fromisoformat(b) - date.fromisoformat(a)).days + 1


def expected(act: dict[str, Any], day: str) -> float | None:
    """Share of the activity that should be done by this day, from its planned dates."""
    if not act.get("start") or not act.get("end"):
        return None
    if day < act["start"]:
        return 0.0
    if day >= act["end"]:
        return 1.0
    return _days(act["start"], day) / _days(act["start"], act["end"])


def lateness(act: dict[str, Any], day: str) -> str:
    """ "" when on time, else why the activity is late."""
    if act["status"] in CLOSED:
        return ""
    if act.get("end") and act["end"] < day:
        return "late_end"
    if act.get("start") and act["start"] < day and act["status"] in ("not_started", "postponed"):
        return "late_start"
    return ""


def activities_view(p: Project, day: str) -> list[dict[str, Any]]:
    """Activities with what the screens show beside them."""
    acts = p.records("activity")
    kids: dict[str, list[dict[str, Any]]] = {}
    for a in acts:
        if a.get("parent_id"):
            kids.setdefault(a["parent_id"], []).append(a)
    out = []
    for a in acts:
        own = kids.get(a["id"])
        if own and a["status"] not in ("cancelled", "postponed"):
            # A parent follows its sub-activities: progress weighted by their length.
            live = [k for k in own if k["status"] != "cancelled"] or own
            weights = [float(_days(k["start"], k["end"])) if k.get("start") and k.get("end") else 1.0 for k in live]
            progress = sum(w * k["progress"] for w, k in zip(weights, live, strict=True)) / sum(weights)
            states = {k["status"] for k in live}
            status = (
                "done"
                if states == {"done"}
                else "not_started"
                if states <= {"not_started", "postponed"}
                else "in_progress"
            )
            a = {**a, "progress": round(progress, 1), "status": status, "derived": True}
        out.append({**a, "expected": expected(a, day), "late": lateness(a, day)})
    return out


def physical(acts: list[dict[str, Any]], day: str) -> dict[str, Any]:
    parents = {a["parent_id"] for a in acts if a.get("parent_id")}
    weight = done = expect = 0.0
    counted = 0
    for a in acts:
        if a["status"] == "cancelled" or a["id"] in parents:
            continue  # a parent counts through its sub-activities
        w = float(_days(a["start"], a["end"])) if a.get("start") and a.get("end") else 1.0
        weight += w
        done += w * (a["progress"] or 0) / 100
        expect += w * (expected(a, day) or 0)
        counted += 1
    return {
        "activities": counted,
        "physical": done / weight if weight else None,
        "expected": expect / weight if weight else None,
        "late": sum(1 for a in acts if lateness(a, day)),
    }


def budget(p: Project, day: str) -> dict[str, Any]:
    periods = p.records("period")
    started = {x["code"] for x in periods if x["start"] <= day}
    lines = p.records("budget_line")
    expenses = p.records("expense")
    spent: dict[str, float] = {}
    for e in expenses:
        spent[e["line_id"]] = spent.get(e["line_id"], 0.0) + e["amount"]
    rows = []
    for ln in lines:
        planned = sum(ln["planned"].values())
        to_date = sum(v for k, v in ln["planned"].items() if k in started)
        s = spent.get(ln["id"], 0.0)
        rows.append(
            {
                "line_id": ln["id"],
                "planned": planned,
                "planned_to_date": to_date,
                "spent": s,
                "rate": s / planned if planned else None,
                "rate_to_date": s / to_date if to_date else None,
            }
        )
    planned = sum(r["planned"] for r in rows)
    total_spent = sum(r["spent"] for r in rows)
    by_period = []
    for x in periods:
        plan = sum(ln["planned"].get(x["code"], 0.0) for ln in lines)
        out = sum(e["amount"] for e in expenses if x["start"] <= e["date"] <= x["end"])
        if plan or out:
            by_period.append({"period": x["code"], "planned": plan, "spent": out})
    return {
        "lines": rows,
        "planned": planned,
        "planned_to_date": sum(r["planned_to_date"] for r in rows),
        "spent": total_spent,
        "financial": total_spent / planned if planned else None,
        "by_period": by_period,
    }


def summary(p: Project, day: str) -> dict[str, Any]:
    profile = schedule.profile_from_meta(p.meta())
    time = None
    if profile.get("start") and profile.get("end"):
        if day <= profile["start"]:
            time = 0.0
        elif day >= profile["end"]:
            time = 1.0
        else:
            time = _days(profile["start"], day) / _days(profile["start"], profile["end"])
    acts = activities_view(p, day)
    b = budget(p, day)
    phys = physical(acts, day)
    gap = None
    if b["financial"] is not None and phys["physical"] is not None:
        gap = b["financial"] - phys["physical"]
    return {
        "day": day,
        "time": time,
        **phys,
        "budget": b,
        "currency": profile.get("currency", ""),
        # Spending ahead of the work done is the signal a manager looks for.
        "financial_ahead": gap,
    }


# ----- M&E activities from the monitoring plan ---------------------------------------------------


def me_activities(p: Project, lang: str) -> list[dict[str, Any]]:
    """M&E activities the monitoring plan implies, keyed by origin so they are made once."""
    fr = lang != "en"
    out = []
    periods = p.records("period")
    entry = [i for i in p.records("indicator") if i.get("source_type") in ("routine", "secondary", "dhis2")]
    if entry:
        for x in periods:
            label = x["label_fr"] if fr else x["label_en"]
            out.append(
                {
                    "origin": f"collection:{x['code']}",
                    "title": (f"Collecte des données de {label}" if fr else f"Data collection for {label}"),
                    "family": "me",
                    "me_kind": "collection",
                    "start": x["start"],
                    "end": x["data_due"],
                }
            )
            out.append(
                {
                    "origin": f"review:{x['code']}",
                    "title": (f"Revue des données de {label}" if fr else f"Data review for {label}"),
                    "family": "me",
                    "me_kind": "review",
                    "start": x["data_due"],
                    "end": x["report_due"],
                }
            )
    years = sorted({x["start"][:4] for x in periods})
    if entry:
        for y in years:
            out.append(
                {
                    "origin": f"dqa:{y}",
                    "title": (f"Revue de la qualité des données {y}" if fr else f"Data quality review {y}"),
                    "family": "me",
                    "me_kind": "dqa",
                    "start": f"{y}-10-01",
                    "end": f"{y}-11-30",
                }
            )
    for ev in p.records("evaluation"):
        if ev.get("start") and ev.get("end"):
            out.append(
                {
                    "origin": f"evaluation:{ev['id']}",
                    "title": ev["title"],
                    "family": "me",
                    "me_kind": "evaluation",
                    "start": ev["start"],
                    "end": ev["end"],
                }
            )
    return out


# ----- expenses read from an accounting export --------------------------------------------------------


def _amount(value: Any) -> float | None:
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    text = str(value).strip().replace(" ", "").replace(" ", "").replace(" ", "")
    if not text:
        return None
    if "," in text and "." in text:
        text = text.replace(".", "").replace(",", ".") if text.rfind(",") > text.rfind(".") else text.replace(",", "")
    else:
        text = text.replace(",", ".")
    try:
        return float(text)
    except ValueError:
        return None


def _date(value: Any) -> str | None:
    from datetime import datetime

    if value is None:
        return None
    if isinstance(value, datetime):
        return value.date().isoformat()
    if isinstance(value, date):
        return value.isoformat()
    text = str(value).strip()[:19]
    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y", "%d.%m.%Y", "%Y/%m/%d", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M:%S"):
        try:
            return datetime.strptime(text, fmt).date().isoformat()
        except ValueError:
            continue
    return None


def read_expenses(p: Project, path: Path, sheet: str | None, columns: dict[str, str], commit: bool) -> dict[str, Any]:
    """Expenses of an accounting export. Lines are matched by code, then by name."""
    from . import datasets

    for need in ("date", "amount", "line"):
        if not columns.get(need):
            raise _err(f"Choose the column of {need}", "field_required", field=need)
    df = datasets.load(path, sheet)
    missing = [c for c in columns.values() if c and c not in df.columns]
    if missing:
        raise _err("Unknown column", "column_missing", column=missing[0])
    lines = p.records("budget_line")
    by_code = {ln["code"].casefold(): ln["id"] for ln in lines if ln["code"]}
    by_name = {ln["name"].casefold(): ln["id"] for ln in lines}
    existing = {(e["line_id"], e["date"], round(e["amount"], 2), e["ref"]) for e in p.records("expense")}
    ok, unknown_lines, bad, duplicates = [], {}, 0, 0
    for row in df.iter_rows(named=True):
        key = str(row.get(columns["line"]) or "").strip()
        line_id = by_code.get(key.casefold()) or by_name.get(key.casefold())
        amount, day = _amount(row.get(columns["amount"])), _date(row.get(columns["date"]))
        if amount is None or day is None:
            bad += 1
            continue
        if line_id is None:
            unknown_lines[key] = unknown_lines.get(key, 0) + 1
            continue
        ref = str(row.get(columns.get("ref") or "") or "").strip()[:80] if columns.get("ref") else ""
        sig = (line_id, day, round(amount, 2), ref)
        if sig in existing:
            duplicates += 1
            continue
        existing.add(sig)
        label = str(row.get(columns["label"]) or "").strip()[:300] if columns.get("label") else ""
        ok.append({"line_id": line_id, "date": day, "amount": amount, "label": label, "ref": ref})
    if commit:
        for e in ok:
            p.insert_record("expense", e)
    return {
        "rows": df.height,
        "read": len(ok),
        "total": sum(e["amount"] for e in ok),
        "bad": bad,
        "duplicates": duplicates,
        "unknown_lines": [{"line": k, "rows": n} for k, n in sorted(unknown_lines.items(), key=lambda x: -x[1])][:30],
    }
