"""Data quality diagnosis of a dataset, after its cleaning journal.

Each issue names a column (or the whole file), counts the rows concerned, shows a
few sample values and, when one fits, proposes the cleaning rule that fixes it.
Nothing is changed here: the user decides, and the rule then goes into the
journal like any other, so it shows in the report.

Issues
- duplicate_id:     the identifier column repeats.
- duplicate_rows:   identical rows (only checked without an identifier column).
- weight_invalid:   the weight column has missing, zero or negative values.
- unknown_codes:    values absent from the questionnaire's list of answers.
- text_in_numbers:  a numeric column holding a few texts.
- outliers:         numbers far from the others (beyond 3 interquartile ranges).
- mostly_missing:   at least half the values missing (often a skipped question).
- constant:         a single value in the whole column.
- empty:            no value at all.
"""

from __future__ import annotations

import math
import re
from typing import Any

import polars as pl

SAMPLES = 5
OUTLIER_K = 3.0
MIN_NUMBERS = 20
MAX_OUTLIER_SHARE = 0.02  # beyond this, the "outliers" are the shape of the distribution, not errors
# Identifiers, codes and device metadata are numbers that are not quantities.
NOT_A_QUANTITY = re.compile(
    r"(?i)(^|[_/.])(id|uuid|index|code|name|deviceid|imei|subscriberid|simserial|phonenumber|start|end|today)$|_id$"
)
SEVERITY = {
    "duplicate_id": "warning",
    "duplicate_rows": "warning",
    "weight_invalid": "warning",
    "unknown_codes": "warning",
    "text_in_numbers": "warning",
    "outliers": "warning",
    "mostly_missing": "info",
    "constant": "info",
    "empty": "info",
}
ORDER = list(SEVERITY)


def _samples(series: pl.Series) -> list[str]:
    counts = series.drop_nulls().value_counts(sort=True)
    return [str(v) for v in counts[counts.columns[0]].head(SAMPLES).to_list()]


def _num(v: float) -> str:
    return str(int(v)) if float(v).is_integer() else f"{v:.4g}"


def _outliers(vals: pl.Series) -> tuple[pl.Series, float, float] | None:
    """Values beyond 3 interquartile ranges, on a log scale for skewed positive amounts (money, volumes).

    None when there are none, or when too many to be errors."""
    skewed = vals.min() >= 0 and vals.median() and vals.max() / vals.median() > 20  # type: ignore[operator]
    x = vals.log1p() if skewed else vals
    q1, q3 = x.quantile(0.25), x.quantile(0.75)
    if q1 is None or q3 is None or q3 <= q1:
        return None
    low, high = q1 - OUTLIER_K * (q3 - q1), q3 + OUTLIER_K * (q3 - q1)
    hit = (x < low) | (x > high)
    count = int(hit.sum())
    if count == 0 or count / vals.len() > MAX_OUTLIER_SHARE:
        return None
    if skewed:
        low, high = math.expm1(low), math.expm1(high)
        low = max(low, 0.0)
    return vals.filter(hit), low, high


def diagnose(df: pl.DataFrame, spec: dict[str, Any]) -> dict[str, Any]:
    n = df.height
    issues: list[dict[str, Any]] = []
    design = spec.get("design") or {}
    weights = design.get("weights")
    id_col = spec.get("id_column")
    technical = {id_col, weights, design.get("cluster"), *(design.get("strata") or [])}
    value_labels = (spec.get("labels") or {}).get("values") or {}

    def add(key: str, column: str | None, count: int, samples: list[str] | None = None, fix=None, **extra: Any):
        issues.append(
            {
                "key": key,
                "severity": SEVERITY[key],
                "column": column,
                "count": int(count),
                "share": (count / n) if n else 0.0,
                "samples": samples or [],
                "fix": fix,
                **extra,
            }
        )

    if n == 0:
        return {"rows": 0, "columns": len(df.columns), "issues": []}

    if id_col and id_col in df.columns:
        ids = df[id_col].drop_nulls()
        dup = ids.filter(ids.is_duplicated())
        if dup.len():
            add(
                "duplicate_id",
                id_col,
                dup.len() - dup.n_unique(),
                _samples(dup),
                {"kind": "duplicates", "columns": [id_col], "note": ""},
            )
    else:
        extra_rows = n - df.unique().height
        if extra_rows:
            add("duplicate_rows", None, extra_rows, fix={"kind": "duplicates", "columns": df.columns, "note": ""})

    if weights and weights in df.columns:
        w = df[weights].cast(pl.Float64, strict=False)
        bad = w.is_null() | (w <= 0)
        count = int(bad.fill_null(True).sum())
        if count:
            add(
                "weight_invalid",
                weights,
                count,
                _samples(df[weights].filter(bad.fill_null(True)).fill_null("NA")),
                {"kind": "exclude", "column": weights, "values": [None], "note": ""},
            )

    for name in df.columns:
        col = df[name]
        present = col.drop_nulls()
        n_present = present.len()
        if n_present == 0:
            add("empty", name, n)
            continue
        missing = n - n_present
        if missing / n >= 0.5:
            add("mostly_missing", name, missing)
        if present.n_unique() == 1 and n_present >= 10 and name not in technical:
            add("constant", name, n_present, [str(present[0])])

        codes = value_labels.get(name)
        if codes and len(codes) >= 2 and set(codes) != {"0", "1"}:
            unknown = present.filter(~present.is_in(list(codes)))
            if unknown.len():
                values = _samples(unknown)
                full = unknown.unique().to_list()
                fix = (
                    {"kind": "recode", "column": name, "from": [str(v) for v in full], "to": None, "note": ""}
                    if len(full) <= 20
                    else None
                )
                add("unknown_codes", name, unknown.len(), values, fix)
            continue

        if name in technical or name.startswith("_"):
            continue
        num = present.cast(pl.Float64, strict=False)
        n_num = n_present - num.null_count()
        if n_num and n_num < n_present and n_num / n_present >= 0.9:
            texts = present.filter(num.is_null())
            full = texts.unique().to_list()
            fix = (
                {"kind": "recode", "column": name, "from": [str(v) for v in full], "to": None, "note": ""}
                if len(full) <= 20
                else None
            )
            add("text_in_numbers", name, texts.len(), _samples(texts), fix)
        if NOT_A_QUANTITY.search(name):
            continue
        vals = num.drop_nulls()
        if n_num >= MIN_NUMBERS and vals.n_unique() >= 10:
            found = _outliers(vals)
            if found:
                out, low, high = found
                lo = math.floor(low) if vals.min() < low else None  # type: ignore[operator]
                hi = math.ceil(high) if vals.max() > high else None  # type: ignore[operator]
                median = float(vals.median())  # type: ignore[arg-type]
                shown = sorted(out.unique().to_list(), key=lambda v: -abs(v - median))[:SAMPLES]
                add(
                    "outliers",
                    name,
                    out.len(),
                    [_num(v) for v in shown],
                    {"kind": "range", "column": name, "min": lo, "max": hi, "note": ""},
                    low=low,
                    high=high,
                    median=median,
                )

    issues.sort(key=lambda i: (i["severity"] != "warning", ORDER.index(i["key"]), -i["count"]))
    return {"rows": n, "columns": len(df.columns), "issues": issues}
