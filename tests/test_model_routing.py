"""Tests for the agentic model routing — dedicated tiers + provider dimension.

Pins the owner's requirements: dedicated scientific/engineering models (not
only general), local-first with external-API opt-in, and the boundary that
NO model is invoked from the measurement path.
"""

from __future__ import annotations

import ast
import pathlib

import pytest

from ophamin.agentic.models import (
    DEFAULT_TIER_MODELS,
    Provider,
    TaskTier,
    model_capabilities,
    pick_model,
)


class TestDedicatedTiers:
    def test_scientific_and_engineering_tiers_exist(self):
        assert TaskTier.SCIENTIFIC.value == "scientific"
        assert TaskTier.ENGINEERING.value == "engineering"
        assert TaskTier.SCIENTIFIC in DEFAULT_TIER_MODELS
        assert TaskTier.ENGINEERING in DEFAULT_TIER_MODELS

    def test_validation_tasks_route_to_dedicated_tiers(self):
        assert pick_model("scientific_validation").tier is TaskTier.SCIENTIFIC
        assert pick_model("result_diagnosis").tier is TaskTier.SCIENTIFIC
        assert pick_model("engineering_diagnosis").tier is TaskTier.ENGINEERING

    def test_dedicated_flagged_in_capabilities(self):
        caps = model_capabilities()
        dedicated = {t["tier"] for t in caps["tiers"] if t["dedicated"]}
        assert dedicated == {"scientific", "engineering"}


class TestProviderDimension:
    def test_local_is_default(self):
        c = pick_model("scientific_validation")
        assert c.provider is Provider.LOCAL
        caps = model_capabilities()
        assert caps["default_provider"] == "local"

    def test_external_api_opt_in_per_tier(self, monkeypatch):
        # Operator points the SCIENTIFIC tier at an external API.
        monkeypatch.setenv("OPHAMIN_LLM_PROVIDER_SCIENTIFIC", "external_api")
        monkeypatch.setenv("OPHAMIN_LLM_BASE_URL_SCIENTIFIC", "https://api.example.com/v1")
        monkeypatch.setenv("OPHAMIN_LLM_API_KEY_ENV_SCIENTIFIC", "MY_SCI_API_KEY")
        c = pick_model("scientific_validation")
        assert c.provider is Provider.EXTERNAL_API
        assert c.base_url == "https://api.example.com/v1"
        assert c.api_key_env == "MY_SCI_API_KEY"
        # Engineering tier stays local — opt-in is per tier.
        assert pick_model("engineering_diagnosis").provider is Provider.LOCAL

    def test_capabilities_never_leak_a_secret(self, monkeypatch):
        # Even with a real key set in the env, capabilities expose only the
        # env-var NAME, never the value.
        monkeypatch.setenv("OPHAMIN_LLM_PROVIDER_SCIENTIFIC", "external_api")
        monkeypatch.setenv("OPHAMIN_LLM_API_KEY_ENV_SCIENTIFIC", "MY_SCI_API_KEY")
        monkeypatch.setenv("MY_SCI_API_KEY", "sk-super-secret-value")
        caps = model_capabilities()
        blob = repr(caps)
        assert "sk-super-secret-value" not in blob
        assert "MY_SCI_API_KEY" in blob  # the name is fine

    def test_general_tiers_unchanged(self):
        # The pre-existing general routing still works.
        assert pick_model("adapter_gen").tier is TaskTier.CODER
        assert pick_model("bundle_query").tier is TaskTier.FAST


class TestMeasurementPathBoundary:
    """The hard rule: no model runs in the measurement path. Mechanically
    enforce it — no module under measuring/scenarios may import the agentic
    model/client layer."""

    def test_scenarios_do_not_import_agentic_models(self):
        repo = pathlib.Path(__file__).resolve().parent.parent
        scen_dir = repo / "src" / "ophamin" / "measuring" / "scenarios"
        offenders: list[str] = []
        for py in scen_dir.rglob("*.py"):
            tree = ast.parse(py.read_text(encoding="utf-8"), filename=str(py))
            for node in ast.walk(tree):
                mod = None
                if isinstance(node, ast.ImportFrom):
                    mod = node.module or ""
                elif isinstance(node, ast.Import):
                    mod = ",".join(a.name for a in node.names)
                if mod and ("ophamin.agentic" in mod):
                    offenders.append(f"{py.name}: imports {mod}")
        assert not offenders, (
            "Measurement-path modules must not import the agentic model "
            f"layer (no-LLM-in-measurement rule): {offenders}"
        )
