"""Zero is the Void — does the substrate's response to the number ZERO collocate
with its VOID/collapse state, and is that void a PLENUM or a STILLNESS?

Owner reframe (2026-05-24): the "sin of Zero" (value 0 → no signal → rest) may be
mis-framed. Kimera's void (`null_state`) is a FIRST-CLASS entity — "a region where
a concept has constructively collapsed due to irresolvable contradiction" — not
emptiness. And in number theory a zero (the Riemann ζ-zeros) is the densest object
there is: by the explicit formula the zeros encode the entire prime distribution.
So is zero the void the number line hangs from? A web-level proxy said the void is
REAL but read as a STALL, not a plenum — but that proxy isn't the cognitive void.
This measures it PROPERLY: the real Takwin cycle, four stimulus conditions.

Conditions (each streamed through the full entity cycle):
  neutral       — low-tension declaratives (rest/idle)
  zero          — the number/concept zero
  numbers       — small integers (beads on the line)
  contradiction — paradoxes (→ the substrate's real void/collapse)

Signature = per-condition mean of the substrate's VOID-class fields
(void/null/contradiction/collapse/dissonance) and ENTROPY-class fields
(entropy/varentropy/uncertainty) read from CycleResult.raw.

Falsifiable (primary): zero sits NEARER the void than rest —
  zero_void_proximity = dist(zero, neutral) − dist(zero, contradiction) > 0.
Secondary rungs in evidence.detail: void REAL (dist(contradiction,neutral)) and
PLENUM (entropy(contradiction) / entropy(neutral)).
REFUTED (zero nearer rest) is the honest "the sin is real on the live substrate"
result — useful either way.
"""
from __future__ import annotations

import math
from collections import defaultdict

import statsmodels as _sm  # noqa: F401

from ophamin import __version__
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

_VOID_KEYS = ("void", "null", "contradiction", "collapse", "dissonance", "paradox")
_ENTROPY_KEYS = ("entropy", "varentropy", "uncertainty")

_CONDITIONS: dict[str, list[str]] = {
    "neutral": [
        "the wall is grey", "a chair stands there", "water is wet",
        "the door is closed", "it is afternoon", "the box holds books",
        "a road goes east", "the lamp is off",
    ],
    "zero": [
        "0", "zero", "0.0", "nought", "nil", "the number zero", "0 0 0", "zero zero",
    ],
    "numbers": [
        "1", "2", "3", "7", "12", "42", "99", "5",
    ],
    "contradiction": [
        "this statement is false", "this sentence is a lie",
        "it is true and it is false", "a square circle exists",
        "the list of all lists that exclude themselves", "yes means no here",
        "always never", "it is both fully open and fully closed",
    ],
}


def _flatten_numeric(raw: object) -> dict[str, float]:
    out: dict[str, float] = {}

    def walk(v: object, path: str) -> None:
        if isinstance(v, dict):
            for k, vv in v.items():
                walk(vv, f"{path}.{k}" if path else str(k))
        elif isinstance(v, bool):
            pass
        elif isinstance(v, (int, float)):
            fv = float(v)
            if math.isfinite(fv):
                out[path] = fv

    walk(raw, "")
    return out


def _keep(key: str, groups: tuple[str, ...]) -> bool:
    k = key.lower()
    return any(g in k for g in groups)


class ZeroVoidScenario(Scenario):
    """Measure whether the number zero collocates with the substrate's void, and
    whether the void is a high-entropy plenum or a stillness."""

    name = "zero-void"
    tier = Tier.SCIENTIFIC
    family = "ontology"
    goal = (
        "Does the substrate's response to the number ZERO collocate with its "
        "VOID/collapse state rather than idle rest — and is that void a "
        "high-entropy plenum (zeta-zero-like) or a stillness?"
    )
    explanation = (
        "Kimera's void (null_state) is a first-class collapse-entity, not "
        "emptiness; and the Riemann zeta-zeros encode the whole prime field. So "
        "zero may be the void the number line hangs from, not a dead bead. This "
        "streams neutral/zero/numbers/contradiction stimuli through the full "
        "cycle and compares their void+entropy signatures: is zero nearer the "
        "void than rest, and is the void richer than rest?"
    )
    method = "zero_void_proximity"
    falsification_consequence = (
        "If zero sits nearer rest than the void, the 'sin of Zero' is real on the "
        "live substrate — zero is admitted as absence, not as the void; a "
        "void-routing for zero is needed before the number sense goes live."
    )
    runner_path = "examples/run_zero_void.py"

    def __init__(self, *, cycles_per_condition: int = 8, target: str = "entity") -> None:
        self.cycles_per_condition = int(cycles_per_condition)
        self.target = target
        self.corpus_name = "zero-void-conditions"
        self.n_cycles = 0  # custom run loop

    def score(self, cycle_results: list[CycleResult], records: list[CorpusRecord]) -> ScenarioScore:
        raise NotImplementedError("ZeroVoidScenario uses a custom run() loop.")

    def build_claim(self) -> Claim:
        return Claim(
            statement=(
                "The substrate's response to the number ZERO collocates with its "
                "VOID/collapse state (contradiction stimuli) more than with idle "
                "rest (neutral stimuli): zero_void_proximity > 0."
            ),
            operationalization=(
                "Stream four stimulus conditions (neutral, zero, numbers, "
                "contradiction) through the full entity cycle; per condition, take "
                "the mean over cycles of the substrate's void-class "
                "(void/null/contradiction/collapse/dissonance) and entropy-class "
                "(entropy/varentropy/uncertainty) raw fields; z-normalise across "
                "conditions; zero_void_proximity = dist(zero, neutral) − "
                "dist(zero, contradiction)."
            ),
            threshold=Threshold(
                metric="zero_void_proximity", comparator=">", value=0.0, units="z-distance",
            ),
            h0="H0: zero sits nearer rest than the void (proximity <= 0) — zero is absence",
            h1="H1: zero sits nearer the void than rest (proximity > 0) — zero is the void",
        )

    def analysis_plan(self) -> str:
        return (
            "Per condition: stream stimuli, flatten CycleResult.raw, keep "
            "void+entropy fields, average over cycles. z-normalise the 4 "
            "signature vectors; report zero_void_proximity = dist(zero,neutral) − "
            "dist(zero,contradiction); secondary: dist(contradiction,neutral) "
            "(void real?) and entropy(contradiction)/entropy(neutral) (plenum?)."
        )

    def run(
        self,
        substrate: SubstrateUnderTest,
        *,
        data_root=None,
        sign_key: bytes = DEFAULT_SIGN_KEY,
    ) -> EmpiricalProofRecord:
        import numpy as np

        sigs: dict[str, dict[str, float]] = {}
        ent_means: dict[str, float] = {}
        for cond, stim in _CONDITIONS.items():
            stimuli = stim[: self.cycles_per_condition]
            cyc = substrate.run_batch(stimuli)
            ok = [c for c in cyc if getattr(c, "success", True)]
            if len(ok) < 2:
                raise RuntimeError(f"zero-void: condition {cond!r} produced <2 cycles")
            acc: dict[str, list[float]] = defaultdict(list)
            ent: list[float] = []
            for c in ok:
                flat = _flatten_numeric(c.raw)
                for k, v in flat.items():
                    if _keep(k, _VOID_KEYS) or _keep(k, _ENTROPY_KEYS):
                        acc[k].append(v)
                    if _keep(k, _ENTROPY_KEYS):
                        ent.append(v)
            sigs[cond] = {k: (sum(v) / len(v)) for k, v in acc.items() if v}
            ent_means[cond] = (sum(ent) / len(ent)) if ent else 0.0

        # align fields present in ALL conditions
        common = set.intersection(*[set(s) for s in sigs.values()]) if sigs else set()
        if len(common) < 3:
            raise RuntimeError(
                f"zero-void: only {len(common)} void/entropy fields common to all "
                "conditions — substrate does not expose enough void signal to measure"
            )
        fields = sorted(common)
        conds = ["neutral", "zero", "numbers", "contradiction"]
        M = np.array([[sigs[c][f] for f in fields] for c in conds], dtype=float)
        Z = (M - M.mean(0)) / (M.std(0) + 1e-9)

        def d(a: str, b: str) -> float:
            return float(np.linalg.norm(Z[conds.index(a)] - Z[conds.index(b)]))

        void_real = d("contradiction", "neutral")
        plenum_ratio = (ent_means["contradiction"] / ent_means["neutral"]
                        if ent_means["neutral"] else float("nan"))
        zero_to_rest = d("zero", "neutral")
        zero_to_void = d("zero", "contradiction")
        proximity = zero_to_rest - zero_to_void

        observed = float(proximity)
        claim = self.build_claim()
        dataset = DatasetRef(
            name="zero-void-conditions",
            content_hash=content_hash({k: v for k, v in _CONDITIONS.items()}),
            n_records=sum(len(v[: self.cycles_per_condition]) for v in _CONDITIONS.values()),
            source="in-scenario stimulus conditions",
            kind="ontology-probe (neutral/zero/numbers/contradiction)",
        )
        prereg = PreRegistration(
            config_hash=content_hash({"scenario": self.name, "cpc": self.cycles_per_condition}),
            data_hash=dataset.content_hash,
            analysis_plan=self.analysis_plan(),
        )
        verdict = Verdict.decide(
            observed=observed,
            threshold=claim.threshold,
            reasoning=(
                f"zero_void_proximity {observed:+.3f} "
                f"(dist(zero,rest)={zero_to_rest:.3f}, dist(zero,void)={zero_to_void:.3f}); "
                f"void-real dist(void,rest)={void_real:.3f}; "
                f"plenum entropy(void)/entropy(rest)={plenum_ratio:.3f}; "
                f"{len(fields)} void/entropy fields"
            ),
        )
        evidence = [
            PillarEvidence(
                pillar="zero_as_void",
                statistic_name="zero_void_proximity",
                statistic_value=observed,
                library="numpy",
                library_version=np.__version__,
                effect_size=observed,
                ci_low=0.0,
                ci_high=0.0,
                p_value=None,
                cross_check="n/a",
                detail={
                    "rung1_void_real_dist": void_real,
                    "rung2_plenum_entropy_ratio": plenum_ratio,
                    "rung3_zero_to_rest": zero_to_rest,
                    "rung3_zero_to_void": zero_to_void,
                    "zero_nearest": min(
                        ("neutral", "numbers", "contradiction"),
                        key=lambda c: d("zero", c),
                    ),
                    "entropy_means": ent_means,
                    "n_void_entropy_fields": len(fields),
                    "fields_used": fields[:40],
                    "cycles_per_condition": self.cycles_per_condition,
                },
            ),
        ]
        record = EmpiricalProofRecord(
            claim=claim,
            preregistration=prereg,
            datasets=[dataset],
            substrate_name=substrate.name,
            substrate_git_commit=substrate.git_commit(),
            evidence=evidence,
            verdict=verdict,
            reproduction=Reproduction(command=self._build_reproduction_command()),
            provenance=self._build_provenance(substrate, dataset).to_prov_json(),
            ophamin_version=__version__,
            ophamin_git_commit=capture_git_commit(_ophamin_project_root()),
        )
        record.sign(sign_key)
        return record
