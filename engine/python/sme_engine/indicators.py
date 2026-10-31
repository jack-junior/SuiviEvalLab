"""Indicators attached to the results framework.

An indicator is computed from a dataset column:
- percent: share of observations whose `column` takes one of `success_values`;
- mean:    mean of the numeric `column`;
- count:   number of observations meeting the conditions, or sum of a column
           (with sampling weights, the estimated number in the population);
- ratio:   sum of `numerator` / sum of `denominator`, times `multiplier`.
Percent and count indicators may combine several conditions (all or any).
Baseline and endline values come from the datasets of those rounds when they
exist; otherwise from the values typed by the user. Targets are always typed.
Percent values are stored as shares (0.62 for 62 %).
"""

from __future__ import annotations

from typing import Any

from .rpc import INVALID_PARAMS, RpcError

UNITS = ("percent", "mean", "count", "ratio")
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


def _conditions(spec: dict[str, Any]) -> list[dict[str, Any]]:
    """Conditions [{column, values}] of a percent or count indicator.

    Older indicators store a single condition as `column` and `success_values`.
    """
    raw = spec.get("conditions")
    if not raw and spec.get("column"):
        raw = [{"column": spec.get("column"), "values": spec.get("success_values") or []}]
    if raw is None:
        return []
    if not isinstance(raw, list) or len(raw) > 6:
        raise _err("conditions must be a list of at most 6 items", "invalid_params")
    out = []
    for c in raw:
        if not isinstance(c, dict):
            raise _err("Invalid condition", "invalid_params")
        column = c.get("column")
        values = c.get("values") or []
        if not isinstance(column, str) or not column.strip():
            continue
        if not isinstance(values, list) or not all(isinstance(v, str) for v in values):
            raise _err("Condition values must be text", "invalid_params")
        out.append({"column": column.strip(), "values": values})
    return out


def validate(spec: dict[str, Any]) -> dict[str, Any]:
    unit = spec.get("unit", "percent")
    if unit not in UNITS:
        raise _err(f"unit must be one of {UNITS}", "invalid_params")
    direction = spec.get("direction", "increase")
    if direction not in DIRECTIONS:
        raise _err(f"direction must be one of {DIRECTIONS}", "invalid_params")
    combine = spec.get("combine", "all")
    if combine not in ("all", "any"):
        raise _err("combine must be all or any", "invalid_params")
    count_mode = spec.get("count_mode", "rows")
    if count_mode not in ("rows", "sum"):
        raise _err("count_mode must be rows or sum", "invalid_params")
    conditions = _conditions(spec) if unit in ("percent", "count") else []
    column = _text(spec, "column", max_len=300) or None
    if unit == "percent" or (unit == "count" and count_mode == "rows"):
        column = conditions[0]["column"] if conditions else None
    multiplier = _num(spec, "multiplier")
    out = {
        "name": _text(spec, "name", required=True, max_len=300),
        "definition": _text(spec, "definition"),
        "unit": unit,
        "direction": direction,
        # `column` is the main column: first condition, mean or sum column, or numerator.
        "column": column if unit != "ratio" else (_text(spec, "numerator", max_len=300) or None),
        "success_values": conditions[0]["values"] if conditions and unit == "percent" else [],
        "conditions": conditions,
        "combine": combine,
        "count_mode": count_mode,
        "numerator": _text(spec, "numerator", max_len=300) or None if unit == "ratio" else None,
        "denominator": _text(spec, "denominator", max_len=300) or None if unit == "ratio" else None,
        "multiplier": multiplier if unit == "ratio" and multiplier not in (None, 0) else 1.0,
        "disaggregation": _text(spec, "disaggregation", max_len=300) or None,
        "disaggregation2": _text(spec, "disaggregation2", max_len=300) or None,
        "baseline_manual": _num(spec, "baseline_manual"),
        "target": _num(spec, "target"),
        "unit_label": _text(spec, "unit_label", max_len=60),
        "source": _text(spec, "source", max_len=500),
    }
    if out["disaggregation2"] and not out["disaggregation"]:
        out["disaggregation"], out["disaggregation2"] = out["disaggregation2"], None
    for name in ("baseline_manual", "target"):
        v = out[name]
        if unit == "percent" and v is not None and not 0 <= v <= 1:
            raise _err(f"{name} must be between 0 and 1 for a percentage", "invalid_share")
    return out


def ready(ind: dict[str, Any]) -> bool:
    """True when the calculation rule is complete enough to compute."""
    unit = ind["unit"]
    if unit == "percent":
        return bool(ind.get("conditions")) and all(c["values"] for c in ind["conditions"])
    if unit == "count":
        if ind.get("count_mode") == "sum":
            return bool(ind.get("column"))
        return bool(ind.get("conditions")) and all(c["values"] for c in ind["conditions"])
    if unit == "ratio":
        return bool(ind.get("numerator") and ind.get("denominator"))
    return bool(ind.get("column"))


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
