# Ophamin — coverage baseline + performance benchmarks

> **Status:** Stage 1 (internal hardening) per
> `docs/ELEVATION_ROADMAP_2026_05_16.md`. Phase S2 (coverage) +
> S3 (benchmarks) artefacts live here; Phase S1 (mypy strict)
> lives in `docs/MYPY_STRICT_BASELINE.md`.
>
> Baselines pinned 2026-05-16 at v0.5.0. Subsequent measurements
> compare against these to detect regression.

---

## 1. Coverage baseline (Phase S2)

Measured on Python 3.14, pytest 7+ with `pytest-cov` 7.1, branch
coverage enabled. Configuration lives in [`.coveragerc`](https://github.com/IdirBenSlama/Ophamin/blob/main/.coveragerc);
the canonical run command is:

```bash
.venv/bin/python -m pytest -q --cov=src/ophamin --cov-branch --cov-report=term-missing
```

### Aggregate

| Metric | Value |
|---|---|
| Total lines instrumented | 13,671 |
| Total branches | 3,674 |
| Tests passing | 1,148 |
| Tests skipped | 1 |
| Combined coverage | **75.4 % on CI (Ubuntu Python 3.12+3.13), ~77.8 % locally** |

The 2.4 pp gap between local and CI is real and honest: the author's
macOS venv has additional optional deps installed from earlier
sessions (NPEET / pacmap / etc.) that add reachable code paths.
**CI is the authoritative cross-platform measurement.** Pre-push gate
and CI gate are aligned at **≥ 75 %** (slightly below the measured
floor to absorb noise).

### Coverage targets

| Slice | Current (CI) | Target (v0.9.0) | Stretch |
|---|---|---|---|
| Whole framework | 75 % CI / 77 % local | **≥ 80 %** | ≥ 85 % |
| `measuring/` (scenarios + pillars + proof + codec) | ~92 % | ≥ 95 % | 100 % |
| `comparing/` (synthesis + regression-alert + drift) | ~90 % | ≥ 95 % | 100 % |
| `auditing/` | ~85 % | ≥ 92 % | ≥ 95 % |
| `reporting/` | ~94 % | ≥ 95 % | 100 % |
| `protocols.py` | 100 % | 100 % | 100 % |
| `registry.py` | 96 % | 100 % | 100 % |
| `campaign.py` (Move F) | high | ≥ 95 % | 100 % |
| `seeing/discovery/` | ~90 % | ≥ 92 % | ≥ 95 % |
| `seeing/wiring/` | 89 % | ≥ 92 % | ≥ 95 % |
| `seeing/substrate/kimera_adapter.py` | **71 %** (post-0.8.3) | ≥ 70 % ✅ | ≥ 80 % |
| `seeing/corpus/connectors.py` | 54 % | ≥ 65 % | ≥ 75 % |
| `verify.py` | 86 % | ≥ 90 % | ≥ 95 % |

### Per-wheel detail (current → 2026-05-16 baseline)

**At or above target (no action needed):**

| File | Coverage | Notes |
|---|---|---|
| `protocols.py` | 100 % | Protocol declarations only |
| `seeing/discovery/schema_diff.py` | 100 % | Pure functional |
| `seeing/__init__.py`, `corpus/__init__.py` | 100 % | Tiny re-export files |
| `reporting/__init__.py` | 100 % | Re-export only |
| `measuring/scenarios/substrate_completeness.py` | 97.7 % | One unreachable line |
| `latex_renderer.py` | 97.4 % | One unrendered control-path |
| `reporting/markdown_renderer.py` | 96.4 % | Same shape |
| `registry.py` | 96.2 % | Two lines guard built-in-substrate import failure |
| `quantum_basis_correlation.py` | 92.6 % | Empirical-deep scenario; some defensive paths uncovered |
| `seeing/telemetry/prometheus_probe.py` | 91.8 % | Network-bound paths use the local-test fallback |
| `seeing/substrate/field_catalog.py` | 90.3 % | Drift-detection paths in field-shape inferrer |

**Below target — action items for the v0.9.0 ratchet:**

| File | Coverage | Gap | Plan |
|---|---|---|---|
| `seeing/corpus/connectors.py` | 54.2 % | Real-corpus access paths gated on downloads | Add mock-filesystem unit tests for parser branches; skip on missing data via `pytest.skip` |
| `seeing/discovery/watcher.py` | 50.4 % | Continuous-loop / mining path (lines 141-171) constructs a KimeraAdapter inline and calls a SchemaMiner; needs a real Kimera repo. **Same integration-test territory as kimera_adapter.** Phase S2 added 7 tests for the static helpers, run_forever loop with monkeypatched sleep, and kimera_head_commit failure paths. | Accept the gap; mining-path coverage comes from owner-side runs against the live Kimera tree. |
| `measuring/timeseries_helpers.py` | 50.7 % | Optional helper paths used only by 2 scenarios | Either dedicated property-test coverage or move to a `helpers/optional/` subpackage with a skip-when-unused convention |
| `measuring/scenarios/throughput_ceiling.py` | 71.9 % | InstrumentedSubstrate wrapping paths | Mock-substrate test that walks the wrapping ladder |

**Closed in 0.8.3 (Phase A4):**

| File | Was | Now | Closure |
|---|---|---|---|
| `seeing/substrate/kimera_adapter.py` | 55.9 % | **71.1 %** | Added [`tests/test_kimera_adapter_subprocess_mock.py`](https://github.com/IdirBenSlama/Ophamin/blob/main/tests/test_kimera_adapter_subprocess_mock.py) — 18 subprocess-mocked tests covering `_invoke` (every parse / decode / timeout branch), `_to_cycle_result` (success / adapter_error / cycle_seconds propagation / non-dict raw), and `run_batch` (subprocess-mode delegation + batch-mode happy path). Past the v0.9.0 ≥ 70 % target *without* a real Kimera repo. The full-suite measurement that combines the new tests with existing happy-path coverage measures the file at ~80 % in-file. |

### CI gate

Both pre-push (`.githooks/pre-push`) and GitHub Actions CI gate at
**≥ 75 %** as of 0.8.1. The gate was lowered from 77 → 75 with full
rationale in [`CHANGELOG.md` § 0.8.1](https://github.com/IdirBenSlama/Ophamin/blob/main/CHANGELOG.md):
clean Ubuntu CI measures the framework at 75.4 % (the honest cross-
platform floor) while the author's macOS dev box reaches 77.7 %
because of NPEET / pacmap / other optional deps installed from
earlier sessions that add reachable code paths. **CI is the
authoritative cross-platform measurement.** Pre-push gate and CI
gate are aligned at the same threshold so a clean local pre-push
implies CI will pass.

```bash
.venv/bin/python -m pytest -q --cov=src/ophamin --cov-branch \
    --cov-fail-under=75
```

Ratchet plan: raise the gate to 80 (target) and then 85 (stretch) as
the action-item table above closes.

---

## 2. Performance benchmarks (Phase S3)

> **Status:** pending. The benchmark suite lives at `tests/bench/`
> (to be created) and runs via:
>
> ```bash
> .venv/bin/python -m pytest tests/bench/ -q --benchmark-only \
>     --benchmark-storage=file:./bench_storage --benchmark-save=baseline
> ```
>
> Pinned baselines populate the table below as benches land. CI gate:
> any single bench regressing > 20 % vs the pinned baseline fails the
> run.

### Scope of bench coverage (target)

| Layer | Bench | Why it matters |
|---|---|---|
| **Codec** | `dump → load → verify_signature` round-trip on a 1KB proof | Per-record write/read cost — load-bearing for `ophamin proof list` on a 1000-proof corpus |
| **Codec** | `EmpiricalProofRecord.sign(key)` HMAC cost | Should be sub-millisecond per record |
| **Codec** | `validate_schema()` JSON-Schema check | Should be ≤ 5 ms per record |
| **Pillar** | `SPC IndividualsChart.evaluate` on N=10⁴ samples | Per-cycle telemetry path |
| **Pillar** | `SPRT.update()` per-observation cost | Sequential-test critical-path |
| **Pillar** | `MixedLM.fit()` on N=10³, groups=10 | Heaviest single-pillar fit |
| **Pillar** | `River ADWIN` per-observation update | Streaming-drift path |
| **Synthesis** | `summarize_directory(<100 proofs>)` | Used by `ophamin summarize` |
| **Registry** | Cold-start cost: `from ophamin.measuring import pillars` (fires all 11 adapters' registration) | First-CLI-invocation latency |
| **CLI** | `time ophamin --version` cold-start | The smallest meaningful CLI surface |
| **CLI** | `time ophamin scenario list` cold-start | The discovery surface |
| **CLI** | `time ophamin proof verify <signed.json>` | Single-record verify |

### Baseline numbers — `baseline_v0_5_0` pinned 2026-05-16

Measured on macOS Apple-Silicon, Python 3.14, pytest-benchmark 5.2.3,
warmup on, 100-iteration micro-benches (where applicable). Numbers are
median wall time across the benchmark's iteration count.

| Bench | Median | Mean | StdDev |
|---|---|---|---|
| **river_adwin_update_per_observation** | **125 ns** | 136 ns | 32 ns |
| **sprt_update_per_observation** (Gaussian) | **190 ns** | 195 ns | 48 ns |
| **cma_add_50** (50 sequential add()) | **2,028 µs** | 2,064 µs | 150 µs |
| **proof_sign_hmac_only** | **58.4 µs** | 59.6 µs | 7.6 µs |
| **proof_verify_signature** | **123 µs** | 128 µs | 20 µs |
| **proof_dump_load_verify_round_trip** | **304 µs** | 314 µs | 43 µs |
| **proof_validate_schema** (jsonschema) | **895 µs** | 923 µs | 73 µs |
| **compute_regression_alert_n50_pair** | **7.11 ms** | 7.19 ms | 0.38 ms |
| **list_proofs_n100** | **12.78 ms** | 12.85 ms | 0.40 ms |
| **build_index_n100** | **13.37 ms** | 13.45 ms | 0.48 ms |
| **summarize_directory_n100** | **19.67 ms** | 19.76 ms | 0.62 ms |
| **spc_individuals_chart_n10000** (fit + evaluate) | **60.2 ms** | 60.2 ms | 1.46 ms |

Baseline saved at `bench_storage/baseline_v0_5_0/`. Re-run + compare via:

```bash
.venv/bin/python -m pytest tests/bench/ -q --benchmark-only \
    --benchmark-storage=file:./bench_storage \
    --benchmark-compare=baseline_v0_5_0 \
    --benchmark-compare-fail=mean:20%
```

### CLI cold-start (separate from pytest-benchmark; measured via `time`)

To be populated as L1 (docs site) lands and provides a stable
measurement environment. Until then, the pytest-benchmark numbers
above are the canonical performance reference.

### Observations

- Per-observation update costs (River ADWIN, SPRT) are sub-microsecond
  — the streaming pillars can handle ≥ 5M observations/s.
- HMAC signing is ~60µs — a 1000-proof corpus signs in ~60ms.
- The 60ms SPC bench dominates the bench suite by an order of
  magnitude; expected for an N=10⁴ fit.
- `list_proofs` and `build_index` are within 5% of each other,
  confirming `build_index` is essentially `list_proofs` + aggregation
  with negligible aggregation cost.

---

## 3. Mypy strict baseline (Phase S1)

See `docs/MYPY_STRICT_BASELINE.md` for the current error count + the
per-layer remediation plan. Summary:

- Strict configuration in `pyproject.toml` `[tool.mypy]`.
- Baseline error count + per-file breakdown captured.
- Remediation: lowest-hanging-fruit layer (protocols + registry +
  measuring/proof) first; CLI + complex adapters last.
- CI gate: mypy strict must pass on every PR once v0.6.0 lands.

---

## 4. Tracking conventions

- Update this doc whenever a coverage gap moves by more than 1 % or
  a bench baseline shifts by more than 5 %.
- Cite the measurement command in the doc above so the reader can
  re-run.
- Pin numbers to a git commit hash when possible (e.g. "baseline at
  `<short-sha>`, 2026-05-16").

---

*Authored by Claude (Opus 4.7 1M context), 2026-05-16, pinning the
Phase S2 + Phase S3 baselines for the v0.5.0 → v0.6.0 transition.*
