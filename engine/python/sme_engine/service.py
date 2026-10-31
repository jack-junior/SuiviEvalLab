"""Engine methods for projects, framework, indicators, data, cleaning, analysis and report.

The interface sees a project as one "snapshot" (project info, framework,
indicators, datasets with their cleaning journal). Methods that change something
return the new snapshot, so the interface never has to merge state itself.
"""

from __future__ import annotations

import base64
import hashlib
import json
from pathlib import Path
from typing import Any

import polars as pl

from . import cleaning, datasets, indicators, merge, quality, stattests, xlsform
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
        self._merged: dict[str, tuple[str, pl.DataFrame, dict[str, int]]] = {}
        self._results: dict[str, Any] = {}

    # ----- state ------------------------------------------------------------------

    @property
    def project(self) -> Project:
        return self.ws.require()

    def reset_caches(self) -> None:
        self._raw.clear()
        self._merged.clear()
        self._clean.clear()
        self._results.clear()

    def snapshot(self) -> dict[str, Any]:
        p = self.project
        ds_list = []
        for ds in p.records("dataset"):
            rules = p.records("cleaning_rule", ds["id"])
            try:
                _, cleaned, effects = self.cleaned(ds["id"])
            except RpcError as exc:  # a merged file whose sources no longer join
                ds_list.append({**ds, "rules": rules, "clean_rows": 0, "error": str(exc)})
                continue
            by_id = {e["id"]: e for e in effects}
            for r in rules:
                r["effect"] = by_id.get(r["id"])
            extra = {"merge": {**ds["merge"], "stats": self.merged(ds)[2]}} if ds.get("merge") else {}
            ds_list.append({**ds, **extra, "rules": rules, "clean_rows": cleaned.height})
        return {
            "project": p.info(),
            "framework": p.framework(),
            "indicators": self.ordered_indicators(),
            "datasets": ds_list,
            "tests": p.records("saved_test"),
        }

    def ordered_indicators(self) -> list[dict[str, Any]]:
        """Indicators in framework order (node order, then position under the node)."""
        order = {n["id"]: i for i, n in enumerate(self.project.framework())}
        return sorted(self.project.records("indicator"), key=lambda r: order.get(r["node_id"], 1 << 30))

    # ----- data -------------------------------------------------------------------

    def dataset_spec(self, dataset_id: Any) -> dict[str, Any]:
        return self.project.record("dataset", dataset_id)

    def raw(self, dataset_id: str) -> pl.DataFrame:
        spec = self.dataset_spec(dataset_id)
        if spec.get("merge"):
            return self.merged(spec)[1]
        if dataset_id not in self._raw:
            self._raw[dataset_id] = datasets.from_parquet(self.project.blob("dataset", "raw", dataset_id))
        return self._raw[dataset_id]

    def merged(self, spec: dict[str, Any]) -> tuple[str, pl.DataFrame, dict[str, int]]:
        """Rows of a merged dataset, joined from the cleaned data of its sources. Cached."""
        m = spec["merge"]
        lsig, left, _ = self.cleaned(m["left"])
        rsig, right, _ = self.cleaned(m["right"])
        signature = hashlib.sha256(json.dumps([lsig, rsig, m], sort_keys=True).encode()).hexdigest()
        cached = self._merged.get(spec["id"])
        if cached and cached[0] == signature:
            return cached
        df, stats = merge.join(left, right, m)
        self._merged[spec["id"]] = (signature, df, stats)
        return self._merged[spec["id"]]

    def cleaned(self, dataset_id: str) -> tuple[str, pl.DataFrame, list[dict[str, Any]]]:
        """Raw data with missing codes as nulls, then the enabled rules in order. Cached."""
        spec = self.dataset_spec(dataset_id)
        rules = self.project.records("cleaning_rule", dataset_id)
        source = self.merged(spec)[0] if spec.get("merge") else None
        signature = hashlib.sha256(
            json.dumps([spec["na_values"], rules, source], sort_keys=True, ensure_ascii=False).encode()
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
        form = params.get("form")
        if isinstance(form, dict) and isinstance(form.get("survey"), str):
            parsed = xlsform.parse(path, form["survey"], form.get("choices"), df.columns)
            spec["labels"] = parsed["labels"]
            spec["form_source"] = {"file": path.name, **form}
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

    def attach_form(self, params: dict[str, Any]) -> dict[str, Any]:
        """Read labels from a questionnaire file (XLSForm) for an imported dataset."""
        spec = self.dataset_spec(params.get("id"))
        path = Path(_text(params, "path", max_len=4000))
        sheets = datasets.sheet_names(path)
        form = xlsform.find_form(path, sheets)
        if not form:
            raise _err("No XLSForm survey sheet found in this file", "form_not_found")
        parsed = xlsform.parse(path, form["survey"], form.get("choices"), [c["name"] for c in spec["columns"]])
        if parsed["matched_columns"] == 0:
            raise _err("The questionnaire matches no column of this dataset", "form_no_match")
        spec["labels"] = xlsform.merge(spec.get("labels"), parsed["labels"])
        spec["form_source"] = {"file": path.name, **form}
        self.project.update_record("dataset", spec["id"], spec)
        return {
            **self.snapshot(),
            "matched_columns": parsed["matched_columns"],
            "matched_value_lists": parsed["matched_value_lists"],
        }

    def set_labels(self, params: dict[str, Any]) -> dict[str, Any]:
        """Labels typed by the user for one column and its values, in one language."""
        spec = self.dataset_spec(params.get("id"))
        column = params.get("column")
        if column not in [c["name"] for c in spec["columns"]]:
            raise _err(f"Unknown column: {column}", "column_not_found")
        lang = params.get("lang") if params.get("lang") in ("fr", "en") else "default"
        labels = spec.setdefault("labels", {"columns": {}, "values": {}})
        if "label" in params:
            text = _text(params, "label", required=False, max_len=500)
            col_labels = labels["columns"].setdefault(column, {})
            if text:
                col_labels[lang] = text
            else:
                col_labels.pop(lang, None)
        values = params.get("values")
        if isinstance(values, dict):
            target = labels["values"].setdefault(column, {})
            for code, text in values.items():
                entry = target.setdefault(str(code), {})
                if isinstance(text, str) and text.strip():
                    entry[lang] = text.strip()[:300]
                else:
                    entry.pop(lang, None)
        self.project.update_record("dataset", spec["id"], spec)
        return self.snapshot()

    def export_dataset(self, params: dict[str, Any]) -> dict[str, Any]:
        """Write the cleaned data as CSV (UTF-8 with BOM, so Excel reads accents), for R or Excel."""
        _, df, _ = self.cleaned(params.get("id"))
        path = Path(_text(params, "path", max_len=4000))
        if path.suffix.lower() != ".csv":
            path = path.with_suffix(".csv")
        df.write_csv(path, include_bom=True, null_value="")
        return {"path": str(path), "rows": df.height}

    def merge_datasets(self, params: dict[str, Any]) -> dict[str, Any]:
        """A new dataset joining two others by a key (individuals to their household)."""
        left = self.dataset_spec(params.get("left"))
        right = self.dataset_spec(params.get("right"))
        m = merge.validate(params, left, right)
        df, stats = merge.join(self.cleaned(left["id"])[1], self.cleaned(right["id"])[1], m)
        names = merge.renamed(
            [c["name"] for c in left["columns"]], [c["name"] for c in right["columns"]], m["right_key"]
        )
        if params.get("dry_run"):
            clashes = [n for c, n in names.items() if n != c]
            return {"stats": stats, "added": len(names), "renamed": clashes}
        design = left.get("design") or {}
        if not design.get("weights"):
            # Individuals often carry no weight; the household weight comes with the household.
            rd = right.get("design") or {}
            design = {
                "weights": names.get(rd.get("weights") or "", None),
                "cluster": names.get(rd.get("cluster") or "", None),
                "strata": [names[c] for c in rd.get("strata") or [] if c in names],
            }
            if not design["weights"]:
                design = datasets.guess_design(df.columns)
        spec = {
            "name": _text(params, "name", max_len=200),
            "round": params.get("round") or left["round"],
            "source_name": f"{left['name']} + {right['name']}",
            "sheet": None,
            "imported_at": datasets.now(),
            "rows": df.height,
            "na_values": [],
            "id_column": left.get("id_column"),
            "design": datasets.validate_design(design, df.columns),
            "attribution": "; ".join(a for a in {left.get("attribution") or "", right.get("attribution") or ""} if a),
            "labels": merge.labels(left, right, names),
            "columns": datasets.describe_columns(df, []),
            "merge": {**m, "stats": stats},
        }
        if spec["round"] not in datasets.ROUNDS:
            raise _err("Unknown round", "invalid_round")
        new_id = self.project.insert_record("dataset", spec, raw=b"")
        return {**self.snapshot(), "created": new_id}

    def delete_dataset(self, dataset_id: Any) -> dict[str, Any]:
        users = [
            d["name"]
            for d in self.project.records("dataset")
            if (d.get("merge") or {}).get("left") == dataset_id or (d.get("merge") or {}).get("right") == dataset_id
        ]
        if users:
            raise _err(f"This file is used by the merged file {users[0]}: delete that one first", "dataset_in_use")
        self.project.delete_record("dataset", dataset_id)
        self._merged.pop(dataset_id, None)
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

    @staticmethod
    def _r_quote(values: list[str]) -> str:
        return ", ".join('"' + v.replace("\\", "\\\\").replace('"', '\\"') + '"' for v in values)

    def _prepare(self, ind: dict[str, Any], ds: dict[str, Any], by: bool) -> tuple[pl.DataFrame, dict[str, Any]] | None:
        """The table sent to R and the R arguments, or None if a needed column is missing.

        Outcomes built from several columns (conditions) and crossed breakdowns are
        computed here, so R receives one outcome column; `y_code` is the R
        equivalent, printed in the reproducible script.
        """
        _, df, _ = self.cleaned(ds["id"])
        design = ds["design"]
        unit = ind["unit"]
        conds = ind.get("conditions") or (
            [{"column": ind["column"], "values": ind["success_values"]}]
            if unit == "percent" and ind.get("column")
            else []
        )
        groups = [c for c in (ind.get("disaggregation"), ind.get("disaggregation2")) if c] if by else []
        needed = [
            *(c["column"] for c in conds),
            *(groups),
            ind.get("column") if unit in ("mean", "count") else None,
            ind.get("numerator"),
            ind.get("denominator"),
            design.get("weights"),
            design.get("cluster"),
            *(design.get("strata") or []),
        ]
        needed = [c for c in dict.fromkeys(needed) if c]
        if any(c not in df.columns for c in needed):
            return None
        table = df.select(needed)
        args: dict[str, Any] = {
            "weights": design.get("weights"),
            "strata": design.get("strata") or None,
            "cluster": design.get("cluster"),
            "level": 0.95,
        }
        y_code = None
        uses_conditions = unit == "percent" or (unit == "count" and ind.get("count_mode") != "sum")
        if uses_conditions:
            hits = [pl.col(c["column"]).is_in(c["values"]) for c in conds]
            missing = pl.any_horizontal([pl.col(c["column"]).is_null() for c in conds])
            met = pl.all_horizontal(hits) if ind.get("combine", "all") == "all" else pl.any_horizontal(hits)
            r_hits = [f"(donnees$`{c['column']}` %in% c({self._r_quote(c['values'])}))" for c in conds]
            r_join = " & " if ind.get("combine", "all") == "all" else " | "
            r_na = " | ".join(f"is.na(donnees$`{c['column']}`)" for c in conds)
            if unit == "percent":
                table = table.with_columns(
                    pl.when(missing)
                    .then(None)
                    .otherwise(pl.when(met).then(pl.lit("1")).otherwise(pl.lit("0")))
                    .alias(".y")
                )
                args.update({"type": "proportion", "var": ".y", "success": ["1"]})
                y_code = f"donnees$y <- as.numeric({r_join.join(r_hits)})\ndonnees$y[{r_na}] <- NA"
            else:
                table = table.with_columns(pl.when(met.fill_null(False)).then(1.0).otherwise(0.0).alias(".y"))
                args.update({"type": "total", "var": ".y"})
                y_code = f"donnees$y <- as.numeric({r_join.join(r_hits)})\ndonnees$y[is.na(donnees$y)] <- 0"
        elif unit == "count":
            args.update({"type": "total", "var": ind["column"]})
        elif unit == "ratio":
            args.update({"type": "ratio", "var": ind["numerator"], "den": ind["denominator"]})
        else:
            args.update({"type": "mean", "var": ind["column"]})
        if groups:
            parts = [pl.col(g).cast(pl.Utf8) for g in groups]
            table = table.with_columns(
                pl.when(pl.any_horizontal([pl.col(g).is_null() for g in groups]))
                .then(None)
                .otherwise(pl.concat_str(parts, separator=" / "))
                .alias(".group")
            )
            args["by"] = ".group"
            r_group = (
                f'donnees$`.group` <- paste(donnees$`{groups[0]}`, donnees$`{groups[1]}`, sep = " / ")'
                if len(groups) == 2
                else f"donnees$`.group` <- donnees$`{groups[0]}`"
            )
            y_code = (
                f"{y_code}\n{r_group}"
                if y_code
                else (f"donnees$y <- as.numeric(donnees$`{args['var']}`)\n{r_group}" if unit != "percent" else None)
            )
        if y_code:
            args["y_code"] = y_code
        return table, args

    @staticmethod
    def _scale(res: dict[str, Any], k: float) -> dict[str, Any]:
        """Multiply a result by k (ratio per 100 or per 1,000)."""
        if k == 1:
            return res
        out = dict(res)
        for f in ("estimate", "ci_low", "ci_high", "se", "difference"):
            if isinstance(out.get(f), (int, float)):
                out[f] = out[f] * k
        for f in ("a", "b"):
            if isinstance(out.get(f), dict):
                out[f] = Service._scale(out[f], k)
        if isinstance(out.get("by"), list):
            out["by"] = [Service._scale(g, k) for g in out["by"]]
        return out

    def _cache_key(self, *parts: Any) -> str:
        return hashlib.sha256(json.dumps(parts, sort_keys=True, default=str).encode()).hexdigest()

    def estimate(self, ind: dict[str, Any], ds: dict[str, Any], by: bool = True) -> dict[str, Any] | None:
        if not indicators.ready(ind):
            return None
        try:
            prepared = self._prepare(ind, ds, by)
        except RpcError as exc:  # a merged dataset whose sources no longer join
            return {"error_key": "dataset_error", "detail": str(exc), "dataset_id": ds["id"]}
        if prepared is None:
            return {"error_key": "column_missing", "dataset_id": ds["id"]}
        table, args = prepared
        sig = self.cleaned(ds["id"])[0]
        key = self._cache_key("estimate", sig, args, ds["design"], table.columns)
        if key not in self._results:
            path = self.bridge.write_table(table, f"t_{key[:16]}")
            try:
                self._results[key] = self.bridge.call("estimate", {"path": path, **args})
            except RpcError as exc:
                return {"error_key": "r_error", "detail": str(exc), "dataset_id": ds["id"]}
        return {**self._scale(self._results[key], ind.get("multiplier") or 1.0), "dataset_id": ds["id"]}

    def compare(self, ind: dict[str, Any], a: dict[str, Any], b: dict[str, Any]) -> dict[str, Any] | None:
        pa_, pb_ = self._prepare(ind, a, False), self._prepare(ind, b, False)
        if pa_ is None or pb_ is None:
            return None
        (ta, args), (tb, _) = pa_, pb_
        if a["design"] != b["design"]:
            # Both rounds must be analysed with the same kind of design; keep the common part.
            for f in ("weights", "cluster", "strata"):
                if a["design"].get(f) != b["design"].get(f):
                    args[f] = None
        key = self._cache_key("compare", self.cleaned(a["id"])[0], self.cleaned(b["id"])[0], args)
        if key not in self._results:
            pa = self.bridge.write_table(ta, f"a_{key[:16]}")
            pb = self.bridge.write_table(tb, f"b_{key[:16]}")
            try:
                self._results[key] = self.bridge.call("compare", {"path_a": pa, "path_b": pb, **args})
            except RpcError as exc:
                return {"error_key": "r_error", "detail": str(exc)}
        return {**self._scale(self._results[key], ind.get("multiplier") or 1.0), "a_id": a["id"], "b_id": b["id"]}

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

    def labeller(self, lang: str) -> Any:
        """label(column, code=None): readable label from the datasets, else the code."""
        sets = self.project.records("dataset")

        def label(column: str, code: str | None = None) -> str:
            for ds in sets:
                labels = ds.get("labels") or {}
                found = (
                    xlsform.pick(labels.get("values", {}).get(column, {}).get(code), lang)
                    if code is not None
                    else xlsform.pick(labels.get("columns", {}).get(column), lang)
                )
                if found:
                    return found
            return code if code is not None else column

        return label

    def test_conclusion(self, spec: dict[str, Any], res: dict[str, Any]) -> dict[str, list[str]]:
        from .report import Fmt

        return {lang: stattests.conclusion(spec, res, lang, Fmt(lang), self.labeller(lang)) for lang in ("fr", "en")}

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

    @server.method("project.backups")
    def backups_list(params: dict[str, Any]) -> dict[str, Any]:
        from . import backups

        return {"backups": backups.listing(Path(_text(params, "path", max_len=4000)))}

    @server.method("project.restore")
    def backups_restore(params: dict[str, Any]) -> dict[str, Any]:
        from . import backups

        path = Path(_text(params, "path", max_len=4000))
        current = workspace.project
        if current is not None and current.path.resolve() == path.resolve():
            workspace.close()
            svc.reset_caches()
        backups.restore(path, params.get("backup"))
        return opened(Project.open(path))

    @server.method("tool.sample_size")
    def sample_size(params: dict[str, Any]) -> dict[str, Any]:
        """Survey sample size, computed by R. Needs no open project."""
        goals = ("estimate_prop", "estimate_mean", "compare_prop", "compare_mean")
        goal = params.get("goal")
        if goal not in goals:
            raise _err(f"goal must be one of {goals}", "invalid_params")

        def num(name: str, low: float | None = None, high: float | None = None, default: Any = None) -> Any:
            v = params.get(name, default)
            if v is None or v == "":
                return default
            if isinstance(v, bool) or not isinstance(v, (int, float)) or v != v:
                raise _err(f"{name} must be a number", "sample_invalid")
            if (low is not None and v <= low) or (high is not None and v > high):
                raise _err(f"{name} is out of range", "sample_invalid")
            return float(v)

        args: dict[str, Any] = {
            "goal": goal,
            "conf": num("conf", 0.5, 0.999, 0.95),
            "power": num("power", 0.5, 0.999, 0.8),
            "deff": max(1.0, num("deff", 0, 20, 1.0)),
            "domains": int(num("domains", 0, 1000, 1)),
            "response": num("response", 0, 1, 1.0),
        }
        if goal in ("estimate_prop", "compare_prop"):
            args["p"] = num("p", 0, 0.999)
            if args["p"] is None:
                raise _err("p is required", "sample_invalid")
        if goal == "compare_prop":
            args["p2"] = num("p2", 0, 0.999)
            if args["p2"] is None or args["p2"] == args["p"]:
                raise _err("p2 is required and differs from p", "sample_invalid")
        if goal in ("estimate_mean", "compare_mean"):
            args["sd"] = num("sd", 0)
            if args["sd"] is None:
                raise _err("sd is required", "sample_invalid")
        if goal.startswith("estimate"):
            args["margin"] = num("margin", 0, None if goal == "estimate_mean" else 0.5)
            if args["margin"] is None:
                raise _err("margin is required", "sample_invalid")
            population = num("population", 0)
            if population is not None:
                args["population"] = population
        if goal == "compare_mean":
            args["delta"] = num("delta", 0)
            if args["delta"] is None:
                raise _err("delta is required", "sample_invalid")
        return bridge.call("sample_size", args)

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

    @server.method("dataset.attach_form")
    def ds_attach_form(params: dict[str, Any]) -> dict[str, Any]:
        return svc.attach_form(params)

    @server.method("dataset.set_labels")
    def ds_set_labels(params: dict[str, Any]) -> dict[str, Any]:
        return svc.set_labels(params)

    @server.method("dataset.export")
    def ds_export(params: dict[str, Any]) -> dict[str, Any]:
        return svc.export_dataset(params)

    @server.method("dataset.merge")
    def ds_merge(params: dict[str, Any]) -> dict[str, Any]:
        return svc.merge_datasets(params)

    @server.method("dataset.quality")
    def ds_quality(params: dict[str, Any]) -> dict[str, Any]:
        spec = svc.dataset_spec(params.get("id"))
        return quality.diagnose(svc.cleaned(spec["id"])[1], spec)

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

    @server.method("test.run")
    def test_run(params: dict[str, Any]) -> dict[str, Any]:
        """Run a test without saving it; the conclusion comes in both languages."""
        spec = stattests.validate(params.get("test") or {})
        res = stattests.run(svc, spec)
        return {"result": res, "conclusion": svc.test_conclusion(spec, res)}

    @server.method("test.save")
    def test_save(params: dict[str, Any]) -> dict[str, Any]:
        spec = stattests.validate(params.get("test") or {})
        if params.get("id"):
            svc.project.update_record("saved_test", params["id"], spec)
            saved = params["id"]
        else:
            saved = svc.project.insert_record("saved_test", spec)
        return {**svc.snapshot(), "saved": saved}

    @server.method("test.delete")
    def test_delete(params: dict[str, Any]) -> dict[str, Any]:
        svc.project.delete_record("saved_test", params.get("id"))
        return svc.snapshot()

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
        meta = svc.project.meta()
        template = base64.b64decode(meta["report_template"]) if meta.get("report_template") else None
        return generate(svc, Path(_text(params, "path", max_len=4000)), lang, template)

    @server.method("report.checks")
    def rep_checks(_: dict[str, Any]) -> dict[str, Any]:
        from .checks import run as checks

        return checks(svc)

    @server.method("report.share")
    def rep_share(params: dict[str, Any]) -> dict[str, Any]:
        from .share import generate as share

        lang = params.get("lang", "fr")
        if lang not in ("fr", "en"):
            raise RpcError("lang must be fr or en", INVALID_PARAMS, data={"key": "invalid_params"})
        return share(svc, Path(_text(params, "path", max_len=4000)), lang)

    @server.method("report.set_template")
    def rep_set_template(params: dict[str, Any]) -> dict[str, Any]:
        """Keep the organisation's Word template inside the project, so the report is reproducible."""
        path = Path(_text(params, "path", max_len=4000))
        if path.suffix.lower() not in (".docx", ".dotx"):
            raise _err("The template must be a Word .docx file", "template_type")
        data = path.read_bytes()
        if len(data) > 20 * 1024 * 1024:
            raise _err("The template is larger than 20 MB", "template_too_large")
        try:
            import io

            from docx import Document

            doc = Document(io.BytesIO(data))
        except Exception:  # noqa: BLE001
            raise _err("This file cannot be opened as a Word document", "template_invalid") from None
        has_anchor = any(k in p.text for p in doc.paragraphs for k in ("{{contenu}}", "{{content}}"))
        svc.project.set_meta("report_template", base64.b64encode(data).decode("ascii"))
        svc.project.set_meta("report_template_name", path.name)
        return {**svc.snapshot(), "has_anchor": has_anchor}

    @server.method("report.clear_template")
    def rep_clear_template(_: dict[str, Any]) -> dict[str, Any]:
        svc.project.set_meta("report_template", None)
        svc.project.set_meta("report_template_name", None)
        return svc.snapshot()

    return svc
