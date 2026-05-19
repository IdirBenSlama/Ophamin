# Proposal — slim `ophamin` install path for verify-only consumers

> **Status:** **Tier-2 proposal** (substrate-touching, reversible, owner pick).
> **Tier:** Tier-2 — pyproject restructure + possible new package layout.
> **Date:** 2026-05-19
> **Blast radius:** Backward-incompatible install command depending on chosen option.

## TL;DR

A consumer who only wants to **verify a signed proof** OR **wrap a
proof in an interop format** (in-toto / RO-Crate / OpenLineage /
CycloneDX / SARIF / JUnit / MLflow / CloudEvents) needs essentially
**zero runtime dependencies beyond Python stdlib**. The current
`pip install ophamin` pulls ~400–600 MB of statsmodels + pandas +
scipy + mlflow + dvc + scikit-learn + lxml + rdflib that the
verify-only path never touches.

The empirical evidence from this investigation (2026-05-19):

| Module | Heavy deps imported |
|---|---|
| `ophamin/__init__.py` | **none** (stdlib only) |
| `measuring/metrics/tiers.py` | **none** |
| `seeing/substrate/base.py` | **none** |
| `measuring/proof/record.py` | **none** |
| `measuring/proof/codec.py` | **none** |
| `interop/in_toto.py` | **none** |
| `interop/ro_crate.py` | **none** |
| `interop/openlineage.py` | **none** |

Every slim-client-facing module imports only Python stdlib +
`from ophamin.…` siblings. The heavy deps come from importing
specific scenarios / pillars / wheels that the slim consumer
doesn't need.

This proposal surveys the four options for shipping a slim install
path and recommends Option C as the cleanest, with concrete
mitigation for the backward-compat break.

## Why this matters

Three downstream use cases that today require a 400–600 MB install:

1. **CI verification jobs** — pipelines that verify signed Ophamin
   proofs (e.g. promotion gates: "this proof's verdict is VALIDATED
   under our deployment key, allow merge"). Pulling statsmodels +
   mlflow + dvc on every job adds minutes of install latency for
   zero functional value.
2. **Edge / embedded consumers** — operators wrapping proofs in
   in-toto / RO-Crate / OpenLineage for transport to Sigstore /
   Zenodo / Marquez. The wrapping itself is a `dict → dict`
   transformation; everything else is dead weight.
3. **Kubernetes admission controllers / sidecars** — consumers
   that want to verify proofs at request time. A 600 MB image is
   excessive overhead for a thin verify-only sidecar.

## The four options

### Option A — separate `ophamin-client` package (sibling distribution)

Ship a second pip-installable package, e.g. `ophamin-client`, that
bundles ONLY:

- `ophamin/__init__.py`
- `ophamin/measuring/proof/` (record + codec + schema)
- `ophamin/interop/` (all 7 + helpers)
- `ophamin/seeing/substrate/base.py` (one stdlib-only file the
  proof record's substrate-classifier needs)
- `ophamin/measuring/metrics/tiers.py` (one stdlib-only file the
  proof record imports through `__init__`)

The full `ophamin` package depends on `ophamin-client` for the
shared code and adds the heavy deps + scenarios on top. This is
the **opentelemetry-api / opentelemetry-sdk** pattern.

**Pro:**
- Cleanest install paths: `pip install ophamin-client` for the
  slim case; `pip install ophamin` (which transitively installs
  `ophamin-client`) for the full framework.
- Full backward compat — existing `pip install ophamin` users
  see no change.
- Two distinct PyPI listings make the slim consumer audience
  explicit in the ecosystem.

**Con:**
- Two pyproject.toml files / two distributions to maintain.
- Slight risk of accidental cross-package import drift if a
  slim-target module ever grows a heavy import. (Hardening-test
  candidate.)
- Cross-language port bindings (`crates/ophamin-proof`,
  `packages/ophamin-proof-js`) already cover this niche for
  non-Python consumers; adding a Python sibling fragments the
  message a bit.

**Effort:** ~200–300 LOC of pyproject.toml + setup.cfg + new
package metadata + a CI job that publishes both distributions.

### Option B — separate `ophamin-client` repo

Ship `ophamin-client` from a different GitHub repo, with its own
release cycle.

**Pro:**
- Complete separation of concerns.

**Con:**
- Code duplication OR git submodule pain.
- Releases drift (chart appVersion / docker tag have to be
  cross-pinned across two repos).
- Out-of-scope for an autonomous-loop session — this is a
  longer-term restructuring call.

**Recommendation:** rule out.

### Option C — move heavy deps to optional `[scenarios]` / `[pillars]` extras

Restructure `[project.dependencies]` to be the slim set, and move
the heavy libraries to a new `[project.optional-dependencies]
scenarios = [...]` group. Existing users adapt with one command:

```bash
# Before this proposal
pip install ophamin

# After this proposal (full framework — most existing users)
pip install ophamin[scenarios]

# After this proposal (slim, verify-only — new use case)
pip install ophamin
```

The slim baseline would carry only:
- `jsonschema>=4.0` (for proof schema validation — opt-in but recommended)
- (everything else moves to extras)

**Pro:**
- Single package, single distribution.
- Minimal code change — pyproject.toml restructuring only.
- Natural Python idiom (`pip install package[extras]`).
- The slim install is genuinely tiny (~5 MB instead of ~500 MB).

**Con:**
- **Backward-incompatible**: existing users running
  `pip install ophamin` lose scenarios + most pillars without
  warning. Migration is one command (`pip install ophamin[scenarios]`)
  but it's a real break.
- Existing tutorials / READMEs / CHANGELOG entries that say
  `pip install ophamin` would all need updating.
- CI workflows on consumer repos that install `ophamin` would
  break until they add the `[scenarios]` extra.

**Mitigation:**
- Major version bump (1.0.0) to signal the break per semver.
- Loud `ImportError` that mentions the migration when a scenario
  module is imported without the heavy deps installed. (Pattern:
  `try: import statsmodels except ImportError: raise ImportError(
  "scenario X requires the [scenarios] extra; install via
  'pip install ophamin[scenarios]'")`.)
- README + tutorials + Docker image build (in `Dockerfile`)
  updated atomically with the cut.
- 1-week deprecation announcement before the cut.

**Effort:** ~50 LOC of pyproject.toml restructuring + ~30 LOC of
honest-failure stubs in scenarios that depend on heavy libs +
~10 docstring / README updates + a CI job that runs the suite
under `pip install ophamin` (slim) and `pip install ophamin[scenarios]`
(full) to catch import drift.

### Option D — do nothing; document the workaround

Tell slim consumers to install via `pip install --no-deps ophamin
jsonschema` and accept that this is unofficial / unsupported. Add
the recipe to `docs/SUPPLY_CHAIN.md` or a new `docs/SLIM_INSTALL.md`.

**Pro:**
- Zero engineering work.

**Con:**
- The recipe is fragile — `--no-deps` ships a broken `ophamin`
  install for anyone who imports a non-stdlib-only module.
- Doesn't surface the slim option to anyone who didn't already
  know to ask.
- Misses the marketing / discoverability value of having a
  first-class slim path.

## Recommendation

**Option C with mitigation.** The empirical evidence (zero heavy
deps in the slim-target modules) makes the engineering simple,
and the backward-compat-break is real but cleanly handled by a
major version bump + honest-failure ImportError.

The natural ship shape:

1. **0.99.0** (preparation release) — add the honest-failure
   ImportError stubs to every scenario module that imports a
   heavy lib. The stubs are no-ops while the heavy deps are
   still core; they activate only after the dep move. This
   release stays installable as today; ships the migration
   infrastructure.
2. **0.99.x deprecation window** — README + tutorials announce
   the upcoming break. The Docker image build (currently
   `pip install ophamin`) gets the heads-up too.
3. **1.0.0** (the break) — move heavy deps to `[scenarios]`.
   Bump major version per semver. CHANGELOG explicitly calls
   out the migration command.
4. **1.0.x docs** — `docs/SLIM_INSTALL.md` covers the new
   verify-only use case + recipes for CI verification jobs,
   sidecars, embedded consumers.

This sequence is roughly **3 releases of work** spread over **2–3
sessions of autonomous-loop time**. It's bigger than any single
0.42.x-style release; the discipline is to scope it carefully.

## What does NOT need to change

These remain valid regardless of which option ships:

- The wire-format Rust + JS ports (`crates/ophamin-proof`,
  `packages/ophamin-proof-js`) are already the slim path for
  non-Python consumers.
- The Helm chart's image continues to use the full framework
  (it's a server, not a slim verifier).
- The signed `EmpiricalProofRecord` format itself doesn't
  change — the slim path produces / verifies the same byte
  format.

## Decision required (from the owner)

1. Pick A / B / C / D (or "none of the above; here's a fifth
   option").
2. If A or C: confirm the migration shape (major bump, deprecation
   window, etc.).
3. If C: confirm 1.0.0 is the right cut moment — the framework's
   `0.42.0` versioning suggests deferring the 1.0.0 cut until
   the broader public-footprint activation (ORCID + Zenodo + JOSS)
   lands.

## Cross-references

- [Ophamin installation guide](https://github.com/IdirBenSlama/Ophamin/blob/main/docs/getting-started/install.md) — current install path
- [Wire-format Rust port README](https://github.com/IdirBenSlama/Ophamin/blob/main/crates/ophamin-proof/README.md) — the existing slim path for non-Python
- [Wire-format JS port README](https://github.com/IdirBenSlama/Ophamin/blob/main/packages/ophamin-proof-js/README.md) — same for JS/TS
- [INTEROP_OVERVIEW.md](../INTEROP_OVERVIEW.md) — the 8 interop layers a slim consumer would use
- [STATUS_2026_05_19.md](../STATUS_2026_05_19.md) — autonomous-doable list (mentions this proposal as next-step)
