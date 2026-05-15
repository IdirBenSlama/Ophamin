"""Content-addressed lineage store — the provenance bridge (F pillar).

The blueprint's lineage bridge: every recorded run is cryptographically tied to
the exact substrate revision and configuration that produced it.

This module fuses two layers:

* a **native content-addressed manifest** (``<root>/<run_id>/manifest.json``) —
  the portable, dependency-free lineage record. It carries the config hash, the
  substrate git commit (the ``data_git_commit_id`` end of the bridge), the
  framework commit, and the explicit parent-run chain. ``get_run`` /
  ``list_runs`` / ``lineage_of`` read from these.
* an **MLflow run** logged alongside each manifest — the tracking backend.
  Params, metrics, tags and the manifest/provenance artifacts go to MLflow's
  store under ``<root>/mlruns`` so the standard MLflow UI and APIs work.

Datasets are content-addressed by ``link_dataset`` (the DVC concept, natively);
``dvc_add`` performs a real ``dvc add`` when the project is a DVC repository.
"""

from __future__ import annotations

import hashlib
import json
import subprocess
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import mlflow

from ophamin import __version__


def _canonical_json(obj: Any) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), default=str)


def content_hash(obj: Any) -> str:
    """Stable SHA-256 of any JSON-serialisable object."""
    return hashlib.sha256(_canonical_json(obj).encode("utf-8")).hexdigest()


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def capture_git_commit(repo_path: str | Path) -> str:
    """Return the HEAD commit of a git repo, or ``""`` if not a repo / git absent.

    The absence is *recorded* (the manifest stores ``""`` explicitly) rather than
    silently dropped.
    """
    repo_path = Path(repo_path)
    if not repo_path.exists():
        return ""
    try:
        result = subprocess.run(
            ["git", "-C", str(repo_path), "rev-parse", "HEAD"],
            capture_output=True,
            text=True,
            timeout=10,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return ""
    return result.stdout.strip() if result.returncode == 0 else ""


def _ophamin_project_root() -> Path:
    # .../src/ophamin/comparing/provenance/lineage.py -> project root is parents[4]
    # (after the three-ring reorg, provenance moved one level deeper under
    # comparing/, so the parents index bumped from 3 to 4)
    return Path(__file__).resolve().parents[4]


def make_run_id(config: Any, unique: bool = True) -> str:
    """Build a content-tagged run id from a config.

    With ``unique`` the id is ``<config_hash[:12]>-<epoch_ms>-<rand>``: a content
    tag, a timestamp, and a random token guaranteeing distinctness even for
    back-to-back calls. With ``unique=False`` the id is the bare config hash
    prefix.
    """
    prefix = content_hash(config)[:12]
    if not unique:
        return prefix
    epoch_ms = int(datetime.now(timezone.utc).timestamp() * 1000)
    return f"{prefix}-{epoch_ms}-{uuid.uuid4().hex[:8]}"


def _flatten(obj: Any, prefix: str = "") -> dict[str, Any]:
    """Flatten a nested dict to dotted keys (leaves kept as-is)."""
    out: dict[str, Any] = {}
    if isinstance(obj, dict):
        for k, v in obj.items():
            key = f"{prefix}.{k}" if prefix else str(k)
            out.update(_flatten(v, key))
    else:
        out[prefix] = obj
    return out


@dataclass
class DatasetPointer:
    """A content-addressed pointer to a dataset file or directory."""

    path: str
    content_hash: str
    size_bytes: int
    kind: str  # "file" | "directory"


@dataclass
class RunRecord:
    """A recorded run: its id, on-disk location, and full manifest."""

    run_id: str
    path: Path
    manifest: dict[str, Any] = field(default_factory=dict)

    @property
    def parent_run_id(self) -> str | None:
        return self.manifest.get("parent_run_id")

    @property
    def substrate_git_commit(self) -> str:
        return self.manifest.get("substrate", {}).get("git_commit", "")

    @property
    def config_hash(self) -> str:
        return self.manifest.get("config_hash", "")

    @property
    def mlflow_run_id(self) -> str:
        return self.manifest.get("mlflow_run_id", "")


class LineageStore:
    """Native content-addressed manifests, with MLflow as the tracking backend."""

    def __init__(
        self,
        root: str | Path,
        experiment_name: str = "ophamin",
        enable_mlflow: bool = True,
    ) -> None:
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)
        self.experiment_name = experiment_name
        self.enable_mlflow = bool(enable_mlflow)
        if self.enable_mlflow:
            mlflow.set_tracking_uri(str((self.root / "mlruns").resolve()))
            mlflow.set_experiment(experiment_name)

    # -- datasets -----------------------------------------------------------

    @staticmethod
    def _hash_file(path: Path) -> tuple[str, int]:
        h = hashlib.sha256()
        size = 0
        with open(path, "rb") as fh:
            for chunk in iter(lambda: fh.read(65536), b""):
                h.update(chunk)
                size += len(chunk)
        return h.hexdigest(), size

    def link_dataset(self, path: str | Path) -> DatasetPointer:
        """Content-address a dataset (the DVC concept, natively — no DVC repo needed)."""
        p = Path(path)
        if not p.exists():
            raise FileNotFoundError(f"dataset path does not exist: {p}")
        if p.is_file():
            digest, size = self._hash_file(p)
            return DatasetPointer(str(p), digest, size, "file")
        entries: list[tuple[str, str]] = []
        total = 0
        for f in sorted(p.rglob("*")):
            if f.is_file():
                fh, fs = self._hash_file(f)
                entries.append((str(f.relative_to(p)), fh))
                total += fs
        digest = hashlib.sha256(_canonical_json(entries).encode("utf-8")).hexdigest()
        return DatasetPointer(str(p), digest, total, "directory")

    @staticmethod
    def dvc_add(path: str | Path) -> str:
        """Run a real ``dvc add`` on ``path`` — full DVC cache versioning.

        Requires the project to be a DVC repository (``dvc init``). Returns the
        path of the created ``.dvc`` pointer file. Raises loudly on failure —
        no silent skip.
        """
        p = Path(path)
        if not p.exists():
            raise FileNotFoundError(f"dataset path does not exist: {p}")
        result = subprocess.run(
            ["dvc", "add", str(p)], capture_output=True, text=True, timeout=120
        )
        if result.returncode != 0:
            raise RuntimeError(
                f"dvc add failed (exit {result.returncode}): {result.stderr.strip()}"
            )
        return f"{p}.dvc"

    # -- runs ---------------------------------------------------------------

    def _log_to_mlflow(self, manifest: dict[str, Any]) -> str:
        """Log one run to MLflow; return the MLflow run id."""
        if mlflow.active_run() is not None:
            mlflow.end_run()
        substrate = manifest.get("substrate", {})
        with mlflow.start_run(run_name=manifest["run_id"]) as active:
            mlflow.set_tags(
                {
                    "ophamin.run_id": manifest["run_id"],
                    "ophamin.parent_run_id": manifest.get("parent_run_id") or "",
                    "ophamin.seeing.substrate": substrate.get("name", ""),
                    "ophamin.substrate_git_commit": substrate.get("git_commit", ""),
                    "ophamin.config_hash": manifest["config_hash"],
                    "ophamin.version": manifest["ophamin_version"],
                }
            )
            for key, value in _flatten(manifest.get("config", {})).items():
                mlflow.log_param(key[:250], str(value)[:500])
            for key, value in _flatten(manifest.get("metrics", {})).items():
                if isinstance(value, bool):
                    continue
                if isinstance(value, (int, float)):
                    fv = float(value)
                    if fv == fv and fv not in (float("inf"), float("-inf")):
                        mlflow.log_metric(key[:250], fv)
            mlflow.log_dict(manifest, "ophamin_manifest.json")
            if manifest.get("provenance"):
                mlflow.log_dict(manifest["provenance"], "provenance.json")
            return active.info.run_id

    def record_run(
        self,
        run_id: str,
        config: dict[str, Any],
        sut_metadata: dict[str, Any],
        metrics: dict[str, Any],
        *,
        provenance: Any = None,
        parent_run_id: str | None = None,
        datasets: list[DatasetPointer] | None = None,
        artifacts: dict[str, str] | None = None,
        extra: dict[str, Any] | None = None,
    ) -> RunRecord:
        """Write the native manifest and log the run to MLflow.

        ``sut_metadata`` must carry the substrate's ``git_commit`` — the
        ``data_git_commit_id`` linking these metrics to an exact substrate state.
        """
        run_dir = self.root / run_id
        run_dir.mkdir(parents=True, exist_ok=True)
        manifest: dict[str, Any] = {
            "run_id": run_id,
            "parent_run_id": parent_run_id,
            "created_at": _now_iso(),
            "ophamin_version": __version__,
            "ophamin_git_commit": capture_git_commit(_ophamin_project_root()),
            "substrate": sut_metadata,
            "config": config,
            "config_hash": content_hash(config),
            "metrics": metrics,
            "datasets": [d.__dict__ for d in (datasets or [])],
            "artifacts": artifacts or {},
            "provenance": provenance.to_prov_json() if provenance is not None else None,
        }
        if extra:
            manifest["extra"] = extra
        if self.enable_mlflow:
            manifest["mlflow_run_id"] = self._log_to_mlflow(manifest)
        (run_dir / "manifest.json").write_text(
            json.dumps(manifest, indent=2, default=str), encoding="utf-8"
        )
        return RunRecord(run_id, run_dir, manifest)

    def get_run(self, run_id: str) -> RunRecord:
        manifest_path = self.root / run_id / "manifest.json"
        if not manifest_path.exists():
            raise FileNotFoundError(f"no run '{run_id}' in lineage store {self.root}")
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        return RunRecord(run_id, self.root / run_id, manifest)

    def list_runs(self) -> list[str]:
        if not self.root.exists():
            return []
        return sorted(
            d.name
            for d in self.root.iterdir()
            if d.is_dir()
            and d.name != "mlruns"
            and (d / "manifest.json").exists()
        )

    def lineage_of(self, run_id: str) -> list[RunRecord]:
        """Walk the parent chain, child-first, stopping at the root run."""
        chain: list[RunRecord] = []
        seen: set[str] = set()
        cursor: str | None = run_id
        while cursor and cursor not in seen:
            seen.add(cursor)
            record = self.get_run(cursor)
            chain.append(record)
            cursor = record.parent_run_id
        return chain
