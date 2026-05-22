"""Tests for the toolkit registry — Ophamin's unified index of native tools.

Pins: the registry resolves real installed versions, every entry carries a
well-formed native link, the live-UI tools are present + routed, and the
registry is extensible via OPHAMIN_TOOLKITS (with loud failure on a malformed
plug-in entry).
"""

from __future__ import annotations

import json

import pytest

from ophamin.interop.toolkit_registry import (
    ToolkitConfigError,
    toolkit_registry,
)


class TestRegistry:
    def test_returns_resolved_toolkits(self):
        r = toolkit_registry()
        assert r["n_toolkits"] >= 20
        assert r["n_core"] == r["n_toolkits"] - r["n_extra"]
        ids = {t["id"] for t in r["toolkits"]}
        # a few load-bearing ones must be present
        assert {"scipy", "statsmodels", "mlflow", "ruff", "cryptography"} <= ids

    def test_versions_resolved_for_installed_core(self):
        # the core deps are installed in this env — versions must resolve.
        r = toolkit_registry()
        scipy = next(t for t in r["toolkits"] if t["id"] == "scipy")
        assert scipy["installed"] is True
        assert scipy["version"]  # non-empty version string

    def test_native_ui_tools_routed(self):
        r = toolkit_registry()
        by_id = {t["id"]: t for t in r["toolkits"]}
        # the tools with a live native UI carry a route
        assert by_id["mlflow"]["native_ui"]
        assert by_id["dvc"]["native_ui"]
        assert by_id["prometheus-client"]["native_ui"]
        assert r["n_with_native_ui"] >= 3

    def test_every_toolkit_has_well_formed_links(self):
        r = toolkit_registry()
        for t in r["toolkits"]:
            assert t["homepage"].startswith(("http://", "https://")), t["id"]
            assert t["docs_url"].startswith(("http://", "https://")), t["id"]
            assert t["role"]  # one-line role is required
            assert t["category"]

    def test_categories_grouped(self):
        r = toolkit_registry()
        assert isinstance(r["categories"], dict)
        assert sum(r["categories"].values()) == r["n_toolkits"]
        assert "statistical" in r["categories"]


class TestExtensibility:
    def test_extra_toolkits_merged(self, tmp_path):
        extra = [{
            "id": "my-sdk", "category": "custom", "role": "the user's own SDK",
            "homepage": "https://example.com", "docs_url": "https://example.com/docs",
        }]
        p = tmp_path / "toolkits.json"
        p.write_text(json.dumps(extra), encoding="utf-8")
        r = toolkit_registry(extra_path=str(p))
        assert r["n_extra"] == 1
        assert any(t["id"] == "my-sdk" for t in r["toolkits"])

    def test_missing_file_raises(self, tmp_path):
        with pytest.raises(ToolkitConfigError):
            toolkit_registry(extra_path=str(tmp_path / "nope.json"))

    def test_malformed_entry_raises(self, tmp_path):
        p = tmp_path / "bad.json"
        p.write_text(json.dumps([{"id": "x"}]), encoding="utf-8")  # missing keys
        with pytest.raises(ToolkitConfigError):
            toolkit_registry(extra_path=str(p))

    def test_non_list_raises(self, tmp_path):
        p = tmp_path / "obj.json"
        p.write_text(json.dumps({"id": "x"}), encoding="utf-8")
        with pytest.raises(ToolkitConfigError):
            toolkit_registry(extra_path=str(p))

    def test_env_var_merges(self, tmp_path, monkeypatch):
        extra = [{
            "id": "env-sdk", "category": "custom", "role": "via env",
            "homepage": "https://e.com", "docs_url": "https://e.com/d",
        }]
        p = tmp_path / "env.json"
        p.write_text(json.dumps(extra), encoding="utf-8")
        monkeypatch.setenv("OPHAMIN_TOOLKITS", str(p))
        r = toolkit_registry()
        assert any(t["id"] == "env-sdk" for t in r["toolkits"])


class TestImpl:
    def test_impl_adds_framework_version(self):
        from ophamin.interfaces._impls import toolkit_registry_impl

        r = toolkit_registry_impl()
        assert "framework_version" in r
        assert r["n_toolkits"] >= 20
