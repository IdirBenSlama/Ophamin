/** @jsxRuntime classic */ /** @jsx React.createElement */
/* global React, Icon */
// Inspector — per-primitive composite reference. Mirrors `ophamin inspect
// <kimera-repo> <primitive>` and demonstrates the "six wheels are composable"
// thesis: how each wheel observes each Kimera primitive.
//
// NO FABRICATION (2026-05-31): this is the DESIGN/REFERENCE map — what each
// wheel is wired to observe for each primitive. It used to embed fabricated
// specific measurements (p95 < 8ms, 2.36s, 53 MiB, ≥99%, "14 SLOC", commit
// refs) as if real, plus dead "Re-inspect / Run / journal" buttons. The fake
// numbers are removed; live values come from running the CLI against a
// connected substrate (shown at the foot of the composite).

const { useState: useInState } = React;

const PRIMITIVES = [
  { id: 'GWF',          family: 'screen',       module: 'kimera_swm.domain.security.gwf', wheels: { seeing: 'fed by entity-feature extraction', measuring: 'concentrated-immune-siege probes the false-positive ceiling',     comparing: 'GWF threshold tuning tracked across commits',  instrumenting: 'per-call latency sampled', auditing: 'ruff + bandit lints applied',           reporting: 'evidence: O.immune.false_positive · O.immune.detection' } },
  { id: 'Walker',       family: 'cognitive',    module: 'kimera_swm.domain.cognitive.prime_topology_walker', wheels: { seeing: 'observes the manifold via the Arachne prime index',   measuring: 'logic-topology-siege · sinew-conservation', comparing: 'sustained-traversal rate tracked across commits', instrumenting: '4 modes (M1/M2/M3/M4) per cycle sampled',  auditing: 'mypy strict typing',         reporting: 'evidence: O.topology.sustained · O.sinew.conservation' } },
  { id: 'Takwin',       family: 'orchestrator', module: 'kimera_swm.domain.cognitive.takwin',         wheels: { seeing: 'composes the seeing-wheel probes',                  measuring: 'throughput-ceiling · memory-as-deformation', comparing: 'cycle-shape stability tracked across commits',     instrumenting: 'cycle wall-time sampled against the configured ceiling', auditing: 'checked for conditional-dead code + silent fallbacks',  reporting: 'evidence: O.engineering.* · structural traces' } },
  { id: 'Arachne',      family: 'registry',     module: 'kimera_swm.domain.cognitive.arachne_protocol',wheels: { seeing: 'canonical prime registry · content-addressed', measuring: 'prime-direct-lookup · prime-cross-instance', comparing: 'identity invariance across instances', instrumenting: 'lookup latency sampled',                 auditing: 'ed25519-signed; non-deletion stance',     reporting: 'evidence: O.prime.p_thermo · invariance' } },
  { id: 'Geoid',        family: 'memory',       module: 'kimera_swm.domain.cognitive.geoid',          wheels: { seeing: 'integrated gravitational shape of all concepts', measuring: 'memory-as-deformation',     comparing: 'manifold-deformation tracked per cycle',    instrumenting: 'no per-cycle cost (passive substrate)',   auditing: 'wired at orchestrator scope (Pattern-P)',   reporting: 'evidence: structural — the substrate is the metric' } },
  { id: 'Vault',        family: 'storage',      module: 'kimera_swm.domain.cognitive.vault',          wheels: { seeing: 'scar deposit receiver',                       measuring: 'scar formation rate measured per cycle',  comparing: 'scar persistence across reruns',            instrumenting: 'storage growth rate sampled',    auditing: 'ed25519-signed; non-deletion stance',     reporting: 'evidence: scars listed in proof.provenance' } },
  { id: 'Piovra',       family: 'sensing',      module: 'kimera_swm.domain.sensing.piovra',           wheels: { seeing: 'multi-arm: text, image, audio, market, telemetry',measuring: 'rosetta-scaling · cross-arm jaccard',     comparing: 'cross-modal coherence climbs with experience',instrumenting: 'per-arm throughput sampled',             auditing: 'pip-audit on the arms’ deps',          reporting: 'evidence: O.language.agreement · jaccard' } },
  { id: 'Sinew',        family: 'connective',   module: 'kimera_swm.domain.cognitive.sinew',          wheels: { seeing: 'connective fabric (M4 invariant)',            measuring: 'sinew-conservation · modulation-disruption',comparing: 'walker_m4_conservation_ratio against its threshold', instrumenting: 'per-cycle ratio sampled',                auditing: 'mypy strict',                              reporting: 'evidence: O.sinew.conservation · recovery_cycles' } },
  { id: 'Cronos',       family: 'temporal',     module: 'kimera_swm.domain.temporal.cronos',          wheels: { seeing: 'atomic-clock layer · 13-frequency pulse',     measuring: 'refractory-period · drift detection',     comparing: 'time-deviation sampled across cycles',     instrumenting: 'tick latency sampled',         auditing: 'no fallbacks; loud-fail on clock drift',  reporting: 'evidence: O.temporal.refractory' } },
  { id: 'PrimeWaveQE',  family: 'quantum',      module: 'kimera_swm.domain.quantum.prime_wave_qe',    wheels: { seeing: 'consumes prime_chain from the walker',            measuring: 'bayesian-phi-posterior · quantum-basis',  comparing: 'phi posterior shape across commits',        instrumenting: 'NUTS sampler timing',                    auditing: 'pymc + numpyro cross-checked',            reporting: 'evidence: phi (IIT measure) · coherence' } },
  { id: 'Rosetta',      family: 'canonicalization', module: 'kimera_swm.domain.linguistic.rosetta',   wheels: { seeing: 'cross-modal arbiter',                         measuring: 'rosetta-scaling on FLORES-200',           comparing: 'canonical agreement across languages',   instrumenting: 'encode latency sampled per-language',   auditing: 'BGE-M3 sole canonical encoder · FastText gone',reporting: 'evidence: O.language.agreement' } },
  { id: 'Alexandria',   family: 'memory',       module: 'kimera_swm.domain.cognitive.alexandria',     wheels: { seeing: 'fused keyspace across instances',             measuring: 'prime-ecosystem · key persistence',  comparing: 'fused-key persistence across cycles',       instrumenting: 'keyspace size sampled',                  auditing: 'non-deletion stance',                     reporting: 'evidence: O.prime.persistent_keys' } },
];

function InspectorScreen() {
  const [selectedId, setSelectedId] = useInState('Walker');
  const [filter, setFilter] = useInState('');
  const filtered = PRIMITIVES.filter(p => !filter || p.id.toLowerCase().includes(filter.toLowerCase()) || p.family.includes(filter.toLowerCase()));
  const p = PRIMITIVES.find(x => x.id === selectedId);

  const WHEEL_META = [
    { id: 'seeing',        color: '#5e9eff' },
    { id: 'measuring',     color: '#2dd4bf' },
    { id: 'comparing',     color: '#8b95e8' },
    { id: 'instrumenting', color: '#ffa726' },
    { id: 'auditing',      color: '#94a3b8' },
    { id: 'reporting',     color: '#4ade80' },
  ];

  return (
    <div className="content-inner page">
      <div className="page-header">
        <div>
          <h1 className="page-title">Inspector</h1>
          <div className="page-subtitle mono" style={{ whiteSpace: 'nowrap' }}>
            Pick a Kimera primitive. See how each Ophamin wheel is wired to observe it.
          </div>
        </div>
      </div>

      <div className="agent-banner" style={{ marginTop: 12 }}>
        <Icon name="cpu" size={16}/>
        <div>
          A <b>reference map</b> — how each of the six wheels observes each primitive (the "six wheels compose" thesis), mirroring <span className="mono">ophamin inspect &lt;kimera-repo&gt; &lt;primitive&gt;</span>. It describes the wiring, not a live read; specific measured values come from running that CLI against a connected substrate.
        </div>
      </div>

      <div className="roadmap-stats" style={{ marginTop: 12 }}>
        <div><span className="micro">PRIMITIVES</span><span className="mono tnum" style={{ fontSize: 22 }}>{PRIMITIVES.length}</span></div>
        <div><span className="micro">CURRENT</span><span className="mono" style={{ fontSize: 14 }}>{p.id}</span></div>
        <div style={{ flex: 1 }}/>
        <div><span className="micro">MODULE</span><span className="mono" style={{ fontSize: 11 }}>{p.module}</span></div>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: '260px 1fr', gap: 16, marginTop: 16 }}>
        {/* LEFT — primitives list */}
        <div className="card" style={{ overflow: 'hidden', alignSelf: 'flex-start' }}>
          <div style={{ padding: 10, borderBottom: '1px solid var(--border)' }}>
            <div style={{ position: 'relative' }}>
              <span style={{ position: 'absolute', left: 8, top: '50%', transform: 'translateY(-50%)', color: 'var(--text-muted)' }}>
                <Icon name="search" size={12}/>
              </span>
              <input className="input" style={{ paddingLeft: 26, height: 26, fontSize: 12 }}
                placeholder="filter primitives"
                value={filter} onChange={e => setFilter(e.target.value)}/>
            </div>
          </div>
          <div style={{ maxHeight: 540, overflowY: 'auto', padding: '4px 0' }}>
            {filtered.map(prim => (
              <div key={prim.id}
                onClick={() => setSelectedId(prim.id)}
                style={{
                  padding: '8px 12px',
                  cursor: 'pointer',
                  background: selectedId === prim.id ? 'var(--accent-soft)' : 'transparent',
                  borderLeft: '3px solid ' + (selectedId === prim.id ? 'var(--accent)' : 'transparent'),
                }}>
                <div style={{ fontSize: 13, fontWeight: 500, color: selectedId === prim.id ? 'var(--accent)' : 'var(--text-primary)' }}>{prim.id}</div>
                <div className="mono" style={{ fontSize: 10, color: 'var(--text-muted)', marginTop: 2 }}>{prim.family}</div>
              </div>
            ))}
          </div>
        </div>

        {/* RIGHT — six-wheel composite for selected primitive */}
        <div className="card">
          <div className="card-header">
            <div>
              <div className="card-title">{p.id}</div>
              <div className="mono" style={{ fontSize: 11, color: 'var(--text-muted)', marginTop: 2 }}>{p.family} · {p.module}</div>
            </div>
            <span className="chip">composite</span>
          </div>
          <div style={{ padding: 16, display: 'flex', flexDirection: 'column', gap: 8 }}>
            {WHEEL_META.map(w => (
              <div key={w.id} className="inspector-wheel-row">
                <div className="inspector-wheel-name" style={{ color: w.color }}>
                  <span className="inspector-wheel-dot" style={{ background: w.color }}/>
                  {w.id.toUpperCase()}
                </div>
                <div style={{ flex: 1, fontSize: 12.5, color: 'var(--text-secondary)', lineHeight: 1.55 }}>
                  {p.wheels[w.id]}
                </div>
              </div>
            ))}
          </div>
          <div style={{ padding: '10px 14px', borderTop: '1px solid var(--border)', display: 'flex', alignItems: 'center', gap: 6 }}>
            <span style={{ fontSize: 11, color: 'var(--text-muted)' }}>Run live against a substrate:</span>
            <span className="mono" style={{ fontSize: 11, color: 'var(--accent)' }}>ophamin inspect &lt;kimera-repo&gt; {p.id}</span>
          </div>
        </div>
      </div>
    </div>
  );
}

window.InspectorScreen = InspectorScreen;
