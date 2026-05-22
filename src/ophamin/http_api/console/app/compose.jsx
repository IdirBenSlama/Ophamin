/** @jsxRuntime classic */ /** @jsx React.createElement */
/* global React, OPHAMIN, Icon */

// ComposeScreen — the visual authoring loop (R&D). Describe an experiment by
// picking a template + corpus + threshold from the live capability menu (or
// paste a full spec), then see — inline — the GROUNDING GATE result and the
// MATERIALIZE plan. No live model needed: it drives /authoring/validate and
// /authoring/materialize. This is the "describe an experiment, get a grounded
// scenario" loop, made visible.
function ComposeScreen() {
  const D = OPHAMIN;
  const caps = D.capabilities || {};
  const templates = caps.invariant_templates || [];
  const corpora = (caps.corpora || []).filter((c) => c.available);
  const base = window.OPHAMIN_API_BASE || '';

  const tmpl0 = templates[0] || {};
  const [mode, setMode] = React.useState('menu');         // 'menu' | 'json'
  const [template, setTemplate] = React.useState(tmpl0.name || 'recognition');
  const [corpus, setCorpus] = React.useState((corpora[0] && corpora[0].name) || 'enron');
  const [threshold, setThreshold] = React.useState('0.80');
  const [title, setTitle] = React.useState('');
  const [grounding, setGrounding] = React.useState('Tononi 2004 (IIT)');
  const [jsonText, setJsonText] = React.useState('');
  const [gate, setGate] = React.useState(null);
  const [plan, setPlan] = React.useState(null);
  const [busy, setBusy] = React.useState(false);
  const [err, setErr] = React.useState('');

  const tmpl = templates.find((t) => t.name === template) || tmpl0;

  // Keep the threshold default in step with the chosen template.
  React.useEffect(() => {
    if (tmpl && tmpl.name === 'phi') setThreshold('0.05');
    else if (tmpl && tmpl.name === 'manifold-topology') setThreshold('1');
    else setThreshold('0.80');
  }, [template]);

  function buildSpec() {
    if (mode === 'json') return JSON.parse(jsonText);
    const isSubstrate = corpus === '(substrate trajectory)';
    return {
      title: title || `${template} on ${corpus}`,
      scope: tmpl.scope || 'flow',
      facet: tmpl.facet || 'neuro',
      claim_statement: tmpl.describes || 'A falsifiable claim about the substrate.',
      operationalization: tmpl.describes || '',
      threshold: {
        metric: tmpl.metric || 'metric',
        comparator: tmpl.comparator || '>=',
        value: parseFloat(threshold),
        units: '',
      },
      grounding: [{ kind: 'paper', ref: grounding || 'unspecified', title: '' }],
      data_source: isSubstrate
        ? { kind: 'substrate-trajectory', name: 'kimera-swm' }
        : { kind: 'corpus', name: corpus },
      invariant_template: template,
      tools: ['statsmodels'],
      authored_by: 'human',
    };
  }

  async function post(path, spec) {
    const r = await fetch(base + path, {
      method: 'POST',
      headers: { 'content-type': 'application/json', accept: 'application/json' },
      body: JSON.stringify({ spec_json: JSON.stringify(spec) }),
    });
    if (!r.ok) throw new Error(path + ' -> HTTP ' + r.status);
    return r.json();
  }

  async function onCheck() {
    setErr(''); setBusy(true); setGate(null); setPlan(null);
    try {
      const spec = buildSpec();
      const [g, p] = await Promise.all([
        post('/authoring/validate', spec),
        post('/authoring/materialize', spec),
      ]);
      setGate(g); setPlan(p);
    } catch (e) {
      setErr(e.message || String(e));
    } finally { setBusy(false); }
  }

  const inputStyle = {
    background: 'var(--bg-base, #0b0e13)', color: 'var(--text-primary)',
    border: '1px solid var(--border)', borderRadius: 'var(--r-sm)',
    padding: '7px 9px', fontSize: 12, fontFamily: "'JetBrains Mono', monospace", width: '100%',
  };
  const labelStyle = { display: 'block', marginBottom: 12 };

  return (
    <div className="content-inner page">
      <div className="page-header">
        <div>
          <h1 className="page-title">Compose</h1>
          <div className="page-subtitle mono">Describe an experiment → grounding gate → materialize plan. No synthetic, no ungrounded.</div>
        </div>
      </div>

      <div className="agent-banner">
        <Icon name="scenarios" size={16}/>
        <div>
          Author a scenario by picking a <b>template + real corpus + threshold</b> from the live menu (or paste a spec). The <b>grounding gate</b> refuses anything synthetic or ungrounded before it can run; <b>materialize</b> shows the exact scenario it builds. The describe→proof loop, visible.
        </div>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 14, alignItems: 'start' }}>
        {/* Left: the spec form */}
        <div className="card" style={{ padding: 16 }}>
          <div style={{ display: 'flex', gap: 8, marginBottom: 14 }}>
            <button className={'btn' + (mode === 'menu' ? '' : ' ghost')} style={{ height: 28, fontSize: 11 }} onClick={() => setMode('menu')}>From menu</button>
            <button className={'btn' + (mode === 'json' ? '' : ' ghost')} style={{ height: 28, fontSize: 11 }} onClick={() => setMode('json')}>Paste spec</button>
          </div>

          {mode === 'menu' ? (
            <div>
              <label style={labelStyle}>
                <div className="micro" style={{ marginBottom: 4 }}>INVARIANT TEMPLATE</div>
                <select style={inputStyle} value={template} onChange={(e) => setTemplate(e.target.value)}>
                  {templates.map((t) => <option key={t.name} value={t.name}>{t.name} — {t.metric}</option>)}
                </select>
                {tmpl.describes && <div className="micro faint" style={{ marginTop: 4, textTransform: 'none', letterSpacing: 0 }}>{tmpl.describes}</div>}
              </label>
              <label style={labelStyle}>
                <div className="micro" style={{ marginBottom: 4 }}>DATA SOURCE (real corpus)</div>
                <select style={inputStyle} value={corpus} onChange={(e) => setCorpus(e.target.value)}>
                  {corpora.map((c) => <option key={c.name} value={c.name}>{c.name}</option>)}
                  <option value="(substrate trajectory)">(substrate trajectory — genesis stimuli)</option>
                </select>
              </label>
              <label style={labelStyle}>
                <div className="micro" style={{ marginBottom: 4 }}>THRESHOLD ({tmpl.comparator || '>='} {tmpl.metric || ''})</div>
                <input style={inputStyle} value={threshold} onChange={(e) => setThreshold(e.target.value)}/>
              </label>
              <label style={labelStyle}>
                <div className="micro" style={{ marginBottom: 4 }}>GROUNDING (paper / standard)</div>
                <input style={inputStyle} value={grounding} onChange={(e) => setGrounding(e.target.value)}/>
              </label>
              <label style={labelStyle}>
                <div className="micro" style={{ marginBottom: 4 }}>TITLE (optional)</div>
                <input style={inputStyle} value={title} onChange={(e) => setTitle(e.target.value)} placeholder={`${template} on ${corpus}`}/>
              </label>
            </div>
          ) : (
            <label style={labelStyle}>
              <div className="micro" style={{ marginBottom: 4 }}>SCENARIO SPEC (JSON)</div>
              <textarea style={{ ...inputStyle, minHeight: 280, resize: 'vertical' }} value={jsonText} onChange={(e) => setJsonText(e.target.value)} placeholder='{"title": "...", "scope": "flow", "invariant_template": "recognition", "threshold": {...}, "grounding": [...], "data_source": {...}}'/>
            </label>
          )}

          <button className="btn" style={{ marginTop: 4 }} onClick={onCheck} disabled={busy}>
            {busy ? 'Checking…' : 'Validate + Materialize'}
          </button>
          {err && <div className="micro" style={{ color: 'var(--refuted)', marginTop: 8 }}>{err}</div>}
        </div>

        {/* Right: the gate + plan results */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
          {/* Grounding gate */}
          <div className="card" style={{ padding: 16 }}>
            <div className="micro" style={{ marginBottom: 8 }}>GROUNDING GATE</div>
            {!gate ? (
              <div className="mono faint" style={{ fontSize: 12 }}>Compose a spec and check it.</div>
            ) : gate.acceptable ? (
              <div className="mono" style={{ color: 'var(--validated, #2dd4bf)', fontSize: 14 }}>✓ grounded — passes the gate</div>
            ) : (
              <div>
                <div className="mono" style={{ color: 'var(--refuted, #ef5b5b)', fontSize: 13, marginBottom: 8 }}>✗ {gate.violations.length} violation{gate.violations.length === 1 ? '' : 's'}</div>
                {gate.violations.map((v, i) => (
                  <div key={i} className="micro" style={{ color: v.severity === 'error' ? 'var(--refuted)' : 'var(--inconclusive)', marginTop: 4, textTransform: 'none', letterSpacing: 0 }}>
                    <b>{v.code}</b> — {v.message}{v.fix ? <span className="faint"> · {v.fix}</span> : ''}
                  </div>
                ))}
              </div>
            )}
          </div>

          {/* Materialize plan */}
          <div className="card" style={{ padding: 16 }}>
            <div className="micro" style={{ marginBottom: 8 }}>MATERIALIZE PLAN</div>
            {!plan ? (
              <div className="mono faint" style={{ fontSize: 12 }}>The runnable scenario this spec builds.</div>
            ) : !plan.acceptable ? (
              <div className="mono faint" style={{ fontSize: 12 }}>Fix the gate violations to see the plan.</div>
            ) : (
              <div>
                <div className="mono" style={{ fontSize: 13, color: 'var(--text-primary)' }}>{plan.scenario_name}</div>
                <div className="mono faint" style={{ fontSize: 11, marginTop: 6 }}>
                  {Object.entries(plan.plan || {}).map(([k, v]) => (
                    <div key={k}>{k}: <span style={{ color: 'var(--text-primary)' }}>{String(v)}</span></div>
                  ))}
                </div>
                <div className="micro" style={{ marginTop: 10, textTransform: 'none', letterSpacing: 0 }}>
                  {plan.needs_substrate
                    ? 'Runs on the live Kimera substrate — `PYTHONPATH=src python examples/run_spec.py <spec.json>`.'
                    : 'Static scenario — runs without a live substrate.'}
                </div>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}

window.ComposeScreen = ComposeScreen;
