/** @jsxRuntime classic */ /** @jsx React.createElement */
/* global React, OPHAMIN, Icon */

// ControlRoomScreen — the MANAGE facet, with an INFRA sub-facet for the
// machinery layer (the medium Kimera runs on).
//
//  • Manage: is the substrate operational, at which commit, which cognitive
//    surfaces are reachable right now — grounded in the real adapter probe
//    (/managing/status). Fetched ON-DEMAND because probing imports Kimera in a
//    subprocess; never blocks console load. Nothing fabricated.
//  • Infra: Parameters reads the live config surface (/configuring/, the same
//    one the Configure screen exposes in full); Containers / Databases / Logs
//    are honest "not wired" scaffolds — real when their introspection backends
//    exist, never fabricated. Panels come from control-infra.jsx.
function ControlRoomScreen() {
  const D = OPHAMIN;
  const [facet, setFacet] = React.useState('manage');
  const [infraTab, setInfraTab] = React.useState('parameters');
  const [st, setSt] = React.useState(D.substrateStatus && D.substrateStatus.targets ? D.substrateStatus : null);
  const [loading, setLoading] = React.useState(!st);

  React.useEffect(() => {
    let alive = true;
    const base = window.OPHAMIN_API_BASE || '';
    setLoading(true);
    fetch(base + '/managing/status', { headers: { accept: 'application/json' } })
      .then((r) => r.json())
      .then((data) => { if (alive) { setSt(data); D.substrateStatus = data; setLoading(false); } })
      .catch(() => { if (alive) { setSt({ configured: false, message: 'probe failed' }); setLoading(false); } });
    return () => { alive = false; };
  }, []);

  const targets = (st && st.targets) || [];
  const ready = !!(st && st.ready);
  const readyColor = ready ? 'var(--validated, #2dd4bf)' : 'var(--refuted, #ef5b5b)';
  const rate = st && typeof st.health_rate === 'number' ? st.health_rate : 0;

  const FACETS = [{ id: 'manage', label: 'Manage' }, { id: 'infra', label: 'Infra' }];
  const INFRA_TABS = [
    { id: 'parameters', label: 'Parameters' },
    { id: 'containers', label: 'Containers' },
    { id: 'databases', label: 'Databases' },
    { id: 'logs', label: 'Logs' },
  ];
  const InfraPanel = {
    parameters: window.ParametersPanel,
    containers: window.ContainersPanel,
    databases: window.DatabasesPanel,
    logs: window.LogsPanel,
  }[infraTab];

  return (
    <div className="content-inner page">
      <div className="page-header">
        <div>
          <h1 className="page-title">Control Room</h1>
          <div className="page-subtitle mono">
            {facet === 'infra'
              ? 'Machinery — the medium Kimera runs on. Live config, plus container / data / log scaffolds.'
              : 'Live Kimera substrate status — operability + per-surface health, from the real probe.'}
          </div>
        </div>
        <div className="page-actions">
          <div style={{ display: 'flex', gap: 6 }}>
            {FACETS.map((f) => (
              <button key={f.id} className={'scn-tier-pill' + (facet === f.id ? ' active' : '')} onClick={() => setFacet(f.id)}>{f.label}</button>
            ))}
          </div>
          {facet === 'manage' && (
            <span className="live-pill" style={{ color: readyColor }}>
              <span className="dot" style={{ background: readyColor }}></span>
              {!st || st.configured === false ? 'not connected' : ready ? 'operational' : 'not ready'}
            </span>
          )}
        </div>
      </div>

      {facet === 'infra' ? (
        <div>
          <div className="agent-banner">
            <Icon name="cpu" size={16}/>
            <div>
              The <b>machinery layer</b> — the medium Kimera runs on. <b>Parameters</b> reads the
              live config surface (the same one the Configure screen exposes in full). Containers,
              data, and logs are honest scaffolds: Ophamin observes proofs + substrate health, and
              these become real when their introspection backends are wired — never fabricated.
            </div>
          </div>
          <div style={{ display: 'flex', gap: 6, margin: '0 0 14px', flexWrap: 'wrap' }}>
            {INFRA_TABS.map((t) => (
              <button key={t.id} className={'scn-tier-pill' + (infraTab === t.id ? ' active' : '')} onClick={() => setInfraTab(t.id)}>{t.label}</button>
            ))}
          </div>
          {InfraPanel
            ? <InfraPanel perspective="kimera"/>
            : <div style={{ padding: 18, color: 'var(--text-muted)', fontSize: 13 }}>panel unavailable</div>}
        </div>
      ) : loading || !st ? (
        <div style={{ padding: 20, color: 'var(--text-muted)', fontSize: 13 }}>
          <div className="mono" style={{ marginBottom: 8, color: 'var(--text-secondary)' }}>Probing the live Kimera substrate…</div>
          Importing each cognitive surface in a subprocess — this takes a few seconds.
        </div>
      ) : (
        <div>
          <div className="agent-banner">
            <Icon name="cpu" size={16}/>
            <div>
              The <b>Manage facet</b>. Ophamin probes the connected Kimera substrate — importing each cognitive surface — and reports what's reachable <i>right now</i>. Because Kimera is under active development, a partly-broken substrate is shown honestly (per-surface ok / error), never assumed healthy.
            </div>
          </div>

          {st.configured === false ? (
            <div style={{ padding: 20, color: 'var(--text-muted)', fontSize: 13 }}>
              No Kimera substrate connected. Set <span className="mono">OPHAMIN_KIMERA_REPO</span> so Ophamin can probe it.
              {st.message ? <div className="mono faint" style={{ marginTop: 6, fontSize: 11 }}>{st.message}</div> : null}
            </div>
          ) : (
            <div style={{ display: 'grid', gridTemplateColumns: '1fr', gap: 14 }}>
              {/* Substrate identity + readiness */}
              <div className="card" style={{ padding: 16 }}>
                <div style={{ display: 'flex', gap: 28, flexWrap: 'wrap', alignItems: 'baseline' }}>
                  <div>
                    <div className="micro">SUBSTRATE</div>
                    <div className="mono" style={{ fontSize: 16, color: 'var(--text-primary)' }}>{st.substrate || 'kimera-swm'}</div>
                  </div>
                  <div>
                    <div className="micro">COMMIT</div>
                    <div className="mono" style={{ fontSize: 14, color: 'var(--text-primary)' }}>{(st.git_commit || '—').slice(0, 12)}</div>
                  </div>
                  <div>
                    <div className="micro">COGNITIVE SURFACES REACHABLE</div>
                    <div className="mono" style={{ fontSize: 16, color: readyColor }}>{st.n_healthy || 0} / {st.n_targets || 0}</div>
                  </div>
                  <div>
                    <div className="micro">RUNNER</div>
                    <div className="mono" style={{ fontSize: 14, color: st.runner_ok ? 'var(--validated)' : 'var(--refuted)' }}>{st.runner_ok ? 'ok' : 'down'}</div>
                  </div>
                </div>
                {/* health bar */}
                <div style={{ marginTop: 14, height: 8, background: 'var(--surface-2, #161b22)', borderRadius: 'var(--r-sm)', overflow: 'hidden' }}>
                  <div style={{ width: (rate * 100) + '%', height: '100%', background: readyColor, opacity: 0.85 }}></div>
                </div>
                {st.error ? <div className="micro" style={{ color: 'var(--refuted)', marginTop: 10 }}>runner error: {st.error}</div> : null}
              </div>

              {/* Per-cognitive-surface health */}
              <div className="card" style={{ overflow: 'hidden' }}>
                <div className="card-header">
                  <div className="card-title">Cognitive surfaces</div>
                  <span className="chip">{targets.length}</span>
                </div>
                <div style={{ padding: 16, display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(180px, 1fr))', gap: 8 }}>
                  {targets.map((t) => {
                    const ok = t.import_ok;
                    const c = ok ? 'var(--validated, #2dd4bf)' : 'var(--refuted, #ef5b5b)';
                    return (
                      <div key={t.name} title={ok ? '' : t.error}
                        style={{ border: '1px solid var(--border)', borderLeft: '3px solid ' + c, borderRadius: 'var(--r-sm)', padding: '8px 10px' }}>
                        <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                          <span className="dot" style={{ background: c }}></span>
                          <span className="mono" style={{ fontSize: 12, color: 'var(--text-primary)' }}>{t.name}</span>
                        </div>
                        {!ok && t.error ? <div className="mono faint" style={{ fontSize: 9, marginTop: 4, maxHeight: 28, overflow: 'hidden' }}>{t.error}</div> : null}
                      </div>
                    );
                  })}
                </div>
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

window.ControlRoomScreen = ControlRoomScreen;
