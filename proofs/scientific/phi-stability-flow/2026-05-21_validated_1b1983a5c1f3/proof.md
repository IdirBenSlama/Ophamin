# Empirical Proof Record — **VALIDATED**

**Proof ID:** `1b1983a5c1f36c9122852ac1b464842e70179f1b3c07b3b8916c74221bedbffd`  
**Created:** 2026-05-21T22:47:35.122985+00:00

## 1. Claim

> Under sustained load, the substrate stays cognitively alive: □ (for every cycle in the trajectory, Φ ≥ 0.05). The reported floor is the lowest-Φ cycle across the whole run.

- **Operationalisation:** Stream 3 passes over 8 substantive stimuli through Kimera's entity target (Takwin); read the per-cycle ``phi``. phi_floor_observed = min Φ over all cycles; the LTL □ invariant holds iff min Φ ≥ φ_floor.
- **Threshold:** `phi_floor >= 0.05 phi`
- **H0:** H0: min Φ < 0.05 — Φ collapses below the non-collapse floor somewhere in the run
- **H1:** H1: min Φ ≥ 0.05 — Φ stays above the collapse floor across the whole trajectory (substrate stays cognitively alive under sustained load)

## 2. Verdict

**Outcome:** VALIDATED  
**Observed:** `0.6603084741552229`

Φ floor 0.6603 over 24 cycles (3 passes × 8 stimuli); mean Φ 0.6892, band [0.6603, 0.7023], stdev 0.0141; non-collapse rate 100.0%; 0 cycles produced no Φ; worst cycle: stimulus 1 @ cycle 1 = 0.6603

## 3. Pre-registration

- Registered at: `2026-05-21T22:47:34.736531+00:00`
- Config hash: `fc0d6fa2b433540d0fc987795a9290da4c1acaff4c0266fcacf945fe8d7490b4`
- Data hash: `4e6090352a40ea27df1cf08fb4d02bd55c48c75253ece6e66e46809e7c3bc4a8`

_Build a sustained-load schedule (3 passes over 8 stimuli = 24 cycles); stream it through Kimera's entity target. Read per-cycle Φ. Decide the LTL □ invariant: min Φ ≥ 0.05. INCONCLUSIVE if fewer than 6 cycles produced a Φ. The Φ band, per-pass means, and per-cycle Φ series are descriptive; none post-hoc-claimable._

## 4. Data

- Substrate: `kimera-swm` @ `674ae6b7b402`
- Dataset: `kimera-phi-stability-trajectory` (substrate-trajectory+sustained-load, 24 records, hash `4e6090352a40…`)

## 5. Evidence

| pillar | statistic | value | 95% CI | library |
|---|---|---|---|---|
| `O.flow.phi_stability` | `phi_floor` | `0.6603084741552229` | — | ophamin 0.77.0 |

## 6. Signature

`72f43dee6a91020a9bb9e48633cc926706160fd778502abe22bb3257b78374a4`
