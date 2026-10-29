# Moteur statistique de SuiviEvalLab.
#
# Processus R persistant piloté par le moteur Python. Il lit une commande JSON
# par ligne sur l'entrée standard : {"id": 1, "fn": "proportion", "args": {...}}
# et répond sur la sortie standard : {"id": 1, "result": ...} ou {"id": 1, "error": "..."}.
# Les messages de diagnostic partent sur la sortie d'erreur.

local({
  args <- commandArgs(trailingOnly = TRUE)
  r_dir <- if (length(args) >= 1) args[[1]] else "."
  for (f in sort(list.files(file.path(r_dir, "R"), pattern = "\\.R$", full.names = TRUE))) {
    sys.source(f, envir = globalenv())
  }
})

suppressPackageStartupMessages({
  library(jsonlite)
})

sme_send <- function(x) {
  out <- jsonlite::toJSON(x, auto_unbox = TRUE, null = "null", na = "null", digits = NA)
  cat(out, "\n", sep = "", file = stdout())
  flush(stdout())
}

sme_dispatch <- list(
  ping = function(args) sme_ping(),
  versions = function(args) sme_versions(),
  proportion = function(args) do.call(sme_proportion, args)
)

sme_send(list(ready = TRUE, r_version = R.version$version.string))

con <- file("stdin", open = "r", encoding = "UTF-8")
repeat {
  line <- readLines(con, n = 1, warn = FALSE)
  if (length(line) == 0) break
  if (!nzchar(trimws(line))) next
  req <- tryCatch(jsonlite::fromJSON(line, simplifyVector = FALSE), error = function(e) NULL)
  if (is.null(req)) {
    sme_send(list(id = NULL, error = "Commande illisible"))
    next
  }
  fn <- sme_dispatch[[req$fn]]
  if (is.null(fn)) {
    sme_send(list(id = req$id, error = paste0("Fonction inconnue : ", req$fn)))
    next
  }
  res <- tryCatch(
    list(id = req$id, result = fn(req$args)),
    error = function(e) list(id = req$id, error = conditionMessage(e))
  )
  sme_send(res)
}
close(con)
