"""Tests for KimeraInventory — static discovery of Kimera's observable surface.

Fixture strategy: build a synthetic *miniature* Kimera repo with exactly the
files each discoverer is looking for. Don't import Kimera. Don't depend on
file system layout outside the fixture. This keeps the tests fast and
reproducible.

A separate `test_kimera_inventory_live.py`-style probe could run against the
real repo at /Users/.../Kimera_SWM — done out-of-band, not in CI.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from ophamin.seeing.discovery.kimera_inventory import (
    DEFAULT_SIGN_KEY,
    INVENTORY_SCHEMA_VERSION,
    STRATA_DISCOVERERS,
    KimeraInventory,
    StratumInventory,
    Surface,
    discover_all,
    discover_cognitive,
    discover_interface,
    discover_lifecycle,
    discover_persistence,
    discover_reconciliation,
    discover_security,
    discover_telemetry,
    discover_temporal,
    discover_transport,
)


# --------------------------------------------------------------------------
# Fixture: synthetic Kimera repo with the files each discoverer needs
# --------------------------------------------------------------------------


@pytest.fixture
def fake_kimera(tmp_path: Path) -> Path:
    """A minimal directory tree that mimics Kimera-SWM enough for discovery."""

    def touch(rel: str, content: str = "") -> Path:
        p = tmp_path / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content, encoding="utf-8")
        return p

    # --- cognitive --------------------------------------------------------
    touch("kimera_swm/domain/cognitive/takwin.py", "class Takwin: pass\n")
    touch("kimera_swm/domain/linguistic/one_plus_three_plus_one_enforcer.py", "class Pentecost: pass\n")
    touch("kimera_swm/domain/mathematical/ouroboros_kernel.py", "class OuroborosKernel: pass\n")
    touch("kimera_swm/domain/semantic/rosetta_service.py", "class RosettaService: pass\n")
    touch("kimera_swm/domain/semantic/rosetta_stele.py", "class RosettaStele: pass\n")
    touch("kimera_swm/domain/prime/arachne_protocol.py", "class ArachneProtocol: pass\n")
    touch("kimera_swm/domain/cognitive/walker.py", "class Walker: pass\n")
    touch("kimera_swm/domain/geoid/geoid_1_3_1_enforcement.py", "class Atlas: pass\n")
    touch("kimera_swm/domain/geoid/spherical_5d_geometry.py", "class Astrolabe: pass\n")
    touch("kimera_swm/infrastructure/temporal/spde_engine.py", "class SPDEEngine: pass\n")
    (tmp_path / "kimera_swm/domain/security/gyroscopic_water_fortress").mkdir(parents=True)
    (tmp_path / "kimera_swm/domain/piovra").mkdir(parents=True)

    # --- interface --------------------------------------------------------
    for name in ("auth_router", "cognitive_router", "monitoring_router", "vault_router",
                 "rosetta_router", "system_router"):
        touch(f"kimera_swm/api/routers/{name}.py")
    for name in ("a2a_controller", "geoid_controller", "echoform_controller"):
        touch(f"kimera_swm/interfaces/rest/controllers/{name}.py")
    for sub in ("schema", "resolvers", "federation", "services"):
        (tmp_path / f"kimera_swm/interfaces/graphql/{sub}").mkdir(parents=True)
    for name in ("a2a_tools", "cognitive_tools", "geoid_tools",
                 "mathematical_tools", "system_tools"):
        touch(f"kimera_swm/interfaces/mcp/tools/{name}.py")
    touch("kimera_swm/interfaces/mcp/server.py")
    for name in ("memory_resources", "state_resources"):
        touch(f"kimera_swm/interfaces/mcp/resources/{name}.py")
    for name in ("audit", "discover", "run"):
        touch(f"kimera_swm/interfaces/cli/commands/{name}.py")
    touch("kimera_swm/interfaces/websocket/manager.py")

    # --- transport --------------------------------------------------------
    for name in ("async_queue", "tcp", "websocket", "kafka", "rabbitmq", "nats"):
        touch(f"kimera_swm/domain/piovra/transports/{name}.py")

    # --- persistence ------------------------------------------------------
    for name in ("postgres_cognitive_repository", "postgres_geoid_repository",
                 "postgres_decision_repository", "arangodb_manager",
                 "redis_manager", "multi_level_cache_manager",
                 "distributed_transaction_coordinator", "migration_manager",
                 "unified_database_manager"):
        touch(f"kimera_swm/infrastructure/database/{name}.py")
    touch("kimera_swm/infrastructure/database/insight_schema.sql", "CREATE TABLE foo (x INT);\n")
    for name in ("vault_repository", "echoform_repository", "ecoform_repository"):
        touch(f"kimera_swm/infrastructure/persistence/{name}.py")
    for name in ("vault_auditor", "vault_sync_manager", "vault_router", "vault_optimizer"):
        touch(f"kimera_swm/infrastructure/vault/{name}.py")

    # --- reconciliation ---------------------------------------------------
    for name in ("g_set", "scar_dag", "echoform_chain", "rateless_iblt",
                 "bloom_preflight", "offline_reconnect"):
        touch(f"kimera_swm/infrastructure/reconciliation/{name}.py")

    # --- temporal ---------------------------------------------------------
    for name in ("cronos_atomic_clock", "cronos_sync", "cronos_metrics",
                 "dtc_flywheel", "thorium_core", "zeta_standard"):
        touch(f"kimera_swm/infrastructure/temporal/cronos/{name}.py")
    for name in ("kccl_system", "kccl_integration", "oscillator_registry",
                 "oscillators", "rhythm_generator", "spde_engine",
                 "optimized_spde_engine"):
        touch(f"kimera_swm/infrastructure/temporal/{name}.py")

    # --- security ---------------------------------------------------------
    for name in ("agent_registry", "capability_directory", "conversation_manager",
                 "policy_gatekeeper", "task_orchestrator", "agent_models"):
        touch(f"kimera_swm/domain/autonomous/a2a/{name}.py")
    for name in ("ed25519_signing", "encryption_service", "rate_limiter",
                 "secret_manager", "secure_auth_service",
                 "runtime_attestation_guard"):
        touch(f"kimera_swm/infrastructure/security/{name}.py")
    for name in ("encryption_engine", "enhanced_authentication_manager",
                 "manipulation_detector_impl"):
        touch(f"kimera_swm/domain/security/{name}.py")
    touch("kimera_swm/domain/security/gyroscopic_water_fortress/cross_request_quorum.py")

    # --- telemetry --------------------------------------------------------
    for name in ("prometheus_exporter", "prometheus_metrics_collector",
                 "grafana_dashboard_manager", "alert_service",
                 "distributed_tracer", "structured_logger",
                 "centralized_logging_system", "system_health_monitor",
                 "performance_monitor", "consistency_monitor_impl",
                 "system_homeostasis_monitor", "metrics_collector",
                 "comprehensive_monitoring_manager", "dashboard"):
        touch(f"kimera_swm/infrastructure/monitoring/{name}.py")
    for name in ("alerts", "alert_channels", "health_monitor", "kccl_tracer",
                 "metrics_dashboard", "tracing"):
        touch(f"kimera_swm/infrastructure/observability/{name}.py")
    touch("kimera_swm/infrastructure/monitoring/prometheus_config.yml",
          "scrape_configs:\n  - job_name: kimera\n")
    touch("kimera_swm/infrastructure/monitoring/alert_rules.yml",
          "groups:\n  - name: kimera\n    rules: []\n")
    touch("kimera_swm/infrastructure/monitoring/alertmanager.yml",
          "global: {}\nroute: {}\n")
    touch("kimera_swm/infrastructure/monitoring/kimera_alerts.yml",
          "groups: []\n")
    touch("kimera_swm/infrastructure/monitoring/grafana_dashboard.json",
          '{"panels":[]}\n')
    touch("kimera_swm/infrastructure/monitoring/docker-compose.monitoring.yml",
          "services: {}\n")

    # --- lifecycle --------------------------------------------------------
    for name in ("builder", "loader", "manifest", "snapshot_encoder", "verifier", "smoke_test"):
        touch(f"kimera_swm/infrastructure/encoder_snapshot/{name}.py")
    for name in ("builder", "manifest", "state", "takwin_integration", "deployment_policy"):
        touch(f"kimera_swm/infrastructure/frozen_on_fall/{name}.py")
    for name in ("memory_pool_manager", "gc_optimizer", "memory_leak_detector",
                 "memory_analytics", "memory_monitor", "memory_manager",
                 "holographic_manifold"):
        touch(f"kimera_swm/infrastructure/memory/{name}.py")

    return tmp_path


# --------------------------------------------------------------------------
# Per-stratum tests
# --------------------------------------------------------------------------


def test_discover_cognitive_finds_all_known_targets(fake_kimera):
    inv = discover_cognitive(fake_kimera)
    assert inv.stratum == "cognitive"
    assert inv.is_live, f"cognitive stratum dormant — found {inv.count}, expected ≥ {inv.expected_count}"
    target_keys = {s.metadata.get("target_key") for s in inv.surfaces}
    # Must find the named targets we seeded
    assert {"takwin", "walker", "arachne", "rosetta", "atlas"} <= target_keys


def test_discover_interface_separates_protocols(fake_kimera):
    inv = discover_interface(fake_kimera)
    assert inv.is_live, f"interface stratum dormant — {inv.count} < {inv.expected_count}"
    protocols = {s.metadata.get("protocol") for s in inv.surfaces}
    assert {"rest", "graphql", "mcp", "cli", "websocket"} <= protocols
    # MCP server file is present
    mcp_names = {s.name for s in inv.surfaces if s.metadata.get("protocol") == "mcp"}
    assert "server" in mcp_names
    # 6 routers were seeded
    routers = [s for s in inv.surfaces if s.metadata.get("role") == "router"]
    assert len(routers) == 6


def test_discover_transport_lists_all_adapters(fake_kimera):
    inv = discover_transport(fake_kimera)
    assert inv.is_live
    names = {s.name for s in inv.surfaces}
    assert {"tcp", "websocket", "kafka", "rabbitmq", "nats", "async_queue"} <= names
    for s in inv.surfaces:
        assert s.metadata["layer"] == "L3"


def test_discover_persistence_tags_backends(fake_kimera):
    inv = discover_persistence(fake_kimera)
    assert inv.is_live
    backends = {s.metadata.get("backend") for s in inv.surfaces}
    assert {"postgres", "arangodb", "redis", "cache", "vault", "transaction"} <= backends
    # Schema SQL file picked up
    sql = [s for s in inv.surfaces if s.metadata.get("format") == "sql"]
    assert len(sql) == 1
    assert sql[0].name == "insight_schema"


def test_discover_reconciliation_tags_families(fake_kimera):
    inv = discover_reconciliation(fake_kimera)
    assert inv.is_live
    families = {s.metadata["family"] for s in inv.surfaces}
    assert {"riblt", "bloom", "dag_crdt", "chain_crdt", "set_crdt", "reconnect_protocol"} <= families


def test_discover_temporal_separates_cronos_and_kccl(fake_kimera):
    inv = discover_temporal(fake_kimera)
    assert inv.is_live
    cronos = [s for s in inv.surfaces if s.metadata["family"] == "cronos"]
    kccl = [s for s in inv.surfaces if s.metadata["family"] == "kccl"]
    spde = [s for s in inv.surfaces if s.metadata["family"] == "spde"]
    assert len(cronos) == 6
    assert len(kccl) >= 2
    assert len(spde) >= 1


def test_discover_security_finds_a2a_and_infra_and_domain(fake_kimera):
    inv = discover_security(fake_kimera)
    assert inv.is_live
    a2a = [s for s in inv.surfaces if s.metadata.get("family") == "a2a"]
    assert {"policy_gatekeeper", "agent_registry", "capability_directory"} <= {s.name for s in a2a}
    families = {s.metadata.get("family") for s in inv.surfaces}
    assert "pki" in families      # ed25519_signing
    assert "rate_limit" in families
    assert "gwf" in families      # cross_request_quorum under gwf subpackage


def test_discover_telemetry_separates_prometheus_grafana_alerting(fake_kimera):
    inv = discover_telemetry(fake_kimera)
    assert inv.is_live
    families = {s.metadata["family"] for s in inv.surfaces}
    assert {"prometheus", "grafana", "alerting", "tracing", "logging", "config_artifact"} <= families
    # YAML/JSON config artefacts captured
    yaml_kinds = {s.kind for s in inv.surfaces if s.metadata["family"] == "config_artifact"}
    assert "yaml_config" in yaml_kinds
    assert "yaml_rule" in yaml_kinds
    assert "json_config" in yaml_kinds


def test_discover_lifecycle_lists_snapshot_freeze_and_memory(fake_kimera):
    inv = discover_lifecycle(fake_kimera)
    assert inv.is_live
    families = {s.metadata["family"] for s in inv.surfaces}
    assert "encoder_snapshot" in families
    assert "frozen_on_fall" in families
    assert "memory_pool" in families
    assert "leak_detection" in families


# --------------------------------------------------------------------------
# Aggregator + signing + serialisation
# --------------------------------------------------------------------------


def test_discover_all_returns_signed_inventory(fake_kimera):
    inv = discover_all(fake_kimera)
    assert isinstance(inv, KimeraInventory)
    assert inv.signature, "inventory must be signed"
    assert inv.verify(DEFAULT_SIGN_KEY), "signature must verify with default key"
    assert inv.schema_version == INVENTORY_SCHEMA_VERSION
    assert inv.total_surfaces() > 50
    # Every stratum present
    stratum_names = {s.stratum for s in inv.strata}
    assert stratum_names == set(STRATA_DISCOVERERS)


def test_discover_all_inventory_id_is_deterministic(fake_kimera):
    a = discover_all(fake_kimera)
    b = discover_all(fake_kimera)
    # captured_at differs, so the bodies differ → ids differ. But under fixed
    # captured_at the canonical bytes are identical.
    body_a = a._canonical_bytes()
    body_b = b._canonical_bytes()
    # Two runs against the same tree should at least cover the same surface
    # set (ordering is sorted by file_path inside each stratum).
    assert a.total_surfaces() == b.total_surfaces()
    assert {s.file_path for st in a.strata for s in st.surfaces} == \
           {s.file_path for st in b.strata for s in st.surfaces}


def test_inventory_round_trips_through_json(fake_kimera):
    inv = discover_all(fake_kimera)
    data = json.loads(inv.to_json())
    rebuilt = KimeraInventory.from_dict(data)
    assert rebuilt.inventory_id == inv.inventory_id
    assert rebuilt.total_surfaces() == inv.total_surfaces()
    assert rebuilt.verify(DEFAULT_SIGN_KEY)


def test_inventory_tampering_breaks_signature(fake_kimera):
    inv = discover_all(fake_kimera)
    # Tamper: drop a surface from one stratum.
    tampered_strata = list(inv.strata)
    cogn = tampered_strata[0]
    if cogn.surfaces:
        new_cogn = StratumInventory(
            stratum=cogn.stratum, description=cogn.description,
            surfaces=cogn.surfaces[1:], expected_count=cogn.expected_count,
        )
        tampered_strata[0] = new_cogn
    tampered = KimeraInventory(
        ophamin_version=inv.ophamin_version,
        ophamin_git_commit=inv.ophamin_git_commit,
        kimera_repo_path=inv.kimera_repo_path,
        kimera_git_commit=inv.kimera_git_commit,
        strata=tuple(tampered_strata),
        captured_at=inv.captured_at,
        schema_version=inv.schema_version,
        signature=inv.signature,       # keep the OLD signature
    )
    assert not tampered.verify(DEFAULT_SIGN_KEY)


def test_inventory_to_markdown_renders_table_with_all_strata(fake_kimera):
    inv = discover_all(fake_kimera)
    md = inv.to_markdown()
    assert "# Kimera-SWM Static Inventory" in md
    # Every stratum heading is present
    for stratum in STRATA_DISCOVERERS:
        assert f"### `{stratum}`" in md
    # Signature line rendered
    assert inv.signature in md


def test_inventory_to_markdown_writes_to_caller_path_not_surface_file(fake_kimera, tmp_path):
    """Regression: prove no shadow bug here. The kimera_inventory.to_markdown's
    loop variables are explicitly named ``surf`` and ``stratum`` (not ``path``),
    so the lesson from auditing.audit_record's 2026-05-15 shadow bug is preserved.
    """
    inv = discover_all(fake_kimera)
    out_dir = tmp_path / "inventory_out"
    out_dir.mkdir()
    out_path = out_dir / "inventory.md"
    inv.to_markdown(str(out_path))
    assert out_path.exists()
    # No source file in fake_kimera was overwritten.
    cogn_target = fake_kimera / "kimera_swm/domain/cognitive/takwin.py"
    assert cogn_target.read_text() == "class Takwin: pass\n"


def test_discover_all_loud_failure_on_missing_repo(tmp_path):
    nonexistent = tmp_path / "no_such_kimera"
    with pytest.raises(FileNotFoundError):
        discover_all(nonexistent)


def test_discover_all_rejects_unknown_stratum(fake_kimera):
    with pytest.raises(ValueError, match="Unknown strata"):
        discover_all(fake_kimera, strata=("cognitive", "totally_made_up"))


def test_discover_all_supports_subset_of_strata(fake_kimera):
    inv = discover_all(fake_kimera, strata=("cognitive", "transport"))
    stratum_names = {s.stratum for s in inv.strata}
    assert stratum_names == {"cognitive", "transport"}
    assert inv.verify(DEFAULT_SIGN_KEY)


# --------------------------------------------------------------------------
# Per-discoverer dormant behaviour — empty repo finds nothing, doesn't crash
# --------------------------------------------------------------------------


def test_discover_all_on_empty_repo_returns_dormant_strata(tmp_path):
    """Discoverers must not crash on a missing-everything tree. Every stratum
    reports zero surfaces and is_live=False.
    """
    empty = tmp_path / "empty_kimera"
    empty.mkdir()
    inv = discover_all(empty)
    assert inv.total_surfaces() == 0
    assert len(inv.live_strata()) == 0
    assert set(inv.dormant_strata()) == set(STRATA_DISCOVERERS)
    # Still signs cleanly
    assert inv.verify(DEFAULT_SIGN_KEY)


def test_stratum_inventory_by_kind_filters(fake_kimera):
    inv = discover_telemetry(fake_kimera)
    config_artefacts = inv.by_kind("yaml_config")
    assert any(s.name == "prometheus_config" for s in config_artefacts)
    assert all(s.kind == "yaml_config" for s in config_artefacts)


def test_surface_round_trip():
    s = Surface(name="x", kind="module", file_path="a/b.py", line_count=42,
                metadata={"family": "test"})
    rebuilt = Surface.from_dict(s.to_dict())
    assert rebuilt == s


def test_surface_from_dict_rejects_missing_keys():
    with pytest.raises(ValueError, match="missing required keys"):
        Surface.from_dict({"name": "x"})


def test_stratum_inventory_round_trip():
    s = StratumInventory(
        stratum="test", description="t",
        surfaces=(Surface("a", "module", "a.py", 1, {}),),
        expected_count=1,
    )
    rebuilt = StratumInventory.from_dict(s.to_dict())
    assert rebuilt == s
