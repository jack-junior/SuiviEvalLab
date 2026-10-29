# 0002. Arrow IPC with nanoarrow for Python to R tables

- Status: accepted
- Date: 2026-10-29

## Context
Tables can reach hundreds of thousands of rows. JSON is slow and loses types. The `arrow` R package is heavy to embed.

## Decision
Python writes Arrow IPC streams with polars (`write_ipc_stream`, uncompressed, `CompatLevel.oldest()` so strings are classic `large_utf8`). R reads them with the lightweight `nanoarrow` package (`read_nanoarrow`).

## Consequences
Fast, typed exchange with a small R dependency. Newer Arrow types (string views) must not be used until nanoarrow supports them; the compatibility level enforces this.
