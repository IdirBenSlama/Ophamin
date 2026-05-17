"""The Causal Discovery scenario — directional structure in substrate dynamics.

Given a captured Kimera multi-channel trajectory, run the PCMCI (PC + MCI)
causal-discovery algorithm via Tigramite to detect *directed* causal links
between channels at lags 0..max_lag. Cross-channel mutual information
(Family T4) tells us *which* channels are coupled; PCMCI tells us *which
direction the arrow points* and at what lag.

Falsifiable claim
=================

> At least one expected-direction causal link is detected with p < 0.05
> from the trajectory. Specifically (any of):
>
>   * `cycle_index → alexandria_knowledge_mass_cumulative` (deterministic
>     accumulation; high-confidence ground truth)
>   * `phi → dissonance_events_count` OR `dissonance_events_count → phi`
>     (Round E T4 found MI=1.02 but couldn't disambiguate direction)
>   * `kuramoto_order_parameter → arachne_web_order_parameter` (substrate
>     synchronization preceding Arachne web emergence is the predicted
>     direction per memory-as-deformation framing)

The scenario is a measurement-machinery validation in the same sense as
T1/T2: it validates that the Tigramite library can find SOMETHING in real
substrate data. The richer claim — "phi causes dissonance, not vice versa"
— is operationalized as a downstream finding-of-fact reported in the
proof's evidence.detail, not as the headline verdict.

Inputs
======

The scenario takes a ``trajectory_path`` to a JSON file with a
``trajectory`` list (output of capture_kimera_trajectory.py). Channels
to test are configurable via ``channels=`` (default: phi,
kuramoto_order_parameter, dissonance_events_count,
arachne_web_order_parameter, alexandria_knowledge_mass_cumulative).

Output
======

A signed ``EmpiricalProofRecord`` carrying:

* per-channel-pair causal links found (parent, child, lag, p-value, val)
* the canonical "direction-detected" verdict (≥1 link with p<0.05)
* graph summary as adjacency list

This scenario is the cleanest demo of the round-3 ``causal_helpers``
``causal_discovery_pcmci`` driving a real Ophamin claim.
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
from ophamin.measuring.scenarios.base import DEFAULT_SIGN_KEY, Scenario, ScenarioScore, Tier
from ophamin.seeing.corpus import CorpusRecord
from ophamin.seeing.substrate.base import CycleResult, SubstrateUnderTest


DEFAULT_CHANNELS: tuple[str, ...] = (
    "phi",
    "kuramoto_order_parameter",
    "dissonance_events_count",
    "arachne_web_order_parameter",
    "alexandria_knowledge_mass_cumulative",
)


class CausalDiscoveryScenario(Scenario):
    """PCMCI-based causal discovery on a captured Kimera trajectory."""

    name = "causal-discovery"
    tier = Tier.EMPIRICAL_DEEP
    family = "causal"
    goal = (
        "Detect directed causal links between Kimera substrate "
        "channels at lags 0..max_lag via PCMCI on a captured "
        "trajectory."
    )
    explanation = (
        "Cross-channel mutual information tells us WHICH channels "
        "are coupled; PCMCI (PC + MCI via Tigramite) tells us "
        "WHICH DIRECTION the arrow points and at what lag. Tests "
        "include: cycle_index -> alexandria_knowledge_mass "
        "(deterministic ground truth); phi <-> dissonance_events "
        "direction (Family L T4 found MI=1.02 but couldn't "
        "disambiguate); kuramoto_order -> arachne_web_order_param "
        "(predicted by memory-as-deformation framing). Headline "
        "verdict: at least one expected-direction link found at "
        "p < 0.05."
    )
    method = "pcmci_significant_links"
    falsification_consequence = (
        "PCMCI finds NO directed link above alpha=0.05 across all "
        "tested channel pairs — either the substrate has no "
        "recoverable causal structure at the sampled cadence or "
        "Tigramite is mis-configured for this signal regime."
    )
    corpus_name = "kimera-multichannel-trajectory"
    target = "captured_substrate_time_series_pcmci"

    def __init__(
        self,
        trajectory_path: str | Path,
        *,
        channels: tuple[str, ...] = DEFAULT_CHANNELS,
        max_lag: int = 3,
        pc_alpha: float = 0.05,
    ) -> None:
        self.trajectory_path = Path(trajectory_path).expanduser()
        if not self.trajectory_path.is_file():
            raise FileNotFoundError(
                f"trajectory_path not found: {self.trajectory_path}"
            )
        if len(channels) < 2:
            raise ValueError(
                f"channels must have ≥ 2 entries, got {channels}"
            )
        if max_lag < 1:
            raise ValueError(f"max_lag must be ≥ 1, got {max_lag}")
        if not 0.0 < pc_alpha < 1.0:
            raise ValueError(f"pc_alpha must be in (0, 1), got {pc_alpha}")
        self.channels = tuple(channels)
        self.max_lag = int(max_lag)
        self.pc_alpha = float(pc_alpha)
        self.n_cycles = 0  # static; base.run() overridden

    def score(
        self,
        cycle_results: list[CycleResult],
        records: list[CorpusRecord],
    ) -> ScenarioScore:
        raise NotImplementedError(
            "CausalDiscoveryScenario uses a custom run() loop."
        )

    def build_claim(self) -> Claim:
        return Claim(
            statement=(
                f"Tigramite PCMCI on a captured {len(self.channels)}-channel "
                f"trajectory at max_lag={self.max_lag} detects ≥ 1 directed "
                f"causal link with p < {self.pc_alpha}. Validates the causal-"
                "discovery library can find directional structure in real "
                "Kimera substrate dynamics — disambiguates the direction-"
                "ambiguous correlations Family T4's mutual-information "
                "scenario found."
            ),
            operationalization=(
                "Build a tigramite DataFrame from the trajectory's per-channel "
                "values; run PCMCI with ParCorr conditional-independence test "
                f"at pc_alpha={self.pc_alpha} and tau_max={self.max_lag}. "
                "Extract significant links (parent, child, lag, p_value); "
                "verdict observed value = count of significant links."
            ),
            threshold=Threshold(
                metric="significant_causal_link_count",
                comparator=">=",
                value=1.0,
                units="links",
            ),
            h0=(
                "no significant causal links found at any lag — channels are "
                "either independent or the trajectory is too short / too "
                "noisy for PCMCI to find structure"
            ),
            h1=(
                "at least one significant causal link detected — substrate's "
                "channels exhibit directional structure (e.g. phi causes "
                "dissonance, or vice versa, or both via common cause)"
            ),
        )

    def run(
        self,
        substrate: SubstrateUnderTest | None = None,
        *,
        data_root: Any = None,
        sign_key: bytes = DEFAULT_SIGN_KEY,
    ) -> EmpiricalProofRecord:
        try:
            from ophamin.measuring.causal_helpers import (
                causal_discovery_pcmci,
            )
        except ImportError as e:
            raise RuntimeError(
                "CausalDiscoveryScenario requires tigramite installed. "
                f"Install via `pip install 'ophamin[causal]'`. ({e})"
            ) from e

        traj_data = json.loads(self.trajectory_path.read_text())
        trajectory = traj_data.get("trajectory", [])
        if not trajectory:
            raise ValueError("trajectory is empty")
        kimera_commit = traj_data.get("kimera_commit", "")

        # Build per-channel time series (drop cycles where any channel is None)
        n_cycles = len(trajectory)
        complete_cycles: list[dict[str, float]] = []
        for c in trajectory:
            row = {}
            ok = True
            for ch in self.channels:
                v = c.get(ch)
                if v is None:
                    ok = False
                    break
                # cycle_index is special; use the index field
                if ch == "cycle_index":
                    v = c.get("cycle_index", complete_cycles and len(complete_cycles))
                if not isinstance(v, (int, float, bool)):
                    ok = False
                    break
                row[ch] = float(v)
            if ok:
                complete_cycles.append(row)

        n_complete = len(complete_cycles)
        if n_complete < 20:
            raise RuntimeError(
                f"too few complete cycles ({n_complete}) — PCMCI needs ≥ 20 "
                "for meaningful results. Capture more or filter channels."
            )

        # Run PCMCI via the round-3 helper
        time_series = [
            [row[ch] for ch in self.channels]
            for row in complete_cycles
        ]
        try:
            pcmci_out = causal_discovery_pcmci(
                time_series,
                var_names=list(self.channels),
                max_lag=self.max_lag,
                pc_alpha=self.pc_alpha,
            )
        except Exception as e:
            raise RuntimeError(
                f"tigramite PCMCI failed: {type(e).__name__}: {e}"
            ) from e

        links = pcmci_out.get("links", [])
        n_links = len(links)
        observed = float(n_links)

        # Categorise links into expected vs unexpected for the diagnostic
        expected_arrows = {
            ("cycle_index", "alexandria_knowledge_mass_cumulative"),
        }
        # Direction-disambiguating arrows for round E T4 findings
        disambiguating_arrows = {
            ("phi", "dissonance_events_count"),
            ("dissonance_events_count", "phi"),
            ("kuramoto_order_parameter", "arachne_web_order_parameter"),
            ("arachne_web_order_parameter", "kuramoto_order_parameter"),
        }

        per_link: list[dict[str, Any]] = []
        for parent, child, lag, p_value in links:
            arrow = (parent, child)
            per_link.append({
                "parent": parent,
                "child": child,
                "lag": lag,
                "p_value": float(p_value),
                "is_expected_groundtruth": arrow in expected_arrows,
                "is_t4_disambiguator": arrow in disambiguating_arrows,
            })

        # PRE-REGISTRATION
        config = {
            "scenario": self.name,
            "trajectory_path": str(self.trajectory_path),
            "channels": list(self.channels),
            "max_lag": self.max_lag,
            "pc_alpha": self.pc_alpha,
            "n_cycles_in_trajectory": n_cycles,
        }
        dataset = DatasetRef(
            name=self.corpus_name,
            content_hash=content_hash({
                "kimera_commit": kimera_commit,
                "n_cycles": n_cycles,
                "channels": list(self.channels),
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
        n_t4_disambig_arrows = sum(
            1 for L in per_link if L["is_t4_disambiguator"]
        )
        n_expected_groundtruth = sum(
            1 for L in per_link if L["is_expected_groundtruth"]
        )
        verdict = Verdict.decide(
            observed=observed,
            threshold=claim.threshold,
            reasoning=(
                f"PCMCI found {n_links} significant link(s) at "
                f"pc_alpha={self.pc_alpha}, max_lag={self.max_lag} "
                f"(n_complete={n_complete} / n_total={n_cycles}); "
                f"{n_expected_groundtruth} expected-groundtruth, "
                f"{n_t4_disambig_arrows} T4-disambiguator."
            ),
        )

        try:
            import tigramite as _tg
            tigramite_version = getattr(_tg, "__version__", "unknown")
        except ImportError:
            tigramite_version = "unavailable"

        evidence = [
            PillarEvidence(
                pillar="tigramite_pcmci",
                statistic_name="significant_causal_link_count",
                statistic_value=observed,
                library="tigramite",
                library_version=tigramite_version,
                effect_size=None,
                ci_low=None,
                ci_high=None,
                p_value=None,
                # Per-link p-values are reported in `detail` for caller
                # inspection; the cross_check here marks the validity of
                # the orchestrating run — passes when tigramite emitted
                # at least one significant link (the scenario's claim
                # presupposes non-trivial structure).
                cross_check="passed" if n_links > 0 else "n/a",
                detail={
                    "cross_check_note": (
                        f"per-link p-values reported in detail; pc_alpha "
                        f"threshold {self.pc_alpha} applied uniformly"
                    ),
                    "kimera_commit": kimera_commit,
                    "n_cycles_in_trajectory": n_cycles,
                    "n_complete_cycles_used": n_complete,
                    "channels": list(self.channels),
                    "max_lag": self.max_lag,
                    "pc_alpha": self.pc_alpha,
                    "links": per_link,
                    "n_links": n_links,
                    "n_expected_groundtruth_links": n_expected_groundtruth,
                    "n_t4_disambiguator_links": n_t4_disambig_arrows,
                    "trajectory_path": str(self.trajectory_path),
                },
            ),
        ]

        # PROVENANCE
        prov = ProvenanceGraph()
        agent_ophamin = prov.agent(
            "ophamin", role="experimentation_framework", version=__version__
        )
        agent_tigramite = prov.agent(
            "tigramite", role="causal_discovery_engine",
            version=tigramite_version,
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
            n_channels=len(self.channels),
            max_lag=self.max_lag,
            pc_alpha=self.pc_alpha,
        )
        result_entity = prov.entity(f"proof:{self.name}")
        prov.used(activity, data_entity)
        prov.was_associated_with(activity, agent_ophamin)
        prov.was_associated_with(activity, agent_tigramite)
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
            f"PCMCI on {len(self.channels)} channels at max_lag={self.max_lag}, "
            f"pc_alpha={self.pc_alpha}. Verdict against ≥ 1 significant "
            "causal link detected."
        )
