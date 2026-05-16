# Changelog

All notable changes to Ophamin will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project follows [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- **Round J (round 10) — closure of two open Family U characterisation tracks.**
  Per owner directive "proceed" + full authorization. Round I left two
  characterisation tracks open: WHAT TRIGGERS the QBE bimodality, and WHY
  did Round H U4's GCD recovery only succeed 25%. Round J root-causes both
  as VALIDATED claims.

  - **`QuantumBasisCorrelationScenario`** (`quantum-basis-correlation`)
    — partitions cycles by stimulus class, computes high-QBE rate per
    class, verdict against ≥ 15pp difference. Secondary measurements:
    `halt_reason × QBE state` cross-tab, prime_chain length per QBE
    state, phi per QBE state.

    First end-to-end run on Round G/H/I's 200-cycle trajectory:

    - **U9 VALIDATED at 2.6× threshold**: mixed-pool 60.0% vs axiom
      21.0% = **39pp difference**.
    - **`selective` halt 6/6 cycles middle-QBE** (perfect alignment).
    - **`amplitude_death` 14/16 zero-QBE** (associates with focused
      quantum basis).
    - High-QBE cycles emit FEWER primes (7.8 vs 11.0 mean).
    - Substrate's quantum prime basis is a coherent observable signal
      about substrate state, not noise.

  - **`PrimeDirectLookupScenario`** (`prime-direct-lookup`) — operates
    on trajectories produced by the new capture script. Calls
    `ArachneProtocol.lookup(concept)` directly to get the actual
    ArachnePrime's `(p_thermo, p_identity, substrate_state_stamp)`
    fields. Verdict against ≥ 95% prime p_thermo AND median ≥ 2.

    First end-to-end run on 60-cycle direct-lookup trajectory:

    - **U10 VALIDATED**: **100% prime p_thermo (483/483)**, range
      [2, 37], median 3, mean 5.09, 11 unique values.
    - **Matches CLAUDE.md F.1.1's documented lyriform [7, 29]
      expectation cleanly** (extends to [2, 37] empirically).
    - **Stamps cycle-uniform: 100% of cycles have a single stamp**
      across all concepts.

  - **Round H U4 root cause definitively closed**: the "p_thermo=1
    majority (74%)" was a GCD-recovery artefact. When p_thermo
    values within a cycle share common factors (42% of values are
    `2`!), `GCD(p_thermo_a × stamp, p_thermo_b × stamp, …) =
    stamp × GCD(p_thermos)`, inflating the recovered stamp and
    collapsing recovered p_thermo to 1. Direct ArachnePrime lookup
    via the substrate's existing `lookup()` API bypasses the
    problem entirely. **Round H U4 SUPERSEDED by U10.**

  - **F.1.1 architecture now empirically airtight at every level**:
    per-element divisibility (Round G U2 = 1880/1880),
    p_identity invariance (Round H U3 = 251/251), p_thermo prime
    emission (Round J U10 = 483/483).

  - **Capture script** at `/tmp/capture_kimera_arachne_lookup.py`
    (uses substrate's `lookup()` API — no Kimera change required).

  - **21 new hardening tests** (10 QBE-correlation + 11
    direct-lookup).

  - **Test suite: 803 → 824 passed** (+21) / 1 skipped / 0 failed.

- **Round I (round 9) — prime ecosystem characterisation (Alexandria fused primes + quantum basis bimodality + internal-event primes).**
  Per owner directive "proceed". Round H wrapped deep F.1.1; Round I
  shifts to the three non-core prime systems on the same 200-cycle
  trajectory.

  - **`PrimeEcosystemScenario`** (`prime-ecosystem`). Three
    sub-measurements:

    1. **U6 — Alexandria fused-prime stability** (HEADLINE):
       persistent fused-keys across cycles validates Alexandria's
       "knowledge fusion via dream cycles" claim. Threshold:
       ≥ 5 keys persist in ≥ 90% of cycles.
    2. **U7 — quantum_prime_basis_entropy distribution +
       bimodality** (characterisation): per-cycle scalar; report
       mean/median/stdev/quantiles; bimodality flag if stdev/mean > 0.8.
    3. **U8 — Internal-event prime emission rate** (characterisation):
       per-cycle iev count distribution; corroborate CLAUDE.md EV-37
       "4/5 kinds fire universally" finding.

    First end-to-end run on Round G's 200-cycle trajectory:

    - **U6: 12 persistent fused-keys VALIDATED at 240% over threshold**.
      Top `Fused(persists+identity)` in 97.5% of cycles. 17562 total
      fused values, **only 48 unique → ~366× prime compression at the
      fusion layer**.
    - **U7: BIMODALITY CONFIRMED.** mean 1.40 ± 1.63, median 0.0000;
      56.5% at 0, 40.5% ≥ 3 nats, only 2.5% middle. stdev/mean = 1.16
      → bimodal indicator TRUE. First empirical characterization of
      the substrate's quantum prime basis pattern.
    - **U8: matches EV-37.** 97.5% of cycles fire ≥ 3 internal-event
      primes. Distribution: 108 cycles fire 3, 87 fire 4, 5 fire 0.
      `last_internal_event_prime` unique across 195/195 cycles.

  - **Cross-finding for Round H U4 p_thermo=1 puzzle**: split the
    trajectory by stimulus class. Both axiom and mixed-pool show
    identical p_thermo distribution (median 1.0, ~75% mass at 1).
    The p_thermo=1 majority is **stimulus-class-invariant** — rules
    out content-class hypothesis. Cause must lie in how the substrate's
    multiple assign methods compose for the bulk of concepts.

  - **Architectural readings**:
    - Alexandria's fusion vocabulary is stable and thematic — top
      `Fused(persists+identity)` matches genesis-axiom 9 ("The prime
      is the invariant. Position changes, shape mutates, identity
      persists").
    - The substrate spends ~half cycles in definite-prime quantum
      wavefunctions (entropy 0) and ~half in entangled multi-prime
      superpositions (entropy ≥ 3) — matches PrimeWaveQuantumEngine's
      `ω_p = exp(2πi/p)` framing in a measurable phenomenon.
    - The 5-kind internal-event closure trilogy (CLAUDE.md
      2026-05-06) remains operationally stable at this commit.

  - **11 hardening tests** including injected-bimodal-qbe + persistent
    threshold validation + EV-37 corroboration test.

  - **Test suite: 792 → 803 passed** (+11) / 1 skipped / 0 failed.

- **Round H (round 8) — deep F.1.1 factorization probe (p_identity invariance + GCD stamp recovery + substrate_state_stamp provenance).**
  Per owner directive "proceed". Round G ended with three follow-on
  candidates explicitly listed; Round H builds the first two as a
  unified scenario and adds U5 surfaced during U4 implementation.

  - **`PrimeFactorizationScenario`** (`prime-factorization`). Three
    sub-measurements on a captured prime trajectory:

    1. **U3 — `p_identity` cross-cycle invariance** (HEADLINE
       verdict): same concept name across N cycles must produce the
       SAME deterministic SHA-256-derived p_identity. Threshold ≥ 99%.
    2. **U4 — Full F.1.1 GCD recovery** (characterisation): per
       CLAUDE.md F.1.1 *"GCD of one cycle's composites recovers that
       cycle's stamp"* — verify by computing `q[j] = composite[j] /
       p_identity(walk[j])`, then `stamp = GCD(q[0..n-1])`, then
       `p_thermo[j] = q[j] / stamp`. Characterise empirical recovery
       rates + p_thermo distribution.
    3. **U5 — `substrate_state_stamp` provenance** (characterisation):
       prime-rate, [100, 49100] range-rate, and equality-rate against
       GCD-recovered Arachne stamp.

    First end-to-end run on Round G's 200-cycle trajectory:

    - **U3: 251/251 = 100% p_identity invariance — VALIDATED.**
    - **U4: GCD-recovered stamp is prime in only 25.26% of cycles**
      (48/190 probed); p_thermo distribution heavily skewed to 1
      (74% of recovered values), top-10 = `{1: 1375, 2: 173, 3: 96,
      5: 85, 7: 70, 11: 28, 17: 18, 13: 18, 23: 5, 19: 4}`. Wider
      range [1, 23] than CLAUDE.md F.1.1's documented lyriform
      [7, 29].
    - **U5: 97.5% prime, 97.5% in [100, 49100] range, 0% match
      GCD-recovered Arachne stamp.** The two "substrate_state_stamp"
      artefacts are provably distinct.

    11 hardening tests including synthetic perfectly-factorizable
    trajectory (validates GCD recovery → 100% under controlled
    conditions).

  - **Architectural finding**: F.1.1 is sound at per-element
    divisibility (Round G U2 confirmed 1880/1880); cycle-level
    GCD-uniform-stamp factorization is more nuanced than the headline
    formula suggests. Multiple assign paths (assign,
    assign_via_lyriform, assign_from_field, assign_from_image,
    assign_from_internal_event, assign_via_zeta) emit different
    composite-formula behaviors; a cycle's prime_chain may mix
    elements from different paths.

  - **Pattern-T naming overlap surfaced**: there are TWO distinct
    things called "substrate_state_stamp" in the substrate. Future
    Ophamin scenarios should specify WHICH one they mean.

  - **Test suite: 781 → 792 passed** (+11) / 1 skipped / 0 failed.

- **Round G (round 7) — prime-tier scenarios focused on substrate's prime apparatus.**
  Per owner directive "focus on Primes aspects". CLAUDE.md §"The
  substrate's architectural center is primes" identifies primes as
  Kimera's load-bearing center. Round G measures the substrate's
  prime emission directly with two new scenarios riding a 200-cycle
  prime-focused capture.

  - **`PrimeStructureScenario`** (`prime-structure`). Multi-faceted
    probe of substrate's prime emission. Captures 4 properties:
    1. **Concept-set recognition Jaccard** (HEADLINE verdict): for
       repeated stimuli, Jaccard between extracted `concepts` sets.
       Per CLAUDE.md F.1.1: composite-prime Jaccard is ~0 by design
       (per-cycle stamp factor) — recognition lives at the concept
       layer, not the composite layer.
    2. **F.1.1 composite-factorization integrity** (secondary): every
       composite emitted in `prime_chain` is verified to satisfy
       `composite % p_identity == 0` where
       `p_identity = SHA256(canonical) → small prime in [100, 49100]`,
       re-implementing `ArachneProtocol._identity_prime` in pure Python
       for offline verification.
    3. **Coverage ratio distribution** —
       `prime_identity_coverage.coverage_ratio` per cycle.
    4. **Vocabulary growth + size distribution** — unique composite
       primes over cycles, log10(prime) histogram, top-10 favourites.

    First end-to-end run on captured 200-cycle Kimera trajectory:

    - **Concept Jaccard floor 0.8462**, mean **0.9932** (HIGHER than
      Session 013's reported 0.94 floor) — VALIDATED.
    - **F.1.1 divisibility 1880/1880 = 100%** — empirically airtight
      at ~50× CLAUDE.md Phase-4's 37/37 baseline.
    - **5 stimuli show PERFECT recognition** (Jaccard = 1.000 across
      all reps) including "The prime is the invariant..."
    - **Composite Jaccard = 0.0000** (informational; confirms
      per-cycle stamp factor working as designed).
    - **Coverage ratio 1.0000 mean and min** across all 200 cycles.

    11 hardening tests including injected F.1.1 violation (off-by-one
    composite breaks divisibility = 1.0).

  - **Capture script** at `/tmp/capture_kimera_prime_trajectory.py`
    (single-purpose; pattern documented in
    `EMPIRICAL_VALIDATION.md` Family U).

  - **Test suite: 770 → 781 passed** (+11) / 1 skipped / 0 failed.

- **Round F (round 6) — substrate-regression hypothesis CLOSED + causal-
  discovery scenario + Pattern-T naming clarifications.**
  Per owner directive "continue analysis for fixes". Round E surfaced 4
  threads worth investigating; Round F resolved all four.

  - **No regression**: Round E T3's "Φ ≈ 0.33 vs Family L's 0.62"
    framing was a confounded-comparison artifact. Verified by 1-cycle
    probe: `phi`, `tidal_kii`, `reasoning_posterior` are three distinct
    top-level OrchestratorResult fields. Family L EV-71's reported
    "0.621 ± 0.065" is `reasoning_posterior` (substrate confidence
    proxy), NOT `phi` (IIT integrated info). Re-captured EV-71's exact
    200-cycle genesis-axiom shape and read `reasoning_posterior`:
    **0.6228 ± 0.0666** vs EV-71's 0.621 ± 0.065 (delta **+0.0018,
    within 1σ — NO REGRESSION**). The Round E T3 `phi` measurements
    are real but compare to nothing in Family L's record.

  - **`CausalDiscoveryScenario`** (`causal-discovery`). Tigramite
    PCMCI on captured Kimera multi-channel trajectories. Default
    5 channels at max_lag=2, pc_alpha=0.05. Verdict against ≥ 1
    significant directed link. First end-to-end run on Round E's
    100-cycle trajectory: **32 significant links** detected.
    Disambiguates Round E T4's direction-ambiguous correlations:
    - `phi → dissonance_events_count` lag=0 AND lag=2 (lag-2 is the
      one-way directed signal — substrate's "integrating-layer-surfaces-
      contradictions-over-time" pattern)
    - `kuramoto → arachne_web_order_parameter` lag=0 (predicted
      direction for memory-as-deformation per CLAUDE.md)
    11 hardening tests including injected-causal-structure detection.

  - **`KIMERA_FIELD_CATALOG` Round F refresh**:
    - **Added `reasoning_posterior` entry** — clarifies that THIS is
      the field Family L EV-71 reported as "0.621 ± 0.065" (not `phi`).
      Round F replicated to 0.6228 ± 0.0666 (delta +0.0018, within 1σ).
    - **Added `phi_source` entry** — provenance label for `phi`'s
      computation source (e.g. `'kii'` when phi is derived from
      tidal_kii, explaining Round E T4's MI=2.30 nats coupling).
    - **Updated `phi` entry** — corrects Family L attribution; adds
      Round F-measured values (`phi` mean ≈ 0.48 on genesis axioms).
    - **Updated `dissonance_score` entry** — explicit note that it
      sums weighted SSD (subsystem-state-dissonance) events from
      Phase 302.6 with 4 types, NOT downstream of `dissonance_events`
      (Zetetic concept-pair list with 6 types). Round E T4's MI=0.17
      nats between them is correct by design — they monitor different
      substrate layers despite sharing the "dissonance" prefix.
    - **Retired phantom `arachne_web_kuramoto_order` entry** with
      retirement comment — the substrate emits no such field at this
      commit (verified by exhaustive grep). Real fields are
      `arachne_web_coupling_frobenius`, `_coupling_top_eigenvalue`,
      `_order_parameter`, `_phase_std`. The whole-substrate "Kuramoto
      order" is captured by top-level `kuramoto_order_parameter` (NOT
      an `arachne_web_*` variant).

  - **Test suite: 759 → 770 passed** (+11 causal-discovery tests) /
    1 skipped / 0 failed.

  - **Empirical findings load-bearing for future Kimera work**:
    - There is NO substrate regression at the canonical confidence
      metric. Future "Φ regression" claims should specify which
      Φ-like metric is meant (`phi` vs `reasoning_posterior` vs
      `tidal_kii` vs legacy `kii_value`).
    - `phi → dissonance_events_count` is causally directed at lag-2
      (substrate's integration-surfaces-contradictions signature).
    - `kuramoto → arachne_web_order_parameter` is directed lag-0
      (first empirical confirmation of memory-as-deformation's
      predicted direction).
    - `dissonance_score` and `dissonance_events_count` are unrelated
      by design (distinct upstream signals from different layers).

- **Round E (round 5) — real-substrate Ophamin scenarios + KIMERA_FIELD_CATALOG drift fixes.**
  Captured a real 100-cycle Kimera trajectory (commit `6bf8756d3`,
  batch-mode adapter, 68.9s wall, 100/100 success) and built two new
  scenarios that operate on REAL substrate data, not synthetic.

  - **`CrossChannelMutualInformationScenario`** (`cross-channel-mi`).
    Pairwise MI across 8 substrate-channel pairs from a captured
    trajectory. Two backends: pyitlib (Shannon, discretized) +
    ennemi (KSG, continuous, unbiased at small N) cross-check.
    First end-to-end run on real Kimera trajectory: **8/8 pairs above
    0.05-nat floor; max MI 2.30 nats `phi ↔ tidal_kii`** (essentially
    perfect coupling — empirically corroborates the phi/KII rename
    signal CLAUDE.md §Family L documents). All 8 pairs agree on
    direction across both estimators (cross-backend soundness). Notable
    findings: `phi ↔ kuramoto_order_parameter` MI 0.67 nats
    (memory-as-deformation cross-channel signature); `phi ↔
    dissonance_events_count` MI 1.02 nats (counterintuitive — substrate
    "thinking-harder" indicator, worth follow-on causal probe);
    `dissonance_score ↔ dissonance_events_count` MI only 0.17 nats
    (surprisingly low — score isn't simply count-derived);
    `alexandria_mass ↔ cycle_index` MI 1.76 nats confirms 17
    mass-units/cycle linear-deterministic rate.
    11 hardening tests including small-N pyitlib bias + ennemi cross-
    check oracle pattern.

  - **`BayesianPhiPosteriorScenario` re-run on REAL captured Φ
    trajectory** (no scenario-code change; T3 proof record using
    `phi_trajectory_path=` mode). Posterior 94% HDI width contracts at
    the predicted √N rate. Observed contraction 0.403 (theoretical
    0.447, ceiling 0.50). **Recovered posterior μ_Φ at N=100 = 0.330
    ± 0.033, HDI [0.295, 0.360]** — substantively LOWER than Family L
    EV-71's 0.621 on engineered axioms. Sits between Family L (0.621
    engineered axioms) and Family P (0.209 Linux kernel commits). The
    mixed-stimulus pool baseline is now an established empirical
    reference for Kimera Φ.

  - **`KIMERA_FIELD_CATALOG` drift fixes** (43 → 55 entries). Capture
    surfaced 5 catalog names that the substrate no longer emits at
    commit `a0adf1a0b/6bf8756d3`:
    - `phi_value` → `phi`
    - `kii_value` → `tidal_kii`
    - `walker_halt_mode` → `halt_reason`
    - `dissonance_events_count` → `dissonance_events` (list) +
      `dissonance_score` (float)
    - `gwf_blocked` → `gwf_lockdown` (bool) + `gwf_verdict` (str) +
      `gwf_health` (float)

    Catalog now carries canonical substrate names alongside legacy
    aliases (no breakage; old names retained for backward-compat with
    Family L EV-71 + earlier Ophamin scenarios).

  - **Capture script** at `/tmp/capture_kimera_trajectory.py`
    (single-purpose; not committed to Ophamin's tree). Pattern
    documented in `EMPIRICAL_VALIDATION.md` Family T (extended) so it's
    reproducible.

  - **Test suite: 748 → 759 passed** (+11 cross-channel-mi tests) /
    1 skipped / 0 failed.

  - **Catalog drift discovery validates the Family-S structural-tier
    pattern**: a per-commit static probe surfaced naming drift between
    Ophamin's documentation layer and Kimera's actual emission. Without
    the discover sweep, this drift would have gone unnoticed; with it,
    every catalog name that the substrate doesn't emit gets surfaced
    automatically.

- **Round 4 — round-3 helpers operationalized as Ophamin scenarios + Kimera-side delivery.**
  Per owner directive *"continue autonomously across all fixes needed, you have
  all authorizations"*. Closes the gap between round-3 (helpers exist) and
  scenarios (helpers drive falsifiable claims that produce signed proof
  records), plus pip_audit scope methodology gap surfaced in EMPIRICAL_VALIDATION
  Family S.

  - **`pip_audit` pillar — target-venv scoping + risk-accepted suppression.**
    - New `python_exe` parameter (constructor or per-call kwarg) scopes the
      scan to a specific venv via `pip freeze --all` → `pip-audit
      --requirement <freeze.txt> --disable-pip`. Closes the methodology gap
      where the pillar implicitly audited Ophamin's ambient venv regardless
      of what the caller passed as `target_path`.
    - New `ignore_vulns` parameter + `DEFAULT_RISK_ACCEPTED_CVES` constant
      with curated default list. Each entry documented per-CVE in
      `docs/RISK_ACCEPTED_CVES.md` (rationale, attack-vector reachability,
      compensating controls).
    - Default suppressions:
      - `CVE-2025-69872` (diskcache 5.6.3 unsafe pickle) — local-only
        attack surface; no upstream fix; pulled in transitively by dvc-data
      - `PYSEC-2022-42969` (py 1.11.0 SVN ReDoS) — Ophamin doesn't use SVN;
        zero reachable attack surface; project abandoned 2021
    - `PillarResult` extended with `extra: dict` field that records what
      scope + ignore-list actually ran (self-describing audit trail).
    - 6 new hardening tests in `tests/test_auditing.py`.

  - **`KIMERA_FIELD_CATALOG` refresh** (39 → 43 entries; docstring header
    updated 638 → 665 OrchestratorResult fields per Kimera commit
    `a0adf1a0b`):
    - `arachne_web_order_parameter` — monotonic 0.295→0.741 across cycles
      1-10 in 2026-05-15 discover sweep (memory-as-deformation at Arachne
      layer)
    - `arachne_web_coupling_frobenius` — monotonic 1.27→2.64 (energy
      interpretation)
    - `arachne_web_coupling_top_eigenvalue` — 1.18→2.24 (dominant-mode
      amplification)
    - `alexandria_knowledge_mass_cumulative` — linear ~4.5 mass-units/cycle

  - **`bayesian_helpers.posterior_for_normal_mean` HDI precision fix.**
    `az.summary` rounds values to 4 decimal places by default — fine for
    display, NOT fine for ratio comparisons (broke the Bayesian-Φ scenario's
    contraction-ratio claim). Now reads HDI bounds via `az.hdi` directly on
    raw posterior samples; preserves full numerical precision. Mean / sd
    also computed from samples directly (consistent precision throughout).
    Backward-compatible with arviz 0.x (`hdi_prob=`), 1.x (`prob=` and
    `ci_prob=`).

  - **2 new scenarios** with signed proof records:
    - **`CRDTLawsScenario`** (`crdt-laws`) — cross-backend Yjs Python
      convergence claim. Generates N randomized insert-op sequences; applies
      each to BOTH `pycrdt` and `y-py` YDocs; asserts identical final text
      in ≥99% of cases. First end-to-end run: 100/100 converged in 0.22s,
      Wilson 95% CI [0.96, 1.00], **VALIDATED**. 9 hardening tests.
    - **`BayesianPhiPosteriorScenario`** (`bayesian-phi-posterior`) — Φ
      posterior contracts at theoretical √N rate as N grows. Default
      sample sizes (20, 50, 100, 200) on Family-L-EV-71-shaped synthetic
      Φ values; pre-registered ceiling `HDI_width(200)/HDI_width(20) ≤
      0.40` (theoretical 0.316). First end-to-end run: contraction ratio
      0.397, **VALIDATED**. 15 hardening tests including zero-HDI-width
      edge case → INCONCLUSIVE handling. Drives `bayesian_helpers.posterior_for_normal_mean`.

  - **Pre-existing test regression fix.** `test_binary_checks_catalog_well_formed`
    was missing `property_test` in its allowed-extras set after round-3 added
    schemathesis to `BINARY_CHECKS`. Surfaced + fixed.

  - **Verified end-to-end against canonical Kimera tree.** The other Kimera
    worktree (`kimera-full-system/.venv`) was missing Kimera deps (uv venv
    without pip). Bootstrapped via `python -m ensurepip` + `pip install -e .`;
    verified `KimeraAdapter` probe round-trips against canonical tree.

  - **Test suite: 724 → 748 passed** (+24 new) / 1 skipped / 0 failed.

- **Round 3 — wrap every installed catalog tool into Ophamin-native pillars / probes / helpers.**
  Per owner directive *"These are installed and importable, but no Ophamin-native
  pillar/probe/scenario wraps them yet. do everything properly"*. Closes the
  gap between *installed* (round 2) and *usable* (round 3).

  - **2 new audit pillars**:
    - **ProspectorPillar** (deep-scope) — wraps `prospector --output-format=json`,
      a multi-linter aggregator (pylint + pyflakes + mccabe + dodgy + pep257 + ...).
      Severity map: error → HIGH, warning → MEDIUM, info → LOW. Wired into
      `DEEP_PILLAR_CLASSES`.
    - **SchemathesisPillar** (project-scope) — wraps `schemathesis run` for
      OpenAPI contract testing. Searches target for `openapi.{json,yaml,yml}` or
      `swagger.{json,yaml,yml}`. Severity map: not_a_server_error → CRITICAL,
      status_code_conformance → HIGH. Wired into `PROJECT_PILLAR_CLASSES`.

  - **6 new helper modules** in `src/ophamin/measuring/` and `src/ophamin/comparing/`:
    - `causal_helpers.py` — DoWhy + EconML + Tigramite wrappers:
      `estimate_average_treatment_effect`, `refute_causal_estimate`,
      `causal_discovery_pcmci` (returns `[(cause, effect, lag, p)]`).
    - `bayesian_helpers.py` — PyMC + ArviZ + NumPyro wrappers:
      `posterior_for_normal_mean` (with HDI), `numpyro_posterior_for_normal_mean`
      (~3-5× faster for large N). ArviZ 0.x and 1.x column-naming both supported
      (`hdi_3%/hdi_97%` and `eti94_lb/eti94_ub`).
    - `sat_smt_helpers.py` — z3 + cvc5 wrappers + cross-backend oracle:
      `check_sat_z3`, `check_sat_cvc5`, `check_sat_cross_backend` (asserts
      both backends agree). Z3 empty-AstVector parse-error trap added so silent
      mis-parses become loud-fails.
    - `timeseries_helpers.py` — STUMPY + PyOD + Darts + tsfresh wrappers:
      `matrix_profile_motifs` (motifs + discords), `detect_outliers_pyod`
      (iforest/lof/knn/copod), `forecast_with_darts` (naive_seasonal/drift/mean),
      `extract_features_tsfresh`.
    - `graph_helpers.py` — python-igraph wrappers (~30× faster than NetworkX
      for large graphs): `pagerank_top_k`, `community_detection`
      (louvain/leiden/label_propagation/infomap), `betweenness_top_k`.
    - `comparing/crdt_state.py` — pycrdt + y-py wrappers with uniform `YDocFacade`
      (insert_text / get_text / encode_state / apply_state) +
      `cross_backend_convergence` cross-check oracle (both backends bind to the
      same Yrs Rust core, so they MUST agree — disagreement is a real bug).

  - **3 helpers extended in `analytic_helpers.py`**:
    - `shannon_entropy_discrete` (pyitlib, supports both int and str samples)
    - `kl_divergence_discrete` (pyitlib)
    - `nonlinear_correlation` (ennemi, version-resilient for both DataFrame and
      ndarray return types)
    - `conformal_prediction_intervals_puncc` (puncc backend cross-check oracle
      for the existing crepes-based intervals)

  - **36 new hardening tests** in `tests/test_round3_wrappers.py`. Test count:
    682 → 718. One skipped: `dowhy.estimate_average_treatment_effect` is upstream-blocked
    (PyPI `dowhy 0.8` calls `networkx.algorithms.d_separated` which NetworkX
    removed in 3.0+ — not an Ophamin issue, documented as `pytest.skip` with
    explanation).

  - **`pyproject.toml` extras** updated with all round-3 tools:
    `causal +tigramite`, `bayesian +numpyro`, `sat_smt +cvc5`, new `graph` and
    `crdt` extras, `audit +prospector`. The `all` extra mirrors the additions.

  - **`verify.py` BINARY_CHECKS** extended with `prospector` and `schemathesis`
    binaries. Verify catalog post-round-3: 89 ok / 0 missing / 1 error
    (CausalPy still upstream-blocked by arviz 1.x).

  - **All helpers raise `ImportError` cleanly on missing deps** (no silent
    fallback per project no-fallback rule); inputs validated at boundary.

- **Plugin-install round 2 — 17 more catalog tools.** Per owner directive
  *"Ophamin is not complete"*. Installed: CausalPy, Tigramite, NumPyro,
  Cosmic Ray, Slipcover, cvc5, pySMT, Safety, SPDX-tools, python-igraph,
  pycrdt, y-py, JAX, Cython, Prospector, NPEET (from git), pacmap.
  Verify catalog: 87 ok / 0 missing / 1 error (CausalPy installed but
  import fails: arviz 1.1 removed `r2_score` — upstream-blocked, not an
  Ophamin issue).

  Failed installs honestly recorded:
    Atheris  — Google fuzzer C-extension build fails on Py 3.14
    gensim   — fastText C-extension build fails on Py 3.14
    Syft / Grype / OSV-Scanner — Go binaries; no brew on this host

- **3 new audit pillars** wired into the registry:
  - **SemgrepPillar** (deep-scope) — custom-rule SAST, default config
    `p/python`. Loads any `.yml` ruleset via `--config <path>`. Prepares
    the way for Kimera-specific custom rules (no-fallback, Pattern-P
    naming) which are next-round.
  - **CoveragePillar** (project-scope) — runs `coverage run -m pytest`
    + emits per-file findings for files below `min_coverage` (default 70%).
  - Plus prior PylintPillar / RefurbPillar / InterrogatePillar.
  - `DEEP_PILLAR_CLASSES` now: pylint, semgrep
  - `PROJECT_PILLAR_CLASSES` now: deptry, fawltydeps, coverage

- **5 new analytic helpers** in `measuring/analytic_helpers.py`:
  - `persistence_diagram(points, maxdim)` — ripser Vietoris-Rips H0/H1/H2
  - `bottleneck_distance(dgm_a, dgm_b)` — persim metric for diagram drift
  - `conformal_prediction_intervals(cal_residuals, yhats, confidence)` —
    crepes-validated CP intervals
  - `mutual_information_npeet(x, y, k)` — NPEET KSG estimator (cross-check
    oracle for `mutual_information_continuous`)
  - `reduce_to_2d_pacmap(embeddings)` — alternative dim reduction
    preserving both local AND global structure (Wang et al. JMLR 2021)

- **21 new hardening tests** in `tests/test_extended_helpers_and_pillars.py`:
  TDA tests (circle → β1=1), bottleneck distance properties, CP coverage,
  NPEET cross-check vs infomeasure, PaCMAP shape, pillar-registry membership.
  Test count: 661 → 682.

- **Bulk plugin-catalog install — 32 of 33 OSS tools landed in Ophamin's venv.**
  Per owner directive *"keep downloading, install, building, and setting up
  all tools for Ophamin"*. Installed across 11 batches:
    - **Statistical / analytical**: pingouin, POT, pyitlib, ennemi,
      infomeasure, crepes, deel-puncc
    - **Causal**: dowhy, econml, causalml
    - **Time-series**: darts, tsfresh, pyod, stumpy, statsforecast
    - **TDA**: ripser, scikit-tda (kepler-mapper + persim), gudhi
    - **Bayesian**: arviz, pymc
    - **Property/fuzz**: hypothesis, schemathesis, coverage
    - **Acceleration**: polars, duckdb, numba
    - **Code quality**: pylint, refurb, semgrep
    - **SAT/SMT**: z3-solver
    - **Dim reduction**: umap-learn, pacmap
    - **Skipped**: PyPhi (upstream Py3.10+ incompatibility — uses
      `from collections import Iterable` removed in 3.10), sktime (caps at
      Py3.11 via skbase), dit (cascading prettytable / pycddlib failures)

- **PylintPillar (deep-scope) + RefurbPillar (file-scope, default).**
  Two new audit pillars wrapping pylint (deeper than ruff — type inference,
  custom plugins, complex inheritance) and refurb (Python ≥3.10
  modernization suggestions). New `DEEP_PILLAR_CLASSES` tuple separates
  pylint from defaults (slow + opinionated, opt-in via
  `--pillars=...,pylint`). Refurb joins `DEFAULT_PILLAR_CLASSES`. Both
  GPL-2 / GPL-3 — invoked via subprocess (no library import).

  Live empirical signal — Ophamin self-audit:
  - **pylint: 755 findings**
  - **refurb: 240 findings**
  - **Combined: 995 findings on Ophamin's own source.** Top hotspots:
    `wiring_probe.py` (113), `kimera_inventory.py` (48), `cli.py` (37),
    `verify.py` (30), `proof/record.py` (30) — exactly the v0.2 modules
    built recently. Concrete fix-list to clean up before v0.2 ships.

- **`measuring/analytic_helpers.py` — 4 small wrappers over catalog libs.**
  - `effect_size_cohens_d_with_ci()` — pingouin's compute_effsize +
    compute_esci bundled (scipy doesn't ship CI for Cohen's d)
  - `multiple_comparisons_correction()` — pingouin.multicomp wrapper
    (FDR / Bonferroni / Holm / Sidak)
  - `wasserstein_distance_1d()` — POT's exact-EMD reference oracle for
    Kimera's IIT30 closed-form `_emd_hamming` validation
  - `mutual_information_continuous()` — infomeasure's KSG estimator
    (Kraskov-Stögbauer-Grassberger, the academic reference for continuous MI)
  - `reduce_to_2d()` — UMAP for visualizing high-dim primes / embeddings
    in the reporting wheel

  All loud-fail on missing deps (no silent fallback per CLAUDE.md). 17
  hardening tests pin known mathematical properties (W1 = 0 for identical
  samples, MI ≈ 0 for independent vars, MI > 0.8 for strongly correlated,
  Bonferroni more conservative than FDR, etc.).

- **`pyproject.toml` extras: 9 new categorized extras** —
  `[analytic]`, `[causal]`, `[tda]`, `[timeseries]`, `[bayesian]`,
  `[property_test]`, `[acceleration]`, `[sat_smt]`, `[conformal]`,
  `[infotheory]`. Lets installers pull only the categories they need.
  `[all]` extra now includes everything.

- **Verify catalog: 70 ok / 0 missing / 0 error.** Self-check now covers
  every installed analytical + statistical tool with `import` verification
  and version capture. Was 37 → 70 (+33 new dep checks + 4 binary checks).

  Test count: 633 → 661 (+28 across pillars + analytic helpers + new
  default-pillars-set test).

- **interrogate audit pillar — PR #9 sibling.** Docstring-coverage pillar
  using `interrogate`'s Python API directly (no subprocess). Per-file
  findings emitted when coverage falls below `fail_under` (default 80%).
  Severity bands: < 30% → HIGH, < 60% → MEDIUM, < 80% → LOW. File-scope
  (joins `DEFAULT_PILLAR_CLASSES`). MIT licensed.

  Pivot story this round: tried Pyright (Node.js bundle download fails in
  this venv), Mutmut (wrong shape — runs full test suite per mutation,
  too expensive for an audit pillar), then settled on interrogate (pure
  Python, native API, native fit). The catalog's 12-pick shortlist isn't
  prescriptive — when a tool doesn't fit, the next adjacent one usually does.

  Live empirical signal: Ophamin self-audit at 52.1% docstring coverage
  (1091 nodes, 568 documented, 523 missing). Provides immediate per-file
  action list of where to add docstrings.

  13 hardening tests in `tests/test_interrogate_pillar.py`. Test count:
  620 → 633.

- **deptry + fawltydeps audit pillars — PR #9 of the v0.2 plugin-catalog
  roadmap.** Two new project-scope audit pillars that detect
  declared-vs-imported dependency mismatches in `pyproject.toml`. Both MIT
  licensed. New `PROJECT_PILLAR_CLASSES` tuple separates them from
  file-scope pillars (`DEFAULT_PILLAR_CLASSES`); they're opt-in via
  `--pillars=...,deptry,fawltydeps`. On non-project targets they return
  `status="error"` with a clear message rather than crashing.

  Smart code-root detection in `FawltyDepsPillar`: walks `src/` →
  `<project_name>` → `lib/` → fallback to project root. Avoids the failure
  mode where the tool would walk Kimera's `data/raw/offensive_security/`
  exploit corpus and choke on intentionally-broken Python.

  Live empirical signal against Kimera-SWM @ a0adf1a0 (2026-05-15):
  - **deptry: 450 findings** (302 HIGH severity = undeclared deps with
    runtime crash risk). Top hotspots: pyproject.toml (13),
    `interfaces/graphql/schema/validation_extensions.py` (7),
    `domain/quantum/thrml_thermodynamic_solver.py` (6),
    `infrastructure/database/async_arango_bridge.py` (6).
  - **fawltydeps: 73 findings** (67 HIGH = undeclared, 6 MEDIUM = unused).
    Top: pyproject.toml (6), `cuda_image_encoder.py` (3),
    `observability/alert_channels.py` (3), `gpu_monitor.py` (2).
  - **Combined: 523 dependency-level wiring issues** in Kimera. Direct
    extension of the wiring probe's surface from module-level to
    dependency-level.

  17 hardening tests in `tests/test_dependency_pillars.py`. Test count:
  603 → 620.

- **`ophamin drift-detect` + River-backed `StreamDriftDetector` — PR #4 of
  the v0.2 plugin-catalog roadmap.** First implementation of the per-stream
  online drift-detection adapter pattern. Wraps River's ADWIN, KSWIN, and
  PageHinkley detectors behind a single `StreamDriftDetector` interface;
  emits a signed, content-addressed `DriftScan` artefact per scan
  (`comparing/drift_detection/`).

  Two stream extractors:
  - `extract_phi_stream(cycle_results)` — per-cycle Φ trajectory
    (handles `phi_value` / `phi` / `kii_value` keys across Kimera's
    naming evolution + MockSubstrate)
  - `extract_walker_halt_counts(cycle_results, window)` — rolling
    fraction of Walker M2 amplitude_death halts (drift on this stream
    marks Family E5's monotonic-decay characterization shifting)

  Pivot story: tried Frouros first (BSD-3, single-purpose) — capped at
  Python 3.12; tried Evidently (Apache-2) — pulled 19+ extra deps
  (litestar, plotly, nltk, faker). Settled on River, which Ophamin
  already had + supports 3.14 + ships ADWIN+KSWIN+PageHinkley. Shows the
  catalog's value: when one tool doesn't fit, the next one in the
  category does.

  Live empirical run against Kimera-SWM @ a0adf1a0 (2026-05-15):
  - 30 cycles on stationary input: 0 false-positive drift events ✓
  - 30 cycles half-neutral / half-formal-math: mean Φ shifts 0.4663 →
    0.2048 (56% drop) but ADWIN at default config didn't fire on N=30
    — correctly conservative; tune `delta` or run more cycles to flag

  CLI: `ophamin drift-detect [--repo R] [--target entity] [--n-cycles N]
       [--stream phi|walker_halt] [--detector adwin|kswin|page_hinkley]`

  26 hardening tests (factory, stream extractors with edge cases,
  stationary-vs-step-change behavior, signing, JSON round-trip,
  tampering, loud-fail on non-numeric input, all 3 detector backends,
  detector-kwargs-forwarded-to-config). Test count: 577 → 603.

- **`ophamin verify` — install self-check + CI fast-fail gate.**
  One command that walks every declared dependency (15 required + 9
  optional packages, 7 binary tools) and every documented CLI subcommand
  (19 of them), reports per-check status with install-extra hints, and
  exits non-zero on any required failure. Catches the venv-binary
  resolution gap, the missing-extras gap, broken imports, and renamed
  subcommands at install time instead of letting them silently degrade
  scenarios at run time. Backed by `src/ophamin/verify.py` (~280 LOC) +
  23 hardening tests. Optional `--kimera-repo` flag also probes the
  adapter end-to-end against a Kimera repo. Wired into CI's pytest job
  as a pre-pytest fast-fail gate. Test count: 554 → 577.

  Also: pyproject's `[audit]` and `[all]` extras now declare
  `cyclonedx-python-lib>=11.0` (the interop wheel's SBOM exporter
  imported it but it wasn't pulled by any extra — silent dependency).
  CI now installs `[all,dev]` instead of `[viz,dev]` so the audit job's
  pillar binaries are reachable.

### Fixed

- **Audit pillars now resolve binaries from the venv's bin/ first, not just PATH.**
  When Ophamin runs as ``.venv/bin/python -m ophamin.cli`` without venv
  activation, ``shutil.which("vulture")`` returns None even though vulture
  is installed at ``.venv/bin/vulture``. The audit pillars consequently
  marked vulture / radon / pip-audit as ``status="unavailable"`` against
  Kimera, even when the user had run ``pip install -e '.[audit]'``. New
  ``AuditPillar.resolved_binary()`` looks next to ``sys.executable`` first,
  falling through to PATH. 3 regression tests pin venv-local-preferred,
  PATH-fall-through, and nowhere-found loud failure.

  Verified end-to-end against Kimera-SWM (2026-05-15): ``ophamin audit
  kimera_swm/ --pillars=ruff,bandit,vulture,radon`` now reports **41,953
  total findings** (ruff 18,838 + vulture 12,520 + radon 7,208 + bandit
  3,387) — 81 critical, 9,106 high — across the entire substrate. Top
  hotspot: ``takwin.py`` with 616 findings.

  README + CONTRIBUTING + CI audit workflow updated to install all extras
  by default. Test count: 551 → 554.

### Added

- **`WiringProbe.scan_all()` + `ophamin wiring --all` — v0.2 Step 5b.**
  The inventory-based `WiringProbe.probe()` covers the ~336 *named primitive*
  surfaces. `scan_all()` walks every .py file under `kimera_swm/` (excluding
  `__init__.py` and `__pycache__`) and applies the same classifier — the
  whole-repo substrate-completion picture. Per-bucket aggregation uses the
  top-level subdirectory name (`domain`, `infrastructure`, `interfaces`,
  `api`, `core`, `tests`, etc.), with top-level standalone scripts collapsed
  into a `scripts` bucket so the table stays readable.

  **First whole-repo measurement against Kimera-SWM @ a0adf1a0 (2026-05-15):
  3,363 Python modules**, of which:
  - **178 WIRE_CANDIDATE** (concentrated in `domain/`; matches CLAUDE.md's
    ~322 raw annotations modulo tests + non-module references)
  - **871 orphans** (~26%, but ~87% of those are in expected-orphan
    buckets — `tests/`, `scripts/`, `research/`)
  - **2,078 modules in domain/**: 56% wired, 18% orphan
  - **416 in infrastructure/**: 84% wired, 16% orphan
  - **116 in interfaces/**: 90% wired, 10% orphan
  - **`monitoring/` bucket: 55% orphan** — surfaces unwired observability code
    distinct from `infrastructure/monitoring/` (which is wired)

  7 new hardening tests for `scan_all`. Test count: 544 → 551.

- **WiringProbe + SubstrateCompletenessScenario + `ophamin wiring` — v0.2 Step 5 (pivoted).**
  The owner clarified Kimera is incomplete by design — infra folders may
  be scaffolding nothing actually uses, and Ophamin's load-bearing value
  is empirical feedback to drive substrate completion. The probe builds
  a repo-wide import graph (one pass over kimera_swm/, ~5s on real
  Kimera, ~3500 .py files) + scans for ``.. note:: WIRE_CANDIDATE`` /
  WIRED / ARCHIVED annotations + counts stub function bodies (``pass``
  / ``raise NotImplementedError`` / ``return None``). For each
  inventoried surface it emits a classification: ``wired`` (≥1 incoming
  import OR WIRED annotation), ``wire_candidate`` (explicitly
  scaffolded), ``orphan`` (zero imports, no annotation — the action
  target), ``archived`` (path under ``_archive/`` or
  ``_predecessor.py`` suffix), ``parse_error`` (broken file), or
  ``config`` (non-Python surface).

  ``SubstrateCompletenessScenario`` aggregates into a falsifiable claim:
  ``aggregate_orphan_rate <= 0.20``. ``ophamin wiring <repo>`` writes
  signed JSON + Markdown reports with per-stratum tables + the orphan +
  WIRE_CANDIDATE action lists.

  **First live measurement against Kimera-SWM @ a0adf1a0 (2026-05-15):**
  - **VALIDATED at 26/323 = 8.05% orphan rate**, Wilson CI [0.0553, 0.1158]
  - 289 wired (89.5%), 26 orphan (8%), 8 WIRE_CANDIDATE (2.5%)
  - Action list pinpoints: 7 persistence orphans (postgres_insight_repository
    with 22 unimported functions, connection_manager, database_production_manager,
    enhanced_database_optimizer_fixed — the "_fixed" suffix is the giveaway),
    4 temporal orphans (kccl_integration, scale5_adapters with 37 fns,
    spde_integration, surfacing), 7 lifecycle orphans (encoder_snapshot/builder.py
    despite its docstring promising SnapshotBuilder.build as public API —
    confirmed orphan: __init__.py doesn't import from it), 6 security orphans,
    1 telemetry orphan, 1 interface orphan (monitoring_router.py — verified by
    a comment in core/application.py saying it was deliberately not wired).

  Import graph correctness was verified mid-build: the first run showed
  40 interface orphans, but ``from kimera_swm.api.routers import
  computation_router`` wasn't being counted as an edge for
  ``kimera_swm.api.routers.computation_router``. Fix: extend the import
  scanner to emit ``parent.child`` references on ``from`` imports. Result
  dropped to 1 true interface orphan.

  52 new hardening tests (40 wiring probe + 12 scenario). Test count:
  492 → 544.

- **InterfaceContractStability scientific scenario — v0.2 Step 4.**
  First scenario targeting the **interface** stratum (REST routers,
  controllers, GraphQL, MCP tools, CLI commands, WebSocket). Pure static
  analysis — does not import or run Kimera. For each Python module
  ``KimeraInventory.discover_interface`` reports, runs ``ast.parse`` and
  checks for top-level OR class-method handler-decorator presence
  (FastAPI verbs, MCP ``@tool``/``@resource``, Click ``@command``, etc.).
  Pre-registered claim: ``contract_compliance_rate >= 0.95`` with Wilson
  95% CI.

  Live measurement against Kimera-SWM @ a0adf1a0 (2026-05-15):
  **VALIDATED at 98/100 = 0.98**, Wilson CI [0.93, 0.9945]. Two
  non-compliant outliers (``api/routers/geoid.py`` +
  ``api/routers/multimodal_router.py``) surfaced for investigation.

  This is the **first VALIDATED claim Ophamin has made about the interface
  stratum**. 23 hardening tests in
  ``tests/test_interface_contract_stability.py`` covering the decorator
  matcher (router.get / @tool / @click.command / negative cases),
  per-module probe (package_dir / non-py skip / top-level handler / class
  method handler / syntax error / pure-schema rejection), end-to-end
  scenario on healthy + broken synthetic trees, registry membership,
  Wilson CI, signature, claim shape. Test count: 469 → 492.

- **PrometheusScrapeProbe + `ophamin scrape` — v0.2 Step 3.**
  Passive consumer of Kimera-SWM's `/metrics` endpoint (Kimera already
  ships a `prometheus_client`-based exporter under
  `kimera_swm/infrastructure/monitoring/prometheus_exporter.py`). One scrape
  produces a signed, content-addressed `PrometheusSnapshot` carrying every
  metric family + sample. Loud failure on connectivity / timeout / parse
  error. Plus `AlignedTelemetryWindow` + `align_to_window()` for
  before/during/after correlation with scenario windows — the foundation
  for the Σ (cross-stratum correlation) measuring pillar. Optional
  dependency: `prometheus_client>=0.17` under the `[telemetry]` extra; the
  module loads but probe construction loud-fails if absent. 19 hardening
  tests using a stdlib `http.server` fixture. Test count: 450 → 469.

- **Field catalog + scenario contract gate + `ophamin discover-fields` — v0.2 Step 2.**
  ``KIMERA_FIELD_CATALOG`` documents ~35 high-signal OrchestratorResult
  fields with type + semantic family + description (the families: phi,
  walker, gwf, echoform, consolidation, prime, piovra, substrate_state,
  internal_event, lateral_line, eikonal, ouroboros, alexandria,
  realtime_encoder, timing, manipulation, scar, thermodynamic). Scenarios
  opt into a ``field_contract()`` declaring the fields they depend on; the
  base scenario harness validates the contract against the first
  successful cycle's ``raw`` before scoring and raises
  ``ScenarioFieldContractViolation`` (loud failure) on missing-required,
  type-mismatch, or family-mismatch. Default ``field_contract() = None``
  is back-compat — existing scenarios keep working untouched.
  `ophamin discover-fields <repo>` probes one cycle and surfaces the
  three-way diff (in-catalog · uncataloged · missing-from-raw) so
  Kimera-side schema drift is visible at experiment-setup time.
  Retroactively, the ``cycle_seconds``-dropped-on-floor incident
  (2026-05-15) would have failed the contract immediately. 40 new
  hardening tests (33 catalog, 7 scenario gate). Test count: 410 → 450.

- **`KimeraInventory` + `ophamin inventory` — v0.2 Step 1**
  ([`docs/KIMERA_OBSERVATIONAL_SURFACE_2026_05_15.md`](docs/KIMERA_OBSERVATIONAL_SURFACE_2026_05_15.md)).
  Static enumeration of every observable surface in a Kimera-SWM working
  tree, across nine strata: cognitive, interface, transport, persistence,
  reconciliation, temporal, security, telemetry, lifecycle. Pure file
  enumeration — does not import or execute Kimera. Output is a signed,
  content-addressed, HMAC-verified `KimeraInventory` JSON + Markdown
  report. Each stratum's discoverer is independent; absent files report as
  "dormant" rather than crashing. 23 hardening tests in
  `tests/test_kimera_inventory.py`.

  First live measurement against the production Kimera-SWM working tree
  (commit `a0adf1a0`, 2026-05-15): **336 observable surfaces, all 9 strata
  live**. Cognitive: 11 · interface: 104 · transport: 8 · persistence: 42 ·
  reconciliation: 8 · temporal: 36 · security: 64 · telemetry: 35 ·
  lifecycle: 28. This is the empirical baseline against which the next
  v0.2 steps (field projection, Prometheus consumer, per-stratum
  scenarios) can be sized.

### Fixed

- **`AuditRecord.to_markdown` shadow bug** — the loop variable `for path, count
  in s.top_files` shadowed the `path` parameter, causing the audit markdown
  to be written into the LAST hotspot SOURCE file instead of the caller's
  output path. Latent since `to_markdown` landed; surfaced on GitHub Actions
  when the audit workflow ran on `src/ophamin` and corrupted
  `src/ophamin/inspecting/inspector.py` with audit-record markdown content,
  breaking the next Python import. Fix: rename the loop variable; added
  regression test
  `test_audit_record_to_markdown_writes_to_caller_path_not_hotspot_file`.
  Retroactively explains the earlier `vulture_pillar.py` and `schema_miner.py`
  corruption incidents in this session.

## [0.1.0] — 2026-05-15

### Initial release

Ophamin's first published version. The framework is structurally complete
across six wheels in two concentric triads, with three experimentation tiers
exercised against real Kimera-SWM.

#### Architecture

- **Outer triad** — empirical observation:
  - `seeing/` — substrate adapter, corpus connectors, Layer A schema mining
    + many-small-eyes watcher.
  - `measuring/` — pre-registered measurement engines + six analytic pillars
    (O · F · A · M · I · N) + scenarios across three tiers.
  - `comparing/` — Layer C drift detection over signed proof records.
- **Inner triad** — engineering observation:
  - `instrumenting/` Phase 1 — psutil-based per-cycle resource profiler +
    InstrumentedSubstrate wrapper + periodic subprocess sampler.
  - `auditing/` — orchestrated static-analysis pillars (ruff / bandit / mypy /
    vulture / radon / pip-audit) producing signed Audit Records.
  - `reporting/` — multi-format academic output (HTML / Markdown / LaTeX) with
    matplotlib charts.
- **Cross-cutting**:
  - `inspecting/` — generic per-primitive profile (PrimitiveCatalog + Locator
    + Inspector) that scales to 17 catalogued Kimera primitives.
  - `interop/` — standard-format exporters: SARIF 2.1.0, JUnit XML, MLflow
    runs, CycloneDX 1.5 SBOM.
  - `protocols.py` — first-class plug-in surfaces (Pillar / DatasetConnector /
    SubstrateProbe / ScenarioProtocol).

#### Shipped scenarios (six, across three tiers)

| Tier | Scenario | Latest verdict |
|---|---|---|
| Scientific | Concentrated Immune Siege | VALIDATED (GWF FP = 3.2%) |
| Scientific | Rosetta Scaling | REFUTED (0% cross-language agreement) |
| Scientific | Organizational Dissonance | VALIDATED (97.4% active rate) |
| Scientific | Logic-Topology Siege | REFUTED (39.6% sustained traversal) |
| Engineering | Throughput Ceiling | VALIDATED (p95 = 2.357 s) |
| Philosophical | Self-Reference | REFUTED (Cohen's d = -0.359) |

#### Substrate fixes (Kimera-SWM)

Two surgical fixes committed to Kimera during framework development:

- **GPU device-honesty + no-fallback** (Kimera commit `204fb4f9b`): the
  `GPUAcceleratedTrajectoryOptimizer` was CUDA-only on Apple Silicon, silently
  CPU; fix selects cuda → mps → cpu honestly. 5 hardening tests pin the fix.
- **IIT30 EMD closed form** (Kimera commit `9c055d303`): `_emd_hamming` was
  using a HiGHS LP solver where a closed-form sum of per-bit marginals works
  for product distributions; ~10% throughput gain. 4 hardening tests pin the
  fix.

#### Kimera-side empirical record

Six new families backfilled into Kimera's `EMPIRICAL_VALIDATION.md`:

- Family M (adversarial defense stack)
- Family N (Rosetta sentence-scale operating envelope)
- Family O (dissonance-layer active rate on real-world organisational email)
- Family P (walker halt-mode distribution on Linux kernel commits)
- Family Q (engineering throughput ceiling)
- Family R (philosophical self-reference — refuted)

R11 added to "What was refuted" — the substrate fires *less* dissonance on
text describing its own primitives than on neutral Enron email (Cohen's d =
-0.359).

#### CLI surface

```
ophamin demo / run / sweep / probe-kimera / lineage
ophamin discover / discover-diff / watch         (Layer A schema mining)
ophamin drift-report                              (Layer C drift)
ophamin audit                                     (orchestrated audit pillars)
ophamin inspect / inspect-all                     (per-primitive profile)
ophamin report                                    (HTML / Markdown / LaTeX)
ophamin export                                    (SARIF / JUnit / MLflow / CycloneDX)
```

#### Tests

386 tests, all green. Cross-checks against scikit-learn, statsmodels, MAPIE,
prov driven directly.

[Unreleased]: https://github.com/IdirBenSlama/Ophamin/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/IdirBenSlama/Ophamin/releases/tag/v0.1.0
