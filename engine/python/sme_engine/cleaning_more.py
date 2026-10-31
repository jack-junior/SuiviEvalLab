"""Advanced cleaning rules: new variables, classes, conditions, consistency checks,
text and dates. Like the basic rules (cleaning.py), each is a small JSON object
interpreted here; nothing typed by the user is evaluated as code.

- compute:     new column from several columns: sum, mean, min, max, difference,
               ratio, or the number of columns taking given values.
- classes:     a number cut into named classes (age groups).
- conditional: set a column (existing or new) to a value, or to missing, where
               conditions hold.
- check:       a consistency check: rows where conditions hold are incoherent;
               flag them in a new column, exclude them, or set a column to missing.
- text:        trim, squeeze spaces, change case, remove accents.
- date:        duration between two date-times (minutes), age in years at a date
               or at another column, or a part of a date (year, month).

Values stay text in the cleaned table, as everywhere else: computed numbers are
written as people type them (12, 12.5).
"""

from __future__ import annotations

import re
from datetime import date
from typing import Any

import polars as pl

from .rpc import INVALID_PARAMS, RpcError

KINDS = ("compute", "classes", "conditional", "check", "text", "date")
COMPUTE_OPS = ("sum", "mean", "min", "max", "difference", "ratio", "count_values")
COND_OPS = ("eq", "ne", "in", "not_in", "lt", "le", "gt", "ge", "missing", "present")
TEXT_OPS = ("trim", "squeeze", "lower", "upper", "title", "accents")
DATE_MODES = ("duration", "age", "year", "month")
CHECK_ACTIONS = ("flag", "exclude", "missing")
NAME = re.compile(r"^[A-Za-z_][A-Za-z0-9_.]{0,59}$")


def _err(message: str) -> RpcError:
    return RpcError(message, INVALID_PARAMS, data={"key": "rule_invalid"})


def _col(name: Any, columns: list[str]) -> str:
    if not isinstance(name, str) or name not in columns:
        raise RpcError(f"Unknown column: {name}", INVALID_PARAMS, data={"key": "column_not_found"})
    return name


def _new(name: Any, columns: list[str], may_exist: bool = False) -> str:
    if not isinstance(name, str) or not NAME.match(name):
        raise _err("The new column name uses letters, digits, _ and . and starts with a letter")
    if name in columns and not may_exist:
        raise _err(f"The column {name} already exists")
    return name


def _number(v: Any, what: str) -> float | None:
    if v is None or v == "":
        return None
    try:
        return float(str(v).replace(",", "."))
    except ValueError:
        raise _err(f"{what} must be a number") from None


def _conditions(raw: Any, columns: list[str]) -> list[dict[str, Any]]:
    if not isinstance(raw, list) or not 1 <= len(raw) <= 6:
        raise _err("Give 1 to 6 conditions")
    out = []
    for c in raw:
        if not isinstance(c, dict) or c.get("op") not in COND_OPS:
            raise _err(f"Each condition needs an operator among {COND_OPS}")
        op = c["op"]
        cond: dict[str, Any] = {"column": _col(c.get("column"), columns), "op": op}
        if op in ("in", "not_in"):
            vals = c.get("values")
            if not isinstance(vals, list) or not vals:
                raise _err("Choose the values")
            cond["values"] = [str(v) for v in vals]
        elif op in ("lt", "le", "gt", "ge"):
            cond["value"] = _number(c.get("value"), "The compared value")
            if cond["value"] is None:
                raise _err("Give the compared value")
        elif op in ("eq", "ne"):
            cond["value"] = str(c.get("value") if c.get("value") is not None else "")
        out.append(cond)
    return out


def validate(rule: dict[str, Any], columns: list[str], out: dict[str, Any]) -> dict[str, Any]:
    """Fill `out` (kind, note, enabled already set) for an advanced rule kind."""
    kind = rule["kind"]
    if kind == "compute":
        op = rule.get("op")
        if op not in COMPUTE_OPS:
            raise _err(f"op must be one of {COMPUTE_OPS}")
        cols = rule.get("columns")
        if not isinstance(cols, list) or not cols:
            raise _err("Choose the columns")
        out["columns"] = [_col(c, columns) for c in cols]
        if op in ("difference", "ratio") and len(out["columns"]) != 2:
            raise _err("A difference or a ratio takes exactly two columns")
        out["op"] = op
        if op == "count_values":
            vals = rule.get("values")
            if not isinstance(vals, list) or not vals:
                raise _err("Choose the values to count")
            out["values"] = [str(v) for v in vals]
        out["target"] = _new(rule.get("target"), columns)
    elif kind == "classes":
        out["column"] = _col(rule.get("column"), columns)
        out["target"] = _new(rule.get("target"), columns)
        classes = rule.get("classes")
        if not isinstance(classes, list) or not 1 <= len(classes) <= 30:
            raise _err("Give 1 to 30 classes")
        cl = []
        for c in classes:
            if not isinstance(c, dict) or not str(c.get("label") or "").strip():
                raise _err("Each class needs a name")
            lo, hi = _number(c.get("from"), "From"), _number(c.get("to"), "To")
            if lo is None and hi is None:
                raise _err("Each class needs a lower or an upper bound")
            if lo is not None and hi is not None and lo >= hi:
                raise _err("A class goes from a smaller to a larger value")
            cl.append({"from": lo, "to": hi, "label": str(c["label"]).strip()[:60]})
        out["classes"] = cl
    elif kind == "conditional":
        out["conditions"] = _conditions(rule.get("conditions"), columns)
        out["combine"] = "any" if rule.get("combine") == "any" else "all"
        out["target"] = _new(rule.get("target"), columns, may_exist=True)
        v = rule.get("value")
        out["value"] = None if v is None or v == "" else str(v)[:200]
    elif kind == "check":
        out["conditions"] = _conditions(rule.get("conditions"), columns)
        out["combine"] = "any" if rule.get("combine") == "any" else "all"
        action = rule.get("action")
        if action not in CHECK_ACTIONS:
            raise _err(f"action must be one of {CHECK_ACTIONS}")
        out["action"] = action
        if action == "flag":
            out["target"] = _new(rule.get("target"), columns)
        if action == "missing":
            out["column"] = _col(rule.get("column"), columns)
    elif kind == "text":
        out["column"] = _col(rule.get("column"), columns)
        ops = rule.get("ops")
        if not isinstance(ops, list) or not ops or any(o not in TEXT_OPS for o in ops):
            raise _err(f"ops must be among {TEXT_OPS}")
        if len({"lower", "upper", "title"} & set(ops)) > 1:
            raise _err("Choose one case only")
        out["ops"] = [o for o in TEXT_OPS if o in ops]
    elif kind == "date":
        mode = rule.get("mode")
        if mode not in DATE_MODES:
            raise _err(f"mode must be one of {DATE_MODES}")
        out["mode"] = mode
        out["column"] = _col(rule.get("column"), columns)
        if mode == "duration":
            out["end"] = _col(rule.get("end"), columns)
        if mode == "age":
            ref_col = rule.get("ref_column")
            if ref_col:
                out["ref_column"] = _col(ref_col, columns)
            else:
                try:
                    out["ref_date"] = date.fromisoformat(str(rule.get("ref_date"))).isoformat()
                except ValueError:
                    raise _err("Give the reference date as YYYY-MM-DD, or a column") from None
        out["target"] = _new(rule.get("target"), columns)
    return out


def new_columns(rule: dict[str, Any]) -> list[str]:
    """Columns a rule adds to the table."""
    if rule["kind"] in ("compute", "classes", "date") or (rule["kind"] == "check" and rule.get("action") == "flag"):
        return [rule["target"]]
    if rule["kind"] == "conditional":
        return [rule["target"]]
    return []


# ----- application ----------------------------------------------------------------


def _as_text(expr: pl.Expr) -> pl.Expr:
    """A number as people write it: 12 rather than 12.0; at most 6 decimals."""
    rounded = expr.round(6)
    return (
        pl.when(rounded.is_null())
        .then(None)
        .when(rounded == rounded.floor())
        .then(rounded.cast(pl.Int64, strict=False).cast(pl.Utf8))
        .otherwise(rounded.cast(pl.Utf8))
    )


def _num(col: str) -> pl.Expr:
    return pl.col(col).cast(pl.Float64, strict=False)


def _condition(c: dict[str, Any]) -> pl.Expr:
    col, op = pl.col(c["column"]), c["op"]
    if op == "missing":
        return col.is_null()
    if op == "present":
        return col.is_not_null()
    if op == "eq":
        return (col == c["value"]).fill_null(False)
    if op == "ne":
        return (col != c["value"]).fill_null(True)
    if op == "in":
        return col.is_in(c["values"]).fill_null(False)
    if op == "not_in":
        return (~col.is_in(c["values"])).fill_null(True)
    x = _num(c["column"])
    v = c["value"]
    expr = {"lt": x < v, "le": x <= v, "gt": x > v, "ge": x >= v}[op]
    return expr.fill_null(False)


def _mask(rule: dict[str, Any]) -> pl.Expr:
    parts = [_condition(c) for c in rule["conditions"]]
    out = parts[0]
    for p in parts[1:]:
        out = (out | p) if rule.get("combine") == "any" else (out & p)
    return out


def _datetime(col: str) -> pl.Expr:
    """Kobo and Excel dates: ISO date-times (offset ignored), ISO dates, dd/mm/yyyy, Excel serial numbers."""
    s = pl.col(col).cast(pl.Utf8).str.strip_chars()
    head = s.str.slice(0, 19).str.replace("T", " ")
    serial = s.cast(pl.Float64, strict=False)
    excel = pl.when((serial > 20000) & (serial < 80000)).then(
        pl.lit(date(1899, 12, 30)).cast(pl.Datetime("us")) + pl.duration(days=serial.floor().cast(pl.Int64))
    )
    return pl.coalesce(
        head.str.strptime(pl.Datetime("us"), "%Y-%m-%d %H:%M:%S", strict=False),
        s.str.slice(0, 10).str.strptime(pl.Datetime("us"), "%Y-%m-%d", strict=False),
        s.str.slice(0, 10).str.strptime(pl.Datetime("us"), "%d/%m/%Y", strict=False),
        excel,
    )


def apply(df: pl.DataFrame, rule: dict[str, Any]) -> tuple[pl.DataFrame, int, int]:
    """Apply one advanced rule. Returns the table, rows removed and cells changed (or produced)."""
    kind = rule["kind"]
    needed = set(rule.get("columns") or [])
    for key in ("column", "end", "ref_column"):
        if rule.get(key):
            needed.add(rule[key])
    needed |= {c["column"] for c in rule.get("conditions") or []}
    if not needed <= set(df.columns):
        return df, 0, 0  # a column removed or not yet created: the rule waits

    if kind == "compute":
        cols, op = rule["columns"], rule["op"]
        nums = [_num(c) for c in cols]
        if op == "sum":
            any_value = pl.any_horizontal([n.is_not_null() for n in nums])
            expr = pl.when(any_value).then(pl.sum_horizontal(nums))
        elif op == "mean":
            expr = pl.mean_horizontal(nums)
        elif op == "min":
            expr = pl.min_horizontal(nums)
        elif op == "max":
            expr = pl.max_horizontal(nums)
        elif op == "difference":
            expr = nums[0] - nums[1]
        elif op == "ratio":
            expr = pl.when(nums[1] != 0).then(nums[0] / nums[1])
        else:  # count_values
            hits = [pl.col(c).is_in(rule["values"]).fill_null(False).cast(pl.Int64) for c in cols]
            expr = pl.sum_horizontal(hits).cast(pl.Float64)
        df = df.with_columns(_as_text(expr).alias(rule["target"]))
        return df, 0, int(df[rule["target"]].is_not_null().sum())

    if kind == "classes":
        x = _num(rule["column"])
        expr = pl.lit(None, dtype=pl.Utf8)
        for c in reversed(rule["classes"]):
            cond = pl.lit(True)
            if c["from"] is not None:
                cond = cond & (x >= c["from"])
            if c["to"] is not None:
                cond = cond & (x < c["to"])
            expr = pl.when(cond.fill_null(False)).then(pl.lit(c["label"])).otherwise(expr)
        df = df.with_columns(expr.alias(rule["target"]))
        return df, 0, int(df[rule["target"]].is_not_null().sum())

    if kind == "conditional":
        target = rule["target"]
        if target not in df.columns:
            df = df.with_columns(pl.lit(None, dtype=pl.Utf8).alias(target))
        mask = _mask(rule)
        changed = int(df.select(mask.sum()).item())
        value = pl.lit(rule["value"], dtype=pl.Utf8)
        df = df.with_columns(pl.when(mask).then(value).otherwise(pl.col(target).cast(pl.Utf8)).alias(target))
        return df, 0, changed

    if kind == "check":
        mask = _mask(rule)
        hits = int(df.select(mask.sum()).item())
        if rule["action"] == "flag":
            df = df.with_columns(pl.when(mask).then(pl.lit("1")).otherwise(pl.lit("0")).alias(rule["target"]))
            return df, 0, hits
        if rule["action"] == "exclude":
            before = df.height
            df = df.filter(~mask)
            return df, before - df.height, 0
        col = rule["column"]
        df = df.with_columns(pl.when(mask).then(None).otherwise(pl.col(col)).alias(col))
        return df, 0, hits

    if kind == "text":
        col = rule["column"]
        expr = pl.col(col).cast(pl.Utf8)
        for op in rule["ops"]:
            if op == "trim":
                expr = expr.str.strip_chars()
            elif op == "squeeze":
                expr = expr.str.replace_all(r"\s+", " ")
            elif op == "lower":
                expr = expr.str.to_lowercase()
            elif op == "upper":
                expr = expr.str.to_uppercase()
            elif op == "title":
                expr = expr.str.to_titlecase()
            elif op == "accents":
                expr = expr.str.normalize("NFKD").str.replace_all(r"\p{M}", "")
        new = df.select(expr.alias("__new"))["__new"]
        changed = int(((new != df[col]).fill_null(False) | (new.is_null() != df[col].is_null())).sum())
        df = df.with_columns(new.alias(col))
        return df, 0, changed

    if kind == "date":
        start = _datetime(rule["column"])
        mode = rule["mode"]
        if mode == "duration":
            expr = (_datetime(rule["end"]) - start).dt.total_seconds() / 60
        elif mode == "age":
            ref = (
                _datetime(rule["ref_column"])
                if rule.get("ref_column")
                else pl.lit(date.fromisoformat(rule["ref_date"])).cast(pl.Datetime("us"))
            )
            # Completed years: one less if the birthday has not come yet that year.
            years = ref.dt.year() - start.dt.year()
            before = (ref.dt.month() < start.dt.month()) | (
                (ref.dt.month() == start.dt.month()) & (ref.dt.day() < start.dt.day())
            )
            expr = (years - before.cast(pl.Int32)).cast(pl.Float64)
        elif mode == "year":
            expr = start.dt.year().cast(pl.Float64)
        else:
            expr = start.dt.month().cast(pl.Float64)
        df = df.with_columns(_as_text(expr).alias(rule["target"]))
        return df, 0, int(df[rule["target"]].is_not_null().sum())

    return df, 0, 0


# ----- plain-language description (report annex) ------------------------------------

WORDS = {
    "fr": {
        "ops": {
            "sum": "somme",
            "mean": "moyenne",
            "min": "minimum",
            "max": "maximum",
            "difference": "différence",
            "ratio": "rapport",
            "count_values": "nombre de colonnes valant {values}",
        },
        "compute": "Nouvelle variable « {target} » : {op} de {columns}",
        "classes": "Nouvelle variable « {target} » : classes de « {column} » ({classes})",
        "conditional": "« {target} » mis à {value} si {conditions}",
        "check_flag": "Contrôle de cohérence : « {target} » vaut 1 si {conditions}",
        "check_exclude": "Contrôle de cohérence : exclure les lignes où {conditions}",
        "check_missing": "Contrôle de cohérence : « {column} » mis en manquant si {conditions}",
        "text": "Dans « {column} » : {ops}",
        "text_ops": {
            "trim": "espaces en début et fin retirés",
            "squeeze": "espaces multiples réduits",
            "lower": "minuscules",
            "upper": "majuscules",
            "title": "initiales en majuscule",
            "accents": "accents retirés",
        },
        "date_duration": "Nouvelle variable « {target} » : durée en minutes de « {column} » à « {end} »",
        "date_age": "Nouvelle variable « {target} » : âge en années révolues de « {column} » au {ref}",
        "date_year": "Nouvelle variable « {target} » : année de « {column} »",
        "date_month": "Nouvelle variable « {target} » : mois de « {column} »",
        "cond": {
            "eq": "« {c} » = {v}",
            "ne": "« {c} » ≠ {v}",
            "in": "« {c} » parmi {v}",
            "not_in": "« {c} » hors de {v}",
            "lt": "« {c} » < {v}",
            "le": "« {c} » ≤ {v}",
            "gt": "« {c} » > {v}",
            "ge": "« {c} » ≥ {v}",
            "missing": "« {c} » manquant",
            "present": "« {c} » renseigné",
        },
        "and": " et ",
        "or": " ou ",
        "missing_value": "manquant",
        "ref_column": "« {c} »",
        "from": "dès {v}",
        "to": "moins de {v}",
    },
    "en": {
        "ops": {
            "sum": "sum",
            "mean": "mean",
            "min": "minimum",
            "max": "maximum",
            "difference": "difference",
            "ratio": "ratio",
            "count_values": "number of columns equal to {values}",
        },
        "compute": 'New variable "{target}": {op} of {columns}',
        "classes": 'New variable "{target}": classes of "{column}" ({classes})',
        "conditional": '"{target}" set to {value} where {conditions}',
        "check_flag": 'Consistency check: "{target}" is 1 where {conditions}',
        "check_exclude": "Consistency check: exclude rows where {conditions}",
        "check_missing": 'Consistency check: "{column}" set to missing where {conditions}',
        "text": 'In "{column}": {ops}',
        "text_ops": {
            "trim": "leading and trailing spaces removed",
            "squeeze": "repeated spaces reduced",
            "lower": "lower case",
            "upper": "upper case",
            "title": "capitalised words",
            "accents": "accents removed",
        },
        "date_duration": 'New variable "{target}": duration in minutes from "{column}" to "{end}"',
        "date_age": 'New variable "{target}": age in completed years of "{column}" at {ref}',
        "date_year": 'New variable "{target}": year of "{column}"',
        "date_month": 'New variable "{target}": month of "{column}"',
        "cond": {
            "eq": '"{c}" = {v}',
            "ne": '"{c}" ≠ {v}',
            "in": '"{c}" among {v}',
            "not_in": '"{c}" not among {v}',
            "lt": '"{c}" < {v}',
            "le": '"{c}" ≤ {v}',
            "gt": '"{c}" > {v}',
            "ge": '"{c}" ≥ {v}',
            "missing": '"{c}" missing',
            "present": '"{c}" filled in',
        },
        "and": " and ",
        "or": " or ",
        "missing_value": "missing",
        "ref_column": '"{c}"',
        "from": "from {v}",
        "to": "under {v}",
    },
}


def _fmt_num(x: float) -> str:
    return str(int(x)) if float(x).is_integer() else str(x)


def describe(rule: dict[str, Any], lang: str) -> str:
    """One sentence for the cleaning journal of the report."""
    w = WORDS[lang]
    q = (lambda v: f"« {v} »") if lang == "fr" else (lambda v: f'"{v}"')
    kind = rule["kind"]

    def conditions() -> str:
        parts = []
        for c in rule["conditions"]:
            op = c["op"]
            if op in ("in", "not_in"):
                v = ", ".join(q(x) for x in c["values"])
            elif op in ("lt", "le", "gt", "ge"):
                v = _fmt_num(c["value"])
            else:
                v = q(c.get("value", ""))
            parts.append(w["cond"][op].format(c=c["column"], v=v))
        return (w["or"] if rule.get("combine") == "any" else w["and"]).join(parts)

    if kind == "compute":
        op = w["ops"][rule["op"]].format(values=", ".join(q(v) for v in rule.get("values", [])))
        return w["compute"].format(target=rule["target"], op=op, columns=", ".join(q(c) for c in rule["columns"]))
    if kind == "classes":
        parts = []
        for c in rule["classes"]:
            bounds = [w["from"].format(v=_fmt_num(c["from"])) if c["from"] is not None else ""]
            bounds.append(w["to"].format(v=_fmt_num(c["to"])) if c["to"] is not None else "")
            parts.append(
                f"{c['label']} : {' '.join(b for b in bounds if b)}"
                if lang == "fr"
                else f"{c['label']}: {' '.join(b for b in bounds if b)}"
            )
        return w["classes"].format(target=rule["target"], column=rule["column"], classes="; ".join(parts))
    if kind == "conditional":
        value = w["missing_value"] if rule["value"] is None else q(rule["value"])
        return w["conditional"].format(target=rule["target"], value=value, conditions=conditions())
    if kind == "check":
        return w[f"check_{rule['action']}"].format(
            target=rule.get("target"), column=rule.get("column"), conditions=conditions()
        )
    if kind == "text":
        return w["text"].format(column=rule["column"], ops=", ".join(w["text_ops"][o] for o in rule["ops"]))
    if kind == "date":
        ref = w["ref_column"].format(c=rule["ref_column"]) if rule.get("ref_column") else rule.get("ref_date")
        return w[f"date_{rule['mode']}"].format(
            target=rule["target"], column=rule["column"], end=rule.get("end"), ref=ref
        )
    return kind
