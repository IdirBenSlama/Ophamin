"""Migrate CampaignRecord JSON files from schema 1.0 → 2.0.

The bump is strictly additive: 2.0 adds ``corrected_verdicts``
(dict[str, str]) and ``multiplicity_correction_method`` (str). The
schema policy in `SCHEMAS.md` documents this as the canonical case
study for additive minor-bumps with version-aware canonicalization.

This script's contract:

* Input: a directory containing CampaignRecord JSON files (any
  schema_version; non-matching files are skipped).
* Output: an in-place rewrite or sibling directory containing 2.0-shaped
  records whose ``schema_version`` is set to ``"2.0"``, with
  ``corrected_verdicts`` populated from the FWER correction pass
  (default ``method="holm"`` over the proofs the record references
  via its ``measuring`` phase's ``proofs/`` artefact) and the
  multiplicity-correction method recorded explicitly.
* The original signature is **invalidated** by the bump (additive
  fields change the canonical body) — the migrated record is re-signed
  under the same key. The migration script REFUSES to operate without
  an explicit ``--sign-key`` argument, so the operator must consciously
  re-attribute the file to the new wire form.

Usage::

    python migrations/campaign_1_to_2.py \
        --in campaigns/before \
        --out campaigns/after \
        --sign-key-hex DEADBEEF... \
        --fwer-method holm \
        --fwer-alpha 0.05

Or in-place (overwrites originals)::

    python migrations/campaign_1_to_2.py \
        --in-place campaigns/legacy \
        --sign-key-hex DEADBEEF...

The script exits with code 0 on success, 2 on documented input failure,
and 64 on argv misuse (mirrors the framework's CLI exit-code convention).
"""

from __future__ import annotations

import argparse
import binascii
import json
import sys
from pathlib import Path

from ophamin.campaign import (
    CampaignRecord,
    correction_family_from_directory,
    dump_campaign,
    load_campaign,
)


def _hex_key(value: str) -> bytes:
    try:
        return binascii.unhexlify(value.replace(" ", ""))
    except binascii.Error as exc:
        raise argparse.ArgumentTypeError(
            f"--sign-key-hex must be hex-encoded bytes, got: {exc}"
        ) from exc


def migrate_one(
    src_path: Path,
    *,
    sign_key: bytes,
    fwer_method: str,
    fwer_alpha: float,
    proofs_dir_override: Path | None,
) -> CampaignRecord:
    """Load a single CampaignRecord; emit a 2.0-shaped, re-signed record.

    Args:
        src_path: input JSON file containing a CampaignRecord (schema 1.0
            or 2.0; passing a 2.0 file is a no-op for the schema bump
            itself but still re-applies the FWER pass).
        sign_key: HMAC-SHA256 key to sign the migrated record with.
        fwer_method: ``"holm"`` / ``"bh"`` / ``"none"``.
        fwer_alpha: family-wise / FDR threshold.
        proofs_dir_override: if not ``None``, use this directory as the
            proofs root for the FWER pass instead of the heuristic
            ``<campaign-dir>/proofs/``.

    Returns:
        A signed :class:`~ophamin.campaign.CampaignRecord` at
        schema_version ``"2.0"``.
    """
    record = load_campaign(src_path)
    record.schema_version = "2.0"
    proofs_dir = (
        proofs_dir_override
        if proofs_dir_override is not None
        else src_path.parent / "proofs"
    )
    if proofs_dir.is_dir():
        family = correction_family_from_directory(
            proofs_dir, method=fwer_method, alpha=fwer_alpha
        )
        record.corrected_verdicts = family.verdicts()
        record.multiplicity_correction_method = family.method
    else:
        record.corrected_verdicts = {}
        record.multiplicity_correction_method = "none"
    # Re-sign under the supplied key; additive fields change the body
    # so the legacy signature is no longer valid.
    record.sign(sign_key)
    return record


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="campaign_1_to_2",
        description=(
            "Migrate CampaignRecord JSON files from schema 1.0 → 2.0. "
            "Re-signs each record with the supplied key — the migrated "
            "records carry NEW signatures; the original 1.0 signatures "
            "cannot be carried forward."
        ),
    )
    source_group = parser.add_mutually_exclusive_group(required=True)
    source_group.add_argument(
        "--in",
        dest="in_dir",
        type=Path,
        help="input directory containing CampaignRecord JSON files",
    )
    source_group.add_argument(
        "--in-place",
        dest="in_place",
        type=Path,
        help="rewrite files in this directory in place",
    )
    parser.add_argument(
        "--out",
        dest="out_dir",
        type=Path,
        help="output directory for migrated records (required with --in)",
    )
    parser.add_argument(
        "--sign-key-hex",
        required=True,
        type=_hex_key,
        help="HMAC-SHA256 sign key as hex-encoded bytes",
    )
    parser.add_argument(
        "--fwer-method",
        default="holm",
        choices=["holm", "bh", "none"],
        help="multiplicity-correction method to apply (default: holm)",
    )
    parser.add_argument(
        "--fwer-alpha",
        default=0.05,
        type=float,
        help="family-wise / FDR threshold (default: 0.05)",
    )
    parser.add_argument(
        "--proofs-dir",
        type=Path,
        default=None,
        help="override the auto-discovered proofs directory",
    )
    parser.add_argument(
        "--glob",
        default="*.json",
        help="filename glob to match within the source directory (default: *.json)",
    )
    args = parser.parse_args(argv)

    if args.in_dir is not None:
        if args.out_dir is None:
            parser.error("--out is required when --in is used")
        source_dir = args.in_dir
        in_place = False
    else:
        source_dir = args.in_place
        in_place = True

    if not source_dir.is_dir():
        print(
            f"error: source directory {source_dir!r} does not exist",
            file=sys.stderr,
        )
        return 2

    if not in_place:
        args.out_dir.mkdir(parents=True, exist_ok=True)

    n_migrated = 0
    n_skipped = 0
    n_failed = 0
    for src in sorted(source_dir.glob(args.glob)):
        try:
            text = src.read_text(encoding="utf-8")
            data = json.loads(text)
        except (OSError, json.JSONDecodeError) as exc:
            print(f"skip {src}: {exc}", file=sys.stderr)
            n_skipped += 1
            continue
        if not isinstance(data, dict) or "phases" not in data:
            n_skipped += 1
            continue
        try:
            migrated = migrate_one(
                src,
                sign_key=args.sign_key_hex,
                fwer_method=args.fwer_method,
                fwer_alpha=args.fwer_alpha,
                proofs_dir_override=args.proofs_dir,
            )
        except Exception as exc:  # noqa: BLE001 — surface every failure with path
            print(f"error migrating {src}: {type(exc).__name__}: {exc}", file=sys.stderr)
            n_failed += 1
            continue
        dest = src if in_place else (args.out_dir / src.name)
        dump_campaign(migrated, dest)
        n_migrated += 1
        print(f"migrated {src} → {dest}")

    print(
        f"\nMigration complete: {n_migrated} migrated, {n_skipped} skipped, "
        f"{n_failed} failed.",
        file=sys.stderr,
    )
    return 0 if n_failed == 0 else 2


if __name__ == "__main__":
    raise SystemExit(main())
