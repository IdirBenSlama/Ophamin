# Reproducer — Organizational Dissonance (firing rate on routine email)

> External-reviewer walkthrough for the `OrganizationalDissonanceScenario`
> proof family (2 shipped, both VALIDATED). Companion to
> [`immune_siege.md`](immune_siege.md) (§3 + §6 templates apply here).

## 1. The pre-registered claim

| Field | Value |
|---|---|
| `metric` | `dissonance_firing_rate` |
| `comparator` | `>=` |
| `value` | `0.9` (90 %) |
| `H0` | dissonance firing rate < 0.9 |
| `H1` | dissonance firing rate >= 0.9 |

In plain terms: on routine organizational email that clears
Kimera's GWF, the dissonance machinery fires reliably — at least
90 % of GWF-cleared cycles produce a non-empty
`dissonance_events` list. This tests whether Kimera's
dissonance-detection subsystem is actually **on** under
benign-input load, not just **theoretically wired**.

## 2. The 2 shipped proofs — both VALIDATED

| Proof file | Verdict | Observed | Kimera commit |
|---|---|---|---|
| [`organizational_dissonance_2b851750908b068f.json`](../organizational_dissonance_2b851750908b068f.json) | `VALIDATED` | 96.4 % (866/898 GWF-cleared) | `4552de7e…` |
| [`organizational_dissonance_b71961a6e5fb9b10.json`](../organizational_dissonance_b71961a6e5fb9b10.json) | `VALIDATED` | 97.4 % (875/898 GWF-cleared) | `83d4655b…` |

Both runs use the same Enron email corpus (data hash
`83109a27c3df2a45…`, ~500K records, balanced sample of 1000).
Both pass the 90 % threshold at margin (6.4-7.4 percentage
points above). The 1.0 pp drift between commits is within the
expected sample-size variance for a ~898-cycle denominator
(95 % CI half-width ≈ ±1.0 pp at p=0.96, n=898).

**What both proofs jointly demonstrate**: dissonance firing
on routine email is a **robust substrate property** across
Kimera commits, not a one-off measurement. Empirical envelope
confirmed at ≥ 96 % firing rate.

Secondary descriptive evidence (from both proofs):

- GWF blocks ~10.2 % of inputs (matching the FP ceiling pinned
  by `immune_siege`; same architectural ceiling, different
  corpus shape).
- manipulation_detector fires on ~0.3 % of inputs (rare on
  benign email — expected).
- median dissonance_events per cycle: 21-22 (range 0-57).

## 3. Verify a proof signature

See [`immune_siege.md`](immune_siege.md) §3 for Python / Rust /
JS recipes. Quick Python check:

```bash
ophamin schema validate proofs/organizational_dissonance_b71961a6e5fb9b10.json
# Expected: OK    .../organizational_dissonance_b71961a6e5fb9b10.json: proof@1.0
#           summary: 1 ok, 0 failed
```

## 4. Re-run the scenario

```bash
PYTHONPATH=src .venv/bin/python -u examples/run_organizational_dissonance.py
```

**Corpus requirement**: Enron email corpus (~500K records).
See `src/ophamin/seeing/corpus/` for the canonical loader. The
scenario draws a balanced 1000-record sample by default; full
run takes ~10-20 minutes.

**Hardcoded runner constants**: `REPO`, `N_CYCLES`, threshold —
same edit pattern as `examples/run_immune_siege.py`. The
threshold is 0.9 (the 90 % architectural claim).

## 5. Spot-check (small subset)

Edit `N_CYCLES` in `examples/run_organizational_dissonance.py`
from 1000 to 100, OR construct directly:

```python
from ophamin.measuring.scenarios import OrganizationalDissonanceScenario
from ophamin.measuring.scenarios.base import DEFAULT_SIGN_KEY
from ophamin.seeing.substrate import KimeraAdapter

substrate = KimeraAdapter("/path/to/your/Kimera-SWM", target="entity")
scenario = OrganizationalDissonanceScenario(n_cycles=100)
proof = scenario.run(substrate=substrate).sign(DEFAULT_SIGN_KEY)
print(f"verdict: {proof.verdict.outcome}; observed: {proof.verdict.observed_value:.3f}")
```

Expected: VALIDATED with observed value in the 0.94-0.98 band
(Wilson 95 % CI half-width ≈ ±3 pp at n=100; verdict direction
matches the shipped proofs).

## 6. Cross-proof diff

Both shipped proofs are VALIDATED; the meaningful diff is the
**observed-value drift across Kimera commits** (96.4 % → 97.4 %,
a 1.0 pp lift). Either:

- Genuine substrate change (newer commit makes dissonance fire
  slightly more reliably), or
- Sample-size noise (within the 95 % CI half-width at n=898).

A reviewer running 3+ fresh proofs at each commit could
distinguish via a 2-sample test on the proportion. The framework
ships the raw evidence so this is reviewable from the proofs alone.

## 7. What this proof family demonstrates

Same template as [`immune_siege.md`](immune_siege.md) §7,
applied to a VALIDATED-only family rather than a VALIDATED +
REFUTED mix:

1. **Pre-registration** — 90 % is the architectural claim
   Kimera's dissonance design names. Not chosen post-hoc.
2. **Mechanical verdict** — both 0.964 and 0.974 satisfy `>= 0.9`
   → VALIDATED. No discretion.
3. **Cross-commit robustness** — both Kimera commits produce
   VALIDATED proofs. Empirical envelope is robust.
4. **Companion to immune_siege's GWF discipline** — both
   scenarios use the offensive-security-style corpus + measure
   GWF-cleared cycles. organizational-dissonance answers
   *"once GWF lets a cycle through, does the substrate process
   it dissonantly?"*; immune_siege answers *"how often does
   GWF block benign cycles?"*. Together they characterize the
   substrate's input-classification envelope.

## See also

- [`immune_siege.md`](immune_siege.md) — companion reproducer doc.
- [`src/ophamin/measuring/scenarios/organizational_dissonance.py`](../../src/ophamin/measuring/scenarios/organizational_dissonance.py) — scenario source.
- [`examples/run_organizational_dissonance.py`](../../examples/run_organizational_dissonance.py) — canonical runner.
- [`proofs/INDEX.md`](../INDEX.md) — full proof catalogue.
