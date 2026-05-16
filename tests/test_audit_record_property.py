"""Property-based round-trip tests for audit-record value classes (Phase S6).

Mirrors the proof-record property suite but for the auditing wheel's
data model: Finding, PillarResult, AuditSummary, AuditRecord. Each class
with a ``to_dict / from_dict`` pair must satisfy round-trip identity at
the canonical-dict layer.

Stable canonical form is load-bearing — audit-record signature
verification rests on the same byte-level reproducibility the proof
records rely on.
"""

from __future__ import annotations

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from ophamin.auditing.audit_record import AuditSummary
from ophamin.auditing.base import Finding, FindingSeverity, PillarResult

# ----------------------------------------------------------------------------
# Strategies
# ----------------------------------------------------------------------------

severities = st.sampled_from(list(FindingSeverity))
statuses = st.sampled_from(["ok", "unavailable", "error"])

identifier_strings = st.text(min_size=1, max_size=40).filter(lambda s: s.strip())
plain_strings = st.text(max_size=120)
path_strings = st.text(min_size=1, max_size=80).filter(lambda s: s.strip())

extras = st.dictionaries(identifier_strings, plain_strings, max_size=3)


@st.composite
def findings(draw: st.DrawFn) -> Finding:
    return Finding(
        pillar_name=draw(identifier_strings),
        rule_id=draw(plain_strings),
        severity=draw(severities),
        message=draw(plain_strings),
        path=draw(path_strings),
        line=draw(st.integers(min_value=0, max_value=10_000)),
        column=draw(st.integers(min_value=0, max_value=500)),
        extra=draw(extras),
    )


@st.composite
def pillar_results(draw: st.DrawFn) -> PillarResult:
    return PillarResult(
        pillar_name=draw(identifier_strings),
        tool_name=draw(plain_strings),
        tool_version=draw(plain_strings),
        status=draw(statuses),
        target_path=draw(path_strings),
        findings=tuple(draw(st.lists(findings(), max_size=4))),
        raw_stdout_bytes=draw(st.integers(min_value=0, max_value=1_000_000)),
        raw_stderr_bytes=draw(st.integers(min_value=0, max_value=1_000_000)),
        exit_code=draw(st.one_of(st.none(), st.integers(min_value=-1, max_value=255))),
        wall_time_s=draw(
            st.floats(
                min_value=0.0, max_value=1000.0,
                allow_nan=False, allow_infinity=False,
            )
        ),
        error_message=draw(plain_strings),
        extra=draw(extras),
    )


severity_histograms = st.dictionaries(
    st.sampled_from([s.value for s in FindingSeverity]),
    st.integers(min_value=0, max_value=10_000),
    max_size=5,
)

per_pillar = st.dictionaries(
    identifier_strings, st.integers(min_value=0, max_value=10_000), max_size=5,
)

top_file_entries = st.tuples(path_strings, st.integers(min_value=1, max_value=10_000))


@st.composite
def audit_summaries(draw: st.DrawFn) -> AuditSummary:
    return AuditSummary(
        total_findings=draw(st.integers(min_value=0, max_value=100_000)),
        severity_histogram=draw(severity_histograms),
        findings_per_pillar=draw(per_pillar),
        top_files=draw(st.lists(top_file_entries, max_size=5)),
        pillars_run=tuple(draw(st.lists(identifier_strings, max_size=4, unique=True))),
        pillars_unavailable=tuple(draw(st.lists(identifier_strings, max_size=3, unique=True))),
        pillars_errored=tuple(draw(st.lists(identifier_strings, max_size=3, unique=True))),
    )


# ----------------------------------------------------------------------------
# Round-trip identity tests
# ----------------------------------------------------------------------------


@given(findings())
@settings(max_examples=150, deadline=None)
def test_finding_roundtrip_dict(f: Finding) -> None:
    rebuilt = Finding.from_dict(f.to_dict())
    assert rebuilt.to_dict() == f.to_dict()
    # Severity must survive as the enum, not as a string
    assert isinstance(rebuilt.severity, FindingSeverity)
    assert rebuilt.severity == f.severity


@given(pillar_results())
@settings(max_examples=100, deadline=None)
def test_pillar_result_roundtrip_dict(p: PillarResult) -> None:
    rebuilt = PillarResult.from_dict(p.to_dict())
    # PillarResult.to_dict includes computed fields (severity_histogram, top10);
    # ``from_dict`` then drops those — so we can't compare full to_dict outputs.
    # The load-bearing invariant is that all the FIELDS the from_dict consumes
    # round-trip identically.
    assert rebuilt.pillar_name == p.pillar_name
    assert rebuilt.tool_name == p.tool_name
    assert rebuilt.tool_version == p.tool_version
    assert rebuilt.status == p.status
    assert rebuilt.target_path == p.target_path
    assert rebuilt.findings == p.findings
    assert rebuilt.raw_stdout_bytes == p.raw_stdout_bytes
    assert rebuilt.raw_stderr_bytes == p.raw_stderr_bytes
    assert rebuilt.exit_code == p.exit_code
    assert rebuilt.wall_time_s == p.wall_time_s
    assert rebuilt.error_message == p.error_message
    assert rebuilt.extra == p.extra


@given(audit_summaries())
@settings(max_examples=100, deadline=None)
def test_audit_summary_roundtrip_dict(s: AuditSummary) -> None:
    rebuilt = AuditSummary.from_dict(s.to_dict())
    assert rebuilt.to_dict() == s.to_dict()
    # top_files: JSON loses tuple-ness so from_dict re-tuples explicitly.
    assert all(isinstance(t, tuple) for t in rebuilt.top_files)


# ----------------------------------------------------------------------------
# Invariants for derived signals
# ----------------------------------------------------------------------------


@given(pillar_results())
@settings(max_examples=100, deadline=None)
def test_pillar_result_finding_count_matches(p: PillarResult) -> None:
    """finding_count is always exactly len(findings)."""
    assert p.finding_count == len(p.findings)
    assert p.to_dict()["finding_count"] == len(p.findings)


@given(pillar_results())
@settings(max_examples=100, deadline=None)
def test_pillar_result_severity_histogram_sum_matches(p: PillarResult) -> None:
    """Σ severity_histogram counts == total finding count."""
    hist = p.severity_histogram()
    assert sum(hist.values()) == len(p.findings)


@given(pillar_results())
@settings(max_examples=100, deadline=None)
def test_pillar_result_per_file_top_n_monotonic(p: PillarResult) -> None:
    """per_file_count(top_n) returns at most top_n entries in descending count order."""
    top = p.per_file_count(10)
    counts = [c for _, c in top]
    assert counts == sorted(counts, reverse=True)
    assert len(top) <= 10


# ----------------------------------------------------------------------------
# Boundary cases
# ----------------------------------------------------------------------------


def test_finding_from_dict_accepts_lowercase_severity() -> None:
    """Severity is stored as the enum value (lowercase). from_dict must accept it back."""
    data = {
        "pillar_name": "ruff",
        "rule_id": "E501",
        "severity": "high",
        "message": "line too long",
        "path": "src/foo.py",
        "line": 12,
        "column": 80,
        "extra": {},
    }
    f = Finding.from_dict(data)
    assert f.severity is FindingSeverity.HIGH


def test_audit_summary_top_files_round_trips_tuple_shape() -> None:
    """top_files JSON-decodes as nested lists; from_dict must re-tuple them."""
    s = AuditSummary(
        total_findings=3,
        severity_histogram={"high": 2, "low": 1},
        findings_per_pillar={"ruff": 3},
        top_files=[("src/a.py", 2), ("src/b.py", 1)],
        pillars_run=("ruff",),
        pillars_unavailable=(),
        pillars_errored=(),
    )
    rebuilt = AuditSummary.from_dict(s.to_dict())
    assert rebuilt.top_files == [("src/a.py", 2), ("src/b.py", 1)]
    assert all(isinstance(t, tuple) and len(t) == 2 for t in rebuilt.top_files)
