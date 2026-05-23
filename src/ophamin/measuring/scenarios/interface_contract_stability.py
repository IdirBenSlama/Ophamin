"""The Interface Contract Stability scenario — first interface-stratum scientific scenario.

Per the v0.2 reframing (``docs/KIMERA_OBSERVATIONAL_SURFACE_2026_05_15.md``
§4.7), Ophamin v0.1 covered the cognitive stratum exclusively. This scenario
is the first to target the **interface** stratum — REST routers, REST
controllers, GraphQL packages, MCP tools, CLI commands, WebSocket handlers.

Falsifiable claim
=================

> Across every interface-stratum module that ``KimeraInventory.discover_interface``
> reports for a given Kimera commit, at least 95% parse cleanly as Python
> (``ast.parse``) AND declare at least one externally-callable handler
> (a FastAPI/router decorator, an MCP tool registration, a CLI command
> registration, or any top-level ``async def`` / ``def`` of arity ≥ 0).
>
> **Operationalization**: parse_success_rate = (parses_ok AND
> has_handler_decl) / total_interface_modules.
>
> **Threshold**: parse_success_rate ≥ 0.95.

The scenario is **fully static** — does not import Kimera, does not run any
substrate cycle, does not require a running Kimera server. It probes
Kimera's interface stratum at commit time via the existing
``discover_interface`` discoverer.

Why this matters
================

The interface stratum is Kimera's public contract: 47 REST routers, 24
controllers, 10 MCP tools, GraphQL surface, CLI commands. A regression here
breaks every downstream consumer. The Ophamin claim is per-commit drift
detection: if parse_success_rate drops below 95%, something on the
interface boundary moved.

The 5% slack is deliberate — a single in-flight refactor can leave one or
two modules temporarily broken; sustained drift (multiple modules) is the
real signal.
"""

from __future__ import annotations

import ast
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import statsmodels as _statsmodels  # noqa: F401 — Wilson CI computed via proportion_confint
from statsmodels.stats.proportion import proportion_confint

from ophamin import __version__
from ophamin.comparing.provenance.lineage import _ophamin_project_root, capture_git_commit
from ophamin.comparing.provenance import ProvenanceGraph
from ophamin.measuring.proof import (
    Claim,
    DatasetRef,
    EmpiricalProofRecord,
    PillarEvidence,
    PreRegistration,
    Reproduction,
    Threshold,
    Verdict,
    content_hash,
)
from ophamin.measuring.scenarios.base import DEFAULT_SIGN_KEY, Scenario, ScenarioScore, Tier
from ophamin.seeing.corpus import CorpusRecord
from ophamin.seeing.discovery.kimera_inventory import (
    Surface,
    discover_interface,
)
from ophamin.seeing.substrate.base import CycleResult, SubstrateUnderTest


#: ``ast`` node types that indicate "this module exports an externally-callable
#: handler" — what every interface-stratum module SHOULD have.
_HANDLER_NODE_TYPES = (ast.AsyncFunctionDef, ast.FunctionDef)

#: decorators that mark FastAPI / aiohttp / GraphQL / MCP / CLI handlers.
#: A module declaring at least one decorator from this set is considered to
#: have a real handler (vs. helper-only modules).
_HANDLER_DECORATOR_NAMES = frozenset({
    "get", "post", "put", "delete", "patch", "head", "options",   # FastAPI / aiohttp verbs
    "websocket", "rpc", "subscription",                            # GraphQL / WS
    "command", "group", "argument", "option",                      # Click / Typer / Hydra
    "tool", "resource", "prompt",                                  # MCP server decorators
    "router",                                                       # any framework's @router(...)
})


@dataclass
class _ModuleProbe:
    """Per-module probe result — what static analysis recovered about one file."""

    file_path: str
    parses_ok: bool
    has_handler_def: bool             # ≥ 1 top-level (async )def
    has_handler_decorator: bool       # ≥ 1 known handler decorator (FastAPI / MCP / etc.)
    syntax_error: str = ""
    n_classes: int = 0
    n_functions: int = 0
    n_decorators: int = 0

    @property
    def is_contract_compliant(self) -> bool:
        """A module is contract-compliant if it parses AND declares at least
        one top-level handler (function or decorated-class)."""
        if not self.parses_ok:
            return False
        return self.has_handler_def or self.has_handler_decorator

    def to_dict(self) -> dict[str, Any]:
        return {
            "file_path": self.file_path,
            "parses_ok": self.parses_ok,
            "has_handler_def": self.has_handler_def,
            "has_handler_decorator": self.has_handler_decorator,
            "is_contract_compliant": self.is_contract_compliant,
            "syntax_error": self.syntax_error,
            "n_classes": self.n_classes,
            "n_functions": self.n_functions,
            "n_decorators": self.n_decorators,
        }


def _probe_module(kimera_repo: Path, surface: Surface) -> _ModuleProbe | None:
    """Statically inspect one interface-stratum file. Returns ``None`` for
    non-probeable surfaces (package directories, non-Python files) — those
    are valid stratum members but not subject to the AST/handler contract.
    Loud-fail nowhere; the caller filters None.
    """
    full = kimera_repo / surface.file_path
    if not full.is_file() or full.suffix != ".py":
        return None

    text = full.read_text(encoding="utf-8", errors="replace")
    try:
        tree = ast.parse(text, filename=str(full))
    except SyntaxError as e:
        return _ModuleProbe(
            file_path=surface.file_path,
            parses_ok=False,
            has_handler_def=False,
            has_handler_decorator=False,
            syntax_error=f"{type(e).__name__}: {e.msg} at line {e.lineno}",
        )

    n_classes = 0
    n_functions = 0
    n_decorators = 0
    has_handler_def = False
    has_handler_decorator = False
    # Walk top-level declarations + one level into class bodies. FastAPI
    # controllers and Click command groups commonly put handler decorators
    # on class methods (``class GeoidController: @router.get("/")``); a
    # module that ONLY checks the module top would miss the entire
    # controller pattern as non-compliant. One level deep is enough — we
    # don't recurse arbitrarily.
    for node in tree.body:
        if isinstance(node, ast.ClassDef):
            n_classes += 1
            for dec in node.decorator_list:
                n_decorators += 1
                if _decorator_matches_handler(dec):
                    has_handler_decorator = True
            # Check class-method decorators (FastAPI controller pattern).
            for sub in node.body:
                if isinstance(sub, _HANDLER_NODE_TYPES):
                    n_functions += 1
                    has_handler_def = True
                    for dec in sub.decorator_list:
                        n_decorators += 1
                        if _decorator_matches_handler(dec):
                            has_handler_decorator = True
        elif isinstance(node, _HANDLER_NODE_TYPES):
            n_functions += 1
            has_handler_def = True
            for dec in node.decorator_list:
                n_decorators += 1
                if _decorator_matches_handler(dec):
                    has_handler_decorator = True
    return _ModuleProbe(
        file_path=surface.file_path,
        parses_ok=True,
        has_handler_def=has_handler_def,
        has_handler_decorator=has_handler_decorator,
        n_classes=n_classes,
        n_functions=n_functions,
        n_decorators=n_decorators,
    )


def _decorator_matches_handler(node: ast.expr) -> bool:
    """Check whether one decorator node is a known handler decorator.

    Handles three patterns:
      ``@router.get(...)``        → attribute access, name == "get"
      ``@router.post``            → bare attribute, name == "post"
      ``@tool``                   → bare name, matches "tool"
    """
    if isinstance(node, ast.Call):
        return _decorator_matches_handler(node.func)
    if isinstance(node, ast.Attribute):
        return node.attr in _HANDLER_DECORATOR_NAMES
    if isinstance(node, ast.Name):
        return node.id in _HANDLER_DECORATOR_NAMES
    return False


class InterfaceContractStabilityScenario(Scenario):
    """Static-analysis scenario over Kimera's interface stratum.

    Unlike corpus-driven scenarios, this one does not stream a corpus through
    a substrate — it walks the interface surfaces ``discover_interface``
    reports and probes each via ``ast.parse``. The proof record carries
    per-module probe results in the evidence.

    Construct with the Kimera repo path; call ``run()`` (no substrate arg)
    to get a signed ``EmpiricalProofRecord``. The base ``Scenario.run()`` is
    fully overridden because this scenario is static — there is no batch of
    cycles to stream, no corpus to download, no field contract to enforce.

    Slots into the SCENARIOS registry alongside the cognitive-tier scenarios.
    """

    name = "interface-contract-stability"
    tier = Tier.SCIENTIFIC
    family = "interface"
    goal = (
        "Test whether Kimera's interface stratum (REST routers, MCP "
        "tools, GraphQL, CLI commands, WebSocket handlers) is "
        "structurally well-formed at a given commit."
    )
    explanation = (
        "The interface stratum is Kimera's public contract — 47 REST "
        "routers + 24 controllers + 10 MCP tools + GraphQL + CLI. A "
        "regression here breaks every downstream consumer. This "
        "scenario is fully static (no substrate cycle, no running "
        "server): for each interface module the inventory reports, "
        "it parses cleanly as Python AND declares at least one "
        "externally-callable handler. Per-commit drift detection "
        "with 5% slack for in-flight refactors."
    )
    method = "static_parse_proportion"
    falsification_consequence = (
        "More than 5% of interface modules fail to parse OR lack a "
        "callable handler — sustained drift on Kimera's public "
        "contract boundary."
    )
    target = "interface_stratum_static_probe"

    def __init__(self, kimera_repo: Path | str, threshold: float = 0.95) -> None:
        self.kimera_repo = Path(kimera_repo).expanduser().resolve()
        if not self.kimera_repo.is_dir():
            raise FileNotFoundError(f"Kimera repo not a directory: {self.kimera_repo}")
        if not 0.0 < threshold <= 1.0:
            raise ValueError(f"threshold must be in (0, 1], got {threshold}")
        self.threshold = float(threshold)
        self.n_cycles = 0   # static scenario — base.run() is overridden

    def score(
        self,
        cycle_results: list[CycleResult],
        records: list[CorpusRecord],
    ) -> ScenarioScore:
        """Never called — base.run() is overridden. Defined to satisfy ABC."""
        raise NotImplementedError(
            "InterfaceContractStabilityScenario uses a custom run() loop; "
            "score() is unreachable."
        )

    # ----------------------------------------------------------------- claim --

    def build_claim(self) -> Claim:
        return Claim(
            statement=(
                "Across every Python module in Kimera-SWM's interface stratum "
                "(REST routers + controllers, GraphQL surface, MCP tools, CLI "
                "commands, WebSocket handlers), at least 95% are structurally "
                "intact (parse cleanly AND declare at least one externally-"
                "callable handler)."
            ),
            operationalization=(
                "contract_compliance_rate = "
                "(parses_ok AND (has_handler_def OR has_handler_decorator)) / "
                "total_interface_modules. ast.parse run on each module; "
                "decorators matched against a known handler-name allowlist "
                "(FastAPI verbs, Click commands, MCP tool/resource/prompt, etc.)."
            ),
            threshold=Threshold(
                metric="contract_compliance_rate",
                comparator=">=",
                value=self.threshold,
                units="proportion",
            ),
            h0=(
                "H0: structural breakage exceeds 5% — the interface contract "
                "is unstable at this Kimera commit"
            ),
            h1=(
                "H1: structural breakage is ≤ 5% — the interface contract "
                "holds at this Kimera commit"
            ),
        )

    def analysis_plan(self) -> str:
        return (
            f"Run KimeraInventory.discover_interface against {self.kimera_repo}. "
            f"For every Python module among the reported surfaces, parse with "
            f"``ast.parse`` and inspect top-level node types. Aggregate into "
            f"contract_compliance_rate; decide against threshold "
            f"≥ {self.threshold:.2%} with a Wilson 95% CI."
        )

    # ------------------------------------------------------------------ run --

    def run(
        self,
        substrate: SubstrateUnderTest | None = None,
        *,
        data_root: str | Path | None = None,
        sign_key: bytes = DEFAULT_SIGN_KEY,
    ) -> EmpiricalProofRecord:
        """Probe every interface-stratum module, aggregate, emit signed record."""
        stratum = discover_interface(self.kimera_repo)
        raw_probes = [_probe_module(self.kimera_repo, s) for s in stratum.surfaces]
        # Drop non-probeable surfaces (package dirs, non-.py files).
        py_probes: list[_ModuleProbe] = [p for p in raw_probes if p is not None]
        n_total = len(py_probes)
        n_compliant = sum(1 for p in py_probes if p.is_contract_compliant)
        observed_value = (n_compliant / n_total) if n_total else 0.0

        # Wilson 95% CI for the compliance proportion.
        if n_total:
            ci_low, ci_high = proportion_confint(
                count=n_compliant, nobs=n_total, alpha=0.05, method="wilson"
            )
        else:
            ci_low = ci_high = 0.0

        # PRE-REGISTRATION — config + data hashed BEFORE the verdict.
        # NOTE: ``contracted_paths`` is a list of file_paths so the data hash is
        # stable across runs against the same Kimera commit.
        config = {
            "scenario": self.name,
            "kimera_repo": str(self.kimera_repo),
            "threshold": self.threshold,
            "n_surfaces": stratum.count,
            "n_python_modules": n_total,
        }
        contracted_paths = sorted(p.file_path for p in py_probes)
        data_payload = {"file_paths": contracted_paths}
        dataset = DatasetRef(
            name="kimera-interface-stratum",
            content_hash=content_hash(data_payload),
            n_records=n_total,
            source=str(self.kimera_repo),
            kind="static-inventory",
        )
        prereg = PreRegistration(
            config_hash=content_hash(config),
            data_hash=dataset.content_hash,
            analysis_plan=self.analysis_plan(),
        )

        # SCORE -> VERDICT
        claim = self.build_claim()
        verdict = Verdict.decide(
            observed=observed_value,
            threshold=claim.threshold,
            reasoning=(
                f"{n_compliant}/{n_total} interface-stratum modules are "
                f"contract-compliant ({observed_value:.4f}); Wilson 95% CI "
                f"[{ci_low:.4f}, {ci_high:.4f}]"
            ),
        )

        # EVIDENCE — one pillar carries the raw probe results.
        import statsmodels as _sm
        evidence = [
            PillarEvidence(
                pillar="static_ast_parse",
                statistic_name="contract_compliance_rate",
                statistic_value=observed_value,
                library="statsmodels",
                library_version=getattr(_sm, "__version__", "unknown"),
                effect_size=None,
                ci_low=ci_low,
                ci_high=ci_high,
                p_value=None,
                cross_check="n/a",
                detail={
                    "n_total": n_total,
                    "n_compliant": n_compliant,
                    "n_non_compliant": n_total - n_compliant,
                    "ci_method": "wilson_95%",
                    "non_compliant_files": [
                        p.file_path for p in py_probes if not p.is_contract_compliant
                    ][:50],
                    "syntax_errors": [
                        {"file": p.file_path, "error": p.syntax_error}
                        for p in py_probes if p.syntax_error
                    ][:50],
                    "stratum_total_surfaces": stratum.count,
                    "stratum_expected_count": stratum.expected_count,
                },
            ),
        ]

        # PROVENANCE
        prov = ProvenanceGraph()
        agent_ophamin = prov.agent(
            "ophamin", role="experimentation_framework", version=__version__
        )
        agent_kimera = prov.agent(
            "kimera-swm", role="substrate_under_static_audit",
        )
        data_entity = prov.entity(
            f"corpus:{dataset.name}",
            content_hash=dataset.content_hash,
            n_records=dataset.n_records,
            kind=dataset.kind,
        )
        activity = prov.activity(
            f"scenario:{self.name}",
            target=self.target,
            n_modules=n_total,
        )
        result_entity = prov.entity(f"proof:{self.name}")
        prov.used(activity, data_entity)
        prov.was_associated_with(activity, agent_ophamin)
        prov.was_associated_with(activity, agent_kimera)
        prov.was_generated_by(result_entity, activity)
        prov.was_attributed_to(result_entity, agent_kimera)
        prov.was_derived_from(result_entity, data_entity)

        record = EmpiricalProofRecord(
            claim=claim,
            preregistration=prereg,
            datasets=[dataset],
            substrate_name="kimera-swm",
            substrate_git_commit=_capture_kimera_commit(self.kimera_repo),
            evidence=evidence,
            verdict=verdict,
            reproduction=Reproduction(

                command=self._build_reproduction_command(),

            ),
            provenance=prov.to_prov_json(),
            ophamin_version=__version__,
            ophamin_git_commit=capture_git_commit(_ophamin_project_root()),
        )
        record.sign(sign_key)
        return record


def _capture_kimera_commit(kimera_repo: Path) -> str:
    """Best-effort capture of Kimera's HEAD commit (delegates to the inventory helper)."""
    from ophamin.seeing.discovery.kimera_inventory import _capture_kimera_commit as _h
    return _h(kimera_repo)
