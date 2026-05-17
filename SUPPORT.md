# Getting help with Ophamin

> **TL;DR:** [open an issue](https://github.com/IdirBenSlama/Ophamin/issues/new/choose)
> for bugs + feature requests; consult [the docs site](https://idirbenslama.github.io/Ophamin/)
> for usage; use GitHub Discussions for open-ended questions.

## Where to look first

| Need | Channel |
|---|---|
| **How do I install / get started?** | [Documentation site](https://idirbenslama.github.io/Ophamin/getting-started/install/) |
| **How do I write a new scenario?** | [Scenario authoring guide](https://idirbenslama.github.io/Ophamin/SCENARIO_AUTHORING/) |
| **How do I plug in my own substrate?** | [`SubstrateUnderTest` protocol](https://idirbenslama.github.io/Ophamin/reference/api/) + [tutorials](https://idirbenslama.github.io/Ophamin/tutorials/wrap-a-pillar/) |
| **What does verdict X mean?** | [Reading a proof](https://idirbenslama.github.io/Ophamin/getting-started/reading-a-proof/) |
| **What's the wire format / schema?** | [`SCHEMAS.md`](https://github.com/IdirBenSlama/Ophamin/blob/main/SCHEMAS.md) |
| **What's the API stability contract?** | [`docs/STABILITY.md`](docs/STABILITY.md) |
| **Where is the project headed?** | [`ROADMAP.md`](https://github.com/IdirBenSlama/Ophamin/blob/main/ROADMAP.md) |
| **Who decides what?** | [`GOVERNANCE.md`](https://github.com/IdirBenSlama/Ophamin/blob/main/GOVERNANCE.md) |
| **I think I found a bug.** | [File a bug report](https://github.com/IdirBenSlama/Ophamin/issues/new?template=bug_report.yml) |
| **I want a new feature.** | [File a feature request](https://github.com/IdirBenSlama/Ophamin/issues/new?template=feature_request.yml) |
| **I want to discuss design before filing an RFC.** | [GitHub Discussions](https://github.com/IdirBenSlama/Ophamin/discussions) (when active) |
| **I found a security vulnerability.** | Email the owner per [`SECURITY.md`](https://github.com/IdirBenSlama/Ophamin/blob/main/SECURITY.md) — do NOT file a public issue. |

## Before you file an issue

A few minutes here saves the maintainer the same time many times over:

1. **Search [existing issues](https://github.com/IdirBenSlama/Ophamin/issues?q=is%3Aissue)** — your question may already be tracked.
2. **Reproduce on the latest release.** `pip install --upgrade ophamin`
   (once PyPI publication is wired) or check out `main` and reinstall.
3. **Capture the minimal reproducer.** A 10-line script that fails the same way is faster to fix than a stack trace.
4. **Include environment info.** `python --version`, `pip freeze | grep ophamin`, OS + arch.

## What kind of response to expect

Per [`GOVERNANCE.md`](https://github.com/IdirBenSlama/Ophamin/blob/main/GOVERNANCE.md), Ophamin is a **single-author**
project in `0.10.x`. Response cadence is best-effort and
capacity-limited; "reasonable window" is on the order of days for
substantive PRs and hours for security reports.

If you need a faster turnaround for a commercial deployment, that
conversation happens via the owner's email in
[`CITATION.cff`](https://github.com/IdirBenSlama/Ophamin/blob/main/CITATION.cff) (or your existing direct channel).

## Contributing

If you'd like to contribute code, docs, scenarios, or
infrastructure: [`CONTRIBUTING.md`](https://github.com/IdirBenSlama/Ophamin/blob/main/CONTRIBUTING.md). Every PR
must:

- Pass the local pre-push gates (`pytest -q --cov=src/ophamin
  --cov-fail-under=75` + `mypy --strict src/ophamin` + `ruff
  check src tests`);
- Carry a CHANGELOG entry under the appropriate section;
- Carry stability-tier annotations for any new public symbol per
  [`docs/STABILITY.md`](docs/STABILITY.md).

PRs that don't pass these gates won't be merged; the gates exist to
keep every release green on the public CI matrix.
