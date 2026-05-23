"""Establish the order-aware BAR for the fair, GRADED path-magnitude test.

The honest, graded test of Kimera's path-memory (the fix for the binary
separation flaw the review found): does a representation's distance between two
*same-multiset* return histories SCALE with their real ``|Δ max-drawdown|``?
A genuine path-memory's distances grade with how different the paths really are;
a binary order-detector's distances saturate at ~1.0 and carry no graded signal.

This measures the two reference points — on real FRED data, no Kimera needed —
that Kimera must be judged against:

  floor  (order-blind mean-pool)  -> ~0: no order information, no graded signal.
  BAR    (order-aware shingle)     -> the graded fidelity a *standard* order-aware
                                      retriever already achieves; Kimera must
                                      EXCEED this to claim a real path-memory.

Run from the repo root:
    .venv/bin/python diagnostics/path_magnitude_bar.py
Reads data/raw/financial/fred/<SERIES>.csv. Read-only; writes nothing.
"""

from __future__ import annotations

import csv
import os
import random
from itertools import combinations
from pathlib import Path

from ophamin.comparing.retrieval_baseline import (
    bag_representation_divergence,
    graded_fidelity,
    ordered_representation_divergence,
)
from ophamin.measuring.scenarios.finance_path_dependence import (
    FinancePathDependenceScenario,
)

_max_drawdown = FinancePathDependenceScenario._max_drawdown

FRED_DIR = Path("data/raw/financial/fred")
SERIES = os.environ.get("SERIES", "SP500")
N_WINDOWS = int(os.environ.get("N_WINDOWS", "6"))
WINDOW_LEN = int(os.environ.get("WINDOW_LEN", "8"))
N_ORDERINGS = int(os.environ.get("N_ORDERINGS", "24"))


def load_returns(series: str) -> list[float]:
    prices: list[float] = []
    with open(FRED_DIR / f"{series}.csv", newline="") as fh:
        for row in csv.reader(fh):
            if len(row) < 2 or row[0] == "observation_date":
                continue
            try:
                prices.append(float(row[1]))
            except ValueError:
                continue
    return [prices[i] / prices[i - 1] - 1.0 for i in range(1, len(prices)) if prices[i - 1]]


def select_windows(returns: list[float], n: int, length: int) -> list[tuple[float, ...]]:
    import numpy as np

    wins = [tuple(returns[i:i + length]) for i in range(0, len(returns) - length, length)]
    wins = [w for w in wins if any(x > 0 for x in w) and any(x < 0 for x in w)]
    vols = [float(np.std(w)) for w in wins]
    order = sorted(range(len(wins)), key=lambda k: vols[k])
    picks = [order[round(k * (len(order) - 1) / (n - 1))] for k in range(n)] if n > 1 else [order[-1]]
    out: list[tuple[float, ...]] = []
    seen: set[int] = set()
    for idx in picks:
        if idx not in seen:
            seen.add(idx)
            out.append(wins[idx])
    return out


def _content_events(arr: tuple[float, ...]) -> list[str]:
    # one token per return, in order, NO position tag -> the only signal is order
    return [f"r{r:+.5f}" for r in arr]


def main() -> int:
    if not (FRED_DIR / f"{SERIES}.csv").exists():
        print(f"ERROR: {FRED_DIR / f'{SERIES}.csv'} not found (run from repo root)")
        return 1
    returns = load_returns(SERIES)
    windows = select_windows(returns, N_WINDOWS, WINDOW_LEN)

    print(f"\nFRED {SERIES}: {len(windows)} windows x {WINDOW_LEN}, "
          f"{N_ORDERINGS}+2 orderings each")
    print("graded fidelity = Spearman( representation-distance , |Δ max-drawdown| )\n")
    header = f"{'win':>3} {'floor(blind)':>13} {'BAR(order-aware)':>16} {'n_pairs':>8}"
    print(header)
    print("-" * len(header))

    floor_rhos: list[float] = []
    bar_rhos: list[float] = []
    for wi, ms in enumerate(windows):
        variants = [tuple(sorted(ms)), tuple(sorted(ms, reverse=True))]
        for s in range(N_ORDERINGS):
            a = list(ms)
            random.Random(s).shuffle(a)
            variants.append(tuple(a))
        variants = list(dict.fromkeys(variants))  # dedup, preserve order
        y = [_max_drawdown(v) for v in variants]
        ev = [_content_events(v) for v in variants]
        blind: list[float] = []
        order: list[float] = []
        gt: list[float] = []
        for i, j in combinations(range(len(variants)), 2):
            gt.append(abs(y[i] - y[j]))
            blind.append(bag_representation_divergence(ev[i], ev[j]))
            order.append(ordered_representation_divergence(ev[i], ev[j]))
        f_blind = graded_fidelity(blind, gt)
        f_order = graded_fidelity(order, gt)
        floor_rhos.append(f_blind)
        bar_rhos.append(f_order)
        print(f"{wi:>3} {f_blind:>13.3f} {f_order:>16.3f} {len(gt):>8}")

    n = len(floor_rhos)
    print("-" * len(header))
    print(f"{'mean':>3} {sum(floor_rhos) / n:>13.3f} {sum(bar_rhos) / n:>16.3f}")
    print("\nReading:")
    print(f"  floor (order-blind) ~ {sum(floor_rhos) / n:.3f}  -> order carries the "
          "signal (≈0 expected)")
    print(f"  BAR   (order-aware) ~ {sum(bar_rhos) / n:.3f}  -> graded fidelity Kimera "
          "must EXCEED")
    print("\nKimera is VALIDATED iff its prime-distance grades drawdown-difference")
    print("ABOVE this order-aware bar; REFUTED if its distances saturate (fidelity ~")
    print("floor) — a binary order-detector, not a graded path-memory.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
