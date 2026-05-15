"""Tests for the F pillar — PROV-O graphs (prov library) and the lineage store.

The strong assertions cross-check Ophamin against the underlying libraries: the
``prov`` library must be able to re-read its own emitted PROV-JSON, and the
MLflow run logged alongside each manifest must really exist with our metadata.
"""

import json

import mlflow
from prov.model import ProvDocument

from ophamin.comparing.provenance.lineage import (
    LineageStore,
    capture_git_commit,
    content_hash,
    make_run_id,
)
from ophamin.comparing.provenance.prov import ProvenanceGraph


def test_provenance_graph_emits_valid_prov_json():
    g = ProvenanceGraph()
    dataset = g.entity("dataset:corpus", role="input")
    run = g.activity("run:001", cycles=100)
    framework = g.agent("ophamin")
    result = g.entity("result:001")
    g.used(run, dataset)
    g.was_associated_with(run, framework)
    g.was_generated_by(result, run)
    g.was_derived_from(result, dataset)

    doc = g.to_prov_json()
    assert "entity" in doc and "activity" in doc and "agent" in doc
    assert "used" in doc and "wasDerivedFrom" in doc
    # strong cross-check: the prov library can re-read its own PROV-JSON
    reparsed = ProvDocument.deserialize(content=json.dumps(doc), format="json")
    assert len(list(reparsed.get_records())) >= 7


def test_content_hash_is_stable_and_discriminating():
    assert content_hash({"a": 1, "b": 2}) == content_hash({"b": 2, "a": 1})
    assert content_hash({"a": 1}) != content_hash({"a": 2})


def test_make_run_id_is_content_tagged_and_unique():
    cfg = {"x": 1}
    assert make_run_id(cfg, unique=False) == content_hash(cfg)[:12]
    u1, u2 = make_run_id(cfg), make_run_id(cfg)
    assert u1 != u2
    assert u1.startswith(content_hash(cfg)[:12])


def test_lineage_store_records_native_manifest_and_mlflow_run(tmp_path):
    store = LineageStore(tmp_path / "runs", experiment_name="test-exp")
    store.record_run(
        run_id="parent",
        config={"cycles": 10},
        sut_metadata={"name": "mock", "git_commit": "abc123"},
        metrics={"summary": {"phi": 0.5}},
    )
    child = store.record_run(
        run_id="child",
        config={"cycles": 10, "rate": 0.5},
        sut_metadata={"name": "mock", "git_commit": "abc123"},
        metrics={"summary": {"phi": 0.6}},
        parent_run_id="parent",
    )

    # native content-addressed manifest layer
    assert sorted(store.list_runs()) == ["child", "parent"]
    assert store.get_run("child").parent_run_id == "parent"
    assert store.get_run("child").substrate_git_commit == "abc123"
    assert [r.run_id for r in store.lineage_of("child")] == ["child", "parent"]

    # MLflow tracking layer — the run really exists with our metadata
    assert child.mlflow_run_id
    client = mlflow.MlflowClient(
        tracking_uri=str((tmp_path / "runs" / "mlruns").resolve())
    )
    ml_run = client.get_run(child.mlflow_run_id)
    assert ml_run.data.tags["ophamin.run_id"] == "child"
    assert ml_run.data.tags["ophamin.parent_run_id"] == "parent"
    assert ml_run.data.metrics["summary.phi"] == 0.6


def test_lineage_store_link_dataset_is_content_addressed(tmp_path):
    store = LineageStore(tmp_path / "runs", enable_mlflow=False)
    a = tmp_path / "a.txt"
    b = tmp_path / "b.txt"
    c = tmp_path / "c.txt"
    a.write_text("identical content")
    b.write_text("identical content")
    c.write_text("different content")
    assert store.link_dataset(a).content_hash == store.link_dataset(b).content_hash
    assert store.link_dataset(a).content_hash != store.link_dataset(c).content_hash
    assert store.link_dataset(a).kind == "file"


def test_capture_git_commit_on_non_repo_returns_empty(tmp_path):
    assert capture_git_commit(tmp_path) == ""
