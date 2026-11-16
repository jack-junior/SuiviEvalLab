# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 GAYI Komi Selassi and SANOUSSI Moudjibou

"""Places, partners and disaggregations of a project.

Places form a tree whose levels are named in the profile (region, district,
commune, village...). Partners are the organisations the project works with, and
the places where each works. Disaggregations are the categories results are broken
down by (sex, age, disability...). Every disaggregation has an implicit category
"not specified", so a total always equals the sum of its parts.

    place:          {"name": "Kara", "code": "TG-K", "level": 0, "parent_id": ""}
    partner:        {"name": "...", "acronym": "...", "role": "implementing",
                     "contact": "...", "place_ids": [...], "start": "", "end": ""}
    disaggregation: {"key": "sex", "name_fr": "Sexe", "name_en": "Sex",
                     "categories": [{"code": "f", "fr": "Femme", "en": "Female"}, ...]}
"""

from __future__ import annotations

import re
import unicodedata
from typing import Any

from .rpc import INVALID_PARAMS, RpcError
from .schedule import parse_date

ROLES = ("implementing", "funding", "technical", "government", "community", "research", "other")
UNSPECIFIED = {"code": "_na", "fr": "Non précisé", "en": "Not specified"}
CODE = re.compile(r"^[A-Za-z0-9_.+\-]{1,30}$")


def _err(message: str, key: str, **info: Any) -> RpcError:
    return RpcError(message, INVALID_PARAMS, data={"key": key, **info})


def _str(value: Any, max_len: int = 200) -> str:
    return str(value or "").strip()[:max_len]


def slug(text: str) -> str:
    """Code made from a name: "Type d'école" gives "type_d_ecole"."""
    plain = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode("ascii")
    return re.sub(r"[^a-z0-9]+", "_", plain.lower()).strip("_")[:30]


# ----- places ------------------------------------------------------------------


def validate_place(spec: Any, places: list[dict[str, Any]], levels: list[str], own_id: str | None = None) -> dict:
    if not isinstance(spec, dict):
        raise _err("The place must be an object", "place_invalid")
    name = _str(spec.get("name"), 120)
    if not name:
        raise _err("The place needs a name", "field_required", field="name")
    parent_id = _str(spec.get("parent_id"), 40)
    by_id = {p["id"]: p for p in places}
    if parent_id:
        parent = by_id.get(parent_id)
        if parent is None or parent_id == own_id:
            raise _err("Unknown parent place", "place_parent_invalid")
        level = parent["level"] + 1
        # A place cannot sit under one of its own descendants.
        cursor = parent
        while cursor.get("parent_id"):
            if cursor["parent_id"] == own_id:
                raise _err("A place cannot be inside itself", "place_parent_invalid")
            cursor = by_id[cursor["parent_id"]]
    else:
        level = 0
    if level >= len(levels):
        raise _err("This place is below the last level of places", "place_too_deep")
    code = _str(spec.get("code"), 30)
    if code and any(p.get("code") == code and p["id"] != own_id for p in places):
        raise _err(f"The code {code} is already used", "place_code_duplicate", code=code)
    siblings = [p for p in places if p.get("parent_id", "") == parent_id and p["id"] != own_id]
    if any(p["name"].casefold() == name.casefold() for p in siblings):
        raise _err(f"{name} already exists at this place", "place_duplicate", name=name)
    return {"name": name, "code": code, "level": level, "parent_id": parent_id}


def import_places(rows: Any, places: list[dict[str, Any]], levels: list[str]) -> list[dict[str, Any]]:
    """Rows of a pasted or imported table: one column per level, from the top.

    [["Kara", "Kozah", "Lama"], ["Kara", "Kozah", "Pya"]] gives the tree once,
    reusing the places already there. Returns the places to create, in order, each
    with a temporary "ref" and a "parent_ref" (an existing id or another ref).
    """
    if not isinstance(rows, list) or len(rows) > 20000:
        raise _err("Expected a list of rows", "place_import_invalid")
    known: dict[tuple[str, str], str] = {(p.get("parent_id", ""), p["name"].casefold()): p["id"] for p in places}
    out: list[dict[str, Any]] = []
    for row in rows:
        if not isinstance(row, list):
            raise _err("Each row must be a list", "place_import_invalid")
        parent = ""
        for depth, cell in enumerate(row[: len(levels)]):
            name = _str(cell, 120)
            if not name:
                break
            key = (parent, name.casefold())
            if key not in known:
                ref = f"new:{len(out)}"
                out.append({"ref": ref, "parent_ref": parent, "name": name, "level": depth})
                known[key] = ref
            parent = known[key]
    return out


def descendants(places: list[dict[str, Any]], place_id: str) -> set[str]:
    out: set[str] = set()
    frontier = [place_id]
    while frontier:
        current = frontier.pop()
        for p in places:
            if p.get("parent_id") == current and p["id"] not in out:
                out.add(p["id"])
                frontier.append(p["id"])
    return out


# ----- partners ----------------------------------------------------------------


def validate_partner(spec: Any, place_ids: set[str]) -> dict[str, Any]:
    if not isinstance(spec, dict):
        raise _err("The partner must be an object", "partner_invalid")
    name = _str(spec.get("name"), 160)
    if not name:
        raise _err("The partner needs a name", "field_required", field="name")
    role = spec.get("role") if spec.get("role") in ROLES else "implementing"
    places = [p for p in spec.get("place_ids") or [] if isinstance(p, str) and p in place_ids]
    out = {
        "name": name,
        "acronym": _str(spec.get("acronym"), 30),
        "role": role,
        "contact": _str(spec.get("contact"), 200),
        "place_ids": list(dict.fromkeys(places)),
        "start": "",
        "end": "",
        "note": _str(spec.get("note"), 2000),
    }
    for key in ("start", "end"):
        if spec.get(key):
            out[key] = parse_date(spec[key], key).isoformat()
    if out["start"] and out["end"] and out["end"] < out["start"]:
        raise _err("The agreement ends before it starts", "dates_order")
    return out


# ----- disaggregations -----------------------------------------------------------


def _cats(*items: tuple[str, str, str]) -> list[dict[str, str]]:
    return [{"code": c, "fr": fr, "en": en} for c, fr, en in items]


PRESETS: dict[str, dict[str, Any]] = {
    "sex": {
        "name_fr": "Sexe",
        "name_en": "Sex",
        "categories": _cats(("f", "Femme", "Female"), ("m", "Homme", "Male")),
    },
    # Age bands used by most humanitarian and health reporting.
    "age": {
        "name_fr": "Tranche d'âge",
        "name_en": "Age group",
        "categories": _cats(
            ("0-4", "0 à 4 ans", "0 to 4 years"),
            ("5-17", "5 à 17 ans", "5 to 17 years"),
            ("18-59", "18 à 59 ans", "18 to 59 years"),
            ("60+", "60 ans et plus", "60 years and over"),
        ),
    },
    # Finer bands for health programmes (immunisation, HIV, nutrition).
    "age_health": {
        "name_fr": "Tranche d'âge (santé)",
        "name_en": "Age group (health)",
        "categories": _cats(
            ("0-11m", "0 à 11 mois", "0 to 11 months"),
            ("12-59m", "12 à 59 mois", "12 to 59 months"),
            ("5-9", "5 à 9 ans", "5 to 9 years"),
            ("10-14", "10 à 14 ans", "10 to 14 years"),
            ("15-19", "15 à 19 ans", "15 to 19 years"),
            ("20-24", "20 à 24 ans", "20 to 24 years"),
            ("25-49", "25 à 49 ans", "25 to 49 years"),
            ("50+", "50 ans et plus", "50 years and over"),
        ),
    },
    # Washington Group short set: a person with a lot of difficulty, or who cannot
    # do at all, in at least one domain.
    "disability": {
        "name_fr": "Handicap",
        "name_en": "Disability",
        "categories": _cats(("yes", "Avec handicap", "With disability"), ("no", "Sans handicap", "Without disability")),
    },
    "status": {
        "name_fr": "Statut de résidence",
        "name_en": "Displacement status",
        "categories": _cats(
            ("host", "Communauté hôte", "Host community"),
            ("idp", "Déplacé interne", "Internally displaced"),
            ("refugee", "Réfugié", "Refugee"),
            ("returnee", "Retourné", "Returnee"),
        ),
    },
    "area": {
        "name_fr": "Milieu",
        "name_en": "Area",
        "categories": _cats(("urban", "Urbain", "Urban"), ("rural", "Rural", "Rural")),
    },
}


def validate_disaggregation(spec: Any, existing: list[dict[str, Any]], own_id: str | None = None) -> dict[str, Any]:
    if not isinstance(spec, dict):
        raise _err("The disaggregation must be an object", "disaggregation_invalid")
    preset = spec.get("preset")
    if preset:
        if preset not in PRESETS:
            raise _err(f"Unknown disaggregation: {preset}", "disaggregation_invalid")
        spec = {**PRESETS[preset], **{k: v for k, v in spec.items() if k != "preset"}, "key": preset}
    name_fr = _str(spec.get("name_fr"), 80)
    if not name_fr:
        raise _err("The disaggregation needs a name", "field_required", field="name_fr")
    key = _str(spec.get("key"), 30) or slug(name_fr) or "d"
    if any(d.get("key") == key and d["id"] != own_id for d in existing):
        raise _err(f"The disaggregation {name_fr} already exists", "disaggregation_duplicate", name=name_fr)
    cats = []
    seen: set[str] = set()
    for c in spec.get("categories") or []:
        if not isinstance(c, dict):
            continue
        fr = _str(c.get("fr"), 80)
        if not fr:
            continue
        code = _str(c.get("code"), 30) or slug(fr)
        if not CODE.match(code) or code == UNSPECIFIED["code"]:
            raise _err(f"Invalid category code: {code}", "category_code_invalid", code=code)
        if code in seen:
            raise _err(f"Two categories have the code {code}", "category_code_duplicate", code=code)
        seen.add(code)
        cats.append({"code": code, "fr": fr, "en": _str(c.get("en"), 80) or fr})
    if len(cats) < 2:
        raise _err("A disaggregation has at least two categories", "categories_too_few")
    if len(cats) > 60:
        raise _err("A disaggregation has at most 60 categories", "categories_too_many")
    return {"key": key, "name_fr": name_fr, "name_en": _str(spec.get("name_en"), 80) or name_fr, "categories": cats}


def with_unspecified(d: dict[str, Any]) -> list[dict[str, str]]:
    return [*d["categories"], dict(UNSPECIFIED)]
