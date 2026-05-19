# Empirical Proof Record — **VALIDATED**

**Proof ID:** `e71be64487df9f56fa4de2636f605a026287be5937621432d0c7daa8d4c30918`  
**Created:** 2026-05-18T02:18:48.338377+00:00

## 1. Claim

> Across 30 synthetic (x, y) sample pairs of size 50 per group drawn from a rotation of normal, log-normal, and Cauchy distributions with varying shift parameters (seed=20260518), ``scipy.stats.mannwhitneyu(use_continuity=True)`` and ``pingouin.mwu`` produce Mann-Whitney U statistics AND two-sided p-values that agree to ≤ 1e-09 across every pair. (RFC 0002 Phase E1: cross-framework validation; first non-parametric variant.)

- **Operationalisation:** Generate N (x, y) pairs cycling through three distribution shapes (Normal(0,1), LogNormal(0,1), Cauchy(0,1)) with a sweep of location shifts. For each pair, compute Mann-Whitney U + two-sided p under both backends with use_continuity=True. Compute max_abs_diff = max over (pair, statistic ∈ {U, p}) of |stat_scipy - stat_pingouin|. VALIDATED iff max_abs_diff ≤ tolerance.
- **Threshold:** `max_absolute_mannwhitneyu_difference <= 1e-09 U_or_p`
- **H0:** scipy and pingouin disagree on Mann-Whitney U OR the two-sided p-value by more than the floating-point tolerance under matched continuity settings.
- **H1:** Both backends compute identical U AND p to floating-point tolerance across every pair.

## 2. Verdict

**Outcome:** VALIDATED  
**Observed:** `0.0`

30 pairs × 2 backends × 2 statistics; max pairwise |Δ| = 0.000e+00 on none (≤ 1e-09 tol)

## 3. Pre-registration

- Registered at: `2026-05-18T02:18:48.157657+00:00`
- Config hash: `ad3e15120cc852c18795179166db8f788a19e5b9cfe779b781ed5148588eb204`
- Data hash: `ad3e15120cc852c18795179166db8f788a19e5b9cfe779b781ed5148588eb204`

_Generate 30 (x, y) sample pairs of size 50 per group, cycling through Normal / LogNormal / Cauchy distributions with location shifts sweeping [-1, 1], seed=20260518. Compute Mann-Whitney U + two-sided p under scipy.stats.mannwhitneyu(use_continuity=True) AND pingouin.mwu (same default). For each pair, compute |ΔU| and |Δp|. Track the maximum of either. VALIDATED iff max_abs_diff ≤ 1e-09._

## 4. Data

- Substrate: `scipy+pingouin-cross-framework` @ `8750cd153e7b`
- Dataset: `synthetic-mann-whitney-mixed-distributions` (synthetic-mann-whitney-mixed-distributions, 30 records, hash `ad3e15120cc8…`)

## 5. Evidence

| pillar | statistic | value | 95% CI | library |
|---|---|---|---|---|
| `mann_whitney_u_scipy_vs_pingouin` | `max_absolute_mannwhitneyu_difference` | `0.0` | — | scipy 1.17.1 |

## 6. Signature

`dffbbb06a016e1c35ecd1bfb2cdfb247fac3e6852b6197e4c4d40d01bd0a85b9`
