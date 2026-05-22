/** @jsxRuntime classic */ /** @jsx React.createElement */
/* global React, OPHAMIN, Icon */

// ModelsScreen — the dedicated-model routing (R&D). Shows the agentic model
// tiers (general + dedicated scientific/engineering), each tier's model +
// provider (local-first / external-API opt-in) + key-env-var name (never the
// secret), and the per-task → tier map. Hydrated from /models. These models
// are tooling-layer only — they never run in the measurement path.
function ModelsScreen() {
  const D = OPHAMIN;
  const m = D.models || {};
  const tiers = m.tiers || [];
  const tasks = m.tasks || [];

  return (
    <div className="content-inner page">
      <div className="page-header">
        <div>
          <h1 className="page-title">Models</h1>
          <div className="page-subtitle mono">Dedicated scientific/engineering models — local-first, external-API opt-in.</div>
        </div>
        <div className="page-actions">
          <span className="chip">{m.default_provider || 'local'}-first{m.external_api_enabled ? ' · external API on' : ''}</span>
        </div>
      </div>

      <div className="agent-banner">
        <Icon name="cpu" size={16}/>
        <div>
          The models the agentic system uses for <b>analysis / diagnosis / authoring</b> — never inside the measurement path. Validation routes to <b>domain-dedicated</b> scientific/engineering tiers. Out of the box those default to a general model (shown below as <span className="mono">general-fallback</span>); set <span className="mono">OPHAMIN_LLM_MODEL_SCIENTIFIC</span> / <span className="mono">_ENGINEERING</span> (local or external API) to back them with a truly dedicated model. Each tier is local by default; the API key is read from an env var, never stored.
        </div>
      </div>

      {tiers.length === 0 ? (
        <div style={{ padding: 20, color: 'var(--text-muted)', fontSize: 13 }}>No model routing available (backend not reached).</div>
      ) : (
        <div style={{ display: 'grid', gridTemplateColumns: '1fr', gap: 14 }}>
          <div className="card" style={{ overflow: 'hidden' }}>
            <div className="card-header"><div className="card-title">Tiers</div></div>
            <div style={{ padding: 16, display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(240px, 1fr))', gap: 10 }}>
              {tiers.map((t) => {
                const dedicated = t.dedicated;
                const isDomain = t.role === 'domain-dedicated';
                // honest accent: green only when ACTUALLY dedicated; amber for a
                // domain tier still on its general-fallback; muted for general.
                const c = dedicated ? 'var(--accent, #2dd4bf)' : (isDomain ? 'var(--inconclusive, #e3b341)' : 'var(--text-muted)');
                return (
                  <div key={t.tier} style={{ border: '1px solid var(--border)', borderLeft: '3px solid ' + c, borderRadius: 'var(--r-sm)', padding: 12 }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 6, flexWrap: 'wrap' }}>
                      <span className="mono" style={{ fontSize: 12, color: 'var(--text-primary)', textTransform: 'uppercase' }}>{t.tier}</span>
                      {dedicated && <span className="chip" style={{ fontSize: 9 }}>dedicated</span>}
                      {isDomain && !dedicated && <span className="chip" style={{ fontSize: 9, color: 'var(--inconclusive, #e3b341)', borderColor: 'var(--inconclusive, #e3b341)' }} title={'currently the same model as the ' + t.fallback_general_tier + ' tier — set a distinct model to make it dedicated'}>general-fallback</span>}
                    </div>
                    <div className="mono" style={{ fontSize: 11, marginTop: 6, color: 'var(--text-primary)', wordBreak: 'break-all' }}>{t.model}</div>
                    <div className="mono faint" style={{ fontSize: 10, marginTop: 4 }}>
                      provider: <span style={{ color: t.provider === 'external_api' ? 'var(--inconclusive)' : 'var(--validated)' }}>{t.provider}</span>
                      {t.provider === 'external_api' && t.api_key_env ? ` · key: ${t.api_key_env}` : ''}
                    </div>
                    {isDomain && !dedicated && t.fallback_general_tier && (
                      <div className="mono faint" style={{ fontSize: 9.5, marginTop: 3 }}>↳ same model as <span style={{ textTransform: 'uppercase' }}>{t.fallback_general_tier}</span></div>
                    )}
                    {('available' in t) && (
                      <div className="mono faint" style={{ fontSize: 9.5, marginTop: 3 }}>
                        installed: <span style={{ color: t.available === true ? 'var(--validated)' : (t.available === false ? 'var(--refuted)' : 'var(--text-muted)') }}>{t.available === true ? 'yes' : (t.available === false ? 'no' : 'unknown')}</span>
                      </div>
                    )}
                  </div>
                );
              })}
            </div>
          </div>

          <div className="card" style={{ overflow: 'hidden' }}>
            <div className="card-header"><div className="card-title">Task routing</div><span className="chip">{tasks.length}</span></div>
            <div style={{ padding: '8px 16px 14px' }}>
              {tasks.map((t) => (
                <div key={t.task} style={{ display: 'flex', alignItems: 'baseline', gap: 10, padding: '4px 0', borderBottom: '1px solid var(--border)' }}>
                  <div className="mono" style={{ fontSize: 11, color: 'var(--text-primary)', flex: '0 0 220px' }}>{t.task}</div>
                  <div className="mono" style={{ fontSize: 11, flex: 1, color: (t.tier === 'scientific' || t.tier === 'engineering') ? 'var(--accent, #2dd4bf)' : 'var(--text-muted)', textTransform: 'uppercase' }}>{t.tier}</div>
                  <div className="mono faint" style={{ fontSize: 9 }}>{t.max_tokens} tok</div>
                </div>
              ))}
            </div>
          </div>

          {m.boundary && (
            <div className="mono faint" style={{ fontSize: 10.5, padding: '0 4px', wordBreak: 'break-word' }}>{m.boundary}</div>
          )}
        </div>
      )}
    </div>
  );
}

window.ModelsScreen = ModelsScreen;
