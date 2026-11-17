# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 GAYI Komi Selassi and SANOUSSI Moudjibou

"""Periodic reports in Word, following a report format (module M12).

A report covers one period (progress report), the periods of a year (annual
report) or the whole project (final report); the user picks the first and the
last period. Sections come from the format; the text sections are written in
the application and kept from one generation to the next (table report_doc).
The organisation's Word template is used when one is set, as for the survey
report.
"""

from __future__ import annotations

import io
from datetime import date, timedelta
from pathlib import Path
from typing import Any

from docx import Document
from docx.shared import Pt, RGBColor

from . import donor_formats as dfmt
from . import monitoring, reception, workplan
from . import registers as rg
from .report import (
    PLACEHOLDERS_CONTENT,
    Fmt,
    _fill_placeholders,
    _heading,
    _move_after,
    _setup,
    _table,
    f_date,
)
from .rpc import INVALID_PARAMS, RpcError

MUTED = RGBColor(0x5F, 0x5C, 0x57)

L = {
    "fr": {
        "progress": "Rapport d'avancement",
        "annual": "Rapport annuel",
        "final": "Rapport final",
        "scope_one": "Période : {a}",
        "scope_many": "Période couverte : de {a} à {b}",
        "generated": "Généré le {date} avec SuiviEvalLab",
        "to_write": "Section à rédiger dans SuiviEvalLab.",
        "indicator": "Indicateur",
        "baseline": "Référence",
        "to_date": "Réalisé à date",
        "target_to_date": "Cible à date",
        "target": "Cible finale",
        "rate": "Réalisation",
        "status": "Statut",
        "statuses": {
            "achieved": "Atteint",
            "on_track": "En bonne voie",
            "late": "En retard",
            "not_started": "Non démarré",
            "no_data": "Sans données",
            "unknown": "Sans données",
        },
        "survey": "enquête",
        "interpolated": "Cible à date interpolée entre la référence et la cible finale.",
        "provisional": "Comprend des valeurs non encore validées.",
        "nothing": "Rien à signaler pour cette période.",
        "gap": "Explication de l'écart ({period}) : {text}",
        "activity": "Activité",
        "dates": "Dates prévues",
        "state": "État",
        "progress_col": "Avancement",
        "comment": "Commentaire",
        "responsible": "Responsable",
        "states": {
            "not_started": "Non démarrée",
            "in_progress": "En cours",
            "done": "Terminée",
            "postponed": "Reportée",
            "cancelled": "Annulée",
        },
        "late": "en retard",
        "line": "Ligne budgétaire",
        "planned": "Prévu",
        "planned_to_date": "Prévu à date",
        "spent_scope": "Dépensé sur la période",
        "spent": "Dépensé à date",
        "execution": "Exécution",
        "total": "Total",
        "progress_summary": (
            "Temps écoulé : {time}. Avancement physique des activités : {physical}. Exécution financière : {financial}."
        ),
        "people": "Personnes comptées",
        "contacts": "contacts, doublons possibles",
        "unique": "personnes uniques",
        "feedback_summary": (
            "{n} retours et plaintes reçus sur la période, dont {sensitive} cas sensibles. {answered} ont reçu une "
            "réponse, {on_time} dans le délai fixé. {open} restent en cours, dont {overdue} hors délai."
        ),
        "category": "Catégorie",
        "count": "Nombre",
        "recommendation": "Recommandation",
        "response": "Réponse",
        "actions": "Actions faites",
        "responses": {
            "pending": "En attente",
            "accepted": "Acceptée",
            "partial": "Acceptée en partie",
            "rejected": "Rejetée",
        },
        "rec_states": {
            "pending": "Réponse attendue",
            "in_progress": "En cours",
            "done": "Mise en œuvre",
            "rejected": "Rejetée",
        },
        "risk": "Risque ou hypothèse",
        "level": "Niveau",
        "measures": "Mesures",
        "levels": {"low": "Faible", "medium": "Moyen", "high": "Élevé"},
        "estimate": "Estimation",
        "ci": "Intervalle de confiance à 95 %",
        "collection": "Collecte",
        "evaluation": "Évaluation",
        "kind": "Type",
        "steps": "Étapes faites",
        "eval_kinds": {
            "midterm": "Mi-parcours",
            "final": "Finale",
            "thematic": "Thématique",
            "ex_post": "Ex post",
            "other": "Autre",
        },
        "result": "Résultat",
        "indicators": "Indicateurs",
        "sources": "Sources de vérification",
        "assumptions": "Hypothèses et risques",
        "period": "Période",
        "pirs": {
            "result": "Résultat",
            "definition": "Définition",
            "unit": "Unité",
            "calculation": "Mode de calcul",
            "breakdown": "Désagrégation",
            "source": "Source des données",
            "method": "Méthode de collecte",
            "frequency": "Fréquence",
            "responsible": "Responsable",
            "baseline": "Référence",
            "target": "Cible finale",
            "direction": "Sens souhaité",
            "people": "Comptage des personnes",
        },
        "units": {
            "count": "Nombre",
            "percent": "Pourcentage",
            "rate": "Taux pour une base",
            "ratio": "Ratio",
            "mean": "Moyenne",
            "median": "Médiane",
            "score": "Score",
            "milestone": "Jalon",
            "scale": "Échelle",
        },
        "directions": {"increase": "Hausse", "decrease": "Baisse", "maintain": "Maintien"},
        "frequencies": {
            "monthly": "Mensuelle",
            "quarterly": "Trimestrielle",
            "semiannual": "Semestrielle",
            "annual": "Annuelle",
        },
        "entry_calc": "Valeurs reçues par période et agrégées selon les règles du projet ({how}).",
        "survey_calc": "Estimation à partir des données d'enquête, selon le plan d'enquête.",
        "expected": "Attendu",
    },
    "en": {
        "progress": "Progress report",
        "annual": "Annual report",
        "final": "Final report",
        "scope_one": "Period: {a}",
        "scope_many": "Period covered: from {a} to {b}",
        "generated": "Generated on {date} with SuiviEvalLab",
        "to_write": "Section to write in SuiviEvalLab.",
        "indicator": "Indicator",
        "baseline": "Baseline",
        "to_date": "Achieved to date",
        "target_to_date": "Target to date",
        "target": "End target",
        "rate": "Achievement",
        "status": "Status",
        "statuses": {
            "achieved": "Achieved",
            "on_track": "On track",
            "late": "Late",
            "not_started": "Not started",
            "no_data": "No data",
            "unknown": "No data",
        },
        "survey": "survey",
        "interpolated": "Target to date interpolated between baseline and end target.",
        "provisional": "Includes values not validated yet.",
        "nothing": "Nothing to report for this period.",
        "gap": "Explanation of the gap ({period}): {text}",
        "activity": "Activity",
        "dates": "Planned dates",
        "state": "State",
        "progress_col": "Progress",
        "comment": "Comment",
        "responsible": "Responsible",
        "states": {
            "not_started": "Not started",
            "in_progress": "In progress",
            "done": "Done",
            "postponed": "Postponed",
            "cancelled": "Cancelled",
        },
        "late": "late",
        "line": "Budget line",
        "planned": "Planned",
        "planned_to_date": "Planned to date",
        "spent_scope": "Spent in the period",
        "spent": "Spent to date",
        "execution": "Execution",
        "total": "Total",
        "progress_summary": (
            "Time elapsed: {time}. Physical progress of activities: {physical}. Financial execution: {financial}."
        ),
        "people": "People counted",
        "contacts": "contacts, possible duplicates",
        "unique": "unique people",
        "feedback_summary": (
            "{n} pieces of feedback and complaints received in the period, of which {sensitive} sensitive cases. "
            "{answered} were answered, {on_time} within the set deadline. "
            "{open} remain open, of which {overdue} overdue."
        ),
        "category": "Category",
        "count": "Number",
        "recommendation": "Recommendation",
        "response": "Response",
        "actions": "Actions done",
        "responses": {
            "pending": "Pending",
            "accepted": "Accepted",
            "partial": "Partly accepted",
            "rejected": "Rejected",
        },
        "rec_states": {
            "pending": "Response due",
            "in_progress": "In progress",
            "done": "Implemented",
            "rejected": "Rejected",
        },
        "risk": "Risk or assumption",
        "level": "Level",
        "measures": "Measures",
        "levels": {"low": "Low", "medium": "Medium", "high": "High"},
        "estimate": "Estimate",
        "ci": "95% confidence interval",
        "collection": "Data collection",
        "evaluation": "Evaluation",
        "kind": "Kind",
        "steps": "Steps done",
        "eval_kinds": {
            "midterm": "Midterm",
            "final": "Final",
            "thematic": "Thematic",
            "ex_post": "Ex post",
            "other": "Other",
        },
        "result": "Result",
        "indicators": "Indicators",
        "sources": "Means of verification",
        "assumptions": "Assumptions and risks",
        "period": "Period",
        "pirs": {
            "result": "Result",
            "definition": "Definition",
            "unit": "Unit",
            "calculation": "Calculation",
            "breakdown": "Disaggregation",
            "source": "Data source",
            "method": "Collection method",
            "frequency": "Frequency",
            "responsible": "Responsible",
            "baseline": "Baseline",
            "target": "End target",
            "direction": "Desired direction",
            "people": "Counting people",
        },
        "units": {
            "count": "Number",
            "percent": "Percentage",
            "rate": "Rate per base",
            "ratio": "Ratio",
            "mean": "Mean",
            "median": "Median",
            "score": "Score",
            "milestone": "Milestone",
            "scale": "Scale",
        },
        "directions": {"increase": "Increase", "decrease": "Decrease", "maintain": "Maintain"},
        "frequencies": {
            "monthly": "Monthly",
            "quarterly": "Quarterly",
            "semiannual": "Six-monthly",
            "annual": "Annual",
        },
        "entry_calc": "Values received by period and aggregated with the project rules ({how}).",
        "survey_calc": "Estimate from survey data, following the survey design.",
        "expected": "Expected",
    },
}

AGG = {
    "fr": {"sum": "cumul", "last": "dernière valeur", "mean": "moyenne des périodes", "max": "maximum"},
    "en": {"sum": "cumulative", "last": "latest value", "mean": "mean of the periods", "max": "maximum"},
}


def _err(message: str, key: str) -> RpcError:
    return RpcError(message, INVALID_PARAMS, data={"key": key})


# ----- formats and texts kept in the project ------------------------------------------------------


def formats(p: Any) -> list[dict[str, Any]]:
    custom = [{**f, "id": f["id"], "builtin": False} for f in p.records("report_format")]
    return [*dfmt.FORMATS, *custom]


def find_format(p: Any, fid: Any) -> dict[str, Any]:
    if fid in dfmt.BY_ID:
        return dfmt.BY_ID[fid]
    for f in p.records("report_format"):
        if f["id"] == fid:
            return {**f, "builtin": False}
    raise _err("Unknown report format", "format_not_found")


def scope(p: Any, params: dict[str, Any]) -> dict[str, Any]:
    periods = p.records("period")
    if not periods:
        raise _err("The project has no calendar", "no_periods")
    codes = [x["code"] for x in periods]
    day = params.get("today") or reception.today()
    last = params.get("to") if params.get("to") in codes else codes[monitoring.selected_period(periods, None, day)]
    first = params.get("from") if params.get("from") in codes else last
    i, j = codes.index(first), codes.index(last)
    if i > j:
        i, j = j, i
    return {
        "periods": periods[i : j + 1],
        "all": periods,
        "from": codes[i],
        "to": codes[j],
        "key": f"{codes[i]}:{codes[j]}",
    }


def doc_key(fid: str, sc: dict[str, Any]) -> str:
    return f"{fid}|{sc['key']}"


def texts(p: Any, fid: str, sc: dict[str, Any]) -> dict[str, str]:
    key = doc_key(fid, sc)
    for d in p.records("report_doc"):
        if d["key"] == key:
            return d["texts"]
    # A new report starts from the texts of the latest report in the same format.
    same = [d for d in p.records("report_doc") if d["key"].startswith(f"{fid}|")]
    return {} if not same else {k: "" for k in same[-1]["texts"]}


def save_texts(p: Any, fid: str, sc: dict[str, Any], values: Any) -> None:
    if not isinstance(values, dict):
        raise _err("texts must be an object", "invalid_params")
    clean = {str(k)[:40]: str(v or "")[:50_000] for k, v in list(values.items())[:80]}
    key = doc_key(fid, sc)
    for d in p.records("report_doc"):
        if d["key"] == key:
            p.update_record("report_doc", d["id"], {**d, "texts": clean, "saved_at": reception.now()})
            return
    p.insert_record("report_doc", {"key": key, "texts": clean, "saved_at": reception.now()})


# ----- generation -----------------------------------------------------------------------------------


def generate(
    svc: Any, path: Path, lang: str, fid: str, params: dict[str, Any], template: bytes | None
) -> dict[str, Any]:
    p = svc.project
    fmt = find_format(p, fid)
    sc = scope(p, params)
    t = L[lang]
    f = Fmt(lang)
    day = params.get("today") or reception.today()
    view = reception.View(p)
    meta_name = p.meta().get("name", "")
    label = (lambda x: x["label_en"]) if lang == "en" else (lambda x: x["label_fr"])
    first, last = sc["periods"][0], sc["periods"][-1]
    n_periods = len(sc["periods"])
    whole = n_periods == len(sc["all"])
    title = fmt["en" if lang == "en" else "fr"] if fmt.get("builtin") else fmt["name"]
    kind_title = t["final"] if whole and n_periods > 1 else t["annual"] if n_periods > 1 else t["progress"]
    scope_text = (
        t["scope_one"].format(a=label(first))
        if n_periods == 1
        else t["scope_many"].format(a=label(first), b=label(last))
    )

    anchor = None
    if template:
        doc = Document(io.BytesIO(template))
        _fill_placeholders(
            doc,
            {
                "{{projet}}": meta_name,
                "{{project}}": meta_name,
                "{{date}}": f_date(lang),
                "{{titre_rapport}}": f"{kind_title} : {label(last)}"
                if lang == "fr"
                else f"{kind_title}: {label(last)}",
                "{{report_title}}": f"{kind_title}: {label(last)}",
                "{{periode}}": scope_text,
                "{{period}}": scope_text,
            },
        )
        anchor = next((x for x in doc.paragraphs if any(k in x.text for k in PLACEHOLDERS_CONTENT)), None)
    else:
        doc = Document()
        _setup(doc)
    body = doc.element.body
    start = len([el for el in body if not el.tag.endswith("}sectPr")])
    if not template:
        doc.add_paragraph(meta_name, style="Title")
        sub = doc.add_paragraph(title)
        sub.runs[0].font.size = Pt(13)
        sub.runs[0].font.color.rgb = MUTED
    if fid not in ("me_plan", "pirs"):
        doc.add_paragraph(scope_text)
    gen = doc.add_paragraph(t["generated"].format(date=f_date(lang)))
    gen.runs[0].font.size = Pt(9)
    gen.runs[0].font.color.rgb = MUTED

    written = texts(p, fid, sc)
    ctx = _Context(svc, view, sc, lang, day)
    for i, sec in enumerate(fmt["sections"], start=1):
        _heading(doc, f"{i}. {sec['en' if lang == 'en' else 'fr']}", level=1)
        if sec["kind"] == "text":
            text = (written.get(sec["key"]) or "").strip()
            if text:
                for para in text.split("\n\n"):
                    doc.add_paragraph(para.strip())
            else:
                note = doc.add_paragraph(t["to_write"])
                note.runs[0].italic = True
                note.runs[0].font.color.rgb = MUTED
            continue
        SECTIONS[sec["kind"]](doc, ctx, t, f)

    if anchor is not None:
        generated = [el for el in body if not el.tag.endswith("}sectPr")][start:]
        _move_after(anchor, generated)
    if path.suffix.lower() != ".docx":
        path = path.with_suffix(".docx")
    doc.save(path)
    return {"path": str(path), "sections": len(fmt["sections"])}


class _Context:
    """What the sections read, computed once."""

    def __init__(self, svc: Any, view: reception.View, sc: dict[str, Any], lang: str, day: str):
        self.svc = svc
        self.p = svc.project
        self.view = view
        self.sc = sc
        self.lang = lang
        self.day = day
        self.codes = [x["code"] for x in sc["periods"]]
        self.start = sc["periods"][0]["start"]
        self.end = sc["periods"][-1]["end"]
        self.nodes = self.p.framework()
        self.indicators = view.indicators
        self._track: dict[str, Any] | None = None

    @property
    def track(self) -> dict[str, dict[str, Any]]:
        if self._track is None:
            rows = reception.track_all(self.view, {"period": self.sc["to"], "today": self.day})["rows"]
            out = {r["indicator_id"]: r for r in rows}
            for r in self.svc.survey_track({"period": self.sc["to"], "today": self.day}):
                out[r["indicator_id"]] = r
            self._track = out
        return self._track

    def baseline(self, ind: dict[str, Any]) -> float | None:
        row = self.track.get(ind["id"])
        return row.get("baseline") if row else monitoring.baseline(ind)

    def label(self, period: dict[str, Any]) -> str:
        return period["label_en"] if self.lang == "en" else period["label_fr"]

    def period_label(self, code: str) -> str:
        per = next((x for x in self.sc["all"] if x["code"] == code), None)
        return self.label(per) if per else code

    def ordered(self) -> list[tuple[dict[str, Any], list[dict[str, Any]]]]:
        out = []
        for n in self.nodes:
            inds = [i for i in self.indicators if i["node_id"] == n["id"]]
            if inds:
                out.append((n, inds))
        return out


def _indicator_rows(
    ctx: _Context, inds: list[dict[str, Any]], t: dict[str, Any], f: Fmt, per_period: bool
) -> list[list[str]]:
    rows = []
    for ind in inds:
        r = ctx.track.get(ind["id"])
        unit = ind["unit"]
        if r is None:
            continue
        name = ind["name"] + (f" ({t['survey']})" if r.get("kind") == "survey" else "")
        cells = [name, f.value(r.get("baseline"), unit)]
        if per_period:
            by = {s["period"]: s for s in r.get("series", [])}
            cells += [f.value((by.get(c) or {}).get("value"), unit) for c in ctx.codes]
        cells += [
            f.value(r.get("to_date"), unit),
            f.value(r.get("target_to_date"), unit),
            f.value(r.get("target"), unit),
            f.pct(r.get("rate_to_date"), 0),
            t["statuses"].get(r.get("status") or "unknown", r.get("status") or ""),
        ]
        rows.append(cells)
    return rows


def _tracking(doc: Any, ctx: _Context, t: dict[str, Any], f: Fmt) -> None:
    per_period = 1 < len(ctx.codes) <= 4
    header = [t["indicator"], t["baseline"]]
    if per_period:
        header += [ctx.period_label(c) for c in ctx.codes]
    header += [t["to_date"], t["target_to_date"], t["target"], t["rate"], t["status"]]
    rows: list[list[str]] = []
    notes = set()
    for node, inds in ctx.ordered():
        mine = _indicator_rows(ctx, inds, t, f, per_period)
        if not mine:
            continue
        rows.append([f"{node['code']} {node['title']}".strip()] + [""] * (len(header) - 1))
        rows += mine
        for ind in inds:
            r = ctx.track.get(ind["id"]) or {}
            if r.get("interpolated"):
                notes.add(t["interpolated"])
            if r.get("provisional"):
                notes.add(t["provisional"])
    if not rows:
        doc.add_paragraph(t["nothing"])
        return
    first = 5.0 if not per_period else 4.0
    rest = (16.6 - first) / (len(header) - 1)
    table = _table(doc, header, rows, [first] + [rest] * (len(header) - 1))
    _merge_group_rows(table, rows)
    for n in sorted(notes):
        para = doc.add_paragraph(n)
        para.runs[0].font.size = Pt(9)
        para.runs[0].font.color.rgb = MUTED


def _merge_group_rows(table: Any, rows: list[list[str]]) -> None:
    """Rows naming a result (only the first cell filled) span the whole table."""
    from .report import _shade

    for i, r in enumerate(rows, start=1):
        if r[0] and not any(r[1:]):
            cells = table.rows[i].cells
            merged = cells[0].merge(cells[-1])
            merged.text = ""
            run = merged.paragraphs[0].add_run(r[0])
            run.bold = True
            run.font.size = Pt(9)
            _shade(merged, "F6F5F2")


def _gap_texts(ctx: _Context, ind_id: str) -> list[tuple[str, str]]:
    return [
        (g["period"], g["text"])
        for g in ctx.p.records("gap_comment", ind_id)
        if g["period"] in ctx.codes and (g.get("text") or "").strip()
    ]


def _results(doc: Any, ctx: _Context, t: dict[str, Any], f: Fmt) -> None:
    acts = workplan.activities_view(ctx.p, ctx.day)
    any_node = False
    for node in ctx.nodes:
        inds = [i for i in ctx.indicators if i["node_id"] == node["id"]]
        mine = [a for a in acts if a.get("node_id") == node["id"] and not a.get("parent_id")]
        if not inds and not mine:
            continue
        any_node = True
        _heading(doc, f"{node['code']} {node['title']}".strip(), level=2)
        for ind in inds:
            r = ctx.track.get(ind["id"])
            if r is None:
                continue
            unit = ind["unit"]
            status = t["statuses"].get(r.get("status") or "unknown", "")
            line = f"{ind['name']} : " if ctx.lang == "fr" else f"{ind['name']}: "
            parts = [f"{t['to_date'].lower()} {f.value(r.get('to_date'), unit)}"]
            if r.get("target_to_date") is not None:
                parts.append(f"{t['target_to_date'].lower()} {f.value(r.get('target_to_date'), unit)}")
            if r.get("rate_to_date") is not None:
                parts.append(f"{t['rate'].lower()} {f.pct(r.get('rate_to_date'), 0)}")
            doc.add_paragraph(line + ", ".join(parts) + f". {status}.")
            for period, text in _gap_texts(ctx, ind["id"]):
                para = doc.add_paragraph(t["gap"].format(period=ctx.period_label(period), text=text))
                para.runs[0].italic = True
        if mine:
            rows = []
            for a in mine:
                if a.get("end") and a["end"] < ctx.start or a.get("start") and a["start"] > ctx.end:
                    continue
                rows.append(
                    [
                        a["title"],
                        t["states"][a["status"]] + (f", {t['late']}" if a["late"] else ""),
                        f.pct(a["progress"] / 100, 0),
                    ]
                )
            if rows:
                _table(doc, [t["activity"], t["state"], t["progress_col"]], rows, [9.6, 4, 3])
    if not any_node:
        doc.add_paragraph(t["nothing"])


def _gaps(doc: Any, ctx: _Context, t: dict[str, Any], f: Fmt) -> None:
    found = False
    for ind in ctx.indicators:
        for period, text in _gap_texts(ctx, ind["id"]):
            found = True
            para = doc.add_paragraph()
            para.add_run(f"{ind['name']} ({ctx.period_label(period)}). ").bold = True
            para.add_run(text)
    if not found:
        doc.add_paragraph(t["nothing"])


def _activity_rows(acts: list[dict[str, Any]], t: dict[str, Any], f: Fmt, lang: str) -> list[list[str]]:
    from .report import f_date as fd

    rows = []
    for a in acts:
        dates = " - ".join(fd(lang, x) for x in (a.get("start"), a.get("end")) if x)
        state = t["states"][a["status"]] + (f", {t['late']}" if a["late"] else "")
        title = ("    " if a.get("parent_id") else "") + a["title"]
        rows.append([title, dates, state, f.pct(a["progress"] / 100, 0), a.get("comment", "")[:300]])
    return rows


def _activities(doc: Any, ctx: _Context, t: dict[str, Any], f: Fmt) -> None:
    acts = [
        a
        for a in workplan.activities_view(ctx.p, ctx.day)
        if a.get("start") and a.get("end") and a["start"] <= ctx.end and a["end"] >= ctx.start
    ]
    if not acts:
        doc.add_paragraph(t["nothing"])
        return
    _table(
        doc,
        [t["activity"], t["dates"], t["state"], t["progress_col"], t["comment"]],
        _activity_rows(acts, t, f, ctx.lang),
        [5.4, 3.4, 2.6, 1.8, 3.4],
    )


def _next_activities(doc: Any, ctx: _Context, t: dict[str, Any], f: Fmt) -> None:
    codes = [x["code"] for x in ctx.sc["all"]]
    i = codes.index(ctx.sc["to"]) + 1
    if i < len(codes):
        nxt = ctx.sc["all"][i]
        a0, a1 = nxt["start"], nxt["end"]
    else:
        a0 = (date.fromisoformat(ctx.end) + timedelta(days=1)).isoformat()
        a1 = (date.fromisoformat(ctx.end) + timedelta(days=92)).isoformat()
    from .report import f_date as fd

    rows = [
        [a["title"], " - ".join(fd(ctx.lang, x) for x in (a["start"], a["end"])), a.get("responsible", "")]
        for a in workplan.activities_view(ctx.p, ctx.day)
        if a.get("start")
        and a.get("end")
        and a["start"] <= a1
        and a["end"] >= a0
        and a["status"] not in ("done", "cancelled")
    ]
    if not rows:
        doc.add_paragraph(t["nothing"])
        return
    _table(doc, [t["activity"], t["dates"], t["responsible"]], rows, [8.6, 4.6, 3.4])


def _budget(doc: Any, ctx: _Context, t: dict[str, Any], f: Fmt) -> None:
    summary = workplan.summary(ctx.p, min(ctx.end, ctx.day) if ctx.day >= ctx.start else ctx.end)
    b = summary["budget"]
    lines = ctx.p.records("budget_line")
    if not lines:
        doc.add_paragraph(t["nothing"])
        return
    expenses = ctx.p.records("expense")
    in_scope: dict[str, float] = {}
    to_end: dict[str, float] = {}
    for e in expenses:
        if ctx.start <= e["date"] <= ctx.end:
            in_scope[e["line_id"]] = in_scope.get(e["line_id"], 0.0) + e["amount"]
        if e["date"] <= ctx.end:
            to_end[e["line_id"]] = to_end.get(e["line_id"], 0.0) + e["amount"]
    started = {x["code"] for x in ctx.sc["all"] if x["start"] <= ctx.end}
    rows, tot = [], [0.0, 0.0, 0.0, 0.0]
    for ln in lines:
        planned = sum(ln["planned"].values())
        to_date = sum(v for k, v in ln["planned"].items() if k in started)
        sp, sp_all = in_scope.get(ln["id"], 0.0), to_end.get(ln["id"], 0.0)
        tot = [tot[0] + planned, tot[1] + to_date, tot[2] + sp, tot[3] + sp_all]
        name = f"{ln['code']} {ln['name']}".strip()
        rows.append(
            [
                name,
                f.num(planned, 0),
                f.num(to_date, 0),
                f.num(sp, 0),
                f.num(sp_all, 0),
                f.pct(sp_all / planned if planned else None, 0),
            ]
        )
    rows.append(
        [
            t["total"],
            f.num(tot[0], 0),
            f.num(tot[1], 0),
            f.num(tot[2], 0),
            f.num(tot[3], 0),
            f.pct(tot[3] / tot[0] if tot[0] else None, 0),
        ]
    )
    cur = summary.get("currency") or ""
    header = [t["line"], t["planned"], t["planned_to_date"], t["spent_scope"], t["spent"], t["execution"]]
    if cur:
        header = [header[0]] + [f"{h} ({cur})" if i < 4 else h for i, h in enumerate(header[1:])]
    _table(doc, header, rows, [5, 2.4, 2.4, 2.4, 2.4, 2])
    doc.add_paragraph(
        t["progress_summary"].format(
            time=f.pct(summary["time"], 0), physical=f.pct(summary["physical"], 0), financial=f.pct(b["financial"], 0)
        )
    )


def _beneficiaries(doc: Any, ctx: _Context, t: dict[str, Any], f: Fmt) -> None:
    rows = []
    for ind in ctx.indicators:
        if ind["unit"] != "count":
            continue
        r = ctx.track.get(ind["id"])
        if r is None:
            continue
        how = t["unique"] if ind.get("people") == "unique" and not r.get("duplicates_possible") else t["contacts"]
        rows.append([ind["name"], f.value(r.get("to_date"), "count"), f.value(r.get("target"), "count"), how])
    if not rows:
        doc.add_paragraph(t["nothing"])
        return
    _table(doc, [t["indicator"], t["to_date"], t["target"], t["people"]], rows, [7.6, 2.8, 2.8, 3.4])


def _feedback(doc: Any, ctx: _Context, t: dict[str, Any], f: Fmt) -> None:
    from collections import Counter

    cats = rg.categories(ctx.p.meta())
    fb = [x for x in ctx.p.records("feedback") if ctx.start <= x["received"] <= ctx.end]
    if not fb:
        doc.add_paragraph(t["nothing"])
        return
    answered = [x for x in fb if x.get("answered_at")]
    on_time = [x for x in answered if x["answered_at"][:10] <= rg.feedback_deadline(x, cats)]
    open_ = [x for x in fb if x["status"] in rg.FEEDBACK_OPEN]
    overdue = [x for x in open_ if rg.feedback_deadline(x, cats) < ctx.day]
    doc.add_paragraph(
        t["feedback_summary"].format(
            n=len(fb),
            sensitive=sum(1 for x in fb if x["sensitive"]),
            answered=len(answered),
            on_time=len(on_time),
            open=len(open_),
            overdue=len(overdue),
        )
    )
    names = {c["key"]: c.get("name") or CATEGORY_NAMES[ctx.lang].get(c["key"], c["key"]) for c in cats}
    rows = [[names.get(k, k), str(n)] for k, n in Counter(x["category"] for x in fb).most_common()]
    _table(doc, [t["category"], t["count"]], rows, [10, 3])


CATEGORY_NAMES = {
    "fr": {
        "info_request": "Demande d'information",
        "assistance_request": "Demande d'assistance",
        "service_complaint": "Plainte sur un service",
        "staff_conduct": "Comportement du personnel",
        "sea": "Exploitation et abus sexuels",
        "fraud": "Fraude ou corruption",
        "thanks": "Remerciement ou suggestion",
        "other": "Autre",
    },
    "en": {
        "info_request": "Request for information",
        "assistance_request": "Request for assistance",
        "service_complaint": "Complaint about a service",
        "staff_conduct": "Staff conduct",
        "sea": "Sexual exploitation and abuse",
        "fraud": "Fraud or corruption",
        "thanks": "Thanks or suggestion",
        "other": "Other",
    },
}


def _recommendations(doc: Any, ctx: _Context, t: dict[str, Any], f: Fmt) -> None:
    recs = ctx.p.records("recommendation")
    if not recs:
        doc.add_paragraph(t["nothing"])
        return
    rows = []
    for r in recs:
        done = sum(1 for a in r["actions"] if a["status"] == "done")
        rows.append(
            [
                r["text"],
                t["responses"][r["response"]],
                f"{done}/{len(r['actions'])}",
                t["rec_states"][rg.recommendation_status(r)],
            ]
        )
    _table(doc, [t["recommendation"], t["response"], t["actions"], t["status"]], rows, [8.6, 3, 2, 3])


def _risks(doc: Any, ctx: _Context, t: dict[str, Any], f: Fmt) -> None:
    risks = [r for r in ctx.p.records("risk") if r["status"] == "active"]
    if not risks:
        doc.add_paragraph(t["nothing"])
        return
    risks.sort(key=lambda r: -r["probability"] * r["impact"])
    rows = [
        [
            r["title"],
            f"{t['levels'][rg.risk_level(r)]} ({r['probability']}x{r['impact']})",
            r.get("measures", ""),
            r.get("responsible", ""),
        ]
        for r in risks
    ]
    _table(doc, [t["risk"], t["level"], t["measures"], t["responsible"]], rows, [5.2, 2.6, 6, 2.8])


def _lessons(doc: Any, ctx: _Context, t: dict[str, Any], f: Fmt) -> None:
    lessons = [x for x in ctx.p.records("lesson") if not x.get("date") or ctx.start <= x["date"] <= ctx.end]
    if not lessons:
        doc.add_paragraph(t["nothing"])
        return
    for x in lessons:
        para = doc.add_paragraph()
        para.add_run(f"{x['title']}. ").bold = True
        para.add_run(" ".join(v for v in (x.get("finding"), x.get("lesson")) if v))


def _surveys(doc: Any, ctx: _Context, t: dict[str, Any], f: Fmt) -> None:
    rows = []
    for ind in ctx.indicators:
        r = ctx.track.get(ind["id"])
        if not r or r.get("kind") != "survey":
            continue
        for s in r.get("series", []):
            if s["period"] in ctx.codes and s.get("value") is not None:
                ci = s.get("ci") or [None, None]
                rows.append(
                    [
                        ind["name"],
                        ctx.period_label(s["period"]),
                        f.value(s["value"], ind["unit"]),
                        f"{f.value(ci[0], ind['unit'])} - {f.value(ci[1], ind['unit'])}" if ci[0] is not None else "",
                    ]
                )
    if not rows:
        doc.add_paragraph(t["nothing"])
        return
    _table(doc, [t["indicator"], t["collection"], t["estimate"], t["ci"]], rows, [7, 3, 3, 3.6])


def _evaluations(doc: Any, ctx: _Context, t: dict[str, Any], f: Fmt) -> None:
    evs = ctx.p.records("evaluation")
    if not evs:
        doc.add_paragraph(t["nothing"])
        return
    from .report import f_date as fd

    rows = [
        [
            e["title"],
            t["eval_kinds"].get(e["kind"], e["kind"]),
            " - ".join(fd(ctx.lang, x) for x in (e.get("start"), e.get("end")) if x),
            f"{sum(1 for s in rg.EVAL_STEPS if e['steps'][s]['done'])}/{len(rg.EVAL_STEPS)}",
        ]
        for e in evs
    ]
    _table(doc, [t["evaluation"], t["kind"], t["dates"], t["steps"]], rows, [7, 3, 4.4, 2.2])


def _logframe(doc: Any, ctx: _Context, t: dict[str, Any], f: Fmt) -> None:
    rows = []
    for n in ctx.nodes:
        inds = [i for i in ctx.indicators if i["node_id"] == n["id"]]
        rows.append(
            [
                f"{n['code']} {n['title']}".strip(),
                "\n".join(i["name"] for i in inds),
                "\n".join(f.value(ctx.baseline(i), i["unit"]) for i in inds),
                "\n".join(f.value(i.get("target"), i["unit"]) for i in inds),
                "\n".join(i.get("source") or "" for i in inds),
                n.get("assumptions") or "",
            ]
        )
    if not rows:
        doc.add_paragraph(t["nothing"])
        return
    _table(
        doc,
        [t["result"], t["indicators"], t["baseline"], t["target"], t["sources"], t["assumptions"]],
        rows,
        [3.6, 4, 1.8, 1.8, 2.6, 2.8],
    )


def _calendar(doc: Any, ctx: _Context, t: dict[str, Any], f: Fmt) -> None:
    periods = ctx.sc["all"]
    entry = [i for i in ctx.indicators if reception.is_entry(i)]
    if not entry or not periods:
        doc.add_paragraph(t["nothing"])
        return
    fiscal = int(ctx.view.profile.get("fiscal_start_month") or 1)
    shown = periods[:12]
    rows = [
        [i["name"], i.get("responsible", "")]
        + [t["expected"] if monitoring.expected(i, x, fiscal) else "" for x in shown]
        for i in entry
    ]
    width = max(0.9, (16.6 - 7) / len(shown))
    _table(
        doc, [t["indicator"], t["responsible"]] + [x["code"] for x in shown], rows, [4.6, 2.4] + [width] * len(shown)
    )


def _pirs(doc: Any, ctx: _Context, t: dict[str, Any], f: Fmt) -> None:
    nodes = {n["id"]: n for n in ctx.nodes}
    labels = t["pirs"]
    dis = {d["key"]: d for d in ctx.p.records("disaggregation")}
    for ind in ctx.indicators:
        _heading(doc, ind["name"], level=2)
        node = nodes.get(ind["node_id"], {})
        if reception.is_entry(ind):
            calc = t["entry_calc"].format(how=AGG[ctx.lang].get(ind.get("aggregation") or "sum", ""))
        else:
            calc = t["survey_calc"]
        rows = [
            [labels["result"], f"{node.get('code', '')} {node.get('title', '')}".strip()],
            [labels["definition"], ind.get("definition") or ""],
            [
                labels["unit"],
                t["units"].get(ind["unit"], ind["unit"]) + (f", {ind['unit_label']}" if ind.get("unit_label") else ""),
            ],
            [labels["calculation"], calc],
            [labels["breakdown"], ", ".join((dis.get(k) or {}).get("name", k) for k in ind.get("breakdowns") or [])],
            [labels["source"], ind.get("source") or ""],
            [labels["method"], ind.get("method") or ""],
            [labels["frequency"], t["frequencies"].get(ind.get("frequency") or "", "")],
            [labels["responsible"], ind.get("responsible") or ""],
            [labels["baseline"], f.value(ctx.baseline(ind), ind["unit"])],
            [labels["target"], f.value(ind.get("target"), ind["unit"])],
            [labels["direction"], t["directions"].get(ind.get("direction") or "increase", "")],
        ]
        if ind["unit"] == "count":
            rows.append(
                [labels["people"], t["unique"] if ind.get("people") == "unique" else t["contacts"].split(",")[0]]
            )
        _kv_table(doc, rows)


def _kv_table(doc: Any, rows: list[list[str]]) -> None:
    """Two columns, the field in bold on a shaded cell: the layout of a reference sheet."""
    from docx.shared import Cm

    from .report import _shade

    table = doc.add_table(rows=0, cols=2)
    try:
        table.style = "Table Grid"
    except (KeyError, ValueError):
        pass
    for k, v in rows:
        cells = table.add_row().cells
        cells[0].text = ""
        run = cells[0].paragraphs[0].add_run(k)
        run.bold = True
        run.font.size = Pt(9)
        _shade(cells[0], "EEEDE9")
        cells[1].text = ""
        cells[1].paragraphs[0].add_run(v).font.size = Pt(9)
        cells[0].width, cells[1].width = Cm(4.2), Cm(12.4)
    from docx.oxml.ns import qn

    table.autofit = False
    for col, w in zip(table._tbl.tblGrid.findall(qn("w:gridCol")), (4.2, 12.4), strict=False):
        col.set(qn("w:w"), str(int(Cm(w).twips)))
    doc.add_paragraph()


SECTIONS = {
    "tracking": _tracking,
    "results": _results,
    "gaps": _gaps,
    "activities": _activities,
    "next_activities": _next_activities,
    "budget": _budget,
    "beneficiaries": _beneficiaries,
    "feedback": _feedback,
    "recommendations": _recommendations,
    "risks": _risks,
    "lessons": _lessons,
    "surveys": _surveys,
    "evaluations": _evaluations,
    "logframe": _logframe,
    "calendar": _calendar,
    "pirs": _pirs,
}
