# Empirical Proof Record — **REFUTED**

**Proof ID:** `c3ef1c9fd90578c75e8d8b980733c837709fdc02bbc25e28c55e42616c87d2d1`  
**Created:** 2026-05-21T23:29:34.543483+00:00

## 1. Claim

> Under sustained load, the substrate stays cognitively alive: □ (for every cycle in the trajectory, Φ ≥ 0.05). The reported floor is the lowest-Φ cycle across the whole run.

- **Operationalisation:** Stream 3 passes over 8 substantive stimuli through Kimera's entity target (Takwin); read the per-cycle ``phi``. phi_floor_observed = min Φ over all cycles; the LTL □ invariant holds iff min Φ ≥ φ_floor.
- **Threshold:** `phi_floor >= 0.05 phi`
- **H0:** H0: min Φ < 0.05 — Φ collapses below the non-collapse floor somewhere in the run
- **H1:** H1: min Φ ≥ 0.05 — Φ stays above the collapse floor across the whole trajectory (substrate stays cognitively alive under sustained load)

## 2. Verdict

**Outcome:** REFUTED  
**Observed:** `0.0`

Φ floor 0.0000 over 24 cycles (3 passes × 8 stimuli); mean Φ 0.5575, band [0.0000, 0.6561], stdev 0.2110; non-collapse rate 87.5%; 0 cycles produced no Φ; worst cycle: stimulus 1 @ cycle 1 = 0.0000

## 3. Pre-registration

- Registered at: `2026-05-21T23:29:34.175173+00:00`
- Config hash: `fc0d6fa2b433540d0fc987795a9290da4c1acaff4c0266fcacf945fe8d7490b4`
- Data hash: `f36c007933b4b5223d517967d58c7b804a0a1417b2305418406bbf29c507cb69`

_Build a sustained-load schedule (3 passes over 8 stimuli = 24 cycles); stream it through Kimera's entity target. Read per-cycle Φ. Decide the LTL □ invariant: min Φ ≥ 0.05. INCONCLUSIVE if fewer than 6 cycles produced a Φ. The Φ band, per-pass means, and per-cycle Φ series are descriptive; none post-hoc-claimable._

## 4. Data

- Substrate: `kimera-swm` @ `674ae6b7b402`
- Dataset: `kimera-phi-stability-trajectory` (substrate-trajectory+sustained-load, 24 records, hash `f36c007933b4…`)

## 5. Evidence

| pillar | statistic | value | 95% CI | library |
|---|---|---|---|---|
| `O.flow.phi_stability` | `phi_floor` | `0.0` | — | ophamin 0.81.0 |

## 6. Signature

`0f527aed3d3488d53d6becea330e620012c45d2f29db697e868b30fd8c0c4a3f`
