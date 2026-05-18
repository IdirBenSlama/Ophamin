//! Read-side example: verify a Python-emitted signed proof from Rust.
//!
//! Usage::
//!
//!     cargo run --example verify_proof -- path/to/proof.json
//!
//! Or with the default — verify any shipped proof under
//! ``proofs/measurement_machinery/``::
//!
//!     cargo run --example verify_proof
//!
//! Demonstrates the consumer-facing surface of the ``ophamin-proof``
//! crate: ``parse_proof`` to load the JSON into a structured
//! ``EmpiricalProofRecord``, then ``verify_signature`` to check the
//! HMAC-SHA256 over the canonical body bytes under the documented
//! ``DEFAULT_SIGN_KEY``.
//!
//! Exit code 0 = verified. Exit code 1 = signature mismatch or
//! parse failure.

use ophamin_proof::{parse_proof, verify_signature};
use std::env;
use std::fs;
use std::path::PathBuf;
use std::process::ExitCode;

/// The HMAC key the Python emitter uses by default. Production
/// deployments rotate this via the ``ophamin schema validate
/// --key`` CLI argument or the ``Scenario.run(sign_key=...)``
/// kwarg.
const DEFAULT_SIGN_KEY: &[u8] = b"ophamin-scenario-proof-key";

fn locate_default_proof() -> Option<PathBuf> {
    // Walk repo root up from the example's working dir to find
    // ``proofs/measurement_machinery/`` and pick the first .json.
    let mut dir = env::current_dir().ok()?;
    for _ in 0..5 {
        let candidate = dir.join("proofs").join("measurement_machinery");
        if candidate.is_dir() {
            for entry in walkdir(&candidate) {
                if entry.extension().is_some_and(|e| e == "json") {
                    return Some(entry);
                }
            }
        }
        dir = dir.parent()?.to_path_buf();
    }
    None
}

fn walkdir(root: &std::path::Path) -> Vec<PathBuf> {
    let mut out = Vec::new();
    let mut stack = vec![root.to_path_buf()];
    while let Some(dir) = stack.pop() {
        let read = match fs::read_dir(&dir) {
            Ok(r) => r,
            Err(_) => continue,
        };
        for entry in read.flatten() {
            let path = entry.path();
            if path.is_dir() {
                stack.push(path);
            } else {
                out.push(path);
            }
        }
    }
    out.sort();
    out
}

fn main() -> ExitCode {
    let proof_path: PathBuf = match env::args().nth(1) {
        Some(arg) => PathBuf::from(arg),
        None => match locate_default_proof() {
            Some(p) => p,
            None => {
                eprintln!("Usage: cargo run --example verify_proof -- <path.json>");
                eprintln!(
                    "       (no path given; no shipped proof found under \
                     proofs/measurement_machinery/ either)"
                );
                return ExitCode::from(1);
            }
        },
    };

    println!("# Read-side example — Rust crate ophamin-proof");
    println!();
    println!("Loading: {}", proof_path.display());

    let text = match fs::read_to_string(&proof_path) {
        Ok(t) => t,
        Err(e) => {
            eprintln!("failed to read {}: {}", proof_path.display(), e);
            return ExitCode::from(1);
        }
    };

    let proof = match parse_proof(&text) {
        Ok(p) => p,
        Err(e) => {
            eprintln!("parse_proof failed: {}", e);
            return ExitCode::from(1);
        }
    };

    println!();
    println!("proof_id:        {}", proof.proof_id.as_deref().unwrap_or("(missing)"));
    println!("schema_version:  {}", &proof.schema_version);
    println!("signature:       {}...", &proof.signature[..16]);

    let verified = match verify_signature(&proof, DEFAULT_SIGN_KEY) {
        Ok(v) => v,
        Err(e) => {
            eprintln!("verify_signature failed: {}", e);
            return ExitCode::from(1);
        }
    };

    println!();
    if verified {
        println!("✓ signature verified under DEFAULT_SIGN_KEY");
        println!();
        println!("The crate has confirmed (byte-for-byte) that the");
        println!("canonical body of this proof was signed with the same key");
        println!("the Python emitter used. Cross-host integrity confirmed.");
        ExitCode::from(0)
    } else {
        eprintln!("✗ signature MISMATCH — proof body has drifted");
        ExitCode::from(1)
    }
}
