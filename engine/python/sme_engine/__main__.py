"""Point d'entrée : python -m sme_engine"""

from __future__ import annotations

import io
import logging
import sys

from .methods import register
from .r_bridge import RBridge
from .rpc import Server


def main() -> None:
    # Toujours de l'UTF-8 sur les flux, y compris sous Windows.
    stdin = io.TextIOWrapper(sys.stdin.buffer, encoding="utf-8")
    stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", line_buffering=True)
    sys.stdin = stdin
    logging.basicConfig(
        stream=io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", line_buffering=True),
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s : %(message)s",
    )
    bridge = RBridge()
    server = Server(stdin=stdin, stdout=stdout)
    register(server, bridge)
    try:
        server.serve_forever()
    finally:
        bridge.stop()


if __name__ == "__main__":
    main()
