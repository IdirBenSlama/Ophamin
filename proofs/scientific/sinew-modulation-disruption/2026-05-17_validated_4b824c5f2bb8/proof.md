# Empirical Proof Record — **VALIDATED**

**Proof ID:** `4b824c5f2bb8f7b55e2b19cdd4450a9e2e4e8c9270bccf269aa43d8a32134dcd`  
**Created:** 2026-05-17T17:32:44.332611+00:00

## 1. Claim

> For Walker M4 events in a Sinew Phase 4-extended trajectory, the modulated-CW conservation ratio R_mod EXCEEDS the seed-CW conservation ratio R_seed by at least 0.05 — the substrate's Phase 148-182 SCAR-CW modulation chain encodes experience-accumulation at the cost of conservation. Both R values use the same (P + T + CW) three-term sum with std-normalized inputs; only the CW source differs (Phase 137 seed `_p137_scar_w` vs the post-modulation `self._scar_coherence_weight`).

- **Operationalisation:** Read trajectory; compute R_seed = median|Δ(P+T+CW_seed)| / median|P+T+CW_seed| at Walker M4 events. Compute R_mod identically with CW = scar_coherence_weight_modulated. Headline metric = R_mod − R_seed. Verdict on delta ≥ threshold. Secondary: per-event-class R_seed vs R_mod, cor(P+T, modulation_delta) as counter-compensation signature, CW distribution statistics for both.
- **Threshold:** `modulation_disruption_delta >= 0.05 dimensionless`
- **H0:** modulation_disruption_delta < 0.05 — the substrate's modulation chain has been redesigned to preserve conservation; entry 991's finding regressed; the Phase 137 seed and the modulated value behave similarly at decision-points
- **H1:** modulation_disruption_delta >= 0.05 — Phases 148-182 are counter-compensatory by design at decision-points; entry 991's finding holds; the substrate prioritizes memory formation (modulations push CW up when stress up) over strict conservation

## 2. Verdict

**Outcome:** VALIDATED  
**Observed:** `0.07630155249669499`

Modulation-disruption measurement (500 cycles, 102 walker_m4 events): R_seed = 0.0873 [CI 0.0705, 0.1152], R_mod = 0.1636 [CI 0.1519, 0.1991], delta = +0.0763. Counter-compensation signature cor(P+T, modulation_delta) = +0.0405 (positive = modulations push CW up when stress up = anti-conservation by design).

## 3. Pre-registration

- Registered at: `2026-05-17T17:32:44.169158+00:00`
- Config hash: `22f4999e3f8dad9f743ae5406d741096143ac81cefea84738c66e38df6d9784c`
- Data hash: `fd2b8faaf10d26df1b01c6056b090ca8f74c07eedc429cc3a2b9512728ef7a9f`

_Read captured Kimera trajectory with both Phase 137 seed AND post-Phase-148-182 modulated scar_coherence_weight. Detect Walker M4 events. Compute R_seed and R_mod using same (P+T+CW) three-term sum, std-normalized. Headline = R_mod − R_seed. Verdict on delta >= 0.05. Secondary: cross-event-class R_seed vs R_mod; counter-compensation correlation cor(P+T, modulation_delta) as architectural signature._

## 4. Data

- Substrate: `kimera-swm` @ `4552de7ee80c`
- Dataset: `kimera-sinew-trajectory` (takwin-sinew-extended-trajectory-with-modulated-cw, 500 records, hash `fd2b8faaf10d…`)

## 5. Evidence

| pillar | statistic | value | 95% CI | library |
|---|---|---|---|---|
| `sinew_modulation_disruption` | `modulation_disruption_delta` | `0.07630155249669499` | — | ophamin.measuring.scenarios.sinew_modulation_disruption 0.9.0 |

## 6. Signature

`eff73722f7476e11882497d530cc3eeccb6a5ee5bf9af39dfb31be6738d65a85`
