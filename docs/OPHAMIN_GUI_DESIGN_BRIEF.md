# Ophamin Console — GUI Design Brief

> **Purpose of this document.** Everything Claude (or any designer) needs to
> build a serious, production-grade GUI for Ophamin in the **Ubiquiti / UniFi**
> visual language — dark, data-dense, calm, with fluid purposeful motion.
> Self-contained: domain primer, exact API contract, design tokens, screen
> architecture, component inventory, motion spec, and a build sequence.
>
> Paste this whole file into Claude (claude.ai, with artifacts) and build
> screen by screen. The provisional GUI it replaces lives at
> `src/ophamin/http_api/static/` (vanilla HTML/JS) — keep it running at `/ui`
> until the new console reaches parity, then mount the new one at `/app`.

---

## 0. TL;DR — what I suggest

- **Name it the "Ophamin Console."** UniFi has the "Network/Protect/Console"
  framing; Ophamin is an *empirical observatory*, so "Console" fits — a calm
  instrument panel over a running substrate.
- **Stack:** React + Vite + TypeScript + Tailwind CSS + shadcn/ui +
  Framer Motion + Recharts + lucide-react. This is exactly what Claude's
  artifact builder is strongest at, and it gives you the UniFi look (shadcn
  cards/tables/tabs) plus fluid motion (Framer Motion) for free.
- **Brand fusion, not copy:** adopt UniFi's *structural* language (dark shell,
  left rail, dense cards, soft elevation, micro-motion) but keep **Ophamin's
  teal/cyan accent** rather than UniFi blue — it reads "scientific instrument"
  not "network switch." Semantic verdict colors (green / red / amber) are
  non-negotiable and carry meaning.
- **Architecture:** build with Vite → static bundle → serve from FastAPI
  `StaticFiles` at `/app`. Build happens at dev time; runtime just serves
  static files (preserves Ophamin's "no runtime build step" property). The new
  console talks to the **same 12 REST endpoints** the provisional GUI uses.
- **Signature motif:** the **six wheels** (Ophamin = Ophanim, wheels-within-
  wheels). Use a six-segment radial as the loading state, the favicon, and a
  subtle "system health" ring on the dashboard. It's the brand's whole identity.
- **Build mock-data-first:** the §6 example payloads let you build every screen
  before wiring live fetch. Then point at a running `ophamin http serve`.

---

## 1. What Ophamin is (so the design means something)

Ophamin is an **empirical observatory framework**: it runs *falsifiable
scenarios* against a *substrate under test* (default: Kimera-SWM) and emits
**content-addressed, HMAC-signed proof records**. Think of it as a CI system,
but for scientific claims instead of code.

The mental model — **"six wheels"** (the framework's own structure):

| wheel | role |
|---|---|
| **seeing** | senses the substrate + the corpus |
| **measuring** | the proof engine + scenarios + statistical pillars (O·F·A·M·I·N) |
| **comparing** | cross-commit retrospection, drift, provenance |
| **instrumenting** | per-cycle CPU / RSS / page-fault sampling |
| **auditing** | static-analysis orchestration (ruff/bandit/mypy/pip-audit) |
| **reporting** | renders results to Markdown / HTML / LaTeX / PDF |

Core nouns the GUI surfaces:

- **Scenario** — a named, falsifiable test. Has a *tier*, *family*, *goal*,
  *method*, *falsification consequence*, and (when materializable) a **claim**.
- **Claim** — a falsifiable five-tuple: *statement*, *operationalization*,
  *threshold* (`metric comparator value units`), *h0*, *h1*.
- **Proof / bundle** — the signed output of running a scenario. Carries a
  **verdict** (`validated` / `refuted` / `inconclusive`), the observed value,
  evidence (statistical pillars with CIs / p-values), pre-registration hashes,
  data provenance, and ships in **5 formats** (JSON / MD / HTML / TEX / PDF),
  often with an embedded matplotlib chart.
- **Tier** — bundles group by tier: `engineering`, `measurement_machinery`,
  `philosophical`, `scientific`.
- **Verdict** — the semantic heartbeat. The whole console should make verdict
  state instantly legible.

**Design implication:** this is a *monitoring + investigation* tool, not a
marketing site. Optimize for at-a-glance verdict state, fast filtering across
many bundles, and deep reading of a single proof. Calm, dense, precise.

---

## 2. The UniFi / Ubiquiti design language (distilled to tokens)

UniFi's feel = **dark, quiet, structured, dense, smoothly animated**. Concrete
distillation:

### 2.1 Color (dark-first)

```
/* Surfaces — near-black, layered by elevation */
--bg-base:        #0e1116;   /* app background */
--bg-surface:     #161a21;   /* cards, rails */
--bg-surface-2:   #1c2129;   /* nested panels, table rows hover */
--bg-elevated:    #232a33;   /* popovers, dropdowns, active rows */
--border:         #2a313b;   /* hairline borders */
--border-strong:  #3a434f;

/* Text */
--text-primary:   #e8edf2;
--text-secondary: #9aa7b4;
--text-muted:     #6b7785;

/* Accent — Ophamin teal/cyan (NOT UniFi blue) */
--accent:         #2dd4bf;   /* primary actions, active nav, focus */
--accent-hover:   #5eead4;
--accent-press:   #14b8a6;
--accent-soft:    rgba(45, 212, 191, 0.12);  /* tinted backgrounds */

/* Semantic verdict colors (carry meaning — keep distinct + accessible) */
--validated:      #34d399;   --validated-bg: rgba(52,211,153,0.14);
--refuted:        #f87171;   --refuted-bg:   rgba(248,113,113,0.14);
--inconclusive:   #fbbf24;   --inconclusive-bg: rgba(251,191,36,0.14);

/* Data viz ramp (charts/gauges) */
--viz-1:#2dd4bf; --viz-2:#60a5fa; --viz-3:#a78bfa; --viz-4:#f472b6;
--viz-5:#fbbf24; --viz-6:#34d399;
```

Provide a **light theme** too (UniFi has both): invert surfaces to
`#f7f9fb / #ffffff / #eef2f6`, text to `#1a1d21 / #51606e`, keep accent +
verdict hues, lighten the tints. Theme toggle in the top bar, persisted to
`localStorage`, respects `prefers-color-scheme` on first load.

### 2.2 Typography

- **Font:** Inter (or the system UI stack). UniFi uses a clean grotesque; Inter
  is the closest free match and ships with the artifact stack.
- **Mono:** `ui-monospace, "SF Mono", Menlo` for hashes, metric names, values,
  code, claim thresholds.
- **Scale (rem):** 0.6875 (11px micro/labels), 0.75 (12 body-dense), 0.8125
  (13 body), 0.875 (14 base), 1 (16 section), 1.25 (20 h2), 1.5 (24 h1),
  2 (32 stat numbers), 2.5 (40 hero stat).
- **Weights:** 400 body, 500 labels/nav, 600 headings/stat numbers.
- **Tracking:** slightly tight on big numbers (`-0.01em`), slightly loose on
  ALL-CAPS micro-labels (`+0.04em`). UniFi loves small uppercase section
  labels.

### 2.3 Space, radius, elevation

- **Spacing scale:** 4 / 8 / 12 / 16 / 20 / 24 / 32 / 48 (Tailwind 1–12).
- **Radius:** `--r-sm: 6px` (chips, inputs), `--r-md: 10px` (cards),
  `--r-lg: 14px` (modals, big panels), `--r-full: 9999px` (pills, dots).
- **Elevation (dark):** prefer **borders + subtle inner highlight** over heavy
  shadows. Cards: `1px solid var(--border)` + `box-shadow: 0 1px 2px
  rgba(0,0,0,0.3)`. Popovers/modals get a real shadow: `0 12px 32px
  rgba(0,0,0,0.5)`. Active/hover rows lift via background, not shadow.
- **Density:** UniFi is dense. Table rows ~36–40px. Card padding 16–20px.
  Gutters 16px. Don't pad like a consumer marketing page.

### 2.4 Shape of the shell

The canonical UniFi layout — **fixed left rail + top bar + scrollable content**:

```
┌────────────────────────────────────────────────────────────┐
│  TOPBAR: brand · global search · health dot · version · theme │
├──────────┬─────────────────────────────────────────────────┤
│  LEFT    │                                                   │
│  RAIL    │   CONTENT AREA (per-screen)                       │
│  (icons  │                                                   │
│  +labels)│                                                   │
│          │                                                   │
└──────────┴─────────────────────────────────────────────────┘
```

- Left rail ~220px (collapsible to ~64px icon-only, animated). Active item: a
  left accent bar (3px) + tinted background + accent icon. UniFi signature.
- Top bar ~56px: brand lockup left; centered/left global search (⌘K palette);
  right cluster = live health dot, version chip, theme toggle, (optional)
  substrate selector.
- Content scrolls independently; rail + top bar are fixed.

---

## 3. Motion spec (the "fluid animations" you want)

UniFi motion is **quick, smooth, and purposeful** — never bouncy-for-the-sake-
of-it. Rules:

- **Durations:** 120ms (hover/press feedback), 200ms (tab/expand), 280ms (page
  transitions), 600–900ms (one-time reveals like number counters / gauge
  sweeps).
- **Easing:** standard `cubic-bezier(0.4, 0, 0.2, 1)` for most; `cubic-bezier
  (0.16, 1, 0.3, 1)` (ease-out-expo) for entrances; Framer Motion `spring`
  (`stiffness: 280, damping: 30`) for the rail collapse + draggable/expanding
  panels only.
- **What animates:**
  - **Stat numbers count up** on load/refresh (Framer Motion `useSpring` or a
    count-up hook). The dashboard's 33 bundles / 21 validated should *tick* up.
  - **Verdict donut** sweeps in (animate `strokeDashoffset`).
  - **Page/route transitions:** fade + 8px upward slide, 280ms.
  - **List/table rows:** stagger-in (20ms per row, cap ~12) on first paint;
    smooth height on expand/collapse.
  - **Tab underline:** a shared `layoutId` indicator that slides between tabs
    (Framer Motion `layout`).
  - **Hover:** rows/cards lift via background + 1px border-accent; 120ms.
  - **Skeleton loaders** (shimmer) for every async panel — never a bare
    "Loading…". UniFi always shows structured skeletons.
  - **Live data:** a subtle pulse on the health dot; a faint "updated" flash on
    metric tiles when their value changes.
  - **The six-wheels loader:** six concentric/segmented arcs rotating at
    different rates — the brand's signature spinner + favicon.
- **Respect `prefers-reduced-motion`:** disable counters/slides, keep instant
  state changes. (Accessibility requirement.)

---

## 4. Information architecture (screens)

Left-rail nav, in order:

1. **Overview** (dashboard) — landing.
2. **Proofs** — the bundle explorer.
3. **Scenarios** — the catalog.
4. **Run** — the run console.
5. **Telemetry** — metrics/gauges.
6. **Agents** — the local-LLM agentic layer (optional, phase 2).
7. **Settings** — theme, substrate target, sign-key handling.

### 4.1 Overview / Dashboard

The instrument panel. Above the fold, no scrolling for the essentials.

- **Hero stat row:** 4–5 `StatTile`s with count-up: Scenarios (33), Bundles
  (33), Validated (21), Refuted (10), Inconclusive (2). Each tile: big number,
  label, tiny trend/sparkline, semantic tint for the verdict tiles.
- **Verdict donut** — the 21/10/2 split as an animated donut with a legend;
  click a segment → jumps to Proofs filtered by that verdict.
- **Six-wheels health ring** — a hero radial showing the six wheels; each arc
  green when its area is healthy (derive from `/health` + presence of recent
  proofs). The brand centerpiece.
- **Recent proofs** — last ~8 bundles as a compact table (date · scenario ·
  verdict pill · hash), newest first; row click → Proofs detail.
- **System strip** — version chip, health dot, uptime, substrate name + git
  commit (from a recent proof's `data.substrate_git_commit`).

### 4.2 Proofs (bundle explorer)

The most-used screen. Two-pane *or* table-with-drawer (recommend a **filterable
table** as primary, with a detail drawer/right-pane — scales better than the
provisional tree at hundreds of bundles).

- **Filter bar:** search (scenario / hash / date), verdict chips
  (All/Validated/Refuted/Inconclusive), tier filter, sort (date / verdict /
  scenario). Live "N of M" count.
- **Bundle table:** columns = verdict pill · scenario · tier · date · hash ·
  formats-available (small badges JSON/MD/HTML/TEX/PDF). Sortable headers.
  Keyboard navigable (↑/↓ to move, Enter to open). Stagger-in on load.
- **Proof viewer** (detail pane / drawer / route `/app/proofs/:tier/:scenario/
  :bundle`): a header (verdict banner, proof_id, created, substrate commit) +
  **format tabs** (JSON / MD / HTML / TEX / PDF):
  - **JSON** — collapsible syntax-highlighted tree.
  - **MD** — rendered markdown **with the embedded chart image** (the asset
    endpoint serves `assets/*.png`; render `![](assets/…)` against it).
  - **HTML** — iframe (served inline) + an "open in new tab" affordance.
  - **PDF** — iframe with the browser PDF viewer + download.
  - **TEX** — monospace source with copy button.
  - A structured "**Claim → Verdict → Evidence**" summary panel above the raw
    formats: statement, threshold (mono), observed value, the evidence pillars
    as a small table (pillar · statistic · value · 95% CI · p), pre-reg hashes.
- **Deep-linkable** (route or `#bundle=…`), shareable, reload-safe.

### 4.3 Scenarios (catalog)

- **Group toggle:** by *tier* or by *family*. Search.
- **Scenario cards** (or dense rows): name, tier badge, family badge, goal
  (truncated), method, a **claim preview** (statement + threshold when
  available; "needs args" note otherwise), and a **Run** button → opens Run
  with this scenario preselected. Expand for full goal + falsification
  consequence + explanation.
- 33 today; design for a few hundred (virtualize the list if needed).

### 4.4 Run (console)

- Scenario `<select>` (searchable combobox) → **claim panel** shows what it
  tests + the threshold + h0/h1.
- **Kwargs editor** — JSON editor (monospace, validates on the fly; show the
  scenario's required-args hint when `claim_available=false`).
- **Run button** — disabled while running; status states: idle → running
  (spinner + elapsed timer) → done (verdict pill) / error (loud).
- **Result** — on success, render the produced verdict + a link straight to the
  new bundle in Proofs; refresh the dashboard counts. On error, show the loud
  failure (Ophamin loud-fails by design — surface the real message, e.g.
  `missing 1 required positional argument: 'trajectory_path'`).
- **Run history** (this session) — a small list of recent runs with verdict +
  timestamp.
- **Guardrail:** runs can be heavy; confirm before firing, and make it obvious
  this is the one *write* surface (everything else is read-only).

### 4.5 Telemetry (metrics)

Turn the raw Prometheus exposition into a proper monitoring view:

- **Grouped gauge/stat cards** by category: HTTP (request totals, latency
  histogram → a small bar/area chart), Proofs (bundles by tier/scenario,
  verdict counts), Process (cpu, rss, threads, fds, page-faults — as
  gauges/sparklines), Scenarios (registered by tier/family).
- **Auto-refresh toggle** (off by default; 5s/15s/30s options) with the "live"
  pulse when on.
- Build-info + python-runtime-info + uptime as a small footer panel.
- Keep a "**raw exposition**" collapsible for power users.

### 4.6 Agents (optional, phase 2)

The 0.63.x local-LLM agentic layer (runs via `ophamin agent …` CLI today; no
HTTP endpoints yet — would need adding). Console view: pick an agent
(prereg-validator / confound-enumerator / scenario-gen / proof-brief / refuted-
triage / bundle-query), feed input, see output + the **signed LLMCallRecord**
audit entry. Defer until you add the HTTP routes; flagged here for IA
completeness.

---

## 5. Component inventory (shadcn/ui-based)

Build these as reusable components; most map to a shadcn primitive:

| component | based on | notes |
|---|---|---|
| `AppShell` | layout | rail + topbar + content; rail collapse animated |
| `NavRail` / `NavItem` | — | active = accent bar + tint; icon (lucide) + label |
| `TopBar` | — | brand · ⌘K search · health dot · version · theme toggle |
| `CommandPalette` | shadcn `command` | ⌘K: jump to scenario/bundle/screen |
| `StatTile` | shadcn `card` | count-up number + label + sparkline + tint |
| `VerdictBadge` | shadcn `badge` | validated/refuted/inconclusive semantic |
| `VerdictDonut` | Recharts `PieChart` | animated; clickable segments |
| `WheelsRing` | custom SVG | six-arc brand ring; also the loader/favicon |
| `FilterBar` | `input` + `toggle-group` | search + verdict chips + sort |
| `BundleTable` | shadcn `table` | sortable, keyboard-nav, stagger-in, drawer |
| `ProofViewer` | shadcn `tabs` | format tabs + claim/verdict/evidence panel |
| `ClaimPanel` | `card` | statement · threshold(mono) · h0/h1 |
| `EvidenceTable` | `table` | pillar · statistic · value · CI · p |
| `ScenarioCard` | `card` + `collapsible` | meta + claim preview + Run CTA |
| `RunConsole` | `form` + `textarea` | combobox + JSON editor + status + result |
| `MetricGauge` / `MetricGroup` | Recharts | gauges + sparklines + histogram |
| `Skeleton` | shadcn `skeleton` | shimmer for every async panel |
| `Toast` | shadcn `sonner` | run done/failed, copy confirmations |
| `ThemeToggle` | — | dark/light, persisted, prefers-color-scheme |
| `SixWheelsLoader` | custom SVG + CSS | the brand spinner |

State/data: a thin fetch layer (TanStack Query recommended — caching,
refetch, loading/error states for free) hitting the §6 endpoints. Routing:
React Router (or TanStack Router) so screens + the selected bundle are real
URLs.

---

## 6. The API / data contract (exact — bind to this)

Base URL: same origin as the console (FastAPI serves both). All JSON unless
noted. **These shapes are captured live from `ophamin http serve` v0.64.1.**

### GET `/health`
```json
{ "status": "ok" }
```

### GET `/version`
```json
{ "name": "ophamin-http-api", "title": "Ophamin HTTP REST API",
  "framework_version": "0.64.1" }
```

### GET `/scenarios`
```json
{
  "count": 33,
  "scenarios": [
    {
      "name": "anova-crosscheck",
      "family": "cross_framework",
      "tier": "measurement_machinery",
      "target": "scipy+statsmodels+pingouin-cross-framework",
      "goal": "Verify the one-way ANOVA implementations …",
      "method": "cross_framework_oracle",
      "corpus_name": "synthetic-anova-three-group",
      "falsification_consequence": "scipy / statsmodels / pingouin disagree …",
      "explanation": "One-way ANOVA generalises the two-sample t-test …"
    }
  ]
}
```
Tiers seen: `engineering`, `measurement_machinery`, `philosophical`,
`scientific`. Families include `cross_framework`, `conservation`, `memory`,
`prime`, `immune`, etc.

### GET `/scenarios/{name}/claim`
Claim is **nested under `.claim` and gated by `claim_available`** (some
scenarios need constructor args before a claim materializes):
```json
{
  "name": "anova-crosscheck",
  "metadata": { /* same shape as a /scenarios entry */ },
  "claim_available": true,
  "claim": {
    "statement": "Across 30 synthetic three-group datasets …",
    "operationalization": "Generate N three-group datasets …",
    "threshold": { "metric": "max_absolute_anova_difference",
                   "comparator": "<=", "value": 1e-09, "units": "F_or_p" },
    "h0": "At least one backend pair disagrees …",
    "h1": "All three backends compute identical F AND p …"
  }
}
```
When unavailable:
```json
{ "name": "sinew-conservation", "metadata": { … },
  "claim_available": false,
  "claim_unavailable_reason": "scenario constructor requires arguments; …" }
```

### GET `/proofs/bundles/tree`
```json
{
  "totals": { "tiers": 4, "scenarios": 18, "bundles": 33,
              "verdicts": { "validated": 21, "inconclusive": 2, "refuted": 10 } },
  "tiers": [
    { "tier": "engineering",
      "scenarios": [
        { "scenario": "throughput-ceiling",
          "bundles": [
            { "date": "2026-05-14", "verdict": "validated",
              "short_hash": "9989f42bc8f2",
              "path": "engineering/throughput-ceiling/2026-05-14_validated_9989f42bc8f2",
              "files": ["proof.json","proof.md","proof.html","proof.tex","proof.pdf"] }
          ] } ] }
  ]
}
```
`verdict ∈ {validated, refuted, inconclusive}`. `files` is the subset present
(not every bundle has a PDF). Accepts `?proofs_root=<path>` to browse a
non-default dir.

### GET `/proofs/bundles/file?tier=&scenario=&bundle=&filename=`
Serves one file from a bundle. `filename ∈ {proof.json, proof.md, proof.html,
proof.tex, proof.pdf}` **or** `assets/<name>.<png|jpg|jpeg|svg|webp|gif>` (the
chart assets). Served **inline** (renders in an iframe/`<img>`, not a
download). Path-traversal + non-image assets refused (400).
- JSON → `application/json`; MD → `text/markdown`; HTML → `text/html`;
  TEX → `text/x-tex`; PDF → `application/pdf`; PNG → `image/png`; etc.

**Proof JSON shape** (the `proof.json` body — the richest object you'll render):
```json
{
  "proof_id": "1bc36bbeb4b5c337…",      /* sha-256 content hash */
  "schema_version": "1.0",
  "identity": { "ophamin_version": "0.8.5",
                "ophamin_git_commit": "…", "created_at": "2026-05-17T16:40:40Z" },
  "claim": { "statement": "…", "operationalization": "…",
             "threshold": { "metric": "…", "comparator": "<", "value": 0.1,
                            "units": "dimensionless" },
             "h0": "…", "h1": "…" },
  "preregistration": { "config_hash": "…", "data_hash": "…",
                       "analysis_plan": "…", "sweep_grid": {},
                       "preregistered_at": "…" },
  "data": { "substrate_name": "kimera-swm", "substrate_git_commit": "…",
            "datasets": [ { "name": "…", "content_hash": "…",
                            "n_records": 500, "source": "…", "kind": "…" } ] },
  "evidence": [ { "pillar": "sinew_conservation",
                  "statistic_name": "walker_m4_conservation_ratio",
                  "statistic_value": 0.0873, "library": "…",
                  "ci_low": 0.0739, "ci_high": 0.1123, "p_value": null,
                  "effect_size": null } ],
  "verdict": { "outcome": "VALIDATED", "observed": 0.0873,
               "reasoning": "Conservation analysis (500 cycles, …)" }
}
```

### GET `/metrics`
Prometheus **text exposition** (not JSON). Parse `# TYPE name kind` then
`name{labels} value` lines. Families: `ophamin_http_requests_total`,
`ophamin_http_request_duration_seconds_bucket`, `ophamin_proof_bundles_total`,
`ophamin_proof_bundles_by_tier`, `ophamin_proof_bundles_by_scenario`,
`ophamin_proof_verdicts`, `ophamin_proof_latest_timestamp`,
`ophamin_proof_bundle_storage_bytes`, `ophamin_scenarios_registered`,
`ophamin_scenarios_registered_by_{tier,family}`, `ophamin_process_*` (cpu,
resident_memory, threads, open_fds, page_faults), `ophamin_build_info`,
`ophamin_python_runtime_info`, `ophamin_uptime_seconds`, `ophamin_health`,
`ophamin_disk_free_bytes`.

### POST `/scenarios/{name}/run`  (the one write surface)
Request: `{ "kwargs_json": "{}" }`  (a JSON *string* of constructor kwargs).
Response on success: a run result containing the produced proof
(`{ "proof": { …proof.json shape… }, … }`). On failure: HTTP 4xx/5xx with
`{ "detail": "…loud error message…", "framework_version": "…" }`. **Heavy** —
confirm before firing; show a spinner + elapsed time.

### POST `/proofs/index`   `{ "directory": "proofs" }` → reindex bundles.
### POST `/verify`   `{ "proof_json": "<string>", "sign_key_b64": "<b64>" }` → signature check.
### POST `/canonicalize`  `{ "value_json": "<string>", "sign_key_b64": "<b64>" }` → canonical form.

> `/verify` + `/canonicalize` + `/proofs/index` are power-user / tooling
> endpoints — surface them in Settings or a "Tools" drawer, not the main flow.

---

## 7. Build sequence (how to drive Claude to build it)

Work in claude.ai with artifacts, **screen by screen, mock-data-first**:

1. **Design system + shell.** "Build the Ophamin Console app shell: dark UniFi-
   style left rail + top bar + content, using these tokens [§2] and this motion
   spec [§3]. React + Tailwind + shadcn/ui + Framer Motion. Include the theme
   toggle and the SixWheelsLoader." Get the shell + tokens right first.
2. **Overview** with the §6.example data hardcoded — StatTiles (count-up),
   VerdictDonut, WheelsRing, recent-proofs table.
3. **Proofs** — FilterBar + BundleTable + ProofViewer, mock data from §6.
4. **Scenarios** — catalog cards + claim preview.
5. **Run** — console form + status states.
6. **Telemetry** — parse the sample `/metrics` text [§6] into gauges.
7. **Wire live data:** replace mock with TanStack Query against the §6
   endpoints. Run `ophamin http serve` locally; point the console's `fetch`
   base at it (same origin once deployed).
8. **Polish pass:** reduced-motion, keyboard nav, skeletons, empty/error
   states, light theme, ⌘K palette.
9. **Export + integrate:** `npm run build` (Vite) → static bundle → drop into
   `src/ophamin/http_api/static_app/` and mount at `/app` via FastAPI
   `StaticFiles` (mirror the existing `/ui` mount; keep `/ui` until parity).
   Add a versioned cache-buster + `no-store` on the HTML entry (the existing
   `/ui` handler already shows the pattern — copy it).

**Prompt tips for Claude:** paste this whole brief; ask for **one screen per
artifact** so each stays focused; insist on shadcn primitives + Framer Motion;
always ask for the loading/empty/error states; ask it to honor
`prefers-reduced-motion`. When wiring live data, paste the relevant §6 endpoint
block again so it binds to the exact shape (especially the **nested/gated claim
shape** and the **Prometheus text** parser — both are easy to get wrong).

---

## 8. Brand kit

- **Name:** Ophamin Console (product) / Ophamin (framework). Tagline:
  *"empirical observatory"* (lowercase, quiet).
- **Logo / motif:** the **six wheels** (Ophanim — wheels-within-wheels covered
  with eyes, Ezekiel 1:18). A six-segment radial / concentric-arc mark. Use as
  favicon, the `SixWheelsLoader`, and the dashboard health ring.
- **Accent:** teal/cyan `#2dd4bf` (instrument, scientific). Verdict greens/reds/
  ambers are semantic, not brand.
- **Voice:** precise, calm, understated. "33 bundles · 21 validated." No
  exclamation marks, no marketing gloss. The framework's own register is
  honest + measured — the console should match.
- **Don't:** copy UniFi's blue or logo; over-animate; pad like a landing page;
  hide the verdict state behind chrome.

---

## 9. Integration notes (for when you wire it into the repo)

- Same 12 endpoints; same origin → no CORS.
- Serve the built bundle from FastAPI `StaticFiles`, mounted at `/app/static`,
  with a `/app` HTML entry route. Copy the `/ui` handler's **cache-busting
  (`?v=<version>`) + `no-store` on the HTML** pattern (already in
  `server.py::get_ui_root`) so upgrading browsers never serve a stale bundle.
- Keep the provisional `/ui` GUI live during the transition; flip the `/`
  redirect from `/ui` to `/app` only once the console is at parity.
- The build step is **dev-time only**; runtime still just serves static files,
  preserving Ophamin's no-runtime-build property.
- Hardening: the server side is already pinned (68+ tests in `test_http_api.py`
  + `test_bundle_browser.py`). The new console is client-side; add a light
  smoke (Playwright optional) but the API contract is the stable boundary.

---

*Generated 2026-05-20 for Ophamin v0.64.1. Endpoint shapes captured live from
`ophamin http serve`. Keep this in sync if the REST surface changes.*
