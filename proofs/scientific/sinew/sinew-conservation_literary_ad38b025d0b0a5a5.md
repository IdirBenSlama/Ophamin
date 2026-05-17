# Ophamin Empirical Proof Record — `VALIDATED`

**Proof ID:** `ad38b025d0b0a5a5d86fb40ffcbf45abfdf38fb6b7d843c39e98f1dee9ff276f`
**Schema:** v1.0  
**Created:** 2026-05-17T17:32:43.593012+00:00

## 1. Identity
- Ophamin: `0.9.0` @ `1be7b296366c512ac3507e62ce9f32bda22f7c7b`
- Substrate: **kimera-swm** @ `4552de7ee80c3c4eefb1ba103710e4c95fa11930`

## 2. Claim
> For Walker M4 events (substrate decision-points: `halt_reason == 'lateral_leap'` OR `walker_annealing_events > 0`) in a Family J Takwin trajectory, the three-term conservation ratio R = median|Δ(P+T+CW_seed)| / median|P+T+CW_seed| is < 0.10. The Phase 137 SEED of scar_coherence_weight (`0.5 + 0.5 · _prior_trajectory_coherence`, before Phases 148-182 modulations) is the substrate's clean linear compensator at decision-points. Pressure and tension are averages over named proxy fields per the Sinew Phase 0 inventory (5 pressure + 5 tension); CW_seed is the legacy `scar_coherence_weight` field on OrchestratorResult. All inputs std-normalized before summing.

- **Operationalization:** Auto-detect Walker M4 events per cycle from the trajectory's events dict (lateral_leap halt OR walker_annealing_events > 0). For each event at index i > 0, compute residual = total(i-1) − total(i) where total = norm(P_avg) + norm(T_avg) + norm(CW_seed). Headline metric = median|residual| / median|total|. Bootstrap 95% CI from 2000 resamples. Verdict on R < threshold. Secondary characterizations: ouroboros + scar conservation ratios + scar magnitude quartile leak structure.
- **Threshold:** `walker_m4_conservation_ratio < 0.1 dimensionless`
- **H0:** walker_m4_conservation_ratio >= 0.10 — the substrate does not obey (P+T+CW_seed) conservation at decision-points; Sinew Phase 4-extended STRONG_PASS regressed; substrate decision-points fail to compensate stress redistribution within the three-term accounting
- **H1:** walker_m4_conservation_ratio < 0.10 — substrate decision-points conserve stress at the STRONG threshold; the Phase 137 SEED is doing genuine compensatory work; Sinew Phase 4-extended finding validated at this commit

## 3. Pre-registration
- Registered at: `2026-05-17T17:32:43.431004+00:00` (must precede §1 created)
- Config hash: `e91d5d3e93f469fbd3ac9d296ea1e6f4bb12e29a68379feb5d3d90b7cda4d2e0`
- Data hash: `13052054ea8feb16e36e5c07c912180a73996f222e7fd926017ebc2a03636000`
- Analysis plan: Read captured Kimera trajectory (Sinew Phase 4-extended shape — per-cycle records with pressure_proxies + tension_proxies + scar.scar_coherence_weight + events). Auto-detect Walker M4 / Ouroboros / scar events. Compute three-term conservation ratio at each event class. Bootstrap 95% CI from 2000 resamples. Verdict on walker_m4_conservation_ratio < 0.1. Secondary characterizations: ouroboros + scar ratios + scar magnitude quartile leak structure.

## 4. Data
- **kimera-sinew-trajectory** (takwin-sinew-extended-trajectory) — 500 records — `13052054ea8feb16…` — /Users/idirbenslama/Desktop/DEV/Kimera_SWM (Spherical Word Memory)/experiments/observatory/runs/sinew_phase_4_extended_literary_v1/per_cycle_records.json

## 5. Evidence
| Pillar | Statistic | Value | Effect | 95% CI | p | Library | Cross-check |
|---|---|---|---|---|---|---|---|
| sinew_conservation | walker_m4_conservation_ratio | 0.0872771 | — | (0.07048, 0.1152) | — | ophamin.measuring.scenarios.sinew_conservation 0.9.0 | passed |

## 6. Verdict
### **VALIDATED**

- Observed: `0.0872771`
- Threshold: `walker_m4_conservation_ratio < 0.1 dimensionless`
- Reasoning: Conservation analysis (500 cycles, 102 walker_m4 events / 48 ouroboros / 448 scar): walker_m4 R=0.0873 [CI 0.0705, 0.1152]; ouroboros R=0.0988; scar R=0.1004. Scar Q4-leak structure: Q1_smallest=0.0527, Q2=0.0691, Q3=0.1229, Q4_largest=0.1938.

## 7. Reproduction
```
PYTHONPATH=src .venv/bin/python -m ophamin.cli scenario sinew-conservation --trajectory-path /Users/idirbenslama/Desktop/DEV/Kimera_SWM (Spherical Word Memory)/experiments/observatory/runs/sinew_phase_4_extended_literary_v1/per_cycle_records.json
```
- Environment lock: 391 entries

## 8. Provenance
- W3C PROV-O graph: 2 entities, 1 activities, 2 agents

## 9. Signature
- `540ea99844ce58d84a76bd0be6181eb205470e83ce9221999f90dd6db4517868`

---
**✓ Record is well-formed** — falsifiable, pre-registered, traceable, reproducible, attributed.
