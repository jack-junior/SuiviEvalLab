"""R code written by the user, run in its own R process.

Each run starts a fresh Rscript in a temporary folder, so the code cannot
disturb the statistical engine (worker.R) and leaves nothing behind. The table
goes to R as an Arrow file and comes back as CSV.

Cleaning step: the code receives `data` (numbers already as numbers) and changes
it. Each row keeps its number in `.sme_row`; keep that column if rows are
reordered or removed, so that cells corrected by hand still find their row.
Values the code did not change keep their original text (01 stays 01).

Analysis: the code receives `data` and, when the dataset has a sampling design,
`plan` (a survey design object from the survey package). Printed output, plots
and a data frame left in `resultat` (or `result`) are returned.
"""

from __future__ import annotations

import base64
import os
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Any

import polars as pl

from .cleaning_free import ROW
from .r_bridge import find_rscript
from .rpc import RpcError

TIMEOUT = 300
NA = "\u0001"
MAX_LOG = 20_000

_PRELUDE = r"""
options(warn = 1, width = 110, OutDec = ".")
suppressPackageStartupMessages(library(nanoarrow))
.sme_dir <- commandArgs(trailingOnly = TRUE)[[1]]
.sme_in <- as.data.frame(nanoarrow::read_nanoarrow(file.path(.sme_dir, "in.arrows")))
.sme_in[] <- lapply(.sme_in, function(x) if (is.character(x)) utils::type.convert(x, as.is = TRUE) else x)
.sme_text <- function(x) {
  if (is.factor(x)) x <- as.character(x)
  if (inherits(x, "Date")) x <- format(x, "%Y-%m-%d")
  if (inherits(x, "POSIXt")) x <- format(x, "%Y-%m-%d %H:%M:%S")
  if (is.logical(x)) x <- ifelse(x, "1", "0")
  if (is.numeric(x)) x <- ifelse(is.na(x), NA, trimws(formatC(x, digits = 15, format = "fg")))
  x <- as.character(x)
  x[is.na(x)] <- "\001"
  x
}
.sme_write <- function(df, name) {
  df <- as.data.frame(df, stringsAsFactors = FALSE)
  out <- as.data.frame(lapply(df, .sme_text), stringsAsFactors = FALSE, check.names = FALSE)
  names(out) <- names(df)
  utils::write.csv(out, file.path(.sme_dir, name), row.names = FALSE, na = "\001", fileEncoding = "UTF-8")
}
.sme_env <- new.env(parent = globalenv())
"""

_CLEAN = r"""
.sme_env$data <- .sme_in
sys.source(file.path(.sme_dir, "user.R"), envir = .sme_env, keep.source = FALSE)
if (!is.data.frame(.sme_env$data)) stop("The script must leave a table in `data`.")
.sme_write(.sme_env$data, "out.csv")
"""

_ANALYSE = r"""
.sme_env$data <- .sme_in
.sme_design <- jsonlite::fromJSON(file.path(.sme_dir, "design.json"))
if (length(.sme_design$weights) || length(.sme_design$strata) || length(.sme_design$cluster)) {
  suppressPackageStartupMessages(library(survey))
  options(survey.lonely.psu = "adjust")
  f <- function(x) if (length(x)) stats::as.formula(paste0("~`", x, "`")) else NULL
  d <- .sme_env$data
  if (length(.sme_design$weights)) d <- d[!is.na(d[[.sme_design$weights]]), , drop = FALSE]
  if (length(.sme_design$strata)) d$.strate <- interaction(d[, .sme_design$strata, drop = FALSE], drop = TRUE)
  .sme_env$plan <- survey::svydesign(
    ids = if (length(.sme_design$cluster)) f(.sme_design$cluster) else ~1,
    strata = if (length(.sme_design$strata)) ~.strate else NULL, weights = f(.sme_design$weights),
    data = d, nest = TRUE
  )
}
grDevices::png(file.path(.sme_dir, "plot%02d.png"), width = 1600, height = 1000, res = 200)
sys.source(file.path(.sme_dir, "user.R"), envir = .sme_env, keep.source = FALSE)
invisible(grDevices::dev.off())
res <- if (exists("resultat", envir = .sme_env, inherits = FALSE)) .sme_env$resultat else
  if (exists("result", envir = .sme_env, inherits = FALSE)) .sme_env$result else NULL
if (is.data.frame(res) || is.matrix(res)) .sme_write(as.data.frame(res), "table.csv")
"""


def _run(df: pl.DataFrame, code: str, body: str, extra: dict[str, str] | None = None) -> tuple[Path, str]:
    rscript = find_rscript()
    if not rscript:
        raise RpcError("R cannot be found.", data={"key": "r_not_found"})
    folder = Path(tempfile.mkdtemp(prefix="sme-user-r-"))
    df.write_ipc_stream(folder / "in.arrows", compression="uncompressed", compat_level=pl.CompatLevel.oldest())
    (folder / "user.R").write_text(code, encoding="utf-8")
    (folder / "run.R").write_text(_PRELUDE + body, encoding="utf-8")
    for name, text in (extra or {}).items():
        (folder / name).write_text(text, encoding="utf-8")
    env = dict(os.environ)
    try:
        proc = subprocess.run(
            [rscript, "--vanilla", str(folder / "run.R"), str(folder)],
            cwd=folder,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=TIMEOUT,
            env=env,
        )
    except subprocess.TimeoutExpired:
        shutil.rmtree(folder, ignore_errors=True)
        raise RpcError(f"The R script ran for more than {TIMEOUT} s.", data={"key": "r_script_timeout"}) from None
    log = (proc.stdout + ("\n" + proc.stderr if proc.stderr.strip() else "")).strip()
    if proc.returncode != 0:
        shutil.rmtree(folder, ignore_errors=True)
        raise RpcError(
            _error_text(proc.stderr) or "The R script failed.", data={"key": "r_script_failed", "log": log[-MAX_LOG:]}
        )
    return folder, log[-MAX_LOG:]


def _error_text(stderr: str) -> str:
    """The R error message, without the call stack lines R adds."""
    lines = [ln for ln in stderr.strip().splitlines() if ln.strip()]
    start = next((i for i, ln in enumerate(lines) if ln.startswith(("Error", "Erreur"))), None)
    if start is None:
        return "\n".join(lines[-4:])[:2000]
    kept = []
    for ln in lines[start:]:
        if ln.startswith(("Calls:", "Execution halted", "Exécution arrêtée")):
            break
        kept.append(ln)
    text = "\n".join(kept)
    text = text.replace("Error in eval(exprs[i], envir) :", "Error:").replace(
        "Erreur dans eval(exprs[i], envir) :", "Erreur :"
    )
    return text[:2000]


def _read_csv(path: Path) -> pl.DataFrame:
    return pl.read_csv(path, infer_schema=False, null_values=[NA], encoding="utf8")


def run_cleaning(df: pl.DataFrame, code: str) -> tuple[pl.DataFrame, str]:
    """Run a cleaning script on the table (which carries ROW). Returns the new table (with ROW) and the output."""
    sent = df.rename({ROW: ".sme_row"}) if ROW in df.columns else df
    folder, log = _run(sent, code, _CLEAN)
    try:
        out = _read_csv(folder / "out.csv")
    finally:
        shutil.rmtree(folder, ignore_errors=True)
    if ".sme_row" in out.columns:
        out = out.rename({".sme_row": ROW}).with_columns(pl.col(ROW).cast(pl.Float64, strict=False).cast(pl.Int64))
        # Keep the original text of the values the script did not change (R reads 01 as 1).
        same = [c for c in out.columns if c in df.columns and c != ROW]
        if same and out[ROW].null_count() == 0 and out[ROW].n_unique() == out.height:
            old = df.select([ROW, *same]).rename({c: f"__old_{c}" for c in same})
            out = out.join(old, on=ROW, how="left", maintain_order="left")
            fixes = []
            for c in same:
                o, n = pl.col(f"__old_{c}"), pl.col(c)
                num_o = o.str.replace(",", ".", literal=True).cast(pl.Float64, strict=False)
                num_n = n.cast(pl.Float64, strict=False)
                keep = (num_o.is_not_null() & (num_o == num_n)) | (o == n)
                fixes.append(pl.when(keep.fill_null(False)).then(o).otherwise(n).alias(c))
            out = out.with_columns(fixes).drop([f"__old_{c}" for c in same])
    return out, log


def run_analysis(df: pl.DataFrame, code: str, design: dict[str, Any]) -> dict[str, Any]:
    """Run an analysis script. Returns the printed output, the plots (PNG, base64) and a table."""
    import json

    d = {k: design.get(k) or [] for k in ("weights", "strata", "cluster")}
    folder, log = _run(df, code, _ANALYSE, {"design.json": json.dumps(d)})
    try:
        plots = []
        for p in sorted(folder.glob("plot*.png")):
            if p.stat().st_size > 2000:  # an empty device writes a blank page
                plots.append(base64.b64encode(p.read_bytes()).decode("ascii"))
        table = None
        if (folder / "table.csv").exists():
            t = _read_csv(folder / "table.csv").head(500)
            table = {"columns": t.columns, "rows": t.rows()}
    finally:
        shutil.rmtree(folder, ignore_errors=True)
    return {"output": log, "plots": plots[:12], "table": table}
