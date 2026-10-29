# Statistics

Summary of the statistical catalogue. Every method below is computed in R.

## 1. Principles

1. Established methods only (base R and maintained packages); no hand-written re-implementation when a reference implementation exists.
2. A confidence interval with every estimate (95 % by default).
3. An effect size with every test.
4. Survey designs are respected everywhere (`survey` package) when weights, strata or clusters are declared; otherwise simple random sampling.
5. Robust defaults: Welch t-test and Welch ANOVA.
6. Assumptions are checked; when they fail, the alternative is used and explained.
7. Careful wording: statistical versus practical significance, no causal language on comparisons.
8. Each result returns the R script that reproduces it.

## 2. Defaults

| Setting | Default |
|---|---|
| Confidence level | 95 % |
| Significance threshold | 0.05 |
| Multiple comparisons | Holm |
| Missing values | Excluded per analysis, counts always reported |
| Imputation | None in 1.0 |

## 3. Estimates

| Measure | Simple sample | Survey design |
|---|---|---|
| Proportion | Wilson interval, `prop.test(correct = FALSE)` (implemented in `sme_estimate`) | `svyciprop(method = "logit")` (implemented); `beta` near 0 or 1 (planned) |
| Mean | `t.test` (implemented in `sme_estimate`) | `svymean` + `confint(df = degf())` (implemented) |
| Median | order-statistic interval | `svyquantile(ci = TRUE)` |
| Total | `sum` | `svytotal` |
| Ratio | delta method on `svydesign(ids = ~1)` | `svyratio` |

**Achievement rate** = (achieved − baseline) / (target − baseline) × 100. Without baseline: achieved / target (increase) or target / achieved (decrease). Status: achieved ≥ 90 %, on track ≥ 60 %, behind < 60 %.

### Implemented in version 0.2 (`engine/r/R/estimate.R`)

- `sme_estimate`: proportion or mean of an indicator, with its 95 % interval, overall and by breakdown group (each group estimated on the subset of the same design). Several stratification columns are combined with `interaction()`. Lonely PSUs: `survey.lonely.psu = "adjust"`.
- `sme_compare`: two independent rounds (baseline and endline). With a design, each round is estimated on its own design and the difference uses SE = sqrt(SE_A² + SE_B²) with a z test. Without a design: `prop.test` on two samples (proportions) or Welch `t.test` (means). Effect size: Cohen's h (proportions) or Cohen's d (means).
- A value already at or beyond the target in the planned direction is "achieved" whatever the achievement rate.
- Missing values: the dataset's missing codes (`NA`, empty, and others listed per dataset) and the cleaning journal decide what is missing; missing outcomes are left out of the denominator.

## 4. Test assistant

| Question | Default test | Fallback | With survey design |
|---|---|---|---|
| Two groups, proportion | Chi-squared without correction | Fisher exact (expected count < 5) | `svychisq` (Rao-Scott) |
| Two categorical variables | Chi-squared | Fisher with simulated p | `svychisq` |
| Two groups, mean | Welch t-test | Mann-Whitney | `svyttest` |
| Three or more groups, mean | Welch ANOVA | Kruskal-Wallis | `svyglm` + `regTermTest` |
| Same people before and after, numeric | Paired t-test | Wilcoxon signed-rank | later |
| Same people before and after, yes/no | McNemar | exact binomial | later |
| Baseline versus endline surveys | As two groups, with survey round as group | idem | stacked designs |
| Proportion versus target | Exact binomial | | z-test on `svyciprop` |
| Mean versus target | One-sample t-test | One-sample Wilcoxon | `svymean` + z-test |
| Two numeric variables | Pearson | Spearman, Kendall | later |
| Ordinal score between groups | Mann-Whitney or Kruskal-Wallis | | later |

Effect sizes: difference in proportions (Newcombe CI), risk and odds ratios, Cramér's V, Hedges' g, omega squared, rank-biserial correlation, rank epsilon squared (`effectsize`).

## 5. Validation

1. Each `sme_*` function equals the direct R call (relative difference < 1e-12).
2. Independent references: NIST StRD, published examples, `survey` documentation.
3. Cross-check with scipy and statsmodels on synthetic data.
4. End-to-end: from import to Word report, numbers equal expected values.
5. Python and R evaluations of the same rule tree are identical.

Any R or package update replays the whole validation before release.
