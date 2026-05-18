---
title: 'Ophamin: A falsifiability-first experimentation framework with signed, cross-language-verifiable empirical proof records'
tags:
  - Python
  - experimentation framework
  - reproducibility
  - statistical methodology
  - cross-framework validation
  - signed records
authors:
  - name: Idir Ben Slama
    orcid: 0000-0000-0000-0000
    corresponding: true
    affiliation: 1
affiliations:
  - name: Independent
    index: 1
date: 18 May 2026
bibliography: paper.bib
---

# Summary

Ophamin is a Python framework that turns experiments into
**signed empirical proof records**. Every measurement an Ophamin
scenario produces is bound to its pre-registered falsifiable claim,
to the exact byte-equal data corpus it ran against, to a versioned
substrate-under-test, and to a tamper-evident HMAC-SHA256
signature. A record's verdict (`VALIDATED`, `REFUTED`, or
`INCONCLUSIVE`) is computed from the claim's threshold, not from
the experimenter's discretion; the wire format is canonical and
specified normatively so that signatures verify byte-for-byte
across Python versions, operating systems, and language ports.

Ophamin ships with five experimentation tiers (scientific,
engineering, philosophical, empirical-deep, and
measurement-machinery) and a registry of ready-to-run scenarios
that emit such records. The measurement-machinery tier in
particular contains cross-framework validation scenarios that
verify the upstream statistical primitives Ophamin itself depends
on. Since `0.15.0`, seven such scenarios ship as signed `VALIDATED`
proofs spanning six statistical-primitive families: proportion
confidence intervals (scipy ↔ statsmodels Wilson), rank correlation
(scipy ↔ pingouin Spearman), product-moment correlation
(scipy ↔ numpy ↔ pingouin Pearson), two-sample parametric
hypothesis testing (scipy ↔ statsmodels ↔ pingouin Welch's
*t*-test), multi-group parametric hypothesis testing (scipy
↔ statsmodels ↔ pingouin one-way ANOVA), non-parametric two-
sample hypothesis testing (scipy ↔ pingouin Mann-Whitney U), and
Bayesian posterior inference (PyMC ↔ NumPyro). All seven agree at
$\le 7 \times 10^{-14}$ — a few units of double-precision machine
epsilon for the parametric checks, exact agreement for the
non-parametric rank-based check.

As of `0.21.x`, the framework is reachable from non-Python
consumers across five distinct interop layers:

1. **Cross-language wire-format ports**: read + write canonical
   bytes from Rust (`crates/ophamin-proof`) and JS/TS
   (`packages/ophamin-proof-js`). The round-trip is symmetric —
   a Rust-built record verifies under Python and JS, a JS-built
   record verifies under Python and Rust, all on the same
   committed cross-language fixtures.
2. **Model Context Protocol (MCP) server** (`ophamin mcp serve`):
   exposes scenario listing, claim inspection, signature
   verification, canonicalization, proof-index reading, and
   scenario execution as MCP tools. Any MCP client (Claude Code,
   Claude Desktop, Cursor, Cline) can drive Ophamin without a
   Python integration.
3. **HTTP REST API** (`ophamin http serve`): same logical surface
   as the MCP server, exposed over HTTP for service-style
   consumers (Kubernetes microservices, browser apps, curl
   scripts). FastAPI-backed; auto-generates OpenAPI 3 spec at
   `/openapi.json`.
4. **CloudEvents 1.0 wrapper**: wraps signed proofs in
   structured-mode envelopes so event-stream consumers (Kafka,
   EventBridge, Knative, NATS) can route Ophamin records
   natively without knowing the framework's wire format.
5. **OpenTelemetry instrumentation**: scenario execution, proof
   verification, and canonicalization emit spans + metrics with
   stable `ophamin.*` attribute names. Any OTel-compatible
   backend (Jaeger, Zipkin, Tempo, Datadog, New Relic,
   Honeycomb, GCP Cloud Trace, AWS X-Ray, Azure Monitor) can
   collect them.

All five layers wrap the **same shared implementations**
(`ophamin.interfaces._impls`), so behavioural drift between them
is structurally impossible.

The framework is intended for researchers and engineers who want
to make falsifiable claims about a software system's behaviour
under data, and who need those claims to survive review, replay,
cross-machine verification, and consumption by non-Python
infrastructure without manual intervention.

# Statement of need

A growing body of work on the research-software validity crisis
[@begley2015reproducibility; @baker2016] has documented that the
problem is not malice but **methodology drift**: experiments are
run, conclusions are written down, and the link between the
underlying data, the analysis pipeline, the chosen threshold, and
the published verdict decays the moment the run terminates.
Tools that nominally fix one piece of this chain — DVC for data,
MLflow for runs, Stan for inference, ReproZip for environments —
do not, by design, fix all of them together. The artefact a
reviewer encounters is still a paragraph of prose backed by a
tarball of logs.

Ophamin targets exactly the seam between *what was run* and *what
was claimed*. A scenario in Ophamin must declare its falsifiable
claim as a five-tuple — `metric`, `comparator`, `threshold value`,
`H0`, `H1` — before it can produce a record at all. The verdict
is computed mechanically from the comparator applied to the
observed statistic; the experimenter cannot vote on the outcome.
The record is then HMAC-signed under a deployment-specific key,
content-addressed, and serialised to a canonical byte form that
is normatively specified [@ophamin-schemas-md] so that any
conformant cross-language decoder reaches the same signature
verification result.

The framework also addresses the multiple-comparisons problem at
the campaign level. When `ophamin run-all` executes a set of
scenarios, the resulting `CampaignRecord` (schema version `2.0`)
records both the per-scenario raw verdicts and a vector of
family-wise-error-rate-corrected verdicts under
Holm–Bonferroni [@holm1979] or the false-discovery-rate-controlled
Benjamini–Hochberg procedure [@benjamini1995]. The choice is the
campaign author's; what cannot drift is the disclosure.

The cross-framework validation tier closes a complementary leak:
even when a single scenario's verdict is correct in its own terms,
that correctness depends on the upstream library it called.
A subtle change in `scipy.stats.spearmanr`'s tied-rank handling,
or in `pingouin.ttest`'s default Welch correction, would silently
invert downstream Ophamin verdicts without anything in the record
flagging it. The measurement-machinery scenarios assert
floating-point agreement between independent implementations of
each primitive on every CI run; an upstream regression surfaces
as a `REFUTED` proof, not as a quiet drift in the science.

To our knowledge, no other widely-distributed Python framework
combines: (a) a normatively specified signed wire format with
cross-language test fixtures, (b) compulsory pre-registration of
the falsifiable claim, (c) multiplicity correction surfaced
inside the same signed artefact, and (d) continuous
cross-framework validation of the statistical primitives the
framework depends on.

# Design

## The signed `EmpiricalProofRecord`

The framework's load-bearing artefact is the
`EmpiricalProofRecord` dataclass and its corresponding JSON
schema (`SCHEMA_VERSION = "1.0"`). A record has nine sections:
the claim five-tuple; the pre-registration block (config hash,
data hash, analysis plan); the data block (substrate identifier,
substrate Git commit, dataset references with content hashes); a
list of `PillarEvidence` entries (one per analysis pillar); the
mechanically-computed verdict; the reproduction command; the
provenance graph in W3C PROV-O JSON form; the identity block
(framework version, framework Git commit, timestamp); and the
HMAC-SHA256 signature over sections 1–8 in canonical form.

The signature is bit-stable across Python 3.10–3.14, the three
major operating systems, and the two JSON serialisers we test
against (stdlib `json` and `orjson`). It is **not** stable
across changes to the canonical-form rules; any such change is a
major-version bump with a published migration script.

## Cross-language canonical form

The canonical byte form is specified by eleven normative rules
R1–R11 in `SCHEMAS.md` covering encoding (UTF-8), separators
(`,` and `:` with no whitespace), object key ordering
(recursive Unicode code-point sort), integer and float
representation (Python `repr` semantics including `1e+20` /
`1e-07` exponent formats and `-0.0` preservation), string
escaping (`ensure_ascii=True` with UTF-16 surrogate pairs for
supplementary-plane code points), and explicit handling of
`null`, booleans, arrays, and the `NaN` / `Infinity` non-standard
forms. Three cross-language test fixtures (`simple`,
`unicode`, `numerical_edge`) ship under
`tests/canonical_form/`, each consisting of a language-neutral
input, the expected canonical byte stream, and the expected
HMAC-SHA256 digest under a fixed test key. A conformant
implementation in any language is one that reproduces all three
fixtures byte-for-byte.

## Five experimentation tiers

Scenarios are organised by *what kind of claim they make*, not by
*what subject they test*. The five tiers are:

1. **Scientific** — claims about a substrate's behaviour
   (false-positive ceilings, cross-language agreement,
   active-rate bounds, sustained traversal rates, contract
   stability, completeness, memory-as-deformation).
2. **Engineering** — claims about a substrate's cost
   (throughput, latency, resource use).
3. **Philosophical** — claims about self-model coherence
   (e.g., Cohen's *d* on a dissonance metric over
   self-referential vs neutral inputs).
4. **Empirical-deep** — claims about substrate physics
   (Bayesian posterior contraction, PCMCI causal-link recovery,
   cross-channel mutual information, prime-emission structure,
   factorisation invariance, basis correlations).
5. **Measurement-machinery** — claims about the upstream
   libraries the framework itself depends on (the
   cross-framework validation scenarios described above).

Every tier shares the same record discipline; they differ only in
what fields they read from a cycle result and what claim their
constructor pre-registers.

## Multiplicity correction

When multiple scenarios run as a single campaign, the resulting
`CampaignRecord` carries both the per-scenario raw verdicts and
the family-wise-error-rate-corrected vector. The default
procedure is Holm–Bonferroni; the campaign author can elect
Benjamini–Hochberg via the CLI. Either choice is itself part of
the signed record. Schema version `2.0` adds these fields
additively to the v1.0 record body, with a body-construction
function that omits them when `schema_version == "1.0"` so that
historical v1.0 signatures continue to verify.

## Reproducibility audit

A dedicated meta-scenario, `DeterministicSeedAuditScenario`, runs
any other scenario twice with identical seed kwargs and asserts
that the two resulting records produce identical
`reproducibility_hash()` outputs. The hash excludes wall-clock
fields (timestamps, provenance node identifiers, per-cycle
timing breakdowns) so that the audit measures determinism of
the substrate, not determinism of the surrounding I/O. A
framework-wide parametrised test
(`test_framework_wide_reproducibility.py`) discovers every
scenario whose constructor accepts a `seed` parameter and runs
the audit against each one as a single PR-time gate.

# Cross-host interoperability

Ophamin's interop story is structured so that **the same logical
surface is exposed across five transports without code
duplication**. A single Python module
(`ophamin.interfaces._impls`) implements six tools — list
scenarios, get scenario claim, verify proof, canonicalize value,
read proof index, run scenario — as transport-agnostic
functions. Each transport is a thin wrapper around these
functions, so a behavioural change in one transport is
structurally impossible without breaking all.

## Cross-language wire-format ports

The Rust crate `ophamin-proof` and the JS/TS package
`@ophamin/proof` implement read-only verifiers AND write-side
canonical-form encoders byte-for-byte equivalent to the Python
reference. The cross-language fixtures at
`tests/canonical_form/` consist of three reference values
(`simple`, `unicode`, `numerical_edge`) each with its expected
canonical byte stream and HMAC-SHA256 digest under a fixed test
key. A `.github/workflows/cross-language.yml` CI workflow runs
both ports against the fixtures on every PR; drift fails CI
loud. The Rust `CanonicalValue` enum (with distinct
`Int(i64)` / `Float(f64)` variants) preserves Python's int/float
distinction at the type system level; the JS port uses a `PyInt`
class for the same purpose.

## MCP server

`ophamin mcp serve` starts a Model Context Protocol [@mcp-spec]
server speaking JSON-RPC over stdio (default), SSE, or
streamable-HTTP. Any MCP client can invoke six tools mirroring
the shared implementations. The package's `[mcp]` extra installs
the underlying `mcp` Python SDK.

## HTTP REST API

`ophamin http serve` starts a FastAPI [@fastapi] app on a
configurable host/port with eight endpoints (the six tools plus
`/health` and `/version`). FastAPI auto-generates OpenAPI 3.x
spec at `/openapi.json` and renders Swagger UI at `/docs`. The
server is auth-agnostic by design; production deployments wrap
it in middleware or sit behind an authenticating reverse proxy.

## CloudEvents wrapper

`ophamin.cloudevents.wrap(proof, source=...)` produces a
CloudEvents 1.0 [@cloudevents-spec] structured-mode envelope
with required attributes (`specversion`, `id` from the
content-addressed `proof_id`, `source`, `type`, `time`,
`datacontenttype`, `dataschema`) plus Ophamin-specific
extensions (`ophaminversion`, `ophaminschema`, `ophaminverdict`)
that consumers can route on. `ophamin.cloudevents.unwrap`
recovers the embedded proof for downstream verification.

## OpenTelemetry instrumentation

The shared implementations emit OpenTelemetry [@otel-spec] spans
with stable `ophamin.*` attribute names and metrics with stable
labels. When no SDK provider is configured (the
production default after `pip install ophamin`), the OTel API
returns no-op tracers and meters; the overhead is roughly 100
nanoseconds per span. Calling `ophamin.observability.setup_otel()`
wires the OTLP HTTP exporter for trace + metric export to any
OTel-compatible backend.

# Concrete falsifications and agreements produced

The framework has produced both verdicts. Selected examples
across the seven cross-framework agreement checks:

- **PyMC ↔ NumPyro Bayesian agreement** (proof ID
  `aae6cf83833b7c05`): posterior mean difference $1.7 \times
  10^{-3}$ and 94 % HDI width ratio $1.02$ on a synthetic
  $\Phi$-posterior corpus; `VALIDATED`.
- **scipy ↔ statsmodels Wilson CI** (proof ID
  `80d5b9f33fbaf6d7`): pairwise CI-bound agreement
  $1.1 \times 10^{-16}$ across 30 proportions sweeping
  $p \in [0.05, 0.95]$; `VALIDATED`.
- **scipy ↔ pingouin Spearman $\rho$** (proof ID
  `f65319cb2ab7eb3d`): exact (zero-bit) agreement across 30
  pairs sweeping $\rho \in [-0.9, 0.9]$ at $N = 100$;
  `VALIDATED`.
- **scipy ↔ numpy ↔ pingouin Pearson $r$** (proof ID
  `7b2498c1937091d1`): three-way pairwise agreement
  $3.3 \times 10^{-16}$ across 30 pairs at $N = 100$;
  `VALIDATED`. Worst pair is scipy↔numpy (different numerical
  paths via centered-product vs covariance matrix), still at
  machine epsilon.
- **scipy ↔ statsmodels ↔ pingouin Welch's *t*-test** (proof
  ID `5c6f481298cbfa3f`): three-way pairwise agreement
  $1.8 \times 10^{-15}$ on both the *t* statistic AND the
  two-sided *p* value across 30 pairs sweeping effect size
  $\delta \in [-1, 1]$ and variance ratio $\sigma_y / \sigma_x
  \in [0.5, 2.0]$; `VALIDATED`. statsmodels is a genuinely
  independent implementation that does not delegate to scipy.
- **scipy ↔ statsmodels ↔ pingouin one-way ANOVA** (proof ID
  `b0fcc417fb505410`): three-way pairwise agreement $7.1 \times
  10^{-14}$ on both the F statistic AND the two-sided *p* value
  across 30 three-group datasets sweeping effect magnitude
  $\in [0, 1.5]$; `VALIDATED`. Generalises the two-sample
  Welch check to $k \ge 3$ groups; statsmodels here drives ANOVA
  through OLS + `anova_lm` (Type II SS), again an independent
  path.
- **scipy ↔ pingouin Mann-Whitney U** (proof ID
  `e71be64487df9f56`): pairwise agreement of exactly $0$ on both
  the *U* statistic and the two-sided *p* value across 30
  independent-sample pairs drawn from a rotation of normal,
  log-normal, and Cauchy distributions; `VALIDATED`. First
  non-parametric check; both backends pinned at
  `use_continuity=True`. Exact agreement under matched
  continuity settings is a stronger pin than the parametric
  cross-checks above can give.

Per-scenario refutations (also in the repository's
`EMPIRICAL_VALIDATION.md` record) include falsifications of
prior load-bearing claims about the host substrate's behaviour
that the framework's discipline was designed to surface, not
hide.

# Limitations

Three limitations bound the framework's current claim:

1. **The signed-record schema is at `1.0`**: any future change
   to the canonical-form rules is a major-version bump with
   migration. The wire format is therefore stable today but
   evolves coarsely.
2. **`NaN`, `Infinity`, and Python's `default=str` fallback are
   non-portable**: bare `NaN` / `Infinity` literals appear in
   Python's `json.dumps` output (non-standard JSON, rejected by
   strict parsers), and `default=str(obj)` produces
   Python-specific string representations of non-JSON-native
   values. Records using them remain verifiable under the
   Python reference but cross-language ports are not required
   to reproduce them. Scenario authors avoiding these values
   keep records inside the portable subset; the framework's
   own scenarios do.
3. **The included scenarios cover a single substrate
   (`kimera-swm`) in detail.** The framework is substrate-agnostic
   by design — any system that emits per-cycle telemetry can be
   the target — but the empirical record is broadest for that one
   case study. The seven measurement-machinery scenarios are
   substrate-free and apply universally.

# Acknowledgements

The framework's development was carried out by the author across
2026 under a series of autonomous-execution sessions. The
RFC 0002 elevation plan and per-phase acceptance criteria were
authored explicitly to make this paper falsifiable in the same
sense the framework requires of its own scenarios.

# References
