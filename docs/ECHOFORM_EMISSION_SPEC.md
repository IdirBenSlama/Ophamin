# Spec — Native Emission Contract (the "faithful partition")

> **Status:** PROPOSAL — awaiting owner review. **Engine-side (Kimera).** Spec-first; nothing implemented.
> **Author:** Ophamin steward, grounded in the 2026-05-30 six-probe audit.
> **Decision owner:** repository owner — this touches Kimera's `OrchestratorResult` / Takwin emission / `PrimePacket.to_wire`, which is **engine territory**. Ophamin proposes; the owner decides.
> **Charter:** closes the root cause in `OPHAMIN_CHARTER.md` §6 and unblocks §7 steps 2–4.

---

## Why

Ophamin reads Kimera across a JSON boundary (`seeing/substrate/kimera_adapter.py::jsonable`). Today that boundary carries the `prime_chain` + scalar telemetry, but **not** the native objects that make a partition *faithful* or the substrate *legible at the physics level*. Measured gaps (six-probe audit):

- **Echoform operator sequence** — the *grammar*. Kimera's own `archipel_architecture.md` calls this "the open extension": `PrimePacket` carries the prime chain, not the operator sequence. Per the Constitution a faithful partition = **primes + Echoform operator sequence + Cronos timestamp + GWF signature** — so today's emission is **not yet re-performable**.
- **Per-step prime energies** — `E_p = ln p` as the substrate weighted them. Ophamin currently *recomputes* `ln p` (a proxy) because the substrate doesn't emit its own step energies.
- **Geoid coordinate trajectory** — the Walker's path on the S⁴ manifold. Ophamin has **no real geoid coordinates**; the one geodesic call is fed Ophamin's own synthetic 5-D points.
- **Scar positions** — Ophamin reads only a scar *count*; "scar = permanent topological deformation" has no positional readout.

## Principle — additive + loud (Constitution §5)

Every field below is **additive** (no existing field changes). **Absence is a recorded gap (`None`), never a fabricated value.** Ophamin treats a missing native field as "not emitted," never as zero — no fallback, no synthetic substitute.

## Proposed emission (per cycle; bundled per partition)

| Field (proposed name) | Type / shape | Meaning | Ophamin reader (unlocks) |
|---|---|---|---|
| `echoform_sequence` | ordered `list[{op, delta_s, targets}]` | the ΔS≥0 grammar applied this cycle, in order | faithful partition · re-performability check |
| `prime_chain_energies` | `list[float]`, parallel to `prime_chain` | the `E_p` the substrate assigned per step | energy-walk metric on the substrate's own energies (not Ophamin's recompute) |
| `geoid_trajectory` | ordered `list[list[float]]` (live geoid dim) | the Walker's positions on the manifold this cycle | curvature · geodesic length · real path (replaces synthetic points) |
| `scar_positions` | `list[{coord, depth}]` for scars deposited this cycle | where deformation landed + how deep | scar-topology metrology (replaces the count) |

*(Field names are proposals — the owner is naming authority.)*

## What each unlocks (charter §7)

- **`echoform_sequence`** → the faithful, re-performable partition → partition observation (#3) + mesh emit→transmit→re-perform verification (#4). Closes the wire-format gap the architecture doc flagged, so it serves both the single-Node *and* the mesh.
- **`prime_chain_energies`** → the energy-walk trajectory metric (already shipped Ophamin-side, `observables.energy_path_divergence`) reads the substrate's real energies instead of a `ln p` proxy.
- **`geoid_trajectory`** → manifold **curvature** + real geodesic path; the thermodynamic magnitude readout (the "size-meter") reborn as native metrology, judged path-aware.
- **`scar_positions`** → **scar-topology** (deposition map, adjacency, depth field) — the deformation *is* the memory.

## Boundaries (the line I hold)

- This is **engine territory.** Ophamin's steward proposes the contract; the owner decides and implements (or directs/authorizes a spec'd PR). Nothing here is imposed on the substrate.
- The Ophamin-side reader changes (new `observables` + adapter capture) are mine to build once the emission lands. Until then they **degrade to honest gaps** — every dependent metric returns `None`, never a fabricated reading.

## Decision points for the owner

1. **Approve** the four fields (names + shapes), or amend.
2. **Sequence** — which lands first? *Recommendation:* `echoform_sequence` — it's the faithful-partition keystone and the already-flagged open extension; it unblocks the most (#3 + #4).
3. **Implementation path** — owner implements / directs, **or** authorizes a spec'd Ophamin-side PR against Kimera's emission layer for owner review.

---

*Proposal by the Ophamin steward. The substrate's emission is the owner's; this is a request, not a change.*
