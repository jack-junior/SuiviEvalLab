# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 GAYI Komi Selassi and SANOUSSI Moudjibou

"""Places from maps: administrative divisions and searching a site (geo.py), with
the map services replaced by files written here."""

from __future__ import annotations

import io
import json

import pytest

from sme_engine import geo
from sme_engine.methods import register
from sme_engine.r_bridge import RBridge
from sme_engine.rpc import Server


def square(x0, y0, x1, y1):
    return [[[x0, y0], [x1, y0], [x1, y1], [x0, y1], [x0, y0]]]


def feature(name, gid, rings, multi=False):
    geometry = {"type": "MultiPolygon", "coordinates": [rings]} if multi else {"type": "Polygon", "coordinates": rings}
    return {"type": "Feature", "properties": {"shapeName": name, "shapeID": gid}, "geometry": geometry}


ADM1 = {
    "type": "FeatureCollection",
    "features": [feature("Savanes", "R1", square(0, 5, 2, 10)), feature("Maritime", "R2", square(0, 0, 2, 5))],
}
ADM2 = {
    "type": "FeatureCollection",
    "features": [
        feature("Tône", "D1", square(0, 5, 1, 10)),
        # An L-shaped district, whose centre is outside it.
        feature("Kpendjal", "D2", [[[1, 5], [2, 5], [2, 10], [1.2, 10], [1.2, 6], [1, 6], [1, 5]]], multi=True),
        feature("Golfe", "D3", square(0, 0, 2, 5)),
        feature("", "D4", square(5, 5, 6, 6)),  # no name: left out
    ],
}


@pytest.fixture()
def maps(monkeypatch, tmp_path):
    monkeypatch.setenv("SME_TRUST_DIR", str(tmp_path / "trust"))
    asked: list[str] = []

    def fetch(url, accept="application/json"):
        asked.append(url)
        if "/ALL/" in url:
            return json.dumps([{"boundaryType": "ADM1"}, {"boundaryType": "ADM2"}, {"boundaryType": "ADM0"}]).encode()
        if "/ADM1/" in url:
            return json.dumps({"simplifiedGeometryGeoJSON": "https://files.example/adm1.geojson"}).encode()
        if "/ADM2/" in url:
            return json.dumps({"gjDownloadURL": "https://files.example/adm2.geojson"}).encode()
        if url.endswith("adm1.geojson"):
            return json.dumps(ADM1).encode()
        if url.endswith("adm2.geojson"):
            return json.dumps(ADM2).encode()
        if url.startswith(geo.NOMINATIM):
            assert "countrycodes=tg" in url
            return json.dumps(
                [
                    {"name": "Dapaong", "display_name": "Dapaong, Tône, Savanes, Togo", "lat": "7.5", "lon": "0.5"},
                    {"display_name": "sans position"},
                ]
            ).encode()
        raise AssertionError(url)

    monkeypatch.setattr(geo, "fetch", fetch)
    return asked


@pytest.fixture()
def call():
    bridge = RBridge()
    server = Server(stdin=io.StringIO(), stdout=io.StringIO())
    register(server, bridge)

    def _call(method, params=None):
        resp = server.handle_line(json.dumps({"jsonrpc": "2.0", "id": 1, "method": method, "params": params or {}}))
        if "error" in resp:
            raise RuntimeError(resp["error"]["data"]["key"])
        return resp["result"]

    yield _call
    bridge.stop()


def test_tree_places_each_division_under_the_one_containing_it(maps):
    assert geo.levels_available("tgo") == [1, 2]
    items = geo.tree("TGO", 2)
    parents = {i["name"]: i["parent_gid"] for i in items}
    assert parents == {"Maritime": "", "Savanes": "", "Golfe": "R2", "Kpendjal": "R1", "Tône": "R1"}
    assert [i["level"] for i in items] == [0, 0, 1, 1, 1]
    # Kept on this computer: asked again without the network.
    n = len(maps)
    assert len(geo.tree("TGO", 2)) == 5 and len(maps) == n
    assert geo.locate("TGO", 3, lat=7.0, lon=1.5) == ["R1", "D2"]
    assert geo.locate("TGO", 2, lat=5.5, lon=1.1) == ["R1", "D2"]  # in the foot of the L
    assert geo.locate("TGO", 2, lat=7.0, lon=1.1) == ["R1"]  # in its notch: no district
    assert geo.locate("TGO", 2, lat=20.0, lon=1.0) == []


def test_import_into_a_project_and_place_a_site_from_the_map(maps, call, tmp_path):
    call("project.create", {"path": str(tmp_path / "geo.sme"), "name": "Carte"})
    countries = call("geo.countries")["countries"]
    assert next(c for c in countries if c["iso3"] == "TGO")["fr"] == "Togo"
    assert call("geo.levels", {"iso": "TGO"})["levels"] == [1, 2]
    assert call("geo.preview", {"iso": "TGO", "depth": 2})["counts"] == [2, 3]
    # A district typed by hand before the import is kept and linked.
    savanes = call("place.save", {"place": {"name": "SAVANES"}})["created"]
    snap = call("geo.import", {"iso": "TGO", "depth": 2})
    assert snap["added"] == 4
    names = {p["name"]: p for p in snap["places"]}
    assert names["SAVANES"]["geo_id"] == "R1"
    assert names["Kpendjal"]["parent_id"] == savanes
    assert call("geo.import", {"iso": "tgo", "depth": 2})["added"] == 0  # again: nothing doubled
    with pytest.raises(RuntimeError, match="geo_too_deep"):
        call("geo.import", {"iso": "TGO", "depth": 5})

    found = call("geo.search", {"q": "Dapaong"})["results"]
    assert found == [{"name": "Dapaong", "label": "Dapaong, Tône, Savanes, Togo", "kind": "", "lat": 7.5, "lon": 0.5}]
    where = call("geo.locate", {"lat": 7.5, "lon": 0.5})["place_id"]
    assert where == names["Tône"]["id"]
    snap = call("place.save", {"place": {"name": "Dapaong", "parent_id": where, "lat": 7.5, "lon": 0.5}})
    site = next(p for p in snap["places"] if p["name"] == "Dapaong")
    assert (site["lat"], site["lon"], site["level"]) == (7.5, 0.5, 2)
    with pytest.raises(RuntimeError, match="place_position_invalid"):
        call("place.save", {"place": {"name": "Ailleurs", "lat": 95, "lon": 0}})


def test_unreachable_service_is_reported(monkeypatch, tmp_path):
    monkeypatch.setenv("SME_TRUST_DIR", str(tmp_path))
    with pytest.raises(geo.RpcError) as exc:
        geo.fetch("http://example.org")
    assert exc.value.data["key"] == "geo_unreachable"
    with pytest.raises(geo.RpcError) as exc:
        geo.tree("Togo", 1)
    assert exc.value.data["key"] == "geo_country_invalid"
