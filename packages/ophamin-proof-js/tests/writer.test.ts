/**
 * Write-side conformance — JS-produced canonical bytes match Python's
 * reference output byte-for-byte (RFC 0002 Phase E9 write-side).
 *
 * Where ``fixtures.test.ts`` exercises the read path (parse + canonicalize
 * an input JSON value → bytes match the committed fixture), this file
 * exercises the write path: build a value tree from native JS primitives
 * (with :class:`PyInt` for integer markers where Python's input is
 * int-typed), canonicalize it, and assert the bytes match the same
 * committed fixture.
 */

import { strict as assert } from "node:assert";
import { readFileSync } from "node:fs";
import { join } from "node:path";
import { describe, it } from "node:test";

import {
  PyInt,
  canonicalBytes,
  signCanonical,
} from "../src/canonical.js";

// At runtime ``import.meta.dirname`` resolves to ``dist/tests/`` (the
// compiled test directory). Repo root is four levels up.
const REPO_ROOT = join(import.meta.dirname, "..", "..", "..", "..");
const FIXTURES_DIR = join(REPO_ROOT, "tests", "canonical_form");
const TEST_KEY = new TextEncoder().encode("ophamin-canonical-test-key-v1");


function buildSimpleFixture(): unknown {
  return {
    a_integer: new PyInt(42),
    list: [new PyInt(1), new PyInt(2), new PyInt(3)],
    m_float: 3.14159,
    nested: { inner_a: new PyInt(1), inner_b: new PyInt(2) },
    w_null: null,
    x_false: false,
    y_true: true,
    z_string: "ophamin",
  };
}

function buildUnicodeFixture(): unknown {
  return {
    ascii_only: "hello world",
    cjk: "字幕",
    cyrillic: "привет",
    emoji: "🚀",
    latin_supp: "café résumé",
    "ключ": "value",
  };
}

function buildNumericalEdgeFixture(): unknown {
  return {
    large_pos: 1e20,
    neg_value: -2.5,
    neg_zero_float: -0.0,
    pi: 3.14159,
    small_neg_exp: 1e-7,
    zero_float: 0.0,
    zero_int: new PyInt(0),
  };
}


describe("JS write-side fixture conformance (E9 write-side)", () => {
  it("simple fixture canonical bytes match Python reference", () => {
    const expected = readFileSync(join(FIXTURES_DIR, "simple.canonical.bytes"));
    const actual = canonicalBytes(buildSimpleFixture() as never);
    assert.equal(
      new TextDecoder().decode(actual),
      new TextDecoder().decode(expected),
      "JS write-side drift on simple fixture",
    );
  });

  it("unicode fixture canonical bytes match Python reference", () => {
    const expected = readFileSync(join(FIXTURES_DIR, "unicode.canonical.bytes"));
    const actual = canonicalBytes(buildUnicodeFixture() as never);
    assert.equal(
      new TextDecoder().decode(actual),
      new TextDecoder().decode(expected),
      "JS write-side drift on unicode fixture",
    );
  });

  it("numerical_edge fixture canonical bytes match Python reference", () => {
    const expected = readFileSync(
      join(FIXTURES_DIR, "numerical_edge.canonical.bytes"),
    );
    const actual = canonicalBytes(buildNumericalEdgeFixture() as never);
    assert.equal(
      new TextDecoder().decode(actual),
      new TextDecoder().decode(expected),
      "JS write-side drift on numerical_edge fixture",
    );
  });

  it("signCanonical on simple fixture matches committed HMAC", async () => {
    const expectedHex = readFileSync(
      join(FIXTURES_DIR, "simple.hmac_sha256.hex"),
      "utf-8",
    ).trim();
    const sig = await signCanonical(
      buildSimpleFixture() as never,
      TEST_KEY,
    );
    assert.equal(sig, expectedHex);
  });

  it("signCanonical on unicode fixture matches committed HMAC", async () => {
    const expectedHex = readFileSync(
      join(FIXTURES_DIR, "unicode.hmac_sha256.hex"),
      "utf-8",
    ).trim();
    const sig = await signCanonical(
      buildUnicodeFixture() as never,
      TEST_KEY,
    );
    assert.equal(sig, expectedHex);
  });

  it("signCanonical on numerical_edge fixture matches committed HMAC", async () => {
    const expectedHex = readFileSync(
      join(FIXTURES_DIR, "numerical_edge.hmac_sha256.hex"),
      "utf-8",
    ).trim();
    const sig = await signCanonical(
      buildNumericalEdgeFixture() as never,
      TEST_KEY,
    );
    assert.equal(sig, expectedHex);
  });

  it("signCanonical returns 64-char lowercase hex", async () => {
    const sig = await signCanonical(
      { x: new PyInt(1) } as never,
      new TextEncoder().encode("any-key"),
    );
    assert.equal(sig.length, 64);
    assert.match(sig, /^[0-9a-f]+$/);
  });
});
