"""Generate the canonical-form cross-language test fixtures.

Run manually after editing _FIXTURES below:

    python -m tests.canonical_form._generate_fixtures

This script is NOT run automatically by CI — the generated artefacts
are committed to the repo and treated as ground truth. CI's job is
to verify they still pass via ``test_canonical_form_fixtures.py``.

The fixtures sit inside the **portable subset** of the canonical form:
no NaN, no Infinity, no non-JSON-native values. See the directory's
README for the full contract.
"""
from __future__ import annotations

import hashlib
import hmac
import json
from pathlib import Path
from typing import Any


_HERE = Path(__file__).parent

# The test key is the same for every fixture and the same as documented
# in tests/canonical_form/README.md.
TEST_KEY: bytes = b"ophamin-canonical-test-key-v1"


# Stems map to the input dicts that get canonicalized.
# Keep these portable: JSON-native types only.
_FIXTURES: dict[str, dict[str, Any]] = {
    # ------------------------------------------------------------------
    # simple — basic types + load-bearing key-sort behaviour
    # ------------------------------------------------------------------
    "simple": {
        # Keys deliberately out of order on input; encoder must sort them.
        "z_string": "ophamin",
        "a_integer": 42,
        "m_float": 3.14159,
        "y_true": True,
        "x_false": False,
        "w_null": None,
        "list": [1, 2, 3],
        "nested": {
            "inner_b": 2,
            "inner_a": 1,
        },
    },
    # ------------------------------------------------------------------
    # unicode — multi-script strings + non-ASCII key + emoji (surrogate)
    # ------------------------------------------------------------------
    "unicode": {
        "ascii_only": "hello world",
        "latin_supp": "café résumé",
        "cyrillic": "привет",
        "cjk": "字幕",
        # Emoji above U+FFFF → must be emitted as UTF-16 surrogate pair.
        "emoji": "🚀",
        # Non-ASCII KEY (must be \uXXXX-escaped per R6 and sort by
        # Python's < operator on the original code-point string).
        "ключ": "value",
    },
    # ------------------------------------------------------------------
    # numerical_edge — the float repr() cases that trip cross-language
    # ports most often
    # ------------------------------------------------------------------
    "numerical_edge": {
        # Trailing .0 must always be present for floats.
        "zero_float": 0.0,
        # Negative zero preserved as a distinct value.
        "neg_zero_float": -0.0,
        # Integer stays integer; no decimal point.
        "zero_int": 0,
        # Large positive exponent → "1e+20" (explicit +).
        "large_pos": 1e20,
        # Small negative exponent → "1e-07" (2-digit zero-padded).
        "small_neg_exp": 1e-7,
        # Shortest-round-trip float repr.
        "pi": 3.14159,
        # Negative
        "neg_value": -2.5,
    },
    # ------------------------------------------------------------------
    # deeply_nested — exercises recursive key sort + deep nesting +
    # arrays-of-objects-of-arrays. Each level adds an indirection a
    # cross-language port has to traverse correctly.
    # ------------------------------------------------------------------
    "deeply_nested": {
        "level1": {
            "level2": {
                "level3": {
                    "level4": {
                        "list": [1, 2, [3, 4, [5, 6]]],
                        "value": 42,
                    },
                },
            },
        },
        "siblings": [
            {"a": 1, "b": {"c": 2, "d": {"e": 3}}},
            {"a": 4, "b": {"c": 5, "d": {"e": 6}}},
        ],
        "mixed_array_levels": [
            [],
            [[]],
            [[[]]],
            [[[[]]]],
        ],
    },
    # ------------------------------------------------------------------
    # boundary_cases — empty containers, control chars in strings,
    # special characters that need escape under R6, and a 200-char
    # ASCII string. Targets the corners of R6 + R8 + R9 a cross-
    # language port is most likely to under-handle.
    # ------------------------------------------------------------------
    "boundary_cases": {
        # Empty containers
        "empty_object": {},
        "empty_array": [],
        "nested_empty": {"empty_inner_array": []},
        # Long ASCII string (200 'a' chars)
        "long_ascii": "a" * 200,
        # JSON special-character escapes per R6
        "json_special_escapes": "\"\\/\b\f\n\r\t",
        # Control characters U+0000..U+001F that need \uXXXX (R6)
        "control_chars": "\x00\x01\x02\x05\x1f",
        # Edge: a key that's a single space (printable ASCII)
        " ": "key-with-single-space",
        # Edge: empty string as a value
        "empty_string_value": "",
    },
}


def _canonical(obj: Any) -> str:
    """Reference canonical-form encoder.

    Identical to ``ophamin.measuring.proof.record._canonical`` but
    inlined here so this generator script has no run-time dependency
    on the package code (which lets it run before the package is
    importable, e.g. in fresh worktrees).
    """
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), default=str)


def _write_fixture(stem: str, obj: dict[str, Any]) -> tuple[Path, Path, Path]:
    """Write the three fixture artefacts for ``stem`` and return their paths."""
    input_path = _HERE / f"{stem}.input.json"
    bytes_path = _HERE / f"{stem}.canonical.bytes"
    hmac_path = _HERE / f"{stem}.hmac_sha256.hex"

    # input.json — pretty-printed so humans can read it. Cross-language
    # ports parse via their own JSON library, NOT via the canonical
    # encoder, so the input file's formatting does not affect the test.
    input_path.write_text(
        json.dumps(obj, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )

    # canonical.bytes — the exact bytes the canonical encoder produces.
    canonical_str = _canonical(obj)
    canonical_bytes = canonical_str.encode("utf-8")
    bytes_path.write_bytes(canonical_bytes)

    # hmac_sha256.hex — HMAC-SHA256 of canonical_bytes under TEST_KEY.
    digest = hmac.new(TEST_KEY, canonical_bytes, hashlib.sha256).hexdigest()
    hmac_path.write_text(digest + "\n", encoding="utf-8")

    return input_path, bytes_path, hmac_path


def main() -> None:
    for stem in sorted(_FIXTURES):
        obj = _FIXTURES[stem]
        input_p, bytes_p, hmac_p = _write_fixture(stem, obj)
        print(f"[{stem}]")
        print(f"  input:     {input_p.name} ({input_p.stat().st_size} B)")
        print(f"  canonical: {bytes_p.name} ({bytes_p.stat().st_size} B)")
        print(f"  hmac_sha256: {hmac_p.read_text().strip()}")


if __name__ == "__main__":
    main()
