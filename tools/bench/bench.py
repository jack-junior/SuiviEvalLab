# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 GAYI Komi Selassi and SANOUSSI Moudjibou

"""Performance thresholds of the specification (section 9), measured on the engine.

    python tools/bench/bench.py [work dir]

Builds, in the work directory (a temporary one by default):
- a large project: 300 indicators, 40 quarterly periods, 500 sites; 60 indicators
  are reported by every site, the others once for the whole project, every
  submission validated (1.2 million values with their breakdowns);
- 20 ordinary projects (40 indicators, 12 periods, 30 sites) for the dashboard;
- a CSV file of 500 000 rows and 12 columns to import.

Then times what the user waits for. The thresholds are those of the
specification; the script ends with a non-zero code if one is missed.

The first display after the values were written computes every period once and
keeps the result (about 0.2 s per period of 60 000 values). It only happens
when many periods arrive at once, so it is shown without a threshold.
"""

from __future__ import annotations

import csv
import io
import json
import random
import sys
import tempfile
import time
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "engine" / "python"))

from sme_engine.methods import register  # noqa: E402
from sme_engine.project import Project  # noqa: E402
from sme_engine.r_bridge import RBridge  # noqa: E402
from sme_engine.rpc import Server  # noqa: E402

THRESHOLDS = {
    "open": 3.0,
    "tracking": 1.0,
    "tracking_filtered": 1.0,
    "tracking_new_indicator": 1.0,
    "dashboard_20": 3.0,
    "import_500k": 60.0,
}


class Engine:
    def __init__(self) -> None:
        self.bridge = RBridge()
        self.server = Server(stdin=io.StringIO(), stdout=io.StringIO())
        register(self.server, self.bridge)

    def __call__(self, method: str, params: dict | None = None):
        line = json.dumps({"jsonrpc": "2.0", "id": 1, "method": method, "params": params or {}})
        resp = self.server.handle_line(line)
        if "error" in resp:
            raise RuntimeError(f"{method}: {resp['error']['message']}")
        return resp["result"]

    def stop(self) -> None:
        self.bridge.stop()


def timed(fn, *args, **kwargs):
    t0 = time.perf_counter()
    out = fn(*args, **kwargs)
    return out, time.perf_counter() - t0


def build(path: Path, years: int, indicators: int, by_site: int, sites: int, seed: int = 1) -> None:
    """Design through the engine, then the reported values written in bulk."""
    rnd = random.Random(seed)
    call = Engine()
    try:
        call(
            "project.create",
            {
                "path": str(path),
                "name": path.stem,
                "profile": {
                    "start": "2020-01-01",
                    "end": f"{2019 + years}-12-31",
                    "frequency": "quarterly",
                    "donors": ["Union européenne"],
                    "country": "Togo",
                    "sector": "Santé",
                },
                "disaggregations": ["sex"],
            },
        )
        outcome = call("framework.add", {"title": "Effet"})["created"]
        call("project.close")
    finally:
        call.stop()

    p = Project.open(path)
    try:
        conn = p.conn
        periods = [r["code"] for r in p.records("period")]
        places = [
            p.insert_record("place", {"name": f"Site {i:03d}", "code": f"S{i:03d}", "parent_id": None})
            for i in range(sites)
        ]
        site_ind, project_ind = [], []
        for i in range(indicators):
            percent = i % 3 == 0
            spec = {
                "name": f"Indicateur {i + 1}",
                "unit": "percent" if percent else "count",
                "source_type": "routine",
                "breakdowns": ["sex"] if i % 2 == 0 else [],
                "frequency": "quarterly",
                "target": 0.8 if percent else 1000,
                "baseline_manual": 0.4 if percent else 0,
            }
            iid = p.insert_record("indicator", spec, scope=outcome)
            (site_ind if i < by_site else project_ind).append((iid, spec))
        now = "2026-01-01T00:00:00"
        subs, values = [], []
        pos = 0

        def add_sub(period: str, place: str) -> str:
            nonlocal pos
            pos += 1
            sid = uuid.uuid4().hex
            spec = {
                "period": period,
                "place_id": place,
                "partner_id": "",
                "channel": "entry",
                "status": "validated",
                "created_at": now,
                "submitted_at": now,
                "validated_at": now,
                "comment": "",
                "source_ref": "",
                "history": [],
            }
            subs.append((sid, pos, json.dumps(spec)))
            return sid

        def add_values(sid: str, period: str, place: str, ind: tuple[str, dict]) -> None:
            iid, spec = ind
            if spec["unit"] == "percent":
                den = rnd.randint(50, 200)
                num = rnd.randint(0, den)
                cells = [("", num / den, num, den)]
                if spec["breakdowns"]:
                    f = rnd.randint(0, num)
                    cells += [("sex=f", None, f, den // 2), ("sex=m", None, num - f, den - den // 2)]
            else:
                v = rnd.randint(0, 100)
                cells = [("", v, None, None)]
                if spec["breakdowns"]:
                    f = rnd.randint(0, v)
                    cells += [("sex=f", f, None, None), ("sex=m", v - f, None, None)]
            for cats, v, num, den in cells:
                values.append((iid, sid, period, place, "", cats, v, num, den))

        for period in periods:
            for place in places:
                sid = add_sub(period, place)
                for ind in site_ind:
                    add_values(sid, period, place, ind)
            sid = add_sub(period, "")
            for ind in project_ind:
                add_values(sid, period, "", ind)
        with conn:
            conn.executemany("INSERT INTO submission(id, position, spec) VALUES (?, ?, ?)", subs)
            conn.executemany(
                "INSERT INTO value(indicator_id, submission_id, period, place_id, partner_id, cats, value, "
                "numerator, denominator) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                values,
            )
            # The change log is for team projects; a single-user benchmark does not need it.
            conn.execute("DELETE FROM changes")
    finally:
        p.close()


def main() -> int:
    work = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(tempfile.mkdtemp(prefix="sme-bench-"))
    work.mkdir(parents=True, exist_ok=True)
    results: dict[str, float] = {}

    big = work / "grand-projet.sme"
    if not big.exists():
        _, t = timed(build, big, 10, 300, 60, 500)
        print(f"build large project: {t:.1f} s, {big.stat().st_size / 1e6:.0f} MB")
    small = []
    for k in range(20):
        path = work / f"projet-{k:02d}.sme"
        if not path.exists():
            build(path, 3, 40, 10, 30, seed=k + 2)
        small.append(str(path))
    data = work / "donnees-500k.csv"
    if not data.exists():
        rnd = random.Random(7)
        with data.open("w", newline="", encoding="utf-8") as fh:
            w = csv.writer(fh)
            w.writerow(
                ["id", "region", "district", "sexe", "age", "menage", "revenu", "eau", "ecole", "score", "date", "note"]
            )
            for i in range(500_000):
                w.writerow(
                    [
                        i,
                        f"R{rnd.randint(1, 8)}",
                        f"D{rnd.randint(1, 60)}",
                        rnd.choice("fm"),
                        rnd.randint(0, 90),
                        rnd.randint(1, 15),
                        round(rnd.uniform(0, 500000), 2),
                        rnd.choice(["oui", "non"]),
                        rnd.choice(["oui", "non", ""]),
                        round(rnd.gauss(50, 15), 1),
                        f"2025-{rnd.randint(1, 12):02d}-{rnd.randint(1, 28):02d}",
                        rnd.choice(["", "à revoir", "ok"]),
                    ]
                )

    call = Engine()
    try:
        snap, results["open"] = timed(call, "project.open", {"path": str(big)})
        periods = [x["code"] for x in snap["periods"]]
        last = periods[-1]
        place = snap["places"][len(snap["places"]) // 2]["id"]
        # First display after the values were written: every period is computed and kept.
        _, results["tracking_first"] = timed(call, "tracking.table", {"period": last, "today": "2029-12-31"})
        _, results["tracking"] = timed(call, "tracking.table", {"period": last, "today": "2029-12-31"})
        _, results["tracking_filtered"] = timed(
            call, "tracking.table", {"period": last, "place_id": place, "today": "2029-12-31"}
        )
        # A new indicator: only it is computed, not the periods again.
        node = snap["framework"][0]["id"]
        call(
            "indicator.save",
            {"node_id": node, "indicator": {"name": "Nouvel indicateur", "unit": "count", "source_type": "routine"}},
        )
        _, results["tracking_new_indicator"] = timed(call, "tracking.table", {"period": last, "today": "2029-12-31"})
        call("project.close")
        _, results["dashboard_20"] = timed(call, "portfolio.dashboard", {"paths": small, "today": "2022-06-30"})
        call("project.create", {"path": str(work / f"import-{uuid.uuid4().hex[:6]}.sme"), "name": "Import"})
        _, results["import_500k"] = timed(
            call, "dataset.import", {"path": str(data), "name": "Grand fichier", "round": "baseline"}
        )
        call("project.close")
    finally:
        call.stop()

    print(f"{'tracking_first':20s} {results['tracking_first']:7.2f} s  (computed once, then kept)")
    failed = False
    for key, limit in THRESHOLDS.items():
        ok = results[key] <= limit
        failed |= not ok
        print(f"{key:20s} {results[key]:7.2f} s  (limit {limit:.0f} s)  {'ok' if ok else 'TOO SLOW'}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
