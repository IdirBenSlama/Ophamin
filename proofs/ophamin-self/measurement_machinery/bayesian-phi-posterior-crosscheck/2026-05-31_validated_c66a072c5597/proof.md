# Empirical Proof Record — **VALIDATED**

**Proof ID:** `c66a072c5597fb113a1db0303eb4876af745db22e940aaf47a8e353ef819ddf4`  
**Created:** 2026-05-31T18:33:50.568342+00:00

## 1. Claim

> PyMC and NumPyro fit the same NormalMean model on the same synthetic Normal(mu=0.5, sigma=0.2) data (N=200, seed=20260517) and produce posteriors that agree within tolerance: |mu_pymc − mu_numpyro| ≤ 0.1 AND |width_ratio − 1| ≤ 0.5. (RFC 0002 Phase E1: cross-framework validation.)

- **Operationalisation:** Generate N samples from Normal(true_mu, true_sigma) with fixed seed. Fit the same model (mu ~ Normal(0, 10); sigma ~ HalfNormal(1); y ~ Normal(mu, sigma)) under both backends. Extract posterior_mean(mu) + 94% HDI(mu). Compute mean_diff = |mu_pymc - mu_numpyro| and width_ratio = hdi_width_pymc / hdi_width_numpyro. VALIDATED iff both tolerances are satisfied (binary; 1.0 / 0.0). REFUTED if either bound is breached.
- **Threshold:** `cross_framework_agreement >= 1.0 proportion`
- **H0:** PyMC and NumPyro disagree on posterior mean and/or HDI width beyond the documented sampler-noise tolerance — at least one backend is broken or the model is mis-specified.
- **H1:** Both backends produce statistically equivalent posteriors on the same data + model — corroborates the framework's Bayesian inference machinery.

## 2. Verdict

**Outcome:** VALIDATED  
**Observed:** `1.0`

PyMC mu=0.4995, HDI=[0.4696, 0.5261]; NumPyro mu=0.4993, HDI=[0.4709, 0.5277]. mean_diff=0.0003 (≤ 0.1 tol); width_ratio=0.9965 (within ±0.5).

## 3. Pre-registration

- Registered at: `2026-05-31T18:33:50.363203+00:00`
- Config hash: `201b9d70c5b338371d95356a52bbdaab0d8e0b4d0d3734eeba55457372e3aae6`
- Data hash: `201b9d70c5b338371d95356a52bbdaab0d8e0b4d0d3734eeba55457372e3aae6`

_Generate 200 samples from Normal(0.5, 0.2) with seed=20260517. Fit NormalMean model under PyMC (1000 draws × 2 chains) AND NumPyro (1000 samples × 1 chain). Compute mean_difference + hdi_width_ratio. VALIDATED iff mean_difference ≤ 0.1 AND |width_ratio − 1| ≤ 0.5._

## 4. Data

- Substrate: `pymc+numpyro-cross-framework` @ `179df78b0109`
- Dataset: `synthetic-normal` (synthetic-normal, 200 records, hash `201b9d70c5b3…`)

## 5. Evidence

| pillar | statistic | value | 95% CI | library |
|---|---|---|---|---|
| `bayesian_cross_framework_pymc_numpyro` | `cross_framework_agreement` | `1.0` | — | pymc 6.0.0 |

## 6. Signature

`5896f39d4922829a2bd5cd69d5ef9bf5a467efbbbebfa3c7c9053dc1176fa270`
