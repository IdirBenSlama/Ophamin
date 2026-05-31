"""The /significance HTTP endpoint — plain-language meaning, served.

Lets the live console (and any client) render the same "what this means about
Kimera" the static renderers carry, from the single Python source. No model in
the loop; honest null on an unauthored metric.
"""

from fastapi.testclient import TestClient

from ophamin.http_api.server import build_app


def _client() -> TestClient:
    return TestClient(build_app())


def test_significance_endpoint_returns_meaning():
    r = _client().get(
        "/significance",
        params={"metric": "order_hysteresis", "outcome": "VALIDATED", "observed": 0.93},
    )
    assert r.status_code == 200
    s = r.json()["significance"]
    assert s and "order" in s.lower() and "0.93" in s


def test_significance_endpoint_unknown_metric_is_null():
    r = _client().get(
        "/significance", params={"metric": "totally_unknown", "outcome": "VALIDATED"}
    )
    assert r.status_code == 200
    assert r.json()["significance"] is None


def test_significance_endpoint_refuted_branch_is_honest():
    r = _client().get(
        "/significance",
        params={"metric": "graded_fidelity_advantage", "outcome": "REFUTED", "observed": 0.05},
    )
    s = r.json()["significance"]
    assert s and "magnitude" in s.lower()  # the honest size-meter gap, in plain words
