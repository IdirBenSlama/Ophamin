"""The Sinew-Conservation scenario — empirical conservation law at
substrate decision-points (Round N, 2026-05-17).

Tests whether Kimera's substrate obeys a conservation law of the form

    pressure + tension + scar_coherence_weight_SEED ≈ conserved

at substrate decision-points (Walker M4 lateral_leap / annealing events).

Derived from the Sinew campaign on Family J (SEC 10-K chunks): Phase 0
through Phase 4-extended landed the architectural finding that the
Phase 137 SEED of scar_coherence_weight (the value `_p137_scar_w =
0.5 + 0.5 · _prior_trajectory_coherence` before Phases 148-182
modulations) is the clean linear compensator that supports conservation
at decision-points. See:

  - EMPIRICAL_VALIDATION.md  §"Family X — Sinew" (X4-ext row)
  - Docs_v2/00_journal/entries/2026-05-17-993-*  (initial finding)
  - Docs_v2/00_journal/entries/2026-05-17-992-*  (scar-weakness diagnostic)
  - Docs_v2/00_journal/entries/2026-05-17-991-*  (Tier-2 substrate touch + modulated worse)
  - Docs_v2/00_journal/entries/2026-05-17-990-*  (counter-compensatory decomposition)
  - Docs_v2/00_journal/entries/2026-05-17-989-*  (multi-regression Q4 irreducibility)

Falsifiable claim
=================

> S1: For Walker M4 events (substrate decision-points: lateral_leap halt
>     reason OR walker_annealing_events > 0) in a 500-cycle Family J
>     trajectory, the conservation ratio
>
>         R = median |Δ(P+T+CW_seed)| / median |P+T+CW_seed|
>
>     satisfies R < 0.10.

Threshold rationale: STRONG conservation in Sinew Phase 4-extended
v1 capture measured 0.0810 [CI 0.066, 0.107] for walker_m4 (n=107),
and v2 capture measured 0.0873 (n=105). Pre-registered threshold of
0.10 sits at the STRONG/WEAK boundary established by the campaign
proposal (`experiments/observatory/proposals/sinew_campaign.md`).

REFUTED would mean substrate decision-points no longer conserve stress
under the (P + T + CW_seed) three-term accounting — either the Phase
137 SEED formula `0.5 + 0.5 · _prior_trajectory_coherence` has drifted
(e.g. if the multiplicative constant or floor changed), or the substrate's
pressure-tension coupling has weakened, or the Walker M4 event class
itself shifted semantics.

> S2 (characterisation, no headline): scar superclass (any cycle with
>    scar_id change) conservation ratio. Expected WEAK (~0.10) with
>    magnitude-dependent leak per the diagnostic; reported as evidence.

> S3 (characterisation, no headline): ouroboros conservation ratio.
>    Expected STRONG-to-WEAK at small N (28-35 events typical).

Inputs
======

Trajectory captured via
``experiments/observatory/probes/sinew_phase_4_extended_capture.py``
on Kimera-SWM. The trajectory must be a list-of-dicts (per-cycle
records) with these fields per cycle:

  - pressure_proxies: dict of pressure-named floats
  - tension_proxies: dict of tension-named floats
  - scar: dict containing scar_coherence_weight (Phase 137 seed; the
    legacy field on OrchestratorResult)
  - events: dict containing halt_reason (str) and walker_annealing_events (int)
  - scar_id: str (changes on each scar formation)
  - ouroboros: dict containing ouroboros_total_fused (int, monotone)
  - crashed: bool

The trajectory is expected at JSON path; commit hash and metadata are
read from a sibling metadata.json if present.

Output
======

Signed `EmpiricalProofRecord` with:
- Headline: walker_m4_conservation_ratio (< 0.10 to pass)
- Secondary: ouroboros_conservation_ratio, scar_conservation_ratio,
  scar_magnitude_quartiles (Q1-Q4 leak structure), bootstrap CI

Artifacts
=========

* `experiments/observatory/runs/sinew_phase_4_extended_v2/per_cycle_records.json`
  — capture used for first signed proof at commit `fad09fdda`.
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
from ophamin.seeing.corpus import CorpusRecord
from ophamin.seeing.substrate.base import CycleResult, SubstrateUnderTest


# ─────────────────── statistical helpers ────────────────────────────

def _normalize(arr: np.ndarray) -> np.ndarray:
    """Normalize by std (returns input if std is zero)."""
    s = float(np.std(arr, ddof=0))
    return arr / s if s > 1e-12 else arr


def _aggregate_avg(records: list[dict[str, Any]], section: str, fields: tuple[str, ...]) -> np.ndarray:
    """Average over named fields per cycle; NaN if crashed."""
    out: list[float] = []
    for r in records:
        if r.get("crashed"):
            out.append(float("nan"))
            continue
        vals = [
            float(v)
            for v in (r.get(section, {}).get(f, 0.0) for f in fields)
            if isinstance(v, (int, float)) and math.isfinite(float(v))
        ]
        out.append(float(np.mean(vals)) if vals else 0.0)
    return np.array(out, dtype=float)


def _aggregate_field(records: list[dict[str, Any]], section: str, field: str) -> np.ndarray:
    """Per-cycle scalar from records[i][section][field]."""
    out: list[float] = []
    for r in records:
        if r.get("crashed"):
            out.append(float("nan"))
            continue
        v = r.get(section, {}).get(field, 0.0)
        out.append(float(v) if isinstance(v, (int, float)) else float("nan"))
    return np.array(out, dtype=float)


def _detect_events(records: list[dict[str, Any]]) -> dict[str, list[int]]:
    """Detect event-cycle indices per class: walker_m4, ouroboros, scar."""
    walker_m4: list[int] = []
    ouroboros: list[int] = []
    scar: list[int] = []
    prev_ouro = 0
    prev_scar = ""
    for i, r in enumerate(records):
        if r.get("crashed"):
            continue
        ev = r.get("events", {})
        if ev.get("halt_reason") == "lateral_leap" or int(ev.get("walker_annealing_events", 0)) > 0:
            walker_m4.append(i)
        ouro = int(r.get("ouroboros", {}).get("ouroboros_total_fused", 0))
        if ouro > prev_ouro:
            ouroboros.append(i)
        prev_ouro = ouro
        sid = r.get("scar_id", "")
        if sid and sid != prev_scar:
            scar.append(i)
        prev_scar = sid
    return {"walker_m4": walker_m4, "ouroboros": ouroboros, "scar": scar}


def _conservation_test(
    total_arr: np.ndarray, event_idx: list[int], n_boot: int = 2000
) -> dict[str, Any]:
    """For each event cycle i, compute residual r = total[i-1] − total[i].
    Report median|r| / median|total|, bootstrap 95% CI."""
    residuals: list[float] = []
    totals: list[float] = []
    for i in event_idx:
        if i == 0:
            continue
        before = total_arr[i - 1]
        after = total_arr[i]
        if math.isfinite(before) and math.isfinite(after):
            residuals.append(float(before - after))
            totals.append(float(before))
            totals.append(float(after))
    if len(residuals) < 5:
        return {"insufficient": True, "n": len(residuals)}
    res = np.array(residuals)
    tot = np.array(totals)
    med_res = float(np.median(np.abs(res)))
    med_tot = float(np.median(np.abs(tot)))
    ratio = med_res / med_tot if med_tot > 0 else float("inf")
    rng = np.random.default_rng(seed=0)
    n = len(res)
    boot: list[float] = []
    for _ in range(n_boot):
        idx = rng.integers(0, n, n)
        m_t = float(np.median(np.abs(tot[idx])))
        if m_t > 0:
            boot.append(float(np.median(np.abs(res[idx]))) / m_t)
    ci_lo = float(np.percentile(boot, 2.5)) if boot else float("nan")
    ci_hi = float(np.percentile(boot, 97.5)) if boot else float("nan")
    return {
        "n_events": len(residuals),
        "ratio": ratio,
        "median_abs_residual": med_res,
        "median_abs_total": med_tot,
        "ci_lo": ci_lo,
        "ci_hi": ci_hi,
        "insufficient": False,
    }


# Pressure / tension proxy lists. These mirror the capture probe
# (`sinew_phase_4_extended_capture.py`) — keeping them in sync is the
# scenario's responsibility.
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


class SinewConservationScenario(Scenario):
    """Sinew Phase 4-extended SEED conservation law at substrate decision-points."""

    name = "sinew-conservation"
    tier = Tier.SCIENTIFIC
    family = "conservation"
    goal = (
        "Test whether Kimera's substrate obeys a three-term conservation law "
        "(pressure + tension + scar_coherence_weight_SEED) at Walker M4 "
        "decision-points (lateral_leap / annealing events)."
    )
    explanation = (
        "The Sinew campaign (2026-05-17) tested whether SPDE pressure and "
        "Arachne tension are components of a conserved substrate quantity. "
        "Phase 4 refuted (P+T)-alone conservation; Phase 4-extended "
        "discovered that the Phase 137 SEED of scar_coherence_weight "
        "(`0.5 + 0.5 · _prior_trajectory_coherence`, before Phases 148-182 "
        "modulations) is the clean linear compensator that closes the gap "
        "at substrate decision-points. The modulated CW (post-148-182) "
        "encodes lived experience and counter-compensates conservation. "
        "This scenario verifies the headline finding: SEED-CW conservation "
        "at Walker M4 events. STRONG <0.10."
    )
    method = "median_residual_ratio_at_decision_points"
    falsification_consequence = (
        "Substrate decision-points no longer conserve stress under the "
        "(P + T + CW_seed) accounting — either Phase 137's SEED formula "
        "drifted, the substrate's pressure-tension coupling weakened, or "
        "the Walker M4 event class itself shifted semantics. Any of these "
        "would invalidate the Sinew architectural finding."
    )
    corpus_name = "kimera-sinew-trajectory"
    target = "captured_takwin_trajectory"

    def __init__(
        self,
        trajectory_path: str | Path,
        *,
        conservation_ratio_max: float = 0.10,
    ) -> None:
        self.trajectory_path = Path(trajectory_path).expanduser()
        if not self.trajectory_path.is_file():
            raise FileNotFoundError(
                f"trajectory_path not found: {self.trajectory_path}"
            )
        if not 0.0 < conservation_ratio_max < 1.0:
            raise ValueError(
                f"conservation_ratio_max must be in (0, 1), got "
                f"{conservation_ratio_max}"
            )
        self.conservation_ratio_max = float(conservation_ratio_max)
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
            "SinewConservationScenario uses a custom run() loop reading a "
            "captured trajectory."
        )

    def build_claim(self) -> Claim:
        return Claim(
            statement=(
                f"For Walker M4 events (substrate decision-points: "
                f"`halt_reason == 'lateral_leap'` OR "
                f"`walker_annealing_events > 0`) in a Family J Takwin "
                f"trajectory, the three-term conservation ratio "
                f"R = median|Δ(P+T+CW_seed)| / median|P+T+CW_seed| is "
                f"< {self.conservation_ratio_max:.2f}. The Phase 137 SEED of "
                f"scar_coherence_weight (`0.5 + 0.5 · _prior_trajectory_coherence`, "
                "before Phases 148-182 modulations) is the substrate's "
                "clean linear compensator at decision-points. Pressure "
                "and tension are averages over named proxy fields per "
                "the Sinew Phase 0 inventory (5 pressure + 5 tension); "
                "CW_seed is the legacy `scar_coherence_weight` field on "
                "OrchestratorResult. All inputs std-normalized before "
                "summing."
            ),
            operationalization=(
                "Auto-detect Walker M4 events per cycle from the "
                "trajectory's events dict (lateral_leap halt OR "
                "walker_annealing_events > 0). For each event at index "
                "i > 0, compute residual = total(i-1) − total(i) where "
                "total = norm(P_avg) + norm(T_avg) + norm(CW_seed). Headline "
                "metric = median|residual| / median|total|. Bootstrap "
                "95% CI from 2000 resamples. Verdict on R < threshold. "
                "Secondary characterizations: ouroboros + scar "
                "conservation ratios + scar magnitude quartile leak "
                "structure."
            ),
            threshold=Threshold(
                metric="walker_m4_conservation_ratio",
                comparator="<",
                value=self.conservation_ratio_max,
                units="dimensionless",
            ),
            h0=(
                f"walker_m4_conservation_ratio >= {self.conservation_ratio_max:.2f} "
                "— the substrate does not obey (P+T+CW_seed) conservation "
                "at decision-points; Sinew Phase 4-extended STRONG_PASS "
                "regressed; substrate decision-points fail to compensate "
                "stress redistribution within the three-term accounting"
            ),
            h1=(
                f"walker_m4_conservation_ratio < {self.conservation_ratio_max:.2f} "
                "— substrate decision-points conserve stress at the "
                "STRONG threshold; the Phase 137 SEED is doing genuine "
                "compensatory work; Sinew Phase 4-extended finding "
                "validated at this commit"
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
                "trajectory must be a JSON list of per-cycle records; "
                f"got {type(records).__name__}"
            )
        n_cycles = len(records)
        if n_cycles < 50:
            raise ValueError(
                f"trajectory has only {n_cycles} cycles; need ≥ 50 for "
                "meaningful event statistics"
            )

        # Detect events
        events = _detect_events(records)
        n_walker_m4 = len(events["walker_m4"])
        n_ouroboros = len(events["ouroboros"])
        n_scar = len(events["scar"])

        # Build P, T, CW arrays (Phase 137 seed only)
        P_raw = _aggregate_avg(records, "pressure_proxies", _PRESSURE_FIELDS)
        T_raw = _aggregate_avg(records, "tension_proxies", _TENSION_FIELDS)
        CW_raw = _aggregate_field(records, "scar", "scar_coherence_weight")
        # Normalize for unit-comparable summation (matches Sinew probe convention)
        P = _normalize(P_raw)
        T = _normalize(T_raw)
        CW = _normalize(CW_raw)
        total = P + T + CW

        # Headline measurement: walker_m4 conservation
        walker_r = _conservation_test(total, events["walker_m4"])
        if walker_r.get("insufficient"):
            raise ValueError(
                f"Walker M4 event count too low ({walker_r.get('n')}); "
                "scenario cannot produce verdict"
            )

        # Secondary measurements
        ouro_r = _conservation_test(total, events["ouroboros"])
        scar_r = _conservation_test(total, events["scar"])

        # Scar magnitude quartile breakdown (the leak structure)
        pt = P + T
        mags: list[tuple[int, float]] = []
        for i in events["scar"]:
            if i == 0:
                continue
            if math.isfinite(pt[i - 1]) and math.isfinite(pt[i]):
                mags.append((i, abs(float(pt[i - 1] - pt[i]))))
        mags.sort(key=lambda x: x[1])
        n_sc = len(mags)
        quartile_results: dict[str, dict[str, Any]] = {}
        for qname, slc in (
            ("Q1_smallest", slice(0, n_sc // 4)),
            ("Q2", slice(n_sc // 4, n_sc // 2)),
            ("Q3", slice(n_sc // 2, 3 * n_sc // 4)),
            ("Q4_largest", slice(3 * n_sc // 4, n_sc)),
        ):
            bucket = mags[slc]
            if bucket:
                qr = _conservation_test(total, [i for i, _ in bucket])
                qr["mag_lo"] = bucket[0][1]
                qr["mag_hi"] = bucket[-1][1]
                quartile_results[qname] = qr

        # Verdict
        observed = float(walker_r["ratio"])
        config = {
            "scenario": self.name,
            "trajectory_path": str(self.trajectory_path),
            "conservation_ratio_max": self.conservation_ratio_max,
            "n_cycles": n_cycles,
            "pressure_fields": list(_PRESSURE_FIELDS),
            "tension_fields": list(_TENSION_FIELDS),
            "scar_coherence_field": "scar_coherence_weight",
            "event_class": "walker_m4",
        }
        dataset = DatasetRef(
            name=self.corpus_name,
            content_hash=content_hash({
                "kimera_commit": self._kimera_commit,
                "n_cycles": n_cycles,
                "n_walker_m4": n_walker_m4,
                "n_ouroboros": n_ouroboros,
                "n_scar": n_scar,
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
        verdict = Verdict.decide(
            observed=observed,
            threshold=claim.threshold,
            reasoning=(
                f"Conservation analysis ({n_cycles} cycles, "
                f"{n_walker_m4} walker_m4 events / {n_ouroboros} ouroboros "
                f"/ {n_scar} scar): "
                f"walker_m4 R={walker_r['ratio']:.4f} "
                f"[CI {walker_r['ci_lo']:.4f}, {walker_r['ci_hi']:.4f}]; "
                f"ouroboros R={ouro_r.get('ratio', float('nan')):.4f}; "
                f"scar R={scar_r.get('ratio', float('nan')):.4f}. "
                f"Scar Q4-leak structure: "
                + ", ".join(
                    f"{q}={qr.get('ratio', float('nan')):.4f}"
                    for q, qr in quartile_results.items()
                )
                + "."
            ),
        )

        evidence = [
            PillarEvidence(
                pillar="sinew_conservation",
                statistic_name="walker_m4_conservation_ratio",
                statistic_value=observed,
                library="ophamin.measuring.scenarios.sinew_conservation",
                library_version=__version__,
                effect_size=None,
                ci_low=walker_r["ci_lo"],
                ci_high=walker_r["ci_hi"],
                p_value=None,
                cross_check=(
                    "secondary: ouroboros + scar conservation ratios + "
                    "scar magnitude quartile breakdown (Q1-Q4 leak "
                    "structure). The Phase 137 SEED conserves at "
                    "decision-points (walker_m4) but degrades with event "
                    "magnitude on routine SCAR formation (Q4 near-FAIL). "
                    "Modulated CW (post-148-182) makes conservation "
                    "worse — per CLAUDE.md sum-of-conditional-experience "
                    "axiom + journal entries 989/990/991/992."
                ),
                detail={
                    "kimera_commit": self._kimera_commit,
                    "n_cycles": n_cycles,
                    "n_walker_m4": n_walker_m4,
                    "n_ouroboros": n_ouroboros,
                    "n_scar": n_scar,
                    "walker_m4_ratio": walker_r["ratio"],
                    "walker_m4_ci": [walker_r["ci_lo"], walker_r["ci_hi"]],
                    "walker_m4_median_abs_residual": walker_r["median_abs_residual"],
                    "walker_m4_median_abs_total": walker_r["median_abs_total"],
                    "ouroboros_ratio": ouro_r.get("ratio"),
                    "ouroboros_ci": [ouro_r.get("ci_lo"), ouro_r.get("ci_hi")] if not ouro_r.get("insufficient") else None,
                    "ouroboros_n": ouro_r.get("n_events"),
                    "scar_ratio": scar_r.get("ratio"),
                    "scar_ci": [scar_r.get("ci_lo"), scar_r.get("ci_hi")] if not scar_r.get("insufficient") else None,
                    "scar_n": scar_r.get("n_events"),
                    "scar_magnitude_quartiles": {
                        q: {
                            "ratio": qr.get("ratio"),
                            "ci": [qr.get("ci_lo"), qr.get("ci_hi")],
                            "n_events": qr.get("n_events"),
                            "mag_range": [qr.get("mag_lo"), qr.get("mag_hi")],
                        } for q, qr in quartile_results.items()
                    },
                    "trajectory_path": str(self.trajectory_path),
                    "pressure_fields": list(_PRESSURE_FIELDS),
                    "tension_fields": list(_TENSION_FIELDS),
                    "scar_coherence_field": "scar_coherence_weight",
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
            n_cycles=n_cycles,
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
                    f"{self.name} --trajectory-path {self.trajectory_path}"
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
            "Read captured Kimera trajectory (Sinew Phase 4-extended "
            "shape — per-cycle records with pressure_proxies + "
            "tension_proxies + scar.scar_coherence_weight + events). "
            "Auto-detect Walker M4 / Ouroboros / scar events. Compute "
            "three-term conservation ratio at each event class. Bootstrap "
            "95% CI from 2000 resamples. Verdict on "
            f"walker_m4_conservation_ratio < {self.conservation_ratio_max}. "
            "Secondary characterizations: ouroboros + scar ratios + "
            "scar magnitude quartile leak structure."
        )
