# Empirical Proof Record — **INCONCLUSIVE**

**Proof ID:** `079b4abd6dacc94581af28ce46db6327caf451bfaa68850f3bf2fed6c0b8c661`  
**Created:** 2026-05-24T03:31:26.445847+00:00

## 1. Claim

> Kimera's semantic manifold stays a single connected component under exposure — the median β₀ (zeroth Betti number, count of connected components) over GWF-cleared cycles equals 1.

- **Operationalisation:** median of β₀ across GWF-cleared cycles for which the substrate exposes a topology measurement
- **Threshold:** `manifold_betti_0_median == 1.0 count`
- **H0:** median β₀ != 1 (manifold fragmented or degenerate)
- **H1:** median β₀ == 1 (manifold connected)

## 2. Verdict

**Outcome:** INCONCLUSIVE  
**Observed:** `0.0`

manifold topology measured on 0/40 GWF-cleared cycles; median β₀ = 0 (connected-component rate 0.0%); median β₁ = 0, median β₂ = 0; geoid graph up to 0 nodes / 0 edges; 0 adapter errors; too few cycles exposed a topology measurement to decide (substrate may not surface β-numbers in this build)

## 3. Pre-registration

- Registered at: `2026-05-24T03:29:04.831512+00:00`
- Config hash: `ba0d4117d8279255bbbc8b646da5da85cc958e2efe7f65221e70f94e97952dab`
- Data hash: `92a34cc4275008279006eeec2c19cd2b45d7cc6167bf0d368d06fdcadf6a6648`

_Stream up to 40 records through Kimera's entity target (Takwin); for each GWF-cleared cycle that exposes topology, read β₀/β₁/β₂. Pre-registered threshold: median β₀ == 1 (manifold connected). Secondary descriptive evidence reports the β₁/β₂ distributions, the connected-component rate, and geoid/scar graph node+edge counts when present — none post-hoc-claimable._

## 4. Data

- Substrate: `kimera-swm` @ `78cb9f9fc6a8`
- Dataset: `linux-kernel-commits` (commit_corpus, 1445246 records, hash `92a34cc42750…`)

## 5. Evidence

| pillar | statistic | value | 95% CI | library |
|---|---|---|---|---|
| `O.topology.manifold_betti_0` | `manifold_betti_0_median` | `0.0` | — | ophamin 0.1.0 |
| `O.topology.manifold_betti_1` | `manifold_betti_1_median` | `0.0` | — | ophamin 0.1.0 |
| `O.topology.manifold_betti_2` | `manifold_betti_2_median` | `0.0` | — | ophamin 0.1.0 |
| `O.topology.geoid_graph` | `geoid_graph_nodes_max` | `0.0` | — | ophamin 0.1.0 |

## 6. Signature

`0eea9812438d104654d047cb906db3ae543fef012ca5f3967de7fda90ea9eea2`
