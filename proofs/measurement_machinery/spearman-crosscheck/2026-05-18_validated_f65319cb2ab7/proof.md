# Empirical Proof Record — **VALIDATED**

**Proof ID:** `f65319cb2ab7eb3d91fe455fd5cc6518a6ec54843779bd7c91be8875fb7f8207`  
**Created:** 2026-05-18T01:17:10.194544+00:00

## 1. Claim

> Across 30 synthetic (x, y) pairs of size 100 (seed=20260518), ``scipy.stats.spearmanr`` and ``pingouin.corr(method='spearman')`` produce Spearman ρ values that agree to ≤ 1e-09. (RFC 0002 Phase E1: cross-framework validation at the statistical-primitive layer.)

- **Operationalisation:** Generate N (x, y) pairs where x ~ Normal(0, 1) and y = ρ_target × x + sqrt(1 - ρ_target²) × Normal(0, 1) for a sweep of ρ_target. Compute Spearman ρ under both backends. Compute max_abs_diff = max over pairs of |ρ_scipy - ρ_pingouin|. VALIDATED iff max_abs_diff ≤ tolerance.
- **Threshold:** `max_absolute_spearman_difference <= 1e-09 correlation`
- **H0:** scipy and pingouin disagree on Spearman ρ by more than the floating-point tolerance — at least one library has a defect or default-behaviour drift.
- **H1:** Both libraries compute identical Spearman ρ to floating-point tolerance across every pair.

## 2. Verdict

**Outcome:** VALIDATED  
**Observed:** `0.0`

30 pairs checked; max |rho_scipy - rho_pingouin| = 0.000e+00 (≤ 1e-09 tol)

## 3. Pre-registration

- Registered at: `2026-05-18T01:17:10.012891+00:00`
- Config hash: `4e41be096c5011fb2c2bed2d180c541c475dee78c3dff955834652a4df22fbf6`
- Data hash: `4e41be096c5011fb2c2bed2d180c541c475dee78c3dff955834652a4df22fbf6`

_Generate 30 (x, y) pairs of size 100 with target Spearman correlations sweeping [-0.9, 0.9], seed=20260518. Compute Spearman ρ under scipy.stats.spearmanr AND pingouin.corr(method='spearman'). Track the maximum absolute difference. VALIDATED iff max_abs_diff ≤ 1e-09._

## 4. Data

- Substrate: `scipy+pingouin-cross-framework` @ `352718907b02`
- Dataset: `synthetic-correlated-pairs` (synthetic-correlated-pairs, 30 records, hash `4e41be096c50…`)

## 5. Evidence

| pillar | statistic | value | 95% CI | library |
|---|---|---|---|---|
| `spearman_scipy_vs_pingouin` | `max_absolute_spearman_difference` | `0.0` | — | scipy 1.17.1 |

## 6. Signature

`f3bd04b3c5c7e1d299a16e37ae80b3c2f048865a9e58d67ab6fe5590972f6890`
