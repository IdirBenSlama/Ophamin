"""Hardening pins for .github/workflows/trivy.yml (0.52.0 phase #2).

Trivy is the Software Composition Analysis (SCA) complement to
SonarQube's SAST — pairs container-image + filesystem scanning
against the public CVE database. The trivy.yml workflow runs:

- fs-scan job: scans repository (source-tree deps + IaC + Dockerfile)
- image-scan job: scans the PUBLISHED GHCR image at ghcr.io/.../ophamin:<tag>

Both emit SARIF reports + upload to GitHub Code Scanning (Security tab).

These tests validate workflow structure without running it.
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

REPO_ROOT = Path(__file__).parent.parent
WORKFLOW = REPO_ROOT / ".github" / "workflows" / "trivy.yml"


# --------------------------------------------------------------------------
# File-presence + parse
# --------------------------------------------------------------------------


def test_trivy_workflow_exists():
    assert WORKFLOW.is_file()


@pytest.fixture(scope="module")
def workflow() -> dict:
    return yaml.safe_load(WORKFLOW.read_text())


def test_workflow_name(workflow):
    assert workflow["name"] == "trivy"


# --------------------------------------------------------------------------
# Triggers — push + PR + schedule + dispatch
# --------------------------------------------------------------------------


def test_workflow_triggers_on_push_to_main(workflow):
    triggers = workflow.get("on", workflow.get(True, {}))
    assert "push" in triggers
    assert "main" in triggers["push"].get("branches", [])


def test_workflow_triggers_on_v_tag(workflow):
    triggers = workflow.get("on", workflow.get(True, {}))
    tags = triggers["push"].get("tags", [])
    assert any("v*" in t for t in tags)


def test_workflow_triggers_on_pull_request(workflow):
    triggers = workflow.get("on", workflow.get(True, {}))
    assert "pull_request" in triggers


def test_workflow_has_weekly_schedule(workflow):
    """Catches newly-disclosed CVEs against the previously-published
    image without requiring a new push."""
    triggers = workflow.get("on", workflow.get(True, {}))
    assert "schedule" in triggers
    schedules = triggers["schedule"]
    assert isinstance(schedules, list) and len(schedules) > 0
    # Cron should have 5 fields
    cron = schedules[0]["cron"]
    assert len(cron.split()) == 5


def test_workflow_has_workflow_dispatch(workflow):
    triggers = workflow.get("on", workflow.get(True, {}))
    assert "workflow_dispatch" in triggers


# --------------------------------------------------------------------------
# Permissions + concurrency
# --------------------------------------------------------------------------


def test_workflow_has_security_events_write_permission(workflow):
    """Required to upload SARIF to GitHub Code Scanning."""
    perms = workflow.get("permissions", {})
    assert perms.get("security-events") == "write"


def test_workflow_contents_read_only(workflow):
    perms = workflow.get("permissions", {})
    assert perms.get("contents") == "read"


def test_workflow_has_concurrency_group(workflow):
    concurrency = workflow.get("concurrency", {})
    assert "trivy-" in concurrency["group"]
    assert concurrency.get("cancel-in-progress") is True


# --------------------------------------------------------------------------
# Jobs — fs-scan + image-scan
# --------------------------------------------------------------------------


def test_workflow_has_fs_scan_job(workflow):
    assert "fs-scan" in workflow["jobs"]


def test_workflow_has_image_scan_job(workflow):
    assert "image-scan" in workflow["jobs"]


def test_image_scan_gated_on_push_or_schedule(workflow):
    """image-scan only runs after docker.yml has published — i.e.
    push to main or v* tag or scheduled/dispatched. PR scans skip
    image-scan because the PR's image isn't published yet."""
    img_job = workflow["jobs"]["image-scan"]
    if_cond = img_job.get("if", "")
    assert "push" in if_cond or "schedule" in if_cond or "workflow_dispatch" in if_cond


# --------------------------------------------------------------------------
# Trivy action pin + SARIF outputs
# --------------------------------------------------------------------------


def test_fs_scan_uses_aquasecurity_trivy_action(workflow):
    """Pin aquasecurity/trivy-action by version. Drift to :latest or
    an alternative fork would invalidate the hardening pins below."""
    steps = workflow["jobs"]["fs-scan"]["steps"]
    found = False
    for step in steps:
        uses = step.get("uses", "")
        if "aquasecurity/trivy-action" in uses:
            found = True
            # Version is pinned
            assert "@" in uses
            version = uses.split("@", 1)[1]
            assert version != "latest", "Don't pin to @latest — drift risk"
            assert version != "main", "Don't pin to @main — drift risk"
    assert found


def test_fs_scan_emits_sarif(workflow):
    """SARIF is the canonical format for GitHub Code Scanning ingest."""
    steps = workflow["jobs"]["fs-scan"]["steps"]
    trivy_step = next(s for s in steps if "trivy-action" in str(s.get("uses", "")))
    assert trivy_step["with"]["format"] == "sarif"
    assert trivy_step["with"].get("output", "").endswith(".sarif")


def test_fs_scan_severity_high_critical(workflow):
    """The severity gate is HIGH + CRITICAL — MEDIUM + LOW are
    advisory and surfaced in the dashboard but don't trigger CI noise."""
    steps = workflow["jobs"]["fs-scan"]["steps"]
    trivy_step = next(s for s in steps if "trivy-action" in str(s.get("uses", "")))
    severity = trivy_step["with"].get("severity", "")
    assert "HIGH" in severity
    assert "CRITICAL" in severity


def test_fs_scan_skip_dirs_excludes_caches(workflow):
    """Standard hygiene — skip .venv / caches / build artifacts /
    node_modules so they don't dominate the scan-time + noise."""
    steps = workflow["jobs"]["fs-scan"]["steps"]
    trivy_step = next(s for s in steps if "trivy-action" in str(s.get("uses", "")))
    skip = trivy_step["with"].get("skip-dirs", "")
    for noise in ("venv", ".mypy_cache", ".ruff_cache", "node_modules"):
        assert noise in skip


def test_fs_scan_uploads_sarif_to_code_scanning(workflow):
    """SARIF upload via github/codeql-action/upload-sarif is what
    populates the Security tab."""
    steps = workflow["jobs"]["fs-scan"]["steps"]
    found = any(
        "codeql-action/upload-sarif" in str(s.get("uses", ""))
        for s in steps
    )
    assert found


def test_fs_scan_uploads_with_always_condition(workflow):
    """Even on workflow failure we want SARIF in the Security tab —
    `if: always()` ensures the upload runs."""
    steps = workflow["jobs"]["fs-scan"]["steps"]
    upload_step = next(
        s for s in steps if "codeql-action/upload-sarif" in str(s.get("uses", ""))
    )
    assert upload_step.get("if") == "always()"


# --------------------------------------------------------------------------
# Image scan specifics
# --------------------------------------------------------------------------


def test_image_scan_uses_aquasecurity_trivy_action(workflow):
    steps = workflow["jobs"]["image-scan"]["steps"]
    found = any("aquasecurity/trivy-action" in str(s.get("uses", "")) for s in steps)
    assert found


def test_image_scan_targets_ghcr_image(workflow):
    """The image scan MUST target ghcr.io/<owner>/ophamin — drift to
    any other path is silently meaningless."""
    steps = workflow["jobs"]["image-scan"]["steps"]
    trivy_step = next(
        s for s in steps if "trivy-action" in str(s.get("uses", ""))
    )
    image_ref = trivy_step["with"]["image-ref"]
    assert "ghcr.io" in image_ref
    assert "ophamin" in image_ref


def test_image_scan_lowercases_owner_namespace(workflow):
    """Same lesson as docker.yml + chart.yml — github.repository_owner
    is mixed-case, OCI refs require lowercase."""
    steps = workflow["jobs"]["image-scan"]["steps"]
    found = False
    for step in steps:
        run = step.get("run", "")
        if "OWNER" in run and "${OWNER,," in run:
            found = True
            break
    assert found, "image-scan should lowercase owner namespace"


def test_image_scan_uploads_with_distinct_category(workflow):
    """The fs-scan + image-scan SARIF uploads MUST use different
    `category` values so the Security tab doesn't conflate them."""
    fs_steps = workflow["jobs"]["fs-scan"]["steps"]
    img_steps = workflow["jobs"]["image-scan"]["steps"]

    fs_upload = next(
        s for s in fs_steps if "codeql-action/upload-sarif" in str(s.get("uses", ""))
    )
    img_upload = next(
        s for s in img_steps if "codeql-action/upload-sarif" in str(s.get("uses", ""))
    )

    fs_cat = fs_upload["with"].get("category", "")
    img_cat = img_upload["with"].get("category", "")
    assert fs_cat != img_cat, "fs-scan + image-scan need distinct SARIF categories"
    assert "fs" in fs_cat.lower() or "filesystem" in fs_cat.lower()
    assert "image" in img_cat.lower()


# --------------------------------------------------------------------------
# Exit-code policy — warn-only in 0.52.0
# --------------------------------------------------------------------------


def test_both_scans_warn_only_in_0_52_0(workflow):
    """The Trivy action's exit-code: "0" means warn-only — findings
    appear in Security tab but the workflow doesn't fail. 0.52.0
    ships the integration; a future ship can flip to exit-code: "1"
    once operators have history to tune against."""
    for job in ("fs-scan", "image-scan"):
        steps = workflow["jobs"][job]["steps"]
        trivy_step = next(s for s in steps if "trivy-action" in str(s.get("uses", "")))
        exit_code = trivy_step["with"].get("exit-code", "1")
        assert exit_code == "0", (
            f"{job}: warn-only mode required for 0.52.0 phase-1 ship"
        )
