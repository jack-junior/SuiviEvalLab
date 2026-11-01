# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 GAYI Komi Selassi and SANOUSSI Moudjibou

# Free analyses (Analyses screen). Every analysis follows the dataset's sampling
# design when it has one (survey package, Taylor linearisation), and the usual
# tests otherwise. The Python engine sends the cleaned table (all columns as
# text) and the options; each function returns tables, tests and charts:
#
#   tables  list of {key, columns = list of {key, fmt}, rows = list of lists}
#           fmt: "text", "int", "num", "pct" (a share, shown as %), "p" (p-value)
#   tests   list of {key, statistic, df, df2, p_value}
#   charts  paths of PNG files
#   script  R code that gives the same result from the exported cleaned data
#
# Column keys and test keys are translated by the Python engine (analyses.py).

sme_an_num <- function(x) suppressWarnings(as.numeric(sub(",", ".", as.character(x), fixed = TRUE)))

sme_an_frame <- function(path, weights, strata, cluster) {
  df <- sme_read_table(path)
  keep <- rep(TRUE, nrow(df))
  if (!is.null(weights)) {
    df[[weights]] <- sme_an_num(df[[weights]])
    keep <- keep & !is.na(df[[weights]]) & df[[weights]] > 0
  }
  for (v in c(strata, cluster)) keep <- keep & !is.na(df[[v]])
  df <- df[keep, , drop = FALSE]
  if (!is.null(strata)) df$.strate <- interaction(df[, strata, drop = FALSE], drop = TRUE, sep = " / ")
  df
}

sme_an_design <- function(df, weights, strata, cluster) {
  if (!sme_has_design(weights, strata, cluster)) return(NULL)
  sme_design(df, weights, strata, cluster)
}

# Script lines that rebuild the design from the exported cleaned data.
sme_an_script_head <- function(weights, strata, cluster, prep = NULL) {
  head <- paste0(
    "# Donnees nettoyees exportees par SuiviEvalLab (Donnees, Exporter)\n",
    'donnees <- read.csv("donnees_nettoyees.csv", na.strings = "", check.names = FALSE)\n',
    if (is.null(prep)) "" else prep
  )
  if (!sme_has_design(weights, strata, cluster)) return(head)
  paste0(head, sme_design_header(weights, strata, cluster))
}

sme_an_q <- function(x) paste0("`", x, "`")

sme_an_wilson <- function(x, n, level) {
  if (n == 0) return(c(NA, NA))
  z <- stats::qnorm(1 - (1 - level) / 2)
  p <- x / n
  centre <- (p + z^2 / (2 * n)) / (1 + z^2 / n)
  half <- z * sqrt(p * (1 - p) / n + z^2 / (4 * n^2)) / (1 + z^2 / n)
  c(max(0, centre - half), min(1, centre + half))
}

sme_an_levels <- function(x) {
  lv <- sort(unique(as.character(x[!is.na(x)])))
  num <- sme_an_num(lv)
  if (length(lv) && all(!is.na(num))) lv <- lv[order(num)]
  lv
}

# Numeric summary of y on a subset (design or not).
sme_an_numeric <- function(y, d, keep, level) {
  ok <- keep & !is.na(y)
  n <- sum(ok)
  if (n == 0) return(list(n = 0))
  x <- y[ok]
  if (is.null(d)) {
    m <- mean(x); s <- if (n > 1) stats::sd(x) else NA
    se <- if (n > 1) s / sqrt(n) else NA
    tq <- if (n > 1) stats::qt(1 - (1 - level) / 2, n - 1) else NA
    q <- stats::quantile(x, c(.25, .5, .75), names = FALSE)
    return(list(n = n, mean = m, se = se, ci_low = m - tq * se, ci_high = m + tq * se, sd = s,
                median = q[2], q1 = q[1], q3 = q[3], min = min(x), max = max(x)))
  }
  dd <- d
  dd$variables$.v <- y
  sub <- subset(dd, ok)
  est <- survey::svymean(~.v, sub)
  ci <- stats::confint(est, level = level, df = survey::degf(sub))
  q <- tryCatch({
    r <- survey::svyquantile(~.v, sub, c(.25, .5, .75), ci = FALSE)
    as.numeric(r[[1]][, 1])
  }, error = function(e) rep(NA, 3))
  v <- tryCatch(as.numeric(survey::svyvar(~.v, sub)), error = function(e) NA)
  list(n = n, mean = unname(stats::coef(est)), se = unname(survey::SE(est))[1],
       ci_low = ci[1], ci_high = ci[2], sd = sqrt(v),
       median = q[2], q1 = q[1], q3 = q[3], min = min(x), max = max(x))
}

# Shares of the values of x on a subset.
sme_an_shares <- function(x, d, keep, level) {
  ok <- keep & !is.na(x)
  lv <- sme_an_levels(x[ok])
  n <- sum(ok)
  lapply(lv, function(l) {
    hit <- as.numeric(as.character(x) == l)
    k <- sum(ok & as.character(x) == l)
    if (is.null(d)) {
      ci <- sme_an_wilson(k, n, level)
      return(list(value = l, n = k, percent = if (n) k / n else NA, ci_low = ci[1], ci_high = ci[2]))
    }
    dd <- d
    dd$variables$.h <- hit
    sub <- subset(dd, ok)
    p <- tryCatch(survey::svyciprop(~.h, sub, method = "logit", level = level), error = function(e) NULL)
    if (is.null(p)) {
      est <- survey::svymean(~.h, sub)
      return(list(value = l, n = k, percent = unname(stats::coef(est)), ci_low = NA, ci_high = NA))
    }
    ci <- attr(p, "ci")
    list(value = l, n = k, percent = unname(as.numeric(p)), ci_low = unname(ci[1]), ci_high = unname(ci[2]))
  })
}

sme_an_chart_bars <- function(out, labels, values, lows, highs, percent, ylab, decimal, groups = NULL) {
  # Horizontal bars when there are many or long labels; error bars for confidence intervals.
  labels <- as.character(labels)
  k <- if (percent) 100 else 1
  values <- as.numeric(values) * k; lows <- as.numeric(lows) * k; highs <- as.numeric(highs) * k
  n <- length(values)
  horizontal <- n > 6 || max(nchar(labels), 0) > 14
  h <- if (horizontal) max(820, 160 + n * 90) else 820
  grDevices::png(out, width = 1600, height = h, res = 200,
                 type = if (.Platform$OS.type == "windows") "windows" else "cairo")
  on.exit(grDevices::dev.off())
  short <- ifelse(nchar(labels) > 38, paste0(substr(labels, 1, 36), "..."), labels)
  top <- max(c(highs, values), na.rm = TRUE)
  bottom <- min(c(lows, values, 0), na.rm = TRUE)
  lim <- c(bottom * 1.15, if (percent) min(100, max(10, top * 1.18)) else top * 1.18)
  if (!is.finite(lim[2]) || lim[2] <= lim[1]) lim <- c(0, 1)
  cols <- "#1D4F91"
  if (!is.null(groups)) {
    pal <- c("#1D4F91", "#B4441A", "#2E7D5B", "#7A5195", "#C49A1A", "#4E8FBF", "#8C6D46", "#5F5C57")
    cols <- pal[(as.integer(factor(groups, levels = unique(groups))) - 1) %% length(pal) + 1]
  }
  graphics::par(family = "sans", col.axis = "#5F5C57", col.lab = "#5F5C57", fg = "#C9C6BF", bty = "n",
                tcl = -0.25, mgp = c(2.6, 0.6, 0))
  if (horizontal) {
    graphics::par(mar = c(3, min(18, 1 + max(nchar(short)) * 0.42), 1, 1.5))
    y <- graphics::barplot(rev(values), names.arg = rev(short), horiz = TRUE, xlim = lim, col = rev(cols),
                           border = NA, las = 1, axes = FALSE, cex.names = 0.8, xlab = ylab)
    graphics::axis(1, lwd = 0, lwd.ticks = 0, cex.axis = 0.8)
    ok <- rev(!is.na(lows) & !is.na(highs))
    if (any(ok)) graphics::arrows(rev(lows)[ok], y[ok], rev(highs)[ok], y[ok], angle = 90, code = 3,
                                  length = 0.04, col = "#1F1E1C", lwd = 1.1)
  } else {
    graphics::par(mar = c(2.6, 4.2, 1, 0.8))
    x <- graphics::barplot(values, names.arg = short, ylim = lim, col = cols, border = NA, space = 0.7,
                           ylab = ylab, las = 1, axes = FALSE, cex.names = 0.85)
    graphics::axis(2, las = 1, lwd = 0, lwd.ticks = 0, cex.axis = 0.8)
    ok <- !is.na(lows) & !is.na(highs)
    if (any(ok)) graphics::arrows(x[ok], lows[ok], x[ok], highs[ok], angle = 90, code = 3,
                                  length = 0.05, col = "#1F1E1C", lwd = 1.1)
    graphics::text(x, ifelse(is.na(highs), values, highs), cex = 0.8, pos = 3, offset = 0.4, col = "#1F1E1C",
                   labels = formatC(values, format = "f", digits = if (percent) 1 else 2, decimal.mark = decimal))
  }
  if (!is.null(groups)) {
    u <- unique(groups)
    graphics::legend("topright", legend = u, fill = cols[match(u, groups)], border = NA, bty = "n", cex = 0.75,
                     text.col = "#1F1E1C")
  }
  out
}

# Grouped bars: one group of bars per row of `m`, one colour per column (series), with optional intervals.
sme_an_chart_grouped <- function(out, m, low = NULL, high = NULL, percent = TRUE, ylab = "%", decimal = ".") {
  k <- if (percent) 100 else 1
  m <- m * k
  if (!is.null(low)) { low <- low * k; high <- high * k }
  pal <- c("#1D4F91", "#B4441A", "#2E7D5B", "#7A5195", "#C49A1A", "#4E8FBF", "#8C6D46", "#5F5C57")
  cols <- pal[(seq_len(ncol(m)) - 1) %% length(pal) + 1]
  grDevices::png(out, width = 1600, height = 860, res = 200,
                 type = if (.Platform$OS.type == "windows") "windows" else "cairo")
  on.exit(grDevices::dev.off())
  graphics::par(mar = c(2.6, 4.2, 2.4, 0.8), family = "sans", col.axis = "#5F5C57", col.lab = "#5F5C57",
                fg = "#C9C6BF", bty = "n", tcl = -0.25, mgp = c(2.6, 0.6, 0), xpd = TRUE)
  top <- max(c(m, high), na.rm = TRUE)
  lim <- c(0, if (percent) min(100, max(10, top * 1.15)) else top * 1.15)
  names <- rownames(m)
  names <- ifelse(nchar(names) > 18, paste0(substr(names, 1, 16), "..."), names)
  x <- graphics::barplot(t(m), beside = TRUE, names.arg = names, col = cols, border = NA, ylim = lim,
                         axes = FALSE, ylab = ylab, cex.names = 0.8, space = c(0.15, 0.9))
  graphics::axis(2, las = 1, lwd = 0, lwd.ticks = 0, cex.axis = 0.8)
  if (!is.null(low)) {
    lo <- t(low); hi <- t(high); ok <- !is.na(lo) & !is.na(hi)
    if (any(ok)) graphics::arrows(x[ok], lo[ok], x[ok], hi[ok], angle = 90, code = 3, length = 0.04,
                                  col = "#1F1E1C", lwd = 1)
  }
  if (length(m) <= 24) {
    yy <- if (is.null(high)) t(m) else pmax(t(m), t(high), na.rm = TRUE)
    graphics::text(x, yy, labels = formatC(t(m), format = "f", digits = if (percent) 1 else 2, decimal.mark = decimal),
                   pos = 3, offset = 0.3, cex = 0.7, col = "#1F1E1C")
  }
  graphics::legend("top", inset = c(0, -0.12), horiz = TRUE, legend = colnames(m), fill = cols, border = NA,
                   bty = "n", cex = 0.75, text.col = "#1F1E1C")
  out
}

sme_an_chart_hist <- function(out, x, w, xlab, decimal) {
  grDevices::png(out, width = 1600, height = 820, res = 200,
                 type = if (.Platform$OS.type == "windows") "windows" else "cairo")
  on.exit(grDevices::dev.off())
  graphics::par(mar = c(3.6, 4.2, 1, 0.8), family = "sans", col.axis = "#5F5C57", col.lab = "#5F5C57",
                fg = "#C9C6BF", bty = "n", tcl = -0.25, mgp = c(2.4, 0.6, 0))
  br <- pretty(range(x, na.rm = TRUE), n = min(30, max(8, ceiling(sqrt(length(x))))))
  if (length(br) < 2) br <- c(min(x) - 0.5, max(x) + 0.5)
  bin <- cut(x, br, include.lowest = TRUE)
  share <- tapply(if (is.null(w)) rep(1, length(x)) else w, bin, sum)
  share[is.na(share)] <- 0
  share <- share / sum(share) * 100
  graphics::plot(NA, xlim = range(br), ylim = c(0, max(share) * 1.1), xlab = xlab, ylab = "%", axes = FALSE)
  graphics::rect(br[-length(br)], 0, br[-1], share, col = "#1D4F91", border = "white")
  graphics::axis(1, lwd = 0, lwd.ticks = 0, cex.axis = 0.8)
  graphics::axis(2, las = 1, lwd = 0, lwd.ticks = 0, cex.axis = 0.8)
  out
}

sme_an_chart_coef <- function(out, labels, est, low, high, ref, xlab) {
  n <- length(est)
  grDevices::png(out, width = 1600, height = max(700, 180 + n * 80), res = 200,
                 type = if (.Platform$OS.type == "windows") "windows" else "cairo")
  on.exit(grDevices::dev.off())
  short <- ifelse(nchar(labels) > 40, paste0(substr(labels, 1, 38), "..."), labels)
  graphics::par(mar = c(3.4, min(20, 1 + max(nchar(short)) * 0.42), 1, 1.5), family = "sans",
                col.axis = "#5F5C57", col.lab = "#5F5C57", fg = "#C9C6BF", bty = "n", tcl = -0.25,
                mgp = c(2.3, 0.6, 0))
  lim <- range(c(low, high, ref), na.rm = TRUE)
  y <- rev(seq_len(n))
  graphics::plot(est, y, xlim = lim, ylim = c(0.5, n + 0.5), pch = 19, col = "#1D4F91", axes = FALSE,
                 xlab = xlab, ylab = "", log = if (ref == 1) "x" else "")
  graphics::abline(v = ref, lty = 2, col = "#B4441A")
  graphics::segments(low, y, high, y, col = "#1D4F91", lwd = 1.6)
  graphics::axis(1, lwd = 0, lwd.ticks = 0, cex.axis = 0.8)
  graphics::axis(2, at = y, labels = short, las = 1, lwd = 0, lwd.ticks = 0, cex.axis = 0.8)
  out
}

sme_an_rows <- function(items, keys) lapply(items, function(r) lapply(keys, function(k) {
  v <- r[[k]]
  if (is.null(v) || length(v) == 0 || (is.numeric(v) && !is.finite(v))) NULL else v
}))

sme_an_cols <- function(keys, fmts) lapply(seq_along(keys), function(i) list(key = keys[[i]], fmt = fmts[[i]]))

# ----- descriptives --------------------------------------------------------------

sme_an_descriptives <- function(df, d, o, level, outdir, decimal) {
  vars <- unlist(o$variables)
  by <- sme_null(o$by)
  types <- o$types
  g <- if (is.null(by)) NULL else as.character(df[[by]])
  groups <- if (is.null(by)) list(NULL) else as.list(sme_an_levels(g))
  num_rows <- list(); cat_rows <- list(); charts <- character(0)
  for (v in vars) {
    x <- df[[v]]
    y <- sme_an_num(x)
    present <- !is.na(x)
    t <- types[[v]]
    numeric <- if (!is.null(t)) identical(t, "numeric") else
      sum(present) > 0 && all(!is.na(y[present])) && length(unique(y[present])) > 10
    for (gr in groups) {
      keep <- if (is.null(gr)) rep(TRUE, nrow(df)) else !is.na(g) & g == gr
      if (numeric) {
        r <- sme_an_numeric(y, d, keep, level)
        r$variable <- v; r$group <- gr
        num_rows[[length(num_rows) + 1]] <- r
      } else {
        for (s in sme_an_shares(x, d, keep, level)) {
          s$variable <- v; s$group <- gr
          cat_rows[[length(cat_rows) + 1]] <- s
        }
      }
    }
    if (length(charts) < 6) {
      out <- file.path(outdir, sprintf("desc_%02d.png", length(charts) + 1))
      if (numeric && is.null(by)) {
        ok <- !is.na(y)
        w <- if (is.null(d)) NULL else stats::weights(d)[ok]
        charts <- c(charts, sme_an_chart_hist(out, y[ok], w, v, decimal))
      } else if (numeric) {
        rs <- Filter(function(r) identical(r$variable, v), num_rows)
        charts <- c(charts, sme_an_chart_bars(out, vapply(rs, function(r) r$group, ""),
                                              vapply(rs, function(r) sme_an_or(r$mean), 0),
                                              vapply(rs, function(r) sme_an_or(r$ci_low), 0),
                                              vapply(rs, function(r) sme_an_or(r$ci_high), 0),
                                              FALSE, v, decimal))
      } else {
        rs <- Filter(function(r) identical(r$variable, v), cat_rows)
        vals <- unique(vapply(rs, function(r) r$value, ""))
        if (is.null(by) && length(rs) <= 40) {
          charts <- c(charts, sme_an_chart_bars(out, vapply(rs, function(r) r$value, ""),
                                                vapply(rs, function(r) sme_an_or(r$percent), 0),
                                                vapply(rs, function(r) sme_an_or(r$ci_low), 0),
                                                vapply(rs, function(r) sme_an_or(r$ci_high), 0), TRUE, "%", decimal))
        } else if (!is.null(by) && length(vals) <= 12 && length(groups) <= 8) {
          gs <- unlist(groups)
          m <- matrix(0, length(vals), length(gs), dimnames = list(vals, gs))
          for (r in rs) m[r$value, r$group] <- sme_an_or(r$percent)
          charts <- c(charts, sme_an_chart_grouped(out, m, percent = TRUE, decimal = decimal))
        }
      }
    }
  }
  tables <- list()
  gk <- if (is.null(by)) character(0) else "group"
  if (length(num_rows)) {
    keys <- c("variable", gk, "n", "mean", "se", "ci_low", "ci_high", "sd", "median", "q1", "q3", "min", "max")
    fmts <- c("text", rep("text", length(gk)), "int", rep("num", 10))
    tables[[length(tables) + 1]] <- list(key = "numeric", columns = sme_an_cols(keys, fmts),
                                         rows = sme_an_rows(num_rows, keys))
  }
  if (length(cat_rows)) {
    keys <- c("variable", gk, "value", "n", "percent", "ci_low", "ci_high")
    fmts <- c("text", rep("text", length(gk)), "text", "int", "pct", "pct", "pct")
    tables[[length(tables) + 1]] <- list(key = "categorical", columns = sme_an_cols(keys, fmts),
                                         rows = sme_an_rows(cat_rows, keys))
  }
  sc <- if (is.null(d)) paste0("summary(donnees[, c(", paste0('"', vars, '"', collapse = ", "), ")])") else
    paste0(vapply(vars, function(v) sprintf("svymean(~%s, plan, na.rm = TRUE)", sme_an_q(v)), ""), collapse = "\n")
  if (!is.null(by) && !is.null(d))
    sc <- paste0(vapply(vars, function(v) sprintf("svyby(~%s, ~%s, plan, svymean, na.rm = TRUE)",
                                                   sme_an_q(v), sme_an_q(by)), ""), collapse = "\n")
  list(tables = tables, tests = list(), charts = charts, script = sc, n = nrow(df))
}

sme_an_or <- function(x) if (is.null(x) || length(x) == 0) NA_real_ else as.numeric(x)

# ----- crosstab ------------------------------------------------------------------

sme_an_crosstab <- function(df, d, o, level, outdir, decimal) {
  r <- o$row; cc <- o$column
  pct <- if (is.null(o$percent)) "row" else o$percent
  ok <- !is.na(df[[r]]) & !is.na(df[[cc]])
  if (sum(ok) < 2) stop("Pas assez de lignes avec les deux variables renseignees")
  a <- factor(as.character(df[[r]]), levels = sme_an_levels(df[[r]][ok]))
  b <- factor(as.character(df[[cc]]), levels = sme_an_levels(df[[cc]][ok]))
  if (nlevels(a) < 2 || nlevels(b) < 2) stop("Chaque variable doit avoir au moins deux valeurs")
  counts <- table(a[ok], b[ok])
  if (is.null(d)) {
    w <- counts
  } else {
    dd <- d
    dd$variables$.a <- a; dd$variables$.b <- b
    sub <- subset(dd, ok)
    w <- survey::svytable(~.a + .b, sub)
  }
  w <- unclass(as.matrix(w))
  p <- switch(pct, row = sweep(w, 1, rowSums(w), "/"), column = sweep(w, 2, colSums(w), "/"), w / sum(w))
  tot <- switch(pct, row = colSums(w) / sum(w), column = rowSums(w) / sum(w), NULL)
  rows <- lapply(seq_len(nrow(p)), function(i) {
    c(list(levels(a)[i]), as.list(unname(p[i, ])),
      if (pct == "row") list(sum(counts[i, ])) else list(sum(w[i, ]) / sum(w)))
  })
  if (pct == "column") rows[[length(rows) + 1]] <- c(list(".n"), as.list(unname(colSums(counts))), list(sum(counts)))
  if (pct == "row") rows[[length(rows) + 1]] <- c(list(".all"), as.list(unname(tot)), list(sum(counts)))
  last <- if (pct == "row") list(key = "n", fmt = "int") else list(key = "all", fmt = "pct")
  cols <- c(list(list(key = "row_value", fmt = "text", label = r)),
            lapply(levels(b), function(l) list(key = "value", label = l, fmt = "pct")), list(last))
  ctab <- list(key = paste0("percent_", pct), columns = cols, rows = rows)
  ncols <- c(list(list(key = "row_value", fmt = "text", label = r)),
             lapply(levels(b), function(l) list(key = "value", label = l, fmt = "int")), list(list(key = "n", fmt = "int")))
  nrows <- lapply(seq_len(nrow(counts)), function(i) c(list(levels(a)[i]), as.list(unname(as.numeric(counts[i, ]))),
                                                       list(sum(counts[i, ]))))
  ntab <- list(key = "counts", columns = ncols, rows = nrows)
  tests <- list(); notes <- character(0)
  if (!is.null(d)) {
    t <- survey::svychisq(~.a + .b, sub, statistic = "F")
    tests[[1]] <- list(key = "rao_scott", statistic = unname(t$statistic), df = unname(t$parameter)[1],
                       df2 = unname(t$parameter)[2], p_value = unname(t$p.value))
    sc <- sprintf('svychisq(~%s + %s, plan, statistic = "F")\nprop.table(svytable(~%s + %s, plan), %s)',
                  sme_an_q(r), sme_an_q(cc), sme_an_q(r), sme_an_q(cc), if (pct == "row") 1 else if (pct == "column") 2 else "NULL")
  } else {
    ch <- suppressWarnings(stats::chisq.test(counts, correct = FALSE))
    if (any(ch$expected < 5)) {
      fi <- if (all(dim(counts) == 2)) stats::fisher.test(counts) else
        stats::fisher.test(counts, simulate.p.value = TRUE, B = 20000)
      tests[[1]] <- list(key = "fisher", p_value = unname(fi$p.value))
      notes <- c(notes, "expected_small")
    } else {
      tests[[1]] <- list(key = "chisq", statistic = unname(ch$statistic), df = unname(ch$parameter),
                         p_value = unname(ch$p.value))
    }
    sc <- sprintf("t <- table(donnees$%s, donnees$%s)\nprop.table(t, %s)\nchisq.test(t, correct = FALSE)",
                  sme_an_q(r), sme_an_q(cc), if (pct == "row") 1 else if (pct == "column") 2 else "NULL")
  }
  chi <- suppressWarnings(stats::chisq.test(counts, correct = FALSE))$statistic
  v <- sqrt(unname(chi) / (sum(counts) * (min(dim(counts)) - 1)))
  tests[[1]]$effect_size <- if (is.finite(v)) v else NULL
  charts <- character(0)
  if (length(p) <= 80) {
    pm <- p
    if (pct == "column") pm <- t(p)
    dimnames(pm) <- if (pct == "column") list(levels(b), levels(a)) else list(levels(a), levels(b))
    charts <- sme_an_chart_grouped(file.path(outdir, "crosstab.png"), pm, percent = TRUE, decimal = decimal)
  }
  list(tables = list(ctab, ntab), tests = tests, charts = charts, notes = notes, script = sc, n = sum(counts))
}

# ----- comparison of means ---------------------------------------------------------

sme_an_means <- function(df, d, o, level, outdir, decimal) {
  y <- sme_an_num(df[[o$outcome]])
  g <- as.character(df[[o$group]])
  ok <- !is.na(y) & !is.na(g)
  lv <- sme_an_levels(g[ok])
  if (length(lv) < 2) stop("Il faut au moins deux groupes avec des valeurs")
  rows <- lapply(lv, function(l) { r <- sme_an_numeric(y, d, ok & g == l, level); r$group <- l; r })
  keys <- c("group", "n", "mean", "se", "ci_low", "ci_high", "sd", "median")
  tab <- list(key = "by_group", columns = sme_an_cols(keys, c("text", "int", rep("num", 6))),
              rows = sme_an_rows(rows, keys))
  tests <- list()
  yy <- sme_an_q(o$outcome); gg <- sme_an_q(o$group)
  if (!is.null(d)) {
    dd <- d
    dd$variables$.y <- y; dd$variables$.g <- factor(g, levels = lv)
    sub <- subset(dd, ok)
    if (length(lv) == 2) {
      t <- survey::svyttest(.y ~ .g, sub)
      ci <- stats::confint(t, level = level)
      tests[[1]] <- list(key = "svyttest", statistic = unname(t$statistic), df = unname(t$parameter),
                         p_value = unname(t$p.value), difference = unname(t$estimate),
                         ci_low = unname(ci[1]), ci_high = unname(ci[2]))
      sc <- sprintf("svyby(~%s, ~%s, plan, svymean, na.rm = TRUE)\nsvyttest(%s ~ %s, plan)", yy, gg, yy, gg)
    } else {
      m <- survey::svyglm(.y ~ .g, sub)
      t <- survey::regTermTest(m, ~.g)
      tests[[1]] <- list(key = "svy_anova", statistic = unname(t$Ftest), df = unname(t$df),
                         df2 = unname(t$ddf), p_value = unname(t$p))
      sc <- sprintf("svyby(~%s, ~%s, plan, svymean, na.rm = TRUE)\nm <- svyglm(%s ~ factor(%s), plan)\nregTermTest(m, ~factor(%s))",
                    yy, gg, yy, gg, gg)
    }
  } else {
    yo <- y[ok]; go <- factor(g[ok], levels = lv)
    if (length(lv) == 2) {
      a <- yo[go == lv[1]]; b <- yo[go == lv[2]]
      t <- stats::t.test(b, a, conf.level = level)
      tests[[1]] <- list(key = "welch", statistic = unname(t$statistic), df = unname(t$parameter),
                         p_value = unname(t$p.value), difference = mean(b) - mean(a),
                         ci_low = t$conf.int[1], ci_high = t$conf.int[2])
      sc <- sprintf("t.test(%s ~ %s, data = donnees)", yy, gg)
    } else {
      t <- stats::oneway.test(yo ~ go)
      tests[[1]] <- list(key = "welch_anova", statistic = unname(t$statistic), df = unname(t$parameter)[1],
                         df2 = unname(t$parameter)[2], p_value = unname(t$p.value))
      sc <- sprintf("oneway.test(%s ~ factor(%s), data = donnees)", yy, gg)
    }
  }
  chart <- sme_an_chart_bars(file.path(outdir, "means.png"), lv,
                             vapply(rows, function(r) sme_an_or(r$mean), 0),
                             vapply(rows, function(r) sme_an_or(r$ci_low), 0),
                             vapply(rows, function(r) sme_an_or(r$ci_high), 0), FALSE, o$outcome, decimal)
  list(tables = list(tab), tests = tests, charts = chart, script = sc, n = sum(ok),
       levels = lv)
}

# ----- correlation ----------------------------------------------------------------

sme_an_correlation <- function(df, d, o, level, outdir, decimal) {
  vars <- unlist(o$variables)
  if (length(vars) < 2) stop("Choisir au moins deux variables")
  m <- sapply(vars, function(v) sme_an_num(df[[v]]))
  ok <- stats::complete.cases(m)
  if (sum(ok) < 4) stop("Moins de 4 lignes ont toutes les variables")
  k <- length(vars)
  r <- matrix(NA, k, k); p <- matrix(NA, k, k)
  if (is.null(d)) {
    r <- stats::cor(m[ok, , drop = FALSE])
    for (i in seq_len(k)) for (j in seq_len(k)) if (i != j)
      p[i, j] <- stats::cor.test(m[ok, i], m[ok, j])$p.value
    sc <- sprintf("v <- donnees[, c(%s)]\ncor(v, use = \"complete.obs\")", paste0('"', vars, '"', collapse = ", "))
  } else {
    dd <- d
    for (i in seq_len(k)) dd$variables[[paste0(".x", i)]] <- m[, i]
    sub <- subset(dd, ok)
    f <- stats::as.formula(paste0("~", paste0(".x", seq_len(k), collapse = " + ")))
    v <- as.matrix(survey::svyvar(f, sub))
    r <- stats::cov2cor(v[seq_len(k), seq_len(k), drop = FALSE])
    for (i in seq_len(k)) for (j in seq_len(k)) if (i != j) {
      fit <- survey::svyglm(stats::as.formula(paste0(".x", i, " ~ .x", j)), sub)
      p[i, j] <- summary(fit)$coefficients[2, 4]
    }
    sc <- sprintf("v <- svyvar(~%s, plan, na.rm = TRUE)\ncov2cor(as.matrix(v))",
                  paste0(vapply(vars, sme_an_q, ""), collapse = " + "))
  }
  cols <- c(list(list(key = "variable", fmt = "text")), lapply(vars, function(v) list(key = "value", label = v, fmt = "num")))
  rows <- lapply(seq_len(k), function(i) c(list(vars[i]), as.list(unname(r[i, ]))))
  prow <- lapply(seq_len(k), function(i) c(list(vars[i]), as.list(unname(p[i, ]))))
  pcols <- c(list(list(key = "variable", fmt = "text")), lapply(vars, function(v) list(key = "value", label = v, fmt = "p")))
  list(tables = list(list(key = "correlation", columns = cols, rows = rows),
                     list(key = "correlation_p", columns = pcols, rows = prow)),
       tests = list(), charts = character(0), script = sc, n = sum(ok))
}

# ----- regression -----------------------------------------------------------------

sme_an_regression <- function(df, d, o, level, outdir, decimal) {
  family <- if (identical(o$family, "logistic")) "logistic" else "linear"
  preds <- unlist(o$predictors)
  factors <- unlist(o$factors)
  if (!length(preds)) stop("Choisir au moins une variable explicative")
  if (family == "logistic") {
    raw <- as.character(df[[o$outcome]])
    y <- ifelse(is.na(raw), NA_real_, as.numeric(raw %in% unlist(o$success)))
  } else {
    y <- sme_an_num(df[[o$outcome]])
  }
  x <- list(); labels <- list(); kinds <- character(0)
  for (i in seq_along(preds)) {
    v <- preds[i]; raw <- df[[v]]; num <- sme_an_num(raw)
    present <- !is.na(raw)
    is_factor <- v %in% factors || any(is.na(num[present]))
    nm <- paste0(".p", i)
    if (is_factor) {
      lv <- sme_an_levels(raw[present])
      if (!is.null(o$reference[[v]]) && o$reference[[v]] %in% lv) lv <- c(o$reference[[v]], setdiff(lv, o$reference[[v]]))
      x[[nm]] <- factor(as.character(raw), levels = lv)
      kinds[nm] <- "factor"
    } else {
      x[[nm]] <- num
      kinds[nm] <- "number"
    }
    labels[[nm]] <- v
  }
  frame <- data.frame(.y = y, x, check.names = FALSE)
  ok <- stats::complete.cases(frame)
  if (sum(ok) < length(preds) + 3) stop("Pas assez de lignes completes pour cette regression")
  form <- stats::as.formula(paste(".y ~", paste(names(x), collapse = " + ")))
  if (is.null(d)) {
    fit <- if (family == "logistic") stats::glm(form, data = frame[ok, ], family = stats::binomial()) else
      stats::lm(form, data = frame[ok, ])
    co <- summary(fit)$coefficients
    ci <- stats::confint.default(fit, level = level)
    if (family == "linear") {
      tq <- stats::qt(1 - (1 - level) / 2, fit$df.residual)
      ci <- cbind(co[, 1] - tq * co[, 2], co[, 1] + tq * co[, 2])
    }
    r2 <- if (family == "linear") summary(fit)$r.squared else 1 - fit$deviance / fit$null.deviance
  } else {
    dd <- d
    for (nm in names(frame)) dd$variables[[nm]] <- frame[[nm]]
    sub <- subset(dd, ok)
    fit <- if (family == "logistic") survey::svyglm(form, sub, family = stats::quasibinomial()) else
      survey::svyglm(form, sub)
    co <- summary(fit)$coefficients
    ci <- stats::confint(fit, level = level, df = survey::degf(sub))
    r2 <- 1 - fit$deviance / fit$null.deviance
  }
  term_label <- function(term) {
    if (term == "(Intercept)") return(".intercept")
    for (nm in names(x)) {
      if (term == nm) return(labels[[nm]])
      if (kinds[nm] == "factor" && startsWith(term, nm)) return(paste0(labels[[nm]], " = ", substring(term, nchar(nm) + 1)))
    }
    term
  }
  rows <- lapply(seq_len(nrow(co)), function(i) {
    term <- rownames(co)[i]
    r <- list(term = term_label(term), estimate = co[i, 1], se = co[i, 2], statistic = co[i, 3],
              p_value = co[i, 4], ci_low = ci[i, 1], ci_high = ci[i, 2])
    if (family == "logistic") { r$odds_ratio <- exp(co[i, 1]); r$or_low <- exp(ci[i, 1]); r$or_high <- exp(ci[i, 2]) }
    r
  })
  keys <- c("term", "estimate", "se", "ci_low", "ci_high", "statistic", "p_value")
  fmts <- c("text", rep("num", 5), "p")
  if (family == "logistic") { keys <- c(keys, "odds_ratio", "or_low", "or_high"); fmts <- c(fmts, "num", "num", "num") }
  refs <- list()
  for (nm in names(x)) if (kinds[nm] == "factor") refs[[labels[[nm]]]] <- levels(x[[nm]])[1]
  fitrow <- list(list(n = sum(ok), r2 = r2))
  tables <- list(list(key = paste0("coefficients_", family), columns = sme_an_cols(keys, fmts), rows = sme_an_rows(rows, keys)),
                 list(key = "fit", columns = sme_an_cols(c("n", "r2"), c("int", "num")), rows = sme_an_rows(fitrow, c("n", "r2"))))
  rr <- rows[-1]
  charts <- character(0)
  if (length(rr)) {
    if (family == "logistic") {
      charts <- sme_an_chart_coef(file.path(outdir, "coef.png"), vapply(rr, function(r) r$term, ""),
                                  vapply(rr, function(r) r$odds_ratio, 0), vapply(rr, function(r) r$or_low, 0),
                                  vapply(rr, function(r) r$or_high, 0), 1,
                                  if (is.null(o$labels$odds_ratio)) "Odds ratio" else o$labels$odds_ratio)
    } else {
      charts <- sme_an_chart_coef(file.path(outdir, "coef.png"), vapply(rr, function(r) r$term, ""),
                                  vapply(rr, function(r) r$estimate, 0), vapply(rr, function(r) r$ci_low, 0),
                                  vapply(rr, function(r) r$ci_high, 0), 0, o$outcome)
    }
  }
  rhs <- paste(vapply(seq_along(preds), function(i) {
    nm <- paste0(".p", i)
    if (kinds[nm] == "factor") sprintf("factor(%s)", sme_an_q(preds[i])) else sme_an_q(preds[i])
  }, ""), collapse = " + ")
  yv <- if (family == "logistic") sprintf("I(%s %%in%% c(%s))", sme_an_q(o$outcome),
                                          paste0('"', unlist(o$success), '"', collapse = ", ")) else sme_an_q(o$outcome)
  sc <- if (is.null(d)) {
    if (family == "logistic") sprintf("m <- glm(%s ~ %s, data = donnees, family = binomial())\nsummary(m)\nexp(coef(m))", yv, rhs) else
      sprintf("m <- lm(%s ~ %s, data = donnees)\nsummary(m)\nconfint(m)", yv, rhs)
  } else {
    if (family == "logistic") sprintf("m <- svyglm(%s ~ %s, plan, family = quasibinomial())\nsummary(m)\nexp(cbind(coef(m), confint(m)))", yv, rhs) else
      sprintf("m <- svyglm(%s ~ %s, plan)\nsummary(m)\nconfint(m)", yv, rhs)
  }
  list(tables = tables, tests = list(), charts = charts, script = sc, n = sum(ok), references = refs)
}

# ----- difference in differences ---------------------------------------------------

sme_an_did <- function(df, d, o, level, outdir, decimal) {
  raw <- as.character(df[[o$outcome]])
  succ <- sme_null(o$success)
  y <- if (!is.null(succ)) ifelse(is.na(raw), NA_real_, as.numeric(raw %in% unlist(succ))) else sme_an_num(raw)
  gr <- as.character(df[[o$group]]); pe <- as.character(df[[o$period]])
  treat <- ifelse(is.na(gr), NA, gr %in% unlist(o$treated))
  post <- ifelse(is.na(pe), NA, pe %in% unlist(o$after))
  ok <- !is.na(y) & !is.na(treat) & !is.na(post)
  cells <- table(treat[ok], post[ok])
  if (any(dim(cells) != 2) || any(cells == 0)) stop("Il faut des observations pour les deux groupes avant et apres")
  frame <- data.frame(.y = y, .t = as.numeric(treat), .a = as.numeric(post))
  if (is.null(d)) {
    fit <- stats::lm(.y ~ .t * .a, data = frame[ok, ])
    co <- summary(fit)$coefficients
    tq <- stats::qt(1 - (1 - level) / 2, fit$df.residual)
    i <- which(rownames(co) == ".t:.a")
    ci <- co[i, 1] + c(-1, 1) * tq * co[i, 2]
    dsg <- NULL
  } else {
    dd <- d
    for (nm in names(frame)) dd$variables[[nm]] <- frame[[nm]]
    dsg <- subset(dd, ok)
    fit <- survey::svyglm(.y ~ .t * .a, dsg)
    co <- summary(fit)$coefficients
    i <- which(rownames(co) == ".t:.a")
    ci <- stats::confint(fit, level = level, df = survey::degf(dsg))[i, ]
  }
  means <- list()
  for (tt in c(FALSE, TRUE)) for (aa in c(FALSE, TRUE)) {
    keep <- ok & treat == tt & post == aa
    r <- sme_an_numeric(y, d, keep, level)
    r$group <- if (tt) "treated" else "comparison"
    r$period <- if (aa) "after" else "before"
    means[[length(means) + 1]] <- r
  }
  keys <- c("group", "period", "n", "mean", "ci_low", "ci_high")
  t1 <- list(key = if (is.null(succ)) "did_means" else "did_shares",
             columns = sme_an_cols(keys, c("text", "text", "int", rep(if (is.null(succ)) "num" else "pct", 3))),
             rows = sme_an_rows(means, keys))
  est <- list(list(estimate = co[i, 1], se = co[i, 2], ci_low = ci[1], ci_high = ci[2], p_value = co[i, 4]))
  t2 <- list(key = "did_estimate", columns = sme_an_cols(c("estimate", "se", "ci_low", "ci_high", "p_value"),
                                                         c(rep(if (is.null(succ)) "num" else "pct", 4), "p")),
             rows = sme_an_rows(est, c("estimate", "se", "ci_low", "ci_high", "p_value")))
  pct <- !is.null(succ)
  lab <- o$labels
  word <- function(k) if (!is.null(lab[[k]])) lab[[k]] else k
  get <- function(field) matrix(vapply(means, function(r) sme_an_or(r[[field]]), 0), nrow = 2,
                                dimnames = list(c(word("before"), word("after")), c(word("comparison"), word("treated"))))
  chart <- sme_an_chart_grouped(file.path(outdir, "did.png"), get("mean"), get("ci_low"), get("ci_high"),
                                percent = pct, ylab = if (pct) "%" else o$outcome, decimal = decimal)
  ycode <- if (pct) sprintf("donnees$y <- as.numeric(donnees$%s %%in%% c(%s))", sme_an_q(o$outcome),
                            paste0('"', unlist(succ), '"', collapse = ", ")) else
    sprintf("donnees$y <- as.numeric(donnees$%s)", sme_an_q(o$outcome))
  prep <- sprintf("%s\ndonnees$traite <- as.numeric(donnees$%s %%in%% c(%s))\ndonnees$apres <- as.numeric(donnees$%s %%in%% c(%s))\n",
                  ycode, sme_an_q(o$group), paste0('"', unlist(o$treated), '"', collapse = ", "),
                  sme_an_q(o$period), paste0('"', unlist(o$after), '"', collapse = ", "))
  sc <- if (is.null(d)) "summary(lm(y ~ traite * apres, data = donnees))" else "summary(svyglm(y ~ traite * apres, plan))"
  list(tables = list(t1, t2), tests = list(), charts = chart, script = sc, prep = prep, n = sum(ok))
}

# ----- entry point -----------------------------------------------------------------

sme_analysis <- function(path, type, options, weights = NULL, strata = NULL, cluster = NULL, level = 0.95,
                         outdir = ".", decimal = ".") {
  weights <- sme_null(weights); strata <- sme_null(strata); cluster <- sme_null(cluster)
  # Axis labels of the charts in the language of the interface (decimal comma in French).
  old <- options(OutDec = decimal)
  on.exit(options(old), add = TRUE)
  df <- sme_an_frame(path, weights, strata, cluster)
  d <- sme_an_design(df, weights, strata, cluster)
  fn <- switch(type,
    descriptives = sme_an_descriptives, crosstab = sme_an_crosstab, means = sme_an_means,
    correlation = sme_an_correlation, regression = sme_an_regression, did = sme_an_did,
    stop("Analyse inconnue : ", type))
  res <- suppressWarnings(fn(df, d, options, level, outdir, decimal))
  # Single finite numbers only: a test that cannot be computed gives NULL, not NaN or an empty vector.
  res$tests <- lapply(res$tests, function(t) lapply(t, function(v) {
    if (!is.numeric(v)) return(v)
    if (length(v) == 0 || !is.finite(v[1])) NULL else unname(v[1])
  }))
  res$script <- paste0(sme_an_script_head(weights, strata, cluster, res$prep), res$script, "\n")
  res$prep <- NULL
  res$design <- !is.null(d)
  res
}
