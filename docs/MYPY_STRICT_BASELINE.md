# Mypy strict baseline (Phase S1)

> **Status:** Stage 1, Phase S1 of the elevation roadmap. Baseline
> captured 2026-05-16 at v0.5.0 + mypy 2.1.0. Remediation lands
> incrementally; see §3 for the per-layer plan.

## 1. Configuration

`pyproject.toml` `[tool.mypy]` sets every strict option that
matters. Source root `src/ophamin/`, target Python 3.12, namespace
packages on. Per-module overrides allow `ignore_missing_imports`
for ~40 upstream libraries that don't ship stubs (river, mapie,
prov, mlflow, omegaconf, pymc, tigramite, …) — these are the
libraries the framework's pillars adapt. The override is per-module,
not global; every Ophamin module sees strict mode.

`src/ophamin/py.typed` marker is present so downstream consumers
see Ophamin's types.

Canonical run command:

```bash
.venv/bin/python -m mypy
```

## 2. Baseline trajectory (2026-05-16)

**Phase S1 CLOSED — 0 errors across 138 files** as of v0.7.0.

| Phase | Date | Errors | Files w/ errors | Files strict-clean |
|---|---|---|---|---|
| Baseline (v0.5.0) | 2026-05-16 morning | 277 | 66 | 72 (no `Any` leakage in 138 − 66) |
| Phase S1.a | 2026-05-16 morning | 220 | 55 | 83 (+9 explicitly pinned in `STRICT_CLEAN`) |
| Phase S1.b | 2026-05-16 afternoon | 195 | 43 | 95 |
| Phase S1.c | 2026-05-16 afternoon | 171 | 28 | 110 |
| Phase S1.d | 2026-05-16 afternoon | 129 | 21 | 117 |
| Phase S1.e (closeout) | 2026-05-16 evening | **0** | **0** | **138 (all)** |

The pre-push hook gate 3 now runs `mypy --strict` against the entire
package; the per-file `STRICT_CLEAN` ratchet is retired.

### Historical — initial per-module error count (top 25, pre-Phase-S1.a)

### Per-module error count — top 25

| Errors | Module |
|---|---|
| 22 | `config/sweep.py` |
| 18 | `measuring/pillars/robustness/cross_validation.py` |
| 15 | `seeing/corpus/connectors.py` |
| 13 | `cli.py` |
| 12 | `interop/mlflow_export.py` |
| 12 | `comparing/provenance/prov.py` |
| 9 | `reporting/chart_helpers.py` |
| 9 | `measuring/pillars/diagnostics/anticipatory.py` |
| 9 | `inspecting/inspector.py` |
| 9 | `campaign.py` |
| 8 | `reporting/html_renderer.py` |
| 8 | `interop/sarif.py` |
| 7 | `comparing/orchestration/experiment.py` |
| 6 | `measuring/pillars/effects/mea.py` |
| 5 | `measuring/timeseries_helpers.py` |
| 5 | `measuring/analytic_helpers.py` |
| 5 | `interop/junit_xml.py` |
| 4 | `registry.py` |
| 4 | `measuring/scenarios/rosetta_scaling.py` |
| 4 | `measuring/scenarios/organizational_dissonance.py` |
| 4 | `measuring/scenarios/logic_topology_siege.py` |
| 4 | `measuring/scenarios/crdt_laws.py` |
| 4 | `comparing/provenance/lineage.py` |
| 4 | `auditing/pillars/fawltydeps_pillar.py` |
| 4 | `auditing/pillars/__init__.py` |

### Error-class clusters (rough triage)

- **Cluster A — missing function annotations** (`no-untyped-def` +
  `no-untyped-call`): ~80 errors. Adding parameter / return-type
  annotations on helper functions. Mechanical.
- **Cluster B — Any-return / Any-assignment** (`no-any-return` +
  `assignment` from Any): ~90 errors. Concentrated in upstream-
  library-adapter paths where Any leaks from untyped 3rd-party
  calls. Needs targeted `cast(...)` calls + explicit local types.
- **Cluster C — generic-without-parameters** (`type-arg`,
  `disallow_any_generics`): ~40 errors. `dict` / `list` / `tuple`
  used without type params; explicit `dict[str, Any]` etc. is the
  fix.
- **Cluster D — actual type bugs** (`assignment` between
  incompatible types, `return-value` shape mismatch): ~30 errors.
  Genuine type defects mypy strict has surfaced.
- **Cluster E — protocol-conformance edge cases** (`type-var`,
  `misc` from Protocol checking): ~37 errors. Mostly in the
  pillar-adapter interface where `Pillar.compute` accepts
  `Iterable[Any]` but adapters narrow it.

## 3. Remediation strategy

Phased + parallelisable. Each phase ends with mypy strict green for
the named files + the full pytest suite still passing.

### Phase S1.a — small-error files (CLOSED 2026-05-16)

Target was every file with ≤ 5 errors. **Result: 277 → 220 errors
(-57)** + 4 files added to the "strict-clean" registry that the
pre-push hook gates on:

- ✅ `protocols.py` — 0 errors (was 0; pinned in strict-clean list)
- ✅ `registry.py` — 4 → 0 (added Path/Callable type-anchors;
  return-type annotations on get_scenario / list_scenarios /
  get_corpus_by_name)
- ✅ `measuring/scenarios/{rosetta_scaling, organizational_dissonance,
  logic_topology_siege, crdt_laws}.py` — 4 each → 0 each (dict
  type-args + Sequence-instead-of-list for invariance-safe helpers +
  Any-instead-of-object on heterogeneous-value dicts)
- ✅ `comparing/provenance/lineage.py` — 4 → 0 (str() coercion on
  Any-return paths from manifest.get + mlflow.run_id)
- ✅ `auditing/pillars/__init__.py` — 4 → 0 (list[AuditPillar])
- ✅ `auditing/pillars/fawltydeps_pillar.py` — 4 → 0 (renamed local
  `line` → `parsed_line` to avoid shadow; declared int|None type)
- ✅ Upstream-library overrides extended: statsmodels, scipy, sklearn,
  matplotlib, psutil added to `[[tool.mypy.overrides]]` (each lacks a
  `py.typed` marker or ships incomplete stubs)
- *Deferred from S1.a (still in S1.b queue):*
  - `measuring/scenarios/base.py` — 3 left (DatasetRef forward-ref +
    untyped dataset_ref call)
  - `measuring/timeseries_helpers.py`, `measuring/analytic_helpers.py`,
    `interop/junit_xml.py` — sub-5-error counts

### Phase S1.b — medium-error files (next turn)

Target: files with 6-15 errors. ~100 errors closed; ~127 remain.

- `measuring/pillars/effects/mea.py` (6)
- `comparing/orchestration/experiment.py` (7)
- `interop/sarif.py` (8)
- `reporting/html_renderer.py` (8)
- `campaign.py` (9)
- `inspecting/inspector.py` (9)
- `measuring/pillars/diagnostics/anticipatory.py` (9)
- `reporting/chart_helpers.py` (9)
- `comparing/provenance/prov.py` (12)
- `interop/mlflow_export.py` (12)
- `cli.py` (13)
- `seeing/corpus/connectors.py` (15)

### Phase S1.c — heavy-error files (turn after that)

Target: ≥ 16-error files. ~40 errors closed; ~87 remain (revised
downward as later passes find common patterns).

- `measuring/pillars/robustness/cross_validation.py` (18)
- `config/sweep.py` (22)

### Phase S1.d — long-tail + invariant tests

Target: ~50 long-tail errors + add structural pytest gate that
mypy strict must stay green. Land hardening test
`tests/test_mypy_strict_clean.py` that fails the suite if mypy
strict regresses on any file currently green.

## 4. CI gate (post-Stage-1)

`.githooks/pre-push` runs `mypy --strict` and fails on any error.
Once the GitHub repo goes public (gate currently held by owner),
the same check runs in GitHub Actions on every PR.

## 5. Tracking

This document updates every time a phase lands. Each row of the
per-module error count gets struck-through when its file hits zero.

---

*Authored by Claude (Opus 4.7 1M context), 2026-05-16, pinning the
mypy strict baseline at the v0.5.0 → v0.6.0 transition.*
