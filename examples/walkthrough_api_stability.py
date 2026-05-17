"""Concept walkthrough — API stability contract (RFC 0002 Phase E8).

Every public Ophamin symbol carries an explicit stability tier:
``@Stable`` / ``@Provisional`` / ``@Internal`` / ``@Deprecated``.
This walkthrough demonstrates the four decorators + the
introspection helpers consumers + tools use to audit a codebase
against the contract.

Run with::

    PYTHONPATH=src python examples/walkthrough_api_stability.py

Safe to import; demo runs only as ``__main__``.
"""

from __future__ import annotations

import warnings

from ophamin._stability import (
    Deprecated,
    Internal,
    Provisional,
    Stable,
    StabilityInfo,
    get_stability,
    is_deprecated,
    is_internal,
    is_provisional,
    is_stable,
)


# === Tier-tagged demo symbols (synthetic — for the walkthrough only)


@Stable(since="0.11.2", notes="Demo of the @Stable tag.")
def stable_function(x: int) -> int:
    """A stable public function."""
    return x * 2


@Stable(since="0.11.2")
class StableClass:
    """A stable public class."""

    def __init__(self, x: int) -> None:
        self.x = x


@Provisional(since="0.11.2", notes="Subject to change without notice.")
def provisional_function() -> str:
    return "provisional"


@Internal(notes="Internal helper; consumers MUST NOT import.")
def _internal_helper() -> int:
    return 42


@Deprecated(
    removal_version="1.0.0",
    replacement="ophamin.examples.walkthrough_api_stability.stable_function",
    since="0.11.2",
    notes="Use stable_function instead.",
)
def deprecated_function(x: int) -> int:
    """A deprecated function — emits DeprecationWarning when called."""
    return x  # no-op for the demo


@Deprecated(removal_version="1.0.0", since="0.11.2")
class DeprecatedClass:
    """A deprecated class — DeprecationWarning fires on instantiation."""

    def __init__(self, x: int) -> None:
        self.x = x


def main() -> None:
    print("# API stability contract walkthrough — RFC 0002 Phase E8")
    print()
    print("Every public Ophamin symbol carries one of four stability tiers.")
    print("The tier is set by a decorator that attaches a StabilityInfo to")
    print("__ophamin_stability__ on the target. Tools read this via the")
    print("get_stability() helper.")

    # === Demo symbols + their stability metadata
    print("\n## The four tiers")
    print()
    print(f"  {'symbol':<24} {'tier':<14} {'since':<10} {'extra'}")
    print(f"  {'-' * 70}")
    for obj in (
        stable_function,
        StableClass,
        provisional_function,
        _internal_helper,
        deprecated_function,
        DeprecatedClass,
    ):
        info = get_stability(obj)
        assert info is not None, f"{obj.__qualname__} missing stability tag"
        extra = ""
        if info.removal_version:
            extra = f"removal at {info.removal_version}"
        print(f"  {obj.__qualname__:<24} {info.tier:<14} {info.since:<10} {extra}")

    # === The predicates
    print("\n## Predicate helpers")
    print()
    print(f"  is_stable(stable_function)         = {is_stable(stable_function)}")
    print(f"  is_provisional(provisional_function) = {is_provisional(provisional_function)}")
    print(f"  is_internal(_internal_helper)      = {is_internal(_internal_helper)}")
    print(f"  is_deprecated(deprecated_function) = {is_deprecated(deprecated_function)}")

    # === @Deprecated emits a warning at call site
    print("\n## @Deprecated emits DeprecationWarning at call site")
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        _ = deprecated_function(99)
    assert any(issubclass(w.category, DeprecationWarning) for w in caught), (
        "Calling a @Deprecated function must emit DeprecationWarning"
    )
    msg = str(caught[0].message)
    print(f"  message: {msg[:120]}{'...' if len(msg) > 120 else ''}")

    # === StabilityInfo invariants
    print("\n## StabilityInfo invariants (construction-time validation)")
    print()
    print("  Unknown tier rejected:")
    try:
        StabilityInfo(tier="Experimental")
        raise AssertionError("Should have raised")
    except ValueError as exc:
        print(f"    ✓ ValueError: {exc!s}")

    print("\n  removal_version on a non-Deprecated tier rejected:")
    try:
        StabilityInfo(tier="Stable", removal_version="1.0.0")
        raise AssertionError("Should have raised")
    except ValueError as exc:
        print(f"    ✓ ValueError: {str(exc)[:90]}...")

    # === Auditing a user codebase
    print("\n## Auditing a user codebase")
    print()
    print("  Tools (the regression suite, `ophamin api-stability check`) read")
    print("  every reachable Ophamin import + flag @Deprecated / @Internal")
    print("  symbols. Try it on your own code:")
    print()
    print("    $ ophamin api-stability list           # show every tagged symbol")
    print("    $ ophamin api-stability check path/   # audit a directory")
    print()
    print("  Exit 0 = clean; exit 1 = at least one @Deprecated or @Internal")
    print("  import found. Suitable for downstream CI gates.")

    print("\n✓ API stability walkthrough complete. Contract demonstrated.")


if __name__ == "__main__":
    main()
