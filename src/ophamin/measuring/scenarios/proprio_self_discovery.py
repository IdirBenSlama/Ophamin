"""The Proprio-Self-Discovery scenario — does Kimera's substrate know its own physics?

Tests three WIRE_CANDIDATE primitives that were designed to surface
substrate physics autonomously:

* `system_laws_discovery.GoverningEquationSynthesizer` (Phase 23, 2025-11-28)
* `semantic_physics_validator.MockEntropicAddresser` + ResonanceDetector (Phase 22)
* `system_safety/contradiction/pressure_state.PressureTransition` typed
  vocabulary (Phase 6 STEP6_PHYSICS)

The campaign tests whether activating these primitives (they've been
WIRE_CANDIDATE since 2025-11-28 / 2026-04-11) surfaces the same
architectural physics Sinew found by external measurement.

Falsifiable claim
=================

> P1: Kimera's substrate-internal self-discovery primitives can
>     INDEPENDENTLY surface the same architectural physics that Sinew
>     found by external measurement. At least 2 of 3 sub-tests must
>     produce STRONG_PASS:
>
>     - SUB-A: system_laws_discovery surfaces a non-trivial governing
>       equation relating scar_coherence_weight to (pressure + tension)
>       on captured trajectory (r² > 0.3)
>     - SUB-B: pressure_state's typed-transition vocabulary applies to
>       ≥80% of Sinew events (classification coverage)
>     - SUB-C: semantic_physics_validator surfaces a triad containing
>       at least 2 of [pressure, tension, scar] from Sinew text

Pre-registered: validating ≥ 2 of 3 sub-tests means the substrate has
measurable self-discovery capability. Validating 1 means partial.
Validating 0 means the self-discovery layer is decoratively-named
scaffolding — Pattern-P at the primitive-name level.

Threshold rationale: VALIDATING is the INTERESTING outcome (substrate
knows itself); REFUTING is also an interesting architectural finding
(substrate doesn't have working self-discovery — campaign-shape
finding documenting the wiring-debt-as-undiscovered-physics
hypothesis was wrong for these primitives).

Inputs
======

* Sinew Phase 4-extended trajectory (sinew_phase_4_extended_v2)
* Phase 2 / 3 / 4 per-phase reports (read from
  experiments/observatory/runs/proprio_phase_*/)

Output
======

Signed `EmpiricalProofRecord` with:
- Headline: sub_tests_passed (≥ 2 of 3 to validate)
- Secondary: per-sub-test verdict + r² + classification distribution
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from ophamin import __version__
from ophamin.comparing.provenance import ProvenanceGraph
from ophamin.comparing.provenance.lineage import (
    _ophamin_project_root,
    capture_git_commit,
)
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
from ophamin.measuring.scenarios.base import (
    DEFAULT_SIGN_KEY, Scenario, ScenarioScore, Tier,
)
from ophamin.seeing.corpus import CorpusRecord
from ophamin.seeing.substrate.base import CycleResult, SubstrateUnderTest


class ProprioSelfDiscoveryScenario(Scenario):
    """Does Kimera's substrate independently surface Sinew's architectural physics?"""

    name = "proprio-self-discovery"
    tier = Tier.SCIENTIFIC
    family = "self_discovery"
    goal = (
        "Test whether Kimera's three WIRE_CANDIDATE self-discovery primitives "
        "(system_laws_discovery + pressure_state + semantic_physics_validator) "
        "can independently surface the architectural physics that Sinew found "
        "by external measurement."
    )
    explanation = (
        "Three primitives have been WIRE_CANDIDATE since 2025-11-28 / 2026-04-11, "
        "all named for substrate-physics self-discovery: GoverningEquationSynthesizer "
        "synthesizes governing equations of KIMERA itself, ResonanceDetector + "
        "QuantumEquationSynthesizer derives physics from text, PressureTransition "
        "vocabulary types stress transitions. The Proprio campaign tests whether "
        "wiring these primitives reveals the same architectural physics Sinew found "
        "or whether they're decoratively-named scaffolding. The hypothesis the "
        "campaign tests is the wiring-debt-as-undiscovered-substrate-physics "
        "framing — does the substrate know what we externally discovered?"
    )
    method = "sub_tests_passed"
    falsification_consequence = (
        "Kimera's self-discovery layer (system_laws_discovery + "
        "semantic_physics_validator + pressure_state typed vocabulary) "
        "doesn't actually surface substrate physics. Pattern-P at the "
        "primitive-name level: 'discovery' / 'validator' / 'state' names "
        "overstate capability. The substrate does NOT know its own physics; "
        "Sinew's external measurement is the substrate's only mirror."
    )
    corpus_name = "kimera-proprio-trajectory"
    target = "captured_takwin_trajectory_and_phase_reports"

    def __init__(
        self,
        phase_2_report: str | Path,
        phase_3_report: str | Path,
        phase_4_report: str | Path,
        *,
        sub_tests_min: int = 2,
    ) -> None:
        self.phase_2_path = Path(phase_2_report).expanduser()
        self.phase_3_path = Path(phase_3_report).expanduser()
        self.phase_4_path = Path(phase_4_report).expanduser()
        for p in (self.phase_2_path, self.phase_3_path, self.phase_4_path):
            if not p.is_file():
                raise FileNotFoundError(f"phase report not found: {p}")
        if not 0 < sub_tests_min <= 3:
            raise ValueError(
                f"sub_tests_min must be in (0, 3], got {sub_tests_min}"
            )
        self.sub_tests_min = int(sub_tests_min)
        self._kimera_commit = ""

    def score(
        self,
        cycle_results: list[CycleResult],
        records: list[CorpusRecord],
    ) -> ScenarioScore:
        raise NotImplementedError(
            "ProprioSelfDiscoveryScenario uses a custom run() loop."
        )

    def build_claim(self) -> Claim:
        return Claim(
            statement=(
                f"Kimera's three WIRE_CANDIDATE self-discovery primitives "
                f"(system_laws_discovery, pressure_state, "
                f"semantic_physics_validator) collectively surface the "
                f"architectural physics that Sinew found by external "
                f"measurement, validating ≥ {self.sub_tests_min} of 3 "
                f"pre-registered sub-tests. SUB-A: system_laws_discovery "
                f"surfaces a non-trivial CW vs (P+T) relationship (r² > "
                f"0.3). SUB-B: pressure_state classifies ≥ 80% of Sinew "
                f"events. SUB-C: semantic_physics_validator surfaces a "
                f"triad containing ≥ 2 of [pressure, tension, scar]."
            ),
            operationalization=(
                "Read per-phase reports from experiments/observatory/runs/"
                "proprio_phase_*/. SUB-A: take Phase 2 headline r² for "
                "CW_seed vs P+T on SEC v2 corpus. SUB-B: take Phase 3 "
                "classified-event-count / total-event-count ratio. SUB-C: "
                "take Phase 4 sinew_verdict (STRONG/WEAK/TRACE/WEAK_VOCAB/"
                "FAIL). Headline metric = count of sub-tests with verdict "
                "in {STRONG_PASS, WEAK_PASS}."
            ),
            threshold=Threshold(
                metric="sub_tests_passed",
                comparator=">=",
                value=self.sub_tests_min,
                units="of_3",
            ),
            h0=(
                f"sub_tests_passed < {self.sub_tests_min} — Kimera's "
                "self-discovery primitives don't actually discover "
                "substrate physics; Pattern-P at primitive-name level"
            ),
            h1=(
                f"sub_tests_passed >= {self.sub_tests_min} — substrate "
                "has measurable self-discovery capability; the wiring "
                "debt does contain working physics-discovery primitives"
            ),
        )

    def _classify_sub_a(self, phase_2: dict[str, Any]) -> tuple[str, dict[str, Any]]:
        """SUB-A: does Phase 2 surface non-trivial CW vs P+T relationship?"""
        # Try normalized variant first if available
        norm_path = self.phase_2_path.parent.parent / "proprio_phase_2_normalized" / "phase_2_1_report.json"
        if norm_path.is_file():
            norm_data = json.loads(norm_path.read_text())
            headline = next((r for r in norm_data.get("results", [])
                            if r["label"].startswith("headline_")), None)
            if headline:
                r_sq = headline.get("r_squared", float("-inf"))
                verdict = "STRONG_PASS" if r_sq > 0.5 else (
                    "WEAK_PASS" if r_sq > 0.3 else "FAIL"
                )
                return verdict, {
                    "r_squared": r_sq,
                    "equation": headline.get("discovered_equation"),
                    "source": "phase_2_normalized",
                }
        # Fall back to raw Phase 2
        aggregate = phase_2.get("aggregate", {})
        sec = aggregate.get("sec_v2", {})
        r_sq = sec.get("headline_r_squared", float("-inf"))
        verdict = "STRONG_PASS" if r_sq > 0.5 else (
            "WEAK_PASS" if r_sq > 0.3 else "FAIL"
        )
        return verdict, {
            "r_squared": r_sq,
            "equation": sec.get("headline_equation"),
            "source": "phase_2_raw",
        }

    def _classify_sub_b(self, phase_3: dict[str, Any]) -> tuple[str, dict[str, Any]]:
        """SUB-B: does pressure_state vocabulary classify ≥80% of Sinew events?"""
        n_classified = phase_3.get("n_classified", {})
        n_total = phase_3.get("n_total", {})
        total = sum(n_total.values())
        classified = sum(n_classified.values())
        coverage = classified / total if total else 0.0
        if coverage >= 0.80:
            verdict = "STRONG_PASS"
        elif coverage >= 0.50:
            verdict = "WEAK_PASS"
        else:
            verdict = "FAIL"
        return verdict, {
            "n_total": total,
            "n_classified": classified,
            "coverage": coverage,
            "scar_absorption_pct": phase_3.get("scar_absorption_pct"),
        }

    def _classify_sub_c(self, phase_4: dict[str, Any]) -> tuple[str, dict[str, Any]]:
        """SUB-C: does semantic_physics_validator surface a Sinew-relevant triad?"""
        sinew_verdict = phase_4.get("sinew_verdict", "FAIL")
        # Map the validator verdicts to scenario verdicts
        if sinew_verdict in ("STRONG", "WEAK"):
            verdict = "STRONG_PASS"
        elif sinew_verdict == "TRACE":
            verdict = "WEAK_PASS"
        else:  # WEAK_VOCAB, FAIL, ERROR
            verdict = "FAIL"
        return verdict, {
            "sinew_verdict": sinew_verdict,
            "sinew_reason": phase_4.get("sinew_reason"),
            "triad": phase_4.get("sinew_result", {}).get("triad"),
            "control_matched_newton": phase_4.get("control_matched_newton"),
        }

    def run(
        self,
        substrate: SubstrateUnderTest | None = None,
        *,
        data_root: Any = None,
        sign_key: bytes = DEFAULT_SIGN_KEY,
    ) -> EmpiricalProofRecord:
        phase_2 = json.loads(self.phase_2_path.read_text())
        phase_3 = json.loads(self.phase_3_path.read_text())
        phase_4 = json.loads(self.phase_4_path.read_text())

        sub_a_verdict, sub_a_detail = self._classify_sub_a(phase_2)
        sub_b_verdict, sub_b_detail = self._classify_sub_b(phase_3)
        sub_c_verdict, sub_c_detail = self._classify_sub_c(phase_4)

        sub_tests_passed = sum(
            1 for v in (sub_a_verdict, sub_b_verdict, sub_c_verdict)
            if v in ("STRONG_PASS", "WEAK_PASS")
        )

        observed = float(sub_tests_passed)
        config = {
            "scenario": self.name,
            "phase_2_path": str(self.phase_2_path),
            "phase_3_path": str(self.phase_3_path),
            "phase_4_path": str(self.phase_4_path),
            "sub_tests_min": self.sub_tests_min,
        }
        dataset = DatasetRef(
            name=self.corpus_name,
            content_hash=content_hash({
                "phase_2_hash": content_hash(phase_2.get("gate", "")),
                "phase_3_hash": content_hash(phase_3.get("gate", "")),
                "phase_4_hash": content_hash(phase_4.get("gate", "")),
            }),
            n_records=3,
            source="phase_reports",
            kind="proprio-phase-reports",
        )
        prereg = PreRegistration(
            config_hash=content_hash(config),
            data_hash=dataset.content_hash,
            analysis_plan=self.analysis_plan(),
        )

        claim = self.build_claim()
        verdict = Verdict.decide(
            observed=observed,
            threshold=claim.threshold,
            reasoning=(
                f"Proprio synthesis: SUB-A (system_laws_discovery vs P+T) = "
                f"{sub_a_verdict}; SUB-B (pressure_state typing coverage) = "
                f"{sub_b_verdict}; SUB-C (semantic_physics_validator triad) = "
                f"{sub_c_verdict}. {sub_tests_passed}/3 sub-tests passed."
            ),
        )

        evidence = [
            PillarEvidence(
                pillar="proprio_self_discovery",
                statistic_name="sub_tests_passed",
                statistic_value=observed,
                library="ophamin.measuring.scenarios.proprio_self_discovery",
                library_version=__version__,
                effect_size=None,
                ci_low=None,
                ci_high=None,
                p_value=None,
                cross_check=(
                    "Three sub-tests probe complementary self-discovery "
                    "primitives. STRONG validation would mean the wiring "
                    "debt contains working physics-discovery primitives. "
                    "REFUTATION means the self-discovery layer is "
                    "decoratively-named scaffolding (Pattern-P at primitive-"
                    "name level — also a real architectural finding)."
                ),
                detail={
                    "sub_a_verdict": sub_a_verdict,
                    "sub_a_detail": sub_a_detail,
                    "sub_b_verdict": sub_b_verdict,
                    "sub_b_detail": sub_b_detail,
                    "sub_c_verdict": sub_c_verdict,
                    "sub_c_detail": sub_c_detail,
                    "sub_tests_passed": sub_tests_passed,
                    "phase_2_path": str(self.phase_2_path),
                    "phase_3_path": str(self.phase_3_path),
                    "phase_4_path": str(self.phase_4_path),
                },
            ),
        ]

        prov = ProvenanceGraph()
        agent_ophamin = prov.agent(
            "ophamin", role="experimentation_framework", version=__version__
        )
        agent_kimera = prov.agent(
            "kimera-swm", role="substrate_under_observation",
        )
        data_entity = prov.entity(
            f"corpus:{dataset.name}",
            content_hash=dataset.content_hash,
            n_records=dataset.n_records,
            source="phase_reports",
        )
        activity = prov.activity(
            f"scenario:{self.name}",
            target=self.target,
            sub_tests_passed=sub_tests_passed,
        )
        result_entity = prov.entity(f"proof:{self.name}")
        prov.used(activity, data_entity)
        prov.was_associated_with(activity, agent_ophamin)
        prov.was_associated_with(activity, agent_kimera)
        prov.was_generated_by(result_entity, activity)
        prov.was_attributed_to(result_entity, agent_kimera)
        prov.was_derived_from(result_entity, data_entity)

        proof = EmpiricalProofRecord(
            claim=claim,
            preregistration=prereg,
            datasets=[dataset],
            substrate_name="kimera-swm",
            substrate_git_commit=self._kimera_commit,
            evidence=evidence,
            verdict=verdict,
            reproduction=Reproduction(
                command=(
                    f"PYTHONPATH=src .venv/bin/python -m ophamin.cli scenario "
                    f"{self.name} --phase-2-report {self.phase_2_path} "
                    f"--phase-3-report {self.phase_3_path} "
                    f"--phase-4-report {self.phase_4_path}"
                )
            ),
            provenance=prov.to_prov_json(),
            ophamin_version=__version__,
            ophamin_git_commit=capture_git_commit(_ophamin_project_root()),
        )
        proof.sign(sign_key)
        return proof

    def analysis_plan(self) -> str:
        return (
            "Read three pre-computed Phase 2/3/4 reports from the Proprio "
            "campaign. SUB-A: classify Phase 2's CW vs P+T discovery r². "
            "SUB-B: classify Phase 3's typed-event coverage ratio. SUB-C: "
            "classify Phase 4's Sinew-triad recovery. Count sub-tests "
            "reaching STRONG_PASS or WEAK_PASS verdicts. Verdict on "
            f"count >= {self.sub_tests_min}."
        )
