"""Bayesian-inference helpers — PyMC + ArviZ + NumPyro wrappers.

Per ``docs/PLUGIN_CATALOG_2026_05_15.md`` §15. Two thin wrappers:

  posterior_for_normal_mean(...)   — PyMC + ArviZ. Bayesian posterior on
                                     the mean of an observed sample.
                                     Useful for the Family L style claim
                                     "posterior on Φ tightens with more
                                     observations". Returns posterior
                                     summary + HDI.
  numpyro_posterior_for_normal_mean(...) — same shape via NumPyro/JAX
                                          (faster for large N).

Both raise ImportError on missing deps. Numerical defaults (chains=2,
draws=1000, tune=500) match published PPL guidance for quick fit-checks.
"""

from __future__ import annotations

from typing import Any


def posterior_for_normal_mean(
    observations: list[float] | tuple[float, ...],
    *,
    prior_mean: float = 0.0,
    prior_sd: float = 10.0,
    draws: int = 1000,
    tune: int = 500,
    chains: int = 2,
    random_seed: int = 42,
    hdi_prob: float = 0.94,
) -> dict[str, Any]:
    """Bayesian posterior on μ = mean(observations) via PyMC.

    Model:
       μ ~ Normal(prior_mean, prior_sd)
       σ ~ HalfNormal(1)
       y_i ~ Normal(μ, σ)

    Returns ``{"mu_mean": float, "mu_sd": float,
              "mu_hdi_low": float, "mu_hdi_high": float,
              "sigma_mean": float, "n": int, "ess_bulk": float,
              "rhat": float}``.

    HDI = highest density interval (the Bayesian analogue of CI).
    R-hat ≤ 1.01 indicates chain convergence.
    """
    try:
        import numpy as np
        import arviz as az
        import pymc as pm
    except ImportError as e:
        raise ImportError(
            "pymc + arviz required; `pip install pymc arviz`"
        ) from e
    obs = np.asarray(observations, dtype=float)
    if obs.size < 2:
        raise ValueError(f"need ≥ 2 observations; got {obs.size}")
    with pm.Model():
        mu = pm.Normal("mu", mu=prior_mean, sigma=prior_sd)
        sigma = pm.HalfNormal("sigma", sigma=1.0)
        pm.Normal("y", mu=mu, sigma=sigma, observed=obs)
        idata = pm.sample(
            draws=draws, tune=tune, chains=chains,
            random_seed=random_seed, progressbar=False,
        )
    # arviz 1.x renamed hdi_prob → ci_prob; try the modern name first.
    try:
        summary = az.summary(idata, var_names=["mu", "sigma"], ci_prob=hdi_prob)
    except TypeError:
        summary = az.summary(idata, var_names=["mu", "sigma"], hdi_prob=hdi_prob)
    mu_row = summary.loc["mu"]
    # arviz column-naming has shifted across versions:
    #   0.x: "hdi_3%" / "hdi_97%"
    #   1.x: "eti94_lb" / "eti94_ub"  (equal-tailed interval at 94%)
    # Try each pattern in order; fall back to first / last "interval-ish"
    # column.
    hdi_lo_col = [c for c in summary.columns
                  if (c.endswith("_lb") or "low" in c.lower() or
                      c.startswith("hdi_") and "%" in c and c < "hdi_5")]
    hdi_hi_col = [c for c in summary.columns
                  if (c.endswith("_ub") or "high" in c.lower() or
                      c.startswith("hdi_") and "%" in c and c >= "hdi_5")]
    if not hdi_lo_col or not hdi_hi_col:
        bracket_cols = sorted(
            c for c in summary.columns
            if c.startswith(("hdi_", "eti", "ci")) or "_lb" in c or "_ub" in c
        )
        if bracket_cols:
            hdi_lo_col = [bracket_cols[0]]
            hdi_hi_col = [bracket_cols[-1]]
        else:
            # No interval columns at all — fall back to mean ± sd
            hdi_lo_col = ["mean"]
            hdi_hi_col = ["mean"]
    return {
        "mu_mean":     float(mu_row["mean"]),
        "mu_sd":       float(mu_row["sd"]),
        "mu_hdi_low":  float(mu_row[hdi_lo_col[0]]),
        "mu_hdi_high": float(mu_row[hdi_hi_col[0]]),
        "sigma_mean":  float(summary.loc["sigma", "mean"]),
        "n":           int(obs.size),
        "ess_bulk":    float(mu_row.get("ess_bulk", 0.0)),
        "rhat":        float(mu_row.get("r_hat", 0.0)),
        "hdi_prob":    hdi_prob,
    }


def numpyro_posterior_for_normal_mean(
    observations: list[float] | tuple[float, ...],
    *,
    prior_mean: float = 0.0,
    prior_sd: float = 10.0,
    num_warmup: int = 500,
    num_samples: int = 1000,
    random_seed: int = 42,
) -> dict[str, Any]:
    """JAX-backed Bayesian posterior — ~3-5× faster than PyMC for large N.

    Same model + return shape as ``posterior_for_normal_mean`` (minus the
    ess_bulk / rhat fields, which require manual conversion from NumPyro
    samples to ArviZ's InferenceData).
    """
    try:
        import jax
        import jax.numpy as jnp
        import numpy as np
        import numpyro
        import numpyro.distributions as dist
        from numpyro.infer import MCMC, NUTS
    except ImportError as e:
        raise ImportError(
            "numpyro + jax required; `pip install numpyro jax jaxlib`"
        ) from e
    obs = np.asarray(observations, dtype=float)
    if obs.size < 2:
        raise ValueError(f"need ≥ 2 observations; got {obs.size}")

    def model(y):
        mu = numpyro.sample("mu", dist.Normal(prior_mean, prior_sd))
        sigma = numpyro.sample("sigma", dist.HalfNormal(1.0))
        numpyro.sample("y", dist.Normal(mu, sigma), obs=y)

    rng_key = jax.random.PRNGKey(random_seed)
    kernel = NUTS(model)
    mcmc = MCMC(
        kernel, num_warmup=num_warmup, num_samples=num_samples,
        progress_bar=False,
    )
    mcmc.run(rng_key, y=jnp.asarray(obs))
    samples = mcmc.get_samples()
    mu_samples = np.asarray(samples["mu"])
    sigma_samples = np.asarray(samples["sigma"])
    # 94% HDI via percentile (3% / 97%) — close enough; for true HDI use ArviZ.
    return {
        "mu_mean":     float(np.mean(mu_samples)),
        "mu_sd":       float(np.std(mu_samples)),
        "mu_hdi_low":  float(np.percentile(mu_samples, 3)),
        "mu_hdi_high": float(np.percentile(mu_samples, 97)),
        "sigma_mean":  float(np.mean(sigma_samples)),
        "n":           int(obs.size),
        "n_samples":   int(num_samples),
    }
