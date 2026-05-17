# Ophamin Empirical Proof Record — `VALIDATED`

**Proof ID:** `20967025655105a56981848617eaf60c0e74862e7c1f93e7e88fa3fe67c2f165`
**Schema:** v1.0  
**Created:** 2026-05-17T17:32:46.125420+00:00

## 1. Identity
- Ophamin: `0.9.0` @ `1be7b296366c512ac3507e62ce9f32bda22f7c7b`
- Substrate: **kimera-swm** @ `4552de7ee80c3c4eefb1ba103710e4c95fa11930`

## 2. Claim
> For each of 12 of Kimera's physics-named primitives (11 energy-field OrchestratorResult fields + prime_log_energy), test whether adding the primitive as a normalized 4th term to (P + T + CW_seed) at Walker M4 events is COMPATIBLE with the conservation framework (best-sign 4-term ratio ≤ 3-term baseline + 0.01). At least 8 of 12 candidates must be compatible — measurable physics-grade coherence at the conservation layer.

- **Operationalization:** Compute 3-term baseline ratio (P + T + CW_seed) at walker_m4 events. For each physics candidate X, test (P + T + CW_seed + sign · X) with sign ∈ {+1, -1}; record best-sign 4-term ratio. Classify each candidate: EXTENDS if ratio < baseline - noise_floor; COMPATIBLE if within ±noise_floor; BREAKS if > baseline + noise_floor. Headline metric = count of EXTENDS + COMPATIBLE candidates.
- **Threshold:** `compatible_or_extends_count >= 8.0 of_12`
- **H0:** compatible_or_extends_count < 8 — Kimera's physics-named primitives mostly DON'T fit the SEED conservation framework; Pattern-P at the primitive-name level; conservation is local to (P + T + CW_seed) rather than substrate-wide
- **H1:** compatible_or_extends_count >= 8 — substrate's physics-named primitives DO fit; physics-grade coherence is measurable at the conservation layer; Phase 5 of the Sinew campaign produces positive evidence

## 3. Pre-registration
- Registered at: `2026-05-17T17:32:45.962254+00:00` (must precede §1 created)
- Config hash: `f2f7f6dc542eb407b8c6bc30af3d643e7919e59c52b0a22f0b9c4f885bcabf56`
- Data hash: `17afe2fa7c74a0dcb3159f9e2a88b84017a02c540d87bdb46d99490fc484f41c`
- Analysis plan: Read captured Sinew Phase 4-extended trajectory. Compute 3-term baseline (P + T + CW_seed) conservation ratio at Walker M4 events. For each of 11 energy fields + prime_log_energy (12 candidates total), compute best-sign 4-term ratio (P + T + CW_seed ± candidate). Classify per-candidate as EXTENDS (ratio < baseline - noise_floor), COMPATIBLE (within ±noise_floor), or BREAKS (> baseline + noise_floor). Headline = count of compatible+extends candidates >= 8 / 12.

## 4. Data
- **kimera-sinew-trajectory** (takwin-sinew-extended-trajectory) — 500 records — `17afe2fa7c74a0dc…` — /Users/idirbenslama/Desktop/DEV/Kimera_SWM (Spherical Word Memory)/experiments/observatory/runs/sinew_phase_4_extended_literary_v1/per_cycle_records.json

## 5. Evidence
| Pillar | Statistic | Value | Effect | 95% CI | p | Library | Cross-check |
|---|---|---|---|---|---|---|---|
| sinew_wider_unification | compatible_or_extends_count | 10 | — | — | — | ophamin.measuring.scenarios.sinew_wider_unification 0.9.0 | passed |

## 6. Verdict
### **VALIDATED**

- Observed: `10`
- Threshold: `compatible_or_extends_count >= 8.0 of_12`
- Reasoning: Wider-unification analysis (500 cycles, 102 walker_m4 events): 3-term baseline ratio = 0.0873. Per-candidate (out of 12): 4 EXTENDS, 6 COMPATIBLE, 2 BREAKS, 0 INSUFFICIENT. compatible_or_extends_count = 10. Details: quantum_energy=COMPATIBLE(0.0881), spde_ground_energy=BREAKS(0.0998), entanglement_entropy=COMPATIBLE(0.0908), riemann_zeta_entropy=EXTENDS(0.0717), riemann_zeta_free_energy=EXTENDS(0.0717), crystal_binding_energy=COMPATIBLE(0.0960), quantum_interference_entropy=EXTENDS(0.0719), quantum_prime_basis_entropy=COMPATIBLE(0.0908), rosetta_composition_entropy=EXTENDS(0.0709), voronoi_neighbourhood_entropy=COMPATIBLE(0.0959), turing_pattern_entropy=COMPATIBLE(0.0849), prime_log_energy=BREAKS(0.1173).

## 7. Reproduction
```
PYTHONPATH=src .venv/bin/python -m ophamin.cli scenario sinew-wider-unification --trajectory-path /Users/idirbenslama/Desktop/DEV/Kimera_SWM (Spherical Word Memory)/experiments/observatory/runs/sinew_phase_4_extended_literary_v1/per_cycle_records.json
```
- Environment lock: 391 entries

## 8. Provenance
- W3C PROV-O graph: 2 entities, 1 activities, 2 agents

## 9. Signature
- `217a8183cc35f63a014c81b8c13fcccd7f86698d1126b3ffd8cd5ab979acdec9`

---
**✓ Record is well-formed** — falsifiable, pre-registered, traceable, reproducible, attributed.
