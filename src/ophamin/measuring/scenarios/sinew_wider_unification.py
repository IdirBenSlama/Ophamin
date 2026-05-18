"""The Sinew-Wider-Unification scenario — Phase 5 of the original Sinew
campaign plan: test whether Kimera's physics-named primitives
(thermodynamic / quantum / entropy / prime energy) fit the
(P + T + CW_seed) conservation framework or sit outside it.

Per the original Sinew campaign discipline (2026-05-17, pre-registered in
`experiments/observatory/proposals/sinew_campaign.md`): Phase 5 is
empirically permitted because Phase 4-extended produced STRONG_PASS at
substrate decision-points. The architectural commitment ("bring physics
primitives under the framework") remains Tier-3 owner-territory; this
scenario does the EMPIRICAL TEST — pure post-hoc, no substrate touch.

Falsifiable claim
=================

> SU1: For each of the 11 energy-named OrchestratorResult fields plus
>      prime_log_energy (12 candidates total), test whether adding the
>      field as a normalized 4th term to (P + T + CW_seed) is COMPATIBLE
>      with conservation at Walker M4 events. Compatible = best-sign
>      4-term ratio does NOT exceed (3-term baseline + 0.01). At least
>      8 of 12 candidates must be compatible.

Threshold rationale: the 3-term baseline (P+T+CW_seed) measures 0.087 at
walker_m4 (Sinew Phase 4-extended STRONG_PASS). A "compatible" 4th term
contributes either a tightening signal (extends conservation) or sits
inside the noise floor of the 3-term sum (independent, doesn't break).
Pre-registering 8/12 = 2/3 majority bar: if fewer than 8 fields fit, the
substrate's physics-named primitives are decoratively-named (Pattern-P)
relative to the conservation framework. If 8 or more fit, the substrate
has measurable physics-grade coherence at the conservation layer.

REFUTED would mean Kimera's substrate has physics-named primitives that
don't actually fit a conservation framework — most are decorative or
sit in different physics regimes than the SCAR-coherence-weighted
stress conservation discovered at Phase 4-extended.

Per-candidate verdicts (secondary characterizations, no headline):
  * EXTENDS:    4-term ratio < (baseline - 0.01), strict improvement
  * COMPATIBLE: 4-term ratio in [baseline-0.01, baseline+0.01], noise floor
  * BREAKS:     4-term ratio > (baseline + 0.01), strict degradation

Inputs
======

Sinew Phase 4-extended trajectory (same format as sinew-conservation +
sinew-modulation-disruption). Requires the 11 energy fields + the
top-level prime_log_energy field to be captured per cycle (the standard
Sinew v2 capture format does this).

Output
======

Signed EmpiricalProofRecord with:
- Headline: compatible_or_extends_count (≥ 8 of 12 to validate)
- Secondary: per-candidate verdict + ratio improvement + best sign
- Architectural reading: which physics layers fit the conservation,
  which sit outside
"""

from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any

import numpy as np

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
from ophamin.measuring.scenarios.base import DEFAULT_SIGN_KEY, Scenario, ScenarioScore, Tier
from ophamin.measuring.scenarios.sinew_conservation import (
    _PRESSURE_FIELDS,
    _TENSION_FIELDS,
    _aggregate_avg,
    _aggregate_field,
    _conservation_test,
    _detect_events,
    _normalize,
)
from ophamin.seeing.corpus import CorpusRecord
from ophamin.seeing.substrate.base import CycleResult, SubstrateUnderTest


# The 12 physics-named candidates: 11 energy fields + prime_log_energy
_PHYSICS_CANDIDATES = (
    ("energy", "quantum_energy"),
    ("energy", "spde_ground_energy"),
    ("energy", "entanglement_entropy"),
    ("energy", "riemann_zeta_entropy"),
    ("energy", "riemann_zeta_free_energy"),
    ("energy", "crystal_binding_energy"),
    ("energy", "quantum_interference_entropy"),
    ("energy", "quantum_prime_basis_entropy"),
    ("energy", "rosetta_composition_entropy"),
    ("energy", "voronoi_neighbourhood_entropy"),
    ("energy", "turing_pattern_entropy"),
    ("top", "prime_log_energy"),
)


def _aggregate_top_level(records: list[dict[str, Any]], field: str) -> np.ndarray:
    """Per-cycle scalar from records[i][field] (top-level)."""
    out: list[float] = []
    for r in records:
        if r.get("crashed"):
            out.append(float("nan"))
            continue
        v = r.get(field, 0.0)
        out.append(float(v) if isinstance(v, (int, float)) else float("nan"))
    return np.array(out, dtype=float)


def _classify_4term(baseline: float, four_term: float, margin: float = 0.01) -> str:
    """Classify 4-term result vs baseline given ±margin noise floor."""
    if four_term < baseline - margin:
        return "EXTENDS"
    elif four_term > baseline + margin:
        return "BREAKS"
    else:
        return "COMPATIBLE"


class SinewWiderUnificationScenario(Scenario):
    """Test whether Kimera's physics-named primitives fit the Sinew conservation framework."""

    name = "sinew-wider-unification"
    tier = Tier.SCIENTIFIC
    family = "conservation"
    goal = (
        "Test whether each of Kimera's 12 physics-named primitives "
        "(11 energy fields + prime_log_energy) is COMPATIBLE with the "
        "Phase 137 SEED conservation framework discovered in Sinew "
        "Phase 4-extended — i.e. adding the primitive as a 4th term to "
        "(P + T + CW_seed) does not increase the conservation ratio."
    )
    explanation = (
        "Phase 5 of the original Sinew campaign plan. The 6-phase plan "
        "(experiments/observatory/proposals/sinew_campaign.md) pre-"
        "registered Phase 5 as conditional on Phase 4 producing positive "
        "evidence — Phase 4-extended did (X4-ext STRONG_PASS for walker_m4 "
        "at R=0.087). This scenario empirically tests the wider-unification "
        "hypothesis: do Kimera's physics-named primitives actually fit "
        "the conservation framework, or are they decoratively named "
        "(Pattern-P drift)? For each of 12 candidates, test whether the "
        "best-sign 4-term sum (P + T + CW_seed ± candidate) yields a "
        "ratio within or below the 3-term baseline + 0.01 noise floor. "
        "If 8 of 12 are compatible, the substrate's physics-named "
        "primitives have measurable physics-grade coherence at the "
        "conservation layer."
    )
    method = "compatible_or_extends_count"
    falsification_consequence = (
        "Most of Kimera's physics-named primitives don't fit the "
        "Phase 137 SEED conservation framework — they sit in different "
        "physics regimes (or are decoratively named). Pattern-P at the "
        "primitive-name level relative to the architectural finding. "
        "Conservation framework is local to (P + T + CW_seed) rather "
        "than substrate-wide."
    )
    corpus_name = "kimera-sinew-trajectory"
    target = "captured_takwin_trajectory"

    def __init__(
        self,
        trajectory_path: str | Path,
        *,
        compatible_or_extends_min: int = 8,
        noise_floor: float = 0.01,
    ) -> None:
        self.trajectory_path = Path(trajectory_path).expanduser()
        if not self.trajectory_path.is_file():
            raise FileNotFoundError(
                f"trajectory_path not found: {self.trajectory_path}"
            )
        if not 0 < compatible_or_extends_min <= len(_PHYSICS_CANDIDATES):
            raise ValueError(
                f"compatible_or_extends_min must be in (0, "
                f"{len(_PHYSICS_CANDIDATES)}], got {compatible_or_extends_min}"
            )
        if not 0.0 < noise_floor < 0.1:
            raise ValueError(
                f"noise_floor must be in (0, 0.1), got {noise_floor}"
            )
        self.compatible_or_extends_min = int(compatible_or_extends_min)
        self.noise_floor = float(noise_floor)
        # Read commit hash from metadata.json sibling if present
        meta_path = self.trajectory_path.parent / "metadata.json"
        self._kimera_commit = ""
        if meta_path.is_file():
            try:
                meta = json.loads(meta_path.read_text())
                self._kimera_commit = str(meta.get("kimera_commit", ""))
            except (OSError, ValueError, KeyError):
                self._kimera_commit = ""

    def score(
        self,
        cycle_results: list[CycleResult],
        records: list[CorpusRecord],
    ) -> ScenarioScore:
        raise NotImplementedError(
            "SinewWiderUnificationScenario uses a custom run() loop."
        )

    def build_claim(self) -> Claim:
        n_total = len(_PHYSICS_CANDIDATES)
        return Claim(
            statement=(
                f"For each of {n_total} of Kimera's physics-named "
                f"primitives (11 energy-field OrchestratorResult fields + "
                f"prime_log_energy), test whether adding the primitive as "
                f"a normalized 4th term to (P + T + CW_seed) at Walker M4 "
                f"events is COMPATIBLE with the conservation framework "
                f"(best-sign 4-term ratio ≤ 3-term baseline + "
                f"{self.noise_floor}). At least "
                f"{self.compatible_or_extends_min} of {n_total} candidates "
                "must be compatible — measurable physics-grade coherence "
                "at the conservation layer."
            ),
            operationalization=(
                "Compute 3-term baseline ratio (P + T + CW_seed) at "
                "walker_m4 events. For each physics candidate X, test "
                "(P + T + CW_seed + sign · X) with sign ∈ {+1, -1}; "
                "record best-sign 4-term ratio. Classify each candidate: "
                "EXTENDS if ratio < baseline - noise_floor; COMPATIBLE "
                "if within ±noise_floor; BREAKS if > baseline + "
                "noise_floor. Headline metric = count of EXTENDS + "
                "COMPATIBLE candidates."
            ),
            threshold=Threshold(
                metric="compatible_or_extends_count",
                comparator=">=",
                value=self.compatible_or_extends_min,
                units=f"of_{n_total}",
            ),
            h0=(
                f"compatible_or_extends_count < "
                f"{self.compatible_or_extends_min} — Kimera's "
                "physics-named primitives mostly DON'T fit the SEED "
                "conservation framework; Pattern-P at the primitive-name "
                "level; conservation is local to (P + T + CW_seed) rather "
                "than substrate-wide"
            ),
            h1=(
                f"compatible_or_extends_count >= "
                f"{self.compatible_or_extends_min} — substrate's "
                "physics-named primitives DO fit; physics-grade coherence "
                "is measurable at the conservation layer; Phase 5 of the "
                "Sinew campaign produces positive evidence"
            ),
        )

    def run(
        self,
        substrate: SubstrateUnderTest | None = None,
        *,
        data_root: Any = None,
        sign_key: bytes = DEFAULT_SIGN_KEY,
    ) -> EmpiricalProofRecord:
        records = json.loads(self.trajectory_path.read_text())
        if not isinstance(records, list):
            raise ValueError(
                f"trajectory must be JSON list; got {type(records).__name__}"
            )
        n_cycles = len(records)
        if n_cycles < 50:
            raise ValueError(
                f"trajectory has only {n_cycles} cycles; need ≥ 50"
            )

        events = _detect_events(records)
        n_walker_m4 = len(events["walker_m4"])

        # 3-term baseline
        P = _normalize(_aggregate_avg(records, "pressure_proxies", _PRESSURE_FIELDS))
        T = _normalize(_aggregate_avg(records, "tension_proxies", _TENSION_FIELDS))
        CW_seed = _normalize(_aggregate_field(records, "scar", "scar_coherence_weight"))
        total_3 = P + T + CW_seed

        baseline = _conservation_test(total_3, events["walker_m4"])
        if baseline.get("insufficient"):
            raise ValueError(
                f"Walker M4 event count too low for verdict "
                f"(n={baseline.get('n')})"
            )
        baseline_ratio = float(baseline["ratio"])

        # Test each candidate
        per_candidate: list[dict[str, Any]] = []
        for section, fname in _PHYSICS_CANDIDATES:
            if section == "top":
                arr = _aggregate_top_level(records, fname)
            else:
                arr = _aggregate_field(records, section, fname)
            arr_clean = arr[np.isfinite(arr)]
            if arr_clean.size < 10 or float(np.std(arr_clean)) < 1e-12:
                per_candidate.append({
                    "field": f"{section}/{fname}" if section != "top" else fname,
                    "verdict": "INSUFFICIENT",
                    "ratio_plus": None,
                    "ratio_minus": None,
                    "best_sign": None,
                    "best_ratio": None,
                    "delta_vs_baseline": None,
                })
                continue
            X = _normalize(arr)
            r_plus = _conservation_test(total_3 + X, events["walker_m4"])
            r_minus = _conservation_test(total_3 - X, events["walker_m4"])
            ratio_plus = float(r_plus["ratio"])
            ratio_minus = float(r_minus["ratio"])
            if ratio_plus < ratio_minus:
                best_sign = "+"
                best_ratio = ratio_plus
            else:
                best_sign = "−"
                best_ratio = ratio_minus
            verdict = _classify_4term(baseline_ratio, best_ratio, margin=self.noise_floor)
            per_candidate.append({
                "field": f"{section}/{fname}" if section != "top" else fname,
                "verdict": verdict,
                "ratio_plus": ratio_plus,
                "ratio_minus": ratio_minus,
                "best_sign": best_sign,
                "best_ratio": best_ratio,
                "delta_vs_baseline": best_ratio - baseline_ratio,
            })

        # Aggregate
        n_extends = sum(1 for c in per_candidate if c["verdict"] == "EXTENDS")
        n_compatible = sum(1 for c in per_candidate if c["verdict"] == "COMPATIBLE")
        n_breaks = sum(1 for c in per_candidate if c["verdict"] == "BREAKS")
        n_insufficient = sum(1 for c in per_candidate if c["verdict"] == "INSUFFICIENT")
        n_compatible_or_extends = n_extends + n_compatible

        observed = float(n_compatible_or_extends)
        config = {
            "scenario": self.name,
            "trajectory_path": str(self.trajectory_path),
            "compatible_or_extends_min": self.compatible_or_extends_min,
            "noise_floor": self.noise_floor,
            "n_candidates": len(_PHYSICS_CANDIDATES),
            "candidates": [f"{s}/{f}" if s != "top" else f for s, f in _PHYSICS_CANDIDATES],
        }
        dataset = DatasetRef(
            name=self.corpus_name,
            content_hash=content_hash({
                "kimera_commit": self._kimera_commit,
                "n_cycles": n_cycles,
                "n_walker_m4": n_walker_m4,
                "phase": "wider_unification",
            }),
            n_records=n_cycles,
            source=str(self.trajectory_path),
            kind="takwin-sinew-extended-trajectory",
        )
        prereg = PreRegistration(
            config_hash=content_hash(config),
            data_hash=dataset.content_hash,
            analysis_plan=self.analysis_plan(),
        )

        claim = self.build_claim()
        def _fmt_candidate(c: dict[str, Any]) -> str:
            br = c.get("best_ratio")
            ratio_str = f"({br:.4f})" if br is not None else "(—)"
            field_short = c["field"].split("/")[-1]
            return f"{field_short}={c['verdict']}{ratio_str}"

        candidate_table = ", ".join(_fmt_candidate(c) for c in per_candidate)
        final_verdict = Verdict.decide(
            observed=observed,
            threshold=claim.threshold,
            reasoning=(
                f"Wider-unification analysis ({n_cycles} cycles, "
                f"{n_walker_m4} walker_m4 events): 3-term baseline ratio = "
                f"{baseline_ratio:.4f}. Per-candidate (out of "
                f"{len(_PHYSICS_CANDIDATES)}): {n_extends} EXTENDS, "
                f"{n_compatible} COMPATIBLE, {n_breaks} BREAKS, "
                f"{n_insufficient} INSUFFICIENT. "
                f"compatible_or_extends_count = {n_compatible_or_extends}. "
                f"Details: {candidate_table}."
            ),
        )

        evidence = [
            PillarEvidence(
                pillar="sinew_wider_unification",
                statistic_name="compatible_or_extends_count",
                statistic_value=observed,
                library="ophamin.measuring.scenarios.sinew_wider_unification",
                library_version=__version__,
                effect_size=None,
                ci_low=None,
                ci_high=None,
                p_value=None,
                cross_check="passed",
                detail={
                    "cross_check_note": (
                        "Per-candidate breakdown: EXTENDS, COMPATIBLE, BREAKS, "
                        "INSUFFICIENT. EXTENDS candidates tighten conservation "
                        "(participate compensatorily); COMPATIBLE candidates "
                        "are independent of the conservation framework "
                        "(orthogonal physics); BREAKS candidates sit OUTSIDE "
                        "the conservation accounting at decision-points."
                    ),
                    "kimera_commit": self._kimera_commit,
                    "n_cycles": n_cycles,
                    "n_walker_m4": n_walker_m4,
                    "baseline_3term_ratio": baseline_ratio,
                    "noise_floor": self.noise_floor,
                    "compatible_or_extends_count": n_compatible_or_extends,
                    "n_extends": n_extends,
                    "n_compatible": n_compatible,
                    "n_breaks": n_breaks,
                    "n_insufficient": n_insufficient,
                    "per_candidate": per_candidate,
                    "trajectory_path": str(self.trajectory_path),
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
            source=str(self.trajectory_path),
        )
        activity = prov.activity(
            f"scenario:{self.name}",
            target=self.target,
            n_walker_m4=n_walker_m4,
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
            verdict=final_verdict,
            reproduction=Reproduction(

                command=self._build_reproduction_command(),

            ),
            provenance=prov.to_prov_json(),
            ophamin_version=__version__,
            ophamin_git_commit=capture_git_commit(_ophamin_project_root()),
        )
        proof.sign(sign_key)
        return proof

    def analysis_plan(self) -> str:
        return (
            "Read captured Sinew Phase 4-extended trajectory. Compute 3-term "
            "baseline (P + T + CW_seed) conservation ratio at Walker M4 "
            "events. For each of 11 energy fields + prime_log_energy "
            "(12 candidates total), compute best-sign 4-term ratio "
            "(P + T + CW_seed ± candidate). Classify per-candidate as "
            "EXTENDS (ratio < baseline - noise_floor), COMPATIBLE (within "
            "±noise_floor), or BREAKS (> baseline + noise_floor). Headline "
            f"= count of compatible+extends candidates >= "
            f"{self.compatible_or_extends_min} / {len(_PHYSICS_CANDIDATES)}."
        )
