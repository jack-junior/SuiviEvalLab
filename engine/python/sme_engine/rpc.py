"""Line-delimited JSON-RPC 2.0 server over stdin and stdout.

Error messages are in English and meant for logs. Errors the interface shows
carry a translation key in `data.key`; the interface owns the wording.
"""

from __future__ import annotations

import json
import logging
import sys
import threading
import traceback
from collections.abc import Callable
from typing import IO, Any

log = logging.getLogger("sme_engine.rpc")

# Standard JSON-RPC error codes, plus our own (range -32000 to -32099).
PARSE_ERROR = -32700
INVALID_REQUEST = -32600
METHOD_NOT_FOUND = -32601
INVALID_PARAMS = -32602
INTERNAL_ERROR = -32603
ENGINE_ERROR = -32000


class RpcError(Exception):
    """Error sent back to the client with a readable message."""

    def __init__(self, message: str, code: int = ENGINE_ERROR, data: Any = None):
        super().__init__(message)
        self.code = code
        self.data = data


Handler = Callable[[dict[str, Any]], Any]


class Server:
    def __init__(self, stdin: IO[str] = sys.stdin, stdout: IO[str] = sys.stdout):
        self._stdin = stdin
        self._stdout = stdout
        self._methods: dict[str, Handler] = {}
        self._write_lock = threading.Lock()

    def method(self, name: str) -> Callable[[Handler], Handler]:
        def register(fn: Handler) -> Handler:
            self._methods[name] = fn
            return fn

        return register

    def notify(self, method: str, params: dict[str, Any]) -> None:
        """Send a notification (for example progress) to the client."""
        self._write({"jsonrpc": "2.0", "method": method, "params": params})

    def _write(self, message: dict[str, Any]) -> None:
        line = json.dumps(message, ensure_ascii=False, allow_nan=False)
        with self._write_lock:
            self._stdout.write(line + "\n")
            self._stdout.flush()

    def handle_line(self, line: str) -> dict[str, Any] | None:
        """Handle one request line and return the response (None for a notification)."""
        try:
            request = json.loads(line)
        except json.JSONDecodeError as exc:
            return _error(None, PARSE_ERROR, f"Unreadable request: {exc.msg}")

        if not isinstance(request, dict) or request.get("jsonrpc") != "2.0" or "method" not in request:
            return _error(
                request.get("id") if isinstance(request, dict) else None, INVALID_REQUEST, "Invalid JSON-RPC request"
            )

        req_id = request.get("id")
        name = request["method"]
        params = request.get("params") or {}
        if not isinstance(params, dict):
            return _error(req_id, INVALID_PARAMS, "Params must be an object")

        handler = self._methods.get(name)
        if handler is None:
            return _error(req_id, METHOD_NOT_FOUND, f"Unknown method: {name}")

        try:
            result = handler(params)
        except RpcError as exc:
            return _error(req_id, exc.code, str(exc), exc.data)
        except Exception as exc:  # noqa: BLE001 - the engine must never crash on a request
            log.error("Internal error in %s\n%s", name, traceback.format_exc())
            return _error(req_id, INTERNAL_ERROR, f"Internal error: {exc}", {"key": "internal"})

        if req_id is None:
            return None
        return {"jsonrpc": "2.0", "id": req_id, "result": result}

    def serve_forever(self) -> None:
        log.info("Engine ready, %d methods", len(self._methods))
        for line in self._stdin:
            line = line.strip()
            if not line:
                continue
            response = self.handle_line(line)
            if response is not None:
                self._write(response)
        log.info("Input closed, engine stopping")


def _error(req_id: Any, code: int, message: str, data: Any = None) -> dict[str, Any]:
    err: dict[str, Any] = {"code": code, "message": message}
    if data is not None:
        err["data"] = data
    return {"jsonrpc": "2.0", "id": req_id, "error": err}
