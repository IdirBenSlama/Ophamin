# Reproducing Ophamin's signed records + cross-language verification

> **Audience:** external reviewers, conformance testers, anyone
> running the framework on their own infrastructure to confirm
> Ophamin's empirical claims hold. This is the doc RFC 0002 Phase E4
> closeout names: "external reviewer rebuilds a tagged release +
> verifies byte-equal SBOM + signed-record output".

If you follow this guide and any step produces output that differs
from what's documented below, that is a real finding — please open
an issue at [github.com/IdirBenSlama/Ophamin/issues](https://github.com/IdirBenSlama/Ophamin/issues)
with the exact diff.

## What "reproducible" means here

The framework makes two distinct reproducibility claims:

1. **Within a tagged release, on the same supported platform**, the
   following are bit-stable:
   - Every signed proof's `proof_id` (content-addressed) and
     `signature` (HMAC-SHA256 under the documented sign key) emitted
     by a given scenario with a given seed.
   - Wheel + sdist content under `SOURCE_DATE_EPOCH` (wheel
     byte-equal across rebuilds; sdist content byte-equal, gzip
     wrapper may drift — see
     [`tests/test_build_reproducibility.py`](../tests/test_build_reproducibility.py)).

2. **Across languages, on the same canonical-form input**, the
   following are bit-stable:
   - Canonical bytes produced by Python's reference encoder, the
     Rust `ophamin-proof` writer, and the JS `@ophamin/proof` encoder.
   - HMAC-SHA256 digests over those bytes under the same key.
   - Cross-language fixture conformance at
     [`tests/canonical_form/`](../tests/canonical_form/) locks both
     directions (Python emit → Rust/JS verify; Rust/JS emit →
     Python verify).

## Minimum reproducer (10 minutes)

Walks through the most empirically-load-bearing checks. If these
pass, the framework's wire-format and signature claims hold on your
system.

### Step 1 — Clone + install

```bash
git clone https://github.com/IdirBenSlama/Ophamin.git
cd Ophamin
git checkout v0.21.2  # or the release you're verifying

python -m venv .venv
source .venv/bin/activate
pip install -e ".[all,dev,property_test]"
```

Supported platforms: Linux + macOS, Python 3.12 or 3.13. Windows
is not part of the CI matrix and is not tested.

### Step 2 — Run the cross-language canonical-form fixture tests

These are the load-bearing wire-format pins:

```bash
pytest tests/test_canonical_form_fixtures.py -v
```

**Expected output:** 21 passed.

If any of these fail on your system, the Python reference encoder
has drifted from the committed fixtures — that's a critical signal.
Run the same suite under JS and Rust (next steps) to triangulate
which port drifted.

### Step 3 — Run the JS port (Node ≥ 18)

```bash
cd packages/ophamin-proof-js
npm install
npm test
```

**Expected output:** 55 tests passing — 48 read-side + 7 write-side.

The output includes lines like:
```
✔ canonical bytes match Python reference (simple)
✔ HMAC-SHA256 under the test key matches Python reference (unicode)
✔ <real Python-emitted proof>.json verifies under DEFAULT_SIGN_KEY
```

If JS fails on fixture conformance but Python passes (step 2), the
JS port has drifted from the spec. If JS fails on a real signed
proof but the fixtures pass, the proof's signature has drifted.

### Step 4 — Run the Rust port

```bash
cd crates/ophamin-proof
cargo test
```

Requires Rust ≥ 1.75 (the documented MSRV). Install via
[rustup](https://rustup.rs/) if you don't have a toolchain.

**Expected output:** 28+ tests passing — 13 in-source unit tests +
~10 read-side integration tests + 7 write-side conformance tests.

### Step 5 — Verify a shipped signed proof end-to-end

This combines all three ports against the same committed artifact:

```bash
# Python
ophamin schema validate proofs/measurement_machinery/spearman_cross_framework/spearman_scipy_vs_pingouin_*.json

# JS — use the package's verifier on the same file
cd packages/ophamin-proof-js
cat > /tmp/verify.mjs <<'EOF'
import { readFileSync } from "node:fs";
import { parseProof, verifySignature } from "./dist/src/index.js";

const text = readFileSync(process.argv[2], "utf-8");
const proof = parseProof(text);
const key = new TextEncoder().encode("ophamin-scenario-proof-key");
const ok = verifySignature(proof, key);
console.log(ok ? "JS: ✓ verified" : "JS: ✗ FAILED");
process.exit(ok ? 0 : 1);
EOF
node /tmp/verify.mjs ../../proofs/measurement_machinery/spearman_cross_framework/spearman_scipy_vs_pingouin_*.json
```

**Expected output:** Python "✅ valid" + JS "✓ verified".

If both pass: the wire-format contract holds on your system across
two independent implementations. The same record verifies under
Rust as well — `cargo test shipped_proofs` exercises it.

## Full reproducer (1-2 hours)

For RFC 0002 E4 owner-side closeout, run the FULL test matrix:

```bash
# Python — full suite (~7 minutes on a modern laptop)
pytest -q

# Expected at v0.21.2: 1693+ passed, 2 skipped, 0 failed.

# JS — full local suite (~3 seconds)
cd packages/ophamin-proof-js && npm test

# Expected: 55 passed.

# Rust — full local suite (~30 seconds with deps cached)
cd crates/ophamin-proof && cargo test --all-features

# Expected: 28+ passed (varies by what test files are added in
# future releases — see the suite's --list output for the exact count).

# Build reproducibility (single-machine — full cross-OS diffoscope
# is the owner-side closeout step)
SOURCE_DATE_EPOCH=1697812800 python -m build --wheel
sha256sum dist/ophamin-*.whl  # record this
# Clean + rebuild + compare
rm -rf dist build && SOURCE_DATE_EPOCH=1697812800 python -m build --wheel
sha256sum dist/ophamin-*.whl  # should match the prior digest
```

The wheel SHA-256 digest is bit-stable across rebuilds on the same
machine when `SOURCE_DATE_EPOCH` is pinned (per
[`tests/test_build_reproducibility.py`](../tests/test_build_reproducibility.py)).
Cross-machine diffoscope-clean build is the owner-side gate for
E4 closeout (requires multiple reviewer rigs).

## Verify a signed empirical proof from a paper

If you're verifying a proof referenced in a paper or blog post,
the workflow is:

1. Download the proof JSON file from the paper's supplementary
   materials or repository.
2. Verify the framework + record version match the paper's claim.
   Check `identity.ophamin_version` and `schema_version` in the
   JSON.
3. Verify the signature:

   ```bash
   ophamin schema validate <proof.json>
   ```

   Or programmatically (Python):

   ```python
   from ophamin.measuring.proof.codec import load
   from ophamin.measuring.scenarios.base import DEFAULT_SIGN_KEY

   record = load("proof.json")
   assert record.verify_signature(DEFAULT_SIGN_KEY)
   ```

4. Inspect the verdict:

   ```python
   print(record.verdict.outcome)        # VALIDATED / REFUTED / INCONCLUSIVE
   print(record.verdict.observed_value) # the measured statistic
   print(record.verdict.threshold)      # the pre-registered pass/fail boundary
   print(record.verdict.reasoning)      # human-readable rationale
   ```

5. Reproduce the scenario (if you have the substrate + corpus):

   ```bash
   ophamin scenario <scenario-name> --seed <seed-from-config>
   ```

   The freshly-emitted record's `proof_id` should match the
   archived one IFF you have the exact same substrate + corpus +
   seed.

## What's verified

| Check | Where | Tests |
|---|---|---|
| Cross-language canonical-form (3 fixtures) | Python `tests/test_canonical_form_fixtures.py`; JS `tests/fixtures.test.ts`; Rust `tests/fixture_conformance.rs` | 21 + 12 + 10 |
| Cross-language WRITE side (Rust+JS → Python verify) | Rust `tests/writer_conformance.rs`; JS `tests/writer.test.ts` | 7 + 7 |
| Real shipped proofs (7 cross-framework + ...) | All three ports | 7+ each |
| Build reproducibility (single-machine, SOURCE_DATE_EPOCH) | Python `tests/test_build_reproducibility.py` | 3 |
| Framework-wide reproducibility audit (every seed-taking scenario produces bit-identical proofs) | Python `tests/test_framework_wide_reproducibility.py` | ~8 |

## What's NOT verified by this guide (owner-side closeout)

These remain owner-driven per RFC 0002:

- **Diffoscope-clean cross-machine build**: building the same
  release on two physically distinct machines and confirming
  byte-equal output via diffoscope. Requires multiple reviewer
  rigs.
- **Zenodo deposit + DOI**: the framework's signed proofs +
  source archive deposited at Zenodo, getting a DOI for paper
  citation. Owner-side because Zenodo account must be linked to
  the GitHub repo.
- **JOSS / SoftwareX / JMLR-OSS submission**: the methods paper
  (`paper/paper.md`) submitted, reviewer feedback addressed.
  Owner-side because requires an ORCID + venue choice.

## See also

- [`SCHEMAS.md`](../SCHEMAS.md) — normative wire-format spec.
- [`docs/STABILITY.md`](STABILITY.md) — API stability contract.
- [`docs/ELEVATION_ROADMAP_2026_05_16.md`](ELEVATION_ROADMAP_2026_05_16.md) §8.5 — RFC 0002 phase status table.
- [`paper/paper.md`](../paper/paper.md) — methods paper draft.
- [`CITATION.cff`](../CITATION.cff) + [`.zenodo.json`](../.zenodo.json) — citation + Zenodo deposit metadata.
