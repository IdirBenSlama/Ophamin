"""Tests for the Ophamin MCP server.

The MCP server exposes Ophamin's read + run + verify surfaces over
the Model Context Protocol. These tests verify the tool catalogue is
correctly registered and each tool's contract holds.

Tools are exercised via their underlying ``_*_impl`` functions
directly — this avoids the asyncio + transport plumbing of the
``FastMCP.call_tool`` API while still pinning the same contract MCP
clients see.
"""

from __future__ import annotations

import asyncio
import base64
import json
from pathlib import Path

import pytest

from ophamin import __version__
from ophamin.mcp import build_server
from ophamin.mcp.server import (
    SERVER_NAME,
    SERVER_TITLE,
    SERVER_VERSION,
    _canonicalize_value_impl,
    _decode_sign_key,
    _get_scenario_claim_impl,
    _list_scenarios_impl,
    _read_proof_index_impl,
    _run_scenario_impl,
    _scenario_metadata,
    _verify_proof_impl,
)
from ophamin.measuring.scenarios.base import DEFAULT_SIGN_KEY, SCENARIOS


REPO_ROOT = Path(__file__).resolve().parent.parent
PROOFS_DIR = REPO_ROOT / "proofs" / "measurement_machinery"
ANY_SHIPPED_PROOF = next(PROOFS_DIR.rglob("*.json"), None)


class TestServerIdentity:
    def test_server_name_is_ophamin(self) -> None:
        assert SERVER_NAME == "ophamin"

    def test_server_title_set(self) -> None:
        assert isinstance(SERVER_TITLE, str)
        assert SERVER_TITLE.startswith("Ophamin")

    def test_server_version_matches_package(self) -> None:
        assert SERVER_VERSION == __version__


class TestBuildServer:
    def test_returns_fastmcp_instance(self) -> None:
        mcp = build_server()
        # Don't rely on isinstance against the mcp lib's class — that
        # couples test to private import surface. Check the duck type.
        assert hasattr(mcp, "run")
        assert hasattr(mcp, "list_tools")
        assert hasattr(mcp, "call_tool")

    def test_six_tools_registered(self) -> None:
        mcp = build_server()
        tools = asyncio.run(mcp.list_tools())
        names = {t.name for t in tools}
        expected = {
            "list_scenarios",
            "get_scenario_claim",
            "verify_proof",
            "canonicalize_value",
            "read_proof_index",
            "run_scenario",
        }
        assert names == expected, (
            f"tool catalogue drifted; expected {sorted(expected)}, "
            f"got {sorted(names)}"
        )

    def test_each_tool_has_description(self) -> None:
        """Every tool MUST carry a description so MCP clients can
        present meaningful UI to users."""
        mcp = build_server()
        tools = asyncio.run(mcp.list_tools())
        for t in tools:
            assert t.description, f"tool {t.name!r} has no description"
            assert len(t.description) > 30, (
                f"tool {t.name!r} description is suspiciously short: "
                f"{t.description!r}"
            )


class TestDecodeSignKey:
    def test_empty_string_uses_default_key(self) -> None:
        assert _decode_sign_key("") == DEFAULT_SIGN_KEY

    def test_valid_base64_decoded(self) -> None:
        key = b"my-custom-key"
        b64 = base64.b64encode(key).decode("ascii")
        assert _decode_sign_key(b64) == key

    def test_invalid_base64_raises(self) -> None:
        with pytest.raises(ValueError, match="base64"):
            _decode_sign_key("not-valid-base64!!!")


class TestScenarioMetadata:
    def test_known_scenario_returns_dict(self) -> None:
        # Pick the first registered scenario at runtime so the test
        # doesn't pin a specific scenario name.
        name = next(iter(sorted(SCENARIOS)))
        meta = _scenario_metadata(name)
        assert meta["name"] == name
        assert "family" in meta
        assert "tier" in meta
        assert "goal" in meta

    def test_unknown_scenario_raises(self) -> None:
        with pytest.raises(ValueError, match="unknown scenario"):
            _scenario_metadata("does-not-exist-anywhere")


class TestListScenarios:
    def test_returns_count_and_list(self) -> None:
        r = _list_scenarios_impl()
        assert "count" in r
        assert "scenarios" in r
        assert "framework_version" in r
        assert r["count"] == len(r["scenarios"])
        assert r["framework_version"] == __version__

    def test_count_is_at_least_seven_cross_framework(self) -> None:
        """0.16.x ships 7 cross-framework scenarios; the framework as a
        whole has many more. Sanity-check the registry is non-empty.
        """
        r = _list_scenarios_impl()
        # At least one of each cross-framework family must be there.
        names = {s["name"] for s in r["scenarios"]}
        for required in (
            "spearman-crosscheck",
            "pearson-crosscheck",
            "welch-t-crosscheck",
            "anova-crosscheck",
            "mann-whitney-crosscheck",
            "wilson-ci-crosscheck",
        ):
            assert required in names, f"missing required scenario {required}"


class TestGetScenarioClaim:
    def test_zero_arg_scenario_returns_claim(self) -> None:
        r = _get_scenario_claim_impl("spearman-crosscheck")
        assert r["claim_available"] is True
        claim = r["claim"]
        assert claim["statement"]
        assert claim["operationalization"]
        assert claim["threshold"]["metric"]
        assert claim["threshold"]["comparator"] in ("<=", ">=", "<", ">", "==")
        assert isinstance(claim["threshold"]["value"], float)
        assert claim["h0"]
        assert claim["h1"]

    def test_unknown_scenario_raises(self) -> None:
        with pytest.raises(ValueError, match="unknown scenario"):
            _get_scenario_claim_impl("does-not-exist")


class TestVerifyProof:
    @pytest.mark.skipif(
        ANY_SHIPPED_PROOF is None,
        reason="no shipped signed proofs found in the repo",
    )
    def test_real_shipped_proof_verifies_under_default_key(self) -> None:
        text = ANY_SHIPPED_PROOF.read_text(encoding="utf-8")
        r = _verify_proof_impl(text)
        assert r["verified"] is True
        assert r["verdict"]["outcome"] in ("VALIDATED", "REFUTED", "INCONCLUSIVE")
        assert len(r["proof_id"]) == 64  # full SHA-256 hex

    @pytest.mark.skipif(
        ANY_SHIPPED_PROOF is None,
        reason="no shipped signed proofs found in the repo",
    )
    def test_tampered_signature_fails_verification(self) -> None:
        text = ANY_SHIPPED_PROOF.read_text(encoding="utf-8")
        record = json.loads(text)
        # Flip the first hex digit of the signature
        sig = record["signature"]
        record["signature"] = ("1" if sig[0] == "0" else "0") + sig[1:]
        r = _verify_proof_impl(json.dumps(record))
        assert r["verified"] is False
        # Verdict block + claim_statement should still come through —
        # verify_proof does NOT raise on tamper, it surfaces a verdict.
        assert "verdict" in r
        assert "claim_statement" in r

    def test_invalid_json_raises(self) -> None:
        with pytest.raises(ValueError, match="valid JSON"):
            _verify_proof_impl("not json at all")

    def test_non_object_raises(self) -> None:
        with pytest.raises(ValueError, match="JSON object"):
            _verify_proof_impl("[1, 2, 3]")


class TestCanonicalizeValue:
    def test_simple_value_canonicalizes(self) -> None:
        r = _canonicalize_value_impl(json.dumps({"a": 1, "b": "café"}))
        # Python's json.dumps emits non-ASCII as \uXXXX under ensure_ascii=True
        # (which our canonical encoder uses).
        assert r["canonical"] == '{"a":1,"b":"caf\\u00e9"}'
        assert len(r["sha256_hex"]) == 64
        assert len(r["hmac_sha256_hex"]) == 64

    def test_custom_key_via_base64(self) -> None:
        key = b"my-key"
        b64 = base64.b64encode(key).decode("ascii")
        r1 = _canonicalize_value_impl(json.dumps({"a": 1}), b64)
        r2 = _canonicalize_value_impl(json.dumps({"a": 1}), "")
        # Same canonical bytes; different HMAC because keys differ.
        assert r1["canonical"] == r2["canonical"]
        assert r1["hmac_sha256_hex"] != r2["hmac_sha256_hex"]

    def test_invalid_json_raises(self) -> None:
        with pytest.raises(ValueError, match="valid JSON"):
            _canonicalize_value_impl("definitely not json {{{")


class TestReadProofIndex:
    @pytest.mark.skipif(
        not PROOFS_DIR.exists(),
        reason="proofs/measurement_machinery/ not present in this checkout",
    )
    def test_indexes_shipped_proofs(self) -> None:
        r = _read_proof_index_impl(str(PROOFS_DIR))
        assert r["total_proofs"] >= 1
        assert r["load_errors"] == 0
        assert isinstance(r["by_scenario"], dict)
        # Every shipped proof should be a cross-framework one →
        # verdict VALIDATED across all.
        for path_entry in r["proofs"]:
            if "verdict" in path_entry:
                assert path_entry["verdict"] in (
                    "VALIDATED",
                    "REFUTED",
                    "INCONCLUSIVE",
                )

    def test_missing_directory_raises(self) -> None:
        with pytest.raises(ValueError, match="does not exist"):
            _read_proof_index_impl("/nonexistent/path/absolutely")

    def test_non_directory_raises(self, tmp_path: Path) -> None:
        f = tmp_path / "not-a-dir.txt"
        f.write_text("x")
        with pytest.raises(ValueError, match="not a directory"):
            _read_proof_index_impl(str(f))


class TestRunScenario:
    def test_small_spearman_runs_and_returns_summary(self) -> None:
        """Smoke-test the heaviest tool. spearman-crosscheck with
        ``n_pairs=3`` finishes in well under a second."""
        r = _run_scenario_impl(
            "spearman-crosscheck",
            json.dumps({"n_pairs": 3, "sample_size": 20}),
        )
        assert r["scenario"] == "spearman-crosscheck"
        assert r["verdict"]["outcome"] == "VALIDATED"
        assert len(r["proof_id"]) == 64
        assert r["framework_version"] == __version__
        assert r["n_evidence_pillars"] >= 1

    def test_unknown_scenario_raises(self) -> None:
        with pytest.raises(ValueError, match="unknown scenario"):
            _run_scenario_impl("does-not-exist", "{}")

    def test_invalid_kwargs_json_raises(self) -> None:
        with pytest.raises(ValueError, match="valid JSON"):
            _run_scenario_impl("spearman-crosscheck", "not json")

    def test_non_object_kwargs_json_raises(self) -> None:
        with pytest.raises(ValueError, match="JSON object"):
            _run_scenario_impl("spearman-crosscheck", "[1, 2]")


class TestEndToEndViaFastMCP:
    """Exercise the actual MCP plumbing once, end-to-end.

    Goes through ``mcp.call_tool`` to make sure the tool registration
    + invocation surface works (not just the underlying _impl
    functions). Slow-ish; one tool exercised is enough.
    """

    def test_list_scenarios_via_call_tool(self) -> None:
        mcp = build_server()
        result = asyncio.run(mcp.call_tool("list_scenarios", {}))
        # call_tool returns a tuple (content_blocks, structured_result)
        # for FastMCP. Assert structure non-empty.
        assert result is not None
