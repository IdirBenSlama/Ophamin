# Contributing to Ophamin

Thanks for taking an interest. This document covers the *what* and *how* of
contribution. The framework is open-source under the **Apache License
2.0** (see [`LICENSE`](LICENSE) + [`NOTICE`](NOTICE)). External
contributions are welcome through the standard GitHub PR flow; the
project follows an RFC process for non-trivial design changes (see
`docs/rfc/` once the process lands; currently architectural
decisions are captured in the audit + extended-audit documents under
`docs/`).

## Ground rules

- **No silent fallbacks.** A misconfigured adapter raises; a missing tool
  reports `status="unavailable"`; a pillar that does not apply to a
  configuration is `skipped` with an explicit reason. We never fabricate a
  plausible-looking result.
- **Wrap, don't rewrite.** New audit pillars should orchestrate existing
  mature tools, not reimplement them. New analytic pillars should delegate
  to a battle-tested library and cross-check against it.
- **Pre-registration discipline.** A new scenario MUST capture its claim,
  threshold, and analysis plan BEFORE the substrate runs. A REFUTED verdict
  is the framework working — it surfaces a real architectural debt.
- **Loud failure, no fabrication.** Every error path explains itself; no
  empty-dict returns hiding a real bug.

## Dev setup

```bash
git clone https://github.com/IdirBenSlama/Ophamin.git
cd Ophamin
python3.12 -m venv .venv
.venv/bin/python -m pip install -e ".[all,dev]"   # full optional surface
.venv/bin/python -m pytest -q          # 842+ tests must pass
```

### Optional: enable the pre-push test gate

GitHub Pro is required for server-side branch protection on private repos,
so until the repo goes public (or upgrades), we ship an opt-in pre-push
git hook that runs the full test suite before allowing a push:

```bash
git config core.hooksPath .githooks
```

The hook lives at [.githooks/pre-push](.githooks/pre-push) and adds ~8 s
to every push. Skip a one-off push with `git push --no-verify`.

## Authoring a new scenario

See [`docs/SCENARIO_AUTHORING.md`](docs/SCENARIO_AUTHORING.md). The short
version:

1. Subclass `ophamin.measuring.scenarios.base.Scenario`.
2. Set `name`, `corpus_name`, `target`, `n_cycles`.
3. Implement `build_claim()` — return a `Claim` with a falsifiable
   `Threshold`.
4. Implement `score()` — read `cycle_results`, return a `ScenarioScore`.
   Use the helpers in `ophamin.measuring.scenarios.helpers` for shape-aware
   extraction (gwf_cleared, dissonance_count, …), Wilson 95% CI, inconclusive
   guards, and distribution stats.
5. Register the class in `ophamin.measuring.scenarios.__init__.py`.
   **This step is load-bearing for the `ophamin scenario <name>` CLI
   path.** Scenarios whose files exist but whose classes aren't added
   to the `SCENARIOS` dict are reachable from Python but not from the
   CLI — see `docs/ARCHITECTURE_INTENT_VS_REALITY_2026_05_16.md` for the
   current registry gap inventory.
6. Add unit tests in `tests/test_scenario_*.py` (use the `_FakeCyberCorpus` /
   `_FakeFloresCorpus` patterns).
7. Add an example runner in `examples/run_<scenario>.py`.

New scenarios should land in ~80 LOC (analytic-deep scenarios in
~300–500 LOC; see `prime_structure.py`, `causal_discovery.py`).

## Authoring a new audit pillar

1. Subclass `ophamin.auditing.base.AuditPillar`.
2. Set `name` (display) and `tool_binary` (the CLI to look up on PATH).
3. Implement `run(target_path) -> PillarResult` — invoke the tool via
   `subprocess.run`, parse its output, normalise into `Finding` dataclasses.
4. Map the tool's native severity scale onto `FindingSeverity` (CRITICAL /
   HIGH / MEDIUM / LOW / INFO).
5. Register the class in `ophamin.auditing.pillars.__init__.py` (add to
   `DEFAULT_PILLAR_CLASSES`).
6. Add an extra to `pyproject.toml` so users can `pip install
   'ophamin[audit]'` and get the tool.
7. Add tests in `tests/test_auditing.py` using `unittest.mock.patch` against
   `subprocess.run` (no live tool invocation in unit tests).

## RFC-first rule for design changes

Some changes need a written design document before code lands. The
**RFC process** ([`docs/rfc/README.md`](docs/rfc/README.md)) covers:

- new public APIs (CLI commands, codec functions, Protocol contracts)
- signed-record schema field changes (see [`SCHEMAS.md`](SCHEMAS.md))
- new dependencies in `[project.dependencies]` (vs. an extra)
- new experimentation tiers in the scenario taxonomy
- splits / merges of the six wheels

Open a PR adding `docs/rfc/NNNN-<slug>.md` based on
[`docs/rfc/0000-template.md`](docs/rfc/0000-template.md). The
maintainer either accepts the RFC (after which an implementation PR
references it by number) or asks for revisions.

**Bug fixes, refactors that don't change behavior, new tests, doc
improvements, and dependency-version bumps** go straight to a PR —
no RFC needed.

## Pull request checklist

Before opening a PR:

- [ ] `pytest -q --ignore=tests/bench` runs green locally (1208+ tests).
- [ ] `mypy --strict src/ophamin` clean (138/138 source files).
- [ ] `ruff check src tests` reports no new violations.
- [ ] If you added a public API, you also added tests for it.
- [ ] If you added a signed-record field, you also updated
      [`SCHEMAS.md`](SCHEMAS.md) and the corresponding codec round-trip
      property test.
- [ ] If you added an external dependency, it's reflected in
      `pyproject.toml` extras AND the relevant lockfile is refreshed.
- [ ] If you added a scenario, you also added an example runner.
- [ ] If the change is design-shaped (per the RFC-first rule above),
      the RFC PR landed first.
- [ ] Your commit message explains the *why* in the body, not just the
      *what* in the title.

## Reporting issues

See [`SECURITY.md`](SECURITY.md) for security issues; use the issue
templates for everything else.

## Code of conduct

See [`CODE_OF_CONDUCT.md`](CODE_OF_CONDUCT.md). Engage in good faith, be
respectful, and bring your honest thinking. Ophamin is a project that values
empirical refutation over comfortable validation — the same disposition
applies to discussion.
