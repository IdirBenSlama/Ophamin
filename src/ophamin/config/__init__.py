"""Configuration injection and parameter sweeps (native, Hydra-compatible)."""

from ophamin.config.sweep import (
    SweepSpec,
    deep_merge,
    get_in,
    load_config,
    load_sweep,
    set_in,
)

__all__ = [
    "SweepSpec",
    "load_config",
    "load_sweep",
    "get_in",
    "set_in",
    "deep_merge",
]
