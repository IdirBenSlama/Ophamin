/** @jsxRuntime classic */ /** @jsx React.createElement */
/* global React, OPHAMIN, Icon */

// FlowScreen — the `flow` scope of the Ophamin Protocol. Where every other
// screen shows a property at one substrate state (a POINT proof), this shows
// a property over a TRAJECTORY: a temporal-logic invariant checked across a
// whole run of cycles. The first flow proof is memory-as-deformation —
// recognition stability when a stimulus is re-shown after the manifold has
// deformed. Hydrated from /flow.
function FlowScreen() {
  const D = OPHAMIN;
  const fl = D.flow || {};
  const flows = fl.flows || [];

  const outColor = (o) =>
    o === 'VALIDATED' ? 'var(--validated, #2dd4bf)'
    : o === 'REFUTED' ? 'var(--refuted, #ef5b5b)'
    : o === 'INCONCLUSIVE' ? 'var(--inconclusive, #ffa726)'
    : 'var(--text-muted)';
  const fmt = (v) => {
    if (typeof v !== 'number') return '—';
    return String(+v.toFixed(4));
  };
  const pct = (v) => (typeof v === 'number' ? Math.max(0, Math.min(1, v)) * 100 : 0);

  // Group flows by their measured metric so each invariant gets one
  // floor-by-domain comparison row — the cross-domain map at a glance.
  const byMetric = {};
  flows.forEach((f) => {
    const k = f.metric_label || 'recognition Jaccard';
    (byMetric[k] = byMetric[k] || []).push(f);
  });
  const metricGroups = Object.keys(byMetric).sort();

  return (
    <div className="content-inner page">
      <div className="page-header">
        <div>
          <h1 className="page-title">Flow</h1>
          <div className="page-subtitle mono">Properties measured over a trajectory of cycles — dynamics, not a single point.</div>
        </div>
        <div className="page-actions">
          <span className="chip">{fl.passing || 0} of {flows.length} flow proofs holding</span>
        </div>
      </div>

      <div className="agent-banner">
        <Icon name="activity" size={16}/>
        <div>
          The <b>flow scope</b> of the protocol. A flow proof checks a <b>temporal-logic invariant</b> — <span className="mono">□ (always)</span> — across a whole run, not at one moment. Memory-as-deformation: when a stimulus is shown again <i>after</i> intervening cycles have deformed the manifold, the substrate must still recognise it. Every value is a signed proof from the corpus.
        </div>
      </div>

      {flows.length === 0 ? (
        <div style={{ padding: 20, color: 'var(--text-muted)', fontSize: 13 }}>
          No flow proofs in the corpus yet — run <span className="mono">examples/run_memory_deformation_flow.py</span>.
        </div>
      ) : (
        <div style={{ display: 'grid', gridTemplateColumns: '1fr', gap: 14 }}>

          {/* Cross-domain map: each invariant's floor across the corpora it's
              been measured on — the spectrum at a glance, above the cards. */}
          {flows.length > 1 && (
            <div className="card" style={{ padding: 16 }}>
              <div className="card-title">Cross-domain map</div>
              <div className="micro" style={{ marginTop: 2, marginBottom: 12 }}>
                Each flow invariant's floor across the corpora it's been measured on. Lower = the dynamics weaken on that data; <span className="mono">gaps</span> = exposures that produced no concept set (e.g. GWF blocking).
              </div>
              {metricGroups.map((label) => {
                const group = byMetric[label].slice().sort((a, b) => (b.floor || 0) - (a.floor || 0));
                return (
                  <div key={label} style={{ marginBottom: 14 }}>
                    <div className="micro" style={{ margin: '4px 0 6px' }}>{label.toUpperCase()} · floor by domain</div>
                    <div style={{ display: 'flex', flexDirection: 'column', gap: 5 }}>
                      {group.map((f, i) => {
                        const thr = typeof f.threshold === 'number' ? f.threshold : null;
                        const ok = thr === null ? true : (f.floor || 0) >= thr;
                        const barColor = ok ? 'var(--validated, #2dd4bf)' : 'var(--refuted, #ef5b5b)';
                        return (
                          <div key={i} style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                            <div className="mono faint" style={{ fontSize: 10, width: 180, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }} title={f.corpus_label}>{f.corpus_label}</div>
                            <div style={{ flex: 1, height: 14, background: 'var(--surface-2, #161b22)', borderRadius: 'var(--r-sm)', overflow: 'hidden', position: 'relative' }}>
                              <div style={{ width: pct(f.floor) + '%', height: '100%', background: barColor, opacity: 0.85 }}></div>
                              {thr !== null && (
                                <div title={'threshold ' + fmt(thr)} style={{ position: 'absolute', top: 0, left: pct(thr) + '%', width: 1, height: '100%', background: 'var(--text-muted)' }}></div>
                              )}
                            </div>
                            <div className="mono" style={{ fontSize: 11, width: 52, textAlign: 'right', color: barColor }}>{fmt(f.floor)}</div>
                            <div className="mono faint" style={{ fontSize: 9, width: 56 }}>{f.n_failed_exposures > 0 ? ('· ' + f.n_failed_exposures + ' gaps') : ''}</div>
                          </div>
                        );
                      })}
                    </div>
                  </div>
                );
              })}
            </div>
          )}

          {flows.map((f, fi) => {
            const color = outColor(f.outcome);
            const stim = f.per_stimulus_floor || {};
            const stimKeys = Object.keys(stim).sort((a, b) => (stim[a] - stim[b]));
            const thr = typeof f.threshold === 'number' ? f.threshold : null;
            const metricLabel = (f.metric_label || 'recognition Jaccard').toUpperCase();
            const unitLabel = (f.unit_label || 'stimulus').toUpperCase();
            const countLabel = f.n_pairs != null ? 'RE-EXPOSURE PAIRS'
              : f.n_measured != null ? 'CYCLES MEASURED' : 'SAMPLES';
            const countVal = f.n_pairs != null ? f.n_pairs
              : f.n_measured != null ? f.n_measured : '—';
            const worst = f.worst_pair || f.worst_unit || null;
            return (
              <div key={fi} className="card" style={{ overflow: 'hidden' }}>
                <div className="card-header">
                  <div>
                    <div className="card-title">
                      {f.scenario}
                      {f.corpus_label && (
                        <span className="chip" style={{ marginLeft: 8, fontSize: 10, verticalAlign: 'middle' }}>{f.corpus_label}</span>
                      )}
                    </div>
                    <div className="micro" style={{ marginTop: 2, maxWidth: 680 }}>{f.claim_statement}</div>
                  </div>
                  <span className="live-pill" style={{ color }}>
                    <span className="dot" style={{ background: color }}></span>
                    {f.outcome || '—'}
                  </span>
                </div>

                <div style={{ padding: 16 }}>
                  {/* headline: floor vs threshold + mean */}
                  <div style={{ display: 'flex', gap: 28, flexWrap: 'wrap', alignItems: 'baseline', marginBottom: 14 }}>
                    <div>
                      <div className="micro">{metricLabel} FLOOR (worst)</div>
                      <div className="mono" style={{ fontSize: 26, color, lineHeight: 1.1 }}>{fmt(f.floor)}</div>
                      <div className="mono faint" style={{ fontSize: 11 }}>
                        {f.comparator || '≥'} {fmt(f.threshold)} threshold
                      </div>
                    </div>
                    <div>
                      <div className="micro">MEAN</div>
                      <div className="mono" style={{ fontSize: 18, color: 'var(--text-primary)' }}>{fmt(f.mean)}</div>
                    </div>
                    <div>
                      <div className="micro">{countLabel}</div>
                      <div className="mono" style={{ fontSize: 18, color: 'var(--text-primary)' }}>{countVal}</div>
                    </div>
                    <div>
                      <div className="micro">SUBSTRATE COMMIT</div>
                      <div className="mono" style={{ fontSize: 13, color: 'var(--text-primary)' }}>{f.substrate_commit || '—'}</div>
                      <div className="mono faint" style={{ fontSize: 10 }}>{(f.created_at || '').slice(0, 10)}</div>
                    </div>
                  </div>

                  {/* the visual: per-unit floor bars (worst first) */}
                  <div className="micro" style={{ margin: '4px 0 8px' }}>PER-{unitLabel} {metricLabel} FLOOR · worst first</div>
                  <div style={{ display: 'flex', flexDirection: 'column', gap: 5 }}>
                    {stimKeys.map((k) => {
                      const v = stim[k];
                      const ok = thr === null ? true : v >= thr;
                      const barColor = ok ? 'var(--validated, #2dd4bf)' : 'var(--refuted, #ef5b5b)';
                      return (
                        <div key={k} style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                          <div className="mono faint" style={{ fontSize: 10, width: 56 }}>stim {k}</div>
                          <div style={{ flex: 1, height: 14, background: 'var(--surface-2, #161b22)', borderRadius: 'var(--r-sm)', overflow: 'hidden', position: 'relative' }}>
                            <div style={{ width: pct(v) + '%', height: '100%', background: barColor, opacity: 0.85 }}></div>
                            {thr !== null && (
                              <div title={'threshold ' + fmt(thr)} style={{ position: 'absolute', top: 0, left: pct(thr) + '%', width: 1, height: '100%', background: 'var(--text-muted)' }}></div>
                            )}
                          </div>
                          <div className="mono" style={{ fontSize: 11, width: 52, textAlign: 'right', color: barColor }}>{fmt(v)}</div>
                        </div>
                      );
                    })}
                  </div>

                  {/* worst sample + invariant */}
                  {worst && (worst.jaccard !== undefined ? (
                    <div className="micro" style={{ marginTop: 14 }}>
                      WORST RE-EXPOSURE · stimulus {worst.stimulus_index} · cycles {worst.cycle_a}↔{worst.cycle_b} ·
                      <span className="mono" style={{ color }}> Jaccard {fmt(worst.jaccard)}</span>
                    </div>
                  ) : (
                    <div className="micro" style={{ marginTop: 14 }}>
                      WORST CYCLE · stimulus {worst.stimulus_index} · cycle {worst.cycle}
                      {worst.pass !== undefined ? ' (pass ' + worst.pass + ')' : ''} ·
                      <span className="mono" style={{ color }}> {fmt(worst.value)}</span>
                    </div>
                  ))}
                  {typeof f.non_collapse_rate === 'number' && (
                    <div className="micro faint" style={{ marginTop: 4 }}>
                      non-collapse rate {(f.non_collapse_rate * 100).toFixed(1)}%
                      {f.per_pass_mean ? ' · per-pass mean Φ ' + Object.entries(f.per_pass_mean).map(([p, v]) => 'p' + p + ':' + fmt(v)).join('  ') : ''}
                    </div>
                  )}
                  {f.n_failed_exposures > 0 && (
                    <div className="micro faint" style={{ marginTop: 4 }}>
                      {f.n_failed_exposures} exposure{f.n_failed_exposures === 1 ? '' : 's'} produced no concept set (gap, not a 0.0 pair)
                    </div>
                  )}
                  <div className="mono faint" style={{ fontSize: 10.5, marginTop: 10, wordBreak: 'break-word' }}>
                    {f.ltl_invariant}
                  </div>
                  {f.threshold_anchor && (
                    <div className="mono faint" style={{ fontSize: 10, marginTop: 4, wordBreak: 'break-word' }}>
                      {f.threshold_anchor}
                    </div>
                  )}
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}

window.FlowScreen = FlowScreen;
