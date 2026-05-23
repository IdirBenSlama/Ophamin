"""Tests for the grounded *discover* stage + the toolkit-index persistence.

Pins the load-bearing property: metadata is AUTHORITATIVE from PyPI, never from
a caller. A name that isn't on PyPI is dropped; an invalid name never reaches
the network; a transport failure is loud (not a silent empty result). Plus the
register->persist round-trip that closes the loop into the unified toolkit index.

All offline — the HTTP fetch is injected; no test touches the real network.
"""

from __future__ import annotations

import json

import pytest

from ophamin.interop.tool_acquisition import (
    CAUTION,
    RECOMMEND,
    acquisition_plan,
    evaluate_candidate,
    register_acquired_tool,
)
from ophamin.interop.tool_discovery import (
    PyPIError,
    PyPINotFound,
    discover_candidates,
    enrich_candidate,
    github_owner_repo,
    resolve_pypi_candidate,
)
from ophamin.interop.toolkit_registry import (
    ToolkitConfigError,
    persist_toolkit_entry,
    toolkit_registry,
)


def _pypi_json(
    name: str = "ruptures",
    *,
    version: str = "1.1.9",
    license_: str = "BSD-2-Clause",
    classifiers: list[str] | None = None,
    summary: str = "change-point detection",
    home_page: str = "https://github.com/deepcharles/ruptures",
    project_urls: dict[str, str] | None = None,
    upload: str = "2024-03-01T12:00:00.000000Z",
) -> dict:
    """A minimal but realistic PyPI ``/pypi/<name>/json`` document."""
    info = {
        "name": name,
        "version": version,
        "license": license_,
        "summary": summary,
        "home_page": home_page,
        "project_urls": project_urls or {},
        "classifiers": classifiers or [],
    }
    return {
        "info": info,
        "releases": {version: [{"upload_time_iso_8601": upload}]} if upload else {},
        "urls": [{"upload_time_iso_8601": upload}] if upload else [],
    }


def _fetch_ok(doc: dict):
    def _f(url: str, timeout_s: float) -> dict:
        return doc
    return _f


def _fetch_map(mapping: dict[str, dict]):
    """Fetch by package name parsed from the URL; unknown names 404."""
    def _f(url: str, timeout_s: float) -> dict:
        name = url.rstrip("/").split("/")[-2]
        if name in mapping:
            return mapping[name]
        raise PyPINotFound(url)
    return _f


class TestResolve:
    def test_parses_authoritative_metadata(self):
        c = resolve_pypi_candidate("ruptures", fetch=_fetch_ok(_pypi_json()))
        assert c is not None
        assert c.name == "ruptures"
        assert c.version == "1.1.9"
        assert c.license == "BSD-2-Clause"
        assert c.source == "pypi"
        assert c.last_release == "2024-03-01"
        assert "github" in c.homepage

    def test_license_falls_back_to_classifiers_when_field_is_full_text(self):
        doc = _pypi_json(
            license_="X" * 200,  # a full license text dumped into the field
            classifiers=["License :: OSI Approved :: MIT License"],
        )
        c = resolve_pypi_candidate("foo", fetch=_fetch_ok(doc))
        assert c is not None
        assert c.license == "MIT License"

    def test_homepage_from_project_urls_when_no_home_page(self):
        doc = _pypi_json(home_page="", project_urls={"Source": "https://ex.org/x"})
        c = resolve_pypi_candidate("foo", fetch=_fetch_ok(doc))
        assert c is not None
        assert c.homepage == "https://ex.org/x"

    def test_not_found_returns_none(self):
        def _f(url, t):
            raise PyPINotFound(url)
        assert resolve_pypi_candidate("nope", fetch=_f) is None

    def test_invalid_name_never_fetches(self):
        called: list[str] = []

        def _f(url, t):
            called.append(url)
            return {}
        assert resolve_pypi_candidate("evil; rm -rf /", fetch=_f) is None
        assert called == []  # guarded before any network call

    def test_hints_are_applied(self):
        c = resolve_pypi_candidate(
            "scikit-learn", import_name="sklearn", fit_note="ml lib",
            fetch=_fetch_ok(_pypi_json(name="scikit-learn")),
        )
        assert c is not None
        assert c.import_name == "sklearn"
        assert c.fit_note == "ml lib"


class TestDiscover:
    def test_partitions_found_and_missing(self):
        mapping = {
            "ruptures": _pypi_json("ruptures"),
            "statsmodels": _pypi_json("statsmodels", license_="BSD"),
        }
        disc = discover_candidates(
            "change points", ["ruptures", "statsmodels", "doesnotexist123"],
            fetch=_fetch_map(mapping),
        )
        assert set(disc.found) == {"ruptures", "statsmodels"}
        assert disc.not_found == ("doesnotexist123",)
        assert len(disc.candidates) == 2

    def test_dedups_names(self):
        mapping = {"ruptures": _pypi_json("ruptures")}
        disc = discover_candidates(
            "x", ["ruptures", "ruptures"], fetch=_fetch_map(mapping))
        assert len(disc.candidates) == 1

    def test_hints_threaded_through(self):
        mapping = {"scikit-learn": _pypi_json("scikit-learn")}
        disc = discover_candidates(
            "x", ["scikit-learn"],
            hints={"scikit-learn": {"import_name": "sklearn", "fit_note": "ml"}},
            fetch=_fetch_map(mapping),
        )
        assert disc.candidates[0].import_name == "sklearn"
        assert disc.candidates[0].fit_note == "ml"

    def test_fit_note_defaults_to_need(self):
        mapping = {"ruptures": _pypi_json("ruptures")}
        disc = discover_candidates(
            "detect change points", ["ruptures"], fetch=_fetch_map(mapping))
        assert disc.candidates[0].fit_note == "detect change points"

    def test_empty_need_raises(self):
        with pytest.raises(ValueError):
            discover_candidates("  ", ["x"], fetch=_fetch_ok(_pypi_json()))

    def test_transport_error_is_loud(self):
        def _f(url, t):
            raise PyPIError("network down")
        with pytest.raises(PyPIError):
            discover_candidates("x", ["ruptures"], fetch=_f)

    def test_to_dict_shape(self):
        mapping = {"ruptures": _pypi_json("ruptures")}
        disc = discover_candidates("x", ["ruptures"], fetch=_fetch_map(mapping))
        d = disc.to_dict()
        assert d["n_candidates"] == 1
        assert d["found"] == ["ruptures"]
        assert d["candidates"][0]["name"] == "ruptures"


class TestOrchestration:
    def test_discover_then_evaluate_then_plan(self):
        doc = _pypi_json(
            "ruptures", version="1.1.9",
            classifiers=["License :: OSI Approved :: BSD License"],
        )
        disc = discover_candidates(
            "change-point detection", ["ruptures"], fetch=_fetch_ok(doc))
        cand = disc.candidates[0]
        ev = evaluate_candidate(cand)
        # permissive license, but no stars/downloads in the JSON API → honest
        # "maturity unknown" → caution (never a false RECOMMEND).
        assert ev["license_class"] == "permissive"
        assert ev["maturity_unknown"] is True
        assert ev["verdict"] == CAUTION
        plan = acquisition_plan(cand)
        assert plan["pinned"] == "ruptures==1.1.9"
        assert plan["executes"] is False


class TestPersist:
    def _entry(self):
        doc = _pypi_json(
            "ruptures", classifiers=["License :: OSI Approved :: BSD License"])
        cand = discover_candidates("x", ["ruptures"], fetch=_fetch_ok(doc)).candidates[0]
        ev = evaluate_candidate(cand)
        return register_acquired_tool(
            cand, ev, {"verified": True, "version": cand.version})

    def test_register_persist_then_registry_merges_it(self, tmp_path):
        entry = self._entry()
        path = tmp_path / "toolkits.json"
        persist_toolkit_entry(entry, path=path)
        reg = toolkit_registry(extra_path=path)
        assert "ruptures" in [t["id"] for t in reg["toolkits"]]
        assert reg["n_extra"] == 1

    def test_persist_dedups_by_id(self, tmp_path):
        entry = self._entry()
        path = tmp_path / "toolkits.json"
        persist_toolkit_entry(entry, path=path)
        persist_toolkit_entry(entry, path=path)
        data = json.loads(path.read_text())
        assert len([e for e in data if e["id"] == "ruptures"]) == 1

    def test_persist_requires_a_path(self, monkeypatch):
        monkeypatch.delenv("OPHAMIN_TOOLKITS", raising=False)
        with pytest.raises(ToolkitConfigError):
            persist_toolkit_entry({
                "id": "x", "category": "c", "role": "r",
                "homepage": "h", "docs_url": "d",
            })

    def test_persist_rejects_incomplete_entry(self, tmp_path):
        with pytest.raises(ToolkitConfigError):
            persist_toolkit_entry({"id": "x"}, path=tmp_path / "t.json")


def _enrich_fetch(*, downloads: int = 12345, stars: int = 678):
    def _f(url: str, timeout_s: float) -> dict:
        if "pypistats.org" in url:
            return {"data": {"last_day": 1, "last_week": 7, "last_month": downloads}}
        if "api.github.com" in url:
            return {"stargazers_count": stars}
        raise PyPINotFound(url)
    return _f


class TestEnrich:
    def test_github_owner_repo_parse(self):
        assert github_owner_repo("https://github.com/deepcharles/ruptures/") == (
            "deepcharles", "ruptures")
        assert github_owner_repo("https://github.com/a/b.git") == ("a", "b")
        assert github_owner_repo("https://example.org/x") is None

    def test_fills_stars_and_downloads(self):
        c = resolve_pypi_candidate(
            "ruptures",
            fetch=_fetch_ok(_pypi_json(home_page="https://github.com/deepcharles/ruptures")))
        e = enrich_candidate(c, fetch=_enrich_fetch(downloads=99999, stars=1700))
        assert e.downloads_month == 99999
        assert e.stars == 1700

    def test_no_github_homepage_leaves_stars_none(self):
        c = resolve_pypi_candidate(
            "foo", fetch=_fetch_ok(_pypi_json(name="foo", home_page="https://ex.org/foo")))
        e = enrich_candidate(c, fetch=_enrich_fetch())
        assert e.stars is None  # no GitHub URL to parse
        assert e.downloads_month == 12345  # pypistats still works

    def test_failure_leaves_none_never_raises(self):
        def _f(url, t):
            raise PyPIError("rate limited")
        c = resolve_pypi_candidate(
            "ruptures", fetch=_fetch_ok(_pypi_json(home_page="https://github.com/a/b")))
        e = enrich_candidate(c, fetch=_f)  # advisory: must not raise
        assert e.stars is None
        assert e.downloads_month is None

    def test_enriched_candidate_can_recommend(self):
        # the payoff: with stars+downloads, a permissive mature tool RECOMMENDs
        c = resolve_pypi_candidate("ruptures", fetch=_fetch_ok(_pypi_json(
            classifiers=["License :: OSI Approved :: BSD License"],
            home_page="https://github.com/deepcharles/ruptures")))
        e = enrich_candidate(c, fetch=_enrich_fetch(downloads=200000, stars=1700))
        ev = evaluate_candidate(e)
        assert ev["maturity_unknown"] is False
        assert ev["verdict"] == RECOMMEND

    def test_discover_with_enrich_threads_fetch(self):
        doc = _pypi_json(
            "ruptures", home_page="https://github.com/deepcharles/ruptures",
            classifiers=["License :: OSI Approved :: BSD License"])

        def _f(url, t):
            if "pypi.org/pypi" in url:
                return doc
            if "pypistats" in url:
                return {"data": {"last_month": 50000}}
            if "github" in url:
                return {"stargazers_count": 1700}
            raise PyPINotFound(url)

        disc = discover_candidates("change points", ["ruptures"], fetch=_f, enrich=True)
        assert disc.candidates[0].stars == 1700
        assert disc.candidates[0].downloads_month == 50000
