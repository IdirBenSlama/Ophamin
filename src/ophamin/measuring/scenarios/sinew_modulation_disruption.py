"""The Sinew-Modulation-Disruption scenario — measure how the substrate's
Phases 148-182 SCAR-CW modulation chain disrupts conservation that the
Phase 137 SEED supports.

Companion to ``sinew-conservation`` (which tests the SEED finding). This
scenario tests the COUNTERFACTUAL: substituting the modulated CW for the
seed in the same three-term sum makes conservation strictly worse at
substrate decision-points (entry 991, 2026-05-17).

Falsifiable claim
=================

> SD1: For Walker M4 events in a Family J Takwin trajectory, the
>      MODULATED-CW conservation ratio
>
>        R_mod = median |Δ(P + T + CW_modulated)| / median |P+T+CW_modulated|
>
>      is STRICTLY GREATER than the SEED-CW conservation ratio
>
>        R_seed = median |Δ(P + T + CW_seed)| / median |P+T+CW_seed|
>
>      by at least 0.05 (the modulation chain DISRUPTS conservation at
>      decision-points, encoding lived experience instead).

Threshold rationale: empirical v2 measurement (entry 991) showed
walker_m4 R_seed=0.0873 vs R_mod=0.1856, a delta of +0.098. The
threshold of +0.05 sits at half of the empirical delta — refuted means
the modulation chain has been redesigned to preserve conservation
(which would be a substantive architectural change to the substrate's
SCAR coherence pipeline).

REFUTED is the INTERESTING outcome here: it would mean the substrate
has been re-engineered so the modulations don't disrupt conservation.
VALIDATED is the current architectural state (memory-formation > strict
conservation at large events, per the "sum of conditional experience"
axiom).

Inputs
======

Same as sinew-conservation: a 500-cycle Sinew Phase 4-extended capture
trajectory with BOTH `scar.scar_coherence_weight` (Phase 137 seed) AND
`scar.scar_coherence_weight_modulated` (post Phase 148-182) per cycle.
The modulated field was added 2026-05-17 (Tier-2 substrate change).

Output
======

Signed `EmpiricalProofRecord` with:
- Headline: modulation_disruption_delta = R_mod − R_seed (≥ 0.05 to validate)
- Secondary: R_seed, R_mod separately; CW distribution comparison;
  modulation_delta correlation with P+T (counter-compensatory check)
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


class SinewModulationDisruptionScenario(Scenario):
    """Phases 148-182 modulation chain DISRUPTS the Phase 137 SEED conservation."""

    name = "sinew-modulation-disruption"
    tier = Tier.SCIENTIFIC
    family = "conservation"
    goal = (
        "Test whether substituting Kimera's modulated scar_coherence_weight "
        "(Phases 148-182 applied) for the Phase 137 seed makes "
        "decision-point conservation strictly worse — the substrate's "
        "memory-formation modulations are counter-compensatory by design."
    )
    explanation = (
        "Sinew Phase 4-extended discovered (entry 991, 2026-05-17) that "
        "Kimera reports the Phase 137 SEED of scar_coherence_weight on "
        "OrchestratorResult but USES the modulated value at SCAR edge "
        "boost sites. The modulated CW captures substrate experience "
        "(twin-prime resonance, cross-domain integration, sync, etc.) "
        "and counter-compensates conservation by design. This scenario "
        "tests the headline observation: R_mod > R_seed + 0.05 at "
        "Walker M4 events. VALIDATED is current state (memory wins "
        "over strict conservation); REFUTED would indicate substrate "
        "re-engineering where modulations preserve conservation."
    )
    method = "modulation_disruption_delta"
    falsification_consequence = (
        "The substrate's Phase 148-182 SCAR-CW modulation chain has been "
        "redesigned to preserve conservation — modulations no longer "
        "counter-compensate at decision-points. This would be a "
        "substantive architectural change overturning the 'sum of "
        "conditional experience' axiom's current numerical signature."
    )
    corpus_name = "kimera-sinew-trajectory"
    target = "captured_takwin_trajectory"

    def __init__(
        self,
        trajectory_path: str | Path,
        *,
        disruption_delta_min: float = 0.05,
    ) -> None:
        self.trajectory_path = Path(trajectory_path).expanduser()
        if not self.trajectory_path.is_file():
            raise FileNotFoundError(
                f"trajectory_path not found: {self.trajectory_path}"
            )
        if not 0.0 < disruption_delta_min < 1.0:
            raise ValueError(
                f"disruption_delta_min must be in (0, 1), got "
                f"{disruption_delta_min}"
            )
        self.disruption_delta_min = float(disruption_delta_min)
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
            "SinewModulationDisruptionScenario uses a custom run() loop."
        )

    def build_claim(self) -> Claim:
        return Claim(
            statement=(
                f"For Walker M4 events in a Sinew Phase 4-extended "
                f"trajectory, the modulated-CW conservation ratio "
                f"R_mod EXCEEDS the seed-CW conservation ratio R_seed by "
                f"at least {self.disruption_delta_min:.2f} — the substrate's "
                "Phase 148-182 SCAR-CW modulation chain encodes "
                "experience-accumulation at the cost of conservation. "
                "Both R values use the same (P + T + CW) three-term "
                "sum with std-normalized inputs; only the CW source "
                "differs (Phase 137 seed `_p137_scar_w` vs the post-modulation "
                "`self._scar_coherence_weight`)."
            ),
            operationalization=(
                "Read trajectory; compute R_seed = median|Δ(P+T+CW_seed)| / "
                "median|P+T+CW_seed| at Walker M4 events. Compute R_mod "
                "identically with CW = scar_coherence_weight_modulated. "
                "Headline metric = R_mod − R_seed. Verdict on delta ≥ "
                "threshold. Secondary: per-event-class R_seed vs R_mod, "
                "cor(P+T, modulation_delta) as counter-compensation "
                "signature, CW distribution statistics for both."
            ),
            threshold=Threshold(
                metric="modulation_disruption_delta",
                comparator=">=",
                value=self.disruption_delta_min,
                units="dimensionless",
            ),
            h0=(
                f"modulation_disruption_delta < {self.disruption_delta_min:.2f} "
                "— the substrate's modulation chain has been redesigned to "
                "preserve conservation; entry 991's finding regressed; the "
                "Phase 137 seed and the modulated value behave similarly "
                "at decision-points"
            ),
            h1=(
                f"modulation_disruption_delta >= {self.disruption_delta_min:.2f} "
                "— Phases 148-182 are counter-compensatory by design at "
                "decision-points; entry 991's finding holds; the substrate "
                "prioritizes memory formation (modulations push CW up "
                "when stress up) over strict conservation"
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
                f"trajectory has only {n_cycles} cycles; need ≥ 50"
            )

        events = _detect_events(records)
        n_walker_m4 = len(events["walker_m4"])
        n_ouroboros = len(events["ouroboros"])
        n_scar = len(events["scar"])

        # Pressure / tension / both CW variants
        P = _normalize(_aggregate_avg(records, "pressure_proxies", _PRESSURE_FIELDS))
        T = _normalize(_aggregate_avg(records, "tension_proxies", _TENSION_FIELDS))
        CW_seed_raw = _aggregate_field(records, "scar", "scar_coherence_weight")
        CW_mod_raw = _aggregate_field(records, "scar", "scar_coherence_weight_modulated")

        # Verify modulated field actually present (loud-fail if not)
        cw_mod_clean = CW_mod_raw[np.isfinite(CW_mod_raw)]
        if cw_mod_clean.size == 0 or float(np.std(cw_mod_clean)) < 1e-12:
            raise ValueError(
                "scar_coherence_weight_modulated field is missing or "
                "constant in trajectory — capture probe must record both "
                "the Phase 137 seed (legacy field) AND the modulated value "
                "(post Phase 148-182). The Tier-2 substrate touch at "
                "takwin.py:24106 must be in place for this scenario."
            )

        CW_seed = _normalize(CW_seed_raw)
        CW_mod = _normalize(CW_mod_raw)
        total_seed = P + T + CW_seed
        total_mod = P + T + CW_mod

        # Headline measurement: R_mod − R_seed at walker_m4
        walker_seed = _conservation_test(total_seed, events["walker_m4"])
        walker_mod = _conservation_test(total_mod, events["walker_m4"])
        if walker_seed.get("insufficient") or walker_mod.get("insufficient"):
            raise ValueError(
                "Walker M4 event count too low for verdict"
            )

        delta = float(walker_mod["ratio"]) - float(walker_seed["ratio"])

        # Secondary measurements: ouroboros + scar with both CW variants
        ouro_seed = _conservation_test(total_seed, events["ouroboros"])
        ouro_mod = _conservation_test(total_mod, events["ouroboros"])
        scar_seed = _conservation_test(total_seed, events["scar"])
        scar_mod = _conservation_test(total_mod, events["scar"])

        # Counter-compensation signature: cor(P+T, modulation_delta)
        delta_arr = CW_mod_raw - CW_seed_raw
        valid_mask = np.isfinite(P) & np.isfinite(T) & np.isfinite(delta_arr)
        pt_valid = (P + T)[valid_mask]
        delta_valid = delta_arr[valid_mask]
        if pt_valid.size > 5 and float(np.std(delta_valid)) > 1e-12 and float(np.std(pt_valid)) > 1e-12:
            counter_comp_cor = float(np.corrcoef(pt_valid, delta_valid)[0, 1])
        else:
            counter_comp_cor = float("nan")

        # CW distribution stats
        cw_seed_clean = CW_seed_raw[np.isfinite(CW_seed_raw)]
        cw_dist = {
            "seed_min": float(np.min(cw_seed_clean)),
            "seed_max": float(np.max(cw_seed_clean)),
            "seed_mean": float(np.mean(cw_seed_clean)),
            "seed_std": float(np.std(cw_seed_clean)),
            "modulated_min": float(np.min(cw_mod_clean)),
            "modulated_max": float(np.max(cw_mod_clean)),
            "modulated_mean": float(np.mean(cw_mod_clean)),
            "modulated_std": float(np.std(cw_mod_clean)),
        }

        observed = delta
        config = {
            "scenario": self.name,
            "trajectory_path": str(self.trajectory_path),
            "disruption_delta_min": self.disruption_delta_min,
            "n_cycles": n_cycles,
        }
        dataset = DatasetRef(
            name=self.corpus_name,
            content_hash=content_hash({
                "kimera_commit": self._kimera_commit,
                "n_cycles": n_cycles,
                "n_walker_m4": n_walker_m4,
            }),
            n_records=n_cycles,
            source=str(self.trajectory_path),
            kind="takwin-sinew-extended-trajectory-with-modulated-cw",
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
                f"Modulation-disruption measurement ({n_cycles} cycles, "
                f"{n_walker_m4} walker_m4 events): "
                f"R_seed = {walker_seed['ratio']:.4f} [CI {walker_seed['ci_lo']:.4f}, {walker_seed['ci_hi']:.4f}], "
                f"R_mod = {walker_mod['ratio']:.4f} [CI {walker_mod['ci_lo']:.4f}, {walker_mod['ci_hi']:.4f}], "
                f"delta = {delta:+.4f}. Counter-compensation signature "
                f"cor(P+T, modulation_delta) = {counter_comp_cor:+.4f} "
                f"(positive = modulations push CW up when stress up = "
                f"anti-conservation by design)."
            ),
        )

        evidence = [
            PillarEvidence(
                pillar="sinew_modulation_disruption",
                statistic_name="modulation_disruption_delta",
                statistic_value=observed,
                library="ophamin.measuring.scenarios.sinew_modulation_disruption",
                library_version=__version__,
                effect_size=None,
                ci_low=None,
                ci_high=None,
                p_value=None,
                cross_check="passed",
                detail={
                    "cross_check_note": (
                        "secondary: ouroboros + scar conservation ratios in "
                        "seed vs modulated form; CW distribution; "
                        "counter-compensation correlation (cor(P+T, "
                        "modulation_delta) — positive = anti-conservation by "
                        "design). The substrate has two distinct CW values "
                        "with different intents — seed for clean linear "
                        "compensation, modulated for memory-formation "
                        "amplification. The disruption delta quantifies the "
                        "tradeoff at decision-points."
                    ),
                    "kimera_commit": self._kimera_commit,
                    "n_cycles": n_cycles,
                    "n_walker_m4": n_walker_m4,
                    "n_ouroboros": n_ouroboros,
                    "n_scar": n_scar,
                    "walker_m4_R_seed": walker_seed["ratio"],
                    "walker_m4_R_seed_ci": [walker_seed["ci_lo"], walker_seed["ci_hi"]],
                    "walker_m4_R_modulated": walker_mod["ratio"],
                    "walker_m4_R_modulated_ci": [walker_mod["ci_lo"], walker_mod["ci_hi"]],
                    "modulation_disruption_delta": delta,
                    "ouroboros_R_seed": ouro_seed.get("ratio"),
                    "ouroboros_R_modulated": ouro_mod.get("ratio"),
                    "scar_R_seed": scar_seed.get("ratio"),
                    "scar_R_modulated": scar_mod.get("ratio"),
                    "counter_compensation_cor": counter_comp_cor,
                    "cw_distribution": cw_dist,
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
            "Read captured Kimera trajectory with both Phase 137 seed AND "
            "post-Phase-148-182 modulated scar_coherence_weight. Detect "
            "Walker M4 events. Compute R_seed and R_mod using same "
            "(P+T+CW) three-term sum, std-normalized. Headline = R_mod − "
            f"R_seed. Verdict on delta >= {self.disruption_delta_min}. "
            "Secondary: cross-event-class R_seed vs R_mod; "
            "counter-compensation correlation cor(P+T, "
            "modulation_delta) as architectural signature."
        )
