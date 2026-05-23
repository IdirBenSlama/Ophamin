"""Substrate Liveness BATTERY — honest liveness across a diverse stimulus battery.

`SubstrateLivenessScenario` measures liveness on ONE corpus, which over-counts
"dead": many signals are frozen on benign text only because that corpus never
exercises their real trigger (audio/visual arms need modality input; thermo
echoform/insight/anomaly accounting needs failure/insight/anomaly events). Those
organs are *correctly conditional*, not dead.

This scenario streams MULTIPLE maximally-different corpora (multilingual /
financial-numeric / source-code / adversarial-security) and computes liveness on
the COMBINED, value-level union: a signal is LIVE if it takes >= 2 distinct
values across the *whole battery*, FROZEN only if constant across every corpus.
A signal frozen across all of them is a **genuine dead wire** (the trustworthy
worklist); a signal that was frozen on flores but varies under another corpus is
*conditional* — exonerated, not dead.

Reuses `SubstrateLivenessScenario.score` (the always-on union classifier) on the
combined cycle stream; only the run() loop (multi-corpus) and the claim differ.
"""

from __future__ import annotations

import itertools
from pathlib import Path

from ophamin import __version__
from ophamin.comparing.provenance.lineage import (
    _ophamin_project_root,
    capture_git_commit,
)
from ophamin.measuring.proof import (
    Claim,
    EmpiricalProofRecord,
    PreRegistration,
    Reproduction,
    Threshold,
    Verdict,
    content_hash,
)
from ophamin.measuring.scenarios.base import DEFAULT_SIGN_KEY, Tier
from ophamin.measuring.scenarios.substrate_liveness import SubstrateLivenessScenario
from ophamin.seeing.corpus import get_corpus
from ophamin.seeing.substrate.base import SubstrateUnderTest


class SubstrateLivenessBatteryScenario(SubstrateLivenessScenario):
    """Multi-corpus liveness: separates genuine dead wires from merely-unexercised
    conditional organs by exercising many different stimulus types."""

    name = "substrate-liveness-battery"
    tier = Tier.SCIENTIFIC
    family = "completeness"
    goal = (
        "Measure liveness across a DIVERSE stimulus battery so signals frozen "
        "only for lack of their trigger (conditional organs) are separated from "
        "genuine dead wires (frozen across every corpus)."
    )
    explanation = (
        "Single-corpus liveness over-counts dead: a signal frozen on benign "
        "text may simply be a correctly-conditional organ the corpus never "
        "exercises. This battery streams multilingual + financial + code + "
        "adversarial corpora and classifies on the value-level union — frozen "
        "across ALL of them = genuine dead wire (the trustworthy B1 worklist); "
        "varies under any = conditional, exonerated. Reuses the always-on "
        "classifier from substrate-liveness on the combined stream."
    )
    method = "liveness_rate_union"
    falsification_consequence = (
        "Signals frozen across every diverse corpus are genuine dead wires — "
        "computed-but-never-synced infrastructure; the worklist names them."
    )
    runner_path = "examples/run_substrate_liveness_battery.py"

    def __init__(
        self,
        *,
        liveness_floor: float = 0.80,
        corpus_names: tuple[str, ...] = ("flores", "financial", "linux", "cyber"),
        target: str = "entity",
        per_corpus_cycles: int = 40,
    ) -> None:
        if not 0.0 < liveness_floor <= 1.0:
            raise ValueError(f"liveness_floor must be in (0, 1], got {liveness_floor}")
        if not corpus_names:
            raise ValueError("corpus_names must be non-empty")
        self.liveness_floor = float(liveness_floor)
        self.corpus_names = tuple(corpus_names)
        self.target = target
        self.per_corpus_cycles = int(per_corpus_cycles)
        # metadata: total cycles across the battery
        self.corpus_name = "+".join(self.corpus_names)
        self.n_cycles = self.per_corpus_cycles * len(self.corpus_names)

    def build_claim(self) -> Claim:
        return Claim(
            statement=(
                f"At least {self.liveness_floor:.0%} of Kimera's always-on "
                "numeric signals carry real dynamics across a DIVERSE stimulus "
                "battery (a signal frozen across every corpus — multilingual, "
                "financial, code, adversarial — is a genuine dead wire, not "
                "merely an unexercised conditional organ)."
            ),
            operationalization=(
                f"Stream {self.per_corpus_cycles} records from each of "
                f"{list(self.corpus_names)} through the '{self.target}' target; "
                "combine all cycles; of signals present in EVERY cycle, the "
                "fraction taking >= 2 distinct values across the WHOLE battery. "
                "liveness_rate_union = always_on_live / always_on_total."
            ),
            threshold=Threshold(
                metric="liveness_rate_union",
                comparator=">=",
                value=self.liveness_floor,
                units="proportion",
            ),
            h0=(
                f"H0: union liveness < {self.liveness_floor:.0%} — genuine dead "
                "wires remain (frozen even under their own trigger); worklist non-empty"
            ),
            h1=(
                f"H1: union liveness >= {self.liveness_floor:.0%} — the always-on "
                "surface is dynamically alive under diverse stimuli"
            ),
        )

    def analysis_plan(self) -> str:
        return (
            f"Stream {self.per_corpus_cycles} records from each of "
            f"{list(self.corpus_names)} through Kimera '{self.target}'; combine "
            "all cycle results; classify each always-on numeric signal live "
            "(>=2 distinct values across the whole battery) vs frozen. Decide "
            f"union liveness against >= {self.liveness_floor:.0%}; Wilson 95% CI. "
            "Genuine dead-wire worklist (frozen across all corpora) in evidence."
        )

    def run(
        self,
        substrate: SubstrateUnderTest,
        *,
        data_root: str | Path | None = None,
        sign_key: bytes = DEFAULT_SIGN_KEY,
    ) -> EmpiricalProofRecord:
        """Stream each corpus through the substrate; score the combined union."""
        all_records = []
        all_cycles = []
        datasets = []
        for cname in self.corpus_names:
            corpus = get_corpus(cname, data_root)
            corpus.require_available()
            recs = list(itertools.islice(corpus.records(), self.per_corpus_cycles))
            if not recs:
                raise RuntimeError(f"battery: corpus '{cname}' yielded no records")
            all_records.extend(recs)
            datasets.append(corpus.dataset_ref())
            all_cycles.extend(substrate.run_batch([r.text for r in recs]))

        claim = self.build_claim()
        self._enforce_field_contract(all_cycles)
        score = self.score(all_cycles, all_records)
        verdict = Verdict.decide(
            score.observed_value,
            claim.threshold,
            inconclusive=score.inconclusive,
            reasoning=score.reasoning,
        )

        config = {
            "scenario": self.name,
            "corpora": list(self.corpus_names),
            "target": self.target,
            "per_corpus_cycles": self.per_corpus_cycles,
            "n_records": len(all_records),
        }
        prereg = PreRegistration(
            config_hash=content_hash(config),
            data_hash=content_hash([d.content_hash for d in datasets]),
            analysis_plan=self.analysis_plan(),
        )
        record = EmpiricalProofRecord(
            claim=claim,
            preregistration=prereg,
            datasets=datasets,
            substrate_name=substrate.name,
            substrate_git_commit=substrate.git_commit(),
            evidence=score.evidence,
            verdict=verdict,
            reproduction=Reproduction(command=self._build_reproduction_command()),
            provenance=self._build_provenance(substrate, datasets[0]).to_prov_json(),
            ophamin_version=__version__,
            ophamin_git_commit=capture_git_commit(_ophamin_project_root()),
        )
        record.sign(sign_key)
        return record
