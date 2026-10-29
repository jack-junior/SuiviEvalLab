"""Test de fumée : lance le moteur comme l'application installée et vérifie la chaîne complète.

    python tools/smoke_test.py --python build/runtime/python/python.exe --rscript build/runtime/R/bin/Rscript.exe

Sans argument, utilise le Python courant et le Rscript du PATH.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--python", default=sys.executable)
    ap.add_argument("--rscript", default=None)
    ap.add_argument("--rdir", default=str(ROOT / "engine" / "r"),
                    help="Dossier du moteur R (worker.R et R/)")
    a = ap.parse_args()

    env = dict(os.environ, PYTHONIOENCODING="utf-8", SME_R_DIR=str(Path(a.rdir).resolve()),
               PYTHONPATH=str(ROOT / "engine" / "python"))
    if a.rscript:
        env["SME_RSCRIPT"] = str(Path(a.rscript).resolve())

    proc = subprocess.Popen(
        [a.python, "-X", "utf8", "-m", "sme_engine"], cwd=ROOT / "engine" / "python", env=env,
        stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True, encoding="utf-8",
    )
    requests = [
        ("system.ping", {}),
        ("system.versions", {}),
        ("demo.proportion", {"design": "simple"}),
        ("demo.proportion", {"design": "survey"}),
    ]
    ok = True
    for i, (method, params) in enumerate(requests, start=1):
        proc.stdin.write(json.dumps({"jsonrpc": "2.0", "id": i, "method": method, "params": params}) + "\n")
        proc.stdin.flush()
        rep = json.loads(proc.stdout.readline())
        resume = json.dumps(rep.get("result", rep.get("error")), ensure_ascii=False)
        print(method, resume[:300])
        if os.environ.get("GITHUB_ACTIONS"):
            # Annotation visible dans le résumé de la construction.
            court = resume if method != "demo.proportion" else (
                f"estimation {rep['result']['estimate']:.4f}, IC [{rep['result']['ci_low']:.4f} ; "
                f"{rep['result']['ci_high']:.4f}], n {rep['result']['n']}" if "result" in rep else resume)
            print(f"::notice title=Test de fumée {method}::{court[:400]}")
        if "error" in rep or (method == "system.versions" and "r_error" in rep["result"]):
            ok = False
        if method == "demo.proportion" and "result" in rep:
            r = rep["result"]
            ok = ok and r["n"] == 612 and 0 < r["ci_low"] < r["estimate"] < r["ci_high"] < 1
    proc.stdin.close()
    proc.wait(timeout=30)
    print("SUCCÈS" if ok else "ÉCHEC")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
