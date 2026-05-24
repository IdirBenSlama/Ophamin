# Empirical Proof Record — **REFUTED**

**Proof ID:** `f4824485daecda4dbf01b6281d402a922a7d15357937bc21e4cf4794b7d948f3`  
**Created:** 2026-05-24T02:21:12.917643+00:00

## 1. Claim

> Kimera's representation-distance (relative divergence of the manifold state: coupling / order_parameter / knowledge_mass) between same-multiset return histories GRADES their real |Δ max-drawdown| (Spearman fidelity) better than a standard order-aware retriever, by a margin: graded_fidelity_advantage = fidelity(kimera_state) − fidelity(order_aware) >= 0.2. The prime set-distance is scored alongside as a saturation control.

- **Operationalisation:** For 8 real return multisets, generate 24+2 orderings spanning drawdowns; score each representation by Spearman(pairwise distance, |Δ max-drawdown|). Headline = mean over windows of fidelity(kimera_state) − fidelity(order_aware shingle); the prime set-distance fidelity (saturation control) and the order-blind mean-pool ~0 floor are reported alongside.
- **Threshold:** `graded_fidelity_advantage >= 0.2 spearman_rho`
- **H0:** H0: advantage < margin — Kimera's manifold-state divergence does not grade drawdown better than generic order-aware retrieval.
- **H1:** H1: advantage >= margin — Kimera's manifold-state divergence carries graded path-magnitude that generic order-aware retrieval does not.

## 2. Verdict

**Outcome:** REFUTED  
**Observed:** `-0.07657866667550224`

graded fidelity — kimera_state=-0.024, order-aware bar=0.053, order-blind floor=0.000; prime control=0.061 (saturation check); advantage=-0.077 vs margin 0.2.

## 3. Pre-registration

- Registered at: `2026-05-24T02:21:12.567268+00:00`
- Config hash: `5f8c5da7f8defc3355090fb892506f67e7b8b23d86787258cc70cf086777e335`
- Data hash: `0753497b317e32f44850f531b693fd36eba436a9eb93b07533924f2a54658c5f`

_For each of 8 real multisets, build 24+2 orderings; run each through Kimera entity·batch; compute pairwise kimera_state = relative manifold-state divergence (coupling/order/mass), prime = 1 − Jaccard(prime_chain) (control), order_aware = shingle cosine, order_blind = mean-pool. graded_fidelity = Spearman(distance, |Δ max-drawdown|) per method per window. Headline = mean(fid_kimera_state − fid_order_aware). INCONCLUSIVE if fewer than 4 windows yield manifold state for all orderings; VALIDATED iff advantage >= margin._

## 4. Data

- Substrate: `kimera-swm` @ `78cb9f9fc6a8`
- Dataset: `FRED SP500 (real market)` (market-returns, 8 records, hash `0753497b317e…`)

## 5. Evidence

| pillar | statistic | value | 95% CI | library |
|---|---|---|---|---|
| `graded-fidelity` | `graded_fidelity_advantage` | `-0.076579` | — | scipy spearmanr |

## 6. Signature

`9d9081aeecb3b0012676b7539708a5c81f767b22bf7bc60a6ec6520717b7382a`
