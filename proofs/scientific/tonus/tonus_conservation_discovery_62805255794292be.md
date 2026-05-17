# Ophamin Empirical Proof Record — `VALIDATED`

**Proof ID:** `62805255794292be163b887feb6218eb581653fa76060b59d21422c6efd84f85`
**Schema:** v1.0  
**Created:** 2026-05-17T19:11:51.204089+00:00

## 1. Identity
- Ophamin: `0.9.5` @ `2fef97a8fe947ebc9f164cd18329bcb9acda1ef7`
- Substrate: **kimera-swm** @ `4552de7ee80c3c4eefb1ba103710e4c95fa11930`

## 2. Claim
> For walker_m4 events in matched SEC v2 + Literary Sinew trajectories, Kimera's native Tonus primitive (Minor Component Analysis on event-conditioned delta vectors) discovers a conservation satisfying (a) linear conservation_strength > 0.5 per corpus, (b) cross-corpus discovered-coefficient cosine similarity > 0.85, and (c) polynomial-degree=2 conservation_strength > 0.95 (essentially exact nonlinear conservation). All three sub-conditions must validate.

- **Operationalization:** Apply native MCA (smallest-eigenvalue eigendecomposition of the event-delta Gram matrix) to matched (state_before, state_after) pairs at walker_m4 events on each corpus. Compare the discovered coefficient vectors via absolute cosine similarity (sign-invariant). Repeat with polynomial degree=2 basis expansion. Headline metric = 1 if all 3 sub-conditions satisfy; 0 otherwise.
- **Threshold:** `sub_conditions_satisfied >= 1.0 all_or_nothing`
- **H0:** At least one sub-condition fails: either Tonus discovers a weak conservation, the discovered direction is content-dependent, or polynomial extension doesn't tighten.
- **H1:** All three sub-conditions satisfy: substrate has a content-invariant linear conservation that becomes essentially exact at polynomial degree 2.

## 3. Pre-registration
- Registered at: `2026-05-17T19:11:51.007797+00:00` (must precede §1 created)
- Config hash: `b2ea44f75f9b468fd0f0b0e3642cf5657b69cba2e60f37aa29f6bae2569d78a9`
- Data hash: `b8340226621e18833ecf74c920dab0d07151d502c1b860b3cedae189ad70174d`
- Analysis plan: Apply native MCA on event-conditioned delta vectors for walker_m4 events on SEC v2 + Literary trajectories. Evaluate three sub-conditions: (a) per-corpus linear strength > 0.5, (b) cross-corpus cosine > 0.85, (c) polynomial degree=2 strength > 0.95. All three must satisfy to validate.

## 4. Data
- **kimera-tonus-cross-corpus** (takwin-sinew-extended-trajectory-paired) — 1,000 records — `b8340226621e1883…` — /Users/idirbenslama/Desktop/DEV/Kimera_SWM (Spherical Word Memory)/experiments/observatory/runs/sinew_phase_4_extended_v2/per_cycle_records.json;/Users/idirbenslama/Desktop/DEV/Kimera_SWM (Spherical Word Memory)/experiments/observatory/runs/sinew_phase_4_extended_literary_v1/per_cycle_records.json

## 5. Evidence
| Pillar | Statistic | Value | Effect | 95% CI | p | Library | Cross-check |
|---|---|---|---|---|---|---|---|
| tonus_conservation_discovery | sub_conditions_satisfied | 1 | — | — | — | ophamin.measuring.scenarios.tonus_conservation_discovery 0.9.5 | passed |

## 6. Verdict
### **VALIDATED**

- Observed: `1`
- Threshold: `sub_conditions_satisfied >= 1.0 all_or_nothing`
- Reasoning: Tonus discovery on matched SEC v2 + Literary trajectories: sub-A (per-corpus linear strength > 0.5) = True; sub-B (cross-corpus cosine > 0.85) = True (observed 0.9784); sub-C (nonlinear strength > 0.95) = True.

## 7. Reproduction
```
PYTHONPATH=src .venv/bin/python -m ophamin.cli scenario tonus-conservation-discovery --sec-trajectory-path /Users/idirbenslama/Desktop/DEV/Kimera_SWM (Spherical Word Memory)/experiments/observatory/runs/sinew_phase_4_extended_v2/per_cycle_records.json --literary-trajectory-path /Users/idirbenslama/Desktop/DEV/Kimera_SWM (Spherical Word Memory)/experiments/observatory/runs/sinew_phase_4_extended_literary_v1/per_cycle_records.json
```
- Environment lock: 405 entries

## 8. Provenance
- W3C PROV-O graph: 2 entities, 1 activities, 2 agents

## 9. Signature
- `dc284af46f1fc528a19402b090173cf2f29d820ef0c679d53c961165baceafa7`

---
**✓ Record is well-formed** — falsifiable, pre-registered, traceable, reproducible, attributed.
