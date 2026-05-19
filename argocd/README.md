# ArgoCD — GitOps deployment for Ophamin

> Phase #4 of the 4-phase SonarQube-integration roadmap closes
> the CI → GitOps loop. After Ophamin's image + chart pass the
> SonarQube quality gate (sonar.yml), the Trivy + OWASP DC
> security scans (trivy.yml + sonar.yml's DC step), and ship
> with cosign + SBOM + SLSA attestations (docker.yml +
> chart.yml), this manifest tells ArgoCD to auto-deploy the
> validated artifact to a K8s cluster.

## What's in this directory

| File | Purpose |
|---|---|
| `ophamin-application.yaml` | ArgoCD `Application` manifest pointing at the Helm chart at `oci://ghcr.io/idirbenslama/ophamin` |
| `README.md` | this doc |

## How to use it

### Pre-requisites

- A Kubernetes cluster (any conformant cluster — KIND, GKE,
  EKS, AKS, on-prem, edge, etc.)
- ArgoCD installed in the cluster (per [official install
  guide](https://argo-cd.readthedocs.io/en/stable/getting_started/))
- ArgoCD 2.6+ (for native OCI Helm chart support; older versions
  need the `helm-oci-experimental` flag)

### Apply the manifest

```bash
# Via kubectl directly (assumes argocd namespace exists)
kubectl apply -f argocd/ophamin-application.yaml -n argocd

# Or via the ArgoCD CLI
argocd app create -f argocd/ophamin-application.yaml

# Verify
argocd app get ophamin
argocd app sync ophamin   # if automated sync didn't trigger
```

ArgoCD will then:

1. Pull the Helm chart from `oci://ghcr.io/idirbenslama/ophamin`
   at version `0.1.0`
2. Render templates with the inline `values:` from the
   Application manifest
3. Apply the rendered resources to namespace `ophamin` in the
   in-cluster destination
4. Watch the chart's GHCR location for new versions (per the
   sync policy)
5. Auto-reconcile drift (self-heal: true)

### What gets deployed

The Helm chart shipped at 0.40.0+ deploys:

- **Deployment + Service for `ophamin http serve`** (2
  replicas, `/health` probes, `policy/v1` Pod Disruption
  Budget at `minAvailable: 50%`, optional autoscaling 2-10
  replicas on 75% CPU)
- **Optional MCP Deployment** (gated on `mcp.enabled=true`;
  disabled by default in this Application manifest)
- **NetworkPolicy** (gated on `networkPolicy.enabled=true`;
  disabled by default — operators tune cluster-specific
  ingress/egress)
- **ServiceAccount** + **`helm test` hook Pod** for
  post-install health curl

See [`charts/ophamin/README.md`](https://github.com/IdirBenSlama/Ophamin/blob/main/charts/ophamin/README.md)
for the full chart resource catalogue.

## Production hardening: combine with policy-controller

For the full supply-chain enforcement, pair this Application
with a Sigstore `policy-controller` ClusterImagePolicy that
requires signed images + SBOM attestation + SLSA provenance.

```yaml
# Excerpt — see docs/SUPPLY_CHAIN.md for the full example
apiVersion: policy.sigstore.dev/v1beta1
kind: ClusterImagePolicy
metadata:
  name: require-ophamin-signed-with-attestations
spec:
  images:
    - glob: "ghcr.io/idirbenslama/ophamin*"
  authorities:
    - keyless:
        identities:
          - issuer: https://token.actions.githubusercontent.com
            subjectRegExp: ^https://github\.com/IdirBenSlama/Ophamin/.*
        attestations:
          - name: must-have-sbom
            predicateType: https://cyclonedx.org/bom
          - name: must-have-slsa
            predicateType: https://slsa.dev/provenance/v1
```

With this in place, an Ophamin Pod cannot start unless its
image carries a valid cosign signature AND a valid CycloneDX
SBOM attestation AND a valid SLSA v1.0 provenance attestation.
**The supply-chain trilogy is enforced at admission time** —
not just available for verification.

## The full pipeline after 0.54.0

```text
┌──────────────────────────────────────────────────────────────┐
│ Developer edits Ophamin source in VS Code / Cursor / etc.    │
│   ↓                                                          │
│ SonarLint (.sonarlint/connectedMode.json, 0.53.0)            │
│   → real-time SonarQube analysis in editor                   │
└────────────────────┬─────────────────────────────────────────┘
                     │ git push / PR
                     ▼
┌──────────────────────────────────────────────────────────────┐
│ GH Actions CI                                                │
│ ├─ sonar.yml (0.51.0) → SonarQube SAST + OWASP DC SCA       │
│ ├─ trivy.yml (0.52.0) → Trivy fs-scan + image-scan          │
│ ├─ docker.yml → multi-arch GHCR push + cosign sign           │
│ │                + SBOM cosign attest + SLSA provenance      │
│ ├─ chart.yml  → Helm chart GHCR push + cosign sign           │
│ └─ All structural pins green (187+ chart/sonar/trivy)        │
└────────────────────┬─────────────────────────────────────────┘
                     │ artifacts in GHCR
                     ▼
┌──────────────────────────────────────────────────────────────┐
│ ArgoCD (0.54.0)                                              │
│ ├─ Watches oci://ghcr.io/idirbenslama/ophamin                │
│ ├─ Auto-syncs ophamin-application.yaml                       │
│ └─ self-heal + prune + retry on sync failure                 │
└────────────────────┬─────────────────────────────────────────┘
                     │ Helm chart render + kubectl apply
                     ▼
┌──────────────────────────────────────────────────────────────┐
│ K8s cluster                                                  │
│ ├─ policy-controller (optional, recommended)                 │
│ │   → admission-gates on signature + SBOM + SLSA attestations│
│ └─ Ophamin Pods running with HTTP REST + (optional) MCP      │
└──────────────────────────────────────────────────────────────┘
```

## Why GitOps for Ophamin

Ophamin's value proposition is **signed, content-addressed,
falsifiable claims**. Imperative `kubectl apply` deployments
break that — they have no commit-pinned trail of what was
applied when. GitOps via ArgoCD makes every deployment a
git commit + a chart digest, both fully attributable.

Pairs naturally with Ophamin's supply-chain trilogy
([`docs/SUPPLY_CHAIN.md`](https://github.com/IdirBenSlama/Ophamin/blob/main/docs/SUPPLY_CHAIN.md)):
the image is cosign-signed + SBOM-attested + SLSA-attested
BEFORE it ever reaches the cluster; ArgoCD then guarantees
that what's deployed matches the validated artifact in GHCR.

## See also

- [ArgoCD Application reference](https://argo-cd.readthedocs.io/en/stable/operator-manual/declarative-setup/#applications)
- [`charts/ophamin/`](https://github.com/IdirBenSlama/Ophamin/tree/main/charts/ophamin) — the Helm chart this Application consumes
- [`docs/SUPPLY_CHAIN.md`](https://github.com/IdirBenSlama/Ophamin/blob/main/docs/SUPPLY_CHAIN.md) — cosign / SBOM / SLSA verification recipes
- [`docs/SONARQUBE.md`](https://github.com/IdirBenSlama/Ophamin/blob/main/docs/SONARQUBE.md) — the four-phase SonarQube integration story (CI / Security / Local / Deployment)
- [`tests/test_argocd_application.py`](https://github.com/IdirBenSlama/Ophamin/blob/main/tests/test_argocd_application.py) — hardening pins for the manifest
