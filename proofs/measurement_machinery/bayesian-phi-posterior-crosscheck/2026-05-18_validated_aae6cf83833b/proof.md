# Empirical Proof Record — **VALIDATED**

**Proof ID:** `aae6cf83833b7c058602499d96048a0decbccc96ab55b1cfe578067d4ab033da`  
**Created:** 2026-05-18T00:35:49.188818+00:00

## 1. Claim

> PyMC and NumPyro fit the same NormalMean model on the same synthetic Normal(mu=0.5, sigma=0.2) data (N=200, seed=20260518) and produce posteriors that agree within tolerance: |mu_pymc − mu_numpyro| ≤ 0.1 AND |width_ratio − 1| ≤ 0.5. (RFC 0002 Phase E1: cross-framework validation.)

- **Operationalisation:** Generate N samples from Normal(true_mu, true_sigma) with fixed seed. Fit the same model (mu ~ Normal(0, 10); sigma ~ HalfNormal(1); y ~ Normal(mu, sigma)) under both backends. Extract posterior_mean(mu) + 94% HDI(mu). Compute mean_diff = |mu_pymc - mu_numpyro| and width_ratio = hdi_width_pymc / hdi_width_numpyro. VALIDATED iff both tolerances are satisfied (binary; 1.0 / 0.0). REFUTED if either bound is breached.
- **Threshold:** `cross_framework_agreement >= 1.0 proportion`
- **H0:** PyMC and NumPyro disagree on posterior mean and/or HDI width beyond the documented sampler-noise tolerance — at least one backend is broken or the model is mis-specified.
- **H1:** Both backends produce statistically equivalent posteriors on the same data + model — corroborates the framework's Bayesian inference machinery.

## 2. Verdict

**Outcome:** VALIDATED  
**Observed:** `1.0`

PyMC mu=0.5185, HDI=[0.4922, 0.5437]; NumPyro mu=0.5182, HDI=[0.4920, 0.5459]. mean_diff=0.0003 (≤ 0.1 tol); width_ratio=0.9556 (within ±0.5).

## 3. Pre-registration

- Registered at: `2026-05-18T00:35:48.960256+00:00`
- Config hash: `75c3fe823fd3ccbe4e6c87576bc3b1a03148cf4f5979eeb92ad59e9581040535`
- Data hash: `75c3fe823fd3ccbe4e6c87576bc3b1a03148cf4f5979eeb92ad59e9581040535`

_Generate 200 samples from Normal(0.5, 0.2) with seed=20260518. Fit NormalMean model under PyMC (1000 draws × 2 chains) AND NumPyro (1000 samples × 1 chain). Compute mean_difference + hdi_width_ratio. VALIDATED iff mean_difference ≤ 0.1 AND |width_ratio − 1| ≤ 0.5._

## 4. Data

- Substrate: `pymc+numpyro-cross-framework` @ `f489b7dd0da7`
- Dataset: `synthetic-normal` (synthetic-normal, 200 records, hash `75c3fe823fd3…`)

## 5. Evidence

| pillar | statistic | value | 95% CI | library |
|---|---|---|---|---|
| `bayesian_cross_framework_pymc_numpyro` | `cross_framework_agreement` | `1.0` | — | pymc 6.0.0 |

## 6. Signature

`03f48806f9d52d57fdf3cb65b91989e85e93e8978c4864accdac11df07225ed6`
