"""SchemaDocument — the immutable record of one schema-mining run.

A SchemaDocument captures *what fields Kimera produced* on a specific commit,
under a specific stimulus set, at a specific moment. It is content-addressable
(via the stimulus hash + Kimera commit) so two runs against the same Kimera
commit + same stimuli yield comparable documents.

Round-trips through JSON. Validation is strict: every required field must be
present, types must match, no silent fallback to defaults.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def _now_utc_iso() -> str:
    """Stable UTC ISO timestamp for record creation."""
    return datetime.now(timezone.utc).isoformat()


@dataclass(frozen=True)
class FieldSchema:
    """One field's empirical schema — every property derived from observation."""

    path: str                       # dot-path into raw, e.g. "prime.composite"
    types_seen: tuple[str, ...]     # python type names (sorted, deduped)
    occurrence_count: int           # cycles where the path was present
    n_cycles_target: int            # total cycles run against the target
    sample_values: tuple[Any, ...]  # first ~5 distinct values (or sample lengths for lists)
    sample_kind: str                # "values" | "lengths" — what sample_values represent

    @property
    def occurrence_rate(self) -> float:
        return self.occurrence_count / self.n_cycles_target if self.n_cycles_target else 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "path": self.path,
            "types_seen": list(self.types_seen),
            "occurrence_count": self.occurrence_count,
            "n_cycles_target": self.n_cycles_target,
            "occurrence_rate": self.occurrence_rate,
            "sample_values": list(self.sample_values),
            "sample_kind": self.sample_kind,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> FieldSchema:
        required = {"path", "types_seen", "occurrence_count", "n_cycles_target",
                    "sample_values", "sample_kind"}
        missing = required - set(data)
        if missing:
            raise ValueError(f"FieldSchema missing required keys: {sorted(missing)}")
        return cls(
            path=str(data["path"]),
            types_seen=tuple(data["types_seen"]),
            occurrence_count=int(data["occurrence_count"]),
            n_cycles_target=int(data["n_cycles_target"]),
            sample_values=tuple(data["sample_values"]),
            sample_kind=str(data["sample_kind"]),
        )


@dataclass(frozen=True)
class TargetSchema:
    """One Kimera target's empirical schema — fields + per-target metadata."""

    name: str
    target_class: str               # the fully-qualified class behind the target
    n_cycles: int
    n_adapter_errors: int
    fields: tuple[FieldSchema, ...]

    def field_paths(self) -> tuple[str, ...]:
        return tuple(f.path for f in self.fields)

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "target_class": self.target_class,
            "n_cycles": self.n_cycles,
            "n_adapter_errors": self.n_adapter_errors,
            "fields": [f.to_dict() for f in self.fields],
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> TargetSchema:
        required = {"name", "target_class", "n_cycles", "n_adapter_errors", "fields"}
        missing = required - set(data)
        if missing:
            raise ValueError(f"TargetSchema missing required keys: {sorted(missing)}")
        return cls(
            name=str(data["name"]),
            target_class=str(data["target_class"]),
            n_cycles=int(data["n_cycles"]),
            n_adapter_errors=int(data["n_adapter_errors"]),
            fields=tuple(FieldSchema.from_dict(f) for f in data["fields"]),
        )


@dataclass(frozen=True)
class SchemaDocument:
    """One complete schema-mining run — every target's fields, attributed.

    The Kimera + Ophamin git commits and the stimulus-set hash together
    uniquely identify *what was probed*. Two SchemaDocuments are
    behaviour-comparable iff they share those three identifiers.
    """

    ophamin_version: str
    ophamin_git_commit: str
    kimera_git_commit: str
    stimulus_set_hash: str           # content hash of the probe stimuli
    n_stimuli: int
    targets: tuple[TargetSchema, ...]
    captured_at: str = field(default_factory=_now_utc_iso)

    def target(self, name: str) -> TargetSchema | None:
        for t in self.targets:
            if t.name == name:
                return t
        return None

    def target_names(self) -> tuple[str, ...]:
        return tuple(t.name for t in self.targets)

    def to_dict(self) -> dict[str, Any]:
        return {
            "ophamin_version": self.ophamin_version,
            "ophamin_git_commit": self.ophamin_git_commit,
            "kimera_git_commit": self.kimera_git_commit,
            "stimulus_set_hash": self.stimulus_set_hash,
            "n_stimuli": self.n_stimuli,
            "captured_at": self.captured_at,
            "targets": [t.to_dict() for t in self.targets],
        }

    def to_json(self, path: str | Path) -> None:
        Path(path).write_text(json.dumps(self.to_dict(), indent=2, default=str))

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> SchemaDocument:
        required = {"ophamin_version", "ophamin_git_commit", "kimera_git_commit",
                    "stimulus_set_hash", "n_stimuli", "targets", "captured_at"}
        missing = required - set(data)
        if missing:
            raise ValueError(f"SchemaDocument missing required keys: {sorted(missing)}")
        return cls(
            ophamin_version=str(data["ophamin_version"]),
            ophamin_git_commit=str(data["ophamin_git_commit"]),
            kimera_git_commit=str(data["kimera_git_commit"]),
            stimulus_set_hash=str(data["stimulus_set_hash"]),
            n_stimuli=int(data["n_stimuli"]),
            targets=tuple(TargetSchema.from_dict(t) for t in data["targets"]),
            captured_at=str(data["captured_at"]),
        )

    @classmethod
    def from_json(cls, path: str | Path) -> SchemaDocument:
        return cls.from_dict(json.loads(Path(path).read_text()))
