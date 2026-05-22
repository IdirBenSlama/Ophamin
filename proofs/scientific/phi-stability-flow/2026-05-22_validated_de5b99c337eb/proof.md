# Empirical Proof Record — **VALIDATED**

**Proof ID:** `de5b99c337eb26caa8acde0e02aedc9ca1f110f41eb19b0269a0d6298c67f348`  
**Created:** 2026-05-22T13:14:11.981467+00:00

## 1. Claim

> Under sustained load, the substrate stays cognitively alive on real input: □ (for every cycle that produced a concept set, Φ ≥ 0.05). Empty-concept cycles are excluded — with nothing to integrate, Φ=0 is correct, not a defect; their rate is reported separately. The floor is the lowest-Φ real-input cycle across the run.

- **Operationalisation:** Stream 5 passes over 8 substantive stimuli through Kimera's entity target (Takwin); read the per-cycle ``phi`` and ``concepts``. Partition cycles into real-input (concepts non-empty) and empty-input. phi_floor = min Φ over real-input cycles; the LTL □ invariant holds iff that floor ≥ φ_floor. empty_input_rate and the over-all-cycles phi_floor_strict are reported alongside.
- **Threshold:** `phi_floor >= 0.05 phi`
- **H0:** H0: min Φ < 0.05 on real-input cycles — Φ collapses below the floor despite the input producing concepts
- **H1:** H1: min Φ ≥ 0.05 on real-input cycles — the substrate stays cognitively alive whenever it has something to integrate

## 2. Verdict

**Outcome:** VALIDATED  
**Observed:** `0.6603084741552229`

Φ floor 0.6603 over 40 real-input cycles (5 passes × 8 stimuli); mean Φ 0.6892, band [0.6603, 0.7023], stdev 0.0141; non-collapse rate 100.0%; 0 empty-input cycles excluded (0.0%; strict floor over all cycles 0.6603); 0 cycles produced no Φ; worst real cycle: stimulus 1 @ cycle 1 = 0.6603; cross-check passed: non-collapse Wilson 95% CI [0.912, 1.000] (confidently alive)

## 3. Pre-registration

- Registered at: `2026-05-22T13:14:11.738173+00:00`
- Config hash: `d9e9ad915c6867382837179e54fdf8701a2341b6a104546693dd4c7a5d50bf0c`
- Data hash: `fc88457a1778b2a25ed9f7930f7315a071fa748b1bfc67d521b595dbb6719c9a`

_Build a sustained-load schedule (5 passes over 8 stimuli = 40 cycles); stream it through Kimera's entity target. Read per-cycle Φ + concepts; partition into real-input vs empty-input cycles. Decide the LTL □ invariant on real-input cycles: min Φ ≥ 0.05. Report empty_input_rate + phi_floor_strict (over all cycles) alongside. INCONCLUSIVE if fewer than 6 real-input cycles. The Φ band, per-pass means, and per-cycle Φ series are descriptive; none post-hoc-claimable._

## 4. Data

- Substrate: `kimera-swm` @ `4598000dda08`
- Dataset: `kimera-phi-stability-trajectory` (substrate-trajectory+sustained-load, 40 records, hash `fc88457a1778…`)

## 5. Evidence

| pillar | statistic | value | 95% CI | library |
|---|---|---|---|---|
| `O.flow.phi_stability` | `phi_floor` | `0.6603084741552229` | — | ophamin 0.97.0 |

## 6. Signature

`6a7f415740c42624be15d058ee781d84cafcd7d03f96e3ca8d0173be1c0347c0`
