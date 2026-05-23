"""The Substrate Liveness scenario — DYNAMICAL aliveness, not structural wiring.

Companion to :class:`SubstrateCompletenessScenario`. Completeness measures
*structural* wiring — "is this module imported / reachable?" — and reports a
high number (most modules are import-connected). But a module can be wired and
still **dead**: it runs every cycle and emits the *same constant value*
regardless of the stimulus — a frozen default. The organ is attached but not
pumping.

This scenario measures the other axis: of the numeric signals Kimera actually
emits during real-corpus cycles, how many carry **real dynamics** (vary with
the stimulus) versus **frozen defaults** (one constant value forever). The
owner's "Kimera is ~13% wired" is THIS axis — dynamical liveness — not the
structural ~92%. The two together give the honest picture: structurally wired
vs actually alive.

Falsifiable claim
=================

    At least ``liveness_floor`` (default 80%) of the numeric signals Kimera
    emits across a diverse real corpus carry real dynamics (take >= 2 distinct
    values across cycles) rather than emitting a frozen default.

REFUTED is the working state (same posture as substrate-completeness): a low
liveness rate means most of the emitted signal surface is dead, AND the
operator gets a concrete action list — the **frozen-signal worklist**, grouped
by organ, carried in the proof evidence. As organs are woken (their components
made to genuinely compute + flow), re-running this scenario shows the liveness
rate climb. That is the closed measure -> fix -> re-measure loop for the
"wire everything into Takwin" campaign.

Output
======

A signed ``EmpiricalProofRecord`` whose single ``signal_dynamics`` pillar
carries: liveness_rate + Wilson 95% CI, the live/frozen counts, the always-on
subset breakdown, frozen-by-organ histogram, and the first 200 frozen signal
paths (the awakening worklist).
"""

from __future__ import annotations

import math
from collections import Counter, defaultdict

import statsmodels as _sm  # noqa: F401
from statsmodels.stats.proportion import proportion_confint

from ophamin.measuring.proof import Claim, PillarEvidence, Threshold
from ophamin.measuring.scenarios.base import Scenario, ScenarioScore, Tier
from ophamin.seeing.corpus import CorpusRecord
from ophamin.seeing.substrate.base import CycleResult


def _flatten_numeric(raw: object) -> dict[str, float]:
    """Collect every finite numeric leaf in a CycleResult.raw dict.

    Walks nested dicts to dotted paths. Bools count (0/1 — a flag that never
    flips is a frozen signal, honestly). Lists / strings / None are skipped.
    """
    out: dict[str, float] = {}

    def walk(v: object, path: str) -> None:
        if isinstance(v, dict):
            for k, vv in v.items():
                child = f"{path}.{k}" if path else str(k)
                walk(vv, child)
        elif isinstance(v, bool):
            out[path] = float(v)
        elif isinstance(v, (int, float)):
            fv = float(v)
            if math.isfinite(fv):
                out[path] = fv

    walk(raw, "")
    return out


class SubstrateLivenessScenario(Scenario):
    """Stream a diverse real corpus through a Kimera target and measure what
    fraction of the emitted numeric signal surface actually carries dynamics.

    Uses the base ``run()`` corpus-stream loop; only ``build_claim`` and
    ``score`` are overridden. The frozen-signal worklist in the evidence is the
    concrete "organs to wake" list for the de-isolation campaign.
    """

    name = "substrate-liveness"
    tier = Tier.SCIENTIFIC
    family = "completeness"
    goal = (
        "Measure how much of Kimera's emitted signal surface carries real "
        "dynamics vs frozen defaults — the dynamical-aliveness counterpart "
        "to structural completeness."
    )
    explanation = (
        "Structural completeness (import reachability) reports ~92% wired, "
        "but a wired module can still emit a constant default every cycle — "
        "attached but not pumping. This scenario streams a diverse real "
        "corpus and classifies each numeric signal LIVE (varies with the "
        "stimulus) or FROZEN (constant across cycles). liveness_rate = "
        "n_live / n_numeric_signals. The owner's '~13% wired' is this axis. "
        "REFUTED is the working state: the evidence carries the frozen-signal "
        "worklist (by organ) — the concrete awakening targets. Re-run after "
        "each wake-wave to watch the rate climb."
    )
    method = "liveness_rate"
    falsification_consequence = (
        "Most of Kimera's emitted signals are frozen defaults — the body is "
        "structurally wired but not dynamically alive; the frozen worklist "
        "names the organs to wake."
    )
    runner_path = "examples/run_substrate_liveness.py"

    def __init__(
        self,
        *,
        liveness_floor: float = 0.80,
        corpus_name: str = "flores",
        target: str = "entity",
        n_cycles: int = 64,
    ) -> None:
        if not 0.0 < liveness_floor <= 1.0:
            raise ValueError(
                f"liveness_floor must be in (0, 1], got {liveness_floor}"
            )
        self.liveness_floor = float(liveness_floor)
        self.corpus_name = corpus_name
        self.target = target
        self.n_cycles = int(n_cycles)

    # ----------------------------------------------------------------- claim --

    def build_claim(self) -> Claim:
        return Claim(
            statement=(
                f"At least {self.liveness_floor:.0%} of the always-on numeric "
                "signals Kimera emits (those present in EVERY cycle) carry real "
                "dynamics (vary with the stimulus) rather than emitting a "
                "frozen default constant."
            ),
            operationalization=(
                f"Stream {self.n_cycles} diverse records from the "
                f"'{self.corpus_name}' corpus through the Kimera "
                f"'{self.target}' target; collect every finite numeric leaf in "
                "CycleResult.raw per cycle. Restrict to ALWAYS-ON signals "
                "(present in all cycles → zero sampling doubt); a signal is "
                "LIVE if it takes >= 2 distinct values, FROZEN if constant. "
                "liveness_rate = always_on_live / always_on_total. "
                "Under-sampled signals are excluded (a signal seen in few "
                "cycles is trivially constant — not a frozen default)."
            ),
            threshold=Threshold(
                metric="liveness_rate",
                comparator=">=",
                value=self.liveness_floor,
                units="proportion",
            ),
            h0=(
                f"H0: liveness < {self.liveness_floor:.0%} — most emitted "
                "signals are frozen defaults; the body is structurally wired "
                "but not dynamically alive; the frozen worklist is non-empty"
            ),
            h1=(
                f"H1: liveness >= {self.liveness_floor:.0%} — the emitted "
                "signal surface is dynamically alive"
            ),
        )

    def analysis_plan(self) -> str:
        return (
            f"Stream {self.n_cycles} diverse '{self.corpus_name}' records "
            f"through the Kimera '{self.target}' target; flatten all numeric "
            "leaves in CycleResult.raw per cycle; classify each signal "
            "live (>=2 distinct values) vs frozen (constant). Decide "
            f"liveness_rate against threshold >= {self.liveness_floor:.0%}. "
            "Wilson 95% CI on the proportion. The frozen-signal worklist "
            "(by organ) is in the proof evidence."
        )

    # ----------------------------------------------------------------- score --

    def score(
        self,
        cycle_results: list[CycleResult],
        records: list[CorpusRecord],
    ) -> ScenarioScore:
        succ = [c for c in cycle_results if getattr(c, "success", True)]
        if not succ:
            return ScenarioScore(
                observed_value=0.0,
                inconclusive=True,
                reasoning="no successful cycles — substrate produced no signals",
            )

        n_cyc = len(succ)
        seen: dict[str, list[float]] = defaultdict(list)
        for c in succ:
            for k, v in _flatten_numeric(c.raw).items():
                seen[k].append(v)

        n_raw = len(seen)
        if n_raw == 0:
            return ScenarioScore(
                observed_value=0.0,
                inconclusive=True,
                reasoning="no numeric signals found in CycleResult.raw",
            )

        def varies(vs: list[float]) -> bool:
            return len({round(x, 9) for x in vs}) > 1

        # HEADLINE = always-on liveness: of the signals emitted in EVERY cycle
        # (fully sampled, zero sampling doubt), how many carry real dynamics.
        # A signal that fires in only a few cycles is trivially "constant" —
        # that is under-sampling, not a frozen DEFAULT — so it must not count
        # toward the rate. The always-on spine is the honest, artifact-free set.
        always_on = {k: vs for k, vs in seen.items() if len(vs) == n_cyc}
        if not always_on:
            return ScenarioScore(
                observed_value=0.0,
                inconclusive=True,
                reasoning=(
                    f"no always-on signals across {n_cyc} cycles — cannot "
                    "score liveness without sampling doubt"
                ),
            )
        ao_live = [k for k, vs in always_on.items() if varies(vs)]
        ao_frozen = [k for k, vs in always_on.items() if not varies(vs)]
        n_ao, n_ao_live, n_ao_frozen = len(always_on), len(ao_live), len(ao_frozen)
        liveness = n_ao_live / n_ao

        # Secondary context only (artifact-prone — reported, never the claim):
        # whole-surface and well-sampled (>= half the cycles) rates.
        min_samples = max(4, (n_cyc + 1) // 2)
        scorable = {k: vs for k, vs in seen.items() if len(vs) >= min_samples}
        sc_live = sum(1 for vs in scorable.values() if varies(vs))
        whole_live = sum(1 for vs in seen.values() if varies(vs))

        # Worklist = always-on FROZEN signals (the trustworthy awakening
        # targets: emitted every cycle, never move = genuine dead defaults).
        frozen_by_organ = Counter(
            k.split(".")[0].split("_")[0] for k in ao_frozen
        )

        ci_low, ci_high = proportion_confint(
            count=n_ao_live, nobs=n_ao, alpha=0.05, method="wilson"
        )

        evidence = [
            PillarEvidence(
                pillar="signal_dynamics",
                statistic_name="liveness_rate",
                statistic_value=liveness,
                library="statsmodels",
                library_version=getattr(_sm, "__version__", "unknown"),
                effect_size=None,
                ci_low=float(ci_low),
                ci_high=float(ci_high),
                p_value=None,
                cross_check="n/a",
                detail={
                    "always_on_total": n_ao,
                    "always_on_live": n_ao_live,
                    "always_on_frozen": n_ao_frozen,
                    "n_cycles_scored": n_cyc,
                    "ci_method": "wilson_95%",
                    # secondary context (artifact-prone, not the claim metric)
                    "whole_surface_total": n_raw,
                    "whole_surface_live": whole_live,
                    "whole_surface_liveness_rate": whole_live / n_raw,
                    "scorable_min_samples": min_samples,
                    "scorable_total": len(scorable),
                    "scorable_live": sc_live,
                    "scorable_liveness_rate": (
                        sc_live / len(scorable) if scorable else 0.0
                    ),
                    # the awakening worklist (always-on frozen = genuine defaults)
                    "frozen_by_organ_top": dict(frozen_by_organ.most_common(25)),
                    "frozen_worklist": sorted(ao_frozen),
                    "frozen_worklist_by_organ": {
                        org: sorted(
                            p for p in ao_frozen
                            if p.split(".")[0].split("_")[0] == org
                        )
                        for org in frozen_by_organ
                    },
                },
            ),
        ]

        reasoning = (
            f"always-on liveness {liveness:.4f}: {n_ao_live}/{n_ao} every-cycle "
            f"signals carry real dynamics; {n_ao_frozen} are frozen defaults "
            f"(the worklist); Wilson 95% CI [{ci_low:.4f}, {ci_high:.4f}]. "
            f"Context: whole-surface {whole_live}/{n_raw} "
            f"({whole_live / n_raw:.4f}, deflated by under-sampling); "
            f"{n_cyc} cycles"
        )
        return ScenarioScore(
            observed_value=liveness, evidence=evidence, reasoning=reasoning
        )
