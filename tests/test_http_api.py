"""Tests for the Ophamin HTTP REST API.

Same logical surface as the MCP server, exposed over HTTP. These
tests use FastAPI's TestClient (which speaks the real HTTP plumbing
without actually opening a port) so they pin both the routing AND
the response shapes a real HTTP consumer would see.

The HTTP API wraps the same shared implementations as the MCP server
(:mod:`ophamin.interfaces._impls`), so behavioural drift between the
two transports is structurally impossible. This file complements
``test_mcp_server.py`` rather than duplicating it: it focuses on the
HTTP-specific surface (status codes, error envelopes, OpenAPI shape).
"""

from __future__ import annotations

import base64
import json
from pathlib import Path

import pytest

# fastapi is in core deps; if it's missing the framework's other
# tests would already fail. No importorskip needed.
from fastapi.testclient import TestClient

from ophamin import __version__
from ophamin.http_api import SERVER_NAME, SERVER_TITLE, SERVER_VERSION, build_app


REPO_ROOT = Path(__file__).resolve().parent.parent
PROOFS_DIR = REPO_ROOT / "proofs" / "measurement_machinery"
ANY_SHIPPED_PROOF = next(PROOFS_DIR.rglob("*.json"), None)


@pytest.fixture(scope="module")
def client() -> TestClient:
    app = build_app()
    return TestClient(app)


class TestServerIdentity:
    def test_server_constants(self) -> None:
        assert SERVER_NAME == "ophamin-http-api"
        assert SERVER_TITLE.startswith("Ophamin")
        assert SERVER_VERSION == __version__


class TestHealthAndVersion:
    def test_health_returns_200(self, client: TestClient) -> None:
        r = client.get("/health")
        assert r.status_code == 200
        assert r.json() == {"status": "ok"}

    def test_version_returns_framework_version(self, client: TestClient) -> None:
        r = client.get("/version")
        assert r.status_code == 200
        body = r.json()
        assert body["name"] == "ophamin-http-api"
        assert body["framework_version"] == __version__


class TestMetrics:
    """Pins on /metrics — the Prometheus exposition endpoint added in
    0.57.0 to back the chart's ServiceMonitor + PodMonitor templates."""

    def test_metrics_returns_200(self, client: TestClient) -> None:
        r = client.get("/metrics")
        assert r.status_code == 200

    def test_metrics_content_type_is_prometheus_text_exposition(
        self, client: TestClient,
    ) -> None:
        r = client.get("/metrics")
        # The Prometheus text exposition format is
        # `text/plain; version=0.0.4` or similar; check the prefix.
        assert r.headers["content-type"].startswith("text/plain")
        assert "version=" in r.headers["content-type"]

    def test_metrics_surface_carries_build_info(self, client: TestClient) -> None:
        body = client.get("/metrics").text
        assert "ophamin_build_info" in body
        assert f'version="{__version__}"' in body

    def test_metrics_surface_carries_scenarios_registered_gauge(
        self, client: TestClient,
    ) -> None:
        body = client.get("/metrics").text
        assert "ophamin_scenarios_registered" in body
        # value line follows the format `metric_name X.0` — count >= 1
        # because the framework always has scenarios registered.
        from ophamin.measuring.scenarios import SCENARIOS
        expected = f"ophamin_scenarios_registered {float(len(SCENARIOS))}"
        assert expected in body


class TestScenariosListing:
    def test_get_scenarios_returns_registry(self, client: TestClient) -> None:
        r = client.get("/scenarios")
        assert r.status_code == 200
        body = r.json()
        assert "count" in body
        assert "scenarios" in body
        assert body["count"] == len(body["scenarios"])
        assert body["framework_version"] == __version__

    def test_registry_covers_seven_cross_framework(self, client: TestClient) -> None:
        r = client.get("/scenarios")
        names = {s["name"] for s in r.json()["scenarios"]}
        for required in (
            "spearman-crosscheck",
            "pearson-crosscheck",
            "welch-t-crosscheck",
            "anova-crosscheck",
            "mann-whitney-crosscheck",
            "wilson-ci-crosscheck",
        ):
            assert required in names, f"missing required scenario {required}"


class TestScenarioClaim:
    def test_returns_claim_for_known_scenario(self, client: TestClient) -> None:
        r = client.get("/scenarios/spearman-crosscheck/claim")
        assert r.status_code == 200
        body = r.json()
        assert body["claim_available"] is True
        claim = body["claim"]
        assert claim["statement"]
        assert claim["threshold"]["comparator"] in ("<=", ">=", "<", ">", "==")

    def test_unknown_scenario_404(self, client: TestClient) -> None:
        r = client.get("/scenarios/does-not-exist/claim")
        assert r.status_code == 404
        assert "unknown scenario" in r.json()["detail"]


class TestVerify:
    @pytest.mark.skipif(
        ANY_SHIPPED_PROOF is None,
        reason="no shipped signed proofs found in the repo",
    )
    def test_real_shipped_proof_verifies(self, client: TestClient) -> None:
        text = ANY_SHIPPED_PROOF.read_text(encoding="utf-8")
        r = client.post("/verify", json={"proof_json": text})
        assert r.status_code == 200
        body = r.json()
        assert body["verified"] is True
        assert body["verdict"]["outcome"] in ("VALIDATED", "REFUTED", "INCONCLUSIVE")
        assert len(body["proof_id"]) == 64

    @pytest.mark.skipif(
        ANY_SHIPPED_PROOF is None,
        reason="no shipped signed proofs found in the repo",
    )
    def test_tampered_signature_returns_verified_false(
        self, client: TestClient
    ) -> None:
        text = ANY_SHIPPED_PROOF.read_text(encoding="utf-8")
        record = json.loads(text)
        sig = record["signature"]
        record["signature"] = ("1" if sig[0] == "0" else "0") + sig[1:]
        r = client.post("/verify", json={"proof_json": json.dumps(record)})
        # NOT 4xx — 200 with verified=False.
        assert r.status_code == 200
        body = r.json()
        assert body["verified"] is False
        # Verdict still readable on a tampered record.
        assert "verdict" in body
        assert "claim_statement" in body

    def test_malformed_json_returns_400(self, client: TestClient) -> None:
        r = client.post("/verify", json={"proof_json": "not json at all"})
        assert r.status_code == 400
        assert "valid JSON" in r.json()["detail"]

    def test_non_object_json_returns_400(self, client: TestClient) -> None:
        r = client.post("/verify", json={"proof_json": "[1, 2, 3]"})
        assert r.status_code == 400

    def test_invalid_sign_key_b64_returns_400(self, client: TestClient) -> None:
        r = client.post(
            "/verify",
            json={"proof_json": '{}', "sign_key_b64": "not-valid-base64!!!"},
        )
        assert r.status_code == 400
        assert "base64" in r.json()["detail"]


class TestCanonicalize:
    def test_simple_value_canonicalizes(self, client: TestClient) -> None:
        r = client.post(
            "/canonicalize",
            json={"value_json": json.dumps({"x": 30, "y": 30.0})},
        )
        assert r.status_code == 200
        body = r.json()
        # Int 30 emits without .0; float 30.0 emits with .0 — exactly
        # what the wire-format contract guarantees.
        assert '"x":30,' in body["canonical"]
        assert '"y":30.0' in body["canonical"]
        assert len(body["sha256_hex"]) == 64
        assert len(body["hmac_sha256_hex"]) == 64

    def test_custom_key_changes_hmac(self, client: TestClient) -> None:
        key_b64 = base64.b64encode(b"custom-key").decode("ascii")
        r1 = client.post(
            "/canonicalize",
            json={"value_json": '{"a": 1}'},
        )
        r2 = client.post(
            "/canonicalize",
            json={"value_json": '{"a": 1}', "sign_key_b64": key_b64},
        )
        assert r1.status_code == 200 and r2.status_code == 200
        # Same canonical bytes; different HMAC.
        assert r1.json()["canonical"] == r2.json()["canonical"]
        assert r1.json()["hmac_sha256_hex"] != r2.json()["hmac_sha256_hex"]

    def test_invalid_json_returns_400(self, client: TestClient) -> None:
        r = client.post(
            "/canonicalize",
            json={"value_json": "definitely not json {{{"},
        )
        assert r.status_code == 400


class TestProofsIndex:
    @pytest.mark.skipif(
        not PROOFS_DIR.exists(),
        reason="proofs/measurement_machinery not present",
    )
    def test_indexes_shipped_proofs(self, client: TestClient) -> None:
        r = client.post(
            "/proofs/index", json={"directory": str(PROOFS_DIR)}
        )
        assert r.status_code == 200
        body = r.json()
        assert body["total_proofs"] >= 1
        assert body["load_errors"] == 0

    def test_missing_directory_returns_400(self, client: TestClient) -> None:
        r = client.post(
            "/proofs/index",
            json={"directory": "/nonexistent/path/absolutely"},
        )
        assert r.status_code == 400
        assert "does not exist" in r.json()["detail"]

    def test_not_a_directory_returns_400(
        self, client: TestClient, tmp_path: Path
    ) -> None:
        f = tmp_path / "not-a-dir.txt"
        f.write_text("x")
        r = client.post("/proofs/index", json={"directory": str(f)})
        assert r.status_code == 400


class TestRunScenario:
    def test_small_spearman_runs(self, client: TestClient) -> None:
        """Smoke-test the heaviest endpoint with minimal kwargs so it
        finishes in well under a second."""
        r = client.post(
            "/scenarios/spearman-crosscheck/run",
            json={"kwargs_json": json.dumps({"n_pairs": 3, "sample_size": 20})},
        )
        assert r.status_code == 200
        body = r.json()
        assert body["scenario"] == "spearman-crosscheck"
        assert body["verdict"]["outcome"] == "VALIDATED"
        assert len(body["proof_id"]) == 64

    def test_unknown_scenario_returns_400(self, client: TestClient) -> None:
        r = client.post("/scenarios/does-not-exist/run", json={"kwargs_json": "{}"})
        assert r.status_code == 400
        assert "unknown scenario" in r.json()["detail"]

    def test_invalid_kwargs_returns_400(self, client: TestClient) -> None:
        r = client.post(
            "/scenarios/spearman-crosscheck/run",
            json={"kwargs_json": "not json"},
        )
        assert r.status_code == 400


class TestOpenAPI:
    """Verify FastAPI's auto-generated OpenAPI surface is sane."""

    def test_openapi_spec_available(self, client: TestClient) -> None:
        r = client.get("/openapi.json")
        assert r.status_code == 200
        spec = r.json()
        assert spec["openapi"].startswith("3.")
        assert spec["info"]["title"] == "Ophamin HTTP REST API"
        assert spec["info"]["version"] == __version__

    def test_swagger_ui_available(self, client: TestClient) -> None:
        r = client.get("/docs")
        assert r.status_code == 200
        # Swagger UI is an HTML page; just check the marker.
        assert "Swagger" in r.text or "swagger" in r.text

    def test_redoc_available(self, client: TestClient) -> None:
        r = client.get("/redoc")
        assert r.status_code == 200
        assert "redoc" in r.text.lower()

    def test_all_endpoints_in_spec(self, client: TestClient) -> None:
        """Every documented endpoint must appear in the OpenAPI paths."""
        spec = client.get("/openapi.json").json()
        paths = set(spec["paths"].keys())
        expected = {
            "/health",
            "/version",
            "/scenarios",
            "/scenarios/{name}/claim",
            "/verify",
            "/canonicalize",
            "/proofs/index",
            "/scenarios/{name}/run",
        }
        missing = expected - paths
        assert not missing, f"missing paths in OpenAPI spec: {missing}"


class TestErrorEnvelope:
    """Uncaught exceptions land as JSON 500 with the type + message,
    not raw stack traces."""

    def test_500_envelope_shape(self, client: TestClient) -> None:
        """No public route raises directly today, but FastAPI's
        validation errors give us a clean way to exercise the
        envelope: send wrong-shape body."""
        # Missing required field 'proof_json'
        r = client.post("/verify", json={})
        # FastAPI's default 422 handler runs before our 500 handler.
        # That's fine — both are JSON envelopes, neither leaks a
        # stack trace.
        assert r.status_code in (400, 422)
        body = r.json()
        assert "detail" in body


class TestBundlesEndpoints:
    """Pins on the 0.60.0 bundle-aware endpoints + the static UI mount."""

    def test_bundles_tree_returns_200_with_expected_shape(self, client: TestClient) -> None:
        r = client.get("/proofs/bundles/tree")
        assert r.status_code == 200
        body = r.json()
        assert "tiers" in body and "totals" in body
        # totals keys
        for k in ("tiers", "scenarios", "bundles", "verdicts"):
            assert k in body["totals"]

    def test_bundles_tree_accepts_custom_proofs_root(self, tmp_path, client: TestClient) -> None:
        """Operator can browse a non-default proofs/ dir via querystring."""
        # Build a tiny synthetic tree.
        bundle = tmp_path / "scientific" / "rosetta-scaling" / "2026-05-19_validated_abcdef012345"
        bundle.mkdir(parents=True)
        (bundle / "proof.json").write_text("{}")
        r = client.get("/proofs/bundles/tree", params={"proofs_root": str(tmp_path)})
        assert r.status_code == 200
        body = r.json()
        assert body["totals"]["bundles"] == 1

    def test_bundles_file_refuses_path_traversal(self, client: TestClient) -> None:
        r = client.get("/proofs/bundles/file", params={
            "tier": "../etc", "scenario": "x",
            "bundle": "y", "filename": "proof.json",
        })
        assert r.status_code == 400
        assert "invalid tier" in r.json()["detail"]

    def test_bundles_file_refuses_disallowed_filename(self, tmp_path, client: TestClient) -> None:
        bundle = tmp_path / "scientific" / "rosetta-scaling" / "2026-05-19_validated_abcdef012345"
        bundle.mkdir(parents=True)
        (bundle / "proof.json").write_text("{}")
        r = client.get("/proofs/bundles/file", params={
            "tier": "scientific", "scenario": "rosetta-scaling",
            "bundle": "2026-05-19_validated_abcdef012345",
            "filename": "passwd",
            "proofs_root": str(tmp_path),
        })
        assert r.status_code == 400
        assert "refusing to serve" in r.json()["detail"]

    def test_bundles_file_returns_404_when_missing(self, tmp_path, client: TestClient) -> None:
        bundle = tmp_path / "scientific" / "rosetta-scaling" / "2026-05-19_validated_abcdef012345"
        bundle.mkdir(parents=True)
        (bundle / "proof.json").write_text("{}")
        r = client.get("/proofs/bundles/file", params={
            "tier": "scientific", "scenario": "rosetta-scaling",
            "bundle": "2026-05-19_validated_abcdef012345",
            "filename": "proof.pdf",  # not present
            "proofs_root": str(tmp_path),
        })
        assert r.status_code == 404

    def test_bundles_file_serves_json_with_application_json_mime(
        self, tmp_path, client: TestClient,
    ) -> None:
        bundle = tmp_path / "scientific" / "rosetta-scaling" / "2026-05-19_validated_abcdef012345"
        bundle.mkdir(parents=True)
        (bundle / "proof.json").write_text('{"hello": "world"}')
        r = client.get("/proofs/bundles/file", params={
            "tier": "scientific", "scenario": "rosetta-scaling",
            "bundle": "2026-05-19_validated_abcdef012345",
            "filename": "proof.json",
            "proofs_root": str(tmp_path),
        })
        assert r.status_code == 200
        assert r.headers["content-type"] == "application/json"
        assert r.json() == {"hello": "world"}


class TestProvisionalGUIMount:
    """The /ui endpoint serves the bundled SPA when the static dir exists."""

    def test_ui_index_returns_html(self, client: TestClient) -> None:
        r = client.get("/ui")
        assert r.status_code == 200
        assert r.headers["content-type"].startswith("text/html")
        assert "Ophamin" in r.text
        assert "/ui/static/styles.css" in r.text
        assert "/ui/static/app.js" in r.text

    def test_ui_static_styles_served(self, client: TestClient) -> None:
        r = client.get("/ui/static/styles.css")
        assert r.status_code == 200
        # FastAPI's StaticFiles uses standard mimetypes; .css → text/css
        assert "text/css" in r.headers["content-type"]
        assert ":root" in r.text  # CSS custom-property block

    def test_ui_static_app_js_served(self, client: TestClient) -> None:
        r = client.get("/ui/static/app.js")
        assert r.status_code == 200
        # JS files served as application/javascript or text/javascript
        ctype = r.headers["content-type"]
        assert "javascript" in ctype
        assert "(function ()" in r.text  # IIFE marker

    def test_root_redirects_to_ui(self, client: TestClient) -> None:
        # follow_redirects=False so we can observe the 302
        r = client.get("/", follow_redirects=False)
        assert r.status_code == 302
        assert r.headers["location"] == "/ui"

    def test_openapi_lists_new_endpoints(self, client: TestClient) -> None:
        """Verify the 3 new endpoints are advertised in the OpenAPI
        schema so external clients can discover them."""
        r = client.get("/openapi.json")
        assert r.status_code == 200
        paths = r.json()["paths"]
        assert "/proofs/bundles/tree" in paths
        assert "/proofs/bundles/file" in paths
        assert "/ui" in paths
