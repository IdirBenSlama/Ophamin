/** @jsxRuntime classic */ /** @jsx React.createElement */
/* global React, OPHAMIN, Icon, VerdictPill, TierChip, SixWheelsLoader, formatNum */

const { useState: useRunState, useEffect: useRunEffect, useRef: useRunRef } = React;

function RunScreen({ initialScenario, onJumpToProof }) {
  const D = OPHAMIN;
  const [scenarioName, setScenarioName] = useRunState(initialScenario?.name || D.scenarios[0].name);
  const scenario = D.scenarios.find(s => s.name === scenarioName);
  const [kwargs, setKwargs] = useRunState(scenario.claim_available ? '{}' : '{\n  "trajectory_path": "/data/cycle-trace.parquet"\n}');
  const [status, setStatus] = useRunState('idle'); // idle, confirming, running, done, error
  const [elapsed, setElapsed] = useRunState(0);
  const [result, setResult] = useRunState(null);
  const [history, setHistory] = useRunState([]);
  const [errMsg, setErrMsg] = useRunState('');

  useRunEffect(() => {
    if (status !== 'running') return;
    let cancelled = false;
    const t0 = Date.now();
    const id = setInterval(() => setElapsed((Date.now() - t0) / 1000), 100);

    // Live run — POST /scenarios/{name}/run and map the signed-proof summary
    // into a bundle row. This is the one screen that changes state. There is
    // NO simulated fallback: a proof tool must never invent a verdict or a
    // proof_id. If the backend doesn't answer, the run fails loudly.
    (async () => {
      const base = window.OPHAMIN_API_BASE || '';
      try {
        const r = await fetch(base + '/scenarios/' + encodeURIComponent(scenario.name) + '/run', {
          method: 'POST',
          headers: { 'content-type': 'application/json', accept: 'application/json' },
          body: JSON.stringify({ kwargs_json: kwargs || '{}' }),
        });
        if (!r.ok) throw new Error('HTTP ' + r.status + (r.statusText ? ' ' + r.statusText : ''));
        const resp = await r.json();
        if (cancelled) return;
        clearInterval(id);
        const v = String(resp.verdict?.outcome || 'INCONCLUSIVE').toLowerCase();
        const obs = resp.verdict ? resp.verdict.observed_value : null;
        const thr = resp.verdict?.threshold?.value ?? scenario.claim?.threshold?.value ?? null;
        const pid = resp.proof_id || null;  // never fabricate — show the real absence
        const bundle = {
          tier: scenario.tier, scenario: scenario.name,
          date: new Date().toISOString().slice(0, 10), verdict: v,
          short_hash: pid ? String(pid).slice(0, 12) : '—',
          files: ['proof.json','proof.md','proof.html','proof.tex','proof.pdf'],
          observed: obs, threshold: thr, ci: [null, null],
          proof_id: pid,
          reasoning: resp.verdict ? resp.verdict.reasoning : undefined,
        };
        setStatus('done');
        setResult(bundle);
        setHistory(h => [{
          time: new Date().toLocaleTimeString(), scenario: scenario.name,
          verdict: v, elapsed: ((Date.now() - t0) / 1000).toFixed(2), live: true,
        }, ...h].slice(0, 6));
        window.toast && window.toast({
          kind: v === 'validated' ? 'success' : v === 'refuted' ? 'error' : 'warn',
          title: `${scenario.name} · ${v}`,
          msg: `observed ${typeof obs === 'number' ? obs.toFixed(4) : obs} · bundle ${bundle.short_hash}`,
          action: { label: 'View', onClick: () => onJumpToProof(bundle) },
        });
      } catch (e) {
        if (cancelled) return;
        clearInterval(id);
        console.warn('[ophamin] live run failed (no fabrication):', e.message);
        setStatus('error');
        setErrMsg(e.message || 'no response from backend');
      }
    })();

    return () => { cancelled = true; clearInterval(id); };
  }, [status]);

  useRunEffect(() => {
    setStatus('idle'); setResult(null); setElapsed(0); setErrMsg('');
    setKwargs(scenario.claim_available ? '{}' : (scenario.claim_unavailable_reason || '').includes('trajectory') ? '{\n  "trajectory_path": "/data/cycle-trace.parquet"\n}' : '{\n  "n_workers": 4\n}');
  }, [scenarioName]);

  const valid = (() => { try { JSON.parse(kwargs); return true; } catch (e) { return false; } })();

  return (
    <div className="content-inner page">
      <div className="page-header">
        <div>
          <h1 className="page-title">Run</h1>
          <div className="page-subtitle mono">
            This is the one place Ophamin actually changes state. Pick a scenario, set its kwargs, fire it.
          </div>
        </div>
        <div className="page-actions">
          <span style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: 11, color: 'var(--inconclusive)' }}>
            <Icon name="rocket" size={14}/> Runs are heavy. Confirm before firing.
          </span>
        </div>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: '1.4fr 1fr', gap: 16 }}>
        {/* LEFT: scenario picker + kwargs + run */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
          {/* Scenario picker */}
          <div className="card">
            <div className="card-header">
              <div className="card-title">Pick a scenario</div>
              <TierChip tier={scenario.tier}/>
            </div>
            <div className="card-body">
              <label className="micro" style={{ display: 'block', marginBottom: 6 }}>SELECT SCENARIO</label>
              <select className="input" value={scenarioName} onChange={e => setScenarioName(e.target.value)} style={{ height: 36 }}>
                {D.scenarios.map(s => (
                  <option key={s.name} value={s.name}>
                    {s.name} · {s.tier} · {s.family}{!s.claim_available ? ' · (needs args)' : ''}
                  </option>
                ))}
              </select>

              {/* Claim panel */}
              <div style={{ marginTop: 16 }}>
                {scenario.claim_available ? (
                  <div style={{ background: 'var(--bg-base)', border: '1px solid var(--border)', borderRadius: 'var(--r-sm)', padding: 14 }}>
                    <div className="micro" style={{ marginBottom: 8 }}>CLAIM</div>
                    <p style={{ fontSize: 13, color: 'var(--text-primary)', lineHeight: 1.55, margin: 0 }}>{scenario.claim.statement}</p>
                    <div style={{ marginTop: 12, display: 'grid', gridTemplateColumns: '70px 1fr', gap: '4px 12px', fontSize: 12 }}>
                      <span className="mono faint">threshold</span>
                      <span className="mono"><span style={{ color: 'var(--text-secondary)' }}>{scenario.claim.threshold.metric}</span> <span style={{ color: 'var(--accent)' }}>{scenario.claim.threshold.comparator}</span> <span style={{ fontWeight: 500 }}>{scenario.claim.threshold.value}</span> <span style={{ color: 'var(--text-muted)' }}>{scenario.claim.threshold.units}</span></span>
                      <span className="mono faint">H₀</span>
                      <span style={{ color: 'var(--text-secondary)' }}>{scenario.claim.h0}</span>
                      <span className="mono faint">H₁</span>
                      <span style={{ color: 'var(--text-secondary)' }}>{scenario.claim.h1}</span>
                    </div>
                  </div>
                ) : (
                  <div style={{ background: 'var(--inconclusive-bg)', border: '1px solid var(--inconclusive-line)', borderRadius: 'var(--r-sm)', padding: 14, color: 'var(--inconclusive)' }}>
                    <div className="micro" style={{ marginBottom: 4, color: 'var(--inconclusive)' }}>CLAIM REQUIRES ARGS</div>
                    <span style={{ fontSize: 12.5 }}>{scenario.claim_unavailable_reason}</span>
                  </div>
                )}
              </div>
            </div>
          </div>

          {/* Kwargs editor */}
          <div className="card">
            <div className="card-header">
              <div className="card-title">Arguments <span className="micro" style={{ marginLeft: 8 }}>JSON</span></div>
              <span style={{ fontSize: 11, color: valid ? 'var(--validated)' : 'var(--refuted)' }}>{valid ? '✓ valid JSON' : '✗ invalid JSON'}</span>
            </div>
            <div style={{ position: 'relative' }}>
              <textarea
                spellCheck="false"
                value={kwargs}
                onChange={e => setKwargs(e.target.value)}
                style={{
                  width: '100%',
                  height: 120,
                  background: 'var(--bg-base)',
                  border: 'none',
                  borderRadius: 0,
                  padding: '14px 16px',
                  color: 'var(--text-primary)',
                  fontFamily: 'JetBrains Mono, monospace',
                  fontSize: 12,
                  lineHeight: 1.65,
                  resize: 'vertical',
                  outline: 'none',
                  display: 'block',
                }}
              />
            </div>
          </div>

          {/* Status + Run button */}
          <div className="card" style={{
            background: status === 'running' ? 'var(--accent-soft)' : status === 'done' ? 'var(--validated-bg)' : status === 'error' ? 'var(--refuted-bg)' : 'var(--bg-surface)',
            borderColor: status === 'running' ? 'var(--accent-line)' : status === 'done' ? 'var(--validated-line)' : status === 'error' ? 'var(--refuted-line)' : 'var(--border)',
            transition: 'all 280ms cubic-bezier(0.4,0,0.2,1)',
          }}>
            <div style={{ padding: 18, display: 'flex', alignItems: 'center', gap: 16 }}>
              {status === 'running' ? <SixWheelsLoader size={48}/> : (
                <div style={{
                  width: 48, height: 48, borderRadius: '50%',
                  background: status === 'done' ? 'var(--validated)' : status === 'error' ? 'var(--refuted)' : 'var(--bg-elevated)',
                  display: 'grid', placeItems: 'center',
                  color: status === 'done' || status === 'error' ? '#07120f' : 'var(--text-muted)',
                  border: '1px solid var(--border-strong)',
                }}>
                  <Icon name={status === 'done' ? 'check' : status === 'error' ? 'x' : 'play'} size={20}/>
                </div>
              )}
              <div style={{ flex: 1 }}>
                <div className="micro" style={{ marginBottom: 2 }}>STATUS</div>
                <div style={{ fontSize: 16, fontWeight: 600, color: status === 'running' ? 'var(--accent)' : status === 'done' ? 'var(--validated)' : status === 'error' ? 'var(--refuted)' : 'var(--text-primary)' }}>
                  {status === 'idle' && 'Idle · ready'}
                  {status === 'confirming' && 'Confirm to fire'}
                  {status === 'running' && <>Running · <span className="mono tnum">{elapsed.toFixed(1)}s</span></>}
                  {status === 'done' && <>Done · {result?.verdict}</>}
                  {status === 'error' && 'Error · loud-fail'}
                </div>
                <div style={{ fontSize: 11, color: 'var(--text-muted)', marginTop: 2 }}>
                  {status === 'idle' && 'press Run to send POST /scenarios/' + scenarioName + '/run'}
                  {status === 'confirming' && 'this is the one write surface — runs are heavy'}
                  {status === 'running' && 'sending to substrate · awaiting proof bundle'}
                  {status === 'done' && result && <>verdict <span style={{ color: `var(--${result.verdict})` }}>{result.verdict.toUpperCase()}</span> · observed {formatNum(result.observed)} · {result.short_hash}</>}
                  {status === 'error' && <>live run failed · <span style={{ color: 'var(--refuted)' }}>{errMsg || 'no response from backend'}</span> · nothing fabricated</>}
                </div>
              </div>
              <div style={{ display: 'flex', gap: 8 }}>
                {status === 'idle' && (
                  <button className="btn primary" onClick={() => setStatus('confirming')} disabled={!valid || !scenario.claim_available}>
                    <Icon name="play" size={14}/> Run scenario
                  </button>
                )}
                {status === 'confirming' && <>
                  <button className="btn ghost" onClick={() => setStatus('idle')}>Cancel</button>
                  <button className="btn primary" onClick={() => { setStatus('running'); setResult(null); }}>
                    Confirm fire <Icon name="rocket" size={14}/>
                  </button>
                </>}
                {status === 'running' && <button className="btn" disabled>Running…</button>}
                {(status === 'done' || status === 'error') && <>
                  <button className="btn" onClick={() => { setStatus('idle'); setResult(null); }}>Reset</button>
                  {status === 'done' && <button className="btn primary" onClick={() => onJumpToProof(result)}>View bundle <Icon name="chevronR" size={14}/></button>}
                </>}
              </div>
            </div>
            {status === 'done' && result && (
              <div style={{ padding: 14, borderTop: '1px solid var(--border)', display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 12, fontSize: 12 }}>
                <ResultMetric label="VERDICT" v={<VerdictPill verdict={result.verdict}/>}/>
                <ResultMetric label="OBSERVED" v={<span className="mono tnum" style={{ fontSize: 14, fontWeight: 600 }}>{formatNum(result.observed)}</span>}/>
                <ResultMetric label="ELAPSED" v={<span className="mono tnum" style={{ fontSize: 14, fontWeight: 600 }}>{elapsed.toFixed(2)}s</span>}/>
                <ResultMetric label="HASH" v={<span className="mono" style={{ fontSize: 11 }}>{result.short_hash}</span>}/>
              </div>
            )}
          </div>
        </div>

        {/* RIGHT: History + curl */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
          {/* Console */}
          <div className="card">
            <div className="card-header">
              <div className="card-title">Live console</div>
              <span className="mono faint" style={{ fontSize: 10 }}>POST /scenarios/…/run</span>
            </div>
            <div style={{
              padding: 14,
              fontFamily: 'JetBrains Mono, monospace',
              fontSize: 11.5,
              lineHeight: 1.65,
              background: 'var(--bg-base)',
              minHeight: 200,
              maxHeight: 280,
              overflow: 'auto',
            }}>
              <LogLine ts="·" lvl="info" msg={'$ ophamin run --scenario ' + scenarioName}/>
              <LogLine ts="·" lvl="info" msg={'POST /scenarios/' + scenarioName + '/run'}/>
              <LogLine ts="·" lvl="dim"  msg={'kwargs: ' + (valid ? kwargs.replace(/\s+/g, ' ') : '<invalid>')}/>
              {status === 'running' && <>
                <LogLine ts="·" lvl="dim" msg="awaiting the substrate — preregister plan, compute pillars, sign the bundle…"/>
                {elapsed > 2.5 && <LogLine ts="·" lvl="dim" msg="still running — heavy scenarios take a while"/>}
              </>}
              {status === 'done' && result && <>
                <LogLine ts="·" lvl="info" msg={'method: ' + scenario.method}/>
                <LogLine ts="·" lvl="info" msg={'observed: ' + formatNum(result.observed)}/>
                <LogLine ts="·" lvl="ok"   msg={'verdict: ' + result.verdict.toUpperCase()}/>
                <LogLine ts="·" lvl="info" msg={'bundle: ' + result.short_hash + (result.proof_id ? '' : ' (no proof_id returned)')}/>
                <LogLine ts="·" lvl="ok"   msg={'done in ' + elapsed.toFixed(2) + 's'}/>
              </>}
              {status === 'error' && <>
                <LogLine ts="·" lvl="err" msg={'live run failed: ' + (errMsg || 'no response from backend')}/>
                <LogLine ts="·" lvl="dim" msg="no verdict, no bundle — nothing fabricated"/>
              </>}
              {status === 'idle' && <div className="faint">awaiting input · press Run to fire</div>}
            </div>
          </div>

          {/* Run history */}
          <div className="card" style={{ flex: 1 }}>
            <div className="card-header">
              <div className="card-title">This session</div>
              <span className="micro">{history.length} RUNS</span>
            </div>
            {history.length === 0 ? (
              <div className="empty" style={{ padding: 28 }}>No runs yet this session</div>
            ) : (
              <div style={{ padding: '8px 4px' }}>
                {history.map((h, i) => (
                  <div key={i} style={{ display: 'flex', alignItems: 'center', gap: 10, padding: '8px 14px', borderBottom: i < history.length - 1 ? '1px solid var(--border)' : 'none' }}>
                    <span className="mono faint" style={{ fontSize: 10 }}>{h.time}</span>
                    <VerdictPill verdict={h.verdict}/>
                    <span style={{ flex: 1, fontSize: 12 }}>{h.scenario}</span>
                    <span className="mono" style={{ fontSize: 11, color: 'var(--text-muted)' }}>{h.elapsed}s</span>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}

function ResultMetric({ label, v }) {
  return (
    <div>
      <div className="micro" style={{ marginBottom: 4 }}>{label}</div>
      <div>{v}</div>
    </div>
  );
}

function LogLine({ ts, lvl, msg }) {
  const colors = { info: 'var(--text-secondary)', dim: 'var(--text-muted)', ok: 'var(--validated)', err: 'var(--refuted)', warn: 'var(--inconclusive)' };
  return (
    <div style={{ display: 'flex', gap: 8, color: colors[lvl] }}>
      <span style={{ color: 'var(--text-faint)' }}>{ts}</span>
      <span style={{ color: 'var(--text-muted)', width: 36, textTransform: 'uppercase', fontSize: 10 }}>{lvl}</span>
      <span style={{ flex: 1 }}>{msg}</span>
    </div>
  );
}

window.RunScreen = RunScreen;
