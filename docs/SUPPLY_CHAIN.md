# Ophamin supply-chain provenance

> Every artifact Ophamin publishes — the Python sdist + wheel, the
> Docker image at `ghcr.io/idirbenslama/ophamin`, the Helm chart at
> `oci://ghcr.io/idirbenslama/ophamin` — carries cryptographic
> evidence of where it came from and is independently verifiable
> against the public Sigstore transparency log.

## At a glance

| Artifact | Where | Signing | How to verify |
|---|---|---|---|
| Docker image | `ghcr.io/idirbenslama/ophamin` | Sigstore keyless (cosign) | `cosign verify ghcr.io/idirbenslama/ophamin@<digest> --certificate-identity-regexp=...` |
| Helm chart | `oci://ghcr.io/idirbenslama/ophamin/ophamin` | Sigstore keyless (cosign) | `cosign verify ghcr.io/idirbenslama/ophamin/ophamin@<digest> --certificate-identity-regexp=...` |
| `EmpiricalProofRecord` (proof JSON) | per-deployment | HMAC-SHA256 (own key) | `verify_proof_impl(json)` / Rust + JS ports / HTTP `/verify` endpoint |
| `EmpiricalProofRecord` (in-toto Statement) | per-deployment | HMAC-SHA256 (own key, double-layer) | `cosign verify-attestation` — see [INTEROP_OVERVIEW.md](INTEROP_OVERVIEW.md) |

The three signing schemes are independent: cosign protects the
distribution channel (Docker image + Helm chart), HMAC-SHA256
protects individual proof records, and the in-toto wrapper
bridges the two (so an Ophamin proof can be signed by Sigstore
when emitted into a SLSA-aware pipeline).

## Cosign keyless signing — how it works

Ophamin's `docker.yml` and `chart.yml` workflows sign every
published artifact via Sigstore's keyless flow:

1. **GitHub Actions OIDC token** — the workflow's
   `id-token: write` permission lets it request a short-lived
   OIDC token identifying the workflow's identity:
   `https://github.com/IdirBenSlama/Ophamin/.github/workflows/docker.yml@refs/heads/main`
   (or the `v*` tag ref, for tagged releases).

2. **Fulcio CA** — Sigstore's Fulcio service receives the OIDC
   token, verifies it against GitHub's identity provider, and
   issues a short-lived X.509 certificate (10-minute lifetime)
   binding a fresh ephemeral key to that identity.

3. **Signing** — `cosign sign` uses the ephemeral key to sign
   the artifact's content digest. The signature, the ephemeral
   public key, and the Fulcio certificate are bundled as an OCI
   "signature artifact" and stored as a sibling of the original
   artifact in GHCR (e.g. `ghcr.io/idirbenslama/ophamin:sha256-<digest>.sig`).

4. **Rekor transparency log** — cosign also records the signing
   event in [Rekor](https://rekor.sigstore.dev), Sigstore's
   public transparency log. The signature's existence becomes
   tamper-evident and permanently auditable — anyone can fetch
   the log entry years later to confirm the artifact was signed
   at the time the publish workflow ran.

5. **Key destruction** — the ephemeral key is discarded
   immediately after signing. No private key material exists to
   be stolen or leaked.

## Verifying an Ophamin Docker image

```bash
# Install cosign if you haven't (one-time)
brew install cosign           # macOS
# or:
# go install github.com/sigstore/cosign/v2/cmd/cosign@latest

# Verify the :latest tag
cosign verify ghcr.io/idirbenslama/ophamin:latest \
    --certificate-identity-regexp='^https://github\.com/IdirBenSlama/Ophamin/\.github/workflows/docker\.yml@.*' \
    --certificate-oidc-issuer=https://token.actions.githubusercontent.com
```

A successful verify prints the certificate's subject (workflow
identity) + the Rekor log index + the bundle. If verification
fails, cosign exits non-zero with a clear error message.

You can also pin verification to a specific commit-driven build:

```bash
# Verify a specific image by digest (not just by tag)
cosign verify ghcr.io/idirbenslama/ophamin@sha256:<digest> \
    --certificate-identity-regexp='^https://github\.com/IdirBenSlama/Ophamin/\.github/workflows/docker\.yml@.*' \
    --certificate-oidc-issuer=https://token.actions.githubusercontent.com
```

## Verifying an Ophamin Helm chart

```bash
# Verify the chart (replace <digest> with the actual digest from
# `helm show chart` or the workflow run summary)
cosign verify ghcr.io/idirbenslama/ophamin/ophamin@sha256:<digest> \
    --certificate-identity-regexp='^https://github\.com/IdirBenSlama/Ophamin/\.github/workflows/chart\.yml@.*' \
    --certificate-oidc-issuer=https://token.actions.githubusercontent.com
```

Note the path differs: the Docker image is at
`ghcr.io/idirbenslama/ophamin` while the Helm chart is at
`ghcr.io/idirbenslama/ophamin/ophamin` (the trailing `/ophamin`
is the chart name segment within the owner's OCI namespace, and
`helm push` creates the subpath automatically based on
`Chart.yaml`'s `name:` field).

## Verification in Kubernetes admission

Use [Sigstore policy-controller](https://github.com/sigstore/policy-controller)
or [Kyverno](https://kyverno.io) to require signed images cluster-
wide:

```yaml
# policy-controller / ClusterImagePolicy
apiVersion: policy.sigstore.dev/v1beta1
kind: ClusterImagePolicy
metadata:
  name: require-ophamin-signed
spec:
  images:
    - glob: "ghcr.io/idirbenslama/ophamin*"
  authorities:
    - keyless:
        identities:
          - issuer: https://token.actions.githubusercontent.com
            subjectRegExp: ^https://github\.com/IdirBenSlama/Ophamin/.*
```

Pods pulling unsigned or wrongly-signed Ophamin images fail
admission with a clear policy violation message.

## Verifying an `EmpiricalProofRecord`

This is independent of cosign — each proof carries its own
HMAC-SHA256 signature over the canonical body bytes (per
[SCHEMAS.md](https://github.com/IdirBenSlama/Ophamin/blob/main/SCHEMAS.md) R1–R11):

```python
from ophamin.measuring.proof.codec import load
record = load("path/to/proof.json")
assert record.verify_signature(b"the-deployment-key")
```

Cross-language verification:

```rust
// Rust port
use ophamin_proof::{parse_proof, verify_signature};
let record = parse_proof(&proof_text)?;
let ok = verify_signature(&record, b"the-deployment-key");
```

```typescript
// JS/TS port
import { parseProof, verifySignature } from "@ophamin/proof";
const record = parseProof(proofText);
const ok = await verifySignature(record, key);
```

All three ports verify byte-identically against the same proof
file — the cross-language conformance suite locks this property
at every release.

## Two-layer Sigstore + Ophamin verification

When an `EmpiricalProofRecord` flows through the in-toto wrapper
(`to_in_toto_statement` / `to_dsse_envelope`), the result is a
double-signed artifact: the outer DSSE envelope is signed by
whatever key the operator chooses (could be cosign keyless via
their own pipeline), and the inner Ophamin proof body is signed
by the original Ophamin HMAC key.

Verifying both layers:

```python
import json, base64
from ophamin.interop import verify_dsse_envelope
from ophamin.measuring.proof.codec import load_from_dict

# 1. Verify outer DSSE
assert verify_dsse_envelope(envelope, dsse_key)

# 2. Decode inner Statement → predicate.body + predicate.signature
statement = json.loads(base64.b64decode(envelope["payload"]))
body = statement["predicate"]["body"]
sig = statement["predicate"]["signature"]

# 3. Verify inner Ophamin HMAC against the body
import hmac, hashlib
from ophamin.measuring.proof.record import _canonical
expected = hmac.new(
    ophamin_key,
    _canonical(body).encode("utf-8"),
    hashlib.sha256,
).hexdigest()
assert hmac.compare_digest(expected, sig)
```

See [INTEROP_OVERVIEW.md](INTEROP_OVERVIEW.md) §"I want my proof
on Sigstore / Rekor / SLSA infrastructure" for the full flow.

## Trust model summary

What each signature guarantees:

- **Cosign signature on Docker image / Helm chart** — the artifact
  was published by Ophamin's GitHub Actions workflow at a specific
  commit. The signature is publicly verifiable; the Rekor entry
  is publicly auditable. The user does NOT need to trust GHCR's
  storage layer — tampering with the artifact bytes in-place
  would break the signature.

- **HMAC signature on a proof record** — the proof body was
  produced by a process holding the deployment's HMAC key. The
  user trusts the key holder (typically the Ophamin operator).
  Different operators use different keys; cross-operator trust
  is established by sharing keys or by layering Sigstore on top
  via the in-toto wrapper.

- **In-toto / DSSE wrapper** — bridges the two by carrying the
  proof body as a DSSE payload that can be signed via cosign
  keyless OR by HMAC. Two-layer verification gives both
  cryptographic provenance (cosign) AND content authenticity
  (Ophamin HMAC).

## What this does NOT include

- **Reproducible-build attestations** (SLSA Level 3+) — the
  Docker image build is *not* yet a fully reproducible Bazel /
  Nix build. The published image is signed but two builds at the
  same commit may differ at the byte level (timestamps, debian
  package ordering). Closing this requires a deeper rebuild of
  the Dockerfile around a reproducible-build framework.
- **SBOM signing** — the SBOM (CycloneDX, per the
  `interop/cyclonedx.py` exporter) is itself an Ophamin proof
  record that uses HMAC. A future ship can also sign the SBOM
  via cosign for cross-format provenance.
- **Cosign signing for the Python package** — `ophamin` on PyPI
  is not yet signed via [PyPI's trusted publishing +
  attestations](https://docs.pypi.org/attestations/). The
  `release.yml` workflow is the operator-physical owner step
  for this; the chart-publish workflow's pattern is reusable.

## See also

- [Sigstore Cosign documentation](https://docs.sigstore.dev/cosign/overview/)
- [SLSA framework](https://slsa.dev/)
- [in-toto Attestation v1 spec](https://github.com/in-toto/attestation/blob/main/spec/v1/statement.md)
- [INTEROP_OVERVIEW.md](INTEROP_OVERVIEW.md) — full Ophamin interop catalogue
- [SCHEMAS.md](https://github.com/IdirBenSlama/Ophamin/blob/main/SCHEMAS.md) — proof record canonical form
- [`.github/workflows/docker.yml`](https://github.com/IdirBenSlama/Ophamin/blob/main/.github/workflows/docker.yml) — image publishing + signing
- [`.github/workflows/chart.yml`](https://github.com/IdirBenSlama/Ophamin/blob/main/.github/workflows/chart.yml) — chart publishing + signing
