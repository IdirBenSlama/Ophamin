#![allow(clippy::approx_constant)]
// ^ ``3.14159`` below is deliberately used as a near-PI fixture
// value matching the Python cross-language fixture exactly so the
// canonical bytes shown by the example match what every other port
// produces. Clippy's ``approx_constant`` lint would suggest the
// constant; allow locally rather than diverge from the fixture.

//! Write-side example: build a canonical value tree from Rust,
//! canonicalize to bytes, and sign with HMAC-SHA256.
//!
//! Usage::
//!
//!     cargo run --example sign_value
//!
//! Demonstrates the consumer-facing write-side of
//! ``ophamin_proof``: construct a ``CanonicalValue`` tree using
//! the typed enum (``Object`` / ``Array`` / ``String`` / ``Int`` /
//! ``Float`` / ``Bool`` / ``Null``), canonicalize to bytes
//! matching the Python reference encoder byte-for-byte, then sign
//! under any application key. The resulting signature verifies
//! identically against the Python reference verifier.
//!
//! Exit code 0 = canonicalize + sign succeeded.

use ophamin_proof::{canonicalize_bytes, sign_canonical, CanonicalValue};

fn main() -> Result<(), Box<dyn std::error::Error>> {
    println!("# Write-side example — Rust crate ophamin-proof");
    println!();
    println!("Building a CanonicalValue tree in Rust and canonicalizing");
    println!("to byte-equivalent output the Python reference would");
    println!("produce on the same logical input.");
    println!();

    // === Step 1: build a tree using the typed enum ===
    println!("## Step 1: build the CanonicalValue tree");
    let mut measurement = CanonicalValue::object();
    measurement.insert("metric", CanonicalValue::Float(3.14159));
    measurement.insert("threshold", CanonicalValue::Float(0.05));
    measurement.insert("n_samples", CanonicalValue::Int(120));
    measurement.insert("verified", CanonicalValue::from(true));

    let mut samples = CanonicalValue::array();
    samples.push(CanonicalValue::Int(1));
    samples.push(CanonicalValue::Int(2));
    samples.push(CanonicalValue::Int(3));

    let mut root = CanonicalValue::object();
    root.insert("measurement", measurement);
    root.insert("samples", samples);
    root.insert("note", CanonicalValue::from("hello from Rust"));

    println!("  tree structure:");
    println!("    {{");
    println!("      \"measurement\": {{");
    println!("        \"metric\": 3.14159, \"threshold\": 0.05,");
    println!("        \"n_samples\": 120, \"verified\": true");
    println!("      }},");
    println!("      \"samples\": [1, 2, 3],");
    println!("      \"note\": \"hello from Rust\"");
    println!("    }}");

    // === Step 2: canonicalize to bytes ===
    println!("\n## Step 2: canonicalize to bytes");
    let canonical = canonicalize_bytes(&root)?;
    let canonical_text = std::str::from_utf8(&canonical)?;
    println!("  byte count:      {}", canonical.len());
    println!("  canonical bytes:");
    println!("    {}", canonical_text);
    println!();
    println!("  Note: integer values stay as `120` (NOT `120.0`).");
    println!("  Float values use Python's repr() formatting.");
    println!("  Object keys are sorted at every nesting level.");

    // === Step 3: sign under an application key ===
    println!("\n## Step 3: sign under an application key");
    let key: &[u8] = b"my-deployment-key";
    let signature = sign_canonical(&root, key)?;
    println!("  key:             my-deployment-key (32-byte SHA-256 derived internally)");
    println!("  HMAC-SHA256:     {}", signature);
    println!();
    println!("  This signature is byte-identical to what the Python");
    println!("  reference encoder produces on the same logical input.");
    println!("  The JS port's signCanonical produces the same bytes too.");

    println!("\n✓ Write-side example complete.");
    Ok(())
}
