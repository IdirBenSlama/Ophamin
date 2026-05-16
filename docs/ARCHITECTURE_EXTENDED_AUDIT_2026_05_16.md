# Ophamin — extended architecture audit (owner observations, 2026-05-16)

> **Status:** structural follow-up to
> `docs/ARCHITECTURE_INTENT_VS_REALITY_2026_05_16.md` (twelve framework
> gaps) and the doc-currency pass that preceded it. This document covers
> the **additional architectural observations** the owner verbalized
> after the first audit:
>
> > *"first i'm not sure we have the entire architecture implemented.
> > that's include, the 6 phases, output formats, organization folder,
> > data separation and labeling. Experiment classifications, with goals
> > and explanations, summarization and analysis and diagnose,
> > visualizations, charts, statistics… etc etc. tools are missing,
> > output format encoder and decoder."*
>
> Plus a closure note on scenario-registration automation (gap **C**
> from the prior audit) which landed in this session.

---

## 0. Closure: scenario auto-registration (gap C from prior audit)

Closed 2026-05-16. `Scenario.__init_subclass__(cls, *, register=True)`
in `src/ophamin/measuring/scenarios/base.py` registers every concrete
subclass into the module-level `SCENARIOS: dict[str, type[Scenario]]`
at class-definition time. `scenarios/__init__.py` auto-walks all
modules in the package via `pkgutil.iter_modules` so the hook fires
exhaustively. Loud-failure guards for sentinel-name and duplicate-name
collisions. `register=False` opt-out for abstract intermediate
parents and test-internal Scenario subclasses.

Net result: the 11 previously-CLI-invisible scenarios from rounds
E-through-M are now first-class citizens. `SCENARIOS` carries 19 entries
exactly matching the on-disk file inventory.

Test surface: `tests/test_scenario_registration.py` (11 structural
tests). Full suite: **857 passed / 1 skipped / 0 failed**.

---

## 1. The owner's eight observations — current code state

Eight surface-level concerns mapped to specific code state, with the
gap each one names.

### 1.1 *"the 6 phases"*

The phrase "6 phases" has no current corollary in the codebase.
Verified: `grep -i "phase" src/ophamin/{cli,protocols,__init__}.py`
returns zero hits. The wheel-as-phase mapping is implied by the
README's *six wheels in two concentric triads* metaphor:

| # | Wheel | Phase verb |
|---|---|---|
| 1 | `seeing/` | sense |
| 2 | `measuring/` | test claim |
| 3 | `comparing/` | drift / retrospect |
| 4 | `instrumenting/` | profile cost |
| 5 | `auditing/` | engineering debt |
| 6 | `reporting/` | output |

But no command runs all six in sequence as one coordinated pass.
Each wheel has its own CLI subcommand; their outputs are
content-addressed but uncorrelated. There is no `RunRecord` /
`CampaignRecord` artifact that says *"this single pass exercised
wheels 1-through-6 against substrate X at commit Y."*

**Gap:** no composite-run primitive. Owner-flagged item is real.

**Shape:**
- A `Run` / `Campaign` aggregate carrying a tuple of phase outputs;
- A `cli` entry `ophamin run-all <kimera-repo> [--scenarios=...]` that
  fires the six wheels in order;
- A signed `CampaignRecord` (composite of: DiscoveryRecord +
  EmpiricalProofRecord×N + ComparisonRecord + InstrumentRecord +
  AuditRecord + ReportRecord) with cross-references between the
  per-wheel artifacts.

### 1.2 *"output formats"*

**Current state:**

| Layer | Outputs | LOC |
|---|---|---|
| `reporting/` | HTML / Markdown / LaTeX renderers + chart helpers | 1282 |
| `interop/` | SARIF / JUnit-XML / MLflow / CycloneDX exporters | 1094 |

Total: **~2.4K LOC, 7 output formats.**

What's MISSING:

- **JSON-LD output.** The proof record IS a labeled graph (claim →
  evidence → dataset → substrate); a JSON-LD output would let it
  integrate with semantic-web / SPARQL tooling. `prov` is already a
  dep (W3C PROV-O is a JSON-LD dialect).
- **CSV / Parquet output for proof corpora.** A flat file of
  `(scenario, tier, family, threshold, observed, verdict, ci_low,
  ci_high, commit, run_date)` rows is the most natural shape for
  cross-corpus analysis tools (pandas / DuckDB / BI). Today nobody can
  do `pd.read_csv("proofs.csv")` on the proof corpus.
- **Plain-text summary.** No `ophamin report --format text`; useful
  for terminals / CI logs / git commit messages.
- **PDF.** LaTeX renderer exists but no `tectonic`-or-equivalent path
  to a one-shot PDF.
- **Slack / Discord-formatted summary.** For team broadcast on
  campaign completion.

### 1.3 *"organization folder"*

**Current state:**

```
proofs/    — 28 records, FLAT layout, no subdirs
audits/    — 2 records, FLAT layout, no subdirs
reports/   — mixed .html .md .tex + assets/, FLAT
logs/      — flat .log files (5)
mlruns/    — standard MLflow layout (numeric experiment IDs)
data/      — data/raw/ + data/zeta_zeros/, no per-corpus subdirs convention
models/    — models/kimera_state/ only, no other models
lineage/   — explicit dir doesn't exist (under mlruns/)
```

What's MISSING:

- **No README** in any of `proofs/`, `audits/`, `reports/`, `logs/`,
  `data/`, `models/` explaining the layout convention.
- **No per-tier / per-family / per-date subdir scheme.** Adding a 100th
  proof to `proofs/` makes finding the right one painful (relies on
  filename grep).
- **No `proofs/INDEX.md` / `proofs/index.json` master manifest** (gap J
  from the prior audit; reiterated here).
- **`reports/assets/` is dropped flat** — no per-scenario subdir.

**Suggested convention** (proposal, owner-pick):

```
proofs/
  scientific/
    immune_siege/
      2026-05-15_kimera-9596c681_0a0575db92c0.json
      2026-05-15_kimera-9596c681_0a0575db92c0.md
    ...
  engineering/
  philosophical/
  empirical_deep/
  measurement_machinery/
  INDEX.md                       ← master manifest
  README.md                      ← convention + sign-key + schema-version refs
```

### 1.4 *"data separation and labeling"*

**Current state:**

- `data/raw/` carries corpora; in `.gitignore`.
- `data/zeta_zeros/` carries one specific dataset.
- No `data/processed/`, no `data/labelled/`, no `data/fixtures/`.
- Corpora are loaded via `seeing/corpus/<corpus>.py` — labelling
  (benign vs adversarial, training vs eval) is corpus-specific and
  not standardized across corpora.

What's MISSING:

- A canonical **data-class taxonomy** (raw / processed / labelled /
  derived / fixtures) with a `DataClass` enum on each `Corpus`
  declaration.
- A canonical **dataset card** per corpus (one-page Markdown:
  source / license / size / labels / known biases / how to refresh
  via Makefile). HuggingFace `datasets` convention is the precedent.
- A `data/README.md` explaining the layout and the refresh commands.
- Per-`DatasetRef.kind` validation at registration: only declared
  kinds (`adversarial_corpus`, `parallel_translation_corpus`,
  `email_corpus`, `commit_history_corpus`, `physics_simulation_hdf5`,
  `synthetic_self_referential`, …) are accepted.

### 1.5 *"experiment classifications, with goals and explanations"*

**Current state:**

The `Scenario` base class has FOUR class attributes:

```python
class Scenario(abc.ABC):
    name: str = "scenario"
    corpus_name: str = ""
    target: str = "entity"
    n_cycles: int = 1000
```

That's it. No `tier`, `family`, `goal`, `explanation`, `method`,
`falsification_consequence` fields.

Tier / family classification lives:

- in `scenarios/__init__.py`'s docstring (read by humans, never by
  code),
- in the README's scenarios table (read by humans, never by code),
- in `EMPIRICAL_VALIDATION.md` over in Kimera-side (Family A-V).

Goals + explanations live:

- only in scenario file docstrings (some have multi-paragraph
  motivation blocks, others have one line).

**Gap is fundamental:**

The framework's epistemic discipline says *every claim must be
falsifiable + pre-registered*. But the BROADER framing (what tier of
question? what family of scenario? what would a REFUTED verdict
ACTUALLY mean for Kimera?) is unstructured. A consumer of a
`EmpiricalProofRecord` JSON file today cannot answer *"what tier
does this scenario live in?"* without out-of-band context (the
scenario's docstring, the README, or human memory).

**Proposed Scenario metadata schema:**

```python
class Tier(str, Enum):
    SCIENTIFIC = "scientific"
    ENGINEERING = "engineering"
    PHILOSOPHICAL = "philosophical"
    EMPIRICAL_DEEP = "empirical_deep"
    MEASUREMENT_MACHINERY = "measurement_machinery"


class Scenario(abc.ABC):
    name: str = "scenario"
    tier: Tier                      # NEW — required
    family: str                     # NEW — required; e.g. "immune", "prime", "phi"
    goal: str                       # NEW — required; one-sentence "what does this answer?"
    explanation: str                # NEW — required; paragraph "why this matters"
    method: str = ""                # NEW — optional; one-line scoring-shape tag
    falsification_consequence: str = ""  # NEW — optional; "what would REFUTED mean?"
    corpus_name: str = ""
    target: str = "entity"
    n_cycles: int = 1000
```

Validation: `__init_subclass__` raises if `tier` / `family` / `goal` /
`explanation` are unset (loud-failure-by-design).

Net result:

- `EmpiricalProofRecord` carries the tier / family / goal in its
  identity section.
- README scenarios table auto-generated from registry.
- `proofs/` can be organized by tier/family programmatically.
- `ophamin scenario list` can produce a sorted hierarchy.

### 1.6 *"summarization and analysis and diagnose"*

**Current state:** ZERO `cmd_summarize` / `cmd_analyze` / `cmd_diagnose`
in `cli.py`.

What's MISSING:

- `ophamin summarize <proofs-dir>` — campaign-level synthesis (e.g.
  "12 of 19 scenarios VALIDATED, 5 REFUTED, 2 INCONCLUSIVE; by tier:
  …; by Kimera commit: …; longest-running scenario: …").
- `ophamin diagnose <proof.json>` — per-record diagnostic ("verdict
  REFUTED at 0.0% vs threshold 80%; observed CI [0%, 16%]; closest
  passing claim at this metric was …; same scenario at commit X
  reported …").
- `ophamin analyze <metric> --across <proofs-dir>` — single-metric
  trajectory across the proof corpus.

These are FIRST-class operations on the proof corpus that the
framework's epistemic discipline naturally invites — and that don't
exist.

### 1.7 *"visualizations, charts, statistics"*

**Current state:** `reporting/chart_helpers.py` is 215 LOC,
matplotlib-backed. Four PNG charts exist in `reports/assets/`
(`ci_dissonance_active_rate_on_cleared.png`, `hotspots.png`,
`per_pillar.png`, `severity.png`). HTML / Markdown / LaTeX renderers
embed them.

What's MISSING:

- A **canonical chart spec per scenario** — every scenario should
  declare which charts its proof record should produce (e.g.
  scenario.chart_spec = ["wilson_ci_bar", "per_record_histogram"]).
  Today chart selection is scenario-renderer-coupled.
- **Cross-scenario / campaign-level charts** — e.g. a verdict
  Sankey across all scenarios in a campaign; a per-commit Φ
  trajectory line chart; a tier×family matrix heatmap.
- **Interactive output** (plotly / bokeh / altair) — current charts
  are static PNG. For exploration of 28+ proof records,
  interactivity is the natural shape.
- **Statistical summary tables** in proof Markdown — currently they
  embed the chart but not the underlying table.

### 1.8 *"output format encoder and decoder"*

**Current state:**

- `to_dict()` / `from_dict()` exist on every component dataclass
  (Threshold, Claim, PreRegistration, DatasetRef, PillarEvidence,
  EmpiricalProofRecord).
- `proof/schema.json` exists.
- `EmpiricalProofRecord.sign()` is HMAC-SHA256 + content-hashing.
- `_canonical_json_dumps` produces sort-keyed deterministic JSON.

What's MISSING:

- A **single-call convenience layer**: `EmpiricalProofRecord.dump(path)`
  / `EmpiricalProofRecord.load(path)`. Today: every consumer does
  `json.loads(Path(p).read_text())` then `from_dict()` by hand.
- A **schema-validating loader** — load a JSON file, validate it
  against `proof/schema.json`, AND verify its HMAC signature, all in
  one call. Today these three checks are uncoupled.
- A **format codec module** at `ophamin/measuring/proof/codec.py`
  that bundles dump / load / validate / verify / migrate (version-up
  shim if schema_version drifts) as one interface.
- **`ophamin proof` subcommands** — `ophamin proof show <path>`,
  `ophamin proof verify <path>`, `ophamin proof validate <path>`,
  `ophamin proof ingest <path>` (the last for accepting a
  third-party Ophamin-shape proof — closes the bidirectional gap the
  interop layer doesn't address).
- Same pattern needed for `AuditRecord` (auditing/audit_record.py)
  and `DriftScan` (comparing/drift_detection/river_detector.py).

### 1.9 Bonus surfaces from the survey

While surveying, three additional gaps surfaced that fit the
owner's "etc etc" tail:

- **Examples coverage.** 10 example runners exist in `examples/` vs
  19 production scenarios — 9 scenarios lack runners. Round-E-to-M
  scenarios all use `/tmp/capture_kimera_*.py` scripts that aren't
  in version control.
- **No `cmd_scenario`.** The CLI has `run / sweep / probe-kimera /
  …` but no first-class `ophamin scenario <name>` that takes the
  scenario name and dispatches to the registry. With registration
  now automatic (per §0), this command is a 10-line addition.
- **No per-corpus dataset card.** `seeing/corpus/<corpus>.py`
  carries the loader; no companion `.md` documents the corpus's
  shape, license, size, labels.

---

## 2. Synthesis — what the eight items have in common

The eight items are not unrelated. They cluster into **three
architectural deficits**:

**Deficit 1 — Scenario metadata is unstructured.** (Items 1.5, partial
1.3, partial 1.4, partial 1.6, partial 1.7.)

A `Scenario` carries 4 fields. The tier, family, goal, explanation,
method, falsification-consequence all live in unstructured docstrings
or out-of-band tables. Every downstream item (organization,
summarization, visualization, README generation) requires this
structure.

**Deficit 2 — Composite-run / phase orchestration is missing.** (Items
1.1, partial 1.2, partial 1.6.)

Each wheel runs independently. No `CampaignRecord` aggregates a
single coordinated pass. The "6 phases" the owner referenced has no
runtime corollary. Composite summarization / cross-wheel diagnosis
requires this.

**Deficit 3 — The proof corpus has no first-class interface.** (Items
1.2 partial, 1.6 partial, 1.8.)

Proof records are signed JSON on disk, but there is no
`ProofCorpus` / `ProofIndex` / `ProofCodec` module. Loading,
validating, querying, summarising, diagnosing all happen ad-hoc.

The other items (1.3 folder organization, 1.4 data labeling, 1.7
visualizations, 1.9 example runners + cmd_scenario + dataset cards)
are mechanical and largely-dependent on Deficits 1 + 3 being closed
first.

---

## 3. Sequenced plan — options, not rankings

Six concrete next moves. Each is independently shippable; each
unlocks the next. Owner picks the cut-off.

**Move A — Scenario metadata fields (close Deficit 1).**

Add `tier: Tier` + `family: str` + `goal: str` + `explanation: str`
+ `method: str = ""` + `falsification_consequence: str = ""` to
`Scenario` base. Make `tier / family / goal / explanation` required
via `__init_subclass__` (extension of the existing hook).
Backfill values on all 19 existing scenarios.

- Net: ~250 LOC across base.py + 19 scenarios + 8 new
  hardening tests.
- Effort: 1 session.
- Unlocks: organization-by-tier, README auto-generation, scenario
  classification index, per-tier summarization.

**Move B — Proof codec module + `ophamin proof {show,verify,validate,ingest}` (close Deficit 3, half-A).**

New `src/ophamin/measuring/proof/codec.py` exposing `dump(record,
path)` + `load(path) -> EmpiricalProofRecord` + `validate(path) ->
ValidationReport` + `verify_signature(path, key) -> bool` + `ingest(path) ->
EmpiricalProofRecord`. New `cmd_proof` umbrella subcommand with
`show / verify / validate / ingest / list` subactions.

- Net: ~400 LOC + ~20 hardening tests.
- Effort: 1 session.
- Unlocks: summarization, diagnostic CLI, third-party proof ingest.

**Move C — Folder organization + per-artifact-dir README (mechanical).**

`proofs/` reorganized into `proofs/<tier>/<family>/` subdirs (uses
Move A's metadata). `audits/`, `reports/`, `logs/` similarly. Each
dir gets a `README.md` declaring its layout convention.
`proofs/INDEX.md` master manifest auto-generated from the corpus +
the codec from Move B.

- Net: ~150 LOC + reorganization (existing 28 proofs relocate by
  git mv).
- Effort: 0.5 session.
- Unlocks: navigability, master-manifest discoverability.

**Move D — `ophamin summarize` + `ophamin diagnose` + `ophamin analyze`
(close Deficit 3 second half).**

Three new CLI subcommands using Move B's codec + Move A's metadata
+ Move C's index. Summarize produces campaign-level synthesis;
diagnose produces per-record explanation; analyze produces
per-metric trajectory.

- Net: ~600 LOC + ~30 hardening tests + new
  `comparing/synthesis.py` + `comparing/diagnostic.py`.
- Effort: 2 sessions.
- Unlocks: epistemic-discipline closure at the campaign layer.

**Move E — Examples + dataset cards + cmd_scenario (mechanical).**

Backfill 9 missing example runners. Write per-corpus dataset cards.
Add `cmd_scenario <name>` to CLI surface (one-liner now that
registration is automatic).

- Net: ~500 LOC examples + ~6 dataset cards + 30-line CLI command +
  ~10 hardening tests.
- Effort: 1 session.
- Unlocks: first-time-user onboarding parity across scenarios.

**Move F — Composite-run / six-phase pass (close Deficit 2).**

`CampaignRecord` aggregate + `ophamin run-all <kimera-repo>`
orchestrator + new `comparing/campaign.py` module. Runs the six
wheels in order, produces a single signed composite artifact with
cross-references.

- Net: ~700 LOC + ~25 hardening tests + design proposal first
  (six-phase ordering, partial-failure semantics, per-phase opt-out
  flags).
- Effort: 2-3 sessions, plus design pass.
- Unlocks: the owner-named "6 phases" intent.

**Suggested order:** A → B → C → E → D → F.

A unlocks the structural metadata everything else needs.
B unlocks the codec the summarization layer needs.
C is mechanical and parallel-safe with B.
E is mechanical and parallel-safe with anything.
D requires A + B + C.
F is the biggest design lift; do last when the foundations are in place.

---

## 4. What I'm landing this session

**Move A — landed 2026-05-16.** Scenario metadata schema (`tier:
Tier` + `family: str` + `goal: str` + `explanation: str` + optional
`method` / `falsification_consequence`) added to `Scenario` base
with class-definition-time validation in `__init_subclass__`. All 19
scenarios backfilled with their tier + family + paragraph goal +
explanation + method tag + falsification consequence. 11 metadata-
validation tests added. Test suite **857 → 869 passed (+12)**, 1
skipped, 0 failed.

Tier distribution across the 19 scenarios:

| Tier | Count | Scenarios |
|---|---|---|
| SCIENTIFIC | 7 | immune-siege, rosetta-scaling, organizational-dissonance, logic-topology-siege, interface-contract-stability, substrate-completeness, memory-as-deformation |
| ENGINEERING | 1 | throughput-ceiling |
| PHILOSOPHICAL | 1 | philosophical-self-reference |
| EMPIRICAL_DEEP | 9 | bayesian-phi-posterior, causal-discovery, cross-channel-mi, prime-structure, prime-factorization, prime-ecosystem, prime-direct-lookup, prime-cross-instance, quantum-basis-correlation |
| MEASUREMENT_MACHINERY | 1 | crdt-laws |

Family distribution: prime (5), dissonance (2), memory (1), walker
(1), interface (1), completeness (1), immune (1), rosetta (1),
throughput (1), self_reference (1), phi (1), causal (1),
mutual_information (1), quantum (1), crdt (1) — 15 families across
19 scenarios.

**Open**: the new metadata is not yet surfaced into
`EmpiricalProofRecord`'s identity / claim sections — that's Move B's
codec-layer work.

After A landed, pausing for owner-pick on B onward (per the
sequenced plan in §3).

---

## 5. Honest unknowns

- **"6 phases" interpretation.** The wheel-as-phase mapping I drew
  in §1.1 is my best guess. If the owner has a different concept in
  mind (e.g. scenario-internal lifecycle phases, or a
  measurement-protocol cadence I haven't seen named), the
  Move-F shape changes. Worth a sentence of clarification before
  committing to Move F's design.
- **Whether the `EmpiricalValidation`-style 5-tuple format (claim →
  operationalization → threshold → result → artifact) used in
  Kimera-side `EMPIRICAL_VALIDATION.md`** should be mirrored as a
  first-class output format here. It's already implicit in
  `EmpiricalProofRecord`'s structure; surfacing it as `--format
  five-tuple-md` is one option.
- **Whether to cut 0.2.0 before or after Moves A-F.** Doc-only-first
  (Move 5 from the prior audit) would land at 0.2.0; substantive
  code work would land at 0.3.0. Today the `[Unreleased]` block
  carries ~970+ lines including this session's work.
- **Parallel-session state on the Ophamin repo.** I have not run
  `gh pr list` against IdirBenSlama/Ophamin or checked for in-flight
  branches. The parallel-session-hygiene rules apply — verify before
  starting Move B+ in case someone else is already there.

---

## 6. Tie-in with the prior architecture audit

The prior audit's 12 framework-core / wheel-asymmetry /
discipline-uniformity gaps + this audit's 3 deficits cluster
together. Two specific cross-references:

- Prior gap **B** (no central plug-in registry) and Move A here both
  want `__init_subclass__`-style validation hooks. Same machinery,
  different surface.
- Prior gap **I** (pre-registration discipline applies only to
  scenarios) and Moves B + D here both want a uniform artifact codec.

A v0.2 cut that landed prior-gap-A's registry surface PLUS this
audit's Move A's metadata fields PLUS Move B's codec would close
~half of both audit lists in one coherent pass.

---

*Authored by Claude (Opus 4.7 1M context), 2026-05-16. Moves A
landed this session; Moves B-F awaiting owner pick.*
