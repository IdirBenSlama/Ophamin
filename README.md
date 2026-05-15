# Ophamin

**An empirical framework for scaling and verifying iterative experimentation.**

Ophamin turns the methodology report *"Scaling and Verifying Iterative
Experimentation"* into running code. It runs experiments against a *substrate
under test*, applies six pillars of statistical and provenance machinery to the
results, and records an auditable lineage trail.

Every pillar is **backed by a mature, battle-tested library** — not a
from-scratch implementation. The framework's own code is the *orchestration*
that wires those libraries to a substrate and to each other; the statistics
themselves come from scikit-learn, statsmodels, MAPIE, river, prov and MLflow.
The test suite cross-checks Ophamin's wrappers against those libraries driven
directly.

It is **independent of Kimera-SWM** — none of the framework imports Kimera —
but it is **built for Kimera**: the thing it tests plugs in through one adapter,
and a `MockSubstrate` lets the whole framework run and be verified without
Kimera present.

---

## The six pillars (O · F · A · M · I · N)

| Pillar | Name | Backing library | Module |
|---|---|---|---|
| **O** | Observability | **scipy** (chi-squared GOF) + **river** (streaming drift detectors); Shewhart SPC validated against Montgomery's published constant tables | `ophamin.observability` |
| **F** | Formal provenance | **prov** (W3C PROV-O / PROV-JSON) + **MLflow** (run tracking) + **DVC** (dataset versioning) | `ophamin.provenance` |
| **A** | Adaptive testing | SPRT / mixture-SPRT validated against the published Wald & Howard closed forms (no single library dominates anytime-valid inference) | `ophamin.adaptive` |
| **M** | Mixed-effects | **statsmodels** — `MixedLM` (random-intercept LMM) and `OLS` + `anova_lm` (interaction tests) | `ophamin.effects` |
| **I** | Iterative synthesis | **statsmodels** — `stats.meta_analysis.combine_effects` (fixed + DerSimonian-Laird random effects) | `ophamin.synthesis` |
| **N** | N-fold robustness | **scikit-learn** — `KFold`, `ShuffleSplit`, `GroupKFold`, `GroupShuffleSplit` | `ophamin.robustness` |

Config composition / merge / dotted access is delegated to **OmegaConf** (the
library underneath Hydra).

Plus three **substrate-specific cognitive diagnostics** (`ophamin.diagnostics`):

- **Anticipatory Failure Classification** — split conformal prediction via
  **MAPIE**, with finite-sample coverage guarantees, plus a three-way
  classifier (success / known failure / OOD anomaly) and the *world-model gap*.
- **Cognitive Inertia Metrics** — a framework-defined metric (no library
  exists): a substrate's resistance to updating on valid new evidence.
- **Oracle Kernel-Coupling Diagnostic** — a framework-defined experiment design:
  sweeps the entropy coefficient at collapse-prone cells to isolate whether a
  collapse is intrinsic behaviour or miscalibrated boundary logic.

Where a pillar is *not* a thin wrapper — SPRT/mSPRT, the Shewhart charts, the
two framework-defined diagnostics — it is because no single library dominates
that method. Those modules are validated against published reference values,
not against the framework's own expectations.

---

## Quickstart

```bash
cd ophamin
python3 -m venv .venv
.venv/bin/python -m pip install -e ".[dev,viz]"
.venv/bin/python -m pytest -q          # 90 tests — statistical core + cross-checks
.venv/bin/python examples/run_mock_experiment.py   # end-to-end, no Kimera needed
```

`run_mock_experiment.py` runs a 4×2 parameter sweep on the `MockSubstrate`,
applies all six pillars and the three diagnostics, and prints what the lineage
store recorded. Or use the CLI:

```bash
.venv/bin/python -m ophamin.cli demo
.venv/bin/python -m ophamin.cli sweep config/experiment_vars.yaml
.venv/bin/python -m ophamin.cli lineage --list
```

MLflow logs every run under `<lineage_root>/mlruns` — point the MLflow UI there
to browse params, metrics and the manifest/provenance artifacts.

---

## Pointing it at Kimera-SWM

The substrate under test is anything implementing `ophamin.substrate.SubstrateUnderTest`.
`KimeraAdapter` is the Kimera implementation — it runs **one cycle per
subprocess** (a fresh interpreter per cycle, the leak-free probe shape) and is
the *only* Kimera-coupled file in the framework.

```bash
# self-test the adapter first — it reports the real Takwin.run signature
.venv/bin/python -m ophamin.cli probe-kimera "/path/to/Kimera_SWM (Spherical Word Memory)"
```

Then set `substrate.kind: kimera` and `substrate.kimera_repo: <path>` in a
config and run `ophamin sweep` / `ophamin run` exactly as with the mock. The
adapter ships an editable runner template; if Kimera's `Takwin` API differs,
`probe-kimera` reports the actual signature so the runner can be corrected.

---

## The catastrophic scenarios

Each scenario binds a real corpus + a Kimera component target + a
**pre-registered falsifiable claim**. The harness runs the corpus through the
substrate, scores the run, and emits a signed 9-section *Empirical Proof
Record* under `proofs/`. The pre-registration is captured *before* the run.
A REFUTED verdict is the framework working — it surfaces a real architectural
debt, not a failure to measure.

| # | Scenario | Corpus | Kimera target | Pre-registered claim | Run example |
|---|---|---|---|---|---|
| 1 | **Concentrated Immune Siege** | offensive-security (deepset + jackhhao + SecLists + …) | `gwf` (direct) + `entity` (Takwin inline) | GWF false-positive rate on benign-labelled prompts ≤ 10% | `examples/run_immune_siege.py` |
| 2 | **Rosetta Scaling** | FLORES-200 sentence-aligned parallel text | `rosetta` (RosettaStele) | Canonical-agreement across 10 languages of the same sentence ≥ 80% | `examples/run_rosetta_scaling.py` |
| 3 | **Organizational Dissonance** | Enron email corpus (~500k CMU emails) | `entity` (Takwin) | On GWF-cleared organisational email, the dissonance machinery fires (≥1 event) in ≥ 90% of cycles | `examples/run_organizational_dissonance.py` |
| 4 | **Logic-Topology Siege** | Linux kernel commit history (~1.4M commits) | `entity` (Takwin) | On GWF-cleared technical-reasoning text, the walker reaches sustained traversal (`halt_mode == 'exhausted'`) in ≥ 60% of cycles | `examples/run_logic_topology_siege.py` |

Each scenario reports its primary observed value with a Wilson 95% confidence
interval, plus a fixed slate of *secondary descriptive evidence* (full halt-
mode distributions, dissonance distributions, GWF block rate, manipulation
rate, …). Secondary evidence is part of the same signed record but is
**never post-hoc claimable** — the primary claim is whatever was
pre-registered before the run.

Run any scenario directly:

```bash
PYTHONPATH=src .venv/bin/python -u examples/run_<scenario>.py
```

Or via the CLI registry:

```bash
.venv/bin/python -m ophamin.cli scenario <scenario-name>
```

---

## Repository structure

```
ophamin/
├── pyproject.toml          # package + library-backed dependencies
├── Makefile                # install / test / demo / sweep / probe-kimera
├── config/
│   ├── base_config.yaml    # the standing configuration
│   └── experiment_vars.yaml# a parameter-sweep definition
├── src/ophamin/
│   ├── metrics/            # the three-tier metric model
│   ├── substrate/          # SubstrateUnderTest + MockSubstrate + KimeraAdapter
│   ├── config/             # OmegaConf-backed config loader + sweep expansion
│   ├── observability/      # O — SPC, SRM (scipy), drift (river)
│   ├── provenance/         # F — PROV-O (prov), lineage (MLflow + DVC)
│   ├── adaptive/           # A — SPRT, mSPRT
│   ├── effects/            # M — mixed-effects + MEA (statsmodels)
│   ├── synthesis/          # I — cumulative meta-analysis (statsmodels)
│   ├── robustness/         # N — cross-validation (scikit-learn)
│   ├── diagnostics/        # anticipatory (MAPIE) / inertia / kernel-coupling
│   ├── orchestration/      # parent/child runs that apply the pillars
│   └── cli.py              # command-line interface
├── tests/                  # pytest suite — cross-checks against every library
└── examples/
    └── run_mock_experiment.py
```

---

## Dependencies

Library-backed pillars mean the framework has real dependencies — installing
them is the point, not a footprint to minimise:

`numpy`, `scipy`, `pandas`, `pyyaml`, `scikit-learn`, `statsmodels`, `mapie`,
`river`, `prov` (+ `lxml`, `rdflib`), `omegaconf`, `mlflow`, `dvc`.

Optional extras (`pip install -e ".[<extra>]"`):

- `viz` — `matplotlib`, for `CumulativeMetaAnalysis.plot`.
- `hydra` — `hydra-core`, for Hydra-driven entry points (OmegaConf is core).
- `dev` — `pytest`.

A missing optional dependency raises a clear, named error — the framework never
silently skips a requested output.

> Note: `confseq` (the authoritative anytime-valid-inference library) has no
> Python 3.14 wheel and is not installed; the mSPRT module is instead validated
> against the published Howard et al. closed form.

---

## Design notes

- **Library-backed, not from-scratch.** Each pillar delegates to a mature
  library; the framework's own code is orchestration. The test suite proves
  this: it cross-checks Ophamin's output against scikit-learn, statsmodels,
  MAPIE and prov driven directly, and validates the few unavoidably-from-scratch
  modules against published reference values.
- **Independent of Kimera.** Nothing under `src/ophamin/` imports Kimera except
  `substrate/kimera_adapter.py`. The `MockSubstrate` makes the framework fully
  runnable and testable on its own.
- **Loud failure, no fabrication.** A failed cycle is recorded as a failure
  with its real error; a misconfigured adapter raises; a pillar that does not
  apply to a configuration is reported as `skipped` with an explicit reason. No
  fallback ever fabricates a plausible-looking result.
- **The provenance bridge.** Each run's `manifest.json` ties its metrics to a
  config hash, the substrate's git commit (`data_git_commit_id`), and the
  framework's own commit — a portable, content-addressed lineage record. MLflow
  is logged alongside it as the tracking backend; DVC is available for dataset
  cache versioning.
