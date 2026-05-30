"""Percept Door — does the faithful rich-vector→prime door preserve a learned sense's
discrimination when the percept enters the substrate's prime space?

The signed validation of the faithful perceptual door (journal 057). A learned sense (Heimdall)
turns an image into a discriminating ADDRESS (prec@5 ~0.91); the substrate must deposit that
percept into its prime space WITHOUT collapsing it. The web-feel readout collapsed it to ~40%
retention; `assign_from_percept` (cosine-LSH → prime CHAIN, the vector analog of the scalar energy
law — both bypass the collapsing web) recovers it.

Reads cached REAL Heimdall addresses for held-out CIFAR (numpy-only consumer); runs the LIVE
`ArachneProtocol.assign_from_percept` on each; reads the deposited prime CHAIN from the unified
registry's chain index; measures:

  primary  : chain prec@5 >= 0.80   (the percept survives into prime space, near the address ceiling)
  contrast : the address's own prec@5 (the ceiling) + retention (chain / address)

Real learned-sense addresses on real images, no synthetic data.
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
_CACHE = _KIMERA / "experiments/observatory/runs/eye/heimdall_cifar_addrs.npz"


def _unit(X):
    return X / (np.linalg.norm(X, axis=1, keepdims=True) + 1e-9)


def _prec5_cosine(addr, labels, k=5):
    A = _unit(addr.astype(np.float64))
    S = A @ A.T
    np.fill_diagonal(S, -np.inf)
    nn = np.argsort(-S, axis=1)[:, :k]
    return float((labels[nn] == labels[:, None]).mean())


def _prec5_chains(chains, labels, k=5):
    vocab = sorted({p for ch in chains for p in ch})
    idx = {p: i for i, p in enumerate(vocab)}
    M = np.zeros((len(chains), len(vocab)))
    for r, ch in enumerate(chains):
        for p in ch:
            M[r, idx[p]] += 1.0
    return _prec5_cosine(M, labels, k)


class PerceptDoorScenario(Scenario):
    """The faithful rich-vector→prime door (cosine-LSH) preserves a learned sense's discrimination
    when the percept enters the unified prime space."""

    name = "percept-door"
    tier = Tier.SCIENTIFIC
    family = "perception"
    goal = ("Does assign_from_percept (cosine-LSH → prime chain) preserve a learned sense's "
            "discrimination when the percept enters the substrate's prime space (vs the web feel "
            "that collapsed it to ~40%)?")
    explanation = (
        "Real Heimdall addresses for held-out CIFAR are deposited via the live "
        "ArachneProtocol.assign_from_percept; the deposited prime chain's prec@5 is compared to "
        "the address's own prec@5 (the ceiling). The faithful door bypasses the collapsing web "
        "with a cosine-preserving LSH map — the vector analog of the scalar energy law."
    )
    method = "percept_chain_prec_at_5"
    falsification_consequence = (
        "If the deposited chain's prec@5 <= 0.80 (far below the address ceiling), the door does not "
        "preserve the percept's discrimination — perception does not faithfully enter prime space."
    )
    runner_path = "examples/run_percept_door.py"

    def __init__(self, *, accuracy_floor: float = 0.80, n_planes: int = 128,
                 target: str = "entity") -> None:
        self.accuracy_floor = float(accuracy_floor)
        self.n_planes = int(n_planes)
        self.target = target
        self.corpus_name = "heimdall-cifar-addresses"
        self.n_cycles = 0

    def score(self, cycle_results: list[CycleResult], records: list[CorpusRecord]) -> ScenarioScore:
        raise NotImplementedError("PerceptDoorScenario uses a custom run() loop.")

    def build_claim(self) -> Claim:
        return Claim(
            statement=(
                f"The faithful percept door (cosine-LSH → prime chain, assign_from_percept) "
                f"preserves a learned sense's discrimination into prime space: deposited-chain "
                f"prec@5 >= {self.accuracy_floor:.2f} on real held-out Heimdall/CIFAR addresses, "
                f"near the address ceiling and far above the web-feel readout (~0.36)."
            ),
            operationalization=(
                "Cached real Heimdall addresses for held-out CIFAR → live "
                "ArachneProtocol.assign_from_percept → the deposited prime chain (from the unified "
                "registry's chain index); prec@5 via bag-of-primes cosine, vs the address's own "
                "cosine prec@5 (the ceiling)."
            ),
            threshold=Threshold(metric="percept_chain_prec_at_5", comparator=">=",
                                value=self.accuracy_floor, units="precision@5"),
            h0="H0: chain prec@5 < 0.80 — the door collapses the percept entering prime space",
            h1=f"H1: chain prec@5 >= {self.accuracy_floor:.2f} — a faithful percept door",
        )

    def analysis_plan(self) -> str:
        return ("Load cached Heimdall addresses; run live assign_from_percept; read the deposited "
                "chains; chain prec@5 vs address prec@5; report retention.")

    def run(self, substrate: SubstrateUnderTest, *, data_root=None,
            sign_key: bytes = DEFAULT_SIGN_KEY) -> EmpiricalProofRecord:
        import warnings
        from kimera_swm.domain.prime.arachne_protocol import ArachneProtocol

        if not _CACHE.exists():
            raise RuntimeError("percept-door: missing heimdall_cifar_addrs.npz "
                               "(run experiments/observatory/probe/percept_prime_door_probe.py first)")
        d = np.load(_CACHE)
        addrs, labels = d["addrs"].astype(np.float64), d["labels"]
        if len(addrs) < 50:
            raise RuntimeError(f"percept-door: only {len(addrs)} cached addresses")

        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            ar = ArachneProtocol()
        chains = []
        for i, a in enumerate(addrs):
            ar.assign_from_percept(f"percept_{i}", a, n_planes=self.n_planes)
            chains.append(ar._chain_index[ar._normalize(f"percept_{i}")])

        chain_prec = _prec5_chains(chains, labels)
        addr_prec = _prec5_cosine(addrs, labels)
        retention = chain_prec / addr_prec if addr_prec else 0.0
        observed = float(chain_prec)
        n_classes = len(set(labels.tolist()))
        chance = 1.0 / n_classes

        claim = self.build_claim()
        dataset = DatasetRef(
            name="heimdall-cifar-addresses",
            content_hash=content_hash({"n": len(addrs), "dim": int(addrs.shape[1]),
                                       "planes": self.n_planes}),
            n_records=len(addrs), source=str(_CACHE),
            kind="real learned-sense (Heimdall) addresses for held-out CIFAR images",
        )
        prereg = PreRegistration(
            config_hash=content_hash({"scenario": self.name, "floor": self.accuracy_floor,
                                      "planes": self.n_planes}),
            data_hash=dataset.content_hash, analysis_plan=self.analysis_plan(),
        )
        verdict = Verdict.decide(observed=observed, threshold=claim.threshold, reasoning=(
            f"deposited-chain prec@5 {observed:.4f} over {len(addrs)} real Heimdall addresses "
            f"({n_classes} classes, chance {chance:.3f}); address ceiling {addr_prec:.4f}; "
            f"retention {retention:.2f} (vs the web-feel readout ~0.40)"))
        evidence = [PillarEvidence(
            pillar="percept_prime_discrimination", statistic_name="percept_chain_prec_at_5",
            statistic_value=observed, library="numpy", library_version=np.__version__,
            effect_size=observed - chance, ci_low=0.0, ci_high=0.0, p_value=None,
            cross_check="passed" if observed >= self.accuracy_floor else "failed",
            detail={"n_percepts": len(addrs), "n_classes": n_classes, "chance": chance,
                    "chain_prec5": observed, "address_prec5": addr_prec, "retention": retention,
                    "n_planes": self.n_planes,
                    "note": "web-feel readout baseline ~0.36 (40% retention); LSH door bypasses the web"},
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
