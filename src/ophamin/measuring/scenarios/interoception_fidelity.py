"""Interoception Fidelity — does the live internal-event chain (real Takwin payload
builders → faithful interoception door) emit a magnitude-ordered prime over REAL
numeric magnitudes, where the legacy name-fingerprint collapsed it?

This is the signed, through-the-real-machinery validation of the Tier-1 faithful
interoception door (journal 052). The substrate's OWN internal magnitudes (ΔS,
pressure, drift, amplitude) used to be baked into an event-name string whose web
fingerprint collapsed them to ~6 levels (Spearman≈0.47). The door routes a finite
numeric ``magnitude`` through the Numeron energy law (E_p=log p) instead.

We drive the REAL static Takwin payload builders
(``_build_internal_event_payload_for_thermodynamic_transition`` / ``_spde_pressure_peak``)
across real FRED-derived magnitudes, route each through the REAL ArachneProtocol
``assign_from_internal_event`` twice — once with interoception ON (the door) and
once OFF (the legacy fingerprint) — and contrast:

  primary    : Spearman(magnitude, p_thermo) >= 0.95   with interoception ON (door)
  baseline   : the same Spearman with interoception OFF (fingerprint — expect ~0.47)
  distinct   : unique primes / N for both paths (door un-collapses; fingerprint ~6)

The contrast (door vs fingerprint, same builders, same magnitudes, only the route
differs) is the faithful-door payoff. Real numeric magnitudes, no synthetic data.
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


def _real_magnitudes(value_range: float, max_n: int) -> list[float]:
    """Distinct real FRED magnitudes (|v|, the natural form of an internal-event
    magnitude — ΔS/pressure are non-negative) within (0, value_range]. No synthetic data."""
    seen: set[float] = set()
    for p in sorted(_FRED_DIR.glob("*.csv")):
        with p.open(encoding="utf-8", errors="ignore") as fh:
            for row in csv.reader(fh):
                if len(row) < 2:
                    continue
                try:
                    v = abs(float(row[1]))
                except ValueError:
                    continue
                if math.isfinite(v) and 0.0 < v <= value_range:
                    seen.add(round(v, 4))
    vals = sorted(seen)
    if len(vals) > max_n:  # even subsample across the sorted range
        step = len(vals) / max_n
        vals = [vals[int(i * step)] for i in range(max_n)]
    return vals


def _spearman(a, b) -> float:
    import numpy as np
    ra, rb = np.argsort(np.argsort(a)).astype(float), np.argsort(np.argsort(b)).astype(float)
    ra -= ra.mean()
    rb -= rb.mean()
    d = float(np.linalg.norm(ra) * np.linalg.norm(rb))
    return float(np.dot(ra, rb) / d) if d else 0.0


def _p_thermo_for(ar, payload) -> int:
    """Route a payload through the real assign_from_internal_event, then read the
    emitted p_thermo from the unified registry (same lookup the live probe uses)."""
    ar.assign_from_internal_event(
        "thermodynamic_transition" if payload.get("_kind") == "thermo" else "spde_pressure_peak",
        payload)
    key = (ar._normalize(payload["canonical_name"]), ar._substrate_state_stamp)
    return int(ar._registry[key].p_thermo)


class InteroceptionFidelityScenario(Scenario):
    """The live internal-event chain (real builders → door) emits a magnitude-ordered
    prime over real magnitudes, restoring the ordinal fidelity the fingerprint lost."""

    name = "interoception-fidelity"
    tier = Tier.SCIENTIFIC
    family = "interoception"
    goal = ("Does the live internal-event chain (real Takwin builders → faithful "
            "interoception door) emit a magnitude-ordered prime over real magnitudes, "
            "where the legacy name-fingerprint collapsed it (~0.47, ~6 levels)?")
    explanation = (
        "The substrate's own internal magnitudes (ΔS/pressure) drive the real static "
        "Takwin payload builders; each payload is routed through the real "
        "assign_from_internal_event twice — interoception ON (the energy-law door) and "
        "OFF (the legacy name-fingerprint). We contrast Spearman(magnitude, p_thermo) "
        "and distinctness. Same builders, same magnitudes, only the route differs."
    )
    method = "interoception_fidelity_spearman"
    falsification_consequence = (
        "If the door's Spearman <= 0.95, the live interoception chain does not preserve "
        "the substrate's own magnitude ordinally — the door is not faithful through the "
        "real builders, and the Tier-1 wiring is wrong."
    )
    runner_path = "examples/run_interoception_fidelity.py"

    def __init__(self, *, value_range: float = 1.0e4, max_numbers: int = 2000,
                 fidelity_floor: float = 0.95, target: str = "entity") -> None:
        self.value_range = float(value_range)
        self.max_numbers = int(max_numbers)
        self.fidelity_floor = float(fidelity_floor)
        self.target = target
        self.corpus_name = "fred-real-magnitudes"
        self.n_cycles = 0

    def score(self, cycle_results: list[CycleResult], records: list[CorpusRecord]) -> ScenarioScore:
        raise NotImplementedError("InteroceptionFidelityScenario uses a custom run() loop.")

    def build_claim(self) -> Claim:
        return Claim(
            statement=(
                f"Across up to {self.max_numbers} real magnitudes in (0, "
                f"{self.value_range:g}], the live internal-event chain with interoception "
                f"ON (the door) emits a magnitude-ordered prime: "
                f"Spearman(magnitude, p_thermo) >= {self.fidelity_floor:.2f}, vs the legacy "
                f"name-fingerprint (interoception OFF, ~0.47)."
            ),
            operationalization=(
                "Distinct real FRED |values| within range drive the real static Takwin "
                "builders (_build_internal_event_payload_for_thermodynamic_transition / "
                "_spde_pressure_peak); each payload → real assign_from_internal_event → "
                "p_thermo from the registry, with _use_interoception True (door) and False "
                "(fingerprint); Spearman(magnitude, p_thermo) for both; distinctness."
            ),
            threshold=Threshold(metric="interoception_fidelity_spearman", comparator=">=",
                                value=self.fidelity_floor, units="rank-correlation"),
            h0="H0: door Spearman < 0.95 — the live chain does not preserve the substrate's own magnitude",
            h1=f"H1: door Spearman >= {self.fidelity_floor:.2f} — a faithful, ordered interoception",
        )

    def analysis_plan(self) -> str:
        return ("Drive real Takwin builders across real magnitudes; route each through "
                "real assign_from_internal_event with interoception ON and OFF; "
                "Spearman(magnitude, p_thermo) for both; report distinctness + the contrast.")

    def run(self, substrate: SubstrateUnderTest, *, data_root=None,
            sign_key: bytes = DEFAULT_SIGN_KEY) -> EmpiricalProofRecord:
        import numpy as np
        from kimera_swm.domain.cognitive.takwin import Takwin
        from kimera_swm.domain.prime.arachne_protocol import ArachneProtocol

        mags = _real_magnitudes(self.value_range, self.max_numbers)
        if len(mags) < 50:
            raise RuntimeError(f"interoception-fidelity: only {len(mags)} real magnitudes in range")

        # The two real static builders (tagged so the router picks the right event kind).
        def _thermo(m):
            p = Takwin._build_internal_event_payload_for_thermodynamic_transition(m, 1.0, 1.0, "echoform")
            p["_kind"] = "thermo"
            return p

        def _spde(m):
            p = Takwin._build_internal_event_payload_for_spde_pressure_peak("void_suction", m, "loc0")
            p["_kind"] = "spde"
            return p

        builders = {"thermodynamic_transition": _thermo, "spde_pressure_peak": _spde}

        per_builder: dict[str, dict] = {}
        for kind, build in builders.items():
            # Validate the builder actually carries the magnitude through (no silent loss).
            sample = build(mags[len(mags) // 2])
            assert "magnitude" in sample, f"{kind} builder must pass magnitude"

            rho_path, distinct_path = {}, {}
            for label, flag in (("door", True), ("fingerprint", False)):
                with warnings.catch_warnings():
                    warnings.simplefilter("ignore")
                    ar = ArachneProtocol()
                ar._use_interoception = flag
                primes = [_p_thermo_for(ar, build(m)) for m in mags]
                rho_path[label] = abs(_spearman(np.array(mags), np.array(primes, float)))
                distinct_path[label] = len(set(primes)) / len(primes)
            per_builder[kind] = {"rho": rho_path, "distinct": distinct_path}

        # Primary = the WORST door Spearman across the builders (conservative).
        door_rhos = [v["rho"]["door"] for v in per_builder.values()]
        fingerprint_rhos = [v["rho"]["fingerprint"] for v in per_builder.values()]
        observed = float(min(door_rhos))
        baseline = float(np.mean(fingerprint_rhos))

        claim = self.build_claim()
        dataset = DatasetRef(
            name="fred-real-magnitudes",
            content_hash=content_hash({"n": len(mags), "range": self.value_range,
                                       "lo": mags[0], "hi": mags[-1]}),
            n_records=len(mags), source=str(_FRED_DIR),
            kind="real-macro magnitudes (|v|) within the interoception operating range",
        )
        prereg = PreRegistration(
            config_hash=content_hash({"scenario": self.name, "range": self.value_range,
                                      "max_n": self.max_numbers}),
            data_hash=dataset.content_hash, analysis_plan=self.analysis_plan(),
        )
        verdict = Verdict.decide(observed=observed, threshold=claim.threshold, reasoning=(
            f"door min-Spearman {observed:.4f} (per-builder "
            f"{ {k: round(v['rho']['door'], 4) for k, v in per_builder.items()} }) over "
            f"{len(mags)} real magnitudes [{mags[0]:g}, {mags[-1]:g}]; "
            f"fingerprint baseline mean {baseline:.4f} "
            f"{ {k: round(v['rho']['fingerprint'], 4) for k, v in per_builder.items()} }"))
        evidence = [PillarEvidence(
            pillar="interoception_magnitude_fidelity",
            statistic_name="interoception_fidelity_spearman",
            statistic_value=observed, library="numpy", library_version=np.__version__,
            effect_size=observed - baseline, ci_low=0.0, ci_high=0.0, p_value=None,
            cross_check="passed" if observed >= self.fidelity_floor > baseline else "failed",
            detail={"n_magnitudes": len(mags), "range_lo": mags[0], "range_hi": mags[-1],
                    "value_range": self.value_range, "door_min_spearman": observed,
                    "fingerprint_mean_spearman": baseline,
                    "cross_check_kind": "door_vs_fingerprint_contrast",
                    "per_builder": {k: {"door_rho": v["rho"]["door"],
                                        "fingerprint_rho": v["rho"]["fingerprint"],
                                        "door_distinct": v["distinct"]["door"],
                                        "fingerprint_distinct": v["distinct"]["fingerprint"]}
                                    for k, v in per_builder.items()}},
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
