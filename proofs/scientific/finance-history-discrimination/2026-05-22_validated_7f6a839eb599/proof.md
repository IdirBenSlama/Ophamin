# Empirical Proof Record — **VALIDATED**

**Proof ID:** `7f6a839eb599a92c43a7aafa736a07475cbedac9aa38796ee3323642f42e532e`  
**Created:** 2026-05-22T19:57:14.999044+00:00

## 1. Claim

> Kimera distinguishes the minimum-drawdown and maximum-drawdown orderings of the same real return multiset (genuinely different risk, identical trade-set), where a set-based retriever represents them identically: history_separation_advantage = mean(kimera_prime_distance) − mean(rag_representation_distance) > 0, with Kimera separating every pair and the RAG side conflating every pair.

- **Operationalisation:** For 5 real-market return multisets, find the min-DD and max-DD ordering (search of 300 shuffles + sorted extremes). Run both through Kimera entity·batch (fresh trajectories). kimera_prime_distance = 1 − Jaccard(prime_chain). rag_representation_distance = mean-pooled TF-IDF divergence (≈ 0, same multiset). VALIDATED iff advantage > 0 with separation rate 1.0 (each kimera_prime_distance ≥ 0.5, each rag ≈ 0).
- **Threshold:** `history_separation_advantage > 0.0 representation_distance`
- **H0:** H0: advantage <= 0 — Kimera conflates the min-DD and max-DD orderings no better than a set-based retriever
- **H1:** H1: advantage > 0 — Kimera separates real-risk-different same-set histories that a set-based retriever conflates

## 2. Verdict

**Outcome:** VALIDATED  
**Observed:** `1.0`

history_separation_advantage +1.0000 = Kimera prime-distance 1.0000 − RAG distance 0.000000 over 5 real min-DD vs max-DD pairs; separation rate 1.00 (Kimera distinguishes real-risk-different same-set histories, RAG conflates). Mean real ΔDD 0.0458 (the histories Kimera separates are genuinely different risk). NOTE: this is discrimination, not magnitude — Kimera does NOT grade by drawdown (MEM4 ρ=+0.18 ns; diagnostic ρ≈0). Series FRED SP500 (real market)

## 3. Pre-registration

- Registered at: `2026-05-22T19:57:14.638121+00:00`
- Config hash: `a337cd052a420c174c18f3dfef5893936aa8e26600ec836f3ae4075d3c9dc78e`
- Data hash: `4ff30d839032219673d615128ef6cf58092324932644a511b8adacf527424150`

_For 5 real return multisets, build the min-DD and max-DD ordering; run both through Kimera entity·batch. kimera_prime_distance = 1 − Jaccard(prime_chain); rag_representation_distance = mean-pooled TF-IDF (≈ 0). Headline: history_separation_advantage = mean(kimera) − mean(rag). INCONCLUSIVE if fewer than 4 windows yield a prime address for both orderings; VALIDATED iff advantage > 0 (Kimera separates, RAG conflates). The real ΔDD per window is reported as grounding; the gradedness limit (Kimera does NOT grade by drawdown magnitude, per MEM4 + diagnostic) is stated, not hidden._

## 4. Data

- Substrate: `kimera-swm` @ `cdda883ff04d`
- Dataset: `fred-market-min-max-drawdown-orderings` (real-market-returns+min-max-drawdown-orderings, 60 records, hash `4ff30d839032…`)

## 5. Evidence

| pillar | statistic | value | 95% CI | library |
|---|---|---|---|---|
| `O.comparison.finance_history_discrimination` | `history_separation_advantage` | `1.0` | — | ophamin 0.111.0 |

## 6. Signature

`26d47a913eed1b7c5c5195c11d6da1bfe878225a4dce1138638316ddf1961651`
