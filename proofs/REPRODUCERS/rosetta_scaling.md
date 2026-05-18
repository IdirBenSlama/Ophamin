# Reproducer — Rosetta Scaling (canonical-agreement at K=10 languages)

> External-reviewer walkthrough for the `RosettaScalingScenario`
> proof family (1 shipped, REFUTED). The most load-bearing
> REFUTATION in the Kimera-side proof corpus — directly
> contradicts the Rosetta layer's universal-semantic-address
> promise at scale. Companion to
> [`immune_siege.md`](immune_siege.md).

## 1. The pre-registered claim

| Field | Value |
|---|---|
| `metric` | `rosetta_canonical_agreement_at_k10` |
| `comparator` | `>=` |
| `value` | `0.8` (80 %) |
| `H0` | canonical agreement at K=10 < 0.8 |
| `H1` | canonical agreement at K=10 >= 0.8 |

In plain terms: on sentence-aligned parallel text (FLORES-200),
Kimera's Rosetta layer should map the same sentence content to
the **same canonical address** across at least 80 % of sentence
groups when 10 languages are sampled per group. This is the
**universal-semantic-address promise** — Kimera's design
document names Rosetta as the layer that should canonicalize
the same meaning across languages to a stable substrate-internal
identifier.

## 2. The 1 shipped proof — REFUTED at 0/20 groups

| Proof file | Verdict | Observed | Kimera commit |
|---|---|---|---|
| [`rosetta_scaling_ed0bf071100bdebe.json`](../rosetta_scaling_ed0bf071100bdebe.json) | `REFUTED` | **0 % (0/20 groups all-agree)** | `1dc88186…` |

The full reasoning from §6:

> Rosetta canonical agreement at K=10: 0/20 groups all-agree (0.0%);
> prime agreement at K=10: 0/20 (0.0%); 1000 cycles, 0 adapter errors

**What this means**: out of 20 randomly-sampled FLORES-200
sentence groups, ZERO of them produced the same Rosetta
canonical address across all 10 sampled language translations.
The agreement rate is exactly **0** — not "below 80 %", not
"borderline" — **the universal-semantic-address promise fails
completely** at the K=10 language scale on this Kimera commit.

The prime-level agreement (whether the same prime ID is emitted
across language translations) is also 0/20 — confirming the
Rosetta canonical layer AND the prime-emission layer both
fail to recognize the same sentence content across languages
at this scale.

## 3. Why this REFUTED proof matters

This is **the most load-bearing single REFUTATION** in the
Kimera-side proof corpus. The claim it refutes is not a
peripheral engineering metric — it's one of Kimera's
flagship cognitive properties (universal semantic addresses
that survive language translation).

The framework's discipline of routing this to REFUTED rather
than INCONCLUSIVE or VALIDATED-with-margin is the difference
between empirical honesty and marketing. A discretionary
verdict system could:

- Have softened the threshold post-hoc (lower than 80 %).
- Sampled fewer languages (K=3 might agree more often).
- Reported just the partial agreement (some groups might
  agree on 7 of 10 languages even if not all 10).

Ophamin's discipline shows the raw 0/20 result against the
pre-registered 80 % threshold. The verdict is mechanical, and
the substrate's cross-language Rosetta layer has a real gap.

Secondary descriptive evidence in the proof reports agreement
at K ∈ {3, 5, 10, 20, 50} — the K=10 case is the pre-registered
threshold, but the full curve is in the record for owner /
reviewer inspection.

## 4. Verify a proof signature

```bash
ophamin schema validate proofs/rosetta_scaling_ed0bf071100bdebe.json
```

(See [`immune_siege.md`](immune_siege.md) §3 for full recipes.)

## 5. Re-run the scenario

```bash
PYTHONPATH=src .venv/bin/python -u examples/run_rosetta_scaling.py
```

**Corpus requirement**: FLORES-200 sentence-aligned parallel
text (997 records, 50 languages each). Source:
<https://dl.fbaipublicfiles.com/nllb/flores200_dataset.tar.gz>.

## 6. Spot-check (small subset)

```python
from ophamin.measuring.scenarios import RosettaScalingScenario
from ophamin.measuring.scenarios.base import DEFAULT_SIGN_KEY
from ophamin.seeing.substrate import KimeraAdapter

substrate = KimeraAdapter("/path/to/your/Kimera-SWM", target="rosetta")
scenario = RosettaScalingScenario(n_cycles=100)  # smaller sample
proof = scenario.run(substrate=substrate).sign(DEFAULT_SIGN_KEY)
print(f"verdict: {proof.verdict.outcome}; observed: {proof.verdict.observed_value:.3f}")
```

Expected: REFUTED with observed value near 0. The Rosetta
cross-language gap is a substrate property — it reproduces.

## 7. What this proof family demonstrates

1. **The framework surfaces architectural gaps.** Kimera's
   Rosetta layer was *intended* to canonicalize cross-language
   semantics; the empirical record shows that at K=10 languages
   it doesn't. This REFUTED proof is the cleanest example in
   the corpus of the framework's value-proposition: catching
   load-bearing claims that don't hold under measurement.
2. **Pre-registration is what makes this verdict load-bearing.**
   The 80 % threshold and the K=10 sampling scheme were declared
   before the run. The 0 % observed value isn't an exotic
   measurement-shape; it's the same comparator + threshold
   applied honestly.
3. **REFUTED is a research signal, not a bug.** A Kimera-side
   investigation should follow: is this a regression in a
   specific commit? Does the agreement curve improve at K=3?
   Are there specific language pairs that DO agree? Those
   questions are downstream of the proof; the proof itself
   is the trigger.

## See also

- [`immune_siege.md`](immune_siege.md) — companion reproducer doc.
- [`src/ophamin/measuring/scenarios/rosetta_scaling.py`](../../src/ophamin/measuring/scenarios/rosetta_scaling.py) — scenario source.
- [`examples/run_rosetta_scaling.py`](../../examples/run_rosetta_scaling.py) — canonical runner.
- Kimera-side `CLAUDE.md` §"Rosetta — universal semantic address" — the architectural claim this proof tests.
