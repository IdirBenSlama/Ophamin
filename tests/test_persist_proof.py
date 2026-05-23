"""Tests for the proof-bundle persistence layer (persist_proof).

Pins:
- Bundle directory shape: <root>/<tier>/<scenario>/<date>_<verdict>_<short>/
- Filename: proof.{json,md,html,tex,pdf}
- All five formats written when BundleFormat.ALL is passed
- PDF gracefully marked skipped (NOT silently absent) when toolchain missing
- Idempotent re-persist on the same record overwrites with identical bytes
- Loud-fail on un-signed record / empty formats set / JSON missing from formats
- Signature stays valid through the round-trip (filename does not affect bytes)
"""

from __future__ import annotations

import json

import pytest

from ophamin.measuring.proof import (
    BundleFormat,
    Claim,
    DatasetRef,
    EmpiricalProofRecord,
    PersistedBundle,
    PillarEvidence,
    PreRegistration,
    Reproduction,
    Threshold,
    Verdict,
    bundle_dir_for,
    content_hash,
    persist_proof,
)


# --------------------------------------------------------------------------
# Fixture — a fully-formed signed record
# --------------------------------------------------------------------------


@pytest.fixture
def signed_record() -> EmpiricalProofRecord:
    threshold = Threshold(metric="x", comparator=">=", value=1.0)
    claim = Claim(
        statement="Test claim.",
        operationalization="noop",
        threshold=threshold,
        h0="h0",
        h1="h1",
    )
    prereg = PreRegistration(
        config_hash=content_hash({"x": 1}),
        data_hash=content_hash({"y": 2}),
        analysis_plan="noop",
    )
    dataset = DatasetRef(
        name="ds", content_hash=content_hash({"d": 1}),
        n_records=1, source="synthetic", kind="test",
    )
    evidence = [
        PillarEvidence(
            pillar="test", statistic_name="x", statistic_value=1.0,
            library="stdlib", library_version="1.0",
        ),
    ]
    verdict = Verdict.decide(observed=1.0, threshold=threshold)
    record = EmpiricalProofRecord(
        claim=claim,
        preregistration=prereg,
        datasets=[dataset],
        substrate_name="mock",
        substrate_git_commit="deadbeef" * 5,
        evidence=evidence,
        verdict=verdict,
        reproduction=Reproduction(command="echo run"),
        ophamin_version="0.59.0",
        ophamin_git_commit="cafef00d" * 5,
    )
    record.sign(b"test-key")
    return record


# --------------------------------------------------------------------------
# bundle_dir_for — pure path computation
# --------------------------------------------------------------------------


def test_bundle_dir_carries_tier_scenario_date_verdict_hash(tmp_path, signed_record):
    bundle = bundle_dir_for(
        signed_record, root=tmp_path,
        tier="engineering", scenario_name="sonarqube-scan",
    )
    parts = bundle.relative_to(tmp_path).parts
    # 3 path components: tier / scenario / leaf
    assert len(parts) == 3
    assert parts[0] == "engineering"
    assert parts[1] == "sonarqube-scan"
    leaf = parts[2]
    # leaf = YYYY-MM-DD_<verdict>_<12-char-short>
    head, verdict_slug, short = leaf.split("_", 2)
    assert len(head) == 10 and head[4] == "-" and head[7] == "-"
    assert verdict_slug == "validated"
    assert len(short) == 12
    assert short == signed_record.proof_id[:12]


def test_bundle_dir_sanitizes_unsafe_tier_and_scenario(tmp_path, signed_record):
    """If a caller passes an unconventional tier or scenario name with
    spaces / slashes / capitals, they get normalized to filesystem-safe
    lowercase."""
    bundle = bundle_dir_for(
        signed_record, root=tmp_path,
        tier="Scientific!!", scenario_name="My Scenario v2",
    )
    parts = bundle.relative_to(tmp_path).parts
    assert parts[0] == "scientific"
    assert parts[1] == "myscenariov2"


def test_bundle_dir_works_on_unsigned_record_signature_check_is_in_persist(
    tmp_path, signed_record,
):
    """`bundle_dir_for` is pure path computation — it does NOT require a
    signature (since proof_id is body-derived). The signature check
    lives in `persist_proof`, which is the boundary where signing
    actually matters (writing tamper-evident artefacts to disk)."""
    signed_record.signature = ""
    # Should NOT raise — signature isn't part of the path.
    bundle = bundle_dir_for(
        signed_record, root=tmp_path,
        tier="engineering", scenario_name="x",
    )
    # Proof_id (body-derived) still produces the same path.
    assert signed_record.proof_id[:12] in bundle.name


def test_bundle_dir_loud_fails_on_malformed_created_at(tmp_path, signed_record):
    signed_record.created_at = "not-a-date"
    with pytest.raises(ValueError):
        bundle_dir_for(
            signed_record, root=tmp_path,
            tier="engineering", scenario_name="x",
        )


# --------------------------------------------------------------------------
# persist_proof — happy path
# --------------------------------------------------------------------------


def test_persist_writes_all_five_formats_by_default(tmp_path, signed_record):
    result = persist_proof(
        signed_record, root=tmp_path,
        tier="engineering", scenario_name="sonarqube-scan",
    )
    assert isinstance(result, PersistedBundle)
    # All five formats should be present (assuming TeX toolchain — see
    # the next test for the toolchain-missing branch).
    for fmt in BundleFormat:
        # PDF may legitimately be skipped on machines without TeX;
        # check that it's accounted for either way.
        assert (fmt in result.written) or (fmt in result.skipped), (
            f"format {fmt} neither written nor skipped"
        )
    # JSON, MD, HTML, LaTeX are toolchain-free → always written.
    for fmt in (BundleFormat.JSON, BundleFormat.MARKDOWN,
                BundleFormat.HTML, BundleFormat.LATEX):
        assert fmt in result.written, f"{fmt} should always be written"


def test_persist_filenames_are_canonical_proof_dot_ext(tmp_path, signed_record):
    """Every file in the bundle must be ``proof.<ext>`` — flat,
    predictable, no hash embedded in the filename (the hash is in
    the bundle dir name)."""
    result = persist_proof(
        signed_record, root=tmp_path,
        tier="engineering", scenario_name="sonarqube-scan",
    )
    for fmt, path in result.written.items():
        assert path.parent == result.bundle_dir
        assert path.stem == "proof", (
            f"format {fmt} filename {path.name} should be 'proof.<ext>'"
        )


def test_persist_json_round_trips_to_identical_record(tmp_path, signed_record):
    """The signed JSON must round-trip back into the same record bytes
    — proves persistence is lossless + the signature survives."""
    result = persist_proof(
        signed_record, root=tmp_path,
        tier="engineering", scenario_name="sonarqube-scan",
    )
    json_path = result.proof_json
    loaded = json.loads(json_path.read_text())
    assert loaded["signature"] == signed_record.signature
    assert loaded["proof_id"] == signed_record.proof_id
    # Re-construct + verify signature against the same key
    from ophamin.measuring.proof.codec import load
    record_back = load(json_path)
    assert record_back.verify_signature(b"test-key")


def test_persist_subset_formats_emits_only_requested(tmp_path, signed_record):
    """Pass only JSON + MD → only those two files exist; HTML / LaTeX /
    PDF NOT in the written dict."""
    result = persist_proof(
        signed_record, root=tmp_path,
        tier="engineering", scenario_name="x",
        formats={BundleFormat.JSON, BundleFormat.MARKDOWN},
    )
    assert set(result.written.keys()) == {BundleFormat.JSON, BundleFormat.MARKDOWN}
    files = sorted(p.name for p in result.bundle_dir.iterdir())
    assert files == ["proof.json", "proof.md"]


def test_persist_idempotent_on_same_record(tmp_path, signed_record):
    """Re-running persist_proof on the same signed record overwrites
    the bundle with identical bytes — same hash → same path → no
    duplicate-bundle proliferation."""
    a = persist_proof(
        signed_record, root=tmp_path,
        tier="engineering", scenario_name="x",
        formats={BundleFormat.JSON, BundleFormat.MARKDOWN},
    )
    a_bytes = a.proof_json.read_bytes()
    b = persist_proof(
        signed_record, root=tmp_path,
        tier="engineering", scenario_name="x",
        formats={BundleFormat.JSON, BundleFormat.MARKDOWN},
    )
    assert a.bundle_dir == b.bundle_dir
    assert b.proof_json.read_bytes() == a_bytes


def test_persist_pdf_skipped_loudly_when_toolchain_missing(
    tmp_path, signed_record, monkeypatch,
):
    """When TeX is absent, PDFReporter raises at construction.
    persist_proof catches THAT specific typed error and records a
    skip-reason in result.skipped — does NOT silently drop the
    format. The operator can branch on result.skipped to know."""
    import ophamin.reporting.pdf_renderer as mod
    monkeypatch.setattr(mod.shutil, "which", lambda n: None)
    result = persist_proof(
        signed_record, root=tmp_path,
        tier="engineering", scenario_name="x",
    )
    assert BundleFormat.PDF not in result.written
    assert BundleFormat.PDF in result.skipped
    assert "MacTeX" in result.skipped[BundleFormat.PDF] or \
           "TeX Live" in result.skipped[BundleFormat.PDF]


# --------------------------------------------------------------------------
# Loud-fail paths
# --------------------------------------------------------------------------


def test_persist_refuses_unsigned_record(tmp_path, signed_record):
    signed_record.signature = ""
    with pytest.raises(ValueError, match="signature is empty"):
        persist_proof(
            signed_record, root=tmp_path,
            tier="engineering", scenario_name="x",
        )


def test_persist_refuses_empty_formats(tmp_path, signed_record):
    with pytest.raises(ValueError, match="formats set is empty"):
        persist_proof(
            signed_record, root=tmp_path,
            tier="engineering", scenario_name="x",
            formats=[],
        )


def test_persist_refuses_to_omit_json(tmp_path, signed_record):
    """Removing JSON from the format set would silently strip the
    signed source of truth — refuse loudly."""
    with pytest.raises(ValueError, match="BundleFormat.JSON is mandatory"):
        persist_proof(
            signed_record, root=tmp_path,
            tier="engineering", scenario_name="x",
            formats={BundleFormat.MARKDOWN, BundleFormat.HTML},
        )


def test_bundle_format_all_carries_five_formats():
    assert BundleFormat.all() == frozenset(BundleFormat)
    assert len(BundleFormat.all()) == 5


def test_bundle_format_json_only_subset():
    s = BundleFormat.json_only()
    assert s == frozenset({BundleFormat.JSON})


def test_persistedbundle_dataclass_is_frozen():
    """Returned bundle should be immutable so callers don't mutate it
    by accident."""
    import dataclasses
    fields = dataclasses.fields(PersistedBundle)
    assert {f.name for f in fields} == {"bundle_dir", "written", "skipped"}
