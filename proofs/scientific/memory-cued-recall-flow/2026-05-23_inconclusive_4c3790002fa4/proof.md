# Empirical Proof Record — **INCONCLUSIVE**

**Proof ID:** `4c3790002fa45821c42b2b6fa065f424357a2e481e347f7e4822637def8bc9a3`  
**Created:** 2026-05-23T23:10:38.020333+00:00

## 1. Claim

> A partial cue of a SEEN experience recalls its full content better than a partial cue of a never-seen item: memory_lift = mean(recall|seen) − mean(recall|never-seen) > 0. Both arms get the same impoverished cue, so this isolates path-dependent memory from deterministic re-derivation.

- **Operationalisation:** Stream 6 seen items; never stream 2 control items. Probe partial cues (first 40% of words) of 6 seen and 2 control items. recall = Jaccard(concepts(partial cue), concepts(full item)). memory_lift = mean(recall seen) − mean(recall control); decided VALIDATED iff lift > 0 with a significant seen>control Mann-Whitney.
- **Threshold:** `memory_lift > 0.0 jaccard`
- **H0:** H0: memory_lift ≤ 0 — a seen partial cue recalls no better than a never-seen one; 'recall' is deterministic re-derivation
- **H1:** H1: memory_lift > 0 — prior exposure completes the partial cue; path-dependent memory beyond re-derivation

## 2. Verdict

**Outcome:** INCONCLUSIVE  
**Observed:** `-0.12069518315648342`

memory_lift -0.1207 = seen recall 0.2578 (n=6) − control recall 0.3785 (n=2); partial cue = first 40% of words; INCONCLUSIVE — too few valid probes per arm

## 3. Pre-registration

- Registered at: `2026-05-23T23:10:37.768681+00:00`
- Config hash: `85ce90b9a2071df259409d64f66955d171cf4d64fdde6bdef0b3a445ea42c85c`
- Data hash: `004b9e2af6b1b66bdf42363d0c9045443098e2f245befaf4c7d66f983dfe6526`

_Stream 6 seen items (record full concept sets). Probe partial cues (first 40% of words) of 6 seen items (warm) and 2 never-seen control items (cold; full run after the cue to get the target). recall = Jaccard(cue concepts, full concepts). memory_lift = mean(recall seen) − mean(recall control). INCONCLUSIVE if fewer than 5 valid probes per arm or the Mann-Whitney is not significant; else VALIDATED iff lift > 0. The per-arm distributions are descriptive._

## 4. Data

- Substrate: `kimera-swm` @ `78cb9f9fc6a8`
- Dataset: `kimera-cued-recall-stream` (substrate-trajectory+partial-cue-recall, 16 records, hash `004b9e2af6b1…`)

## 5. Evidence

| pillar | statistic | value | 95% CI | library |
|---|---|---|---|---|
| `O.flow.cued_recall` | `memory_lift` | `-0.12069518315648342` | — | ophamin 0.115.2 |

## 6. Signature

`c465d04f9f5f0db65b44884e9b0026741707394d6ec67b9ed9e7f7ca20ed6bf7`
