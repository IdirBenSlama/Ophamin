# Ophamin Console — Architecture & Information Architecture

> Successor to [`OPHAMIN_GUI_DESIGN_BRIEF.md`](OPHAMIN_GUI_DESIGN_BRIEF.md).
> The brief defined the **visual language** (UniFi/Ubiquiti). This document
> defines the **information architecture** — which screens exist, which are
> built vs. routed-to vs. cut, and the phased plan to get there.
>
> Status: **adopted direction**, phased execution. The React Console ships
> today at `/app` (see `src/ophamin/http_api/console/`). This spec governs
> how it evolves.

---

## 1. Premise

Ophamin's architecture is "wrap mature open-source projects; don't
reimplement them." Every pillar library already ships a battle-tested
interface:

| Ophamin dependency | Its mature native interface |
|---|---|
| `mlflow` | MLflow Tracking UI (runs / params / metrics / artifacts / registry) |
| `prometheus_client` (`/metrics`) | Grafana (scrapes Prometheus) |
| `opentelemetry-*` | Jaeger / Tempo / Grafana traces |
| `prov` + `dvc` | PROV-O graph viewers / `dvc dag` / DVC Studio |
| `arviz` + `pymc` | arviz posterior plots (the Bayesian native UI) |
| `ruff/bandit/mypy/...` | SARIF → GitHub Code Scanning / VS Code |
| `cyclonedx` | SBOM viewers (Dependency-Track) |
| `river` | streaming-drift dashboards (Grafana / notebooks) |
| `statsmodels/scipy/sklearn` | Jupyter notebooks |
| `mkdocs-material` | the documentation site itself |

A custom GUI that re-skins those is **reinventing the wheel in mock** —
and competing in the exact category (generic ML/observability dashboard)
that MLflow + Grafana already win.

## 2. The principle (one line)

> **Own the signed empirical layer; route to the commodity analytics.**

The only thing *no* OSS tool provides — Ophamin's actual invention — is the
chain:

> a **falsifiable claim** (five-tuple, pre-registered) → a **signed,
> reproducible `EmpiricalProofRecord`** (9 sections, HMAC over canonical
> bytes, O·F·A·M·I·N pillar evidence) → the **Kimera substrate state that
> produced it** (geoid / scar / vault / prime / Φ / halt-mode / GWF).

Everything off that spine is a commodity rendered better elsewhere.

## 3. Visual language vs. product philosophy

Keep the **UniFi/Ubiquiti visual language** — it suits an observatory
(calm, dense, dark, status-pills, mono technical values, teal accent
`#2dd4bf`). But also adopt UniFi's **product philosophy**, which the
current 18-screen Console does *not*:

- UniFi is **~5 deep apps** (Network / Protect / Access…), not 18 flat
  dashboards.
- A **site/console selector** at the top picks *what you're observing*.
- A **topology map** is the signature hero.
- **Devices/clients** carry live status pills + drill-in.
- An **Integrations** area adopts external services rather than rebuilding
  them.

## 4. Build / Defer / Cut

| Screen (current) | Decision | Rationale |
|---|---|---|
| Overview | **BUILD** | at-a-glance corpus + substrate health + event feed |
| Proofs | **BUILD** | the signed-record corpus — the heart (live ✅) |
| Scenarios | **BUILD** | falsifiable-claim catalog + pre-registration (live ✅) |
| Run | **BUILD** | trigger scenario → signed proof (live ✅) |
| Agents | **BUILD** | 7 agents + signed LLM-call audit (live ✅) |
| **Substrate** (new) | **BUILD** | live Kimera scope: organ cards + manifold topology hero — *the missing soul* |
| Campaigns (new) | **BUILD** | sweeps + multiplicity correction + meta-analysis (Ophamin-proper framing) |
| Verify (new) | **BUILD** | drop-a-proof HMAC check (custom canonicalization) |
| Insights (was scattered) | **BUILD** | unified event feed (new proofs / drift / agent calls) |
| Telemetry | **DEFER → Grafana** | Prometheus scrape; `/metrics` + "Open in Grafana" |
| drift | **DEFER → Grafana** | River computes it; show signed drift-alert + link |
| lineage / inspector | **DEFER → prov/DVC** | render the proof's PROV-O, link to viewer |
| audit | **DEFER → SARIF** | export → code-scanning, don't rebuild a linter UI |
| interop | **DEFER → target tools** | export is Ophamin's job; the *viewer* isn't |
| roadmap | **DEFER → docs site** | mkdocs already renders it |
| control / control-infra | **CUT** | fleet-ops theater; Ophamin is single-process |
| lab | **CUT** | Jupyter is the native sandbox |
| chat | **HOLD** | routes to agent *execution* (LLMs over HTTP) — opt-in only, not now |
| settings | **KEEP (local)** | client-side prefs (theme/density/accent); no backend |

Net: **18 → ~9 first-class apps + an Integrations area.**

## 5. Target information architecture

**Top bar (UniFi "console" context):**
- **Substrate selector** — `kimera-swm @ <commit>`. Picks *which substrate
  state* you're observing. Makes the partition/provenance principle the
  first decision. (UniFi's site/console picker.)
- Global search (⌘K). System-status pill (real, derived).

**Left rail — first-class apps:**
1. **Overview** — corpus + substrate health, latest verdicts, event feed
2. **Proofs** — the signed-record corpus
3. **Scenarios** — claim catalog + Run
4. **Substrate** — live Kimera scope + manifold topology hero ← keystone
5. **Campaigns** — sweeps + multiplicity correction + meta-analysis
6. **Verify** — drop-a-proof signature check
7. **Agents** — agents + signed LLM-call audit
8. **Insights** — unified event feed
9. **Integrations** — BYO Grafana / MLflow / DVC / SARIF / docs (settings)

## 6. The Substrate app (the keystone)

The one screen that's unmistakably a *Kimera* observatory, and the place
the UniFi aesthetic earns its keep most. Two parts, both UniFi-native:

- **Organ status cards** (UniFi "devices"): geoid, scar, vault, prime, Φ,
  halt-mode, GWF — each a card with a live status pill, a key metric, a
  sparkline, and drill-in. These are the substrate's named primitives.
- **Manifold topology hero** (UniFi "network map"): the geoid graph + scar
  network, with persistent-homology summary (β₀ / β₁ / β₂). The signature
  visual.

**Data source:** the `KimeraAdapter` subprocess boundary. Requires new
read-only endpoints (Phase 3) exposing substrate state — there is no live
substrate surface today, which is why this app does not yet exist.

## 7. Integrations model (route, don't reinvent)

A UniFi-style "Integrations" page. For each mature tool:

- **Configured** (env var set, e.g. `OPHAMIN_GRAFANA_URL`) → deep-link card
  ("Open in Grafana"), optionally an embedded iframe.
- **Not configured** → a card explaining what it provides + how to point
  Ophamin at it.
- **Deliberately thin fallback** only where neither is available (e.g. the
  raw `/metrics` text when no Grafana is wired).

This is *bring-your-own*: Ophamin adopts your Grafana/MLflow/DVC, it does
not rebuild them. Backed by a small `/integrations` endpoint returning the
configured URLs (none by default — honest).

## 8. Honesty / provenance discipline

For an observatory whose thesis is *signed, falsifiable, auditable*, no
pixel of fabricated data may be indistinguishable from measured data.

- **Provenance badges everywhere:** `LIVE` / `SAMPLE` / `DERIVED`, wired
  from the `OPHAMIN.live.*` flags (already computed in `data.js`, never
  shown).
- **No fabricated-as-real values.** Known offenders to remove:
  - the global "CONTINUOUS GATES" bar (`shell.jsx`) hardcodes
    `hardening 2,944` — that's *Kimera's* number; Ophamin has its own. →
    derive from real hydrated facts (version, signed-proof count) or drop.
  - the per-agent "AUDIT TRAIL FOR THIS CALL" block (`agents.jsx`) hardcodes
    a fake model/hash/signature *next to* the real signed-audit table. →
    remove; point at the real records.
- Illustrative screens carry a `SAMPLE` badge until backed.

## 9. Phased execution plan

- **Phase 1 — honesty & restraint (no new backend):** provenance badges
  from `live.*`; fix the gates bar; remove the fake agent-audit block; mark
  illustrative screens `SAMPLE`.
- **Phase 2 — route, don't reinvent:** Integrations app + `/integrations`
  endpoint; substrate-commit selector; demote Telemetry/lineage/audit/
  roadmap to deep-links; cut control/lab.
- **Phase 3 — the Kimera observatory:** the **Substrate app** (organ cards
  + manifold topology hero) backed by new `KimeraAdapter` endpoints;
  per-proof construction-loop panel (measure → remediate → opportunity →
  optimize → enhance); Campaigns (multiplicity correction); Verify
  drop-zone.
- **Phase 4 — SOTA polish:** SSE/WebSocket live updates (new proofs, run
  progress, streaming metrics); one-click reproduce-this-proof; optional
  production build (React prod UMD / prebuild) replacing the in-browser
  dev-build + Babel.

## 10. Non-goals

- Do **not** rebuild Grafana / MLflow / prov / DVC / SARIF viewers / the
  docs site. Adopt them.
- Do **not** add fleet/ops "control room" theater — Ophamin is a
  single-process tool.
- Do **not** ship fabricated values indistinguishable from measured ones.

---

*The keystone is the Substrate app: UniFi organ cards + a live manifold
topology map. It is the one view that is unmistakably a Kimera observatory,
and the reason the UniFi language belongs here.*
