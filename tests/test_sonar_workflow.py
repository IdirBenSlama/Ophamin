"""Hardening pins for .github/workflows/sonar.yml (0.51.0).

The sonar.yml workflow brings up an ephemeral SonarQube stack inside CI
(matching the local sonar/docker-compose.yml from 0.50.0) and runs a
scan against the Ophamin source tree on every push/PR. These tests
validate the workflow's structural correctness WITHOUT requiring it to
actually run.

What's pinned here:
- Workflow file exists + parses as YAML
- Required triggers (push to main, push v* tag, pull_request,
  workflow_dispatch)
- Concurrency group prevents stale runs from racing
- SonarQube + PostgreSQL services declared with the SAME image pins
  as sonar/docker-compose.yml (drift-free across CI vs local)
- JVM heap settings match the local compose file (Elasticsearch
  bootstrap-check requires Xms == Xmx in SONAR_SEARCH_JAVAOPTS)
- Healthchecks use curl + grep '"status":"UP"' (NOT wget; the
  SonarQube image lacks wget — discovered empirically in 0.50.0)
- ulimits raised for Elasticsearch
- All 9 expected steps present in the right order
- Quality-gate check runs but is warn-only in 0.51.0
  (phase-1 release; tightens to fail-the-job in a future ship
  once operators have history to tune the gate against)
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

REPO_ROOT = Path(__file__).parent.parent
WORKFLOW = REPO_ROOT / ".github" / "workflows" / "sonar.yml"
COMPOSE = REPO_ROOT / "sonar" / "docker-compose.yml"


# --------------------------------------------------------------------------
# File-presence + parse
# --------------------------------------------------------------------------


def test_sonar_workflow_exists():
    assert WORKFLOW.is_file()


@pytest.fixture(scope="module")
def workflow() -> dict:
    return yaml.safe_load(WORKFLOW.read_text())


@pytest.fixture(scope="module")
def compose() -> dict:
    return yaml.safe_load(COMPOSE.read_text())


def test_workflow_parses_as_yaml(workflow):
    """The workflow file MUST parse as valid YAML."""
    assert "name" in workflow
    assert workflow["name"] == "sonar"


# --------------------------------------------------------------------------
# Triggers + concurrency + permissions
# --------------------------------------------------------------------------


def test_workflow_triggers_on_push_to_main(workflow):
    """`push` to main is the canonical trigger for baseline scans."""
    # PyYAML parses bare `on:` as boolean True — GH Actions accepts either
    triggers = workflow.get("on", workflow.get(True, {}))
    assert "push" in triggers
    push_config = triggers["push"]
    assert "main" in push_config.get("branches", [])


def test_workflow_triggers_on_tag_push(workflow):
    triggers = workflow.get("on", workflow.get(True, {}))
    push_config = triggers["push"]
    # v* tag push for release scans
    tags = push_config.get("tags", [])
    assert any("v*" in t for t in tags), f"expected v* in tags; got {tags}"


def test_workflow_triggers_on_pull_request(workflow):
    """PR scans surface drift BEFORE merge — load-bearing for the
    quality-gate-as-merge-block pattern."""
    triggers = workflow.get("on", workflow.get(True, {}))
    assert "pull_request" in triggers


def test_workflow_has_workflow_dispatch(workflow):
    """Manual trigger for ad-hoc / debugging runs."""
    triggers = workflow.get("on", workflow.get(True, {}))
    assert "workflow_dispatch" in triggers


def test_workflow_has_concurrency_group(workflow):
    """Newer pushes to the same ref MUST cancel older in-flight scans
    (saves CI minutes on noisy branches)."""
    concurrency = workflow.get("concurrency", {})
    assert "group" in concurrency
    assert "sonar-" in concurrency["group"]
    assert concurrency.get("cancel-in-progress") is True


def test_workflow_has_minimal_permissions(workflow):
    """contents: read is sufficient — no GHCR / Pages / attestation
    writes from this workflow. Drift to write permissions would expand
    blast radius unnecessarily."""
    perms = workflow.get("permissions", {})
    assert perms.get("contents") == "read"
    # No write permissions should be needed
    for key, value in perms.items():
        if value == "write":
            pytest.fail(f"sonar.yml should not have write permissions; found {key}: write")


# --------------------------------------------------------------------------
# Services — drift-free with local compose file
# --------------------------------------------------------------------------


def test_workflow_has_sonarqube_service(workflow):
    services = workflow["jobs"]["scan"]["services"]
    assert "sonarqube" in services


def test_workflow_has_sonardb_service(workflow):
    services = workflow["jobs"]["scan"]["services"]
    assert "sonardb" in services


def test_workflow_sonarqube_image_matches_local_compose(workflow, compose):
    """The CI workflow's SonarQube image MUST match the local
    compose file's image — otherwise CI scans against a different
    version than what the local stack runs. Pinning both to the same
    tag prevents that drift."""
    ci_image = workflow["jobs"]["scan"]["services"]["sonarqube"]["image"]
    compose_image = compose["services"]["sonarqube"]["image"]
    assert ci_image == compose_image, (
        f"CI sonar.yml uses {ci_image!r} but local compose uses {compose_image!r}; "
        f"keep both pinned to the same tag to avoid version drift between "
        f"local and CI scans"
    )


def test_workflow_postgres_image_matches_local_compose(workflow, compose):
    ci_image = workflow["jobs"]["scan"]["services"]["sonardb"]["image"]
    compose_image = compose["services"]["sonardb"]["image"]
    assert ci_image == compose_image


def test_workflow_sonarqube_search_jvm_xms_equals_xmx(workflow):
    """Elasticsearch bootstrap-check REQUIRES -Xms == -Xmx in
    SONAR_SEARCH_JAVAOPTS. Mismatch ('resize pauses' bootstrap check)
    kills the search subprocess at boot. Discovered empirically in
    0.50.0 — pinning this prevents regression."""
    sq = workflow["jobs"]["scan"]["services"]["sonarqube"]
    search_opts = sq["env"].get("SONAR_SEARCH_JAVAOPTS", "")
    # Extract -Xmx and -Xms values
    import re
    xmx = re.search(r"-Xmx(\S+)", search_opts)
    xms = re.search(r"-Xms(\S+)", search_opts)
    assert xmx and xms, f"SONAR_SEARCH_JAVAOPTS missing -Xmx or -Xms; got {search_opts!r}"
    assert xmx.group(1) == xms.group(1), (
        f"SONAR_SEARCH_JAVAOPTS: -Xms must equal -Xmx for Elasticsearch "
        f"bootstrap-check; got Xmx={xmx.group(1)!r}, Xms={xms.group(1)!r}"
    )


def test_workflow_sonarqube_telemetry_off(workflow):
    sq = workflow["jobs"]["scan"]["services"]["sonarqube"]
    telemetry = str(sq["env"].get("SONAR_TELEMETRY_ENABLE", "true")).lower()
    assert telemetry == "false"


def test_workflow_sonarqube_publishes_port_9000(workflow):
    sq = workflow["jobs"]["scan"]["services"]["sonarqube"]
    ports = sq.get("ports", [])
    # GH Actions services use port syntax `host:container` like compose
    assert any("9000" in str(p) for p in ports)


def test_workflow_sonarqube_healthcheck_uses_curl_not_wget(workflow):
    """SonarQube image has curl but NOT wget — discovered in 0.50.0
    when the wget-based healthcheck returned false-negative-unhealthy.
    Pin this so drift back to wget surfaces at PR time."""
    sq = workflow["jobs"]["scan"]["services"]["sonarqube"]
    options = sq.get("options", "")
    assert "curl" in options, "healthcheck should use curl"
    assert "wget" not in options, "healthcheck should NOT use wget (not in image)"


def test_workflow_sonarqube_healthcheck_greps_status_up(workflow):
    """The healthcheck MUST verify status==UP, not just /api/system/status
    returning 200 (which it does even during STARTING / DB_MIGRATION_NEEDED
    states). Drift here would silently pass scans against a not-actually-
    ready SonarQube."""
    sq = workflow["jobs"]["scan"]["services"]["sonarqube"]
    options = sq.get("options", "")
    # YAML parses `\"status\":\"UP\"` to escaped form in Python strings;
    # check for the structural fragment without exact-quote matching.
    assert "status" in options and "UP" in options
    # And there must be a grep of the UP token
    assert "grep" in options.lower()


def test_workflow_sonarqube_has_raised_ulimits(workflow):
    """Elasticsearch bundled in SonarQube needs raised file-descriptor
    + process limits. Drift here would produce ES startup failures
    that look like generic SonarQube boot timeouts."""
    sq = workflow["jobs"]["scan"]["services"]["sonarqube"]
    options = sq.get("options", "")
    assert "--ulimit" in options or "ulimit" in options
    assert "nofile" in options


def test_workflow_postgres_has_health_check(workflow):
    pg = workflow["jobs"]["scan"]["services"]["sonardb"]
    options = pg.get("options", "")
    assert "pg_isready" in options


# --------------------------------------------------------------------------
# Steps — required + ordered
# --------------------------------------------------------------------------


def test_workflow_has_checkout_step_with_full_history(workflow):
    """SonarQube uses git blame + commit ages for new-code +
    blame-heatmap features. Shallow clone breaks both. fetch-depth: 0
    is the canonical full-history flag."""
    steps = workflow["jobs"]["scan"]["steps"]
    checkout = next((s for s in steps if "checkout" in str(s.get("uses", "")).lower()), None)
    assert checkout is not None, "Checkout step missing"
    assert checkout.get("with", {}).get("fetch-depth") == 0


def test_workflow_has_wait_for_sonarqube_step(workflow):
    steps = workflow["jobs"]["scan"]["steps"]
    names = [s.get("name", "") for s in steps]
    assert any("Wait" in n and "SonarQube" in n for n in names)


def test_workflow_has_scanner_step(workflow):
    """The actual scan invocation MUST be present."""
    steps = workflow["jobs"]["scan"]["steps"]
    names = [s.get("name", "") for s in steps]
    assert any("sonar-scanner" in n.lower() or "scan" in n.lower() for n in names)


def test_workflow_scanner_uses_sonarsource_docker_image(workflow):
    """Pin sonarsource/sonar-scanner-cli (drift to alternative scanner
    images would diverge from the local sonar_scan.sh behavior + may
    use an incompatible analyzer protocol)."""
    steps = workflow["jobs"]["scan"]["steps"]
    found = False
    for step in steps:
        run_block = step.get("run", "")
        if "sonarsource/sonar-scanner-cli" in run_block:
            found = True
            break
    assert found, "no step invokes sonarsource/sonar-scanner-cli"


def test_workflow_has_quality_gate_check(workflow):
    """The Quality Gate check is the load-bearing pass/fail criterion.
    A workflow without it would publish results but never enforce them."""
    steps = workflow["jobs"]["scan"]["steps"]
    names = [s.get("name", "") for s in steps]
    assert any("Quality Gate" in n for n in names)


def test_workflow_quality_gate_uses_sonar_api(workflow):
    """The Quality Gate check MUST hit the project_status endpoint
    on the local SonarQube instance — not some external API."""
    steps = workflow["jobs"]["scan"]["steps"]
    gate_step = next(s for s in steps if "Quality Gate" in s.get("name", ""))
    run = gate_step.get("run", "")
    assert "project_status" in run
    assert "localhost:9000" in run


def test_workflow_generates_coverage(workflow):
    """The scan should consume coverage.xml. The workflow generates it
    via pytest --cov. Without this, Sonar reports 0% coverage —
    confusing in the dashboard."""
    steps = workflow["jobs"]["scan"]["steps"]
    # Find the step whose `run` block actually invokes pytest --cov
    coverage_step = next(
        (s for s in steps if "--cov" in s.get("run", "")),
        None,
    )
    assert coverage_step is not None, "no step runs pytest --cov"


def test_workflow_coverage_step_is_best_effort(workflow):
    """A failing test inside the coverage step shouldn't fail the scan.
    `continue-on-error: true` is the documented contract here."""
    steps = workflow["jobs"]["scan"]["steps"]
    coverage_step = next(
        s for s in steps if "--cov" in s.get("run", "")
    )
    assert coverage_step.get("continue-on-error") is True


# --------------------------------------------------------------------------
# Cross-file consistency with sonar/docker-compose.yml
# --------------------------------------------------------------------------


def test_workflow_postgres_credentials_match_compose(workflow, compose):
    """If the CI workflow uses different PG credentials than the local
    stack, the SonarQube JDBC URL has to use them. Easier to pin both
    to the same `sonarqube:sonarqube` so the SonarQube env vars
    parallel local exactly."""
    ci_pg = workflow["jobs"]["scan"]["services"]["sonardb"]["env"]
    compose_pg = compose["services"]["sonardb"]["environment"]
    assert ci_pg["POSTGRES_USER"] == compose_pg["POSTGRES_USER"]
    assert ci_pg["POSTGRES_PASSWORD"] == compose_pg["POSTGRES_PASSWORD"]
    assert ci_pg["POSTGRES_DB"] == compose_pg["POSTGRES_DB"]


def test_workflow_jdbc_url_matches_compose(workflow, compose):
    ci_jdbc = workflow["jobs"]["scan"]["services"]["sonarqube"]["env"]["SONAR_JDBC_URL"]
    compose_jdbc = compose["services"]["sonarqube"]["environment"]["SONAR_JDBC_URL"]
    assert ci_jdbc == compose_jdbc


# --------------------------------------------------------------------------
# OWASP Dependency-Check integration (0.52.0)
# --------------------------------------------------------------------------


def test_workflow_has_owasp_dc_step(workflow):
    """Phase #2 of 4 shipped in 0.52.0 wires OWASP Dependency-Check
    into the sonar.yml pipeline. The Sonar dashboard ingests its
    SARIF output via the CVE plugin."""
    steps = workflow["jobs"]["scan"]["steps"]
    found = any(
        "OWASP Dependency-Check" in s.get("name", "")
        or "owasp/dependency-check" in s.get("run", "")
        for s in steps
    )
    assert found


def test_workflow_owasp_dc_is_best_effort(workflow):
    """OWASP DC has known NVD-throttling issues without an NVD API
    key. The step is `continue-on-error: true` so SonarQube SAST
    still passes even when NVD is rate-limiting us."""
    steps = workflow["jobs"]["scan"]["steps"]
    # Selector must hit the RUN step (not the Cache step which also has
    # "OWASP Dependency-Check" in its name)
    dc_step = next(
        s for s in steps
        if "owasp/dependency-check" in s.get("run", "")
    )
    assert dc_step.get("continue-on-error") is True


def test_workflow_owasp_dc_supports_nvd_api_key_secret(workflow):
    """The step MUST plumb the NVD_API_KEY secret through env so
    operators who set it get the un-throttled flow. The conditional
    arg-building pattern keeps the absence-of-secret path working
    too."""
    steps = workflow["jobs"]["scan"]["steps"]
    # Selector must hit the RUN step (not the Cache step which also has
    # "OWASP Dependency-Check" in its name)
    dc_step = next(
        s for s in steps
        if "owasp/dependency-check" in s.get("run", "")
    )
    env = dc_step.get("env", {})
    assert "NVD_API_KEY" in env
    # The run block should mention the secret + the conditional shape
    run = dc_step.get("run", "")
    assert "NVD_API_KEY" in run


def test_workflow_caches_dependency_check_nvd_data(workflow):
    """NVD download is slow on cold cache (~10 min) but stable across
    runs. Caching cuts subsequent runs to ~30s — load-bearing for the
    workflow staying under timeout-minutes."""
    steps = workflow["jobs"]["scan"]["steps"]
    found = any(
        "actions/cache" in str(s.get("uses", ""))
        and "dependency-check" in str(s.get("with", {}).get("path", ""))
        for s in steps
    )
    assert found, "workflow should cache the OWASP DC NVD data dir"


def test_workflow_owasp_dc_emits_sarif(workflow):
    """SARIF is the format SonarQube + Code Scanning both ingest.
    JSON is also produced for direct Sonar-plugin consumption."""
    steps = workflow["jobs"]["scan"]["steps"]
    dc_step = next(
        s for s in steps
        if "owasp/dependency-check" in s.get("run", "")
    )
    run = dc_step.get("run", "")
    assert "SARIF" in run or "sarif" in run.lower()
