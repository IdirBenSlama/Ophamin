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
[`SCHEMAS.md`](../SCHEMAS.md); ophamin-version and schema-version are
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

## 5. Zenodo DOI (minor + major only)

Pre-requisite: the Zenodo–GitHub integration is configured. If not,
**this is owner-territory** — the owner authenticates Zenodo on
zenodo.org and authorises the GitHub repo. After that, every tagged
release auto-mints a DOI based on [`.zenodo.json`](../.zenodo.json)
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
[`Dockerfile`](../Dockerfile) for the scope rationale.)

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
