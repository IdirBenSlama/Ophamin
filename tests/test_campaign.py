"""Hardening tests for the 6-phase composite-run orchestrator (Move F).

Covers:

- :class:`CampaignPhase` + :class:`CampaignRecord` data model + serde
  round-trip + signing + sign verification + canonical ID stability;
- :func:`run_campaign` against :class:`MockSubstrate` for the
  always-runnable phases (measuring + comparing + reporting); the
  three phases that require Kimera repo / InstrumentedSubstrate surface
  must `skipped` cleanly with reason text.
- CLI smoke for `ophamin run-all`.
"""

from __future__ import annotations

import json
import subprocess
import sys

import pytest

from ophamin import __version__
from ophamin.campaign import (
    CANONICAL_PHASE_ORDER,
    CampaignPhase,
    CampaignRecord,
    dump_campaign,
    load_campaign,
    run_campaign,
)
from ophamin.seeing.substrate import MockSubstrate


_SIGN_KEY = b"campaign-test-key"


# --- data model -----------------------------------------------------------


def test_canonical_phase_order_is_exactly_six():
    """The six wheels are the canonical phase order — adding a 7th
    without docs update is a drift signal."""
    assert CANONICAL_PHASE_ORDER == (
        "seeing",
        "measuring",
        "comparing",
        "instrumenting",
        "auditing",
        "reporting",
    )


def test_campaign_phase_frozen():
    phase = CampaignPhase(
        wheel="seeing",
        started_at="2026-05-16T00:00:00+00:00",
        completed_at="2026-05-16T00:00:01+00:00",
        status="ok",
    )
    with pytest.raises(Exception):
        phase.status = "failed"  # type: ignore[misc]


def test_campaign_phase_to_dict_round_trip():
    phase = CampaignPhase(
        wheel="measuring",
        started_at="2026-05-16T00:00:00+00:00",
        completed_at="2026-05-16T00:00:10+00:00",
        status="ok",
        artifact_paths=("/tmp/a.json",),
        summary={"n_validated": 1, "n_refuted": 0},
    )
    data = phase.to_dict()
    back = CampaignPhase.from_dict(data)
    assert back == phase


def test_campaign_record_id_is_content_hash():
    record = CampaignRecord(
        target_name="mock",
        target_git_commit="abc",
        phases=[],
    )
    cid_a = record.campaign_id
    # mutating an unrelated field must change the id
    record.target_git_commit = "def"
    cid_b = record.campaign_id
    assert cid_a != cid_b


def test_campaign_record_sign_and_verify():
    record = CampaignRecord(target_name="mock", target_git_commit="abc")
    record.sign(_SIGN_KEY)
    assert record.verify_signature(_SIGN_KEY) is True
    assert record.verify_signature(b"wrong-key") is False


def test_campaign_record_to_dict_from_dict_round_trip():
    record = CampaignRecord(
        target_name="mock",
        target_git_commit="abc",
        phases=[
            CampaignPhase(
                wheel="seeing",
                started_at="2026-05-16T00:00:00+00:00",
                completed_at="2026-05-16T00:00:01+00:00",
                status="skipped",
                error="reason",
            )
        ],
    )
    record.sign(_SIGN_KEY)
    data = record.to_dict()
    back = CampaignRecord.from_dict(data)
    assert back.campaign_id == record.campaign_id
    assert back.verify_signature(_SIGN_KEY) is True


def test_campaign_dump_load_round_trip(tmp_path):
    record = CampaignRecord(target_name="mock", target_git_commit="abc").sign(_SIGN_KEY)
    path = dump_campaign(record, tmp_path / "CAMPAIGN.json")
    loaded = load_campaign(path)
    assert loaded.campaign_id == record.campaign_id
    assert loaded.verify_signature(_SIGN_KEY)


def test_status_counts_aggregates():
    record = CampaignRecord(target_name="mock", target_git_commit="abc")
    record.phases = [
        CampaignPhase(wheel="w1", started_at="x", completed_at="y", status="ok"),
        CampaignPhase(wheel="w2", started_at="x", completed_at="y", status="ok"),
        CampaignPhase(wheel="w3", started_at="x", completed_at="y", status="skipped"),
        CampaignPhase(wheel="w4", started_at="x", completed_at="y", status="failed"),
    ]
    counts = record.status_counts
    assert counts == {"ok": 2, "skipped": 1, "failed": 1}


def test_all_ok_and_any_failed():
    r1 = CampaignRecord(target_name="mock", target_git_commit="abc")
    r1.phases = [CampaignPhase(wheel="w", started_at="x", completed_at="y", status="ok")]
    assert r1.all_ok and not r1.any_failed

    r2 = CampaignRecord(target_name="mock", target_git_commit="abc")
    r2.phases = [
        CampaignPhase(wheel="w1", started_at="x", completed_at="y", status="ok"),
        CampaignPhase(wheel="w2", started_at="x", completed_at="y", status="skipped"),
    ]
    assert not r2.all_ok and not r2.any_failed

    r3 = CampaignRecord(target_name="mock", target_git_commit="abc")
    r3.phases = [
        CampaignPhase(wheel="w", started_at="x", completed_at="y", status="failed"),
    ]
    assert not r3.all_ok and r3.any_failed


# --- orchestrator (against MockSubstrate) ----------------------------------


@pytest.fixture
def lite_scenarios(request):
    """A short list of fast self-contained scenarios for orchestrator testing.

    The campaign orchestrator default-instantiates each Scenario class
    (no args) and runs each against the substrate. Real scenarios like
    ImmuneSiegeScenario / OrganizationalDissonanceScenario require their
    backing corpora on disk (cyber-payloads / enron) — fine for the
    author's dev box, broken on a clean CI runner where ``data/raw/`` is
    gitignored.

    To exercise the orchestrator's plumbing without coupling to corpus
    availability, we register a synthetic in-memory corpus at fixture
    setup, return the module-level test scenarios that use it, then
    clean up the corpus registration on teardown. The scenario classes
    are defined at module level (Scenario subclasses register globally
    on creation, so a fixture-scoped class would collide on its second
    invocation).
    """
    from ophamin.seeing.corpus import (
        CORPUS_FACTORIES,
        register_corpus_factory,
    )

    _NAME = "synthetic-test"
    if _NAME in CORPUS_FACTORIES:
        del CORPUS_FACTORIES[_NAME]
    register_corpus_factory(_NAME, lambda root: _SyntheticCorpus(root))

    try:
        yield [_CampaignLiteScenario, _CampaignLiteScenarioB]
    finally:
        CORPUS_FACTORIES.pop(_NAME, None)


# --- Module-level synthetic corpus + scenarios -----------------------------
# Scenario subclasses register globally on creation; keeping them at module
# scope means they register ONCE per test session and never collide.

from typing import Iterator as _Iter  # noqa: E402

from ophamin.measuring.proof import (  # noqa: E402
    Claim as _Claim,
    PillarEvidence as _PillarEvidence,
    Threshold as _Threshold,
)
from ophamin.measuring.scenarios.base import (  # noqa: E402
    Scenario as _Scenario,
    ScenarioScore as _ScenarioScore,
    Tier as _Tier,
)
from ophamin.seeing.corpus.base import (  # noqa: E402
    Corpus as _Corpus,
    CorpusRecord as _CorpusRecord,
)


class _SyntheticCorpus(_Corpus):
    """In-memory corpus for orchestrator tests; emits 6 synthetic stimuli."""

    name = "synthetic-test"
    kind = "synthetic"
    source = "in-memory (test fixture)"

    def is_available(self) -> bool:
        return True

    def records(self) -> "_Iter[_CorpusRecord]":
        for i in range(6):
            yield _CorpusRecord(
                id=f"syn-{i}", text=f"synthetic stimulus {i}", metadata={}
            )

    def _compute_content_hash(self) -> str:
        return "0" * 64

    def _compute_count(self) -> int:
        return 6


class _CampaignLiteScenario(_Scenario, register=False):
    """Self-contained scenario for campaign tests — uses the synthetic
    corpus + asserts the substrate produced ≥ 1 successful cycle.

    ``register=False`` keeps this class out of the global ``SCENARIOS``
    dict (so the CLI-iteration tests don't see it), while still being
    class-instantiable for the campaign tests that pass it explicitly.
    """

    name = "campaign_lite_a"
    tier = _Tier.SCIENTIFIC
    family = "harness"
    goal = "exercise the campaign orchestrator end-to-end"
    explanation = (
        "Synthetic corpus + thin scenario used to exercise the 6-phase "
        "orchestrator without requiring real corpora on disk."
    )
    corpus_name = "synthetic-test"
    target = "any"
    n_cycles = 4

    def build_claim(self) -> _Claim:
        return _Claim(
            statement="the substrate produces ≥ 1 successful cycle out of N",
            operationalization="count cr.success across cycle_results",
            threshold=_Threshold(
                metric="n_success", comparator=">=", value=1.0
            ),
            h0="substrate produces zero successful cycles",
            h1="substrate produces ≥ 1 successful cycle",
        )

    def select_records(self, corpus):
        return corpus.records()

    def score(self, cycle_results, records):
        n_success = sum(1 for cr in cycle_results if cr.success)
        return _ScenarioScore(
            observed_value=float(n_success),
            inconclusive=False,
            reasoning=f"{n_success} successful cycle(s) of {len(cycle_results)}",
            evidence=(
                _PillarEvidence(
                    pillar="harness",
                    statistic_name="n_success",
                    statistic_value=float(n_success),
                    library="ophamin",
                    library_version=__version__,
                ),
            ),
        )

    def analysis_plan(self) -> str:
        return "Count successful cycles; verdict via Threshold n_success >= 1."


class _CampaignLiteScenarioB(_CampaignLiteScenario, register=False):
    """Second scenario for the iteration-over-list exercise."""

    name = "campaign_lite_b"
    goal = "second scenario for orchestrator iteration test"


def test_run_campaign_against_mock_substrate(tmp_path, lite_scenarios):
    """End-to-end: 6 phases, MockSubstrate, lite scenarios. The phases
    that need a Kimera repo / InstrumentedSubstrate surface must
    skip cleanly with reason text."""
    substrate = MockSubstrate(seed=1)
    record = run_campaign(
        substrate=substrate,
        scenarios=lite_scenarios,
        out_dir=tmp_path,
        sign_key=_SIGN_KEY,
    )
    assert isinstance(record, CampaignRecord)
    assert record.verify_signature(_SIGN_KEY)
    # All six phases attempted
    assert [p.wheel for p in record.phases] == list(CANONICAL_PHASE_ORDER)
    # Phases that need Kimera repo: seeing + auditing
    seeing = next(p for p in record.phases if p.wheel == "seeing")
    auditing = next(p for p in record.phases if p.wheel == "auditing")
    assert seeing.status == "skipped"
    assert "kimera_repo" in (seeing.error or "")
    assert auditing.status == "skipped"
    # Phase that needs InstrumentedSubstrate: instrumenting
    instr = next(p for p in record.phases if p.wheel == "instrumenting")
    assert instr.status == "skipped"
    # Phases that should always run against MockSubstrate
    measuring = next(p for p in record.phases if p.wheel == "measuring")
    comparing = next(p for p in record.phases if p.wheel == "comparing")
    reporting = next(p for p in record.phases if p.wheel == "reporting")
    assert measuring.status == "ok"
    assert comparing.status == "ok"
    assert reporting.status == "ok"


def test_run_campaign_writes_per_phase_artifacts(tmp_path, lite_scenarios):
    substrate = MockSubstrate(seed=1)
    record = run_campaign(
        substrate=substrate,
        scenarios=lite_scenarios,
        out_dir=tmp_path,
        sign_key=_SIGN_KEY,
    )
    # measuring writes signed proofs into proofs/<tier>/<family>/
    proofs_dir = tmp_path / "proofs"
    assert proofs_dir.is_dir()
    proof_files = list(proofs_dir.rglob("*.json"))
    assert len(proof_files) >= 1  # at least one scenario produced a proof
    # comparing writes SUMMARY.md
    assert (tmp_path / "SUMMARY.md").is_file()
    # reporting writes REPORT.md
    assert (tmp_path / "REPORT.md").is_file()


def test_run_campaign_skip_phases(tmp_path, lite_scenarios):
    substrate = MockSubstrate(seed=1)
    record = run_campaign(
        substrate=substrate,
        scenarios=lite_scenarios,
        enable_phases={"measuring", "comparing"},
        out_dir=tmp_path,
        sign_key=_SIGN_KEY,
    )
    wheels = [p.wheel for p in record.phases]
    assert wheels == ["measuring", "comparing"]


def test_run_campaign_default_scenarios_includes_19(tmp_path):
    """When no scenarios are provided, the orchestrator picks every
    default-instantiable scenario from SCENARIOS. The exact count
    depends on which scenarios accept zero required args."""
    from ophamin.campaign import _select_default_instantiable_scenarios
    chosen = _select_default_instantiable_scenarios()
    # At least the 6 well-known default-instantiable scenarios
    assert len(chosen) >= 6


def test_run_campaign_target_name_falls_back_to_substrate_name(tmp_path, lite_scenarios):
    substrate = MockSubstrate(seed=1)
    record = run_campaign(
        substrate=substrate,
        scenarios=lite_scenarios,
        enable_phases={"measuring"},
        out_dir=tmp_path,
        sign_key=_SIGN_KEY,
    )
    assert record.target_name == "mock"  # MockSubstrate.name


def test_run_campaign_explicit_target_name(tmp_path, lite_scenarios):
    substrate = MockSubstrate(seed=1)
    record = run_campaign(
        substrate=substrate,
        target_name="my-explicit-name",
        target_git_commit="abc123",
        scenarios=lite_scenarios,
        enable_phases={"measuring"},
        out_dir=tmp_path,
        sign_key=_SIGN_KEY,
    )
    assert record.target_name == "my-explicit-name"
    assert record.target_git_commit == "abc123"


def test_run_campaign_measuring_records_verdicts(tmp_path, lite_scenarios):
    substrate = MockSubstrate(seed=1)
    record = run_campaign(
        substrate=substrate,
        scenarios=lite_scenarios,
        enable_phases={"measuring"},
        out_dir=tmp_path,
        sign_key=_SIGN_KEY,
    )
    measuring = record.phases[0]
    assert measuring.wheel == "measuring"
    assert "n_scenarios_attempted" in measuring.summary
    assert measuring.summary["n_scenarios_attempted"] == 2


# --- CLI smoke -------------------------------------------------------------


def _real_corpus_available(name: str) -> bool:
    """True iff the named corpus's expected root is on disk.

    The CLI doesn't know about test-fixture corpora; it can only invoke
    scenarios registered in ``SCENARIOS`` with real ``corpus_name`` values.
    On a clean CI runner ``data/raw/`` is empty (gitignored), so the
    scenarios referenced below need their backing corpora present to
    run. Tests that exercise the CLI happy-path therefore skip when the
    corpus is absent — a hosted Kimera-aware CI runner is the right
    environment for the full CLI smoke."""
    from ophamin.seeing.corpus import get_corpus
    try:
        corpus = get_corpus(name)
        return corpus.is_available()
    except Exception:
        return False


@pytest.mark.skipif(
    not (_real_corpus_available("cyber") and _real_corpus_available("enron")),
    reason="CLI smoke needs cyber + enron corpora on disk; absent in clean CI",
)
def test_cli_run_all_against_mock_substrate(tmp_path):
    """`ophamin run-all` against MockSubstrate (no --repo) — skip the
    slow scenarios via --scenarios to keep CI fast."""
    result = subprocess.run(
        [
            sys.executable, "-m", "ophamin.cli", "run-all",
            "--scenarios", "concentrated-immune-siege,organizational-dissonance",
            "--out-dir", str(tmp_path),
            "--quiet",
        ],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
    assert (tmp_path / "CAMPAIGN.json").is_file()
    assert "campaign complete" in result.stdout


def test_cli_run_all_unknown_scenario_returns_2(tmp_path):
    result = subprocess.run(
        [
            sys.executable, "-m", "ophamin.cli", "run-all",
            "--scenarios", "totally-fictional-scenario",
            "--out-dir", str(tmp_path),
            "--quiet",
        ],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 2
    assert "unknown scenario" in result.stderr


def test_cli_run_all_unknown_phase_returns_2(tmp_path):
    result = subprocess.run(
        [
            sys.executable, "-m", "ophamin.cli", "run-all",
            "--scenarios", "concentrated-immune-siege",
            "--skip", "not-a-real-phase",
            "--out-dir", str(tmp_path),
            "--quiet",
        ],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 2
    assert "unknown phase" in result.stderr


@pytest.mark.skipif(
    not _real_corpus_available("cyber"),
    reason="CLI smoke needs cyber corpus on disk; absent in clean CI",
)
def test_cli_run_all_skip_phases(tmp_path):
    result = subprocess.run(
        [
            sys.executable, "-m", "ophamin.cli", "run-all",
            "--scenarios", "concentrated-immune-siege",
            "--skip", "seeing,auditing,instrumenting",
            "--out-dir", str(tmp_path),
            "--quiet",
        ],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0
    data = json.loads((tmp_path / "CAMPAIGN.json").read_text())
    phases = {p["wheel"] for p in data["phases"]}
    assert "seeing" not in phases
    assert "auditing" not in phases
    assert "instrumenting" not in phases
    assert "measuring" in phases
