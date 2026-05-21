/** @jsxRuntime classic */ /** @jsx React.createElement */
/* global React, OPHAMIN, Icon, Glossary */
// Discovery — clean & narrative. What does the substrate currently expose?

const { useState: useDiState, useMemo: useDiMemo } = React;

const FIELD_SCHEMA = [
  { path: 'response',                  group: 'output',     type: 'str',         cardinality: 'always',  desc: 'Plain-language response from CognitiveInterpreter' },
  { path: 'concepts',                  group: 'output',     type: 'list[str]',   cardinality: 'always',  desc: 'Concepts extracted from the input' },
  { path: 'trajectory',                group: 'cognitive',  type: 'list[Step]',  cardinality: 'always',  desc: 'Step-by-step walk on the manifold (~12 steps)' },
  { path: 'trajectory[*].mode',        group: 'cognitive',  type: 'enum',        cardinality: 'always',  desc: 'M1 COMMIT · M2 HALT · M3 ROLLBACK · M4 LATERAL LEAP' },
  { path: 'trajectory[*].geoid_prime', group: 'cognitive',  type: 'int',         cardinality: 'always',  desc: 'Prime assigned to the visited geoid via Arachne' },
  { path: 'phi',                       group: 'metrics',    type: 'float',       cardinality: 'always',  desc: 'Integrated Information (IIT) measure' },
  { path: 'graph_coherence',           group: 'metrics',    type: 'float',       cardinality: 'always',  desc: 'Coherence across the substrate graph this cycle' },
  { path: 'prime_chain',               group: 'metrics',    type: 'list[int]',   cardinality: 'always',  desc: 'The cycles canonical prime chain' },
  { path: 'substrate_state_stamp',     group: 'identity',   type: 'str',         cardinality: 'always',  desc: 'Content-hash of substrate state when cycle ran' },
  { path: 'scar_formed',               group: 'memory',     type: 'bool',        cardinality: 'always',  desc: 'true if contradiction-gate fired and a scar was deposited' },
  { path: 'cycle_seconds',             group: 'engineering',type: 'float',       cardinality: 'always',  desc: 'Wall-time spent in Takwin.run()' },
  { path: 'raw.gwf_verdict',           group: 'security',   type: 'enum',        cardinality: 'always',  desc: 'allow | block — first-line adversarial filter' },
  { path: 'raw.gwf_features',          group: 'security',   type: 'dict',        cardinality: 'always',  desc: '12 entity-feature scores fed into the GWF' },
  { path: 'raw.manipulation_score',    group: 'security',   type: 'float',       cardinality: 'always',  desc: 'Manipulation-detector score (downstream of GWF)' },
  { path: 'raw.dissonance_active',     group: 'cognitive',  type: 'bool',        cardinality: 'always',  desc: 'true on dissonance-firing cycles' },
  { path: 'raw.walker_sustained',      group: 'cognitive',  type: 'bool',        cardinality: 'always',  desc: 'true if the walker held traversal for N hops' },
  { path: 'raw.cross_arm_jaccard',     group: 'metrics',    type: 'float',       cardinality: 'sometimes', desc: 'Cross-modal coherence across Piovra arms' },
  { path: 'raw.tonus_ratio',           group: 'metrics',    type: 'float',       cardinality: 'sometimes', desc: 'Tonus conservation ratio' },
  { path: 'raw.sinew_m4_ratio',        group: 'metrics',    type: 'float',       cardinality: 'sometimes', desc: 'Walker M4 conservation ratio under perturbation' },
  { path: 'raw.alexandria_keys',       group: 'memory',     type: 'list[str]',   cardinality: 'sometimes', desc: 'Alexandria fused keys persisting this cycle' },
  { path: 'raw.proprio_coverage',      group: 'cognitive',  type: 'float',       cardinality: 'always',  desc: 'Fraction of substrate fields proprio can name' },
  { path: 'raw.canonical_emit_stream', group: 'output',     type: 'list',        cardinality: 'always',  desc: 'Canonicals emitted this cycle, by channel' },
  { path: 'identity.ophamin_version',  group: 'identity',   type: 'str',         cardinality: 'always',  desc: 'Ophamin framework version' },
  { path: 'identity.substrate_git_commit', group: 'identity', type: 'str',       cardinality: 'always',  desc: 'Kimera-SWM substrate commit observed' },
];

const SNAPSHOT_DIFFS = [
  { kind: 'added',     path: 'raw.bge_m3_encoding_ms',     note: 'New with the BGE-M3 swap (6e4477eb).' },
  { kind: 'added',     path: 'raw.cross_cycle_pair_count', note: 'New from Phase 3 cross-cycle helper.' },
  { kind: 'removed',   path: 'raw.fasttext_vocab_hit',     note: 'FastText eradicated 2026-05-17.' },
  { kind: 'removed',   path: 'raw.fasttext_oov_rate',      note: 'FastText eradicated 2026-05-17.' },
  { kind: 'type',      path: 'phi',                        note: 'Precision normalized (was sometimes float32).' },
  { kind: 'cardinality', path: 'raw.cross_arm_jaccard',    note: 'Now measured-only-when-present (was always pre-Stage 39).' },
];

const GROUP_META = {
  output:      { color: '#5e9eff', label: 'OUTPUT' },
  cognitive:   { color: '#2dd4bf', label: 'COGNITIVE' },
  metrics:     { color: '#8b95e8', label: 'METRICS' },
  identity:    { color: '#94a3b8', label: 'IDENTITY' },
  memory:      { color: '#ffa726', label: 'MEMORY' },
  engineering: { color: '#4ade80', label: 'ENGINEERING' },
  security:    { color: '#ef5b5b', label: 'SECURITY' },
};

function DiscoveryScreen() {
  const [watching, setWatching] = useDiState(false);
  const [filter, setFilter] = useDiState('');
  const [showPowerUser, setShowPowerUser] = useDiState(false);

  const filtered = useDiMemo(() => {
    if (!filter) return FIELD_SCHEMA;
    const q = filter.toLowerCase();
    return FIELD_SCHEMA.filter(f => f.path.toLowerCase().includes(q) || f.desc.toLowerCase().includes(q));
  }, [filter]);

  const grouped = useDiMemo(() => {
    const m = new Map();
    for (const f of filtered) {
      if (!m.has(f.group)) m.set(f.group, []);
      m.get(f.group).push(f);
    }
    return [...m.entries()];
  }, [filtered]);

  const counts = {
    added:   SNAPSHOT_DIFFS.filter(d => d.kind === 'added').length,
    removed: SNAPSHOT_DIFFS.filter(d => d.kind === 'removed').length,
    changed: SNAPSHOT_DIFFS.filter(d => d.kind === 'type' || d.kind === 'cardinality').length,
  };

  return (
    <div className="content-inner page" style={{ maxWidth: 1100 }}>
      <div className="page-header">
        <div>
          <h1 className="page-title">Discovery</h1>
          <div className="page-subtitle">What the substrate exposes right now, and what has changed since you last looked.</div>
        </div>
        <div className="page-actions">
          <span className={'live-pill' + (watching ? '' : ' muted')}>
            <span className="dot"></span>{watching ? 'watching' : 'snapshot'}
          </span>
          <button className="btn" onClick={() => setWatching(w => !w)}>
            <Icon name={watching ? 'x' : 'eye'} size={13}/> {watching ? 'Stop watch' : 'Start watch'}
          </button>
        </div>
      </div>

      {/* Narrative hero */}
      <div className="discovery-hero">
        <div className="discovery-hero-headline">
          The substrate exposes <span className="discovery-hero-num">{FIELD_SCHEMA.length}</span> fields today.
          {(counts.added + counts.removed + counts.changed) > 0 && <> Since the last snapshot, <span className="discovery-hero-num discovery-hero-num-warn">{counts.added + counts.removed + counts.changed}</span> have changed.</>}
        </div>
        <div className="discovery-hero-deltas">
          {counts.added   > 0 && <span className="discovery-hero-delta added"><Icon name="check" size={11}/> {counts.added} added</span>}
          {counts.removed > 0 && <span className="discovery-hero-delta removed"><Icon name="x"     size={11}/> {counts.removed} removed</span>}
          {counts.changed > 0 && <span className="discovery-hero-delta changed"><Icon name="refresh" size={11}/> {counts.changed} changed</span>}
          <span style={{ flex: 1 }}/>
          <span className="mono" style={{ fontSize: 11, color: 'var(--text-muted)' }}>kimera-swm @ 6e4477eb</span>
        </div>
      </div>

      {/* Changes since last snapshot — prominent, scrollable card */}
      {SNAPSHOT_DIFFS.length > 0 && (
        <div className="card" style={{ marginBottom: 20 }}>
          <div className="card-header">
            <div>
              <div className="card-title">What changed since last time</div>
              <div className="micro" style={{ marginTop: 2 }}>SINCE 2026-05-12</div>
            </div>
            <button className="btn ghost" style={{ fontSize: 11 }}><Icon name="download" size={11}/> Export diff</button>
          </div>
          <div style={{ padding: 14, display: 'flex', flexDirection: 'column', gap: 8 }}>
            {SNAPSHOT_DIFFS.map((d, i) => (
              <div key={i} className={'discovery-diff-row discovery-diff-' + d.kind}>
                <span className={'discovery-diff-kind discovery-diff-kind-' + d.kind}>
                  {d.kind === 'added' && <Icon name="check" size={11}/>}
                  {d.kind === 'removed' && <Icon name="x" size={11}/>}
                  {(d.kind === 'type' || d.kind === 'cardinality') && <Icon name="refresh" size={11}/>}
                  <span>{d.kind}</span>
                </span>
                <span className="mono" style={{ fontSize: 12, color: 'var(--text-primary)' }}>{d.path}</span>
                <span style={{ flex: 1, fontSize: 12, color: 'var(--text-muted)' }}>{d.note}</span>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Field schema, grouped — clean and friendly */}
      <div className="card">
        <div className="card-header">
          <div>
            <div className="card-title">Every field, by area</div>
            <div className="micro" style={{ marginTop: 2 }}>WHAT KIMERA EMITS EVERY CYCLE</div>
          </div>
          <div style={{ position: 'relative' }}>
            <span style={{ position: 'absolute', left: 10, top: '50%', transform: 'translateY(-50%)', color: 'var(--text-muted)' }}>
              <Icon name="search" size={13}/>
            </span>
            <input className="input" style={{ paddingLeft: 30, height: 28, fontSize: 12, width: 240 }}
              placeholder="filter by name or description"
              value={filter} onChange={e => setFilter(e.target.value)}/>
          </div>
        </div>
        <div style={{ padding: '6px 0' }}>
          {grouped.map(([group, fields]) => {
            const meta = GROUP_META[group] || { label: group.toUpperCase(), color: 'var(--text-muted)' };
            return (
              <div key={group}>
                <div className="discovery-group-head">
                  <span className="discovery-group-dot" style={{ background: meta.color }}/>
                  <span>{meta.label}</span>
                  <span className="discovery-group-count">{fields.length}</span>
                </div>
                {fields.map(f => (
                  <div key={f.path} className="discovery-field-row">
                    <span className="mono" style={{ fontSize: 12, color: 'var(--text-primary)', minWidth: 240 }}>{f.path}</span>
                    <span className="mono" style={{ fontSize: 11, color: 'var(--text-muted)', minWidth: 80 }}>{f.type}</span>
                    {f.cardinality === 'sometimes' && <span className="discovery-cardinality-pill">sometimes</span>}
                    <span style={{ flex: 1, fontSize: 12, color: 'var(--text-secondary)' }}>{f.desc}</span>
                  </div>
                ))}
              </div>
            );
          })}
        </div>
      </div>

      {/* Power-user expandable */}
      <div className="card" style={{ marginTop: 16 }}>
        <div className="card-header" onClick={() => setShowPowerUser(v => !v)} style={{ cursor: 'pointer' }}>
          <div className="card-title">
            <Icon name={showPowerUser ? 'chevronD' : 'chevronR'} size={12}/>{' '}
            For power users · CLI equivalents
          </div>
          <span className="micro">SEEING/ WHEEL</span>
        </div>
        {showPowerUser && (
          <div style={{ padding: 14, display: 'grid', gridTemplateColumns: 'repeat(2, 1fr)', gap: 10 }}>
            <CliCard cmd="ophamin discover <kimera-repo>"        desc="One-shot field-schema mining"/>
            <CliCard cmd="ophamin discover-diff a.json b.json"   desc="Structural diff between two snapshots"/>
            <CliCard cmd="ophamin watch <kimera-repo>"           desc="Continuous re-discover + diff"/>
            <CliCard cmd="ophamin inventory <kimera-repo>"       desc="Primitive inventory"/>
          </div>
        )}
      </div>
    </div>
  );
}

function CliCard({ cmd, desc }) {
  return (
    <div style={{ background: 'var(--bg-base)', border: '1px solid var(--border)', borderRadius: 'var(--r-sm)', padding: 10 }}>
      <div className="mono" style={{ fontSize: 12, color: 'var(--accent)', fontWeight: 500 }}>{cmd}</div>
      <div style={{ fontSize: 11, color: 'var(--text-muted)', marginTop: 3 }}>{desc}</div>
    </div>
  );
}

window.DiscoveryScreen = DiscoveryScreen;
