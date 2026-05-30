# Empirical Proof Record — **VALIDATED**

**Proof ID:** `4abe91b30cd0ec9ede6b8e46d795e0a26b1c4b172cd4774ad5bf372ce8f6dbf9`  
**Created:** 2026-05-23T23:13:23.435527+00:00

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

- Registered at: `2026-05-23T23:13:23.178033+00:00`
- Config hash: `650f785bb6c4c650aa559236e9e29db30d373ea10f5d1e78b04d1d00602d28c7`
- Data hash: `650f785bb6c4c650aa559236e9e29db30d373ea10f5d1e78b04d1d00602d28c7`

_Generate 30 two-sample pairs of size 50 per group, sweeping effect-size δ across [-1, 1] and variance-ratio σ_y/σ_x across [0.5, 2.0] (deterministically shuffled), seed=20260518. Compute Welch's t AND two-sided p under scipy.stats.ttest_ind(equal_var=False), statsmodels.stats.weightstats.ttest_ind(usevar='unequal'), and pingouin.ttest(correction=True). For each pair, compute all six pairwise distances (3 backend pairs × 2 statistics). Track the maximum. VALIDATED iff max_abs_diff ≤ 1e-09._

## 4. Data

- Substrate: `scipy+statsmodels+pingouin-cross-framework` @ `f9e0012b75f2`
- Dataset: `synthetic-welch-t-pairs` (synthetic-welch-t-pairs, 30 records, hash `650f785bb6c4…`)

## 5. Evidence

| pillar | statistic | value | 95% CI | library |
|---|---|---|---|---|
| `welch_t_scipy_vs_statsmodels_vs_pingouin` | `max_absolute_welch_difference` | `1.7763568394002505e-15` | — | scipy 1.17.1 |

## 6. Signature

`2b8537e99eddb60491abbe2cf7dfb828f25ba4d7571a85000a9d41d2af28a3a2`
