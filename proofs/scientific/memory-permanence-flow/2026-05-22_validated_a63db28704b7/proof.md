# Empirical Proof Record — **VALIDATED**

**Proof ID:** `a63db28704b781f2ffd08558719d4446d4e1738e272e53c6bd853e916fefe521`  
**Created:** 2026-05-22T17:09:46.396192+00:00

## 1. Claim

> When an identically-recognised probe is re-exposed across a trajectory, it lands on a strictly-deeper (more-scarred) manifold every time: memory_path_dependence = (recognised re-exposure transitions with Δ permanent-scars > 0) / (recognised re-exposure transitions) >= 1.0, with the whole-run scar count monotonic non-decreasing (a scar cannot be reset). This measures memory where Kimera keeps it — the scars and the S4 manifold — not the content-recognition layer.

- **Operationalisation:** Run 8 stimuli each re-exposed 3x, interleaved (gap = len(stimuli)), through Kimera's entity target (Takwin) in batch mode so the substrate accumulates across the batch. Per cycle read vault_stats.total_scars_stored (canonical permanent scars), arachne_web_coupling_frobenius (manifold deformation), and the concept set (recognition). For each same-stimulus consecutive exposure pair: recognised iff Jaccard(concepts) >= 0.80; confirmed iff recognised AND Δ scars > 0. memory_path_dependence = confirmed / recognised. Forced to 0.0 (REFUTED) if the whole-run scar count ever decreases.
- **Threshold:** `memory_path_dependence >= 1.0 proportion`
- **H0:** H0: memory_path_dependence < 1.0 — some re-exposure of a recognised probe did NOT land on more permanent scars (the substrate re-derives without accumulating), or a scar was reset; not path-dependent permanent memory
- **H1:** H1: memory_path_dependence >= 1.0 — every re-exposure of a recognised probe lands on a strictly-deeper manifold and no scar is ever reset; path-dependent permanent memory in the scar/S4 substrate

## 2. Verdict

**Outcome:** VALIDATED  
**Observed:** `1.0`

memory_path_dependence 1.0000 = 16/16 recognised re-exposure transitions landed on strictly more permanent scars; 0 transitions failed recognition (excluded). Permanence: HOLDS (0 scar-count decreases over the run). Scars 1.0→24.0; coupling 1.293702→10.47013; phi |delta| mean 0.0000 (Φ-rigid → memory is in the scars/manifold, not Φ); scar-depth vs exposure-ordinal Spearman rho=0.9436, p=2.4e-12 (deepens with experience)

## 3. Pre-registration

- Registered at: `2026-05-22T17:09:46.139642+00:00`
- Config hash: `f5c0c3ae55bb8ed69287755ab991315a732fea6239797b9a59a4a16eead2d320`
- Data hash: `4e6090352a40ea27df1cf08fb4d02bd55c48c75253ece6e66e46809e7c3bc4a8`

_Build an interleaved re-exposure schedule (8 stimuli x 3 exposures, gap = 8); stream through Kimera's entity target in batch mode. Per cycle read the permanent scar count (vault_stats.total_scars_stored), the manifold coupling, the cumulative mass, the concept set, phi and halt. Headline: memory_path_dependence = fraction of recognised same-stimulus re-exposure transitions that land on strictly more permanent scars; VALIDATED iff >= 1.0 AND whole-run scars monotonic. INCONCLUSIVE if fewer than 6 recognised transitions. Cross-check (scipy Spearman): scar depth vs exposure ordinal, rho > 0 + p < 0.05. Permanence, accumulation slopes, halt-flip rate and phi-rigidity are reported as evidence; none post-hoc-claimable._

## 4. Data

- Substrate: `kimera-swm` @ `eba50120eadd`
- Dataset: `kimera-memory-permanence-trajectory` (substrate-trajectory+scar-accumulation, 24 records, hash `4e6090352a40…`)

## 5. Evidence

| pillar | statistic | value | 95% CI | library |
|---|---|---|---|---|
| `O.flow.memory_path_dependence` | `memory_path_dependence` | `1.0` | — | ophamin 0.109.0 |

## 6. Signature

`7bc3d8aed9ec1648ba5bb56d744be7458106bb98812314fd33fc56eafe0a7b5d`
