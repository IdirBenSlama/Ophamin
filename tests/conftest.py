"""Pytest session configuration.

Proof attestation (ed25519, CR2) is ON BY DEFAULT in `persist_proof` so that
real proofs an operator produces are publicly verifiable. The test suite opts
OUT (`OPHAMIN_ATTEST=0`) so persisted proof bytes stay deterministic and
machine-independent (the attestation block embeds a per-machine author + public
key). Tests that exercise attestation set `OPHAMIN_ATTEST=1` explicitly via
monkeypatch.

Forced (not setdefault) so the suite is deterministic regardless of the
developer's shell environment.
"""

from __future__ import annotations

import os

os.environ["OPHAMIN_ATTEST"] = "0"

# MLflow 3.x deprecated the filesystem tracking backend by default —
# FileStore now raises MlflowException unless MLFLOW_ALLOW_FILE_STORE=true.
# Tests use tmp_path-backed file:// URIs as self-contained sandboxes, so opt
# in at the suite level (forced — does not depend on developer shell env).
# Tests using a database backend can monkeypatch.delenv in their own scope.
os.environ["MLFLOW_ALLOW_FILE_STORE"] = "true"
