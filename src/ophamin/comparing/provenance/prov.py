"""W3C PROV-O provenance graphs (F pillar).

Backed by the **prov** library (Trung Dong Huynh's W3C PROV implementation).
``ProvenanceGraph`` is a thin, snake_case wrapper over ``prov.model.ProvDocument``
so the rest of the framework has a stable API — while the PROV data model, its
validation, and the W3C PROV-JSON serialization all come from the library.

PROV-O maps three node types and the relations between them:

    Entity    a physical or digital object (a dataset, a config, a result)
    Activity  a transformation or process acting on/producing entities
    Agent     a user, script, or organisation bearing responsibility
"""

from __future__ import annotations

import json
import re
from typing import Any

from prov.model import ProvDocument

_NS_PREFIX = "ophamin"
_NS_URI = "https://ophamin.example/"
_UNSAFE = re.compile(r"[^A-Za-z0-9_.\-]")


def _primitive(value: Any) -> Any:
    """Coerce an attribute value to something the prov library can serialize."""
    if isinstance(value, (bool, int, float, str)):
        return value
    return str(value)


class ProvenanceGraph:
    """A W3C PROV graph of entities, activities, agents and their relations."""

    def __init__(self) -> None:
        self._doc = ProvDocument()
        self._doc.add_namespace(_NS_PREFIX, _NS_URI)
        self._nodes: dict[str, Any] = {}

    @staticmethod
    def _qname(identifier: str) -> str:
        local = _UNSAFE.sub("_", str(identifier))
        return f"{_NS_PREFIX}:{local}"

    @staticmethod
    def _attrs(kwargs: dict[str, Any]) -> dict[str, Any] | None:
        if not kwargs:
            return None
        return {f"{_NS_PREFIX}:{k}": _primitive(v) for k, v in kwargs.items()}

    def _resolve(self, ref: Any) -> Any:
        """Accept a prov node or an id string; return a prov node.

        An id referenced in a relation but never declared is registered as a
        bare entity — the relation is still recorded, the node is not lost.
        """
        if hasattr(ref, "identifier"):
            return ref
        key = str(ref)
        if key not in self._nodes:
            self._nodes[key] = self._doc.entity(self._qname(key))
        return self._nodes[key]

    # -- nodes --------------------------------------------------------------

    def entity(self, identifier: str, **attributes: Any) -> Any:
        key = str(identifier)
        node = self._doc.entity(
            self._qname(key), other_attributes=self._attrs(attributes)
        )
        self._nodes[key] = node
        return node

    def activity(
        self,
        identifier: str,
        start_time: Any = None,
        end_time: Any = None,
        **attributes: Any,
    ) -> Any:
        key = str(identifier)
        node = self._doc.activity(
            self._qname(key),
            start_time,
            end_time,
            other_attributes=self._attrs(attributes),
        )
        self._nodes[key] = node
        return node

    def agent(self, identifier: str, **attributes: Any) -> Any:
        key = str(identifier)
        node = self._doc.agent(
            self._qname(key), other_attributes=self._attrs(attributes)
        )
        self._nodes[key] = node
        return node

    # -- relations ----------------------------------------------------------

    def used(self, activity: Any, entity: Any, **attributes: Any) -> Any:
        return self._doc.used(
            self._resolve(activity),
            self._resolve(entity),
            other_attributes=self._attrs(attributes),
        )

    def was_generated_by(self, entity: Any, activity: Any, **attributes: Any) -> Any:
        return self._doc.wasGeneratedBy(
            self._resolve(entity),
            self._resolve(activity),
            other_attributes=self._attrs(attributes),
        )

    def was_associated_with(self, activity: Any, agent: Any, **attributes: Any) -> Any:
        return self._doc.wasAssociatedWith(
            self._resolve(activity),
            self._resolve(agent),
            other_attributes=self._attrs(attributes),
        )

    def was_attributed_to(self, entity: Any, agent: Any, **attributes: Any) -> Any:
        return self._doc.wasAttributedTo(
            self._resolve(entity),
            self._resolve(agent),
            other_attributes=self._attrs(attributes),
        )

    def was_derived_from(self, entity: Any, source_entity: Any, **attributes: Any) -> Any:
        return self._doc.wasDerivedFrom(
            self._resolve(entity),
            self._resolve(source_entity),
            other_attributes=self._attrs(attributes),
        )

    def was_informed_by(self, activity: Any, informant: Any, **attributes: Any) -> Any:
        return self._doc.wasInformedBy(
            self._resolve(activity),
            self._resolve(informant),
            other_attributes=self._attrs(attributes),
        )

    def acted_on_behalf_of(self, agent: Any, responsible: Any, **attributes: Any) -> Any:
        return self._doc.actedOnBehalfOf(
            self._resolve(agent),
            self._resolve(responsible),
            other_attributes=self._attrs(attributes),
        )

    # -- serialisation ------------------------------------------------------

    def to_prov_json(self) -> dict[str, Any]:
        """Emit a W3C PROV-JSON document (via the prov library serializer)."""
        result: dict[str, Any] = json.loads(self._doc.serialize(format="json"))
        return result

    def to_dict(self) -> dict[str, Any]:
        """Alias for :meth:`to_prov_json` — the canonical serialisation."""
        return self.to_prov_json()

    @property
    def document(self) -> ProvDocument:
        """The underlying ``prov.model.ProvDocument`` (for PROV-N / PROV-XML, etc.)."""
        return self._doc

    def __repr__(self) -> str:
        return f"ProvenanceGraph({len(list(self._doc.get_records()))} records)"
