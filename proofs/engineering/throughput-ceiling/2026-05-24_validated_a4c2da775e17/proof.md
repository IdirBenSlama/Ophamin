# Empirical Proof Record — **VALIDATED**

**Proof ID:** `a4c2da775e1746fc0c0050b761179823c2eaa317b13e43a3eedaa950c429f22a`  
**Created:** 2026-05-24T03:32:46.534089+00:00

## 1. Claim

> Under sustained load on a balanced text corpus, Kimera's entity target completes each cycle in under 5.00 seconds at the 95th percentile (the architectural throughput ceiling).

- **Operationalisation:** 95th-percentile of per-cycle wall-time (raw['cycle_seconds']) across the streamed batch; cycles that failed to record a cycle_seconds are excluded from the denominator
- **Threshold:** `p95_cycle_wall_time_s <= 5.0 seconds`
- **H0:** p95 wall-time > 5.00s
- **H1:** p95 wall-time <= 5.00s

## 2. Verdict

**Outcome:** VALIDATED  
**Observed:** `4.197375525604002`

measured per-cycle wall-time on 40/40 cycles (0 adapter errors); distribution: median 1.47s, p95 4.20s, p99 6.69s (range 0.30-8.29s); batch totals: wall 90.59s, cpu 89.72s (periodic_subprocess_sampler), rss_peak 3822.3MB, max threads 93, max procs 3

## 3. Pre-registration

- Registered at: `2026-05-24T03:31:15.714820+00:00`
- Config hash: `311bd781c294b3d83c2235bf6767fba83e5b1fa59be6230ca570d9e53f376cf5`
- Data hash: `83109a27c3df2a45b912398b969fa8f7250b3d04dee11916d73ecf679d828010`

_Stream up to 40 balanced text records through Kimera's entity target wrapped in InstrumentedSubstrate, then compute the per-cycle wall-time distribution from the adapter's own ``cycle_seconds`` field. Pre-registered threshold: 95th-percentile cycle wall-time <= 5.00s. Secondary descriptive evidence reports the median / p50 / p99 wall-time, batch CPU total (from the periodic subprocess sampler), RSS peak, and process-tree maximums._

## 4. Data

- Substrate: `instrumented(kimera-swm)` @ `78cb9f9fc6a8`
- Dataset: `offensive-security-corpus` (adversarial_corpus, 4416305 records, hash `83109a27c3df…`)

## 5. Evidence

| pillar | statistic | value | 95% CI | library |
|---|---|---|---|---|
| `O.engineering.p95_wall_time` | `p95_cycle_wall_time_s` | `4.197375525604002` | — | python-stdlib 3.14 |
| `O.engineering.wall_time_distribution` | `cycle_wall_time_distribution` | `1.4651527499081567` | — | python-stdlib 3.14 |
| `O.engineering.batch_cpu` | `batch_cpu_total_s` | `89.722139759` | — | psutil 7.x |
| `O.engineering.rss_peak` | `rss_peak_bytes` | `3822256128.0` | — | psutil 7.x |

## 6. Signature

`24b38add7a4badc11db9a9a0f24dcda8f2b968e453a7eb43cd6b99f2d7fc57d3`
