# Empirical Proof Record — **REFUTED**

**Proof ID:** `f295557437040044148de44cb6cb5b470ef729f840ca87f45578d5c8764c7dc9`  
**Created:** 2026-05-24T03:32:08.141870+00:00

## 1. Claim

> At least 80% of the always-on numeric signals Kimera emits (those present in EVERY cycle) carry real dynamics (vary with the stimulus) rather than emitting a frozen default constant.

- **Operationalisation:** Stream 40 diverse records from the 'flores' corpus through the Kimera 'entity' target; collect every finite numeric leaf in CycleResult.raw per cycle. Restrict to ALWAYS-ON signals (present in all cycles → zero sampling doubt); a signal is LIVE if it takes >= 2 distinct values, FROZEN if constant. liveness_rate = always_on_live / always_on_total. Under-sampled signals are excluded (a signal seen in few cycles is trivially constant — not a frozen default).
- **Threshold:** `liveness_rate >= 0.8 proportion`
- **H0:** H0: liveness < 80% — most emitted signals are frozen defaults; the body is structurally wired but not dynamically alive; the frozen worklist is non-empty
- **H1:** H1: liveness >= 80% — the emitted signal surface is dynamically alive

## 2. Verdict

**Outcome:** REFUTED  
**Observed:** `0.6642246642246642`

always-on liveness 0.6642: 544/819 every-cycle signals carry real dynamics; 275 are frozen defaults (the worklist); Wilson 95% CI [0.6312, 0.6957]. Context: whole-surface 2234/10370 (0.2154, deflated by under-sampling); 40 cycles

![liveness_rate confidence interval](assets/ci_liveness_rate.png)

## 3. Pre-registration

- Registered at: `2026-05-24T03:30:22.414817+00:00`
- Config hash: `aff78804fbf24aae8e45515cb6ddce91cd84466cd289943072c2ab44cafb4055`
- Data hash: `bf4196403365897ad95dbcc18fc5116a99bc007f58e71dd302566b61b4296262`

_Stream 40 diverse 'flores' records through the Kimera 'entity' target; flatten all numeric leaves in CycleResult.raw per cycle; classify each signal live (>=2 distinct values) vs frozen (constant). Decide liveness_rate against threshold >= 80%. Wilson 95% CI on the proportion. The frozen-signal worklist (by organ) is in the proof evidence._

## 4. Data

- Substrate: `kimera-swm` @ `78cb9f9fc6a8`
- Dataset: `flores-200` (parallel_corpus, 997 records, hash `bf4196403365…`)

## 5. Evidence

| pillar | statistic | value | 95% CI | library |
|---|---|---|---|---|
| `signal_dynamics` | `liveness_rate` | `0.6642246642246642` | (0.6312, 0.6957) | statsmodels 0.14.6 |

## 6. Signature

`5906b4818cd5367ce56f254ccdf0c74cd4a4075e31b9c2466e16fc52535f47e9`
