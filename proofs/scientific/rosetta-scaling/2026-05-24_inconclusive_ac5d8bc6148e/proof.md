# Empirical Proof Record — **INCONCLUSIVE**

**Proof ID:** `ac5d8bc6148e1d88f17a1198905541743490cfab62e941a05d93110ccc2b667f`  
**Created:** 2026-05-24T03:32:27.402077+00:00

## 1. Claim

> On sentence-aligned parallel text, Kimera's Rosetta layer maps the same sentence content to the same canonical address in >= 80% of sentence groups when 10 languages are sampled per group (the universal-semantic-address promise).

- **Operationalisation:** fraction of FLORES-200 sentence groups for which Kimera's Rosetta returns a single distinct canonical value across 10 randomly-sampled language translations of the same sentence
- **Threshold:** `rosetta_canonical_agreement_at_k10 >= 0.8 fraction`
- **H0:** canonical agreement at K=10 < 0.8
- **H1:** canonical agreement at K=10 >= 0.8

## 2. Verdict

**Outcome:** INCONCLUSIVE  
**Observed:** `0.0`

Rosetta canonical agreement at K=10: 0/1 groups all-agree (0.0%); prime agreement at K=10: 0/1 (0.0%); 40 cycles, 0 adapter errors; too few complete sentence groups to decide

![rosetta_canonical_agreement_at_k10 confidence interval](assets/ci_rosetta_canonical_agreement_at_k10.png)

## 3. Pre-registration

- Registered at: `2026-05-24T03:30:18.451245+00:00`
- Config hash: `edc62a36d20e34afad28c9aa0b4202d0f1453d5036d69a3c65889a89f9b237b3`
- Data hash: `bf4196403365897ad95dbcc18fc5116a99bc007f58e71dd302566b61b4296262`

_Stream up to 40 single-language translations from FLORES-200 (50 languages per sentence group, deterministically sampled with seed=0) through Kimera's Rosetta 'rosetta' target, then per sentence group compute whether all K translations collapsed to the same Rosetta canonical address. Report agreement rates at K in [3, 5, 10, 20, 50]; the pre-registered threshold sits at K=10 (>= 80%)._

## 4. Data

- Substrate: `kimera-swm` @ `78cb9f9fc6a8`
- Dataset: `flores-200` (parallel_corpus, 997 records, hash `bf4196403365…`)

## 5. Evidence

| pillar | statistic | value | 95% CI | library |
|---|---|---|---|---|
| `O.rosetta.canonical_agreement` | `rosetta_canonical_agreement_at_k10` | `0.0` | (0.0000, 0.7935) | statsmodels 0.14.6 |
| `O.rosetta.prime_agreement` | `rosetta_prime_agreement_at_k10` | `0.0` | (0.0000, 0.7935) | statsmodels 0.14.6 |

## 6. Signature

`133feecedd1fbd4e13101d73187eea65b08c362c2e3abff4ae6fd16a8ebfe9ff`
