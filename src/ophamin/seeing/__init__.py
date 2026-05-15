"""Wheel 1 — Seeing.

The innermost ring of Ophamin: how the observatory senses Kimera and the
world. Three submodules:

  - ``substrate``  — the inner shell touching Kimera (KimeraAdapter,
                     SubstrateUnderTest, MockSubstrate)
  - ``corpus``     — plug-in datasets the world is seen through
                     (Enron, Linux kernel, FLORES-200, offensive-security,
                     financial, the Well)
  - ``discovery``  — auto-discovery of Kimera's field schema (Layer A of
                     the Kimera-co-evolution stack)

In the Ophanim image, this wheel carries the eyes that look at the central
flame.
"""

from __future__ import annotations

from ophamin.seeing import corpus, discovery, substrate

__all__ = ["corpus", "discovery", "substrate"]
