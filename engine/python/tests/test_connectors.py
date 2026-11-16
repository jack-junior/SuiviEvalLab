# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 GAYI Komi Selassi and SANOUSSI Moudjibou

"""Kobo, ODK Central and DHIS2, against a local server answering like them."""

from __future__ import annotations

import io
import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

import pytest

from sme_engine.methods import register
from sme_engine.r_bridge import RBridge
from sme_engine.rpc import Server

KOBO_TOKEN = "kobo-secret"
ODK_PASSWORD = "odk-secret"
DHIS2_TOKEN = "d2pat_secret"

KOBO_CONTENT = {
    "translations": ["Français (fr)", "English (en)"],
    "survey": [
        {"type": "begin_group", "name": "menage"},
        {"type": "integer", "name": "taille", "label": ["Taille du ménage", "Household size"]},
        {"type": "select_one", "select_from_list_name": "yn", "name": "ecole", "label": ["École à 2 km", "School"]},
        {"type": "end_group"},
    ],
    "choices": [
        {"list_name": "yn", "name": "oui", "label": ["Oui", "Yes"]},
        {"list_name": "yn", "name": "non", "label": ["Non", "No"]},
    ],
}
KOBO_DATA = [
    {"_id": 1, "menage/taille": "5", "menage/ecole": "oui", "_attachments": [], "_submission_time": "2026-02-01"},
    {"_id": 2, "menage/taille": "3", "menage/ecole": "non", "_attachments": [], "_submission_time": "2026-02-02"},
    {"_id": 3, "menage/taille": "8", "menage/ecole": "oui", "_attachments": [], "_submission_time": "2026-02-03"},
]

ODK_ROWS = [
    {
        "__id": "uuid:1",
        "identite": {"age": 30, "sexe": "f"},
        "__system": {"submissionDate": "2026-03-01", "reviewState": None},
    },
    {
        "__id": "uuid:2",
        "identite": {"age": 41, "sexe": "m"},
        "__system": {"submissionDate": "2026-03-02", "reviewState": "approved"},
    },
]

# DHIS2 values by (element, period, organisation unit).
DHIS2 = {
    ("deVacc", "202601", "ouKara"): 10,
    ("deVacc", "202602", "ouKara"): 12,
    ("deVacc", "202603", "ouKara"): 8,
    ("deVacc", "202601", "ouLome"): 5,
    ("deVacc", "202602", "ouLome"): 5,
    ("deVacc", "202603", "ouLome"): 5,
    ("inCover", "2026Q1", "ouKara"): 82.5,
    ("inCover", "2026Q1", "ouLome"): 91.0,
}


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *args):  # quiet
        pass

    def _send(self, code: int, body):
        data = body if isinstance(body, bytes) else json.dumps(body).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(data)

    def do_POST(self):  # noqa: N802
        n = int(self.headers.get("Content-Length") or 0)
        body = json.loads(self.rfile.read(n) or b"{}")
        if self.path == "/v1/sessions":
            if body.get("password") != ODK_PASSWORD:
                return self._send(401, {"message": "bad"})
            return self._send(200, {"token": "odk-session"})
        self._send(404, {})

    def do_GET(self):  # noqa: N802
        url = urlparse(self.path)
        q = parse_qs(url.query)
        auth = self.headers.get("Authorization", "")
        if url.path.startswith("/api/v2/"):
            if auth != f"Token {KOBO_TOKEN}":
                return self._send(401, {})
            if url.path == "/api/v2/assets/":
                return self._send(
                    200,
                    {
                        "next": None,
                        "results": [
                            {
                                "uid": "aForm1",
                                "name": "Enquête ménages",
                                "asset_type": "survey",
                                "deployment__submission_count": 3,
                                "has_deployment": True,
                            }
                        ],
                    },
                )
            if url.path == "/api/v2/assets/aForm1/":
                return self._send(200, {"uid": "aForm1", "content": KOBO_CONTENT})
            if url.path == "/api/v2/assets/aForm1/data/":
                start = int(q.get("start", ["0"])[0])
                page = KOBO_DATA[start : start + 2]
                nxt = f"http://{self.headers['Host']}/api/v2/assets/aForm1/data/?format=json&limit=2&start={start + 2}"
                return self._send(200, {"results": page, "next": nxt if start + 2 < len(KOBO_DATA) else None})
        if url.path.startswith("/v1/"):
            if auth != "Bearer odk-session":
                return self._send(401, {})
            if url.path == "/v1/projects":
                return self._send(200, [{"id": 7, "name": "Projet ODK"}])
            if url.path == "/v1/projects/7/forms":
                return self._send(200, [{"xmlFormId": "registre", "name": "Registre", "submissions": 2}])
            if url.path == "/v1/projects/7/forms/registre.svc/Submissions":
                skip = int(q.get("$skip", ["0"])[0])
                return self._send(200, {"value": ODK_ROWS[skip:], "@odata.count": len(ODK_ROWS)})
            if url.path == "/v1/projects/7/forms/registre.xlsx":
                return self._send(404, {})
        if url.path.startswith("/api/"):
            if auth != f"ApiToken {DHIS2_TOKEN}":
                return self._send(401, {})
            if url.path == "/api/organisationUnits.json":
                return self._send(200, {"organisationUnits": [{"id": "ouKara", "displayName": "Kara", "level": 2}]})
            if url.path == "/api/analytics.json":
                dims = dict(d.split(":", 1) for d in q["dimension"])
                rows = [
                    [dx, pe, ou, str(v)]
                    for (dx, pe, ou), v in DHIS2.items()
                    if dx in dims["dx"].split(";") and pe in dims["pe"].split(";") and ou in dims["ou"].split(";")
                ]
                return self._send(
                    200, {"headers": [{"name": "dx"}, {"name": "pe"}, {"name": "ou"}, {"name": "value"}], "rows": rows}
                )
        self._send(404, {})


@pytest.fixture()
def server(monkeypatch):
    monkeypatch.setenv("NO_PROXY", "127.0.0.1,localhost")
    monkeypatch.setenv("no_proxy", "127.0.0.1,localhost")
    httpd = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    yield f"http://127.0.0.1:{httpd.server_address[1]}"
    httpd.shutdown()


@pytest.fixture()
def call():
    bridge = RBridge()
    srv = Server(stdin=io.StringIO(), stdout=io.StringIO())
    register(srv, bridge)

    def _call(method, params=None):
        resp = srv.handle_line(json.dumps({"jsonrpc": "2.0", "id": 1, "method": method, "params": params or {}}))
        if "error" in resp:
            raise RuntimeError(resp["error"]["data"]["key"] + ": " + resp["error"]["message"])
        return resp["result"]

    yield _call
    bridge.stop()


def test_server_address_must_be_https(call, tmp_path):
    call("project.create", {"path": str(tmp_path / "p.sme"), "name": "P"})
    with pytest.raises(RuntimeError, match="server_url_invalid"):
        call("connection.save", {"connection": {"kind": "kobo", "url": "http://kf.kobotoolbox.org"}})
    snap = call("connection.save", {"connection": {"kind": "kobo", "url": "https://kf.kobotoolbox.org/"}})
    assert snap["connections"][0]["url"] == "https://kf.kobotoolbox.org"


def test_kobo_forms_and_sync_into_a_dataset(call, tmp_path, server):
    call("project.create", {"path": str(tmp_path / "p.sme"), "name": "P"})
    cid = call("connection.save", {"connection": {"kind": "kobo", "name": "Kobo", "url": server}})["created"]
    with pytest.raises(RuntimeError, match="server_secret_missing"):
        call("connection.forms", {"connection_id": cid})
    with pytest.raises(RuntimeError, match="server_auth"):
        call("connection.forms", {"connection_id": cid, "secret": "wrong"})
    forms = call("connection.forms", {"connection_id": cid, "secret": KOBO_TOKEN})["forms"]
    assert forms == [{"uid": "aForm1", "name": "Enquête ménages", "submissions": 3, "deployed": True}]
    call(
        "connection.save",
        {
            "id": cid,
            "connection": {
                "kind": "kobo",
                "name": "Kobo",
                "url": server,
                "form": {"uid": "aForm1", "name": "Enquête ménages"},
            },
        },
    )
    res = call("connection.sync", {"connection_id": cid, "secret": KOBO_TOKEN, "round": "baseline"})
    assert res["rows"] == 3  # two pages read
    ds = next(d for d in res["datasets"] if d["id"] == res["dataset_id"])
    assert ds["name"] == "Enquête ménages" and ds["round"] == "baseline"
    names = [c["name"] for c in ds["columns"]]
    assert "menage/taille" in names and "_attachments" not in names
    assert ds["labels"]["columns"]["menage/taille"]["fr"] == "Taille du ménage"
    assert ds["labels"]["values"]["menage/ecole"]["oui"]["en"] == "Yes"
    # A second sync replaces the data of the same dataset and is listed.
    KOBO_DATA.append({"_id": 4, "menage/taille": "2", "menage/ecole": "non", "_submission_time": "2026-02-05"})
    try:
        res = call("connection.sync", {"connection_id": cid, "secret": KOBO_TOKEN})
    finally:
        KOBO_DATA.pop()
    assert res["rows"] == 4 and len(res["datasets"]) == 1
    conn = next(c for c in res["connections"] if c["id"] == cid)
    assert [s["rows"] for s in conn["syncs"]] == [3, 4] and "secret" not in json.dumps(conn)
    rows = call("dataset.rows", {"id": res["dataset_id"], "offset": 0, "limit": 10})
    assert len(rows["rows"]) == 4


def test_odk_central(call, tmp_path, server):
    call("project.create", {"path": str(tmp_path / "p.sme"), "name": "P"})
    cid = call("connection.save", {"connection": {"kind": "odk", "url": server, "username": "me@ong.org"}})["created"]
    with pytest.raises(RuntimeError, match="server_auth"):
        call("connection.forms", {"connection_id": cid, "secret": "bad"})
    assert call("connection.forms", {"connection_id": cid, "secret": ODK_PASSWORD})["forms"] == [
        {"project_id": "7", "name": "Projet ODK"}
    ]
    forms = call("connection.forms", {"connection_id": cid, "secret": ODK_PASSWORD, "project_id": "7"})["forms"]
    assert forms[0]["form_id"] == "registre"
    call(
        "connection.save",
        {
            "id": cid,
            "connection": {
                "kind": "odk",
                "url": server,
                "username": "me@ong.org",
                "form": {"project_id": "7", "form_id": "registre"},
            },
        },
    )
    res = call("connection.sync", {"connection_id": cid, "secret": ODK_PASSWORD})
    ds = next(d for d in res["datasets"] if d["id"] == res["dataset_id"])
    names = [c["name"] for c in ds["columns"]]
    assert {"identite/age", "identite/sexe", "_submission_time", "_review_state"} <= set(names)
    assert res["rows"] == 2


def test_dhis2_values_into_submissions(call, tmp_path, server):
    call(
        "project.create",
        {
            "path": str(tmp_path / "p.sme"),
            "name": "P",
            "profile": {"start": "2026-01-01", "end": "2026-12-31", "frequency": "quarterly"},
        },
    )
    node = call("framework.add", {"title": "Effet"})["created"]
    vacc = call(
        "indicator.save",
        {
            "node_id": node,
            "indicator": {"name": "Enfants vaccinés", "unit": "count", "source_type": "dhis2", "dhis2_id": "deVacc"},
        },
    )["saved"]
    cover = call(
        "indicator.save",
        {
            "node_id": node,
            "indicator": {"name": "Couverture", "unit": "percent", "source_type": "dhis2", "dhis2_id": "inCover"},
        },
    )["saved"]
    kara = call("place.save", {"place": {"name": "Kara", "code": "ouKara"}})["created"]
    lome = call("place.save", {"place": {"name": "Lomé", "code": "ouLome"}})["created"]
    cid = call("connection.save", {"connection": {"kind": "dhis2", "url": server}})["created"]
    found = call("dhis2.search", {"connection_id": cid, "secret": DHIS2_TOKEN, "what": "places", "query": "Kar"})
    assert found["results"] == [{"id": "ouKara", "name": "Kara", "level": 2}]
    res = call("dhis2.import", {"connection_id": cid, "secret": DHIS2_TOKEN, "periods": ["T1-2026"]})
    assert res["written"] == 2 and res["skipped"] == 0
    subs = {s["place_id"]: s for s in res["submissions"]}
    assert set(subs) == {kara, lome} and {s["status"] for s in subs.values()} == {"submitted"}
    assert subs[kara]["channel"] == "dhis2"
    detail = call("submission.get", {"id": subs[kara]["id"]})
    assert detail["cells"][vacc][""][0] == 30  # three months added
    assert detail["cells"][cover][""][0] == pytest.approx(0.825)  # DHIS2 percentages kept as shares
    for s in subs.values():
        call("submission.act", {"id": s["id"], "action": "validate"})
    row = next(
        r
        for r in call("tracking.table", {"period": "T1-2026", "today": "2026-04-15"})["rows"]
        if r["indicator_id"] == vacc
    )
    assert row["value_period"] == 45
    # Imported again once validated: left alone.
    res = call("dhis2.import", {"connection_id": cid, "secret": DHIS2_TOKEN, "periods": ["T1-2026"]})
    assert res["written"] == 0 and res["skipped"] == 2


def test_dhis2_periods():
    from sme_engine import connectors as cx

    q1 = {"code": "T1", "start": "2026-01-01", "end": "2026-03-31"}
    assert cx.dhis2_periods(q1, True) == ["202601", "202602", "202603"]
    assert cx.dhis2_periods(q1, False) == ["2026Q1"]
    fiscal = {"code": "T1-26-27", "start": "2026-07-01", "end": "2026-09-30"}
    assert cx.dhis2_periods(fiscal, False) == ["2026Q3"]
    odd = {"code": "P", "start": "2026-02-01", "end": "2026-04-30"}
    with pytest.raises(Exception, match="calendar month"):
        cx.dhis2_periods(odd, False)
    assert cx.dhis2_periods({"code": "Y", "start": "2026-01-01", "end": "2026-12-31"}, False) == ["2026"]
