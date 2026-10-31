"""Cleaning journal: rules applied in order to a copy of the raw data.

The raw table is never modified. Each rule is a small JSON object, so the journal
can be replayed, reordered, switched off, and printed in the report. There is no
free-text expression language and nothing is evaluated as code.

Rule kinds
- duplicates: keep the first row of each group of identical values in `columns`.
- recode:     replace the values listed in `from` by `to` in `column` (`to` null = missing).
- range:      set numbers of `column` outside [min, max] to missing.
- exclude:    drop the rows where `column` takes one of `values` (null in values = missing).

Advanced kinds (new variables, classes, conditions, consistency checks, text and
dates) are in cleaning_more.py.
"""

from __future__ import annotations

from typing import Any

import polars as pl

from . import cleaning_more
from .rpc import INVALID_PARAMS, RpcError

BASIC = ("duplicates", "recode", "range", "exclude")
KINDS = BASIC + cleaning_more.KINDS


def _err(message: str, key: str) -> RpcError:
    return RpcError(message, INVALID_PARAMS, data={"key": key})


def _str_list(value: Any, name: str, allow_null: bool = False) -> list[str | None]:
    if not isinstance(value, list) or not value:
        raise _err(f"{name} must be a non-empty list", "rule_invalid")
    out: list[str | None] = []
    for v in value:
        if v is None and allow_null:
            out.append(None)
        elif isinstance(v, (str, int, float)) and not isinstance(v, bool):
            out.append(str(v))
        else:
            raise _err(f"{name} contains an invalid value", "rule_invalid")
    return out


def _number(value: Any) -> float | None:
    if value is None or value == "":
        return None
    if isinstance(value, bool):
        raise _err("min and max must be numbers", "rule_invalid")
    try:
        return float(value)
    except (TypeError, ValueError):
        raise _err("min and max must be numbers", "rule_invalid") from None


def validate(rule: dict[str, Any], columns: list[str]) -> dict[str, Any]:
    kind = rule.get("kind")
    if kind not in KINDS:
        raise _err(f"kind must be one of {KINDS}", "rule_invalid")
    note = rule.get("note") or ""
    if not isinstance(note, str):
        raise _err("note must be text", "rule_invalid")
    out: dict[str, Any] = {"kind": kind, "note": note.strip()[:500], "enabled": rule.get("enabled", True) is not False}
    if kind in cleaning_more.KINDS:
        return cleaning_more.validate(rule, columns, out)

    def column(name: Any) -> str:
        if not isinstance(name, str) or name not in columns:
            raise _err(f"Unknown column: {name}", "column_not_found")
        return name

    if kind == "duplicates":
        out["columns"] = [column(c) for c in _str_list(rule.get("columns"), "columns")]
    elif kind == "recode":
        out["column"] = column(rule.get("column"))
        out["from"] = _str_list(rule.get("from"), "from")
        to = rule.get("to")
        out["to"] = None if to is None or to == "" else str(to)
    elif kind == "range":
        out["column"] = column(rule.get("column"))
        out["min"], out["max"] = _number(rule.get("min")), _number(rule.get("max"))
        if out["min"] is None and out["max"] is None:
            raise _err("Give a minimum, a maximum or both", "rule_invalid")
        if out["min"] is not None and out["max"] is not None and out["min"] > out["max"]:
            raise _err("The minimum is above the maximum", "rule_invalid")
    elif kind == "exclude":
        out["column"] = column(rule.get("column"))
        out["values"] = _str_list(rule.get("values"), "values", allow_null=True)
    return out


def new_columns(rule: dict[str, Any]) -> list[str]:
    """Columns a rule adds to the cleaned table (none for the basic kinds)."""
    return cleaning_more.new_columns(rule) if rule["kind"] in cleaning_more.KINDS else []


def missing_to_null(df: pl.DataFrame, na_values: list[str]) -> pl.DataFrame:
    """Turn the dataset's missing-value codes into real nulls."""
    return df.with_columns(pl.when(pl.all().is_in(na_values)).then(None).otherwise(pl.all()).name.keep())


def apply(df: pl.DataFrame, rules: list[dict[str, Any]]) -> tuple[pl.DataFrame, list[dict[str, Any]]]:
    """Apply the enabled rules in order. Returns the cleaned table and one effect per rule."""
    effects = []
    for rule in rules:
        before = df.height
        changed = 0
        if not rule.get("enabled", True):
            effects.append({"id": rule.get("id"), "applied": False, "rows_removed": 0, "cells_changed": 0})
            continue
        kind = rule["kind"]
        if kind in cleaning_more.KINDS:
            df, removed, changed = cleaning_more.apply(df, rule)
            effects.append({"id": rule.get("id"), "applied": True, "rows_removed": removed, "cells_changed": changed})
            continue
        if kind == "duplicates":
            df = df.unique(subset=rule["columns"], keep="first", maintain_order=True)
        elif kind == "recode":
            col = rule["column"]
            if col in df.columns:
                hit = pl.col(col).is_in([v for v in rule["from"] if v is not None])
                changed = int(df.select(hit.sum()).item())
                df = df.with_columns(
                    pl.when(hit).then(pl.lit(rule["to"], dtype=pl.Utf8)).otherwise(pl.col(col)).alias(col)
                )
        elif kind == "range":
            col = rule["column"]
            if col in df.columns:
                num = pl.col(col).cast(pl.Float64, strict=False)
                out = pl.lit(False)
                if rule["min"] is not None:
                    out = out | (num < rule["min"])
                if rule["max"] is not None:
                    out = out | (num > rule["max"])
                out = out.fill_null(False)
                changed = int(df.select(out.sum()).item())
                df = df.with_columns(pl.when(out).then(None).otherwise(pl.col(col)).alias(col))
        elif kind == "exclude":
            col = rule["column"]
            if col in df.columns:
                values = [v for v in rule["values"] if v is not None]
                drop = pl.col(col).is_in(values)
                if None in rule["values"]:
                    drop = drop | pl.col(col).is_null()
                df = df.filter(~drop.fill_null(False))
        effects.append(
            {"id": rule.get("id"), "applied": True, "rows_removed": before - df.height, "cells_changed": changed}
        )
    return df, effects
