# Sample size for a survey: estimate a proportion or a mean with a given margin
# of error, or detect a change between two independent rounds (baseline and
# endline) with a given power.
#
# The steps are returned one by one (base size, design effect, finite
# population, domains, non-response) so the interface can show the reasoning.

sme_sample_size <- function(goal, p = NULL, p2 = NULL, sd = NULL, margin = NULL, delta = NULL,
                            conf = 0.95, power = 0.8, deff = 1, population = NULL,
                            domains = 1, response = 1) {
  z <- qnorm(1 - (1 - conf) / 2)
  if (goal == "estimate_prop") {
    stopifnot(!is.null(p), !is.null(margin), p > 0, p < 1, margin > 0, margin < 1)
    n0 <- z^2 * p * (1 - p) / margin^2
    method <- "cochran_prop"
    script <- sprintf("n0 <- qnorm(%s)^2 * %s * (1 - %s) / %s^2", 1 - (1 - conf) / 2, p, p, margin)
  } else if (goal == "estimate_mean") {
    stopifnot(!is.null(sd), !is.null(margin), sd > 0, margin > 0)
    n0 <- (z * sd / margin)^2
    method <- "cochran_mean"
    script <- sprintf("n0 <- (qnorm(%s) * %s / %s)^2", 1 - (1 - conf) / 2, sd, margin)
  } else if (goal == "compare_prop") {
    stopifnot(!is.null(p), !is.null(p2), p > 0, p < 1, p2 > 0, p2 < 1, p != p2)
    n0 <- stats::power.prop.test(p1 = p, p2 = p2, sig.level = 1 - conf, power = power)$n
    method <- "power_prop"
    script <- sprintf("n0 <- power.prop.test(p1 = %s, p2 = %s, sig.level = %s, power = %s)$n", p, p2, 1 - conf, power)
  } else if (goal == "compare_mean") {
    stopifnot(!is.null(sd), !is.null(delta), sd > 0, delta != 0)
    n0 <- stats::power.t.test(delta = abs(delta), sd = sd, sig.level = 1 - conf, power = power)$n
    method <- "power_mean"
    script <- sprintf("n0 <- power.t.test(delta = %s, sd = %s, sig.level = %s, power = %s)$n",
                      abs(delta), sd, 1 - conf, power)
  } else {
    stop("Objectif inconnu : ", goal)
  }
  stopifnot(deff >= 1, domains >= 1, response > 0, response <= 1)
  n_deff <- n0 * deff
  # Finite population correction: only for estimates, and only when the population is known.
  n_fpc <- if (!is.null(population) && population > 0 && goal %in% c("estimate_prop", "estimate_mean")) {
    n_deff / (1 + (n_deff - 1) / population)
  } else {
    n_deff
  }
  n_domains <- n_fpc * domains
  n_final <- ceiling(n_domains / response)
  script <- paste(c(
    script,
    sprintf("n <- n0 * %s  # design effect", deff),
    if (!identical(n_fpc, n_deff)) sprintf("n <- n / (1 + (n - 1) / %s)  # finite population", population),
    sprintf("n <- n * %s  # domains", domains),
    sprintf("ceiling(n / %s)  # expected response rate", response)
  ), collapse = "\n")
  list(
    method_key = method,
    per_round = goal %in% c("compare_prop", "compare_mean"),
    n0 = n0,
    n_deff = n_deff,
    n_fpc = n_fpc,
    n_domains = n_domains,
    n = n_final,
    z = z,
    script = script
  )
}
