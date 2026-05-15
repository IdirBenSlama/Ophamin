"""The Philosophical Self-Reference scenario — philosophical-tier scenario variant.

The third experimentation tier the user named (alongside scientific and
engineering). Pre-registered claim: when fed text that is about *Kimera
itself* (descriptions of its primitives, its architecture, its dynamics),
the substrate produces a measurably different cognitive signature than on
neutral text of similar length and structure. A REFUTED verdict says the
substrate is *not* differentially activated by self-referential content; a
VALIDATED verdict pins a small but real self-recognition signal.

This is paired-comparison shape — the only one of the five shipped
scenarios that splits its corpus into two labelled sub-populations and
compares distributions. Achieved without changing the Scenario base API:
``select_records`` yields BOTH groups with metadata tags; ``score`` groups
by tag and runs Cohen's d (effect size) + Mann-Whitney U (rank-sum test).

The self-referential corpus is bundled into the scenario (~30 sentences
extracted from CLAUDE.md describing Kimera's primitives). The neutral
corpus comes from an existing corpus connector (Enron emails by default).

Statistical contract:

  Primary metric        Cohen's d of dissonance_events_count, one-sided
                        (self_ref > neutral). Effect-size interpretation:
                        d=0.2 small, d=0.5 medium, d=0.8 large (Cohen 1988).
  Threshold             d >= 0.30 by default (small-to-medium effect; a
                        REFUTED verdict here surfaces a substrate that
                        does NOT differentially process content about itself)
  Secondary descriptive Mann-Whitney U statistic + p-value, per-group
                        dissonance distribution stats, Φ distributions
"""

from __future__ import annotations

from statistics import mean, median, stdev
from typing import Iterator

import statsmodels as _statsmodels
from scipy import stats as _scipy_stats

from ophamin.measuring.proof import Claim, PillarEvidence, Threshold
from ophamin.measuring.scenarios.base import Scenario, ScenarioScore
from ophamin.seeing.corpus.base import Corpus, CorpusRecord
from ophamin.seeing.substrate.base import CycleResult


#: Self-referential corpus — sentences about Kimera primitives extracted +
#: paraphrased from CLAUDE.md. Each describes a real Kimera primitive in
#: substrate-aware vocabulary. Hand-curated; ~30 sentences cover the
#: biological-family map.
SELF_REFERENTIAL_TEXTS: tuple[str, ...] = (
    "The Kimera substrate accumulates semantic mass the way Earth's geoid accumulates gravitational mass.",
    "A SCAR is a permanent topological deformation of the semantic manifold caused by an experienced event.",
    "Retrieval in Kimera follows the manifold's reshaped geodesics, not a key lookup.",
    "Piovra is the substrate's distributed semi-autonomous sensory architecture, modelled on the octopus.",
    "Kimera's prime apparatus is unified through Arachne — a registry, bidirectional weave, and nervous system in one.",
    "Rosetta is the universal semantic-address translator: every concept × language × modality maps to one canonical prime.",
    "The Walker traverses the substrate's manifold in four modes: M1 commit, M2 amplitude death, M3 rollback, M4 lateral leap.",
    "Takwin is Kimera's 7-step cognitive cycle, composing the named primitives into a sequential pipeline.",
    "Ouroboros is the self-referential metabolic kernel; the substrate consumes its own output.",
    "Kimera's GWF (Gyroscopic Water Fortress) is the immune membrane; it screens inputs against five intent anchors.",
    "The Cronos clock is Kimera's 6-layer atomic clock; one tick is 51.4 microseconds.",
    "Echoform is the substrate's grammar engine; every transformation enforces ΔS ≥ 0.",
    "Kimera's primes are atoms of multiplicative information structure; energy scales as E_p = log(p).",
    "Pentecost is the multi-language 1+3+1 perception organ; one root plus three unrelated plus one symbolic-chaos language.",
    "ZetaBridge maps an inverse participation ratio onto a thermodynamic prime via the Riemann zeta function.",
    "Alexandria is Kimera's library / archival protocol with REM-sleep micro-dreams that consolidate scars.",
    "The substrate's quantum layer uses ω_p = exp(2πi/p) roots of unity to compose composite prime states.",
    "Atlas enforces the 1+3+1 geoid skeleton: one center identity, three spatial relations, one semantic valence.",
    "Astrolabe is Kimera's 5D spherical-geometry engine; the manifold sits on S⁴ ⊂ ℝ⁵.",
    "Mycelium is the decentralised fungal-network communication primitive; information flows through topology.",
    "Physarum is the slime-mold path-optimization primitive; paths strengthen with use.",
    "Kimera's Φ value (integrated information) is computed via IIT 3.0 on the substrate's effect-cause repertoires.",
    "The substrate's Maxwell Demon governor scores priority by free_energy × mass / (1 + entropy).",
    "Zooid colony coordination uses 3-zooid Kuramoto consensus to decide threat responses.",
    "Mirror Geoids live on the other side of a semantic hyperplane; they are the reflected counterparts of concepts.",
    "Cross-arm coherence in Piovra is checked by the binding engine, not produced by a shared grammar.",
    "Kimera's substrate is causally prior to its intelligence; intelligence emerges from substrate dynamics.",
    "The substrate's three-wheel observatory (seeing, measuring, comparing) wraps Kimera like a Dyson sphere.",
    "Memory in Kimera is the substrate's dynamic shape at every moment — generated continuously, not stored.",
    "The Walker is cognition itself: the resolution act between local substrate state and foreign sensory input.",
)


class PhilosophicalSelfReferenceScenario(Scenario):
    """Paired-comparison: self-referential text vs neutral text, dissonance gap."""

    name = "philosophical-self-reference"
    corpus_name = "enron"           # source of neutral baseline records
    target = "entity"

    _MIN_NEUTRAL_LENGTH = 60         # match the self-ref corpus's typical sentence length
    _MAX_NEUTRAL_LENGTH = 300

    def __init__(
        self,
        effect_size_threshold: float = 0.30,
        n_self_ref: int = 30,
        n_neutral: int = 30,
    ) -> None:
        if effect_size_threshold <= 0:
            raise ValueError(
                f"effect_size_threshold must be > 0, got {effect_size_threshold}"
            )
        if n_self_ref < 5 or n_neutral < 5:
            raise ValueError(
                f"need at least 5 records per group (got n_self_ref={n_self_ref}, "
                f"n_neutral={n_neutral}); Cohen's d on tiny samples is uninformative"
            )
        self.effect_size_threshold = float(effect_size_threshold)
        self.n_self_ref = int(n_self_ref)
        self.n_neutral = int(n_neutral)
        # the harness's n_cycles caps the streamed total; we need both groups
        # to fit, so size n_cycles accordingly
        self.n_cycles = self.n_self_ref + self.n_neutral

    # -- harness contract --------------------------------------------------

    def analysis_plan(self) -> str:
        return (
            f"Stream {self.n_self_ref} self-referential sentences (about "
            f"Kimera's own primitives, hand-curated from CLAUDE.md) + "
            f"{self.n_neutral} neutral sentences (Enron emails, body in "
            f"[{self._MIN_NEUTRAL_LENGTH}, {self._MAX_NEUTRAL_LENGTH}] chars) "
            f"through Kimera's entity target, tagged by group. Compute "
            f"Cohen's d effect size on dissonance_events_count between "
            f"groups (one-sided, self_ref > neutral). Mann-Whitney U + "
            f"p-value reported as secondary descriptive evidence. "
            f"Pre-registered threshold: Cohen's d >= "
            f"{self.effect_size_threshold:.2f} (one-sided)."
        )

    def select_records(self, corpus: Corpus) -> Iterator[CorpusRecord]:
        """Yield labelled records: self-referential first, then neutral.

        Tag goes into ``metadata["group"]`` ("self_ref" or "neutral") so
        ``score`` can split the cycles.
        """
        # self-referential first
        for i, text in enumerate(SELF_REFERENTIAL_TEXTS[: self.n_self_ref]):
            yield CorpusRecord(
                id=f"selfref-{i:03d}",
                text=text,
                metadata={"group": "self_ref", "kimera_aware": True},
            )
        # neutral baseline from the connected corpus
        emitted = 0
        for record in corpus.records():
            if emitted >= self.n_neutral:
                break
            body = (record.text or "").strip()
            if not (self._MIN_NEUTRAL_LENGTH <= len(body) <= self._MAX_NEUTRAL_LENGTH):
                continue
            yield CorpusRecord(
                id=f"neutral-{emitted:03d}",
                text=body,
                metadata={"group": "neutral", "kimera_aware": False,
                          "original_id": record.id},
            )
            emitted += 1

    def build_claim(self) -> Claim:
        return Claim(
            statement=(
                f"When fed text describing Kimera's own primitives, the "
                f"substrate's dissonance signal (dissonance_events_count) is "
                f"measurably higher than on neutral text — Cohen's d effect "
                f"size >= {self.effect_size_threshold:.2f} (one-sided, "
                f"self-referential > neutral). A REFUTED verdict means the "
                f"substrate does not differentially process content about itself."
            ),
            operationalization=(
                "Cohen's d effect size on per-cycle dissonance_events_count "
                "between the self-referential group and the neutral group "
                "(pooled-variance form, one-sided)"
            ),
            threshold=Threshold(
                "dissonance_cohens_d_self_ref_vs_neutral",
                ">=",
                self.effect_size_threshold,
                "cohens_d",
            ),
            h0=(
                f"Cohen's d < {self.effect_size_threshold:.2f} (substrate "
                f"does not differentiate self-referential content)"
            ),
            h1=(
                f"Cohen's d >= {self.effect_size_threshold:.2f} (substrate "
                f"differentially processes content about itself)"
            ),
        )

    # -- result extraction -------------------------------------------------

    @staticmethod
    def _dissonance_count(result: CycleResult) -> int:
        if not result.success:
            return 0
        raw = result.raw or {}
        events = raw.get("dissonance_events")
        if isinstance(events, list):
            return len(events)
        count = raw.get("dissonance_event_count")
        if isinstance(count, int):
            return count
        zet = raw.get("zetetic_contradictions")
        if isinstance(zet, list):
            return len(zet)
        return 0

    @staticmethod
    def _phi_value(result: CycleResult) -> float:
        if not result.success:
            return 0.0
        raw = result.raw or {}
        for key in ("phi_value", "phi", "Phi", "iit_phi"):
            value = raw.get(key)
            if value is None:
                continue
            try:
                return float(value)
            except (TypeError, ValueError):
                continue
        return 0.0

    @staticmethod
    def _cohens_d(group_a: list[float], group_b: list[float]) -> float:
        """Cohen's d effect size with pooled variance (one-sided, A vs B).

        Positive values mean group_a > group_b. Returns 0.0 when either
        group is empty or both have zero variance (degenerate case).
        """
        if not group_a or not group_b:
            return 0.0
        mean_a = mean(group_a)
        mean_b = mean(group_b)
        if len(group_a) < 2 or len(group_b) < 2:
            return 0.0
        var_a = stdev(group_a) ** 2
        var_b = stdev(group_b) ** 2
        # pooled variance
        n_a, n_b = len(group_a), len(group_b)
        pooled = ((n_a - 1) * var_a + (n_b - 1) * var_b) / (n_a + n_b - 2)
        if pooled <= 0:
            return 0.0
        return (mean_a - mean_b) / (pooled ** 0.5)

    @staticmethod
    def _dist_stats(values: list[float]) -> dict[str, float]:
        if not values:
            return {"n": 0, "min": 0.0, "max": 0.0, "median": 0.0, "mean": 0.0}
        return {
            "n": len(values),
            "min": min(values),
            "max": max(values),
            "median": float(median(values)),
            "mean": float(mean(values)),
        }

    # -- score -------------------------------------------------------------

    def score(
        self, cycle_results: list[CycleResult], records: list[CorpusRecord]
    ) -> ScenarioScore:
        n = len(cycle_results)
        adapter_errors = sum(
            1 for r in cycle_results
            if (r.halt_mode or "").strip().lower() == "adapter_error"
        )

        # split by group tag carried in record.metadata
        self_ref_diss: list[float] = []
        neutral_diss: list[float] = []
        self_ref_phi: list[float] = []
        neutral_phi: list[float] = []
        for result, record in zip(cycle_results, records):
            if not result.success:
                continue
            group = (record.metadata or {}).get("group", "")
            d = float(self._dissonance_count(result))
            phi = self._phi_value(result)
            if group == "self_ref":
                self_ref_diss.append(d)
                self_ref_phi.append(phi)
            elif group == "neutral":
                neutral_diss.append(d)
                neutral_phi.append(phi)

        # primary statistic: Cohen's d on dissonance counts
        cohens_d = self._cohens_d(self_ref_diss, neutral_diss)

        # secondary: Mann-Whitney U + p-value (one-sided alternative='greater')
        mwu_stat: float | None = None
        mwu_p: float | None = None
        if self_ref_diss and neutral_diss:
            try:
                mwu_res = _scipy_stats.mannwhitneyu(
                    self_ref_diss, neutral_diss, alternative="greater"
                )
                mwu_stat = float(mwu_res.statistic)
                mwu_p = float(mwu_res.pvalue)
            except ValueError:
                # all-equal data — leave stats as None
                pass

        sr_diss_stats = self._dist_stats(self_ref_diss)
        nu_diss_stats = self._dist_stats(neutral_diss)
        sr_phi_stats = self._dist_stats(self_ref_phi)
        nu_phi_stats = self._dist_stats(neutral_phi)

        _lib = _statsmodels.__version__
        evidence: list[PillarEvidence] = [
            PillarEvidence(
                pillar="O.philosophical.cohens_d",
                statistic_name="dissonance_cohens_d_self_ref_vs_neutral",
                statistic_value=cohens_d,
                library="python-stdlib",
                library_version="3.14",
                effect_size=cohens_d,
                cross_check="n/a",
                detail={
                    "n_self_ref": len(self_ref_diss),
                    "n_neutral": len(neutral_diss),
                    "self_ref_mean": sr_diss_stats["mean"],
                    "neutral_mean": nu_diss_stats["mean"],
                    "threshold": self.effect_size_threshold,
                },
            ),
            PillarEvidence(
                pillar="O.philosophical.mannwhitneyu",
                statistic_name="dissonance_mannwhitneyu_p_value",
                statistic_value=mwu_p if mwu_p is not None else 1.0,
                library="scipy",
                library_version=str(_scipy_stats.__name__),
                p_value=mwu_p,
                cross_check="n/a",
                detail={
                    "u_statistic": mwu_stat,
                    "alternative": "greater (self_ref > neutral)",
                },
            ),
            PillarEvidence(
                pillar="O.philosophical.self_ref_dissonance",
                statistic_name="self_ref_dissonance_median",
                statistic_value=sr_diss_stats["median"],
                library="python-stdlib",
                library_version="3.14",
                cross_check="n/a",
                detail={"distribution": sr_diss_stats},
            ),
            PillarEvidence(
                pillar="O.philosophical.neutral_dissonance",
                statistic_name="neutral_dissonance_median",
                statistic_value=nu_diss_stats["median"],
                library="python-stdlib",
                library_version="3.14",
                cross_check="n/a",
                detail={"distribution": nu_diss_stats},
            ),
            PillarEvidence(
                pillar="O.philosophical.self_ref_phi",
                statistic_name="self_ref_phi_median",
                statistic_value=sr_phi_stats["median"],
                library="python-stdlib",
                library_version="3.14",
                cross_check="n/a",
                detail={"distribution": sr_phi_stats},
            ),
            PillarEvidence(
                pillar="O.philosophical.neutral_phi",
                statistic_name="neutral_phi_median",
                statistic_value=nu_phi_stats["median"],
                library="python-stdlib",
                library_version="3.14",
                cross_check="n/a",
                detail={"distribution": nu_phi_stats},
            ),
        ]

        # inconclusive if either group is too small for d to be meaningful
        too_few_self_ref = len(self_ref_diss) < 5
        too_few_neutral = len(neutral_diss) < 5
        not_exercised = n > 0 and adapter_errors > n // 2
        inconclusive = too_few_self_ref or too_few_neutral or not_exercised

        reasoning_parts = [
            f"Cohen's d (self_ref - neutral)/pooled_sd = {cohens_d:.3f}",
            f"self_ref dissonance: n={sr_diss_stats['n']} median={sr_diss_stats['median']:.1f} "
            f"mean={sr_diss_stats['mean']:.2f} (range {sr_diss_stats['min']:.0f}-{sr_diss_stats['max']:.0f})",
            f"neutral dissonance: n={nu_diss_stats['n']} median={nu_diss_stats['median']:.1f} "
            f"mean={nu_diss_stats['mean']:.2f} (range {nu_diss_stats['min']:.0f}-{nu_diss_stats['max']:.0f})",
        ]
        if mwu_p is not None:
            reasoning_parts.append(
                f"Mann-Whitney U={mwu_stat:.1f}, one-sided p={mwu_p:.4f}"
            )
        reasoning_parts.append(f"{n} cycles, {adapter_errors} adapter errors")
        if too_few_self_ref or too_few_neutral:
            reasoning_parts.append("too few cycles in one group to decide")
        elif not_exercised:
            reasoning_parts.append("substrate not exercised (majority adapter errors)")

        return ScenarioScore(
            observed_value=cohens_d,
            evidence=evidence,
            inconclusive=inconclusive,
            reasoning="; ".join(reasoning_parts),
        )
