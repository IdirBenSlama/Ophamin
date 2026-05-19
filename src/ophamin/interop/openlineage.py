"""OpenLineage 2.0 event emitter for signed Ophamin proofs.

OpenLineage (https://openlineage.io/) is a CNCF-incubating open
standard for data-pipeline lineage: every job in a pipeline emits
``START`` / ``COMPLETE`` / ``FAIL`` events carrying inputs, outputs,
job metadata, and arbitrary "facets" (extensible structured
sub-records). Production consumers include Apache Airflow (native
listener), dbt (via the Marquez backend), Apache Spark (spark-app
plugin), Apache Flink, and any other tool that posts events to a
collector.

Where in-toto provides cryptographic claims about an artifact, and
RO-Crate provides self-describing static packaging, OpenLineage
provides **lineage events** — the streaming-side counterpart that
slots an Ophamin observation into a live data-pipeline graph.

Mapping into OpenLineage's RunEvent shape:

  eventType         "COMPLETE" for VALIDATED / REFUTED outcomes;
                    "FAIL" for an INCONCLUSIVE verdict (the run
                    completed but the claim couldn't be decided)
  eventTime         proof.created_at (RFC 3339 UTC)
  run.runId         deterministic UUIDv5 derived from proof_id —
                    Ophamin's content-addressing makes the run_id
                    stable across re-emits (same proof → same runId)
  job.namespace     "ophamin"
  job.name          The scenario / pillar name from §5 (first
                    PillarEvidence.pillar by convention)
  inputs            One InputDataset per §4 DatasetRef
  outputs           One OutputDataset for the proof itself
  producer          Ophamin's repo URL + version
  schemaURL         OpenLineage 2.0.2 schema (or whatever's
                    pinned in OPENLINEAGE_SCHEMA_URL)

Two custom facets carry the Ophamin payload:

  ophamin_claim     The §2 claim (statement, h0/h1, threshold)
  ophamin_verdict   The §6 verdict (outcome, observed, reasoning)

Consumers wanting more granular lineage facets can post-process the
emitted event — the spec allows arbitrary additional facets per the
JSON-Schema "extensibility" guarantee.

For documentation context see:

- https://openlineage.io/docs/spec/object-model
- https://openlineage.io/apidocs/openapi/
- https://openlineage.io/docs/integrations/marquez

Producer URL convention:

The ``producer`` field is a stable URL identifying the *software
that emitted the event*. Per spec, it should encode the version so
consumers can disambiguate event-shape drift across emitter versions.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from ophamin import __version__ as OPHAMIN_VERSION
from ophamin.measuring.proof.record import (
    Claim,
    DatasetRef,
    EmpiricalProofRecord,
)

# --------------------------------------------------------------------------
# Constants — pinned by tests as @Stable surfaces. Drifting them is a
# major-version bump for downstream lineage consumers.
# --------------------------------------------------------------------------

#: OpenLineage 2.0.2 schema URL — the version Ophamin currently
#: emits against. Bumping pins downstream consumers to revalidate.
OPENLINEAGE_SCHEMA_URL = (
    "https://openlineage.io/spec/2-0-2/OpenLineage.json#/$defs/RunEvent"
)

#: Stable producer URL with the running Ophamin version. The version
#: encoding lets a Marquez / Airflow consumer attribute event-shape
#: variations to a specific Ophamin release.
OPENLINEAGE_PRODUCER_URL_BASE = "https://github.com/IdirBenSlama/Ophamin"

#: Default namespace for Ophamin-emitted jobs. Consumers may want to
#: override this (e.g., one namespace per deployment) by post-editing
#: the event dict before sending to Marquez — the field is part of
#: the public RunEvent surface so we don't expose a kwarg for it.
DEFAULT_NAMESPACE = "ophamin"

#: UUIDv5 namespace for deriving runIds from proof_ids. Using a fixed
#: namespace makes ``proof_id → runId`` deterministic and reproducible
#: across emitter instances / machines.
OPHAMIN_RUNID_NAMESPACE = uuid.UUID("ec1e6b1c-0000-4000-8000-000000000001")


# --------------------------------------------------------------------------
# Public API
# --------------------------------------------------------------------------


def to_openlineage_event(
    proof: EmpiricalProofRecord,
    *,
    job_name: str | None = None,
    namespace: str = DEFAULT_NAMESPACE,
    extra_facets: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build an OpenLineage 2.0 RunEvent dict for a signed proof.

    The returned dict is ready to POST to a Marquez backend or any
    OpenLineage-aware collector:

    .. code-block:: python

        import requests
        event = to_openlineage_event(signed_proof)
        requests.post("http://marquez:5000/api/v1/lineage", json=event)

    Parameters
    ----------
    proof
        Signed :class:`EmpiricalProofRecord`. Unsigned proofs are
        accepted (lineage events are descriptive, not cryptographic)
        but the signature, when present, is preserved in the
        ``ophamin_verdict`` facet for downstream attribution.
    job_name
        Override for the job name. Defaults to the first
        ``PillarEvidence.pillar`` from §5, or ``"empirical-claim"``
        if there's no evidence (unusual but possible).
    namespace
        The OpenLineage job namespace. Defaults to ``"ophamin"``.
    extra_facets
        Optional additional facets to merge into the run.facets dict.
        Each value should be a dict conforming to OpenLineage's
        facet schema shape (with `_producer` + `_schemaURL` keys).

    Returns
    -------
    dict
        An OpenLineage RunEvent dict. Serialize with the standard
        ``json.dumps`` (no canonicalization needed — OpenLineage
        spec doesn't require canonical bytes).

    Raises
    ------
    ValueError
        If ``namespace`` is empty (downstream Marquez requires
        non-empty namespace).
    """
    if not namespace:
        raise ValueError("namespace must be non-empty")

    event_type = _outcome_to_event_type(proof.verdict.outcome)
    run_id = _proof_id_to_run_id(proof.proof_id)
    job_name_resolved = job_name or _derive_job_name(proof)
    producer = _build_producer_url()

    run_facets: dict[str, Any] = {
        "ophamin_claim": _build_claim_facet(proof, producer),
        "ophamin_verdict": _build_verdict_facet(proof, producer),
    }
    if extra_facets:
        for key, value in extra_facets.items():
            run_facets[key] = value

    job_facets: dict[str, Any] = {}
    if proof.preregistration.analysis_plan:
        # OpenLineage has a "documentation" facet for human-readable
        # job documentation — perfect fit for the analysis plan.
        job_facets["documentation"] = {
            "_producer": producer,
            "_schemaURL": (
                "https://openlineage.io/spec/facets/1-0-1/"
                "DocumentationJobFacet.json"
            ),
            "description": proof.preregistration.analysis_plan,
        }

    return {
        "eventType": event_type,
        "eventTime": proof.created_at,
        "run": {
            "runId": str(run_id),
            "facets": run_facets,
        },
        "job": {
            "namespace": namespace,
            "name": job_name_resolved,
            "facets": job_facets,
        },
        "inputs": _build_inputs(proof, producer),
        "outputs": _build_outputs(proof, producer),
        "producer": producer,
        "schemaURL": OPENLINEAGE_SCHEMA_URL,
    }


# --------------------------------------------------------------------------
# Streaming event sequencing — START + RUNNING + COMPLETE / FAIL
# --------------------------------------------------------------------------
#
# The single-event ``to_openlineage_event`` above is the right shape for
# emit-once-when-done. For long-running Ophamin campaigns (hour-scale
# scenarios, multi-cycle observations), pipeline operators benefit from
# the full lifecycle: START at scenario boot, periodic RUNNING heartbeats
# during the run, and a terminal COMPLETE (with the proof) or FAIL (with
# an error description) at the end.
#
# The same ``run_id`` MUST be used for all events in a single run —
# OpenLineage's spec ties events together by ``run.runId`` equality.
# Use :func:`new_run_id` at scenario start, pass the resulting UUID
# through to each subsequent event call.


def new_run_id() -> uuid.UUID:
    """Mint a fresh random ``runId`` for a new Ophamin scenario invocation.

    OpenLineage RunEvent spec requires ``run.runId`` to be consistent
    across the START + RUNNING + COMPLETE / FAIL events for one run.
    The single-event :func:`to_openlineage_event` path derives runId
    deterministically from the signed proof's ``proof_id``; the
    streaming path can't do that (no proof exists yet at START time),
    so the caller mints a fresh UUID and threads it through.

    Returns
    -------
    uuid.UUID
        A fresh random UUIDv4. Pass it as the ``run_id`` kwarg to
        :func:`to_openlineage_start_event`, :func:`to_openlineage_running_event`,
        and the terminal :func:`to_openlineage_complete_event` or
        :func:`to_openlineage_fail_event`.

    Notes
    -----
    The single-event terminal :func:`to_openlineage_event` continues
    to derive runId from proof_id (deterministic, content-addressed).
    The streaming path is non-deterministic by necessity — same scenario
    code, same inputs, different ``runId`` per invocation.
    """
    return uuid.uuid4()


def to_openlineage_start_event(
    *,
    run_id: uuid.UUID | str,
    scenario_name: str,
    namespace: str = DEFAULT_NAMESPACE,
    claim: Claim | None = None,
    datasets: list[DatasetRef] | None = None,
    analysis_plan: str = "",
    event_time: str | None = None,
    extra_facets: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build an OpenLineage START RunEvent for a fresh scenario invocation.

    Emit this immediately before kicking off the substrate measurement.
    Marquez (or any OpenLineage collector) renders this as the job's
    start marker; subsequent RUNNING + terminal events tie back to the
    same ``run_id``.

    Parameters
    ----------
    run_id
        The run identifier shared by ALL events in this run. Mint a
        fresh one via :func:`new_run_id`. Accepts ``uuid.UUID`` or its
        string form (a 36-char dashed UUID).
    scenario_name
        The job name (e.g. ``"immune_siege"``, ``"organizational_dissonance"``).
        OpenLineage's ``job.name`` field.
    namespace
        OpenLineage job namespace. Defaults to ``"ophamin"``.
    claim
        Optional pre-registered :class:`Claim`. When provided, the
        ``ophamin_claim`` run facet is attached so consumers know what
        the run is *about to test* before any results exist.
    datasets
        Optional list of :class:`DatasetRef` the scenario will consume.
        Maps to OpenLineage ``inputs`` so the lineage graph shows the
        intended sources from event 1.
    analysis_plan
        Optional plain-text analysis plan. Attached as the standard
        OpenLineage ``documentation`` job facet.
    event_time
        RFC 3339 UTC timestamp. Defaults to "now".
    extra_facets
        Additional run.facets to merge.

    Returns
    -------
    dict
        An OpenLineage RunEvent with ``eventType: "START"`` ready to
        POST to a Marquez backend.

    Raises
    ------
    ValueError
        Empty namespace, empty scenario_name, or invalid run_id.
    """
    if not namespace:
        raise ValueError("namespace must be non-empty")
    if not scenario_name:
        raise ValueError("scenario_name must be non-empty")

    run_id_str = _coerce_run_id(run_id)
    event_time_str = event_time or _now_rfc3339()
    producer = _build_producer_url()

    run_facets: dict[str, Any] = {}
    if claim is not None:
        run_facets["ophamin_claim"] = _build_claim_facet_from_claim(claim, producer)
    if extra_facets:
        run_facets.update(extra_facets)

    job_facets: dict[str, Any] = {}
    if analysis_plan:
        job_facets["documentation"] = {
            "_producer": producer,
            "_schemaURL": (
                "https://openlineage.io/spec/facets/1-0-1/"
                "DocumentationJobFacet.json"
            ),
            "description": analysis_plan,
        }

    return {
        "eventType": "START",
        "eventTime": event_time_str,
        "run": {"runId": run_id_str, "facets": run_facets},
        "job": {
            "namespace": namespace,
            "name": scenario_name,
            "facets": job_facets,
        },
        "inputs": _build_inputs_from_datasets(datasets or [], producer),
        "outputs": [],  # No output yet at START
        "producer": producer,
        "schemaURL": OPENLINEAGE_SCHEMA_URL,
    }


def to_openlineage_running_event(
    *,
    run_id: uuid.UUID | str,
    scenario_name: str,
    namespace: str = DEFAULT_NAMESPACE,
    event_time: str | None = None,
    progress: dict[str, Any] | None = None,
    extra_facets: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build an OpenLineage RUNNING RunEvent — a heartbeat during a long run.

    Emit one or more of these between START and terminal events to
    surface progress in Marquez's job-running view. Each RUNNING event
    is a snapshot; OpenLineage doesn't require any specific cadence.

    Parameters
    ----------
    run_id
        MUST match the run_id passed to the START event.
    scenario_name
        MUST match the START event's scenario_name (job.name).
    namespace
        MUST match the START event's namespace.
    event_time
        RFC 3339 UTC timestamp. Defaults to "now".
    progress
        Optional dict of progress fields to attach as the
        ``ophamin_progress`` custom facet. Conventional fields:

        - ``percent_complete`` — float in [0.0, 1.0]
        - ``cycles_completed`` — int
        - ``cycles_total`` — int
        - ``message`` — short status string

        Any keys allowed; the spec for this facet is open by design.
    extra_facets
        Additional run.facets to merge.

    Returns
    -------
    dict
        An OpenLineage RunEvent with ``eventType: "RUNNING"``.

    Raises
    ------
    ValueError
        Empty namespace or scenario_name.
    """
    if not namespace:
        raise ValueError("namespace must be non-empty")
    if not scenario_name:
        raise ValueError("scenario_name must be non-empty")

    run_id_str = _coerce_run_id(run_id)
    event_time_str = event_time or _now_rfc3339()
    producer = _build_producer_url()

    run_facets: dict[str, Any] = {}
    if progress:
        run_facets["ophamin_progress"] = {
            "_producer": producer,
            "_schemaURL": (
                f"{OPENLINEAGE_PRODUCER_URL_BASE}/blob/main/SCHEMAS.md"
                "#progress-ophamin"
            ),
            **progress,
        }
    if extra_facets:
        run_facets.update(extra_facets)

    return {
        "eventType": "RUNNING",
        "eventTime": event_time_str,
        "run": {"runId": run_id_str, "facets": run_facets},
        "job": {
            "namespace": namespace,
            "name": scenario_name,
            "facets": {},
        },
        "inputs": [],
        "outputs": [],
        "producer": producer,
        "schemaURL": OPENLINEAGE_SCHEMA_URL,
    }


def to_openlineage_complete_event(
    *,
    run_id: uuid.UUID | str,
    proof: EmpiricalProofRecord,
    namespace: str = DEFAULT_NAMESPACE,
    job_name: str | None = None,
    extra_facets: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build a terminal OpenLineage event using a caller-managed run_id.

    Same shape as :func:`to_openlineage_event` (eventType mapping is
    identical: VALIDATED/REFUTED → COMPLETE; INCONCLUSIVE → FAIL), but
    the ``run.runId`` is the caller-provided ``run_id`` instead of
    being derived from ``proof.proof_id``. Use this as the terminal
    event of a START/RUNNING/COMPLETE sequence so the run_id stays
    consistent with the earlier events.

    For single-event emission (no START + RUNNING preamble), use
    :func:`to_openlineage_event` instead — it derives a content-addressed
    runId from the proof for cross-machine determinism.

    Parameters
    ----------
    run_id
        MUST match the run_id from the START event.
    proof
        The signed :class:`EmpiricalProofRecord`.
    namespace
        OpenLineage namespace (default ``"ophamin"``).
    job_name
        Job name override; defaults to first pillar in §5 evidence.
    extra_facets
        Additional run.facets to merge alongside ophamin_claim +
        ophamin_verdict.

    Returns
    -------
    dict
        An OpenLineage RunEvent with ``eventType: "COMPLETE"`` (for
        VALIDATED/REFUTED outcomes) or ``"FAIL"`` (for INCONCLUSIVE).
    """
    if not namespace:
        raise ValueError("namespace must be non-empty")

    run_id_str = _coerce_run_id(run_id)
    event_type = _outcome_to_event_type(proof.verdict.outcome)
    job_name_resolved = job_name or _derive_job_name(proof)
    producer = _build_producer_url()

    run_facets: dict[str, Any] = {
        "ophamin_claim": _build_claim_facet(proof, producer),
        "ophamin_verdict": _build_verdict_facet(proof, producer),
    }
    if extra_facets:
        run_facets.update(extra_facets)

    job_facets: dict[str, Any] = {}
    if proof.preregistration.analysis_plan:
        job_facets["documentation"] = {
            "_producer": producer,
            "_schemaURL": (
                "https://openlineage.io/spec/facets/1-0-1/"
                "DocumentationJobFacet.json"
            ),
            "description": proof.preregistration.analysis_plan,
        }

    return {
        "eventType": event_type,
        "eventTime": proof.created_at,
        "run": {"runId": run_id_str, "facets": run_facets},
        "job": {
            "namespace": namespace,
            "name": job_name_resolved,
            "facets": job_facets,
        },
        "inputs": _build_inputs(proof, producer),
        "outputs": _build_outputs(proof, producer),
        "producer": producer,
        "schemaURL": OPENLINEAGE_SCHEMA_URL,
    }


def to_openlineage_fail_event(
    *,
    run_id: uuid.UUID | str,
    scenario_name: str,
    namespace: str = DEFAULT_NAMESPACE,
    error_message: str = "",
    error_type: str = "",
    event_time: str | None = None,
    extra_facets: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build an OpenLineage FAIL RunEvent for a scenario that crashed
    before producing a proof.

    Distinct from the INCONCLUSIVE-verdict path (which DOES produce a
    proof but couldn't decide the threshold): FAIL is for the case
    where the scenario raised an exception, ran out of resources, or
    otherwise terminated without emitting a proof at all.

    Marquez renders FAIL events as red in the lineage graph. The
    ``ophamin_error`` facet carries the failure details.

    Parameters
    ----------
    run_id
        MUST match the run_id from the START event.
    scenario_name
        MUST match the START event's scenario_name (job.name).
    namespace
        MUST match the START event's namespace.
    error_message
        Plain-text description of what went wrong.
    error_type
        Optional exception class name (e.g. ``"TimeoutError"``,
        ``"FileNotFoundError"``).
    event_time
        RFC 3339 UTC timestamp. Defaults to "now".
    extra_facets
        Additional run.facets to merge.

    Returns
    -------
    dict
        An OpenLineage RunEvent with ``eventType: "FAIL"``.
    """
    if not namespace:
        raise ValueError("namespace must be non-empty")
    if not scenario_name:
        raise ValueError("scenario_name must be non-empty")

    run_id_str = _coerce_run_id(run_id)
    event_time_str = event_time or _now_rfc3339()
    producer = _build_producer_url()

    run_facets: dict[str, Any] = {}
    if error_message or error_type:
        run_facets["ophamin_error"] = {
            "_producer": producer,
            "_schemaURL": (
                f"{OPENLINEAGE_PRODUCER_URL_BASE}/blob/main/SCHEMAS.md"
                "#error-ophamin"
            ),
            "error_message": error_message,
            "error_type": error_type,
        }
    if extra_facets:
        run_facets.update(extra_facets)

    return {
        "eventType": "FAIL",
        "eventTime": event_time_str,
        "run": {"runId": run_id_str, "facets": run_facets},
        "job": {
            "namespace": namespace,
            "name": scenario_name,
            "facets": {},
        },
        "inputs": [],
        "outputs": [],
        "producer": producer,
        "schemaURL": OPENLINEAGE_SCHEMA_URL,
    }


# --------------------------------------------------------------------------
# Helpers
# --------------------------------------------------------------------------


def _coerce_run_id(run_id: uuid.UUID | str) -> str:
    """Accept either a UUID object or a 36-char dashed string; emit string form."""
    if isinstance(run_id, uuid.UUID):
        return str(run_id)
    if isinstance(run_id, str):
        # Validate the string parses as a UUID — catches typos
        try:
            uuid.UUID(run_id)
        except ValueError as exc:
            raise ValueError(
                f"run_id string must be a valid UUID: {run_id!r}"
            ) from exc
        return run_id
    raise TypeError(
        f"run_id must be uuid.UUID or str, got {type(run_id).__name__}"
    )


def _now_rfc3339() -> str:
    """Current UTC time as an RFC 3339 string (e.g. '2026-05-19T01:30:00Z')."""
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _build_claim_facet_from_claim(
    claim: Claim, producer: str
) -> dict[str, Any]:
    """Build an ophamin_claim facet directly from a Claim (no full proof needed).

    Used by START events where we have the pre-registered claim but
    no proof yet. The output matches what :func:`_build_claim_facet`
    produces, so STARTÉ + COMPLETE events present a consistent
    ophamin_claim facet to Marquez.
    """
    return {
        "_producer": producer,
        "_schemaURL": (
            f"{OPENLINEAGE_PRODUCER_URL_BASE}/blob/main/SCHEMAS.md"
            "#claim-ophamin"
        ),
        "statement": claim.statement,
        "operationalization": claim.operationalization,
        "h0": claim.h0,
        "h1": claim.h1,
        "threshold": {
            "metric": claim.threshold.metric,
            "comparator": claim.threshold.comparator,
            "value": claim.threshold.value,
            "units": claim.threshold.units,
        },
    }


def _build_inputs_from_datasets(
    datasets: list[DatasetRef], producer: str
) -> list[dict[str, Any]]:
    """Build OpenLineage inputs directly from a DatasetRef list.

    Used by START events. Output matches what :func:`_build_inputs`
    produces from a proof, so START and COMPLETE events present
    consistent inputs to Marquez.
    """
    inputs: list[dict[str, Any]] = []
    for dataset in datasets:
        entry: dict[str, Any] = {
            "namespace": "ophamin.datasets",
            "name": dataset.name,
            "facets": {
                "dataSource": {
                    "_producer": producer,
                    "_schemaURL": (
                        "https://openlineage.io/spec/facets/1-0-1/"
                        "DataSourceDatasetFacet.json"
                    ),
                    "name": dataset.kind,
                    "uri": dataset.source,
                },
                "ophamin_dataset": {
                    "_producer": producer,
                    "_schemaURL": (
                        f"{OPENLINEAGE_PRODUCER_URL_BASE}/blob/main/SCHEMAS.md"
                        "#datasetref-ophamin"
                    ),
                    "content_hash": dataset.content_hash,
                    "n_records": dataset.n_records,
                    "kind": dataset.kind,
                },
            },
        }
        inputs.append(entry)
    return inputs


def _build_producer_url() -> str:
    """Producer URL with version-pinned suffix for consumer disambiguation."""
    return f"{OPENLINEAGE_PRODUCER_URL_BASE}@{OPHAMIN_VERSION}"


def _outcome_to_event_type(outcome: str) -> str:
    """Map Ophamin verdict outcomes to OpenLineage eventType.

    OpenLineage's RunEvent enum: START | RUNNING | COMPLETE | ABORT |
    FAIL | OTHER. Ophamin emits a single terminal event per proof:

    - VALIDATED → COMPLETE (the canonical happy path)
    - REFUTED → COMPLETE (the claim was disproved — that's a real
      empirical result, not a job failure)
    - INCONCLUSIVE → FAIL (the run completed but the threshold
      couldn't be evaluated — the job didn't produce a deciding
      observation)

    The distinction matters: REFUTED is a valid Ophamin outcome
    that should NOT trip downstream "job failure" alerts on the
    pipeline platform. INCONCLUSIVE genuinely means the job didn't
    produce its expected output.
    """
    if outcome == "INCONCLUSIVE":
        return "FAIL"
    return "COMPLETE"


def _proof_id_to_run_id(proof_id: str) -> uuid.UUID:
    """Deterministically derive a UUIDv5 from the proof's content-addressed proof_id.

    Using UUIDv5 with a fixed namespace makes the mapping
    reproducible: the same proof_id always maps to the same runId,
    regardless of which Ophamin emitter machine produced it. This
    lets a downstream Marquez backend dedupe re-emitted events
    without consulting any state outside the proof itself.
    """
    if not proof_id:
        # Fall back to a random UUID — an unsigned/incomplete proof
        # still emits a syntactically-valid event, just without
        # the determinism guarantee.
        return uuid.uuid4()
    return uuid.uuid5(OPHAMIN_RUNID_NAMESPACE, proof_id)


def _derive_job_name(proof: EmpiricalProofRecord) -> str:
    """Compose the job name from the first evidence pillar.

    OpenLineage doesn't have a canonical "scenario name" field;
    job.name is its closest analogue. The first PillarEvidence's
    ``pillar`` field (e.g. "I.cma", "O.x.rate") is the most
    descriptive token Ophamin records carry.
    """
    if proof.evidence:
        return proof.evidence[0].pillar
    return "empirical-claim"


def _build_inputs(proof: EmpiricalProofRecord, producer: str) -> list[dict[str, Any]]:
    """Each §4 DatasetRef → one OpenLineage InputDataset."""
    inputs: list[dict[str, Any]] = []
    for dataset in proof.datasets:
        entry: dict[str, Any] = {
            "namespace": "ophamin.datasets",
            "name": dataset.name,
            "facets": {},
        }
        # Carry the content-hash in a Storage facet so a Marquez
        # operator can join lineage on it.
        entry["facets"]["dataSource"] = {
            "_producer": producer,
            "_schemaURL": (
                "https://openlineage.io/spec/facets/1-0-1/"
                "DataSourceDatasetFacet.json"
            ),
            "name": dataset.kind,
            "uri": dataset.source,
        }
        # Use a custom "ophamin_dataset" facet to carry the content
        # hash + record count — these don't fit any standard
        # OpenLineage facet but consumers can pick them out.
        entry["facets"]["ophamin_dataset"] = {
            "_producer": producer,
            "_schemaURL": (
                f"{OPENLINEAGE_PRODUCER_URL_BASE}/blob/main/SCHEMAS.md"
                "#datasetref-ophamin"
            ),
            "content_hash": dataset.content_hash,
            "n_records": dataset.n_records,
            "kind": dataset.kind,
        }
        inputs.append(entry)
    return inputs


def _build_outputs(
    proof: EmpiricalProofRecord, producer: str
) -> list[dict[str, Any]]:
    """The signed proof itself is the lineage output of the run.

    A scenario run consumes datasets and produces a content-addressed
    signed claim — that's the lineage shape. Carrying the proof_id
    as the output's name lets downstream consumers dedupe + index.
    """
    return [
        {
            "namespace": "ophamin.proofs",
            "name": proof.proof_id or "unsigned-proof",
            "facets": {
                "schema": {
                    "_producer": producer,
                    "_schemaURL": (
                        "https://openlineage.io/spec/facets/1-0-1/"
                        "SchemaDatasetFacet.json"
                    ),
                    "fields": [
                        {"name": "proof_id", "type": "string"},
                        {"name": "verdict.outcome", "type": "string"},
                        {"name": "verdict.observed_value", "type": "number"},
                        {"name": "signature", "type": "string"},
                    ],
                },
            },
        }
    ]


def _build_claim_facet(
    proof: EmpiricalProofRecord, producer: str
) -> dict[str, Any]:
    claim = proof.claim
    return {
        "_producer": producer,
        "_schemaURL": (
            f"{OPENLINEAGE_PRODUCER_URL_BASE}/blob/main/SCHEMAS.md"
            "#claim-ophamin"
        ),
        "statement": claim.statement,
        "operationalization": claim.operationalization,
        "h0": claim.h0,
        "h1": claim.h1,
        "threshold": {
            "metric": claim.threshold.metric,
            "comparator": claim.threshold.comparator,
            "value": claim.threshold.value,
            "units": claim.threshold.units,
        },
    }


def _build_verdict_facet(
    proof: EmpiricalProofRecord, producer: str
) -> dict[str, Any]:
    verdict = proof.verdict
    facet: dict[str, Any] = {
        "_producer": producer,
        "_schemaURL": (
            f"{OPENLINEAGE_PRODUCER_URL_BASE}/blob/main/SCHEMAS.md"
            "#verdict-ophamin"
        ),
        "outcome": verdict.outcome,
        "observed_value": verdict.observed_value,
        "reasoning": verdict.reasoning,
        "threshold": {
            "metric": verdict.threshold.metric,
            "comparator": verdict.threshold.comparator,
            "value": verdict.threshold.value,
            "units": verdict.threshold.units,
        },
    }
    if proof.signature:
        # Preserve the inner Ophamin HMAC so downstream attribution
        # can re-verify the lineage event's payload against the
        # signed proof.
        facet["ophamin_signature"] = proof.signature
        facet["ophamin_signature_algorithm"] = "HMAC-SHA256"
    return facet
