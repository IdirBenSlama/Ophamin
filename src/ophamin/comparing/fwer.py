"""Multiplicity correction for campaign-level verdict aggregation.

When a campaign runs N scenarios, each producing an independent
hypothesis test at level α, the family-wise error rate climbs: at N=19
scenarios and α=0.05, the probability of at least one spurious
VALIDATED is roughly ``1 − (1 − 0.05) ** 19 ≈ 0.62``. A methods
reviewer flags this on first read.

This module implements two corrections, both as **pure functions** of a
sequence of :class:`CorrectionInput` records:

* :func:`holm_bonferroni` — Holm's step-down procedure. Strictly
  controls family-wise error rate (FWER). Reference: Holm (1979),
  *A Simple Sequentially Rejective Multiple Test Procedure*,
  Scandinavian Journal of Statistics 6(2), 65–70.
  DOI `10.2307/4615733 <https://doi.org/10.2307/4615733>`_.

* :func:`benjamini_hochberg` — the BH step-up procedure. Controls
  false-discovery rate (FDR), which is the expected proportion of
  false positives among all rejections. Less conservative than Holm
  when many tests are expected to reject. Reference: Benjamini &
  Hochberg (1995), *Controlling the False Discovery Rate*, Journal of
  the Royal Statistical Society B 57(1), 289–300.
  DOI `10.1111/j.2517-6161.1995.tb02031.x
  <https://doi.org/10.1111/j.2517-6161.1995.tb02031.x>`_.

Both functions are deterministic, side-effect-free, and use only
standard library — they intentionally do NOT depend on statsmodels so
they can run inside the campaign aggregation pass without pulling the
full ``[stats]`` extra.

Inputs that carry ``p_value is None`` (the framework's
:class:`PillarEvidence` allows this for non-frequentist scenarios)
pass through with ``corrected_p_value = None`` and
``significant_after_correction = False``; their ``corrected_verdict``
is the raw verdict unchanged. They count toward the family size for
the others (a conservative choice — including them does not weaken
the FWER guarantee but may under-power the BH procedure).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Sequence

from ophamin._stability import Stable


# --- typed inputs / outputs -------------------------------------------------


@Stable(since="0.9.0")
@dataclass(frozen=True)
class CorrectionInput:
    """One claim's raw verdict + its representative p-value.

    The aggregator emits one :class:`CorrectionInput` per signed proof
    record. If a record has multiple pillars with p-values, take the
    **minimum** p-value across the record's pillars before calling the
    correction (Bonferroni-within-record; conservative). The
    :func:`corrections_from_records` helper in :mod:`ophamin.campaign`
    handles this projection.

    Attributes:
        claim_id: stable identifier — typically the ``proof_id`` of the
            originating signed record, or another deterministic string
            (scenario_name + commit) when proof_id isn't yet assigned.
        raw_verdict: one of ``VALIDATED`` / ``REFUTED`` / ``INCONCLUSIVE``
            (the same string set as :data:`ophamin.measuring.proof.record._OUTCOMES`).
        p_value: in [0, 1]. ``None`` means the underlying claim has no
            frequentist p-value to correct; the record passes through
            unchanged but still counts toward the family size.
    """

    claim_id: str
    raw_verdict: str
    p_value: float | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.claim_id, str) or not self.claim_id:
            raise ValueError("claim_id must be a non-empty string")
        if not isinstance(self.raw_verdict, str) or not self.raw_verdict:
            raise ValueError("raw_verdict must be a non-empty string")
        if self.p_value is not None:
            if not isinstance(self.p_value, (int, float)):
                raise TypeError("p_value must be a real number or None")
            if not (0.0 <= float(self.p_value) <= 1.0):
                raise ValueError(
                    f"p_value must lie in [0, 1], got {self.p_value!r}"
                )


@Stable(since="0.9.0")
@dataclass(frozen=True)
class CorrectionResult:
    """One claim's corrected verdict + bookkeeping.

    Attributes:
        claim_id: echo of the input identifier.
        raw_verdict: echo of the input verdict.
        corrected_verdict: ``raw_verdict`` if the test remains significant
            after correction, OR ``"INCONCLUSIVE"`` if a raw VALIDATED
            failed to survive the correction. Raw REFUTED and INCONCLUSIVE
            pass through unchanged — correction can only *demote*
            VALIDATED into INCONCLUSIVE, not the other way around.
        raw_p_value: echo of the input p_value (``None`` if absent).
        corrected_p_value: the monotonized corrected p-value. ``None``
            iff ``raw_p_value`` was ``None``.
        method: ``"holm"`` / ``"bh"`` / ``"none"``.
        alpha: the family-wise / FDR threshold used.
        family_size: total number of records in the correction family
            (including p_value=None passthroughs).
        significant_after_correction: ``True`` iff
            ``corrected_p_value is not None and corrected_p_value <= alpha``.
    """

    claim_id: str
    raw_verdict: str
    corrected_verdict: str
    raw_p_value: float | None
    corrected_p_value: float | None
    method: str
    alpha: float
    family_size: int
    significant_after_correction: bool


@Stable(since="0.9.0")
@dataclass(frozen=True)
class CorrectionFamily:
    """Aggregate view of one correction pass.

    Returned by the convenience helpers and easy to serialise into the
    CampaignRecord's ``corrected_verdicts`` field.

    Attributes:
        method: ``"holm"`` / ``"bh"`` / ``"none"``.
        alpha: the threshold used.
        family_size: ``len(results)``.
        n_with_p_value: how many family members had a non-``None`` p-value.
        n_rejections: how many family members had
            ``significant_after_correction = True``.
        results: per-input outcomes.
    """

    method: str
    alpha: float
    family_size: int
    n_with_p_value: int
    n_rejections: int
    results: tuple[CorrectionResult, ...] = field(default_factory=tuple)

    def verdicts(self) -> dict[str, str]:
        """Project to a ``{claim_id → corrected_verdict}`` mapping.

        Suitable for direct assignment to
        :attr:`ophamin.campaign.CampaignRecord.corrected_verdicts`.
        """
        return {r.claim_id: r.corrected_verdict for r in self.results}


# --- supported methods ------------------------------------------------------

SUPPORTED_METHODS: frozenset[str] = frozenset({"holm", "bh", "none"})


# --- core algorithms --------------------------------------------------------


def _demote(raw_verdict: str, significant: bool) -> str:
    """Return the corrected verdict.

    Raw VALIDATED becomes INCONCLUSIVE if the test fails to survive
    correction. Everything else (REFUTED, INCONCLUSIVE, or any other
    string a future scenario emits) passes through unchanged.
    """
    if raw_verdict == "VALIDATED" and not significant:
        return "INCONCLUSIVE"
    return raw_verdict


def _split_with_pvalues(
    inputs: Sequence[CorrectionInput],
) -> tuple[list[tuple[int, CorrectionInput]], list[tuple[int, CorrectionInput]]]:
    """Partition into (with-p-value, without-p-value) preserving input order.

    Each element is ``(original_index, input)``.
    """
    with_p: list[tuple[int, CorrectionInput]] = []
    without_p: list[tuple[int, CorrectionInput]] = []
    for idx, inp in enumerate(inputs):
        if inp.p_value is None:
            without_p.append((idx, inp))
        else:
            with_p.append((idx, inp))
    return with_p, without_p


def _emit_passthrough(
    idx: int,
    inp: CorrectionInput,
    *,
    method: str,
    alpha: float,
    family_size: int,
) -> tuple[int, CorrectionResult]:
    """Emit a passthrough result for an input with ``p_value=None``."""
    return (
        idx,
        CorrectionResult(
            claim_id=inp.claim_id,
            raw_verdict=inp.raw_verdict,
            corrected_verdict=inp.raw_verdict,  # passthrough — no demotion
            raw_p_value=None,
            corrected_p_value=None,
            method=method,
            alpha=alpha,
            family_size=family_size,
            significant_after_correction=False,
        ),
    )


@Stable(since="0.9.0")
def holm_bonferroni(
    inputs: Sequence[CorrectionInput],
    *,
    alpha: float = 0.05,
) -> CorrectionFamily:
    """Holm-Bonferroni step-down correction. Strictly controls FWER.

    Algorithm (Holm 1979):

    1. Sort p-values ascending: p_(1) ≤ p_(2) ≤ ... ≤ p_(n).
    2. The corrected p-value for the j-th smallest is
       ``p̃_(j) = max{ (n − j + 1) * p_(j), p̃_(j−1), p_(j) }``
       clipped to ``[0, 1]``. The ``p̃_(j−1)`` term enforces
       monotonicity (the step-down property); the ``p_(j)`` floor
       guards against the corrected value going below the raw value.
    3. Reject H_0_(j) iff ``p̃_(j) ≤ α``.

    Args:
        inputs: the family of records to correct. Order is preserved
            in the output ``results`` tuple.
        alpha: family-wise error rate, in (0, 1]. Default 0.05.

    Returns:
        A :class:`CorrectionFamily` with one
        :class:`CorrectionResult` per input.

    Raises:
        ValueError: if ``alpha`` is not in (0, 1] or any input
            violates the :class:`CorrectionInput` invariants (those
            checks fire at input-construction time, not here).
    """
    if not (0.0 < alpha <= 1.0):
        raise ValueError(f"alpha must lie in (0, 1], got {alpha!r}")
    n = len(inputs)
    with_p, without_p = _split_with_pvalues(inputs)
    m = len(with_p)

    indexed_results: list[tuple[int, CorrectionResult]] = []

    # Sort the with-p-value subset by p_value ascending, break ties by
    # original index for determinism.
    sorted_with_p = sorted(with_p, key=lambda t: (t[1].p_value, t[0]))

    running_max = 0.0
    for j_zero, (orig_idx, inp) in enumerate(sorted_with_p):
        j = j_zero + 1  # 1-based rank
        raw_p = float(inp.p_value)  # type: ignore[arg-type]
        # Holm's step-down adjusted p-value.
        candidate = (m - j + 1) * raw_p
        # Monotonize against the running max so far AND don't go below raw.
        adjusted = max(candidate, running_max, raw_p)
        # Clip to [0, 1].
        adjusted = min(adjusted, 1.0)
        running_max = adjusted
        significant = adjusted <= alpha
        indexed_results.append(
            (
                orig_idx,
                CorrectionResult(
                    claim_id=inp.claim_id,
                    raw_verdict=inp.raw_verdict,
                    corrected_verdict=_demote(inp.raw_verdict, significant),
                    raw_p_value=raw_p,
                    corrected_p_value=adjusted,
                    method="holm",
                    alpha=alpha,
                    family_size=n,
                    significant_after_correction=significant,
                ),
            )
        )

    for orig_idx, inp in without_p:
        indexed_results.append(
            _emit_passthrough(orig_idx, inp, method="holm", alpha=alpha, family_size=n)
        )

    # Sort back into the original input order.
    indexed_results.sort(key=lambda t: t[0])
    results = tuple(r for _, r in indexed_results)
    n_rejections = sum(1 for r in results if r.significant_after_correction)
    return CorrectionFamily(
        method="holm",
        alpha=alpha,
        family_size=n,
        n_with_p_value=m,
        n_rejections=n_rejections,
        results=results,
    )


@Stable(since="0.9.0")
def benjamini_hochberg(
    inputs: Sequence[CorrectionInput],
    *,
    alpha: float = 0.05,
) -> CorrectionFamily:
    """Benjamini-Hochberg step-up correction. Controls FDR.

    Algorithm (Benjamini & Hochberg 1995):

    1. Sort p-values ascending: p_(1) ≤ p_(2) ≤ ... ≤ p_(m).
    2. The corrected p-value for the j-th smallest is
       ``p̃_(j) = min{ p_(j) * m / j, p̃_(j+1) }`` clipped to
       ``[0, 1]``. The ``p̃_(j+1)`` term enforces monotonicity
       (the step-up property — moving from largest p down to smallest).
    3. Reject H_0_(j) iff ``p̃_(j) ≤ α``.

    Args:
        inputs: the family of records to correct.
        alpha: FDR threshold, in (0, 1]. Default 0.05.

    Returns:
        A :class:`CorrectionFamily` with one
        :class:`CorrectionResult` per input.

    Raises:
        ValueError: if ``alpha`` is not in (0, 1].
    """
    if not (0.0 < alpha <= 1.0):
        raise ValueError(f"alpha must lie in (0, 1], got {alpha!r}")
    n = len(inputs)
    with_p, without_p = _split_with_pvalues(inputs)
    m = len(with_p)

    indexed_results: list[tuple[int, CorrectionResult]] = []
    sorted_with_p = sorted(with_p, key=lambda t: (t[1].p_value, t[0]))

    # Two-pass: compute raw BH adjusted p first, then monotonize step-up.
    raw_adjusted: list[float] = []
    for j_zero, (_, inp) in enumerate(sorted_with_p):
        j = j_zero + 1
        raw_p = float(inp.p_value)  # type: ignore[arg-type]
        candidate = raw_p * m / j if m > 0 else raw_p
        raw_adjusted.append(min(candidate, 1.0))

    # Monotonize step-up: walking from largest p down, each adjusted
    # value is the minimum of itself and the one above it.
    monotone = list(raw_adjusted)
    for k in range(len(monotone) - 2, -1, -1):
        if monotone[k + 1] < monotone[k]:
            monotone[k] = monotone[k + 1]

    for j_zero, (orig_idx, inp) in enumerate(sorted_with_p):
        raw_p = float(inp.p_value)  # type: ignore[arg-type]
        adjusted = monotone[j_zero]
        significant = adjusted <= alpha
        indexed_results.append(
            (
                orig_idx,
                CorrectionResult(
                    claim_id=inp.claim_id,
                    raw_verdict=inp.raw_verdict,
                    corrected_verdict=_demote(inp.raw_verdict, significant),
                    raw_p_value=raw_p,
                    corrected_p_value=adjusted,
                    method="bh",
                    alpha=alpha,
                    family_size=n,
                    significant_after_correction=significant,
                ),
            )
        )

    for orig_idx, inp in without_p:
        indexed_results.append(
            _emit_passthrough(orig_idx, inp, method="bh", alpha=alpha, family_size=n)
        )

    indexed_results.sort(key=lambda t: t[0])
    results = tuple(r for _, r in indexed_results)
    n_rejections = sum(1 for r in results if r.significant_after_correction)
    return CorrectionFamily(
        method="bh",
        alpha=alpha,
        family_size=n,
        n_with_p_value=m,
        n_rejections=n_rejections,
        results=results,
    )


@Stable(since="0.9.0")
def no_correction(
    inputs: Sequence[CorrectionInput],
    *,
    alpha: float = 0.05,
) -> CorrectionFamily:
    """Identity transform — no correction applied.

    Returned for the ``"none"`` method case. Each record's
    ``corrected_verdict`` equals its ``raw_verdict``; the
    ``significant_after_correction`` flag uses the raw p-value
    directly against alpha (no adjustment).

    Useful for: campaign aggregations where the operator explicitly
    wants the uncorrected view, OR where the family size is 1 (no
    multiplicity to correct).
    """
    if not (0.0 < alpha <= 1.0):
        raise ValueError(f"alpha must lie in (0, 1], got {alpha!r}")
    n = len(inputs)
    m = sum(1 for i in inputs if i.p_value is not None)
    results: list[CorrectionResult] = []
    n_rejections = 0
    for inp in inputs:
        if inp.p_value is None:
            results.append(
                CorrectionResult(
                    claim_id=inp.claim_id,
                    raw_verdict=inp.raw_verdict,
                    corrected_verdict=inp.raw_verdict,
                    raw_p_value=None,
                    corrected_p_value=None,
                    method="none",
                    alpha=alpha,
                    family_size=n,
                    significant_after_correction=False,
                )
            )
        else:
            raw_p = float(inp.p_value)
            significant = raw_p <= alpha
            n_rejections += int(significant)
            results.append(
                CorrectionResult(
                    claim_id=inp.claim_id,
                    raw_verdict=inp.raw_verdict,
                    corrected_verdict=inp.raw_verdict,
                    raw_p_value=raw_p,
                    corrected_p_value=raw_p,
                    method="none",
                    alpha=alpha,
                    family_size=n,
                    significant_after_correction=significant,
                )
            )
    return CorrectionFamily(
        method="none",
        alpha=alpha,
        family_size=n,
        n_with_p_value=m,
        n_rejections=n_rejections,
        results=tuple(results),
    )


# --- dispatcher -------------------------------------------------------------


@Stable(since="0.9.0", notes="Dispatcher; chooses Holm / BH / no-op by method string.")
def apply_correction(
    inputs: Sequence[CorrectionInput],
    *,
    method: str = "holm",
    alpha: float = 0.05,
) -> CorrectionFamily:
    """Dispatch to the requested correction.

    Args:
        inputs: the family to correct.
        method: one of :data:`SUPPORTED_METHODS`.
        alpha: passed through to the underlying method.

    Returns:
        A :class:`CorrectionFamily` from the dispatched method.

    Raises:
        ValueError: if ``method`` is not in :data:`SUPPORTED_METHODS`.
    """
    if method not in SUPPORTED_METHODS:
        raise ValueError(
            f"method must be one of {sorted(SUPPORTED_METHODS)}, got {method!r}"
        )
    if method == "holm":
        return holm_bonferroni(inputs, alpha=alpha)
    if method == "bh":
        return benjamini_hochberg(inputs, alpha=alpha)
    return no_correction(inputs, alpha=alpha)


__all__ = [
    "CorrectionInput",
    "CorrectionResult",
    "CorrectionFamily",
    "SUPPORTED_METHODS",
    "apply_correction",
    "holm_bonferroni",
    "benjamini_hochberg",
    "no_correction",
]
