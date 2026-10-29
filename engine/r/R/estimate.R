# Indicator estimation and round comparison. See docs/statistics.md.
#
# Every function takes a table written by the Python engine (Arrow IPC), already
# cleaned, and a specification:
#   type     "proportion" (share of `success` values of `var`) or "mean" (mean of `var`)
#   weights  column of sampling weights, or NULL
#   strata   character vector of stratification columns (combined), or NULL
#   cluster  column of primary sampling units, or NULL
# Without weights, strata or clusters the sample is treated as simple random:
# Wilson interval for proportions, Student t interval for means.
# With any of them, a survey design (Taylor linearisation) is used.
#
# Each result carries `method_key` (translated by the interface) and the R
# script that reproduces it from the cleaned data.

options(survey.lonely.psu = "adjust")

sme_null <- function(x) if (is.null(x) || length(x) == 0 || identical(x, "")) NULL else unlist(x)

# Outcome column .y (0/1 for proportions, numeric for means) and design columns.
sme_prepare <- function(df, type, var, success, weights, strata, cluster) {
  if (!var %in% names(df)) stop("Variable absente : ", var)
  for (v in c(weights, strata, cluster)) if (!v %in% names(df)) stop("Variable absente : ", v)
  if (type == "proportion") {
    y <- ifelse(is.na(df[[var]]), NA_real_, as.numeric(df[[var]] %in% unlist(success)))
  } else if (type == "mean") {
    y <- suppressWarnings(as.numeric(df[[var]]))
  } else {
    stop("Type inconnu : ", type)
  }
  df$.y <- y
  keep <- !is.na(df$.y)
  if (!is.null(weights)) {
    df[[weights]] <- suppressWarnings(as.numeric(df[[weights]]))
    keep <- keep & !is.na(df[[weights]]) & df[[weights]] > 0
  }
  for (v in c(strata, cluster)) keep <- keep & !is.na(df[[v]])
  df <- df[keep, , drop = FALSE]
  if (!is.null(strata)) df$.strate <- interaction(df[, strata, drop = FALSE], drop = TRUE, sep = " / ")
  df
}

sme_has_design <- function(weights, strata, cluster) !is.null(weights) || !is.null(strata) || !is.null(cluster)

sme_design <- function(df, weights, strata, cluster) {
  survey::svydesign(
    ids = if (is.null(cluster)) ~1 else stats::as.formula(paste0("~`", cluster, "`")),
    strata = if (is.null(strata)) NULL else ~.strate,
    weights = if (is.null(weights)) NULL else stats::as.formula(paste0("~`", weights, "`")),
    data = df, nest = TRUE
  )
}

# One estimate on a prepared table.
sme_estimate_one <- function(df, type, weights, strata, cluster, level) {
  n <- nrow(df)
  if (n == 0) return(list(estimate = NULL, ci_low = NULL, ci_high = NULL, se = NULL, n = 0))
  if (!sme_has_design(weights, strata, cluster)) {
    if (type == "proportion") {
      x <- sum(df$.y)
      t <- stats::prop.test(x, n, conf.level = level, correct = FALSE)
      est <- x / n
      return(list(estimate = est, ci_low = t$conf.int[1], ci_high = t$conf.int[2],
                  se = sqrt(est * (1 - est) / n), n = n, successes = x))
    }
    if (n < 2) return(list(estimate = mean(df$.y), ci_low = NULL, ci_high = NULL, se = NULL, n = n))
    t <- stats::t.test(df$.y, conf.level = level)
    return(list(estimate = mean(df$.y), ci_low = t$conf.int[1], ci_high = t$conf.int[2],
                se = stats::sd(df$.y) / sqrt(n), n = n))
  }
  d <- sme_design(df, weights, strata, cluster)
  if (type == "proportion") {
    r <- survey::svyciprop(~.y, d, method = "logit", level = level)
    ci <- as.numeric(attr(r, "ci"))
    return(list(estimate = as.numeric(r), ci_low = ci[1], ci_high = ci[2],
                se = as.numeric(survey::SE(r)), n = n, successes = sum(df$.y)))
  }
  m <- survey::svymean(~.y, d)
  ci <- as.numeric(stats::confint(m, level = level, df = survey::degf(d)))
  list(estimate = as.numeric(m), ci_low = ci[1], ci_high = ci[2], se = as.numeric(survey::SE(m)), n = n)
}

sme_script <- function(type, var, success, weights, strata, cluster, by, level) {
  y <- if (type == "proportion") {
    sprintf('donnees$y <- as.numeric(donnees$`%s` %%in%% c(%s))\ndonnees$y[is.na(donnees$`%s`)] <- NA',
            var, paste0('"', unlist(success), '"', collapse = ", "), var)
  } else {
    sprintf("donnees$y <- as.numeric(donnees$`%s`)", var)
  }
  head <- paste0(
    "# Donnees nettoyees exportees par SuiviEvalLab (une ligne par observation)\n",
    'donnees <- read.csv("donnees_nettoyees.csv", na.strings = "", check.names = FALSE)\n', y,
    "\ndonnees <- donnees[!is.na(donnees$y), ]\n"
  )
  if (!sme_has_design(weights, strata, cluster)) {
    body <- if (type == "proportion") {
      sprintf("prop.test(sum(donnees$y), nrow(donnees), conf.level = %s, correct = FALSE)", level)
    } else {
      sprintf("t.test(donnees$y, conf.level = %s)", level)
    }
    return(paste0(head, body))
  }
  st <- if (is.null(strata)) "" else
    sprintf("donnees$strate <- interaction(donnees[, c(%s)], drop = TRUE)\n",
            paste0('"', strata, '"', collapse = ", "))
  plan <- sprintf(
    "library(survey)\noptions(survey.lonely.psu = \"adjust\")\n%splan <- svydesign(ids = %s, strata = %s, weights = %s, data = donnees, nest = TRUE)\n",
    st,
    if (is.null(cluster)) "~1" else sprintf("~`%s`", cluster),
    if (is.null(strata)) "NULL" else "~strate",
    if (is.null(weights)) "NULL" else sprintf("~`%s`", weights)
  )
  est <- if (type == "proportion") {
    sprintf('svyciprop(~y, plan, method = "logit", level = %s)', level)
  } else {
    sprintf("confint(svymean(~y, plan), level = %s, df = degf(plan))", level)
  }
  if (!is.null(by)) {
    est <- paste0(est, sprintf("\nsvyby(~y, ~`%s`, plan, %s, vartype = \"ci\")", by,
                               if (type == "proportion") 'svyciprop, method = "logit"' else "svymean"))
  }
  paste0(head, plan, est)
}

sme_estimate <- function(path, type, var, success = NULL, weights = NULL, strata = NULL,
                         cluster = NULL, by = NULL, level = 0.95) {
  weights <- sme_null(weights); strata <- sme_null(strata); cluster <- sme_null(cluster); by <- sme_null(by)
  df <- sme_prepare(sme_read_table(path), type, var, success, weights, strata, cluster)
  if (nrow(df) == 0) stop("Aucune observation utilisable pour ", var)
  res <- sme_estimate_one(df, type, weights, strata, cluster, level)
  groups <- list()
  if (!is.null(by)) {
    if (!by %in% names(df)) stop("Variable absente : ", by)
    for (g in sort(unique(stats::na.omit(df[[by]])))) {
      sub <- df[!is.na(df[[by]]) & df[[by]] == g, , drop = FALSE]
      # Strata with a single unit inside a group are handled by survey.lonely.psu.
      r <- tryCatch(sme_estimate_one(sub, type, weights, strata, cluster, level),
                    error = function(e) list(estimate = NULL, n = nrow(sub), error = conditionMessage(e)))
      r$group <- g
      groups[[length(groups) + 1]] <- r
    }
  }
  res$by <- groups
  res$level <- level
  res$type <- type
  res$method_key <- if (sme_has_design(weights, strata, cluster)) {
    if (type == "proportion") "survey_logit" else "survey_mean"
  } else {
    if (type == "proportion") "wilson" else "t_mean"
  }
  res$script <- sme_script(type, var, success, weights, strata, cluster, by, level)
  res
}

# Comparison of two independent rounds (for example baseline and endline).
# Difference B - A with its confidence interval, test and effect size.
# With a design: each round is estimated on its own design and the difference
# uses SE = sqrt(SE_A^2 + SE_B^2) (independent samples), z test.
# Without a design: two-sample test of proportions (chi-squared, Newcombe
# interval via prop.test) or Welch t test for means.
sme_compare <- function(path_a, path_b, type, var, success = NULL, weights = NULL, strata = NULL,
                        cluster = NULL, level = 0.95) {
  weights <- sme_null(weights); strata <- sme_null(strata); cluster <- sme_null(cluster)
  a <- sme_prepare(sme_read_table(path_a), type, var, success, weights, strata, cluster)
  b <- sme_prepare(sme_read_table(path_b), type, var, success, weights, strata, cluster)
  if (nrow(a) < 2 || nrow(b) < 2) stop("Pas assez d'observations pour comparer")
  ra <- sme_estimate_one(a, type, weights, strata, cluster, level)
  rb <- sme_estimate_one(b, type, weights, strata, cluster, level)
  diff <- rb$estimate - ra$estimate
  z <- stats::qnorm(1 - (1 - level) / 2)

  if (sme_has_design(weights, strata, cluster)) {
    se <- sqrt(ra$se^2 + rb$se^2)
    stat <- diff / se
    p <- 2 * stats::pnorm(-abs(stat))
    ci <- c(diff - z * se, diff + z * se)
    test_key <- if (type == "proportion") "z_survey_prop" else "z_survey_mean"
  } else if (type == "proportion") {
    t <- stats::prop.test(c(rb$successes, ra$successes), c(rb$n, ra$n), conf.level = level, correct = FALSE)
    stat <- unname(sqrt(t$statistic)) * sign(diff)
    p <- t$p.value
    ci <- as.numeric(t$conf.int)
    se <- sqrt(ra$se^2 + rb$se^2)
    test_key <- "chisq_prop"
  } else {
    t <- stats::t.test(b$.y, a$.y, conf.level = level)
    stat <- unname(t$statistic)
    p <- t$p.value
    ci <- as.numeric(t$conf.int)
    se <- unname(t$stderr)
    test_key <- "welch"
  }

  # Effect size: Cohen's h for proportions, Cohen's d (pooled SD, unweighted) for means.
  effect <- if (type == "proportion") {
    2 * asin(sqrt(rb$estimate)) - 2 * asin(sqrt(ra$estimate))
  } else {
    sp <- sqrt(((nrow(a) - 1) * stats::var(a$.y) + (nrow(b) - 1) * stats::var(b$.y)) / (nrow(a) + nrow(b) - 2))
    if (sp > 0) diff / sp else NA_real_
  }

  list(
    a = ra, b = rb, difference = diff, ci_low = ci[1], ci_high = ci[2], se = se,
    statistic = stat, p_value = p, level = level, test_key = test_key,
    effect_size = effect, effect_key = if (type == "proportion") "cohen_h" else "cohen_d"
  )
}

# Bar chart for the Word report: one bar per round with its interval, and the target.
# Text (labels, title, target label) comes from the Python engine in the report language.
sme_chart <- function(out, labels, values, lows, highs, target = NULL, percent = TRUE,
                      title = "", ylab = "", target_label = "Target", decimal = ".") {
  values <- as.numeric(unlist(values)); lows <- as.numeric(unlist(lows)); highs <- as.numeric(unlist(highs))
  labels <- unlist(labels)
  target <- sme_null(target)
  k <- if (percent) 100 else 1
  top <- max(c(highs, values, target), na.rm = TRUE) * k
  ylim <- c(0, if (percent) min(100, max(10, top * 1.2)) else top * 1.2)
  grDevices::png(out, width = 1600, height = 820, res = 200,
                 type = if (.Platform$OS.type == "windows") "windows" else "cairo")
  on.exit(grDevices::dev.off())
  graphics::par(mar = c(2.6, 4.2, 2.2, 0.8), family = "sans", col.axis = "#5F5C57", col.lab = "#5F5C57",
                fg = "#C9C6BF", bty = "n", tcl = -0.25, mgp = c(2.6, 0.6, 0))
  x <- graphics::barplot(values * k, names.arg = labels, ylim = ylim, col = "#1D4F91", border = NA,
                         space = 0.9, ylab = ylab, las = 1, main = title, cex.main = 0.95, font.main = 1,
                         col.main = "#1F1E1C", axes = FALSE, cex.names = 0.9)
  ticks <- pretty(ylim)
  graphics::abline(h = ticks[ticks > 0 & ticks <= ylim[2]], col = "#ECEAE5", lwd = 1)
  graphics::barplot(values * k, ylim = ylim, col = "#1D4F91", border = NA, space = 0.9, axes = FALSE,
                    add = TRUE, names.arg = rep("", length(values)))
  graphics::axis(2, at = ticks, las = 1, lwd = 0, lwd.ticks = 0, cex.axis = 0.85)
  ok <- !is.na(lows) & !is.na(highs)
  if (any(ok)) graphics::arrows(x[ok], lows[ok] * k, x[ok], highs[ok] * k, angle = 90, code = 3,
                                length = 0.05, col = "#1F1E1C", lwd = 1.2)
  label_y <- ifelse(is.na(highs), values, highs) * k
  graphics::text(x, label_y, labels = formatC(values * k, format = "f", digits = 1, decimal.mark = decimal),
                 pos = 3, offset = 0.45, cex = 0.85, col = "#1F1E1C")
  if (!is.null(target) && !is.na(target)) {
    graphics::segments(graphics::par("usr")[1], target * k, graphics::par("usr")[2], target * k,
                       lty = 2, col = "#B4441A", lwd = 1.5)
    graphics::text(graphics::par("usr")[1], target * k, labels = target_label, adj = c(0, -0.5),
                   cex = 0.8, col = "#B4441A", xpd = TRUE)
  }
  list(path = out)
}
