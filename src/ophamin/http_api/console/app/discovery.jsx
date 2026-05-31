/** @jsxRuntime classic */ /** @jsx React.createElement */
/* global React, Icon */
// Discovery — the substrate's output-field contract, as reference.
//
// NO FABRICATION (2026-05-31): this is the documented contract of what
// Takwin.run emits each cycle — what `ophamin discover <kimera-repo>` mines.
// It is REFERENCE, not a live read. The screen used to pose as live ("watching"
// toggle, "exposes N fields today", a hardcoded current-commit, and a
// fabricated "what changed since last time" diff) — all removed. Live mining /
// diff / watch run via the CLI (shown below) and aren't wired into the console.

const { useState: useDiState, useMemo: useDiMemo } = React;

const FIELD_SCHEMA = [
  { path: 'response',                  group: 'output',     type: 'str',         cardinality: 'always',  desc: 'Plain-language response from CognitiveInterpreter' },
  { path: 'concepts',                  group: 'output',     type: 'list[str]',   cardinality: 'always',  desc: 'Concepts extracted from the input' },
  { path: 'trajectory',                group: 'cognitive',  type: 'list[Step]',  cardinality: 'always',  desc: 'Step-by-step walk on the manifold (~12 steps)' },
  { path: 'trajectory[*].mode',        group: 'cognitive',  type: 'enum',        cardinality: 'always',  desc: 'M1 COMMIT · M2 HALT · M3 ROLLBACK · M4 LATERAL LEAP' },
  { path: 'trajectory[*].geoid_prime', group: 'cognitive',  type: 'int',         cardinality: 'always',  desc: 'Prime assigned to the visited geoid via Arachne' },
  { path: 'phi',                       group: 'metrics',    type: 'float',       cardinality: 'always',  desc: 'Integrated Information (IIT) measure' },
  { path: 'graph_coherence',           group: 'metrics',    type: 'float',       cardinality: 'always',  desc: 'Coherence across the substrate graph this cycle' },
  { path: 'prime_chain',               group: 'metrics',    type: 'list[int]',   cardinality: 'always',  desc: 'The cycle’s canonical prime chain' },
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

  return (
    <div className="content-inner page" style={{ maxWidth: 1100 }}>
      <div className="page-header">
        <div>
          <h1 className="page-title">Discovery</h1>
          <div className="page-subtitle">Kimera's output-field contract — what every cycle emits. Reference, not a live read; live mining runs via <span className="mono">ophamin discover</span> (below) and isn't wired into the console yet.</div>
        </div>
        <div className="page-actions">
          <span className="live-pill muted"><span className="dot"></span>reference</span>
        </div>
      </div>

      {/* Reference hero — count only, nothing computed live */}
      <div className="discovery-hero">
        <div className="discovery-hero-headline">
          The output contract documents <span className="discovery-hero-num">{FIELD_SCHEMA.length}</span> fields, grouped by area.
        </div>
        <div className="discovery-hero-deltas">
          <span style={{ fontSize: 12, color: 'var(--text-muted)' }}>
            A live snapshot/diff against a connected substrate isn't wired into the console — nothing here is measured live. Use the CLI for live mining.
          </span>
        </div>
      </div>

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

      {/* Power-user expandable — the real CLI that mines/diffs/watches live */}
      <div className="card" style={{ marginTop: 16 }}>
        <div className="card-header" onClick={() => setShowPowerUser(v => !v)} style={{ cursor: 'pointer' }}>
          <div className="card-title">
            <Icon name={showPowerUser ? 'chevronD' : 'chevronR'} size={12}/>{' '}
            Live mining · CLI equivalents
          </div>
          <span className="micro">SEEING/ WHEEL</span>
        </div>
        {showPowerUser && (
          <div style={{ padding: 14, display: 'grid', gridTemplateColumns: 'repeat(2, 1fr)', gap: 10 }}>
            <CliCard cmd="ophamin discover <kimera-repo>"        desc="One-shot field-schema mining (live)"/>
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
