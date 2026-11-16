# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 GAYI Komi Selassi and SANOUSSI Moudjibou

"""Methods to set a project up: profile, calendar, places, partners,
disaggregations and targets by period."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any

from . import places as pl_
from . import schedule, targets
from .project import Project, _err
from .rpc import Server

if TYPE_CHECKING:
    from .service import Service


def state(p: Project) -> dict[str, Any]:
    """The part of the snapshot this module owns."""
    by_indicator: dict[str, list[dict[str, Any]]] = {}
    for t in p.records("target"):
        by_indicator.setdefault(t["indicator_id"], []).append(t)
    return {
        "profile": schedule.profile_from_meta(p.meta()),
        "periods": p.records("period"),
        "places": p.records("place"),
        "partners": p.records("partner"),
        "disaggregations": p.records("disaggregation"),
        "targets": by_indicator,
    }


def _used_periods(p: Project) -> set[str]:
    return {t["period"] for t in p.records("target")}


def apply_profile(p: Project, spec: Any) -> dict[str, Any]:
    profile = schedule.validate_profile(spec)
    p.set_meta("profile", json.dumps(profile, ensure_ascii=False))
    return profile


def generate_periods(p: Project) -> None:
    """Rebuild the calendar from the profile, keeping the state of periods that stay.

    Refused when a period that would disappear has targets or is locked.
    """
    profile = schedule.profile_from_meta(p.meta())
    new = schedule.generate(profile)
    old = p.records("period")
    new_codes = {x["code"] for x in new}
    used = _used_periods(p)
    lost = [x for x in old if x["code"] not in new_codes and (x["code"] in used or x["state"] == "locked")]
    if lost:
        raise _err(
            f"{len(lost)} periods hold targets or are locked and would disappear",
            "periods_in_use",
        )
    states = {x["code"]: x["state"] for x in old}
    for x in old:
        p.delete_record("period", x["id"])
    for x in new:
        p.insert_record("period", {**x, "state": states.get(x["code"], "open")})


def save_period(p: Project, params: dict[str, Any]) -> str:
    spec = schedule.validate_period(params.get("period"))
    others = [x for x in p.records("period") if x["id"] != params.get("id")]
    if params.get("id"):
        current = p.record("period", params["id"])
        if current["code"] != spec["code"] and current["code"] in _used_periods(p):
            raise _err("This period holds targets: its code cannot change", "period_in_use")
    schedule.check_overlaps([*others, spec])
    if params.get("id"):
        p.update_record("period", params["id"], spec)
        record_id = params["id"]
    else:
        record_id = p.insert_record("period", spec)
    # Keep the calendar in date order whatever order periods were typed in.
    ordered = sorted(p.records("period"), key=lambda x: x["start"])
    with p.conn:
        p.conn.executemany(
            "UPDATE period SET position = ? WHERE id = ?", [(i, x["id"]) for i, x in enumerate(ordered, start=1)]
        )
    return record_id


def register_setup(server: Server, svc: Service) -> None:
    def project() -> Project:
        return svc.project

    # Profile and calendar
    @server.method("profile.set")
    def profile_set(params: dict[str, Any]) -> dict[str, Any]:
        apply_profile(project(), params.get("profile"))
        if params.get("generate_periods") is True:
            generate_periods(project())
        return svc.snapshot()

    @server.method("period.generate")
    def period_generate(_: dict[str, Any]) -> dict[str, Any]:
        generate_periods(project())
        return svc.snapshot()

    @server.method("period.save")
    def period_save(params: dict[str, Any]) -> dict[str, Any]:
        created = save_period(project(), params)
        return {**svc.snapshot(), "created": created}

    @server.method("period.delete")
    def period_delete(params: dict[str, Any]) -> dict[str, Any]:
        p = project()
        period = p.record("period", params.get("id"))
        if period["code"] in _used_periods(p):
            raise _err("This period holds targets", "period_in_use")
        if period["state"] == "locked":
            raise _err("This period is locked", "period_locked")
        p.delete_record("period", period["id"])
        return svc.snapshot()

    @server.method("period.set_state")
    def period_set_state(params: dict[str, Any]) -> dict[str, Any]:
        p = project()
        period = p.record("period", params.get("id"))
        new_state = params.get("state")
        if new_state not in schedule.STATES:
            raise _err("Unknown period state", "invalid_params")
        p.update_record("period", period["id"], {**period, "state": new_state})
        return svc.snapshot()

    # Places
    def levels() -> list[str]:
        return schedule.profile_from_meta(project().meta())["place_levels"]

    @server.method("place.save")
    def place_save(params: dict[str, Any]) -> dict[str, Any]:
        p = project()
        all_places = p.records("place")
        own = params.get("id")
        if own:
            current = p.record("place", own)
            spec = pl_.validate_place(params.get("place"), all_places, levels(), own)
            if spec["level"] != current["level"] and pl_.descendants(all_places, own):
                raise _err("A place with places inside cannot change level", "place_has_children")
            p.update_record("place", own, spec)
            created = own
        else:
            spec = pl_.validate_place(params.get("place"), all_places, levels())
            created = p.insert_record("place", spec)
        return {**svc.snapshot(), "created": created}

    @server.method("place.import")
    def place_import(params: dict[str, Any]) -> dict[str, Any]:
        p = project()
        todo = pl_.import_places(params.get("rows"), p.records("place"), levels())
        ids: dict[str, str] = {}
        for item in todo:
            parent = ids.get(item["parent_ref"], item["parent_ref"])
            ids[item["ref"]] = p.insert_record(
                "place", {"name": item["name"], "code": "", "level": item["level"], "parent_id": parent}
            )
        return {**svc.snapshot(), "added": len(todo)}

    @server.method("place.delete")
    def place_delete(params: dict[str, Any]) -> dict[str, Any]:
        p = project()
        place = p.record("place", params.get("id"))
        all_places = p.records("place")
        if pl_.descendants(all_places, place["id"]):
            raise _err("Remove the places inside it first", "place_has_children")
        for partner in p.records("partner"):
            if place["id"] in partner["place_ids"]:
                partner["place_ids"] = [x for x in partner["place_ids"] if x != place["id"]]
                p.update_record("partner", partner["id"], partner)
        p.delete_record("place", place["id"])
        return svc.snapshot()

    @server.method("place.move")
    def place_move(params: dict[str, Any]) -> dict[str, Any]:
        project().move_record("place", params.get("id"), params.get("direction"))
        return svc.snapshot()

    # Partners
    @server.method("partner.save")
    def partner_save(params: dict[str, Any]) -> dict[str, Any]:
        p = project()
        ids = {x["id"] for x in p.records("place")}
        spec = pl_.validate_partner(params.get("partner"), ids)
        if params.get("id"):
            p.update_record("partner", params["id"], spec)
            created = params["id"]
        else:
            created = p.insert_record("partner", spec)
        return {**svc.snapshot(), "created": created}

    @server.method("partner.delete")
    def partner_delete(params: dict[str, Any]) -> dict[str, Any]:
        project().delete_record("partner", params.get("id"))
        return svc.snapshot()

    @server.method("partner.move")
    def partner_move(params: dict[str, Any]) -> dict[str, Any]:
        project().move_record("partner", params.get("id"), params.get("direction"))
        return svc.snapshot()

    # Disaggregations
    @server.method("disaggregation.presets")
    def dis_presets(_: dict[str, Any]) -> dict[str, Any]:
        return {"presets": [{"key": k, **v} for k, v in pl_.PRESETS.items()], "unspecified": pl_.UNSPECIFIED}

    @server.method("disaggregation.save")
    def dis_save(params: dict[str, Any]) -> dict[str, Any]:
        p = project()
        own = params.get("id")
        spec = pl_.validate_disaggregation(params.get("disaggregation"), p.records("disaggregation"), own)
        if own:
            p.update_record("disaggregation", own, spec)
            created = own
        else:
            created = p.insert_record("disaggregation", spec)
        return {**svc.snapshot(), "created": created}

    @server.method("disaggregation.delete")
    def dis_delete(params: dict[str, Any]) -> dict[str, Any]:
        project().delete_record("disaggregation", params.get("id"))
        return svc.snapshot()

    @server.method("disaggregation.move")
    def dis_move(params: dict[str, Any]) -> dict[str, Any]:
        project().move_record("disaggregation", params.get("id"), params.get("direction"))
        return svc.snapshot()

    # Targets by period
    @server.method("target.set")
    def target_set(params: dict[str, Any]) -> dict[str, Any]:
        p = project()
        indicator = p.record("indicator", params.get("indicator_id"))
        period = params.get("period")
        if not isinstance(period, str):
            raise _err("period must be a string", "invalid_params")
        codes = {x["code"] for x in p.records("period")}
        locked = {x["code"] for x in p.records("period") if x["state"] == "locked"}
        current = next((t for t in p.records("target", indicator["id"]) if t["period"] == period), None)
        if period in locked and current is not None:
            raise _err("This period is locked", "period_locked")
        value = params.get("value")
        if period == targets.TOTAL and current is None and indicator.get("target") is not None:
            # End of project target set before 1.0, from the indicator form: the first
            # change from it is a revision too.
            current = {"id": None, "period": targets.TOTAL, "value": indicator["target"], "history": []}
        new = targets.set_value(current, period, value, params.get("reason"), codes)
        if new is not None:
            if indicator.get("unit") == "percent" and not 0 <= new["value"] <= 1:
                raise _err("A percentage target is between 0 and 100", "invalid_share")
            if current is None or current["id"] is None:
                p.insert_record("target", new, scope=indicator["id"])
            else:
                p.update_record("target", current["id"], new)
            if period == targets.TOTAL:
                # The end of project target also lives on the indicator, where the
                # analyses and the report read it.
                p.update_record("indicator", indicator["id"], {**indicator, "target": new["value"]})
                svc._results.clear()
        return svc.snapshot()

    @server.method("target.clear")
    def target_clear(params: dict[str, Any]) -> dict[str, Any]:
        p = project()
        indicator = p.record("indicator", params.get("indicator_id"))
        current = next((t for t in p.records("target", indicator["id"]) if t["period"] == params.get("period")), None)
        if current is not None:
            p.delete_record("target", current["id"])
        if params.get("period") == targets.TOTAL and indicator.get("target") is not None:
            p.update_record("indicator", indicator["id"], {**indicator, "target": None})
            svc._results.clear()
        return svc.snapshot()
