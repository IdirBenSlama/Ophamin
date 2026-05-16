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

**Total: ~20–30 sessions.** Each stage is independently shippable.
Owner picks the cut-off.

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
