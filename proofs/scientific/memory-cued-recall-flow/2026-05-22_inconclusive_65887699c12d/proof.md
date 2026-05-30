# Empirical Proof Record — **INCONCLUSIVE**

**Proof ID:** `65887699c12d3ab5fadf05fd094b99ce4868159aeb5e0b7180df4dd10b88b260`  
**Created:** 2026-05-22T16:57:12.463256+00:00

## 1. Claim

> A partial cue of a SEEN experience recalls its full content better than a partial cue of a never-seen item: memory_lift = mean(recall|seen) − mean(recall|never-seen) > 0. Both arms get the same impoverished cue, so this isolates path-dependent memory from deterministic re-derivation.

- **Operationalisation:** Stream 80 seen items; never stream 25 control items. Probe partial cues (first 15% of words) of 25 seen and 25 control items. recall = Jaccard(concepts(partial cue), concepts(full item)). memory_lift = mean(recall seen) − mean(recall control); decided VALIDATED iff lift > 0 with a significant seen>control Mann-Whitney.
- **Threshold:** `memory_lift > 0.0 jaccard`
- **H0:** H0: memory_lift ≤ 0 — a seen partial cue recalls no better than a never-seen one; 'recall' is deterministic re-derivation
- **H1:** H1: memory_lift > 0 — prior exposure completes the partial cue; path-dependent memory beyond re-derivation

## 2. Verdict

**Outcome:** INCONCLUSIVE  
**Observed:** `-0.08073282185995534`

memory_lift -0.0807 = seen recall 0.2698 (n=21) − control recall 0.3505 (n=25); partial cue = first 15% of words; seen>control Mann-Whitney p=0.52 (NOT significant); INCONCLUSIVE — lift not statistically significant

## 3. Pre-registration

- Registered at: `2026-05-22T16:57:12.100044+00:00`
- Config hash: `b93b2d8f275099986fa6eba8d38dee0d5a968cf74b34c3f912557ddcf1208f1f`
- Data hash: `244f8039cec223feccf8dbb9a59c8c7e220a04ef3d77abdc6083f28e5025dbf6`

_Stream 80 seen items (record full concept sets). Probe partial cues (first 15% of words) of 25 seen items (warm) and 25 never-seen control items (cold; full run after the cue to get the target). recall = Jaccard(cue concepts, full concepts). memory_lift = mean(recall seen) − mean(recall control). INCONCLUSIVE if fewer than 5 valid probes per arm or the Mann-Whitney is not significant; else VALIDATED iff lift > 0. The per-arm distributions are descriptive._

## 4. Data

- Substrate: `kimera-swm` @ `eba50120eadd`
- Dataset: `kimera-cued-recall-stream` (substrate-trajectory+partial-cue-recall, 155 records, hash `244f8039cec2…`)

## 5. Evidence

| pillar | statistic | value | 95% CI | library |
|---|---|---|---|---|
| `O.flow.cued_recall` | `memory_lift` | `-0.08073282185995534` | — | ophamin 0.108.0 |

## 6. Signature

`45b1e22adf051db917bb90559c60c05869039c692f0e87a6bc99b7bc627c91f6`
