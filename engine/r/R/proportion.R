# Proportion with confidence interval.
#
# Simple random sample: Wilson interval, via prop.test(correct = FALSE).
# Survey design (weights, strata, clusters): survey::svyciprop, logit method.
# See docs/statistics.md, section 3.
#
# Also returns the R script that reproduces the computation exactly.
# The `method` text is user-facing (French for now, translated later).

sme_proportion <- function(path, var, success, level = 0.95,
                           weights = NULL, strata = NULL, cluster = NULL) {
  df <- sme_read_table(path)
  if (!var %in% names(df)) stop("Variable absente : ", var)
  df <- df[!is.na(df[[var]]), , drop = FALSE]
  n <- nrow(df)
  if (n == 0) stop("Aucune observation non manquante pour ", var)
  df$.succes <- as.numeric(df[[var]] == success)
  x <- sum(df$.succes)

  plan <- !is.null(weights) || !is.null(strata) || !is.null(cluster)
  if (!plan) {
    test <- stats::prop.test(x, n, conf.level = level, correct = FALSE)
    est <- unname(test$estimate)
    ci <- as.numeric(test$conf.int)
    methode <- "Intervalle de Wilson (prop.test, sans correction de continuité)"
    script <- sprintf(
      'donnees <- as.data.frame(nanoarrow::read_nanoarrow("%s"))\nx <- sum(donnees$%s == "%s", na.rm = TRUE)\nn <- sum(!is.na(donnees$%s))\nprop.test(x, n, conf.level = %s, correct = FALSE)',
      basename(path), var, success, var, level
    )
  } else {
    f <- function(v) if (is.null(v)) NULL else stats::as.formula(paste0("~", v))
    design <- survey::svydesign(
      ids = if (is.null(cluster)) ~1 else f(cluster),
      strata = f(strata), weights = f(weights), data = df, nest = TRUE
    )
    res <- survey::svyciprop(~.succes, design, method = "logit", level = level)
    est <- as.numeric(res)
    ci <- as.numeric(attr(res, "ci"))
    methode <- "Proportion pondérée, plan d'enquête (survey::svyciprop, méthode logit)"
    script <- sprintf(
      'library(survey)\ndonnees <- as.data.frame(nanoarrow::read_nanoarrow("%s"))\ndonnees$succes <- as.numeric(donnees$%s == "%s")\nplan <- svydesign(ids = %s, strata = %s, weights = %s, data = donnees, nest = TRUE)\nsvyciprop(~succes, plan, method = "logit", level = %s)',
      basename(path), var, success,
      if (is.null(cluster)) "~1" else paste0("~", cluster),
      if (is.null(strata)) "NULL" else paste0("~", strata),
      if (is.null(weights)) "NULL" else paste0("~", weights),
      level
    )
  }

  list(
    estimate = est,
    ci_low = ci[1],
    ci_high = ci[2],
    level = level,
    n = n,
    successes = x,
    method = methode,
    script = script
  )
}
