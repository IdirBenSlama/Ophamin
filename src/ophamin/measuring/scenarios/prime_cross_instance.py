"""The Prime Cross-Instance scenario — strongest determinism claim.

Round H U3 confirmed p_identity invariance WITHIN one Takwin (251/251).
Round K extends to ACROSS multiple fresh Takwin instances (subprocess
isolation + reset_all_singletons + warmup): does the same canonical
concept name produce the same prime fields across separate runs?

Per CLAUDE.md F.1.1: *"`p_identity` carries ~16 bits via SHA-256.
Deterministic from `_normalize(concept)` — same canonical name → same
`p_identity` across all runs and Takwin instances."*

This is the STRONGEST possible determinism claim — not just within a
process but across fresh processes that share only the substrate's
source code + warmup discipline.

Falsifiable claims
==================

> U11: Across N fresh Takwin instances, p_identity invariance for
> concepts shared between instances is ≥ 99% (deterministic SHA-256
> derivation).

REFUTED here would mean concept-name normalization is non-deterministic
across processes — a Pattern-T (truthfulness) failure of CLAUDE.md's
"all runs and Takwin instances" claim.

A secondary measurement (no headline threshold) characterises:

* **p_thermo cross-instance invariance** — should ALSO be deterministic
  by CLAUDE.md's *"same concept + same encoder → same prime"* framing.
  Empirically observed to be ~50% in initial probes, suggesting the
  lyriform path has non-determinism (Pattern-T candidate).
* **substrate_state_stamp cross-instance invariance** — should be
  deterministic if the warmup-then-fixed-schedule pattern produces a
  reproducible substrate state.
* **composite cross-instance invariance** — by F.1.1
  `composite = p_thermo × p_identity × stamp`, composite invariance =
  AND of the three factors' invariances.

Inputs
======

Trajectory captured via ``/tmp/capture_kimera_cross_instance.py``: runs
N fresh Takwin processes (each `reset_all_singletons` + warmup + N
stimuli), harvests `ArachneProtocol.lookup(concept)` for each unique
concept seen, and records the (p_identity, p_thermo, stamp, composite)
tuple per concept per instance.

Output
======

Signed proof carrying:

* U11 headline: p_identity invariance rate
* Secondary: per-factor invariance rates (p_thermo, stamp, composite)
* Per-concept invariance records
"""

from __future__ import annotations

import json
import statistics
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


class PrimeCrossInstanceScenario(Scenario):
    """Strongest determinism claim: p_identity invariance across fresh Takwin instances."""

    name = "prime-cross-instance"
    corpus_name = "kimera-cross-instance-prime"
    target = "captured_cross_instance_arachne_lookup"

    def __init__(
        self,
        trajectory_path: str | Path,
        *,
        p_identity_invariance_floor: float = 0.99,
    ) -> None:
        self.trajectory_path = Path(trajectory_path).expanduser()
        if not self.trajectory_path.is_file():
            raise FileNotFoundError(
                f"trajectory_path not found: {self.trajectory_path}"
            )
        if not 0.0 < p_identity_invariance_floor <= 1.0:
            raise ValueError(
                f"p_identity_invariance_floor must be in (0, 1], "
                f"got {p_identity_invariance_floor}"
            )
        self.p_identity_invariance_floor = float(p_identity_invariance_floor)
        self.n_cycles = 0  # static; base.run() overridden

    def score(
        self,
        cycle_results: list[CycleResult],
        records: list[CorpusRecord],
    ) -> ScenarioScore:
        raise NotImplementedError(
            "PrimeCrossInstanceScenario uses a custom run() loop."
        )

    def build_claim(self) -> Claim:
        return Claim(
            statement=(
                f"Across N fresh Takwin instances (subprocess isolation + "
                f"reset_all_singletons + warmup), p_identity invariance "
                f"for concepts shared between instances is "
                f">= {self.p_identity_invariance_floor:.0%}. Validates "
                "CLAUDE.md F.1.1 claim 'same canonical name → same "
                "p_identity across all runs and Takwin instances'."
            ),
            operationalization=(
                "For each concept name observed in ≥ 2 instances, "
                "verify the set of p_identity values has cardinality 1 "
                "(byte-identical across all instances). Headline = "
                "fraction of cross-instance concepts with this property."
            ),
            threshold=Threshold(
                metric="cross_instance_p_identity_invariance_rate",
                comparator=">=",
                value=self.p_identity_invariance_floor,
                units="proportion",
            ),
            h0=(
                f"cross-instance p_identity invariance < "
                f"{self.p_identity_invariance_floor} — concept-name "
                "normalization is non-deterministic across processes; "
                "Pattern-T failure of CLAUDE.md F.1.1 claim"
            ),
            h1=(
                f"cross-instance p_identity invariance >= "
                f"{self.p_identity_invariance_floor} — p_identity is "
                "fully deterministic from canonical concept name, "
                "validating SHA-256 derivation works as expected across "
                "fresh substrate instances"
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
        traj_data = json.loads(self.trajectory_path.read_text())
        instances = traj_data.get("per_instance_results", [])
        if not instances:
            raise ValueError(
                "trajectory has no per_instance_results — ensure capture "
                "via capture_kimera_cross_instance.py"
            )
        n_instances = len(instances)
        kimera_commit = traj_data.get("kimera_commit", "")

        # Re-compute invariance records (trust capture, but verify here)
        all_concepts: set[str] = set()
        for r in instances:
            cp = r.get("per_concept_primes")
            if cp:
                all_concepts.update(cp.keys())

        invariance_records: list[dict[str, Any]] = []
        for concept in sorted(all_concepts):
            instances_with = [
                r for r in instances
                if "per_concept_primes" in r and concept in r["per_concept_primes"]
            ]
            if len(instances_with) < 2:
                continue
            p_identities = set(
                r["per_concept_primes"][concept]["p_identity"]
                for r in instances_with
            )
            p_thermos = set(
                r["per_concept_primes"][concept]["p_thermo"]
                for r in instances_with
            )
            stamps = set(
                r["per_concept_primes"][concept]["substrate_state_stamp"]
                for r in instances_with
            )
            composites = set(
                r["per_concept_primes"][concept]["composite"]
                for r in instances_with
            )
            invariance_records.append({
                "concept": concept,
                "n_instances": len(instances_with),
                "p_identity_unique": len(p_identities),
                "p_thermo_unique": len(p_thermos),
                "stamp_unique": len(stamps),
                "composite_unique": len(composites),
                "p_identity_values": sorted(p_identities)[:4],
                "p_thermo_values": sorted(p_thermos)[:4],
                "stamp_values": sorted(stamps)[:4],
            })

        n_shared = len(invariance_records)
        n_p_identity_inv = sum(1 for r in invariance_records if r["p_identity_unique"] == 1)
        n_p_thermo_inv = sum(1 for r in invariance_records if r["p_thermo_unique"] == 1)
        n_stamp_inv = sum(1 for r in invariance_records if r["stamp_unique"] == 1)
        n_composite_inv = sum(1 for r in invariance_records if r["composite_unique"] == 1)

        p_identity_rate = n_p_identity_inv / max(n_shared, 1)
        p_thermo_rate = n_p_thermo_inv / max(n_shared, 1)
        stamp_rate = n_stamp_inv / max(n_shared, 1)
        composite_rate = n_composite_inv / max(n_shared, 1)

        # Identify the most-varying concepts (Pattern-T candidates)
        non_invariant_p_thermo = [
            r for r in invariance_records if r["p_thermo_unique"] > 1
        ]
        sample_non_invariant = sorted(
            non_invariant_p_thermo,
            key=lambda r: -r["p_thermo_unique"],
        )[:10]

        observed = p_identity_rate
        config = {
            "scenario": self.name,
            "trajectory_path": str(self.trajectory_path),
            "p_identity_invariance_floor": self.p_identity_invariance_floor,
            "n_instances": n_instances,
        }
        dataset = DatasetRef(
            name=self.corpus_name,
            content_hash=content_hash({
                "kimera_commit": kimera_commit,
                "n_instances": n_instances,
            }),
            n_records=n_shared,
            source=str(self.trajectory_path),
            kind="cross-instance-arachne-lookup",
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
                f"Cross-instance invariance ({n_instances} instances, "
                f"{n_shared} shared concepts): "
                f"p_identity {n_p_identity_inv}/{n_shared} = "
                f"{p_identity_rate*100:.2f}%; "
                f"p_thermo {n_p_thermo_inv}/{n_shared} = "
                f"{p_thermo_rate*100:.2f}%; "
                f"stamp {n_stamp_inv}/{n_shared} = {stamp_rate*100:.2f}%; "
                f"composite {n_composite_inv}/{n_shared} = "
                f"{composite_rate*100:.2f}%. "
                f"p_thermo non-determinism candidates: {len(non_invariant_p_thermo)} concepts "
                "with > 1 p_thermo across instances."
            ),
        )

        evidence = [
            PillarEvidence(
                pillar="prime_cross_instance",
                statistic_name="cross_instance_p_identity_invariance_rate",
                statistic_value=observed,
                library="ophamin.measuring.scenarios.prime_cross_instance",
                library_version=__version__,
                effect_size=None,
                ci_low=None,
                ci_high=None,
                p_value=None,
                cross_check=(
                    "secondary: p_thermo / stamp / composite invariance "
                    "rates; non-invariant p_thermo concept list for "
                    "Pattern-T investigation"
                ),
                detail={
                    "kimera_commit": kimera_commit,
                    "n_instances": n_instances,
                    "n_shared_concepts": n_shared,
                    "p_identity_invariance": {
                        "n_invariant": n_p_identity_inv,
                        "rate": p_identity_rate,
                    },
                    "p_thermo_invariance": {
                        "n_invariant": n_p_thermo_inv,
                        "rate": p_thermo_rate,
                    },
                    "stamp_invariance": {
                        "n_invariant": n_stamp_inv,
                        "rate": stamp_rate,
                    },
                    "composite_invariance": {
                        "n_invariant": n_composite_inv,
                        "rate": composite_rate,
                    },
                    "non_invariant_p_thermo_sample": sample_non_invariant,
                    "trajectory_path": str(self.trajectory_path),
                },
            ),
        ]

        # PROVENANCE
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
            n_instances=n_instances,
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
            "Re-compute per-concept invariance records from cross-instance "
            "capture; verdict against p_identity invariance >= "
            f"{self.p_identity_invariance_floor}. Secondary: characterise "
            "p_thermo / stamp / composite invariance rates."
        )
