# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 GAYI Komi Selassi and SANOUSSI Moudjibou

"""What the Word report contains: sections and their order, indicators and what is shown
for each, analyses and saved tests, and the annexes. Saved in the project (meta
`report_content`); anything not mentioned keeps its default, so new indicators and
analyses are included until the user removes them.
"""

from __future__ import annotations

import json
from typing import Any

from .rpc import INVALID_PARAMS, RpcError

SECTIONS = ("summary", "results", "analyses", "tests", "framework", "annex_data", "annex_methods", "sources")
INDICATOR_PARTS = ("reading", "chart", "breakdown", "definition")
ANALYSIS_PARTS = ("reading", "tables", "charts", "script")
DEFAULT_ANALYSIS = {"reading": True, "tables": True, "charts": True, "script": False}


def _err(message: str) -> RpcError:
    return RpcError(message, INVALID_PARAMS, data={"key": "report_content_invalid"})


def default() -> dict[str, Any]:
    return {
        "sections": [{"id": s, "on": True} for s in SECTIONS],
        "indicators": {},
        "analyses": {},
        "tests": {},
        "journal": True,
    }


def load(project: Any) -> dict[str, Any]:
    raw = project.meta().get("report_content")
    try:
        return normalise(json.loads(raw)) if raw else default()
    except (ValueError, RpcError):
        return default()


def normalise(raw: Any) -> dict[str, Any]:
    """Validate a content choice and complete it with the defaults."""
    if not isinstance(raw, dict):
        raise _err("The report content must be an object")
    out = default()
    sections = raw.get("sections")
    if sections is not None:
        if not isinstance(sections, list):
            raise _err("sections must be a list")
        seen, order = set(), []
        for s in sections:
            sid = s.get("id") if isinstance(s, dict) else None
            if sid in SECTIONS and sid not in seen:
                seen.add(sid)
                order.append({"id": sid, "on": s.get("on", True) is not False})
        order += [{"id": s, "on": True} for s in SECTIONS if s not in seen]  # sections added in a later version
        out["sections"] = order
    for key, parts in (("indicators", INDICATOR_PARTS), ("analyses", ANALYSIS_PARTS)):
        value = raw.get(key) or {}
        if not isinstance(value, dict):
            raise _err(f"{key} must be an object")
        for item_id, opts in value.items():
            if isinstance(opts, dict):
                # An analysis is in the report or not by its own in_report flag (Analyses screen).
                clean = {} if key == "analyses" else {"on": opts.get("on", True) is not False}
                clean |= {p: bool(opts[p]) for p in parts if p in opts}
                out[key][str(item_id)] = clean
    tests = raw.get("tests") or {}
    if not isinstance(tests, dict):
        raise _err("tests must be an object")
    out["tests"] = {str(k): v is not False for k, v in tests.items()}
    out["journal"] = raw.get("journal", True) is not False
    return out


def save(project: Any, raw: Any) -> dict[str, Any]:
    content = normalise(raw)
    project.set_meta("report_content", json.dumps(content, ensure_ascii=False))
    return content


def indicator(content: dict[str, Any], ind_id: str) -> dict[str, bool]:
    opts = content["indicators"].get(ind_id, {})
    return {"on": opts.get("on", True), **{p: opts.get(p, True) for p in INDICATOR_PARTS}}


def analysis(content: dict[str, Any], spec: dict[str, Any]) -> dict[str, bool]:
    opts = content["analyses"].get(spec["id"], {})
    return {"on": spec.get("in_report", True), **{p: opts.get(p, DEFAULT_ANALYSIS[p]) for p in ANALYSIS_PARTS}}


def section_on(content: dict[str, Any], sid: str) -> bool:
    return next((s["on"] for s in content["sections"] if s["id"] == sid), True)
