"""Tests for the 0.62.0 self-dogfood layer (`ophamin self-test`).

Pins:
- Every scenario in SELF_TEST_SCENARIOS exists in the SCENARIOS registry
- run_self_test produces one bundle per scenario
- All bundles land under <proofs_root>/<tier>/<scenario>/<bundle>/
  and carry the standard 5 (or 1 if json-only) files
- SelfTestResult counters match the actual outcomes
- Errors in one scenario don't abort the whole loop
- Workflow file exists + parses + has expected step shape
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest
import yaml

from ophamin.measuring.proof import BundleFormat
from ophamin.measuring.scenarios import SCENARIOS
from ophamin.self_test import (
    SELF_TEST_SCENARIOS,
    ScenarioRunResult,
    SelfTestResult,
    run_self_test,
)


REPO_ROOT = Path(__file__).resolve().parent.parent
WORKFLOW = REPO_ROOT / ".github" / "workflows" / "self-test.yml"


# --------------------------------------------------------------------------
# SELF_TEST_SCENARIOS — curated list invariants
# --------------------------------------------------------------------------

def test_self_test_scenarios_is_non_empty():
    assert len(SELF_TEST_SCENARIOS) >= 5, (
        "SELF_TEST_SCENARIOS must include at least the 7 statistical "
        "crosschecks + a few measurement-machinery validators"
    )


def test_every_self_test_scenario_is_registered():
    """Every scenario name in the curated list MUST be in SCENARIOS —
    otherwise the runner would emit an ERROR row for it."""
    missing = [
        name for name, _ in SELF_TEST_SCENARIOS if name not in SCENARIOS
    ]
    assert not missing, f"SELF_TEST_SCENARIOS references unregistered: {missing}"


def test_self_test_scenarios_kwargs_are_dicts():
    """Each entry is (str, dict) tuple — guards against accidental shape
    drift (e.g. someone passing positional args)."""
    for name, kwargs in SELF_TEST_SCENARIOS:
        assert isinstance(name, str), f"name not str: {name!r}"
        assert isinstance(kwargs, dict), f"kwargs not dict for {name}: {kwargs!r}"


def test_self_test_scenarios_includes_seven_crosschecks():
    """The 7 statistical crosschecks are the load-bearing self-dogfood —
    pin their presence."""
    names = {name for name, _ in SELF_TEST_SCENARIOS}
    for required in (
        "spearman-crosscheck",
        "pearson-crosscheck",
        "anova-crosscheck",
        "welch-t-crosscheck",
        "mann-whitney-crosscheck",
        "wilson-ci-crosscheck",
        "bayesian-phi-posterior-crosscheck",
    ):
        assert required in names, f"missing required crosscheck: {required}"


def test_self_test_scenarios_no_kimera_substrate_required():
    """No scenario in the curated list may require a Kimera-shape
    constructor arg (`kimera_repo`, `repo_path`, etc.) — that would
    mean it's substrate-bound and shouldn't be in the substrate-free
    dogfood set."""
    import inspect
    kimera_arg_names = {"kimera_repo", "repo_path", "substrate_repo"}
    for name, _ in SELF_TEST_SCENARIOS:
        cls = SCENARIOS[name]
        sig = inspect.signature(cls.__init__)
        for param_name in sig.parameters:
            assert param_name not in kimera_arg_names, (
                f"{name}: requires Kimera-shape arg {param_name!r} — "
                "not substrate-free, shouldn't be in SELF_TEST_SCENARIOS"
            )


# --------------------------------------------------------------------------
# run_self_test — live run + bundle shape
# --------------------------------------------------------------------------

@pytest.fixture
def fast_self_test(tmp_path):
    """A fast run with JSON-only bundles (skip MD/HTML/LaTeX/PDF)."""
    result = run_self_test(
        proofs_root=tmp_path / "self-test-out",
        formats=BundleFormat.json_only(),
        seed=42,
    )
    return result, tmp_path / "self-test-out"


def test_run_self_test_produces_one_result_per_scenario(fast_self_test):
    result, _ = fast_self_test
    assert isinstance(result, SelfTestResult)
    assert result.n_total == len(SELF_TEST_SCENARIOS)
    assert all(isinstance(r, ScenarioRunResult) for r in result.results)


def test_run_self_test_persists_one_bundle_per_scenario(fast_self_test):
    _, proofs_root = fast_self_test
    bundles = list(proofs_root.rglob("proof.json"))
    assert len(bundles) == len(SELF_TEST_SCENARIOS), (
        f"expected {len(SELF_TEST_SCENARIOS)} bundles, got {len(bundles)}"
    )


def test_run_self_test_counters_are_consistent(fast_self_test):
    result, _ = fast_self_test
    assert (result.n_validated + result.n_refuted +
            result.n_inconclusive + result.n_errored) == result.n_total


def test_run_self_test_all_dogfood_scenarios_validated_under_seed_42(fast_self_test):
    """The substrate-free dogfood scenarios MUST all validate under any
    seed — they test framework invariants, not stochastic substrate
    behavior. If one regresses to REFUTED that's a real defect."""
    result, _ = fast_self_test
    if result.n_refuted > 0:
        refuted = [r for r in result.results if r.verdict == "REFUTED"]
        pytest.fail(
            f"{len(refuted)} scenarios REFUTED under self-test: "
            + ", ".join(r.scenario_name for r in refuted)
        )


def test_run_self_test_bundles_land_under_tier_subdirs(fast_self_test):
    """Bundles must land at <root>/<tier>/<scenario>/<bundle>/proof.json
    (0.59.0+ layout)."""
    _, proofs_root = fast_self_test
    for bundle_json in proofs_root.rglob("proof.json"):
        parts = bundle_json.relative_to(proofs_root).parts
        # tier / scenario / bundle / proof.json
        assert len(parts) == 4, f"unexpected depth for {bundle_json}: {parts}"


def test_run_self_test_result_to_dict_is_json_serializable(fast_self_test):
    result, _ = fast_self_test
    payload = result.to_dict()
    # round-trip must succeed (no orphan dataclass / Path / etc.)
    serialized = json.dumps(payload)
    parsed = json.loads(serialized)
    assert parsed["n_total"] == result.n_total


def test_run_self_test_handles_unregistered_scenario_gracefully(tmp_path, monkeypatch):
    """If SELF_TEST_SCENARIOS references a name not in SCENARIOS, the
    runner records an ERROR row but continues — doesn't abort the loop."""
    from ophamin.self_test import SELF_TEST_SCENARIOS as _orig
    import ophamin.self_test as mod
    monkeypatch.setattr(mod, "SELF_TEST_SCENARIOS", (
        ("spearman-crosscheck", {}),
        ("nonexistent-scenario-xyzzy", {}),
    ))
    result = run_self_test(
        proofs_root=tmp_path / "out", formats=BundleFormat.json_only(),
    )
    assert result.n_total == 2
    assert result.n_errored == 1
    error_row = next(r for r in result.results if r.verdict == "ERROR")
    assert error_row.scenario_name == "nonexistent-scenario-xyzzy"
    assert "not in registry" in error_row.error


# --------------------------------------------------------------------------
# Workflow file invariants
# --------------------------------------------------------------------------

def test_workflow_file_exists():
    assert WORKFLOW.is_file()


def test_workflow_parses_as_yaml():
    yaml.safe_load(WORKFLOW.read_text())


@pytest.fixture(scope="module")
def workflow():
    return yaml.safe_load(WORKFLOW.read_text())


def test_workflow_triggers_on_push_pr_and_dispatch(workflow):
    # PyYAML parses unquoted `on:` as the Python literal True (boolean
    # YAML true/yes/on). Handle both shapes for forward-compat.
    triggers = workflow.get("on") or workflow.get(True)
    assert triggers, "workflow must declare an `on:` block"
    assert "push" in triggers
    assert "pull_request" in triggers
    assert "workflow_dispatch" in triggers


def test_workflow_has_concurrency_group(workflow):
    assert workflow.get("concurrency", {}).get("cancel-in-progress") is True


def test_workflow_has_minimal_permissions(workflow):
    assert workflow.get("permissions", {}).get("contents") == "read"


def test_workflow_has_self_test_step(workflow):
    steps = workflow["jobs"]["self-test"]["steps"]
    names = [s.get("name", "") for s in steps]
    assert any("Run self-test" in n for n in names)


def test_workflow_installs_latex_for_pdf_renders(workflow):
    """The PDF render needs latexmk on the runner."""
    steps = workflow["jobs"]["self-test"]["steps"]
    found = any(
        "latexmk" in s.get("run", "") and "apt-get install" in s.get("run", "")
        for s in steps
    )
    assert found, "workflow must install latexmk"


def test_workflow_uploads_bundle_artifact(workflow):
    steps = workflow["jobs"]["self-test"]["steps"]
    found = any(
        "actions/upload-artifact" in str(s.get("uses", ""))
        and "ophamin-self-test" in str(s.get("with", {}).get("name", ""))
        for s in steps
    )
    assert found


def test_workflow_artifact_uploads_even_on_failure(workflow):
    """REFUTED bundles are the most useful — must upload regardless."""
    steps = workflow["jobs"]["self-test"]["steps"]
    upload = next(
        s for s in steps
        if "actions/upload-artifact" in str(s.get("uses", ""))
    )
    assert upload.get("if") == "always()"


def test_workflow_artifact_uses_v4_or_higher(workflow):
    steps = workflow["jobs"]["self-test"]["steps"]
    upload = next(
        s for s in steps
        if "actions/upload-artifact" in str(s.get("uses", ""))
    )
    version_tag = upload["uses"].split("@")[-1]
    assert version_tag.startswith(("v4", "v5"))


def test_workflow_artifact_includes_sha_in_name(workflow):
    steps = workflow["jobs"]["self-test"]["steps"]
    upload = next(
        s for s in steps
        if "actions/upload-artifact" in str(s.get("uses", ""))
    )
    assert "github.sha" in upload["with"]["name"]
