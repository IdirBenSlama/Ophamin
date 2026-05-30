"""Arrow of Time — STRENGTHENED: all FRED series, parallel, mechanism-split.

The signed n=8 proof (proofs/scientific/arrow-of-time/...fae2098bf5fa) scored
rate 1.0 but had three honest weaknesses: small n, sign-agnostic vote, and
rate = max over many observables. This driver firms all three by reusing the
EXACT scenario logic (_load_fred_window/_zscore/_flatten_numeric/_summaries)
across ALL 42 FRED series in PARALLEL (the 037 throughput fix applied to the
very test that was queued behind it), and reports:

  * pervasiveness — how MANY observables are arrow-consistent (not just the max)
  * mechanism-split — do THERMODYNAMIC observables (thermo/entropy/echoform/phi/
    ness/free_energy) carry the arrow MORE than non-thermo ones? (the
    "is it specifically the thermodynamic arrow" question)
  * directional consistency at n=42 + Wilson CI on the best observable

Order-blind baseline stays 0.5 by construction (identical value multiset; any
input-only stat has delta 0 → excluded).

    PYTHONPATH=src .venv/bin/python -u examples/arrow_of_time_scaled.py [max_series]
"""
from __future__ import annotations

import math
import os
import sys
import time
from collections import defaultdict
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path

REPO = "/Users/idirbenslama/Desktop/DEV/Kimera_SWM (Spherical Word Memory)"
FRED_DIR = Path("/Volumes/Behemoth/Ophamin FrameWork /ophamin/data/raw/financial/fred")
WINDOW = 48
CONCURRENCY = max(1, min(10, (os.cpu_count() or 2) - 2))

# thermodynamic-arrow keywords vs everything else (mechanism-specificity probe)
THERMO_KW = ("thermo", "entropy", "echoform", "phi", "ness", "free_energy",
             "dissip", "heat", "beta", "work", "energy")


def _is_thermo(key: str) -> bool:
    k = key.lower()
    return any(w in k for w in THERMO_KW)


def run_chunk(paths: list[str], channel: str = "value") -> list[tuple[str, dict[str, float]]]:
    """One worker: build a real KimeraAdapter once, stream fwd+rev for each
    series, return per-(observable::stat) forward-minus-reversed deltas.
    channel='value' (bare values) or 'delta' (consecutive changes = the
    transition/derivative wire under test)."""
    from ophamin.measuring.scenarios.arrow_of_time import (
        ArrowOfTimeScenario, _flatten_numeric, _load_fred_window, _zscore,
    )
    from ophamin.seeing.substrate import KimeraAdapter

    summaries = ArrowOfTimeScenario._summaries
    adapter = KimeraAdapter(REPO, target="entity", mode="batch", batch_timeout=900.0)

    def _seq(values: list[float]) -> list[float]:
        """Stimulus sequence for `channel`. value = z-scored values; delta =
        z-scored consecutive CHANGES (derived AFTER any reversal, so a reversed
        series' deltas are the negated-reverse of forward — the directional
        signal the value channel drops)."""
        z = _zscore(values)
        if channel in ("delta", "delta_raw"):
            dd = [z[i] - z[i - 1] for i in range(1, len(z))]
            if channel == "delta_raw":
                return dd  # trend SIGN preserved (mean of dd = net trend)
            return _zscore(dd) if len(dd) >= 2 else dd  # detrended (mean removed)
        return z

    out: list[tuple[str, dict[str, float]]] = []
    for ps in paths:
        p = Path(ps)
        vals = _load_fred_window(p, WINDOW)
        if len(vals) < max(8, WINDOW // 2):
            continue
        fwd_seq = _seq(vals)
        rev_seq = _seq(list(reversed(vals)))
        if len(fwd_seq) < 2 or len(rev_seq) < 2:
            continue
        fwd = adapter.run_batch([f"{x:.4f}" for x in fwd_seq])
        rev = adapter.run_batch([f"{x:.4f}" for x in rev_seq])
        fok = [c for c in fwd if getattr(c, "success", True)]
        rok = [c for c in rev if getattr(c, "success", True)]
        if len(fok) < 2 or len(rok) < 2:
            continue
        ftr: dict[str, list[float]] = defaultdict(list)
        rtr: dict[str, list[float]] = defaultdict(list)
        for c in fok:
            for k, v in _flatten_numeric(c.raw).items():
                ftr[k].append(v)
        for c in rok:
            for k, v in _flatten_numeric(c.raw).items():
                rtr[k].append(v)
        d: dict[str, float] = {}
        for k in set(ftr) & set(rtr):
            sf = summaries(ftr[k])
            sr = summaries(rtr[k])
            for stat in set(sf) & set(sr):
                delta = sf[stat] - sr[stat]
                if math.isfinite(delta):
                    d[f"{k}::{stat}"] = delta
        out.append((p.stem, d))
    return out


def _chunks(items: list, n: int) -> list[list]:
    return [items[i::n] for i in range(n)]


def _chance_floor(n: int) -> float:
    """Pure-noise consistency floor E[max(k,n-k)/n], k~Binomial(n,0.5)."""
    from math import comb
    return sum(comb(n, k) * max(k, n - k) for k in range(n + 1)) / (2 ** n) / n


def main() -> int:
    from statsmodels.stats.proportion import proportion_confint

    max_series = int(sys.argv[1]) if len(sys.argv) > 1 else 42
    channel = sys.argv[2] if len(sys.argv) > 2 else "value"
    files = [str(p) for p in sorted(FRED_DIR.glob("*.csv"))[:max_series]]
    if not files:
        raise RuntimeError(f"no FRED CSVs under {FRED_DIR}")
    print(f"arrow-of-time SCALED: {len(files)} series, channel={channel}, window={WINDOW}, "
          f"concurrency={CONCURRENCY}, target=entity @ real Kimera", flush=True)

    t0 = time.time()
    deltas: dict[str, list[float]] = defaultdict(list)
    n_series = 0
    used: list[str] = []
    with ProcessPoolExecutor(max_workers=CONCURRENCY) as ex:
        futs = [ex.submit(run_chunk, c, channel) for c in _chunks(files, CONCURRENCY) if c]
        for fut in as_completed(futs):
            for stem, d in fut.result():
                n_series += 1
                used.append(stem)
                for key, delta in d.items():
                    deltas[key].append(delta)
            print(f"  ... {n_series} series done ({time.time()-t0:.0f}s)", flush=True)

    if n_series < 2:
        raise RuntimeError(f"only {n_series} usable series")

    # per-observable directional consistency across series (sign-agnostic):
    # rate = fraction of series whose delta carries the majority sign.
    per_key: dict[str, tuple[float, int]] = {}  # key -> (consistency, n_nonzero)
    for key, ds in deltas.items():
        nz = [x for x in ds if abs(x) > 1e-12]
        if len(nz) < max(2, n_series // 2):
            continue
        pos = sum(1 for x in nz if x > 0)
        per_key[key] = (max(pos, len(nz) - pos) / len(nz), len(nz))

    if not per_key:
        raise RuntimeError("no observable had enough nonzero series")

    best_key, (best_rate, best_n) = max(per_key.items(), key=lambda kv: (kv[1][0], kv[1][1]))
    ci_low, ci_high = proportion_confint(round(best_rate * best_n), best_n,
                                         alpha=0.05, method="wilson")

    # pervasiveness
    rates = [r for r, _ in per_key.values()]
    frac = lambda thr: sum(1 for r in rates if r >= thr) / len(rates)  # noqa: E731

    # mechanism-split
    th = [r for k, (r, _) in per_key.items() if _is_thermo(k)]
    ot = [r for k, (r, _) in per_key.items() if not _is_thermo(k)]
    mean = lambda xs: sum(xs) / len(xs) if xs else float("nan")  # noqa: E731

    print(f"\n{'=' * 70}\nARROW OF TIME — STRENGTHENED ({n_series} real series, {time.time()-t0:.0f}s)\n{'=' * 70}")
    print(f"order-blind baseline   : 0.500 (identical value multiset, by construction)")
    print(f"best observable        : {best_key}")
    print(f"  consistency          : {best_rate:.3f}  (n={best_n} series; Wilson 95% CI [{ci_low:.3f}, {ci_high:.3f}])")
    obs_mean = sum(r for r, _ in per_key.values()) / len(per_key)
    null_mean = sum(_chance_floor(n) for _, n in per_key.values()) / len(per_key)
    excess = obs_mean - null_mean
    print(f"\nMEAN consistency  (the honest signal — not the cherry-picked max)")
    print(f"  observed mean        : {obs_mean:.3f}")
    print(f"  expected under null  : {null_mean:.3f}  (pure-noise floor for these n)")
    print(f"  excess over null     : {excess:+.3f}   {'<<< REAL SIGNAL' if excess > 0.03 else '~ noise (no arrow)'}")
    print(f"\nPERVASIVENESS  ({len(per_key)} path-dependent observables w/ enough nonzero series)")
    print(f"  consistency == 1.00  : {frac(1.0):.1%}")
    print(f"  consistency >= 0.90  : {frac(0.90):.1%}")
    print(f"  consistency >= 0.75  : {frac(0.75):.1%}")
    print(f"\nMECHANISM-SPLIT  (is it specifically the THERMODYNAMIC arrow?)")
    print(f"  thermodynamic obs    : n={len(th):<4} mean consistency {mean(th):.3f}  frac>=0.90 {sum(1 for r in th if r>=0.9)/len(th) if th else float('nan'):.1%}")
    print(f"  other (non-thermo)   : n={len(ot):<4} mean consistency {mean(ot):.3f}  frac>=0.90 {sum(1 for r in ot if r>=0.9)/len(ot) if ot else float('nan'):.1%}")
    print(f"\nTOP 20 ARROW-CARRYING OBSERVABLES")
    for k, (r, nn) in sorted(per_key.items(), key=lambda kv: (kv[1][0], kv[1][1]), reverse=True)[:20]:
        print(f"  {r:.3f}  (n={nn:>2}) {'[THERMO]' if _is_thermo(k) else '        '} {k}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
