"""JUnit XML exporter — EmpiricalProofRecord → JUnit XML.

JUnit XML is the de-facto standard format for CI test-result aggregation
(Jenkins originated it; every modern CI consumes it). Output produced here
is compatible with:

  - GitHub Actions (via ``actions/upload-artifact`` + test-report viewers)
  - GitLab CI's "Tests" tab
  - CircleCI's test summary
  - Jenkins' Test Result Trend
  - Bitrise / TeamCity / Bamboo / any CI's JUnit consumer

Mapping (Empirical Proof Record → JUnit):

  one scenario (one proof record)          → one ``<testsuite>``
  the pre-registered claim                 → one ``<testcase>`` named after
                                              the claim's threshold metric
  verdict.outcome
      VALIDATED                            → testcase passes (no child)
      REFUTED                              → testcase fails (``<failure>``)
      INCONCLUSIVE                         → testcase skipped (``<skipped>``)
  each PillarEvidence statistic            → one extra ``<testcase>`` if it
                                              carries a CI; passes by default
                                              (descriptive evidence, not gated)

Original Ophamin signature + proof_id land in ``<properties>`` so the
record is traceable from any CI dashboard.

A JUnit ``<testsuites>`` wrapper is emitted at the top so multiple records
can be bundled together in a future batch-export call.
"""

from __future__ import annotations

import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any
from defusedxml.minidom import parseString  # XXE-hardened drop-in

_FAILURE_TYPE = "ophamin.REFUTED"
_SKIPPED_TYPE = "ophamin.INCONCLUSIVE"


def _attrib_str(value: Any) -> str:
    """Coerce a value to a string suitable for an XML attribute."""
    if value is None:
        return ""
    return str(value)


def _add_property(properties: ET.Element, name: str, value: Any) -> None:
    ET.SubElement(properties, "property", attrib={
        "name": name,
        "value": _attrib_str(value),
    })


def proof_record_to_junit_xml(record: dict[str, Any]) -> ET.Element:
    """Convert an Empirical Proof Record dict (as produced by
    EmpiricalProofRecord.to_dict()) into a JUnit ``<testsuites>`` element.

    Returns the root XML element; caller serializes with ElementTree.tostring
    or via ``JUnitXMLExporter.export``.
    """
    if not isinstance(record, dict):
        raise TypeError("proof_record_to_junit_xml expects a dict")
    if "claim" not in record or "verdict" not in record:
        raise ValueError(
            "input does not look like an Empirical Proof Record "
            "(missing 'claim' and/or 'verdict')"
        )

    claim = record.get("claim", {})
    threshold = claim.get("threshold", {})
    verdict = record.get("verdict", {})
    identity = record.get("identity", {})
    data = record.get("data", {})
    reproduction = record.get("reproduction", {})
    evidence = record.get("evidence", []) or []

    outcome = verdict.get("outcome", "")
    metric = threshold.get("metric", "primary")
    scenario_name = _scenario_name_from_record(record)

    # one suite per record; one primary testcase + one per evidence statistic
    suites = ET.Element("testsuites", attrib={
        "name": f"ophamin/{scenario_name}",
        "tests": "0",      # set below
        "failures": "0",
        "errors": "0",
        "skipped": "0",
        "time": "0",
    })
    suite = ET.SubElement(suites, "testsuite", attrib={
        "name": scenario_name,
        "tests": "0",
        "failures": "0",
        "errors": "0",
        "skipped": "0",
        "time": "0",
        "timestamp": _attrib_str(identity.get("created_at", "")),
    })

    # provenance properties — every consumer can drill back
    props = ET.SubElement(suite, "properties")
    _add_property(props, "ophamin_proof_id", record.get("proof_id", ""))
    _add_property(props, "ophamin_signature", record.get("signature", ""))
    _add_property(props, "ophamin_schema_version", record.get("schema_version", ""))
    _add_property(props, "ophamin_version", identity.get("ophamin_version", ""))
    _add_property(props, "ophamin_git_commit", identity.get("ophamin_git_commit", ""))
    _add_property(props, "substrate_name", data.get("substrate_name", ""))
    _add_property(props, "substrate_git_commit", data.get("substrate_git_commit", ""))
    _add_property(props, "reproduction_command", reproduction.get("command", ""))
    _add_property(props, "claim_statement", claim.get("statement", ""))
    _add_property(props, "claim_h0", claim.get("h0", ""))
    _add_property(props, "claim_h1", claim.get("h1", ""))
    _add_property(props, "preregistered_at",
                  record.get("preregistration", {}).get("preregistered_at", ""))

    # primary testcase: the pre-registered claim's pass/fail
    classname = f"ophamin.scenario.{scenario_name}"
    primary = ET.SubElement(suite, "testcase", attrib={
        "classname": classname,
        "name": metric,
        "time": "0",
    })
    _add_outcome(primary, outcome, verdict, threshold)

    # evidence testcases — each non-primary statistic is its own descriptive
    # testcase that always passes (the proof record's verdict is on the
    # primary metric, not on evidence)
    n_extra = 0
    for ev in evidence:
        stat = ev.get("statistic_name", "")
        if not stat or stat == metric:
            continue  # already covered by the primary testcase
        n_extra += 1
        case = ET.SubElement(suite, "testcase", attrib={
            "classname": f"{classname}.evidence",
            "name": stat,
            "time": "0",
        })
        # surface CI + value as system-out so dashboards can show context
        sysout = ET.SubElement(case, "system-out")
        lo = ev.get("ci_low")
        hi = ev.get("ci_high")
        ci_part = (
            f", 95% CI ({lo:.4f}, {hi:.4f})"
            if (lo is not None and hi is not None) else ""
        )
        sysout.text = (
            f"value={ev.get('statistic_value', '')}{ci_part} "
            f"[{ev.get('library', '')} {ev.get('library_version', '')}]"
        )

    # finalize testsuite counts
    n_tests = 1 + n_extra
    n_failed = 1 if outcome == "REFUTED" else 0
    n_skipped = 1 if outcome == "INCONCLUSIVE" else 0
    suite.set("tests", str(n_tests))
    suite.set("failures", str(n_failed))
    suite.set("skipped", str(n_skipped))
    suites.set("tests", str(n_tests))
    suites.set("failures", str(n_failed))
    suites.set("skipped", str(n_skipped))

    return suites


def _add_outcome(
    case: ET.Element, outcome: str, verdict: dict[str, Any], threshold: dict[str, Any]
) -> None:
    """Wire the verdict outcome onto the testcase element."""
    reasoning = verdict.get("reasoning", "")
    threshold_desc = (
        f"{threshold.get('metric', '')} {threshold.get('comparator', '')} "
        f"{threshold.get('value', '')} {threshold.get('units', '')}".strip()
    )
    if outcome == "REFUTED":
        failure = ET.SubElement(case, "failure", attrib={
            "type": _FAILURE_TYPE,
            "message": (
                f"observed {verdict.get('observed_value', '')} does NOT "
                f"satisfy {threshold_desc}"
            ),
        })
        failure.text = reasoning
    elif outcome == "INCONCLUSIVE":
        skipped = ET.SubElement(case, "skipped", attrib={
            "type": _SKIPPED_TYPE,
            "message": (
                f"INCONCLUSIVE — evidence insufficient to decide for or "
                f"against the claim (threshold: {threshold_desc})"
            ),
        })
        skipped.text = reasoning
    elif outcome == "VALIDATED":
        # passing testcase needs no child; record the observed value in
        # system-out for downstream visibility
        sysout = ET.SubElement(case, "system-out")
        sysout.text = (
            f"observed {verdict.get('observed_value', '')} satisfies "
            f"{threshold_desc}"
        )
    else:
        # unknown outcome — surface as an error
        error = ET.SubElement(case, "error", attrib={
            "type": f"ophamin.unknown_outcome.{outcome}",
            "message": f"unknown verdict outcome: {outcome!r}",
        })
        error.text = reasoning


def _scenario_name_from_record(record: dict[str, Any]) -> str:
    """Best-effort scenario name from the reproduction command or claim.

    Looks for ``scenario <name>`` anywhere in the reproduction command,
    not just at position 1. Reproduction commands in the wild look like
    ``PYTHONPATH=src .venv/bin/python -m ophamin.cli scenario foo``, so
    a simple positional check misses the name.
    """
    cmd = str(record.get("reproduction", {}).get("command", ""))
    if cmd:
        parts = cmd.split()
        for i, token in enumerate(parts):
            if token == "scenario" and i + 1 < len(parts):
                return parts[i + 1].replace("/", "-")
    # fallback: hash up the threshold metric
    metric = record.get("claim", {}).get("threshold", {}).get("metric", "")
    if metric:
        return f"metric-{metric}"
    return "unnamed"


def _prettify(element: ET.Element) -> str:
    """Return a pretty-printed XML string for the element."""
    rough = ET.tostring(element, encoding="utf-8")
    pretty: str = parseString(rough).toprettyxml(indent="  ", encoding="utf-8").decode("utf-8")
    return pretty


class JUnitXMLExporter:
    """Wrap ``proof_record_to_junit_xml`` for ergonomic CLI access."""

    def export(self, proof_record: dict[str, Any], out_path: str | Path) -> Path:
        root = proof_record_to_junit_xml(proof_record)
        out = Path(out_path)
        if out.suffix.lower() not in (".xml", ".junit"):
            out = out.with_suffix(".xml")
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(_prettify(root), encoding="utf-8")
        return out
