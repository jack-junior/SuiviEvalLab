# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 GAYI Komi Selassi and SANOUSSI Moudjibou

"""Logical framework models: the levels of the results chain and their names, by donor.

Projects keep five internal level keys, from the top: impact, outcome, output,
activity, detail. They only mark the depth: what each level is called comes from
the model. A model says how many levels are used (2 to 5), their names in French
and English, and which levels carry indicators. The model of a project is kept
in its metadata, so the interface, the Word report, the monitoring plan and the
dashboard all use the donor's own words.

    {"id": "eu", "levels": [{"fr": "...", "en": "...", "indicators": true}, ...]}
"""

from __future__ import annotations

import json
from typing import Any

from .rpc import INVALID_PARAMS, RpcError

KEYS = ("impact", "outcome", "output", "activity", "detail")


def _lv(fr: str, en: str, indicators: bool = True) -> dict[str, Any]:
    return {"fr": fr, "en": en, "indicators": indicators}


MODELS: dict[str, list[dict[str, Any]]] = {
    # The chain used until version 0.3, close to most NGO logframes.
    "standard": [
        _lv("Impact", "Impact"),
        _lv("Effet", "Outcome"),
        _lv("Produit", "Output"),
        _lv("Activité", "Activity", False),
    ],
    # European Union logical framework (results chain of the 2020s guidelines).
    "eu": [
        _lv("Objectif global", "Overall objective"),
        _lv("Objectif spécifique", "Specific objective"),
        _lv("Produit", "Output"),
        _lv("Activité", "Activity", False),
    ],
    # USAID results framework, with the activities of the work plan below it.
    "usaid": [
        _lv("But", "Goal"),
        _lv("Objectif de développement", "Development objective"),
        _lv("Résultat intermédiaire", "Intermediate result"),
        _lv("Sous-résultat intermédiaire", "Sub-intermediate result"),
        _lv("Activité", "Activity", False),
    ],
    # United Nations results-based management.
    "un": [
        _lv("Impact", "Impact"),
        _lv("Effet", "Outcome"),
        _lv("Produit", "Output"),
        _lv("Activité", "Activity", False),
    ],
    # World Bank results framework: indicators of the project development objective,
    # and intermediate results indicators grouped by component. Activities serve the
    # work plan; they are not part of the Bank's results framework.
    "worldbank": [
        _lv("Objectif de développement du projet", "Project development objective"),
        _lv("Composante", "Component", False),
        _lv("Résultat intermédiaire", "Intermediate result"),
        _lv("Activité", "Activity", False),
    ],
    # International Federation of Red Cross and Red Crescent Societies logframe.
    "ifrc": [
        _lv("Objectif global", "Goal"),
        _lv("Résultat", "Outcome"),
        _lv("Produit", "Output"),
        _lv("Activité", "Activity", False),
    ],
}
# Two-level World Bank model of versions 0.4 and 0.5, kept for the projects made with it.
WORLDBANK_V04 = [
    _lv("Objectif de développement du projet", "Project development objective"),
    _lv("Résultat intermédiaire", "Intermediate result"),
]
DEFAULT = "standard"


def _err(message: str) -> RpcError:
    return RpcError(message, INVALID_PARAMS, data={"key": "framework_model_invalid"})


def validate(spec: Any) -> dict[str, Any]:
    """A model chosen in the list, or a custom one with 2 to 5 named levels."""
    if not isinstance(spec, dict):
        raise _err("The framework model must be an object")
    model_id = spec.get("id")
    if model_id in MODELS:
        return {"id": model_id, "levels": [dict(x) for x in MODELS[model_id]]}
    if model_id != "custom":
        raise _err(f"Unknown framework model: {model_id}")
    levels = spec.get("levels")
    if not isinstance(levels, list) or not 2 <= len(levels) <= len(KEYS):
        raise _err("A custom framework has 2 to 5 levels")
    out = []
    for lv in levels:
        if not isinstance(lv, dict):
            raise _err("Invalid level")
        fr = str(lv.get("fr") or "").strip()[:60]
        en = str(lv.get("en") or "").strip()[:60] or fr
        if not fr:
            raise _err("Each level needs a name")
        out.append({"fr": fr, "en": en, "indicators": lv.get("indicators", True) is not False})
    if not any(lv["indicators"] for lv in out):
        raise _err("At least one level must carry indicators")
    return {"id": "custom", "levels": out}


def from_meta(meta: dict[str, str]) -> dict[str, Any]:
    raw = meta.get("framework_model")
    if raw:
        try:
            return validate(json.loads(raw))
        except (ValueError, RpcError):
            pass
    return {"id": DEFAULT, "levels": [dict(x) for x in MODELS[DEFAULT]]}


def level_index(level: str) -> int:
    return KEYS.index(level)


def name(model: dict[str, Any], level: str, lang: str) -> str:
    i = level_index(level)
    levels = model["levels"]
    if i >= len(levels):
        return level
    return levels[i].get(lang) or levels[i]["fr"]


def carries_indicators(model: dict[str, Any], level: str) -> bool:
    i = level_index(level)
    return i < len(model["levels"]) and bool(model["levels"][i]["indicators"])


def names(model: dict[str, Any], lang: str) -> dict[str, str]:
    """{level key: name} for the levels of the model."""
    return {KEYS[i]: lv.get(lang) or lv["fr"] for i, lv in enumerate(model["levels"])}
