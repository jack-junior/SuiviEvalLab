# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 GAYI Komi Selassi and SANOUSSI Moudjibou

"""R code trusted on this computer.

An R script in a project runs only if its exact text has been accepted on this
computer: written here, or shown to the user and accepted ("Trust this code?").
The list lives in the user's folder, never in the project file, so a project
received from someone else cannot mark its own code as trusted.
"""

from __future__ import annotations

import hashlib
import json
import os
import threading
from pathlib import Path

_lock = threading.Lock()


def path() -> Path:
    env = os.environ.get("SME_TRUST_DIR")
    base = Path(env) if env else Path.home() / ".suivievallab"
    return base / "trusted-r.json"


def digest(code: str) -> str:
    return hashlib.sha256(code.replace("\r\n", "\n").strip().encode("utf-8")).hexdigest()


def _load() -> set[str]:
    try:
        data = json.loads(path().read_text(encoding="utf-8"))
        return {h for h in data.get("sha256", []) if isinstance(h, str)}
    except (OSError, ValueError):
        return set()


def is_trusted(code: str) -> bool:
    with _lock:
        return digest(code) in _load()


def trust(codes: list[str]) -> None:
    with _lock:
        known = _load() | {digest(c) for c in codes}
        p = path()
        p.parent.mkdir(parents=True, exist_ok=True)
        tmp = p.with_suffix(".tmp")
        tmp.write_text(json.dumps({"sha256": sorted(known)}, indent=1), encoding="utf-8")
        tmp.replace(p)
