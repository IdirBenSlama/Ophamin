# Authoring a new Ophamin scenario

This guide is for the case where a new Kimera discovery — a field that
emerged, a behavior that shifted, a property worth testing — has surfaced and
you want to land it as a pre-registered, signed Empirical Proof Record.

Ophamin's scenarios are deliberately code, not config, because each one has
its own scoring shape. The shared infrastructure (`ophamin.scenario.helpers`)
makes the per-scenario file a thin layer over reusable building blocks.

## The shape of a scenario

A scenario is a `Scenario` subclass that:

1. names a **corpus** (one of the registered names in `ophamin.corpus`)
2. names a Kimera **target** (one of the registered targets in
   `ophamin.substrate.KimeraAdapter`)
3. builds a **pre-registered claim** with a falsifiable threshold
4. **selects records** from the corpus (optional filter / re-sampling)
5. **scores** the resulting `CycleResult` list against the threshold

The harness in `Scenario.run` does the rest: pre-registration capture,
substrate batch run, verdict, signed proof record, provenance graph.

## Boilerplate elimination

Before this layer existed, each scenario re-implemented:

- shape-aware extraction of `gwf_verdict`, `dissonance_events`, `canonical`,
  `prime`, `halt_mode`, `phi_value`;
- Wilson 95% CI computation;
- inconclusive guards (too few cycles / majority adapter errors);
- descriptive distribution summaries (median, mean, p10/p90).

All four are now in `ophamin.scenario.helpers`. Use them rather than rolling
your own — when Kimera shifts a field name, those helpers get updated in one
place rather than four.

## The minimal scenario

```python
from ophamin.measuring.proof import Claim, PillarEvidence, Threshold
from ophamin.measuring.scenarios import helpers
from ophamin.measuring.scenarios.base import Scenario, ScenarioScore, Tier


class MyNewScenario(Scenario):
    name = "my-new-scenario"

    # --- required metadata (Move A, 2026-05-16) ---
    tier = Tier.SCIENTIFIC          # SCIENTIFIC / ENGINEERING / PHILOSOPHICAL
                                    # / EMPIRICAL_DEEP / MEASUREMENT_MACHINERY
    family = "<family-tag>"         # e.g. "immune", "prime", "phi"; scenarios in the
                                    # same family probe the same substrate aspect from
                                    # different angles
    goal = (
        "<one-sentence statement of what question this scenario answers>"
    )
    explanation = (
        "<paragraph: why this scenario is interesting, what substrate "
        "property a verdict would tell us about, what is at stake>"
    )
    # --- optional metadata ---
    method = "<scoring-shape-tag>"  # e.g. "wilson_ci_proportion",
                                    # "jaccard_floor", "cohens_d_paired"
    falsification_consequence = (
        "<one-line of what a REFUTED verdict would mean concretely>"
    )
    # --- end metadata ---

    corpus_name = "<corpus-name>"          # enron, linux, flores, cyber, financial, the-well
    target = "<target-name>"               # entity, pentecost, ouroboros, rosetta, arachne,
                                           # walker, gwf, piovra, astrolabe, atlas, spde

    def __init__(self, n_cycles: int = 1000, threshold: float = 0.50) -> None:
        self.n_cycles = int(n_cycles)
        self.threshold = float(threshold)

    def build_claim(self) -> Claim:
        return Claim(
            statement=(
                f"On <corpus> records that <filter>, Kimera's <subsystem> "
                f"<property> in >= {self.threshold:.0%} of cycles."
            ),
            operationalization="fraction of cycles for which <predicate>",
            threshold=Threshold(
                "<metric_name>", ">=", self.threshold, "fraction"
            ),
            h0=f"P(<event> | <filter>) < {self.threshold}",
            h1=f"P(<event> | <filter>) >= {self.threshold}",
        )

    def score(self, cycle_results, records):
        cleared_total = 0
        cleared_event = 0
        adapter_errors = sum(1 for r in cycle_results if helpers.is_adapter_error(r))
        for result in cycle_results:
            if helpers.is_adapter_error(result):
                continue
            if helpers.gwf_cleared(result):            # adjust the filter
                cleared_total += 1
                if <YOUR-EVENT-CONDITION>:             # e.g. helpers.dissonance_count(result) >= 1
                    cleared_event += 1

        rate = cleared_event / cleared_total if cleared_total else 0.0
        lo, hi = helpers.wilson_95_ci(cleared_event, cleared_total)
        inconclusive, reason = helpers.is_inconclusive(
            n_cycles=len(cycle_results),
            adapter_errors=adapter_errors,
            n_denominator=cleared_total,
        )
        evidence = [
            PillarEvidence(
                pillar="<O.subsystem.metric>",
                statistic_name="<metric_name>",
                statistic_value=rate,
                library="statsmodels",
                library_version="0.14",
                ci_low=lo,
                ci_high=hi,
                cross_check="n/a",
                detail={
                    "cleared_event": cleared_event,
                    "cleared_total": cleared_total,
                    "ci_method": "wilson_95",
                },
            ),
        ]
        return ScenarioScore(
            observed_value=rate,
            evidence=evidence,
            inconclusive=inconclusive,
            reasoning=(
                f"event fired in {cleared_event}/{cleared_total} "
                f"cleared cycles ({rate:.1%}); "
                f"{len(cycle_results)} cycles, {adapter_errors} adapter errors"
                + (f"; {reason}" if reason else "")
            ),
        )
```

A simple-proportion scenario in this shape lands in ~80 lines.
Empirical-deep scenarios (Bayesian / causal / cross-channel-MI /
prime-structure) are typically 300–500 LOC because they orchestrate
multiple library backends.

Register the class in `src/ophamin/measuring/scenarios/__init__.py`'s
`SCENARIOS` dict so it's reachable from the `ophamin scenario <name>`
CLI surface. Write a runner in `examples/`; add tests in
`tests/test_scenario_*.py` using the `_SyntheticSubstrate` pattern (one
test file per scenario is the current convention).

## When you need more than the simple proportion shape

The 19 shipped scenarios cover several distinct scoring shapes:

| Shape | Example | What's different |
|---|---|---|
| Simple proportion (filter + event) | Organizational Dissonance, Logic-Topology Siege | The minimal scenario above is sufficient. |
| Labelled paired sample | Immune Siege | Computes false-positive AND detection rates on benign vs malicious labels; needs `select_records` for balanced interleave. |
| Group-by + all-K-agree | Rosetta Scaling | Each "group" is a set of K stimuli; score is the fraction of groups where all K landed on the same canonical. |
| Distribution-floor (Jaccard / divisibility / coverage) | Memory-As-Deformation, Prime Structure, Substrate Completeness | Score is the minimum or aggregate over many measurements (e.g. concept-Jaccard floor across re-exposure pairs). |
| Bayesian posterior contraction | Bayesian Φ Posterior | Score is the HDI contraction ratio at N vs theoretical-frequentist bound; depends on `arviz` + `pymc`. |
| Causal-graph recovery | Causal Discovery | Score is the count of significant directed links recovered by PCMCI; depends on `tigramite`. |
| Cross-channel mutual information | Cross-Channel MI | Score is a count of pairs above a MI floor; depends on `pyitlib` + `ennemi` (cross-check oracle). |
| Cross-instance determinism | Prime Cross-Instance | Score is an invariance fraction across N fresh Takwin processes. |

For the more elaborate shapes, look at the existing scenario files for
the pattern. The helpers library still applies — it just composes with
custom group / pair logic. Bayesian / causal / MI scenarios also use the
matching `bayesian_helpers.py` / `causal_helpers.py` / `analytic_helpers.py`
modules in `src/ophamin/measuring/`.

## The pre-registration discipline (load-bearing)

- The claim is **registered before** the substrate runs.
- The threshold is **falsifiable** — a value Kimera could fail to meet.
- The proof record is **signed** with `DEFAULT_SIGN_KEY` (HMAC-SHA256).
- The provenance graph captures both the substrate's and Ophamin's git commits.
- A REFUTED verdict is the framework working, not failing. Don't soften
  thresholds post-hoc to land VALIDATED.

If your discovery doesn't fit a pre-registrable claim shape — e.g. you want
to characterise a distribution rather than test a threshold — that's
descriptive evidence, not a claim. Capture it as `PillarEvidence` with
`cross_check="n/a"` and no surrounding `Threshold`. It still lands in the
proof record but is not part of the primary verdict.

## Layer A discovery: don't author blindly

Before writing a new scenario against a field you read about in Kimera's
docs, run `ophamin discover <kimera-repo>` to confirm the field actually
exists in `CycleResult.raw` on the current Kimera commit. The schema doc
saves you from writing a 300-line scenario against a renamed or removed
field.

## Layer C drift (when it ships)

Once Layer C is online, every scenario's secondary descriptive evidence
becomes a tracked trend across Kimera commits. Two practical implications:

- Add a **distribution PillarEvidence** for the underlying signal even when
  your primary claim is a single proportion. (This is the convention
  across the shipped scenarios.) Layer C reads the distribution stats,
  not just the proportion.
- Use **stable statistic names** across versions of the same scenario. If a
  scenario renames its statistic, drift detection treats it as a new metric
  (false-negative on real drift).
