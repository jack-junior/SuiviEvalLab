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
    }


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
        return rc.track_all(view, params)

    @server.method("tracking.breakdown")
    def tracking_breakdown(params: dict[str, Any]) -> dict[str, Any]:
        p = project()
        view = rc.View(p)
        ind = p.record("indicator", params.get("indicator_id"))
        return {"values": rc.by_category(view, ind, str(params.get("key")), params)}

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
