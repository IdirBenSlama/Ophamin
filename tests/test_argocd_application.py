"""Hardening pins for argocd/ophamin-application.yaml (0.54.0 phase #4).

The ArgoCD Application manifest closes the CI → GitOps loop:
docker.yml + chart.yml + sonar.yml + trivy.yml pass → ArgoCD pulls
the signed Helm chart from GHCR → deploys to a K8s cluster.

These tests validate the manifest's static shape without requiring
ArgoCD or a K8s cluster to be reachable.
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

REPO_ROOT = Path(__file__).parent.parent
ARGOCD_DIR = REPO_ROOT / "argocd"
APP_MANIFEST = ARGOCD_DIR / "ophamin-application.yaml"


# --------------------------------------------------------------------------
# File presence
# --------------------------------------------------------------------------


def test_argocd_directory_exists():
    assert ARGOCD_DIR.is_dir()


def test_application_manifest_exists():
    assert APP_MANIFEST.is_file()


def test_argocd_readme_exists():
    assert (ARGOCD_DIR / "README.md").is_file()


# --------------------------------------------------------------------------
# Manifest schema
# --------------------------------------------------------------------------


@pytest.fixture(scope="module")
def manifest() -> dict:
    return yaml.safe_load(APP_MANIFEST.read_text())


def test_manifest_uses_argocd_api_version(manifest):
    """The Application CRD is at argoproj.io/v1alpha1 (stable alpha
    that ArgoCD has shipped for years). Drift to a different group
    would break compatibility with installed ArgoCD."""
    assert manifest["apiVersion"] == "argoproj.io/v1alpha1"


def test_manifest_kind_is_application(manifest):
    assert manifest["kind"] == "Application"


def test_manifest_is_in_argocd_namespace(manifest):
    """ArgoCD reads Application resources from its OWN namespace
    by default (controlled by the controller's --application-namespaces
    flag). Drift to a different namespace silently breaks
    auto-detection."""
    assert manifest["metadata"]["namespace"] == "argocd"


def test_manifest_has_argocd_finalizer(manifest):
    """Without this finalizer, deleting the Application orphans
    the workload Pods in the cluster (no GC). Load-bearing for
    `argocd app delete` to actually clean up."""
    finalizers = manifest["metadata"].get("finalizers", [])
    assert "resources-finalizer.argocd.argoproj.io" in finalizers


def test_manifest_has_managed_by_label(manifest):
    """Standard K8s label — surfaces in kubectl get + dashboards."""
    labels = manifest["metadata"].get("labels", {})
    assert labels.get("app.kubernetes.io/managed-by") == "argocd"


# --------------------------------------------------------------------------
# Source — Helm chart on GHCR
# --------------------------------------------------------------------------


def test_source_points_at_ghcr_helm_chart(manifest):
    """The Application MUST pull from the GHCR chart published by
    chart.yml. Drift to a different repository silently breaks the
    supply-chain claim (the chart on the other path may not be
    cosign-signed)."""
    source = manifest["spec"]["source"]
    assert "ghcr.io/idirbenslama/ophamin" in source["repoURL"]
    assert source["chart"] == "ophamin"


def test_source_targetRevision_is_pinned(manifest):
    """Production Application targetRevision MUST be pinned to a
    specific chart version. Drift to `latest` or empty means
    every ArgoCD reconcile may roll the cluster to a different
    chart version."""
    target = manifest["spec"]["source"].get("targetRevision", "")
    assert target, "targetRevision must be set"
    assert target != "latest", "targetRevision should be a specific version, not latest"


def test_helm_release_name_is_ophamin(manifest):
    """release-name aligns with the chart's expected ophamin.fullname
    template behavior — without it, ArgoCD generates a random release
    name + the resources don't follow the documented `<release>-http`
    naming."""
    helm = manifest["spec"]["source"].get("helm", {})
    assert helm.get("releaseName") == "ophamin"


def test_helm_values_pins_image_tag(manifest):
    """Production deployments MUST pin the image tag explicitly.
    Without it, the chart falls back to Chart.appVersion which
    advances every release — every ArgoCD reconcile pulls a different
    image."""
    helm = manifest["spec"]["source"].get("helm", {})
    values_str = helm.get("values", "")
    assert "tag:" in values_str
    # And the tag is NOT just empty string
    import re
    match = re.search(r'tag:\s*"([^"]+)"', values_str)
    assert match, f"tag should be quoted + non-empty; values:\n{values_str}"
    assert match.group(1), "tag must be non-empty"


def test_helm_values_enables_pdb(manifest):
    """Production Application should enable Pod Disruption Budget
    (chart 0.47.0 feature). Without it, voluntary cluster disruptions
    can take all replicas down at once."""
    helm = manifest["spec"]["source"].get("helm", {})
    values_str = helm.get("values", "")
    assert "podDisruptionBudget:" in values_str
    assert "enabled: true" in values_str


# --------------------------------------------------------------------------
# Destination
# --------------------------------------------------------------------------


def test_destination_namespace_is_ophamin(manifest):
    """Production deployment goes into the `ophamin` namespace
    (not `default`). CreateNamespace=true sync option handles
    namespace creation."""
    dest = manifest["spec"]["destination"]
    assert dest["namespace"] == "ophamin"


def test_destination_uses_in_cluster_server(manifest):
    """Default destination is the in-cluster API server. Operators
    deploying cross-cluster override this via `argocd cluster add`
    + a different server URL."""
    dest = manifest["spec"]["destination"]
    assert "kubernetes.default.svc" in dest["server"]


# --------------------------------------------------------------------------
# Sync policy
# --------------------------------------------------------------------------


def test_sync_policy_is_automated(manifest):
    """Automated sync is the GitOps promise: git/registry is the
    source of truth + the cluster auto-reconciles. Without
    automated, every chart bump requires a manual `argocd app sync`."""
    sync = manifest["spec"].get("syncPolicy", {})
    assert "automated" in sync


def test_sync_policy_enables_prune(manifest):
    """prune: true removes resources that disappear from the chart.
    Without it, deletes accumulate as orphaned objects across
    chart-version bumps."""
    sync = manifest["spec"]["syncPolicy"]
    assert sync["automated"]["prune"] is True


def test_sync_policy_enables_self_heal(manifest):
    """self-heal: true rolls back drift in the cluster. Load-bearing
    for the "git is the source of truth" promise — without it,
    a `kubectl edit` can silently override ArgoCD-managed state."""
    sync = manifest["spec"]["syncPolicy"]
    assert sync["automated"]["selfHeal"] is True


def test_sync_policy_creates_namespace(manifest):
    """CreateNamespace=true lets the Application bootstrap the
    target namespace on first apply (no separate kubectl create ns
    step needed)."""
    sync = manifest["spec"]["syncPolicy"]
    options = sync.get("syncOptions", [])
    assert "CreateNamespace=true" in options


def test_sync_policy_has_retry_with_backoff(manifest):
    """Network blips + transient API-server errors are common.
    Exponential backoff with a finite retry count is the canonical
    resilience pattern."""
    sync = manifest["spec"]["syncPolicy"]
    retry = sync.get("retry", {})
    assert retry.get("limit", 0) >= 3
    backoff = retry.get("backoff", {})
    assert backoff.get("factor", 0) >= 2  # exponential


def test_revision_history_limit_set(manifest):
    """revisionHistoryLimit controls how many previous syncs are
    retained for `argocd app rollback`. Without it, history grows
    unbounded."""
    history = manifest["spec"].get("revisionHistoryLimit", 0)
    assert history >= 5


# --------------------------------------------------------------------------
# Cross-file consistency with the Helm chart
# --------------------------------------------------------------------------


def test_image_tag_in_values_matches_some_published_release(manifest):
    """The pinned image tag in the Application's helm.values MUST be
    a tag that the docker.yml workflow actually publishes (semver
    format like 0.54.0 or 0.x.y). Drift to a non-existent tag
    silently breaks the pull."""
    helm = manifest["spec"]["source"]["helm"]
    values_str = helm["values"]
    import re
    match = re.search(r'tag:\s*"([^"]+)"', values_str)
    tag = match.group(1)
    # Accept semver-ish: digits + dots; reject obvious junk
    assert re.match(r"^\d+\.\d+\.\d+", tag), (
        f"image tag should be semver; got {tag!r}"
    )


def test_chart_targetRevision_matches_chart_yaml_pin(manifest):
    """The Application's chart targetRevision (e.g. 0.1.0) should be
    semver-shaped — the chart.yml workflow publishes the chart's
    Chart.yaml `version` field, which is independent of Ophamin's
    appVersion. Drift here points at a non-existent chart on GHCR."""
    target = manifest["spec"]["source"]["targetRevision"]
    import re
    assert re.match(r"^\d+\.\d+\.\d+", target), (
        f"chart targetRevision should be semver; got {target!r}"
    )


# --------------------------------------------------------------------------
# README content
# --------------------------------------------------------------------------


def test_argocd_readme_documents_kubectl_apply():
    """The operator-facing quick-start MUST cover the `kubectl apply`
    path — alternative paths (`argocd app create`) are also
    documented but kubectl is the most universal."""
    content = (ARGOCD_DIR / "README.md").read_text()
    assert "kubectl apply" in content
    assert "ophamin-application.yaml" in content


def test_argocd_readme_links_to_supply_chain_doc():
    """policy-controller integration is the load-bearing
    production-hardening step. The README MUST cross-reference
    docs/SUPPLY_CHAIN.md for the full setup."""
    content = (ARGOCD_DIR / "README.md").read_text()
    assert "SUPPLY_CHAIN.md" in content


def test_argocd_readme_documents_policy_controller_integration():
    """Without the policy-controller link, operators don't know
    how to enforce signature + SBOM + SLSA at admission time —
    just verifying after-the-fact misses the value."""
    content = (ARGOCD_DIR / "README.md").read_text()
    assert "policy-controller" in content.lower()
    assert "ClusterImagePolicy" in content
