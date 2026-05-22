"""Tests for the result-diagnosis agent (Requirement 2 — agentic analysis).

The deterministic core (grounded prompt build + structured parse) is tested
with no model; the orchestration is tested with an injected fake client. No
live model is needed.
"""

from __future__ import annotations

import json

import pytest

from ophamin.agentic.client import LLMResponse
from ophamin.agentic.agents.result_diagnosis import (
    DiagnosisParseError,
    build_diagnosis_messages,
    diagnose,
    parse_diagnosis,
    summarize_proof,
)


# --- a fake client (no live model) ---------------------------------------

class _FakeClient:
    def __init__(self, content: str, *, runtime: str = "fake-runtime"):
        self._content = content
        self.runtime_hint = runtime
        self.seen: dict = {}

    def chat(self, *, model, messages, max_tokens, temperature):
        self.seen = {"model": model, "messages": messages,
                     "max_tokens": max_tokens, "temperature": temperature}
        return LLMResponse(
            content=self._content, model=model, finish_reason="stop",
            prompt_tokens=10, completion_tokens=20, latency_ms=1.5, raw={})


_VALID_DIAGNOSIS = json.dumps({
    "summary": "Recognition holds on real email.",
    "meaning": "Floor 0.86 > 0.80 threshold; memory-as-deformation generalises.",
    "construction_brief": "",
    "anomalies": ["worst pair lower than genesis baseline"],
    "confounds": ["email length not controlled"],
    "recommendations": ["measure more domains"],
    "next_question": "Does it hold on multilingual prose?",
})

_PROOF = {
    "proof_id": "abc123def456aaaa",
    "claim": {"statement": "Recognition holds across re-exposures.",
              "threshold": {"metric": "recognition_jaccard_floor",
                            "comparator": ">=", "value": 0.80}},
    "verdict": {"outcome": "VALIDATED", "observed_value": 0.8636,
                "reasoning": "floor 0.8636 over 24 pairs"},
    "evidence": [{"statistic_name": "recognition_jaccard_floor",
                  "statistic_value": 0.8636, "ci_low": None, "ci_high": None,
                  "p_value": None}],
}


class TestSummarizeProof:
    def test_grounds_in_real_fields(self):
        s = summarize_proof(_PROOF)
        assert s["proof_id"] == "abc123def456aaaa"
        assert s["verdict_outcome"] == "VALIDATED"
        assert s["verdict_observed"] == 0.8636
        assert s["threshold"]["value"] == 0.80
        assert s["evidence"][0]["statistic_value"] == 0.8636


class TestBuildMessages:
    def test_single_vs_set_framing(self):
        one = build_diagnosis_messages([summarize_proof(_PROOF)])
        assert "Diagnose this Ophamin proof" in one[1]["content"]
        many = build_diagnosis_messages([summarize_proof(_PROOF)] * 3)
        assert "set of 3" in many[1]["content"]
        # system prompt forbids re-deciding the verdict
        assert "NEVER re-decide the verdict" in one[0]["content"]


class TestParseDiagnosis:
    def test_plain_json(self):
        d = parse_diagnosis(_VALID_DIAGNOSIS)
        assert d["summary"].startswith("Recognition")
        assert d["anomalies"] == ["worst pair lower than genesis baseline"]

    def test_fenced_json(self):
        d = parse_diagnosis("```json\n" + _VALID_DIAGNOSIS + "\n```")
        assert d["next_question"].endswith("prose?")

    def test_json_with_surrounding_prose(self):
        d = parse_diagnosis("Here is the diagnosis:\n" + _VALID_DIAGNOSIS + "\nDone.")
        assert d["meaning"].startswith("Floor 0.86")

    def test_missing_keys_normalised(self):
        d = parse_diagnosis('{"summary": "x"}')
        assert d["summary"] == "x"
        assert d["anomalies"] == []          # missing list -> []
        assert d["construction_brief"] == "" # missing str -> ""
        assert set(d.keys()) == {
            "summary", "meaning", "construction_brief",
            "anomalies", "confounds", "recommendations", "next_question"}

    def test_no_json_raises_no_fallback(self):
        with pytest.raises(DiagnosisParseError):
            parse_diagnosis("I could not produce a diagnosis.")

    def test_broken_json_raises_with_raw(self):
        with pytest.raises(DiagnosisParseError) as ei:
            parse_diagnosis("{ this is : not json }")
        assert ei.value.raw  # raw response preserved for triage


class TestDiagnoseOrchestration:
    def test_single_proof_routes_to_scientific_tier(self):
        client = _FakeClient(_VALID_DIAGNOSIS)
        res = diagnose(_PROOF, client=client, audit=False)
        assert res.tier == "scientific"          # dedicated model, not general
        assert res.n_proofs == 1
        assert res.proof_ids == ("abc123def456aaaa",)
        assert res.diagnosis["summary"].startswith("Recognition")
        assert res.runtime == "fake-runtime"
        # the prompt the model saw was grounded in the real proof
        assert "0.8636" in json.dumps(client.seen["messages"])

    def test_set_of_proofs(self):
        client = _FakeClient(_VALID_DIAGNOSIS)
        res = diagnose([_PROOF, _PROOF, _PROOF], client=client, audit=False)
        assert res.n_proofs == 3
        assert "set of 3" in json.dumps(client.seen["messages"])

    def test_no_fallback_on_unparseable(self):
        client = _FakeClient("the model rambled with no JSON")
        with pytest.raises(DiagnosisParseError):
            diagnose(_PROOF, client=client, audit=False)

    def test_to_dict_round_trips(self):
        res = diagnose(_PROOF, client=_FakeClient(_VALID_DIAGNOSIS), audit=False)
        d = res.to_dict()
        assert d["tier"] == "scientific"
        assert d["diagnosis"]["next_question"]
        assert d["n_proofs"] == 1
