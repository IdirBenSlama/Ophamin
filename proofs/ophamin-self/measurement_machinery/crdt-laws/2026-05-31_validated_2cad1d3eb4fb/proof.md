# Empirical Proof Record — **VALIDATED**

**Proof ID:** `2cad1d3eb4fb50b41537639bcad3b227368efc4b0e9245d561206c1177f8a401`  
**Created:** 2026-05-31T18:33:51.782865+00:00

## 1. Claim

> Across 100 randomized op sequences (20 insert ops each), the two Yjs Python backends (pycrdt, y-py) converge to identical final text in ≥ 99.0% of cases. Both wrappers bind to the same Yrs Rust core; disagreement is a real bug. (CLAUDE.md §Layer 4 CRDT reconciliation: Kimera's distributed-substrate fusion relies on this law holding for the underlying CRDTs.)

- **Operationalisation:** For each of N sequences (deterministic seed), generate K insert ops with random (position, char) pairs. Apply each sequence to both backends; record (a) whether final text agrees, (b) per-backend wall-time. Aggregate the agreement rate; Wilson 95% CI on the binomial proportion.
- **Threshold:** `cross_backend_convergence_rate >= 0.99 proportion`
- **H0:** cross_backend_convergence_rate < 0.99 (at least one backend disagrees on final state in > 1.0% of cases)
- **H1:** cross_backend_convergence_rate >= 0.99 (both Yjs Python wrappers — pycrdt + y_py — converge to identical final text on the vast majority of randomized op sequences, as the shared Yrs Rust core requires)

## 2. Verdict

**Outcome:** VALIDATED  
**Observed:** `1.0`

100/100 sequences converged across both backends (1.0000); Wilson 95% CI [0.9630, 1.0000]

![cross_backend_convergence_rate confidence interval](assets/ci_cross_backend_convergence_rate.png)

## 3. Pre-registration

- Registered at: `2026-05-31T18:33:51.607322+00:00`
- Config hash: `eef18a4bba44d947a0033d81f07e75bf238d3bbc90dc8094d3525624ba140d75`
- Data hash: `eef18a4bba44d947a0033d81f07e75bf238d3bbc90dc8094d3525624ba140d75`

_Generate 100 random insert-op sequences (20 ops each, seed=20260515); apply each to a pycrdt YDoc AND a y-py YDoc; assert final text agrees. Wilson 95% CI on the binomial agreement rate; verdict against the pre-registered ≥99.0% threshold._

## 4. Data

- Substrate: `pycrdt+y_py-cross-backend` @ `pycrdt-0.13.`
- Dataset: `synthetic-crdt-op-sequences` (synthetic-crdt-op-stream, 100 records, hash `eef18a4bba44…`)

## 5. Evidence

| pillar | statistic | value | 95% CI | library |
|---|---|---|---|---|
| `cross_backend_yjs_convergence` | `cross_backend_convergence_rate` | `1.0` | (0.9630, 1.0000) | statsmodels 0.14.6 |

## 6. Signature

`30fa75b5338d733e7af1ca482ee9e3832e0ffe66358c18da7fd6626a635db5f7`
