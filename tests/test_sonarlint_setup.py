"""Hardening pins for .sonarlint/ — local IDE guardrails (0.53.0 phase #3).

SonarQube for IDE (formerly SonarLint) reads .sonarlint/connectedMode.json
from the workspace root + auto-binds to the configured SonarQube instance.
These tests validate the binding file's static shape WITHOUT requiring an
IDE to be running.

The binding lives in JSON (not properties) per SonarSource's documented
connected-mode setup. Drift in any of the load-bearing keys
(`sonarQubeUri`, `projectKey`) silently breaks the auto-detection.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).parent.parent
SONARLINT_DIR = REPO_ROOT / ".sonarlint"


# --------------------------------------------------------------------------
# File presence
# --------------------------------------------------------------------------


def test_sonarlint_dir_exists():
    """The .sonarlint/ directory is the SonarSource-documented home
    for the binding file. Drift to a different path silently breaks
    auto-detection in IDEs."""
    assert SONARLINT_DIR.is_dir()


def test_connected_mode_json_exists():
    """`.sonarlint/connectedMode.json` is the canonical binding file.
    IDEs probe THIS exact filename — renaming would break the
    auto-detection chain."""
    assert (SONARLINT_DIR / "connectedMode.json").is_file()


def test_sonarlint_readme_exists():
    """README explains why the binding exists + how to enable it
    in each supported IDE. Without it, operators see the
    .sonarlint/ directory + don't know what to do with it."""
    assert (SONARLINT_DIR / "README.md").is_file()


# --------------------------------------------------------------------------
# connectedMode.json content
# --------------------------------------------------------------------------


@pytest.fixture(scope="module")
def binding() -> dict:
    return json.loads((SONARLINT_DIR / "connectedMode.json").read_text())


def test_binding_has_schema_reference(binding):
    """The $schema field points at SonarSource's published JSON Schema
    for the binding file — IDEs (and editors with JSON-schema support)
    use it for autocomplete + validation."""
    schema = binding.get("$schema", "")
    assert "sonarsource.com" in schema
    assert "connectedMode" in schema


def test_binding_project_key_is_ophamin(binding):
    """The projectKey MUST match what `sonar.projectKey` is in
    the workflow's generated sonar-project.properties. Drift here
    means IDE finds the wrong project on the server (or none) and
    silently falls back to standalone mode."""
    assert binding["projectKey"] == "ophamin"


def test_binding_targets_local_sonarqube(binding):
    """Default binding points at the bundled local stack
    (`sonar/docker-compose.yml` exposes port 9000). Operators
    using a remote SonarQube override via IDE connection
    settings — but the in-tree default is the local instance."""
    uri = binding.get("sonarQubeUri", "")
    assert "localhost:9000" in uri or "127.0.0.1:9000" in uri


def test_binding_uri_is_http_not_https_for_local(binding):
    """The local sonar/docker-compose.yml ships SonarQube on HTTP
    (no TLS termination). HTTPS binding would silently fail to
    connect against the local stack."""
    uri = binding.get("sonarQubeUri", "")
    assert uri.startswith("http://"), (
        f"local binding should use http://; got {uri!r}"
    )


def test_binding_does_not_carry_credentials(binding):
    """Tokens / passwords MUST NOT be committed. The IDE prompts
    operators for a token on first connection + stores it locally
    via the IDE's credential manager."""
    # Common credential field names
    forbidden = {"token", "password", "secret", "apiKey", "api_key", "credentials"}
    for key in binding.keys():
        assert key.lower() not in {f.lower() for f in forbidden}, (
            f"binding MUST NOT carry credentials; found suspicious key: {key!r}"
        )


def test_binding_project_key_matches_sonar_project_properties():
    """The IDE binding's projectKey + the CI scanner's sonar.projectKey
    MUST match — otherwise issues recorded in the server (via the CI
    scan) wouldn't surface in the IDE."""
    # Read the CI workflow's properties template generation
    workflow_yml = (REPO_ROOT / ".github" / "workflows" / "sonar.yml").read_text()
    # The generated properties file in sonar.yml uses
    # `sonar.projectKey=ophamin`
    assert "sonar.projectKey=ophamin" in workflow_yml


# --------------------------------------------------------------------------
# Cross-file consistency with docker-compose
# --------------------------------------------------------------------------


def test_binding_uri_matches_local_compose_port(binding):
    """The local compose file publishes SonarQube on port 9000
    (sonar/docker-compose.yml). The binding URI must hit that
    same port."""
    compose = (REPO_ROOT / "sonar" / "docker-compose.yml").read_text()
    # Verify the local compose publishes 9000:9000
    assert "9000:9000" in compose, (
        "sonar/docker-compose.yml should publish port 9000:9000"
    )
    # And the binding URI uses 9000 too
    assert "9000" in binding["sonarQubeUri"]


# --------------------------------------------------------------------------
# README content
# --------------------------------------------------------------------------


def test_sonarlint_readme_mentions_connected_mode():
    """The README MUST explain the standalone-vs-connected
    distinction — operators new to SonarLint don't know why
    connected mode matters without it."""
    content = (SONARLINT_DIR / "README.md").read_text()
    assert "connected" in content.lower()
    assert "standalone" in content.lower()


def test_sonarlint_readme_lists_supported_ides():
    """The README should list at least: VS Code, IntelliJ, Eclipse.
    Operators don't know which extension to install without this."""
    content = (SONARLINT_DIR / "README.md").read_text()
    assert "VS Code" in content or "vscode" in content.lower()
    assert "IntelliJ" in content
    assert "Eclipse" in content


def test_sonarlint_readme_documents_quick_start():
    """4-step quick-start (bring up SQ + install extension + open
    repo + generate token) MUST be present — it's the load-bearing
    operator-facing content."""
    content = (SONARLINT_DIR / "README.md").read_text()
    assert "sonar_up.sh" in content
    assert "token" in content.lower() or "account/security" in content


def test_sonarlint_readme_in_repo_root_links():
    """The README cross-references docs/SONARQUBE.md + sonar/docker-compose.yml.
    Drift in those filenames would break the docs."""
    content = (SONARLINT_DIR / "README.md").read_text()
    assert "SONARQUBE.md" in content
    assert "docker-compose.yml" in content
