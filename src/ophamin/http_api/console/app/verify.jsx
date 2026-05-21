/** @jsxRuntime classic */ /** @jsx React.createElement */
/* global React, OPHAMIN, Icon */

// VerifyScreen — paste a signed proof record, check its HMAC signature
// against the framework key via POST /verify. Verification is Ophamin's
// own (custom canonicalization, SCHEMAS.md R1–R11) — nothing else verifies
// these signatures. Real end to end; "Load a proof from the corpus" pulls
// a real signed proof.json the hydrate step already fetched.
const { useState: useVerifyState } = React;

function VerifyScreen() {
  const D = OPHAMIN;
  const [text, setText] = useVerifyState('');
  const [status, setStatus] = useVerifyState('idle'); // idle | verifying | done | error
  const [result, setResult] = useVerifyState(null);
  const [errMsg, setErrMsg] = useVerifyState('');

  const loadSample = async () => {
    // Fetch the EXACT bytes of a signed proof.json. We must NOT
    // JSON.stringify a parsed object — JS drops trailing ".0" on
    // whole-number floats (500.0 -> 500), which changes the canonical
    // form and makes a valid signature fail. Verification is over bytes.
    const b = (D.bundles || []).find(x => x._live && (x.files || []).includes('proof.json'));
    if (!b) {
      setErrMsg('No signed proof available in the corpus to load.');
      setStatus('error');
      return;
    }
    try {
      const base = window.OPHAMIN_API_BASE || '';
      const qs = new URLSearchParams({
        tier: b.tier, scenario: b.scenario, bundle: b.bundle_dir, filename: 'proof.json',
      }).toString();
      const r = await fetch(base + '/proofs/bundles/file?' + qs);
      if (!r.ok) throw new Error('HTTP ' + r.status);
      const raw = await r.text();
      setText(raw);
      setStatus('idle'); setResult(null); setErrMsg('');
    } catch (e) {
      setErrMsg('Could not load proof: ' + e.message);
      setStatus('error');
    }
  };

  const verify = async () => {
    setStatus('verifying'); setResult(null); setErrMsg('');
    try {
      const base = window.OPHAMIN_API_BASE || '';
      const r = await fetch(base + '/verify', {
        method: 'POST',
        headers: { 'content-type': 'application/json', accept: 'application/json' },
        body: JSON.stringify({ proof_json: text }),
      });
      const j = await r.json();
      if (!r.ok) { setStatus('error'); setErrMsg(j.detail || ('HTTP ' + r.status)); return; }
      setResult(j); setStatus('done');
    } catch (e) {
      setStatus('error');
      setErrMsg('Request failed: ' + e.message + ' (is the server reachable?)');
    }
  };

  const verified = result && result.verified;

  return (
    <div className="content-inner page">
      <div className="page-header">
        <div>
          <h1 className="page-title">Verify</h1>
          <div className="page-subtitle mono">Paste a signed proof record — check its HMAC signature against the framework key.</div>
        </div>
        <div className="page-actions">
          <button className="btn" style={{ fontSize: 12 }} onClick={loadSample}>Load a proof from the corpus</button>
        </div>
      </div>

      <div className="agent-banner">
        <Icon name="proofs" size={16}/>
        <div>
          Drop the exact bytes of a <span className="mono">proof.json</span>. Ophamin re-canonicalizes the record (SCHEMAS.md R1–R11) and re-computes the HMAC over its body — so tampering with any field, including the verdict, fails the check. Verification never raises: a bad signature returns <span className="mono">verified: false</span> with the fields still introspectable.
        </div>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16 }}>
        <div>
          <div className="micro" style={{ marginBottom: 6 }}>PROOF RECORD (JSON)</div>
          <textarea spellCheck="false" value={text} onChange={e => setText(e.target.value)}
            placeholder='{"schema_version": "1.0", ...}'
            style={{ width: '100%', minHeight: 360, padding: 12, background: 'var(--bg-base)', border: '1px solid var(--border)', borderRadius: 'var(--r-sm)', color: 'var(--text-primary)', fontFamily: 'JetBrains Mono, monospace', fontSize: 11.5, resize: 'vertical' }}/>
          <div style={{ display: 'flex', gap: 8, marginTop: 12 }}>
            <button className="btn primary" style={{ fontSize: 12 }}
              disabled={!text.trim() || status === 'verifying'} onClick={verify}>
              <Icon name="proofs" size={12}/> {status === 'verifying' ? 'Verifying…' : 'Verify signature'}
            </button>
            {text && (
              <button className="btn" style={{ fontSize: 12 }}
                onClick={() => { setText(''); setResult(null); setStatus('idle'); setErrMsg(''); }}>
                Clear
              </button>
            )}
          </div>
        </div>

        <div>
          <div className="micro" style={{ marginBottom: 6 }}>RESULT</div>
          <div className="card" style={{ minHeight: 360, padding: 20 }}>
            {status === 'idle' && <div className="faint" style={{ fontSize: 13 }}>Paste a proof and press Verify, or load one from the corpus.</div>}
            {status === 'verifying' && <div className="faint" style={{ fontSize: 13 }}>Re-canonicalizing + checking HMAC…</div>}
            {status === 'error' && <div style={{ color: 'var(--refuted, #ef5b5b)', fontSize: 13 }}>{errMsg}</div>}
            {status === 'done' && result && (
              <div>
                <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                  <span style={{ fontSize: 32, color: verified ? 'var(--validated, #2dd4bf)' : 'var(--refuted, #ef5b5b)' }}>{verified ? '✓' : '✗'}</span>
                  <span style={{ fontSize: 18, fontWeight: 700, color: verified ? 'var(--validated, #2dd4bf)' : 'var(--refuted, #ef5b5b)' }}>
                    {verified ? 'Signature verified' : 'Signature NOT verified'}
                  </span>
                </div>
                <div style={{ marginTop: 16, display: 'grid', gridTemplateColumns: '110px 1fr', gap: '6px 12px', fontSize: 12 }}>
                  <span className="mono faint">proof_id</span><span className="mono" style={{ wordBreak: 'break-all', fontSize: 10 }}>{result.proof_id}</span>
                  <span className="mono faint">schema</span><span className="mono">{result.schema_version || '—'}</span>
                  <span className="mono faint">verdict</span><span className="mono">{(result.verdict || {}).outcome || '—'}</span>
                  <span className="mono faint">claim</span><span style={{ color: 'var(--text-secondary)' }}>{result.claim_statement || '—'}</span>
                </div>
                {(result.verdict || {}).reasoning && (
                  <div style={{ marginTop: 14 }}>
                    <div className="micro" style={{ marginBottom: 4 }}>REASONING</div>
                    <div style={{ fontSize: 12, lineHeight: 1.5, color: 'var(--text-secondary)' }}>{result.verdict.reasoning}</div>
                  </div>
                )}
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}

window.VerifyScreen = VerifyScreen;
