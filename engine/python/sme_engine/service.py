"""Engine methods for projects, framework, indicators, data, cleaning, analysis and report.

The interface sees a project as one "snapshot" (project info, framework,
indicators, datasets with their cleaning journal). Methods that change something
return the new snapshot, so the interface never has to merge state itself.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

import polars as pl

from . import cleaning, datasets, indicators
from .project import Project, Workspace, _err, _text
from .r_bridge import RBridge
from .rpc import INVALID_PARAMS, RpcError, Server

ROUND_ORDER = {r: i for i, r in enumerate(datasets.ROUNDS)}


class Service:
    def __init__(self, workspace: Workspace, bridge: RBridge):
        self.ws = workspace
        self.bridge = bridge
        self._raw: dict[str, pl.DataFrame] = {}
        self._clean: dict[str, tuple[str, pl.DataFrame, list[dict[str, Any]]]] = {}
        self._results: dict[str, Any] = {}

    # ----- state ------------------------------------------------------------------

    @property
    def project(self) -> Project:
        return self.ws.require()

    def reset_caches(self) -> None:
        self._raw.clear()
        self._clean.clear()
        self._results.clear()

    def snapshot(self) -> dict[str, Any]:
        p = self.project
        ds_list = []
        for ds in p.records("dataset"):
            rules = p.records("cleaning_rule", ds["id"])
            _, cleaned, effects = self.cleaned(ds["id"])
            by_id = {e["id"]: e for e in effects}
            for r in rules:
                r["effect"] = by_id.get(r["id"])
            ds_list.append({**ds, "rules": rules, "clean_rows": cleaned.height})
        return {
            "project": p.info(),
            "framework": p.framework(),
            "indicators": self.ordered_indicators(),
            "datasets": ds_list,
        }

    def ordered_indicators(self) -> list[dict[str, Any]]:
        """Indicators in framework order (node order, then position under the node)."""
        order = {n["id"]: i for i, n in enumerate(self.project.framework())}
        return sorted(self.project.records("indicator"), key=lambda r: order.get(r["node_id"], 1 << 30))

    # ----- data -------------------------------------------------------------------

    def dataset_spec(self, dataset_id: Any) -> dict[str, Any]:
        return self.project.record("dataset", dataset_id)

    def raw(self, dataset_id: str) -> pl.DataFrame:
        if dataset_id not in self._raw:
            self._raw[dataset_id] = datasets.from_parquet(self.project.blob("dataset", "raw", dataset_id))
        return self._raw[dataset_id]

    def cleaned(self, dataset_id: str) -> tuple[str, pl.DataFrame, list[dict[str, Any]]]:
        """Raw data with missing codes as nulls, then the enabled rules in order. Cached."""
        spec = self.dataset_spec(dataset_id)
        rules = self.project.records("cleaning_rule", dataset_id)
        signature = hashlib.sha256(
            json.dumps([spec["na_values"], rules], sort_keys=True, ensure_ascii=False).encode()
        ).hexdigest()
        cached = self._clean.get(dataset_id)
        if cached and cached[0] == signature:
            return cached
        df = cleaning.missing_to_null(self.raw(dataset_id), spec["na_values"])
        df, effects = cleaning.apply(df, rules)
        self._clean[dataset_id] = (signature, df, effects)
        return self._clean[dataset_id]

    def import_dataset(self, params: dict[str, Any]) -> dict[str, Any]:
        path = Path(_text(params, "path", max_len=4000))
        name = _text(params, "name", max_len=200)
        round_ = params.get("round", "baseline")
        sheet = params.get("sheet")
        df = datasets.load(path, sheet if isinstance(sheet, str) else None)
        spec = datasets.new_spec(name, round_, path, sheet if isinstance(sheet, str) else None, df, params)
        new_id = self.project.insert_record("dataset", spec, raw=datasets.to_parquet(df))
        self._raw[new_id] = df
        return {**self.snapshot(), "created": new_id}

    def update_dataset(self, params: dict[str, Any]) -> dict[str, Any]:
        spec = self.dataset_spec(params.get("id"))
        names = [c["name"] for c in spec["columns"]]
        if "name" in params:
            spec["name"] = _text(params, "name", max_len=200)
        if "round" in params:
            if params["round"] not in datasets.ROUNDS:
                raise _err("Unknown round", "invalid_round")
            spec["round"] = params["round"]
        if "design" in params:
            spec["design"] = datasets.validate_design(params["design"], names)
        if "attribution" in params:
            spec["attribution"] = _text(params, "attribution", required=False, max_len=500)
        if "id_column" in params:
            col = params["id_column"] or None
            if col is not None and col not in names:
                raise _err(f"Unknown column: {col}", "column_not_found")
            spec["id_column"] = col
        self.project.update_record("dataset", spec["id"], spec)
        self._results.clear()
        return self.snapshot()

    def export_dataset(self, params: dict[str, Any]) -> dict[str, Any]:
        """Write the cleaned data as CSV (UTF-8 with BOM, so Excel reads accents), for R or Excel."""
        _, df, _ = self.cleaned(params.get("id"))
        path = Path(_text(params, "path", max_len=4000))
        if path.suffix.lower() != ".csv":
            path = path.with_suffix(".csv")
        df.write_csv(path, include_bom=True, null_value="")
        return {"path": str(path), "rows": df.height}

    def delete_dataset(self, dataset_id: Any) -> dict[str, Any]:
        self.project.delete_record("dataset", dataset_id)
        self._raw.pop(dataset_id, None)
        self._clean.pop(dataset_id, None)
        self._results.clear()
        return self.snapshot()

    def preview(self, params: dict[str, Any]) -> dict[str, Any]:
        dataset_id = params.get("id")
        spec = self.dataset_spec(dataset_id)
        df = self.cleaned(dataset_id)[1] if params.get("cleaned", True) else self.raw(dataset_id)
        offset = max(0, int(params.get("offset") or 0))
        limit = min(200, max(1, int(params.get("limit") or 50)))
        columns = params.get("columns")
        if isinstance(columns, list) and columns:
            df = df.select([c for c in columns if c in df.columns])
        page = df.slice(offset, limit)
        return {"id": spec["id"], "total": df.height, "offset": offset, "columns": page.columns, "rows": page.rows()}

    def column_values(self, params: dict[str, Any]) -> dict[str, Any]:
        dataset_id = params.get("id")
        column = params.get("column")
        df = self.cleaned(dataset_id)[1] if params.get("cleaned", True) else self.raw(dataset_id)
        if column not in df.columns:
            raise _err(f"Unknown column: {column}", "column_not_found")
        counts = df[column].value_counts(sort=True, name="n").head(int(params.get("limit") or 60))
        values = [{"value": v, "n": int(n)} for v, n in counts.rows()]
        num = df[column].cast(pl.Float64, strict=False)
        stats = None
        present = df[column].drop_nulls()
        if present.len() and num.drop_nulls().len() == present.len():
            stats = {"min": num.min(), "max": num.max(), "mean": num.mean(), "median": num.median()}
        return {
            "column": column,
            "total": df.height,
            "missing": df[column].null_count(),
            "values": values,
            "stats": stats,
        }

    # ----- cleaning ---------------------------------------------------------------

    def add_rule(self, params: dict[str, Any]) -> dict[str, Any]:
        dataset_id = params.get("dataset_id")
        spec = self.dataset_spec(dataset_id)
        rule = cleaning.validate(params.get("rule") or {}, [c["name"] for c in spec["columns"]])
        self.project.insert_record("cleaning_rule", rule, scope=dataset_id)
        self._results.clear()
        return self.snapshot()

    def update_rule(self, params: dict[str, Any]) -> dict[str, Any]:
        current = self.project.record("cleaning_rule", params.get("id"))
        spec = self.dataset_spec(current["dataset_id"])
        merged = {**current, **(params.get("rule") or {})}
        rule = cleaning.validate(merged, [c["name"] for c in spec["columns"]])
        self.project.update_record("cleaning_rule", current["id"], rule)
        self._results.clear()
        return self.snapshot()

    # ----- indicators -------------------------------------------------------------

    def save_indicator(self, params: dict[str, Any]) -> dict[str, Any]:
        spec = indicators.validate(params.get("indicator") or {})
        if params.get("id"):
            current = self.project.record("indicator", params["id"])
            self.project.update_record("indicator", current["id"], spec)
            created = current["id"]
        else:
            node_id = params.get("node_id")
            node = self.project._node(node_id)
            if node["level"] == "activity":
                raise _err("Indicators belong to results, not activities", "indicator_on_activity")
            created = self.project.insert_record("indicator", spec, scope=node_id)
        self._results.clear()
        return {**self.snapshot(), "saved": created}

    # ----- analysis ---------------------------------------------------------------

    def _ordered_datasets(self) -> list[dict[str, Any]]:
        ds = self.project.records("dataset")
        return sorted(ds, key=lambda d: (ROUND_ORDER.get(d["round"], 9), d.get("imported_at", "")))

    def _r_args(self, ind: dict[str, Any], ds: dict[str, Any]) -> dict[str, Any]:
        design = ds["design"]
        return {
            "type": "proportion" if ind["unit"] == "percent" else "mean",
            "var": ind["column"],
            "success": ind["success_values"],
            "weights": design.get("weights"),
            "strata": design.get("strata") or None,
            "cluster": design.get("cluster"),
            "level": 0.95,
        }

    def _table_for(self, ind: dict[str, Any], ds: dict[str, Any]) -> pl.DataFrame | None:
        _, df, _ = self.cleaned(ds["id"])
        design = ds["design"]
        needed = [
            ind["column"],
            ind.get("disaggregation"),
            design.get("weights"),
            design.get("cluster"),
            *(design.get("strata") or []),
        ]
        needed = [c for c in dict.fromkeys(needed) if c]
        if any(c not in df.columns for c in needed):
            return None
        return df.select(needed)

    def _cache_key(self, *parts: Any) -> str:
        return hashlib.sha256(json.dumps(parts, sort_keys=True, default=str).encode()).hexdigest()

    def estimate(self, ind: dict[str, Any], ds: dict[str, Any], by: bool = True) -> dict[str, Any] | None:
        if not ind.get("column"):
            return None
        table = self._table_for(ind, ds)
        if table is None:
            return {"error_key": "column_missing", "dataset_id": ds["id"]}
        sig = self.cleaned(ds["id"])[0]
        args = self._r_args(ind, ds)
        if by and ind.get("disaggregation"):
            args["by"] = ind["disaggregation"]
        key = self._cache_key("estimate", sig, args, ds["design"])
        if key not in self._results:
            path = self.bridge.write_table(table, f"t_{key[:16]}")
            try:
                self._results[key] = self.bridge.call("estimate", {"path": path, **args})
            except RpcError as exc:
                return {"error_key": "r_error", "detail": str(exc), "dataset_id": ds["id"]}
        return {**self._results[key], "dataset_id": ds["id"]}

    def compare(self, ind: dict[str, Any], a: dict[str, Any], b: dict[str, Any]) -> dict[str, Any] | None:
        ta, tb = self._table_for(ind, a), self._table_for(ind, b)
        if ta is None or tb is None:
            return None
        args = self._r_args(ind, a)
        if a["design"] != b["design"]:
            # Both rounds must be analysed with the same kind of design; keep the common part.
            common = {
                "weights": a["design"].get("weights")
                if a["design"].get("weights") == b["design"].get("weights")
                else None,
                "cluster": a["design"].get("cluster")
                if a["design"].get("cluster") == b["design"].get("cluster")
                else None,
                "strata": a["design"].get("strata") if a["design"].get("strata") == b["design"].get("strata") else None,
            }
            args.update({k: v or None for k, v in common.items()})
        key = self._cache_key("compare", self.cleaned(a["id"])[0], self.cleaned(b["id"])[0], args)
        if key not in self._results:
            pa = self.bridge.write_table(ta, f"a_{key[:16]}")
            pb = self.bridge.write_table(tb, f"b_{key[:16]}")
            try:
                self._results[key] = self.bridge.call("compare", {"path_a": pa, "path_b": pb, **args})
            except RpcError as exc:
                return {"error_key": "r_error", "detail": str(exc)}
        return {**self._results[key], "a_id": a["id"], "b_id": b["id"]}

    def indicator_analysis(self, indicator_id: Any) -> dict[str, Any]:
        ind = self.project.record("indicator", indicator_id)
        rounds = []
        for ds in self._ordered_datasets():
            est = self.estimate(ind, ds)
            if est is not None:
                rounds.append({"dataset_id": ds["id"], "round": ds["round"], "name": ds["name"], "result": est})
        usable = [r for r in rounds if "error_key" not in r["result"]]
        comparison = None
        base = next((r for r in usable if r["round"] == "baseline"), None)
        later = [r for r in usable if r["round"] != "baseline"]
        if base and later:
            a = self.dataset_spec(base["dataset_id"])
            b = self.dataset_spec(later[-1]["dataset_id"])
            comparison = self.compare(ind, a, b)
        return {"indicator": ind, "rounds": rounds, "comparison": comparison, **self._summary(ind, usable)}

    def _summary(self, ind: dict[str, Any], usable: list[dict[str, Any]]) -> dict[str, Any]:
        base = next((r for r in usable if r["round"] == "baseline"), None)
        later = [r for r in usable if r["round"] != "baseline"]
        baseline = base["result"]["estimate"] if base else ind.get("baseline_manual")
        current = later[-1]["result"]["estimate"] if later else None
        rate = indicators.achievement(baseline, current, ind.get("target"))
        return {
            "baseline": baseline,
            "baseline_source": "data" if base else ("manual" if baseline is not None else None),
            "current": current,
            "current_round": later[-1]["round"] if later else None,
            "target": ind.get("target"),
            "achievement": rate,
            "status": indicators.status(rate, current, ind.get("target"), ind.get("direction", "increase")),
        }

    def overview(self) -> dict[str, Any]:
        rows = []
        ordered = self._ordered_datasets()
        for ind in self.ordered_indicators():
            usable = []
            for ds in ordered:
                est = self.estimate(ind, ds, by=False)
                if est is not None and "error_key" not in est:
                    usable.append({"dataset_id": ds["id"], "round": ds["round"], "result": est})
            rows.append({"indicator_id": ind["id"], "node_id": ind["node_id"], **self._summary(ind, usable)})
        return {"rows": rows}


def register(server: Server, workspace: Workspace, bridge: RBridge) -> Service:
    svc = Service(workspace, bridge)

    def opened(project: Project) -> dict[str, Any]:
        workspace.set(project)
        svc.reset_caches()
        return svc.snapshot()

    @server.method("project.create")
    def create(params: dict[str, Any]) -> dict[str, Any]:
        path = _text(params, "path", max_len=4000)
        name = _text(params, "name", max_len=200)
        opened(Project.create(path, name))
        if params.get("example") is True:
            from .example import fill_example

            fill_example(svc, params.get("lang", "fr") if params.get("lang") in ("fr", "en") else "fr")
        return svc.snapshot()

    @server.method("project.open")
    def open_(params: dict[str, Any]) -> dict[str, Any]:
        return opened(Project.open(_text(params, "path", max_len=4000)))

    @server.method("project.close")
    def close(_: dict[str, Any]) -> dict[str, Any]:
        workspace.close()
        svc.reset_caches()
        return {"ok": True}

    @server.method("project.get")
    def get(_: dict[str, Any]) -> dict[str, Any]:
        return svc.snapshot()

    @server.method("project.rename")
    def rename(params: dict[str, Any]) -> dict[str, Any]:
        svc.project.rename(_text(params, "name", max_len=200))
        return svc.snapshot()

    # Framework
    @server.method("framework.add")
    def fw_add(params: dict[str, Any]) -> dict[str, Any]:
        parent_id = params.get("parent_id")
        if parent_id is not None and not isinstance(parent_id, str):
            raise _err("parent_id must be a string or null", "invalid_params")
        created = svc.project.add_node(parent_id, _text(params, "title"), _text(params, "description", required=False))
        return {**svc.snapshot(), "created": created["id"]}

    @server.method("framework.update")
    def fw_update(params: dict[str, Any]) -> dict[str, Any]:
        svc.project.update_node(params.get("id"), _text(params, "title"), _text(params, "description", required=False))
        return svc.snapshot()

    @server.method("framework.delete")
    def fw_delete(params: dict[str, Any]) -> dict[str, Any]:
        removed = svc.project.delete_node(params.get("id"))
        svc._results.clear()
        return {**svc.snapshot(), "removed": removed}

    @server.method("framework.move")
    def fw_move(params: dict[str, Any]) -> dict[str, Any]:
        svc.project.move_node(params.get("id"), params.get("direction"))
        return svc.snapshot()

    # Indicators
    @server.method("indicator.save")
    def ind_save(params: dict[str, Any]) -> dict[str, Any]:
        return svc.save_indicator(params)

    @server.method("indicator.delete")
    def ind_delete(params: dict[str, Any]) -> dict[str, Any]:
        svc.project.delete_record("indicator", params.get("id"))
        return svc.snapshot()

    @server.method("indicator.move")
    def ind_move(params: dict[str, Any]) -> dict[str, Any]:
        svc.project.move_record("indicator", params.get("id"), params.get("direction"))
        return svc.snapshot()

    # Datasets
    @server.method("dataset.inspect")
    def ds_inspect(params: dict[str, Any]) -> dict[str, Any]:
        sheet = params.get("sheet")
        return datasets.inspect(Path(_text(params, "path", max_len=4000)), sheet if isinstance(sheet, str) else None)

    @server.method("dataset.import")
    def ds_import(params: dict[str, Any]) -> dict[str, Any]:
        return svc.import_dataset(params)

    @server.method("dataset.update")
    def ds_update(params: dict[str, Any]) -> dict[str, Any]:
        return svc.update_dataset(params)

    @server.method("dataset.export")
    def ds_export(params: dict[str, Any]) -> dict[str, Any]:
        return svc.export_dataset(params)

    @server.method("dataset.delete")
    def ds_delete(params: dict[str, Any]) -> dict[str, Any]:
        return svc.delete_dataset(params.get("id"))

    @server.method("dataset.preview")
    def ds_preview(params: dict[str, Any]) -> dict[str, Any]:
        return svc.preview(params)

    @server.method("dataset.column_values")
    def ds_values(params: dict[str, Any]) -> dict[str, Any]:
        return svc.column_values(params)

    # Cleaning
    @server.method("cleaning.add")
    def cl_add(params: dict[str, Any]) -> dict[str, Any]:
        return svc.add_rule(params)

    @server.method("cleaning.update")
    def cl_update(params: dict[str, Any]) -> dict[str, Any]:
        return svc.update_rule(params)

    @server.method("cleaning.delete")
    def cl_delete(params: dict[str, Any]) -> dict[str, Any]:
        svc.project.delete_record("cleaning_rule", params.get("id"))
        svc._results.clear()
        return svc.snapshot()

    @server.method("cleaning.move")
    def cl_move(params: dict[str, Any]) -> dict[str, Any]:
        svc.project.move_record("cleaning_rule", params.get("id"), params.get("direction"))
        svc._results.clear()
        return svc.snapshot()

    # Analysis
    @server.method("analysis.indicator")
    def an_indicator(params: dict[str, Any]) -> dict[str, Any]:
        return svc.indicator_analysis(params.get("id"))

    @server.method("analysis.overview")
    def an_overview(_: dict[str, Any]) -> dict[str, Any]:
        return svc.overview()

    # Report
    @server.method("report.generate")
    def rep_generate(params: dict[str, Any]) -> dict[str, Any]:
        from .report import generate

        lang = params.get("lang", "fr")
        if lang not in ("fr", "en"):
            raise RpcError("lang must be fr or en", INVALID_PARAMS, data={"key": "invalid_params"})
        return generate(svc, Path(_text(params, "path", max_len=4000)), lang)

    return svc
