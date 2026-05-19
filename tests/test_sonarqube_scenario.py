"""Tests for SonarQubeScanProof — code-quality as a signed empirical claim.

Pins the scenario's invariants without requiring a running SonarQube
instance: every external HTTP call is monkey-patched at the
``_http_get_json`` / ``urllib.request.urlopen`` seams. A small
``conftest``-style helper captures the URLs the scenario hits so the
endpoint shape is part of the contract.
"""

from __future__ import annotations

import io
import json
import urllib.error
from typing import Any

import pytest

from ophamin.measuring.proof import (
    REFUTED,
    VALIDATED,
    EmpiricalProofRecord,
)
from ophamin.measuring.scenarios import SCENARIOS
from ophamin.measuring.scenarios.base import Tier
from ophamin.measuring.scenarios.sonarqube_scan import (
    SonarQubeAPIError,
    SonarQubeQualityGateMissingError,
    SonarQubeScanProof,
    _CANONICAL_METRIC_KEYS,
    _VALID_QG_STATUSES,
    _coerce_measure,
)


# --------------------------------------------------------------------------
# Fixtures — synthesize SonarQube REST responses without a live instance
# --------------------------------------------------------------------------

def _qg_payload(status: str = "OK", *, conditions: list[dict[str, Any]] | None = None):
    return {
        "projectStatus": {
            "status": status,
            "conditions": conditions or [],
            "ignoredConditions": False,
            "caycStatus": "compliant",
        }
    }


def _measures_payload(values: dict[str, float] | None = None):
    defaults = {
        "bugs": "667",
        "vulnerabilities": "2",
        "security_hotspots": "236",
        "code_smells": "7827",
        "duplicated_lines_density": "9.0",
        "ncloc": "571610",
        "sqale_index": "59322",
    }
    if values is not None:
        for k, v in values.items():
            defaults[k] = str(v)
    return {
        "component": {
            "key": "kimera-swm",
            "name": "Kimera-SWM",
            "qualifier": "TRK",
            "measures": [{"metric": k, "value": v} for k, v in defaults.items()],
        }
    }


def _install_fake_http(monkeypatch, *, qg_status="OK", measures_overrides=None,
                       server_version="26.5.0.122743"):
    """Patch the module's _http_get_json so it returns synthetic payloads.

    Also returns a list of URLs hit so callers can assert endpoint shape.
    """
    urls: list[str] = []

    def fake_get(url: str, *, token: str = "", timeout: float = 30.0):
        urls.append(url)
        if "qualitygates/project_status" in url:
            return _qg_payload(qg_status)
        if "measures/component" in url:
            return _measures_payload(measures_overrides)
        raise AssertionError(f"unexpected URL hit in fake_get: {url}")

    def fake_urlopen(req, timeout=None):  # used for /api/server/version path
        urls.append(req.full_url)
        body = io.BytesIO(server_version.encode("utf-8"))

        class _Resp:
            def __enter__(self_inner):
                return self_inner

            def __exit__(self_inner, *a):
                return False

            def read(self_inner):
                return body.read()

        return _Resp()

    import ophamin.measuring.scenarios.sonarqube_scan as mod
    monkeypatch.setattr(mod, "_http_get_json", fake_get)
    monkeypatch.setattr(mod.urllib.request, "urlopen", fake_urlopen)
    return urls


# --------------------------------------------------------------------------
# Metadata / registration / static structure
# --------------------------------------------------------------------------

def test_scenario_is_registered_with_kebab_case_name():
    assert "sonarqube-scan" in SCENARIOS
    assert SCENARIOS["sonarqube-scan"] is SonarQubeScanProof


def test_scenario_metadata_block_is_complete():
    cls = SonarQubeScanProof
    assert cls.name == "sonarqube-scan"
    assert cls.tier is Tier.ENGINEERING
    assert cls.family == "code_quality"
    assert cls.goal.strip()
    assert cls.explanation.strip()
    assert cls.method == "quality_gate_boolean"
    assert cls.falsification_consequence.strip()
    assert cls.target == "sonarqube_rest_api"


def test_canonical_metric_keys_are_the_seven_we_committed_to():
    assert _CANONICAL_METRIC_KEYS == (
        "bugs",
        "vulnerabilities",
        "security_hotspots",
        "code_smells",
        "duplicated_lines_density",
        "ncloc",
        "sqale_index",
    )


def test_valid_qg_statuses_match_sonar_api_documented_set():
    assert _VALID_QG_STATUSES == frozenset({"OK", "WARN", "ERROR", "NONE"})


# --------------------------------------------------------------------------
# Constructor validation — loud-failure on bad arguments
# --------------------------------------------------------------------------

def test_constructor_rejects_non_http_base_url():
    with pytest.raises(ValueError, match="must be a fully qualified http"):
        SonarQubeScanProof(base_url="localhost:9000")


def test_constructor_rejects_empty_project_key():
    with pytest.raises(ValueError, match="non-empty"):
        SonarQubeScanProof(project_key="   ")


def test_constructor_rejects_non_positive_timeout():
    with pytest.raises(ValueError, match="positive seconds"):
        SonarQubeScanProof(timeout=0)
    with pytest.raises(ValueError, match="positive seconds"):
        SonarQubeScanProof(timeout=-1.5)


def test_constructor_strips_trailing_slash_from_base_url():
    s = SonarQubeScanProof(base_url="http://localhost:9000/")
    assert s.base_url == "http://localhost:9000"


# --------------------------------------------------------------------------
# Claim / threshold shape
# --------------------------------------------------------------------------

def test_build_claim_thresholds_qg_passed_ge_1():
    s = SonarQubeScanProof(project_key="kimera-swm")
    claim = s.build_claim()
    assert claim.threshold.metric == "qg_passed"
    assert claim.threshold.comparator == ">="
    assert claim.threshold.value == 1.0
    assert claim.threshold.units == "boolean"
    assert "kimera-swm" in claim.statement
    assert "QG" in claim.h0 or "OK" in claim.h0


# --------------------------------------------------------------------------
# Endpoint composition — the URL contract the operator + CI rely on
# --------------------------------------------------------------------------

def test_qg_endpoint_carries_project_key_in_querystring():
    s = SonarQubeScanProof(base_url="http://x:9000", project_key="kimera-swm")
    assert s._qg_endpoint().endswith("projectKey=kimera-swm")


def test_measures_endpoint_carries_canonical_metric_keys():
    s = SonarQubeScanProof(base_url="http://x:9000", project_key="kimera-swm")
    url = s._measures_endpoint()
    for k in _CANONICAL_METRIC_KEYS:
        assert k in url


def test_dashboard_url_is_project_key_quoted():
    s = SonarQubeScanProof(base_url="http://x:9000", project_key="kimera swm/x")
    url = s._dashboard_url()
    # urllib.parse.quote should percent-encode the space + slash
    assert "%20" in url or "+" in url
    assert "kimera" in url


# --------------------------------------------------------------------------
# Measure coercion
# --------------------------------------------------------------------------

def test_coerce_measure_parses_string_to_float():
    assert _coerce_measure("667") == 667.0
    assert _coerce_measure("9.0") == 9.0


def test_coerce_measure_none_returns_default():
    assert _coerce_measure(None) == 0.0
    assert _coerce_measure(None, default=-1.0) == -1.0


# --------------------------------------------------------------------------
# Live-run path — synthetic SonarQube, full proof emitted + signed
# --------------------------------------------------------------------------

def test_run_emits_validated_proof_when_qg_is_ok(monkeypatch):
    _install_fake_http(monkeypatch, qg_status="OK")
    proof = SonarQubeScanProof(token="t").run()
    assert isinstance(proof, EmpiricalProofRecord)
    assert proof.verdict.outcome == VALIDATED
    assert proof.verify_signature(b"ophamin-scenario-proof-key") is True


def test_run_emits_refuted_proof_when_qg_is_error(monkeypatch):
    _install_fake_http(monkeypatch, qg_status="ERROR")
    proof = SonarQubeScanProof(token="t").run()
    assert proof.verdict.outcome == REFUTED


def test_run_emits_refuted_proof_when_qg_is_warn(monkeypatch):
    _install_fake_http(monkeypatch, qg_status="WARN")
    proof = SonarQubeScanProof(token="t").run()
    assert proof.verdict.outcome == REFUTED


def test_run_emits_refuted_proof_when_qg_is_none(monkeypatch):
    _install_fake_http(monkeypatch, qg_status="NONE")
    proof = SonarQubeScanProof(token="t").run()
    assert proof.verdict.outcome == REFUTED


def test_run_evidence_carries_the_seven_canonical_measures(monkeypatch):
    _install_fake_http(monkeypatch, qg_status="OK")
    proof = SonarQubeScanProof(token="t").run()
    [ev] = proof.evidence
    measures = ev.detail["measures"]
    for k in _CANONICAL_METRIC_KEYS:
        assert k in measures
    assert measures["bugs"] == 667.0
    assert measures["vulnerabilities"] == 2.0
    assert measures["ncloc"] == 571610.0
    assert measures["duplicated_lines_density"] == 9.0


def test_run_evidence_carries_dashboard_url(monkeypatch):
    _install_fake_http(monkeypatch, qg_status="OK")
    proof = SonarQubeScanProof(
        base_url="http://localhost:9000", project_key="kimera-swm", token="t",
    ).run()
    [ev] = proof.evidence
    assert ev.detail["dashboard_url"] == (
        "http://localhost:9000/dashboard?id=kimera-swm"
    )


def test_run_pillar_library_version_is_sonar_server_version(monkeypatch):
    _install_fake_http(monkeypatch, qg_status="OK", server_version="26.5.0.122743")
    proof = SonarQubeScanProof(token="t").run()
    [ev] = proof.evidence
    assert ev.library == "sonarqube"
    assert ev.library_version == "26.5.0.122743"


def test_run_dataset_n_records_is_ncloc(monkeypatch):
    _install_fake_http(monkeypatch, qg_status="OK")
    proof = SonarQubeScanProof(token="t").run()
    [ds] = proof.datasets
    assert ds.n_records == 571610
    assert ds.kind == "sonarqube-rest-api"


def test_run_pillar_statistic_value_is_qg_passed_boolean(monkeypatch):
    _install_fake_http(monkeypatch, qg_status="OK")
    proof_ok = SonarQubeScanProof(token="t").run()
    [ev_ok] = proof_ok.evidence
    assert ev_ok.statistic_name == "qg_passed"
    assert ev_ok.statistic_value == 1.0

    _install_fake_http(monkeypatch, qg_status="ERROR")
    proof_err = SonarQubeScanProof(token="t").run()
    [ev_err] = proof_err.evidence
    assert ev_err.statistic_value == 0.0


def test_run_proof_is_content_addressed_and_reproducible(monkeypatch):
    _install_fake_http(monkeypatch, qg_status="OK")
    proof_a = SonarQubeScanProof(token="t").run()
    _install_fake_http(monkeypatch, qg_status="OK")
    proof_b = SonarQubeScanProof(token="t").run()
    # created_at differs, but the body's substantive content matches.
    assert proof_a.verdict.outcome == proof_b.verdict.outcome
    assert proof_a.evidence[0].detail["measures"] == proof_b.evidence[0].detail["measures"]


def test_run_provenance_contains_both_agents(monkeypatch):
    _install_fake_http(monkeypatch, qg_status="OK")
    proof = SonarQubeScanProof(token="t").run()
    agents = proof.provenance.get("agent", {})
    # ProvenanceGraph keys agents as "ophamin:<name>"; assert by key suffix.
    agent_suffixes = {key.split(":", 1)[-1] for key in agents}
    assert "ophamin" in agent_suffixes
    assert "sonarqube" in agent_suffixes


def test_run_records_last_payload_for_replay(monkeypatch):
    _install_fake_http(monkeypatch, qg_status="OK")
    s = SonarQubeScanProof(token="t")
    s.run()
    assert s.last_payload is not None
    assert s.last_payload["qg_status"] == "OK"
    assert s.last_payload["server_version"] == "26.5.0.122743"
    assert s.last_payload["measures"]["bugs"] == 667.0


# --------------------------------------------------------------------------
# Loud-failure paths
# --------------------------------------------------------------------------

def test_fetch_quality_gate_raises_on_unknown_status(monkeypatch):
    import ophamin.measuring.scenarios.sonarqube_scan as mod

    def fake_get(url, *, token="", timeout=30.0):
        return {"projectStatus": {"status": "BOGUS", "conditions": []}}

    monkeypatch.setattr(mod, "_http_get_json", fake_get)
    with pytest.raises(SonarQubeQualityGateMissingError):
        SonarQubeScanProof(token="t").fetch_quality_gate()


def test_fetch_quality_gate_raises_on_missing_project_status(monkeypatch):
    import ophamin.measuring.scenarios.sonarqube_scan as mod

    def fake_get(url, *, token="", timeout=30.0):
        return {"errors": [{"msg": "Project not found"}]}

    monkeypatch.setattr(mod, "_http_get_json", fake_get)
    with pytest.raises(SonarQubeQualityGateMissingError):
        SonarQubeScanProof(token="t").fetch_quality_gate()


def test_http_get_json_wraps_httperror_into_sonarqube_api_error():
    import ophamin.measuring.scenarios.sonarqube_scan as mod
    # We simulate the wrap by directly raising HTTPError out of urlopen.

    def raising_urlopen(req, timeout=None):
        raise urllib.error.HTTPError(
            url=req.full_url if hasattr(req, "full_url") else "http://x",
            code=401, msg="Unauthorized", hdrs={}, fp=io.BytesIO(b'{"err":"no"}'),
        )

    real_urlopen = mod.urllib.request.urlopen
    mod.urllib.request.urlopen = raising_urlopen
    try:
        with pytest.raises(SonarQubeAPIError) as exc_info:
            mod._http_get_json("http://x/api/system/status")
        assert exc_info.value.status_code == 401
    finally:
        mod.urllib.request.urlopen = real_urlopen


def test_score_raises_unreachable_pattern():
    """The base.Scenario.score contract is unused — base.run() is overridden."""
    s = SonarQubeScanProof(token="t")
    with pytest.raises(NotImplementedError, match="custom run"):
        s.score([], [])


def test_endpoint_urls_actually_hit_in_run_path(monkeypatch):
    urls = _install_fake_http(monkeypatch, qg_status="OK")
    SonarQubeScanProof(token="t").run()
    # qualitygates + measures + server/version — all three must be touched
    qg_hits = [u for u in urls if "qualitygates/project_status" in u]
    measures_hits = [u for u in urls if "measures/component" in u]
    version_hits = [u for u in urls if "server/version" in u]
    assert len(qg_hits) == 1
    assert len(measures_hits) == 1
    assert len(version_hits) == 1


def test_token_header_present_when_provided(monkeypatch):
    """Token-based HTTP Basic header must be added when token is non-empty."""
    import ophamin.measuring.scenarios.sonarqube_scan as mod
    captured: dict[str, str] = {}

    real_urlopen = mod.urllib.request.urlopen

    def capturing_urlopen(req, timeout=None):
        # Capture headers, then route to a synthetic response so test
        # finishes cleanly.
        for k, v in req.headers.items():
            captured[k.lower()] = v
        body = io.BytesIO(b'{"projectStatus":{"status":"OK","conditions":[]}}')

        class _Resp:
            def __enter__(self_inner):
                return self_inner

            def __exit__(self_inner, *a):
                return False

            def read(self_inner):
                return body.read()

        return _Resp()

    mod.urllib.request.urlopen = capturing_urlopen
    try:
        mod._http_get_json("http://localhost:9000/api/qualitygates/project_status",
                            token="MYTOKEN")
    finally:
        mod.urllib.request.urlopen = real_urlopen

    assert "authorization" in captured
    assert captured["authorization"].startswith("Basic ")
