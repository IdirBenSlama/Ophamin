# `reports/` — rendered output (HTML / Markdown / LaTeX)

Output of `ophamin report <record.json> --format <html|markdown|latex>`.
The companion `assets/` directory carries chart PNGs referenced by the
HTML and LaTeX renderers.

## Layout

```
reports/
  assets/                       chart PNGs (referenced by HTML + LaTeX)
  <record-name>.html            HTML rendering of a record
  <record-name>.md              Markdown rendering (also written by the
                                proof harness — same file as
                                proofs/<record>.md)
  <record-name>.tex             LaTeX rendering (compile-ready)
  README.md                     this file
```

## Regenerating

```bash
ophamin report proofs/<record>.json --format html --out-dir reports/
ophamin report audits/<record>.json --format latex --out-dir reports/
```

The Markdown rendering written next to the JSON in `proofs/` is the
canonical human-facing form; `reports/` carries the HTML + LaTeX
variants for academic-grade output.

## Open: campaign-level reports

Today reports are per-record. A campaign-level renderer that walks
`proofs/` (using the codec's `list_proofs` + `build_index` helpers)
and emits a single rolled-up HTML / Markdown / LaTeX document is
the natural extension — covered by Move D
(`ophamin summarize`) in the extended audit.
