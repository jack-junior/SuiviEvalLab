# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 GAYI Komi Selassi and SANOUSSI Moudjibou

"""Free cleaning: formula language, filters, cells corrected in the data table,
R scripts (trusted on this computer only), and the journal as an R script."""

from __future__ import annotations

import io
import json
import subprocess

import polars as pl
import pytest

from sme_engine import cleaning, formula, formula_r, trust
from sme_engine.methods import register
from sme_engine.r_bridge import RBridge, find_rscript
from sme_engine.rpc import Server

needs_r = pytest.mark.skipif(find_rscript() is None, reason="R not installed")

DATA = pl.DataFrame(
    {
        "id": ["01", "02", "03", "04", "05"],
        "age": ["17", "25", None, "40", "70"],
        "sexe": ["F", "F", "M", "F", "M"],
        "start": ["2024-01-01T10:00:00.000+06", "2024-01-01T09:00:00", "2024-01-02 08:00:00", None, "02/01/2024"],
        "end": ["2024-01-01T10:45:30", "2024-01-01T09:20:00", "2024-01-02 09:00:00", "x", "03/01/2024"],
        "groupe/taille": ["5", "3", "4", "2", "1"],
        "rev": ["1000", "2,5", None, "10", "0"],
        "village": ["  Kofi  Kope ", "AKPAKPA", "éwé", None, "lome"],
    }
)


def value(text: str, df: pl.DataFrame = DATA) -> list:
    return df.with_columns(formula.value_expr(text, df.columns).alias("__x"))["__x"].to_list()


def test_formulas_give_text_values_like_the_rest_of_the_table():
    assert value('si(age >= 18 et sexe = "F"; 1; 0)') == ["0", "1", "0", "1", "0"]
    assert value("age >= 18") == ["0", "1", None, "1", "1"]  # a condition on a missing value is missing
    assert value("minutes_entre(date(start); date(end))") == ["45.5", "20", "60", None, "1440"]
    assert value("[groupe/taille] * 2 + somme(age; rev)") == [
        "1027",
        "33.5",
        None,
        "54",
        "72",
    ]
    assert value("rev / [groupe/taille]") == ["200", "0.833333", None, "5", "0"]
    assert value("arrondi(rev / 3; 1)") == ["333.3", "0.8", None, "3.3", "0"]
    assert value('si(age > 30; "senior")') == [None, None, None, "senior", "senior"]
    assert value('sexe & "-" & age') == ["F-17", "F-25", "M-", "F-40", "M-70"]
    assert value("majuscule(nettoyer(village))") == ["KOFI KOPE", "AKPAKPA", "ÉWÉ", None, "LOME"]
    assert value('dans(sexe; "F")') == ["1", "1", "0", "1", "0"]
    assert value("est_manquant(age) ou age > 60") == ["0", "0", "1", "0", "1"]
    assert value("si_manquant(age; 0)") == ["17", "25", "0", "40", "70"]
    assert value("age - moyenne_colonne(age)") == ["-21", "-13", None, "2", "32"]
    assert value("annee(start)") == ["2024", "2024", "2024", None, "2024"]
    assert value('age(date("2000-06-15"); date("2024-06-14"))') == ["23"] * 5
    # English names and operators work too.
    assert value('if(age >= 18 and sexe == "F", 1, 0)') == ["0", "1", "0", "1", "0"]
    assert value('compter("F"; sexe; sexe)') == ["2", "2", "0", "2", "0"]
    # Codes stay codes: comparing a column with a text compares texts.
    assert value('id = "01"') == ["1", "0", "0", "0", "0"]
    assert value("id = 1") == ["1", "0", "0", "0", "0"]


@pytest.mark.parametrize(
    ("text", "reason", "info"),
    [
        ("si(age > 18; 1", "missing_parenthesis", {}),
        ("agee + 1", "unknown_column", {"name": "agee", "suggestion": "age"}),
        ('sexe < "F"', "compare_text", {}),
        ("sii(age; 1)", "unknown_function", {"name": "sii", "suggestion": "si"}),
        ('"abc', "unclosed_text", {}),
        ("1 +", "unexpected_end", {}),
        ("somme()", "arguments", {"name": "somme"}),
        ('age + "a"', "text_in_calculation", {}),
        ("", "empty", {}),
        ("age $ 2", "unexpected_sign", {"sign": "$"}),
        ("[groupe", "unclosed_column", {}),
        ("contient(village; sexe)", "literal_expected", {}),
    ],
)
def test_formula_errors_say_what_and_where(text, reason, info):
    with pytest.raises(formula.FormulaError) as e:
        formula.check(text, DATA.columns)
    assert e.value.reason == reason
    assert e.value.data["key"] == "formula_invalid"
    for k, v in info.items():
        assert e.value.info[k] == v


def test_condition_check_and_preview():
    with pytest.raises(formula.FormulaError):
        formula.check('concat(sexe; "x")', DATA.columns, condition=True)
    p = formula.preview(DATA, "age >= 18", condition=True)
    assert (p["true"], p["false"], p["rows"]) == (3, 2, 5)
    p = formula.preview(DATA, "age * 2")
    assert p["type"] == "num" and p["missing"] == 1 and p["sample"][0] == {"inputs": {"age": "17"}, "value": "34"}


def test_formula_filter_and_edit_rules():
    rules = [
        {"kind": "formula", "target": "adulte", "expression": "si(age >= 18; 1; 0)"},
        {"kind": "formula", "target": "age", "expression": "si(age > 65; manquant; age)"},  # an existing column
        {"kind": "filter", "expression": "non_manquant(age)", "action": "keep"},
        {
            "kind": "edit",
            "cells": [{"row": 2, "column": "sexe", "value": "M"}, {"row": 3, "column": "sexe", "value": "F"}],
        },
        {"kind": "filter", "expression": 'sexe = "M"', "action": "drop"},
    ]
    cols, valid = list(DATA.columns), []
    for i, r in enumerate(rules):
        v = cleaning.validate(r, cols)
        v["id"] = i
        valid.append(v)
        cols += [c for c in cleaning.new_columns(v) if c not in cols]
    df, effects = cleaning.apply(DATA, valid)
    assert df["id"].to_list() == ["01", "04"]  # 03 had no age, 05 became missing, 02 corrected to M
    assert df["adulte"].to_list() == ["0", "1"]
    assert [e.get("cells_changed") for e in effects[:2]] == [5, 1]
    assert effects[2]["rows_removed"] == 2
    assert effects[3]["cells_changed"] == 1  # row 3 was already removed
    assert effects[4]["rows_removed"] == 1
    assert cleaning.ROW not in df.columns


# ----- through the service -----------------------------------------------------------


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


def make_project(call, tmp_path):
    csv = tmp_path / "data.csv"
    DATA.write_csv(csv)
    call("project.create", {"path": str(tmp_path / "p.sme"), "name": "Test"})
    return call("dataset.import", {"path": str(csv), "name": "Menages", "round": "baseline"})["created"]


def test_data_table_corrections_go_to_the_journal(call, tmp_path):
    ds = make_project(call, tmp_path)
    call("cleaning.add", {"dataset_id": ds, "rule": {"kind": "filter", "expression": "age < 60"}})
    page = call("dataset.rows", {"id": ds, "limit": 10})
    assert page["row_numbers"] == [1, 2, 4] and page["total"] == 3
    assert page["columns"][0] == "id" and "__row" not in page["columns"]
    # Two corrections, then a third one on the same cell: one journal step, first old value kept.
    call("cleaning.edit_cells", {"dataset_id": ds, "cells": [{"row": 4, "column": "age", "value": "41"}]})
    snap = call(
        "cleaning.edit_cells",
        {
            "dataset_id": ds,
            "cells": [{"row": 4, "column": "age", "value": "42"}, {"row": 1, "column": "sexe", "value": ""}],
        },
    )
    rules = snap["datasets"][0]["rules"]
    assert [r["kind"] for r in rules] == ["filter", "edit"]
    cells = {(c["row"], c["column"]): c for c in rules[1]["cells"]}
    assert cells[(4, "age")] == {"row": 4, "column": "age", "value": "42", "old": "40"}
    assert cells[(1, "sexe")]["value"] is None
    assert rules[1]["effect"]["cells_changed"] == 2
    assert "ligne 4, « age » : 40 → 42" in rules[1]["description"]["fr"]
    page = call("dataset.rows", {"id": ds, "filter": 'sexe = "F"', "sort": {"column": "age", "descending": True}})
    assert page["filtered"] == 2 and page["rows"][0][1] == "42"
    page = call("dataset.rows", {"id": ds, "sort": {"column": "age", "descending": True}})
    assert page["row_numbers"] == [4, 2, 1]  # sorted as numbers: 42, 25, 17
    assert "4|age" in page["edited"]
    with pytest.raises(RuntimeError, match="row_not_found"):
        call("cleaning.edit_cells", {"dataset_id": ds, "cells": [{"row": 3, "column": "age", "value": "1"}]})
    with pytest.raises(RuntimeError, match="formula_invalid"):
        call("cleaning.add", {"dataset_id": ds, "rule": {"kind": "formula", "target": "x", "expression": "agee"}})
    p = call("formula.preview", {"dataset_id": ds, "expression": "age >= 18", "condition": True})
    assert p["true"] == 2 and p["rows"] == 3
    assert any(f["fr"] == "jours_entre" for f in call("formula.functions")["functions"])


@needs_r
def test_r_script_runs_only_when_trusted_here(call, tmp_path, trust_dir):
    ds = make_project(call, tmp_path)
    code = "data$age2 <- data$age * 2\ndata <- data[order(-data$age), ]\nprint(nrow(data))"
    snap = call("cleaning.add", {"dataset_id": ds, "rule": {"kind": "r_script", "code": code}})
    entry = snap["datasets"][0]
    rule = entry["rules"][0]
    assert rule["trusted"] is True and rule["effect"]["columns_added"] == ["age2"]
    assert "5" in rule["effect"]["log"]
    assert [c["name"] for c in entry["derived_columns"]] == ["age2"]
    # Rows keep their number in the file after the script reordered them; 01 stays 01.
    page = call("dataset.rows", {"id": ds})
    assert page["row_numbers"][0] == 5 and page["rows"][0][0] == "05"
    assert call("dataset.column_values", {"id": ds, "column": "age2"})["total"] == 5
    # The next rule can use the column the script created.
    call("cleaning.add", {"dataset_id": ds, "rule": {"kind": "formula", "target": "x", "expression": "age2 + 1"}})
    call("cleaning.edit_cells", {"dataset_id": ds, "cells": [{"row": 2, "column": "age", "value": "26"}]})

    # The same project opened on another computer (empty trust list): the script is paused.
    call("project.close")
    trust.path().unlink()
    snap = call("project.open", {"path": str(tmp_path / "p.sme")})
    entry = snap["datasets"][0]
    assert entry["rules"][0]["trusted"] is False and entry["rules"][0]["effect"]["paused"] is True
    assert snap["untrusted_scripts"] == [
        {"where": "cleaning", "id": entry["rules"][0]["id"], "dataset": "Menages", "code": code}
    ]
    assert entry["rules"][1]["effect"]["applied"] is False  # waits for age2
    assert entry["rules"][2]["effect"]["cells_changed"] == 1  # the rest of the journal runs
    snap = call("scripts.trust", {"ids": [entry["rules"][0]["id"]]})
    assert snap["untrusted_scripts"] == [] and snap["datasets"][0]["rules"][1]["effect"].get("cells_changed") == 4

    # An error in the script is reported, the table stays as before the step.
    rid = entry["rules"][0]["id"]
    snap = call("cleaning.update", {"id": rid, "rule": {"code": 'stop("colonne absente")'}})
    eff = snap["datasets"][0]["rules"][0]["effect"]
    assert eff["applied"] is False and "colonne absente" in eff["message"]


@needs_r
def test_exported_r_script_gives_the_same_table_with_free_steps(call, tmp_path):
    ds = make_project(call, tmp_path)
    for rule in [
        {"kind": "formula", "target": "adulte", "expression": 'si(age >= 18 et sexe = "F"; 1; 0)'},
        {"kind": "formula", "target": "duree", "expression": "minutes_entre(date(start); date(end))"},
        {"kind": "formula", "target": "taille2", "expression": "[groupe/taille] * 2 + somme(age; rev)"},
        {"kind": "formula", "target": "ratio", "expression": "arrondi(rev / [groupe/taille]; 3)"},
        {"kind": "formula", "target": "nom", "expression": 'majuscule(nettoyer(village)) & "-" & sexe'},
        {"kind": "formula", "target": "senior", "expression": 'si(age > 30; "oui"; "non")'},
        {"kind": "formula", "target": "manque", "expression": 'est_manquant(age) ou dans(sexe; "M")'},
        {"kind": "r_script", "code": "data$age3 <- data$age + 1\ndata <- data[!is.na(data$age), ]"},
        {"kind": "filter", "expression": "age < 65"},
    ]:
        call("cleaning.add", {"dataset_id": ds, "rule": rule})
    call("cleaning.edit_cells", {"dataset_id": ds, "cells": [{"row": 2, "column": "village", "value": "Akpakpa"}]})
    out = call("cleaning.export_r", {"id": ds, "path": str(tmp_path / "nettoyage"), "lang": "fr"})
    expected = tmp_path / "expected.csv"
    call("dataset.export", {"id": ds, "path": str(expected)})
    script = (
        f"setwd({json.dumps(str(tmp_path))})\nsource('nettoyage.R', encoding = 'UTF-8')\n"
        "write.csv(clean, 'got.csv', row.names = FALSE, na = '', fileEncoding = 'UTF-8')\n"
    )
    r = subprocess.run([find_rscript(), "-e", script], capture_output=True, text=True, timeout=120)
    assert r.returncode == 0, r.stderr + open(out["path"], encoding="utf-8").read()
    a = pl.read_csv(expected, infer_schema=False)
    b = pl.read_csv(tmp_path / "got.csv", infer_schema=False)
    assert a.columns == b.columns and a.height == b.height == 3
    assert a.to_dicts() == b.to_dicts()


def test_r_translation_of_conditions():
    assert (
        formula_r.condition("age >= 18", ["age"])
        == '(!is.na((sme_num(trimws(d[["age"]])) >= 18)) & (sme_num(trimws(d[["age"]])) >= 18))'
    )
