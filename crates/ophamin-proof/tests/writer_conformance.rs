//! Write-side conformance — Rust-produced canonical bytes match
//! Python's reference output byte-for-byte (RFC 0002 Phase E9 write-side).
//!
//! Where `fixture_conformance.rs` exercises the read path (parse +
//! canonicalize a JSON value → bytes match the committed fixture),
//! this file exercises the write path: build a `CanonicalValue`
//! tree from native Rust primitives, canonicalize it, and assert
//! the bytes match the same committed fixture.
//!
//! Why this matters: a Rust producer can now emit signed records
//! that Python (and JS, and any future port) can verify
//! cross-language. The fixtures lock in byte-equivalence.

use hmac::{Hmac, Mac};
use ophamin_proof::{canonicalize_bytes, sign_canonical, CanonicalValue};
use sha2::Sha256;
use std::collections::BTreeMap;
use std::fs;
use std::path::{Path, PathBuf};

type HmacSha256 = Hmac<Sha256>;

const TEST_KEY: &[u8] = b"ophamin-canonical-test-key-v1";

fn repo_root() -> PathBuf {
    let manifest_dir = PathBuf::from(env!("CARGO_MANIFEST_DIR"));
    manifest_dir
        .parent()
        .and_then(Path::parent)
        .map(Path::to_path_buf)
        .unwrap_or(manifest_dir)
}

fn fixtures_dir() -> PathBuf {
    repo_root().join("tests").join("canonical_form")
}

/// Build the `simple` fixture as a native CanonicalValue tree. Must
/// match the JSON input at `tests/canonical_form/simple.input.json`.
fn build_simple_fixture() -> CanonicalValue {
    let mut nested = BTreeMap::new();
    nested.insert("inner_a".to_string(), CanonicalValue::Int(1));
    nested.insert("inner_b".to_string(), CanonicalValue::Int(2));

    let mut root = BTreeMap::new();
    root.insert("a_integer".to_string(), CanonicalValue::Int(42));
    root.insert("m_float".to_string(), CanonicalValue::Float(3.14159));
    root.insert("w_null".to_string(), CanonicalValue::Null);
    root.insert("y_true".to_string(), CanonicalValue::Bool(true));
    root.insert("x_false".to_string(), CanonicalValue::Bool(false));
    root.insert("z_string".to_string(), CanonicalValue::String("ophamin".to_string()));
    root.insert(
        "list".to_string(),
        CanonicalValue::Array(vec![
            CanonicalValue::Int(1),
            CanonicalValue::Int(2),
            CanonicalValue::Int(3),
        ]),
    );
    root.insert("nested".to_string(), CanonicalValue::Object(nested));
    CanonicalValue::Object(root)
}

/// Build the `unicode` fixture as a native CanonicalValue tree.
fn build_unicode_fixture() -> CanonicalValue {
    let mut root = BTreeMap::new();
    root.insert(
        "ascii_only".to_string(),
        CanonicalValue::String("hello world".to_string()),
    );
    root.insert(
        "latin_supp".to_string(),
        CanonicalValue::String("café résumé".to_string()),
    );
    root.insert(
        "cyrillic".to_string(),
        CanonicalValue::String("привет".to_string()),
    );
    root.insert(
        "cjk".to_string(),
        CanonicalValue::String("字幕".to_string()),
    );
    root.insert(
        "emoji".to_string(),
        CanonicalValue::String("🚀".to_string()),
    );
    root.insert(
        "ключ".to_string(),
        CanonicalValue::String("value".to_string()),
    );
    CanonicalValue::Object(root)
}

/// Build the `numerical_edge` fixture as a native CanonicalValue tree.
fn build_numerical_edge_fixture() -> CanonicalValue {
    let mut root = BTreeMap::new();
    root.insert("zero_float".to_string(), CanonicalValue::Float(0.0));
    root.insert("neg_zero_float".to_string(), CanonicalValue::Float(-0.0));
    root.insert("zero_int".to_string(), CanonicalValue::Int(0));
    root.insert("large_pos".to_string(), CanonicalValue::Float(1e20));
    root.insert("small_neg_exp".to_string(), CanonicalValue::Float(1e-7));
    root.insert("pi".to_string(), CanonicalValue::Float(3.14159));
    root.insert("neg_value".to_string(), CanonicalValue::Float(-2.5));
    CanonicalValue::Object(root)
}

#[test]
fn write_simple_fixture_bytes_match_python() {
    let value = build_simple_fixture();
    let actual = canonicalize_bytes(&value).expect("canonicalize");
    let expected =
        fs::read(fixtures_dir().join("simple.canonical.bytes")).expect("read fixture");
    assert_eq!(
        actual,
        expected,
        "Rust write-side drift on simple fixture:\n  expected: {}\n  actual:   {}",
        String::from_utf8_lossy(&expected),
        String::from_utf8_lossy(&actual),
    );
}

#[test]
fn write_unicode_fixture_bytes_match_python() {
    let value = build_unicode_fixture();
    let actual = canonicalize_bytes(&value).expect("canonicalize");
    let expected =
        fs::read(fixtures_dir().join("unicode.canonical.bytes")).expect("read fixture");
    assert_eq!(
        actual,
        expected,
        "Rust write-side drift on unicode fixture:\n  expected: {}\n  actual:   {}",
        String::from_utf8_lossy(&expected),
        String::from_utf8_lossy(&actual),
    );
}

#[test]
fn write_numerical_edge_fixture_bytes_match_python() {
    let value = build_numerical_edge_fixture();
    let actual = canonicalize_bytes(&value).expect("canonicalize");
    let expected = fs::read(fixtures_dir().join("numerical_edge.canonical.bytes"))
        .expect("read fixture");
    assert_eq!(
        actual,
        expected,
        "Rust write-side drift on numerical_edge fixture:\n  expected: {}\n  actual:   {}",
        String::from_utf8_lossy(&expected),
        String::from_utf8_lossy(&actual),
    );
}

#[test]
fn write_simple_hmac_matches_committed_fixture() {
    let value = build_simple_fixture();
    let sig = sign_canonical(&value, TEST_KEY).expect("sign");
    let expected_hex = fs::read_to_string(fixtures_dir().join("simple.hmac_sha256.hex"))
        .expect("read hmac");
    assert_eq!(sig, expected_hex.trim());
}

#[test]
fn write_unicode_hmac_matches_committed_fixture() {
    let value = build_unicode_fixture();
    let sig = sign_canonical(&value, TEST_KEY).expect("sign");
    let expected_hex = fs::read_to_string(fixtures_dir().join("unicode.hmac_sha256.hex"))
        .expect("read hmac");
    assert_eq!(sig, expected_hex.trim());
}

#[test]
fn write_numerical_edge_hmac_matches_committed_fixture() {
    let value = build_numerical_edge_fixture();
    let sig = sign_canonical(&value, TEST_KEY).expect("sign");
    let expected_hex =
        fs::read_to_string(fixtures_dir().join("numerical_edge.hmac_sha256.hex"))
            .expect("read hmac");
    assert_eq!(sig, expected_hex.trim());
}

#[test]
fn write_then_verify_via_hmac_compare_is_constant_time_compatible() {
    // The sign function returns a hex string; the read-side
    // verify_signature compares with subtle::ConstantTimeEq.
    // A round-trip: emit via write-side, verify via read-side's
    // primitive (HMAC parity), confirms cross-port consistency.
    let value = build_simple_fixture();
    let actual_sig = sign_canonical(&value, TEST_KEY).expect("sign");
    let bytes = canonicalize_bytes(&value).expect("canonicalize");
    let mut mac = <HmacSha256 as Mac>::new_from_slice(TEST_KEY).unwrap();
    mac.update(&bytes);
    let expected = hex::encode(mac.finalize().into_bytes());
    assert_eq!(actual_sig, expected);
}
