"""Tests du moteur Python et de la chaîne complète Python vers R."""

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
needs_r = pytest.mark.skipif(find_rscript() is None, reason="R non installé")


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


def test_methode_inconnue():
    server, _ = make_server()
    rep = call(server, "nexiste.pas")
    assert rep["error"]["code"] == -32601
    assert "Méthode inconnue" in rep["error"]["message"]


def test_requete_illisible():
    server, _ = make_server()
    rep = server.handle_line("{pas du json")
    assert rep["error"]["code"] == -32700


def test_parametre_invalide():
    server, _ = make_server()
    rep = call(server, "demo.proportion", {"design": "autre"})
    assert rep["error"]["code"] == -32602


@needs_r
def test_chaine_python_r_plan_enquete():
    server, bridge = make_server()
    try:
        rep = call(server, "demo.proportion", {"design": "survey"})
        res = rep["result"]
        assert 0 < res["ci_low"] < res["estimate"] < res["ci_high"] < 1
        assert res["n"] == 612
        assert "svyciprop" in res["script"]
    finally:
        bridge.stop()


@needs_r
def test_chaine_python_r_simple_egale_wilson():
    """L'intervalle simple doit être l'intervalle de Wilson, recalculé ici en Python."""
    server, bridge = make_server()
    try:
        res = call(server, "demo.proportion", {"design": "simple"})["result"]
        x, n, z = res["successes"], res["n"], 1.959963984540054
        p = x / n
        centre = (p + z * z / (2 * n)) / (1 + z * z / n)
        demi = z * ((p * (1 - p) / n + z * z / (4 * n * n)) ** 0.5) / (1 + z * z / n)
        assert res["estimate"] == pytest.approx(p, rel=1e-12)
        assert res["ci_low"] == pytest.approx(centre - demi, rel=1e-9)
        assert res["ci_high"] == pytest.approx(centre + demi, rel=1e-9)
    finally:
        bridge.stop()


@needs_r
def test_processus_complet_stdio():
    """Lance le moteur comme le fait l'application et dialogue avec lui."""
    proc = subprocess.Popen(
        [sys.executable, "-m", "sme_engine"], cwd=ENGINE_DIR,
        stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
        text=True, encoding="utf-8", env={**os.environ, "PYTHONPATH": str(ENGINE_DIR)},
    )
    try:
        for i, method in enumerate(["system.ping", "system.versions", "r.ping"], start=1):
            proc.stdin.write(json.dumps({"jsonrpc": "2.0", "id": i, "method": method}) + "\n")
            proc.stdin.flush()
            rep = json.loads(proc.stdout.readline())
            assert rep["id"] == i and "result" in rep, rep
        assert rep["result"] == {"pong": True}
    finally:
        proc.stdin.close()
        proc.wait(timeout=20)
