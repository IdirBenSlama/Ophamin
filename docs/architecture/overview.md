# Architecture overview

Ophamin's architecture is **six wheels in two concentric triads**, plus
cross-cutting layers for inspection + interop. The two triads sit at
different layers of observation:

```
┌─────────────────────────────────────────────────┐
│  OUTER TRIAD — empirical observation            │
│                                                 │
│    seeing     →    measuring    →    comparing  │
│  (discover)      (run scenarios)   (drift)      │
│                                                 │
│  ┌─────────────────────────────────────────┐    │
│  │  INNER TRIAD — engineering observation  │    │
│  │                                         │    │
│  │  instrumenting  →  auditing  →  reporting│   │
│  │  (resource)       (static)     (render) │    │
│  │                                         │    │
│  └─────────────────────────────────────────┘    │
│                                                 │
└─────────────────────────────────────────────────┘
```

The outer triad answers *"what is the substrate doing?"*; the inner
triad answers *"what is the substrate costing?"*. Each wheel is a
Python package under `src/ophamin/`; cross-cutting layers
(`inspecting`, `interop`, `application`) sit alongside.

## The six wheels

| Wheel | What it owns | Backed by |
|---|---|---|
| `seeing` | corpus connectors + substrate adapters + field-schema discovery + Prometheus / wiring probes | scikit-learn, h5py, pandas |
| `measuring` | the 32 scenarios + the six pillars (O / F / A / M / I / N) + the signed proof codec | statsmodels, mapie, river, scipy, numpyro, pymc |
| `comparing` | cross-commit drift detection + W3C PROV-O lineage + regression alerts | prov, mlflow, dvc, river |
| `instrumenting` | per-cycle CPU / RSS / page-fault sampling + OTEL traces + flamegraph capture | psutil, opentelemetry, py-spy, memray |
| `auditing` | orchestrated static analyses (ruff / bandit / mypy / pip-audit / radon / vulture / interrogate) + SARIF export | ruff, bandit, mypy, vulture, radon, pip-audit, cyclonedx-python-lib |
| `reporting` | render proof + audit + campaign records to Markdown / HTML / LaTeX | matplotlib |

## The six pillars (inside `measuring/pillars/`)

| Letter | Pillar | Library |
|---|---|---|
| O | observability (SPC / drift) | scipy + river |
| F | feasibility (causal + treatment effects) | dowhy + econml |
| A | adaptive (SPRT, sequential testing) | scipy |
| M | mixed-effects modelling | statsmodels |
| I | iterative synthesis (cumulative meta-analysis) | statsmodels |
| N | n-fold robustness (cross-validation) | scikit-learn |

Each pillar's pattern: **wrap one mature upstream library, attribute
explicitly, never reinvent**.

## The five experimentation tiers

Scenarios are grouped by what their claim is about:

- **Scientific** — substrate *behaviour*
- **Engineering** — substrate *cost*
- **Philosophical** — substrate *self-model*
- **Measurement-machinery** — the *measurement apparatus*
- **Structural** — substrate *shape*

See [Write a new scenario](../tutorials/write-a-scenario.md) for the
authoring path.

## The signed-record contract

Every measurement scenario produces an **EmpiricalProofRecord** —
nine sections, content-addressed via `proof_id` (SHA-256 over canonical
body), HMAC-signed via `signature`. The framework's load-bearing
promise is on the wire format:

- **Minor schema bumps** add fields only; never remove or rename
- **Major schema bumps** ship migration scripts + a deprecation cycle
- **Canonical signing form** is JSON `sort_keys=True` with
  `(",", ":")` separators — bit-stable across Python 3.10–3.14 and
  macOS / Linux / Windows

See [the schemas reference](../reference/schemas.md) for the full
catalogue.

## The plug-in registry

Four protocols define the plug-in surface (Move A):

- `Pillar` — a statistical / analytical method (six built-in, more via
  `register_pillar`)
- `ScenarioProtocol` — a scenario class (19 built-in)
- `DatasetConnector` — a corpus connector (Enron, Linux, Flores,
  cyber-payloads, financial, the_well)
- `SubstrateProbe` — a substrate adapter (MockSubstrate, KimeraAdapter)

Third-party code registers under these protocols via the registry
functions in `ophamin.registry` + per-wheel `register_*` helpers.

## Deeper reading

The audit + intent-vs-reality documents capture the design's actual
shape at each maturity step:

- [Architecture extended audit](../ARCHITECTURE_EXTENDED_AUDIT_2026_05_16.md)
  — the 16-deficit audit driving the elevation roadmap
- [Architecture intent vs reality](../ARCHITECTURE_INTENT_VS_REALITY_2026_05_16.md)
  — per-wheel intent-vs-reality narrative
- [Elevation roadmap](../ELEVATION_ROADMAP_2026_05_16.md) — the
  4-stage plan (S1–S6 internal hardening + L1–L6 external legitimacy)
- [Plugin catalog](../PLUGIN_CATALOG_2026_05_15.md) — what plugs in
  where, with current count + version requirements

## Code map

```
src/ophamin/
├── seeing/
│   ├── corpus/          corpus connectors (6 corpora)
│   ├── discovery/       field-schema mining + diff + watcher
│   ├── substrate/       MockSubstrate + KimeraAdapter + field catalog
│   ├── telemetry/       PrometheusScrapeProbe
│   └── wiring/          WiringProbe (orphan/wire-candidate classification)
├── measuring/
│   ├── pillars/         O / F / A / M / I / N + diagnostics + adaptive + …
│   ├── scenarios/       the 32 scenarios
│   ├── proof/           signed-record codec + JSON Schema
│   └── metrics/         Tier1/2/3 metrics
├── comparing/
│   ├── drift/           cross-commit DriftReport + ProofIndex
│   ├── drift_detection/ streaming drift (River ADWIN)
│   ├── orchestration/   ExperimentRunner (sweep parents + child runs)
│   ├── provenance/      W3C PROV-O + LineageStore + MLflow + DVC
│   ├── crdt_state.py    YDoc cross-backend (pycrdt + y-py)
│   ├── regression_alert.py
│   └── synthesis.py
├── instrumenting/       resource sampling + InstrumentedSubstrate wrapper
├── auditing/            orchestrated static-analysis pillars + signed audit record
├── reporting/           Markdown / HTML / LaTeX renderers + chart helpers
├── inspecting/          per-primitive deep-dive (locator + catalog + inspector)
├── interop/             SARIF / JUnit XML / MLflow / CycloneDX
├── config/              OmegaConf-backed config loading + sweep expansion
├── application/         use-cases that pull from the wheels (Move I)
├── cli.py               the `ophamin` entry point
├── campaign.py          the 6-phase composite-run orchestrator (Move F)
├── registry.py          the 4-Protocol plug-in registry (Move A)
├── protocols.py         the four Protocol declarations (Move A)
└── verify.py            startup health-check
```
