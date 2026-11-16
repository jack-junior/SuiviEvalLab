# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 GAYI Komi Selassi and SANOUSSI Moudjibou

"""Targets of an indicator, by reporting period.

One record per indicator and period, plus an optional end of project target
(period "total"). A target that changes keeps its history with the reason given,
because donors ask why a target was revised and when.

    {"period": "T1-2026", "value": 120, "history": [{"value": 100, "at": "...", "reason": "..."}]}
"""

from __future__ import annotations

import math
from datetime import UTC, datetime
from typing import Any

from .rpc import INVALID_PARAMS, RpcError

TOTAL = "total"


def _err(message: str, key: str, **info: Any) -> RpcError:
    return RpcError(message, INVALID_PARAMS, data={"key": key, **info})


def number(value: Any) -> float:
    if isinstance(value, bool):
        raise _err("The target must be a number", "target_invalid")
    if isinstance(value, str):
        value = value.strip().replace(" ", "").replace(" ", "").replace(",", ".")
    try:
        n = float(value)
    except (TypeError, ValueError):
        raise _err("The target must be a number", "target_invalid") from None
    if not math.isfinite(n):
        raise _err("The target must be a number", "target_invalid")
    return n


def set_value(
    current: dict[str, Any] | None, period: str, value: Any, reason: Any, period_codes: set[str]
) -> dict[str, Any] | None:
    """The new record, or None when nothing changes.

    The first value needs no reason; any later change does.
    """
    if period != TOTAL and period not in period_codes:
        raise _err(f"Unknown period: {period}", "period_not_found", period=period)
    n = number(value)
    reason = str(reason or "").strip()[:500]
    if current is None:
        return {"period": period, "value": n, "history": []}
    if current["value"] == n:
        return None
    if not reason:
        raise _err("Give the reason for changing this target", "target_reason_required")
    history = [
        *current.get("history", []),
        {"value": current["value"], "at": datetime.now(UTC).isoformat(timespec="seconds"), "reason": reason},
    ]
    return {"period": period, "value": n, "history": history[-50:]}


def cumulative(records: list[dict[str, Any]], period_order: list[str]) -> dict[str, float]:
    """Running sum of targets along the calendar, for indicators counted over time."""
    by_period = {r["period"]: r["value"] for r in records if r["period"] != TOTAL}
    out: dict[str, float] = {}
    running = 0.0
    for code in period_order:
        if code in by_period:
            running += by_period[code]
            out[code] = running
    return out
