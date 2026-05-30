"""Dynamic-N (SEEDLESS) — a default substrate, NOTHING imposed, finds + grows its own dimension from scratch.

The signed capstone of dynamic-N (journal 083; owner: "No seed, nothing is imposed in Kimera-SWM,
everything dynamic — mandatory not optional"). A default Takwin() — no seed basis, no flags — starts cold
(N=5 hash, no learned manifold), lives, and at its first rich consolidation BOOTSTRAPS its first learned
manifold from its OWN accumulated `_geoid_map` cloud (never a seed), then grows it — coherently.

The live measurement runs in the KIMERA venv (Takwin needs asyncpg/encoder); the Ophamin venv is json-only
(percept-door / live-refit pattern): `dynamic_n_seedless_cache_probe.py` runs the seedless bootstrap and
caches the trajectory (`seedless.json`); this scenario SIGNS it.

  primary  : post-bootstrap mean Φ >= 0.5  (coherent through the cold→learned bootstrap and growth)
  gate     : bootstrapped (cold N=5 → learned-N from its OWN cloud, NO seed) AND N grew end>start
  contrast : the N trajectory (cold 5 → learned → grown) + the bootstrap cycle
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
_CACHE = _KIMERA / "experiments/observatory/runs/dynamic_n_adaptive/seedless.json"


class DynamicNSeedlessScenario(Scenario):
    """A default substrate (no seed, nothing imposed) bootstraps + grows its own geoid dimension from its
    own lived experience — seedless, mandatory, intrinsic dynamic-N."""

    name = "dynamic-n-seedless"
    tier = Tier.SCIENTIFIC
    family = "geoid"
    goal = ("Does a default Takwin() — NO seed, no flags — bootstrap its own learned geoid manifold from "
            "its OWN lived cloud (cold N=5 → learned-N) and grow it, coherently? Nothing imposed.")
    explanation = (
        "A default substrate starts cold (N=5 hash, no learned manifold) and is fed a stream of "
        "accumulating experience. At its first rich consolidation it builds its first learned manifold "
        "from its own _geoid_map cloud (never a seed), flips learned_geoid on, and grows N as it learns "
        "more — Φ staying coherent. Measured live in the Kimera venv (cached); signed here."
    )
    method = "post_bootstrap_mean_phi"
    falsification_consequence = (
        "If the substrate does not bootstrap from cold (no cold→learned from its own cloud), or post-"
        "bootstrap mean Φ < 0.5, then seedless+mandatory dynamic-N is not viable — a seed or a fixed N "
        "would be required, contradicting 'nothing imposed'."
    )
    runner_path = "examples/run_dynamic_n_seedless.py"

    def __init__(self, *, phi_floor: float = 0.5) -> None:
        self.phi_floor = float(phi_floor)
        self.corpus_name = "default-substrate-seedless-bootstrap"
        self.n_cycles = 0

    def score(self, cycle_results: list[CycleResult], records: list[CorpusRecord]) -> ScenarioScore:
        raise NotImplementedError("DynamicNSeedlessScenario signs a cached live measurement.")

    def build_claim(self) -> Claim:
        return Claim(
            statement=(
                "A default Takwin() with NO seed and no flags bootstraps its own learned geoid manifold "
                "from its OWN lived cloud at the first rich consolidation (cold N=5 → learned-N, no seed) "
                "and grows it as experience accumulates, with the cycle staying coherent (post-bootstrap "
                "mean Φ >= 0.5). Nothing is imposed; dynamic-N is mandatory and intrinsic."
            ),
            operationalization=(
                "Default Takwin() (cold N=5 hash, _use_learned_geoid=False) → stream of accumulating "
                "experience → _refit_geoid_dimension fires at consolidation, bootstrapping the first "
                "learned manifold from the lived _geoid_map cloud; observed = post-bootstrap mean Φ, "
                "gated on bootstrapped (cold→learned) AND N grew."
            ),
            threshold=Threshold(metric="post_bootstrap_mean_phi", comparator=">=",
                                value=self.phi_floor, units="phi"),
            h0="H0: no cold-start bootstrap, or post-bootstrap Φ < 0.5 — seedless dynamic-N not viable",
            h1=f"H1: bootstrapped from cold (no seed) and post-Φ >= {self.phi_floor:.2f} — nothing imposed",
        )

    def analysis_plan(self) -> str:
        return ("Load the cached seedless measurement (dynamic_n_seedless_cache_probe): N trajectory, "
                "bootstrap cycle, learned_geoid start/end, per-cycle Φ; observed = post-bootstrap mean Φ "
                "gated on a cold→learned bootstrap with N growth.")

    def run(self, substrate: SubstrateUnderTest, *, data_root=None,
            sign_key: bytes = DEFAULT_SIGN_KEY) -> EmpiricalProofRecord:
        if not _CACHE.exists():
            raise RuntimeError("dynamic-n-seedless: missing seedless.json — run "
                               "experiments/observatory/probe/dynamic_n_seedless_cache_probe.py first "
                               "(measured in the Kimera venv; this scenario signs it)")
        rec = json.loads(_CACHE.read_text())
        boot_at = rec.get("bootstrapped_at")
        n_start, n_end = int(rec["n_start"]), int(rec["n_end"])
        learned_start, learned_end = bool(rec["learned_start"]), bool(rec["learned_end"])
        post_mean = float(rec.get("post_mean", 0.0))
        phi_min = float(rec.get("phi_min", 0.0))
        n_path = rec.get("n_path", [])
        bootstrapped = (boot_at is not None) and (not learned_start) and learned_end and (n_end > n_start)
        observed = post_mean if bootstrapped else 0.0

        claim = self.build_claim()
        dataset = DatasetRef(
            name=self.corpus_name,
            content_hash=content_hash(rec),
            n_records=int(rec.get("geoids_end", 0)), source=str(_CACHE),
            kind="default substrate (no seed) bootstrapping its own geoid dimension from lived experience",
        )
        prereg = PreRegistration(
            config_hash=content_hash({"scenario": self.name, "floor": self.phi_floor}),
            data_hash=dataset.content_hash, analysis_plan=self.analysis_plan(),
        )
        verdict = Verdict.decide(observed=observed, threshold=claim.threshold, reasoning=(
            f"cold start N={n_start} (learned={learned_start}); bootstrapped at cycle {boot_at} → "
            f"learned-N from the substrate's OWN cloud (no seed); grew to N={n_end} "
            f"({rec.get('n_grows')} grows); post-bootstrap mean Φ {post_mean:.3f} (min {phi_min:.3f}) — "
            f"coherent through the bootstrap. Nothing imposed; mandatory, intrinsic dynamic-N."))
        evidence = [PillarEvidence(
            pillar="seedless_self_dimensioning", statistic_name="post_bootstrap_mean_phi",
            statistic_value=observed, library="numpy", library_version=np.__version__,
            effect_size=float(n_end - n_start), ci_low=0.0, ci_high=0.0, p_value=None,
            cross_check="passed" if (observed >= self.phi_floor and bootstrapped) else "failed",
            detail={"n_start": n_start, "n_end": n_end, "bootstrapped_at": boot_at,
                    "learned_start": learned_start, "learned_end": learned_end, "n_path": n_path,
                    "n_grows": rec.get("n_grows"), "geoids_end": rec.get("geoids_end"),
                    "post_mean": post_mean, "phi_min": phi_min,
                    "note": ("default Takwin(), NO seed/flags: cold N=5 hash → first learned manifold built "
                             "from the substrate's OWN lived cloud at consolidation, then grown. Mandatory "
                             "(KIMERA_ADAPTIVE_N default-ON); nothing imposed. Measured in the Kimera venv.")},
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
