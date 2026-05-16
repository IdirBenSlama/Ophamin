"""KimeraInventory — static enumeration of every observable surface in Kimera-SWM.

Where SchemaMiner asks *what fields does Kimera emit per cycle?*, KimeraInventory
asks *what observable surfaces exist in the Kimera source tree, at this commit?*
The output is a content-addressed, HMAC-signed record listing all primitives,
modules, config files, and infrastructure components Ophamin could observe — by
stratum.

Nine strata mirror the v0.2 reframing
(see ``docs/KIMERA_OBSERVATIONAL_SURFACE_2026_05_15.md``):

  cognitive      — the named primitives Ophamin already targets via KimeraAdapter
  interface      — REST routers, GraphQL schema, MCP tools, CLI commands, WebSocket
  transport      — Piovra L3 transport adapters (TCP/WebSocket/Kafka/...)
  persistence    — PostgreSQL repos, ArangoDB, Redis, vault, multi-level cache
  reconciliation — Layer 4 CRDTs + RIBLT + Bloom
  temporal       — Cronos atomic clock, KCCL phases, oscillators, SPDE engines
  security       — A2A, ed25519, rate-limit, GWF anchors, auth managers
  telemetry      — Prometheus / Grafana / Alertmanager / structured logger
  lifecycle      — encoder snapshot, frozen-on-fall, memory pool, vault sync

Each discoverer is purely static — it reads the Kimera filesystem at the
passed-in path. No Python imports of Kimera, no subprocess. Loud failure on
a missing repo root; per-surface absence is a finding, not a fatal.

Content addressing: the inventory's hash covers (kimera_repo_path,
kimera_git_commit, sorted surfaces). Two runs against the same commit emit
the same hash. The HMAC signature uses the same default key as AuditRecord.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import re
import subprocess
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from ophamin import __version__
from ophamin.comparing.provenance.lineage import (
    _ophamin_project_root,
    capture_git_commit,
)


DEFAULT_SIGN_KEY = b"ophamin-inventory-default-key"
INVENTORY_SCHEMA_VERSION = 1


def _now_utc_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _capture_kimera_commit(kimera_repo: Path) -> str:
    """Best-effort capture of Kimera's HEAD commit. Returns '' if not a git repo."""
    try:
        result = subprocess.run(
            ["git", "-C", str(kimera_repo), "rev-parse", "HEAD"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode == 0:
            return result.stdout.strip()
    except (subprocess.TimeoutExpired, FileNotFoundError):
        pass
    return ""


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Surface:
    """One observable surface — a module file, a config file, a class declaration."""

    name: str                            # short identifier (e.g. "postgres_geoid_repository")
    kind: str                            # "module" | "config_file" | "yaml_rule" | "package_dir" | "class_decl"
    file_path: str                       # path relative to the kimera repo root
    line_count: int                      # source LOC (0 for dirs / unread files)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "kind": self.kind,
            "file_path": self.file_path,
            "line_count": self.line_count,
            "metadata": dict(self.metadata),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Surface:
        required = {"name", "kind", "file_path", "line_count"}
        missing = required - set(data)
        if missing:
            raise ValueError(f"Surface missing required keys: {sorted(missing)}")
        return cls(
            name=str(data["name"]),
            kind=str(data["kind"]),
            file_path=str(data["file_path"]),
            line_count=int(data["line_count"]),
            metadata=dict(data.get("metadata", {})),
        )


@dataclass(frozen=True)
class StratumInventory:
    """One stratum's complete static inventory.

    ``expected_count`` is the lower bound below which the stratum reads as
    "not live in this repo" — useful when probing a partial Kimera checkout.
    """

    stratum: str
    description: str
    surfaces: tuple[Surface, ...]
    expected_count: int

    @property
    def count(self) -> int:
        return len(self.surfaces)

    @property
    def is_live(self) -> bool:
        return self.count >= self.expected_count

    def by_kind(self, kind: str) -> tuple[Surface, ...]:
        return tuple(s for s in self.surfaces if s.kind == kind)

    def to_dict(self) -> dict[str, Any]:
        return {
            "stratum": self.stratum,
            "description": self.description,
            "expected_count": self.expected_count,
            "count": self.count,
            "is_live": self.is_live,
            "surfaces": [s.to_dict() for s in self.surfaces],
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> StratumInventory:
        required = {"stratum", "description", "expected_count", "surfaces"}
        missing = required - set(data)
        if missing:
            raise ValueError(f"StratumInventory missing required keys: {sorted(missing)}")
        return cls(
            stratum=str(data["stratum"]),
            description=str(data["description"]),
            surfaces=tuple(Surface.from_dict(s) for s in data["surfaces"]),
            expected_count=int(data["expected_count"]),
        )


@dataclass(frozen=True)
class KimeraInventory:
    """A complete static inventory of one Kimera commit, signed and content-addressed."""

    ophamin_version: str
    ophamin_git_commit: str
    kimera_repo_path: str
    kimera_git_commit: str
    strata: tuple[StratumInventory, ...]
    captured_at: str = field(default_factory=_now_utc_iso)
    schema_version: int = INVENTORY_SCHEMA_VERSION
    signature: str = ""

    # ------- introspection -------

    def stratum(self, name: str) -> StratumInventory | None:
        for s in self.strata:
            if s.stratum == name:
                return s
        return None

    def total_surfaces(self) -> int:
        return sum(s.count for s in self.strata)

    def live_strata(self) -> tuple[str, ...]:
        return tuple(s.stratum for s in self.strata if s.is_live)

    def dormant_strata(self) -> tuple[str, ...]:
        return tuple(s.stratum for s in self.strata if not s.is_live)

    # ------- serialisation + signing -------

    def _body(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "ophamin_version": self.ophamin_version,
            "ophamin_git_commit": self.ophamin_git_commit,
            "kimera_repo_path": self.kimera_repo_path,
            "kimera_git_commit": self.kimera_git_commit,
            "captured_at": self.captured_at,
            "strata": [s.to_dict() for s in self.strata],
        }

    def _canonical_bytes(self) -> bytes:
        return json.dumps(self._body(), sort_keys=True, separators=(",", ":")).encode("utf-8")

    @property
    def inventory_id(self) -> str:
        return hashlib.sha256(self._canonical_bytes()).hexdigest()

    def sign(self, key: bytes) -> KimeraInventory:
        sig = hmac.new(key, self._canonical_bytes(), hashlib.sha256).hexdigest()
        return KimeraInventory(
            ophamin_version=self.ophamin_version,
            ophamin_git_commit=self.ophamin_git_commit,
            kimera_repo_path=self.kimera_repo_path,
            kimera_git_commit=self.kimera_git_commit,
            strata=self.strata,
            captured_at=self.captured_at,
            schema_version=self.schema_version,
            signature=sig,
        )

    def verify(self, key: bytes) -> bool:
        if not self.signature:
            return False
        expected = hmac.new(key, self._canonical_bytes(), hashlib.sha256).hexdigest()
        return hmac.compare_digest(expected, self.signature)

    def to_dict(self) -> dict[str, Any]:
        return {"inventory_id": self.inventory_id, **self._body(), "signature": self.signature}

    def to_json(self, path: str | None = None, indent: int = 2) -> str:
        text = json.dumps(self.to_dict(), indent=indent, default=str)
        if path:
            Path(path).write_text(text, encoding="utf-8")
        return text

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> KimeraInventory:
        required = {"ophamin_version", "ophamin_git_commit", "kimera_repo_path",
                    "kimera_git_commit", "strata", "captured_at"}
        missing = required - set(data)
        if missing:
            raise ValueError(f"KimeraInventory missing required keys: {sorted(missing)}")
        return cls(
            ophamin_version=str(data["ophamin_version"]),
            ophamin_git_commit=str(data["ophamin_git_commit"]),
            kimera_repo_path=str(data["kimera_repo_path"]),
            kimera_git_commit=str(data["kimera_git_commit"]),
            strata=tuple(StratumInventory.from_dict(s) for s in data["strata"]),
            captured_at=str(data["captured_at"]),
            schema_version=int(data.get("schema_version", INVENTORY_SCHEMA_VERSION)),
            signature=str(data.get("signature", "")),
        )

    def to_markdown(self, target_path: str | None = None) -> str:
        """Human-readable per-stratum inventory report."""
        lines: list[str] = []
        lines.append("# Kimera-SWM Static Inventory\n")
        lines.append(f"**Inventory ID:** `{self.inventory_id}`  ")
        lines.append(f"**Schema:** v{self.schema_version}  ")
        lines.append(f"**Captured:** {self.captured_at}  \n")

        lines.append("## 1. Identity\n")
        lines.append(f"- Ophamin: `{self.ophamin_version}` @ `{self.ophamin_git_commit or '(no commit)'}`")
        lines.append(f"- Kimera repo: `{self.kimera_repo_path}`")
        lines.append(f"- Kimera commit: `{self.kimera_git_commit or '(not a git repo)'}`\n")

        lines.append("## 2. Stratum coverage\n")
        lines.append("| stratum | live? | count | expected | description |")
        lines.append("|---|---|---|---|---|")
        for s in self.strata:
            mark = "[live]" if s.is_live else "[dormant]"
            lines.append(f"| `{s.stratum}` | {mark} | {s.count} | {s.expected_count} | {s.description} |")
        lines.append("")

        lines.append("## 3. Surface enumeration per stratum\n")
        for stratum in self.strata:
            lines.append(f"### `{stratum.stratum}` ({stratum.count} surfaces)\n")
            if not stratum.surfaces:
                lines.append("- _no surfaces detected_\n")
                continue
            lines.append("| name | kind | file_path | LOC |")
            lines.append("|---|---|---|---|")
            for surf in stratum.surfaces:
                # NOTE: do NOT name this loop variable `path` — would shadow
                # any caller variable (avoided here; lesson from
                # auditing.audit_record's 2026-05-15 shadow bug)
                lines.append(
                    f"| `{surf.name}` | {surf.kind} | `{surf.file_path}` | {surf.line_count} |"
                )
            lines.append("")

        lines.append("## 4. Summary\n")
        lines.append(f"- Total surfaces: **{self.total_surfaces()}**")
        lines.append(f"- Live strata: {len(self.live_strata())}/{len(self.strata)} — "
                     f"{', '.join(self.live_strata()) or '_none_'}")
        if self.dormant_strata():
            lines.append(f"- Dormant strata: {', '.join(self.dormant_strata())}\n")

        lines.append(f"## 5. Signature\n- `{self.signature or '(not signed)'}`\n")

        body = "\n".join(lines) + "\n"
        if target_path:
            Path(target_path).write_text(body, encoding="utf-8")
        return body


# ---------------------------------------------------------------------------
# Discovery helpers (file globbing — no Kimera imports)
# ---------------------------------------------------------------------------


def _exists(kimera_repo: Path, rel: str) -> bool:
    return (kimera_repo / rel).exists()


def _line_count(p: Path) -> int:
    """LOC for a Python/YAML/JSON file. 0 if unreadable."""
    try:
        return sum(1 for _ in p.open("r", encoding="utf-8", errors="replace"))
    except (OSError, UnicodeDecodeError):
        return 0


def _list_modules(kimera_repo: Path, rel_dir: str, *, recursive: bool = False) -> list[Path]:
    """Python modules in a directory (excluding ``__init__.py`` and ``__pycache__``)."""
    base = kimera_repo / rel_dir
    if not base.is_dir():
        return []
    pattern = "**/*.py" if recursive else "*.py"
    out: list[Path] = []
    for p in sorted(base.glob(pattern)):
        if p.name == "__init__.py" or "__pycache__" in p.parts:
            continue
        out.append(p)
    return out


def _module_to_surface(repo_root: Path, p: Path, *, kind: str = "module", metadata: dict[str, Any] | None = None) -> Surface:
    rel = p.relative_to(repo_root).as_posix()
    return Surface(
        name=p.stem,
        kind=kind,
        file_path=rel,
        line_count=_line_count(p),
        metadata=metadata or {},
    )


_CLASS_DECL_RE = re.compile(r"^class\s+([A-Z][A-Za-z0-9_]*)\s*[\(:]", re.MULTILINE)


def _scan_classes(p: Path, *, prefix_filter: str | None = None) -> tuple[str, ...]:
    """Top-level class names declared in a Python source file."""
    try:
        text = p.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ()
    names = _CLASS_DECL_RE.findall(text)
    if prefix_filter:
        names = [n for n in names if n.startswith(prefix_filter)]
    return tuple(names)


# ---------------------------------------------------------------------------
# Per-stratum discoverers — each takes the Kimera repo path, returns a
# StratumInventory. Surfaces are sorted deterministically (by file_path) so
# inventory_id is stable across runs against the same commit.
# ---------------------------------------------------------------------------


def discover_cognitive(kimera_repo: Path) -> StratumInventory:
    """Named cognitive primitives Ophamin already targets, plus any *Engine /
    *System / *Protocol / *Walker that matches the named-primitive pattern under
    domain/cognitive/, domain/prime/, domain/linguistic/, domain/semantic/."""

    # The 11 targets the existing KimeraAdapter knows about.
    known_targets = {
        "takwin":     "kimera_swm/domain/cognitive/takwin.py",
        "pentecost":  "kimera_swm/domain/linguistic/one_plus_three_plus_one_enforcer.py",
        "ouroboros":  "kimera_swm/domain/mathematical/ouroboros_kernel.py",
        "rosetta":    "kimera_swm/domain/semantic/rosetta_service.py",
        "rosetta_stele": "kimera_swm/domain/semantic/rosetta_stele.py",
        "arachne":    "kimera_swm/domain/prime/arachne_protocol.py",
        "walker":     "kimera_swm/domain/cognitive/walker.py",
        "gwf":        "kimera_swm/domain/security/gyroscopic_water_fortress",
        "piovra":     "kimera_swm/domain/piovra",
        "atlas":      "kimera_swm/domain/geoid/geoid_1_3_1_enforcement.py",
        "astrolabe":  "kimera_swm/domain/geoid/spherical_5d_geometry.py",
        "spde":       "kimera_swm/infrastructure/temporal/spde_engine.py",
    }
    surfaces: list[Surface] = []
    for name, rel in sorted(known_targets.items()):
        p = kimera_repo / rel
        if p.exists():
            if p.is_file():
                surfaces.append(_module_to_surface(kimera_repo, p,
                    metadata={"target_key": name}))
            else:
                surfaces.append(Surface(
                    name=name, kind="package_dir",
                    file_path=p.relative_to(kimera_repo).as_posix(),
                    line_count=0,
                    metadata={"target_key": name},
                ))

    return StratumInventory(
        stratum="cognitive",
        description="Named cognitive primitives reachable as KimeraAdapter targets",
        surfaces=tuple(sorted(surfaces, key=lambda s: s.file_path)),
        expected_count=8,
    )


def discover_interface(kimera_repo: Path) -> StratumInventory:
    """REST routers, REST controllers, GraphQL surface, MCP tools, CLI commands, WebSocket."""

    surfaces: list[Surface] = []

    # REST routers (FastAPI-style)
    for p in _list_modules(kimera_repo, "kimera_swm/api/routers"):
        surfaces.append(_module_to_surface(kimera_repo, p, metadata={"protocol": "rest", "role": "router"}))
    # REST controllers
    for p in _list_modules(kimera_repo, "kimera_swm/interfaces/rest/controllers"):
        surfaces.append(_module_to_surface(kimera_repo, p, metadata={"protocol": "rest", "role": "controller"}))
    # GraphQL surface
    for sub in ("schema", "resolvers", "federation", "services"):
        rel = f"kimera_swm/interfaces/graphql/{sub}"
        if (kimera_repo / rel).is_dir():
            surfaces.append(Surface(
                name=f"graphql_{sub}", kind="package_dir",
                file_path=rel, line_count=0,
                metadata={"protocol": "graphql", "role": sub},
            ))
    # MCP tool modules
    for p in _list_modules(kimera_repo, "kimera_swm/interfaces/mcp/tools"):
        surfaces.append(_module_to_surface(kimera_repo, p, metadata={"protocol": "mcp", "role": "tool"}))
    # MCP resources
    for p in _list_modules(kimera_repo, "kimera_swm/interfaces/mcp/resources"):
        surfaces.append(_module_to_surface(kimera_repo, p, metadata={"protocol": "mcp", "role": "resource"}))
    # MCP server
    mcp_server = kimera_repo / "kimera_swm/interfaces/mcp/server.py"
    if mcp_server.exists():
        surfaces.append(_module_to_surface(kimera_repo, mcp_server, metadata={"protocol": "mcp", "role": "server"}))
    # CLI commands
    for p in _list_modules(kimera_repo, "kimera_swm/interfaces/cli/commands"):
        surfaces.append(_module_to_surface(kimera_repo, p, metadata={"protocol": "cli", "role": "command"}))
    # WebSocket
    for p in _list_modules(kimera_repo, "kimera_swm/interfaces/websocket"):
        surfaces.append(_module_to_surface(kimera_repo, p, metadata={"protocol": "websocket"}))

    return StratumInventory(
        stratum="interface",
        description="REST routers + controllers, GraphQL surface, MCP tools, CLI commands, WebSocket handlers",
        surfaces=tuple(sorted(surfaces, key=lambda s: s.file_path)),
        expected_count=20,
    )


def discover_transport(kimera_repo: Path) -> StratumInventory:
    """Piovra L3 transport adapters."""

    surfaces: list[Surface] = []
    for p in _list_modules(kimera_repo, "kimera_swm/domain/piovra/transports"):
        surfaces.append(_module_to_surface(kimera_repo, p, metadata={"layer": "L3"}))
    return StratumInventory(
        stratum="transport",
        description="Piovra L3 transport adapters wrapping ArchipelPeerRouter",
        surfaces=tuple(sorted(surfaces, key=lambda s: s.file_path)),
        expected_count=4,
    )


def discover_persistence(kimera_repo: Path) -> StratumInventory:
    """PostgreSQL repositories, ArangoDB, Redis, vault repo, persistence layer, schemas."""

    surfaces: list[Surface] = []
    # PostgreSQL per-domain repositories
    for p in _list_modules(kimera_repo, "kimera_swm/infrastructure/database"):
        meta = {"backend": "unknown"}
        n = p.stem
        if n.startswith("postgres_") or n.startswith("postgresql_"):
            meta["backend"] = "postgres"
        elif n.startswith("arango"):
            meta["backend"] = "arangodb"
        elif n.startswith("redis"):
            meta["backend"] = "redis"
        elif "cache" in n:
            meta["backend"] = "cache"
        elif "migration" in n or "schema" in n:
            meta["backend"] = "schema_mgmt"
        elif "transaction" in n:
            meta["backend"] = "transaction"
        surfaces.append(_module_to_surface(kimera_repo, p, metadata=meta))
    # Persistence wheel
    for p in _list_modules(kimera_repo, "kimera_swm/infrastructure/persistence"):
        surfaces.append(_module_to_surface(kimera_repo, p, metadata={"backend": "persistence_layer"}))
    # Vault infrastructure
    for p in _list_modules(kimera_repo, "kimera_swm/infrastructure/vault"):
        surfaces.append(_module_to_surface(kimera_repo, p, metadata={"backend": "vault"}))
    # SQL + schema files
    sql_files = list((kimera_repo / "kimera_swm/infrastructure/database").glob("*.sql")) if \
        (kimera_repo / "kimera_swm/infrastructure/database").is_dir() else []
    for p in sorted(sql_files):
        surfaces.append(Surface(
            name=p.stem, kind="config_file",
            file_path=p.relative_to(kimera_repo).as_posix(),
            line_count=_line_count(p),
            metadata={"backend": "schema_sql", "format": "sql"},
        ))

    return StratumInventory(
        stratum="persistence",
        description="PostgreSQL per-domain repos, ArangoDB, Redis, multi-level cache, vault, persistence layer",
        surfaces=tuple(sorted(surfaces, key=lambda s: s.file_path)),
        expected_count=15,
    )


def discover_reconciliation(kimera_repo: Path) -> StratumInventory:
    """Layer 4 CRDTs + RIBLT + Bloom + offline reconnect."""

    surfaces: list[Surface] = []
    for p in _list_modules(kimera_repo, "kimera_swm/infrastructure/reconciliation"):
        # Tag each by CRDT family from its file name.
        n = p.stem
        if n.endswith("_iblt") or "iblt" in n:
            family = "riblt"
        elif "bloom" in n:
            family = "bloom"
        elif "dag" in n:
            family = "dag_crdt"
        elif "chain" in n:
            family = "chain_crdt"
        elif "g_set" in n:
            family = "set_crdt"
        elif "reconnect" in n:
            family = "reconnect_protocol"
        else:
            family = "other"
        surfaces.append(_module_to_surface(kimera_repo, p, metadata={"family": family}))
    return StratumInventory(
        stratum="reconciliation",
        description="Layer 4 CRDTs (G-Set, SCAR-DAG, Echoform-chain) + RIBLT + Bloom pre-flight + offline reconnect",
        surfaces=tuple(sorted(surfaces, key=lambda s: s.file_path)),
        expected_count=5,
    )


def discover_temporal(kimera_repo: Path) -> StratumInventory:
    """Cronos atomic clock + KCCL system + oscillators + SPDE engines."""

    surfaces: list[Surface] = []
    for p in _list_modules(kimera_repo, "kimera_swm/infrastructure/temporal/cronos"):
        surfaces.append(_module_to_surface(kimera_repo, p, metadata={"family": "cronos"}))
    for p in _list_modules(kimera_repo, "kimera_swm/infrastructure/temporal"):
        # Skip cronos subdir entries (already included)
        if "cronos/" in p.relative_to(kimera_repo).as_posix():
            continue
        n = p.stem
        if "kccl" in n:
            family = "kccl"
        elif "oscillator" in n:
            family = "oscillator"
        elif "spde" in n:
            family = "spde"
        elif "rhythm" in n:
            family = "rhythm"
        else:
            family = "other"
        surfaces.append(_module_to_surface(kimera_repo, p, metadata={"family": family}))
    return StratumInventory(
        stratum="temporal",
        description="Cronos atomic clock (6 layers), KCCL system, oscillator registry, SPDE engine variants",
        surfaces=tuple(sorted(surfaces, key=lambda s: s.file_path)),
        expected_count=10,
    )


def discover_security(kimera_repo: Path) -> StratumInventory:
    """A2A protocol, ed25519/HMAC signing, rate-limit, GWF anchors, auth managers."""

    surfaces: list[Surface] = []
    # A2A protocol
    for p in _list_modules(kimera_repo, "kimera_swm/domain/autonomous/a2a"):
        surfaces.append(_module_to_surface(kimera_repo, p,
            metadata={"family": "a2a", "primitive": p.stem}))
    # Infrastructure security
    for p in _list_modules(kimera_repo, "kimera_swm/infrastructure/security"):
        n = p.stem
        if "ed25519" in n:
            family = "pki"
        elif "encryption" in n:
            family = "encryption"
        elif "rate_limit" in n:
            family = "rate_limit"
        elif "secret" in n:
            family = "secret_mgmt"
        elif "auth" in n:
            family = "auth"
        elif "attestation" in n:
            family = "attestation"
        elif "vulnerability" in n:
            family = "vuln_mgmt"
        else:
            family = "other"
        surfaces.append(_module_to_surface(kimera_repo, p, metadata={"family": family, "layer": "infra"}))
    # Domain security (excluding obvious model/exception files)
    for p in _list_modules(kimera_repo, "kimera_swm/domain/security"):
        n = p.stem
        if n.endswith("_models") or n.endswith("_exceptions") or n == "interfaces":
            continue
        family = "domain_security"
        if "encryption" in n:
            family = "encryption"
        elif "auth" in n:
            family = "auth"
        elif "manipulation" in n:
            family = "manipulation_detection"
        elif "instability" in n or "divergence" in n:
            family = "stability_check"
        surfaces.append(_module_to_surface(kimera_repo, p, metadata={"family": family, "layer": "domain"}))
    # GWF (Gyroscopic Water Fortress) subpackage
    gwf_dir = kimera_repo / "kimera_swm/domain/security/gyroscopic_water_fortress"
    if gwf_dir.is_dir():
        for p in _list_modules(kimera_repo, "kimera_swm/domain/security/gyroscopic_water_fortress"):
            surfaces.append(_module_to_surface(kimera_repo, p, metadata={"family": "gwf", "layer": "domain"}))

    return StratumInventory(
        stratum="security",
        description="A2A protocol, ed25519/HMAC, rate limiting, GWF anchors, encryption, auth managers",
        surfaces=tuple(sorted(surfaces, key=lambda s: s.file_path)),
        expected_count=15,
    )


def discover_telemetry(kimera_repo: Path) -> StratumInventory:
    """Prometheus + Grafana + Alertmanager stack, structured loggers, distributed tracer."""

    surfaces: list[Surface] = []

    # Monitoring Python modules
    for p in _list_modules(kimera_repo, "kimera_swm/infrastructure/monitoring"):
        n = p.stem
        if "prometheus" in n:
            family = "prometheus"
        elif "grafana" in n:
            family = "grafana"
        elif "alert" in n:
            family = "alerting"
        elif "tracer" in n or "tracing" in n:
            family = "tracing"
        elif "log" in n:
            family = "logging"
        elif "health" in n:
            family = "health_check"
        elif "homeostasis" in n:
            family = "homeostasis"
        elif "dashboard" in n:
            family = "dashboard"
        else:
            family = "monitoring_general"
        surfaces.append(_module_to_surface(kimera_repo, p, metadata={"family": family}))

    # Observability subpackage (parallel to monitoring/)
    for p in _list_modules(kimera_repo, "kimera_swm/infrastructure/observability"):
        n = p.stem
        if "alert" in n:
            family = "alerting"
        elif "tracing" in n or "tracer" in n:
            family = "tracing"
        elif "health" in n:
            family = "health_check"
        elif "dashboard" in n:
            family = "dashboard"
        else:
            family = "observability_general"
        surfaces.append(_module_to_surface(kimera_repo, p, metadata={"family": family}))

    # Config files (the load-bearing ones)
    config_artefacts = {
        "prometheus_config":      ("kimera_swm/infrastructure/monitoring/prometheus_config.yml", "yaml_config"),
        "alert_rules":            ("kimera_swm/infrastructure/monitoring/alert_rules.yml",        "yaml_rule"),
        "kimera_alerts":          ("kimera_swm/infrastructure/monitoring/kimera_alerts.yml",      "yaml_rule"),
        "alertmanager_config":    ("kimera_swm/infrastructure/monitoring/alertmanager.yml",       "yaml_config"),
        "grafana_dashboard_json": ("kimera_swm/infrastructure/monitoring/grafana_dashboard.json", "json_config"),
        "monitoring_compose":     ("kimera_swm/infrastructure/monitoring/docker-compose.monitoring.yml", "yaml_config"),
    }
    for name, (rel, kind) in sorted(config_artefacts.items()):
        p = kimera_repo / rel
        if p.exists():
            surfaces.append(Surface(
                name=name, kind=kind, file_path=rel, line_count=_line_count(p),
                metadata={"family": "config_artifact"},
            ))

    return StratumInventory(
        stratum="telemetry",
        description="Prometheus exporter + Grafana dashboards + Alertmanager + structured loggers + tracers",
        surfaces=tuple(sorted(surfaces, key=lambda s: s.file_path)),
        expected_count=20,
    )


def discover_lifecycle(kimera_repo: Path) -> StratumInventory:
    """Encoder snapshot lifecycle, frozen-on-fall persistence, memory + vault sync."""

    surfaces: list[Surface] = []
    for p in _list_modules(kimera_repo, "kimera_swm/infrastructure/encoder_snapshot"):
        surfaces.append(_module_to_surface(kimera_repo, p, metadata={"family": "encoder_snapshot"}))
    for p in _list_modules(kimera_repo, "kimera_swm/infrastructure/frozen_on_fall"):
        surfaces.append(_module_to_surface(kimera_repo, p, metadata={"family": "frozen_on_fall"}))
    for p in _list_modules(kimera_repo, "kimera_swm/infrastructure/memory"):
        n = p.stem
        if "leak" in n:
            family = "leak_detection"
        elif "gc" in n:
            family = "gc"
        elif "pool" in n:
            family = "memory_pool"
        elif "analytics" in n:
            family = "analytics"
        elif "monitor" in n:
            family = "monitoring"
        elif "manager" in n:
            family = "manager"
        elif "holographic" in n:
            family = "holographic"
        elif "maxwell" in n:
            family = "maxwell_demon"
        else:
            family = "memory_other"
        surfaces.append(_module_to_surface(kimera_repo, p, metadata={"family": family}))
    return StratumInventory(
        stratum="lifecycle",
        description="Encoder snapshot lifecycle, frozen-on-fall persistence, memory pool + GC + leak detection",
        surfaces=tuple(sorted(surfaces, key=lambda s: s.file_path)),
        expected_count=10,
    )


# ---------------------------------------------------------------------------
# Aggregator
# ---------------------------------------------------------------------------


STRATA_DISCOVERERS: dict[str, Callable[[Path], StratumInventory]] = {
    "cognitive":      discover_cognitive,
    "interface":      discover_interface,
    "transport":      discover_transport,
    "persistence":    discover_persistence,
    "reconciliation": discover_reconciliation,
    "temporal":       discover_temporal,
    "security":       discover_security,
    "telemetry":      discover_telemetry,
    "lifecycle":      discover_lifecycle,
}


def discover_all(
    kimera_repo: str | Path,
    *,
    strata: tuple[str, ...] | None = None,
    sign_key: bytes = DEFAULT_SIGN_KEY,
) -> KimeraInventory:
    """Run every stratum's discoverer against a Kimera repo, return a signed inventory.

    Loud failure on missing repo. ``strata`` defaults to all nine — pass a
    subset (e.g. ``("interface", "transport")``) to skip the others.
    """
    repo = Path(kimera_repo).expanduser().resolve()
    if not repo.is_dir():
        raise FileNotFoundError(f"Kimera repo not a directory: {repo}")
    requested = tuple(strata) if strata is not None else tuple(STRATA_DISCOVERERS)
    unknown = set(requested) - set(STRATA_DISCOVERERS)
    if unknown:
        raise ValueError(f"Unknown strata: {sorted(unknown)}; "
                         f"valid: {sorted(STRATA_DISCOVERERS)}")

    out: list[StratumInventory] = []
    for stratum in requested:
        out.append(STRATA_DISCOVERERS[stratum](repo))

    inv = KimeraInventory(
        ophamin_version=__version__,
        ophamin_git_commit=capture_git_commit(_ophamin_project_root()) or "",
        kimera_repo_path=str(repo),
        kimera_git_commit=_capture_kimera_commit(repo),
        strata=tuple(out),
    )
    return inv.sign(sign_key)
