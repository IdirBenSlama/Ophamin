# Empirical Proof Record — **VALIDATED**

**Proof ID:** `98cafc15f11214e26b550eb4a08d86a73a57a1841464d5c3456504bf5f4ec356`  
**Created:** 2026-05-23T23:09:41.663048+00:00

## 1. Claim

> Two independent invocations of the 'crdt-laws' scenario with constructor kwargs {'n_sequences': 5, 'ops_per_sequence': 5, 'seed': 20260517} produce bit-identical reproducibility-form proof hashes. (RFC 0002 Phase E4: research-grade reproducibility — every scenario must be deterministic given a fixed seed + corpus + substrate_commit + ophamin_commit.)

- **Operationalisation:** Instantiate the target scenario twice with identical kwargs; run each to emit a signed proof record; compute reproducibility_hash(proof) on each (SHA-256 over the canonical body with wall-clock fields stripped); assert the two hashes match exactly.
- **Threshold:** `reproducibility_hash_match >= 1.0 proportion`
- **H0:** Two independent runs of the target scenario produce different reproducibility-form hashes — non-determinism is leaking somewhere in the measurement pipeline.
- **H1:** Two independent runs produce bit-identical reproducibility-form hashes — the scenario honours the seed + config contract.

## 2. Verdict

**Outcome:** VALIDATED  
**Observed:** `1.0`

match: reproducibility_hash_a=d235bb996604fb4e..., reproducibility_hash_b=d235bb996604fb4e... — target scenario was 'crdt-laws'

## 3. Pre-registration

- Registered at: `2026-05-23T23:09:41.457643+00:00`
- Config hash: `7ffe47f60a2a3087c17fd9d7cc332ccca581272f6cf3f7eeb885032bff206928`
- Data hash: `7ffe47f60a2a3087c17fd9d7cc332ccca581272f6cf3f7eeb885032bff206928`

_Instantiate SCENARIOS['crdt-laws'] twice with identical kwargs {'n_sequences': 5, 'ops_per_sequence': 5, 'seed': 20260517}. Run each to emit a signed proof. Compute SHA-256 over the canonical body with wall-clock fields stripped per _REPRODUCIBILITY_EXCLUDED_PATHS + per-pillar timing keys matching _REPRODUCIBILITY_EXCLUDED_DETAIL_KEY_SUFFIXES. VALIDATED iff the two hashes match (binary; 1.0 / 0.0)._

## 4. Data

- Substrate: `ophamin-self-audit` @ `f9e0012b75f2`
- Dataset: `synthetic-self-audit` (self-audit-replay, 2 records, hash `7ffe47f60a2a…`)

## 5. Evidence

| pillar | statistic | value | 95% CI | library |
|---|---|---|---|---|
| `reproducibility_audit` | `reproducibility_hash_match` | `1.0` | — | ophamin 0.115.2 |

## 6. Signature

`0b6d10b704e574bf7882f3522dace63f06498d06d0ba3def9ac0ae4b1f1dc16c`
