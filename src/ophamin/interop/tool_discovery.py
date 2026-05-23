"""Tool discovery — the grounded *discover* stage of acquisition.

This is the producer that :mod:`ophamin.interop.tool_acquisition` refers to when
it says it "accepts the candidates it produces, from any source". It turns bare
package *names* into :class:`ToolCandidate` objects whose metadata is pulled from
the **authoritative PyPI JSON API** (version, license, summary, homepage, last
release date). The design point:

    A name-proposing agent may suggest *what* to look at; it must NOT supply the
    version or license. Those come from PyPI. So nothing the model fabricates
    (an invented version, a wished-for license) can survive into the pipeline,
    and a proposed name that does not exist on PyPI is **dropped** — it cannot be
    hallucinated into existence.

That mirrors the rest of the observatory: the model is advisory, the ground
truth is deterministic and re-checkable.

Network boundary:

- The HTTP fetch is injectable (the ``fetch`` parameter) so the module is
  testable offline.
- Per the framework's no-fallback rule, a transport failure is **loud**
  (:class:`PyPIError`); a 404 is a normal "not found" (the name is dropped),
  not an error.

This module reads public package *metadata* only. It never installs anything —
install stays owner-gated in :mod:`tool_acquisition`.
"""

from __future__ import annotations

import dataclasses
import functools
import json
import re
import ssl
import urllib.error
import urllib.request
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any, Callable

from ophamin.interop.tool_acquisition import ToolCandidate

#: PyPI's per-project JSON metadata endpoint. ``{name}`` is URL-path-safe for a
#: valid distribution name (validated before formatting).
PYPI_JSON_URL = "https://pypi.org/pypi/{name}/json"

#: Conservative PEP 508 distribution-name shape (kept local rather than reaching
#: into tool_acquisition's private regex). Guards against path/URL injection
#: before a name is ever interpolated into the PyPI URL.
_NAME_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,213}$")

_DEFAULT_TIMEOUT_S = 10.0

#: A fetch callable: ``(url, timeout_s) -> parsed-JSON dict``. Raises
#: :class:`PyPINotFound` for HTTP 404 and :class:`PyPIError` for any other
#: transport / shape failure.
FetchJson = Callable[[str, float], dict[str, Any]]


class PyPIError(RuntimeError):
    """A PyPI metadata lookup failed at the transport / response layer."""


class PyPINotFound(PyPIError):
    """The package name does not exist on PyPI (HTTP 404) — a normal 'miss'."""


@functools.lru_cache(maxsize=1)
def _ssl_context() -> ssl.SSLContext:
    """A verifying TLS context using certifi's CA bundle when available.

    urllib does not use certifi by default, which is the usual cause of
    ``[SSL: CERTIFICATE_VERIFY_FAILED]`` against PyPI on macOS. This loads
    certifi's bundle when present, else the system default. It NEVER disables
    verification — an observatory acquiring code over an unverified channel
    would be a contradiction in terms.
    """
    try:
        import certifi
        return ssl.create_default_context(cafile=certifi.where())
    except Exception:  # noqa: BLE001 — certifi missing/broken → system default
        return ssl.create_default_context()


def _default_fetch(url: str, timeout_s: float) -> dict[str, Any]:
    """Fetch + decode a JSON document over HTTPS. The default :data:`FetchJson`.

    Loud-fail (no silent empty): 404 → :class:`PyPINotFound`; any other HTTP /
    transport / decode error → :class:`PyPIError`. Mirrors the urllib usage in
    :mod:`ophamin.agentic.client`, with a certifi-backed verifying TLS context.
    """
    req = urllib.request.Request(
        url, method="GET", headers={"User-Agent": "ophamin-tool-discovery"},
    )
    try:
        with urllib.request.urlopen(  # noqa: S310
            req, timeout=timeout_s, context=_ssl_context(),
        ) as resp:
            raw = resp.read().decode("utf-8")
    except urllib.error.HTTPError as exc:
        if exc.code == 404:
            raise PyPINotFound(f"not on PyPI: {url}") from exc
        raise PyPIError(f"PyPI HTTP {exc.code}: {exc.reason} at {url}") from exc
    except urllib.error.URLError as exc:
        raise PyPIError(f"PyPI transport failure at {url}: {exc.reason}") from exc
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise PyPIError(f"PyPI returned non-JSON at {url}: {exc}") from exc
    if not isinstance(data, dict):
        raise PyPIError(f"PyPI returned unexpected shape at {url}")
    return data


def _license_from_info(info: dict[str, Any]) -> str:
    """Best authoritative license string from PyPI metadata.

    Prefers ``info.license`` when it's a short SPDX-ish token. Many projects
    instead dump the *full license text* into that field (long / multi-line) or
    leave it blank — in those cases fall back to the trove ``classifiers``
    (``License :: OSI Approved :: MIT License`` → ``MIT License``), which the
    downstream license classifier matches on by substring.
    """
    raw = str(info.get("license") or "").strip()
    if raw and len(raw) <= 40 and "\n" not in raw:
        return raw
    for classifier in info.get("classifiers") or []:
        c = str(classifier)
        if c.startswith("License ::"):
            tail = c.split("::")[-1].strip()
            if tail and tail.lower() != "osi approved":
                return tail
    return raw[:40] if raw else ""


def _homepage_from_info(info: dict[str, Any]) -> str:
    """Canonical homepage: ``home_page`` then known ``project_urls`` keys."""
    hp = str(info.get("home_page") or "").strip()
    if hp:
        return hp
    urls = info.get("project_urls") or {}
    if isinstance(urls, dict):
        for key in ("Homepage", "Home", "Source", "Repository", "Documentation"):
            val = str(urls.get(key) or "").strip()
            if val:
                return val
    return ""


def _last_release_date(data: dict[str, Any], version: str) -> str:
    """ISO date (YYYY-MM-DD) of the current release's first uploaded file."""
    files = (data.get("releases") or {}).get(version) or data.get("urls") or []
    if isinstance(files, list):
        for f in files:
            ts = str((f or {}).get("upload_time_iso_8601") or "").strip()
            if ts:
                return ts[:10]
    return ""


def resolve_pypi_candidate(
    name: str,
    *,
    need: str = "",
    import_name: str = "",
    fit_note: str = "",
    fetch: FetchJson | None = None,
    timeout_s: float = _DEFAULT_TIMEOUT_S,
) -> ToolCandidate | None:
    """Ground one package name into a :class:`ToolCandidate` from PyPI.

    Returns ``None`` if the name is invalid or not on PyPI (a dropped miss).
    Every field except ``import_name``/``fit_note`` comes from PyPI — those two
    are optional *hints* (e.g. from a name-proposing agent) the caller may pass,
    since PyPI does not publish an import name. ``stars`` / ``downloads_month``
    are left ``None`` (not in the JSON API); the evaluator treats that as
    ``maturity UNKNOWN`` honestly rather than guessing.
    """
    if not _NAME_RE.match(name or ""):
        return None
    do_fetch = fetch or _default_fetch
    try:
        data = do_fetch(PYPI_JSON_URL.format(name=name), timeout_s)
    except PyPINotFound:
        return None
    info = data.get("info") or {}
    if not isinstance(info, dict):
        raise PyPIError(f"PyPI metadata for {name!r} has no 'info' object")
    version = str(info.get("version") or "").strip()
    canonical = str(info.get("name") or name).strip() or name
    return ToolCandidate(
        name=canonical,
        summary=str(info.get("summary") or "").strip(),
        version=version,
        license=_license_from_info(info),
        homepage=_homepage_from_info(info),
        source="pypi",
        import_name=import_name,
        last_release=_last_release_date(data, version),
        fit_note=fit_note or need,
    )


@dataclass(frozen=True)
class DiscoveryResult:
    """The outcome of grounding a list of proposed names against PyPI."""

    need: str
    candidates: tuple[ToolCandidate, ...]
    found: tuple[str, ...]
    not_found: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "need": self.need,
            "n_candidates": len(self.candidates),
            "candidates": [c.to_dict() for c in self.candidates],
            "found": list(self.found),
            "not_found": list(self.not_found),
        }


def discover_candidates(
    need: str,
    names: Sequence[str],
    *,
    hints: dict[str, dict[str, str]] | None = None,
    fetch: FetchJson | None = None,
    timeout_s: float = _DEFAULT_TIMEOUT_S,
    enrich: bool = False,
) -> DiscoveryResult:
    """Ground a list of candidate names into PyPI-backed :class:`ToolCandidate`s.

    ``names`` is the agent's (or operator's) proposal; ``hints`` optionally maps
    a name to ``{"import_name": ..., "fit_note": ...}`` (e.g. a scout knows the
    import name differs from the dist name, like ``scikit-learn`` → ``sklearn``).
    De-duplicates names preserving order. Names that don't resolve land in
    ``not_found``. Raises :class:`PyPIError` only on a real transport failure —
    a 404 is a normal miss, not a failure.
    """
    if not need or not need.strip():
        raise ValueError("discovery need must be a non-empty description")
    hints = hints or {}
    seen: set[str] = set()
    candidates: list[ToolCandidate] = []
    found: list[str] = []
    not_found: list[str] = []
    for raw_name in names:
        name = (raw_name or "").strip()
        if not name or name in seen:
            continue
        seen.add(name)
        hint = hints.get(name, {})
        cand = resolve_pypi_candidate(
            name, need=need,
            import_name=str(hint.get("import_name", "")),
            fit_note=str(hint.get("fit_note", "")),
            fetch=fetch, timeout_s=timeout_s,
        )
        if cand is None:
            not_found.append(name)
        else:
            if enrich:
                cand = enrich_candidate(cand, fetch=fetch, timeout_s=timeout_s)
            candidates.append(cand)
            found.append(cand.name)
    return DiscoveryResult(
        need=need,
        candidates=tuple(candidates),
        found=tuple(found),
        not_found=tuple(not_found),
    )


# ----------------------------------------------- maturity enrichment ----------
#
# Best-effort stars (GitHub) + downloads (pypistats) so evaluate_candidate can
# return "recommend" instead of always "caution" (maturity-unknown). Unlike
# discovery's grounding, enrichment is ADVISORY: a missing star count must NOT
# block acquisition, only leave the maturity signal unknown. So it swallows
# transport failures to None (never fabricates a number, never raises) — the
# honest "we couldn't look" is None, which the evaluator already reads as
# maturity-unknown.

PYPISTATS_RECENT_URL = "https://pypistats.org/api/packages/{name}/recent"
GITHUB_REPO_API_URL = "https://api.github.com/repos/{owner}/{repo}"
_GITHUB_REPO_RE = re.compile(
    r"github\.com[/:]([A-Za-z0-9._-]+)/([A-Za-z0-9._-]+?)(?:\.git)?/?$"
)


def github_owner_repo(url: str) -> tuple[str, str] | None:
    """Parse ``(owner, repo)`` from a GitHub URL, else ``None``."""
    m = _GITHUB_REPO_RE.search(url or "")
    return (m.group(1), m.group(2)) if m else None


def _safe_fetch(
    fetch: FetchJson, url: str, timeout_s: float,
) -> dict[str, Any] | None:
    """Fetch JSON, returning ``None`` on ANY failure — enrichment is advisory."""
    try:
        return fetch(url, timeout_s)
    except (PyPIError, OSError, ValueError):
        return None


def enrich_candidate(
    candidate: ToolCandidate,
    *,
    fetch: FetchJson | None = None,
    timeout_s: float = _DEFAULT_TIMEOUT_S,
) -> ToolCandidate:
    """A copy of ``candidate`` with best-effort ``stars`` + ``downloads_month``.

    Downloads come from pypistats, stars from the GitHub API (needs a GitHub
    homepage). Advisory + non-fabricating: any field that can't be resolved
    stays ``None`` (the evaluator reads that as maturity-unknown). Never raises.
    Only fills fields that are currently ``None`` — won't clobber known values.
    """
    do_fetch = fetch or _default_fetch
    downloads = candidate.downloads_month
    if downloads is None:
        d = _safe_fetch(
            do_fetch, PYPISTATS_RECENT_URL.format(name=candidate.name), timeout_s)
        last_month = (d or {}).get("data", {}).get("last_month") if d else None
        if isinstance(last_month, int):
            downloads = last_month
    stars = candidate.stars
    if stars is None:
        owner_repo = github_owner_repo(candidate.homepage)
        if owner_repo:
            g = _safe_fetch(
                do_fetch,
                GITHUB_REPO_API_URL.format(owner=owner_repo[0], repo=owner_repo[1]),
                timeout_s,
            )
            sc = g.get("stargazers_count") if g else None
            if isinstance(sc, int):
                stars = sc
    return dataclasses.replace(candidate, stars=stars, downloads_month=downloads)
