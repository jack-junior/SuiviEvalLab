# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 GAYI Komi Selassi and SANOUSSI Moudjibou

"""SuiviEvalLab relay server (section 7.2, server mode).

It keeps the synchronisation files the members of a project send, and hands
them to the other members. The files are signed by their authors and encrypted
with the key of the project: the server can neither read them nor make valid
ones. It only checks the access key of each project.

Run:  python relay.py --data /srv/suivievallab --port 8470
Keys: one line per project in <data>/keys.txt, "<project uid> <access key>".
Put it behind an HTTPS reverse proxy (Caddy, nginx, IIS).

Requires Python 3.10 or later, no other package.
"""

from __future__ import annotations

import argparse
import hmac
import json
import re
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

UID = re.compile(r"^[0-9a-f]{32}$")
MAX_FILE = 200 * 1024 * 1024
LOCK = threading.Lock()


class Store:
    def __init__(self, root: Path):
        self.root = root
        root.mkdir(parents=True, exist_ok=True)

    def keys(self) -> dict[str, str]:
        out = {}
        try:
            for line in (self.root / "keys.txt").read_text(encoding="utf-8").splitlines():
                parts = line.split()
                if len(parts) == 2 and UID.match(parts[0]):
                    out[parts[0]] = parts[1]
        except OSError:
            pass
        return out

    def folder(self, uid: str) -> Path:
        d = self.root / uid
        d.mkdir(exist_ok=True)
        return d

    def index(self, uid: str) -> list[dict]:
        f = self.folder(uid) / "index.json"
        try:
            return json.loads(f.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return []

    def add(self, uid: str, author: str, data: bytes) -> int:
        with LOCK:
            items = self.index(uid)
            seq = (items[-1]["seq"] if items else 0) + 1
            (self.folder(uid) / f"{seq}.smesync").write_bytes(data)
            items.append({"seq": seq, "author": author[:64], "size": len(data)})
            tmp = self.folder(uid) / "index.tmp"
            tmp.write_text(json.dumps(items), encoding="utf-8")
            tmp.replace(self.folder(uid) / "index.json")
            return seq


def make_handler(store: Store):
    class Handler(BaseHTTPRequestHandler):
        server_version = "SuiviEvalLabRelay/1"

        def log_message(self, fmt, *args):  # no request bodies or keys in logs
            pass

        def _reply(self, code: int, body: bytes = b"", kind: str = "application/json") -> None:
            self.send_response(code)
            self.send_header("Content-Type", kind)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def _project(self) -> tuple[str, str] | None:
            m = re.match(r"^/v1/projects/([0-9a-f]{32})(/.*)$", self.path.split("?", 1)[0])
            if not m:
                self._reply(404)
                return None
            uid, rest = m.group(1), m.group(2)
            key = store.keys().get(uid)
            given = self.headers.get("Authorization", "").removeprefix("Bearer ").strip()
            if not key or not hmac.compare_digest(key, given):
                self._reply(401)
                return None
            return uid, rest

        def do_GET(self):  # noqa: N802
            got = self._project()
            if not got:
                return
            uid, rest = got
            if rest == "/files":
                query = self.path.split("?", 1)[1] if "?" in self.path else ""
                after = int(dict(x.split("=", 1) for x in query.split("&") if "=" in x).get("after", "0") or 0)
                items = [i for i in store.index(uid) if i["seq"] > after]
                return self._reply(200, json.dumps({"files": items}).encode())
            m = re.match(r"^/files/(\d+)$", rest)
            if m:
                f = store.folder(uid) / f"{int(m.group(1))}.smesync"
                if f.is_file():
                    return self._reply(200, f.read_bytes(), "application/octet-stream")
            self._reply(404)

        def do_POST(self):  # noqa: N802
            got = self._project()
            if not got:
                return
            uid, rest = got
            if rest != "/files":
                return self._reply(404)
            size = int(self.headers.get("Content-Length", "0") or 0)
            if size <= 0 or size > MAX_FILE:
                return self._reply(413)
            data = self.rfile.read(size)
            if not data.startswith(b"SMESYNC"):  # a synchronisation file, whatever its version
                return self._reply(400)
            seq = store.add(uid, self.headers.get("X-Author", ""), data)
            self._reply(201, json.dumps({"seq": seq}).encode())

    return Handler


def serve(root: Path, host: str, port: int) -> ThreadingHTTPServer:
    return ThreadingHTTPServer((host, port), make_handler(Store(root)))


def main() -> None:
    ap = argparse.ArgumentParser(description="SuiviEvalLab relay server")
    ap.add_argument("--data", required=True, type=Path)
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--port", default=8470, type=int)
    a = ap.parse_args()
    httpd = serve(a.data, a.host, a.port)
    print(f"Relay listening on {a.host}:{a.port}, data in {a.data}")
    httpd.serve_forever()


if __name__ == "__main__":
    main()
