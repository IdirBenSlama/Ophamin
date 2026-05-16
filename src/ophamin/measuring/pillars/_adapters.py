"""Pillar-Protocol adapters for every shipped pillar (Move G).

One thin adapter per pillar module, each:

- declares ``pillar_name`` (OFAMIN-style identifier),
- declares ``library`` (the upstream package the pillar delegates to),
- resolves ``library_version`` via :func:`_pkg_version` at import time,
- exposes a ``compute(cycle_results, records=None, **kwargs)`` method
  that either does best-effort work OR raises
  :class:`NonUniformComputeError` pointing at the module's canonical
  API.

Every adapter is registered with :data:`ophamin.registry.PILLARS` at
module import time. Each scenario / discovery surface that wants the
metadata (library attribution, version, count) reads from the
registry rather than from any specific pillar module.

Eleven adapters in canonical OFAMIN + diagnostics order:

  O.spc                       observability/spc.py
  O.srm                       observability/srm.py
  O.drift                     observability/drift.py
  A.sprt                      adaptive/sprt.py
  M.mixed_effects             effects/mixed_effects.py
  M.mea                       effects/mea.py
  I.cma                       synthesis/cma.py
  N.cross_validation          robustness/cross_validation.py
  diagnostics.anticipatory    diagnostics/anticipatory.py
  diagnostics.inertia         diagnostics/inertia.py
  diagnostics.kernel_coupling diagnostics/kernel_coupling.py
"""

from __future__ import annotations

from typing import Any, Iterable

from ophamin.measuring.pillars.base import (
    NonUniformComputeError,
    PillarBase,
    _pkg_version,
)


# --- O · Observability ------------------------------------------------------


class SPCPillar(PillarBase):
    """Shewhart Statistical Process Control — control charts + Western
    Electric special-cause rules.

    Canonical API: :class:`IndividualsChart` / :class:`XbarRChart` /
    :func:`western_electric_rules` in
    ``ophamin.measuring.pillars.observability.spc``.
    """

    pillar_name = "O.spc"
    library = "numpy"
    library_version = _pkg_version("numpy")

    def compute(
        self,
        cycle_results: Iterable[Any],
        records: Iterable[Any] | None = None,
        **kwargs: Any,
    ) -> Any:
        raise NonUniformComputeError(
            "SPC operates on a numeric subgroup stream; call "
            "ophamin.measuring.pillars.observability.spc.IndividualsChart "
            "(or XbarRChart) directly with your fitted values."
        )


class SRMPillar(PillarBase):
    """Sample Ratio Mismatch — scipy chi-squared goodness-of-fit.

    Canonical API: :class:`SRMDetector` in
    ``ophamin.measuring.pillars.observability.srm``.
    """

    pillar_name = "O.srm"
    library = "scipy"
    library_version = _pkg_version("scipy")

    def compute(
        self,
        cycle_results: Iterable[Any],
        records: Iterable[Any] | None = None,
        **kwargs: Any,
    ) -> Any:
        raise NonUniformComputeError(
            "SRM operates on a per-arm count dict; call "
            "ophamin.measuring.pillars.observability.srm.SRMDetector "
            "directly with your observed-by-arm counts."
        )


class RiverDriftPillar(PillarBase):
    """River-backed streaming drift detection (ADWIN / KSWIN / PageHinkley).

    Canonical API: :class:`DriftMonitor` in
    ``ophamin.measuring.pillars.observability.drift``.
    """

    pillar_name = "O.drift"
    library = "river"
    library_version = _pkg_version("river")

    def compute(
        self,
        cycle_results: Iterable[Any],
        records: Iterable[Any] | None = None,
        **kwargs: Any,
    ) -> Any:
        raise NonUniformComputeError(
            "DriftMonitor is incremental — feed observations via "
            "DriftMonitor.update() rather than a batch compute."
        )


# --- A · Adaptive sequential testing ----------------------------------------


class SPRTPillar(PillarBase):
    """Wald's SPRT + mSPRT — anytime-valid sequential decision making.

    Canonical API: :class:`SPRT` / :class:`GaussianSPRT` /
    :class:`BernoulliSPRT` / :class:`MixtureSPRT` in
    ``ophamin.measuring.pillars.adaptive.sprt``.
    """

    pillar_name = "A.sprt"
    library = "numpy"
    library_version = _pkg_version("numpy")

    def compute(
        self,
        cycle_results: Iterable[Any],
        records: Iterable[Any] | None = None,
        **kwargs: Any,
    ) -> Any:
        raise NonUniformComputeError(
            "SPRT consumes observations incrementally; instantiate a "
            "GaussianSPRT or MixtureSPRT and call .update() per "
            "observation, or .state() / .decision() to read out."
        )


# --- M · Mixed-effects + multi-experiment analysis --------------------------


class MixedEffectsPillar(PillarBase):
    """Random-intercept linear mixed model — statsmodels MixedLM wrapper.

    Canonical API: :class:`RandomInterceptModel` in
    ``ophamin.measuring.pillars.effects.mixed_effects``.
    """

    pillar_name = "M.mixed_effects"
    library = "statsmodels"
    library_version = _pkg_version("statsmodels")

    def compute(
        self,
        cycle_results: Iterable[Any],
        records: Iterable[Any] | None = None,
        **kwargs: Any,
    ) -> Any:
        raise NonUniformComputeError(
            "MixedLM consumes (X, y, groups) tabular data; instantiate "
            "RandomInterceptModel(reml=True) and call .fit(X, y, groups)."
        )


class MEAPillar(PillarBase):
    """Multi-experiment analysis — OLS interactions + ANOVA via statsmodels.

    Canonical API: :class:`MultiExperimentAnalysis` in
    ``ophamin.measuring.pillars.effects.mea``.
    """

    pillar_name = "M.mea"
    library = "statsmodels"
    library_version = _pkg_version("statsmodels")

    def compute(
        self,
        cycle_results: Iterable[Any],
        records: Iterable[Any] | None = None,
        **kwargs: Any,
    ) -> Any:
        raise NonUniformComputeError(
            "MEA expects a DataFrame with treatment + covariates; "
            "instantiate MultiExperimentAnalysis and call "
            ".joint_estimate(df, formula) directly."
        )


# --- I · Iterative cumulative meta-analysis ---------------------------------


class CMAPillar(PillarBase):
    """Cumulative meta-analysis — sequential pooling via statsmodels.

    Canonical API: :class:`CumulativeMetaAnalysis` in
    ``ophamin.measuring.pillars.synthesis.cma``.
    """

    pillar_name = "I.cma"
    library = "statsmodels"
    library_version = _pkg_version("statsmodels")

    def compute(
        self,
        cycle_results: Iterable[Any],
        records: Iterable[Any] | None = None,
        **kwargs: Any,
    ) -> Any:
        raise NonUniformComputeError(
            "CMA consumes (effect_size, variance) pairs; instantiate "
            "CumulativeMetaAnalysis(model='random') and feed pairs via "
            ".accumulate(effect, variance)."
        )


# --- N · N-fold robustness --------------------------------------------------


class CrossValidationPillar(PillarBase):
    """Cross-validation splitters — scikit-learn KFold / ShuffleSplit /
    GroupKFold / GroupShuffleSplit + Ophamin's bootstrap+monte-carlo
    helpers.

    Canonical API: :func:`monte_carlo_cv` / :func:`k_fold_cv` /
    :func:`bootstrap_cv` in
    ``ophamin.measuring.pillars.robustness.cross_validation``.
    """

    pillar_name = "N.cross_validation"
    library = "scikit-learn"
    library_version = _pkg_version("scikit-learn")

    def compute(
        self,
        cycle_results: Iterable[Any],
        records: Iterable[Any] | None = None,
        **kwargs: Any,
    ) -> Any:
        raise NonUniformComputeError(
            "Cross-validation expects (items, evaluator) — see "
            "monte_carlo_cv / k_fold_cv / bootstrap_cv in "
            "ophamin.measuring.pillars.robustness.cross_validation."
        )


# --- diagnostics ------------------------------------------------------------


class AnticipatoryPillar(PillarBase):
    """Anticipatory Failure Classification — split conformal via MAPIE.

    Canonical API: :class:`AnticipatoryFailureClassifier` in
    ``ophamin.measuring.pillars.diagnostics.anticipatory``.
    """

    pillar_name = "diagnostics.anticipatory"
    library = "mapie"
    library_version = _pkg_version("mapie")

    def compute(
        self,
        cycle_results: Iterable[Any],
        records: Iterable[Any] | None = None,
        **kwargs: Any,
    ) -> Any:
        raise NonUniformComputeError(
            "AnticipatoryFailureClassifier needs a fitted ConformalPredictor "
            "+ observed labels; instantiate it directly and call "
            ".assess(predictions, observations)."
        )


class InertiaPillar(PillarBase):
    """Cognitive Inertia Metrics — defensive-rejection vs Bayesian-adaptation
    rate.

    Canonical API: :class:`CognitiveInertiaMeter` in
    ``ophamin.measuring.pillars.diagnostics.inertia``.
    """

    pillar_name = "diagnostics.inertia"
    library = "numpy"
    library_version = _pkg_version("numpy")

    def compute(
        self,
        cycle_results: Iterable[Any],
        records: Iterable[Any] | None = None,
        **kwargs: Any,
    ) -> Any:
        raise NonUniformComputeError(
            "CognitiveInertiaMeter consumes labelled (event, outcome) "
            "pairs; instantiate it and call .record(...) then .report()."
        )


class KernelCouplingPillar(PillarBase):
    """Oracle Kernel-Coupling Diagnostic — entropy-coefficient sweep at
    collapse-prone cells.

    Canonical API: :class:`OracleKernelCouplingDiagnostic` in
    ``ophamin.measuring.pillars.diagnostics.kernel_coupling``.
    """

    pillar_name = "diagnostics.kernel_coupling"
    library = "numpy"
    library_version = _pkg_version("numpy")

    def compute(
        self,
        cycle_results: Iterable[Any],
        records: Iterable[Any] | None = None,
        **kwargs: Any,
    ) -> Any:
        raise NonUniformComputeError(
            "Kernel-coupling diagnostic sweeps an entropy coefficient "
            "against a substrate; instantiate "
            "OracleKernelCouplingDiagnostic(...) and call .sweep(sut, "
            "stimulus, base_params)."
        )


# --- registration -----------------------------------------------------------


def _register_all() -> tuple[PillarBase, ...]:
    """Register every adapter with :data:`ophamin.registry.PILLARS`.

    Returns the tuple of registered pillars so callers (e.g. tests) can
    introspect the canonical list. Idempotent — :func:`register_pillar`
    treats same-object re-registration as a no-op so module reloads
    don't trip.
    """
    from ophamin.registry import register_pillar

    adapters: tuple[PillarBase, ...] = (
        SPCPillar(),
        SRMPillar(),
        RiverDriftPillar(),
        SPRTPillar(),
        MixedEffectsPillar(),
        MEAPillar(),
        CMAPillar(),
        CrossValidationPillar(),
        AnticipatoryPillar(),
        InertiaPillar(),
        KernelCouplingPillar(),
    )
    for a in adapters:
        register_pillar(a)
    return adapters


#: tuple of every adapter that successfully registered at module import
#: (eleven entries in canonical OFAMIN + diagnostics order).
REGISTERED_PILLARS: tuple[PillarBase, ...] = _register_all()


__all__ = [
    "AnticipatoryPillar",
    "CMAPillar",
    "CrossValidationPillar",
    "InertiaPillar",
    "KernelCouplingPillar",
    "MEAPillar",
    "MixedEffectsPillar",
    "REGISTERED_PILLARS",
    "RiverDriftPillar",
    "SPCPillar",
    "SPRTPillar",
    "SRMPillar",
]
