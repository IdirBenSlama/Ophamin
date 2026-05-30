# Empirical Proof Record — **VALIDATED**

**Proof ID:** `850146a8ff97404b962909327ec17ae5d4d92dfba2d81a94718d8538ac08d5b3`  
**Created:** 2026-05-24T03:30:06.276145+00:00

## 1. Claim

> Across 30 synthetic (x, y) pairs of size 100 (seed=20260518), ``scipy.stats.pearsonr``, ``numpy.corrcoef``, and ``pingouin.corr(method='pearson')`` produce Pearson r values that agree to ≤ 1e-09 across all three pairwise comparisons. (RFC 0002 Phase E1: cross-framework validation at the statistical-primitive layer; three-way variant.)

- **Operationalisation:** Generate N (x, y) pairs where x ~ Normal(0, 1) and y = ρ_target × x + sqrt(1 - ρ_target²) × Normal(0, 1) for a sweep of ρ_target across [-0.9, 0.9]. Compute Pearson r under each of scipy, numpy, pingouin. Compute max_abs_diff = max over (pair, backend-comparison) of |r_a - r_b|. VALIDATED iff max_abs_diff ≤ tolerance across all three pairwise comparisons.
- **Threshold:** `max_absolute_pearson_difference <= 1e-09 correlation`
- **H0:** At least one backend pair (scipy↔numpy, scipy↔pingouin, numpy↔pingouin) disagrees on Pearson r by more than the floating-point tolerance.
- **H1:** All three backends compute identical Pearson r to floating-point tolerance across every pair.

## 2. Verdict

**Outcome:** VALIDATED  
**Observed:** `3.3306690738754696e-16`

30 pairs × 3 backends; max pairwise |Δr| = 3.331e-16 on scipy_vs_numpy (≤ 1e-09 tol)

## 3. Pre-registration

- Registered at: `2026-05-24T03:30:06.003730+00:00`
- Config hash: `395ced3ae94d681473ffeddcaa298fd2d83f246762c44c4d38e6f94ea692ddbb`
- Data hash: `395ced3ae94d681473ffeddcaa298fd2d83f246762c44c4d38e6f94ea692ddbb`

_Generate 30 (x, y) pairs of size 100 with target Pearson correlations sweeping [-0.9, 0.9], seed=20260518. Compute Pearson r under scipy.stats.pearsonr, numpy.corrcoef, and pingouin.corr(method='pearson'). For each pair, compute the three pairwise absolute differences. Track the maximum. VALIDATED iff max_abs_diff ≤ 1e-09._

## 4. Data

- Substrate: `scipy+numpy+pingouin-cross-framework` @ `ad2afd4070ac`
- Dataset: `synthetic-correlated-pairs-pearson` (synthetic-correlated-pairs, 30 records, hash `395ced3ae94d…`)

## 5. Evidence

| pillar | statistic | value | 95% CI | library |
|---|---|---|---|---|
| `pearson_scipy_vs_numpy_vs_pingouin` | `max_absolute_pearson_difference` | `3.3306690738754696e-16` | — | scipy 1.17.1 |

## 6. Signature

`87e55cfb2898dd4ace1f022e1476e4e027c93dcf45148706d413b62d8c577270`
