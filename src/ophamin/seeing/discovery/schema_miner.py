"""SchemaMiner — streams a balanced stimulus set through every Kimera target.

For each target × stimulus, runs one cycle and flattens ``CycleResult.raw``
into dot-paths. Aggregates types, occurrence rates, and sample values per
path across all cycles. Builds a SchemaDocument tagged with the Kimera +
Ophamin git commits and the stimulus-set content hash.

Lists are recorded at their parent path with type ``list`` and sample
*lengths* (not values) — recursing into list elements would explode for
fields like ``zetetic_contradictions`` that can carry 30+ items per cycle.
Nested dicts ARE recursed into.

The miner uses the framework's existing ``SubstrateUnderTest`` interface, so
it works against ``KimeraAdapter`` (real Kimera) or ``MockSubstrate`` (tests)
without any branching.
"""

from __future__ import annotations

import hashlib
from collections import Counter
from typing import Any, Iterable

from ophamin import __version__
from ophamin.seeing.discovery.schema_document import (
    FieldSchema,
    SchemaDocument,
    TargetSchema,
)
from ophamin.comparing.provenance.lineage import _ophamin_project_root, capture_git_commit
from ophamin.seeing.substrate.base import CycleResult, SubstrateUnderTest

#: maximum distinct sample values (or lengths) to record per field path
DEFAULT_MAX_SAMPLES = 5
#: maximum recursion depth into nested dicts
DEFAULT_MAX_DEPTH = 6
#: characters to truncate string sample values at (avoids 4000-char prompts in the schema doc)
DEFAULT_STRING_SAMPLE_LIMIT = 80


def _flatten(
    raw: Any,
    *,
    prefix: str = "",
    depth: int = 0,
    max_depth: int = DEFAULT_MAX_DEPTH,
    out: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Flatten a nested dict to dot-paths.

    Returns ``{path: value}`` where:
      - dict values are recursed into;
      - list values are kept as the list itself (the caller records type=list +
        sample_lengths rather than recursing into elements);
      - scalar values are kept as-is;
      - max recursion depth is bounded to defend against pathological cycles.
    """
    if out is None:
        out = {}
    if depth > max_depth:
        out[prefix or "<too_deep>"] = "<MAX_DEPTH_EXCEEDED>"
        return out
    if isinstance(raw, dict):
        if not raw and prefix:
            out[prefix] = {}  # empty dict — record presence
        for key, value in raw.items():
            sub_path = f"{prefix}.{key}" if prefix else str(key)
            _flatten(value, prefix=sub_path, depth=depth + 1, max_depth=max_depth, out=out)
    else:
        out[prefix] = raw
    return out


def _python_type_name(value: Any) -> str:
    return type(value).__name__


def _truncate_string(value: str, limit: int = DEFAULT_STRING_SAMPLE_LIMIT) -> str:
    if len(value) <= limit:
        return value
    return value[: limit - 1] + "…"


def _summarise_value(value: Any) -> Any:
    """Coerce one cycle's value into a JSON-safe representation for the sample."""
    if isinstance(value, str):
        return _truncate_string(value)
    if isinstance(value, (bool, int, float)) or value is None:
        return value
    if isinstance(value, (list, tuple, set)):
        # never inline list contents — caller records the LENGTH separately
        return f"<{type(value).__name__} len={len(value)}>"
    if isinstance(value, dict):
        return f"<dict keys={sorted(value.keys())[:5]}>"
    return f"<{type(value).__name__}>"


def _content_hash_stimuli(stimuli: list[str]) -> str:
    """SHA-256 over the canonical encoding of the stimulus list."""
    h = hashlib.sha256()
    for s in stimuli:
        h.update(len(s).to_bytes(4, "big"))
        h.update(s.encode("utf-8"))
    return h.hexdigest()


class SchemaMiner:
    """Streams a stimulus set through every target and builds a SchemaDocument.

    Construction is cheap; the work happens in ``mine()``. One SchemaMiner can
    mine the same substrate against multiple stimulus sets — each call to
    ``mine()`` produces an independent SchemaDocument.
    """

    def __init__(
        self,
        substrate: SubstrateUnderTest,
        *,
        max_samples: int = DEFAULT_MAX_SAMPLES,
        max_depth: int = DEFAULT_MAX_DEPTH,
    ) -> None:
        self.substrate = substrate
        self.max_samples = int(max_samples)
        self.max_depth = int(max_depth)

    def mine(
        self,
        targets: Iterable[str],
        stimuli: list[str],
    ) -> SchemaDocument:
        """Mine schemas for every named target on the given stimulus list.

        Returns a SchemaDocument with one TargetSchema per target.

        Raises ``ValueError`` if ``stimuli`` is empty.
        """
        if not stimuli:
            raise ValueError("SchemaMiner.mine requires at least one stimulus")
        targets = list(targets)
        if not targets:
            raise ValueError("SchemaMiner.mine requires at least one target")
        stimulus_hash = _content_hash_stimuli(stimuli)
        target_schemas: list[TargetSchema] = []
        for target in targets:
            target_schemas.append(self._mine_target(target, stimuli))
        kimera_commit = self.substrate.git_commit()
        return SchemaDocument(
            ophamin_version=__version__,
            ophamin_git_commit=capture_git_commit(_ophamin_project_root()),
            kimera_git_commit=kimera_commit or "",
            stimulus_set_hash=stimulus_hash,
            n_stimuli=len(stimuli),
            targets=tuple(target_schemas),
        )

    def _mine_target(self, target: str, stimuli: list[str]) -> TargetSchema:
        """Run every stimulus against one target, aggregate paths."""
        substrate = self._substrate_for_target(target)
        cycle_results = substrate.run_batch(stimuli)

        paths_seen: Counter[str] = Counter()
        types_per_path: dict[str, set[str]] = {}
        scalar_samples: dict[str, list[Any]] = {}
        list_lengths: dict[str, list[int]] = {}
        n_adapter_errors = 0
        n_cycles = len(cycle_results)

        for result in cycle_results:
            if result.halt_mode == "adapter_error":
                n_adapter_errors += 1
                continue
            flattened = _flatten(
                result.raw or {}, prefix="", depth=0, max_depth=self.max_depth
            )
            for path, value in flattened.items():
                if not path:
                    continue
                paths_seen[path] += 1
                types_per_path.setdefault(path, set()).add(_python_type_name(value))
                if isinstance(value, (list, tuple, set)):
                    list_lengths.setdefault(path, []).append(len(value))
                else:
                    samples = scalar_samples.setdefault(path, [])
                    summary = _summarise_value(value)
                    if summary not in samples and len(samples) < self.max_samples:
                        samples.append(summary)

        fields: list[FieldSchema] = []
        for path in sorted(paths_seen):
            types = tuple(sorted(types_per_path[path]))
            if path in list_lengths and path not in scalar_samples:
                lengths = list_lengths[path]
                # store the first ~max_samples *distinct* lengths, sorted
                distinct_lengths = sorted(set(lengths))[: self.max_samples]
                fields.append(
                    FieldSchema(
                        path=path,
                        types_seen=types,
                        occurrence_count=paths_seen[path],
                        n_cycles_target=n_cycles - n_adapter_errors,
                        sample_values=tuple(distinct_lengths),
                        sample_kind="lengths",
                    )
                )
            else:
                samples = tuple(scalar_samples.get(path, []))
                fields.append(
                    FieldSchema(
                        path=path,
                        types_seen=types,
                        occurrence_count=paths_seen[path],
                        n_cycles_target=n_cycles - n_adapter_errors,
                        sample_values=samples,
                        sample_kind="values",
                    )
                )

        target_class = self._target_class_name(target)
        return TargetSchema(
            name=target,
            target_class=target_class,
            n_cycles=n_cycles,
            n_adapter_errors=n_adapter_errors,
            fields=tuple(fields),
        )

    def _substrate_for_target(self, target: str) -> SubstrateUnderTest:
        """Return a substrate configured for the given target.

        For KimeraAdapter we rebind the target by constructing a fresh adapter
        with the same Kimera repo and the new target. For substrates without
        a switchable target (MockSubstrate), we use the substrate as-is —
        MockSubstrate is target-agnostic by design.
        """
        # KimeraAdapter exposes ``.kimera_repo`` + ``.mode`` + ``.batch_timeout``
        # + ``.python_exe`` and accepts a ``target`` kwarg. MockSubstrate
        # carries no ``kimera_repo`` attribute — getattr returns None and we
        # fall through to the original substrate. (This block is the load-
        # bearing target-rebind; an earlier version queried ``substrate.repo``
        # which doesn't exist on KimeraAdapter, silently kept every target on
        # the original substrate's target and produced duplicate fields across
        # every target in the schema — fixed 2026-05-15.)
        kimera_repo = getattr(self.substrate, "kimera_repo", None)
        if kimera_repo is not None:
            from ophamin.seeing.substrate import KimeraAdapter
            return KimeraAdapter(
                kimera_repo,
                python_exe=getattr(self.substrate, "python_exe", None),
                target=target,
                mode=getattr(self.substrate, "mode", "batch"),
                batch_timeout=getattr(self.substrate, "batch_timeout", 600.0),
            )
        return self.substrate

    def _target_class_name(self, target: str) -> str:
        """Best-effort fully-qualified class name for the target.

        Reads from the substrate's metadata if available; falls back to a
        placeholder so we never lie about an unknown class.
        """
        substrate = self._substrate_for_target(target)
        try:
            meta = substrate.metadata()
        except Exception:  # noqa: BLE001 — substrate may not expose metadata
            return "<unknown>"
        if isinstance(meta, dict):
            return str(meta.get("target_class", "<unknown>"))
        return "<unknown>"
