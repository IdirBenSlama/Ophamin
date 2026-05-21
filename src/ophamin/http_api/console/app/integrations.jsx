/** @jsxRuntime classic */ /** @jsx React.createElement */
/* global React, OPHAMIN, Icon */

// IntegrationsScreen — the "route, don't reinvent" hub. Ophamin wraps
// mature OSS (Grafana / MLflow / DVC / SARIF viewers / docs); rather than
// re-skin them, this screen routes to whichever the operator has wired up
// (via env vars). Live from /integrations; nothing configured by default.
function IntegrationsScreen() {
  const D = OPHAMIN;
  const items = D.integrations || [];
  const configured = items.filter(i => i.configured).length;
  const tealOr = (on, off) => (on ? 'var(--validated, #2dd4bf)' : off);

  return (
    <div className="content-inner page">
      <div className="page-header">
        <div>
          <h1 className="page-title">Integrations</h1>
          <div className="page-subtitle mono">Ophamin wraps mature open-source tools — each with its own UI. Rather than re-skin them, route to them. Bring your own.</div>
        </div>
        <div className="page-actions">
          <span className="chip">{configured} of {items.length} configured</span>
        </div>
      </div>

      <div className="agent-banner">
        <Icon name="external" size={16}/>
        <div>
          The Console owns the <b>signed-proof + falsifiable-claim + Kimera-substrate</b> spine. Everything else — metrics dashboards, run tracking, lineage graphs, static-analysis viewers, the docs site — is rendered better by the mature tool itself. Point Ophamin at yours with the env var on each card.
        </div>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(320px, 1fr))', gap: 14 }}>
        {items.length === 0 ? (
          <div style={{ padding: 20, color: 'var(--text-muted)', fontSize: 13 }}>
            No integration catalog available (backend not reached).
          </div>
        ) : items.map(it => (
          <div key={it.id} className="card" style={{ overflow: 'hidden' }}>
            <div className="card-header">
              <div className="card-title">{it.name}</div>
              <span className="live-pill" style={{ color: tealOr(it.configured, 'var(--text-muted)') }}>
                <span className="dot" style={{ background: tealOr(it.configured, 'var(--text-muted)') }}></span>
                {it.configured ? 'connected' : 'not configured'}
              </span>
            </div>
            <div style={{ padding: 16 }}>
              <div className="micro" style={{ marginBottom: 4 }}>REPLACES</div>
              <div style={{ fontSize: 12.5, color: 'var(--text-secondary)', marginBottom: 12 }}>{it.replaces}</div>
              <p style={{ fontSize: 12.5, lineHeight: 1.55, color: 'var(--text-secondary)', margin: '0 0 14px' }}>{it.description}</p>
              {it.configured ? (
                <a href={it.url} target="_blank" rel="noopener noreferrer" className="btn primary"
                  style={{ fontSize: 12, textDecoration: 'none', display: 'inline-flex', alignItems: 'center', gap: 6 }}>
                  Open in {it.name} <Icon name="external" size={12}/>
                </a>
              ) : (
                <div>
                  <div className="micro" style={{ marginBottom: 4 }}>TO WIRE</div>
                  <pre style={{ background: 'var(--bg-base)', border: '1px solid var(--border)', borderRadius: 'var(--r-sm)', padding: '8px 10px', fontFamily: 'JetBrains Mono, monospace', fontSize: 11.5, color: 'var(--text-primary)', margin: 0, whiteSpace: 'pre-wrap' }}>
{'export ' + it.env_var + '=…'}
                  </pre>
                </div>
              )}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

window.IntegrationsScreen = IntegrationsScreen;
