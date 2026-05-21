# Empirical Proof Record — **VALIDATED**

**Proof ID:** `e8e96b1fed7ffbb72c3c33492b24327c85e87a4e79feed356c7b14df39d74d30`  
**Created:** 2026-05-21T23:30:26.573610+00:00

## 1. Claim

> Under sustained load, the substrate stays cognitively alive: □ (for every cycle in the trajectory, Φ ≥ 0.05). The reported floor is the lowest-Φ cycle across the whole run.

- **Operationalisation:** Stream 3 passes over 8 substantive stimuli through Kimera's entity target (Takwin); read the per-cycle ``phi``. phi_floor_observed = min Φ over all cycles; the LTL □ invariant holds iff min Φ ≥ φ_floor.
- **Threshold:** `phi_floor >= 0.05 phi`
- **H0:** H0: min Φ < 0.05 — Φ collapses below the non-collapse floor somewhere in the run
- **H1:** H1: min Φ ≥ 0.05 — Φ stays above the collapse floor across the whole trajectory (substrate stays cognitively alive under sustained load)

## 2. Verdict

**Outcome:** VALIDATED  
**Observed:** `0.5997059933291004`

Φ floor 0.5997 over 24 cycles (3 passes × 8 stimuli); mean Φ 0.6496, band [0.5997, 0.7148], stdev 0.0348; non-collapse rate 100.0%; 0 cycles produced no Φ; worst cycle: stimulus 5 @ cycle 13 = 0.5997

## 3. Pre-registration

- Registered at: `2026-05-21T23:30:26.204684+00:00`
- Config hash: `fc0d6fa2b433540d0fc987795a9290da4c1acaff4c0266fcacf945fe8d7490b4`
- Data hash: `f40e027c9d1b04da2ab75d1781c5c3f517b8b7aca4cd245479f64354d552f2de`

_Build a sustained-load schedule (3 passes over 8 stimuli = 24 cycles); stream it through Kimera's entity target. Read per-cycle Φ. Decide the LTL □ invariant: min Φ ≥ 0.05. INCONCLUSIVE if fewer than 6 cycles produced a Φ. The Φ band, per-pass means, and per-cycle Φ series are descriptive; none post-hoc-claimable._

## 4. Data

- Substrate: `kimera-swm` @ `674ae6b7b402`
- Dataset: `kimera-phi-stability-trajectory` (substrate-trajectory+sustained-load, 24 records, hash `f40e027c9d1b…`)

## 5. Evidence

| pillar | statistic | value | 95% CI | library |
|---|---|---|---|---|
| `O.flow.phi_stability` | `phi_floor` | `0.5997059933291004` | — | ophamin 0.81.0 |

## 6. Signature

`1ec2928741ef5abd0fdd7baf791d57bd1c63414a53c7fed1a29b4f2d36010b71`
