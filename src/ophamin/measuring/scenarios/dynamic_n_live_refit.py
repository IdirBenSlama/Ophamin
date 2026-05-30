"""Dynamic-N (LIVE re-fit) — N grows mid-session on the live substrate and the cognitive cycle stays coherent.

The signed validation of the genuine RUNTIME dynamic-N (journal 079). A naive mid-session dimension
swap collapses the cycle (Φ=0: the cached Ymir + the F2 drift accumulator go stale). The
`_refit_geoid_dimension` method (grow-only, re-fit on the substrate's OWN lived `_geoid_map` cloud,
N=round IPR) resets exactly those — so N grows with accumulated experience and the cycle keeps running.

The live measurement runs in the KIMERA venv (Takwin needs asyncpg + the encoder; the Ophamin venv is
json/numpy-only) — matching the percept-door / adaptive pattern: `dynamic_n_refit_cache_probe.py` runs
the live mid-session grow and caches the measurement (`refit_live.json`); this scenario SIGNS it.

  primary  : post-grow mean Φ >= 0.5   (the cycle survives the mid-session grow; naive swap → Φ=0)
  gate     : N actually grew (grew=True), i.e. the lived cloud's IPR exceeded the starting dim
  contrast : the N transition (16 → IPR) + the naive-swap Φ=0 baseline (journals 077/079)
"""
from __future__ import annotations

import json
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
_CACHE = _KIMERA / "experiments/observatory/runs/dynamic_n_adaptive/refit_live.json"


class DynamicNLiveRefitScenario(Scenario):
    """The live substrate grows its geoid dimension mid-session (on its own lived cloud) and the
    cognitive cycle stays coherent — runtime dynamic-N, not a chosen N."""

    name = "dynamic-n-live-refit"
    tier = Tier.SCIENTIFIC
    family = "geoid"
    goal = ("Does the live substrate grow its geoid dimension mid-session (re-fit on its own lived "
            "cloud, N=IPR, grow-only) and keep the cognitive cycle coherent — where a naive swap "
            "collapses it to Φ=0?")
    explanation = (
        "A learned-N Takwin starts at N=16, is warmed up on real BGE-encoded words, then grows via "
        "_refit_geoid_dimension() (N=round IPR of the accumulated _geoid_map; grow-only). The method "
        "swaps the projector, re-projects geoids, clears the F2 drift, and rebuilds Ymir — so the "
        "post-grow cycle's Φ stays healthy instead of the naive-swap Φ=0. Measured live in the Kimera "
        "venv (cached); signed here."
    )
    method = "post_grow_mean_phi"
    falsification_consequence = (
        "If post-grow mean Φ < 0.5 (or N does not grow), a mid-session dimension grow degrades the live "
        "cycle — runtime dynamic-N would not be viable and N could not adapt with experience."
    )
    runner_path = "examples/run_dynamic_n_live_refit.py"

    def __init__(self, *, phi_floor: float = 0.5) -> None:
        self.phi_floor = float(phi_floor)
        self.corpus_name = "os-dictionary-live-refit"
        self.n_cycles = 0

    def score(self, cycle_results: list[CycleResult], records: list[CorpusRecord]) -> ScenarioScore:
        raise NotImplementedError("DynamicNLiveRefitScenario signs a cached live measurement.")

    def build_claim(self) -> Claim:
        return Claim(
            statement=(
                "On the live substrate, growing the geoid dimension mid-session via "
                "_refit_geoid_dimension (re-fit on the substrate's own lived cloud, grow-only, N=IPR) "
                "keeps the cognitive cycle coherent — post-grow mean Φ >= 0.5 — where a naive dimension "
                "swap collapses it (Φ=0, stale Ymir + F2 drift). N grows with accumulated experience."
            ),
            operationalization=(
                "Learned-N Takwin at N=16 → warm-up cycles on real BGE words → _refit_geoid_dimension() "
                "(N=round IPR of the lived _geoid_map) → post-grow cycles; observed = post-grow mean Φ, "
                "gated on grew=True. (Measured in the Kimera venv; signed from the cache.)"
            ),
            threshold=Threshold(metric="post_grow_mean_phi", comparator=">=",
                                value=self.phi_floor, units="phi"),
            h0="H0: post-grow mean Φ < 0.5 or N did not grow — a live mid-session grow degrades cognition",
            h1=f"H1: post-grow mean Φ >= {self.phi_floor:.2f} and N grew — runtime dynamic-N is viable",
        )

    def analysis_plan(self) -> str:
        return ("Load the cached live measurement (dynamic_n_refit_cache_probe): N transition, IPR, "
                "pre/post-grow Φ; observed = post-grow mean Φ gated on N growing; contrast = the N "
                "transition + the naive-swap Φ=0 baseline.")

    def run(self, substrate: SubstrateUnderTest, *, data_root=None,
            sign_key: bytes = DEFAULT_SIGN_KEY) -> EmpiricalProofRecord:
        if not _CACHE.exists():
            raise RuntimeError("dynamic-n-live-refit: missing refit_live.json — run "
                               "experiments/observatory/probe/dynamic_n_refit_cache_probe.py first "
                               "(the live re-fit is measured in the Kimera venv; this scenario signs it)")
        rec = json.loads(_CACHE.read_text())
        grew = bool(rec.get("grew"))
        n_pre, n_post = int(rec["n_pre"]), int(rec["n_post"])
        ipr = float(rec.get("ipr", 0.0))
        reproj = int(rec.get("reprojected", 0))
        pre = [float(x) for x in rec.get("pre_phi", [])]
        post = [float(x) for x in rec.get("post_phi", [])]
        pre_mean = float(rec.get("pre_mean", 0.0))
        post_mean = float(rec.get("post_mean", 0.0))
        observed = post_mean if grew else 0.0

        claim = self.build_claim()
        dataset = DatasetRef(
            name=self.corpus_name,
            content_hash=content_hash(rec),
            n_records=int(rec.get("n_words", 0)), source=str(_CACHE),
            kind="live substrate mid-session geoid-dimension grow on real BGE-encoded words (measured in-venv)",
        )
        prereg = PreRegistration(
            config_hash=content_hash({"scenario": self.name, "floor": self.phi_floor,
                                      "start_dim": rec.get("start_dim"), "warmup": rec.get("warmup"),
                                      "post": rec.get("post")}),
            data_hash=dataset.content_hash, analysis_plan=self.analysis_plan(),
        )
        verdict = Verdict.decide(observed=observed, threshold=claim.threshold, reasoning=(
            f"live mid-session grow N {n_pre}→{n_post} (IPR {ipr:.1f}, {reproj} geoids re-projected, "
            f"grew={grew}); post-grow mean Φ {post_mean:.3f} over {len(post)} cycles (pre-grow {pre_mean:.3f}); "
            f"naive-swap baseline Φ=0 (stale Ymir + F2 drift; journals 077/079) — the method's resets keep "
            f"the cycle coherent"))
        evidence = [PillarEvidence(
            pillar="runtime_dynamic_n_coherent", statistic_name="post_grow_mean_phi",
            statistic_value=observed, library="numpy", library_version=np.__version__,
            effect_size=post_mean, ci_low=0.0, ci_high=0.0, p_value=None,
            cross_check="passed" if observed >= self.phi_floor else "failed",
            detail={"n_pre": n_pre, "n_post": n_post, "ipr": ipr, "reprojected": reproj,
                    "grew": grew, "lived": rec.get("lived"), "pre_grow_phi": pre, "post_grow_phi": post,
                    "pre_mean": pre_mean, "post_mean": post_mean,
                    "note": ("measured live in the Kimera venv (Takwin needs asyncpg/encoder; the Ophamin "
                             "venv signs the cached measurement). Naive swap → Φ=0 (stale cached Ymir + F2 "
                             "drift broadcast); _refit_geoid_dimension nulls Ymir + clears drift. Default-OFF; "
                             "live auto-call at consolidation owner-gated.")},
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
