# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 GAYI Komi Selassi and SANOUSSI Moudjibou

"""Free analyses: descriptives, crosstabs, means, correlations, regressions,
difference in differences and R scripts, with and without a survey design.
Figures are checked against direct calculations."""

from __future__ import annotations

import io
import json
import os
from pathlib import Path

import numpy as np
import polars as pl
import pytest
from docx import Document

from sme_engine import trust
from sme_engine.methods import register
from sme_engine.r_bridge import RBridge, find_rscript
from sme_engine.rpc import Server

pytestmark = pytest.mark.skipif(find_rscript() is None, reason="R not installed")

rng = np.random.default_rng(7)
N = 400
group = rng.choice(["A", "B", "C"], N)
treated = rng.choice(["oui", "non"], N)
period = rng.choice(["2023", "2025"], N)
age = rng.integers(18, 80, N)
income = np.round(1000 + 30 * age + (group == "B") * 400 + rng.normal(0, 300, N), 1)
water = np.where(rng.random(N) < 0.3 + 0.3 * (treated == "oui") * (period == "2025"), "yes", "no")
weight = np.round(rng.uniform(0.5, 2.0, N), 3)
camp = rng.choice(["c1", "c2", "c3", "c4"], N)
DATA = pl.DataFrame(
    {
        "group": group,
        "treated": treated,
        "period": period,
        "age": age.astype(str),
        "income": income.astype(str),
        "water": water,
        "weight": weight.astype(str),
        "camp": camp,
    }
).with_columns(pl.when(pl.int_range(pl.len()) % 37 == 0).then(None).otherwise(pl.col("income")).alias("income"))


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


def project(call, tmp_path, design=None):
    csv = tmp_path / "data.csv"
    DATA.write_csv(csv)
    call("project.create", {"path": str(tmp_path / "p.sme"), "name": "Test"})
    ds = call("dataset.import", {"path": str(csv), "name": "Menages", "round": "baseline"})["created"]
    call("dataset.update", {"id": ds, "design": design or {"weights": None, "strata": [], "cluster": None}})
    return ds


def run(call, ds, spec, lang="fr"):
    snap = call("analysis.save", {"analysis": {"dataset_id": ds, **spec}})
    return call("analysis.run", {"id": snap["created"], "lang": lang})


def table(res, key):
    t = next(t for t in res["tables"] if t["key"] == key)
    keys = [c["label"] if c["data"] else c["key"] for c in t["columns"]]
    return [dict(zip(keys, r, strict=True)) for r in t["rows"]]


def test_descriptives_without_and_with_weights(call, tmp_path):
    ds = project(call, tmp_path)
    res = run(call, ds, {"type": "descriptives", "variables": ["income", "water", "age"], "types": {"age": "numeric"}})
    assert "error" not in res, res
    num = {r["variable"]: r for r in table(res, "numeric")}
    inc = DATA["income"].cast(pl.Float64).drop_nulls()
    assert num["income"]["n"] == inc.len() and num["income"]["mean"] == pytest.approx(inc.mean())
    assert num["income"]["median"] == pytest.approx(inc.median())
    assert num["age"]["mean"] == pytest.approx(DATA["age"].cast(pl.Float64).mean())
    cat = table(res, "categorical")
    yes = next(r for r in cat if r["value"] == "yes")
    assert yes["percent"] == pytest.approx((DATA["water"] == "yes").mean())
    assert yes["ci_low"] < yes["percent"] < yes["ci_high"]
    assert len(res["charts"]) == 3 and res["tables"][0]["columns"][0]["label"] == "Variable"
    assert "donnees" in res["script"]

    call("dataset.update", {"id": ds, "design": {"weights": "weight", "strata": ["camp"], "cluster": None}})
    res = run(call, ds, {"type": "descriptives", "variables": ["income"], "by": "group"})
    rows = {r["group"]: r for r in table(res, "numeric")}
    sub = DATA.filter(pl.col("group") == "B").drop_nulls("income")
    w, y = sub["weight"].cast(pl.Float64), sub["income"].cast(pl.Float64)
    assert rows["B"]["mean"] == pytest.approx(float((w * y).sum() / w.sum()))
    assert "svyby" in res["script"] and any("plan d'enquête" in s for s in res["reading"])


def test_crosstab_means_and_their_reading(call, tmp_path):
    ds = project(call, tmp_path, {"weights": "weight", "strata": [], "cluster": None})
    res = run(call, ds, {"type": "crosstab", "row": "treated", "column": "water", "percent": "row"})
    rows = {r["row_value"]: r for r in table(res, "percent_row")}
    sub = DATA.filter(pl.col("treated") == "oui")
    w = sub["weight"].cast(pl.Float64)
    assert rows["oui"]["yes"] == pytest.approx(float(w.filter(sub["water"] == "yes").sum() / w.sum()))
    assert rows["oui"]["yes"] + rows["oui"]["no"] == pytest.approx(1)
    assert res["tests"][0]["key"] == "rao_scott" and 0 <= res["tests"][0]["p_value"] <= 1
    assert res["reading"][0].startswith("Le lien entre « treated » et « water »")
    counts = table(res, "counts")
    assert sum(r["n"] for r in counts) == N

    res = run(call, ds, {"type": "means", "outcome": "income", "group": "group"}, lang="en")
    assert res["tests"][0]["key"] == "svy_anova" and res["tests"][0]["p_value"] < 0.001
    assert "differences between groups are statistically significant" in res["reading"][0]
    res = run(call, ds, {"type": "means", "outcome": "income", "group": "treated"})
    assert res["tests"][0]["key"] == "svyttest"
    m = {r["group"]: r["mean"] for r in table(res, "by_group")}
    assert res["tests"][0]["difference"] == pytest.approx(m["oui"] - m["non"])


def test_regressions_match_least_squares(call, tmp_path):
    ds = project(call, tmp_path)
    res = run(call, ds, {"type": "regression", "outcome": "income", "predictors": ["age", "group"], "family": "linear"})
    assert "error" not in res, res
    co = {r["term"]: r for r in table(res, "coefficients_linear")}
    df = DATA.drop_nulls("income")
    x = np.column_stack(
        [
            np.ones(df.height),
            df["age"].cast(pl.Float64).to_numpy(),
            (df["group"] == "B").to_numpy().astype(float),
            (df["group"] == "C").to_numpy().astype(float),
        ]
    )
    beta = np.linalg.lstsq(x, df["income"].cast(pl.Float64).to_numpy(), rcond=None)[0]
    assert co["Constante"]["estimate"] == pytest.approx(beta[0])
    assert co["age"]["estimate"] == pytest.approx(beta[1])
    assert co["group = B"]["estimate"] == pytest.approx(beta[2]) and co["group = B"]["p_value"] < 0.001
    assert table(res, "fit")[0]["n"] == df.height
    assert "age" in res["reading"][0] and "group = A" in res["reading"][1]

    res = run(
        call,
        ds,
        {"type": "regression", "outcome": "water", "success": ["yes"], "predictors": ["treated"], "family": "logistic"},
        lang="en",
    )
    co = {r["term"]: r for r in table(res, "coefficients_logistic")}
    assert co["treated = oui"]["odds_ratio"] == pytest.approx(np.exp(co["treated = oui"]["estimate"]))
    assert len(res["charts"]) == 1


def test_did_is_the_difference_of_four_means(call, tmp_path):
    ds = project(call, tmp_path, {"weights": "weight", "strata": [], "cluster": None})
    spec = {
        "type": "did",
        "outcome": "water",
        "success": ["yes"],
        "group": "treated",
        "treated": ["oui"],
        "period": "period",
        "after": ["2025"],
    }
    res = run(call, ds, spec)
    assert "error" not in res, res
    means = {(r["group"], r["period"]): r["mean"] for r in table(res, "did_shares")}
    did = (means[("Bénéficiaires", "Après")] - means[("Bénéficiaires", "Avant")]) - (
        means[("Comparaison", "Après")] - means[("Comparaison", "Avant")]
    )
    est = table(res, "did_estimate")[0]
    assert est["estimate"] == pytest.approx(did)
    assert est["ci_low"] < est["estimate"] < est["ci_high"]
    assert "points de plus chez les bénéficiaires" in res["reading"][0] and "tendances parallèles" in res["reading"][1]


def test_correlation_and_errors(call, tmp_path):
    ds = project(call, tmp_path)
    res = run(call, ds, {"type": "correlation", "variables": ["age", "income", "weight"]})
    m = table(res, "correlation")
    df = DATA.drop_nulls("income")
    r = np.corrcoef(df["age"].cast(pl.Float64), df["income"].cast(pl.Float64))[0, 1]
    assert m[0]["income"] == pytest.approx(r) and m[0]["age"] == pytest.approx(1)
    assert "« age » et « income »" in res["reading"][0]
    with pytest.raises(RuntimeError, match="column_not_found"):
        run(call, ds, {"type": "crosstab", "row": "nope", "column": "water"})
    # An analysis whose column was removed later reports it instead of failing.
    snap = call(
        "cleaning.add", {"dataset_id": ds, "rule": {"kind": "formula", "target": "x2", "expression": "age * 2"}}
    )
    a = call("analysis.save", {"analysis": {"dataset_id": ds, "type": "means", "outcome": "x2", "group": "group"}})
    call("cleaning.delete", {"id": snap["datasets"][0]["rules"][0]["id"]})
    assert call("analysis.run", {"id": a["created"]}) == {
        "id": a["created"],
        "error": "column_missing",
        "columns": ["x2"],
    }
    res = run(call, ds, {"type": "means", "outcome": "income", "group": "period"})
    assert "error" not in res
    res = run(call, ds, {"type": "means", "outcome": "age", "group": "water"})
    assert res["tests"][0]["key"] == "welch"


def test_r_script_analysis_trust_and_report(call, tmp_path):
    ds = project(call, tmp_path, {"weights": "weight", "strata": [], "cluster": None})
    code = "print(svymean(~income, plan, na.rm = TRUE))\nhist(data$age)\nresultat <- aggregate(age ~ group, data, mean)"
    snap = call(
        "analysis.save", {"analysis": {"dataset_id": ds, "type": "r_script", "code": code, "title": "Mon script"}}
    )
    res = call("analysis.run", {"id": snap["created"]})
    out = res["script_result"]
    assert "income" in out["output"] and len(out["plots"]) == 1 and out["table"]["columns"] == ["group", "age"]
    run(call, ds, {"type": "crosstab", "row": "treated", "column": "water", "title": "Eau selon le statut"})
    report = tmp_path / "r.docx"
    call("report.generate", {"path": str(report), "lang": "fr"})
    text = "\n".join(p.text for p in Document(report).paragraphs)
    assert "Eau selon le statut" in text and "Le lien entre « treated » et « water »" in text
    assert "Mon script" in text

    call("project.close")
    trust.path().unlink()
    snap = call("project.open", {"path": str(tmp_path / "p.sme")})
    assert [s["where"] for s in snap["untrusted_scripts"]] == ["analysis"]
    assert call("analysis.run", {"id": snap["untrusted_scripts"][0]["id"]})["paused"] is True


@pytest.mark.skipif(not os.environ.get("SME_FULL_DATA"), reason="full HDX files not downloaded")
def test_on_real_survey_with_camp_weights(call, tmp_path):
    path = Path(os.environ["SME_FULL_DATA"]) / "bgd_wash_baseline_2018.xlsx"
    call("project.create", {"path": str(tmp_path / "bgd.sme"), "name": "BGD"})
    ds = call("dataset.import", {"path": str(path), "sheet": "Dataset", "name": "BGD", "round": "baseline"})["created"]
    call(
        "dataset.update",
        {"id": ds, "design": {"weights": "Camp weights", "strata": ["reported_camp_name"], "cluster": None}},
    )
    res = run(call, ds, {"type": "descriptives", "variables": ["HoH/household_size", "HoH/head_of_household"]})
    assert "error" not in res, res
    assert table(res, "numeric")[0]["n"] > 100
    res = run(call, ds, {"type": "crosstab", "row": "HoH/head_of_household", "column": "disability/disability_present"})
    assert "error" not in res and res["tests"][0]["key"] == "rao_scott"
    res = run(
        call,
        ds,
        {
            "type": "regression",
            "outcome": "disability/disability_present",
            "success": ["yes"],
            "predictors": ["HoH/household_size", "HoH/head_of_household"],
            "family": "logistic",
        },
    )
    assert "error" not in res, res


def test_report_content_choices(call, tmp_path):
    ds = project(call, tmp_path)
    run(call, ds, {"type": "crosstab", "row": "treated", "column": "water", "title": "Eau selon le statut"})
    hidden = call(
        "analysis.save",
        {
            "analysis": {
                "dataset_id": ds,
                "type": "means",
                "outcome": "age",
                "group": "water",
                "title": "Cachee",
                "in_report": False,
            }
        },
    )
    snap = call(
        "report.set_content",
        {
            "content": {
                "sections": [{"id": "analyses"}, {"id": "summary", "on": False}, {"id": "framework", "on": False}],
                "analyses": {
                    hidden["created"]: {"script": True},
                    snap_id(hidden, "Eau selon le statut"): {"charts": False},
                },
                "journal": False,
            }
        },
    )
    content = snap["report_content"]
    assert [s["id"] for s in content["sections"]][:3] == ["analyses", "summary", "framework"]
    assert len(content["sections"]) == 8  # the others keep their place after the chosen ones
    report = tmp_path / "r.docx"
    call("report.generate", {"path": str(report), "lang": "fr"})
    doc = Document(report)
    heads = [p.text for p in doc.paragraphs if p.style.name.startswith("Heading")]
    assert heads[0] == "1. Analyses statistiques" and "Eau selon le statut" in heads
    assert "Cachee" not in heads and not any("Synthèse" in h for h in heads)
    assert len(doc.inline_shapes) == 0  # charts switched off for the crosstab
    with pytest.raises(RuntimeError, match="report_content_invalid"):
        call("report.set_content", {"content": {"sections": "x"}})


def snap_id(saved, title):
    return next(a["id"] for a in saved["analyses"] if a.get("title") == title)
