# Diagnostics — exploratory substrate probes (Tier-1 tooling)

Reproducible investigation scripts that inform scenario authoring. They are
*candidate-generation / characterization* runs, not signed proofs — a finding
worth a verdict graduates into a signed `Scenario`.

Run from the Ophamin repo root with the Kimera venv reachable:

    PYTHONPATH=src .venv/bin/python diagnostics/<script>.py

## size_meter — "does Kimera grade risk MAGNITUDE, not just detect difference?"

The decisive question after the memory arc (Kimera *discriminates* same-set
different-order histories — MEM5 — but does it measure *how much* worse?).

- `drawdown_gradedness.py` — same return multiset, min-DD..max-DD arrangements;
  do prime-address / coarse-state observables grade by drawdown? **No** (ρ≈0).
- `size_meter_sweep.py` — the FULL-surface sweep: of all ~4,000 emitted signals,
  which (if any) rises with the size of the order-dependent drawdown gap?
  Top candidate on SP500: `thermo_bridge_state.ness.rolling_mean_sigma` ρ=0.976.
- `size_meter_validate.py` — pre-registered confirmatory test on INDEPENDENT
  data (NASDAQ). The candidate did **not** replicate (ρ=0.43, p=0.14).

**Conclusion**: no replicated magnitude "size-meter" among Kimera's currently
*live* signals (only ~13% of the ~4,000 emitted signals vary with input; the
rest are defaults/conditional — Kimera is partially wired). Per the owner: this
is a **wiring brief** (the magnitude readout isn't live yet), not an
architectural verdict. The faint physics-native trend (NESS entropy production)
is the most promising place a magnitude readout would live if wired.
