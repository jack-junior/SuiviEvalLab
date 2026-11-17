# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 GAYI Komi Selassi and SANOUSSI Moudjibou

"""Excel data templates sent to partners and read back (section M6, channel 2).

For one period and one reporting unit, the template lists every indicator with
values entered, one line per cell of its disaggregation, with only the cells to
fill unlocked. A hidden sheet carries the identity of the project, the period,
the unit and a fingerprint of the lines. When the workbook comes back it is
refused if it belongs to another project or period, or if its lines were moved,
added or removed; the values are then stored in the unit's submission.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

import xlsxwriter

from . import intake_checks, monitoring, reception
from .rpc import INVALID_PARAMS, RpcError

FORMAT = 1
META_SHEET = "_sme"

TEXT = {
    "fr": {
        "sheet": "Saisie",
        "title": "Données de suivi à remplir",
        "project": "Projet",
        "period": "Période",
        "unit": "Remis par",
        "due": "À renvoyer avant le",
        "help": (
            "Remplissez seulement les cellules blanches. Pour un pourcentage ou un taux, donnez le numérateur "
            "et le dénominateur. Ne modifiez pas l'ordre des lignes : le fichier serait refusé au retour."
        ),
        "cols": ["Résultat", "Indicateur", "Catégorie", "Valeur", "Numérateur", "Dénominateur"],
        "total": "Total",
        "na": "Non précisé",
        "done": "Fait",
        "not_done": "Non fait",
        "source": "Source ou document de référence",
        "whole": "Le projet",
    },
    "en": {
        "sheet": "Entry",
        "title": "Monitoring data to fill in",
        "project": "Project",
        "period": "Period",
        "unit": "Sent by",
        "due": "To send back before",
        "help": (
            "Fill in the white cells only. For a percentage or a rate, give the numerator and the denominator. "
            "Do not change the order of the lines: the file would be refused when it comes back."
        ),
        "cols": ["Result", "Indicator", "Category", "Value", "Numerator", "Denominator"],
        "total": "Total",
        "na": "Not specified",
        "done": "Done",
        "not_done": "Not done",
        "source": "Source or reference document",
        "whole": "The project",
    },
}
FIRST = 8  # first line of the table (0-based)


def _err(message: str, key: str, **info: Any) -> RpcError:
    return RpcError(message, INVALID_PARAMS, data={"key": key, **info})


def lines(view: reception.View, lang: str) -> list[dict[str, Any]]:
    """The lines of the template, in order: (indicator, cells) with their labels."""
    t = TEXT[lang]
    out = []
    for ind in view.entry:
        keys = intake_checks.cells_expected(ind, view.dis)
        if not keys:
            out.append({"indicator": ind, "cats": "", "label": t["total"]})
            continue
        for key in keys:
            parts = []
            for k, code in monitoring.cats_dict(key).items():
                dis = view.dis[k]
                cat = next((c for c in dis["categories"] if c["code"] == code), None)
                parts.append(t["na"] if cat is None else (cat["en"] if lang == "en" else cat["fr"]))
            out.append({"indicator": ind, "cats": key, "label": ", ".join(parts)})
    return out


def fingerprint(items: list[dict[str, Any]]) -> str:
    raw = json.dumps([[x["indicator"]["id"], x["cats"], monitoring.kind(x["indicator"])] for x in items])
    return hashlib.sha256(raw.encode()).hexdigest()


def write(
    view: reception.View,
    period: str,
    place_id: str,
    partner_id: str,
    path: str | Path,
    lang: str = "fr",
    node_titles: dict[str, str] | None = None,
) -> int:
    """Write the template of a unit for a period, filled with the values already received."""
    t = TEXT[lang]
    per = view.period(period)
    items = lines(view, lang)
    if not items:
        raise _err("No indicator has values entered by period", "canevas_empty")
    sub = reception.find(view, period, place_id, partner_id)
    have = view.cells(sub["id"]) if sub else {}
    unit = {"place_id": place_id, "partner_id": partner_id}
    from .agenda import _unit_name

    unit_name = _unit_name(view, unit, lang) if (place_id or partner_id) else t["whole"]
    wb = xlsxwriter.Workbook(str(path))
    ws = wb.add_worksheet(t["sheet"])
    bold = wb.add_format({"bold": True})
    title = wb.add_format({"bold": True, "font_size": 14})
    head = wb.add_format({"bold": True, "bg_color": "#E8EEF0", "border": 1, "text_wrap": True, "valign": "top"})
    fixed = wb.add_format({"border": 1, "text_wrap": True, "valign": "top", "bg_color": "#F4F4F2", "locked": True})
    free = wb.add_format({"border": 1, "locked": False, "num_format": "#,##0.##"})
    shut = wb.add_format({"border": 1, "bg_color": "#D9D9D9", "locked": True})
    wrap = wb.add_format({"text_wrap": True, "italic": True, "font_color": "#555555"})
    ws.set_column(0, 0, 34)
    ws.set_column(1, 1, 46)
    ws.set_column(2, 2, 24)
    ws.set_column(3, 5, 14)
    ws.write(0, 0, t["title"], title)
    ws.write(1, 0, t["project"], bold)
    ws.write(1, 1, view.p.meta().get("name", ""))
    ws.write(2, 0, t["period"], bold)
    ws.write(2, 1, per["label_en"] if lang == "en" else per["label_fr"])
    ws.write(3, 0, t["unit"], bold)
    ws.write(3, 1, unit_name)
    ws.write(4, 0, t["due"], bold)
    ws.write(4, 1, per["data_due"])
    ws.merge_range(5, 0, 5, 5, t["help"], wrap)
    ws.set_row(5, 45)
    ws.write_row(FIRST - 1, 0, t["cols"], head)
    titles = node_titles or {}
    for i, item in enumerate(items):
        row = FIRST + i
        ind = item["indicator"]
        k = monitoring.kind(ind)
        ws.write(row, 0, titles.get(ind["node_id"], ""), fixed)
        ws.write(row, 1, ind["name"], fixed)
        ws.write(row, 2, item["label"], fixed)
        v, num, den = have.get(ind["id"], {}).get(item["cats"], (None, None, None))
        if k == "fraction":
            ws.write_blank(row, 3, None, shut)
            for col, x in ((4, num), (5, den)):
                if x is None:
                    ws.write_blank(row, col, None, free)
                else:
                    ws.write_number(row, col, x, free)
                ws.data_validation(row, col, row, col, {"validate": "decimal", "criteria": ">=", "value": 0})
        else:
            if k == "milestone":
                text = "" if v is None else (t["done"] if v == 1 else t["not_done"])
                ws.write_string(row, 3, text, free)
                ws.data_validation(row, 3, row, 3, {"validate": "list", "source": [t["done"], t["not_done"]]})
            else:
                if v is None:
                    ws.write_blank(row, 3, None, free)
                else:
                    ws.write_number(row, 3, v * 100 if ind.get("unit") == "percent" else v, free)
                ws.data_validation(row, 3, row, 3, {"validate": "decimal", "criteria": ">=", "value": 0})
            ws.write_blank(row, 4, None, shut)
            ws.write_blank(row, 5, None, shut)
    end = FIRST + len(items) + 1
    ws.write(end, 0, t["source"], bold)
    ws.merge_range(end, 1, end, 5, (sub or {}).get("source_ref", ""), wb.add_format({"border": 1, "locked": False}))
    ws.freeze_panes(FIRST, 2)
    ws.protect("", {"format_columns": True, "format_rows": True})
    meta = wb.add_worksheet(META_SHEET)
    meta.write_row(
        0,
        0,
        [
            "suivievallab",
            FORMAT,
            view.p.meta().get("uid", ""),
            period,
            place_id,
            partner_id,
            fingerprint(items),
            len(items),
            lang,
        ],
    )
    for i, item in enumerate(items):
        meta.write_row(i + 1, 0, [item["indicator"]["id"], item["cats"]])
    meta.hide()
    meta.protect()
    wb.close()
    return len(items)


def read(view: reception.View, path: str | Path) -> dict[str, Any]:
    """The values of a template filled in, after checking it is the one sent."""
    from openpyxl import load_workbook

    try:
        wb = load_workbook(str(path), data_only=True, read_only=True)
    except Exception:  # noqa: BLE001 - any unreadable file is refused the same way
        raise _err("This file cannot be read as an Excel workbook", "canevas_unreadable") from None
    try:
        if META_SHEET not in wb.sheetnames:
            raise _err("This workbook is not a SuiviEvalLab template", "canevas_not_template")
        meta_rows = list(wb[META_SHEET].iter_rows(values_only=True))
        head = meta_rows[0] if meta_rows else ()
        if len(head) < 9 or head[0] != "suivievallab":
            raise _err("This workbook is not a SuiviEvalLab template", "canevas_not_template")
        _, fmt, uid, period, place_id, partner_id, finger, n, lang = head[:9]
        if int(fmt or 0) > FORMAT:
            raise _err("This template comes from a newer version", "canevas_too_new")
        if uid != view.p.meta().get("uid"):
            raise _err("This template belongs to another project", "canevas_other_project")
        place_id, partner_id = place_id or "", partner_id or ""
        lang = "en" if lang == "en" else "fr"
        items = lines(view, lang)
        if fingerprint(items) != finger or int(n or 0) != len(items):
            raise _err(
                "The indicators changed since this template was made: make a new one",
                "canevas_outdated",
            )
        sheet = wb[TEXT[lang]["sheet"]]
        rows = list(sheet.iter_rows(min_row=FIRST + 1, max_row=FIRST + len(items) + 2, values_only=True))
        t = TEXT[lang]
        values = []
        for i, item in enumerate(items):
            row = rows[i] if i < len(rows) else ()
            row = tuple(row) + (None,) * (6 - len(row))
            ind = item["indicator"]
            if row[1] != ind["name"]:
                raise _err("The lines of the template were moved or changed", "canevas_changed", line=FIRST + i + 1)
            k = monitoring.kind(ind)
            cell: dict[str, Any] = {"indicator_id": ind["id"], "cats": monitoring.cats_dict(item["cats"])}
            if k == "fraction":
                cell["numerator"], cell["denominator"] = row[4], row[5]
            elif k == "milestone":
                # The list's words, or 1 and 0 typed over them.
                said = str(row[3] if row[3] is not None else "").strip().lower()
                words = {t["done"].lower(): 1, t["not_done"].lower(): 0, "1": 1, "0": 0, "1.0": 1, "0.0": 0}
                cell["value"] = words.get(said)
            else:
                cell["value"] = row[3]
            values.append(cell)
        source_row = rows[len(items) + 1] if len(rows) > len(items) + 1 else ()
        source_ref = (source_row[1] if len(source_row) > 1 else None) or ""
        return {
            "period": period,
            "place_id": place_id,
            "partner_id": partner_id,
            "values": values,
            "source_ref": str(source_ref),
        }
    finally:
        wb.close()


def receive(p: Any, path: str | Path, indicators: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    """Read a template and store its values in the unit's submission.

    A template for a validated submission is a revision: it is not applied, and
    the differences are returned so they can be looked at before reopening.
    `indicators` in the order the template was written with (the logframe's)."""
    view = reception.View(p, indicators)
    got = read(view, path)
    sub = reception.find(view, got["period"], got["place_id"], got["partner_id"])
    if sub and sub["status"] in ("validated", "locked"):
        before = view.cells(sub["id"])
        changes = []
        for cell in got["values"]:
            ind = next(i for i in view.entry if i["id"] == cell["indicator_id"])
            new = monitoring.clean_cell(ind, cell)
            old = before.get(ind["id"], {}).get(monitoring.cats_key(cell["cats"]), (None, None, None))
            if tuple(new) != tuple(old):
                changes.append(
                    {"indicator_id": ind["id"], "cats": cell["cats"], "before": list(old), "after": list(new)}
                )
        return {"submission_id": sub["id"], "revision": True, "changes": changes, "applied": False}
    sid = (
        sub["id"]
        if sub
        else reception.open_submission(p, got["period"], got["place_id"], got["partner_id"], channel="excel")
    )
    n = reception.save_values(p, sid, got["values"], got["source_ref"] or None)
    current = p.record("submission", sid)
    if current["status"] in ("draft", "returned"):
        reception.act(p, sid, "submit")
    return {"submission_id": sid, "revision": False, "changes": [], "applied": True, "saved": n}
