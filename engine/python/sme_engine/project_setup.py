# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 GAYI Komi Selassi and SANOUSSI Moudjibou

"""Methods to set a project up: profile, calendar, places, partners,
disaggregations and targets by period."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any

from . import geo as geo_
from . import library, schedule, targets
from . import places as pl_
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
    kept = {x["code"]: {k: x[k] for k in ("state", "history", "reported_at") if k in x} for x in old}
    for x in old:
        p.delete_record("period", x["id"])
    for x in new:
        p.insert_record("period", {**x, **kept.get(x["code"], {})})


def save_period(p: Project, params: dict[str, Any]) -> str:
    spec = schedule.validate_period(params.get("period"))
    others = [x for x in p.records("period") if x["id"] != params.get("id")]
    if params.get("id"):
        current = p.record("period", params["id"])
        if current["code"] != spec["code"] and current["code"] in _used_periods(p):
            raise _err("This period holds targets: its code cannot change", "period_in_use")
    schedule.check_overlaps([*others, spec])
    if params.get("id"):
        current = p.record("period", params["id"])
        if current["state"] == "locked":
            raise _err("This period is locked", "period_locked")
        # The state, the history and the report date change only through their own actions.
        keep = {k: current[k] for k in ("state", "history", "reported_at") if k in current}
        p.update_record("period", params["id"], {**spec, **keep})
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
        """Lock a period once its submissions are validated, or reopen it with a reason."""
        from . import reception

        p = project()
        period = p.record("period", params.get("id"))
        new_state = params.get("state")
        if new_state not in schedule.STATES:
            raise _err("Unknown period state", "invalid_params")
        if new_state != period["state"]:
            reception.lock_period(p, period, new_state == "locked", str(params.get("reason") or ""))
        return svc.snapshot()

    @server.method("period.mark_reported")
    def period_mark_reported(params: dict[str, Any]) -> dict[str, Any]:
        """The report of the period has been sent (or not, with done false)."""
        from .reception import now

        p = project()
        period = p.record("period", params.get("id"))
        period["reported_at"] = now() if params.get("done", True) else None
        p.update_record("period", period["id"], period)
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

    # ----- places from maps (geo.py) -----

    @server.method("geo.countries")
    def geo_countries(params: dict[str, Any]) -> dict[str, Any]:
        return {"countries": geo_.countries(), "country": project().meta().get("geo_country", "")}

    @server.method("geo.levels")
    def geo_levels(params: dict[str, Any]) -> dict[str, Any]:
        return {"levels": geo_.levels_available(params.get("iso"))}

    @server.method("geo.preview")
    def geo_preview(params: dict[str, Any]) -> dict[str, Any]:
        items = geo_.tree(params.get("iso"), int(params.get("depth") or 1))
        counts = [sum(1 for i in items if i["level"] == k) for k in range(int(params.get("depth") or 1))]
        return {"counts": counts}

    @server.method("geo.import")
    def geo_import(params: dict[str, Any]) -> dict[str, Any]:
        """The divisions of a country, levels 1 to depth, merged with the places already
        there (same name under the same place)."""
        p = project()
        iso = str(params.get("iso") or "").upper()
        depth = int(params.get("depth") or 1)
        if depth > len(levels()):
            raise _err("More levels than the project has", "geo_too_deep")
        items = geo_.tree(iso, depth)
        places = p.records("place")
        by_key = {(x.get("parent_id", ""), x["name"].casefold()): x for x in places}
        by_gid = {x["geo_id"]: x for x in places if x.get("geo_id")}
        ids: dict[str, str] = {}
        added = 0
        for item in items:
            parent = ids.get(item["parent_gid"], "") if item["parent_gid"] else ""
            if item["parent_gid"] and not parent:
                continue
            found = by_gid.get(item["gid"]) or by_key.get((parent, item["name"].casefold()))
            if found:
                if not found.get("geo_id"):
                    keep = {k: v for k, v in found.items() if k != "id"}
                    p.update_record("place", found["id"], {**keep, "geo_id": item["gid"]})
                ids[item["gid"]] = found["id"]
                continue
            spec = {
                "name": item["name"],
                "code": "",
                "level": item["level"],
                "parent_id": parent,
                "geo_id": item["gid"],
            }
            ids[item["gid"]] = p.insert_record("place", spec)
            added += 1
        p.set_meta("geo_country", iso)
        return {**svc.snapshot(), "added": added}

    @server.method("geo.search")
    def geo_search(params: dict[str, Any]) -> dict[str, Any]:
        iso = project().meta().get("geo_country", "")
        iso2 = next((c["iso2"] for c in geo_.countries() if c["iso3"] == iso), "")
        return {"results": geo_.search(params.get("q"), iso2, str(params.get("lang") or "fr"))}

    @server.method("geo.locate")
    def geo_locate(params: dict[str, Any]) -> dict[str, Any]:
        """The deepest place of the project that contains a point (from the imported divisions)."""
        p = project()
        iso = p.meta().get("geo_country", "")
        try:
            lat, lon = float(params.get("lat")), float(params.get("lon"))
        except (TypeError, ValueError):
            raise _err("Latitude and longitude must be numbers", "place_position_invalid") from None
        if not iso:
            return {"place_id": ""}
        gids = geo_.locate(iso, len(levels()), lat, lon)
        by_gid = {x["geo_id"]: x["id"] for x in p.records("place") if x.get("geo_id")}
        hit = next((by_gid[g] for g in reversed(gids) if g in by_gid), "")
        return {"place_id": hit}

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

    # Workspace: summaries of the projects known to this computer. The paths come
    # from the application's own list, never from the interface.
    @server.method("workspace.summaries")
    def ws_summaries(params: dict[str, Any]) -> dict[str, Any]:
        from . import workspace

        lang = "en" if params.get("lang") == "en" else "fr"
        return {"projects": workspace.summaries(params.get("paths"), params.get("today"), lang)}

    @server.method("workspace.agenda")
    def ws_agenda(params: dict[str, Any]) -> dict[str, Any]:
        from . import agenda, workspace

        start = agenda._day(params.get("start"), "start", required=True)[:10]
        end = agenda._day(params.get("end"), "end", required=True)[:10]
        lang = "en" if params.get("lang") == "en" else "fr"
        return workspace.agenda_all(params.get("paths"), start, end, lang, params.get("today"))

    # Portfolio (M13, M14): the paths come from the application's own list.
    @server.method("portfolio.dashboard")
    def pf_dashboard(params: dict[str, Any]) -> dict[str, Any]:
        from . import portfolio

        return portfolio.dashboard(params.get("paths"), params.get("today"), params.get("archived"))

    @server.method("portfolio.export")
    def pf_export(params: dict[str, Any]) -> dict[str, Any]:
        from pathlib import Path

        from . import portfolio

        lang = "en" if params.get("lang") == "en" else "fr"
        target = params.get("target")
        if not isinstance(target, str) or not target:
            raise portfolio._err("No file chosen", "invalid_params")
        data = portfolio.dashboard(params.get("paths"), params.get("today"), params.get("archived"))
        if params.get("kind") == "note":
            return portfolio.note_docx(data, Path(target), lang)
        return portfolio.html(data, Path(target), lang)

    @server.method("portfolio.settings")
    def pf_settings(params: dict[str, Any]) -> dict[str, Any]:
        from . import portfolio

        if "settings" in params:
            return {"settings": portfolio.save_settings(params["settings"])}
        return {"settings": portfolio.settings(), "defaults": portfolio.DEFAULT_SETTINGS}

    @server.method("portfolio.import_pack")
    def pf_import(params: dict[str, Any]) -> dict[str, Any]:
        from pathlib import Path

        from . import portfolio

        path = params.get("path")
        if not isinstance(path, str) or not Path(path).is_file():
            raise portfolio._err("No file chosen", "invalid_params")
        return portfolio.import_pack(Path(path))

    @server.method("portfolio.remove_pack")
    def pf_remove(params: dict[str, Any]) -> dict[str, Any]:
        from . import portfolio

        portfolio.remove_pack(params.get("uid"))
        return {"removed": True}

    @server.method("project.duplicate_model")
    def pf_duplicate(params: dict[str, Any]) -> dict[str, Any]:
        from pathlib import Path

        from . import portfolio

        source, target = params.get("source"), params.get("target")
        if not isinstance(source, str) or not isinstance(target, str) or not Path(source).is_file():
            raise portfolio._err("No file chosen", "invalid_params")
        name = str(params.get("name") or Path(target).stem)[:200]
        portfolio.duplicate_as_model(Path(source), Path(target), name)
        return {"path": target, "name": name}

    @server.method("personal.get")
    def personal_get(_: dict[str, Any]) -> dict[str, Any]:
        from . import workspace

        return workspace.personal_load()

    @server.method("personal.task_save")
    def personal_task(params: dict[str, Any]) -> dict[str, Any]:
        import uuid

        from . import agenda, workspace

        data = workspace.personal_load()
        own = params.get("id")
        current = next((t for t in data["tasks"] if t.get("id") == own), None) if own else None
        if params.get("delete"):
            data["tasks"] = [t for t in data["tasks"] if t.get("id") != own]
        else:
            spec = {**agenda.validate_task(params.get("task"), current), "id": own or uuid.uuid4().hex}
            data["tasks"] = (
                [spec if t.get("id") == own else t for t in data["tasks"]]
                if current
                else [
                    *data["tasks"],
                    spec,
                ]
            )
            if current and spec["status"] == "done" and current.get("status") != "done":
                nxt = agenda.next_occurrence(spec)
                if nxt:
                    data["tasks"].append({**nxt, "id": uuid.uuid4().hex})
        workspace.personal_save(data)
        return data

    @server.method("personal.event_save")
    def personal_event(params: dict[str, Any]) -> dict[str, Any]:
        import uuid

        from . import agenda, workspace

        data = workspace.personal_load()
        own = params.get("id")
        if params.get("delete"):
            data["events"] = [e for e in data["events"] if e.get("id") != own]
        else:
            spec = {**agenda.validate_event(params.get("event")), "id": own or uuid.uuid4().hex}
            if own and any(e.get("id") == own for e in data["events"]):
                data["events"] = [spec if e.get("id") == own else e for e in data["events"]]
            else:
                data["events"].append(spec)
        workspace.personal_save(data)
        return data

    # Indicator library
    @server.method("library.sectors")
    def lib_sectors(_: dict[str, Any]) -> dict[str, Any]:
        lib = library.load()
        return {"sectors": lib["sectors"], "total": len(lib["sheets"])}

    @server.method("library.search")
    def lib_search(params: dict[str, Any]) -> dict[str, Any]:
        return {"results": library.search(params.get("query"), params.get("sector"))}

    @server.method("library.adopt")
    def lib_adopt(params: dict[str, Any]) -> dict[str, Any]:
        """Add an indicator to a result from a library sheet.

        The disaggregations the sheet suggests are added to the project when they
        are among the presets and still missing.
        """
        p = project()
        lang = params.get("lang") if params.get("lang") in ("fr", "en") else "fr"
        spec = library.to_indicator(library.sheet(params.get("id")), lang)
        have = {d["key"] for d in p.records("disaggregation")}
        for key in spec["breakdowns"]:
            if key not in have and key in pl_.PRESETS:
                p.insert_record(
                    "disaggregation", pl_.validate_disaggregation({"preset": key}, p.records("disaggregation"))
                )
                have.add(key)
        spec["breakdowns"] = [k for k in spec["breakdowns"] if k in have]
        return svc.save_indicator({"node_id": params.get("node_id"), "indicator": spec})

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
