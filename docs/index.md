# Ophamin

**An empirical observatory wrapped around a substrate under test.**

Ophamin is the apparatus through which a complex substrate (Kimera-SWM
today, anything implementing the [`SubstrateUnderTest`](reference/api.md)
protocol tomorrow) becomes legible.

The name is the angelic order **Ophanim** — *wheels within wheels,
covered with eyes* (Ezekiel 1:18). Architecturally, Ophamin is a
*dyson sphere* around the substrate: the substrate sits at the centre
emitting; Ophamin envelops, senses, measures, audits, instruments,
reports — and returns signed, content-addressed, falsifiable
artefacts.

[Get started in 5 minutes :material-arrow-right:](getting-started/install.md){ .md-button .md-button--primary }
[Browse the architecture :material-arrow-right:](architecture/overview.md){ .md-button }

---

## Six wheels, two concentric triads

| Triad | Wheel | What it does | Backed by |
|---|---|---|---|
| **Outer (empirical)** | `seeing` | discover the substrate's surface + ingest corpora | sklearn, h5py |
| | `measuring` | run scenarios; emit signed Empirical Proof Records | statsmodels, mapie, river |
| | `comparing` | cross-commit drift + regression alerts | prov, mlflow, dvc |
| **Inner (engineering)** | `instrumenting` | per-cycle CPU / RSS / page-fault sampling | psutil, opentelemetry |
| | `auditing` | orchestrated static-analysis tools | ruff, bandit, mypy, pip-audit |
| | `reporting` | render results to Markdown / HTML / LaTeX | matplotlib |

Plus cross-cutting layers for per-primitive [`inspecting`](reference/api.md),
standard-format [`interop`](reference/api.md) (SARIF / JUnit XML /
MLflow / CycloneDX SBOM), and an `application` layer for the CLI.

## Five experimentation tiers

Every scenario binds a corpus + a substrate-target + a pre-registered
falsifiable claim, runs the corpus through the substrate, and emits a
signed [Empirical Proof Record](reference/schemas.md):

- **Scientific** — claims about substrate *behaviour*
- **Engineering** — claims about substrate *cost*
- **Philosophical** — claims about substrate *self-model*
- **Measurement-machinery** — claims about the *measurement apparatus*
- **Structural** — claims about *what the substrate is*, not what it does

19 scenarios ship today. See [`SCENARIO_AUTHORING.md`](SCENARIO_AUTHORING.md)
for the authoring path.

## The load-bearing promise

Every signed artefact carries an explicit `schema_version` and is HMAC
over a canonical JSON form. Minor versions never break existing
records; major versions ship migration scripts. See
[`SCHEMAS.md`](reference/schemas.md) for the full policy.

## Where to next

- New to Ophamin? Start with [Installation](getting-started/install.md)
  → [Your first scenario](getting-started/first-scenario.md)
- Want to contribute? Read [Contributing](contributing.md) +
  [Design changes go through RFC](rfc/README.md)
- Want to know what changed? [Changelog](changelog.md)
- Want to cite Ophamin? See the [CITATION.cff](https://github.com/IdirBenSlama/Ophamin/blob/main/CITATION.cff)
  or the Zenodo DOI on the latest release
