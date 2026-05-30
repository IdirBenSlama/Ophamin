# Empirical Proof Record — **VALIDATED**

**Proof ID:** `ab9f13103a03b2257566ffb4a090d1b063eeaae5d0ce9833172f01b1cf6a3d6a`  
**Created:** 2026-05-24T03:31:24.810102+00:00

## 1. Claim

> Across 30 synthetic two-sample pairs of size 50 per group with varying effect sizes and variance ratios (seed=20260518), ``scipy.stats.ttest_ind(equal_var=False)``, ``statsmodels.stats.weightstats.ttest_ind(usevar='unequal')``, and ``pingouin.ttest(correction=True)`` produce Welch t-statistics AND two-sided p-values that agree to ≤ 1e-09 across all pairwise comparisons. (RFC 0002 Phase E1: cross-framework validation; three-way variant with genuinely-independent statsmodels.)

- **Operationalisation:** Generate N (x, y) pairs where x ~ Normal(0, σ_x²) and y ~ Normal(δ, σ_y²) for a sweep of δ across [-1.0, 1.0] and variance-ratio σ_y/σ_x across [0.5, 2.0]. Compute Welch's t and two-sided p under each backend. Compute max_abs_diff = max over (pair, statistic ∈ {t, p}, backend-pair) of |stat_a - stat_b|. VALIDATED iff max_abs_diff ≤ tolerance.
- **Threshold:** `max_absolute_welch_difference <= 1e-09 t_or_p`
- **H0:** At least one backend pair disagrees on the Welch t-statistic OR the two-sided p-value by more than the floating-point tolerance.
- **H1:** All three backends compute identical Welch t AND p to floating-point tolerance across every pair.

## 2. Verdict

**Outcome:** VALIDATED  
**Observed:** `1.7763568394002505e-15`

30 pairs × 3 backends × 2 statistics; max pairwise |Δ| = 1.776e-15 on (t, scipy_vs_statsmodels) (≤ 1e-09 tol)

## 3. Pre-registration

- Registered at: `2026-05-24T03:31:24.540632+00:00`
- Config hash: `650f785bb6c4c650aa559236e9e29db30d373ea10f5d1e78b04d1d00602d28c7`
- Data hash: `650f785bb6c4c650aa559236e9e29db30d373ea10f5d1e78b04d1d00602d28c7`

_Generate 30 two-sample pairs of size 50 per group, sweeping effect-size δ across [-1, 1] and variance-ratio σ_y/σ_x across [0.5, 2.0] (deterministically shuffled), seed=20260518. Compute Welch's t AND two-sided p under scipy.stats.ttest_ind(equal_var=False), statsmodels.stats.weightstats.ttest_ind(usevar='unequal'), and pingouin.ttest(correction=True). For each pair, compute all six pairwise distances (3 backend pairs × 2 statistics). Track the maximum. VALIDATED iff max_abs_diff ≤ 1e-09._

## 4. Data

- Substrate: `scipy+statsmodels+pingouin-cross-framework` @ `ad2afd4070ac`
- Dataset: `synthetic-welch-t-pairs` (synthetic-welch-t-pairs, 30 records, hash `650f785bb6c4…`)

## 5. Evidence

| pillar | statistic | value | 95% CI | library |
|---|---|---|---|---|
| `welch_t_scipy_vs_statsmodels_vs_pingouin` | `max_absolute_welch_difference` | `1.7763568394002505e-15` | — | scipy 1.17.1 |

## 6. Signature

`ab68516bc329773a9921e60c061dde7b99b45a6e4651d440aad33c501270def2`
