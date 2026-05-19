"""Tests for the bundle_browser module — tree walk + path-safe file serving.

Critical pins:
- bundle_tree() returns the right shape on a synthetic tree
- bundle_tree() handles missing root / empty root without raising
- safe_bundle_file_path() refuses every form of traversal attack
- safe_bundle_file_path() refuses any filename not in ALLOWED_BUNDLE_FILES
- safe_bundle_file_path() refuses symlinks that escape the proofs root
"""

from __future__ import annotations

from pathlib import Path

import pytest

from ophamin.http_api.bundle_browser import (
    ALLOWED_BUNDLE_FILES,
    BundlePathError,
    bundle_tree,
    safe_bundle_file_path,
)


# --------------------------------------------------------------------------
# Fixture — a synthetic proofs/ tree with two tiers + three bundles
# --------------------------------------------------------------------------

@pytest.fixture
def synthetic_proofs(tmp_path: Path) -> Path:
    """Build a small but realistic synthetic proofs/ tree."""
    paths = [
        # engineering/throughput-ceiling/2026-05-14_validated_9989f42bc8f2/proof.json
        "engineering/throughput-ceiling/2026-05-14_validated_9989f42bc8f2/proof.json",
        "engineering/throughput-ceiling/2026-05-14_validated_9989f42bc8f2/proof.md",
        "engineering/throughput-ceiling/2026-05-14_validated_9989f42bc8f2/proof.pdf",
        # engineering/throughput-ceiling/2026-05-15_inconclusive_aabbccddeeff/proof.json
        "engineering/throughput-ceiling/2026-05-15_inconclusive_aabbccddeeff/proof.json",
        "engineering/throughput-ceiling/2026-05-15_inconclusive_aabbccddeeff/proof.html",
        # scientific/immune-siege/2026-05-15_refuted_112233445566/proof.json
        "scientific/concentrated-immune-siege/2026-05-15_refuted_112233445566/proof.json",
        "scientific/concentrated-immune-siege/2026-05-15_refuted_112233445566/proof.tex",
        # noise — should NOT show up in the tree
        "scientific/concentrated-immune-siege/2026-05-15_refuted_112233445566/.pdfbuild/proof.aux",
        "scientific/concentrated-immune-siege/2026-05-15_refuted_112233445566/random_extra.txt",
        # malformed bundle dir name — should NOT show up
        "scientific/legit-scenario/not_a_valid_bundle_name/proof.json",
        # Capital-letter tier — should NOT show up
        "ENGINEERING/ScreamingTier/2026-05-15_validated_deadbeefcafe/proof.json",
    ]
    for p in paths:
        full = tmp_path / p
        full.parent.mkdir(parents=True, exist_ok=True)
        full.write_text("{}")
    return tmp_path


# --------------------------------------------------------------------------
# bundle_tree()
# --------------------------------------------------------------------------

def test_bundle_tree_returns_expected_shape(synthetic_proofs):
    tree = bundle_tree(synthetic_proofs)
    assert set(tree.keys()) == {"tiers", "totals"}
    assert isinstance(tree["tiers"], list)
    # 2 valid tiers — ENGINEERING (caps) is filtered out
    assert tree["totals"]["tiers"] == 2
    # 2 valid scenarios: throughput-ceiling + concentrated-immune-siege
    # (legit-scenario has no valid bundle children → excluded)
    assert tree["totals"]["scenarios"] == 2
    assert tree["totals"]["bundles"] == 3
    assert tree["totals"]["verdicts"] == {
        "validated": 1, "inconclusive": 1, "refuted": 1,
    }


def test_bundle_tree_lists_bundles_in_sorted_order(synthetic_proofs):
    tree = bundle_tree(synthetic_proofs)
    eng = next(t for t in tree["tiers"] if t["tier"] == "engineering")
    sc = next(s for s in eng["scenarios"] if s["scenario"] == "throughput-ceiling")
    # sort by dir-name asc — date-first format makes this also chronological
    dates = [b["date"] for b in sc["bundles"]]
    assert dates == sorted(dates)


def test_bundle_tree_files_only_canonical_proof_files(synthetic_proofs):
    tree = bundle_tree(synthetic_proofs)
    # Verify the noisy bundle (random_extra.txt + .pdfbuild/) only shows
    # proof.json + proof.tex, not the noise.
    sc_tier = next(t for t in tree["tiers"] if t["tier"] == "scientific")
    sc = next(s for s in sc_tier["scenarios"]
              if s["scenario"] == "concentrated-immune-siege")
    bundle = sc["bundles"][0]
    assert set(bundle["files"]) == {"proof.json", "proof.tex"}
    assert all(name in ALLOWED_BUNDLE_FILES for name in bundle["files"])


def test_bundle_tree_handles_missing_root(tmp_path):
    """When proofs_root doesn't exist, return an empty tree — no raise."""
    tree = bundle_tree(tmp_path / "does-not-exist")
    assert tree["tiers"] == []
    assert tree["totals"]["bundles"] == 0


def test_bundle_tree_handles_empty_root(tmp_path):
    tree = bundle_tree(tmp_path)
    assert tree["tiers"] == []
    assert tree["totals"]["bundles"] == 0


def test_bundle_tree_skips_invalid_tier_names(synthetic_proofs):
    """ENGINEERING (capitals) doesn't match _PATH_COMPONENT_RE; it must
    NOT show up in the tree."""
    tree = bundle_tree(synthetic_proofs)
    tiers = {t["tier"] for t in tree["tiers"]}
    assert "ENGINEERING" not in tiers


def test_bundle_tree_skips_malformed_bundle_dirs(synthetic_proofs):
    """The not_a_valid_bundle_name dir under legit-scenario must NOT
    appear — _BUNDLE_DIR_RE refuses it. Since legit-scenario then has
    zero valid bundles, the scenario itself is also pruned."""
    tree = bundle_tree(synthetic_proofs)
    sc_tier = next(t for t in tree["tiers"] if t["tier"] == "scientific")
    scenarios = {s["scenario"] for s in sc_tier["scenarios"]}
    assert "legit-scenario" not in scenarios


def test_bundle_tree_returns_paths_relative_to_root(synthetic_proofs):
    """Each bundle's `path` must be relative to proofs_root so the
    URL the GUI builds doesn't leak the absolute filesystem path."""
    tree = bundle_tree(synthetic_proofs)
    for t in tree["tiers"]:
        for s in t["scenarios"]:
            for b in s["bundles"]:
                # path must start with the tier name + be three-segment
                assert b["path"].startswith(t["tier"])
                assert len(Path(b["path"]).parts) == 3


# --------------------------------------------------------------------------
# safe_bundle_file_path() — path-traversal protection
# --------------------------------------------------------------------------

def test_safe_path_resolves_legitimate_file(synthetic_proofs):
    p = safe_bundle_file_path(
        synthetic_proofs,
        "engineering", "throughput-ceiling",
        "2026-05-14_validated_9989f42bc8f2", "proof.json",
    )
    assert p.is_file()
    assert p.name == "proof.json"


def test_safe_path_refuses_dotdot_in_tier(synthetic_proofs):
    with pytest.raises(BundlePathError, match="invalid tier"):
        safe_bundle_file_path(
            synthetic_proofs, "../etc", "throughput-ceiling",
            "2026-05-14_validated_9989f42bc8f2", "proof.json",
        )


def test_safe_path_refuses_dotdot_in_scenario(synthetic_proofs):
    with pytest.raises(BundlePathError, match="invalid scenario"):
        safe_bundle_file_path(
            synthetic_proofs, "engineering", "../bad",
            "2026-05-14_validated_9989f42bc8f2", "proof.json",
        )


def test_safe_path_refuses_dotdot_in_bundle(synthetic_proofs):
    with pytest.raises(BundlePathError, match="invalid bundle"):
        safe_bundle_file_path(
            synthetic_proofs, "engineering", "throughput-ceiling",
            "../../etc/passwd", "proof.json",
        )


def test_safe_path_refuses_filename_with_slashes(synthetic_proofs):
    with pytest.raises(BundlePathError, match="refusing to serve"):
        safe_bundle_file_path(
            synthetic_proofs, "engineering", "throughput-ceiling",
            "2026-05-14_validated_9989f42bc8f2", "../proof.json",
        )


def test_safe_path_refuses_disallowed_filename(synthetic_proofs):
    """Even a non-traversal filename like 'random_extra.txt' is refused
    — we only serve the canonical five."""
    with pytest.raises(BundlePathError, match="refusing to serve"):
        safe_bundle_file_path(
            synthetic_proofs, "scientific", "concentrated-immune-siege",
            "2026-05-15_refuted_112233445566", "random_extra.txt",
        )


def test_safe_path_refuses_capital_tier(synthetic_proofs):
    """Tier name must be lowercase per the regex."""
    with pytest.raises(BundlePathError, match="invalid tier"):
        safe_bundle_file_path(
            synthetic_proofs, "ENGINEERING", "throughput-ceiling",
            "2026-05-14_validated_9989f42bc8f2", "proof.json",
        )


def test_safe_path_refuses_unknown_verdict_in_bundle(synthetic_proofs):
    with pytest.raises(BundlePathError, match="invalid bundle"):
        safe_bundle_file_path(
            synthetic_proofs, "engineering", "throughput-ceiling",
            "2026-05-14_bogus_9989f42bc8f2", "proof.json",
        )


def test_safe_path_refuses_short_hash_too_short(synthetic_proofs):
    """The hash component must be ≥ 8 hex chars."""
    with pytest.raises(BundlePathError, match="invalid bundle"):
        safe_bundle_file_path(
            synthetic_proofs, "engineering", "throughput-ceiling",
            "2026-05-14_validated_abc", "proof.json",
        )


def test_safe_path_raises_not_found_when_file_missing(synthetic_proofs):
    """A request that passes all the regex gates but refers to a
    non-existent file gets FileNotFoundError, not BundlePathError —
    the API layer will turn this into a 404."""
    # synthetic_proofs fixture didn't write proof.html for this bundle.
    with pytest.raises(FileNotFoundError):
        safe_bundle_file_path(
            synthetic_proofs, "engineering", "throughput-ceiling",
            "2026-05-14_validated_9989f42bc8f2", "proof.html",
        )


def test_safe_path_refuses_symlink_escape(synthetic_proofs, tmp_path):
    """Construct a bundle with a symlinked proof.pdf that points OUTSIDE
    the proofs root; safe_bundle_file_path must refuse to serve it."""
    target_outside = tmp_path.parent / "secret_outside.bin"
    if not target_outside.exists():
        target_outside.write_text("sensitive")
    bundle_dir = synthetic_proofs / "engineering" / "throughput-ceiling" / \
                 "2026-05-14_validated_9989f42bc8f2"
    symlink = bundle_dir / "proof.pdf"
    if symlink.exists() or symlink.is_symlink():
        symlink.unlink()
    symlink.symlink_to(target_outside)
    with pytest.raises(BundlePathError, match="escapes proofs root"):
        safe_bundle_file_path(
            synthetic_proofs, "engineering", "throughput-ceiling",
            "2026-05-14_validated_9989f42bc8f2", "proof.pdf",
        )


def test_allowed_bundle_files_is_exact_set():
    """The canonical five — refusing to serve anything else."""
    assert ALLOWED_BUNDLE_FILES == frozenset({
        "proof.json", "proof.md", "proof.html", "proof.tex", "proof.pdf",
    })
