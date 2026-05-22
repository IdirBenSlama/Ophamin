"""Run the Finance-Path-Dependence proof on REAL market data (FRED SP500).

The functional-advantage question: is Kimera's path-dependent memory *useful* on
real data? Answer it on the canonical order-dependent financial quantity —
maximum drawdown. Max drawdown is order-dependent by definition (same return
multiset, different order → different drawdown), so a set-based retriever
(order-invariant representation) is structurally blind to it. Does Kimera's
representation TRACK it?

    drawdown_tracking_rho = Spearman( kimera_state_divergence(true, shuffle),
                                      |maxdrawdown(true) − maxdrawdown(shuffle)| )

> 0 + significant ⇒ Kimera's memory carries the order-information a real risk
metric needs, where RAG carries zero (demonstrated). ≤ 0 ⇒ Kimera's text
encoding misses the numeric path — an honest finance construction brief.

Real data: FRED SP500 daily index. Windows are selected to span the volatility
range (transparent, deterministic) — NOT cherry-picked by outcome.

    PYTHONPATH=src N_WINDOWS=6 WINDOW_LEN=6 N_SHUFFLES=2 .venv/bin/python -u examples/run_finance_path_dependence.py
"""

from __future__ import annotations

import os
import traceback
from pathlib import Path

from ophamin.measuring.proof.persistence import persist_proof
from ophamin.measuring.scenarios.base import DEFAULT_SIGN_KEY, Tier
from ophamin.measuring.scenarios.finance_path_dependence import (
    FinancePathDependenceScenario,
)
from ophamin.seeing.substrate import KimeraAdapter

REPO = "/Users/idirbenslama/Desktop/DEV/Kimera_SWM (Spherical Word Memory)"
SERIES = os.environ.get("SERIES", "SP500")
FRED_DIR = Path("data/raw/financial/fred")
N_WINDOWS = int(os.environ.get("N_WINDOWS", "6"))
WINDOW_LEN = int(os.environ.get("WINDOW_LEN", "6"))
N_SHUFFLES = int(os.environ.get("N_SHUFFLES", "2"))
OUT_DIR = Path("proofs")


def banner(text: str) -> None:
    print(f"\n{'=' * 72}\n{text}\n{'=' * 72}")


def load_returns(series: str) -> list[float]:
    """Daily returns from a FRED price series CSV (skip non-numeric gaps)."""
    import csv

    prices: list[float] = []
    with open(FRED_DIR / f"{series}.csv", newline="") as fh:
        for row in csv.reader(fh):
            if len(row) < 2 or row[0] == "observation_date":
                continue
            try:
                prices.append(float(row[1]))
            except ValueError:
                continue  # FRED uses "." for missing
    return [prices[i] / prices[i - 1] - 1.0 for i in range(1, len(prices)) if prices[i - 1]]


def select_windows(returns: list[float], n: int, length: int) -> list[tuple[float, ...]]:
    """Non-overlapping windows selected to span the volatility range
    (deterministic; selection is by volatility spread, never by outcome)."""
    import numpy as np

    wins = [tuple(returns[i:i + length]) for i in range(0, len(returns) - length, length)]
    wins = [w for w in wins if len(w) == length]
    vols = [float(np.std(w)) for w in wins]
    order = sorted(range(len(wins)), key=lambda k: vols[k])
    # pick n windows at evenly-spaced volatility ranks (low → high)
    picks = [order[round(k * (len(order) - 1) / (n - 1))] for k in range(n)] if n > 1 else [order[-1]]
    seen, out = set(), []
    for idx in picks:
        if idx not in seen:
            seen.add(idx)
            out.append(wins[idx])
    return out


def main() -> int:
    banner("OPHAMIN — finance-path-dependence on REAL market data (FRED SP500): "
           "does Kimera track order-dependent drawdown that RAG cannot?")

    returns = load_returns(SERIES)
    if len(returns) < N_WINDOWS * WINDOW_LEN:
        print(f"ERROR: only {len(returns)} returns for {SERIES}")
        return 1
    windows = select_windows(returns, N_WINDOWS, WINDOW_LEN)
    print(f"series      : FRED {SERIES} — {len(returns)} daily returns")
    print(f"windows     : {len(windows)} × {WINDOW_LEN} periods (spanning the volatility range)")
    print(f"shuffles    : {N_SHUFFLES} per window (same return multiset, different order)")

    scenario = FinancePathDependenceScenario(
        return_windows=tuple(windows), n_shuffles=N_SHUFFLES,
        series_label=f"FRED {SERIES} (real market)",
    )
    print(f"schedule    : {scenario.n_cycles} cycles "
          f"({len(windows)} × (1+{N_SHUFFLES}) batches)")
    print("ground truth: max drawdown (order-dependent by definition)")
    print("baseline    : mean-pooled TF-IDF representation (order-invariant by construction)")

    adapter = KimeraAdapter(REPO, target="entity", mode="batch", batch_timeout=10800.0)
    print(f"substrate   : {adapter.name} @ {adapter.git_commit()[:12]}")
    print(f"streaming   : {scenario.n_cycles} cycles on live Kimera — real-data functional test…")

    try:
        record = scenario.run(adapter, sign_key=DEFAULT_SIGN_KEY)
    except Exception:  # noqa: BLE001
        banner("FINANCE-PATH-DEPENDENCE RUN RAISED")
        traceback.print_exc()
        return 1

    ev = record.evidence[0]
    d = ev.detail
    banner("KIMERA vs RAG — tracking order-dependent drawdown on real market data")
    print(f"  drawdown_tracking_rho (Kimera)    : {d['drawdown_tracking_rho']} "
          f"(Spearman p={d['spearman_p_value']})")
    print(f"  Kimera mean state-divergence      : {d['kimera_state_divergence_mean']:.4f}")
    print(f"  Kimera prime-address order-div    : {d['kimera_prime_divergence_mean']:.4f}")
    print(f"  RAG representation divergence     : {d['rag_representation_divergence_mean']:.6f}  "
          f"(order-invariant by construction)")
    print(f"  pairs measured                    : {d['n_pairs']}")

    banner("VERDICT")
    print(f"verdict     : {record.verdict.outcome}")
    print(f"reasoning   : {record.verdict.reasoning}")
    print(f"\ninterpretation: {d['interpretation']}")

    bundle = persist_proof(
        record, root=OUT_DIR, tier=Tier.SCIENTIFIC.value,
        scenario_name=scenario.name)
    print(f"proof       : {bundle.bundle_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
