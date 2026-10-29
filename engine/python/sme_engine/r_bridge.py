"""Bridge to the R statistical engine.

A persistent R process (worker.R) receives JSON commands, one per line, and
answers the same way. Data tables never travel as JSON: they are written as
Arrow IPC streams in the working directory and read by R with nanoarrow.
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
from typing import Any

import polars as pl

from .rpc import RpcError

log = logging.getLogger("sme_engine.r")

DEFAULT_TIMEOUT = 120.0
READY_TIMEOUT = 60.0


def find_rscript() -> str | None:
    """Locate Rscript: SME_RSCRIPT first (embedded R), then the PATH."""
    explicit = os.environ.get("SME_RSCRIPT")
    if explicit:
        return explicit if Path(explicit).exists() else None
    return shutil.which("Rscript")


def r_dir() -> Path:
    """Folder holding the R code (worker.R and R/)."""
    explicit = os.environ.get("SME_R_DIR")
    if explicit:
        return Path(explicit)
    return Path(__file__).resolve().parents[2] / "r"


class RBridge:
    def __init__(self, workdir: Path | None = None):
        self._proc: subprocess.Popen[str] | None = None
        self._responses: queue.Queue[dict[str, Any]] = queue.Queue()
        self._lock = threading.Lock()
        self._ids = itertools.count(1)
        self._ready: dict[str, Any] | None = None
        self.workdir = workdir or Path(tempfile.mkdtemp(prefix="sme-"))

    # Start and stop -----------------------------------------------------------

    def start(self) -> dict[str, Any]:
        if self._proc and self._proc.poll() is None and self._ready:
            return self._ready
        rscript = find_rscript()
        if not rscript:
            raise RpcError("R cannot be found.", data={"key": "r_not_found"})
        worker = r_dir() / "worker.R"
        if not worker.exists():
            raise RpcError(f"The R engine is incomplete: {worker} is missing.", data={"key": "r_incomplete"})
        log.info("Starting R: %s %s", rscript, worker)
        env = dict(os.environ)
        env.setdefault("R_LIBS_USER", "")  # ignore any personal R library
        self._proc = subprocess.Popen(
            [rscript, "--vanilla", str(worker), str(r_dir())],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            bufsize=1,
            env=env,
        )
        self._responses = queue.Queue()
        threading.Thread(target=self._read_stdout, daemon=True).start()
        threading.Thread(target=self._read_stderr, daemon=True).start()
        try:
            msg = self._responses.get(timeout=READY_TIMEOUT)
        except queue.Empty:
            self.stop()
            raise RpcError("R did not start in time.", data={"key": "r_start_timeout"}) from None
        if msg.get("ready") is not True:
            self.stop()
            raise RpcError("Unexpected R start message.", data={"key": "r_bad_start", "message": msg})
        self._ready = msg
        log.info("R ready: %s", msg.get("r_version"))
        return msg

    def stop(self) -> None:
        proc, self._proc, self._ready = self._proc, None, None
        if proc and proc.poll() is None:
            try:
                proc.stdin.close()  # type: ignore[union-attr]
                proc.wait(timeout=5)
            except Exception:  # noqa: BLE001
                proc.kill()

    # Stream readers -----------------------------------------------------------

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
                log.warning("Ignored R output: %s", line[:200])
        self._responses.put({"closed": True})

    def _read_stderr(self) -> None:
        proc = self._proc
        assert proc and proc.stderr
        for line in proc.stderr:
            log.info("[R] %s", line.rstrip())

    # Calls --------------------------------------------------------------------

    def call(self, fn: str, args: dict[str, Any] | None = None, timeout: float = DEFAULT_TIMEOUT) -> Any:
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
                log.error("Timeout for %s, restarting R", fn)
                self.stop()
                raise RpcError(f"R call {fn!r} exceeded {int(timeout)} s.", data={"key": "r_timeout"}) from None
            if msg.get("closed"):
                self.stop()
                raise RpcError("The R engine stopped during the call.", data={"key": "r_stopped"})
            if msg.get("id") != req_id:
                self.stop()
                raise RpcError("R response out of sync.", data={"key": "r_desync", "message": msg})
            if "error" in msg:
                raise RpcError(str(msg["error"]), data={"key": "r_error"})
            return msg.get("result")

    def write_table(self, df: pl.DataFrame, name: str) -> str:
        """Write a table as an Arrow IPC stream for R and return its path."""
        self.workdir.mkdir(parents=True, exist_ok=True)
        path = self.workdir / f"{name}.arrows"
        # CompatLevel.oldest: classic Arrow strings (large_utf8) that nanoarrow can read.
        df.write_ipc_stream(path, compression="uncompressed", compat_level=pl.CompatLevel.oldest())
        return str(path)
