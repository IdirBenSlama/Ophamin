//! `ophamin-proof` — read-only verifier for Ophamin signed
//! empirical-proof records.
//!
//! Byte-equivalent to the Python reference canonical form per
//! [`SCHEMAS.md`](https://github.com/IdirBenSlama/Ophamin/blob/main/SCHEMAS.md)
//! §"Canonical-form determinism (normative)".
//!
//! # Quick start
//!
//! ```no_run
//! use ophamin_proof::{parse_proof, verify_signature};
//!
//! let text = std::fs::read_to_string("path/to/some-proof.json")?;
//! let proof = parse_proof(&text)?;
//! let key = b"ophamin-scenario-proof-key"; // deployment's signing key
//! assert!(verify_signature(&proof, key)?);
//! # Ok::<(), Box<dyn std::error::Error>>(())
//! ```
//!
//! # Design
//!
//! The crate is **read-only by design**. Records originate from the
//! Python reference emitter; the Rust port verifies them.
//!
//! The load-bearing primitive is `canonical_body_bytes`: it produces
//! the exact UTF-8 byte sequence Python signed over. To do that we:
//!
//! - Parse the wire form with `serde_json`'s `arbitrary_precision`
//!   feature, which preserves the lexical form of every number
//!   (so we don't lose Python's int-vs-float distinction).
//! - Walk the resulting `Value` tree depth-first, emitting bytes
//!   per the eleven rules R1–R11 of `SCHEMAS.md`:
//!     - sort object keys by their UTF-8 byte sequence
//!       (which matches Python's `<` on strings = Unicode
//!       code-point order)
//!     - no whitespace between tokens
//!     - escape strings under `ensure_ascii=True` semantics
//!       (every code point ≥ 0x80 becomes `\uXXXX`; supplementary-
//!       plane code points emit as UTF-16 surrogate pairs)
//!     - preserve the lexical form of numbers as parsed
//!
//! HMAC-SHA256 over those bytes under the deployment's signing key
//! is then compared to the record's `signature` field in constant
//! time via the `subtle` crate.

use hmac::{Hmac, Mac};
use serde::Deserialize;
use serde_json::Value;
use sha2::Sha256;
use std::collections::BTreeMap;
use subtle::ConstantTimeEq;
use thiserror::Error;

type HmacSha256 = Hmac<Sha256>;

// ---------------------------------------------------------------------------
// Error types
// ---------------------------------------------------------------------------

/// Errors raised by the verifier.
#[derive(Debug, Error)]
pub enum ProofError {
    #[error("JSON parse error: {0}")]
    Parse(#[from] serde_json::Error),

    #[error("expected JSON object at top level")]
    NotAnObject,

    #[error("missing required field: {0}")]
    MissingField(&'static str),

    #[error("signature must be a non-empty string")]
    BadSignature,

    #[error("HMAC key initialisation failed")]
    HmacKey,

    #[error("canonical form refuses {0}")]
    NonPortableValue(&'static str),
}

// ---------------------------------------------------------------------------
// Public record types (read-only views)
// ---------------------------------------------------------------------------

/// A parsed `EmpiricalProofRecord` from the wire form.
///
/// Fields use `serde_json::Value` so the crate doesn't have to mirror
/// every field of the Python dataclass tree — the read-API contract
/// is "verify the HMAC + expose structured data", not "re-typecheck
/// every field". For ergonomic typed access to specific fields,
/// callers can re-deserialize the relevant `Value` into their own
/// types via `serde_json::from_value`.
#[derive(Debug, Deserialize)]
pub struct EmpiricalProofRecord {
    pub schema_version: String,
    pub identity: Value,
    pub claim: Value,
    pub preregistration: Value,
    pub data: Value,
    pub evidence: Value,
    pub verdict: Value,
    pub reproduction: Value,
    pub provenance: Value,
    pub signature: String,
    /// Optional content-addressed identifier (SHA-256 over the body).
    /// Not part of the signed body — derived from it.
    #[serde(default)]
    pub proof_id: Option<String>,

    /// Any record-level fields a future Python minor version may
    /// add land here without breaking the reader.
    #[serde(flatten)]
    pub extras: BTreeMap<String, Value>,
}

// ---------------------------------------------------------------------------
// Public API
// ---------------------------------------------------------------------------

/// Parse a wire-form JSON proof record.
pub fn parse_proof(text: &str) -> Result<EmpiricalProofRecord, ProofError> {
    let record: EmpiricalProofRecord = serde_json::from_str(text)?;
    if record.signature.is_empty() {
        return Err(ProofError::BadSignature);
    }
    Ok(record)
}

/// Produce the canonical UTF-8 byte sequence Python signed over.
///
/// This is the body of the record — every field except `signature`
/// and `proof_id`, canonicalised per `SCHEMAS.md` R1–R11.
pub fn canonical_body_bytes(record: &EmpiricalProofRecord) -> Result<Vec<u8>, ProofError> {
    let body = build_body_value(record);
    let mut out = String::with_capacity(4096);
    canonicalize_value(&body, &mut out)?;
    Ok(out.into_bytes())
}

/// Verify the record's HMAC-SHA256 signature under `key`.
///
/// Returns `Ok(true)` iff the signature matches.
pub fn verify_signature(
    record: &EmpiricalProofRecord,
    key: &[u8],
) -> Result<bool, ProofError> {
    let body = canonical_body_bytes(record)?;
    let mut mac = <HmacSha256 as Mac>::new_from_slice(key).map_err(|_| ProofError::HmacKey)?;
    mac.update(&body);
    let expected = mac.finalize().into_bytes();
    let expected_hex = hex::encode(&expected);
    // Constant-time compare on the hex strings.
    Ok(record
        .signature
        .as_bytes()
        .ct_eq(expected_hex.as_bytes())
        .into())
}

/// Compute the content-addressed `proof_id` (SHA-256 of canonical body bytes).
pub fn compute_proof_id(record: &EmpiricalProofRecord) -> Result<String, ProofError> {
    use sha2::Digest;
    let body = canonical_body_bytes(record)?;
    let mut hasher = Sha256::new();
    hasher.update(&body);
    Ok(hex::encode(hasher.finalize()))
}

// ---------------------------------------------------------------------------
// Body assembly
// ---------------------------------------------------------------------------

fn build_body_value(record: &EmpiricalProofRecord) -> Value {
    // Construct the body dict in canonical key order. The canonical
    // encoder sorts at every depth anyway, but this keeps the
    // structure explicit.
    let mut map = serde_json::Map::new();
    map.insert("schema_version".to_string(), Value::String(record.schema_version.clone()));
    map.insert("identity".to_string(), record.identity.clone());
    map.insert("claim".to_string(), record.claim.clone());
    map.insert("preregistration".to_string(), record.preregistration.clone());
    map.insert("data".to_string(), record.data.clone());
    map.insert("evidence".to_string(), record.evidence.clone());
    map.insert("verdict".to_string(), record.verdict.clone());
    map.insert("reproduction".to_string(), record.reproduction.clone());
    map.insert("provenance".to_string(), record.provenance.clone());
    // Any extras a future emitter adds — include them too.
    for (k, v) in &record.extras {
        // Defensive: never include signature/proof_id even if they
        // somehow ended up in extras.
        if k == "signature" || k == "proof_id" {
            continue;
        }
        map.insert(k.clone(), v.clone());
    }
    Value::Object(map)
}

// ---------------------------------------------------------------------------
// Canonical-form encoder
// ---------------------------------------------------------------------------

fn canonicalize_value(value: &Value, out: &mut String) -> Result<(), ProofError> {
    match value {
        Value::Null => {
            out.push_str("null");
            Ok(())
        }
        Value::Bool(true) => {
            out.push_str("true");
            Ok(())
        }
        Value::Bool(false) => {
            out.push_str("false");
            Ok(())
        }
        Value::Number(n) => {
            // With ``serde_json``'s ``arbitrary_precision`` feature, the
            // Number's Display impl returns the lexical form the parser
            // saw. For Python-emitted records this IS the canonical
            // form, so emit verbatim — including the int-vs-float
            // distinction (R4 / R5) and the ``1e+20`` / ``1e-07``
            // exponent formatting Python produces.
            //
            // We reject any bare ``NaN`` / ``Infinity`` literals per
            // R10 since they break strict-JSON consumers.
            let s = n.to_string();
            if s == "NaN" || s == "Infinity" || s == "-Infinity" {
                return Err(ProofError::NonPortableValue("NaN/Infinity"));
            }
            out.push_str(&s);
            Ok(())
        }
        Value::String(s) => {
            escape_string(s, out);
            Ok(())
        }
        Value::Array(arr) => {
            out.push('[');
            for (i, item) in arr.iter().enumerate() {
                if i > 0 {
                    out.push(',');
                }
                canonicalize_value(item, out)?;
            }
            out.push(']');
            Ok(())
        }
        Value::Object(map) => {
            // Sort keys by their UTF-8 byte sequence, which matches
            // Python's ``sorted(keys)`` since Python's ``str.__lt__``
            // compares by Unicode code point and UTF-8 preserves the
            // ordering of code points across the BMP. (For
            // supplementary-plane code points UTF-8 and code-point
            // order also agree.)
            let mut keys: Vec<&String> = map.keys().collect();
            keys.sort_unstable_by(|a, b| a.as_bytes().cmp(b.as_bytes()));
            out.push('{');
            for (i, k) in keys.iter().enumerate() {
                if i > 0 {
                    out.push(',');
                }
                escape_string(k, out);
                out.push(':');
                canonicalize_value(&map[*k], out)?;
            }
            out.push('}');
            Ok(())
        }
    }
}

/// Escape a string under Python's ``ensure_ascii=True`` semantics.
///
/// Per SCHEMAS.md R6:
/// - `"` and `\` → escape pairs
/// - `\b` / `\f` / `\n` / `\r` / `\t` → named escapes
/// - Other 0x00..=0x1F → `\u00XX` (lowercase hex)
/// - Every code point ≥ 0x80 → `\uXXXX` (lowercase hex);
///   supplementary-plane code points emit as UTF-16 surrogate pair.
/// - 0x20..=0x7E (printable ASCII) except `"` and `\` → literal.
fn escape_string(s: &str, out: &mut String) {
    out.push('"');
    for ch in s.chars() {
        let code = ch as u32;
        match code {
            0x22 => out.push_str("\\\""),
            0x5C => out.push_str("\\\\"),
            0x08 => out.push_str("\\b"),
            0x09 => out.push_str("\\t"),
            0x0A => out.push_str("\\n"),
            0x0C => out.push_str("\\f"),
            0x0D => out.push_str("\\r"),
            0x00..=0x1F => {
                out.push_str(&format!("\\u{:04x}", code));
            }
            0x20..=0x7E => {
                // Printable ASCII (except " and \ handled above).
                out.push(ch);
            }
            0x7F..=0xFFFF => {
                // BMP code points (including DEL = 0x7F) → single
                // \uXXXX escape.
                out.push_str(&format!("\\u{:04x}", code));
            }
            _ => {
                // Supplementary plane: emit as UTF-16 surrogate pair.
                let n = code - 0x10000;
                let high = 0xD800 + (n >> 10);
                let low = 0xDC00 + (n & 0x3FF);
                out.push_str(&format!("\\u{:04x}\\u{:04x}", high, low));
            }
        }
    }
    out.push('"');
}

// ---------------------------------------------------------------------------
// Public ``testing`` module — exposes the internal canonical-form
// encoder so integration tests can verify byte-equivalence against
// committed fixtures without round-tripping through a fake
// ``EmpiricalProofRecord`` shell.
//
// The functions here are NOT part of the crate's stable API and may
// change between minor versions. They are documented so external
// language-port authors can use them as references.
// ---------------------------------------------------------------------------

#[doc(hidden)]
pub mod testing {
    use super::{canonicalize_value, ProofError};
    use serde_json::Value;

    /// Canonicalise a parsed JSON value to its UTF-8 byte stream
    /// per `SCHEMAS.md` R1–R11. Returns the bytes a Python emitter
    /// would have signed over for the same input.
    pub fn canonicalize_value_to_bytes(value: &Value) -> Result<Vec<u8>, ProofError> {
        let mut out = String::with_capacity(256);
        canonicalize_value(value, &mut out)?;
        Ok(out.into_bytes())
    }
}

// ---------------------------------------------------------------------------
// Unit tests for the encoder (fixture conformance lives in tests/)
// ---------------------------------------------------------------------------

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn null_true_false_lowercase() {
        let mut out = String::new();
        canonicalize_value(&Value::Null, &mut out).unwrap();
        canonicalize_value(&Value::Bool(true), &mut out).unwrap();
        canonicalize_value(&Value::Bool(false), &mut out).unwrap();
        assert_eq!(out, "nulltruefalse");
    }

    #[test]
    fn escape_string_basic_ascii() {
        let mut out = String::new();
        escape_string("hello", &mut out);
        assert_eq!(out, "\"hello\"");
    }

    #[test]
    fn escape_string_named_controls() {
        let mut out = String::new();
        escape_string("\n", &mut out);
        assert_eq!(out, "\"\\n\"");
        out.clear();
        escape_string("\t", &mut out);
        assert_eq!(out, "\"\\t\"");
    }

    #[test]
    fn escape_string_non_ascii_uses_uxxxx() {
        let mut out = String::new();
        escape_string("café", &mut out);
        assert_eq!(out, "\"caf\\u00e9\"");
    }

    #[test]
    fn escape_string_supplementary_uses_surrogate_pair() {
        let mut out = String::new();
        escape_string("🚀", &mut out);
        assert_eq!(out, "\"\\ud83d\\ude80\"");
    }

    #[test]
    fn keys_sorted_by_byte_order() {
        let v: Value = serde_json::from_str(r#"{"z":1,"a":2,"10":3,"2":4}"#).unwrap();
        let mut out = String::new();
        canonicalize_value(&v, &mut out).unwrap();
        // "10" < "2" < "a" < "z" by byte order (== code-point order).
        assert_eq!(out, "{\"10\":3,\"2\":4,\"a\":2,\"z\":1}");
    }

    #[test]
    fn array_preserves_order_no_whitespace() {
        let v: Value = serde_json::from_str("[1, 2, 3]").unwrap();
        let mut out = String::new();
        canonicalize_value(&v, &mut out).unwrap();
        assert_eq!(out, "[1,2,3]");
    }

    #[test]
    fn empty_object_and_array() {
        let v: Value = serde_json::from_str("{}").unwrap();
        let mut out = String::new();
        canonicalize_value(&v, &mut out).unwrap();
        assert_eq!(out, "{}");
        out.clear();
        let v: Value = serde_json::from_str("[]").unwrap();
        canonicalize_value(&v, &mut out).unwrap();
        assert_eq!(out, "[]");
    }
}
