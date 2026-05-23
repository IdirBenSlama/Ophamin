# Empirical Proof Record — **VALIDATED**

**Proof ID:** `77c1f925244a3490887366d80bd78b9dab7fc83ed5bf190d31900e2d83d7d4e9`  
**Created:** 2026-05-23T21:01:11.725624+00:00

## 1. Claim

> At least 80% of Kimera's always-on numeric signals carry real dynamics across a DIVERSE stimulus battery (a signal frozen across every corpus — multilingual, financial, code, adversarial — is a genuine dead wire, not merely an unexercised conditional organ).

- **Operationalisation:** Stream 40 records from each of ['flores', 'financial', 'linux', 'cyber'] through the 'entity' target; combine all cycles; of signals present in EVERY cycle, the fraction taking >= 2 distinct values across the WHOLE battery. liveness_rate_union = always_on_live / always_on_total.
- **Threshold:** `liveness_rate_union >= 0.8 proportion`
- **H0:** H0: union liveness < 80% — genuine dead wires remain (frozen even under their own trigger); worklist non-empty
- **H1:** H1: union liveness >= 80% — the always-on surface is dynamically alive under diverse stimuli

## 2. Verdict

**Outcome:** VALIDATED  
**Observed:** `0.8641304347826086`

always-on liveness 0.8641: 477/552 every-cycle signals carry real dynamics; 75 are frozen defaults (the worklist); Wilson 95% CI [0.8330, 0.8902]. Context: whole-surface 4647/22053 (0.2107, deflated by under-sampling); 160 cycles

## 3. Pre-registration

- Registered at: `2026-05-23T21:01:11.503367+00:00`
- Config hash: `5520036ff0ed73c1a2194ec88e9eac8fc6c533d69594750db3a8201e83fb02ab`
- Data hash: `1a70e8416900df8686bc14a72935ba15b1b2b966a9aeaddc1d2931fd24c93d3e`

_Stream 40 records from each of ['flores', 'financial', 'linux', 'cyber'] through Kimera 'entity'; combine all cycle results; classify each always-on numeric signal live (>=2 distinct values across the whole battery) vs frozen. Decide union liveness against >= 80%; Wilson 95% CI. Genuine dead-wire worklist (frozen across all corpora) in evidence._

## 4. Data

- Substrate: `kimera-swm` @ `78cb9f9fc6a8`
- Dataset: `flores-200` (parallel_corpus, 997 records, hash `bf4196403365…`)
- Dataset: `financial-corpus` (financial_corpus, 9847012 records, hash `55ab1cb57046…`)
- Dataset: `linux-kernel-commits` (commit_corpus, 1445246 records, hash `92a34cc42750…`)
- Dataset: `offensive-security-corpus` (adversarial_corpus, 4416305 records, hash `83109a27c3df…`)

## 5. Evidence

| pillar | statistic | value | 95% CI | library |
|---|---|---|---|---|
| `signal_dynamics` | `liveness_rate` | `0.8641304347826086` | (0.8330, 0.8902) | statsmodels 0.14.6 |

## 6. Signature

`a3016d4e1e2067429a6361ef04d5b4a9b32b90fa163a1e69d91029a5420ad878`
