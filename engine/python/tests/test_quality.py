"""Data quality diagnosis: each issue found, and each proposed fix accepted by the cleaning journal."""

from __future__ import annotations

from pathlib import Path

import polars as pl

from sme_engine import cleaning, datasets, quality


def spec_for(df: pl.DataFrame, **extra):
    return {
        "id_column": None,
        "design": {"weights": None, "strata": [], "cluster": None},
        "labels": {"columns": {}, "values": {}},
        **extra,
    }


def test_each_issue_and_its_fix():
    n = 200
    ages = [str(20 + i % 40) for i in range(n)]
    ages[3], ages[4] = "450", "abc"
    df = pl.DataFrame(
        {
            "hh_id": [str(i) for i in range(n - 2)] + ["7", "8"],
            "age": ages,
            "w": ["1.5"] * (n - 1) + [None],
            "q1": ["yes", "no"] * (n // 2 - 1) + ["maybe", "yes"],
            "skip": [None] * (n - 5) + ["a"] * 5,
            "same": ["x"] * n,
            "empty": pl.Series([None] * n, dtype=pl.Utf8),
        }
    )
    spec = spec_for(
        df,
        id_column="hh_id",
        design={"weights": "w", "strata": [], "cluster": None},
        labels={"columns": {}, "values": {"q1": {"yes": {"en": "Yes"}, "no": {"en": "No"}}}},
    )
    found = {(i["key"], i["column"]): i for i in quality.diagnose(df, spec)["issues"]}
    assert found[("duplicate_id", "hh_id")]["count"] == 2
    assert found[("weight_invalid", "w")]["count"] == 1
    assert found[("unknown_codes", "q1")]["samples"] == ["maybe"]
    assert found[("text_in_numbers", "age")]["samples"] == ["abc"]
    out = found[("outliers", "age")]
    assert out["samples"] == ["450"] and out["fix"]["max"] < 450 and out["fix"]["min"] is None
    assert ("mostly_missing", "skip") in found and ("constant", "same") in found and ("empty", "empty") in found
    # Warnings come first.
    keys = [i["severity"] for i in quality.diagnose(df, spec)["issues"]]
    assert keys == sorted(keys, key=lambda s: s != "warning")

    # Every proposed fix is a valid rule and removes its issue.
    rules = [cleaning.validate(i["fix"], df.columns) for i in found.values() if i["fix"]]
    cleaned, _ = cleaning.apply(df, rules)
    after = {(i["key"], i["column"]) for i in quality.diagnose(cleaned, spec)["issues"] if i["severity"] == "warning"}
    assert after == set()


def test_no_false_alarm_on_real_survey_columns():
    """Real household data (REACH Iraq 2019 extract): counts and identifiers raise no outlier warning."""
    path = Path(__file__).resolve().parents[1] / "sme_engine" / "examples" / "mcna_irak_2019.xlsx"
    df = datasets.load(path, "Donnees menages")
    spec = spec_for(df, id_column="X_uuid", design={"weights": "weights", "strata": [], "cluster": None})
    issues = quality.diagnose(cleaning.missing_to_null(df, datasets.DEFAULT_NA), spec)["issues"]
    flagged = {i["column"] for i in issues if i["key"] == "outliers"}
    assert "weights" not in flagged and "X_uuid" not in flagged
    assert all(i["count"] / df.height <= quality.MAX_OUTLIER_SHARE for i in issues if i["key"] == "outliers")
