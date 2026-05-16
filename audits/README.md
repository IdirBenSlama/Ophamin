# `audits/` — signed AuditRecord artifacts

Every `*.json` file in this directory is an
:class:`ophamin.auditing.audit_record.AuditRecord` written by
`ophamin audit <path>`. Like proof records, audit records are
content-addressed and HMAC-signed; unlike proof records they are
**descriptive** rather than falsifiable by default — the value is
in the findings distribution, not in passing a threshold.

## Layout

Currently flat. Per-Kimera-commit subdirectories (e.g.
`audits/kimera-<short-commit>/`) are a convention-only suggestion
when the corpus grows past ~20 files.

## Regenerating

```bash
ophamin audit <path> --out-dir audits/
```

## Open: audit-record codec

The proof-record codec (`ophamin.measuring.proof.codec`) provides a
single canonical load / validate / verify / ingest surface for proof
records. The same shape applies cleanly to audit records — that's a
follow-on Move (open per `docs/ARCHITECTURE_EXTENDED_AUDIT_2026_05_16.md`
Move B's open note).
