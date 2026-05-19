# Empirical Proof Record — **VALIDATED**

**Proof ID:** `80d5b9f33fbaf6d7fabd58c913067e98528686f01fe0172cfcc0e1ed2110679a`  
**Created:** 2026-05-18T01:17:09.791746+00:00

## 1. Claim

> Across 100 random (k, n) binomial pairs (seed=20260518, max_n=1000), scipy's ``binomtest.proportion_ci(method='wilson')`` and statsmodels's ``proportion_confint(method='wilson')`` produce 95% CI bounds that agree to ≤ 1e-09 on both lower and upper endpoints. (RFC 0002 Phase E1: cross-framework validation at the statistical-primitive layer.)

- **Operationalisation:** Generate N pairs (k, n) with k ~ Uniform(0, n), n ~ Uniform(2, max_n). For each pair, compute the Wilson CI at the configured confidence under both backends. Compute max_abs_diff = max over pairs of max(|low_scipy - low_sm|, |high_scipy - high_sm|). VALIDATED iff max_abs_diff ≤ tolerance.
- **Threshold:** `max_absolute_ci_difference <= 1e-09 proportion`
- **H0:** scipy and statsmodels disagree on the Wilson CI by more than the floating-point tolerance — at least one implementation has a defect.
- **H1:** Both libraries evaluate the same closed-form Wilson CI and produce identical bounds to floating-point tolerance.

## 2. Verdict

**Outcome:** VALIDATED  
**Observed:** `3.3306690738754696e-16`

100 pairs checked; max |low_scipy - low_sm| = 1.110e-16; max |high_scipy - high_sm| = 3.331e-16; max overall = 3.331e-16 (≤ 1e-09 tol)

## 3. Pre-registration

- Registered at: `2026-05-18T01:17:09.581755+00:00`
- Config hash: `ab8fb015887c4a2ac85c8b2ffe1e676a730cb4a473e1993bc272b9a0e2bf10bc`
- Data hash: `ab8fb015887c4a2ac85c8b2ffe1e676a730cb4a473e1993bc272b9a0e2bf10bc`

_Generate 100 random (k, n) binomial pairs with seed=20260518, n ∈ [2, 1000]. For each compute the 95% Wilson CI under scipy (binomtest.proportion_ci) AND statsmodels (proportion_confint). Track the maximum absolute difference on both CI bounds across pairs. VALIDATED iff max_abs_diff ≤ 1e-09._

## 4. Data

- Substrate: `scipy+statsmodels-cross-framework` @ `352718907b02`
- Dataset: `synthetic-binomial-pairs` (synthetic-binomial-pairs, 100 records, hash `ab8fb015887c…`)

## 5. Evidence

| pillar | statistic | value | 95% CI | library |
|---|---|---|---|---|
| `wilson_ci_scipy_vs_statsmodels` | `max_absolute_ci_difference` | `3.3306690738754696e-16` | — | scipy 1.17.1 |

## 6. Signature

`b41472097b95c3706beb31c251cdae416275dfaec44f25e2be8883112ae90889`
