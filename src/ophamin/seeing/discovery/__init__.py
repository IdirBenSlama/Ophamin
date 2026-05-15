"""Substrate-introspection telescope — Layer A of Ophamin's Kimera-co-evolution stack.

Kimera-SWM is a substrate whose emergent behaviour evolves faster than
hand-rolled probe scripts can keep up. Each new commit shifts field names,
default values, halt-mode distributions, or wires new fields into
``OrchestratorResult``. The hand-rolled approach — write a one-off probe per
finding — means Ophamin's record drifts behind Kimera's actual state.

The discovery layer flips this:

    SchemaMiner             streams a balanced corpus through every Kimera
                            target, collects the full set of fields appearing
                            in ``CycleResult.raw`` (dot-paths into nested
                            dicts), with type, occurrence rate, and sample
                            values per path.
    SchemaDocument          immutable record of one schema-mining run, tagged
                            with the Kimera git commit, the Ophamin git
                            commit, the stimulus-set content hash, and a UTC
                            timestamp. Round-trips through JSON.
    SchemaWriter            writes a SchemaDocument as a human-readable
                            Markdown reference (KIMERA_FIELDS.md style).

Layers B and C of the evolution stack — scenario-as-config and behavioural
drift detection — both sit on top of this layer.
"""

from __future__ import annotations

from ophamin.seeing.discovery.schema_diff import FieldChange, SchemaDiff, diff_schemas
from ophamin.seeing.discovery.schema_document import (
    FieldSchema,
    SchemaDocument,
    TargetSchema,
)
from ophamin.seeing.discovery.schema_miner import SchemaMiner
from ophamin.seeing.discovery.schema_writer import write_schema_markdown
from ophamin.seeing.discovery.watcher import (
    DEFAULT_POLL_INTERVAL_S,
    KimeraDiscoveryWatcher,
    WatchOutcome,
    kimera_head_commit,
)

__all__ = [
    "DEFAULT_POLL_INTERVAL_S",
    "FieldChange",
    "FieldSchema",
    "KimeraDiscoveryWatcher",
    "SchemaDiff",
    "SchemaDocument",
    "SchemaMiner",
    "TargetSchema",
    "WatchOutcome",
    "diff_schemas",
    "kimera_head_commit",
    "write_schema_markdown",
]
