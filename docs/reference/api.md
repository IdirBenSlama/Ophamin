# Public API reference

Auto-generated from the source docstrings via
[`mkdocstrings`](https://mkdocstrings.github.io/). Every public symbol
listed below is part of Ophamin's stable surface; breaking changes
follow the [semver promise](https://github.com/IdirBenSlama/Ophamin/blob/main/SCHEMAS.md#migration-policy).

## Top-level

::: ophamin
    options:
      members:
        - __version__

## Protocols

::: ophamin.protocols
    options:
      members:
        - Pillar
        - ScenarioProtocol
        - DatasetConnector
        - SubstrateProbe

## Registry

::: ophamin.registry
    options:
      members:
        - register_pillar
        - register_scenario
        - register_dataset_connector
        - register_substrate_probe

## Signed-record codecs

### Empirical Proof Record

::: ophamin.measuring.proof.record
    options:
      members:
        - EmpiricalProofRecord
        - Claim
        - Threshold
        - Verdict
        - PillarEvidence
        - PreRegistration
        - DatasetRef
        - Reproduction

::: ophamin.measuring.proof.codec
    options:
      members:
        - SCHEMA_VERSION
        - dump
        - load
        - validate
        - verify_signature
        - ingest
        - list_proofs

### Audit Record

::: ophamin.auditing.audit_record
    options:
      members:
        - AuditRecord
        - AuditSummary

::: ophamin.auditing.codec
    options:
      members:
        - SCHEMA_VERSION
        - dump
        - load
        - validate
        - verify_signature
        - list_audits

### Campaign Record

::: ophamin.campaign
    options:
      members:
        - CAMPAIGN_SCHEMA_VERSION
        - CANONICAL_PHASE_ORDER
        - CampaignPhase
        - CampaignRecord
        - run_campaign
        - dump_campaign
        - load_campaign

### Regression Alert Record

::: ophamin.comparing.regression_alert
    options:
      members:
        - REGRESSION_ALERT_SCHEMA_VERSION
        - RegressionAlertRecord
        - DriftDelta

## Substrate base

::: ophamin.seeing.substrate.base
    options:
      members:
        - SubstrateUnderTest
        - CycleResult

::: ophamin.seeing.substrate.mock
    options:
      members:
        - MockSubstrate

::: ophamin.seeing.substrate.kimera_adapter
    options:
      members:
        - KimeraAdapter

## Corpus base

::: ophamin.seeing.corpus.base
    options:
      members:
        - Corpus
        - CorpusRecord

## Scenario base

::: ophamin.measuring.scenarios.base
    options:
      members:
        - Scenario
        - ScenarioScore
        - Tier
        - DEFAULT_SIGN_KEY

## Audit pillar base

::: ophamin.auditing.base
    options:
      members:
        - AuditPillar
        - Finding
        - FindingSeverity
        - PillarResult

## Agentic layer (local-LLM tooling)

LLM-assisted observatory tooling that sits *beside* the measurement
engine — advisory, default-off, opt-in per call, and never inside a
scenario's measurement path. Targets any OpenAI-compatible local
runtime (Ollama / MLX-LM / LM Studio) via `OPHAMIN_LLM_BASE_URL`; every
call persists a signed [`LLMCallRecord`](#agentic-layer-local-llm-tooling)
under `proofs/llm_calls/`.

::: ophamin.agentic
    options:
      members:
        - LLMClient
        - LLMClientError
        - TaskTier
        - TASK_ROUTING
        - pick_model
        - LLMCallRecord
        - persist_call

The seven agents live under `ophamin.agentic.agents` — `adapter_gen`,
`proof_brief`, `refuted_triage`, `bundle_query`, `prereg_validator`,
`confound_enumerator`, `scenario_gen` — each exposing a single
entry-point function. They are driven through the
`ophamin agent {adapt, brief, triage, query, prereg, confounds, scenario-gen}`
CLI rather than imported directly.
