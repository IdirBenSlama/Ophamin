"""Grounding verification — resolve a citation to a *real, readable* paper.

This is what turns the grounding gate from a formality (the ref string is
non-empty) into enforcement (the cited paper actually exists and can be
read). A citation is verified two ways:

  * **By direct link** — an arXiv id (via the arXiv API), a DOI (via
    Crossref), or a URL (fetched). Resolution returns the paper's real
    title, so a fabricated citation fails.
  * **Locally downloaded** — a path, or a filename in the papers directory
    (``OPHAMIN_PAPERS_DIR``). The file must exist and be readable. This is
    the **offline-rigorous** path: cite a paper you've downloaded and it
    verifies with no network at all.

Status per ref:
  * ``resolved``    — the paper is real + readable (title recovered).
  * ``unresolved``  — we reached the source and it does NOT exist (404 /
                      empty result / missing file). A fabricated citation.
  * ``unreachable`` — network/IO error; we could not check (offline).
  * ``unsupported`` — the ref isn't a recognisable arXiv/DOI/URL/path.

The gate treats ``unresolved`` as an ERROR (reject the fabrication) and
``unreachable`` as a WARN (can't verify offline — don't block, but say so).
A local citation is always checkable offline, so rigorous offline work is
possible. No LLM is involved — this is deterministic resolution; reading is
HTTP/file IO. (Judging whether a paper *supports* a claim is a separate,
optional step for the dedicated scientific model.)
"""

from __future__ import annotations

import json
import os
import re
import ssl
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from xml.etree import ElementTree as ET


def _ssl_context() -> "ssl.SSLContext | None":
    """A verifying SSL context backed by certifi's CA bundle when present.

    Some Python installs (notably macOS framework builds) ship without a
    usable system CA store, so the default context fails verification on
    every https fetch. Using certifi's bundle makes citation links actually
    resolve while keeping verification ON (we never disable it)."""
    try:
        import certifi
        return ssl.create_default_context(cafile=certifi.where())
    except Exception:  # noqa: BLE001 — fall back to the platform default
        return None


_SSL_CTX = _ssl_context()

# Resolution status constants.
RESOLVED = "resolved"
UNRESOLVED = "unresolved"
UNREACHABLE = "unreachable"
UNSUPPORTED = "unsupported"

_ARXIV_RE = re.compile(r"(?:arxiv[:/]\s*)?(\d{4}\.\d{4,5})(?:v\d+)?", re.I)
_DOI_RE = re.compile(r"(10\.\d{4,9}/[-._;()/:A-Za-z0-9]+)")
_USER_AGENT = "ophamin-grounding-verifier/1.0 (citation verification)"
_MAX_BYTES = 1_000_000  # cap fetched bodies


@dataclass(frozen=True)
class GroundingResolution:
    """The outcome of resolving one citation."""

    ref: str
    kind: str            # "arxiv" | "doi" | "url" | "local" | "unknown"
    status: str          # RESOLVED | UNRESOLVED | UNREACHABLE | UNSUPPORTED
    title: str = ""
    source: str = ""     # where it resolved (api url / file path)
    detail: str = ""

    @property
    def ok(self) -> bool:
        return self.status == RESOLVED

    def to_dict(self) -> dict[str, Any]:
        return {
            "ref": self.ref, "kind": self.kind, "status": self.status,
            "title": self.title, "source": self.source, "detail": self.detail,
        }


def _papers_dir(papers_dir: str | Path | None) -> Path | None:
    p = papers_dir or os.environ.get("OPHAMIN_PAPERS_DIR", "")
    if not p:
        return None
    path = Path(p).expanduser()
    return path if path.is_dir() else None


def classify_ref(ref: str, *, papers_dir: str | Path | None = None) -> str:
    """Best-effort classify a citation ref into a resolution kind."""
    r = (ref or "").strip()
    if not r:
        return "unknown"
    # A local file path or a filename in the papers dir takes precedence —
    # offline verification is preferred when available.
    pd = _papers_dir(papers_dir)
    if Path(r).expanduser().is_file():
        return "local"
    if pd is not None and (_match_local(r, pd) is not None):
        return "local"
    if r.lower().startswith(("http://", "https://")):
        # A direct arXiv/doi.org URL is still classed by its stronger id.
        if "arxiv.org" in r.lower() and _ARXIV_RE.search(r):
            return "arxiv"
        if _DOI_RE.search(r):
            return "doi"
        return "url"
    if r.lower().startswith("arxiv") or _ARXIV_RE.fullmatch(r) or _ARXIV_RE.match(r) and r[0].isdigit():
        return "arxiv"
    if r.startswith("10.") or _DOI_RE.search(r):
        return "doi"
    return "unknown"


def _match_local(ref: str, pd: Path) -> Path | None:
    """Find a file in the papers dir matching the ref (path, filename, or
    a slugged substring of the title). Returns the path or None."""
    cand = Path(ref).expanduser()
    if cand.is_file():
        return cand
    # exact filename or stem
    for f in pd.rglob("*"):
        if not f.is_file():
            continue
        if f.name == ref or f.stem == ref:
            return f
    # slug substring (e.g. ref "Tononi 2004" → "tononi-2004-iit.pdf")
    slug = re.sub(r"[^a-z0-9]+", "", ref.lower())
    if len(slug) >= 4:
        for f in pd.rglob("*"):
            if f.is_file() and slug in re.sub(r"[^a-z0-9]+", "", f.name.lower()):
                return f
    return None


def _http_get(url: str, *, accept: str = "*/*", timeout: float = 8.0) -> tuple[int, bytes]:
    req = urllib.request.Request(url, headers={"User-Agent": _USER_AGENT, "Accept": accept})
    with urllib.request.urlopen(req, timeout=timeout, context=_SSL_CTX) as resp:  # noqa: S310 — citation verification
        return resp.status, resp.read(_MAX_BYTES)


def _resolve_arxiv(ref: str, timeout: float) -> GroundingResolution:
    m = _ARXIV_RE.search(ref)
    if not m:
        return GroundingResolution(ref, "arxiv", UNSUPPORTED, detail="no arXiv id found")
    aid = m.group(1)
    api = f"http://export.arxiv.org/api/query?id_list={aid}"
    try:
        status, body = _http_get(api, accept="application/atom+xml", timeout=timeout)
    except (urllib.error.URLError, OSError, TimeoutError) as exc:
        return GroundingResolution(ref, "arxiv", UNREACHABLE, source=api, detail=str(exc)[:120])
    if status != 200:
        return GroundingResolution(ref, "arxiv", UNRESOLVED, source=api, detail=f"HTTP {status}")
    try:
        root = ET.fromstring(body)
        ns = {"a": "http://www.w3.org/2005/Atom"}
        entry = root.find("a:entry", ns)
        if entry is None:
            return GroundingResolution(ref, "arxiv", UNRESOLVED, source=api, detail="no entry for id")
        title = (entry.findtext("a:title", default="", namespaces=ns) or "").strip()
        return GroundingResolution(ref, "arxiv", RESOLVED, title=" ".join(title.split()), source=api)
    except ET.ParseError as exc:
        return GroundingResolution(ref, "arxiv", UNREACHABLE, source=api, detail=f"parse: {exc}")


def _resolve_doi(ref: str, timeout: float) -> GroundingResolution:
    m = _DOI_RE.search(ref)
    if not m:
        return GroundingResolution(ref, "doi", UNSUPPORTED, detail="no DOI found")
    doi = m.group(1)
    api = f"https://api.crossref.org/works/{doi}"
    try:
        status, body = _http_get(api, accept="application/json", timeout=timeout)
    except (urllib.error.URLError, OSError, TimeoutError) as exc:
        return GroundingResolution(ref, "doi", UNREACHABLE, source=api, detail=str(exc)[:120])
    if status == 404:
        return GroundingResolution(ref, "doi", UNRESOLVED, source=api, detail="DOI not found")
    if status != 200:
        return GroundingResolution(ref, "doi", UNRESOLVED, source=api, detail=f"HTTP {status}")
    try:
        msg = (json.loads(body) or {}).get("message", {})
        title = (msg.get("title") or [""])[0]
        return GroundingResolution(ref, "doi", RESOLVED, title=str(title).strip(), source=api)
    except ValueError as exc:
        return GroundingResolution(ref, "doi", UNREACHABLE, source=api, detail=f"json: {exc}")


def _resolve_url(ref: str, timeout: float) -> GroundingResolution:
    try:
        status, body = _http_get(ref, timeout=timeout)
    except (urllib.error.URLError, OSError, TimeoutError) as exc:
        return GroundingResolution(ref, "url", UNREACHABLE, source=ref, detail=str(exc)[:120])
    if status >= 400:
        return GroundingResolution(ref, "url", UNRESOLVED, source=ref, detail=f"HTTP {status}")
    title = ""
    m = re.search(rb"<title[^>]*>(.*?)</title>", body, re.I | re.S)
    if m:
        title = " ".join(m.group(1).decode("utf-8", "replace").split())[:200]
    return GroundingResolution(ref, "url", RESOLVED, title=title, source=ref)


def _resolve_local(ref: str, pd: Path | None) -> GroundingResolution:
    cand = Path(ref).expanduser()
    f = cand if cand.is_file() else (_match_local(ref, pd) if pd else None)
    if f is None:
        where = str(pd) if pd else "(no papers dir set)"
        return GroundingResolution(ref, "local", UNRESOLVED, detail=f"no local file matches in {where}")
    try:
        with open(f, "rb") as fh:
            head = fh.read(256)  # confirm readable
        readable = len(head) > 0
    except OSError as exc:
        return GroundingResolution(ref, "local", UNREACHABLE, source=str(f), detail=str(exc)[:120])
    return GroundingResolution(
        ref, "local", RESOLVED if readable else UNRESOLVED,
        title=f.stem, source=str(f),
        detail="" if readable else "file empty",
    )


def resolve_ref(
    ref: str, *, papers_dir: str | Path | None = None, timeout: float = 8.0,
) -> GroundingResolution:
    """Resolve one citation to a real, readable paper (or report why not)."""
    pd = _papers_dir(papers_dir)
    kind = classify_ref(ref, papers_dir=papers_dir)
    if kind == "local":
        return _resolve_local(ref, pd)
    if kind == "arxiv":
        return _resolve_arxiv(ref, timeout)
    if kind == "doi":
        return _resolve_doi(ref, timeout)
    if kind == "url":
        return _resolve_url(ref, timeout)
    return GroundingResolution(ref, "unknown", UNSUPPORTED,
                               detail="not a recognisable arXiv id / DOI / URL / local path")


def verify_grounding(
    refs: list[str], *, papers_dir: str | Path | None = None, timeout: float = 8.0,
) -> dict[str, Any]:
    """Resolve every citation; summarise into an enforcement verdict.

    ``verified`` is True iff there is at least one ``resolved`` citation AND
    none that is ``unresolved`` (fabricated) or ``unsupported`` (no resolvable
    locator — a prose-only citation we cannot check). ``unreachable`` refs
    (network down) are reported but tolerated so offline work isn't blocked —
    the offline-rigorous path is to cite a locally-downloaded paper, which
    always resolves without network.
    """
    resolutions = [resolve_ref(r, papers_dir=papers_dir, timeout=timeout) for r in refs]
    n_resolved = sum(1 for r in resolutions if r.status == RESOLVED)
    n_unresolved = sum(1 for r in resolutions if r.status == UNRESOLVED)
    n_unreachable = sum(1 for r in resolutions if r.status == UNREACHABLE)
    n_unsupported = sum(1 for r in resolutions if r.status == UNSUPPORTED)
    return {
        "verified": n_resolved >= 1 and n_unresolved == 0 and n_unsupported == 0,
        "n_resolved": n_resolved,
        "n_unresolved": n_unresolved,
        "n_unreachable": n_unreachable,
        "n_unsupported": n_unsupported,
        "resolutions": [r.to_dict() for r in resolutions],
    }
