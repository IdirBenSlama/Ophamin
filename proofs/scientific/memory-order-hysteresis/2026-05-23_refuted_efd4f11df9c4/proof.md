# Empirical Proof Record — **REFUTED**

**Proof ID:** `efd4f11df9c451e0c3136f4d99e9619b1b4775b485f58bd1eadf04ca4ed7168c`  
**Created:** 2026-05-23T23:12:57.844884+00:00

## 1. Claim

> After the same documents in a different ORDER, the same identically-recognised query gets a different prime-address from Kimera (hysteresis) beyond its own run-noise, whereas a set-based retriever returns the identical ranking (order-blind by construction): order_hysteresis = mean(order_divergence) − mean(noise_floor) > 0.

- **Operationalisation:** Run 6 documents + 6 held-out probes through Kimera's entity target (batch) in order A, order A again (determinism control), and order B (shuffled). Per probe: order_divergence = 1 − Jaccard(prime_chain|A, prime_chain|B); noise_floor = 1 − Jaccard(prime_chain|A1, prime_chain|A2). order_hysteresis = mean(order_divergence) − mean(noise_floor). Baseline: TF-IDF retrieval order-divergence over the same docs/queries (= 0). VALIDATED iff order_hysteresis > 0 with a significant paired order_divergence > noise_floor test.
- **Threshold:** `order_hysteresis > 0.0 jaccard_distance`
- **H0:** H0: order_hysteresis <= 0 — Kimera's response does not depend on document order beyond run-noise; accumulation is commutative, like a set-based retriever
- **H1:** H1: order_hysteresis > 0 — the same query after the same documents in a different order gets a different prime-address; Kimera carries the ORDER of experience (hysteresis) where RAG carries only the inventory

## 2. Verdict

**Outcome:** REFUTED  
**Observed:** `0.0`

order_hysteresis +0.0000 = Kimera order-divergence 1.0000 − noise-floor 1.0000 over 6 probes (prime-address); RAG (TF-IDF) order-divergence 0.0000 (set-based, order-blind by construction); manifold-state order-effect coupling Δ=0.175958, mass Δ=6.289987 (noise coupling Δ=0.0)

## 3. Pre-registration

- Registered at: `2026-05-23T23:12:57.603543+00:00`
- Config hash: `e9e0949b499b8b4758262350a7ec8186c65d34268517b474db214c627bb3688c`
- Data hash: `3896f14d8eaa26af9e1b43a0bcd7ece78d21d5ea1163e34de76c5ed375a27662`

_Three batches of 6 docs + 6 probes (order A, A again, B-shuffled) through Kimera entity/batch. Per probe compute prime-address (prime_chain) order_divergence (A vs B) and noise_floor (A vs A). order_hysteresis = mean difference. Baseline TF-IDF order-divergence (= 0) is the contrast. INCONCLUSIVE if fewer than 4 probes yield a prime address in all three runs, or the paired Wilcoxon (order_divergence > noise_floor) is not significant; else VALIDATED iff order_hysteresis > 0. Per-probe series + aggregate manifold-state divergence (coupling/mass) are evidence._

## 4. Data

- Substrate: `kimera-swm` @ `78cb9f9fc6a8`
- Dataset: `kimera-order-hysteresis-trajectory` (substrate-trajectory+order-permutation+rag-baseline, 36 records, hash `3896f14d8eaa…`)

## 5. Evidence

| pillar | statistic | value | 95% CI | library |
|---|---|---|---|---|
| `O.comparison.order_hysteresis` | `order_hysteresis` | `0.0` | — | ophamin 0.115.2 |

## 6. Signature

`9c84b27aa3bf36c6e55999aa9dc403a101d4aa1c55cce38a7521fd401185bd86`
