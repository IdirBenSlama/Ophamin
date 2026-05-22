# Empirical Proof Record — **INCONCLUSIVE**

**Proof ID:** `0e9151f3e42f14cab3a4b353c25a01bbb2967f435690e636023d26f49e7acf6a`  
**Created:** 2026-05-22T16:50:07.145331+00:00

## 1. Claim

> A partial cue of a SEEN experience recalls its full content better than a partial cue of a never-seen item: memory_lift = mean(recall|seen) − mean(recall|never-seen) > 0. Both arms get the same impoverished cue, so this isolates path-dependent memory from deterministic re-derivation.

- **Operationalisation:** Stream 80 seen items; never stream 25 control items. Probe partial cues (first 40% of words) of 25 seen and 25 control items. recall = Jaccard(concepts(partial cue), concepts(full item)). memory_lift = mean(recall seen) − mean(recall control); decided VALIDATED iff lift > 0 with a significant seen>control Mann-Whitney.
- **Threshold:** `memory_lift > 0.0 jaccard`
- **H0:** H0: memory_lift ≤ 0 — a seen partial cue recalls no better than a never-seen one; 'recall' is deterministic re-derivation
- **H1:** H1: memory_lift > 0 — prior exposure completes the partial cue; path-dependent memory beyond re-derivation

## 2. Verdict

**Outcome:** INCONCLUSIVE  
**Observed:** `0.06468032986947281`

memory_lift +0.0647 = seen recall 0.7057 (n=21) − control recall 0.6410 (n=25); partial cue = first 40% of words; seen>control Mann-Whitney p=0.31 (NOT significant); INCONCLUSIVE — lift not statistically significant

## 3. Pre-registration

- Registered at: `2026-05-22T16:50:06.750923+00:00`
- Config hash: `57008019a405d3f104ca26c52165b988e10f99c030dfdfaf0ad09c7de13e1b73`
- Data hash: `831fd7cf7614cc5c9e71016a2fb328adef8ee00e951e29a7a7085f53d40fe693`

_Stream 80 seen items (record full concept sets). Probe partial cues (first 40% of words) of 25 seen items (warm) and 25 never-seen control items (cold; full run after the cue to get the target). recall = Jaccard(cue concepts, full concepts). memory_lift = mean(recall seen) − mean(recall control). INCONCLUSIVE if fewer than 5 valid probes per arm or the Mann-Whitney is not significant; else VALIDATED iff lift > 0. The per-arm distributions are descriptive._

## 4. Data

- Substrate: `kimera-swm` @ `9c66d1449518`
- Dataset: `kimera-cued-recall-stream` (substrate-trajectory+partial-cue-recall, 155 records, hash `831fd7cf7614…`)

## 5. Evidence

| pillar | statistic | value | 95% CI | library |
|---|---|---|---|---|
| `O.flow.cued_recall` | `memory_lift` | `0.06468032986947281` | — | ophamin 0.107.0 |

## 6. Signature

`4cbb7e90878a08dcac1b733b40cba1f6725e1a353e07a2dbb5fbf6c33b143cc8`
