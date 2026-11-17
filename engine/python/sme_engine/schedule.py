# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 GAYI Komi Selassi and SANOUSSI Moudjibou

"""Project profile and reporting calendar.

The profile says who funds the project, who runs it, where, and from when to when.
The calendar cuts the project into reporting periods (months, quarters, half-years,
years or periods typed by hand). Each period carries the date its data is due and
the date its report is due, and is either open or locked once its figures are
final. Targets, data, tasks and the agenda all hang on these periods.

Profile, kept as JSON in the project metadata under "profile":

    {"code": "PRJ-01", "summary": "...", "start": "2026-01-01", "end": "2028-12-31",
     "frequency": "quarterly", "fiscal_start_month": 1, "data_due_days": 10,
     "report_due_days": 30, "donors": [{"name": "...", "agreement": "...",
     "frequency": "semiannual"}], "implementer": "...", "partners_note": "...",
     "countries": ["Togo"], "sectors": ["health"], "currency": "XOF", "budget": 0,
     "manager": "...", "color": "#2f6f6a", "place_levels": ["Région", "Préfecture"]}

Period:

    {"code": "T1-2026", "start": "2026-01-01", "end": "2026-03-31", "data_due": "...",
     "report_due": "...", "state": "open" | "locked", "label_fr": "...", "label_en": "..."}
"""

from __future__ import annotations

import calendar
import json
import re
from datetime import date, timedelta
from typing import Any

from .rpc import INVALID_PARAMS, RpcError

FREQUENCIES = {"monthly": 1, "quarterly": 3, "semiannual": 6, "annual": 12}
STATES = ("open", "locked")
COLOR = re.compile(r"^#[0-9a-fA-F]{6}$")
MAX_PERIODS = 240

_MONTHS_FR = ("janv.", "févr.", "mars", "avr.", "mai", "juin", "juil.", "août", "sept.", "oct.", "nov.", "déc.")
_MONTHS_EN = ("Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec")


def _err(message: str, key: str = "profile_invalid", **info: Any) -> RpcError:
    return RpcError(message, INVALID_PARAMS, data={"key": key, **info})


def parse_date(value: Any, name: str) -> date:
    if not isinstance(value, str):
        raise _err(f"{name} must be a date", "date_invalid", field=name)
    try:
        return date.fromisoformat(value.strip()[:10])
    except ValueError:
        raise _err(f"{name} is not a valid date: {value}", "date_invalid", field=name) from None


def _str(value: Any, max_len: int = 200) -> str:
    return str(value or "").strip()[:max_len]


def _strings(value: Any, max_items: int = 50) -> list[str]:
    if not isinstance(value, list):
        return []
    out = []
    for item in value[:max_items]:
        text = _str(item, 120)
        if text and text not in out:
            out.append(text)
    return out


def _int(value: Any, lo: int, hi: int, default: int) -> int:
    try:
        n = int(value)
    except (TypeError, ValueError):
        return default
    return min(max(n, lo), hi)


# ----- profile -----------------------------------------------------------------


def default_profile() -> dict[str, Any]:
    return {
        "code": "",
        "summary": "",
        "start": "",
        "end": "",
        "frequency": "quarterly",
        "fiscal_start_month": 1,
        "data_due_days": 10,
        "report_due_days": 30,
        "donors": [],
        "implementer": "",
        "countries": [],
        "sectors": [],
        "currency": "",
        "budget": 0,
        "manager": "",
        "color": "#2f6f6a",
        "place_levels": ["Région", "District", "Commune", "Village"],
        # Who reports each period: the whole project, each partner, each place of a
        # level, or each partner in each of its places (monitoring.units).
        "reporting_by": "project",
        "reporting_level": 0,
        # Share of the target to date from which an indicator is on track.
        "on_track": 0.9,
    }


def validate_profile(spec: Any) -> dict[str, Any]:
    if not isinstance(spec, dict):
        raise _err("The profile must be an object")
    out = default_profile()
    out["code"] = _str(spec.get("code"), 40)
    out["summary"] = _str(spec.get("summary"), 4000)
    for key in ("start", "end"):
        if spec.get(key):
            out[key] = parse_date(spec[key], key).isoformat()
    if out["start"] and out["end"] and out["end"] < out["start"]:
        raise _err("The project ends before it starts", "dates_order")
    freq = spec.get("frequency", "quarterly")
    if freq not in FREQUENCIES:
        raise _err(f"Unknown frequency: {freq}", "frequency_invalid")
    out["frequency"] = freq
    out["fiscal_start_month"] = _int(spec.get("fiscal_start_month"), 1, 12, 1)
    out["data_due_days"] = _int(spec.get("data_due_days"), 0, 180, 10)
    out["report_due_days"] = _int(spec.get("report_due_days"), 0, 365, 30)
    donors = []
    for d in spec.get("donors") or []:
        if isinstance(d, dict) and _str(d.get("name")):
            f = d.get("frequency") if d.get("frequency") in FREQUENCIES else ""
            donors.append({"name": _str(d.get("name")), "agreement": _str(d.get("agreement"), 80), "frequency": f})
    out["donors"] = donors[:20]
    out["implementer"] = _str(spec.get("implementer"))
    out["countries"] = _strings(spec.get("countries"))
    out["sectors"] = _strings(spec.get("sectors"))
    out["currency"] = _str(spec.get("currency"), 8).upper()
    try:
        out["budget"] = max(0.0, float(spec.get("budget") or 0))
    except (TypeError, ValueError):
        raise _err("The budget must be a number", "budget_invalid") from None
    out["manager"] = _str(spec.get("manager"))
    color = _str(spec.get("color"), 7)
    out["color"] = color if COLOR.match(color) else "#2f6f6a"
    levels = _strings(spec.get("place_levels"), 6)
    out["place_levels"] = levels or default_profile()["place_levels"]
    how = spec.get("reporting_by", "project")
    out["reporting_by"] = how if how in ("project", "partner", "place", "partner_place") else "project"
    out["reporting_level"] = _int(spec.get("reporting_level"), 0, len(out["place_levels"]) - 1, 0)
    try:
        share = float(spec.get("on_track", 0.9))
    except (TypeError, ValueError):
        share = 0.9
    out["on_track"] = min(max(share, 0.5), 1.0)
    return out


def profile_from_meta(meta: dict[str, str]) -> dict[str, Any]:
    raw = meta.get("profile")
    if raw:
        try:
            return validate_profile(json.loads(raw))
        except (ValueError, RpcError):
            pass
    return default_profile()


# ----- periods -------------------------------------------------------------------


def _add_months(d: date, months: int) -> date:
    m = d.month - 1 + months
    y = d.year + m // 12
    m = m % 12 + 1
    return date(y, m, min(d.day, calendar.monthrange(y, m)[1]))


def _labels(start: date, frequency: str, fiscal_start: int) -> tuple[str, str, str]:
    """Code, French label and English label of a period."""
    months = FREQUENCIES[frequency]
    # Fiscal year named after the calendar year it starts in, or both years when it spans two.
    fy_start = start.year if start.month >= fiscal_start else start.year - 1
    fy = str(fy_start) if fiscal_start == 1 else f"{fy_start}-{str(fy_start + 1)[2:]}"
    rank = ((start.month - fiscal_start) % 12) // months + 1
    if frequency == "monthly":
        fr = f"{_MONTHS_FR[start.month - 1]} {start.year}"
        en = f"{_MONTHS_EN[start.month - 1]} {start.year}"
        code = f"{start.year}-{start.month:02d}"
    elif frequency == "quarterly":
        fr, en, code = f"T{rank} {fy}", f"Q{rank} {fy}", f"T{rank}-{fy}"
    elif frequency == "semiannual":
        fr, en, code = f"S{rank} {fy}", f"H{rank} {fy}", f"S{rank}-{fy}"
    else:
        fr, en, code = f"Année {fy}", f"Year {fy}", f"A-{fy}"
    return code, fr, en


def generate(profile: dict[str, Any]) -> list[dict[str, Any]]:
    """Periods from the start to the end of the project, aligned on the fiscal year.

    The first and last periods are cut to the project dates: a project starting on
    15 February has a first quarter running from 15 February to 31 March.
    """
    if not profile.get("start") or not profile.get("end"):
        raise _err("Set the start and end dates of the project first", "dates_required")
    start = date.fromisoformat(profile["start"])
    end = date.fromisoformat(profile["end"])
    frequency = profile["frequency"]
    months = FREQUENCIES[frequency]
    fiscal = profile["fiscal_start_month"]
    # First boundary on or before the start: periods begin on fiscal months.
    back = ((start.month - fiscal) % 12) % months
    cursor = _add_months(date(start.year, start.month, 1), -back)
    out = []
    i = 0
    while cursor <= end:
        nxt = _add_months(cursor, months)
        p_start = max(cursor, start)
        p_end = min(nxt - timedelta(days=1), end)
        code, fr, en = _labels(cursor, frequency, fiscal)
        out.append(
            {
                "code": code,
                "label_fr": fr,
                "label_en": en,
                "start": p_start.isoformat(),
                "end": p_end.isoformat(),
                "data_due": (p_end + timedelta(days=profile["data_due_days"])).isoformat(),
                "report_due": (p_end + timedelta(days=profile["report_due_days"])).isoformat(),
                "state": "open",
            }
        )
        cursor = nxt
        i += 1
        if i > MAX_PERIODS:
            raise _err("Too many periods: choose a longer frequency", "periods_too_many")
    return out


def validate_period(spec: Any) -> dict[str, Any]:
    """A period typed or edited by hand."""
    if not isinstance(spec, dict):
        raise _err("The period must be an object", "period_invalid")
    start = parse_date(spec.get("start"), "start")
    end = parse_date(spec.get("end"), "end")
    if end < start:
        raise _err("The period ends before it starts", "dates_order")
    code = _str(spec.get("code"), 30) or start.isoformat()
    out = {
        "code": code,
        "label_fr": _str(spec.get("label_fr"), 60) or code,
        "label_en": _str(spec.get("label_en"), 60) or _str(spec.get("label_fr"), 60) or code,
        "start": start.isoformat(),
        "end": end.isoformat(),
        "data_due": parse_date(spec.get("data_due") or end.isoformat(), "data_due").isoformat(),
        "report_due": parse_date(spec.get("report_due") or end.isoformat(), "report_due").isoformat(),
        "state": spec.get("state") if spec.get("state") in STATES else "open",
    }
    return out


def check_overlaps(periods: list[dict[str, Any]]) -> None:
    ordered = sorted(periods, key=lambda p: p["start"])
    for a, b in zip(ordered, ordered[1:], strict=False):
        if b["start"] <= a["end"]:
            raise _err(f"Periods {a['code']} and {b['code']} overlap", "periods_overlap", a=a["code"], b=b["code"])
    codes = [p["code"] for p in periods]
    if len(set(codes)) != len(codes):
        raise _err("Two periods have the same code", "period_code_duplicate")


def period_of(periods: list[dict[str, Any]], day: str) -> dict[str, Any] | None:
    for p in periods:
        if p["start"] <= day <= p["end"]:
            return p
    return None
