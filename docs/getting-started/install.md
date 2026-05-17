# Installation

Ophamin requires **Python 3.12 or 3.13** (the canonical CI matrix).
The package is on the canonical GitHub repo; PyPI publishing is open
work for a future release.

## From GitHub (recommended for early adopters)

```bash
git clone https://github.com/IdirBenSlama/Ophamin.git
cd Ophamin
python3.12 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -e ".[dev]"
```

## Verify the install

```bash
ophamin --help
ophamin verify        # checks every required dep is importable
```

## Optional extras

Ophamin's pyproject ships a layered extras model:

| Extra | Adds | Use when |
|---|---|---|
| `dev` | pytest | always |
| `all` | matplotlib, pingouin, POT, tigramite, dowhy, ripser, scikit-tda, darts, pymc, numpyro, hypothesis, polars, duckdb, igraph, pycrdt, … | you want every scenario runnable |
| `audit` | ruff, bandit, mypy, vulture, radon, pip-audit, cyclonedx-python-lib | running the audit pillar |
| `property_test` | hypothesis, schemathesis, coverage, pytest-cov, pytest-benchmark | running property-tests + measuring coverage |
| `docs` | mkdocs-material, mkdocstrings | building this docs site |
| `causal` | dowhy, econml, causalml, tigramite | causal-discovery scenarios |
| `bayesian` | pymc, numpyro, arviz | Bayesian scenarios |
| `tda` | ripser, scikit-tda | topological-data-analysis pillars |
| `crdt` | pycrdt, y-py | CRDT-laws scenario |
| `viz` | matplotlib | reporting + meta-analysis charts |

Install several at once:

```bash
pip install -e ".[all,dev,property_test,docs]"
```

## Notes on the macOS lockfile

The repository ships `requirements-lock.darwin-py314.txt` — a
**local-environment snapshot** of the author's macOS Python 3.14 venv,
useful for forensic reference. It is **not portable** across platforms
or Python versions (e.g. `gudhi==3.12.0` has no linux/arm64 Python 3.12
wheel, so this lockfile breaks fresh installs on Linux ARM).

The Dockerfile + CI therefore install from `pyproject.toml` directly —
fresh resolution against Python 3.12 inside Linux containers.

## Docker

```bash
docker build -t ophamin:0.8.0 .
docker run --rm ophamin:0.8.0 --help
```

The image is **core-only** (`pip install -e .` with no extras). Many
optional extras need C/C++ build tools that `python:3.12-slim` doesn't
ship. For full-surface development use the local venv on a
build-tool-equipped host.

## Pre-push hook (developers)

```bash
git config core.hooksPath .githooks
```

The pre-push gate runs (1) pytest, (2) coverage ≥ 77 %, (3)
`mypy --strict` on the full package, (4) ruff. Any single failure
aborts the push. CI on GitHub runs the same gates plus a pip-audit
job.
