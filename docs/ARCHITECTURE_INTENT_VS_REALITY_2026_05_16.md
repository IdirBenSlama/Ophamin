# Ophamin — initial intent vs. current reality

> **Status:** structural audit, 2026-05-16. Read alongside
> `KIMERA_OBSERVATIONAL_SURFACE_2026_05_15.md` (covers *coverage* gaps —
> what Ophamin doesn't observe yet) and `PLUGIN_CATALOG_2026_05_15.md`
> (covers *tooling* gaps — which external libraries to plug in). **This
> document covers `architecture / structure / infrastructure / logic`
> gaps — places where the framework's declared shape and its built shape
> diverge.**
>
> Scope: only the framework itself (`src/ophamin/`). Substrate-coverage
> work is owner-gated separately.

---

## 0. What "initial intent" means here

Three load-bearing sources describe what Ophamin was *meant* to be:

1. **README §"The architecture — six wheels in two concentric triads"**
   — names the six wheels (`seeing / measuring / comparing /
   instrumenting / auditing / reporting`), the cross-cutting layers
   (`inspecting / interop / protocols.py`), and the angelic-order
   metaphor (Ophanim — wheels within wheels, covered with eyes; *dyson
   sphere around the substrate*).
2. **README §"The six analytic pillars (O · F · A · M · I · N)"** —
   names the OFAMIN initialism that IS the framework's name. Six
   library-backed pillars: scipy + river / prov + mlflow + dvc / SPRT /
   statsmodels MixedLM / statsmodels meta-analysis / scikit-learn
   splitters. **The framework's *name* is the pillar initialism.**
3. **`src/ophamin/protocols.py`** — four plug-in surfaces declared as
   `runtime_checkable` Protocols: `SubstrateProbe`, `DatasetConnector`,
   `Pillar`, `ScenarioProtocol`. Each contract narrow and explicit;
   each declared "registrable" via `isinstance(plugin, ProtocolName)`.

The intent in three sentences:

- **Architecture:** six wheels orbit a substrate; each wheel is
  independently extensible.
- **Pillars:** six library-backed analytics, one statistical method per
  pillar, modular by Protocol.
- **Extensibility:** plug in a new dataset / probe / pillar / scenario
  by satisfying the corresponding Protocol — nothing in the core has to
  change.

---

## 1. What's built today

Grep-verified against the working tree, 2026-05-16:

### Wheels — size + state

| Wheel | LOC | Files | State |
|---|---|---|---|
| `seeing/` | ~4.5K | substrate (4) + corpus (8) + discovery (5) + telemetry (1) + wiring (1) | ✅ rich |
| `measuring/` | ~10K | proof (4) + scenarios (19) + pillars (11) + diagnostics (3) + 6 `*_helpers.py` | ✅ richest wheel |
| `comparing/` | ~1.2K | drift (2) + drift_detection (1) + provenance (2) + orchestration (1) + crdt_state (1) | ⚠ thin given the metaphor |
| `instrumenting/` | ~500 | wrapper + periodic_sampler + resource_metrics | ⚠ thinnest wheel |
| `auditing/` | ~1.8K | runner + base + 12 pillars | ✅ healthy |
| `reporting/` | ~1.2K | html + markdown + latex + chart_helpers + runner + base | ✅ healthy |
| `inspecting/` | ~990 | catalog + inspector + locator + primitive_profile | ⚠ scaffolded, under-used |
| `interop/` | ~600 | sarif + junit_xml + mlflow_export + cyclonedx | ✅ done |
| `protocols.py` | 151 | 4 Protocol declarations | ⚠ declared, not implemented |
| `verify.py` | ~280 | install self-check + CI gate | ✅ done |
| `cli.py` | ~? | 20 `cmd_*` subcommands | ✅ rich |

### Scenarios — registry vs file inventory

- **19 scenario files** in `src/ophamin/measuring/scenarios/`.
- **8 entries** in `SCENARIOS` dict in
  `src/ophamin/measuring/scenarios/__init__.py`.
- **11 scenarios** (bayesian-phi-posterior, causal-discovery, crdt-laws,
  cross-channel-mi, memory-as-deformation, prime-cross-instance,
  prime-direct-lookup, prime-ecosystem, prime-factorization,
  prime-structure, quantum-basis-correlation) are file-importable but
  **CLI-invisible**. They were authored against the `Scenario` base
  class and run via capture scripts at `/tmp/capture_kimera_*.py` —
  outside Ophamin's CLI discipline.

### Pillars — declared shape vs built shape

`measuring/pillars/*/` contains 11 module files, ~2.2K LOC:
`observability/{spc, srm, drift}`, `adaptive/sprt`, `effects/{mea,
mixed_effects}`, `synthesis/cma`, `robustness/cross_validation`,
`diagnostics/{anticipatory, inertia, kernel_coupling}`.

These are **module-level dataclasses + functions**. They are NOT
classes that satisfy the `Pillar` Protocol in `protocols.py`. None of
them declares `pillar_name: str`, `library: str`, `library_version:
str`, or a `compute(...)` method on a class instance. Verified by
grep: zero matches for `pillar_name\s*=` in the pillar directory.

---

## 2. Where intent and reality diverge

Twelve concrete gaps, ordered by structural depth (1–4 = framework core;
5–8 = wheel asymmetry; 9–12 = discipline-uniformity).

### 2.1 Framework-core gaps

**A. `Pillar` Protocol is declared but no implementation satisfies it.**

`protocols.py:Pillar` expects an object with `pillar_name / library /
library_version` attributes and a `compute()` method. The 11 pillar
modules expose functions and dataclasses — `Pillar`-as-an-object
doesn't exist. The runtime check `isinstance(my_pillar, Pillar)` from
the docstring cannot be exercised today.

Consequence: the named promise *"a new Pillar implements the protocol;
nothing inside Ophamin's core has to change"* is rhetorical. Adding a
new pillar today means importing into a specific scenario, not
registering a plug-in.

**B. No central plug-in registry.**

There is no `ophamin.registry` module. There is no
`register_pillar()` / `register_scenario()` / `register_corpus()` /
`register_probe()` function. Scenarios are registered via manual edit
to `SCENARIOS` dict. Corpora via the `get_corpus(name)` lookup function
in `seeing/corpus/__init__.py`. Pillars not registered anywhere.

Consequence: the "wheels within wheels, covered with eyes" image
suggests pluralistic extension. Concretely, the four declared plug-in
surfaces have **zero registration surface area** between them.

**C. Scenarios registry is out of sync with scenario files.**

11 of 19 scenarios are not in `SCENARIOS`. The drift is the gap that
CONTRIBUTING.md step-5 was meant to enforce — the rounds-E-through-M
autopilot did not exercise that step.

A simple structural test that walks `scenarios/*.py`, finds every
`class X(Scenario):` subclass, and asserts every one is in `SCENARIOS`
would close this and prevent recurrence. Such a test does not exist
today.

**D. The OFAMIN initialism no longer fits the built shape.**

The framework name asserts six pillars: **O**bservability ·
**F**ormal-provenance · **A**daptive · **M**ixed-effects ·
**I**terative-synthesis · **N**-fold-robustness.

In reality `measuring/` ships:

- the 6 OFAMIN pillars,
- **plus** 3 substrate-specific cognitive diagnostics
  (anticipatory / inertia / kernel-coupling),
- **plus** 6 helper families (`analytic_helpers`, `bayesian_helpers`,
  `causal_helpers`, `graph_helpers`, `sat_smt_helpers`,
  `timeseries_helpers`) that scenarios pull from but that aren't
  pillars per se,
- **plus** the strategic-doc-proposed but not-yet-landed 4 new
  measuring pillars (L · B · A · Σ — latency, bandwidth,
  availability, correlation) and 3 new auditing pillars
  (schema-audit, api-audit, security-config-audit).

The OFAMIN name was sized for a smaller measurement vocabulary than
what's built and what's proposed. Either:

- the initialism stays as a *historical anchor* (OFAMIN was the
  founding hexad; the framework now exposes pillars more broadly), or
- the pillar-set is reorganized so the count + the name align.

This is naming/branding, not a fix per se — but it's the kind of
structural-intent drift the owner flagged.

### 2.2 Wheel-asymmetry gaps

**E. Inner-triad / outer-triad LOC asymmetry.**

- Outer triad (`seeing` + `measuring` + `comparing`) ≈ **15.7K LOC**.
- Inner triad (`instrumenting` + `auditing` + `reporting`) ≈ **3.5K
  LOC**.

The metaphor said *two concentric triads*; the built shape is
**~4.5× heavier on empirical observation than on engineering
observation**. Specifically:

- `instrumenting/` ships 3 files (~500 LOC). The Tier-2 telemetry
  proposal (Kimera-side OpenTelemetry hooks) is the missing piece on
  this wheel and is owner-gated.
- `reporting/` ships 3 renderers + chart helpers but no `ophamin
  report-batch` command that takes the full `proofs/` directory.
- `auditing/` is the strongest of the three (12 tool pillars + signed
  AuditRecord shape).

**F. `comparing/` is thin given the metaphor.**

The wheel name is "comparing" — the implied job is cross-commit
retrospection over the proof corpus. Today the wheel has 1.2K LOC and
no automated `ophamin compare <commit_a> <commit_b>` command. The
strategic doc's "Layer C drift detection" is partially wired
(`drift_detection/river_detector.py` lands the streaming side; the
batch / corpus-walking side is open).

No `comparing/regression_alert.py` exists. When a Kimera commit
breaks a previously-VALIDATED claim, no Ophamin-paced loop notices
— the operator has to re-run scenarios manually.

**G. `inspecting/` wheel is scaffolded but under-exercised.**

988 LOC across `catalog`, `inspector`, `locator`, `primitive_profile`.
The PrimitiveCatalog has a registration API (`register()`); the
locator resolves classes at runtime; the inspector emits markdown +
JSON. The output is a single static artifact (`primitives_survey.md`).

The metaphor implies *composes the wheels*. In practice the wheel is
its own silo — `inspect` doesn't trigger an `instrument` run, doesn't
fire an `audit` against the inspected primitive's source file, doesn't
produce a signed proof. Composition is named but not built.

**H. `seeing/wiring/` is the youngest sub-wheel and the most
load-bearing for v0.2.**

The WiringProbe lands an inventory + orphan classification + signed
`SubstrateCompleteness` scenario verdict. It already shipped a real
finding (Kimera's 26/323 = 8.05% orphan rate on `domain/prime/`).

Asymmetry: `seeing/wiring/` is *the* surface most tightly coupled to
Kimera (it walks the Kimera tree directly, not via the substrate
adapter). The framework intent of "independent of Kimera except for
KimeraAdapter" is softer than the README states: `seeing/wiring/`,
`seeing/discovery/`, and `seeing/telemetry/PrometheusScrapeProbe`
also reach into Kimera shapes. Not wrong, but the README claim of
"only one Kimera-coupled file" is stale.

### 2.3 Discipline-uniformity gaps

**I. Pre-registration discipline applies to scenarios only.**

CONTRIBUTING.md ground rule #3: *"Pre-registration discipline. A new
scenario MUST capture its claim, threshold, and analysis plan BEFORE
the substrate runs."*

Concretely applied to scenarios → signed `EmpiricalProofRecord` with
9 sections.

Not applied to:

- **Audit pillars** — `AuditRecord` is signed and content-addressed
  but has no pre-registered claim (the implicit claim is "count
  findings, classify by severity").
- **Drift scans** — `DriftScan` artefact from `drift_detection/` is
  signed but pre-registers nothing.
- **Discovery records** — Layer A schema-mining outputs are not
  signed at all.
- **Inventory / wiring** — WiringProbe emits JSON + Markdown; the
  signed-verdict path is via the `SubstrateCompleteness` scenario,
  which IS a scenario. WiringProbe-as-tool has no pre-reg of its own.

Consequence: the framework's most distinctive promise (anti-p-hacking
pre-registration) is non-universal. A drift-detection threshold can be
tuned after a scan without breaking any discipline; a scenario
threshold cannot.

**J. No master proof manifest.**

`proofs/` carries 28 signed records on disk. No `proofs/index.json`
catalogues them. The `comparing/drift/proof_index.py` builds one at
runtime but doesn't persist it. A `ophamin proof-list` command does
not exist.

For a framework whose *whole point* is signed-content-addressed
proof records, the absence of a master manifest is a real shape gap.

**K. CLI surface is wide but uneven in producing signed artifacts.**

20 `cmd_*` subcommands. Some produce signed artifacts (`audit`,
`drift-detect`, `wiring`, `discover`); some don't (`inspect`,
`inspect-all`, `report`, `export`, `verify`, `lineage`). The README
narration implies every observation lands as a signed artifact; the
implementation is split.

**L. The Protocol→Test→Implementation chain has gaps.**

The four `protocols.py` Protocols are declared `runtime_checkable`
but there's no test that asserts:

- every `Scenario` subclass appears in `SCENARIOS`,
- every Corpus is reachable via `get_corpus`,
- every Pillar implementation satisfies `isinstance(p, Pillar)`,
- every SubstrateProbe satisfies `isinstance(s, SubstrateProbe)`.

Such tests would catch (A), (B), (C) at every PR and prevent the
drift they currently codify.

---

## 3. The architectural shape this points at

If the gaps in §2 had to be named as ONE shape, it would be:

> Ophamin's **measurement output** ran ahead of its **plug-in
> infrastructure**. The scenarios shipped (19), the audit pillars
> shipped (12), the corpora shipped (~8) — all real. The
> Protocol/registry/discovery layer that was meant to make these
> plural and discoverable is roughly half-built.

The implication is not that Ophamin is wrong-shaped — it's that the
*scaffolding to make Ophamin a true plug-in framework* (which is the
literal claim in README §"Design notes" + protocols.py) is the next
load-bearing pass.

## 4. Remediation shapes — options, not rankings

Five different shapes the next pass could take. Owner picks.

**Shape 1 — Close the registry surface (3–5 sessions).**

Land the missing scaffold:

- `ophamin/registry.py` — central `register_pillar / register_scenario
  / register_corpus / register_probe` API with name uniqueness +
  Protocol-conformance checks.
- Replace `SCENARIOS` dict in `scenarios/__init__.py` with an auto-walk
  that discovers every `Scenario` subclass in the package + registers
  it via the new registry. Same shape for corpora and probes.
- Wrap each existing pillar module in a thin `class XxxPillar:` that
  satisfies the Pillar Protocol (the *minimum* surface — `pillar_name`
  + `library` + `library_version` + `compute()`). Leaves the module
  functions intact.
- Add four structural tests: every Scenario in `SCENARIOS`; every
  Corpus reachable; every Pillar passes `isinstance`; every Probe
  passes `isinstance`.

Net result: the Protocol surface in `protocols.py` becomes
load-bearing instead of decorative. New plug-ins land via Protocol
satisfaction. The framework name (OFAMIN, *wheels covered with eyes*)
matches the built reality.

**Shape 2 — Universalize the pre-registration discipline (2–3
sessions).**

Apply the signed `EmpiricalProofRecord` shape to every artifact
Ophamin emits:

- `AuditRecord` gains a pre-registered `Claim` ("LOC × maintainability
  index ≥ X", "no findings above CRITICAL", etc.) per pillar.
- `DriftScan` gains a pre-registered `Threshold` (the alarm trigger).
- WiringProbe gains a `WiringClaim` distinct from the wrapping
  `SubstrateCompleteness` scenario.
- Discovery records become signed (Layer A schema is itself a content
  hash).

Net result: the framework's distinctive epistemic promise applies
uniformly. Every artifact answers "what claim does this falsify or
sustain?"

**Shape 3 — Fill the inner-triad asymmetry (4–6 sessions).**

Bring `instrumenting/auditing/reporting` to parity with the outer
triad:

- `instrumenting/`: land the Tier-2 telemetry hook on the Kimera side
  (owner-gated) OR build `scalene` / `viztracer` integration as
  external profilers (no Kimera dep).
- `reporting/`: add `ophamin report-batch <proofs-dir>` that emits a
  campaign-level HTML + Markdown + LaTeX summary across many records.
- `auditing/`: add pre-registered audit claims per Shape 2.

Net result: engineering observation gets the same density as empirical
observation. The two-concentric-triads metaphor stops being
asymmetric.

**Shape 4 — Build the closed-loop / regression-alert side (2–4
sessions).**

The feedback memory says *"Ophamin measures to FIX/optimize/enhance
Kimera, not measure-only; closed loop measure→fix→re-measure"*.
Today the loop is operator-paced. Concrete pieces:

- `comparing/regression_alert.py` — re-runs all VALIDATED scenarios
  against a new Kimera commit; emits a `RegressionAlert` artefact when
  any verdict changes.
- `comparing/proof_index.py` persisted as `proofs/index.json`; rebuilt
  on every new proof.
- `ophamin watch-kimera` — daemon that polls Kimera's HEAD, fires
  regression alert on change.
- `ophamin compare <commit_a> <commit_b>` — explicit batch comparator
  across the full proof corpus.

Net result: the loop runs without an agent driving it. Failures
surface in seconds, not days.

**Shape 5 — Doc-only-first cut (0.5 sessions).**

Land what just happened in this session (README + CONTRIBUTING +
SCENARIO_AUTHORING + protocols.py updates) and this architecture
document as a 0.2.0-doc release. Cut the CHANGELOG `[Unreleased]`
block as `[0.2.0] — 2026-05-16`. Decide on shape 1–4 *next* session.

---

## 5. Honest unknowns

- **Test count discrepancy.** I counted 842 test function definitions
  via grep; CLAUDE.md cites 845 passed at Round M close. The 3-test
  delta is small (perhaps fixtures or `pytest.mark.parametrize`); I
  used "842+" in the README badge to be conservative. A real `pytest
  -q --co -q | tail -5` against this venv would give the canonical
  count; I haven't run it in this session.
- **Whether the unregistered scenarios are intentionally CLI-invisible.**
  The 11 unregistered scenarios are autopilot-output that talks to
  captured Takwin trajectories, not live substrate. They may have been
  deliberately kept off the standard CLI because they require captured
  artefacts at specific paths. Worth checking with the author of round
  E-M (likely a prior session) before mechanically adding them.
- **Whether the `Pillar` Protocol unimplementation is bug or
  intentional**. It may be that the Protocol was declared as
  *aspirational*: a contract a future plug-in author would satisfy,
  but the in-house pillars stay functional. If so, the protocol should
  say so explicitly (the docstring note I added in this session
  makes the gap visible but doesn't resolve the intent question).
- **Strategic-reframe authorization status.** The 2026-05-15 strategic
  docs are clearly labelled as awaiting owner decision. If those land,
  4 new measuring pillars + 3 new auditing pillars are coming — which
  is the load-bearing reason to fix the registry surface FIRST (Shape
  1) before scaling the pillar count.
- **Branch / PR / multi-session state.** I haven't run
  `gh pr list` against the IdirBenSlama/Ophamin repo or checked for
  in-flight work in other worktrees. The parallel-session-hygiene
  rules from Kimera-side apply here too — verify before acting on
  anything beyond docs.

---

## 6. What changed in this session

Doc-currency pass (this session):

- **`README.md`** — test badge 386 → 842+; scenarios table expanded
  from 6 to 19 across 5 tiers; CLI surface updated (added `verify`,
  `discover-fields`, `inventory`, `wiring`, `drift-detect`, `scrape`);
  optional-extras table expanded from 8 to 20 entries; repository
  structure tree refreshed; Phase-2-telemetry note updated;
  strategic-doc pointer added.
- **`CONTRIBUTING.md`** — test counts 551/386 → 842+; install line
  updated to `[all,dev]`; scenario-registration note made
  load-bearing-explicit.
- **`docs/SCENARIO_AUTHORING.md`** — stale import paths fixed
  (`ophamin.scenario.*` → `ophamin.measuring.scenarios.*`); corpus +
  target lists updated; "four shipped" → "19 shipped"; new scoring
  shapes catalogued (distribution-floor / Bayesian-posterior /
  causal-graph / cross-channel-MI / cross-instance).
- **`src/ophamin/protocols.py`** — docstrings updated for Pillar +
  ScenarioProtocol to point at the unimplementation gaps documented
  here.
- **This document** — new architectural intent-vs-reality review.

Substrate code not touched. No version cut. CHANGELOG not edited
(`[Unreleased]` remains; owner picks whether to cut 0.2.0).

---

*Authored by Claude (Opus 4.7 1M context), 2026-05-16. Awaiting owner
decision on which remediation shape — or which combination — to
pursue.*
