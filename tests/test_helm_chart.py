"""Hardening pins for the Ophamin Helm chart.

These tests validate the chart's static structure WITHOUT requiring
the `helm` binary (not installed in CI / dev environments by default).
They catch:

- Chart.yaml + values.yaml YAML parse errors
- Drift between Chart.appVersion and the Ophamin package version
- Missing required template files
- Required keys in values.yaml that templates reference
- Image repository pin (the published GHCR image)

What these tests DON'T catch (out of scope without helm):

- Template rendering errors (would need `helm template`)
- Schema-level validation (would need `helm lint`)
- Cluster compatibility issues

A future ship could add a helm-lint job to CI for those, but the
structural pins below catch the most common drift modes.
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

CHART_DIR = Path(__file__).parent.parent / "charts" / "ophamin"


@pytest.fixture(scope="module")
def chart_yaml() -> dict:
    """Parse Chart.yaml once for all tests."""
    return yaml.safe_load((CHART_DIR / "Chart.yaml").read_text())


@pytest.fixture(scope="module")
def values_yaml() -> dict:
    """Parse values.yaml once for all tests."""
    return yaml.safe_load((CHART_DIR / "values.yaml").read_text())


# --------------------------------------------------------------------------
# Chart.yaml — metadata invariants
# --------------------------------------------------------------------------


def test_chart_yaml_exists():
    assert (CHART_DIR / "Chart.yaml").is_file()


def test_chart_api_version_is_v2(chart_yaml):
    """apiVersion v2 is Helm 3+ — v1 is deprecated."""
    assert chart_yaml["apiVersion"] == "v2"


def test_chart_name_matches_directory(chart_yaml):
    """The chart name in Chart.yaml MUST match its directory name —
    helm enforces this."""
    assert chart_yaml["name"] == CHART_DIR.name == "ophamin"


def test_chart_type_is_application(chart_yaml):
    """An application chart deploys a runtime workload; library
    charts are reusable templates only. Ophamin's chart is the former."""
    assert chart_yaml["type"] == "application"


def test_chart_version_is_semver(chart_yaml):
    """Chart version must be valid semver (Helm enforces this on
    push to OCI registries)."""
    import re
    assert re.match(r"^\d+\.\d+\.\d+", chart_yaml["version"])


def test_app_version_matches_ophamin_package(chart_yaml):
    """The chart's appVersion MUST track the most recent Ophamin
    release. Bumping Ophamin without bumping this drifts the chart's
    NOTES.txt + the image-tag-fallback behavior."""
    from ophamin import __version__ as ophamin_version
    assert chart_yaml["appVersion"] == ophamin_version, (
        f"Chart.yaml appVersion ({chart_yaml['appVersion']!r}) doesn't "
        f"match the installed Ophamin version ({ophamin_version!r}). "
        f"Update charts/ophamin/Chart.yaml appVersion when bumping "
        f"the Ophamin package."
    )


def test_chart_has_home_and_sources(chart_yaml):
    """Provenance — helm consumers can see where the chart comes from."""
    assert chart_yaml["home"].startswith("https://github.com/IdirBenSlama/Ophamin")
    assert any(
        s.startswith("https://github.com/IdirBenSlama/Ophamin")
        for s in chart_yaml["sources"]
    )


# --------------------------------------------------------------------------
# values.yaml — required structure
# --------------------------------------------------------------------------


def test_values_yaml_exists():
    assert (CHART_DIR / "values.yaml").is_file()


def test_values_has_image_section(values_yaml):
    img = values_yaml["image"]
    assert "repository" in img
    assert "pullPolicy" in img
    assert "tag" in img


def test_image_repository_is_ghcr_idirbenslama_ophamin(values_yaml):
    """The published image lives at this exact path. Drifting this
    breaks the GHCR pull path docker.yml produces."""
    assert values_yaml["image"]["repository"] == "ghcr.io/idirbenslama/ophamin"


def test_default_image_tag_is_empty_string(values_yaml):
    """An empty tag falls back to Chart.appVersion via the _helpers.tpl
    `ophamin.image` template. Defaulting to a specific tag (e.g. 'latest')
    would override appVersion and surprise users — the empty-string +
    fallback pattern is the canonical Helm idiom."""
    assert values_yaml["image"]["tag"] == ""


def test_http_default_enabled(values_yaml):
    """The HTTP REST surface is the primary use case; it's enabled by default."""
    assert values_yaml["http"]["enabled"] is True


def test_mcp_default_disabled(values_yaml):
    """The MCP surface needs the [mcp] extra installed; the published
    Dockerfile doesn't include it. Default-off prevents broken
    deployments on the published image."""
    assert values_yaml["mcp"]["enabled"] is False


def test_http_has_probes(values_yaml):
    """Both liveness and readiness probes must be defined — Helm
    won't lint without them, and K8s deployment is much less safe
    without them."""
    http = values_yaml["http"]
    assert "livenessProbe" in http
    assert "readinessProbe" in http
    # Both probes must point to /health
    assert http["livenessProbe"]["httpGet"]["path"] == "/health"
    assert http["readinessProbe"]["httpGet"]["path"] == "/health"


def test_http_probe_port_named_http(values_yaml):
    """The probe port name MUST match the containerPort name in the
    Deployment template ('http'). A drift would silently break probes
    (k8s would TCP-connect to nothing)."""
    http = values_yaml["http"]
    assert http["livenessProbe"]["httpGet"]["port"] == "http"
    assert http["readinessProbe"]["httpGet"]["port"] == "http"


def test_service_default_type_is_clusterip(values_yaml):
    """ClusterIP-only by default — safe for the common in-cluster
    use case. Operators opt in to NodePort / LoadBalancer / Ingress."""
    assert values_yaml["service"]["type"] == "ClusterIP"


def test_service_http_port_routing(values_yaml):
    """The Service exposes port 80 → container port 8000 (the Uvicorn
    default Ophamin's `http serve --port 8000` binds to)."""
    svc = values_yaml["service"]["http"]
    assert svc["port"] == 80
    assert svc["targetPort"] == 8000


def test_ingress_default_disabled(values_yaml):
    """Ingress is opt-in. Default deployment is internal-only."""
    assert values_yaml["ingress"]["enabled"] is False


def test_service_account_create_default_true(values_yaml):
    """Default to creating a dedicated SA — RBAC scoping works
    out-of-the-box. Operators can opt out via serviceAccount.create=false
    to use a pre-provisioned SA."""
    assert values_yaml["serviceAccount"]["create"] is True


def test_pod_security_context_runs_as_non_root(values_yaml):
    """The Dockerfile USER directive is `ophamin` (non-root). The chart
    pins this at the pod-spec level too — defense in depth."""
    assert values_yaml["podSecurityContext"]["runAsNonRoot"] is True


def test_security_context_disables_privilege_escalation(values_yaml):
    """allowPrivilegeEscalation: false is a baseline-pod-security-standard
    requirement. The chart must enforce it."""
    assert values_yaml["securityContext"]["allowPrivilegeEscalation"] is False


def test_security_context_drops_all_capabilities(values_yaml):
    """Drop ALL capabilities at container start — Ophamin needs none
    of them."""
    assert values_yaml["securityContext"]["capabilities"]["drop"] == ["ALL"]


def test_autoscaling_default_disabled(values_yaml):
    """HPA is opt-in. Default static-replica deployment is simpler."""
    assert values_yaml["autoscaling"]["enabled"] is False


def test_autoscaling_min_replicas_at_least_2(values_yaml):
    """When autoscaling IS enabled, the minimum should be ≥ 2 for
    availability during rolling updates."""
    assert values_yaml["autoscaling"]["minReplicas"] >= 2


def test_network_policy_default_disabled(values_yaml):
    """NetworkPolicy is opt-in — only needed on strict-default-deny
    clusters. Default-on would break in clusters without a NetPol
    controller."""
    assert values_yaml["networkPolicy"]["enabled"] is False


def test_network_policy_has_required_keys(values_yaml):
    """When enabled, NetworkPolicy needs policyTypes + ingress + egress."""
    np = values_yaml["networkPolicy"]
    assert "policyTypes" in np
    assert "ingress" in np
    assert "egress" in np


def test_network_policy_default_policy_types_is_ingress(values_yaml):
    """Default NetPol covers ingress (the most common requirement);
    egress can be added explicitly for stricter postures."""
    assert "Ingress" in values_yaml["networkPolicy"]["policyTypes"]


# --------------------------------------------------------------------------
# Template files — required presence
# --------------------------------------------------------------------------


@pytest.mark.parametrize("template_file", [
    "_helpers.tpl",
    "serviceaccount.yaml",
    "deployment-http.yaml",
    "service-http.yaml",
    "deployment-mcp.yaml",
    "service-mcp.yaml",
    "ingress.yaml",
    "hpa.yaml",
    "networkpolicy.yaml",
    "NOTES.txt",
    "tests/test-http-health.yaml",
])
def test_required_template_file_exists(template_file):
    path = CHART_DIR / "templates" / template_file
    assert path.is_file(), f"Required template file missing: {template_file}"


def test_helmignore_exists():
    """The .helmignore file controls what doesn't get packaged.
    Without it, helm bundles editor swap files / .DS_Store / etc."""
    assert (CHART_DIR / ".helmignore").is_file()


def test_readme_exists():
    """Chart README is what `helm show readme` surfaces — operator-facing docs."""
    assert (CHART_DIR / "README.md").is_file()


# --------------------------------------------------------------------------
# Template content invariants — catch the most common drift modes
# --------------------------------------------------------------------------


def test_deployment_http_uses_image_template(values_yaml):
    """The Deployment MUST reference the image via the _helpers.tpl
    `ophamin.image` template, not hard-code the image string. This
    ensures values.image.tag override works."""
    content = (CHART_DIR / "templates" / "deployment-http.yaml").read_text()
    assert "ophamin.image" in content


def test_deployment_http_uses_args_not_command():
    """ENTRYPOINT in the Dockerfile is `ophamin`. The Deployment must
    pass the subcommand + flags via `args:`, NOT override `command:`
    (which would bypass the ENTRYPOINT and break)."""
    content = (CHART_DIR / "templates" / "deployment-http.yaml").read_text()
    assert "args:" in content
    # command override would silently break — pin its absence
    # (allowing it in a comment is fine; the actual key must not appear)
    lines = content.split("\n")
    for line in lines:
        stripped = line.strip()
        if stripped.startswith("command:"):
            pytest.fail(
                f"deployment-http.yaml has a 'command:' override at "
                f"line: {line!r}. Use args: instead — the Dockerfile's "
                f"ENTRYPOINT is `ophamin` and overriding command bypasses it."
            )


def test_deployment_http_binds_0_0_0_0():
    """`ophamin http serve --host 0.0.0.0` is required for K8s — binding
    to 127.0.0.1 (the dev default) makes the pod unreachable from outside."""
    content = (CHART_DIR / "templates" / "deployment-http.yaml").read_text()
    assert "0.0.0.0" in content


def test_deployment_http_exposes_port_8000():
    """containerPort 8000 must match the Service's targetPort + the
    `--port 8000` arg."""
    content = (CHART_DIR / "templates" / "deployment-http.yaml").read_text()
    assert "containerPort: 8000" in content


def test_service_http_targets_container_port_via_values():
    """Service.targetPort MUST come from values, not hardcoded —
    operators changing the container port should change one place."""
    content = (CHART_DIR / "templates" / "service-http.yaml").read_text()
    assert ".Values.service.http.targetPort" in content


def test_deployment_mcp_uses_streamable_http_default(values_yaml):
    """K8s networking model fits streamable-http; stdio doesn't. The
    default value MUST be streamable-http."""
    assert values_yaml["mcp"]["transport"] == "streamable-http"


def test_helpers_define_required_templates():
    """The _helpers.tpl must define every helper template the other
    files reference. A missing definition would surface only at
    `helm install` time."""
    content = (CHART_DIR / "templates" / "_helpers.tpl").read_text()
    required = [
        'define "ophamin.name"',
        'define "ophamin.fullname"',
        'define "ophamin.chart"',
        'define "ophamin.labels"',
        'define "ophamin.selectorLabels"',
        'define "ophamin.httpSelectorLabels"',
        'define "ophamin.mcpSelectorLabels"',
        'define "ophamin.serviceAccountName"',
        'define "ophamin.image"',
    ]
    for needed in required:
        assert needed in content, f"_helpers.tpl missing: {needed}"


def test_labels_template_includes_chart_version():
    """The labels helper MUST include helm.sh/chart label per Helm
    best practice — this is how `helm upgrade` reconciles resources."""
    content = (CHART_DIR / "templates" / "_helpers.tpl").read_text()
    assert "helm.sh/chart" in content


# --------------------------------------------------------------------------
# Cross-file consistency
# --------------------------------------------------------------------------


def test_deployment_and_service_use_same_selector(values_yaml):
    """Deployment.spec.selector MUST match Service.spec.selector, or
    the Service routes to no Pods. Both templates use
    `ophamin.httpSelectorLabels` — pin that they don't drift."""
    deployment = (CHART_DIR / "templates" / "deployment-http.yaml").read_text()
    service = (CHART_DIR / "templates" / "service-http.yaml").read_text()
    assert "ophamin.httpSelectorLabels" in deployment
    assert "ophamin.httpSelectorLabels" in service


def test_mcp_deployment_and_service_use_same_selector():
    """Same invariant for the optional MCP Deployment + Service."""
    deployment = (CHART_DIR / "templates" / "deployment-mcp.yaml").read_text()
    service = (CHART_DIR / "templates" / "service-mcp.yaml").read_text()
    assert "ophamin.mcpSelectorLabels" in deployment
    assert "ophamin.mcpSelectorLabels" in service


def test_http_and_mcp_have_distinct_selectors():
    """HTTP and MCP Pods must be selectable separately — otherwise
    Service.http would route to MCP pods too."""
    helpers = (CHART_DIR / "templates" / "_helpers.tpl").read_text()
    assert 'app.kubernetes.io/component: http-serve' in helpers
    assert 'app.kubernetes.io/component: mcp-serve' in helpers


# --------------------------------------------------------------------------
# helm-test hook (templates/tests/)
# --------------------------------------------------------------------------


def test_helm_test_hook_has_test_annotation():
    """The Pod under templates/tests/ MUST carry helm.sh/hook: test,
    or `helm test` won't execute it."""
    content = (CHART_DIR / "templates" / "tests" / "test-http-health.yaml").read_text()
    assert '"helm.sh/hook": test' in content


def test_helm_test_hook_has_delete_policy():
    """hook-delete-policy keeps the test Pod from lingering as a
    completed-then-orphaned object after the test."""
    content = (CHART_DIR / "templates" / "tests" / "test-http-health.yaml").read_text()
    assert "helm.sh/hook-delete-policy" in content
    assert "hook-succeeded" in content


def test_helm_test_hook_targets_http_service():
    """The test Pod's curl URL MUST point at the HTTP Service the chart
    creates (templated via ophamin.fullname). Hardcoding a hostname
    would break for any non-default release name."""
    content = (CHART_DIR / "templates" / "tests" / "test-http-health.yaml").read_text()
    assert 'ophamin.fullname' in content
    assert "/health" in content


def test_helm_test_hook_only_runs_when_http_enabled():
    """If http.enabled is false (rare; would be MCP-only deployments),
    the test Pod isn't useful and shouldn't be rendered."""
    content = (CHART_DIR / "templates" / "tests" / "test-http-health.yaml").read_text()
    assert content.lstrip().startswith("{{- if .Values.http.enabled")


def test_helm_test_hook_image_is_pinned():
    """Pinning the curl image by exact tag/digest is reproducibility
    hygiene — drift could change the curl flags' behavior."""
    content = (CHART_DIR / "templates" / "tests" / "test-http-health.yaml").read_text()
    # Some explicit tag (NOT :latest)
    assert "curlimages/curl:" in content
    assert "curlimages/curl:latest" not in content


# --------------------------------------------------------------------------
# NetworkPolicy template (opt-in)
# --------------------------------------------------------------------------


def test_network_policy_only_renders_when_enabled():
    """The NetworkPolicy template is gated on networkPolicy.enabled —
    consumers without strict-default-deny don't pay for the resource."""
    content = (CHART_DIR / "templates" / "networkpolicy.yaml").read_text()
    assert content.lstrip().startswith("{{- if .Values.networkPolicy.enabled")


def test_network_policy_targets_chart_pods():
    """The NetPol's podSelector MUST match the chart's selector labels —
    a drift would either apply to the wrong pods (security violation)
    or leave the chart's pods unprotected."""
    content = (CHART_DIR / "templates" / "networkpolicy.yaml").read_text()
    assert "ophamin.selectorLabels" in content


def test_network_policy_uses_networking_k8s_io():
    """The right apiVersion for NetworkPolicy is networking.k8s.io/v1
    (NOT extensions/v1beta1 — long-deprecated)."""
    content = (CHART_DIR / "templates" / "networkpolicy.yaml").read_text()
    assert "apiVersion: networking.k8s.io/v1" in content
