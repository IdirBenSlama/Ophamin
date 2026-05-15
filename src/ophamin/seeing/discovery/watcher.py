"""Many-small-eyes mode — Layer A in continuous-observation shape.

The observatory's discovery layer can run on demand (``ophamin discover``) or
continuously. Continuous mode polls the Kimera repository's git HEAD on a
short interval; when HEAD changes, it auto-runs:

  1. ``SchemaMiner.mine``                    fresh field-schema for the new commit
  2. ``write_schema_markdown``               human-readable reference doc
  3. ``diff_schemas`` (vs. previous schema)  what fields changed
  4. ``ophamin drift-report``                cross-commit behavioural drift
                                              over any signed proof records

The output is a dated artefact directory per Kimera commit. Re-running on the
same commit is a no-op (idempotent by content hash).

This is the dyson-sphere posture: keep watching, capture every emission. It's
not a substitute for pre-registered scenarios — it's the always-on layer
that catches Kimera evolutions between scheduled runs.
"""

from __future__ import annotations

import subprocess
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from ophamin.seeing.discovery.schema_diff import diff_schemas
from ophamin.seeing.discovery.schema_document import SchemaDocument
from ophamin.seeing.discovery.schema_miner import SchemaMiner
from ophamin.seeing.discovery.schema_writer import write_schema_markdown
from ophamin.seeing.substrate import KimeraAdapter

DEFAULT_POLL_INTERVAL_S = 30.0


def kimera_head_commit(repo: str | Path) -> str:
    """Read the Kimera repository's current HEAD commit (or empty string)."""
    try:
        result = subprocess.run(
            ["git", "-C", str(repo), "rev-parse", "HEAD"],
            capture_output=True,
            text=True,
            timeout=10,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return ""
    if result.returncode != 0:
        return ""
    return result.stdout.strip()


@dataclass
class WatchOutcome:
    """One iteration of the watcher's outer loop — what happened this tick."""

    kimera_commit: str
    schema_json_path: Path | None
    schema_md_path: Path | None
    diff_md_path: Path | None
    drift_path: Path | None
    new_commit_discovered: bool
    reason: str  # plain-words reason for what was/wasn't done this tick


class KimeraDiscoveryWatcher:
    """Loop that runs discovery + drift on every new Kimera HEAD.

    ``run_once`` executes one tick — read HEAD, decide whether to mine, mine
    if needed, return an outcome. ``run_forever`` calls ``run_once`` on a
    fixed interval until interrupted. Both can be invoked from the CLI or
    library code.
    """

    def __init__(
        self,
        kimera_repo: str | Path,
        *,
        targets: list[str],
        stimuli: list[str],
        out_dir: str | Path = "discovery",
        proofs_dir: str | Path = "proofs",
        batch_timeout: float = 600.0,
        head_reader: Callable[[str | Path], str] = kimera_head_commit,
    ) -> None:
        if not targets:
            raise ValueError("KimeraDiscoveryWatcher requires at least one target")
        if not stimuli:
            raise ValueError("KimeraDiscoveryWatcher requires at least one stimulus")
        self.kimera_repo = str(kimera_repo)
        self.targets = list(targets)
        self.stimuli = list(stimuli)
        self.out_dir = Path(out_dir)
        self.proofs_dir = Path(proofs_dir)
        self.batch_timeout = float(batch_timeout)
        self._head_reader = head_reader
        self._last_mined_commit: str | None = None

    def _previous_schema_path(self, current_commit: str) -> Path | None:
        """Return the most recent schema document NOT matching the current commit."""
        if not self.out_dir.is_dir():
            return None
        candidates = sorted(
            (
                path
                for path in self.out_dir.glob("kimera_fields_*.json")
                if current_commit[:12] not in path.name
            ),
            key=lambda p: p.stat().st_mtime,
            reverse=True,
        )
        return candidates[0] if candidates else None

    def run_once(self) -> WatchOutcome:
        """One tick of the outer loop. Mines + diffs + drift-reports if HEAD
        is a commit we haven't yet seen; otherwise returns a no-op outcome."""
        commit = self._head_reader(self.kimera_repo)
        if not commit:
            return WatchOutcome(
                kimera_commit="",
                schema_json_path=None,
                schema_md_path=None,
                diff_md_path=None,
                drift_path=None,
                new_commit_discovered=False,
                reason="kimera repo HEAD unreadable (not a git repo or git unavailable)",
            )
        if commit == self._last_mined_commit:
            return WatchOutcome(
                kimera_commit=commit,
                schema_json_path=None,
                schema_md_path=None,
                diff_md_path=None,
                drift_path=None,
                new_commit_discovered=False,
                reason=f"HEAD unchanged at {commit[:12]} since last tick",
            )

        # mine the fresh schema
        substrate = KimeraAdapter(
            self.kimera_repo,
            target=self.targets[0],
            mode="batch",
            batch_timeout=self.batch_timeout,
        )
        miner = SchemaMiner(substrate)
        doc = miner.mine(targets=self.targets, stimuli=self.stimuli)
        self.out_dir.mkdir(parents=True, exist_ok=True)
        short = commit[:12]
        schema_json = self.out_dir / f"kimera_fields_{short}.json"
        schema_md = self.out_dir / f"kimera_fields_{short}.md"
        doc.to_json(schema_json)
        write_schema_markdown(doc, schema_md)

        # diff against the most-recent prior schema (if any)
        diff_md: Path | None = None
        previous = self._previous_schema_path(commit)
        if previous is not None:
            prev_doc = SchemaDocument.from_json(previous)
            diff = diff_schemas(prev_doc, doc)
            diff_md = self.out_dir / f"diff_{previous.stem.replace('kimera_fields_', '')}_to_{short}.md"
            self._write_diff_markdown(diff, diff_md, prev_doc, doc)

        # drift report over proof records (Layer C output, scoped to this commit)
        drift_path: Path | None = None
        if self.proofs_dir.is_dir():
            drift_path = self._write_drift_report(commit)

        self._last_mined_commit = commit
        return WatchOutcome(
            kimera_commit=commit,
            schema_json_path=schema_json,
            schema_md_path=schema_md,
            diff_md_path=diff_md,
            drift_path=drift_path,
            new_commit_discovered=True,
            reason=f"mined fresh schema for {short}",
        )

    def run_forever(
        self,
        *,
        poll_interval_s: float = DEFAULT_POLL_INTERVAL_S,
        on_outcome: Callable[[WatchOutcome], None] | None = None,
    ) -> None:
        """Run the outer loop indefinitely. Caller interrupts via Ctrl-C."""
        if poll_interval_s <= 0:
            raise ValueError(f"poll_interval_s must be > 0, got {poll_interval_s}")
        try:
            while True:
                outcome = self.run_once()
                if on_outcome is not None:
                    on_outcome(outcome)
                time.sleep(poll_interval_s)
        except KeyboardInterrupt:
            return

    @staticmethod
    def _write_diff_markdown(
        diff, path: Path, before: SchemaDocument, after: SchemaDocument
    ) -> None:
        """Render the structural diff as a small Markdown report."""
        lines = [
            "# Kimera field-schema diff\n",
            "_Auto-generated by Ophamin's many-small-eyes watcher._\n\n",
            "## Provenance\n",
            f"- before kimera commit: `{before.kimera_git_commit}` ({before.captured_at})\n",
            f"- after  kimera commit: `{after.kimera_git_commit}` ({after.captured_at})\n",
            f"- structural changes : {len(diff.field_changes)}\n",
            f"- targets added      : {', '.join(diff.targets_added) or '—'}\n",
            f"- targets removed    : {', '.join(diff.targets_removed) or '—'}\n\n",
        ]
        if diff.is_empty():
            lines.append("**No structural changes between the two schemas.**\n")
        else:
            lines.append("## Field changes\n\n")
            lines.append("| kind | target | path | before | after |\n")
            lines.append("|---|---|---|---|---|\n")
            for c in diff.field_changes:
                before_types = ", ".join(c.types_before) or "—"
                after_types = ", ".join(c.types_after) or "—"
                lines.append(
                    f"| {c.kind} | {c.target} | `{c.path}` | "
                    f"{before_types} | {after_types} |\n"
                )
        path.write_text("".join(lines))

    def _write_drift_report(self, commit: str) -> Path:
        """Snapshot the current drift-report state into a dated file."""
        # late import to avoid a circular import between comparing and seeing layers
        from ophamin.comparing.drift import ProofIndex, detect_drift

        import json

        index = ProofIndex.from_directory(self.proofs_dir)
        report = detect_drift(index)
        path = self.out_dir / f"drift_at_{commit[:12]}.json"
        path.write_text(json.dumps(report, indent=2, default=str))
        return path
