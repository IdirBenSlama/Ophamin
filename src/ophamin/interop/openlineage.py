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
from typing import Any

from ophamin import __version__ as OPHAMIN_VERSION
from ophamin.measuring.proof.record import EmpiricalProofRecord

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
# Helpers
# --------------------------------------------------------------------------


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
