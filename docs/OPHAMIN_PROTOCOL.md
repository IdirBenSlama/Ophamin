# The Ophamin Protocol

> **Status:** draft v0.1 — the constitution. Everything Ophamin builds must
> cite a layer of this document. Companion to
> [`OPHAMIN_CONSOLE_ARCHITECTURE.md`](OPHAMIN_CONSOLE_ARCHITECTURE.md)
> (which governs the GUI) and `SCHEMAS.md` (which defines the record bytes).

---

## For the person who holds the vision (plain language)

Ophamin turns Kimera's behavior into **signed receipts you can trust and
show anyone.** Every receipt says *what was claimed*, proves it was
*measured against recognized standards*, and can be *re-run* to check.
This document is the rulebook that keeps every receipt honest — whether
it's one measurement, a whole flow, a campaign, or a shippable business.

Kimera is the engine. Ophamin is the stack on top that makes the engine
**trustworthy enough to build a business on.** That trust is manufactured
by this protocol.

---

## The spine (one sentence)

> A claim about the substrate counts as evidence only when it is
> **pre-registered, measured against a recognized standard, signed,
> reproducible, and provenance-tracked.** Otherwise it does not count.

---

## The 8 invariant rules (non-negotiable)

1. **Pre-register before measure.** The falsifiable claim is fixed before
   the run; no post-hoc claiming. *(Ref: OSF Registered Reports.)*
2. **No claim without a falsifiable threshold.** It must be possible to fail.
3. **Standard-backed + cross-checked.** Every statistic is computed by a
   recognized library and, where possible, confirmed by ≥2 independent
   implementations. *(Ref: O·F·A·M·I·N pillars + the `cross_framework` tier.)*
4. **Deterministic canonicalization.** The record serializes to identical
   bytes everywhere. *(Ref: `SCHEMAS.md` R1–R11.)*
5. **Signed + tamper-evident.** HMAC/ed25519 over the canonical body.
6. **Reproducible.** Exact command + locked environment + content-hashed
   datasets travel with the proof.
7. **Provenance.** Substrate commit, corpus, framework version, lineage.
   *(Ref: W3C PROV-O + OpenLineage run model.)*
8. **Honest verdict.** VALIDATED / REFUTED / INCONCLUSIVE — refutations are
   first-class evidence, never failures. *(Ref: OSF "published regardless
   of outcome".)*

---

## The 8 layers

### L0 · Observation contract (Kimera → Ophamin)
A controlled, versioned **semantic-convention vocabulary** for substrate
signals — the "alien telemetry standard". Faceted:

- **neuro:** `phi`, `halt_mode ∈ {M1,M2,M3,M4}`, `kccl_phase`, `sleep_event`
- **physics:** `delta_s` (ΔS≥0), `free_energy`, `temperature_beta`,
  `kuramoto_order`, `spde_pressure.{resonance,contradiction,void,drift}`
- **math:** `betti_{0,1,2}`, `prime_emission`, `geodesic_distance`
- **cs:** `prime_packet`, `partition`, `encoder_snapshot_id`, `gwf_verdict`

Every signal has a fixed **name + unit + facet** so observations are
comparable across runs, commits, and nodes. *(Ref: OpenTelemetry semantic
conventions; BIDS controlled vocabulary.)* **This + L5 `Flow` are
Ophamin's original contribution — no prior art monitors an emergent
cybernetic-physics intelligence this way.**

### L1 · Claim contract
The falsifiable five-tuple (statement / operationalization / threshold /
H0 / H1), tagged **`confirmatory | exploratory`** and **faceted**, frozen
before the run. *(Ref: OSF pre-registration; HELM scenario × dimension.)*

### L2 · Measurement contract
Standard-backed + cross-checked across ≥2 independent libraries; **raw
trace released** for inspection. For `Flow` claims: a **full-session
causal-chain trace** of the Takwin cycle, with the claimed invariant
evaluated **as a temporal-logic property along the trajectory**.
*(Ref: HELM transparency; AI-agent observability full-session tracing;
digital-twin TLA correctness properties.)*

### L3 · Proof envelope
A signed attestation: **`subject`** (`kimera-swm@commit`) +
**`predicate`** (claim + evidence + verdict, typed by scope) +
**`signature`**. Native Ophamin envelope is the core; an **in-toto / DSSE
export** is provided for ecosystem interop (Sigstore, SLSA verifiers, OCI).
**Core + facets** for extensibility. *(Ref: in-toto/DSSE, Sigstore;
OpenLineage facets.)*

### L4 · Provenance graph
PROV-O entities/activities/agents + OpenLineage run model linking
proof → corpus → substrate-commit → framework version.

### L5 · Scope hierarchy
Escalating signed predicates:

| Scope | What is signed |
|---|---|
| **Point** | one measurement |
| **Flow** | a temporal-logic invariant held across a whole trajectory |
| **Campaign** | a family of claims under one multiplicity-correction regime |
| **Vertical** | corpus-card + campaign + proofs + deploy-manifest = a business unit's *license to operate* |

### L6 · Packaging
On-disk **BIDS-style** tree (`proofs/<tier>/<scenario>/<bundle>/`) +
**Croissant** cards for corpora + **RO-Crate** for verticals. Self-
describing, FAIR, portable. *(Ref: BIDS, MLCommons Croissant, RO-Crate.)*

### L7 · Verification + policy
Verify signature + provenance + freshness; **deploy-time policy gate**:
*a vertical may ship only if its campaign proof is VALIDATED,
cross-confirmed, signed, and fresh.* *(Ref: SLSA policy enforcement.)*

---

## The cohesion: one grid

Every artifact Ophamin produces is **a signed, faceted, provenance-tracked
predicate at one of four scopes, observed through shared semantic
conventions, packaged as a portable crate, and policy-gated.**

```
            FACET →   neuro   physics   math   novel-cs   engineering
SCOPE ↓
  Point                ·         ·        ·        ·           ·
  Flow                 ·         ·        ·        ·           ·
  Campaign             ·         ·        ·        ·           ·
  Vertical             ·         ·        ·        ·           ·
```

The build cockpit = the `engineering` facet. The proving ground =
`confirmatory` Point/Campaign proofs. The four scientific lenses = the
facets. The flow validator = the `Flow` scope. The vertical platform =
the `Vertical` scope. **One protocol, every face.**

---

## Design decisions (made; not to be re-litigated without cause)

- **D1 — Native envelope + in-toto export (not in-toto outright).** Keep
  the working, tested Ophamin signed-record format as the core; map to
  in-toto/DSSE on export for ecosystem interop. Rationale: don't rip out a
  proven, test-pinned foundation; gain interop additively + reversibly.
- **D2 — Facets, not subtypes.** Extensibility via OpenLineage-style typed
  facets on a stable core, not a proliferation of record subclasses.
- **D3 — Flow = temporal-logic invariant over a trajectory**, not an
  output assertion. Emergence means you check *what must hold*, not *what
  it produces*.

---

## Inspired by (the standards this protocol stands on)

| Borrowed principle | Source |
|---|---|
| Signed attestation envelope; deploy-time policy; keyless signing | in-toto · SLSA · Sigstore |
| Pre-registration; confirmatory/exploratory; publish-regardless | OSF Registered Reports |
| Holistic scenario × dimension eval; full raw transparency | Stanford HELM |
| Stable core + extensible facets; run model | OpenLineage |
| Machine-readable dataset cards | MLCommons Croissant |
| Self-describing FAIR research crate (JSON-LD) | RO-Crate |
| Entities / activities / agents provenance | W3C PROV-O |
| Filesystem data-structure standard + controlled vocab | BIDS |
| Shared signal vocabulary; cross-signal | OpenTelemetry semantic conventions |
| Full-session causal-chain tracing; observe→evaluate | AI-agent observability |
| Temporal-logic correctness properties; TEVV; real-time mirror | Digital-twin verification (TLA) |

---

*This is a living constitution. It evolves by explicit amendment, with the
rationale recorded under "Design decisions".*
