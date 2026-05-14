"""F pillar — Formal data lineage and provenance.

Cryptographically links every result to the exact substrate revision and
configuration that produced it.

    prov     W3C PROV-O graph wrapping the `prov` library -> PROV-JSON
    lineage  content-addressed run manifests + MLflow tracking + DVC datasets
"""

from ophamin.provenance.lineage import (
    DatasetPointer,
    LineageStore,
    RunRecord,
    capture_git_commit,
    content_hash,
    make_run_id,
)
from ophamin.provenance.prov import ProvenanceGraph

__all__ = [
    "ProvenanceGraph",
    "LineageStore",
    "RunRecord",
    "DatasetPointer",
    "content_hash",
    "capture_git_commit",
    "make_run_id",
]
