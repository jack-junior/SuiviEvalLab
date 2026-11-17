# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 GAYI Komi Selassi and SANOUSSI Moudjibou

"""Methods of reception (submissions, values, alerts) and of the tracking table."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from . import reception as rc
from .project import Project
from .rpc import Server

if TYPE_CHECKING:
    from .service import Service


def state(p: Project) -> dict[str, Any]:
    """The part of the snapshot this module owns."""
    view = rc.View(p, [])
    gaps: dict[str, list[dict[str, Any]]] = {}
    for g in p.records("gap_comment"):
        gaps.setdefault(g["indicator_id"], []).append(g)
    return {
        "submissions": list(view.subs.values()),
        "units": view.units(),
        "gap_comments": gaps,
        "tasks": p.records("task"),
        "quality_reviews": _by_indicator(p.records("quality_review")),
        "events": p.records("event"),
    }


def _by_indicator(records: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    out: dict[str, list[dict[str, Any]]] = {}
    for r in records:
        out.setdefault(r["indicator_id"], []).append(r)
    return out


def submission_detail(p: Project, sub_id: Any) -> dict[str, Any]:
    sub = p.record("submission", sub_id)
    view = rc.View(p)
    cells = {ind_id: {key: list(v) for key, v in c.items()} for ind_id, c in view.cells(sub["id"]).items()}
    found = rc.alerts(view, sub)
    just = rc.justified(p)
    return {
        "submission": sub,
        "cells": cells,
        "alerts": [{**a, "justification": just.get(a["key"], {}).get("text")} for a in found],
    }


def register_reception(server: Server, svc: Service) -> None:
    def project() -> Project:
        return svc.project

    def changed() -> None:
        svc._results.clear()

    @server.method("submission.open")
    def sub_open(params: dict[str, Any]) -> dict[str, Any]:
        sid = rc.open_submission(
            project(),
            params.get("period"),
            params.get("place_id") or "",
            params.get("partner_id") or "",
            params.get("channel") or "entry",
        )
        return {**svc.snapshot(), "created": sid}

    @server.method("submission.get")
    def sub_get(params: dict[str, Any]) -> dict[str, Any]:
        return submission_detail(project(), params.get("id"))

    @server.method("submission.save")
    def sub_save(params: dict[str, Any]) -> dict[str, Any]:
        n = rc.save_values(project(), params.get("id"), params.get("values"), params.get("source_ref"))
        changed()
        return {**svc.snapshot(), **submission_detail(project(), params.get("id")), "saved": n}

    @server.method("submission.act")
    def sub_act(params: dict[str, Any]) -> dict[str, Any]:
        rc.act(project(), params.get("id"), params.get("action"), params.get("comment"))
        changed()
        return {**svc.snapshot(), **submission_detail(project(), params.get("id"))}

    @server.method("submission.delete")
    def sub_delete(params: dict[str, Any]) -> dict[str, Any]:
        rc.delete_submission(project(), params.get("id"))
        changed()
        return svc.snapshot()

    @server.method("people.save")
    def people_save(params: dict[str, Any]) -> dict[str, Any]:
        from . import team_rpc

        team_rpc.require_encryption(project())
        n = rc.save_people(
            project(), params.get("id"), params.get("indicator_id"), params.get("ids"), params.get("cats")
        )
        changed()
        return {**svc.snapshot(), **submission_detail(project(), params.get("id")), "people": n}

    @server.method("alert.justify")
    def alert_justify(params: dict[str, Any]) -> dict[str, Any]:
        p = project()
        key = params.get("key")
        if not isinstance(key, str) or key.count(":") != 3:
            raise rc._err("Unknown alert", "invalid_params")
        text = str(params.get("text") or "").strip()[:2000]
        current = rc.justified(p).get(key)
        if current:
            p.delete_record("justification", current["id"])
        if text:
            p.insert_record("justification", {"key": key, "text": text, "at": rc.now()})
        sub_id = key.split(":", 1)[0]
        return {**svc.snapshot(), **submission_detail(p, sub_id)}

    @server.method("tracking.table")
    def tracking_table(params: dict[str, Any]) -> dict[str, Any]:
        view = rc.View(project(), svc.ordered_indicators())
        out = rc.track_all(view, params)
        # Survey estimates, unless the view is narrowed to a place, a partner or a category.
        if not (params.get("place_id") or params.get("partner_id") or params.get("cats")):
            out = {**out, "rows": [*out["rows"], *svc.survey_track(params)]}
        return out

    @server.method("tracking.breakdown")
    def tracking_breakdown(params: dict[str, Any]) -> dict[str, Any]:
        p = project()
        view = rc.View(p)
        ind = p.record("indicator", params.get("indicator_id"))
        return {"values": rc.by_category(view, ind, str(params.get("key")), params)}

    @server.method("tracking.crosstab")
    def tracking_crosstab(params: dict[str, Any]) -> dict[str, Any]:
        p = project()
        view = rc.View(p)
        ind = p.record("indicator", params.get("indicator_id"))
        if not rc.is_entry(ind):
            raise rc._err("This indicator is computed from imported data", "invalid_params")
        return rc.crosstab(view, ind, params)

    @server.method("quality.save")
    def quality_save(params: dict[str, Any]) -> dict[str, Any]:
        """A data quality review of an indicator: five criteria, conclusions, actions."""
        from . import agenda

        p = project()
        ind = p.record("indicator", params.get("indicator_id"))
        spec = params.get("review") or {}
        if not isinstance(spec, dict):
            raise rc._err("The review must be an object", "invalid_params")
        scores = {}
        for crit in ("validity", "reliability", "timeliness", "precision", "integrity"):
            v = (spec.get("scores") or {}).get(crit)
            scores[crit] = v if v in ("met", "partly", "not_met") else ""
        review = {
            "date": agenda._day(spec.get("date"), "date", required=True)[:10],
            "scores": scores,
            "reviewer": str(spec.get("reviewer") or "").strip()[:120],
            "conclusions": str(spec.get("conclusions") or "").strip()[:4000],
            "actions": str(spec.get("actions") or "").strip()[:4000],
        }
        if params.get("id"):
            p.update_record("quality_review", params["id"], review)
        else:
            p.insert_record("quality_review", review, scope=ind["id"])
        return svc.snapshot()

    @server.method("quality.delete")
    def quality_delete(params: dict[str, Any]) -> dict[str, Any]:
        project().delete_record("quality_review", params.get("id"))
        return svc.snapshot()

    @server.method("gap.save")
    def gap_save(params: dict[str, Any]) -> dict[str, Any]:
        p = project()
        ind = p.record("indicator", params.get("indicator_id"))
        period = params.get("period")
        rc.View(p, []).period(period)
        text = str(params.get("text") or "").strip()[:4000]
        current = next((g for g in p.records("gap_comment", ind["id"]) if g["period"] == period), None)
        if current and not text:
            p.delete_record("gap_comment", current["id"])
        elif current:
            p.update_record("gap_comment", current["id"], {**current, "text": text, "at": rc.now()})
        elif text:
            p.insert_record("gap_comment", {"period": period, "text": text, "at": rc.now()}, scope=ind["id"])
        return svc.snapshot()


# ----- agenda and tasks ------------------------------------------------------------------------

ICS_TITLES = {
    "fr": {"data_due": "Données de {period} attendues", "report_due": "Rapport de {period} à rendre"},
    "en": {"data_due": "Data for {period} due", "report_due": "Report for {period} due"},
}


def register_agenda(server: Server, svc: Service) -> None:
    from pathlib import Path

    from . import agenda

    def project() -> Project:
        return svc.project

    def lang(params: dict[str, Any]) -> str:
        return "en" if params.get("lang") == "en" else "fr"

    @server.method("today.project")
    def today_project(params: dict[str, Any]) -> dict[str, Any]:
        return agenda.today(project(), lang(params), params.get("today"))

    @server.method("agenda.list")
    def agenda_list(params: dict[str, Any]) -> dict[str, Any]:
        start = agenda._day(params.get("start"), "start", required=True)[:10]
        end = agenda._day(params.get("end"), "end", required=True)[:10]
        return agenda.agenda(project(), start, end, lang(params), params.get("today"))

    @server.method("task.save")
    def task_save(params: dict[str, Any]) -> dict[str, Any]:
        p = project()
        own = params.get("id")
        current = p.record("task", own) if own else None
        spec = agenda.validate_task(params.get("task"), current)
        if current:
            p.update_record("task", own, spec)
            created = own
            if spec["status"] == "done" and current["status"] != "done":
                nxt = agenda.next_occurrence(spec)
                if nxt:
                    p.insert_record("task", nxt)
        else:
            created = p.insert_record("task", spec)
        return {**svc.snapshot(), "created": created}

    @server.method("task.delete")
    def task_delete(params: dict[str, Any]) -> dict[str, Any]:
        project().delete_record("task", params.get("id"))
        return svc.snapshot()

    @server.method("event.save")
    def event_save(params: dict[str, Any]) -> dict[str, Any]:
        p = project()
        spec = agenda.validate_event(params.get("event"))
        if params.get("id"):
            p.update_record("event", params["id"], spec)
            created = params["id"]
        else:
            created = p.insert_record("event", spec)
        return {**svc.snapshot(), "created": created}

    @server.method("event.delete")
    def event_delete(params: dict[str, Any]) -> dict[str, Any]:
        project().delete_record("event", params.get("id"))
        return svc.snapshot()

    @server.method("agenda.export_ics")
    def agenda_export(params: dict[str, Any]) -> dict[str, Any]:
        p = project()
        path = params.get("path")
        if not isinstance(path, str):
            raise rc._err("No file chosen", "invalid_params")
        start = agenda._day(params.get("start") or "1900-01-01", "start")[:10]
        end = agenda._day(params.get("end") or "2999-12-31", "end")[:10]
        events = agenda.agenda(p, start, end, lang(params))["events"]
        text = agenda.to_ics(p.meta().get("name", ""), events, ICS_TITLES[lang(params)])
        Path(path).write_text(text, encoding="utf-8", newline="")
        return {"path": path, "events": len(events)}

    @server.method("agenda.import_ics")
    def agenda_import(params: dict[str, Any]) -> dict[str, Any]:
        p = project()
        path = params.get("path")
        if not isinstance(path, str) or not Path(path).is_file():
            raise rc._err("No file chosen", "invalid_params")
        if Path(path).stat().st_size > 5_000_000:
            raise rc._err("The calendar file is too large", "file_too_large")
        events = agenda.from_ics(Path(path).read_text(encoding="utf-8", errors="replace"))
        for e in events:
            p.insert_record("event", agenda.validate_event(e))
        return {**svc.snapshot(), "imported": len(events)}


# ----- Excel templates ------------------------------------------------------------------------------


def register_canevas(server: Server, svc: Service) -> None:
    import re
    from pathlib import Path

    from . import canevas

    def project() -> Project:
        return svc.project

    def titles() -> dict[str, str]:
        return {n["id"]: f"{n.get('code') or ''} {n['title']}".strip() for n in svc.snapshot()["framework"]}

    @server.method("canevas.write")
    def canevas_write(params: dict[str, Any]) -> dict[str, Any]:
        """One template, or one per reporting unit when a folder is given."""
        p = project()
        view = rc.View(p, svc.ordered_indicators())
        lang = "en" if params.get("lang") == "en" else "fr"
        period = params.get("period")
        view.period(period)
        path = params.get("path")
        if not isinstance(path, str):
            raise rc._err("No file chosen", "invalid_params")
        target = Path(path)
        names = titles()
        if target.is_dir():
            from .agenda import _unit_name

            written = []
            for u in view.units():
                name = _unit_name(view, u, lang)
                safe = re.sub(r"[^\w\-]+", "-", f"{period}-{name}", flags=re.UNICODE).strip("-")[:80]
                file = target / f"{safe}.xlsx"
                canevas.write(view, period, u["place_id"], u["partner_id"], file, lang, names)
                written.append(file.name)
            return {"files": written, "folder": str(target)}
        canevas.write(view, period, params.get("place_id") or "", params.get("partner_id") or "", target, lang, names)
        return {"files": [target.name], "folder": str(target.parent)}

    @server.method("canevas.receive")
    def canevas_receive(params: dict[str, Any]) -> dict[str, Any]:
        path = params.get("path")
        if not isinstance(path, str) or not Path(path).is_file():
            raise rc._err("No file chosen", "invalid_params")
        p = project()
        result = canevas.receive(p, path)
        if result["revision"] and params.get("apply"):
            # A revision accepted: the validated submission is reopened with the reason,
            # then the template's values are applied.
            rc.act(p, result["submission_id"], "reopen", params.get("reason") or "")
            result = {**canevas.receive(p, path), "revised": True}
        svc._results.clear()
        return {**svc.snapshot(), **result}
