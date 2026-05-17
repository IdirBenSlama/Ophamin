# Ophamin roadmap

> **Where this lives:** the load-bearing record of intent is in
> [`docs/ELEVATION_ROADMAP_2026_05_16.md`](docs/ELEVATION_ROADMAP_2026_05_16.md)
> and [RFC 0002](docs/rfc/0002-sota-elevation-stages-5-and-6.md).
> This file is the **year-focused readable summary** for downstream
> consumers; revisit at every major release.

> **Last updated:** 2026-05-17, against `v0.10.x`. Refresh per
> [GOVERNANCE.md § Amending this document](https://github.com/IdirBenSlama/Ophamin/blob/main/GOVERNANCE.md).

## What Ophamin is (in one paragraph)

Ophamin is an empirical observatory wrapped around a substrate under
test — six wheels (seeing, measuring, comparing, instrumenting,
auditing, reporting), pre-registered scenarios, signed proofs,
falsifiable claims. Built for [Kimera-SWM](https://github.com/IdirBenSlama/Kimera-SWM-System) as
its first substrate; independent of it (any system implementing the
`SubstrateUnderTest` protocol works). Apache-2.0 licensed.

## The campaign

The project is executing a four-stage elevation arc. Stages 1–4 are
done; Stages 5–6 are landing in `0.9.x` + `0.10.x`.

| Stage | Theme | Status | Releases |
|---|---|---|---|
| **1** Solid | Internal hardening (S1–S6: mypy strict, property tests, benches, coverage, type-safety, observability) | ✅ done | 0.5.x – 0.7.x |
| **2** Legit | External legitimacy (L1–L6: docs, badges, Apache-2.0, RFC process, schema versioning) | ✅ done | 0.7.x – 0.8.x |
| **3** Hardened | Stage-3 follow-ups (per-OS lockfile, macOS CI, bench advisory gate, coverage ratchet) | ✅ done | 0.8.3 |
| **4** Public | Repo public + GitHub Pages live (site at <https://idirbenslama.github.io/Ophamin/>) | ✅ done | 0.8.4 – 0.8.5 |
| **5** Scientific SOTA | Cross-framework validation, FWER correction, open data, research-grade reproducibility, peer review | 🟡 in flight | 0.9.x – ? |
| **6** Engineering SOTA | PyPI, SLSA, API stability, cross-language read APIs, community infra | 🟡 in flight | 0.9.x – 0.10.x |

## Where we are: `0.10.x` (May 2026)

The two prerequisites for `1.0.0` per [RFC 0002 §3.2 Phase E8](docs/rfc/0002-sota-elevation-stages-5-and-6.md)
are both met:

- **Wire-format stability contract** (`CampaignRecord/1.0 → 2.0` —
  Phase E2, shipped 0.9.0)
- **Python-API stability contract** (28 `@Stable`-tagged symbols + a
  regression suite + the `ophamin api-stability` CLI — Phase E8,
  shipped 0.10.0)

What separates `0.10.x` from `1.0.0` is **external validation under
real upgrade pressure**:

- **E4** — a third party rebuilds a tagged release from source +
  lockfile and verifies byte-equal SBOM + signed-record output;
- **E5** — a methods paper passes JOSS / SoftwareX / JMLR-OSS review.

`1.0.0` will ship when at least one of those external passes exists.
Until then, the framework lives at `0.10.x` with the contract
"claimable for the first time" but not yet "tested by a full
deprecation cycle in the wild."

## What's queued for next: a tightened twelve-month view

The roadmap below is a **best-effort sequencing**, not a contract.
Phase order can shift; the RFC governs what's load-bearing.

### Within 0.10.x (June–July 2026)

- **E10** Community infrastructure — `GOVERNANCE.md` + this `ROADMAP.md` (landed in 0.10.x); GitHub Discussions + Sponsor toggles (owner-side).
- **E4** Research-grade reproducibility — per-OS lockfiles for the missing triples (macOS-arm64-py312, linux-arm64-py312); deterministic-seed propagation audit; cosign container signing.
- **Owner action** — register PyPI Trusted Publisher at <https://pypi.org/manage/account/publishing/> so `pip install ophamin` works canonically.

### Toward 0.11.x – 0.12.x

- **E9** Cross-language read APIs — Rust `crates/ophamin-proof` + TS `packages/ophamin-proof-js`. Both verify signed-record bytes byte-equal against the Python reference codec.
- **E3** Open data + benchmarks — Zenodo deposit of a curated 100+-proof benchmark corpus with its own DOI; reproducer notebooks for ≥ 6 scenarios.

### Toward 1.0.0

- **E1** Cross-framework validation — GWF↔Garak + Bayesian↔Stan + CRDT↔Yjs cross-checks, each producing a signed proof published under `proofs/measurement_machinery/`.
- **E5** Peer review + publication — methods paper submitted to JOSS / SoftwareX / JMLR-OSS.
- **External rebuild verification** (E4 closeout) — a third-party reviewer rebuilds a tagged release and signs off on byte-equal output.

When E4 closes + E5 has reviewer feedback, the owner cuts `1.0.0`.

## What we are NOT doing

- **No external LLM in the runtime.** The framework is library code +
  pre-registered scientific scenarios; an LLM-in-the-loop would
  contaminate every signed proof's reproducibility claim.
- **No surveillance / behavioural-modification scenarios.** The
  framework's scope is empirical measurement of substrates that
  consent to being measured. Scenarios that target unconsenting
  systems are out of scope.
- **No paid features.** The full framework is Apache-2.0, forever.
  The Sponsor button (when active) supports the project's continued
  development; it never gates features.

## How to influence the roadmap

- **Propose an RFC** under `docs/rfc/` (see [`docs/rfc/README.md`](docs/rfc/README.md)).
- **File an issue** for bugs, regressions, or scope questions on a
  specific scenario.
- **Open a PR** for bug fixes / refactors / tests / docs without
  filing an RFC first; the owner reviews on the merit of the diff.

## Cross-references

- [`docs/ELEVATION_ROADMAP_2026_05_16.md`](docs/ELEVATION_ROADMAP_2026_05_16.md) — the full design intent
- [RFC 0002](docs/rfc/0002-sota-elevation-stages-5-and-6.md) — Stages 5+6 ratified plan
- [`CHANGELOG.md`](https://github.com/IdirBenSlama/Ophamin/blob/main/CHANGELOG.md) — what's actually shipped
- [`GOVERNANCE.md`](https://github.com/IdirBenSlama/Ophamin/blob/main/GOVERNANCE.md) — who decides what
- [`docs/STABILITY.md`](docs/STABILITY.md) — what the contract guarantees
- [`SCHEMAS.md`](https://github.com/IdirBenSlama/Ophamin/blob/main/SCHEMAS.md) — what the wire format guarantees
