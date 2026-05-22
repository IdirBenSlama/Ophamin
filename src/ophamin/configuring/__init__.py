"""Ophamin Configure facet — manage Kimera-SWM's configuration.

One of the horizontal platform's operational facets (alongside Manage,
Cockpit, Observatory, R&D). Introspects Kimera's env-var config contract
*statically from source* (no import, no run), resolves the effective config,
validates it against a config gate, and snapshots it for provenance — so an
empirical proof can record *which Kimera config produced it*, not just which
commit.

Public API:

- :func:`extract_config_schema` + :class:`ConfigKnob` — the live knob contract.
- :func:`effective_config` + :class:`EffectiveKnob` — current resolved values
  (secrets redacted).
- :func:`config_snapshot` + :class:`ConfigSnapshot` — secret-safe provenance hash.
- :func:`validate_config` + :func:`is_valid` + :class:`ConfigViolation` — the gate.
- :func:`plan_config_change` + :func:`apply_config_change` (CR5) — the ONE
  mutating capability, owner-gated: dry-run plan by default, apply only with
  ``authorized=True`` AND the ``OPHAMIN_ALLOW_CONFIG_APPLY=1`` env gate, with a
  reversible backup + signed audit. Everything else here is read-only.
"""

from __future__ import annotations

from ophamin.configuring.apply import (
    APPLY_GATE_ENV,
    ConfigApplyError,
    ConfigApplyNotAuthorized,
    ConfigChangeAudit,
    ConfigChangePlan,
    apply_authorized,
    apply_config_change,
    plan_config_change,
)
from ophamin.configuring.schema import ConfigKnob, extract_config_schema
from ophamin.configuring.snapshot import (
    ConfigSnapshot,
    EffectiveKnob,
    config_snapshot,
    effective_config,
)
from ophamin.configuring.validation import (
    ConfigViolation,
    is_valid,
    validate_config,
)

__all__ = [
    "ConfigKnob",
    "ConfigSnapshot",
    "ConfigViolation",
    "EffectiveKnob",
    "config_snapshot",
    "effective_config",
    "extract_config_schema",
    "is_valid",
    "validate_config",
    # apply surface (CR5, owner-gated)
    "APPLY_GATE_ENV",
    "ConfigApplyError",
    "ConfigApplyNotAuthorized",
    "ConfigChangeAudit",
    "ConfigChangePlan",
    "apply_authorized",
    "apply_config_change",
    "plan_config_change",
]
