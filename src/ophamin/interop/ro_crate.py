"""RO-Crate 1.2 exporter for signed Ophamin proofs.

RO-Crate (Research Object Crate) is a community-driven specification
for packaging research data + metadata as a self-describing directory,
keyed by a single ``ro-crate-metadata.json`` file at the root. The
spec is maintained at https://www.researchobject.org/ro-crate/ and is
formally based on JSON-LD + schema.org vocabulary.

Where in-toto answers "is this signed claim authentic?", RO-Crate
answers "what is the full self-describing artifact and how do its
pieces fit together?". The two layers are complementary:

- in-toto Statement → cryptographic claim about a digest
- RO-Crate Metadata → self-describing package: proof + data + provenance

Ophamin's mapping into RO-Crate's @graph:

  Root descriptor (`ro-crate-metadata.json`) → CreativeWork conforming
                                                 to RO-Crate 1.2
  Root data entity (`./`)                  → Dataset
  The signed proof (`proof.json`)          → File (application/json)
  Each §4 DatasetRef                       → Dataset (content-addressed)
  The §4 substrate name+commit             → SoftwareApplication
  The §6 verdict                           → AssessAction linking the
                                              claim to the observed value
  The §7 reproduction command              → SoftwareSourceCode
  Identity (ophamin_version, ophamin_git_commit) →
                                              additional SoftwareApplication

The exporter returns the metadata JSON dict; the caller writes it
alongside the proof file in whatever physical directory structure
they want (a "physical RO-Crate" is just a directory with the
metadata JSON at the root + the referenced files inside).

For documentation context see:

- https://www.researchobject.org/ro-crate/specification/1.2/
- https://www.researchobject.org/ro-crate/specification/1.2/root-data-entity.html
- https://schema.org/ — base vocabulary
"""

from __future__ import annotations

from typing import Any

from ophamin import __version__ as OPHAMIN_VERSION
from ophamin.measuring.proof.record import EmpiricalProofRecord

# --------------------------------------------------------------------------
# Constants — pinned by tests as @Stable surfaces. Drifting them is a
# major-version bump (consumers reading the conformsTo URI would need a
# migration path).
# --------------------------------------------------------------------------

#: URI for the RO-Crate 1.2 JSON-LD context.
RO_CRATE_CONTEXT_V1_2 = "https://w3id.org/ro/crate/1.2/context"

#: URI that the root descriptor declares conformance to.
RO_CRATE_CONFORMS_TO_V1_2 = "https://w3id.org/ro/crate/1.2"

#: Default file name for the proof referenced from the root Dataset's
#: ``hasPart``. Consumers may override via ``proof_filename`` kwarg.
DEFAULT_PROOF_FILENAME = "proof.json"


# --------------------------------------------------------------------------
# Public API
# --------------------------------------------------------------------------


def to_ro_crate_metadata(
    proof: EmpiricalProofRecord,
    *,
    proof_filename: str = DEFAULT_PROOF_FILENAME,
    extra_root_metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build an RO-Crate 1.2 ``ro-crate-metadata.json`` content dict.

    The returned dict is the literal content of ``ro-crate-metadata.json``
    as the spec describes it: a JSON-LD object with ``@context`` +
    ``@graph`` keys, where ``@graph`` lists every entity in the crate.

    The caller writes this dict to a file alongside the proof JSON to
    produce a complete RO-Crate directory. Typical filesystem layout::

        my-attestation/
          ro-crate-metadata.json   <- written from this function's return
          proof.json               <- ``json.dumps(proof.to_dict())``

    Parameters
    ----------
    proof
        The signed :class:`EmpiricalProofRecord` to package. Unsigned
        proofs are accepted (the crate is descriptive, not
        cryptographic) but the signature, when present, is preserved
        as the proof File entity's ``identifier`` so verifiers can
        re-check it via Ophamin's standard verify path.
    proof_filename
        File name to reference for the proof JSON. Default
        ``"proof.json"``. Must be a valid relative path — no
        leading ``/`` or ``..``.
    extra_root_metadata
        Optional extra key/value pairs to merge into the root Dataset
        entity (``@id: "./"``). Useful for adding ``creator``,
        ``license``, ``publisher`` — fields RO-Crate consumers like
        to surface but that Ophamin's proof shape doesn't carry
        natively. Keys are merged into the root entity verbatim; the
        caller is responsible for using schema.org-compliant property
        names.

    Returns
    -------
    dict
        The ``ro-crate-metadata.json`` content as a JSON-serializable
        dict. Serialize with ``json.dumps(metadata, indent=2,
        sort_keys=True)`` for human-readable output; or with the
        Ophamin canonical-form rules for byte-equivalent storage.

    Raises
    ------
    ValueError
        If ``proof_filename`` is empty, absolute (starts with ``/``),
        contains ``..``, or contains a NUL byte.
    """
    _validate_filename(proof_filename)

    graph: list[dict[str, Any]] = []

    # ---- Required: root descriptor ---------------------------------------
    # Per RO-Crate spec §"Root Data Entity Descriptor": exactly one
    # entity with @id "ro-crate-metadata.json", @type "CreativeWork",
    # about pointing to the root Dataset, conformsTo pointing to the
    # RO-Crate version URI.
    graph.append(
        {
            "@id": "ro-crate-metadata.json",
            "@type": "CreativeWork",
            "about": {"@id": "./"},
            "conformsTo": {"@id": RO_CRATE_CONFORMS_TO_V1_2},
        }
    )

    # ---- Required: root data entity --------------------------------------
    # Per RO-Crate spec §"Root Data Entity": @id is "./", @type at least
    # "Dataset" (additional types allowed), datePublished + name are
    # SHOULD-have-but-not-MUST.
    root_dataset: dict[str, Any] = {
        "@id": "./",
        "@type": "Dataset",
        "name": f"Ophamin Empirical Proof Record — {_short_proof_id(proof)}",
        "description": _build_root_description(proof),
        "datePublished": proof.created_at,
        "identifier": proof.proof_id,
        "conformsTo": [
            {"@id": RO_CRATE_CONFORMS_TO_V1_2},
            {"@id": f"https://ophamin.org/schema/{proof.schema_version}"},
        ],
        "hasPart": _build_has_part(proof, proof_filename),
        # mainEntity points at the proof file — the principal artifact
        # this RO-Crate is about (per RO-Crate "mainEntity" guidance).
        "mainEntity": {"@id": proof_filename},
    }
    if extra_root_metadata:
        for key, value in extra_root_metadata.items():
            root_dataset[key] = value
    graph.append(root_dataset)

    # ---- Proof JSON as File ----------------------------------------------
    graph.append(
        {
            "@id": proof_filename,
            "@type": "File",
            "name": "Empirical Proof Record (signed)",
            "description": (
                "JSON encoding of the Ophamin EmpiricalProofRecord — "
                "sections 1–8 (claim, preregistration, data, evidence, "
                "verdict, reproduction, provenance) plus the §9 HMAC-SHA256 "
                "signature. See SCHEMAS.md for the canonical-form spec."
            ),
            "encodingFormat": "application/json",
            "identifier": proof.signature if proof.signature else proof.proof_id,
        }
    )

    # ---- Each Dataset from §4 --------------------------------------------
    for dataset in proof.datasets:
        dataset_entity_id = _dataset_entity_id(dataset.content_hash)
        entity: dict[str, Any] = {
            "@id": dataset_entity_id,
            "@type": "Dataset",
            "name": dataset.name,
            "identifier": dataset.content_hash,
            "additionalType": dataset.kind,
        }
        if dataset.source:
            entity["url"] = dataset.source
        if dataset.n_records:
            # schema.org doesn't have a "record count" property; use the
            # generic "size" with a quantitative-value pattern.
            entity["size"] = {
                "@type": "QuantitativeValue",
                "value": dataset.n_records,
                "unitText": "records",
            }
        graph.append(entity)

    # ---- Substrate as SoftwareApplication --------------------------------
    if proof.substrate_name:
        substrate_id = (
            f"#substrate-{proof.substrate_name}"
            + (f"@{proof.substrate_git_commit[:12]}" if proof.substrate_git_commit else "")
        )
        substrate_entity: dict[str, Any] = {
            "@id": substrate_id,
            "@type": "SoftwareApplication",
            "name": proof.substrate_name,
            "applicationCategory": "substrate-under-test",
        }
        if proof.substrate_git_commit:
            substrate_entity["softwareVersion"] = proof.substrate_git_commit
        graph.append(substrate_entity)

    # ---- Verdict as AssessAction -----------------------------------------
    # An AssessAction (per schema.org) is the perfect fit: a deliberate
    # act of judging a target by some scale, producing an outcome.
    verdict = proof.verdict
    verdict_entity: dict[str, Any] = {
        "@id": "#verdict",
        "@type": "AssessAction",
        "name": f"Verdict — {verdict.outcome}",
        "result": {
            "@type": "PropertyValue",
            "propertyID": verdict.threshold.metric,
            "value": verdict.observed_value,
            "unitText": verdict.threshold.units,
        },
        "description": verdict.reasoning,
        "actionStatus": "CompletedActionStatus",
        # additionalType carries the structured Ophamin verdict outcome
        # so consumers parsing schema.org can branch on VALIDATED /
        # REFUTED / INCONCLUSIVE.
        "additionalType": verdict.outcome,
    }
    graph.append(verdict_entity)

    # ---- Reproduction command as SoftwareSourceCode ---------------------
    repro_entity: dict[str, Any] = {
        "@id": "#reproduction",
        "@type": "SoftwareSourceCode",
        "name": "Reproduction command",
        "text": proof.reproduction.command,
        "programmingLanguage": "shell",
        "description": (
            "Run this command from a clean Ophamin checkout to "
            "reproduce the empirical observation that produced this proof."
        ),
    }
    if proof.reproduction.lineage_chain:
        # Per W3C PROV best-practice — earlier proofs in the chain are
        # "wasDerivedFrom" references. We use schema.org's "isBasedOn".
        repro_entity["isBasedOn"] = [
            {"@id": f"#proof-{ancestor[:16]}"}
            for ancestor in proof.reproduction.lineage_chain
        ]
    graph.append(repro_entity)

    # ---- Ophamin as SoftwareApplication ----------------------------------
    ophamin_entity: dict[str, Any] = {
        "@id": "#ophamin",
        "@type": "SoftwareApplication",
        "name": "Ophamin",
        "softwareVersion": proof.ophamin_version or OPHAMIN_VERSION,
        "url": "https://github.com/IdirBenSlama/Ophamin",
        "description": (
            "Ophamin — an empirical observatory framework producing "
            "content-addressed, HMAC-signed proof records of falsifiable "
            "claims about a substrate under test."
        ),
    }
    if proof.ophamin_git_commit:
        ophamin_entity["identifier"] = proof.ophamin_git_commit
    graph.append(ophamin_entity)

    return {
        "@context": RO_CRATE_CONTEXT_V1_2,
        "@graph": graph,
    }


# --------------------------------------------------------------------------
# Helpers
# --------------------------------------------------------------------------


def _validate_filename(filename: str) -> None:
    """Refuse path-traversal / absolute / NUL-byte filenames LOUDLY.

    The proof file lives next to ``ro-crate-metadata.json`` in the crate
    directory. A filename like ``"../../etc/passwd"`` or ``"/tmp/x"`` is
    a real attack vector if a consumer naïvely joins it under the crate
    root and writes data there.
    """
    if not filename:
        raise ValueError("proof_filename must be non-empty")
    if filename.startswith("/"):
        raise ValueError(
            f"proof_filename must be a relative path, got absolute: {filename!r}"
        )
    if ".." in filename.split("/"):
        raise ValueError(
            f"proof_filename must not contain '..' path components: {filename!r}"
        )
    if "\x00" in filename:
        raise ValueError(
            f"proof_filename must not contain NUL bytes: {filename!r}"
        )


def _short_proof_id(proof: EmpiricalProofRecord) -> str:
    """First 16 hex chars of proof_id — used as a human-shortened tag in names."""
    return proof.proof_id[:16] if proof.proof_id else "unknown"


def _build_root_description(proof: EmpiricalProofRecord) -> str:
    """Compose a short human-readable description from claim + verdict."""
    statement = proof.claim.statement.strip()
    outcome = proof.verdict.outcome
    return (
        f"Self-contained empirical observation of: "
        f"{statement} — Verdict: {outcome}."
    )


def _build_has_part(
    proof: EmpiricalProofRecord, proof_filename: str
) -> list[dict[str, Any]]:
    """List of @id references the root Dataset hasPart on.

    Always includes the proof file. Datasets from §4 land here too, by
    their content-addressed @id (so consumers downloading the crate
    can refetch the dataset bytes from the URLs at runtime).
    """
    parts: list[dict[str, Any]] = [{"@id": proof_filename}]
    for dataset in proof.datasets:
        parts.append({"@id": _dataset_entity_id(dataset.content_hash)})
    return parts


def _dataset_entity_id(content_hash: str) -> str:
    """Stable @id for a Dataset entity, content-addressed by its hash.

    Using ``#dataset-<short_hash>`` keeps the @id within the RO-Crate
    document (a JSON-LD "blank node" style) rather than dereferencing
    to a network URL — the crate is self-contained. Consumers wanting
    the raw bytes follow the entity's ``url`` field.
    """
    short = content_hash[:16] if content_hash else "unknown"
    return f"#dataset-{short}"
