"""Per-tier endpoint routing — client_for_model resolves a ModelChoice to the
right LLMClient endpoint.

Pins the fix that makes the per-tier provider/base_url (which pick_model already
computes and /models advertises) actually take effect: a LOCAL tier uses the
framework-wide endpoint (unchanged), an EXTERNAL_API tier targets its own
base_url + reads the key from the named env var.
"""

from __future__ import annotations

from ophamin.agentic.models import client_for_model, pick_model


def test_local_tier_uses_framework_default(monkeypatch):
    monkeypatch.delenv("OPHAMIN_LLM_PROVIDER_WORKHORSE", raising=False)
    mc = pick_model("proof_brief")  # WORKHORSE, LOCAL by default
    assert mc.provider.value == "local"
    client = client_for_model(mc)
    assert client.base_url.startswith(("http://", "https://"))


def test_external_api_tier_targets_its_endpoint_and_key(monkeypatch):
    monkeypatch.setenv("OPHAMIN_LLM_PROVIDER_SCIENTIFIC", "external_api")
    monkeypatch.setenv("OPHAMIN_LLM_BASE_URL_SCIENTIFIC", "https://api.example.test/v1")
    monkeypatch.setenv("OPHAMIN_LLM_API_KEY_ENV_SCIENTIFIC", "MY_SCI_KEY")
    monkeypatch.setenv("MY_SCI_KEY", "sk-secret-123")
    mc = pick_model("scientific_validation")  # SCIENTIFIC tier
    assert mc.provider.value == "external_api"
    assert mc.base_url == "https://api.example.test/v1"
    client = client_for_model(mc)
    assert client.base_url == "https://api.example.test/v1"
    assert client.api_key == "sk-secret-123"  # read from the named env var


def test_external_without_base_url_falls_back_to_local(monkeypatch):
    # provider=external_api but no base_url configured -> safe local fallback,
    # never a crash on a half-configured tier.
    monkeypatch.setenv("OPHAMIN_LLM_PROVIDER_ENGINEERING", "external_api")
    monkeypatch.delenv("OPHAMIN_LLM_BASE_URL_ENGINEERING", raising=False)
    mc = pick_model("engineering_diagnosis")
    client = client_for_model(mc)
    assert client.base_url.startswith(("http://", "https://"))


def test_key_absent_does_not_crash(monkeypatch):
    # external_api + base_url but the key env var is unset -> client still builds
    # (the runtime ignores the token for local-style endpoints).
    monkeypatch.setenv("OPHAMIN_LLM_PROVIDER_SCIENTIFIC", "external_api")
    monkeypatch.setenv("OPHAMIN_LLM_BASE_URL_SCIENTIFIC", "https://api.example.test/v1")
    monkeypatch.setenv("OPHAMIN_LLM_API_KEY_ENV_SCIENTIFIC", "UNSET_KEY_VAR")
    monkeypatch.delenv("UNSET_KEY_VAR", raising=False)
    mc = pick_model("scientific_validation")
    client = client_for_model(mc)
    assert client.base_url == "https://api.example.test/v1"
