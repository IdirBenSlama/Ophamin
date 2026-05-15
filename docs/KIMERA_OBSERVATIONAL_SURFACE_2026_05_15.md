# Kimera-SWM observational surface — what Ophamin sees, what it misses

> **Status**: strategic reframing draft, 2026-05-15. Read before committing to
> Ophamin v0.2 scope. Written after a re-read of Kimera-SWM's `CLAUDE.md` +
> `EMPIRICAL_VALIDATION.md` + `KIMERA_STATE.md` and a code-level walk of
> `kimera_swm/infrastructure/` (68 subpackages) + `kimera_swm/interfaces/`
> (5 protocols) + `kimera_swm/domain/autonomous/a2a/`.
>
> The honest finding: **Ophamin v0.1 covers ~10–15% of Kimera's actual
> observable surface.** The cognitive cycle is one stratum among many. The
> reframe below names what's missing and proposes how to extend the six-wheel
> architecture without burning what works.

---

## 1. What Ophamin v0.1 actually observes

The `KimeraAdapter` in [`seeing/substrate/kimera_adapter.py`](../src/ophamin/seeing/substrate/kimera_adapter.py)
targets **11 cognitive primitives** via direct Python entry points:

```
entity (full Takwin), pentecost, ouroboros, rosetta, arachne,
walker, gwf, piovra, astrolabe, atlas, spde
```

Six wheels orbit this single observation surface:

- `seeing/` — discovers field schema, watches for HEAD changes
- `measuring/` — runs pre-registered scenarios across three tiers
- `comparing/` — drift over signed proof records
- `instrumenting/` — psutil per-cycle resource profile
- `auditing/` — ruff + bandit + mypy + vulture + radon + pip-audit on source
- `reporting/` — HTML / Markdown / LaTeX academic output

The shape is: *one cognitive cycle in, one signed CycleResult out, six wheels
look at the resulting trajectory.*

This is correct for what Ophamin was first scoped to do (verify Kimera's
cognitive **claims**). It is **insufficient** for what Kimera actually is.

---

## 2. What Kimera-SWM actually exposes — the verified inventory

Each row below is grep-verified against the working tree on 2026-05-15.

### 2.1 Persistence — six PostgreSQL repositories + ArangoDB + Redis + multi-level cache

```
kimera_swm/infrastructure/database/
  postgres_cognitive_repository.py
  postgres_contradiction_repository.py
  postgres_decision_repository.py
  postgres_geoid_repository.py
  postgres_insight_repository.py
  postgres_learning_repository.py
  arangodb_manager.py
  async_arango_bridge.py
  redis_manager.py
  distributed_transaction_coordinator.py
  multi_level_cache_manager.py
  enhanced_query_cache.py
  query_optimization_engine.py
  schema/ + migrations/ + insight_schema.sql
  unified_database_manager.py
  production_wiring.py
```

Plus `infrastructure/persistence/` with `vault_repository`,
`echoform_repository`, `ecoform_repository`, `zetetic_repository`,
`universal_database_manager`, `postgresql_chaos_repository`,
`in_memory_chaos_repository`.

Plus `infrastructure/vault/` with `vault_auditor`, `vault_optimizer`,
`vault_router`, `vault_sync_manager`.

**What Ophamin observes**: SCAR count via `entity` cycle result.
**Blind to**: per-repository query latency, transaction conflict rate,
ArangoDB graph traversal cost, Redis hit/miss ratios, cache hierarchy
behavior, schema migration state, vault sync drift.

### 2.2 Five protocol interfaces — REST × 47 routers, GraphQL, MCP × 10 tools, CLI, WebSocket

```
kimera_swm/interfaces/
  rest/app.py + 24 controllers/
  graphql/  app.py + federation/ + resolvers/ + schema/ + services/
  cli/      app.py + commands/ + batch.py + interactive.py + plugins.py
  mcp/      server.py + 10 tool files + resources/ + prompts/ + transports/
  websocket/ + websockets/
  auth/ + middleware/ + compliance/ + monitoring/
```

Plus `kimera_swm/api/routers/` with **47 router modules** (auth, autonomous,
cognitive, cognitive_intelligence, chaos, causality, computation, event,
infrastructure, insight, integration_communication, monitoring, query,
quality, rosetta, sat, security, security_protection, specialized, system,
vault, …) and `api/auth.py` + `api/graphql.py` + `api/security_dashboard.py`.

MCP tool surface includes `a2a_tools.py`, `autonomous_tools.py`,
`cognitive_tools.py`, `geoid_tools.py`, `linguistic_tools.py`,
`mathematical_tools.py`, `boundary_tools.py`, `system_tools.py`,
`advanced_tools.py`.

**What Ophamin observes**: nothing at this layer.
**Blind to**: every API entry point, every MCP tool call, every WebSocket
session, every GraphQL query, every CLI invocation. Auth flows, rate limits,
schema-mismatch refusals — completely invisible.

### 2.3 A2A protocol — agent registry, capability, trust, rate-limit, HMAC

```
kimera_swm/domain/autonomous/a2a/
  agent_registry.py
  capability_directory.py
  conversation_manager.py
  policy_gatekeeper.py     (HMAC + trust scores + rate limit + TTL)
  task_orchestrator.py
  agent_models.py
```

Plus an MCP bridge at `interfaces/mcp/tools/a2a_tools.py` exposing the
A2A primitives as MCP tools.

**What Ophamin observes**: nothing.
**Blind to**: agent registration/deregistration, capability-grant flow,
trust score evolution, rate-limit hits, policy violations, message latency
between agents, HMAC verification failures.

### 2.4 Network transports — seven adapters wrapping `ArchipelPeerRouter`

```
kimera_swm/domain/piovra/transports/
  async_queue.py
  tcp.py
  grpc.py
  websocket.py
  kafka.py
  rabbitmq.py
  nats.py
  network_emulator.py
```

**What Ophamin observes**: nothing.
**Blind to**: PrimePacket wire bytes (v2 compact), ed25519 signature
verification rate, dead-letter accumulation, snapshot-mismatch refusals,
per-transport throughput, partition rate.

### 2.5 Layer 4 reconciliation — three CRDTs + RIBLT + Bloom

```
kimera_swm/infrastructure/reconciliation/
  g_set.py
  scar_dag.py
  echoform_chain.py
  rateless_iblt.py        (η ≈ 1.4 post-Phase-14 fix)
  bloom_preflight.py
  offline_reconnect.py
  strict_mode.py
```

**What Ophamin observes**: nothing.
**Blind to**: CRDT convergence time, RIBLT decode success rate, Bloom
filter FP rate, gap-fill bandwidth, snapshot ID divergence.

### 2.6 Message queue + event store + CQRS

```
kimera_swm/infrastructure/message_queue/
  kafka_adapter.py
  rabbitmq_adapter.py
  rabbitmq_provider.py
  message_queue_manager.py
  message_queue_provider.py
  cqrs_manager.py
  event_store.py
  async_scar_writer.py + refined_async_scar_writer.py
```

**What Ophamin observes**: nothing.
**Blind to**: event store growth, CQRS command/query latency, async SCAR
write backlog, message queue depth.

### 2.7 Service mesh + API gateway

```
kimera_swm/infrastructure/service_mesh/
  istio_service_mesh_manager.py
  envoy_proxy.py
  service_discovery.py
  service_mesh_config.py

kimera_swm/infrastructure/api_gateway/
  auth_manager.py
  gateway_config.py
```

**What Ophamin observes**: nothing.
**Blind to**: virtual-service rollout state, Envoy circuit-breaker trips,
service-discovery TTL, gateway auth cache hits.

### 2.8 Already-existing monitoring stack — Prometheus + Grafana + Alertmanager

This is the load-bearing point. **Kimera already has a 38-file monitoring
stack**:

```
kimera_swm/infrastructure/monitoring/
  prometheus_config.yml       ← exporter config
  prometheus_exporter.py
  prometheus_metrics_collector.py
  grafana_dashboard.json
  grafana_dashboard_manager.py
  grafana_dashboard_sync_service.py
  alertmanager.yml
  alert_rules.yml
  kimera_alerts.yml
  alert_service.py
  alert_channels.py             (under observability/)
  distributed_tracer.py
  structured_logger.py
  centralized_logging_system.py
  consistency_monitor_impl.py
  database_health_monitor.py
  system_homeostasis_monitor.py
  system_monitor.py + system_health_monitor.py
  performance_monitor.py
  metrics_collector.py
  observability_manager.py
  comprehensive_monitoring_manager.py
  comprehensive_monitoring_endpoints.py
  monitoring_system.py + monitoring_service.py + monitoring.py
  docker-compose.monitoring.yml
  dashboard.py
```

Plus a parallel `kimera_swm/infrastructure/observability/` (8 files:
alerts, alert_channels, health_monitor, kccl_tracer, metrics_dashboard,
tracing).

**Implication**: Ophamin shouldn't reinvent any of this — it should
**consume** these existing telemetry streams as one of its observation
strata. The metrics already exist; Ophamin's value-add is the **proof
record discipline + cross-stratum correlation + falsifiable claims**, not
re-implementing scrape endpoints.

### 2.9 Cronos timing + KCCL — 25-file temporal infrastructure

```
kimera_swm/infrastructure/temporal/
  cronos/
    cronos_atomic_clock.py (6-layer, 51.4 µs/tick)
    cronos_sync.py (ReversePTP + PI controller)
    cronos_metrics.py
    cronos_integration_bridge.py
    dtc_flywheel.py
    global_phase_filter.py
    system_clock_reference.py
    thorium_core.py
    zeta_standard.py
  kccl_system.py
  oscillator_registry.py
  oscillators.py
  spde_engine.py + 4 variants (optimized, prime_wave, partitioned, gpu_accelerated)
  rhythm_generator.py
  cross_frequency_coupling.py
  prime_wave_cip_coordinator.py
  reservoir_computing.py
  temporal_initializer.py + temporal_learning.py
  watchdog.py + time_provider.py
```

**What Ophamin observes**: total `cycle_seconds` per Takwin cycle.
**Blind to**: per-phase KCCL timing, Cronos drift Allan deviation,
oscillator phase coherence, SPDE engine selection at runtime, watchdog
trips.

### 2.10 Quantum + encoder + frozen-on-fall + memory + security

| Cluster | Files | Ophamin sees |
|---|---|---|
| `infrastructure/quantum/` | 5 (geoid_quantum_processor, qinterpreter_service, quantum_error_correction, quantum_integration_service, quantum_reinforcement_learning) | nothing |
| `infrastructure/encoder_snapshot/` | 8 (builder, loader, manifest, snapshot, snapshot_encoder, smoke_test, verifier) | nothing |
| `infrastructure/frozen_on_fall/` | 6 (builder, manifest, state, takwin_integration, deployment_policy) | nothing |
| `infrastructure/memory/` | 14 (memory_pool_manager, gc_optimizer, leak_detector, holographic_manifold, maxwell_demon_governor, …) | nothing |
| `infrastructure/security/` + `domain/security/` | 17 + 30 = 47 (ed25519, rate_limiter, secret_rotation, manipulation_detector, gyroscopic_water_fortress, …) | GWF threat block rate via `entity` cycle |

---

## 3. The Takwin entry point is itself underused

Even on the cognitive surface Ophamin already targets, the adapter only
extracts a handful of fields from `OrchestratorResult`. Per CLAUDE.md,
`OrchestratorResult` exposes **638 fields per cycle** as of 2026-05-04
(was 542 at the 2026-04-20 audit; grows every Phase). Ophamin's
`CycleResult.raw` carries `cycle_seconds`, `walker_halt_mode`,
`phi_value`, `gwf_blocked`, `manipulation_detected`,
`dissonance_events_count`, `concepts_count`, `prime_chain`, and a few
others — call it ~15 fields.

**That's <3% of what one cycle emits.** The other 620+ fields are
discarded at the adapter boundary.

---

## 4. The proposed reframing — Ophamin v0.2 as a multi-stratum observatory

The six-wheel architecture stays. What changes is **what each wheel can
look at**.

### 4.1 Add a fourth axis to the substrate model: *stratum*

Today the adapter takes a `target` string ("entity", "walker", "rosetta",
…). Add an orthogonal **stratum** dimension:

| Stratum | Examples | Today | Proposed |
|---|---|---|---|
| `cognitive` | walker, rosetta, gwf, entity | ✓ | ✓ |
| `interface` | REST routers, GraphQL, MCP tools, CLI | ✗ | new |
| `transport` | TCP, WebSocket, Kafka, NATS pairs | ✗ | new |
| `persistence` | Postgres repos, ArangoDB, Redis, vault | ✗ | new |
| `reconciliation` | G-Set, SCAR-DAG, Echoform-chain CRDTs | ✗ | new |
| `temporal` | Cronos atomic clock, KCCL phases, oscillators | ✗ | new |
| `security` | A2A trust, ed25519 verify, GWF anchors, rate-limit | partial | full |
| `telemetry` | Prometheus scrape, structured logs, Grafana panels | ✗ | new (consumer) |
| `lifecycle` | encoder snapshot, frozen-on-fall, vessel state | ✗ | new |

A scenario picks `(stratum, target)`. Existing scenarios stay on
`(cognitive, *)`. New scenarios reach into other strata.

### 4.2 Map new strata to existing wheels

| Stratum | seeing/ | measuring/ | comparing/ | instrumenting/ | auditing/ | reporting/ |
|---|---|---|---|---|---|---|
| interface | enumerate routers / tools / GQL fields | blackbox-probe scenarios, schema-evolution claims | drift in router count / signature | per-request resource profile via wrk/oha | ruff/bandit on router code | latency histograms |
| transport | enumerate transport instances | partition-recovery scenarios, RIBLT bandwidth claims | wire-byte drift across commits | per-transport throughput probe | scan for unsigned packet acceptance | bandwidth/latency charts |
| persistence | schema introspection across all 6 PG repos + Arango + Redis | DB consistency-after-chaos scenarios | schema drift across commits | per-query timing | sqlfluff / dataset migration audit | DB health dashboard |
| reconciliation | enumerate CRDT instances | convergence-time scenarios | RIBLT η drift across commits | per-merge cost profile | scan for non-idempotent paths | convergence proofs |
| temporal | enumerate oscillators + KCCL phases | Cronos Allan-deviation scenarios | drift in phase coherence | per-phase wall-time | check for monotonic-clock assumptions | KCCL timing chart |
| security | enumerate auth flows, A2A policy rules | red-team scenarios (Family M-style, expanded) | GWF anchor diff across commits | per-rule eval cost | bandit + custom security pillar | threat-detection report |
| telemetry | scrape Kimera's `/metrics` endpoint | claims about Prometheus alert firing rate | metric cardinality drift | passive — uses existing exporter | check alert_rules.yml well-formedness | Grafana-panel embeds |
| lifecycle | inspect snapshot manifests, frozen-on-fall manifests | snapshot tamper-detection scenarios | snapshot ID divergence across nodes | snapshot read time | verify HMAC + ed25519 on every artifact | lifecycle audit trail |

Every stratum slots into one or more of the existing six wheels. **No new
wheel is needed** — but each existing wheel needs new pillars/probes.

### 4.3 The single biggest leverage move: consume the Prometheus stream

Kimera **already exports metrics**. Ophamin's `seeing/` wheel should add a
**`PrometheusScrapeProbe`** that:

1. Connects to Kimera's Prometheus exporter (configured at
   `infrastructure/monitoring/prometheus_config.yml`).
2. Streams metrics into Ophamin's measurement engine as a passive
   observation stream alongside the active scenario stream.
3. Aligns timestamps with Ophamin's pre-registered scenario windows so
   `(scenario, prometheus_snapshot_before, prometheus_snapshot_during,
   prometheus_snapshot_after)` becomes a single signed observation.
4. Triggers `measuring/scenarios/observability_*` scenarios that test
   claims about the alert rules themselves (e.g. "the
   `KimeraHighPhiVariance` alert fires when Φ stdev > 0.1 over a 5-min
   window").

This single addition unlocks observability into roughly **20 of Kimera's
68 infrastructure subpackages** without any new probe code on Ophamin's
side — they all already emit to Prometheus.

### 4.4 The second biggest leverage move: expand the adapter's field extraction

Today's adapter copies ~15 fields from `OrchestratorResult`. Replace with a
**field-projection layer** that:

1. Maintains a JSON allowlist mapping `OrchestratorResult` fields → opaque
   `raw` keys.
2. Defaults to copying ~50 high-signal fields (the existing 15 + Walker
   M1/M2/M3/M4 counters + per-phase wall-time + per-stratum substrate
   signals).
3. Lets a scenario opt-in to additional fields via
   `scenario.required_raw_fields = ["eikonal_mean_arrival_time", ...]`.
4. Validates at run-time that the requested fields exist on the result —
   loud failure if Kimera renames a field (which surfaces drift instead
   of hiding it).

This costs **one file** (a `field_projection.py` in
`seeing/substrate/`), zero changes to scenario authoring, and immediately
makes 5–10× more fields available to measuring pillars.

### 4.5 Three new measuring pillars (additive to the existing O · F · A · M · I · N six)

| Pillar | What it does | Backing library |
|---|---|---|
| **L (atency)** | Quantifies per-stratum latency distributions (p50/p95/p99/max) with the same Wilson-CI discipline applied to histograms via `numpy.percentile` + bootstrap | numpy / statsmodels |
| **B (andwidth)** | Quantifies bytes-on-wire for transport scenarios, with RIBLT savings versus full-state baselines as a paired comparison | numpy |
| **A (vailability)** | Quantifies uptime / error rates / circuit-breaker trips across the multi-protocol interface layer | scipy.stats binomial |

Plus one cross-cutting pillar:

| Pillar | What it does |
|---|---|
| **Σ (correlation)** | Cross-stratum correlation: when GWF fires (security), does request latency spike (interface)? When CRDT merge slows (reconciliation), does cognitive Φ drift (cognitive)? Pearson + Spearman with multiple-comparison correction |

### 4.6 Three new auditing pillars (additive to the existing six)

| Pillar | Wraps | Surfaces |
|---|---|---|
| **schema-audit** | sqlfluff or sqlglot on `*.sql` + `schema/*.py` | drift in PostgreSQL repository schemas, migration gaps |
| **api-audit** | OpenAPI spec extraction from FastAPI app + `schemathesis` blackbox tests | undocumented endpoints, schema-vs-implementation drift |
| **security-config-audit** | parse `alert_rules.yml`, `alertmanager.yml`, `prometheus_config.yml`, A2A `policy_gatekeeper.py` rules | mis-configured rules, missing alert coverage, over-broad anchors |

### 4.7 Three new scenarios (one per tier, exercising the new strata)

| Tier | Scenario | Stratum | Claim |
|---|---|---|---|
| Scientific | **InterfaceContractStability** | interface | Across 30 days of Kimera commits, the OpenAPI spec breaking-changes count is ≤ N at every commit boundary (signed) |
| Engineering | **TransportRecoveryTime** | transport | After a simulated partition + reconnect, all 6 transport adapters resync the G-Set to Jaccard=1.0 within ≤ T seconds (signed) |
| Philosophical | **MultiStratumSelfModel** | telemetry | When the substrate processes text about its own infrastructure (a `prometheus_config.yml` block, an Istio `VirtualService` definition), the `system_homeostasis_monitor`'s `homeostasis_score` differs significantly from neutral text (Mann-Whitney U, paired) |

---

## 5. What this reframing buys

| Before (v0.1) | After (v0.2) |
|---|---|
| 11 cognitive primitives observable | 11 cognitive + ~50 infrastructure surfaces |
| ~15 `OrchestratorResult` fields per cycle | ~50 default + opt-in for the other 580 |
| Six wheels, all targeting cognitive | Six wheels × nine strata = 54-cell coverage matrix |
| No telemetry consumer | Prometheus + Grafana + Alertmanager stream consumer |
| O · F · A · M · I · N (6 measuring pillars) | + L · B · A · Σ (10 pillars) |
| ruff · bandit · mypy · vulture · radon · pip-audit (6 audit pillars) | + schema-audit · api-audit · security-config-audit (9 pillars) |
| Six scenarios | + InterfaceContractStability + TransportRecoveryTime + MultiStratumSelfModel (9 scenarios) |
| One target per scenario | `(stratum, target)` tuple — many-to-many |
| Falsifiable claims about cognition | Falsifiable claims about cognition + infrastructure + cross-stratum interaction |

The shape of the framework doesn't change — it just gains depth.

---

## 6. Honest unknowns

- **MCP transport authentication**: I haven't verified whether Kimera's
  MCP server runs in stdio-only mode (no network surface) or with HTTP/SSE
  (network-exposed). If stdio-only, MCP observability is limited to
  process-level instrumentation.
- **Kafka/RabbitMQ/NATS deployment status**: code is present; whether
  these are actually wired into production runtime or are
  WIRE_CANDIDATEs for future Archipel deployment is unclear from CLAUDE.md
  alone. Operational observability requires they actually fire.
- **Prometheus exporter actively scrapeable**: I see the `.yml` config
  and the `prometheus_exporter.py` module but haven't confirmed the
  exporter is bound to a port at runtime. Verify via
  `lsof -iTCP:<port>` against a running Kimera instance before building
  the consumer.
- **47 REST routers production-bound**: similarly, the routers exist in
  source but whether the FastAPI app actually mounts all 47 on a running
  instance is a separate question. `kimera_swm/api/__init__.py` probably
  knows.
- **A2A protocol traffic**: A2A is implemented; whether there are
  currently any agents talking on it during a typical Kimera run is a
  separate measurement. If A2A is dormant in single-node Kimera,
  observability is hypothetical until Archipel deployment lights it up.

Each of these is a `seeing/discovery/`-style probe rather than a guess.
Step zero before building v0.2 is **measuring which surfaces are live**.

---

## 7. Suggested next step ordering

If we commit to v0.2:

1. **Discovery probes first** (1–2 sessions): for each of the nine strata,
   land a `seeing/discovery/<stratum>_inventory.py` that enumerates the
   primitives Kimera actually exposes at runtime (not from source). This
   builds the empirical baseline of "what's live."
2. **Field projection** (1 session): replace the adapter's ad-hoc field
   extraction with `field_projection.py` + allowlist.
3. **Prometheus consumer** (1 session): land a `PrometheusScrapeProbe` in
   `seeing/` + an `observability_*` scenario that uses it.
4. **One new scenario per tier** (3 sessions): InterfaceContractStability
   (scientific) → TransportRecoveryTime (engineering) →
   MultiStratumSelfModel (philosophical).
5. **Three new measuring pillars** (1 session): L · B · A · Σ. Wire them
   into the existing engine with the same Wilson-CI / Cohen's d /
   Mann-Whitney discipline applied to their respective signal types.
6. **Three new auditing pillars** (1 session): schema-audit, api-audit,
   security-config-audit.

Eight focused sessions. Each one ends with green tests + a signed proof
record demonstrating the new surface. No big-bang rewrite.

---

## 8. What stays the same

- The non-deletion stance toward Kimera primitives.
- Pre-registration discipline — claims before measurement.
- Loud failure / no silent fallbacks.
- Signed, content-addressed, HMAC-verified proof records.
- The six wheels and three tiers.
- `MockSubstrate` so the framework runs without Kimera present.
- Independence from Kimera at the code level (only the adapter knows).

---

*Authored by Claude (Opus 4.7 1M context), 2026-05-15, after re-reading
CLAUDE.md, EMPIRICAL_VALIDATION.md, KIMERA_STATE.md, and walking the
infrastructure tree. Awaiting owner decision on scope before any
implementation work.*
