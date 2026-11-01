"""Free analyses: the Analyses screen, a results document saved in the project.

Each analysis is a JSON spec stored in the `analysis` table; its result is
recomputed from the cleaned data when shown (and cached), like JASP. All of them
follow the sampling design of the dataset (survey package) when it has one.

    {"type": "descriptives", "dataset_id", "variables": [..], "by": col|None, "types": {col: "numeric"|"categorical"}}
    {"type": "crosstab", "dataset_id", "row", "column", "percent": "row"|"column"|"total"}
    {"type": "means", "dataset_id", "outcome", "group"}
    {"type": "correlation", "dataset_id", "variables": [..]}
    {"type": "regression", "dataset_id", "outcome", "predictors": [..], "family": "linear"|"logistic",
     "success": [values] (logistic), "factors": [cols], "reference": {col: value}}
    {"type": "did", "dataset_id", "outcome", "success": [values]|None, "group", "treated": [values],
     "period", "after": [values]}
    {"type": "r_script", "dataset_id", "code"}

Common fields: title, note, level (0.9, 0.95, 0.99), in_report (bool).
"""

from __future__ import annotations

import base64
import shutil
import tempfile
from pathlib import Path
from typing import Any

from . import r_user, trust
from .rpc import INVALID_PARAMS, RpcError

GROUP_WORDS = ("treated", "comparison", "before", "after")
TYPES = ("descriptives", "crosstab", "means", "correlation", "regression", "did", "r_script")
LEVELS = (0.9, 0.95, 0.99)
MAX_VARIABLES = 30


def _err(message: str, key: str = "analysis_invalid") -> RpcError:
    return RpcError(message, INVALID_PARAMS, data={"key": key})


def _col(spec: dict[str, Any], key: str, columns: list[str], required: bool = True) -> str | None:
    v = spec.get(key)
    if v in (None, "") and not required:
        return None
    if not isinstance(v, str) or v not in columns:
        raise RpcError(f"Unknown column: {v}", INVALID_PARAMS, data={"key": "column_not_found", "field": key})
    return v


def _cols(spec: dict[str, Any], key: str, columns: list[str], lo: int = 1, hi: int = MAX_VARIABLES) -> list[str]:
    v = spec.get(key)
    if not isinstance(v, list) or not lo <= len(v) <= hi:
        raise _err(f"Choose {lo} to {hi} variables ({key})")
    out = []
    for c in v:
        if not isinstance(c, str) or c not in columns:
            raise RpcError(f"Unknown column: {c}", INVALID_PARAMS, data={"key": "column_not_found", "field": key})
        if c not in out:
            out.append(c)
    return out


def _values(spec: dict[str, Any], key: str, required: bool = True) -> list[str] | None:
    v = spec.get(key)
    if v in (None, []) and not required:
        return None
    if not isinstance(v, list) or not v or any(not isinstance(x, (str, int, float)) for x in v):
        raise _err(f"Choose the values ({key})")
    return [str(x) for x in v]


def validate(spec: dict[str, Any], columns: list[str]) -> dict[str, Any]:
    t = spec.get("type")
    if t not in TYPES:
        raise _err(f"type must be one of {TYPES}")
    level = spec.get("level", 0.95)
    if level not in LEVELS:
        raise _err("level must be 0.9, 0.95 or 0.99")
    out: dict[str, Any] = {
        "type": t,
        "dataset_id": spec.get("dataset_id"),
        "title": str(spec.get("title") or "").strip()[:200],
        "note": str(spec.get("note") or "").strip()[:4000],
        "level": level,
        "in_report": spec.get("in_report", True) is not False,
    }
    if t == "descriptives":
        out["variables"] = _cols(spec, "variables", columns)
        out["by"] = _col(spec, "by", columns, required=False)
        types = spec.get("types") or {}
        if not isinstance(types, dict):
            raise _err("types must be an object")
        out["types"] = {k: v for k, v in types.items() if k in out["variables"] and v in ("numeric", "categorical")}
    elif t == "crosstab":
        out["row"] = _col(spec, "row", columns)
        out["column"] = _col(spec, "column", columns)
        if out["row"] == out["column"]:
            raise _err("Choose two different variables")
        out["percent"] = spec.get("percent") if spec.get("percent") in ("row", "column", "total") else "row"
    elif t == "means":
        out["outcome"] = _col(spec, "outcome", columns)
        out["group"] = _col(spec, "group", columns)
    elif t == "correlation":
        out["variables"] = _cols(spec, "variables", columns, lo=2, hi=12)
    elif t == "regression":
        out["outcome"] = _col(spec, "outcome", columns)
        out["predictors"] = [c for c in _cols(spec, "predictors", columns, hi=15) if c != out["outcome"]]
        if not out["predictors"]:
            raise _err("Choose explanatory variables other than the outcome")
        out["family"] = "logistic" if spec.get("family") == "logistic" else "linear"
        if out["family"] == "logistic":
            out["success"] = _values(spec, "success")
        out["factors"] = [c for c in (spec.get("factors") or []) if c in out["predictors"]]
        ref = spec.get("reference") or {}
        out["reference"] = {k: str(v) for k, v in ref.items() if k in out["predictors"] and v not in (None, "")}
    elif t == "did":
        out["outcome"] = _col(spec, "outcome", columns)
        out["success"] = _values(spec, "success", required=False)
        out["group"] = _col(spec, "group", columns)
        out["treated"] = _values(spec, "treated")
        out["period"] = _col(spec, "period", columns)
        out["after"] = _values(spec, "after")
    elif t == "r_script":
        code = spec.get("code")
        if not isinstance(code, str) or not code.strip():
            raise _err("Write the R code")
        if len(code) > 50_000:
            raise _err("The R code is too long")
        out["code"] = code.replace("\r\n", "\n")
    return out


def used_columns(spec: dict[str, Any]) -> list[str]:
    cols: list[str] = []
    for k in ("variables", "predictors"):
        cols += spec.get(k) or []
    for k in ("by", "row", "column", "outcome", "group", "period"):
        if spec.get(k):
            cols.append(spec[k])
    return list(dict.fromkeys(cols))


def run(svc: Any, spec: dict[str, Any], lang: str) -> dict[str, Any]:
    """Result of one analysis, with labels in `lang`. Errors are returned, not raised."""
    try:
        ds = svc.dataset_spec(spec["dataset_id"])
    except RpcError:
        return {"error": "dataset_missing"}
    sig, df, _ = svc.cleaned(ds["id"])
    design = ds.get("design") or {}
    design_cols = [c for c in [design.get("weights"), design.get("cluster"), *(design.get("strata") or [])] if c]
    if spec["type"] == "r_script":
        if not trust.is_trusted(spec["code"]):
            return {"paused": True}
        key = svc._cache_key("analysis", spec, sig, design)
        if key not in svc._results:
            try:
                svc._results[key] = {"script_result": r_user.run_analysis(df, spec["code"], design)}
            except RpcError as exc:
                return {"error": "r_script_failed", "message": str(exc)}
        return svc._results[key]
    missing = [c for c in used_columns(spec) if c not in df.columns]
    if missing:
        return {"error": "column_missing", "columns": missing}
    key = svc._cache_key("analysis", spec, sig, design, lang)
    if key in svc._results:
        return svc._results[key]
    table = df.select(list(dict.fromkeys([*used_columns(spec), *design_cols])))
    path = svc.bridge.write_table(table, f"a_{key[:16]}")
    out_dir = Path(tempfile.mkdtemp(prefix="sme-an-", dir=svc.bridge.workdir))
    options = {k: v for k, v in spec.items() if k not in ("title", "note", "in_report", "dataset_id", "level", "type")}
    if spec["type"] == "did":
        options["labels"] = {w: LABELS[lang]["special"][w] for w in GROUP_WORDS}
    if spec["type"] == "regression":
        options["labels"] = {"odds_ratio": LABELS[lang]["columns"]["odds_ratio"]}
    try:
        res = svc.bridge.call(
            "analysis",
            {
                "path": path,
                "type": spec["type"],
                "options": options,
                "weights": design.get("weights"),
                "strata": design.get("strata") or None,
                "cluster": design.get("cluster"),
                "level": spec["level"],
                "outdir": str(out_dir),
                "decimal": "," if lang == "fr" else ".",
            },
            timeout=300,
        )
    except RpcError as exc:
        shutil.rmtree(out_dir, ignore_errors=True)
        if (exc.data or {}).get("key") == "r_error":
            return {"error": "r_error", "message": str(exc)}
        raise
    charts = res.get("charts") or []
    if isinstance(charts, str):
        charts = [charts]
    res["charts"] = [base64.b64encode(Path(p).read_bytes()).decode("ascii") for p in charts if Path(p).exists()]
    shutil.rmtree(out_dir, ignore_errors=True)
    res["tables"] = [_label_table(t, lang) for t in res.get("tables") or []]
    for t in res.get("tests") or []:
        t["label"] = LABELS[lang]["tests"].get(t["key"], t["key"])
    res["notes"] = [LABELS[lang]["notes"].get(n, n) for n in _as_list(res.get("notes"))]
    res["reading"] = reading(spec, res, lang)
    svc._results[key] = res
    return res


def _as_list(x: Any) -> list[Any]:
    if x is None:
        return []
    return x if isinstance(x, list) else [x]


def _label_table(t: dict[str, Any], lang: str) -> dict[str, Any]:
    L = LABELS[lang]
    cols = []
    for c in t["columns"]:
        data = bool(c.get("label")) and c["key"] == "value"  # a value of the data (crosstab column), not a header
        label = c["label"] if c.get("label") else L["columns"].get(c["key"], c["key"])
        cols.append({"key": c["key"], "fmt": c.get("fmt", "text"), "label": label, "data": data})
    rows = []
    for r in t["rows"]:
        row = [None if isinstance(v, dict) and not v else v for v in r]
        if row and isinstance(row[0], str) and row[0].startswith(".") and row[0] in L["special"]:
            row[0] = L["special"][row[0]]
        rows.append([L["special"].get(v, v) if isinstance(v, str) and v in GROUP_WORDS else v for v in row])
    return {"key": t["key"], "title": L["tables"].get(t["key"], ""), "columns": cols, "rows": rows}


# ----- plain-language reading ------------------------------------------------------------


def _sig(p: float | None, alpha: float = 0.05) -> bool:
    return isinstance(p, (int, float)) and p < alpha


def reading(spec: dict[str, Any], res: dict[str, Any], lang: str) -> list[str]:
    from .report import Fmt

    f = Fmt(lang)
    W = READING[lang]
    t = spec["type"]
    tests = res.get("tests") or []
    tables = res.get("tables") or []

    def pv(p: float) -> str:
        return f.p(p, {"p_small": W["p_small"], "p_eq": W["p_eq"]})

    out: list[str] = []
    if t == "crosstab" and tests:
        test = tests[0]
        sig = _sig(test.get("p_value"))
        out.append(
            W["crosstab"].format(
                row=spec["row"],
                column=spec["column"],
                verdict=W["sig"] if sig else W["not_sig"],
                test=test["label"],
                p=pv(test["p_value"]),
            )
        )
        if test.get("effect_size") is not None:
            out.append(W["cramer"].format(v=f.num(test["effect_size"], 2)))
    elif t == "means" and tests and tables:
        rows = tables[0]["rows"]
        test = tests[0]
        sig = _sig(test.get("p_value"))
        means = [(r[0], r[2]) for r in rows if r[2] is not None]
        if len(means) == 2:
            (ga, a), (gb, b) = means
            out.append(
                W["means_two"].format(
                    y=spec["outcome"],
                    gb=gb,
                    b=f.num(b, 2),
                    ga=ga,
                    a=f.num(a, 2),
                    d=f.num(abs(b - a), 2),
                    verdict=W["sig_m"] if sig else W["not_sig_m"],
                    test=test["label"],
                    p=pv(test["p_value"]),
                )
            )
        elif means:
            lo = min(means, key=lambda m: m[1])
            hi = max(means, key=lambda m: m[1])
            out.append(
                W["means_many"].format(
                    y=spec["outcome"],
                    lo=f.num(lo[1], 2),
                    glo=lo[0],
                    hi=f.num(hi[1], 2),
                    ghi=hi[0],
                    verdict=W["sig_f"] if sig else W["not_sig_f"],
                    test=test["label"],
                    p=pv(test["p_value"]),
                )
            )
    elif t == "regression" and tables:
        co = tables[0]
        keys = [c["key"] for c in co["columns"]]
        ip, ie = keys.index("p_value"), keys.index("estimate")
        ior = keys.index("odds_ratio") if "odds_ratio" in keys else None
        terms = [r for r in co["rows"] if r[0] != LABELS[lang]["special"][".intercept"]]
        sig_terms = [r for r in terms if _sig(r[ip])]
        n = tables[1]["rows"][0][0] if len(tables) > 1 else None
        if not sig_terms:
            out.append(W["reg_none"].format(n=f.num(n, 0) if n else "", y=spec["outcome"]))
        else:
            parts = []
            for r in sig_terms[:6]:
                if ior is not None:
                    parts.append(W["reg_or"].format(term=r[0], v=f.num(r[ior], 2)))
                else:
                    parts.append(W["reg_lin"].format(term=r[0], v=f.num(r[ie], 3)))
            out.append(W["reg_some"].format(n=f.num(n, 0) if n else "", y=spec["outcome"], terms="; ".join(parts)))
        refs = res.get("references") or {}
        if refs:
            out.append(W["reg_ref"].format(refs=", ".join(f"{k} = {v}" for k, v in refs.items())))
    elif t == "did" and len(tables) > 1:
        e = tables[1]["rows"][0]
        pct = spec.get("success") is not None
        val = (lambda x: f.num(x * 100, 1) + " " + W["points"]) if pct else (lambda x: f.num(x, 2))
        if e[0] is not None:
            out.append(
                W["did"].format(
                    y=spec["outcome"],
                    dir=W["more"] if e[0] >= 0 else W["less"],
                    v=val(abs(e[0])),
                    lo=val(e[2]) if e[2] is not None else f.none,
                    hi=val(e[3]) if e[3] is not None else f.none,
                    level=f.num(spec["level"] * 100, 0),
                    verdict=W["sig_f"] if _sig(e[4]) else W["not_sig_f"],
                    p=pv(e[4]) if e[4] is not None else f.none,
                )
            )
            out.append(W["did_caution"])
    elif t == "correlation" and tables:
        m = tables[0]
        names = [c["label"] for c in m["columns"][1:]]
        best = None
        for i, r in enumerate(m["rows"]):
            for j, v in enumerate(r[1:]):
                if j > i and v is not None and (best is None or abs(v) > abs(best[2])):
                    best = (names[i], names[j], v)
        if best:
            out.append(W["corr"].format(a=best[0], b=best[1], r=f.num(best[2], 2)))
    if res.get("design"):
        out.append(W["design"])
    return out


LABELS: dict[str, dict[str, dict[str, str]]] = {
    "fr": {
        "columns": {
            "variable": "Variable",
            "group": "Groupe",
            "period": "Période",
            "value": "Valeur",
            "row_value": "",
            "n": "Effectif",
            "mean": "Moyenne",
            "se": "Erreur type",
            "ci_low": "IC bas",
            "ci_high": "IC haut",
            "sd": "Écart type",
            "median": "Médiane",
            "q1": "1er quartile",
            "q3": "3e quartile",
            "min": "Minimum",
            "max": "Maximum",
            "percent": "Part",
            "all": "Ensemble",
            "term": "Variable explicative",
            "estimate": "Coefficient",
            "statistic": "Statistique",
            "p_value": "p",
            "odds_ratio": "Rapport de cotes",
            "or_low": "RC bas",
            "or_high": "RC haut",
            "r2": "R² (part de variance expliquée)",
        },
        "tables": {
            "numeric": "Variables numériques",
            "categorical": "Répartition des valeurs",
            "percent_row": "Pourcentages en ligne",
            "percent_column": "Pourcentages en colonne",
            "percent_total": "Pourcentages du total",
            "counts": "Effectifs observés (non pondérés)",
            "by_group": "Moyenne par groupe",
            "correlation": "Coefficients de corrélation (Pearson)",
            "correlation_p": "Valeurs p des corrélations",
            "coefficients_linear": "Coefficients (régression linéaire)",
            "coefficients_logistic": "Coefficients (régression logistique)",
            "fit": "Ajustement du modèle",
            "did_means": "Moyennes avant et après",
            "did_shares": "Parts avant et après",
            "did_estimate": "Différence de différences",
        },
        "tests": {
            "rao_scott": "test du khi-deux corrigé de Rao-Scott",
            "chisq": "test du khi-deux",
            "fisher": "test exact de Fisher",
            "svyttest": "test t pour plan d'enquête",
            "welch": "test t de Welch",
            "svy_anova": "test F global (régression pour plan d'enquête)",
            "welch_anova": "ANOVA de Welch",
        },
        "notes": {"expected_small": "Effectifs attendus faibles : le test exact de Fisher remplace le khi-deux."},
        "special": {
            ".all": "Ensemble",
            ".n": "Effectif",
            ".intercept": "Constante",
            "treated": "Bénéficiaires",
            "comparison": "Comparaison",
            "before": "Avant",
            "after": "Après",
        },
    },
    "en": {
        "columns": {
            "variable": "Variable",
            "group": "Group",
            "period": "Period",
            "value": "Value",
            "row_value": "",
            "n": "Count",
            "mean": "Mean",
            "se": "Standard error",
            "ci_low": "CI low",
            "ci_high": "CI high",
            "sd": "Standard deviation",
            "median": "Median",
            "q1": "1st quartile",
            "q3": "3rd quartile",
            "min": "Minimum",
            "max": "Maximum",
            "percent": "Share",
            "all": "All",
            "term": "Explanatory variable",
            "estimate": "Coefficient",
            "statistic": "Statistic",
            "p_value": "p",
            "odds_ratio": "Odds ratio",
            "or_low": "OR low",
            "or_high": "OR high",
            "r2": "R² (share of variance explained)",
        },
        "tables": {
            "numeric": "Numeric variables",
            "categorical": "Distribution of values",
            "percent_row": "Row percentages",
            "percent_column": "Column percentages",
            "percent_total": "Percentages of the total",
            "counts": "Observed counts (unweighted)",
            "by_group": "Mean by group",
            "correlation": "Correlation coefficients (Pearson)",
            "correlation_p": "p-values of the correlations",
            "coefficients_linear": "Coefficients (linear regression)",
            "coefficients_logistic": "Coefficients (logistic regression)",
            "fit": "Model fit",
            "did_means": "Means before and after",
            "did_shares": "Shares before and after",
            "did_estimate": "Difference in differences",
        },
        "tests": {
            "rao_scott": "Rao-Scott corrected chi-square test",
            "chisq": "chi-square test",
            "fisher": "Fisher's exact test",
            "svyttest": "t-test for a survey design",
            "welch": "Welch t-test",
            "svy_anova": "overall F test (survey regression)",
            "welch_anova": "Welch ANOVA",
        },
        "notes": {"expected_small": "Small expected counts: Fisher's exact test replaces the chi-square test."},
        "special": {
            ".all": "All",
            ".n": "Count",
            ".intercept": "Intercept",
            "treated": "Beneficiaries",
            "comparison": "Comparison",
            "before": "Before",
            "after": "After",
        },
    },
}

READING = {
    "fr": {
        "p_small": "p < 0,001",
        "p_eq": "p = {p}",
        "sig": "est statistiquement significatif",
        "not_sig": "n'est pas statistiquement significatif",
        "sig_m": "est statistiquement significatif",
        "not_sig_m": "n'est pas statistiquement significatif",
        "sig_f": "sont statistiquement significatives",
        "not_sig_f": "ne sont pas statistiquement significatives",
        "crosstab": "Le lien entre « {row} » et « {column} » {verdict} ({test}, {p}).",
        "cramer": "Force du lien (V de Cramér) : {v}, de 0 (aucun lien) à 1 (lien parfait).",
        "means_two": (
            "La moyenne de « {y} » est de {b} pour {gb} contre {a} pour {ga} ; l'écart de {d} {verdict} ({test}, {p})."
        ),
        "means_many": (
            "La moyenne de « {y} » va de {lo} ({glo}) à {hi} ({ghi}) ; les différences entre "
            "groupes {verdict} ({test}, {p})."
        ),
        "reg_none": (
            "Sur {n} lignes complètes, aucune variable explicative n'a d'effet "
            "statistiquement significatif sur « {y} » au seuil de 5 %."
        ),
        "reg_some": (
            "Sur {n} lignes complètes, à autres variables égales, effets statistiquement "
            "significatifs sur « {y} » au seuil de 5 % : {terms}."
        ),
        "reg_lin": "{term} (coefficient {v})",
        "reg_or": "{term} (rapport de cotes {v})",
        "reg_ref": "Pour les variables qualitatives, chaque modalité est comparée à la modalité de référence : {refs}.",
        "points": "points",
        "more": "plus",
        "less": "moins",
        "did": (
            "Entre avant et après, « {y} » évolue de {v} de {dir} chez les bénéficiaires que dans le groupe de "
            "comparaison (IC à {level} % : {lo} à {hi}) ; les différences {verdict} ({p})."
        ),
        "did_caution": (
            "Cette estimation suppose que, sans le projet, les deux groupes auraient évolué de la même façon "
            "(tendances parallèles)."
        ),
        "corr": "La corrélation la plus forte relie « {a} » et « {b} » (r = {r}).",
        "design": "Calculs selon le plan d'enquête du fichier (pondération, strates, grappes).",
    },
    "en": {
        "p_small": "p < 0.001",
        "p_eq": "p = {p}",
        "sig": "is statistically significant",
        "not_sig": "is not statistically significant",
        "sig_m": "is statistically significant",
        "not_sig_m": "is not statistically significant",
        "sig_f": "are statistically significant",
        "not_sig_f": "are not statistically significant",
        "crosstab": 'The association between "{row}" and "{column}" {verdict} ({test}, {p}).',
        "cramer": "Strength of the association (Cramér's V): {v}, from 0 (none) to 1 (perfect).",
        "means_two": 'The mean of "{y}" is {b} for {gb} against {a} for {ga}; the gap of {d} {verdict} ({test}, {p}).',
        "means_many": (
            'The mean of "{y}" ranges from {lo} ({glo}) to {hi} ({ghi}); the differences '
            "between groups {verdict} ({test}, {p})."
        ),
        "reg_none": (
            "On {n} complete rows, no explanatory variable has a statistically significant "
            'effect on "{y}" at the 5% level.'
        ),
        "reg_some": (
            "On {n} complete rows, other variables being equal, statistically significant "
            'effects on "{y}" at the 5% level: {terms}.'
        ),
        "reg_lin": "{term} (coefficient {v})",
        "reg_or": "{term} (odds ratio {v})",
        "reg_ref": "For categorical variables, each value is compared with the reference value: {refs}.",
        "points": "points",
        "more": "more",
        "less": "less",
        "did": (
            'Between before and after, "{y}" changes by {v} {dir} among beneficiaries than in the comparison '
            "group ({level}% CI: {lo} to {hi}); the differences {verdict} ({p})."
        ),
        "did_caution": (
            "This estimate assumes that, without the project, both groups would have changed in the same way "
            "(parallel trends)."
        ),
        "corr": 'The strongest correlation links "{a}" and "{b}" (r = {r}).',
        "design": "Computed with the file's sampling design (weights, strata, clusters).",
    },
}


# ----- titles and cells (Analyses screen and Word report) ------------------------------

TITLES = {
    "fr": {
        "descriptives": "Statistiques descriptives : {variables}",
        "descriptives_by": "Statistiques descriptives : {variables}, selon {by}",
        "crosstab": "Tableau croisé : {row} selon {column}",
        "means": "Comparaison de moyennes : {outcome} selon {group}",
        "correlation": "Corrélations : {variables}",
        "regression_linear": "Régression linéaire de {outcome}",
        "regression_logistic": "Régression logistique de {outcome}",
        "did": "Différence de différences : {outcome}",
        "r_script": "Script R",
    },
    "en": {
        "descriptives": "Descriptive statistics: {variables}",
        "descriptives_by": "Descriptive statistics: {variables}, by {by}",
        "crosstab": "Crosstab: {row} by {column}",
        "means": "Comparison of means: {outcome} by {group}",
        "correlation": "Correlations: {variables}",
        "regression_linear": "Linear regression of {outcome}",
        "regression_logistic": "Logistic regression of {outcome}",
        "did": "Difference in differences: {outcome}",
        "r_script": "R script",
    },
}


def default_title(spec: dict[str, Any], lang: str) -> str:
    T = TITLES[lang]
    t = spec["type"]
    names = ", ".join((spec.get("variables") or [])[:4]) + (" ..." if len(spec.get("variables") or []) > 4 else "")
    if t == "descriptives":
        return (T["descriptives_by"] if spec.get("by") else T["descriptives"]).format(
            variables=names, by=spec.get("by")
        )
    if t == "regression":
        return T[f"regression_{spec['family']}"].format(outcome=spec["outcome"])
    return T[t].format(variables=names, **{k: spec.get(k) for k in ("row", "column", "outcome", "group")})


def title(spec: dict[str, Any], lang: str) -> str:
    return spec.get("title") or default_title(spec, lang)


def cell(value: Any, fmt: str, f: Any) -> str:
    """A table cell as text, with the conventions of the report (Fmt)."""
    if value is None:
        return f.none if fmt != "text" else ""
    if fmt == "text" or isinstance(value, str):
        return str(value)
    x = float(value)
    if fmt == "int":
        return f.num(x, 0)
    if fmt == "pct":
        return f.pct(x, 1)
    if fmt == "p":
        return ("< 0,001" if f.lang == "fr" else "< 0.001") if x < 0.001 else f.num(x, 3)
    ax = abs(x)
    digits = 0 if ax >= 10000 else 1 if ax >= 100 else 2 if ax >= 1 or ax == 0 else 3
    return f.num(x, digits)
