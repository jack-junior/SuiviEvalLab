"""Project file, framework, indicators, import and cleaning (no R needed)."""

from __future__ import annotations

import sqlite3
from pathlib import Path

import polars as pl
import pytest

from sme_engine import cleaning, datasets, indicators
from sme_engine.project import Project
from sme_engine.rpc import RpcError

EXAMPLES = Path(__file__).resolve().parents[1] / "sme_engine" / "examples"


def test_create_reopen_and_keep_changes(tmp_path):
    path = tmp_path / "projet"
    p = Project.create(path, "Mon projet")
    assert p.path.suffix == ".sme"
    impact = p.add_node(None, "Impact")["id"]
    o1 = p.add_node(impact, "Effet A")["id"]
    p.add_node(impact, "Effet B")
    p.add_node(o1, "Extrant A1")
    p.close()

    p2 = Project.open(tmp_path / "projet.sme")
    fw = p2.framework()
    assert [n["code"] for n in fw] == ["", "1", "1.1", "2"]
    assert [n["level"] for n in fw] == ["impact", "outcome", "output", "outcome"]
    assert p2.info()["name"] == "Mon projet"
    assert p2.info()["counts"]["outcome"] == 2


def test_move_and_cascade_delete(tmp_path):
    p = Project.create(tmp_path / "p.sme", "x")
    impact = p.add_node(None, "I")["id"]
    a = p.add_node(impact, "A")["id"]
    b = p.add_node(impact, "B")["id"]
    p.add_node(a, "A1")
    p.move_node(b, -1)
    assert [n["title"] for n in p.framework()] == ["I", "B", "A", "A1"]
    assert p.delete_node(a) == 2
    assert [n["title"] for n in p.framework()] == ["I", "B"]


def test_activities_have_no_children(tmp_path):
    p = Project.create(tmp_path / "p.sme", "x")
    n = p.add_node(None, "I")["id"]
    for _ in range(3):
        n = p.add_node(n, "x")["id"]
    with pytest.raises(RpcError) as exc:
        p.add_node(n, "trop profond")
    assert exc.value.data["key"] == "node_no_children"


def test_refuses_other_files(tmp_path):
    other = tmp_path / "autre.sme"
    sqlite3.connect(other).execute("CREATE TABLE t(x)").connection.close()
    with pytest.raises(RpcError) as exc:
        Project.open(other)
    assert exc.value.data["key"] == "project_invalid"
    text = tmp_path / "texte.sme"
    text.write_text("pas une base", encoding="utf-8")
    with pytest.raises(RpcError) as exc:
        Project.open(text)
    assert exc.value.data["key"] == "project_invalid"


def test_import_bundled_example_keeps_values_as_text():
    info = datasets.inspect(EXAMPLES / "mcna_irak_2019.xlsx")
    assert info["sheet"] == "Donnees menages"  # the read-me sheet is skipped
    assert info["design"]["weights"] == "weights"
    assert info["id_column"] == "X_uuid"
    df = datasets.load(EXAMPLES / "mcna_irak_2019.xlsx", "Donnees menages")
    assert df.height == 12887
    assert all(dt == pl.Utf8 for dt in df.dtypes)
    cols = {c["name"]: c for c in datasets.describe_columns(df, datasets.DEFAULT_NA)}
    assert cols["weights"]["type"] == "number"
    assert cols["population_group"]["type"] == "text"


def test_csv_with_semicolons(tmp_path):
    csv = tmp_path / "kobo.csv"
    csv.write_text("_uuid;age;statut\na;12;Oui\nb;NA;Non\n", encoding="utf-8")
    info = datasets.inspect(csv)
    assert info["columns"] == ["_uuid", "age", "statut"]
    df = datasets.load(csv, None)
    assert df.height == 2


def test_cleaning_rules_in_order():
    df = pl.DataFrame(
        {
            "id": ["1", "1", "2", "3", "4"],
            "age": ["12", "12", "250", "8", "NA"],
            "groupe": ["a", "a", "b", "hors", "b"],
            "rep": ["oui", "oui", "nsp", "non", "oui"],
        }
    )
    df = cleaning.missing_to_null(df, ["NA"])
    cols = df.columns
    rules = [
        cleaning.validate(r, cols) | {"id": str(i)}
        for i, r in enumerate(
            [
                {"kind": "duplicates", "columns": ["id"]},
                {"kind": "range", "column": "age", "min": 0, "max": 120},
                {"kind": "recode", "column": "rep", "from": ["nsp"], "to": None},
                {"kind": "exclude", "column": "groupe", "values": ["hors"]},
                {"kind": "exclude", "column": "age", "values": [None], "enabled": False},
            ]
        )
    ]
    out, effects = cleaning.apply(df, rules)
    assert out["id"].to_list() == ["1", "2", "4"]
    assert out["age"].to_list() == ["12", None, None]
    assert out["rep"].to_list() == ["oui", None, "oui"]
    assert [e["rows_removed"] for e in effects] == [1, 0, 0, 1, 0]
    assert [e["cells_changed"] for e in effects] == [0, 1, 1, 0, 0]
    assert effects[4]["applied"] is False


def test_cleaning_validation():
    with pytest.raises(RpcError):
        cleaning.validate({"kind": "range", "column": "x", "min": 5, "max": 1}, ["x"])
    with pytest.raises(RpcError):
        cleaning.validate({"kind": "recode", "column": "absente", "from": ["a"]}, ["x"])
    with pytest.raises(RpcError):
        cleaning.validate({"kind": "eval", "code": "import os"}, ["x"])


def test_indicator_validation_and_achievement():
    spec = indicators.validate(
        {"name": "Taux", "unit": "percent", "column": "x", "success_values": ["oui"], "target": 0.8}
    )
    assert spec["direction"] == "increase"
    with pytest.raises(RpcError):
        indicators.validate({"name": "Taux", "unit": "percent", "target": 80})
    assert indicators.achievement(0.5, 0.65, 0.8) == pytest.approx(0.5)
    assert indicators.status(0.5) == "late"
    assert indicators.status(0.7) == "on_track"
    assert indicators.status(0.95) == "achieved"
    # Baseline already beyond the target: the value decides.
    assert indicators.status(-2.0, 0.77, 0.65, "increase") == "achieved"
    assert indicators.status(1.08, 0.018, 0.02, "decrease") == "achieved"
