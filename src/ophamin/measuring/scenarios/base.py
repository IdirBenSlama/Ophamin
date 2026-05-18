"""The catastrophic-scenario layer.

A ``Scenario`` binds a real corpus + a substrate target + a *pre-registered*
falsifiable claim. It streams the corpus through the substrate, scores the run,
and emits a signed ``EmpiricalProofRecord``.

The harness is substrate-agnostic — it runs identically against ``MockSubstrate``
(tests) or ``KimeraAdapter`` (real catastrophic runs). Pre-registration is
captured *before* the run; the proof record is content-addressed and signed.

Scenario registration
=====================

Every concrete subclass of :class:`Scenario` that sets a ``name`` attribute
distinct from the base sentinel ``"scenario"`` is **automatically
registered** in the module-level :data:`SCENARIOS` mapping via the
:meth:`Scenario.__init_subclass__` hook. There is no manual editing of an
``__init__.py`` dict required; the registry is built by class-definition
side effect.

Registration is **loud-failure**:

- A duplicate ``name`` across two subclasses raises
  :class:`DuplicateScenarioNameError` at class-definition time.
- A subclass that sets ``name = "scenario"`` (the unchanged base default)
  raises :class:`ScenarioNameNotOverriddenError`.
- A subclass that opts out via ``register=False`` (e.g. an abstract
  intermediate parent in a class hierarchy) is skipped silently. This is
  the *only* sanctioned skip path.

Third-party / out-of-tree scenarios reach the same registry by simply
inheriting from :class:`Scenario` in their own package; importing their
module fires the registration hook.
"""

from __future__ import annotations

import abc
import enum
import itertools
from dataclasses import dataclass, field
from typing import Iterator

from ophamin import __version__
from ophamin.seeing.corpus import Corpus, CorpusRecord, get_corpus
from pathlib import Path  # noqa: F401 — typed-only Path import

from ophamin.measuring.proof import (
    Claim,
    DatasetRef,  # noqa: F401 — typed reference in _build_provenance
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

#: name reserved for the abstract :class:`Scenario` base — no subclass may
#: keep this value as its ``name`` attribute.
_BASE_SCENARIO_NAME = "scenario"

#: registry of every concrete Scenario subclass that has been imported,
#: keyed by ``cls.name``. Populated by :meth:`Scenario.__init_subclass__`
#: at class-definition time. Read by ``ophamin.measuring.scenarios.__init__``
#: and re-exported as ``SCENARIOS`` for back-compat.
SCENARIOS: dict[str, type["Scenario"]] = {}


class DuplicateScenarioNameError(RuntimeError):
    """Two Scenario subclasses declared the same ``name``.

    Names are the substrate's CLI handle (``ophamin scenario <name>``) and
    the proof-record identifier; duplicates would silently collide. Raised
    at class-definition time so the conflict surfaces at import — the
    earliest possible point.
    """

    def __init__(self, name: str, existing: type, incoming: type) -> None:
        self.name = name
        self.existing = existing
        self.incoming = incoming
        super().__init__(
            f"Scenario name {name!r} is already registered by "
            f"{existing.__module__}.{existing.__qualname__}; "
            f"cannot also register {incoming.__module__}.{incoming.__qualname__}"
        )


class ScenarioNameNotOverriddenError(RuntimeError):
    """A Scenario subclass kept the abstract base's ``name`` sentinel.

    Every concrete scenario must declare its own kebab-case identifier
    (e.g. ``name = "memory-as-deformation"``). Raised at class-definition
    time to catch the omission immediately.
    """

    def __init__(self, cls: type) -> None:
        self.cls = cls
        super().__init__(
            f"{cls.__module__}.{cls.__qualname__} kept the base sentinel "
            f"name {_BASE_SCENARIO_NAME!r}; declare a unique kebab-case name "
            f"(e.g. name = \"my-scenario\")"
        )


class ScenarioMetadataMissingError(RuntimeError):
    """A Scenario subclass omitted one of the required metadata fields.

    Every concrete scenario must declare ``tier`` / ``family`` / ``goal``
    / ``explanation`` so that proof records carry self-describing
    classification + intent text. Raised at class-definition time to
    surface the omission at import — the earliest possible point.
    """

    def __init__(self, cls: type, missing: tuple[str, ...]) -> None:
        self.cls = cls
        self.missing = missing
        details = ", ".join(missing)
        super().__init__(
            f"{cls.__module__}.{cls.__qualname__} is missing required "
            f"Scenario metadata field(s): {details}. Declare them as "
            f"class attributes (tier: Tier; family / goal / explanation: "
            f"non-empty str)."
        )


class Tier(str, enum.Enum):
    """The experimentation tier a scenario lives in.

    Tiers carry epistemic shape, not just bookkeeping:

    - ``SCIENTIFIC`` — claims about substrate *behaviour* (does the
      substrate do X under condition Y?).
    - ``ENGINEERING`` — claims about substrate *cost* (does X stay
      under threshold T?).
    - ``PHILOSOPHICAL`` — claims about substrate *self-model* (does
      the substrate respond differently to self-referential vs
      neutral input?).
    - ``EMPIRICAL_DEEP`` — substrate-physics characterisation
      scenarios that target Kimera's prime apparatus / Φ /
      cross-channel behaviour and mirror Family A-V claims in
      Kimera's ``EMPIRICAL_VALIDATION.md``.
    - ``MEASUREMENT_MACHINERY`` — validation of the upstream libraries
      Ophamin itself depends on (e.g. CRDT laws against pycrdt +
      y-py as cross-check oracle).

    Inheriting from ``str`` makes a Tier serialise as its value
    string in JSON; the JSON proof-record schema sees a plain string,
    not a Python-specific enum encoding.
    """

    SCIENTIFIC = "scientific"
    ENGINEERING = "engineering"
    PHILOSOPHICAL = "philosophical"
    EMPIRICAL_DEEP = "empirical_deep"
    MEASUREMENT_MACHINERY = "measurement_machinery"


#: required Scenario metadata attribute names (validated at class-def time).
_REQUIRED_METADATA: tuple[str, ...] = ("tier", "family", "goal", "explanation")


def _missing_metadata(cls: type) -> tuple[str, ...]:
    """Return the names of any required metadata fields missing on ``cls``.

    *Missing* means: attribute not declared (only inherited from the
    abstract base, which has no value), or declared but empty / sentinel.
    A field that is present and non-empty / non-sentinel passes.

    For ``tier`` specifically: the abstract base declares the attribute
    as a type-annotation only (no value). Subclasses MUST assign an
    actual :class:`Tier` member. ``hasattr`` on the abstract base will
    return False because Python doesn't materialise annotation-only
    class attributes; subclasses that don't assign will inherit that
    absence.
    """
    missing: list[str] = []
    for attr in _REQUIRED_METADATA:
        # Walk the MRO except the abstract base itself. A field is
        # considered set if a non-Scenario-base ancestor declared a
        # non-empty value.
        value = None
        for base in cls.__mro__:
            if base is Scenario:
                break
            if attr in base.__dict__:
                value = base.__dict__[attr]
                break
        if value is None:
            missing.append(attr)
            continue
        if attr == "tier":
            if not isinstance(value, Tier):
                missing.append(attr)
        else:
            if not isinstance(value, str) or not value.strip():
                missing.append(attr)
    return tuple(missing)


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
    """Binds corpus + target + pre-registered claim -> a signed proof record.

    Every concrete subclass declares a metadata block (``name``, ``tier``,
    ``family``, ``goal``, ``explanation``, and optionally ``method`` +
    ``falsification_consequence``) that classifies the experiment and
    explains its intent without requiring the reader to chase docstrings.
    The metadata is validated at class-definition time by
    :meth:`__init_subclass__` (loud-failure on omission) and surfaces into
    every signed ``EmpiricalProofRecord`` produced by the scenario.
    """

    #: Kebab-case CLI identifier (e.g. ``"memory-as-deformation"``).
    #: Must be overridden — :exc:`ScenarioNameNotOverriddenError` is
    #: raised on subclass definition if the sentinel value below is kept.
    name: str = _BASE_SCENARIO_NAME

    #: Experimentation tier — see :class:`Tier` for the five values.
    #: Required on every concrete subclass.
    tier: Tier

    #: Family group (e.g. ``"prime"``, ``"phi"``, ``"immune"``). Two
    #: scenarios in the same family probe the same substrate aspect
    #: from different angles. Used by ``proofs/`` directory organization
    #: and the README scenarios table grouping.
    family: str

    #: One-sentence answer to *"what question does this scenario test?"*
    #: Required; read by ``ophamin scenario list`` + ``ophamin
    #: summarize`` + the proof-record human-facing renderers.
    goal: str

    #: Paragraph explaining *"why this scenario is interesting"* — what
    #: substrate property a verdict on the claim would tell us about,
    #: what would be at stake if the substrate's behaviour shifted.
    #: Required; longer than ``goal``, shorter than the file docstring.
    explanation: str

    #: Optional one-line scoring-shape tag (e.g.
    #: ``"distribution_floor"``, ``"wilson_ci_proportion"``). Empty by
    #: default; helps cross-scenario synthesis classify similar
    #: scoring shapes.
    method: str = ""

    #: Optional one-line description of what a REFUTED verdict would
    #: mean concretely (e.g. *"substrate's recognition layer regressed
    #: beyond the Zetetic-noise bound"*). Empty by default. Read by
    #: ``ophamin diagnose`` when a REFUTED verdict surfaces.
    falsification_consequence: str = ""

    #: Optional path (repo-relative) to a hand-rolled runner script
    #: that emits this scenario's signed proof end-to-end. When set,
    #: the auto-emitted ``Reproduction.command`` in each proof points
    #: at this runner; when empty (the default), the command points
    #: at the generic ``run-all --scenarios <name>`` form via the
    #: ophamin CLI. See ``docs/proposals/PROOF_REPRODUCTION_COMMAND.md``
    #: for the rationale (resolves §7-staleness across all
    #: future-emitted proofs).
    runner_path: str = ""

    corpus_name: str = ""
    target: str = "entity"
    n_cycles: int = 1000

    def __init_subclass__(cls, /, register: bool = True, **kwargs: object) -> None:
        """Auto-register concrete subclasses in :data:`SCENARIOS`.

        Skips registration when ``register=False`` (abstract intermediate
        parents, test-internal scenarios). Otherwise:

        - raises :class:`ScenarioNameNotOverriddenError` if the subclass
          kept the base sentinel name;
        - raises :class:`ScenarioMetadataMissingError` if any of
          ``tier`` / ``family`` / ``goal`` / ``explanation`` is unset or
          empty;
        - raises :class:`DuplicateScenarioNameError` if another subclass
          already registered the same name.

        Re-registration of the *same class object* under the same name is
        idempotent — this is necessary so module reloads (e.g. test
        fixtures, ``importlib.reload``) don't trip the duplicate guard.
        """
        super().__init_subclass__(**kwargs)
        if not register:
            return
        if cls.name == _BASE_SCENARIO_NAME:
            raise ScenarioNameNotOverriddenError(cls)
        missing = _missing_metadata(cls)
        if missing:
            raise ScenarioMetadataMissingError(cls, missing)
        existing = SCENARIOS.get(cls.name)
        if existing is not None and existing is not cls:
            raise DuplicateScenarioNameError(cls.name, existing, cls)
        SCENARIOS[cls.name] = cls

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

    def _build_reproduction_command(self) -> str:
        """Compose the canonical §7 ``Reproduction.command`` for this scenario.

        Routes through three cases:

        1. **``runner_path`` set** — point at the hand-rolled runner
           script (handles multi-target scenarios + scenarios with
           hardcoded sample sizes that the generic runner can't
           parameterize). Closed for the 6 hand-rolled-runner
           scenarios at 0.29.0.
        2. **No ``runner_path`` + default-instantiable** — point at
           the generic ``examples/run_scenario.py {name}`` runner,
           which constructs the class with default ctor args.
        3. **No ``runner_path`` + required ctor args** — emit a
           runnable inline-Python form that calls the ctor with the
           required args captured from ``self.<arg>``. Verbose but
           **actually runnable** when copied verbatim.

        Closes RFC 0002 Phase E3 §7-staleness across all 32
        currently-registered scenarios. See
        ``docs/proposals/PROOF_REPRODUCTION_COMMAND.md`` for the
        full rationale (Option R1, landed at 0.30.0).
        """
        import inspect

        if self.runner_path:
            return (
                f"PYTHONPATH=src .venv/bin/python -u {self.runner_path}"
            )

        sig = inspect.signature(type(self).__init__)
        required = [
            p.name
            for p in sig.parameters.values()
            if p.default is inspect.Parameter.empty
            and p.name != "self"
            and p.kind is not inspect.Parameter.VAR_POSITIONAL
            and p.kind is not inspect.Parameter.VAR_KEYWORD
        ]

        if not required:
            # Default-instantiable scenarios (crosscheck tier, etc.)
            # — the generic runner handles them by name.
            return (
                f"PYTHONPATH=src .venv/bin/python "
                f"examples/run_scenario.py {self.name}"
            )

        # Required-args path: emit an inline-Python form with actual
        # values captured from self.<arg>. The repr() formatting
        # quotes strings safely and reproduces standard types
        # (Path, int, float, etc.) verbatim.
        cls = type(self)
        # Convert Path values to their string form for repr cleanliness.
        from pathlib import Path as _Path

        def _repr_value(value: object) -> str:
            if isinstance(value, _Path):
                return repr(str(value))
            return repr(value)

        arg_repr = ", ".join(
            f"{n}={_repr_value(getattr(self, n))}" for n in required
        )
        return (
            f"PYTHONPATH=src .venv/bin/python -c "
            f'"from {cls.__module__} import {cls.__name__} as S; '
            f"from ophamin.measuring.scenarios.base import DEFAULT_SIGN_KEY; "
            f"from ophamin.seeing.substrate import MockSubstrate; "
            f"r = S({arg_repr}).run(substrate=MockSubstrate(seed=1))"
            f'.sign(DEFAULT_SIGN_KEY); print(r.proof_id)"'
        )

    # -- the harness -------------------------------------------------------

    def _build_provenance(
        self,
        substrate: SubstrateUnderTest,
        dataset: "DatasetRef",
    ) -> ProvenanceGraph:
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
        data_root: str | "Path" | None = None,
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
                command=self._build_reproduction_command(),
            ),
            provenance=self._build_provenance(substrate, dataset).to_prov_json(),
            ophamin_version=__version__,
            ophamin_git_commit=capture_git_commit(_ophamin_project_root()),
        )
        record.sign(sign_key)
        return record
