"""Run the Finance-History-Discrimination proof on REAL market data (FRED SP500).

The honest positive capability after MEM4 + the gradedness diagnostic showed the
limit (Kimera does NOT grade by drawdown magnitude — saturated order-detector):
Kimera SEPARATES the min-drawdown and max-drawdown orderings of the same real
return multiset (genuinely different risk, identical trades) where a set-based
retriever represents them identically.

    history_separation_advantage = mean(kimera_prime_distance)
                                  − mean(rag_representation_distance)

VALIDATED iff > 0 with Kimera separating every outcome-different pair and RAG
conflating them. Discrimination, not magnitude — the limit is reported, not hidden.

    PYTHONPATH=src N_WINDOWS=5 WINDOW_LEN=6 .venv/bin/python -u examples/run_finance_history_discrimination.py
"""

from __future__ import annotations

import os
import traceback
from pathlib import Path

from ophamin.measuring.proof.persistence import persist_proof
from ophamin.measuring.scenarios.base import DEFAULT_SIGN_KEY, Tier
from ophamin.measuring.scenarios.finance_history_discrimination import (
    FinanceHistoryDiscriminationScenario,
)
from ophamin.seeing.substrate import KimeraAdapter

REPO = "/Users/idirbenslama/Desktop/DEV/Kimera_SWM (Spherical Word Memory)"
SERIES = os.environ.get("SERIES", "SP500")
FRED_DIR = Path("data/raw/financial/fred")
N_WINDOWS = int(os.environ.get("N_WINDOWS", "5"))
WINDOW_LEN = int(os.environ.get("WINDOW_LEN", "6"))
OUT_DIR = Path("proofs")


def banner(text: str) -> None:
    print(f"\n{'=' * 72}\n{text}\n{'=' * 72}")


def load_returns(series: str) -> list[float]:
    import csv

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
    """Mixed-sign, volatility-spanning windows (so min-DD vs max-DD differ)."""
    import numpy as np

    wins = [tuple(returns[i:i + length]) for i in range(0, len(returns) - length, length)]
    # require both gains and losses so the drawdown ordering is non-trivial
    wins = [w for w in wins if any(x > 0 for x in w) and any(x < 0 for x in w)]
    vols = [float(np.std(w)) for w in wins]
    order = sorted(range(len(wins)), key=lambda k: vols[k])
    picks = [order[round(k * (len(order) - 1) / (n - 1))] for k in range(n)] if n > 1 else [order[-1]]
    seen, out = set(), []
    for idx in picks:
        if idx not in seen:
            seen.add(idx)
            out.append(wins[idx])
    return out


def main() -> int:
    banner("OPHAMIN — finance-history-discrimination on REAL market data (FRED SP500): "
           "does Kimera separate real-risk-different histories RAG conflates?")

    returns = load_returns(SERIES)
    windows = select_windows(returns, N_WINDOWS, WINDOW_LEN)
    if len(windows) < N_WINDOWS:
        print(f"ERROR: only {len(windows)} suitable windows")
        return 1
    scenario = FinanceHistoryDiscriminationScenario(
        return_windows=tuple(windows), series_label=f"FRED {SERIES} (real market)",
    )
    print(f"series      : FRED {SERIES} — {len(returns)} daily returns")
    print(f"windows     : {len(windows)} × {WINDOW_LEN} (min-DD vs max-DD ordering each)")
    print(f"schedule    : {scenario.n_cycles} cycles ({len(windows)} × 2 batches)")
    print("baseline    : mean-pooled TF-IDF (order-invariant by construction)")

    adapter = KimeraAdapter(REPO, target="entity", mode="batch", batch_timeout=10800.0)
    print(f"substrate   : {adapter.name} @ {adapter.git_commit()[:12]}")
    print(f"streaming   : {scenario.n_cycles} cycles on live Kimera…")

    try:
        record = scenario.run(adapter, sign_key=DEFAULT_SIGN_KEY)
    except Exception:  # noqa: BLE001
        banner("FINANCE-HISTORY-DISCRIMINATION RUN RAISED")
        traceback.print_exc()
        return 1

    ev = record.evidence[0]
    d = ev.detail
    banner("KIMERA vs RAG — separating real-risk-different histories (same trades)")
    print(f"  Kimera prime-distance (min-DD vs max-DD) : {d['kimera_prime_distance_mean']:.4f}")
    print(f"  RAG representation distance              : {d['rag_representation_distance_mean']:.6f}  "
          f"(order-invariant)")
    print(f"  separation rate                          : {d['separation_rate']:.2f}")
    print(f"  mean real ΔDD (risk difference)          : {d['delta_drawdown_mean']:.4f}")
    print(f"  history_separation_advantage             : {d['history_separation_advantage']:+.4f}")
    print(f"\n  scope: {d['claim_scope']} — {d['gradedness_limit'][:120]}…")

    banner("VERDICT")
    print(f"verdict     : {record.verdict.outcome}")
    print(f"reasoning   : {record.verdict.reasoning}")

    bundle = persist_proof(
        record, root=OUT_DIR, tier=Tier.SCIENTIFIC.value,
        scenario_name=scenario.name)
    print(f"proof       : {bundle.bundle_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
