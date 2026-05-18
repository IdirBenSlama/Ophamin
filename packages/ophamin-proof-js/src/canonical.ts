/**
 * Canonical-form encoder — byte-equivalent to Python's
 * ``json.dumps(obj, sort_keys=True, separators=(",", ":"), default=str)``
 * with ``ensure_ascii=True`` (Python's default).
 *
 * This is the load-bearing primitive behind the JS/TS read API: an
 * Ophamin signed record's HMAC-SHA256 is computed over the canonical
 * UTF-8 bytes of its body. For a JS consumer to verify a Python-emitted
 * signature, this encoder MUST produce byte-equivalent output.
 *
 * The contract is normative in `SCHEMAS.md` §"Canonical-form
 * determinism (normative)" with eleven rules R1–R11. Three reference
 * fixtures under `tests/canonical_form/` of the main Ophamin repo are
 * the cross-language conformance suite.
 *
 * NaN, Infinity, and Python's `default=str` fallback are intentionally
 * out of scope — records using them are non-portable per the spec.
 * This encoder throws on NaN/Inf and on non-JSON-native input types.
 */

/**
 * Wrapper for integers that should canonicalize WITHOUT a trailing
 * ``.0`` — matching Python's ``int`` → JSON serialisation.
 *
 * Returned by :func:`parseJsonPreservingInts` for every numeric token
 * that lacked a decimal point + exponent in the source JSON. Construct
 * directly when authoring CanonicalValues in JS that should round-trip
 * Python ints exactly.
 */
export class PyInt {
  readonly value: number;

  constructor(value: number) {
    if (!Number.isInteger(value)) {
      throw new TypeError(
        `PyInt requires an integer value, got ${value}`,
      );
    }
    if (!Number.isSafeInteger(value)) {
      throw new TypeError(
        `PyInt requires a safe integer (|x| < 2^53), got ${value}`,
      );
    }
    this.value = value;
  }
}

export type CanonicalValue =
  | string
  | number
  | PyInt
  | boolean
  | null
  | CanonicalValue[]
  | { [key: string]: CanonicalValue };

export class CanonicalFormError extends Error {
  constructor(message: string) {
    super(message);
    this.name = "CanonicalFormError";
  }
}

/**
 * Format a number the way Python's ``repr(float)`` formats it.
 *
 * Python rules (verified empirically against CPython 3.10–3.14):
 *
 * - Integer-valued floats: emit ``N.0`` (trailing ``.0`` distinguishes
 *   float from int).
 * - Negative zero: emit ``-0.0`` (sign preserved).
 * - Fixed-point range: ``abs(x) < 1e16 && abs(x) >= 1e-4`` (and x != 0)
 *   → emit shortest-round-trip decimal in fixed-point form.
 * - Outside that range: emit scientific notation
 *   ``M.NNNeSEE`` where:
 *     - M is the shortest-round-trip mantissa (no leading zeros)
 *     - S is ``+`` for positive exponent, ``-`` for negative
 *     - EE is at least 2 digits, zero-padded; longer exponents
 *       continue without further padding (so ``1e+100`` not ``1e+0100``).
 *
 * @throws {CanonicalFormError} on NaN, ±Infinity, or unsupported number
 *         types.
 */
export function pythonRepr(num: number): string {
  if (Number.isNaN(num)) {
    throw new CanonicalFormError(
      "Canonical form does not support NaN — strict JSON forbids it. " +
        "See SCHEMAS.md R10."
    );
  }
  if (!Number.isFinite(num)) {
    throw new CanonicalFormError(
      "Canonical form does not support Infinity — strict JSON forbids it. " +
        "See SCHEMAS.md R10."
    );
  }
  // Zero cases (signed) — Python keeps "-0.0" distinct from "0.0".
  if (Object.is(num, -0)) return "-0.0";
  if (num === 0) return "0.0";

  // Range gate per Python's repr rules:
  //   fixed-point iff 1e-4 <= |x| < 1e16
  //   scientific otherwise
  //
  // Note: ``Number.isInteger`` cannot be used as the integer-vs-float
  // discriminator here, because a value like ``1e20`` is an integer
  // in IEEE-754 but Python's repr is still scientific. The range
  // gate is the only correct test.
  const abs = Math.abs(num);
  if (abs >= 1e-4 && abs < 1e16) {
    // Fixed-point form. Node's `.toString()` already does shortest-
    // round-trip via the IEEE-754 "shortest representation" rule.
    // JS only switches to scientific at 1e21 / 1e-7, so for the
    // range [1e-4, 1e16) JS's toString() output is fixed-point.
    const s = num.toString();
    if (s.includes("e") || s.includes("E")) {
      // Shouldn't happen in this range; guard anyway.
      throw new CanonicalFormError(
        `Internal: number ${num} formatted with exponent inside ` +
          `fixed-point range`
      );
    }
    // Python always carries a decimal point on float values. If JS
    // emitted an integer-shaped string (e.g. for 1000000.0 →
    // "1000000"), append ".0".
    return s.includes(".") ? s : `${s}.0`;
  }

  // Scientific form. JS's toExponential() with no argument gives
  // shortest round-trip. Reformat exponent to Python's style.
  return reformatExponentToPython(num.toExponential());
}

/**
 * Reformat a JS ``toExponential`` output to Python's ``repr`` style.
 *
 * JS:     ``1e+20``, ``1e-7``, ``1.5e+30``, ``-2e-100``
 * Python: ``1e+20``, ``1e-07``, ``1.5e+30``, ``-2e-100``
 *
 * Differences:
 * - JS uses 1-digit exponent for small magnitudes; Python pads to 2.
 * - Otherwise the formats agree.
 *
 * Mantissa: JS already gives shortest-round-trip without trailing
 * zeros; Python matches.
 */
function reformatExponentToPython(jsExp: string): string {
  const eIdx = jsExp.indexOf("e");
  if (eIdx === -1) {
    throw new CanonicalFormError(
      `Expected exponent form, got ${jsExp}`
    );
  }
  let mantissa = jsExp.slice(0, eIdx);
  const expPart = jsExp.slice(eIdx + 1);

  // Python always emits a decimal point on the mantissa? Actually no:
  // repr(1e20) is "1e+20" (NO decimal point on the mantissa). Match.
  // But repr(1.5e20) is "1.5e+20". So the mantissa just keeps whatever
  // shortest-round-trip form it has — same as JS.
  // One subtle case: JS toExponential may emit "1e+20" without a dot
  // for an integer-mantissa scientific value; same as Python.
  // No mantissa rewrite needed.

  const sign = expPart.startsWith("+") || expPart.startsWith("-")
    ? expPart[0]
    : "+";
  const expDigits = expPart.startsWith("+") || expPart.startsWith("-")
    ? expPart.slice(1)
    : expPart;

  // Pad to at least 2 digits (Python's rule).
  const paddedExpDigits =
    expDigits.length < 2 ? expDigits.padStart(2, "0") : expDigits;

  return `${mantissa}e${sign}${paddedExpDigits}`;
}

/**
 * Escape a string under Python's ``ensure_ascii=True`` semantics.
 *
 * Per SCHEMAS.md R6:
 * - `"` → `\"`, `\` → `\\`
 * - `\b`(BS), `\f`(FF), `\n`, `\r`, `\t` → their two-character escapes
 * - All other 0x00–0x1F → `\uXXXX` (lowercase hex, 4 digits)
 * - All code points ≥ 0x80 → `\uXXXX` (lowercase hex)
 * - Supplementary plane (≥ U+10000) → UTF-16 surrogate pair
 *   ``\uHHHH\uLLLL`` (JS strings ARE UTF-16 code units, so iterating
 *   by ``charCodeAt`` already yields surrogate pairs naturally)
 * - Printable ASCII (0x20–0x7E) except `"` and `\` → literal
 *
 * @returns the JSON string literal with surrounding double quotes.
 */
export function escapeString(s: string): string {
  let out = '"';
  for (let i = 0; i < s.length; i++) {
    const code = s.charCodeAt(i);
    if (code === 0x22) {
      out += '\\"';
    } else if (code === 0x5c) {
      out += "\\\\";
    } else if (code === 0x08) {
      out += "\\b";
    } else if (code === 0x09) {
      out += "\\t";
    } else if (code === 0x0a) {
      out += "\\n";
    } else if (code === 0x0c) {
      out += "\\f";
    } else if (code === 0x0d) {
      out += "\\r";
    } else if (code < 0x20 || code >= 0x7f) {
      // 0x00-0x1F other control chars + everything >= 0x7F (which
      // includes both DEL=0x7F and all non-ASCII code units, AND
      // both halves of any surrogate pair).
      out += "\\u" + code.toString(16).padStart(4, "0");
    } else {
      out += s[i];
    }
  }
  out += '"';
  return out;
}

/**
 * Encode any JSON-native value to its canonical UTF-8 byte string.
 *
 * Recursion strategy:
 * - null / true / false → literals
 * - number → ``pythonRepr``
 * - string → ``escapeString``
 * - Array → ``[item,...]`` no whitespace, element order preserved
 * - Object → ``{"key":value,...}`` with keys recursively sorted by
 *   the JS ``<`` operator (which is Unicode code-point order, matching
 *   Python's ``sort_keys=True``).
 *
 * Non-JSON-native values (Date, Map, Set, BigInt, undefined, functions)
 * throw.
 *
 * @throws {CanonicalFormError} on unsupported types.
 */
export function canonicalize(value: CanonicalValue): string {
  if (value === null) return "null";
  if (typeof value === "boolean") return value ? "true" : "false";
  if (value instanceof PyInt) return value.value.toString(10);
  if (typeof value === "number") return pythonRepr(value);
  if (typeof value === "string") return escapeString(value);
  if (Array.isArray(value)) {
    return "[" + value.map(canonicalize).join(",") + "]";
  }
  if (typeof value === "object") {
    // Filter out keys whose values are functions / undefined? Python
    // would not allow those in a JSON dict either, so reject loud.
    const entries = Object.entries(value);
    for (const [k, v] of entries) {
      if (typeof v === "undefined") {
        throw new CanonicalFormError(
          `Cannot canonicalize: key ${JSON.stringify(k)} has undefined value`
        );
      }
      if (typeof v === "function") {
        throw new CanonicalFormError(
          `Cannot canonicalize: key ${JSON.stringify(k)} has function value`
        );
      }
    }
    entries.sort(([a], [b]) => (a < b ? -1 : a > b ? 1 : 0));
    return (
      "{" +
      entries
        .map(([k, v]) => `${escapeString(k)}:${canonicalize(v)}`)
        .join(",") +
      "}"
    );
  }
  if (typeof value === "bigint") {
    throw new CanonicalFormError(
      "Cannot canonicalize: BigInt is not JSON-native. Convert to " +
        "string or number first."
    );
  }
  throw new CanonicalFormError(
    `Cannot canonicalize: unsupported type ${typeof value}`
  );
}

/**
 * Return the canonical UTF-8 bytes for a value. Use this when you need
 * to compute an HMAC or compare byte-for-byte with another encoder.
 */
export function canonicalBytes(value: CanonicalValue): Uint8Array {
  return new TextEncoder().encode(canonicalize(value));
}
