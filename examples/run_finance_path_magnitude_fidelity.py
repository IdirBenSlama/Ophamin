"""Run the fair, GRADED path-magnitude-fidelity proof on REAL market data (FRED).

The test the observatory was built to run. Not "does Kimera separate two
orderings" (binary; a metric artifact, as finance-history-discrimination was
shown to be) but "does Kimera's representation-distance SCALE with the real
|Δ max-drawdown| the orderings encode" — graded, matched-metric, fair:

    graded_fidelity_advantage = fidelity(kimera) − fidelity(order_aware_baseline)
    fidelity = Spearman(pairwise representation-distance, |Δ max-drawdown|)

VALIDATED iff advantage >= margin (default 0.20); REFUTED if Kimera's
prime-distance saturates (a binary detector, not a graded path-memory). The
order-aware bar (~0.04 on SP500) and order-blind floor (~0) are established
WITHOUT Kimera in diagnostics/path_magnitude_bar.py.

    PYTHONPATH=src N_WINDOWS=6 WINDOW_LEN=8 N_ORDERINGS=24 \
        .venv/bin/python -u examples/run_finance_path_magnitude_fidelity.py
"""

from __future__ import annotations

import os
import traceback
from pathlib import Path

from ophamin.measuring.proof.persistence import persist_proof
from ophamin.measuring.scenarios.base import DEFAULT_SIGN_KEY, Tier
from ophamin.measuring.scenarios.finance_path_magnitude_fidelity import (
    FinancePathMagnitudeFidelityScenario,
)
from ophamin.seeing.substrate import KimeraAdapter

REPO = "/Users/idirbenslama/Desktop/DEV/Kimera_SWM (Spherical Word Memory)"
SERIES = os.environ.get("SERIES", "SP500")
FRED_DIR = Path("data/raw/financial/fred")
N_WINDOWS = int(os.environ.get("N_WINDOWS", "6"))
WINDOW_LEN = int(os.environ.get("WINDOW_LEN", "8"))
N_ORDERINGS = int(os.environ.get("N_ORDERINGS", "24"))
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


def main() -> int:
    banner("OPHAMIN — path-magnitude FIDELITY (graded, fair) on REAL FRED data")
    returns = load_returns(SERIES)
    windows = select_windows(returns, N_WINDOWS, WINDOW_LEN)
    if len(windows) < N_WINDOWS:
        print(f"ERROR: only {len(windows)} suitable windows")
        return 1
    scenario = FinancePathMagnitudeFidelityScenario(
        return_windows=tuple(windows), n_orderings=N_ORDERINGS,
        series_label=f"FRED {SERIES} (real market)",
    )
    print(f"series      : FRED {SERIES} — {len(returns)} daily returns")
    print(f"windows     : {len(windows)} × {WINDOW_LEN}, {N_ORDERINGS}+2 orderings each")
    print(f"schedule    : {scenario.n_cycles} cycles on live Kimera")
    print("metric      : graded_fidelity = Spearman(distance, |Δ max-drawdown|), matched both sides")
    print("bar         : order-aware shingle (~0.04 on SP500); floor: order-blind (~0)")

    adapter = KimeraAdapter(REPO, target="entity", mode="batch", batch_timeout=10800.0)
    print(f"substrate   : {adapter.name} @ {adapter.git_commit()[:12]}")

    try:
        record = scenario.run(adapter, sign_key=DEFAULT_SIGN_KEY)
    except Exception:  # noqa: BLE001
        banner("PATH-MAGNITUDE-FIDELITY RUN RAISED")
        traceback.print_exc()
        return 1

    ev = record.evidence[0]
    banner("KIMERA vs order-aware baseline — does prime-distance GRADE drawdown?")
    print(f"  graded_fidelity_advantage : {ev.statistic_value:+.4f}  "
          "(kimera fidelity − order-aware bar)")
    for w in ev.detail.get("per_window", []):
        if w.get("gap"):
            print(f"  window {w['window']}: GAP (no primes)")
        else:
            print(f"  window {w['window']}: kimera={w['fidelity_kimera']:+.3f}  "
                  f"order-aware={w['fidelity_order_aware']:+.3f}  "
                  f"floor={w['fidelity_order_blind']:+.3f}")

    banner("VERDICT")
    print(f"verdict     : {record.verdict.outcome}")
    print(f"reasoning   : {record.verdict.reasoning}")

    bundle = persist_proof(
        record, root=OUT_DIR, tier=Tier.SCIENTIFIC.value, scenario_name=scenario.name)
    print(f"proof       : {bundle.bundle_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
