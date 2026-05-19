# Ophamin Helm chart

> Deploys `ophamin http serve` (FastAPI REST surface) and, optionally,
> `ophamin mcp serve` (Model Context Protocol surface) on Kubernetes.
> The image is the multi-arch `ghcr.io/idirbenslama/ophamin` published
> by the project's `docker.yml` GitHub Actions workflow.

## Installing

```bash
helm install my-ophamin oci://ghcr.io/idirbenslama/ophamin \
    --version 0.1.0 \
    --namespace ophamin \
    --create-namespace
```

Override the Ophamin image tag explicitly:

```bash
helm install my-ophamin oci://ghcr.io/idirbenslama/ophamin \
    --version 0.1.0 \
    --set image.tag=0.40.0 \
    --namespace ophamin \
    --create-namespace
```

Override defaults via a values file:

```bash
helm install my-ophamin oci://ghcr.io/idirbenslama/ophamin \
    --version 0.1.0 \
    -f my-values.yaml \
    --namespace ophamin
```

## What gets deployed

By default:

| Resource | Name | Purpose |
|---|---|---|
| Deployment | `<release>-http` | 2 replicas of `ophamin http serve` on port 8000 |
| Service | `<release>-http` | ClusterIP exposing port 80 → 8000 |
| ServiceAccount | `<release>` | The pods' identity |

Optional resources (opt-in via values.yaml):

| Resource | Toggle | Purpose |
|---|---|---|
| Deployment + Service | `mcp.enabled=true` | `ophamin mcp serve` (streamable-http) on port 8765 |
| Ingress | `ingress.enabled=true` | External access via cluster's Ingress controller |
| HorizontalPodAutoscaler | `autoscaling.enabled=true` | CPU/memory-based scaling for the HTTP Deployment |
| NetworkPolicy | `networkPolicy.enabled=true` | Required for strict-default-deny clusters; supply explicit ingress / egress rules in values for production |
| PodDisruptionBudget | `podDisruptionBudget.enabled=true` | Protects HTTP / MCP Pods from voluntary disruptions (node drains, upgrades, cluster-autoscaler scale-down). Separate PDB per Deployment; set `minAvailable` OR `maxUnavailable` per component, not both |
| `helm test` Pod | always (via `templates/tests/`) | Post-install health check — invoke with `helm test <release>` to curl `/health` against the deployed Service |

## Probes

The HTTP Deployment uses Ophamin's `/health` endpoint for both
liveness and readiness. The MCP Deployment uses TCP-socket probes
(MCP has no `/health` endpoint per se).

## Resources

Defaults are sized for moderate workloads:

```yaml
resources:
  requests:
    cpu: 100m
    memory: 256Mi
  limits:
    cpu: 2000m
    memory: 2Gi
```

The HTTP surface is mostly I/O-bound (verify_proof / read_proof_index);
`run_scenario` delegates to scenario code which has its own resource
needs. Tune via `--set http.resources.limits.memory=4Gi` for
larger workloads.

## Security context

Runs as the non-root `ophamin` user (per the Dockerfile's `USER`
directive). `allowPrivilegeEscalation: false` + `capabilities.drop: [ALL]`
are set by default. `readOnlyRootFilesystem` is left **false** because
Ophamin's CLI surface writes proof / audit files to local working
directories. Set it to `true` if you mount writable volumes explicitly.

## Prometheus Operator integration (0.57.0+)

The chart ships ServiceMonitor + PodMonitor templates for the
Prometheus Operator CRDs (`monitoring.coreos.com/v1`). Both are
default-OFF; enable on clusters where the operator's CRDs are
installed.

```yaml
monitoring:
  serviceMonitor:
    enabled: true
    additionalLabels:
      release: kube-prometheus-stack   # whatever the operator selects on
  # OR (or both)
  podMonitor:
    enabled: true
```

Both scrape `/metrics` on the chart's named `http` port. The
endpoint surfaces `ophamin_build_info` (version + server-name
labels) and `ophamin_scenarios_registered` (count of scenarios in
the registry). Default scrape interval 30s / timeout 10s — tune
under `monitoring.scrapeInterval` / `monitoring.scrapeTimeout`.

## Cloud-managed workload identity (0.57.0+)

For GKE / EKS / AKS deployments, enable the matching block under
`workloadIdentity.*` to get the per-cloud SA annotation +
(AKS only) the `azure.workload.identity/use=true` Pod label
auto-injected:

```yaml
# GKE
workloadIdentity:
  gke:
    enabled: true
    gcpServiceAccount: "ophamin@my-project.iam.gserviceaccount.com"

# EKS
workloadIdentity:
  eks:
    enabled: true
    roleArn: "arn:aws:iam::123456789012:role/OphaminEksWorkload"

# AKS
workloadIdentity:
  aks:
    enabled: true
    clientId: "<azure-ad-app-client-id>"
    # tenantId: "<optional-tenant-id>"
```

Only one cloud may be enabled per release; the chart fails fast
at template time if more than one is. The cluster-side
trust-policy / role binding remains the operator's responsibility
— this chart's contract ends at the Pod's SA annotation.

## What this chart does NOT do (out of scope)

- **TLS termination** — handled by the Ingress controller / a sidecar
  / a load balancer in front of the cluster, not by the chart.
- **OIDC / auth** — Ophamin's HTTP endpoints are unauthenticated by
  default. Put a sidecar (oauth2-proxy / Envoy with JWT filter) in
  front for any deployment exposed beyond the cluster.
- **Persistent volumes** — Ophamin's CLI is stateless for the HTTP
  surface. Scenario runs that need persistent storage should mount
  volumes via a custom values.yaml override.
- **Secrets management** — `KIMERA_ENCODER_SNAPSHOT_KEY` and similar
  secrets should come from a real Secret (External Secrets Operator,
  SealedSecrets, or in-cluster Vault), not from values.yaml. Pass
  them via `http.env` referencing a Secret you've already provisioned.

## Verifying the deployment

The chart ships two `helm test` Pods:

- **HTTP `/health`** (always rendered when `http.enabled=true`)
  curls `/health` via the chart's Service.
- **MCP TCP probe** (rendered only when `mcp.enabled=true`,
  0.57.0+) uses `busybox` + `nc -z` to verify the MCP Service's
  TCP port accepts connections. Cheap minimum-viable signal at
  the network layer; the full MCP handshake is out of scope for
  helm-test (use `examples/walkthrough_mcp_server.py` for that).

Invoke both:

```bash
helm test my-ophamin -n ophamin
```

A green test confirms each surface is reachable. Test Pods are
auto-cleaned up after the run (hook-delete-policy:
hook-succeeded).

For manual verification:

```bash
kubectl get pods -n ophamin -l app.kubernetes.io/instance=my-ophamin
kubectl logs -n ophamin -l app.kubernetes.io/component=http-serve --tail=50
```

Port-forward and exercise:

```bash
kubectl port-forward -n ophamin svc/my-ophamin-http 8000:80
curl http://127.0.0.1:8000/health
curl http://127.0.0.1:8000/openapi.json | jq '.info'
```

## Upgrading

```bash
# Pin a new Ophamin version
helm upgrade my-ophamin oci://ghcr.io/idirbenslama/ophamin \
    --version 0.1.0 \
    --set image.tag=0.41.0 \
    --namespace ophamin

# Re-apply a values file
helm upgrade my-ophamin oci://ghcr.io/idirbenslama/ophamin \
    --version 0.1.0 \
    -f my-values.yaml \
    --namespace ophamin
```

## Uninstalling

```bash
helm uninstall my-ophamin --namespace ophamin
```

## Chart vs Ophamin versions

The chart's `version` (in `Chart.yaml`) is independent of the
`appVersion` (Ophamin's version). Bumping `image.tag` doesn't
require a chart re-cut. Bumping the chart's `version` is for
chart-only changes (template fixes, new toggles, etc.).

## See also

- [Ophamin project README](https://github.com/IdirBenSlama/Ophamin/blob/main/README.md)
- [Ophamin interop overview](https://github.com/IdirBenSlama/Ophamin/blob/main/docs/INTEROP_OVERVIEW.md)
- [Ophamin HTTP API README](https://github.com/IdirBenSlama/Ophamin/blob/main/src/ophamin/http_api/README.md)
- [Ophamin MCP server README](https://github.com/IdirBenSlama/Ophamin/blob/main/src/ophamin/mcp/README.md)
- [Docker GHCR publishing workflow](https://github.com/IdirBenSlama/Ophamin/blob/main/.github/workflows/docker.yml)
