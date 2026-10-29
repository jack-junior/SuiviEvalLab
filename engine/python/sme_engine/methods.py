"""Méthodes exposées à l'application de bureau."""

from __future__ import annotations

import platform
import sys
from typing import Any, Dict

import polars as pl

from . import __version__, demo
from .r_bridge import RBridge
from .rpc import INVALID_PARAMS, RpcError, Server


def register(server: Server, bridge: RBridge) -> None:
    @server.method("system.ping")
    def ping(_: Dict[str, Any]) -> Dict[str, Any]:
        return {"pong": True}

    @server.method("system.versions")
    def versions(_: Dict[str, Any]) -> Dict[str, Any]:
        info: Dict[str, Any] = {
            "engine": __version__,
            "python": platform.python_version(),
            "polars": pl.__version__,
            "platform": platform.platform(),
        }
        try:
            info["r"] = bridge.call("versions")
        except RpcError as exc:
            info["r_error"] = str(exc)
        return info

    @server.method("r.ping")
    def r_ping(_: Dict[str, Any]) -> Any:
        return bridge.call("ping")

    @server.method("demo.proportion")
    def demo_proportion(params: Dict[str, Any]) -> Any:
        """Proportion de filles scolarisées, avec ou sans plan d'enquête."""
        design = params.get("design", "survey")
        if design not in ("simple", "survey"):
            raise RpcError("design doit valoir « simple » ou « survey »", INVALID_PARAMS)
        df = demo.filles_6_11()
        path = bridge.write_table(df, "demo_filles")
        args: Dict[str, Any] = {"path": path, "var": "scolarise", "success": "Oui", "level": 0.95}
        if design == "survey":
            args.update({"weights": "poids", "strata": "zone", "cluster": "village"})
        return bridge.call("proportion", args)

    @server.method("system.shutdown")
    def shutdown(_: Dict[str, Any]) -> Dict[str, Any]:
        bridge.stop()
        sys.stdin.close()
        return {"ok": True}
