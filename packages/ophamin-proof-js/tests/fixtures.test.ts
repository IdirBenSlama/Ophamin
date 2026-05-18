/**
 * Cross-language canonical-form fixture conformance suite.
 *
 * Loads the five fixtures under ``<repo>/tests/canonical_form/``
 * (``boundary_cases``, ``deeply_nested``, ``numerical_edge``,
 * ``simple``, ``unicode``) and asserts:
 *
 * - The JS canonical-form encoder produces byte-equivalent output to
 *   the committed ``<stem>.canonical.bytes`` for each fixture.
 * - HMAC-SHA256 over the canonical bytes under the fixed test key
 *   matches the committed ``<stem>.hmac_sha256.hex``.
 *
 * Failure here means the JS port has drifted from the Python
 * reference — signatures will no longer cross-verify and the
 * package's read-API contract is broken.
 */

import { strict as assert } from "node:assert";
import { createHmac } from "node:crypto";
import { readFileSync } from "node:fs";
import { join } from "node:path";
import { describe, it } from "node:test";

import { canonicalBytes, canonicalize } from "../src/canonical.js";
import { parseJsonPreservingInts } from "../src/parse.js";

// At runtime ``import.meta.dirname`` resolves to ``dist/tests/`` (the
// compiled test directory). Repo root is four levels up:
// dist/tests → dist → ophamin-proof-js → packages → repo
const REPO_ROOT = join(import.meta.dirname, "..", "..", "..", "..");
const FIXTURES_DIR = join(REPO_ROOT, "tests", "canonical_form");

const TEST_KEY = new TextEncoder().encode(
  "ophamin-canonical-test-key-v1",
);

const FIXTURE_STEMS = [
  "boundary_cases",
  "deeply_nested",
  "numerical_edge",
  "simple",
  "unicode",
] as const;

function readFixtureInput(stem: string): unknown {
  // Use the int-preserving parser so integers in fixture inputs
  // canonicalize back to ``N`` (not ``N.0``) — matching Python.
  return parseJsonPreservingInts(
    readFileSync(join(FIXTURES_DIR, `${stem}.input.json`), "utf-8"),
  );
}

function readFixtureCanonical(stem: string): Uint8Array {
  return readFileSync(join(FIXTURES_DIR, `${stem}.canonical.bytes`));
}

function readFixtureHmac(stem: string): string {
  return readFileSync(
    join(FIXTURES_DIR, `${stem}.hmac_sha256.hex`),
    "utf-8",
  ).trim();
}

describe("canonical-form fixture conformance", () => {
  for (const stem of FIXTURE_STEMS) {
    describe(stem, () => {
      it("canonical bytes match Python reference", () => {
        const input = readFixtureInput(stem);
        const expected = readFixtureCanonical(stem);
        // Cast to CanonicalValue since the JSON parser returns
        // `unknown` but we know the fixtures are JSON-native.
        const actual = canonicalBytes(input as never);
        assert.equal(
          Buffer.from(actual).toString("hex"),
          Buffer.from(expected).toString("hex"),
          `canonical-form drift on ${stem}:\n` +
            `  expected (${expected.length}B): ${new TextDecoder().decode(expected)}\n` +
            `  actual   (${actual.length}B): ${new TextDecoder().decode(actual)}`,
        );
      });

      it("HMAC-SHA256 under the test key matches Python reference", () => {
        const expectedHex = readFixtureHmac(stem);
        const canonical = readFixtureCanonical(stem);
        const actualHex = createHmac("sha256", TEST_KEY)
          .update(canonical)
          .digest("hex");
        assert.equal(
          actualHex,
          expectedHex,
          `HMAC drift on ${stem}:\n` +
            `  expected: ${expectedHex}\n` +
            `  actual:   ${actualHex}`,
        );
      });

      it("idempotence: re-canonicalizing the parsed canonical bytes yields the same bytes", () => {
        // Parse the canonical bytes as JSON, re-canonicalize, assert
        // byte-equal. This is the same property the Python test
        // `test_all_fixtures_round_trip_via_python_json` pins.
        const canonical = readFixtureCanonical(stem);
        const reParsed = parseJsonPreservingInts(
          new TextDecoder().decode(canonical),
        );
        const reCanonical = canonicalize(reParsed);
        assert.equal(
          reCanonical,
          new TextDecoder().decode(canonical),
        );
      });
    });
  }

  it("each fixture has all three artefacts on disk", () => {
    for (const stem of FIXTURE_STEMS) {
      for (const suffix of [
        ".input.json",
        ".canonical.bytes",
        ".hmac_sha256.hex",
      ]) {
        const path = join(FIXTURES_DIR, `${stem}${suffix}`);
        assert.doesNotThrow(
          () => readFileSync(path),
          `missing ${path}`,
        );
      }
    }
  });
});
