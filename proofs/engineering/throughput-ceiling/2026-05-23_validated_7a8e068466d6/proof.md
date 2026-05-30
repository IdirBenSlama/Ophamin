# Empirical Proof Record — **VALIDATED**

**Proof ID:** `7a8e068466d606dfed784d544066d76d08f2eb1b02cfe54e240e3fbe619df427`  
**Created:** 2026-05-23T23:14:37.297085+00:00

## 1. Claim

> Under sustained load on a balanced text corpus, Kimera's entity target completes each cycle in under 5.00 seconds at the 95th percentile (the architectural throughput ceiling).

- **Operationalisation:** 95th-percentile of per-cycle wall-time (raw['cycle_seconds']) across the streamed batch; cycles that failed to record a cycle_seconds are excluded from the denominator
- **Threshold:** `p95_cycle_wall_time_s <= 5.0 seconds`
- **H0:** p95 wall-time > 5.00s
- **H1:** p95 wall-time <= 5.00s

## 2. Verdict

**Outcome:** VALIDATED  
**Observed:** `3.8971680900198398`

measured per-cycle wall-time on 40/40 cycles (0 adapter errors); distribution: median 1.49s, p95 3.90s, p99 5.81s (range 0.25-6.86s); batch totals: wall 86.43s, cpu 90.02s (periodic_subprocess_sampler), rss_peak 3820.0MB, max threads 96, max procs 3

## 3. Pre-registration

- Registered at: `2026-05-23T23:13:10.629945+00:00`
- Config hash: `311bd781c294b3d83c2235bf6767fba83e5b1fa59be6230ca570d9e53f376cf5`
- Data hash: `83109a27c3df2a45b912398b969fa8f7250b3d04dee11916d73ecf679d828010`

_Stream up to 40 balanced text records through Kimera's entity target wrapped in InstrumentedSubstrate, then compute the per-cycle wall-time distribution from the adapter's own ``cycle_seconds`` field. Pre-registered threshold: 95th-percentile cycle wall-time <= 5.00s. Secondary descriptive evidence reports the median / p50 / p99 wall-time, batch CPU total (from the periodic subprocess sampler), RSS peak, and process-tree maximums._

## 4. Data

- Substrate: `instrumented(kimera-swm)` @ `78cb9f9fc6a8`
- Dataset: `offensive-security-corpus` (adversarial_corpus, 4416305 records, hash `83109a27c3df…`)

## 5. Evidence

| pillar | statistic | value | 95% CI | library |
|---|---|---|---|---|
| `O.engineering.p95_wall_time` | `p95_cycle_wall_time_s` | `3.8971680900198398` | — | python-stdlib 3.14 |
| `O.engineering.wall_time_distribution` | `cycle_wall_time_distribution` | `1.4903680626302958` | — | python-stdlib 3.14 |
| `O.engineering.batch_cpu` | `batch_cpu_total_s` | `90.01924266399999` | — | psutil 7.x |
| `O.engineering.rss_peak` | `rss_peak_bytes` | `3820027904.0` | — | psutil 7.x |

## 6. Signature

`119ebb4fea67aef36e78003be21eade59d3976ef62c1a019edb750446cf5b604`
