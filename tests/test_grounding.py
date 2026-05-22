"""Tests for the grounding verifier — the fix that makes the gate real.

Offline-deterministic tests cover classification, the local-papers
(offline-rigorous) path, and the verify_grounding enforcement logic. The
network paths (arXiv / Crossref) are exercised resiliently: a real id must
NOT come back ``unresolved`` (it's either resolved, or unreachable when
offline), and a fabricated id must NOT come back ``resolved``.
"""

from __future__ import annotations

from ophamin.authoring.grounding import (
    RESOLVED,
    UNREACHABLE,
    UNRESOLVED,
    classify_ref,
    resolve_ref,
    verify_grounding,
)


class TestClassify:
    def test_arxiv_forms(self):
        assert classify_ref("2402.02668") == "arxiv"
        assert classify_ref("arXiv:2402.02668") == "arxiv"
        assert classify_ref("https://arxiv.org/abs/2402.02668") == "arxiv"

    def test_doi_forms(self):
        assert classify_ref("10.1145/3651890.3672255") == "doi"
        assert classify_ref("https://doi.org/10.1145/3651890.3672255") == "doi"

    def test_url(self):
        assert classify_ref("https://example.com/paper") == "url"

    def test_unknown(self):
        assert classify_ref("asdf") == "unknown"
        assert classify_ref("") == "unknown"


class TestLocalPapers:
    def _papers(self, tmp_path):
        (tmp_path / "tononi-2004-iit.pdf").write_bytes(b"%PDF-1.4 real bytes")
        return tmp_path

    def test_local_filename_match(self, tmp_path):
        pd = self._papers(tmp_path)
        r = resolve_ref("tononi-2004-iit.pdf", papers_dir=pd)
        assert r.status == RESOLVED
        assert r.kind == "local"
        assert r.title == "tononi-2004-iit"

    def test_local_slug_match(self, tmp_path):
        # "Tononi 2004" slug-matches tononi-2004-iit.pdf — offline.
        pd = self._papers(tmp_path)
        r = resolve_ref("Tononi 2004", papers_dir=pd)
        assert r.status == RESOLVED
        assert r.kind == "local"

    def test_local_path(self, tmp_path):
        pd = self._papers(tmp_path)
        r = resolve_ref(str(pd / "tononi-2004-iit.pdf"))
        assert r.status == RESOLVED

    def test_empty_local_file_not_resolved(self, tmp_path):
        (tmp_path / "empty.pdf").write_bytes(b"")
        r = resolve_ref(str(tmp_path / "empty.pdf"))
        assert r.status != RESOLVED


class TestVerifyEnforcement:
    def test_all_local_resolved_verifies(self, tmp_path):
        (tmp_path / "a.pdf").write_bytes(b"x")
        (tmp_path / "b.pdf").write_bytes(b"y")
        v = verify_grounding(["a.pdf", "b.pdf"], papers_dir=tmp_path)
        assert v["verified"] is True
        assert v["n_resolved"] == 2 and v["n_unresolved"] == 0

    def test_one_fabricated_local_fails(self, tmp_path):
        (tmp_path / "a.pdf").write_bytes(b"x")
        # "fabricated-9999" is unknown (no file, not arxiv/doi/url) → not resolved
        v = verify_grounding(["a.pdf", "fabricated-paper-9999"], papers_dir=tmp_path)
        assert v["verified"] is False

    def test_no_grounding_not_verified(self, tmp_path):
        v = verify_grounding([], papers_dir=tmp_path)
        assert v["verified"] is False
        assert v["n_resolved"] == 0


class TestNetworkResilient:
    def test_real_arxiv_not_unresolved(self):
        # Resilient to offline: a real id is resolved OR unreachable, never
        # falsely 'unresolved'.
        r = resolve_ref("2402.02668", timeout=12)
        assert r.status in (RESOLVED, UNREACHABLE)
        if r.status == RESOLVED:
            assert r.title  # a real title was read from arXiv

    def test_fabricated_arxiv_not_resolved(self):
        r = resolve_ref("9999.99999", timeout=12)
        assert r.status != RESOLVED  # unresolved (online) or unreachable (offline)
