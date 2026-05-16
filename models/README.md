# `models/` — captured / shipped model artifacts

Sub-layout:

```
models/
  kimera_state/                 captured Kimera-state snapshots used by
                                cross-cycle / cross-instance scenarios
                                (e.g. PrimeCrossInstanceScenario reads
                                trajectories from here)
  README.md                     this file
```

Currently small and ad-hoc. As scenarios that depend on captured
Kimera state grow (Round-J / Round-K trajectory captures), this
directory will gain per-capture subdirectories with their own
manifests.

## Capture provenance

Each captured artifact carries:

- the Kimera commit it was captured against;
- the capture script that produced it (typically
  `experiments/observatory/capture_*.py` Kimera-side);
- the cycle count, stimulus schedule, and reset-singletons state.

When ingesting into an Ophamin scenario, pass the capture path to
the scenario constructor (e.g. `PrimeCrossInstanceScenario(
trajectory_path="models/kimera_state/<capture>.json")`).

## Open

No formal manifest schema yet — captures are scenario-private.
A future Move could standardize a `CapturedTrajectoryManifest`
parallel to `EmpiricalProofRecord` / `AuditRecord`.
