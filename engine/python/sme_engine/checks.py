"""Checks before the report: what would weaken it, with where to fix it.

Warnings would leave a gap or a wrong figure in the report (an indicator without
data or target, a broken merged file, a very small sample). Remarks are worth a
look but are often deliberate (no survey weights, no definition).
"""

from __future__ import annotations

from typing import Any

from . import indicators

SMALL_SAMPLE = 30


def run(svc: Any) -> dict[str, Any]:
    snap = svc.snapshot()
    items: list[dict[str, Any]] = []

    def add(key: str, severity: str, view: str, target: str | None, name: str = "", **extra: Any) -> None:
        items.append({"key": key, "severity": severity, "view": view, "id": target, "name": name, **extra})

    if not snap["indicators"]:
        add("no_indicators", "warning", "indicators", None)

    for ds in snap["datasets"]:
        if ds.get("error"):
            add("dataset_broken", "warning", "data", ds["id"], ds["name"], detail=ds["error"])
        elif not (ds.get("design") or {}).get("weights"):
            add("dataset_unweighted", "info", "data", ds["id"], ds["name"])

    with_ind = {i["node_id"] for i in snap["indicators"]}
    for node in snap["framework"]:
        if node["level"] in ("outcome", "output") and node["id"] not in with_ind:
            add("node_without_indicator", "info", "indicators", node["id"], node["title"], code=node.get("code") or "")

    for ind in snap["indicators"]:
        name = ind["name"]
        if ind.get("source_type") == "routine":
            an = svc.indicator_analysis(ind["id"])
            if an["current"] is None:
                add("routine_no_values", "warning", "analysis", ind["id"], name)
            elif ind.get("target") is None:
                add("indicator_no_target", "warning", "indicators", ind["node_id"], name)
            if not (ind.get("definition") or "").strip():
                add("indicator_no_definition", "info", "indicators", ind["node_id"], name)
            continue
        if not indicators.ready(ind):
            add("indicator_incomplete", "warning", "indicators", ind["node_id"], name)
            continue
        an = svc.indicator_analysis(ind["id"])
        usable = [r for r in an["rounds"] if "error_key" not in r["result"]]
        if not usable:
            add("indicator_no_data", "warning", "indicators", ind["node_id"], name)
            continue
        if ind.get("target") is None:
            add("indicator_no_target", "warning", "indicators", ind["node_id"], name)
        if an.get("baseline") is None:
            add("indicator_no_baseline", "warning", "indicators", ind["node_id"], name)
        if an.get("current") is None:
            add("indicator_no_current", "info", "analysis", ind["id"], name)
        small = [r for r in usable if (r["result"].get("n") or 0) < SMALL_SAMPLE]
        for r in small:
            add("small_sample", "warning", "analysis", ind["id"], name, n=r["result"].get("n") or 0, round=r["round"])
        comp = an.get("comparison")
        if comp and comp.get("warning") == "weights_scale":
            a, b = comp["mean_weights"]
            add("count_weights_scale", "warning", "analysis", ind["id"], name, a=a, b=b)
        if comp and "error_key" not in comp and comp.get("p_value") is None:
            add("comparison_descriptive", "info", "analysis", ind["id"], name)
        if not (ind.get("definition") or "").strip():
            add("indicator_no_definition", "info", "indicators", ind["node_id"], name)

    warnings = sum(1 for i in items if i["severity"] == "warning")
    items.sort(key=lambda i: i["severity"] != "warning")
    return {"items": items, "warnings": warnings, "remarks": len(items) - warnings}
