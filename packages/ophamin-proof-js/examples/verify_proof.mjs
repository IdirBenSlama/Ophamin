/**
 * Read-side example: verify a Python-emitted signed proof from JS.
 *
 * Usage:
 *
 *   node packages/ophamin-proof-js/examples/verify_proof.mjs [path/to/proof.json]
 *
 * Or via the npm script:
 *
 *   npm run --silent example:verify
 *
 * Demonstrates the consumer-facing surface of @ophamin/proof:
 * parseProof to load the JSON into a structured record, then
 * verifySignature to check HMAC-SHA256 over the canonical body
 * bytes under the documented DEFAULT_SIGN_KEY.
 *
 * Exit 0 = verified. Exit 1 = signature mismatch or parse failure.
 *
 * Build artifacts: this example imports from ../dist/, so run
 * `npm run build` first if you haven't.
 */

import { readFileSync, readdirSync, statSync } from "node:fs";
import { join, dirname } from "node:path";
import { fileURLToPath } from "node:url";
import { parseProof, verifySignature } from "../dist/src/index.js";

const HERE = dirname(fileURLToPath(import.meta.url));
const PACKAGE_ROOT = join(HERE, "..");
const REPO_ROOT = join(PACKAGE_ROOT, "..", "..");

// The HMAC key the Python emitter uses by default. Production
// deployments rotate this via the `ophamin schema validate --key`
// CLI argument or the `Scenario.run(sign_key=...)` kwarg.
const DEFAULT_SIGN_KEY = new TextEncoder().encode(
  "ophamin-scenario-proof-key",
);

function findFirstShippedProof() {
  const dir = join(REPO_ROOT, "proofs", "measurement_machinery");
  const stack = [dir];
  while (stack.length > 0) {
    const cur = stack.pop();
    let entries;
    try {
      entries = readdirSync(cur);
    } catch {
      continue;
    }
    for (const name of entries.sort()) {
      const path = join(cur, name);
      const st = statSync(path);
      if (st.isDirectory()) {
        stack.push(path);
      } else if (name.endsWith(".json")) {
        return path;
      }
    }
  }
  return null;
}

async function main() {
  console.log("# Read-side example — JS package @ophamin/proof");
  console.log();

  let proofPath = process.argv[2];
  if (!proofPath) {
    proofPath = findFirstShippedProof();
    if (!proofPath) {
      console.error(
        "Usage: node examples/verify_proof.mjs [path/to/proof.json]",
      );
      console.error(
        "       (no path given; no shipped proof found under " +
          "proofs/measurement_machinery/ either)",
      );
      process.exit(1);
    }
  }

  console.log(`Loading: ${proofPath}`);
  const text = readFileSync(proofPath, "utf-8");

  let proof;
  try {
    proof = parseProof(text);
  } catch (err) {
    console.error("parseProof failed:", err.message);
    process.exit(1);
  }

  console.log();
  console.log(`proof_id:       ${proof.proof_id}`);
  console.log(`schema_version: ${proof.schema_version}`);
  console.log(`verdict:        ${proof.verdict.outcome}`);
  console.log(`signature:      ${proof.signature.slice(0, 16)}...`);

  let verified;
  try {
    verified = await verifySignature(proof, DEFAULT_SIGN_KEY);
  } catch (err) {
    console.error("verifySignature failed:", err.message);
    process.exit(1);
  }

  console.log();
  if (verified) {
    console.log("✓ signature verified under DEFAULT_SIGN_KEY");
    console.log();
    console.log("The package has confirmed (byte-for-byte) that the");
    console.log("canonical body of this proof was signed with the same");
    console.log("key the Python emitter used. Cross-host integrity confirmed.");
    process.exit(0);
  } else {
    console.error("✗ signature MISMATCH — proof body has drifted");
    process.exit(1);
  }
}

await main();
