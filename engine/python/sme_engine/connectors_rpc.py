# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 GAYI Komi Selassi and SANOUSSI Moudjibou

"""Methods of the server connections (Kobo, ODK Central, DHIS2).

The `secret` of a call is added by the application from its encrypted store; it
is used for that call only and never written to the project.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from . import connectors as cx
from . import datasets, monitoring, reception, xlsform
from .project import Project
from .rpc import Server

if TYPE_CHECKING:
    from .service import Service


def register_connectors(server: Server, svc: Service) -> None:
    def project() -> Project:
        return svc.project

    def conn_of(params: dict[str, Any]) -> dict[str, Any]:
        return project().record("connection", params.get("connection_id"))

    @server.method("connection.save")
    def connection_save(params: dict[str, Any]) -> dict[str, Any]:
        p = project()
        own = params.get("id")
        spec = cx.validate(params.get("connection"))
        if own:
            current = p.record("connection", own)
            spec["dataset_id"] = current.get("dataset_id", "")
            spec["syncs"] = current.get("syncs", [])
            p.update_record("connection", own, spec)
            created = own
        else:
            created = p.insert_record("connection", spec)
        return {**svc.snapshot(), "created": created}

    @server.method("connection.delete")
    def connection_delete(params: dict[str, Any]) -> dict[str, Any]:
        project().delete_record("connection", params.get("id"))
        return svc.snapshot()

    @server.method("connection.forms")
    def connection_forms(params: dict[str, Any]) -> dict[str, Any]:
        """Forms (Kobo), projects then forms (ODK) the account can see."""
        c = conn_of(params)
        secret = params.get("secret")
        if c["kind"] == "kobo":
            return {"forms": cx.kobo_forms(c["url"], secret)}
        if c["kind"] == "odk":
            return {"forms": cx.odk_forms(c["url"], c["username"], secret, params.get("project_id"))}
        raise cx._err("DHIS2 has no forms to choose", "invalid_params")

    @server.method("connection.sync")
    def connection_sync(params: dict[str, Any]) -> dict[str, Any]:
        """Download the submissions into the connection's dataset (created the first time)."""
        p = project()
        c = conn_of(params)
        secret = params.get("secret")
        labels: dict[str, Any] = {"columns": {}, "values": {}}
        if c["kind"] == "kobo":
            uid = c["form"].get("uid")
            if not uid:
                raise cx._err("Choose a form first", "server_form_missing")
            df, content = cx.kobo_fetch(c["url"], secret, uid)
            if content:
                survey, choices = xlsform.from_kobo_content(content)
                labels = xlsform.parse_frames(survey, choices, df.columns)["labels"]
        elif c["kind"] == "odk":
            pid, fid = c["form"].get("project_id"), c["form"].get("form_id")
            if not pid or not fid:
                raise cx._err("Choose a form first", "server_form_missing")
            df, xlsx = cx.odk_fetch(c["url"], c["username"], secret, pid, fid)
            if xlsx:
                import tempfile
                from pathlib import Path

                with tempfile.TemporaryDirectory() as tmp:
                    path = Path(tmp) / "form.xlsx"
                    path.write_bytes(xlsx)
                    try:
                        form = xlsform.find_form(path, datasets.sheet_names(path))
                        if form:
                            labels = xlsform.parse(path, form["survey"], form.get("choices"), df.columns)["labels"]
                    except Exception:  # noqa: BLE001 - labels are a convenience, the data are what matters
                        pass
        else:
            raise cx._err("DHIS2 values are imported into periods, not as a dataset", "invalid_params")
        if df.height == 0:
            raise cx._err("The form has no submissions yet", "server_empty")
        df = datasets.normalise(df)
        stamp = datasets.now()
        dataset_id = c.get("dataset_id")
        existing = None
        if dataset_id:
            try:
                existing = p.record("dataset", dataset_id)
            except Exception:  # noqa: BLE001 - deleted since: a new dataset is made
                existing = None
        if existing:
            existing["rows"] = df.height
            existing["columns"] = datasets.describe_columns(df, existing.get("na_values") or datasets.DEFAULT_NA)
            existing["labels"] = xlsform.merge(existing.get("labels"), labels)
            existing["imported_at"] = stamp
            p.replace_raw(dataset_id, datasets.to_parquet(df))
            p.update_record("dataset", dataset_id, existing)
            # Everything computed from the old data goes.
            svc._raw.pop(dataset_id, None)
            svc._clean.clear()
            svc._merged.clear()
            svc._rows.clear()
        else:
            from pathlib import Path

            spec = datasets.new_spec(
                str(params.get("name") or c["form"].get("name") or c["name"])[:200],
                params.get("round") if params.get("round") in datasets.ROUNDS else "monitoring",
                Path(f"{c['kind']}.json"),
                None,
                df,
                {},
            )
            spec["labels"] = labels
            spec["source_name"] = f"{c['name']} ({c['url']})"
            dataset_id = p.insert_record("dataset", spec, raw=datasets.to_parquet(df))
            svc._raw[dataset_id] = df
        c["dataset_id"] = dataset_id
        c["syncs"] = [*c.get("syncs", []), {"at": stamp, "rows": df.height}][-20:]
        p.update_record("connection", c["id"], {k: v for k, v in c.items() if k != "id"})
        svc._results.clear()
        return {**svc.snapshot(), "dataset_id": dataset_id, "rows": df.height}

    @server.method("dhis2.search")
    def dhis2_search(params: dict[str, Any]) -> dict[str, Any]:
        c = conn_of(params)
        if c["kind"] != "dhis2":
            raise cx._err("Not a DHIS2 server", "invalid_params")
        return {
            "results": cx.dhis2_search(
                c["url"], c["username"], params.get("secret"), str(params.get("what")), str(params.get("query") or "")
            )
        }

    @server.method("dhis2.import")
    def dhis2_import(params: dict[str, Any]) -> dict[str, Any]:
        """Values of the indicators linked to DHIS2, for the periods asked (by default
        the ended periods that are not locked), by place: each place whose code is a
        DHIS2 organisation unit, else the unit given for the whole project."""
        p = project()
        c = conn_of(params)
        if c["kind"] != "dhis2":
            raise cx._err("Not a DHIS2 server", "invalid_params")
        view = reception.View(p)
        linked = [i for i in view.entry if i.get("dhis2_id")]
        if not linked:
            raise cx._err("No indicator is linked to a DHIS2 element", "dhis2_nothing_linked")
        today = reception.today()
        wanted = params.get("periods")
        periods = [
            x
            for x in view.periods
            if (x["code"] in wanted if isinstance(wanted, list) else x["end"] < today) and x["state"] != "locked"
        ]
        places = [x for x in view.places if x.get("code")]
        root = str(params.get("org_unit") or "").strip()
        ous = {x["code"]: x["id"] for x in places} if places else ({root: ""} if root else {})
        if not ous:
            raise cx._err(
                "Give the DHIS2 codes of the places, or the organisation unit of the project", "dhis2_no_org_unit"
            )
        # {(period, place): {indicator: value}}
        got: dict[tuple[str, str], dict[str, float]] = {}
        for ind in linked:
            additive = monitoring.kind(ind) == "count"
            for per in periods:
                pe = cx.dhis2_periods(per, additive)
                rows = cx.dhis2_fetch(c["url"], c["username"], params.get("secret"), [ind["dhis2_id"]], pe, list(ous))
                for _dx, _pe, ou, value in rows:
                    key = (per["code"], ous.get(ou, ""))
                    cell = got.setdefault(key, {})
                    cell[ind["id"]] = cell.get(ind["id"], 0.0) + value if additive else value
        written, skipped = 0, 0
        for (period, place_id), values in got.items():
            sub = reception.find(reception.View(p, []), period, place_id, "")
            if sub and sub["status"] not in monitoring.EDITABLE:
                skipped += 1  # validated: a change goes through reopening
                continue
            sid = sub["id"] if sub else reception.open_submission(p, period, place_id, "", channel="dhis2")
            items = []
            for ind_id, v in values.items():
                ind = next(i for i in linked if i["id"] == ind_id)
                # DHIS2 gives percentages as 0 to 100; they are kept as shares like typed ones.
                items.append({"indicator_id": ind_id, "value": f"{v}%" if ind["unit"] == "percent" else v})
            reception.save_values(p, sid, items, f"DHIS2 {c['url']}")
            current = p.record("submission", sid)
            if current["status"] in ("draft", "returned"):
                reception.act(p, sid, "submit")
            written += 1
        c["syncs"] = [*c.get("syncs", []), {"at": datasets.now(), "rows": written}][-20:]
        p.update_record("connection", c["id"], {k: v for k, v in c.items() if k != "id"})
        svc._results.clear()
        return {**svc.snapshot(), "written": written, "skipped": skipped}
