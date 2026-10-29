"""Download the test datasets listed in sources.json and describe their structure."""

import hashlib
import json
import sys
import urllib.request
from pathlib import Path

import openpyxl

out_dir = Path(sys.argv[1])
out_dir.mkdir(parents=True, exist_ok=True)
sources = json.loads(Path("tools/datasets/sources.json").read_text(encoding="utf-8"))
report = ["# Test dataset structure", ""]
for s in sources:
    target = out_dir / (s["id"] + ".xlsx")
    req = urllib.request.Request(s["url"], headers={"User-Agent": "SuiviEvalLab-test-material/0.1"})
    with urllib.request.urlopen(req, timeout=300) as r:
        target.write_bytes(r.read())
    sha = hashlib.sha256(target.read_bytes()).hexdigest()
    s["sha256"] = sha
    s["bytes"] = target.stat().st_size
    report += [f"## {s['id']}", f"{s['title']}  ", f"{s['bytes']} bytes, sha256 `{sha}`", ""]
    wb = openpyxl.load_workbook(target, read_only=True)
    for ws in wb.worksheets:
        rows = ws.iter_rows(values_only=True)
        header = next(rows, ()) or ()
        sample = [next(rows, None) for _ in range(3)]
        n = 1 + 3 + sum(1 for _ in rows)
        report.append(f"### sheet `{ws.title}`: about {n} rows, {len(header)} columns")
        report.append("")
        for i, col in enumerate(header):
            vals = [str(r[i])[:40] if r and i < len(r) and r[i] is not None else "" for r in sample]
            report.append(f"- `{col}`: {' | '.join(vals)}")
        report.append("")
Path(out_dir / "sources.lock.json").write_text(json.dumps(sources, indent=2), encoding="utf-8")
Path("tools/datasets/structure.md").write_text("\n".join(report), encoding="utf-8")
