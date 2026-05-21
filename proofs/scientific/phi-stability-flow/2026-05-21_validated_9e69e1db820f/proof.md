# Empirical Proof Record — **VALIDATED**

**Proof ID:** `9e69e1db820fba5d982a240866e547e13b429f7a131ee7748745927124f7e6b8`  
**Created:** 2026-05-21T23:41:38.213392+00:00

## 1. Claim

> Under sustained load, the substrate stays cognitively alive on real input: □ (for every cycle that produced a concept set, Φ ≥ 0.05). Empty-concept cycles are excluded — with nothing to integrate, Φ=0 is correct, not a defect; their rate is reported separately. The floor is the lowest-Φ real-input cycle across the run.

- **Operationalisation:** Stream 3 passes over 8 substantive stimuli through Kimera's entity target (Takwin); read the per-cycle ``phi`` and ``concepts``. Partition cycles into real-input (concepts non-empty) and empty-input. phi_floor = min Φ over real-input cycles; the LTL □ invariant holds iff that floor ≥ φ_floor. empty_input_rate and the over-all-cycles phi_floor_strict are reported alongside.
- **Threshold:** `phi_floor >= 0.05 phi`
- **H0:** H0: min Φ < 0.05 on real-input cycles — Φ collapses below the floor despite the input producing concepts
- **H1:** H1: min Φ ≥ 0.05 on real-input cycles — the substrate stays cognitively alive whenever it has something to integrate

## 2. Verdict

**Outcome:** VALIDATED  
**Observed:** `0.6156636348270582`

Φ floor 0.6157 over 21 real-input cycles (3 passes × 8 stimuli); mean Φ 0.6372, band [0.6157, 0.6561], stdev 0.0123; non-collapse rate 100.0%; 3 empty-input cycles excluded (12.5%; strict floor over all cycles 0.0000); 0 cycles produced no Φ; worst real cycle: stimulus 4 @ cycle 20 = 0.6157

## 3. Pre-registration

- Registered at: `2026-05-21T23:41:37.833041+00:00`
- Config hash: `fc0d6fa2b433540d0fc987795a9290da4c1acaff4c0266fcacf945fe8d7490b4`
- Data hash: `f36c007933b4b5223d517967d58c7b804a0a1417b2305418406bbf29c507cb69`

_Build a sustained-load schedule (3 passes over 8 stimuli = 24 cycles); stream it through Kimera's entity target. Read per-cycle Φ + concepts; partition into real-input vs empty-input cycles. Decide the LTL □ invariant on real-input cycles: min Φ ≥ 0.05. Report empty_input_rate + phi_floor_strict (over all cycles) alongside. INCONCLUSIVE if fewer than 6 real-input cycles. The Φ band, per-pass means, and per-cycle Φ series are descriptive; none post-hoc-claimable._

## 4. Data

- Substrate: `kimera-swm` @ `674ae6b7b402`
- Dataset: `kimera-phi-stability-trajectory` (substrate-trajectory+sustained-load, 24 records, hash `f36c007933b4…`)

## 5. Evidence

| pillar | statistic | value | 95% CI | library |
|---|---|---|---|---|
| `O.flow.phi_stability` | `phi_floor` | `0.6156636348270582` | — | ophamin 0.82.0 |

## 6. Signature

`c7ea620639b46d64637b9e2d9c1aa378957f94acd7f149adcacf08fea3fc71ec`
