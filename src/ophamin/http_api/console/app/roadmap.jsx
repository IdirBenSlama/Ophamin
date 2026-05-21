/** @jsxRuntime classic */ /** @jsx React.createElement */
/* global React, OPHAMIN, Icon, formatNum, Glossary */
// Roadmap — the 7-phase Kimera autonomous campaign as a steerable surface.
// Mirrors ROADMAP_2026_05_18.md in the Kimera-SWM-System repo.

const { useState: useRmState } = React;

const ROADMAP = [
  {
    id: 0, name: 'Pre-flight bootstrap', status: 'validated',
    question: 'Is the substrate ready to execute the roadmap?',
    scenario: 'roadmap-phase0-bootstrap',
    sub: [
      { label: 'Ophamin venv reachable',           pass: true },
      { label: 'BGE-M3 lazy-loads + encodes',      pass: true },
      { label: 'ArachneProtocol uses BGE-M3',      pass: true },
      { label: '5-cycle Kimera smoke',             pass: true },
      { label: 'Hardening green on touched files', pass: true },
      { label: 'Pre-existing failures inventory',  pass: true },
    ],
    branch: 'ALL PASS → Phase 1',
    proof_id: 'ph0b2f7a3c91d4e5...',
  },
  {
    id: 1, name: 'Re-baseline on BGE-M3', status: 'running',
    question: 'What is the substrate\u2019s actual current behavior on BGE-M3?',
    note: 'FastText eradicated. Family BB/CC/DD numbers are historical-only.',
    sub: [
      { scenario: 'bb1-bge-m3-baseline',           label: 'BB1 held-out semantic discrimination', threshold: 'separation > +0.10 · CI lower > 0', observed: '+0.142 · CI [+0.118, +0.171]', verdict: 'validated' },
      { scenario: 'ev-39-bge-replication',         label: 'EV-39 trilogy halt-mode replication',  threshold: '\u2265 6/8 within 1\u03c3 of EV-39c', observed: '5/8 within 1\u03c3', verdict: 'inconclusive' },
      { scenario: 'substrate-emission-distribution-bge', label: 'Substrate emission distribution', threshold: '\u2265 250 unique · \u2265 4/5 internal-event kinds', observed: 'running', verdict: 'pending' },
    ],
    branch: 'ALL VALIDATED \u2192 Phase 2 · 1a REFUTED \u2192 halt · 1b PARTIAL \u2192 pin · 1c PARTIAL \u2192 diagnose',
  },
  {
    id: 2, name: 'Multi-modal feedback loop activation', status: 'pending',
    question: 'Do dormant image/audio paths produce measurable emit contribution on real Kaido inputs?',
    scenario: 'multimodal-feedback-loop-activation',
    threshold: 'image-channel \u2265 10% · field/audio \u2265 10% · crash-count = 0',
    branch: 'VALIDATED \u2192 Phase 3 · PARTIAL \u2192 pin failed channel · REFUTED \u2192 dormant by deeper reasons',
  },
  {
    id: 3, name: 'Cross-cycle temporal pair extraction', status: 'pending',
    question: 'Do same-canonical observations across cycles form a discriminative pair signal?',
    scenario: 'cross-cycle-pair-trainability',
    threshold: 'cross-cycle-only sep \u2265 +0.10 (vs L3-only +0.115)',
    branch: 'VALIDATED \u2192 canonical Path A input · INFORMATIVE \u2192 opt-in · REFUTED \u2192 delete helper',
  },
  {
    id: 4, name: 'BGE-native concept expansion', status: 'pending',
    question: 'Can BGE-native expansion restore substrate graph size to \u2265 6 concepts on short prompts?',
    scenario: 'bge-native-concept-expansion',
    threshold: '8/8 _DIVERSE_PROMPTS produce \u2265 6 concepts',
    branch: 'VALIDATED \u2192 lives in substrate · PARTIAL \u2192 tune candidate corpus · REFUTED \u2192 revert',
  },
  {
    id: 5, name: 'GWF Family W', status: 'pending',
    question: 'Does embedding-based context analysis reduce GWF false-positives on legitimate prose?',
    note: 'Owner-pinned 2026-05-17 \u00b7 4 W-probes',
    sub: [
      { scenario: 'gwf-family-w-1-calibration', label: 'Calibration',            threshold: '\u2265 5 paired contexts measurable',         verdict: 'pending' },
      { scenario: 'gwf-family-w-2-separation',  label: 'MiniLM/BGE separation',  threshold: 'AUC \u2265 0.80',                              verdict: 'pending' },
      { scenario: 'gwf-family-w-3-integration', label: 'Integration',            threshold: 'wired without crash + per-call latency pin',  verdict: 'pending' },
      { scenario: 'gwf-family-w-4-fp-reduction',label: 'Empirical FP-rate',      threshold: '\u2265 30% FP reduction · 0 false-negatives', verdict: 'pending' },
    ],
    branch: 'ALL VALIDATED \u2192 Family W lands · ANY REFUTED \u2192 halt + diagnose',
  },
  {
    id: 6, name: 'Small mysteries + Pattern-P decisions', status: 'pending',
    question: 'Characterize small mysteries surfaced earlier; surface options to owner.',
    sub: [
      { scenario: '6a-emotion-prefix-audit',     label: 'emotion_* extractor prefix audit', kind: 'observability-only' },
      { scenario: '6b-tempo-filter-mystery',     label: 'tempo silent-drop mystery',        kind: 'bug-or-principle?'   },
      { scenario: '6c-quantum-eq-synth-patternp',label: 'QuantumEquationSynthesizer Pattern-P', kind: 'rename/refactor/disclaim — owner picks' },
    ],
  },
  {
    id: 7, name: 'Path A re-open feasibility', status: 'pending',
    question: 'After Phases 2/3/4, is the substrate producing pair-volume in the 10\u2074+ range?',
    scenario: 'path-a-pair-volume-feasibility',
    threshold: '\u2265 10,000 unique pairs across all sources in 100-cycle run',
    branch: 'VALIDATED \u2192 Path A v4 campaign · PARTIAL/REFUTED \u2192 Path A pinned',
  },
];

function RoadmapScreen({ onNavToProofs }) {
  const [selected, setSelected] = useRmState(1);
  const phase = ROADMAP.find(p => p.id === selected);

  const overallStats = {
    validated: ROADMAP.filter(p => p.status === 'validated').length,
    running:   ROADMAP.filter(p => p.status === 'running').length,
    pending:   ROADMAP.filter(p => p.status === 'pending').length,
  };

  return (
    <div className="content-inner page">
      <div className="page-header">
        <div>
          <h1 className="page-title">Roadmap</h1>
          <div className="page-subtitle mono" style={{ whiteSpace: 'nowrap' }}>
            The 7-phase Kimera campaign in flight. Every measurement is Ophamin-signed before commit.
          </div>
        </div>
        <div className="page-actions">
          <span className="live-pill"><span className="dot"></span>Live execution</span>
          <button className="btn"><Icon name="download" size={13}/> Export DD snapshot</button>
        </div>
      </div>

      <div className="roadmap-stats">
        <div><span className="micro">VALIDATED</span><span className="mono tnum" style={{ color: 'var(--validated)', fontSize: 22 }}>{overallStats.validated}</span></div>
        <div><span className="micro">IN FLIGHT</span><span className="mono tnum" style={{ color: 'var(--accent)', fontSize: 22 }}>{overallStats.running}</span></div>
        <div><span className="micro">PENDING</span><span className="mono tnum" style={{ color: 'var(--text-muted)', fontSize: 22 }}>{overallStats.pending}</span></div>
        <div style={{ flex: 1 }}/>
        <div><span className="micro">SUBSTRATE STATE</span><span className="mono" style={{ fontSize: 13 }}>BGE-M3 @ 6e4477ebb</span></div>
        <div><span className="micro">FAMILY</span><span className="mono" style={{ fontSize: 13, color: 'var(--accent)' }}>EE (roadmap)</span></div>
      </div>

      <div className="roadmap-layout">
        <aside className="roadmap-rail">
          <div className="micro" style={{ padding: '8px 12px' }}>PHASES</div>
          {ROADMAP.map(p => (
            <div key={p.id}
              className={'roadmap-phase-row' + (selected === p.id ? ' active' : '')}
              onClick={() => setSelected(p.id)}>
              <span className={'roadmap-phase-num roadmap-phase-' + p.status}>{p.id}</span>
              <div style={{ flex: 1, minWidth: 0 }}>
                <div style={{ fontSize: 12, fontWeight: 500, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>{p.name}</div>
                <div style={{ fontSize: 10, color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.06em', marginTop: 1 }}>{p.status}</div>
              </div>
            </div>
          ))}
        </aside>

        <div className="card" style={{ overflow: 'auto' }}>
          <div className="card-header">
            <div>
              <div className="card-title">Phase {phase.id} \u00b7 {phase.name}</div>
              <div style={{ fontSize: 11, color: 'var(--text-muted)', marginTop: 2, fontStyle: 'italic' }}>{phase.question}</div>
            </div>
            <span className={'verdict-pill ' + (phase.status === 'validated' ? 'validated' : phase.status === 'running' ? 'inconclusive' : 'inconclusive')} style={phase.status === 'pending' ? { color: 'var(--text-muted)', background: 'var(--bg-surface-2)', borderColor: 'var(--border)' } : null}>
              <span className="dot"></span>{phase.status}
            </span>
          </div>

          <div style={{ padding: 18 }}>
            {phase.note && (
              <div style={{ padding: '10px 12px', background: 'var(--bg-base)', borderLeft: '3px solid var(--accent)', borderRadius: 'var(--r-sm)', marginBottom: 14, fontSize: 12, color: 'var(--text-secondary)', lineHeight: 1.55 }}>
                {phase.note}
              </div>
            )}

            {phase.scenario && !phase.sub && (
              <div style={{ background: 'var(--bg-base)', border: '1px solid var(--border)', borderRadius: 'var(--r-sm)', padding: 12, marginBottom: 14 }}>
                <div className="micro" style={{ marginBottom: 6 }}>WHAT THIS PROVES</div>
                <div className="mono" style={{ fontSize: 13, color: 'var(--accent)', fontWeight: 500 }}>{phase.scenario}</div>
                {phase.threshold && (
                  <>
                    <div className="micro" style={{ marginTop: 10, marginBottom: 4 }}>
                      <Glossary term="preregistration"><span>PASS WHEN</span></Glossary>
                    </div>
                    <div className="mono" style={{ fontSize: 12, color: 'var(--text-primary)' }}>{phase.threshold}</div>
                  </>
                )}
              </div>
            )}

            {phase.sub && (
              <div style={{ marginBottom: 14 }}>
                <div className="micro" style={{ marginBottom: 8 }}>
                  {phase.id === 0 ? 'CHECKS TO PASS' : phase.id === 6 ? 'TASKS' : 'WHAT THIS PROVES'}
                </div>
                <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
                  {phase.sub.map((s, i) => (
                    <div key={i} className="roadmap-sub-row">
                      <span className={'roadmap-sub-icon ' + (s.verdict || (s.pass ? 'validated' : s.pass === false ? 'refuted' : 'pending'))}>
                        {(s.verdict === 'validated' || s.pass) && <Icon name="check" size={11}/>}
                        {s.verdict === 'refuted' && <Icon name="x" size={11}/>}
                        {s.verdict === 'inconclusive' && '?'}
                        {(s.verdict === 'pending' || s.verdict === undefined) && s.pass === undefined && '\u2022'}
                      </span>
                      <div style={{ flex: 1, minWidth: 0 }}>
                        <div className="mono" style={{ fontSize: 12, color: 'var(--accent)', fontWeight: 500 }}>{s.scenario || s.label}</div>
                        {s.scenario && <div style={{ fontSize: 11.5, color: 'var(--text-secondary)', marginTop: 2 }}>{s.label}</div>}
                        {s.threshold && (
                          <div style={{ marginTop: 4, display: 'grid', gridTemplateColumns: '90px 1fr', gap: '2px 10px', fontSize: 11 }}>
                            <span className="mono faint">threshold</span><span className="mono">{s.threshold}</span>
                            {s.observed && <><span className="mono faint">observed</span><span className="mono" style={{ color: s.verdict === 'validated' ? 'var(--validated)' : s.verdict === 'refuted' ? 'var(--refuted)' : s.verdict === 'inconclusive' ? 'var(--inconclusive)' : 'var(--text-muted)' }}>{s.observed}</span></>}
                          </div>
                        )}
                        {s.kind && <div className="mono" style={{ fontSize: 10, color: 'var(--text-muted)', marginTop: 2 }}>{s.kind}</div>}
                      </div>
                      {s.verdict && s.verdict !== 'pending' && (
                        <button className="btn ghost" style={{ fontSize: 11 }} onClick={() => onNavToProofs && onNavToProofs(null)}>
                          <Icon name="external" size={11}/> Proof
                        </button>
                      )}
                    </div>
                  ))}
                </div>
              </div>
            )}

            {phase.branch && (
              <div style={{ padding: '10px 12px', background: 'var(--accent-soft)', borderLeft: '3px solid var(--accent)', borderRadius: 'var(--r-sm)', fontSize: 12, fontFamily: 'JetBrains Mono, monospace', lineHeight: 1.65, color: 'var(--text-primary)' }}>
                <div className="micro" style={{ color: 'var(--accent)', marginBottom: 4 }}>WHAT HAPPENS NEXT</div>
                {phase.branch}
              </div>
            )}

            <div style={{ display: 'flex', gap: 6, marginTop: 14, flexWrap: 'wrap' }}>
              <button className="btn primary" style={{ fontSize: 12 }}><Icon name="play" size={12}/> Run phase</button>
              <button className="btn" style={{ fontSize: 12 }}><Icon name="copy" size={12}/> Copy CLI</button>
              <button className="btn" style={{ fontSize: 12 }}><Icon name="external" size={12}/> Journal entry</button>
              {phase.proof_id && (
                <div style={{ marginLeft: 'auto', fontSize: 10, color: 'var(--text-muted)', fontFamily: 'JetBrains Mono, monospace', alignSelf: 'center' }}>
                  proof_id: {phase.proof_id}
                </div>
              )}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

window.RoadmapScreen = RoadmapScreen;
