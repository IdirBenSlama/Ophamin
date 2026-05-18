"""Concept walkthrough — CloudEvents 1.0 envelope (RFC 0002 Phase E9.5).

Demonstrates the **event-stream interop layer**: any signed
Ophamin proof can be wrapped in a CloudEvents 1.0 envelope for
transport through Kafka / EventBridge / Knative / any
CloudEvents-aware router, then unwrapped on the consumer side
with the signature surface preserved bit-for-bit.

The CloudEvents wrapper adds NO bytes to the proof itself. It
adds metadata (`id`, `source`, `type`, `specversion`,
`datacontenttype`, `time`) around the proof so event-stream
infrastructure can route on those headers without parsing the
payload. The proof inside the envelope verifies byte-identically
to the proof outside the envelope.

Run with::

    PYTHONPATH=src python examples/walkthrough_cloudevents.py

Safe to import; demo runs only as ``__main__``.
"""

from __future__ import annotations

import json
from pathlib import Path

from ophamin.cloudevents import unwrap, validate_envelope, wrap
from ophamin.interfaces._impls import verify_proof_impl


REPO_ROOT = Path(__file__).resolve().parent.parent
PROOFS_DIR = REPO_ROOT / "proofs" / "measurement_machinery"


def _find_shipped_proof() -> Path:
    """Return the first shipped signed-proof JSON we can find."""
    candidates = sorted(PROOFS_DIR.rglob("*.json"))
    if not candidates:
        raise SystemExit(
            "No shipped proof found under proofs/measurement_machinery/. "
            "Run `ophamin scenario list` first to ensure the framework is "
            "fully installed."
        )
    return candidates[0]


def main() -> None:
    print("# CloudEvents 1.0 envelope walkthrough — RFC 0002 Phase E9.5")
    print()
    print("Ophamin signed proofs are pure JSON dicts. To flow through")
    print("event-stream infrastructure (Kafka, EventBridge, Knative, NATS,")
    print("any CloudEvents-aware router), they need to wear a standard")
    print("envelope so consumers can route on metadata without parsing the")
    print("payload.")
    print()
    print("This walkthrough wraps a real shipped proof in a CloudEvents 1.0")
    print("envelope, simulates serialization to text (transit), then unwraps")
    print("on the receiver side and asserts the verification surface is")
    print("preserved byte-for-byte.")

    # === Step 1: load a shipped signed proof ===
    proof_path = _find_shipped_proof()
    print(f"\n## Step 1: load a real shipped proof")
    print()
    print(f"  file:  {proof_path.relative_to(REPO_ROOT)}")
    proof_dict = json.loads(proof_path.read_text())
    print(f"  scenario:    {proof_dict.get('scenario_name', '?')}")
    print(f"  proof_id:    {proof_dict['proof_id'][:32]}...")
    print(f"  signature:   {proof_dict['signature'][:16]}...")
    print(f"  verdict:     {proof_dict.get('verdict', {}).get('outcome', '?')}")

    # === Step 2: wrap in CloudEvents envelope ===
    print("\n## Step 2: wrap in CloudEvents 1.0 envelope")
    envelope = wrap(
        proof_dict,
        source="urn:ophamin:walkthrough:cloudevents",
    )
    validate_envelope(envelope)
    print()
    print(f"  specversion:      {envelope['specversion']}")
    print(f"  type:             {envelope['type']}")
    print(f"  source:           {envelope['source']}")
    print(f"  id:               {envelope['id'][:32]}...")
    print(f"  datacontenttype:  {envelope.get('datacontenttype', '?')}")
    print(f"  time:             {envelope.get('time', '?')}")
    print()
    print("  Note: envelope['id'] equals proof_dict['proof_id'] by design")
    print("  — that's the content-addressing guarantee that survives")
    print("  every transport.")
    assert envelope["id"] == proof_dict["proof_id"], (
        "envelope.id must equal proof_dict.proof_id"
    )

    # === Step 3: serialize for transit ===
    print("\n## Step 3: serialize for transit (over the wire)")
    envelope_text = json.dumps(envelope)
    print()
    print(f"  envelope bytes: {len(envelope_text.encode('utf-8'))}")
    print(f"  proof bytes:    {len(json.dumps(proof_dict).encode('utf-8'))}")
    overhead = len(envelope_text) - len(json.dumps(proof_dict))
    print(f"  envelope overhead: ~{overhead} bytes (metadata only)")
    print()
    print("  This is what a Kafka producer would publish:")
    print(f"    producer.send('ophamin.proofs', {envelope_text[:80]}...)")

    # === Step 4: unwrap on consumer side ===
    print("\n## Step 4: unwrap on the consumer side")
    envelope_recovered = json.loads(envelope_text)
    proof_recovered = unwrap(envelope_recovered)
    print()
    print(f"  recovered proof_id:  {proof_recovered['proof_id'][:32]}...")
    print(f"  recovered signature: {proof_recovered['signature'][:16]}...")
    print()
    print(f"  recovered == original: {proof_recovered == proof_dict}")
    assert proof_recovered == proof_dict, (
        "unwrap(wrap(x)) must be a no-op on the proof dict"
    )

    # === Step 5: verify the unwrapped proof ===
    print("\n## Step 5: verify the unwrapped proof")
    result = verify_proof_impl(json.dumps(proof_recovered))
    print()
    print(f"  verified:        {result['verified']}")
    print(f"  verdict.outcome: {result['verdict']['outcome']}")
    print(f"  proof_id:        {result['proof_id'][:32]}...")
    print()
    print("  The proof verifies byte-identically after wrap → transit →")
    print("  unwrap. The CloudEvents envelope adds metadata for routing")
    print("  but does not touch the signature surface.")

    # === Invariants — what we MUST pin ===
    assert result["verified"] is True, "CloudEvents wrap/unwrap must preserve verification"
    assert result["proof_id"] == proof_dict["proof_id"]
    assert envelope["specversion"] == "1.0"
    assert envelope["source"] == "urn:ophamin:walkthrough:cloudevents"
    assert envelope.get("datacontenttype", "").startswith("application/json")

    print("\n✓ CloudEvents walkthrough complete. Contract validated.")


if __name__ == "__main__":
    main()
