/** @jsxRuntime classic */ /** @jsx React.createElement */
/* global React, OPHAMIN, Icon */

const { useState: useAgState } = React;

function AgentsScreen() {
  const D = OPHAMIN;
  const [active, setActive] = useAgState(D.agents[0].id);
  const agent = D.agents.find(a => a.id === active);

  return (
    <div className="content-inner page">
      <div className="page-header">
        <div>
          <h1 className="page-title">Agents</h1>
          <div className="page-subtitle mono">Reference catalog of the seven agents. To actually invoke one, use Chat — it routes your question to the right agent.</div>
        </div>
        <div className="page-actions">
          <span className="live-pill advisory">
            <span className="dot"></span>
            advisory only
          </span>
          <span style={{ fontSize: 11, color: 'var(--text-muted)' }}>via OPHAMIN_LLM_BASE_URL · Ollama / MLX-LM / LM Studio</span>
        </div>
      </div>

      <div className="agent-banner">
        <Icon name="eye" size={16}/>
        <div>
          <b>LLMs never override <span className="mono">Verdict.decide(...)</span></b>, never author statistical scoring, and never run inside the substrate's measurement path. Every call persists a content-hashed, HMAC-signed <span className="mono">LLMCallRecord</span> under <span className="mono">proofs/llm_calls/</span>.
        </div>
      </div>

      <div className="agents-layout">
        <aside className="agents-rail">
          {D.agents.map(a => (
            <div key={a.id}
              className={'agent-item' + (active === a.id ? ' active' : '')}
              onClick={() => setActive(a.id)}>
              <div className="agent-item-row">
                <span className={'agent-tier-dot agent-tier-' + a.tier}/>
                <span className="agent-name">{a.label}</span>
              </div>
              <div className="agent-cli mono">ophamin agent {a.id}</div>
            </div>
          ))}
        </aside>

        <div className="card" style={{ overflow: 'hidden' }}>
          <div className="card-header">
            <div>
              <div className="card-title">{agent.label}</div>
              <div className="micro" style={{ marginTop: 2 }}>{agent.tier.toUpperCase()} TIER</div>
            </div>
            <span className="chip">advisory</span>
          </div>

          <div style={{ padding: 20, display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16 }}>
            <div>
              <div className="micro" style={{ marginBottom: 6 }}>WHAT IT DOES</div>
              <p style={{ fontSize: 13, lineHeight: 1.55, color: 'var(--text-secondary)' }}>{agent.desc}</p>

              <div className="micro" style={{ margin: '14px 0 6px' }}>CLI</div>
              <pre style={{ background: 'var(--bg-base)', border: '1px solid var(--border)', borderRadius: 'var(--r-sm)', padding: '10px 12px', fontFamily: 'JetBrains Mono, monospace', fontSize: 12, color: 'var(--text-primary)', margin: 0, whiteSpace: 'pre-wrap' }}>
{agentExampleCli(agent.id)}
              </pre>

              <div className="micro" style={{ margin: '14px 0 6px' }}>INPUT</div>
              <textarea spellCheck="false" style={{ width: '100%', minHeight: 120, padding: 10, background: 'var(--bg-base)', border: '1px solid var(--border)', borderRadius: 'var(--r-sm)', color: 'var(--text-primary)', fontFamily: 'JetBrains Mono, monospace', fontSize: 12, resize: 'vertical' }}
                defaultValue={agentExampleInput(agent.id)}/>

              <div style={{ display: 'flex', gap: 8, marginTop: 12 }}>
                <button className="btn primary" style={{ fontSize: 12 }}><Icon name="play" size={12}/> Run agent</button>
                <button className="btn" style={{ fontSize: 12 }}>Dry-run</button>
              </div>
            </div>

            <div>
              <div className="micro" style={{ marginBottom: 6 }}>WHAT THE AGENT REPLIES</div>
              <div style={{ background: 'var(--bg-base)', border: '1px solid var(--border)', borderRadius: 'var(--r-sm)', padding: 12, fontFamily: 'JetBrains Mono, monospace', fontSize: 11.5, lineHeight: 1.65, color: 'var(--text-primary)', minHeight: 220 }}>
                {agentExampleOutput(agent.id)}
              </div>

              <div className="micro" style={{ margin: '14px 0 6px' }}>AUDIT TRAIL FOR THIS CALL</div>
              <div style={{ display: 'grid', gridTemplateColumns: '110px 1fr', gap: '4px 12px', fontSize: 12 }}>
                <span className="mono faint">model</span><span className="mono">qwen2.5-coder:14b-instruct</span>
                <span className="mono faint">base_url</span><span className="mono">http://localhost:11434/v1</span>
                <span className="mono faint">content_hash</span><span className="mono" style={{ wordBreak: 'break-all', fontSize: 10 }}>sha256:4a8e1f…d203</span>
                <span className="mono faint">signature</span><span className="mono" style={{ wordBreak: 'break-all', fontSize: 10 }}>04c1b2be…ba9c71</span>
                <span className="mono faint">tokens_in</span><span className="mono">412</span>
                <span className="mono faint">tokens_out</span><span className="mono">186</span>
                <span className="mono faint">latency_s</span><span className="mono">1.84</span>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

function agentExampleCli(id) {
  return {
    prereg:        'ophamin agent prereg ./claim.md\n# or pass a proof.json',
    'scenario-gen':'ophamin agent scenario-gen my-new-scenario \\\n  --claim "p95 latency <= 50ms"',
    adapt:         'ophamin agent adapt \\\n  --name custom-corpus \\\n  --description "JSONL log lines with field=msg"',
    brief:         'ophamin agent brief proofs/scientific/.../proof.json',
    triage:        'ophamin agent triage \\\n  proofs/scientific/.../refuted.../proof.json',
    confounds:     'ophamin agent confounds \\\n  proofs/scientific/.../validated.../proof.json',
    query:         'ophamin agent query \\\n  "Which scenarios are refuted in the last 7 days?"',
  }[id];
}

function agentExampleInput(id) {
  return {
    prereg: '{\n  "statement": "Substrate latency p95 ≤ 50ms",\n  "threshold": {"metric": "p95_latency", "comparator": "<=", "value": 50, "units": "ms"}\n}',
    'scenario-gen': '{\n  "name": "latency-floor",\n  "claim": "p95 HTTP latency ≤ 50ms",\n  "corpus": "synthetic-load"\n}',
    adapt: '{\n  "name": "custom-jsonl",\n  "format": "jsonl",\n  "field": "msg",\n  "description": "Application log lines"\n}',
    brief: 'proofs/scientific/concentrated-immune-siege/2026-05-16_validated_6d47d8c9a2de/proof.json',
    triage: 'proofs/scientific/logic-topology-siege/2026-05-16_refuted_94e389abcd63/proof.json',
    confounds: 'proofs/scientific/concentrated-immune-siege/2026-05-16_validated_6d47d8c9a2de/proof.json',
    query: 'Which scenarios have moved from validated → refuted in the last 7 days?',
  }[id];
}

function agentExampleOutput(id) {
  const map = {
    prereg: (
      <>
        <div style={{ color: 'var(--validated)' }}>● falsifiable: YES</div>
        <div style={{ marginTop: 6, color: 'var(--text-secondary)' }}>
          The claim names a measurable metric (<span style={{ color: 'var(--accent)' }}>p95_latency</span>),
          a comparator (<span style={{ color: 'var(--accent)' }}>≤</span>), a numeric threshold (50), and units (ms).
          Both H₀ and H₁ are implied by the comparator.
        </div>
        <div style={{ marginTop: 10, color: 'var(--text-muted)' }}>Concerns:</div>
        <div style={{ color: 'var(--text-secondary)' }}>— Corpus not specified. The claim is falsifiable in shape but not yet in deployment.</div>
        <div style={{ color: 'var(--text-secondary)' }}>— Threshold is conventional (50ms) — confirm this is preregistered, not post-hoc.</div>
      </>
    ),
    'scenario-gen': (
      <>
        <div style={{ color: 'var(--text-muted)' }}># Generated scenarios/latency_floor.py</div>
        <div><span style={{ color: 'var(--viz-3)' }}>class</span> <span style={{ color: 'var(--accent)' }}>LatencyFloorScenario</span>(Scenario):</div>
        <div>{'    '}name = <span style={{ color: '#c4b5fd' }}>"latency-floor"</span></div>
        <div>{'    '}tier = <span style={{ color: '#c4b5fd' }}>"engineering"</span></div>
        <div>{'    '}corpus_name = <span style={{ color: '#c4b5fd' }}>"synthetic-load"</span></div>
        <div>{'    '}target = <span style={{ color: '#c4b5fd' }}>"entity"</span></div>
        <div style={{ marginTop: 4 }}>{'    '}<span style={{ color: 'var(--viz-3)' }}>def</span> <span style={{ color: 'var(--accent)' }}>build_claim</span>(self): ...</div>
        <div>{'    '}<span style={{ color: 'var(--viz-3)' }}>def</span> <span style={{ color: 'var(--accent)' }}>score</span>(self, results):</div>
        <div>{'        '}<span style={{ color: 'var(--text-muted)' }}># TODO: stub — author the scoring</span></div>
        <div>{'        '}<span style={{ color: 'var(--viz-3)' }}>raise</span> NotImplementedError</div>
      </>
    ),
    adapt: (
      <>
        <div style={{ color: 'var(--text-muted)' }}># Generated seeing/corpus/custom_jsonl.py — 142 lines</div>
        <div><span style={{ color: 'var(--viz-3)' }}>class</span> <span style={{ color: 'var(--accent)' }}>CustomJsonlCorpus</span>(DatasetConnector):</div>
        <div>{'    '}name = <span style={{ color: '#c4b5fd' }}>"custom-jsonl"</span></div>
        <div>{'    '}<span style={{ color: 'var(--viz-3)' }}>def</span> <span style={{ color: 'var(--accent)' }}>stream</span>(self, path) -&gt; Iterator[Record]: ...</div>
        <div>{'    '}<span style={{ color: 'var(--viz-3)' }}>def</span> <span style={{ color: 'var(--accent)' }}>content_hash</span>(self) -&gt; str: ...</div>
        <div style={{ marginTop: 6, color: 'var(--text-secondary)' }}>✓ field schema inferred from first 100 lines</div>
        <div style={{ color: 'var(--text-secondary)' }}>✓ matches <span className="mono">DatasetConnector</span> protocol</div>
      </>
    ),
    brief: (
      <>
        <div style={{ color: 'var(--accent)' }}>concentrated-immune-siege · VALIDATED</div>
        <div style={{ marginTop: 6, color: 'var(--text-secondary)' }}>
          Across 1,000 cycles, Kimera's GWF blocked 16 of 500 benign inputs (3.2% false-positive rate, Wilson 95% CI 1.98%–5.13%) — comfortably under the pre-registered ceiling of 10%. The full defense stack (GWF + manipulation-detector + Danger-Theory-Gate) caught 272 of 500 malicious inputs (54.4%) but at the cost of a 15.8% benign false-positive rate.
        </div>
        <div style={{ marginTop: 10, color: 'var(--text-muted)' }}>What this means:</div>
        <div style={{ color: 'var(--text-secondary)' }}>The architectural false-positive ceiling holds for the GWF in isolation. The downstream layers tighten detection but degrade benign-input throughput — an architectural trade-off worth surfacing.</div>
      </>
    ),
    triage: (
      <>
        <div style={{ color: 'var(--refuted)' }}>logic-topology-siege · REFUTED (39.6%, threshold 60%)</div>
        <div style={{ marginTop: 6, color: 'var(--text-muted)' }}>Follow-up scenarios:</div>
        <div style={{ color: 'var(--text-secondary)' }}>1. <span className="mono">walker-step-budget</span> — vary step budget; does traversal rate scale?</div>
        <div style={{ color: 'var(--text-secondary)' }}>2. <span className="mono">corpus-density-control</span> — test on lower-density commit subgraphs to isolate topology effect.</div>
        <div style={{ color: 'var(--text-secondary)' }}>3. <span className="mono">walker-seed-stability</span> — fix walker seed; is the 39.6% structural or stochastic?</div>
        <div style={{ marginTop: 8, color: 'var(--text-muted)' }}>None of these adopts the original claim's threshold — they decompose <i>why</i> it failed.</div>
      </>
    ),
    confounds: (
      <>
        <div style={{ color: 'var(--accent)' }}>Red-team · concentrated-immune-siege</div>
        <div style={{ marginTop: 6, color: 'var(--text-muted)' }}>Alternative explanations for the 3.2% false-positive rate:</div>
        <div style={{ color: 'var(--text-secondary)' }}>1. <b>Corpus bias</b> — benign-labelled records may already be filtered upstream by metasploit/SecLists curation. Disambiguating test: inject random text from <span className="mono">flores-200</span> as benign control.</div>
        <div style={{ color: 'var(--text-secondary)' }}>2. <b>Label leakage</b> — GWF may have implicit access to corpus tags. Test: shuffle benign/malicious labels post-hoc; verdict should hold or flip predictably.</div>
        <div style={{ color: 'var(--text-secondary)' }}>3. <b>Sample-size artifact</b> — n=500 benign gives Wilson CI [1.98%, 5.13%]. At n=10,000 the rate could rise. Test: rerun at 10× sample.</div>
      </>
    ),
    query: (
      <>
        <div style={{ color: 'var(--accent)' }}>Found 3 scenarios with verdict flips (validated → refuted) in last 7 days:</div>
        <div style={{ marginTop: 6, color: 'var(--text-secondary)' }}>1. <span className="mono">concentrated-immune-siege</span> — 2 flips (05-14, 05-15); related to GWF threshold tuning commit.</div>
        <div style={{ color: 'var(--text-secondary)' }}>2. <span className="mono">throughput-ceiling</span> — 1 inconclusive on 05-15 after substrate commit <span className="mono">179edd23</span>.</div>
        <div style={{ color: 'var(--text-secondary)' }}>3. <span className="mono">sinew-conservation</span> — 1 refutation on 05-14 with M4 ratio 0.087 (threshold 0.05).</div>
        <div style={{ marginTop: 8, color: 'var(--text-muted)' }}>Suggested action: run <span className="mono">ophamin agent triage</span> on the refuted bundles.</div>
      </>
    ),
  };
  return map[id];
}

window.AgentsScreen = AgentsScreen;
