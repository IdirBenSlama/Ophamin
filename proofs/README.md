# `proofs/` — signed Empirical Proof Records

Every `*.json` file in this directory is an
:class:`ophamin.measuring.proof.EmpiricalProofRecord` written by a
scenario via the standard `Scenario.run` path. The companion `*.md`
files are the Markdown rendering of the same record (`record.to_markdown()`).

**Every record is content-addressed and HMAC-signed** — the filename
hash is the proof_id's prefix; the on-disk content can be verified
end-to-end via:

```bash
ophamin proof verify <path>             # HMAC-only
ophamin proof validate <path> --with-signature   # schema + structural + signature
ophamin proof ingest <path> --strict-signature   # full pipeline, loud-failure
```

For a directory-level summary use `ophamin proof index <directory>`
(generates `INDEX.md`) or `ophamin proof list <directory>`
(prints a verdict / schema / signature table to stdout).

## Layout — per-tier subdirectories (canonical for new proofs)

New proofs (from 2026-05-16 onward) land in per-tier subdirectories
that mirror the `Scenario.tier` enum:

```
proofs/
  scientific/           Tier.SCIENTIFIC scenarios (immune, rosetta,
                        dissonance, walker, interface, completeness, memory)
  engineering/          Tier.ENGINEERING (throughput-ceiling et al)
  philosophical/        Tier.PHILOSOPHICAL (self-reference et al)
  empirical_deep/       Tier.EMPIRICAL_DEEP (phi, causal, mi, prime, quantum)
  measurement_machinery/  Tier.MEASUREMENT_MACHINERY (crdt-laws et al)
  INDEX.md              master manifest — regenerate via `ophamin proof index`
  README.md             this file
```

A scenario's `tier` attribute is the canonical authority on which
subdirectory its proof should land in. Within a tier, family-level
grouping (per-scenario subdir if useful, e.g.
`scientific/immune/<proof>.json`) is convention-only — the family
attribute on `Scenario` is descriptive, not enforced as a path.

## Legacy flat-layout proofs (pre-2026-05-16)

Records written before Move A + Move B landed (the metadata schema +
codec, respectively) live at the top level of this directory. They
remain valid signed proofs — content-addressing and HMAC verification
work identically. They are NOT relocated by automated tooling
because moving them would change their on-disk paths in any
external reference (CHANGELOG entries, journal log lines, MLflow
artifacts pointing at them). The INDEX.md surfaces them alongside the
new per-tier layout.

## Filename convention

Both legacy and new proofs follow:

```
<scenario-name>[_<target>]_<short-proof-id>.json
<scenario-name>[_<target>]_<short-proof-id>.md
```

where `<short-proof-id>` is the first 16 hex characters of the
SHA-256 content hash (the full hash is in the file's `proof_id`
field). The `_<target>` segment is included when the scenario's
target attribute is informationally useful (e.g.
`immune_siege_entity_*` vs `immune_siege_gwf_*` — the same scenario
exercised against two different Kimera adapters).

## Regenerating the master index

```bash
ophamin proof index proofs/ --out proofs/INDEX.md
```

This walks recursively, classifies each record by verdict + family
(heuristic from filename), and writes the rolled-up Markdown
manifest. It is safe to re-run — the index file is fully regenerated
each time. The codec's `build_index()` function is the same
machinery if a Python caller wants the structured `ProofIndex`
dataclass.

## Adding a new proof

A scenario writes its proof via `Scenario.run`; the harness handles
signing + content-addressing. Operator code typically does:

```python
record = MyScenario().run(substrate)
ophamin.measuring.proof.dump(record, "proofs/<tier>/<family>/<filename>.json")
```

Then regenerate the index:

```bash
ophamin proof index proofs/ --out proofs/INDEX.md
```

The pre-registration discipline ensures the claim + threshold +
analysis plan were captured BEFORE the substrate ran — a REFUTED
verdict is a result, not a failure to measure.
