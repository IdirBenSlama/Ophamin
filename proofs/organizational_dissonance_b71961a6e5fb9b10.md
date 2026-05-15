# Ophamin Empirical Proof Record — `VALIDATED`

**Proof ID:** `b71961a6e5fb9b10b8c9a915806b1acc6a3208cd72d90bf74705e153d37405f0`
**Schema:** v1.0  
**Created:** 2026-05-15T12:31:55.424266+00:00

## 1. Identity
- Ophamin: `0.1.0` @ `7133f641c1c1594507e6ca9f4f0878f31915ed5f`
- Substrate: **kimera-swm** @ `83d4655bcf306578ef617834ae9c477dc8b50568`

## 2. Claim
> On routine organizational email that clears Kimera's GWF, the dissonance machinery fires (dissonance_events_count >= 1) in >= 90% of cycles (the architectural active-dissonance floor).

- **Operationalization:** fraction of GWF-cleared Enron-email cycles for which raw['dissonance_events'] is a non-empty list
- **Threshold:** `dissonance_active_rate_on_cleared >= 0.9 fraction`
- **H0:** P(dissonance fires | gwf cleared) < 0.9
- **H1:** P(dissonance fires | gwf cleared) >= 0.9

## 3. Pre-registration
- Registered at: `2026-05-15T11:51:54.333166+00:00` (must precede §1 created)
- Config hash: `634a7fa908610f797105b46eb48c7819fdd19f7a83ad7d94fe6e2dd0e5b1b761`
- Data hash: `b3da1b3fe0369ec3140bb4fbce94702c33b7da810ec15d718b3fadf5cd748ca7`
- Analysis plan: Stream up to 1000 real Enron emails (body length in [100, 4000] chars) through Kimera's entity target (Takwin), then measure the fraction of GWF-cleared cycles for which the dissonance machinery fired (dissonance_events_count >= 1). Pre-registered threshold: >= 90%. Secondary descriptive evidence reports the distribution of dissonance_events_count and productive_dissonance_score, the GWF block rate on Enron, and the manipulation_detector rate — none post-hoc-claimable.

## 4. Data
- **enron-email-corpus** (email_corpus) — 517,401 records — `b3da1b3fe0369ec3…` — https://www.cs.cmu.edu/~enron/enron_mail_20150507.tar.gz

## 5. Evidence
| Pillar | Statistic | Value | Effect | 95% CI | p | Library | Cross-check |
|---|---|---|---|---|---|---|---|
| O.dissonance.active_on_cleared | dissonance_active_rate_on_cleared | 0.974388 | — | (0.9619, 0.9829) | — | statsmodels 0.14.6 | n/a |
| O.dissonance.intensity_distribution | dissonance_events_count_median | 21 | — | — | — | python-stdlib 3.14 | n/a |
| O.dissonance.productive_score | productive_dissonance_score_median | 0.56 | — | — | — | python-stdlib 3.14 | n/a |
| O.organizational.gwf_block_rate | gwf_block_rate_on_enron | 0.102 | — | — | — | ophamin 0.1.0 | n/a |
| O.organizational.manipulation_rate | manipulation_detected_rate_on_enron | 0.003 | — | — | — | ophamin 0.1.0 | n/a |

## 6. Verdict
### **VALIDATED**

- Observed: `0.974388`
- Threshold: `dissonance_active_rate_on_cleared >= 0.9 fraction`
- Reasoning: dissonance fired in 875/898 GWF-cleared cycles (97.4%); GWF blocked 102/1000 (10.2%); manipulation_detected in 3/1000 (0.3%); dissonance_events median=21 (range 0-57); 1000 cycles, 0 adapter errors

## 7. Reproduction
```
PYTHONPATH=src .venv/bin/python -m ophamin.cli scenario organizational-dissonance
```
- Environment lock: 178 entries

## 8. Provenance
- W3C PROV-O graph: 2 entities, 1 activities, 2 agents

## 9. Signature
- `dd1c7ba87b8f2a065975e3b517df596f205a869a302f8555d11278325f5a318b`

---
**✓ Record is well-formed** — falsifiable, pre-registered, traceable, reproducible, attributed.
