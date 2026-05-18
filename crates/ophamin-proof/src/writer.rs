#![allow(clippy::approx_constant)]
// ^ ``3.14159`` appears in tests below as a deliberate near-PI
// fixture value matching the Python cross-language fixture exactly.
// Clippy's ``approx_constant`` lint would flag it; allow locally
// rather than diverge from the fixture.

//! Canonical-form WRITER (RFC 0002 Phase E9 write-side).
//!
//! Where the rest of the crate is a read-only verifier of
//! Python-emitted records, this module lets native Rust code
//! PRODUCE canonical bytes byte-for-byte equivalent to what
//! Python's `json.dumps(obj, sort_keys=True, separators=(",", ":"),
//! default=str)` would produce on the same input.
//!
//! Cross-language emit means: a Rust-built `CanonicalValue` can be
//! canonicalized + signed in Rust, then verified in Python (or JS,
//! or any future port) without round-tripping through Python first.
//!
//! Two public entry points:
//!
//! - [`canonicalize_bytes`] — produce the canonical UTF-8 byte
//!   stream for a [`CanonicalValue`].
//! - [`sign_canonical`] — HMAC-SHA256 over those bytes; returns the
//!   hex digest a Python verifier will accept.
//!
//! The load-bearing primitive is [`python_repr`], which formats an
//! `f64` byte-for-byte equivalent to Python's `repr(float)`.

use hmac::{Hmac, Mac};
use sha2::Sha256;
use std::collections::BTreeMap;

use crate::ProofError;

type HmacSha256 = Hmac<Sha256>;

/// A value that can be canonicalized.
///
/// Unlike `serde_json::Value`, this enum carries a distinct
/// `Int(i64)` variant so the canonical form preserves Python's
/// `int` vs `float` distinction. A Python `int 30` and a Python
/// `float 30.0` produce different canonical bytes (`30` vs `30.0`)
/// → different HMAC digests; the type system must keep them apart.
#[derive(Debug, Clone, PartialEq)]
pub enum CanonicalValue {
    Null,
    Bool(bool),
    Int(i64),
    Float(f64),
    String(String),
    Array(Vec<CanonicalValue>),
    Object(BTreeMap<String, CanonicalValue>),
}

impl CanonicalValue {
    /// Convenience constructor for an empty object.
    #[must_use]
    pub fn object() -> Self {
        Self::Object(BTreeMap::new())
    }

    /// Convenience constructor for an empty array.
    #[must_use]
    pub fn array() -> Self {
        Self::Array(Vec::new())
    }

    /// Insert a key-value pair if `self` is an `Object`, no-op otherwise.
    ///
    /// Returns `self` for chained construction.
    pub fn insert(&mut self, key: impl Into<String>, value: CanonicalValue) -> &mut Self {
        if let Self::Object(map) = self {
            map.insert(key.into(), value);
        }
        self
    }

    /// Push a value if `self` is an `Array`, no-op otherwise.
    pub fn push(&mut self, value: CanonicalValue) -> &mut Self {
        if let Self::Array(arr) = self {
            arr.push(value);
        }
        self
    }
}

/// Convert any value supporting `Into<CanonicalValue>` into one.
impl From<bool> for CanonicalValue {
    fn from(b: bool) -> Self {
        Self::Bool(b)
    }
}
impl From<i64> for CanonicalValue {
    fn from(i: i64) -> Self {
        Self::Int(i)
    }
}
impl From<i32> for CanonicalValue {
    fn from(i: i32) -> Self {
        Self::Int(i64::from(i))
    }
}
impl From<f64> for CanonicalValue {
    fn from(f: f64) -> Self {
        Self::Float(f)
    }
}
impl From<String> for CanonicalValue {
    fn from(s: String) -> Self {
        Self::String(s)
    }
}
impl From<&str> for CanonicalValue {
    fn from(s: &str) -> Self {
        Self::String(s.to_string())
    }
}

// ---------------------------------------------------------------------------
// python_repr — byte-equivalent to Python's repr(float)
// ---------------------------------------------------------------------------

/// Format an `f64` the way Python's `repr(float)` formats it.
///
/// Rules (matching `SCHEMAS.md` R5):
///
/// - 0.0 → `"0.0"`; -0.0 → `"-0.0"` (negative-zero preserved).
/// - Fixed-point form when `1e-4 ≤ |x| < 1e16`. Trailing `.0` is
///   always present (distinguishes float from int).
/// - Scientific form otherwise: `M.NNNeSEE` where the mantissa is
///   the shortest-round-trip decimal, `S` is `+` or `-`, and `EE`
///   is at least 2 digits (zero-padded for negative exponents,
///   not extra-padded for larger positive ones — `1e+100`).
///
/// Errors:
///
/// - `ProofError::NonPortableValue` on `NaN`, `±Infinity` per
///   `SCHEMAS.md` R10 (the canonical form refuses these for
///   cross-language portability).
pub fn python_repr(f: f64) -> Result<String, ProofError> {
    if f.is_nan() {
        return Err(ProofError::NonPortableValue("NaN"));
    }
    if f.is_infinite() {
        return Err(ProofError::NonPortableValue("Infinity"));
    }
    // Handle zero / negative zero explicitly; `0.0.is_sign_negative()`
    // returns `true` for `-0.0` (per IEEE 754).
    if f == 0.0 {
        return Ok(if f.is_sign_negative() { "-0.0".to_string() } else { "0.0".to_string() });
    }

    let abs = f.abs();
    if (1e-4..1e16).contains(&abs) {
        // Fixed-point. Rust's `f64::to_string()` uses Ryū's
        // shortest-round-trip algorithm; it always returns
        // fixed-point in this range (Rust only switches to
        // scientific at extreme magnitudes via `{:e}`).
        let s = f.to_string();
        // Rust's `{}` formatter on integer-valued floats returns
        // "1234" without a decimal; Python's repr returns "1234.0".
        // Append `.0` if missing.
        if s.contains('.') {
            Ok(s)
        } else {
            Ok(format!("{s}.0"))
        }
    } else {
        // Scientific. Rust's `{:e}` gives `1e20` / `1e-7`;
        // Python's repr gives `1e+20` / `1e-07`. Reformat the
        // exponent to Python style.
        reformat_exponent_to_python(&format!("{f:e}"))
    }
}

/// Reformat a Rust `{:e}` exponent to Python's `repr` exponent style:
/// add an explicit `+` for positive exponents; zero-pad negative
/// exponents to at least 2 digits.
fn reformat_exponent_to_python(s: &str) -> Result<String, ProofError> {
    let e_idx = s
        .find('e')
        .ok_or(ProofError::NonPortableValue("missing exponent marker"))?;
    let mantissa = &s[..e_idx];
    let exp_part = &s[e_idx + 1..];
    if exp_part.is_empty() {
        return Err(ProofError::NonPortableValue("empty exponent"));
    }
    let (sign_char, digits) = match exp_part.as_bytes()[0] {
        b'+' => ('+', &exp_part[1..]),
        b'-' => ('-', &exp_part[1..]),
        _ => ('+', exp_part),
    };
    if digits.is_empty() {
        return Err(ProofError::NonPortableValue("missing exponent digits"));
    }
    // Pad negative exponents to ≥ 2 digits. Positive exponents are
    // NOT zero-padded beyond their natural width — `1e+100` not
    // `1e+0100`. Python's rule: minimum 2 digits.
    let padded: String = if digits.len() < 2 {
        format!("0{digits}")
    } else {
        digits.to_string()
    };
    Ok(format!("{mantissa}e{sign_char}{padded}"))
}

// ---------------------------------------------------------------------------
// Canonicalization
// ---------------------------------------------------------------------------

/// Produce the canonical UTF-8 byte stream for a value.
///
/// Implements `SCHEMAS.md` R1–R11 byte-for-byte. A Rust-produced
/// canonical-byte stream is byte-equal to what Python's
/// `_canonical(obj)` would produce on the equivalent input.
pub fn canonicalize_bytes(value: &CanonicalValue) -> Result<Vec<u8>, ProofError> {
    let mut out = String::with_capacity(256);
    canonicalize_value_into(value, &mut out)?;
    Ok(out.into_bytes())
}

fn canonicalize_value_into(value: &CanonicalValue, out: &mut String) -> Result<(), ProofError> {
    match value {
        CanonicalValue::Null => {
            out.push_str("null");
            Ok(())
        }
        CanonicalValue::Bool(true) => {
            out.push_str("true");
            Ok(())
        }
        CanonicalValue::Bool(false) => {
            out.push_str("false");
            Ok(())
        }
        CanonicalValue::Int(i) => {
            // Rust's default integer formatting matches Python's
            // emission: no leading `+`, decimal digits, optional
            // leading `-` for negatives.
            out.push_str(&i.to_string());
            Ok(())
        }
        CanonicalValue::Float(f) => {
            out.push_str(&python_repr(*f)?);
            Ok(())
        }
        CanonicalValue::String(s) => {
            escape_string_into(s, out);
            Ok(())
        }
        CanonicalValue::Array(arr) => {
            out.push('[');
            for (i, item) in arr.iter().enumerate() {
                if i > 0 {
                    out.push(',');
                }
                canonicalize_value_into(item, out)?;
            }
            out.push(']');
            Ok(())
        }
        CanonicalValue::Object(map) => {
            // BTreeMap already iterates in sorted key order, which
            // matches Python's `sort_keys=True` since Python's
            // `str.__lt__` compares by Unicode code point and UTF-8
            // preserves the ordering of code points across the BMP.
            out.push('{');
            for (i, (key, val)) in map.iter().enumerate() {
                if i > 0 {
                    out.push(',');
                }
                escape_string_into(key, out);
                out.push(':');
                canonicalize_value_into(val, out)?;
            }
            out.push('}');
            Ok(())
        }
    }
}

/// String escaping under Python's `ensure_ascii=True` semantics.
///
/// Same rules as `SCHEMAS.md` R6 — the read-side encoder in this
/// crate already implements them; duplicated here so the writer
/// is self-contained.
fn escape_string_into(s: &str, out: &mut String) {
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
                out.push_str(&format!("\\u{code:04x}"));
            }
            0x20..=0x7E => {
                out.push(ch);
            }
            0x7F..=0xFFFF => {
                out.push_str(&format!("\\u{code:04x}"));
            }
            _ => {
                // Supplementary plane: emit as UTF-16 surrogate pair.
                let n = code - 0x10000;
                let high = 0xD800 + (n >> 10);
                let low = 0xDC00 + (n & 0x3FF);
                out.push_str(&format!("\\u{high:04x}\\u{low:04x}"));
            }
        }
    }
    out.push('"');
}

// ---------------------------------------------------------------------------
// HMAC signing
// ---------------------------------------------------------------------------

/// HMAC-SHA256 over the canonical byte stream of `value` under `key`.
///
/// Returns the hex digest (lowercase, 64 chars) a Python verifier
/// (or the Rust read-side `verify_signature`, or the JS port) will
/// accept.
pub fn sign_canonical(value: &CanonicalValue, key: &[u8]) -> Result<String, ProofError> {
    let bytes = canonicalize_bytes(value)?;
    let mut mac = <HmacSha256 as Mac>::new_from_slice(key).map_err(|_| ProofError::HmacKey)?;
    mac.update(&bytes);
    Ok(hex::encode(mac.finalize().into_bytes()))
}

// ---------------------------------------------------------------------------
// Unit tests
// ---------------------------------------------------------------------------

#[cfg(test)]
mod tests {
    use super::*;

    // ----- python_repr -----------------------------------------------------

    #[test]
    fn python_repr_zero() {
        assert_eq!(python_repr(0.0).unwrap(), "0.0");
    }

    #[test]
    fn python_repr_negative_zero() {
        assert_eq!(python_repr(-0.0).unwrap(), "-0.0");
    }

    #[test]
    fn python_repr_fixed_point_simple() {
        assert_eq!(python_repr(3.14159).unwrap(), "3.14159");
        assert_eq!(python_repr(-2.5).unwrap(), "-2.5");
    }

    #[test]
    fn python_repr_integer_valued_float_keeps_trailing_dot_zero() {
        assert_eq!(python_repr(1.0).unwrap(), "1.0");
        assert_eq!(python_repr(1000.0).unwrap(), "1000.0");
    }

    #[test]
    fn python_repr_large_uses_scientific_with_plus() {
        assert_eq!(python_repr(1e20).unwrap(), "1e+20");
        assert_eq!(python_repr(1e16).unwrap(), "1e+16");
    }

    #[test]
    fn python_repr_small_uses_scientific_with_padded_negative_exponent() {
        assert_eq!(python_repr(1e-7).unwrap(), "1e-07");
        assert_eq!(python_repr(1e-10).unwrap(), "1e-10");
    }

    #[test]
    fn python_repr_three_digit_exponent_not_padded_further() {
        assert_eq!(python_repr(1e100).unwrap(), "1e+100");
        assert_eq!(python_repr(1e-100).unwrap(), "1e-100");
    }

    #[test]
    fn python_repr_rejects_nan() {
        assert!(python_repr(f64::NAN).is_err());
    }

    #[test]
    fn python_repr_rejects_infinity() {
        assert!(python_repr(f64::INFINITY).is_err());
        assert!(python_repr(f64::NEG_INFINITY).is_err());
    }

    // ----- canonicalize_bytes ---------------------------------------------

    #[test]
    fn canonical_null_true_false() {
        assert_eq!(canonicalize_bytes(&CanonicalValue::Null).unwrap(), b"null");
        assert_eq!(
            canonicalize_bytes(&CanonicalValue::Bool(true)).unwrap(),
            b"true"
        );
        assert_eq!(
            canonicalize_bytes(&CanonicalValue::Bool(false)).unwrap(),
            b"false"
        );
    }

    #[test]
    fn canonical_int_vs_float_distinct() {
        let int_30 = canonicalize_bytes(&CanonicalValue::Int(30)).unwrap();
        let float_30 = canonicalize_bytes(&CanonicalValue::Float(30.0)).unwrap();
        assert_eq!(int_30, b"30");
        assert_eq!(float_30, b"30.0");
        assert_ne!(int_30, float_30);
    }

    #[test]
    fn canonical_object_keys_sorted() {
        let mut map = BTreeMap::new();
        map.insert("z".to_string(), CanonicalValue::Int(1));
        map.insert("a".to_string(), CanonicalValue::Int(2));
        map.insert("m".to_string(), CanonicalValue::Int(3));
        let v = CanonicalValue::Object(map);
        let bytes = canonicalize_bytes(&v).unwrap();
        // BTreeMap iterates in sorted-by-key order = canonical order.
        assert_eq!(bytes, br#"{"a":2,"m":3,"z":1}"#);
    }

    #[test]
    fn canonical_array_preserves_order_no_whitespace() {
        let v = CanonicalValue::Array(vec![
            CanonicalValue::Int(1),
            CanonicalValue::Int(2),
            CanonicalValue::Int(3),
        ]);
        assert_eq!(canonicalize_bytes(&v).unwrap(), b"[1,2,3]");
    }

    #[test]
    fn canonical_string_escapes_non_ascii() {
        // Under ``ensure_ascii=True`` (R6), "café" emits as
        // "café" (the ASCII bytes spelling that escape sequence).
        // Note: byte string literals cannot contain non-ASCII chars
        // directly, so we assert against the escaped form.
        let v = CanonicalValue::String("café".to_string());
        assert_eq!(canonicalize_bytes(&v).unwrap(), b"\"caf\\u00e9\"");
    }

    #[test]
    fn canonical_string_escapes_supplementary_plane() {
        // Under R6's supplementary-plane rule, U+1F680 (🚀) emits as
        // the UTF-16 surrogate pair 🚀.
        let v = CanonicalValue::String("🚀".to_string());
        assert_eq!(canonicalize_bytes(&v).unwrap(), b"\"\\ud83d\\ude80\"");
    }

    #[test]
    fn canonical_string_named_control_escapes() {
        let v = CanonicalValue::String("a\nb\tc".to_string());
        assert_eq!(canonicalize_bytes(&v).unwrap(), br#""a\nb\tc""#);
    }

    // ----- sign_canonical -------------------------------------------------

    #[test]
    fn sign_returns_64_hex_chars() {
        let v = CanonicalValue::Object(BTreeMap::new());
        let sig = sign_canonical(&v, b"test-key").unwrap();
        assert_eq!(sig.len(), 64);
        assert!(sig.chars().all(|c| c.is_ascii_hexdigit()));
    }

    #[test]
    fn sign_changes_with_key() {
        let v = CanonicalValue::Bool(true);
        let s1 = sign_canonical(&v, b"key-a").unwrap();
        let s2 = sign_canonical(&v, b"key-b").unwrap();
        assert_ne!(s1, s2);
    }

    #[test]
    fn sign_stable_with_same_key_and_value() {
        let v = CanonicalValue::Int(42);
        let s1 = sign_canonical(&v, b"k").unwrap();
        let s2 = sign_canonical(&v, b"k").unwrap();
        assert_eq!(s1, s2);
    }
}
