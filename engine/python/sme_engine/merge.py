"""Merged datasets: one file joined to another by a key, such as individuals to households.

A merged dataset stores no data of its own. Its rows are computed from the cleaned
data of its two sources each time they change, so a correction made in the
household file reaches the merged file too. It then has its own cleaning journal
like any other dataset.

    {"left": id, "right": id, "left_key": column, "right_key": column, "how": "left" | "inner"}

The join is many-to-one: every row of the left file finds at most one row of the
right file (each individual has one household). A right key that repeats would
copy left rows silently, so it is refused. Keys are compared as text; an empty
key matches nothing.
"""

from __future__ import annotations

from typing import Any

import polars as pl

from .project import _err

HOW = ("left", "inner")
SUFFIX = "_2"


def validate(params: dict[str, Any], left: dict[str, Any], right: dict[str, Any]) -> dict[str, Any]:
    if left["id"] == right["id"]:
        raise _err("Choose two different files", "merge_same")
    left_cols = [c["name"] for c in left["columns"]]
    right_cols = [c["name"] for c in right["columns"]]
    left_key, right_key = params.get("left_key"), params.get("right_key")
    if left_key not in left_cols:
        raise _err(f"Unknown column: {left_key}", "column_not_found")
    if right_key not in right_cols:
        raise _err(f"Unknown column: {right_key}", "column_not_found")
    how = params.get("how") or "left"
    if how not in HOW:
        raise _err(f"how must be one of {HOW}", "invalid_params")
    return {"left": left["id"], "right": right["id"], "left_key": left_key, "right_key": right_key, "how": how}


def renamed(left_columns: list[str], right_columns: list[str], right_key: str) -> dict[str, str]:
    """Right column -> name in the merged file. The right key is dropped; clashes take a suffix."""
    taken = set(left_columns)
    out = {}
    for c in right_columns:
        if c == right_key:
            continue
        name = c
        while name in taken:
            name += SUFFIX
        taken.add(name)
        out[c] = name
    return out


def join(left: pl.DataFrame, right: pl.DataFrame, m: dict[str, Any]) -> tuple[pl.DataFrame, dict[str, int]]:
    """The merged rows and match counts. Raises if the right key repeats."""
    lk, rk = m["left_key"], m["right_key"]
    keys = right[rk].cast(pl.Utf8)
    present = keys.drop_nulls()
    dup = present.filter(present.is_duplicated()).unique().sort()
    if dup.len():
        raise _err(
            f"The key {rk} repeats in the second file ({dup.len()} values, for example {dup[0]}): "
            "each row of the first file must find at most one row",
            "merge_key_repeats",
        )
    names = renamed(left.columns, right.columns, rk)
    r = right.with_columns(keys.alias("__key")).select(["__key", *[pl.col(c).alias(n) for c, n in names.items()]])
    r = r.filter(pl.col("__key").is_not_null())
    lkey = left[lk].cast(pl.Utf8)
    marked = left.with_columns(lkey.alias("__key"), pl.int_range(pl.len()).alias("__row"))
    out = marked.join(r.with_columns(pl.lit(True).alias("__hit")), on="__key", how=m["how"], coalesce=True)
    out = out.sort("__row")
    matched = int(out["__hit"].fill_null(False).sum())
    used = set(lkey.drop_nulls().to_list())
    stats = {
        "left_rows": left.height,
        "right_rows": right.height,
        "rows": out.height,
        "matched": matched,
        "left_unmatched": left.height - matched,
        "right_unmatched": int((~r["__key"].is_in(list(used))).sum()),
    }
    return out.drop(["__key", "__row", "__hit"]), stats


def labels(left: dict[str, Any], right: dict[str, Any], names: dict[str, str]) -> dict[str, Any]:
    """Labels of both files, under the names the right columns take in the merged file."""
    ll = left.get("labels") or {"columns": {}, "values": {}}
    rl = right.get("labels") or {"columns": {}, "values": {}}
    columns = dict(ll.get("columns", {}))
    values = dict(ll.get("values", {}))
    for src, dst in names.items():
        if src in rl.get("columns", {}):
            columns[dst] = rl["columns"][src]
        if src in rl.get("values", {}):
            values[dst] = rl["values"][src]
    return {"columns": columns, "values": values}


def stack(frames: list[tuple[str, pl.DataFrame]], source_column: str) -> tuple[pl.DataFrame, dict[str, Any]]:
    """Rows of several files one under the other, columns matched by name. A column missing
    from a file is empty for its rows. The first column tells which file each row comes from."""
    names = [n for n, _ in frames]
    all_columns: list[str] = []
    for _, df in frames:
        all_columns += [c for c in df.columns if c not in all_columns]
    col = source_column
    while col in all_columns:
        col += SUFFIX
    parts = [df.with_columns(pl.all().cast(pl.Utf8)).with_columns(pl.lit(name).alias(col)) for name, df in frames]
    out = pl.concat(parts, how="diagonal").select([col, *all_columns])
    missing = {n: [c for c in all_columns if c not in df.columns] for n, df in frames}
    stats = {
        "files": len(frames),
        "rows": out.height,
        "rows_by_file": {n: df.height for n, df in frames},
        "columns": len(all_columns),
        "missing_columns": {n: m for n, m in missing.items() if m},
        "names": names,
    }
    return out, stats
