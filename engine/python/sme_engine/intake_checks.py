# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 GAYI Komi Selassi and SANOUSSI Moudjibou

"""Checks run on a submission as it is received (section M7).

Each check gives an alert with a severity:
- blocking: the submission cannot be validated until it is corrected;
- review: to correct, or to justify in writing before validation;
- info: shown, nothing required.

Alerts are computed from the data each time, so an alert disappears as soon as
its cause is corrected. Only the written justifications are stored, under the
alert key, which names the submission, the check, the indicator and the cell.
"""

from __future__ import annotations

from itertools import product
from typing import Any

from . import monitoring as m

JUMP = 3.0  # a value more than three times, or less than a third of, the previous period


def _alert(sub_id: str, check: str, severity: str, ind_id: str = "", cats: str = "", **info: Any) -> dict[str, Any]:
    return {
        "key": f"{sub_id}:{check}:{ind_id}:{cats}",
        "check": check,
        "severity": severity,
        "indicator_id": ind_id,
        "cats": cats,
        "info": info,
    }


def cells_expected(ind: dict[str, Any], disaggregations: dict[str, dict[str, Any]]) -> list[str]:
    """The cells of the finest level: every combination of the indicator's breakdowns."""
    keys = [k for k in ind.get("breakdowns") or [] if k in disaggregations]
    if not keys:
        return []
    lists = [[c["code"] for c in disaggregations[k]["categories"]] + ["_na"] for k in keys]
    return [m.cats_key(dict(zip(keys, combo, strict=True))) for combo in product(*lists)]


def run(
    sub: dict[str, Any],
    inds: list[dict[str, Any]],
    cells: dict[str, dict[str, tuple]],
    previous: dict[str, float | None],
    disaggregations: dict[str, dict[str, Any]],
    period: dict[str, Any] | None,
) -> list[dict[str, Any]]:
    """Alerts of one submission. `cells` is {indicator: {cats: (value, num, den)}};
    `previous` the value of the same unit in the period before, by indicator."""
    out: list[dict[str, Any]] = []
    sid = sub["id"]
    for ind in inds:
        mine = cells.get(ind["id"], {})
        k = m.kind(ind)
        filled = {key: c for key, c in mine.items() if any(x is not None for x in c)}
        if not filled:
            out.append(_alert(sid, "missing", "review", ind["id"]))
            continue
        expected = cells_expected(ind, disaggregations)
        if expected and not any(key for key in filled):
            out.append(_alert(sid, "missing_breakdown", "review", ind["id"]))
        for key, (v, num, den) in filled.items():
            if k == "fraction":
                if num is not None and den is not None and num > den and ind.get("unit") == "percent":
                    out.append(_alert(sid, "num_gt_den", "blocking", ind["id"], key, num=num, den=den))
                if (num is None) != (den is None):
                    out.append(_alert(sid, "half_fraction", "blocking", ind["id"], key))
                if den == 0:
                    out.append(_alert(sid, "zero_den", "blocking", ind["id"], key))
                if ind.get("unit") == "percent" and v is not None and not 0 <= v <= 1:
                    out.append(_alert(sid, "out_of_range", "blocking", ind["id"], key, value=v))
            if k == "count" and v is not None and v < 0:
                out.append(_alert(sid, "negative", "blocking", ind["id"], key, value=v))
            bounds = ind.get("bounds") or {}
            lo, hi = bounds.get("min"), bounds.get("max")
            if v is not None and ((lo is not None and v < lo) or (hi is not None and v > hi)):
                out.append(_alert(sid, "bounds", "review", ind["id"], key, value=v, min=lo, max=hi))
        # The total against the sum of its cells (counts and fractions with their parts).
        if "" in filled and any(key for key in filled):
            total = m.Measure(*filled[""])
            parts = m.combine(ind, [m.Measure(*c) for key, c in filled.items() if key])
            if k == "count" and parts.ok and total.ok and abs(parts.value - total.value) > 1e-9:  # type: ignore[operator]
                out.append(_alert(sid, "total_mismatch", "review", ind["id"], total=total.value, parts=parts.value))
            if k == "fraction" and total.num is not None and parts.num is not None:
                if abs(total.num - parts.num) > 1e-9 or abs((total.den or 0) - (parts.den or 0)) > 1e-9:
                    out.append(
                        _alert(
                            sid,
                            "total_mismatch",
                            "review",
                            ind["id"],
                            total=total.num,
                            parts=parts.num,
                        )
                    )
        # Plausibility against the period before, for the same reporting unit.
        now = m.submission_measure(ind, filled, {})
        before = previous.get(ind["id"])
        if now.ok and before not in (None, 0) and k in ("count", "fraction", "mean"):
            ratio = now.value / before  # type: ignore[operator]
            if ratio > JUMP or ratio < 1 / JUMP:
                out.append(_alert(sid, "jump", "info", ind["id"], value=now.value, previous=before))
    if period and sub.get("submitted_at") and sub["submitted_at"][:10] > period["data_due"]:
        out.append(_alert(sid, "late", "info", due=period["data_due"], at=sub["submitted_at"][:10]))
    return out


def blocking(alerts: list[dict[str, Any]], justified: set[str]) -> list[dict[str, Any]]:
    """Alerts that prevent validation: blocking ones, and review ones not justified."""
    return [
        a for a in alerts if a["severity"] == "blocking" or (a["severity"] == "review" and a["key"] not in justified)
    ]
