"""The Substrate Completeness scenario — empirical wired-vs-scaffolded feedback.

Different from cognitive-tier scenarios: this one does not run any Kimera
cycle. It probes the *static structure* of the repo against an empirical
import graph + annotation scan, and aggregates per-stratum into a
falsifiable claim about the orphan rate.

This is the load-bearing scenario for the user's stated v0.2 goal:

> the purpose itself of Ophamin in my usecase is to have empirical values
> feedbacks to continue developing and "fixing" Kimera at all level of the
> stack — owner, 2026-05-15

Falsifiable claim
=================

> The aggregate orphan rate across all 9 KimeraInventory strata is ≤ 20% —
> i.e., at least 80% of inventoried surfaces are either ``wired`` (≥ 1
> incoming import or annotated ``WIRED``), explicitly ``WIRE_CANDIDATE``
> (scaffolding the operator already knows about), or ``archived``
> (path-pattern recognised as retired).

The 20% slack is the starting threshold. As Kimera matures, the threshold
should ratchet down — measured drift per commit is the next-level signal.

REFUTED here is the working state — orphan rate above the threshold means
load-bearing infrastructure is sitting unwired, AND the operator gets a
concrete action list (the per-surface orphan files in the evidence).

Output
======

A signed ``EmpiricalProofRecord`` whose evidence carries:

  * per-stratum wired_rate / orphan_rate / wire_candidate_rate
  * the full orphan surfaces list (first 100; ancillary)
  * the full WIRE_CANDIDATE surfaces list (first 100; ancillary)
  * the underlying ``CompletenessReport`` ID for full per-surface lookup

The per-surface ``CompletenessReport`` is also written next to the proof
record so the operator can navigate the action list directly.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import statsmodels as _sm  # noqa: F401
from statsmodels.stats.proportion import proportion_confint

from ophamin.measuring.scenarios.base import Tier

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
from ophamin.seeing.discovery import discover_all
from ophamin.seeing.substrate.base import CycleResult, SubstrateUnderTest
from ophamin.seeing.discovery.kimera_inventory import _capture_kimera_commit
from ophamin.seeing.wiring import CompletenessReport, WiringProbe


class SubstrateCompletenessScenario(Scenario):
    """Static-analysis scenario over Kimera's entire observable surface.

    Per-stratum classifies every inventoried surface as wired /
    wire_candidate / orphan / archived / parse_error and emits a
    falsifiable claim about the aggregate orphan rate. The proof-record
    evidence carries the full orphan list — this is the *action list* the
    operator uses to drive substrate-completion work.

    Construct with the Kimera repo path; call ``run()`` to get a signed
    ``EmpiricalProofRecord``. Optional ``out_dir`` writes the underlying
    ``CompletenessReport`` JSON alongside.
    """

    name = "substrate-completeness"
    tier = Tier.SCIENTIFIC
    family = "completeness"
    goal = (
        "Measure Kimera's aggregate orphan rate across all 9 "
        "inventory strata — empirical feedback for substrate "
        "completion."
    )
    explanation = (
        "Per owner directive, Ophamin's load-bearing value is "
        "empirical feedback to drive Kimera substrate completion. "
        "This scenario probes Kimera's static structure (no cycle "
        "runs): an import-graph walk + WIRED/WIRE_CANDIDATE/ARCHIVED "
        "annotation scan classifies every inventoried surface as "
        "wired / wire_candidate / orphan / archived. The threshold "
        "(default 20%) is the starting bar; ratchets down as Kimera "
        "matures. The output evidence carries the orphan + "
        "WIRE_CANDIDATE action lists for direct operator pickup."
    )
    method = "aggregate_orphan_rate"
    falsification_consequence = (
        "Load-bearing infrastructure is sitting unwired across more "
        "than 20% of inventoried surfaces — the operator's "
        "completion-action list is the concrete output."
    )
    target = "all_strata_static_probe"

    def __init__(
        self,
        kimera_repo: Path | str,
        *,
        orphan_rate_ceiling: float = 0.20,
        out_dir: Path | str | None = None,
    ) -> None:
        self.kimera_repo = Path(kimera_repo).expanduser().resolve()
        if not self.kimera_repo.is_dir():
            raise FileNotFoundError(f"Kimera repo not a directory: {self.kimera_repo}")
        if not 0.0 < orphan_rate_ceiling <= 1.0:
            raise ValueError(
                f"orphan_rate_ceiling must be in (0, 1], got {orphan_rate_ceiling}"
            )
        self.orphan_rate_ceiling = float(orphan_rate_ceiling)
        self.out_dir = Path(out_dir).expanduser().resolve() if out_dir else None
        self.n_cycles = 0   # static scenario — base.run() is overridden
        # ``last_report`` is set by run() so the CLI can write the underlying
        # CompletenessReport to disk alongside the proof record.
        self.last_report: CompletenessReport | None = None

    def score(
        self,
        cycle_results: list[CycleResult],
        records: list[CorpusRecord],
    ) -> ScenarioScore:
        """Never called — base.run() is overridden."""
        raise NotImplementedError(
            "SubstrateCompletenessScenario uses a custom run() loop; "
            "score() is unreachable."
        )

    # ----------------------------------------------------------------- claim --

    def build_claim(self) -> Claim:
        return Claim(
            statement=(
                "Across all 9 KimeraInventory strata, the aggregate orphan "
                f"rate is ≤ {self.orphan_rate_ceiling:.1%}. An orphan is a "
                "Python module in the inventory that has zero incoming "
                "imports from any other file in the Kimera repo AND is not "
                "explicitly annotated as WIRE_CANDIDATE / WIRED / ARCHIVED."
            ),
            operationalization=(
                "Build an import graph by walking every .py file under "
                "kimera_swm/ and parsing ``import`` / ``from ... import`` "
                "statements. For each inventoried surface, count incoming "
                "edges. Combine with annotation scanning (``.. note:: "
                "WIRE_CANDIDATE`` etc.) to produce one of {wired, "
                "wire_candidate, orphan, archived, parse_error, config}. "
                "orphan_rate = n_orphan / n_total_python_surfaces."
            ),
            threshold=Threshold(
                metric="aggregate_orphan_rate",
                comparator="<=",
                value=self.orphan_rate_ceiling,
                units="proportion",
            ),
            h0=(
                f"H0: orphan rate > {self.orphan_rate_ceiling:.1%} — load-bearing "
                "infrastructure is sitting unwired; fix list is non-empty"
            ),
            h1=(
                f"H1: orphan rate ≤ {self.orphan_rate_ceiling:.1%} — "
                "substrate completeness within target band"
            ),
        )

    def analysis_plan(self) -> str:
        return (
            f"Run KimeraInventory.discover_all against {self.kimera_repo}, "
            f"then build a repo-wide import graph and classify each surface "
            f"per the operationalization. Aggregate orphan_rate across all "
            f"strata; decide against threshold ≤ {self.orphan_rate_ceiling:.2%}. "
            f"Wilson 95% CI on the proportion. Per-stratum breakdown and the "
            f"orphan / WIRE_CANDIDATE action lists are in the proof evidence."
        )

    # ------------------------------------------------------------------ run --

    def run(
        self,
        substrate: SubstrateUnderTest | None = None,
        *,
        data_root: str | Path | None = None,
        sign_key: bytes = DEFAULT_SIGN_KEY,
    ) -> EmpiricalProofRecord:
        """Build inventory + completeness report, aggregate, emit signed record."""
        inventory = discover_all(self.kimera_repo)
        probe = WiringProbe(self.kimera_repo)
        report = probe.probe(inventory)
        self.last_report = report

        if self.out_dir:
            self.out_dir.mkdir(parents=True, exist_ok=True)
            short = report.report_id[:16]
            (self.out_dir / f"wiring_{short}.json").write_text(
                report.to_json(), encoding="utf-8"
            )
            (self.out_dir / f"wiring_{short}.md").write_text(
                report.to_markdown(), encoding="utf-8"
            )

        # Aggregate orphan rate across all strata (Python surfaces only).
        n_python_total = sum(s.n_total for s in report.per_stratum)
        n_orphan_total = sum(s.n_orphan for s in report.per_stratum)
        observed = (n_orphan_total / n_python_total) if n_python_total else 0.0

        # Wilson 95% CI for the orphan proportion.
        if n_python_total:
            ci_low, ci_high = proportion_confint(
                count=n_orphan_total, nobs=n_python_total,
                alpha=0.05, method="wilson",
            )
        else:
            ci_low = ci_high = 0.0

        # PRE-REGISTRATION
        config = {
            "scenario": self.name,
            "kimera_repo": str(self.kimera_repo),
            "orphan_rate_ceiling": self.orphan_rate_ceiling,
            "n_strata": len(report.per_stratum),
            "n_python_surfaces": n_python_total,
        }
        per_stratum_summary = [
            {
                "stratum": s.stratum,
                "n_total": s.n_total,
                "n_wired": s.n_wired,
                "n_orphan": s.n_orphan,
                "n_wire_candidate": s.n_wire_candidate,
            }
            for s in report.per_stratum
        ]
        dataset = DatasetRef(
            name="kimera-substrate-completeness-probe",
            content_hash=content_hash({"per_stratum": per_stratum_summary}),
            n_records=n_python_total,
            source=str(self.kimera_repo),
            kind="static-inventory+import-graph",
        )
        prereg = PreRegistration(
            config_hash=content_hash(config),
            data_hash=dataset.content_hash,
            analysis_plan=self.analysis_plan(),
        )

        # SCORE -> VERDICT
        claim = self.build_claim()
        verdict = Verdict.decide(
            observed=observed,
            threshold=claim.threshold,
            reasoning=(
                f"{n_orphan_total}/{n_python_total} surfaces classified orphan "
                f"({observed:.4f}); Wilson 95% CI [{ci_low:.4f}, {ci_high:.4f}]"
            ),
        )

        # EVIDENCE — one pillar carries the aggregate; per-stratum + action
        # lists go in the detail dict.
        orphan_files = [
            {"stratum": s.stratum, "file_path": s.file_path}
            for s in report.orphan_surfaces()
        ]
        wc_files = [
            {"stratum": s.stratum, "file_path": s.file_path}
            for s in report.wire_candidate_surfaces()
        ]
        evidence = [
            PillarEvidence(
                pillar="import_graph_static",
                statistic_name="aggregate_orphan_rate",
                statistic_value=observed,
                library="statsmodels",
                library_version=getattr(_sm, "__version__", "unknown"),
                effect_size=None,
                ci_low=ci_low,
                ci_high=ci_high,
                p_value=None,
                cross_check="n/a",
                detail={
                    "n_python_surfaces_total": n_python_total,
                    "n_orphan_total": n_orphan_total,
                    "n_wired_total": sum(s.n_wired for s in report.per_stratum),
                    "n_wire_candidate_total": sum(
                        s.n_wire_candidate for s in report.per_stratum
                    ),
                    "n_archived_total": sum(s.n_archived for s in report.per_stratum),
                    "n_parse_error_total": sum(
                        s.n_parse_error for s in report.per_stratum
                    ),
                    "ci_method": "wilson_95%",
                    "per_stratum": [s.to_dict() for s in report.per_stratum],
                    "orphan_action_list": orphan_files[:100],
                    "wire_candidate_action_list": wc_files[:100],
                    "completeness_report_id": report.report_id,
                },
            ),
        ]

        # PROVENANCE
        prov = ProvenanceGraph()
        agent_ophamin = prov.agent(
            "ophamin", role="experimentation_framework", version=__version__
        )
        agent_kimera = prov.agent(
            "kimera-swm", role="substrate_under_static_audit",
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
            n_modules=n_python_total,
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
            substrate_git_commit=_capture_kimera_commit(self.kimera_repo),
            evidence=evidence,
            verdict=verdict,
            reproduction=Reproduction(
                command=(
                    f"PYTHONPATH=src .venv/bin/python -m ophamin.cli scenario "
                    f"{self.name} --kimera-repo '{self.kimera_repo}' "
                    f"--orphan-rate-ceiling {self.orphan_rate_ceiling}"
                )
            ),
            provenance=prov.to_prov_json(),
            ophamin_version=__version__,
            ophamin_git_commit=capture_git_commit(_ophamin_project_root()),
        )
        proof.sign(sign_key)
        return proof
