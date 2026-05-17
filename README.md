# Ophamin

[![CI](https://github.com/IdirBenSlama/Ophamin/actions/workflows/ci.yml/badge.svg?branch=main)](https://github.com/IdirBenSlama/Ophamin/actions/workflows/ci.yml)
[![Audit](https://github.com/IdirBenSlama/Ophamin/actions/workflows/audit.yml/badge.svg?branch=main)](https://github.com/IdirBenSlama/Ophamin/actions/workflows/audit.yml)
[![Python](https://img.shields.io/badge/python-3.12%20%7C%203.13-blue.svg)](https://github.com/IdirBenSlama/Ophamin/blob/main/pyproject.toml)
[![Version](https://img.shields.io/badge/version-0.8.0-blue.svg)](https://github.com/IdirBenSlama/Ophamin/releases)
[![License](https://img.shields.io/badge/license-Apache--2.0-blue.svg)](LICENSE)
[![Tests](https://img.shields.io/badge/tests-1223%2B%20passing-brightgreen.svg)](https://github.com/IdirBenSlama/Ophamin/actions/workflows/ci.yml)
[![mypy](https://img.shields.io/badge/mypy-strict%20%E2%9C%93-blue.svg)](docs/MYPY_STRICT_BASELINE.md)
[![Schemas](https://img.shields.io/badge/schemas-versioned-blueviolet.svg)](SCHEMAS.md)

**An empirical observatory wrapped around a substrate under test.**

Ophamin is the apparatus through which a complex substrate (Kimera-SWM
today, anything implementing the `SubstrateUnderTest` protocol tomorrow)
becomes legible. The name is the angelic order **Ophanim** — *wheels within
wheels, covered with eyes* (Ezekiel 1:18). Architecturally, Ophamin is a
*dyson sphere* around the substrate: the substrate sits at the centre
emitting; Ophamin envelops, senses, measures, audits, instruments, reports
— and returns signed, content-addressed, falsifiable artefacts.

It is **independent of Kimera-SWM** — nothing under `src/ophamin/` imports
Kimera except the `KimeraAdapter` plug-in — but it is **built for
Kimera**: the thing it tests slots in through one adapter, and a
`MockSubstrate` lets the whole framework run and be verified without
Kimera present.

---

## The architecture — six wheels in two concentric triads

### Outer triad — *empirical observation*

| Wheel | What it observes | Lives in |
|---|---|---|
| **`seeing/`** | how the substrate is sensed: substrate adapter, corpus connectors, auto-discovery of field schema | `src/ophamin/seeing/` |
| **`measuring/`** | pre-registered falsifiable claims + plug-in statistical pillars | `src/ophamin/measuring/` |
| **`comparing/`** | cross-commit drift detection over signed proof records | `src/ophamin/comparing/` |

### Inner triad — *engineering observation*

| Wheel | What it observes | Lives in |
|---|---|---|
| **`instrumenting/`** | runtime cost: per-cycle wall-time, CPU, RSS, threads, GPU; subprocess-inclusive via background-thread sampler | `src/ophamin/instrumenting/` |
| **`auditing/`** | code structure: orchestrates `ruff`, `bandit`, `mypy`, `vulture`, `radon`, `pip-audit` as audit pillars | `src/ophamin/auditing/` |
| **`reporting/`** | renders every record as academic-grade output: HTML / Markdown / LaTeX with matplotlib charts | `src/ophamin/reporting/` |

### Cross-cutting

| | What | Lives in |
|---|---|---|
| **`inspecting/`** | generic per-primitive inspector — scales from hand-rolled scenarios to any catalogued substrate primitive | `src/ophamin/inspecting/` |
| **`interop/`** | export to standard formats: **SARIF 2.1.0** (audit → VS Code / GitHub Code Scanning), **JUnit XML** (proof → CI), **MLflow** (proof+audit → tracking server), **CycloneDX 1.5** (SBOM → security tooling) | `src/ophamin/interop/` |
| **`protocols.py`** | first-class plug-in surfaces: `Pillar`, `DatasetConnector`, `SubstrateProbe`, `ScenarioProtocol` | `src/ophamin/protocols.py` |

---

## The six analytic pillars (O · F · A · M · I · N)

The `measuring/` ring's statistical machinery. Every pillar is **backed by
a mature, battle-tested library** — not a from-scratch implementation. The
framework's own code is the *orchestration* that wires those libraries to
a substrate and to each other.

| Pillar | Name | Backing library | Module |
|---|---|---|---|
| **O** | Observability | **scipy** (chi-squared GOF) + **river** (streaming drift detectors); Shewhart SPC validated against Montgomery's published constant tables | `ophamin.measuring.pillars.observability` |
| **F** | Formal provenance | **prov** (W3C PROV-O / PROV-JSON) + **MLflow** (run tracking) + **DVC** (dataset versioning) | `ophamin.comparing.provenance` |
| **A** | Adaptive testing | SPRT / mixture-SPRT validated against the published Wald & Howard closed forms | `ophamin.measuring.pillars.adaptive` |
| **M** | Mixed-effects | **statsmodels** — `MixedLM` (random-intercept LMM) and `OLS` + `anova_lm` (interaction tests) | `ophamin.measuring.pillars.effects` |
| **I** | Iterative synthesis | **statsmodels** — `stats.meta_analysis.combine_effects` (fixed + DerSimonian-Laird random effects) | `ophamin.measuring.pillars.synthesis` |
| **N** | N-fold robustness | **scikit-learn** — `KFold`, `ShuffleSplit`, `GroupKFold`, `GroupShuffleSplit` | `ophamin.measuring.pillars.robustness` |

Plus three **substrate-specific cognitive diagnostics** (`ophamin.measuring.pillars.diagnostics`):

- **Anticipatory Failure Classification** — split conformal prediction via **MAPIE**, with finite-sample coverage guarantees.
- **Cognitive Inertia Metrics** — substrate's resistance to updating on valid new evidence.
- **Oracle Kernel-Coupling Diagnostic** — sweeps the entropy coefficient at collapse-prone cells.

Config composition / merge / dotted access is delegated to **OmegaConf**.

---

## Three experimentation tiers — 19 shipped scenarios

The original six scenarios (Scientific / Engineering / Philosophical
tiers) have been joined by an **empirical-deep tier** (Family A–V in
Kimera's `EMPIRICAL_VALIDATION.md` — substrate-physics scenarios) and a
**measurement-machinery tier** (validation of the upstream libraries
Ophamin itself depends on). The discipline is unchanged: every scenario
captures a pre-registered falsifiable claim before the run and emits a
signed 9-section Empirical Proof Record.

### Scientific tier — claims about substrate behaviour

| Scenario | Corpus | Target | Pre-registered claim | Latest live verdict |
|---|---|---|---|---|
| Concentrated Immune Siege | offensive-security | `gwf` + `entity` | GWF false-positive rate on benign-labelled prompts ≤ 10% | VALIDATED 3.2% (CI 2.0%–5.1%) |
| Rosetta Scaling | FLORES-200 sentence-aligned parallel text | `rosetta` | Canonical-agreement across 10 languages ≥ 80% | REFUTED 0.0% (CI 0%–16%) |
| Organizational Dissonance | Enron email (~500k records) | `entity` | Dissonance fires on ≥ 90% of GWF-cleared cycles | VALIDATED 97.4% (CI 96.2%–98.3%) |
| Logic-Topology Siege | Linux kernel commits (~1.4M) | `entity` | Walker sustained-traversal rate ≥ 60% | REFUTED 39.6% (CI 36.0%–43.4%) |
| Interface Contract Stability | Kimera substrate self-introspect | (structural) | OrchestratorResult field-contract violations ≤ 2 per probe | first signed proof landed |
| Substrate Completeness | Kimera repo structural walk | (structural) | Aggregate orphan rate ≤ 20% (canonical-name files in `kimera_swm/`) | VALIDATED 8.05% (Wilson CI [0.0555, 0.1153]) |
| Memory-As-Deformation | captured Takwin trajectory | `entity` | Concept-set Jaccard floor across re-exposure pairs ≥ 0.80 | VALIDATED 1.0000 (Round M) |

### Engineering tier — claims about substrate cost

| Scenario | Corpus | Target | Pre-registered claim | Latest live verdict |
|---|---|---|---|---|
| Throughput Ceiling | mixed text load | `entity` (wrapped in `InstrumentedSubstrate`) | p95 per-cycle wall-time ≤ 4.0 s | VALIDATED 2.357s |

### Philosophical tier — claims about substrate self-model

| Scenario | Corpus | Target | Pre-registered claim | Latest live verdict |
|---|---|---|---|---|
| Self-Reference | self-referential + Enron neutral | `entity` (paired) | Cohen's d ≥ 0.30 (self-ref dissonance > neutral) | REFUTED d = −0.359 |

### Empirical-deep tier — substrate-physics scenarios

These scenarios target Kimera's prime apparatus + Φ + cross-channel
behaviour. They mirror Family A–V claims in Kimera's
`EMPIRICAL_VALIDATION.md` and run against captured trajectories.

| Scenario | Probes | Pre-registered claim | Latest verdict |
|---|---|---|---|
| Bayesian Φ Posterior | Φ trajectory | HDI contraction ratio < theoretical-frequentist bound | VALIDATED (Family T) |
| Causal Discovery | multi-channel trajectory (Tigramite PCMCI) | ≥ 1 directed link recovered above α level | VALIDATED 32 links (Family F) |
| Cross-Channel Mutual Information | multi-channel trajectory (pyitlib + ennemi) | ≥ 1 pair above 0.05-nat floor | VALIDATED 8/8 pairs (Family T) |
| Prime Structure | 200-cycle prime trajectory | concept-Jaccard floor ≥ 0.80, F.1.1 divisibility 100% | VALIDATED both (Family U Round G) |
| Prime Factorization | 200-cycle prime trajectory | p_identity invariance ≥ 99% | VALIDATED 100% (Family U Round H) |
| Prime Ecosystem | 200-cycle prime trajectory | Alexandria fused-key persistence ≥ 5 keys at ≥ 90% cycles | VALIDATED 12 keys (Round I) |
| Prime Direct Lookup | 200-cycle prime trajectory | direct ArachneProtocol lookup p_thermo ≥ 99% prime | VALIDATED 100% (Round J) |
| Prime Cross-Instance | N fresh Takwin processes | cross-instance p_identity invariance ≥ 99% | VALIDATED 100% (Round K) |
| Quantum Basis Correlation | trajectory partitioned by stimulus class | content-class effect ≥ 15pp difference | VALIDATED 39pp (Round J) |

### Measurement-machinery tier — validation of upstream libraries

| Scenario | What it validates | Library | Latest verdict |
|---|---|---|---|
| CRDT Laws | Yjs CRDT convergence | pycrdt + y-py | VALIDATED 100/100 sequences |

A REFUTED verdict is the framework working — it surfaces a real
architectural gap, not a failure to measure. Per-tier verdict trail
lives in `proofs/` (content-addressed JSON + Markdown twins) and in
Kimera's `EMPIRICAL_VALIDATION.md` family entries.

Each scenario produces a signed **9-section Empirical Proof Record**:
identity, claim, pre-registration, data, evidence, verdict, reproduction,
provenance, signature. Content-addressed (proof-id is the SHA-256 of the
body), HMAC-signed, JSON-serialized, ready for export via `interop/` to
any traditional engineering tool.

---

## Quickstart

```bash
git clone https://github.com/IdirBenSlama/Ophamin.git
cd Ophamin
python3.12 -m venv .venv             # Python 3.10+ required; 3.12 recommended

# Minimal install — runs MockSubstrate scenarios + the analytic pillars.
.venv/bin/python -m pip install -e ".[dev,viz]"

# Full install — everything Ophamin can do against Kimera, including the
# audit pillars (ruff/bandit/mypy/vulture/radon/pip-audit), profile tools
# (py-spy/memray), telemetry consumer (prometheus_client + opentelemetry),
# and SBOM exporter (cyclonedx).
.venv/bin/python -m pip install -e ".[dev,viz,audit,profile,telemetry,well,hydra]"
# or shorthand:
.venv/bin/python -m pip install -e ".[all,dev]"

.venv/bin/python -m pytest -q                      # 842+ tests, all green
.venv/bin/python examples/run_mock_experiment.py   # end-to-end, no Kimera needed
```

If you skip the `[audit]` extra, `ophamin audit` will report each missing
pillar as `status="unavailable"` with an install hint — loud failure, not
silent skip. To verify all pillars resolve correctly:

```bash
.venv/bin/python -m ophamin.cli audit src/ophamin \
  --pillars=ruff,bandit,mypy,vulture,radon,pip_audit \
  --out-dir /tmp/audit-self --timeout 120
```

`run_mock_experiment.py` runs a 4×2 parameter sweep on the `MockSubstrate`,
applies all six pillars and the three diagnostics, and prints what the
lineage store recorded. Or use the CLI:

```bash
.venv/bin/python -m ophamin.cli demo
.venv/bin/python -m ophamin.cli sweep config/experiment_vars.yaml
.venv/bin/python -m ophamin.cli lineage --list
```

MLflow logs every run under `<lineage_root>/mlruns` — point the MLflow UI
there to browse params, metrics and the manifest / provenance artifacts.

---

## CLI surface — what you can run today

```bash
# core entry points
ophamin demo                                  # end-to-end mock experiment, no Kimera needed
ophamin run <config.yaml>                     # run one experiment from a base config
ophamin sweep <experiment.yaml>               # parent + children parameter sweep
ophamin probe-kimera <kimera-repo>            # self-test the Kimera adapter
ophamin lineage --list                        # list recorded runs
ophamin verify                                # install self-check + CI fast-fail gate

# seeing/ — substrate-discovery surface
ophamin discover <kimera-repo>                # mine Kimera's field-schema (one-shot)
ophamin discover-fields <kimera-repo>         # catalogue OrchestratorResult fields
ophamin discover-diff <a.json> <b.json>       # structural diff between two schema documents
ophamin watch <kimera-repo>                   # many-small-eyes: continuous re-discover + diff + drift
ophamin inventory <kimera-repo>               # primitive inventory (Ophamin-side catalog)
ophamin wiring <kimera-repo> [--all]          # WiringProbe: orphan / WIRE_CANDIDATE / wired classification
ophamin scrape <kimera-repo>                  # PrometheusScrapeProbe — consume Kimera's /metrics

# comparing/ — Layer C drift detection
ophamin drift-report                          # cross-commit drift over signed proofs
ophamin drift-detect --stream <s> --detector <d>   # River-backed streaming drift on Φ / walker-halt

# auditing/ — engineering-debt detection
ophamin audit <path>                          # orchestrate static-analysis pillars; signed audit record

# inspecting/ — per-primitive profile
ophamin inspect <kimera-repo> <primitive>     # static introspection + optional dynamic
ophamin inspect-all <kimera-repo>             # survey every catalogued primitive

# reporting/ — multi-format academic output
ophamin report <record.json> --format html|markdown|latex

# interop/ — standard-format export
ophamin export <record.json> --format sarif|junit-xml|mlflow|cyclonedx
```

---

## Pointing it at Kimera-SWM

```bash
# self-test the adapter first — it reports the real Takwin.run signature
.venv/bin/python -m ophamin.cli probe-kimera "/path/to/Kimera_SWM"
```

Then set `substrate.kind: kimera` and `substrate.kimera_repo: <path>` in
a config and run `ophamin sweep` / `ophamin run` exactly as with the
mock. `KimeraAdapter` (in `seeing/substrate/`) is the central
Kimera-coupling point — it adapts the substrate-under-test surface
without leaking Kimera types into `measuring/` or `comparing/`. A
small number of discovery / wiring / telemetry helpers in `seeing/`
(`seeing/discovery/`, `seeing/wiring/`, `seeing/telemetry/`) also
reach into Kimera shapes — these are *seeing-wheel-internal* probes,
the same conceptual layer as `KimeraAdapter` itself. The
`MockSubstrate` makes every wheel runnable + testable on its own.

The four scientific scenarios + the engineering and philosophical scenarios
all bring their own corpus connectors; running them needs the corpora
downloaded under `data/raw/` (Enron from the CMU release, FLORES-200 from
the NLLB release, offensive-security as a curated bundle, Linux kernel
as a blobless bare clone — see `Makefile` targets for the canonical
fetch commands).

---

## Repository structure

```
Ophamin/
├── pyproject.toml                         # package + library-backed dependencies
├── requirements.txt                       # runtime deps (mirrors pyproject)
├── requirements-dev.txt                   # all optional extras + dev tools
├── README.md                              # this file
├── LICENSE                                # Apache-2.0
├── NOTICE                                 # required-attributions companion to LICENSE
├── Makefile                               # install / test / demo / sweep / probe-kimera
├── config/                                # base + sweep config files
│   ├── base_config.yaml
│   └── experiment_vars.yaml
├── docs/                                  # scenario authoring + Tier-2 telemetry proposal
│   ├── SCENARIO_AUTHORING.md
│   └── TIER_2_TELEMETRY_PROPOSAL.md
├── src/ophamin/
│   ├── seeing/                            # Wheel 1 — sense Kimera + the world
│   │   ├── substrate/                       SubstrateUnderTest, MockSubstrate, KimeraAdapter,
│   │   │                                    field_catalog
│   │   ├── corpus/                          Enron, Linux, FLORES, offensive-security, financial, The Well
│   │   ├── discovery/                       Layer A schema mining + watcher + inventory
│   │   ├── telemetry/                       PrometheusScrapeProbe (consumes Kimera's /metrics)
│   │   └── wiring/                          WiringProbe — orphan / WIRE_CANDIDATE / wired classifier
│   ├── measuring/                         # Wheel 2 — pre-registered measurement
│   │   ├── proof/                           the 9-section Empirical Proof Record
│   │   ├── scenarios/                       19 scenarios across 5 tiers + authoring helpers
│   │   ├── metrics/                         three-tier metric model
│   │   ├── pillars/                         O · F · A · M · I · N (statsmodels / scikit-learn / scipy / …)
│   │   └── *_helpers.py                     analytic / bayesian / causal / graph / sat_smt / timeseries
│   ├── comparing/                         # Wheel 3 — cross-commit retrospection
│   │   ├── drift/                           Layer C drift detection (delta_report, proof_index)
│   │   ├── drift_detection/                 River-backed streaming detectors (ADWIN/KSWIN/PageHinkley)
│   │   ├── provenance/                      W3C PROV-O + MLflow + DVC
│   │   ├── orchestration/                   parent/child experiment runs
│   │   └── crdt_state.py                    Yjs / y-py CRDT state probing
│   ├── instrumenting/                     # Wheel 4 — runtime resource cost
│   │   ├── wrapper.py                       InstrumentedSubstrate
│   │   ├── periodic_sampler.py              background-thread subprocess sampler
│   │   └── resource_metrics.py              per-cycle CPU / RSS / threads / GPU
│   ├── auditing/                          # Wheel 5 — static-analysis orchestrator
│   │   └── pillars/                         ruff / bandit / mypy / vulture / radon / pip-audit
│   │                                        + deptry / fawltydeps / interrogate / pylint / refurb / prospector
│   ├── reporting/                         # Wheel 6 — HTML / Markdown / LaTeX renderers + charts
│   ├── inspecting/                        # per-primitive profile (composes the wheels)
│   │                                        catalog + inspector + locator + primitive_profile
│   ├── interop/                           # SARIF / JUnit XML / MLflow / CycloneDX exporters
│   ├── protocols.py                       # plug-in protocols (Pillar / DatasetConnector / …)
│   ├── verify.py                          # install self-check + CI fast-fail gate
│   └── cli.py                             # the unified `ophamin` command-line
├── tests/                                 # 842+ tests, all green
└── examples/                              # one runner per scenario + mock end-to-end
```

---

## Dependencies

Core dependencies (always installed; see `requirements.txt`):

```
numpy, scipy, pandas, pyyaml, scikit-learn, statsmodels, mapie, river,
prov (+ lxml, rdflib), omegaconf, mlflow, dvc, psutil
```

Optional extras (`pip install 'ophamin[<extra>]'`; combined in `requirements-dev.txt`):

| Extra | Adds | Used by |
|---|---|---|
| `viz` | `matplotlib` | `reporting/` charts + `synthesis/` cumulative-meta-analysis plots |
| `audit` | `ruff`, `bandit`, `mypy`, `vulture`, `radon`, `pip-audit`, `deptry`, `fawltydeps`, `interrogate`, `pylint`, `refurb`, `prospector` + `cyclonedx-python-lib` | `auditing/` orchestrated pillars (twelve tools) |
| `telemetry` | `opentelemetry-api`, `opentelemetry-sdk`, `prometheus_client` | `instrumenting/` + `seeing/telemetry/` PrometheusScrapeProbe |
| `profile` | `py-spy`, `memray` | `instrumenting/` deep profilers (sampling + memory flamegraphs) |
| `well` | `h5py` | `seeing.corpus.TheWellCorpus` for physics-simulation HDF5 datasets |
| `hydra` | `hydra-core` | Hydra-driven entry points (OmegaConf is core) |
| `analytic` | `pingouin`, `POT`, `infomeasure`, `umap-learn` | `measuring/` effect-size + Wasserstein + entropy/MI |
| `causal` | `dowhy`, `econml`, `causalml`, `tigramite` | `measuring/` causal inference + PCMCI discovery |
| `tda` | `ripser`, `scikit-tda`, `gudhi` | `seeing/` + `measuring/` topological data analysis |
| `timeseries` | `darts`, `tsfresh`, `pyod`, `stumpy`, `statsforecast` | drift / forecasting / motif-discord |
| `bayesian` | `arviz`, `pymc`, `numpyro` | `measuring/` Bayesian PPL (Family T posteriors) |
| `property_test` | `hypothesis`, `schemathesis`, `coverage` | CRDT-law tests + API contract testing |
| `acceleration` | `polars`, `duckdb`, `numba` | scenario speed-ups when stream sizes grow |
| `sat_smt` | `z3-solver`, `cvc5` | `measuring/` formal verification |
| `graph` | `igraph` | `measuring/` graph algorithms |
| `crdt` | `pycrdt`, `y-py` | `comparing/crdt_state.py` distributed-state probing (cross-check oracle) |
| `conformal` | `crepes`, `puncc` | `measuring/` conformal prediction |
| `infotheory` | `pyitlib`, `ennemi` | `measuring/cross_channel_mutual_information` MI cross-check |
| `dev` | `pytest` | running the test suite |
| `all` | every optional extra | full local install |

A missing optional dependency raises a clear, named error — the framework
never silently skips a requested output.

> Note: `confseq` (the authoritative anytime-valid-inference library) has
> no Python 3.14 wheel; the mSPRT module is instead validated against the
> published Howard et al. closed form.

---

## Design notes

- **Library-backed, not from-scratch.** Each pillar delegates to a mature
  library; the framework's own code is orchestration. The test suite proves
  this — it cross-checks Ophamin's output against scikit-learn, statsmodels,
  MAPIE and prov driven directly.
- **Wrap, don't rewrite.** The `auditing/` wheel orchestrates ruff /
  bandit / mypy / vulture / radon / pip-audit; the `interop/` wheel emits
  SARIF / JUnit XML / MLflow / CycloneDX. Each tool / format is a mature
  external dependency — Ophamin is the conductor.
- **Independent of Kimera.** Nothing under `src/ophamin/` imports Kimera
  except `seeing/substrate/kimera_adapter.py`. The `MockSubstrate` makes
  the framework fully runnable and testable on its own.
- **Loud failure, no fabrication.** A failed cycle is recorded as a
  failure with its real error; a misconfigured adapter raises; a missing
  audit tool reports `status="unavailable"` with a clear install hint —
  never silently swallowed.
- **Signed and content-addressed.** Every record (proof + audit) is
  HMAC-SHA256 signed and content-addressed (the record-id is the SHA-256
  of its body sections). The `interop/` exporters preserve the original
  Ophamin signature in their target format's properties bag so downstream
  consumers can trace back.
- **Pre-registration discipline.** Every scenario captures its config +
  data hashes + analysis plan *before* the substrate runs. A REFUTED
  verdict means the substrate failed to meet a threshold the framework
  committed to before seeing the result — that's the point.
- **Three experimentation tiers, one shape.** Scientific / engineering /
  philosophical scenarios all share the `Scenario` / `ScenarioScore` /
  signed proof-record discipline. They differ in what fields they read
  from `CycleResult.raw` and how they pre-register the falsifiable
  threshold — not in their epistemic shape.

---

## Authoring a new scenario

See [`docs/SCENARIO_AUTHORING.md`](docs/SCENARIO_AUTHORING.md). The
short version: subclass `Scenario`, name a `corpus_name` + `target` +
`build_claim()` + `score()`. Use the helpers in
`ophamin.measuring.scenarios.helpers` for shape-aware extraction,
Wilson CIs, inconclusive guards, and distribution stats. New scenarios
land in ~80 LOC.

## Tier-2 Kimera-side telemetry hooks

See [`docs/TIER_2_TELEMETRY_PROPOSAL.md`](docs/TIER_2_TELEMETRY_PROPOSAL.md).
The proposal describes per-cycle OpenTelemetry hooks Kimera could add to
unlock substrate-internal span-tree attribution. Owner-gated per Kimera's
Tier-1/2/3 fix policy.

## Strategic context — what Ophamin currently observes, what it doesn't

Two reference documents capture where Ophamin sits today and where the
v0.2 reframe is pointed:

- [`docs/KIMERA_OBSERVATIONAL_SURFACE_2026_05_15.md`](docs/KIMERA_OBSERVATIONAL_SURFACE_2026_05_15.md)
  — measurement-coverage analysis. Names the nine substrate strata
  Ophamin v0.2 should reach (cognitive / interface / transport /
  persistence / reconciliation / temporal / security / telemetry /
  lifecycle) and the four new measuring pillars + three new auditing
  pillars proposed to support them.
- [`docs/PLUGIN_CATALOG_2026_05_15.md`](docs/PLUGIN_CATALOG_2026_05_15.md)
  — Kimera-aspect × Ophamin-wheel matrix mapping ~50 open-source tools
  to gaps in the framework, with a 12-tool priority shortlist.

Both are reading material before scoping new work. Implementation
sequence is owner-gated.
