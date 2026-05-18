//! Cross-language canonical-form fixture conformance suite.
//!
//! Loads the three reference fixtures under
//! ``<repo>/tests/canonical_form/`` and asserts:
//!
//! - The Rust canonical-form encoder produces byte-equivalent output
//!   to the committed ``<stem>.canonical.bytes`` for each fixture.
//! - HMAC-SHA256 over the canonical bytes under the fixed test key
//!   matches the committed ``<stem>.hmac_sha256.hex``.
//! - Every Python-emitted signed proof under
//!   ``<repo>/proofs/measurement_machinery/`` verifies under the
//!   Python ``DEFAULT_SIGN_KEY``.
//!
//! Failure here means the Rust port has drifted from the Python
//! reference and the read-API contract is broken.

use hmac::{Hmac, Mac};
use ophamin_proof::{compute_proof_id, parse_proof, verify_signature};
use serde_json::Value;
use sha2::Sha256;
use std::fs;
use std::path::{Path, PathBuf};

type HmacSha256 = Hmac<Sha256>;

const FIXTURE_STEMS: &[&str] = &[
    "boundary_cases",
    "deeply_nested",
    "numerical_edge",
    "simple",
    "unicode",
];
const TEST_KEY: &[u8] = b"ophamin-canonical-test-key-v1";
const DEFAULT_SIGN_KEY: &[u8] = b"ophamin-scenario-proof-key";

fn repo_root() -> PathBuf {
    // CARGO_MANIFEST_DIR points at crates/ophamin-proof. The repo
    // root is two parents up.
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

fn proofs_dir() -> PathBuf {
    repo_root().join("proofs").join("measurement_machinery")
}

#[test]
fn fixture_canonical_bytes_match_python_reference() {
    for stem in FIXTURE_STEMS {
        let input_path = fixtures_dir().join(format!("{stem}.input.json"));
        let canon_path = fixtures_dir().join(format!("{stem}.canonical.bytes"));
        let input_text =
            fs::read_to_string(&input_path).unwrap_or_else(|e| panic!("read {input_path:?}: {e}"));
        let expected = fs::read(&canon_path).unwrap_or_else(|e| panic!("read {canon_path:?}: {e}"));

        // Parse the input as a serde_json::Value (with
        // arbitrary_precision via Cargo.toml feature) and canonicalize
        // via the crate's testing-export of the internal encoder.
        let value: Value = serde_json::from_str(&input_text).expect("parse input");
        let actual =
            ophamin_proof::testing::canonicalize_value_to_bytes(&value).expect("canonicalize");

        assert_eq!(
            actual,
            expected,
            "canonical-form drift on {stem}:\n  expected: {}\n  actual:   {}",
            String::from_utf8_lossy(&expected),
            String::from_utf8_lossy(&actual),
        );
    }
}

#[test]
fn fixture_hmac_matches_python_reference() {
    for stem in FIXTURE_STEMS {
        let canon_path = fixtures_dir().join(format!("{stem}.canonical.bytes"));
        let hmac_path = fixtures_dir().join(format!("{stem}.hmac_sha256.hex"));

        let canonical = fs::read(canon_path).expect("read canonical bytes");
        let expected_hex = fs::read_to_string(hmac_path)
            .expect("read hmac")
            .trim()
            .to_string();

        let mut mac = <HmacSha256 as Mac>::new_from_slice(TEST_KEY).unwrap();
        mac.update(&canonical);
        let actual_hex = hex::encode(mac.finalize().into_bytes());

        assert_eq!(
            actual_hex, expected_hex,
            "HMAC drift on {stem}: expected {expected_hex}, got {actual_hex}",
        );
    }
}

#[test]
fn shipped_proofs_verify_under_default_key() {
    let dir = proofs_dir();
    if !dir.exists() {
        panic!("expected proofs directory at {:?}", dir);
    }
    let mut verified = 0usize;
    for entry in fs::read_dir(&dir).expect("read proofs dir") {
        let entry = entry.expect("entry");
        let path = entry.path();
        if !path.is_dir() {
            continue;
        }
        for sub in fs::read_dir(path).expect("read subdir") {
            let sub = sub.expect("subentry");
            let p = sub.path();
            if p.extension().is_some_and(|e| e == "json") {
                let text = fs::read_to_string(&p).expect("read proof");
                let record = parse_proof(&text).unwrap_or_else(|e| panic!("parse {p:?}: {e}"));
                let ok = verify_signature(&record, DEFAULT_SIGN_KEY)
                    .unwrap_or_else(|e| panic!("verify {p:?}: {e}"));
                assert!(
                    ok,
                    "signature mismatch on {:?} (signature prefix: {})",
                    p,
                    &record.signature[..16],
                );
                verified += 1;
            }
        }
    }
    assert!(
        verified >= 1,
        "no signed proofs verified; expected to find some under {:?}",
        dir
    );
}

#[test]
fn computed_proof_id_matches_filename_id_prefix() {
    let dir = proofs_dir();
    for entry in fs::read_dir(dir).expect("read proofs dir") {
        let path = entry.expect("entry").path();
        if !path.is_dir() {
            continue;
        }
        for sub in fs::read_dir(path).expect("read subdir") {
            let sub_path = sub.expect("subentry").path();
            if sub_path.extension().is_some_and(|e| e == "json") {
                let text = fs::read_to_string(&sub_path).expect("read");
                let record = parse_proof(&text).expect("parse");
                let proof_id = compute_proof_id(&record).expect("compute");
                let stem = sub_path.file_stem().and_then(|s| s.to_str()).expect("stem");
                let id16 = &proof_id[..16];
                assert!(
                    stem.contains(id16),
                    "computed proof_id prefix {id16} not in filename {stem}"
                );
                // One match is enough — return early.
                return;
            }
        }
    }
    panic!("no signed proofs found to test proof_id derivation");
}

#[test]
fn re_canonicalize_round_trip_idempotent() {
    // Parse the committed canonical bytes as JSON, re-canonicalize,
    // assert byte-equal. Property: canonicalization is idempotent on
    // already-canonical input.
    for stem in FIXTURE_STEMS {
        let canon_path = fixtures_dir().join(format!("{stem}.canonical.bytes"));
        let canonical = fs::read(canon_path).expect("read");
        let value: Value = serde_json::from_slice(&canonical).expect("parse");
        let re = ophamin_proof::testing::canonicalize_value_to_bytes(&value).expect("canonicalize");
        assert_eq!(
            re, canonical,
            "canonicalization not idempotent on fixture {stem}"
        );
    }
}
