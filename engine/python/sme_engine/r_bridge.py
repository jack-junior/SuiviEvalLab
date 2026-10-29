"""Pont vers le moteur statistique R.

Un processus R persistant (worker.R) reçoit des commandes JSON, une par ligne,
et répond de la même façon. Les tableaux de données ne passent jamais en JSON :
ils sont écrits au format Arrow IPC dans le dossier de travail, et R les lit
avec le package nanoarrow.
"""

from __future__ import annotations

import itertools
import json
import logging
import os
import queue
import shutil
import subprocess
import tempfile
import threading
from pathlib import Path
from typing import Any, Dict, Optional

import polars as pl

from .rpc import RpcError

log = logging.getLogger("sme_engine.r")

DEFAULT_TIMEOUT = 120.0
READY_TIMEOUT = 60.0


def find_rscript() -> Optional[str]:
    """Trouve Rscript : variable SME_RSCRIPT d'abord (R embarqué), sinon le PATH."""
    explicit = os.environ.get("SME_RSCRIPT")
    if explicit:
        return explicit if Path(explicit).exists() else None
    return shutil.which("Rscript")


def r_dir() -> Path:
    """Dossier du code R de SuiviEvalLab (worker.R et R/)."""
    explicit = os.environ.get("SME_R_DIR")
    if explicit:
        return Path(explicit)
    return Path(__file__).resolve().parents[2] / "r"


class RBridge:
    def __init__(self, workdir: Optional[Path] = None):
        self._proc: Optional[subprocess.Popen[str]] = None
        self._responses: "queue.Queue[Dict[str, Any]]" = queue.Queue()
        self._lock = threading.Lock()
        self._ids = itertools.count(1)
        self._ready: Optional[Dict[str, Any]] = None
        self.workdir = workdir or Path(tempfile.mkdtemp(prefix="sme-"))

    # Démarrage et arrêt -------------------------------------------------

    def start(self) -> Dict[str, Any]:
        if self._proc and self._proc.poll() is None and self._ready:
            return self._ready
        rscript = find_rscript()
        if not rscript:
            raise RpcError("R est introuvable. Vérifiez l'installation de SuiviEvalLab.")
        worker = r_dir() / "worker.R"
        if not worker.exists():
            raise RpcError(f"Le moteur R est incomplet : {worker} manquant.")
        log.info("Démarrage de R : %s %s", rscript, worker)
        env = dict(os.environ)
        env.setdefault("R_LIBS_USER", "")  # ignorer une bibliothèque R personnelle
        self._proc = subprocess.Popen(
            [rscript, "--vanilla", str(worker), str(r_dir())],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            text=True, encoding="utf-8", bufsize=1, env=env,
        )
        self._responses = queue.Queue()
        threading.Thread(target=self._read_stdout, daemon=True).start()
        threading.Thread(target=self._read_stderr, daemon=True).start()
        try:
            msg = self._responses.get(timeout=READY_TIMEOUT)
        except queue.Empty:
            self.stop()
            raise RpcError("R n'a pas démarré à temps.")
        if msg.get("ready") is not True:
            self.stop()
            raise RpcError("R a renvoyé un message de démarrage inattendu.", data=msg)
        self._ready = msg
        log.info("R prêt : %s", msg.get("r_version"))
        return msg

    def stop(self) -> None:
        proc, self._proc, self._ready = self._proc, None, None
        if proc and proc.poll() is None:
            try:
                proc.stdin.close()  # type: ignore[union-attr]
                proc.wait(timeout=5)
            except Exception:  # noqa: BLE001
                proc.kill()

    # Lecture des flux ------------------------------------------------------

    def _read_stdout(self) -> None:
        proc = self._proc
        assert proc and proc.stdout
        for line in proc.stdout:
            line = line.strip()
            if not line:
                continue
            try:
                self._responses.put(json.loads(line))
            except json.JSONDecodeError:
                log.warning("Sortie R ignorée : %s", line[:200])
        self._responses.put({"closed": True})

    def _read_stderr(self) -> None:
        proc = self._proc
        assert proc and proc.stderr
        for line in proc.stderr:
            log.info("[R] %s", line.rstrip())

    # Appels -----------------------------------------------------------------

    def call(self, fn: str, args: Optional[Dict[str, Any]] = None,
             timeout: float = DEFAULT_TIMEOUT) -> Any:
        with self._lock:
            self.start()
            assert self._proc and self._proc.stdin
            req_id = next(self._ids)
            payload = json.dumps({"id": req_id, "fn": fn, "args": args or {}}, ensure_ascii=False)
            self._proc.stdin.write(payload + "\n")
            self._proc.stdin.flush()
            try:
                msg = self._responses.get(timeout=timeout)
            except queue.Empty:
                log.error("Délai dépassé pour %s, redémarrage de R", fn)
                self.stop()
                raise RpcError(f"Le calcul R « {fn} » a dépassé {int(timeout)} s.")
            if msg.get("closed"):
                self.stop()
                raise RpcError("Le moteur R s'est arrêté pendant le calcul.")
            if msg.get("id") != req_id:
                self.stop()
                raise RpcError("Réponse R désynchronisée.", data=msg)
            if "error" in msg:
                raise RpcError(f"Erreur R : {msg['error']}")
            return msg.get("result")

    def write_table(self, df: pl.DataFrame, name: str) -> str:
        """Écrit un tableau au format Arrow IPC (flux) pour R et renvoie son chemin."""
        self.workdir.mkdir(parents=True, exist_ok=True)
        path = self.workdir / f"{name}.arrows"
        # CompatLevel.oldest : chaînes Arrow classiques (large_utf8), lisibles par nanoarrow.
        df.write_ipc_stream(path, compression="uncompressed", compat_level=pl.CompatLevel.oldest())
        return str(path)
