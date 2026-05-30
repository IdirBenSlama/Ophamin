# Empirical Proof Record — **VALIDATED**

**Proof ID:** `9446da2db140de54590b8f5455ddb5dece99e915ae5ad0c27ac4ef7e0d595cbd`  
**Created:** 2026-05-24T13:52:25.907281+00:00

## 1. Claim

> Across up to 200 real magnitudes in (0, 10000], the live internal-event chain with interoception ON (the door) emits a magnitude-ordered prime: Spearman(magnitude, p_thermo) >= 0.95, vs the legacy name-fingerprint (interoception OFF, ~0.47).

- **Operationalisation:** Distinct real FRED |values| within range drive the real static Takwin builders (_build_internal_event_payload_for_thermodynamic_transition / _spde_pressure_peak); each payload → real assign_from_internal_event → p_thermo from the registry, with _use_interoception True (door) and False (fingerprint); Spearman(magnitude, p_thermo) for both; distinctness.
- **Threshold:** `interoception_fidelity_spearman >= 0.95 rank-correlation`
- **H0:** H0: door Spearman < 0.95 — the live chain does not preserve the substrate's own magnitude
- **H1:** H1: door Spearman >= 0.95 — a faithful, ordered interoception

## 2. Verdict

**Outcome:** VALIDATED  
**Observed:** `1.0000000000000002`

door min-Spearman 1.0000 (per-builder {'thermodynamic_transition': 1.0, 'spde_pressure_peak': 1.0}) over 200 real magnitudes [0.001, 8952.16]; fingerprint baseline mean 0.0731 {'thermodynamic_transition': 0.1047, 'spde_pressure_peak': 0.0415}

![interoception_fidelity_spearman confidence interval](assets/ci_interoception_fidelity_spearman.png)

## 3. Pre-registration

- Registered at: `2026-05-24T13:52:25.597851+00:00`
- Config hash: `b4b4d5c3374126b64df9fd1c17a9be2692134980ef3c1e3333319e7424773b3a`
- Data hash: `70913ba380254e4a87785f94a4075ee44f925e6b51b3eb2375e0466bb9e5b6a2`

_Drive real Takwin builders across real magnitudes; route each through real assign_from_internal_event with interoception ON and OFF; Spearman(magnitude, p_thermo) for both; report distinctness + the contrast._

## 4. Data

- Substrate: `kimera-swm` @ `78cb9f9fc6a8`
- Dataset: `fred-real-magnitudes` (real-macro magnitudes (|v|) within the interoception operating range, 200 records, hash `70913ba38025…`)

## 5. Evidence

| pillar | statistic | value | 95% CI | library |
|---|---|---|---|---|
| `interoception_magnitude_fidelity` | `interoception_fidelity_spearman` | `1.0000000000000002` | (0.0000, 0.0000) | numpy 2.4.4 |

## 6. Signature

`89c7e70edcdbbdd160f17a70140c9ebb68ec2a3b0f5ef1b38ec6e07712209123`
