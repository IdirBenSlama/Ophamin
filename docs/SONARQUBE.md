# SonarQube — mandatory code-quality + SAST surface for Kimera-SWM

> Ophamin ships a **mandatory** SonarQube stack for static
> analysis + code-quality reporting against Kimera-SWM (and any
> other Python substrate target). SonarQube CE + PostgreSQL +
> persistent volumes run via Docker Compose; a sonar-project
> properties template + three helper scripts make a complete
> scan reproducible in under five minutes.

## Quick start

```bash
# 1. Bring up the stack (~60-90s first boot)
bash scripts/sonar_up.sh

# 2. Open http://localhost:9000
#    Default admin / admin → change password on first login
#    Generate a token at: /account/security
#    Export it:
export SONAR_TOKEN=<your-token>

# 3. Scan a Kimera-SWM checkout
bash scripts/sonar_scan.sh /path/to/Kimera_SWM

# 4. (later) Stop the stack — volumes preserved
bash scripts/sonar_down.sh
```

The scan dashboard lands at
`http://localhost:9000/dashboard?id=kimera-swm`.

## CI integration (0.51.0)

The `.github/workflows/sonar.yml` workflow brings up an
**ephemeral** SonarQube stack inside CI (same image pins as
`sonar/docker-compose.yml` — drift-free across CI vs local)
and runs a scan against the Ophamin source tree on every:

- Push to `main` (baseline scan; updates Sonar history)
- Push to `v*` tag (release-cut scan)
- Pull request to `main` (per-PR scan; surfaces drift before merge)
- Manual `workflow_dispatch`

The workflow uses GitHub Actions `services:` containers to
spin up SonarQube + PostgreSQL — no persistent state between
runs. Quality-gate enforcement is **warn-only** in 0.51.0
(operators need history to tune the "Sonar way" defaults
against). A future ship can flip the gate to a hard exit-1
once thresholds are stable.

**Scope note:** the CI workflow scans **Ophamin itself**, not
Kimera-SWM. Kimera-SWM lives in a separate repo and would
need its own `sonar.yml` (or a multi-repo orchestration step
that checks out the Kimera-SWM tree before scanning). For
in-CI Kimera-SWM analysis, copy `.github/workflows/sonar.yml`
into the Kimera-SWM repo + adjust `sonar.sources` /
`sonar.tests` to point at `kimera_swm/` + `tests/`.

For **persistent** / cross-run SonarQube history (e.g. tracking
issue trends over time), use the bundled stack locally per
the Quick Start above, or wire a self-hosted runner that
replaces `services:` with `SONAR_HOST_URL` pointing at a
long-lived SonarQube.

## Security scanning (0.52.0)

Phase #2 of the 4-phase integration roadmap pairs SonarQube
SAST with **Software Composition Analysis (SCA)** via two
complementary tools:

### Trivy — container + repository CVE scanner

`.github/workflows/trivy.yml` runs two scan jobs:

- **`fs-scan`** — repository scan on every push + PR + weekly
  schedule. Covers source-tree deps + Dockerfile +
  IaC manifests against the public CVE database.
- **`image-scan`** — scans the PUBLISHED GHCR image
  (`ghcr.io/idirbenslama/ophamin:<tag>`) for OS-package + Python-
  package CVEs. Runs on main push + tag push + weekly schedule.
  (PRs skip image-scan because the PR's image isn't published yet.)

Both jobs emit SARIF reports + upload them to GitHub Code
Scanning so findings appear in the Security tab alongside
SonarQube-surface issues. Severity gate: HIGH + CRITICAL
only (MEDIUM + LOW are advisory). **Warn-only** in 0.52.0
(exit-code: "0"); future ship can flip to hard-fail once
operators have history.

Trivy is Apache-2.0 (Aqua Security) — no auth required for the
public CVE database.

### OWASP Dependency-Check — CVE ingest into SonarQube

A new step in `.github/workflows/sonar.yml` runs OWASP
Dependency-Check + ingests its SARIF report alongside the
SonarQube SAST findings:

```yaml
- name: Run OWASP Dependency-Check (best-effort, ingests into SonarQube)
  continue-on-error: true
  env:
    NVD_API_KEY: ${{ secrets.NVD_API_KEY }}
  # ... docker run owasp/dependency-check:latest --scan ... --format SARIF
```

**NVD API key**: OWASP DC downloads the National Vulnerability
Database (NVD) on first run. Without an API key, downloads can
be rate-limited. Register one at
<https://nvd.nist.gov/developers/request-an-api-key> + add it
to the repo's Settings → Secrets → Actions as `NVD_API_KEY`.
The workflow uses it when present, falls back to rate-limited
download when absent.

**NVD cache**: the workflow uses `actions/cache@v4` to persist
the `dependency-check-data/` directory across runs. Cold cache
runs take ~10 min; warm cache runs take ~30s.

### Together with SonarQube + supply-chain trilogy

After 0.52.0 the security claim is:

| Layer | Tool | What it catches |
|---|---|---|
| SAST | SonarQube + Sonar's Python analyzer | bugs, code smells, hot-spot review, vulnerabilities in code |
| SCA (deps) | OWASP Dependency-Check | declared + transitive CVEs |
| SCA (image) | Trivy fs-scan + image-scan | OS-package + lib CVEs in the deployed surface |
| Image signature | cosign keyless (0.42.0) | tampering / wrong-source detection |
| SBOM attestation | CycloneDX via cosign (0.48.0) | "what's inside" cryptographic claim |
| SLSA provenance | actions/attest-build-provenance (0.49.x) | "how it was built" cryptographic claim |

Six independent layers, all verifiable, all surfaced either in
SonarQube's dashboard or GitHub's Security tab.

## Local IDE guardrails (0.53.0)

Phase #3 of the 4-phase integration roadmap ships
`.sonarlint/connectedMode.json` — a SonarQube-for-IDE
connected-mode binding that auto-detects when operators open
the Ophamin repo in any SonarLint-compatible editor:

| IDE | Extension |
|---|---|
| VS Code / VSCodium / Cursor | `SonarSource.sonarlint-vscode` |
| IntelliJ IDEA / PyCharm / WebStorm | `org.sonarlint.idea` |
| Eclipse | SonarLint plugin |
| Visual Studio | `SonarSource.SonarQubeForVS` |

After installing the extension + bringing up the bundled
SonarQube via `bash scripts/sonar_up.sh`, the IDE binds
automatically to `http://localhost:9000` with project key
`ophamin`. Every file you edit gets real-time analysis using
the **same rules as the CI pipeline** — no more "passes
locally, fails in PR" surprises.

For AI-assisted coding (Cursor, Copilot, etc.), this is the
**immediate** guardrail: AI-generated code gets analyzed as
it lands in the editor, before commit, before PR, before any
CI runs. Bugs + vulnerabilities + code smells surface in
real time.

See [`.sonarlint/README.md`](https://github.com/IdirBenSlama/Ophamin/blob/main/.sonarlint/README.md)
for the 4-step quick-start + the standalone-vs-connected
mode distinction.

## Deployment & GitOps (0.54.0)

Phase #4 of the 4-phase integration roadmap closes the
CI → GitOps loop with an ArgoCD Application manifest at
`argocd/ophamin-application.yaml`:

```bash
# Pre-req: K8s cluster with ArgoCD installed
kubectl apply -f argocd/ophamin-application.yaml -n argocd
```

The Application watches `oci://ghcr.io/idirbenslama/ophamin`
(the cosign-signed Helm chart from 0.41.0+) + auto-syncs to a
target K8s cluster. Sync policy:

- **`automated.prune: true`** — removes orphaned K8s resources
  on chart-version bumps
- **`automated.selfHeal: true`** — rolls back drift in the
  cluster (a kubectl-edit gets undone on next reconcile)
- **`CreateNamespace=true`** — bootstraps the target namespace
- **Retry with exponential backoff** (5 attempts, factor 2,
  max 3 min) — resilient to transient API-server errors

Pairs with Sigstore `policy-controller` ClusterImagePolicy for
**admission-time enforcement** of the supply-chain trilogy:
signature + SBOM + SLSA attestation all checked BEFORE the
Pod can start. See [`argocd/README.md`](https://github.com/IdirBenSlama/Ophamin/blob/main/argocd/README.md)
for the ClusterImagePolicy example + the full deployment-pipeline
ASCII diagram.

After 0.54.0 the full pipeline is:

```text
Edit (with SonarLint guardrail) → Push → GH Actions CI
  (sonar.yml + trivy.yml + docker.yml + chart.yml)
  → cosign-signed GHCR artifacts with SBOM + SLSA
  → ArgoCD auto-sync
  → policy-controller admission-gate
  → Ophamin running in production with full provenance
```

## All four integration phases — complete

| Phase | Release | What landed |
|---|---|---|
| #1 — CI automation | `0.51.0` | `sonar.yml` workflow: ephemeral SonarQube in CI services; per-PR + per-main scans; Quality Gate visible (warn-only) |
| #2 — Security & deps | `0.52.0` | `trivy.yml` workflow (fs-scan + image-scan); OWASP DC step in `sonar.yml`; all SARIF in Code Scanning |
| #3 — Local guardrails | `0.53.0` | `.sonarlint/connectedMode.json` for VS Code / Cursor / IntelliJ / Eclipse |
| #4 — Deployment & GitOps | `0.54.0` | `argocd/ophamin-application.yaml` for K8s auto-sync of the cosign-signed Helm chart |

**Six independent security + quality layers** after 0.54.0:
SAST (SonarQube) + SCA deps (OWASP DC) + SCA image (Trivy) +
signature (cosign) + SBOM (CycloneDX attestation) + SLSA
provenance. All verifiable, all surfaced in either the
SonarQube dashboard, GitHub Security tab, or via
`cosign verify` / `gh attestation verify`.

## Why "mandatory"

Ophamin's value proposition is **measured + signed claims about
a substrate**. The Tier-1 interop layers (in-toto, RO-Crate,
OpenLineage) cover the empirical-measurement side. The
auditing wheel (ruff, bandit, mypy, pip-audit) covers per-PR
static checks. **SonarQube fills the gap between them**:
project-level code-quality history + SAST trend tracking +
quality-gate enforcement that the per-PR linters can't
provide.

Without SonarQube, Ophamin can sign Kimera-SWM's empirical
findings but not surface the substrate's own code-quality
posture over time. SonarQube changes that — every scan
produces a dashboard with:

- **Bugs / vulnerabilities / security hotspots** tracked
  across commits
- **Code smells** + maintainability index
- **Cyclomatic complexity** + cognitive complexity heatmap
  per file
- **Duplication** percentage + per-block locations
- **Test coverage** (when `--with-coverage` is passed)
- **External-linter ingest** for ruff / bandit / mypy
  (when their respective `--with-*` flags are passed)
- **Quality gate** pass/fail status with configurable
  thresholds

A scan against current Kimera-SWM (~3,800 production files +
~1,459 test files) typically takes 5-10 minutes wall-clock and
produces ~10,000+ Sonar issues — most of them code-smells +
maintainability hints, not critical bugs.

## What gets deployed

`docker-compose.yml` at [`sonar/docker-compose.yml`](https://github.com/IdirBenSlama/Ophamin/blob/main/sonar/docker-compose.yml)
brings up:

| Container | Image | Purpose |
|---|---|---|
| `ophamin-sonarqube` | `sonarqube:25-community` | Web UI on `:9000`, compute engine, bundled Elasticsearch |
| `ophamin-sonardb` | `postgres:16-alpine` | SonarQube's metadata + scan-history database |

Persistent named volumes:

- `ophamin_sonarqube_data` — issues, projects, history
- `ophamin_sonarqube_extensions` — installed plugins
- `ophamin_sonarqube_logs` — log files
- `ophamin_sonardb_data` — PostgreSQL data dir

`bash scripts/sonar_down.sh` stops containers but **preserves
volumes**. Use `bash scripts/sonar_down.sh --wipe` (with explicit
confirmation prompt) to also delete volumes — destroys ALL
SonarQube history.

## What gets scanned

The bundled `sonar-project.kimera-swm.properties` configures
the scanner for Kimera-SWM's specific layout:

| Property | Value | Why |
|---|---|---|
| `sonar.projectKey` | `kimera-swm` | Stable key — multi-scan history accumulates under this key |
| `sonar.sources` | `kimera_swm/` | The substrate codebase (~3,800 files at 2026-05-19) |
| `sonar.tests` | `tests/,kimera_swm/tests/` | Both test trees (~1,459 files) |
| `sonar.python.version` | `3.12` | Ophamin's pinned Python version |
| `sonar.exclusions` | bytecode + caches + `.venv` + `_archive/` + `_legacy_intake/` + `Docs_v2/` + `experiments/observatory/runs/` + proof artifacts + sbom | Noise reduction; these dirs contain generated / archived / non-source content |
| `sonar.cpd.exclusions` | `test_*.py`, `conftest.py` | Test code has justified repetition (fixtures, parametrize) |

Override any value via `-D<key>=<value>` on the
`sonar-scanner` command line if needed for a specific run.

## Coverage + external-linter ingest

The `sonar_scan.sh` wrapper supports four ingest modes via
flags:

```bash
# Just the scan (Sonar's own Python analyzer)
bash scripts/sonar_scan.sh /path/to/Kimera_SWM

# Plus test coverage (runs pytest --cov first)
bash scripts/sonar_scan.sh /path/to/Kimera_SWM --with-coverage

# Plus ruff issues (ingested with their ruff rule IDs)
bash scripts/sonar_scan.sh /path/to/Kimera_SWM --with-ruff

# Plus bandit security findings
bash scripts/sonar_scan.sh /path/to/Kimera_SWM --with-bandit

# All four
bash scripts/sonar_scan.sh /path/to/Kimera_SWM \
    --with-coverage --with-ruff --with-bandit
```

Each `--with-*` flag generates the corresponding report
in-place under the target directory + passes its path to the
scanner. The flags are independent; mix freely.

## Quality gates

Defaults from SonarQube's "Sonar way" quality gate (active
on first install):

| Metric (new code) | Threshold | Failure mode |
|---|---|---|
| Bugs | 0 | Quality gate fails |
| Vulnerabilities | 0 | Quality gate fails |
| Security Hotspots Reviewed | 100% | Quality gate fails |
| Coverage | ≥ 80% | Quality gate fails |
| Duplicated Lines | ≤ 3% | Quality gate fails |
| Maintainability Rating | A | Quality gate fails |
| Reliability Rating | A | Quality gate fails |
| Security Rating | A | Quality gate fails |

Customize at `http://localhost:9000/quality_gates`. Gate applies
to **new code** (defined by the project's new-code reference);
historical code is reported but not gated.

## Architecture

```text
      ┌─────────────────────────┐
      │ Kimera-SWM checkout     │
      │  (source tree, tests)   │
      └────────────┬────────────┘
                   │ mounted as /usr/src
                   ▼
      ┌────────────────────────────────────────────┐
      │ sonarsource/sonar-scanner-cli (Docker)     │
      │  - parses sonar-project.properties         │
      │  - analyzes Python sources                 │
      │  - ingests coverage.xml + ruff + bandit    │
      │  - submits results via HTTP                │
      └────────────┬───────────────────────────────┘
                   │ POST localhost:9000 (--network=host)
                   ▼
      ┌────────────────────────────────────────────┐
      │  ophamin-sonarqube  (sonarqube:25-community)│
      │  - web UI (:9000)                           │
      │  - compute engine                           │
      │  - bundled Elasticsearch                    │
      │  - persistent data + extensions + logs     │
      └────────────┬───────────────────────────────┘
                   │ JDBC
                   ▼
      ┌────────────────────────────────────────────┐
      │  ophamin-sonardb  (postgres:16-alpine)      │
      │  - metadata + scan history                 │
      └────────────────────────────────────────────┘
```

All three containers live on a Docker Compose internal network.
Only the SonarQube web UI port (`9000`) is published to the
host. The scanner uses `--network=host` to reach
`localhost:9000` from the scanner container.

## Operating considerations

### Memory + ulimits

SonarQube ships with bundled Elasticsearch, which requires
raised `nofile` + `nproc` ulimits + a 4 GB working set. The
compose file sets both ulimits and a 1g/2g/1g Java heap split
across web / compute engine / search. **Less than 4 GB RAM
available to Docker will produce intermittent OOM-killed
Elasticsearch behavior** — the compose file declares this
explicitly in comments.

### Backups

`ophamin_sonarqube_data` + `ophamin_sonardb_data` are the
load-bearing volumes; `_extensions` + `_logs` are reproducible.
For a backup:

```bash
docker run --rm \
    -v ophamin_sonarqube_data:/data \
    -v "$(pwd):/backup" \
    alpine tar czf /backup/sonarqube-data-$(date +%Y%m%d).tar.gz -C /data .

docker run --rm \
    -v ophamin_sonardb_data:/data \
    -v "$(pwd):/backup" \
    alpine tar czf /backup/sonardb-data-$(date +%Y%m%d).tar.gz -C /data .
```

Restore with the inverse.

### Upgrading SonarQube

SonarQube's data-migration step runs automatically on first
boot of a newer version IF the JDBC URL points to a
SonarQube-managed PostgreSQL whose schema is one minor version
back from the new SonarQube. **Across LTS boundaries**, follow
SonarSource's [upgrade guide](https://docs.sonarsource.com/sonarqube-server/latest/setup-and-upgrade/upgrade-the-server/upgrade-guide/)
before changing the `image:` tag in compose.

### Updating the bundled Python analyzer

SonarQube ships its own Python analyzer with each release;
no separate update required. To see the Python rules' current
catalogue:
[`http://localhost:9000/coding_rules?languages=py`](http://localhost:9000/coding_rules?languages=py)

## Mandatory integration with the rest of Ophamin

SonarQube is the **9th interop / observability surface** Ophamin
ships (after the 8 interop layers from 0.16.0 → 0.39.0). It's
mandatory in the sense that:

- Every Ophamin operator analyzing Kimera-SWM has it available
  by default — no additional install step.
- The compose stack is tracked in git (`sonar/`), not externally
  hosted.
- The helper scripts (`sonar_up.sh` / `sonar_scan.sh` /
  `sonar_down.sh`) bring it from cold-start to scan-result in
  under 5 minutes.
- Hardening pins (`tests/test_sonar_setup.py`) catch drift in
  the compose file structure + scanner properties.

Unlike the in-toto / RO-Crate / OpenLineage layers (which are
**export-only** wrappers around signed proof records),
SonarQube is **runtime infrastructure** — it has its own
state, its own UI, its own auth. The 8 interop layers + the
SonarQube stack together cover the full
"empirical-claim-side" + "code-quality-side" of the
substrate-validation story.

## See also

- [SonarQube Server documentation](https://docs.sonarsource.com/sonarqube-server/latest/)
- [SonarQube Python rules catalogue](https://rules.sonarsource.com/python/)
- [`sonar/docker-compose.yml`](https://github.com/IdirBenSlama/Ophamin/blob/main/sonar/docker-compose.yml) — the stack definition
- [`sonar/sonar-project.kimera-swm.properties`](https://github.com/IdirBenSlama/Ophamin/blob/main/sonar/sonar-project.kimera-swm.properties) — the Kimera-SWM scan config
- [`scripts/sonar_up.sh`](https://github.com/IdirBenSlama/Ophamin/blob/main/scripts/sonar_up.sh) / [`scripts/sonar_scan.sh`](https://github.com/IdirBenSlama/Ophamin/blob/main/scripts/sonar_scan.sh) / [`scripts/sonar_down.sh`](https://github.com/IdirBenSlama/Ophamin/blob/main/scripts/sonar_down.sh) — the helper scripts
- [`tests/test_sonar_setup.py`](https://github.com/IdirBenSlama/Ophamin/blob/main/tests/test_sonar_setup.py) — hardening pins
- [`docs/SUPPLY_CHAIN.md`](SUPPLY_CHAIN.md) — supply-chain provenance (cosign + SBOM + SLSA)
- [`docs/INTEROP_OVERVIEW.md`](INTEROP_OVERVIEW.md) — the 8 interop layers
