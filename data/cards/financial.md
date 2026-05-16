# Dataset card — Financial filings (SEC EDGAR)

## Source

- US SEC EDGAR public corporate filings:
  <https://www.sec.gov/edgar/searchedgar/companysearch>
- 10-K (annual) + 10-Q (quarterly) + 8-K (material event) filings.
- Public domain (US government release).

## Size

Varies by configured filter (which firms / which years).

A typical Ophamin run targets ~5–10 firms × ~5 years of filings = a
few hundred filings (a few hundred MB of structured text).

## Schema (per record)

| Field | Type | Description |
|---|---|---|
| `id` | str | EDGAR accession number |
| `text` | str | filing body (often very long; scenarios chunk it) |
| `metadata.firm` | str | company ticker |
| `metadata.form` | str | "10-K" / "10-Q" / "8-K" |
| `metadata.fiscal_year` | int | reporting year |
| `metadata.date_filed` | str | ISO-8601 |
| `metadata.section` | str | optional: "Risk Factors" / "MD&A" / "Notes" / ... |

## Labels

No labels. The Phase 4-10 Kimera-side SEC-EDGAR investigation used
this corpus to surface the GWF cybersecurity-vocabulary false-positive
rate (Kimera CLAUDE.md §"GWF cybersecurity-vocabulary FP limit") —
those measurements are now part of Kimera's empirical record.

## Refresh

EDGAR is rate-limited (~10 req/s) per SEC's fair-use policy. The
connector handles backoff. There is no `make data-financial` target
today; runs configure the firms + date range inline.

## Used by

- Currently no Ophamin scenario streams from this corpus directly —
  the SEC-EDGAR work was done in capture scripts on the Kimera side
  (see Kimera-SWM `experiments/the_well/sec_edgar_kimera/`).
- Future scenario candidates: a per-section dissonance-firing
  scenario; a GWF-fp-rate-at-scale scenario.
