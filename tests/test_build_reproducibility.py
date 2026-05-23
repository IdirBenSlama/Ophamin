"""Build reproducibility pin (RFC 0002 Phase E4 sub-task).

Verifies that ``python -m build`` produces reproducible artefacts when
``SOURCE_DATE_EPOCH`` is set. Two layers of guarantee:

1. **Wheel byte-equivalence** — two independent invocations with the
   same ``SOURCE_DATE_EPOCH`` MUST emit byte-identical wheels (SHA-256
   match). Wheels are zip archives; Python's zip writer + setuptools'
   wheel builder both honour ``SOURCE_DATE_EPOCH`` cleanly.

2. **Sdist content-equivalence** — two independent invocations MUST
   produce ``.tar.gz`` files whose **extracted contents** are identical
   even if the gzip header's mtime drifts between runs (this is a
   known limitation of setuptools' sdist builder under
   ``SOURCE_DATE_EPOCH`` for some setuptools/Python combinations).
   The tar **content** must be identical; the gzip wrapper may not be.

The test skips itself if ``build`` is not installed (it's in the
``[release]`` extra, not the default install).

Reference: RFC 0002 §3.1 Phase E4 ("Diffoscope-clean builds —
diffoscope should report zero meaningful diffs between two
independent builds of the same commit."). This is the project's
local-only proxy for the cross-machine diffoscope claim; the
cross-machine version requires the external reviewer rebuild
documented in RFC 0002 §3.2.
"""

from __future__ import annotations

import hashlib
import os
import shutil
import subprocess
import sys
import tarfile
from pathlib import Path

import pytest

# Pinned ``SOURCE_DATE_EPOCH`` — 2024-05-16 12:00:00 UTC. Any fixed
# value works; pinning makes the test's pre-conditions explicit + lets
# operators reproduce locally with the same env var.
_SOURCE_DATE_EPOCH = "1715846400"


def _have_build_tool() -> bool:
    """Check whether `python -m build` is available."""
    try:
        result = subprocess.run(
            [sys.executable, "-m", "build", "--version"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        return result.returncode == 0
    except (subprocess.SubprocessError, FileNotFoundError, OSError):
        return False


_BUILD_AVAILABLE = _have_build_tool()


def _emit_build(repo_root: Path, out_dir: Path) -> None:
    """Run ``python -m build`` against ``repo_root`` into ``out_dir``."""
    env = dict(os.environ)
    env["SOURCE_DATE_EPOCH"] = _SOURCE_DATE_EPOCH
    # Force timezone determinism for any code path that reads tzdata.
    env["TZ"] = "UTC"
    # Clear any cached build/ from a prior invocation in the same dir.
    build_cache = repo_root / "build"
    if build_cache.exists():
        shutil.rmtree(build_cache)
    subprocess.run(
        [sys.executable, "-m", "build", "--outdir", str(out_dir)],
        check=True,
        cwd=str(repo_root),
        env=env,
        capture_output=True,
        timeout=600,
    )


def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def _extract_tar_member_hashes(tarball: Path) -> dict[str, str]:
    """Return ``{member_name → SHA-256(content)}`` for every regular
    file in the tar archive. Order-independent; captures content drift
    only."""
    out: dict[str, str] = {}
    with tarfile.open(tarball, "r:gz") as tf:
        for member in tf.getmembers():
            if not member.isfile():
                continue
            extracted = tf.extractfile(member)
            if extracted is None:
                continue
            data = extracted.read()
            out[member.name] = hashlib.sha256(data).hexdigest()
    return out


@pytest.fixture(scope="module")
def _repo_root() -> Path:
    return Path(__file__).resolve().parent.parent


@pytest.fixture(scope="module")
def _two_builds(tmp_path_factory: pytest.TempPathFactory, _repo_root: Path) -> tuple[Path, Path]:
    """Build the project twice into separate dirs. Module-scoped because
    `python -m build` takes ~30 s each invocation; running once per
    test would balloon the wall time."""
    if not _BUILD_AVAILABLE:
        pytest.skip("`python -m build` not available; install with [release] extra")
    out_a = tmp_path_factory.mktemp("build_a")
    out_b = tmp_path_factory.mktemp("build_b")
    _emit_build(_repo_root, out_a)
    _emit_build(_repo_root, out_b)
    return out_a, out_b


def _find_artefact(out_dir: Path, suffix: str) -> Path:
    matches = sorted(out_dir.glob(f"*{suffix}"))
    assert matches, f"Expected at least one *{suffix} under {out_dir}"
    return matches[0]


# ---------------------------------------------------------------------------
# Wheel byte-equivalence
# ---------------------------------------------------------------------------


@pytest.mark.skipif(not _BUILD_AVAILABLE, reason="build tool missing")
def test_wheel_is_byte_identical_under_pinned_source_date_epoch(
    _two_builds: tuple[Path, Path],
) -> None:
    """Two independent builds with the same SOURCE_DATE_EPOCH produce
    wheels with identical SHA-256."""
    out_a, out_b = _two_builds
    wheel_a = _find_artefact(out_a, ".whl")
    wheel_b = _find_artefact(out_b, ".whl")
    hash_a = _sha256_file(wheel_a)
    hash_b = _sha256_file(wheel_b)
    assert hash_a == hash_b, (
        f"Wheel reproducibility broken — two independent `python -m build` "
        f"invocations with SOURCE_DATE_EPOCH={_SOURCE_DATE_EPOCH} produced "
        f"different wheels:\n"
        f"  wheel_a sha256: {hash_a}\n"
        f"  wheel_b sha256: {hash_b}\n"
        f"  wheel_a path:   {wheel_a}\n"
        f"  wheel_b path:   {wheel_b}\n"
        f"Diff with: `diffoscope {wheel_a} {wheel_b}` (requires diffoscope)."
    )


# ---------------------------------------------------------------------------
# Sdist content-equivalence
# ---------------------------------------------------------------------------


@pytest.mark.skipif(not _BUILD_AVAILABLE, reason="build tool missing")
def test_sdist_contents_are_byte_identical_under_pinned_source_date_epoch(
    _two_builds: tuple[Path, Path],
) -> None:
    """Two independent builds produce sdists whose extracted file
    contents are identical even if the gzip header drifts.

    This is the framework's reproducibility property at the *content*
    level: the bytes Python actually loads at install time are
    deterministic, even though the gzip wrapper carries a wall-clock
    mtime that setuptools' sdist builder doesn't always pin under
    SOURCE_DATE_EPOCH.
    """
    out_a, out_b = _two_builds
    sdist_a = _find_artefact(out_a, ".tar.gz")
    sdist_b = _find_artefact(out_b, ".tar.gz")

    members_a = _extract_tar_member_hashes(sdist_a)
    members_b = _extract_tar_member_hashes(sdist_b)

    # Sanity: same member set (no files added / dropped between runs).
    set_a, set_b = set(members_a), set(members_b)
    missing_in_b = set_a - set_b
    extra_in_b = set_b - set_a
    assert not missing_in_b, (
        f"Sdist B is missing members that A has: {sorted(missing_in_b)}"
    )
    assert not extra_in_b, (
        f"Sdist B has extra members not in A: {sorted(extra_in_b)}"
    )

    # Content: every member hashes the same.
    differing = [
        (name, members_a[name], members_b[name])
        for name in sorted(set_a)
        if members_a[name] != members_b[name]
    ]
    assert not differing, (
        "Sdist content drifted across two `python -m build` invocations:\n"
        + "\n".join(
            f"  {name}: a={a[:16]}... b={b[:16]}..."
            for name, a, b in differing[:5]
        )
        + (f"\n  ... and {len(differing) - 5} more" if len(differing) > 5 else "")
    )


# ---------------------------------------------------------------------------
# Observability: known gzip-header drift
# ---------------------------------------------------------------------------


@pytest.mark.skipif(not _BUILD_AVAILABLE, reason="build tool missing")
def test_sdist_gzip_header_drift_is_documented_not_silent(
    _two_builds: tuple[Path, Path],
) -> None:
    """If the sdist gzip header DOES drift between runs (known
    limitation of setuptools' sdist builder on some Python/setuptools
    combinations under SOURCE_DATE_EPOCH), this test stays GREEN —
    its job is to document the drift, not gate on byte-equivalence
    of the wrapper.

    If the sdist gzip header becomes byte-deterministic in a future
    setuptools / Python release, this test still passes (the
    assertion is informational, not gating). When that happens, the
    next maintainer should tighten this test to a hard byte-equality
    check, matching the wheel test.
    """
    out_a, out_b = _two_builds
    sdist_a = _find_artefact(out_a, ".tar.gz")
    sdist_b = _find_artefact(out_b, ".tar.gz")
    hash_a = _sha256_file(sdist_a)
    hash_b = _sha256_file(sdist_b)
    # Informational only — print observed state but don't fail.
    if hash_a == hash_b:
        # Bonus: sdist gzip wrapper is byte-deterministic. Encourage
        # the next maintainer to tighten this test.
        print(
            "\n  INFO: sdist gzip wrappers are byte-identical under "
            "SOURCE_DATE_EPOCH on this Python/setuptools combination. "
            "Consider tightening test_sdist_gzip_header_drift_is_"
            "documented_not_silent to a hard assertion."
        )
    else:
        print(
            "\n  INFO: sdist gzip wrappers differ (expected on this "
            "setuptools/Python combination). Wheel + sdist content "
            "remain byte-identical per the prior two tests."
        )
    # Always passes — this test exists to surface the state, not gate it.
    assert True
