# Ophamin Empirical Proof Record — `VALIDATED`

**Proof ID:** `90a140c5f64778db71689e04c73d8d3ee514e31a186a84c440350b3872917871`
**Schema:** v1.0  
**Created:** 2026-05-17T16:40:41.235951+00:00

## 1. Identity
- Ophamin: `0.8.5` @ `4fe98758319bdc35e0ee5fe4f30129fa9d663554`
- Substrate: **kimera-swm** @ `4552de7ee80c3c4eefb1ba103710e4c95fa11930`

## 2. Claim
> For Walker M4 events in a Sinew Phase 4-extended trajectory, the modulated-CW conservation ratio R_mod EXCEEDS the seed-CW conservation ratio R_seed by at least 0.05 — the substrate's Phase 148-182 SCAR-CW modulation chain encodes experience-accumulation at the cost of conservation. Both R values use the same (P + T + CW) three-term sum with std-normalized inputs; only the CW source differs (Phase 137 seed `_p137_scar_w` vs the post-modulation `self._scar_coherence_weight`).

- **Operationalization:** Read trajectory; compute R_seed = median|Δ(P+T+CW_seed)| / median|P+T+CW_seed| at Walker M4 events. Compute R_mod identically with CW = scar_coherence_weight_modulated. Headline metric = R_mod − R_seed. Verdict on delta ≥ threshold. Secondary: per-event-class R_seed vs R_mod, cor(P+T, modulation_delta) as counter-compensation signature, CW distribution statistics for both.
- **Threshold:** `modulation_disruption_delta >= 0.05 dimensionless`
- **H0:** modulation_disruption_delta < 0.05 — the substrate's modulation chain has been redesigned to preserve conservation; entry 991's finding regressed; the Phase 137 seed and the modulated value behave similarly at decision-points
- **H1:** modulation_disruption_delta >= 0.05 — Phases 148-182 are counter-compensatory by design at decision-points; entry 991's finding holds; the substrate prioritizes memory formation (modulations push CW up when stress up) over strict conservation

## 3. Pre-registration
- Registered at: `2026-05-17T16:40:41.072581+00:00` (must precede §1 created)
- Config hash: `e847a0d89a21a05d1efbe73a3c43b814da0c2cf7ac24a4581226e929f978b8ea`
- Data hash: `58732f97c5b2abbc04b7b7bf0d637947a75599ba9831ee1ee1a7335e3ca3e465`
- Analysis plan: Read captured Kimera trajectory with both Phase 137 seed AND post-Phase-148-182 modulated scar_coherence_weight. Detect Walker M4 events. Compute R_seed and R_mod using same (P+T+CW) three-term sum, std-normalized. Headline = R_mod − R_seed. Verdict on delta >= 0.05. Secondary: cross-event-class R_seed vs R_mod; counter-compensation correlation cor(P+T, modulation_delta) as architectural signature.

## 4. Data
- **kimera-sinew-trajectory** (takwin-sinew-extended-trajectory-with-modulated-cw) — 500 records — `58732f97c5b2abbc…` — /Users/idirbenslama/Desktop/DEV/Kimera_SWM (Spherical Word Memory)/experiments/observatory/runs/sinew_phase_4_extended_v2/per_cycle_records.json

## 5. Evidence
| Pillar | Statistic | Value | Effect | 95% CI | p | Library | Cross-check |
|---|---|---|---|---|---|---|---|
| sinew_modulation_disruption | modulation_disruption_delta | 0.0982613 | — | — | — | ophamin.measuring.scenarios.sinew_modulation_disruption 0.8.5 | passed |

## 6. Verdict
### **VALIDATED**

- Observed: `0.0982613`
- Threshold: `modulation_disruption_delta >= 0.05 dimensionless`
- Reasoning: Modulation-disruption measurement (500 cycles, 105 walker_m4 events): R_seed = 0.0873 [CI 0.0739, 0.1123], R_mod = 0.1856 [CI 0.1573, 0.2564], delta = +0.0983. Counter-compensation signature cor(P+T, modulation_delta) = +0.2688 (positive = modulations push CW up when stress up = anti-conservation by design).

## 7. Reproduction
```
PYTHONPATH=src .venv/bin/python -m ophamin.cli scenario sinew-modulation-disruption --trajectory-path /Users/idirbenslama/Desktop/DEV/Kimera_SWM (Spherical Word Memory)/experiments/observatory/runs/sinew_phase_4_extended_v2/per_cycle_records.json
```
- Environment lock: 391 entries

## 8. Provenance
- W3C PROV-O graph: 2 entities, 1 activities, 2 agents

## 9. Signature
- `2670a76324187a0a7ab171123de0f1e1ffdd6456e0c01bfd3df120feceba5db0`

---
**✓ Record is well-formed** — falsifiable, pre-registered, traceable, reproducible, attributed.
