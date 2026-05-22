// ToolkitsScreen — the unified index that routes to every wrapped tool's
// NATIVE interface (R&D). Ophamin is the garage; these are the mature tools on
// the wall. Each card shows the tool's role in Ophamin, its installed version,
// and direct links to its own docs (and live UI where one exists — MLflow /
// DVC / Prometheus). Hydrated from /toolkits. The point: both interfaces —
// Ophamin's view AND the tool's own — never hide the native one.

function ToolkitsScreen() {
  const data = (window.OPHAMIN && window.OPHAMIN.toolkits) || {};
  const toolkits = data.toolkits || [];
  const cats = data.categories || {};
  const catNames = Object.keys(cats).sort();

  const uiBadge = (kind) => {
    if (kind === 'local-server') return 'live · local server';
    if (kind === 'web-app') return 'live · web app';
    if (kind === 'doc') return 'local report';
    return 'native UI';
  };

  return (
    <div className="screen">
      <div className="screen-head">
        <h1>Toolkits</h1>
        <p className="sub">Unified index — Ophamin routes to every wrapped tool's native interface</p>
      </div>

      <div className="agent-banner">
        <Icon name="package" size={16}/>
        <div>
          The mature open-source tools Ophamin builds on, each with its own role, version, and <b>native</b> interface. Ophamin routes to them rather than hiding them — you get both views. Tools with a live UI (MLflow, DVC, Prometheus) carry a launch route. Plug your own SDK or toolkit in via <span className="mono">OPHAMIN_TOOLKITS=&lt;json&gt;</span> and it appears here too.
        </div>
      </div>

      {toolkits.length === 0 ? (
        <div style={{ padding: 20, color: 'var(--text-muted)', fontSize: 13 }}>No toolkit index available (backend not reached).</div>
      ) : (
        <>
          <div style={{ display: 'flex', gap: 18, flexWrap: 'wrap', margin: '4px 2px 16px', fontSize: 12 }}>
            <span className="mono faint">{data.n_toolkits} toolkits</span>
            <span className="mono faint">{data.n_installed} installed</span>
            <span className="mono" style={{ color: 'var(--accent, #2dd4bf)' }}>{data.n_with_native_ui} with a live native UI</span>
            {data.n_extra > 0 && <span className="mono faint">{data.n_extra} plugged in</span>}
          </div>

          {catNames.map((cat) => (
            <div key={cat} className="card" style={{ overflow: 'hidden', marginBottom: 14 }}>
              <div className="card-header">
                <div className="card-title" style={{ textTransform: 'capitalize' }}>{cat}</div>
                <span className="chip">{cats[cat]}</span>
              </div>
              <div style={{ padding: 14, display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(280px, 1fr))', gap: 10 }}>
                {toolkits.filter((t) => t.category === cat).map((t) => {
                  const hasUI = !!t.native_ui;
                  const c = hasUI ? 'var(--accent, #2dd4bf)' : 'var(--border)';
                  return (
                    <div key={t.id} style={{ border: '1px solid var(--border)', borderLeft: '3px solid ' + c, borderRadius: 'var(--r-sm)', padding: 12 }}>
                      <div style={{ display: 'flex', alignItems: 'baseline', gap: 8, flexWrap: 'wrap' }}>
                        <span className="mono" style={{ fontSize: 13, color: 'var(--text-primary)' }}>{t.id}</span>
                        {t.installed
                          ? <span className="mono faint" style={{ fontSize: 10 }}>v{t.version}</span>
                          : <span className="mono" style={{ fontSize: 10, color: 'var(--refuted)' }}>not installed</span>}
                      </div>
                      <div style={{ fontSize: 12, color: 'var(--text-secondary)', margin: '6px 0' }}>{t.role}</div>
                      {t.ophamin_module && (
                        <div className="mono faint" style={{ fontSize: 10, marginBottom: 6 }}>used in: {t.ophamin_module}</div>
                      )}
                      <div style={{ display: 'flex', gap: 12, flexWrap: 'wrap', fontSize: 11 }}>
                        <a href={t.docs_url} target="_blank" rel="noopener noreferrer" className="mono" style={{ color: 'var(--accent, #2dd4bf)' }}>docs ↗</a>
                        <a href={t.homepage} target="_blank" rel="noopener noreferrer" className="mono faint">home ↗</a>
                      </div>
                      {hasUI && (
                        <div style={{ marginTop: 8, padding: '6px 8px', background: 'var(--surface-2, #161b22)', borderRadius: 'var(--r-sm)' }}>
                          <div className="micro" style={{ color: 'var(--accent, #2dd4bf)' }}>{uiBadge(t.native_ui_kind)}</div>
                          <div className="mono" style={{ fontSize: 10.5, marginTop: 2, wordBreak: 'break-word', color: 'var(--text-secondary)' }}>{t.native_ui}</div>
                        </div>
                      )}
                    </div>
                  );
                })}
              </div>
            </div>
          ))}

          {data.boundary && (
            <div className="mono faint" style={{ fontSize: 10.5, padding: '0 4px', wordBreak: 'break-word' }}>{data.boundary}</div>
          )}
        </>
      )}
    </div>
  );
}

window.ToolkitsScreen = ToolkitsScreen;
