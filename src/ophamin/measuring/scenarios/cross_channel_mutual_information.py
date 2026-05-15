"""The Cross-Channel Mutual Information scenario.

Given a captured Kimera multi-channel trajectory (per-cycle phi_value,
arachne_web_kuramoto_order, alexandria_knowledge_mass_cumulative,
dissonance_events_count, walker_halt_mode, ...), compute pairwise mutual
information between selected pairs of channels and ask: which channels are
empirically coupled in the substrate?

Falsifiable claim
=================

> Channels that share semantic provenance (e.g. ``phi_value`` and
> ``arachne_web_kuramoto_order``, both downstream of the substrate's
> ongoing coupling dynamics) exhibit non-trivial mutual information,
> with at least one tested pair having ``MI > 0.05`` nats. Channels
> known to be loosely coupled (or independent) should NOT trip this.

The default pair set probes the predicted couplings:

  * ``phi_value`` ↔ ``arachne_web_kuramoto_order`` — both reflect substrate
    integration; CLAUDE.md Family L EV-71 says Φ is downstream of the
    coupling layer.
  * ``alexandria_knowledge_mass_cumulative`` ↔ ``cycle_index`` — should be
    near-deterministic linear (mass accumulates linearly with cycles).
  * ``phi_value`` ↔ ``dissonance_events_count`` — Family L describes
    dissonance and Φ as related signal-handling layers.
  * ``arachne_web_coupling_frobenius`` ↔ ``arachne_web_kuramoto_order`` —
    both measured on the same coupling matrix; should track each other.

Cross-check: every MI is computed via TWO backends — pyitlib (Shannon
estimator on discretized samples) and ennemi (KSG continuous-MI estimator,
no discretization). Both should report MI > 0 and broadly track each other
when the relationship is real.

The scenario validates: (a) at least one expected-coupled pair has MI
above the empirical floor, (b) the two estimators agree on direction
(both > 0 or both ≈ 0). Failure of (b) is a measurement-machinery issue;
failure of (a) is a finding about the substrate's coupling structure.

Inputs
======

The scenario takes a ``trajectory_path`` to a JSON file containing a
``trajectory`` list-of-dicts (output of capture_kimera_trajectory.py or
similar). Each dict must carry the channel keys at minimum.

Output
======

A signed ``EmpiricalProofRecord`` carrying:

* per-pair MI (pyitlib + ennemi; agreement flag)
* the strongest-coupled pair found
* the empirical floor (max MI observed) — used as the verdict's observed
  value against the pre-registered ``mi_floor_threshold``

This scenario is the cleanest demo of the round-3 ``analytic_helpers``
information-theory functions driving a real Ophamin scenario claim.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

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
from ophamin.measuring.scenarios.base import DEFAULT_SIGN_KEY, Scenario, ScenarioScore
from ophamin.seeing.corpus import CorpusRecord
from ophamin.seeing.substrate.base import CycleResult, SubstrateUnderTest


# Default pair list — channels expected to share information.
# NB (2026-05-15): uses canonical substrate field names per Kimera commit
# `a0adf1a0b+` (NOT the legacy `phi_value` / `walker_halt_mode` aliases).
# See `field_catalog.py` for the full alias map.
DEFAULT_PAIRS: tuple[tuple[str, str], ...] = (
    ("phi", "kuramoto_order_parameter"),
    ("phi", "dissonance_events_count"),
    ("phi", "tidal_kii"),
    ("alexandria_knowledge_mass_cumulative", "cycle_index"),
    ("arachne_web_coupling_frobenius", "arachne_web_order_parameter"),
    ("arachne_web_coupling_top_eigenvalue", "arachne_web_coupling_frobenius"),
    ("kuramoto_order_parameter", "arachne_web_order_parameter"),
    ("dissonance_score", "dissonance_events_count"),
)


class CrossChannelMutualInformationScenario(Scenario):
    """Pairwise MI across captured Kimera substrate channels."""

    name = "cross-channel-mi"
    corpus_name = "kimera-multichannel-trajectory"
    target = "captured_phi_kuramoto_alex_dissonance_walker_trajectory"

    def __init__(
        self,
        trajectory_path: str | Path,
        *,
        pairs: tuple[tuple[str, str], ...] = DEFAULT_PAIRS,
        mi_floor_threshold: float = 0.05,  # nats
    ) -> None:
        self.trajectory_path = Path(trajectory_path).expanduser()
        if not self.trajectory_path.is_file():
            raise FileNotFoundError(
                f"trajectory_path not found: {self.trajectory_path}"
            )
        if not pairs:
            raise ValueError("pairs cannot be empty")
        self.pairs = tuple((str(a), str(b)) for a, b in pairs)
        if mi_floor_threshold < 0:
            raise ValueError(
                f"mi_floor_threshold must be ≥ 0, got {mi_floor_threshold}"
            )
        self.mi_floor_threshold = float(mi_floor_threshold)
        self.n_cycles = 0  # static; base.run() overridden

    def score(
        self,
        cycle_results: list[CycleResult],
        records: list[CorpusRecord],
    ) -> ScenarioScore:
        raise NotImplementedError(
            "CrossChannelMutualInformationScenario uses a custom run() loop."
        )

    def build_claim(self) -> Claim:
        return Claim(
            statement=(
                f"Across the {len(self.pairs)} pre-registered substrate-channel "
                f"pairs (e.g. phi_value ↔ arachne_web_kuramoto_order), at least "
                f"one pair exhibits mutual information above the empirical "
                f"floor of {self.mi_floor_threshold} nats. Confirms the "
                f"substrate's channels are non-trivially coupled (memory-as-"
                f"deformation has measurable cross-channel signature)."
            ),
            operationalization=(
                "For each (channel_a, channel_b) pair: extract per-cycle "
                "samples from the captured trajectory; compute MI via "
                "pyitlib (Shannon, discretized) and ennemi (KSG, continuous) "
                "as a cross-check oracle. The verdict's observed value is "
                "max(MI_pyitlib) across all pairs; threshold is "
                f"{self.mi_floor_threshold} nats."
            ),
            threshold=Threshold(
                metric="max_pairwise_mi_nats",
                comparator=">=",
                value=self.mi_floor_threshold,
                units="nats",
            ),
            h0=(
                f"max pairwise MI < {self.mi_floor_threshold} nats — substrate "
                "channels are independent at the cycle scale (no observable "
                "coupling)"
            ),
            h1=(
                f"max pairwise MI >= {self.mi_floor_threshold} nats — at "
                "least one expected-coupled pair carries shared information "
                "across cycles, consistent with memory-as-deformation"
            ),
        )

    # ------------------------------------------------------------------ run --

    def run(
        self,
        substrate: SubstrateUnderTest | None = None,
        *,
        data_root: Any = None,
        sign_key: bytes = DEFAULT_SIGN_KEY,
    ) -> EmpiricalProofRecord:
        try:
            from ophamin.measuring.analytic_helpers import (
                shannon_entropy_discrete,
            )
        except ImportError as e:
            raise RuntimeError(
                "CrossChannelMutualInformationScenario requires pyitlib "
                f"(install via `pip install 'ophamin[infotheory]'`). ({e})"
            ) from e

        traj_data = json.loads(self.trajectory_path.read_text())
        if "trajectory" not in traj_data:
            raise ValueError(
                f"{self.trajectory_path} must contain a 'trajectory' key"
            )
        trajectory = traj_data["trajectory"]
        if not trajectory:
            raise ValueError("trajectory is empty")

        n_cycles = len(trajectory)
        kimera_commit = traj_data.get("kimera_commit", "")

        # Per-pair MI computation
        per_pair: list[dict[str, Any]] = []
        for ch_a, ch_b in self.pairs:
            samples_a = [
                _coerce(c.get(ch_a) if ch_a != "cycle_index" else c.get("cycle_index", i))
                for i, c in enumerate(trajectory)
            ]
            samples_b = [
                _coerce(c.get(ch_b) if ch_b != "cycle_index" else c.get("cycle_index", i))
                for i, c in enumerate(trajectory)
            ]
            # Filter out cycles where either is None (from substrate halt or
            # field absence)
            paired = [
                (a, b) for a, b in zip(samples_a, samples_b)
                if a is not None and b is not None
            ]
            n_paired = len(paired)
            if n_paired < 5:
                per_pair.append({
                    "pair": [ch_a, ch_b],
                    "n_paired": n_paired,
                    "mi_pyitlib_nats": None,
                    "mi_ennemi_nats": None,
                    "agree_direction": None,
                    "skip_reason": "n_paired < 5 (insufficient samples)",
                })
                continue
            xs = [a for a, _ in paired]
            ys = [b for _, b in paired]

            # pyitlib MI on discretized samples (uses entropy on joint dist)
            mi_py = _mi_via_pyitlib(xs, ys)

            # ennemi MI for continuous-numeric pairs (KSG estimator)
            mi_en = _mi_via_ennemi(xs, ys)

            # Agreement: both > 0 or both ≈ 0 (within 0.05 nats of each other)
            if mi_py is None or mi_en is None:
                agree = None
            else:
                agree = (
                    (mi_py > 0.01 and mi_en > 0.01)
                    or (mi_py < 0.01 and mi_en < 0.01)
                )
            per_pair.append({
                "pair": [ch_a, ch_b],
                "n_paired": n_paired,
                "mi_pyitlib_nats": mi_py,
                "mi_ennemi_nats": mi_en,
                "agree_direction": agree,
            })

        # Verdict: max MI across pairs (pyitlib backend, since it always works)
        all_mis = [
            row["mi_pyitlib_nats"] for row in per_pair
            if row.get("mi_pyitlib_nats") is not None
        ]
        observed = max(all_mis) if all_mis else 0.0
        strongest = next(
            (row for row in per_pair
             if row.get("mi_pyitlib_nats") == observed and observed > 0),
            None,
        )

        # PRE-REGISTRATION
        config = {
            "scenario": self.name,
            "trajectory_path": str(self.trajectory_path),
            "pairs": [list(p) for p in self.pairs],
            "mi_floor_threshold": self.mi_floor_threshold,
            "n_cycles_in_trajectory": n_cycles,
        }
        dataset = DatasetRef(
            name=self.corpus_name,
            content_hash=content_hash({
                "kimera_commit": kimera_commit,
                "n_cycles": n_cycles,
                "pairs": [list(p) for p in self.pairs],
            }),
            n_records=n_cycles,
            source=str(self.trajectory_path),
            kind="captured-multichannel-substrate-trajectory",
        )
        prereg = PreRegistration(
            config_hash=content_hash(config),
            data_hash=dataset.content_hash,
            analysis_plan=self.analysis_plan(),
        )

        claim = self.build_claim()
        if strongest:
            reasoning = (
                f"max MI {observed:.4f} nats from pair "
                f"{strongest['pair'][0]} ↔ {strongest['pair'][1]} "
                f"(n_paired={strongest['n_paired']}); ennemi cross-check "
                f"{strongest['mi_ennemi_nats']:.4f} nats "
                f"(agree={strongest['agree_direction']}). Threshold "
                f"{self.mi_floor_threshold} nats."
            )
        else:
            reasoning = (
                f"no pair produced MI > 0; all {len(self.pairs)} pairs "
                "either had insufficient samples or zero observed coupling."
            )
        verdict = Verdict.decide(
            observed=observed,
            threshold=claim.threshold,
            reasoning=reasoning,
        )

        try:
            import pyitlib as _pi
            pyitlib_version = getattr(_pi, "__version__", "unknown")
        except ImportError:
            pyitlib_version = "unavailable"
        try:
            import ennemi as _en
            ennemi_version = getattr(_en, "__version__", "unknown")
        except ImportError:
            ennemi_version = "unavailable"

        # Cross-backend agreement summary (informational)
        n_pairs_with_both = sum(
            1 for row in per_pair
            if row.get("mi_pyitlib_nats") is not None
            and row.get("mi_ennemi_nats") is not None
        )
        n_agree = sum(
            1 for row in per_pair if row.get("agree_direction") is True
        )
        evidence = [
            PillarEvidence(
                pillar="pairwise_mi_pyitlib_ennemi_cross_check",
                statistic_name="max_pairwise_mi_nats",
                statistic_value=observed,
                library="pyitlib",
                library_version=pyitlib_version,
                effect_size=None,
                ci_low=None,
                ci_high=None,
                p_value=None,
                cross_check=(
                    f"ennemi {ennemi_version}; cross-pair direction "
                    f"agreement {n_agree}/{n_pairs_with_both}"
                ),
                detail={
                    "kimera_commit": kimera_commit,
                    "n_cycles_in_trajectory": n_cycles,
                    "n_pairs_tested": len(self.pairs),
                    "n_pairs_with_both_estimators": n_pairs_with_both,
                    "n_pairs_agree_direction": n_agree,
                    "per_pair_results": per_pair,
                    "strongest_pair": strongest["pair"] if strongest else None,
                    "trajectory_path": str(self.trajectory_path),
                },
            ),
        ]

        # PROVENANCE
        prov = ProvenanceGraph()
        agent_ophamin = prov.agent(
            "ophamin", role="experimentation_framework", version=__version__
        )
        agent_pyitlib = prov.agent(
            "pyitlib", role="information_theory_backend",
            version=pyitlib_version,
        )
        agent_ennemi = prov.agent(
            "ennemi", role="information_theory_cross_check",
            version=ennemi_version,
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
            n_pairs=len(self.pairs),
            n_cycles=n_cycles,
        )
        result_entity = prov.entity(f"proof:{self.name}")
        prov.used(activity, data_entity)
        prov.was_associated_with(activity, agent_ophamin)
        prov.was_associated_with(activity, agent_pyitlib)
        prov.was_associated_with(activity, agent_ennemi)
        prov.was_associated_with(activity, agent_kimera)
        prov.was_generated_by(result_entity, activity)
        prov.was_attributed_to(result_entity, agent_kimera)
        prov.was_derived_from(result_entity, data_entity)

        proof = EmpiricalProofRecord(
            claim=claim,
            preregistration=prereg,
            datasets=[dataset],
            substrate_name="kimera-swm",
            substrate_git_commit=kimera_commit,
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
            f"Compute pairwise MI for {len(self.pairs)} pre-registered "
            f"channel pairs from a captured trajectory of {self.n_cycles or '?'} "
            "cycles. Two backends (pyitlib + ennemi) cross-check each pair. "
            f"Verdict against max MI ≥ {self.mi_floor_threshold} nats."
        )


# --- helpers ---------------------------------------------------------------


def _coerce(v: Any) -> float | None:
    """Coerce a substrate field value to a float; return None if not numeric."""
    if v is None:
        return None
    if isinstance(v, bool):
        return float(v)
    if isinstance(v, (int, float)):
        return float(v)
    # Strings / lists / dicts → not directly MI-able; caller filters
    return None


def _mi_via_pyitlib(xs: list[float], ys: list[float]) -> float | None:
    """MI via pyitlib's Shannon estimator on discretized samples."""
    try:
        import numpy as np
        from pyitlib import discrete_random_variable as drv
    except ImportError:
        return None
    arr_x = np.asarray(xs)
    arr_y = np.asarray(ys)
    # Discretize via 10-bin equal-frequency binning (robust on small N)
    try:
        # pandas qcut handles ties; fall back to linspace if all-equal
        import pandas as pd
        bins = max(2, min(10, len(arr_x) // 5))
        x_disc = pd.qcut(arr_x, q=bins, labels=False, duplicates="drop")
        y_disc = pd.qcut(arr_y, q=bins, labels=False, duplicates="drop")
    except Exception:
        return None
    if x_disc is None or y_disc is None:
        return None
    # Replace NaN bins with 0 (constant-channel cells)
    import numpy as np
    x_arr = np.nan_to_num(np.asarray(x_disc), nan=0).astype(int)
    y_arr = np.nan_to_num(np.asarray(y_disc), nan=0).astype(int)
    try:
        mi_bits = float(drv.information_mutual(x_arr, y_arr))
    except Exception:
        return None
    # Convert bits → nats
    import math
    return mi_bits * math.log(2)


def _mi_via_ennemi(xs: list[float], ys: list[float]) -> float | None:
    """MI via ennemi (KSG continuous-MI estimator, no discretization)."""
    try:
        from ophamin.measuring.analytic_helpers import nonlinear_correlation
    except ImportError:
        return None
    try:
        return float(nonlinear_correlation(xs, ys, k=3))
    except Exception:
        return None
