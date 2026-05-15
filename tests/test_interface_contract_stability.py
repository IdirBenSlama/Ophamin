"""Tests for InterfaceContractStabilityScenario — the first interface-stratum
scientific scenario.

Fixture strategy: build a synthetic Kimera tree where we control parse-ability
and handler-decorator presence per-file. No real Kimera dependency.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from ophamin.measuring.proof import EmpiricalProofRecord, VALIDATED, REFUTED
from ophamin.measuring.scenarios.interface_contract_stability import (
    InterfaceContractStabilityScenario,
    _decorator_matches_handler,
    _probe_module,
)


_COMPLIANT_TOP_LEVEL = """\
from fastapi import APIRouter
router = APIRouter()

@router.get("/health")
async def health():
    return {"status": "ok"}
"""

_COMPLIANT_CLASS_METHOD = """\
from fastapi import APIRouter
router = APIRouter()

class GeoidController:
    @router.get("/geoid")
    async def list_geoids(self):
        return []
"""

_COMPLIANT_MCP_TOOL = """\
from mcp.server import Server
server = Server("kimera")

@server.tool()
def query_arachne(prompt: str) -> dict:
    return {"prompt": prompt}
"""

_NON_COMPLIANT_NO_HANDLER = """\
from pydantic import BaseModel

class GeoidSchema(BaseModel):
    name: str
    radius: float

# Pure schema module — no router/handler decorators
"""

_NON_COMPLIANT_HELPER_ONLY = """\
DEFAULT_TIMEOUT = 30

def _internal_helper():
    return DEFAULT_TIMEOUT * 2
"""

_SYNTAX_BROKEN = """\
def broken(:
    pass
"""


def _build_fake_kimera(tmp_path: Path, files: dict[str, str]) -> Path:
    """Build a minimal Kimera repo with the given interface-stratum files."""
    for rel, content in files.items():
        p = tmp_path / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content, encoding="utf-8")
    return tmp_path


# --------------------------------------------------------------------------
# _decorator_matches_handler
# --------------------------------------------------------------------------


import ast


def _parse_first_decorator(src: str) -> ast.expr:
    """Helper: pull the first decorator out of source for testing the matcher."""
    tree = ast.parse(src)
    for node in tree.body:
        if hasattr(node, "decorator_list") and node.decorator_list:
            return node.decorator_list[0]
    raise AssertionError("no decorator found in source")


def test_decorator_matcher_recognises_router_get():
    dec = _parse_first_decorator("@router.get('/x')\ndef f(): pass")
    assert _decorator_matches_handler(dec)


def test_decorator_matcher_recognises_bare_attribute_decorator():
    dec = _parse_first_decorator("@router.post\ndef f(): pass")
    assert _decorator_matches_handler(dec)


def test_decorator_matcher_recognises_bare_name_tool():
    dec = _parse_first_decorator("@tool\ndef f(): pass")
    assert _decorator_matches_handler(dec)


def test_decorator_matcher_recognises_click_command():
    dec = _parse_first_decorator("@click.command()\ndef f(): pass")
    assert _decorator_matches_handler(dec)


def test_decorator_matcher_rejects_arbitrary_decorator():
    dec = _parse_first_decorator("@staticmethod\ndef f(): pass")
    assert not _decorator_matches_handler(dec)


def test_decorator_matcher_rejects_dataclass():
    dec = _parse_first_decorator("@dataclass\nclass C: pass")
    assert not _decorator_matches_handler(dec)


# --------------------------------------------------------------------------
# _probe_module — per-file static analysis
# --------------------------------------------------------------------------


def test_probe_module_returns_none_for_non_python_files(tmp_path):
    p = tmp_path / "kimera_swm/x.txt"
    p.parent.mkdir(parents=True)
    p.write_text("not python")

    from ophamin.seeing.discovery.kimera_inventory import Surface
    surf = Surface(name="x", kind="config_file", file_path="kimera_swm/x.txt",
                   line_count=1, metadata={})
    assert _probe_module(tmp_path, surf) is None


def test_probe_module_returns_none_for_package_dirs(tmp_path):
    (tmp_path / "kimera_swm/pkg").mkdir(parents=True)
    from ophamin.seeing.discovery.kimera_inventory import Surface
    surf = Surface(name="pkg", kind="package_dir", file_path="kimera_swm/pkg",
                   line_count=0, metadata={})
    assert _probe_module(tmp_path, surf) is None


def test_probe_module_detects_compliant_top_level_handler(tmp_path):
    p = tmp_path / "kimera_swm/api/routers/foo.py"
    p.parent.mkdir(parents=True)
    p.write_text(_COMPLIANT_TOP_LEVEL)

    from ophamin.seeing.discovery.kimera_inventory import Surface
    surf = Surface(name="foo", kind="module",
                   file_path="kimera_swm/api/routers/foo.py", line_count=8,
                   metadata={})
    probe = _probe_module(tmp_path, surf)
    assert probe is not None
    assert probe.parses_ok
    assert probe.has_handler_def
    assert probe.has_handler_decorator
    assert probe.is_contract_compliant


def test_probe_module_detects_class_method_handler(tmp_path):
    p = tmp_path / "kimera_swm/interfaces/rest/controllers/foo.py"
    p.parent.mkdir(parents=True)
    p.write_text(_COMPLIANT_CLASS_METHOD)

    from ophamin.seeing.discovery.kimera_inventory import Surface
    surf = Surface(name="foo", kind="module",
                   file_path="kimera_swm/interfaces/rest/controllers/foo.py",
                   line_count=10, metadata={})
    probe = _probe_module(tmp_path, surf)
    assert probe is not None
    assert probe.parses_ok
    assert probe.has_handler_decorator       # decorator on class method
    assert probe.has_handler_def              # the method itself counts
    assert probe.is_contract_compliant


def test_probe_module_detects_mcp_tool_decorator(tmp_path):
    p = tmp_path / "kimera_swm/interfaces/mcp/tools/foo.py"
    p.parent.mkdir(parents=True)
    p.write_text(_COMPLIANT_MCP_TOOL)

    from ophamin.seeing.discovery.kimera_inventory import Surface
    surf = Surface(name="foo", kind="module",
                   file_path="kimera_swm/interfaces/mcp/tools/foo.py",
                   line_count=8, metadata={})
    probe = _probe_module(tmp_path, surf)
    assert probe.is_contract_compliant


def test_probe_module_marks_pure_schema_as_non_compliant(tmp_path):
    p = tmp_path / "kimera_swm/api/routers/schemas.py"
    p.parent.mkdir(parents=True)
    p.write_text(_NON_COMPLIANT_NO_HANDLER)

    from ophamin.seeing.discovery.kimera_inventory import Surface
    surf = Surface(name="schemas", kind="module",
                   file_path="kimera_swm/api/routers/schemas.py", line_count=8,
                   metadata={})
    probe = _probe_module(tmp_path, surf)
    assert probe.parses_ok
    assert not probe.has_handler_decorator   # no FastAPI-style decorator
    # has_handler_def is False (no top-level function); is_contract_compliant False
    assert not probe.is_contract_compliant


def test_probe_module_compliant_when_helper_function_exists(tmp_path):
    """A module with a top-level `def` (even private) satisfies has_handler_def.
    This is intentional — interface-stratum modules with private helpers are
    still "structurally well-formed" by our contract; the operator can tighten
    the threshold if they want stricter coverage.
    """
    p = tmp_path / "kimera_swm/interfaces/cli/commands/util.py"
    p.parent.mkdir(parents=True)
    p.write_text(_NON_COMPLIANT_HELPER_ONLY)

    from ophamin.seeing.discovery.kimera_inventory import Surface
    surf = Surface(name="util", kind="module",
                   file_path="kimera_swm/interfaces/cli/commands/util.py",
                   line_count=4, metadata={})
    probe = _probe_module(tmp_path, surf)
    assert probe.parses_ok
    assert probe.has_handler_def              # has a top-level def
    assert probe.is_contract_compliant         # contract treats this as compliant


def test_probe_module_records_syntax_error(tmp_path):
    p = tmp_path / "kimera_swm/api/routers/broken.py"
    p.parent.mkdir(parents=True)
    p.write_text(_SYNTAX_BROKEN)

    from ophamin.seeing.discovery.kimera_inventory import Surface
    surf = Surface(name="broken", kind="module",
                   file_path="kimera_swm/api/routers/broken.py", line_count=3,
                   metadata={})
    probe = _probe_module(tmp_path, surf)
    assert not probe.parses_ok
    assert probe.syntax_error
    assert "SyntaxError" in probe.syntax_error
    assert not probe.is_contract_compliant


# --------------------------------------------------------------------------
# Scenario end-to-end against synthetic Kimera trees
# --------------------------------------------------------------------------


@pytest.fixture
def healthy_kimera_tree(tmp_path):
    """A fake Kimera with 6 fully-compliant interface modules → ≥95% trivially."""
    files = {}
    # 5 routers with top-level handlers
    for i in range(5):
        files[f"kimera_swm/api/routers/router_{i}.py"] = _COMPLIANT_TOP_LEVEL
    # 5 controllers with class-method handlers
    for i in range(5):
        files[f"kimera_swm/interfaces/rest/controllers/ctrl_{i}.py"] = _COMPLIANT_CLASS_METHOD
    # 5 MCP tools
    for i in range(5):
        files[f"kimera_swm/interfaces/mcp/tools/tool_{i}.py"] = _COMPLIANT_MCP_TOOL
    # 5 CLI command modules (top-level def — counts as handler_def)
    for i in range(5):
        files[f"kimera_swm/interfaces/cli/commands/cmd_{i}.py"] = _NON_COMPLIANT_HELPER_ONLY
    # Ensure at least 20 modules so the stratum is "live"
    return _build_fake_kimera(tmp_path, files)


@pytest.fixture
def broken_kimera_tree(tmp_path):
    """A fake Kimera where 6/20 modules are non-compliant (70% rate)."""
    files = {}
    for i in range(14):
        files[f"kimera_swm/api/routers/r_{i}.py"] = _COMPLIANT_TOP_LEVEL
    for i in range(6):
        files[f"kimera_swm/api/routers/broken_{i}.py"] = _NON_COMPLIANT_NO_HANDLER
    return _build_fake_kimera(tmp_path, files)


def test_scenario_validated_on_healthy_tree(healthy_kimera_tree):
    s = InterfaceContractStabilityScenario(healthy_kimera_tree)
    record = s.run()
    assert isinstance(record, EmpiricalProofRecord)
    assert record.verdict.outcome == VALIDATED
    assert record.verdict.observed_value >= 0.95


def test_scenario_refuted_on_broken_tree(broken_kimera_tree):
    s = InterfaceContractStabilityScenario(broken_kimera_tree, threshold=0.95)
    record = s.run()
    assert record.verdict.outcome == REFUTED
    assert record.verdict.observed_value < 0.95


def test_scenario_evidence_lists_non_compliant_files(broken_kimera_tree):
    s = InterfaceContractStabilityScenario(broken_kimera_tree)
    record = s.run()
    non_compliant = record.evidence[0].detail["non_compliant_files"]
    assert len(non_compliant) == 6
    for path in non_compliant:
        assert "broken_" in path


def test_scenario_threshold_validation():
    with pytest.raises(ValueError, match="threshold must be in"):
        InterfaceContractStabilityScenario(
            kimera_repo=Path("/tmp"), threshold=1.5,
        )


def test_scenario_loud_failure_on_missing_repo(tmp_path):
    nonexistent = tmp_path / "no_such_kimera"
    with pytest.raises(FileNotFoundError):
        InterfaceContractStabilityScenario(nonexistent)


def test_scenario_proof_record_is_signed(healthy_kimera_tree):
    s = InterfaceContractStabilityScenario(healthy_kimera_tree)
    record = s.run()
    assert record.signature, "proof record must be signed"


def test_scenario_records_wilson_ci(healthy_kimera_tree):
    s = InterfaceContractStabilityScenario(healthy_kimera_tree)
    record = s.run()
    ev = record.evidence[0]
    assert ev.ci_low is not None
    assert ev.ci_high is not None
    # Allow a small numeric tolerance for the upper bound — Wilson CI can
    # round to 0.9999... when the observed proportion is exactly 1.0.
    eps = 1e-9
    assert 0.0 <= ev.ci_low <= ev.statistic_value
    assert ev.statistic_value <= ev.ci_high + eps
    assert ev.ci_high <= 1.0 + eps
    assert ev.detail["ci_method"] == "wilson_95%"


def test_scenario_is_in_global_registry():
    from ophamin.measuring.scenarios import SCENARIOS
    assert "interface-contract-stability" in SCENARIOS
    assert SCENARIOS["interface-contract-stability"] is InterfaceContractStabilityScenario


def test_scenario_claim_has_h0_h1_and_threshold(healthy_kimera_tree):
    s = InterfaceContractStabilityScenario(healthy_kimera_tree)
    claim = s.build_claim()
    assert claim.h0
    assert claim.h1
    assert claim.threshold.comparator == ">="
    assert claim.threshold.value == 0.95
