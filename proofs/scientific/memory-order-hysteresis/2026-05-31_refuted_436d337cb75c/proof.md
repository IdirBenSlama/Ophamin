# Empirical Proof Record — **REFUTED**

**Proof ID:** `436d337cb75c5f83b63d8f437a73f7b6a04297c8883e096d6c56d97fb2ad65b2`  
**Created:** 2026-05-31T20:24:29.611071+00:00

## What this means

This proof tests whether Kimera remembers the ORDER things happened, not just what happened — a filing cabinet (order-blind) versus a landscape you walk, where the path leaves a groove. It did not here: accumulation came out order-independent — the differentiator is permanence and path-depth, not order. (observed order_hysteresis = 0.0)

## 1. Claim

> After the same documents in a different ORDER, the same identically-recognised query gets a different prime-address from Kimera (hysteresis) beyond its own run-noise, whereas a set-based retriever returns the identical ranking (order-blind by construction): order_hysteresis = mean(order_divergence) − mean(noise_floor) > 0.

- **Operationalisation:** Run 6 documents + 15 held-out probes through Kimera's entity target (batch) in order A, order A again (determinism control), and order B (shuffled). Per probe: order_divergence = 1 − Jaccard(prime_chain|A, prime_chain|B); noise_floor = 1 − Jaccard(prime_chain|A1, prime_chain|A2). order_hysteresis = mean(order_divergence) − mean(noise_floor). Baseline: TF-IDF retrieval order-divergence over the same docs/queries (= 0). VALIDATED iff order_hysteresis > 0 with a significant paired order_divergence > noise_floor test.
- **Threshold:** `order_hysteresis > 0.0 jaccard_distance`
- **H0:** H0: order_hysteresis <= 0 — Kimera's response does not depend on document order beyond run-noise; accumulation is commutative, like a set-based retriever
- **H1:** H1: order_hysteresis > 0 — the same query after the same documents in a different order gets a different prime-address; Kimera carries the ORDER of experience (hysteresis) where RAG carries only the inventory

## 2. Verdict

**Outcome:** REFUTED  
**Observed:** `0.0`

order_hysteresis +0.0000 = Kimera order-divergence 1.0000 − noise-floor 1.0000 over 14 probes (prime-address); RAG (TF-IDF) order-divergence 0.0000 (set-based, order-blind by construction); manifold-state order-effect coupling Δ=2.374707, mass Δ=0.982999 (noise coupling Δ=3.411841)

## 3. Pre-registration

- Registered at: `2026-05-31T20:24:29.409326+00:00`
- Config hash: `91269c9c9238ea1f32695ba2a90a0ad059d1a2d073e8441047753c4fa0bd9660`
- Data hash: `b22b0bfc0b009088ddc2a6536a912cc77ca22df80cacd1ba63431f8b6c062577`

_Three batches of 6 docs + 15 probes (order A, A again, B-shuffled) through Kimera entity/batch. Per probe compute prime-address (prime_chain) order_divergence (A vs B) and noise_floor (A vs A). order_hysteresis = mean difference. Baseline TF-IDF order-divergence (= 0) is the contrast. INCONCLUSIVE if fewer than 4 probes yield a prime address in all three runs, or the paired Wilcoxon (order_divergence > noise_floor) is not significant; else VALIDATED iff order_hysteresis > 0. Per-probe series + aggregate manifold-state divergence (coupling/mass) are evidence._

## 4. Data

- Substrate: `kimera-swm` @ `9227694980fb`
- Dataset: `kimera-order-hysteresis-trajectory` (substrate-trajectory+order-permutation+rag-baseline, 63 records, hash `b22b0bfc0b00…`)

## 5. Evidence

| pillar | statistic | value | 95% CI | library |
|---|---|---|---|---|
| `O.comparison.order_hysteresis` | `order_hysteresis` | `0.0` | — | ophamin 0.115.2 |

## 6. Signature

`5c64f72023e5427a693cb15bcd525f57a3bf39b374a5bdaa231d8b68c86010ec`
