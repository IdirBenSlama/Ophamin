"""Tonus — native MCA-based conservation-law discovery scenario.

Tests whether Kimera's native Tonus primitive (Minor Component Analysis on
event-conditioned delta vectors) discovers a substrate-internal conservation
law that:

* matches OR refines the Sinew Phase 4-extended finding (P + T + CW_seed)
* is content-invariant across corpora (SEC v2 vs Literary)
* improves with polynomial basis expansion (degree=2 nonlinear conservation)

The Tonus primitive is a NATIVE Kimera-SWM implementation (no third-party
libraries). The mathematical core is closed-form linear algebra
(eigendecomposition of the event-delta Gram matrix); the substrate
contribution is the application to Kimera's per-cycle state vectors and
the interpretation in substrate-native vocabulary.

Falsifiable claim
=================

> T1: For walker_m4 events in matched SEC v2 + Literary Sinew trajectories,
>     the Tonus primitive discovers a linear conservation with:
>
>     (a) conservation_strength > 0.50 on each corpus separately
>     (b) cross-corpus cosine similarity > 0.85 (the conserved direction
>         is content-invariant)
>     (c) polynomial degree=2 conservation_strength > 0.95 (nonlinear
>         conservation is essentially exact)

All three sub-conditions must validate.

Threshold rationale: validating T1 establishes that Tonus is a working
native substrate-internal conservation-discovery primitive AND that the
substrate has a stronger conservation than Sinew's linear hypothesis
suggested. REFUTED would mean either (a) Tonus doesn't work as designed,
(b) the substrate has no consistent conservation across corpora, or (c)
nonlinear extensions don't help. All three are interesting outcomes.

Inputs
======

Two Sinew capture trajectories (per_cycle_records.json) — SEC v2 + Literary —
each carrying at least 50 walker_m4 events.

Output
======

Signed EmpiricalProofRecord with:
- Headline: sub_conditions_satisfied (1 if all 3 satisfy; 0 otherwise)
- Secondary: per-corpus discovered coefficients, conservation strength,
  cross-corpus cosine similarity, polynomial degree=2 strength,
  readable equations.
"""

from __future__ import annotations

import json
import math
import sys
from pathlib import Path
from typing import Any, Sequence

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
from ophamin.measuring.scenarios.base import (
    DEFAULT_SIGN_KEY, Scenario, ScenarioScore, Tier,
)
from ophamin.seeing.corpus import CorpusRecord
from ophamin.seeing.substrate.base import CycleResult, SubstrateUnderTest


_PRESSURE_FIELDS = (
    "allen_cahn_mean_free_energy",
    "prime_reregistration_pressure",
    "void_pressure_mean",
    "gamma_pressure",
    "contradiction_collapse_count",
)
_TENSION_FIELDS = (
    "graph_coherence",
    "alexandria_prime_coherence",
    "adaptive_coherence_threshold",
    "arachne_web_coupling_frobenius",
    "kuramoto_order_parameter",
)


def _avg(record: dict[str, Any], section: str, fields: tuple[str, ...]) -> float:
    vals = [
        v for v in (record.get(section, {}).get(f, 0.0) for f in fields)
        if isinstance(v, (int, float)) and math.isfinite(float(v))
    ]
    return float(np.mean(vals)) if vals else 0.0


def _normalize_per_signal(matrix: np.ndarray) -> np.ndarray:
    std = np.std(matrix, axis=0, ddof=0)
    std = np.where(std < 1e-12, 1.0, std)
    return matrix / std


def _detect_walker_m4(records: list[dict[str, Any]]) -> list[int]:
    return [
        i for i, r in enumerate(records)
        if not r.get("crashed")
        and (
            r.get("events", {}).get("halt_reason") == "lateral_leap"
            or int(r.get("events", {}).get("walker_annealing_events", 0)) > 0
        )
    ]


def _build_before_after_at_events(
    records: list[dict[str, Any]], event_indices: list[int]
) -> tuple[np.ndarray, np.ndarray]:
    P_raw = np.array([
        _avg(r, "pressure_proxies", _PRESSURE_FIELDS) if not r.get("crashed") else math.nan
        for r in records
    ])
    T_raw = np.array([
        _avg(r, "tension_proxies", _TENSION_FIELDS) if not r.get("crashed") else math.nan
        for r in records
    ])
    CW_raw = np.array([
        float(r.get("scar", {}).get("scar_coherence_weight", 0.0)) if not r.get("crashed") else math.nan
        for r in records
    ])
    P = _normalize_per_signal(P_raw.reshape(-1, 1)).ravel()
    T = _normalize_per_signal(T_raw.reshape(-1, 1)).ravel()
    CW = _normalize_per_signal(CW_raw.reshape(-1, 1)).ravel()
    before, after = [], []
    for i in event_indices:
        if i == 0:
            continue
        if all(math.isfinite(x) for x in (P[i-1], P[i], T[i-1], T[i], CW[i-1], CW[i])):
            before.append([P[i-1], T[i-1], CW[i-1]])
            after.append([P[i], T[i], CW[i]])
    return np.array(before), np.array(after)


def _native_tonus_discover(
    states_before: np.ndarray,
    states_after: np.ndarray,
    *,
    polynomial_degree: int = 1,
) -> dict[str, Any]:
    """Native MCA (Minor Component Analysis) — vendored implementation.

    Independent re-implementation of the Tonus algorithm in pure numpy. The
    Kimera-side primitive at `kimera_swm.domain.cognitive.tonus.tonus`
    contains the canonical code; this scenario re-implements the same math
    to keep the Ophamin scenario self-contained (no Kimera-side import
    dependency from Ophamin, per the framework's independence contract).

    Returns dict with keys: coefficients, smallest_eigenvalue,
    conservation_strength, eigenvalue_spectrum, feature_names.
    """
    if polynomial_degree < 1 or polynomial_degree > 3:
        raise ValueError(f"polynomial_degree must be in [1, 3], got {polynomial_degree}")
    n_signals = states_before.shape[1]
    signal_names = ["pressure", "tension", "scar_coherence_weight"]
    # Polynomial basis expansion
    if polynomial_degree == 1:
        basis_before = states_before.copy()
        basis_after = states_after.copy()
        feature_names = list(signal_names)
    else:
        basis_before, feature_names = _expand_basis(states_before, polynomial_degree, signal_names)
        basis_after, _ = _expand_basis(states_after, polynomial_degree, signal_names)
    deltas = basis_after - basis_before
    if np.allclose(deltas, 0.0):
        raise ValueError("all deltas zero")
    n = deltas.shape[0]
    gram = (deltas.T @ deltas) / n
    eigvals, eigvecs = np.linalg.eigh(gram)
    c = eigvecs[:, 0]
    c = c / max(float(np.linalg.norm(c)), 1e-12)
    smallest = float(eigvals[0])
    mean_e = float(eigvals.mean())
    strength = 0.0 if mean_e <= 1e-12 else 1.0 - smallest / mean_e
    strength = float(min(1.0, max(0.0, strength)))
    return {
        "coefficients": c.tolist(),
        "feature_names": feature_names,
        "smallest_eigenvalue": smallest,
        "conservation_strength": strength,
        "eigenvalue_spectrum": eigvals.tolist(),
    }


def _expand_basis(
    states: np.ndarray, degree: int, names: Sequence[str]
) -> tuple[np.ndarray, list[str]]:
    """Polynomial basis expansion — same convention as Kimera-side Tonus."""
    n_samples, n_signals = states.shape
    cols = [states.copy()]
    out_names = list(names)
    if degree >= 2:
        for i in range(n_signals):
            for j in range(i, n_signals):
                cols.append((states[:, i] * states[:, j]).reshape(-1, 1))
                out_names.append(f"{names[i]}^2" if i == j else f"{names[i]}*{names[j]}")
    if degree >= 3:
        for i in range(n_signals):
            for j in range(i, n_signals):
                for k in range(j, n_signals):
                    cols.append(
                        (states[:, i] * states[:, j] * states[:, k]).reshape(-1, 1)
                    )
                    out_names.append(f"{names[i]}*{names[j]}*{names[k]}")
    return np.hstack(cols), out_names


class TonusConservationDiscoveryScenario(Scenario):
    """Native MCA-based substrate conservation discovery (Tonus primitive)."""

    name = "tonus-conservation-discovery"
    tier = Tier.SCIENTIFIC
    family = "conservation"
    goal = (
        "Test whether Kimera's native Tonus primitive (Minor Component "
        "Analysis on event-conditioned delta vectors, pure numpy, no "
        "third-party libraries) discovers a content-invariant substrate "
        "conservation that matches OR refines Sinew's manual P+T+CW finding."
    )
    explanation = (
        "Tonus is named after physiological tonus — the constant "
        "background tension that living tissue maintains continuously. "
        "Mechanically, it discovers the conserved linear (or polynomial) "
        "combination of substrate state signals whose value persists "
        "through reconnection events. Native implementation in pure numpy "
        "preserves Kimera's IP integrity (no ConservNet / SINDy / external "
        "package imports). The mathematical core (smallest-eigenvalue "
        "eigendecomposition of the event-delta Gram matrix, aka Minor "
        "Component Analysis) is a 19th-century closed-form result, "
        "public-domain; Kimera's contribution is the substrate-semantic "
        "application + interpretation in substrate-native vocabulary."
    )
    method = "minor_component_analysis"
    falsification_consequence = (
        "EITHER Tonus doesn't surface a usable conservation (primitive "
        "broken or no conservation exists at this resolution) OR the "
        "discovered conservation is content-dependent (not substrate-"
        "universal) OR polynomial extension doesn't improve strength "
        "(no nonlinear conservation hidden beneath the linear approximation). "
        "Any of these refutes the substrate's conserved-baseline hypothesis."
    )
    corpus_name = "kimera-tonus-cross-corpus"
    target = "captured_takwin_trajectories"

    def __init__(
        self,
        sec_trajectory_path: str | Path,
        literary_trajectory_path: str | Path,
        *,
        linear_strength_min: float = 0.50,
        cross_corpus_cosine_min: float = 0.85,
        nonlinear_strength_min: float = 0.95,
    ) -> None:
        self.sec_path = Path(sec_trajectory_path).expanduser()
        self.lit_path = Path(literary_trajectory_path).expanduser()
        for p in (self.sec_path, self.lit_path):
            if not p.is_file():
                raise FileNotFoundError(f"trajectory not found: {p}")
        if not 0.0 < linear_strength_min < 1.0:
            raise ValueError(f"linear_strength_min must be in (0, 1)")
        if not 0.0 < cross_corpus_cosine_min < 1.0:
            raise ValueError(f"cross_corpus_cosine_min must be in (0, 1)")
        if not 0.0 < nonlinear_strength_min < 1.0:
            raise ValueError(f"nonlinear_strength_min must be in (0, 1)")
        self.linear_strength_min = float(linear_strength_min)
        self.cross_corpus_cosine_min = float(cross_corpus_cosine_min)
        self.nonlinear_strength_min = float(nonlinear_strength_min)
        # Read commit hash from metadata.json siblings if present
        self._kimera_commit = ""
        for p in (self.sec_path, self.lit_path):
            meta_path = p.parent / "metadata.json"
            if meta_path.is_file():
                try:
                    meta = json.loads(meta_path.read_text())
                    if meta.get("kimera_commit") and not self._kimera_commit:
                        self._kimera_commit = str(meta["kimera_commit"])
                except (OSError, ValueError, KeyError):
                    continue

    def score(
        self,
        cycle_results: list[CycleResult],
        records: list[CorpusRecord],
    ) -> ScenarioScore:
        raise NotImplementedError(
            "TonusConservationDiscoveryScenario uses a custom run() loop."
        )

    def build_claim(self) -> Claim:
        return Claim(
            statement=(
                f"For walker_m4 events in matched SEC v2 + Literary Sinew "
                f"trajectories, Kimera's native Tonus primitive (Minor "
                f"Component Analysis on event-conditioned delta vectors) "
                f"discovers a conservation satisfying (a) linear "
                f"conservation_strength > {self.linear_strength_min} per "
                f"corpus, (b) cross-corpus discovered-coefficient cosine "
                f"similarity > {self.cross_corpus_cosine_min}, and (c) "
                f"polynomial-degree=2 conservation_strength > "
                f"{self.nonlinear_strength_min} (essentially exact nonlinear "
                f"conservation). All three sub-conditions must validate."
            ),
            operationalization=(
                "Apply native MCA (smallest-eigenvalue eigendecomposition "
                "of the event-delta Gram matrix) to matched (state_before, "
                "state_after) pairs at walker_m4 events on each corpus. "
                "Compare the discovered coefficient vectors via absolute "
                "cosine similarity (sign-invariant). Repeat with polynomial "
                "degree=2 basis expansion. Headline metric = 1 if all 3 "
                "sub-conditions satisfy; 0 otherwise."
            ),
            threshold=Threshold(
                metric="sub_conditions_satisfied",
                comparator=">=",
                value=1.0,
                units="all_or_nothing",
            ),
            h0=(
                "At least one sub-condition fails: either Tonus discovers "
                "a weak conservation, the discovered direction is content-"
                "dependent, or polynomial extension doesn't tighten."
            ),
            h1=(
                "All three sub-conditions satisfy: substrate has a content-"
                "invariant linear conservation that becomes essentially "
                "exact at polynomial degree 2."
            ),
        )

    def run(
        self,
        substrate: SubstrateUnderTest | None = None,
        *,
        data_root: Any = None,
        sign_key: bytes = DEFAULT_SIGN_KEY,
    ) -> EmpiricalProofRecord:
        sec_records = json.loads(self.sec_path.read_text())
        lit_records = json.loads(self.lit_path.read_text())

        per_corpus: dict[str, dict[str, Any]] = {}
        for label, records in (("sec_v2", sec_records), ("literary", lit_records)):
            event_idx = _detect_walker_m4(records)
            before, after = _build_before_after_at_events(records, event_idx)
            if len(before) < 5:
                per_corpus[label] = {"insufficient": True, "n_events": len(before)}
                continue
            linear = _native_tonus_discover(before, after, polynomial_degree=1)
            nonlinear = _native_tonus_discover(before, after, polynomial_degree=2)
            per_corpus[label] = {
                "n_cycles": len(records),
                "n_events": len(before),
                "linear": linear,
                "nonlinear": nonlinear,
            }

        # Cross-corpus cosine similarity (linear coefficients)
        cross_cos = float("nan")
        if (
            "linear" in per_corpus.get("sec_v2", {})
            and "linear" in per_corpus.get("literary", {})
        ):
            sec_c = np.array(per_corpus["sec_v2"]["linear"]["coefficients"])
            lit_c = np.array(per_corpus["literary"]["linear"]["coefficients"])
            cross_cos = abs(float(sec_c @ lit_c))

        # Evaluate three sub-conditions
        sub_a_per_corpus_strength = all(
            per_corpus.get(c, {}).get("linear", {}).get("conservation_strength", 0)
            > self.linear_strength_min
            for c in ("sec_v2", "literary")
        )
        sub_b_cross_corpus_cosine = (
            not math.isnan(cross_cos) and cross_cos > self.cross_corpus_cosine_min
        )
        sub_c_nonlinear_strength = all(
            per_corpus.get(c, {}).get("nonlinear", {}).get("conservation_strength", 0)
            > self.nonlinear_strength_min
            for c in ("sec_v2", "literary")
        )
        all_pass = sub_a_per_corpus_strength and sub_b_cross_corpus_cosine and sub_c_nonlinear_strength
        observed = 1.0 if all_pass else 0.0

        config = {
            "scenario": self.name,
            "sec_trajectory_path": str(self.sec_path),
            "literary_trajectory_path": str(self.lit_path),
            "linear_strength_min": self.linear_strength_min,
            "cross_corpus_cosine_min": self.cross_corpus_cosine_min,
            "nonlinear_strength_min": self.nonlinear_strength_min,
        }
        dataset = DatasetRef(
            name=self.corpus_name,
            content_hash=content_hash({
                "kimera_commit": self._kimera_commit,
                "sec_n_cycles": per_corpus.get("sec_v2", {}).get("n_cycles", 0),
                "lit_n_cycles": per_corpus.get("literary", {}).get("n_cycles", 0),
                "scenario_revision": "tonus-v1",
            }),
            n_records=(
                per_corpus.get("sec_v2", {}).get("n_cycles", 0)
                + per_corpus.get("literary", {}).get("n_cycles", 0)
            ),
            source=f"{self.sec_path};{self.lit_path}",
            kind="takwin-sinew-extended-trajectory-paired",
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
                f"Tonus discovery on matched SEC v2 + Literary trajectories: "
                f"sub-A (per-corpus linear strength > {self.linear_strength_min}) "
                f"= {sub_a_per_corpus_strength}; sub-B (cross-corpus cosine > "
                f"{self.cross_corpus_cosine_min}) = {sub_b_cross_corpus_cosine} "
                f"(observed {cross_cos:.4f}); sub-C (nonlinear strength > "
                f"{self.nonlinear_strength_min}) = {sub_c_nonlinear_strength}."
            ),
        )

        evidence = [
            PillarEvidence(
                pillar="tonus_conservation_discovery",
                statistic_name="sub_conditions_satisfied",
                statistic_value=observed,
                library="ophamin.measuring.scenarios.tonus_conservation_discovery",
                library_version=__version__,
                effect_size=None,
                ci_low=None,
                ci_high=None,
                p_value=None,
                cross_check="passed" if all_pass else "failed",
                detail={
                    "cross_check_narrative": (
                        "Three pre-registered sub-conditions probe complementary "
                        "aspects: (a) substrate has a workable linear conservation, "
                        "(b) the conservation is content-invariant, (c) polynomial "
                        "extension tightens it. Tonus uses native MCA (numpy-only "
                        "eigendecomposition); no third-party library imports. "
                        "Refines Sinew Phase 4-extended finding."
                    ),
                    "kimera_commit": self._kimera_commit,
                    "per_corpus": per_corpus,
                    "cross_corpus_cosine_similarity": cross_cos,
                    "sub_a_per_corpus_strength_satisfied": sub_a_per_corpus_strength,
                    "sub_b_cross_corpus_cosine_satisfied": sub_b_cross_corpus_cosine,
                    "sub_c_nonlinear_strength_satisfied": sub_c_nonlinear_strength,
                    "thresholds": {
                        "linear_strength_min": self.linear_strength_min,
                        "cross_corpus_cosine_min": self.cross_corpus_cosine_min,
                        "nonlinear_strength_min": self.nonlinear_strength_min,
                    },
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
            source=str(self.sec_path),
        )
        activity = prov.activity(
            f"scenario:{self.name}",
            target=self.target,
            sub_conditions_satisfied=int(observed),
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
            "Apply native MCA on event-conditioned delta vectors for "
            "walker_m4 events on SEC v2 + Literary trajectories. Evaluate "
            "three sub-conditions: (a) per-corpus linear strength > "
            f"{self.linear_strength_min}, (b) cross-corpus cosine > "
            f"{self.cross_corpus_cosine_min}, (c) polynomial degree=2 "
            f"strength > {self.nonlinear_strength_min}. All three must "
            "satisfy to validate."
        )
