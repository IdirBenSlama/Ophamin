# Empirical Proof Record — **REFUTED**

**Proof ID:** `e7450c9afec58d0237254fff0699422ab9eba17799063b166d1deeaa3e1a52e9`  
**Created:** 2026-05-23T20:49:15.033957+00:00

## 1. Claim

> At least 80% of the always-on numeric signals Kimera emits (those present in EVERY cycle) carry real dynamics (vary with the stimulus) rather than emitting a frozen default constant.

- **Operationalisation:** Stream 64 diverse records from the 'flores' corpus through the Kimera 'entity' target; collect every finite numeric leaf in CycleResult.raw per cycle. Restrict to ALWAYS-ON signals (present in all cycles → zero sampling doubt); a signal is LIVE if it takes >= 2 distinct values, FROZEN if constant. liveness_rate = always_on_live / always_on_total. Under-sampled signals are excluded (a signal seen in few cycles is trivially constant — not a frozen default).
- **Threshold:** `liveness_rate >= 0.8 proportion`
- **H0:** H0: liveness < 80% — most emitted signals are frozen defaults; the body is structurally wired but not dynamically alive; the frozen worklist is non-empty
- **H1:** H1: liveness >= 80% — the emitted signal surface is dynamically alive

## 2. Verdict

**Outcome:** REFUTED  
**Observed:** `0.6776556776556777`

always-on liveness 0.6777: 555/819 every-cycle signals carry real dynamics; 264 are frozen defaults (the worklist); Wilson 95% CI [0.6449, 0.7088]. Context: whole-surface 3315/15754 (0.2104, deflated by under-sampling); 64 cycles

![liveness_rate confidence interval](assets/ci_liveness_rate.png)

## 3. Pre-registration

- Registered at: `2026-05-23T20:46:58.311038+00:00`
- Config hash: `e683f31a2ae22e752e0db448f4a3059407edee45e64a148af8fd44713cfb157b`
- Data hash: `bf4196403365897ad95dbcc18fc5116a99bc007f58e71dd302566b61b4296262`

_Stream 64 diverse 'flores' records through the Kimera 'entity' target; flatten all numeric leaves in CycleResult.raw per cycle; classify each signal live (>=2 distinct values) vs frozen (constant). Decide liveness_rate against threshold >= 80%. Wilson 95% CI on the proportion. The frozen-signal worklist (by organ) is in the proof evidence._

## 4. Data

- Substrate: `kimera-swm` @ `78cb9f9fc6a8`
- Dataset: `flores-200` (parallel_corpus, 997 records, hash `bf4196403365…`)

## 5. Evidence

| pillar | statistic | value | 95% CI | library |
|---|---|---|---|---|
| `signal_dynamics` | `liveness_rate` | `0.6776556776556777` | (0.6449, 0.7088) | statsmodels 0.14.6 |

## 6. Signature

`e7cd14131f399ed5c11dd0d75be4f27bfd0b1197f5082c8dbfdd8b36ee9ceda9`
