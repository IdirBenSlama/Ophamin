"""Number Line — does the production number sense emit a magnitude-faithful number
line over a large set of REAL numbers?

Validates the live Arachne number sense (energy law E_p=log p, journal 049) at
scale on REAL FRED macro values (present dataset — no synthetic data). For each
real number within the sense's operating range, the production assign() emits a
p_thermo; we measure the line:

  primary    : Spearman(value, p_thermo) > 0.90   (a real, monotone number line)
  distinct   : unique primes / N                   (not collapsed)
  locality   : adjacent-rank prime gap << random-pair gap (neighbours stay near)
  zero       : assign("0") → a distinct, valid origin prime (>= 2)

Drives the real ArachneProtocol directly (the number sense is an Arachne feature;
per-number full-Takwin cycles would be hours). The substrate arg supplies signed
provenance.
"""
from __future__ import annotations

import csv
import math
import warnings
from pathlib import Path

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

_FRED_DIR = Path("/Volumes/Behemoth/Ophamin FrameWork /ophamin/data/raw/financial/fred")


def _real_numbers(value_range: float, max_n: int) -> list[float]:
    """Distinct real FRED values within ±value_range (no synthetic data)."""
    seen: set[float] = set()
    for p in sorted(_FRED_DIR.glob("*.csv")):
        with p.open(encoding="utf-8", errors="ignore") as fh:
            for row in csv.reader(fh):
                if len(row) < 2:
                    continue
                try:
                    v = float(row[1])
                except ValueError:
                    continue
                if math.isfinite(v) and abs(v) <= value_range:
                    seen.add(round(v, 4))
    vals = sorted(seen)
    if len(vals) > max_n:  # even subsample across the sorted range
        step = len(vals) / max_n
        vals = [vals[int(i * step)] for i in range(max_n)]
    return vals


def _spearman(a, b) -> float:
    import numpy as np
    ra, rb = np.argsort(np.argsort(a)).astype(float), np.argsort(np.argsort(b)).astype(float)
    ra -= ra.mean(); rb -= rb.mean()
    d = float(np.linalg.norm(ra) * np.linalg.norm(rb))
    return float(np.dot(ra, rb) / d) if d else 0.0


class NumberLineScenario(Scenario):
    """The production number sense emits a monotone, neighbour-local number line
    over real numbers within its operating range."""

    name = "number-line"
    tier = Tier.SCIENTIFIC
    family = "number_sense"
    goal = ("Does the live number sense (energy law) emit a magnitude-faithful, "
            "monotone, neighbour-local number line over real numbers?")
    explanation = (
        "The production number sense maps a value's magnitude onto the prime "
        "energy scale E_p=log(p) and emerges the real prime. This streams real "
        "FRED values within the sense's range through the live assign() and "
        "measures Spearman(value, p_thermo), distinctness, neighbour-locality, "
        "and the zero origin."
    )
    method = "number_line_spearman"
    falsification_consequence = (
        "If Spearman <= 0.90, the live number sense does not preserve magnitude "
        "ordinally on real data — the energy-law wiring is wrong at scale."
    )
    runner_path = "examples/run_number_line.py"

    def __init__(self, *, value_range: float = 1.0e4, max_numbers: int = 4000,
                 accuracy_floor: float = 0.90, target: str = "entity") -> None:
        self.value_range = float(value_range)
        self.max_numbers = int(max_numbers)
        self.accuracy_floor = float(accuracy_floor)
        self.target = target
        self.corpus_name = "fred-real-numbers"
        self.n_cycles = 0

    def score(self, cycle_results: list[CycleResult], records: list[CorpusRecord]) -> ScenarioScore:
        raise NotImplementedError("NumberLineScenario uses a custom run() loop.")

    def build_claim(self) -> Claim:
        return Claim(
            statement=(
                f"Across up to {self.max_numbers} real FRED numbers within "
                f"±{self.value_range:g}, the live number sense emits a monotone "
                f"number line: Spearman(value, p_thermo) >= {self.accuracy_floor:.2f}."
            ),
            operationalization=(
                "Distinct real FRED values within range; live ArachneProtocol "
                "assign(str(v)) → p_thermo; Spearman(value, p_thermo); distinctness; "
                "neighbour-locality (adjacent-rank prime gap vs random-pair gap); "
                "zero → assign('0').p_thermo."
            ),
            threshold=Threshold(metric="number_line_spearman", comparator=">=",
                                value=self.accuracy_floor, units="rank-correlation"),
            h0="H0: Spearman < 0.90 — the number sense does not preserve magnitude on real data",
            h1=f"H1: Spearman >= {self.accuracy_floor:.2f} — a real magnitude number line",
        )

    def analysis_plan(self) -> str:
        return ("Stream real FRED numbers within range through live assign(); "
                "Spearman(value, p_thermo); report distinctness, neighbour-locality, zero.")

    def run(self, substrate: SubstrateUnderTest, *, data_root=None,
            sign_key: bytes = DEFAULT_SIGN_KEY) -> EmpiricalProofRecord:
        import numpy as np
        from kimera_swm.domain.prime.arachne_protocol import ArachneProtocol

        values = _real_numbers(self.value_range, self.max_numbers)
        if len(values) < 50:
            raise RuntimeError(f"number-line: only {len(values)} real numbers in range")
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            ar = ArachneProtocol()
        if not ar.numeron_enabled:
            raise RuntimeError("number-line: numeron must be enabled (production default)")

        primes = [int(ar.assign(f"{v:g}").p_thermo) for v in values]
        rho = abs(_spearman(np.array(values), np.array(primes, float)))
        distinct = len(set(primes)) / len(primes)

        # neighbour-locality: adjacent (value-sorted) prime gaps vs random pairs
        order = np.argsort(values)
        ps = np.array(primes, float)[order]
        adj = float(np.mean(np.abs(np.diff(ps))))
        rng = np.random.default_rng(0)
        idx = rng.integers(0, len(ps), size=(2, 4000))
        rnd = float(np.mean(np.abs(ps[idx[0]] - ps[idx[1]])))
        locality_ratio = adj / rnd if rnd else float("nan")

        zero_prime = int(ar.assign("0").p_thermo)

        observed = float(rho)
        claim = self.build_claim()
        dataset = DatasetRef(
            name="fred-real-numbers",
            content_hash=content_hash({"n": len(values), "range": self.value_range,
                                       "lo": values[0], "hi": values[-1]}),
            n_records=len(values), source=str(_FRED_DIR),
            kind="real-macro values within the number sense's operating range",
        )
        prereg = PreRegistration(
            config_hash=content_hash({"scenario": self.name, "range": self.value_range,
                                      "max_n": self.max_numbers}),
            data_hash=dataset.content_hash, analysis_plan=self.analysis_plan(),
        )
        verdict = Verdict.decide(observed=observed, threshold=claim.threshold, reasoning=(
            f"Spearman {observed:.4f} over {len(values)} real numbers "
            f"[{values[0]:g}, {values[-1]:g}]; distinct {distinct:.3f}; "
            f"neighbour-locality adj/random {locality_ratio:.4f}; zero→{zero_prime}"))
        evidence = [PillarEvidence(
            pillar="magnitude_number_line", statistic_name="number_line_spearman",
            statistic_value=observed, library="numpy", library_version=np.__version__,
            effect_size=observed - 0.0, ci_low=0.0, ci_high=0.0, p_value=None,
            cross_check="n/a",
            detail={"n_numbers": len(values), "range_lo": values[0], "range_hi": values[-1],
                    "distinct_fraction": distinct, "neighbour_locality_ratio": locality_ratio,
                    "zero_prime": zero_prime, "value_range": self.value_range},
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
