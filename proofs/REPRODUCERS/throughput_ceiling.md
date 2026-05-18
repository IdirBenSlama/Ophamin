# Reproducer — Throughput Ceiling (Kimera p95 cycle wall-time)

> **What this doc is**: external-reviewer walkthrough for the
> `ThroughputCeilingScenario` proof family (2 shipped) plus the
> related `measure_kimera_throughput.py` runner (1 shipped proof).
>
> **Companion**: this doc assumes you've read
> [`immune_siege.md`](immune_siege.md) §3 for the Python / Rust /
> JS verification-recipe templates. Those generalize across every
> proof family; this doc focuses on the throughput-specific bits.

## 1. The pre-registered claim

`ThroughputCeilingScenario` declares:

| Field | Value |
|---|---|
| `metric` | `p95_cycle_wall_time_s` |
| `comparator` | `<=` |
| `value` | `4.0` (seconds) |
| `H0` | p95 wall-time > 4.00s |
| `H1` | p95 wall-time <= 4.00s |

In plain terms: under sustained load on a balanced text corpus,
Kimera's `entity` target — wrapped in `InstrumentedSubstrate` —
completes each cycle in under 4 seconds at the 95th percentile.
This is the **architectural throughput ceiling** Kimera's design
names for sustained-load operation.

The companion `measure_kimera_throughput.py` runner emits a
**separate, related** proof against a different claim:

| Field | Value |
|---|---|
| `metric` | `projected_50k_component_run_hours` |
| `comparator` | `<=` |
| `value` | `4.0` (hours) |
| `H0` | projected 50K-cycle run > 4h |
| `H1` | projected 50K-cycle run <= 4h |

Same vessel, same threshold scale (4), different metric (a
projected total-time vs a per-cycle p95). Treat them as
complementary signals — one says "this run completes fast
enough"; the other says "each cycle is fast enough".

## 2. The 3 shipped proofs

| Proof file | Verdict | Observed | Source |
|---|---|---|---|
| [`throughput_ceiling_69197dbcb7cc2e3a.json`](../throughput_ceiling_69197dbcb7cc2e3a.json) | `VALIDATED` | p95 = **2.357 s** | `ThroughputCeilingScenario` against Kimera commit `179edd23…` |
| [`throughput_ceiling_bb5e9af1dd08a55f.json`](../throughput_ceiling_bb5e9af1dd08a55f.json) | `INCONCLUSIVE` | p95 = **0** (0/200 cycles measured) | Same scenario + commit; instrumentation gap |
| [`throughput_9989f42bc8f2b0d2.json`](../throughput_9989f42bc8f2b0d2.json) | `VALIDATED` | 50K-projection = **0.568 h** (~34 min) | `examples/measure_kimera_throughput.py` against Kimera commit `9596c681…` |

## 3. Why the INCONCLUSIVE proof is the framework working

The INCONCLUSIVE proof at `bb5e9af1…` shows
`p95_cycle_wall_time_s = 0` across 0/200 measured cycles.
Reasoning (from §6):

> measured per-cycle wall-time on 0/200 cycles (0 adapter errors);
> distribution: median 0.00s, p95 0.00s, p99 0.00s (range
> 0.00-0.00s); batch totals: wall 222.04s, cpu 243.85s
> (periodic_subprocess_sampler), rss_peak 4593.2MB, max threads
> 80, max procs 2; too few cycles measured to decide

Two important things this proof tells us:

1. **`p95 = 0` is NOT a VALIDATED result.** A naïve framework
   would compute `Threshold.decide(0.0) → 0.0 <= 4.0 → True` and
   emit VALIDATED. Ophamin's scenario emits **INCONCLUSIVE**
   because the substrate wasn't actually measured (0/200
   cycles recorded their `cycle_seconds` field). The full batch
   ran (222s wall, 244s CPU, ~4.6 GB peak RSS — the substrate
   did real work) but the instrumentation channel didn't catch
   per-cycle timings.
2. **Engineering signal**: the InstrumentedSubstrate wrapper's
   `cycle_seconds` field-injection path was broken or
   disconnected on this Kimera commit. The proof captures this
   as a falsifiable engineering observation rather than hiding
   the gap. A reviewer comparing the VALIDATED proof at
   `69197db…` (also against `179edd23…`) against this INCONCLUSIVE
   one sees the instrumentation regression directly in the
   record.

The framework's discipline of routing measurement-not-exercised
to INCONCLUSIVE (rather than VALIDATED-with-zero-observations or
REFUTED-via-zero) is the same pattern documented in
[`immune_siege.md`](immune_siege.md) §2 Setup C for the adapter-
error case there. Both surface honest empirical limitations.

## 4. Verify a proof signature (no re-run needed)

See [`immune_siege.md`](immune_siege.md) §3 for the full Python /
Rust / JS recipe templates. They apply to every proof family;
substitute the throughput proof path of your choice. Quick check
in Python:

```bash
ophamin schema validate proofs/throughput_ceiling_69197dbcb7cc2e3a.json
# Expected: OK    proofs/throughput_ceiling_69197dbcb7cc2e3a.json: proof@1.0
#           summary: 1 ok, 0 failed
```

All 3 shipped proofs verify under the default sign key.

## 5. Re-run the scenario (full corpus)

For `ThroughputCeilingScenario` (proofs 1 + 2):

```bash
PYTHONPATH=src .venv/bin/python -u examples/run_throughput_ceiling.py
```

The runner emits a proof against the `entity` target wrapped in
`InstrumentedSubstrate`. Same `offensive-security-corpus`
prerequisite as immune_siege — see
[`immune_siege.md`](immune_siege.md) §4 for the corpus + env-lock
details.

For `measure_kimera_throughput.py` (proof 3):

```bash
PYTHONPATH=src .venv/bin/python -u examples/measure_kimera_throughput.py
```

Different runner, different artifact — emits one proof per
(component × CPU/GPU) configuration. The shipped proof reports
5 evidence rows: entity-CPU, entity-GPU, arachne-CPU, arachne-
GPU, rosetta-CPU. The projection is against the **fastest**
component's steady-state rate.

**Hardcoded runner constants** (`examples/run_throughput_ceiling.py`):
the runner's `REPO`, `N_CYCLES = 200`, and `P95_CEILING_S = 4.0`
need to be adjusted to your Kimera checkout / sample size /
threshold. Same edit pattern as `examples/run_immune_siege.py`.

## 6. Spot-check (small subset)

`ThroughputCeilingScenario` is `ScientificEngineering`-tier — the
metric is wall-time, which is **noisy at small samples**. A spot
check needs at least 30-50 cycles to give a stable p95. Two
approaches:

**(a) Edit the runner's `N_CYCLES`** in
`examples/run_throughput_ceiling.py` from 200 to 50.

**(b) Construct directly in Python**:

```python
from ophamin.measuring.scenarios import ThroughputCeilingScenario
from ophamin.measuring.scenarios.base import DEFAULT_SIGN_KEY
from ophamin.seeing.substrate import KimeraAdapter, InstrumentedSubstrate

kimera = KimeraAdapter(
    "/path/to/your/Kimera-SWM",
    target="entity",
    mode="batch",
)
substrate = InstrumentedSubstrate(kimera)
scenario = ThroughputCeilingScenario(n_cycles=50, p95_wall_time_ceiling_s=4.0)
proof = scenario.run(substrate=substrate).sign(DEFAULT_SIGN_KEY)
print(f"verdict: {proof.verdict.outcome}")
print(f"observed p95: {proof.verdict.observed_value:.3f}s")
```

Expected: a fresh proof with p95 in the same neighbourhood as
2.357s (shipped VALIDATED at `69197db…`). If the InstrumentedSubstrate
wrapper isn't propagating `cycle_seconds` to the cycle dicts —
exactly the INCONCLUSIVE-case condition — you'll see p95 = 0
and `INCONCLUSIVE`. That's the framework correctly refusing to
declare a verdict when the substrate isn't measured.

## 7. Cross-proof diff

Same shape as [`immune_siege.md`](immune_siege.md) §6.
Comparisons that are meaningful here:

- **VALIDATED vs INCONCLUSIVE on the same Kimera commit**
  (proofs 1 + 2 are both against `179edd23…`). One was emitted
  when `cycle_seconds` propagation worked; one when it didn't.
  The proof_ids + signatures differ because §1's `created_at`
  differs; the **verdict** is the load-bearing diff.
- **VALIDATED across Kimera commits**: proof 1 vs proof 3
  (different commits — `179edd23…` vs `9596c681…`). Both
  pass their respective threshold under different metrics; the
  Kimera throughput envelope is robust across at least these
  two commits.

## 8. What this proof family demonstrates about Ophamin

A condensed version of the discipline-illustration in
[`immune_siege.md`](immune_siege.md) §7, throughput-specific:

1. **Pre-registration is compulsory** — the 4.0s threshold is the
   architectural ceiling Kimera's design names. Not chosen
   post-hoc to make the proof pass.
2. **Mechanical verdict** — `Threshold.decide(2.357) → 2.357 <=
   4.0 → True` → VALIDATED. No experimenter discretion.
3. **INCONCLUSIVE captures honest engineering gaps** — when
   InstrumentedSubstrate fails to record `cycle_seconds`, the
   verdict is INCONCLUSIVE, not VALIDATED-by-default or REFUTED-
   by-zero. Substrate-not-measured must never read as PASS.
4. **Two metrics, one architectural envelope** — the per-cycle
   p95 (≤ 4s) and the projected total run-time (≤ 4h) test the
   same engineering claim from different angles. Both
   VALIDATED on shipped vessel configurations.
5. **0.30.0 §7 fix applies here** — fresh proofs from
   `ThroughputCeilingScenario` now emit
   `PYTHONPATH=src .venv/bin/python -u examples/run_throughput_ceiling.py`
   as their Reproduction.command (the runner_path-form). Older
   shipped proofs retain the historical `ophamin.cli scenario`
   form — sealed; signature unaffected.

## See also

- [`immune_siege.md`](immune_siege.md) — companion reproducer doc; verification-recipe templates apply here.
- [`proofs/INDEX.md`](../INDEX.md) — full proof catalogue.
- [`src/ophamin/measuring/scenarios/throughput_ceiling.py`](../../src/ophamin/measuring/scenarios/throughput_ceiling.py) — scenario source.
- [`examples/run_throughput_ceiling.py`](../../examples/run_throughput_ceiling.py) — canonical runner for the scenario.
- [`examples/measure_kimera_throughput.py`](../../examples/measure_kimera_throughput.py) — companion runner for the 50K-cycle projection claim.
- [`docs/proposals/PROOF_REPRODUCTION_COMMAND.md`](../../docs/proposals/PROOF_REPRODUCTION_COMMAND.md) — closed at 0.30.0; explains why old vs new §7 strings differ.
