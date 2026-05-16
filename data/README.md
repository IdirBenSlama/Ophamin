# `data/` — corpora + datasets the substrate reads

Sub-layout:

```
data/
  raw/                          source-of-truth corpora (gitignored)
                                — Enron emails, Linux kernel commits,
                                  FLORES-200 parallel text, etc.
  zeta_zeros/                   pre-computed Riemann zeta zeros (small
                                fixture used by prime-related scenarios)
  README.md                     this file
```

## `data/raw/` — corpora the substrate streams through

Gitignored by default — the corpora are large (Enron ~500MB, Linux
kernel ~5GB blobless bare clone, FLORES-200 ~150MB). The canonical
fetch commands live in `Makefile` targets:

```bash
make data-enron        # fetch the CMU Enron release
make data-linux        # clone torvalds/linux blobless+bare
make data-flores       # fetch FLORES-200 from the NLLB release
make data-cyber        # fetch the offensive-security curated bundle
```

Each corpus has a Python connector in
`src/ophamin/seeing/corpus/<corpus>.py` that reads from
`data/raw/<corpus>/`. The connector's `is_available()` predicate is
the runtime check; scenarios `pytest.skip(...)` cleanly when a
corpus isn't installed.

## `data/zeta_zeros/` — fixture

Small (a few MB) lookup table of the first N Riemann zeta zeros, used
by the prime-wave-related scenarios as a reference dataset. Tracked
in git because of its size + immutable nature.

## Open: per-corpus dataset cards

A future Move (E in the extended audit) will add a per-corpus
`<corpus>_DATASET.md` card with: source URL, license, size, label
schema, known biases, refresh frequency. Following HuggingFace
`datasets` convention.
