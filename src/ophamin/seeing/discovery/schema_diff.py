"""Structural diff between two SchemaDocuments — what changed in Kimera?

Reports added / removed / type-changed fields between two schemas. This is
*structural* drift: a field that appears or disappears, a field whose Python
types changed across runs. Behavioural drift (e.g. occurrence rate shifted
from 100% to 60%) is Layer C's responsibility, not Layer A's.

The diff is deterministic — two equal SchemaDocuments produce an empty diff.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from ophamin.seeing.discovery.schema_document import SchemaDocument, TargetSchema


@dataclass(frozen=True)
class FieldChange:
    """One field's structural change between two schemas."""

    target: str
    path: str
    kind: str                       # "added" | "removed" | "type_changed"
    types_before: tuple[str, ...] = ()
    types_after: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            "target": self.target,
            "path": self.path,
            "kind": self.kind,
            "types_before": list(self.types_before),
            "types_after": list(self.types_after),
        }


@dataclass(frozen=True)
class SchemaDiff:
    """Structural diff between two SchemaDocuments.

    Targets and fields are normalised by name / path so the diff is
    independent of the underlying list ordering.
    """

    before: SchemaDocument
    after: SchemaDocument
    targets_added: tuple[str, ...] = field(default_factory=tuple)
    targets_removed: tuple[str, ...] = field(default_factory=tuple)
    field_changes: tuple[FieldChange, ...] = field(default_factory=tuple)

    def is_empty(self) -> bool:
        return (
            not self.targets_added
            and not self.targets_removed
            and not self.field_changes
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "before_kimera_commit": self.before.kimera_git_commit,
            "after_kimera_commit": self.after.kimera_git_commit,
            "before_captured_at": self.before.captured_at,
            "after_captured_at": self.after.captured_at,
            "targets_added": list(self.targets_added),
            "targets_removed": list(self.targets_removed),
            "field_changes": [c.to_dict() for c in self.field_changes],
            "is_empty": self.is_empty(),
        }


def diff_schemas(before: SchemaDocument, after: SchemaDocument) -> SchemaDiff:
    """Compute the structural diff between two SchemaDocuments."""
    before_targets = {t.name: t for t in before.targets}
    after_targets = {t.name: t for t in after.targets}

    targets_added = tuple(sorted(set(after_targets) - set(before_targets)))
    targets_removed = tuple(sorted(set(before_targets) - set(after_targets)))

    changes: list[FieldChange] = []
    for name in sorted(set(before_targets) & set(after_targets)):
        changes.extend(
            _diff_one_target(before_targets[name], after_targets[name])
        )
    # also surface fields belonging to ADDED targets as field-added
    for name in targets_added:
        for fld in after_targets[name].fields:
            changes.append(
                FieldChange(
                    target=name,
                    path=fld.path,
                    kind="added",
                    types_after=fld.types_seen,
                )
            )
    for name in targets_removed:
        for fld in before_targets[name].fields:
            changes.append(
                FieldChange(
                    target=name,
                    path=fld.path,
                    kind="removed",
                    types_before=fld.types_seen,
                )
            )

    return SchemaDiff(
        before=before,
        after=after,
        targets_added=targets_added,
        targets_removed=targets_removed,
        field_changes=tuple(changes),
    )


def _diff_one_target(
    before: TargetSchema, after: TargetSchema
) -> list[FieldChange]:
    """Per-target field diff: added / removed / type-changed."""
    before_fields = {f.path: f for f in before.fields}
    after_fields = {f.path: f for f in after.fields}

    added = sorted(set(after_fields) - set(before_fields))
    removed = sorted(set(before_fields) - set(after_fields))
    shared = sorted(set(before_fields) & set(after_fields))

    changes: list[FieldChange] = []
    for path in added:
        changes.append(
            FieldChange(
                target=after.name,
                path=path,
                kind="added",
                types_after=after_fields[path].types_seen,
            )
        )
    for path in removed:
        changes.append(
            FieldChange(
                target=before.name,
                path=path,
                kind="removed",
                types_before=before_fields[path].types_seen,
            )
        )
    for path in shared:
        types_before = before_fields[path].types_seen
        types_after = after_fields[path].types_seen
        if types_before != types_after:
            changes.append(
                FieldChange(
                    target=before.name,
                    path=path,
                    kind="type_changed",
                    types_before=types_before,
                    types_after=types_after,
                )
            )
    return changes
