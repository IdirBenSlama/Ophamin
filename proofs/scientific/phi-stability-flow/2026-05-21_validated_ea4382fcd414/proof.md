# Empirical Proof Record — **VALIDATED**

**Proof ID:** `ea4382fcd414cefff5889044b139d94d1ca6a4022bdb7dad8ed661e6fea4d9f1`  
**Created:** 2026-05-21T23:03:10.308076+00:00

## 1. Claim

> Under sustained load, the substrate stays cognitively alive: □ (for every cycle in the trajectory, Φ ≥ 0.05). The reported floor is the lowest-Φ cycle across the whole run.

- **Operationalisation:** Stream 3 passes over 8 substantive stimuli through Kimera's entity target (Takwin); read the per-cycle ``phi``. phi_floor_observed = min Φ over all cycles; the LTL □ invariant holds iff min Φ ≥ φ_floor.
- **Threshold:** `phi_floor >= 0.05 phi`
- **H0:** H0: min Φ < 0.05 — Φ collapses below the non-collapse floor somewhere in the run
- **H1:** H1: min Φ ≥ 0.05 — Φ stays above the collapse floor across the whole trajectory (substrate stays cognitively alive under sustained load)

## 2. Verdict

**Outcome:** VALIDATED  
**Observed:** `0.6155826812407138`

Φ floor 0.6156 over 24 cycles (3 passes × 8 stimuli); mean Φ 0.6563, band [0.6156, 0.7041], stdev 0.0326; non-collapse rate 100.0%; 0 cycles produced no Φ; worst cycle: stimulus 5 @ cycle 21 = 0.6156

## 3. Pre-registration

- Registered at: `2026-05-21T23:03:09.942439+00:00`
- Config hash: `fc0d6fa2b433540d0fc987795a9290da4c1acaff4c0266fcacf945fe8d7490b4`
- Data hash: `0289f594eb2ea25b582960992cf2db41bf790750618ae39f5dadc693ee1fb06b`

_Build a sustained-load schedule (3 passes over 8 stimuli = 24 cycles); stream it through Kimera's entity target. Read per-cycle Φ. Decide the LTL □ invariant: min Φ ≥ 0.05. INCONCLUSIVE if fewer than 6 cycles produced a Φ. The Φ band, per-pass means, and per-cycle Φ series are descriptive; none post-hoc-claimable._

## 4. Data

- Substrate: `kimera-swm` @ `674ae6b7b402`
- Dataset: `kimera-phi-stability-trajectory` (substrate-trajectory+sustained-load, 24 records, hash `0289f594eb2e…`)

## 5. Evidence

| pillar | statistic | value | 95% CI | library |
|---|---|---|---|---|
| `O.flow.phi_stability` | `phi_floor` | `0.6155826812407138` | — | ophamin 0.79.0 |

## 6. Signature

`7b3ca6d9a0ddeeb9a9adcc638d90e2204fbcc2d5c6666e7faa02abf8742f5a82`
