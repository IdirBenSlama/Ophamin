# Empirical Proof Record — **VALIDATED**

**Proof ID:** `7e334cc352b171be0073f27ce567fb921587b5bf47a2bfa01676f494b61a4345`  
**Created:** 2026-05-23T20:18:05.141370+00:00

## 1. Claim

> Across all 9 KimeraInventory strata, the aggregate orphan rate is ≤ 20.0%. An orphan is a Python module in the inventory that has zero incoming imports from any other file in the Kimera repo AND is not explicitly annotated as WIRE_CANDIDATE / WIRED / ARCHIVED.

- **Operationalisation:** Build an import graph by walking every .py file under kimera_swm/ and parsing ``import`` / ``from ... import`` statements. For each inventoried surface, count incoming edges. Combine with annotation scanning (``.. note:: WIRE_CANDIDATE`` etc.) to produce one of {wired, wire_candidate, orphan, archived, parse_error, config}. orphan_rate = n_orphan / n_total_python_surfaces.
- **Threshold:** `aggregate_orphan_rate <= 0.2 proportion`
- **H0:** H0: orphan rate > 20.0% — load-bearing infrastructure is sitting unwired; fix list is non-empty
- **H1:** H1: orphan rate ≤ 20.0% — substrate completeness within target band

## 2. Verdict

**Outcome:** VALIDATED  
**Observed:** `0.08`

26/325 surfaces classified orphan (0.0800); Wilson 95% CI [0.0552, 0.1146]

![aggregate_orphan_rate confidence interval](assets/ci_aggregate_orphan_rate.png)

## 3. Pre-registration

- Registered at: `2026-05-23T20:18:04.719958+00:00`
- Config hash: `c0fd9cc53c786b0fb80f5ca5cab5c6f30ce671d494ebea10832ed9cbd1e42c88`
- Data hash: `76543e1c4be6bcde01d8c66ab84d6245155ed9225991d5d810ce89b878fa4b9f`

_Run KimeraInventory.discover_all against /Users/idirbenslama/Desktop/DEV/Kimera_SWM (Spherical Word Memory), then build a repo-wide import graph and classify each surface per the operationalization. Aggregate orphan_rate across all strata; decide against threshold ≤ 20.00%. Wilson 95% CI on the proportion. Per-stratum breakdown and the orphan / WIRE_CANDIDATE action lists are in the proof evidence._

## 4. Data

- Substrate: `kimera-swm` @ `78cb9f9fc6a8`
- Dataset: `kimera-substrate-completeness-probe` (static-inventory+import-graph, 325 records, hash `76543e1c4be6…`)

## 5. Evidence

| pillar | statistic | value | 95% CI | library |
|---|---|---|---|---|
| `import_graph_static` | `aggregate_orphan_rate` | `0.08` | (0.0552, 0.1146) | statsmodels 0.14.6 |

## 6. Signature

`26857efebaec60e49505ceb2fa4582952c39d73f9a6b7146dec81a9c49bc7d4a`
