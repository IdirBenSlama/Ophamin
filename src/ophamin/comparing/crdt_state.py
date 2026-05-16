"""crdt_state — pycrdt + y-py wrappers for distributed-state probing.

Per ``docs/PLUGIN_CATALOG_2026_05_15.md`` §14. Two thin wrappers exposing
Yjs CRDT semantics through Python — both bind to the same Yrs Rust core
under the hood, so they're functionally equivalent + cross-checkable.

Use for:
  - Modeling multi-Ophamin-instance state (when scaling beyond one node)
  - Cross-checking Kimera's own G-Set / SCAR-DAG / Echoform-chain CRDTs
    via property-based testing (build a Hypothesis strategy that drives
    Kimera's CRDT + a pycrdt CRDT through the same op sequence; assert
    final-state equivalence)

Helpers:
  YDocFacade(backend="pycrdt"|"y_py")  — uniform interface over both libs
  cross_backend_convergence(...)        — drive both backends through same
                                          op sequence; assert equivalence
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass
class YDocFacade:
    """Thin uniform wrapper over pycrdt or y-py YDoc.

    Exposes the smallest surface area both libs share: ``get_text`` /
    ``get_array`` / ``get_map``, with op-application + state-as-bytes for
    cross-instance sync.
    """

    backend: str = "pycrdt"
    _doc: Any = None

    def __post_init__(self) -> None:
        backend = self.backend.strip().lower()
        if backend == "pycrdt":
            try:
                from pycrdt import Doc
            except ImportError as e:
                raise ImportError("pycrdt required; `pip install pycrdt`") from e
            self._doc = Doc()
        elif backend in ("y_py", "y-py", "ypy"):
            try:
                import y_py as Y
            except ImportError as e:
                raise ImportError("y-py required; `pip install y-py`") from e
            self._doc = Y.YDoc()
        else:
            raise ValueError(
                f"backend must be 'pycrdt' or 'y_py'; got {self.backend!r}"
            )
        self.backend = backend if backend != "ypy" else "y_py"
        if backend == "y-py":
            self.backend = "y_py"

    def insert_text(self, key: str, position: int, value: str) -> None:
        """Insert ``value`` into the named YText at ``position``."""
        if self.backend == "pycrdt":
            from pycrdt import Text as PyText
            text = self._doc.get(key, type=PyText)
            text.insert(position, value)
        else:  # y_py
            import y_py as Y
            text = self._doc.get_text(key)
            with self._doc.begin_transaction() as txn:
                text.insert(txn, position, value)

    def get_text(self, key: str) -> str:
        """Return the current text of the named YText."""
        if self.backend == "pycrdt":
            from pycrdt import Text as PyText
            text = self._doc.get(key, type=PyText)
            return str(text)
        else:
            text = self._doc.get_text(key)
            return str(text)

    def encode_state(self) -> bytes:
        """Encode the doc's full state as an update payload (for sync to another node).

        Both backends return an *update* — the operation stream another doc
        can replay via :meth:`apply_state` to converge. Note: pycrdt's
        ``get_state()`` returns the state *vector* (a logical clock summary,
        unusable as an update), so we route through ``get_update()`` instead.
        """
        if self.backend == "pycrdt":
            return bytes(self._doc.get_update())
        else:
            import y_py as Y
            return bytes(Y.encode_state_as_update(self._doc))

    def apply_state(self, state: bytes) -> None:
        """Apply an encoded state from another node (idempotent + commutative)."""
        if self.backend == "pycrdt":
            self._doc.apply_update(state)
        else:
            import y_py as Y
            with self._doc.begin_transaction() as txn:
                Y.apply_update(self._doc, state)


def cross_backend_convergence(
    operations: list[tuple[str, int, str]],
    text_key: str = "main",
) -> dict[str, Any]:
    """Apply a sequence of insert ops to BOTH pycrdt and y-py YDocs;
    verify they converge to the same final text.

    ``operations``: ``[(op_kind, position, value), ...]`` where
    ``op_kind`` is currently always ``"insert"`` (extension point).

    Returns ``{"agreed": bool, "pycrdt_text": str, "y_py_text": str,
              "n_ops": int}``. The two CRDT backends bind to the same
    Yrs Rust core, so they MUST agree — disagreement is a bug.
    """
    try:
        pycrdt_doc = YDocFacade(backend="pycrdt")
        y_py_doc = YDocFacade(backend="y_py")
    except ImportError as e:
        raise ImportError(
            f"both pycrdt + y-py required for cross-backend check: {e}"
        ) from e

    for op_kind, position, value in operations:
        if op_kind != "insert":
            raise ValueError(
                f"only 'insert' op currently supported; got {op_kind!r}"
            )
        pycrdt_doc.insert_text(text_key, position, value)
        y_py_doc.insert_text(text_key, position, value)

    pycrdt_text = pycrdt_doc.get_text(text_key)
    y_py_text = y_py_doc.get_text(text_key)
    return {
        "agreed": pycrdt_text == y_py_text,
        "pycrdt_text": pycrdt_text,
        "y_py_text": y_py_text,
        "n_ops": len(operations),
    }
