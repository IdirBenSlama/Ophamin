# Run a full campaign

A **campaign** runs the framework's six wheels end-to-end against a
substrate, producing one signed `CampaignRecord` that aggregates each
phase's output. This is the canonical way to exercise Ophamin: it
covers `seeing → measuring → comparing → instrumenting → auditing →
reporting` in one pass.

## CLI invocation

```bash
ophamin run-all --out-dir ./my-campaign
```

By default this runs against a `MockSubstrate` and selects every
default-instantiable scenario. The output directory will contain:

```
my-campaign/
├── CAMPAIGN.json         the signed CampaignRecord
├── REPORT.md             the rolled-up Markdown summary
├── SUMMARY.md            cross-phase verdict / drift summary
├── proofs/
│   ├── scientific/...     per-scenario signed proofs by tier + family
│   ├── engineering/...
│   └── philosophical/...
└── per-phase/...          phase-specific artefacts (audit findings, etc.)
```

## The six phases

| Phase | What it does | Skips when |
|---|---|---|
| `seeing` | discover the substrate's surface (Kimera field schema) | substrate has no `kimera_repo` (e.g. MockSubstrate) |
| `measuring` | run every selected scenario; emit signed proofs | always runs (the load-bearing phase) |
| `comparing` | drift detection across the freshly-written proofs | always runs (no-op if proofs/ is empty) |
| `instrumenting` | per-cycle resource profile | substrate isn't wrapped in `InstrumentedSubstrate` |
| `auditing` | static-analysis sweep over the substrate's source | substrate has no `kimera_repo` |
| `reporting` | render the rolled-up Markdown | always runs |

A phase can return `ok` / `skipped` / `failed`. The campaign continues
through every phase regardless — loud-failure at the campaign level,
not per-phase.

## Against a real Kimera-SWM tree

```bash
ophamin run-all \
  --repo /path/to/kimera-swm \
  --target arachne \
  --scenarios memory-as-deformation,prime-cross-instance \
  --out-dir ./kimera-campaign
```

The CLI accepts:

- `--repo PATH` — point at a real Kimera repo to enable `seeing` +
  `auditing`
- `--target NAME` — substrate target (default `entity`; see
  `KIMERA_TARGETS`)
- `--scenarios A,B,C` — filter to specific scenarios (comma-separated)
- `--skip PHASE,PHASE` — skip named phases (e.g. `--skip auditing`)
- `--quiet` — suppress phase-by-phase chatter

## Python API

For programmatic use:

```python
from ophamin.campaign import run_campaign
from ophamin.measuring.scenarios import (
    InterfaceContractStabilityScenario,
    SubstrateCompletenessScenario,
)
from ophamin.seeing.substrate.mock import MockSubstrate

record = run_campaign(
    substrate=MockSubstrate(seed=1),
    scenarios=[InterfaceContractStabilityScenario, SubstrateCompletenessScenario],
    out_dir="my-campaign/",
    sign_key=b"my-team-key",
)

print(record.status_counts)
# {"ok": 4, "skipped": 2, "failed": 0}
```

## Reading the CampaignRecord

```bash
ophamin schema info my-campaign/CAMPAIGN.json
ophamin schema validate my-campaign/CAMPAIGN.json --key my-team-key
```

The record carries every phase's status + summary + artefact paths.
See [`SCHEMAS.md`](../reference/schemas.md) for the schema layout.

## CI-grade campaigns

For a CI-grade campaign (every scenario, every phase, real Kimera
tree on a build runner), see the
[release procedure](../RELEASE_PROCEDURE.md) for the canonical
invocation + post-processing steps.
