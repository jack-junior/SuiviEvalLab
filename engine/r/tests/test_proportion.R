# R engine tests, no testthat dependency: Rscript engine/r/tests/test_proportion.R
# Each SuiviEvalLab function is compared with the equivalent direct R call.

# Run from the repository root, or set SME_R_DIR.
r_dir <- Sys.getenv("SME_R_DIR", "engine/r")
for (f in list.files(file.path(r_dir, "R"), pattern = "\\.R$", full.names = TRUE)) sys.source(f, envir = globalenv())

failures <- 0
check <- function(nom, condition) {
  if (isTRUE(condition)) cat("OK   ", nom, "\n") else { cat("FAIL", nom, "\n"); failures <<- failures + 1 }
}
close_to <- function(a, b, tol = 1e-12) isTRUE(all.equal(a, b, tolerance = tol))

# Test data written as Arrow IPC by polars, as the Python engine does
# (fixture generated once and committed).
path <- file.path(r_dir, "tests", "fixtures", "echantillon.arrows")
df <- sme_read_table(path)

# 1. Simple sample = direct prop.test
r1 <- sme_proportion(path, "y", "Oui")
ok <- df[!is.na(df$y), ]
ref <- prop.test(sum(ok$y == "Oui"), nrow(ok), correct = FALSE)
check("simple: estimate", close_to(r1$estimate, unname(ref$estimate)))
check("simple: CI", close_to(c(r1$ci_low, r1$ci_high), as.numeric(ref$conf.int)))
check("simple: n excludes missing values", r1$n == nrow(ok))

# 2. Survey design = direct svyciprop
r2 <- sme_proportion(path, "y", "Oui", weights = "w", strata = "s", cluster = "g")
ok$succes <- as.numeric(ok$y == "Oui")
d <- survey::svydesign(ids = ~g, strata = ~s, weights = ~w, data = ok, nest = TRUE)
ref2 <- survey::svyciprop(~succes, d, method = "logit")
check("design: estimate", close_to(r2$estimate, as.numeric(ref2)))
check("design: CI", close_to(c(r2$ci_low, r2$ci_high), as.numeric(attr(ref2, "ci"))))

# 3. The returned script is present
check("script present", grepl("svyciprop", r2$script))

# 4. Clear error on a missing variable
msg <- tryCatch({ sme_proportion(path, "absente", "Oui"); "" }, error = conditionMessage)
check("missing variable: clear message", grepl("Variable absente", msg))

if (failures > 0) quit(status = 1)
cat("All R tests passed.\n")
