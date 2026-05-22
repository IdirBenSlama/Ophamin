#!/usr/bin/env python3
"""Bump (or check) Ophamin's version across ALL the places it must agree.

The version lives in three files and they MUST stay in lockstep — a mismatch is
caught (loudly, after the fact) by ``tests/test_helm_chart.py``. This session hit
that failure twice because the Helm chart was bumped by hand and forgotten. This
is the root-cause fix: one command sets all three.

    python tools/bump_version.py 0.114.0      # set every location to 0.114.0
    python tools/bump_version.py --check      # verify they already agree (exit 1 if not)

Locations:
  * pyproject.toml            ``version = "X"``
  * src/ophamin/__init__.py   ``__version__ = "X"``
  * charts/ophamin/Chart.yaml ``appVersion: "X"``  (chart `version:` is independent)
"""

from __future__ import annotations

import re
import sys
from dataclasses import dataclass
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
_SEMVER = re.compile(r"^\d+\.\d+\.\d+([-+].+)?$")


@dataclass(frozen=True)
class _Loc:
    path: Path
    pattern: re.Pattern[str]   # one capture group around the version literal
    label: str


_LOCATIONS = (
    _Loc(_ROOT / "pyproject.toml",
         re.compile(r'(?m)^version = "([^"]+)"'), "pyproject.toml version"),
    _Loc(_ROOT / "src" / "ophamin" / "__init__.py",
         re.compile(r'(?m)^__version__ = "([^"]+)"'), "__init__.py __version__"),
    _Loc(_ROOT / "charts" / "ophamin" / "Chart.yaml",
         re.compile(r'(?m)^appVersion: "([^"]+)"'), "Chart.yaml appVersion"),
)


def _read(loc: _Loc) -> tuple[str, str]:
    text = loc.path.read_text(encoding="utf-8")
    m = loc.pattern.search(text)
    if m is None:
        raise SystemExit(f"ERROR: could not find version in {loc.label} ({loc.path})")
    return text, m.group(1)


def check() -> int:
    versions = {loc.label: _read(loc)[1] for loc in _LOCATIONS}
    distinct = set(versions.values())
    for label, v in versions.items():
        print(f"  {label:28s} {v}")
    if len(distinct) == 1:
        print(f"OK — all locations agree at {distinct.pop()}")
        return 0
    print(f"MISMATCH — {sorted(distinct)}")
    return 1


def bump(new: str) -> int:
    if not _SEMVER.match(new):
        raise SystemExit(f"ERROR: {new!r} is not a semantic version (X.Y.Z)")
    for loc in _LOCATIONS:
        text, old = _read(loc)
        # replace only the captured version literal, preserving surrounding text
        updated = loc.pattern.sub(
            lambda m: m.group(0).replace(f'"{m.group(1)}"', f'"{new}"'), text, count=1)
        loc.path.write_text(updated, encoding="utf-8")
        print(f"  {loc.label:28s} {old} -> {new}")
    print(f"bumped all locations to {new}")
    return 0


def main(argv: list[str]) -> int:
    if len(argv) != 1 or argv[0] in {"-h", "--help"}:
        print(__doc__)
        return 0 if argv and argv[0] in {"-h", "--help"} else 2
    if argv[0] == "--check":
        return check()
    return bump(argv[0])


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
