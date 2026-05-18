"""Cross-language canonical-form fixture conformance tests.

These tests are the **load-bearing pins** behind RFC 0002 Phase E9
(cross-language read APIs). They verify that the Python reference
canonical encoder produces byte-equivalent output to what the
committed fixtures expect, AND that the HMAC-SHA256 signatures over
those bytes match the committed hex digests.

Why this matters:

- The fixtures are the contract Rust / JS / future-language ports must
  satisfy to claim conformance. Drift in the Python emitter would
  silently break that contract.
- The canonical form is the only thing standing between
  "this signature verifies on the box that produced it" and "this
  signature verifies on every box, in every language, forever."

If any test in this file fails, STOP. Either the fixtures are stale
(re-run ``python -m tests.canonical_form._generate_fixtures`` and
review the diff) or the canonical encoder regressed. The latter is a
major-version-bump concern per SCHEMAS.md.
"""
from __future__ import annotations

import hashlib
import hmac
import json
from pathlib import Path

import pytest

from ophamin.measuring.proof.record import _canonical
from tests.canonical_form._generate_fixtures import (
    TEST_KEY,
    _canonical as _generator_canonical,
)


_FIXTURES_DIR = Path(__file__).parent / "canonical_form"

# Stems pinned explicitly so accidentally-added artefacts don't silently
# become part of the contract. To add a new fixture, append the stem
# here and regenerate.
_FIXTURE_STEMS = ("numerical_edge", "simple", "unicode")


def _read_input(stem: str) -> dict:
    return json.loads((_FIXTURES_DIR / f"{stem}.input.json").read_text(encoding="utf-8"))


def _read_canonical_bytes(stem: str) -> bytes:
    return (_FIXTURES_DIR / f"{stem}.canonical.bytes").read_bytes()


def _read_hmac_hex(stem: str) -> str:
    return (_FIXTURES_DIR / f"{stem}.hmac_sha256.hex").read_text(encoding="utf-8").strip()


# --------------------------------------------------------------------------
# Conformance — production encoder matches committed fixture bytes
# --------------------------------------------------------------------------


@pytest.mark.parametrize("stem", _FIXTURE_STEMS)
def test_production_canonical_matches_fixture_bytes(stem: str) -> None:
    """Production ``_canonical`` MUST produce exactly the fixture bytes.

    Drift here means an Ophamin emitter change broke the
    cross-language signature compatibility contract. That is a
    MAJOR-version concern, not a minor fix.
    """
    obj = _read_input(stem)
    expected = _read_canonical_bytes(stem)
    actual = _canonical(obj).encode("utf-8")
    assert actual == expected, (
        f"canonical-form drift on {stem!r}:\n"
        f"  expected ({len(expected)}B): {expected!r}\n"
        f"  actual   ({len(actual)}B): {actual!r}"
    )


@pytest.mark.parametrize("stem", _FIXTURE_STEMS)
def test_hmac_matches_fixture(stem: str) -> None:
    """HMAC-SHA256 of canonical bytes under the test key matches the fixture.

    Failure means either the canonical bytes drifted (the prior test
    would also fail) or the HMAC primitive itself drifted.
    """
    expected_hex = _read_hmac_hex(stem)
    canonical_bytes = _read_canonical_bytes(stem)
    actual_hex = hmac.new(TEST_KEY, canonical_bytes, hashlib.sha256).hexdigest()
    assert actual_hex == expected_hex, (
        f"HMAC drift on {stem!r}:\n"
        f"  expected: {expected_hex}\n"
        f"  actual:   {actual_hex}"
    )


# --------------------------------------------------------------------------
# Inline reference — generator's _canonical agrees with production's
# --------------------------------------------------------------------------


@pytest.mark.parametrize("stem", _FIXTURE_STEMS)
def test_generator_reference_matches_production_canonical(stem: str) -> None:
    """The generator-script-inlined ``_canonical`` MUST agree with the
    production one byte-for-byte.

    The inline copy exists so the generator can run with no package
    dependency. If they ever drift, the generator could quietly emit
    fixtures that the production code can never reproduce.
    """
    obj = _read_input(stem)
    assert _canonical(obj) == _generator_canonical(obj)


# --------------------------------------------------------------------------
# Spec-rule coverage — every R1–R11 rule has at least one fixture pin
# --------------------------------------------------------------------------


def test_unicode_fixture_escapes_non_ascii_keys() -> None:
    """R6: a non-ASCII KEY in the source dict is \\uXXXX-escaped in the
    canonical bytes (not emitted as UTF-8 multi-byte).
    """
    data = _read_canonical_bytes("unicode")
    # The key was "ключ" (Cyrillic 'klyuch'); under R6 it must appear in
    # the canonical bytes as the escape sequence.
    assert b"\\u043a\\u043b\\u044e\\u0447" in data
    # And the raw UTF-8 bytes of "ключ" MUST NOT appear.
    assert "ключ".encode("utf-8") not in data


def test_unicode_fixture_uses_utf16_surrogate_for_supplementary_plane() -> None:
    """R6 supplementary-plane rule: 🚀 (U+1F680) → ``\\ud83d\\ude80``."""
    data = _read_canonical_bytes("unicode")
    assert b"\\ud83d\\ude80" in data


def test_numerical_edge_fixture_preserves_negative_zero() -> None:
    """R5: -0.0 must survive as the literal ``-0.0``."""
    data = _read_canonical_bytes("numerical_edge")
    assert b'"neg_zero_float":-0.0,' in data


def test_numerical_edge_fixture_positive_exponent_carries_plus_sign() -> None:
    """R5: 1e20 → ``1e+20`` (explicit + sign)."""
    data = _read_canonical_bytes("numerical_edge")
    assert b'"large_pos":1e+20,' in data


def test_numerical_edge_fixture_negative_exponent_is_two_digit_padded() -> None:
    """R5: 1e-7 → ``1e-07`` (2-digit zero-padded exponent)."""
    data = _read_canonical_bytes("numerical_edge")
    assert b'"small_neg_exp":1e-07,' in data


def test_numerical_edge_fixture_zero_float_has_decimal_point() -> None:
    """R5: 0.0 → ``0.0`` (trailing .0 distinguishes from int 0)."""
    data = _read_canonical_bytes("numerical_edge")
    assert b'"zero_float":0.0' in data
    assert b'"zero_int":0' in data
    # The integer zero MUST NOT carry a decimal point.
    assert b'"zero_int":0.0' not in data


def test_simple_fixture_keys_are_sorted_at_every_level() -> None:
    """R3: object keys appear in lexicographic byte order, recursively."""
    text = _read_canonical_bytes("simple").decode("utf-8")
    # Top-level: a_integer < list < m_float < nested < w_null < x_false < y_true < z_string
    pos_a = text.index('"a_integer"')
    pos_list = text.index('"list"')
    pos_m = text.index('"m_float"')
    pos_nested = text.index('"nested"')
    pos_w = text.index('"w_null"')
    pos_x = text.index('"x_false"')
    pos_y = text.index('"y_true"')
    pos_z = text.index('"z_string"')
    assert pos_a < pos_list < pos_m < pos_nested < pos_w < pos_x < pos_y < pos_z

    # Nested: inner_a before inner_b
    assert text.index('"inner_a"') < text.index('"inner_b"')


def test_simple_fixture_uses_lowercase_null_true_false() -> None:
    """R7: null / true / false are lowercase."""
    data = _read_canonical_bytes("simple")
    assert b'"w_null":null,' in data
    assert b'"x_false":false,' in data
    assert b'"y_true":true,' in data
    # No capitalized variants
    assert b"None" not in data
    assert b"True" not in data
    assert b"False" not in data


def test_simple_fixture_has_no_whitespace_in_separators() -> None:
    """R2: no whitespace between tokens, including no space after colons."""
    text = _read_canonical_bytes("simple").decode("utf-8")
    # No ": " or ", " sequences anywhere in the canonical bytes.
    assert ": " not in text
    assert ", " not in text


def test_all_fixtures_round_trip_via_python_json() -> None:
    """Sanity: every committed canonical-bytes file is itself valid JSON.

    A canonical byte stream must always be valid standard JSON
    (modulo NaN/Inf which our fixtures don't use). This guards
    against accidentally checking in a malformed byte stream.
    """
    for stem in _FIXTURE_STEMS:
        canonical_bytes = _read_canonical_bytes(stem)
        parsed = json.loads(canonical_bytes.decode("utf-8"))
        # And re-canonicalizing the parsed value reproduces the bytes
        # (idempotence of canonicalization).
        re_canonical = _canonical(parsed).encode("utf-8")
        assert re_canonical == canonical_bytes, (
            f"canonicalization not idempotent on fixture {stem!r}"
        )


# --------------------------------------------------------------------------
# Catalogue completeness — every fixture stem on disk is tested
# --------------------------------------------------------------------------


def test_fixture_catalogue_matches_disk() -> None:
    """Every stem on disk must be in ``_FIXTURE_STEMS`` and vice versa.

    Catches the failure mode where a new fixture lands on disk but
    nobody added its stem to the catalogue, so it is silently
    untested.
    """
    disk_stems = {
        path.name.removesuffix(".input.json")
        for path in _FIXTURES_DIR.glob("*.input.json")
    }
    catalogue_stems = set(_FIXTURE_STEMS)
    assert disk_stems == catalogue_stems, (
        f"fixture stems on disk {sorted(disk_stems)} differ from "
        f"catalogue {sorted(catalogue_stems)}. Update _FIXTURE_STEMS "
        f"if the divergence is intentional."
    )


def test_each_fixture_has_all_three_artefacts() -> None:
    """Each stem needs input.json + canonical.bytes + hmac_sha256.hex."""
    for stem in _FIXTURE_STEMS:
        for suffix in (".input.json", ".canonical.bytes", ".hmac_sha256.hex"):
            path = _FIXTURES_DIR / f"{stem}{suffix}"
            assert path.exists(), f"missing {path}"
            assert path.stat().st_size > 0, f"empty {path}"
