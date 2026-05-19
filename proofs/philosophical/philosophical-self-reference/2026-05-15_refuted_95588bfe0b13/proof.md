# Empirical Proof Record — **REFUTED**

**Proof ID:** `95588bfe0b136bd7e8d111a2bc4a44a811796d72e60a719c9b7b556d76988de0`  
**Created:** 2026-05-15T15:01:46.423245+00:00

## 1. Claim

> When fed text describing Kimera's own primitives, the substrate's dissonance signal (dissonance_events_count) is measurably higher than on neutral text — Cohen's d effect size >= 0.30 (one-sided, self-referential > neutral). A REFUTED verdict means the substrate does not differentially process content about itself.

- **Operationalisation:** Cohen's d effect size on per-cycle dissonance_events_count between the self-referential group and the neutral group (pooled-variance form, one-sided)
- **Threshold:** `dissonance_cohens_d_self_ref_vs_neutral >= 0.3 cohens_d`
- **H0:** Cohen's d < 0.30 (substrate does not differentiate self-referential content)
- **H1:** Cohen's d >= 0.30 (substrate differentially processes content about itself)

## 2. Verdict

**Outcome:** REFUTED  
**Observed:** `-0.35857771704220054`

Cohen's d (self_ref - neutral)/pooled_sd = -0.359; self_ref dissonance: n=30 median=17.0 mean=17.37 (range 0-29); neutral dissonance: n=30 median=20.0 mean=20.73 (range 0-45); Mann-Whitney U=323.0, one-sided p=0.9705; 60 cycles, 0 adapter errors

## 3. Pre-registration

- Registered at: `2026-05-15T15:00:44.121975+00:00`
- Config hash: `bf33182ff4be1531ad64054bd6a66d91c1c9c2b40d7891957bb174bde8a4fc6a`
- Data hash: `b3da1b3fe0369ec3140bb4fbce94702c33b7da810ec15d718b3fadf5cd748ca7`

_Stream 30 self-referential sentences (about Kimera's own primitives, hand-curated from CLAUDE.md) + 30 neutral sentences (Enron emails, body in [60, 300] chars) through Kimera's entity target, tagged by group. Compute Cohen's d effect size on dissonance_events_count between groups (one-sided, self_ref > neutral). Mann-Whitney U + p-value reported as secondary descriptive evidence. Pre-registered threshold: Cohen's d >= 0.30 (one-sided)._

## 4. Data

- Substrate: `kimera-swm` @ `179edd233c15`
- Dataset: `enron-email-corpus` (email_corpus, 517401 records, hash `b3da1b3fe036…`)

## 5. Evidence

| pillar | statistic | value | 95% CI | library |
|---|---|---|---|---|
| `O.philosophical.cohens_d` | `dissonance_cohens_d_self_ref_vs_neutral` | `-0.35857771704220054` | — | python-stdlib 3.14 |
| `O.philosophical.mannwhitneyu` | `dissonance_mannwhitneyu_p_value` | `0.9705333972024691` | — | scipy scipy.stats |
| `O.philosophical.self_ref_dissonance` | `self_ref_dissonance_median` | `17.0` | — | python-stdlib 3.14 |
| `O.philosophical.neutral_dissonance` | `neutral_dissonance_median` | `20.0` | — | python-stdlib 3.14 |
| `O.philosophical.self_ref_phi` | `self_ref_phi_median` | `0.24045171557812872` | — | python-stdlib 3.14 |
| `O.philosophical.neutral_phi` | `neutral_phi_median` | `0.22309648380453345` | — | python-stdlib 3.14 |

## 6. Signature

`00b7441f65dbccf26055347e0e2ac5ab998957262a1a4730493de42442249931`
