"""Hardening pins for the SonarQube Docker setup (0.50.0).

Ophamin ships SonarQube as a mandatory code-quality surface for
analyzing Kimera-SWM. These tests validate the static structure
WITHOUT requiring Docker to be running or SonarQube to be reachable —
the validation catches drift in:

- sonar/docker-compose.yml schema + service definitions + volumes
- sonar/sonar-project.kimera-swm.properties required keys
- scripts/sonar_{up,scan,down}.sh existence + executable bit
- docs/SONARQUBE.md presence + key sections
- mkdocs nav entry

Runtime validation (does SonarQube actually become healthy + can the
scanner reach it) is a separate empirical concern documented in
docs/SONARQUBE.md.
"""

from __future__ import annotations

import os
import stat
from pathlib import Path

import pytest
import yaml

REPO_ROOT = Path(__file__).parent.parent
SONAR_DIR = REPO_ROOT / "sonar"
SCRIPTS_DIR = REPO_ROOT / "scripts"
DOCS_DIR = REPO_ROOT / "docs"


# --------------------------------------------------------------------------
# File-presence pins
# --------------------------------------------------------------------------


def test_sonar_compose_file_exists():
    """The Docker Compose file is the canonical entry point for the
    SonarQube stack. Without it, `sonar_up.sh` has nothing to bring up."""
    assert (SONAR_DIR / "docker-compose.yml").is_file()


def test_sonar_project_properties_template_exists():
    """The Kimera-SWM scan config template MUST be present so
    `sonar_scan.sh` can copy it into the target directory."""
    assert (SONAR_DIR / "sonar-project.kimera-swm.properties").is_file()


@pytest.mark.parametrize("script_name", [
    "sonar_up.sh",
    "sonar_scan.sh",
    "sonar_down.sh",
])
def test_helper_script_exists(script_name):
    path = SCRIPTS_DIR / script_name
    assert path.is_file(), f"Helper script missing: scripts/{script_name}"


@pytest.mark.parametrize("script_name", [
    "sonar_up.sh",
    "sonar_scan.sh",
    "sonar_down.sh",
])
def test_helper_script_is_executable(script_name):
    """The scripts MUST have the executable bit set — `bash scripts/...`
    works without it but operators expect `./scripts/...` too."""
    path = SCRIPTS_DIR / script_name
    mode = path.stat().st_mode
    assert mode & stat.S_IXUSR, f"scripts/{script_name} missing user-execute bit"
    assert mode & stat.S_IXGRP, f"scripts/{script_name} missing group-execute bit"


def test_sonarqube_docs_page_exists():
    """The mandatory-integration docs page MUST be present
    (referenced from mkdocs.yml nav + docs/INTEROP_OVERVIEW links)."""
    assert (DOCS_DIR / "SONARQUBE.md").is_file()


# --------------------------------------------------------------------------
# docker-compose.yml schema
# --------------------------------------------------------------------------


@pytest.fixture(scope="module")
def compose_yaml() -> dict:
    return yaml.safe_load((SONAR_DIR / "docker-compose.yml").read_text())


def test_compose_has_sonarqube_and_sonardb_services(compose_yaml):
    """Both services MUST be defined: web-side SonarQube + PostgreSQL
    backend. Removing either breaks the stack."""
    services = compose_yaml.get("services", {})
    assert "sonarqube" in services
    assert "sonardb" in services


def test_compose_sonarqube_uses_community_edition(compose_yaml):
    """Ophamin's stack uses SonarQube Community Edition (free + open
    source). Don't accidentally drift to a paid Developer/Enterprise
    image without owner approval."""
    image = compose_yaml["services"]["sonarqube"]["image"]
    assert "community" in image.lower(), (
        f"sonarqube image should be the community edition; got {image!r}"
    )


def test_compose_postgres_pinned_to_major_version(compose_yaml):
    """Postgres image MUST be pinned (e.g. postgres:16-alpine), NOT
    `postgres:latest`. Bumping the major version is a coordinated
    operation that requires checking SonarQube's supported-PG list."""
    image = compose_yaml["services"]["sonardb"]["image"]
    assert image.startswith("postgres:"), f"postgres image expected; got {image!r}"
    assert image != "postgres:latest", "postgres:latest is forbidden — pin a major"
    # Format: postgres:16-alpine or postgres:16. We're flexible about variant.
    suffix = image.split(":", 1)[1]
    assert suffix[0].isdigit(), f"postgres tag should start with a major version digit; got {suffix!r}"


def test_compose_sonarqube_depends_on_sonardb_healthy(compose_yaml):
    """SonarQube cannot start before PostgreSQL is ready. The
    depends_on condition MUST be `service_healthy`, NOT `service_started`
    (which fires immediately on the container starting, before PG
    accepts connections — produces flaky boots)."""
    depends = compose_yaml["services"]["sonarqube"]["depends_on"]
    assert depends["sonardb"]["condition"] == "service_healthy"


def test_compose_sonarqube_publishes_port_9000(compose_yaml):
    """Web UI MUST be reachable from host at :9000."""
    ports = compose_yaml["services"]["sonarqube"]["ports"]
    assert "9000:9000" in ports


def test_compose_postgres_port_not_published(compose_yaml):
    """PostgreSQL port 5432 should NOT be published — it's internal-only.
    Publishing it adds an unnecessary attack surface."""
    # `ports` key may be missing entirely (good) OR present but empty (also good).
    ports = compose_yaml["services"].get("sonardb", {}).get("ports", [])
    for port in ports:
        # Reject anything that looks like a PG port publish
        assert "5432" not in str(port), (
            f"PostgreSQL port 5432 should NOT be host-published; got {port!r}"
        )


def test_compose_sonarqube_has_healthcheck(compose_yaml):
    """A healthcheck is required for the helper scripts' wait-loop +
    for depends_on chains in larger stacks."""
    assert "healthcheck" in compose_yaml["services"]["sonarqube"]


def test_compose_postgres_has_healthcheck(compose_yaml):
    """Same for the PG side."""
    assert "healthcheck" in compose_yaml["services"]["sonardb"]


def test_compose_has_all_required_named_volumes(compose_yaml):
    """Four named volumes MUST be declared so docker compose down
    preserves state by default (volumes survive without -v flag)."""
    volumes = compose_yaml.get("volumes", {})
    required = {"sonarqube_data", "sonarqube_extensions", "sonarqube_logs", "sonardb_data"}
    declared = set(volumes.keys())
    missing = required - declared
    assert not missing, f"Missing required named volumes: {missing}"


def test_compose_volume_names_are_namespaced(compose_yaml):
    """Each named volume MUST carry an `ophamin_` prefix in its `name:`
    field so it doesn't collide with other compose stacks on the same
    host."""
    volumes = compose_yaml.get("volumes", {})
    for vol_key, vol_config in volumes.items():
        if isinstance(vol_config, dict):
            actual_name = vol_config.get("name", "")
            assert actual_name.startswith("ophamin_"), (
                f"Volume {vol_key} should have `name:` prefixed with `ophamin_`; "
                f"got {actual_name!r}"
            )


def test_compose_sonarqube_has_ulimits(compose_yaml):
    """SonarQube's bundled Elasticsearch requires raised ulimits.
    Without them the search engine fails with `vm.max_map_count too low`."""
    sonarqube = compose_yaml["services"]["sonarqube"]
    assert "ulimits" in sonarqube, "sonarqube service requires `ulimits:` for ES"
    ulimits = sonarqube["ulimits"]
    assert "nofile" in ulimits or "nproc" in ulimits


def test_compose_sonarqube_telemetry_off_by_default(compose_yaml):
    """Don't ship telemetry-enabled-by-default. Operators can opt in
    explicitly if they want to share usage stats with SonarSource."""
    env = compose_yaml["services"]["sonarqube"]["environment"]
    if "SONAR_TELEMETRY_ENABLE" in env:
        assert str(env["SONAR_TELEMETRY_ENABLE"]).lower() == "false"


def test_compose_restart_policy_is_unless_stopped(compose_yaml):
    """Both services should auto-restart unless explicitly stopped —
    survives host reboots without operator intervention."""
    for service in ("sonarqube", "sonardb"):
        restart = compose_yaml["services"][service].get("restart", "no")
        assert restart == "unless-stopped", (
            f"{service} restart policy should be unless-stopped; got {restart!r}"
        )


# --------------------------------------------------------------------------
# sonar-project.kimera-swm.properties contents
# --------------------------------------------------------------------------


@pytest.fixture(scope="module")
def sonar_properties() -> dict[str, str]:
    """Parse the .properties file into a dict."""
    text = (SONAR_DIR / "sonar-project.kimera-swm.properties").read_text()
    props: dict[str, str] = {}
    pending_value: list[str] = []
    pending_key: str | None = None
    for line in text.splitlines():
        line = line.rstrip()
        if not line or line.lstrip().startswith("#"):
            continue
        if pending_key is not None:
            # Continuation of a multi-line value (ended with backslash)
            value = line.lstrip()
            if value.endswith("\\"):
                pending_value.append(value[:-1].rstrip(","))
            else:
                pending_value.append(value)
                props[pending_key] = ",".join(pending_value)
                pending_key = None
                pending_value = []
            continue
        if "=" in line:
            key, value = line.split("=", 1)
            key = key.strip()
            value = value.strip()
            if value.endswith("\\"):
                pending_key = key
                pending_value = [value[:-1].rstrip(",")]
            else:
                props[key] = value
    return props


def test_sonar_project_key_is_kimera_swm(sonar_properties):
    """The project key is the stable identifier under which scans
    accumulate. Changing it forks scan history."""
    assert sonar_properties.get("sonar.projectKey") == "kimera-swm"


def test_sonar_sources_includes_kimera_swm(sonar_properties):
    """The production code path MUST be `kimera_swm` — that's where
    Kimera-SWM's 3,800+ Python files live."""
    sources = sonar_properties.get("sonar.sources", "")
    assert "kimera_swm" in sources


def test_sonar_python_version_pinned(sonar_properties):
    """Pin the Python version so the analyzer applies the right rule
    set (no Python-2-era rules on a 3.12 project)."""
    py_ver = sonar_properties.get("sonar.python.version", "")
    assert py_ver, "sonar.python.version must be set"
    assert py_ver.startswith("3."), f"Python 3 required; got {py_ver!r}"


def test_sonar_tests_includes_both_test_trees(sonar_properties):
    """Both `tests/` (top-level) AND `kimera_swm/tests/` (in-tree)
    contain test code — both must be listed under sonar.tests."""
    tests = sonar_properties.get("sonar.tests", "")
    assert "tests" in tests
    assert "kimera_swm/tests" in tests or "kimera_swm" in tests


def test_sonar_exclusions_skip_archives(sonar_properties):
    """The `_archive/` + `_legacy_intake/` directories carry preserved-
    but-not-active code. Excluding them prevents noise + false
    positives against retired code."""
    exclusions = sonar_properties.get("sonar.exclusions", "")
    assert "_archive" in exclusions
    assert "_legacy_intake" in exclusions or "legacy" in exclusions


def test_sonar_exclusions_skip_venv_and_caches(sonar_properties):
    """Standard hygiene — don't scan .venv / __pycache__ / .mypy_cache
    / .ruff_cache / .hypothesis (generated content)."""
    exclusions = sonar_properties.get("sonar.exclusions", "")
    for noise in ("__pycache__", ".venv", ".mypy_cache", ".ruff_cache", ".hypothesis"):
        assert noise in exclusions, f"Exclusions missing: {noise}"


def test_sonar_exclusions_skip_observatory_runs(sonar_properties):
    """`experiments/observatory/runs/` contains scenario-run outputs
    (JSON + logs). Scanning them produces nothing useful."""
    exclusions = sonar_properties.get("sonar.exclusions", "")
    assert "observatory/runs" in exclusions or "experiments" in exclusions


def test_sonar_cpd_exclusions_skip_tests(sonar_properties):
    """Code-Pattern-Detection (duplication scan) should ignore test
    files — test code has justified repetition (fixtures, parametrize)."""
    cpd_exclusions = sonar_properties.get("sonar.cpd.exclusions", "")
    assert "test" in cpd_exclusions.lower()


def test_sonar_coverage_report_path_set(sonar_properties):
    """When `--with-coverage` is passed, the scanner reads coverage.xml.
    The property MUST be set so the scanner knows where to look."""
    cov_path = sonar_properties.get("sonar.python.coverage.reportPaths", "")
    assert cov_path, "sonar.python.coverage.reportPaths must be set"
    assert "coverage.xml" in cov_path


def test_sonar_host_url_defaults_to_localhost_9000(sonar_properties):
    """Default scanner target is the bundled compose stack. Operators
    can override via -Dsonar.host.url=... for a remote SonarQube."""
    host_url = sonar_properties.get("sonar.host.url", "")
    assert "localhost:9000" in host_url or "127.0.0.1:9000" in host_url


def test_sonar_source_encoding_is_utf8(sonar_properties):
    """Python source files are UTF-8; pin the encoding explicitly so
    the analyzer doesn't default to platform encoding."""
    assert sonar_properties.get("sonar.sourceEncoding") == "UTF-8"


# --------------------------------------------------------------------------
# Helper-script content invariants
# --------------------------------------------------------------------------


def test_sonar_up_script_uses_compose_file_path():
    """The up script MUST reference sonar/docker-compose.yml exactly —
    drift in the path would silently bring up nothing."""
    content = (SCRIPTS_DIR / "sonar_up.sh").read_text()
    assert "sonar/docker-compose.yml" in content


def test_sonar_up_script_has_set_e():
    """All bash helper scripts must have `set -e` so the first failure
    is loud, not silent."""
    content = (SCRIPTS_DIR / "sonar_up.sh").read_text()
    assert "set -e" in content


def test_sonar_scan_script_requires_sonar_token():
    """The scan script MUST refuse to run without SONAR_TOKEN —
    silently scanning with no auth produces a Sonar guest-mode
    submission that gets rejected at the server side."""
    content = (SCRIPTS_DIR / "sonar_scan.sh").read_text()
    assert "SONAR_TOKEN" in content
    assert "required" in content.lower() or "must" in content.lower()


def test_sonar_scan_script_uses_sonarsource_scanner():
    """The scanner runs in Docker via sonarsource/sonar-scanner-cli.
    Don't drift to alternative scanner images that may not match the
    server's analyzer version."""
    content = (SCRIPTS_DIR / "sonar_scan.sh").read_text()
    assert "sonarsource/sonar-scanner-cli" in content


def test_sonar_scan_script_supports_with_coverage_flag():
    """The --with-coverage flag is the documented way to include
    pytest coverage in the scan."""
    content = (SCRIPTS_DIR / "sonar_scan.sh").read_text()
    assert "--with-coverage" in content


def test_sonar_down_script_default_preserves_volumes():
    """`sonar_down.sh` (no flag) MUST preserve named volumes. Wiping
    state requires explicit --wipe + confirmation. Drift here would
    silently destroy SonarQube history on every stop."""
    content = (SCRIPTS_DIR / "sonar_down.sh").read_text()
    # Default path uses `docker compose down` (no -v); --wipe uses `down -v`
    assert "docker compose -f \"$COMPOSE_FILE\" down\n" in content \
        or "compose -f \"$COMPOSE_FILE\" down" in content


def test_sonar_down_script_wipe_requires_confirmation():
    """`--wipe` MUST require explicit confirmation (typing 'wipe') OR
    the OPHAMIN_SONAR_WIPE_CONFIRMED=yes env var. Otherwise a typo
    `bash scripts/sonar_down.sh --wipe` destroys all scan history
    without a second chance."""
    content = (SCRIPTS_DIR / "sonar_down.sh").read_text()
    assert "wipe" in content.lower()
    # Either interactive prompt OR env var gate
    assert "read" in content or "OPHAMIN_SONAR_WIPE_CONFIRMED" in content


# --------------------------------------------------------------------------
# docs/SONARQUBE.md content
# --------------------------------------------------------------------------


def test_sonarqube_doc_mentions_mandatory():
    """The doc MUST flag SonarQube as a mandatory surface (per owner
    directive). Drifting to optional/recommended/etc. silently
    downgrades the integration."""
    content = (DOCS_DIR / "SONARQUBE.md").read_text()
    assert "mandatory" in content.lower()


def test_sonarqube_doc_documents_quick_start():
    """A copy-paste quick-start section is the load-bearing
    operator-facing content. Without it the doc is useless for
    new operators."""
    content = (DOCS_DIR / "SONARQUBE.md").read_text()
    assert "sonar_up.sh" in content
    assert "sonar_scan.sh" in content
    assert "sonar_down.sh" in content


def test_sonarqube_doc_in_mkdocs_nav():
    """The doc MUST be in the mkdocs nav — otherwise it's only
    accessible to people who know the URL."""
    nav = (REPO_ROOT / "mkdocs.yml").read_text()
    assert "SONARQUBE.md" in nav


def test_sonarqube_doc_links_to_helper_scripts():
    """The doc cross-references the helper scripts. A drift in the
    scripts' filenames or paths would break the docs."""
    content = (DOCS_DIR / "SONARQUBE.md").read_text()
    for script in ("sonar_up.sh", "sonar_scan.sh", "sonar_down.sh"):
        assert script in content, f"docs/SONARQUBE.md should reference scripts/{script}"
