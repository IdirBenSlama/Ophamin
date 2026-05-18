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

## Concept walkthroughs (RFC-0002 phase demos)

Eight walkthrough scripts demonstrate the load-bearing framework
primitives shipped across the 0.9.x → 0.24.x line. Each:

* runs end-to-end with `PYTHONPATH=src python examples/walkthrough_*.py`,
* has rich docstring + annotated stdout,
* asserts its own invariants (the `assert` at the bottom is the
  contract; CI runs each as a smoke).

The four interop walkthroughs (CloudEvents / HTTP / MCP / OTel)
demonstrate the consumer-facing surfaces shipped at 0.17.0–0.21.0
that let any non-Python consumer drive, observe, or route Ophamin
records.

### Foundational phase walkthroughs

| Walkthrough | RFC-0002 phase | What it shows |
|---|---|---|
| [`walkthrough_fwer_correction.py`](walkthrough_fwer_correction.py) | E2 | Holm-Bonferroni + Benjamini-Hochberg on a hand-crafted family of 10 p-values; pins the Holm ⊆ BH rejection-set invariant; shows `CampaignRecord/2.0`'s `corrected_verdicts` integration. |
| [`walkthrough_reproducibility_audit.py`](walkthrough_reproducibility_audit.py) | E4 | `DeterministicSeedAuditScenario` against `crdt-laws`; demonstrates the exclusion list of `reproducibility_hash`; explains what the framework-wide audit gate in `tests/test_framework_wide_reproducibility.py` covers. |
| [`walkthrough_api_stability.py`](walkthrough_api_stability.py) | E8 | `@Stable` / `@Provisional` / `@Internal` / `@Deprecated` decorators on synthetic targets; shows the predicates (`is_stable`, `is_deprecated`); demonstrates `@Deprecated`'s `DeprecationWarning` at call site; surfaces the `StabilityInfo` invariants enforced at construction time. |
| [`walkthrough_cross_framework.py`](walkthrough_cross_framework.py) | E1 | Runs `BayesianPhiPosteriorCrosscheckScenario` — same NormalMean model under PyMC + NumPyro on the same synthetic data; prints per-backend posteriors side by side + agreement metrics; asserts means agree to ≤ 0.05. Demonstrates the cross-framework validation primitive RFC 0002 §3.1 E1 names as load-bearing. |

### Interop layer walkthroughs (E9.3 – E9.6)

| Walkthrough | RFC-0002 phase | What it shows |
|---|---|---|
| [`walkthrough_mcp_server.py`](walkthrough_mcp_server.py) | E9.3 (MCP) | Exercises all 6 MCP tools (`list_scenarios`, `get_scenario_claim`, `verify_proof`, `canonicalize_value`, `read_proof_index`, `run_scenario`) through FastMCP's in-process `call_tool` path. Demonstrates the AI-agent interop surface (Claude Code / Cursor / Cline). |
| [`walkthrough_http_api.py`](walkthrough_http_api.py) | E9.4 (HTTP REST) | Drives every HTTP endpoint (`/health`, `/version`, `/scenarios`, `/scenarios/{name}/claim`, `/canonicalize`, `/verify`, `/proofs/index`, `/openapi.json`) via `fastapi.testclient.TestClient`. Demonstrates the service-style interop surface (Kubernetes / API-gateway / curl). |
| [`walkthrough_cloudevents.py`](walkthrough_cloudevents.py) | E9.5 (CloudEvents) | Wraps a real shipped proof in a CloudEvents 1.0 envelope, serializes for transit, unwraps on the consumer side, and asserts the verification surface is preserved byte-for-byte. Demonstrates the event-stream interop surface (Kafka / EventBridge / Knative / NATS). |
| [`walkthrough_otel.py`](walkthrough_otel.py) | E9.6 (OTel) | Installs `InMemorySpanExporter` + `InMemoryMetricReader`, exercises `verify_proof_impl` + `canonicalize_value_impl`, and prints the captured spans (`ophamin.proof.verify`, `ophamin.canonical.encode`) + metrics (`ophamin_proofs_verified_total`, `ophamin_canonical_bytes_encoded`). Demonstrates the observability interop surface (Jaeger / Datadog / Prometheus / Grafana). |

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
