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
                   prompt_tokens: int = 10, completion_tokens: int = 20,
                   reasoning_content: str | None = None,
                   finish_reason: str = "stop") -> bytes:
    """Build a fake OpenAI chat-completions response body.

    Set ``reasoning_content`` to simulate an LM Studio reasoning-tuned
    model (Gemma 4 reasoning, Qwen3.5 reasoning, etc.) whose output
    is routed through the reasoning channel instead of ``content``.
    """
    message: dict = {"role": "assistant", "content": content}
    if reasoning_content is not None:
        message["reasoning_content"] = reasoning_content
    return json.dumps({
        "id": "chatcmpl-test",
        "model": model,
        "choices": [{
            "index": 0,
            "message": message,
            "finish_reason": finish_reason,
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
    # 0.63.2 — falsifiability guardrail agents
    assert pick_model("prereg_validator").tier == TaskTier.REASONING
    assert pick_model("confound_enumerator").tier == TaskTier.REASONING
    # 0.63.3 — scenario scaffold generator (CODER, like adapter_gen)
    assert pick_model("scenario_gen").tier == TaskTier.CODER


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


# ===========================================================================
# 0.63.1 — reasoning_content channel (LM Studio reasoning-tuned models)
# ===========================================================================
# Gemma 4 reasoning / Qwen3.5 reasoning / DeepSeek-R1 / GPT-OSS in
# reasoning-effort=high split their output into a separate
# `reasoning_content` field. The client exposes both channels; agents
# opt in to surfacing the reasoning stream via accept_reasoning=True.


def test_llm_response_reasoning_populated_when_present(mock_llm):
    """LLMResponse.reasoning gets set from message.reasoning_content."""
    client = LLMClient(base_url="http://localhost:1234/v1", api_key="")
    mock_llm(_mock_chat_body(
        content="",
        reasoning_content="Step 1: parse. Step 2: classify.",
        finish_reason="length",
    ))
    r = client.chat(model="m", messages=[{"role": "user", "content": "x"}])
    assert r.content == ""
    assert "Step 1" in r.reasoning


def test_llm_response_reasoning_defaults_empty_when_absent(mock_llm):
    """No reasoning_content in raw → LLMResponse.reasoning is empty string."""
    client = LLMClient(base_url="http://localhost:1234/v1", api_key="")
    mock_llm(_mock_chat_body(content="PONG"))
    r = client.chat(model="m", messages=[{"role": "user", "content": "x"}])
    assert r.content == "PONG"
    assert r.reasoning == ""


def test_llm_response_content_null_treated_as_empty(mock_llm):
    """Some reasoning models emit `content: null`; treat as ''."""
    client = LLMClient(base_url="http://localhost:1234/v1", api_key="")
    body = json.dumps({
        "id": "x", "model": "m",
        "choices": [{"index": 0, "message": {"role": "assistant",
                     "content": None, "reasoning_content": "ABC"},
                     "finish_reason": "length"}],
        "usage": {"prompt_tokens": 1, "completion_tokens": 1},
    }).encode("utf-8")
    mock_llm(body)
    r = client.chat(model="m", messages=[{"role": "user", "content": "x"}])
    assert r.content == ""
    assert r.reasoning == "ABC"


def test_proof_brief_accept_reasoning_false_keeps_empty(mock_llm, tmp_path):
    """Default accept_reasoning=False: empty content stays empty
    even if reasoning_content is populated. NO silent fallback."""
    from ophamin.agentic.agents.proof_brief import write_brief
    mock_llm(_mock_chat_body(
        content="",
        reasoning_content="Some analysis text the model produced.",
        finish_reason="length",
        model="qwen3.5-35b-a3b",
    ))
    proof = {
        "proof_id": "a" * 64,
        "claim": {"statement": "X >= 0", "threshold": {}},
        "verdict": {"outcome": "VALIDATED"},
        "evidence": [],
    }
    r = write_brief(proof, proofs_root=str(tmp_path))
    # Brief should be empty (no silent reasoning substitution)
    assert r.brief_markdown == ""


def test_proof_brief_accept_reasoning_true_surfaces_reasoning(mock_llm, tmp_path):
    """accept_reasoning=True + empty content + non-empty reasoning →
    brief = reasoning (prefixed with audit marker)."""
    from ophamin.agentic.agents.proof_brief import write_brief
    mock_llm(_mock_chat_body(
        content="",
        reasoning_content="The substrate validated the claim cleanly.",
        finish_reason="length",
        model="qwen3.5-35b-a3b",
    ))
    proof = {
        "proof_id": "a" * 64,
        "claim": {"statement": "X >= 0", "threshold": {}},
        "verdict": {"outcome": "VALIDATED"},
        "evidence": [],
    }
    r = write_brief(proof, proofs_root=str(tmp_path), accept_reasoning=True)
    assert "substrate validated" in r.brief_markdown
    # Audit marker tells the reader the content channel was empty.
    assert "reasoning_content" in r.brief_markdown


def test_proof_brief_accept_reasoning_unused_when_content_nonempty(mock_llm, tmp_path):
    """accept_reasoning=True but content is non-empty: use content,
    ignore reasoning. (Reasoning channel is the LAST RESORT, not
    a default override.)"""
    from ophamin.agentic.agents.proof_brief import write_brief
    mock_llm(_mock_chat_body(
        content="## Brief\n\nClean validation.",
        reasoning_content="Some chain-of-thought noise.",
        model="gpt-oss-120b",
    ))
    proof = {
        "proof_id": "a" * 64,
        "claim": {"statement": "X >= 0", "threshold": {}},
        "verdict": {"outcome": "VALIDATED"},
        "evidence": [],
    }
    r = write_brief(proof, proofs_root=str(tmp_path), accept_reasoning=True)
    assert "Clean validation" in r.brief_markdown
    # Audit marker NOT present (we read content, not reasoning).
    assert "reasoning_content" not in r.brief_markdown


def test_refuted_triage_accept_reasoning_extracts_json_from_reasoning(mock_llm, tmp_path):
    """accept_reasoning=True + empty content + reasoning containing
    a parsable JSON object with 'followups' → followups extracted."""
    from ophamin.agentic.agents.refuted_triage import propose_followups
    canned = json.dumps({
        "followups": [
            {"title": "via-reasoning", "claim_statement": "Z >= 1",
             "operationalization": "noop", "threshold_metric": "z",
             "threshold_op": ">=", "threshold_value": 1.0,
             "h0": "Z < 1", "h1": "Z >= 1", "rationale": "from reasoning"},
        ]
    })
    reasoning_blob = "Let me think...\n\nFinal answer:\n" + canned
    mock_llm(_mock_chat_body(
        content="",
        reasoning_content=reasoning_blob,
        finish_reason="length",
        model="qwen3.5-35b-a3b",
    ))
    proof = {
        "proof_id": "r" * 64,
        "claim": {"statement": "X >= 0", "threshold": {}},
        "verdict": {"outcome": "REFUTED", "observed": -0.5},
        "evidence": [],
    }
    r = propose_followups(proof, proofs_root=str(tmp_path), accept_reasoning=True)
    assert len(r.followups) == 1
    assert r.followups[0]["title"] == "via-reasoning"


def test_refuted_triage_accept_reasoning_false_ignores_reasoning(mock_llm, tmp_path):
    """Default accept_reasoning=False: empty content → empty followups,
    even when reasoning would parse cleanly."""
    from ophamin.agentic.agents.refuted_triage import propose_followups
    canned = json.dumps({"followups": [{"title": "would-have-worked",
                                         "claim_statement": "Z",
                                         "operationalization": "noop",
                                         "threshold_metric": "z",
                                         "threshold_op": ">=",
                                         "threshold_value": 1.0,
                                         "h0": "Z < 1", "h1": "Z >= 1",
                                         "rationale": "x"}]})
    mock_llm(_mock_chat_body(
        content="",
        reasoning_content=canned,
        finish_reason="length",
    ))
    proof = {"proof_id": "r" * 64, "claim": {}, "verdict": {"outcome": "REFUTED"},
             "evidence": []}
    r = propose_followups(proof, proofs_root=str(tmp_path))  # accept_reasoning defaults False
    assert r.followups == []


def test_refuted_triage_accept_reasoning_handles_unparsable_reasoning(mock_llm, tmp_path):
    """accept_reasoning=True + empty content + reasoning has no
    JSON object → followups stay empty, no crash."""
    from ophamin.agentic.agents.refuted_triage import propose_followups
    mock_llm(_mock_chat_body(
        content="",
        reasoning_content="No structured output here, just prose.",
        finish_reason="length",
    ))
    proof = {"proof_id": "r" * 64, "claim": {}, "verdict": {"outcome": "REFUTED"},
             "evidence": []}
    r = propose_followups(proof, proofs_root=str(tmp_path), accept_reasoning=True)
    assert r.followups == []


# ===========================================================================
# 0.63.1 — OPHAMIN_LLM_JSON_FORMAT runtime knob (LM Studio compat)
# ===========================================================================
# LM Studio rejects {"type":"json_object"} with HTTP 400 — only accepts
# json_schema or text. Different OpenAI-compatible servers have
# different opinions. The knob lets the operator pick.


def test_json_format_default_emits_json_object(mock_llm, monkeypatch):
    """Default (env unset): the on-wire response_format is the
    OpenAI canonical {"type":"json_object"}."""
    monkeypatch.delenv("OPHAMIN_LLM_JSON_FORMAT", raising=False)
    captured = {}
    def fake_urlopen(req, timeout=None):
        captured["body"] = json.loads(req.data.decode("utf-8"))
        return _MockOpenAIResponse(_mock_chat_body("{}"))
    import ophamin.agentic.client as mod
    monkeypatch.setattr(mod.urllib.request, "urlopen", fake_urlopen)
    client = LLMClient(base_url="http://localhost:1234/v1", api_key="")
    client.chat(model="m", messages=[{"role": "user", "content": "x"}],
                response_format="json_object")
    assert captured["body"]["response_format"] == {"type": "json_object"}


def test_json_format_text_for_lmstudio(mock_llm, monkeypatch):
    """OPHAMIN_LLM_JSON_FORMAT=text → emit {"type":"text"} (LM Studio
    accepts this shape but rejects json_object)."""
    monkeypatch.setenv("OPHAMIN_LLM_JSON_FORMAT", "text")
    captured = {}
    def fake_urlopen(req, timeout=None):
        captured["body"] = json.loads(req.data.decode("utf-8"))
        return _MockOpenAIResponse(_mock_chat_body("{}"))
    import ophamin.agentic.client as mod
    monkeypatch.setattr(mod.urllib.request, "urlopen", fake_urlopen)
    client = LLMClient(base_url="http://localhost:1234/v1", api_key="")
    client.chat(model="m", messages=[{"role": "user", "content": "x"}],
                response_format="json_object")
    assert captured["body"]["response_format"] == {"type": "text"}


def test_json_format_none_omits_response_format(mock_llm, monkeypatch):
    """OPHAMIN_LLM_JSON_FORMAT=none → response_format key is absent
    from the request payload entirely."""
    monkeypatch.setenv("OPHAMIN_LLM_JSON_FORMAT", "none")
    captured = {}
    def fake_urlopen(req, timeout=None):
        captured["body"] = json.loads(req.data.decode("utf-8"))
        return _MockOpenAIResponse(_mock_chat_body("{}"))
    import ophamin.agentic.client as mod
    monkeypatch.setattr(mod.urllib.request, "urlopen", fake_urlopen)
    client = LLMClient(base_url="http://localhost:1234/v1", api_key="")
    client.chat(model="m", messages=[{"role": "user", "content": "x"}],
                response_format="json_object")
    assert "response_format" not in captured["body"]


def test_json_format_invalid_raises(mock_llm, monkeypatch):
    """Unknown value rejected loud — no silent fallback to default."""
    monkeypatch.setenv("OPHAMIN_LLM_JSON_FORMAT", "yaml")
    client = LLMClient(base_url="http://localhost:1234/v1", api_key="")
    with pytest.raises(LLMClientError, match="OPHAMIN_LLM_JSON_FORMAT"):
        client.chat(model="m", messages=[{"role": "user", "content": "x"}],
                    response_format="json_object")


def test_json_format_unused_when_response_format_none(monkeypatch):
    """When the caller doesn't ask for JSON, the env knob is a no-op."""
    monkeypatch.setenv("OPHAMIN_LLM_JSON_FORMAT", "json_object")
    captured = {}
    def fake_urlopen(req, timeout=None):
        captured["body"] = json.loads(req.data.decode("utf-8"))
        return _MockOpenAIResponse(_mock_chat_body("hello"))
    import ophamin.agentic.client as mod
    monkeypatch.setattr(mod.urllib.request, "urlopen", fake_urlopen)
    client = LLMClient(base_url="http://localhost:1234/v1", api_key="")
    client.chat(model="m", messages=[{"role": "user", "content": "x"}])
    assert "response_format" not in captured["body"]


# ===========================================================================
# 0.63.2 — prereg_validator agent
# ===========================================================================

def _good_claim() -> dict:
    """A well-formed falsifiable claim."""
    return {
        "statement": "On a Family J Takwin trajectory, the Walker M4 conservation ratio R < 0.10",
        "operationalization": "For each M4 event, compute residual = total(i-1) - total(i); R = median|residual|/median|total| with 2000-resample bootstrap CI.",
        "threshold": {"metric": "walker_m4_conservation_ratio",
                      "comparator": "<", "value": 0.10,
                      "units": "dimensionless"},
        "h0": "R >= 0.10 — substrate fails to conserve at decision points.",
        "h1": "R < 0.10 — substrate conserves at decision points.",
    }


def test_prereg_validator_ok_path(mock_llm, tmp_path):
    """Happy path: well-formed claim → severity='ok'."""
    from ophamin.agentic.agents.prereg_validator import validate_preregistration
    canned = json.dumps({
        "severity": "ok",
        "is_falsifiable": True,
        "issues": [],
        "recommendations": [],
    })
    mock_llm(_mock_chat_body(canned, model="gpt-oss-120b"))
    r = validate_preregistration(_good_claim(), proofs_root=str(tmp_path))
    assert r.severity == "ok"
    assert r.is_falsifiable is True
    assert r.issues == []
    assert Path(r.call_record_path).exists()


def test_prereg_validator_block_path(mock_llm, tmp_path):
    """Block: model returns severity='block' + concrete issues."""
    from ophamin.agentic.agents.prereg_validator import validate_preregistration
    canned = json.dumps({
        "severity": "block",
        "is_falsifiable": False,
        "issues": [
            {"code": "THRESHOLD_VAGUE",
             "detail": "threshold.value is None"},
            {"code": "H0_H1_OVERLAP",
             "detail": "h0 and h1 both assert X >= 0"},
        ],
        "recommendations": [
            "set threshold.value to a numeric (e.g. 0.10)",
            "rewrite h0 as the logical negation of h1",
        ],
    })
    mock_llm(_mock_chat_body(canned, model="gpt-oss-120b"))
    r = validate_preregistration(
        {"statement": "X is good", "threshold": {"value": None},
         "h0": "X >= 0", "h1": "X >= 0"},
        proofs_root=str(tmp_path),
    )
    assert r.severity == "block"
    assert r.is_falsifiable is False
    assert len(r.issues) == 2
    assert r.issues[0]["code"] == "THRESHOLD_VAGUE"
    assert len(r.recommendations) == 2


def test_prereg_validator_accepts_proof_json_path(mock_llm, tmp_path):
    """Path input: when handed a proof.json, descend to the nested 'claim' key."""
    from ophamin.agentic.agents.prereg_validator import validate_preregistration
    proof_path = tmp_path / "proof.json"
    proof_path.write_text(json.dumps({
        "proof_id": "x" * 64,
        "claim": _good_claim(),
        "verdict": {"outcome": "VALIDATED"},
    }))
    canned = json.dumps({"severity": "ok", "is_falsifiable": True,
                          "issues": [], "recommendations": []})
    mock_llm(_mock_chat_body(canned, model="gpt-oss-120b"))
    r = validate_preregistration(proof_path, proofs_root=str(tmp_path))
    assert r.severity == "ok"


def test_prereg_validator_malformed_json_does_not_silently_pass(mock_llm, tmp_path):
    """Parse failure: severity='warn' + OTHER-code issue, never 'ok'.
    A silently-'ok' verdict on a malformed response would mask the
    failure from the operator."""
    from ophamin.agentic.agents.prereg_validator import validate_preregistration
    mock_llm(_mock_chat_body("not valid json", model="gpt-oss-120b"))
    r = validate_preregistration(_good_claim(), proofs_root=str(tmp_path))
    assert r.severity == "warn"
    assert r.is_falsifiable is False
    assert any(i.get("code") == "OTHER" for i in r.issues)


def test_prereg_validator_severity_clamped_to_known_values(mock_llm, tmp_path):
    """Unknown severity from model → clamp to 'warn' (defensive)."""
    from ophamin.agentic.agents.prereg_validator import validate_preregistration
    canned = json.dumps({
        "severity": "yellow",  # not in {ok, warn, block}
        "is_falsifiable": True,
        "issues": [],
        "recommendations": [],
    })
    mock_llm(_mock_chat_body(canned, model="gpt-oss-120b"))
    r = validate_preregistration(_good_claim(), proofs_root=str(tmp_path))
    assert r.severity == "warn"


def test_prereg_validator_audit_can_be_disabled(mock_llm, tmp_path):
    from ophamin.agentic.agents.prereg_validator import validate_preregistration
    canned = json.dumps({"severity": "ok", "is_falsifiable": True,
                          "issues": [], "recommendations": []})
    mock_llm(_mock_chat_body(canned, model="gpt-oss-120b"))
    r = validate_preregistration(_good_claim(), proofs_root=str(tmp_path),
                                  audit=False)
    assert r.call_record_path == ""
    assert not (tmp_path / "llm_calls").exists()


def test_prereg_validator_accept_reasoning_extracts_from_reasoning(mock_llm, tmp_path):
    """When content is empty + accept_reasoning=True + reasoning has
    a valid JSON object → parse from reasoning."""
    from ophamin.agentic.agents.prereg_validator import validate_preregistration
    canned = json.dumps({"severity": "warn", "is_falsifiable": True,
                          "issues": [{"code": "SCOPE_VAGUE", "detail": "x"}],
                          "recommendations": ["narrow the scope"]})
    mock_llm(_mock_chat_body(
        content="",
        reasoning_content="Thinking...\n" + canned,
        finish_reason="length",
    ))
    r = validate_preregistration(_good_claim(), proofs_root=str(tmp_path),
                                  accept_reasoning=True)
    assert r.severity == "warn"
    assert r.issues[0]["code"] == "SCOPE_VAGUE"


def test_prereg_validator_rejects_bad_input_type(tmp_path):
    """Inputs that are not dict / str / Path raise TypeError loudly."""
    from ophamin.agentic.agents.prereg_validator import validate_preregistration
    with pytest.raises(TypeError, match="unsupported claim input type"):
        validate_preregistration(12345, proofs_root=str(tmp_path))  # type: ignore[arg-type]


# ===========================================================================
# 0.63.2 — confound_enumerator agent
# ===========================================================================

def _validated_proof() -> dict:
    return {
        "proof_id": "v" * 64,
        "claim": {"statement": "Cycle recognition floor >= 0.94",
                  "operationalization": "Concept Jaccard across 5/5 re-exposure pairs",
                  "threshold": {"metric": "concept_jaccard_floor",
                                "comparator": ">=", "value": 0.94}},
        "verdict": {"outcome": "VALIDATED", "observed": 1.0,
                    "reasoning": "5/5 pairs at 1.0000"},
        "evidence": [{"pillar": "recognition", "statistic_name": "jaccard",
                      "statistic_value": 1.0}],
        "data": {"substrate_name": "kimera-swm",
                 "datasets": [{"name": "trajectory", "n_records": 5,
                                "kind": "takwin"}]},
    }


def test_confound_enumerator_returns_confounds(mock_llm, tmp_path):
    from ophamin.agentic.agents.confound_enumerator import enumerate_confounds
    canned = json.dumps({
        "confounds": [
            {"name": "deterministic-dispatch",
             "mechanism": "Same input → same output via cached hash; "
                          "Jaccard=1.0 with no real computation.",
             "disambiguating_test": "Re-run with PYTHONHASHSEED varying; "
                                    "expect Jaccard drop if dispatch is "
                                    "the source."},
            {"name": "recognition-cache-hit",
             "mechanism": "The substrate cached the concepts from the "
                          "first exposure and returned them verbatim.",
             "disambiguating_test": "Insert a 100-cycle gap before "
                                    "re-exposure; cache should expire."},
        ]
    })
    mock_llm(_mock_chat_body(canned, model="gpt-oss-120b"))
    r = enumerate_confounds(_validated_proof(), proofs_root=str(tmp_path))
    assert len(r.confounds) == 2
    assert r.confounds[0]["name"] == "deterministic-dispatch"
    assert "disambiguating_test" in r.confounds[1]
    assert Path(r.call_record_path).exists()


def test_confound_enumerator_n_max_truncates(mock_llm, tmp_path):
    from ophamin.agentic.agents.confound_enumerator import enumerate_confounds
    canned = json.dumps({
        "confounds": [
            {"name": f"c{i}", "mechanism": "m", "disambiguating_test": "t"}
            for i in range(7)
        ]
    })
    mock_llm(_mock_chat_body(canned, model="gpt-oss-120b"))
    r = enumerate_confounds(_validated_proof(), proofs_root=str(tmp_path),
                             n_max=3)
    assert len(r.confounds) == 3


def test_confound_enumerator_returns_empty_on_malformed_json(mock_llm, tmp_path):
    from ophamin.agentic.agents.confound_enumerator import enumerate_confounds
    mock_llm(_mock_chat_body("not valid json", model="gpt-oss-120b"))
    r = enumerate_confounds(_validated_proof(), proofs_root=str(tmp_path))
    assert r.confounds == []
    assert r.raw_response == "not valid json"


def test_confound_enumerator_accept_reasoning_extracts_from_reasoning(mock_llm, tmp_path):
    from ophamin.agentic.agents.confound_enumerator import enumerate_confounds
    canned = json.dumps({"confounds": [{"name": "via-reasoning",
                                          "mechanism": "x",
                                          "disambiguating_test": "y"}]})
    mock_llm(_mock_chat_body(
        content="",
        reasoning_content="Final:\n" + canned,
        finish_reason="length",
    ))
    r = enumerate_confounds(_validated_proof(), proofs_root=str(tmp_path),
                             accept_reasoning=True)
    assert len(r.confounds) == 1
    assert r.confounds[0]["name"] == "via-reasoning"


def test_confound_enumerator_accepts_path(mock_llm, tmp_path):
    from ophamin.agentic.agents.confound_enumerator import enumerate_confounds
    proof_path = tmp_path / "proof.json"
    proof_path.write_text(json.dumps(_validated_proof()))
    canned = json.dumps({"confounds": [{"name": "x",
                                          "mechanism": "y",
                                          "disambiguating_test": "z"}]})
    mock_llm(_mock_chat_body(canned, model="gpt-oss-120b"))
    r = enumerate_confounds(proof_path, proofs_root=str(tmp_path))
    assert len(r.confounds) == 1


def test_confound_enumerator_audit_can_be_disabled(mock_llm, tmp_path):
    from ophamin.agentic.agents.confound_enumerator import enumerate_confounds
    canned = json.dumps({"confounds": [{"name": "x", "mechanism": "y",
                                          "disambiguating_test": "z"}]})
    mock_llm(_mock_chat_body(canned, model="gpt-oss-120b"))
    r = enumerate_confounds(_validated_proof(), proofs_root=str(tmp_path),
                             audit=False)
    assert r.call_record_path == ""
    assert not (tmp_path / "llm_calls").exists()


def test_confound_enumerator_rejects_bad_input_type(tmp_path):
    from ophamin.agentic.agents.confound_enumerator import enumerate_confounds
    with pytest.raises(TypeError, match="unsupported proof input type"):
        enumerate_confounds(12345, proofs_root=str(tmp_path))  # type: ignore[arg-type]


# ===========================================================================
# 0.63.3 — scenario_gen agent
# ===========================================================================

_FAKE_SCENARIO_SOURCE = '''"""Test scenario emitted by the agent for hardening."""
from ophamin.measuring.proof import Claim, Threshold
from ophamin.measuring.scenarios.base import Scenario, ScenarioScore, Tier


class FakeScenario(Scenario):
    name = "fake-scenario"
    tier = Tier.SCIENTIFIC
    family = "test"
    goal = "test"
    explanation = "test"
    method = "test"
    falsification_consequence = "test"
    corpus_name = "test"
    target = "test"

    def __init__(self, *, threshold_value=0.5):
        if not 0.0 < threshold_value <= 1.0:
            raise ValueError("threshold_value out of range")
        self.threshold_value = float(threshold_value)

    def build_claim(self):
        return Claim(
            statement=f"M >= {self.threshold_value}",
            operationalization="compute M somehow",
            threshold=Threshold(metric="M", comparator=">=",
                                 value=self.threshold_value, units="x"),
            h0=f"M < {self.threshold_value}",
            h1=f"M >= {self.threshold_value}",
        )

    def score(self, cycle_results, records):
        raise NotImplementedError("operator: implement scoring")
'''


def test_scenario_gen_happy_path(mock_llm, tmp_path):
    from ophamin.agentic.agents.scenario_gen import generate
    mock_llm(_mock_chat_body(_FAKE_SCENARIO_SOURCE, model="qwen3-coder-next"))
    r = generate(
        name="fake-scenario", family="test",
        claim=_good_claim(),
        proofs_root=str(tmp_path),
    )
    assert "class FakeScenario" in r.source
    assert "raise NotImplementedError" in r.source
    assert "build_claim" in r.source
    assert Path(r.call_record_path).exists()


def test_scenario_gen_strips_markdown_fences(mock_llm, tmp_path):
    """If the model wraps source in ```python ... ``` despite instructions,
    the agent strips fences cleanly (existing pattern from adapter_gen)."""
    from ophamin.agentic.agents.scenario_gen import generate
    wrapped = "```python\n" + _FAKE_SCENARIO_SOURCE + "\n```"
    mock_llm(_mock_chat_body(wrapped, model="qwen3-coder-next"))
    r = generate(
        name="fake-scenario", family="test",
        claim=_good_claim(), proofs_root=str(tmp_path),
    )
    assert not r.source.startswith("```")
    assert 'raise NotImplementedError("operator: implement scoring")' in r.source
    assert "```" not in r.source


def test_scenario_gen_accepts_proof_json_path(mock_llm, tmp_path):
    """Path input: when handed a proof.json, descend to nested 'claim'."""
    from ophamin.agentic.agents.scenario_gen import generate
    proof_path = tmp_path / "proof.json"
    proof_path.write_text(json.dumps({
        "proof_id": "z" * 64,
        "claim": _good_claim(),
        "verdict": {"outcome": "VALIDATED"},
    }))
    mock_llm(_mock_chat_body(_FAKE_SCENARIO_SOURCE, model="qwen3-coder-next"))
    r = generate(name="from-proof", family="test", claim=proof_path,
                  proofs_root=str(tmp_path))
    assert "FakeScenario" in r.source


def test_scenario_gen_rejects_unknown_tier(tmp_path):
    """tier must be SCIENTIFIC or OPERATIONAL; anything else raises loud."""
    from ophamin.agentic.agents.scenario_gen import generate
    with pytest.raises(ValueError, match="tier must be one of"):
        generate(name="x", family="test", claim=_good_claim(),
                  tier="LEGENDARY", proofs_root=str(tmp_path))


def test_scenario_gen_rejects_bad_claim_input(tmp_path):
    from ophamin.agentic.agents.scenario_gen import generate
    with pytest.raises(TypeError, match="unsupported claim input type"):
        generate(name="x", family="test",
                  claim=12345,  # type: ignore[arg-type]
                  proofs_root=str(tmp_path))


def test_scenario_gen_audit_can_be_disabled(mock_llm, tmp_path):
    from ophamin.agentic.agents.scenario_gen import generate
    mock_llm(_mock_chat_body(_FAKE_SCENARIO_SOURCE, model="qwen3-coder-next"))
    r = generate(name="x", family="test", claim=_good_claim(),
                  audit=False, proofs_root=str(tmp_path))
    assert r.call_record_path == ""
    assert not (tmp_path / "llm_calls").exists()
