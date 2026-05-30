# Empirical Proof Record — **REFUTED**

**Proof ID:** `8c7306acee3769380751e4e4bb7a8336f1a5491a725f6e992c26219f8ae8180a`  
**Created:** 2026-05-24T03:31:55.462164+00:00

## 1. Claim

> When fed text describing Kimera's own primitives, the substrate's dissonance signal (dissonance_events_count) is measurably higher than on neutral text — Cohen's d effect size >= 0.30 (one-sided, self-referential > neutral). A REFUTED verdict means the substrate does not differentially process content about itself.

- **Operationalisation:** Cohen's d effect size on per-cycle dissonance_events_count between the self-referential group and the neutral group (pooled-variance form, one-sided)
- **Threshold:** `dissonance_cohens_d_self_ref_vs_neutral >= 0.3 cohens_d`
- **H0:** Cohen's d < 0.30 (substrate does not differentiate self-referential content)
- **H1:** Cohen's d >= 0.30 (substrate differentially processes content about itself)

## 2. Verdict

**Outcome:** REFUTED  
**Observed:** `-0.13162162750960466`

Cohen's d (self_ref - neutral)/pooled_sd = -0.132; self_ref dissonance: n=30 median=4.5 mean=7.70 (range 0-21); neutral dissonance: n=10 median=7.5 mean=8.60 (range 0-23); Mann-Whitney U=145.5, one-sided p=0.5623; 40 cycles, 0 adapter errors

## 3. Pre-registration

- Registered at: `2026-05-24T03:30:07.777116+00:00`
- Config hash: `a6849a2807fd2bef4900b84b42422662e58dc7afa2d3e492a958788b4cd76973`
- Data hash: `b3da1b3fe0369ec3140bb4fbce94702c33b7da810ec15d718b3fadf5cd748ca7`

_Stream 30 self-referential sentences (about Kimera's own primitives, hand-curated from CLAUDE.md) + 30 neutral sentences (Enron emails, body in [60, 300] chars) through Kimera's entity target, tagged by group. Compute Cohen's d effect size on dissonance_events_count between groups (one-sided, self_ref > neutral). Mann-Whitney U + p-value reported as secondary descriptive evidence. Pre-registered threshold: Cohen's d >= 0.30 (one-sided)._

## 4. Data

- Substrate: `kimera-swm` @ `78cb9f9fc6a8`
- Dataset: `enron-email-corpus` (email_corpus, 517401 records, hash `b3da1b3fe036…`)

## 5. Evidence

| pillar | statistic | value | 95% CI | library |
|---|---|---|---|---|
| `O.philosophical.cohens_d` | `dissonance_cohens_d_self_ref_vs_neutral` | `-0.13162162750960466` | — | python-stdlib 3.14 |
| `O.philosophical.mannwhitneyu` | `dissonance_mannwhitneyu_p_value` | `0.5622579635117437` | — | scipy scipy.stats |
| `O.philosophical.self_ref_dissonance` | `self_ref_dissonance_median` | `4.5` | — | python-stdlib 3.14 |
| `O.philosophical.neutral_dissonance` | `neutral_dissonance_median` | `7.5` | — | python-stdlib 3.14 |
| `O.philosophical.self_ref_phi` | `self_ref_phi_median` | `0.6524345227680417` | — | python-stdlib 3.14 |
| `O.philosophical.neutral_phi` | `neutral_phi_median` | `0.6360755133242495` | — | python-stdlib 3.14 |

## 6. Signature

`cce753aa1754765bc6d93fac6ab40979c1a592d0e5b43354ce83c9a251456f20`
