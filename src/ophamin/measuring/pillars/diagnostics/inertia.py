"""Cognitive Inertia Metrics — the immune-system gap.

A hyper-secure substrate risks catastrophic rigidity. *Cognitive inertia* is a
system's resistance to changing its internal models despite receiving new,
*valid* evidence. If the defensive layer becomes dominant it entrenches
status-quo bias and rejects legitimate-but-novel data as malicious.

This meter quantifies the balance between defensive rejection and Bayesian
adaptation. Each observation is one valid-novel evidence event:

    evidence_strength  how strong / well-formed the new evidence is
    expected_shift     how far a correct Bayesian updater *should* move
    observed_shift     how far the substrate's internal model *actually* moved
    accepted           whether the substrate accepted (vs rejected) the evidence

Inertia near 1 means rigid (warranted updates not made); near 0 means plastic.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np


@dataclass
class _Event:
    evidence_strength: float
    expected_shift: float
    observed_shift: float
    accepted: bool


@dataclass
class InertiaReport:
    """Summary of the defensive-vs-adaptive balance over observed events."""

    n_events: int
    inertia_index: float            # 0 = fully plastic, 1 = fully rigid
    defensive_rejection_rate: float  # fraction of valid evidence rejected
    bayesian_adaptation_rate: float  # share of warranted update actually made
    balance: float                  # adaptation - rejection, in [-1, 1]
    stagnant: bool

    def summary(self) -> str:
        verdict = "STAGNANT" if self.stagnant else "adaptive"
        return (
            f"inertia[{verdict}]: index={self.inertia_index:.3f} "
            f"rejection_rate={self.defensive_rejection_rate:.3f} "
            f"adaptation_rate={self.bayesian_adaptation_rate:.3f} "
            f"balance={self.balance:+.3f} (n={self.n_events})"
        )


class CognitiveInertiaMeter:
    """Tracks a substrate's resistance to updating on valid new evidence."""

    def __init__(self, stagnant_threshold: float = 0.8) -> None:
        if not (0.0 <= stagnant_threshold <= 1.0):
            raise ValueError("stagnant_threshold must be in [0, 1]")
        self.stagnant_threshold = float(stagnant_threshold)
        self._events: list[_Event] = []

    def observe(
        self,
        evidence_strength: float,
        expected_shift: float,
        observed_shift: float,
        accepted: bool = True,
    ) -> None:
        """Record one valid-novel evidence event."""
        if evidence_strength < 0 or expected_shift < 0 or observed_shift < 0:
            raise ValueError("strengths and shifts must be non-negative")
        self._events.append(
            _Event(
                float(evidence_strength),
                float(expected_shift),
                float(observed_shift),
                bool(accepted),
            )
        )

    def report(self) -> InertiaReport:
        events = self._events
        n = len(events)
        if n == 0:
            return InertiaReport(0, 0.0, 0.0, 0.0, 0.0, False)

        # adaptation ratio per event: observed / expected, clipped to [0, 1].
        # events with no warranted shift (expected == 0) carry no inertia signal.
        ratios = []
        for e in events:
            if e.expected_shift > 0:
                ratios.append(min(1.0, e.observed_shift / e.expected_shift))
        adaptation = float(np.mean(ratios)) if ratios else 1.0
        inertia = 1.0 - adaptation

        rejected = sum(1 for e in events if not e.accepted)
        rejection_rate = rejected / n

        balance = adaptation - rejection_rate
        stagnant = inertia >= self.stagnant_threshold or rejection_rate >= self.stagnant_threshold

        return InertiaReport(
            n_events=n,
            inertia_index=inertia,
            defensive_rejection_rate=rejection_rate,
            bayesian_adaptation_rate=adaptation,
            balance=balance,
            stagnant=stagnant,
        )

    def reset(self) -> None:
        self._events.clear()
