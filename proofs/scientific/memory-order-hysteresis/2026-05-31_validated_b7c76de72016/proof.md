# Empirical Proof Record — **VALIDATED**

**Proof ID:** `b7c76de7201677eba6ab61ff942859b14196f49db96a4be5981886b20680bafe`  
**Created:** 2026-05-31T19:26:02.096914+00:00

## What this means

This proof tests whether Kimera remembers the ORDER things happened, not just what happened — a filing cabinet (order-blind) versus a landscape you walk, where the path leaves a groove. It does: the same query, after the same documents in a different order, lands differently. Kimera carries the order of experience where retrieval carries only the inventory. (observed order_hysteresis = 0.9444444444444444)

## 1. Claim

> After the same documents in a different ORDER, the same identically-recognised query gets a different prime-address from Kimera (hysteresis) beyond its own run-noise, whereas a set-based retriever returns the identical ranking (order-blind by construction): order_hysteresis = mean(order_divergence) − mean(noise_floor) > 0.

- **Operationalisation:** Run 6 documents + 6 held-out probes through Kimera's entity target (batch) in order A, order A again (determinism control), and order B (shuffled). Per probe: order_divergence = 1 − Jaccard(prime_chain|A, prime_chain|B); noise_floor = 1 − Jaccard(prime_chain|A1, prime_chain|A2). order_hysteresis = mean(order_divergence) − mean(noise_floor). Baseline: TF-IDF retrieval order-divergence over the same docs/queries (= 0). VALIDATED iff order_hysteresis > 0 with a significant paired order_divergence > noise_floor test.
- **Threshold:** `order_hysteresis > 0.0 jaccard_distance`
- **H0:** H0: order_hysteresis <= 0 — Kimera's response does not depend on document order beyond run-noise; accumulation is commutative, like a set-based retriever
- **H1:** H1: order_hysteresis > 0 — the same query after the same documents in a different order gets a different prime-address; Kimera carries the ORDER of experience (hysteresis) where RAG carries only the inventory

## 2. Verdict

**Outcome:** VALIDATED  
**Observed:** `0.9444444444444444`

order_hysteresis +0.9444 = Kimera order-divergence 1.0000 − noise-floor 0.0556 over 6 probes (prime-address); RAG (TF-IDF) order-divergence 0.0000 (set-based, order-blind by construction); paired order>noise Wilcoxon p=0.016 (significant — order matters); manifold-state order-effect coupling Δ=0.231499, mass Δ=0.389913 (noise coupling Δ=0.291579)

## 3. Pre-registration

- Registered at: `2026-05-31T19:26:01.711896+00:00`
- Config hash: `e9e0949b499b8b4758262350a7ec8186c65d34268517b474db214c627bb3688c`
- Data hash: `3896f14d8eaa26af9e1b43a0bcd7ece78d21d5ea1163e34de76c5ed375a27662`

_Three batches of 6 docs + 6 probes (order A, A again, B-shuffled) through Kimera entity/batch. Per probe compute prime-address (prime_chain) order_divergence (A vs B) and noise_floor (A vs A). order_hysteresis = mean difference. Baseline TF-IDF order-divergence (= 0) is the contrast. INCONCLUSIVE if fewer than 4 probes yield a prime address in all three runs, or the paired Wilcoxon (order_divergence > noise_floor) is not significant; else VALIDATED iff order_hysteresis > 0. Per-probe series + aggregate manifold-state divergence (coupling/mass) are evidence._

## 4. Data

- Substrate: `kimera-swm` @ `e6f4a36ab56d`
- Dataset: `kimera-order-hysteresis-trajectory` (substrate-trajectory+order-permutation+rag-baseline, 36 records, hash `3896f14d8eaa…`)

## 5. Evidence

| pillar | statistic | value | 95% CI | library |
|---|---|---|---|---|
| `O.comparison.order_hysteresis` | `order_hysteresis` | `0.9444444444444444` | — | ophamin 0.115.2 |

## 6. Signature

`2644a5707cd2d401576ff7fb56d9fb1f3942d3c2c6dbfc215fe7388dd396cf92`
