# Empirical Proof Record — **VALIDATED**

**Proof ID:** `672c567ecad7538397dbf697a0b8a7cb69d1dd9ff2ad7e6c279902820e9e2d52`  
**Created:** 2026-05-21T23:32:08.453426+00:00

## 1. Claim

> Under sustained load, the substrate stays cognitively alive: □ (for every cycle in the trajectory, Φ ≥ 0.05). The reported floor is the lowest-Φ cycle across the whole run.

- **Operationalisation:** Stream 3 passes over 8 substantive stimuli through Kimera's entity target (Takwin); read the per-cycle ``phi``. phi_floor_observed = min Φ over all cycles; the LTL □ invariant holds iff min Φ ≥ φ_floor.
- **Threshold:** `phi_floor >= 0.05 phi`
- **H0:** H0: min Φ < 0.05 — Φ collapses below the non-collapse floor somewhere in the run
- **H1:** H1: min Φ ≥ 0.05 — Φ stays above the collapse floor across the whole trajectory (substrate stays cognitively alive under sustained load)

## 2. Verdict

**Outcome:** VALIDATED  
**Observed:** `0.6132373986483411`

Φ floor 0.6132 over 24 cycles (3 passes × 8 stimuli); mean Φ 0.6609, band [0.6132, 0.7099], stdev 0.0307; non-collapse rate 100.0%; 0 cycles produced no Φ; worst cycle: stimulus 6 @ cycle 6 = 0.6132

## 3. Pre-registration

- Registered at: `2026-05-21T23:32:08.026939+00:00`
- Config hash: `fc0d6fa2b433540d0fc987795a9290da4c1acaff4c0266fcacf945fe8d7490b4`
- Data hash: `45e1fddd1cfe8d50b4a966ac821126b862c2c1aa4864db75099d9e26b29fd65b`

_Build a sustained-load schedule (3 passes over 8 stimuli = 24 cycles); stream it through Kimera's entity target. Read per-cycle Φ. Decide the LTL □ invariant: min Φ ≥ 0.05. INCONCLUSIVE if fewer than 6 cycles produced a Φ. The Φ band, per-pass means, and per-cycle Φ series are descriptive; none post-hoc-claimable._

## 4. Data

- Substrate: `kimera-swm` @ `674ae6b7b402`
- Dataset: `kimera-phi-stability-trajectory` (substrate-trajectory+sustained-load, 24 records, hash `45e1fddd1cfe…`)

## 5. Evidence

| pillar | statistic | value | 95% CI | library |
|---|---|---|---|---|
| `O.flow.phi_stability` | `phi_floor` | `0.6132373986483411` | — | ophamin 0.81.0 |

## 6. Signature

`b25d9eb10c8a14d2359bb261d34e46a8f767ac8a14a12a44100f6dd748d34cc4`
