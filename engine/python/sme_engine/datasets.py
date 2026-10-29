"""Data import: Excel (including Kobo exports) and CSV files.

The imported table is stored unchanged in the project as Parquet. Every value is
kept as text at import, exactly as in the file; column types are inferred for
display and analysis, and cleaning works on a copy (see cleaning.py).
"""

from __future__ import annotations

import io
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import polars as pl

from .rpc import INVALID_PARAMS, RpcError

ROUNDS = ("baseline", "midline", "endline", "monitoring")
# Text read as a missing value. "NA" and empty cells are what Kobo and R write.
DEFAULT_NA = ["", "NA", "N/A", "n/a", "NaN", "null", "NULL"]
MAX_ROWS = 2_000_000
SAMPLE_ROWS = 8


def _err(message: str, key: str) -> RpcError:
    return RpcError(message, INVALID_PARAMS, data={"key": key})


def _read(path: Path, sheet: str | None, n_rows: int | None = None) -> pl.DataFrame:
    """Read one sheet (or the CSV) with every column as text."""
    suffix = path.suffix.lower()
    try:
        if suffix == ".csv":
            # Kobo and Excel CSV files may use ";" as separator: sniff the first line.
            with path.open("r", encoding="utf-8-sig", errors="replace") as fh:
                first = fh.readline()
            sep = ";" if first.count(";") > first.count(",") else ","
            return pl.read_csv(
                path,
                separator=sep,
                infer_schema=False,
                n_rows=n_rows,
                encoding="utf8-lossy",
                truncate_ragged_lines=True,
            )
        if suffix in (".xlsx", ".xlsm", ".xls"):
            opts: dict[str, Any] = {"n_rows": n_rows} if n_rows else {}
            return pl.read_excel(
                path,
                sheet_name=sheet,
                engine="calamine",
                infer_schema_length=0,
                read_options=opts,
            )
    except Exception as exc:  # noqa: BLE001 - any reader failure is a readable error for the user
        raise _err(f"Cannot read {path.name}: {exc}", "file_unreadable") from None
    raise _err(f"Unsupported file type: {suffix}", "file_type")


def sheet_names(path: Path) -> list[str]:
    if path.suffix.lower() == ".csv":
        return [path.stem]
    import fastexcel

    try:
        return list(fastexcel.read_excel(str(path)).sheet_names)
    except Exception as exc:  # noqa: BLE001
        raise _err(f"Cannot read {path.name}: {exc}", "file_unreadable") from None


def _unique_names(columns: list[str]) -> list[str]:
    """Excel headers can be empty or repeated: make them unique and non-empty."""
    seen: dict[str, int] = {}
    out = []
    for i, name in enumerate(columns):
        base = (name or "").strip() or f"column_{i + 1}"
        n = seen.get(base, 0)
        seen[base] = n + 1
        out.append(base if n == 0 else f"{base}_{n + 1}")
    return out


def normalise(df: pl.DataFrame) -> pl.DataFrame:
    df = df.rename(dict(zip(df.columns, _unique_names(df.columns), strict=True)))
    # Everything as text, trimmed; fully empty rows are dropped (Excel leftovers).
    df = df.with_columns(pl.all().cast(pl.Utf8).str.strip_chars())
    return df.filter(~pl.all_horizontal(pl.all().is_null() | (pl.all() == "")))


def describe_columns(df: pl.DataFrame, na_values: list[str]) -> list[dict[str, Any]]:
    """Type, missing count and distinct values of each column."""
    out = []
    n = df.height
    for name in df.columns:
        col = df[name]
        missing_mask = col.is_null() | col.is_in(na_values)
        present = col.filter(~missing_mask)
        numeric = present.cast(pl.Float64, strict=False)
        n_present = present.len()
        n_numeric = n_present - numeric.null_count()
        kind = "number" if n_present > 0 and n_numeric == n_present else "text"
        info: dict[str, Any] = {
            "name": name,
            "type": kind,
            "missing": int(missing_mask.sum()),
            "distinct": int(present.n_unique()),
            "rows": n,
        }
        if kind == "number":
            info["min"] = float(numeric.min())  # type: ignore[arg-type]
            info["max"] = float(numeric.max())  # type: ignore[arg-type]
        out.append(info)
    return out


def guess_design(columns: list[str]) -> dict[str, Any]:
    """Suggest the survey design columns from common Kobo and REACH names."""
    lower = {c.lower(): c for c in columns}

    def first(*names: str) -> str | None:
        for n in names:
            if n in lower:
                return lower[n]
        return None

    return {
        "weights": first("weights", "weight", "poids", "wt", "survey_weight", "hh_weight"),
        "strata": [s for s in [first("strata", "stratum", "strate", "zone")] if s],
        "cluster": first("cluster", "cluster_id", "psu", "village", "grappe", "cluster_location_id"),
    }


def guess_id(columns: list[str]) -> str | None:
    for c in columns:
        if c.lower() in ("_uuid", "x_uuid", "uuid", "hh_id", "id", "_id", "key", "instanceid"):
            return c
    return None


def inspect(path: Path, sheet: str | None = None) -> dict[str, Any]:
    """What the import screen shows before importing: sheets, columns, sample rows."""
    sheets = sheet_names(path)
    if not sheets:
        raise _err(f"{path.name} contains no sheet", "file_empty")
    chosen = sheet if sheet in sheets else _best_sheet(path, sheets)
    df = normalise(_read(path, None if path.suffix.lower() == ".csv" else chosen, n_rows=200))
    return {
        "file_name": path.name,
        "sheets": sheets,
        "sheet": chosen,
        "columns": df.columns,
        "sample": df.head(SAMPLE_ROWS).rows(),
        "design": guess_design(df.columns),
        "id_column": guess_id(df.columns),
    }


def _best_sheet(path: Path, sheets: list[str]) -> str:
    """The sheet with the most columns, skipping read-me and questionnaire sheets."""
    if len(sheets) == 1 or path.suffix.lower() == ".csv":
        return sheets[0]
    skip = ("read", "lisez", "questionnaire", "choices", "survey", "coverage", "log", "key", "tool", "deleted")
    best, best_cols = sheets[0], -1
    for s in sheets:
        if any(k in s.lower() for k in skip):
            continue
        try:
            n = len(_read(path, s, n_rows=2).columns)
        except RpcError:
            continue
        if n > best_cols:
            best, best_cols = s, n
    return best


def load(path: Path, sheet: str | None) -> pl.DataFrame:
    df = normalise(_read(path, None if path.suffix.lower() == ".csv" else sheet))
    if df.height == 0:
        raise _err("The sheet contains no data rows", "file_empty")
    if df.height > MAX_ROWS:
        raise _err(f"More than {MAX_ROWS} rows", "file_too_large")
    return df


def to_parquet(df: pl.DataFrame) -> bytes:
    buf = io.BytesIO()
    df.write_parquet(buf, compression="zstd")
    return buf.getvalue()


def from_parquet(blob: bytes) -> pl.DataFrame:
    return pl.read_parquet(io.BytesIO(blob))


def validate_design(design: Any, columns: list[str]) -> dict[str, Any]:
    if not isinstance(design, dict):
        design = {}
    weights = design.get("weights") or None
    cluster = design.get("cluster") or None
    strata = [s for s in (design.get("strata") or []) if s]
    for name in [weights, cluster, *strata]:
        if name is not None and name not in columns:
            raise _err(f"Unknown column: {name}", "column_not_found")
    return {"weights": weights, "strata": strata, "cluster": cluster}


def new_spec(name: str, round_: str, path: Path, sheet: str | None, df: pl.DataFrame, params: dict[str, Any]) -> dict:
    if round_ not in ROUNDS:
        raise _err(f"round must be one of {ROUNDS}", "invalid_round")
    na_values = params.get("na_values")
    if not isinstance(na_values, list) or not all(isinstance(v, str) for v in na_values):
        na_values = DEFAULT_NA
    id_column = params.get("id_column") or guess_id(df.columns)
    if id_column is not None and id_column not in df.columns:
        raise _err(f"Unknown column: {id_column}", "column_not_found")
    return {
        "name": name,
        "round": round_,
        "source_name": path.name,
        "sheet": sheet if path.suffix.lower() != ".csv" else None,
        "imported_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "rows": df.height,
        "na_values": na_values,
        "id_column": id_column,
        "design": validate_design(params.get("design") or guess_design(df.columns), df.columns),
        "attribution": str(params.get("attribution") or "")[:500],
        "columns": describe_columns(df, na_values),
    }
