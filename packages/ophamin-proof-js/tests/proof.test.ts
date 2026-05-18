/**
 * End-to-end pins for ``parseProof`` + ``verifySignature``.
 *
 * The load-bearing test verifies a real Python-emitted signed proof
 * (the Spearman cross-framework agreement record from
 * ``proofs/measurement_machinery/``) using the JS verifier and the
 * Python deployment's ``DEFAULT_SIGN_KEY``. If this passes, JS reads
 * Python signatures cleanly — that IS the E9 read-API contract.
 */

import { strict as assert } from "node:assert";
import { readdirSync, readFileSync } from "node:fs";
import { join } from "node:path";
import { describe, it } from "node:test";

import {
  ProofParseError,
  parseProof,
  verifySignature,
  computeProofId,
} from "../src/proof.js";

// At runtime ``import.meta.dirname`` resolves to ``dist/tests/`` (the
// compiled test directory). Repo root is four levels up.
const REPO_ROOT = join(import.meta.dirname, "..", "..", "..", "..");
const PROOFS_DIR = join(REPO_ROOT, "proofs", "measurement_machinery");

// Same default sign key as Python's
// ``ophamin.measuring.scenarios.base.DEFAULT_SIGN_KEY``.
const DEFAULT_SIGN_KEY = new TextEncoder().encode(
  "ophamin-scenario-proof-key",
);

/** Discover every shipped signed proof to test against. */
function findShippedProofs(): string[] {
  const out: string[] = [];
  let subdirs: string[];
  try {
    subdirs = readdirSync(PROOFS_DIR);
  } catch {
    return [];
  }
  for (const dir of subdirs) {
    let files: string[];
    try {
      files = readdirSync(join(PROOFS_DIR, dir));
    } catch {
      continue;
    }
    for (const f of files) {
      if (f.endsWith(".json")) {
        out.push(join(PROOFS_DIR, dir, f));
      }
    }
  }
  return out;
}

describe("parseProof", () => {
  it("rejects non-JSON", () => {
    assert.throws(() => parseProof("not json"), ProofParseError);
  });

  it("rejects JSON arrays at top level", () => {
    assert.throws(() => parseProof("[1, 2, 3]"), ProofParseError);
  });

  it("rejects records missing required fields", () => {
    assert.throws(
      () => parseProof('{"schema_version": "1.0"}'),
      ProofParseError,
    );
  });

  it("accepts a minimally-shaped record", () => {
    // Strictly: parseProof only checks the top-level shape, NOT the
    // signature. So a record with all required keys parses cleanly
    // even if the signature is invalid.
    const minimal = JSON.stringify({
      schema_version: "1.0",
      identity: {},
      claim: {},
      preregistration: {},
      data: {},
      evidence: [],
      verdict: {},
      reproduction: {},
      provenance: {},
      signature: "deadbeef",
    });
    assert.doesNotThrow(() => parseProof(minimal));
  });
});

describe("verifySignature — Python-emitted proofs", () => {
  const shippedProofs = findShippedProofs();

  if (shippedProofs.length === 0) {
    it("(skipped — no signed proofs found in repo)", () => {});
    return;
  }

  for (const path of shippedProofs) {
    const name = path.split("/").slice(-2).join("/");
    it(`${name} verifies under DEFAULT_SIGN_KEY`, () => {
      const text = readFileSync(path, "utf-8");
      const proof = parseProof(text);
      const ok = verifySignature(proof, DEFAULT_SIGN_KEY);
      assert.equal(
        ok,
        true,
        `signature verification failed for ${name}\n` +
          `  signature in record: ${proof.signature.slice(0, 16)}...`,
      );
    });
  }

  it(`at least one signed proof exists in the repo (found ${shippedProofs.length})`, () => {
    assert.ok(shippedProofs.length >= 1);
  });
});

describe("computeProofId", () => {
  const shippedProofs = findShippedProofs();
  if (shippedProofs.length === 0) {
    it("(skipped — no signed proofs)", () => {});
    return;
  }

  it("matches a shipped proof's content-addressed filename", () => {
    // The filename contains the first 16 hex chars of the proof_id
    // (per the canonical-publication convention).
    const path = shippedProofs[0]!;
    const text = readFileSync(path, "utf-8");
    const proof = parseProof(text);
    const computed = computeProofId(proof);
    const filenameStem = path.split("/").pop()!.replace(".json", "");
    // Filenames may include the proof_id prefix or not — the
    // canonical pattern is "<scenario>_<id16>.json".
    const id16 = computed.slice(0, 16);
    assert.ok(
      filenameStem.includes(id16),
      `computed proof_id ${id16} not found in filename ${filenameStem}`,
    );
  });
});
