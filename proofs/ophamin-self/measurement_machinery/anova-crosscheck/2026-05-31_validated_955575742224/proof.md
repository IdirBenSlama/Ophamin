# Empirical Proof Record — **VALIDATED**

**Proof ID:** `95557574222495c3948d0cdcbf61f2f6e0bc7f1370924cea4569775891800d5b`  
**Created:** 2026-05-31T18:33:47.584307+00:00

## 1. Claim

> Across 30 synthetic three-group datasets of size 30 per group sweeping effect size from null to strong (seed=20260518), ``scipy.stats.f_oneway``, ``statsmodels.stats.anova.anova_lm`` (via OLS), and ``pingouin.anova`` produce F-statistics AND two-sided p-values that agree to ≤ 1e-09 across all pairwise comparisons. (RFC 0002 Phase E1: cross-framework validation; three-way ANOVA variant.)

- **Operationalisation:** Generate N three-group datasets where each group has size n and is drawn from Normal(μ_g, σ²) for a sweep of (μ_0, μ_1, μ_2) configurations including null (all μ equal) and alternatives. Compute F and two-sided p under scipy.stats.f_oneway, statsmodels OLS+anova_lm, and pingouin.anova. Compute max_abs_diff = max over (dataset, statistic ∈ {F, p}, backend-pair) of |stat_a - stat_b|. VALIDATED iff max_abs_diff ≤ tolerance.
- **Threshold:** `max_absolute_anova_difference <= 1e-09 F_or_p`
- **H0:** At least one backend pair disagrees on the ANOVA F statistic OR the two-sided p value by more than the floating-point tolerance.
- **H1:** All three backends compute identical F AND p to floating-point tolerance across every dataset.

## 2. Verdict

**Outcome:** VALIDATED  
**Observed:** `5.684341886080802e-14`

30 datasets × 3 backends × 2 statistics; max pairwise |Δ| = 5.684e-14 on (F, scipy_vs_pingouin) (≤ 1e-09 tol)

## 3. Pre-registration

- Registered at: `2026-05-31T18:33:47.399117+00:00`
- Config hash: `c8e368fe8b61be3829c27bb61d9b320882814e8146783a5fd6f8c5cad4f16f58`
- Data hash: `c8e368fe8b61be3829c27bb61d9b320882814e8146783a5fd6f8c5cad4f16f58`

_Generate 30 three-group datasets of size 30 per group, sweeping effect magnitude from null to 1.5σ, seed=20260518. Compute F and two-sided p under scipy.stats.f_oneway, statsmodels OLS+anova_lm (Type II SS), and pingouin.anova. For each dataset, compute all six pairwise distances (3 backend pairs × 2 statistics). Track the maximum. VALIDATED iff max_abs_diff ≤ 1e-09._

## 4. Data

- Substrate: `scipy+statsmodels+pingouin-cross-framework` @ `179df78b0109`
- Dataset: `synthetic-anova-three-group` (synthetic-anova-three-group, 30 records, hash `c8e368fe8b61…`)

## 5. Evidence

| pillar | statistic | value | 95% CI | library |
|---|---|---|---|---|
| `anova_scipy_vs_statsmodels_vs_pingouin` | `max_absolute_anova_difference` | `5.684341886080802e-14` | — | scipy 1.17.1 |

## 6. Signature

`0f3a0b2e88881d7ddf794963fdbbab9391dd5599aba8fdbdbe6bd65d1e4fdd41`
