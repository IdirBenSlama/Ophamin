# Ophamin Empirical Proof Record — `INCONCLUSIVE`

**Proof ID:** `bb5e9af1dd08a55f3685d9fbefbfc0536ac42c3d8e5df875d8c33976603ddf57`
**Schema:** v1.0  
**Created:** 2026-05-15T14:50:43.901320+00:00

## 1. Identity
- Ophamin: `0.1.0` @ `5ca7aaf11a1f8f93377ef92b7ffc674219683216`
- Substrate: **instrumented(kimera-swm)** @ `179edd233c157441c8b052bbea45e19fcc666561`

## 2. Claim
> Under sustained load on a balanced text corpus, Kimera's entity target completes each cycle in under 4.00 seconds at the 95th percentile (the architectural throughput ceiling).

- **Operationalization:** 95th-percentile of per-cycle wall-time (raw['cycle_seconds']) across the streamed batch; cycles that failed to record a cycle_seconds are excluded from the denominator
- **Threshold:** `p95_cycle_wall_time_s <= 4.0 seconds`
- **H0:** p95 wall-time > 4.00s
- **H1:** p95 wall-time <= 4.00s

## 3. Pre-registration
- Registered at: `2026-05-15T14:47:01.715915+00:00` (must precede §1 created)
- Config hash: `1bfc2c127c850b1a04fdff3622986f3f66f2a11b7c4d25dcce17fab02e4d20dc`
- Data hash: `83109a27c3df2a45b912398b969fa8f7250b3d04dee11916d73ecf679d828010`
- Analysis plan: Stream up to 200 balanced text records through Kimera's entity target wrapped in InstrumentedSubstrate, then compute the per-cycle wall-time distribution from the adapter's own ``cycle_seconds`` field. Pre-registered threshold: 95th-percentile cycle wall-time <= 4.00s. Secondary descriptive evidence reports the median / p50 / p99 wall-time, batch CPU total (from the periodic subprocess sampler), RSS peak, and process-tree maximums.

## 4. Data
- **offensive-security-corpus** (adversarial_corpus) — 4,416,305 records — `83109a27c3df2a45…` — metasploit-framework + SecLists + PayloadsAllTheThings + nuclei-templates + atomic-red-team + exploit-db + garak + prompt-injection / jailbreak sets

## 5. Evidence
| Pillar | Statistic | Value | Effect | 95% CI | p | Library | Cross-check |
|---|---|---|---|---|---|---|---|
| O.engineering.p95_wall_time | p95_cycle_wall_time_s | 0 | — | — | — | python-stdlib 3.14 | n/a |
| O.engineering.wall_time_distribution | cycle_wall_time_distribution | 0 | — | — | — | python-stdlib 3.14 | n/a |
| O.engineering.batch_cpu | batch_cpu_total_s | 243.846 | — | — | — | psutil 7.x | n/a |
| O.engineering.rss_peak | rss_peak_bytes | 4.59319e+09 | — | — | — | psutil 7.x | n/a |

## 6. Verdict
### **INCONCLUSIVE**

- Observed: `0`
- Threshold: `p95_cycle_wall_time_s <= 4.0 seconds`
- Reasoning: measured per-cycle wall-time on 0/200 cycles (0 adapter errors); distribution: median 0.00s, p95 0.00s, p99 0.00s (range 0.00-0.00s); batch totals: wall 222.04s, cpu 243.85s (periodic_subprocess_sampler), rss_peak 4593.2MB, max threads 80, max procs 2; too few cycles measured to decide

## 7. Reproduction
```
PYTHONPATH=src .venv/bin/python -m ophamin.cli scenario throughput-ceiling
```
- Environment lock: 178 entries

## 8. Provenance
- W3C PROV-O graph: 2 entities, 1 activities, 2 agents

## 9. Signature
- `33560f56a35dd98e4fee503d8d89aa18118799ca794582091f3856c25cd2d207`

---
**✓ Record is well-formed** — falsifiable, pre-registered, traceable, reproducible, attributed.
