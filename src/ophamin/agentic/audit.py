"""Signed audit record per LLM call — same discipline as scenario proofs.

Every agentic invocation persists an :class:`LLMCallRecord`:

    proofs/llm_calls/<YYYY-MM-DD>/<call_id-short>.json

The record is content-hashed (so two identical calls produce the
same ``call_id``) and HMAC-signed (so the operator can verify the
record wasn't tampered after-the-fact). The shape mirrors
:class:`ophamin.measuring.proof.EmpiricalProofRecord` minus the
falsifiable-claim machinery — an LLM call isn't a claim, it's a
witness.

Why per-day flat layout (not <tier>/<scenario>/<bundle>/):

- LLM calls pile up fast (hundreds per day during active development).
- The proofs/ tree shape is optimized for scenario-output browsing;
  LLM calls are operationally distinct (think audit log, not
  experimental record).
- Flat per-day means easy retention policy: ``rm -rf
  proofs/llm_calls/<old-date>/`` to prune.

When an agent's output ends up inside a scenario bundle (e.g.
``proof_brief`` writes the ``proof.md`` for a bundle), the bundle's
provenance graph carries a reference back to the LLM call's
``call_id``. The call record is the canonical audit trail.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import os
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


#: Default HMAC key for LLM call records. Distinct from
#: ``DEFAULT_SIGN_KEY`` so a leaked LLM-call key doesn't forge proofs.
#: Override via ``OPHAMIN_LLM_AUDIT_KEY`` env var in production.
DEFAULT_LLM_AUDIT_KEY = os.environ.get(
    "OPHAMIN_LLM_AUDIT_KEY", "ophamin-llm-call-audit-key",
).encode("utf-8")


def _canonical(obj: Any) -> str:
    """Deterministic JSON for hashing/signing.

    Same convention as ``ophamin.measuring.proof.record._canonical``:
    sorted keys, compact separators, ensure_ascii=False so unicode
    survives round-trip identically.
    """
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class LLMCallRecord:
    """One LLM invocation, content-addressed + HMAC-signed.

    ``call_id`` is SHA-256 of the canonical body (everything except
    signature + created_at). Two identical calls produce the same
    call_id → cache-deduplicable if desired. Signature is HMAC-SHA256
    over the same canonical body.
    """

    # Task identity
    task: str                   # e.g. "adapter_gen", "proof_brief"
    runtime: str                # "ollama" / "mlx-lm" / "unknown"

    # Request
    model: str
    messages: list[dict[str, str]]
    max_tokens: int
    temperature: float
    response_format: str        # "json_object" or "text"

    # Response
    content: str
    finish_reason: str
    prompt_tokens: int
    completion_tokens: int
    latency_ms: float

    # Audit
    ophamin_version: str = ""
    created_at: str = field(default_factory=_now)
    signature: str = ""

    # ----------------------------------------------------------------
    # Body + signing — same shape pattern as EmpiricalProofRecord
    # ----------------------------------------------------------------

    def _body(self) -> dict[str, Any]:
        """Sections 1-N (everything except created_at + signature)
        — the content-addressable + signable body."""
        return {
            "task": self.task,
            "runtime": self.runtime,
            "request": {
                "model": self.model,
                "messages": self.messages,
                "max_tokens": self.max_tokens,
                "temperature": self.temperature,
                "response_format": self.response_format,
            },
            "response": {
                "content": self.content,
                "finish_reason": self.finish_reason,
                "prompt_tokens": self.prompt_tokens,
                "completion_tokens": self.completion_tokens,
                "latency_ms": self.latency_ms,
            },
            "identity": {
                "ophamin_version": self.ophamin_version,
            },
        }

    @property
    def call_id(self) -> str:
        return hashlib.sha256(_canonical(self._body()).encode("utf-8")).hexdigest()

    def sign(self, key: bytes = DEFAULT_LLM_AUDIT_KEY) -> "LLMCallRecord":
        self.signature = hmac.new(
            key, _canonical(self._body()).encode("utf-8"), hashlib.sha256,
        ).hexdigest()
        return self

    def verify_signature(self, key: bytes = DEFAULT_LLM_AUDIT_KEY) -> bool:
        if not self.signature:
            return False
        expected = hmac.new(
            key, _canonical(self._body()).encode("utf-8"), hashlib.sha256,
        ).hexdigest()
        return hmac.compare_digest(self.signature, expected)

    def to_dict(self) -> dict[str, Any]:
        d = self._body()
        d["call_id"] = self.call_id
        d["created_at"] = self.created_at
        d["signature"] = self.signature
        return d


def persist_call(
    record: LLMCallRecord,
    *,
    proofs_root: str | Path = "proofs",
    sign_key: bytes = DEFAULT_LLM_AUDIT_KEY,
) -> Path:
    """Sign + persist an LLM call record. Returns the on-disk path.

    Layout:

        <proofs_root>/llm_calls/<YYYY-MM-DD>/<short-call-id>.json

    where ``<short-call-id>`` is the first 16 chars of the call_id.
    Two calls with the same body produce the same path → idempotent
    re-write of identical bytes.
    """
    if not record.signature:
        record.sign(sign_key)

    date_part = record.created_at[:10]  # YYYY-MM-DD
    short = record.call_id[:16]
    out_dir = Path(proofs_root) / "llm_calls" / date_part
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"{short}.json"
    out_path.write_text(
        json.dumps(record.to_dict(), indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    return out_path
