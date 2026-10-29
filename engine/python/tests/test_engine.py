"""Tests for the Python engine and the full Python to R chain."""

from __future__ import annotations

import io
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from sme_engine.methods import register
from sme_engine.r_bridge import RBridge, find_rscript
from sme_engine.rpc import Server

ENGINE_DIR = Path(__file__).resolve().parents[1]
needs_r = pytest.mark.skipif(find_rscript() is None, reason="R not installed")


def make_server():
    bridge = RBridge()
    server = Server(stdin=io.StringIO(), stdout=io.StringIO())
    register(server, bridge)
    return server, bridge


def call(server, method, params=None, req_id=1):
    line = json.dumps({"jsonrpc": "2.0", "id": req_id, "method": method, "params": params or {}})
    return server.handle_line(line)


def test_ping():
    server, _ = make_server()
    assert call(server, "system.ping") == {"jsonrpc": "2.0", "id": 1, "result": {"pong": True}}


def test_unknown_method():
    server, _ = make_server()
    resp = call(server, "does.not.exist")
    assert resp["error"]["code"] == -32601
    assert "Unknown method" in resp["error"]["message"]


def test_unreadable_request():
    server, _ = make_server()
    resp = server.handle_line("{not json")
    assert resp["error"]["code"] == -32700


def test_invalid_params():
    server, _ = make_server()
    resp = call(server, "demo.proportion", {"design": "other"})
    assert resp["error"]["code"] == -32602
    assert resp["error"]["data"]["key"] == "invalid_design"


@needs_r
def test_python_r_chain_survey_design():
    server, bridge = make_server()
    try:
        resp = call(server, "demo.proportion", {"design": "survey"})
        res = resp["result"]
        assert 0 < res["ci_low"] < res["estimate"] < res["ci_high"] < 1
        assert res["n"] == 612
        assert "svyciprop" in res["script"]
        assert res["method_key"] == "survey_logit"
    finally:
        bridge.stop()


@needs_r
def test_python_r_chain_simple_matches_wilson():
    """The simple interval must equal the Wilson interval, recomputed here in Python."""
    server, bridge = make_server()
    try:
        res = call(server, "demo.proportion", {"design": "simple"})["result"]
        assert res["method_key"] == "wilson"
        x, n, z = res["successes"], res["n"], 1.959963984540054
        p = x / n
        center = (p + z * z / (2 * n)) / (1 + z * z / n)
        half = z * ((p * (1 - p) / n + z * z / (4 * n * n)) ** 0.5) / (1 + z * z / n)
        assert res["estimate"] == pytest.approx(p, rel=1e-12)
        assert res["ci_low"] == pytest.approx(center - half, rel=1e-9)
        assert res["ci_high"] == pytest.approx(center + half, rel=1e-9)
    finally:
        bridge.stop()


@needs_r
def test_full_process_over_stdio():
    """Start the engine the way the app does and talk to it."""
    proc = subprocess.Popen(
        [sys.executable, "-m", "sme_engine"],
        cwd=ENGINE_DIR,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        text=True,
        encoding="utf-8",
        env={**os.environ, "PYTHONPATH": str(ENGINE_DIR)},
    )
    try:
        for i, method in enumerate(["system.ping", "system.versions", "r.ping"], start=1):
            proc.stdin.write(json.dumps({"jsonrpc": "2.0", "id": i, "method": method}) + "\n")
            proc.stdin.flush()
            resp = json.loads(proc.stdout.readline())
            assert resp["id"] == i and "result" in resp, resp
        assert resp["result"] == {"pong": True}
    finally:
        proc.stdin.close()
        proc.wait(timeout=20)
