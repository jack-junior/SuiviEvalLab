# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 GAYI Komi Selassi and SANOUSSI Moudjibou

"""Reception of data (section M6): submissions, their values and their statuses.

A submission is what one reporting unit sends for one period:

    {"period": "T1-2026", "place_id": "", "partner_id": "...", "channel": "entry",
     "status": "draft", "created_at": "...", "submitted_at": null, "validated_at": null,
     "comment": "", "source_ref": "", "history": [{"at": "...", "action": "submit", ...}]}

Statuses: draft, submitted, review (being checked), returned (sent back with a
comment), validated, locked (its period is locked). Values can be changed while
the submission is not validated; a validated one is reopened with a reason, and
that stays in its history.
"""

from __future__ import annotations

import json
import re
import sqlite3
import uuid
from datetime import UTC, date, datetime, timedelta
from typing import Any

from . import intake_checks, monitoring, schedule
from . import targets as targets_
from .monitoring import Scope
from .project import Project
from .rpc import INVALID_PARAMS, RpcError

ENTRY_SOURCES = ("routine", "secondary")


def _err(message: str, key: str, **info: Any) -> RpcError:
    return RpcError(message, INVALID_PARAMS, data={"key": key, **info})


def now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


def today() -> str:
    return date.today().isoformat()


def is_entry(ind: dict[str, Any]) -> bool:
    return ind.get("source_type") in ENTRY_SOURCES


# ----- reading -------------------------------------------------------------------------


class View:
    """What the calculations need from a project, read once."""

    def __init__(self, p: Project, indicators: list[dict[str, Any]] | None = None) -> None:
        self.p = p
        self.profile = schedule.profile_from_meta(p.meta())
        self.periods = p.records("period")
        self.subs = {s["id"]: s for s in p.records("submission")}
        self.indicators = indicators if indicators is not None else p.records("indicator")
        self.entry = [i for i in self.indicators if is_entry(i)]
        self.dis = {d["key"]: d for d in p.records("disaggregation")}
        self.places = p.records("place")
        self.partners = p.records("partner")
        self._values: dict[tuple[str, str, str], dict[str, tuple]] | None = None
        self._targets: dict[str, dict[str, float]] | None = None

    @property
    def values(self) -> dict[tuple[str, str, str], dict[str, tuple]]:
        if self._values is None:
            self._values = monitoring.read_values(self.p.conn, [i["id"] for i in self.entry])
        return self._values

    @property
    def targets(self) -> dict[str, dict[str, float]]:
        if self._targets is None:
            out: dict[str, dict[str, float]] = {}
            for t in self.p.records("target"):
                if t["period"] != targets_.TOTAL:
                    out.setdefault(t["indicator_id"], {})[t["period"]] = t["value"]
            self._targets = out
        return self._targets

    def period(self, code: str) -> dict[str, Any]:
        for p in self.periods:
            if p["code"] == code:
                return p
        raise _err(f"Unknown period: {code}", "period_not_found", period=code)

    def units(self) -> list[dict[str, str]]:
        return monitoring.units(self.profile, self.places, self.partners)

    def cells(self, sub_id: str) -> dict[str, dict[str, tuple]]:
        out: dict[str, dict[str, tuple]] = {}
        for (ind_id, _period, sid), cells in self.values.items():
            if sid == sub_id:
                out[ind_id] = cells
        return out


def find(view: View, period: str, place_id: str, partner_id: str) -> dict[str, Any] | None:
    for s in view.subs.values():
        if s["period"] == period and s.get("place_id", "") == place_id and s.get("partner_id", "") == partner_id:
            return s
    return None


def alerts(view: View, sub: dict[str, Any]) -> list[dict[str, Any]]:
    idx = next((i for i, p in enumerate(view.periods) if p["code"] == sub["period"]), None)
    previous: dict[str, float | None] = {}
    if idx:
        before = find(view, view.periods[idx - 1]["code"], sub.get("place_id", ""), sub.get("partner_id", ""))
        if before:
            cells = view.cells(before["id"])
            for ind in view.entry:
                if ind["id"] in cells:
                    previous[ind["id"]] = monitoring.submission_measure(ind, cells[ind["id"]], {}).value
    period = next((p for p in view.periods if p["code"] == sub["period"]), None)
    return intake_checks.run(sub, view.entry, view.cells(sub["id"]), previous, view.dis, period)


def justified(p: Project) -> dict[str, dict[str, Any]]:
    return {j["key"]: j for j in p.records("justification")}


# ----- changing -----------------------------------------------------------------------


def _history(sub: dict[str, Any], action: str, comment: str = "") -> list[dict[str, Any]]:
    entry = {"at": now(), "action": action, "status": sub["status"]}
    if comment:
        entry["comment"] = comment
    return [*sub.get("history", []), entry][-200:]


def _check_unit(view: View, place_id: str, partner_id: str) -> None:
    if place_id and place_id not in {p["id"] for p in view.places}:
        raise _err("Unknown place", "place_not_found")
    if partner_id and partner_id not in {p["id"] for p in view.partners}:
        raise _err("Unknown partner", "partner_not_found")


def open_submission(p: Project, period: str, place_id: str = "", partner_id: str = "", channel: str = "entry") -> str:
    """The submission of a unit for a period, created as a draft when there is none."""
    view = View(p, [])
    per = view.period(period)
    _check_unit(view, place_id, partner_id)
    existing = find(view, period, place_id, partner_id)
    if existing:
        return existing["id"]
    if per["state"] == "locked":
        raise _err("This period is locked", "period_locked")
    if channel not in monitoring.CHANNELS:
        channel = "entry"
    spec = {
        "period": period,
        "place_id": place_id,
        "partner_id": partner_id,
        "channel": channel,
        "status": "draft",
        "created_at": now(),
        "submitted_at": None,
        "validated_at": None,
        "comment": "",
        "source_ref": "",
        "history": [],
    }
    spec["history"] = _history(spec, "create")
    return p.insert_record("submission", spec)


def _editable(p: Project, sub: dict[str, Any]) -> None:
    if sub["status"] not in monitoring.EDITABLE:
        raise _err("This submission is validated: reopen it to change it", "submission_validated")
    per = next((x for x in p.records("period") if x["code"] == sub["period"]), None)
    if per and per["state"] == "locked":
        raise _err("This period is locked", "period_locked")


def save_values(p: Project, sub_id: Any, items: Any, source_ref: Any = None) -> int:
    """Replace the cells of the indicators given. Each item:
    {"indicator_id", "cats": {"sex": "f"}, "value", "numerator", "denominator"}.
    Empty cells are removed. Returns the number of cells stored."""
    sub = p.record("submission", sub_id)
    _editable(p, sub)
    if not isinstance(items, list) or len(items) > 200_000:
        raise _err("values must be a list", "invalid_params")
    inds = {i["id"]: i for i in p.records("indicator") if is_entry(i)}
    dis = {d["key"]: d for d in p.records("disaggregation")}
    rows: dict[tuple[str, str], tuple] = {}
    touched: set[str] = set()
    for item in items:
        if not isinstance(item, dict):
            raise _err("Each value must be an object", "invalid_params")
        ind = inds.get(item.get("indicator_id"))
        if ind is None:
            raise _err("Unknown indicator, or not an indicator with values entered", "indicator_not_found")
        touched.add(ind["id"])
        cats = item.get("cats") or {}
        if not isinstance(cats, dict):
            raise _err("cats must be an object", "invalid_params")
        for k, c in cats.items():
            if k not in (ind.get("breakdowns") or []) or k not in dis:
                raise _err(f"{k} is not a disaggregation of this indicator", "category_invalid")
            if c != "_na" and c not in {x["code"] for x in dis[k]["categories"]}:
                raise _err(f"Unknown category {c}", "category_invalid")
        v, num, den = monitoring.clean_cell(ind, item)
        if v is None and num is None and den is None:
            continue
        rows[(ind["id"], monitoring.cats_key(cats))] = (v, num, den)
    with p.conn:
        for ind_id in touched:
            p.conn.execute("DELETE FROM value WHERE submission_id = ? AND indicator_id = ?", (sub["id"], ind_id))
        p.conn.executemany(
            "INSERT INTO value(indicator_id, submission_id, period, place_id, partner_id, cats, value, "
            "numerator, denominator) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            [
                (ind_id, sub["id"], sub["period"], sub.get("place_id", ""), sub.get("partner_id", ""), key, *vals)
                for (ind_id, key), vals in rows.items()
            ],
        )
    if source_ref is not None:
        sub["source_ref"] = str(source_ref).strip()[:500]
    if sub["status"] == "returned":
        pass  # stays returned until submitted again
    p.update_record("submission", sub["id"], sub)
    return len(rows)


TRANSITIONS = {
    "submit": (("draft", "returned"), "submitted"),
    "review": (("submitted",), "review"),
    "return": (("submitted", "review"), "returned"),
    "validate": (("draft", "submitted", "review", "returned"), "validated"),
    "reopen": (("validated",), "draft"),
}


def act(p: Project, sub_id: Any, action: Any, comment: Any = "") -> dict[str, Any]:
    sub = p.record("submission", sub_id)
    if action not in TRANSITIONS:
        raise _err(f"Unknown action: {action}", "invalid_params")
    allowed, new = TRANSITIONS[action]
    per = next((x for x in p.records("period") if x["code"] == sub["period"]), None)
    if per and per["state"] == "locked":
        raise _err("This period is locked", "period_locked")
    if sub["status"] not in allowed:
        raise _err(f"A {sub['status']} submission cannot be {action}ed", "submission_transition", status=sub["status"])
    comment = str(comment or "").strip()[:2000]
    if action in ("return", "reopen") and not comment:
        raise _err("Give the reason", "comment_required")
    if action == "validate":
        view = View(p)
        stop = intake_checks.blocking(alerts(view, sub), set(justified(p)))
        if stop:
            raise _err(f"{len(stop)} alerts must be corrected or justified first", "alerts_open", n=len(stop))
        sub["validated_at"] = now()
    if action == "submit":
        sub["submitted_at"] = now()
    if action == "return":
        sub["comment"] = comment
    sub["status"] = new
    sub["history"] = _history(sub, action, comment)
    p.update_record("submission", sub["id"], sub)
    return sub


def lock_period(p: Project, period: dict[str, Any], lock: bool, reason: str = "") -> None:
    """Lock: every submission of the period must be validated; they become locked.
    Reopening needs a reason, kept in the period history."""
    subs = [s for s in p.records("submission") if s["period"] == period["code"]]
    if lock:
        pending = [s for s in subs if s["status"] not in ("validated", "locked")]
        if pending:
            raise _err(f"{len(pending)} submissions are not validated", "period_unvalidated", n=len(pending))
        for s in subs:
            s["status"] = "locked"
            s["history"] = _history(s, "lock")
            p.update_record("submission", s["id"], s)
    else:
        if not reason.strip():
            raise _err("Give the reason for reopening the period", "comment_required")
        for s in subs:
            if s["status"] == "locked":
                s["status"] = "validated"
                s["history"] = _history(s, "unlock", reason)
                p.update_record("submission", s["id"], s)
    period["state"] = "locked" if lock else "open"
    period["history"] = [
        *period.get("history", []),
        {"at": now(), "action": "lock" if lock else "unlock", **({"comment": reason} if reason else {})},
    ][-50:]
    p.update_record("period", period["id"], {k: v for k, v in period.items() if k != "id"})


def delete_submission(p: Project, sub_id: Any) -> None:
    sub = p.record("submission", sub_id)
    if sub["status"] not in ("draft",):
        raise _err("Only a draft submission can be deleted", "submission_validated")
    with p.conn:
        p.conn.execute("DELETE FROM value WHERE submission_id = ?", (sub["id"],))
    p.delete_record("submission", sub["id"])


# ----- tracking table --------------------------------------------------------------------


def scope_from(params: dict[str, Any], view: View) -> Scope:
    place = params.get("place_id") or None
    place_ids = None
    if place:
        from .places import descendants

        place_ids = {place, *descendants(view.places, place)}
    cats = params.get("cats") or {}
    if not isinstance(cats, dict):
        cats = {}
    return Scope(
        provisional=bool(params.get("provisional")),
        place_ids=place_ids,
        partner_id=params.get("partner_id") or None,
        cats={str(k): str(v) for k, v in cats.items()},
    )


def threshold(view: View) -> float:
    return float(view.profile.get("on_track") or monitoring.ON_TRACK)


def track_all(view: View, params: dict[str, Any] | None = None) -> dict[str, Any]:
    params = params or {}
    day = params.get("today") or today()
    if not view.periods:
        return {"period": None, "rows": [], "periods": []}
    upto = monitoring.selected_period(view.periods, params.get("period"), day)
    scope = scope_from(params, view)
    rows = []
    for ind in view.entry:
        rows.append(
            monitoring.track(
                ind,
                view.periods,
                view.subs,
                view.values,
                view.targets.get(ind["id"], {}),
                view.profile,
                scope,
                upto,
                day,
                threshold(view),
            )
        )
    return {"period": view.periods[upto]["code"], "rows": rows}


def by_category(view: View, ind: dict[str, Any], key: str, params: dict[str, Any]) -> dict[str, float | None]:
    """Value to date of each category of one disaggregation."""
    dis = view.dis.get(key)
    if dis is None:
        return {}
    day = params.get("today") or today()
    upto = monitoring.selected_period(view.periods, params.get("period"), day)
    out = {}
    for code in [c["code"] for c in dis["categories"]] + ["_na"]:
        scope = scope_from({**params, "cats": {key: code}}, view)
        row = monitoring.track(ind, view.periods, view.subs, view.values, {}, view.profile, scope, upto, day)
        out[code] = row["to_date"]
    return out


def compat(view: View, ind: dict[str, Any], lang: str = "fr") -> dict[str, Any]:
    """The shape the overview, the analysis screen and the report used for routine
    indicators in 0.5, computed from the submissions."""
    track = track_all(view, {})
    row = next((r for r in track["rows"] if r["indicator_id"] == ind["id"]), None)
    label = {p["code"]: (p["label_en"] if lang == "en" else p["label_fr"]) for p in view.periods}
    if row is None:
        return {
            "source": "routine",
            "aggregation": monitoring.time_mode(ind),
            "periods": [],
            "baseline": monitoring.baseline(ind),
            "baseline_source": None,
            "current": None,
            "current_period": None,
            "current_round": None,
            "target": ind.get("target"),
            "planned_to_date": None,
            "pace": None,
            "achievement": None,
            "status": "unknown",
            "by_total": {},
        }
    done = [s for s in row["series"] if s["value"] is not None]
    last = done[-1] if done else None
    upto = next((i for i, s in enumerate(row["series"]) if last and s["period"] == last["period"]), None)
    at = row["series"][upto] if upto is not None else None
    base = monitoring.baseline(ind)
    current = at["to_date"] if at else None
    target = ind.get("target")
    achievement = None
    if current is not None and target is not None and base is not None and target != base:
        achievement = (current - base) / (target - base)
    by_total: dict[str, float] = {}
    keys = ind.get("breakdowns") or []
    if keys and keys[0] in view.dis and at:
        dis = view.dis[keys[0]]
        names = {c["code"]: (c["en"] if lang == "en" else c["fr"]) for c in dis["categories"]}
        for code, v in by_category(view, ind, keys[0], {"period": at["period"]}).items():
            if v is not None and code in names:
                by_total[names[code]] = v
    status = row["series"][upto]["status"] if upto is not None else "unknown"
    if status in ("no_data", "not_started"):
        status = "unknown"
    return {
        "source": "routine",
        "aggregation": monitoring.time_mode(ind),
        "periods": [
            {
                "period": label.get(s["period"], s["period"]),
                "code": s["period"],
                "achieved": s["value"],
                "planned": s["target"],
                "to_date": s["to_date"],
                "planned_to_date": s["target_to_date"],
                "provisional": s["provisional"],
            }
            for s in row["series"]
            if s["value"] is not None or s["target"] is not None
        ],
        "baseline": base,
        "baseline_source": "manual" if ind.get("baseline_manual") is not None else ("zero" if base == 0 else None),
        "current": current,
        "current_period": label.get(last["period"]) if last else None,
        "current_round": None,
        "target": target,
        "planned_to_date": at["target_to_date"] if at else None,
        "pace": at["rate_to_date"] if at else None,
        "achievement": achievement,
        "status": status,
        "by_total": by_total,
    }


# ----- migration of the routine values of 0.4 and 0.5 --------------------------------------


def _slug(text: str) -> str:
    from .places import slug

    return slug(text) or "c"


def migrate_routine(conn: sqlite3.Connection) -> None:
    """Move routine values into the calendar, submissions and values.

    Each period of values becomes a validated submission of the whole project in
    the matching period of the calendar (created from the values' end dates when
    the project has none). Planned values become targets by period; categories
    become a disaggregation. The old rows are kept untouched; rows that cannot be
    placed in the calendar (no end date) are listed in the project metadata.
    """
    tables = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type = 'table'")}
    if "routine_value" not in tables:
        return
    rows = conn.execute("SELECT indicator_id, spec FROM routine_value ORDER BY indicator_id, position").fetchall()
    if not rows:
        return
    inds = {r[0]: json.loads(r[1]) for r in conn.execute("SELECT id, spec FROM indicator")}
    by_ind: dict[str, list[dict[str, Any]]] = {}
    for ind_id, spec in rows:
        if ind_id in inds:
            by_ind.setdefault(ind_id, []).append(json.loads(spec))

    def pos(table: str) -> int:
        return conn.execute(f"SELECT COALESCE(MAX(position), 0) + 1 FROM {table}").fetchone()[0]

    def insert(table: str, spec: dict[str, Any], scope: tuple[str, str] | None = None) -> str:
        rid = uuid.uuid4().hex
        if scope:
            conn.execute(
                f"INSERT INTO {table}(id, {scope[0]}, position, spec) VALUES (?, ?, ?, ?)",
                (rid, scope[1], pos(table), json.dumps(spec, ensure_ascii=False)),
            )
        else:
            conn.execute(
                f"INSERT INTO {table}(id, position, spec) VALUES (?, ?, ?)",
                (rid, pos(table), json.dumps(spec, ensure_ascii=False)),
            )
        return rid

    periods = [json.loads(r[0]) for r in conn.execute("SELECT spec FROM period ORDER BY position")]
    if not periods:
        # A calendar from the end dates of the values.
        ends = sorted({(r["end"], r["period"]) for rs in by_ind.values() for r in rs if r.get("end")})
        codes_seen: set[str] = set()
        prev_end: date | None = None
        for i, (end, label) in enumerate(ends):
            e = date.fromisoformat(end)
            if prev_end is None:
                gap = (date.fromisoformat(ends[1][0]) - e).days if len(ends) > 1 else 91
                start = e - timedelta(days=max(gap, 1) - 1)
            else:
                start = prev_end + timedelta(days=1)
            code = re.sub(r"\s+", "-", label.strip())[:30] or end
            if code in codes_seen:
                code = f"{code}-{i}"
            codes_seen.add(code)
            spec = {
                "code": code,
                "label_fr": label,
                "label_en": label,
                "start": start.isoformat(),
                "end": end,
                "data_due": end,
                "report_due": end,
                "state": "open",
            }
            insert("period", spec)
            periods.append(spec)
            prev_end = e

    def place(row: dict[str, Any]) -> str | None:
        if row.get("end"):
            for p in periods:
                if p["start"] <= row["end"] <= p["end"]:
                    return p["code"]
        for p in periods:
            if row["period"] in (p["code"], p["label_fr"], p["label_en"]):
                return p["code"]
        return None

    dis = [json.loads(r[0]) for r in conn.execute("SELECT spec FROM disaggregation")]
    subs: dict[str, str] = {}
    unplaced = []
    stamp = now()
    for ind_id, rs in by_ind.items():
        ind = inds[ind_id]
        cats = ind.get("categories") or []
        key = None
        if cats:
            names = [c.casefold() for c in cats]
            same = next((d for d in dis if [c["fr"].casefold() for c in d["categories"]] == names), None)
            if same is None:
                n = 1
                while any(d["key"] == f"repartition_{n}" for d in dis):
                    n += 1
                codes: list[str] = []
                for c in cats:
                    code = _slug(c)
                    while code in codes:
                        code += "_"
                    codes.append(code)
                same = {
                    "key": f"repartition_{n}",
                    "name_fr": f"Répartition {n}",
                    "name_en": f"Breakdown {n}",
                    "categories": [{"code": code, "fr": c, "en": c} for code, c in zip(codes, cats, strict=True)],
                }
                insert("disaggregation", same)
                dis.append(same)
            key = same["key"]
            code_of = {c["fr"]: c["code"] for c in same["categories"]}
            ind["breakdowns"] = list(dict.fromkeys([key, *(ind.get("breakdowns") or [])]))
            conn.execute("UPDATE indicator SET spec = ? WHERE id = ?", (json.dumps(ind, ensure_ascii=False), ind_id))
        have_targets = {
            json.loads(r[0])["period"]
            for r in conn.execute("SELECT spec FROM target WHERE indicator_id = ?", (ind_id,))
        }
        for r in rs:
            code = place(r)
            if code is None:
                unplaced.append({"indicator_id": ind_id, "period": r["period"]})
                continue
            if code not in subs:
                spec = {
                    "period": code,
                    "place_id": "",
                    "partner_id": "",
                    "channel": "migrated",
                    "status": "validated",
                    "created_at": stamp,
                    "submitted_at": stamp,
                    "validated_at": stamp,
                    "comment": "",
                    "source_ref": "",
                    "history": [{"at": stamp, "action": "migrate", "status": "validated"}],
                }
                subs[code] = insert("submission", spec)
            cells = []
            if r.get("achieved") is not None:
                cells.append(("", r["achieved"]))
            for name, v in (r.get("by") or {}).items():
                if key and name in code_of and v is not None:
                    cells.append((monitoring.cats_key({key: code_of[name]}), v))
            conn.executemany(
                "INSERT OR REPLACE INTO value(indicator_id, submission_id, period, cats, value) VALUES (?, ?, ?, ?, ?)",
                [(ind_id, subs[code], code, k, v) for k, v in cells],
            )
            if r.get("planned") is not None and code not in have_targets:
                insert("target", {"period": code, "value": r["planned"], "history": []}, ("indicator_id", ind_id))
                have_targets.add(code)
    if unplaced:
        conn.execute("INSERT OR REPLACE INTO meta(key, value) VALUES ('routine_unplaced', ?)", (json.dumps(unplaced),))
