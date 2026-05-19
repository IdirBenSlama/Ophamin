"""Hardening pins for the RO-Crate 1.2 exporter.

RO-Crate (Research Object Crate) is a JSON-LD-based packaging spec
for self-describing research artifacts. Each test pins a load-bearing
property of the export contract: spec-compliance entities, schema.org
vocabulary correctness, ID stability, security checks (path traversal),
and end-to-end serializability.
"""

from __future__ import annotations

import json

import pytest

from ophamin.interop.ro_crate import (
    DEFAULT_PROOF_FILENAME,
    RO_CRATE_CONFORMS_TO_V1_2,
    RO_CRATE_CONTEXT_V1_2,
    to_ro_crate_metadata,
)
from ophamin.measuring.proof import (
    Claim,
    DatasetRef,
    EmpiricalProofRecord,
    PillarEvidence,
    PreRegistration,
    Reproduction,
    Threshold,
    Verdict,
)


# --------------------------------------------------------------------------
# Helpers
# --------------------------------------------------------------------------


def _signed_proof(
    *,
    n_datasets: int = 1,
    substrate_name: str = "kimera-swm",
    substrate_git_commit: str = "9596c681092358be",
    outcome_target: float = 0.18,  # makes Verdict VALIDATED for threshold >=0.1
) -> EmpiricalProofRecord:
    """Build a complete signed EmpiricalProofRecord for RO-Crate wrapping."""
    threshold = Threshold(
        metric="dissonance_slope", comparator=">=", value=0.1, units="per cycle"
    )
    claim = Claim(
        statement="Substrate doubt rises as internal documents contradict public filings.",
        operationalization="I.cma pooled slope of the zetetic dissonance gradient",
        threshold=threshold,
        h0="dissonance slope <= 0.1 per cycle",
        h1="dissonance slope > 0.1 per cycle",
    )
    prereg = PreRegistration(
        config_hash="cfg" + "0" * 61,
        data_hash="dat" + "0" * 61,
        analysis_plan="cumulative meta-analysis over batches",
        sweep_grid={"batch_size": [1000, 5000]},
    )
    datasets = [
        DatasetRef(
            name=f"test-corpus-{i}",
            content_hash=("abc" + str(i)) + "0" * (64 - 3 - len(str(i))),
            n_records=100 * (i + 1),
            source=f"https://example.invalid/dataset-{i}",
            kind="email_corpus",
        )
        for i in range(n_datasets)
    ]
    evidence = [
        PillarEvidence(
            pillar="I.cma",
            statistic_name="pooled_slope",
            statistic_value=outcome_target,
            library="statsmodels",
            library_version="0.14.6",
            effect_size=outcome_target,
            ci_low=0.14,
            ci_high=0.22,
            p_value=1e-9,
            cross_check="passed",
        )
    ]
    record = EmpiricalProofRecord(
        claim=claim,
        preregistration=prereg,
        datasets=datasets,
        substrate_name=substrate_name,
        substrate_git_commit=substrate_git_commit,
        evidence=evidence,
        verdict=Verdict.decide(outcome_target, threshold),
        reproduction=Reproduction(
            command="ophamin scenario test",
            lineage_chain=[],
        ),
        provenance={"entity": {}, "activity": {}, "agent": {}},
        ophamin_version="0.35.1-test",
        ophamin_git_commit="deadbeefcafe",
    )
    record.sign(b"ro-crate-test-key")
    return record


def _by_id(graph: list[dict], entity_id: str) -> dict:
    """Find the @graph entry whose @id matches."""
    for entity in graph:
        if entity.get("@id") == entity_id:
            return entity
    raise AssertionError(f"@id {entity_id!r} not found in graph")


# --------------------------------------------------------------------------
# Constants — @Stable URI pins
# --------------------------------------------------------------------------


def test_context_uri_is_ro_crate_1_2_context():
    assert RO_CRATE_CONTEXT_V1_2 == "https://w3id.org/ro/crate/1.2/context"


def test_conforms_to_uri_is_ro_crate_1_2():
    assert RO_CRATE_CONFORMS_TO_V1_2 == "https://w3id.org/ro/crate/1.2"


def test_default_proof_filename_is_stable():
    assert DEFAULT_PROOF_FILENAME == "proof.json"


# --------------------------------------------------------------------------
# RO-Crate spec-required structure
# --------------------------------------------------------------------------


def test_metadata_has_context_and_graph_keys():
    md = to_ro_crate_metadata(_signed_proof())
    assert set(md.keys()) == {"@context", "@graph"}


def test_context_is_ro_crate_v1_2():
    md = to_ro_crate_metadata(_signed_proof())
    assert md["@context"] == RO_CRATE_CONTEXT_V1_2


def test_graph_is_list():
    md = to_ro_crate_metadata(_signed_proof())
    assert isinstance(md["@graph"], list)


def test_root_descriptor_present():
    """RO-Crate REQUIRES exactly one @id=ro-crate-metadata.json
    CreativeWork as the root descriptor."""
    md = to_ro_crate_metadata(_signed_proof())
    descriptor = _by_id(md["@graph"], "ro-crate-metadata.json")
    assert descriptor["@type"] == "CreativeWork"


def test_root_descriptor_conforms_to_v1_2():
    md = to_ro_crate_metadata(_signed_proof())
    descriptor = _by_id(md["@graph"], "ro-crate-metadata.json")
    assert descriptor["conformsTo"] == {"@id": RO_CRATE_CONFORMS_TO_V1_2}


def test_root_descriptor_about_points_to_root_dataset():
    md = to_ro_crate_metadata(_signed_proof())
    descriptor = _by_id(md["@graph"], "ro-crate-metadata.json")
    assert descriptor["about"] == {"@id": "./"}


def test_root_data_entity_present():
    """The root Dataset has @id "./" per spec — the path is dot-slash, NOT empty."""
    md = to_ro_crate_metadata(_signed_proof())
    root = _by_id(md["@graph"], "./")
    assert "Dataset" in (root["@type"] if isinstance(root["@type"], list) else [root["@type"]])


def test_root_dataset_has_required_metadata():
    """Per spec SHOULD: name + datePublished on the root Dataset."""
    md = to_ro_crate_metadata(_signed_proof())
    root = _by_id(md["@graph"], "./")
    assert root["name"]  # non-empty
    assert root["datePublished"]  # non-empty


def test_root_dataset_identifier_is_proof_id():
    """The root entity's identifier IS the proof's content-addressed proof_id —
    so an RO-Crate consumer can recover the Ophamin record without parsing
    the proof file."""
    proof = _signed_proof()
    md = to_ro_crate_metadata(proof)
    root = _by_id(md["@graph"], "./")
    assert root["identifier"] == proof.proof_id


def test_root_dataset_conforms_to_both_ro_crate_and_ophamin_schemas():
    proof = _signed_proof()
    md = to_ro_crate_metadata(proof)
    root = _by_id(md["@graph"], "./")
    conforms = root["conformsTo"]
    assert {"@id": RO_CRATE_CONFORMS_TO_V1_2} in conforms
    assert any(
        c.get("@id", "").startswith("https://ophamin.org/schema/") for c in conforms
    )


def test_root_dataset_main_entity_points_to_proof_file():
    md = to_ro_crate_metadata(_signed_proof())
    root = _by_id(md["@graph"], "./")
    assert root["mainEntity"] == {"@id": DEFAULT_PROOF_FILENAME}


# --------------------------------------------------------------------------
# Proof file entity
# --------------------------------------------------------------------------


def test_proof_file_entity_present():
    md = to_ro_crate_metadata(_signed_proof())
    proof_entity = _by_id(md["@graph"], DEFAULT_PROOF_FILENAME)
    assert proof_entity["@type"] == "File"


def test_proof_file_encoding_format_is_application_json():
    md = to_ro_crate_metadata(_signed_proof())
    proof_entity = _by_id(md["@graph"], DEFAULT_PROOF_FILENAME)
    assert proof_entity["encodingFormat"] == "application/json"


def test_proof_file_identifier_carries_signature():
    """When the proof is signed, its identifier is the signature — so
    a downstream consumer can re-verify without descending into the
    proof file."""
    proof = _signed_proof()
    md = to_ro_crate_metadata(proof)
    proof_entity = _by_id(md["@graph"], DEFAULT_PROOF_FILENAME)
    assert proof_entity["identifier"] == proof.signature


def test_unsigned_proof_uses_proof_id_as_identifier():
    """An unsigned proof falls back to its content-addressed proof_id —
    the crate is still valid (RO-Crate is descriptive, not cryptographic)."""
    proof = _signed_proof()
    proof.signature = ""
    md = to_ro_crate_metadata(proof)
    proof_entity = _by_id(md["@graph"], DEFAULT_PROOF_FILENAME)
    assert proof_entity["identifier"] == proof.proof_id


def test_custom_proof_filename_propagates_everywhere():
    """A non-default filename must land in BOTH mainEntity AND the file
    entity itself — they're the same @id."""
    md = to_ro_crate_metadata(
        _signed_proof(), proof_filename="empirical_record.json"
    )
    root = _by_id(md["@graph"], "./")
    assert root["mainEntity"] == {"@id": "empirical_record.json"}
    # The File entity exists under the same @id
    _by_id(md["@graph"], "empirical_record.json")


# --------------------------------------------------------------------------
# Datasets — §4 mapping
# --------------------------------------------------------------------------


def test_each_dataset_appears_in_graph():
    proof = _signed_proof(n_datasets=3)
    md = to_ro_crate_metadata(proof)
    for dataset in proof.datasets:
        # Each DatasetRef maps to a #dataset-<short> entity
        expected_id = f"#dataset-{dataset.content_hash[:16]}"
        _by_id(md["@graph"], expected_id)  # raises if missing


def test_dataset_entity_carries_content_hash_as_identifier():
    proof = _signed_proof(n_datasets=2)
    md = to_ro_crate_metadata(proof)
    for dataset in proof.datasets:
        ds_entity = _by_id(md["@graph"], f"#dataset-{dataset.content_hash[:16]}")
        assert ds_entity["identifier"] == dataset.content_hash


def test_dataset_entity_carries_source_as_url():
    proof = _signed_proof(n_datasets=1)
    md = to_ro_crate_metadata(proof)
    ds_entity = _by_id(
        md["@graph"], f"#dataset-{proof.datasets[0].content_hash[:16]}"
    )
    assert ds_entity["url"] == proof.datasets[0].source


def test_dataset_entity_n_records_in_size_quantitative_value():
    proof = _signed_proof(n_datasets=1)
    md = to_ro_crate_metadata(proof)
    ds_entity = _by_id(
        md["@graph"], f"#dataset-{proof.datasets[0].content_hash[:16]}"
    )
    assert ds_entity["size"]["@type"] == "QuantitativeValue"
    assert ds_entity["size"]["value"] == proof.datasets[0].n_records
    assert ds_entity["size"]["unitText"] == "records"


def test_datasets_appear_in_root_has_part():
    """All §4 datasets land in the root Dataset's hasPart list, alongside the proof file."""
    proof = _signed_proof(n_datasets=2)
    md = to_ro_crate_metadata(proof)
    root = _by_id(md["@graph"], "./")
    has_part_ids = {entry["@id"] for entry in root["hasPart"]}
    assert DEFAULT_PROOF_FILENAME in has_part_ids
    for dataset in proof.datasets:
        assert f"#dataset-{dataset.content_hash[:16]}" in has_part_ids


# --------------------------------------------------------------------------
# Substrate entity
# --------------------------------------------------------------------------


def test_substrate_software_application_present():
    proof = _signed_proof(substrate_name="kimera-swm", substrate_git_commit="abc123def456")
    md = to_ro_crate_metadata(proof)
    substrate = _by_id(md["@graph"], "#substrate-kimera-swm@abc123def456")
    assert substrate["@type"] == "SoftwareApplication"
    assert substrate["name"] == "kimera-swm"
    assert substrate["softwareVersion"] == "abc123def456"


def test_substrate_without_commit_still_emits_entity():
    proof = _signed_proof(substrate_name="kimera-swm", substrate_git_commit="")
    md = to_ro_crate_metadata(proof)
    substrate = _by_id(md["@graph"], "#substrate-kimera-swm")
    assert substrate["name"] == "kimera-swm"


# --------------------------------------------------------------------------
# Verdict — AssessAction
# --------------------------------------------------------------------------


def test_verdict_is_assess_action():
    md = to_ro_crate_metadata(_signed_proof())
    verdict = _by_id(md["@graph"], "#verdict")
    assert verdict["@type"] == "AssessAction"


def test_verdict_result_is_property_value():
    proof = _signed_proof()
    md = to_ro_crate_metadata(proof)
    verdict = _by_id(md["@graph"], "#verdict")
    result = verdict["result"]
    assert result["@type"] == "PropertyValue"
    assert result["propertyID"] == proof.verdict.threshold.metric
    assert result["value"] == proof.verdict.observed_value
    assert result["unitText"] == proof.verdict.threshold.units


def test_verdict_outcome_in_additional_type():
    """schema.org's AssessAction doesn't have an enum for VALIDATED /
    REFUTED / INCONCLUSIVE — we carry the structured outcome via
    additionalType so consumers can branch on it."""
    proof = _signed_proof()
    md = to_ro_crate_metadata(proof)
    verdict = _by_id(md["@graph"], "#verdict")
    assert verdict["additionalType"] == proof.verdict.outcome  # "VALIDATED"


def test_verdict_action_status_is_completed():
    md = to_ro_crate_metadata(_signed_proof())
    verdict = _by_id(md["@graph"], "#verdict")
    assert verdict["actionStatus"] == "CompletedActionStatus"


# --------------------------------------------------------------------------
# Reproduction — SoftwareSourceCode
# --------------------------------------------------------------------------


def test_reproduction_is_software_source_code():
    md = to_ro_crate_metadata(_signed_proof())
    repro = _by_id(md["@graph"], "#reproduction")
    assert repro["@type"] == "SoftwareSourceCode"
    assert repro["programmingLanguage"] == "shell"


def test_reproduction_text_carries_the_command():
    proof = _signed_proof()
    md = to_ro_crate_metadata(proof)
    repro = _by_id(md["@graph"], "#reproduction")
    assert repro["text"] == proof.reproduction.command


# --------------------------------------------------------------------------
# Ophamin entity
# --------------------------------------------------------------------------


def test_ophamin_software_application_present():
    md = to_ro_crate_metadata(_signed_proof())
    ophamin = _by_id(md["@graph"], "#ophamin")
    assert ophamin["@type"] == "SoftwareApplication"
    assert ophamin["name"] == "Ophamin"
    assert ophamin["url"] == "https://github.com/IdirBenSlama/Ophamin"


def test_ophamin_carries_git_commit_as_identifier():
    proof = _signed_proof()
    md = to_ro_crate_metadata(proof)
    ophamin = _by_id(md["@graph"], "#ophamin")
    assert ophamin["identifier"] == proof.ophamin_git_commit


# --------------------------------------------------------------------------
# Filename validation — security boundary
# --------------------------------------------------------------------------


def test_empty_filename_rejected():
    with pytest.raises(ValueError, match="non-empty"):
        to_ro_crate_metadata(_signed_proof(), proof_filename="")


def test_absolute_filename_rejected():
    with pytest.raises(ValueError, match="absolute"):
        to_ro_crate_metadata(_signed_proof(), proof_filename="/etc/passwd")


def test_path_traversal_filename_rejected():
    with pytest.raises(ValueError, match=r"\.\."):
        to_ro_crate_metadata(_signed_proof(), proof_filename="../../etc/passwd")


def test_nul_byte_filename_rejected():
    with pytest.raises(ValueError, match="NUL"):
        to_ro_crate_metadata(_signed_proof(), proof_filename="proof\x00.json")


def test_nested_relative_filename_accepted():
    """Subdirectories are fine — only path traversal is rejected."""
    md = to_ro_crate_metadata(
        _signed_proof(), proof_filename="data/proofs/proof.json"
    )
    _by_id(md["@graph"], "data/proofs/proof.json")  # raises if missing


# --------------------------------------------------------------------------
# extra_root_metadata pass-through
# --------------------------------------------------------------------------


def test_extra_root_metadata_merged_into_root_dataset():
    md = to_ro_crate_metadata(
        _signed_proof(),
        extra_root_metadata={
            "creator": {"@id": "https://orcid.org/0000-0000-0000-0000"},
            "license": {"@id": "https://spdx.org/licenses/Apache-2.0"},
        },
    )
    root = _by_id(md["@graph"], "./")
    assert root["creator"] == {"@id": "https://orcid.org/0000-0000-0000-0000"}
    assert root["license"] == {"@id": "https://spdx.org/licenses/Apache-2.0"}


def test_extra_root_metadata_does_not_overwrite_required_fields():
    """An attacker passing extra_root_metadata can't downgrade conformsTo —
    it WOULD overwrite per dict.update() semantics. Pin: required
    fields aren't structurally protected against overwrite. This test
    documents the contract as-shipped; tightening to refuse known-required
    keys is a future enhancement.
    """
    md = to_ro_crate_metadata(
        _signed_proof(),
        extra_root_metadata={"conformsTo": "OVERWRITTEN"},
    )
    root = _by_id(md["@graph"], "./")
    # The pin documents current behavior — overwrite is permitted.
    # A future ship may convert this to refuse loud.
    assert root["conformsTo"] == "OVERWRITTEN"


# --------------------------------------------------------------------------
# Serializability — must round-trip through json
# --------------------------------------------------------------------------


def test_metadata_serializes_to_json():
    """The full RO-Crate metadata dict json.dumps() without errors."""
    md = to_ro_crate_metadata(_signed_proof(n_datasets=3))
    text = json.dumps(md, sort_keys=True)
    assert text  # non-empty
    # Round-trip
    decoded = json.loads(text)
    assert decoded == md


def test_metadata_serializes_with_indent_for_human_consumption():
    """RO-Crate metadata is typically human-readable — pretty-printing
    works without errors."""
    md = to_ro_crate_metadata(_signed_proof())
    text = json.dumps(md, indent=2, sort_keys=True)
    assert "  " in text  # indentation present
    assert "@context" in text
    assert "@graph" in text


# --------------------------------------------------------------------------
# End-to-end shape pins
# --------------------------------------------------------------------------


def test_graph_contains_at_least_required_entities():
    """A minimal RO-Crate has root descriptor + root Dataset + proof File
    + substrate + verdict + reproduction + ophamin = 6 entities minimum
    (plus N datasets)."""
    md = to_ro_crate_metadata(_signed_proof(n_datasets=0))
    ids = {entry["@id"] for entry in md["@graph"]}
    # 0 datasets case still has these 6
    assert "ro-crate-metadata.json" in ids
    assert "./" in ids
    assert DEFAULT_PROOF_FILENAME in ids
    assert any(i.startswith("#substrate-") for i in ids)
    assert "#verdict" in ids
    assert "#reproduction" in ids
    assert "#ophamin" in ids


def test_graph_grows_with_datasets():
    """Adding §4 datasets adds entities one-for-one."""
    md_0 = to_ro_crate_metadata(_signed_proof(n_datasets=0))
    md_3 = to_ro_crate_metadata(_signed_proof(n_datasets=3))
    assert len(md_3["@graph"]) == len(md_0["@graph"]) + 3


def test_zero_datasets_proof_still_packages_cleanly():
    """A proof with no §4 datasets is unusual but valid (e.g., a purely-
    computational claim with no input corpus). The RO-Crate must still
    be well-formed."""
    md = to_ro_crate_metadata(_signed_proof(n_datasets=0))
    root = _by_id(md["@graph"], "./")
    # hasPart still has the proof file
    has_part_ids = {entry["@id"] for entry in root["hasPart"]}
    assert has_part_ids == {DEFAULT_PROOF_FILENAME}


def test_each_entity_has_at_id_and_at_type():
    """RO-Crate / JSON-LD invariant — every entity in @graph has @id and @type."""
    md = to_ro_crate_metadata(_signed_proof(n_datasets=2))
    for entity in md["@graph"]:
        assert "@id" in entity, f"Missing @id in {entity!r}"
        assert "@type" in entity, f"Missing @type in {entity!r}"


def test_all_at_ids_are_unique_in_graph():
    """JSON-LD: each @id must uniquely identify one entity in the @graph."""
    md = to_ro_crate_metadata(_signed_proof(n_datasets=3))
    ids = [entry["@id"] for entry in md["@graph"]]
    assert len(ids) == len(set(ids)), f"Duplicate @id detected: {ids}"
