"""Ophamin reproducing wheel — measure what re-running actually reproduces.

A proof carries a ``reproduction`` section (command + environment lock +
lineage) that says HOW to re-run it. This wheel measures WHAT reproduces when
you do — honestly, by layer (see :mod:`ophamin.reproducing.check`).
"""

from __future__ import annotations

from ophamin.reproducing.check import ReproductionReport, reproduce

__all__ = ["ReproductionReport", "reproduce"]
