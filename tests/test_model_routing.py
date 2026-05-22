"""Tests for the agentic model routing — dedicated tiers + provider dimension.

Pins the owner's requirements: dedicated scientific/engineering models (not
only general), local-first with external-API opt-in, and the boundary that
NO model is invoked from the measurement path.
"""

from __future__ import annotations

import ast
import pathlib

from ophamin.agentic.models import (
    DEFAULT_TIER_MODELS,
    Provider,
    TaskTier,
    _dedicated_status,
    model_capabilities,
    pick_model,
    probe_tier_availability,
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


class TestDedicatedHonesty:
    """CR3: a tier reports dedicated:true ONLY when actually backed by a
    distinct/external model, not just because it's a domain-dedicated tier."""

    def test_default_is_general_fallback_not_claimed_dedicated(self, monkeypatch):
        # With no model overrides, SCIENTIFIC == reasoning's model and
        # ENGINEERING == coder's model — so they are general-fallback, NOT
        # dedicated. The surface must say so honestly.
        for v in ("SCIENTIFIC", "ENGINEERING", "REASONING", "CODER"):
            monkeypatch.delenv(f"OPHAMIN_LLM_MODEL_{v}", raising=False)
            monkeypatch.delenv(f"OPHAMIN_LLM_PROVIDER_{v}", raising=False)
        caps = model_capabilities()
        by_tier = {t["tier"]: t for t in caps["tiers"]}
        sci, eng = by_tier["scientific"], by_tier["engineering"]
        assert sci["dedicated"] is False
        assert sci["status"] == "general-fallback"
        assert sci["fallback_general_tier"] == "reasoning"
        assert sci["role"] == "domain-dedicated"
        assert eng["dedicated"] is False
        assert eng["status"] == "general-fallback"
        assert eng["fallback_general_tier"] == "coder"
        assert caps["dedicated_models_configured"] is False

    def test_distinct_model_makes_it_dedicated(self):
        # _dedicated_status takes the model directly (DEFAULT_TIER_MODELS is
        # import-time), so test the honest decision directly.
        is_ded, fb, status = _dedicated_status(
            TaskTier.SCIENTIFIC, "some-science-tuned:13b", Provider.LOCAL
        )
        assert is_ded is True
        assert fb == "reasoning"
        assert status == "dedicated"

    def test_external_api_counts_as_dedicated(self):
        # Pointing a dedicated tier at an external API is a dedicated choice,
        # even if the model string coincides with the fallback.
        is_ded, fb, status = _dedicated_status(
            TaskTier.ENGINEERING,
            DEFAULT_TIER_MODELS[TaskTier.CODER],
            Provider.EXTERNAL_API,
        )
        assert is_ded is True
        assert status == "dedicated"

    def test_general_tier_is_not_dedicated(self):
        is_ded, fb, status = _dedicated_status(
            TaskTier.FAST, DEFAULT_TIER_MODELS[TaskTier.FAST], Provider.LOCAL
        )
        assert is_ded is False
        assert fb is None
        assert status == "general"

    def test_capabilities_dedicated_when_distinct_model_set(self, monkeypatch):
        # End-to-end: a distinct model for the dedicated tier flips the
        # capability surface to dedicated:true. DEFAULT_TIER_MODELS is
        # import-time, so set the dict item directly (monkeypatch restores it)
        # — NEVER importlib.reload here: it rebinds the TaskTier enum and
        # breaks `is` identity for every other test in the session.
        import ophamin.agentic.models as m

        monkeypatch.setitem(
            m.DEFAULT_TIER_MODELS, TaskTier.SCIENTIFIC, "sci-tuned-model:13b"
        )
        caps = m.model_capabilities()
        sci = {t["tier"]: t for t in caps["tiers"]}["scientific"]
        assert sci["dedicated"] is True
        assert sci["status"] == "dedicated"
        assert caps["dedicated_models_configured"] is True


class TestAvailabilityProbe:
    """The dedicated-model claim is only honest if the model is actually
    installed — probe_tier_availability checks the runtime's /v1/models."""

    def _fake_client(self, monkeypatch, installed, *, raise_exc=False):
        import ophamin.agentic.client as clientmod

        class _Fake:
            def __init__(self, *a, **k):
                pass

            def list_models(self):
                if raise_exc:
                    raise clientmod.LLMClientError("runtime down")
                return list(installed)

        monkeypatch.setattr(clientmod, "LLMClient", _Fake)

    def test_available_when_model_installed(self, monkeypatch):
        self._fake_client(
            monkeypatch,
            [DEFAULT_TIER_MODELS[t] for t in TaskTier],
        )
        avail = probe_tier_availability()
        assert avail["fast"] is True
        assert avail["scientific"] is True

    def test_unavailable_when_model_missing(self, monkeypatch):
        self._fake_client(monkeypatch, ["something-else:1b"])
        avail = probe_tier_availability()
        assert avail["fast"] is False

    def test_unknown_when_runtime_down(self, monkeypatch):
        self._fake_client(monkeypatch, [], raise_exc=True)
        avail = probe_tier_availability()
        assert avail["fast"] is None

    def test_capabilities_includes_availability_when_requested(self, monkeypatch):
        self._fake_client(
            monkeypatch, [DEFAULT_TIER_MODELS[t] for t in TaskTier]
        )
        caps = model_capabilities(check_availability=True)
        assert caps["availability_checked"] is True
        assert all("available" in t for t in caps["tiers"])

    def test_capabilities_omits_availability_by_default(self):
        caps = model_capabilities()
        assert caps["availability_checked"] is False
        assert all("available" not in t for t in caps["tiers"])


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
