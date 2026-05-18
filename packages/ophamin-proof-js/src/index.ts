/**
 * `@ophamin/proof` — read-only verifier for Ophamin signed
 * empirical-proof records.
 *
 * Two public surfaces:
 *
 * 1. ``canonical`` — the byte-equivalent canonical-form encoder.
 *    Implements `SCHEMAS.md` §"Canonical-form determinism (normative)"
 *    rules R1–R11. Use it when you need to verify a Python-emitted
 *    HMAC byte-for-byte from another language.
 *
 * 2. ``proof`` — record parser + signature verifier. Reads a
 *    `EmpiricalProofRecord` from the wire form, exposes its fields
 *    in typed form, and verifies the HMAC-SHA256 signature.
 *
 * Conformance is pinned by tests under `tests/`, which load the
 * same fixtures the Python reference uses under
 * `<repo>/tests/canonical_form/`. A drift in the canonical-form
 * encoder fails the suite loud.
 *
 * See `<repo>/SCHEMAS.md` for the normative spec, and
 * `<repo>/crates/README.md` for the parallel Rust port's design.
 */

export {
  CanonicalFormError,
  PyInt,
  canonicalize,
  canonicalBytes,
  escapeString,
  pythonRepr,
} from "./canonical.js";
export type { CanonicalValue } from "./canonical.js";

export {
  JsonParseError,
  parseJsonPreservingInts,
} from "./parse.js";

export {
  ProofParseError,
  ProofSignatureError,
  bodyForSigning,
  computeProofId,
  parseProof,
  verifySignature,
} from "./proof.js";
export type {
  Claim,
  DatasetRef,
  EmpiricalProofRecord,
  PillarEvidence,
  PreRegistration,
  Reproduction,
  Threshold,
  Verdict,
} from "./proof.js";
