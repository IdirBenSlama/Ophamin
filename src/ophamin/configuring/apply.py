"""Owner-gated config write/apply for the Configure facet (CR5).

Everything else in Configure is read-only (schema / effective / snapshot /
validate). This module adds the ONE mutating capability — writing a proposed
config change to a ``.env``-style file Kimera reads — and gates it hard,
because applying a config change mutates the substrate:

  * **DRY-RUN by default.** :func:`plan_config_change` returns a diff +
    validation and writes NOTHING. Inspecting a change is always safe.
  * **OWNER-GATED apply.** :func:`apply_config_change` writes ONLY when the
    caller passes ``authorized=True`` AND the operator has set
    ``OPHAMIN_ALLOW_CONFIG_APPLY=1`` in the environment. Either missing → loud
    refusal (:class:`ConfigApplyNotAuthorized`). Defense in depth: a stray
    ``authorized=True`` can't apply without the operator's env gate, and the
    env gate alone can't apply without an intentional authorized call.
  * **VALIDATED before apply.** Proposed changes must reference known knobs,
    parse as their declared type, and the resulting effective config must pass
    :func:`~ophamin.configuring.validation.validate_config` with no ERROR. An
    invalid plan is not applicable.
  * **REVERSIBLE.** The prior file content is captured (hash + a ``.bak``
    sidecar) before the write, and recorded in the signed audit, so the owner
    can roll back.
  * **SECRET-SAFE.** Secret knobs are REFUSED — the plan marks them
    ``secret_refused`` and apply never writes or audits a secret value. The
    owner sets secrets manually; the tool never handles a credential.
  * **AUDITED.** Every apply emits a signed :class:`ConfigChangeAudit`
    (secret-safe) to the audit trail.

The target ``.env`` path is always explicit — this module never defaults to
writing inside the Kimera repo. The owner says where.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ophamin.configuring.schema import ConfigKnob
from ophamin.configuring.snapshot import config_snapshot, effective_config
from ophamin.configuring.validation import is_valid, validate_config

#: The operator's environment gate. Apply refuses unless this is exactly "1".
APPLY_GATE_ENV = "OPHAMIN_ALLOW_CONFIG_APPLY"

# entry statuses
_OK = "ok"
_NOOP = "noop"                  # proposed == current; nothing to do
_UNKNOWN = "unknown_knob"       # env var not in the schema
_TYPE_ERROR = "type_error"      # proposed value doesn't parse as the knob type
_SECRET_REFUSED = "secret_refused"  # secret knob — owner sets it manually


class ConfigApplyError(RuntimeError):
    """A config-apply precondition was violated (invalid plan, bad target)."""


class ConfigApplyNotAuthorized(ConfigApplyError):
    """Apply was attempted without BOTH the env gate and authorized=True."""


# --- planning (always safe, writes nothing) --------------------------------


@dataclass(frozen=True)
class ConfigChangeEntry:
    env_var: str
    current: str
    proposed: str
    value_type: str
    secret: bool
    status: str            # one of the _* statuses above

    def to_dict(self) -> dict[str, Any]:
        # secret-safe: never echo a secret's current/proposed value
        cur = "<secret>" if self.secret else self.current
        prop = "<secret>" if self.secret else self.proposed
        return {
            "env_var": self.env_var,
            "current": cur,
            "proposed": prop,
            "value_type": self.value_type,
            "secret": self.secret,
            "status": self.status,
        }


@dataclass(frozen=True)
class ConfigChangePlan:
    target_file: str
    entries: list[ConfigChangeEntry]
    validation: list[dict[str, Any]]   # ConfigViolation dicts on the result
    applicable: bool                   # all entries ok/noop AND validation clean

    def to_dict(self) -> dict[str, Any]:
        return {
            "target_file": self.target_file,
            "entries": [e.to_dict() for e in self.entries],
            "validation": self.validation,
            "applicable": self.applicable,
            "n_changes": sum(1 for e in self.entries if e.status == _OK),
            "n_refused": sum(
                1 for e in self.entries
                if e.status in (_UNKNOWN, _TYPE_ERROR, _SECRET_REFUSED)
            ),
        }


def _parses_as(value: str, value_type: str) -> bool:
    if value_type == "int":
        try:
            int(value)
        except ValueError:
            return False
        return True
    if value_type == "float":
        try:
            float(value)
        except ValueError:
            return False
        return True
    if value_type == "bool":
        return value.strip().lower() in ("true", "false")
    return True  # str accepts anything


def plan_config_change(
    schema: list[ConfigKnob],
    changes: dict[str, str],
    *,
    env_file: str,
) -> ConfigChangePlan:
    """Produce a dry-run plan for ``changes`` against ``schema``. Writes nothing.

    The tool MANAGES the ``.env`` file at ``env_file``, so "current" is read
    from that file (falling back to the schema default for knobs the file does
    not set) — NOT from ``os.environ``. This keeps the plan's diff coherent
    with what apply actually writes. Each proposed change is classified (ok /
    noop / unknown_knob / type_error / secret_refused). The resulting file
    config (file overlaid with the ok changes, over defaults) is validated; the
    plan is ``applicable`` iff every entry is ok/noop, validation has no ERROR,
    and there is at least one real change.
    """
    by_var = {k.env_var: k for k in schema}
    target = Path(env_file)
    file_env = (
        _parse_env_file(target.read_text(encoding="utf-8"))
        if target.exists() else {}
    )
    entries: list[ConfigChangeEntry] = []
    overlay: dict[str, str] = {}

    for var, proposed in changes.items():
        knob = by_var.get(var)
        current = file_env.get(var, knob.default if knob else "")
        if knob is None:
            status = _UNKNOWN
        elif knob.secret:
            status = _SECRET_REFUSED
        elif not _parses_as(proposed, knob.value_type):
            status = _TYPE_ERROR
        elif str(proposed) == str(current):
            status = _NOOP
        else:
            status = _OK
            overlay[var] = proposed
        entries.append(ConfigChangeEntry(
            env_var=var,
            current=current,
            proposed=proposed,
            value_type=knob.value_type if knob else "str",
            secret=bool(knob.secret) if knob else False,
            status=status,
        ))

    # Validate the resulting FILE config (file + ok overlay, over defaults).
    merged = {**file_env, **overlay}
    eff = effective_config(schema, env=merged)
    violations = validate_config(eff)
    refused = any(
        e.status in (_UNKNOWN, _TYPE_ERROR, _SECRET_REFUSED) for e in entries
    )
    applicable = (not refused) and is_valid(violations) and bool(overlay)
    return ConfigChangePlan(
        target_file=env_file,
        entries=entries,
        validation=[v.to_dict() for v in violations],
        applicable=applicable,
    )


# --- apply (owner-gated, mutating) -----------------------------------------


@dataclass(frozen=True)
class ConfigChangeAudit:
    audit_id: str
    target_file: str
    applied_at: str
    prior_content_hash: str
    new_content_hash: str
    before_snapshot_id: str
    after_snapshot_id: str
    changes: list[dict[str, Any]]      # secret-safe entry dicts (status == ok)
    backup_file: str
    signature: str = ""

    def _body(self) -> dict[str, Any]:
        return {
            "audit_id": self.audit_id,
            "target_file": self.target_file,
            "applied_at": self.applied_at,
            "prior_content_hash": self.prior_content_hash,
            "new_content_hash": self.new_content_hash,
            "before_snapshot_id": self.before_snapshot_id,
            "after_snapshot_id": self.after_snapshot_id,
            "changes": self.changes,
            "backup_file": self.backup_file,
        }

    def to_dict(self) -> dict[str, Any]:
        return {**self._body(), "signature": self.signature}

    def verify_signature(self, key: bytes) -> bool:
        if not self.signature:
            return False
        expected = hmac.new(
            key,
            json.dumps(self._body(), sort_keys=True, separators=(",", ":")).encode(),
            hashlib.sha256,
        ).hexdigest()
        return hmac.compare_digest(expected, self.signature)


def apply_authorized(authorized: bool, env: dict[str, str] | None = None) -> bool:
    """True iff BOTH the env gate is set to "1" AND ``authorized`` is True."""
    e = os.environ if env is None else env
    return bool(authorized) and e.get(APPLY_GATE_ENV, "").strip() == "1"


def _parse_env_file(text: str) -> dict[str, str]:
    out: dict[str, str] = {}
    for line in text.splitlines():
        s = line.strip()
        if not s or s.startswith("#") or "=" not in s:
            continue
        k, _, val = s.partition("=")
        out[k.strip()] = val
    return out


def _render_env_file(existing: dict[str, str], overlay: dict[str, str]) -> str:
    merged = {**existing, **overlay}
    lines = [f"{k}={merged[k]}" for k in sorted(merged)]
    return "\n".join(lines) + "\n"


def apply_config_change(
    plan: ConfigChangePlan,
    schema: list[ConfigKnob],
    *,
    authorized: bool,
    sign_key: bytes,
    audit_root: str | Path = "proofs/config_changes",
    gate_env: dict[str, str] | None = None,
) -> ConfigChangeAudit:
    """Apply an ``applicable`` plan to its target ``.env`` file. OWNER-GATED.

    Refuses (loud) unless :func:`apply_authorized` is True — i.e. ``authorized``
    is True AND ``gate_env`` (defaults to ``os.environ``) has
    ``OPHAMIN_ALLOW_CONFIG_APPLY=1``. Refuses a non-applicable plan. Writes a
    ``.bak`` of the prior file, applies the ok changes, and returns a signed
    :class:`ConfigChangeAudit` under ``audit_root``. Secret values are never
    read or written here (the plan already refused secret knobs). The before/
    after snapshots reflect the FILE config (file → file+overlay), consistent
    with the file-based plan; ``gate_env`` is ONLY the runtime authorization
    gate, never the config baseline.
    """
    if not apply_authorized(authorized, env=gate_env):
        raise ConfigApplyNotAuthorized(
            "config apply refused: requires BOTH authorized=True AND the "
            f"operator env gate {APPLY_GATE_ENV}=1. This mutates Kimera's "
            "config — it is owner-gated by design."
        )
    if not plan.applicable:
        raise ConfigApplyError(
            "plan is not applicable (refused entries or validation errors, or "
            "no real changes) — refusing to write. Inspect plan.to_dict()."
        )

    target = Path(plan.target_file)
    prior_text = target.read_text(encoding="utf-8") if target.exists() else ""
    prior_hash = hashlib.sha256(prior_text.encode("utf-8")).hexdigest()

    file_env = _parse_env_file(prior_text)
    overlay = {
        e.env_var: e.proposed for e in plan.entries if e.status == _OK
    }

    # before/after secret-safe snapshots reflect the FILE config (provenance)
    before_snap = config_snapshot(effective_config(schema, env=file_env))
    after_snap = config_snapshot(
        effective_config(schema, env={**file_env, **overlay})
    )

    new_text = _render_env_file(file_env, overlay)
    new_hash = hashlib.sha256(new_text.encode("utf-8")).hexdigest()

    applied_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    # backup BEFORE writing (reversibility)
    backup = ""
    if target.exists():
        backup = str(target) + f".bak.{applied_at.replace(':', '').replace('-', '')}"
        Path(backup).write_text(prior_text, encoding="utf-8")

    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(new_text, encoding="utf-8")

    audit_id = hashlib.sha256(
        f"{plan.target_file}|{prior_hash}|{new_hash}|{applied_at}".encode()
    ).hexdigest()
    audit = ConfigChangeAudit(
        audit_id=audit_id,
        target_file=str(target),
        applied_at=applied_at,
        prior_content_hash=prior_hash,
        new_content_hash=new_hash,
        before_snapshot_id=before_snap.snapshot_id,
        after_snapshot_id=after_snap.snapshot_id,
        changes=[e.to_dict() for e in plan.entries if e.status == _OK],
        backup_file=backup,
    )
    sig = hmac.new(
        sign_key,
        json.dumps(audit._body(), sort_keys=True, separators=(",", ":")).encode(),
        hashlib.sha256,
    ).hexdigest()
    audit = ConfigChangeAudit(**{**audit._body(), "signature": sig})

    root = Path(audit_root)
    root.mkdir(parents=True, exist_ok=True)
    (root / f"{applied_at.replace(':', '').replace('-', '')}_{audit_id[:12]}.json").write_text(
        json.dumps(audit.to_dict(), indent=2), encoding="utf-8"
    )
    return audit
