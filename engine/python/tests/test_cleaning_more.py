"""Advanced cleaning: new variables, classes, conditions, checks, text, dates, stacking,
and the journal written as an R script that gives the same table."""

from __future__ import annotations

import io
import json
import os
import subprocess
from pathlib import Path

import polars as pl
import pytest
from docx import Document

from sme_engine import cleaning, cleaning_more
from sme_engine.methods import register
from sme_engine.r_bridge import RBridge, find_rscript
from sme_engine.rpc import RpcError, Server

needs_r = pytest.mark.skipif(find_rscript() is None, reason="R not installed")

KOBO = pl.DataFrame(
    {
        "hh": ["1", "2", "3", "4", "5", "6"],
        "start": [
            "2018-04-01T11:55:39.741+06",
            "2018-04-01T12:00:00",
            "2018-04-02T09:00:00.000+06",
            None,
            "2018-04-02T10:00:00",
            "2018-04-03 08:00:00",
        ],
        "end": [
            "2018-04-01T12:40:09.741+06",
            "2018-04-01T12:03:30",
            "2018-04-02T08:30:00.000+06",
            "2018-04-02T10:00:00",
            "2018-04-02T11:15:00",
            "2018-04-03 08:59:00",
        ],
        "birth": ["1990-06-15", "15/06/2000", "36000", "inconnu", "2010-01-01", "1950-12-31"],
        "size": ["5", "3", "12", "0", "4", None],
        "children": ["2", "1", "13", "0", "1", "2"],
        "adults": ["3", "2", "3", None, "3", "1"],
        "water": ["yes", "no", "yes", "yes", "dont_know", "no"],
        "soap": ["yes", "yes", "no", "dont_know", "yes", "no"],
        "village": ["  Kofi  Kope ", "AKPAKPA", "éwé-dzodze", None, "lome", "Tsévié"],
    }
)


def run(rules: list[dict], df: pl.DataFrame = KOBO) -> tuple[pl.DataFrame, list[dict]]:
    cols, out = list(df.columns), []
    for i, r in enumerate(rules):
        v = cleaning.validate(r, cols)
        v["id"] = i
        out.append(v)
        cols += [c for c in cleaning.new_columns(v) if c not in cols]
    return cleaning.apply(df, out)


def test_interview_duration_and_quick_interviews_flagged():
    df, eff = run(
        [
            {"kind": "date", "mode": "duration", "column": "start", "end": "end", "target": "duration"},
            {
                "kind": "check",
                "conditions": [
                    {"column": "duration", "op": "lt", "value": 10},
                    {"column": "duration", "op": "missing"},
                ],
                "combine": "any",
                "action": "flag",
                "target": "too_quick",
            },
        ]
    )
    assert df["duration"].to_list() == ["44.5", "3.5", "-30", None, "75", "59"]
    assert df["too_quick"].to_list() == ["0", "1", "1", "1", "0", "0"]
    assert eff[0]["cells_changed"] == 5 and eff[1]["cells_changed"] == 3


def test_age_classes_and_date_parts():
    df, _ = run(
        [
            {"kind": "date", "mode": "age", "column": "birth", "ref_date": "2026-06-14", "target": "age"},
            {
                "kind": "classes",
                "column": "age",
                "target": "age_group",
                "classes": [
                    {"from": None, "to": 18, "label": "Moins de 18 ans"},
                    {"from": 18, "to": 60, "label": "18 à 59 ans"},
                    {"from": 60, "to": None, "label": "60 ans et plus"},
                ],
            },
            {"kind": "date", "mode": "year", "column": "birth", "target": "birth_year"},
        ]
    )
    # 15 June 2000 is not yet reached on 14 June 2026; 36000 is an Excel date (24 July 1998).
    assert df["age"].to_list() == ["35", "25", "27", None, "16", "75"]
    assert df["age_group"].to_list() == [
        "18 à 59 ans",
        "18 à 59 ans",
        "18 à 59 ans",
        None,
        "Moins de 18 ans",
        "60 ans et plus",
    ]
    assert df["birth_year"].to_list() == ["1990", "2000", "1998", None, "2010", "1950"]


def test_computed_variables():
    df, _ = run(
        [
            {"kind": "compute", "op": "sum", "columns": ["children", "adults"], "target": "members"},
            {"kind": "compute", "op": "difference", "columns": ["size", "members"], "target": "gap"},
            {"kind": "compute", "op": "ratio", "columns": ["children", "size"], "target": "child_share"},
            {
                "kind": "compute",
                "op": "count_values",
                "columns": ["water", "soap"],
                "values": ["yes"],
                "target": "wash",
            },
            {"kind": "compute", "op": "max", "columns": ["children", "adults"], "target": "largest"},
        ]
    )
    assert df["members"].to_list() == ["5", "3", "16", "0", "4", "3"]
    assert df["gap"].to_list() == ["0", "0", "-4", "0", "0", None]
    assert df["child_share"].to_list() == ["0.4", "0.333333", "1.083333", None, "0.25", None]
    assert df["wash"].to_list() == ["2", "1", "1", "1", "1", "0"]
    assert df["largest"].to_list() == ["3", "2", "13", "0", "3", "2"]


def test_consistency_checks_and_conditional_replacement():
    rules = [
        {
            "kind": "check",
            "conditions": [{"column": "children", "op": "gt", "value": 10}],
            "action": "missing",
            "column": "children",
        },
        {
            "kind": "conditional",
            "conditions": [{"column": "water", "op": "eq", "value": "dont_know"}],
            "target": "water",
            "value": None,
        },
        {
            "kind": "conditional",
            "conditions": [
                {"column": "water", "op": "eq", "value": "yes"},
                {"column": "soap", "op": "in", "values": ["yes"]},
            ],
            "target": "basic_wash",
            "value": "1",
        },
        {"kind": "check", "conditions": [{"column": "size", "op": "le", "value": 0}], "action": "exclude"},
    ]
    df, eff = run(rules)
    assert df["hh"].to_list() == ["1", "2", "3", "5", "6"]
    assert df["children"].to_list() == ["2", "1", None, "1", "2"]
    assert df["water"].to_list() == ["yes", "no", "yes", None, "no"]
    assert df["basic_wash"].to_list() == ["1", None, None, None, None]
    assert [e["cells_changed"] for e in eff[:3]] == [1, 1, 1] and eff[3]["rows_removed"] == 1


def test_text_cleaning():
    df, eff = run([{"kind": "text", "column": "village", "ops": ["trim", "squeeze", "accents", "title"]}])
    assert df["village"].to_list() == ["Kofi Kope", "Akpakpa", "Ewe-Dzodze", None, "Lome", "Tsevie"]
    assert eff[0]["cells_changed"] == 5


def test_validation_errors():
    cols = list(KOBO.columns)
    bad = [
        {"kind": "compute", "op": "difference", "columns": ["size"], "target": "x"},
        {"kind": "compute", "op": "sum", "columns": ["size"], "target": "size"},  # exists
        {"kind": "compute", "op": "sum", "columns": ["size"], "target": "2 bad"},
        {"kind": "classes", "column": "size", "target": "c", "classes": [{"from": 5, "to": 2, "label": "x"}]},
        {"kind": "check", "conditions": [{"column": "size", "op": "gt"}], "action": "flag", "target": "f"},
        {"kind": "text", "column": "village", "ops": ["lower", "upper"]},
        {"kind": "date", "mode": "age", "column": "birth", "ref_date": "14/06/2026", "target": "a"},
        {"kind": "check", "conditions": [{"column": "nope", "op": "missing"}], "action": "exclude"},
    ]
    for rule in bad:
        with pytest.raises(RpcError):
            cleaning.validate(rule, cols)


def test_rule_waits_for_a_column_created_later():
    rules = [cleaning.validate({"kind": "compute", "op": "sum", "columns": ["size"], "target": "t"}, KOBO.columns)]
    rules[0]["columns"] = ["later"]  # a column that does not exist yet
    df, eff = cleaning.apply(KOBO, rules)
    assert "t" not in df.columns and eff[0]["cells_changed"] == 0


def test_descriptions_for_the_report():
    rule = cleaning.validate(
        {
            "kind": "check",
            "conditions": [{"column": "children", "op": "gt", "value": 10}],
            "action": "flag",
            "target": "f",
        },
        KOBO.columns,
    )
    assert cleaning_more.describe(rule, "fr") == "Contrôle de cohérence : « f » vaut 1 si « children » > 10"
    assert cleaning_more.describe(rule, "en") == 'Consistency check: "f" is 1 where "children" > 10'


# ----- through the service: stacking, derived columns, report, R script ------------


@pytest.fixture()
def call():
    bridge = RBridge()
    server = Server(stdin=io.StringIO(), stdout=io.StringIO())
    register(server, bridge)

    def _call(method, params=None):
        resp = server.handle_line(json.dumps({"jsonrpc": "2.0", "id": 1, "method": method, "params": params or {}}))
        if "error" in resp:
            raise RuntimeError((resp["error"].get("data") or {}).get("key", "") + ": " + resp["error"]["message"])
        return resp["result"]

    yield _call
    bridge.stop()


ALL_RULES = [
    {"kind": "date", "mode": "duration", "column": "start", "end": "end", "target": "duration"},
    {
        "kind": "check",
        "conditions": [{"column": "duration", "op": "lt", "value": 10}],
        "action": "flag",
        "target": "quick",
    },
    {"kind": "date", "mode": "age", "column": "birth", "ref_date": "2026-06-14", "target": "age"},
    {
        "kind": "classes",
        "column": "age",
        "target": "age_group",
        "classes": [{"from": None, "to": 18, "label": "<18"}, {"from": 18, "to": None, "label": "18+"}],
    },
    {"kind": "compute", "op": "sum", "columns": ["children", "adults"], "target": "members"},
    {"kind": "compute", "op": "mean", "columns": ["children", "adults"], "target": "avg"},
    {"kind": "compute", "op": "ratio", "columns": ["children", "size"], "target": "share"},
    {"kind": "compute", "op": "count_values", "columns": ["water", "soap"], "values": ["yes"], "target": "wash"},
    {"kind": "recode", "column": "water", "from": ["dont_know"], "to": None},
    {
        "kind": "conditional",
        "conditions": [{"column": "water", "op": "missing"}, {"column": "soap", "op": "ne", "value": "yes"}],
        "combine": "any",
        "target": "risk",
        "value": "1",
    },
    {"kind": "text", "column": "village", "ops": ["trim", "squeeze", "lower"]},
    {"kind": "range", "column": "children", "min": 0, "max": 10},
    {"kind": "check", "conditions": [{"column": "size", "op": "missing"}], "action": "exclude"},
    {"kind": "duplicates", "columns": ["hh"]},
]


def make_project(call, tmp_path, name="kobo", df=KOBO):
    csv = tmp_path / f"{name}.csv"
    df.write_csv(csv)
    if not (tmp_path / "p.sme").exists():
        call("project.create", {"path": str(tmp_path / "p.sme"), "name": "Test"})
    return call("dataset.import", {"path": str(csv), "name": name, "round": "baseline"})["created"]


def test_service_derived_columns_report_and_stack(call, tmp_path):
    ds = make_project(call, tmp_path)
    for rule in ALL_RULES[:5]:
        snap = call("cleaning.add", {"dataset_id": ds, "rule": rule})
    entry = next(d for d in snap["datasets"] if d["id"] == ds)
    derived = {c["name"]: c for c in entry["derived_columns"]}
    assert list(derived) == ["duration", "quick", "age", "age_group", "members"]
    assert derived["duration"]["type"] == "number" and derived["age_group"]["type"] == "text"
    values = call("dataset.column_values", {"id": ds, "column": "age_group"})
    assert {v["value"] for v in values["values"]} == {"<18", "18+", None}
    # A created column can be used by the next rule, and its name cannot be taken twice.
    with pytest.raises(RuntimeError, match="already exists"):
        call("cleaning.add", {"dataset_id": ds, "rule": {**ALL_RULES[4]}})
    rid = entry["rules"][4]["id"]
    call("cleaning.update", {"id": rid, "rule": {"op": "max"}})  # its own name stays allowed

    # Stacking two files of the same structure; a column missing from one is empty there.
    other = make_project(call, tmp_path, "kobo_b", KOBO.drop("soap").head(2))
    dry = call("dataset.stack", {"sources": [ds, other], "name": "All", "dry_run": True})
    assert dry["stats"]["rows"] == 8 and dry["stats"]["missing_columns"]["kobo_b"][0] == "soap"
    snap = call("dataset.stack", {"sources": [ds, other], "name": "All", "round": "baseline"})
    stacked = next(d for d in snap["datasets"] if d["id"] == snap["created"])
    names = [c["name"] for c in stacked["columns"]]
    assert names[0] == "source_file" and "age_group" in names and stacked["clean_rows"] == 8
    with pytest.raises(RuntimeError, match="dataset_in_use"):
        call("dataset.delete", {"id": other})

    report = tmp_path / "r.docx"
    call("report.generate", {"path": str(report), "lang": "fr"})
    cells = [c.text for t in Document(report).tables for r in t.rows for c in r.cells]
    assert "Nouvelle variable « members » : maximum de « children », « adults »" in cells
    assert "5 valeurs calculées" in cells


@needs_r
def test_r_script_gives_the_same_table(call, tmp_path):
    ds = make_project(call, tmp_path)
    for rule in ALL_RULES:
        call("cleaning.add", {"dataset_id": ds, "rule": rule})
    out = call("cleaning.export_r", {"id": ds, "path": str(tmp_path / "nettoyage"), "lang": "fr"})
    assert out["path"].endswith("nettoyage.R") and out["data"].endswith("nettoyage_brut.csv")
    expected = tmp_path / "expected.csv"
    call("dataset.export", {"id": ds, "path": str(expected)})

    got = tmp_path / "got.csv"
    script = (
        f"setwd({json.dumps(str(tmp_path))})\n"
        f"source('nettoyage.R', encoding = 'UTF-8')\n"
        f"write.csv(clean, 'got.csv', row.names = FALSE, na = '', fileEncoding = 'UTF-8')\n"
    )
    subprocess.run([find_rscript(), "-e", script], check=True, capture_output=True, timeout=120)
    a = pl.read_csv(expected, infer_schema=False)
    b = pl.read_csv(got, infer_schema=False)
    assert a.columns == b.columns
    assert a.height == b.height
    for col in a.columns:
        left, right = a[col].to_list(), b[col].to_list()
        for x, y in zip(left, right, strict=True):
            try:
                assert abs(float(x) - float(y)) < 1e-6, col
            except (TypeError, ValueError):
                assert x == y, (col, x, y)


@pytest.mark.skipif(not os.environ.get("SME_FULL_DATA"), reason="full HDX files not downloaded")
def test_kobo_interview_duration_on_real_survey(call, tmp_path):
    path = Path(os.environ["SME_FULL_DATA"]) / "bgd_wash_baseline_2018.xlsx"
    call("project.create", {"path": str(tmp_path / "bgd.sme"), "name": "BGD"})
    ds = call("dataset.import", {"path": str(path), "sheet": "Dataset", "name": "BGD", "round": "baseline"})["created"]
    rule = {"kind": "date", "mode": "duration", "column": "start", "end": "end", "target": "duration"}
    call("cleaning.add", {"dataset_id": ds, "rule": rule})
    check = {
        "kind": "check",
        "conditions": [{"column": "duration", "op": "lt", "value": 15}],
        "action": "flag",
        "target": "quick",
    }
    snap = call("cleaning.add", {"dataset_id": ds, "rule": check})
    entry = next(d for d in snap["datasets"] if d["id"] == ds)
    dur = next(c for c in entry["derived_columns"] if c["name"] == "duration")
    assert dur["type"] == "number" and dur["missing"] == 0
    quick = entry["rules"][1]["effect"]["cells_changed"]
    assert 0 < quick < entry["clean_rows"]
