"""N pillar — N-fold robustness and validation.

Proves a substrate's adaptations are generalisable responses to data structure,
not overfitted reactions to a specific data sequence.

    monte_carlo_cv / k_fold_cv / bootstrap_cv   resampling validators
    cross_validate                              run an evaluator over splits
    monte_carlo_splits / k_fold_splits / ...    split generators (group-aware)
"""

from ophamin.robustness.cross_validation import (
    CVResult,
    CVSplit,
    bootstrap_cv,
    bootstrap_splits,
    cross_validate,
    k_fold_cv,
    k_fold_splits,
    monte_carlo_cv,
    monte_carlo_splits,
)

__all__ = [
    "CVResult",
    "CVSplit",
    "cross_validate",
    "monte_carlo_cv",
    "monte_carlo_splits",
    "k_fold_cv",
    "k_fold_splits",
    "bootstrap_cv",
    "bootstrap_splits",
]
