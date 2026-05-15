# Changelog

All notable changes to Ophamin will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project follows [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- **WiringProbe + SubstrateCompletenessScenario + `ophamin wiring` — v0.2 Step 5 (pivoted).**
  The owner clarified Kimera is incomplete by design — infra folders may
  be scaffolding nothing actually uses, and Ophamin's load-bearing value
  is empirical feedback to drive substrate completion. The probe builds
  a repo-wide import graph (one pass over kimera_swm/, ~5s on real
  Kimera, ~3500 .py files) + scans for ``.. note:: WIRE_CANDIDATE`` /
  WIRED / ARCHIVED annotations + counts stub function bodies (``pass``
  / ``raise NotImplementedError`` / ``return None``). For each
  inventoried surface it emits a classification: ``wired`` (≥1 incoming
  import OR WIRED annotation), ``wire_candidate`` (explicitly
  scaffolded), ``orphan`` (zero imports, no annotation — the action
  target), ``archived`` (path under ``_archive/`` or
  ``_predecessor.py`` suffix), ``parse_error`` (broken file), or
  ``config`` (non-Python surface).

  ``SubstrateCompletenessScenario`` aggregates into a falsifiable claim:
  ``aggregate_orphan_rate <= 0.20``. ``ophamin wiring <repo>`` writes
  signed JSON + Markdown reports with per-stratum tables + the orphan +
  WIRE_CANDIDATE action lists.

  **First live measurement against Kimera-SWM @ a0adf1a0 (2026-05-15):**
  - **VALIDATED at 26/323 = 8.05% orphan rate**, Wilson CI [0.0553, 0.1158]
  - 289 wired (89.5%), 26 orphan (8%), 8 WIRE_CANDIDATE (2.5%)
  - Action list pinpoints: 7 persistence orphans (postgres_insight_repository
    with 22 unimported functions, connection_manager, database_production_manager,
    enhanced_database_optimizer_fixed — the "_fixed" suffix is the giveaway),
    4 temporal orphans (kccl_integration, scale5_adapters with 37 fns,
    spde_integration, surfacing), 7 lifecycle orphans (encoder_snapshot/builder.py
    despite its docstring promising SnapshotBuilder.build as public API —
    confirmed orphan: __init__.py doesn't import from it), 6 security orphans,
    1 telemetry orphan, 1 interface orphan (monitoring_router.py — verified by
    a comment in core/application.py saying it was deliberately not wired).

  Import graph correctness was verified mid-build: the first run showed
  40 interface orphans, but ``from kimera_swm.api.routers import
  computation_router`` wasn't being counted as an edge for
  ``kimera_swm.api.routers.computation_router``. Fix: extend the import
  scanner to emit ``parent.child`` references on ``from`` imports. Result
  dropped to 1 true interface orphan.

  52 new hardening tests (40 wiring probe + 12 scenario). Test count:
  492 → 544.

- **InterfaceContractStability scientific scenario — v0.2 Step 4.**
  First scenario targeting the **interface** stratum (REST routers,
  controllers, GraphQL, MCP tools, CLI commands, WebSocket). Pure static
  analysis — does not import or run Kimera. For each Python module
  ``KimeraInventory.discover_interface`` reports, runs ``ast.parse`` and
  checks for top-level OR class-method handler-decorator presence
  (FastAPI verbs, MCP ``@tool``/``@resource``, Click ``@command``, etc.).
  Pre-registered claim: ``contract_compliance_rate >= 0.95`` with Wilson
  95% CI.

  Live measurement against Kimera-SWM @ a0adf1a0 (2026-05-15):
  **VALIDATED at 98/100 = 0.98**, Wilson CI [0.93, 0.9945]. Two
  non-compliant outliers (``api/routers/geoid.py`` +
  ``api/routers/multimodal_router.py``) surfaced for investigation.

  This is the **first VALIDATED claim Ophamin has made about the interface
  stratum**. 23 hardening tests in
  ``tests/test_interface_contract_stability.py`` covering the decorator
  matcher (router.get / @tool / @click.command / negative cases),
  per-module probe (package_dir / non-py skip / top-level handler / class
  method handler / syntax error / pure-schema rejection), end-to-end
  scenario on healthy + broken synthetic trees, registry membership,
  Wilson CI, signature, claim shape. Test count: 469 → 492.

- **PrometheusScrapeProbe + `ophamin scrape` — v0.2 Step 3.**
  Passive consumer of Kimera-SWM's `/metrics` endpoint (Kimera already
  ships a `prometheus_client`-based exporter under
  `kimera_swm/infrastructure/monitoring/prometheus_exporter.py`). One scrape
  produces a signed, content-addressed `PrometheusSnapshot` carrying every
  metric family + sample. Loud failure on connectivity / timeout / parse
  error. Plus `AlignedTelemetryWindow` + `align_to_window()` for
  before/during/after correlation with scenario windows — the foundation
  for the Σ (cross-stratum correlation) measuring pillar. Optional
  dependency: `prometheus_client>=0.17` under the `[telemetry]` extra; the
  module loads but probe construction loud-fails if absent. 19 hardening
  tests using a stdlib `http.server` fixture. Test count: 450 → 469.

- **Field catalog + scenario contract gate + `ophamin discover-fields` — v0.2 Step 2.**
  ``KIMERA_FIELD_CATALOG`` documents ~35 high-signal OrchestratorResult
  fields with type + semantic family + description (the families: phi,
  walker, gwf, echoform, consolidation, prime, piovra, substrate_state,
  internal_event, lateral_line, eikonal, ouroboros, alexandria,
  realtime_encoder, timing, manipulation, scar, thermodynamic). Scenarios
  opt into a ``field_contract()`` declaring the fields they depend on; the
  base scenario harness validates the contract against the first
  successful cycle's ``raw`` before scoring and raises
  ``ScenarioFieldContractViolation`` (loud failure) on missing-required,
  type-mismatch, or family-mismatch. Default ``field_contract() = None``
  is back-compat — existing scenarios keep working untouched.
  `ophamin discover-fields <repo>` probes one cycle and surfaces the
  three-way diff (in-catalog · uncataloged · missing-from-raw) so
  Kimera-side schema drift is visible at experiment-setup time.
  Retroactively, the ``cycle_seconds``-dropped-on-floor incident
  (2026-05-15) would have failed the contract immediately. 40 new
  hardening tests (33 catalog, 7 scenario gate). Test count: 410 → 450.

- **`KimeraInventory` + `ophamin inventory` — v0.2 Step 1**
  ([`docs/KIMERA_OBSERVATIONAL_SURFACE_2026_05_15.md`](docs/KIMERA_OBSERVATIONAL_SURFACE_2026_05_15.md)).
  Static enumeration of every observable surface in a Kimera-SWM working
  tree, across nine strata: cognitive, interface, transport, persistence,
  reconciliation, temporal, security, telemetry, lifecycle. Pure file
  enumeration — does not import or execute Kimera. Output is a signed,
  content-addressed, HMAC-verified `KimeraInventory` JSON + Markdown
  report. Each stratum's discoverer is independent; absent files report as
  "dormant" rather than crashing. 23 hardening tests in
  `tests/test_kimera_inventory.py`.

  First live measurement against the production Kimera-SWM working tree
  (commit `a0adf1a0`, 2026-05-15): **336 observable surfaces, all 9 strata
  live**. Cognitive: 11 · interface: 104 · transport: 8 · persistence: 42 ·
  reconciliation: 8 · temporal: 36 · security: 64 · telemetry: 35 ·
  lifecycle: 28. This is the empirical baseline against which the next
  v0.2 steps (field projection, Prometheus consumer, per-stratum
  scenarios) can be sized.

### Fixed

- **`AuditRecord.to_markdown` shadow bug** — the loop variable `for path, count
  in s.top_files` shadowed the `path` parameter, causing the audit markdown
  to be written into the LAST hotspot SOURCE file instead of the caller's
  output path. Latent since `to_markdown` landed; surfaced on GitHub Actions
  when the audit workflow ran on `src/ophamin` and corrupted
  `src/ophamin/inspecting/inspector.py` with audit-record markdown content,
  breaking the next Python import. Fix: rename the loop variable; added
  regression test
  `test_audit_record_to_markdown_writes_to_caller_path_not_hotspot_file`.
  Retroactively explains the earlier `vulture_pillar.py` and `schema_miner.py`
  corruption incidents in this session.

## [0.1.0] — 2026-05-15

### Initial release

Ophamin's first published version. The framework is structurally complete
across six wheels in two concentric triads, with three experimentation tiers
exercised against real Kimera-SWM.

#### Architecture

- **Outer triad** — empirical observation:
  - `seeing/` — substrate adapter, corpus connectors, Layer A schema mining
    + many-small-eyes watcher.
  - `measuring/` — pre-registered measurement engines + six analytic pillars
    (O · F · A · M · I · N) + scenarios across three tiers.
  - `comparing/` — Layer C drift detection over signed proof records.
- **Inner triad** — engineering observation:
  - `instrumenting/` Phase 1 — psutil-based per-cycle resource profiler +
    InstrumentedSubstrate wrapper + periodic subprocess sampler.
  - `auditing/` — orchestrated static-analysis pillars (ruff / bandit / mypy /
    vulture / radon / pip-audit) producing signed Audit Records.
  - `reporting/` — multi-format academic output (HTML / Markdown / LaTeX) with
    matplotlib charts.
- **Cross-cutting**:
  - `inspecting/` — generic per-primitive profile (PrimitiveCatalog + Locator
    + Inspector) that scales to 17 catalogued Kimera primitives.
  - `interop/` — standard-format exporters: SARIF 2.1.0, JUnit XML, MLflow
    runs, CycloneDX 1.5 SBOM.
  - `protocols.py` — first-class plug-in surfaces (Pillar / DatasetConnector /
    SubstrateProbe / ScenarioProtocol).

#### Shipped scenarios (six, across three tiers)

| Tier | Scenario | Latest verdict |
|---|---|---|
| Scientific | Concentrated Immune Siege | VALIDATED (GWF FP = 3.2%) |
| Scientific | Rosetta Scaling | REFUTED (0% cross-language agreement) |
| Scientific | Organizational Dissonance | VALIDATED (97.4% active rate) |
| Scientific | Logic-Topology Siege | REFUTED (39.6% sustained traversal) |
| Engineering | Throughput Ceiling | VALIDATED (p95 = 2.357 s) |
| Philosophical | Self-Reference | REFUTED (Cohen's d = -0.359) |

#### Substrate fixes (Kimera-SWM)

Two surgical fixes committed to Kimera during framework development:

- **GPU device-honesty + no-fallback** (Kimera commit `204fb4f9b`): the
  `GPUAcceleratedTrajectoryOptimizer` was CUDA-only on Apple Silicon, silently
  CPU; fix selects cuda → mps → cpu honestly. 5 hardening tests pin the fix.
- **IIT30 EMD closed form** (Kimera commit `9c055d303`): `_emd_hamming` was
  using a HiGHS LP solver where a closed-form sum of per-bit marginals works
  for product distributions; ~10% throughput gain. 4 hardening tests pin the
  fix.

#### Kimera-side empirical record

Six new families backfilled into Kimera's `EMPIRICAL_VALIDATION.md`:

- Family M (adversarial defense stack)
- Family N (Rosetta sentence-scale operating envelope)
- Family O (dissonance-layer active rate on real-world organisational email)
- Family P (walker halt-mode distribution on Linux kernel commits)
- Family Q (engineering throughput ceiling)
- Family R (philosophical self-reference — refuted)

R11 added to "What was refuted" — the substrate fires *less* dissonance on
text describing its own primitives than on neutral Enron email (Cohen's d =
-0.359).

#### CLI surface

```
ophamin demo / run / sweep / probe-kimera / lineage
ophamin discover / discover-diff / watch         (Layer A schema mining)
ophamin drift-report                              (Layer C drift)
ophamin audit                                     (orchestrated audit pillars)
ophamin inspect / inspect-all                     (per-primitive profile)
ophamin report                                    (HTML / Markdown / LaTeX)
ophamin export                                    (SARIF / JUnit / MLflow / CycloneDX)
```

#### Tests

386 tests, all green. Cross-checks against scikit-learn, statsmodels, MAPIE,
prov driven directly.

[Unreleased]: https://github.com/IdirBenSlama/Ophamin/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/IdirBenSlama/Ophamin/releases/tag/v0.1.0
