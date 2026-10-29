"""Search HDX for open household survey microdata usable as test material.

Writes a Markdown report (license, access, resources) to the path given as argument.
Only datasets with a direct public download and an open licence are of interest.
"""

import json
import sys
import urllib.parse
import urllib.request

API = "https://data.humdata.org/api/3/action/"
QUERIES = [
    "multi-sector needs assessment household dataset",
    "msna dataset reach",
    "mcna dataset reach",
    "education household survey dataset",
    "school attendance household survey",
    "baseline endline survey dataset",
    "kobo dataset household",
]


def get(action, **params):
    url = API + action + "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers={"User-Agent": "SuiviEvalLab-test-material/0.1"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.load(r)["result"]


seen = {}
for q in QUERIES:
    try:
        res = get("package_search", q=q, rows=40, fq="res_format:XLSX OR res_format:CSV")
    except Exception as exc:  # noqa: BLE001
        print(f"query failed: {q}: {exc}")
        continue
    for ds in res["results"]:
        seen.setdefault(ds["name"], ds)

lines = ["# HDX candidates", ""]
for name, ds in sorted(seen.items(), key=lambda kv: kv[1].get("metadata_modified", ""), reverse=True):
    if ds.get("is_requestdata_type"):
        continue
    lic = ds.get("license_title") or ds.get("license_id")
    org = (ds.get("organization") or {}).get("title", "")
    lines.append(f"## {ds.get('title')}")
    lines.append(f"- id: `{name}`  org: {org}  licence: {lic}  modified: {ds.get('metadata_modified', '')[:10]}")
    lines.append(f"- dataset date: {ds.get('dataset_date', '')}  locations: {', '.join(g['name'] for g in ds.get('groups', []))}")
    for r in ds.get("resources", []):
        lines.append(f"  - {r.get('format')} {r.get('size') or '?'} B: {r.get('name')} <{r.get('url')}>")
    lines.append("")

open(sys.argv[1], "w", encoding="utf-8").write("\n".join(lines))
print(f"{len(seen)} datasets found")
