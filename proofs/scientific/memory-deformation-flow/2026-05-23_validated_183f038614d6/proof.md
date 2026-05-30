# Empirical Proof Record — **VALIDATED**

**Proof ID:** `183f038614d6a6288a95be163df4a55a558250cf528040bc80b91d337048ff5c`  
**Created:** 2026-05-23T23:10:48.999916+00:00

## 1. Claim

> Across a trajectory with spaced re-exposures, the substrate keeps recognising every re-exposed stimulus: □ (for every same-stimulus re-exposure pair (i, j) in the trajectory, Jaccard(concepts_i, concepts_j) ≥ 0.80). The reported floor is the worst pair across the whole run.

- **Operationalisation:** Run a schedule of len(stimuli) unique stimuli each repeated 3× and interleaved (gap = len(stimuli)) through Kimera's entity target (Takwin). For each stimulus, take the per-cycle ``concepts`` set at each exposure and compute Jaccard over all exposure pairs. recognition_jaccard_floor = min over all pairs across all stimuli; the LTL □ invariant holds iff floor ≥ θ.
- **Threshold:** `recognition_jaccard_floor >= 0.8 jaccard`
- **H0:** H0: floor < 0.80 — recognition collapses under manifold deformation somewhere in the run
- **H1:** H1: floor ≥ 0.80 — recognition is stable across the whole trajectory (memory-as-deformation holds as a flow property)

## 2. Verdict

**Outcome:** VALIDATED  
**Observed:** `0.95`

recognition floor 0.9500 over 24 re-exposure pairs (8 stimuli × 3 exposures); mean Jaccard 0.9958; 0 exposures produced no concept set; worst pair: stimulus 2 cycles 2↔10 = 0.9500; control: same-stimulus median 1.000 vs cross-stimulus median 0.026, Mann-Whitney p=1.7e-17 (recognition IS significantly above the cross-stimulus baseline)

## 3. Pre-registration

- Registered at: `2026-05-23T23:10:48.762737+00:00`
- Config hash: `0fbe8ce56b2a2db7203910b72aaebc0c6677a1340f6ddf2f6131319b11f8cfd2`
- Data hash: `4e6090352a40ea27df1cf08fb4d02bd55c48c75253ece6e66e46809e7c3bc4a8`

_Build an interleaved re-exposure schedule (8 stimuli × 3 exposures, gap = 8); stream it through Kimera's entity target. Per stimulus, compute Jaccard of the per-cycle concept set across all exposure pairs. Decide the LTL □ invariant: floor (min Jaccard over all pairs) ≥ 0.80. INCONCLUSIVE if fewer than 6 valid pairs were measured. Per-pair series + per-stimulus floors are the action evidence; none post-hoc-claimable._

## 4. Data

- Substrate: `kimera-swm` @ `78cb9f9fc6a8`
- Dataset: `kimera-memory-deformation-trajectory` (substrate-trajectory+reexposure, 24 records, hash `4e6090352a40…`)

## 5. Evidence

| pillar | statistic | value | 95% CI | library |
|---|---|---|---|---|
| `O.flow.recognition_stability` | `recognition_jaccard_floor` | `0.95` | — | ophamin 0.115.2 |

## 6. Signature

`985f6a3af07e8039602a6e9ffebc654fabaff79c326d9ea18478fd009256fc29`
