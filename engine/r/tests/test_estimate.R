# Tests of sme_estimate and sme_compare against direct calls to R and survey.
#   Rscript engine/r/tests/test_estimate.R

r_dir <- Sys.getenv("SME_R_DIR", "engine/r")
for (f in list.files(file.path(r_dir, "R"), pattern = "\\.R$", full.names = TRUE)) sys.source(f, envir = globalenv())

failures <- 0
check <- function(nom, condition) {
  if (isTRUE(condition)) cat("OK   ", nom, "\n") else { cat("FAIL", nom, "\n"); failures <<- failures + 1 }
}
close_to <- function(a, b, tol = 1e-10) isTRUE(all.equal(as.numeric(a), as.numeric(b), tolerance = tol))

path <- file.path(r_dir, "tests", "fixtures", "echantillon.arrows")
df <- sme_read_table(path)
ok <- df[!is.na(df$y), ]
ok$succes <- as.numeric(ok$y == "Oui")

# Proportion, simple sample: Wilson
r <- sme_estimate(path, "proportion", "y", list("Oui"))
ref <- prop.test(sum(ok$succes), nrow(ok), correct = FALSE)
check("estimate simple: value", close_to(r$estimate, ref$estimate))
check("estimate simple: CI", close_to(c(r$ci_low, r$ci_high), ref$conf.int))
check("estimate simple: method", r$method_key == "wilson")

# Proportion, survey design, with breakdown
r <- sme_estimate(path, "proportion", "y", list("Oui"), weights = "w", strata = list("s"), cluster = "g", by = "s")
d <- survey::svydesign(ids = ~g, strata = ~s, weights = ~w, data = ok, nest = TRUE)
ref <- survey::svyciprop(~succes, d, method = "logit")
check("estimate design: value", close_to(r$estimate, ref))
check("estimate design: CI", close_to(c(r$ci_low, r$ci_high), attr(ref, "ci")))
g1 <- r$by[[1]]
sub <- subset(d, s == g1$group)
check("estimate design: group value", close_to(g1$estimate, survey::svyciprop(~succes, sub, method = "logit")))

# Mean, survey design (table written with nanoarrow, as the Python engine would)
ok$num <- seq_len(nrow(ok)) %% 7
df2 <- df; df2$num <- NA_real_; df2$num[!is.na(df2$y)] <- ok$num
path2 <- tempfile(fileext = ".arrows")
nanoarrow::write_nanoarrow(df2, path2)
r <- sme_estimate(path2, "mean", "num", weights = "w", strata = list("s"), cluster = "g")
d <- survey::svydesign(ids = ~g, strata = ~s, weights = ~w, data = ok, nest = TRUE)
m <- survey::svymean(~num, d)
check("mean design: value", close_to(r$estimate, m))
check("mean design: CI", close_to(c(r$ci_low, r$ci_high), confint(m, df = survey::degf(d))))

# Comparison of two rounds, simple samples: prop.test two-sample
c1 <- sme_compare(path, path, "proportion", "y", list("Oui"))
check("compare same data: difference 0", close_to(c1$difference, 0))
check("compare same data: p = 1", close_to(c1$p_value, 1, 1e-8))

# Comparison with a design: SE combined from the two estimates
c2 <- sme_compare(path, path, "proportion", "y", list("Oui"), weights = "w", strata = list("s"), cluster = "g")
se1 <- survey::SE(survey::svymean(~succes, d))
check("compare design: SE", close_to(c2$se, sqrt(2) * se1, 1e-6))
check("compare design: test key", c2$test_key == "z_survey_prop")

# Chart is written
png <- tempfile(fileext = ".png")
invisible(sme_chart(png, list("A", "B"), list(0.4, 0.6), list(0.35, 0.55), list(0.45, 0.65), target = 0.7))
check("chart written", file.exists(png) && file.size(png) > 1000)

if (failures > 0) { cat(failures, "test(s) failed\n"); quit(status = 1) }
cat("All estimate tests passed.\n")
