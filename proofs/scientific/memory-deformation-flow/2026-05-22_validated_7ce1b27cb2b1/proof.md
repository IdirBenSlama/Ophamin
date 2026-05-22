# Empirical Proof Record — **VALIDATED**

**Proof ID:** `7ce1b27cb2b11e240c9bbd02cfb02f8e12e6f5dc3fa4ad6100d5696185bccb99`  
**Created:** 2026-05-22T14:07:58.612245+00:00

## 1. Claim

> Across a trajectory with spaced re-exposures, the substrate keeps recognising every re-exposed stimulus: □ (for every same-stimulus re-exposure pair (i, j) in the trajectory, Jaccard(concepts_i, concepts_j) ≥ 0.80). The reported floor is the worst pair across the whole run.

- **Operationalisation:** Run a schedule of len(stimuli) unique stimuli each repeated 3× and interleaved (gap = len(stimuli)) through Kimera's entity target (Takwin). For each stimulus, take the per-cycle ``concepts`` set at each exposure and compute Jaccard over all exposure pairs. recognition_jaccard_floor = min over all pairs across all stimuli; the LTL □ invariant holds iff floor ≥ θ.
- **Threshold:** `recognition_jaccard_floor >= 0.8 jaccard`
- **H0:** H0: floor < 0.80 — recognition collapses under manifold deformation somewhere in the run
- **H1:** H1: floor ≥ 0.80 — recognition is stable across the whole trajectory (memory-as-deformation holds as a flow property)

## 2. Verdict

**Outcome:** VALIDATED  
**Observed:** `0.8636363636363636`

recognition floor 0.8636 over 252 re-exposure pairs (100 stimuli × 3 exposures); mean Jaccard 0.9936; 43 exposures produced no concept set; worst pair: stimulus 3 cycles 3↔103 = 0.8636; control: same-stimulus median 1.000 vs cross-stimulus median 0.000, Mann-Whitney p=1.5e-196 (recognition IS significantly above the cross-stimulus baseline)

## 3. Pre-registration

- Registered at: `2026-05-22T14:07:58.381470+00:00`
- Config hash: `f6bc53805d417e3efed14f11a888eb547e38f41519f509a6173cc6473fe24c90`
- Data hash: `0337ab84541480cc72d72c54d196983b6553e78d039d8cd1d6425d57474123da`

_Build an interleaved re-exposure schedule (100 stimuli × 3 exposures, gap = 100); stream it through Kimera's entity target. Per stimulus, compute Jaccard of the per-cycle concept set across all exposure pairs. Decide the LTL □ invariant: floor (min Jaccard over all pairs) ≥ 0.80. INCONCLUSIVE if fewer than 6 valid pairs were measured. Per-pair series + per-stimulus floors are the action evidence; none post-hoc-claimable._

## 4. Data

- Substrate: `kimera-swm` @ `c571612fabcb`
- Dataset: `kimera-memory-deformation-trajectory` (substrate-trajectory+reexposure, 300 records, hash `0337ab845414…`)

## 5. Evidence

| pillar | statistic | value | 95% CI | library |
|---|---|---|---|---|
| `O.flow.recognition_stability` | `recognition_jaccard_floor` | `0.8636363636363636` | — | ophamin 0.99.0 |

## 6. Signature

`395baea0c4b982d438d5340d96670d88a7cbd4fa0468372fbbdb24ae64b54c92`
