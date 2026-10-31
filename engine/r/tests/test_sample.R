# Sample size: against textbook values and direct R calls.
for (f in list.files("engine/r/R", full.names = TRUE)) source(f)
ok <- function(cond, msg) if (!isTRUE(cond)) stop("FAILED: ", msg) else cat("ok:", msg, "\n")

# Cochran: p = 0.5, margin 5 %, 95 % -> 384.1 (the classic 384 or 385).
r <- sme_sample_size("estimate_prop", p = 0.5, margin = 0.05)
ok(abs(r$n0 - 384.1459) < 1e-3 && r$n == 385, "Cochran 384.1 -> 385")

# Design effect 2, population 10 000, 3 domains, 90 % response.
r <- sme_sample_size("estimate_prop", p = 0.5, margin = 0.05, deff = 2, population = 10000, domains = 3, response = 0.9)
n_fpc <- 768.2918 / (1 + (768.2918 - 1) / 10000)
ok(abs(r$n_fpc - n_fpc) < 1e-3, "finite population correction")
ok(r$n == ceiling(n_fpc * 3 / 0.9), "domains and response")
ok(grepl("finite population", r$script), "script lists every step")

# Mean: sd 10, margin 2 -> (1.96 * 10 / 2)^2 = 96.04.
r <- sme_sample_size("estimate_mean", sd = 10, margin = 2)
ok(abs(r$n0 - (qnorm(0.975) * 5)^2) < 1e-9 && r$n == 97, "mean")

# Change from 40 % to 50 %, 80 % power: power.prop.test gives 387.3 per round.
r <- sme_sample_size("compare_prop", p = 0.4, p2 = 0.5, deff = 1.5)
ref <- power.prop.test(p1 = 0.4, p2 = 0.5, power = 0.8)$n
ok(abs(r$n0 - ref) < 1e-9 && r$per_round && r$n == ceiling(ref * 1.5), "two rounds, proportions")
# Population size does not change a comparison.
ok(sme_sample_size("compare_prop", p = 0.4, p2 = 0.5, population = 500)$n == ceiling(ref), "no FPC on comparisons")

r <- sme_sample_size("compare_mean", sd = 10, delta = 3)
ok(abs(r$n0 - power.t.test(delta = 3, sd = 10, power = 0.8)$n) < 1e-9, "two rounds, means")

ok(inherits(try(sme_sample_size("estimate_prop", p = 1.2, margin = 0.05), silent = TRUE), "try-error"), "p out of range refused")
