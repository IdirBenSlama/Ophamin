# Changelog

All notable changes to Ophamin will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project follows [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

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
