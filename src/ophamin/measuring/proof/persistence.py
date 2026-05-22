"""Persist signed proof records into a self-describing bundle directory.

The legacy convention was to write ``<scenario>_<hash>.json`` (and
sometimes a ``.md`` sibling) into ``proofs/`` root or a per-tier
subdir. Filenames carried no scenario name + date + verdict, so an
``ls`` told the operator nothing — they had to open each file.

The 0.59.0 convention writes a *bundle directory* per proof::

    proofs/<tier>/<scenario-name>/<YYYY-MM-DD>_<verdict>_<short-hash>/
    ├── proof.json   ← signed source of truth (unchanged bytes)
    ├── proof.md     ← markdown render
    ├── proof.html   ← HTML render
    ├── proof.tex    ← LaTeX source
    └── proof.pdf    ← compiled PDF (requires latexmk / pdflatex)

The bundle dir name carries the date + verdict + short hash; ``ls
proofs/<tier>/<scenario>/`` immediately tells the operator what ran
when, with what outcome.

Filename collisions are content-addressed: the short hash is the
first 12 chars of ``proof.proof_id``. Two proofs with the same
hash are by construction the same proof (HMAC over the same
canonical body), so re-running ``persist_proof`` on the same
signed record is idempotent — it overwrites the bundle with
identical bytes.

Format selection lives in :class:`BundleFormat` — pass any subset
to ``persist_proof(formats=...)`` to skip formats the caller can't
or doesn't want to emit (e.g. PDF on a machine without LaTeX).
``BundleFormat.ALL`` is the default and emits all five.
"""

from __future__ import annotations

import enum
import json
import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from ophamin.measuring.proof.record import EmpiricalProofRecord


#: Maps the proof's verdict outcome to the filesystem-safe lowercase
#: variant used in the bundle directory name. ``Verdict.outcome``
#: today is one of {VALIDATED, REFUTED, INCONCLUSIVE} per the
#: enum at record.py:42-44.
_VERDICT_DIR_SLUG: dict[str, str] = {
    "VALIDATED": "validated",
    "REFUTED": "refuted",
    "INCONCLUSIVE": "inconclusive",
}


class BundleFormat(str, enum.Enum):
    """The set of files :func:`persist_proof` can write into a bundle dir.

    ``ALL`` is the default. Subsets are useful when the caller wants
    to skip PDF on a machine without TeX, or wants JSON-only for
    fast-emission scenarios that render later via ``ophamin report``.
    """

    JSON = "json"
    MARKDOWN = "markdown"
    HTML = "html"
    LATEX = "latex"
    PDF = "pdf"

    @classmethod
    def all(cls) -> frozenset["BundleFormat"]:
        return frozenset({cls.JSON, cls.MARKDOWN, cls.HTML, cls.LATEX, cls.PDF})

    @classmethod
    def json_only(cls) -> frozenset["BundleFormat"]:
        return frozenset({cls.JSON})


@dataclass(frozen=True)
class PersistedBundle:
    """The result of writing a proof bundle to disk.

    Lets callers branch on which formats actually got written —
    useful when one renderer's loud-failure is expected (e.g. PDF
    on a machine that *should* have LaTeX but the operator misconfigured).
    """

    bundle_dir: Path
    written: dict[BundleFormat, Path]
    skipped: dict[BundleFormat, str]  # format → reason string

    @property
    def proof_json(self) -> Path:
        """The signed JSON source of truth — always present."""
        return self.written[BundleFormat.JSON]


_SAFE_NAME_RE = re.compile(r"[^a-z0-9_-]")


def _sanitize_scenario_name(name: str) -> str:
    """Make a scenario name filesystem-safe + canonical.

    Scenarios are kebab-case by convention (the ``Scenario.name``
    field). Lowercase + strip anything that isn't alphanumeric +
    underscore + hyphen so a name like ``sonarqube-scan`` lands as
    ``sonarqube-scan`` and an unconventional ``Scenario_X.1`` lands
    as ``scenario_x1``.
    """
    if not name:
        return "unknown-scenario"
    return _SAFE_NAME_RE.sub("", name.lower()) or "unknown-scenario"


def _extract_date(record: EmpiricalProofRecord) -> str:
    """Pull the YYYY-MM-DD prefix from the record's ``created_at``.

    Loud-fails on a malformed timestamp — the caller's record came
    from a tampered source if this raises.
    """
    created = record.created_at
    if not created or len(created) < 10:
        raise ValueError(
            f"record.created_at is too short to parse as date: {created!r}"
        )
    date_part = created[:10]
    if not re.match(r"^\d{4}-\d{2}-\d{2}$", date_part):
        raise ValueError(
            f"record.created_at does not start with YYYY-MM-DD: {created!r}"
        )
    return date_part


def _verdict_slug(record: EmpiricalProofRecord) -> str:
    outcome = record.verdict.outcome
    return _VERDICT_DIR_SLUG.get(outcome, outcome.lower())


def bundle_dir_for(
    record: EmpiricalProofRecord,
    *,
    root: Path,
    tier: str,
    scenario_name: str,
) -> Path:
    """Compute the canonical bundle path for a signed record.

    Pure: does not create the directory. Exposed for inspection +
    tests + the migration script.

    Path shape: ``<root>/<tier>/<scenario>/<YYYY-MM-DD>_<verdict>_<short>/``
    where ``<short>`` is the first 12 hex chars of ``record.proof_id``.
    """
    if not record.proof_id:
        raise ValueError("record.proof_id is empty — record must be signed before persist")
    tier_safe = _sanitize_scenario_name(tier) or "unknown-tier"
    scenario_safe = _sanitize_scenario_name(scenario_name) or "unknown-scenario"
    date = _extract_date(record)
    verdict = _verdict_slug(record)
    short = record.proof_id[:12]
    bundle_name = f"{date}_{verdict}_{short}"
    return Path(root) / tier_safe / scenario_safe / bundle_name


def persist_proof(
    record: EmpiricalProofRecord,
    *,
    root: Path,
    tier: str,
    scenario_name: str,
    formats: Iterable[BundleFormat] | None = None,
) -> PersistedBundle:
    """Write the proof into a self-describing bundle directory.

    Parameters
    ----------
    record:
        The signed ``EmpiricalProofRecord``. Must have a non-empty
        ``signature`` (caller is responsible for ``record.sign(key)``).
    root:
        The base ``proofs/`` directory. Created if missing.
    tier:
        The scenario's :class:`~ophamin.measuring.scenarios.base.Tier`
        value (string form — ``"scientific"`` / ``"engineering"`` /
        etc.) — used to partition the tree.
    scenario_name:
        ``Scenario.name`` (kebab-case CLI identifier).
    formats:
        Subset of :class:`BundleFormat` to emit. Defaults to
        :meth:`BundleFormat.all`. Pass :meth:`BundleFormat.json_only`
        for fast-emission scenarios that re-render later via
        ``ophamin report``.

    Returns
    -------
    PersistedBundle
        Carries the bundle dir + per-format written paths + per-format
        skip reasons (e.g. ``"toolchain missing"`` for PDF when
        latexmk is absent — that case is loud-warned via the
        returned ``skipped`` dict, not silently swallowed).
    """
    if not record.signature:
        raise ValueError(
            "record.signature is empty — call record.sign(key) before persist_proof"
        )

    # --- author attestation (CR2, opt-in) ---
    # If the operator declared an identity via OPHAMIN_AUTHOR, attest the proof
    # with their ed25519 key (loaded/created from the keystore) before writing.
    # This adds real, publicly-verifiable authorship on top of the shared-key
    # HMAC integrity seal. No author configured -> un-attested (backward
    # compatible). Attestation lives outside the body, so proof_id / bundle dir
    # are unchanged. Keystore errors fail loud — never a silent skip.
    if not record.attestation:
        author = os.environ.get("OPHAMIN_AUTHOR", "").strip()
        if author:
            from ophamin.measuring.proof.attestation import (
                load_or_create_author_key,
            )

            key = load_or_create_author_key(author)
            record.attest(key.private_key, author, public_key=key.public_key)

    formats_set: frozenset[BundleFormat]
    if formats is None:
        formats_set = BundleFormat.all()
    else:
        formats_set = frozenset(formats)
    if not formats_set:
        raise ValueError("formats set is empty — pass at least one BundleFormat")
    if BundleFormat.JSON not in formats_set:
        # JSON is the signed source of truth — refusing to write it
        # would silently strip the only tamper-evident artifact.
        raise ValueError(
            "BundleFormat.JSON is mandatory; remove it only by writing "
            "elsewhere — never persist a bundle without the signed JSON."
        )

    bundle = bundle_dir_for(
        record, root=root, tier=tier, scenario_name=scenario_name,
    )
    bundle.mkdir(parents=True, exist_ok=True)

    written: dict[BundleFormat, Path] = {}
    skipped: dict[BundleFormat, str] = {}

    # --- JSON (always) ---
    json_path = bundle / "proof.json"
    json_path.write_text(json.dumps(record.to_dict(), indent=2), encoding="utf-8")
    written[BundleFormat.JSON] = json_path

    # The non-JSON renderers all consume the record dict — load once.
    record_dict = record.to_dict()

    if BundleFormat.MARKDOWN in formats_set:
        from ophamin.reporting.markdown_renderer import MarkdownReporter
        out = bundle / "proof.md"
        MarkdownReporter().render_proof(record_dict, out)
        written[BundleFormat.MARKDOWN] = out

    if BundleFormat.HTML in formats_set:
        from ophamin.reporting.html_renderer import HTMLReporter
        out = bundle / "proof.html"
        HTMLReporter().render_proof(record_dict, out)
        written[BundleFormat.HTML] = out

    if BundleFormat.LATEX in formats_set:
        from ophamin.reporting.latex_renderer import LaTeXReporter
        out = bundle / "proof.tex"
        LaTeXReporter().render_proof(record_dict, out)
        written[BundleFormat.LATEX] = out

    if BundleFormat.PDF in formats_set:
        # PDFReporter is loud-fail at construction when TeX is missing.
        # We catch ONLY that one typed error and record it in `skipped`
        # — every other render error propagates.
        try:
            from ophamin.reporting.pdf_renderer import (
                PDFReporter,
                PDFToolchainMissingError,
            )
        except ImportError as exc:  # PDFReporter module fails to import (unlikely)
            skipped[BundleFormat.PDF] = f"import error: {exc}"
        else:
            try:
                reporter = PDFReporter()
            except PDFToolchainMissingError as exc:
                skipped[BundleFormat.PDF] = str(exc)
            else:
                out = bundle / "proof.pdf"
                reporter.render_proof(record_dict, out)
                written[BundleFormat.PDF] = out

    return PersistedBundle(bundle_dir=bundle, written=written, skipped=skipped)
