# Empirical Proof Record — **VALIDATED**

**Proof ID:** `cbab3d9af622fb833439f3351cd76393855c4252f0b2e8630578d3bcd4e5521b`  
**Created:** 2026-06-01T13:20:39.461861+00:00

## What this means

This proof tests whether Kimera remembers the ORDER things happened, not just what happened — a filing cabinet (order-blind) versus a landscape you walk, where the path leaves a groove. It does: the same query, after the same documents in a different order, lands differently. Kimera carries the order of experience where retrieval carries only the inventory. (observed order_hysteresis = 0.5759920634920634)

## 1. Claim

> After the same documents in a different ORDER, the same identically-recognised query gets a different prime-address from Kimera (hysteresis) beyond its own run-noise, whereas a set-based retriever returns the identical ranking (order-blind by construction): order_hysteresis = mean(order_divergence) − mean(noise_floor) > 0.

- **Operationalisation:** Run 6 documents + 15 held-out probes through Kimera's entity target (batch) in order A, order A again (determinism control), and order B (shuffled). Per probe: order_divergence = 1 − Jaccard(prime_chain|A, prime_chain|B); noise_floor = 1 − Jaccard(prime_chain|A1, prime_chain|A2). order_hysteresis = mean(order_divergence) − mean(noise_floor). Baseline: TF-IDF retrieval order-divergence over the same docs/queries (= 0). VALIDATED iff order_hysteresis > 0 with a significant paired order_divergence > noise_floor test.
- **Threshold:** `order_hysteresis > 0.0 jaccard_distance`
- **H0:** H0: order_hysteresis <= 0 — Kimera's response does not depend on document order beyond run-noise; accumulation is commutative, like a set-based retriever
- **H1:** H1: order_hysteresis > 0 — the same query after the same documents in a different order gets a different prime-address; Kimera carries the ORDER of experience (hysteresis) where RAG carries only the inventory

## 2. Verdict

**Outcome:** VALIDATED  
**Observed:** `0.5759920634920634`

order_hysteresis +0.5760 = Kimera order-divergence 1.0000 − noise-floor 0.4240 over 14 probes (prime-address); RAG (TF-IDF) order-divergence 0.0000 (set-based, order-blind by construction); paired order>noise Wilcoxon p=0.0022 (significant — order matters); manifold-state order-effect coupling Δ=0.121933, mass Δ=0.982999 (noise coupling Δ=0.365885)

## 3. Pre-registration

- Registered at: `2026-06-01T13:20:39.082841+00:00`
- Config hash: `91269c9c9238ea1f32695ba2a90a0ad059d1a2d073e8441047753c4fa0bd9660`
- Data hash: `b22b0bfc0b009088ddc2a6536a912cc77ca22df80cacd1ba63431f8b6c062577`

_Three batches of 6 docs + 15 probes (order A, A again, B-shuffled) through Kimera entity/batch. Per probe compute prime-address (prime_chain) order_divergence (A vs B) and noise_floor (A vs A). order_hysteresis = mean difference. Baseline TF-IDF order-divergence (= 0) is the contrast. INCONCLUSIVE if fewer than 4 probes yield a prime address in all three runs, or the paired Wilcoxon (order_divergence > noise_floor) is not significant; else VALIDATED iff order_hysteresis > 0. Per-probe series + aggregate manifold-state divergence (coupling/mass) are evidence._

## 4. Data

- Substrate: `kimera-swm` @ `bfc970cb5654`
- Dataset: `kimera-order-hysteresis-trajectory` (substrate-trajectory+order-permutation+rag-baseline, 63 records, hash `b22b0bfc0b00…`)

## 5. Evidence

| pillar | statistic | value | 95% CI | library |
|---|---|---|---|---|
| `O.comparison.order_hysteresis` | `order_hysteresis` | `0.5759920634920634` | — | ophamin 0.115.2 |

## 6. Signature

`d109c0530fcca2167ed0bf84a261835c75bcf1aa4a616ca65417f95a72ab4f18`
