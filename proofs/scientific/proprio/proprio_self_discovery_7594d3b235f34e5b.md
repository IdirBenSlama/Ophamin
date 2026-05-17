# Ophamin Empirical Proof Record — `REFUTED`

**Proof ID:** `7594d3b235f34e5b744d6782eb7e2ddf95e225e59489876bc7a07f6295b8cc68`
**Schema:** v1.0  
**Created:** 2026-05-17T18:08:01.095628+00:00

## 1. Identity
- Ophamin: `0.9.2` @ `92dc71837ccb28b58d883657a57ebb686baee8bf`
- Substrate: **kimera-swm** @ `(no commit)`

## 2. Claim
> Kimera's three WIRE_CANDIDATE self-discovery primitives (system_laws_discovery, pressure_state, semantic_physics_validator) collectively surface the architectural physics that Sinew found by external measurement, validating ≥ 2 of 3 pre-registered sub-tests. SUB-A: system_laws_discovery surfaces a non-trivial CW vs (P+T) relationship (r² > 0.3). SUB-B: pressure_state classifies ≥ 80% of Sinew events. SUB-C: semantic_physics_validator surfaces a triad containing ≥ 2 of [pressure, tension, scar].

- **Operationalization:** Read per-phase reports from experiments/observatory/runs/proprio_phase_*/. SUB-A: take Phase 2 headline r² for CW_seed vs P+T on SEC v2 corpus. SUB-B: take Phase 3 classified-event-count / total-event-count ratio. SUB-C: take Phase 4 sinew_verdict (STRONG/WEAK/TRACE/WEAK_VOCAB/FAIL). Headline metric = count of sub-tests with verdict in {STRONG_PASS, WEAK_PASS}.
- **Threshold:** `sub_tests_passed >= 2.0 of_3`
- **H0:** sub_tests_passed < 2 — Kimera's self-discovery primitives don't actually discover substrate physics; Pattern-P at primitive-name level
- **H1:** sub_tests_passed >= 2 — substrate has measurable self-discovery capability; the wiring debt does contain working physics-discovery primitives

## 3. Pre-registration
- Registered at: `2026-05-17T18:08:00.899919+00:00` (must precede §1 created)
- Config hash: `448da14b61933d956db50ae840ebbff7248b7dbfded1a4ab33244c0398503819`
- Data hash: `9ca122d80906d73bf377121bf49dceab177c09db1a99519600c5334052ec4121`
- Analysis plan: Read three pre-computed Phase 2/3/4 reports from the Proprio campaign. SUB-A: classify Phase 2's CW vs P+T discovery r². SUB-B: classify Phase 3's typed-event coverage ratio. SUB-C: classify Phase 4's Sinew-triad recovery. Count sub-tests reaching STRONG_PASS or WEAK_PASS verdicts. Verdict on count >= 2.

## 4. Data
- **kimera-proprio-trajectory** (proprio-phase-reports) — 3 records — `9ca122d80906d73b…` — phase_reports

## 5. Evidence
| Pillar | Statistic | Value | Effect | 95% CI | p | Library | Cross-check |
|---|---|---|---|---|---|---|---|
| proprio_self_discovery | sub_tests_passed | 1 | — | — | — | ophamin.measuring.scenarios.proprio_self_discovery 0.9.2 | Three sub-tests probe complementary self-discovery primitives. STRONG validation would mean the wiring debt contains working physics-discovery primitives. REFUTATION means the self-discovery layer is decoratively-named scaffolding (Pattern-P at primitive-name level — also a real architectural finding). |

## 6. Verdict
### **REFUTED**

- Observed: `1`
- Threshold: `sub_tests_passed >= 2.0 of_3`
- Reasoning: Proprio synthesis: SUB-A (system_laws_discovery vs P+T) = FAIL; SUB-B (pressure_state typing coverage) = STRONG_PASS; SUB-C (semantic_physics_validator triad) = FAIL. 1/3 sub-tests passed.

## 7. Reproduction
```
PYTHONPATH=src .venv/bin/python -m ophamin.cli scenario proprio-self-discovery --phase-2-report /Users/idirbenslama/Desktop/DEV/Kimera_SWM (Spherical Word Memory)/experiments/observatory/runs/proprio_phase_2/phase_2_report.json --phase-3-report /Users/idirbenslama/Desktop/DEV/Kimera_SWM (Spherical Word Memory)/experiments/observatory/runs/proprio_phase_3/phase_3_report.json --phase-4-report /Users/idirbenslama/Desktop/DEV/Kimera_SWM (Spherical Word Memory)/experiments/observatory/runs/proprio_phase_4/phase_4_report.json
```
- Environment lock: 405 entries

## 8. Provenance
- W3C PROV-O graph: 2 entities, 1 activities, 2 agents

## 9. Signature
- `3cd2f4eb05c4fe5c606e9b1b6e83eefe36beb4aee691d67eca0b69ab936ce7b6`

---
**⚠ 1 validation problem(s):**
- substrate_git_commit is empty — the substrate must be versioned
