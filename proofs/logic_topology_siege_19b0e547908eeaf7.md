# Ophamin Empirical Proof Record — `REFUTED`

**Proof ID:** `19b0e547908eeaf788398f6ccdaab54ab72032287b8616e2813887b2e5d294fa`
**Schema:** v1.0  
**Created:** 2026-05-15T13:04:36.612283+00:00

## 1. Identity
- Ophamin: `0.1.0` @ `7133f641c1c1594507e6ca9f4f0878f31915ed5f`
- Substrate: **kimera-swm** @ `a9145ac8937d34d287d7e82d1ed5fb6e5f9d2de4`

## 2. Claim
> On real technical-domain text (Linux kernel commit messages) that clears Kimera's GWF, the substrate's walker reaches sustained traversal (halt_mode == 'exhausted') in >= 60% of cycles — i.e. the topology layer engages on technical reasoning instead of collapsing to amplitude_death.

- **Operationalization:** fraction of GWF-cleared Linux-kernel-commit cycles for which result.halt_mode == 'exhausted'
- **Threshold:** `sustained_traversal_rate_on_cleared >= 0.6 fraction`
- **H0:** P(halt='exhausted' | gwf cleared) < 0.6
- **H1:** P(halt='exhausted' | gwf cleared) >= 0.6

## 3. Pre-registration
- Registered at: `2026-05-15T12:32:23.763443+00:00` (must precede §1 created)
- Config hash: `898ebda325a9dc57963638a7cf5ece8ce90824a72b13ed5d0a404fede9376ce4`
- Data hash: `92a34cc4275008279006eeec2c19cd2b45d7cc6167bf0d368d06fdcadf6a6648`
- Analysis plan: Stream up to 1000 real Linux kernel commit messages (body length in [80, 4000] chars) through Kimera's entity target (Takwin), then measure the fraction of GWF-cleared cycles whose halt_mode is 'exhausted' (the substrate's sustained-traversal mode). Pre-registered threshold: >= 60%. Secondary descriptive evidence reports the full halt-mode distribution, dissonance-event distribution, GWF block rate, and Φ distribution — none post-hoc-claimable.

## 4. Data
- **linux-kernel-commits** (commit_corpus) — 1,445,246 records — `92a34cc427500827…` — https://github.com/torvalds/linux.git

## 5. Evidence
| Pillar | Statistic | Value | Effect | 95% CI | p | Library | Cross-check |
|---|---|---|---|---|---|---|---|
| O.topology.sustained_traversal | sustained_traversal_rate_on_cleared | 0.396369 | — | (0.3598, 0.4342) | — | statsmodels 0.14.6 | n/a |
| O.topology.amplitude_death_rate | amplitude_death_rate_on_cleared | 0.288956 | — | — | — | ophamin 0.1.0 | n/a |
| O.topology.halt_mode_distribution | halt_modes_observed_count | 3 | — | — | — | ophamin 0.1.0 | n/a |
| O.topology.gwf_block_rate | gwf_block_rate_on_linux | 0.339 | — | — | — | ophamin 0.1.0 | n/a |
| O.topology.dissonance_intensity | dissonance_events_count_median | 28 | — | — | — | python-stdlib 3.14 | n/a |
| O.topology.phi_distribution | phi_value_median | 0.20941 | — | — | — | python-stdlib 3.14 | n/a |

## 6. Verdict
### **REFUTED**

- Observed: `0.396369`
- Threshold: `sustained_traversal_rate_on_cleared >= 0.6 fraction`
- Reasoning: walker reached sustained traversal in 262/661 GWF-cleared cycles (39.6%); amplitude_death in 191/661 (28.9%); GWF blocked 339/1000 (33.9%); halt modes observed: {'exhausted': 262, 'selective': 208, 'amplitude_death': 191}; dissonance median=28 (range 0-49); Φ median=0.209; 1000 cycles, 0 adapter errors

## 7. Reproduction
```
PYTHONPATH=src .venv/bin/python -m ophamin.cli scenario logic-topology-siege
```
- Environment lock: 178 entries

## 8. Provenance
- W3C PROV-O graph: 2 entities, 1 activities, 2 agents

## 9. Signature
- `5651b2e897f40c38607df311c27afecd0c96e5e5e710ab5e415c02c8e86b14f9`

---
**✓ Record is well-formed** — falsifiable, pre-registered, traceable, reproducible, attributed.
