"""Routine monitoring indicators: values entered period by period.

Many output and activity indicators do not come from a survey but from registers,
attendance lists or monthly reports: "people trained", "latrines built",
"attendance rate of the centres". Their values are typed (or pasted from Excel)
for each period, with an optional planned value and an optional breakdown into
categories (women and men, for example).

Values of one period:

    {"period": "2026-T1", "end": "2026-03-31", "achieved": 320, "planned": 300,
     "by": {"Femmes": 180, "Hommes": 140}, "note": ""}

How periods add up (`aggregation` of the indicator):
- sum:  cumulative total, the usual case for counts (people trained to date);
- last: the latest value, for rates and stocks (attendance rate this quarter);
- mean: the mean of the periods.

The status compares the value to date with the target and, when planned values
are given, with what was planned to date: 90 % of the planned value or more is
on track, less is late. These are counts and records, not samples: there is no
confidence interval and nothing to estimate, so no R call is needed.
"""

from __future__ import annotations

import re
from datetime import date
from typing import Any

from .rpc import INVALID_PARAMS, RpcError

AGGREGATIONS = ("sum", "last", "mean")
MAX_PERIODS = 400
MAX_CATEGORIES = 12


def _err(message: str, key: str = "routine_invalid") -> RpcError:
    return RpcError(message, INVALID_PARAMS, data={"key": key})


def _num(v: Any, name: str) -> float | None:
    if v is None or v == "":
        return None
    if isinstance(v, bool):
        raise _err(f"{name} must be a number")
    if isinstance(v, str):
        v = v.replace(" ", "").replace(" ", "").replace(" ", "").replace(",", ".")
    try:
        x = float(v)
    except (TypeError, ValueError):
        raise _err(f"{name} must be a number: {v}") from None
    if x != x or x in (float("inf"), float("-inf")):
        raise _err(f"{name} must be a number")
    return x


def validate_values(raw: Any, categories: list[str], percent: bool) -> list[dict[str, Any]]:
    """Clean the rows typed or pasted by the user. Percent values may be typed as 45 or 0.45."""
    if not isinstance(raw, list) or len(raw) > MAX_PERIODS:
        raise _err(f"values must be a list of at most {MAX_PERIODS} periods")
    out, seen = [], set()
    for i, row in enumerate(raw, start=1):
        if not isinstance(row, dict):
            raise _err(f"Row {i} is invalid")
        period = str(row.get("period") or "").strip()[:40]
        if not period:
            raise _err(f"Row {i}: give the period")
        if period in seen:
            raise _err(f"Period {period} appears twice", "routine_duplicate_period")
        seen.add(period)
        end = str(row.get("end") or "").strip()
        if end:
            try:
                end = date.fromisoformat(end).isoformat()
            except ValueError:
                raise _err(f"Row {i}: the end date must be written YYYY-MM-DD") from None
        by_raw = row.get("by") or {}
        by: dict[str, float] = {}
        if isinstance(by_raw, dict):
            for cat in categories:
                v = _num(by_raw.get(cat), f"{period}, {cat}")
                if v is not None:
                    by[cat] = v
        achieved = _num(row.get("achieved"), f"{period}, achieved")
        planned = _num(row.get("planned"), f"{period}, planned")
        if achieved is None and by:
            achieved = sum(by.values()) if not percent else None
        if percent:
            achieved, planned = (None if x is None else (x / 100 if x > 1 else x) for x in (achieved, planned))
            by = {k: (v / 100 if v > 1 else v) for k, v in by.items()}
        out.append(
            {
                "period": period,
                "end": end or None,
                "achieved": achieved,
                "planned": planned,
                "by": by,
                "note": str(row.get("note") or "").strip()[:300],
            }
        )
    # Chronological order: by end date when given, else as typed.
    if all(r["end"] for r in out):
        out.sort(key=lambda r: r["end"])
    return out


def _agg(values: list[float], how: str) -> float | None:
    if not values:
        return None
    if how == "sum":
        return float(sum(values))
    if how == "last":
        return float(values[-1])
    return float(sum(values) / len(values))


def analyse(ind: dict[str, Any], rows: list[dict[str, Any]]) -> dict[str, Any]:
    """Periods with running totals, value to date, planned to date, achievement and status."""
    how = ind.get("aggregation") or "sum"
    done = [r for r in rows if r.get("achieved") is not None]
    periods = []
    acc_a: list[float] = []
    acc_p: list[float] = []
    for r in rows:
        if r.get("achieved") is not None:
            acc_a.append(r["achieved"])
        if r.get("planned") is not None:
            acc_p.append(r["planned"])
        periods.append(
            {
                **r,
                "to_date": _agg(acc_a, how) if r.get("achieved") is not None else None,
                "planned_to_date": _agg(acc_p, how) if r.get("planned") is not None else None,
            }
        )
    current = _agg([r["achieved"] for r in done], how)
    last_done = done[-1]["period"] if done else None
    # Planned up to the last period with an achieved value.
    planned_rows = []
    for r in rows:
        if r.get("planned") is not None:
            planned_rows.append(r["planned"])
        if r["period"] == last_done:
            break
    planned_to_date = _agg(planned_rows, how) if last_done else None
    by_total: dict[str, float] = {}
    for cat in ind.get("categories") or []:
        vals = [r["by"][cat] for r in done if cat in r.get("by", {})]
        v = _agg(vals, how)
        if v is not None:
            by_total[cat] = v

    target = ind.get("target")
    baseline = ind.get("baseline_manual")
    if baseline is None and how == "sum":
        baseline = 0.0  # a cumulative count starts from zero
    decrease = ind.get("direction") == "decrease"
    achievement = None
    if current is not None and target is not None and baseline is not None and target != baseline:
        achievement = (current - baseline) / (target - baseline)
    pace = None
    if current is not None and planned_to_date:
        pace = (planned_to_date / current if current else None) if decrease else current / planned_to_date

    status = "unknown"
    if current is not None and target is not None and (current <= target if decrease else current >= target):
        status = "achieved"
    elif pace is not None:
        status = "on_track" if pace >= 0.9 else "late"
    elif achievement is not None:
        status = "achieved" if achievement >= 0.9 else "on_track" if achievement >= 0.6 else "late"

    return {
        "source": "routine",
        "aggregation": how,
        "periods": periods,
        "baseline": baseline,
        "baseline_source": "manual" if ind.get("baseline_manual") is not None else ("zero" if how == "sum" else None),
        "current": current,
        "current_period": last_done,
        "current_round": None,
        "target": target,
        "planned_to_date": planned_to_date,
        "pace": pace,
        "achievement": achievement,
        "status": status,
        "by_total": by_total,
    }


def parse_paste(text: str, categories: list[str]) -> list[dict[str, Any]]:
    """Rows pasted from Excel: period, end date, achieved, planned, then one column per category.

    A first line of headers is skipped when its value columns are not numbers."""
    rows = []
    for line in text.replace("\r\n", "\n").split("\n"):
        if not line.strip():
            continue
        cells = [c.strip() for c in line.split("\t")]
        cells += [""] * (4 + len(categories) - len(cells))
        if not rows and cells[2] and not re.match(r"^-?[\d\s.,  ]+%?$", cells[2]):
            continue  # header line
        rows.append(
            {
                "period": cells[0],
                "end": cells[1],
                "achieved": cells[2].rstrip("%"),
                "planned": cells[3].rstrip("%"),
                "by": {c: cells[4 + i].rstrip("%") for i, c in enumerate(categories)},
            }
        )
    return rows


TEXT = {
    "fr": {
        "how": {"sum": "en cumul", "last": "à la dernière période", "mean": "en moyenne sur les périodes"},
        "value": "{name} : {value} {how} au terme de la période {period}.",
        "target": "Cela représente {rate} de la cible de {target}.",
        "reached": "La cible de {target} est atteinte.",
        "planned": "Il était prévu {planned} à cette date : le rythme est de {pace} du prévu.",
        "by": "Répartition : {parts}.",
        "none": "Aucune valeur saisie pour cet indicateur de suivi.",
        "col_period": "Période",
        "col_achieved": "Réalisé",
        "col_planned": "Prévu",
        "col_to_date": "Réalisé à date",
        "col_planned_to_date": "Prévu à date",
        "method": (
            "Indicateur de suivi de routine : valeurs relevées période par période dans les registres et "
            "rapports du projet ({how}), sans échantillonnage ni intervalle de confiance."
        ),
    },
    "en": {
        "how": {"sum": "cumulatively", "last": "in the latest period", "mean": "on average over the periods"},
        "value": "{name}: {value} {how} at the end of period {period}.",
        "target": "This is {rate} of the target of {target}.",
        "reached": "The target of {target} is reached.",
        "planned": "{planned} was planned by this date: progress is {pace} of the plan.",
        "by": "Breakdown: {parts}.",
        "none": "No value has been entered for this monitoring indicator.",
        "col_period": "Period",
        "col_achieved": "Achieved",
        "col_planned": "Planned",
        "col_to_date": "Achieved to date",
        "col_planned_to_date": "Planned to date",
        "method": (
            "Routine monitoring indicator: values recorded period by period from the project's registers "
            "and reports ({how}), without sampling or confidence interval."
        ),
    },
}


def sentences(ind: dict[str, Any], an: dict[str, Any], lang: str, f: Any) -> list[str]:
    """The reading of a routine indicator, in the report language (`f` is report.Fmt)."""
    t = TEXT[lang]
    unit = ind["unit"]
    if an.get("current") is None:
        return [t["none"]]
    out = [
        t["value"].format(
            name=ind["name"],
            value=f.value(an["current"], unit),
            how=t["how"][an["aggregation"]],
            period=an["current_period"],
        )
    ]
    if an["status"] == "achieved" and an.get("target") is not None:
        out.append(t["reached"].format(target=f.value(an["target"], unit)))
    elif an.get("achievement") is not None:
        out.append(t["target"].format(rate=f.pct(an["achievement"], 0), target=f.value(an["target"], unit)))
    if an.get("pace") is not None:
        out.append(t["planned"].format(planned=f.value(an["planned_to_date"], unit), pace=f.pct(an["pace"], 0)))
    if an.get("by_total"):
        parts = ", ".join(f"{k} {f.value(v, unit)}" for k, v in an["by_total"].items())
        out.append(t["by"].format(parts=parts))
    return out
