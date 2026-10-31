"""End-to-end engine flow on real data: example project, analysis in R, Word report.

The reference values are recomputed here independently (weighted shares with
polars) so the R results are checked against a second implementation.
"""

from __future__ import annotations

import io
import json
import os
from pathlib import Path

import polars as pl
import pytest
from docx import Document

from sme_engine.methods import register
from sme_engine.r_bridge import RBridge, find_rscript
from sme_engine.rpc import Server

needs_r = pytest.mark.skipif(find_rscript() is None, reason="R not installed")
EXAMPLES = Path(__file__).resolve().parents[1] / "sme_engine" / "examples"


@pytest.fixture()
def engine():
    bridge = RBridge()
    server = Server(stdin=io.StringIO(), stdout=io.StringIO())
    register(server, bridge)

    def call(method, params=None):
        resp = server.handle_line(json.dumps({"jsonrpc": "2.0", "id": 1, "method": method, "params": params or {}}))
        assert "error" not in resp, resp.get("error")
        return resp["result"]

    yield call
    bridge.stop()


def weighted_share(file: str, column: str, success: str, excluded_groups=(), missing=()) -> float:
    df = pl.read_excel(EXAMPLES / file, sheet_name="Donnees menages", infer_schema_length=0)
    df = df.filter(~pl.col("population_group").is_in(list(excluded_groups)))
    df = df.filter(pl.col(column).is_not_null() & ~pl.col(column).is_in(["NA", *missing]))
    w = df["weights"].cast(pl.Float64)
    return float((w * (df[column] == success).cast(pl.Float64)).sum() / w.sum())


@needs_r
def test_example_project_analysis_and_report(engine, tmp_path):
    snap = engine("project.create", {"path": str(tmp_path / "exemple.sme"), "name": "x", "example": True})
    assert len(snap["framework"]) == 8
    assert len(snap["indicators"]) == 3
    base, end = snap["datasets"]
    assert (base["rows"], base["clean_rows"]) == (12887, 8952)
    assert (end["rows"], end["clean_rows"]) == (3872, 3872)

    overview = engine("analysis.overview")["rows"]
    primary = overview[0]
    expected_base = weighted_share(
        "mcna_irak_2019.xlsx", "primary_school_place", "within_2km", ("idp_in_camp", "host"), ("do_not_know",)
    )
    expected_end = weighted_share("mcna_irak_2020.xlsx", "primary_school_place", "within_2km", (), ("do_not_know",))
    assert primary["baseline"] == pytest.approx(expected_base, abs=1e-9)
    assert primary["current"] == pytest.approx(expected_end, abs=1e-9)
    assert primary["status"] in ("achieved", "on_track", "late")

    dropout = engine("analysis.indicator", {"id": snap["indicators"][2]["id"]})
    comp = dropout["comparison"]
    assert comp["test_key"] == "z_survey_prop"
    assert comp["ci_low"] < comp["difference"] < comp["ci_high"]
    assert 0 <= comp["p_value"] <= 1
    groups = {g["group"] for g in dropout["rounds"][0]["result"]["by"]}
    assert groups == {"idp_out_camp", "returnee"}

    # Changing the journal changes the results (and the cache follows).
    rule = next(r for r in snap["datasets"][0]["rules"] if r["kind"] == "exclude")
    engine("cleaning.update", {"id": rule["id"], "rule": {"enabled": False}})
    again = engine("analysis.overview")["rows"][0]
    assert again["baseline"] != pytest.approx(primary["baseline"], abs=1e-9)

    for lang in ("fr", "en"):
        out = engine("report.generate", {"path": str(tmp_path / f"rapport_{lang}"), "lang": lang})
        doc = Document(out["path"])
        text = "\n".join(p.text for p in doc.paragraphs)
        assert ("Synthèse" if lang == "fr" else "Summary") in text
        assert "REACH Initiative" in text
        assert len(doc.inline_shapes) == 3  # one chart per indicator
        for forbidden in ("—", "–"):  # writing conventions: no em or en dash
            assert forbidden not in text


@needs_r
def test_export_cleaned_data(engine, tmp_path):
    snap = engine("project.create", {"path": str(tmp_path / "e.sme"), "name": "x", "example": True})
    out = engine("dataset.export", {"id": snap["datasets"][0]["id"], "path": str(tmp_path / "propre.csv")})
    df = pl.read_csv(out["path"], infer_schema=False)
    assert df.height == 8952


@pytest.mark.skipif(not os.environ.get("SME_FULL_DATA"), reason="full HDX files not downloaded")
def test_import_full_hdx_files():
    """Robustness on the original files (hundreds of columns, several sheets)."""
    from sme_engine import datasets

    folder = Path(os.environ["SME_FULL_DATA"])
    for name in sorted(folder.glob("*.xlsx")):
        info = datasets.inspect(name)
        df = datasets.load(name, info["sheet"])
        assert df.height > 100, name
        assert len(df.columns) > 50, name


@needs_r
def test_indicator_types_on_real_data(engine, tmp_path):
    """Count, ratio, two conditions and a crossed breakdown, checked against polars."""
    snap = engine("project.create", {"path": str(tmp_path / "t.sme"), "name": "x", "example": True})
    node = snap["indicators"][0]["node_id"]
    base = snap["datasets"][0]
    raw = pl.read_excel(EXAMPLES / "mcna_irak_2019.xlsx", sheet_name="Donnees menages", infer_schema_length=0)
    raw = raw.filter(~pl.col("population_group").is_in(["idp_in_camp", "host"]))
    w = raw["weights"].cast(pl.Float64)

    def save(spec):
        out = engine("indicator.save", {"node_id": node, "indicator": spec})
        return engine("analysis.indicator", {"id": out["saved"]})

    # Two conditions: primary AND secondary school within 2 km (weighted share).
    both = save(
        {
            "name": "Deux écoles proches",
            "unit": "percent",
            "conditions": [
                {"column": "primary_school_place", "values": ["within_2km"]},
                {"column": "secondary_school_place", "values": ["within_2km"]},
            ],
            "combine": "all",
            "disaggregation": "population_group",
            "disaggregation2": "governorate_mcna",
        }
    )
    ok = raw.filter(
        ~pl.col("primary_school_place").is_in(["do_not_know"])
        & ~pl.col("secondary_school_place").is_in(["do_not_know"])
    )
    wk = ok["weights"].cast(pl.Float64)
    hit = ((ok["primary_school_place"] == "within_2km") & (ok["secondary_school_place"] == "within_2km")).cast(
        pl.Float64
    )
    assert both["rounds"][0]["result"]["estimate"] == pytest.approx(float((wk * hit).sum() / wk.sum()), abs=1e-9)
    groups = {g["group"] for g in both["rounds"][0]["result"]["by"]}
    assert "returnee / ninewa" in groups
    assert "y <- as.numeric(" in both["rounds"][0]["result"]["script"]

    # Count of households with a child withdrawn, weighted: estimated number of households.
    count = save(
        {
            "name": "Ménages ayant retiré un enfant",
            "unit": "count",
            "conditions": [{"column": "child_dropout_school", "values": ["yes"]}],
        }
    )
    expected = float((w * (raw["child_dropout_school"] == "yes").cast(pl.Float64)).sum())
    assert count["rounds"][0]["result"]["estimate"] == pytest.approx(expected, rel=1e-9)
    assert count["rounds"][0]["result"]["method_key"] == "survey_total"
    assert count["comparison"]["test_key"] == "z_survey_total"

    # Ratio: children per household, per 100 households (weighted).
    ratio = save(
        {
            "name": "Enfants pour 100 ménages",
            "unit": "ratio",
            "numerator": "tot_child",
            "denominator": "weights",
            "multiplier": 100,
        }
    )
    assert ratio["rounds"][0]["result"]["method_key"] == "survey_ratio"
    tc = raw["tot_child"].cast(pl.Float64)
    expected = float((w * tc).sum() / (w * w).sum()) * 100
    assert ratio["rounds"][0]["result"]["estimate"] == pytest.approx(expected, rel=1e-9)
    assert base["id"] == ratio["rounds"][0]["dataset_id"]
