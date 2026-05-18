# Proposal — Working reproduction commands in §7 of every emitted proof

> **Status:** **CLOSED at 0.30.0**. All 32 registered scenarios
> now emit working §7 reproduction commands via the
> ``Scenario._build_reproduction_command()`` helper. The R1
> refactor recommended in this proposal landed in full.
> **Discovered while drafting:** [`proofs/REPRODUCERS/immune_siege.md`](https://github.com/IdirBenSlama/Ophamin/blob/main/proofs/REPRODUCERS/immune_siege.md) (0.28.0).
> **Tier:** Tier-2 (substrate-touching but reversible + scoped).

## Update (0.30.0) — R1 refactor landed in full

The shared helper [`Scenario._build_reproduction_command()`](https://github.com/IdirBenSlama/Ophamin/blob/main/src/ophamin/measuring/scenarios/base.py)
now lives on the base class and routes through three cases:

1. **`runner_path` set** → emits `python -u {runner_path}`
   pointing at the hand-rolled runner script. Used by the 6
   scenarios listed below.
2. **No `runner_path` + default-instantiable ctor** → emits
   `python examples/run_scenario.py {name}` pointing at the
   generic runner. Used by 10 scenarios (the cross-framework
   crosscheck tier + a few others).
3. **No `runner_path` + required ctor args** → emits an inline
   `python -c "<verbose snippet>"` form that captures the actual
   arg values from `self.<name>` and is *literally runnable* when
   copy-pasted. Used by 16 scenarios (the empirical-deep tier
   that needs trajectory paths + the 2 structural scenarios that
   need Kimera repo paths).

All 26 scenarios that previously hardcoded the stale `ophamin.cli
scenario {name}` form now call the helper instead. The 6
hand-rolled-runner scenarios already routed through the base.py
emission path; nothing changes for them.

**Verified**: 11 hardening tests pin all 3 routing cases plus the
"no stale string remaining" structural invariant. 144 tests pass
across the regression-sensitive suites. End-to-end smoke confirms
each of the 3 routing cases emits the correct shape.

## Update (0.29.0) — partial Option-C fix landed

The fix landed at 0.29.0 covers the **6 hand-rolled-runner
scenarios** (`concentrated-immune-siege`, `logic-topology-siege`,
`organizational-dissonance`, `philosophical-self-reference`,
`rosetta-scaling`, `throughput-ceiling`):

- [`base.py`](https://github.com/IdirBenSlama/Ophamin/blob/main/src/ophamin/measuring/scenarios/base.py)
  gained the opt-in `runner_path: str = ""` class attribute on
  the `Scenario` base.
- Each of the 6 scenarios above declares its
  `runner_path = "examples/run_<name>.py"`.
- The Reproduction.command emission in base.py is now conditional:
  `runner_path`-set → `python -u {runner_path}`; otherwise →
  fallback to `run-all --scenarios {name}`.
- 9 hardening tests pinned in
  [`tests/test_runner_path_reproduction.py`](https://github.com/IdirBenSlama/Ophamin/blob/main/tests/test_runner_path_reproduction.py).

**Validated**: fresh proofs from any of the 6 scenarios now emit
a §7 reproduction command that points at a working runner script.

## Wider scope discovered (still open) — CLOSED 0.30.0

While implementing the 0.29.0 fix, surfaced that **26 of 32
scenarios bypass the base.py emission path entirely** — each one
constructs its own `EmpiricalProofRecord` with a hand-built
`Reproduction.command` string. The hand-built strings carry the
same stale `ophamin.cli scenario {name}` form, often with
per-scenario CLI flags (`--n-pairs`, `--n-datasets`,
`--trajectory-path`, `--target-scenario`, `--threshold`,
`--kimera-repo`, etc.) that the current CLI never had.

Inventory of affected scenarios (all 26 contain hardcoded stale
strings; none of them benefit from the 0.29.0 partial fix):

```
anova_crosscheck, bayesian_phi_posterior,
bayesian_phi_posterior_crosscheck, causal_discovery, crdt_laws,
cross_channel_mutual_information, deterministic_seed_audit,
interface_contract_stability, mann_whitney_crosscheck,
memory_as_deformation, pearson_crosscheck, prime_cross_instance,
prime_direct_lookup, prime_ecosystem, prime_factorization,
prime_structure, proprio_self_discovery, quantum_basis_correlation,
sinew_conservation, sinew_modulation_disruption,
sinew_wider_unification, spearman_crosscheck, substrate_completeness,
tonus_conservation_discovery, welch_t_crosscheck,
wilson_ci_crosscheck
```

Some have required ctor args (e.g. `cross_channel_mi` needs
`trajectory_path`); these cannot be reproduced via a generic
runner — they need their own runner script OR an inline-Python
form.

## Recommended follow-up (after 0.29.0)

The remaining 26 sites need one of two follow-ups, owner pick:

**(R1) Refactor each of the 26 to call a shared helper.** Add
`Scenario._build_reproduction_command()` to base.py; refactor each
hardcoded site to call it. Helper logic:

- If `runner_path` is set → `python -u {runner_path}`
- Else if scenario has a generic-runnable constructor (no required
  args beyond defaults) → `python examples/run_scenario.py {name}`
- Else (required ctor args) → emit an inline-Python snippet that
  constructs the class with default kwargs + signs the proof.

**Effort**: ~80 LOC across 27 files (26 scenarios + base helper).
Mechanical refactor; low semantic risk per file. Pinned by an
extended version of `test_runner_path_reproduction.py`.

**(R2) Author dedicated runner scripts for the 26.** Match the
6-scenario pattern: write `examples/run_<name>.py` for each
crosscheck / empirical-deep / structural scenario. Then add
`runner_path` to each.

**Effort**: ~1-2 hours per scenario × 26 = 26-52 hours. Tedious
but produces hand-tailored runners for each scenario (per-scenario
defaults, hardcoded sample sizes, etc.).

Recommendation: **R1**. The 26 hardcoded strings are uniform in
shape; one helper closes them all. R2 is overkill for scenarios
whose CLI surface is exactly "construct with defaults + run".

---

## Original finding (preserved for trail)

## Finding

Every Ophamin scenario populates `EmpiricalProofRecord.reproduction.command` from a single line in [`src/ophamin/measuring/scenarios/base.py:464-466`](https://github.com/IdirBenSlama/Ophamin/blob/main/src/ophamin/measuring/scenarios/base.py):

```python
reproduction=Reproduction(
    command=f"PYTHONPATH=src .venv/bin/python -m ophamin.cli scenario {self.name}"
),
```

That command **does not work** under the current CLI surface. The
`ophamin scenario` subcommand was refactored at some earlier point
into a list / show / info **umbrella** — it no longer accepts a
scenario name as a positional. An external reviewer copying §7
verbatim from any shipped proof gets:

```text
$ ophamin scenario concentrated-immune-siege
usage: ophamin scenario [-h] action ...
ophamin scenario: error: invalid choice: 'concentrated-immune-siege'
(choose from 'list', 'show', 'info')
```

Every proof emitted since the CLI refactor carries this stale
string. The signatures verify regardless (the `command` field is
metadata, not load-bearing for the canonical bytes), but the
**reproducer contract is broken at the §7 surface**.

## What's broken vs what's fine

- ✅ The proof's signature still verifies. The wire-format
  contract is unaffected.
- ✅ The shipped proofs' bodies are sealed and cannot/should not
  be modified — historical metadata of how each proof was emitted
  at the time.
- ❌ Future-emitted proofs carry the same stale string. Every
  fresh proof shipped today inherits the broken contract.
- ❌ External reviewers reading the proof's §7 get a non-working
  command on their first attempt.

## Workaround in place

[`proofs/REPRODUCERS/immune_siege.md`](https://github.com/IdirBenSlama/Ophamin/blob/main/proofs/REPRODUCERS/immune_siege.md)
§4 documents the actual working entry point
([`examples/run_immune_siege.py`](https://github.com/IdirBenSlama/Ophamin/blob/main/examples/run_immune_siege.py))
with a caveat box pointing out the §7 string is historical. This
is a per-proof-family doc patch — it scales linearly with the
number of proof families that need reproducer docs (13 shipped
proofs across ~7 families).

## Three options for the upstream fix

The workaround above closes the immediate gap for the
immune_siege family. To prevent the staleness re-appearing in
every future-emitted proof, one of these three:

### Option A — minimal one-line fix

Update `base.py:464-466` to emit a command that works against the
current CLI. The simplest working form:

```python
reproduction=Reproduction(
    command=f"PYTHONPATH=src .venv/bin/python -m ophamin.cli run-all --scenarios {self.name}"
),
```

`run-all --scenarios <name>` exists in the current CLI, accepts a
single scenario name (per [`cli.py`](https://github.com/IdirBenSlama/Ophamin/blob/main/src/ophamin/cli.py) cmd_run_all),
and produces a signed CampaignRecord plus the per-scenario proofs.

**Pros**: one-line change, no new CLI surface, immediate fix.
**Cons**: `run-all` produces a CampaignRecord wrapping the
proof; a reviewer expecting a direct proof JSON gets a directory.
The §7 promise of "this exact command reproduces this exact
record" gets fuzzier — fresh proof IDs and signatures naturally
differ from the shipped ones because the timestamp differs, but
the wrapping campaign layer introduces an extra hop.

### Option B — add an `ophamin scenario run <name>` subcommand

Add a new subcommand `run` to the `ophamin scenario` umbrella
that does what the old format implied: run one scenario, emit
one signed proof. Then update `base.py:464-466` to:

```python
reproduction=Reproduction(
    command=f"PYTHONPATH=src .venv/bin/python -m ophamin.cli scenario run {self.name}"
),
```

**Pros**: matches the historical command shape the proofs already
reference; no CampaignRecord wrapping hop; semantically aligned
with what the user expects (one scenario → one proof).

**Cons**: new CLI subcommand surface to maintain; ~30 LOC + pin
tests; some scenarios need substrate/dataset configuration that
default-instantiation doesn't cover (e.g. concentrated-immune-siege
needs a Kimera repo path) — the new subcommand needs sensible
defaults or `--repo` + `--target` flags mirroring `run-all`.

### Option C — auto-emit via per-scenario runner reference

Each scenario optionally declares a `runner_path` (or similar)
metadata field; if set, `Reproduction.command` uses it; otherwise
falls back to the `run-all --scenarios` form (Option A). For
immune_siege specifically:

```python
class ImmuneSiegeScenario(Scenario):
    runner_path = "examples/run_immune_siege.py"  # canonical runner
    ...
```

Then `base.py` emits:

```python
reproduction=Reproduction(
    command=(
        f"PYTHONPATH=src .venv/bin/python -u {self.runner_path}"
        if getattr(self, "runner_path", None)
        else f"PYTHONPATH=src .venv/bin/python -m ophamin.cli run-all --scenarios {self.name}"
    )
),
```

**Pros**: explicit per-scenario routing; multi-target scenarios
(like immune_siege which runs entity + gwf in one invocation)
get to declare their canonical runner script; backward compatible
for scenarios without a custom runner.

**Cons**: adds a new opt-in scenario metadata field; not all
scenarios HAVE a hand-rolled runner; risk of "two ways to express
the same thing" that drift apart.

## Recommendation

**Option C** is the architecturally cleanest and matches how the
framework already works (the `examples/run_*.py` runners exist
for the per-scenario hand-tailored cases, and `run-all` exists
for the generic case). It surfaces the existing per-scenario
runner distinction at the proof level.

But **Option A** is the immediate-fix that's safest under
cautious-mode review: one line, no new surface, no semantic shift
in what the `Reproduction.command` field guarantees. If we accept
that proofs emitted via `run-all --scenarios X` produce a
CampaignRecord-wrapped layer over the single proof (and the
external reviewer can extract the proof JSON from there), Option
A is the cheapest closure.

**Owner pick which option, agent executes.** Each option has a
clear PR shape:

- **A**: edit `base.py:464-466` (one line), update any tests
  pinning the string format if found, ship as 0.29.0.
- **B**: add `p_scen_run` subparser in `cli.py` + cmd_scenario_run
  handler + hardening test; edit `base.py:464-466`; ship as 0.29.0.
- **C**: add `runner_path` class attribute to `Scenario` base in
  `base.py`; add the conditional in `Reproduction.command`
  emission; update each existing hand-rolled scenario class that
  has a per-scenario runner (`concentrated-immune-siege`,
  `logic-topology-siege`, `organizational-dissonance`,
  `philosophical-self-reference`, `rosetta-scaling`,
  `throughput-ceiling` per `examples/run_*.py`); ship as 0.29.0.

## What this finding affects beyond reproducer docs

The §7 staleness has been latent in every released proof since
the CLI refactor. If the reproducer-doc cycle continues (one doc
per shipped proof family), each new doc gets the same caveat box.
Better to close the upstream once than document the workaround
N times.

## See also

- [`proofs/REPRODUCERS/immune_siege.md`](https://github.com/IdirBenSlama/Ophamin/blob/main/proofs/REPRODUCERS/immune_siege.md) §4 — workaround in place for the immune_siege family.
- [`src/ophamin/measuring/scenarios/base.py:464`](https://github.com/IdirBenSlama/Ophamin/blob/main/src/ophamin/measuring/scenarios/base.py) — the single line of code that emits the stale string.
- [`src/ophamin/cli.py`](https://github.com/IdirBenSlama/Ophamin/blob/main/src/ophamin/cli.py) — `cmd_run_all`, `cmd_scenario` (list/show/info).
- [`docs/STABILITY.md`](../STABILITY.md) — note: `Reproduction.command` is a metadata string, not a `@Stable` contract on the exact wire content. Changing the format does not violate stability policy.
