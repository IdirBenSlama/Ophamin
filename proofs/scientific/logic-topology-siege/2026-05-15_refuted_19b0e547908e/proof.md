# Empirical Proof Record — **REFUTED**

**Proof ID:** `19b0e547908eeaf788398f6ccdaab54ab72032287b8616e2813887b2e5d294fa`  
**Created:** 2026-05-15T13:04:36.612283+00:00

## 1. Claim

> On real technical-domain text (Linux kernel commit messages) that clears Kimera's GWF, the substrate's walker reaches sustained traversal (halt_mode == 'exhausted') in >= 60% of cycles — i.e. the topology layer engages on technical reasoning instead of collapsing to amplitude_death.

- **Operationalisation:** fraction of GWF-cleared Linux-kernel-commit cycles for which result.halt_mode == 'exhausted'
- **Threshold:** `sustained_traversal_rate_on_cleared >= 0.6 fraction`
- **H0:** P(halt='exhausted' | gwf cleared) < 0.6
- **H1:** P(halt='exhausted' | gwf cleared) >= 0.6

## 2. Verdict

**Outcome:** REFUTED  
**Observed:** `0.39636913767019666`

walker reached sustained traversal in 262/661 GWF-cleared cycles (39.6%); amplitude_death in 191/661 (28.9%); GWF blocked 339/1000 (33.9%); halt modes observed: {'exhausted': 262, 'selective': 208, 'amplitude_death': 191}; dissonance median=28 (range 0-49); Φ median=0.209; 1000 cycles, 0 adapter errors

![sustained_traversal_rate_on_cleared confidence interval](assets/ci_sustained_traversal_rate_on_cleared.png)

## 3. Pre-registration

- Registered at: `2026-05-15T12:32:23.763443+00:00`
- Config hash: `898ebda325a9dc57963638a7cf5ece8ce90824a72b13ed5d0a404fede9376ce4`
- Data hash: `92a34cc4275008279006eeec2c19cd2b45d7cc6167bf0d368d06fdcadf6a6648`

_Stream up to 1000 real Linux kernel commit messages (body length in [80, 4000] chars) through Kimera's entity target (Takwin), then measure the fraction of GWF-cleared cycles whose halt_mode is 'exhausted' (the substrate's sustained-traversal mode). Pre-registered threshold: >= 60%. Secondary descriptive evidence reports the full halt-mode distribution, dissonance-event distribution, GWF block rate, and Φ distribution — none post-hoc-claimable._

## 4. Data

- Substrate: `kimera-swm` @ `a9145ac8937d`
- Dataset: `linux-kernel-commits` (commit_corpus, 1445246 records, hash `92a34cc42750…`)

## 5. Evidence

| pillar | statistic | value | 95% CI | library |
|---|---|---|---|---|
| `O.topology.sustained_traversal` | `sustained_traversal_rate_on_cleared` | `0.39636913767019666` | (0.3598, 0.4342) | statsmodels 0.14.6 |
| `O.topology.amplitude_death_rate` | `amplitude_death_rate_on_cleared` | `0.28895612708018154` | — | ophamin 0.1.0 |
| `O.topology.halt_mode_distribution` | `halt_modes_observed_count` | `3.0` | — | ophamin 0.1.0 |
| `O.topology.gwf_block_rate` | `gwf_block_rate_on_linux` | `0.339` | — | ophamin 0.1.0 |
| `O.topology.dissonance_intensity` | `dissonance_events_count_median` | `28.0` | — | python-stdlib 3.14 |
| `O.topology.phi_distribution` | `phi_value_median` | `0.20941038886785676` | — | python-stdlib 3.14 |

## 6. Signature

`5651b2e897f40c38607df311c27afecd0c96e5e5e710ab5e415c02c8e86b14f9`
