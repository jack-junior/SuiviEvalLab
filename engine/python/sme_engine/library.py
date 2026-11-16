# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 GAYI Komi Selassi and SANOUSSI Moudjibou

"""Indicator library: reference sheets by sector, with their public source.

Each sector is a JSON file in the library folder. A sheet gives the name and
definition in French and English, the type, numerator and denominator, the level
it usually sits at, how it is collected, how often, the suggested
disaggregations, and the public reference it follows. Taking a sheet into a
project fills an indicator from it; the indicator keeps the sheet id, so the
same indicator can later be added up across projects.
"""

from __future__ import annotations

import json
import unicodedata
from functools import lru_cache
from pathlib import Path
from typing import Any

from .rpc import INVALID_PARAMS, RpcError

FOLDER = Path(__file__).resolve().parent / "library"
TYPES = ("percent", "count", "mean", "ratio")
LEVELS = ("impact", "outcome", "output")
COLLECTIONS = ("routine", "survey")


def _err(message: str, key: str) -> RpcError:
    return RpcError(message, INVALID_PARAMS, data={"key": key})


def _fold(text: str) -> str:
    plain = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode("ascii")
    return plain.casefold()


def _check(sheet: dict[str, Any], sources: dict[str, Any], sector: str) -> None:
    """Fail loudly on a malformed sheet: the library ships with the application."""
    where = f"{sector}/{sheet.get('id')}"
    for key in ("name", "definition"):
        assert sheet[key]["fr"] and sheet[key]["en"], f"{where}: {key} in both languages"
    assert sheet["type"] in TYPES, f"{where}: type"
    assert sheet["level"] in LEVELS, f"{where}: level"
    assert sheet["collection"] in COLLECTIONS, f"{where}: collection"
    assert sheet.get("source") is None or sheet["source"] in sources, f"{where}: source"
    if sheet["type"] in ("percent", "ratio"):
        assert sheet.get("numerator") and sheet.get("denominator"), f"{where}: numerator and denominator"
    assert sheet.get("aggregation", "sum") in ("sum", "last", "mean"), f"{where}: aggregation"


@lru_cache(maxsize=1)
def load() -> dict[str, Any]:
    sources = json.loads((FOLDER / "sources.json").read_text(encoding="utf-8"))
    sources.pop("_licence", None)
    sectors = []
    sheets: dict[str, dict[str, Any]] = {}
    for path in sorted(FOLDER.glob("*.json")):
        if path.name == "sources.json":
            continue
        data = json.loads(path.read_text(encoding="utf-8"))
        sectors.append({"key": data["sector"], "name": data["name"], "count": len(data["indicators"])})
        for sheet in data["indicators"]:
            _check(sheet, sources, data["sector"])
            assert sheet["id"] not in sheets, f"duplicate {sheet['id']}"
            sheets[sheet["id"]] = {**sheet, "sector": data["sector"]}
    return {"sources": sources, "sectors": sectors, "sheets": sheets}


def citation(sheet: dict[str, Any]) -> str:
    src = load()["sources"].get(sheet.get("source") or "")
    if not src:
        return ""
    parts = [src["publisher"], src["title"], str(src["year"])]
    if sheet.get("ref"):
        parts.append(sheet["ref"])
    return ", ".join(parts)


def search(query: Any = "", sector: Any = None, limit: int = 200) -> list[dict[str, Any]]:
    lib = load()
    words = _fold(str(query or "")).split()
    out = []
    for sheet in lib["sheets"].values():
        if sector and sheet["sector"] != sector:
            continue
        haystack = _fold(
            " ".join(
                [
                    *sheet["name"].values(),
                    *sheet["definition"].values(),
                    sheet.get("ref") or "",
                    sheet["id"],
                ]
            )
        )
        if all(w in haystack for w in words):
            out.append(
                {**sheet, "citation": citation(sheet), "source_info": lib["sources"].get(sheet.get("source") or "")}
            )
        if len(out) >= limit:
            break
    return out


def sheet(sheet_id: Any) -> dict[str, Any]:
    found = load()["sheets"].get(sheet_id) if isinstance(sheet_id, str) else None
    if found is None:
        raise _err(f"Unknown library indicator: {sheet_id}", "library_not_found")
    return found


def to_indicator(s: dict[str, Any], lang: str) -> dict[str, Any]:
    """Indicator spec filled from a library sheet, in the project language."""
    text = lambda d: (d or {}).get(lang) or (d or {}).get("fr") or ""  # noqa: E731
    labels = {
        "fr": ("Numérateur : ", "Dénominateur : "),
        "en": ("Numerator: ", "Denominator: "),
    }[lang]
    definition = text(s["definition"])
    if s.get("numerator"):
        definition += f"\n{labels[0]}{text(s['numerator'])}.\n{labels[1]}{text(s['denominator'])}."
    if s.get("benchmark"):
        definition += f"\n{text(s['benchmark'])}"
    spec: dict[str, Any] = {
        "name": text(s["name"]),
        "definition": definition,
        "unit": s["type"],
        "direction": s.get("direction", "increase"),
        "source_type": s["collection"],
        "frequency": s["frequency"],
        "unit_label": text(s.get("unit_label")),
        "library_id": s["id"],
        "library_ref": citation(s),
        "breakdowns": list(s.get("breakdowns") or []),
    }
    if s["type"] == "ratio":
        spec["multiplier"] = s.get("multiplier", 1)
    if s["collection"] == "routine":
        spec["aggregation"] = s.get("aggregation") or ("last" if s["type"] == "percent" else "sum")
    return spec
