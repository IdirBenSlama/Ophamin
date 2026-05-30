# Empirical Proof Record — **INCONCLUSIVE**

**Proof ID:** `cc005bda452d1f584a1cc340d51b84bd53d52c273c881eb8e64cbf9480b45b07`  
**Created:** 2026-05-24T00:59:27.196828+00:00

## 1. Claim

> Kimera's representation-distance (relative divergence of the manifold state: coupling / order_parameter / knowledge_mass) between same-multiset return histories GRADES their real |Δ max-drawdown| (Spearman fidelity) better than a standard order-aware retriever, by a margin: graded_fidelity_advantage = fidelity(kimera_state) − fidelity(order_aware) >= 0.2. The prime set-distance is scored alongside as a saturation control.

- **Operationalisation:** For 2 real return multisets, generate 8+2 orderings spanning drawdowns; score each representation by Spearman(pairwise distance, |Δ max-drawdown|). Headline = mean over windows of fidelity(kimera_state) − fidelity(order_aware shingle); the prime set-distance fidelity (saturation control) and the order-blind mean-pool ~0 floor are reported alongside.
- **Threshold:** `graded_fidelity_advantage >= 0.2 spearman_rho`
- **H0:** H0: advantage < margin — Kimera's manifold-state divergence does not grade drawdown better than generic order-aware retrieval.
- **H1:** H1: advantage >= margin — Kimera's manifold-state divergence carries graded path-magnitude that generic order-aware retrieval does not.

## 2. Verdict

**Outcome:** INCONCLUSIVE  
**Observed:** `0.0`

only 2/2 windows yielded manifold state for all orderings (need 4).

## 3. Pre-registration

- Registered at: `2026-05-24T00:59:26.933514+00:00`
- Config hash: `5c54f11dc61f758ff9f76a2c69f7c5783361829cb3666ada56f90ecbdcb570e5`
- Data hash: `daefbdeac7a7e6b95e7144bd2a4d5e8c1ea6f271f2c2e0633a6bbe2797c5651f`

_For each of 2 real multisets, build 8+2 orderings; run each through Kimera entity·batch; compute pairwise kimera_state = relative manifold-state divergence (coupling/order/mass), prime = 1 − Jaccard(prime_chain) (control), order_aware = shingle cosine, order_blind = mean-pool. graded_fidelity = Spearman(distance, |Δ max-drawdown|) per method per window. Headline = mean(fid_kimera_state − fid_order_aware). INCONCLUSIVE if fewer than 4 windows yield manifold state for all orderings; VALIDATED iff advantage >= margin._

## 4. Data

- Substrate: `kimera-swm` @ `78cb9f9fc6a8`
- Dataset: `FRED SP500 (real market)` (market-returns, 2 records, hash `daefbdeac7a7…`)

## 5. Evidence

| pillar | statistic | value | 95% CI | library |
|---|---|---|---|---|
| `graded-fidelity` | `graded_fidelity_advantage` | `0.0` | — | scipy spearmanr |

## 6. Signature

`ee0c662bb35a803d737e05db627081e1a26b16243e79840a4bcd90944fe1824b`
