/** @jsxRuntime classic */ /** @jsx React.createElement */
/* global React, Icon */
// Control Room — infrastructure panels (Parameters / Containers / Databases / Logs).
// Loaded after control.jsx; mounted into ControlRoomScreen.
//
// NO FABRICATION (2026-05-31): Parameters reads the live /configuring/ surface
// (source-scanned substrate env knobs + effective .env, read-only; mutation is
// CLI-gated by design). Containers / Databases / Logs show honest "not wired"
// states — Ophamin observes proofs + substrate health, it does not invent
// container stats, DB latencies, or substrate log lines.

const { useState: useInfraState } = React;

function ParametersPanel({ perspective }) {
  if (perspective === 'ophamin') {
    return (
      <div className="card cr-panel">
        <div className="card-header"><div className="card-title">Ophamin runtime parameters</div></div>
        <div style={{ padding: 18, fontSize: 13, color: 'var(--text-muted)', lineHeight: 1.6 }}>
          Ophamin's own runtime config (signing batch, sampler interval, workers…) isn't
          exposed over the API yet — manage it via the config file / CLI. Nothing is shown
          here rather than invent values.
        </div>
      </div>
    );
  }

  const [st, setSt] = useInfraState({ loading: true, configured: null, knobs: [], message: '' });
  React.useEffect(() => {
    let alive = true;
    const base = window.OPHAMIN_API_BASE || '';
    Promise.all([
      fetch(base + '/configuring/schema', { headers: { accept: 'application/json' } }).then(r => r.json()),
      fetch(base + '/configuring/effective', { headers: { accept: 'application/json' } }).then(r => r.json()),
    ]).then(([schema, eff]) => {
      if (!alive) return;
      if (!schema || !schema.configured) {
        setSt({ loading: false, configured: false, knobs: [], message: (schema && schema.message) || 'No substrate connected.' });
        return;
      }
      const values = {};
      (eff.effective || []).forEach(e => {
        values[e.env_var] = (e.value != null ? e.value : (e.effective != null ? e.effective : e.current));
      });
      const knobs = (schema.knobs || []).map(k => ({
        env_var: k.env_var, group: k.group || 'config', type: k.type, secret: k.is_secret,
        value: values[k.env_var] != null ? values[k.env_var] : k.default, def: k.default,
      }));
      setSt({ loading: false, configured: true, knobs, message: '' });
    }).catch(() => { if (alive) setSt({ loading: false, configured: false, knobs: [], message: 'config probe failed' }); });
    return () => { alive = false; };
  }, []);

  if (st.loading) {
    return <div className="card cr-panel"><div style={{ padding: 18, color: 'var(--text-muted)', fontSize: 13 }}>Reading the substrate's live config…</div></div>;
  }
  if (!st.configured) {
    return (
      <div className="card cr-panel">
        <div className="card-header"><div className="card-title">Kimera substrate parameters</div></div>
        <div style={{ padding: 18, fontSize: 13, color: 'var(--text-muted)', lineHeight: 1.6 }}>
          No Kimera substrate connected — set <span className="mono">OPHAMIN_KIMERA_REPO</span> and
          Ophamin reads its live config knobs (source-scanned env vars + effective <span className="mono">.env</span>).
          {st.message ? <div className="mono faint" style={{ marginTop: 8, fontSize: 11 }}>{st.message}</div> : null}
        </div>
      </div>
    );
  }

  const groups = {};
  st.knobs.forEach(k => { (groups[k.group] = groups[k.group] || []).push(k); });
  return (
    <div className="card cr-panel">
      <div className="card-header">
        <div>
          <div className="card-title">Kimera substrate parameters</div>
          <div className="micro" style={{ marginTop: 2 }}>LIVE · SOURCE-SCANNED KNOBS + EFFECTIVE .ENV · READ-ONLY HERE</div>
        </div>
        <span className="live-pill ok"><span className="dot"></span>{st.knobs.length} knobs</span>
      </div>
      <div style={{ padding: 16, display: 'grid', gap: 16 }}>
        {Object.keys(groups).sort().map(g => (
          <div key={g}>
            <div className="micro" style={{ marginBottom: 6 }}>{g}</div>
            <div style={{ display: 'grid', gap: 4 }}>
              {groups[g].map(k => (
                <div key={k.env_var} style={{ display: 'grid', gridTemplateColumns: '1fr auto', gap: 12, fontSize: 12, padding: '4px 0', borderBottom: '1px solid var(--border)' }}>
                  <span className="mono" style={{ color: 'var(--text-secondary)' }}>{k.env_var}</span>
                  <span className="mono" style={{ color: 'var(--text-primary)' }}>{k.secret ? '••••••' : String(k.value)}</span>
                </div>
              ))}
            </div>
          </div>
        ))}
      </div>
      <div style={{ padding: '12px 18px', borderTop: '1px solid var(--border)', fontSize: 12, color: 'var(--text-muted)' }}>
        Changes apply via the operator-gated CLI — <span className="mono" style={{ color: 'var(--text-secondary)' }}>ophamin config apply</span>. Config mutation is intentionally not exposed over HTTP.
      </div>
    </div>
  );
}

function NotWiredPanel({ title, children }) {
  return (
    <div className="cr-panel">
      <div className="card" style={{ padding: 20 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 8 }}>
          <Icon name="cpu" size={14}/>
          <div className="card-title">{title}</div>
        </div>
        <div style={{ fontSize: 13, color: 'var(--text-muted)', lineHeight: 1.6 }}>{children}</div>
      </div>
    </div>
  );
}

function ContainersPanel() {
  return (
    <NotWiredPanel title="Containers — not wired">
      Ophamin observes the substrate's signed proofs and live health (the Control Room
      probe), not the deploy stack. Orchestration — start / stop / scale — lives in{' '}
      <span className="mono">argocd</span> / <span className="mono">helm</span> by design;
      the observatory watches, it doesn't drive deploys. A read-only{' '}
      <span className="mono">docker ps</span> view could be added if useful — but no
      container stats are invented here.
    </NotWiredPanel>
  );
}

function DatabasesPanel() {
  return (
    <NotWiredPanel title="Databases — not wired">
      Live database introspection isn't connected. What's real surfaces elsewhere: the
      signed proof corpus (Proofs) and the vault scar counts (Overview). A live DB view
      would need a read-only introspection backend — until then, no sizes or latencies
      are invented here.
    </NotWiredPanel>
  );
}

function LogsPanel() {
  return (
    <NotWiredPanel title="Logs — not wired">
      Live log streaming isn't connected. The substrate's recorded behavior lives in the
      signed, re-performable proof corpus (Proofs) — not a transient tail. No log lines
      are fabricated here.
    </NotWiredPanel>
  );
}

window.ParametersPanel = ParametersPanel;
window.ContainersPanel = ContainersPanel;
window.DatabasesPanel  = DatabasesPanel;
window.LogsPanel       = LogsPanel;
