"""API stability tier annotations (Phase E8 of RFC 0002).

Every public symbol Ophamin exposes carries an explicit stability
**tier** — a contract between the framework and its consumers about
how aggressively a symbol's signature, behaviour, or existence may
change between releases.

The tiers are:

* :class:`Stable` — semver-backed public API. Signature changes are
  breaking changes per :ref:`SCHEMAS.md`'s "Migration policy".
  Adding optional parameters with defaults is allowed at minor; any
  rename, removal, or required-parameter addition needs a major
  bump and a deprecation cycle.
* :class:`Provisional` — public but subject to change without a
  deprecation cycle. May be promoted to ``Stable`` or removed at
  any minor release.
* :class:`Internal` — not part of the public API. The leading
  underscore convention plus this decorator marks symbols that
  consumers MUST NOT import. May change in any release.
* :class:`Deprecated` — scheduled for removal at the version
  recorded in ``removal_version``. Calling a Deprecated callable
  emits a ``DeprecationWarning`` exactly once per process. The
  ``ophamin api-stability check`` CLI surfaces reachable
  deprecations in a user codebase.

The mechanism is intentionally tiny: every decorator sets a single
attribute :attr:`STABILITY_ATTR` on the target. Tools — including
the regression test suite at
``tests/test_api_stability_contract.py`` and the
``ophamin api-stability check`` command — read that attribute by
name; they never re-evaluate the decorator. This keeps the runtime
overhead at zero (attribute assignment is constant-time) and avoids
any double-decoration-order pitfalls when composing with
``@dataclass``.

Reference: RFC 0002 §3.2 "Phase E8 — API stability policy".
"""

from __future__ import annotations

import warnings
from dataclasses import dataclass
from typing import Any, Callable, TypeVar

T = TypeVar("T")


#: Attribute name set on every annotated target. Reader tools walk
#: imports and read this attribute via ``getattr(obj, STABILITY_ATTR,
#: None)``.
STABILITY_ATTR = "__ophamin_stability__"

#: The four canonical tier names, in increasing strictness order.
#: Stable + Provisional + Internal are mutually exclusive; Deprecated
#: composes with one of them (a previously-Stable symbol may become
#: Deprecated; never a Provisional or Internal one).
TIERS: frozenset[str] = frozenset(
    {"Stable", "Provisional", "Internal", "Deprecated"}
)


@dataclass(frozen=True)
class StabilityInfo:
    """Structured tier annotation read by tools.

    Attributes:
        tier: one of :data:`TIERS`.
        since: version string this symbol was introduced at
            (e.g. ``"0.9.0"``). ``""`` for symbols predating the
            policy.
        removal_version: only meaningful when ``tier == "Deprecated"``.
            The version at which the symbol will be removed (e.g.
            ``"1.0.0"``); consumers SHOULD migrate before this version
            lands.
        replacement: only meaningful when ``tier == "Deprecated"``.
            The fully-qualified name of the symbol that supersedes
            this one, or ``""`` if no direct replacement exists.
        notes: free-form prose; goes into the
            ``DeprecationWarning`` message if tier == "Deprecated",
            otherwise descriptive.
    """

    tier: str
    since: str = ""
    removal_version: str = ""
    replacement: str = ""
    notes: str = ""

    def __post_init__(self) -> None:
        if self.tier not in TIERS:
            raise ValueError(
                f"StabilityInfo.tier must be one of {sorted(TIERS)}; got {self.tier!r}"
            )
        if self.tier != "Deprecated":
            if self.removal_version or self.replacement:
                raise ValueError(
                    "removal_version + replacement are only meaningful "
                    f"for tier='Deprecated'; got tier={self.tier!r}"
                )


def _set_stability(obj: T, info: StabilityInfo) -> T:
    """Attach the stability annotation to a target object.

    Works on classes, functions, methods, and dataclass-decorated
    classes (the @dataclass result is still attribute-settable).
    Returns the input unchanged so the decorator chain is composable.
    """
    try:
        setattr(obj, STABILITY_ATTR, info)
    except (AttributeError, TypeError):
        # Built-in or C-extension targets won't accept attribute
        # assignment. The decorator becomes a no-op for those — tools
        # treat the absence of STABILITY_ATTR as "unannotated".
        pass
    return obj


# --- public decorators ------------------------------------------------------


def Stable(*, since: str = "", notes: str = "") -> Callable[[T], T]:
    """Mark a symbol as part of the semver-backed public API.

    Usage::

        from ophamin._stability import Stable

        @Stable(since="0.9.0")
        class CampaignRecord:
            ...

        @Stable(since="0.9.0", notes="Returns a signed proof.")
        def run_campaign(...) -> CampaignRecord:
            ...

    Stable symbols' signatures may grow (new optional parameters
    with defaults) at minor releases; they may not shrink or rename
    without a major bump + deprecation cycle.
    """
    info = StabilityInfo(tier="Stable", since=since, notes=notes)

    def decorator(obj: T) -> T:
        return _set_stability(obj, info)

    return decorator


def Provisional(*, since: str = "", notes: str = "") -> Callable[[T], T]:
    """Mark a symbol as public but subject to change without a deprecation cycle.

    Provisional symbols are useful for letting consumers exercise an
    API before its shape is frozen. The promotion path is
    Provisional → Stable (when the design settles); the alternative
    is removal at any minor.
    """
    info = StabilityInfo(tier="Provisional", since=since, notes=notes)

    def decorator(obj: T) -> T:
        return _set_stability(obj, info)

    return decorator


def Internal(*, notes: str = "") -> Callable[[T], T]:
    """Mark a symbol as not part of the public API.

    The leading-underscore convention covers most internal symbols;
    this decorator is useful for the cases where the underscore is
    awkward (e.g. a public-looking module that contains
    framework-internal helpers, or a class whose name a future
    refactor will rename).

    Consumers MUST NOT import @Internal symbols. The CLI
    ``ophamin api-stability check`` reports any reachable Internal
    imports in a target codebase.
    """
    info = StabilityInfo(tier="Internal", since="", notes=notes)

    def decorator(obj: T) -> T:
        return _set_stability(obj, info)

    return decorator


def Deprecated(
    *,
    removal_version: str,
    replacement: str = "",
    since: str = "",
    notes: str = "",
) -> Callable[[T], T]:
    """Mark a symbol as scheduled for removal.

    Args:
        removal_version: the version at which this symbol will be
            removed (e.g. ``"1.0.0"``). Consumers SHOULD migrate
            before this version lands.
        replacement: fully-qualified name of the superseding symbol
            (e.g. ``"ophamin.run_campaign"``). Empty if no direct
            replacement.
        since: the version this symbol was first marked deprecated.
        notes: additional prose to include in the
            ``DeprecationWarning`` message.

    Calling a @Deprecated callable emits a ``DeprecationWarning``
    once per process (per `warnings.warn`'s default behaviour with a
    unique message), pointing the consumer at the replacement +
    removal deadline.

    For @Deprecated classes, instantiation triggers the warning;
    the class itself stays usable until ``removal_version``.
    """
    if not removal_version:
        raise ValueError("Deprecated requires removal_version")
    info = StabilityInfo(
        tier="Deprecated",
        since=since,
        removal_version=removal_version,
        replacement=replacement,
        notes=notes,
    )

    def decorator(obj: T) -> T:
        _set_stability(obj, info)
        # Wrap callable targets so calling them surfaces the warning.
        # Classes get __init__ wrapped; functions get a thin wrapper.
        if isinstance(obj, type):
            # Use getattr/setattr to avoid mypy's
            # "accessing __init__ on an instance is unsound" warning;
            # at runtime this is the same as obj.__init__ since
            # classes carry __init__ as a class-level attribute.
            original_init = getattr(obj, "__init__")

            def _warn_init(self: Any, *args: Any, **kwargs: Any) -> None:
                _emit_deprecation_warning(obj, info)
                original_init(self, *args, **kwargs)

            setattr(obj, "__init__", _warn_init)
        elif callable(obj):
            from functools import wraps

            @wraps(obj)
            def _warn_call(*args: Any, **kwargs: Any) -> Any:
                _emit_deprecation_warning(obj, info)
                return obj(*args, **kwargs)

            # Preserve the stability annotation on the wrapper so
            # tools still find it.
            _set_stability(_warn_call, info)
            return _warn_call  # type: ignore[return-value]
        return obj

    return decorator


def _emit_deprecation_warning(target: Any, info: StabilityInfo) -> None:
    """Format the standard message + emit a DeprecationWarning."""
    name = getattr(target, "__qualname__", None) or getattr(
        target, "__name__", "<unknown>"
    )
    module = getattr(target, "__module__", "")
    fq = f"{module}.{name}" if module else name
    msg_parts = [
        f"{fq} is deprecated; scheduled for removal at version {info.removal_version}."
    ]
    if info.replacement:
        msg_parts.append(f"Use {info.replacement} instead.")
    if info.notes:
        msg_parts.append(info.notes)
    warnings.warn(" ".join(msg_parts), DeprecationWarning, stacklevel=3)


# --- introspection helpers (tools layer) ------------------------------------


def get_stability(obj: Any) -> StabilityInfo | None:
    """Return the :class:`StabilityInfo` attached to ``obj``, or ``None``.

    Tools (the regression suite, the ``api-stability check`` CLI)
    read tier metadata via this helper rather than touching
    :data:`STABILITY_ATTR` directly so that future refactors of the
    underlying attribute don't break consumers.
    """
    info = getattr(obj, STABILITY_ATTR, None)
    if isinstance(info, StabilityInfo):
        return info
    return None


def is_stable(obj: Any) -> bool:
    info = get_stability(obj)
    return info is not None and info.tier == "Stable"


def is_provisional(obj: Any) -> bool:
    info = get_stability(obj)
    return info is not None and info.tier == "Provisional"


def is_internal(obj: Any) -> bool:
    info = get_stability(obj)
    return info is not None and info.tier == "Internal"


def is_deprecated(obj: Any) -> bool:
    info = get_stability(obj)
    return info is not None and info.tier == "Deprecated"


__all__ = [
    "STABILITY_ATTR",
    "TIERS",
    "Deprecated",
    "Internal",
    "Provisional",
    "Stable",
    "StabilityInfo",
    "get_stability",
    "is_deprecated",
    "is_internal",
    "is_provisional",
    "is_stable",
]
