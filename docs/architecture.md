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
| Project file (SQLite `.sme`), import, data cleaning, Word report, orchestration | Python engine |
| Indicators, confidence intervals, survey designs, tests, report charts, reproducible R scripts | R engine |

## Key files

| Path | Role |
|---|---|
| `apps/desktop/src/main/main.ts` | Window, engine launch (dev vs installed), IPC allowlist |
| `apps/desktop/src/main/engine.ts` | JSON-RPC client for the Python engine |
| `apps/desktop/src/main/preload.ts` | `window.sme` bridge exposed to the interface |
| `apps/desktop/src/renderer/` | React interface: `App.tsx` (shell), `screens/`, `ui.tsx`, `state.tsx`, `i18n/` |
| `engine/python/sme_engine/rpc.py` | JSON-RPC server |
| `engine/python/sme_engine/r_bridge.py` | Persistent R worker, Arrow IPC exchange |
| `engine/python/sme_engine/methods.py` | System and demo methods; registers the others |
| `engine/python/sme_engine/service.py` | Project, framework, indicator, data, cleaning, analysis and report methods |
| `engine/python/sme_engine/project.py` | `.sme` file: SQLite schema, framework tree, positioned JSON records |
| `engine/python/sme_engine/datasets.py` | Excel, Kobo, CSV, SPSS and Stata import (everything kept as text), column description, design guess |
| `engine/python/sme_engine/xlsform.py` | Labels from a Kobo or ODK questionnaire (XLSForm), in several languages |
| `engine/python/sme_engine/merge.py` | Merged datasets: many-to-one join of two cleaned datasets by a key |
| `engine/python/sme_engine/stattests.py` | Test assistant: validation, data preparation, conclusions in words |
| `engine/python/sme_engine/share.py` | Read-only HTML dashboard (aggregated results only) |
| `engine/python/sme_engine/quality.py` | Data quality diagnosis, with a proposed cleaning rule per issue |
| `engine/python/sme_engine/checks.py` | Checks before the report |
| `engine/python/sme_engine/plan.py` | Monitoring plan workbook (xlsxwriter) |
| `engine/python/sme_engine/backups.py` | Automatic project copies at opening, and restore |
| `engine/python/sme_engine/cleaning.py` | Cleaning journal: four rule kinds applied in order to a copy of the raw data |
| `engine/python/sme_engine/indicators.py` | Indicator validation, achievement rate and status |
| `engine/python/sme_engine/report.py` | Word report (python-docx), French and English text, on the built-in layout or the organisation's template |
| `engine/python/sme_engine/example.py` | Example project on real REACH data (`examples/`) |
| `engine/r/worker.R` | R command loop |
| `engine/r/R/*.R` | Statistical functions (`sme_*`) |
| `tools/windows/prepare-runtimes.ps1` | Embedded Python and R for the installer |

## Project file

A project is one SQLite file with the `.sme` extension (`PRAGMA application_id` marks it). Every change is written at once; there is no save button. Tables: `meta`, `framework_node`, `indicator`, `dataset` (the raw table as Parquet, never modified), `cleaning_rule` and `saved_test`. Indicators, datasets, rules and tests keep their settings as JSON in a `spec` column, validated by the Python engine. Cleaned data and results are recomputed from the raw data and the journal, and cached in memory. The schema has a version number (2 since 0.3); older files are migrated when opened.

A merged dataset stores no rows: they are joined from the cleaned data of its two sources whenever those change, then its own journal applies. A source used by a merge cannot be deleted. Labels (XLSForm, SPSS or Stata metadata, or typed by the user) live in the dataset spec; codes stay the reference for every calculation. The organisation's Word template is kept in `meta`, so the project file carries it.

Each opening copies the project (SQLite backup API, before any migration) into `SME_BACKUP_DIR`, set by the host to the user's application folder; the last ten copies of each project are kept, and a restore first copies the current state.

## Files and the interface

The interface never sends a file path. File dialogs run in the host (`dialog:pick`), which returns a token; the host swaps the token for the path when the engine is called (`file_token`). End-to-end tests answer dialogs through `SME_E2E_DIALOGS`.

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
