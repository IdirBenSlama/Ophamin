# Dataset cards

One Markdown card per corpus connector. Each card covers:

- **Source** — where the data comes from + canonical license.
- **Size** — record count + on-disk footprint.
- **Schema** — what fields each record carries.
- **Labels** — explicit label vocabulary (when applicable).
- **Refresh** — how to (re-)download or update.
- **Used by** — which Ophamin scenarios stream from this corpus.

Cards follow the spirit of HuggingFace's
[dataset-card-template](https://github.com/huggingface/datasets-tagging)
adapted to the scope Ophamin needs.

## Index

| Corpus | Card |
|---|---|
| Enron email | [`enron.md`](enron.md) |
| Linux kernel commits | [`linux.md`](linux.md) |
| FLORES-200 parallel text | [`flores.md`](flores.md) |
| Offensive-security curated bundle | [`offensive_security.md`](offensive_security.md) |
| Financial filings (SEC EDGAR) | [`financial.md`](financial.md) |
| The Well — physics simulation HDF5 | [`the_well.md`](the_well.md) |
