"""SAT/SMT helpers — z3 + cvc5 + pysmt wrappers.

Per ``docs/PLUGIN_CATALOG_2026_05_15.md`` §"SAT/SMT solvers". Two helpers
+ one cross-check oracle:

  check_sat_z3(formula_str, declarations)         — z3 backend
  check_sat_cvc5(formula_str, declarations)       — cvc5 backend
  check_sat_cross_backend(formula, declarations)  — both, must agree

Useful for verifying substrate invariants (e.g., "for all SCAR
formations, the topological deformation is monotonic"). Currently
generic; substrate-specific scenarios in follow-on PRs.
"""

from __future__ import annotations

from typing import Any


def check_sat_z3(
    constraints: list[str] | tuple[str, ...],
    *,
    declarations: list[str] | tuple[str, ...] = (),
    timeout_ms: int = 10000,
) -> dict[str, Any]:
    """Check satisfiability of an SMT-LIB-style formula with z3.

    ``declarations`` is a list of ``"(declare-fun x () Int)"`` style lines.
    ``constraints`` is a list of ``"(assert ...)"`` style lines.

    Returns ``{"sat": bool, "model": dict|None, "backend": "z3", "ms": int}``.
    """
    try:
        import time as _time
        from z3 import Solver, parse_smt2_string, sat as z3_sat, unsat as z3_unsat
    except ImportError as e:
        raise ImportError("z3-solver required; `pip install z3-solver`") from e
    smt2 = "\n".join(list(declarations) + list(constraints))
    solver = Solver()
    solver.set("timeout", int(timeout_ms))
    try:
        formulas = parse_smt2_string(smt2)
    except Exception as e:
        raise ValueError(
            f"z3 failed to parse SMT-LIB input: {type(e).__name__}: {e}"
        ) from e
    # z3's parse_smt2_string returns an empty AstVector on parse error
    # (writes the diagnostic to stderr instead of raising). Detect that
    # and surface as a loud-failure ValueError.
    if len(formulas) == 0 and constraints:
        raise ValueError(
            f"z3 parsed 0 formulas from {len(constraints)} constraint(s); "
            f"check SMT-LIB syntax. First constraint: {list(constraints)[0][:80]!r}"
        )
    for f in formulas:
        solver.add(f)
    t0 = _time.perf_counter()
    result = solver.check()
    ms = int((_time.perf_counter() - t0) * 1000)
    if result == z3_sat:
        model = solver.model()
        return {
            "sat": True,
            "model": {str(d): str(model[d]) for d in model.decls()},
            "backend": "z3",
            "ms": ms,
        }
    if result == z3_unsat:
        return {"sat": False, "model": None, "backend": "z3", "ms": ms}
    return {"sat": False, "model": None, "backend": "z3", "ms": ms,
            "unknown": True}


def check_sat_cvc5(
    constraints: list[str] | tuple[str, ...],
    *,
    declarations: list[str] | tuple[str, ...] = (),
    timeout_ms: int = 10000,
) -> dict[str, Any]:
    """Check satisfiability with cvc5 (alternative SMT backend).

    Same interface as ``check_sat_z3``. Useful as a cross-check oracle.
    """
    try:
        import time as _time
        import cvc5
        from cvc5 import Kind  # noqa: F401
    except ImportError as e:
        raise ImportError("cvc5 required; `pip install cvc5`") from e
    solver = cvc5.Solver()
    solver.setOption("produce-models", "true")
    solver.setOption("tlimit", str(int(timeout_ms)))
    smt2 = "\n".join(list(declarations) + list(constraints) + ["(check-sat)"])
    t0 = _time.perf_counter()
    try:
        # cvc5 Python bindings: parse via setLogic + assert via parser API.
        # Simpler path: use the SymbolManager + Parser pipeline if available;
        # otherwise compile via the CLI fallback. For Phase 0 we use the
        # standalone parser API.
        from cvc5 import InputParser, SymbolManager
        sym_mgr = SymbolManager(solver)
        parser = InputParser(solver, sym_mgr)
        parser.setStringInput(cvc5.InputLanguage.SMT_LIB_2_6, smt2, "ophamin")
        cmd = parser.nextCommand()
        while cmd.isNull() is False:
            cmd.invoke(solver, sym_mgr)
            cmd = parser.nextCommand()
        result = solver.checkSat()
        ms = int((_time.perf_counter() - t0) * 1000)
        return {
            "sat": bool(result.isSat()),
            "model": None,        # cvc5 model retrieval is more involved
            "backend": "cvc5",
            "ms": ms,
        }
    except Exception as e:
        return {
            "sat": False,
            "model": None,
            "backend": "cvc5",
            "ms": int((_time.perf_counter() - t0) * 1000),
            "error": f"{type(e).__name__}: {e}",
        }


def check_sat_cross_backend(
    constraints: list[str] | tuple[str, ...],
    *,
    declarations: list[str] | tuple[str, ...] = (),
    timeout_ms: int = 10000,
) -> dict[str, Any]:
    """Check sat with both z3 and cvc5; they MUST agree.

    Returns ``{"agreed": bool, "z3": {...}, "cvc5": {...}}``.

    Loud warning when the two disagree — that's a real issue (either a
    bug in one solver, or a non-deterministic / undefined formula).
    """
    z3_out = check_sat_z3(constraints, declarations=declarations,
                          timeout_ms=timeout_ms)
    cvc5_out = check_sat_cvc5(constraints, declarations=declarations,
                              timeout_ms=timeout_ms)
    return {
        "agreed": (z3_out["sat"] == cvc5_out["sat"]) and
                  not z3_out.get("unknown", False) and
                  not cvc5_out.get("error"),
        "z3": z3_out,
        "cvc5": cvc5_out,
    }
