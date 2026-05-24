"""DockerAuditPillar — base for audit pillars whose tool ships as a container.

Some best-in-class scanners (osv-scanner, trivy) are distributed primarily as
Go binaries / OCI images rather than PyPI wheels. Rather than vendor a binary,
Ophamin runs them from their official image via ``docker run`` and parses the
same structured output. The contract is identical to a local-binary pillar:
``is_available()`` is honest (docker present AND the image pulled), and absence
is reported as ``status="unavailable"`` — never silently skipped.

The target directory is mounted **read-only** at ``/src``; the tool only ever
reads it. No network, no write access to the host tree.
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

from ophamin.auditing.base import AuditPillar, PillarResult


class DockerAuditPillar(AuditPillar):
    """An audit pillar backed by an OCI image run via ``docker run --rm``."""

    #: the OCI image reference, e.g. "ghcr.io/google/osv-scanner:latest"
    image: str = ""
    #: every docker pillar's "binary" is docker itself
    tool_binary = "docker"
    #: where the target is mounted inside the container
    mount_point = "/src"
    #: most scanners need no network; SCA tools (osv-scanner) query an online
    #: advisory DB and set this True. Default-deny keeps the sandbox tight.
    allow_network = False

    def __init__(self) -> None:
        super().__init__()
        if not self.image:
            raise ValueError(
                f"DockerAuditPillar subclass {type(self).__name__} must set `image`"
            )

    def is_available(self) -> bool:  # type: ignore[override]
        """docker on PATH AND the image already pulled (no implicit pull)."""
        if shutil.which("docker") is None:
            return False
        try:
            r = subprocess.run(
                ["docker", "image", "inspect", self.image],
                capture_output=True, timeout=20,
            )
        except (FileNotFoundError, subprocess.TimeoutExpired):
            return False
        return r.returncode == 0

    def tool_version(self, timeout_s: float = 20.0) -> str:
        """Resolve the image's own ``--version`` (best-effort)."""
        try:
            r = subprocess.run(
                ["docker", "run", "--rm", self.image, "--version"],
                capture_output=True, text=True, timeout=timeout_s,
            )
        except (FileNotFoundError, subprocess.TimeoutExpired):
            return ""
        return (r.stdout + r.stderr).strip().split("\n")[0]

    def unavailable_result(self, target_path: str) -> PillarResult:
        return PillarResult(
            pillar_name=self.name,
            tool_name=self.tool_binary,
            tool_version="",
            status="unavailable",
            target_path=str(target_path),
            error_message=(
                f"{self.image} not available: docker missing or image not "
                f"pulled. Run `docker pull {self.image}`."
            ),
        )

    def docker_cmd(self, target: str, args: list[str]) -> list[str]:
        """``docker run --rm [--network=none] -v <target>:/src:ro <image> <args>``."""
        net = [] if self.allow_network else ["--network=none"]
        return [
            "docker", "run", "--rm", *net,
            "-v", f"{target}:{self.mount_point}:ro",
            self.image, *args,
        ]

    def run_docker(
        self, target: str, args: list[str], timeout_s: float,
    ) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            self.docker_cmd(target, args),
            capture_output=True, text=True, timeout=timeout_s,
        )

    @staticmethod
    def host_path(container_path: str, target: str) -> str:
        """Map a ``/src/...`` container path back to the host target tree."""
        mp = "/src/"
        if container_path.startswith(mp):
            return str(Path(target) / container_path[len(mp):])
        if container_path in ("/src", "src"):
            return target
        return container_path
