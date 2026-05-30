# Ophamin — Charter

> **The north star.** What Ophamin is for, the whole scope, the grounded state, and the order of building.
> Vision is owner-authored; current-state is measured (six-probe audit, 2026-05-30). Where the two disagree, the vision is the target and the measurement is the starting line.
>
> **Status:** DRAFT v1 — awaiting owner correction. Add what's missing in §9 before this lands.

---

## 0. What Ophamin is

Ophamin is the **observatory and operational plane that makes Kimera-SWM legible, measurable, and operable — for the world.**

It exists because Kimera is **first-of-its-kind**: the measurements needed to see it *do not exist yet*. Ophamin's deepest job is not to *apply* measurement — it is to **invent the metrology that does not exist**, for an intelligence that has never existed before.

It is **dependent and independent** at once: born to see Kimera (its telos), built as a protocol-general platform (its form). The dependence gives it purpose; the independence makes it a platform.

**It is NOT:** a generic statistics harness with substrate labels · a pass/fail scoreboard · a command channel into cognition · a single-substrate test rig.

---

## 1. The three purposes (owner-stated vision)

1. **Legibility — for the world.** The owner cannot explain Kimera in words. Ophamin *is* the explanation, rendered in measurements: the thing that lets an outsider, a skeptic, eventually a customer, see what Kimera is.
2. **Metrology — invent the missing instruments.** New measurement tools for a new kind of substrate — prime-space, manifold-geometry, scar-topology, heat, the ordered walk.
3. **Platform — the AIP-style horizontal plane.** Control, management, monitoring, security across the topology. Vertical real-world businesses deploy on it; Kimera is the engine underneath. (The Foundry pattern, over a *cognition*-mesh.)

These are ordered by dependency: **3 stands on 2 stands on 1's data.** You cannot govern, secure, or sell what you cannot yet measure.

---

## 2. The topology it spans — Node → Archipel → Indra's Net

| Tier | What it is |
|---|---|
| **Node** | one full substrate (solo-mode fully valid) |
| **Archipel** | a local mesh of Nodes |
| **Indra's Net** | global pooled experience across all Nodes |

*Intelligence is constant across vessels; only experience scales with connectivity.* Ophamin is the plane across **all three tiers and all scales** (local · remote · network).

**The hard constraint (Kimera's Constitution):** there is **no command channel** — nothing imposes onto a substrate; the wire carries **partitions**, not raw signals. So "Archipel / Indra's-Net control" means **governing connectivity and partition-flow** — membership, routing, pooled-experience observation, admission — and *never* commanding a Node's cognition.

**The three control surfaces.** Ophamin's reach splits in three, by Kimera's own *heat-vs-medium* distinction (the substrate is the heat; hardware is boilerplate):

- **Cognition (the heat)** — *observe only*. Feed stimuli, read emissions, never command.
- **Wire (the partition / PrimePacket)** — *govern*. Route, admit, reconcile across the mesh.
- **Machinery (the medium — hardware/compute)** — *control*. Provision, allocate, scale, start/stop. This is the one **imperative** surface Ophamin gets to drive, precisely because the machinery is boilerplate and not the substrate.

Only the bottom surface is commanded; the top is sacrosanct.

---

## 3. The keystone — the PrimePacket (partition)

Everything the platform does is an operation on **one object**: the partition / PrimePacket =
**primes + Echoform operator sequence + Cronos timestamp + GWF signature** (the re-performable unit of the wire).

- Network control = **routing** PrimePackets.
- Monitoring = **watching** them flow.
- Security = **authenticating** them (GWF sig + PKI).
- Pooling (Indra's Net) = **reconciling** them to convergence.
- Metrology = reading **what a PrimePacket means** about the substrate.
- "All scales" = **how far** the PrimePacket travels.

Build the PrimePacket as a first-class observed/verified/routed/secured object **once, at the Node**, and extend it outward. That is the spine of the entire platform.

---

## 4. The operational planes × scales

| Plane | The PrimePacket operation | Node | local → remote → network (mesh) |
|---|---|---|---|
| **Monitor / Observe** | watch flow + telemetry | partial | absent |
| **Network control** | route / membership / dead-letter | n/a | scaffold (unplugged) |
| **Security** | authenticity · admission · identity | asymmetric | PKI scaffold; no authz |
| **Reconcile / Pool** | CRDT convergence of pooled experience | n/a | scaffold (unplugged) |
| **Metrology** | what the packet *means* | ~10% native | absent |
| **Legibility** | explain it to a human | hand-authored | absent |

**Beneath the packet planes sits the machinery (medium) layer** — the hardware/compute a Node runs on (today: simulated quantum + analytical thermo + THRML→TSU bridge; intended: real quantum / Extropic-TSU). Ophamin *senses* it (`instrumenting/`: walltime/CPU/RSS/GPU/threads) but cannot yet *act* on it. **Machinery control** is the actuator complement: provision / allocate / scale / start-stop the compute a Node or Archipel runs on — the imperative-control surface, and the "operate the engine" half the platform audit found absent (only `config-apply` mutates today).

---

## 5. Grounded current state (measured, 2026-05-30 — six-probe audit)

- **Metrology:** ~80% borrowed statistics / ~10–15% invented. The **lossy JSON emission boundary** (`kimera_adapter.jsonable`) flattens native objects before any instrument sees them — it forecloses native metrology *by construction*. The one genuinely-native instrument: `prime_factorization.py` (order-aware GCD recovery). Scenarios argue "order matters" in prose but measure with **order-discarding Jaccard**.
- **Legibility:** the **trust problem is solved** — signed, pre-registered, content-addressed, re-verifiable, failures kept. But the *explanation* is **two hand-authored files** (`KIMERA_MEMORY_CASE.md`, `Ophamin_Proof_Brief.html`), not a machine output. The 147-proof corpus renders as jargon. The owner is still the interpreter — the premise isn't met yet.
- **Platform:** an **observatory served over HTTP/MCP**, not a control plane. Two real footholds (`run_scenario` drive-to-measure, `config-apply` CLI-only). **No auth, no tenancy, no identity, no lifecycle.**
- **Topology:** **both Kimera and Ophamin are single-Node in practice today.** Kimera's mesh tier (ArchipelPeerRouter, 7 transports, full CRDT reconciliation, ed25519 PKI) is **scaffold-built + ~500 hardening tests but UNPLUGGED** — nothing instantiates it in the runtime; partitions are built and consumed *locally* (the body hears itself via `PartitionEcho`); the wire is "wired by the owner next," and even the wire-format omits the Echoform sequence. Ophamin has **no partition / multi-Node concept** at all.

---

## 6. The root cause under all of it

**One pipe blocks all three pillars: the Ophamin↔Kimera interface is a one-way, lossy JSON telemetry stream.** Native metrology can't be invented (objects destroyed at the boundary); explanation can't be machine-generated (only scalars arrive); the platform can't see partitions. **Fix the contract → all three pillars unlock.** That is the floor.

---

## 7. The build sequence (foundation-first)

0. **[DONE 2026-05-30]** Land the at-risk uncommitted work + push the security fix.
1. **Single-Node PrimePacket as a first-class observed object** — an order-keeping trajectory metric on *existing* emissions (the ordered chain is already there; scenarios just discard it). Pure Ophamin-side, no engine change. Tests the inside-out thesis cheaply.
2. **Widen the emission contract** — Kimera emits the **Echoform operator sequence + per-step E_p energies + geoid coordinate trajectory + scar positions**. *Engine-side; owner territory; spec-first, never imposed.* Unlocks curvature, native magnitude (the size-meter reborn), scar-topology.
3. **The partition, observed** — a partition record alongside `CycleResult`; first where it already lives (local `PartitionEcho`), then onto the wire as the seam is plugged.
4. **The mesh observatory — born with the mesh.** Multi-Node abstraction + partition emit→transmit→re-perform verification + pooled-experience convergence. Ophamin's observation is what makes wiring the connective tissue *safe and legible*; it unblocks Indra's Net rather than waiting on it.
5. **The operational planes, outward** — monitor → secure (admission/identity — the platform's biggest hole) → route → reconcile, across local → remote → network.
6. **Legibility, throughout** — a per-proof "what this means about Kimera, in plain terms" so the corpus explains *itself* and the owner leaves the loop.

---

## 8. Governance & boundaries

- **Vision = owner.** Meaning wins. Primitive names and purpose are owner-only.
- **Execution = steward** (the agent), with full authority over Ophamin.
- **Kimera's engine is spec-first** — anything requiring the substrate to emit/behave differently is proposed, never imposed.
- **Everything auditable** — signed, committed, journaled. The owner can verify any move without reading code.
- **Irreversible / public actions** (releases, deletions, anything outward beyond normal pushes) are flagged *before*.
- **No LLM in any measurement/proof decision** (the agentic layer is advisory tooling, every call signed; never overrides a verdict, never in the substrate path). *Open owner question: whether the post-2026-05-25 "no LLM even offline" stance extends from the substrate to the instrument.*

---

## 9. Open scope — owner to fill ("etc etc")

_Placeholders for scope the owner has named or will name — to be expanded:_

- Network control surfaces beyond observation (routing policy, membership governance).
- Monitoring at mesh scale (fleet telemetry, cross-Node dashboards).
- Security: runtime admission / identity / authz plane (the platform's biggest gap).
- **Machinery control** — operate the medium/compute layer (hardware backends, process lifecycle, resource allocation). *Reading to confirm: the engine's own compute (a) vs real-world industrial machinery as a vertical (b), or both.*
- Vertical-business deployment model (how a vertical sits on the horizontal plane).
- _…_

---

*Charter v1, drafted by the steward, grounded in the 2026-05-30 six-probe audit. Awaiting owner correction before it lands in history.*
