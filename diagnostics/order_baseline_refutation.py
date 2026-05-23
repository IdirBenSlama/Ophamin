"""Refutation diagnostic: is the finance-history "advantage" a metric artifact?

The signed proof `finance-history-discrimination` reports, on real FRED SP500
data, `kimera_prime_distance = 1.0` vs `rag_representation_distance = 0.0` for
every window — headline "Kimera separates real-risk-different histories that RAG
conflates." This diagnostic stress-tests that claim WITHOUT Kimera (which isn't
runnable here) by reconstructing the EXACT min-DD / max-DD orderings the proof
used and re-scoring the RAG side with order-bearing / matched-metric baselines.

The proof scores the two sides with DIFFERENT metrics:
  * Kimera side : 1 − Jaccard(prime_set)          (saturates → 1.0)
  * RAG side    : mean-pooled TF-IDF cosine        (commutative → 0.0)

If a STANDARD retrieval representation — applied to the same events — also
separates the orderings, then "RAG conflates them" is a property of the chosen
baseline (mean-pooling), not of retrieval, and the 1.0-vs-0.0 "advantage" is a
metric-choice artifact rather than a measured capability gap.

Run from the repo root:
    .venv/bin/python diagnostics/order_baseline_refutation.py
Reads data/raw/financial/fred/SP500.csv (the same source the proof used).
Read-only; writes nothing. Honest by construction: it would happily report
"baseline still 0" if that were true.
"""

from __future__ import annotations

import csv
import os
from pathlib import Path

from ophamin.comparing.retrieval_baseline import (
    bag_representation_divergence,
    event_set_jaccard_divergence,
    ordered_representation_divergence,
)
from ophamin.measuring.scenarios.finance_history_discrimination import (
    FinanceHistoryDiscriminationScenario,
    _render_event,
)

FRED_DIR = Path("data/raw/financial/fred")
SERIES = os.environ.get("SERIES", "SP500")
N_WINDOWS = int(os.environ.get("N_WINDOWS", "5"))
WINDOW_LEN = int(os.environ.get("WINDOW_LEN", "6"))


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
    seen: set[int] = set()
    out: list[tuple[float, ...]] = []
    for idx in picks:
        if idx not in seen:
            seen.add(idx)
            out.append(wins[idx])
    return out


def main() -> int:
    if not (FRED_DIR / f"{SERIES}.csv").exists():
        print(f"ERROR: {FRED_DIR / f'{SERIES}.csv'} not found (run from repo root)")
        return 1
    returns = load_returns(SERIES)
    windows = select_windows(returns, N_WINDOWS, WINDOW_LEN)
    scenario = FinanceHistoryDiscriminationScenario(
        return_windows=tuple(windows), series_label=f"FRED {SERIES}",
    )

    print(f"\nFRED {SERIES}: {len(returns)} returns, {len(windows)} windows x {WINDOW_LEN}")
    print("Reconstructing the EXACT min-DD/max-DD orderings the proof scored.\n")
    print("Per window — RAG side scored three ways on the SAME events:")
    print("  bag      = mean-pooled TF-IDF cosine   (what the PROOF used)")
    print("  ordered  = unigram+bigram shingle cosine (order-bearing, standard IR)")
    print("  set-jacc = 1 - Jaccard(event sets)     (SAME metric used on Kimera)\n")

    hdr = f"{'win':>3} {'bag':>8} {'ordered':>8} {'set-jacc':>8}   {'bag(val)':>8} {'ord(val)':>8}"
    print(hdr)
    print("-" * len(hdr))

    bags, ordereds, jaccs = [], [], []
    for wi, ms in enumerate(windows):
        lo_arr, _lo_dd, hi_arr, _hi_dd = scenario._min_max_dd_orderings(ms)
        # position-tagged events, EXACTLY as fed to Kimera in the proof
        lo_events = [_render_event(i, r) for i, r in enumerate(lo_arr)]
        hi_events = [_render_event(i, r) for i, r in enumerate(hi_arr)]
        bag = bag_representation_divergence(lo_events, hi_events)
        ordr = ordered_representation_divergence(lo_events, hi_events)
        jac = event_set_jaccard_divergence(lo_events, hi_events)
        # content-only events (no position tag): set is identical; only ORDER differs
        lo_val = [f"return {r:+.4f}" for r in lo_arr]
        hi_val = [f"return {r:+.4f}" for r in hi_arr]
        bag_v = bag_representation_divergence(lo_val, hi_val)
        ord_v = ordered_representation_divergence(lo_val, hi_val)
        bags.append(bag)
        ordereds.append(ordr)
        jaccs.append(jac)
        print(f"{wi:>3} {bag:>8.3f} {ordr:>8.3f} {jac:>8.3f}   {bag_v:>8.3f} {ord_v:>8.3f}")

    n = len(bags)
    print("-" * len(hdr))
    print(f"mean {sum(bags)/n:>8.3f} {sum(ordereds)/n:>8.3f} {sum(jaccs)/n:>8.3f}")
    print("\nProof's claim: kimera_prime_distance=1.0 vs rag=bag=0.0 -> advantage 1.0\n")
    print("Finding:")
    print(f"  - bag (proof's RAG metric) reproduces ~0  -> mean {sum(bags)/n:.3f}")
    print(f"  - ordered (standard order-aware IR) is    -> mean {sum(ordereds)/n:.3f}")
    print(f"  - set-jacc (Kimera's OWN metric on RAG)    -> mean {sum(jaccs)/n:.3f}")
    if sum(jaccs) / n >= 0.5 or sum(ordereds) / n > 0.0:
        print("\n  => A standard retrieval representation SEPARATES the same histories")
        print("     the mean-pool 'conflates'. The 1.0-vs-0.0 advantage is a metric-")
        print("     choice artifact (Jaccard-on-Kimera vs mean-pool-on-RAG), not a")
        print("     measured capability gap. Claim NOT supported under a fair baseline.")
    else:
        print("\n  => Standard order-aware baselines ALSO score ~0: the claim survives.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
