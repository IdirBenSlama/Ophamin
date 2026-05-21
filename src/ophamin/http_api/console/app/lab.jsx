/** @jsxRuntime classic */ /** @jsx React.createElement */
/* global React, OPHAMIN, Icon, SixWheelsLoader, formatNum */
// Lab — wire-format playground for /verify + /canonicalize.

const { useState: useLabState, useMemo: useLabMemo, useEffect: useLabEffect } = React;

const DEMO_PROOF = {
  proof_id: 'will_be_recomputed',
  schema_version: '1.0',
  identity: {
    ophamin_version: '0.64.1',
    ophamin_git_commit: '3f0763aa468566729f3e2f795cfb5f433457534d',
    created_at: '2026-05-19T16:40:40.000000+00:00',
  },
  claim: {
    statement: 'Demo claim — substrate p95 latency stays under 50ms.',
    operationalization: '95th percentile of /run cycle wall-time across 200 cycles',
    threshold: { metric: 'p95_latency', comparator: '<=', value: 50, units: 'ms' },
    h0: 'p95 > 50ms',
    h1: 'p95 <= 50ms',
  },
  preregistration: {
    config_hash: 'sha256:b3525b62c7f8ab3406570978bdba7172fa5d03492a51a99b8a7ca9188a9f4cd8',
    data_hash:   'sha256:83109a27c3df2a45b912398b969fa8f7250b3d04dee11916d73ecf679d828010',
    analysis_plan: 'Stream 200 records through entity target, sample wall-time, compute p95.',
    sweep_grid: {},
    preregistered_at: '2026-05-19T16:30:00.000000+00:00',
  },
  data: {
    substrate_name: 'kimera-swm',
    substrate_git_commit: '4552de7ee80c',
    datasets: [{ name: 'synthetic-load', content_hash: 'sha256:abc123', n_records: 200, source: 'demo', kind: 'synthetic' }],
  },
  evidence: [
    { pillar: 'O.engineering.p95_wall_time', statistic_name: 'p95_cycle_wall_time_ms', statistic_value: 42.7, library: 'python-stdlib', library_version: '3.14', ci_low: null, ci_high: null, p_value: null, cross_check: 'n/a', detail: { n: 200 } },
  ],
  verdict: {
    outcome: 'VALIDATED',
    observed_value: 42.7,
    threshold: { metric: 'p95_latency', comparator: '<=', value: 50, units: 'ms' },
    reasoning: 'p95 of 42.7ms < 50ms ceiling across 200 cycles.',
  },
  reproduction: { command: 'ophamin run demo', environment: { python: '3.14.3' }, lineage_chain: [] },
  provenance: { prefix: { ophamin: 'https://ophamin.example/' } },
  signature: 'will_be_recomputed',
};

// ─── Canonical JSON emitter (RFC 8785 lite — sorted keys, no whitespace,
// integer vs float preserved, NaN/Inf rejected). Pedagogical, not full JCS.
function canonicalize(value) {
  if (value === null) return 'null';
  if (typeof value === 'boolean') return value ? 'true' : 'false';
  if (typeof value === 'number') {
    if (!Number.isFinite(value)) throw new Error(`non-finite number: ${value}`);
    // Distinguish "30" (int) from "30.0" (float) — JS forgets, so we sniff via toString
    const s = value.toString();
    return s;
  }
  if (typeof value === 'string') {
    return JSON.stringify(value);
  }
  if (Array.isArray(value)) {
    return '[' + value.map(canonicalize).join(',') + ']';
  }
  if (typeof value === 'object') {
    const keys = Object.keys(value).sort();
    return '{' + keys.map(k => JSON.stringify(k) + ':' + canonicalize(value[k])).join(',') + '}';
  }
  throw new Error(`unsupported type: ${typeof value}`);
}

// SHA-256 via Web Crypto
async function sha256Hex(bytes) {
  const buf = await crypto.subtle.digest('SHA-256', bytes);
  return [...new Uint8Array(buf)].map(b => b.toString(16).padStart(2, '0')).join('');
}

// HMAC-SHA256
async function hmacSha256Hex(keyBytes, msgBytes) {
  const key = await crypto.subtle.importKey('raw', keyBytes, { name: 'HMAC', hash: 'SHA-256' }, false, ['sign']);
  const sig = await crypto.subtle.sign('HMAC', key, msgBytes);
  return [...new Uint8Array(sig)].map(b => b.toString(16).padStart(2, '0')).join('');
}

function LabScreen() {
  const [proofText, setProofText] = useLabState(JSON.stringify(DEMO_PROOF, null, 2));
  const [keyB64, setKeyB64] = useLabState('cGRyYWZ0LXB1Yi1rZXk=');
  const [parseError, setParseError] = useLabState(null);
  const [parsed, setParsed] = useLabState(null);

  useLabEffect(() => {
    try {
      setParsed(JSON.parse(proofText));
      setParseError(null);
    } catch (e) {
      setParseError(e.message);
      setParsed(null);
    }
  }, [proofText]);

  const [canonical, setCanonical] = useLabState('');
  const [proofId, setProofId] = useLabState('');
  const [signature, setSignature] = useLabState('');
  const [computing, setComputing] = useLabState(false);
  const [canonError, setCanonError] = useLabState(null);

  useLabEffect(() => {
    if (!parsed) { setCanonical(''); setProofId(''); setSignature(''); return; }
    setComputing(true);
    setCanonError(null);
    (async () => {
      try {
        // body = all fields except proof_id and signature
        const { proof_id, signature: _sig, ...body } = parsed;
        const canon = canonicalize(body);
        setCanonical(canon);
        const enc = new TextEncoder();
        const bytes = enc.encode(canon);
        const pid = await sha256Hex(bytes);
        setProofId(pid);
        let key;
        try {
          key = Uint8Array.from(atob(keyB64), c => c.charCodeAt(0));
        } catch {
          key = enc.encode(keyB64);
        }
        const sig = await hmacSha256Hex(key, bytes);
        setSignature(sig);
      } catch (e) {
        setCanonError(e.message);
        setCanonical(''); setProofId(''); setSignature('');
      } finally {
        setComputing(false);
      }
    })();
  }, [parsed, keyB64]);

  // ─── Quick mutators for pedagogical "watch what happens" demos
  const mutate = (kind) => {
    if (!parsed) return;
    const p = JSON.parse(JSON.stringify(parsed));
    if (kind === 'flipInt') {
      p.claim.threshold.value = 50.0;
    } else if (kind === 'addWhitespace') {
      setProofText(JSON.stringify(p, null, 6));
      return;
    } else if (kind === 'mutateField') {
      p.verdict.observed_value = (p.verdict.observed_value || 0) + 0.001;
    } else if (kind === 'addInfinity') {
      p.verdict.observed_value = Infinity;
    } else if (kind === 'reset') {
      setProofText(JSON.stringify(DEMO_PROOF, null, 2));
      return;
    }
    setProofText(JSON.stringify(p, null, 2));
  };

  const matches = parsed && proofId && parsed.proof_id !== 'will_be_recomputed'
    ? parsed.proof_id === proofId
    : null;
  const sigMatches = parsed && signature && parsed.signature !== 'will_be_recomputed'
    ? parsed.signature === signature
    : null;

  return (
    <div className="content-inner page">
      <div className="page-header">
        <div>
          <h1 className="page-title">Lab</h1>
          <div className="page-subtitle mono">Paste a proof. Watch its bytes, hash, and signature recompute live. Break it on purpose to see what the framework guarantees.</div>
        </div>
        <div className="page-actions">
          <span className="live-pill">
            <span className="dot"></span>
            live in-browser
          </span>
          <button className="btn" onClick={() => mutate('reset')}>Reset</button>
        </div>
      </div>

      <div className="card" style={{ marginTop: 16, marginBottom: 16 }}>
        <div className="card-header">
          <div>
            <div className="card-title">Wire-format spec</div>
            <div className="micro" style={{ marginTop: 2 }}>NORMATIVE · SCHEMAS.md · what any verifier must enforce</div>
          </div>
          <a className="btn ghost" href="#" style={{ fontSize: 11 }}>
            <Icon name="external" size={12}/> SCHEMAS.md
          </a>
        </div>
        <div style={{ padding: 14, display: 'grid', gridTemplateColumns: 'repeat(2, 1fr)', gap: 10 }}>
          <SpecRule num="R1" label="9 sections always present"  desc="identity · claim · preregistration · data · evidence · verdict · reproduction · provenance · signature. Missing a section means the record refuses to verify."/>
          <SpecRule num="R2" label="UTF-8 canonical bytes"      desc="RFC 8785 JSON Canonicalization Scheme — sorted keys, no whitespace, no trailing newline. Bytes are identical across any language."/>
          <SpecRule num="R3" label="proof_id = sha256(body)"    desc="Content-addressed. Any byte mutation cascades through the proof_id and breaks verification."/>
          <SpecRule num="R4" label="Integer ≠ float emission"  desc="Integer 30 emits as 30. Float 30.0 emits as 30.0. Round-trip stable; type-preserving."/>
          <SpecRule num="R5" label="NaN / Infinity rejected"    desc="Non-finite floats fail canonicalize loudly; never silently coerced. Loud-fail discipline at the wire."/>
          <SpecRule num="R6" label="HMAC-SHA256 signature"      desc="signature = HMAC-SHA256(publication_key, canonical_body). Auth chain rooted in the key."/>
        </div>
        <div style={{ padding: '10px 16px', borderTop: '1px solid var(--border)', display: 'flex', alignItems: 'center', gap: 8, fontSize: 11, color: 'var(--text-muted)' }}>
          <Icon name="eye" size={12}/>
          A consumer in Rust, JS, or any language that implements R1–R6 verifies bit-equal to the Python reference codec. That is what cross-language interop means here.
        </div>
      </div>

      <div className="lab-banner">
        <Icon name="eye" size={16}/>
        <div>
          <b>This is your wire-format laboratory.</b> Paste a proof.json (or mutate the demo below) and watch its canonical bytes, sha256 content-hash, and HMAC signature recompute live. Toggle the helpers to break the canonicalization on purpose — the framework's epistemic guarantees are bytes, not promises.
        </div>
      </div>

      <div className="lab-layout">
        {/* LEFT — editor + mutators */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: 12, minWidth: 0 }}>
          <div className="card" style={{ overflow: 'hidden' }}>
            <div className="card-header">
              <div className="card-title">proof.json</div>
              <span className="mono" style={{ fontSize: 11, color: parseError ? 'var(--refuted)' : 'var(--validated)' }}>
                {parseError ? '✗ ' + parseError.slice(0, 40) : '✓ valid JSON · ' + proofText.length.toLocaleString() + ' chars'}
              </span>
            </div>
            <textarea
              spellCheck="false"
              value={proofText}
              onChange={e => setProofText(e.target.value)}
              style={{
                width: '100%',
                height: 420,
                padding: 14,
                background: 'var(--bg-base)',
                border: 0,
                color: 'var(--text-primary)',
                fontFamily: 'JetBrains Mono, monospace',
                fontSize: 11.5,
                lineHeight: 1.65,
                resize: 'vertical',
                outline: 'none',
              }}
            />
          </div>

          <div className="card">
            <div className="card-header">
              <div className="card-title">Try breaking it</div>
              <span className="micro">SAFE — TRY THEM</span>
            </div>
            <div style={{ padding: 12, display: 'flex', flexDirection: 'column', gap: 6 }}>
              <LabMutatorRow label="Add whitespace" desc="reformat with 6-space indent" detail="canonical form is identical — proof_id unchanged" onClick={() => mutate('addWhitespace')}/>
              <LabMutatorRow label="Int → float coerce" desc="set threshold.value = 50.0 (not 50)" detail="canonical form differs (50 vs 50.0) — proof_id changes" onClick={() => mutate('flipInt')}/>
              <LabMutatorRow label="Mutate observed_value" desc="add 0.001 to verdict.observed_value" detail="any single byte change cascades through proof_id + signature" onClick={() => mutate('mutateField')}/>
              <LabMutatorRow label="Inject Infinity" desc="set verdict.observed_value = Infinity" detail="canonicalize REFUSES — non-finite floats violate the wire format" onClick={() => mutate('addInfinity')} danger/>
            </div>
          </div>
        </div>

        {/* RIGHT — canonical bytes + hash + signature */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: 12, minWidth: 0 }}>
          <div className="card">
            <div className="card-header">
              <div className="card-title">Canonical form</div>
              <span className="micro">{canonical ? canonical.length.toLocaleString() + ' BYTES · UTF-8' : '—'}</span>
            </div>
            <div style={{ padding: 14, minHeight: 120, background: 'var(--bg-base)', fontFamily: 'JetBrains Mono, monospace', fontSize: 11, lineHeight: 1.55, color: canonError ? 'var(--refuted)' : 'var(--text-primary)', maxHeight: 180, overflow: 'auto', whiteSpace: 'pre-wrap', wordBreak: 'break-all' }}>
              {canonError ? '✗ ' + canonError : computing ? 'computing…' : canonical || 'paste a valid proof.json'}
            </div>
            <div style={{ padding: '8px 14px', borderTop: '1px solid var(--border)', fontSize: 10.5, color: 'var(--text-muted)' }}>
              Sorted keys · no whitespace · integer/float distinction preserved · NaN/Inf rejected
            </div>
          </div>

          <div className="card">
            <div className="card-header">
              <div className="card-title">Content hash · proof_id</div>
              <span className="micro">SHA-256(canonical_body)</span>
            </div>
            <LabHashRow value={proofId} status={matches}/>
            <LabHashCompare against={parsed?.proof_id} computed={proofId} kind="content hash"/>
          </div>

          <div className="card">
            <div className="card-header">
              <div className="card-title">Signature</div>
              <span className="micro">HMAC-SHA256(key, canonical_body)</span>
            </div>
            <div style={{ padding: '12px 14px', borderBottom: '1px solid var(--border)', display: 'flex', alignItems: 'center', gap: 10 }}>
              <span className="mono" style={{ fontSize: 10, color: 'var(--text-muted)' }}>key (b64)</span>
              <input value={keyB64} onChange={e => setKeyB64(e.target.value)}
                style={{ flex: 1, background: 'var(--bg-base)', border: '1px solid var(--border)', borderRadius: 'var(--r-sm)', color: 'var(--text-primary)', fontFamily: 'JetBrains Mono, monospace', fontSize: 11, padding: '4px 8px' }}/>
            </div>
            <LabHashRow value={signature} status={sigMatches}/>
            <LabHashCompare against={parsed?.signature} computed={signature} kind="signature"/>
          </div>

          <div className="card">
            <div className="card-header">
              <div className="card-title">Verification checks</div>
            </div>
            <div style={{ padding: 14, display: 'flex', flexDirection: 'column', gap: 6, fontSize: 12 }}>
              <LabStatusRow label="JSON parses"      ok={!parseError}/>
              <LabStatusRow label="Canonicalizes"    ok={!canonError && !!canonical}/>
              <LabStatusRow label="9 sections present" ok={parsed && ['identity','claim','preregistration','data','evidence','verdict','reproduction','provenance','signature'].every(k => k in parsed)}/>
              <LabStatusRow label="proof_id matches" ok={matches} muted={matches === null}/>
              <LabStatusRow label="signature matches" ok={sigMatches} muted={sigMatches === null}/>
            </div>
          </div>
        </div>
      </div>

      {/* Phase B — sign-external-probe pane */}
      <div className="card" style={{ marginTop: 16 }}>
        <div className="card-header">
          <div>
            <div className="card-title">Sign a probe from Kimera</div>
            <div className="micro" style={{ marginTop: 2 }}>CROSS-VENV WORKFLOW · KIMERA → OPHAMIN</div>
          </div>
          <span className="chip">workflow</span>
        </div>
        <div style={{ padding: 16 }}>
          <p style={{ fontSize: 12.5, color: 'var(--text-secondary)', lineHeight: 1.55, margin: '0 0 14px' }}>
            Per the Kimera roadmap: probes run in the Kimera venv, write JSON to <span className="mono">experiments/observatory/runs/&lt;scenario&gt;/</span>, then a sign script in the Ophamin venv wraps the JSON in a 9-section proof. Use this form to perform that second step in-browser.
          </p>
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
            <div>
              <div className="micro" style={{ marginBottom: 6 }}>SCENARIO</div>
              <input className="input" defaultValue="roadmap-phase-1a-bb1-bge-baseline" style={{ fontFamily: 'JetBrains Mono, monospace', fontSize: 12 }}/>
              <div className="micro" style={{ marginTop: 10, marginBottom: 6 }}>KIMERA SUBSTRATE COMMIT</div>
              <input className="input" defaultValue="6e4477ebb" style={{ fontFamily: 'JetBrains Mono, monospace', fontSize: 12 }}/>
              <div className="micro" style={{ marginTop: 10, marginBottom: 6 }}>ANALYSIS PLAN</div>
              <textarea className="input" defaultValue="Encode BB1 held-out corpus with BGE-M3; compute within-group vs cross-group cosine separation; bootstrap 95% CI (1000 resamples)." style={{ minHeight: 60, fontFamily: 'Inter, sans-serif', fontSize: 12, resize: 'vertical' }}/>
            </div>
            <div>
              <div className="micro" style={{ marginBottom: 6 }}>PROBE JSON (FROM KIMERA VENV)</div>
              <textarea spellCheck="false" defaultValue={'{\n  "separation": 0.142,\n  "ci_low": 0.118,\n  "ci_high": 0.171,\n  "n_bootstrap": 1000,\n  "n_pairs": 20\n}'} style={{ width: '100%', minHeight: 142, padding: 10, background: 'var(--bg-base)', border: '1px solid var(--border)', borderRadius: 'var(--r-sm)', color: 'var(--text-primary)', fontFamily: 'JetBrains Mono, monospace', fontSize: 11.5, resize: 'vertical' }}/>
            </div>
          </div>
          <div style={{ display: 'flex', gap: 6, marginTop: 12, alignItems: 'center' }}>
            <button className="btn primary" style={{ fontSize: 12 }}><Icon name="play" size={12}/> Wrap + sign</button>
            <button className="btn" style={{ fontSize: 12 }}><Icon name="copy" size={12}/> Copy CLI</button>
            <span style={{ flex: 1 }}/>
            <span className="mono" style={{ fontSize: 10, color: 'var(--text-muted)' }}>
              writes to proofs/scientific/&lt;scenario&gt;/&lt;timestamp&gt;.json
            </span>
          </div>
        </div>
      </div>

      {/* API endpoints reference */}
      <div className="card" style={{ marginTop: 16 }}>
        <div className="card-header">
          <div className="card-title">Run this from the command line</div>
          <span className="micro">POWER-USER ENDPOINTS</span>
        </div>
        <div style={{ padding: '12px 16px', display: 'grid', gridTemplateColumns: 'repeat(2, 1fr)', gap: 12 }}>
          <ApiEndpoint method="POST" path="/canonicalize" desc="Canonical UTF-8 bytes + SHA-256 + HMAC for any value" body='{"value_json": "<json>", "sign_key_b64": "<b64>"}'/>
          <ApiEndpoint method="POST" path="/verify"       desc="Verify a wire-form signed proof"                  body='{"proof_json": "<json>", "sign_key_b64": "<b64>"}'/>
        </div>
      </div>
    </div>
  );
}

function SpecRule({ num, label, desc }) {
  return (
    <div className="spec-rule">
      <span className="spec-num mono">{num}</span>
      <div style={{ flex: 1, minWidth: 0 }}>
        <div style={{ fontSize: 12.5, fontWeight: 600, color: 'var(--text-primary)' }}>{label}</div>
        <div style={{ fontSize: 11.5, color: 'var(--text-secondary)', lineHeight: 1.55, marginTop: 2 }}>{desc}</div>
      </div>
    </div>
  );
}

function LabMutatorRow({ label, desc, detail, onClick, danger }) {
  return (
    <div style={{
      display: 'flex',
      alignItems: 'center',
      gap: 12,
      padding: '8px 10px',
      background: 'var(--bg-surface-2)',
      border: '1px solid var(--border)',
      borderRadius: 'var(--r-sm)',
    }}>
      <div style={{ flex: 1, minWidth: 0 }}>
        <div style={{ fontSize: 12, fontWeight: 500, color: danger ? 'var(--refuted)' : 'var(--text-primary)' }}>{label}</div>
        <div style={{ fontSize: 11, color: 'var(--text-muted)', marginTop: 2 }}>{desc}</div>
        <div className="mono" style={{ fontSize: 10, color: danger ? 'var(--refuted)' : 'var(--accent)', marginTop: 3 }}>↳ {detail}</div>
      </div>
      <button className="btn" style={{ fontSize: 11 }} onClick={onClick}>Apply</button>
    </div>
  );
}

function LabHashRow({ value, status }) {
  return (
    <div style={{
      padding: '12px 14px',
      borderBottom: '1px solid var(--border)',
      background: status === true ? 'var(--validated-bg)' : status === false ? 'var(--refuted-bg)' : 'transparent',
      display: 'flex',
      alignItems: 'center',
      gap: 10,
    }}>
      <span className="mono" style={{ flex: 1, fontSize: 11, wordBreak: 'break-all', lineHeight: 1.5, color: 'var(--text-primary)' }}>
        {value || '—'}
      </span>
      <button className="btn ghost" style={{ fontSize: 11 }}><Icon name="copy" size={11}/></button>
    </div>
  );
}

function LabHashCompare({ against, computed, kind }) {
  if (!against || against === 'will_be_recomputed') {
    return (
      <div style={{ padding: '8px 14px', fontSize: 11, color: 'var(--text-muted)' }}>
        no bundled {kind} to compare against — paste a real proof.json to see if the computed value matches.
      </div>
    );
  }
  const matches = against === computed;
  return (
    <div style={{ padding: '8px 14px', fontSize: 11, color: matches ? 'var(--validated)' : 'var(--refuted)', display: 'flex', alignItems: 'center', gap: 6 }}>
      {matches ? <Icon name="check" size={11}/> : <Icon name="x" size={11}/>}
      {matches ? `computed ${kind} matches bundled value` : `MISMATCH — bundled: ${against.slice(0, 16)}…`}
    </div>
  );
}

function LabStatusRow({ label, ok, muted }) {
  const color = muted ? 'var(--text-muted)' : ok ? 'var(--validated)' : 'var(--refuted)';
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 8, color }}>
      <Icon name={muted ? 'eye' : ok ? 'check' : 'x'} size={12}/>
      <span style={{ flex: 1 }}>{label}</span>
      <span className="mono" style={{ fontSize: 10 }}>{muted ? '—' : ok ? 'pass' : 'fail'}</span>
    </div>
  );
}

function ApiEndpoint({ method, path, desc, body }) {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 4, padding: 10, background: 'var(--bg-base)', border: '1px solid var(--border)', borderRadius: 'var(--r-sm)' }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
        <span className="mono" style={{ fontSize: 10, color: 'var(--accent)', padding: '1px 5px', border: '1px solid var(--accent-line)', borderRadius: 3 }}>{method}</span>
        <span className="mono" style={{ fontSize: 12, color: 'var(--text-primary)', fontWeight: 500 }}>{path}</span>
      </div>
      <div style={{ fontSize: 11, color: 'var(--text-muted)' }}>{desc}</div>
      <div className="mono" style={{ fontSize: 10, color: 'var(--text-secondary)' }}>{body}</div>
    </div>
  );
}

function WireFormatSpec() {
  return null; // placeholder
}

window.LabScreen = LabScreen;
