"""Deterministic-seed propagation audit — RFC 0002 Phase E4.

Per [RFC 0002 §3.1](../../../docs/rfc/0002-sota-elevation-stages-5-and-6.md)
Phase E4, every scenario should produce a **bit-identical proof for the
same ``(seed, corpus, substrate_commit, ophamin_commit)`` tuple across
N invocations**. Without this property, the project's reproducibility
claim is rhetoric; with it, an external reviewer can rebuild a tagged
release and demand byte-equal output.

This scenario empirically tests the property. It:

1. Picks a target scenario from :data:`SCENARIOS` (CRDT laws by
   default — small, fast, fully deterministic given seed);
2. Instantiates it twice with identical constructor kwargs;
3. Runs each to emit a signed proof record;
4. Computes a **reproducibility-form hash** of each proof — the
   content hash over every load-bearing field *except* the wall-clock
   fields that genuinely vary per invocation
   (``identity.created_at``, ``preregistration.preregistered_at``,
   the per-pillar timing in ``detail.*_seconds``, and the W3C PROV-O
   ``provenance`` block whose own timestamps drift);
5. Asserts the two hashes match. VALIDATED iff bit-identical.

Falsifiable claim
=================

> Two independent runs of the chosen target scenario with identical
> constructor kwargs produce bit-identical reproducibility-form proof
> hashes.

Falsification means a load-bearing scenario or one of its pillars
exposes non-deterministic behaviour — random seeding leaks, a
substrate's RNG state isn't reset between invocations, or a library
returns inputs in an unspecified order. Any of these breaks the
reproducibility contract that Ophamin's signed-proof discipline
depends on.

Output
======

A signed :class:`EmpiricalProofRecord` whose evidence carries:

* the two reproducibility-form hashes (matching or not);
* the target scenario name + version;
* the target scenario's own proof_ids (for forensic comparison if the
  test fails — the operator can diff the two proofs directly).
"""

from __future__ import annotations

import hashlib
import json
from typing import Any

from ophamin import __version__
from ophamin._stability import Stable
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
from ophamin.measuring.scenarios.base import (
    DEFAULT_SIGN_KEY,
    SCENARIOS,
    Scenario,
    ScenarioScore,
    Tier,
)
from ophamin.seeing.corpus import CorpusRecord
from ophamin.seeing.substrate.base import CycleResult, SubstrateUnderTest


# --- the reproducibility-form hash -----------------------------------------


#: Field paths excluded from the reproducibility-form hash. Each entry
#: is a tuple of nested keys; the canonicalizer walks the body dict
#: and removes each path before hashing.
_REPRODUCIBILITY_EXCLUDED_PATHS: tuple[tuple[str, ...], ...] = (
    # Wall-clock timestamps that genuinely change per invocation.
    ("identity", "created_at"),
    ("preregistration", "preregistered_at"),
    # The PROV-O provenance block carries per-activity timestamps via
    # the prov.activity(started=...) hooks. We don't strip individual
    # timestamps within it; we treat the whole block as transient.
    # If a future hardening tightens what goes into provenance, this
    # can be relaxed to keep more of it.
    ("provenance",),
    # The reproduction.command may include absolute paths (e.g.
    # PYTHONPATH=src .venv/bin/python ...) that vary across hosts.
    ("reproduction", "command"),
)

#: Field paths whose VALUES are stripped from each PillarEvidence's
#: ``detail`` dict — these are timing measurements and per-invocation
#: identifiers that vary per invocation but don't change the
#: scenario's verdict.
_REPRODUCIBILITY_EXCLUDED_DETAIL_KEY_SUFFIXES: tuple[str, ...] = (
    "_seconds",
    "_avg_ms",
    "_wall_time",
    "_perf_counter",
    # Per-invocation proof IDs — content-hashed but include
    # wall-clock identity.created_at in their input, so they drift
    # even when the underlying scenario is reproducible. Excluding
    # them lets the audit scenario be self-reproducible — verified
    # by tests/test_deterministic_seed_audit.py +
    # examples/walkthrough_reproducibility_audit.py.
    "_proof_id",
)


def _strip_path(body: dict[str, Any], path: tuple[str, ...]) -> None:
    """Mutate ``body`` to remove the nested key at ``path``."""
    if not path:
        return
    cursor: Any = body
    for key in path[:-1]:
        if not isinstance(cursor, dict) or key not in cursor:
            return
        cursor = cursor[key]
    if isinstance(cursor, dict):
        cursor.pop(path[-1], None)


def _strip_evidence_detail(body: dict[str, Any]) -> None:
    """Remove timing-suffixed keys from each evidence row's ``detail``."""
    evidence = body.get("evidence")
    if not isinstance(evidence, list):
        return
    for entry in evidence:
        if not isinstance(entry, dict):
            continue
        detail = entry.get("detail")
        if not isinstance(detail, dict):
            continue
        for key in list(detail.keys()):
            if any(key.endswith(suf) for suf in _REPRODUCIBILITY_EXCLUDED_DETAIL_KEY_SUFFIXES):
                detail.pop(key, None)


@Stable(since="0.11.0", notes="The reproducibility-form proof hash for RFC-0002 Phase E4 audits.")
def reproducibility_hash(proof: EmpiricalProofRecord) -> str:
    """Content-addressed hash of a proof's reproducibility form.

    Computes SHA-256 over the canonical JSON form of the proof body
    after stripping every field listed in
    :data:`_REPRODUCIBILITY_EXCLUDED_PATHS` and every timing-suffixed
    key from :class:`PillarEvidence.detail`.

    Two independent invocations of the *same* scenario with the same
    seed + corpus + substrate_commit + ophamin_commit MUST produce the
    same reproducibility_hash. Any drift indicates non-determinism
    leaking into the measurement.
    """
    body = proof._body()
    # Deep-copy via JSON round-trip so we don't mutate the proof.
    body = json.loads(json.dumps(body, sort_keys=True, separators=(",", ":"), default=str))
    for path in _REPRODUCIBILITY_EXCLUDED_PATHS:
        _strip_path(body, path)
    _strip_evidence_detail(body)
    canonical = json.dumps(body, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


# --- the scenario ---------------------------------------------------------


@Stable(since="0.11.0", notes="RFC-0002 Phase E4 reproducibility audit scenario.")
class DeterministicSeedAuditScenario(Scenario):
    """Two-independent-runs reproducibility audit.

    Picks a target scenario (default ``"crdt-laws"`` — small, fast,
    fully deterministic given its ``seed`` parameter). Runs it twice
    with identical constructor kwargs. Computes the
    :func:`reproducibility_hash` of each output proof. VALIDATED iff
    the two hashes match.

    Args:
        target_scenario_name: name of the registered scenario to
            audit. Default ``"crdt-laws"``. Must be present in
            :data:`SCENARIOS`.
        target_scenario_kwargs: kwargs to pass to the target
            scenario's ``__init__``. Default ``{"n_sequences": 5,
            "ops_per_sequence": 5, "seed": 20260517}`` — small enough
            for fast CI, large enough to exercise the cross-backend
            agreement.
        threshold: pass-rate threshold; this scenario is binary
            (matches or doesn't) so the default is ``1.0`` (the
            hashes MUST match).
    """

    name = "deterministic-seed-audit"
    tier = Tier.MEASUREMENT_MACHINERY
    family = "reproducibility"
    goal = (
        "Empirically test the framework's per-scenario reproducibility "
        "contract: two independent invocations with the same seed + "
        "config produce bit-identical reproducibility-form proof hashes."
    )
    explanation = (
        "RFC 0002 Phase E4 names reproducibility as a load-bearing "
        "research-grade-quality property: every scenario must "
        "produce a bit-identical proof for the same (seed, corpus, "
        "substrate_commit, ophamin_commit) tuple. This scenario "
        "validates the property empirically — it runs a target "
        "scenario twice with identical constructor kwargs, computes a "
        "'reproducibility-form' content hash of each proof (stripping "
        "only the wall-clock fields that genuinely vary per "
        "invocation), and asserts the two hashes match. Falsification "
        "means a load-bearing scenario or one of its pillars exposes "
        "non-determinism."
    )
    method = "static_replay"
    falsification_consequence = (
        "Two independent invocations of the target scenario with "
        "identical inputs produce different reproducibility-form "
        "hashes — non-determinism is leaking somewhere in the "
        "measurement pipeline. Operator can diff the two proofs to "
        "isolate the source."
    )
    corpus_name = "synthetic-self-audit"
    target = "ophamin-itself"

    def __init__(
        self,
        *,
        target_scenario_name: str = "crdt-laws",
        target_scenario_kwargs: dict[str, Any] | None = None,
        threshold: float = 1.0,
    ) -> None:
        if not target_scenario_name:
            raise ValueError("target_scenario_name must be non-empty")
        if target_scenario_name not in SCENARIOS:
            raise ValueError(
                f"target_scenario_name {target_scenario_name!r} is not "
                f"registered; known: {sorted(SCENARIOS)}"
            )
        if not 0.0 < threshold <= 1.0:
            raise ValueError(f"threshold must be in (0, 1], got {threshold}")
        self.target_scenario_name = target_scenario_name
        self.target_scenario_kwargs: dict[str, Any] = dict(
            target_scenario_kwargs
            if target_scenario_kwargs is not None
            else {"n_sequences": 5, "ops_per_sequence": 5, "seed": 20260517}
        )
        self.threshold = float(threshold)
        # static scenario — base.run() is overridden
        self.n_cycles = 0

    def score(
        self,
        cycle_results: list[CycleResult],
        records: list[CorpusRecord],
    ) -> ScenarioScore:
        """Never called — base.run() is overridden."""
        raise NotImplementedError(
            "DeterministicSeedAuditScenario uses a custom run() loop; "
            "score() is unreachable."
        )

    def build_claim(self) -> Claim:
        return Claim(
            statement=(
                f"Two independent invocations of the {self.target_scenario_name!r} "
                f"scenario with constructor kwargs {self.target_scenario_kwargs!r} "
                "produce bit-identical reproducibility-form proof hashes. "
                "(RFC 0002 Phase E4: research-grade reproducibility — every "
                "scenario must be deterministic given a fixed seed + corpus + "
                "substrate_commit + ophamin_commit.)"
            ),
            operationalization=(
                "Instantiate the target scenario twice with identical kwargs; "
                "run each to emit a signed proof record; compute "
                "reproducibility_hash(proof) on each (SHA-256 over the canonical "
                "body with wall-clock fields stripped); assert the two hashes "
                "match exactly."
            ),
            threshold=Threshold(
                metric="reproducibility_hash_match",
                comparator=">=",
                value=self.threshold,
                units="proportion",
            ),
            h0=(
                "Two independent runs of the target scenario produce different "
                "reproducibility-form hashes — non-determinism is leaking "
                "somewhere in the measurement pipeline."
            ),
            h1=(
                "Two independent runs produce bit-identical reproducibility-form "
                "hashes — the scenario honours the seed + config contract."
            ),
        )

    def run(
        self,
        substrate: SubstrateUnderTest | None = None,
        *,
        data_root: Any = None,
        sign_key: bytes = DEFAULT_SIGN_KEY,
    ) -> EmpiricalProofRecord:
        target_cls = SCENARIOS[self.target_scenario_name]

        # Build a defensive substrate fallback. The default target
        # ("crdt-laws") ignores `substrate` entirely (its run() is a
        # custom loop), but other targets may not — wrap None in a
        # fresh MockSubstrate so the audit works against any target.
        if substrate is None:
            from ophamin.seeing.substrate.mock import MockSubstrate
            audit_substrate: SubstrateUnderTest = MockSubstrate(seed=20260517)
        else:
            audit_substrate = substrate

        # Two independent invocations with identical kwargs. The
        # scenarios may emit different created_at / wall-times, but
        # everything load-bearing must hash identically.
        first = target_cls(**self.target_scenario_kwargs).run(
            substrate=audit_substrate, sign_key=sign_key
        )
        second = target_cls(**self.target_scenario_kwargs).run(
            substrate=audit_substrate, sign_key=sign_key
        )

        hash_a = reproducibility_hash(first)
        hash_b = reproducibility_hash(second)
        matches = hash_a == hash_b
        observed = 1.0 if matches else 0.0

        # PRE-REGISTRATION — record what we're testing + the input
        # kwargs so the proof itself is reproducible at the meta level.
        config = {
            "scenario": self.name,
            "target_scenario_name": self.target_scenario_name,
            "target_scenario_kwargs": self.target_scenario_kwargs,
            "threshold": self.threshold,
            "excluded_paths": [list(p) for p in _REPRODUCIBILITY_EXCLUDED_PATHS],
            "excluded_detail_key_suffixes": list(
                _REPRODUCIBILITY_EXCLUDED_DETAIL_KEY_SUFFIXES
            ),
        }
        dataset = DatasetRef(
            name=self.corpus_name,
            content_hash=content_hash(config),
            n_records=2,  # the two target-scenario invocations
            source=f"SCENARIOS[{self.target_scenario_name!r}]",
            kind="self-audit-replay",
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
                f"{'match' if matches else 'mismatch'}: "
                f"reproducibility_hash_a={hash_a[:16]}..., "
                f"reproducibility_hash_b={hash_b[:16]}... — "
                f"target scenario was {self.target_scenario_name!r}"
            ),
        )

        evidence = [
            PillarEvidence(
                pillar="reproducibility_audit",
                statistic_name="reproducibility_hash_match",
                statistic_value=observed,
                library="ophamin",
                library_version=__version__,
                effect_size=None,
                ci_low=None,
                ci_high=None,
                p_value=None,
                # The cross-check is the binary hash-equality test itself.
                cross_check="passed" if matches else "failed",
                detail={
                    "cross_check_note": (
                        "Binary match of two reproducibility-form proof hashes. "
                        "The 'first' invocation's proof_id (full) is also recorded "
                        "below so an operator can diff it against 'second' "
                        "directly when an audit fails."
                    ),
                    "target_scenario_name": self.target_scenario_name,
                    "target_scenario_kwargs": dict(self.target_scenario_kwargs),
                    "reproducibility_hash_first": hash_a,
                    "reproducibility_hash_second": hash_b,
                    "first_proof_id": first.proof_id,
                    "second_proof_id": second.proof_id,
                    "first_substrate_git_commit": first.substrate_git_commit,
                    "first_ophamin_git_commit": first.ophamin_git_commit,
                    "first_verdict": first.verdict.outcome,
                    "second_verdict": second.verdict.outcome,
                    "verdict_agreement": first.verdict.outcome == second.verdict.outcome,
                },
            ),
        ]

        # PROVENANCE
        prov = ProvenanceGraph()
        agent_ophamin = prov.agent(
            "ophamin", role="experimentation_framework", version=__version__
        )
        agent_self_audit = prov.agent(
            "deterministic-seed-audit",
            role="self_audit_scenario",
        )
        data_entity = prov.entity(
            f"corpus:{dataset.name}",
            content_hash=dataset.content_hash,
            n_records=dataset.n_records,
            kind=dataset.kind,
        )
        activity = prov.activity(
            f"scenario:{self.name}",
            target=self.target,
            target_scenario=self.target_scenario_name,
        )
        result_entity = prov.entity(f"proof:{self.name}")
        prov.used(activity, data_entity)
        prov.was_associated_with(activity, agent_ophamin)
        prov.was_associated_with(activity, agent_self_audit)
        prov.was_generated_by(result_entity, activity)
        prov.was_derived_from(result_entity, data_entity)

        proof = EmpiricalProofRecord(
            claim=claim,
            preregistration=prereg,
            datasets=[dataset],
            substrate_name="ophamin-self-audit",
            substrate_git_commit=capture_git_commit(_ophamin_project_root()),
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
            f"Instantiate SCENARIOS[{self.target_scenario_name!r}] twice with "
            f"identical kwargs {self.target_scenario_kwargs!r}. Run each to "
            "emit a signed proof. Compute SHA-256 over the canonical body "
            "with wall-clock fields stripped per "
            "_REPRODUCIBILITY_EXCLUDED_PATHS + per-pillar timing keys "
            "matching _REPRODUCIBILITY_EXCLUDED_DETAIL_KEY_SUFFIXES. "
            "VALIDATED iff the two hashes match (binary; 1.0 / 0.0)."
        )


__all__ = [
    "DeterministicSeedAuditScenario",
    "reproducibility_hash",
]
