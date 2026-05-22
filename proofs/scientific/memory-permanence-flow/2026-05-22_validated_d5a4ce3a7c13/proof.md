# Empirical Proof Record — **VALIDATED**

**Proof ID:** `d5a4ce3a7c13c2da3c49a12950204c2c0eae8c4d29504a7f956fe187e4e8da2a`  
**Created:** 2026-05-22T18:11:53.104513+00:00

## 1. Claim

> When an identically-recognised probe is re-exposed across a trajectory, it lands on a strictly-deeper (more-scarred) manifold every time: memory_path_dependence = (recognised re-exposure transitions with Δ permanent-scars > 0) / (recognised re-exposure transitions) >= 1.0, with the whole-run scar count monotonic non-decreasing (a scar cannot be reset). This measures memory where Kimera keeps it — the scars and the S4 manifold — not the content-recognition layer.

- **Operationalisation:** Run 12 stimuli each re-exposed 3x, interleaved (gap = len(stimuli)), through Kimera's entity target (Takwin) in batch mode so the substrate accumulates across the batch. Per cycle read vault_stats.total_scars_stored (canonical permanent scars), arachne_web_coupling_frobenius (manifold deformation), and the concept set (recognition). For each same-stimulus consecutive exposure pair: recognised iff Jaccard(concepts) >= 0.80; confirmed iff recognised AND Δ scars > 0. memory_path_dependence = confirmed / recognised. Forced to 0.0 (REFUTED) if the whole-run scar count ever decreases.
- **Threshold:** `memory_path_dependence >= 1.0 proportion`
- **H0:** H0: memory_path_dependence < 1.0 — some re-exposure of a recognised probe did NOT land on more permanent scars (the substrate re-derives without accumulating), or a scar was reset; not path-dependent permanent memory
- **H1:** H1: memory_path_dependence >= 1.0 — every re-exposure of a recognised probe lands on a strictly-deeper manifold and no scar is ever reset; path-dependent permanent memory in the scar/S4 substrate

## 2. Verdict

**Outcome:** VALIDATED  
**Observed:** `1.0`

memory_path_dependence 1.0000 = 20/20 recognised re-exposure transitions landed on strictly more permanent scars; 0 transitions failed recognition (excluded). Permanence: HOLDS (0 scar-count decreases over the run). Scars 1.0→29.0; coupling 1.240565→16.629817; phi |delta| mean 0.0020 (Φ-rigid → memory is in the scars/manifold, not Φ); scar-depth vs exposure-ordinal Spearman rho=0.944, p=3.1e-18 (deepens with experience)

## 3. Pre-registration

- Registered at: `2026-05-22T18:11:52.760330+00:00`
- Config hash: `7d353f8d2b982cf4c2ecb24447af42ad6ee0f472ed7c01f8f0187980d23d7415`
- Data hash: `548d6568d12e293ce4229c8104f6265fb666e9b9bc5212e084f05fe7d115a77e`

_Build an interleaved re-exposure schedule (12 stimuli x 3 exposures, gap = 12); stream through Kimera's entity target in batch mode. Per cycle read the permanent scar count (vault_stats.total_scars_stored), the manifold coupling, the cumulative mass, the concept set, phi and halt. Headline: memory_path_dependence = fraction of recognised same-stimulus re-exposure transitions that land on strictly more permanent scars; VALIDATED iff >= 1.0 AND whole-run scars monotonic. INCONCLUSIVE if fewer than 6 recognised transitions. Cross-check (scipy Spearman): scar depth vs exposure ordinal, rho > 0 + p < 0.05. Permanence, accumulation slopes, halt-flip rate and phi-rigidity are reported as evidence; none post-hoc-claimable._

## 4. Data

- Substrate: `kimera-swm` @ `058a709b52b4`
- Dataset: `kimera-memory-permanence-trajectory` (substrate-trajectory+scar-accumulation, 36 records, hash `548d6568d12e…`)

## 5. Evidence

| pillar | statistic | value | 95% CI | library |
|---|---|---|---|---|
| `O.flow.memory_path_dependence` | `memory_path_dependence` | `1.0` | — | ophamin 0.109.0 |

## 6. Signature

`3a1eb9735f927eaf6383028eb6782a0f1996f7a0524752849a2e36164e1392b4`
