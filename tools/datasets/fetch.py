"""Download the original HDX survey files used by the robustness tests.

    python tools/datasets/fetch.py <folder>

Each file is checked against the SHA-256 recorded in sources.json; files already
present with the right hash are kept. The licences are listed in sources.json.
"""

import hashlib
import json
import sys
import urllib.request
from pathlib import Path

folder = Path(sys.argv[1])
folder.mkdir(parents=True, exist_ok=True)
sources = json.loads((Path(__file__).parent / "sources.json").read_text(encoding="utf-8"))
for s in sources:
    target = folder / f"{s['id']}.xlsx"
    if target.exists() and hashlib.sha256(target.read_bytes()).hexdigest() == s["sha256"]:
        print(f"{target.name}: cached")
        continue
    req = urllib.request.Request(s["url"], headers={"User-Agent": "SuiviEvalLab-tests"})
    with urllib.request.urlopen(req, timeout=300) as r:
        data = r.read()
    digest = hashlib.sha256(data).hexdigest()
    if digest != s["sha256"]:
        sys.exit(f"{s['id']}: unexpected SHA-256 {digest}, the published file changed")
    target.write_bytes(data)
    print(f"{target.name}: downloaded, {len(data)} bytes")
