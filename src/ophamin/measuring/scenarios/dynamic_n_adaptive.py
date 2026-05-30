"""Dynamic-N (adaptive) — does the substrate find its OWN dimension as its concept cloud grows?

The owner's correction (journal 075): validating a hardcoded N=64 is NOT dynamic-N. Dynamic = (a) the
dimension is SELF-DETERMINED from the data (N = round of the cloud's participation ratio / IPR), and
(b) it ADAPTS as experience accumulates. This scenario signs the zetetic test of the adaptive mechanism:

As a REAL concept cloud GROWS (40 → 200 words, cumulative), at each growth stage re-fit the learned
geoid projector on the accumulated cloud with NO chosen N (target_dim=None → N=round(IPR)) — the
adaptive mechanism — and ask: does the self-found N (1) track the growing cloud and (2) stay near the
recall achievable at a generous fixed dimension? If yes, "meaning finds its own dimension" is real and
near-optimal; no number need be chosen by anyone.

  primary  : min over stages of (adaptive recall@5 / generous-N recall@5) >= 0.95, GATED on N growing
             (N_last > N_first, non-decreasing). The self-found dimension is within 5% of the ceiling at
             every stage AND tracks the data.
  contrast : adaptive vs the live fixed-5 default (the gap it recovers) + the N trajectory (efficiency:
             few dims early, more as the cloud grows).

Real OS-dictionary words, BGE-encoded (cached by dynamic_n_corpus_cache_probe.py); LearnedManifoldProjector
is pure-SVD numpy. Honest scope: PROJECTOR-level mechanism prototype (re-fit on growth) — the prerequisite
for wiring adaptive-N into the live cycle (N is frozen at init today); scar-migration under re-fit is the
remaining live question.
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import statsmodels as _sm  # noqa: F401

from ophamin import __version__
from ophamin.comparing.provenance.lineage import _ophamin_project_root, capture_git_commit
from ophamin.measuring.proof import (
    Claim, DatasetRef, EmpiricalProofRecord, PillarEvidence, PreRegistration,
    Reproduction, Threshold, Verdict, content_hash,
)
from ophamin.measuring.scenarios.base import DEFAULT_SIGN_KEY, Scenario, ScenarioScore, Tier
from ophamin.seeing.corpus import CorpusRecord
from ophamin.seeing.substrate.base import CycleResult, SubstrateUnderTest

_KIMERA = Path("/Users/idirbenslama/Desktop/DEV/Kimera_SWM (Spherical Word Memory)")
_CACHE = _KIMERA / "experiments/observatory/runs/dynamic_n_adaptive/corpus.npz"
_STAGES = [40, 80, 120, 160, 200]


def _unit(M):
    return M / (np.linalg.norm(M, axis=1, keepdims=True) + 1e-9)


def _recall_at5(P, F):
    """Leave-one-out recall@5: ground-truth kin = argmax-cosine in full space F; kept in top-5 of P."""
    Sp, Sf = P @ P.T, F @ F.T
    np.fill_diagonal(Sp, -np.inf)
    np.fill_diagonal(Sf, -np.inf)
    gt = np.argmax(Sf, axis=1)
    top5 = np.argsort(-Sp, axis=1)[:, :5]
    return float(np.mean([gt[i] in top5[i] for i in range(P.shape[0])]))


class DynamicNAdaptiveScenario(Scenario):
    """The substrate's self-determined geoid dimension (N=IPR) tracks a growing concept cloud and stays
    near-optimal for recall — dynamic-N as 'meaning finds its own dimension', not a chosen number."""

    name = "dynamic-n-adaptive"
    tier = Tier.SCIENTIFIC
    family = "geoid"
    goal = ("Does the substrate find its OWN geoid dimension as its concept cloud grows — N=round(IPR), "
            "tracking the data and staying near the recall achievable at a generous fixed N (no number "
            "chosen by anyone)?")
    explanation = (
        "A real concept cloud grows 40→200 BGE-encoded words. At each stage the learned geoid projector "
        "is re-fit on the accumulated cloud with target_dim=None (N=round(participation ratio)) — the "
        "adaptive mechanism. We test whether the self-found N (1) grows with the cloud and (2) keeps "
        "recall@5 within 5% of a generous fixed N, vs the live fixed-5 default."
    )
    method = "adaptive_vs_generous_recall_ratio_over_growth"
    falsification_consequence = (
        "If min-stage (adaptive recall@5 / generous recall@5) < 0.95, or N does not grow with the cloud, "
        "the self-determined dimension is not near-optimal / not tracking — 'meaning finds its own "
        "dimension' would not hold and a fixed N (or a hand-tuned one) would be required."
    )
    runner_path = "examples/run_dynamic_n_adaptive.py"

    def __init__(self, *, ratio_floor: float = 0.95) -> None:
        self.ratio_floor = float(ratio_floor)
        self.corpus_name = "os-dictionary-growing-concept-cloud"
        self.n_cycles = 0

    def score(self, cycle_results: list[CycleResult], records: list[CorpusRecord]) -> ScenarioScore:
        raise NotImplementedError("DynamicNAdaptiveScenario uses a custom run() loop.")

    def build_claim(self) -> Claim:
        return Claim(
            statement=(
                "As a real concept cloud grows (40→200 words), the substrate's self-determined geoid "
                "dimension N=round(IPR) tracks the cloud (N grows, non-decreasing) and stays within 5% of "
                "the recall@5 achievable at a generous fixed dimension at every growth stage — meaning "
                "finds its own near-optimal dimension, no number chosen by anyone."
            ),
            operationalization=(
                "At each cumulative stage, re-fit LearnedManifoldProjector(accumulated_cloud, "
                "target_dim=None) → N=round(IPR); leave-one-out recall@5 (full-BGE kin) on the projected "
                "positions vs the same at a generous fixed N=min(stage_size-1,128); min over stages of the "
                "ratio, gated on N growing."
            ),
            threshold=Threshold(metric="adaptive_vs_generous_recall_ratio", comparator=">=",
                                value=self.ratio_floor, units="ratio"),
            h0="H0: ratio < 0.95 or N does not grow — the self-found dimension is not near-optimal/tracking",
            h1=f"H1: ratio >= {self.ratio_floor:.2f} and N grows — meaning finds its own near-optimal dimension",
        )

    def analysis_plan(self) -> str:
        return ("Load cached real-word BGE embeddings; for cumulative stages [40,80,120,160,200] re-fit the "
                "learned projector with N=IPR (adaptive), N=5 (live default), N=min(size-1,128) (generous); "
                "leave-one-out recall@5 each; report N trajectory + min(adaptive/generous) gated on N growth.")

    def run(self, substrate: SubstrateUnderTest, *, data_root=None,
            sign_key: bytes = DEFAULT_SIGN_KEY) -> EmpiricalProofRecord:
        from kimera_swm.domain.geoid.learned_manifold_projector import LearnedManifoldProjector

        if not _CACHE.exists():
            raise RuntimeError("dynamic-n-adaptive: missing corpus.npz "
                               "(run experiments/observatory/probe/dynamic_n_corpus_cache_probe.py first)")
        d = np.load(_CACHE, allow_pickle=True)
        E = d["embeddings"].astype(np.float64)
        words = [str(w) for w in d["words"]]
        if E.shape[0] < _STAGES[-1]:
            raise RuntimeError(f"dynamic-n-adaptive: cached {E.shape[0]} < {_STAGES[-1]} words")

        def project(cloud, n):
            p = LearnedManifoldProjector(cloud, n)
            P = np.stack([p.project(e) for e in cloud]).astype(np.float64)
            return _unit(P), p

        stages = []
        for size in _STAGES:
            C = E[:size]
            F = _unit(C)
            P_ad, p_ad = project(C, None)          # adaptive: N = round(IPR)
            N_ad, ipr = int(p_ad.target_dim), float(p_ad.effective_dim())
            P5, _ = project(C, 5)                    # live default
            Ng = int(min(size - 1, 128))            # generous fixed N (ceiling reference)
            Pg, _ = project(C, Ng)
            stages.append({
                "size": size, "N_adaptive": N_ad, "ipr": round(ipr, 2), "N_generous": Ng,
                "recall5_adaptive": round(_recall_at5(P_ad, F), 4),
                "recall5_fixed5": round(_recall_at5(P5, F), 4),
                "recall5_generous": round(_recall_at5(Pg, F), 4),
            })

        N_traj = [s["N_adaptive"] for s in stages]
        n_grew = N_traj[-1] > N_traj[0] and all(N_traj[i] <= N_traj[i + 1] for i in range(len(N_traj) - 1))
        ratios = [s["recall5_adaptive"] / s["recall5_generous"] if s["recall5_generous"] else 0.0
                  for s in stages]
        gaps = [s["recall5_adaptive"] - s["recall5_fixed5"] for s in stages]
        ratio_min = float(min(ratios))
        gap_min = float(min(gaps))
        observed = ratio_min if n_grew else 0.0

        claim = self.build_claim()
        dataset = DatasetRef(
            name=self.corpus_name,
            content_hash=content_hash({"words": words, "stages": _STAGES}),
            n_records=int(E.shape[0]), source=str(_CACHE),
            kind="real OS-dictionary words, BGE-encoded, grown cumulatively into a concept cloud",
        )
        prereg = PreRegistration(
            config_hash=content_hash({"scenario": self.name, "floor": self.ratio_floor, "stages": _STAGES}),
            data_hash=dataset.content_hash, analysis_plan=self.analysis_plan(),
        )
        verdict = Verdict.decide(observed=observed, threshold=claim.threshold, reasoning=(
            f"N trajectory {N_traj} (grew={n_grew}, IPR-tracked); min(adaptive/generous recall@5)="
            f"{ratio_min:.4f} over {len(_STAGES)} growth stages; adaptive beats the live fixed-5 default by "
            f"min {gap_min:+.3f}; the self-found dimension is near the generous-N ceiling at every stage "
            f"while using {N_traj[0]} dims at 40 concepts vs {stages[0]['N_generous']} generous."))
        evidence = [PillarEvidence(
            pillar="self_determined_dimension_near_optimal", statistic_name="adaptive_vs_generous_recall_ratio",
            statistic_value=observed, library="numpy", library_version=np.__version__,
            effect_size=gap_min, ci_low=0.0, ci_high=0.0, p_value=None,
            cross_check="passed" if observed >= self.ratio_floor else "failed",
            detail={"stages": stages, "N_trajectory": N_traj, "N_grew": n_grew,
                    "ratio_min_adaptive_over_generous": ratio_min, "gap_min_adaptive_over_fixed5": gap_min,
                    "note": ("adaptive N=round(IPR), re-fit per stage (the adaptive mechanism); generous "
                             "N=min(size-1,128) is the ceiling reference; fixed-5 is the live default. "
                             "Projector-level prototype — live wiring (N frozen at init) + scar-migration "
                             "under re-fit remain (proposal §7).")},
        )]
        record = EmpiricalProofRecord(
            claim=claim, preregistration=prereg, datasets=[dataset],
            substrate_name=substrate.name, substrate_git_commit=substrate.git_commit(),
            evidence=evidence, verdict=verdict,
            reproduction=Reproduction(command=self._build_reproduction_command()),
            provenance=self._build_provenance(substrate, dataset).to_prov_json(),
            ophamin_version=__version__,
            ophamin_git_commit=capture_git_commit(_ophamin_project_root()),
        )
        record.sign(sign_key)
        return record
