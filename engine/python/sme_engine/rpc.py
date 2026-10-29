"""Serveur JSON-RPC 2.0 ligne par ligne, sur l'entrée et la sortie standard."""

from __future__ import annotations

import json
import logging
import sys
import threading
import traceback
from typing import Any, Callable, Dict, IO, Optional

log = logging.getLogger("sme_engine.rpc")

# Codes d'erreur JSON-RPC standard, plus les nôtres (plage -32000 à -32099).
PARSE_ERROR = -32700
INVALID_REQUEST = -32600
METHOD_NOT_FOUND = -32601
INVALID_PARAMS = -32602
INTERNAL_ERROR = -32603
ENGINE_ERROR = -32000


class RpcError(Exception):
    """Erreur renvoyée proprement au client, avec un message lisible."""

    def __init__(self, message: str, code: int = ENGINE_ERROR, data: Any = None):
        super().__init__(message)
        self.code = code
        self.data = data


Handler = Callable[[Dict[str, Any]], Any]


class Server:
    def __init__(self, stdin: IO[str] = sys.stdin, stdout: IO[str] = sys.stdout):
        self._stdin = stdin
        self._stdout = stdout
        self._methods: Dict[str, Handler] = {}
        self._write_lock = threading.Lock()

    def method(self, name: str) -> Callable[[Handler], Handler]:
        def register(fn: Handler) -> Handler:
            self._methods[name] = fn
            return fn

        return register

    def notify(self, method: str, params: Dict[str, Any]) -> None:
        """Envoie une notification (par exemple une progression) au client."""
        self._write({"jsonrpc": "2.0", "method": method, "params": params})

    def _write(self, message: Dict[str, Any]) -> None:
        line = json.dumps(message, ensure_ascii=False, allow_nan=False)
        with self._write_lock:
            self._stdout.write(line + "\n")
            self._stdout.flush()

    def handle_line(self, line: str) -> Optional[Dict[str, Any]]:
        """Traite une ligne et renvoie la réponse (None pour une notification)."""
        try:
            request = json.loads(line)
        except json.JSONDecodeError as exc:
            return _error(None, PARSE_ERROR, f"Requête illisible : {exc.msg}")

        if not isinstance(request, dict) or request.get("jsonrpc") != "2.0" or "method" not in request:
            return _error(request.get("id") if isinstance(request, dict) else None,
                          INVALID_REQUEST, "Requête JSON-RPC invalide")

        req_id = request.get("id")
        name = request["method"]
        params = request.get("params") or {}
        if not isinstance(params, dict):
            return _error(req_id, INVALID_PARAMS, "Les paramètres doivent être un objet")

        handler = self._methods.get(name)
        if handler is None:
            return _error(req_id, METHOD_NOT_FOUND, f"Méthode inconnue : {name}")

        try:
            result = handler(params)
        except RpcError as exc:
            return _error(req_id, exc.code, str(exc), exc.data)
        except Exception as exc:  # noqa: BLE001 - on ne laisse jamais tomber le moteur
            log.error("Erreur interne dans %s\n%s", name, traceback.format_exc())
            return _error(req_id, INTERNAL_ERROR, f"Erreur interne : {exc}")

        if req_id is None:
            return None
        return {"jsonrpc": "2.0", "id": req_id, "result": result}

    def serve_forever(self) -> None:
        log.info("Moteur prêt, %d méthodes", len(self._methods))
        for line in self._stdin:
            line = line.strip()
            if not line:
                continue
            response = self.handle_line(line)
            if response is not None:
                self._write(response)
        log.info("Entrée fermée, arrêt du moteur")


def _error(req_id: Any, code: int, message: str, data: Any = None) -> Dict[str, Any]:
    err: Dict[str, Any] = {"code": code, "message": message}
    if data is not None:
        err["data"] = data
    return {"jsonrpc": "2.0", "id": req_id, "error": err}
