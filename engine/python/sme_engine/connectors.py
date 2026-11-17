# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 GAYI Komi Selassi and SANOUSSI Moudjibou

"""Data from servers: KoboToolbox, ODK Central and DHIS2 (section M6, channels 3 and 4).

A connection is kept in the project without its secret:

    {"kind": "kobo" | "odk" | "dhis2", "name": "...", "url": "https://kf.kobotoolbox.org",
     "username": "...", "form": {"uid": "..."} or {"project_id": 3, "form_id": "..."},
     "dataset_id": "...", "syncs": [{"at": "...", "rows": 120}]}

The token or password never enters the project file: the application keeps it
encrypted on the computer and hands it to each call (`secret`).

Kobo and ODK submissions become a dataset, with the questionnaire's labels, and
go through the same cleaning and calculations as an imported file. DHIS2
aggregate values become submissions of the matching periods and places, to be
checked and validated like any other.
"""

from __future__ import annotations

import base64
import json
import urllib.error
import urllib.parse
import urllib.request
from datetime import date
from typing import Any

import polars as pl

from .rpc import INVALID_PARAMS, RpcError

KINDS = ("kobo", "odk", "dhis2")
TIMEOUT = 60
PAGE = 1000
MAX_ROWS = 2_000_000


def _err(message: str, key: str, **info: Any) -> RpcError:
    return RpcError(message, INVALID_PARAMS, data={"key": key, **info})


def clean_url(url: Any) -> str:
    text = str(url or "").strip().rstrip("/")
    parsed = urllib.parse.urlparse(text)
    # Plain http only for a server on this computer (tests, a local DHIS2).
    local = parsed.hostname in ("localhost", "127.0.0.1")
    if parsed.scheme not in ("https", "http") or not parsed.netloc or (parsed.scheme == "http" and not local):
        raise _err("The server address must start with https://", "server_url_invalid")
    return text


def validate(spec: Any) -> dict[str, Any]:
    if not isinstance(spec, dict) or spec.get("kind") not in KINDS:
        raise _err("Unknown kind of server", "invalid_params")
    form = spec.get("form") if isinstance(spec.get("form"), dict) else {}
    out = {
        "kind": spec["kind"],
        "name": str(spec.get("name") or "").strip()[:120] or spec["kind"],
        "url": clean_url(spec.get("url")),
        "username": str(spec.get("username") or "").strip()[:200],
        "form": {k: str(v)[:200] for k, v in form.items() if k in ("uid", "project_id", "form_id", "name")},
        "dataset_id": str(spec.get("dataset_id") or "")[:40],
        "syncs": list(spec.get("syncs") or [])[-20:],
    }
    return out


# ----- HTTP ------------------------------------------------------------------------------------


def _request(url: str, headers: dict[str, str], body: dict[str, Any] | None = None, raw: bool = False) -> Any:
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, data=data, method="POST" if body is not None else "GET")
    req.add_header("Accept", "application/json")
    if body is not None:
        req.add_header("Content-Type", "application/json")
    for k, v in headers.items():
        req.add_header(k, v)
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:  # noqa: S310 - https enforced by clean_url
            payload = resp.read()
    except urllib.error.HTTPError as exc:
        if exc.code in (401, 403):
            raise _err("The server refused the identifiers", "server_auth", status=exc.code) from None
        if exc.code == 404:
            raise _err("Not found on the server", "server_not_found", status=exc.code) from None
        raise _err(f"The server answered {exc.code}", "server_error", status=exc.code) from None
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        raise _err(f"The server cannot be reached: {exc}", "server_unreachable") from None
    if raw:
        return payload
    try:
        return json.loads(payload.decode("utf-8"))
    except ValueError:
        raise _err("The server did not answer in JSON", "server_error") from None


def _secret(secret: Any) -> str:
    if not isinstance(secret, str) or not secret:
        raise _err("The token or password of this server is missing", "server_secret_missing")
    return secret


def _flatten(record: dict[str, Any], prefix: str = "") -> dict[str, str | None]:
    """Nested groups become "group/question"; lists are kept as JSON text."""
    out: dict[str, str | None] = {}
    for k, v in record.items():
        name = f"{prefix}{k}"
        if isinstance(v, dict):
            out.update(_flatten(v, f"{name}/"))
        elif isinstance(v, list):
            out[name] = json.dumps(v, ensure_ascii=False) if v else None
        elif v is None:
            out[name] = None
        else:
            out[name] = str(v)
    return out


def _frame(records: list[dict[str, str | None]]) -> pl.DataFrame:
    columns: list[str] = []
    seen: set[str] = set()
    for r in records:
        for k in r:
            if k not in seen:
                seen.add(k)
                columns.append(k)
    return pl.DataFrame({c: [r.get(c) for r in records] for c in columns}, schema={c: pl.String for c in columns})


# ----- KoboToolbox -------------------------------------------------------------------------------


def _kobo_headers(secret: Any) -> dict[str, str]:
    return {"Authorization": f"Token {_secret(secret)}"}


def kobo_forms(url: str, secret: Any) -> list[dict[str, Any]]:
    """The deployed forms the account can see."""
    out = []
    nxt: str | None = f"{clean_url(url)}/api/v2/assets/?asset_type=survey&format=json&limit=200"
    while nxt and len(out) < 2000:
        page = _request(nxt, _kobo_headers(secret))
        for a in page.get("results", []):
            if a.get("asset_type", "survey") == "survey":
                out.append(
                    {
                        "uid": a.get("uid"),
                        "name": a.get("name") or a.get("uid"),
                        "submissions": a.get("deployment__submission_count"),
                        "deployed": bool(a.get("has_deployment", True)),
                    }
                )
        nxt = page.get("next")
    return out


# Kobo's own fields that say nothing about the person interviewed.
KOBO_SKIP = (
    "_attachments",
    "_notes",
    "_tags",
    "_geolocation",
    "_validation_status",
    "_status",
    "__version__",
    "_xform_id_string",
    "_bamboo_dataset_id",
    "meta/rootUuid",
    "formhub/uuid",
    "_supplementalDetails",
)


def kobo_fetch(url: str, secret: Any, uid: str) -> tuple[pl.DataFrame, dict[str, Any]]:
    """All submissions of a form, and its questionnaire (for labels)."""
    base = f"{clean_url(url)}/api/v2/assets/{urllib.parse.quote(uid)}"
    asset = _request(f"{base}/?format=json", _kobo_headers(secret))
    records = []
    nxt: str | None = f"{base}/data/?format=json&limit={PAGE}"
    while nxt:
        page = _request(nxt, _kobo_headers(secret))
        for r in page.get("results", []):
            rec = {k: v for k, v in r.items() if k not in KOBO_SKIP}
            records.append(_flatten(rec))
        if len(records) > MAX_ROWS:
            raise _err("Too many submissions", "too_many_rows")
        nxt = page.get("next")
    return _frame(records), asset.get("content") or {}


# ----- ODK Central -----------------------------------------------------------------------------------


def _odk_headers(url: str, username: str, secret: Any) -> dict[str, str]:
    session = _request(f"{clean_url(url)}/v1/sessions", {}, {"email": username, "password": _secret(secret)})
    return {"Authorization": f"Bearer {session['token']}"}


def odk_forms(url: str, username: str, secret: Any, project_id: Any) -> list[dict[str, Any]]:
    headers = _odk_headers(url, username, secret)
    headers["X-Extended-Metadata"] = "true"
    base = clean_url(url)
    if not project_id:
        return [{"project_id": str(p["id"]), "name": p.get("name")} for p in _request(f"{base}/v1/projects", headers)]
    pid = urllib.parse.quote(str(project_id))
    return [
        {
            "form_id": f.get("xmlFormId"),
            "name": f.get("name") or f.get("xmlFormId"),
            "submissions": f.get("submissions"),
        }
        for f in _request(f"{base}/v1/projects/{pid}/forms", headers)
    ]


def odk_fetch(url: str, username: str, secret: Any, project_id: Any, form_id: str) -> tuple[pl.DataFrame, bytes | None]:
    """Submissions of a form through the OData feed (repeat groups are left out),
    and the questionnaire as an XLSForm file when one was uploaded."""
    headers = _odk_headers(url, username, secret)
    base = f"{clean_url(url)}/v1/projects/{urllib.parse.quote(str(project_id))}/forms/{urllib.parse.quote(form_id)}"
    records = []
    skip = 0
    while True:
        page = _request(f"{base}.svc/Submissions?$top={PAGE}&$skip={skip}&$count=true", headers)
        rows = page.get("value", [])
        for r in rows:
            system = r.pop("__system", {}) or {}
            rec = _flatten({k: v for k, v in r.items() if not k.endswith("@odata.navigationLink")})
            rec["_submission_time"] = system.get("submissionDate")
            rec["_review_state"] = system.get("reviewState")
            records.append(rec)
        skip += len(rows)
        if not rows or skip >= int(page.get("@odata.count") or 0) or skip > MAX_ROWS:
            break
    try:
        xlsx = _request(f"{base}.xlsx", headers, raw=True)
    except RpcError:
        xlsx = None
    return _frame(records), xlsx


# ----- DHIS2 -----------------------------------------------------------------------------------------


def _dhis2_headers(username: str, secret: Any) -> dict[str, str]:
    token = _secret(secret)
    if username:
        basic = base64.b64encode(f"{username}:{token}".encode()).decode()
        return {"Authorization": f"Basic {basic}"}
    return {"Authorization": f"ApiToken {token}"}


def dhis2_search(url: str, username: str, secret: Any, what: str, query: str) -> list[dict[str, Any]]:
    """Data elements, indicators or organisation units whose name contains the text."""
    endpoint = {"data": "dataElements", "indicators": "indicators", "places": "organisationUnits"}.get(what)
    if endpoint is None:
        raise _err("Unknown kind of DHIS2 object", "invalid_params")
    fields = "id,displayName,level" if what == "places" else "id,displayName"
    q = urllib.parse.quote(str(query or "")[:100])
    page = _request(
        f"{clean_url(url)}/api/{endpoint}.json?fields={fields}&pageSize=50&filter=displayName:ilike:{q}",
        _dhis2_headers(username, secret),
    )
    return [
        {"id": o["id"], "name": o.get("displayName"), **({"level": o.get("level")} if what == "places" else {})}
        for o in page.get(endpoint, [])
    ]


def dhis2_periods(period: dict[str, Any], additive: bool) -> list[str]:
    """DHIS2 period identifiers that make up a project period.

    Values that add up (counts) are read month by month and added; the others
    (rates, percentages computed by DHIS2) need the period itself, so the project
    period must be a calendar month, quarter, half-year or year."""
    start, end = date.fromisoformat(period["start"]), date.fromisoformat(period["end"])
    months = []
    y, m = start.year, start.month
    while (y, m) <= (end.year, end.month):
        months.append(f"{y}{m:02d}")
        m += 1
        if m == 13:
            y, m = y + 1, 1
    if additive:
        return months
    n = len(months)
    if n == 1:
        return months
    if n == 3 and start.month in (1, 4, 7, 10):
        return [f"{start.year}Q{(start.month - 1) // 3 + 1}"]
    if n == 6 and start.month in (1, 7):
        return [f"{start.year}S{1 if start.month == 1 else 2}"]
    if n == 12 and start.month == 1:
        return [str(start.year)]
    raise _err(
        "This DHIS2 value does not add up and the period is not a calendar month, quarter, half-year or year",
        "dhis2_period_unaligned",
        period=period["code"],
    )


def dhis2_fetch(
    url: str, username: str, secret: Any, dx: list[str], pe: list[str], ou: list[str]
) -> list[tuple[str, str, str, float]]:
    """(data element or indicator, period, organisation unit, value) from the analytics API."""
    if not dx or not pe or not ou:
        return []
    out = []
    for i in range(0, len(ou), 50):
        chunk = ou[i : i + 50]
        query = (
            f"dimension=dx:{';'.join(dx)}&dimension=pe:{';'.join(pe)}&dimension=ou:{';'.join(chunk)}"
            "&skipMeta=true&displayProperty=NAME"
        )
        page = _request(f"{clean_url(url)}/api/analytics.json?{query}", _dhis2_headers(username, secret))
        names = [h["name"] for h in page.get("headers", [])]
        idx = {n: names.index(n) for n in ("dx", "pe", "ou", "value") if n in names}
        if len(idx) < 4:
            continue
        for row in page.get("rows", []):
            try:
                out.append((row[idx["dx"]], row[idx["pe"]], row[idx["ou"]], float(row[idx["value"]])))
            except (TypeError, ValueError):
                continue
    return out
