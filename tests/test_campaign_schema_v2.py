"""Tests for the CampaignRecord 1.0 → 2.0 schema bump.

Three guarantees pinned here:

1. **New writers always emit 2.0** — :data:`CAMPAIGN_SCHEMA_VERSION`
   is ``"2.0"`` and a freshly-built record carries that version.

2. **Legacy 1.0 records remain readable + signature-verifiable** —
   round-trip a hand-built 1.0 record (no ``corrected_verdicts``,
   no ``multiplicity_correction_method`` in the wire form) and
   confirm the signature still verifies under the original key. The
   schema-2.0 reader must produce a body bit-equal to the original
   1.0 body so the HMAC chain stays intact.

3. **2.0 records round-trip + verify with the new fields populated** —
   build a 2.0 record with non-empty ``corrected_verdicts`` and
   ``multiplicity_correction_method``, dump + load, confirm signature
   re-verifies and the new fields survive.
"""

from __future__ import annotations

import hashlib
import hmac
import json
from pathlib import Path
from typing import Any

import pytest

from ophamin.campaign import (
    CAMPAIGN_SCHEMA_VERSION,
    SUPPORTED_CAMPAIGN_SCHEMA_VERSIONS,
    CampaignPhase,
    CampaignRecord,
    dump_campaign,
    load_campaign,
)
from ophamin.measuring.scenarios.base import DEFAULT_SIGN_KEY


# ---------------------------------------------------------------------------
# Schema-version constants
# ---------------------------------------------------------------------------


def test_default_schema_version_is_2_0() -> None:
    assert CAMPAIGN_SCHEMA_VERSION == "2.0"


def test_supported_versions_include_both_1_0_and_2_0() -> None:
    assert "1.0" in SUPPORTED_CAMPAIGN_SCHEMA_VERSIONS
    assert "2.0" in SUPPORTED_CAMPAIGN_SCHEMA_VERSIONS


def test_fresh_record_defaults_to_current_version() -> None:
    rec = CampaignRecord(target_name="t", target_git_commit="deadbeef")
    assert rec.schema_version == "2.0"
    assert rec.corrected_verdicts == {}
    assert rec.multiplicity_correction_method == "none"


# ---------------------------------------------------------------------------
# Schema-2.0 round-trip + signature
# ---------------------------------------------------------------------------


def test_2_0_record_round_trip_preserves_new_fields(tmp_path: Path) -> None:
    rec = CampaignRecord(
        target_name="kimera",
        target_git_commit="cafebabe",
        phases=[
            CampaignPhase(
                wheel="measuring",
                started_at="2026-05-17T00:00:00+00:00",
                completed_at="2026-05-17T00:01:00+00:00",
                status="ok",
                summary={"n_proofs": 19},
            )
        ],
        completed_at="2026-05-17T00:01:30+00:00",
        ophamin_git_commit="badf00d",
        corrected_verdicts={
            "proof-abc": "VALIDATED",
            "proof-def": "INCONCLUSIVE",
        },
        multiplicity_correction_method="holm",
    )
    rec.sign(DEFAULT_SIGN_KEY)

    path = tmp_path / "campaign.json"
    dump_campaign(rec, path)
    loaded = load_campaign(path)

    assert loaded.schema_version == "2.0"
    assert loaded.corrected_verdicts == {
        "proof-abc": "VALIDATED",
        "proof-def": "INCONCLUSIVE",
    }
    assert loaded.multiplicity_correction_method == "holm"
    assert loaded.verify_signature(DEFAULT_SIGN_KEY) is True
    assert loaded.campaign_id == rec.campaign_id


def test_2_0_record_signature_binds_corrected_verdicts(tmp_path: Path) -> None:
    """Mutating corrected_verdicts after signing must invalidate the signature."""
    rec = CampaignRecord(
        target_name="kimera",
        target_git_commit="cafebabe",
        corrected_verdicts={"proof-abc": "VALIDATED"},
        multiplicity_correction_method="holm",
    )
    rec.sign(DEFAULT_SIGN_KEY)
    assert rec.verify_signature(DEFAULT_SIGN_KEY) is True

    rec.corrected_verdicts["proof-abc"] = "INCONCLUSIVE"
    assert rec.verify_signature(DEFAULT_SIGN_KEY) is False


def test_2_0_record_signature_binds_method(tmp_path: Path) -> None:
    """Method swap after signing must invalidate the signature."""
    rec = CampaignRecord(
        target_name="kimera",
        target_git_commit="cafebabe",
        corrected_verdicts={"proof-abc": "VALIDATED"},
        multiplicity_correction_method="holm",
    )
    rec.sign(DEFAULT_SIGN_KEY)
    rec.multiplicity_correction_method = "bh"
    assert rec.verify_signature(DEFAULT_SIGN_KEY) is False


# ---------------------------------------------------------------------------
# Backward compat: 1.0 records remain verifiable
# ---------------------------------------------------------------------------


def _legacy_1_0_body(
    *,
    target_name: str,
    target_git_commit: str,
    started_at: str,
    completed_at: str,
    ophamin_version: str,
    ophamin_git_commit: str,
    phases: list[dict[str, Any]],
) -> dict[str, Any]:
    """Build a 1.0-shaped body — same order/fields as the pre-bump _body."""
    return {
        "schema_version": "1.0",
        "target_name": target_name,
        "target_git_commit": target_git_commit,
        "started_at": started_at,
        "completed_at": completed_at,
        "ophamin_version": ophamin_version,
        "ophamin_git_commit": ophamin_git_commit,
        "phases": phases,
    }


def _canonical_legacy(obj: dict[str, Any]) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), default=str)


def test_legacy_1_0_record_loads_and_verifies(tmp_path: Path) -> None:
    """Round-trip a hand-built 1.0 record signed under 1.0 canonicalization."""
    body = _legacy_1_0_body(
        target_name="kimera",
        target_git_commit="cafebabe",
        started_at="2026-05-15T00:00:00+00:00",
        completed_at="2026-05-15T00:01:00+00:00",
        ophamin_version="0.8.5",
        ophamin_git_commit="deadbeef",
        phases=[
            {
                "wheel": "measuring",
                "started_at": "2026-05-15T00:00:00+00:00",
                "completed_at": "2026-05-15T00:00:30+00:00",
                "status": "ok",
                "artifact_paths": [],
                "summary": {"n_proofs": 5},
                "error": None,
            },
        ],
    )
    signature = hmac.new(
        DEFAULT_SIGN_KEY,
        _canonical_legacy(body).encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()
    campaign_id = hashlib.sha256(
        _canonical_legacy(body).encode("utf-8")
    ).hexdigest()

    wire = {"campaign_id": campaign_id, **body, "signature": signature}
    path = tmp_path / "campaign_1_0.json"
    path.write_text(json.dumps(wire, indent=2), encoding="utf-8")

    loaded = load_campaign(path)
    assert loaded.schema_version == "1.0"
    # Schema-2.0 additive fields default to empty/none on a 1.0 read.
    assert loaded.corrected_verdicts == {}
    assert loaded.multiplicity_correction_method == "none"
    # Signature verifies despite the new schema-2.0 fields being absent
    # from the body — the version-aware _body() omits them when
    # schema_version == "1.0".
    assert loaded.verify_signature(DEFAULT_SIGN_KEY) is True
    assert loaded.campaign_id == campaign_id


def test_legacy_1_0_round_trip_keeps_1_0_version(tmp_path: Path) -> None:
    """Loading + dumping a 1.0 record preserves the 1.0 version, not bump."""
    body = _legacy_1_0_body(
        target_name="kimera",
        target_git_commit="cafebabe",
        started_at="2026-05-15T00:00:00+00:00",
        completed_at="2026-05-15T00:01:00+00:00",
        ophamin_version="0.8.5",
        ophamin_git_commit="deadbeef",
        phases=[],
    )
    signature = hmac.new(
        DEFAULT_SIGN_KEY,
        _canonical_legacy(body).encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()
    campaign_id = hashlib.sha256(
        _canonical_legacy(body).encode("utf-8")
    ).hexdigest()
    wire = {"campaign_id": campaign_id, **body, "signature": signature}
    path = tmp_path / "campaign_1_0.json"
    path.write_text(json.dumps(wire), encoding="utf-8")

    loaded = load_campaign(path)
    path2 = tmp_path / "campaign_1_0_roundtrip.json"
    dump_campaign(loaded, path2)
    loaded2 = load_campaign(path2)
    assert loaded2.schema_version == "1.0"  # preserved, not promoted
    assert loaded2.verify_signature(DEFAULT_SIGN_KEY) is True


def test_unknown_schema_version_is_rejected_loud(tmp_path: Path) -> None:
    """An unknown schema_version on the wire raises at load time."""
    body = _legacy_1_0_body(
        target_name="kimera",
        target_git_commit="cafebabe",
        started_at="2026-05-15T00:00:00+00:00",
        completed_at="2026-05-15T00:01:00+00:00",
        ophamin_version="0.8.5",
        ophamin_git_commit="deadbeef",
        phases=[],
    )
    body["schema_version"] = "3.0"  # not supported
    wire = {"campaign_id": "deadbeef", **body, "signature": ""}
    path = tmp_path / "campaign_3_0.json"
    path.write_text(json.dumps(wire), encoding="utf-8")

    with pytest.raises(ValueError, match="unsupported CampaignRecord schema_version"):
        load_campaign(path)


# ---------------------------------------------------------------------------
# Behavioural property: 1.0 record's signature survives a roundtrip through
# the 2.0 reader unchanged.
# ---------------------------------------------------------------------------


def test_1_0_body_canonical_form_excludes_new_fields() -> None:
    """The version-aware _body must omit the schema-2.0 additive fields
    when ``schema_version == '1.0'``. Otherwise legacy signatures break."""
    rec = CampaignRecord(
        target_name="kimera",
        target_git_commit="cafebabe",
        schema_version="1.0",
        corrected_verdicts={"x": "VALIDATED"},  # set, but should NOT appear
        multiplicity_correction_method="holm",  # ditto
    )
    body = rec._body()
    assert "corrected_verdicts" not in body
    assert "multiplicity_correction_method" not in body


def test_2_0_body_canonical_form_includes_new_fields() -> None:
    """And 2.0 records DO include them — even when empty."""
    rec = CampaignRecord(
        target_name="kimera",
        target_git_commit="cafebabe",
        schema_version="2.0",
    )
    body = rec._body()
    assert "corrected_verdicts" in body
    assert "multiplicity_correction_method" in body
    assert body["corrected_verdicts"] == {}
    assert body["multiplicity_correction_method"] == "none"
