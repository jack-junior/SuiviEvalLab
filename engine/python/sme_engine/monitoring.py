# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 GAYI Komi Selassi and SANOUSSI Moudjibou

"""Monitoring: values received period by period, and the indicator tracking table.

Values arrive in submissions (envois): one per reporting period and reporting
unit (the whole project, a partner, a place, or a partner in a place). A
submission goes through draft, submitted, under review, returned, validated and
locked. Only validated values count in the tracking table, unless provisional
values are asked for, and they are then marked.

Each value is one row of the `value` table: an indicator, a submission, and
either the total (no category) or one cell of the disaggregation (sex and age,
for instance, crossed at the finest level). Fractions (percentages, rates,
ratios) are entered as numerator and denominator whenever possible, because
they are never added up: numerators and denominators are, then divided
(section 6.2 of the specification). A value given without them is used alone,
and an aggregation that would need it is refused with its reason.

The rules of calculation (types, aggregation in time and across places,
targets to date, achievement and status) are all here, so the tracking table,
the overview, the report and the workspace read the same figures.
"""

from __future__ import annotations

import math
import sqlite3
from collections.abc import Iterable
from dataclasses import dataclass, field
from datetime import date
from typing import Any

from .rpc import INVALID_PARAMS, RpcError

# Indicator types (section 6.1) and how their values are entered and combined.
#   fraction: numerator / denominator x multiplier (percent: share, rate: per base)
#   count:    added up
#   mean:     mean weighted by the number of observations when given
#   level:    a value that does not add up (median, score, scale)
#   milestone: done (1) or not done (0)
KIND = {
    "count": "count",
    "percent": "fraction",
    "rate": "fraction",
    "ratio": "fraction",
    "mean": "mean",
    "median": "level",
    "score": "level",
    "scale": "level",
    "milestone": "milestone",
}
# Aggregation in time: cumulative (sum), last value, mean of the periods, maximum.
TIME_MODES = ("sum", "last", "mean", "max")
STATUSES = ("draft", "submitted", "review", "returned", "validated", "locked")
EDITABLE = ("draft", "submitted", "review", "returned")
CHANNELS = ("entry", "excel", "import", "secondary", "migrated")
REPORTING = ("project", "partner", "place", "partner_place")
ON_TRACK = 0.9


def _err(message: str, key: str, **info: Any) -> RpcError:
    return RpcError(message, INVALID_PARAMS, data={"key": key, **info})


def kind(ind: dict[str, Any]) -> str:
    return KIND.get(ind.get("unit", "count"), "count")


def multiplier(ind: dict[str, Any]) -> float:
    if ind.get("unit") == "percent":
        return 1.0  # shares, shown as percentages
    m = ind.get("multiplier") or 1.0
    return float(m)


def time_mode(ind: dict[str, Any]) -> str:
    mode = ind.get("aggregation")
    if mode in TIME_MODES:
        return mode
    return "sum" if kind(ind) == "count" else "last"


# ----- storage -------------------------------------------------------------------

SCHEMA = """
CREATE TABLE IF NOT EXISTS value (
    id            INTEGER PRIMARY KEY,
    indicator_id  TEXT NOT NULL REFERENCES indicator(id) ON DELETE CASCADE,
    submission_id TEXT NOT NULL,
    period        TEXT NOT NULL,
    place_id      TEXT NOT NULL DEFAULT '',
    partner_id    TEXT NOT NULL DEFAULT '',
    cats          TEXT NOT NULL DEFAULT '',   -- '' for the total, else "age=5-17;sex=f"
    value         REAL,
    numerator     REAL,
    denominator   REAL,
    UNIQUE (submission_id, indicator_id, cats)
);
CREATE INDEX IF NOT EXISTS value_indicator ON value(indicator_id, period);
CREATE INDEX IF NOT EXISTS value_submission ON value(submission_id);
"""


def cats_key(cats: dict[str, str] | None) -> str:
    if not cats:
        return ""
    return ";".join(f"{k}={cats[k]}" for k in sorted(cats))


def cats_dict(key: str) -> dict[str, str]:
    if not key:
        return {}
    return dict(part.split("=", 1) for part in key.split(";"))


def number(v: Any, name: str = "value") -> float | None:
    """A number typed by a person: spaces, non-breaking spaces and a decimal comma accepted."""
    if v is None or v == "":
        return None
    if isinstance(v, bool):
        raise _err(f"{name} must be a number", "value_invalid", field=name)
    if isinstance(v, str):
        v = v.strip().replace(" ", "").replace(" ", "").replace(" ", "").replace(",", ".")
        if v.endswith("%"):
            v = v[:-1]
    try:
        x = float(v)
    except (TypeError, ValueError):
        raise _err(f"{name} must be a number: {v}", "value_invalid", field=name) from None
    if not math.isfinite(x):
        raise _err(f"{name} must be a number", "value_invalid", field=name)
    return x


def clean_cell(ind: dict[str, Any], cell: dict[str, Any]) -> tuple[float | None, float | None, float | None]:
    """(value, numerator, denominator) of a typed cell. A fraction typed with its
    numerator and denominator gets its value computed; a percentage typed alone is
    read as a percentage (45 or 45 %) and kept as a share."""
    k = kind(ind)
    v = number(cell.get("value"))
    num = number(cell.get("numerator"), "numerator") if k in ("fraction", "mean") else None
    den = number(cell.get("denominator"), "denominator") if k in ("fraction", "mean") else None
    if k == "fraction":
        if num is not None and den is not None:
            v = num / den * multiplier(ind) if den else None
        elif v is not None and ind.get("unit") == "percent":
            v = v / 100
    if k == "milestone" and v is not None and v not in (0.0, 1.0):
        raise _err("A milestone is done (1) or not done (0)", "value_invalid")
    return v, num, den


# ----- combining values ----------------------------------------------------------


@dataclass
class Measure:
    """A value with what is needed to combine it with others."""

    value: float | None
    num: float | None = None
    den: float | None = None
    n: int = 1  # rows combined
    reason: str | None = None  # why it could not be computed

    @property
    def ok(self) -> bool:
        return self.value is not None


def combine(ind: dict[str, Any], parts: list[Measure]) -> Measure:
    """Several places, partners or categories into one (section 6.2)."""
    parts = [p for p in parts if p.ok or p.num is not None]
    if not parts:
        return Measure(None, reason="no_data")
    k = kind(ind)
    if len(parts) == 1:
        return parts[0]
    if k == "count":
        return Measure(sum(p.value for p in parts if p.value is not None), n=len(parts))
    if k == "fraction":
        if all(p.num is not None and p.den is not None for p in parts):
            num = sum(p.num for p in parts)  # type: ignore[misc]
            den = sum(p.den for p in parts)  # type: ignore[misc]
            return Measure(num / den * multiplier(ind) if den else None, num, den, len(parts))
        return Measure(None, reason="no_denominator", n=len(parts))
    if k == "mean":
        if all(p.den for p in parts):
            den = sum(p.den for p in parts)  # type: ignore[misc]
            return Measure(sum(p.value * p.den for p in parts) / den, None, den, len(parts))  # type: ignore[operator]
        return Measure(None, reason="no_weights", n=len(parts))
    if k == "milestone":
        return Measure(1.0 if all(p.value == 1 for p in parts) else 0.0, n=len(parts))
    return Measure(None, reason="not_additive", n=len(parts))


def over_time(ind: dict[str, Any], series: list[Measure]) -> Measure:
    """The value to date from the values of the periods so far, by the indicator's mode."""
    done = [m for m in series if m.ok]
    if not done:
        return Measure(None, reason="no_data")
    mode = time_mode(ind)
    k = kind(ind)
    if mode == "last" or k == "milestone":
        return done[-1]
    if mode == "max":
        return max(done, key=lambda m: m.value)  # type: ignore[arg-type,return-value]
    if mode == "mean":
        return Measure(sum(m.value for m in done) / len(done), n=len(done))  # type: ignore[misc]
    # Cumulative.
    if k == "count":
        return Measure(sum(m.value for m in done), n=len(done))  # type: ignore[misc]
    if k == "fraction":
        if all(m.num is not None and m.den is not None for m in done):
            num = sum(m.num for m in done)  # type: ignore[misc]
            den = sum(m.den for m in done)  # type: ignore[misc]
            return Measure(num / den * multiplier(ind) if den else None, num, den, len(done))
        return Measure(None, reason="no_denominator", n=len(done))
    return done[-1]


# ----- reading the store -------------------------------------------------------------


@dataclass
class Scope:
    """Which values to read: validated only or also provisional, and filters."""

    provisional: bool = False
    place_ids: set[str] | None = None  # a place and the places inside it
    partner_id: str | None = None
    cats: dict[str, str] = field(default_factory=dict)  # one category of one disaggregation, or crossed


def counted(sub: dict[str, Any], scope: Scope) -> bool:
    if sub["status"] in ("validated", "locked"):
        return True
    return scope.provisional and sub["status"] in ("submitted", "review", "returned", "draft")


def read_values(
    conn: sqlite3.Connection, indicator_ids: Iterable[str] | None = None
) -> dict[tuple[str, str, str], dict[str, tuple[float | None, float | None, float | None]]]:
    """{(indicator, period, submission): {cats: (value, numerator, denominator)}}."""
    sql = "SELECT indicator_id, period, submission_id, cats, value, numerator, denominator FROM value"
    args: list[Any] = []
    if indicator_ids is not None:
        ids = list(indicator_ids)
        if not ids:
            return {}
        sql += f" WHERE indicator_id IN ({','.join('?' * len(ids))})"
        args = ids
    out: dict[tuple[str, str, str], dict[str, tuple[float | None, float | None, float | None]]] = {}
    for ind_id, period, sub_id, cats, v, num, den in conn.execute(sql, args):
        out.setdefault((ind_id, period, sub_id), {})[cats] = (v, num, den)
    return out


def submission_measure(ind: dict[str, Any], cells: dict[str, tuple], want: dict[str, str]) -> Measure:
    """One submission's value for the whole scope or for one category.

    The total row is used when given; otherwise the cells are combined. For a
    category, the cells that belong to it are combined (all ages of women, say).
    """
    if not want:
        if "" in cells:
            v, num, den = cells[""]
            return Measure(v, num, den)
        parts = [Measure(*c) for key, c in cells.items() if key]
        return combine(ind, parts)
    parts = []
    for key, c in cells.items():
        if not key:
            continue
        d = cats_dict(key)
        if all(d.get(k) == v for k, v in want.items()):
            parts.append(Measure(*c))
    return combine(ind, parts) if parts else Measure(None, reason="no_data")


def period_measures(
    ind: dict[str, Any],
    period_codes: list[str],
    subs: dict[str, dict[str, Any]],
    values: dict[tuple[str, str, str], dict[str, tuple]],
    scope: Scope,
) -> dict[str, tuple[Measure, bool]]:
    """{period: (measure, provisional)} for one indicator, combining the submissions of each period."""
    by_period: dict[str, list[tuple[Measure, bool]]] = {}
    for (ind_id, period, sub_id), cells in values.items():
        if ind_id != ind["id"]:
            continue
        sub = subs.get(sub_id)
        if sub is None or not counted(sub, scope):
            continue
        if scope.partner_id is not None and sub.get("partner_id", "") != scope.partner_id:
            continue
        if scope.place_ids is not None and sub.get("place_id", "") not in scope.place_ids:
            continue
        m = submission_measure(ind, cells, scope.cats)
        by_period.setdefault(period, []).append((m, sub["status"] not in ("validated", "locked")))
    out = {}
    for code in period_codes:
        items = by_period.get(code)
        if items:
            out[code] = (combine(ind, [m for m, _ in items]), any(p for _, p in items))
    return out


# ----- targets, achievement, status -------------------------------------------------------


def _better(ind: dict[str, Any], a: float, b: float) -> bool:
    """a is at or beyond b in the wanted direction."""
    return a <= b if ind.get("direction") == "decrease" else a >= b


def baseline(ind: dict[str, Any]) -> float | None:
    if ind.get("baseline_manual") is not None:
        return float(ind["baseline_manual"])
    if kind(ind) == "count" and time_mode(ind) == "sum":
        return 0.0  # a cumulative count starts from zero
    if kind(ind) == "milestone":
        return 0.0
    return None


def target_to_date(
    ind: dict[str, Any],
    periods: list[dict[str, Any]],
    upto: int,
    by_period: dict[str, float],
    project_start: str | None,
    project_end: str | None,
) -> tuple[float | None, bool]:
    """(target to date, interpolated). `upto` is the index of the selected period.

    Cumulative indicators add the targets of the periods so far; the others take
    the target of the period, or the last one set before it. Without targets by
    period, the target moves in a straight line from the baseline at the start to
    the final target at the end, and is flagged as such (section 6.5).
    """
    final = ind.get("target")
    if by_period:
        if time_mode(ind) == "sum" and kind(ind) == "count":
            return sum(by_period.get(p["code"], 0.0) for p in periods[: upto + 1]), False
        for p in reversed(periods[: upto + 1]):
            if p["code"] in by_period:
                return by_period[p["code"]], False
        return None, False
    if final is None:
        return None, False
    if kind(ind) == "milestone":
        return (final if upto == len(periods) - 1 else None), False
    base = baseline(ind)
    start = project_start or (periods[0]["start"] if periods else None)
    end = project_end or (periods[-1]["end"] if periods else None)
    if base is None or not start or not end or not periods:
        return None, False
    d0, d1 = date.fromisoformat(start), date.fromisoformat(end)
    at = date.fromisoformat(periods[upto]["end"])
    span = (d1 - d0).days
    share = 1.0 if span <= 0 else min(max((at - d0).days / span, 0.0), 1.0)
    return base + (final - base) * share, True


def rate(ind: dict[str, Any], realised: float | None, target: float | None) -> float | None:
    """Achievement rate: realised over target; for a decrease, measured from the baseline."""
    if realised is None or target is None:
        return None
    if ind.get("direction") == "decrease":
        base = baseline(ind)
        if base is None or base == target:
            return None
        return (base - realised) / (base - target)
    if target == 0:
        return None
    return realised / target


def status(
    ind: dict[str, Any],
    to_date: float | None,
    target_now: float | None,
    elapsed: bool,
    threshold: float = ON_TRACK,
) -> str:
    """achieved, on_track, late, not_started, no_data or unknown (no target)."""
    final = ind.get("target")
    if to_date is None:
        return "no_data" if elapsed else "not_started"
    if final is not None and _better(ind, to_date, final):
        return "achieved"
    r = rate(ind, to_date, target_now)
    if r is None:
        return "unknown"
    return "on_track" if r >= threshold else "late"


def _period_rate(ind: dict[str, Any], value: float | None, target: float | None) -> float | None:
    """Achievement of the period against its own target. For a decrease the period
    target is the level to reach, so the rate is measured from the baseline too."""
    return rate(ind, value, target)


def trend(prev: float | None, now: float | None) -> str | None:
    if prev is None or now is None:
        return None
    if abs(now - prev) <= 1e-9 * max(1.0, abs(prev)):
        return "flat"
    return "up" if now > prev else "down"


def selected_period(periods: list[dict[str, Any]], code: str | None, today: str) -> int:
    """Index of the period asked for, else the last period started by today."""
    if code:
        for i, p in enumerate(periods):
            if p["code"] == code:
                return i
        raise _err(f"Unknown period: {code}", "period_not_found", period=code)
    idx = 0
    for i, p in enumerate(periods):
        if p["start"] <= today:
            idx = i
    return idx


def track(
    ind: dict[str, Any],
    periods: list[dict[str, Any]],
    subs: dict[str, dict[str, Any]],
    values: dict[tuple[str, str, str], dict[str, tuple]],
    targets: dict[str, float],
    profile: dict[str, Any],
    scope: Scope,
    upto: int,
    today: str,
    threshold: float = ON_TRACK,
) -> dict[str, Any]:
    """One row of the tracking table, with the series by period."""
    codes = [p["code"] for p in periods]
    measures = period_measures(ind, codes, subs, values, scope)
    series = []
    running: list[Measure] = []
    prev_value = None
    for i, p in enumerate(periods):
        m, provisional = measures.get(p["code"], (Measure(None, reason="no_data"), False))
        running.append(m)
        acc = over_time(ind, running)
        t_now, interp = target_to_date(ind, periods, i, targets, profile.get("start"), profile.get("end"))
        elapsed = p["end"] < today
        series.append(
            {
                "period": p["code"],
                "value": m.value,
                "numerator": m.num,
                "denominator": m.den,
                "reason": m.reason if not m.ok and m.reason != "no_data" else None,
                "provisional": provisional,
                "target": targets.get(p["code"]),
                "to_date": acc.value,
                "target_to_date": t_now,
                "interpolated": interp,
                "rate_to_date": rate(ind, acc.value, t_now),
                "status": status(ind, acc.value, t_now, elapsed, threshold),
                "trend": trend(prev_value, m.value),
            }
        )
        if m.ok:
            prev_value = m.value
    row = series[upto] if series else None
    return {
        "indicator_id": ind["id"],
        "kind": kind(ind),
        "mode": time_mode(ind),
        "baseline": baseline(ind),
        "target": ind.get("target"),
        "period": row["period"] if row else None,
        "value_period": row["value"] if row else None,
        "target_period": row["target"] if row else None,
        "rate_period": _period_rate(ind, row["value"], row["target"]) if row else None,
        "to_date": row["to_date"] if row else None,
        "target_to_date": row["target_to_date"] if row else None,
        "interpolated": row["interpolated"] if row else False,
        "rate_to_date": row["rate_to_date"] if row else None,
        "status": row["status"] if row else "not_started",
        "trend": row["trend"] if row else None,
        "provisional": any(s["provisional"] for s in series[: upto + 1]),
        "reason": next((s["reason"] for s in reversed(series[: upto + 1]) if s["reason"]), None),
        "series": series,
    }


# ----- reporting units and expected submissions --------------------------------------------


def units(
    profile: dict[str, Any], places: list[dict[str, Any]], partners: list[dict[str, Any]]
) -> list[dict[str, str]]:
    """Who reports, for each period: [{"place_id", "partner_id"}]."""
    how = profile.get("reporting_by") or "project"
    level = int(profile.get("reporting_level") or 0)
    if how == "partner" and partners:
        return [{"place_id": "", "partner_id": p["id"]} for p in partners if p.get("role") != "funding"]
    if how == "place" and places:
        return [{"place_id": p["id"], "partner_id": ""} for p in places if p["level"] == level]
    if how == "partner_place" and partners:
        out = []
        by_id = {p["id"]: p for p in places}
        for partner in partners:
            if partner.get("role") == "funding":
                continue
            for pid in partner.get("place_ids") or []:
                if pid in by_id:
                    out.append({"place_id": pid, "partner_id": partner["id"]})
        return out
    return [{"place_id": "", "partner_id": ""}]


def unit_key(place_id: str, partner_id: str) -> str:
    return f"{partner_id}|{place_id}"
