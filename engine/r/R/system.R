# Fonctions système du moteur R.

sme_ping <- function() {
  list(pong = TRUE)
}

sme_versions <- function() {
  pkgs <- c("survey", "jsonlite", "nanoarrow")
  list(
    r = paste(R.version$major, R.version$minor, sep = "."),
    packages = setNames(
      lapply(pkgs, function(p) {
        if (requireNamespace(p, quietly = TRUE)) as.character(utils::packageVersion(p)) else NULL
      }),
      pkgs
    )
  )
}

# Lit un tableau écrit par le moteur Python (flux Arrow IPC).
sme_read_table <- function(path) {
  if (!file.exists(path)) stop("Fichier de données introuvable : ", path)
  as.data.frame(nanoarrow::read_nanoarrow(path))
}
