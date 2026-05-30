# Empirical Proof Record — **VALIDATED**

**Proof ID:** `57284c4e30f20d834c210e80eac8445f5b62989118f5bd91a09a9ce47becf0d4`  
**Created:** 2026-05-23T23:16:24.474411+00:00

## 1. Claim

> At least 80% of Kimera's always-on numeric signals carry real dynamics across a DIVERSE stimulus battery (a signal frozen across every corpus — multilingual, financial, code, adversarial — is a genuine dead wire, not merely an unexercised conditional organ).

- **Operationalisation:** Stream 15 records from each of ['flores', 'financial', 'linux', 'cyber'] through the 'entity' target; combine all cycles; of signals present in EVERY cycle, the fraction taking >= 2 distinct values across the WHOLE battery. liveness_rate_union = always_on_live / always_on_total.
- **Threshold:** `liveness_rate_union >= 0.8 proportion`
- **H0:** H0: union liveness < 80% — genuine dead wires remain (frozen even under their own trigger); worklist non-empty
- **H1:** H1: union liveness >= 80% — the always-on surface is dynamically alive under diverse stimuli

## 2. Verdict

**Outcome:** VALIDATED  
**Observed:** `0.8605072463768116`

always-on liveness 0.8605: 475/552 every-cycle signals carry real dynamics; 77 are frozen defaults (the worklist); Wilson 95% CI [0.8291, 0.8869]. Context: whole-surface 2615/10276 (0.2545, deflated by under-sampling); 60 cycles

## 3. Pre-registration

- Registered at: `2026-05-23T23:16:24.273948+00:00`
- Config hash: `1299abf46cf679d41ddcea85442c738c8a16298307067524346b5f2ad307894c`
- Data hash: `1a70e8416900df8686bc14a72935ba15b1b2b966a9aeaddc1d2931fd24c93d3e`

_Stream 15 records from each of ['flores', 'financial', 'linux', 'cyber'] through Kimera 'entity'; combine all cycle results; classify each always-on numeric signal live (>=2 distinct values across the whole battery) vs frozen. Decide union liveness against >= 80%; Wilson 95% CI. Genuine dead-wire worklist (frozen across all corpora) in evidence._

## 4. Data

- Substrate: `kimera-swm` @ `78cb9f9fc6a8`
- Dataset: `flores-200` (parallel_corpus, 997 records, hash `bf4196403365…`)
- Dataset: `financial-corpus` (financial_corpus, 9847012 records, hash `55ab1cb57046…`)
- Dataset: `linux-kernel-commits` (commit_corpus, 1445246 records, hash `92a34cc42750…`)
- Dataset: `offensive-security-corpus` (adversarial_corpus, 4416305 records, hash `83109a27c3df…`)

## 5. Evidence

| pillar | statistic | value | 95% CI | library |
|---|---|---|---|---|
| `signal_dynamics` | `liveness_rate` | `0.8605072463768116` | (0.8291, 0.8869) | statsmodels 0.14.6 |

## 6. Signature

`ecd1fb1267287eee97790a74ee48be5358cb4291b0c4d1c6aa5e789c2feb5b0d`
