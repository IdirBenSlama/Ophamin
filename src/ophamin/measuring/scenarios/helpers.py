"""Scenario authoring helpers — Layer B foundation of Ophamin's co-evolution stack.

Every scenario today re-implements the same three pieces:

  - shape-aware field extraction (``_gwf_cleared``, ``_canonical``, ``_prime``,
    ``_dissonance_count``, ``_halt_mode``, ``_phi_value``) — already 5×
    duplicated across the 4 existing scenarios;
  - Wilson 95% CI computation (``proportion_confint(method="wilson")``) — 4×
    duplicated;
  - inconclusive guards (too few cleared, majority adapter errors) — 4×
    duplicated;
  - descriptive distribution statistics (median, mean, p10/p90, range).

A new scenario should be **a thin file** that picks its corpus + target +
threshold and assembles helpers — not a 300-LOC re-implementation. This
module is that thin-file substrate.

The pre-registration discipline is preserved exactly: every helper returns
plain values, never opinions. ``ScenarioScore`` and ``Claim`` construction
still happens in the scenario itself — these helpers are pure building blocks,
not a magic config-driven runner.

**Stability promise.** These extractors are shape-aware against the *live*
Kimera ``CycleResult.raw`` shape (verified 2026-05-15 against entity, rosetta,
gwf, walker, arachne targets). When Kimera's field names drift, the
discovery layer's schema-diff (``ophamin discover-diff``) surfaces the
change, and the helpers here get updated in one place rather than four.
"""

from __future__ import annotations

from statistics import mean, median
from typing import Any

from statsmodels.stats.proportion import proportion_confint

from ophamin.seeing.substrate.base import CycleResult


# --------------------------------------------------------------------------
# Field extractors — shape-aware against the real Kimera raw dict
# --------------------------------------------------------------------------


def gwf_cleared(result: CycleResult) -> bool:
    """Did Kimera's GWF clear this input?

    Recognised shapes (verified 2026-05-15 against the live entity target):
      - ``raw["gwf_lockdown"] is True``   → blocked (lockdown short-circuit)
      - ``raw["gwf_verdict"]`` startswith ``"blocked"`` or contains ``"lockdown"`` → blocked
      - ``raw["gwf_verdict"] == "cleared"`` or missing → cleared

    Failed cycles (``result.success is False``) are NOT cleared — they are
    measurement failures, not allowances.
    """
    if not result.success:
        return False
    raw = result.raw or {}
    if raw.get("gwf_lockdown") is True:
        return False
    verdict = str(raw.get("gwf_verdict", "")).strip().lower()
    if verdict.startswith("blocked") or "lockdown" in verdict:
        return False
    return True


def gwf_allowed_directly(result: CycleResult) -> bool | None:
    """Did the ``gwf`` *direct* target return ``allowed: True``?

    Distinct from ``gwf_cleared`` (which reads the entity target's flattened
    verdict). Returns None when the shape doesn't apply (no ``allowed`` key
    present).
    """
    if not result.success:
        return False
    raw = result.raw or {}
    if "allowed" in raw:
        return bool(raw["allowed"])
    return None


def halt_mode(result: CycleResult) -> str:
    """Normalised halt mode (lowercased, stripped) — empty string if absent."""
    return (result.halt_mode or "").strip().lower()


def manipulation_detected(result: CycleResult) -> bool:
    if not result.success:
        return False
    raw = result.raw or {}
    return raw.get("manipulation_detected") is True


def danger_theory_gated(result: CycleResult) -> bool:
    if not result.success:
        return False
    raw = result.raw or {}
    return raw.get("danger_theory_gated") is True


def dissonance_count(result: CycleResult) -> int:
    """Number of dissonance events raised this cycle (live ``dissonance_events`` list).

    Recognises three shapes:
      - ``raw["dissonance_events"]`` as a list  → ``len(list)``
      - ``raw["dissonance_event_count"]`` as an int → that int
      - ``raw["zetetic_contradictions"]`` as a list (symmetric fallback)
    """
    if not result.success:
        return 0
    raw = result.raw or {}
    events = raw.get("dissonance_events")
    if isinstance(events, list):
        return len(events)
    count = raw.get("dissonance_event_count")
    if isinstance(count, int):
        return count
    zet = raw.get("zetetic_contradictions")
    if isinstance(zet, list):
        return len(zet)
    return 0


def productive_dissonance_score(result: CycleResult) -> float:
    if not result.success:
        return 0.0
    raw = result.raw or {}
    value = raw.get("productive_dissonance_score")
    try:
        return float(value) if value is not None else 0.0
    except (TypeError, ValueError):
        return 0.0


def phi_value(result: CycleResult) -> float:
    """Φ (integrated information) value — searches the canonical field-name set."""
    if not result.success:
        return 0.0
    raw = result.raw or {}
    for key in ("phi_value", "phi", "Phi", "iit_phi"):
        value = raw.get(key)
        if value is None:
            continue
        try:
            return float(value)
        except (TypeError, ValueError):
            continue
    return 0.0


def rosetta_canonical(result: CycleResult) -> str | None:
    """The canonical address Rosetta returned, if any.

    Live ``RosettaStele.process`` returns ``raw["canonical"]`` directly;
    synthetic substrates may use ``canonical_form`` / ``canonical_key`` /
    ``canonical_concept``.
    """
    if not result.success:
        return None
    raw = result.raw or {}
    for key in (
        "canonical",
        "canonical_form",
        "canonical_key",
        "canonical_concept",
    ):
        value = raw.get(key)
        if value is not None:
            return str(value)
    return None


def rosetta_prime(result: CycleResult) -> int | None:
    """The composite prime Rosetta emitted.

    Two shapes:
      - live Kimera: ``raw["prime"]`` is a nested dict
        ``{"composite", "p_thermo", "p_identity", ...}`` → returns ``composite``;
      - synthetic substrates: ``raw["composite"]`` (or ``raw["prime"]``) is
        already a scalar.
    """
    if not result.success:
        return None
    raw = result.raw or {}
    nested = raw.get("prime")
    if isinstance(nested, dict):
        for nested_key in ("composite", "p_identity", "p_thermo"):
            value = nested.get(nested_key)
            if value is None:
                continue
            try:
                return int(value)
            except (TypeError, ValueError):
                continue
    for key in ("composite", "prime", "p_thermo"):
        value = raw.get(key)
        if value is None or isinstance(value, dict):
            continue
        try:
            return int(value)
        except (TypeError, ValueError):
            continue
    return None


def is_adapter_error(result: CycleResult) -> bool:
    """Is this cycle an Ophamin adapter error rather than a substrate result?

    Adapter errors are produced by ``KimeraAdapter`` on subprocess timeout /
    crash / serialisation failure — they MUST be excluded from binomial
    denominators since they aren't measurements of the substrate.
    """
    return halt_mode(result) == "adapter_error"


# --------------------------------------------------------------------------
# Statistical helpers — Wilson CI + distribution summaries
# --------------------------------------------------------------------------


def wilson_95_ci(successes: int, total: int) -> tuple[float | None, float | None]:
    """Wilson 95% CI for a binomial proportion. Returns (None, None) when total=0."""
    if not total:
        return None, None
    lo, hi = proportion_confint(successes, total, alpha=0.05, method="wilson")
    return float(lo), float(hi)


def distribution_stats(values: list[float | int]) -> dict[str, Any]:
    """Cheap descriptive stats — n, min/max/median/mean, p10/p90.

    Empty input returns a zero-shaped dict so downstream code never crashes
    on an absent secondary-evidence channel. The ``n`` field tells the reader
    whether the distribution was actually sampled.
    """
    if not values:
        return {
            "n": 0,
            "min": 0.0,
            "max": 0.0,
            "median": 0.0,
            "mean": 0.0,
            "p10": 0.0,
            "p90": 0.0,
        }
    sorted_v = sorted(float(v) for v in values)
    n = len(sorted_v)
    return {
        "n": n,
        "min": sorted_v[0],
        "max": sorted_v[-1],
        "median": float(median(sorted_v)),
        "mean": float(mean(sorted_v)),
        "p10": sorted_v[max(0, int(n * 0.10) - 1)],
        "p90": sorted_v[min(n - 1, int(n * 0.90))],
    }


# --------------------------------------------------------------------------
# Inconclusive guards — the boilerplate that every scenario re-implements
# --------------------------------------------------------------------------


def is_inconclusive(
    *,
    n_cycles: int,
    adapter_errors: int,
    n_denominator: int,
    min_denominator: int = 10,
) -> tuple[bool, str]:
    """The standard "should this run be marked inconclusive?" check.

    Returns ``(inconclusive, reason)``. Two failure modes are checked:

      1. ``n_denominator < min_denominator`` — too few cycles in the binomial
         denominator for a Wilson CI to mean anything (default floor = 10);
      2. ``adapter_errors > n_cycles // 2`` — the substrate wasn't actually
         exercised; majority of cycles were Ophamin-adapter failures.

    The first failure that fires wins; the reason string explains which one.
    Empty reason iff ``inconclusive`` is ``False``.
    """
    if n_cycles > 0 and adapter_errors > n_cycles // 2:
        return True, "substrate not exercised (majority adapter errors)"
    if n_denominator < min_denominator:
        return True, "too few cycles in denominator to decide"
    return False, ""
