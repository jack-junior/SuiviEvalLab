"""End-to-end engine flow on real data: example project, analysis in R, Word report.

The reference values are recomputed here independently (weighted shares with
polars) so the R results are checked against a second implementation.
"""

from __future__ import annotations

import html
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
    assert len(snap["indicators"]) == 4
    routine_ind = next(i for i in snap["indicators"] if i["source_type"] == "routine")
    an = engine("analysis.indicator", {"id": routine_ind["id"]})
    assert an["current"] == 19 and an["planned_to_date"] == 25 and an["status"] == "late"
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

    dropout_id = next(i["id"] for i in snap["indicators"] if i.get("column") == "child_dropout_school")
    dropout = engine("analysis.indicator", {"id": dropout_id})
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
        assert len(doc.inline_shapes) == 4  # one chart per indicator
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
    # 2019 weights expand to the population, 2020 weights are normalised: counts are not comparable.
    assert count["comparison"]["warning"] == "weights_scale"
    keys = {i["key"] for i in engine("report.checks")["items"]}
    assert "count_weights_scale" in keys

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


@needs_r
def test_test_assistant_on_real_data(engine, tmp_path):
    snap = engine("project.create", {"path": str(tmp_path / "t.sme"), "name": "x", "example": True})
    base, end = snap["datasets"]
    groups = {
        "question": "groups",
        "kind": "proportion",
        "dataset_id": base["id"],
        "outcome": {"column": "primary_school_place", "values": ["within_2km"]},
        "group": "population_group",
        "title": "Accès selon le groupe",
    }
    out = engine("test.run", {"test": groups})
    assert out["result"]["test_key"] == "rao_scott"
    assert 0 <= out["result"]["p_value"] <= 1
    assert "Déplacés hors camp" in " ".join(out["conclusion"]["fr"])
    assert "IDPs out of camp" in " ".join(out["conclusion"]["en"])

    target = {
        "question": "target",
        "kind": "proportion",
        "dataset_id": end["id"],
        "outcome": {"column": "child_dropout_school", "values": ["yes"]},
        "target": 0.02,
    }
    out = engine("test.run", {"test": target})
    assert out["result"]["test_key"] == "z_target_prop"

    paired = {
        "question": "paired",
        "kind": "proportion",
        "dataset_id": base["id"],
        "mode": "columns",
        "outcome": {"column": "primary_school_place", "values": ["within_2km"]},
        "column_b": "secondary_school_place",
    }
    out = engine("test.run", {"test": paired})
    assert out["result"]["test_key"] in ("mcnemar", "mcnemar_exact")

    # Two different survey rounds share no household: pairing fails clearly.
    with pytest.raises(AssertionError):
        engine("test.run", {"test": {**paired, "mode": "datasets", "dataset_b_id": end["id"]}})

    saved = engine("test.save", {"test": groups})
    assert len(saved["tests"]) == 1
    report = engine("report.generate", {"path": str(tmp_path / "r.docx"), "lang": "fr"})
    text = "\n".join(p.text for p in Document(report["path"]).paragraphs)
    assert "Analyses complémentaires" in text
    assert "Accès selon le groupe" in text

    # A project saved by version 0.2 (schema 1) opens and gains the new table.
    import sqlite3

    old = tmp_path / "ancien.sme"
    engine("project.create", {"path": str(old), "name": "ancien"})
    engine("project.close")
    con = sqlite3.connect(old)
    con.execute("DROP TABLE saved_test")
    con.execute("PRAGMA user_version = 1")
    con.commit()
    con.close()
    assert engine("project.open", {"path": str(old)})["tests"] == []


@needs_r
def test_report_on_organisation_template(engine, tmp_path):
    """The organisation's template keeps its header and texts; results go at {{contenu}}."""
    engine("project.create", {"path": str(tmp_path / "t.sme"), "name": "x", "example": True})
    template = Path(__file__).parent / "fixtures" / "modele_organisation.docx"
    out = engine("report.set_template", {"path": str(template)})
    assert out["has_anchor"] is True
    assert out["project"]["report_template"] == "modele_organisation.docx"
    report = Document(engine("report.generate", {"path": str(tmp_path / "r.docx"), "lang": "fr"})["path"])
    texts = [p.text for p in report.paragraphs]
    order = {t: i for i, t in enumerate(texts)}
    assert order["Résumé exécutif"] < order["1. Synthèse"] < order["Recommandations"]
    assert not any("{{" in t for t in texts)
    assert "ONG Exemple" in report.sections[0].header.paragraphs[0].text
    assert "Accès à l'éducation" in report.sections[0].header.paragraphs[0].text
    engine("report.clear_template")
    assert engine("project.get")["project"]["report_template"] is None


@pytest.mark.parametrize("ext", ["sav", "dta"])
def test_import_spss_and_stata_with_labels(engine, tmp_path, ext):
    """SPSS and Stata files built from real Bangladesh WASH data (REACH 2018): codes and labels kept."""
    engine("project.create", {"path": str(tmp_path / "s.sme"), "name": "x"})
    path = Path(__file__).parent / "fixtures" / f"wash_bgd_2018.{ext}"
    info = engine("dataset.inspect", {"path": str(path)})
    assert info["columns"][:3] == ["uuid", "camp_id", "enu_gen"] and info["sample"][0][1] == "19"
    snap = engine("dataset.import", {"path": str(path), "name": "WASH", "round": "baseline"})
    ds = next(d for d in snap["datasets"] if d["id"] == snap["created"])
    assert ds["rows"] == 600
    labels = ds["labels"]
    assert labels["columns"]["res_age"]["default"] == "How old are you?"
    assert labels["values"]["drnk_wat"]["2"]["default"] == "Tubewells/borehole/handpump"
    # Codes stay the reference: whole numbers written as typed ("2", not "2.0").
    values = engine("dataset.column_values", {"id": ds["id"], "column": "drnk_wat"})
    codes = {v["value"] for v in values["values"]}
    assert "2" in codes and not any(c.endswith(".0") for c in codes)
    # Numeric columns keep their values (ages from the original file).
    age = engine("dataset.column_values", {"id": ds["id"], "column": "res_age"})
    assert age["stats"] and 15 <= age["stats"]["min"] and age["stats"]["max"] < 120


def test_merge_containers_with_households(engine, tmp_path):
    """Kobo repeat joined to its household (real WASH data): counts, columns, weights, labels, refresh."""
    engine("project.create", {"path": str(tmp_path / "m.sme"), "name": "x"})
    path = str(Path(__file__).parent / "fixtures" / "wash_bgd_containers.xlsx")
    hh = engine("dataset.import", {"path": path, "name": "Ménages", "sheet": "Menages"})["created"]
    ct = engine("dataset.import", {"path": path, "name": "Contenants", "sheet": "Contenants"})["created"]
    engine("dataset.set_labels", {"id": hh, "column": "reported_camp_name", "lang": "fr", "label": "Camp"})
    engine("dataset.update", {"id": hh, "design": {"weights": "Camp weights", "strata": ["reported_camp_name"]}})

    households = pl.read_excel(path, sheet_name="Menages", infer_schema_length=0)
    containers = pl.read_excel(path, sheet_name="Contenants", infer_schema_length=0)
    known = set(households["_index"].to_list())
    expected = int(containers["_parent_index"].is_in(list(known)).sum())

    params = {"left": ct, "right": hh, "left_key": "_parent_index", "right_key": "_index", "name": "C + M"}
    snap = engine("dataset.merge", params)
    m = next(d for d in snap["datasets"] if d["id"] == snap["created"])
    stats = m["merge"]["stats"]
    assert m["rows"] == containers.height == stats["rows"]
    assert stats["matched"] == expected and stats["left_unmatched"] == containers.height - expected
    names = [c["name"] for c in m["columns"]]
    # The household index clashes with the container index: it takes a suffix; the right key is dropped.
    assert "_index" in names and "Camp weights" in names and "reported_camp_name" in names
    # Containers carry no weight: the household design comes with the household.
    assert m["design"] == {"weights": "Camp weights", "strata": ["reported_camp_name"], "cluster": None}
    assert m["labels"]["columns"]["reported_camp_name"] == {"fr": "Camp"}

    # Each container carries the camp of its household.
    rows = engine("dataset.preview", {"id": m["id"], "limit": 200, "columns": ["_parent_index", "reported_camp_name"]})
    camp = dict(zip(households["_index"], households["reported_camp_name"], strict=True))
    for parent, name in rows["rows"]:
        assert name == camp.get(parent)

    # Inner join keeps matched rows only; a correction in the household file reaches the merged file.
    inner = engine("dataset.merge", {**params, "how": "inner", "name": "inner"})
    i = next(d for d in inner["datasets"] if d["id"] == inner["created"])
    assert i["clean_rows"] == expected
    engine("cleaning.add", {"dataset_id": hh, "rule": {"kind": "exclude", "column": "_index", "values": ["116"]}})
    after = engine("project.get")
    i = next(d for d in after["datasets"] if d["id"] == i["id"])
    assert i["clean_rows"] == expected - int((containers["_parent_index"] == "116").sum())

    # A source used by a merged file cannot be deleted; the other way works.
    server_error = None
    try:
        engine("dataset.delete", {"id": hh})
    except AssertionError as exc:
        server_error = str(exc)
    assert server_error and "dataset_in_use" in server_error


def test_merge_refuses_a_repeated_key(engine, tmp_path):
    """Duplicated parent keys (the BGD follow-up file appends two form versions) are refused, not multiplied."""
    engine("project.create", {"path": str(tmp_path / "r.sme"), "name": "x"})
    path = str(Path(__file__).parent / "fixtures" / "wash_bgd_containers.xlsx")
    hh = engine("dataset.import", {"path": path, "name": "M", "sheet": "Menages"})["created"]
    ct = engine("dataset.import", {"path": path, "name": "C", "sheet": "Contenants"})["created"]
    with pytest.raises(AssertionError, match="merge_key_repeats"):
        # Households to containers: a household has several containers, so the key repeats.
        engine(
            "dataset.merge", {"left": hh, "right": ct, "left_key": "_index", "right_key": "_parent_index", "name": "x"}
        )


@pytest.mark.skipif(not os.environ.get("SME_FULL_DATA"), reason="full HDX files not downloaded")
def test_merge_on_full_bangladesh_files(engine, tmp_path):
    """Baseline: 5,476 containers, 5,438 with their household. Follow-up: duplicated _index refused."""
    folder = Path(os.environ["SME_FULL_DATA"])
    engine("project.create", {"path": str(tmp_path / "f.sme"), "name": "x"})
    base = str(folder / "bgd_wash_baseline_2018.xlsx")
    hh = engine("dataset.import", {"path": base, "name": "M", "sheet": "Dataset"})["created"]
    ct = engine("dataset.import", {"path": base, "name": "C", "sheet": "Dataset_containergroup"})["created"]
    snap = engine(
        "dataset.merge", {"left": ct, "right": hh, "left_key": "_parent_index", "right_key": "_index", "name": "x"}
    )
    m = next(d for d in snap["datasets"] if d["id"] == snap["created"])
    assert m["merge"]["stats"]["rows"] == 5476 and m["merge"]["stats"]["matched"] == 5438

    follow = str(folder / "bgd_wash_followup_2018.xlsx")
    fh = engine("dataset.import", {"path": follow, "name": "M2", "sheet": "Household Dataset"})["created"]
    fi = engine("dataset.import", {"path": follow, "name": "I2", "sheet": "Individuals Dataset"})["created"]
    with pytest.raises(AssertionError, match="merge_key_repeats"):
        engine(
            "dataset.merge", {"left": fi, "right": fh, "left_key": "_parent_index", "right_key": "_index", "name": "y"}
        )


@needs_r
def test_read_only_dashboard_holds_results_only(engine, tmp_path):
    """Self-contained HTML: every indicator, no external resource, no data row, small groups hidden."""
    snap = engine("project.create", {"path": str(tmp_path / "d.sme"), "name": "x", "example": True, "lang": "fr"})
    # A breakdown with tiny groups: districts by population group.
    ind = snap["indicators"][0]
    spec = {k: v for k, v in ind.items() if k not in ("id", "node_id")}
    engine(
        "indicator.save",
        {"id": ind["id"], "indicator": {**spec, "disaggregation": "district", "disaggregation2": "population_group"}},
    )
    out = engine("report.share", {"path": str(tmp_path / "tableau"), "lang": "fr"})
    page = Path(out["path"]).read_text(encoding="utf-8")
    assert out["path"].endswith(".html") and out["indicators"] == len(snap["indicators"])
    for i in snap["indicators"]:
        assert html.escape(i["name"]) in page
    assert "<svg" in page and "Lecture seule" in page
    assert "http://" not in page.replace("http://www.w3.org/2000/svg", "") and "https://" not in page
    assert "<details>" in page and "al.adhamiya / Déplacés hors camp" in page
    # No identifier or raw value from the data file reaches the page.
    raw = pl.read_excel(EXAMPLES / "mcna_irak_2019.xlsx", sheet_name="Donnees menages", infer_schema_length=0)
    id_col = next(c for c in raw.columns if "uuid" in c.lower())
    assert not any(v in page for v in raw[id_col].drop_nulls().head(200).to_list())
    en = engine("report.share", {"path": str(tmp_path / "board.html"), "lang": "en"})
    assert "Read only" in Path(en["path"]).read_text(encoding="utf-8")


def test_dashboard_hides_small_groups():
    from sme_engine import share
    from sme_engine.report import Fmt

    ind = {"unit": "percent", "disaggregation": "camp"}
    rounds = [
        {
            "round": "baseline",
            "result": {"by": [{"group": "a", "estimate": 0.5, "n": 120}, {"group": "b", "estimate": 1.0, "n": 3}]},
        }
    ]
    out = share._breakdown(ind, rounds, share.S["fr"], Fmt("fr"), lambda c, v=None: v or c)
    assert "50,0\u202f%" in out and "100,0" not in out and "moins de 5 obs." in out


@needs_r
def test_checks_before_the_report(engine, tmp_path):
    snap = engine("project.create", {"path": str(tmp_path / "c.sme"), "name": "x", "example": True, "lang": "fr"})
    clean = engine("report.checks")
    assert clean["warnings"] == 0, clean["items"]
    ind = snap["indicators"][0]
    spec = {k: v for k, v in ind.items() if k not in ("id", "node_id")}
    engine("indicator.save", {"id": ind["id"], "indicator": {**spec, "target": None}})
    node = snap["indicators"][1]["node_id"]
    engine("indicator.save", {"node_id": node, "indicator": {"name": "Sans règle", "unit": "percent"}})
    keys = {(i["key"], i["name"]) for i in engine("report.checks")["items"]}
    assert ("indicator_no_target", ind["name"]) in keys
    assert ("indicator_incomplete", "Sans règle") in keys


@needs_r
def test_sample_size_without_project(engine):
    r = engine("tool.sample_size", {"goal": "estimate_prop", "p": 0.5, "margin": 0.05, "deff": 2, "response": 0.9})
    assert r["n"] == 854 and r["method_key"] == "cochran_prop"  # ceil(384.15 * 2 / 0.9)
    r = engine("tool.sample_size", {"goal": "compare_prop", "p": 0.4, "p2": 0.5})
    assert r["per_round"] and r["n"] == 388


@needs_r
def test_monitoring_plan_workbook(engine, tmp_path):
    snap = engine("project.create", {"path": str(tmp_path / "p.sme"), "name": "x", "example": True, "lang": "fr"})
    ind = snap["indicators"][0]
    spec = {k: v for k, v in ind.items() if k not in ("id", "node_id")}
    extra = {
        "frequency": "rounds",
        "responsible": "Chargé de S&E",
        "method": "Enquête ménages",
        "target_date": "2027-06",
    }
    engine("indicator.save", {"id": ind["id"], "indicator": {**spec, **extra}})
    out = engine("report.plan", {"path": str(tmp_path / "plan"), "lang": "fr"})
    assert out["path"].endswith(".xlsx")
    sheet = pl.read_excel(out["path"], sheet_name="Plan de suivi", read_options={"header_row": 3})
    assert sheet.height == len(snap["indicators"])
    first = sheet.row(0, named=True)
    assert first["Indicateur"] == ind["name"] and first["Responsable"] == "Chargé de S&E"
    assert first["Fréquence"].startswith("À chaque enquête") and first["Échéance de la cible"] == "2027-06"
    assert first["Mode de calcul"].startswith("Part des observations où")
    assert "À moins de 2 km" in first["Mode de calcul"]  # labels, not codes
    assert first["Cible"] == "90,0 %"
    fw = pl.read_excel(out["path"], sheet_name="Cadre de résultats")
    assert fw.height == len(snap["framework"])
    with pytest.raises(AssertionError, match="invalid_params"):
        engine("indicator.save", {"id": ind["id"], "indicator": {**spec, "frequency": "weekly"}})
