# Architecture

## Overview

```
Interface (Electron renderer, React + TypeScript)
        |  IPC through a typed preload, allowlisted methods
Host (Electron main process, TypeScript)
        |  JSON-RPC 2.0 over stdin/stdout, one message per line
Business engine (Python, embedded)
        |  JSON commands over stdin/stdout + Arrow IPC files for tables
Statistical engine (R, embedded, persistent process)
```

No component opens a network port. Each engine runs in its own process, so a crash in R never takes down the Python engine, and the host restarts the Python engine if it stops.

## Responsibilities

| Concern | Component |
|---|---|
| Screens, forms, previews | Interface |
| Window, menus, file dialogs, engine supervision, updates | Host |
| Project file (SQLite, planned), import, data cleaning, Word report, orchestration | Python engine |
| Indicators, confidence intervals, survey designs, tests, report charts, reproducible R scripts | R engine |

## Key files

| Path | Role |
|---|---|
| `apps/desktop/src/main/main.ts` | Window, engine launch (dev vs installed), IPC allowlist |
| `apps/desktop/src/main/engine.ts` | JSON-RPC client for the Python engine |
| `apps/desktop/src/main/preload.ts` | `window.sme` bridge exposed to the interface |
| `apps/desktop/src/renderer/` | React interface |
| `engine/python/sme_engine/rpc.py` | JSON-RPC server |
| `engine/python/sme_engine/r_bridge.py` | Persistent R worker, Arrow IPC exchange |
| `engine/python/sme_engine/methods.py` | Methods exposed to the interface |
| `engine/r/worker.R` | R command loop |
| `engine/r/R/*.R` | Statistical functions (`sme_*`) |
| `tools/windows/prepare-runtimes.ps1` | Embedded Python and R for the installer |

## Installed layout (Windows)

```
SuiviEvalLab/
  SuiviEvalLab.exe
  resources/
    app.asar                 interface and host
    python/                  embeddable Python 3.12 + site-packages
    R/                       R 4.4 + jsonlite, survey, nanoarrow
    engine/python/sme_engine business engine
    engine/r/                worker.R and R/
```

The embedded Python finds the engine through its `python312._pth` file (`..\engine\python`). The host sets `SME_RSCRIPT` and `SME_R_DIR` so the Python engine uses the embedded R and ignores any R installed on the machine.

## Adding an engine method

1. Write the R function in `engine/r/R/` (prefix `sme_`), returning a list with the result and its R script. Add it to `sme_dispatch` in `worker.R`. Test it against the direct R call.
2. Expose it in `engine/python/sme_engine/methods.py`; write tables with `bridge.write_table`. Add a pytest test.
3. Add the method name to the `ALLOWED` set in `apps/desktop/src/main/main.ts`.
4. Call it from the interface with `call<T>("method.name", params)` from `src/renderer/api.ts`.

## Planning documents

The full planning (vision, functional specification, data model, statistics catalogue, quality plan, roadmap) is summarised in [roadmap.md](roadmap.md) and [statistics.md](statistics.md). Decisions are recorded in [adr/](adr/).
