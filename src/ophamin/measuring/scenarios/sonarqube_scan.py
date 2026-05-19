"""The SonarQube-scan scenario — code-quality as a signed empirical claim.

Different from cognitive- and structural-tier scenarios: this one does
not run any Kimera cycle and does not walk the repo. It probes a
running SonarQube instance over REST, captures the project's *measured*
code-quality state, and emits a signed ``EmpiricalProofRecord`` whose
falsifiable claim is the SonarQube Quality Gate verdict (and whose
evidence carries the raw measures: bugs / vulnerabilities / security
hotspots / code smells / duplication / SQALE technical-debt / ncloc).

This is the load-bearing scenario for the user's 0.50.0+ directive:

> a proper SonarQube instance, running for kimera swm, mandatory
> — owner, 2026-05-19

Code quality + cognitive behaviour now share one signed-claim
discipline. The empirical numbers captured by the bundled SonarQube
stack (post `bash scripts/sonar_scan.sh ...`) become observation
records, not text in a README.

Falsifiable claim (default)
===========================

> The SonarQube Quality Gate for project ``<projectKey>`` is **OK** —
> i.e. ``project_status.status == "OK"``.

The Quality Gate is the dev's signed-off threshold for whether code is
shippable. The "Sonar way" gate enforces Clean-as-You-Code (no NEW
regression on bugs / vulnerabilities / coverage / duplication on NEW
code since the baseline). A future caller can override the threshold to
gate on absolute counts (``max_bugs``, ``max_vulnerabilities``,
``max_duplication_pct``) instead, but the default is QG-equality.

REFUTED here means the Quality Gate failed on the latest scan — the
operator's action list is exactly what the SonarQube dashboard
surfaces (this scenario does not duplicate that list; it links to it
via the dashboard URL embedded in the evidence detail).

Output
======

A signed ``EmpiricalProofRecord`` whose evidence carries:

  * ``qg_status`` (OK / WARN / ERROR / NONE) + ``qg_passed`` (1.0/0.0)
  * the seven canonical Sonar metrics: ``bugs``, ``vulnerabilities``,
    ``security_hotspots``, ``code_smells``, ``duplicated_lines_density``
    (percent), ``ncloc`` (non-comment lines of code), ``sqale_index``
    (technical-debt minutes)
  * the dashboard URL the operator can open to drill down
  * the SonarQube server version (for reproducibility — captured as
    pillar ``library_version``)

This scenario is the empirical-validation counterpart to
``docs/SONARQUBE_KIMERA_VALIDATION.md`` — same numbers, but signed,
content-addressed, and re-runnable by anyone with REST access to the
stack.
"""

from __future__ import annotations

import json
import urllib.error
import urllib.parse
import urllib.request
from base64 import b64encode
from pathlib import Path
from typing import Any

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
from ophamin.measuring.scenarios.base import (
    DEFAULT_SIGN_KEY,
    Scenario,
    ScenarioScore,
    Tier,
)
from ophamin.seeing.corpus import CorpusRecord
from ophamin.seeing.substrate.base import CycleResult, SubstrateUnderTest


#: The canonical Sonar metric keys this scenario captures. Order is the
#: stable presentation order in the proof-record evidence detail.
_CANONICAL_METRIC_KEYS: tuple[str, ...] = (
    "bugs",
    "vulnerabilities",
    "security_hotspots",
    "code_smells",
    "duplicated_lines_density",
    "ncloc",
    "sqale_index",
)

#: The four valid Quality Gate states per SonarQube's API documentation.
_VALID_QG_STATUSES: frozenset[str] = frozenset({"OK", "WARN", "ERROR", "NONE"})


class SonarQubeAPIError(RuntimeError):
    """Raised when the SonarQube REST API returns a non-2xx response.

    Loud failure on API error surfaces a misconfigured / unreachable /
    auth-expired SonarQube instance at scenario-run time instead of
    silently degrading. Carries the URL + status code + first 500 chars
    of the response body for the caller to log.
    """

    def __init__(self, url: str, status_code: int, body: str) -> None:
        self.url = url
        self.status_code = status_code
        self.body = body
        snippet = body[:500] + ("..." if len(body) > 500 else "")
        super().__init__(
            f"SonarQube API call failed: {url} → HTTP {status_code}; "
            f"body: {snippet!r}"
        )


class SonarQubeQualityGateMissingError(RuntimeError):
    """Raised when the QG status payload is malformed or missing.

    A SonarQube instance with a project but no scan run yet returns
    ``status="NONE"``; we surface this loudly because emitting a proof
    against an un-scanned project is not a meaningful empirical claim.
    """

    def __init__(self, project_key: str, payload: dict[str, Any]) -> None:
        self.project_key = project_key
        self.payload = payload
        super().__init__(
            f"SonarQube project_status for {project_key!r} carries no "
            f"meaningful status; payload was: {json.dumps(payload)[:300]!r}"
        )


def _http_get_json(url: str, *, token: str = "", timeout: float = 30.0) -> dict[str, Any]:
    """GET ``url`` and parse the body as JSON; loud-fail on non-2xx.

    Authentication: SonarQube uses ``Basic <token>:`` (token as user,
    empty password). When ``token`` is empty, no Authorization header
    is sent — the caller is presumed to be hitting an open instance or
    using anonymous-permitted endpoints.
    """
    req = urllib.request.Request(url)
    if token:
        auth = b64encode(f"{token}:".encode("ascii")).decode("ascii")
        req.add_header("Authorization", f"Basic {auth}")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:  # noqa: S310
            payload = resp.read().decode("utf-8")
            return json.loads(payload)
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace") if exc.fp else ""
        raise SonarQubeAPIError(url, exc.code, body) from exc


def _coerce_measure(raw_value: str | None, *, default: float = 0.0) -> float:
    """Parse a Sonar measure string value into a float; ``None`` → default.

    SonarQube returns numeric measures as JSON strings (e.g. ``"667"``,
    ``"9.0"``). We coerce defensively so a missing measure (project too
    new to have one) does not raise — the empirical claim is on the
    Quality Gate status, not on every measure.
    """
    if raw_value is None:
        return default
    return float(raw_value)


class SonarQubeScanProof(Scenario):
    """Sign a SonarQube Quality Gate verdict as an empirical proof record.

    Probes a running SonarQube instance over REST, captures the QG
    status + canonical measures for ``project_key``, and emits a signed
    record whose threshold is the QG verdict. The proof's evidence
    carries the seven canonical metrics so downstream proof consumers
    can read the numbers without re-hitting the API.

    Construct with the running stack's ``base_url`` + ``project_key``
    and a SonarQube user token (token-as-user HTTP Basic auth); call
    ``run()`` to get a signed ``EmpiricalProofRecord``.
    """

    name = "sonarqube-scan"
    tier = Tier.ENGINEERING
    family = "code_quality"
    goal = (
        "Capture a SonarQube Quality Gate verdict as a signed empirical "
        "proof record — bring code-quality observation under the same "
        "signed-claim discipline as cognitive-behaviour observation."
    )
    explanation = (
        "Per the 0.50.0+ mandatory-SonarQube directive, Ophamin runs a "
        "SonarQube stack for Kimera-SWM. This scenario is the empirical "
        "validation counterpart to the dashboard: it probes the SonarQube "
        "REST API (``/api/qualitygates/project_status`` + "
        "``/api/measures/component``), captures the QG status + seven "
        "canonical metrics (bugs / vulnerabilities / security_hotspots / "
        "code_smells / duplicated_lines_density / ncloc / sqale_index), "
        "and signs the result. The default falsifiable claim is "
        "``qg_status == OK``; the operator can re-run the scan + scenario "
        "to track regression vs. a baseline. REFUTED here means the "
        "dashboard's action list is non-empty — Ophamin does not "
        "duplicate that list; it links to it."
    )
    method = "quality_gate_boolean"
    falsification_consequence = (
        "SonarQube Quality Gate is not OK — the dashboard's bug + "
        "vulnerability + duplication + coverage findings are the "
        "concrete action list."
    )
    target = "sonarqube_rest_api"

    def __init__(
        self,
        *,
        base_url: str = "http://localhost:9000",
        project_key: str = "kimera-swm",
        token: str = "",
        timeout: float = 30.0,
    ) -> None:
        if not base_url.startswith(("http://", "https://")):
            raise ValueError(
                f"base_url must be a fully qualified http(s) URL, got {base_url!r}"
            )
        if not project_key.strip():
            raise ValueError("project_key must be a non-empty string")
        if timeout <= 0:
            raise ValueError(f"timeout must be positive seconds, got {timeout}")
        self.base_url = base_url.rstrip("/")
        self.project_key = project_key
        self.token = token
        self.timeout = float(timeout)
        # static scenario — base.run() is overridden, no cycle stream
        self.n_cycles = 0
        # ``last_payload`` is populated by run() so the CLI can persist
        # the raw REST response alongside the proof for offline replay.
        self.last_payload: dict[str, Any] | None = None

    # ----------------------------------------------------------------- claim --

    def build_claim(self) -> Claim:
        return Claim(
            statement=(
                f"The SonarQube Quality Gate for project {self.project_key!r} "
                f"is OK — i.e. the project meets the configured gate's "
                f"conditions on new-code regressions and aggregate counts."
            ),
            operationalization=(
                "Query SonarQube's REST API "
                f"``GET {self.base_url}/api/qualitygates/project_status"
                f"?projectKey={self.project_key}`` and read "
                "``projectStatus.status``. Map OK -> 1.0, anything else "
                "(WARN / ERROR / NONE) -> 0.0. Threshold: must equal 1.0."
            ),
            threshold=Threshold(
                metric="qg_passed",
                comparator=">=",
                value=1.0,
                units="boolean",
            ),
            h0=(
                f"H0: SonarQube QG for {self.project_key!r} is not OK — code "
                "quality regressed against the configured gate"
            ),
            h1=(
                f"H1: SonarQube QG for {self.project_key!r} is OK — the "
                "configured gate's conditions are met"
            ),
        )

    def analysis_plan(self) -> str:
        return (
            f"Connect to SonarQube at {self.base_url} (token auth), fetch "
            f"project_status for {self.project_key!r}, then fetch the seven "
            f"canonical measures via /api/measures/component. Map QG status "
            f"OK -> 1.0 / other -> 0.0; decide against threshold >= 1.0. "
            f"Raw measures + server version + dashboard URL go into the "
            f"proof evidence detail."
        )

    def score(
        self,
        cycle_results: list[CycleResult],
        records: list[CorpusRecord],
    ) -> ScenarioScore:
        """Never called — base.run() is overridden."""
        raise NotImplementedError(
            "SonarQubeScanProof uses a custom run() loop; score() is "
            "unreachable."
        )

    # ----------------------------------------------------------------- REST --

    def _qg_endpoint(self) -> str:
        return (
            f"{self.base_url}/api/qualitygates/project_status?"
            + urllib.parse.urlencode({"projectKey": self.project_key})
        )

    def _measures_endpoint(self) -> str:
        return (
            f"{self.base_url}/api/measures/component?"
            + urllib.parse.urlencode(
                {
                    "component": self.project_key,
                    "metricKeys": ",".join(_CANONICAL_METRIC_KEYS),
                }
            )
        )

    def _version_endpoint(self) -> str:
        return f"{self.base_url}/api/server/version"

    def _dashboard_url(self) -> str:
        return f"{self.base_url}/dashboard?id={urllib.parse.quote(self.project_key)}"

    def fetch_quality_gate(self) -> tuple[str, list[dict[str, Any]]]:
        """Fetch QG status + conditions; loud-fail on missing payload."""
        payload = _http_get_json(
            self._qg_endpoint(), token=self.token, timeout=self.timeout
        )
        ps = payload.get("projectStatus")
        if not isinstance(ps, dict) or "status" not in ps:
            raise SonarQubeQualityGateMissingError(self.project_key, payload)
        status = str(ps["status"])
        if status not in _VALID_QG_STATUSES:
            raise SonarQubeQualityGateMissingError(self.project_key, payload)
        conditions = list(ps.get("conditions") or [])
        return status, conditions

    def fetch_measures(self) -> dict[str, float]:
        """Fetch the seven canonical measures; coerce strings to floats."""
        payload = _http_get_json(
            self._measures_endpoint(), token=self.token, timeout=self.timeout
        )
        component = payload.get("component") or {}
        measures_raw = component.get("measures") or []
        by_key = {str(m.get("metric", "")): m.get("value") for m in measures_raw}
        return {
            key: _coerce_measure(by_key.get(key)) for key in _CANONICAL_METRIC_KEYS
        }

    def fetch_server_version(self) -> str:
        """Fetch the SonarQube server version (plain text endpoint)."""
        req = urllib.request.Request(self._version_endpoint())
        if self.token:
            auth = b64encode(f"{self.token}:".encode("ascii")).decode("ascii")
            req.add_header("Authorization", f"Basic {auth}")
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:  # noqa: S310
                return resp.read().decode("utf-8").strip()
        except urllib.error.HTTPError as exc:
            body = exc.read().decode("utf-8", errors="replace") if exc.fp else ""
            raise SonarQubeAPIError(
                self._version_endpoint(), exc.code, body
            ) from exc

    # ------------------------------------------------------------------ run --

    def run(  # type: ignore[override]
        self,
        substrate: SubstrateUnderTest | None = None,
        *,
        data_root: str | Path | None = None,
        sign_key: bytes = DEFAULT_SIGN_KEY,
    ) -> EmpiricalProofRecord:
        """Probe SonarQube REST, sign the QG verdict, return the record."""
        qg_status, qg_conditions = self.fetch_quality_gate()
        measures = self.fetch_measures()
        server_version = self.fetch_server_version()

        qg_passed = 1.0 if qg_status == "OK" else 0.0

        payload_dump: dict[str, Any] = {
            "qg_status": qg_status,
            "qg_conditions": qg_conditions,
            "measures": dict(measures),
            "server_version": server_version,
            "base_url": self.base_url,
            "project_key": self.project_key,
        }
        self.last_payload = payload_dump

        # PRE-REGISTRATION
        config = {
            "scenario": self.name,
            "base_url": self.base_url,
            "project_key": self.project_key,
            "metric_keys": list(_CANONICAL_METRIC_KEYS),
            "qg_pass_value": "OK",
        }
        dataset = DatasetRef(
            name=f"sonarqube-scan:{self.project_key}",
            content_hash=content_hash(payload_dump),
            n_records=int(measures.get("ncloc", 0.0)),
            source=self._dashboard_url(),
            kind="sonarqube-rest-api",
        )
        prereg = PreRegistration(
            config_hash=content_hash(config),
            data_hash=dataset.content_hash,
            analysis_plan=self.analysis_plan(),
        )

        # SCORE -> VERDICT
        claim = self.build_claim()
        verdict = Verdict.decide(
            observed=qg_passed,
            threshold=claim.threshold,
            reasoning=(
                f"SonarQube QG status for {self.project_key!r} = {qg_status!r}; "
                f"qg_passed = {qg_passed}; bugs={int(measures.get('bugs', 0))}; "
                f"vulnerabilities={int(measures.get('vulnerabilities', 0))}; "
                f"security_hotspots={int(measures.get('security_hotspots', 0))}; "
                f"duplication={measures.get('duplicated_lines_density', 0.0):.1f}%; "
                f"ncloc={int(measures.get('ncloc', 0))}; "
                f"sqale_index={int(measures.get('sqale_index', 0))} minutes"
            ),
        )

        # EVIDENCE — one pillar; raw measures + conditions + URL in detail.
        evidence = [
            PillarEvidence(
                pillar="sonarqube_rest_api",
                statistic_name="qg_passed",
                statistic_value=qg_passed,
                library="sonarqube",
                library_version=server_version,
                effect_size=None,
                ci_low=None,
                ci_high=None,
                p_value=None,
                cross_check="n/a",
                detail={
                    "qg_status": qg_status,
                    "qg_conditions": qg_conditions,
                    "measures": measures,
                    "dashboard_url": self._dashboard_url(),
                    "metric_keys": list(_CANONICAL_METRIC_KEYS),
                    "base_url": self.base_url,
                    "project_key": self.project_key,
                },
            ),
        ]

        # PROVENANCE
        prov = ProvenanceGraph()
        agent_ophamin = prov.agent(
            "ophamin", role="experimentation_framework", version=__version__
        )
        agent_sonar = prov.agent(
            "sonarqube",
            role="external_code_quality_analyzer",
            version=server_version,
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
            base_url=self.base_url,
            project_key=self.project_key,
        )
        result_entity = prov.entity(f"proof:{self.name}")
        prov.used(activity, data_entity)
        prov.was_associated_with(activity, agent_ophamin)
        prov.was_associated_with(activity, agent_sonar)
        prov.was_generated_by(result_entity, activity)
        prov.was_attributed_to(result_entity, agent_sonar)
        prov.was_derived_from(result_entity, data_entity)

        proof = EmpiricalProofRecord(
            claim=claim,
            preregistration=prereg,
            datasets=[dataset],
            substrate_name=f"sonarqube:{self.project_key}",
            substrate_git_commit="",  # external analyser; no Kimera commit on this scan path
            evidence=evidence,
            verdict=verdict,
            reproduction=Reproduction(
                command=self._build_reproduction_command(),
            ),
            provenance=prov.to_prov_json(),
            ophamin_version=__version__,
            ophamin_git_commit=capture_git_commit(_ophamin_project_root()),
        )
        proof.sign(sign_key)
        return proof
