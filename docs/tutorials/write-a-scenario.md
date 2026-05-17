# Write a new scenario

A scenario binds a corpus + a substrate target + a pre-registered
falsifiable claim, runs the corpus through the substrate, and emits a
signed Empirical Proof Record. New scenarios should land in ~80 LOC
(analytic-deep scenarios may run 300–500 LOC).

This tutorial is the **practitioner** view. The
**authoritative reference** lives at
[`docs/SCENARIO_AUTHORING.md`](../SCENARIO_AUTHORING.md) — read both;
they don't duplicate.

## The five-step anatomy

Every scenario is a subclass of `ophamin.measuring.scenarios.base.Scenario`
that overrides:

```python
class MyScenario(Scenario):
    # 1. Identity + metadata (required class attributes)
    name = "my-scenario"               # CLI handle
    tier = Tier.SCIENTIFIC             # five tiers (see below)
    family = "harness"                 # logical grouping for proof storage
    goal = "..."                       # one-line plain-English aim
    explanation = "..."                # paragraph for `ophamin scenario show`
    corpus_name = "my-corpus"          # which corpus to feed
    target = "any"                     # substrate target slot
    n_cycles = 100                     # how many records to run

    # 2. The falsifiable claim
    def build_claim(self) -> Claim: ...

    # 3. Record selection from the corpus
    def select_records(self, corpus): ...

    # 4. The pillar that decides verdict
    def score(self, cycle_results, records) -> ScenarioScore: ...

    # 5. The plain-English analysis plan (for pre-registration)
    def analysis_plan(self) -> str: ...
```

That's it. The base class handles:

- corpus loading + availability check
- record streaming + `n_cycles` truncation
- pre-registration capture (config_hash + data_hash + analysis_plan)
- substrate batching via `substrate.run_batch(stimuli)`
- field-contract validation against the first successful cycle
- verdict decision via `Verdict.decide(observed, threshold)`
- signed proof emission with HMAC-SHA256

## The five experimentation tiers

| Tier | What the claim is about |
|---|---|
| `SCIENTIFIC` | substrate *behaviour* (e.g. GWF false-positive ≤ 10%) |
| `ENGINEERING` | substrate *cost* (e.g. p95 wall-time ≤ 5s) |
| `PHILOSOPHICAL` | substrate *self-model* (e.g. dissonance on self-reference) |
| `MEASUREMENT_MACHINERY` | the *measurement apparatus* (e.g. Bayesian posterior contracts as √N) |
| `STRUCTURAL` | substrate *shape* (e.g. orphan rate ≤ 20%) |

Pick the tier that matches what the scenario is actually claiming.
When in doubt, `SCIENTIFIC` is the safe default.

## Worked example — a minimal scenario

```python
from ophamin.measuring.scenarios.base import Scenario, ScenarioScore, Tier
from ophamin.measuring.proof import Claim, PillarEvidence, Threshold

class HelloOphaminScenario(Scenario):
    name = "hello-ophamin"
    tier = Tier.SCIENTIFIC
    family = "harness"
    goal = "demonstrate the scenario authoring API end-to-end"
    explanation = (
        "Stream N records through the substrate; count successful "
        "cycles; assert ≥ 80%."
    )
    corpus_name = "flores"             # any registered corpus
    target = "any"
    n_cycles = 50

    def build_claim(self) -> Claim:
        return Claim(
            statement="≥ 80% of cycles succeed",
            operationalization="count cr.success / total cycles",
            threshold=Threshold(
                metric="success_rate", comparator=">=", value=0.8
            ),
            h0="success_rate < 0.8",
            h1="success_rate >= 0.8",
        )

    def select_records(self, corpus):
        return corpus.records()  # default streaming

    def score(self, cycle_results, records):
        n_success = sum(1 for cr in cycle_results if cr.success)
        rate = n_success / max(len(cycle_results), 1)
        return ScenarioScore(
            observed_value=rate,
            inconclusive=False,
            reasoning=f"{n_success} / {len(cycle_results)} = {rate:.3f}",
            evidence=(
                PillarEvidence(
                    pillar="harness",
                    statistic_name="success_rate",
                    statistic_value=rate,
                    library="ophamin",
                    library_version="0.8.0",
                ),
            ),
        )

    def analysis_plan(self) -> str:
        return "Count successful cycles; ratio; decide against 0.8 threshold."
```

## Wiring it in

If you want the scenario discoverable by `ophamin scenario list`,
register it in `src/ophamin/measuring/scenarios/__init__.py`:

```python
from ophamin.measuring.scenarios.hello_ophamin import HelloOphaminScenario

SCENARIOS["hello-ophamin"] = HelloOphaminScenario
```

For one-off / test-only scenarios that shouldn't pollute the registry,
declare with `class MyScenario(Scenario, register=False):`.

## Test it

Add a test in `tests/test_my_scenario.py`:

```python
def test_my_scenario_validates_on_happy_path():
    s = HelloOphaminScenario()
    proof = s.run(MockSubstrate(seed=42))
    assert proof.verdict.outcome == "VALIDATED"
    assert proof.signature  # signed
```

Run:

```bash
pytest tests/test_my_scenario.py
```

## Submit it

If it's a non-trivial design decision (new tier? new corpus type?
new field-contract shape?), follow the
[RFC process](../rfc/README.md). Otherwise a regular PR is fine.

Reference checklist on the PR before merging:

- [ ] Class metadata (`name`, `tier`, `family`, `goal`, `explanation`)
      all filled in
- [ ] `build_claim` returns a Claim with a Threshold (the falsifiable
      line)
- [ ] `score` returns a `ScenarioScore` with at least one
      `PillarEvidence` row
- [ ] Tests pass against `MockSubstrate`
- [ ] Example runner under `examples/run_<scenario>.py` (if applicable)
