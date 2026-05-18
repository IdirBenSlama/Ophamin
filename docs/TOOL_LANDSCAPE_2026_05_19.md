# Tool & standards landscape — where Ophamin fits

> **Audience**: the owner + any Claude session deciding next-direction
> work on Ophamin. Surveys the open-source tools and standards
> Ophamin's signed-proof discipline can compose with, conform to, or
> compete against across criticality tiers (civil → professional →
> critical-mission → military-grade) and data shapes (single-modal,
> multimodal, multi-business).
>
> **What this is NOT**: a recommendation to add every tool below as an
> Ophamin dependency. It's a **landscape map** for positioning,
> benchmarking, and identifying interop targets.
>
> Anchored in primary sources (Ophamin's own paper.md / README / code)
> + 2026 OSS-ecosystem web research. Where a claim depends on
> external sources, the source is cited inline.

## I. The problem-space axes

Ophamin's value proposition (per [paper.md](https://github.com/IdirBenSlama/Ophamin/blob/main/paper/paper.md)
§Statement of need) is **closing the seam between what was run and
what was claimed** with signed, content-addressed, cross-language-
verifiable proof records. Different consumer contexts demand different
compositions of that core:

| Axis | Tiers | What changes per tier |
|---|---|---|
| **Criticality** | Civil → Professional → Critical-mission → Military-grade | Verification surface, signing strength, audit-trail durability, regulatory conformance |
| **Data shape** | Single-modal → Multimodal → Multi-business | Storage backend, schema discipline, modality-specific tooling |
| **Audience** | Internal evidence → External-publishable → Regulator-auditable | Citation surface, archival permanence, third-party validation |

Ophamin today sits **squarely in the "professional / external-
publishable" cell** — JOSS-ready, Zenodo-citable, scientifically
reviewable. The sections below name where Ophamin already touches
each landscape, and which adjacencies are real next-direction
options.

---

## II. The landscape by category

### A. Signed records + supply-chain attestation

The dominant 2026 stack centers on three interlocking standards.

| Tool / standard | What it does | Ophamin relationship |
|---|---|---|
| **in-toto Attestation Framework (ITE-6)** | Defines a common envelope (Statement + Subject + Predicate) for provenance claims. Sigstore + SLSA both consume this envelope. | Ophamin's `EmpiricalProofRecord` is a parallel attestation format, scoped to *empirical claims about substrate behaviour* rather than build-time provenance. Could emit an in-toto Statement wrapper as a future interop layer. |
| **SLSA framework** (Supply-chain Levels for Software Artifacts) | Per-level requirements (1-4) for build provenance + isolation + verification. SLSA 3 = hermetic + parametrized + verifiable build. | Ophamin already ships at **SLSA 3** per `release.yml` — `slsa-github-generator` produces signed provenance for every released wheel. |
| **Sigstore (cosign + Rekor + Fulcio)** | Keyless artifact signing via short-lived OIDC certificates; transparency log via Rekor. As of late 2025 / 2026, Rekor dual-signs each entry with ECDSA + ML-DSA (post-quantum) per Red Hat / sigstore-PQC work. | Ophamin already signs Python wheels via sigstore at release time. Could extend the signing surface to per-proof signatures (today: HMAC-SHA256 only). |
| **PEP 740 (attestations on PyPI)** | Per-release attestations attached to PyPI packages, anchored in sigstore. | Already plumbed in Ophamin's `release.yml` (continue-on-error until PyPI publisher activated). |
| **DSSE** (Dead Simple Signing Envelope) | The transport format for in-toto attestations. | Pattern Ophamin could adopt if it ever emits in-toto attestations. |
| **SCITT** (Supply-Chain Integrity, Transparency, Trust) | IETF draft framework, DARPA-flavored, integrates with sigstore. | Worth tracking for post-quantum audit-trail use cases. |

**Where Ophamin extends beyond build provenance**: SLSA/in-toto attest
**how a build happened**. Ophamin's signed proofs attest **what a
measurement found**. The two compose: an Ophamin proof could itself
be a SLSA-attested artifact in an in-toto Statement.

---

### B. Reproducibility, workflow, lineage

The OSS ecosystem here has consolidated around several families:

| Tool | Domain | What it does |
|---|---|---|
| **DVC** (Data Version Control) | Data / ML | Git-LFS-like for data + experiments; pipeline DAGs. Cited in Ophamin's paper as the "data leg" complement. |
| **MLflow** | ML lifecycle | Run tracking, model registry, OpenLineage emit. Cited in Ophamin's paper as the "run leg" complement; Ophamin's `interop/` exports to MLflow. |
| **Snakemake** | Bioinformatics + general | Make-style declarative workflows; Python-shaped. ~9.x with full plugin architecture as of 2026 per [tasrieit comparison](https://tasrieit.com/blog/nextflow-vs-snakemake-2026). |
| **Nextflow** | Bioinformatics + general | Groovy DSL; dataflow paradigm; container-native; nf-core community. 25.04 introduced strict syntax + `nextflow lint`. |
| **Airflow / Prefect / Dagster / Argo Workflows** | General orchestration | DAG runners for production ML / data pipelines. |
| **Galaxy** | Bioinformatics | Browser-driven workflow platform. |
| **OpenLineage** | Lineage metadata | Open standard for collecting lineage from running pipelines. Hosted by LF AI & Data Foundation; expanded by IBM watsonx in early 2026. Integrations with Airflow, Spark, dbt, Snowflake, BigQuery. |
| **ReproZip** | Environment | Captures the OS-level dependencies of a run. Cited in Ophamin's paper as the "environment leg" complement. |
| **DataLad** | Git-LFS-style data + provenance | Layered on `git-annex`; rich provenance. |
| **CWL** (Common Workflow Language) | Portable workflow spec | Standards-track; consumed by multiple runners. |

**Where Ophamin sits**: orthogonal to these. DVC tracks data, MLflow
tracks runs, Snakemake/Nextflow orchestrate, OpenLineage records
lineage. Ophamin signs the **falsifiability claim and the verdict**.
The four-leg DVC/MLflow/Stan/ReproZip framing in Ophamin's
Statement-of-Need is now closer to a five-leg framing: data /
runs / inference / environment / **signed empirical claim**.

---

### C. Provenance + FAIR data

| Standard / tool | What it does | Maturity |
|---|---|---|
| **W3C PROV-O** | Upper-level OWL2 ontology for provenance (people / institutions / entities / activities). The reference framework. | Stable since 2013; widely consumed by RO-Crate, Galaxy, others. |
| **RO-Crate** (Research Object Crate) | JSON-LD-based packaging of research artifacts + their provenance metadata. **Workflow Run RO-Crate** profile aligns to W3C PROV and is now implemented by 6 workflow systems per the [2024 PLOS One paper](https://journals.plos.org/plosone/article?id=10.1371%2Fjournal.pone.0309210). |
| **OpenLineage** | (see §B) — pipeline-level lineage standard. |
| **FAIR data principles** | Findable / Accessible / Interoperable / Reusable. Not a tool — a metadata + access discipline. |
| **CodeMeta** | Concept-level metadata for research software (JSON-LD, schema.org-aligned). Often paired with CITATION.cff. |
| **Schema.org `SoftwareSourceCode`** | Web-facing software metadata. |

**Ophamin already emits W3C PROV-JSON** in section 8 of every signed
record (`reproduction.provenance` field). Adopting RO-Crate as an
optional output wrapper would integrate Ophamin proofs with the
broader workflow-run RO-Crate ecosystem.

---

### D. Safety-critical certification (where the criticality tier
explicitly matters)

Different industries demand different certifications. Ophamin's
discipline of "compulsory pre-registration + mechanical verdict +
tamper-evident signature" is the kind of property safety-critical
auditors look for, but **Ophamin is not certified** against any of
these standards today. Listed for positioning:

| Standard | Industry | What it requires | OSS tools in this space |
|---|---|---|---|
| **DO-178C** | Avionics (FAA / EASA-mandated for commercial + military aircraft) | Per-level (A-E) requirements for design / verification / configuration management. Tool qualification per DO-330. | `Frama-C` (formal C analysis); `SPARK / Ada` (deductive verification — AdaCore + NVIDIA recent work per [embedded-computing](https://embeddedcomputing.com/technology/open-source/risc-v-open-source-ip/adacore-nvidia-accelerate-iso-26262-compliance-by-securing-critical-firmware-with-ada-and-spark)) |
| **ISO 26262** | Automotive (ASIL A-D levels) | Functional safety analyses (FMEA, FTA); software unit-test coverage requirements. | Same tools as DO-178C. AdaCore has addressed multiple standards including DO-178B/C, EN 50128, ECSS-E-ST-40C/ECSS-Q-ST-80C, IEC 61508, ISO 26262 per [AdaCore](https://www.adacore.com/papers/compare-spark-misra-c-frama-c). |
| **IEC 62304** | Medical-device software (Class A-C) | Risk-based lifecycle process for medical software per [Mndwrk](https://www.mndwrk.com/blog/the-role-of-standards-in-safety-critical-qa-navigating-iso-26262-do-178c-and-iec-62304). |
| **IEC 61508** | Generic functional safety | SIL 1-4 levels. Parent of many domain-specific standards. |
| **EN 50128** | Railway control + protection systems | SIL-based, similar to ISO 26262. |
| **MISRA-C / MISRA-C++** | Coding rules for safety-critical embedded C / C++ | Heavy static-analysis tooling (Cppcheck, Coverity, Polyspace, AbsInt's astree). |
| **CENELEC EN 50657** | Railway onboard software | |

**OSS formal-methods tools relevant across these standards**:

- **Frama-C** — modular static analyzer for C; supports WP (weakest-precondition), Value Analysis, Eva; per [frama-c.com](https://frama-c.com/).
- **SPARK** — Ada subset for deductive verification per [AdaCore paper](https://www.adacore.com/papers/compare-spark-misra-c-frama-c).
- **TLA+** — model checker for distributed systems (Leslie Lamport).
- **Coq / Lean / Isabelle** — proof assistants; foundational rather than industrial.
- **CBMC / Kani** — bounded model checking for C / Rust.
- **Why3 / Cryptol / SAW** — verification frameworks adjacent to SPARK.

**Where Ophamin could conform / extend**: Ophamin's pre-registration
discipline maps cleanly to DO-178C's "objectives are defined before
verification activities begin" principle. A "Phase E11 — safety-
critical conformance" stage would scope Ophamin's signed-proof format
as an artifact suitable for inclusion in a DO-178C / ISO 26262
verification dossier.

---

### E. Compliance + regulated environments

For deployments in regulated / government settings:

| Framework | Scope | What it imposes |
|---|---|---|
| **NIST SP 800-53 Rev 5** | US federal information systems | 1000+ controls across 20 control families. Three baselines: Low, Moderate, High. Per [Isora GRC](https://www.saltycloud.com/blog/nist-800-53-compliance-guide/). |
| **FedRAMP** | US federal cloud services | Authority to Operate (ATO) gated on 800-53 implementation at the right baseline + 3PAO assessment + continuous monitoring per [stackArmor](https://stackarmor.com/fedramp-releases-updates-to-ato-requirements-based-on-nist-sp-800-53-rev-5-for-public-review/). Recent shift toward "continuous authorization" per [trustcloud](https://www.trustcloud.ai/fedramp/from-nist-800-53-to-fedramp-what-it-really-takes-to-bridge-the-gap/). |
| **NIST SP 800-171** | Controlled Unclassified Information (CUI) at non-federal contractors | Subset of 800-53; foundation for CMMC. |
| **CMMC** (Cybersecurity Maturity Model Certification) | DoD contractors | Levels 1-3 based on 800-171 + 800-172. |
| **ISO 27001 / ISO 27002** | Information-security management | International equivalent of 800-53 framing. Often paired with SOC 2 audits. |
| **Common Criteria (ISO 15408)** | Security functional + assurance requirements | EAL 1-7 levels. Government / defense use. |
| **STIG** (Security Technical Implementation Guides) | DISA-mandated hardening | Per-product configuration baselines for DoD systems. |

**OSS tools for compliance-evidence collection**:

- **CycloneDX / SPDX** — SBOM formats. Ophamin already exports CycloneDX SBOMs.
- **OpenSCAP** — automated compliance-baseline scanning.
- **Trivy / Grype** — vulnerability scanners.
- **Falco** — runtime security monitoring.
- **OPA / Gatekeeper** — policy-as-code.
- **OCSF** (Open Cybersecurity Schema Framework) — log normalization.

**Where Ophamin sits**: Ophamin's signed proofs are the **evidence
side**, not the policy side. A signed proof is exactly the kind of
artifact a 3PAO or ATO assessor wants for "we ran the validation
test on this date, on this commit, with this corpus, and got this
verdict, signed by this key."

---

### F. Multimodal scientific data infrastructure

The data side: where heterogeneous modalities (imaging, audio,
text, sensor) need to live together for cross-modal analysis.

| Format / tool | Strength | Domain |
|---|---|---|
| **HDF5** | Hierarchical, multi-dimensional numerical arrays. Strong for raw imaging / audio / simulation per [Oreate AI](https://www.oreateai.com/blog/hdf5-vs-parquet-navigating-the-maze-of-multimodal-data-storage/196c67962d9d249d4ca893c36a80407e). Ophamin already uses HDF5 via The Well corpus. |
| **Zarr** | Cloud-native chunked N-dim arrays; HDF5-compatible front-end API. |
| **Apache Arrow / Parquet** | Column-oriented; analytical workloads with tabular data. Cross-language (Python, R, JS, Rust, C++, Go, …). |
| **N5** | Image-tile-friendly variant of HDF5; popular in neuroimaging. |
| **DICOM** | Internationally adopted standard for biomedical imaging entities + relationships per [PMC article](https://pmc.ncbi.nlm.nih.gov/articles/PMC12451937/). Foundation for hospital-grade imaging pipelines. |
| **NWB** (Neurodata Without Borders) | Standard for neurophysiology data; HDF5-backed. |
| **BIDS** (Brain Imaging Data Structure) | Filesystem-layout standard for neuroimaging. |
| **OMOP CDM** | Common Data Model for observational health; incorporates DICOM imaging since [2025 work](https://pmc.ncbi.nlm.nih.gov/articles/PMC12451937/). |
| **AnnData / scanpy / scverse** | Single-cell genomics standards. |
| **xarray** | Labeled multi-dim arrays in Python; reads HDF5/NetCDF/Zarr. |

**Where Ophamin is positioned**: substrate-agnostic by design.
`SubstrateUnderTest` is the only protocol the framework cares
about — anything emitting per-cycle telemetry can be the
target. Multimodal extension would mean Piovra-like sensory
adapters (the Kimera-side primitive) that consume each modality
and emit unified cycle records.

---

### G. Statistical + analytical methodology (state-of-the-art OSS)

Ophamin's `measuring/pillars/` already orchestrates around
battle-tested libraries (the OFAMIN acronym = O · F · A · M · I · N
pillars). Adjacent OSS in 2026:

| Category | Reference OSS |
|---|---|
| **Frequentist core** | scipy, statsmodels, NumPy (Ophamin uses all three). |
| **Cross-framework validation** | pingouin (provides independent implementations of scipy primitives — already in Ophamin's measurement-machinery tier). |
| **Bayesian inference** | PyMC (PyTensor backend), NumPyro (JAX), Stan / cmdstanpy / PyStan, bambi (formula-based on top of PyMC), Turing.jl (Julia). Ophamin's E1.1 validates PyMC↔NumPyro agreement. |
| **Conformal prediction** | MAPIE (Ophamin uses), conformal-prediction (R + Python). |
| **Mixed-effects / GLMM** | statsmodels MixedLM (Ophamin uses), pymer4 (R lme4 from Python), lme4 (R). |
| **Meta-analysis** | statsmodels `combine_effects` (Ophamin uses for cumulative meta-analysis pillar), `metafor` (R reference). |
| **Causal inference** | DoWhy, EconML, CausalML, tigramite (Ophamin lists in `[causal]` extra). |
| **Topological data analysis** | ripser, scikit-tda, GUDHI (Ophamin lists in `[tda]` extra). |
| **Time series** | darts (deep + classical), prophet, statsforecast, tslearn. |
| **Robust statistics** | scipy.stats robust estimators; R `MASS`. |
| **Streaming drift detection** | river (Ophamin uses). |
| **Property-based testing** | Hypothesis, hypothesis-numpy, schemathesis (Ophamin uses all three). |
| **Information theory** | pyitlib, ennemi, dit (Ophamin uses pyitlib + ennemi for cross-channel-MI scenario). |

**Where Ophamin is differentiated**: not in the methodology
libraries themselves (those are all best-of-class already), but
in **binding the result of those libraries to a signed,
pre-registered, cross-language-verifiable claim**.

---

### H. Publication, citation, archival

| Venue / standard | What it is |
|---|---|
| **JOSS** (Journal of Open Source Software) | Peer-reviewed open-access journal that requires reviewers to install + verify functionality per [PeerJ](https://peerj.com/articles/cs-147/). Open issue-thread review. Authors required to deposit to Zenodo or similar before publication. |
| **SoftwareX** | Elsevier OA journal for software contributions per [Elsevier](https://www.sciencedirect.com/journal/softwarex). |
| **JMLR-OSS** (Journal of Machine Learning Research, OSS track) | OSS track of JMLR. |
| **Software Heritage** | Universal archive for source code; produces SWHID identifiers. |
| **Zenodo** | CERN-hosted archive; per-release + concept DOIs per [arxiv](https://arxiv.org/pdf/1911.00295). Standard for software DOI minting. GitHub integration is one-toggle. |
| **figshare / OSF** | Alternatives to Zenodo. |
| **CITATION.cff** | GitHub-rendered citation metadata. Ophamin ships one. |
| **CodeMeta** | Concept-level metadata format. |

Ophamin's `paper/paper.md` is JOSS-ready, paper-build CI validates
render. `docs/ZENODO_DEPOSIT_WORKFLOW.md` is the owner-physical
workflow.

---

## III. Where Ophamin already touches each landscape

| Category | Ophamin's current touch | Maturity |
|---|---|---|
| Signed records / supply chain | SLSA 3, sigstore, PEP 740, CycloneDX SBOM | ✅ shipped |
| Wire-format ports | Rust crate + JS package (read + write); WCAG-style canonical-form spec | ✅ shipped |
| Reproducibility / workflow | MLflow export; CycloneDX export; reproducibility audit scenario | ✅ shipped |
| Provenance / FAIR | W3C PROV-JSON in every signed proof; CITATION.cff; .zenodo.json | ✅ shipped |
| Safety-critical certification | None today | ➕ open |
| Compliance (NIST/FedRAMP) | Pattern-aligned (signed evidence) but no formal mapping | ➕ open |
| Multimodal data | HDF5 via The Well; Piovra-style adapter pattern (Kimera-side) | 🔄 partial |
| Statistical methodology | OFAMIN pillars + measurement-machinery tier with 7 cross-framework validations | ✅ shipped |
| Publication / citation | JOSS-ready paper, paper-build CI, Zenodo workflow, CITATION.cff | 🔄 owner-physical |

---

## IV. Next-direction candidates ranked by leverage

A future Claude session deciding where to push:

### Tier 1 — extensions natural to Ophamin's existing positioning

1. **in-toto Attestation emitter** — wrap `EmpiricalProofRecord` in
   an in-toto Statement so Ophamin proofs flow through existing
   SLSA/sigstore tooling. ~50-100 LOC. High interop leverage.
2. **RO-Crate output wrapper** — package signed proofs + provenance
   into Workflow-Run-RO-Crate-shaped artifacts. Integrates with
   6+ workflow systems per the 2024 PLOS One paper. ~100-200 LOC.
3. **OpenLineage emitter** — emit Ophamin scenario runs as
   OpenLineage events. Feeds Airflow / Spark / dbt / Snowflake
   dashboards directly. ~100-150 LOC.
4. **Streaming proof writes** — addresses Kimera's 4-hour-
   campaign-crash data-loss failure mode. **Architectural** — the
   current `EmpiricalProofRecord.sign()` seals at end. Streaming
   would require per-cycle attestation + a manifest signature.
   Real design call, multi-day.

### Tier 2 — adjacencies (broaden Ophamin's audience)

5. **Workflow runner adapters** — Snakemake / Nextflow plugin so
   their pipeline output emits Ophamin signed proofs. Real
   bioinformatics + life-sciences reach.
6. **DICOM ingestion + multimodal Piovra-style adapter** — extend
   `SubstrateUnderTest` for imaging modalities. Opens medical-
   imaging use cases.
7. **R port `ophamin-proof`** — R is the lingua franca of
   statistical methodology. Multi-week effort but high reach.
8. **Property-based fuzz tests via Hypothesis-numpy** — for the
   canonical-form encoder corner-cases. Catches edge cases the
   5 fixtures don't.

### Tier 3 — speculative, owner-territory

9. **DO-178C / ISO 26262 conformance dossier** — Ophamin's signed
   proofs as artifacts in safety-critical verification packages.
   Requires real engagement with avionics / automotive standards
   bodies. Owner-physical decision.
10. **FedRAMP-aligned compliance evidence** — pattern Ophamin's
    proofs as ATO-relevant evidence. Requires 3PAO engagement.
11. **Post-quantum signature surface** — Rekor is already dual-
    signing (ECDSA + ML-DSA) per 2025-2026 sigstore work. Ophamin
    could add a PQ signature surface for long-lived audit trails.
    Speculative; depends on consumer demand.

### Tier 4 — straightforward dev-experience wins (already in
[`STATUS_2026_05_19.md`](STATUS_2026_05_19.md))

12. Windows CI matrix
13. Docker GHCR publishing workflow
14. `.pre-commit-config.yaml`
15. Slim `ophamin-client` package
16. Helm chart / K8s manifests
17. Public benchmark dashboard

---

## V. Honesty about uncertainty

What I'm confident about:
- Ophamin's own positioning (anchored in paper.md / README / code).
- The major OSS tool families and what they do (DVC, MLflow, Snakemake, Nextflow, scipy, PyMC, etc.).
- The Sigstore / SLSA / in-toto relationship (cross-referenced web research).
- W3C PROV-O + RO-Crate provenance ecosystem (cross-referenced).

What I'm less confident about:
- Specific 2026 maturity levels of in-progress standards (SCITT
  IETF draft, post-quantum-Rekor production status). Tracked but
  not pinned.
- The detailed conformance shape of DO-178C / ISO 26262 / IEC 62304
  tool qualification — these are domain-deep + frequently
  proprietary. Cited sources cover the surface.
- Whether OMOP-CDM + DICOM multimodal integration is genuinely
  production-stable in 2026 or still research-stage.

Before acting on any Tier 1-3 recommendation, a future Claude
session should verify the current maturity of the target ecosystem
+ check whether the integration is still considered the
state-of-art.

---

## VI. See also

- [`STATUS_2026_05_19.md`](STATUS_2026_05_19.md) — session-state pin (autonomous-doable + owner-physical).
- [`ELEVATION_ROADMAP_2026_05_16.md`](ELEVATION_ROADMAP_2026_05_16.md) — RFC 0002 phase status table.
- [`paper/paper.md`](https://github.com/IdirBenSlama/Ophamin/blob/main/paper/paper.md) §Statement of need — Ophamin's positioning in its own words.
- [`docs/INTEROP_OVERVIEW.md`](INTEROP_OVERVIEW.md) — 5-layer consumer on-ramp.

## Sources cited

- [Sigstore — OpenSSF](https://openssf.org/tag/sigstore/) — keyless signing background.
- [Software Supply Chain Security Beyond SBOMs: Sigstore, SLSA, and Build Provenance](https://aquilax.ai/blog/supply-chain-artifact-signing-slsa).
- [SLSA in-toto framework relationship](https://slsa.dev/blog/2023/05/in-toto-and-slsa).
- [Provenance tools becoming standard in developer platforms — InfoQ](https://www.infoq.com/news/2025/08/provenance/).
- [Nextflow vs Snakemake 2026 — Tasrie IT](https://tasrieit.com/blog/nextflow-vs-snakemake-2026).
- [Recording provenance of workflow runs with RO-Crate — PLOS One](https://journals.plos.org/plosone/article?id=10.1371%2Fjournal.pone.0309210).
- [The Role of Standards in Safety-Critical QA: ISO 26262, DO-178C, IEC 62304 — Mndwrk](https://www.mndwrk.com/blog/the-role-of-standards-in-safety-critical-qa-navigating-iso-26262-do-178c-and-iec-62304).
- [SPARK vs MISRA C vs Frama-C comparison — AdaCore](https://www.adacore.com/papers/compare-spark-misra-c-frama-c).
- [AdaCore + NVIDIA accelerate ISO 26262 compliance — embedded-computing](https://embeddedcomputing.com/technology/open-source/risc-v-open-source-ip/adacore-nvidia-accelerate-iso-26262-compliance-by-securing-critical-firmware-with-ada-and-spark).
- [NIST 800-53 Compliance Guide [2026] — Isora GRC](https://www.saltycloud.com/blog/nist-800-53-compliance-guide/).
- [FedRAMP ATO requirements based on NIST 800-53 Rev 5 — stackArmor](https://stackarmor.com/fedramp-releases-updates-to-ato-requirements-based-on-nist-sp-800-53-rev-5-for-public-review/).
- [Quantum-proofing Sigstore: A Tale of Three Approaches — Red Hat](https://tldrecap.tech/posts/2026/opensource-securitycon/quantum-proofing-sigstore-post-quantum-cryptography/).
- [Rekor transparency log — Sigstore docs](https://docs.sigstore.dev/logging/overview/).
- [HDF5 vs. Parquet — Oreate AI](https://www.oreateai.com/blog/hdf5-vs-parquet-navigating-the-maze-of-multimodal-data-storage/196c67962d9d249d4ca893c36a80407e).
- [Breaking data silos: DICOM imaging in OMOP CDM — PMC](https://pmc.ncbi.nlm.nih.gov/articles/PMC12451937/).
- [JOSS design and first-year review — PeerJ](https://peerj.com/articles/cs-147/).
- [Tracking Software and Data Citations to Zenodo DOIs — arxiv](https://arxiv.org/pdf/1911.00295).
- [Frama-C](https://frama-c.com/).
- [Post-Quantum-Resilient Audit Evidence for Long-Lived Regulated Systems — arxiv](https://arxiv.org/pdf/2512.00110).
