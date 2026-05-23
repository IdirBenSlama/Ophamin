"""Tests for the tool-scout agent — the LLM half of the *discover* stage.

The load-bearing guarantee: the scout proposes NAMES only. Even if the model
ignores the contract and emits a version/license, the agent strips it — a
fabricated fact can never reach the pipeline. Malformed names are dropped.

Offline — a fake client returns canned content; no runtime required.
"""

from __future__ import annotations

import json

import pytest

from ophamin.agentic.agents.tool_scout import (
    ToolScoutError,
    _clean_proposals,
    _extract_json_object,
    scout,
)
from ophamin.agentic.client import LLMResponse


class _FakeClient:
    runtime_hint = "fake"

    def __init__(self, content: str, reasoning: str = "") -> None:
        self._content = content
        self._reasoning = reasoning

    def chat(self, **kw) -> LLMResponse:
        return LLMResponse(
            content=self._content, model="fake-model", finish_reason="stop",
            prompt_tokens=1, completion_tokens=1, latency_ms=1.0, raw={},
            reasoning=self._reasoning,
        )


class TestExtract:
    def test_strips_markdown_fence(self):
        obj = _extract_json_object('```json\n{"candidates": []}\n```')
        assert obj == {"candidates": []}

    def test_extracts_object_amid_prose(self):
        obj = _extract_json_object('sure!\n{"candidates": [{"name": "x"}]}\ndone')
        assert obj["candidates"][0]["name"] == "x"

    def test_no_object_raises(self):
        with pytest.raises(ToolScoutError):
            _extract_json_object("no json here")


class TestClean:
    def test_strips_fabricated_metadata(self):
        obj = {"candidates": [
            {"name": "ruptures", "version": "9.9.9", "license": "MIT",
             "stars": 99999, "fit_note": "cpd"},
        ]}
        out = _clean_proposals(obj, n_max=6)
        assert out == ({"name": "ruptures", "import_name": "", "fit_note": "cpd"},)
        # the version/license/stars the model invented are gone
        assert "version" not in out[0]
        assert "license" not in out[0]

    def test_drops_invalid_names(self):
        obj = {"candidates": [
            {"name": "good-pkg"},
            {"name": "bad name!"},
            {"name": "evil; rm -rf /"},
        ]}
        out = _clean_proposals(obj, n_max=6)
        assert [c["name"] for c in out] == ["good-pkg"]

    def test_dedups_and_caps(self):
        obj = {"candidates": [
            {"name": "a"}, {"name": "a"}, {"name": "b"}, {"name": "c"},
        ]}
        out = _clean_proposals(obj, n_max=2)
        assert [c["name"] for c in out] == ["a", "b"]

    def test_missing_candidates_list_raises(self):
        with pytest.raises(ToolScoutError):
            _clean_proposals({"nope": 1}, n_max=6)


class TestScout:
    def test_proposes_and_grounds_hints(self):
        content = json.dumps({"candidates": [
            {"name": "ruptures", "import_name": "ruptures", "fit_note": "cpd",
             "version": "9.9.9", "license": "MIT"},
            {"name": "bad name!", "fit_note": "drop me"},
            {"name": "scikit-learn", "import_name": "sklearn", "fit_note": "ml"},
        ]})
        r = scout("detect change points", client=_FakeClient(content), audit=False)
        assert r.names == ["ruptures", "scikit-learn"]  # bad name dropped
        assert r.hints["scikit-learn"]["import_name"] == "sklearn"
        assert "version" not in r.proposed[0]  # fabricated metadata stripped
        assert r.call_record_path == ""  # audit off → no record written

    def test_empty_need_raises(self):
        with pytest.raises(ValueError):
            scout("   ", client=_FakeClient("{}"), audit=False)

    def test_accept_reasoning_fallback(self):
        content_empty = ""
        reasoning = json.dumps({"candidates": [{"name": "ruptures"}]})
        r = scout(
            "x", client=_FakeClient(content_empty, reasoning=reasoning),
            audit=False, accept_reasoning=True,
        )
        assert r.names == ["ruptures"]

    def test_unparseable_raises(self):
        with pytest.raises(ToolScoutError):
            scout("x", client=_FakeClient("not json at all"), audit=False)
