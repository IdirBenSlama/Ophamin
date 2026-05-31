/** @jsxRuntime classic */ /** @jsx React.createElement */
/* global React, Icon */
// Mesh — the Indra's-Net observatory. Observe a partition exchange across the
// wire: did the receiving Node re-perform it faithfully (order-keeping), and how
// much experience has pooled across Nodes? It MEASURES a mesh, never drives one.
//
// Real: POSTs a controlled exchange to /comparing/mesh and renders the real
// observation (or honest nulls). No live mesh is fabricated — when the wire
// flows, the same surface shows it. The pre-filled exchange is a clearly-marked
// editable EXAMPLE (a controlled two-Node rig), not a captured live one.

const { useState: useMeshState } = React;

const EXAMPLE = {
  emitted: {
    primes: ["2", "7", "13", "17", "23"],
    echoform_sequence: [{ op: "deposit" }, { op: "resolve" }, { op: "commit" }],
  },
  received: {
    primes: ["2", "7", "13", "17", "23"],
    echoform_sequence: [{ op: "deposit" }, { op: "resolve" }, { op: "commit" }],
  },
  node_prime_sets: [["2", "7", "13", "17", "23"], ["2", "7", "13", "31"]],
};

function MeshScreen() {
  const [text, setText] = useMeshState(JSON.stringify(EXAMPLE, null, 2));
  const [result, setResult] = useMeshState(null); // null | {observation, meaning} | {error}
  const [busy, setBusy] = useMeshState(false);

  let parseError = null;
  try { JSON.parse(text); } catch (e) { parseError = e.message; }

  const observe = async () => {
    let body;
    try { body = JSON.parse(text); } catch (e) { setResult({ error: 'Invalid JSON: ' + e.message }); return; }
    setBusy(true);
    try {
      const base = window.OPHAMIN_API_BASE || '';
      const r = await fetch(base + '/comparing/mesh', {
        method: 'POST',
        headers: { 'content-type': 'application/json', accept: 'application/json' },
        body: JSON.stringify(body),
      });
      const data = await r.json().catch(() => ({}));
      setResult(r.ok ? data : { error: data.detail || ('HTTP ' + r.status) });
    } catch (e) {
      setResult({ error: 'Network error reaching /comparing/mesh: ' + (e && e.message) });
    } finally {
      setBusy(false);
    }
  };

  const obs = result && result.observation;
  const fmt = (v) => (v == null ? '—' : v.toFixed(3));
  const fidColor = (v) => (v == null ? 'var(--text-muted)' : v >= 0.999 ? 'var(--validated)' : v >= 0.6 ? 'var(--inconclusive)' : 'var(--refuted)');

  return (
    <div className="content-inner page" style={{ maxWidth: 1100 }}>
      <div className="page-header">
        <div>
          <h1 className="page-title">Mesh</h1>
          <div className="page-subtitle">The Indra's-Net observatory — observe a partition exchange across the wire. It measures a mesh, never drives one.</div>
        </div>
        <div className="page-actions">
          <span className="live-pill muted"><span className="dot"></span>no live mesh · controlled rig</span>
        </div>
      </div>

      <div className="agent-banner">
        <Icon name="activity" size={16}/>
        <div>
          Kimera's topology is <b>Node → Archipel → Indra's Net</b>: a Node is one substrate, an Archipel a local mesh, Indra's Net the global pooled experience. The wire carries <b>partitions</b> (primes + Echoform operator sequence + Cronos + GWF) — re-performable instructions, never commands. No live mesh is connected; observe a controlled two-Node exchange below, and the same surface lights up when the wire flows.
        </div>
      </div>

      {/* Topology strip */}
      <div className="card" style={{ marginTop: 4, padding: 16, display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 20, flexWrap: 'wrap' }}>
        {[
          { t: 'NODE', d: 'one substrate' },
          { t: 'ARCHIPEL', d: 'local mesh' },
          { t: "INDRA'S NET", d: 'global pooled experience' },
        ].map((n, i, arr) => (
          <React.Fragment key={n.t}>
            <div style={{ textAlign: 'center' }}>
              <div className="mono" style={{ fontSize: 13, fontWeight: 600, color: 'var(--text-primary)' }}>{n.t}</div>
              <div style={{ fontSize: 11, color: 'var(--text-muted)', marginTop: 2 }}>{n.d}</div>
            </div>
            {i < arr.length - 1 && <span style={{ color: 'var(--accent)', fontSize: 18 }}>→</span>}
          </React.Fragment>
        ))}
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16, marginTop: 16 }}>
        {/* Exchange input */}
        <div className="card" style={{ overflow: 'hidden' }}>
          <div className="card-header">
            <div className="card-title">Partition exchange</div>
            <span className="micro">EDITABLE EXAMPLE · CONTROLLED RIG</span>
          </div>
          <textarea spellCheck="false" value={text} onChange={e => setText(e.target.value)}
            style={{ width: '100%', height: 300, padding: 12, background: 'var(--bg-base)', border: 'none', color: 'var(--text-primary)', fontFamily: 'JetBrains Mono, monospace', fontSize: 12, lineHeight: 1.6, resize: 'vertical', outline: 'none', display: 'block' }}/>
          <div style={{ padding: '10px 14px', borderTop: '1px solid var(--border)', display: 'flex', alignItems: 'center', gap: 10 }}>
            <button className="btn primary" onClick={observe} disabled={busy || !!parseError}>
              <Icon name="activity" size={13}/> {busy ? 'Observing…' : 'Observe exchange'}
            </button>
            <span style={{ fontSize: 11, color: parseError ? 'var(--refuted)' : 'var(--text-muted)' }}>
              {parseError ? '✗ invalid JSON' : 'POST /comparing/mesh · real observation'}
            </span>
          </div>
        </div>

        {/* Observation */}
        <div className="card">
          <div className="card-header">
            <div className="card-title">Observation</div>
            <span className="micro">ORDER-AWARE · HONEST NULLS</span>
          </div>
          <div style={{ padding: 18 }}>
            {!result && (
              <div style={{ fontSize: 13, color: 'var(--text-muted)', lineHeight: 1.6 }}>
                Observe an exchange to see the two readings — re-performance fidelity (did the wire carry it faithfully?) and pooled-experience convergence (the Indra's-Net readout). Nothing is shown until a real exchange is measured.
              </div>
            )}
            {result && result.error && (
              <div style={{ fontSize: 13, color: 'var(--refuted)', lineHeight: 1.6 }}>Couldn't observe: {result.error}</div>
            )}
            {obs && (
              <div style={{ display: 'flex', flexDirection: 'column', gap: 18 }}>
                <div>
                  <div className="micro">RE-PERFORMANCE FIDELITY</div>
                  <div className="mono tnum" style={{ fontSize: 32, fontWeight: 600, color: fidColor(obs.reperformance_fidelity) }}>{fmt(obs.reperformance_fidelity)}</div>
                  <div style={{ fontSize: 12, color: 'var(--text-secondary)', marginTop: 4, lineHeight: 1.5 }}>{result.meaning.reperformance_fidelity}</div>
                </div>
                <div>
                  <div className="micro">POOLED CONVERGENCE <span className="mono faint">· {obs.n_nodes} NODES</span></div>
                  <div className="mono tnum" style={{ fontSize: 32, fontWeight: 600, color: obs.pooled_convergence == null ? 'var(--text-muted)' : 'var(--accent)' }}>{fmt(obs.pooled_convergence)}</div>
                  <div style={{ fontSize: 12, color: 'var(--text-secondary)', marginTop: 4, lineHeight: 1.5 }}>{result.meaning.pooled_convergence}</div>
                </div>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}

window.MeshScreen = MeshScreen;
