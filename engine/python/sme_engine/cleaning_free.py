# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 GAYI Komi Selassi and SANOUSSI Moudjibou

"""Free cleaning steps: formulas, filters, cells corrected by hand, R scripts.

- formula:  a column (new or existing) computed by a formula (formula.py).
- filter:   keep, or drop, the rows where a formula is true.
- edit:     cells corrected in the data table, each identified by its row
            number in the file (the `row` shown in the table) and its column.
- r_script: R code that receives the table as `data` and returns it changed.
            Only run when the code is trusted on this computer (trust.py);
            otherwise the step is paused and the rest of the journal runs.
"""

from __future__ import annotations

from typing import Any, Protocol

import polars as pl

from . import formula
from .cleaning_more import NAME
from .rpc import INVALID_PARAMS, RpcError

KINDS = ("formula", "filter", "edit", "r_script")
ROW = "__row"
MAX_CELLS = 20_000
MAX_CODE = 50_000


class Context(Protocol):
    def trusted(self, code: str) -> bool: ...

    def run_r(self, df: pl.DataFrame, code: str) -> tuple[pl.DataFrame, str]: ...


def _err(message: str, key: str = "rule_invalid") -> RpcError:
    return RpcError(message, INVALID_PARAMS, data={"key": key})


def validate(rule: dict[str, Any], columns: list[str], out: dict[str, Any]) -> dict[str, Any]:
    kind = rule["kind"]
    if kind == "formula":
        target = rule.get("target")
        if not isinstance(target, str) or not NAME.match(target):
            raise _err("The column name uses letters, digits, _ and . and starts with a letter")
        expr = rule.get("expression")
        formula.check(expr, columns)
        out["target"], out["expression"] = target, expr.strip()
    elif kind == "filter":
        expr = rule.get("expression")
        formula.check(expr, columns, condition=True)
        out["expression"] = expr.strip()
        out["action"] = "drop" if rule.get("action") == "drop" else "keep"
    elif kind == "edit":
        cells = rule.get("cells")
        if not isinstance(cells, list) or not cells or len(cells) > MAX_CELLS:
            raise _err(f"Give 1 to {MAX_CELLS} corrected cells")
        seen: dict[tuple[int, str], dict[str, Any]] = {}
        for c in cells:
            if not isinstance(c, dict) or not isinstance(c.get("row"), int) or isinstance(c.get("row"), bool):
                raise _err("Each corrected cell needs its row number")
            col = c.get("column")
            if not isinstance(col, str) or col not in columns:
                raise RpcError(f"Unknown column: {col}", INVALID_PARAMS, data={"key": "column_not_found"})
            value = c.get("value")
            old = c.get("old")
            seen[(c["row"], col)] = {
                "row": c["row"],
                "column": col,
                "value": None if value is None or value == "" else str(value)[:2000],
                "old": None if old is None or old == "" else str(old)[:2000],
            }
        out["cells"] = list(seen.values())
    elif kind == "r_script":
        code = rule.get("code")
        if not isinstance(code, str) or not code.strip():
            raise _err("Write the R code")
        if len(code) > MAX_CODE:
            raise _err("The R code is too long")
        out["code"] = code.replace("\r\n", "\n")
    return out


def new_columns(rule: dict[str, Any]) -> list[str]:
    return [rule["target"]] if rule["kind"] == "formula" else []


def apply(df: pl.DataFrame, rule: dict[str, Any], ctx: Context | None) -> tuple[pl.DataFrame, dict[str, Any]]:
    """Apply one free step. The table carries the row numbers in ROW. Returns the table and the effect."""
    kind = rule["kind"]
    columns = [c for c in df.columns if c != ROW]
    if kind in ("formula", "filter"):
        try:
            if kind == "formula":
                expr = formula.value_expr(rule["expression"], columns)
                target = rule["target"]
                before = df[target] if target in df.columns else None
                df = df.with_columns(expr.alias(target))
                after = df[target]
                if before is None:
                    changed = int(after.is_not_null().sum())
                else:
                    changed = int(((after != before).fill_null(False) | (after.is_null() != before.is_null())).sum())
                return df, {"cells_changed": changed}
            mask = formula.condition_expr(rule["expression"], columns)
            before = df.height
            df = df.filter(mask if rule["action"] == "keep" else ~mask)
            return df, {"rows_removed": before - df.height}
        except formula.FormulaError as exc:
            # A column the formula reads no longer exists (rule moved, file changed): the step waits.
            return df, {"applied": False, "error": exc.data.get("reason"), "error_info": exc.info}
    if kind == "edit":
        changed = 0
        by_column: dict[str, list[dict[str, Any]]] = {}
        for c in rule["cells"]:
            by_column.setdefault(c["column"], []).append(c)
        rows = df[ROW]
        for col, cells in by_column.items():
            if col not in df.columns:
                continue
            mapping = {c["row"]: c["value"] for c in cells}
            hit = rows.is_in(list(mapping))
            n = int(hit.sum())
            if not n:
                continue
            changed += n
            df = df.with_columns(
                pl.col(ROW)
                .replace_strict(
                    list(mapping), list(mapping.values()), default=pl.col(col).cast(pl.Utf8), return_dtype=pl.Utf8
                )
                .alias(col)
            )
        return df, {"cells_changed": changed}
    if kind == "r_script":
        if ctx is None or not ctx.trusted(rule["code"]):
            return df, {"applied": False, "paused": True}
        before = df.height
        try:
            out, log = ctx.run_r(df, rule["code"])
        except RpcError as exc:
            return df, {"applied": False, "error": "r_script_failed", "message": str(exc)[:4000]}
        if ROW not in out.columns:
            out = out.with_columns(pl.int_range(1, out.height + 1, dtype=pl.Int64).alias(ROW))
        added = [c for c in out.columns if c not in df.columns and c != ROW]
        return out, {
            "rows_removed": max(before - out.height, 0),
            "rows_added": max(out.height - before, 0),
            "columns_added": added,
            "columns_removed": [c for c in df.columns if c not in out.columns],
            "log": log[-4000:],
        }
    return df, {}


WORDS = {
    "fr": {
        "formula": "Variable « {target} » = {expression}",
        "filter_keep": "Garder seulement les lignes où {expression}",
        "filter_drop": "Retirer les lignes où {expression}",
        "edit": "{n} cellule(s) corrigée(s) à la main : {cells}",
        "edit_cell": "ligne {row}, « {column} » : {old} → {value}",
        "missing": "manquant",
        "r_script": "Script R ({lines} lignes)",
    },
    "en": {
        "formula": 'Variable "{target}" = {expression}',
        "filter_keep": "Keep only the rows where {expression}",
        "filter_drop": "Remove the rows where {expression}",
        "edit": "{n} cell(s) corrected by hand: {cells}",
        "edit_cell": 'row {row}, "{column}": {old} → {value}',
        "missing": "missing",
        "r_script": "R script ({lines} lines)",
    },
}


def describe(rule: dict[str, Any], lang: str) -> str:
    w = WORDS[lang]
    kind = rule["kind"]
    if kind == "formula":
        return w["formula"].format(target=rule["target"], expression=rule["expression"])
    if kind == "filter":
        return w[f"filter_{rule['action']}"].format(expression=rule["expression"])
    if kind == "edit":
        shown = rule["cells"][:5]
        cells = "; ".join(
            w["edit_cell"].format(
                row=c["row"], column=c["column"], old=c["old"] or w["missing"], value=c["value"] or w["missing"]
            )
            for c in shown
        )
        if len(rule["cells"]) > 5:
            cells += " ..."
        return w["edit"].format(n=len(rule["cells"]), cells=cells)
    if kind == "r_script":
        return w["r_script"].format(lines=rule["code"].count("\n") + 1)
    return kind
