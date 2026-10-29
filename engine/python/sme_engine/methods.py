"""Methods exposed to the desktop app."""

from __future__ import annotations

import platform
import sys
from typing import Any

import polars as pl

from . import __version__, demo, service
from .project import Workspace
from .r_bridge import RBridge
from .rpc import INVALID_PARAMS, RpcError, Server


def register(server: Server, bridge: RBridge) -> None:
    service.register(server, Workspace(), bridge)

    @server.method("system.ping")
    def ping(_: dict[str, Any]) -> dict[str, Any]:
        return {"pong": True}

    @server.method("system.versions")
    def versions(_: dict[str, Any]) -> dict[str, Any]:
        info: dict[str, Any] = {
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
    def r_ping(_: dict[str, Any]) -> Any:
        return bridge.call("ping")

    @server.method("demo.proportion")
    def demo_proportion(params: dict[str, Any]) -> Any:
        """Share of girls attending school, with or without a survey design."""
        design = params.get("design", "survey")
        if design not in ("simple", "survey"):
            raise RpcError('design must be "simple" or "survey"', INVALID_PARAMS, data={"key": "invalid_design"})
        df = demo.girls_6_11()
        path = bridge.write_table(df, "demo_girls")
        args: dict[str, Any] = {"path": path, "var": "scolarise", "success": "Oui", "level": 0.95}
        if design == "survey":
            args.update({"weights": "poids", "strata": "zone", "cluster": "village"})
        return bridge.call("proportion", args)

    @server.method("system.shutdown")
    def shutdown(_: dict[str, Any]) -> dict[str, Any]:
        bridge.stop()
        sys.stdin.close()
        return {"ok": True}
