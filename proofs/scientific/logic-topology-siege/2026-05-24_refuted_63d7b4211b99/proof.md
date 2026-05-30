# Empirical Proof Record — **REFUTED**

**Proof ID:** `63d7b4211b99115e593107746e8480fd67ffbfeec1e9d63dc5d3b599360d264b`  
**Created:** 2026-05-24T03:31:26.309825+00:00

## 1. Claim

> On real technical-domain text (Linux kernel commit messages) that clears Kimera's GWF, the substrate's walker reaches sustained traversal (halt_mode == 'exhausted') in >= 60% of cycles — i.e. the topology layer engages on technical reasoning instead of collapsing to amplitude_death.

- **Operationalisation:** fraction of GWF-cleared Linux-kernel-commit cycles for which result.halt_mode == 'exhausted'
- **Threshold:** `sustained_traversal_rate_on_cleared >= 0.6 fraction`
- **H0:** P(halt='exhausted' | gwf cleared) < 0.6
- **H1:** P(halt='exhausted' | gwf cleared) >= 0.6

## 2. Verdict

**Outcome:** REFUTED  
**Observed:** `0.125`

walker reached sustained traversal in 4/32 GWF-cleared cycles (12.5%); amplitude_death in 28/32 (87.5%); GWF blocked 8/40 (20.0%); halt modes observed: {'amplitude_death': 28, 'exhausted': 4}; dissonance median=13 (range 0-35); Φ median=0.632; 40 cycles, 0 adapter errors

![sustained_traversal_rate_on_cleared confidence interval](assets/ci_sustained_traversal_rate_on_cleared.png)

## 3. Pre-registration

- Registered at: `2026-05-24T03:29:04.831521+00:00`
- Config hash: `8828d82eff83d5002e25687d42f2897a2478a72604e0eaaf41d13a3a27a87f19`
- Data hash: `92a34cc4275008279006eeec2c19cd2b45d7cc6167bf0d368d06fdcadf6a6648`

_Stream up to 40 real Linux kernel commit messages (body length in [80, 4000] chars) through Kimera's entity target (Takwin), then measure the fraction of GWF-cleared cycles whose halt_mode is 'exhausted' (the substrate's sustained-traversal mode). Pre-registered threshold: >= 60%. Secondary descriptive evidence reports the full halt-mode distribution, dissonance-event distribution, GWF block rate, and Φ distribution — none post-hoc-claimable._

## 4. Data

- Substrate: `kimera-swm` @ `78cb9f9fc6a8`
- Dataset: `linux-kernel-commits` (commit_corpus, 1445246 records, hash `92a34cc42750…`)

## 5. Evidence

| pillar | statistic | value | 95% CI | library |
|---|---|---|---|---|
| `O.topology.sustained_traversal` | `sustained_traversal_rate_on_cleared` | `0.125` | (0.0497, 0.2807) | statsmodels 0.14.6 |
| `O.topology.amplitude_death_rate` | `amplitude_death_rate_on_cleared` | `0.875` | — | ophamin 0.1.0 |
| `O.topology.halt_mode_distribution` | `halt_modes_observed_count` | `2.0` | — | ophamin 0.1.0 |
| `O.topology.gwf_block_rate` | `gwf_block_rate_on_linux` | `0.2` | — | ophamin 0.1.0 |
| `O.topology.dissonance_intensity` | `dissonance_events_count_median` | `13.0` | — | python-stdlib 3.14 |
| `O.topology.phi_distribution` | `phi_value_median` | `0.6323452260010114` | — | python-stdlib 3.14 |

## 6. Signature

`0f1b8f3618145fd6ae2d655ed60f0bf21dd6be8e451f8b0e0705c5b66802d9a3`
