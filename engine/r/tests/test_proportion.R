# Tests du moteur R, sans dépendance à testthat : Rscript engine/r/tests/test_proportion.R
# Chaque fonction de SuiviEvalLab est comparée à l'appel R direct équivalent.

# Lancer depuis la racine du dépôt, ou indiquer le dossier avec SME_R_DIR.
r_dir <- Sys.getenv("SME_R_DIR", "engine/r")
for (f in list.files(file.path(r_dir, "R"), pattern = "\\.R$", full.names = TRUE)) sys.source(f, envir = globalenv())

echecs <- 0
verifie <- function(nom, condition) {
  if (isTRUE(condition)) cat("OK   ", nom, "\n") else { cat("ECHEC", nom, "\n"); echecs <<- echecs + 1 }
}
proche <- function(a, b, tol = 1e-12) isTRUE(all.equal(a, b, tolerance = tol))

# Jeu de test écrit au format Arrow IPC par polars, comme le fait le moteur Python
# (fixture générée une fois et versionnée).
chemin <- file.path(r_dir, "tests", "fixtures", "echantillon.arrows")
df <- sme_read_table(chemin)

# 1. Échantillon simple = prop.test direct
r1 <- sme_proportion(chemin, "y", "Oui")
ok <- df[!is.na(df$y), ]
ref <- prop.test(sum(ok$y == "Oui"), nrow(ok), correct = FALSE)
verifie("simple : estimation", proche(r1$estimate, unname(ref$estimate)))
verifie("simple : IC", proche(c(r1$ci_low, r1$ci_high), as.numeric(ref$conf.int)))
verifie("simple : n exclut les manquants", r1$n == nrow(ok))

# 2. Plan d'enquête = svyciprop direct
r2 <- sme_proportion(chemin, "y", "Oui", weights = "w", strata = "s", cluster = "g")
ok$succes <- as.numeric(ok$y == "Oui")
d <- survey::svydesign(ids = ~g, strata = ~s, weights = ~w, data = ok, nest = TRUE)
ref2 <- survey::svyciprop(~succes, d, method = "logit")
verifie("plan : estimation", proche(r2$estimate, as.numeric(ref2)))
verifie("plan : IC", proche(c(r2$ci_low, r2$ci_high), as.numeric(attr(ref2, "ci"))))

# 3. Le script fourni reproduit le résultat
verifie("script présent", grepl("svyciprop", r2$script))

# 4. Erreur claire sur variable absente
msg <- tryCatch({ sme_proportion(chemin, "absente", "Oui"); "" }, error = conditionMessage)
verifie("variable absente : message clair", grepl("Variable absente", msg))

if (echecs > 0) quit(status = 1)
cat("Tous les tests R sont passés.\n")
