# Dataset card — FLORES-200 sentence-aligned parallel text

## Source

- The NLLB (No Language Left Behind) team's FLORES-200 evaluation
  set: <https://github.com/facebookresearch/flores>
- Each sentence group is the same source sentence translated into up
  to 200 languages.
- License: CC-BY-SA-4.0.

## Size

- ~3,000 sentence groups (the "devtest" split is the standard
  benchmark partition).
- Each group has translations into up to 200 languages.
- Total ~150MB compressed.

## Schema (per record)

| Field | Type | Description |
|---|---|---|
| `id` | str | sentence-group id |
| `text` | str | one translation (the scenario picks K translations per group) |
| `metadata.language` | str | ISO 639-3 language code |
| `metadata.group_id` | str | parent sentence-group id (== `id` prefix) |
| `metadata.reference_text` | str | the source-language reference for the group |

## Labels

No threshold labels; the **group_id is the load-bearing axis** — a
scenario testing language-invariance fans K translations of the same
group through the substrate and measures whether the substrate's
output collapses to a single canonical.

## Refresh

```bash
make data-flores       # fetches the FLORES-200 release to data/raw/flores/
```

## Used by

- `rosetta-scaling` (Scientific tier) — measures Rosetta's
  universal-semantic-address invariance across K aligned translations
  per group. Threshold (default 80% at K=10) tests whether the
  registry + encoder-fallback together honour the promise on whole
  sentences.
