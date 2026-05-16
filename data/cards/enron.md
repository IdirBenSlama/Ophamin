# Dataset card — Enron email corpus

## Source

- Original release: Carnegie Mellon University (William Cohen)
  release of the 2002 Enron email corpus (~500k executive emails
  publicly released as part of the Enron investigation).
- Canonical URL: <https://www.cs.cmu.edu/~enron/>
- License: open release; treated as public-domain for research use.
  Enron Corporation never asserted copyright on the released
  archive.

## Size

- ~500,000 email messages.
- ~423MB compressed (`enron_mail_<date>.tar.gz`).
- ~1.7GB extracted.

## Schema (per record)

| Field | Type | Description |
|---|---|---|
| `id` | str | message ID assigned by the corpus connector |
| `text` | str | email body, cleaned (headers stripped, signatures preserved) |
| `metadata.sender` | str | from address |
| `metadata.subject` | str | email subject line |
| `metadata.date` | str | ISO-8601 timestamp |

## Labels

No labels in the original release. Ophamin scenarios use Enron as an
**unlabelled neutral corpus** — the substrate's response is the
signal of interest, not a label-vs-prediction comparison.

## Refresh

```bash
make data-enron        # fetches + extracts to data/raw/enron/
```

The corpus connector is at `src/ophamin/seeing/corpus/connectors.py:EnronCorpus`;
its `is_available()` predicate checks for the extracted directory
and `pytest.skip(...)` cleanly when missing.

## Used by

- `organizational-dissonance` (Scientific tier) — measures the
  dissonance-layer firing rate on routine organizational email.
- `philosophical-self-reference` (Philosophical tier) — Enron is the
  neutral baseline against which self-referential text is compared.
