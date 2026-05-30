# Empirical Proof Record — **VALIDATED**

**Proof ID:** `46579fd975238b022e6355b50b484b62d30164e92f74e4329bcb679b2eb6bfe1`  
**Created:** 2026-05-24T03:29:05.435281+00:00

## 1. Claim

> Across 30 synthetic three-group datasets of size 30 per group sweeping effect size from null to strong (seed=20260518), ``scipy.stats.f_oneway``, ``statsmodels.stats.anova.anova_lm`` (via OLS), and ``pingouin.anova`` produce F-statistics AND two-sided p-values that agree to ≤ 1e-09 across all pairwise comparisons. (RFC 0002 Phase E1: cross-framework validation; three-way ANOVA variant.)

- **Operationalisation:** Generate N three-group datasets where each group has size n and is drawn from Normal(μ_g, σ²) for a sweep of (μ_0, μ_1, μ_2) configurations including null (all μ equal) and alternatives. Compute F and two-sided p under scipy.stats.f_oneway, statsmodels OLS+anova_lm, and pingouin.anova. Compute max_abs_diff = max over (dataset, statistic ∈ {F, p}, backend-pair) of |stat_a - stat_b|. VALIDATED iff max_abs_diff ≤ tolerance.
- **Threshold:** `max_absolute_anova_difference <= 1e-09 F_or_p`
- **H0:** At least one backend pair disagrees on the ANOVA F statistic OR the two-sided p value by more than the floating-point tolerance.
- **H1:** All three backends compute identical F AND p to floating-point tolerance across every dataset.

## 2. Verdict

**Outcome:** VALIDATED  
**Observed:** `7.105427357601002e-14`

30 datasets × 3 backends × 2 statistics; max pairwise |Δ| = 7.105e-14 on (F, scipy_vs_statsmodels) (≤ 1e-09 tol)

## 3. Pre-registration

- Registered at: `2026-05-24T03:29:05.180056+00:00`
- Config hash: `c8e368fe8b61be3829c27bb61d9b320882814e8146783a5fd6f8c5cad4f16f58`
- Data hash: `c8e368fe8b61be3829c27bb61d9b320882814e8146783a5fd6f8c5cad4f16f58`

_Generate 30 three-group datasets of size 30 per group, sweeping effect magnitude from null to 1.5σ, seed=20260518. Compute F and two-sided p under scipy.stats.f_oneway, statsmodels OLS+anova_lm (Type II SS), and pingouin.anova. For each dataset, compute all six pairwise distances (3 backend pairs × 2 statistics). Track the maximum. VALIDATED iff max_abs_diff ≤ 1e-09._

## 4. Data

- Substrate: `scipy+statsmodels+pingouin-cross-framework` @ `ad2afd4070ac`
- Dataset: `synthetic-anova-three-group` (synthetic-anova-three-group, 30 records, hash `c8e368fe8b61…`)

## 5. Evidence

| pillar | statistic | value | 95% CI | library |
|---|---|---|---|---|
| `anova_scipy_vs_statsmodels_vs_pingouin` | `max_absolute_anova_difference` | `7.105427357601002e-14` | — | scipy 1.17.1 |

## 6. Signature

`d453e1a9d3c370b2da0b5429be6f35bf454796e84862bcbf98d65c5d78d9eefc`
