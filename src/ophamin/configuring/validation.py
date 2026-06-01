"""The config gate — validate a Kimera effective config.

The same discipline as the authoring grounding gate and the reporting
conformance gate, applied to Kimera's *configuration*: every knob's value
must parse as its declared type, and a config declared ``production`` must
not ship dev-only / unsafe settings (empty DB password, debug on, reload
on, a bind-all server host). Violations are structured + actionable; never
raised.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from ophamin.configuring.snapshot import EffectiveKnob

ERROR = "error"
WARN = "warn"


@dataclass(frozen=True)
class ConfigViolation:
    env_var: str
    code: str
    severity: str
    message: str
    fix: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "env_var": self.env_var,
            "code": self.code,
            "severity": self.severity,
            "message": self.message,
            "fix": self.fix,
        }


def _by_var(effective: list[EffectiveKnob]) -> dict[str, EffectiveKnob]:
    return {k.env_var: k for k in effective}


def validate_config(effective: list[EffectiveKnob]) -> list[ConfigViolation]:
    """Validate an effective config. Empty list = clean."""
    v: list[ConfigViolation] = []
    by_var = _by_var(effective)

    # 1. Type integrity: every non-secret value must parse as its type.
    for k in effective:
        if k.secret:
            continue
        if k.value_type == "int" and not isinstance(k.current, int):
            v.append(ConfigViolation(
                k.env_var, "type_mismatch", ERROR,
                f"{k.env_var}={k.current!r} is not a valid int.",
                "Set an integer value."))
        elif k.value_type == "float" and not isinstance(k.current, (int, float)):
            v.append(ConfigViolation(
                k.env_var, "type_mismatch", ERROR,
                f"{k.env_var}={k.current!r} is not a valid float.",
                "Set a numeric value."))

    # 2. Production safety: a production config must not ship dev defaults.
    env_knob = by_var.get("KIMERA_ENVIRONMENT")
    is_production = env_knob is not None and str(env_knob.current).lower() == "production"
    if is_production:
        pw = by_var.get("KIMERA_DB_PASSWORD")
        if pw is not None and pw.current == "<unset>":
            v.append(ConfigViolation(
                "KIMERA_DB_PASSWORD", "empty_secret_in_production", ERROR,
                "Production config has no database password set.",
                "Set KIMERA_DB_PASSWORD in the production environment."))
        debug = by_var.get("KIMERA_DEBUG")
        if debug is not None and debug.current is True:
            v.append(ConfigViolation(
                "KIMERA_DEBUG", "debug_on_in_production", ERROR,
                "Debug mode is ON in a production config.",
                "Set KIMERA_DEBUG=false for production."))
        reload_ = by_var.get("KIMERA_API_RELOAD")
        if reload_ is not None and reload_.current is True:
            v.append(ConfigViolation(
                "KIMERA_API_RELOAD", "reload_on_in_production", WARN,
                "API auto-reload is ON in a production config.",
                "Set KIMERA_API_RELOAD=false for production."))
        host = by_var.get("KIMERA_SERVER_HOST")
        if host is not None and str(host.current) == "0.0.0.0":  # noqa: S104  # nosec B104 — not a real bind-all (host comparison / validation warning); serve defaults to 127.0.0.1
            v.append(ConfigViolation(
                "KIMERA_SERVER_HOST", "bind_all_in_production", WARN,
                "Server binds all interfaces (0.0.0.0) in production.",
                "Bind a specific interface unless a fronting proxy is intended."))

    return v


def is_valid(violations: list[ConfigViolation]) -> bool:
    """True iff no ERROR-severity violations."""
    return not any(x.severity == ERROR for x in violations)
