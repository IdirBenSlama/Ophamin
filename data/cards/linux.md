# Dataset card — Linux kernel commits

## Source

- The Linux kernel git repository: <https://git.kernel.org/torvalds/linux>
- Cloned as **blobless bare**:
  `git clone --bare --filter=blob:none https://github.com/torvalds/linux.git`
- License: kernel source is GPL-2; commit messages are
  factual-statement metadata not subject to copyright claim. Ophamin
  reads commit messages only (no source code).

## Size

- ~1.4M commits as of 2026-05.
- ~12GB blobless bare clone (vs ~5GB full clone for messages alone).
- The connector only reads commit message text + author + date — no
  diff content is ingested.

## Schema (per record)

| Field | Type | Description |
|---|---|---|
| `id` | str | commit SHA (full) |
| `text` | str | commit message (subject + body) |
| `metadata.author` | str | author name + email |
| `metadata.date` | str | author-date ISO-8601 |
| `metadata.subject` | str | first line of the commit message |

## Labels

No labels. Linux is the technical-content corpus used to test
substrate behaviour on engineering / kernel / driver / build-system
discussion text.

## Refresh

```bash
make data-linux        # blobless bare clone into data/raw/linux.git/
```

Periodic re-clone is the simplest refresh; for incremental updates,
`git fetch` in the existing bare clone is the lighter path.

## Used by

- `logic-topology-siege` (Scientific tier) — measures the walker's
  sustained-traversal rate on technical content. Probe finding (5
  hand-picked kernel-style stimuli, 2026-05-15): all 5 GWF-cleared,
  all 5 halt_mode=exhausted, dissonance fires 10-27 events each —
  technical content sustains the walker more reliably than
  narrative content.
