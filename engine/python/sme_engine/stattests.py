"""Test assistant: the question, the data it needs, the R test, and a conclusion in words.

A test spec (validated by `validate`) is one of:

    {"question": "groups", "dataset_id", "kind": "proportion"|"mean", "outcome": {...}, "group": column}
    {"question": "target", "dataset_id", "kind", "outcome": {...}, "target": number}
    {"question": "paired", "kind", "outcome": {...}, "mode": "columns", "dataset_id", "column_b"}
    {"question": "paired", "kind", "outcome": {...}, "mode": "datasets", "dataset_id", "dataset_b_id"}

`outcome` is {"column", "values"} for a yes/no outcome (share of `values`) or
{"column"} for a numeric one. Saved tests are recomputed from the current data.
"""

from __future__ import annotations

from typing import Any

import polars as pl

from .rpc import INVALID_PARAMS, RpcError

QUESTIONS = ("groups", "target", "paired")
KINDS = ("proportion", "mean")


def _err(message: str, key: str) -> RpcError:
    return RpcError(message, INVALID_PARAMS, data={"key": key})


def validate(spec: dict[str, Any]) -> dict[str, Any]:
    q = spec.get("question")
    if q not in QUESTIONS:
        raise _err(f"question must be one of {QUESTIONS}", "test_invalid")
    kind = spec.get("kind")
    if kind not in KINDS:
        raise _err(f"kind must be one of {KINDS}", "test_invalid")
    outcome = spec.get("outcome") or {}
    if not isinstance(outcome, dict) or not isinstance(outcome.get("column"), str) or not outcome["column"]:
        raise _err("Choose the variable to test", "test_invalid")
    values = outcome.get("values") or []
    if kind == "proportion" and (
        not isinstance(values, list) or not values or not all(isinstance(v, str) for v in values)
    ):
        raise _err("Choose the values counted as yes", "test_invalid")
    out: dict[str, Any] = {
        "question": q,
        "kind": kind,
        "dataset_id": spec.get("dataset_id"),
        "outcome": {"column": outcome["column"], "values": values if kind == "proportion" else []},
        "title": str(spec.get("title") or "")[:300],
    }
    if not isinstance(out["dataset_id"], str):
        raise _err("Choose a dataset", "test_invalid")
    if q == "groups":
        if not isinstance(spec.get("group"), str) or not spec["group"]:
            raise _err("Choose the group variable", "test_invalid")
        out["group"] = spec["group"]
    elif q == "target":
        t = spec.get("target")
        if isinstance(t, bool) or not isinstance(t, (int, float)):
            raise _err("Give a target value", "test_invalid")
        if kind == "proportion" and not 0 < t < 1:
            raise _err("A target percentage must be between 0 and 100", "invalid_share")
        out["target"] = float(t)
    else:
        mode = spec.get("mode", "columns")
        if mode not in ("columns", "datasets"):
            raise _err("mode must be columns or datasets", "test_invalid")
        out["mode"] = mode
        if mode == "columns":
            if not isinstance(spec.get("column_b"), str) or not spec["column_b"]:
                raise _err("Choose the second measure", "test_invalid")
            out["column_b"] = spec["column_b"]
        else:
            if not isinstance(spec.get("dataset_b_id"), str):
                raise _err("Choose the second dataset", "test_invalid")
            out["dataset_b_id"] = spec["dataset_b_id"]
    return out


def _outcome(col: str, kind: str, values: list[str]) -> pl.Expr:
    if kind == "proportion":
        return pl.when(pl.col(col).is_null()).then(None).otherwise(pl.col(col).is_in(values).cast(pl.Float64))
    return pl.col(col).cast(pl.Float64, strict=False)


def _r_y(col: str, kind: str, values: list[str], name: str = "y") -> str:
    if kind == "proportion":
        quoted = ", ".join('"' + v.replace('"', '\\"') + '"' for v in values)
        return f"donnees${name} <- ifelse(is.na(donnees$`{col}`), NA, as.numeric(donnees$`{col}` %in% c({quoted})))"
    return f"donnees${name} <- as.numeric(donnees$`{col}`)"


def prepare(svc: Any, spec: dict[str, Any]) -> tuple[str, pl.DataFrame, dict[str, Any]]:
    """R function name, table and arguments for a validated spec."""
    ds = svc.dataset_spec(spec["dataset_id"])
    _, df, _ = svc.cleaned(ds["id"])
    col, kind, values = spec["outcome"]["column"], spec["kind"], spec["outcome"]["values"]
    if col not in df.columns:
        raise _err(f"Unknown column: {col}", "column_not_found")
    design = ds["design"]
    design_cols = [c for c in [design.get("weights"), design.get("cluster"), *(design.get("strata") or [])] if c]
    args: dict[str, Any] = {
        "kind": kind,
        "weights": design.get("weights"),
        "strata": design.get("strata") or None,
        "cluster": design.get("cluster"),
        "level": 0.95,
    }
    y_code = _r_y(col, kind, values)
    if spec["question"] == "groups":
        g = spec["group"]
        if g not in df.columns:
            raise _err(f"Unknown column: {g}", "column_not_found")
        table = df.select([*design_cols, _outcome(col, kind, values).alias(".y"), pl.col(g).cast(pl.Utf8).alias(".g")])
        args["y_code"] = f"{y_code}\ndonnees$groupe <- donnees$`{g}`"
        return "test_groups", table, args
    if spec["question"] == "target":
        table = df.select([*design_cols, _outcome(col, kind, values).alias(".y")])
        args["target"] = spec["target"]
        args["y_code"] = y_code
        return "test_target", table, args
    # Paired: no survey design (the pairs are the units).
    for k in ("weights", "strata", "cluster"):
        args.pop(k)
    if spec["mode"] == "columns":
        b = spec["column_b"]
        if b not in df.columns:
            raise _err(f"Unknown column: {b}", "column_not_found")
        table = df.select([_outcome(col, kind, values).alias(".y"), _outcome(b, kind, values).alias(".y2")])
        args["y_code"] = f"{_r_y(col, kind, values, 'avant')}\n{_r_y(b, kind, values, 'apres')}"
        return "test_paired", table, args
    other = svc.dataset_spec(spec["dataset_b_id"])
    key_a, key_b = ds.get("id_column"), other.get("id_column")
    if not key_a or not key_b:
        raise _err("Both datasets need an identifier column", "test_no_id")
    _, df_b, _ = svc.cleaned(other["id"])
    if col not in df_b.columns:
        raise _err(f"Unknown column in the second dataset: {col}", "column_not_found")
    left = df.select([pl.col(key_a).alias(".id"), _outcome(col, kind, values).alias(".y")]).unique(".id", keep="first")
    right = df_b.select([pl.col(key_b).alias(".id"), _outcome(col, kind, values).alias(".y2")]).unique(
        ".id", keep="first"
    )
    table = left.join(right, on=".id", how="inner").drop(".id")
    if table.height < 3:
        raise _err("Fewer than 3 identifiers are found in both datasets", "test_no_pairs")
    args["y_code"] = (
        f"# Paires : jointure des deux jeux de données sur `{key_a}` et `{key_b}`\n"
        f"{_r_y(col, kind, values, 'avant')}\n{_r_y(col, kind, values, 'apres')}"
    )
    return "test_paired", table, args


def run(svc: Any, spec: dict[str, Any]) -> dict[str, Any]:
    fn, table, args = prepare(svc, spec)
    key = svc._cache_key("test", fn, spec, svc.cleaned(spec["dataset_id"])[0], args)
    if key not in svc._results:
        path = svc.bridge.write_table(table, f"x_{key[:16]}")
        svc._results[key] = svc.bridge.call(fn, {"path": path, **args})
    return svc._results[key]


# ----- conclusion in words -------------------------------------------------------

TEXT = {
    "fr": {
        "share_of": "la part de « {v} »",
        "mean_of": "la moyenne de {c}",
        "groups_range": "{what} varie de {lo} ({glo}) à {hi} ({ghi}) selon {group}.",
        "groups_two": "{what} est de {b} pour {gb} contre {a} pour {ga}, soit un écart de {d}.",
        "target": "{what} est de {est} (IC à 95 % : {lo} à {hi}), pour une cible de {target} : un écart de {d}.",
        "paired": "Pour les {n} mêmes unités, {what} passe de {before} à {after}, soit un écart de {d}.",
        "sig": "Cette différence est statistiquement significative ({p}).",
        "nonsig": "Cette différence n'est pas statistiquement significative ({p}).",
        "effect": "Taille d'effet : {name} = {v} ({size}).",
        "alt": "Les conditions du test principal ne sont pas toutes réunies ({why}) : le {test} donne {p}.",
        "why": {
            "not_normal_small": "petits effectifs, distribution non normale",
            "small_groups": "groupes de moins de 30 observations",
        },
        "note_expected_small": "Effectifs attendus inférieurs à 5 : le test exact de Fisher remplace le khi-deux.",
        "note_few_discordant": "Moins de 25 paires discordantes : test exact.",
        "p_small": "p < 0,001",
        "p_eq": "p = {p}",
        "points": "points",
        "sizes": {"negligible": "négligeable", "small": "faible", "medium": "moyenne", "large": "forte"},
        "effects": {
            "cramer_v": "V de Cramér",
            "hedges_g": "g de Hedges",
            "omega2": "oméga carré",
            "cohen_h": "h de Cohen",
            "cohen_d": "d de Cohen",
            "cohen_dz": "d de Cohen (paires)",
            "odds_ratio_paired": "rapport des cotes apparié",
        },
        "tests": {
            "chisq": "test du khi-deux",
            "fisher": "test exact de Fisher",
            "rao_scott": "test du khi-deux de Rao-Scott (plan d'enquête)",
            "welch": "test t de Welch",
            "svyttest": "test t sur plan d'enquête",
            "welch_anova": "ANOVA de Welch",
            "svyglm_wald": "test de Wald sur modèle pondéré",
            "binomial": "test binomial exact",
            "one_sample_t": "test t à un échantillon",
            "z_target_prop": "test z sur la proportion pondérée",
            "z_target_mean": "test z sur la moyenne pondérée",
            "paired_t": "test t apparié",
            "mcnemar": "test de McNemar",
            "mcnemar_exact": "test de McNemar exact",
            "mann_whitney": "test de Mann-Whitney",
            "kruskal": "test de Kruskal-Wallis",
            "wilcoxon_signed": "test des rangs signés de Wilcoxon",
        },
    },
    "en": {
        "share_of": 'the share of "{v}"',
        "mean_of": "the mean of {c}",
        "groups_range": "{what} ranges from {lo} ({glo}) to {hi} ({ghi}) across {group}.",
        "groups_two": "{what} is {b} for {gb} against {a} for {ga}, a gap of {d}.",
        "target": "{what} is {est} (95% CI: {lo} to {hi}), for a target of {target}: a gap of {d}.",
        "paired": "For the same {n} units, {what} goes from {before} to {after}, a change of {d}.",
        "sig": "This difference is statistically significant ({p}).",
        "nonsig": "This difference is not statistically significant ({p}).",
        "effect": "Effect size: {name} = {v} ({size}).",
        "alt": "Not all conditions of the main test are met ({why}): the {test} gives {p}.",
        "why": {
            "not_normal_small": "small samples, non-normal distribution",
            "small_groups": "groups under 30 observations",
        },
        "note_expected_small": "Expected counts below 5: Fisher's exact test replaces the chi-squared test.",
        "note_few_discordant": "Fewer than 25 discordant pairs: exact test.",
        "p_small": "p < 0.001",
        "p_eq": "p = {p}",
        "points": "points",
        "sizes": {"negligible": "negligible", "small": "small", "medium": "medium", "large": "large"},
        "effects": {
            "cramer_v": "Cramér's V",
            "hedges_g": "Hedges' g",
            "omega2": "omega squared",
            "cohen_h": "Cohen's h",
            "cohen_d": "Cohen's d",
            "cohen_dz": "Cohen's d (pairs)",
            "odds_ratio_paired": "paired odds ratio",
        },
        "tests": {
            "chisq": "chi-squared test",
            "fisher": "Fisher's exact test",
            "rao_scott": "Rao-Scott chi-squared test (survey design)",
            "welch": "Welch t test",
            "svyttest": "survey design t test",
            "welch_anova": "Welch ANOVA",
            "svyglm_wald": "Wald test on a weighted model",
            "binomial": "exact binomial test",
            "one_sample_t": "one-sample t test",
            "z_target_prop": "z test on the weighted proportion",
            "z_target_mean": "z test on the weighted mean",
            "paired_t": "paired t test",
            "mcnemar": "McNemar test",
            "mcnemar_exact": "exact McNemar test",
            "mann_whitney": "Mann-Whitney test",
            "kruskal": "Kruskal-Wallis test",
            "wilcoxon_signed": "Wilcoxon signed-rank test",
        },
    },
}


def effect_size_word(key: str, v: float) -> str | None:
    a = abs(v)
    if key == "cramer_v":
        cuts = (0.1, 0.3, 0.5)
    elif key == "omega2":
        cuts = (0.01, 0.06, 0.14)
    elif key in ("cohen_h", "cohen_d", "hedges_g", "cohen_dz"):
        cuts = (0.2, 0.5, 0.8)
    else:
        return None
    return "negligible" if a < cuts[0] else "small" if a < cuts[1] else "medium" if a < cuts[2] else "large"


def conclusion(spec: dict[str, Any], res: dict[str, Any], lang: str, fmt: Any, label: Any) -> list[str]:
    """Sentences: magnitude first, then significance, effect size and caveats.

    `fmt` is report.Fmt; `label(column, code=None)` returns readable labels.
    """
    t = TEXT[lang]
    kind = spec["kind"]
    col = spec["outcome"]["column"]
    if kind == "proportion":
        what = t["share_of"].format(v=", ".join(label(col, v) for v in spec["outcome"]["values"]))
    else:
        what = t["mean_of"].format(c=label(col))

    def val(x: float | None) -> str:
        return fmt.pct(x) if kind == "proportion" else fmt.num(x, 2)

    def gap(x: float) -> str:
        return f"{fmt.num(abs(x) * 100)} {t['points']}" if kind == "proportion" else fmt.num(abs(x), 2)

    out: list[str] = []
    q = spec["question"]
    if q == "groups":
        groups = [g for g in res.get("groups", []) if g.get("estimate") is not None]
        gl = lambda g: label(spec["group"], g["group"])  # noqa: E731
        if len(groups) == 2:
            a, b = groups
            out.append(
                t["groups_two"].format(
                    what=what[:1].upper() + what[1:],
                    a=val(a["estimate"]),
                    ga=gl(a),
                    b=val(b["estimate"]),
                    gb=gl(b),
                    d=gap(b["estimate"] - a["estimate"]),
                )
            )
        elif groups:
            lo = min(groups, key=lambda g: g["estimate"])
            hi = max(groups, key=lambda g: g["estimate"])
            out.append(
                t["groups_range"].format(
                    what=what[:1].upper() + what[1:],
                    lo=val(lo["estimate"]),
                    glo=gl(lo),
                    hi=val(hi["estimate"]),
                    ghi=gl(hi),
                    group=label(spec["group"]),
                )
            )
    elif q == "target":
        e = res["estimate"]
        out.append(
            t["target"].format(
                what=what[:1].upper() + what[1:],
                est=val(e["estimate"]),
                lo=val(e.get("ci_low")),
                hi=val(e.get("ci_high")),
                target=val(spec["target"]),
                d=gap(res["difference"]),
            )
        )
    else:
        out.append(
            t["paired"].format(
                n=fmt.num(res["n"], 0),
                what=what,
                before=val(res["before"]),
                after=val(res["after"]),
                d=gap(res["difference"]),
            )
        )
    p = res.get("p_value")
    if p is not None:
        ptxt = t["p_small"] if p < 0.001 else t["p_eq"].format(p=fmt.num(p, 3))
        out.append((t["sig"] if p < 0.05 else t["nonsig"]).format(p=ptxt))
    es = res.get("effect_size")
    if es is not None and res.get("effect_key") in t["effects"]:
        size = effect_size_word(res["effect_key"], es)
        if size:
            out.append(
                t["effect"].format(name=t["effects"][res["effect_key"]], v=fmt.num(es, 2), size=t["sizes"][size])
            )
    for note in res.get("notes") or []:
        if f"note_{note}" in t:
            out.append(t[f"note_{note}"])
    alt = res.get("alternative")
    if alt:
        why = next((t["why"][n] for n in res.get("notes") or [] if n in t["why"]), "")
        ap = alt["p_value"]
        out.append(
            t["alt"].format(
                why=why,
                test=t["tests"].get(alt["test_key"], alt["test_key"]),
                p=t["p_small"] if ap < 0.001 else t["p_eq"].format(p=fmt.num(ap, 3)),
            )
        )
    return out
