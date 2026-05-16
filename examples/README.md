# `examples/` — runnable templates

Two flavours of example:

## Per-scenario hand-tailored runners (six)

Showcases the typical construction pattern for a scenario whose
configuration is non-trivial (the corpus connector + per-target
options + score callback):

| Runner | Scenario | What it shows |
|---|---|---|
| [`run_immune_siege.py`](run_immune_siege.py) | concentrated-immune-siege | GWF false-positive ceiling with the cyber corpus |
| [`run_logic_topology_siege.py`](run_logic_topology_siege.py) | logic-topology-siege | Walker sustained-traversal on Linux kernel commits |
| [`run_organizational_dissonance.py`](run_organizational_dissonance.py) | organizational-dissonance | Dissonance firing-rate on Enron |
| [`run_philosophical_self_reference.py`](run_philosophical_self_reference.py) | philosophical-self-reference | Paired self-ref vs neutral comparison via Cohen's d |
| [`run_rosetta_scaling.py`](run_rosetta_scaling.py) | rosetta-scaling | Rosetta cross-language invariance on FLORES-200 |
| [`run_throughput_ceiling.py`](run_throughput_ceiling.py) | throughput-ceiling | Wrapping a substrate in InstrumentedSubstrate for p95 wall-time |

## Generic runner — covers any registered scenario by name

[`run_scenario.py`](run_scenario.py) — dispatches into `SCENARIOS[name]`
and runs against `MockSubstrate(seed=1)` for scenarios whose
constructor accepts only default arguments. Use when the scenario
doesn't need per-instance configuration beyond `n_cycles`.

```bash
python examples/run_scenario.py concentrated-immune-siege
python examples/run_scenario.py organizational-dissonance --n-cycles 100
python examples/run_scenario.py rosetta-scaling --out proofs/scientific/rosetta/test.json
```

## Discovery commands (no code reading required)

```bash
ophamin scenario list                          # every registered scenario
ophamin scenario list --tier empirical_deep    # filter to one tier
ophamin scenario show <name>                   # full metadata block for one
```

## Scenarios that NEED a captured trajectory

These 9 scenarios read a JSON trajectory file captured from Kimera's
observatory; they cannot be run from the generic template because the
trajectory path is a required argument:

- bayesian-phi-posterior (Phi trajectory)
- causal-discovery (multi-channel trajectory)
- cross-channel-mi (multi-channel trajectory)
- prime-structure (prime-emission trajectory)
- prime-factorization (prime-emission trajectory)
- prime-ecosystem (prime-emission trajectory)
- prime-direct-lookup (ArachneProtocol.lookup trajectory)
- prime-cross-instance (N-process trajectory)
- quantum-basis-correlation (prime-emission trajectory with stimulus class)

For each of these, the Kimera-SWM observatory tree provides a
capture script (look for `experiments/observatory/capture_*.py`
on the Kimera-side); the resulting JSON is what these scenarios
ingest. Construct the scenario directly in Python:

```python
from ophamin.measuring.scenarios import SCENARIOS

cls = SCENARIOS["prime-structure"]
scenario = cls(trajectory_path="/path/to/captured.json")
record = scenario.run(substrate)
```

## Mock + Kimera adapter end-to-ends

- [`run_mock_experiment.py`](run_mock_experiment.py) — 4×2 mock sweep,
  applies all pillars + diagnostics, walks the lineage store.
- [`run_kimera_discovery.py`](run_kimera_discovery.py) — Layer A schema
  mining against a real Kimera-SWM repo (no substrate run).
- [`verify_kimera_adapter.py`](verify_kimera_adapter.py) — self-test the
  Kimera adapter (probes every target, reports reachability).
- [`measure_kimera_throughput.py`](measure_kimera_throughput.py) — direct
  use of `InstrumentedSubstrate` to profile a real Kimera bracket.
