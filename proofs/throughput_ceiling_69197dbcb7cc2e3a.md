# Ophamin Empirical Proof Record — `VALIDATED`

**Proof ID:** `69197dbcb7cc2e3a8ee46d2464d970f52f20a9cfcc969139e95b93f0db77f3dd`
**Schema:** v1.0  
**Created:** 2026-05-15T14:58:38.684512+00:00

## 1. Identity
- Ophamin: `0.1.0` @ `f517ec81fe79bfc02abead297de11179091640e2`
- Substrate: **instrumented(kimera-swm)** @ `179edd233c157441c8b052bbea45e19fcc666561`

## 2. Claim
> Under sustained load on a balanced text corpus, Kimera's entity target completes each cycle in under 4.00 seconds at the 95th percentile (the architectural throughput ceiling).

- **Operationalization:** 95th-percentile of per-cycle wall-time (raw['cycle_seconds']) across the streamed batch; cycles that failed to record a cycle_seconds are excluded from the denominator
- **Threshold:** `p95_cycle_wall_time_s <= 4.0 seconds`
- **H0:** p95 wall-time > 4.00s
- **H1:** p95 wall-time <= 4.00s

## 3. Pre-registration
- Registered at: `2026-05-15T14:54:56.599862+00:00` (must precede §1 created)
- Config hash: `1bfc2c127c850b1a04fdff3622986f3f66f2a11b7c4d25dcce17fab02e4d20dc`
- Data hash: `83109a27c3df2a45b912398b969fa8f7250b3d04dee11916d73ecf679d828010`
- Analysis plan: Stream up to 200 balanced text records through Kimera's entity target wrapped in InstrumentedSubstrate, then compute the per-cycle wall-time distribution from the adapter's own ``cycle_seconds`` field. Pre-registered threshold: 95th-percentile cycle wall-time <= 4.00s. Secondary descriptive evidence reports the median / p50 / p99 wall-time, batch CPU total (from the periodic subprocess sampler), RSS peak, and process-tree maximums.

## 4. Data
- **offensive-security-corpus** (adversarial_corpus) — 4,416,305 records — `83109a27c3df2a45…` — metasploit-framework + SecLists + PayloadsAllTheThings + nuclei-templates + atomic-red-team + exploit-db + garak + prompt-injection / jailbreak sets

## 5. Evidence
| Pillar | Statistic | Value | Effect | 95% CI | p | Library | Cross-check |
|---|---|---|---|---|---|---|---|
| O.engineering.p95_wall_time | p95_cycle_wall_time_s | 2.35728 | — | — | — | python-stdlib 3.14 | n/a |
| O.engineering.wall_time_distribution | cycle_wall_time_distribution | 1.01041 | — | — | — | python-stdlib 3.14 | n/a |
| O.engineering.batch_cpu | batch_cpu_total_s | 243.859 | — | — | — | psutil 7.x | n/a |
| O.engineering.rss_peak | rss_peak_bytes | 4.57672e+09 | — | — | — | psutil 7.x | n/a |

## 6. Verdict
### **VALIDATED**

- Observed: `2.35728`
- Threshold: `p95_cycle_wall_time_s <= 4.0 seconds`
- Reasoning: measured per-cycle wall-time on 200/200 cycles (0 adapter errors); distribution: median 1.01s, p95 2.36s, p99 3.02s (range 0.08-3.26s); batch totals: wall 221.94s, cpu 243.86s (periodic_subprocess_sampler), rss_peak 4576.7MB, max threads 80, max procs 2

## 7. Reproduction
```
PYTHONPATH=src .venv/bin/python -m ophamin.cli scenario throughput-ceiling
```
- Environment lock: 178 entries

## 8. Provenance
- W3C PROV-O graph: 2 entities, 1 activities, 2 agents

## 9. Signature
- `ae740c6246e190f06e71626ec8e618b199a6d54581640682254a1537ae02743a`

---
**✓ Record is well-formed** — falsifiable, pre-registered, traceable, reproducible, attributed.
