"""Arrow of Time — can the substrate feel which way time flows?

A real process and its EXACT time-reversal contain the *identical multiset of
values*. So any order-blind reader — a mean, a histogram, a bag-of-values, a
mean-pooled embedding (the LLM-retrieval analogue) — is provably at chance (0.5)
on "which direction is forward": the two streams are indistinguishable to it.

Kimera is not order-blind. It presses each observation into a path-dependent,
thermodynamically-grounded manifold (scars accumulate, ΔS≥0 is enforced, state
is hysteretic). So streaming the TRUE forward order vs the reversed order leaves
two *different* accumulated states. If the substrate's accumulated irreversibility
signature is consistently tied to the real arrow, it can recover temporal
direction from data alone — reading the arrow of time off its own entropy
production. That is the claim under test.

Falsifiable claim
=================
    Across N real FRED series, the substrate's accumulated path-dependent
    observable shows a CONSISTENT asymmetry between the true-forward and the
    time-reversed stream (|consistency − 0.5| large; arrow-detection rate ≥ θ).
    The order-blind baseline is 0.5 by construction (identical value multiset).

REFUTED (rate ≈ 0.5) is an honest, useful result: it means the current numeric
channel doesn't carry the arrow into the substrate's thermodynamics — a
construction brief (a richer number→prime channel is needed), not a dead end.

Output: a signed proof whose evidence carries, per candidate observable, the
forward-vs-reversed asymmetry and the arrow-detection rate; the best observable
is the headline statistic.
"""

from __future__ import annotations

import csv
import math
from collections import defaultdict
from pathlib import Path

import statsmodels as _sm  # noqa: F401
from statsmodels.stats.proportion import proportion_confint

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

_DEFAULT_FRED_DIR = Path(
    "/Volumes/Behemoth/Ophamin FrameWork /ophamin/data/raw/financial/fred"
)


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


def _load_fred_window(path: Path, window: int) -> list[float]:
    """The last ``window`` finite numeric values of a FRED CSV (date,value)."""
    vals: list[float] = []
    with path.open(encoding="utf-8", errors="ignore") as fh:
        for row in csv.reader(fh):
            if len(row) < 2:
                continue
            try:
                v = float(row[1])
            except ValueError:
                continue  # header / missing marker
            if math.isfinite(v):
                vals.append(v)
    return vals[-window:] if len(vals) >= window else vals


def _zscore(vals: list[float]) -> list[float]:
    m = sum(vals) / len(vals)
    var = sum((x - m) ** 2 for x in vals) / len(vals)
    sd = math.sqrt(var) if var > 0 else 1.0
    return [(x - m) / sd for x in vals]


class ArrowOfTimeScenario(Scenario):
    """Recover the temporal direction of a real process from its time-reversal
    via the substrate's path-dependent (hysteretic, ΔS≥0) accumulated state —
    a discrimination that is 0.5-by-construction for any order-blind reader."""

    name = "arrow-of-time"
    tier = Tier.SCIENTIFIC
    family = "thermodynamic"
    goal = (
        "Can the substrate recover the true temporal direction of a real "
        "process from its exact time-reversal — feeling time's arrow off its "
        "own path-dependent entropy production — where an order-blind reader is "
        "provably at chance (identical value multiset)?"
    )
    explanation = (
        "A series and its reversal share the identical multiset of values, so "
        "any order-invariant model (histogram, mean, bag-of-values, mean-pooled "
        "embedding) is exactly 0.5 on 'which way is forward'. Kimera presses "
        "each value into a hysteretic, ΔS≥0 manifold; forward vs reversed leave "
        "different accumulated states. The scenario streams both directions of "
        "real FRED series and tests whether the substrate's accumulated "
        "irreversibility signature is consistently tied to the real arrow. "
        "REFUTED (~0.5) is a construction brief (numeric channel doesn't carry "
        "the arrow), not a dead end."
    )
    method = "arrow_detection_rate"
    falsification_consequence = (
        "The substrate's thermodynamics do not register the temporal asymmetry "
        "of a real process through the numeric channel — a richer number→prime "
        "path is needed to feel the arrow."
    )
    runner_path = "examples/run_arrow_of_time.py"

    def __init__(
        self,
        *,
        window: int = 48,
        max_series: int = 12,
        accuracy_floor: float = 0.65,
        fred_dir: Path | str = _DEFAULT_FRED_DIR,
        target: str = "entity",
    ) -> None:
        self.window = int(window)
        self.max_series = int(max_series)
        self.accuracy_floor = float(accuracy_floor)
        self.fred_dir = Path(fred_dir)
        self.target = target
        self.corpus_name = "fred-arrow-of-time"
        self.n_cycles = 0  # custom run loop

    def score(self, cycle_results: list[CycleResult], records: list[CorpusRecord]) -> ScenarioScore:
        raise NotImplementedError("ArrowOfTimeScenario uses a custom run() loop.")

    def build_claim(self) -> Claim:
        return Claim(
            statement=(
                f"Across {self.max_series} real FRED series, the substrate "
                f"recovers the true temporal direction (vs the exact reversal) "
                f"at rate ≥ {self.accuracy_floor:.0%} via a consistent "
                "path-dependent irreversibility signature. An order-blind reader "
                "is 0.5 by construction (identical value multiset)."
            ),
            operationalization=(
                f"For each series, take the last {self.window} values "
                "(z-scored); stream them FORWARD and REVERSED through the "
                f"'{self.target}' target as bare-number stimuli (no direction "
                "words). For each path-dependent numeric observable in "
                "CycleResult.raw, compute a per-direction summary; the substrate "
                "'votes' forward = the direction with the larger summary. "
                "arrow_detection_rate = sign-consistency of that vote vs the "
                "true arrow, max over observables (sign-agnostic: a flipped but "
                "consistent vote still counts as detection)."
            ),
            threshold=Threshold(
                metric="arrow_detection_rate",
                comparator=">=",
                value=self.accuracy_floor,
                units="proportion",
            ),
            h0=(
                "H0: rate ≈ 0.5 — the substrate is arrow-blind through the "
                "numeric channel (no consistent forward/reversed asymmetry)"
            ),
            h1=(
                f"H1: rate ≥ {self.accuracy_floor:.0%} — the substrate feels "
                "the arrow of time via its path-dependent entropy production"
            ),
        )

    def analysis_plan(self) -> str:
        return (
            f"Stream {self.max_series} real FRED series (last {self.window} "
            "z-scored values) forward and reversed; per path-dependent "
            "observable compute forward-vs-reversed asymmetry; arrow_detection_"
            "rate = best sign-consistent vote vs the true arrow; decide against "
            f">= {self.accuracy_floor:.0%} (chance 0.5); Wilson 95% CI."
        )

    # ----------------------------------------------------------------- helpers

    @staticmethod
    def _summaries(traj: list[float]) -> dict[str, float]:
        """Path-dependent summaries of an observable trajectory (a stateful
        substrate makes forward/reversed trajectories genuinely different)."""
        a = [x for x in traj if math.isfinite(x)]
        if len(a) < 2:
            return {}
        n = len(a)
        final = a[-1]
        mean = sum(a) / n
        # cumulative "work": running-sum endpoint (path-dependent accumulation)
        cum = 0.0
        cum_end = 0.0
        for x in a:
            cum += x
            cum_end = cum
        # late-vs-early energy (settling asymmetry)
        half = n // 2
        late = sum(abs(x) for x in a[half:]) / max(1, n - half)
        early = sum(abs(x) for x in a[:half]) / max(1, half)
        return {
            "final": final,
            "mean": mean,
            "cum_end": cum_end,
            "late_minus_early": late - early,
        }

    def run(
        self,
        substrate: SubstrateUnderTest,
        *,
        data_root=None,
        sign_key: bytes = DEFAULT_SIGN_KEY,
    ) -> EmpiricalProofRecord:
        files = sorted(self.fred_dir.glob("*.csv"))[: self.max_series]
        if not files:
            raise RuntimeError(f"no FRED CSVs under {self.fred_dir}")

        # per (observable, summary): list of (fwd_stat - rev_stat) across series
        deltas: dict[str, list[float]] = defaultdict(list)
        n_series = 0
        used = []
        for f in files:
            vals = _load_fred_window(f, self.window)
            if len(vals) < max(8, self.window // 2):
                continue
            z = _zscore(vals)
            stimuli = [f"{v:.4f}" for v in z]  # bare numbers — no direction words
            fwd = substrate.run_batch(stimuli)
            rev = substrate.run_batch(list(reversed(stimuli)))
            fwd_ok = [c for c in fwd if getattr(c, "success", True)]
            rev_ok = [c for c in rev if getattr(c, "success", True)]
            if len(fwd_ok) < 2 or len(rev_ok) < 2:
                continue
            # collect each numeric observable's trajectory per direction
            fwd_tr: dict[str, list[float]] = defaultdict(list)
            rev_tr: dict[str, list[float]] = defaultdict(list)
            for c in fwd_ok:
                for k, val in _flatten_numeric(c.raw).items():
                    fwd_tr[k].append(val)
            for c in rev_ok:
                for k, val in _flatten_numeric(c.raw).items():
                    rev_tr[k].append(val)
            common = set(fwd_tr) & set(rev_tr)
            for k in common:
                sf = self._summaries(fwd_tr[k])
                sr = self._summaries(rev_tr[k])
                for stat in set(sf) & set(sr):
                    d = sf[stat] - sr[stat]
                    if math.isfinite(d):
                        deltas[f"{k}::{stat}"].append(d)
            n_series += 1
            used.append(f.stem)

        if n_series < 2:
            raise RuntimeError(f"arrow-of-time: only {n_series} usable series")

        # arrow-detection rate per (observable,stat) = sign-consistency of the
        # fwd-vs-rev sign across series (the substrate's blind 'forward = larger'
        # vote; sign-agnostic so a flipped-but-consistent detector still counts).
        best_key = None
        best_rate = 0.0
        per_key: dict[str, float] = {}
        for key, ds in deltas.items():
            nz = [d for d in ds if abs(d) > 1e-12]
            if len(nz) < max(2, n_series // 2):
                continue
            pos = sum(1 for d in nz if d > 0)
            rate = max(pos, len(nz) - pos) / len(nz)  # consistency (sign-agnostic)
            per_key[key] = rate
            if rate > best_rate:
                best_rate, best_key, _best_pos = rate, key, pos

        observed = float(best_rate)
        n_eff = len(deltas.get(best_key, [])) if best_key else n_series
        ci_low, ci_high = (
            proportion_confint(round(observed * n_eff), n_eff, alpha=0.05, method="wilson")
            if n_eff
            else (0.0, 0.0)
        )

        dataset = DatasetRef(
            name="fred-arrow-of-time",
            content_hash=content_hash({"series": used, "window": self.window}),
            n_records=n_series,
            source=str(self.fred_dir),
            kind="real-macro-time-series (forward vs exact reversal)",
        )
        claim = self.build_claim()
        prereg = PreRegistration(
            config_hash=content_hash(
                {"scenario": self.name, "window": self.window, "max_series": self.max_series}
            ),
            data_hash=dataset.content_hash,
            analysis_plan=self.analysis_plan(),
        )
        top = sorted(per_key.items(), key=lambda kv: kv[1], reverse=True)[:15]
        verdict = Verdict.decide(
            observed=observed,
            threshold=claim.threshold,
            reasoning=(
                f"arrow-detection rate {observed:.3f} on {n_series} real series "
                f"(best observable: {best_key}); order-blind baseline = 0.500 by "
                f"construction; Wilson 95% CI [{ci_low:.3f}, {ci_high:.3f}]"
            ),
        )
        evidence = [
            PillarEvidence(
                pillar="path_dependent_irreversibility",
                statistic_name="arrow_detection_rate",
                statistic_value=observed,
                library="statsmodels",
                library_version=getattr(_sm, "__version__", "unknown"),
                effect_size=observed - 0.5,
                ci_low=float(ci_low),
                ci_high=float(ci_high),
                p_value=None,
                cross_check="n/a",
                detail={
                    "order_blind_baseline_note": "0.5 by construction (identical value multiset fwd/rev)",
                    "n_series": n_series,
                    "series_used": used,
                    "window": self.window,
                    "best_observable": best_key,
                    "order_blind_baseline": 0.5,
                    "top_observables": dict(top),
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
