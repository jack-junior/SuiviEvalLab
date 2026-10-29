"""Indicators attached to the results framework.

An indicator is computed from a dataset column:
- percent: share of observations whose `column` takes one of `success_values`;
- mean:    mean of the numeric `column`.
Baseline and endline values come from the datasets of those rounds when they
exist; otherwise from the values typed by the user. Targets are always typed.
Percent values are stored as shares (0.62 for 62 %).
"""

from __future__ import annotations

from typing import Any

from .rpc import INVALID_PARAMS, RpcError

UNITS = ("percent", "mean")
DIRECTIONS = ("increase", "decrease")


def _err(message: str, key: str) -> RpcError:
    return RpcError(message, INVALID_PARAMS, data={"key": key})


def _text(spec: dict[str, Any], name: str, required: bool = False, max_len: int = 2000) -> str:
    v = spec.get(name, "")
    if v is None:
        v = ""
    if not isinstance(v, str):
        raise _err(f"{name} must be text", "invalid_params")
    v = v.strip()
    if required and not v:
        raise _err(f"{name} is required", "field_required")
    if len(v) > max_len:
        raise _err(f"{name} is too long", "field_too_long")
    return v


def _num(spec: dict[str, Any], name: str) -> float | None:
    v = spec.get(name)
    if v is None or v == "":
        return None
    if isinstance(v, bool) or not isinstance(v, (int, float)):
        raise _err(f"{name} must be a number", "invalid_number")
    return float(v)


def validate(spec: dict[str, Any]) -> dict[str, Any]:
    unit = spec.get("unit", "percent")
    if unit not in UNITS:
        raise _err(f"unit must be one of {UNITS}", "invalid_params")
    direction = spec.get("direction", "increase")
    if direction not in DIRECTIONS:
        raise _err(f"direction must be one of {DIRECTIONS}", "invalid_params")
    success = spec.get("success_values") or []
    if not isinstance(success, list) or not all(isinstance(v, str) for v in success):
        raise _err("success_values must be a list of text values", "invalid_params")
    out = {
        "name": _text(spec, "name", required=True, max_len=300),
        "definition": _text(spec, "definition"),
        "unit": unit,
        "direction": direction,
        "column": _text(spec, "column", max_len=300) or None,
        "success_values": success if unit == "percent" else [],
        "disaggregation": _text(spec, "disaggregation", max_len=300) or None,
        "baseline_manual": _num(spec, "baseline_manual"),
        "target": _num(spec, "target"),
        "unit_label": _text(spec, "unit_label", max_len=60),
        "source": _text(spec, "source", max_len=500),
    }
    for name in ("baseline_manual", "target"):
        v = out[name]
        if unit == "percent" and v is not None and not 0 <= v <= 1:
            raise _err(f"{name} must be between 0 and 1 for a percentage", "invalid_share")
    return out


def achievement(baseline: float | None, current: float | None, target: float | None) -> float | None:
    """Share of the planned change achieved: (current - baseline) / (target - baseline)."""
    if baseline is None or current is None or target is None or target == baseline:
        return None
    return (current - baseline) / (target - baseline)


def status(
    rate: float | None, current: float | None = None, target: float | None = None, direction: str = "increase"
) -> str:
    """Thresholds of the conventions: 90 % achieved, 60 % in progress, below is late.

    A value already at or beyond the target, in the planned direction, is achieved
    whatever the baseline (the rate is meaningless when the baseline already beat it).
    """
    if current is not None and target is not None:
        if (direction == "increase" and current >= target) or (direction == "decrease" and current <= target):
            return "achieved"
    if rate is None:
        return "unknown"
    if rate >= 0.9:
        return "achieved"
    if rate >= 0.6:
        return "on_track"
    return "late"
