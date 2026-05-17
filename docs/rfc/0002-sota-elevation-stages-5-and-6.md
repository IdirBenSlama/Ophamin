# RFC 0002 — State-of-the-art elevation: Stages 5 (scientific) and 6 (engineering)

| | |
|---|---|
| **Status** | DRAFT |
| **Author** | Idir Ben Slama |
| **Created** | 2026-05-17 |
| **Last updated** | 2026-05-17 |
| **Discussion** | landed alongside 0.8.3 (no PR review — author-acknowledged scope-setter) |
| **Implementation PR(s)** | (filled in as each phase ships) |

---

## 1. Summary

This RFC proposes the next two elevation stages beyond the 0.8.x
Stage-3 + Stage-4 work already shipped. **Stage 5** raises Ophamin
from "internally rigorous + publicly browsable" to **citable as a
scientific methods framework** (cross-framework validation, FWER
correction, open benchmark deposit, research-grade reproducibility,
peer review). **Stage 6** raises it from "Apache-2.0 source on
GitHub" to **on the shelf next to scikit-learn / mlflow / pymc** —
PyPI + conda-forge installable, SLSA-signed releases, formal API
stability policy, cross-language read APIs, community infrastructure.

The full per-phase detail lives in
[`ELEVATION_ROADMAP_2026_05_16.md` §9–§12](https://github.com/IdirBenSlama/Ophamin/blob/main/docs/ELEVATION_ROADMAP_2026_05_16.md);
this RFC ratifies that detail under the L5 process so the plan is
**reviewable + revisable + citable** under the same lifecycle as any
future single-phase RFC.

## 2. Problem statement

The 0.8.x line closed every Stage-1–4 phase: internal hardening
(S1–S6), external legitimacy (L1–L5), the Apache-2.0 relicense, the
honest cross-platform coverage gate, the docs site under
[idirbenslama.github.io/Ophamin](https://idirbenslama.github.io/Ophamin/),
and a portable Linux lockfile. The framework is internally rigorous
and publicly browsable.

But the gap to **state-of-the-art** is concrete:

1. **No multiple-testing correction.** Today `ophamin run-all`
   produces N proofs at independent α=0.05. With N=19 scenarios the
   probability of ≥ 1 spurious VALIDATED is ~62 %. A methods reviewer
   would flag this on first read of any draft.
2. **No external validation of measurement machinery.** Family T
   (Bayesian + CRDT) cross-checks tools against themselves
   (pycrdt ↔ y-py, pyitlib ↔ ennemi) but not against independent
   implementations in other ecosystems (Stan, Yjs JS, Garak).
3. **Not installable.** `pip install ophamin` does not work; only
   `pip install -e .` from a clone does. Conda-forge has no
   feedstock. New users cannot get the framework without a Git
   checkout.
4. **No stability contract.** SCHEMAS.md formalises the codec policy
   but no Python-API equivalent exists. Public symbols have no
   tier annotation; renames could break downstream silently.
5. **No SLSA-level release provenance.** Tarballs and wheels are
   unsigned; downstream cannot cryptographically attribute a release
   artefact to a specific commit + builder.
6. **Python-only.** No read API in Rust / JS — every consumer must
   speak Python.
7. **No published benchmark dataset.** The 19 scenarios self-validate
   on synthetic substrates but the corpus is not citable as a
   benchmark from a downstream paper.
8. **No peer review.** No external reviewer has rebuilt the framework
   from source and verified the signed-record output byte-equal. No
   methods paper exists in any venue's review pipeline.

These are not aspirational gaps — each one is a concrete deficiency a
SOTA-comparable framework (scikit-learn / mlflow / pymc) would close
before shipping a 1.0.

## 3. Proposed change

Adopt the **10 phases** specified in
[`ELEVATION_ROADMAP_2026_05_16.md`](https://github.com/IdirBenSlama/Ophamin/blob/main/docs/ELEVATION_ROADMAP_2026_05_16.md)
as the ratified plan for Stages 5 and 6. Each phase is independent
and ships as its own minor or patch release; the order below is the
**recommended dependency order**, not a hard sequence.

### 3.1 Stage 5 — scientific tier (E1–E5)

| Phase | Deliverable | Acceptance |
|---|---|---|
| **E1** Cross-framework validation | GWF↔Garak + Bayesian↔Stan + CRDT↔Yjs cross-checks; ≥ 3 signed VALIDATED proofs | proofs land under `proofs/measurement_machinery/`; agreement threshold documented per proof |
| **E2** Formal statistical rigor | FWER correction (Holm–Bonferroni + Benjamini–Hochberg) on CampaignRecord; Bayesian posterior updating across scenario runs; per-scenario power analysis | new pillars `M.fwer` + `E.power`; CampaignRecord schema → 2.0; corrected + raw verdicts both surfaced |
| **E3** Open data + benchmarks | Zenodo-deposited benchmark corpus (100+ signed proofs + synthetic substrates); per-scenario reproducer notebooks; one methods paper draft | DOI separate from framework's; notebooks for ≥ 6 scenarios; paper draft in a software-paper venue (JOSS / SoftwareX / JMLR-OSS) |
| **E4** Research-grade reproducibility | Per-OS lockfiles for every supported triple; deterministic-seed propagation audit; SLSA-3 attestations; cosign-signed container images; diffoscope-clean builds | external reviewer rebuilds a tagged release + verifies byte-equal SBOM + signed-record output |
| **E5** Peer review + publication | Methods paper submitted; reviewer-time feedback addressed | accepted at JOSS / SoftwareX / JMLR-OSS |

### 3.2 Stage 6 — engineering tier (E6–E10)

| Phase | Deliverable | Acceptance |
|---|---|---|
| **E6** PyPI + conda-forge + multi-platform wheels | Trusted-Publishing-based PyPI workflow; conda-forge feedstock; `cibuildwheel` scaffold | `pip install ophamin` works; conda recipe auto-updates per release |
| **E7** Signed releases + SLSA provenance | Sigstore cosign signatures on all release artefacts; SLSA-3 build provenance; transparency-log entries | `cosign verify` + `gh attestation verify` succeed end-to-end |
| **E8** API stability policy | Tier annotations (`Stable` / `Provisional` / `Internal` / `Deprecated`) on every public symbol; regression test pinning signatures; `ophamin api-stability check` CLI | renames fail the stability suite at PR time; deprecation policy mirrors SCHEMAS.md |
| **E9** Cross-language interop | `crates/ophamin-proof` (Rust); `packages/ophamin-proof-js` (TS); both verify signed-record bytes | byte-equal signature verification across Python + Rust + JS on a 100-proof fixture |
| **E10** Community infrastructure | GitHub Discussions; CODE_OF_CONDUCT.md; Sponsor button; GOVERNANCE.md; ROADMAP.md | visible from project root; CoC + governance reviewable |

### 3.3 Public surface impact

- **CLI**: adds `ophamin compare update-posterior`, `ophamin
  scenario power-check`, `ophamin api-stability check` (E2, E2, E8
  respectively). All exit-coded per the existing convention (0 happy
  / 2 documented failure / 64 misuse).
- **Codec / wire format**: `CampaignRecord` bumps `schema_version` to
  `2.0` to include corrected verdicts (E2). Reader continues to
  support `1.0` per the SCHEMAS.md backward-compat read-rule policy.
  No other schema changes.
- **Protocol interface**: `ScenarioScore` gains optional
  `minimum_detectable_effect: float | None` (E2). Existing
  scenarios continue to work; the field is computed lazily from the
  signed proof's pre-registered claim when present.
- **Optional dependencies**: new extras `[bayesian_stan]` (E1),
  `[cosign]` (E7), `[stability_test]` (E8). `[all]` continues to
  exclude provisional extras to keep the install footprint honest.

### 3.4 Backward compatibility

- **Reading older records**: `CampaignRecord/1.0` records remain
  readable indefinitely per SCHEMAS.md §"Backward compatibility on
  read". E2 adds a 2.0 producer; the reader stays both-versions
  aware.
- **Writing**: existing producers continue to work unmodified.
  Pre-registration discipline is unchanged; FWER correction is an
  *additional* surface on the aggregate, not a replacement.
- **Deprecation**: no fields removed. The pre-E2 single-α verdict
  semantics remain available via the `raw_verdict` field on the
  bumped CampaignRecord.

## 4. Alternatives considered

### 4.1 Alternative A — ship 1.0 with Stages 1–4 only

Concrete and shippable today. But premature: a 1.0 implies an
explicit stability contract (E8) and an installable distribution
(E6) — neither of which exists yet. Shipping 1.0 without them
locks in the *current* surface while still calling it stable,
which is dishonest.

### 4.2 Alternative B — ship Stage 5 (science) only, defer Stage 6

The methods paper (E5) would land before the framework is
`pip install`-able (E6). New readers of the paper would find
the framework only as a Git clone — which they'd reasonably
read as "this is research code, not production". The science
and engineering tiers are tightly coupled at the *reception*
layer; doing one without the other under-sells both.

### 4.3 Alternative C — ship Stage 6 (engineering) only, defer Stage 5

PyPI publication + SLSA signing without FWER correction or
cross-framework validation produces a polished distribution of a
methodology that hasn't been formally peer-reviewed. The reverse
of 4.2: looks production, but a methods reviewer would still flag
the multiple-testing gap on first read.

### 4.4 Do nothing

The framework stays internally rigorous + publicly browsable. New
users continue to install via clone. The known statistical gap (~62 %
spurious-verdict probability at run-all scale) remains. Citations
remain owner-side outreach rather than reviewer-validated. Honest
baseline if elevation is no longer the goal — but it's expressly the
opposite of the user directive on 2026-05-17.

## 5. Drawbacks

- **Scope is large.** Stage 5 estimated 13–24 sessions; Stage 6
  estimated 8–14 sessions. Cumulative 21–38 sessions of focused work.
  At Ophamin's current cadence (one Stage = days–weeks per phase)
  this is a 2–4 month elevation.
- **Some phases depend on external review** (E5 peer review, E4
  reviewer-side rebuild). The framework cannot single-handedly close
  them; the L5-ratified plan must explicitly mark these as
  owner-driven external-dependency phases.
- **Schema bump (CampaignRecord → 2.0) is the first non-trivial
  versioned bump.** Validates the SCHEMAS.md policy under load but
  also exercises the migration-script discipline for the first time.
- **Cross-language codecs (E9) double the maintenance surface.** Adds
  a Rust crate + a TS package to keep in lockstep with the Python
  schema. Mitigation: read-only codecs only; cross-language *write*
  is deferred to a future RFC.
- **PyPI Trusted Publishing requires GitHub-side OIDC config** the
  agent cannot set unilaterally. Owner-side step on the critical
  path for E6.
- **The roadmap could drift.** This RFC ratifies the plan as of
  2026-05-17. Re-ratification (a follow-on RFC) is required if any
  phase changes scope substantially.

## 6. Acceptance criteria

The RFC itself is ACCEPTED when:

- [x] This document exists at `docs/rfc/0002-sota-elevation-stages-5-and-6.md`
- [x] The 10 phases (E1–E10) are individually specified with acceptance
      criteria + estimated effort + dependency notes
- [x] Stages 5 + 6 are visible in [`ELEVATION_ROADMAP_2026_05_16.md`
      §9–§12](https://github.com/IdirBenSlama/Ophamin/blob/main/docs/ELEVATION_ROADMAP_2026_05_16.md)
- [x] The CHANGELOG entry for the release that lands this RFC links
      to it
- [x] mkdocs `--strict` build succeeds with the new RFC in nav

The full elevation is COMPLETE when every per-phase acceptance
criterion in §3.1 + §3.2 has its own VALIDATED checkbox. Each phase
ships under its own minor or patch release; this RFC does NOT have to
land as a single PR with all 10 phases.

## 7. Migration plan

### 7.1 CampaignRecord 1.0 → 2.0 (E2)

The schema bump is a **strictly additive** change: 2.0 adds
`corrected_verdicts: dict[str, str]` (mapping pre-registered claim
ID → Holm/BH-corrected verdict) and `multiplicity_correction_method:
str` (one of `"holm"`, `"bh"`, `"none"`). 1.0 readers ignore the new
fields; 2.0 readers compute corrected verdicts lazily from raw
verdicts if the field is absent (preserving backwards-read).

Migration tool: `tools/migrations/campaign_1_to_2.py` — accepts a
directory of 1.0 records, emits 2.0 records into a sibling
directory, byte-faithful for every other field. Pre-registration
metadata is preserved verbatim.

### 7.2 ScenarioScore `minimum_detectable_effect` (E2)

Strictly additive. No migration required; existing producers emit
records without the field; existing readers fall back to `None`.

### 7.3 No other migrations required

E1, E3, E4, E5–E10 add new artefacts but do not modify any existing
signed-record schema.

## 8. Open questions

1. **JOSS vs SoftwareX vs JMLR-Open-Source-Software for E5.** All
   three are viable. JOSS has the fastest turnaround but narrowest
   scope; JMLR-OSS the highest prestige but slowest review.
   Resolution: owner-territory, picked at submission time.
2. **Conda-forge feedstock owner.** First-time submissions need a
   maintainer to commit to the feedstock; owner-territory.
3. **Rust vs Go for the cross-language codec in E9.** Rust chosen in
   the roadmap (better cosign / signature-verification crate
   ecosystem). Open to revision if a downstream use case demands Go.
4. **SLSA Level 3 vs Level 4 for E7.** Level 3 is the realistic
   GitHub-Actions ceiling today; Level 4 requires two-party
   review of every build, which conflicts with the single-author
   reality. Resolution: ship Level 3; document the Level-4 gap
   honestly.
5. **Whether to require a deterministic-seed audit for every
   scenario or just the ones with statistical claims.** E4 says
   "every scenario"; pragmatically, the structural-tier scenarios
   (Family S substrate-completeness) may not need it. Resolution:
   start with the statistical-tier scenarios (Families A, B, C, L,
   M, U, V); revisit at E4 closeout.

## 9. References

- [`ELEVATION_ROADMAP_2026_05_16.md`](https://github.com/IdirBenSlama/Ophamin/blob/main/docs/ELEVATION_ROADMAP_2026_05_16.md)
  — the per-phase plan this RFC ratifies
- [`SCHEMAS.md`](https://github.com/IdirBenSlama/Ophamin/blob/main/SCHEMAS.md)
  — the codec versioning policy E2's schema bump exercises
- [`CHANGELOG.md`](https://github.com/IdirBenSlama/Ophamin/blob/main/CHANGELOG.md)
  — release-cadence record; each phase appears here as it ships
- RFC 0001 — the retrospective pointer; this RFC is the **first
  forward-looking ACCEPTED use** of the L5 process once it merges
- Upstream prior art:
  - JOSS submission guidelines: <https://joss.readthedocs.io/>
  - SLSA framework: <https://slsa.dev/>
  - sigstore cosign: <https://docs.sigstore.dev/cosign/>
  - PyPI Trusted Publishing:
    <https://docs.pypi.org/trusted-publishers/>
  - Holm–Bonferroni correction (Holm 1979):
    DOI [10.2307/4615733](https://doi.org/10.2307/4615733)
  - Benjamini–Hochberg correction (1995):
    DOI [10.1111/j.2517-6161.1995.tb02031.x](https://doi.org/10.1111/j.2517-6161.1995.tb02031.x)
