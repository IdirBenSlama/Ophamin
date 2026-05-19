# Empirical Proof Record — **REFUTED**

**Proof ID:** `66f3388942474f236c7e6fb4ab5c20e6c71297a4cca26c4841da01b76249cfde`  
**Created:** 2026-05-17T18:32:26.642916+00:00

## 1. Claim

> Kimera's three WIRE_CANDIDATE self-discovery primitives (system_laws_discovery, pressure_state, semantic_physics_validator) collectively surface the architectural physics that Sinew found by external measurement, validating ≥ 2 of 3 pre-registered sub-tests. SUB-A: system_laws_discovery surfaces a non-trivial CW vs (P+T) relationship (r² > 0.3). SUB-B: pressure_state classifies ≥ 80% of Sinew events. SUB-C: semantic_physics_validator surfaces a triad containing ≥ 2 of [pressure, tension, scar].

- **Operationalisation:** Read per-phase reports from experiments/observatory/runs/proprio_phase_*/. SUB-A: take Phase 2 headline r² for CW_seed vs P+T on SEC v2 corpus. SUB-B: take Phase 3 classified-event-count / total-event-count ratio. SUB-C: take Phase 4 sinew_verdict (STRONG/WEAK/TRACE/WEAK_VOCAB/FAIL). Headline metric = count of sub-tests with verdict in {STRONG_PASS, WEAK_PASS}.
- **Threshold:** `sub_tests_passed >= 2.0 of_3`
- **H0:** sub_tests_passed < 2 — Kimera's self-discovery primitives don't actually discover substrate physics; Pattern-P at primitive-name level
- **H1:** sub_tests_passed >= 2 — substrate has measurable self-discovery capability; the wiring debt does contain working physics-discovery primitives

## 2. Verdict

**Outcome:** REFUTED  
**Observed:** `1.0`

Proprio synthesis: SUB-A (system_laws_discovery vs P+T) = FAIL; SUB-B (pressure_state typing coverage) = STRONG_PASS; SUB-C (semantic_physics_validator triad) = FAIL. 1/3 sub-tests passed.

## 3. Pre-registration

- Registered at: `2026-05-17T18:32:26.448183+00:00`
- Config hash: `448da14b61933d956db50ae840ebbff7248b7dbfded1a4ab33244c0398503819`
- Data hash: `54591a60c2ee7f903b4e1a763c8ade45443db587824d2058b712ffae28a49005`

_Read three pre-computed Phase 2/3/4 reports from the Proprio campaign. SUB-A: classify Phase 2's CW vs P+T discovery r². SUB-B: classify Phase 3's typed-event coverage ratio. SUB-C: classify Phase 4's Sinew-triad recovery. Count sub-tests reaching STRONG_PASS or WEAK_PASS verdicts. Verdict on count >= 2._

## 4. Data

- Substrate: `kimera-swm` @ ``
- Dataset: `kimera-proprio-trajectory` (proprio-phase-reports, 3 records, hash `54591a60c2ee…`)

## 5. Evidence

| pillar | statistic | value | 95% CI | library |
|---|---|---|---|---|
| `proprio_self_discovery` | `sub_tests_passed` | `1.0` | — | ophamin.measuring.scenarios.proprio_self_discovery 0.9.3 |

## 6. Signature

`42b8aeb946dec0f874da1d5e9fc33b4d1ef4ac0a6ad0a3ac03c04faadc972327`
