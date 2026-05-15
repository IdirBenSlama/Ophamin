# Ophamin Empirical Proof Record — `REFUTED`

**Proof ID:** `95588bfe0b136bd7e8d111a2bc4a44a811796d72e60a719c9b7b556d76988de0`
**Schema:** v1.0  
**Created:** 2026-05-15T15:01:46.423245+00:00

## 1. Identity
- Ophamin: `0.1.0` @ `f517ec81fe79bfc02abead297de11179091640e2`
- Substrate: **kimera-swm** @ `179edd233c157441c8b052bbea45e19fcc666561`

## 2. Claim
> When fed text describing Kimera's own primitives, the substrate's dissonance signal (dissonance_events_count) is measurably higher than on neutral text — Cohen's d effect size >= 0.30 (one-sided, self-referential > neutral). A REFUTED verdict means the substrate does not differentially process content about itself.

- **Operationalization:** Cohen's d effect size on per-cycle dissonance_events_count between the self-referential group and the neutral group (pooled-variance form, one-sided)
- **Threshold:** `dissonance_cohens_d_self_ref_vs_neutral >= 0.3 cohens_d`
- **H0:** Cohen's d < 0.30 (substrate does not differentiate self-referential content)
- **H1:** Cohen's d >= 0.30 (substrate differentially processes content about itself)

## 3. Pre-registration
- Registered at: `2026-05-15T15:00:44.121975+00:00` (must precede §1 created)
- Config hash: `bf33182ff4be1531ad64054bd6a66d91c1c9c2b40d7891957bb174bde8a4fc6a`
- Data hash: `b3da1b3fe0369ec3140bb4fbce94702c33b7da810ec15d718b3fadf5cd748ca7`
- Analysis plan: Stream 30 self-referential sentences (about Kimera's own primitives, hand-curated from CLAUDE.md) + 30 neutral sentences (Enron emails, body in [60, 300] chars) through Kimera's entity target, tagged by group. Compute Cohen's d effect size on dissonance_events_count between groups (one-sided, self_ref > neutral). Mann-Whitney U + p-value reported as secondary descriptive evidence. Pre-registered threshold: Cohen's d >= 0.30 (one-sided).

## 4. Data
- **enron-email-corpus** (email_corpus) — 517,401 records — `b3da1b3fe0369ec3…` — https://www.cs.cmu.edu/~enron/enron_mail_20150507.tar.gz

## 5. Evidence
| Pillar | Statistic | Value | Effect | 95% CI | p | Library | Cross-check |
|---|---|---|---|---|---|---|---|
| O.philosophical.cohens_d | dissonance_cohens_d_self_ref_vs_neutral | -0.358578 | -0.3586 | — | — | python-stdlib 3.14 | n/a |
| O.philosophical.mannwhitneyu | dissonance_mannwhitneyu_p_value | 0.970533 | — | — | 0.9705 | scipy scipy.stats | n/a |
| O.philosophical.self_ref_dissonance | self_ref_dissonance_median | 17 | — | — | — | python-stdlib 3.14 | n/a |
| O.philosophical.neutral_dissonance | neutral_dissonance_median | 20 | — | — | — | python-stdlib 3.14 | n/a |
| O.philosophical.self_ref_phi | self_ref_phi_median | 0.240452 | — | — | — | python-stdlib 3.14 | n/a |
| O.philosophical.neutral_phi | neutral_phi_median | 0.223096 | — | — | — | python-stdlib 3.14 | n/a |

## 6. Verdict
### **REFUTED**

- Observed: `-0.358578`
- Threshold: `dissonance_cohens_d_self_ref_vs_neutral >= 0.3 cohens_d`
- Reasoning: Cohen's d (self_ref - neutral)/pooled_sd = -0.359; self_ref dissonance: n=30 median=17.0 mean=17.37 (range 0-29); neutral dissonance: n=30 median=20.0 mean=20.73 (range 0-45); Mann-Whitney U=323.0, one-sided p=0.9705; 60 cycles, 0 adapter errors

## 7. Reproduction
```
PYTHONPATH=src .venv/bin/python -m ophamin.cli scenario philosophical-self-reference
```
- Environment lock: 178 entries

## 8. Provenance
- W3C PROV-O graph: 2 entities, 1 activities, 2 agents

## 9. Signature
- `00b7441f65dbccf26055347e0e2ac5ab998957262a1a4730493de42442249931`

---
**✓ Record is well-formed** — falsifiable, pre-registered, traceable, reproducible, attributed.
