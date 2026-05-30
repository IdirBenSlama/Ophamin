# Empirical Proof Record — **VALIDATED**

**Proof ID:** `94966e2e44a5f0c30f07a752d76c7ca1e19712eea8c9bcc32a80f357e61b8eaf`  
**Created:** 2026-05-20T15:34:36.709536+00:00

## 1. Claim

> The posterior 94% HDI width on μ_Φ contracts at the theoretical √N rate as the number of observations grows. Specifically, HDI_width(N=200) / HDI_width(N=20) ≤ 0.40 (theoretical contraction factor √(20/200) = 0.316; the 0.40 ceiling allows finite-sample slack).

- **Operationalisation:** Fit a PyMC NUTS posterior to subsamples of the Φ trajectory at sizes 20, 50, 100, 200. Posterior model: μ ~ Normal(prior), σ ~ HalfNormal, y_i ~ Normal(μ, σ). Compute the 94% HDI width on μ at each size; the contraction metric is HDI_width(N=200) / HDI_width(N=20).
- **Threshold:** `hdi_contraction_ratio <= 0.4 ratio`
- **H0:** hdi_contraction_ratio > 0.40 (posterior fails to tighten at the predicted rate — data may be non-Gaussian, non-stationary, or sampler mis-calibrated)
- **H1:** hdi_contraction_ratio <= 0.40 (posterior tightens approximately at the theoretical √N rate, confirming Bayesian inference behaves correctly on the Φ trajectory)

## 2. Verdict

**Outcome:** VALIDATED  
**Observed:** `0.27735050659795846`

HDI width N=20 → N=200: 0.0654 → 0.0181; contraction ratio 0.2774 (theoretical 0.3162; ceiling 0.4000). Empirical Φ mean=0.6140 sd=0.0680 (n=200).

## 3. Pre-registration

- Registered at: `2026-05-20T15:34:36.444141+00:00`
- Config hash: `a47e4fd070e7935308f57886af093806231bc6f94eadb97d79d4d5115e2c1299`
- Data hash: `9ef317fe291445319fcba522d29836dc95d28340eef98c4abfe67be6ecec71c5`

_Fit a PyMC NUTS posterior on the Φ trajectory at sample sizes 20, 50, 100, 200. Compute 94% HDI width on μ at each size; verdict against hdi_contraction_ratio = HDI_width(N=200) / HDI_width(N=20) ≤ 0.40._

## 4. Data

- Substrate: `phi_trajectory+pymc` @ ``
- Dataset: `kimera-phi-trajectory` (phi-value-trajectory, 200 records, hash `9ef317fe2914…`)

## 5. Evidence

| pillar | statistic | value | 95% CI | library |
|---|---|---|---|---|
| `pymc_nuts_posterior` | `hdi_contraction_ratio` | `0.27735050659795846` | — | pymc 6.0.0 |

## 6. Signature

`28d5f4d5efce54d410ddb5febd225da389e7c4511c4898597cbf231ecc7e189b`
