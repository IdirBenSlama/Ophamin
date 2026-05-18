/**
 * Read-only proof-record verifier.
 *
 * An :class:`EmpiricalProofRecord` is a 9-section signed artefact
 * Ophamin scenarios emit. The wire form is the body (sections 1–8 in
 * nested-dict shape) plus ``signature`` and ``proof_id`` at the top
 * level. The JS port supports:
 *
 * - Parsing the JSON wire form into a typed record.
 * - Reconstructing the body bytes that the Python emitter signed.
 * - Verifying the HMAC-SHA256 signature in section 9.
 *
 * Mutating the record or re-signing it is intentionally NOT supported
 * — JS is the read-only side per RFC 0002 §3.1 E9. Records originate
 * from the Python reference; the JS port verifies them.
 */

import { createHmac, createHash, timingSafeEqual } from "node:crypto";
import {
  CanonicalFormError,
  CanonicalValue,
  canonicalBytes,
} from "./canonical.js";
import { parseJsonPreservingInts } from "./parse.js";

/** Sub-record types — mirror the Python dataclasses' wire shape. */

export interface Threshold {
  metric: string;
  comparator: ">=" | "<=" | ">" | "<" | "==";
  value: number;
  units?: string;
}

export interface Claim {
  statement: string;
  operationalization: string;
  threshold: Threshold;
  h0: string;
  h1: string;
}

export interface DatasetRef {
  name: string;
  content_hash: string;
  n_records: number;
  source?: string;
  kind?: string;
}

export interface PillarEvidence {
  pillar: string;
  statistic_name: string;
  statistic_value: number;
  library?: string;
  library_version?: string;
  effect_size?: number | null;
  ci_low?: number | null;
  ci_high?: number | null;
  p_value?: number | null;
  cross_check?: string;
  detail?: Record<string, unknown>;
}

export interface Verdict {
  outcome: "VALIDATED" | "REFUTED" | "INCONCLUSIVE";
  observed_value: number;
  threshold: Threshold;
  reasoning: string;
}

export interface PreRegistration {
  config_hash: string;
  data_hash: string;
  analysis_plan: string;
  preregistered_at?: string;
}

export interface Reproduction {
  command: string;
}

/** Nested ``identity`` block in the wire form. */
export interface Identity {
  ophamin_version: string;
  ophamin_git_commit: string;
  created_at: string;
}

/** Nested ``data`` block in the wire form. */
export interface Data {
  substrate_name: string;
  substrate_git_commit: string;
  datasets: DatasetRef[];
}

/**
 * Read-only view of an `EmpiricalProofRecord` parsed from the wire.
 * Field layout matches the Python emitter's ``_body()`` plus the
 * top-level ``signature`` and ``proof_id`` keys.
 */
export interface EmpiricalProofRecord {
  schema_version: string;
  identity: Identity;
  claim: Claim;
  preregistration: PreRegistration;
  data: Data;
  evidence: PillarEvidence[];
  verdict: Verdict;
  reproduction: Reproduction;
  provenance: Record<string, unknown>;
  signature: string;
  proof_id?: string;
  // Future minor-version additions land here without breaking
  // the reader.
  [extra: string]: unknown;
}

export class ProofParseError extends Error {
  constructor(message: string) {
    super(message);
    this.name = "ProofParseError";
  }
}

export class ProofSignatureError extends Error {
  constructor(message: string) {
    super(message);
    this.name = "ProofSignatureError";
  }
}

const REQUIRED_TOP_LEVEL_KEYS = [
  "schema_version",
  "identity",
  "claim",
  "preregistration",
  "data",
  "evidence",
  "verdict",
  "reproduction",
  "provenance",
  "signature",
] as const;

/**
 * Parse a wire-form JSON proof record into a typed object.
 *
 * Uses :func:`parseJsonPreservingInts` rather than ``JSON.parse`` so
 * that Python's int-vs-float distinction survives parsing. This is
 * load-bearing for signature verification: canonical bytes for an
 * int and a float of the same numeric value DIFFER (``30`` vs
 * ``30.0``), and the JS encoder must match the Python emitter
 * byte-for-byte.
 */
export function parseProof(json: string | Uint8Array): EmpiricalProofRecord {
  const text =
    typeof json === "string" ? json : new TextDecoder("utf-8").decode(json);
  let raw: unknown;
  try {
    raw = parseJsonPreservingInts(text);
  } catch (err) {
    throw new ProofParseError(`Not valid JSON: ${(err as Error).message}`);
  }
  if (raw === null || typeof raw !== "object" || Array.isArray(raw)) {
    throw new ProofParseError("Expected JSON object at top level");
  }
  const obj = raw as Record<string, unknown>;
  for (const req of REQUIRED_TOP_LEVEL_KEYS) {
    if (!(req in obj)) {
      throw new ProofParseError(`Missing required field: ${req}`);
    }
  }
  if (typeof obj.signature !== "string" || obj.signature.length === 0) {
    throw new ProofParseError("signature must be a non-empty string");
  }
  return obj as EmpiricalProofRecord;
}

/**
 * Reconstruct the body (sections 1–8) that the Python emitter signs.
 *
 * The Python reference signs the entire wire dict minus the wire-only
 * fields ``signature`` and ``proof_id`` — see
 * `EmpiricalProofRecord._body()`. We mirror that subtraction here:
 *
 * - Include every top-level key the wire form carries.
 * - Exclude ``signature`` (the field being verified) and ``proof_id``
 *   (derived from the body, not part of it).
 *
 * The canonical encoder will then sort keys per R3.
 *
 * This subtraction-style construction is forward-compatible: if a
 * future Python minor version adds a top-level field, JS verification
 * keeps working without code change as long as the new field is
 * included in the body alongside the existing ones.
 */
export function bodyForSigning(record: EmpiricalProofRecord): CanonicalValue {
  const body: Record<string, CanonicalValue> = {};
  for (const [k, v] of Object.entries(record)) {
    if (k === "signature" || k === "proof_id") continue;
    body[k] = v as CanonicalValue;
  }
  return body;
}

/**
 * Verify an `EmpiricalProofRecord`'s HMAC-SHA256 signature.
 *
 * @param record  The parsed proof record.
 * @param key     The signing key bytes — the same key the Python
 *                emitter used (typically the deployment's
 *                ``DEFAULT_SIGN_KEY``).
 * @returns       ``true`` iff the signature matches the canonical
 *                body bytes under ``key``.
 *
 * Comparison is constant-time via ``crypto.timingSafeEqual`` to
 * preclude timing-side-channel signal in adversarial settings.
 */
export function verifySignature(
  record: EmpiricalProofRecord,
  key: Uint8Array,
): boolean {
  let bodyBytes: Uint8Array;
  try {
    bodyBytes = canonicalBytes(bodyForSigning(record));
  } catch (err) {
    if (err instanceof CanonicalFormError) {
      throw new ProofSignatureError(
        `Cannot canonicalize body for verification: ${err.message}`,
      );
    }
    throw err;
  }
  const expectedHex = createHmac("sha256", key)
    .update(bodyBytes)
    .digest("hex");

  if (
    typeof record.signature !== "string" ||
    record.signature.length !== expectedHex.length
  ) {
    return false;
  }
  // Convert both to bytes for timing-safe comparison.
  const actual = Buffer.from(record.signature, "utf-8");
  const expected = Buffer.from(expectedHex, "utf-8");
  return timingSafeEqual(actual, expected);
}

/** Compute the content-addressed proof_id (SHA-256 over the body). */
export function computeProofId(record: EmpiricalProofRecord): string {
  const bodyBytes = canonicalBytes(bodyForSigning(record));
  return createHash("sha256").update(bodyBytes).digest("hex");
}
