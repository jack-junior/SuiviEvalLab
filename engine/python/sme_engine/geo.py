# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 GAYI Komi Selassi and SANOUSSI Moudjibou

"""Places from maps: the administrative divisions of a country, and searching a
site by its name.

Administrative divisions come from geoBoundaries (gbOpen release, CC BY 4.0,
William & Mary geoLab): one GeoJSON file per country and level. The files are
downloaded once and kept on this computer, so the divisions can be used again
offline. geoBoundaries does not say which region a district belongs to: a
division is placed under the division of the level above that contains it.

Sites are searched with Nominatim, the search engine of OpenStreetMap. Only the
typed name is sent. The service asks for one request per second at most and an
identified application: searches are made one at a time, when asked.
"""

from __future__ import annotations

import json
import os
import re
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

from .rpc import INVALID_PARAMS, RpcError

GB_API = "https://www.geoboundaries.org/api/current/gbOpen/{iso}/{level}/"
NOMINATIM = "https://nominatim.openstreetmap.org/search"
AGENT = "SuiviEvalLab/1.0 (+https://github.com/jack-junior/SuiviEvalLab)"
TIMEOUT = 60
ISO3 = re.compile(r"^[A-Z]{3}$")
MAX_LEVEL = 5


def _err(message: str, key: str, **info: Any) -> RpcError:
    return RpcError(message, INVALID_PARAMS, data={"key": key, **info})


def countries() -> list[dict[str, str]]:
    """ISO 3166 countries with their French and English names."""
    return json.loads((Path(__file__).parent / "data" / "countries.json").read_text(encoding="utf-8"))


def cache_dir() -> Path:
    env = os.environ.get("SME_TRUST_DIR")
    base = Path(env) if env else Path.home() / ".suivievallab"
    d = base / "geo"
    d.mkdir(parents=True, exist_ok=True)
    return d


# ----- HTTP (replaced in tests) ------------------------------------------------------------------


def fetch(url: str, accept: str = "application/json") -> bytes:
    """GET over https, with the application named as the services ask."""
    if not url.startswith("https://"):
        raise _err("Only https addresses are read", "geo_unreachable")
    req = urllib.request.Request(url, headers={"User-Agent": AGENT, "Accept": accept})
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:  # noqa: S310 - https checked above
            return resp.read()
    except urllib.error.HTTPError as exc:
        if exc.code == 404:
            raise _err("Not available for this country", "geo_not_found") from None
        raise _err(f"The map service answered {exc.code}", "geo_unreachable", status=exc.code) from None
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        raise _err(f"The map service cannot be reached: {exc}", "geo_unreachable") from None


# ----- administrative divisions ------------------------------------------------------------------


def _iso(value: Any) -> str:
    iso = str(value or "").strip().upper()
    if not ISO3.match(iso):
        raise _err("Unknown country", "geo_country_invalid")
    return iso


def boundaries(iso: Any, level: int) -> dict[str, Any]:
    """The GeoJSON of one level (1 = first level below the country), from the
    computer if it was downloaded before."""
    iso = _iso(iso)
    if not 1 <= int(level) <= MAX_LEVEL:
        raise _err("Unknown administrative level", "geo_level_invalid")
    target = cache_dir() / f"{iso}-ADM{int(level)}.geojson"
    if target.exists():
        try:
            return json.loads(target.read_text(encoding="utf-8"))
        except ValueError:
            target.unlink(missing_ok=True)
    meta = json.loads(fetch(GB_API.format(iso=iso, level=f"ADM{int(level)}")))
    if isinstance(meta, list):
        meta = meta[0] if meta else {}
    url = meta.get("simplifiedGeometryGeoJSON") or meta.get("gjDownloadURL")
    if not url:
        raise _err("Not available for this country", "geo_not_found")
    data = json.loads(fetch(url, "application/geo+json, application/json"))
    if not isinstance(data, dict) or not isinstance(data.get("features"), list):
        raise _err("The divisions could not be read", "geo_unreachable")
    tmp = target.with_suffix(".part")
    tmp.write_text(json.dumps(data), encoding="utf-8")
    tmp.replace(target)
    return data


def levels_available(iso: Any) -> list[int]:
    """Levels geoBoundaries has for a country (asked once, then kept)."""
    iso = _iso(iso)
    target = cache_dir() / f"{iso}-levels.json"
    if target.exists():
        try:
            return json.loads(target.read_text(encoding="utf-8"))
        except ValueError:
            pass
    meta = json.loads(fetch(GB_API.format(iso=iso, level="ALL")))
    items = meta if isinstance(meta, list) else [meta]
    out = sorted(
        {
            int(m["boundaryType"][3:])
            for m in items
            if isinstance(m, dict) and re.fullmatch(r"ADM[1-5]", str(m.get("boundaryType", "")))
        }
    )
    target.write_text(json.dumps(out), encoding="utf-8")
    return out


def _rings(geometry: dict[str, Any]) -> list[list[list[list[float]]]]:
    """Polygons of a geometry, each as [outer ring, holes...]."""
    kind = geometry.get("type")
    coords = geometry.get("coordinates") or []
    if kind == "Polygon":
        return [coords]
    if kind == "MultiPolygon":
        return list(coords)
    return []


def _in_ring(x: float, y: float, ring: list[list[float]]) -> bool:
    inside = False
    j = len(ring) - 1
    for i in range(len(ring)):
        xi, yi = ring[i][0], ring[i][1]
        xj, yj = ring[j][0], ring[j][1]
        if (yi > y) != (yj > y) and x < (xj - xi) * (y - yi) / ((yj - yi) or 1e-300) + xi:
            inside = not inside
        j = i
    return inside


class Shape:
    """A division: its name, identifier, polygons and their bounding box."""

    def __init__(self, feature: dict[str, Any]) -> None:
        props = feature.get("properties") or {}
        self.name = str(props.get("shapeName") or "").strip()[:120]
        self.gid = str(props.get("shapeID") or "").strip()[:60]
        self.polygons = _rings(feature.get("geometry") or {})
        xs = [pt[0] for poly in self.polygons for pt in poly[0]] if self.polygons else [0.0]
        ys = [pt[1] for poly in self.polygons for pt in poly[0]] if self.polygons else [0.0]
        self.box = (min(xs), min(ys), max(xs), max(ys))

    def contains(self, x: float, y: float) -> bool:
        x0, y0, x1, y1 = self.box
        if not (x0 <= x <= x1 and y0 <= y <= y1):
            return False
        for poly in self.polygons:
            if poly and _in_ring(x, y, poly[0]) and not any(_in_ring(x, y, hole) for hole in poly[1:]):
                return True
        return False

    def inner_point(self) -> tuple[float, float] | None:
        """A point inside the division (to find the division above it)."""
        if not self.polygons:
            return None
        outer = max((poly[0] for poly in self.polygons), key=len)
        cx = sum(p[0] for p in outer) / len(outer)
        cy = sum(p[1] for p in outer) / len(outer)
        if self.contains(cx, cy):
            return cx, cy
        # A concave shape: try points between the centre and each vertex.
        for p in outer[:: max(1, len(outer) // 50)]:
            for t in (0.5, 0.25, 0.75, 0.1, 0.9):
                x, y = cx + (p[0] - cx) * t, cy + (p[1] - cy) * t
                if self.contains(x, y):
                    return x, y
        return outer[0][0], outer[0][1]


def shapes(iso: Any, level: int) -> list[Shape]:
    return [s for s in (Shape(f) for f in boundaries(iso, level)["features"]) if s.name]


def tree(iso: Any, depth: int) -> list[dict[str, Any]]:
    """Divisions of levels 1 to depth, each with the identifier of the division
    above it: [{"gid", "name", "level" (0-based), "parent_gid"}], parents first."""
    if not 1 <= int(depth) <= MAX_LEVEL:
        raise _err("Unknown administrative level", "geo_level_invalid")
    out: list[dict[str, Any]] = []
    above: list[Shape] = []
    for level in range(1, int(depth) + 1):
        current = shapes(iso, level)
        for s in sorted(current, key=lambda s: s.name.casefold()):
            parent = ""
            if above:
                pt = s.inner_point()
                if pt is not None:
                    parent = next((a.gid for a in above if a.contains(*pt)), "")
                if not parent:
                    continue  # outside every division above (a gap in the data): left out
            out.append({"gid": s.gid, "name": s.name, "level": level - 1, "parent_gid": parent})
        above = current
    return out


def locate(iso: Any, depth: int, lat: float, lon: float) -> list[str]:
    """Identifiers of the divisions containing a point, from the top; only the
    levels already on this computer are read."""
    out: list[str] = []
    for level in range(1, int(depth) + 1):
        if not (cache_dir() / f"{_iso(iso)}-ADM{level}.geojson").exists():
            break
        hit = next((s for s in shapes(iso, level) if s.contains(lon, lat)), None)
        if hit is None:
            break
        out.append(hit.gid)
    return out


# ----- searching a site ---------------------------------------------------------------------------


def search(query: Any, country_iso2: str = "", lang: str = "fr") -> list[dict[str, Any]]:
    q = str(query or "").strip()[:200]
    if len(q) < 2:
        return []
    params = {"q": q, "format": "jsonv2", "limit": "8", "accept-language": "fr" if lang == "fr" else "en"}
    if re.fullmatch(r"[a-z]{2}", country_iso2 or ""):
        params["countrycodes"] = country_iso2
    data = json.loads(fetch(NOMINATIM + "?" + urllib.parse.urlencode(params)))
    out = []
    for item in data if isinstance(data, list) else []:
        try:
            lat, lon = float(item["lat"]), float(item["lon"])
        except (KeyError, TypeError, ValueError):
            continue
        out.append(
            {
                "name": str(item.get("name") or item.get("display_name", "")).strip()[:120],
                "label": str(item.get("display_name", "")).strip()[:300],
                "kind": str(item.get("type") or item.get("category") or "")[:40],
                "lat": round(lat, 6),
                "lon": round(lon, 6),
            }
        )
    return out
