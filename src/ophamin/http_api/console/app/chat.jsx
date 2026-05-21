/** @jsxRuntime classic */ /** @jsx React.createElement */
/* global React, OPHAMIN, Icon, SixWheelsLoader, formatNum */
// Chat — conversational front door to Ophamin + Kimera-SWM via the 7 agents.

const { useState: useChState, useEffect: useChEffect, useRef: useChRef } = React;

// ─── Mock corpus of conversations to seed the chat with realism ──
// Each "agent" maps to one of the real `ophamin agent <id>` CLI tools.
const STARTER_CHIPS = [
  { id: 'why-refuted',  label: 'Why was logic-topology-siege refuted?',           agent: 'triage' },
  { id: 'gwf-fpr',      label: 'How is the GWF false-positive rate computed?',     agent: 'brief' },
  { id: 'sinew-explain',label: 'What does sinew-conservation actually measure?',   agent: 'brief' },
  { id: 'check-claim',  label: 'Is "p95 latency ≤ 50ms" a falsifiable claim?',     agent: 'prereg' },
  { id: 'drift-7d',     label: 'Which scenarios flipped verdict in the last week?',agent: 'query' },
  { id: 'red-team',     label: 'Red-team the latest validated immune-siege proof.',agent: 'confounds' },
  { id: 'takwin',       label: 'What does Takwin.run() do per cycle?',                  agent: 'brief' },
  { id: 'mem-deform',   label: 'How does memory-as-deformation manifest empirically?', agent: 'brief' },
  { id: 'paths-seam',   label: 'What is the Path-A / Path-B seam, and why is it unfused?', agent: 'brief' },
  { id: 'roadmap-now',  label: 'What phase of the Kimera roadmap is in flight right now?', agent: 'query' },
];

const AGENT_META = {
  prereg:        { tier: 'reasoning', label: 'Prereg validator',   icon: 'eye' },
  'scenario-gen':{ tier: 'coder',     label: 'Scenario generator',  icon: 'code' },
  adapt:         { tier: 'coder',     label: 'Adapter generator',   icon: 'code' },
  brief:         { tier: 'workhorse', label: 'Proof brief',         icon: 'eye' },
  triage:        { tier: 'reasoning', label: 'Refuted triage',      icon: 'rocket' },
  confounds:     { tier: 'reasoning', label: 'Confound enumerator', icon: 'eye' },
  query:         { tier: 'fast',      label: 'Bundle query',        icon: 'search' },
};

// Mocked agent replies — tied to the real proofs/scenarios in OPHAMIN data
function agentReply(question, agent) {
  const q = question.toLowerCase();
  if (q.includes('logic-topology') || q.includes('refuted')) {
    return {
      agent: 'triage',
      summary: 'logic-topology-siege · REFUTED · sustained traversal rate 39.6% < threshold 60%',
      body: [
        { type: 'text', content: "The walker's sustained-traversal rate on the Linux-kernel commit graph fell to 39.6% (Wilson 95% CI [36.0%, 43.4%]) against a pre-registered threshold of 60%. The framework's commitment held — the substrate did not." },
        { type: 'list', label: 'Suggested follow-up scenarios', items: [
          { name: 'walker-step-budget',     desc: 'Vary step budget; test whether 39.6% is a budget artifact or structural.' },
          { name: 'corpus-density-control', desc: 'Stratify by commit-graph branching factor to isolate topology from corpus density.' },
          { name: 'walker-seed-stability',  desc: 'Fix walker seed; N=20 reruns to characterize stochastic vs structural failure.' },
        ]},
        { type: 'cta', label: 'View the refuted bundle', kind: 'open-proof', target: { scenario: 'logic-topology-siege', date: '2026-05-16' } },
      ],
    };
  }
  if (q.includes('gwf') || q.includes('false-positive')) {
    return {
      agent: 'brief',
      summary: 'GWF false-positive rate · O.immune.false_positive',
      body: [
        { type: 'text', content: "The General Workspace Filter (GWF) is Kimera-SWM's first-line adversarial filter. Ophamin streams up to 1,000 records from the offensive-security corpus (4.4M labelled records) through the entity target, counting how often the GWF blocks a benign-labelled input." },
        { type: 'kv', items: [
          ['operationalization', 'fraction of benign records the GWF returns a blocking verdict for'],
          ['library', 'statsmodels 0.14.6 (Wilson 95% CI)'],
          ['n', '500 benign records per run'],
          ['pre-registered threshold', '≤ 10%'],
          ['latest verdict', '3.2% — VALIDATED (CI 1.98%–5.13%)'],
        ]},
        { type: 'text', content: "The full defense stack (GWF + manipulation-detector + Danger-Theory-Gate) catches more malicious inputs (54.4%) but at a 15.8% benign false-positive cost — a trade-off the proof surfaces explicitly." },
      ],
    };
  }
  if (q.includes('sinew')) {
    return {
      agent: 'brief',
      summary: 'sinew-conservation · M4 invariant under perturbation',
      body: [
        { type: 'text', content: "sinew-conservation tests whether Kimera's walker maintains the M4 statistical invariant when its trajectory is perturbed. The walker is supposed to conserve a particular fourth-moment ratio across cycles; if that ratio drifts above 0.05 under perturbation, the conservation property is broken." },
        { type: 'text', content: "It's an empirical-deep tier scenario — directly probing substrate physics, not just behavior. Falsification consequence: 'Sinew breaks M4 invariant', which would unwind a load-bearing claim about the substrate's internal structure." },
        { type: 'kv', items: [
          ['threshold', 'walker_m4_conservation_ratio ≤ 0.05'],
          ['corpus', 'takwin-trajectory (500 cycles)'],
          ['latest verdict', '0.087 — REFUTED (CI 0.074–0.112)'],
        ]},
        { type: 'cta', label: 'Read the latest sinew-conservation proof', kind: 'open-proof', target: { scenario: 'sinew-conservation', date: '2026-05-14' } },
      ],
    };
  }
  if (q.includes('falsifiable') || q.includes('claim')) {
    return {
      agent: 'prereg',
      summary: 'Claim falsifiability check',
      body: [
        { type: 'text', content: "Your claim — \"p95 latency ≤ 50ms\" — has a measurable metric (p95_latency), a comparator (≤), a numeric threshold (50), and units (ms). H₀ and H₁ are implied by the comparator." },
        { type: 'badge', color: 'var(--validated)', label: 'falsifiable: YES' },
        { type: 'list', label: 'Concerns before you run it', items: [
          { name: 'Corpus unspecified',  desc: 'The claim is falsifiable in shape but not yet in deployment. Pre-register the corpus and its content_hash.' },
          { name: 'Conventional threshold', desc: '50ms is a frequent default. Confirm it was committed to before measurement, not adjusted after.' },
          { name: 'Latency definition',     desc: 'Wall-time? CPU-time? End-to-end including network? Operationalization is what makes the threshold portable.' },
        ]},
        { type: 'cta', label: 'Scaffold a Scenario subclass for this claim', kind: 'open-agent', target: { agent: 'scenario-gen' } },
      ],
    };
  }
  if (q.includes('flip') || q.includes('drift') || q.includes('week')) {
    return {
      agent: 'query',
      summary: 'Verdict-flip query · last 7 days',
      body: [
        { type: 'text', content: "Found 3 scenarios with verdict transitions in the 7-day window (2026-05-13 → 2026-05-19):" },
        { type: 'list', label: 'Transitions', items: [
          { name: 'concentrated-immune-siege', desc: '2 flips (validated→refuted→validated) coincident with GWF tuning commit 4552de7e.' },
          { name: 'throughput-ceiling',        desc: 'INCONCLUSIVE on 05-15 (p95 = 3.81s, threshold = 4.0s, CI crossed). Resolved validated on 05-19.' },
          { name: 'sinew-conservation',        desc: 'New REFUTED on 05-14 (M4 ratio 0.087 vs 0.05 threshold).' },
        ]},
        { type: 'cta', label: 'Open the Drift surface', kind: 'open-drift' },
      ],
    };
  }
  if (q.includes('red-team') || q.includes('confound')) {
    return {
      agent: 'confounds',
      summary: 'Alternative explanations · concentrated-immune-siege validated proof',
      body: [
        { type: 'text', content: 'Before drawing scientific conclusions from this 3.2% false-positive rate, three confounds worth ruling out:' },
        { type: 'list', label: 'Confounds', items: [
          { name: 'Corpus selection bias', desc: 'Benign-labelled records may already be pre-filtered by metasploit/SecLists curation. Test: inject random text from flores-200 as a benign control.' },
          { name: 'Label leakage',         desc: 'GWF may have implicit access to corpus tags. Test: shuffle benign/malicious labels post-hoc.' },
          { name: 'Sample-size artifact',  desc: 'n=500 gives Wilson CI [1.98%, 5.13%]. At n=10,000 the rate could rise. Test: 10× sample.' },
        ]},
      ],
    };
  }

  if (q.includes('takwin') || q.includes('per cycle') || q.includes('kccl')) {
    return {
      agent: 'brief',
      summary: 'Takwin.run() · the KCCL canonical pipeline',
      body: [
        { type: 'text', content: 'Takwin is the substrates canonical orchestrator. One Takwin.run() call IS one cognitive cycle, embodied as 7 steps inside the Kimera Core Cognitive Loop (KCCL):' },
        { type: 'kv', items: [
          ['step 0', 'Screen — GWF filters adversarial inputs'],
          ['step 2', 'Encode — concepts extracted, projected to S⁴ ⊂ ℝ⁵, each assigned a prime via Arachne'],
          ['step 3-4', 'Traverse — PrimeTopologyWalker traverses the manifold (M1 COMMIT, M2 HALT, M3 ROLLBACK, M4 LATERAL LEAP)'],
          ['step 5', 'Consolidate — trajectory finalized; prime_chain extracted'],
          ['step 6', 'Vault — if contradiction-gate fires, a SCAR is formed and stored'],
          ['step 7', 'Render — physics-to-language via deterministic CognitiveInterpreter'],
        ]},
        { type: 'text', content: 'Primes are load-bearing, not decorative: GeoidNode.prime comes from a real sieve through Arachne; prime_chain feeds PrimeWaveQuantumEngine which computes amplitudes via ω_p = exp(2πi/p) roots of unity.' },
      ],
    };
  }
  if (q.includes('memory-as-deformation') || q.includes('manifold') || q.includes('session 013')) {
    return {
      agent: 'brief',
      summary: 'Memory-as-deformation · measured empirically Session 013',
      body: [
        { type: 'text', content: 'The principle that experience carves the manifold and recall follows the reshaped curvature has moved from philosophy to an observed cycle-level phenomenon. A 500-cycle observation (Session 013, 2026-04-23) captured 109 re-exposures of 15 genesis seeds.' },
        { type: 'kv', items: [
          ['recognition preserved',   'concept-set identity holds in >= 94% of re-exposures'],
          ['prime-chain set identity','~100% preservation'],
          ['cognition drifts',        'trajectory ORDER drifts after 2-3 exposures'],
          ['formal content is rigid', 'Φ = 0.250 stable across 6 exposures, stdev 0.000'],
          ['narrative drifts',        'Alexandria seed Φ rises +0.030 across 11 exposures; liar paradox Φ falls −0.032 across 10 (habituation)'],
        ]},
        { type: 'text', content: 'This is the first direct empirical measurement of memory-as-deformation in Kimera-SWM. The substrate thinks the same content differently after sustained novel experience.' },
      ],
    };
  }
  if (q.includes('path a') || q.includes('path-a') || q.includes('path b') || q.includes('path-b') || q.includes('seam') || q.includes('unfused')) {
    return {
      agent: 'brief',
      summary: 'Path-A / Path-B · the deliberately unfused seam',
      body: [
        { type: 'text', content: 'Kimera has two parallel thermodynamic stacks. They answer different questions, so they are not interchangeable, so they are deliberately unfused. The seam is an architectural commitment.' },
        { type: 'kv', items: [
          ['Path A (analytical)', 'zeta-prime partition, TFD purification, Bekenstein area, Landau phases'],
          ['Path A oracle',       'mpmath.zeta + analytical identities'],
          ['Path B (EBM/learning)','Modern-Hopfield, BCPNN, sparse-Hopfield, scar-Hopfield'],
          ['Path B oracle',       'THRML (candidate; bridge present)'],
        ]},
        { type: 'text', content: 'Path A: given this energy landscape, what is the equilibrium? Path B: given these observations, what energy landscape explains them? Both are thermodynamics, neither subsumes the other. The unfused seam is documented in SAFETY_CLAIMS.md.' },
      ],
    };
  }
  if (q.includes('roadmap') || q.includes('phase') || q.includes('campaign')) {
    return {
      agent: 'query',
      summary: 'Kimera autonomous roadmap (2026-05-18) · 7 phases',
      body: [
        { type: 'text', content: 'The Kimera autonomous campaign is in flight. Substrate is BGE-M3 @ 6e4477ebb; Family EE in EMPIRICAL_VALIDATION.md is open for this campaign.' },
        { type: 'list', label: 'Phase status', items: [
          { name: 'Phase 0 · Pre-flight bootstrap',           desc: 'VALIDATED — 6/6 checks green' },
          { name: 'Phase 1 · Re-baseline on BGE-M3',          desc: 'RUNNING — 1a validated (+0.142), 1b inconclusive (5/8 within 1σ), 1c pending' },
          { name: 'Phase 2 · Multi-modal activation',         desc: 'pending — image + audio channels' },
          { name: 'Phase 3 · Cross-cycle pair extraction',    desc: 'pending' },
          { name: 'Phase 4 · BGE-native concept expansion',   desc: 'pending' },
          { name: 'Phase 5 · GWF Family W (4 W-probes)',      desc: 'pending — owner-pinned' },
          { name: 'Phase 6 · Small mysteries + Pattern-P',    desc: 'pending' },
          { name: 'Phase 7 · Path A re-open feasibility',     desc: 'pending' },
        ]},
        { type: 'cta', label: 'Open the Roadmap surface', kind: 'open-roadmap' },
      ],
    };
  }

  // Default — route via 'query' agent
  return {
    agent: 'query',
    summary: 'Natural-language query · routed to query agent',
    body: [
      { type: 'text', content: `I parsed your question as a general query over the proof-bundle tree (${OPHAMIN.totals.bundles} bundles across ${OPHAMIN.totals.scenarios} scenarios in ${OPHAMIN.totals.tiers} tiers).` },
      { type: 'text', content: 'Try one of the starter chips above, or ask about a specific scenario name (e.g. "What does prime-factorization test?"), a specific verdict ("Why was X refuted?"), or a claim ("Is X falsifiable?").' },
      { type: 'kv', items: [
        ['scenarios catalogued',     OPHAMIN.totals.scenarios],
        ['proof bundles indexed',    OPHAMIN.totals.bundles],
        ['validated / refuted / inconclusive', `${OPHAMIN.totals.verdicts.validated} / ${OPHAMIN.totals.verdicts.refuted} / ${OPHAMIN.totals.verdicts.inconclusive}`],
        ['substrate', `${OPHAMIN.substrate} @ ${OPHAMIN.substrate_commit}`],
      ]},
    ],
  };
}

function ChatScreen({ onNavToProofs, onNavToDrift, onNavToAgents }) {
  const [messages, setMessages] = useChState([
    { role: 'system', content: "Ask me about Ophamin or Kimera-SWM. I route your question to one of seven specialized agents (prereg · scenario-gen · adapt · brief · triage · confounds · query), each of which signs and audits its response." },
  ]);
  const [input, setInput] = useChState('');
  const [thinking, setThinking] = useChState(false);
  const scrollRef = useChRef(null);

  useChEffect(() => {
    if (scrollRef.current) scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
  }, [messages, thinking]);

  const send = (text) => {
    const q = text.trim();
    if (!q) return;
    setMessages(m => [...m, { role: 'user', content: q }]);
    setInput('');
    setThinking(true);
    setTimeout(() => {
      const reply = agentReply(q, null);
      setMessages(m => [...m, { role: 'agent', ...reply }]);
      setThinking(false);
    }, 900 + Math.random() * 700);
  };

  const handleCta = (cta) => {
    if (cta.kind === 'open-proof') {
      const b = OPHAMIN.bundles.find(b => b.scenario === cta.target.scenario);
      if (b) onNavToProofs(null, b);
    } else if (cta.kind === 'open-drift') {
      onNavToDrift();
    } else if (cta.kind === 'open-roadmap') {
      window.location.hash = '#roadmap';
      window.parent && window.parent.postMessage({ navTo: 'roadmap' }, '*');
    } else if (cta.kind === 'open-agent') {
      onNavToAgents();
    }
  };

  return (
    <div className="content-inner page" style={{ height: 'calc(100vh - var(--topbar-h))', display: 'flex', flexDirection: 'column', maxWidth: 'none', padding: 0 }}>
      <div className="page-header" style={{ padding: '20px 28px 14px', margin: 0 }}>
        <div>
          <h1 className="page-title">Chat</h1>
          <div className="page-subtitle mono">Ask anything about Ophamin or Kimera-SWM. I route to the right agent. Every reply is signed.</div>
        </div>
        <div className="page-actions">
          <span className="live-pill advisory">
            <span className="dot"></span>
            advisory only
          </span>
          <span style={{ fontSize: 11, color: 'var(--text-muted)' }}>qwen2.5-coder:14b · local · 47ms p50</span>
        </div>
      </div>

      <div className="chat-layout" style={{ flex: 1, minHeight: 0 }}>
        <aside className="chat-history">
          <div className="micro" style={{ padding: '12px 14px 6px' }}>RECENT</div>
          <div className="chat-history-item active">
            <Icon name="activity" size={11}/>
            <span>New conversation</span>
          </div>
          <div className="chat-history-item">
            <Icon name="rocket" size={11}/>
            <span>Triage refuted topology siege</span>
            <span className="chat-history-time mono">12m</span>
          </div>
          <div className="chat-history-item">
            <Icon name="eye" size={11}/>
            <span>Confounds: immune-siege validation</span>
            <span className="chat-history-time mono">1h</span>
          </div>
          <div className="chat-history-item">
            <Icon name="search" size={11}/>
            <span>Drift query · last 7 days</span>
            <span className="chat-history-time mono">3h</span>
          </div>

          <div className="micro" style={{ padding: '16px 14px 6px' }}>AGENTS</div>
          {Object.entries(AGENT_META).map(([id, meta]) => (
            <div key={id} className="chat-agent-row">
              <span className={'agent-tier-dot agent-tier-' + meta.tier}/>
              <span style={{ fontSize: 11.5 }}>{meta.label}</span>
              <span className="mono" style={{ marginLeft: 'auto', fontSize: 10, color: 'var(--text-muted)' }}>{id}</span>
            </div>
          ))}
        </aside>

        <main className="chat-main">
          <div className="chat-thread" ref={scrollRef}>
            {messages.map((m, i) => <Message key={i} m={m} onCta={handleCta}/>)}
            {thinking && (
              <div className="msg msg-agent">
                <div className="msg-avatar"><SixWheelsLoader size={22}/></div>
                <div className="msg-body">
                  <div className="msg-meta">
                    <span className="mono" style={{ color: 'var(--text-muted)' }}>routing query…</span>
                  </div>
                  <div className="msg-content"><span className="muted">parsing intent · selecting agent · loading proof context</span></div>
                </div>
              </div>
            )}
          </div>

          <div className="chat-input-area">
            {messages.length <= 1 && (
              <div className="chat-chips">
                <div className="micro" style={{ marginBottom: 6 }}>START WITH</div>
                <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6 }}>
                  {STARTER_CHIPS.map(c => (
                    <button key={c.id} className="chat-chip" onClick={() => send(c.label)}>
                      <span className={'agent-tier-dot agent-tier-' + AGENT_META[c.agent].tier}/>
                      {c.label}
                    </button>
                  ))}
                </div>
              </div>
            )}

            <form className="chat-input-form" onSubmit={e => { e.preventDefault(); send(input); }}>
              <input className="chat-input" placeholder="Ask about Ophamin · scenarios · proofs · Kimera-SWM substrate…"
                value={input} onChange={e => setInput(e.target.value)}/>
              <button className="btn primary" type="submit" disabled={!input.trim() || thinking}>
                <Icon name="play" size={13}/> Send
              </button>
            </form>

            <div className="chat-foot">
              <span><Icon name="eye" size={11}/> LLMs never override verdict.decide() · never run inside the substrate measurement path</span>
              <span style={{ marginLeft: 'auto' }} className="mono">via OPHAMIN_LLM_BASE_URL · local model</span>
            </div>
          </div>
        </main>
      </div>
    </div>
  );
}

function Message({ m, onCta }) {
  if (m.role === 'system') {
    return (
      <div className="msg msg-system">
        <Icon name="eye" size={14}/>
        <div>{m.content}</div>
      </div>
    );
  }
  if (m.role === 'user') {
    return (
      <div className="msg msg-user">
        <div className="msg-body">
          <div className="msg-content">{m.content}</div>
        </div>
      </div>
    );
  }
  const meta = AGENT_META[m.agent] || { label: m.agent, tier: 'reasoning', icon: 'eye' };
  return (
    <div className="msg msg-agent">
      <div className="msg-avatar">
        <Icon name={meta.icon} size={14}/>
      </div>
      <div className="msg-body">
        <div className="msg-meta">
          <span className={'agent-tier-dot agent-tier-' + meta.tier}/>
          <span style={{ fontWeight: 600, color: 'var(--text-primary)' }}>{meta.label}</span>
          <span className="mono faint" style={{ marginLeft: 4 }}>· ophamin agent {m.agent}</span>
          <span style={{ marginLeft: 'auto', display: 'flex', alignItems: 'center', gap: 4, color: 'var(--validated)', fontSize: 10 }}>
            <Icon name="check" size={10}/> signed · 04c1b2be…
          </span>
        </div>
        {m.summary && <div className="msg-summary">{m.summary}</div>}
        <div className="msg-content">
          {m.body.map((block, i) => <MessageBlock key={i} block={block} onCta={onCta}/>)}
        </div>
      </div>
    </div>
  );
}

function MessageBlock({ block, onCta }) {
  if (block.type === 'text')   return <p style={{ margin: '8px 0', lineHeight: 1.6, color: 'var(--text-secondary)', fontSize: 13 }}>{block.content}</p>;
  if (block.type === 'badge')  return <span style={{ display: 'inline-flex', alignItems: 'center', gap: 6, padding: '3px 10px', background: 'var(--validated-bg)', border: '1px solid var(--validated-line)', borderRadius: 'var(--r-full)', color: block.color, fontSize: 11, fontWeight: 600, marginTop: 6 }}>● {block.label}</span>;
  if (block.type === 'kv') {
    return (
      <div style={{ background: 'var(--bg-base)', border: '1px solid var(--border)', borderRadius: 'var(--r-sm)', padding: 12, marginTop: 10, display: 'grid', gridTemplateColumns: 'minmax(120px, max-content) 1fr', gap: '4px 14px', fontSize: 12 }}>
        {block.items.map(([k, v], i) => (
          <React.Fragment key={i}>
            <span className="mono" style={{ color: 'var(--text-muted)', fontSize: 11 }}>{k}</span>
            <span style={{ color: 'var(--text-primary)' }}>{v}</span>
          </React.Fragment>
        ))}
      </div>
    );
  }
  if (block.type === 'list') {
    return (
      <div style={{ marginTop: 10 }}>
        {block.label && <div className="micro" style={{ marginBottom: 6 }}>{block.label}</div>}
        <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
          {block.items.map((item, i) => (
            <div key={i} style={{ background: 'var(--bg-surface)', border: '1px solid var(--border)', borderRadius: 'var(--r-sm)', padding: '8px 10px', display: 'flex', gap: 10 }}>
              <span style={{ width: 18, height: 18, borderRadius: '50%', background: 'var(--bg-base)', border: '1px solid var(--border-strong)', color: 'var(--text-muted)', fontFamily: 'JetBrains Mono, monospace', fontSize: 11, fontWeight: 600, display: 'grid', placeItems: 'center', flexShrink: 0 }}>{i + 1}</span>
              <div style={{ flex: 1, minWidth: 0 }}>
                <div className="mono" style={{ fontSize: 12, color: 'var(--accent)', fontWeight: 500 }}>{item.name}</div>
                <div style={{ fontSize: 12, color: 'var(--text-secondary)', lineHeight: 1.5, marginTop: 2 }}>{item.desc}</div>
              </div>
            </div>
          ))}
        </div>
      </div>
    );
  }
  if (block.type === 'cta') {
    return (
      <button className="btn primary" style={{ marginTop: 10, fontSize: 12 }} onClick={() => onCta(block)}>
        <Icon name="external" size={12}/> {block.label}
      </button>
    );
  }
  return null;
}

window.ChatScreen = ChatScreen;
