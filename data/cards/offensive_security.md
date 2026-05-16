# Dataset card — Offensive-security curated bundle

## Source

A curated bundle of labelled adversarial-input corpora pulled from
public security tooling repositories. Sources:

- **Metasploit Framework** — exploit / payload templates.
- **SecLists** — wordlists, payloads, scanning patterns.
- **PayloadsAllTheThings** — injection / XSS / SSRF payloads.
- **nuclei-templates** — vulnerability scanning templates.
- **atomic-red-team** — MITRE ATT&CK technique demonstrations.
- **exploit-db** — public CVE PoCs.
- **garak** — LLM jailbreak / prompt-injection benchmarks.
- **deepset prompt-injection** — labelled benign vs injection pairs.
- **jackhhao jailbreak** — labelled benign vs jailbreak pairs.

Licenses are per-source; all sources are publicly available open-source
security tooling. The bundle is for defensive measurement use.

## Size

- ~4.4 million records (deduplicated across sources).
- ~5.5GB extracted (text + minimal metadata; binaries not included).

## Schema (per record)

| Field | Type | Description |
|---|---|---|
| `id` | str | source-prefixed unique id |
| `text` | str | the adversarial / benign input under test |
| `metadata.source` | str | origin (metasploit / seclists / deepset / …) |
| `metadata.label` | str | "benign" / "jailbreak" / "injection" / "malicious" / etc. — see scenario for vocab |

## Labels

Two vocabularies in active use (the connector exposes the source label verbatim):

- **deepset** uses ``0`` / ``1`` for benign / injection.
- **jackhhao** uses ``benign`` / ``jailbreak``.

The `concentrated-immune-siege` scenario normalises both into its
internal `_MALICIOUS` / `_BENIGN` set vocabulary.

## Refresh

```bash
make data-cyber        # fetches + extracts to data/raw/cyber/
```

The connector is at `src/ophamin/seeing/corpus/connectors.py:OffensiveSecurityCorpus`.

## Used by

- `concentrated-immune-siege` (Scientific tier) — measures Kimera's
  GWF false-positive ceiling on benign-labelled inputs.
- `throughput-ceiling` (Engineering tier) — uses the cyber corpus as
  a balanced text load for per-cycle wall-time profiling (any text
  corpus would work; cyber is convenient because of the label split).
