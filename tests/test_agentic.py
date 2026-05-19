"""Tests for the 0.63.0 agentic layer.

Mocks the LLM HTTP calls at ``urllib.request.urlopen`` so tests are
deterministic and don't depend on a running Ollama/MLX-LM. Live
smoke against a real runtime is done out-of-band by the operator.

Pins:
- Client: base_url validation, timeout validation, runtime-hint
  inference, error envelopes (HTTPError → LLMClientError,
  URLError → LLMClientError), happy-path response parsing
- Models: pick_model routing per task, env overrides, fallback tier
- Audit: LLMCallRecord round-trip, signature verifies, persist
  lands at proofs/llm_calls/<date>/<short>.json, idempotent
- Agents: each agent runs end-to-end against a mocked LLM,
  produces expected output shape, writes an audit record (unless
  audit=False)
- Bundle-query: apply_filter pure-code path with synthetic trees
  + _sanitize_spec rejects bad inputs
"""

from __future__ import annotations

import io
import json
import os
from pathlib import Path

import pytest

from ophamin.agentic import (
    LLMClient,
    LLMClientError,
    LLMCallRecord,
    persist_call,
    pick_model,
    TaskTier,
)


# ===========================================================================
# Helpers — mock the LLM transport so tests are deterministic
# ===========================================================================

class _MockOpenAIResponse:
    """Pretends to be a urllib HTTPResponse for one mocked LLM call."""

    def __init__(self, body: bytes):
        self._body = body

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def read(self):
        return self._body


def _mock_chat_body(content: str, *, model: str = "test-model",
                   prompt_tokens: int = 10, completion_tokens: int = 20) -> bytes:
    """Build a fake OpenAI chat-completions response body."""
    return json.dumps({
        "id": "chatcmpl-test",
        "model": model,
        "choices": [{
            "index": 0,
            "message": {"role": "assistant", "content": content},
            "finish_reason": "stop",
        }],
        "usage": {
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "total_tokens": prompt_tokens + completion_tokens,
        },
    }).encode("utf-8")


@pytest.fixture
def mock_llm(monkeypatch):
    """Patch ophamin.agentic.client.urllib.request.urlopen to return
    canned responses. Yields a setter the test calls to queue the
    next response body."""
    queue = []

    def fake_urlopen(req, timeout=None):
        if not queue:
            raise RuntimeError("test forgot to queue an LLM response")
        return _MockOpenAIResponse(queue.pop(0))

    import ophamin.agentic.client as mod
    monkeypatch.setattr(mod.urllib.request, "urlopen", fake_urlopen)
    return queue.append


# ===========================================================================
# LLMClient
# ===========================================================================

def test_client_base_url_validation():
    with pytest.raises(ValueError, match="fully-qualified"):
        LLMClient(base_url="localhost:11434/v1")


def test_client_timeout_validation():
    with pytest.raises(ValueError, match="positive"):
        LLMClient(timeout_s=0)
    with pytest.raises(ValueError, match="positive"):
        LLMClient(timeout_s=-1)


def test_client_runtime_hint():
    assert LLMClient(base_url="http://localhost:11434/v1").runtime_hint == "ollama"
    assert LLMClient(base_url="http://localhost:8080/v1").runtime_hint == "mlx-lm"
    assert LLMClient(base_url="http://example.org/v1").runtime_hint == "unknown"


def test_client_strips_trailing_slash():
    c = LLMClient(base_url="http://localhost:11434/v1/")
    assert c.base_url == "http://localhost:11434/v1"


def test_client_chat_happy_path(mock_llm):
    mock_llm(_mock_chat_body("hello world", model="llama3.1:8b",
                              prompt_tokens=5, completion_tokens=2))
    c = LLMClient()
    r = c.chat(model="llama3.1:8b",
                messages=[{"role": "user", "content": "hi"}])
    assert r.content == "hello world"
    assert r.model == "llama3.1:8b"
    assert r.finish_reason == "stop"
    assert r.prompt_tokens == 5
    assert r.completion_tokens == 2
    assert r.latency_ms >= 0


def test_client_chat_includes_json_response_format(mock_llm, monkeypatch):
    """When response_format='json_object', payload must include the OpenAI
    shape."""
    captured = {}
    import ophamin.agentic.client as mod
    real_urlopen = mod.urllib.request.urlopen

    def capturing(req, timeout=None):
        captured["payload"] = json.loads(req.data.decode())
        return _MockOpenAIResponse(_mock_chat_body('{"x": 1}'))

    monkeypatch.setattr(mod.urllib.request, "urlopen", capturing)
    c = LLMClient()
    c.chat(model="t", messages=[{"role": "user", "content": "x"}],
            response_format="json_object")
    assert captured["payload"]["response_format"] == {"type": "json_object"}


def test_client_chat_loud_fail_on_http_error(monkeypatch):
    import urllib.error
    import ophamin.agentic.client as mod

    def raising(req, timeout=None):
        raise urllib.error.HTTPError(
            url=req.full_url, code=404, msg="Not Found",
            hdrs={}, fp=io.BytesIO(b'{"error":"model not found"}'),
        )

    monkeypatch.setattr(mod.urllib.request, "urlopen", raising)
    c = LLMClient()
    with pytest.raises(LLMClientError) as exc_info:
        c.chat(model="missing", messages=[{"role": "user", "content": "x"}])
    assert exc_info.value.status_code == 404
    assert "Not Found" in str(exc_info.value)


def test_client_chat_loud_fail_on_url_error(monkeypatch):
    import urllib.error
    import ophamin.agentic.client as mod

    def raising(req, timeout=None):
        raise urllib.error.URLError("Connection refused")

    monkeypatch.setattr(mod.urllib.request, "urlopen", raising)
    c = LLMClient()
    with pytest.raises(LLMClientError, match="transport failure"):
        c.chat(model="m", messages=[{"role": "user", "content": "x"}])


def test_client_chat_loud_fail_on_non_json(mock_llm):
    mock_llm(b"<html>oops</html>")
    c = LLMClient()
    with pytest.raises(LLMClientError, match="non-JSON"):
        c.chat(model="m", messages=[{"role": "user", "content": "x"}])


def test_client_chat_loud_fail_on_malformed_choices(mock_llm):
    mock_llm(b'{"id": "x", "model": "m", "choices": []}')
    c = LLMClient()
    with pytest.raises(LLMClientError, match="response shape unexpected"):
        c.chat(model="m", messages=[{"role": "user", "content": "x"}])


# ===========================================================================
# models.pick_model
# ===========================================================================

def test_pick_model_routes_per_task():
    assert pick_model("adapter_gen").tier == TaskTier.CODER
    assert pick_model("proof_brief").tier == TaskTier.WORKHORSE
    assert pick_model("refuted_triage").tier == TaskTier.REASONING
    assert pick_model("bundle_query").tier == TaskTier.FAST


def test_pick_model_unknown_task_falls_back_to_workhorse():
    assert pick_model("not-a-real-task").tier == TaskTier.WORKHORSE


def test_pick_model_env_override(monkeypatch):
    monkeypatch.setenv("OPHAMIN_AGENT_MODEL_ADAPTER_GEN", "custom-coder:1b")
    mc = pick_model("adapter_gen")
    assert mc.model == "custom-coder:1b"
    # Tier stays the same (it's the task's classification, not the model)
    assert mc.tier == TaskTier.CODER


def test_pick_model_max_tokens_override(monkeypatch):
    monkeypatch.setenv("OPHAMIN_AGENT_MAXTOK_BUNDLE_QUERY", "1024")
    assert pick_model("bundle_query").max_tokens == 1024


def test_pick_model_max_tokens_default_per_task():
    # adapter_gen defaults to 4096 (codegen is verbose)
    assert pick_model("adapter_gen").max_tokens == 4096
    # bundle_query defaults to 512 (JSON filter is small)
    assert pick_model("bundle_query").max_tokens == 512


# ===========================================================================
# audit.LLMCallRecord + persist_call
# ===========================================================================

def _sample_record() -> LLMCallRecord:
    return LLMCallRecord(
        task="bundle_query",
        runtime="ollama",
        model="llama3.1:8b",
        messages=[{"role": "user", "content": "x"}],
        max_tokens=512,
        temperature=0.0,
        response_format="json_object",
        content='{"tier": null}',
        finish_reason="stop",
        prompt_tokens=10,
        completion_tokens=5,
        latency_ms=42.0,
        ophamin_version="0.63.0",
    )


def test_record_call_id_is_content_addressed():
    r1 = _sample_record()
    r2 = _sample_record()
    # Same body → same call_id
    assert r1.call_id == r2.call_id
    assert len(r1.call_id) == 64  # SHA-256 hex


def test_record_sign_verify_round_trip():
    r = _sample_record()
    r.sign()
    assert r.verify_signature()
    # Tampering breaks
    r.content = "TAMPERED"
    assert not r.verify_signature()


def test_record_to_dict_includes_call_id_and_signature():
    r = _sample_record().sign()
    d = r.to_dict()
    assert "call_id" in d
    assert "signature" in d
    assert "created_at" in d
    assert d["task"] == "bundle_query"


def test_persist_call_writes_at_canonical_path(tmp_path):
    r = _sample_record()
    p = persist_call(r, proofs_root=tmp_path)
    # Path: <tmp>/llm_calls/<date>/<short>.json
    assert p.exists()
    parts = p.relative_to(tmp_path).parts
    assert parts[0] == "llm_calls"
    assert len(parts[1]) == 10  # YYYY-MM-DD
    assert parts[2].endswith(".json")
    # JSON round-trips
    data = json.loads(p.read_text())
    assert data["task"] == "bundle_query"
    assert data["signature"]


def test_persist_call_idempotent(tmp_path):
    r1 = _sample_record()
    r1.created_at = "2026-05-19T12:00:00+00:00"
    p1 = persist_call(r1, proofs_root=tmp_path)
    r2 = _sample_record()
    r2.created_at = "2026-05-19T12:00:00+00:00"
    p2 = persist_call(r2, proofs_root=tmp_path)
    # Same body + same created_at → same path → overwrites identically
    assert p1 == p2
    assert p1.read_bytes() == p2.read_bytes()


def test_persist_call_signs_if_unsigned(tmp_path):
    r = _sample_record()
    assert not r.signature
    p = persist_call(r, proofs_root=tmp_path)
    data = json.loads(p.read_text())
    assert data["signature"], "persist_call should sign if signature is empty"


# ===========================================================================
# Agents end-to-end (mocked LLM)
# ===========================================================================

def test_adapter_gen_agent_end_to_end(mock_llm, tmp_path, monkeypatch):
    """A canned adapter source from the mock LLM produces a sensible
    AdapterGenResult and writes an audit record."""
    from ophamin.agentic.agents.adapter_gen import generate

    canned_source = '''"""Adapter: test-foo."""
from pathlib import Path

ROOT = Path("/Volumes/Kaido/Foreign_Corpus/symbolic/test_foo")

def load() -> list[dict]:
    return []

def samples(meta, n=10):
    return []

def feature_summary(meta) -> str:
    return f"test-foo: {len(meta)} items"
'''
    mock_llm(_mock_chat_body(canned_source, model="qwen2.5-coder:32b"))

    result = generate(
        name="test_foo",
        description="A tiny test dataset for validation.",
        category="symbolic",
        proofs_root=str(tmp_path),
    )
    assert "def load()" in result.source
    assert "def samples" in result.source
    assert "def feature_summary" in result.source
    assert result.model == "qwen2.5-coder:32b"
    assert Path(result.call_record_path).exists()


def test_adapter_gen_strips_markdown_fences(mock_llm, tmp_path):
    """If the model wraps output in ```python ... ``` despite
    instructions, the agent strips fences."""
    from ophamin.agentic.agents.adapter_gen import generate
    fenced = "```python\ndef load(): pass\n```"
    mock_llm(_mock_chat_body(fenced))
    result = generate(
        name="x", description="x", category="y",
        proofs_root=str(tmp_path),
    )
    assert "```" not in result.source
    assert "def load()" in result.source


def test_proof_brief_agent_end_to_end(mock_llm, tmp_path):
    from ophamin.agentic.agents.proof_brief import write_brief
    mock_llm(_mock_chat_body(
        "## Brief\n\nThe scenario validated.",
        model="llama3.3:70b",
    ))
    proof = {
        "proof_id": "a" * 64,
        "claim": {"statement": "X >= 0", "threshold": {"metric": "x", "value": 0}},
        "verdict": {"outcome": "VALIDATED", "observed": 1.0, "reasoning": "yes"},
        "evidence": [],
    }
    r = write_brief(proof, proofs_root=str(tmp_path))
    assert "validated" in r.brief_markdown.lower()
    assert Path(r.call_record_path).exists()


def test_proof_brief_loads_from_path(mock_llm, tmp_path):
    from ophamin.agentic.agents.proof_brief import write_brief
    proof_path = tmp_path / "proof.json"
    proof_path.write_text(json.dumps({
        "proof_id": "b" * 64,
        "claim": {"statement": "X", "threshold": {}},
        "verdict": {"outcome": "REFUTED"},
        "evidence": [],
    }))
    mock_llm(_mock_chat_body("Refuted brief.", model="llama3.3:70b"))
    r = write_brief(proof_path, proofs_root=str(tmp_path))
    assert "Refuted" in r.brief_markdown


def test_refuted_triage_agent_end_to_end(mock_llm, tmp_path):
    from ophamin.agentic.agents.refuted_triage import propose_followups
    canned = json.dumps({
        "followups": [
            {"title": "test-followup-1",
             "claim_statement": "Y >= 1",
             "operationalization": "noop",
             "threshold_metric": "y", "threshold_op": ">=",
             "threshold_value": 1.0,
             "h0": "Y < 1", "h1": "Y >= 1",
             "rationale": "because"},
        ]
    })
    mock_llm(_mock_chat_body(canned, model="deepseek-r1:32b"))
    proof = {
        "proof_id": "c" * 64,
        "claim": {"statement": "X >= 0", "threshold": {"metric": "x", "value": 0}},
        "verdict": {"outcome": "REFUTED", "observed": -0.5},
        "evidence": [],
    }
    r = propose_followups(proof, proofs_root=str(tmp_path))
    assert len(r.followups) == 1
    assert r.followups[0]["title"] == "test-followup-1"
    assert Path(r.call_record_path).exists()


def test_refuted_triage_returns_empty_on_malformed_json(mock_llm, tmp_path):
    from ophamin.agentic.agents.refuted_triage import propose_followups
    mock_llm(_mock_chat_body("not valid json", model="deepseek-r1:32b"))
    r = propose_followups(
        {"proof_id": "x", "claim": {}, "verdict": {}, "evidence": []},
        proofs_root=str(tmp_path),
    )
    assert r.followups == []
    assert r.raw_response == "not valid json"


def test_bundle_query_agent_returns_spec(mock_llm, tmp_path):
    from ophamin.agentic.agents.bundle_query import parse_query
    canned = json.dumps({
        "tier": "scientific", "scenario": None, "verdict": "validated",
        "since": "2026-05-15", "until": None, "n_limit": 10,
    })
    mock_llm(_mock_chat_body(canned, model="llama3.1:8b"))
    r = parse_query("validated scientific proofs since may 15", proofs_root=str(tmp_path))
    assert r.filter_spec["tier"] == "scientific"
    assert r.filter_spec["verdict"] == "validated"
    assert r.filter_spec["since"] == "2026-05-15"
    assert r.filter_spec["n_limit"] == 10


def test_bundle_query_sanitizer_rejects_unknown_tier(mock_llm, tmp_path):
    from ophamin.agentic.agents.bundle_query import parse_query
    mock_llm(_mock_chat_body(json.dumps({
        "tier": "BOGUS_TIER", "verdict": "validated",
    }), model="llama3.1:8b"))
    r = parse_query("x", proofs_root=str(tmp_path))
    assert r.filter_spec["tier"] is None
    assert r.filter_spec["verdict"] == "validated"


def test_bundle_query_sanitizer_rejects_bad_date(mock_llm, tmp_path):
    from ophamin.agentic.agents.bundle_query import parse_query
    mock_llm(_mock_chat_body(json.dumps({
        "since": "yesterday", "until": "20-05-2026",
    }), model="llama3.1:8b"))
    r = parse_query("x", proofs_root=str(tmp_path))
    assert r.filter_spec["since"] is None
    assert r.filter_spec["until"] is None


def test_apply_filter_pure_path():
    from ophamin.agentic.agents.bundle_query import apply_filter
    tree = {
        "tiers": [
            {"tier": "scientific", "scenarios": [
                {"scenario": "alpha", "bundles": [
                    {"date": "2026-05-19", "verdict": "validated",
                     "short_hash": "abc", "path": "p1"},
                    {"date": "2026-05-10", "verdict": "refuted",
                     "short_hash": "def", "path": "p2"},
                ]},
            ]},
            {"tier": "engineering", "scenarios": [
                {"scenario": "beta", "bundles": [
                    {"date": "2026-05-19", "verdict": "validated",
                     "short_hash": "ghi", "path": "p3"},
                ]},
            ]},
        ],
    }
    spec = {"tier": "scientific", "scenario": None, "verdict": "validated",
            "since": "2026-05-15", "until": None, "n_limit": None}
    out = apply_filter(tree, spec)
    assert len(out) == 1
    assert out[0]["short_hash"] == "abc"
    # No filter = all 3
    spec_all = {"tier": None, "scenario": None, "verdict": None,
                "since": None, "until": None, "n_limit": None}
    assert len(apply_filter(tree, spec_all)) == 3
    # n_limit truncates
    spec_lim = dict(spec_all, n_limit=2)
    assert len(apply_filter(tree, spec_lim)) == 2


def test_agent_audit_can_be_disabled(mock_llm, tmp_path):
    from ophamin.agentic.agents.adapter_gen import generate
    mock_llm(_mock_chat_body("def load(): pass", model="qwen2.5-coder:32b"))
    result = generate(
        name="x", description="x", category="y",
        proofs_root=str(tmp_path),
        audit=False,
    )
    assert result.call_record_path == ""
    # No llm_calls dir created
    assert not (tmp_path / "llm_calls").exists()
