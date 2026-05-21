/** @jsxRuntime classic */ /** @jsx React.createElement */
/* global React, OPHAMIN, Icon */

// SubstrateScreen — the keystone. The substrate-under-test (Kimera)
// observed through what the SIGNED proofs measured about it: one card per
// named organ (GWF / Walker / prime apparatus / scar-vault / Φ /
// dissonance / Rosetta / …), each showing its latest signed measurement.
// Real + signed + always available (no live Kimera). Hydrated from
// /substrate. The manifold-topology hero + live adapter probe are
// follow-on slices.
function SubstrateScreen() {
  const D = OPHAMIN;
  const organs = D.substrate_organs || [];
  const measured = organs.filter(o => o.status !== 'no_data').length;
  const topology = organs.find(o => o.id === 'topology') || null;
  const gridOrgans = organs.filter(o => o.id !== 'topology');

  const statusColor = (s) =>
    s === 'validated' ? 'var(--validated, #2dd4bf)'
    : s === 'refuted' ? 'var(--refuted, #ef5b5b)'
    : s === 'inconclusive' ? 'var(--inconclusive, #ffa726)'
    : 'var(--text-muted)';

  const fmt = (v) => {
    if (typeof v !== 'number') return '—';
    if (v !== 0 && Math.abs(v) < 0.001) return v.toExponential(2);
    return String(+v.toFixed(4));
  };

  return (
    <div className="content-inner page">
      <div className="page-header">
        <div>
          <h1 className="page-title">Substrate</h1>
          <div className="page-subtitle mono">Kimera observed through what the signed proofs measured — each organ's latest verdict from the corpus.</div>
        </div>
        <div className="page-actions">
          <span className="chip">{measured} of {organs.length} organs measured</span>
        </div>
      </div>

      <div className="agent-banner">
        <Icon name="cpu" size={16}/>
        <div>
          The substrate's named organs — GWF, Walker, the prime apparatus, scar/vault memory, Φ, dissonance, Rosetta and more — each backed by the <b>latest signed proof</b> that exercised it. Organs marked <span className="mono">no proof yet</span> haven't been measured into the corpus. A live <span className="mono">KimeraAdapter</span> probe (organ telemetry + manifold topology) is a future opt-in.
        </div>
      </div>

      {topology && (() => {
        const lt = topology.latest;
        const b0 = lt && typeof lt.observed === 'number' ? Math.round(lt.observed) : null;
        const connected = b0 === 1;
        const heroColor = b0 == null ? 'var(--text-muted)'
          : connected ? 'var(--validated, #2dd4bf)' : 'var(--refuted, #ef5b5b)';
        return (
          <div className="card" style={{ overflow: 'hidden', marginBottom: 16 }}>
            <div className="card-header">
              <div>
                <div className="card-title">Manifold topology</div>
                <div className="micro" style={{ marginTop: 2 }}>connectivity of the geoid manifold (β₀ / β₁ / β₂)</div>
              </div>
              <span className="live-pill" style={{ color: heroColor }}>
                <span className="dot" style={{ background: heroColor }}></span>
                {b0 == null ? 'no proof yet' : connected ? 'connected' : 'fragmented'}
              </span>
            </div>
            <div style={{ padding: 20 }}>
              {b0 == null ? (
                <div style={{ fontSize: 13, lineHeight: 1.6, color: 'var(--text-secondary)' }}>
                  No manifold-topology proof in the corpus yet. Generate one with{' '}
                  <span className="mono">ophamin scenario manifold-topology</span>{' '}
                  against a Kimera substrate — this panel renders β₀ / β₁ / β₂ and the
                  geoid graph from the signed proof the moment it lands.
                </div>
              ) : (
                <div>
                  <div style={{ display: 'flex', alignItems: 'baseline', gap: 8 }}>
                    <span className="mono" style={{ fontSize: 40, fontWeight: 700, color: heroColor, lineHeight: 1 }}>β₀ = {b0}</span>
                    <span style={{ fontSize: 13, color: 'var(--text-secondary)' }}>
                      {connected ? 'single connected component' : b0 + ' disconnected components'}
                    </span>
                  </div>
                  <div className="mono faint" style={{ fontSize: 11, marginTop: 10 }}>
                    {lt.scenario} · {topology.proof_count} proof{topology.proof_count === 1 ? '' : 's'} · {(lt.substrate_name || 'kimera-swm')}{lt.substrate_commit ? ' @ ' + lt.substrate_commit : ''}
                  </div>
                  <div className="micro" style={{ marginTop: 12, color: 'var(--text-muted)' }}>
                    β₁ (loops) + β₂ (voids) + the geoid/scar graph render here from the proof's evidence — coming as the topology proof gains those fields.
                  </div>
                </div>
              )}
            </div>
          </div>
        );
      })()}

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(300px, 1fr))', gap: 14 }}>
        {gridOrgans.length === 0 ? (
          <div style={{ padding: 20, color: 'var(--text-muted)', fontSize: 13 }}>
            No substrate organs available (backend not reached).
          </div>
        ) : gridOrgans.map(o => {
          const lt = o.latest;
          const color = statusColor(o.status);
          return (
            <div key={o.id} className="card" style={{ overflow: 'hidden', opacity: o.status === 'no_data' ? 0.6 : 1 }}>
              <div className="card-header">
                <div className="card-title">{o.name}</div>
                <span className="live-pill" style={{ color }}>
                  <span className="dot" style={{ background: color }}></span>
                  {o.status === 'no_data' ? 'no proof yet' : o.status}
                </span>
              </div>
              <div style={{ padding: 16 }}>
                <p style={{ fontSize: 12.5, lineHeight: 1.5, color: 'var(--text-secondary)', margin: '0 0 14px' }}>{o.role}</p>
                {lt ? (
                  <div>
                    <div className="micro" style={{ marginBottom: 4 }}>LATEST SIGNED MEASUREMENT</div>
                    <div className="mono" style={{ fontSize: 13, color: 'var(--text-primary)', wordBreak: 'break-word' }}>
                      {lt.metric} = <span style={{ color }}>{fmt(lt.observed)}</span>
                      <span className="faint" style={{ fontSize: 11 }}> ({lt.comparator} {fmt(lt.threshold)})</span>
                    </div>
                    <div className="mono faint" style={{ fontSize: 10, marginTop: 8 }}>
                      {lt.scenario} · {o.proof_count} proof{o.proof_count === 1 ? '' : 's'}
                    </div>
                    <div className="mono faint" style={{ fontSize: 10, marginTop: 2 }}>
                      {(lt.substrate_name || 'kimera-swm')}{lt.substrate_commit ? ' @ ' + lt.substrate_commit : ''}
                    </div>
                  </div>
                ) : (
                  <div className="mono faint" style={{ fontSize: 11.5 }}>Not yet exercised as a signed proof.</div>
                )}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}

window.SubstrateScreen = SubstrateScreen;
