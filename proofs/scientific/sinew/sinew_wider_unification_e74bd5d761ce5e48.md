# Ophamin Empirical Proof Record — `VALIDATED`

**Proof ID:** `e74bd5d761ce5e48f2e0745713ea4f72b19bd578d00f04ae14a518360766c409`
**Schema:** v1.0  
**Created:** 2026-05-17T16:45:54.126957+00:00

## 1. Identity
- Ophamin: `0.9.0` @ `266439da70a5c913b3aa1abe011918a785bcf3a6`
- Substrate: **kimera-swm** @ `4552de7ee80c3c4eefb1ba103710e4c95fa11930`

## 2. Claim
> For each of 12 of Kimera's physics-named primitives (11 energy-field OrchestratorResult fields + prime_log_energy), test whether adding the primitive as a normalized 4th term to (P + T + CW_seed) at Walker M4 events is COMPATIBLE with the conservation framework (best-sign 4-term ratio ≤ 3-term baseline + 0.01). At least 8 of 12 candidates must be compatible — measurable physics-grade coherence at the conservation layer.

- **Operationalization:** Compute 3-term baseline ratio (P + T + CW_seed) at walker_m4 events. For each physics candidate X, test (P + T + CW_seed + sign · X) with sign ∈ {+1, -1}; record best-sign 4-term ratio. Classify each candidate: EXTENDS if ratio < baseline - noise_floor; COMPATIBLE if within ±noise_floor; BREAKS if > baseline + noise_floor. Headline metric = count of EXTENDS + COMPATIBLE candidates.
- **Threshold:** `compatible_or_extends_count >= 8.0 of_12`
- **H0:** compatible_or_extends_count < 8 — Kimera's physics-named primitives mostly DON'T fit the SEED conservation framework; Pattern-P at the primitive-name level; conservation is local to (P + T + CW_seed) rather than substrate-wide
- **H1:** compatible_or_extends_count >= 8 — substrate's physics-named primitives DO fit; physics-grade coherence is measurable at the conservation layer; Phase 5 of the Sinew campaign produces positive evidence

## 3. Pre-registration
- Registered at: `2026-05-17T16:45:53.939625+00:00` (must precede §1 created)
- Config hash: `c385cceb8c3ab1f0879134c7c3b01134ca634bebbc4a0edf136b174c0bafd727`
- Data hash: `5ca01594634b70ff8f5d176efc4e27ca605f0dc5040df136e88072707b1b8db8`
- Analysis plan: Read captured Sinew Phase 4-extended trajectory. Compute 3-term baseline (P + T + CW_seed) conservation ratio at Walker M4 events. For each of 11 energy fields + prime_log_energy (12 candidates total), compute best-sign 4-term ratio (P + T + CW_seed ± candidate). Classify per-candidate as EXTENDS (ratio < baseline - noise_floor), COMPATIBLE (within ±noise_floor), or BREAKS (> baseline + noise_floor). Headline = count of compatible+extends candidates >= 8 / 12.

## 4. Data
- **kimera-sinew-trajectory** (takwin-sinew-extended-trajectory) — 500 records — `5ca01594634b70ff…` — /Users/idirbenslama/Desktop/DEV/Kimera_SWM (Spherical Word Memory)/experiments/observatory/runs/sinew_phase_4_extended_v2/per_cycle_records.json

## 5. Evidence
| Pillar | Statistic | Value | Effect | 95% CI | p | Library | Cross-check |
|---|---|---|---|---|---|---|---|
| sinew_wider_unification | compatible_or_extends_count | 8 | — | — | — | ophamin.measuring.scenarios.sinew_wider_unification 0.9.0 | passed |

## 6. Verdict
### **VALIDATED**

- Observed: `8`
- Threshold: `compatible_or_extends_count >= 8.0 of_12`
- Reasoning: Wider-unification analysis (500 cycles, 105 walker_m4 events): 3-term baseline ratio = 0.0873. Per-candidate (out of 12): 4 EXTENDS, 4 COMPATIBLE, 4 BREAKS, 0 INSUFFICIENT. compatible_or_extends_count = 8. Details: quantum_energy=BREAKS(0.0992), spde_ground_energy=COMPATIBLE(0.0851), entanglement_entropy=BREAKS(0.0993), riemann_zeta_entropy=EXTENDS(0.0663), riemann_zeta_free_energy=EXTENDS(0.0663), crystal_binding_energy=COMPATIBLE(0.0805), quantum_interference_entropy=EXTENDS(0.0753), quantum_prime_basis_entropy=BREAKS(0.0994), rosetta_composition_entropy=EXTENDS(0.0767), voronoi_neighbourhood_entropy=COMPATIBLE(0.0824), turing_pattern_entropy=COMPATIBLE(0.0778), prime_log_energy=BREAKS(0.1064).

## 7. Reproduction
```
PYTHONPATH=src .venv/bin/python -m ophamin.cli scenario sinew-wider-unification --trajectory-path /Users/idirbenslama/Desktop/DEV/Kimera_SWM (Spherical Word Memory)/experiments/observatory/runs/sinew_phase_4_extended_v2/per_cycle_records.json
```
- Environment lock: 391 entries

## 8. Provenance
- W3C PROV-O graph: 2 entities, 1 activities, 2 agents

## 9. Signature
- `7c2730c6e3d6689339783ff340820a20519fddd693346e499d13f40068974b91`

---
**✓ Record is well-formed** — falsifiable, pre-registered, traceable, reproducible, attributed.
