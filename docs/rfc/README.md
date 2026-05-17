# RFC process (Phase L5)

> **Design changes follow RFC-first; bug fixes follow PR-first.**

Ophamin uses a lightweight RFC process for non-trivial design changes.
The process is deliberately minimal — one template, one numbering
scheme, one merge rule — so it stays useful without becoming bureaucracy.

## When to write an RFC

Write an RFC when the change:

- introduces or removes a **public API** (CLI command, codec function,
  Protocol interface, signed-record schema field)
- changes a **load-bearing invariant** (signature canonical form, semver
  promise on a schema, plug-in registry semantics)
- introduces a **new wheel** or splits an existing wheel
- adds a new **dependency** to `[project.dependencies]` (vs. an extra)
- changes the **substrate adapter contract** (SubstrateUnderTest
  Protocol shape)
- proposes a new **experimentation tier** in the scenario taxonomy

**Bug fixes, refactors that don't change behavior, new tests, doc
improvements, and dependency-version bumps** go through a regular PR
without an RFC.

When in doubt: file a small "RFC stub" PR with just the problem
statement + proposed direction. The maintainer either accepts (no full
RFC needed) or asks for the full document.

## RFC lifecycle

```
DRAFT  →  REVIEW  →  ACCEPTED  →  IMPLEMENTED
                  ↓
                REJECTED
```

1. **DRAFT**: open a PR adding `docs/rfc/NNNN-<short-slug>.md` based on
   [`0000-template.md`](0000-template.md). Reserve the next available
   number; if multiple drafts race, the first merged wins the number
   and others rebase.
2. **REVIEW**: discussion happens on the PR. Substantive comments
   should reference the RFC body's section IDs so revisions are
   traceable.
3. **ACCEPTED**: the maintainer merges the RFC PR with status
   ACCEPTED. Code-implementation PRs reference the RFC number.
4. **IMPLEMENTED**: once the code lands and the RFC's
   "acceptance criteria" are met, a follow-up PR updates the RFC's
   status to IMPLEMENTED and links the implementing commit(s).
5. **REJECTED**: an RFC may be closed without merging if the proposal
   doesn't survive review. The PR is closed with a comment summarising
   why; the slug remains reserved so future authors don't reuse it.

## Numbering

- `0000` — template (this directory's template file).
- `0001..NNNN` — accepted RFCs in chronological order.
- Drafts in PRs use `NNNN` placeholder until merged.

## Existing architectural decisions

The audits and extended-audit documents under [`docs/`](../index.md)
(`ARCHITECTURE_EXTENDED_AUDIT_*.md`,
`ARCHITECTURE_INTENT_VS_REALITY_*.md`,
`ELEVATION_ROADMAP_*.md`) predate this RFC process and stand as the
canonical record of pre-0.8.0 design decisions. They will be
retrospectively re-numbered as RFCs `0001` onward in a follow-up;
new design changes start using RFC numbers ≥ 0002.

## Reviewer checklist

Use this when reviewing an RFC PR:

- [ ] Problem statement is concrete (cites a specific issue / failure)
- [ ] Alternatives section discusses ≥ 2 alternatives + why-not
- [ ] Backward-compat impact is explicit (schemas / wire format / CLI)
- [ ] Acceptance criteria are testable (not "feels right")
- [ ] Drawbacks are honestly listed (not just upsides)
- [ ] If the RFC introduces a new signed-record schema or modifies an
      existing one, [`SCHEMAS.md`](https://github.com/IdirBenSlama/Ophamin/blob/main/SCHEMAS.md) update is part of
      the implementation plan

## Where this came from

This RFC process was introduced as Phase L5 of the elevation roadmap
([`docs/ELEVATION_ROADMAP_2026_05_16.md`](../ELEVATION_ROADMAP_2026_05_16.md)).
The motivation was that as Ophamin gains external consumers, design
changes that affect public surface need a written record that
predates the implementation — otherwise the "why" of any non-obvious
choice evaporates the moment the deciding author leaves the project.
