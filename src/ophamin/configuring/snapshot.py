"""The effective Kimera config + a provenance snapshot.

``effective_config`` resolves each knob to its current value (the env
override, or the schema default) — redacting secrets. ``config_snapshot``
produces a content-hashed, secret-safe snapshot that can be attached to a
proof as a provenance dimension: *which Kimera config produced this result*,
alongside the substrate git commit. Two runs with the same snapshot hash
were configured identically (secrets compared only as set/unset, never by
value).
"""

from __future__ import annotations

import hashlib
import json
import os
from dataclasses import dataclass
from typing import Any

from ophamin.configuring.schema import ConfigKnob

_REDACTED = "<redacted>"
_SET = "<set>"
_UNSET = "<unset>"


def _cast(value: str, value_type: str) -> Any:
    if value_type == "int":
        try:
            return int(value)
        except ValueError:
            return value
    if value_type == "float":
        try:
            return float(value)
        except ValueError:
            return value
    if value_type == "bool":
        return value.strip().lower() == "true"
    return value


@dataclass(frozen=True)
class EffectiveKnob:
    """One knob resolved to its current effective value."""

    env_var: str
    group: str
    value_type: str
    default: str
    current: Any            # redacted for secrets
    is_default: bool        # True if no env override
    secret: bool

    def to_dict(self) -> dict[str, Any]:
        return {
            "env_var": self.env_var,
            "group": self.group,
            "value_type": self.value_type,
            "default": _REDACTED if self.secret else self.default,
            "current": self.current,
            "is_default": self.is_default,
            "secret": self.secret,
        }


def effective_config(
    schema: list[ConfigKnob], env: dict[str, str] | None = None,
) -> list[EffectiveKnob]:
    """Resolve every knob to its current effective value.

    ``env`` defaults to ``os.environ``. Secrets are redacted in ``current``
    (the snapshot records only whether they're set).
    """
    e = os.environ if env is None else env
    out: list[EffectiveKnob] = []
    for k in schema:
        raw = e.get(k.env_var)
        is_default = raw is None
        value = k.default if raw is None else raw
        if k.secret:
            current: Any = _UNSET if value == "" else _SET
        else:
            current = _cast(value, k.value_type)
        out.append(EffectiveKnob(
            env_var=k.env_var, group=k.group, value_type=k.value_type,
            default=k.default, current=current, is_default=is_default,
            secret=k.secret,
        ))
    return out


@dataclass(frozen=True)
class ConfigSnapshot:
    """A secret-safe, content-hashed snapshot of an effective config."""

    snapshot_id: str        # sha256 over the canonical secret-safe payload
    n_knobs: int
    n_overridden: int       # how many differ from default (env-set)
    groups: dict[str, int]  # knob count per group
    payload: dict[str, Any] # the canonical secret-safe payload (for audit)

    def to_dict(self) -> dict[str, Any]:
        return {
            "snapshot_id": self.snapshot_id,
            "n_knobs": self.n_knobs,
            "n_overridden": self.n_overridden,
            "groups": self.groups,
            "payload": self.payload,
        }


def config_snapshot(effective: list[EffectiveKnob]) -> ConfigSnapshot:
    """Content-hash the effective config into a provenance snapshot.

    The hashed payload is secret-safe: a secret contributes only ``<set>`` /
    ``<unset>``, never its value. Two identical setups (same non-secret
    values + same secrets-set pattern) produce the same ``snapshot_id``.
    """
    payload: dict[str, Any] = {}
    groups: dict[str, int] = {}
    n_overridden = 0
    for k in sorted(effective, key=lambda x: x.env_var):
        payload[k.env_var] = k.current  # already redacted for secrets
        groups[k.group] = groups.get(k.group, 0) + 1
        if not k.is_default:
            n_overridden += 1
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    snapshot_id = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
    return ConfigSnapshot(
        snapshot_id=snapshot_id,
        n_knobs=len(effective),
        n_overridden=n_overridden,
        groups=groups,
        payload=payload,
    )
