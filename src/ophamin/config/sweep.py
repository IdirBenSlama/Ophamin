"""Configuration injection and parameter sweeps.

Config loading, merging and dotted access are delegated to **OmegaConf** — the
library underneath Hydra — which handles composition, type coercion and
interpolation. The framework's own thin layer is the sweep grid expansion (a
cartesian product), since Hydra performs multirun sweeps through its
CLI-owning ``@hydra.main`` entry point rather than as a plain library call.

Public helpers (``get_in`` / ``set_in`` / ``deep_merge``) keep their signatures
so the rest of the framework is unaffected, but each is now an OmegaConf call.
"""

from __future__ import annotations

import itertools
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from omegaconf import OmegaConf


def get_in(config: Any, dotted: str, default: Any = None) -> Any:
    """Read a nested value by dotted key (OmegaConf.select)."""
    cfg = config if OmegaConf.is_config(config) else OmegaConf.create(config)
    value = OmegaConf.select(cfg, dotted, default=default)
    if OmegaConf.is_config(value):
        return OmegaConf.to_container(value, resolve=True)
    return value


def _as_dict(obj: Any) -> dict[str, Any]:
    """Coerce an OmegaConf-to_container result to a dict (loud-fail if it isn't)."""
    if not isinstance(obj, dict):
        raise TypeError(
            f"expected a dict from OmegaConf.to_container, got {type(obj).__name__}"
        )
    return dict(obj)


def set_in(config: dict[str, Any], dotted: str, value: Any) -> None:
    """Write a nested value by dotted key, in place (OmegaConf.update)."""
    cfg = OmegaConf.create(config)
    OmegaConf.update(cfg, dotted, value, force_add=True)
    config.clear()
    config.update(_as_dict(OmegaConf.to_container(cfg, resolve=False)))


def deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    """Recursively merge ``override`` onto ``base`` (OmegaConf.merge).

    Neither input is mutated; the result shares no state with either.
    """
    merged = OmegaConf.merge(OmegaConf.create(base), OmegaConf.create(override))
    return _as_dict(OmegaConf.to_container(merged, resolve=True))


def _resolve_base_path(base: str, relative_to: Path) -> Path:
    """Find a ``base:`` reference — try cwd-relative, then config-dir, then project root."""
    candidates = [
        Path(base),
        relative_to.parent / base,
        relative_to.parent.parent / base,
    ]
    for c in candidates:
        if c.exists():
            return c
    raise FileNotFoundError(
        f"could not resolve base config '{base}' (tried: "
        f"{', '.join(str(c) for c in candidates)})"
    )


def load_config(path: str | Path) -> dict[str, Any]:
    """Load a YAML config via OmegaConf, resolving a ``base:`` reference if present.

    A config may declare ``base: <path>``; the loaded base is merged under the
    rest of the file (the file's own keys win).
    """
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"config not found: {path}")
    cfg = OmegaConf.load(path)
    if not OmegaConf.is_dict(cfg):
        raise ValueError(f"config {path} must be a mapping at the top level")
    base_ref = OmegaConf.select(cfg, "base", default=None)
    if base_ref:
        rest = OmegaConf.create(
            {k: v for k, v in cfg.items() if k != "base"}
        )
        base_cfg = OmegaConf.create(
            load_config(_resolve_base_path(str(base_ref), path))
        )
        merged = OmegaConf.merge(base_cfg, rest)
        return _as_dict(OmegaConf.to_container(merged, resolve=True))
    return _as_dict(OmegaConf.to_container(cfg, resolve=True))


@dataclass
class SweepSpec:
    """A parent experiment plus a parameter grid expanding into child configs."""

    base_config: dict[str, Any] = field(default_factory=dict)
    parent_name: str = "ophamin-experiment"
    parent_description: str = ""
    grid: dict[str, list[Any]] = field(default_factory=dict)
    stimuli: list[Any] = field(default_factory=list)
    diagnostics: dict[str, Any] = field(default_factory=dict)

    def points(self) -> list[dict[str, Any]]:
        """The list of ``{dotted_key: value}`` dicts — the cartesian product."""
        if not self.grid:
            return [{}]
        keys = list(self.grid)
        combos = itertools.product(*(self.grid[k] for k in keys))
        return [dict(zip(keys, values)) for values in combos]

    def expand(self) -> list[tuple[dict[str, Any], dict[str, Any]]]:
        """Expand the grid into ``(child_config, sweep_point)`` pairs (OmegaConf-built)."""
        out: list[tuple[dict[str, Any], dict[str, Any]]] = []
        for point in self.points():
            cfg = OmegaConf.create(self.base_config)
            for dotted, value in point.items():
                OmegaConf.update(cfg, dotted, value, force_add=True)
            out.append((_as_dict(OmegaConf.to_container(cfg, resolve=True)), point))
        return out

    def __len__(self) -> int:
        return len(self.points())


def load_sweep(path: str | Path) -> SweepSpec:
    """Load a sweep definition (e.g. ``config/experiment_vars.yaml``)."""
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"sweep config not found: {path}")
    raw = OmegaConf.load(path)
    if not OmegaConf.is_dict(raw):
        raise ValueError(f"sweep config {path} must be a mapping at the top level")

    base_ref = OmegaConf.select(raw, "base", default=None)
    base_config = (
        load_config(_resolve_base_path(str(base_ref), path)) if base_ref else {}
    )

    parent = _as_dict(OmegaConf.to_container(
        OmegaConf.select(raw, "parent_experiment", default=OmegaConf.create({})),
        resolve=True,
    ))
    grid_cfg = OmegaConf.select(raw, "sweep", default=OmegaConf.create({}))
    grid_raw = OmegaConf.to_container(grid_cfg, resolve=True) or {}
    grid: dict[str, list[Any]] = _as_dict(grid_raw)
    for k, v in grid.items():
        if not isinstance(v, list) or not v:
            raise ValueError(f"sweep key '{k!s}' must map to a non-empty list")

    stimuli_cfg = OmegaConf.select(raw, "stimuli", default=None)
    stimuli: list[Any] = []
    if stimuli_cfg is not None:
        stimuli_spec = OmegaConf.to_container(stimuli_cfg, resolve=True)
        if isinstance(stimuli_spec, list):
            stimuli = list(stimuli_spec)
        elif isinstance(stimuli_spec, dict):
            source = stimuli_spec.get("source", "inline")
            if source == "inline":
                stimuli = list(stimuli_spec.get("items", []))
            elif source == "file":
                corpus = Path(stimuli_spec["path"])
                if not corpus.exists():
                    raise FileNotFoundError(f"stimuli corpus not found: {corpus}")
                stimuli = [
                    line
                    for line in corpus.read_text(encoding="utf-8").splitlines()
                    if line.strip()
                ]
            else:
                raise ValueError(f"unknown stimuli source: {source!r}")

    diagnostics = _as_dict(OmegaConf.to_container(
        OmegaConf.select(raw, "diagnostics", default=OmegaConf.create({})),
        resolve=True,
    ))

    return SweepSpec(
        base_config=base_config,
        parent_name=str(parent.get("name", "ophamin-experiment")),
        parent_description=str(parent.get("description", "")),
        grid=grid,
        stimuli=stimuli,
        diagnostics=diagnostics or {},
    )
