"""The catastrophic-scenario layer.

A ``Scenario`` binds a real corpus + a substrate target + a *pre-registered*
falsifiable claim. It streams the corpus through the substrate, scores the run,
and emits a signed ``EmpiricalProofRecord``.

The harness is substrate-agnostic — it runs identically against ``MockSubstrate``
(tests) or ``KimeraAdapter`` (real catastrophic runs). Pre-registration is
captured *before* the run; the proof record is content-addressed and signed.
"""

from __future__ import annotations

import abc
import itertools
from dataclasses import dataclass, field
from typing import Iterator

from ophamin import __version__
from ophamin.seeing.corpus import Corpus, CorpusRecord, get_corpus
from ophamin.measuring.proof import (
    Claim,
    EmpiricalProofRecord,
    PillarEvidence,
    PreRegistration,
    Reproduction,
    Verdict,
    content_hash,
)
from ophamin.comparing.provenance import ProvenanceGraph
from ophamin.comparing.provenance.lineage import _ophamin_project_root, capture_git_commit
from ophamin.seeing.substrate.base import CycleResult, SubstrateUnderTest
from ophamin.seeing.substrate.field_catalog import (
    ScenarioFieldContract,
    validate_contract_against_raw,
)

DEFAULT_SIGN_KEY = b"ophamin-scenario-proof-key"


class ScenarioFieldContractViolation(RuntimeError):
    """Raised when a scenario's field contract is violated by a probe cycle.

    Loud failure on violation surfaces Kimera-side schema drift instead of
    letting the scenario silently degrade. ``violations`` carries the full
    ``ContractViolation`` tuple for the caller to log.
    """

    def __init__(self, scenario_name: str, violations: tuple) -> None:  # type: ignore[type-arg]
        self.scenario_name = scenario_name
        self.violations = violations
        details = "\n  - ".join(
            f"{v.kind}: {v.field_name} — {v.detail}" for v in violations
        )
        super().__init__(
            f"scenario {scenario_name!r} field contract violated by probe cycle:\n  - {details}"
        )


@dataclass
class ScenarioScore:
    """A scenario's read of a completed run — the observed value + the evidence."""

    observed_value: float
    evidence: list[PillarEvidence] = field(default_factory=list)
    inconclusive: bool = False
    reasoning: str = ""


class Scenario(abc.ABC):
    """Binds corpus + target + pre-registered claim -> a signed proof record."""

    name: str = "scenario"
    corpus_name: str = ""
    target: str = "entity"
    n_cycles: int = 1000

    # -- the per-scenario contract -----------------------------------------

    @abc.abstractmethod
    def build_claim(self) -> Claim:
        """The pre-registered falsifiable claim this scenario tests."""

    @abc.abstractmethod
    def score(
        self, cycle_results: list[CycleResult], records: list[CorpusRecord]
    ) -> ScenarioScore:
        """Read the completed run into an observed value + pillar evidence."""

    def field_contract(self) -> ScenarioFieldContract | None:
        """The OrchestratorResult fields this scenario depends on.

        Default ``None`` means no contract — scenarios that don't override
        this run exactly as before (back-compat). Scenarios that DO override
        get loud-failure on the first cycle if a required field is missing
        or has the wrong type. This catches Kimera-side renames at experiment
        setup time instead of silently breaking downstream.

        Returning a contract is purely additive — the scenario still reads
        ``cycle.raw["..."]`` ad-hoc in :meth:`score`. The contract is the
        gate, not the projection.
        """
        return None

    # -- overridable helpers -----------------------------------------------

    def analysis_plan(self) -> str:
        return (
            f"Stream up to {self.n_cycles} real records from the '{self.corpus_name}' "
            f"corpus through the Kimera '{self.target}' target, then score the run "
            f"against the pre-registered threshold."
        )

    def select_records(self, corpus: Corpus) -> Iterator[CorpusRecord]:
        """Which corpus records to use — default is the corpus stream; override to filter."""
        return corpus.records()

    # -- the harness -------------------------------------------------------

    def _build_provenance(self, substrate: SubstrateUnderTest, dataset) -> ProvenanceGraph:
        prov = ProvenanceGraph()
        agent_ophamin = prov.agent(
            "ophamin", role="experimentation_framework", version=__version__
        )
        agent_sut = prov.agent(substrate.name, role="substrate_under_test")
        data_entity = prov.entity(
            f"corpus:{dataset.name}",
            content_hash=dataset.content_hash,
            n_records=dataset.n_records,
            kind=dataset.kind,
        )
        activity = prov.activity(
            f"scenario:{self.name}", target=self.target, n_cycles=self.n_cycles
        )
        result_entity = prov.entity(f"proof:{self.name}")
        prov.used(activity, data_entity)
        prov.was_associated_with(activity, agent_ophamin)
        prov.was_associated_with(activity, agent_sut)
        prov.was_generated_by(result_entity, activity)
        prov.was_attributed_to(result_entity, agent_sut)
        prov.was_derived_from(result_entity, data_entity)
        return prov

    def run(
        self,
        substrate: SubstrateUnderTest,
        *,
        data_root=None,
        sign_key: bytes = DEFAULT_SIGN_KEY,
    ) -> EmpiricalProofRecord:
        """Run the scenario end-to-end and return a signed Empirical Proof Record."""
        corpus = get_corpus(self.corpus_name, data_root)
        corpus.require_available()
        records = list(itertools.islice(self.select_records(corpus), self.n_cycles))
        if not records:
            raise RuntimeError(f"scenario '{self.name}': no corpus records were selected")
        dataset = corpus.dataset_ref()
        claim = self.build_claim()

        # PRE-REGISTRATION — captured before the run (the anti-p-hacking lock)
        config = {
            "scenario": self.name,
            "corpus": self.corpus_name,
            "target": self.target,
            "n_cycles": self.n_cycles,
            "n_records_selected": len(records),
        }
        prereg = PreRegistration(
            config_hash=content_hash(config),
            data_hash=dataset.content_hash,
            analysis_plan=self.analysis_plan(),
        )

        # RUN — stream the real corpus through the substrate
        stimuli = [record.text for record in records]
        cycle_results = substrate.run_batch(stimuli)

        # FIELD-CONTRACT VALIDATION — if the scenario declares a contract,
        # validate the first successful cycle's raw dict against it before
        # scoring. Loud failure on missing-required or type-mismatch surfaces
        # Kimera-side schema drift; silent degradation is forbidden by the
        # framework's no-fallback rule.
        contract = self.field_contract()
        if contract is not None and cycle_results:
            for cr in cycle_results:
                if cr.success:
                    violations = validate_contract_against_raw(contract, cr.raw)
                    fatal = tuple(
                        v for v in violations
                        if v.kind in {"missing_required", "type_mismatch", "family_mismatch"}
                    )
                    if fatal:
                        raise ScenarioFieldContractViolation(self.name, fatal)
                    break

        # SCORE -> VERDICT
        score = self.score(cycle_results, records)
        verdict = Verdict.decide(
            score.observed_value,
            claim.threshold,
            inconclusive=score.inconclusive,
            reasoning=score.reasoning,
        )

        record = EmpiricalProofRecord(
            claim=claim,
            preregistration=prereg,
            datasets=[dataset],
            substrate_name=substrate.name,
            substrate_git_commit=substrate.git_commit(),
            evidence=score.evidence,
            verdict=verdict,
            reproduction=Reproduction(
                command=f"PYTHONPATH=src .venv/bin/python -m ophamin.cli scenario {self.name}"
            ),
            provenance=self._build_provenance(substrate, dataset).to_prov_json(),
            ophamin_version=__version__,
            ophamin_git_commit=capture_git_commit(_ophamin_project_root()),
        )
        record.sign(sign_key)
        return record
