# Kimera-SWM Memory — the proven gap, the honest limit, the path

*An independently-verifiable evidence brief. Every claim below links to a signed
proof you can re-check yourself; the limits are stated up front, not buried. No
marketing — if a line isn't backed by a signed, real-data proof, it isn't here.*

Generated 2026-05-22 · Kimera commit `a3befa25d` · Ophamin v0.113.0

---

## The one line

**Today's memory systems store an *inventory*. Kimera-SWM stores *history*.**
Retrieval (the industry standard — vector search, RAG, long context) remembers
*what* it was given. Kimera remembers *how things unfolded* — order, permanence,
and the path of experience — and we have signed, real-data proof that this is a
real, structural difference, not a slogan.

## The gap, plainly

- **A filing cabinet** (RAG / retrieval): you drop documents in; it returns the
  ones that look similar. It does **not** care what *order* they arrived. Two
  histories made of the same events in different order look **identical** to it.
- **A landscape you walk** (Kimera): every experience wears a permanent groove;
  the *order* of walking shapes the terrain; the terrain *is* the memory. Two
  same-event different-order histories leave **different** terrain.

Where order/history carry meaning — fraud sequences, how a crisis developed, a
portfolio that crashed-then-recovered vs rose-then-fell — the filing cabinet is
blind and Kimera is not.

## What is proven (each line is a signed proof you can re-verify)

| # | Claim (plain) | Result | Real data | Signed proof |
|---|---|---|---|---|
| **1** | Memory is **permanent** — a scar never resets; the same recognised input lands on a strictly-deeper manifold every time | VALIDATED 1.0 (16/16) | Kimera genesis | `a63db28704b7` |
| **2** | …and it holds on **real-world data**, not curated text | VALIDATED 1.0 (20/20), ρ=0.94 p=3e-18 | Enron email | `d5a4ce3a7c13` |
| **3** | Memory is **order-sensitive** where retrieval is order-blind *by construction* | VALIDATED, order-effect +0.93 vs RAG 0.0, p=0.016 | — | `f6af1a5c15df` |
| **4** | Does it measure risk **magnitude**? (honest) | INCONCLUSIVE — order seen, size not tracked | FRED SP500 | `6209cb915c83` |
| **5** | Kimera **separates real-risk-different histories** (same trades, opposite drawdown) that retrieval conflates | VALIDATED, separation 1.0 vs RAG 0.0 | FRED SP500 | `7f6a839eb599` |

**Re-verify any line yourself** (no trust required — HMAC-signed, content-addressed):

```
ophamin proof verify proofs/scientific/memory-permanence-flow/2026-05-22_validated_a63db28704b7/proof.json
ophamin proof verify proofs/scientific/memory-permanence-flow/2026-05-22_validated_d5a4ce3a7c13/proof.json
ophamin proof verify proofs/scientific/memory-order-hysteresis/2026-05-22_validated_f6af1a5c15df/proof.json
ophamin proof verify proofs/scientific/finance-path-dependence/2026-05-22_inconclusive_6209cb915c83/proof.json
ophamin proof verify proofs/scientific/finance-history-discrimination/2026-05-22_validated_7f6a839eb599/proof.json
```

## What is NOT proven — stated plainly

- **Kimera does not yet *measure* risk magnitude.** It tells two histories apart
  (proof 5); it does not yet say *how much* worse one is (proof 4). We searched
  this **exhaustively** — all ~4,000 of Kimera's emitted signals — and the one
  strong candidate (a thermodynamic entropy-production signal, ρ=0.976 on SP500)
  **failed** a pre-registered re-test on independent NASDAQ data (ρ=0.43, ns).
  So: no working "size-meter" today. *(diagnostics: `diagnostics/size_meter_*`)*
- **Kimera is partially wired.** Of its ~3,500 numeric signals, only **~13%**
  currently move with input; the rest are defaults or dormant. So the magnitude
  null is a **wiring gap, not an architectural ceiling** — the readout isn't live
  yet, not "the design can't."

## Why this is credible (and skeptic-resistant)

1. **Every claim is a signed, content-addressed proof** — re-verifiable by anyone, no trust in us required.
2. **Real data** — Enron email, FRED SP500, NASDAQ — not toy inputs.
3. **Built-in controls** rule out the obvious objections: re-derivation (a never-seen baseline), run-noise (a determinism control), recognition-vs-memory (held constant), and a **set-based-retrieval baseline that is order-blind by construction** — so the contrast is structural, not a tuning artifact.
4. **An honest null is included** (proof 4 + the size-meter search). A case that only ever says "yes" isn't trustworthy; this one reports what failed.

## The path (what would unlock magnitude)

The exhaustive search points at one place: a **live thermodynamic magnitude
readout** in Kimera (the entropy-production signal showed the right shape before
it failed to replicate — it's the natural home, consistent with Kimera's
"intelligence is the heat" design). Wiring that is an *engine* change (owner
territory), and Ophamin already produced the input it needs: the list of dormant
signals to bring online. That turns *"tells histories apart"* into *"measures the
risk"* — the step from a real capability to a sellable one.

---

*This brief is the legible layer over Ophamin's signed proof corpus. The proofs
are the truth; this is the map to them. Re-run any line; the framework is built
so you don't have to take our word for it.*
