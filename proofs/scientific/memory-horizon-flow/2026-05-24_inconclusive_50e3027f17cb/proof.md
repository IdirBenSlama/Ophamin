# Empirical Proof Record — **INCONCLUSIVE**

**Proof ID:** `50e3027f17cba984c9f20d34634895aac83281870010dd6148cdf0714fd28abf`  
**Created:** 2026-05-24T03:30:04.455933+00:00

## 1. Claim

> Across a long single-pass stream, the substrate still recalls earlier experiences beyond a fixed context window: □ (for every probe whose lag exceeds window_ref=256, recall Jaccard ≥ 0.50). The reported floor is the worst beyond-window probe.

- **Operationalisation:** Stream 8 distinct stimuli once through Kimera's entity target, then re-probe 8 positions spread over the stream. For each probe, recall = Jaccard(concept set at first exposure, concept set at probe); lag = intervening cycles. recall_floor_beyond_window = min recall over probes with lag > 256; the □ invariant holds iff that floor ≥ 0.50.
- **Threshold:** `recall_floor_beyond_window >= 0.5 jaccard`
- **H0:** H0: recall < 0.50 for some item recalled beyond window_ref=256 — the horizon is shorter than the reference window
- **H1:** H1: recall ≥ 0.50 for every beyond-window probe — memory reaches past a fixed window of that size

## 2. Verdict

**Outcome:** INCONCLUSIVE  
**Observed:** `0.0`

recall floor 0.0000 over 0 beyond-window probes (lag > 256); mean recall 0.0000, stdev 0.0000; memory horizon (max lag with recall ≥ 0.50) = 8 cycles; max lag measured 8; 8-item single-pass stream; 0 probes produced no concept set; too few beyond-window probes (<3) to decide — widen the stream or lower window_ref

## 3. Pre-registration

- Registered at: `2026-05-24T03:30:04.172431+00:00`
- Config hash: `97758cc1fa8320dc018877a25a8d436ee411e4ff74e51964a6f5c637ebf2e278`
- Data hash: `221a8a035c85eee67ce8bccf6670a709747efc6253d96a5b9e81ed1b493edc57`

_Stream 8 stimuli once, then re-probe 8 evenly-spread positions. Per probe compute recall = Jaccard(first exposure concepts, probe concepts) and lag = probe_cycle − exposure_cycle. Partition probes at window_ref=256. Decide □: min recall over beyond-window probes ≥ 0.50. INCONCLUSIVE if fewer than 3 beyond-window probes are valid. The lag→recall curve, memory horizon (max lag with recall ≥ floor), and the negative control are descriptive._

## 4. Data

- Substrate: `kimera-swm` @ `78cb9f9fc6a8`
- Dataset: `kimera-memory-horizon-stream` (substrate-trajectory+single-pass-stream, 16 records, hash `221a8a035c85…`)

## 5. Evidence

| pillar | statistic | value | 95% CI | library |
|---|---|---|---|---|
| `O.flow.memory_horizon` | `recall_floor_beyond_window` | `0.0` | — | ophamin 0.115.2 |

## 6. Signature

`4989de94dc3a06cc4ca7831702fa8e956f88ae9bfd32b07bded58fbcc06f05a9`
