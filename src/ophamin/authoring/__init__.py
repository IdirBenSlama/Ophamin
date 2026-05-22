"""Ophamin authoring — grounded scenario specification.

The contract layer for describing experiments — by hand, from a file, or
(eventually) from a natural-language description handed to an offline model.
Its job is to make an ungrounded or synthetic scenario impossible: every
spec must carry a falsifiable threshold, scientific grounding, and a real
data source before it can become a runnable scenario.

No LLM runs in this layer's measurement path. A model may *fill* a spec
offline (Ophamin tooling), but the spec — and the scenario it produces —
runs with no external LLM, per the substrate's no-external-LLM rule.

Public API:

- :class:`ScenarioSpec`, :class:`GroundingRef`, :class:`Threshold`,
  :class:`DataSourceRef` — the spec data model.
- :func:`available_capabilities` — the live menu of real corpora / scopes /
  facets / invariant templates / tools / standards an author selects from.
- :func:`validate_spec`, :func:`validate_spec_dict`, :func:`is_acceptable`,
  :class:`SpecViolation` — the grounding gate.
"""

from __future__ import annotations

from ophamin.authoring.capabilities import (
    available_capabilities,
    invariant_template_names,
    tool_ids,
)
from ophamin.authoring.spec import (
    DataSourceRef,
    GroundingRef,
    ScenarioSpec,
    Threshold,
)
from ophamin.authoring.validation import (
    SpecViolation,
    is_acceptable,
    validate_spec,
    validate_spec_dict,
)
from ophamin.authoring.materialize import (
    MaterializationError,
    MaterializedScenario,
    materialization_plan,
    materialize_spec,
)

__all__ = [
    "DataSourceRef",
    "GroundingRef",
    "MaterializationError",
    "MaterializedScenario",
    "ScenarioSpec",
    "SpecViolation",
    "Threshold",
    "available_capabilities",
    "invariant_template_names",
    "is_acceptable",
    "materialization_plan",
    "materialize_spec",
    "tool_ids",
    "validate_spec",
    "validate_spec_dict",
]
