# Empirical Proof Record — **VALIDATED**

**Proof ID:** `236d77eefa17d940e69a9f9796e446a21b014a991f0371ba6842862994e7df4c`  
**Created:** 2026-05-24T03:33:24.927091+00:00

## 1. Claim

> The substrate's response to the number ZERO collocates with its VOID/collapse state (contradiction stimuli) more than with idle rest (neutral stimuli): zero_void_proximity > 0.

- **Operationalisation:** Stream four stimulus conditions (neutral, zero, numbers, contradiction) through the full entity cycle; per condition, take the mean over cycles of the substrate's void-class (void/null/contradiction/collapse/dissonance) and entropy-class (entropy/varentropy/uncertainty) raw fields; z-normalise across conditions; zero_void_proximity = dist(zero, neutral) − dist(zero, contradiction).
- **Threshold:** `zero_void_proximity > 0.0 z-distance`
- **H0:** H0: zero sits nearer rest than the void (proximity <= 0) — zero is absence
- **H1:** H1: zero sits nearer the void than rest (proximity > 0) — zero is the void

## 2. Verdict

**Outcome:** VALIDATED  
**Observed:** `1.6182530963887647`

zero_void_proximity +1.618 (dist(zero,rest)=9.075, dist(zero,void)=7.457); void-real dist(void,rest)=9.380; plenum entropy(void)/entropy(rest)=1.140; 50 void/entropy fields

![zero_void_proximity confidence interval](assets/ci_zero_void_proximity.png)

## 3. Pre-registration

- Registered at: `2026-05-24T03:33:24.712508+00:00`
- Config hash: `adc55152c7c9ad3cbb55167674030259202b54a6eb080a86382849389a06102a`
- Data hash: `8e4cb8d2cf9747c5d252c5d7532fe1348700c94310ad18ffcc3bd0bf62110b14`

_Per condition: stream stimuli, flatten CycleResult.raw, keep void+entropy fields, average over cycles. z-normalise the 4 signature vectors; report zero_void_proximity = dist(zero,neutral) − dist(zero,contradiction); secondary: dist(contradiction,neutral) (void real?) and entropy(contradiction)/entropy(neutral) (plenum?)._

## 4. Data

- Substrate: `kimera-swm` @ `78cb9f9fc6a8`
- Dataset: `zero-void-conditions` (ontology-probe (neutral/zero/numbers/contradiction), 32 records, hash `8e4cb8d2cf97…`)

## 5. Evidence

| pillar | statistic | value | 95% CI | library |
|---|---|---|---|---|
| `zero_as_void` | `zero_void_proximity` | `1.6182530963887647` | (0.0000, 0.0000) | numpy 2.4.4 |

## 6. Signature

`0d5f3004de9bca8e2e8af6d2ca43a57006e20693d394bf393a7983cc88376782`
