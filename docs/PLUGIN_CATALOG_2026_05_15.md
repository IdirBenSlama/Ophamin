# Ophamin plugin catalog — open-source tools mapped to Kimera-SWM aspects

> **Status**: deep-research synthesis, 2026-05-15. Generated from web searches
> across the major Kimera-SWM aspects. Each entry: what it does, license,
> which Ophamin wheel + Kimera aspect it serves, install command, and an
> honest note on when to pick it vs alternatives.
>
> **Reading order**: §3 is the priority shortlist (the ~12 tools with the
> highest leverage given Ophamin's current state). §4–§16 are the per-aspect
> catalogs. §17 is the integration roadmap with sequenced PRs.

---

## 1. The matrix — Kimera aspect × Ophamin wheel

Each row is a Kimera aspect that needs measurement; each column is an
Ophamin wheel that should host it.

| Kimera aspect ↓ \ Ophamin wheel → | seeing | measuring | comparing | instrumenting | auditing | reporting | interop |
|---|---|---|---|---|---|---|---|
| **Substrate physics** (thermo / quantum / SPDE) | qiskit, qutip, fenics, firedrake | scipy.stats, mpmath | drift on partition functions | jax+numba acceleration | — | matplotlib | — |
| **Cognitive (Walker / Φ / IIT)** | pyphi, geomip | pyphi, infomeasure, dit | drift on Φ across commits | scalene per-cycle | — | matplotlib | mlflow |
| **Memory / SCAR topology** | gudhi, ripser, giotto-tda | persistence diagrams | drift on β₀/β₁/β₂ | — | — | persim | — |
| **Distributed / Archipel** | py-crdt, automerge | conformal prediction (puncc) | reconciliation drift | — | — | — | — |
| **Encoder / Rosetta primes** | sentence-transformers, BGE | UMAP/PaCMAP, optimal transport (POT) | encoder snapshot drift | — | — | UMAP plots | — |
| **Time / Cronos / KCCL** | kuramoto, multiSyncPy | sktime, darts, statsforecast | Allan deviation drift | viztracer | — | — | — |
| **Statistical pillars** | — | mapie, puncc, river, infomeasure, dit | drift detection (frouros, evidently) | — | — | arviz | — |
| **Wire format / determinism** | hypothesis | property-based equivalence | semver/CRDT drift | — | semgrep custom rules | — | spdx-tools |
| **Code substrate health** | tree-sitter | radon, lizard | LOC/complexity drift | austin, viztracer | semgrep, pyright, prospector, fawltydeps, deptry | — | sarif (have) |
| **Telemetry / observability** | jaeger, tempo, loki | prometheus_client (have) | metric cardinality drift | otel (have) | promtool | grafana | otel-exporter |
| **Causal / counterfactual** | — | dowhy, econml, causalml, causalpy | causal-graph drift | — | — | dowhy plots | — |
| **Supply chain** | syft (SBOM gen) | osv-scanner | dependency drift | — | grype, scancode, ossf scorecard | — | cyclonedx (have), spdx-tools |

---

## 2. Ophamin's current plugin baseline (recap)

| Layer | Tools currently integrated |
|---|---|
| **Statistical core** | numpy, scipy, statsmodels, pandas, scikit-learn, mapie, river |
| **Audit pillars** | ruff, bandit, mypy, vulture, radon, pip-audit |
| **Telemetry** | prometheus_client, opentelemetry-api/sdk |
| **Profile** | psutil, py-spy, memray |
| **Provenance** | prov, lxml, rdflib, mlflow, dvc |
| **Interop** | SARIF, JUnit XML, MLflow, CycloneDX |
| **Reporting** | matplotlib, hydra-core |
| **Datasets** | h5py (TheWell) |

These cover ~30% of what Kimera needs measurement-wise. The catalog below
is the other 70%.

---

## 3. Priority shortlist — top 12 to integrate next

Ranked by *signal-per-LOC-of-integration* against Kimera's current state.

| # | Tool | License | What it gives Ophamin | Ophamin wheel | Install |
|---|---|---|---|---|---|
| 1 | **PyPhi** | GPL-3 | Native Φ computation — Kimera's Φ is computed inline; PyPhi is the canonical reference implementation to cross-check against | measuring | `pip install pyphi` |
| 2 | **giotto-tda** | AGPL-3 / Comm. | TDA pipeline (Vietoris-Rips, persistence diagrams, kernels) for the manifold — Kimera has a `TopologicalComplexityAnalyzer` but no time-series-of-diagrams comparator | measuring + comparing | `pip install giotto-tda` |
| 3 | **POT (Python Optimal Transport)** | MIT | Wasserstein / Earth Mover for repertoires + barycentre for averaging Φ-trajectories. Kimera replaced `_emd_hamming` with closed-form recently (commit `9c055d303`); POT is the reference oracle for cross-checking | measuring | `pip install POT` |
| 4 | **Frouros** | BSD-3 | Pure-purpose drift detection (no anomaly / outlier / etc. wraps). Plug into `comparing/drift/` to ratchet thresholds per commit | comparing | `pip install frouros` |
| 5 | **DoWhy** + **EconML** | MIT | Causal inference. Kimera has 222 feedback-loop pathways → ideal substrate for causal-graph identification (does Φ drift CAUSE walker M2 amplitude_death, or just correlate?) | measuring + comparing | `pip install dowhy econml` |
| 6 | **scalene** | Apache-2 | Line-level CPU + memory profile (per-cycle). py-spy + memray we have, but scalene fuses both with line precision | instrumenting | `pip install scalene` |
| 7 | **deptry** + **fawltydeps** | MIT | Find unused / undeclared deps in Kimera's pyproject vs actual imports. Direct extension of `seeing/wiring/`'s scope to dependency-level | auditing | `pip install deptry fawltydeps` |
| 8 | **Hypothesis** | MPL-2 | Property-based testing — for Kimera's CRDT primitives (G-Set, SCAR-DAG, Echoform-chain) where invariants like idempotence / commutativity / associativity should hold by construction | auditing | `pip install hypothesis` |
| 9 | **Semgrep** | LGPL / Comm. | Custom-rule SAST that catches Kimera's no-fallback rule violations (`try: ... except: pass`) at the AST level — beyond what bandit catches | auditing | `pip install semgrep` |
| 10 | **infomeasure** | MIT | Comprehensive entropy + mutual info + transfer entropy estimators (newer than dit/pyitlib, 2025 paper). Foundation for the Σ correlation pillar measuring Kimera's 222 feedback paths | measuring | `pip install infomeasure` |
| 11 | **Syft + Grype** | Apache-2 | SBOM generation + vuln scanning. Anchore-backed, complementary to pip-audit's narrower Python focus | auditing + interop | `brew install syft grype` |
| 12 | **OSSF Scorecard** | Apache-2 | Upstream-dependency health scoring — surfaces which of Kimera's pinned deps are abandoned / unmaintained | auditing | `go install github.com/ossf/scorecard@latest` |

These 12 are the "fix next" surface. Sections §4-§16 are the broader catalog.

---

## 4. IIT / Φ computation

Kimera-SWM computes Φ inline via its IIT30 implementation (CLAUDE.md
§Family E reports mean Φ 0.621 ± 0.065 across 200 cycles). External tools
provide cross-check + alternative parameterizations.

| Tool | Notes | License |
|---|---|---|
| **[PyPhi](https://github.com/wmayner/pyphi)** | Canonical IIT 4.0 reference — Albantakis L. et al. PLoS Computational Biology 2023. Slow but exhaustive. | GPL-3 |
| **GeoMIP** | 165-326× speedup over PyPhi, 98-100% partition-identification agreement; recasts MIP search as graph optimization on hypercube | (academic, status unclear) |

**Decision**: ship PyPhi as a cross-check oracle for Kimera's `iit30_emd`
output. Pre-registered claim shape: *"Kimera's per-cycle Φ falls within
[PyPhi's Φ ± δ] on identical TPM input"*.

---

## 5. Topological data analysis (TDA)

For the Vietoris-Rips filtration, β₀/β₁/β₂ that Kimera's
`TopologicalComplexityAnalyzer` already computes (Q13 measured: β₀=1,
β₁≈322, β₂≈192) and the SCAR-network homology that `VaultHomology`
tracks.

| Tool | Strengths | License |
|---|---|---|
| **[GUDHI](https://gudhi.inria.fr/)** | C++ with Python interface; broadest simplicial-complex coverage (Rips, Witness, Alpha, Čech). Bottleneck distance, persistence | MIT (Python) |
| **[Ripser](https://github.com/scikit-tda/ripser.py)** | Fastest persistent homology computation at scale; doesn't construct complex explicitly | MIT |
| **[giotto-tda](https://giotto-ai.github.io/gtda-docs/)** | Scikit-learn-API wrapper around GUDHI + Ripser. Persistence-diagram vectorization + kernels for ML downstream | AGPL-3 / Commercial |
| **[scikit-tda](https://scikit-tda.org/)** | Umbrella package — ripser, persim, kepler-mapper | MIT |

**Decision**: giotto-tda → `seeing/topology/`, persistence-diagram-drift
scenario in `comparing/`. Track β₀/β₁/β₂ time-series across Kimera commits.

---

## 6. Information theory (entropy, mutual info, transfer entropy)

Kimera's seven entropy measures (CLAUDE.md §Semantic Entropy) need an
external reference for cross-checking. Also: Σ pillar (cross-stratum
correlation between cognitive Φ and telemetry latency) needs proper
mutual-information estimators, not Pearson r.

| Tool | Strengths | License |
|---|---|---|
| **[infomeasure](https://github.com/your/infomeasure)** | Newest (2025 paper, *Scientific Reports*); discrete + continuous; entropy / MI / transfer entropy / divergences | MIT |
| **[NPEET](https://github.com/gregversteeg/NPEET)** | Greg Ver Steeg's non-parametric Kraskov-Stögbauer-Grassberger MI estimator — the academic reference for continuous variables | MIT |
| **[ennemi](https://polsys.github.io/ennemi/)** | Easy-API nearest-neighbour MI; continuous focus | MIT |
| **[dit](https://github.com/dit/dit)** | Discrete information theory — partition-mutual-info, intrinsic-mutual-info, multivariate generalizations | BSD-3 |
| **[pyitlib](https://pafoster.github.io/pyitlib/)** | Older reference impl; standard MI / entropy / KL | GPL-3 |

**Decision**: infomeasure for the Σ pillar (covers both continuous + 
discrete with state-of-the-art estimators). NPEET as a second-opinion
oracle for the non-parametric KSG estimator.

---

## 7. Optimal transport / Earth Mover's Distance

Kimera replaced the IIT30 `_emd_hamming` HiGHS LP with an O(N·2^N)
closed form (CLAUDE.md §2026-05-15 IIT30 fix; commit `9c055d303`,
~10% throughput gain). External validation:

| Tool | Strengths | License |
|---|---|---|
| **[POT](https://pythonot.github.io/)** | Network simplex (exact EMD), Sinkhorn (entropic regularization, GPU), Gromov-Wasserstein, barycentres | MIT |

**Decision**: POT as Ophamin's reference oracle for `_emd_hamming` —
write a regression scenario asserting Kimera's closed form ≈ POT's
network-simplex within 1e-12. Ratchet on every commit touching
`_effect_repertoire` / `_cause_repertoire`.

---

## 8. Drift detection

Ophamin already has a `comparing/drift/` directory but the scope is per-PR
proof-record drift. For per-commit metric drift across many strata, a
purpose-built library helps.

| Tool | Strengths | License |
|---|---|---|
| **[Frouros](https://github.com/IFCA-Advanced-Computing/frouros)** | Pure-purpose drift detection (no overlap with anomaly / adversarial / imbalance — single responsibility). Both concept + data drift. | BSD-3 |
| **[Evidently](https://github.com/evidentlyai/evidently)** | 100+ pre-built checks, interactive HTML reports, well-suited for ratchet-style monitoring | Apache-2 |
| **[NannyML](https://nannyml.readthedocs.io/)** | Performance estimation without ground truth (univariate + multivariate) | Apache-2 |
| **[TorchDrift](https://github.com/TorchDrift/TorchDrift)** | PyTorch-native, kernel MMD, classifier two-sample tests | Apache-2 |
| **[River](https://riverml.xyz/)** *(installed)* | Already in Ophamin. Online algorithms include drift detectors (ADWIN, DDM, EDDM, KSWIN) | BSD-3 |

**Decision**: Frouros for the new dedicated `comparing/drift/` library
(one purpose, signed proof-records). Evidently for HTML-report ratchets.

---

## 9. Causal inference

Kimera has 222 feedback-loop pathways. Today Ophamin's Σ pillar (planned)
would only measure CORRELATION. Causal inference distinguishes *X causes Y*
from *X correlates with Y but Z drives both* — exactly the question
needed when Φ drift correlates with walker M2 amplitude_death.

| Tool | Strengths | License |
|---|---|---|
| **[DoWhy](https://www.pywhy.org/dowhy/)** | PyWhy ecosystem orchestrator. Four-step API (model → identify → estimate → refute). Integrates EconML + CausalML | MIT |
| **[EconML](https://github.com/py-why/EconML)** | Microsoft's HTE estimators (DML, DR-Learner, X-Learner, Causal Forests) | MIT |
| **[CausalML](https://github.com/uber/causalml)** | Uber's uplift modeling — counterfactual + doubly-robust | Apache-2 |
| **[CausalPy](https://github.com/pymc-labs/CausalPy)** | Bayesian causal inference (synthetic control, RDD, ITS) on top of PyMC | Apache-2 |
| **[Tigramite](https://github.com/jakobrunge/tigramite)** | Time-series causal discovery (PCMCI). Directly applicable to Kimera's per-cycle Φ trajectory | GPL-3 |

**Decision**: DoWhy as the orchestrator + Tigramite for time-series-causal
discovery on Kimera's 638-field per-cycle OrchestratorResult traces.

---

## 10. Code-substrate health (static analysis + dependency wiring)

Kimera is a 3,363-module substrate (per Ophamin's wiring scan). Today's
audit pillars (ruff, bandit, mypy, vulture, radon, pip-audit) cover
linting + security + types + dead code + complexity + dep vulns. Gaps:

| Tool | Fills | License |
|---|---|---|
| **[Semgrep](https://semgrep.dev/)** | Custom-rule SAST. Can encode Kimera's no-fallback rule (`try: ... except: pass`), Pattern-P naming-violation patterns (Enhanced*, Unified*, *Manager) | LGPL-2.1 / Commercial |
| **[Pyright / Pyrefly](https://github.com/microsoft/pyright)** | Microsoft's fast type checker. Pyrefly (the next-gen) provides IDE features. Faster than mypy on large codebases | MIT |
| **[Pylint](https://pylint.readthedocs.io/)** | Deep type-inference + custom plugins beyond what ruff replicates | GPL-2 |
| **[Prospector](https://prospector.landscape.io/)** | Multi-tool aggregator (Pylint + Mypy + McCabe + dodgy + frosted) | GPL-2 |
| **[FawltyDeps](https://github.com/tweag/FawltyDeps)** | Find undeclared + unused 3rd-party deps; reads pyproject / requirements / setup.py / setup.cfg / environment.yml | MIT |
| **[deptry](https://github.com/fpgmaas/deptry)** | Same shape, faster, supports Poetry / pip / PDM / uv / PEP 621 | MIT |
| **[lizard](https://github.com/terryyin/lizard)** | Cyclomatic complexity, multi-language; complements radon | MIT |
| **[refurb](https://github.com/dosisod/refurb)** | Modernization suggestions for Python ≥ 3.10+ idioms | GPL-3 |
| **[autoflake](https://github.com/PyCQA/autoflake)** | Remove unused imports + variables | MIT |

**Decision**: ship semgrep + pyright + fawltydeps + deptry as the
"audit pillar v2" tier. Each as an opt-in pillar.

---

## 11. Profiling + tracing

Kimera's `takwin.py` is 32,743 lines; the 6 audit pillars surfaced
616 findings on it. For per-cycle profile, where is the 8s wall-time
actually going?

| Tool | Strengths | License |
|---|---|---|
| **[Scalene](https://github.com/plasma-umass/scalene)** | Line-level CPU + GPU + memory in one tool. Best for deep substrate-cycle timing | Apache-2 |
| **[Pyinstrument](https://github.com/joerick/pyinstrument)** | Beautiful call-stack visualization. Best for narrative reports | BSD-3 |
| **[VizTracer](https://github.com/gaogaotiantian/viztracer)** | Interactive timeline (Chrome trace viewer). Best when timing IS the bug | Apache-2 |
| **[Austin](https://github.com/P403n1x87/austin)** | Frame-stack sampler (low overhead). Pairs well with austinp graphics | GPL-3 |
| **[py-spy](https://github.com/benfred/py-spy)** *(installed)* | Already in Ophamin. Production-safe sampling, zero modification of running process | MIT |
| **[memray](https://github.com/bloomberg/memray)** *(installed)* | Already in Ophamin. Per-allocation tracker | Apache-2 |
| **[line_profiler](https://github.com/pyutils/line_profiler)** | Line-level CPU only. Surgical for hot spots after py-spy locates them | BSD-3 |

**Decision**: add scalene as the "deep cycle inspection" tier. Wire
into `instrumenting/` as an opt-in.

---

## 12. Time-series + anomaly detection (Cronos / KCCL telemetry)

Kimera's Cronos atomic clock has Allan-deviation tracking; KCCL
oscillators emit per-phase wall-time. Ophamin should track these as
proper time-series.

| Tool | Strengths | License |
|---|---|---|
| **[sktime](https://www.sktime.net/)** | Unified scikit-learn-style API for forecasting / classification / anomaly | BSD-3 |
| **[Darts](https://unit8co.github.io/darts/)** | Forecasting + anomaly + filtering. Anomaly module wraps any model into detector | Apache-2 |
| **[Kats](https://github.com/facebookresearch/Kats)** | Meta's one-stop time-series. Detection + forecasting + features + multivariate | MIT |
| **[TSFresh](https://tsfresh.readthedocs.io/)** | Feature-extraction (1000+ features) + selection. Pairs with River for online drift | MIT |
| **[PyOD](https://pyod.readthedocs.io/)** | Outlier detection (50+ algorithms). PyODScorer trivially wraps for Darts | BSD-2 |
| **[STUMPY](https://stumpy.readthedocs.io/)** | Matrix profile (Eamonn Keogh's framework) — fast motif + discord discovery | BSD-3 |
| **[NeuralForecast](https://github.com/Nixtla/neuralforecast)** | 30+ neural models (NHITS, NBEATS, TFT, Informer, PatchTST). Good for multi-step Φ-trajectory forecasting | Apache-2 |
| **[StatsForecast](https://github.com/Nixtla/statsforecast)** | Classical statistical forecasters (AutoARIMA, ETS, MSTL); fast | Apache-2 |

**Decision**: STUMPY for matrix-profile drift on per-cycle Φ trajectory.
Darts for forecasting + anomaly bands on telemetry streams.

---

## 13. Distributed tracing + observability stack

Ophamin currently consumes Prometheus. Production deployment also wants
distributed tracing.

| Tool | Strengths | License |
|---|---|---|
| **[Jaeger](https://www.jaegertracing.io/)** | CNCF-graduated. Adaptive sampling, scalable, rich UI | Apache-2 |
| **[Grafana Tempo](https://grafana.com/oss/tempo/)** | Cost-efficient (object storage only). Integrates with Prom+Loki+Grafana | AGPL-3 |
| **[Loki](https://grafana.com/oss/loki/)** | Log aggregation (queries via LogQL). Part of LGTM stack | AGPL-3 |
| **[OpenTelemetry](https://opentelemetry.io/)** *(installed)* | Industry-standard collector. Already in Ophamin | Apache-2 |
| **[Mimir](https://grafana.com/oss/mimir/)** | Long-term Prometheus storage (not in Ophamin scope) | AGPL-3 |
| **[Pyroscope](https://pyroscope.io/)** | Continuous profiling (Grafana family). Complements py-spy / scalene | AGPL-3 |

**Decision**: Tempo as the natural extension of Ophamin's telemetry
consumer; both speak OTel. Pyroscope as a continuous-profile addition.

---

## 14. CRDT / reconciliation (for Archipel cross-checks)

Kimera has its own G-Set, SCAR-DAG, Echoform-chain CRDTs. External
references for cross-check + interop:

| Tool | Strengths | License |
|---|---|---|
| **[Yjs](https://github.com/yjs/yjs)** | Most-deployed CRDT library globally as of 2026. Modular (text, array, map, xml) | MIT |
| **[Automerge](https://automerge.org/)** | JSON CRDT (Rust core). Automerge 3.x has columnar storage + Peritext for rich text | MIT |
| **[pycrdt](https://github.com/y-crdt/pycrdt)** | Python bindings for Yrs (the Rust port of Yjs) | MIT |
| **[y-py](https://github.com/y-crdt/ypy)** | Python bindings for Y-CRDT | MIT |

**Decision**: pycrdt as a property-based-test oracle for Kimera's
G-Set + SCAR-DAG (Hypothesis strategies that compare Kimera's CRDT
against Yrs's CRDT for the same operation sequence).

---

## 15. Statistical + uncertainty quantification

Kimera's empirical record (per Ophamin scenarios) uses Wilson 95% CI +
Cohen's d + Mann-Whitney U today. To raise the rigor bar:

| Tool | Strengths | License |
|---|---|---|
| **[MAPIE](https://mapie.readthedocs.io/)** *(installed)* | Already in Ophamin. v1+ has 20+ conformal methods | BSD-3 |
| **[PUNCC](https://github.com/deel-ai/puncc)** | Conformal prediction + classification + object detection + anomaly. Integrates with PyTorch / TensorFlow | MIT |
| **[crepes](https://crepes.readthedocs.io/)** | Conformal regressors + classifiers + predictive systems. Semi-online | BSD-3 |
| **[TorchCP](https://github.com/ml-stat-Sustech/TorchCP)** | PyTorch-native, fastest of the four (90% faster than PUNCC). LLM / GNN support | Apache-2 |
| **[ArviZ](https://python.arviz.org/)** | Bayesian-posterior visualization + diagnostics. Standard across PyMC / Stan / NumPyro | Apache-2 |
| **[PyMC](https://www.pymc.io/)** | Bayesian PPL. Compiles to C / JAX / Numba. For posterior-tempering scenarios (CLAUDE.md §Family L L9 already does this manually) | Apache-2 |
| **[NumPyro](https://num.pyro.ai/)** | JAX-backed PPL. Faster than PyMC for HMC / NUTS at scale | Apache-2 |
| **[pingouin](https://pingouin-stats.org/)** | Effect-size + correlation + multiple comparison. Cleaner API than scipy.stats for many tests | GPL-3 |

**Decision**: pingouin for proper effect-size + multiple-comparison
correction in cross-stratum scenarios. PyMC + ArviZ for any Bayesian
scenario (Family L's posterior-tempering would benefit from a proper
PPL implementation).

---

## 16. SBOM / supply chain / dependency security

Beyond pip-audit (which we have):

| Tool | Strengths | License |
|---|---|---|
| **[Syft](https://github.com/anchore/syft)** | SBOM generation for containers + filesystems + archives. Outputs CycloneDX + SPDX. Anchore-backed | Apache-2 |
| **[Grype](https://github.com/anchore/grype)** | Vulnerability scanning of SBOMs. Pairs with Syft | Apache-2 |
| **[Trivy](https://github.com/aquasecurity/trivy)** | All-in-one (vuln + IaC + SBOM). **WARNING**: compromised twice in March 2026 supply chain attack — re-evaluate before use | Apache-2 |
| **[ScanCode-toolkit](https://scancode-toolkit.readthedocs.io/)** | License + copyright + dependency detection. Outputs SPDX + CycloneDX | Apache-2 |
| **[Dependency-Track](https://dependencytrack.org/)** | Long-term SBOM monitoring (server) | Apache-2 |
| **[OSV-Scanner](https://google.github.io/osv-scanner/)** | Google's CLI scanner against OSV.dev DB | Apache-2 |
| **[Socket](https://socket.dev/)** | Runtime install-time analysis (network requests, dynamic code execution) — closest to real-time supply chain protection | Commercial |
| **[OpenSSF Scorecard](https://github.com/ossf/scorecard)** | Upstream-dep health scoring (signed releases, branch protection, fuzz coverage) | Apache-2 |
| **[Safety](https://safetycli.com/)** | Python-specific vuln scanner | MIT |
| **[Snyk Open Source](https://snyk.io/)** | Reachability analysis, auto-fix PRs, license compliance | Commercial |
| **[SPDX-tools](https://github.com/spdx/tools-python)** | SPDX format generation/validation | Apache-2 |

**Decision**: Syft + Grype as the bulk SBOM layer (covering Kimera's
container deployments). OSV-Scanner as a CI fast-fail gate.
SPDX-tools for the interop wheel (currently CycloneDX-only).

---

## 17. Quantum / thermodynamic / SPDE substrate libraries

For cross-checking Kimera's physics-side claims:

| Tool | Aspect | License |
|---|---|---|
| **[Qiskit](https://www.ibm.com/quantum/qiskit)** | Quantum circuits + pulse + dynamic. Most feature-rich. Cross-check `PrimeWaveQuantumEngine` outputs | Apache-2 |
| **[Cirq](https://github.com/quantumlib/Cirq)** | Google's NISQ-focused. Lightweight | Apache-2 |
| **[PennyLane](https://pennylane.ai/)** | Quantum + ML differentiable programming. For Kimera's quantum-RL primitives | Apache-2 |
| **[QuTiP](https://qutip.org/)** | Quantum dynamics simulation. Best for the thermofield-double + open-system dynamics | BSD-3 |
| **[Strawberry Fields](https://strawberryfields.ai/)** | Photonic quantum circuits | Apache-2 |
| **[FEniCS](https://fenicsproject.org/)** | FEM-based PDE solver. Reference oracle for SPDE engine | LGPL |
| **[Firedrake](https://www.firedrakeproject.org/)** | Newer, FEniCS-compatible UFL, automated code generation | LGPL |
| **[DeepXDE](https://deepxde.readthedocs.io/)** | Physics-informed neural networks (PINNs) for Allen-Cahn, Gray-Scott, Eikonal | Apache-2 |

**Decision**: Qiskit + QuTiP as quantum cross-check oracles. FEniCS or
Firedrake as the SPDE oracle. Out-of-scope for v0.2; flagged for v0.3.

---

## 18. Graph + network analysis (manifold + SCAR-network)

Kimera builds graphs everywhere (geoid manifold, SCAR network, Arachne
web, Piovra arms). Today's NetworkX is fine for small graphs but slow
at scale.

| Tool | Strengths | Speed vs NetworkX |
|---|---|---|
| **[NetworkX](https://networkx.org/)** *(implicit)* | Pure Python, easiest install | 1× (baseline) |
| **[graph-tool](https://graph-tool.skewed.de/)** | C++ core. Statistical inference (SBM, hierarchical SBM) | 40-250× faster |
| **[igraph](https://igraph.org/python/)** | C core. Mature graph algorithms | ~30× faster |
| **[NetworKit](https://networkit.github.io/)** | Parallel C++. Page rank in 0.2s on Pokec dataset | Up to 250× faster |
| **[SNAP-py](https://snap.stanford.edu/snappy/)** | Stanford's network analysis platform | ~10× faster |

**Decision**: NetworKit for any graph-analysis scenario hitting
Kimera's full SCAR network (1M+ scars). graph-tool if SBM-style
community detection is needed for substrate clustering.

---

## 19. Encoder / embedding (for Rosetta primes cross-check)

Kimera has its own EnhancedTransformer + FastText fallback. External
encoders for cross-check:

| Tool | Strengths | License |
|---|---|---|
| **[sentence-transformers](https://sbert.net/)** | 15,000+ pretrained models on Hugging Face. Standard | Apache-2 |
| **[BGE](https://github.com/FlagOpen/FlagEmbedding)** | BAAI's BGE-M3 (already in Kimera as a fallback) | MIT |
| **[GTE](https://huggingface.co/Alibaba-NLP)** | Alibaba's multi-lingual encoders | Apache-2 |
| **[mxbai-embed](https://www.mixedbread.ai/)** | Mixedbread AI's embeddings | Apache-2 |
| **[Nomic Embed](https://www.nomic.ai/)** | Nomic's open-source encoders, including ModernBERT-based | Apache-2 |
| **[gensim](https://radimrehurek.com/gensim/)** | Word2Vec, FastText, Doc2Vec — for cross-checking Kimera's FastText | LGPL |

**Decision**: sentence-transformers as the canonical reference oracle
for `assign_via_lyriform`'s output. Per-encoder cross-check scenario:
*"two semantically equivalent sentences produce primes whose Wilson CI
on Jaccard ≥ 0.5"*.

---

## 20. Probabilistic / fuzz testing

For Kimera's CRDT primitives + the no-fallback rule:

| Tool | Strengths | License |
|---|---|---|
| **[Hypothesis](https://hypothesis.works/)** | Property-based testing with strategies. CRDT laws (idempotent / commutative / associative) are textbook strategies | MPL-2 |
| **[Atheris](https://github.com/google/atheris)** | Coverage-guided fuzzing (libFuzzer-based). Catches crashes in PrimePacket parsers, RIBLT decoders | Apache-2 |
| **[Mutmut](https://github.com/boxed/mutmut)** | Mutation testing — 1,200 mutants/min, 88.5% kill rate. Faster than Cosmic Ray | MIT |
| **[Cosmic Ray](https://cosmic-ray.readthedocs.io/)** | Mutation testing — most operators, parallel execution. 82.7% kill rate | MIT |
| **[Schemathesis](https://schemathesis.readthedocs.io/)** | API contract testing from OpenAPI / GraphQL specs. For Kimera's 47 REST routers | MIT |
| **[Coverage.py](https://coverage.readthedocs.io/)** | Standard line + branch coverage | Apache-2 |
| **[Slipcover](https://github.com/plasma-umass/slipcover)** | Faster (10×) coverage for Python | Apache-2 |

**Decision**: Hypothesis for CRDT laws. Schemathesis as the API-contract
audit pillar. Mutmut as the mutation-testing audit pillar.

---

## 21. Acceleration (when scenarios get slow)

Kimera's scenarios run cycles in batches; some take 8s+ each. If
Ophamin's analytic pillars become bottlenecks:

| Tool | Strengths | License |
|---|---|---|
| **[JAX](https://jax.readthedocs.io/)** | Autograd + JIT for scientific computing. NumPy-API. Hundreds of × faster than pure Python | Apache-2 |
| **[Numba](https://numba.pydata.org/)** | JIT for NumPy + scalar code. 6× speedup typical, no source rewriting | BSD-3 |
| **[Cython](https://cython.org/)** | Compiles annotated Python to C. 50× speedups, but rewrite needed | Apache-2 |
| **[Polars](https://www.pola.rs/)** | Faster pandas-replacement; Apache-Arrow-backed | MIT |
| **[DuckDB](https://duckdb.org/)** | In-process analytical SQL; great for proof-record corpus queries | MIT |

**Decision**: Polars for `comparing/drift/` corpus queries. JAX for
any matrix-heavy pillar. Numba for hot inner loops in the wiring probe.

---

## 22. Recommended integration sequence (PRs)

| PR | Adds | Wheel | LOC budget | Tier-2 / Tier-3 |
|---|---|---|---|---|
| 1 | PyPhi cross-check oracle for IIT30 | measuring | 200 + 100 tests | Tier-2 |
| 2 | POT cross-check oracle for `_emd_hamming` | measuring | 150 + 80 tests | Tier-2 |
| 3 | giotto-tda persistence-diagram drift | measuring + comparing | 350 + 200 tests | Tier-2 |
| 4 | infomeasure + Σ correlation pillar | measuring | 400 + 250 tests | Tier-2 |
| 5 | Frouros drift detector for `comparing/drift/` | comparing | 250 + 150 tests | Tier-2 |
| 6 | DoWhy + Tigramite causal-graph identification | measuring + comparing | 500 + 300 tests | Tier-2 |
| 7 | Semgrep custom-rule audit pillar (no-fallback + Pattern-P) | auditing | 200 + 150 tests | Tier-2 |
| 8 | Pyright audit pillar (faster type-check than mypy) | auditing | 100 + 50 tests | Tier-2 |
| 9 | deptry + fawltydeps for dependency wiring | auditing | 150 + 80 tests | Tier-2 |
| 10 | Hypothesis CRDT-law tests (Tier-2 — for Kimera's CRDTs, not Ophamin's) | (Kimera-side) | 300 + 200 tests | Tier-3 (owner-gated) |
| 11 | Schemathesis API-contract audit pillar | auditing | 200 + 100 tests | Tier-2 |
| 12 | Mutmut mutation-testing audit pillar | auditing | 200 + 100 tests | Tier-2 |
| 13 | Scalene per-cycle line-level profile | instrumenting | 200 + 100 tests | Tier-2 |
| 14 | STUMPY matrix-profile drift on Φ-trajectory | comparing | 250 + 150 tests | Tier-2 |
| 15 | Syft + Grype SBOM gen + vuln scan in interop | interop + auditing | 300 + 150 tests | Tier-2 |
| 16 | OSSF Scorecard upstream-dep health score | auditing | 200 + 100 tests | Tier-2 |
| 17 | NetworKit for SCAR-network analysis at scale | seeing | 250 + 150 tests | Tier-2 |
| 18 | sentence-transformers cross-encoder Jaccard scenario | measuring | 350 + 200 tests | Tier-2 |
| 19 | PyMC + ArviZ Bayesian Family-L style scenario | measuring | 400 + 250 tests | Tier-2 |
| 20 | Pingouin effect-size + multi-comparison helper | measuring | 100 + 60 tests | Tier-2 |

**Total rough budget**: ~5,000 LOC + ~2,800 tests across 20 PRs.

If sequenced one PR per 1-2 sessions, this is 4-6 weeks of work. Each
PR is independently reviewable and ships value on its own.

---

## 23. What's deliberately out of scope

- **Closed-source / commercial-only**: Datadog, New Relic, Snyk Code,
  Splunk. Ophamin should stay OSS-first; an enterprise can add these
  as adapters but they're not core.
- **JVM-only**: JIDT (Java Information Dynamics Toolkit) — equivalent
  Python coverage exists.
- **Heavy external infra**: full Loki / Tempo deployments need K8s and
  go beyond what Ophamin can usefully wrap. Provide consumer adapters
  but don't ship the deployment.
- **AI/ML model serving**: NVIDIA Triton, KServe, Seldon — not relevant
  to Kimera-as-substrate.
- **GPU-only tools**: anything requiring CUDA without a CPU fallback
  would break MockSubstrate-only test runs.

---

## 24. Honest unknowns

- **Trivy supply-chain compromise (March 2026)**: per the search
  results, Trivy was compromised twice. Verify current safety status
  before any integration. Syft+Grype is the cleaner Anchore-stack
  alternative.
- **GeoMIP availability**: 165-326× speedup over PyPhi sounds great
  but the search results don't surface a maintained pip-installable
  package. Verify maturity before substituting for PyPhi.
- **Pyrefly (Pyre next-gen) maturity**: Meta's replacement; depends on
  whether 2026 release supports the codebases Ophamin targets.
- **License compatibility with Ophamin's proprietary license**: GPL-3
  tools (PyPhi, Tigramite, refurb, Pylint) need a usage-pattern
  audit before bundling vs invoking-via-subprocess.
- **Performance on Kimera-scale inputs**: most academic libraries
  benchmarked on smaller graphs / corpora. Validate at Kimera-SWM
  scale (3,363 modules, 1M+ scars potential) before committing to
  any one tool.

---

## 25. Sources

Per the WebSearch tool requirement, sources for this synthesis:

### IIT / Φ
- [PyPhi (PyPI)](https://pypi.org/project/pyphi/)
- [PyPhi GitHub](https://github.com/wmayner/pyphi)
- [PyPhi paper (PLOS Comp Bio)](https://journals.plos.org/ploscompbiol/article?id=10.1371/journal.pcbi.1006343)
- [Integrated Information Theory (official)](http://staging.integratedinformationtheory.org/index.html)

### TDA
- [GUDHI library](https://gudhi.inria.fr/index.html)
- [giotto-tda paper (JMLR)](https://www.jmlr.org/papers/volume22/20-325/20-325.pdf)
- [awesome-tda list](https://github.com/FatemehTarashi/awesome-tda)

### Information theory
- [infomeasure paper (Nature SR 2025)](https://www.nature.com/articles/s41598-025-14053-5)
- [NPEET](https://github.com/gregversteeg/NPEET)
- [pyitlib](https://pafoster.github.io/pyitlib/)
- [dit](https://github.com/dit/dit)
- [ennemi](https://polsys.github.io/ennemi/)

### Causal inference
- [DoWhy (PyWhy)](https://www.pywhy.org/)
- [DoWhy GitHub](https://github.com/py-why/dowhy)
- [CausalML (Uber)](https://github.com/uber/causalml)
- [Causal ML paper](https://www.sciencedirect.com/science/article/pii/S2352711022002126)

### Optimal transport
- [POT documentation](https://pythonot.github.io/)
- [POT paper (JMLR)](https://www.jmlr.org/papers/volume22/20-451/20-451.pdf)

### Drift detection
- [Frouros GitHub](https://github.com/IFCA-Advanced-Computing/frouros)
- [Frouros paper (SoftwareX)](https://www.sciencedirect.com/science/article/pii/S2352711024001043)
- [TorchDrift](https://github.com/TorchDrift/TorchDrift)
- [Evidently AI](https://www.evidentlyai.com/ml-in-production/concept-drift)

### Profiling
- [py-spy](https://github.com/benfred/py-spy)
- [awesome-profiling list](https://github.com/msaroufim/awesome-profiling)
- [10 Profiling Tools 2026](https://thectoclub.com/tools/best-profiling-tools/)

### Dependency analysis
- [FawltyDeps](https://github.com/tweag/FawltyDeps)
- [deptry](https://pypi.org/project/deptry/)
- [PyTrim paper (arXiv)](https://arxiv.org/html/2510.00674v1)

### SBOM / supply chain
- [Syft (Anchore)](https://github.com/anchore/syft)
- [Top 5 SBOM Tools](https://www.ox.security/blog/sbom-tools/)
- [SBOM tools comparison 2026](https://sbomify.com/2026/01/26/sbom-generation-tools-comparison/)
- [Awesome supply chain security](https://github.com/bureado/awesome-software-supply-chain-security)

### Mutation + property testing
- [Cosmic Ray](https://github.com/sixty-north/cosmic-ray)
- [Hypothesis](https://github.com/HypothesisWorks/hypothesis)
- [Atheris (Google)](https://pypi.org/project/atheris/)
- [Mutmut 2026 guide](https://johal.in/mutation-testing-with-mutmut-python-for-code-reliability-2026/)

### Static analysis
- [Top 10 Python Code Analysis Tools 2026](https://www.jit.io/resources/appsec-tools/top-python-code-analysis-tools-to-improve-code-quality)
- [Best Code Review Tools for Python 2026](https://dev.to/rahulxsingh/best-code-review-tools-for-python-in-2026-linters-sast-and-ai-5pb)
- [Awesome static analysis](https://github.com/analysis-tools-dev/static-analysis)

### Quantum
- [Qiskit](https://www.ibm.com/quantum/qiskit)
- [Cirq](https://github.com/quantumlib/Cirq)
- [PennyLane](https://pennylane.ai/)
- [Open Quantum Projects List](https://qosf.org/project_list/)

### Reaction-diffusion / PDE
- [FEniCS Project](https://fenicsproject.org/)
- [Firedrake](https://www.firedrakeproject.org/)
- [DeepXDE](https://deepxde.readthedocs.io/)

### Graph analysis
- [graph-tool benchmarks](https://graph-tool.skewed.de/performance.html)
- [Quasilinear benchmark](https://www.timlrx.com/blog/benchmark-of-popular-graph-network-packages-v2/)
- [GraphBenchmark repo](https://github.com/ytyz1307zzh/GraphBenchmark)

### CRDT
- [Yjs](https://github.com/yjs/yjs)
- [Automerge](https://automerge.org/)
- [pycrdt](https://y-crdt.github.io/pycrdt/)
- [CRDT implementations list](https://crdt.tech/implementations)

### Bayesian / PPL
- [PyMC paper (PeerJ)](https://peerj.com/articles/cs-1516/)
- [NumPyro GitHub](https://github.com/pyro-ppl/numpyro)
- [Bayesian Modeling and Computation Book](https://bayesiancomputationbook.com/markdown/chp_10.html)

### MLOps
- [Top 20 MLOps Tools 2026](https://www.sganalytics.com/blog/mlops-tools/)
- [MLflow alternatives](https://www.zenml.io/blog/mlflow-alternatives)
- [W&B alternatives](https://www.zenml.io/blog/weights-and-biases-alternatives)

### Time-series
- [awesome-TS-anomaly-detection](https://github.com/rob-med/awesome-TS-anomaly-detection)
- [Hyndman: Python time-series](https://robjhyndman.com/hyndsight/python_time_series.html)
- [awesome-time-series](https://github.com/lmmentel/awesome-time-series)

### Distributed tracing
- [Grafana Tempo](https://grafana.com/oss/tempo/)
- [LGTM stack on K8s](https://github.com/saidsef/grafana-loki-on-k8s)
- [Top 10 OSS Observability 2026](https://openobserve.ai/blog/top-10-open-source-observability-tools/)

### Kuramoto / oscillators
- [fabridamicelli/kuramoto](https://github.com/fabridamicelli/kuramoto)
- [carpet](https://github.com/icemtel/carpet)
- [PyRates](https://pyrates.readthedocs.io/)
- [multiSyncPy paper](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC10027834/)

### Embeddings
- [SBERT](https://sbert.net/)
- [BGE (FlagEmbedding)](https://github.com/FlagOpen/FlagEmbedding)
- [Top Embedding Models 2026](https://artsmart.ai/blog/top-embedding-models-in-2025/)

### Dimensionality reduction
- [UMAP docs](https://umap-learn.readthedocs.io/)
- [PaCMAP](https://github.com/YingfanWang/PaCMAP)
- [Wang et al. JMLR 2021](https://jmlr.org/papers/v22/20-1061.html)

### SAT/SMT
- [PySAT](https://pysathq.github.io/)
- [Z3](https://gu-youngfeng.github.io/blogs/smtsolver.html)
- [CVC5](https://github.com/cvc5/cvc5)
- [pySMT](https://github.com/pysmt/pysmt)

### Conformal prediction
- [MAPIE v1 announcement](https://medium.com/capgemini-invent-lab/uncertainty-quantified-mapie-v1-is-here-b0d0f953b5ac)
- [PUNCC](https://github.com/deel-ai/puncc)
- [TorchCP paper (JMLR)](https://www.jmlr.org/papers/volume26/24-2141/24-2141.pdf)

### Streaming / online
- [River](https://github.com/online-ml/river)
- [NeuralForecast](https://pypi.org/project/neuralforecast/)

### Acceleration
- [Cython 3.0 vs Numba 2026](https://johal.in/cython-3-0-speedups-numba-jit-compilation-alternatives-comparison-2026/)
- [JAX comparative study](https://www.researchgate.net/publication/394089474_A_Comparative_Study_of_Pure_Python_and_JAX-Based_Approaches_in_Computing_Harmonic_Series)
- [PyCon US 2026 talk](https://us.pycon.org/2026/schedule/presentation/128/)

### Supply chain (more)
- [SCA Tools for Python 2026](https://appsecsanta.com/sca-tools/sca-tools-for-python)
- [OSSF Scorecard](https://github.com/ossf/scorecard)

---

*Authored by Claude (Opus 4.7 1M context), 2026-05-15. Synthesized from
22 parallel WebSearch queries across the 20+ Kimera-SWM aspects. Subject
to owner pick + sequencing decisions before implementation.*
