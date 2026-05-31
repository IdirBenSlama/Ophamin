# Empirical Proof Record — **VALIDATED**

**Proof ID:** `84d8258707cdb8d5b5f1de2b6a807073b885a488669b1aaac4a35b2fcb96cfc5`  
**Created:** 2026-05-31T18:47:18.937451+00:00

## 1. Claim

> Across a trajectory of spaced re-exposures, the manifold's cumulative scar deformation never decreases: □ (for every consecutive cycle pair (i, i+1), total_deformation_{i+1} >= total_deformation_i). The reported metric is the fraction of consecutive pairs that hold; the invariant requires 1.00.

- **Operationalisation:** Run a schedule of len(stimuli) unique stimuli each repeated 2x and interleaved (gap = len(stimuli)) through Kimera's entity target (Takwin). Read the live manifold deformation per cycle via observables.manifold_deformation (raw['scar_state'].total_deformation). monotonic_nondecrease_fraction = (# consecutive pairs with total_deformation non-decreasing) / (# pairs); the invariant holds iff fraction >= theta.
- **Threshold:** `monotonic_nondecrease_fraction >= 1.0 fraction`
- **H0:** H0: fraction < 1.00 — cumulative deformation decreased somewhere (a scar was lost / a reset occurred), violating permanence
- **H1:** H1: fraction >= 1.00 — deformation is monotonically non-decreasing across the whole trajectory (scars accumulate, never reset)

## 2. Verdict

**Outcome:** VALIDATED  
**Observed:** `1.0`

monotonic non-decrease fraction 1.0000 over 15 consecutive cycle pairs (8 stimuli x 2 exposures); 0 cycles emitted no deformation value (recorded gaps); n_scars 1 -> 15; cross-check: 8/8 stimuli sit on a more-deformed manifold at last exposure than first (same-stimulus accumulation passed)

## 3. Pre-registration

- Registered at: `2026-05-31T18:47:18.574359+00:00`
- Config hash: `cbdb723ea6b1c111ba583c92bd3ba4b1dcd9ce6c1f56a9e3e3ca6bb556c60391`
- Data hash: `221a8a035c85eee67ce8bccf6670a709747efc6253d96a5b9e81ed1b493edc57`

_Build an interleaved re-exposure schedule (8 stimuli x 2 exposures, gap = 8); stream it through Kimera's entity target. Per cycle, read live total_deformation + n_scars via observables.manifold_deformation. Decide the LTL invariant: fraction of consecutive pairs with non-decreasing total_deformation >= 1.00 (eps=1e-09). INCONCLUSIVE if fewer than 6 pairs emitted a deformation value. Cross-check (independent): each stimulus's last-exposure deformation must exceed its first-exposure deformation (same-stimulus accumulation). The per-cycle series, the first violation, and the per-stimulus deltas are the action evidence; none post-hoc-claimable._

## 4. Data

- Substrate: `kimera-swm` @ `1b510a85de5c`
- Dataset: `kimera-scar-accumulation-trajectory` (substrate-trajectory+reexposure, 16 records, hash `221a8a035c85…`)

## 5. Evidence

| pillar | statistic | value | 95% CI | library |
|---|---|---|---|---|
| `O.flow.scar_accumulation` | `monotonic_nondecrease_fraction` | `1.0` | — | ophamin 0.115.2 |

## 6. Signature

`132c59395741071a3d9e110bc1cb3e03154be95fbc2a72fcb7a72218b5587db6`
