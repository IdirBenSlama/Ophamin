# Wrap a third-party pillar in ~50 LOC

Ophamin's pillars are thin wrappers over **mature, battle-tested
libraries**. The framework's own job is the protocol + the
attribution + the test harness; the heavy maths is delegated upstream.

This tutorial walks through wrapping a third-party library as a
pillar, using a hypothetical "complexity-from-radon" pillar as the
example.

## The Pillar protocol

`ophamin.protocols.Pillar` is a [Protocol](https://docs.python.org/3/library/typing.html#typing.Protocol)
— anything that quacks like a Pillar can be passed to a scenario.
The contract:

```python
class Pillar(Protocol):
    """A statistical / analytical method, delegating to one upstream library."""
    name: str               # short identifier, e.g. "O.spc"
    library: str            # the upstream library used, e.g. "statsmodels"
    library_version: str    # captured at runtime via importlib.metadata

    def run(self, *args, **kwargs) -> Any:
        """Apply the pillar to its inputs; return the result."""
```

There's no abstract base class; you just implement the three attributes
+ one method and you're a Pillar. (The `register_pillar` registry is
optional — used when you want CLI discovery.)

## Worked example — a complexity pillar over radon

[Radon](https://radon.readthedocs.io) computes cyclomatic complexity
+ maintainability index. Let's wrap it as an Ophamin pillar.

```python
# src/ophamin/auditing/pillars/radon_pillar.py
from __future__ import annotations

import subprocess
from importlib.metadata import version
from pathlib import Path
from typing import Any

from ophamin.auditing.base import AuditPillar, Finding, FindingSeverity, PillarResult


class RadonComplexityPillar(AuditPillar):
    """Cyclomatic-complexity findings from radon."""

    name = "audit.radon"
    tool_binary = "radon"

    @property
    def library(self) -> str:
        return "radon"

    @property
    def library_version(self) -> str:
        return version("radon")

    def run(self, target_path: str | Path, **_kwargs: Any) -> PillarResult:
        target = str(Path(target_path).resolve())
        if not self.is_available():
            return self.unavailable_result(target)
        cmd = [self.resolved_binary() or self.tool_binary, "cc", "-s", "-j", target]
        completed = subprocess.run(
            cmd, capture_output=True, text=True, check=False
        )
        if completed.returncode != 0:
            return self.error_result(target, completed.stderr or completed.stdout)
        findings = self._parse_radon_json(completed.stdout, target)
        return self.ok_result(
            target,
            findings=findings,
            tool_version=self.library_version,
            wall_time_s=0.0,
        )

    def _parse_radon_json(self, stdout: str, target: str) -> tuple[Finding, ...]:
        import json
        data = json.loads(stdout)
        out: list[Finding] = []
        for path, blocks in data.items():
            for b in blocks:
                if b.get("rank", "") in ("E", "F"):   # rank E/F = high complexity
                    out.append(Finding(
                        pillar_name=self.name,
                        rule_id=f"complexity-{b['rank']}",
                        severity=FindingSeverity.HIGH,
                        message=f"{b['name']} cyclomatic complexity {b['complexity']}",
                        path=path,
                        line=int(b.get("lineno", 0)),
                        column=int(b.get("col_offset", 0)),
                        extra={"complexity": b["complexity"], "rank": b["rank"]},
                    ))
        return tuple(out)
```

That's ~50 LOC. Now register it:

```python
# src/ophamin/auditing/pillars/__init__.py
from ophamin.auditing.pillars.radon_pillar import RadonComplexityPillar

DEEP_PILLAR_CLASSES = (
    *DEEP_PILLAR_CLASSES,
    RadonComplexityPillar,
)
```

## Test it

```python
# tests/test_audit_radon.py
def test_radon_pillar_skips_when_radon_missing(tmp_path):
    p = RadonComplexityPillar()
    if not p.is_available():
        result = p.run(tmp_path)
        assert result.status == "unavailable"


def test_radon_pillar_finds_high_complexity(tmp_path):
    src = tmp_path / "complex.py"
    src.write_text(
        "def f(x):\n" +
        "\n".join(f"    if x == {i}: return {i}" for i in range(20)) +
        "\n    return -1\n"
    )
    p = RadonComplexityPillar()
    if not p.is_available():
        import pytest; pytest.skip("radon not installed")
    result = p.run(tmp_path)
    assert result.status == "ok"
    assert len(result.findings) >= 1
```

## The "library_version is captured at runtime" rule

Every pillar MUST surface its upstream library + version. Reason:
when a proof or audit record is reproduced later, knowing exactly
which version of statsmodels / mapie / radon / etc. produced the
number is what makes the result auditable.

Don't hardcode the version. Use `importlib.metadata.version(...)`.

## The "delegate, don't reinvent" rule

Pillars that reimplement standard maths instead of calling upstream
will be rejected at review. The framework's value is **the
attribution, the test harness, the signed-record output** — not
re-deriving t-tests in Python.

If the upstream library is missing a feature, file an upstream issue
+ document the gap. The pillar should still call the library and
surface "the feature isn't available in this library version" via a
Finding rather than reimplementing it.

## Submit it

See [Contributing](../contributing.md) for the PR checklist. For a
non-trivial new pillar (new tier? new severity scheme?), open an
[RFC](../rfc/README.md) first.
