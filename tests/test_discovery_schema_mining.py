"""Tests for the discovery layer (Layer A of the Kimera-co-evolution stack).

Exercise the SchemaMiner / SchemaDocument / SchemaWriter without Kimera using
MockSubstrate plus hand-built CycleResults; the live Kimera-mining path is
covered by the standalone example script (no smoke test in the unit suite).
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from ophamin.seeing.discovery import (
    FieldChange,
    FieldSchema,
    SchemaDiff,
    SchemaDocument,
    SchemaMiner,
    TargetSchema,
    diff_schemas,
    write_schema_markdown,
)
from ophamin.seeing.discovery.schema_miner import (
    _content_hash_stimuli,
    _flatten,
    _summarise_value,
)
from ophamin.seeing.substrate.base import CycleResult, SubstrateUnderTest


def test_flatten_handles_nested_dicts():
    raw = {
        "halt_mode": "exhausted",
        "prime": {"composite": 506413, "p_thermo": 17, "p_identity": 29789},
        "dissonance_events": [1, 2, 3],
    }
    flat = _flatten(raw)
    # dot-paths for nested dict
    assert flat["prime.composite"] == 506413
    assert flat["prime.p_thermo"] == 17
    assert flat["halt_mode"] == "exhausted"
    # list stays as a list at the parent path (caller records lengths)
    assert isinstance(flat["dissonance_events"], list)
    assert flat["dissonance_events"] == [1, 2, 3]


def test_flatten_records_empty_dict_presence():
    raw = {"meta": {}}
    flat = _flatten(raw)
    assert flat["meta"] == {}


def test_flatten_respects_max_depth():
    deep = {"a": {"b": {"c": {"d": {"e": {"f": {"g": "too deep"}}}}}}}
    flat = _flatten(deep, max_depth=3)
    # the truncation marker shows up under the path where depth ran out
    truncations = [v for v in flat.values() if v == "<MAX_DEPTH_EXCEEDED>"]
    assert truncations, "expected at least one truncation marker"


def test_summarise_value_truncates_long_strings():
    long_str = "x" * 200
    summary = _summarise_value(long_str)
    assert isinstance(summary, str)
    assert len(summary) < 200
    assert summary.endswith("…")


def test_summarise_value_keeps_scalars():
    assert _summarise_value(42) == 42
    assert _summarise_value(3.14) == 3.14
    assert _summarise_value(True) is True
    assert _summarise_value(None) is None


def test_summarise_value_compresses_collections():
    s = _summarise_value([1, 2, 3])
    assert "len=3" in s
    d = _summarise_value({"k": "v", "x": 1})
    assert "keys=" in d


def test_content_hash_stimuli_is_deterministic_and_distinct():
    a = _content_hash_stimuli(["hello", "world"])
    b = _content_hash_stimuli(["hello", "world"])
    c = _content_hash_stimuli(["hello", "WORLD"])
    assert a == b
    assert a != c


# -- SchemaMiner end-to-end against a hand-built substrate ----------------


class _SyntheticSubstrate(SubstrateUnderTest):
    """Returns a controllable CycleResult for each stimulus.

    The miner treats every SubstrateUnderTest identically — so this stands in
    for both KimeraAdapter and MockSubstrate without depending on either.
    """

    name = "synthetic-substrate"

    def __init__(self, results_factory) -> None:
        self._factory = results_factory
        self._cycle = 0

    def reset(self) -> None:
        self._cycle = 0

    def run_cycle(self, stimulus, params=None):
        result = self._factory(stimulus, self._cycle)
        self._cycle += 1
        return result

    def run_batch(self, stimuli, params=None):
        return [self._factory(s, i) for i, s in enumerate(stimuli)]

    def git_commit(self) -> str:
        return "synthetic-deadbeef"

    def metadata(self) -> dict:
        return {"target_class": "synthetic.target.Class"}


def test_schema_miner_records_paths_and_types():
    def factory(stimulus, idx):
        return CycleResult(
            cycle_index=idx,
            success=True,
            raw={
                "halt_mode": "exhausted",
                "gwf_verdict": "cleared",
                "prime": {"composite": 100 + idx, "p_thermo": 17},
                "dissonance_events": list(range(10 + idx)),
            },
            halt_mode="exhausted",
        )

    miner = SchemaMiner(_SyntheticSubstrate(factory))
    doc = miner.mine(targets=["entity"], stimuli=["a", "b", "c"])

    assert isinstance(doc, SchemaDocument)
    assert doc.n_stimuli == 3
    entity = doc.target("entity")
    assert entity is not None
    paths = entity.field_paths()
    assert "halt_mode" in paths
    assert "gwf_verdict" in paths
    assert "prime.composite" in paths
    assert "prime.p_thermo" in paths
    assert "dissonance_events" in paths
    diss = next(f for f in entity.fields if f.path == "dissonance_events")
    assert "list" in diss.types_seen
    assert diss.sample_kind == "lengths"
    # 3 distinct lengths -> 10, 11, 12
    assert set(diss.sample_values) == {10, 11, 12}


def test_schema_miner_records_occurrence_rates():
    def factory(stimulus, idx):
        # only stimulus #0 has the "rare_field"
        raw = {"halt_mode": "exhausted"}
        if idx == 0:
            raw["rare_field"] = "once"
        return CycleResult(cycle_index=idx, success=True, raw=raw, halt_mode="exhausted")

    miner = SchemaMiner(_SyntheticSubstrate(factory))
    doc = miner.mine(targets=["entity"], stimuli=["a", "b", "c", "d", "e"])
    entity = doc.target("entity")
    assert entity is not None
    rare = next((f for f in entity.fields if f.path == "rare_field"), None)
    assert rare is not None
    assert rare.occurrence_count == 1
    assert rare.n_cycles_target == 5
    assert rare.occurrence_rate == pytest.approx(0.2)


def test_schema_miner_counts_adapter_errors():
    def factory(stimulus, idx):
        if idx == 2:
            return CycleResult(
                cycle_index=idx, success=False, raw={}, halt_mode="adapter_error"
            )
        return CycleResult(
            cycle_index=idx, success=True, raw={"k": "v"}, halt_mode="commit"
        )

    miner = SchemaMiner(_SyntheticSubstrate(factory))
    doc = miner.mine(targets=["entity"], stimuli=["a", "b", "c"])
    entity = doc.target("entity")
    assert entity is not None
    assert entity.n_cycles == 3
    assert entity.n_adapter_errors == 1
    k_field = next(f for f in entity.fields if f.path == "k")
    # adapter errors NOT in the cycle-target denominator
    assert k_field.n_cycles_target == 2


def test_schema_miner_rebinds_target_for_substrates_with_kimera_repo(tmp_path):
    """Regression: _substrate_for_target must construct a *fresh* substrate per
    target when the underlying substrate carries a ``kimera_repo`` attribute.

    Pre-2026-05-15, the miner looked for ``self.substrate.repo`` (typo'd
    attribute name); KimeraAdapter only has ``kimera_repo``, so getattr
    returned None, the rebind silently fell through to ``return self.substrate``,
    and every probed target inherited the original substrate's target. The
    live discovery probe surfaced this by reporting ~3000 identical fields
    across every target — all of them really the entity target.

    We fake a substrate with ``kimera_repo`` set and verify that calling
    _substrate_for_target("rosetta") returns a DIFFERENT instance configured
    for that target. The test never constructs a real KimeraAdapter; it just
    verifies the rebind-branch fires."""
    class _FakeKimeraAdapter:
        kimera_repo = tmp_path
        python_exe = None
        mode = "batch"
        batch_timeout = 600.0
        target = "entity"
        name = "fake"
        def reset(self): pass
        def run_cycle(self, *_args, **_kwargs):
            return CycleResult(0, True, {}, "commit")
        def run_batch(self, stimuli, *_args, **_kwargs):
            return [CycleResult(i, True, {"target_used": self.target}, "commit")
                    for i, _ in enumerate(stimuli)]
        def git_commit(self) -> str: return "fake-commit"
        def metadata(self): return {"target_class": f"fake.{self.target}.Class"}

    miner = SchemaMiner(_FakeKimeraAdapter())
    # the rebind path must hit ``kimera_repo``, not ``repo``. We can't
    # easily call KimeraAdapter from a unit test (it needs a real repo), so
    # we monkeypatch the import inside the method to a stub.
    rebind_calls: list[dict] = []
    class _StubAdapter:
        def __init__(self, kimera_repo=None, target=None, **kwargs):
            rebind_calls.append({"kimera_repo": kimera_repo, "target": target, **kwargs})
            self.target = target
            self.name = f"stub-{target}"
        def reset(self): pass
        def run_cycle(self, *a, **k):
            return CycleResult(0, True, {"target_used": self.target}, "commit")
        def run_batch(self, stimuli, *a, **k):
            return [CycleResult(i, True, {"target_used": self.target}, "commit")
                    for i, _ in enumerate(stimuli)]
        def git_commit(self): return "stub"
        def metadata(self): return {"target_class": f"stub.{self.target}.Class"}
    import sys as _sys, types as _types
    fake_mod = _types.ModuleType("ophamin.seeing.substrate")
    fake_mod.KimeraAdapter = _StubAdapter
    saved = _sys.modules.get("ophamin.seeing.substrate")
    _sys.modules["ophamin.seeing.substrate"] = fake_mod
    try:
        sub = miner._substrate_for_target("rosetta")
        assert isinstance(sub, _StubAdapter)
        assert sub.target == "rosetta"
        assert len(rebind_calls) == 1
        assert rebind_calls[0]["target"] == "rosetta"
        assert rebind_calls[0]["kimera_repo"] == tmp_path
    finally:
        if saved is not None:
            _sys.modules["ophamin.seeing.substrate"] = saved
        else:
            _sys.modules.pop("ophamin.seeing.substrate", None)


def test_schema_miner_rejects_empty_stimuli():
    def factory(s, i):
        return CycleResult(i, True, {}, "commit")
    miner = SchemaMiner(_SyntheticSubstrate(factory))
    with pytest.raises(ValueError, match="at least one stimulus"):
        miner.mine(targets=["entity"], stimuli=[])
    with pytest.raises(ValueError, match="at least one target"):
        miner.mine(targets=[], stimuli=["a"])


def test_schema_document_roundtrips_json(tmp_path):
    field_schema = FieldSchema(
        path="halt_mode",
        types_seen=("str",),
        occurrence_count=5,
        n_cycles_target=5,
        sample_values=("exhausted", "amplitude_death"),
        sample_kind="values",
    )
    target = TargetSchema(
        name="entity",
        target_class="kimera_swm.domain.cognitive.takwin.Takwin",
        n_cycles=5,
        n_adapter_errors=0,
        fields=(field_schema,),
    )
    doc = SchemaDocument(
        ophamin_version="0.1.0",
        ophamin_git_commit="ophamin-deadbeef",
        kimera_git_commit="kimera-deadbeef",
        stimulus_set_hash="hash-deadbeef",
        n_stimuli=5,
        targets=(target,),
    )
    json_path = tmp_path / "schema.json"
    doc.to_json(json_path)
    reloaded = SchemaDocument.from_json(json_path)
    assert reloaded == doc


def test_schema_document_from_dict_rejects_missing_keys():
    bad = {"ophamin_version": "0.1.0"}
    with pytest.raises(ValueError, match="missing required keys"):
        SchemaDocument.from_dict(bad)


def _build_doc(targets: list[TargetSchema], *, kimera_commit: str = "k") -> SchemaDocument:
    return SchemaDocument(
        ophamin_version="0.1.0",
        ophamin_git_commit="o",
        kimera_git_commit=kimera_commit,
        stimulus_set_hash="h",
        n_stimuli=5,
        targets=tuple(targets),
    )


def _build_field(path: str, types: tuple[str, ...] = ("str",)) -> FieldSchema:
    return FieldSchema(
        path=path,
        types_seen=types,
        occurrence_count=5,
        n_cycles_target=5,
        sample_values=("sample",),
        sample_kind="values",
    )


def _build_target(name: str, fields: list[FieldSchema]) -> TargetSchema:
    return TargetSchema(
        name=name,
        target_class=f"kimera.{name}.Class",
        n_cycles=5,
        n_adapter_errors=0,
        fields=tuple(fields),
    )


def test_diff_schemas_empty_when_identical():
    target = _build_target("entity", [_build_field("halt_mode")])
    doc = _build_doc([target])
    d = diff_schemas(doc, doc)
    assert d.is_empty()
    assert d.targets_added == ()
    assert d.targets_removed == ()
    assert d.field_changes == ()


def test_diff_schemas_surfaces_added_field():
    before = _build_doc([_build_target("entity", [_build_field("halt_mode")])])
    after = _build_doc([
        _build_target("entity", [_build_field("halt_mode"), _build_field("new_field")])
    ])
    d = diff_schemas(before, after)
    assert not d.is_empty()
    assert any(
        c.kind == "added" and c.path == "new_field" and c.target == "entity"
        for c in d.field_changes
    )


def test_diff_schemas_surfaces_removed_field():
    before = _build_doc([
        _build_target("entity", [_build_field("halt_mode"), _build_field("old_field")])
    ])
    after = _build_doc([_build_target("entity", [_build_field("halt_mode")])])
    d = diff_schemas(before, after)
    assert any(
        c.kind == "removed" and c.path == "old_field" for c in d.field_changes
    )


def test_diff_schemas_surfaces_type_change():
    before = _build_doc([
        _build_target("entity", [_build_field("phi", types=("int",))])
    ])
    after = _build_doc([
        _build_target("entity", [_build_field("phi", types=("float",))])
    ])
    d = diff_schemas(before, after)
    change = next(c for c in d.field_changes if c.path == "phi")
    assert change.kind == "type_changed"
    assert change.types_before == ("int",)
    assert change.types_after == ("float",)


def test_diff_schemas_surfaces_added_target():
    before = _build_doc([_build_target("entity", [_build_field("halt_mode")])])
    after = _build_doc([
        _build_target("entity", [_build_field("halt_mode")]),
        _build_target("walker", [_build_field("M1_commits")]),
    ])
    d = diff_schemas(before, after)
    assert "walker" in d.targets_added
    # the walker.M1_commits field surfaces too
    assert any(
        c.target == "walker" and c.path == "M1_commits" and c.kind == "added"
        for c in d.field_changes
    )


def test_diff_schemas_surfaces_removed_target():
    before = _build_doc([
        _build_target("entity", [_build_field("halt_mode")]),
        _build_target("walker", [_build_field("M1_commits")]),
    ])
    after = _build_doc([_build_target("entity", [_build_field("halt_mode")])])
    d = diff_schemas(before, after)
    assert "walker" in d.targets_removed
    assert any(
        c.target == "walker" and c.path == "M1_commits" and c.kind == "removed"
        for c in d.field_changes
    )


def test_diff_schemas_to_dict_is_serializable():
    before = _build_doc([_build_target("entity", [_build_field("halt_mode")])])
    after = _build_doc([
        _build_target("entity", [_build_field("halt_mode"), _build_field("new_field")])
    ])
    d = diff_schemas(before, after)
    serialized = json.dumps(d.to_dict())
    parsed = json.loads(serialized)
    assert parsed["is_empty"] is False
    assert any(fc["path"] == "new_field" for fc in parsed["field_changes"])


def test_schema_writer_produces_readable_markdown(tmp_path):
    field_schema = FieldSchema(
        path="prime.composite",
        types_seen=("int",),
        occurrence_count=20,
        n_cycles_target=20,
        sample_values=(232453, 506413, 286871),
        sample_kind="values",
    )
    field_list = FieldSchema(
        path="dissonance_events",
        types_seen=("list",),
        occurrence_count=20,
        n_cycles_target=20,
        sample_values=(10, 22, 30),
        sample_kind="lengths",
    )
    target = TargetSchema(
        name="entity",
        target_class="kimera_swm.domain.cognitive.takwin.Takwin",
        n_cycles=20,
        n_adapter_errors=0,
        fields=(field_schema, field_list),
    )
    doc = SchemaDocument(
        ophamin_version="0.1.0",
        ophamin_git_commit="ophamin-c",
        kimera_git_commit="kimera-c",
        stimulus_set_hash="hash",
        n_stimuli=20,
        targets=(target,),
    )
    out = write_schema_markdown(doc, tmp_path / "KIMERA_FIELDS.md")
    body = out.read_text()
    # the markdown carries the load-bearing facts
    assert "kimera-c" in body
    assert "prime.composite" in body
    assert "lengths: 10, 22, 30" in body
    assert "232453" in body
    assert "20/20 (100%)" in body
    assert "## Per-target field schemas" in body
