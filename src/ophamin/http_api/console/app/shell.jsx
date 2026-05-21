/** @jsxRuntime classic */ /** @jsx React.createElement */
/* global React */
// AppShell, NavRail, TopBar — the canonical UniFi-style structural chrome.

const { useState: useShellState, useEffect: useShellEffect } = React;

function Icon({ name, size = 18 }) {
  const s = size;
  const stroke = "currentColor";
  const sw = 1.5;
  const common = { width: s, height: s, viewBox: "0 0 24 24", fill: "none", stroke, strokeWidth: sw, strokeLinecap: "round", strokeLinejoin: "round" };
  const paths = {
    overview: <><circle cx="12" cy="12" r="9"/><circle cx="12" cy="12" r="5"/><circle cx="12" cy="12" r="1.5" fill={stroke}/></>,
    proofs:   <><rect x="4" y="3" width="14" height="18" rx="2"/><path d="M8 8h6M8 12h6M8 16h4"/></>,
    scenarios:<><path d="M3 6h7v6H3zM14 6h7v12h-7zM3 14h7v6H3z"/></>,
    run:      <><path d="M5 4l14 8-14 8z"/></>,
    telemetry:<><path d="M3 18l4-7 4 4 5-10 5 13"/></>,
    agents:   <><circle cx="12" cy="8" r="3"/><path d="M5 21v-1a7 7 0 0 1 14 0v1"/><circle cx="12" cy="8" r="0.5" fill={stroke}/></>,
    settings: <><circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.7 1.7 0 0 0 .3 1.8l.1.1a2 2 0 1 1-2.8 2.8l-.1-.1a1.7 1.7 0 0 0-1.8-.3 1.7 1.7 0 0 0-1 1.5V21a2 2 0 1 1-4 0v-.1a1.7 1.7 0 0 0-1.1-1.5 1.7 1.7 0 0 0-1.8.3l-.1.1a2 2 0 1 1-2.8-2.8l.1-.1a1.7 1.7 0 0 0 .3-1.8 1.7 1.7 0 0 0-1.5-1H3a2 2 0 1 1 0-4h.1a1.7 1.7 0 0 0 1.5-1.1 1.7 1.7 0 0 0-.3-1.8l-.1-.1a2 2 0 1 1 2.8-2.8l.1.1a1.7 1.7 0 0 0 1.8.3H9a1.7 1.7 0 0 0 1-1.5V3a2 2 0 1 1 4 0v.1a1.7 1.7 0 0 0 1 1.5 1.7 1.7 0 0 0 1.8-.3l.1-.1a2 2 0 1 1 2.8 2.8l-.1.1a1.7 1.7 0 0 0-.3 1.8V9a1.7 1.7 0 0 0 1.5 1H21a2 2 0 1 1 0 4h-.1a1.7 1.7 0 0 0-1.5 1z"/></>,
    search:   <><circle cx="11" cy="11" r="7"/><path d="m20 20-3.5-3.5"/></>,
    sun:      <><circle cx="12" cy="12" r="4"/><path d="M12 2v2M12 20v2M4.93 4.93l1.41 1.41M17.66 17.66l1.41 1.41M2 12h2M20 12h2M4.93 19.07l1.41-1.41M17.66 6.34l1.41-1.41"/></>,
    moon:     <><path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z"/></>,
    chevronL: <><path d="m15 18-6-6 6-6"/></>,
    chevronR: <><path d="m9 18 6-6-6-6"/></>,
    chevronD: <><path d="m6 9 6 6 6-6"/></>,
    chevronU: <><path d="m18 15-6-6-6 6"/></>,
    x:        <><path d="M18 6 6 18M6 6l12 12"/></>,
    copy:     <><rect x="9" y="9" width="13" height="13" rx="2"/><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"/></>,
    download: <><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4M7 10l5 5 5-5M12 15V3"/></>,
    external: <><path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6M15 3h6v6M10 14 21 3"/></>,
    play:     <><path d="m5 3 14 9-14 9z"/></>,
    refresh:  <><path d="M3 12a9 9 0 0 1 15-6.7L21 8M21 3v5h-5M21 12a9 9 0 0 1-15 6.7L3 16M3 21v-5h5"/></>,
    filter:   <><path d="M3 6h18M7 12h10M10 18h4"/></>,
    sort:     <><path d="M3 6h13M3 12h9M3 18h5M16 18l4-4M20 18V8"/></>,
    check:    <><path d="M20 6 9 17l-5-5"/></>,
    eye:      <><path d="M2 12s4-7 10-7 10 7 10 7-4 7-10 7S2 12 2 12z"/><circle cx="12" cy="12" r="3"/></>,
    cpu:      <><rect x="5" y="5" width="14" height="14" rx="1"/><rect x="9" y="9" width="6" height="6"/><path d="M9 2v3M15 2v3M9 19v3M15 19v3M2 9h3M2 15h3M19 9h3M19 15h3"/></>,
    activity: <><path d="M22 12h-4l-3 9L9 3l-3 9H2"/></>,
    calendar: <><rect x="3" y="5" width="18" height="16" rx="2"/><path d="M3 9h18M8 3v4M16 3v4"/></>,
    rocket:   <><path d="M4.5 16.5c-1.5 1-2 5-2 5s4-.5 5-2c.59-.85.58-2.14-.1-2.83a1.93 1.93 0 0 0-2.83-.1zM12 15l-3-3 7-7 3 3-7 7zM9 12l-1.5 1.5L9 15l1.5-1.5zM15 9l1.5-1.5L18 9l-1.5 1.5zM17 6l4 4"/></>,
    code:     <><path d="m18 16 4-4-4-4M6 8l-4 4 4 4M14.5 4l-5 16"/></>,
  };
  return <svg {...common}>{paths[name] || paths.overview}</svg>;
}
window.Icon = Icon;

function AppShell({ active, onNav, totals, accent, theme, density, onToggleTheme, onSubstrateChange, children }) {
  const [substrateOpen, setSubstrateOpen] = useShellState(false);
  const [activeSubstrate, setActiveSubstrate] = useShellState({
    name: 'all substrates',
    commit: '',
  });
  const navItems = [
    { id: 'control',   label: 'Control',   icon: 'cpu' },
    { id: 'chat',      label: 'Chat',      icon: 'agents' },
    { id: 'overview',  label: 'Overview',  icon: 'overview' },
    { id: 'roadmap',   label: 'Roadmap',   icon: 'rocket' },
    { id: 'discovery', label: 'Discovery', icon: 'eye' },
    { id: 'inspector', label: 'Inspector', icon: 'cpu' },
    { id: 'proofs',    label: 'Proofs',    icon: 'proofs',    count: totals.bundles },
    { id: 'drift',     label: 'Drift',     icon: 'telemetry' },
    { id: 'topology',  label: 'Topology',  icon: 'scenarios' },
    { id: 'scenarios', label: 'Scenarios', icon: 'scenarios', count: totals.scenarios },
    { id: 'run',       label: 'Run',       icon: 'run' },
    { id: 'telemetry', label: 'Telemetry', icon: 'telemetry' },
    { id: 'lab',       label: 'Lab',       icon: 'code' },
    { id: 'interop',   label: 'Interop',   icon: 'external' },
    { id: 'audit',     label: 'Audit',     icon: 'cpu' },
  ];
  const navBottom = [
    { id: 'agents',       label: 'Agents',       icon: 'agents' },
    { id: 'integrations', label: 'Integrations', icon: 'external' },
    { id: 'settings',     label: 'Settings',     icon: 'settings' },
  ];

  const activeItem = [...navItems, ...navBottom].find(i => i.id === active);

  // Real substrate catalogue, derived from the proof corpus by hydrate
  // (api.substrates). Falls back to a single grounded entry off disk.
  // The "all substrates" head entry clears the scope.
  const O = window.OPHAMIN || {};
  const realSubs = O.substrates || [];
  const allCount = (O._allBundles && O._allBundles.length) || (totals && totals.bundles) || 0;
  const substrates = [
    { name: 'all substrates', commit: '', bundles: allCount, status: 'healthy', all: true },
    ...realSubs.map((s) => ({
      name: s.name,
      commit: s.commitCount === 1 ? s.commit : (s.commitCount + ' commits'),
      bundles: s.bundles,
      status: 'healthy',
    })),
  ];

  return (
    <div className="app-shell">
      <header className="topbar">
        <div className="brand">
          <BrandMark/>
        </div>

        {/* Substrate selector — "Dream Router" pattern with dropdown */}
        <div style={{ position: 'relative' }}>
          <button className="substrate-selector" onClick={() => setSubstrateOpen(o => !o)} title="Substrate under test">
            <span className="dot"></span>
            <span style={{ fontWeight: 500 }}>{activeSubstrate.name}</span>
            <span className="mono" style={{ fontSize: 10, color: 'var(--text-muted)', marginLeft: 2 }}>{activeSubstrate.commit}</span>
            <span className="chev" style={{ transform: substrateOpen ? 'rotate(180deg)' : 'none', transition: 'transform 200ms ease' }}>
              <Icon name="chevronD" size={11}/>
            </span>
          </button>
          {substrateOpen && (
            <>
              <div style={{ position: 'fixed', inset: 0, zIndex: 9 }} onClick={() => setSubstrateOpen(false)}/>
              <div className="substrate-dropdown">
                <div className="substrate-dropdown-head">
                  <span className="micro">SUBSTRATES UNDER TEST · {substrates.length}</span>
                </div>
                {substrates.map(s => (
                  <div key={s.name}
                    className={'substrate-item' + (s.name === activeSubstrate.name ? ' active' : '')}
                    onClick={() => {
                      setActiveSubstrate({ name: s.name, commit: s.commit });
                      setSubstrateOpen(false);
                      if (window.OPHAMIN && window.OPHAMIN.setActiveSubstrate) {
                        window.OPHAMIN.setActiveSubstrate(s.all ? null : s.name);
                      }
                      if (onSubstrateChange) onSubstrateChange();
                      window.toast && window.toast({ kind: 'success', title: 'Now observing', msg: s.all ? 'all substrates' : (s.name + (s.commit ? ' · ' + s.commit : '')) });
                    }}>
                    <span className="substrate-item-dot" style={{ background: s.status === 'healthy' ? 'var(--validated)' : 'var(--inconclusive)' }}/>
                    <div style={{ flex: 1, minWidth: 0 }}>
                      <div style={{ display: 'flex', alignItems: 'baseline', gap: 6 }}>
                        <span style={{ fontWeight: 500 }}>{s.name}</span>
                      </div>
                      <div className="mono" style={{ fontSize: 10, color: 'var(--text-muted)' }}>
                        {s.commit ? s.commit + ' · ' : ''}{s.bundles} bundles
                      </div>
                    </div>
                    {s.name === activeSubstrate.name && <Icon name="check" size={13}/>}
                  </div>
                ))}
                <div className="substrate-dropdown-foot">
                  <button className="link-btn"><Icon name="rocket" size={11}/> Add substrate</button>
                  <button className="link-btn">Manage fleet</button>
                </div>
              </div>
            </>
          )}
        </div>

        {/* Centered brand + breadcrumb */}
        <div className="topbar-title">
          <span className="brand-mark-text">Ophamin</span>
          <span className="crumb-sep">/</span>
          <span className="crumb">Fleet</span>
          <span className="crumb-sep">/</span>
          <span className="crumb">{activeSubstrate.name}</span>
          <span className="crumb-sep">/</span>
          <span className="crumb current">{activeItem?.label || 'Console'}</span>
        </div>

        <div className="topbar-right">
          <button className="btn ghost" style={{ height: 28, fontSize: 11, gap: 4 }}
            onClick={() => window.dispatchEvent(new KeyboardEvent('keydown', { key: 'k', metaKey: true }))}
            title="Search · ⌘K">
            <Icon name="search" size={13}/>
            <span className="mono" style={{ color: 'var(--text-muted)', fontSize: 10, padding: '0 4px', border: '1px solid var(--border)', borderRadius: 3 }}>⌘K</span>
          </button>
          <span className="design-preview-pill" title="Click to re-open the intro" onClick={() => { try { localStorage.removeItem('ophamin_intro_seen'); } catch(e){} window.openIntro && window.openIntro(); }} style={{ cursor: 'pointer' }}>
            <span className="dot"></span>design preview
          </span>
          <button className="btn ghost icon" aria-label="Open intro" title="Open intro / help"
            onClick={() => { try { localStorage.removeItem('ophamin_intro_seen'); } catch(e){} window.openIntro && window.openIntro(); }}>
            <Icon name="eye" size={14}/>
          </button>
          <button className="btn ghost icon" title="Notifications">
            <Icon name="activity" size={14}/>
          </button>
          <button className="btn ghost icon" onClick={onToggleTheme} title="Toggle theme">
            <Icon name={theme === 'dark' ? 'sun' : 'moon'} size={14}/>
          </button>
        </div>
      </header>

      <nav className="rail">
        {navItems.map(item => (
          <div key={item.id}
            className={'nav-item' + (active === item.id ? ' active' : '')}
            onClick={() => onNav(item.id)}
            title={item.label}>
            {item.count != null && <span className="nav-count mono">{item.count}</span>}
            <span className="nav-icon"><Icon name={item.icon} size={18}/></span>
            <span className="nav-label">{item.label}</span>
          </div>
        ))}

        <div style={{ flex: 1, minHeight: 8 }}></div>

        {navBottom.map(item => (
          <div key={item.id}
            className={'nav-item' + (active === item.id ? ' active' : '')}
            onClick={() => onNav(item.id)}
            title={item.label}
            style={item.muted ? { opacity: 0.55 } : null}>
            <span className="nav-icon"><Icon name={item.icon} size={18}/></span>
            <span className="nav-label">{item.label}</span>
          </div>
        ))}

        <div className="rail-footer">
          <span style={{ color: 'var(--validated)', fontSize: 12 }}>●</span>
        </div>
      </nav>

      <main className="content">
        <GatesBanner/>
        {children}
      </main>

      <ToastStack/>
    </div>
  );
}

function BrandMark() {
  // The six-wheels mark, compact — used in the topbar lockup
  return (
    <svg width={26} height={26} viewBox="0 0 32 32" style={{ flexShrink: 0 }}>
      {[0,1,2].map(i => {
        const r = 6 + i * 4;
        const c = 2 * Math.PI * r;
        return (
          <circle key={i} cx="16" cy="16" r={r}
            fill="none"
            stroke="var(--accent)"
            strokeWidth="1.4"
            strokeDasharray={`${c * 0.55} ${c * 0.45}`}
            opacity={0.4 + i * 0.2}
            transform={`rotate(${i * 35} 16 16)`}
          />
        );
      })}
      <circle cx="16" cy="16" r="1.5" fill="var(--accent)"/>
    </svg>
  );
}



// =============================================================
// GatesBanner — live status strip. Every value is real + hydrated
// (version, signed-proof count, scenario count, agent count) plus a
// LIVE/SAMPLE provenance pill driven by OPHAMIN.live.* — so the strip
// never shows fabricated numbers. (It previously hardcoded a Kimera
// hardening count; Ophamin reports its own state here instead.)
// =============================================================
function GatesBanner() {
  const D = window.OPHAMIN || {};
  const t = D.totals || {};
  const live = D.live || {};
  const isLive = Object.values(live).some(Boolean);
  const accent = isLive ? 'var(--validated, #2dd4bf)' : 'var(--inconclusive, #ffa726)';
  return (
    <div className="gates-banner">
      <span className="gates-label">OPHAMIN</span>
      <span className="gates-pill ok"><span className="dot"></span>v{D.version || '—'}</span>
      <span className="gates-pill ok"><span className="dot"></span>{t.bundles != null ? t.bundles : '—'} signed proofs</span>
      <span className="gates-pill ok"><span className="dot"></span>{t.scenarios != null ? t.scenarios : '—'} scenarios</span>
      <span className="gates-pill ok"><span className="dot"></span>{(D.agents || []).length} agents</span>
      <span className="gates-pill" style={{ color: accent }} title={isLive ? 'overlaid with live REST data' : 'showing grounded sample data (backend not reached)'}>
        <span className="dot" style={{ background: accent }}></span>{isLive ? 'LIVE' : 'SAMPLE'}
      </span>
      <span style={{ flex: 1 }}/>
      <span className="gates-meta">substrate · {D.substrate || 'kimera-swm'}{D.substrate_commit ? ' @ ' + D.substrate_commit : ''}</span>
    </div>
  );
}
window.GatesBanner = GatesBanner;

window.AppShell = AppShell;
window.BrandMark = BrandMark;



// =============================================================
// Glossary — hover tooltip with plain-language definitions for
// the framework's technical vocabulary.
// =============================================================
const GLOSSARY_TERMS = {
  'wilson-ci': {
    title: 'Wilson 95% confidence interval',
    code: 'statsmodels · proportion_confint(method="wilson")',
    body: 'Range of true rates consistent with the observed count, at 95% confidence. Tighter than the naive Wald interval for small n or rates near 0/1. If the CI excludes the threshold, the verdict is decisive.',
  },
  'p-value': {
    title: 'p-value',
    body: 'Probability of seeing data this extreme if H₀ were true. Ophamin does not threshold on p alone — verdicts are governed by pre-registered claim thresholds. p is reported as descriptive evidence, not a gate.',
  },
  'pillar': {
    title: 'OFAMIN pillar',
    code: 'O.{domain}.{metric}',
    body: 'A pre-registered statistical primitive backed by a mature library. O = Observability, F = Formal-provenance, A = Adaptive-testing, M = Mixed-effects, I = Iterative-synthesis, N = N-fold-robustness. Pillars compose into a Scenarios evidence.',
  },
  'effect-size': {
    title: 'Effect size',
    body: 'Magnitude of a difference, scale-independent. Cohen d for paired/unpaired means; Cliffs δ for non-parametric. A statistically significant effect with d ≈ 0 is rarely interesting; d ≥ 0.3 is conventionally "small but real".',
  },
  'preregistration': {
    title: 'Pre-registration',
    code: 'config_hash + data_hash captured before run',
    body: 'Ophamin records the config + data hashes + analysis plan BEFORE the substrate runs. The verdict is judged against a threshold committed to in advance — that is what makes a REFUTED outcome epistemically meaningful, not a failure to measure.',
  },
  'proof-id': {
    title: 'proof_id (content hash)',
    code: 'sha256(canonical_body)',
    body: 'The proof bundle is content-addressed: any byte mutation cascades through the proof_id. RFC 8785 canonical form ensures the hash is the same in any language (Python / Rust / JS verifiers).',
  },
  'hmac': {
    title: 'HMAC signature',
    code: 'HMAC-SHA256(publication_key, canonical_body)',
    body: 'Authenticates that this proof came from the holder of the publication key. Independent of (and stronger than) the content hash. The /verify endpoint checks both.',
  },
  'cross-check': {
    title: 'Cross-framework check',
    code: 'measurement-machinery tier',
    body: 'Validates that Ophamins upstream libraries agree among themselves (scipy ↔ statsmodels ↔ pingouin etc) to within float epsilon. These scenarios test the measurement apparatus, not the substrate.',
  },
  'observed': {
    title: 'Observed value',
    body: 'The pillar point estimate for this run — the single number that gets compared against the pre-registered threshold to decide the verdict.',
  },
  'verdict': {
    title: 'Verdict',
    body: 'VALIDATED · substrate met the threshold. REFUTED · framework commitment held; substrate did not meet it (this is the framework working, not a failure). INCONCLUSIVE · evidence does not resolve the claim within tolerance.',
  },
  'geoid': {
    title: 'Geoid',
    code: 'kimera_swm.domain.cognitive.geoid',
    body: 'The substrates accumulated semantic shape. Integrated gravitational mass of every concept that has ever passed through. Literal Earth-geoid analogy: experience adds mass, mass deforms the manifold, deformation reshapes future retrieval. Not a metaphor.',
  },
  'walker': {
    title: 'Walker',
    code: 'PrimeTopologyWalker (4 modes)',
    body: 'Oscillator-driven traversal of the prime-indexed manifold. Four contradiction-resolution modes: M1 COMMIT, M2 HALT, M3 ROLLBACK, M4 LATERAL LEAP. The walk IS the cognition — each step is a lived experience under tension.',
  },
  'takwin': {
    title: 'Takwin',
    code: 'Takwin.run() · KCCL canonical pipeline',
    body: '7-step canonical cognitive loop: Screen (GWF) -> Encode (5D hypersphere, prime assignment) -> Traverse (walker) -> Consolidate (prime_chain) -> Vault (scar if contradiction-gate passes) -> Render. One per cognitive cycle.',
  },
  'sinew': {
    title: 'Sinew',
    body: 'Substrate connective tissue carrying the M4-conservation invariant. Tested via sinew-conservation scenario (walker_m4_conservation_ratio <= 0.05). Refutation means the walker is breaking conservation under perturbation.',
  },
  'prime-chain': {
    title: 'Prime chain',
    code: 'GeoidNode.prime -> PrimeWaveQuantumEngine',
    body: 'The substrates universal language. Every concept is assigned a prime via the Arachne sieve. Trajectories are sequences of primes. By the Fundamental Theorem of Arithmetic no two products of distinct primes collide -- provenance by construction.',
  },
  'arachne': {
    title: 'Arachne',
    code: 'ArachneProtocol · prime registry',
    body: 'The canonical prime-assignment registry. Every concept the substrate has ever encoded gets a prime here. Lookups are content-addressed; assignment is deterministic.',
  },
  'piovra': {
    title: 'Piovra',
    body: 'Multi-arm distributed sensing primitive (octopus analogy). Each arm handles a foreign-corpus channel (text, image, audio, market, telemetry). Cross-arm coherence is what climbs as the substrate accumulates experience.',
  },
  'kccl': {
    title: 'KCCL',
    code: 'Kimera Core Cognitive Loop',
    body: 'The substrates canonical pipeline embodied as one Takwin.run() cycle. 13-frequency Cronos pulse drives it; every cycle deposits to one Arachne and one Vault.',
  },
  'scar': {
    title: 'Scar',
    body: 'Permanent topological deformation of the manifold formed when the contradiction-gate fires. Scars accumulate; they are how the substrate learns. No reset. Learning IS scar accumulation.',
  },
  'vault': {
    title: 'Vault',
    body: 'Substrate-internal storage where scars and consolidated trajectories deposit. Ed25519-signed; non-deletion stance.',
  },
  'phi': {
    title: 'Phi (Φ)',
    code: 'Integrated Information per IIT (Oizumi et al. 2014)',
    body: 'Graph-theoretic measure of integrated information on the substrates prime-wave quantum state per cycle. NOT a phenomenological claim of consciousness -- a structural property. Measured per-cycle; drifts directionally with content.',
  },
  'gwf': {
    title: 'GWF',
    code: 'General Workspace Filter',
    body: 'First-line adversarial filter on the input membrane. Decides what gets to enter the Takwin pipeline. The concentrated-immune-siege scenario tests its false-positive rate (architectural ceiling: <= 10%).',
  },
  'rosetta': {
    title: 'Rosetta',
    body: 'Cross-modal canonicalization primitive. Image / audio / text all deposit into ONE Arachne via Rosetta. Validation: rosetta-scaling scenario tests canonical-agreement across 10 languages on FLORES-200.',
  },
  'manifold': {
    title: 'Spherical manifold',
    code: 'S⁴ ⊂ ℝ⁵ (1+3+1 = 5D)',
    body: 'The substrates memory IS a 4-sphere in 5D. Concepts are points on the surface; experience deforms the surface; retrieval follows the deformed geodesics. Memory-as-deformation is measured empirically (Session 013).',
  },
  'path-a-b': {
    title: 'Path A / Path B',
    body: 'Two parallel thermodynamic stacks. Path A: analytical (zeta-prime partition, TFD, Bekenstein, Landau, oracle: mpmath). Path B: EBM/learning (Hopfield variants, scar-Hopfield, BCPNN; oracle: THRML). Deliberately unfused -- they answer different questions.',
  },
  'kaido': {
    title: 'Kaido',
    body: 'External corpus volume mounted at /Volumes/Kaido/Foreign_Corpus/. Multi-modal sources: sensory_vision (CIFAR-10 etc), sensory_audio (ESC-50), market feeds. Piovra arms pull from here.',
  },
  'pattern-p': {
    title: 'Pattern-P drift',
    code: 'Docs_v2/06_development/philosophical_drift.md',
    body: 'Kimera-side defect class: code or docstring claims something (e.g. "this is NOT physical X") that drifts from the owners actual perception. The framework explicitly hunts for sycophancy-hedge disclaimers and unprincipled software-engineering simplifications. Three Pattern-P primitives have been resolved at the corrected methodology.',
  },
  'no-fallback': {
    title: 'No-fallback rule',
    code: 'owner directive 2026-04-22',
    body: 'Fallbacks, shims, stubs, simulations, and silent-feature-off patterns are strictly forbidden in Kimera-SWM. ~900 sites across 240+ files hardened in Tranches 1-9. Loud failure with the real error is the discipline.',
  },
  'non-deletion': {
    title: 'Non-deletion stance',
    body: 'No primitive is deleted without explicit owner authorization, even apparently-dead code. The substrate accumulates; nothing resets. Mirrors the substrates own ontology (we are the sum of our conditional experience).',
  },
  'mcp': {
    title: 'MCP (Model Context Protocol)',
    code: 'ophamin mcp serve',
    body: 'A standard for agents to call tools. Ophamin ships an MCP server exposing the same read+run+verify surface as the HTTP API. Shared implementations behind both — behavioural drift is structurally impossible. Claude Code, Claude Desktop, Cursor, and Cline all speak MCP natively.',
  },
  'bge-m3': {
    title: 'BGE-M3',
    code: '1024-d, MPS, lazy-load · sole canonical encoder',
    body: 'The substrates current text encoder (replaced FastText 2026-05). 1024-dimensional L2-normalized. The roadmap (2026-05-18) re-baselines every measurement under BGE-M3 because FastText-era numbers are historical-only.',
  },
  'substrate': {
    title: 'Substrate under test',
    code: 'kimera-swm @ 6e4477ebb',
    body: 'The system Ophamin is observing. Default is Kimera-SWM. Anything implementing the SubstrateUnderTest protocol works — Ophamin is built for Kimera but not coupled to it.',
  },
};

function Glossary({ term, children }) {
  const def = GLOSSARY_TERMS[term];
  if (!def) return children;
  return (
    <span className="glossary">
      {children}
      <span className="glossary-icon">?</span>
      <span className="glossary-tip">
        <div className="glossary-tip-head">{def.title}</div>
        {def.code && <div className="glossary-tip-mono">{def.code}</div>}
        <div>{def.body}</div>
      </span>
    </span>
  );
}
window.Glossary = Glossary;

// ============================================================
// Toast stack — bottom-right, UniFi-style ephemeral notifications
// ============================================================
const TOAST_BUS = { listeners: [], push(t) { this.listeners.forEach(l => l(t)); } };
window.toast = (toast) => TOAST_BUS.push(toast);

function ToastStack() {
  const [toasts, setToasts] = useShellState([]);
  useShellEffect(() => {
    const listener = (t) => {
      const id = Math.random().toString(36).slice(2);
      setToasts(ts => [...ts, { ...t, id }]);
      setTimeout(() => setToasts(ts => ts.filter(x => x.id !== id)), t.duration || 5500);
    };
    TOAST_BUS.listeners.push(listener);
    return () => { TOAST_BUS.listeners = TOAST_BUS.listeners.filter(l => l !== listener); };
  }, []);

  if (!toasts.length) return null;
  return (
    <div className="toast-stack">
      {toasts.map(t => (
        <div key={t.id} className={'toast toast-' + (t.kind || 'info')}>
          <span className="toast-icon">
            <Icon name={t.kind === 'success' ? 'check' : t.kind === 'error' ? 'x' : t.kind === 'warn' ? 'rocket' : 'activity'} size={14}/>
          </span>
          <div className="toast-body">
            <div className="toast-title">{t.title}</div>
            {t.msg && <div className="toast-msg">{t.msg}</div>}
          </div>
          {t.action && (
            <button className="link-btn" style={{ fontSize: 11 }} onClick={t.action.onClick}>{t.action.label}</button>
          )}
          <button className="toast-close" onClick={() => setToasts(ts => ts.filter(x => x.id !== t.id))}>
            <Icon name="x" size={11}/>
          </button>
        </div>
      ))}
    </div>
  );
}
window.ToastStack = ToastStack;

// ============================================================
// CountUp — animated number that ticks up on mount/value-change
// ============================================================
function CountUp({ value, duration = 900, decimals = 0, suffix = '' }) {
  const [v, setV] = useShellState(0);
  useShellEffect(() => {
    const start = performance.now();
    const from = 0;
    const reduce = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
    if (reduce) { setV(value); return; }
    let raf;
    const tick = (now) => {
      const t = Math.min(1, (now - start) / duration);
      // ease-out-expo
      const eased = t === 1 ? 1 : 1 - Math.pow(2, -10 * t);
      setV(from + (value - from) * eased);
      if (t < 1) raf = requestAnimationFrame(tick);
    };
    raf = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf);
  }, [value, duration]);
  return <span className="mono tnum">{decimals ? v.toFixed(decimals) : Math.round(v)}{suffix}</span>;
}
window.CountUp = CountUp;

// VerdictPill
function VerdictPill({ verdict, size = 'sm' }) {
  return (
    <span className={'verdict-pill ' + verdict}>
      <span className="dot"></span>
      {verdict}
    </span>
  );
}
window.VerdictPill = VerdictPill;

// TierChip
function TierChip({ tier }) {
  const label = tier === 'measurement_machinery' ? 'measurement' : tier;
  return <span className={'chip tier-' + tier}>{label}</span>;
}
window.TierChip = TierChip;

// Format badges row
function FormatBadges({ files }) {
  const all = [
    ['json', 'proof.json'],
    ['md',   'proof.md'],
    ['html', 'proof.html'],
    ['tex',  'proof.tex'],
    ['pdf',  'proof.pdf'],
  ];
  return (
    <div style={{ display: 'flex', gap: 4 }}>
      {all.map(([label, fname]) => (
        <span key={label} className={'fmt-badge' + (files.includes(fname) ? ' has' : '')}>{label}</span>
      ))}
    </div>
  );
}
window.FormatBadges = FormatBadges;
