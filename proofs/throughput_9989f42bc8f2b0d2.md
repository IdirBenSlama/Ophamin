# Ophamin Empirical Proof Record — `VALIDATED`

**Proof ID:** `9989f42bc8f2b0d230ddc9b61a2d6ff74cbe28d1a4f057e0689449e858dceb4f`
**Schema:** v1.0  
**Created:** 2026-05-14T20:39:41.476793+00:00

## 1. Identity
- Ophamin: `0.1.0` @ `(no commit)`
- Substrate: **kimera-swm** @ `9596c681092358be4788dbbbff99da411be432dd`

## 2. Claim
> A 50,000-cycle component-level catastrophic run against Kimera-SWM completes within 4.0 hours on this vessel.

- **Operationalization:** measured steady-state cycles/sec (construction excluded) of the fastest component target, projected to 50000 cycles
- **Threshold:** `projected_50k_component_run_hours <= 4.0 hours`
- **H0:** projected run time > 4.0h — in-session density testing impractical
- **H1:** projected run time <= 4.0h — in-session density testing is practical

## 3. Pre-registration
- Registered at: `2026-05-14T20:38:58.421081+00:00` (must precede §1 created)
- Config hash: `8d26f6573f75b50b4f74150a9a35aec6f748287b369b98a3107829c3f6adf1b2`
- Data hash: `83109a27c3df2a45b912398b969fa8f7250b3d04dee11916d73ecf679d828010`
- Analysis plan: Measure steady-state cycles/sec (construction separated from per-cycle cost) for the Kimera entity and two cheap components, each with and without the GPU-acceleration flag, on real offensive-security corpus stimuli truncated to 4000 chars. Project the fastest component's steady-state rate to a 50000-cycle run and compare against the 4.0h threshold.

## 4. Data
- **offensive-security-corpus** (adversarial_corpus) — 4,416,305 records — `83109a27c3df2a45…` — metasploit-framework + SecLists + PayloadsAllTheThings + nuclei-templates + atomic-red-team + exploit-db + garak + prompt-injection / jailbreak sets

## 5. Evidence
| Pillar | Statistic | Value | Effect | 95% CI | p | Library | Cross-check |
|---|---|---|---|---|---|---|---|
| throughput.entity_cpu | steady_state_cycles_per_sec | 4.27725 | — | — | — | ophamin 0.1.0 | n/a |
| throughput.entity_gpu | steady_state_cycles_per_sec | 4.3069 | — | — | — | ophamin 0.1.0 | n/a |
| throughput.arachne_cpu | steady_state_cycles_per_sec | 24.2055 | — | — | — | ophamin 0.1.0 | n/a |
| throughput.arachne_gpu | steady_state_cycles_per_sec | 24.4437 | — | — | — | ophamin 0.1.0 | n/a |
| throughput.rosetta_cpu | steady_state_cycles_per_sec | 24.0279 | — | — | — | ophamin 0.1.0 | n/a |

## 6. Verdict
### **VALIDATED**

- Observed: `0.568198`
- Threshold: `projected_50k_component_run_hours <= 4.0 hours`
- Reasoning: observed 0.568198 satisfies the pre-registered threshold (projected_50k_component_run_hours <= 4.0 hours)

## 7. Reproduction
```
PYTHONPATH=src .venv/bin/python -u examples/measure_kimera_throughput.py
```
- Environment lock: 177 entries

## 8. Provenance
- W3C PROV-O graph: 0 entities, 0 activities, 0 agents

## 9. Signature
- `3f745dee3a523f4e83c4277c527c51c791d130de2961ef7d713d7c6c90937f5e`

---
**✓ Record is well-formed** — falsifiable, pre-registered, traceable, reproducible, attributed.
