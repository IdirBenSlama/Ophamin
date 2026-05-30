# Empirical Proof Record — **VALIDATED**

**Proof ID:** `d8f5489669b890919ab3e0128aba43298508f7e85d7e0c96164f2ebaa07fcdc8`  
**Created:** 2026-05-23T23:13:09.117131+00:00

## 1. Claim

> On routine organizational email that clears Kimera's GWF, the dissonance machinery fires (dissonance_events_count >= 1) in >= 90% of cycles (the architectural active-dissonance floor).

- **Operationalisation:** fraction of GWF-cleared Enron-email cycles for which raw['dissonance_events'] is a non-empty list
- **Threshold:** `dissonance_active_rate_on_cleared >= 0.9 fraction`
- **H0:** P(dissonance fires | gwf cleared) < 0.9
- **H1:** P(dissonance fires | gwf cleared) >= 0.9

## 2. Verdict

**Outcome:** VALIDATED  
**Observed:** `1.0`

dissonance fired in 33/33 GWF-cleared cycles (100.0%); GWF blocked 7/40 (17.5%); manipulation_detected in 0/40 (0.0%); dissonance_events median=10 (range 1-41); 40 cycles, 0 adapter errors

![dissonance_active_rate_on_cleared confidence interval](assets/ci_dissonance_active_rate_on_cleared.png)

## 3. Pre-registration

- Registered at: `2026-05-23T23:11:27.560186+00:00`
- Config hash: `5c47a0239c88e8882d03417943db4abe05f799f7d98ba5883102579bcbbf51f3`
- Data hash: `b3da1b3fe0369ec3140bb4fbce94702c33b7da810ec15d718b3fadf5cd748ca7`

_Stream up to 40 real Enron emails (body length in [100, 4000] chars) through Kimera's entity target (Takwin), then measure the fraction of GWF-cleared cycles for which the dissonance machinery fired (dissonance_events_count >= 1). Pre-registered threshold: >= 90%. Secondary descriptive evidence reports the distribution of dissonance_events_count and productive_dissonance_score, the GWF block rate on Enron, and the manipulation_detector rate — none post-hoc-claimable._

## 4. Data

- Substrate: `kimera-swm` @ `78cb9f9fc6a8`
- Dataset: `enron-email-corpus` (email_corpus, 517401 records, hash `b3da1b3fe036…`)

## 5. Evidence

| pillar | statistic | value | 95% CI | library |
|---|---|---|---|---|
| `O.dissonance.active_on_cleared` | `dissonance_active_rate_on_cleared` | `1.0` | (0.8957, 1.0000) | statsmodels 0.14.6 |
| `O.dissonance.intensity_distribution` | `dissonance_events_count_median` | `10.0` | — | python-stdlib 3.14 |
| `O.dissonance.productive_score` | `productive_dissonance_score_median` | `0.2143` | — | python-stdlib 3.14 |
| `O.organizational.gwf_block_rate` | `gwf_block_rate_on_enron` | `0.175` | — | ophamin 0.1.0 |
| `O.organizational.manipulation_rate` | `manipulation_detected_rate_on_enron` | `0.0` | — | ophamin 0.1.0 |

## 6. Signature

`f3dfea3c05e1aa40bdd91adad2ca8586e8745cc03c6c3d25fd0f189993421576`
