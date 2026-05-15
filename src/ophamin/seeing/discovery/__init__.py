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

from ophamin.seeing.discovery.kimera_inventory import (
    DEFAULT_SIGN_KEY,
    INVENTORY_SCHEMA_VERSION,
    STRATA_DISCOVERERS,
    KimeraInventory,
    StratumInventory,
    Surface,
    discover_all,
    discover_cognitive,
    discover_interface,
    discover_lifecycle,
    discover_persistence,
    discover_reconciliation,
    discover_security,
    discover_telemetry,
    discover_temporal,
    discover_transport,
)
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
    "DEFAULT_SIGN_KEY",
    "FieldChange",
    "FieldSchema",
    "INVENTORY_SCHEMA_VERSION",
    "KimeraDiscoveryWatcher",
    "KimeraInventory",
    "SchemaDiff",
    "SchemaDocument",
    "SchemaMiner",
    "STRATA_DISCOVERERS",
    "StratumInventory",
    "Surface",
    "TargetSchema",
    "WatchOutcome",
    "diff_schemas",
    "discover_all",
    "discover_cognitive",
    "discover_interface",
    "discover_lifecycle",
    "discover_persistence",
    "discover_reconciliation",
    "discover_security",
    "discover_telemetry",
    "discover_temporal",
    "discover_transport",
    "kimera_head_commit",
    "write_schema_markdown",
]
