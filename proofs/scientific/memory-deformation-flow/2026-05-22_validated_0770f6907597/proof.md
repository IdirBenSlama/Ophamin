# Empirical Proof Record — **VALIDATED**

**Proof ID:** `0770f69075972a861207c24d54fe73b7d46661af06f25fa5cc9b181e401b719f`  
**Created:** 2026-05-22T10:56:37.696051+00:00

## 1. Claim

> Across a trajectory with spaced re-exposures, the substrate keeps recognising every re-exposed stimulus: □ (for every same-stimulus re-exposure pair (i, j) in the trajectory, Jaccard(concepts_i, concepts_j) ≥ 0.80). The reported floor is the worst pair across the whole run.

- **Operationalisation:** Run a schedule of len(stimuli) unique stimuli each repeated 3× and interleaved (gap = len(stimuli)) through Kimera's entity target (Takwin). For each stimulus, take the per-cycle ``concepts`` set at each exposure and compute Jaccard over all exposure pairs. recognition_jaccard_floor = min over all pairs across all stimuli; the LTL □ invariant holds iff floor ≥ θ.
- **Threshold:** `recognition_jaccard_floor >= 0.8 jaccard`
- **H0:** H0: floor < 0.80 — recognition collapses under manifold deformation somewhere in the run
- **H1:** H1: floor ≥ 0.80 — recognition is stable across the whole trajectory (memory-as-deformation holds as a flow property)

## 2. Verdict

**Outcome:** VALIDATED  
**Observed:** `0.8636363636363636`

recognition floor 0.8636 over 24 re-exposure pairs (8 stimuli × 3 exposures); mean Jaccard 0.9629; 0 exposures produced no concept set; worst pair: stimulus 3 cycles 3↔11 = 0.8636

## 3. Pre-registration

- Registered at: `2026-05-22T10:56:37.331092+00:00`
- Config hash: `0fbe8ce56b2a2db7203910b72aaebc0c6677a1340f6ddf2f6131319b11f8cfd2`
- Data hash: `0289f594eb2ea25b582960992cf2db41bf790750618ae39f5dadc693ee1fb06b`

_Build an interleaved re-exposure schedule (8 stimuli × 3 exposures, gap = 8); stream it through Kimera's entity target. Per stimulus, compute Jaccard of the per-cycle concept set across all exposure pairs. Decide the LTL □ invariant: floor (min Jaccard over all pairs) ≥ 0.80. INCONCLUSIVE if fewer than 6 valid pairs were measured. Per-pair series + per-stimulus floors are the action evidence; none post-hoc-claimable._

## 4. Data

- Substrate: `kimera-swm` @ `674ae6b7b402`
- Dataset: `kimera-memory-deformation-trajectory` (substrate-trajectory+reexposure, 24 records, hash `0289f594eb2e…`)

## 5. Evidence

| pillar | statistic | value | 95% CI | library |
|---|---|---|---|---|
| `O.flow.recognition_stability` | `recognition_jaccard_floor` | `0.8636363636363636` | — | ophamin 0.87.0 |

## 6. Signature

`9eb52e1f68c43c4198313462893e7e318943b1151972f4ac961f6305f96fab93`
