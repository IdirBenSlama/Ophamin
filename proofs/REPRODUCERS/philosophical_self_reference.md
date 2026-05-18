# Reproducer — Philosophical Self-Reference (Cohen's d on dissonance)

> External-reviewer walkthrough for the
> `PhilosophicalSelfReferenceScenario` proof family (1 shipped,
> REFUTED). The Philosophical-tier scenario — tests whether
> Kimera differentially processes content **about itself**.
> Companion to [`immune_siege.md`](immune_siege.md).

## 1. The pre-registered claim

| Field | Value |
|---|---|
| `metric` | `dissonance_cohens_d_self_ref_vs_neutral` |
| `comparator` | `>=` |
| `value` | `0.3` (Cohen's *d*; one-sided) |
| `H0` | Cohen's *d* < 0.30 |
| `H1` | Cohen's *d* >= 0.30 |

In plain terms: when fed text describing Kimera's own primitives
(self-referential content, hand-curated from `CLAUDE.md`), the
substrate's dissonance signal — `dissonance_events_count` per
cycle — should be measurably **higher** than on neutral text
(Enron emails) by a one-sided Cohen's *d* effect size of at
least 0.30 ("small-to-medium" by Cohen's convention).

A REFUTED verdict means the substrate **does not differentially
process content about itself** — its dissonance signal is
indistinguishable, or LOWER, on self-referential text than on
neutral text.

## 2. The 1 shipped proof — REFUTED with negative d

| Proof file | Verdict | Observed | Kimera commit |
|---|---|---|---|
| [`philosophical_self_reference_95588bfe0b136bd7.json`](../philosophical_self_reference_95588bfe0b136bd7.json) | `REFUTED` | **d = −0.359** (NEGATIVE) | `179edd23…` |

The full reasoning from §6:

> Cohen's d (self_ref - neutral)/pooled_sd = −0.359;
> self_ref dissonance: n=30 median=17.0 mean=17.37 (range 0-29);
> neutral dissonance: n=30 median=20.0 mean=20.73 (range 0-45);
> Mann-Whitney U=323.0, one-sided p=0.9705; 60 cycles, 0 adapter errors

**The empirical finding**: the observed Cohen's *d* is **negative**
(−0.359) — meaning Kimera produces **less** dissonance on
self-referential text than on neutral Enron emails. The direction
is opposite to H1, by a small-to-medium effect size.

The supporting non-parametric check (Mann-Whitney U=323.0,
one-sided p=0.97) corroborates the direction: 97 % probability
that a randomly-drawn self_ref dissonance is **less than** a
randomly-drawn neutral dissonance, the opposite of what H1
predicts.

The mechanical verdict is REFUTED because `-0.359 >= 0.30` is
False. The framework would also have REFUTED at d = 0 (no
difference) or d = 0.1 (below threshold). The specific finding
here is stronger: not "no effect" but "effect in the WRONG
direction".

## 3. Why this REFUTED proof is interesting

Empirically: Kimera processes neutral Enron emails with **more**
dissonance than text describing its own primitives. Possible
interpretations (out of scope of the proof itself):

- Self-referential text is more **structured** (it follows a
  curated CLAUDE.md narrative); Enron emails are messier prose
  that triggers more substrate-level dissonance.
- Kimera has internal coherence-priors when processing
  descriptions of its own primitives that suppress dissonance
  events.
- The 30-sentence sample size for each group is small (n=30,
  total 60 cycles); the effect is small-to-medium but the
  Mann-Whitney p=0.97 is reassuring on the direction.

The proof's discipline doesn't try to interpret. The mechanical
verdict says: the claim of "differential processing of
self-referential content" does **not** hold under this
operationalization on this Kimera commit. A Kimera-side
follow-up could test:

- Different operationalization (Φ instead of dissonance?
  prime-emission entropy?).
- Different self-ref corpus (longer / less curated samples).
- Larger n (60 → 200 cycles).

## 4. Verify a proof signature

```bash
ophamin schema validate proofs/philosophical_self_reference_95588bfe0b136bd7.json
```

## 5. Re-run the scenario

```bash
PYTHONPATH=src .venv/bin/python -u examples/run_philosophical_self_reference.py
```

**Corpus requirement**: Enron email corpus (the neutral baseline).
Self-referential corpus is hand-curated in the runner script
from `CLAUDE.md` excerpts.

## 6. Spot-check

The shipped proof uses n=30 self_ref + n=30 neutral. For a
smaller spot-check, edit `examples/run_philosophical_self_reference.py`'s
sample-size constants or construct directly:

```python
from ophamin.measuring.scenarios import PhilosophicalSelfReferenceScenario
from ophamin.measuring.scenarios.base import DEFAULT_SIGN_KEY
from ophamin.seeing.substrate import KimeraAdapter

substrate = KimeraAdapter("/path/to/your/Kimera-SWM", target="entity")
# Default ctor — small fixed sample
scenario = PhilosophicalSelfReferenceScenario()
proof = scenario.run(substrate=substrate).sign(DEFAULT_SIGN_KEY)
print(f"verdict: {proof.verdict.outcome}; d: {proof.verdict.observed_value:.3f}")
```

Expected: REFUTED with negative or near-zero d. The direction
(self_ref < neutral) reproduces; the magnitude varies with the
specific Kimera commit's dissonance dynamics.

## 7. What this proof family demonstrates

1. **The framework distinguishes "no effect" from "wrong-direction
   effect".** A discretionary verdict system might have reported
   "d = 0" (rounded) or "p > 0.05" (NS). Ophamin reports the
   raw signed *d* = −0.359; the negative sign is load-bearing
   information.
2. **Pre-registration prevents post-hoc reframing.** The
   reasonable post-hoc question — "what if the substrate
   processes self-ref text LESS dissonantly than neutral?" —
   has no privileged answer here; H1 was one-sided (self_ref >
   neutral), so observing the opposite direction is REFUTED,
   not a discovery to claim.
3. **Substrate-cognitive-property scenarios are first-class.**
   The Philosophical tier (per `docs/index.md`'s tier framing)
   captures claims about substrate self-model. REFUTED here
   doesn't mean Kimera lacks a self-model; it means *this
   particular operationalization* of self-reference fails to
   measurably affect dissonance. Other operationalizations
   remain testable.

## See also

- [`immune_siege.md`](immune_siege.md) — companion reproducer doc.
- [`src/ophamin/measuring/scenarios/philosophical_self_reference.py`](../../src/ophamin/measuring/scenarios/philosophical_self_reference.py) — scenario source.
- [`examples/run_philosophical_self_reference.py`](../../examples/run_philosophical_self_reference.py) — canonical runner.
