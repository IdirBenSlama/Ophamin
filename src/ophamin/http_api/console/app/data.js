// Ophamin mock data — GROUNDED IN THE REAL REPO (github.com/IdirBenSlama/Ophamin)
// Real scenario names, real verdicts, real 9-section proof structure.

window.OPHAMIN = (() => {
  // ============================================================
  // Six wheels — REAL module mapping
  // ============================================================
  const wheels = [
    { id: 'seeing',        label: 'SEEING',        triad: 'outer',
      desc: 'substrate adapter · corpus connectors · auto-discovery',
      module: 'src/ophamin/seeing/',
      health: 1.00, color: '#5e9eff' },
    { id: 'measuring',     label: 'MEASURING',     triad: 'outer',
      desc: 'pre-registered claims · O·F·A·M·I·N pillars',
      module: 'src/ophamin/measuring/',
      health: 0.97, color: '#2dd4bf' },
    { id: 'comparing',     label: 'COMPARING',     triad: 'outer',
      desc: 'cross-commit drift over signed proofs',
      module: 'src/ophamin/comparing/',
      health: 0.93, color: '#8b95e8' },
    { id: 'instrumenting', label: 'INSTRUMENTING', triad: 'inner',
      desc: 'wall-time · CPU · RSS · threads · GPU per cycle',
      module: 'src/ophamin/instrumenting/',
      health: 1.00, color: '#ffa726' },
    { id: 'auditing',      label: 'AUDITING',      triad: 'inner',
      desc: 'ruff · bandit · mypy · vulture · radon · pip-audit',
      module: 'src/ophamin/auditing/',
      health: 0.91, color: '#94a3b8' },
    { id: 'reporting',     label: 'REPORTING',     triad: 'inner',
      desc: 'HTML · Markdown · LaTeX renderers with matplotlib',
      module: 'src/ophamin/reporting/',
      health: 1.00, color: '#4ade80' },
  ];

  // ============================================================
  // OFAMIN pillars — REAL backing libraries
  // ============================================================
  const pillars = [
    { id: 'O', name: 'Observability',    library: 'scipy + river',          backing: 'chi-squared GOF + ADWIN/KSWIN drift detectors', validated: 0.94 },
    { id: 'F', name: 'Formal provenance',library: 'prov + MLflow + DVC',    backing: 'W3C PROV-O + run tracking + data versioning',  validated: 1.00 },
    { id: 'A', name: 'Adaptive testing', library: 'numpy (Wald/Howard)',    backing: 'SPRT / mSPRT validated against closed forms',  validated: 0.96 },
    { id: 'M', name: 'Mixed-effects',    library: 'statsmodels',            backing: 'MixedLM + OLS + anova_lm interaction tests',   validated: 0.92 },
    { id: 'I', name: 'Iterative synthesis', library: 'statsmodels',         backing: 'meta_analysis.combine_effects (DerSimonian-Laird)', validated: 0.98 },
    { id: 'N', name: 'N-fold robustness', library: 'scikit-learn',          backing: 'KFold · ShuffleSplit · GroupKFold',            validated: 0.95 },
  ];

  // ============================================================
  // Tiers — REAL: 5 tiers, not 4
  // ============================================================
  const tiers = [
    { id: 'scientific',           label: 'Scientific',           desc: 'claims about substrate behaviour',           color: '#ffa726' },
    { id: 'engineering',          label: 'Engineering',          desc: 'claims about substrate cost',                color: '#7aa3ff' },
    { id: 'philosophical',        label: 'Philosophical',        desc: 'claims about substrate self-model',          color: '#b89dff' },
    { id: 'empirical_deep',       label: 'Empirical-deep',       desc: 'substrate-physics scenarios (Family A–V)',   color: '#2dd4bf' },
    { id: 'measurement_machinery',label: 'Measurement-machinery',desc: 'cross-framework validation of pillars',      color: '#ef5b5b' },
  ];

  // ============================================================
  // Corpora — REAL with real record counts
  // ============================================================
  const corpora = [
    { name: 'offensive-security-corpus', n: 4416305, kind: 'adversarial_corpus',
      source: 'metasploit-framework + SecLists + PayloadsAllTheThings + nuclei-templates + atomic-red-team + exploit-db + garak + prompt-injection / jailbreak sets',
      hash: '83109a27c3df2a45b912398b969fa8f7250b3d04dee11916d73ecf679d828010' },
    { name: 'enron-email',  n: 517431,  kind: 'organizational_corpus', source: 'CMU Enron email release', hash: 'a3f44b6c…' },
    { name: 'flores-200',   n: 204000,  kind: 'parallel_text',         source: 'NLLB FLORES-200',         hash: 'c2e1a39d…' },
    { name: 'linux-kernel', n: 1414235, kind: 'commit_history',        source: 'Linux kernel (blobless bare clone)', hash: '7b6d2901…' },
    { name: 'kimera-self',  n: 2841,    kind: 'structural_walk',       source: 'Kimera substrate self-introspect',  hash: '4f1c8b22…' },
    { name: 'prime-trajectory-200', n: 200, kind: 'substrate_trajectory', source: 'captured Kimera prime apparatus', hash: 'd5e0a7f1…' },
    { name: 'takwin-trajectory', n: 500, kind: 'substrate_trajectory', source: 'captured Takwin cycle trace', hash: '9c2bf088…' },
  ];

  // ============================================================
  // Scenarios — REAL, from the repo (33 total across 5 tiers)
  // ============================================================
  function s(tier, name, target, corpus_name, claim, claim_meta) {
    return {
      name, tier, family: claim_meta.family,
      target, corpus_name,
      goal: claim.statement,
      method: claim_meta.method,
      falsification_consequence: claim_meta.falsification_consequence,
      explanation: claim_meta.explanation || claim.statement,
      claim_available: true,
      claim,
    };
  }

  const scenarios = [
    // ─── Scientific tier ───────────────────────────────────────
    s('scientific', 'concentrated-immune-siege', 'entity', 'offensive-security-corpus',
      { statement: "Kimera's GWF blocks ≤ 10% of benign-labelled inputs under a concentrated immune siege.",
        operationalization: 'fraction of benign-labelled corpus records for which the GWF returns a blocking verdict',
        threshold: { metric: 'gwf_false_positive_rate', comparator: '<=', value: 0.10, units: 'fraction' },
        h0: 'GWF false-positive rate > 0.10',
        h1: 'GWF false-positive rate <= 0.10' },
      { family: 'immune', method: 'streaming labelled-corpus probe', falsification_consequence: 'GWF discriminator is over-conservative; immune-system architecture re-thinks itself.' }),
    s('scientific', 'rosetta-scaling', 'rosetta', 'flores-200',
      { statement: 'Rosetta canonical-agreement across 10 languages ≥ 80%.',
        operationalization: 'pairwise canonical-form agreement across language pairs',
        threshold: { metric: 'canonical_agreement', comparator: '>=', value: 0.80, units: 'fraction' },
        h0: 'agreement < 0.80', h1: 'agreement ≥ 0.80' },
      { family: 'language', method: 'parallel-corpus oracle', falsification_consequence: 'Rosetta does not generalize across languages — canonicalization is locale-bound.' }),
    s('scientific', 'organizational-dissonance', 'entity', 'enron-email',
      { statement: 'Dissonance fires on ≥ 90% of GWF-cleared cycles in the Enron corpus.',
        operationalization: 'dissonance_active_rate conditioned on gwf_cleared',
        threshold: { metric: 'dissonance_active_rate_on_cleared', comparator: '>=', value: 0.90, units: 'fraction' },
        h0: 'rate < 0.90', h1: 'rate ≥ 0.90' },
      { family: 'organizational', method: 'conditional rate', falsification_consequence: 'Dissonance layer is silent on GWF-cleared inputs.' }),
    s('scientific', 'logic-topology-siege', 'entity', 'linux-kernel',
      { statement: 'Walker sustained-traversal rate ≥ 60% on Linux-kernel commit graph.',
        operationalization: 'fraction of GWF-cleared cycles where walker sustains traversal ≥ N hops',
        threshold: { metric: 'sustained_traversal_rate_on_cleared', comparator: '>=', value: 0.60, units: 'fraction' },
        h0: 'rate < 0.60', h1: 'rate ≥ 0.60' },
      { family: 'topology', method: 'graph-walk oracle', falsification_consequence: 'Walker collapses under real commit-graph topology.' }),
    s('scientific', 'interface-contract-stability', 'entity', 'kimera-self',
      { statement: 'OrchestratorResult field-contract violations ≤ 2 per probe.',
        operationalization: 'count of missing/mistyped fields per OrchestratorResult instance',
        threshold: { metric: 'field_contract_violations', comparator: '<=', value: 2, units: 'count' },
        h0: 'violations > 2', h1: 'violations ≤ 2' },
      { family: 'contract', method: 'structural introspect', falsification_consequence: 'Substrate breaks its own interface contract.' }),
    s('scientific', 'substrate-completeness', 'entity', 'kimera-self',
      { statement: 'Aggregate orphan rate ≤ 20% in kimera_swm/ canonical-name files.',
        operationalization: 'orphans / (orphans + wired) across canonical-named modules',
        threshold: { metric: 'orphan_rate', comparator: '<=', value: 0.20, units: 'fraction' },
        h0: 'rate > 0.20', h1: 'rate ≤ 0.20' },
      { family: 'completeness', method: 'wiring oracle', falsification_consequence: 'Substrate has hidden dead code at canonical names.' }),
    s('scientific', 'memory-as-deformation', 'entity', 'takwin-trajectory',
      { statement: 'Concept-set Jaccard floor ≥ 0.80 across re-exposure pairs.',
        operationalization: 'min pairwise Jaccard over re-exposure rounds',
        threshold: { metric: 'jaccard_floor', comparator: '>=', value: 0.80, units: 'fraction' },
        h0: 'floor < 0.80', h1: 'floor ≥ 0.80' },
      { family: 'memory', method: 'set-overlap oracle', falsification_consequence: 'Memory drifts under re-exposure.' }),

    // ─── Engineering tier ──────────────────────────────────────
    s('engineering', 'throughput-ceiling', 'entity', 'offensive-security-corpus',
      { statement: 'p95 per-cycle wall-time ≤ 4.0 seconds under sustained load.',
        operationalization: '95th percentile of per-cycle wall-time across the streamed batch',
        threshold: { metric: 'p95_cycle_wall_time_s', comparator: '<=', value: 4.0, units: 'seconds' },
        h0: 'p95 > 4.0s', h1: 'p95 ≤ 4.0s' },
      { family: 'performance', method: 'instrumented wall-time sampling', falsification_consequence: 'Substrate exceeds its architectural throughput ceiling.' }),

    // ─── Philosophical tier ────────────────────────────────────
    s('philosophical', 'philosophical-self-reference', 'entity', 'enron-email',
      { statement: "Cohen's d ≥ 0.30 (self-ref dissonance > neutral).",
        operationalization: "Cohen's d on paired dissonance scores (self-ref vs. neutral)",
        threshold: { metric: 'cohens_d', comparator: '>=', value: 0.30, units: 'effect_size' },
        h0: 'd < 0.30', h1: 'd ≥ 0.30' },
      { family: 'self_model', method: 'paired effect-size', falsification_consequence: 'Substrate does not differentiate self-reference from neutral.' }),

    // ─── Empirical-deep tier ───────────────────────────────────
    s('empirical_deep', 'bayesian-phi-posterior', 'entity', 'prime-trajectory-200',
      { statement: 'HDI contraction ratio < theoretical-frequentist bound.',
        operationalization: 'Bayesian HDI width / frequentist CI width',
        threshold: { metric: 'hdi_contraction_ratio', comparator: '<', value: 1.0, units: 'ratio' },
        h0: 'ratio ≥ 1.0', h1: 'ratio < 1.0' },
      { family: 'bayesian_phi', method: 'PyMC NUTS posterior', falsification_consequence: 'Φ posterior is no tighter than frequentist baseline.' }),
    s('empirical_deep', 'causal-discovery', 'entity', 'takwin-trajectory',
      { statement: '≥ 1 directed causal link recovered above α level by Tigramite PCMCI.',
        operationalization: 'count of significant directed links from PCMCI',
        threshold: { metric: 'directed_link_count', comparator: '>=', value: 1, units: 'count' },
        h0: 'count < 1', h1: 'count ≥ 1' },
      { family: 'causal', method: 'PCMCI', falsification_consequence: 'No discoverable causal structure in multi-channel trace.' }),
    s('empirical_deep', 'cross-channel-mutual-information', 'entity', 'takwin-trajectory',
      { statement: '≥ 1 channel pair above 0.05-nat MI floor.',
        operationalization: 'count of pairs with MI ≥ 0.05 nat',
        threshold: { metric: 'mi_pairs_above_floor', comparator: '>=', value: 1, units: 'count' },
        h0: 'count < 1', h1: 'count ≥ 1' },
      { family: 'information', method: 'pyitlib + ennemi cross-check', falsification_consequence: 'Channels are independent at this resolution.' }),
    s('empirical_deep', 'prime-structure', 'entity', 'prime-trajectory-200',
      { statement: 'Concept-Jaccard floor ≥ 0.80, divisibility 100%.',
        operationalization: 'min pairwise Jaccard + divisibility test',
        threshold: { metric: 'jaccard_floor', comparator: '>=', value: 0.80, units: 'fraction' },
        h0: 'floor < 0.80', h1: 'floor ≥ 0.80' },
      { family: 'prime', method: 'set-overlap + divisibility', falsification_consequence: 'Prime apparatus drifts across cycles.' }),
    s('empirical_deep', 'prime-factorization', 'entity', 'prime-trajectory-200',
      { statement: 'p_identity invariance ≥ 99%.',
        operationalization: 'fraction of cycles where p_identity matches expected',
        threshold: { metric: 'p_identity_invariance', comparator: '>=', value: 0.99, units: 'fraction' },
        h0: 'invariance < 0.99', h1: 'invariance ≥ 0.99' },
      { family: 'prime', method: 'identity-invariance oracle', falsification_consequence: 'Factorization is not invariant.' }),
    s('empirical_deep', 'prime-ecosystem', 'entity', 'prime-trajectory-200',
      { statement: 'Alexandria fused-key persistence ≥ 5 keys at ≥ 90% cycles.',
        operationalization: 'count of fused keys persisting across ≥90% cycles',
        threshold: { metric: 'persistent_keys', comparator: '>=', value: 5, units: 'count' },
        h0: 'count < 5', h1: 'count ≥ 5' },
      { family: 'prime', method: 'persistence oracle', falsification_consequence: 'Alexandria does not sustain a stable fused keyspace.' }),
    s('empirical_deep', 'prime-direct-lookup', 'entity', 'prime-trajectory-200',
      { statement: 'Direct ArachneProtocol lookup p_thermo ≥ 99% prime.',
        operationalization: 'fraction of direct lookups returning prime-typed thermo',
        threshold: { metric: 'p_thermo_prime', comparator: '>=', value: 0.99, units: 'fraction' },
        h0: 'rate < 0.99', h1: 'rate ≥ 0.99' },
      { family: 'prime', method: 'protocol-direct lookup', falsification_consequence: 'ArachneProtocol returns non-prime thermo.' }),
    s('empirical_deep', 'prime-cross-instance', 'entity', 'prime-trajectory-200',
      { statement: 'Cross-instance p_identity invariance ≥ 99% across N fresh Takwin processes.',
        operationalization: 'p_identity match-rate across instances',
        threshold: { metric: 'cross_instance_invariance', comparator: '>=', value: 0.99, units: 'fraction' },
        h0: 'rate < 0.99', h1: 'rate ≥ 0.99' },
      { family: 'prime', method: 'multi-instance oracle', falsification_consequence: 'Identity drifts between fresh substrate instances.' }),
    s('empirical_deep', 'quantum-basis-correlation', 'entity', 'takwin-trajectory',
      { statement: 'Content-class effect ≥ 15 percentage-point difference.',
        operationalization: 'partition by stimulus class, measure correlation effect',
        threshold: { metric: 'class_effect_pp', comparator: '>=', value: 15, units: 'percentage_points' },
        h0: 'effect < 15pp', h1: 'effect ≥ 15pp' },
      { family: 'quantum', method: 'class-partitioned correlation', falsification_consequence: 'Quantum-basis is content-independent.' }),
    s('empirical_deep', 'sinew-conservation', 'entity', 'takwin-trajectory',
      { statement: 'Walker M4 conservation ratio ≤ 0.05 under perturbations.',
        operationalization: 'max M4-invariant ratio across perturbation regime',
        threshold: { metric: 'walker_m4_conservation_ratio', comparator: '<=', value: 0.05, units: 'fraction' },
        h0: 'ratio > 0.05', h1: 'ratio ≤ 0.05' },
      { family: 'sinew', method: 'M4 conservation oracle', falsification_consequence: 'Sinew breaks M4 invariant.' }),
    s('empirical_deep', 'sinew-modulation-disruption', 'entity', 'takwin-trajectory',
      { statement: 'Modulation disruption recovery ≤ 12 cycles.',
        operationalization: 'cycle-count to recover post-disruption',
        threshold: { metric: 'recovery_cycles', comparator: '<=', value: 12, units: 'cycles' },
        h0: 'cycles > 12', h1: 'cycles ≤ 12' },
      { family: 'sinew', method: 'recovery-time oracle', falsification_consequence: 'Sinew does not recover within budget.' }),
    s('empirical_deep', 'sinew-wider-unification', 'entity', 'takwin-trajectory',
      { statement: 'Unification ratio ≥ 0.85 across wider sinew topologies.',
        operationalization: 'unification_score over partitioned sinew network',
        threshold: { metric: 'unification_ratio', comparator: '>=', value: 0.85, units: 'fraction' },
        h0: 'ratio < 0.85', h1: 'ratio ≥ 0.85' },
      { family: 'sinew', method: 'unification oracle', falsification_consequence: 'Wider sinew topology fragments.' }),
    s('empirical_deep', 'tonus-conservation-discovery', 'entity', 'takwin-trajectory',
      { statement: 'Tonus conservation invariant holds ≥ 95% of cycles.',
        operationalization: 'fraction of cycles where tonus delta < tol',
        threshold: { metric: 'tonus_conservation_rate', comparator: '>=', value: 0.95, units: 'fraction' },
        h0: 'rate < 0.95', h1: 'rate ≥ 0.95' },
      { family: 'tonus', method: 'invariant-check oracle', falsification_consequence: 'Tonus is not conserved.' }),
    s('empirical_deep', 'proprio-self-discovery', 'entity', 'kimera-self',
      { statement: 'Proprioceptive self-model coverage ≥ 80%.',
        operationalization: 'fraction of substrate fields the proprio-system can name',
        threshold: { metric: 'proprio_coverage', comparator: '>=', value: 0.80, units: 'fraction' },
        h0: 'coverage < 0.80', h1: 'coverage ≥ 0.80' },
      { family: 'proprio', method: 'self-discovery oracle', falsification_consequence: 'Substrate is opaque to itself.' }),

    // ─── Measurement-machinery tier ────────────────────────────
    s('measurement_machinery', 'anova-crosscheck', 'scipy+statsmodels+pingouin', 'synthetic',
      { statement: 'Three ANOVA backends agree on F and p within 1e-9.',
        operationalization: 'max pairwise abs-diff over F and p across backends',
        threshold: { metric: 'max_abs_anova_difference', comparator: '<=', value: 1e-9, units: 'F_or_p' },
        h0: 'diff > 1e-9', h1: 'diff ≤ 1e-9' },
      { family: 'cross_framework', method: 'cross-framework oracle', falsification_consequence: 'scipy / statsmodels / pingouin disagree beyond float epsilon.' }),
    s('measurement_machinery', 'welch-t-crosscheck', 'scipy+statsmodels', 'synthetic',
      { statement: 'scipy and statsmodels Welch-t agree within 1e-9.',
        operationalization: 'max abs-diff of t-statistic across backends',
        threshold: { metric: 'max_abs_t_diff', comparator: '<=', value: 1e-9, units: 't' },
        h0: 'diff > 1e-9', h1: 'diff ≤ 1e-9' },
      { family: 'cross_framework', method: 'cross-framework oracle', falsification_consequence: 'Backends disagree on Welch-t.' }),
    s('measurement_machinery', 'mann-whitney-crosscheck', 'scipy+pingouin', 'synthetic',
      { statement: 'Mann-Whitney U agreement across backends within 1e-9.',
        operationalization: 'max abs-diff of U across scipy/pingouin',
        threshold: { metric: 'max_abs_u_diff', comparator: '<=', value: 1e-9, units: 'U' },
        h0: 'diff > 1e-9', h1: 'diff ≤ 1e-9' },
      { family: 'cross_framework', method: 'cross-framework oracle', falsification_consequence: 'Backends disagree on U.' }),
    s('measurement_machinery', 'pearson-crosscheck', 'scipy+statsmodels+pingouin', 'synthetic',
      { statement: 'Pearson r agreement across backends within 1e-9.',
        operationalization: 'max abs-diff of r over backends',
        threshold: { metric: 'max_abs_r_diff', comparator: '<=', value: 1e-9, units: 'r' },
        h0: 'diff > 1e-9', h1: 'diff ≤ 1e-9' },
      { family: 'cross_framework', method: 'cross-framework oracle', falsification_consequence: 'Backends disagree on r.' }),
    s('measurement_machinery', 'spearman-crosscheck', 'scipy+pingouin', 'synthetic',
      { statement: 'Spearman ρ agreement across backends within 1e-9.',
        operationalization: 'max abs-diff of ρ',
        threshold: { metric: 'max_abs_rho_diff', comparator: '<=', value: 1e-9, units: 'rho' },
        h0: 'diff > 1e-9', h1: 'diff ≤ 1e-9' },
      { family: 'cross_framework', method: 'cross-framework oracle', falsification_consequence: 'Backends disagree on ρ.' }),
    s('measurement_machinery', 'wilson-ci-crosscheck', 'statsmodels', 'synthetic',
      { statement: 'Wilson 95% CI agrees with Newcombe closed form within 1e-9.',
        operationalization: 'max abs-diff of CI bounds',
        threshold: { metric: 'max_abs_ci_diff', comparator: '<=', value: 1e-9, units: 'fraction' },
        h0: 'diff > 1e-9', h1: 'diff ≤ 1e-9' },
      { family: 'cross_framework', method: 'analytical-oracle cross-check', falsification_consequence: 'statsmodels Wilson CI deviates from closed form.' }),
    s('measurement_machinery', 'bayesian-phi-posterior-crosscheck', 'pymc+numpyro+arviz', 'synthetic',
      { statement: 'PyMC and NumPyro Bayesian Φ posteriors agree (Wasserstein < 0.01).',
        operationalization: 'Wasserstein distance between posterior samples',
        threshold: { metric: 'wasserstein_distance', comparator: '<', value: 0.01, units: 'distance' },
        h0: 'd ≥ 0.01', h1: 'd < 0.01' },
      { family: 'cross_framework', method: 'PPL cross-check', falsification_consequence: 'Bayesian backends disagree on Φ posterior shape.' }),
    s('measurement_machinery', 'crdt-laws', 'pycrdt+y-py', 'synthetic',
      { statement: 'Yjs CRDT convergence: 100/100 random sequences converge.',
        operationalization: 'count of converged sequences over 100 random reorderings',
        threshold: { metric: 'converged_sequences', comparator: '==', value: 100, units: 'count' },
        h0: 'converged < 100', h1: 'converged == 100' },
      { family: 'property_test', method: 'CRDT convergence oracle', falsification_consequence: 'CRDT laws violated under reordering.' }),
    s('measurement_machinery', 'deterministic-seed-audit', 'numpy+random', 'synthetic',
      { statement: 'Seeded reruns produce bit-identical outputs.',
        operationalization: 'bit-equality across reruns with same seed',
        threshold: { metric: 'bitwise_diff', comparator: '==', value: 0, units: 'bits' },
        h0: 'diff > 0', h1: 'diff == 0' },
      { family: 'reproducibility', method: 'determinism oracle', falsification_consequence: 'RNG seed does not produce deterministic output.' }),
    s('measurement_machinery', 'sonarqube-scan', 'sonarqube', 'src-tree',
      { statement: 'No MAJOR+ SonarQube issues on src/ophamin/.',
        operationalization: 'count of MAJOR+ issues from SonarQube CLI',
        threshold: { metric: 'major_plus_issues', comparator: '==', value: 0, units: 'issues' },
        h0: 'issues > 0', h1: 'issues == 0' },
      { family: 'static_analysis', method: 'SonarQube oracle', falsification_consequence: 'MAJOR+ issues present in src.' }),
  ];

  // ============================================================
  // Bundles — REAL: from the actual proofs/ tree, with real
  // verdicts. The README table is gold for these.
  // ============================================================
  const allFormats = ['proof.json', 'proof.md', 'proof.html', 'proof.tex', 'proof.pdf'];
  const noPdf      = ['proof.json', 'proof.md', 'proof.html', 'proof.tex'];

  const bundleSpec = [
    // [tier, scenario, date, verdict, hash, files, observed, threshold, ci_low, ci_high]
    // ─── Real proofs from the repo's proofs/ tree ─────────────
    ['scientific', 'concentrated-immune-siege', '2026-05-16', 'validated',    '6d47d8c9a2de', allFormats, 0.032, 0.10, 0.01979, 0.05134],
    ['scientific', 'concentrated-immune-siege', '2026-05-16', 'refuted',      '776d02f2497a', allFormats, 0.158, 0.10, 0.1287,  0.1926],
    ['scientific', 'concentrated-immune-siege', '2026-05-15', 'validated',    'd030c48f4d6f', allFormats, 0.032, 0.10, 0.0198,  0.0513],
    ['scientific', 'concentrated-immune-siege', '2026-05-15', 'validated',    '0a0575db92c0', allFormats, 0.034, 0.10, 0.0210,  0.0540],
    ['scientific', 'concentrated-immune-siege', '2026-05-15', 'refuted',      'be023fabe6b1', allFormats, 0.142, 0.10, 0.1140,  0.1758],
    ['scientific', 'concentrated-immune-siege', '2026-05-14', 'refuted',      '027ace2fba81', allFormats, 0.124, 0.10, 0.0978,  0.1546],
    ['scientific', 'concentrated-immune-siege', '2026-05-14', 'refuted',      '1f957bda5285', allFormats, 0.118, 0.10, 0.0926,  0.1480],
    ['scientific', 'concentrated-immune-siege', '2026-05-14', 'inconclusive', '4f8a2ffd29ed', allFormats, 0.094, 0.10, 0.0710,  0.1227],
    ['scientific', 'logic-topology-siege',      '2026-05-16', 'refuted',      '94e389abcd63', allFormats, 0.396, 0.60, 0.3601,  0.4329],
    ['scientific', 'logic-topology-siege',      '2026-05-15', 'refuted',      '19b0e547908e', allFormats, 0.412, 0.60, 0.3764,  0.4491],
    ['scientific', 'organizational-dissonance', '2026-05-15', 'validated',    'b71961a6e5fb', allFormats, 0.974, 0.90, 0.9619,  0.9826],
    ['scientific', 'rosetta-scaling',           '2026-05-13', 'refuted',      '8a91e2bc4f10', noPdf,      0.00,  0.80, 0.00,    0.16],
    ['scientific', 'memory-as-deformation',     '2026-05-12', 'validated',    'cd4f7a890e22', allFormats, 1.00,  0.80, 1.00,    1.00],
    ['scientific', 'substrate-completeness',    '2026-05-11', 'validated',    'b22c0418afe1', allFormats, 0.0805, 0.20, 0.0555,  0.1153],
    ['scientific', 'interface-contract-stability', '2026-05-10', 'validated', '7c8b1ee03d2a', allFormats, 1,     2,   1,       1],

    // Engineering tier
    ['engineering', 'throughput-ceiling', '2026-05-15', 'validated',    '69197dbcb7cc', allFormats, 2.357, 4.00, null, null],
    ['engineering', 'throughput-ceiling', '2026-05-15', 'inconclusive', 'bb5e9af1dd08', allFormats, 3.812, 4.00, null, null],
    ['engineering', 'throughput-ceiling', '2026-05-14', 'validated',    '9989f42bc8f2', allFormats, 2.491, 4.00, null, null],

    // Philosophical tier
    ['philosophical', 'philosophical-self-reference', '2026-05-15', 'refuted', '95588bfe0b13', allFormats, -0.359, 0.30, null, null],

    // Empirical-deep tier — synthesized but realistic
    ['empirical_deep', 'bayesian-phi-posterior',          '2026-05-17', 'validated', 'f3a2901c4ed1', allFormats, 0.42, 1.00, null, null],
    ['empirical_deep', 'causal-discovery',                '2026-05-17', 'validated', 'a91b2c3d4e5f', allFormats, 32,   1,    null, null],
    ['empirical_deep', 'cross-channel-mutual-information','2026-05-17', 'validated', 'b2c3d4e5f607', allFormats, 8,    1,    null, null],
    ['empirical_deep', 'prime-structure',                 '2026-05-16', 'validated', 'c3d4e5f60718', allFormats, 1.00, 0.80, null, null],
    ['empirical_deep', 'prime-factorization',             '2026-05-16', 'validated', 'd4e5f6071829', allFormats, 1.00, 0.99, null, null],
    ['empirical_deep', 'prime-ecosystem',                 '2026-05-16', 'validated', 'e5f60718293a', allFormats, 12,   5,    null, null],
    ['empirical_deep', 'prime-direct-lookup',             '2026-05-16', 'validated', 'f60718293a4b', allFormats, 1.00, 0.99, null, null],
    ['empirical_deep', 'prime-cross-instance',            '2026-05-15', 'validated', '0718293a4b5c', allFormats, 1.00, 0.99, null, null],
    ['empirical_deep', 'quantum-basis-correlation',       '2026-05-15', 'validated', '18293a4b5c6d', allFormats, 39,   15,   null, null],
    ['empirical_deep', 'sinew-conservation',              '2026-05-14', 'refuted',   '293a4b5c6d7e', allFormats, 0.087, 0.05, 0.074, 0.112],
    ['empirical_deep', 'sinew-modulation-disruption',     '2026-05-14', 'validated', '3a4b5c6d7e8f', allFormats, 8,    12,   null, null],
    ['empirical_deep', 'tonus-conservation-discovery',    '2026-05-13', 'inconclusive','4b5c6d7e8f90', noPdf,    0.948, 0.95, 0.940, 0.957],

    // Measurement-machinery tier
    ['measurement_machinery', 'anova-crosscheck',                  '2026-05-18', 'validated', 'b0fcc417fb50', allFormats, 4e-12, 1e-9, null, null],
    ['measurement_machinery', 'welch-t-crosscheck',                '2026-05-18', 'validated', '5c6f481298cb', allFormats, 7e-13, 1e-9, null, null],
    ['measurement_machinery', 'mann-whitney-crosscheck',           '2026-05-18', 'validated', 'e71be64487df', allFormats, 2e-12, 1e-9, null, null],
    ['measurement_machinery', 'pearson-crosscheck',                '2026-05-18', 'validated', '7b2498c19370', allFormats, 3e-13, 1e-9, null, null],
    ['measurement_machinery', 'spearman-crosscheck',               '2026-05-18', 'validated', 'f65319cb2ab7', allFormats, 6e-13, 1e-9, null, null],
    ['measurement_machinery', 'wilson-ci-crosscheck',              '2026-05-18', 'validated', '80d5b9f33fba', allFormats, 1e-12, 1e-9, null, null],
    ['measurement_machinery', 'bayesian-phi-posterior-crosscheck', '2026-05-18', 'validated', 'aae6cf83833b', allFormats, 0.007, 0.01, null, null],
    ['measurement_machinery', 'crdt-laws',                         '2026-05-12', 'validated', '5c6d7e8f9012', allFormats, 100, 100, null, null],
  ];

  const bundles = bundleSpec.map(([tier, scenario, date, verdict, short_hash, files, observed, threshold, ci_low, ci_high]) => ({
    tier, scenario, date, verdict, short_hash, files,
    path: `${tier}/${scenario}/${date}_${verdict}_${short_hash}`,
    observed,
    threshold,
    ci: [ci_low, ci_high],
    proof_id: short_hash + 'ef83a11608a5b3302e69a20386821e87d2d4db0418d820463f7b'.slice(0, 52),
  }));

  // ============================================================
  // Totals
  // ============================================================
  const totals = {
    tiers: tiers.length,
    scenarios: scenarios.length,
    bundles: bundles.length,
    verdicts: {
      validated:    bundles.filter(b => b.verdict === 'validated').length,
      refuted:      bundles.filter(b => b.verdict === 'refuted').length,
      inconclusive: bundles.filter(b => b.verdict === 'inconclusive').length,
    }
  };

  // ============================================================
  // Build a REAL 9-section proof bundle for a given bundle.
  // Matches the actual repo proof.json shape.
  // ============================================================
  function buildProof(bundle) {
    // Live wiring: when hydrate() has attached the real on-disk
    // EmpiricalProofRecord (fetched from /proofs/bundles/file), render
    // THAT verbatim instead of the synthetic mock. The mock shape below
    // was modeled on the real proof.json (identical top-level keys), so
    // the proof-detail view renders either faithfully.
    if (bundle && bundle._realProof) return bundle._realProof;
    const scn = scenarios.find(s => s.name === bundle.scenario);
    const corpus = corpora.find(c => c.name === scn?.corpus_name) || corpora[0];

    // Evidence: invented pillar entries matching the real `O.<domain>.<metric>` naming
    const domain = scn?.family || 'general';
    const evidence = [];
    if (bundle.tier === 'scientific' && bundle.scenario.includes('immune-siege')) {
      evidence.push(
        { pillar: 'O.immune.false_positive', statistic_name: 'gwf_false_positive_rate', statistic_value: bundle.observed, library: 'statsmodels', library_version: '0.14.6', ci_low: bundle.ci[0], ci_high: bundle.ci[1], p_value: null, cross_check: 'n/a', detail: { benign_blocked: Math.round(bundle.observed*500), benign_total: 500, feature_extraction: 'kimera_native', target: 'entity', adapter_errors: 0, ci_method: 'wilson_95' } },
        { pillar: 'O.immune.detection',     statistic_name: 'gwf_detection_rate',      statistic_value: 0.488, library: 'statsmodels', library_version: '0.14.6', ci_low: 0.444, ci_high: 0.532, p_value: null, cross_check: 'n/a', detail: { malicious_blocked: 244, malicious_total: 500, target: 'entity', ci_method: 'wilson_95' } },
        { pillar: 'O.immune.full_stack_false_positive', statistic_name: 'full_stack_false_positive_rate', statistic_value: 0.158, library: 'statsmodels', library_version: '0.14.6', ci_low: 0.129, ci_high: 0.193, p_value: null, cross_check: 'n/a', detail: { benign_caught: 79, benign_total: 500, defense_layers: ['gwf','manipulation_detector','danger_theory_gate'], target: 'entity', ci_method: 'wilson_95' } },
        { pillar: 'O.immune.full_stack_detection',      statistic_name: 'full_stack_detection_rate',      statistic_value: 0.544, library: 'statsmodels', library_version: '0.14.6', ci_low: 0.500, ci_high: 0.587, p_value: null, cross_check: 'n/a', detail: { malicious_caught: 272, malicious_total: 500, defense_layers: ['gwf','manipulation_detector','danger_theory_gate'], target: 'entity', ci_method: 'wilson_95' } },
      );
    } else if (bundle.scenario === 'throughput-ceiling') {
      evidence.push(
        { pillar: 'O.engineering.p95_wall_time', statistic_name: 'p95_cycle_wall_time_s', statistic_value: bundle.observed, library: 'python-stdlib', library_version: '3.14', ci_low: null, ci_high: null, p_value: null, cross_check: 'n/a', detail: { n_cycles_measured: 200, n_cycles_total: 200, adapter_errors: 0, ceiling_s: 4.0 } },
        { pillar: 'O.engineering.wall_time_distribution', statistic_name: 'cycle_wall_time_distribution', statistic_value: 1.010, library: 'python-stdlib', library_version: '3.14', ci_low: null, ci_high: null, p_value: null, cross_check: 'n/a', detail: { n: 200, min: 0.078, max: 3.261, median: 1.010, mean: 1.064, p95: 2.357, p99: 3.020 } },
        { pillar: 'O.engineering.batch_cpu',     statistic_name: 'batch_cpu_total_s', statistic_value: 243.86, library: 'psutil', library_version: '7.x', ci_low: null, ci_high: null, p_value: null, cross_check: 'n/a', detail: { user_s: 215.64, system_s: 28.22, cpu_source: 'periodic_subprocess_sampler', sampler_polls: 1571 } },
        { pillar: 'O.engineering.rss_peak',      statistic_name: 'rss_peak_bytes', statistic_value: 4576722944, library: 'psutil', library_version: '7.x', ci_low: null, ci_high: null, p_value: null, cross_check: 'n/a', detail: { rss_before_bytes: 296075264, rss_after_bytes: 494174208, threads_max: 80, process_count_max: 2 } },
      );
    } else {
      // Generic evidence row
      evidence.push({
        pillar: `O.${domain}.primary`,
        statistic_name: scn?.claim?.threshold?.metric || 'value',
        statistic_value: bundle.observed,
        library: 'statsmodels',
        library_version: '0.14.6',
        ci_low: bundle.ci[0],
        ci_high: bundle.ci[1],
        p_value: bundle.verdict === 'validated' ? 0.002 : bundle.verdict === 'refuted' ? 0.041 : 0.063,
        cross_check: 'n/a',
        detail: { ci_method: bundle.ci[0] != null ? 'wilson_95' : 'n/a' },
      });
    }

    return {
      proof_id: bundle.proof_id,
      schema_version: '1.0',
      identity: {
        ophamin_version: '0.64.1',
        ophamin_git_commit: '3f0763aa468566729f3e2f795cfb5f433457534d',
        created_at: bundle.date + 'T17:33:22.184713+00:00',
      },
      claim: scn?.claim || {},
      preregistration: {
        config_hash: 'sha256:' + bundle.proof_id.slice(0, 64).padEnd(64, '0'),
        data_hash:   corpus.hash,
        analysis_plan: scn?.claim?.operationalization || 'Stream the corpus through the target and apply the claim threshold.',
        sweep_grid: {},
        preregistered_at: bundle.date + 'T17:05:19.498431+00:00',
      },
      data: {
        substrate_name: bundle.scenario === 'throughput-ceiling' ? 'instrumented(kimera-swm)' : 'kimera-swm',
        substrate_git_commit: '4552de7ee80c',
        datasets: [{ name: corpus.name, content_hash: corpus.hash, n_records: corpus.n, source: corpus.source, kind: corpus.kind }],
      },
      evidence,
      verdict: {
        outcome: bundle.verdict.toUpperCase(),
        observed_value: bundle.observed,
        threshold: scn?.claim?.threshold || { metric: 'value', comparator: '<=', value: bundle.threshold, units: 'units' },
        reasoning: buildReasoning(bundle, scn),
      },
      reproduction: {
        command: `PYTHONPATH=src .venv/bin/python -m ophamin.cli scenario ${bundle.scenario}`,
        environment: { python: '3.14.3', platform: 'macOS-26.3.1-arm64-arm-64bit-Mach-O', ophamin: '0.64.1', scipy: '1.17.1', statsmodels: '0.14.6', 'scikit-learn': '1.6.1', numpy: '2.4.4', pandas: '2.3.3' },
        lineage_chain: [],
      },
      provenance: {
        prefix: { ophamin: 'https://ophamin.example/' },
        agent: {
          'ophamin:ophamin':    { 'ophamin:role': 'experimentation_framework', 'ophamin:version': '0.64.1' },
          'ophamin:kimera-swm': { 'ophamin:role': 'substrate_under_test' },
        },
        entity: {
          [`ophamin:corpus_${corpus.name}`]: { 'ophamin:content_hash': corpus.hash, 'ophamin:n_records': corpus.n, 'ophamin:kind': corpus.kind },
          [`ophamin:proof_${bundle.scenario}`]: {},
        },
        activity: { [`ophamin:scenario_${bundle.scenario}`]: { 'ophamin:target': scn?.target || 'entity', 'ophamin:n_cycles': 1000 } },
        used:               { '_:id1': { 'prov:activity': `ophamin:scenario_${bundle.scenario}`, 'prov:entity': `ophamin:corpus_${corpus.name}` } },
        wasAssociatedWith:  { '_:id2': { 'prov:activity': `ophamin:scenario_${bundle.scenario}`, 'prov:agent': 'ophamin:ophamin' }, '_:id3': { 'prov:activity': `ophamin:scenario_${bundle.scenario}`, 'prov:agent': 'ophamin:kimera-swm' } },
        wasGeneratedBy:     { '_:id4': { 'prov:entity': `ophamin:proof_${bundle.scenario}`, 'prov:activity': `ophamin:scenario_${bundle.scenario}` } },
        wasAttributedTo:    { '_:id5': { 'prov:entity': `ophamin:proof_${bundle.scenario}`, 'prov:agent': 'ophamin:kimera-swm' } },
        wasDerivedFrom:     { '_:id6': { 'prov:generatedEntity': `ophamin:proof_${bundle.scenario}`, 'prov:usedEntity': `ophamin:corpus_${corpus.name}` } },
      },
      signature: bundle.proof_id.slice(0, 64).padEnd(64, '0'),
    };
  }

  function buildReasoning(bundle, scn) {
    if (bundle.scenario.includes('immune-siege')) {
      return `GWF blocked ${Math.round(bundle.observed*500)}/500 benign (${(bundle.observed*100).toFixed(1)}% false-positive); detection rate 48.8% on 500 malicious; full defense stack caught 272/500 (54.4%) and 79/500 benign (15.8%); 1000 cycles, 0 adapter errors.`;
    }
    if (bundle.scenario === 'throughput-ceiling') {
      return `measured per-cycle wall-time on 200/200 cycles (0 adapter errors); distribution: median 1.01s, p95 ${bundle.observed.toFixed(2)}s, p99 3.02s; batch totals: wall 221.94s, cpu 243.86s, rss_peak 4577MB, max threads 80.`;
    }
    return `${scn?.method || 'analysis'} — observed ${bundle.observed}, threshold ${scn?.claim?.threshold?.comparator || '<='} ${scn?.claim?.threshold?.value}; verdict: ${bundle.verdict}.`;
  }

  // ============================================================
  // Activity (14-day trend, real)
  // ============================================================
  const activity = [
    { d: '05-06', v: 1 }, { d: '05-07', v: 0 }, { d: '05-08', v: 0 },
    { d: '05-09', v: 0 }, { d: '05-10', v: 1 }, { d: '05-11', v: 1 },
    { d: '05-12', v: 2 }, { d: '05-13', v: 2 }, { d: '05-14', v: 4 },
    { d: '05-15', v: 5 }, { d: '05-16', v: 4 }, { d: '05-17', v: 3 },
    { d: '05-18', v: 8 }, { d: '05-19', v: 2 },
  ];

  // ============================================================
  // Agentic layer — 7 agents (real CLI surfaces)
  // ============================================================
  const agents = [
    { id: 'prereg',       label: 'Prereg validator',  tier: 'reasoning', desc: 'flags whether a claim is actually falsifiable before a run' },
    { id: 'scenario-gen', label: 'Scenario generator',tier: 'coder',     desc: 'scaffolds a Scenario subclass from a claim (leaves score() a stub)' },
    { id: 'adapt',        label: 'Adapter generator', tier: 'coder',     desc: 'generates a Foreign-Corpus adapter module' },
    { id: 'brief',        label: 'Proof brief',       tier: 'workhorse', desc: 'plain-English brief for a signed proof' },
    { id: 'triage',       label: 'Refuted triage',    tier: 'reasoning', desc: 'proposes follow-up scenarios for a REFUTED proof' },
    { id: 'confounds',    label: 'Confound enumerator', tier: 'reasoning', desc: 'red-teams a VALIDATED proof — alternative explanations' },
    { id: 'query',        label: 'Bundle query',      tier: 'fast',      desc: 'natural-language query over the proof-bundle tree' },
  ];

  // ============================================================
  // Prometheus metrics (real names from src/ophamin/http_api/metrics.py)
  // ============================================================
  const metricsText = `# HELP ophamin_http_requests_total Total HTTP requests served
# TYPE ophamin_http_requests_total counter
ophamin_http_requests_total{method="GET",path="/health"} 4128
ophamin_http_requests_total{method="GET",path="/version"} 1842
ophamin_http_requests_total{method="GET",path="/scenarios"} 941
ophamin_http_requests_total{method="GET",path="/proofs/bundles/tree"} 1276
ophamin_http_requests_total{method="GET",path="/proofs/bundles/file"} 3812
ophamin_http_requests_total{method="GET",path="/metrics"} 982
ophamin_http_requests_total{method="POST",path="/scenarios/{name}/run"} ${totals.bundles}

# HELP ophamin_http_request_duration_seconds Histogram of HTTP latency
# TYPE ophamin_http_request_duration_seconds histogram
ophamin_http_request_duration_seconds_bucket{le="0.005"} 5102
ophamin_http_request_duration_seconds_bucket{le="0.01"} 9612
ophamin_http_request_duration_seconds_bucket{le="0.025"} 11209
ophamin_http_request_duration_seconds_bucket{le="0.05"} 12640
ophamin_http_request_duration_seconds_bucket{le="0.1"} 12892
ophamin_http_request_duration_seconds_bucket{le="0.5"} 13001
ophamin_http_request_duration_seconds_bucket{le="+Inf"} 13014

# HELP ophamin_proof_bundles_total Total proof bundles indexed
# TYPE ophamin_proof_bundles_total gauge
ophamin_proof_bundles_total ${totals.bundles}

# HELP ophamin_proof_bundles_by_tier Bundles partitioned by tier
# TYPE ophamin_proof_bundles_by_tier gauge
ophamin_proof_bundles_by_tier{tier="scientific"} ${bundles.filter(b => b.tier === 'scientific').length}
ophamin_proof_bundles_by_tier{tier="engineering"} ${bundles.filter(b => b.tier === 'engineering').length}
ophamin_proof_bundles_by_tier{tier="philosophical"} ${bundles.filter(b => b.tier === 'philosophical').length}
ophamin_proof_bundles_by_tier{tier="empirical_deep"} ${bundles.filter(b => b.tier === 'empirical_deep').length}
ophamin_proof_bundles_by_tier{tier="measurement_machinery"} ${bundles.filter(b => b.tier === 'measurement_machinery').length}

# HELP ophamin_proof_verdicts Bundles partitioned by verdict
# TYPE ophamin_proof_verdicts gauge
ophamin_proof_verdicts{verdict="validated"} ${totals.verdicts.validated}
ophamin_proof_verdicts{verdict="refuted"} ${totals.verdicts.refuted}
ophamin_proof_verdicts{verdict="inconclusive"} ${totals.verdicts.inconclusive}

# HELP ophamin_proof_latest_timestamp Unix timestamp of newest bundle
# TYPE ophamin_proof_latest_timestamp gauge
ophamin_proof_latest_timestamp 1747756840

# HELP ophamin_proof_bundle_storage_bytes Total disk usage for bundles
# TYPE ophamin_proof_bundle_storage_bytes gauge
ophamin_proof_bundle_storage_bytes 53477376

# HELP ophamin_scenarios_registered Scenarios registered
# TYPE ophamin_scenarios_registered gauge
ophamin_scenarios_registered ${totals.scenarios}

# HELP ophamin_scenarios_registered_by_tier Scenarios by tier
# TYPE ophamin_scenarios_registered_by_tier gauge
ophamin_scenarios_registered_by_tier{tier="scientific"} 7
ophamin_scenarios_registered_by_tier{tier="engineering"} 1
ophamin_scenarios_registered_by_tier{tier="philosophical"} 1
ophamin_scenarios_registered_by_tier{tier="empirical_deep"} 15
ophamin_scenarios_registered_by_tier{tier="measurement_machinery"} 10

# HELP ophamin_process_cpu_seconds_total CPU seconds consumed
# TYPE ophamin_process_cpu_seconds_total counter
ophamin_process_cpu_seconds_total 1142.31

# HELP ophamin_process_resident_memory_bytes Resident memory
# TYPE ophamin_process_resident_memory_bytes gauge
ophamin_process_resident_memory_bytes 184549376

# HELP ophamin_process_threads Number of OS threads
# TYPE ophamin_process_threads gauge
ophamin_process_threads 14

# HELP ophamin_process_open_fds Number of open file descriptors
# TYPE ophamin_process_open_fds gauge
ophamin_process_open_fds 38

# HELP ophamin_uptime_seconds Process uptime
# TYPE ophamin_uptime_seconds counter
ophamin_uptime_seconds 184321

# HELP ophamin_health 1 = healthy
# TYPE ophamin_health gauge
ophamin_health 1

# HELP ophamin_disk_free_bytes Free space on bundle volume
# TYPE ophamin_disk_free_bytes gauge
ophamin_disk_free_bytes 184943587328

# HELP ophamin_build_info Build / runtime info
# TYPE ophamin_build_info gauge
ophamin_build_info{version="0.64.1",commit="3f0763a",python="3.14.3"} 1
`;

  function formatThreshold(t) {
    if (!t) return '—';
    return `${t.metric} ${t.comparator} ${t.value} ${t.units}`;
  }

  // Family taxonomy — mirrors EMPIRICAL_VALIDATION.md per-scenario family letters
  const SCENARIO_FAMILY = {
    'concentrated-immune-siege': 'V',  'rosetta-scaling': 'R',
    'organizational-dissonance': 'O',  'logic-topology-siege': 'L',
    'interface-contract-stability': 'I', 'substrate-completeness': 'C',
    'memory-as-deformation': 'M',      'throughput-ceiling': 'T',
    'philosophical-self-reference': 'P', 'bayesian-phi-posterior': 'T',
    'causal-discovery': 'F', 'cross-channel-mutual-information': 'T',
    'prime-structure': 'U', 'prime-factorization': 'U', 'prime-ecosystem': 'U',
    'prime-direct-lookup': 'U', 'prime-cross-instance': 'U',
    'quantum-basis-correlation': 'J', 'sinew-conservation': 'S',
    'sinew-modulation-disruption': 'S', 'sinew-wider-unification': 'S',
    'tonus-conservation-discovery': 'TN', 'proprio-self-discovery': 'PR',
    'anova-crosscheck': 'EE', 'welch-t-crosscheck': 'EE', 'mann-whitney-crosscheck': 'EE',
    'pearson-crosscheck': 'EE', 'spearman-crosscheck': 'EE', 'wilson-ci-crosscheck': 'EE',
    'bayesian-phi-posterior-crosscheck': 'EE', 'crdt-laws': 'EE',
    'deterministic-seed-audit': 'EE', 'sonarqube-scan': 'EE',
  };
  // Per-bundle substrate_git_commit — matches the real proof.json shape.
  // Earlier dates were on 4552de7e; the BGE-M3 swap (6e4477eb) shows up
  // for any bundle dated >= 2026-05-17.
  bundles.forEach(b => {
    b.substrate_git_commit = b.date >= '2026-05-17' ? '6e4477eb'
                            : b.date >= '2026-05-13' ? '179edd23'
                            : '4552de7e';
  });
  // substrate_git_commit_per_bundle marker
  bundles.forEach(b => { b.family = SCENARIO_FAMILY[b.scenario] || '?'; });
  scenarios.forEach(s => { s.familyLetter = SCENARIO_FAMILY[s.name] || '?'; });

  // Phase C: substrate-state-stamps with annotations
  const substrateStamps = [
    { commit: '4552de7e', range: '2026-05-10 → 2026-05-12', label: 'Stage 39 baseline',          note: 'cross-modal coherence baseline' },
    { commit: '179edd23', range: '2026-05-13 → 2026-05-16', label: 'GWF threshold tuning',       note: 'concentrated-immune-siege flipped here' },
    { commit: '6e4477eb', range: '2026-05-17 → present',    label: 'BGE-M3 watershed',           note: 'FastText eradicated; roadmap re-baseline opens' },
  ];

  // ============================================================
  // Live wiring — overlay real REST data onto the grounded mock.
  //
  // hydrate(apiBase) fetches the live Ophamin HTTP surface and
  // overwrites the screen-backing fields IN PLACE on `api`:
  //   /version             -> api.version
  //   /scenarios           -> api.scenarios   (merged; mock claims kept)
  //   /proofs/bundles/tree -> api.bundles + api.totals (flattened)
  //   /proofs/bundles/file -> bundle._realProof (real signed proof.json)
  //   /metrics             -> api.metricsText
  //
  // Every endpoint is independently guarded: a failed or empty fetch
  // leaves that slice as the grounded mock, so the console renders
  // fully whether it is talking to a live server, a fresh instance
  // with no proofs yet, or opened straight off disk (file://).
  // ============================================================
  const MAX_PROOF_PREFETCH = 120;

  async function hydrate(apiBase) {
    apiBase = apiBase || '';
    const live = api.live;

    const getJSON = async (path) => {
      const r = await fetch(apiBase + path, { headers: { accept: 'application/json' } });
      if (!r.ok) throw new Error(path + ' -> HTTP ' + r.status);
      return r.json();
    };
    const getText = async (path) => {
      const r = await fetch(apiBase + path);
      if (!r.ok) throw new Error(path + ' -> HTTP ' + r.status);
      return r.text();
    };

    // --- /version ------------------------------------------------
    try {
      const v = await getJSON('/version');
      if (v && v.framework_version) { api.version = v.framework_version; live.version = true; }
    } catch (e) { console.warn('[ophamin] hydrate /version skipped:', e.message); }

    // --- /scenarios (merge; preserve mock falsifiable claims) ----
    try {
      const s = await getJSON('/scenarios');
      if (s && Array.isArray(s.scenarios) && s.scenarios.length) {
        const mockByName = {};
        scenarios.forEach((sc) => { mockByName[sc.name] = sc; });
        api.scenarios = s.scenarios.map((rs) => {
          const m = mockByName[rs.name];
          return {
            name: rs.name,
            tier: rs.tier || (m && m.tier) || 'scientific',
            family: rs.family || (m && m.family) || '',
            target: rs.target || (m && m.target) || 'entity',
            corpus_name: rs.corpus_name || (m && m.corpus_name) || '',
            goal: rs.goal || (m && m.goal) || '',
            method: rs.method || (m && m.method) || '',
            falsification_consequence:
              rs.falsification_consequence || (m && m.falsification_consequence) || '',
            explanation: rs.explanation || (m && m.explanation) || '',
            // The claim five-tuple isn't carried by the list endpoint;
            // keep the mock's claim when present so the Run / Scenarios
            // threshold previews stay populated. New scenarios with no
            // mock counterpart are flagged claim-unavailable.
            claim_available: !!(m && m.claim_available),
            claim: (m && m.claim) || null,
          };
        });
        api.totals = Object.assign({}, api.totals, { scenarios: api.scenarios.length });
        live.scenarios = true;
      }
    } catch (e) { console.warn('[ophamin] hydrate /scenarios skipped:', e.message); }

    // --- /proofs/bundles/tree (flatten -> bundle rows) -----------
    let liveBundles = null;
    try {
      const t = await getJSON('/proofs/bundles/tree');
      const flat = [];
      (t.tiers || []).forEach((tr) =>
        (tr.scenarios || []).forEach((scn) =>
          (scn.bundles || []).forEach((b) => {
            flat.push({
              tier: tr.tier,
              scenario: scn.scenario,
              date: b.date,
              verdict: b.verdict,
              short_hash: b.short_hash,
              files: b.files || [],
              path: b.path,
              bundle_dir: String(b.path || '').split('/').pop(),
              observed: null,
              threshold: null,
              ci: [null, null],
              proof_id: (b.short_hash || '') + '…',
              _live: true,
            });
          })));
      if (flat.length) {
        flat.sort((a, b) => String(b.date).localeCompare(String(a.date)));
        api.bundles = flat;
        liveBundles = flat;
        const vc = (t.totals && t.totals.verdicts) || flat.reduce((acc, b) => {
          acc[b.verdict] = (acc[b.verdict] || 0) + 1; return acc;
        }, {});
        api.totals = {
          tiers: (t.totals && t.totals.tiers) || new Set(flat.map((b) => b.tier)).size,
          scenarios: api.scenarios.length,
          bundles: flat.length,
          verdicts: {
            validated: vc.validated || 0,
            refuted: vc.refuted || 0,
            inconclusive: vc.inconclusive || 0,
          },
        };
        live.bundles = true;
      }
    } catch (e) { console.warn('[ophamin] hydrate /proofs/bundles/tree skipped:', e.message); }

    // --- /proofs/bundles/file (attach the REAL signed proof.json) -
    // Prefetch the on-disk EmpiricalProofRecord for each live bundle
    // (capped) so the Proofs detail view shows the real signed record
    // and the bundle rows carry real observed / threshold / ci values.
    if (liveBundles && liveBundles.length) {
      const targets = liveBundles.slice(0, MAX_PROOF_PREFETCH);
      const settled = await Promise.allSettled(targets.map(async (b) => {
        if (!(b.files || []).includes('proof.json')) return;
        const qs = new URLSearchParams({
          tier: b.tier, scenario: b.scenario, bundle: b.bundle_dir, filename: 'proof.json',
        }).toString();
        const r = await fetch(apiBase + '/proofs/bundles/file?' + qs);
        if (!r.ok) return;
        const proof = await r.json();
        b._realProof = proof;
        b.proof_id = proof.proof_id || b.proof_id;
        if (proof.verdict) {
          if (typeof proof.verdict.observed_value === 'number') b.observed = proof.verdict.observed_value;
          if (proof.verdict.threshold && typeof proof.verdict.threshold.value === 'number') {
            b.threshold = proof.verdict.threshold.value;
          }
          if (proof.verdict.outcome) b.verdict = String(proof.verdict.outcome).toLowerCase();
        }
        const ev0 = (proof.evidence || [])[0];
        if (ev0 && (ev0.ci_low != null || ev0.ci_high != null)) b.ci = [ev0.ci_low, ev0.ci_high];
        const pdata = proof.data || {};
        if (pdata.substrate_name) b.substrate_name = pdata.substrate_name;
        if (pdata.substrate_git_commit) b.substrate_commit = pdata.substrate_git_commit;
      }));
      if (settled.some((r) => r.status === 'fulfilled')) live.proofs = true;

      // Derive the real substrate catalogue from the prefetched proofs,
      // and keep the full bundle list so the substrate selector can scope
      // the corpus (data-layer filter — every screen that reads
      // api.bundles re-scopes for free).
      api._allBundles = liveBundles;
      const subMap = new Map();
      liveBundles.forEach((b) => {
        const name = b.substrate_name || '(unspecified)';
        const e = subMap.get(name) || { name, bundles: 0, commits: new Set() };
        e.bundles += 1;
        if (b.substrate_commit) e.commits.add(b.substrate_commit);
        subMap.set(name, e);
      });
      if (subMap.size) {
        api.substrates = [...subMap.values()]
          .map((e) => ({
            name: e.name,
            bundles: e.bundles,
            commitCount: e.commits.size,
            commit: e.commits.size === 1 ? String([...e.commits][0]).slice(0, 12) : '',
          }))
          .sort((a, b) => b.bundles - a.bundles);
        live.substrates = true;
      }
    }

    // --- /metrics ------------------------------------------------
    try {
      const m = await getText('/metrics');
      if (m && m.trim().length) { api.metricsText = m; live.metrics = true; }
    } catch (e) { console.warn('[ophamin] hydrate /metrics skipped:', e.message); }

    // --- /agents (merge; keep mock label/desc when richer) -------
    try {
      const a = await getJSON('/agents');
      if (a && Array.isArray(a.agents) && a.agents.length) {
        const mockById = {};
        agents.forEach((ag) => { mockById[ag.id] = ag; });
        api.agents = a.agents.map((ra) => {
          const m = mockById[ra.id];
          return {
            id: ra.id,
            label: ra.label || (m && m.label) || ra.id,
            tier: ra.tier || (m && m.tier) || 'fast',
            desc: ra.desc || (m && m.desc) || '',
            task: ra.task || '',
            cli: ra.cli || ('ophamin agent ' + ra.id),
          };
        });
        live.agents = true;
      }
    } catch (e) { console.warn('[ophamin] hydrate /agents skipped:', e.message); }

    // --- /agents/calls (signed LLM-call audit trail) -------------
    try {
      const c = await getJSON('/agents/calls?limit=200');
      if (c && Array.isArray(c.calls)) {
        api.agentCalls = c.calls;
        live.agentCalls = true;
      }
    } catch (e) { console.warn('[ophamin] hydrate /agents/calls skipped:', e.message); }

    // --- /integrations (external tools the operator wired up) ----
    try {
      const g = await getJSON('/integrations');
      if (g && Array.isArray(g.integrations)) {
        api.integrations = g.integrations;
        live.integrations = true;
      }
    } catch (e) { console.warn('[ophamin] hydrate /integrations skipped:', e.message); }

    // --- /substrate (organ state from the signed proof corpus) ---
    // Note: api.substrate is the active-substrate *name* (status strip);
    // the organ array lives under api.substrate_organs to avoid clashing.
    try {
      const su = await getJSON('/substrate');
      if (su && Array.isArray(su.organs)) {
        api.substrate_organs = su.organs;
        live.substrate_organs = true;
      }
    } catch (e) { console.warn('[ophamin] hydrate /substrate skipped:', e.message); }

    return live;
  }

  // Scope the corpus to one substrate (by name) — the UniFi "console
  // picker". Filters at the data layer + recomputes bundle-derived totals,
  // so Proofs / Overview / Insights (all read api.bundles / api.totals)
  // re-scope without per-screen changes. name=null restores "all".
  function setActiveSubstrate(name) {
    api.activeSubstrate = name || null;
    const src = api._allBundles || api.bundles || [];
    const filtered = name
      ? src.filter((b) => (b.substrate_name || '(unspecified)') === name)
      : src;
    api.bundles = filtered;
    const vc = filtered.reduce((acc, b) => {
      acc[b.verdict] = (acc[b.verdict] || 0) + 1; return acc;
    }, {});
    api.totals = Object.assign({}, api.totals, {
      bundles: filtered.length,
      verdicts: {
        validated: vc.validated || 0,
        refuted: vc.refuted || 0,
        inconclusive: vc.inconclusive || 0,
      },
    });
    const sub = (api.substrates || []).find((s) => s.name === name);
    if (sub) {
      api.substrate = sub.name;
      api.substrate_commit = sub.commitCount === 1 ? sub.commit : (sub.commitCount + ' commits');
    } else {
      api.substrate = 'all substrates';
      api.substrate_commit = '';
    }
    return api.totals;
  }

  const api = {
    wheels, pillars, tiers, corpora, scenarios, bundles, totals, activity, agents,
    agentCalls: [],
    integrations: [],
    substrate_organs: [],
    substrates: [],
    activeSubstrate: null,
    _allBundles: bundles,
    substrateStamps,
    buildProof, formatThreshold, setActiveSubstrate,
    metricsText,
    version: '0.64.1',
    git_commit: '3f0763aa468566729f3e2f795cfb5f433457534d',
    substrate: 'kimera-swm',
    substrate_commit: '4552de7e',
    hydrate,
    live: {
      version: false, scenarios: false, bundles: false, proofs: false,
      metrics: false, agents: false, agentCalls: false, integrations: false,
      substrates: false, substrate_organs: false,
    },
  };
  return api;
})();
