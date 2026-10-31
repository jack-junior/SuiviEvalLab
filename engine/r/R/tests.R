# Test assistant. Each function answers one question with the default test of
# docs/statistics.md, checks its conditions, reports the fallback when they
# fail, and returns estimates by group, the test, an effect size and the R script.
#
# Variables arrive already built by the Python engine:
#   .y   outcome: 0/1 for yes/no questions, a number otherwise
#   .g   group (text), for comparisons between groups
#   .y2  second measure of the same unit, for paired questions
# With weights, strata or clusters the survey package is used (design-based tests).

sme_test_frame <- function(path, weights, strata, cluster, cols) {
  df <- sme_read_table(path)
  for (v in c(cols, weights, strata, cluster)) if (!v %in% names(df)) stop("Variable absente : ", v)
  for (v in intersect(c(".y", ".y2"), names(df))) df[[v]] <- suppressWarnings(as.numeric(df[[v]]))
  keep <- stats::complete.cases(df[, cols, drop = FALSE])
  if (!is.null(weights)) {
    df[[weights]] <- suppressWarnings(as.numeric(df[[weights]]))
    keep <- keep & !is.na(df[[weights]]) & df[[weights]] > 0
  }
  for (v in c(strata, cluster)) keep <- keep & !is.na(df[[v]])
  df <- df[keep, , drop = FALSE]
  if (!is.null(strata)) df$.strate <- interaction(df[, strata, drop = FALSE], drop = TRUE, sep = " / ")
  if (".g" %in% names(df)) df$.g <- factor(df$.g)
  df
}

sme_design_header <- function(weights, strata, cluster) {
  if (!sme_has_design(weights, strata, cluster)) return("")
  st <- if (is.null(strata)) "" else
    sprintf("donnees$strate <- interaction(donnees[, c(%s)], drop = TRUE)\n", paste0('"', strata, '"', collapse = ", "))
  sprintf(
    "library(survey)\noptions(survey.lonely.psu = \"adjust\")\n%splan <- svydesign(ids = %s, strata = %s, weights = %s, data = donnees, nest = TRUE)\n",
    st,
    if (is.null(cluster)) "~1" else sprintf("~`%s`", cluster),
    if (is.null(strata)) "NULL" else "~strate",
    if (is.null(weights)) "NULL" else sprintf("~`%s`", weights)
  )
}

sme_script_head <- function(y_code) {
  paste0(
    "# Donnees nettoyees exportees par SuiviEvalLab\n",
    'donnees <- read.csv("donnees_nettoyees.csv", na.strings = "", check.names = FALSE)\n',
    y_code, "\n"
  )
}

# 1 and 2. Compare a yes/no outcome or a numeric outcome between groups.
sme_test_groups <- function(path, kind, weights = NULL, strata = NULL, cluster = NULL,
                            level = 0.95, y_code = "") {
  weights <- sme_null(weights); strata <- sme_null(strata); cluster <- sme_null(cluster)
  df <- sme_test_frame(path, weights, strata, cluster, c(".y", ".g"))
  df$.g <- droplevels(df$.g)
  k <- nlevels(df$.g)
  if (k < 2) stop("Il faut au moins deux groupes avec des observations")
  design <- sme_has_design(weights, strata, cluster)
  d <- if (design) sme_design(df, weights, strata, cluster) else NULL
  type <- if (kind == "proportion") "proportion" else "mean"

  groups <- lapply(levels(df$.g), function(g) {
    sub <- df[df$.g == g, , drop = FALSE]
    r <- tryCatch(sme_estimate_one(sub, type, weights, strata, cluster, level),
                  error = function(e) list(estimate = NULL, n = nrow(sub)))
    r$group <- g
    r
  })
  notes <- character(0)
  alt <- NULL
  script <- paste0(sme_script_head(y_code), sme_design_header(weights, strata, cluster))

  if (kind == "proportion") {
    if (design) {
      t <- survey::svychisq(~.y + .g, d, statistic = "F")
      res <- list(test_key = "rao_scott", statistic = unname(t$statistic), df = unname(t$parameter)[1],
                  df2 = unname(t$parameter)[2], p_value = unname(t$p.value))
      script <- paste0(script, 'svychisq(~y + groupe, plan, statistic = "F")')
      tab <- table(df$.g, df$.y)
    } else {
      tab <- table(df$.g, df$.y)
      ch <- suppressWarnings(stats::chisq.test(tab, correct = FALSE))
      if (any(ch$expected < 5)) {
        fi <- if (all(dim(tab) == 2)) stats::fisher.test(tab) else stats::fisher.test(tab, simulate.p.value = TRUE, B = 20000)
        notes <- c(notes, "expected_small")
        res <- list(test_key = "fisher", statistic = NULL, df = NULL, p_value = unname(fi$p.value))
        script <- paste0(script, "fisher.test(table(donnees$groupe, donnees$y))")
      } else {
        res <- list(test_key = "chisq", statistic = unname(ch$statistic), df = unname(ch$parameter),
                    p_value = unname(ch$p.value))
        script <- paste0(script, "chisq.test(table(donnees$groupe, donnees$y), correct = FALSE)")
      }
    }
    # Cramér's V from the unweighted table (descriptive size of the association).
    chi <- suppressWarnings(stats::chisq.test(tab, correct = FALSE))$statistic
    v <- sqrt(unname(chi) / (sum(tab) * (min(dim(tab)) - 1)))
    res$effect_size <- if (is.finite(v)) v else NULL
    res$effect_key <- "cramer_v"
  } else if (k == 2) {
    if (design) {
      t <- survey::svyttest(.y ~ .g, d)
      res <- list(test_key = "svyttest", statistic = unname(t$statistic), df = unname(t$parameter),
                  p_value = unname(t$p.value), difference = unname(t$estimate))
      script <- paste0(script, "svyttest(y ~ groupe, plan)")
    } else {
      a <- df$.y[df$.g == levels(df$.g)[1]]; b <- df$.y[df$.g == levels(df$.g)[2]]
      t <- stats::t.test(b, a, conf.level = level)
      res <- list(test_key = "welch", statistic = unname(t$statistic), df = unname(t$parameter),
                  p_value = unname(t$p.value), difference = mean(b) - mean(a),
                  ci_low = t$conf.int[1], ci_high = t$conf.int[2])
      script <- paste0(script, "t.test(y ~ groupe, data = donnees)")
      small <- min(length(a), length(b)) < 30
      normal <- all(vapply(list(a, b), function(x) length(x) < 3 || length(x) > 5000 ||
                             stats::shapiro.test(x)$p.value >= 0.05, logical(1)))
      if (small && !normal) {
        w <- suppressWarnings(stats::wilcox.test(b, a))
        notes <- c(notes, "not_normal_small")
        alt <- list(test_key = "mann_whitney", statistic = unname(w$statistic), p_value = unname(w$p.value))
      }
    }
    a <- df$.y[df$.g == levels(df$.g)[1]]; b <- df$.y[df$.g == levels(df$.g)[2]]
    sp <- sqrt(((length(a) - 1) * stats::var(a) + (length(b) - 1) * stats::var(b)) / (length(a) + length(b) - 2))
    g <- if (sp > 0) (mean(b) - mean(a)) / sp * (1 - 3 / (4 * (length(a) + length(b)) - 9)) else NA_real_
    res$effect_size <- if (is.finite(g)) g else NULL
    res$effect_key <- "hedges_g"
  } else {
    if (design) {
      m <- survey::svyglm(.y ~ .g, d)
      t <- survey::regTermTest(m, ~.g)
      res <- list(test_key = "svyglm_wald", statistic = unname(t$Ftest), df = unname(t$df),
                  df2 = unname(t$ddf), p_value = unname(t$p))
      script <- paste0(script, "regTermTest(svyglm(y ~ groupe, plan), ~groupe)")
    } else {
      t <- stats::oneway.test(.y ~ .g, data = df, var.equal = FALSE)
      res <- list(test_key = "welch_anova", statistic = unname(t$statistic), df = unname(t$parameter[1]),
                  p_value = unname(t$p.value))
      script <- paste0(script, "oneway.test(y ~ groupe, data = donnees, var.equal = FALSE)")
      if (min(table(df$.g)) < 30) {
        kw <- stats::kruskal.test(.y ~ .g, data = df)
        notes <- c(notes, "small_groups")
        alt <- list(test_key = "kruskal", statistic = unname(kw$statistic), p_value = unname(kw$p.value))
      }
    }
    # Omega squared from the one-way ANOVA table (unweighted).
    a <- summary(stats::aov(.y ~ .g, data = df))[[1]]
    ss_b <- a[1, "Sum Sq"]; ss_w <- a[2, "Sum Sq"]; ms_w <- a[2, "Mean Sq"]; dfb <- a[1, "Df"]
    w2 <- (ss_b - dfb * ms_w) / (ss_b + ss_w + ms_w)
    res$effect_size <- if (is.finite(w2)) max(0, w2) else NULL
    res$effect_key <- "omega2"
  }
  c(res, list(question = "groups", kind = kind, groups = groups, n = nrow(df), level = level,
              notes = as.list(notes), alternative = alt, design = design, script = script))
}

# 3. Compare a proportion or a mean with a target value.
sme_test_target <- function(path, kind, target, weights = NULL, strata = NULL, cluster = NULL,
                            level = 0.95, y_code = "") {
  weights <- sme_null(weights); strata <- sme_null(strata); cluster <- sme_null(cluster)
  df <- sme_test_frame(path, weights, strata, cluster, ".y")
  type <- if (kind == "proportion") "proportion" else "mean"
  est <- sme_estimate_one(df, type, weights, strata, cluster, level)
  design <- sme_has_design(weights, strata, cluster)
  script <- paste0(sme_script_head(y_code), sme_design_header(weights, strata, cluster))
  if (design) {
    z <- (est$estimate - target) / est$se
    res <- list(test_key = if (kind == "proportion") "z_target_prop" else "z_target_mean",
                statistic = z, df = NULL, p_value = 2 * stats::pnorm(-abs(z)))
    script <- paste0(script, if (kind == "proportion") "r <- svyciprop(~y, plan, method = \"logit\")\n" else "r <- svymean(~y, plan)\n",
                     sprintf("z <- (coef(r) - %s) / SE(r)\n2 * pnorm(-abs(z))", target))
  } else if (kind == "proportion") {
    b <- stats::binom.test(sum(df$.y), nrow(df), p = target)
    res <- list(test_key = "binomial", statistic = NULL, df = NULL, p_value = unname(b$p.value))
    script <- paste0(script, sprintf("binom.test(sum(donnees$y), nrow(donnees), p = %s)", target))
  } else {
    t <- stats::t.test(df$.y, mu = target)
    res <- list(test_key = "one_sample_t", statistic = unname(t$statistic), df = unname(t$parameter),
                p_value = unname(t$p.value))
    script <- paste0(script, sprintf("t.test(donnees$y, mu = %s)", target))
  }
  effect <- if (kind == "proportion") 2 * asin(sqrt(est$estimate)) - 2 * asin(sqrt(target)) else
    if (stats::sd(df$.y) > 0) (est$estimate - target) / stats::sd(df$.y) else NA_real_
  c(res, list(question = "target", kind = kind, target = target, estimate = est, n = nrow(df), level = level,
              difference = est$estimate - target,
              effect_size = if (is.finite(effect)) effect else NULL,
              effect_key = if (kind == "proportion") "cohen_h" else "cohen_d",
              notes = list(), alternative = NULL, design = design, script = script))
}

# 4. Same units measured twice (two columns, or two datasets linked by an identifier).
sme_test_paired <- function(path, kind, level = 0.95, y_code = "") {
  df <- sme_test_frame(path, NULL, NULL, NULL, c(".y", ".y2"))
  n <- nrow(df)
  if (n < 3) stop("Pas assez de paires complètes")
  notes <- character(0)
  alt <- NULL
  script <- sme_script_head(y_code)
  if (kind == "proportion") {
    b <- sum(df$.y == 1 & df$.y2 == 0); c <- sum(df$.y == 0 & df$.y2 == 1)
    if (b + c == 0) stop("Aucune paire discordante : pas de changement à tester")
    if (b + c < 25) {
      t <- stats::binom.test(c, b + c)
      res <- list(test_key = "mcnemar_exact", statistic = NULL, df = NULL, p_value = unname(t$p.value))
      notes <- c(notes, "few_discordant")
      script <- paste0(script, "b <- sum(donnees$avant == 1 & donnees$apres == 0); c <- sum(donnees$avant == 0 & donnees$apres == 1)\nbinom.test(c, b + c)")
    } else {
      t <- stats::mcnemar.test(matrix(c(sum(df$.y == 1 & df$.y2 == 1), c, b, sum(df$.y == 0 & df$.y2 == 0)), 2), correct = FALSE)
      res <- list(test_key = "mcnemar", statistic = unname(t$statistic), df = unname(t$parameter), p_value = unname(t$p.value))
      script <- paste0(script, "mcnemar.test(table(donnees$avant, donnees$apres), correct = FALSE)")
    }
    p1 <- mean(df$.y); p2 <- mean(df$.y2)
    res$effect_size <- if (b > 0) c / b else NULL
    res$effect_key <- "odds_ratio_paired"
    res$before <- p1; res$after <- p2; res$difference <- p2 - p1
    res$discordant <- list(lost = b, gained = c)
  } else {
    dlt <- df$.y2 - df$.y
    t <- stats::t.test(df$.y2, df$.y, paired = TRUE, conf.level = level)
    res <- list(test_key = "paired_t", statistic = unname(t$statistic), df = unname(t$parameter),
                p_value = unname(t$p.value), ci_low = t$conf.int[1], ci_high = t$conf.int[2])
    script <- paste0(script, "t.test(donnees$apres, donnees$avant, paired = TRUE)")
    if (n < 30 && n <= 5000 && stats::shapiro.test(dlt)$p.value < 0.05) {
      w <- suppressWarnings(stats::wilcox.test(df$.y2, df$.y, paired = TRUE))
      notes <- c(notes, "not_normal_small")
      alt <- list(test_key = "wilcoxon_signed", statistic = unname(w$statistic), p_value = unname(w$p.value))
    }
    res$effect_size <- if (stats::sd(dlt) > 0) mean(dlt) / stats::sd(dlt) else NULL
    res$effect_key <- "cohen_dz"
    res$before <- mean(df$.y); res$after <- mean(df$.y2); res$difference <- mean(dlt)
  }
  c(res, list(question = "paired", kind = kind, n = n, level = level, notes = as.list(notes),
              alternative = alt, design = FALSE, script = script))
}
