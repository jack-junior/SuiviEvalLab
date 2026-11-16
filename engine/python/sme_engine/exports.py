# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 GAYI Komi Selassi and SANOUSSI Moudjibou

"""Exports of the monitoring data (module M12).

- the tracking table in Excel: the selected period, and the values by period;
- the validated values, flat, in Excel or CSV, for work in other tools;
- the data pack: a normalised file another installation consolidates in its
  portfolio (module M13). It carries no personal data: no pseudonyms, no
  content of feedback, no secrets.
"""

from __future__ import annotations

import csv
import gzip
import json
from datetime import datetime
from pathlib import Path
from typing import Any

import xlsxwriter

from . import __version__, reception, workplan
from . import registers as rg
from .project import Project
from .rpc import INVALID_PARAMS, RpcError

PACK_FORMAT = "suivievallab-pack"
PACK_VERSION = 1

H = {
    "fr": {
        "sheet": "Suivi",
        "sheet_series": "Par période",
        "result": "Résultat",
        "code": "Code",
        "indicator": "Indicateur",
        "unit": "Unité",
        "baseline": "Référence",
        "target_period": "Cible de la période",
        "value_period": "Réalisé sur la période",
        "to_date": "Réalisé à date",
        "target_to_date": "Cible à date",
        "target": "Cible finale",
        "rate_period": "Réalisation de la période",
        "rate_to_date": "Réalisation à date",
        "status": "Statut",
        "gap": "Explication de l'écart",
        "statuses": {
            "achieved": "Atteint",
            "on_track": "En bonne voie",
            "late": "En retard",
            "not_started": "Non démarré",
            "no_data": "Sans données",
        },
        "title": "Tableau de suivi des indicateurs, {period}",
        "values": "Valeurs validées",
        "period": "Période",
        "start": "Début",
        "end": "Fin",
        "place_code": "Code du lieu",
        "place": "Lieu",
        "partner": "Partenaire",
        "categories": "Catégories",
        "value": "Valeur",
        "numerator": "Numérateur",
        "denominator": "Dénominateur",
        "submission": "Envoi",
        "channel": "Canal",
    },
    "en": {
        "sheet": "Tracking",
        "sheet_series": "By period",
        "result": "Result",
        "code": "Code",
        "indicator": "Indicator",
        "unit": "Unit",
        "baseline": "Baseline",
        "target_period": "Target of the period",
        "value_period": "Achieved in the period",
        "to_date": "Achieved to date",
        "target_to_date": "Target to date",
        "target": "End target",
        "rate_period": "Achievement in the period",
        "rate_to_date": "Achievement to date",
        "status": "Status",
        "gap": "Explanation of the gap",
        "statuses": {
            "achieved": "Achieved",
            "on_track": "On track",
            "late": "Late",
            "not_started": "Not started",
            "no_data": "No data",
        },
        "title": "Indicator tracking table, {period}",
        "values": "Validated values",
        "period": "Period",
        "start": "Start",
        "end": "End",
        "place_code": "Place code",
        "place": "Place",
        "partner": "Partner",
        "categories": "Categories",
        "value": "Value",
        "numerator": "Numerator",
        "denominator": "Denominator",
        "submission": "Submission",
        "channel": "Channel",
    },
}


def _err(message: str, key: str) -> RpcError:
    return RpcError(message, INVALID_PARAMS, data={"key": key})


def _pct(unit: str) -> bool:
    return unit == "percent"


def tracking_xlsx(svc: Any, path: Path, lang: str, period: str | None, day: str | None = None) -> dict[str, Any]:
    p = svc.project
    h = H[lang]
    view = reception.View(p)
    if not view.periods:
        raise _err("The project has no calendar", "no_periods")
    track = reception.track_all(view, {"period": period, "today": day})
    rows = {r["indicator_id"]: r for r in track["rows"]}
    for r in svc.survey_track({"period": period, "today": day}):
        rows[r["indicator_id"]] = r
    code = track["period"]
    per = next(x for x in view.periods if x["code"] == code)
    label = per["label_en"] if lang == "en" else per["label_fr"]
    gaps = {(g["indicator_id"], g["period"]): g["text"] for g in p.records("gap_comment")}
    if path.suffix.lower() != ".xlsx":
        path = path.with_suffix(".xlsx")
    wb = xlsxwriter.Workbook(str(path))
    bold = wb.add_format({"bold": True, "bg_color": "#EEEDE9", "border": 1, "text_wrap": True, "valign": "top"})
    group = wb.add_format({"bold": True, "bg_color": "#F6F5F2"})
    text = wb.add_format({"text_wrap": True, "valign": "top"})
    num = wb.add_format({"num_format": "#,##0.##", "valign": "top"})
    pct = wb.add_format({"num_format": "0.0%", "valign": "top"})
    title = wb.add_format({"bold": True, "font_size": 13})

    ws = wb.add_worksheet(h["sheet"])
    ws.write(0, 0, h["title"].format(period=label), title)
    cols = [
        "code",
        "indicator",
        "unit",
        "baseline",
        "target_period",
        "value_period",
        "to_date",
        "target_to_date",
        "target",
        "rate_period",
        "rate_to_date",
        "status",
        "gap",
    ]
    for j, c in enumerate(cols):
        ws.write(2, j, h[c], bold)
    widths = [8, 44, 12, 11, 11, 11, 11, 11, 11, 11, 11, 13, 50]
    for j, w in enumerate(widths):
        ws.set_column(j, j, w)
    ws.freeze_panes(3, 2)
    r = 3
    for node in p.framework():
        inds = [i for i in view.indicators if i["node_id"] == node["id"] and i["id"] in rows]
        if not inds:
            continue
        ws.merge_range(r, 0, r, len(cols) - 1, f"{node['code']} {node['title']}".strip(), group)
        r += 1
        for ind in inds:
            row = rows[ind["id"]]
            f = pct if _pct(ind["unit"]) else num
            ws.write(r, 0, node["code"], text)
            ws.write(r, 1, ind["name"], text)
            ws.write(r, 2, ind.get("unit_label") or ind["unit"], text)
            for j, key in enumerate(
                ("baseline", "target_period", "value_period", "to_date", "target_to_date", "target"), 3
            ):
                v = row.get(key)
                if v is not None:
                    ws.write_number(r, j, v, f)
            for j, key in ((9, "rate_period"), (10, "rate_to_date")):
                if row.get(key) is not None:
                    ws.write_number(r, j, row[key], pct)
            ws.write(r, 11, h["statuses"].get(row.get("status") or "no_data", row.get("status") or ""), text)
            ws.write(r, 12, gaps.get((ind["id"], code), ""), text)
            r += 1

    # Values by period, one column per period up to the selected one.
    ws2 = wb.add_worksheet(h["sheet_series"])
    upto = [x for x in view.periods if x["start"] <= per["start"]]
    ws2.write(0, 0, h["indicator"], bold)
    ws2.set_column(0, 0, 44)
    for j, x in enumerate(upto, 1):
        ws2.write(0, j, x["label_en"] if lang == "en" else x["label_fr"], bold)
        ws2.set_column(j, j, 11)
    ws2.freeze_panes(1, 1)
    r = 1
    for ind in view.indicators:
        row = rows.get(ind["id"])
        if not row:
            continue
        f = pct if _pct(ind["unit"]) else num
        ws2.write(r, 0, ind["name"], text)
        by = {s["period"]: s for s in row.get("series", [])}
        for j, x in enumerate(upto, 1):
            v = (by.get(x["code"]) or {}).get("value")
            if v is not None:
                ws2.write_number(r, j, v, f)
        r += 1
    wb.close()
    return {"path": str(path), "period": code, "indicators": len(rows)}


def validated_values(p: Project, lang: str) -> tuple[list[str], list[list[Any]]]:
    h = H[lang]
    view = reception.View(p)
    subs = {s["id"]: s for s in p.records("submission") if s["status"] in ("validated", "locked")}
    inds = {i["id"]: i for i in view.indicators}
    nodes = {n["id"]: n for n in p.framework()}
    periods = {x["code"]: x for x in view.periods}
    places = {x["id"]: x for x in view.places}
    partners = {x["id"]: x for x in view.partners}
    dis_keys = sorted(view.dis)
    header = [
        h["code"],
        h["indicator"],
        h["unit"],
        h["period"],
        h["start"],
        h["end"],
        h["place_code"],
        h["place"],
        h["partner"],
        *[view.dis[k].get("name", k) for k in dis_keys],
        h["value"],
        h["numerator"],
        h["denominator"],
        h["submission"],
        h["channel"],
    ]
    out = []
    sql = (
        "SELECT indicator_id, submission_id, period, place_id, partner_id, cats, value, numerator, denominator "
        "FROM value ORDER BY period, indicator_id"
    )
    for ind_id, sub_id, period, place_id, partner_id, cats, v, num, den in p.conn.execute(sql):
        sub = subs.get(sub_id)
        ind = inds.get(ind_id)
        if sub is None or ind is None:
            continue
        parts = dict(x.split("=", 1) for x in cats.split(";") if "=" in x)
        node = nodes.get(ind["node_id"], {})
        per = periods.get(period, {})
        place = places.get(place_id, {})
        out.append(
            [
                node.get("code", ""),
                ind["name"],
                ind["unit"],
                period,
                per.get("start", ""),
                per.get("end", ""),
                place.get("code", ""),
                place.get("name", ""),
                (partners.get(partner_id) or {}).get("acronym") or (partners.get(partner_id) or {}).get("name", ""),
                *[_category_name(view.dis.get(k), parts.get(k)) for k in dis_keys],
                v,
                num,
                den,
                sub_id[:8],
                sub.get("channel", ""),
            ]
        )
    return header, out


def _category_name(dis: dict[str, Any] | None, key: str | None) -> str:
    if not key or not dis:
        return ""
    cat = next((c for c in dis.get("categories", []) if c.get("key") == key), None)
    return (cat or {}).get("name") or key


def values_file(p: Project, path: Path, lang: str, kind: str) -> dict[str, Any]:
    header, rows = validated_values(p, lang)
    if kind == "csv":
        if path.suffix.lower() != ".csv":
            path = path.with_suffix(".csv")
        with path.open("w", encoding="utf-8-sig", newline="") as fh:
            w = csv.writer(fh, delimiter=";" if lang == "fr" else ",")
            w.writerow(header)
            for row in rows:
                w.writerow(
                    [
                        "" if x is None else (str(x).replace(".", ",") if lang == "fr" and isinstance(x, float) else x)
                        for x in row
                    ]
                )
    else:
        if path.suffix.lower() != ".xlsx":
            path = path.with_suffix(".xlsx")
        wb = xlsxwriter.Workbook(str(path))
        ws = wb.add_worksheet(H[lang]["values"][:31])
        bold = wb.add_format({"bold": True, "bg_color": "#EEEDE9"})
        ws.write_row(0, 0, header, bold)
        for i, row in enumerate(rows, 1):
            for j, x in enumerate(row):
                if x is None:
                    continue
                if isinstance(x, (int, float)):
                    ws.write_number(i, j, x)
                else:
                    ws.write(i, j, x)
        ws.freeze_panes(1, 0)
        ws.autofilter(0, 0, max(1, len(rows)), len(header) - 1)
        wb.close()
    return {"path": str(path), "rows": len(rows)}


# ----- data pack ------------------------------------------------------------------------------------


def pack(svc: Any, day: str | None = None) -> dict[str, Any]:
    """What a portfolio needs to know about the project, without personal data."""
    p = svc.project
    day = day or reception.today()
    meta = p.meta()
    view = reception.View(p)
    from . import schedule

    profile = schedule.profile_from_meta(meta)
    track = reception.track_all(view, {"today": day}) if view.periods else {"rows": [], "period": None}
    rows = {r["indicator_id"]: r for r in track["rows"]}
    for r in svc.survey_track({"today": day}) if view.periods else []:
        rows[r["indicator_id"]] = r
    indicators = []
    for ind in view.indicators:
        r = rows.get(ind["id"]) or {}
        indicators.append(
            {
                "id": ind["id"],
                "node_id": ind["node_id"],
                "name": ind["name"],
                "unit": ind["unit"],
                "direction": ind.get("direction") or "increase",
                "aggregation": ind.get("aggregation") or "",
                "people": ind.get("people") or "",
                "library_id": ind.get("library_id") or "",
                "source_type": ind.get("source_type") or "",
                "baseline": r.get("baseline"),
                "target": ind.get("target"),
                "to_date": r.get("to_date"),
                "target_to_date": r.get("target_to_date"),
                "rate_to_date": r.get("rate_to_date"),
                "status": r.get("status"),
                "duplicates_possible": bool(r.get("duplicates_possible")) or (ind.get("people") != "unique"),
                "series": [
                    {
                        "period": s["period"],
                        "value": s.get("value"),
                        "to_date": s.get("to_date"),
                        "target_to_date": s.get("target_to_date"),
                    }
                    for s in r.get("series", [])
                ],
            }
        )
    wp = workplan.summary(p, day)
    stats = {"feedback": len(p.records("feedback")), "feedback_overdue": 0}
    cats = rg.categories(meta)
    stats["feedback_overdue"] = sum(
        1 for f in p.records("feedback") if f["status"] in rg.FEEDBACK_OPEN and rg.feedback_deadline(f, cats) < day
    )
    return {
        "format": PACK_FORMAT,
        "version": PACK_VERSION,
        "made_with": __version__,
        "exported_at": datetime.now().isoformat(timespec="seconds"),
        "day": day,
        "project": {
            "uid": meta.get("uid", ""),
            "name": meta.get("name", ""),
            "profile": {
                k: profile.get(k)
                for k in (
                    "code",
                    "start",
                    "end",
                    "donors",
                    "countries",
                    "sectors",
                    "currency",
                    "budget",
                    "manager",
                    "implementer",
                    "color",
                    "frequency",
                )
            },
        },
        "framework": [{k: n[k] for k in ("id", "parent_id", "level", "title", "code")} for n in p.framework()],
        "periods": [
            {k: x[k] for k in ("code", "start", "end", "label_fr", "label_en", "report_due", "data_due")}
            for x in view.periods
        ],
        "current_period": track.get("period"),
        "indicators": indicators,
        "workplan": {
            "time": wp["time"],
            "physical": wp["physical"],
            "expected": wp["expected"],
            "late": wp["late"],
            "activities": wp["activities"],
            "financial": wp["budget"]["financial"],
            "planned": wp["budget"]["planned"],
            "spent": wp["budget"]["spent"],
        },
        "accountability": stats,
    }


def write_pack(svc: Any, path: Path) -> dict[str, Any]:
    data = pack(svc)
    if path.suffix.lower() != ".smepack":
        path = path.with_suffix(".smepack")
    with gzip.open(path, "wt", encoding="utf-8") as fh:
        json.dump(data, fh, ensure_ascii=False)
    return {"path": str(path), "indicators": len(data["indicators"])}


def read_pack(path: Path) -> dict[str, Any]:
    try:
        with gzip.open(path, "rt", encoding="utf-8") as fh:
            data = json.load(fh)
    except (OSError, ValueError):
        raise _err("This file is not a data pack", "pack_invalid") from None
    if not isinstance(data, dict) or data.get("format") != PACK_FORMAT:
        raise _err("This file is not a data pack", "pack_invalid")
    if int(data.get("version") or 0) > PACK_VERSION:
        raise _err("This data pack comes from a newer version", "pack_newer")
    return data
