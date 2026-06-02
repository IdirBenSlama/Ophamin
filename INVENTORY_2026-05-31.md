# Ophamin — Full Inventory (2026-05-31)

Ground-truth snapshot built from a 6-slice parallel audit, each slice reading the
code **and running cheap checks** (imports, targeted tests, CLI, a live server) so
"ready" and "broken" are measured, not guessed. Lens: the **wedge** — substrate-deep,
signed metrology that traces Kimera's *cognition* (a thought → primes/scars/deformation),
an artifact no LLM stack can produce.

Tags: **[ran]** = measured · **[read]** = inferred from code · absence-claims are provisional.

---

## Headline

The **apparatus is real and solid**; the **gaps are about where it points, and about
shipping**, not about whether it works.

- **[ran] Full suite: 2946 passed / 0 failed / 4 skipped / 0 errors (649s).** `ophamin verify` ok=94 / required-missing=0. `ophamin self-test` 10/10 VALIDATED.
- The signed proof bundle (the atom) is **bulletproof — tamper-detection verified live**.
- The **ontology muddiness is real, but at the NAME layer, not the code layer** — relabel, don't rebuild.
- The wedge is **closer than it looks**: the hard parts exist (signed atom + real mechanism reads + legibility), but mechanism-reading is the exception not the default, and the best output formats can't be shipped yet.

---

## 1. WHAT WE HAVE (real, tested components)

- **The atom — a signed, falsifiable proof bundle** (`measuring/proof/record.py`). Content-addressed `proof_id`; HMAC integrity seal + **real ed25519** author attestation (`cryptography`); JSON-Schema Draft-2020-12 validation; anti-p-hacking lock (`preregistered_at` must precede `created_at`); a `validate()` checklist that refuses un-falsifiable / un-attributed records; REFUTED is a valid proof. **[ran] 147 real proof bundles already on disk.**
- **~54–57 scenarios** registered (auto-registered, loud-fail on missing metadata): 33 scientific, 9 empirical-deep, 9 measurement-machinery (oracle cross-checks of Ophamin's *own* stats libs), 2 engineering, 1 philosophical.
- **18 audit pillars — all real subprocess wrappers, 0 stubs** [ran]: ruff, bandit, mypy, vulture, radon, pip-audit, interrogate, refurb, pylint, semgrep, prospector, deptry, fawltydeps, coverage, schemathesis, detect-secrets, osv-scanner, trivy. Every binary resolves in this venv.
- **7 interop exporters** (sarif, junit-xml, cyclonedx, in-toto/DSSE, ro-crate, openlineage, mlflow) + a CloudEvents 1.0 envelope; **4 reporting renderers** (html/markdown/latex/pdf) + a standards-conformance gate.
- **The observation ring** (`seeing/`): a Kimera subprocess adapter with a **59-field result catalog** across 18 substrate families, pluggable real corpora (Enron, Linux-kernel, FLORES-200, cyber, financial, The Well), field/schema discovery, and a static wired/orphan wiring probe.
- **Control surfaces**: `configuring/` (parses Kimera's env knobs; `config-apply` = the one mutating actuator, double-gated + backup + signed audit), `auditing/` runner, `reproducing/` (re-run N + drift band; static env-lock baked into every proof §7), `authoring/` (scenario specs with real citation grounding — arXiv/Crossref/DOI, refuses fabricated cites), `campaign.py` (6-phase orchestrator with FWER correction, signed).
- **Human-facing layer**: **37 HTTP routes**, a **33-screen console** (in-browser, honest "grounded-mock + live-overlay" with a loud "SAMPLE DATA — backend unreachable" banner), an **MCP server** (read/run/verify tools), and an **agentic layer** — local-LLM client (Ollama/LM-Studio/MLX, no cloud default, loud-fail), 10 advisory agents, HMAC-signed LLM-call audit trail, and **RAG-grounded `/chat`** over the real proof corpus (honest 503 when no LLM). *(LLMs here are legitimate — Ophamin layer, not the substrate.)*
- **Self-check tooling**: `verify.py` (96 dep + 17 binary + CLI checks), `self_test.py` (dogfoods 10 scenarios → signed proofs), `_stability.py` (API-tier decorators). **46 CLI subcommands**, ~161 test files. v0.115.2, Apache-2.0.

## 2. WHAT WE DON'T HAVE / WHAT'S MISSING

- **Mechanism-reading is the exception, not the default.** The substrate-deep path exists — the `entity` target reads real geoid positions, scar deformation, n_scars, and Echoform operator sequences *off the live Kimera object*, and `manifold_topology` reads the scar/geoid manifold (β₀/β₁/β₂) — but it's **1–2 scenarios**. Most scenarios read the **59-field cycle-boundary self-report** (what Kimera *says after* a cycle), not the live deformation / Walker traversal / prime activation *during* it. This is the outside-in frame mismatch, confirmed at the source.
- **The best wedge outputs can't be shipped.** in-toto/DSSE (supply-chain signing), RO-Crate (FAIR research bundle), OpenLineage (lineage) — exactly the "signed, legible proof for the world" formats — are **built and tested but Python-only**: no CLI / HTTP / MCP surface emits them.
- **No `ophamin reproduce` command.** Reproducibility is the thesis, but the dynamic "re-run N, show the drift band" (`reproducing/`) is library-only; only the *static* env-lock in proof §7 ships. No single "reproduce this signed proof" entry point.
- **No dedicated wedge-exhibit view.** The pieces (real mechanism reads + signed proofs + plain-language verdict glosses + chat-grounding) exist but are **not composed** into one screen/flow that takes a single proof and says "here is a thought traced to its scar — no LLM can show you this."
- **No PROV-O exporter**, yet the "Provenance viewer" integration promises one. **No live-stream eye** (everything is request/response). **No CI gate** runs the green suite automatically.

## 3. WHAT'S READY (measured)

- **[ran] Whole suite green**: 2946/2950 (the 4 are intentional skips). Per-slice: core 702 · observation 114 · control 305 · interop 554 · api/console 382 — all 0-fail.
- **[ran] The atom works end-to-end**: sign → verify True, wrong-key False, mutate a value → signature invalidates, round-trip signature-stable.
- **[ran] A real audit runs**: `ophamin audit … --pillars ruff,bandit,vulture` produced a signed finding record; all 18 pillar binaries present.
- **[ran] The server is live and honest**: 200 on /health, /version, /integrations, /agents, /chat, /scenarios; console fetches hit **only real routes** (zero dead-endpoint calls).
- **[ran] Integrations 4/6 configured** (Grafana, MLflow, Documentation, Code-scanning), persistent via `scripts/integrations_up.sh`.
- **[ran] `self-test` 10/10 VALIDATED**, `verify` green.

## 4. WHAT'S BROKEN (measured)

- **2 optional deps dead on Python 3.14**: `pyphi` 1.2.0 (`collections.Iterable` moved) — **disables the Φ/IIT scenarios** `run-all`'s measuring phase would exercise — and `causalpy` 0.8.1 (arviz API moved). Both non-fatal (optional, already flagged in pyproject), but pyphi's hole is real.
- **One remaining UI fabrication**: `console/app/proofs.jsx` `triageFor()` / `confoundsFor()` (L786–841) render **hardcoded mock agent text unconditionally** — no live overlay, no call to the real `/agents` layer. The de-fab campaign cleaned audit/run/chat but missed this. (The real agents exist and are signed; the wire from the proof screen to them is absent.)
- **`reproducing.reproduce()` has no self-contained smoke path** — needs a live substrate to invoke at all.
- **Minor**: a leaked file handle (`seeing/discovery/kimera_inventory.py:322`, ResourceWarning); `verify.py:206` dead branch (`"info" if … else "info"`).
- No broken tests, no broken imports, no 500-ing routes, no dead pillars.

## 5. WHAT'S ABSURD (the naming/ontology mess — real, at the NAME layer)

- **The four "observation" gerunds only one of which observes Kimera.** `seeing` = observe Kimera; `inspecting` = a *composer* that orchestrates the other wheels (not an observer); `instrumenting` = resource *cost* (psutil); `observability` = Ophamin's *own* OTel telemetry. Distinct in code, **misleading in name** — this is the muddiness you felt. Fix by relabeling, not merging.
- **"pillar" names two unrelated registries**: 11 *statistical-test* pillars (`measuring.pillars`) vs 18 *static-analysis* pillars (`auditing.pillars`). `ophamin pillar list` shows only the statistical one — an operator looking for audit tools gets the wrong list with no signpost.
- **Two word-collisions**: "telemetry" = scrape-Kimera's-metrics (`seeing/telemetry`) vs emit-Ophamin's-metrics (`observability`); "instrument" = psutil-cost (`instrumenting`) vs OTel-spans (`observability`). Same word, opposite subsystems.
- **3 exporters + CloudEvents are orphans**: in-toto, ro-crate, openlineage are library-only (no CLI/consumer); CloudEvents `wrap()` has **no caller and no transport** — a format with neither producer nor consumer. Docstring advertises 7 exporters; only 4 ship.
- **`drift/` vs `drift_detection/`** — genuinely different (cross-commit proof-drift vs online stream-drift) but the names invite confusion. **`managing/`** ships only read-only status despite a docstring promising "lifecycle." **Stale**: Py3.14 in use but classifiers say 3.12/3.13; `verify.py` checks only 19 of 46 subcommands.

## 6. WHAT THIS MEANS FOR THE WEDGE (the first move)

The inventory says the **hard parts already exist**: a bulletproof signed atom, *real* mechanism reads (geoid positions, scars, Echoform ops via the `entity` target; manifold topology), plain-language legibility, and RAG that can cite a real proof's reasoning. Building the **first wedge exhibit** is therefore mostly *composition + shipping*, not new invention:

1. **Make mechanism-reading the spine of one scenario** — `memory_as_deformation` via the `entity` target, reading the actual scar, not concept-name Jaccard.
2. **Ship the proof** — wire `in-toto/DSSE` + `ro-crate` to the `export` CLI/HTTP (they're built, just unshippable).
3. **Compose the exhibit** — one screen/flow: a single signed proof that traces a thought to its scar, in plain words, with the kicker "no LLM stack can produce this artifact."

Two real blockers to clear first: **pyphi** (if the exhibit touches Φ) and the **`proofs.jsx` mock-agent fake** (so the exhibit screen is 100% honest).

---

*Snapshot only — a point-in-time measured audit, not a standing claim. Re-run the 6-slice audit to refresh.*
