# Release procedure (Phase L2 + L3)

> **Source of truth for tagging an Ophamin release.** Every minor and
> major release goes through this checklist; patch releases (`0.x.y`)
> may skip step 5 (Zenodo) if no notable scientific change.

## 0. Pre-flight

- [ ] `main` is the source of truth; all release commits land on `main`
- [ ] CI on `main` is green (CI + Audit + lint + typecheck workflows)
- [ ] `mypy --strict src/ophamin` clean locally
- [ ] `pytest -q --ignore=tests/bench` green locally
- [ ] pre-push hook installed (`git config core.hooksPath .githooks`)

## 1. Pick the version

Ophamin follows [Semantic Versioning](https://semver.org):

- **patch** (`0.7.2`): bug fixes only, no new public surface
- **minor** (`0.8.0`): new public surface (CLI command, scenario,
  schema field, Protocol contract), full backward compatibility
- **major** (`1.0.0`): breaking changes to wire format / Protocol /
  CLI semantics; requires a migration script

Schema version bumps are tracked separately in
[`SCHEMAS.md`](https://github.com/IdirBenSlama/Ophamin/blob/main/SCHEMAS.md); ophamin-version and schema-version are
NOT coupled (a patch ophamin bump may still ship a v2 of one schema
when the older v1 stays readable).

## 2. Update version metadata

Three files must agree:

```bash
# pyproject.toml
sed -i '' 's/version = "0.7.2"/version = "0.8.0"/' pyproject.toml

# src/ophamin/__init__.py
sed -i '' 's/__version__ = "0.7.2"/__version__ = "0.8.0"/' src/ophamin/__init__.py

# CITATION.cff (two places: top-level + preferred-citation)
sed -i '' 's/version: 0.7.2/version: 0.8.0/g' CITATION.cff
```

Verify they match:

```bash
grep -E '^version|^__version__' pyproject.toml src/ophamin/__init__.py CITATION.cff
```

## 3. Update CHANGELOG.md

Add a new section `## [<version>] — YYYY-MM-DD` above the previous
release section. Follow the established structure:
**Added / Changed / Fixed / Validated**. Every section starts with
concrete bullets; no marketing language.

If a schema bumped, add a `### Schema migrations` subsection summarising
the change and pointing at the migration script under `migrations/`.

## 4. Tag + push

```bash
# Sanity: should match the version you set
.venv/bin/python -c "import ophamin; print(ophamin.__version__)"

# Commit the version bump
git add pyproject.toml src/ophamin/__init__.py CITATION.cff CHANGELOG.md
git commit -m "$(cat <<'EOF'
Cut <version> — <one-line subject>

<body matching CHANGELOG entry>

Co-Authored-By: <if AI-assisted>
EOF
)"

# Tag with the same string as pyproject's version
git tag -a v<version> -m "Ophamin <version>"

# Push commit + tag together
git push origin main
git push origin v<version>
```

## 4.5 PyPI publication (auto via Trusted Publishing)

The `v<version>` tag push triggers
[`.github/workflows/release.yml`](https://github.com/IdirBenSlama/Ophamin/blob/main/.github/workflows/release.yml),
which builds an sdist + pure-Python wheel and publishes to PyPI via
**Trusted Publishing** (OIDC; no long-lived API tokens).

### One-time owner-side setup

Before the first publish, the owner must wire PyPI's "pending publisher"
for the project. Until this is done, the `publish` job in
`release.yml` will fail with `invalid_grant` (expected and gating).
The `build` job continues to succeed on every tag push so the wheel
remains downloadable as a workflow artefact.

1. Sign in at <https://pypi.org/manage/account/publishing/>.
2. Click "Add a new pending publisher".
3. Fill in:

   | Field | Value |
   |---|---|
   | PyPI Project Name | `ophamin` |
   | Owner | `IdirBenSlama` |
   | Repository name | `Ophamin` |
   | Workflow name | `release.yml` |
   | Environment name | `pypi` |

4. Save. The pending publisher will be active until the first
   successful publish, at which point PyPI promotes it to a standard
   trusted publisher.

5. (Optional but recommended) Add `Idir Ben Slama <ben.slama.idir@gmail.com>`
   as a project owner on PyPI under "Manage" once the project exists,
   so future publishers don't depend on whoever made the first push.

### Per-release behaviour

After the one-time setup, every `v*` tag push:

1. Builds sdist + wheel (`python -m build`).
2. Verifies the build with `twine check --strict` (PyPI metadata sanity,
   README rendering, long-description content type).
3. Uploads both artefacts to PyPI as `ophamin <version>`.

### Dry-run

To rebuild without publishing — e.g. verifying a candidate before
tagging — trigger the workflow manually with `dry_run=true`:

```bash
gh workflow run release.yml -f dry_run=true
```

The build job still runs + verifies; the publish job is skipped.

### Local pre-flight

To mirror the workflow's build + verify locally:

```bash
.venv/bin/python -m pip install -e ".[release]"
rm -rf dist/
.venv/bin/python -m build
.venv/bin/python -m twine check --strict dist/*
```

The `[release]` extra is intentionally lightweight (build + twine
only); no PyPI credentials are stored locally.

## 4.6 SLSA 3 provenance + sigstore + PEP 740 attestations

Every release artefact carries **three independent cryptographic
attestations**:

| Layer | Generated by | Verify with | Where it lives |
|---|---|---|---|
| **SLSA 3 build provenance** | `actions/attest-build-provenance@v2` (in `release.yml` `build` job) | `gh attestation verify` | GitHub attestation store + Rekor transparency log |
| **Sigstore cosign signature** | Embedded inside the SLSA attestation (sigstore is the signing backend) | `cosign verify-blob` | Rekor + Fulcio |
| **PEP 740 PyPI attestations** | `pypa/gh-action-pypi-publish` with `attestations: true` (in `release.yml` `publish` job) | `pip install --verify-attestations` | PyPI index, alongside the .whl/.tar.gz |

The three layers serve different verification surfaces:

- **GitHub clone** — `gh attestation verify` against a downloaded wheel
  proves the wheel was produced by Ophamin's `release.yml` at a
  specific commit.
- **Sigstore consumer** — `cosign verify-blob` proves the wheel was
  signed by the workflow's OIDC identity and the signature is in the
  Rekor transparency log.
- **PyPI install path** — `pip install ophamin --verify-attestations`
  proves provenance at the moment of install, with no separate
  download step.

All three are produced from **a single sigstore signing event** in the
workflow run — there is no parallel signing key; the OIDC identity
is the credential.

### Verify a downloaded wheel

```bash
# Download the wheel (or sdist) from PyPI or a workflow artifact.
wget https://files.pythonhosted.org/packages/.../ophamin-X.Y.Z-py3-none-any.whl

# Verify the SLSA 3 attestation via GitHub's CLI.
gh attestation verify \
    ophamin-X.Y.Z-py3-none-any.whl \
    --owner IdirBenSlama

# Or via sigstore cosign directly (independent of GitHub):
cosign verify-blob \
    --bundle ophamin-X.Y.Z-py3-none-any.whl.sigstore.json \
    --certificate-identity-regexp 'https://github.com/IdirBenSlama/Ophamin/.+' \
    --certificate-oidc-issuer https://token.actions.githubusercontent.com \
    ophamin-X.Y.Z-py3-none-any.whl
```

A successful verification prints the SLSA claim + the workflow run URL
that produced the artefact + the source commit hash.

### Verify at install time

```bash
# pip 25+ with --verify-attestations (PEP 740) — once the first
# trusted-publishing release lands on PyPI:
pip install ophamin --verify-attestations

# or via uv:
uv pip install ophamin --verify-attestations
```

### Owner-side prerequisites

**None.** SLSA + sigstore + PEP 740 attestations all use GitHub's OIDC
identity, no external secrets, no extra signing keys to manage. The
PyPI Trusted Publisher setup from §4.5 also activates PEP 740
attestation upload (the same OIDC claim authenticates both).

### Failure modes during transition

Before the PyPI pending publisher is registered (§4.5):

- ✅ SLSA 3 attestation generates fine (no PyPI dependency).
- ❌ PEP 740 attestation upload fails (PyPI rejects the publish; the
  attestation isn't uploaded because no package is uploaded either).

After PyPI pending publisher is registered:

- ✅ Both SLSA 3 and PEP 740 attestations generate + upload cleanly.

## 5. Zenodo DOI (minor + major only)

Pre-requisite: the Zenodo–GitHub integration is configured. If not,
**this is owner-territory** — the owner authenticates Zenodo on
zenodo.org and authorises the GitHub repo. After that, every tagged
release auto-mints a DOI based on [`.zenodo.json`](https://github.com/IdirBenSlama/Ophamin/blob/main/.zenodo.json)
metadata.

To verify: visit
https://zenodo.org/account/settings/github/repository/IdirBenSlama/Ophamin
and confirm the repository toggle is ON. The next push of a
`v<version>` tag mints a fresh DOI.

After the DOI mints, add a badge to README.md:

```markdown
[![DOI](https://zenodo.org/badge/DOI/<minted-doi>.svg)](https://doi.org/<minted-doi>)
```

(The "all-versions" DOI in `[![DOI]](...)` style points at every
release; per-release DOIs are accessible from the release page.)

## 6. Build + verify the Docker image

```bash
docker build -t ophamin:<version> .
docker run --rm ophamin:<version> --help
```

(The image is CORE-only — `pip install -e .` with no extras. See
[`Dockerfile`](https://github.com/IdirBenSlama/Ophamin/blob/main/Dockerfile) for the scope rationale.)

## 7. Regenerate the SBOM

```bash
bash scripts/generate_sbom.sh --scan
```

Commit the refreshed `sbom/ophamin.cdx.json` + `sbom/ophamin.cdx.txt`
on the **next** patch release; do NOT include in the release commit
(keeps the release commit minimal + signed).

## 8. Post-release housekeeping

- [ ] Update README badge versions if not parameterised
- [ ] Close any release-blocking issues / RFCs as IMPLEMENTED
- [ ] Watch CI on `main` post-tag — the tag itself doesn't trigger a
      separate workflow, but the commit before the tag does

## Failure modes + recovery

- **CI red after push**: do NOT delete the tag. Patch on top with a
  `<version>.<patch+1>` release that addresses the failure. Deleting a
  pushed tag corrupts the Zenodo DOI relationship.
- **Wrong version in CITATION.cff**: same — patch with a follow-up
  release. The cited record stays at the original version.
- **SBOM mismatch**: SBOM is descriptive, not normative. Refresh on
  next patch.
