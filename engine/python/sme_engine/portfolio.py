# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 GAYI Komi Selassi and SANOUSSI Moudjibou

"""Portfolio dashboard and organisation resources (modules M13 and M14).

Every project file is read without being changed; packs received from other
offices (exports.py) are read the same way. For each project the dashboard puts
three measures of progress side by side (section 6.6):

- time: share of the project duration gone by;
- physical: share of the indicators on track, and the progress of activities;
- financial: amount spent over the amount planned;

and gives a global status with its reasons. Thresholds are set once for the
organisation (settings.json in the user folder).

Common indicators are those adopted from the same sheet of the indicator
library in several projects. Counts are added up across projects; people can
be counted in more than one project, so their total is always flagged as a
possible double count (each project keeps its own pseudonym key).
"""

from __future__ import annotations

import json
import shutil
import sqlite3
from collections import Counter
from datetime import date, timedelta
from pathlib import Path
from typing import Any

from . import exports, reception
from .project import APPLICATION_ID, SCHEMA_VERSION, Project
from .rpc import INVALID_PARAMS, RpcError

DEFAULT_SETTINGS = {
    # Share of indicators achieved or on track for the project to be on track.
    "indicators_on_track": 0.7,
    # Below this share, the project is in difficulty.
    "indicators_difficulty": 0.4,
    # How far spending may run ahead of physical progress of activities.
    "financial_margin": 0.15,
    # Share of late activities from which the project is to watch.
    "late_activities": 0.2,
}


def _err(message: str, key: str) -> RpcError:
    return RpcError(message, INVALID_PARAMS, data={"key": key})


def _folder() -> Path:
    from . import trust

    return trust.path().parent


def settings() -> dict[str, float]:
    try:
        data = json.loads((_folder() / "settings.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        data = {}
    out = dict(DEFAULT_SETTINGS)
    for k in DEFAULT_SETTINGS:
        v = data.get("portfolio", {}).get(k)
        if isinstance(v, (int, float)) and 0 <= v <= 1:
            out[k] = float(v)
    return out


def save_settings(values: Any) -> dict[str, float]:
    if not isinstance(values, dict):
        raise _err("settings must be an object", "invalid_params")
    file = _folder() / "settings.json"
    try:
        data = json.loads(file.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        data = {}
    clean = {}
    for k in DEFAULT_SETTINGS:
        v = values.get(k)
        if not isinstance(v, (int, float)) or not 0 <= v <= 1:
            raise _err(f"{k} must be between 0 and 1", "number_out_of_range")
        clean[k] = float(v)
    data["portfolio"] = clean
    file.parent.mkdir(parents=True, exist_ok=True)
    tmp = file.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, indent=1), encoding="utf-8")
    tmp.replace(file)
    return settings()


# ----- one project ----------------------------------------------------------------------------------


class _Svc:
    """What exports.pack needs of a service, for a project read without R."""

    def __init__(self, p: Project):
        self.project = p

    def survey_track(self, params: dict[str, Any]) -> list[dict[str, Any]]:
        return []  # survey estimates need R: the dashboard stays fast without them


def pack_of(path: Path, day: str) -> dict[str, Any] | None:
    try:
        conn = sqlite3.connect(f"{path.resolve().as_uri()}?mode=ro", uri=True)
    except sqlite3.Error:
        return None
    try:
        if conn.execute("PRAGMA application_id").fetchone()[0] != APPLICATION_ID:
            return None
        if conn.execute("PRAGMA user_version").fetchone()[0] != SCHEMA_VERSION:
            return None
        conn.row_factory = sqlite3.Row
        return exports.pack(_Svc(Project(path, conn)), day)
    except (sqlite3.Error, KeyError, ValueError):
        return None
    finally:
        conn.close()


def card(pk: dict[str, Any], day: str, cfg: dict[str, float], source: str, path: str) -> dict[str, Any]:
    profile = pk["project"]["profile"]
    inds = [i for i in pk["indicators"] if i.get("source_type") in ("routine", "secondary", "dhis2")]
    judged = [i for i in inds if i.get("status") in ("achieved", "on_track", "late")]
    on_track = [i for i in judged if i["status"] in ("achieved", "on_track")]
    share = len(on_track) / len(judged) if judged else None
    wp = pk["workplan"]
    late_share = wp["late"] / wp["activities"] if wp.get("activities") else None
    reasons = []
    level = 0
    if share is not None and share < cfg["indicators_difficulty"]:
        reasons.append("indicators_low")
        level = 2
    elif share is not None and share < cfg["indicators_on_track"]:
        reasons.append("indicators_watch")
        level = max(level, 1)
    if wp.get("financial") is not None and wp.get("physical") is not None:
        if wp["financial"] - wp["physical"] > cfg["financial_margin"]:
            reasons.append("spending_ahead")
            level = max(level, 1)
    if late_share is not None and late_share > cfg["late_activities"]:
        reasons.append("activities_late")
        level = max(level, 1)
    if len(reasons) >= 2:
        level = 2
    periods = pk.get("periods") or []
    deadlines = sorted(
        [("data", x["data_due"], x) for x in periods if x["data_due"] >= day]
        + [("report", x["report_due"], x) for x in periods if x["report_due"] >= day],
        key=lambda d: (d[1], d[0] == "report"),
    )
    nxt = deadlines[0] if deadlines else None
    status = "unknown" if share is None and wp.get("physical") is None else ("on_track", "watch", "difficulty")[level]
    return {
        "source": source,
        "path": path,
        "uid": pk["project"].get("uid", ""),
        "name": pk["project"]["name"],
        "profile": profile,
        "day": pk.get("day"),
        "exported_at": pk.get("exported_at") if source == "pack" else None,
        "time": wp.get("time"),
        "indicators": len(inds),
        "indicators_judged": len(judged),
        "indicators_on_track": share,
        "late_indicators": [i["name"] for i in judged if i["status"] == "late"][:10],
        "physical": wp.get("physical"),
        "expected": wp.get("expected"),
        "financial": wp.get("financial"),
        "planned": wp.get("planned"),
        "spent": wp.get("spent"),
        "activities": wp.get("activities"),
        "late_activities": wp.get("late"),
        "feedback_overdue": (pk.get("accountability") or {}).get("feedback_overdue", 0),
        "next_deadline": {
            "kind": nxt[0],
            "date": nxt[1],
            "label_fr": nxt[2]["label_fr"],
            "label_en": nxt[2]["label_en"],
        }
        if nxt
        else None,
        "deadlines_30": sum(1 for d in deadlines if d[1] <= (date.fromisoformat(day) + timedelta(days=30)).isoformat()),
        "status": status,
        "reasons": reasons,
        "series": [
            {"name": i["name"], "unit": i["unit"], "rate": i.get("rate_to_date"), "status": i.get("status")}
            for i in inds
        ],
    }


# ----- packs received from other offices ------------------------------------------------------------


def packs_folder() -> Path:
    return _folder() / "packs"


def import_pack(path: Path) -> dict[str, Any]:
    data = exports.read_pack(path)
    folder = packs_folder()
    folder.mkdir(parents=True, exist_ok=True)
    uid = data["project"].get("uid") or path.stem
    safe = "".join(c for c in uid if c.isalnum() or c in "-_")[:80] or "paquet"
    # A newer pack of the same project replaces the older one.
    shutil.copyfile(path, folder / f"{safe}.smepack")
    return {"name": data["project"]["name"], "uid": uid}


def remove_pack(uid: Any) -> None:
    if not isinstance(uid, str) or not uid:
        raise _err("Unknown pack", "invalid_params")
    safe = "".join(c for c in uid if c.isalnum() or c in "-_")[:80]
    file = packs_folder() / f"{safe}.smepack"
    if file.is_file():
        file.unlink()


def packs() -> list[tuple[Path, dict[str, Any]]]:
    out = []
    folder = packs_folder()
    if not folder.is_dir():
        return out
    for f in sorted(folder.glob("*.smepack")):
        try:
            out.append((f, exports.read_pack(f)))
        except RpcError:
            continue
    return out


# ----- the dashboard ------------------------------------------------------------------------------


def dashboard(paths: Any, day: str | None = None, archived: Any = None) -> dict[str, Any]:
    day = day or reception.today()
    cfg = settings()
    hidden = set(archived) if isinstance(archived, list) else set()
    cards, raw = [], []
    seen_uids = set()
    for path in (paths if isinstance(paths, list) else [])[:200]:
        if not isinstance(path, str) or path in hidden:
            continue
        pk = pack_of(Path(path), day)
        if pk is None:
            continue
        seen_uids.add(pk["project"].get("uid"))
        cards.append(card(pk, day, cfg, "file", path))
        raw.append(pk)
    for f, pk in packs():
        if pk["project"].get("uid") and pk["project"]["uid"] in seen_uids:
            continue  # the project itself is open here: its file is newer than its pack
        cards.append(card(pk, pk.get("day") or day, cfg, "pack", str(f)))
        raw.append(pk)
    by = {"donor": Counter(), "country": Counter(), "sector": Counter()}
    for c in cards:
        for d in c["profile"].get("donors") or []:
            name = d.get("name") if isinstance(d, dict) else str(d)
            if name:
                by["donor"][name] += 1
        for k, field in (("country", "countries"), ("sector", "sectors")):
            for x in c["profile"].get(field) or []:
                by[k][x] += 1
    return {
        "day": day,
        "settings": cfg,
        "cards": cards,
        "overview": {
            "projects": len(cards),
            "by_status": dict(Counter(c["status"] for c in cards)),
            "late_activities": sum(c["late_activities"] or 0 for c in cards),
            "late_indicators": sum(len(c["late_indicators"]) for c in cards),
            "feedback_overdue": sum(c["feedback_overdue"] or 0 for c in cards),
            "deadlines_30": sum(c["deadlines_30"] for c in cards),
            "planned": sum(c["planned"] or 0 for c in cards),
            "spent": sum(c["spent"] or 0 for c in cards),
        },
        "distribution": {k: dict(v.most_common()) for k, v in by.items()},
        "common": common_indicators(raw),
    }


def common_indicators(raw: list[dict[str, Any]]) -> list[dict[str, Any]]:
    groups: dict[str, list[tuple[dict[str, Any], dict[str, Any]]]] = {}
    for pk in raw:
        for ind in pk["indicators"]:
            if ind.get("library_id"):
                groups.setdefault(ind["library_id"], []).append((pk, ind))
    out = []
    for lib, items in groups.items():
        if len(items) < 2:
            continue
        unit = items[0][1]["unit"]
        same_unit = all(i["unit"] == unit for _, i in items)
        additive = same_unit and unit == "count"
        total = sum(i["to_date"] or 0 for _, i in items) if additive else None
        target = sum(i["target"] or 0 for _, i in items) if additive else None
        out.append(
            {
                "library_id": lib,
                "name": items[0][1]["name"],
                "unit": unit,
                "projects": [
                    {"name": pk["project"]["name"], "to_date": i["to_date"], "target": i["target"]} for pk, i in items
                ],
                "total": total,
                "target": target,
                # People counted in several projects cannot be told apart: flagged, never hidden.
                "double_count_possible": additive,
                "not_additive": not additive,
            }
        )
    return sorted(out, key=lambda x: x["name"])


# ----- a project as a model for a new one -----------------------------------------------------------

KEEP_AS_MODEL = {
    "indicator",
    "period",
    "place",
    "partner",
    "disaggregation",
    "target",
    "activity",
    "budget_line",
    "risk",
    "learning_question",
    "evaluation",
    "qual_theme",
    "report_format",
}
CLEARED = (
    "submission",
    "gap_comment",
    "justification",
    "task",
    "event",
    "quality_review",
    "connection",
    "expense",
    "feedback",
    "recommendation",
    "lesson",
    "meeting",
    "qual_note",
    "report_doc",
    "dataset",
    "cleaning_rule",
    "saved_test",
    "analysis",
    "routine_value",
)


def duplicate_as_model(source: Path, target: Path, name: str) -> None:
    """A new project file with the design of another and none of its data."""
    if target.exists():
        raise _err("A file already has this name", "file_exists")
    with sqlite3.connect(f"{source.resolve().as_uri()}?mode=ro", uri=True) as src:
        if src.execute("PRAGMA application_id").fetchone()[0] != APPLICATION_ID:
            raise _err("This is not a SuiviEvalLab project", "not_a_project")
        if src.execute("PRAGMA user_version").fetchone()[0] != SCHEMA_VERSION:
            raise _err("Open the project once in this version first", "project_older")
        dst = sqlite3.connect(target)
        src.backup(dst)
        dst.close()
    p = Project.open(target)
    try:
        tables = {r[0] for r in p.conn.execute("SELECT name FROM sqlite_master WHERE type = 'table'")}
        import secrets
        import uuid

        with p.conn:
            for t in CLEARED:
                if t in tables:
                    p.conn.execute(f"DELETE FROM {t}")
            for t in ("value", "person", "measure_cache"):
                if t in tables:
                    p.conn.execute(f"DELETE FROM {t}")
            p.conn.execute("DELETE FROM meta WHERE key LIKE 'rev:%' OR key IN ('person_key', 'previous_open')")
            p.conn.execute("INSERT OR REPLACE INTO meta(key, value) VALUES ('uid', ?)", (uuid.uuid4().hex,))
            p.conn.execute("INSERT OR REPLACE INTO meta(key, value) VALUES ('name', ?)", (name,))
            p.conn.execute("INSERT OR REPLACE INTO meta(key, value) VALUES ('person_key', ?)", (secrets.token_hex(32),))
        for a in p.records("activity"):
            p.update_record(
                "activity",
                a["id"],
                {**a, "status": "not_started", "progress": 0.0, "actual_start": "", "actual_end": "", "comment": ""},
            )
        for x in p.records("period"):
            clean = {k: v for k, v in x.items() if k not in ("reported_at",)}
            p.update_record("period", x["id"], {**clean, "state": "open"})
        for r in p.records("risk"):
            p.update_record("risk", r["id"], {**r, "reviews": []})
        for e in p.records("evaluation"):
            steps = {k: {**v, "done": False} for k, v in e["steps"].items()}
            p.update_record("evaluation", e["id"], {**e, "steps": steps, "conclusions": ""})
        p.conn.execute("VACUUM")
    finally:
        p.close()


def note_docx(data: dict[str, Any], path: Path, lang: str) -> dict[str, Any]:
    """The portfolio synthesis note in Word."""
    from docx import Document
    from docx.shared import Pt

    from .report import Fmt, _heading, _setup, _table, f_date

    f = Fmt(lang)
    fr = lang != "en"
    doc = Document()
    _setup(doc)
    doc.add_paragraph("Note de synthèse du portefeuille" if fr else "Portfolio summary note", style="Title")
    sub = doc.add_paragraph(f_date(lang))
    sub.runs[0].font.size = Pt(11)
    o = data["overview"]
    st = o["by_status"]
    names = {
        "on_track": "en bonne voie" if fr else "on track",
        "watch": "à surveiller" if fr else "to watch",
        "difficulty": "en difficulté" if fr else "in difficulty",
        "unknown": "sans données" if fr else "no data",
    }
    _heading(doc, "1. Vue d'ensemble" if fr else "1. Overview", 1)
    parts = ", ".join(f"{st[k]} {names[k]}" for k in ("on_track", "watch", "difficulty", "unknown") if st.get(k))
    doc.add_paragraph(
        (
            f"{o['projects']} projets : {parts}. {o['late_activities']} activités en retard, {o['late_indicators']} "
            f"indicateurs en retard, {o['feedback_overdue']} retours hors délai, {o['deadlines_30']} échéances dans les "
            "30 prochains jours."
        )
        if fr
        else (
            f"{o['projects']} projects: {parts}. {o['late_activities']} late activities, {o['late_indicators']} late "
            f"indicators, {o['feedback_overdue']} overdue pieces of feedback, {o['deadlines_30']} deadlines in the "
            "next 30 days."
        )
    )
    _heading(doc, "2. Projets" if fr else "2. Projects", 1)
    header = (
        ["Projet", "Temps écoulé", "Indicateurs en bonne voie", "Activités", "Exécution financière", "Statut"]
        if fr
        else ["Project", "Time elapsed", "Indicators on track", "Activities", "Financial execution", "Status"]
    )
    rows = [
        [
            c["name"],
            f.pct(c["time"], 0),
            f.pct(c["indicators_on_track"], 0),
            f.pct(c["physical"], 0),
            f.pct(c["financial"], 0),
            names[c["status"]],
        ]
        for c in data["cards"]
    ]
    _table(doc, header, rows, [5.2, 2.2, 2.6, 2.2, 2.4, 2.4])
    reasons_txt = {
        "indicators_low": "peu d'indicateurs en bonne voie" if fr else "few indicators on track",
        "indicators_watch": "indicateurs à surveiller" if fr else "indicators to watch",
        "spending_ahead": "dépenses en avance sur l'avancement" if fr else "spending ahead of progress",
        "activities_late": "activités en retard" if fr else "activities late",
    }
    for c in data["cards"]:
        if c["reasons"] or c["late_indicators"]:
            para = doc.add_paragraph()
            para.add_run(f"{c['name']}. ").bold = True
            text = ", ".join(reasons_txt[r] for r in c["reasons"])
            if c["late_indicators"]:
                lead = "Indicateurs en retard : " if fr else "Late indicators: "
                text = (text + ". " if text else "") + lead + ", ".join(c["late_indicators"])
            para.add_run(text + ".")
    if data["common"]:
        _heading(doc, "3. Indicateurs communs" if fr else "3. Common indicators", 1)
        rows = []
        for x in data["common"]:
            total = (
                f.value(x["total"], x["unit"])
                if x["total"] is not None
                else ("non additionnable" if fr else "not additive")
            )
            rows.append(
                [x["name"], str(len(x["projects"])), total, f.value(x["target"], x["unit"]) if x["target"] else ""]
            )
        _table(
            doc,
            ["Indicateur", "Projets", "Total à date", "Cible"]
            if fr
            else ["Indicator", "Projects", "Total to date", "Target"],
            rows,
            [8, 2, 3.4, 3.2],
        )
        doc.add_paragraph(
            "Les personnes comptées dans plusieurs projets peuvent l'être deux fois : les totaux de personnes sont des "
            "maximums."
            if fr
            else "People counted in several projects may be counted twice: totals of people are upper bounds."
        )
    if path.suffix.lower() != ".docx":
        path = path.with_suffix(".docx")
    doc.save(path)
    return {"path": str(path)}


def html(data: dict[str, Any], path: Path, lang: str) -> dict[str, Any]:
    """The dashboard as a single read-only HTML page, to share or print to PDF."""
    from .report import Fmt, f_date
    from .share import e

    f = Fmt(lang)
    fr = lang != "en"
    st_name = {
        "on_track": "En bonne voie" if fr else "On track",
        "watch": "À surveiller" if fr else "To watch",
        "difficulty": "En difficulté" if fr else "In difficulty",
        "unknown": "Sans données" if fr else "No data",
    }
    colors = {"on_track": "#2e6b47", "watch": "#875811", "difficulty": "#a3392b", "unknown": "#69665f"}

    def bar(x: float | None) -> str:
        w = 0 if x is None else max(0.0, min(1.0, x)) * 100
        return f'<span class="bar"><span style="width:{w:.0f}%"></span></span> {e(f.pct(x, 0))}'

    o = data["overview"]
    rows = "".join(
        f"<tr><td><strong>{e(c['name'])}</strong><br><small>{e(', '.join((d.get('name') if isinstance(d, dict) else str(d)) for d in c['profile'].get('donors') or []))}</small></td>"
        f"<td>{bar(c['time'])}</td><td>{bar(c['indicators_on_track'])}</td><td>{bar(c['physical'])}</td>"
        f'<td>{bar(c["financial"])}</td><td style="color:{colors[c["status"]]};font-weight:600">{e(st_name[c["status"]])}</td></tr>'
        for c in data["cards"]
    )
    head = (
        ["Projet", "Temps écoulé", "Indicateurs en bonne voie", "Activités", "Exécution financière", "Statut"]
        if fr
        else ["Project", "Time elapsed", "Indicators on track", "Activities", "Financial execution", "Status"]
    )
    kpis = [
        ("Projets" if fr else "Projects", o["projects"]),
        ("Activités en retard" if fr else "Late activities", o["late_activities"]),
        ("Indicateurs en retard" if fr else "Late indicators", o["late_indicators"]),
        ("Échéances à 30 jours" if fr else "Deadlines within 30 days", o["deadlines_30"]),
    ]
    common = ""
    if data["common"]:
        lines = "".join(
            f"<tr><td>{e(x['name'])}</td><td>{len(x['projects'])}</td><td>{e(f.value(x['total'], x['unit']) if x['total'] is not None else '')}</td></tr>"
            for x in data["common"]
        )
        common = (
            f"<h2>{'Indicateurs communs' if fr else 'Common indicators'}</h2><table><tr><th>{'Indicateur' if fr else 'Indicator'}</th>"
            f"<th>{'Projets' if fr else 'Projects'}</th><th>{'Total à date' if fr else 'Total to date'}</th></tr>{lines}</table>"
            f'<p class="note">{"Les totaux de personnes sont des maximums : une personne peut être comptée dans plusieurs projets." if fr else "Totals of people are upper bounds: a person may be counted in several projects."}</p>'
        )
    page = f"""<!DOCTYPE html><html lang="{lang}"><head><meta charset="utf-8">
<title>{e("Tableau de bord du portefeuille" if fr else "Portfolio dashboard")}</title>
<style>
body{{font:14px/1.5 "Segoe UI",system-ui,sans-serif;color:#1f1e1c;margin:32px auto;max-width:1100px;padding:0 20px}}
h1{{font:600 26px Georgia,serif;margin:0}} h2{{font:600 18px Georgia,serif;margin-top:28px}}
.kpis{{display:grid;grid-template-columns:repeat(4,1fr);gap:10px;margin:18px 0}}
.kpi{{border:1px solid #e3e1db;border-radius:10px;padding:12px}} .kpi b{{display:block;font-size:24px}}
table{{border-collapse:collapse;width:100%}} th,td{{border-bottom:1px solid #e3e1db;padding:8px;text-align:left;vertical-align:top}}
th{{font-size:12px;color:#5f5c57}} .bar{{display:inline-block;width:70px;height:8px;background:#e6e4df;border-radius:4px;vertical-align:middle}}
.bar span{{display:block;height:100%;background:#1d4f91;border-radius:4px}} .note,.muted{{color:#5f5c57;font-size:12px}}
</style></head><body>
<h1>{e("Tableau de bord du portefeuille" if fr else "Portfolio dashboard")}</h1>
<p class="muted">{e(f_date(lang))}. {e("Lecture seule, généré par SuiviEvalLab." if fr else "Read only, generated by SuiviEvalLab.")}</p>
<div class="kpis">{"".join(f'<div class="kpi">{e(k)}<b>{v}</b></div>' for k, v in kpis)}</div>
<table><tr>{"".join(f"<th>{e(h)}</th>" for h in head)}</tr>{rows}</table>
{common}
</body></html>"""
    if path.suffix.lower() != ".html":
        path = path.with_suffix(".html")
    path.write_text(page, encoding="utf-8")
    return {"path": str(path)}
