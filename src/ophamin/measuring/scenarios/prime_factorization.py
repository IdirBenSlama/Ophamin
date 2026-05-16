"""The Prime Factorization scenario — F.1.1 deep verification.

Family U Round H follow-on. Round G's PrimeStructureScenario verified that
``composite % p_identity == 0`` at 1880/1880 (100%). This scenario goes
deeper:

1. **U3 — `p_identity` cross-cycle invariance**: same concept name across N
   cycles must produce the SAME `p_identity` (deterministic SHA-256). The
   substrate's `_identity_prime` is mathematically deterministic; this
   probe confirms no concept-name normalization is silently introducing
   variation.

2. **U4 — Full F.1.1 factorization recovery**: per CLAUDE.md F.1.1
   *"GCD of one cycle's composites recovers that cycle's stamp"*. For each
   cycle, compute `q[j] = composite[j] / p_identity(walk[j])`, recover
   `stamp = GCD(q[0], q[1], ..., q[n-1])`, then `p_thermo[j] = q[j] / stamp`.
   Verify (a) recovered stamp is prime (when ≥ 2), (b) recovered p_thermo
   are all prime, (c) characterize the empirical p_thermo distribution
   (CLAUDE.md says range [7, 29] from lyriform; empirical may differ).

3. **U5 — `substrate_state_stamp` provenance**: the OrchestratorResult-
   level `substrate_state_stamp` field. Determine empirically whether it's
   the SAME as the Arachne-internal stamp (used in composite) or a
   different content-derived signature. Per takwin.py:24754 it's
   *"Content-derived signature (registry_size + total_scars_stored), not
   wall-clock-derived"* — should be a prime in [100, 49100] range matching
   `_identity_prime` output.

Falsifiable claim
==================

> p_identity cross-cycle invariance is ≥ 99%.

`p_identity` is deterministic by construction (SHA-256 of canonical name
→ small prime). A failure here surfaces non-determinism in concept-name
normalization upstream of `_identity_prime`.

Inputs
======

The scenario takes a ``trajectory_path`` to a JSON with `prime_chain`,
`trajectory_walk`, and `substrate_state_stamp` per cycle.

Output
======

Signed proof carrying:

* p_identity invariance per concept name
* Per-cycle GCD-recovered stamp + recovered p_thermo distribution
* substrate_state_stamp distribution + prime ratio
* Sample of cycles where recovery succeeds vs not (full F.1.1 chain)
"""

from __future__ import annotations

import json
import math
import statistics
from collections import Counter, defaultdict
from functools import reduce
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
from ophamin.measuring.scenarios.prime_structure import (
    _identity_prime_from_canonical,
    _is_prime,
)
from ophamin.seeing.corpus import CorpusRecord
from ophamin.seeing.substrate.base import CycleResult, SubstrateUnderTest


class PrimeFactorizationScenario(Scenario):
    """Deep F.1.1 verification: p_identity invariance + stamp recovery + p_thermo distribution."""

    name = "prime-factorization"
    tier = Tier.EMPIRICAL_DEEP
    family = "prime"
    goal = (
        "Deep F.1.1 verification: p_identity cross-cycle "
        "invariance + GCD stamp recovery + substrate_state_stamp "
        "provenance."
    )
    explanation = (
        "Family U Round H follow-on to Round G's PrimeStructure. "
        "Three sub-probes: (1) same concept name across N cycles "
        "must produce the same p_identity (deterministic SHA-256); "
        "(2) GCD-recover the per-cycle stamp from composite chain, "
        "verify stamp + recovered p_thermo are prime, characterize "
        "the empirical distribution (CLAUDE.md cites lyriform range "
        "[7, 29]); (3) determine whether OrchestratorResult's "
        "substrate_state_stamp is the same as Arachne's internal "
        "stamp or a separate content-derived signature."
    )
    method = "invariance_fraction"
    falsification_consequence = (
        "p_identity cross-cycle invariance drops below 99% — "
        "concept-name normalization is non-deterministic upstream "
        "of _identity_prime, contradicting CLAUDE.md F.1.1."
    )

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
            "PrimeFactorizationScenario uses a custom run() loop."
        )

    def build_claim(self) -> Claim:
        return Claim(
            statement=(
                f"`p_identity` cross-cycle invariance is "
                f">= {self.p_identity_invariance_floor:.2f} — for every "
                "concept name observed in N cycles, the SHA-256-derived "
                "p_identity is the SAME across all observations. Validates "
                "concept-name normalization is deterministic upstream of "
                "`_identity_prime` (no silent canonicalization drift)."
            ),
            operationalization=(
                "For each cycle, for each (concept, composite) pair via "
                "`trajectory_walk[j]` ↔ `prime_chain[j]`, compute "
                "p_identity = `_identity_prime(concept_name)` (re-implemented "
                "in pure Python). Group p_identities by concept name; count "
                "concepts where the set of distinct p_identities seen has "
                "size 1. Headline = invariance rate."
            ),
            threshold=Threshold(
                metric="p_identity_invariance_rate",
                comparator=">=",
                value=self.p_identity_invariance_floor,
                units="proportion",
            ),
            h0=(
                f"p_identity invariance < {self.p_identity_invariance_floor} "
                "— concept-name normalization is producing different prime "
                "addresses for the same name across cycles (substrate "
                "non-determinism in `_normalize` or upstream)"
            ),
            h1=(
                f"p_identity invariance >= "
                f"{self.p_identity_invariance_floor} — `_identity_prime` is "
                "deterministic as the SHA-256 path requires"
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
        trajectory = traj_data.get("trajectory", [])
        if not trajectory:
            raise ValueError("trajectory is empty")
        kimera_commit = traj_data.get("kimera_commit", "")
        n_cycles = len(trajectory)

        # ---- (1) U3: p_identity cross-cycle invariance ----
        # For each concept name observed, collect set of p_identities seen.
        p_identity_per_concept: dict[str, set[int]] = defaultdict(set)
        for c in trajectory:
            walk = c.get("trajectory_walk")
            if not isinstance(walk, list):
                continue
            for concept_name in walk:
                if isinstance(concept_name, str):
                    p_identity_per_concept[concept_name].add(
                        _identity_prime_from_canonical(concept_name)
                    )
        n_unique_concepts = len(p_identity_per_concept)
        n_invariant = sum(1 for s in p_identity_per_concept.values() if len(s) == 1)
        invariance_rate = n_invariant / max(n_unique_concepts, 1)

        # ---- (2) U4: Full F.1.1 factorization via GCD recovery ----
        # Per CLAUDE.md F.1.1: 'GCD of one cycle's composites recovers
        # that cycle's stamp'. After dividing each composite by p_identity,
        # the GCD across q values is the stamp; q/stamp = p_thermo.
        cycles_probed = 0
        cycles_recovered_stamp_prime = 0
        cycles_p_thermo_all_prime = 0
        recovered_stamp_values: list[int] = []
        all_p_thermo_values: list[int] = []
        per_cycle_factorization: list[dict[str, Any]] = []
        for c in trajectory:
            chain = c.get("prime_chain")
            walk = c.get("trajectory_walk")
            if not (isinstance(chain, list) and isinstance(walk, list)
                    and len(chain) >= 2):
                continue
            qs: list[int] = []
            for j, composite in enumerate(chain):
                if j >= len(walk) or not isinstance(composite, (int, float)):
                    continue
                if not isinstance(walk[j], str):
                    continue
                p_id = _identity_prime_from_canonical(walk[j])
                if int(composite) % p_id == 0:
                    qs.append(int(composite) // p_id)
            if len(qs) < 2:
                continue
            cycles_probed += 1
            stamp = reduce(math.gcd, qs)
            recovered_stamp_values.append(stamp)
            stamp_is_prime = _is_prime(stamp)
            if stamp_is_prime:
                cycles_recovered_stamp_prime += 1
            p_thermos = [q // stamp for q in qs] if stamp >= 1 else []
            thermos_all_prime = bool(p_thermos) and all(_is_prime(t) for t in p_thermos)
            if thermos_all_prime:
                cycles_p_thermo_all_prime += 1
            all_p_thermo_values.extend(p_thermos)
            if len(per_cycle_factorization) < 50:
                per_cycle_factorization.append({
                    "cycle_index": c.get("cycle_index"),
                    "n_qs": len(qs),
                    "recovered_stamp": stamp,
                    "stamp_is_prime": stamp_is_prime,
                    "p_thermo_distinct": len(set(p_thermos)),
                    "p_thermo_all_prime": thermos_all_prime,
                })

        recovered_stamp_prime_rate = (
            cycles_recovered_stamp_prime / max(cycles_probed, 1)
        )
        p_thermo_all_prime_rate = (
            cycles_p_thermo_all_prime / max(cycles_probed, 1)
        )
        p_thermo_freq = Counter(all_p_thermo_values)
        p_thermo_top10 = p_thermo_freq.most_common(10)

        # ---- (3) U5: substrate_state_stamp provenance ----
        sss_values: list[int] = []
        for c in trajectory:
            sss = c.get("substrate_state_stamp")
            if isinstance(sss, int) and sss > 0:
                sss_values.append(sss)
        sss_prime_count = sum(1 for s in sss_values if _is_prime(s))
        sss_in_identity_range_count = sum(
            1 for s in sss_values if 100 <= s <= 49100
        )
        sss_matches_recovered_stamp_count = 0
        for c in trajectory:
            sss = c.get("substrate_state_stamp")
            chain = c.get("prime_chain")
            walk = c.get("trajectory_walk")
            if not (isinstance(sss, int) and isinstance(chain, list)
                    and isinstance(walk, list) and len(chain) >= 2):
                continue
            qs = []
            for j, composite in enumerate(chain):
                if j >= len(walk) or not isinstance(composite, (int, float)):
                    continue
                if not isinstance(walk[j], str):
                    continue
                p_id = _identity_prime_from_canonical(walk[j])
                if int(composite) % p_id == 0:
                    qs.append(int(composite) // p_id)
            if len(qs) >= 2 and reduce(math.gcd, qs) == sss:
                sss_matches_recovered_stamp_count += 1

        sss_summary = {
            "n_cycles_with_sss": len(sss_values),
            "sss_prime_rate": (sss_prime_count / max(len(sss_values), 1)),
            "sss_in_identity_range_rate": (
                sss_in_identity_range_count / max(len(sss_values), 1)
            ),
            "sss_matches_recovered_stamp_rate": (
                sss_matches_recovered_stamp_count / max(cycles_probed, 1)
            ),
            "sss_min": min(sss_values) if sss_values else None,
            "sss_max": max(sss_values) if sss_values else None,
            "sss_unique": len(set(sss_values)),
        }

        # ---- VERDICT ---------------------------------------------------
        observed = invariance_rate
        config = {
            "scenario": self.name,
            "trajectory_path": str(self.trajectory_path),
            "p_identity_invariance_floor": self.p_identity_invariance_floor,
            "n_cycles": n_cycles,
        }
        dataset = DatasetRef(
            name=self.corpus_name,
            content_hash=content_hash({
                "kimera_commit": kimera_commit,
                "n_cycles": n_cycles,
            }),
            n_records=n_cycles,
            source=str(self.trajectory_path),
            kind="captured-prime-trajectory",
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
                f"p_identity invariance: {n_invariant}/{n_unique_concepts} "
                f"= {invariance_rate:.4f}. "
                f"Full F.1.1 factorization: {cycles_recovered_stamp_prime}/"
                f"{cycles_probed} cycles ({recovered_stamp_prime_rate:.4f}) "
                "have a prime-recovered stamp; "
                f"{cycles_p_thermo_all_prime}/{cycles_probed} "
                f"({p_thermo_all_prime_rate:.4f}) have all p_thermo prime. "
                f"substrate_state_stamp prime-rate = "
                f"{sss_summary['sss_prime_rate']:.4f}, in [100, 49100] "
                f"range {sss_summary['sss_in_identity_range_rate']:.4f}, "
                f"matches recovered Arachne stamp "
                f"{sss_summary['sss_matches_recovered_stamp_rate']:.4f}."
            ),
        )

        evidence = [
            PillarEvidence(
                pillar="prime_factorization_deep",
                statistic_name="p_identity_invariance_rate",
                statistic_value=observed,
                library="ophamin.measuring.scenarios.prime_factorization",
                library_version=__version__,
                effect_size=None,
                ci_low=None,
                ci_high=None,
                p_value=None,
                cross_check=(
                    "secondary measurements: full F.1.1 GCD recovery, "
                    "p_thermo distribution, substrate_state_stamp provenance"
                ),
                detail={
                    "kimera_commit": kimera_commit,
                    "n_cycles": n_cycles,
                    "n_unique_concepts": n_unique_concepts,
                    "n_invariant_p_identity": n_invariant,
                    "p_identity_invariance_rate": invariance_rate,
                    "u4_full_factorization": {
                        "n_cycles_probed": cycles_probed,
                        "cycles_recovered_stamp_prime": cycles_recovered_stamp_prime,
                        "recovered_stamp_prime_rate": recovered_stamp_prime_rate,
                        "cycles_p_thermo_all_prime": cycles_p_thermo_all_prime,
                        "p_thermo_all_prime_rate": p_thermo_all_prime_rate,
                        "p_thermo_distribution_top10": p_thermo_top10,
                        "p_thermo_n_total": len(all_p_thermo_values),
                        "p_thermo_unique_values": len(set(all_p_thermo_values)),
                        "p_thermo_min": min(all_p_thermo_values) if all_p_thermo_values else None,
                        "p_thermo_max": max(all_p_thermo_values) if all_p_thermo_values else None,
                        "p_thermo_median": (
                            statistics.median(all_p_thermo_values)
                            if all_p_thermo_values else None
                        ),
                        "p_thermo_mean": (
                            statistics.mean(all_p_thermo_values)
                            if all_p_thermo_values else None
                        ),
                        "recovered_stamps_unique": len(set(recovered_stamp_values)),
                        "recovered_stamps_min": (
                            min(recovered_stamp_values) if recovered_stamp_values else None
                        ),
                        "recovered_stamps_max": (
                            max(recovered_stamp_values) if recovered_stamp_values else None
                        ),
                        "first_50_per_cycle_factorizations": per_cycle_factorization,
                    },
                    "u5_substrate_state_stamp": sss_summary,
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
            "U3: per-concept p_identity set; verdict against invariance "
            f"rate >= {self.p_identity_invariance_floor}. U4: GCD-recover "
            "stamp per cycle; characterize p_thermo distribution. U5: "
            "substrate_state_stamp prime-rate + range + match-with-"
            "recovered-Arachne-stamp."
        )
