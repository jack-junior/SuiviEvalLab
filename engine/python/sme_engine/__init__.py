# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 GAYI Komi Selassi and SANOUSSI Moudjibou

"""SuiviEvalLab business engine.

The engine is a child process started by the desktop app. It reads JSON-RPC 2.0
requests on stdin (one per line) and writes responses on stdout. Logs go to stderr.
"""

__version__ = "0.5.2"
