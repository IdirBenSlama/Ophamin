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
            "/agents",
            "/agents/calls",
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

    def test_bundles_file_serves_html_inline_not_attachment(
        self, tmp_path, client: TestClient,
    ) -> None:
        """proof.html MUST be served Content-Disposition: inline so the
        GUI's iframe RENDERS it instead of triggering a download.

        Regression guard (0.63.5): passing `filename=` to FileResponse
        defaults the disposition to `attachment`, which blanks the
        GUI's HTML/PDF iframe (browser downloads rather than displays).
        The file endpoint's docstring contract is "the browser renders
        HTML/PDF natively" — that depends on inline disposition.
        """
        bundle = tmp_path / "scientific" / "rosetta-scaling" / "2026-05-19_validated_abcdef012345"
        bundle.mkdir(parents=True)
        (bundle / "proof.html").write_text("<!doctype html><title>Proof</title><body>x</body>")
        r = client.get("/proofs/bundles/file", params={
            "tier": "scientific", "scenario": "rosetta-scaling",
            "bundle": "2026-05-19_validated_abcdef012345",
            "filename": "proof.html",
            "proofs_root": str(tmp_path),
        })
        assert r.status_code == 200
        assert r.headers["content-type"].startswith("text/html")
        disp = r.headers.get("content-disposition", "")
        assert disp.startswith("inline"), (
            f"proof.html must be inline so the iframe renders it, got: {disp!r}"
        )
        assert "attachment" not in disp

    def test_bundles_file_serves_pdf_inline_not_attachment(
        self, tmp_path, client: TestClient,
    ) -> None:
        """proof.pdf likewise must be inline so the PDF iframe renders
        it in-browser rather than downloading."""
        bundle = tmp_path / "scientific" / "rosetta-scaling" / "2026-05-19_validated_abcdef012345"
        bundle.mkdir(parents=True)
        # Minimal PDF header is enough for the disposition assertion.
        (bundle / "proof.pdf").write_bytes(b"%PDF-1.4\n%%EOF\n")
        r = client.get("/proofs/bundles/file", params={
            "tier": "scientific", "scenario": "rosetta-scaling",
            "bundle": "2026-05-19_validated_abcdef012345",
            "filename": "proof.pdf",
            "proofs_root": str(tmp_path),
        })
        assert r.status_code == 200
        disp = r.headers.get("content-disposition", "")
        assert disp.startswith("inline"), (
            f"proof.pdf must be inline so the iframe renders it, got: {disp!r}"
        )
        assert "attachment" not in disp

    def _bundle_with_asset(self, tmp_path):
        bundle = tmp_path / "scientific" / "rosetta-scaling" / "2026-05-19_validated_abcdef012345"
        (bundle / "assets").mkdir(parents=True)
        (bundle / "proof.md").write_text(
            "# Proof\n\n![chart](assets/ci_metric.png)\n"
        )
        # 1x1 transparent PNG (valid header is enough for the assertions).
        png = bytes.fromhex(
            "89504e470d0a1a0a0000000d49484452000000010000000108060000001f15c489"
            "0000000a49444154789c6300010000050001"
            "0d0a2db40000000049454e44ae426082"
        )
        (bundle / "assets" / "ci_metric.png").write_bytes(png)
        return bundle

    def test_bundles_file_serves_asset_png_inline(
        self, tmp_path, client: TestClient,
    ) -> None:
        """Bundle assets (charts referenced by proof.md) are served with
        image/* mime + inline disposition so the MD view can render them.
        Regression guard (0.63.6): before this, the endpoint allow-listed
        only proof.{json,md,html,tex,pdf} and there was NO asset route —
        the MD chart 404'd."""
        self._bundle_with_asset(tmp_path)
        r = client.get("/proofs/bundles/file", params={
            "tier": "scientific", "scenario": "rosetta-scaling",
            "bundle": "2026-05-19_validated_abcdef012345",
            "filename": "assets/ci_metric.png",
            "proofs_root": str(tmp_path),
        })
        assert r.status_code == 200
        assert r.headers["content-type"] == "image/png"
        disp = r.headers.get("content-disposition", "")
        assert disp.startswith("inline")
        assert r.content[:8] == b"\x89PNG\r\n\x1a\n"

    def test_bundles_file_refuses_non_image_asset(
        self, tmp_path, client: TestClient,
    ) -> None:
        """An asset path with a non-image extension is refused — the
        asset route is for charts, not arbitrary file reads."""
        bundle = self._bundle_with_asset(tmp_path)
        (bundle / "assets" / "secret.txt").write_text("nope")
        r = client.get("/proofs/bundles/file", params={
            "tier": "scientific", "scenario": "rosetta-scaling",
            "bundle": "2026-05-19_validated_abcdef012345",
            "filename": "assets/secret.txt",
            "proofs_root": str(tmp_path),
        })
        assert r.status_code == 400
        assert "refusing to serve" in r.json()["detail"]

    def test_bundles_file_refuses_asset_path_traversal(
        self, tmp_path, client: TestClient,
    ) -> None:
        """`assets/../../etc` style traversal in the asset path is
        refused at the boundary."""
        self._bundle_with_asset(tmp_path)
        r = client.get("/proofs/bundles/file", params={
            "tier": "scientific", "scenario": "rosetta-scaling",
            "bundle": "2026-05-19_validated_abcdef012345",
            "filename": "assets/../../../../etc/passwd",
            "proofs_root": str(tmp_path),
        })
        assert r.status_code == 400

    def test_bundles_file_refuses_nested_asset_subdir(
        self, tmp_path, client: TestClient,
    ) -> None:
        """Only a single `assets/<name>` segment is allowed — no deeper
        nesting that could walk into unexpected dirs."""
        self._bundle_with_asset(tmp_path)
        r = client.get("/proofs/bundles/file", params={
            "tier": "scientific", "scenario": "rosetta-scaling",
            "bundle": "2026-05-19_validated_abcdef012345",
            "filename": "assets/sub/dir/x.png",
            "proofs_root": str(tmp_path),
        })
        assert r.status_code == 400


class TestProvisionalGUIMount:
    """The /ui endpoint serves the bundled SPA when the static dir exists."""

    def test_ui_index_returns_html(self, client: TestClient) -> None:
        r = client.get("/ui")
        assert r.status_code == 200
        assert r.headers["content-type"].startswith("text/html")
        assert "Ophamin" in r.text
        assert "/ui/static/styles.css" in r.text
        assert "/ui/static/app.js" in r.text

    def test_ui_static_assets_are_cache_busted_by_version(
        self, client: TestClient,
    ) -> None:
        """The /ui HTML stamps app.js + styles.css with ?v=<version> so
        an upgrading browser loads fresh JS/CSS instead of a stale
        cached copy (regression guard, 0.63.6)."""
        from ophamin import __version__
        r = client.get("/ui")
        assert r.status_code == 200
        assert f"/ui/static/app.js?v={__version__}" in r.text
        assert f"/ui/static/styles.css?v={__version__}" in r.text

    def test_ui_html_is_not_cacheable(self, client: TestClient) -> None:
        """The /ui HTML must be no-store: it carries the version stamp,
        so a stale cached copy would point at an old app.js and defeat
        the cache-buster (regression guard, 0.63.6)."""
        r = client.get("/ui")
        assert r.status_code == 200
        cc = r.headers.get("cache-control", "")
        assert "no-store" in cc

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


class TestConsoleMount:
    """The /app endpoint serves the React 'Ophamin Console' (Claude
    Design export) when the console/ bundle dir exists. Mirrors the
    /ui discipline: relative `app/…` refs rewritten to absolute
    /app/static/app/… + per-version cache-buster + no-store HTML."""

    def test_console_index_returns_html(self, client: TestClient) -> None:
        r = client.get("/app")
        assert r.status_code == 200
        assert r.headers["content-type"].startswith("text/html")
        assert "Ophamin Console" in r.text

    def test_console_asset_refs_are_absolutized(self, client: TestClient) -> None:
        """The design bundle's relative `app/…` refs must be rewritten to
        absolute `/app/static/app/…` so they resolve when served at /app
        (a page at /app would otherwise resolve `app/x` to /app/x)."""
        r = client.get("/app")
        assert r.status_code == 200
        # No leftover relative refs.
        assert 'src="app/' not in r.text
        assert 'href="app/' not in r.text
        # Absolutized refs for the data layer + stylesheet + entry script.
        assert "/app/static/app/data.js" in r.text
        assert "/app/static/app/styles.css" in r.text
        assert "/app/static/app/app.jsx" in r.text

    def test_console_assets_are_cache_busted_by_version(
        self, client: TestClient,
    ) -> None:
        """Every bundle asset ref carries ?v=<version> so an upgrading
        browser loads fresh JS/CSS/data instead of a stale cached copy
        (same discipline as /ui)."""
        from ophamin import __version__
        r = client.get("/app")
        assert r.status_code == 200
        assert f"/app/static/app/data.js?v={__version__}" in r.text
        assert f"/app/static/app/styles.css?v={__version__}" in r.text
        assert f"/app/static/app/app.jsx?v={__version__}" in r.text

    def test_console_html_is_not_cacheable(self, client: TestClient) -> None:
        """The /app HTML must be no-store: it carries the version stamp,
        so a stale cached copy would point at old assets and defeat the
        cache-buster."""
        r = client.get("/app")
        assert r.status_code == 200
        assert "no-store" in r.headers.get("cache-control", "")

    def test_console_injects_asset_and_api_base(self, client: TestClient) -> None:
        """The route injects OPHAMIN_ASSET_BASE (force-load fallback) and
        OPHAMIN_API_BASE (data.js hydrate target) so the bundle resolves
        its assets + REST surface against this server."""
        r = client.get("/app")
        assert r.status_code == 200
        assert "window.OPHAMIN_ASSET_BASE='/app/static/app/'" in r.text
        assert "window.OPHAMIN_API_BASE=''" in r.text

    def test_console_static_data_js_served_with_hydrate(
        self, client: TestClient,
    ) -> None:
        r = client.get("/app/static/app/data.js")
        assert r.status_code == 200
        assert "javascript" in r.headers["content-type"]
        # The live-wiring contract: data.js exposes hydrate().
        assert "hydrate" in r.text
        assert "window.OPHAMIN" in r.text

    def test_console_static_styles_served(self, client: TestClient) -> None:
        r = client.get("/app/static/app/styles.css")
        assert r.status_code == 200
        assert "text/css" in r.headers["content-type"]

    def test_console_in_openapi(self, client: TestClient) -> None:
        r = client.get("/openapi.json")
        assert r.status_code == 200
        assert "/app" in r.json()["paths"]


class TestAgentsEndpoints:
    """Read-only surfaces over the advisory agentic layer: the agent
    catalogue (/agents) + the signed LLM-call audit trail (/agents/calls).
    Neither runs an agent or touches a measurement path."""

    def test_agents_returns_seven_with_metadata(self, client: TestClient) -> None:
        r = client.get("/agents")
        assert r.status_code == 200
        body = r.json()
        assert body["count"] == 7
        assert body["framework_version"] == __version__
        ids = {a["id"] for a in body["agents"]}
        assert ids == {
            "prereg", "scenario-gen", "adapt", "brief",
            "triage", "confounds", "query",
        }
        for a in body["agents"]:
            for k in ("id", "task", "label", "desc", "tier", "cli"):
                assert k in a, f"agent missing {k}: {a}"
            assert a["tier"] in {"fast", "workhorse", "coder", "reasoning"}
            assert a["cli"] == f"ophamin agent {a['id']}"

    def test_agents_tier_sourced_from_routing(self, client: TestClient) -> None:
        """Tiers reflect TASK_ROUTING (not a hardcoded dup)."""
        from ophamin.agentic.models import TASK_ROUTING
        body = client.get("/agents").json()
        by_id = {a["id"]: a for a in body["agents"]}
        # Spot-check the routing-derived tier for two agents.
        assert by_id["query"]["tier"] == TASK_ROUTING["bundle_query"].value
        assert by_id["prereg"]["tier"] == TASK_ROUTING["prereg_validator"].value

    def test_agents_in_openapi(self, client: TestClient) -> None:
        paths = client.get("/openapi.json").json()["paths"]
        assert "/agents" in paths
        assert "/agents/calls" in paths

    def test_agent_calls_empty_when_no_llm_calls_dir(
        self, tmp_path, client: TestClient,
    ) -> None:
        """A proofs tree with no llm_calls/ yields an empty list, not an
        error (fresh instance has run no agents)."""
        r = client.get("/agents/calls", params={"proofs_root": str(tmp_path)})
        assert r.status_code == 200
        body = r.json()
        assert body["count"] == 0
        assert body["calls"] == []

    def test_agent_calls_summarizes_signed_record(
        self, tmp_path, client: TestClient,
    ) -> None:
        """A real signed LLMCallRecord on disk surfaces as a verified
        summary — and prompt messages + response content are NOT leaked."""
        from ophamin.agentic.audit import LLMCallRecord

        rec = LLMCallRecord(
            task="proof_brief",
            runtime="ollama",
            model="llama3.3:70b",
            messages=[{"role": "user", "content": "SECRET PROMPT TEXT"}],
            max_tokens=512,
            temperature=0.2,
            response_format="text",
            content="SECRET RESPONSE TEXT",
            finish_reason="stop",
            prompt_tokens=120,
            completion_tokens=88,
            latency_ms=1840.0,
            ophamin_version=__version__,
        ).sign()
        call_dir = tmp_path / "llm_calls" / "2026-05-21"
        call_dir.mkdir(parents=True)
        (call_dir / f"{rec.call_id[:16]}.json").write_text(
            json.dumps(rec.to_dict()), encoding="utf-8",
        )

        r = client.get("/agents/calls", params={"proofs_root": str(tmp_path)})
        assert r.status_code == 200
        body = r.json()
        assert body["count"] == 1
        call = body["calls"][0]
        assert call["task"] == "proof_brief"
        assert call["model"] == "llama3.3:70b"
        assert call["runtime"] == "ollama"
        assert call["verified"] is True
        assert call["prompt_tokens"] == 120
        assert call["completion_tokens"] == 88
        assert call["signature_prefix"] == rec.signature[:16]
        # No prompt / response payload leaks into the audit summary.
        assert "messages" not in call
        assert "content" not in call
        assert "SECRET" not in json.dumps(body)

    def test_agent_calls_flags_tampered_signature_unverified(
        self, tmp_path, client: TestClient,
    ) -> None:
        """A record whose signature doesn't match its body surfaces as
        verified=False — the audit trail is HMAC-checked, not trusted."""
        from ophamin.agentic.audit import LLMCallRecord

        rec = LLMCallRecord(
            task="bundle_query", runtime="mlx-lm", model="llama3.1:8b",
            messages=[{"role": "user", "content": "q"}], max_tokens=64,
            temperature=0.0, response_format="json_object", content="{}",
            finish_reason="stop", prompt_tokens=10, completion_tokens=4,
            latency_ms=120.0, ophamin_version=__version__,
        ).sign()
        d = rec.to_dict()
        d["signature"] = "00" * 32  # tamper
        call_dir = tmp_path / "llm_calls" / "2026-05-21"
        call_dir.mkdir(parents=True)
        (call_dir / "tampered.json").write_text(json.dumps(d), encoding="utf-8")

        body = client.get(
            "/agents/calls", params={"proofs_root": str(tmp_path)},
        ).json()
        assert body["count"] == 1
        assert body["calls"][0]["verified"] is False

    def test_agent_calls_respects_limit(
        self, tmp_path, client: TestClient,
    ) -> None:
        from ophamin.agentic.audit import LLMCallRecord

        call_dir = tmp_path / "llm_calls" / "2026-05-21"
        call_dir.mkdir(parents=True)
        for i in range(5):
            rec = LLMCallRecord(
                task="proof_brief", runtime="ollama", model="m",
                messages=[{"role": "user", "content": f"q{i}"}],
                max_tokens=8, temperature=0.0, response_format="text",
                content="a", finish_reason="stop", prompt_tokens=1,
                completion_tokens=1, latency_ms=1.0,
                ophamin_version=__version__,
            ).sign()
            (call_dir / f"{i}_{rec.call_id[:8]}.json").write_text(
                json.dumps(rec.to_dict()), encoding="utf-8",
            )
        body = client.get(
            "/agents/calls", params={"proofs_root": str(tmp_path), "limit": 3},
        ).json()
        assert body["count"] == 3
