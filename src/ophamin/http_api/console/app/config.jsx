/** @jsxRuntime classic */ /** @jsx React.createElement */
/* global React, OPHAMIN, Icon */

// ConfigScreen — the CONFIGURE facet. Ophamin manages Kimera's configuration:
// the env-var knob contract introspected statically from Kimera's source
// (app-level + substrate-tuning domain knobs), the effective values (secrets
// redacted), a provenance snapshot, and the config gate. Hydrated from
// /configuring/effective + /configuring/validate.
function ConfigScreen() {
  const D = OPHAMIN;
  const cfg = D.config || {};
  const effective = cfg.effective || [];
  const snap = cfg.snapshot || null;
  const violations = cfg.violations || [];

  // Group knobs by their config group.
  const byGroup = {};
  effective.forEach((k) => { (byGroup[k.group] = byGroup[k.group] || []).push(k); });
  const groups = Object.keys(byGroup).sort();

  const gateColor = cfg.valid === false ? 'var(--refuted, #ef5b5b)'
    : cfg.valid === true ? 'var(--validated, #2dd4bf)' : 'var(--text-muted)';

  return (
    <div className="content-inner page">
      <div className="page-header">
        <div>
          <h1 className="page-title">Configuration</h1>
          <div className="page-subtitle mono">Kimera's config knobs — introspected from source, secrets redacted, gated.</div>
        </div>
        <div className="page-actions">
          {snap && <span className="chip">{snap.n_knobs} knobs · {snap.n_overridden} overridden</span>}
        </div>
      </div>

      <div className="agent-banner">
        <Icon name="settings" size={16}/>
        <div>
          The <b>Configure facet</b>. Kimera's full env-var contract — app-level (database / api / system) and the <b>substrate-tuning domain knobs</b> (geoid / scar / thermodynamic / …) — parsed statically from source (no import, no run). Secrets show only <span className="mono">&lt;set&gt;</span> / <span className="mono">&lt;unset&gt;</span>. The snapshot ties a proof to the exact config that produced it.
        </div>
      </div>

      {!cfg.configured ? (
        <div style={{ padding: 20, color: 'var(--text-muted)', fontSize: 13 }}>
          No Kimera repo connected. Set <span className="mono">OPHAMIN_KIMERA_REPO</span> so Ophamin can read Kimera's config.
          {cfg.message ? <div className="mono faint" style={{ marginTop: 6, fontSize: 11 }}>{cfg.message}</div> : null}
        </div>
      ) : (
        <div style={{ display: 'grid', gridTemplateColumns: '1fr', gap: 14 }}>
          {/* Snapshot + config gate */}
          <div className="card" style={{ padding: 16 }}>
            <div style={{ display: 'flex', gap: 28, flexWrap: 'wrap', alignItems: 'baseline' }}>
              <div>
                <div className="micro">CONFIG SNAPSHOT (provenance)</div>
                <div className="mono" style={{ fontSize: 14, color: 'var(--text-primary)' }}>{snap ? snap.snapshot_id.slice(0, 16) : '—'}</div>
                <div className="mono faint" style={{ fontSize: 10 }}>secret-safe content hash · ties a proof to this exact config</div>
              </div>
              <div>
                <div className="micro">CONFIG GATE</div>
                <div className="mono" style={{ fontSize: 16, color: gateColor }}>
                  {cfg.valid === true ? 'valid' : cfg.valid === false ? `${violations.length} violation${violations.length === 1 ? '' : 's'}` : '—'}
                </div>
              </div>
            </div>
            {violations.length > 0 && (
              <div style={{ marginTop: 12 }}>
                {violations.map((v, i) => (
                  <div key={i} className="micro" style={{ color: v.severity === 'error' ? 'var(--refuted)' : 'var(--inconclusive)', marginTop: 4 }}>
                    [{(v.severity || '').toUpperCase()}] {v.env_var} — {v.message}
                  </div>
                ))}
              </div>
            )}
          </div>

          {/* Knobs grouped by config group */}
          {groups.map((g) => (
            <div key={g} className="card" style={{ overflow: 'hidden' }}>
              <div className="card-header">
                <div className="card-title" style={{ textTransform: 'capitalize' }}>{g.replace('_', ' ')}</div>
                <span className="chip">{byGroup[g].length}</span>
              </div>
              <div style={{ padding: '8px 16px 14px' }}>
                {byGroup[g].map((k) => (
                  <div key={k.env_var} style={{ display: 'flex', alignItems: 'baseline', gap: 10, padding: '4px 0', borderBottom: '1px solid var(--border)' }}>
                    <div className="mono" style={{ fontSize: 11, color: 'var(--text-primary)', flex: '0 0 320px', wordBreak: 'break-all' }}>
                      {k.secret && <span title="secret" style={{ marginRight: 4 }}>🔒</span>}
                      {k.env_var}
                    </div>
                    <div className="mono" style={{ fontSize: 11, color: k.is_default ? 'var(--text-muted)' : 'var(--accent, #2dd4bf)', flex: 1 }}>
                      {String(k.current)}
                      {!k.is_default && <span className="faint" style={{ fontSize: 9 }}> (override)</span>}
                    </div>
                    <div className="mono faint" style={{ fontSize: 9, flex: '0 0 44px', textAlign: 'right' }}>{k.value_type}</div>
                  </div>
                ))}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

window.ConfigScreen = ConfigScreen;
