"""Tests for SubstrateCompletenessScenario — the empirical wired-vs-orphan claim."""

from __future__ import annotations

from pathlib import Path

import pytest

from ophamin.measuring.proof import EmpiricalProofRecord, REFUTED, VALIDATED
from ophamin.measuring.scenarios.substrate_completeness import (
    SubstrateCompletenessScenario,
)


def _build_fake_kimera(tmp_path: Path, files: dict[str, str]) -> Path:
    for rel, content in files.items():
        p = tmp_path / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content, encoding="utf-8")
    return tmp_path


@pytest.fixture
def healthy_kimera(tmp_path):
    """A fake Kimera tree where every interface module is imported by main.py."""
    files = {
        "kimera_swm/__init__.py": "",
        "kimera_swm/main.py": "\n".join([
            "from kimera_swm.api.routers import r1, r2, r3",
            "from kimera_swm.interfaces.rest.controllers import c1, c2",
            "from kimera_swm.interfaces.mcp.tools import t1, t2, t3",
            "from kimera_swm.interfaces.cli.commands import cmd1",
            "from kimera_swm.domain.piovra.transports import tcp",
            "from kimera_swm.infrastructure.database import postgres_cognitive_repository",
            "from kimera_swm.infrastructure.reconciliation import g_set",
            "from kimera_swm.infrastructure.temporal.cronos import cronos_atomic_clock",
            "from kimera_swm.infrastructure.security import ed25519_signing",
            "from kimera_swm.infrastructure.monitoring import prometheus_exporter",
            "from kimera_swm.infrastructure.encoder_snapshot import builder",
            "from kimera_swm.domain.cognitive import takwin",
        ]),
        # Cognitive (>= 8 surfaces required to be live, populate a few)
        "kimera_swm/domain/__init__.py": "",
        "kimera_swm/domain/cognitive/__init__.py": "",
        "kimera_swm/domain/cognitive/takwin.py": "class Takwin: pass\n",
        "kimera_swm/domain/cognitive/walker.py": "class Walker: pass\n",
        "kimera_swm/domain/mathematical/__init__.py": "",
        "kimera_swm/domain/mathematical/ouroboros_kernel.py": "class OuroborosKernel: pass\n",
        "kimera_swm/domain/semantic/__init__.py": "",
        "kimera_swm/domain/semantic/rosetta_service.py": "class RosettaService: pass\n",
        "kimera_swm/domain/semantic/rosetta_stele.py": "class RosettaStele: pass\n",
        "kimera_swm/domain/prime/__init__.py": "",
        "kimera_swm/domain/prime/arachne_protocol.py": "class ArachneProtocol: pass\n",
        "kimera_swm/domain/security/__init__.py": "",
        "kimera_swm/domain/security/gyroscopic_water_fortress/__init__.py": "",
        "kimera_swm/domain/geoid/__init__.py": "",
        "kimera_swm/domain/geoid/geoid_1_3_1_enforcement.py": "class Atlas: pass\n",
        "kimera_swm/domain/geoid/spherical_5d_geometry.py": "class Astrolabe: pass\n",
        "kimera_swm/domain/piovra/__init__.py": "",
        # Interface — 7 modules, all imported by main.py
        "kimera_swm/api/__init__.py": "",
        "kimera_swm/api/routers/__init__.py": "",
        "kimera_swm/api/routers/r1.py": "def get(): pass\n",
        "kimera_swm/api/routers/r2.py": "def get(): pass\n",
        "kimera_swm/api/routers/r3.py": "def get(): pass\n",
        "kimera_swm/interfaces/__init__.py": "",
        "kimera_swm/interfaces/rest/__init__.py": "",
        "kimera_swm/interfaces/rest/controllers/__init__.py": "",
        "kimera_swm/interfaces/rest/controllers/c1.py": "class C1: pass\n",
        "kimera_swm/interfaces/rest/controllers/c2.py": "class C2: pass\n",
        "kimera_swm/interfaces/mcp/__init__.py": "",
        "kimera_swm/interfaces/mcp/tools/__init__.py": "",
        "kimera_swm/interfaces/mcp/tools/t1.py": "def tool(): pass\n",
        "kimera_swm/interfaces/mcp/tools/t2.py": "def tool(): pass\n",
        "kimera_swm/interfaces/mcp/tools/t3.py": "def tool(): pass\n",
        "kimera_swm/interfaces/mcp/server.py": "class Server: pass\n",
        "kimera_swm/interfaces/cli/__init__.py": "",
        "kimera_swm/interfaces/cli/commands/__init__.py": "",
        "kimera_swm/interfaces/cli/commands/cmd1.py": "def cmd(): pass\n",
        "kimera_swm/interfaces/graphql/__init__.py": "",
        "kimera_swm/interfaces/graphql/schema/__init__.py": "",
        "kimera_swm/interfaces/graphql/resolvers/__init__.py": "",
        "kimera_swm/interfaces/graphql/federation/__init__.py": "",
        "kimera_swm/interfaces/graphql/services/__init__.py": "",
        "kimera_swm/interfaces/websocket/__init__.py": "",
        "kimera_swm/interfaces/websocket/manager.py": "def handle(): pass\n",
        # Transport — 4 modules, all imported via tcp + indirect
        "kimera_swm/domain/piovra/transports/__init__.py": "",
        "kimera_swm/domain/piovra/transports/tcp.py": "from kimera_swm.domain.piovra.transports import async_queue, websocket, kafka\nclass T: pass\n",
        "kimera_swm/domain/piovra/transports/async_queue.py": "class T: pass\n",
        "kimera_swm/domain/piovra/transports/websocket.py": "class T: pass\n",
        "kimera_swm/domain/piovra/transports/kafka.py": "class T: pass\n",
        # Persistence
        "kimera_swm/infrastructure/__init__.py": "",
        "kimera_swm/infrastructure/database/__init__.py": "",
        "kimera_swm/infrastructure/database/postgres_cognitive_repository.py": (
            "from kimera_swm.infrastructure.database import postgres_geoid_repository\n"
            "class R: pass\n"
        ),
        "kimera_swm/infrastructure/database/postgres_geoid_repository.py": "class R: pass\n",
        "kimera_swm/infrastructure/database/arangodb_manager.py": (
            "from kimera_swm.infrastructure.database import redis_manager, multi_level_cache_manager\n"
        ),
        "kimera_swm/infrastructure/database/redis_manager.py": "class R: pass\n",
        "kimera_swm/infrastructure/database/multi_level_cache_manager.py": "class C: pass\n",
        "kimera_swm/infrastructure/database/distributed_transaction_coordinator.py": "class T: pass\n",
        "kimera_swm/infrastructure/database/migration_manager.py": "class M: pass\n",
        "kimera_swm/infrastructure/database/unified_database_manager.py": (
            "from kimera_swm.infrastructure.database import (\n"
            "    arangodb_manager, distributed_transaction_coordinator,\n"
            "    migration_manager\n)\n"
        ),
        "kimera_swm/infrastructure/persistence/__init__.py": (
            "from kimera_swm.infrastructure.persistence import vault_repository, echoform_repository\n"
        ),
        "kimera_swm/infrastructure/persistence/vault_repository.py": "class V: pass\n",
        "kimera_swm/infrastructure/persistence/echoform_repository.py": "class E: pass\n",
        "kimera_swm/infrastructure/vault/__init__.py": (
            "from kimera_swm.infrastructure.vault import vault_auditor, vault_sync_manager,"
            " vault_router, vault_optimizer\n"
        ),
        "kimera_swm/infrastructure/vault/vault_auditor.py": "class A: pass\n",
        "kimera_swm/infrastructure/vault/vault_sync_manager.py": "class S: pass\n",
        "kimera_swm/infrastructure/vault/vault_router.py": "class R: pass\n",
        "kimera_swm/infrastructure/vault/vault_optimizer.py": "class O: pass\n",
        # Reconciliation
        "kimera_swm/infrastructure/reconciliation/__init__.py": (
            "from kimera_swm.infrastructure.reconciliation import "
            "scar_dag, echoform_chain, rateless_iblt, bloom_preflight, offline_reconnect\n"
        ),
        "kimera_swm/infrastructure/reconciliation/g_set.py": "class G: pass\n",
        "kimera_swm/infrastructure/reconciliation/scar_dag.py": "class S: pass\n",
        "kimera_swm/infrastructure/reconciliation/echoform_chain.py": "class C: pass\n",
        "kimera_swm/infrastructure/reconciliation/rateless_iblt.py": "def encode(): pass\n",
        "kimera_swm/infrastructure/reconciliation/bloom_preflight.py": "def build(): pass\n",
        "kimera_swm/infrastructure/reconciliation/offline_reconnect.py": "class S: pass\n",
        # Temporal — 10 modules
        "kimera_swm/infrastructure/temporal/__init__.py": (
            "from kimera_swm.infrastructure.temporal import (\n"
            "    kccl_system, oscillator_registry, oscillators, "
            "    rhythm_generator, spde_engine, optimized_spde_engine\n)\n"
        ),
        "kimera_swm/infrastructure/temporal/cronos/__init__.py": (
            "from kimera_swm.infrastructure.temporal.cronos import ("
            "    cronos_sync, cronos_metrics, dtc_flywheel, thorium_core, zeta_standard\n)\n"
        ),
        "kimera_swm/infrastructure/temporal/cronos/cronos_atomic_clock.py": "class A: pass\n",
        "kimera_swm/infrastructure/temporal/cronos/cronos_sync.py": "class S: pass\n",
        "kimera_swm/infrastructure/temporal/cronos/cronos_metrics.py": "class M: pass\n",
        "kimera_swm/infrastructure/temporal/cronos/dtc_flywheel.py": "class F: pass\n",
        "kimera_swm/infrastructure/temporal/cronos/thorium_core.py": "class C: pass\n",
        "kimera_swm/infrastructure/temporal/cronos/zeta_standard.py": "class Z: pass\n",
        "kimera_swm/infrastructure/temporal/kccl_system.py": "class K: pass\n",
        "kimera_swm/infrastructure/temporal/oscillator_registry.py": "class O: pass\n",
        "kimera_swm/infrastructure/temporal/oscillators.py": "class O: pass\n",
        "kimera_swm/infrastructure/temporal/rhythm_generator.py": "class R: pass\n",
        "kimera_swm/infrastructure/temporal/spde_engine.py": "class S: pass\n",
        "kimera_swm/infrastructure/temporal/optimized_spde_engine.py": "class S: pass\n",
        # Security — 15+ modules, all wired
        "kimera_swm/infrastructure/security/__init__.py": (
            "from kimera_swm.infrastructure.security import (\n"
            "    encryption_service, rate_limiter, secret_manager, secure_auth_service,\n"
            "    runtime_attestation_guard\n)\n"
        ),
        "kimera_swm/infrastructure/security/ed25519_signing.py": "def sign(): pass\n",
        "kimera_swm/infrastructure/security/encryption_service.py": "class E: pass\n",
        "kimera_swm/infrastructure/security/rate_limiter.py": "class R: pass\n",
        "kimera_swm/infrastructure/security/secret_manager.py": "class S: pass\n",
        "kimera_swm/infrastructure/security/secure_auth_service.py": "class A: pass\n",
        "kimera_swm/infrastructure/security/runtime_attestation_guard.py": "class G: pass\n",
        "kimera_swm/domain/autonomous/__init__.py": "",
        "kimera_swm/domain/autonomous/a2a/__init__.py": (
            "from kimera_swm.domain.autonomous.a2a import (\n"
            "    agent_registry, capability_directory, conversation_manager,\n"
            "    policy_gatekeeper, task_orchestrator, agent_models\n)\n"
        ),
        "kimera_swm/domain/autonomous/a2a/agent_registry.py": "class R: pass\n",
        "kimera_swm/domain/autonomous/a2a/capability_directory.py": "class D: pass\n",
        "kimera_swm/domain/autonomous/a2a/conversation_manager.py": "class M: pass\n",
        "kimera_swm/domain/autonomous/a2a/policy_gatekeeper.py": "class G: pass\n",
        "kimera_swm/domain/autonomous/a2a/task_orchestrator.py": "class O: pass\n",
        "kimera_swm/domain/autonomous/a2a/agent_models.py": "class M: pass\n",
        "kimera_swm/domain/security/encryption_engine.py": "class E: pass\n",
        "kimera_swm/domain/security/enhanced_authentication_manager.py": "class A: pass\n",
        "kimera_swm/domain/security/manipulation_detection/__init__.py": "",
        "kimera_swm/domain/security/gyroscopic_water_fortress/cross_request_quorum.py": "class Q: pass\n",
        # Telemetry — full stack
        "kimera_swm/infrastructure/monitoring/__init__.py": (
            "from kimera_swm.infrastructure.monitoring import (\n"
            "    prometheus_metrics_collector, grafana_dashboard_manager, alert_service,\n"
            "    distributed_tracer, structured_logger, centralized_logging_system,\n"
            "    system_health_monitor, performance_monitor, consistency_monitor_impl,\n"
            "    system_homeostasis_monitor, metrics_collector,\n"
            "    comprehensive_monitoring_manager, dashboard\n)\n"
        ),
        "kimera_swm/infrastructure/monitoring/prometheus_exporter.py": "class E: pass\n",
        "kimera_swm/infrastructure/monitoring/prometheus_metrics_collector.py": "class C: pass\n",
        "kimera_swm/infrastructure/monitoring/grafana_dashboard_manager.py": "class M: pass\n",
        "kimera_swm/infrastructure/monitoring/alert_service.py": "class A: pass\n",
        "kimera_swm/infrastructure/monitoring/distributed_tracer.py": "class T: pass\n",
        "kimera_swm/infrastructure/monitoring/structured_logger.py": "class L: pass\n",
        "kimera_swm/infrastructure/monitoring/centralized_logging_system.py": "class L: pass\n",
        "kimera_swm/infrastructure/monitoring/system_health_monitor.py": "class M: pass\n",
        "kimera_swm/infrastructure/monitoring/performance_monitor.py": "class P: pass\n",
        "kimera_swm/infrastructure/monitoring/consistency_monitor_impl.py": "class C: pass\n",
        "kimera_swm/infrastructure/monitoring/system_homeostasis_monitor.py": "class H: pass\n",
        "kimera_swm/infrastructure/monitoring/metrics_collector.py": "class C: pass\n",
        "kimera_swm/infrastructure/monitoring/comprehensive_monitoring_manager.py": "class M: pass\n",
        "kimera_swm/infrastructure/monitoring/dashboard.py": "class D: pass\n",
        "kimera_swm/infrastructure/monitoring/prometheus_config.yml": "scrape_configs: []\n",
        "kimera_swm/infrastructure/monitoring/alert_rules.yml": "groups: []\n",
        "kimera_swm/infrastructure/monitoring/alertmanager.yml": "global: {}\n",
        "kimera_swm/infrastructure/monitoring/kimera_alerts.yml": "groups: []\n",
        "kimera_swm/infrastructure/monitoring/grafana_dashboard.json": '{"panels":[]}\n',
        "kimera_swm/infrastructure/monitoring/docker-compose.monitoring.yml": "services: {}\n",
        "kimera_swm/infrastructure/observability/__init__.py": (
            "from kimera_swm.infrastructure.observability import (\n"
            "    alerts, alert_channels, health_monitor, kccl_tracer,\n"
            "    metrics_dashboard, tracing\n)\n"
        ),
        "kimera_swm/infrastructure/observability/alerts.py": "class A: pass\n",
        "kimera_swm/infrastructure/observability/alert_channels.py": "class C: pass\n",
        "kimera_swm/infrastructure/observability/health_monitor.py": "class M: pass\n",
        "kimera_swm/infrastructure/observability/kccl_tracer.py": "class T: pass\n",
        "kimera_swm/infrastructure/observability/metrics_dashboard.py": "class D: pass\n",
        "kimera_swm/infrastructure/observability/tracing.py": "class T: pass\n",
        # Lifecycle
        "kimera_swm/infrastructure/encoder_snapshot/__init__.py": (
            "from kimera_swm.infrastructure.encoder_snapshot import (\n"
            "    loader, manifest, snapshot_encoder, verifier, smoke_test\n)\n"
        ),
        "kimera_swm/infrastructure/encoder_snapshot/builder.py": "class B: pass\n",
        "kimera_swm/infrastructure/encoder_snapshot/loader.py": "class L: pass\n",
        "kimera_swm/infrastructure/encoder_snapshot/manifest.py": "class M: pass\n",
        "kimera_swm/infrastructure/encoder_snapshot/snapshot_encoder.py": "class E: pass\n",
        "kimera_swm/infrastructure/encoder_snapshot/verifier.py": "class V: pass\n",
        "kimera_swm/infrastructure/encoder_snapshot/smoke_test.py": "def smoke(): pass\n",
        "kimera_swm/infrastructure/frozen_on_fall/__init__.py": (
            "from kimera_swm.infrastructure.frozen_on_fall import (\n"
            "    manifest, state, takwin_integration, deployment_policy\n)\n"
        ),
        "kimera_swm/infrastructure/frozen_on_fall/builder.py": "class B: pass\n",
        "kimera_swm/infrastructure/frozen_on_fall/manifest.py": "class M: pass\n",
        "kimera_swm/infrastructure/frozen_on_fall/state.py": "class S: pass\n",
        "kimera_swm/infrastructure/frozen_on_fall/takwin_integration.py": "def integrate(): pass\n",
        "kimera_swm/infrastructure/frozen_on_fall/deployment_policy.py": "class P: pass\n",
        "kimera_swm/infrastructure/memory/__init__.py": (
            "from kimera_swm.infrastructure.memory import (\n"
            "    memory_pool_manager, gc_optimizer, memory_leak_detector,\n"
            "    memory_analytics, memory_monitor, memory_manager, holographic_manifold\n)\n"
        ),
        "kimera_swm/infrastructure/memory/memory_pool_manager.py": "class M: pass\n",
        "kimera_swm/infrastructure/memory/gc_optimizer.py": "class O: pass\n",
        "kimera_swm/infrastructure/memory/memory_leak_detector.py": "class D: pass\n",
        "kimera_swm/infrastructure/memory/memory_analytics.py": "class A: pass\n",
        "kimera_swm/infrastructure/memory/memory_monitor.py": "class M: pass\n",
        "kimera_swm/infrastructure/memory/memory_manager.py": "class M: pass\n",
        "kimera_swm/infrastructure/memory/holographic_manifold.py": "class H: pass\n",
        "kimera_swm/infrastructure/api_gateway/__init__.py": "",
    }
    return _build_fake_kimera(tmp_path, files)


@pytest.fixture
def orphan_heavy_kimera(tmp_path):
    """A fake Kimera where most modules are orphan — should REFUTE."""
    files = {
        "kimera_swm/__init__.py": "",
        # Only one of N routers is imported.
        "kimera_swm/main.py": "from kimera_swm.api.routers import wired_r\n",
        "kimera_swm/api/__init__.py": "",
        "kimera_swm/api/routers/__init__.py": "",
        "kimera_swm/api/routers/wired_r.py": "def f(): pass\n",
    }
    # Add 30 orphan routers
    for i in range(30):
        files[f"kimera_swm/api/routers/orphan_{i}.py"] = "def f(): pass\n"
    return _build_fake_kimera(tmp_path, files)


def test_scenario_validated_on_healthy_kimera(healthy_kimera):
    s = SubstrateCompletenessScenario(healthy_kimera, orphan_rate_ceiling=0.20)
    record = s.run()
    assert isinstance(record, EmpiricalProofRecord)
    assert record.verdict.outcome == VALIDATED
    assert record.verdict.observed_value <= 0.20


def test_scenario_refuted_on_orphan_heavy_kimera(orphan_heavy_kimera):
    s = SubstrateCompletenessScenario(orphan_heavy_kimera, orphan_rate_ceiling=0.20)
    record = s.run()
    assert record.verdict.outcome == REFUTED
    assert record.verdict.observed_value > 0.20


def test_scenario_evidence_lists_orphan_files(orphan_heavy_kimera):
    s = SubstrateCompletenessScenario(orphan_heavy_kimera)
    record = s.run()
    orphan_list = record.evidence[0].detail["orphan_action_list"]
    assert len(orphan_list) >= 1
    for entry in orphan_list:
        assert "stratum" in entry
        assert "file_path" in entry


def test_scenario_records_per_stratum_breakdown(healthy_kimera):
    s = SubstrateCompletenessScenario(healthy_kimera)
    record = s.run()
    per_stratum = record.evidence[0].detail["per_stratum"]
    stratum_names = {s["stratum"] for s in per_stratum}
    # All 9 strata represented
    assert {"cognitive", "interface", "transport", "persistence",
            "reconciliation", "temporal", "security", "telemetry",
            "lifecycle"} <= stratum_names


def test_scenario_records_wilson_ci(healthy_kimera):
    s = SubstrateCompletenessScenario(healthy_kimera)
    record = s.run()
    ev = record.evidence[0]
    assert ev.ci_low is not None
    assert ev.ci_high is not None
    eps = 1e-9
    assert 0.0 <= ev.ci_low <= ev.statistic_value + eps
    assert ev.statistic_value <= ev.ci_high + eps
    assert ev.detail["ci_method"] == "wilson_95%"


def test_scenario_writes_completeness_report_when_out_dir_given(healthy_kimera, tmp_path):
    out_dir = tmp_path / "wiring_out"
    s = SubstrateCompletenessScenario(healthy_kimera, out_dir=out_dir)
    record = s.run()
    # Two files written: JSON + Markdown.
    assert out_dir.exists()
    files = list(out_dir.iterdir())
    assert any(f.suffix == ".json" for f in files)
    assert any(f.suffix == ".md" for f in files)


def test_scenario_last_report_is_populated(healthy_kimera):
    s = SubstrateCompletenessScenario(healthy_kimera)
    assert s.last_report is None
    s.run()
    assert s.last_report is not None
    # The proof references the report's ID.


def test_scenario_threshold_validation():
    with pytest.raises(ValueError, match="orphan_rate_ceiling must be in"):
        SubstrateCompletenessScenario(Path("/tmp"), orphan_rate_ceiling=1.5)


def test_scenario_loud_failure_on_missing_repo(tmp_path):
    nonexistent = tmp_path / "no_such_kimera"
    with pytest.raises(FileNotFoundError):
        SubstrateCompletenessScenario(nonexistent)


def test_scenario_is_in_global_registry():
    from ophamin.measuring.scenarios import SCENARIOS
    assert "substrate-completeness" in SCENARIOS
    assert SCENARIOS["substrate-completeness"] is SubstrateCompletenessScenario


def test_scenario_claim_has_h0_h1(healthy_kimera):
    s = SubstrateCompletenessScenario(healthy_kimera)
    claim = s.build_claim()
    assert claim.h0
    assert claim.h1
    assert claim.threshold.comparator == "<="
    assert claim.threshold.value == 0.20


def test_scenario_proof_is_signed(healthy_kimera):
    s = SubstrateCompletenessScenario(healthy_kimera)
    record = s.run()
    assert record.signature
