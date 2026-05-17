# Migration scripts

This directory holds **one-shot scripts** for upgrading signed-record
JSON files from an older schema version to the current one.

| Script | From | To | When to run |
|---|---|---|---|
| [`campaign_1_to_2.py`](campaign_1_to_2.py) | `CampaignRecord/1.0` | `CampaignRecord/2.0` | Once, against your historical campaign corpus, when upgrading from Ophamin `< 0.9.0` to `>= 0.9.0`. Optional — 0.9.0 readers handle 1.0 records natively. |

The framework's stability contract (see
[`SCHEMAS.md` § "Migration policy"](../SCHEMAS.md)) guarantees that
**reading older records works without migration**. Migration scripts
exist only when you want to **rewrite the wire format** — e.g. so a
downstream tool that only knows the current schema can read every
record uniformly.

## Schema-2.0 migration in particular

The `1.0 → 2.0` bump is strictly additive (adds
`corrected_verdicts: dict[str, str]` + `multiplicity_correction_method: str`).
Schema-2.0 readers consume 1.0 records natively, defaulting the new
fields to empty / `"none"`. The migration script is therefore optional;
it is provided so operators who want the FWER correction populated for
historical records can run a one-pass rewrite.

**Re-signing required.** Adding fields to the canonical body invalidates
the legacy signature. The script refuses to operate without an explicit
`--sign-key-hex` argument, and the migrated records carry a NEW signature
under the supplied key. The original 1.0 file remains unchanged unless
`--in-place` is passed; with `--in` + `--out`, the original is preserved
alongside the migrated copy.

Usage example:

```bash
python migrations/campaign_1_to_2.py \
    --in campaigns/legacy/ \
    --out campaigns/migrated/ \
    --sign-key-hex 6f7068616d696e2d7363656e6172696f2d70726f6f662d6b6579 \
    --fwer-method holm \
    --fwer-alpha 0.05
```
