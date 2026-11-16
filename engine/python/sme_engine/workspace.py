# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 GAYI Komi Selassi and SANOUSSI Moudjibou

"""Workspace: what the user sees of all their projects without opening them.

Each project file is read without being changed (read-only connection, no
migration), so a project made with an older version, or open in another window,
can be listed safely. The summary says where the project stands in its
calendar and what is due next.
"""

from __future__ import annotations

import json
import sqlite3
from datetime import date
from pathlib import Path
from typing import Any

from . import frameworks, schedule
from .project import APPLICATION_ID, SCHEMA_VERSION


def _tables(conn: sqlite3.Connection) -> set[str]:
    return {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type = 'table'")}


def _count(conn: sqlite3.Connection, tables: set[str], table: str) -> int:
    return conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0] if table in tables else 0


def summary(path: str, today: str | None = None) -> dict[str, Any]:
    day = today or date.today().isoformat()
    file = Path(path)
    if not file.is_file():
        return {"path": path, "state": "missing"}
    try:
        conn = sqlite3.connect(f"{file.resolve().as_uri()}?mode=ro", uri=True)
    except sqlite3.Error:
        return {"path": path, "state": "unreadable"}
    try:
        if conn.execute("PRAGMA application_id").fetchone()[0] != APPLICATION_ID:
            return {"path": path, "state": "unreadable"}
        version = conn.execute("PRAGMA user_version").fetchone()[0]
        if version > SCHEMA_VERSION:
            return {"path": path, "state": "too_new"}
        tables = _tables(conn)
        meta = dict(conn.execute("SELECT key, value FROM meta").fetchall())
        profile = schedule.profile_from_meta(meta)
        periods = []
        if "period" in tables:
            periods = [json.loads(r[0]) for r in conn.execute("SELECT spec FROM period ORDER BY position")]
        current = schedule.period_of(periods, day)
        deadlines = sorted(
            [{"kind": "data", "date": p["data_due"], "period": p} for p in periods if p["data_due"] >= day]
            + [{"kind": "report", "date": p["report_due"], "period": p} for p in periods if p["report_due"] >= day],
            key=lambda d: (d["date"], d["kind"] == "report"),
        )
        nxt = deadlines[0] if deadlines else None
        progress = None
        if profile["start"] and profile["end"] and profile["end"] > profile["start"]:
            total = (date.fromisoformat(profile["end"]) - date.fromisoformat(profile["start"])).days
            done = (date.fromisoformat(day) - date.fromisoformat(profile["start"])).days
            progress = min(max(done / total, 0.0), 1.0)
        return {
            "path": path,
            "state": "ok" if version == SCHEMA_VERSION else "older",
            "name": meta.get("name", file.stem),
            "updated_at": meta.get("updated_at"),
            "model": frameworks.from_meta(meta)["id"],
            "profile": {
                k: profile[k]
                for k in ("code", "start", "end", "frequency", "donors", "countries", "sectors", "color", "manager")
            },
            "time_elapsed": progress,
            "phase": (
                "not_started"
                if profile["start"] and day < profile["start"]
                else "closed"
                if profile["end"] and day > profile["end"]
                else "running"
                if profile["start"]
                else "unset"
            ),
            "current_period": current,
            "next_deadline": (
                {
                    "kind": nxt["kind"],
                    "date": nxt["date"],
                    "period": nxt["period"]["code"],
                    "label_fr": nxt["period"]["label_fr"],
                    "label_en": nxt["period"]["label_en"],
                }
                if nxt
                else None
            ),
            "counts": {
                "results": _count(conn, tables, "framework_node"),
                "indicators": _count(conn, tables, "indicator"),
                "datasets": _count(conn, tables, "dataset"),
                "periods": len(periods),
                "places": _count(conn, tables, "place"),
                "partners": _count(conn, tables, "partner"),
            },
        }
    except (sqlite3.Error, ValueError, KeyError):
        return {"path": path, "state": "unreadable"}
    finally:
        conn.close()


def summaries(paths: Any, today: str | None = None) -> list[dict[str, Any]]:
    if not isinstance(paths, list):
        return []
    return [summary(p, today) for p in paths[:200] if isinstance(p, str)]
