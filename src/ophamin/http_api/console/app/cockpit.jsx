/** @jsxRuntime classic */ /** @jsx React.createElement */
/* global React, OPHAMIN, Icon */

// CockpitScreen — the Build Cockpit. The `engineering` facet of the
// Ophamin Protocol: Kimera's engineering health (orphans / contract /
// quality / cost / reproducibility) as signed proofs from the corpus,
// shown as a TIMELINE across substrate commits so the trend is visible
// while Kimera is built. Hydrated from /cockpit.
const SCENARIO_FOR = {
  completeness: 'substrate-completeness',
  interface: 'interface-contract-stability',
  code_quality: 'sonarqube-scan',
  throughput: 'throughput-ceiling',
  reproducibility: 'deterministic-seed-audit',
};

function CockpitScreen() {
  const D = OPHAMIN;
  const ck = D.cockpit || {};
  const checks = ck.checks || [];

  const statusColor = (s) =>
    s === 'validated' ? 'var(--validated, #2dd4bf)'
    : s === 'refuted' ? 'var(--refuted, #ef5b5b)'
    : s === 'inconclusive' ? 'var(--inconclusive, #ffa726)'
    : 'var(--text-muted)';
  const outColor = (o) =>
    statusColor(o === 'VALIDATED' ? 'validated' : o === 'REFUTED' ? 'refuted' : 'inconclusive');
  const fmt = (v) => {
    if (typeof v !== 'number') return '—';
    if (v !== 0 && Math.abs(v) < 0.001) return v.toExponential(2);
    return String(+v.toFixed(4));
  };

  return (
    <div className="content-inner page">
      <div className="page-header">
        <div>
          <h1 className="page-title">Build Cockpit</h1>
          <div className="page-subtitle mono">Kimera's engineering health, tracked over substrate commits — orphans, contract, quality, cost, reproducibility.</div>
        </div>
        <div className="page-actions">
          <span className="chip">{ck.passing || 0} of {checks.length} checks passing</span>
        </div>
      </div>

      <div className="agent-banner">
        <Icon name="cpu" size={16}/>
        <div>
          The <b>engineering facet</b> of the protocol — every check is a signed proof from the corpus, shown as a <b>timeline across substrate commits</b> so you and your code model can see whether Kimera is getting healthier or drifting as it's built. Checks marked <span className="mono">no proof yet</span> haven't been run into the corpus.
        </div>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: '1fr', gap: 14 }}>
        {checks.length === 0 ? (
          <div style={{ padding: 20, color: 'var(--text-muted)', fontSize: 13 }}>
            No engineering checks available (backend not reached).
          </div>
        ) : checks.map(c => {
          const color = statusColor(c.status);
          const lt = c.latest;
          return (
            <div key={c.id} className="card" style={{ overflow: 'hidden', opacity: c.status === 'no_data' ? 0.62 : 1 }}>
              <div className="card-header">
                <div>
                  <div className="card-title">{c.name}</div>
                  <div className="micro" style={{ marginTop: 2 }}>{c.desc}</div>
                </div>
                <span className="live-pill" style={{ color }}>
                  <span className="dot" style={{ background: color }}></span>
                  {c.status === 'no_data' ? 'no proof yet' : c.status}
                </span>
              </div>
              <div style={{ padding: 16 }}>
                {lt ? (
                  <div>
                    <div className="mono" style={{ fontSize: 13, wordBreak: 'break-word' }}>
                      {lt.metric} = <span style={{ color }}>{fmt(lt.observed)}</span>
                      <span className="faint" style={{ fontSize: 11 }}> ({lt.comparator} {fmt(lt.threshold)})</span>
                    </div>
                    <div className="micro" style={{ margin: '14px 0 6px' }}>OVER SUBSTRATE COMMITS · {c.proof_count} proof{c.proof_count === 1 ? '' : 's'}</div>
                    <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
                      {(c.series || []).map((pt, i) => (
                        <div key={i} title={pt.outcome + ' · ' + (pt.created_at || '').slice(0, 10)}
                          style={{ border: '1px solid var(--border)', borderLeft: '3px solid ' + outColor(pt.outcome), borderRadius: 'var(--r-sm)', padding: '5px 8px', minWidth: 84 }}>
                          <div className="mono" style={{ fontSize: 11, color: 'var(--text-primary)' }}>{fmt(pt.observed)}</div>
                          <div className="mono faint" style={{ fontSize: 9 }}>{pt.substrate_commit || '—'}</div>
                          <div className="mono faint" style={{ fontSize: 9 }}>{(pt.created_at || '').slice(0, 10)}</div>
                        </div>
                      ))}
                    </div>
                  </div>
                ) : (
                  <div className="mono faint" style={{ fontSize: 11.5 }}>
                    Not yet run into the corpus — <span className="mono">ophamin scenario {SCENARIO_FOR[c.id] || c.id}</span>.
                  </div>
                )}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}

window.CockpitScreen = CockpitScreen;
