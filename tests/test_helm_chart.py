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
    "pdb-http.yaml",
    "pdb-mcp.yaml",
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


# --------------------------------------------------------------------------
# Pod Disruption Budget (PDB) — opt-in via podDisruptionBudget.enabled
# --------------------------------------------------------------------------


def test_pdb_default_disabled(values_yaml):
    """PDB is opt-in. Single-replica deployments don't benefit from it
    (and would break under voluntary disruption), so default-off is
    the safe baseline."""
    assert values_yaml["podDisruptionBudget"]["enabled"] is False


def test_pdb_has_separate_http_and_mcp_blocks(values_yaml):
    """HTTP and MCP get separate PDB resources so operators can set
    different constraints per Deployment."""
    pdb = values_yaml["podDisruptionBudget"]
    assert "http" in pdb
    assert "mcp" in pdb


def test_pdb_per_deployment_has_minAvailable_and_maxUnavailable_keys(values_yaml):
    """Both keys present per Deployment — operators set ONE, leave the
    other empty. Kubernetes refuses PDBs with both set; the chart
    enforces this at template time via `fail`."""
    for component in ("http", "mcp"):
        block = values_yaml["podDisruptionBudget"][component]
        assert "minAvailable" in block
        assert "maxUnavailable" in block


def test_pdb_http_template_only_renders_when_pdb_enabled_AND_http_enabled():
    """Both gates must be satisfied — a PDB for a non-existent
    Deployment is dead code."""
    content = (CHART_DIR / "templates" / "pdb-http.yaml").read_text()
    assert "podDisruptionBudget.enabled" in content
    assert "http.enabled" in content


def test_pdb_mcp_template_only_renders_when_pdb_enabled_AND_mcp_enabled():
    content = (CHART_DIR / "templates" / "pdb-mcp.yaml").read_text()
    assert "podDisruptionBudget.enabled" in content
    assert "mcp.enabled" in content


def test_pdb_uses_policy_v1_apiVersion():
    """The right apiVersion is policy/v1 (NOT policy/v1beta1 —
    deprecated in K8s 1.21, removed in K8s 1.25). The chart targets
    modern clusters."""
    for tpl in ("pdb-http.yaml", "pdb-mcp.yaml"):
        content = (CHART_DIR / "templates" / tpl).read_text()
        assert "apiVersion: policy/v1" in content
        assert "apiVersion: policy/v1beta1" not in content


def test_pdb_http_targets_http_pods_via_selector():
    """The PDB selector MUST match the HTTP Deployment's pod selector
    so the constraint binds to the right pods."""
    content = (CHART_DIR / "templates" / "pdb-http.yaml").read_text()
    assert "ophamin.httpSelectorLabels" in content


def test_pdb_mcp_targets_mcp_pods_via_selector():
    content = (CHART_DIR / "templates" / "pdb-mcp.yaml").read_text()
    assert "ophamin.mcpSelectorLabels" in content


def test_pdb_template_enforces_xor_via_fail():
    """If operator accidentally sets BOTH minAvailable and maxUnavailable,
    helm should fail at template time with a clear message — not
    produce an invalid PDB resource that the apiserver rejects."""
    for tpl in ("pdb-http.yaml", "pdb-mcp.yaml"):
        content = (CHART_DIR / "templates" / tpl).read_text()
        assert "fail" in content
        # The fail message should mention the constraint
        assert "minAvailable or maxUnavailable" in content


def test_pdb_template_defaults_to_min_available_1():
    """When neither is set but PDB is enabled, the safe default is
    minAvailable: 1 — at least one pod stays up during disruptions."""
    for tpl in ("pdb-http.yaml", "pdb-mcp.yaml"):
        content = (CHART_DIR / "templates" / tpl).read_text()
        assert "minAvailable: 1" in content


# --------------------------------------------------------------------------
# 0.57.0 — Monitoring (ServiceMonitor + PodMonitor) + workload identity +
# MCP helm-test
# --------------------------------------------------------------------------


def test_values_carries_monitoring_block(values_yaml):
    """Values must declare the monitoring block so chart-consumers can
    discover the flags via `helm show values`."""
    mon = values_yaml.get("monitoring")
    assert isinstance(mon, dict), "monitoring block missing"
    for key in ("scrapePath", "scrapeInterval", "scrapeTimeout"):
        assert key in mon, f"monitoring.{key} missing"
    for sub in ("serviceMonitor", "podMonitor"):
        block = mon.get(sub)
        assert isinstance(block, dict), f"monitoring.{sub} block missing"
        assert block["enabled"] is False, (
            f"monitoring.{sub}.enabled MUST default to False"
        )
        assert "additionalLabels" in block
        assert "namespace" in block
        assert "relabelings" in block
        assert "metricRelabelings" in block


def test_values_monitoring_defaults_to_metrics_path_and_30s():
    """Default scrape path /metrics + 30s interval / 10s timeout match
    the FastAPI endpoint added in 0.57.0."""
    values = yaml.safe_load((CHART_DIR / "values.yaml").read_text())
    mon = values["monitoring"]
    assert mon["scrapePath"] == "/metrics"
    assert mon["scrapeInterval"] == "30s"
    assert mon["scrapeTimeout"] == "10s"


def test_servicemonitor_template_exists():
    assert (CHART_DIR / "templates" / "servicemonitor.yaml").is_file()


def test_podmonitor_template_exists():
    assert (CHART_DIR / "templates" / "podmonitor.yaml").is_file()


def test_servicemonitor_template_gated_by_http_AND_serviceMonitor_enabled():
    content = (CHART_DIR / "templates" / "servicemonitor.yaml").read_text()
    assert "http.enabled" in content
    assert "monitoring.serviceMonitor.enabled" in content
    # The gate is an `and` so neither half on its own renders the CRD
    assert "if and" in content


def test_podmonitor_template_gated_by_http_AND_podMonitor_enabled():
    content = (CHART_DIR / "templates" / "podmonitor.yaml").read_text()
    assert "http.enabled" in content
    assert "monitoring.podMonitor.enabled" in content
    assert "if and" in content


def test_servicemonitor_uses_prometheus_operator_apiVersion():
    content = (CHART_DIR / "templates" / "servicemonitor.yaml").read_text()
    assert "apiVersion: monitoring.coreos.com/v1" in content
    assert "kind: ServiceMonitor" in content


def test_podmonitor_uses_prometheus_operator_apiVersion():
    content = (CHART_DIR / "templates" / "podmonitor.yaml").read_text()
    assert "apiVersion: monitoring.coreos.com/v1" in content
    assert "kind: PodMonitor" in content


def test_servicemonitor_targets_http_pods_via_selector():
    content = (CHART_DIR / "templates" / "servicemonitor.yaml").read_text()
    assert "ophamin.httpSelectorLabels" in content


def test_podmonitor_targets_http_pods_via_selector():
    content = (CHART_DIR / "templates" / "podmonitor.yaml").read_text()
    assert "ophamin.httpSelectorLabels" in content


def test_servicemonitor_uses_named_http_port():
    """Port reference must match the Service's named 'http' port —
    not a number, so chart-internal port renumbering doesn't break the
    monitor binding."""
    content = (CHART_DIR / "templates" / "servicemonitor.yaml").read_text()
    assert "port: http" in content


def test_podmonitor_uses_named_http_port():
    content = (CHART_DIR / "templates" / "podmonitor.yaml").read_text()
    assert "port: http" in content


def test_values_carries_workloadIdentity_block(values_yaml):
    wi = values_yaml.get("workloadIdentity")
    assert isinstance(wi, dict)
    for cloud in ("gke", "eks", "aks"):
        block = wi.get(cloud)
        assert isinstance(block, dict)
        assert block["enabled"] is False


def test_helpers_carries_workload_identity_logic():
    """The serviceAccount.annotations helper must implement the
    mutually-exclusive cloud check + the per-cloud annotation key
    mapping."""
    content = (CHART_DIR / "templates" / "_helpers.tpl").read_text()
    assert 'define "ophamin.serviceAccount.annotations"' in content
    assert "iam.gke.io/gcp-service-account" in content
    assert "eks.amazonaws.com/role-arn" in content
    assert "azure.workload.identity/client-id" in content
    # mutually-exclusive guard
    assert "only one of gke / eks / aks" in content


def test_helpers_carries_aks_pod_label_helper():
    """AKS additionally requires `azure.workload.identity/use=true` as a
    Pod label; the helper signals when to inject it."""
    content = (CHART_DIR / "templates" / "_helpers.tpl").read_text()
    assert 'define "ophamin.aksPodLabelEnabled"' in content


def test_serviceaccount_template_uses_new_annotations_helper():
    """The SA template must call the new helper rather than the
    old static toYaml of .Values.serviceAccount.annotations — otherwise
    workload-identity annotations don't reach the SA."""
    content = (CHART_DIR / "templates" / "serviceaccount.yaml").read_text()
    assert 'include "ophamin.serviceAccount.annotations"' in content


def test_deployment_http_injects_aks_pod_label_when_enabled():
    content = (CHART_DIR / "templates" / "deployment-http.yaml").read_text()
    assert "ophamin.aksPodLabelEnabled" in content
    assert "azure.workload.identity/use" in content


def test_deployment_mcp_injects_aks_pod_label_when_enabled():
    content = (CHART_DIR / "templates" / "deployment-mcp.yaml").read_text()
    assert "ophamin.aksPodLabelEnabled" in content
    assert "azure.workload.identity/use" in content


def test_mcp_helm_test_template_exists():
    assert (CHART_DIR / "templates" / "tests" / "test-mcp-tcp.yaml").is_file()


def test_mcp_helm_test_gated_by_mcp_enabled():
    content = (CHART_DIR / "templates" / "tests" / "test-mcp-tcp.yaml").read_text()
    assert "mcp.enabled" in content
    assert 'helm.sh/hook": test' in content


def test_mcp_helm_test_uses_busybox_nc_probe():
    """The MCP test probes TCP connectivity (the minimum viable signal)
    — full handshake would require a richer client."""
    content = (CHART_DIR / "templates" / "tests" / "test-mcp-tcp.yaml").read_text()
    assert "busybox" in content
    assert "nc -z" in content


def test_quality_gate_json_exists_and_parses():
    """The pre-baked quality gate must ship in the repo at the path
    docs/SONARQUBE.md will reference."""
    import json
    path = CHART_DIR.parent.parent / "sonar" / "kimera-swm-quality-gate.json"
    assert path.is_file(), f"missing quality-gate spec at {path}"
    data = json.loads(path.read_text())
    assert data["name"] == "Kimera-SWM Gate"
    assert isinstance(data["conditions"], list)
    assert len(data["conditions"]) >= 5
    for cond in data["conditions"]:
        assert "metric" in cond and "op" in cond and "error" in cond


def test_quality_gate_carries_new_code_conditions():
    """Per the Clean-as-You-Code shape, the gate's primary axis is on
    NEW-code metrics — verify they're present."""
    import json
    path = CHART_DIR.parent.parent / "sonar" / "kimera-swm-quality-gate.json"
    data = json.loads(path.read_text())
    metrics = {c["metric"] for c in data["conditions"]}
    for new_metric in ("new_bugs", "new_vulnerabilities",
                       "new_duplicated_lines_density"):
        assert new_metric in metrics, f"missing {new_metric} in gate"


def test_quality_gate_apply_script_exists_and_executable():
    """The apply-script must ship + be executable so the operator
    can run it directly without chmod."""
    import os, stat
    path = CHART_DIR.parent.parent / "scripts" / "sonar_apply_quality_gate.sh"
    assert path.is_file(), f"missing apply script at {path}"
    mode = path.stat().st_mode
    assert mode & stat.S_IXUSR, "apply script not executable"


def test_quality_gate_apply_script_is_idempotent():
    """The apply script must handle 'gate already exists' as a no-op
    (idempotent re-apply) — checked by looking for the existing-name
    early-out, AND for the delete-condition loop that rewrites the
    spec on every run."""
    path = CHART_DIR.parent.parent / "scripts" / "sonar_apply_quality_gate.sh"
    content = path.read_text()
    assert "qualitygates/list" in content
    assert "delete_condition" in content
    assert "create_condition" in content
    assert "qualitygates/select" in content  # binds to project
