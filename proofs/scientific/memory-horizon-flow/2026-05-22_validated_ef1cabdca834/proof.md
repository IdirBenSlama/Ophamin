# Empirical Proof Record — **VALIDATED**

**Proof ID:** `ef1cabdca834fb1cce611630f3e1091eb6e5ab830edd30c4c39b0fff7bd1a1eb`  
**Created:** 2026-05-22T16:01:39.308346+00:00

## 1. Claim

> Across a long single-pass stream, the substrate still recalls earlier experiences beyond a fixed context window: □ (for every probe whose lag exceeds window_ref=256, recall Jaccard ≥ 0.50). The reported floor is the worst beyond-window probe.

- **Operationalisation:** Stream 400 distinct stimuli once through Kimera's entity target, then re-probe 20 positions spread over the stream. For each probe, recall = Jaccard(concept set at first exposure, concept set at probe); lag = intervening cycles. recall_floor_beyond_window = min recall over probes with lag > 256; the □ invariant holds iff that floor ≥ 0.50.
- **Threshold:** `recall_floor_beyond_window >= 0.5 jaccard`
- **H0:** H0: recall < 0.50 for some item recalled beyond window_ref=256 — the horizon is shorter than the reference window
- **H1:** H1: recall ≥ 0.50 for every beyond-window probe — memory reaches past a fixed window of that size

## 2. Verdict

**Outcome:** VALIDATED  
**Observed:** `1.0`

recall floor 1.0000 over 5 beyond-window probes (lag > 256); mean recall 1.0000, stdev 0.0000; memory horizon (max lag with recall ≥ 0.50) = 360 cycles; max lag measured 360; 400-item single-pass stream; 5 probes produced no concept set; worst beyond-window probe: stimulus 42 @ lag 360 = 1.0000; control: beyond-window recall median 1.000 vs cross-item median 0.000, Mann-Whitney p=7.5e-06 (recall real beyond window)

## 3. Pre-registration

- Registered at: `2026-05-22T16:01:39.048005+00:00`
- Config hash: `44cc9a3bf33f3a0b7bdab2a0977ca76fa4ea6bb51e6867d3edd781ff113fc6c4`
- Data hash: `ad79ab41ed3eb80cd1fbe8041eea8cc8ca0d7fe0595c54db2d634f2510514817`

_Stream 400 stimuli once, then re-probe 20 evenly-spread positions. Per probe compute recall = Jaccard(first exposure concepts, probe concepts) and lag = probe_cycle − exposure_cycle. Partition probes at window_ref=256. Decide □: min recall over beyond-window probes ≥ 0.50. INCONCLUSIVE if fewer than 3 beyond-window probes are valid. The lag→recall curve, memory horizon (max lag with recall ≥ floor), and the negative control are descriptive._

## 4. Data

- Substrate: `kimera-swm` @ `0092eb373087`
- Dataset: `kimera-memory-horizon-stream` (substrate-trajectory+single-pass-stream, 420 records, hash `ad79ab41ed3e…`)

## 5. Evidence

| pillar | statistic | value | 95% CI | library |
|---|---|---|---|---|
| `O.flow.memory_horizon` | `recall_floor_beyond_window` | `1.0` | — | ophamin 0.103.0 |

## 6. Signature

`f8a384a68785c069f9c6e4d2e11d03c54d73f00d8348a35fb27acc27e158719b`
