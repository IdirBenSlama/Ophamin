# RFC 0001 — Retrospective pointer to pre-0.8.0 architecture decisions

| | |
|---|---|
| **Status** | ACCEPTED |
| **Author** | Idir Ben Slama |
| **Created** | 2026-05-17 |
| **Last updated** | 2026-05-17 |
| **Discussion** | landed alongside 0.8.2 (no PR review — author-acknowledged retrospective) |
| **Implementation PR(s)** | n/a — this RFC is itself the artefact |

---

## 1. Summary

The RFC process introduced in Phase L5 (0.8.0) covers design changes
**going forward**. The framework's pre-0.8.0 architectural decisions
are captured in five existing audit / roadmap / authoring documents
under [`docs/`](https://github.com/IdirBenSlama/Ophamin/blob/main/docs/).
This RFC records that those documents stand as the **canonical
retrospective design record** for everything before 0.8.0, and
declares the indexing rule for navigating between them.

It also functions as the **first concrete use of the L5 process** —
demonstrating that the template works, the numbering scheme survives
contact with real material, and the lifecycle terminates at ACCEPTED.

## 2. Problem statement

Phase L5 (0.8.0) added an RFC process for design changes. But the
framework already had ~14 months of architectural decisions that
predated the process:

- **Move A** introduced the 4-Protocol plug-in registry (Pillar,
  ScenarioProtocol, DatasetConnector, SubstrateProbe)
- **Move F** introduced the 6-phase campaign orchestrator
- **Move L** introduced the int→float coercion in `Threshold` /
  `Verdict` for canonical-form stability
- **Move N** introduced optional pre-registration + verdict on
  `AuditRecord` (v1.0 → v1.1)
- The 19 scenarios across 5 experimentation tiers all landed without
  RFC review
- The signed-record schema policy in [`SCHEMAS.md`](https://github.com/IdirBenSlama/Ophamin/blob/main/SCHEMAS.md)
  formalised an implicit policy that had been operationally
  load-bearing since 0.5.0

Without a record that these decisions exist + were deliberate, a
future contributor reading only `docs/rfc/` would conclude that
**nothing** had been designed before 0.8.0 — which is the opposite of
true. The audit documents under `docs/` carry the actual record;
this RFC indexes them.

## 3. Proposed change

### 3.1 Recognise existing docs as the retrospective record

Five documents under [`docs/`](https://github.com/IdirBenSlama/Ophamin/blob/main/docs/)
together form the pre-0.8.0 design record:

| Document | Captures |
|---|---|
| [`ARCHITECTURE_EXTENDED_AUDIT_2026_05_16.md`](https://github.com/IdirBenSlama/Ophamin/blob/main/docs/ARCHITECTURE_EXTENDED_AUDIT_2026_05_16.md) | the 16-deficit audit that drove the elevation roadmap; named every gap with concrete evidence |
| [`ARCHITECTURE_INTENT_VS_REALITY_2026_05_16.md`](https://github.com/IdirBenSlama/Ophamin/blob/main/docs/ARCHITECTURE_INTENT_VS_REALITY_2026_05_16.md) | per-wheel intent-vs-reality narrative; the deliberate framing |
| [`ELEVATION_ROADMAP_2026_05_16.md`](https://github.com/IdirBenSlama/Ophamin/blob/main/docs/ELEVATION_ROADMAP_2026_05_16.md) | the four-stage plan: S1–S6 internal hardening + L1–L6 external legitimacy |
| [`KIMERA_OBSERVATIONAL_SURFACE_2026_05_15.md`](https://github.com/IdirBenSlama/Ophamin/blob/main/docs/KIMERA_OBSERVATIONAL_SURFACE_2026_05_15.md) | how Ophamin "sees" Kimera; the substrate-adapter contract narrative |
| [`PLUGIN_CATALOG_2026_05_15.md`](https://github.com/IdirBenSlama/Ophamin/blob/main/docs/PLUGIN_CATALOG_2026_05_15.md) | the plug-in surface (every protocol + every concrete implementation + version requirement) |
| [`SCENARIO_AUTHORING.md`](https://github.com/IdirBenSlama/Ophamin/blob/main/docs/SCENARIO_AUTHORING.md) | the authoring contract for new scenarios |

These five documents are referenced by-name in `docs/rfc/README.md`'s
"Existing architectural decisions" section.

### 3.2 Indexing rule

When a future RFC needs to cite a pre-0.8.0 decision, it links to the
relevant audit document directly:

```markdown
See [`ARCHITECTURE_EXTENDED_AUDIT_2026_05_16.md` §Move F](https://github.com/IdirBenSlama/Ophamin/blob/main/docs/ARCHITECTURE_EXTENDED_AUDIT_2026_05_16.md)
for the original CampaignRecord design.
```

Audit documents are NOT renumbered as RFCs. Reasons:

- they're long, dense, and rewriting them into the RFC template would
  destroy their actual structure
- they reference specific dates + measurement records that lose
  meaning when divorced from their original context
- the load-bearing thing about an RFC is the *process* (problem,
  alternatives, drawbacks, acceptance criteria); applying that
  template retroactively is theatre, not validation

### 3.3 Public surface impact

- **CLI**: no change.
- **Codec / wire format**: no change.
- **Protocol interface**: no change.
- **Optional dependencies**: no change.
- **Docs**: `docs/rfc/README.md` already references the audit
  documents under §"Existing architectural decisions". This RFC
  ratifies that pointer.

### 3.4 Backward compatibility

n/a — this RFC is documentary, not architectural.

## 4. Alternatives considered

### 4.1 Renumber every audit document as RFC 0001..0006

Mechanical, but expensive. The audit documents are large prose
artefacts capturing dated empirical state, not abstract design
proposals. Forcing them through the RFC template structure would
lose information without adding any.

### 4.2 Do nothing (no retrospective RFC at all)

A future reader of `docs/rfc/` would conclude no design had happened
before 0.8.0. Bad for new contributors trying to understand why
things are the way they are.

### 4.3 Write one retrospective summary RFC (this proposal)

Light, accurate, points readers at the actual record. Doubles as a
canary that the L5 process works end-to-end.

## 5. Drawbacks

- New contributors might assume audit documents = "RFCs" by analogy
  and try to write new design proposals in audit style. The
  `docs/rfc/0000-template.md` is the authoritative template; this
  RFC's "Where this came from" framing reinforces it.
- The retrospective pointer is a one-time artefact. Future
  retrospectives (e.g. when 1.0.0 ships) should produce their own
  RFCs at that point, not append to this one.

## 6. Acceptance criteria

- [x] `docs/rfc/README.md` references the pre-0.8.0 audit documents
      under §"Existing architectural decisions" (already in place
      since 0.8.0; this RFC ratifies that)
- [x] This RFC exists as `docs/rfc/0001-retrospective-pre-0.8.0-architecture.md`
- [x] The RFC numbering scheme (`0001-<slug>.md`) is exercised end-to-end
- [x] The L5 lifecycle (DRAFT → ACCEPTED) terminates correctly

## 7. Migration plan

n/a — no migration required.

## 8. Open questions

None.

## 9. References

- The five referenced audit documents (links in §3.1)
- [`docs/rfc/README.md`](README.md) — the L5 process documentation
- [`docs/rfc/0000-template.md`](0000-template.md) — the RFC template
