# Reproducer — Logic-Topology Siege (Walker sustained-traversal rate)

> External-reviewer walkthrough for the `LogicTopologySiegeScenario`
> proof family (2 shipped, both REFUTED). Companion to
> [`immune_siege.md`](immune_siege.md).

## 1. The pre-registered claim

| Field | Value |
|---|---|
| `metric` | `walker_sustained_traversal_rate` |
| `comparator` | `>=` |
| `value` | `0.6` (60 %) |
| `H0` | sustained-traversal rate < 0.6 |
| `H1` | sustained-traversal rate >= 0.6 |

In plain terms: on real technical-domain text (Linux kernel
commit messages) that clears Kimera's GWF, the substrate's
prime-topology Walker reaches **sustained traversal** (halt
mode = `exhausted`, indicating the cognitive cycle ran to
natural completion) in at least 60 % of cycles. This tests
whether the Walker can sustain meaningful traversal on
domain-rich technical input, not just terminate via
`amplitude_death` (collapse) or `selective` (early exit).

## 2. The 2 shipped proofs — both REFUTED

| Proof file | Verdict | Observed | Kimera commit |
|---|---|---|---|
| [`logic_topology_siege_19b0e547908eeaf7.json`](../logic_topology_siege_19b0e547908eeaf7.json) | `REFUTED` | 39.6 % (262/661 GWF-cleared) | `a9145ac8…` |
| [`logic_topology_siege_94e389abcd63c96c.json`](../logic_topology_siege_94e389abcd63c96c.json) | `REFUTED` | 39.9 % (264/661 GWF-cleared) | `4552de7e…` |

Both runs use the same Linux-kernel-commit corpus and produce
nearly identical observed rates (within 0.3 pp of each other,
well inside the Wilson 95 % CI half-width at n=661 ≈ ±3.7 pp).
**The 20-percentage-point gap below the 60 % threshold is robust
across two Kimera commits** — this is a real engineering
observation about Kimera's Walker behaviour on technical-domain
text, not a measurement artifact.

Halt-mode distribution (from both proofs):

| Halt mode | Share |
|---|---|
| `exhausted` (sustained traversal — the "good" path) | ~40 % |
| `amplitude_death` (collapse before completion) | ~28-29 % |
| `selective` (early exit on insufficient signal) | ~31 % |

**The empirical finding the REFUTED proofs surface**:
amplitude_death is firing on ~28 % of GWF-cleared cycles on
technical-domain text. The Walker is collapsing before
reaching sustained-traversal, which the framework's discipline
records honestly rather than hides.

GWF on this corpus blocks 33.9 % (much higher than the 10 %
ceiling on immune_siege's adversarial corpus — Linux kernel
commits trigger many false-positive cyber-vocabulary blocks,
matching the GWF cybersecurity-vocab FP limit documented in
Kimera-side CLAUDE.md).

Φ median 0.209; dissonance median 28.

## 3. Verify a proof signature

```bash
ophamin schema validate proofs/logic_topology_siege_19b0e547908eeaf7.json
```

(See [`immune_siege.md`](immune_siege.md) §3 for full recipe
templates.)

## 4. Re-run the scenario

```bash
PYTHONPATH=src .venv/bin/python -u examples/run_logic_topology_siege.py
```

**Corpus requirement**: Linux kernel commit-message corpus
(~1.4 M commits). Loader at
`src/ophamin/seeing/corpus/`. The scenario draws a balanced
1000-cycle sample by default.

## 5. Spot-check (small subset)

```python
from ophamin.measuring.scenarios import LogicTopologySiegeScenario
from ophamin.measuring.scenarios.base import DEFAULT_SIGN_KEY
from ophamin.seeing.substrate import KimeraAdapter

substrate = KimeraAdapter("/path/to/your/Kimera-SWM", target="entity")
scenario = LogicTopologySiegeScenario(n_cycles=100)
proof = scenario.run(substrate=substrate).sign(DEFAULT_SIGN_KEY)
print(f"verdict: {proof.verdict.outcome}; observed: {proof.verdict.observed_value:.3f}")
```

Expected: REFUTED with observed value in the 0.35-0.45 band
(matching the shipped 0.396-0.399). The Walker amplitude_death
on technical text is a substrate property; the spot-check should
reproduce the REFUTED direction reliably.

## 6. What this proof family demonstrates

1. **REFUTED proofs are first-class outcomes**. The framework
   surfaces an honest engineering observation (Walker
   amplitude_death on technical-domain text) that a discretionary
   verdict-system would suppress.
2. **Cross-commit robustness of REFUTED**: both Kimera commits
   land in the same observed band, ~20 pp below threshold.
   The gap is robust, not version-fragile.
3. **Cross-claim resonance**: GWF FP rate ~33.9 % on Linux
   commits matches the cybersecurity-vocab FP limit observed
   in immune_siege and discussed in Kimera-side `CLAUDE.md` —
   different scenarios surfacing the same substrate limit
   from different angles.

## See also

- [`immune_siege.md`](immune_siege.md) — companion reproducer doc.
- [`src/ophamin/measuring/scenarios/logic_topology_siege.py`](../../src/ophamin/measuring/scenarios/logic_topology_siege.py) — scenario source.
- [`examples/run_logic_topology_siege.py`](../../examples/run_logic_topology_siege.py) — canonical runner.
