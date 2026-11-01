"""Monitoring plan as an Excel workbook (indicator reference sheet).

One row per indicator, in framework order: result, definition, calculation in
words, unit, breakdown, data source and collection method, frequency, who is
responsible, baseline, target and its date, current value and status. A second
sheet holds the results framework. This is the table donors ask for in a
monitoring and evaluation plan; it stays editable in Excel.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import xlsxwriter

from . import frameworks
from .report import Fmt, T

P = {
    "fr": {
        "sheet": "Plan de suivi",
        "sheet_fw": "Cadre de résultats",
        "title": "Plan de suivi des indicateurs",
        "cols": [
            "Code",
            "Niveau",
            "Résultat",
            "Indicateur",
            "Définition",
            "Mode de calcul",
            "Unité",
            "Désagrégation",
            "Source des données",
            "Méthode de collecte",
            "Fréquence",
            "Responsable",
            "Référence",
            "Cible",
            "Échéance de la cible",
            "Valeur actuelle",
            "Réalisation",
            "Statut",
        ],
        "fw_cols": ["Code", "Niveau", "Intitulé", "Description", "Hypothèses et risques", "Indicateurs"],
        "units": {"percent": "Pourcentage", "mean": "Moyenne", "count": "Effectif", "ratio": "Ratio"},
        "freq": {
            "": "",
            "monthly": "Mensuelle",
            "quarterly": "Trimestrielle",
            "semiannual": "Semestrielle",
            "annual": "Annuelle",
            "rounds": "À chaque enquête (référence, mi-parcours, fin)",
            "other": "Autre",
        },
        "share": "Part des observations où {cond}",
        "share_any": "Part des observations où au moins une condition est remplie : {cond}",
        "mean": "Moyenne de {col}",
        "count_rows": "Nombre d'observations où {cond} (pondéré : effectif estimé dans la population)",
        "count_sum": "Somme de {col}",
        "ratio": "Somme de {num} / somme de {den}",
        "ratio_k": "Somme de {num} / somme de {den}, multipliée par {k}",
        "cond": "{col} vaut {values}",
        "and": " et ",
        "or": " ou ",
        "incomplete": "Règle de calcul à compléter",
        "routine": "Suivi de routine : valeurs relevées par période, {how}",
        "how": {"sum": "cumulées", "last": "dernière valeur", "mean": "moyenne des périodes"},
        "generated": "Généré le {date} avec SuiviEvalLab",
    },
    "en": {
        "sheet": "Monitoring plan",
        "sheet_fw": "Results framework",
        "title": "Indicator monitoring plan",
        "cols": [
            "Code",
            "Level",
            "Result",
            "Indicator",
            "Definition",
            "Calculation",
            "Unit",
            "Breakdown",
            "Data source",
            "Collection method",
            "Frequency",
            "Responsible",
            "Baseline",
            "Target",
            "Target date",
            "Current value",
            "Achievement",
            "Status",
        ],
        "fw_cols": ["Code", "Level", "Title", "Description", "Assumptions and risks", "Indicators"],
        "units": {"percent": "Percentage", "mean": "Mean", "count": "Count", "ratio": "Ratio"},
        "freq": {
            "": "",
            "monthly": "Monthly",
            "quarterly": "Quarterly",
            "semiannual": "Every six months",
            "annual": "Yearly",
            "rounds": "At each survey (baseline, midline, endline)",
            "other": "Other",
        },
        "share": "Share of observations where {cond}",
        "share_any": "Share of observations meeting at least one condition: {cond}",
        "mean": "Mean of {col}",
        "count_rows": "Number of observations where {cond} (weighted: estimated number in the population)",
        "count_sum": "Sum of {col}",
        "ratio": "Sum of {num} / sum of {den}",
        "ratio_k": "Sum of {num} / sum of {den}, times {k}",
        "cond": "{col} is {values}",
        "and": " and ",
        "or": " or ",
        "incomplete": "Calculation rule to complete",
        "routine": "Routine monitoring: values recorded per period, {how}",
        "how": {"sum": "cumulative", "last": "latest value", "mean": "mean of the periods"},
        "generated": "Generated on {date} with SuiviEvalLab",
    },
}


def calculation(ind: dict[str, Any], lang: str, label: Any, f: Fmt) -> str:
    """The calculation rule of an indicator, in words, with readable labels."""
    p = P[lang]
    if ind.get("source_type") == "routine":
        return p["routine"].format(how=p["how"][ind.get("aggregation") or "sum"])
    conds = ind.get("conditions") or (
        [{"column": ind["column"], "values": ind.get("success_values") or []}] if ind.get("column") else []
    )
    joiner = p["or"] if ind.get("combine") == "any" else p["and"]
    cond = joiner.join(
        p["cond"].format(
            col=f"« {label(c['column'])} »" if lang == "fr" else f'"{label(c["column"])}"',
            values=", ".join(label(c["column"], v) for v in c["values"]),
        )
        for c in conds
    )
    unit = ind["unit"]
    if unit == "percent":
        return (
            p["share_any" if ind.get("combine") == "any" and len(conds) > 1 else "share"].format(cond=cond)
            if conds
            else p["incomplete"]
        )
    if unit == "count":
        if ind.get("count_mode") == "sum":
            return p["count_sum"].format(col=label(ind["column"])) if ind.get("column") else p["incomplete"]
        return p["count_rows"].format(cond=cond) if conds else p["incomplete"]
    if unit == "ratio":
        if not (ind.get("numerator") and ind.get("denominator")):
            return p["incomplete"]
        k = ind.get("multiplier") or 1
        key = "ratio" if k == 1 else "ratio_k"
        return p[key].format(num=label(ind["numerator"]), den=label(ind["denominator"]), k=f.num(k, 0))
    return p["mean"].format(col=label(ind["column"])) if ind.get("column") else p["incomplete"]


def generate(svc: Any, path: Path, lang: str) -> dict[str, Any]:
    from .report import f_date

    p, t, f = P[lang], T[lang], Fmt(lang)
    snap = svc.snapshot()
    label = svc.labeller(lang)
    nodes = {n["id"]: n for n in snap["framework"]}
    model = snap["project"]["framework_model"]
    summary = {r["indicator_id"]: r for r in svc.overview()["rows"]}
    if path.suffix.lower() != ".xlsx":
        path = path.with_suffix(".xlsx")

    wb = xlsxwriter.Workbook(str(path))
    head = wb.add_format(
        {"bold": True, "bg_color": "#1D4F91", "font_color": "#FFFFFF", "text_wrap": True, "valign": "top", "border": 1}
    )
    cell = wb.add_format({"text_wrap": True, "valign": "top", "border": 1, "border_color": "#D9D6CF"})
    title = wb.add_format({"bold": True, "font_size": 14})
    muted = wb.add_format({"font_color": "#5F5C57", "italic": True})
    st = {
        "achieved": wb.add_format({"valign": "top", "border": 1, "border_color": "#D9D6CF", "bg_color": "#E2EFE7"}),
        "on_track": wb.add_format({"valign": "top", "border": 1, "border_color": "#D9D6CF", "bg_color": "#F5EBD8"}),
        "late": wb.add_format({"valign": "top", "border": 1, "border_color": "#D9D6CF", "bg_color": "#F6E3DF"}),
        "unknown": cell,
    }

    ws = wb.add_worksheet(p["sheet"])
    ws.write(
        0,
        0,
        f"{snap['project']['name']} : {p['title']}" if lang == "fr" else f"{snap['project']['name']}: {p['title']}",
        title,
    )
    ws.write(1, 0, p["generated"].format(date=f_date(lang)), muted)
    widths = [7, 11, 30, 34, 36, 40, 12, 18, 24, 24, 16, 18, 11, 11, 13, 13, 11, 13]
    for i, w in enumerate(widths):
        ws.set_column(i, i, w)
    ws.write_row(3, 0, p["cols"], head)
    ws.set_row(3, 30)
    ws.freeze_panes(4, 4)
    for sheet in (ws,):
        sheet.set_landscape()
        sheet.set_paper(9)  # A4
        sheet.fit_to_pages(1, 0)
        sheet.repeat_rows(3)
        sheet.set_margins(left=0.4, right=0.4, top=0.5, bottom=0.5)
    row = 4
    for ind in snap["indicators"]:
        node = nodes.get(ind["node_id"], {})
        s = summary.get(ind["id"], {})
        unit = ind["unit"]
        by = [label(c) for c in (ind.get("disaggregation"), ind.get("disaggregation2")) if c]
        status = s.get("status", "unknown")
        values = [
            node.get("code") or "",
            frameworks.name(model, node["level"], lang) if node else "",
            node.get("title", ""),
            ind["name"],
            ind.get("definition") or "",
            calculation(ind, lang, label, f),
            p["units"][unit] + (f" ({ind['unit_label']})" if ind.get("unit_label") else ""),
            " × ".join(by),
            ind.get("source") or "",
            ind.get("method") or "",
            p["freq"].get(ind.get("frequency") or "", ""),
            ind.get("responsible") or "",
            f.value(s.get("baseline"), unit) if s.get("baseline") is not None else "",
            f.value(ind.get("target"), unit) if ind.get("target") is not None else "",
            ind.get("target_date") or "",
            f.value(s.get("current"), unit) if s.get("current") is not None else "",
            f.pct(s.get("achievement"), 0) if s.get("achievement") is not None else "",
        ]
        ws.write_row(row, 0, values, cell)
        ws.write(row, len(values), t["status"][status], st[status])
        row += 1
    ws.autofilter(3, 0, max(row - 1, 3), len(p["cols"]) - 1)

    fw = wb.add_worksheet(p["sheet_fw"])
    for i, w in enumerate([8, 18, 46, 40, 36, 46]):
        fw.set_column(i, i, w)
    fw.write_row(0, 0, p["fw_cols"], head)
    fw.set_landscape()
    fw.set_paper(9)
    fw.fit_to_pages(1, 0)
    fw.repeat_rows(0)
    for i, node in enumerate(snap["framework"], start=1):
        names = "\n".join(x["name"] for x in snap["indicators"] if x["node_id"] == node["id"])
        fw.write_row(
            i,
            0,
            [
                node.get("code") or "",
                frameworks.name(model, node["level"], lang),
                node["title"],
                node.get("description") or "",
                node.get("assumptions") or "",
                names,
            ],
            cell,
        )
    wb.close()
    return {"path": str(path), "indicators": len(snap["indicators"])}
