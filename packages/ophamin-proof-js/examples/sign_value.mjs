/**
 * Write-side example: build a canonical value tree from JS,
 * canonicalize to bytes, and sign with HMAC-SHA256.
 *
 * Usage:
 *
 *   node packages/ophamin-proof-js/examples/sign_value.mjs
 *
 * Or via the npm script:
 *
 *   npm run --silent example:sign
 *
 * Demonstrates the consumer-facing surface of @ophamin/proof's
 * write-side: construct a value using ``PyInt`` for integer-typed
 * fields (preserves Python's int/float distinction in the
 * canonical bytes), canonicalize to bytes matching the Python
 * reference encoder byte-for-byte, then sign under any application
 * key. The resulting signature verifies identically against the
 * Python reference verifier.
 *
 * Build artifacts: this example imports from ../dist/, so run
 * `npm run build` first if you haven't.
 *
 * Exit 0 = canonicalize + sign succeeded.
 */

import { canonicalBytes, PyInt, signCanonical } from "../dist/src/index.js";

console.log("# Write-side example — JS package @ophamin/proof");
console.log();
console.log("Building a value tree in JS and canonicalizing to byte-");
console.log("equivalent output the Python reference would produce on the");
console.log("same logical input.");
console.log();

// === Step 1: build a value using PyInt for integer-typed fields ===
console.log("## Step 1: build the value tree");
const value = {
  measurement: {
    metric: 3.14159,
    threshold: 0.05,
    n_samples: new PyInt(120), // preserves int type in canonical bytes
    verified: true,
  },
  samples: [new PyInt(1), new PyInt(2), new PyInt(3)],
  note: "hello from JS",
};

console.log("  tree structure:");
console.log("    {");
console.log("      measurement: {");
console.log("        metric: 3.14159, threshold: 0.05,");
console.log("        n_samples: PyInt(120), verified: true");
console.log("      },");
console.log("      samples: [PyInt(1), PyInt(2), PyInt(3)],");
console.log("      note: 'hello from JS'");
console.log("    }");

// === Step 2: canonicalize to bytes ===
console.log("\n## Step 2: canonicalize to bytes");
const canonical = canonicalBytes(value);
const canonicalText = new TextDecoder().decode(canonical);
console.log(`  byte count:      ${canonical.length}`);
console.log("  canonical bytes:");
console.log(`    ${canonicalText}`);
console.log();
console.log("  Note: PyInt-wrapped values emit as `120` (NOT `120.0`).");
console.log("  Float values use Python's repr() formatting.");
console.log("  Object keys are sorted at every nesting level.");

// === Step 3: sign under an application key ===
console.log("\n## Step 3: sign under an application key");
const key = new TextEncoder().encode("my-deployment-key");
const signature = await signCanonical(value, key);
console.log(
  "  key:             my-deployment-key (HMAC-SHA256 derived internally)",
);
console.log(`  HMAC-SHA256:     ${signature}`);
console.log();
console.log("  This signature is byte-identical to what the Python");
console.log("  reference encoder produces on the same logical input.");
console.log("  The Rust port's sign_canonical produces the same bytes too.");

console.log("\n✓ Write-side example complete.");
