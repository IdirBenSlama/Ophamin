"""Tests for the Manage facet — substrate status / health.

The deterministic core (``normalize_status``) is tested with synthetic
probe reports; the live ``substrate_status`` is tested for the degraded
path (no live substrate needed) plus a skippable real-repo integration.
"""

from __future__ import annotations

import pytest

from ophamin.managing import normalize_status, substrate_status


class TestNormalizeStatus:
    def test_all_healthy_is_ready(self):
        rep = {
            "kimera_repo": "/r", "git_commit": "abc123", "python_exe": "/py",
            "runner_ok": True,
            "targets": {
                "entity": {"import_ok": True, "module": "m"},
                "walker": {"import_ok": True, "module": "m"},
            },
        }
        s = normalize_status(rep)
        assert s["ready"] is True
        assert s["n_healthy"] == 2 and s["n_targets"] == 2
        assert s["health_rate"] == 1.0
        assert s["git_commit"] == "abc123"

    def test_partial_health_surfaces_broken_target(self):
        rep = {
            "runner_ok": True,
            "targets": {
                "entity": {"import_ok": True},
                "walker": {"import_ok": False, "error": "boom"},
            },
        }
        s = normalize_status(rep)
        assert s["ready"] is True            # >=1 healthy → operable
        assert s["n_healthy"] == 1
        assert s["health_rate"] == 0.5
        walker = next(t for t in s["targets"] if t["name"] == "walker")
        assert walker["import_ok"] is False
        assert walker["error"] == "boom"

    def test_runner_down_is_not_ready(self):
        s = normalize_status({"runner_ok": False, "error": "import blew up"})
        assert s["runner_ok"] is False
        assert s["ready"] is False
        assert s["n_targets"] == 0
        assert s["error"] == "import blew up"

    def test_zero_healthy_is_not_ready(self):
        rep = {"runner_ok": True,
               "targets": {"entity": {"import_ok": False, "error": "x"}}}
        s = normalize_status(rep)
        assert s["ready"] is False           # runner up but nothing reachable
        assert s["n_healthy"] == 0


class TestSubstrateStatus:
    def test_missing_repo_is_degraded_not_crash(self):
        s = substrate_status("/nonexistent/kimera/repo")
        assert s["runner_ok"] is False
        assert s["ready"] is False
        assert "not found" in s["error"].lower()
        assert s["targets"] == []

    def test_real_repo_if_present(self):
        import pathlib
        repo = pathlib.Path(
            "/Users/idirbenslama/Desktop/DEV/Kimera_SWM (Spherical Word Memory)")
        if not (repo / "kimera_swm").is_dir():
            pytest.skip("real Kimera repo not present")
        s = substrate_status(repo)
        # The substrate should be runnable and report cognitive surfaces.
        assert s["runner_ok"] is True
        assert s["n_targets"] >= 5
        assert {"entity", "walker", "arachne"} <= {t["name"] for t in s["targets"]}
        assert isinstance(s["git_commit"], str) and len(s["git_commit"]) > 0
