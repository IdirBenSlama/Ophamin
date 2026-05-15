<!--
Thanks for opening a pull request. Please fill in this template so reviewers
can land your change quickly.
-->

## What

<!-- 1–3 sentences. What does this PR do? -->

## Why

<!-- 1–3 sentences. The motivation, not the mechanism. -->

## Test plan

<!--
Be explicit. The framework's load-bearing discipline is reproducibility.
- [ ] Specific tests added / updated:
- [ ] Live verification (if applicable): `PYTHONPATH=src .venv/bin/python -m ophamin.cli <command>`
- [ ] Manual checks performed:
-->

## Checklist

- [ ] `pytest -q` runs green locally (all 386+ tests pass)
- [ ] No new lint findings I haven't acknowledged (`ruff check src tests`)
- [ ] If I added a public API, I also added tests for it
- [ ] If I added an external dependency, it's reflected in `pyproject.toml` AND `requirements.txt` / `requirements-dev.txt`
- [ ] If I added a scenario, I also added an example runner + tests
- [ ] If I changed a signed-record schema, I bumped the schema version
- [ ] Commit messages explain the *why* in the body, not just the *what* in the title
- [ ] No silent fallbacks introduced — every error path is loud
- [ ] No fabricated values — empty distributions are reported as empty, not zero-filled

## Linked issues

<!--
"Closes #N" for issues this PR resolves. "Refs #N" for related context.
-->
