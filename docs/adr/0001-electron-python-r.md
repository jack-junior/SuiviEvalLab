# 0001. Electron interface, Python business engine, R statistical engine

- Status: accepted
- Date: 2026-10-29

## Context
The tool must be a desktop app that M&E officers use daily, offline, with statistical results that are methodologically sound and auditable. R is the reference for survey statistics; Python is stronger for file handling, data cleaning and filling existing Word templates; a web stack gives the richest interface.

## Decision
- Interface and host: Electron, React, TypeScript.
- Business engine: Python (polars, later docxtpl), owner of the project file.
- Statistical engine: R, a persistent process driven by Python. Every statistical computation runs in R.
- Engines communicate over stdin/stdout (JSON-RPC 2.0 for the Python engine, line-delimited JSON for R). No network ports. `rpy2` is not used, so an R crash cannot bring down Python.
- Python and R are embedded in the installer; users install nothing else.

## Consequences
Large installer (about 230 MB). Three languages to maintain, mitigated by a single JSON contract and tests at each boundary. Statistical results are reproducible as R scripts.
