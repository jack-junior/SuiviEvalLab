"""Expected results of the test kit.

Each scenario of the guide is played through the engine exactly as a tester does
it in the app, and the results are written to expected.json for guide.py. The
survey estimates are then checked independently with check_in_r.R.

    PYTHONPATH=engine/python python tools/test-kit/expected.py build/test-kit
"""

from __future__ import annotations

import io
import json
import os
import sys
import tempfile
from pathlib import Path

os.environ.setdefault("SME_BACKUP_DIR", tempfile.mkdtemp())

from sme_engine.methods import register  # noqa: E402
from sme_engine.r_bridge import RBridge  # noqa: E402
from sme_engine.rpc import Server  # noqa: E402

KIT = Path(sys.argv[1] if len(sys.argv) > 1 else "build/test-kit")
D = KIT / "donnees"
bridge = RBridge()
server = Server(stdin=io.StringIO(), stdout=io.StringIO())
register(server, bridge)


def call(method: str, params: dict | None = None):
    resp = server.handle_line(json.dumps({"jsonrpc": "2.0", "id": 1, "method": method, "params": params or {}}))
    if "error" in resp:
        raise RuntimeError(resp["error"])
    return resp["result"]


def pack(a: dict) -> dict:
    rounds = []
    for r in a["rounds"]:
        if "error_key" in r["result"]:
            continue
        res = r["result"]
        rounds.append(
            {k: res.get(k) for k in ("estimate", "ci_low", "ci_high", "n", "method_key")}
            | {"round": r["round"], "by": [(g["group"], g["estimate"], g["n"]) for g in res.get("by", [])]}
        )
    comp = a.get("comparison")
    keys = ("difference", "ci_low", "ci_high", "p_value", "test_key", "warning")
    return {
        "rounds": rounds,
        "comparison": {k: comp.get(k) for k in keys} if comp else None,
        "achievement": a.get("achievement"),
        "status": a.get("status"),
    }


E: dict = {}
tmp = Path(tempfile.mkdtemp())

# Iraq: baseline 2019, endline 2020 (scenarios 4 to 11).
call("project.create", {"path": str(tmp / "t.sme"), "name": "Test"})
f19, f20 = D / "01_irak_mcna_2019_reference.xlsx", D / "02_irak_mcna_2020_fin_de_projet.xlsx"
i19 = call("dataset.inspect", {"path": str(f19)})
i20 = call("dataset.inspect", {"path": str(f20)})
E["sheets"] = {
    "2019": i19["sheet"],
    "2020": i20["sheet"],
    "design19": i19["design"],
    "design20": i20["design"],
    "cols19": len(i19["columns"]),
    "cols20": len(i20["columns"]),
}
common = {"sheet": i19["sheet"], "design": i19["design"]}
d19 = call("dataset.import", {"path": str(f19), "name": "MCNA 2019", "round": "baseline", **common})["created"]
common = {"sheet": i20["sheet"], "design": i20["design"]}
d20 = call("dataset.import", {"path": str(f20), "name": "MCNA 2020", "round": "endline", **common})["created"]
E["rows"] = {d["name"]: d["rows"] for d in call("project.get")["datasets"]}
q = call("dataset.quality", {"id": d19})
E["quality19"] = [(i["key"], i["column"], i["count"]) for i in q["issues"] if i["severity"] == "warning"]
exclude = {"kind": "exclude", "column": "population_group", "values": ["idp_in_camp", "host"], "note": "2020"}
call("cleaning.add", {"dataset_id": d19, "rule": exclude})
recode = {"kind": "recode", "column": "primary_school_place", "from": ["do_not_know"], "to": None, "note": "NSP"}
for d in (d19, d20):
    call("cleaning.add", {"dataset_id": d, "rule": recode})
snap = call("project.get")
E["effects"] = {d["name"]: [(r["kind"], r["effect"]) for r in d["rules"]] for d in snap["datasets"]}
E["clean_rows"] = {d["name"]: d["clean_rows"] for d in snap["datasets"]}
call("framework.add", {"level": "impact", "title": "Les enfants ont accès à l'éducation"})
root = call("project.get")["framework"][0]["id"]
node = call("framework.add", {"parent_id": root, "title": "L'accès physique aux écoles s'améliore"})["created"]


def indicator(spec: dict) -> dict:
    saved = call("indicator.save", {"node_id": node, "indicator": spec})["saved"]
    return pack(call("analysis.indicator", {"id": saved}))


E["ind1"] = indicator(
    {
        "name": "Ménages avec une école primaire à moins de 2 km",
        "unit": "percent",
        "conditions": [{"column": "primary_school_place", "values": ["within_2km"]}],
        "target": 0.9,
        "disaggregation": "population_group",
    }
)
E["ind2"] = indicator(
    {
        "name": "Ménages ayant retiré un enfant de l'école",
        "unit": "count",
        "conditions": [{"column": "child_dropout_school", "values": ["yes"]}],
        "direction": "decrease",
    }
)
E["ind3"] = indicator({"name": "Nombre moyen d'enfants par ménage", "unit": "mean", "column": "tot_child"})
test = {
    "question": "groups",
    "kind": "proportion",
    "dataset_id": d19,
    "outcome": {"column": "primary_school_place", "values": ["within_2km"]},
    "group": "population_group",
}
t = call("test.run", {"test": test})
E["test"] = {k: t["result"].get(k) for k in ("test_key", "p_value", "statistic", "df", "df2", "effect", "n")} | {
    "groups": [(g["group"], g.get("estimate"), g.get("n")) for g in t["result"].get("groups", [])],
    "fr": t["conclusion"]["fr"],
}
E["quality20"] = [
    (i["key"], i["column"], i["count"], i["severity"])
    for i in call("dataset.quality", {"id": d20})["issues"]
    if i["key"] == "weights_normalised" or i["severity"] == "warning"
]
E["checks"] = [(i["key"], i["name"]) for i in call("report.checks")["items"] if i["severity"] == "warning"]

# Bangladesh: Kobo labels, quality, merge and refused merge (scenarios 12 to 15).
fb = D / "03_bangladesh_wash_2018_reference.xlsx"
ib = call("dataset.inspect", {"path": str(fb)})
s = call("dataset.import", {"path": str(fb), "name": "Ménages", "sheet": "Dataset", "form": ib["form"]})
hb = s["created"]
ds = next(d for d in s["datasets"] if d["id"] == hb)
E["bgd_labels"] = {
    "columns": len(ds["labels"]["columns"]),
    "values": len(ds["labels"]["values"]),
    "form": ib["form"],
    "cols": len(ds["columns"]),
}
issues = call("dataset.quality", {"id": hb})["issues"]
E["bgd_quality"] = [(i["key"], i["column"], i["count"]) for i in issues if i["severity"] == "warning"]
fix = next(i for i in issues if i["key"] == "duplicate_id")
call("cleaning.add", {"dataset_id": hb, "rule": {**fix["fix"], "note": "doublons"}})
E["bgd_after_dedupe"] = next(d for d in call("project.get")["datasets"] if d["id"] == hb)["clean_rows"]
cb = call("dataset.import", {"path": str(fb), "name": "Contenants", "sheet": "Dataset_containergroup"})["created"]
keys = {"left_key": "_parent_index", "right_key": "_index", "dry_run": True}
E["merge"] = call("dataset.merge", {"left": cb, "right": hb, "how": "left", **keys})
ff = D / "04_bangladesh_wash_2018_suivi.xlsx"
hf = call("dataset.import", {"path": str(ff), "name": "Ménages suivi", "sheet": "Household Dataset"})["created"]
pf = call("dataset.import", {"path": str(ff), "name": "Individus suivi", "sheet": "Individuals Dataset"})["created"]
try:
    call("dataset.merge", {"left": pf, "right": hf, **keys})
    E["refusal"] = None
except RuntimeError as exc:
    E["refusal"] = str(exc)
for ext in ("sav", "dta"):
    s = call("dataset.import", {"path": str(D / f"05_bangladesh_wash_2018_extrait.{ext}"), "name": ext})
    x = next(d for d in s["datasets"] if d["id"] == s["created"])
    E[ext] = {
        "rows": x["rows"],
        "cols": len(x["columns"]),
        "label_res_age": x["labels"]["columns"].get("res_age"),
        "drnk_2": x["labels"]["values"].get("drnk_wat", {}).get("2"),
    }
size = {"deff": 1.5, "response": 0.9}
E["sample1"] = call("tool.sample_size", {"goal": "estimate_prop", "p": 0.5, "margin": 0.05, **size})["n"]
E["sample2"] = call("tool.sample_size", {"goal": "compare_prop", "p": 0.5, "p2": 0.6, **size})["n"]
bridge.stop()
(KIT / "expected.json").write_text(json.dumps(E, ensure_ascii=False, indent=1, default=str), encoding="utf-8")
print(f"{len(E)} results written to {KIT / 'expected.json'}")
