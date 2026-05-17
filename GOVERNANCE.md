# Project governance

> **Status:** single-maintainer / BDFL (Benevolent Dictator For Life).
> **Path:** small-core-team as contributor density grows.
> **Owner:** Idir Ben Slama (`@IdirBenSlama`).

This document describes how decisions are made about Ophamin's
direction, scope, and external surface — both today, and the path the
project intends to take as it grows.

## The current state (single maintainer)

Ophamin is, as of `0.10.x`, a **single-author project** under
[Apache License 2.0](https://github.com/IdirBenSlama/Ophamin/blob/main/LICENSE). All decisions — strategic, technical,
and operational — are made by the project owner. Contributors are
welcomed via PR, but every merge is the owner's call.

This is the most honest description of the actual decision flow today.
Posting it explicitly here matters because:

- New contributors know what to expect from a PR review (one reviewer,
  the owner's calendar);
- Downstream consumers know who they're trusting when they `pip
  install ophamin`;
- Future contributors who want to take on more responsibility have a
  documented path (below) rather than relying on tribal knowledge.

## The owner's responsibilities

The owner commits to:

- **Reviewing PRs in good faith within a reasonable window.** A "reasonable window" today is best-effort and capacity-limited; once the team grows, this becomes a formal SLA.
- **Following the project's own contracts** — the wire-format stability policy in [`SCHEMAS.md`](https://github.com/IdirBenSlama/Ophamin/blob/main/SCHEMAS.md), the runtime stability policy in [`docs/STABILITY.md`](docs/STABILITY.md), the RFC process in [`docs/rfc/README.md`](docs/rfc/README.md). No private exceptions.
- **Publishing CHANGELOG entries that match wire / API reality.** Every release tag carries a CHANGELOG entry; every entry's claims are validated against the actual diff.
- **Honouring the Code of Conduct** in every project interaction.
- **Surfacing breaking decisions through an RFC** — see [`docs/rfc/0000-template.md`](docs/rfc/0000-template.md). Bug fixes and refactors that don't change behaviour go through regular PR review without an RFC.

## The owner's authority

The owner's final say covers:

- **Merge / reject decisions** on every PR;
- **Release cadence + version-bump scope** (`patch` vs `minor` vs `major`);
- **Stability tier assignments** (`@Stable` / `@Provisional` / `@Internal` / `@Deprecated`) — see [`docs/STABILITY.md`](docs/STABILITY.md);
- **Schema bump policy** — see [`SCHEMAS.md`](https://github.com/IdirBenSlama/Ophamin/blob/main/SCHEMAS.md);
- **CI workflow + branch protection settings;**
- **Trademark + naming decisions** — the project name and the Apache-2.0 license terms are non-negotiable surfaces.

## Decision-making process today

For all decisions:

1. **Bug fixes + refactors that preserve behaviour** — owner merges
   the PR; no RFC required.
2. **Design changes** (new public API, schema bump, plug-in protocol
   change) — RFC required per
   [`docs/rfc/README.md`](docs/rfc/README.md). The RFC's "Acceptance
   criteria" section is the load-bearing contract.
3. **Cross-organisation impact** (e.g. a hypothetical Kimera-specific
   change that Ophamin's substrate-agnostic core would absorb) — the
   owner consults the affected stakeholders before merging the RFC.

For all timelines:

- The owner publishes roadmap intent at [`ROADMAP.md`](https://github.com/IdirBenSlama/Ophamin/blob/main/ROADMAP.md) +
  the open RFCs under `docs/rfc/`. Both are revised in the open as
  reality changes.
- Critical security fixes are merged as fast as the verification
  allows; the SLA on those is "ASAP, with the same correctness gates
  as any release."

## Path to a small core team

When + how the governance model evolves:

| Trigger | Response |
|---|---|
| **≥ 3 external contributors with ≥ 5 merged PRs each** | Add `CODEOWNERS` lines mapping subsystems to those contributors; their approval becomes sufficient for merges in their area. |
| **≥ 1 contributor consistently reviewing PRs in the owner's absence** | Promote to **committer** (merge rights on PRs they didn't author). Documented in `CODEOWNERS`. |
| **≥ 3 committers** | Form a **core team**. Decisions previously owner-only (release timing, stability tier assignments, RFC acceptance) become 2/3 majority + owner-veto. |
| **≥ 1 active commercial deployment** | Add a **steering committee** with downstream representation. Governance becomes consensus-driven; the owner retains a tie-breaking vote and final stability-policy say. |

These thresholds are intentionally simple — when reality changes, this
document is amended in the open via an RFC, not by private edits.

## Code of Conduct enforcement

Per [`CODE_OF_CONDUCT.md`](https://github.com/IdirBenSlama/Ophamin/blob/main/CODE_OF_CONDUCT.md): reports go to the
owner's email (in CITATION.cff). In the BDFL state, the owner is both
the recipient and the arbiter. As the team grows, the CoC's enforcement
authority devolves to the core team (with the owner retaining a veto
on policy changes — never on individual enforcement decisions).

## Decisions that have already happened

These are documented in the open:

- **License: Apache-2.0** — relicensed from the original choice in the
  pre-0.8.0 audit window. See [`LICENSE`](https://github.com/IdirBenSlama/Ophamin/blob/main/LICENSE) +
  [`NOTICE`](https://github.com/IdirBenSlama/Ophamin/blob/main/NOTICE).
- **Naming: "Ophamin"** — chosen 2026-05-16 for resonance with the
  angelic order Ophanim (wheels-within-wheels covered with eyes,
  Ezekiel 1:18); architectural metaphor for the six-wheel observatory
  around the substrate-under-test. See [`docs/ELEVATION_ROADMAP_2026_05_16.md`](docs/ELEVATION_ROADMAP_2026_05_16.md) §8.
- **API stability contract** — RFC 0002 §3.2 Phase E8, landed
  in 0.10.0. See [`docs/STABILITY.md`](docs/STABILITY.md).
- **Wire-format stability contract** — landed in 0.9.0 via
  `CampaignRecord/1.0 → 2.0`. See [`SCHEMAS.md`](https://github.com/IdirBenSlama/Ophamin/blob/main/SCHEMAS.md)
  § "Case study — CampaignRecord/1.0 → 2.0".

## Amending this document

This document is amended via a normal PR + owner review. Substantial
changes (anything that affects the core-team trigger conditions or the
owner's authority list) require an RFC. The current state is the
state on `main`.
