# Ophamin elevation roadmap — from working to solid + legit

> **Status:** strategic plan, 2026-05-16. Written after every open item
> from the prior architecture audits had been closed (Moves A through
> N, ending at v0.4.0). The framework now does what the README + the
> protocols.py + the architectural docs say it does. This roadmap is
> the next-stage question:
>
> > *How do we elevate Ophamin to something more solid and legit?*
>
> "Solid" is internal: would survive a hostile code review by a
> distributed-systems team. "Legit" is external: would survive a
> hostile review by an academic / engineering audit body.
>
> **Owner-locked constraints (2026-05-16):**
>
> 1. **Open-source.** The framework ships under the Apache License
>    2.0 (see `LICENSE` + `NOTICE`). Every elevation phase assumes
>    public-OSS posture: public docs site, public CI, DOI-citable,
>    community-shaped RFC process, validation studies open to
>    third-party replication.
> 2. **Do not rename Ophamin.** The name (from the angelic order
>    Ophanim — "wheels within wheels, covered with eyes") is the
>    framework's stable identifier. Architectural changes happen
>    under the existing name; downstream forks that diverge
>    architecturally choose their own name rather than retaining
>    "Ophamin" (codified in `NOTICE`).
>
> These two constraints lock in the full 4-stage elevation plan
> (~20–30 sessions). The §7 license-decision question below is now
> resolved: open-source.

---

## 0. Where we are

The framework's *epistemic shape* is finished:

- **6 wheels** (seeing / measuring / comparing / instrumenting /
  auditing / reporting) all produce signed artifacts.
- **4 plug-in Protocols** (Pillar / ScenarioProtocol / DatasetConnector
  / SubstrateProbe) all have a registration + discovery surface.
- **42 CLI subcommands** covering scenario / proof / audit-record /
  pillar / corpus / substrate / drift-detect / watch-proofs / inspect /
  inspect-all / report / report-batch / summarize / diagnose / analyze /
  run-all + 26 others.
- **5 result-record types** (EmpiricalProofRecord, AuditRecord,
  DriftScan, RegressionAlertRecord, CampaignRecord) all signed +
  content-addressed + HMAC-verifiable + JSON-round-trippable.
- **1,148 tests passing** across 32+ test files; 0 failures.

What's NOT there yet:

- The framework runs against ~10% of Kimera's observable surface
  (per `docs/KIMERA_OBSERVATIONAL_SURFACE_2026_05_15.md` — measurement
  coverage, not framework architecture).
- No external validation against another framework or ground-truth
  benchmark.
- No published doc site, no DOI, no public CI, no security policy.
- No formal types contract (mypy passes but isn't enforced strict).
- No performance benchmarks pinned.
- No formal RFC process for design changes.

---

## 1. What "solid" means + 6 phases that get us there

**Phase S1 — type-checked end-to-end (mypy strict).**

- Configure `mypy --strict` for `src/ophamin/`.
- Resolve type-errors layer-by-layer: protocols → registry →
  measuring/proof → comparing/synthesis → comparing/regression_alert
  → comparing/drift_detection → auditing → inspecting → reporting →
  cli.
- Add `py.typed` marker so downstream consumers see the types.
- CI gate: mypy strict must pass on every PR.
- Estimated effort: 3-5 sessions. Effort is in fixing existing latent
  type imprecisions, not in changing the architecture.

**Phase S2 — coverage measurement + targets.**

- Configure `coverage.py` with branch coverage.
- Establish current baseline (likely ~80-90% line, ~70-80% branch).
- Set targets: ≥ 90% line / ≥ 85% branch on every wheel.
- CI gate: coverage may not regress on a PR.
- Surface uncovered lines / branches in PR comments.
- Estimated effort: 1-2 sessions.

**Phase S3 — performance benchmarks.**

- `tests/bench/` directory with `pytest-benchmark` micro-bench per
  pillar (SPC chart fitting on N=10⁴ samples, SPRT update cost,
  MixedLM fit cost), per codec (proof dump+load+verify_signature
  round-trip cost), per CLI cold-start (`time ophamin --version`).
- Pin baseline numbers in a `BENCHMARKS.md` table.
- CI gate: regression > 20% on any pinned bench fails.
- Estimated effort: 2-3 sessions.

**Phase S4 — reproducible builds + lockfile + container image.**

- `requirements-lock.txt` from `pip-compile --strip-extras`.
- Optional `uv.lock` (uv replacement for pip).
- `Dockerfile` that pins Python 3.12 + lockfile + entry-point
  `ophamin verify`.
- Verified-rebuild guarantee: same lockfile + same Dockerfile = same
  `ophamin --version` + same test outcome.
- Estimated effort: 1-2 sessions.

**Phase S5 — supply-chain hygiene.**

- `ophamin audit pyproject.toml` (which uses `pip-audit` +
  `cyclonedx-python-lib`) emits a signed SBOM that ships with the
  release.
- `osv-scanner` integration; weekly cron CI run; alert on new CVE.
- Auto-fail CI if `pip-audit` reports a HIGH-or-CRITICAL CVE.
- Published `SECURITY.md` already exists; add responsible-disclosure
  email + PGP key.
- Estimated effort: 1 session.

**Phase S6 — formal correctness specs.**

- For each signed-record codec, prove the round-trip invariant
  (`load(dump(r)) == r` in canonical form) via property-based test
  (hypothesis).
- For the Pillar Protocol, prove `isinstance(p, Pillar)` for every
  registered pillar (Move G already does this; formalize as a
  property-test).
- For the CRDT Laws scenario, prove the four laws hold across
  Hypothesis-generated op sequences (the scenario does this; formalize
  as a property test).
- Estimated effort: 2-3 sessions.

**S1–S6 cumulative effort: 10–16 sessions.**

---

## 2. What "legit" means + 6 phases that get us there

**Phase L1 — public documentation site.**

- mkdocs-material configured with:
  - the entire `docs/` tree pre-rendered,
  - per-module API reference (`mkdocstrings`),
  - tutorial: "your first scenario in 5 minutes",
  - tutorial: "wrap a third-party pillar in 50 LOC",
  - tutorial: "from `ophamin run-all` to a published proof",
  - architecture: re-render of the audit + extended-audit docs as
    canonical pages,
  - CHANGELOG mirror.
- GitHub Pages deployment on every push to main.
- Custom domain pointer (e.g. ophamin.idirbenslama.dev).
- Estimated effort: 2-3 sessions.

**Phase L2 — CITATION.cff + Zenodo DOI.**

- `CITATION.cff` already exists; verify metadata (authors,
  identifiers, version, keywords).
- Connect Zenodo to the GitHub repo; mint a DOI on the next tagged
  release.
- README badge: `[![DOI](...)]`.
- Estimated effort: 0.5 session.

**Phase L3 — public CI.**

- GitHub Actions: matrix run across Python 3.12 / 3.13.
- Jobs: lint (ruff) → typecheck (mypy strict) → test (pytest -q +
  coverage) → audit (pip-audit) → bench (pytest-benchmark with
  baseline comparison) → docs build (mkdocs build).
- Badges in README.
- Branch protection: every PR requires CI green.
- Estimated effort: 1 session (workflows exist, need refinement).

**Phase L4 — versioned schemas with migration guarantees.**

- Maintain a `SCHEMAS.md` cataloguing every signed-record schema
  (EmpiricalProofRecord 1.0, AuditRecord 1.0 + 1.1, DriftScan 1 + 2,
  CampaignRecord 1.0, RegressionAlertRecord 1.0). For each, declare:
  - current version
  - backward-compat read-policy (which older versions the codec
    accepts)
  - migration script when a major bump happens
  - guaranteed-stable fields vs deprecated-fields-with-removal-date
- `ophamin schema validate <record.json>` CLI that runs the
  appropriate codec's structural check.
- Semver promise: minor versions never break existing record JSONs;
  major versions ship migration scripts.
- Estimated effort: 1-2 sessions.

**Phase L5 — RFC process + contributor onboarding.**

- `docs/rfc/0001-template.md` + `docs/rfc/README.md` documenting the
  process.
- Convert the existing architecture audits into RFC-numbered
  documents in retrospect (RFC 0001: Move A scenario metadata, RFC
  0002: Move B proof codec, …).
- `CONTRIBUTING.md` already exists; expand with the RFC-first rule
  for design changes vs the PR-first rule for bug fixes.
- Add a "good first issue" label workflow.
- Estimated effort: 1 session.

**Phase L6 — scientific validation studies.**

- For each shipped scenario, publish (in `docs/validation/`):
  - the cross-framework comparison: "Immune Siege using Ophamin's
    pipeline vs running the same offensive-security corpus through
    Garak / promptfoo / [other]"
  - the substrate-independence study: run the scenario against
    MockSubstrate with controlled noise; verify the verdict tracks
    the noise level as predicted.
  - reproducibility report: same seed + same Kimera commit + same
    Ophamin commit → bit-identical proof_id.
- Cross-validate the CRDT-laws scenario against Yjs's own JS test
  suite (translate one of theirs into a Hypothesis strategy).
- Estimated effort: 4-6 sessions.

**L1–L6 cumulative effort: 9.5–13.5 sessions.**

---

## 3. Sequenced execution plan

If we commit to elevation, the cleanest order is:

| Stage | Phases | Sessions | Outcome |
|---|---|---|---|
| **Stage 1 — internal hardening** | S1 (mypy strict), S2 (coverage), S3 (benchmarks) | 6–10 | "every regression is caught by CI" |
| **Stage 2 — reproducible + secure** | S4 (lockfile + container), S5 (supply chain), S6 (property tests) | 4–6 | "any reviewer can rebuild bit-identically; any CVE is alerted within 24h" |
| **Stage 3 — public legitimacy** | L1 (docs site), L2 (DOI), L3 (public CI), L4 (schema policy) | 4.5–6.5 | "citable + browsable + every PR shows green; consumers can rely on schemas" |
| **Stage 4 — community + science** | L5 (RFC process), L6 (validation studies) | 5–7 | "third-party contributors can navigate the design space; the framework's claims are independently checkable" |
| **Stage 5 — state-of-the-art scientific tier** | E1 (cross-framework validation), E2 (statistical rigor), E3 (open data + benchmarks), E4 (research-grade reproducibility), E5 (peer review + publication) | 10–18 | "the framework's claims meet bar for a methods paper; cited externally" |
| **Stage 6 — state-of-the-art engineering tier** | E6 (multi-platform wheels + PyPI/conda), E7 (signed releases + SLSA provenance), E8 (deprecation + stability policy), E9 (cross-language interop), E10 (community infrastructure) | 8–14 | "Ophamin is on the shelf next to scikit-learn / mlflow / pymc as a citable + installable + maintainable scientific framework" |

**Total: ~38–55 sessions** if every phase lands. Each stage is
independently shippable; the owner picks the cut-off. Stages 5–6
target **state-of-the-art** legitimacy — see §9 + §10 below for the
detailed phase breakdowns.

---

## 4. The single highest-leverage move

If only ONE phase landed, the highest leverage by far is **L1
(public documentation site)** — because it's the gating phase for
every other "legit" claim (no DOI without docs to cite; no community
without docs to onboard; no scientific reviewer without docs to
parse). It also surfaces every architectural gap the architecture
audits already named (gap E inner-triad asymmetry surfaces visually
in a tree of mkdocs pages; gap F regression-alert daemon now has a
home as a tutorial).

If two phases: L1 + S1 (mypy strict). Together they give the
framework a public face + a defensible internal contract.

---

## 5. What we should NOT do

- **Don't rename / re-brand the OFAMIN initialism.** The pillar count
  has outgrown the six letters (gap D from the prior audit named
  this). The right move is to accept OFAMIN as a historical anchor
  rather than to retrofit a new acronym. Renames break every link in
  every doc + every shipped proof's pillar attribution.
- **Don't try to ship a `pip install ophamin` to PyPI without the
  L4 schema policy.** Once a schema is in the wild, breaking it is a
  betrayal of consumers; a clear schema-policy document must precede
  any public distribution.
- **Don't open-source the framework before L5 (RFC process).**
  Without an RFC process the project will accumulate ad-hoc design
  changes from contributors that drift the architecture. The RFC
  process is the gate that keeps the architectural-intent docs
  load-bearing.
- **Don't add new measurement scenarios beyond the current 19
  before the elevation phases run.** Scenario count growth without
  the structural-hygiene phases will widen rather than close the
  validation gap.

---

## 6. Honest unknowns

- **Whether the v0.4.0 design has hidden defects only mypy strict
  would surface.** The 1,148 tests cover behavior; they don't
  catch type-level latent bugs. Stage 1 S1 will tell us.
- **Whether the OFAMIN-initialism + pillar-count mismatch is a
  cosmetic issue or a design issue.** Gap D from the prior audit
  said it was structural-intent drift; my read above says it's
  cosmetic. Stage 4 L5 (RFC process) would force the question.
- **Whether L6 (validation studies) is feasible without a research
  partner.** Cross-framework comparison + reproducibility studies
  are scientifically valuable but operationally heavy. May need
  external collaboration.
- **The proprietary license vs open-source decision.** Today the
  LICENSE is Proprietary; many of the "legit" phases (DOI,
  community, contributor onboarding) assume open-source. This is
  an owner decision, not a framework decision.
- **Distribution channels.** PyPI? Conda-forge? Private wheel
  server? All possible; each has different legitimacy implications.

---

## 7. License decision — RESOLVED (2026-05-16)

The previously-open question — **Will Ophamin be open-source or stay
proprietary?** — was resolved by owner directive 2026-05-16:
**open-source under Apache License 2.0.** Concrete consequences for
the roadmap:

- L1 docs site → **public mkdocs** (likely GitHub Pages, possibly a
  custom domain).
- L2 DOI → Zenodo-mintable on the first tagged release; needs the
  repo to be GitHub-public.
- L3 public CI → GitHub Actions matrix runs with public badges;
  branch protection on `main`.
- L5 RFC process → **community-shaped**: outside contributors can
  propose RFCs through the standard PR flow; the existing
  architectural audit docs become RFC-0001 through RFC-0014 in
  retrospect.
- L6 validation studies → eligible for academic-collaboration
  proposals; substrate-comparison studies against other frameworks
  (Garak, promptfoo, Frouros, …) become possible.

Effort: **~20–30 sessions** for the full 4-stage path.

## 8. Naming decision — RESOLVED (2026-05-16)

The previously-deferred question — what to do about the OFAMIN
initialism vs the now-broader pillar count — was resolved by owner
directive 2026-05-16: **do not rename Ophamin.** The name is the
stable identifier per `NOTICE`; the pillar count having outgrown the
six letters is a historical-anchor situation, not a naming defect.

Concrete consequences:

- Existing OFAMIN pillar identifiers (`O.spc / O.srm / O.drift /
  A.sprt / M.mixed_effects / M.mea / I.cma / N.cross_validation`)
  remain the canonical pillar names.
- New pillars beyond the six get descriptive names rather than
  forcing them into the initialism (e.g. the proposed `L.atency /
  B.andwidth / Availability / Σ.correlation` pillars from the
  observational-surface doc would land as `latency / bandwidth /
  availability / correlation` rather than as new OFAMIN letters).
- Diagnostic pillars (`diagnostics.anticipatory / inertia /
  kernel_coupling`) already use the descriptive shape; future
  diagnostic additions follow suit.
- The name itself ("Ophamin") is reserved per `NOTICE`;
  architectural-divergence forks choose their own name.

---

*Authored by Claude (Opus 4.7 1M context), 2026-05-16, after
landing every open architectural gap (Moves A–N), cutting v0.4.0,
and receiving owner-locked constraints (open-source + no rename).
Ready to execute Stage 1 (S1 mypy strict + S2 coverage + S3
benchmarks) on owner go-ahead.*

---

## 8.5. Stage 5 + 6 — execution status (refreshed 2026-05-18)

This table tracks per-phase shipped state. Phases land as one or more
patch/minor releases; the canonical record is the CHANGELOG.

| Phase | Theme | Status | Releases |
|---|---|---|---|
| **E2** | FWER correction at campaign level + CampaignRecord/2.0 schema bump | ✅ shipped | `0.9.0` |
| **E6** | PyPI Trusted Publishing release workflow + advisory-until-PyPI-enabled | ✅ shipped (one owner step pending) | `0.9.1`, `0.9.2` |
| **E7** | SLSA 3 build provenance + sigstore signing + PEP 740 attestations | ✅ shipped | `0.9.3` |
| **E8** | Python-API stability contract (`@Stable` / `@Provisional` / `@Internal` / `@Deprecated` decorators + regression suite + `ophamin api-stability` CLI) | ✅ shipped | `0.10.0`, `0.10.1` |
| **E10** | Community infrastructure (GOVERNANCE / ROADMAP / SUPPORT / FUNDING / CoC link) | ✅ shipped | `0.10.2` |
| **E4** | Research-grade reproducibility — deterministic-seed audit scenario + framework-wide audit gate + `SOURCE_DATE_EPOCH` build reproducibility | ✅ shipped (per-OS lockfiles + cross-machine diffoscope remain owner-side) | `0.11.0`–`0.11.2`, `0.11.4` |
| **E3.1** | Concept walkthroughs (E2 + E4 + E8 + E1 demos under `examples/walkthrough_*.py`) | ✅ shipped | `0.11.3`, `0.12.1` |
| **E1.1** | First cross-framework validation — PyMC↔NumPyro Bayesian posterior agreement + signed proof published under `proofs/measurement_machinery/bayesian_cross_framework/` | ✅ shipped | `0.12.0` |
| **E1.2** | Second cross-framework validation — Wilson CI scipy↔statsmodels (machine-epsilon agreement, signed proof under `proofs/measurement_machinery/wilson_ci_cross_framework/`) | ✅ shipped | `0.13.0` |
| **E1.3** | Third cross-framework validation — Spearman ρ scipy↔pingouin (exact 0.000 agreement, signed proof under `proofs/measurement_machinery/spearman_cross_framework/`) | ✅ shipped | `0.13.0` |
| **E1.4** | Fourth cross-framework validation — Pearson r scipy↔numpy↔pingouin (three-way, machine-epsilon agreement, signed proof under `proofs/measurement_machinery/pearson_cross_framework/`) | ✅ shipped | `0.14.0` |
| **E1.5** | Fifth cross-framework validation — Welch's t-test scipy↔statsmodels↔pingouin (three-way, both *t* and two-sided *p*, ~8× machine epsilon agreement; signed proof under `proofs/measurement_machinery/welch_t_cross_framework/`) | ✅ shipped | `0.14.0` |
| **E1.6** | Sixth cross-framework validation — one-way ANOVA scipy↔statsmodels↔pingouin (three-way, both F and two-sided p, ~32× machine epsilon agreement; signed proof under `proofs/measurement_machinery/anova_cross_framework/`) | ✅ shipped | `0.15.0` |
| **E1.7** | Seventh cross-framework validation — Mann-Whitney U scipy↔pingouin (exact agreement on both U and p under matched continuity; first non-parametric check in the portfolio; signed proof under `proofs/measurement_machinery/mann_whitney_cross_framework/`) | ✅ shipped | `0.15.0` |
| **E1 acceptance** | ≥ 3 cross-framework VALIDATED proofs under `proofs/measurement_machinery/` | ✅ met (7 / 3) | `0.13.0`–`0.15.0` |
| **E9 spec** | Canonical-form byte representation promoted to normative `SCHEMAS.md` §"Canonical-form determinism (normative)" R1–R11 + three cross-language test fixtures under `tests/canonical_form/` with HMAC pins | ✅ shipped | `0.14.0` |
| **E5 draft** | JOSS-style methods paper draft authored under `paper/paper.md` + `paper/paper.bib` (~1500 words, 7 cross-framework agreement proofs tabulated) | ✅ shipped (refreshed `0.15.0`) | `0.14.0`, `0.15.0` |
| **E9 implementation** | Rust `crates/ophamin-proof` (read-only verifier; serde_json + arbitrary_precision + custom escape_string per R6) + TS `packages/ophamin-proof-js` (custom JSON parser preserving int/float + Python-repr float formatter + ensure_ascii escape) + CI workflow `.github/workflows/cross-language.yml` running both fixture suites AND signature verification on every shipped Python-emitted signed proof | ✅ shipped (read-only) | `0.16.0` |
| **E3** owner-side | Zenodo benchmark deposit + DOI + reproducer notebooks for ≥ 6 scenarios | open (owner) | — |
| **E4** owner-side | External reviewer rebuild verification (byte-equal SBOM + signed-record output) | open (owner) | — |
| **E5 submission** | Methods paper submission (JOSS / SoftwareX / JMLR-OSS) + reviewer-time feedback | open (owner: ORCID + venue + Zenodo DOI per `paper/README.md`) | — |
| **E9 write-side (future)** | Canonical-form WRITERS in Rust + JS (require reimplementing Python's `repr(float)` byte-for-byte) | not implemented; out of scope for the 0.16.0 read-API contract | — |

**Both 1.0.0 prerequisites met:** wire-format stability contract (E2 — `0.9.0`)
and Python-API stability contract (E8 — `0.10.0`). What separates the
current `0.12.x` line from `1.0.0` is **external validation under real
upgrade pressure** — RFC 0002 §3.2 names "third party rebuilds a tagged
release and verifies byte-equal SBOM + signed-record output" (E4
owner-side) and "methods paper passes review" (E5) as the two doors.

## 9. Stage 5 — state-of-the-art scientific tier

Stage 5 raises Ophamin from "internally rigorous + publicly browsable"
(Stages 1–4) to "citable as a scientific methods framework". Each
phase has concrete acceptance criteria and a publication-shaped
deliverable.

**Phase E1 — cross-framework validation studies.**

The framework's measurement-machinery tier is already self-validating
(Bayesian posterior contracts as √N; CRDT laws cross-checked between
pycrdt + y-py). Stage-5 extends this to cross-framework validation:

- **GWF-class scenarios cross-checked against Garak + promptfoo** —
  run the same offensive-security corpus through both and surface the
  delta as a signed proof. The discipline: pre-register the
  expected agreement bound BEFORE running.
- **Pillar-class scenarios cross-checked against R / Stan / PyMC** —
  the Bayesian-phi-posterior scenario already uses PyMC; add a Stan
  alternative under `[bayesian_stan]` and assert posterior
  contraction agrees within tolerance.
- **CRDT-laws cross-checked against Yjs's own JS test suite** —
  translate one of Yjs's foundational tests into a Hypothesis
  strategy; verify Ophamin reaches the same fixed-point.

Acceptance: ≥ 3 cross-framework validation proofs published under
[`proofs/measurement_machinery/`](https://github.com/IdirBenSlama/Ophamin/blob/main/proofs/measurement_machinery/);
each is a VALIDATED record with a documented agreement threshold.
Estimated effort: 3–5 sessions.

**Phase E2 — formal statistical rigor.**

Pre-registration discipline + Wilson 95 % CIs are already shipped.
Stage-5 adds the statistical machinery a methods paper would expect:

- **Family-wise error rate (FWER) management across a campaign.** When
  `ophamin run-all` produces N proofs, the probability of at least one
  spurious VALIDATED at α=0.05 climbs with N. Implement Holm–Bonferroni
  or Benjamini–Hochberg correction in the CampaignRecord aggregate;
  surface both raw and corrected verdicts.
- **Bayesian updating across a scenario sequence.** When the same
  scenario runs N times against different commits, the posterior
  should update — not reset. Add `ophamin compare update-posterior
  <scenario>` that walks a directory of proofs and emits a posterior
  trajectory record.
- **Power analysis** for every scenario at scenario-authoring time.
  Add `ScenarioScore.minimum_detectable_effect` or similar; warn at
  `ophamin scenario show` time when the configured N is below the
  power-80 threshold for the pre-registered claim.

Acceptance: a new pillar `M.fwer` (multiplicity correction) + a new
`E.power` pillar (effect-size + power calculation). Both pass
property tests. CampaignRecord schema bumps to `2.0` to include
corrected verdicts.

Estimated effort: 2–4 sessions.

**Phase E3 — open data + benchmarks.**

A SOTA scientific framework publishes its **benchmark corpus**:

- **Substrate-vs-claim benchmark suite.** Curate 100+ signed proofs
  across the 19 scenarios + N synthetic-substrate variants; publish
  as a tagged Zenodo deposit with its own DOI separate from the
  framework's. The benchmark is then *citable as a dataset* —
  downstream papers can reference it directly.
- **Reproducer notebook per scenario** — a Jupyter or marimo
  notebook that, given the published benchmark, reproduces every
  scenario's claim end-to-end. Owner-runnable; the notebook is the
  scientific artefact.
- **Hardness landscape paper** — a short methods paper showing how
  scenario verdicts shift as substrate parameters vary (e.g. MockSubstrate
  noise level → ImmuneSiege false-positive rate trajectory). Submitted
  to a software-paper venue (JOSS, SoftwareX, JMLR-Open-Source).

Acceptance: one Zenodo benchmark deposit + one methods paper draft +
reproducer notebooks for ≥ 6 scenarios.

Estimated effort: 3–5 sessions + owner-side paper authoring.

**Phase E4 — research-grade reproducibility.**

Beyond Stages 1–3's reproducible-build foundation:

- **Per-OS lockfiles** for every supported triple: macOS-arm64-py312,
  linux-amd64-py312, linux-amd64-py313, linux-arm64-py312 (when wheels
  catch up). Stage-3 shipped two; Stage-5 adds the rest via
  `uv pip compile --universal` or per-platform Docker emit.
- **Deterministic-seed propagation audit.** Every scenario should
  produce a bit-identical `proof_id` for the same `(seed, corpus,
  substrate_commit, ophamin_commit)` tuple across N machines. Add a
  `MeasurementMachinery` scenario that asserts this empirically.
- **In-toto / SLSA Level 3 attestations** for every release artefact.
  GitHub Actions natively supports SLSA 3 via the `slsa-framework`
  reusable workflow; wire it.
- **Container image signing** via cosign (sigstore). The 0.8.x
  Dockerfile produces an image; cosign-sign it on every release.
- **Diffoscope-clean builds** — `diffoscope` should report zero
  meaningful diffs between two independent builds of the same commit.

Acceptance: at least one external reviewer rebuilds a tagged release
from source + lockfile and verifies the SBOM byte-equal +
signed-record byte-equal output. Published as a reproducibility
report.

Estimated effort: 2–4 sessions + owner-side cross-validation.

**Phase E5 — peer review + publication.**

The capstone: a methods paper. Likely venues + paths:

- **JOSS** (Journal of Open Source Software) — fast turnaround,
  reviewer focus on "is the software well-engineered + documented"
  rather than novel research. Realistic 1–3 month review cycle.
- **SoftwareX** — Elsevier, scopes broader than JOSS, asks for some
  research narrative + reproducibility evidence.
- **JMLR-Open-Source-Software** — narrowest scope (ML/stats software);
  prestige bump.

Acceptance: paper draft + JOSS-style review issue opened at the
chosen venue. The framework's claims become **independently
checkable** by reviewer-time peer review.

Estimated effort: 3–6 sessions of authoring + revision rounds.

**Stage 5 cumulative effort: 13–24 sessions.**

---

## 10. Stage 6 — state-of-the-art engineering tier

Stage 6 raises Ophamin from "Apache-2.0 source on GitHub" to "on the
shelf next to scikit-learn / mlflow / pymc — installable, signed,
multi-platform, with formal stability guarantees".

**Phase E6 — PyPI + conda-forge + multi-platform wheels.**

Today the framework is GitHub-only; `pip install ophamin` doesn't
work. Stage-6 phase one:

- **PyPI publication** via Trusted Publishing. Add the OIDC config to
  `.github/workflows/release.yml`. Every `v*` tag triggers a sdist +
  pure-Python wheel build + upload. No long-lived PyPI tokens — the
  OIDC trust is the release credential.
- **conda-forge feedstock** — separate repo `conda-forge/ophamin-feedstock`,
  the recipe meta.yaml derives from pyproject's extras. Conda users
  install via `conda install -c conda-forge ophamin`.
- **Multi-platform wheel matrix** — for the future-when-Ophamin-grows-
  C-extensions case (it's pure-Python today, so a single wheel
  suffices); the scaffolding is `cibuildwheel`. Adds a workflow stub
  even though it's a no-op for the current code so future C extensions
  ship pre-built.

Acceptance: `pip install ophamin` works against PyPI; conda-forge
recipe lands; both auto-update on every release.

Estimated effort: 1–2 sessions.

**Phase E7 — signed releases + SLSA provenance.**

Beyond Stage-5's research-reproducibility framing, the engineering
SOTA requires:

- **Sigstore release signing** — every PyPI artefact + container image
  cosign-signed; signatures published to a transparency log.
- **SLSA Level 3 build provenance** — auto-generated by the release
  workflow; attached to every release as an in-toto attestation.
- **Source provenance** — the GitHub commit signature chain back to
  the owner's GPG / SSH key. Verifiable via `gh attestation verify`.

Acceptance: `cosign verify` succeeds against every release artefact;
`gh attestation verify` confirms the build provenance.

Estimated effort: 1 session + GitHub owner-side cosign setup.

**Phase E8 — deprecation + stability policy.**

Today the framework lives under 0.x; backward compatibility is
*encouraged* but not *contractually guaranteed* beyond the schema
policy in SCHEMAS.md. State-of-the-art engineering demands an
explicit stability contract:

- **API stability tiers** — every public symbol carries an explicit
  tier in its docstring: `Stable`, `Provisional`, `Internal`,
  `Deprecated (until <date>)`. The audit pillar `mypy` enforces this
  via a `@stable` / `@provisional` / `@internal` decorator stack
  (also exposed via mkdocstrings).
- **Deprecation policy** — at least one full minor release of warning
  + the documented migration path before removal in a major bump.
  Mirrors the SCHEMAS.md policy at the Python level.
- **Stability test suite** — for every `Stable` symbol, a regression
  test pins its signature + behavior. Adding parameters is OK;
  removing or renaming fails the test.
- **`ophamin api-stability check`** CLI — surfaces deprecation
  warnings reachable from a user's code (point at a directory or a
  proof record's `reproduction.command`).

Acceptance: every public symbol annotated; the stability test suite
catches accidental renames at PR time.

Estimated effort: 2–3 sessions.

**Phase E9 — cross-language interop.**

Today Ophamin is Python-only. SOTA scientific frameworks have at
minimum a Read API in adjacent languages. Concrete shape:

- **Rust signed-record codec** (read-only) — a `cargo` crate
  `ophamin-proof` that parses `EmpiricalProofRecord` JSON, verifies
  the signature, and exposes the data structurally. Validates the
  schema is platform-agnostic; opens the door to Rust scenarios.
- **JS / TypeScript signed-record codec** — same pattern, for the
  browser-side replay-a-proof story.
- **Schema stability via cross-language tests** — the Rust + JS
  codecs run against a fixture of 100 signed proofs from Python;
  byte-equal signature verification across all three.

Acceptance: a `crates/ophamin-proof/` + `packages/ophamin-proof-js/`
subdir; both ship their own CI; cross-language reproducibility test
passes.

Estimated effort: 3–5 sessions.

**Phase E10 — community infrastructure.**

The last piece of the "alongside scikit-learn / mlflow / pymc" gap:

- **GitHub Discussions** enabled — paired with the existing Issues
  templates.
- **Code of Conduct** activated and visible.
- **Sponsor button** — GitHub Sponsors / Open Collective. Not for
  fundraising; for *signalling that the project accepts contributions
  at the community-economics layer*.
- **Project governance doc** — `GOVERNANCE.md` explaining the
  owner-as-BDFL state today + the path to a small core team if /
  when contributors arrive.
- **Annual roadmap doc** — `ROADMAP.md` derived from this elevation
  roadmap, but refreshed each year. Shows external readers where the
  project is heading.
- **Quarterly state-of-Ophamin post** — owner-territory; one
  short post per quarter showing what changed, what shipped, what's
  next. Doubles as a check-in artifact.

Acceptance: every infrastructure piece visible from
`https://github.com/IdirBenSlama/Ophamin`.

Estimated effort: 1–2 sessions + ongoing owner cadence.

**Stage 6 cumulative effort: 8–14 sessions.**

---

## 11. Definition of "state-of-the-art" — what we measure against

The framing of Stages 5 + 6 is "be on the shelf next to
scikit-learn / mlflow / pymc". Concrete criteria:

| Criterion | scikit-learn | mlflow | pymc | **Ophamin target after Stages 5+6** |
|---|---|---|---|---|
| PyPI installable | ✅ | ✅ | ✅ | ✅ Phase E6 |
| Conda-forge available | ✅ | ✅ | ✅ | ✅ Phase E6 |
| Multi-platform CI matrix | Linux + macOS + Windows | Linux + macOS | Linux + macOS + Windows | Linux + macOS (Phase A2); Windows via E6 follow-up |
| mypy --strict clean | partial | partial | partial | ✅ (Phase S1) |
| Property-test coverage | partial | partial | ✅ | ✅ (Phase S6) |
| Methods paper published | n/a (textbook) | yes (Databricks blog series + workshop) | yes (JOSS) | Phase E5 |
| DOI per release | no | no | ✅ Zenodo | Phase L2 (owner-side activation) |
| Schema versioning policy | informal | yes (mlflow_model) | informal | ✅ (Phase L4) |
| SLSA-signed releases | partial | yes | partial | Phase E7 |
| Cross-language read API | C / R bindings | yes (JS / R / Java) | partial (R) | Phase E9 |
| Public RFC process | yes | yes | yes | ✅ (Phase L5) |
| Governance doc | ✅ | ✅ | ✅ | Phase E10 |
| External contributors | thousands | hundreds | dozens | owner-territory |
| Citations | tens of thousands | thousands | thousands | owner-territory |

What we **can** deliver via framework-internal work: every row up to
"External contributors". What we **can't** deliver via code alone:
the last two rows are owner-driven (paper writing, community
building, conference talks). State-of-the-art means *delivering
everything that's framework-internal* + *having the infrastructure
ready* for the external-driven parts.

---

## 12. The next single highest-leverage move (after Stages 1–4)

If only ONE Stage-5 phase landed first, **Phase E2 (formal
statistical rigor — FWER correction across a campaign)** is the
highest leverage. Three reasons:

1. It's framework-internal — no owner-side dependency.
2. It surfaces a real defect in the current methodology: today, a
   `ophamin run-all` that produces 19 scenario verdicts has an
   ~62 % chance of at least one spurious VALIDATED at α=0.05 from
   pure multiple-testing. The fix is documented + implemented in a
   single round; the win is publishable as part of the methods
   paper.
3. It's the bridge between "rigorous internally" and "citable
   externally" — without it, a methods reviewer asks the
   multiple-testing question immediately.

Second-highest: Phase E1 (cross-framework validation). It surfaces
exactly the dependencies that make Ophamin not-yet-SOTA today: the
framework's claims about Kimera are testable only against itself.
