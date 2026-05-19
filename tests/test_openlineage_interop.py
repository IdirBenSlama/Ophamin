"""Hardening pins for the OpenLineage 2.0 RunEvent emitter.

OpenLineage is a CNCF-incubating spec for data-pipeline lineage events.
Each test pins a load-bearing property of the emitter contract:
RunEvent spec-compliance, eventType mapping (the REFUTED-vs-FAIL
distinction matters), deterministic UUIDv5 runId derivation,
producer URL format, and facet structure.
"""

from __future__ import annotations

import json
import uuid

import pytest

from ophamin.interop.openlineage import (
    DEFAULT_NAMESPACE,
    OPENLINEAGE_PRODUCER_URL_BASE,
    OPENLINEAGE_SCHEMA_URL,
    OPHAMIN_RUNID_NAMESPACE,
    new_run_id,
    to_openlineage_complete_event,
    to_openlineage_event,
    to_openlineage_fail_event,
    to_openlineage_running_event,
    to_openlineage_start_event,
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
    outcome_target: float = 0.18,  # VALIDATED at threshold >=0.1
    threshold_value: float = 0.1,
    threshold_comparator: str = ">=",
    pillar: str = "I.cma",
    statement: str = "Substrate doubt rises as docs contradict filings.",
) -> EmpiricalProofRecord:
    threshold = Threshold(
        metric="dissonance_slope",
        comparator=threshold_comparator,
        value=threshold_value,
        units="per cycle",
    )
    claim = Claim(
        statement=statement,
        operationalization="I.cma pooled slope of the zetetic dissonance gradient",
        threshold=threshold,
        h0="dissonance slope <= 0.1 per cycle",
        h1="dissonance slope > 0.1 per cycle",
    )
    prereg = PreRegistration(
        config_hash="cfg" + "0" * 61,
        data_hash="dat" + "0" * 61,
        analysis_plan="cumulative meta-analysis over chronological batches",
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
            pillar=pillar,
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
        substrate_name="kimera-swm",
        substrate_git_commit="9596c681092358be",
        evidence=evidence,
        verdict=Verdict.decide(outcome_target, threshold),
        reproduction=Reproduction(command="ophamin scenario test"),
        provenance={"entity": {}, "activity": {}, "agent": {}},
        ophamin_version="0.37.0-test",
        ophamin_git_commit="deadbeefcafe",
    )
    record.sign(b"openlineage-test-key")
    return record


# --------------------------------------------------------------------------
# Constants — @Stable URI pins
# --------------------------------------------------------------------------


def test_schema_url_is_openlineage_2_0_2():
    assert OPENLINEAGE_SCHEMA_URL == (
        "https://openlineage.io/spec/2-0-2/OpenLineage.json#/$defs/RunEvent"
    )


def test_producer_url_base_is_ophamin_repo():
    assert OPENLINEAGE_PRODUCER_URL_BASE == "https://github.com/IdirBenSlama/Ophamin"


def test_default_namespace_is_ophamin():
    assert DEFAULT_NAMESPACE == "ophamin"


def test_runid_namespace_is_pinned_uuid():
    """The UUIDv5 namespace MUST NOT drift — that would break the
    deterministic proof_id → runId mapping for existing downstream
    consumers."""
    assert str(OPHAMIN_RUNID_NAMESPACE) == "ec1e6b1c-0000-4000-8000-000000000001"


# --------------------------------------------------------------------------
# OpenLineage RunEvent spec-required top-level shape
# --------------------------------------------------------------------------


def test_event_has_all_required_top_level_keys():
    event = to_openlineage_event(_signed_proof())
    required = {
        "eventType",
        "eventTime",
        "run",
        "job",
        "inputs",
        "outputs",
        "producer",
        "schemaURL",
    }
    assert required.issubset(event.keys())


def test_schema_url_points_to_2_0_2():
    event = to_openlineage_event(_signed_proof())
    assert event["schemaURL"] == OPENLINEAGE_SCHEMA_URL


def test_producer_includes_version():
    """Producer URL convention: <repo>@<version> so consumers can
    disambiguate event-shape drift across Ophamin releases."""
    event = to_openlineage_event(_signed_proof())
    assert event["producer"].startswith(OPENLINEAGE_PRODUCER_URL_BASE)
    assert "@" in event["producer"]  # version suffix present


def test_event_time_matches_proof_created_at():
    proof = _signed_proof()
    event = to_openlineage_event(proof)
    assert event["eventTime"] == proof.created_at


# --------------------------------------------------------------------------
# eventType — the load-bearing REFUTED-vs-FAIL distinction
# --------------------------------------------------------------------------


def test_validated_outcome_maps_to_complete():
    proof = _signed_proof(outcome_target=0.18)  # > threshold 0.1
    event = to_openlineage_event(proof)
    assert proof.verdict.outcome == "VALIDATED"
    assert event["eventType"] == "COMPLETE"


def test_refuted_outcome_maps_to_complete_not_fail():
    """REFUTED is a VALID empirical result — must NOT map to FAIL
    or downstream platform alerts trip on every refuted claim."""
    proof = _signed_proof(outcome_target=0.05)  # < threshold 0.1
    event = to_openlineage_event(proof)
    assert proof.verdict.outcome == "REFUTED"
    assert event["eventType"] == "COMPLETE"


def test_inconclusive_outcome_maps_to_fail():
    """INCONCLUSIVE means the run didn't produce a deciding observation —
    that's a real job failure from the pipeline's perspective."""
    threshold = Threshold("slope", ">=", 0.1)
    proof = _signed_proof()
    # Construct an INCONCLUSIVE verdict manually
    proof.verdict = Verdict.decide(0.18, threshold, inconclusive=True)
    proof.sign(b"openlineage-test-key")
    event = to_openlineage_event(proof)
    assert proof.verdict.outcome == "INCONCLUSIVE"
    assert event["eventType"] == "FAIL"


# --------------------------------------------------------------------------
# runId — UUIDv5 derivation MUST be deterministic
# --------------------------------------------------------------------------


def test_runid_is_valid_uuid():
    event = to_openlineage_event(_signed_proof())
    # Should parse as a UUID
    parsed = uuid.UUID(event["run"]["runId"])
    assert isinstance(parsed, uuid.UUID)


def test_runid_is_deterministic_for_same_proof():
    """The same proof_id MUST produce the same runId every time —
    consumers (Marquez) dedupe on runId."""
    proof = _signed_proof()
    event_1 = to_openlineage_event(proof)
    event_2 = to_openlineage_event(proof)
    assert event_1["run"]["runId"] == event_2["run"]["runId"]


def test_different_proofs_produce_different_runids():
    proof_a = _signed_proof(statement="Claim A")
    proof_b = _signed_proof(statement="Claim B")
    assert proof_a.proof_id != proof_b.proof_id
    event_a = to_openlineage_event(proof_a)
    event_b = to_openlineage_event(proof_b)
    assert event_a["run"]["runId"] != event_b["run"]["runId"]


def test_runid_is_uuidv5_derived_from_namespace():
    """The runId must be derivable as uuid5(OPHAMIN_RUNID_NAMESPACE, proof_id) —
    so a consumer with the proof_id can independently compute the expected
    runId for offline verification."""
    proof = _signed_proof()
    expected = str(uuid.uuid5(OPHAMIN_RUNID_NAMESPACE, proof.proof_id))
    event = to_openlineage_event(proof)
    assert event["run"]["runId"] == expected


# --------------------------------------------------------------------------
# Job — namespace + name
# --------------------------------------------------------------------------


def test_default_namespace_lands_in_event():
    event = to_openlineage_event(_signed_proof())
    assert event["job"]["namespace"] == DEFAULT_NAMESPACE


def test_custom_namespace_propagates():
    event = to_openlineage_event(_signed_proof(), namespace="prod.kimera")
    assert event["job"]["namespace"] == "prod.kimera"


def test_empty_namespace_rejected():
    with pytest.raises(ValueError, match="namespace must be non-empty"):
        to_openlineage_event(_signed_proof(), namespace="")


def test_default_job_name_derived_from_first_pillar():
    proof = _signed_proof(pillar="O.x.rate")
    event = to_openlineage_event(proof)
    assert event["job"]["name"] == "O.x.rate"


def test_custom_job_name_overrides_pillar():
    event = to_openlineage_event(
        _signed_proof(pillar="O.x.rate"), job_name="my_custom_job"
    )
    assert event["job"]["name"] == "my_custom_job"


def test_job_documentation_facet_carries_analysis_plan():
    proof = _signed_proof()
    event = to_openlineage_event(proof)
    doc_facet = event["job"]["facets"]["documentation"]
    assert doc_facet["description"] == proof.preregistration.analysis_plan
    assert doc_facet["_producer"]
    assert doc_facet["_schemaURL"]


# --------------------------------------------------------------------------
# Inputs — §4 DatasetRefs map 1:1
# --------------------------------------------------------------------------


def test_inputs_length_matches_dataset_count():
    proof = _signed_proof(n_datasets=3)
    event = to_openlineage_event(proof)
    assert len(event["inputs"]) == 3


def test_zero_datasets_produces_empty_inputs():
    proof = _signed_proof(n_datasets=0)
    event = to_openlineage_event(proof)
    assert event["inputs"] == []


def test_input_dataset_carries_name_and_namespace():
    proof = _signed_proof(n_datasets=1)
    event = to_openlineage_event(proof)
    inp = event["inputs"][0]
    assert inp["namespace"] == "ophamin.datasets"
    assert inp["name"] == proof.datasets[0].name


def test_input_dataset_carries_content_hash_in_ophamin_facet():
    proof = _signed_proof(n_datasets=1)
    event = to_openlineage_event(proof)
    facet = event["inputs"][0]["facets"]["ophamin_dataset"]
    assert facet["content_hash"] == proof.datasets[0].content_hash
    assert facet["n_records"] == proof.datasets[0].n_records


def test_input_dataset_has_datasource_facet_with_uri():
    proof = _signed_proof(n_datasets=1)
    event = to_openlineage_event(proof)
    ds_facet = event["inputs"][0]["facets"]["dataSource"]
    assert ds_facet["uri"] == proof.datasets[0].source


# --------------------------------------------------------------------------
# Outputs — the signed proof is the one output
# --------------------------------------------------------------------------


def test_one_output_per_proof():
    """Each scenario run produces exactly one signed proof as its lineage output."""
    event = to_openlineage_event(_signed_proof())
    assert len(event["outputs"]) == 1


def test_output_name_is_proof_id():
    proof = _signed_proof()
    event = to_openlineage_event(proof)
    assert event["outputs"][0]["name"] == proof.proof_id


def test_output_namespace_is_ophamin_proofs():
    event = to_openlineage_event(_signed_proof())
    assert event["outputs"][0]["namespace"] == "ophamin.proofs"


def test_output_has_schema_facet_describing_proof_shape():
    """The output dataset declares its column schema — Marquez UIs
    render this as "this is what came out of the job"."""
    event = to_openlineage_event(_signed_proof())
    schema = event["outputs"][0]["facets"]["schema"]
    field_names = {f["name"] for f in schema["fields"]}
    assert "proof_id" in field_names
    assert "verdict.outcome" in field_names
    assert "signature" in field_names


# --------------------------------------------------------------------------
# Run.facets — the Ophamin payload
# --------------------------------------------------------------------------


def test_ophamin_claim_facet_present():
    proof = _signed_proof()
    event = to_openlineage_event(proof)
    facet = event["run"]["facets"]["ophamin_claim"]
    assert facet["statement"] == proof.claim.statement
    assert facet["h0"] == proof.claim.h0
    assert facet["h1"] == proof.claim.h1


def test_ophamin_claim_facet_carries_threshold():
    proof = _signed_proof()
    event = to_openlineage_event(proof)
    threshold = event["run"]["facets"]["ophamin_claim"]["threshold"]
    assert threshold["metric"] == proof.claim.threshold.metric
    assert threshold["comparator"] == proof.claim.threshold.comparator
    assert threshold["value"] == proof.claim.threshold.value
    assert threshold["units"] == proof.claim.threshold.units


def test_ophamin_verdict_facet_carries_outcome_and_observed():
    proof = _signed_proof()
    event = to_openlineage_event(proof)
    facet = event["run"]["facets"]["ophamin_verdict"]
    assert facet["outcome"] == proof.verdict.outcome
    assert facet["observed_value"] == proof.verdict.observed_value


def test_signed_proof_carries_signature_in_verdict_facet():
    """When the proof is signed, the verdict facet preserves the
    HMAC — downstream consumers can re-verify against the proof
    body for cross-attribution."""
    proof = _signed_proof()
    event = to_openlineage_event(proof)
    facet = event["run"]["facets"]["ophamin_verdict"]
    assert facet["ophamin_signature"] == proof.signature
    assert facet["ophamin_signature_algorithm"] == "HMAC-SHA256"


def test_unsigned_proof_omits_signature_from_verdict_facet():
    """An unsigned proof emits a syntactically-valid event but without
    the signature attribution — descriptive lineage works without
    cryptographic proof."""
    proof = _signed_proof()
    proof.signature = ""
    event = to_openlineage_event(proof)
    facet = event["run"]["facets"]["ophamin_verdict"]
    assert "ophamin_signature" not in facet


# --------------------------------------------------------------------------
# Extra facets
# --------------------------------------------------------------------------


def test_extra_facets_merge_into_run_facets():
    event = to_openlineage_event(
        _signed_proof(),
        extra_facets={
            "custom_facet": {
                "_producer": "https://example.org/producer",
                "_schemaURL": "https://example.org/schema.json",
                "field": "value",
            }
        },
    )
    assert event["run"]["facets"]["custom_facet"]["field"] == "value"


def test_extra_facets_dont_overwrite_ophamin_facets():
    """ophamin_claim + ophamin_verdict are load-bearing — even if a
    consumer passes the same key in extra_facets, they should be
    additive (last-wins on collisions is current contract; tighten
    later)."""
    event = to_openlineage_event(
        _signed_proof(),
        extra_facets={"my_facet": {"_producer": "p", "_schemaURL": "s"}},
    )
    assert "ophamin_claim" in event["run"]["facets"]
    assert "ophamin_verdict" in event["run"]["facets"]
    assert "my_facet" in event["run"]["facets"]


# --------------------------------------------------------------------------
# Facet schema invariants (each Ophamin custom facet has _producer + _schemaURL)
# --------------------------------------------------------------------------


def test_every_ophamin_facet_has_producer_and_schema_url():
    """OpenLineage requires every facet to carry _producer + _schemaURL."""
    event = to_openlineage_event(_signed_proof(n_datasets=2))
    for facet in event["run"]["facets"].values():
        assert "_producer" in facet
        assert "_schemaURL" in facet
    for inp in event["inputs"]:
        for facet in inp["facets"].values():
            assert "_producer" in facet
            assert "_schemaURL" in facet
    for out in event["outputs"]:
        for facet in out["facets"].values():
            assert "_producer" in facet
            assert "_schemaURL" in facet
    for facet in event["job"]["facets"].values():
        assert "_producer" in facet
        assert "_schemaURL" in facet


# --------------------------------------------------------------------------
# Serializability — must round-trip through json (no custom types)
# --------------------------------------------------------------------------


def test_event_serializes_to_json_cleanly():
    event = to_openlineage_event(_signed_proof(n_datasets=3))
    text = json.dumps(event, sort_keys=True)
    decoded = json.loads(text)
    assert decoded == event


def test_event_with_extra_facets_serializes():
    event = to_openlineage_event(
        _signed_proof(),
        extra_facets={"custom": {"_producer": "p", "_schemaURL": "s", "x": [1, 2]}},
    )
    json.dumps(event)  # should not raise


# --------------------------------------------------------------------------
# Edge cases — zero-evidence, no-prereg-plan
# --------------------------------------------------------------------------


def test_no_evidence_falls_back_to_empirical_claim_name():
    """A proof with no §5 evidence is unusual but technically valid;
    job name falls back to a stable default."""
    proof = _signed_proof()
    proof.evidence = []  # forcibly drop evidence
    event = to_openlineage_event(proof)
    assert event["job"]["name"] == "empirical-claim"


def test_empty_analysis_plan_omits_documentation_facet():
    """If preregistration.analysis_plan is empty, the documentation
    facet is omitted — facets must carry real content, not empty
    descriptions."""
    proof = _signed_proof()
    proof.preregistration.analysis_plan = ""
    event = to_openlineage_event(proof)
    assert "documentation" not in event["job"]["facets"]


# --------------------------------------------------------------------------
# Event-sequencing — START + RUNNING + COMPLETE / FAIL
# --------------------------------------------------------------------------


def test_new_run_id_returns_uuid():
    """The runId minter returns a valid uuid.UUID."""
    import uuid as uuid_lib
    run_id = new_run_id()
    assert isinstance(run_id, uuid_lib.UUID)


def test_new_run_ids_are_unique():
    """Each invocation mints a distinct runId — load-bearing for
    distinguishing parallel campaigns."""
    ids = {new_run_id() for _ in range(10)}
    assert len(ids) == 10


# --- START events --------------------------------------------------------


def test_start_event_has_event_type_start():
    rid = new_run_id()
    event = to_openlineage_start_event(
        run_id=rid, scenario_name="my_scenario"
    )
    assert event["eventType"] == "START"


def test_start_event_preserves_run_id():
    rid = new_run_id()
    event = to_openlineage_start_event(
        run_id=rid, scenario_name="my_scenario"
    )
    assert event["run"]["runId"] == str(rid)


def test_start_event_accepts_string_run_id():
    """run_id can be passed as a UUID string (e.g. from CLI)."""
    rid_str = str(new_run_id())
    event = to_openlineage_start_event(
        run_id=rid_str, scenario_name="my_scenario"
    )
    assert event["run"]["runId"] == rid_str


def test_start_event_refuses_invalid_run_id_string():
    """A string that doesn't parse as UUID raises loud."""
    with pytest.raises(ValueError, match="valid UUID"):
        to_openlineage_start_event(
            run_id="not-a-uuid",
            scenario_name="my_scenario",
        )


def test_start_event_refuses_empty_namespace():
    rid = new_run_id()
    with pytest.raises(ValueError, match="namespace must be non-empty"):
        to_openlineage_start_event(
            run_id=rid, scenario_name="x", namespace=""
        )


def test_start_event_refuses_empty_scenario_name():
    rid = new_run_id()
    with pytest.raises(ValueError, match="scenario_name must be non-empty"):
        to_openlineage_start_event(run_id=rid, scenario_name="")


def test_start_event_uses_scenario_name_as_job_name():
    rid = new_run_id()
    event = to_openlineage_start_event(
        run_id=rid, scenario_name="immune_siege"
    )
    assert event["job"]["name"] == "immune_siege"


def test_start_event_outputs_empty_no_proof_yet():
    """At START time no proof exists yet, so outputs is []."""
    rid = new_run_id()
    event = to_openlineage_start_event(
        run_id=rid, scenario_name="my_scenario"
    )
    assert event["outputs"] == []


def test_start_event_with_claim_attaches_claim_facet():
    """When a pre-registered claim is provided, consumers see what
    the run is testing BEFORE any results exist."""
    rid = new_run_id()
    proof = _signed_proof()  # use its claim
    event = to_openlineage_start_event(
        run_id=rid, scenario_name="my_scenario", claim=proof.claim
    )
    facet = event["run"]["facets"]["ophamin_claim"]
    assert facet["statement"] == proof.claim.statement


def test_start_event_without_claim_omits_claim_facet():
    rid = new_run_id()
    event = to_openlineage_start_event(
        run_id=rid, scenario_name="my_scenario", claim=None
    )
    assert "ophamin_claim" not in event["run"]["facets"]


def test_start_event_with_datasets_attaches_inputs():
    rid = new_run_id()
    proof = _signed_proof(n_datasets=2)
    event = to_openlineage_start_event(
        run_id=rid,
        scenario_name="my_scenario",
        datasets=proof.datasets,
    )
    assert len(event["inputs"]) == 2
    # First input carries the correct content_hash
    facet = event["inputs"][0]["facets"]["ophamin_dataset"]
    assert facet["content_hash"] == proof.datasets[0].content_hash


def test_start_event_inputs_default_to_empty():
    rid = new_run_id()
    event = to_openlineage_start_event(
        run_id=rid, scenario_name="my_scenario"
    )
    assert event["inputs"] == []


def test_start_event_attaches_analysis_plan_documentation_facet():
    rid = new_run_id()
    event = to_openlineage_start_event(
        run_id=rid,
        scenario_name="my_scenario",
        analysis_plan="cumulative meta-analysis over 1000 cycles",
    )
    doc = event["job"]["facets"]["documentation"]
    assert doc["description"] == "cumulative meta-analysis over 1000 cycles"


def test_start_event_omits_documentation_when_plan_is_empty():
    rid = new_run_id()
    event = to_openlineage_start_event(
        run_id=rid, scenario_name="my_scenario", analysis_plan=""
    )
    assert "documentation" not in event["job"]["facets"]


def test_start_event_default_event_time_is_rfc3339_utc():
    rid = new_run_id()
    event = to_openlineage_start_event(
        run_id=rid, scenario_name="my_scenario"
    )
    # RFC 3339 UTC ends in 'Z'
    assert event["eventTime"].endswith("Z")
    # And matches the YYYY-MM-DDTHH:MM:SSZ shape
    import re
    assert re.match(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$", event["eventTime"])


def test_start_event_custom_event_time_passes_through():
    rid = new_run_id()
    event = to_openlineage_start_event(
        run_id=rid,
        scenario_name="my_scenario",
        event_time="2026-05-19T12:34:56Z",
    )
    assert event["eventTime"] == "2026-05-19T12:34:56Z"


# --- RUNNING events ------------------------------------------------------


def test_running_event_has_event_type_running():
    rid = new_run_id()
    event = to_openlineage_running_event(
        run_id=rid, scenario_name="my_scenario"
    )
    assert event["eventType"] == "RUNNING"


def test_running_event_preserves_run_id():
    rid = new_run_id()
    event = to_openlineage_running_event(
        run_id=rid, scenario_name="my_scenario"
    )
    assert event["run"]["runId"] == str(rid)


def test_running_event_inputs_and_outputs_are_empty():
    """RUNNING events are heartbeats; the canonical inputs/outputs
    are emitted on the START + terminal events."""
    rid = new_run_id()
    event = to_openlineage_running_event(
        run_id=rid, scenario_name="my_scenario"
    )
    assert event["inputs"] == []
    assert event["outputs"] == []


def test_running_event_with_progress_attaches_facet():
    rid = new_run_id()
    event = to_openlineage_running_event(
        run_id=rid,
        scenario_name="my_scenario",
        progress={
            "percent_complete": 0.42,
            "cycles_completed": 4200,
            "cycles_total": 10000,
            "message": "Batch 42/100",
        },
    )
    facet = event["run"]["facets"]["ophamin_progress"]
    assert facet["percent_complete"] == 0.42
    assert facet["cycles_completed"] == 4200
    assert facet["message"] == "Batch 42/100"
    # Always carries the producer + schema URL
    assert facet["_producer"]
    assert facet["_schemaURL"]


def test_running_event_without_progress_omits_facet():
    rid = new_run_id()
    event = to_openlineage_running_event(
        run_id=rid, scenario_name="my_scenario"
    )
    assert "ophamin_progress" not in event["run"]["facets"]


# --- COMPLETE events (caller-managed run_id) ----------------------------


def test_complete_event_uses_caller_run_id_not_proof_derived():
    """The streaming-COMPLETE function MUST use the caller's run_id,
    not the deterministic proof-derived one. This is the load-bearing
    distinction from the single-event to_openlineage_event path."""
    rid = new_run_id()
    proof = _signed_proof()
    event = to_openlineage_complete_event(
        run_id=rid, proof=proof
    )
    assert event["run"]["runId"] == str(rid)
    # And NOT the proof-derived one
    import uuid as uuid_lib
    proof_derived = str(uuid_lib.uuid5(OPHAMIN_RUNID_NAMESPACE, proof.proof_id))
    assert event["run"]["runId"] != proof_derived


def test_complete_event_carries_full_proof_payload():
    """COMPLETE events still embed claim + verdict facets + inputs +
    outputs from the proof — same shape as to_openlineage_event."""
    rid = new_run_id()
    proof = _signed_proof(n_datasets=2)
    event = to_openlineage_complete_event(run_id=rid, proof=proof)
    assert "ophamin_claim" in event["run"]["facets"]
    assert "ophamin_verdict" in event["run"]["facets"]
    assert len(event["inputs"]) == 2
    assert len(event["outputs"]) == 1
    assert event["outputs"][0]["name"] == proof.proof_id


def test_complete_event_validated_maps_to_complete():
    rid = new_run_id()
    proof = _signed_proof(outcome_target=0.18)  # VALIDATED
    event = to_openlineage_complete_event(run_id=rid, proof=proof)
    assert event["eventType"] == "COMPLETE"


def test_complete_event_refuted_maps_to_complete_not_fail():
    """REFUTED is a real result — must NOT trip job-failure alerts."""
    rid = new_run_id()
    proof = _signed_proof(outcome_target=0.05)  # REFUTED
    event = to_openlineage_complete_event(run_id=rid, proof=proof)
    assert proof.verdict.outcome == "REFUTED"
    assert event["eventType"] == "COMPLETE"


def test_complete_event_inconclusive_maps_to_fail():
    rid = new_run_id()
    from ophamin.measuring.proof import Threshold, Verdict
    threshold = Threshold("slope", ">=", 0.1)
    proof = _signed_proof()
    proof.verdict = Verdict.decide(0.18, threshold, inconclusive=True)
    proof.sign(b"openlineage-test-key")
    event = to_openlineage_complete_event(run_id=rid, proof=proof)
    assert event["eventType"] == "FAIL"


# --- FAIL events (scenario crashed before producing proof) --------------


def test_fail_event_has_event_type_fail():
    rid = new_run_id()
    event = to_openlineage_fail_event(
        run_id=rid, scenario_name="my_scenario"
    )
    assert event["eventType"] == "FAIL"


def test_fail_event_with_error_message_attaches_error_facet():
    rid = new_run_id()
    event = to_openlineage_fail_event(
        run_id=rid,
        scenario_name="my_scenario",
        error_message="data source unreachable",
        error_type="ConnectionError",
    )
    facet = event["run"]["facets"]["ophamin_error"]
    assert facet["error_message"] == "data source unreachable"
    assert facet["error_type"] == "ConnectionError"


def test_fail_event_without_error_info_omits_facet():
    """No error_message + no error_type → no ophamin_error facet
    (facets must carry real content)."""
    rid = new_run_id()
    event = to_openlineage_fail_event(
        run_id=rid, scenario_name="my_scenario"
    )
    assert "ophamin_error" not in event["run"]["facets"]


def test_fail_event_with_just_error_type_still_attaches_facet():
    """Either error_message OR error_type alone is enough content."""
    rid = new_run_id()
    event = to_openlineage_fail_event(
        run_id=rid,
        scenario_name="my_scenario",
        error_type="TimeoutError",
    )
    assert "ophamin_error" in event["run"]["facets"]


# --- End-to-end sequence consistency -------------------------------------


def test_start_to_complete_sequence_shares_run_id():
    """The canonical workflow: mint run_id once, thread it through
    START + RUNNING + COMPLETE. All three events MUST carry the
    same runId — that's how Marquez ties them into one run record."""
    rid = new_run_id()
    proof = _signed_proof()

    start = to_openlineage_start_event(
        run_id=rid,
        scenario_name="my_scenario",
        claim=proof.claim,
        datasets=proof.datasets,
    )
    running = to_openlineage_running_event(
        run_id=rid, scenario_name="my_scenario"
    )
    complete = to_openlineage_complete_event(
        run_id=rid, proof=proof, job_name="my_scenario"
    )

    assert start["run"]["runId"] == running["run"]["runId"]
    assert running["run"]["runId"] == complete["run"]["runId"]
    assert start["run"]["runId"] == str(rid)


def test_start_to_fail_sequence_shares_run_id():
    """Same shape but ending in FAIL (e.g., scenario crashed)."""
    rid = new_run_id()

    start = to_openlineage_start_event(
        run_id=rid, scenario_name="my_scenario"
    )
    fail = to_openlineage_fail_event(
        run_id=rid,
        scenario_name="my_scenario",
        error_message="OOM at cycle 3422",
        error_type="MemoryError",
    )

    assert start["run"]["runId"] == fail["run"]["runId"]


def test_all_streaming_events_serialize_to_json():
    """Every event in the streaming sequence must round-trip cleanly
    through json.dumps for transport."""
    rid = new_run_id()
    proof = _signed_proof()

    for event in [
        to_openlineage_start_event(
            run_id=rid,
            scenario_name="my_scenario",
            claim=proof.claim,
            datasets=proof.datasets,
            analysis_plan="test plan",
        ),
        to_openlineage_running_event(
            run_id=rid,
            scenario_name="my_scenario",
            progress={"percent_complete": 0.5},
        ),
        to_openlineage_complete_event(
            run_id=rid, proof=proof
        ),
        to_openlineage_fail_event(
            run_id=rid,
            scenario_name="my_scenario",
            error_message="test failure",
        ),
    ]:
        text = json.dumps(event, sort_keys=True)
        assert json.loads(text) == event


def test_streaming_events_match_schema_url():
    """All streaming events declare the same schemaURL as the
    single-event path — consistent shape for downstream consumers."""
    rid = new_run_id()
    proof = _signed_proof()

    for event in [
        to_openlineage_start_event(run_id=rid, scenario_name="x"),
        to_openlineage_running_event(run_id=rid, scenario_name="x"),
        to_openlineage_complete_event(run_id=rid, proof=proof),
        to_openlineage_fail_event(run_id=rid, scenario_name="x"),
    ]:
        assert event["schemaURL"] == OPENLINEAGE_SCHEMA_URL


def test_streaming_events_carry_version_pinned_producer():
    """All streaming events carry the same versioned producer URL."""
    rid = new_run_id()
    proof = _signed_proof()
    events = [
        to_openlineage_start_event(run_id=rid, scenario_name="x"),
        to_openlineage_running_event(run_id=rid, scenario_name="x"),
        to_openlineage_complete_event(run_id=rid, proof=proof),
        to_openlineage_fail_event(run_id=rid, scenario_name="x"),
    ]
    producers = {e["producer"] for e in events}
    assert len(producers) == 1  # all identical
    assert OPENLINEAGE_PRODUCER_URL_BASE in producers.pop()


def test_run_id_accepts_uuid_or_string_consistently():
    """All 4 streaming-event functions accept UUID OR str."""
    rid_uuid = new_run_id()
    rid_str = str(rid_uuid)
    proof = _signed_proof()

    for run_id_arg in (rid_uuid, rid_str):
        # All four functions accept it
        to_openlineage_start_event(run_id=run_id_arg, scenario_name="x")
        to_openlineage_running_event(run_id=run_id_arg, scenario_name="x")
        to_openlineage_complete_event(run_id=run_id_arg, proof=proof)
        to_openlineage_fail_event(run_id=run_id_arg, scenario_name="x")
