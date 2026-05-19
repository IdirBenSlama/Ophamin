# Empirical Proof Record — **VALIDATED**

**Proof ID:** `9989f42bc8f2b0d230ddc9b61a2d6ff74cbe28d1a4f057e0689449e858dceb4f`  
**Created:** 2026-05-14T20:39:41.476793+00:00

## 1. Claim

> A 50,000-cycle component-level catastrophic run against Kimera-SWM completes within 4.0 hours on this vessel.

- **Operationalisation:** measured steady-state cycles/sec (construction excluded) of the fastest component target, projected to 50000 cycles
- **Threshold:** `projected_50k_component_run_hours <= 4.0 hours`
- **H0:** projected run time > 4.0h — in-session density testing impractical
- **H1:** projected run time <= 4.0h — in-session density testing is practical

## 2. Verdict

**Outcome:** VALIDATED  
**Observed:** `0.5681984997257435`

observed 0.568198 satisfies the pre-registered threshold (projected_50k_component_run_hours <= 4.0 hours)

## 3. Pre-registration

- Registered at: `2026-05-14T20:38:58.421081+00:00`
- Config hash: `8d26f6573f75b50b4f74150a9a35aec6f748287b369b98a3107829c3f6adf1b2`
- Data hash: `83109a27c3df2a45b912398b969fa8f7250b3d04dee11916d73ecf679d828010`

_Measure steady-state cycles/sec (construction separated from per-cycle cost) for the Kimera entity and two cheap components, each with and without the GPU-acceleration flag, on real offensive-security corpus stimuli truncated to 4000 chars. Project the fastest component's steady-state rate to a 50000-cycle run and compare against the 4.0h threshold._

## 4. Data

- Substrate: `kimera-swm` @ `9596c6810923`
- Dataset: `offensive-security-corpus` (adversarial_corpus, 4416305 records, hash `83109a27c3df…`)

## 5. Evidence

| pillar | statistic | value | 95% CI | library |
|---|---|---|---|---|
| `throughput.entity_cpu` | `steady_state_cycles_per_sec` | `4.2772529758101285` | — | ophamin 0.1.0 |
| `throughput.entity_gpu` | `steady_state_cycles_per_sec` | `4.306903481687651` | — | ophamin 0.1.0 |
| `throughput.arachne_cpu` | `steady_state_cycles_per_sec` | `24.205516857317008` | — | ophamin 0.1.0 |
| `throughput.arachne_gpu` | `steady_state_cycles_per_sec` | `24.443726788424712` | — | ophamin 0.1.0 |
| `throughput.rosetta_cpu` | `steady_state_cycles_per_sec` | `24.0279083175282` | — | ophamin 0.1.0 |

## 6. Signature

`3f745dee3a523f4e83c4277c527c51c791d130de2961ef7d713d7c6c90937f5e`
