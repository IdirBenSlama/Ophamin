# Empirical Proof Record — **VALIDATED**

**Proof ID:** `f6af1a5c15df3c4aa0f94411f77485fe3f1937be195cd8682d4a4b5434f954f8`  
**Created:** 2026-05-22T18:22:29.635644+00:00

## 1. Claim

> After the same documents in a different ORDER, the same identically-recognised query gets a different prime-address from Kimera (hysteresis) beyond its own run-noise, whereas a set-based retriever returns the identical ranking (order-blind by construction): order_hysteresis = mean(order_divergence) − mean(noise_floor) > 0.

- **Operationalisation:** Run 6 documents + 6 held-out probes through Kimera's entity target (batch) in order A, order A again (determinism control), and order B (shuffled). Per probe: order_divergence = 1 − Jaccard(prime_chain|A, prime_chain|B); noise_floor = 1 − Jaccard(prime_chain|A1, prime_chain|A2). order_hysteresis = mean(order_divergence) − mean(noise_floor). Baseline: TF-IDF retrieval order-divergence over the same docs/queries (= 0). VALIDATED iff order_hysteresis > 0 with a significant paired order_divergence > noise_floor test.
- **Threshold:** `order_hysteresis > 0.0 jaccard_distance`
- **H0:** H0: order_hysteresis <= 0 — Kimera's response does not depend on document order beyond run-noise; accumulation is commutative, like a set-based retriever
- **H1:** H1: order_hysteresis > 0 — the same query after the same documents in a different order gets a different prime-address; Kimera carries the ORDER of experience (hysteresis) where RAG carries only the inventory

## 2. Verdict

**Outcome:** VALIDATED  
**Observed:** `0.9333333333333333`

order_hysteresis +0.9333 = Kimera order-divergence 1.0000 − noise-floor 0.0667 over 6 probes (prime-address); RAG (TF-IDF) order-divergence 0.0000 (set-based, order-blind by construction); paired order>noise Wilcoxon p=0.016 (significant — order matters); manifold-state order-effect coupling Δ=0.058803, mass Δ=4.511444 (noise coupling Δ=0.175958)

## 3. Pre-registration

- Registered at: `2026-05-22T18:22:29.262800+00:00`
- Config hash: `e9e0949b499b8b4758262350a7ec8186c65d34268517b474db214c627bb3688c`
- Data hash: `3896f14d8eaa26af9e1b43a0bcd7ece78d21d5ea1163e34de76c5ed375a27662`

_Three batches of 6 docs + 6 probes (order A, A again, B-shuffled) through Kimera entity/batch. Per probe compute prime-address (prime_chain) order_divergence (A vs B) and noise_floor (A vs A). order_hysteresis = mean difference. Baseline TF-IDF order-divergence (= 0) is the contrast. INCONCLUSIVE if fewer than 4 probes yield a prime address in all three runs, or the paired Wilcoxon (order_divergence > noise_floor) is not significant; else VALIDATED iff order_hysteresis > 0. Per-probe series + aggregate manifold-state divergence (coupling/mass) are evidence._

## 4. Data

- Substrate: `kimera-swm` @ `949d9fc73e5d`
- Dataset: `kimera-order-hysteresis-trajectory` (substrate-trajectory+order-permutation+rag-baseline, 36 records, hash `3896f14d8eaa…`)

## 5. Evidence

| pillar | statistic | value | 95% CI | library |
|---|---|---|---|---|
| `O.comparison.order_hysteresis` | `order_hysteresis` | `0.9333333333333333` | — | ophamin 0.109.0 |

## 6. Signature

`37f93c4d5b33ae0e9f33f7a9be7c9d3eb0bd1a897ea3c458938d4d0bb716b809`
