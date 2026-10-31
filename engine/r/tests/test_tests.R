# Tests of the test assistant against direct calls to stats and survey.
#   Rscript engine/r/tests/test_tests.R

r_dir <- Sys.getenv("SME_R_DIR", "engine/r")
for (f in list.files(file.path(r_dir, "R"), pattern = "\\.R$", full.names = TRUE)) sys.source(f, envir = globalenv())

failures <- 0
check <- function(nom, condition) {
  if (isTRUE(condition)) cat("OK   ", nom, "\n") else { cat("FAIL", nom, "\n"); failures <<- failures + 1 }
}
close_to <- function(a, b, tol = 1e-10) isTRUE(all.equal(as.numeric(a), as.numeric(b), tolerance = tol))
write <- function(df) { p <- tempfile(fileext = ".arrows"); nanoarrow::write_nanoarrow(df, p); p }

set.seed(42)
n <- 400
df <- data.frame(
  .y = rbinom(n, 1, 0.4), .g = sample(c("A", "B", "C"), n, replace = TRUE),
  num = rnorm(n, 50, 10), w = runif(n, 0.5, 2), s = sample(c("s1", "s2"), n, replace = TRUE),
  check.names = FALSE
)
p <- write(df)

# Proportion between groups, simple: chi-squared
r <- sme_test_groups(p, "proportion")
ref <- chisq.test(table(df$.g, df$.y), correct = FALSE)
check("groups prop: chi-squared p", close_to(r$p_value, ref$p.value))
check("groups prop: three groups", length(r$groups) == 3)

# Proportion between groups, design: Rao-Scott
r <- sme_test_groups(p, "proportion", weights = "w", strata = list("s"))
d <- survey::svydesign(ids = ~1, strata = ~s, weights = ~w, data = transform(df, y = .y, g = .g))
ref <- survey::svychisq(~y + g, d, statistic = "F")
check("groups prop design: Rao-Scott p", close_to(r$p_value, ref$p.value, 1e-8))

# Mean between two groups: Welch and Hedges g
df2 <- df[df$.g != "C", ]; df2$.y <- df2$num
r <- sme_test_groups(write(df2), "mean")
ref <- t.test(df2$num[df2$.g == "B"], df2$num[df2$.g == "A"])
check("groups mean: Welch p", close_to(r$p_value, ref$p.value))
check("groups mean: effect is Hedges g", r$effect_key == "hedges_g")

# Mean between three groups: Welch ANOVA
df3 <- df; df3$.y <- df3$num
r <- sme_test_groups(write(df3), "mean")
ref <- oneway.test(num ~ .g, data = df3, var.equal = FALSE)
check("groups mean 3: Welch ANOVA p", close_to(r$p_value, ref$p.value))

# Proportion against a target: exact binomial
r <- sme_test_target(p, "proportion", 0.5)
ref <- binom.test(sum(df$.y), n, p = 0.5)
check("target prop: binomial p", close_to(r$p_value, ref$p.value))

# Mean against a target: one-sample t
r <- sme_test_target(write(df3), "mean", 48)
ref <- t.test(df3$num, mu = 48)
check("target mean: t p", close_to(r$p_value, ref$p.value))

# Paired numeric: paired t
pp <- data.frame(.y = df$num, .y2 = df$num + rnorm(n, 1, 3), check.names = FALSE)
r <- sme_test_paired(write(pp), "mean")
ref <- t.test(pp$.y2, pp$.y, paired = TRUE)
check("paired mean: t p", close_to(r$p_value, ref$p.value))

# Paired yes/no: McNemar
pb <- data.frame(.y = df$.y, .y2 = ifelse(runif(n) < 0.2, 1 - df$.y, df$.y), check.names = FALSE)
r <- sme_test_paired(write(pb), "proportion")
tab <- table(factor(pb$.y, 0:1), factor(pb$.y2, 0:1))
ref <- mcnemar.test(tab, correct = FALSE)
check("paired prop: McNemar p", close_to(r$p_value, ref$p.value))

if (failures > 0) { cat(failures, "test(s) failed\n"); quit(status = 1) }
cat("All test-assistant tests passed.\n")
