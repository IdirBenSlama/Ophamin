/** @jsxRuntime classic */ /** @jsx React.createElement */
/* global React, Icon */
// Chat — conversational front door to Ophamin + Kimera-SWM via the 7 agents.
//
// NO FABRICATION (2026-05-31): conversational chat is MEANT to run on a local
// LLM (qwen2.5-coder via OPHAMIN_LLM_BASE_URL) — allowed in Ophamin, since the
// LLM only advises and never enters Kimera's measurement path — but it is NOT
// wired into the console yet. This screen used to FAKE it: scripted canned
// replies with fabricated specifics (39.6%, "3.2% VALIDATED", CIs), a fake
// live-model badge ("qwen2.5-coder:14b · 47ms p50"), per-reply "signed · 04c1…"
// stamps, and a fake conversation history. All removed. Until the LLM is wired,
// the chat answers nothing — it points to the real surface that holds the
// answer, and never invents one.

const { useState: useChState, useEffect: useChEffect, useRef: useChRef } = React;

const STARTER_CHIPS = [
  { id: 'why-refuted',  label: 'Why was logic-topology-siege refuted?' },
  { id: 'gwf-fpr',      label: 'How is the GWF false-positive rate computed?' },
  { id: 'check-claim',  label: 'Is "p95 latency ≤ 50ms" a falsifiable claim?' },
  { id: 'drift-7d',     label: 'Which scenarios flipped verdict recently?' },
  { id: 'roadmap-now',  label: 'What phase of the Kimera roadmap is in flight?' },
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

// Honest reply: the LLM chat isn't wired, so answer nothing — route to the real
// surface. NO canned/fabricated answers.
function notWiredReply() {
  return {
    agent: 'query',
    summary: 'Conversational chat isn’t wired into the console yet',
    body: [
      { type: 'text', content: "I won't fabricate an answer. Ophamin's chat is meant to run on a local LLM (qwen2.5-coder via OPHAMIN_LLM_BASE_URL) — that's allowed here, because the LLM only ever advises and never enters Kimera's measurement path — but it isn't connected to this console yet." },
      { type: 'text', content: "The seven agents are real and run via the CLI (ophamin agent <id>). Whatever you asked, the real answer lives on one of these surfaces:" },
      { type: 'cta', label: 'Proofs — signed verdicts + plain-language significance', kind: 'open-proofs' },
      { type: 'cta', label: 'Agents — what each of the seven does', kind: 'open-agent' },
      { type: 'cta', label: 'Roadmap — the campaign plan', kind: 'open-roadmap' },
    ],
  };
}

function ChatScreen({ onNavToProofs, onNavToDrift, onNavToAgents }) {
  const [messages, setMessages] = useChState([
    { role: 'system', content: "Ask about Ophamin or Kimera-SWM. The seven agents (prereg · scenario-gen · adapt · brief · triage · confounds · query) run via the CLI; conversational chat through the console (a local LLM) isn't wired yet — so rather than invent an answer, I'll point you to the surface that actually holds it." },
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
    // brief, honest pause — no fake "selecting agent / loading proof context"
    setTimeout(() => {
      setMessages(m => [...m, { role: 'agent', ...notWiredReply() }]);
      setThinking(false);
    }, 250);
  };

  const handleCta = (cta) => {
    if (cta.kind === 'open-proofs')      onNavToProofs && onNavToProofs(null);
    else if (cta.kind === 'open-drift')  onNavToDrift && onNavToDrift();
    else if (cta.kind === 'open-roadmap') window.dispatchEvent(new CustomEvent('ophamin:nav', { detail: 'roadmap' }));
    else if (cta.kind === 'open-agent')  onNavToAgents && onNavToAgents();
  };

  return (
    <div className="content-inner page" style={{ height: 'calc(100vh - var(--topbar-h))', display: 'flex', flexDirection: 'column', maxWidth: 'none', padding: 0 }}>
      <div className="page-header" style={{ padding: '20px 28px 14px', margin: 0 }}>
        <div>
          <h1 className="page-title">Chat</h1>
          <div className="page-subtitle mono">Ask about Ophamin or Kimera-SWM. Conversational LLM chat is the intended backend — not wired into the console yet, so nothing is answered here, only routed.</div>
        </div>
        <div className="page-actions">
          <span className="live-pill muted"><span className="dot"></span>LLM chat · not wired</span>
        </div>
      </div>

      <div className="chat-layout" style={{ flex: 1, minHeight: 0 }}>
        <aside className="chat-history">
          <div className="micro" style={{ padding: '12px 14px 6px' }}>RECENT</div>
          <div className="chat-history-item active">
            <Icon name="activity" size={11}/>
            <span>New conversation</span>
          </div>

          <div className="micro" style={{ padding: '16px 14px 6px' }}>AGENTS (run via CLI)</div>
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
                <div className="msg-avatar"><Icon name="search" size={14}/></div>
                <div className="msg-body">
                  <div className="msg-meta">
                    <span className="mono" style={{ color: 'var(--text-muted)' }}>routing…</span>
                  </div>
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
              <span><Icon name="eye" size={11}/> An LLM here only advises — it never overrides verdict.decide() and never runs inside Kimera's measurement path.</span>
              <span style={{ marginLeft: 'auto' }} className="mono">local LLM via OPHAMIN_LLM_BASE_URL · not wired into the console yet</span>
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
  if (block.type === 'cta') {
    return (
      <button className="btn" style={{ marginTop: 8, marginRight: 6, fontSize: 12 }} onClick={() => onCta(block)}>
        <Icon name="external" size={12}/> {block.label}
      </button>
    );
  }
  return null;
}

window.ChatScreen = ChatScreen;
