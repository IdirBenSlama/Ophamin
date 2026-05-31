/** @jsxRuntime classic */ /** @jsx React.createElement */
/* global React, Icon */
// Chat — conversational front door to Ophamin + Kimera-SWM.
//
// WIRED to a real local LLM (2026-05-31): POST /chat → ophamin.agentic LLMClient
// → a local model (Ollama / LM Studio / MLX-LM via OPHAMIN_LLM_BASE_URL). An LLM
// is allowed HERE because Ophamin is the layer ABOUT Kimera: it only advises,
// never overrides verdict.decide(), and never runs inside Kimera's measurement
// path (the substrate itself contains no LLM). Replies are REAL model output
// with REAL model/latency/token metrics. When no local LLM is reachable the
// endpoint 503s and the chat shows an honest "couldn't reach the LLM" message
// that routes to the real surfaces — it never fabricates a reply or metrics.
// (This replaced a fully-scripted fake: canned answers + a fake live-model badge
// + fake signatures + fake history.)

const { useState: useChState, useEffect: useChEffect, useRef: useChRef } = React;

const STARTER_CHIPS = [
  { id: 'what-is',      label: 'What is Ophamin, and how does it relate to Kimera-SWM?' },
  { id: 'why-refuted',  label: 'What does a REFUTED verdict mean here?' },
  { id: 'gwf',          label: 'What is the GWF false-positive rate, in plain words?' },
  { id: 'falsifiable',  label: 'What makes a claim falsifiable?' },
  { id: 'proofs',       label: 'How do I re-verify a signed proof myself?' },
];

function errorReply(detail) {
  return {
    agent: 'query',
    summary: 'Couldn’t reach the local LLM',
    body: [
      { type: 'text', content: detail || "The local LLM isn't reachable right now — so I won't fabricate an answer." },
      { type: 'text', content: "Ophamin's chat runs on a local LLM (Ollama / LM Studio / MLX-LM via OPHAMIN_LLM_BASE_URL) — allowed here because the LLM only advises and never enters Kimera's measurement path. Start a local model, or go straight to the real surfaces:" },
      { type: 'cta', label: 'Proofs — signed verdicts + significance', kind: 'open-proofs' },
      { type: 'cta', label: 'Agents — what each of the seven does', kind: 'open-agent' },
      { type: 'cta', label: 'Roadmap — the campaign plan', kind: 'open-roadmap' },
    ],
  };
}

function ChatScreen({ onNavToProofs, onNavToDrift, onNavToAgents }) {
  const [messages, setMessages] = useChState([
    { role: 'system', content: "Ask about Ophamin or Kimera-SWM. Answers come from a local LLM that only advises — it never decides a verdict and never runs inside Kimera's substrate (which contains no LLM). If the local model isn't running, I'll say so and point you to the real surfaces rather than invent an answer." },
  ]);
  const [input, setInput] = useChState('');
  const [thinking, setThinking] = useChState(false);
  const scrollRef = useChRef(null);

  useChEffect(() => {
    if (scrollRef.current) scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
  }, [messages, thinking]);

  const send = async (text) => {
    const q = (text || '').trim();
    if (!q || thinking) return;
    const history = messages
      .filter(m => m.role === 'user' || (m.role === 'agent' && m.replyText))
      .map(m => ({ role: m.role === 'agent' ? 'assistant' : 'user', content: m.role === 'agent' ? m.replyText : m.content }))
      .slice(-8);
    setMessages(m => [...m, { role: 'user', content: q }]);
    setInput('');
    setThinking(true);
    try {
      const base = window.OPHAMIN_API_BASE || '';
      const r = await fetch(base + '/chat', {
        method: 'POST',
        headers: { 'content-type': 'application/json', accept: 'application/json' },
        body: JSON.stringify({ question: q, history }),
      });
      const data = await r.json().catch(() => ({}));
      if (!r.ok) {
        setMessages(m => [...m, { role: 'agent', ...errorReply(data.detail) }]);
      } else if (data.reply) {
        setMessages(m => [...m, { role: 'agent', replyText: data.reply, body: [{ type: 'text', content: data.reply }], meta: data }]);
      } else if (data.reasoning) {
        setMessages(m => [...m, { role: 'agent', summary: '(the model emitted only a reasoning stream — no final answer)', replyText: data.reasoning, body: [{ type: 'text', content: data.reasoning }], meta: data }]);
      } else {
        setMessages(m => [...m, { role: 'agent', ...errorReply('The model returned an empty answer.') }]);
      }
    } catch (e) {
      setMessages(m => [...m, { role: 'agent', ...errorReply('Network error reaching /chat: ' + (e && e.message)) }]);
    } finally {
      setThinking(false);
    }
  };

  const handleCta = (cta) => {
    if (cta.kind === 'open-proofs')       onNavToProofs && onNavToProofs(null);
    else if (cta.kind === 'open-drift')   onNavToDrift && onNavToDrift();
    else if (cta.kind === 'open-roadmap') window.dispatchEvent(new CustomEvent('ophamin:nav', { detail: 'roadmap' }));
    else if (cta.kind === 'open-agent')   onNavToAgents && onNavToAgents();
  };

  return (
    <div className="content-inner page" style={{ height: 'calc(100vh - var(--topbar-h))', display: 'flex', flexDirection: 'column', maxWidth: 'none', padding: 0 }}>
      <div className="page-header" style={{ padding: '20px 28px 14px', margin: 0 }}>
        <div>
          <h1 className="page-title">Chat</h1>
          <div className="page-subtitle mono">Ask about Ophamin or Kimera-SWM — answered by a local LLM (advisory only; never inside Kimera's substrate).</div>
        </div>
        <div className="page-actions">
          <span className="live-pill"><span className="dot"></span>local LLM · advisory</span>
        </div>
      </div>

      <div className="chat-layout" style={{ flex: 1, minHeight: 0 }}>
        <aside className="chat-history">
          <div className="micro" style={{ padding: '12px 14px 6px' }}>SESSION</div>
          <div className="chat-history-item active">
            <Icon name="activity" size={11}/>
            <span>New conversation</span>
          </div>
          <div className="micro" style={{ padding: '16px 14px 6px' }}>BOUNDARY</div>
          <div style={{ padding: '4px 14px', fontSize: 11, color: 'var(--text-muted)', lineHeight: 1.5 }}>
            The LLM advises about the substrate. It never decides a verdict and never runs inside Kimera. Kimera-SWM itself contains no LLM.
          </div>
        </aside>

        <main className="chat-main">
          <div className="chat-thread" ref={scrollRef}>
            {messages.map((m, i) => <Message key={i} m={m} onCta={handleCta}/>)}
            {thinking && (
              <div className="msg msg-agent">
                <div className="msg-avatar"><Icon name="activity" size={14}/></div>
                <div className="msg-body">
                  <div className="msg-meta">
                    <span className="mono" style={{ color: 'var(--text-muted)' }}>asking the local model…</span>
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
              <span><Icon name="eye" size={11}/> The LLM only advises — it never overrides verdict.decide() and never runs inside Kimera's measurement path.</span>
              <span style={{ marginLeft: 'auto' }} className="mono">local LLM via OPHAMIN_LLM_BASE_URL</span>
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
  // agent message: a real LLM reply (m.meta present) or an honest error/route (m.agent)
  const isLLM = !!m.meta;
  return (
    <div className="msg msg-agent">
      <div className="msg-avatar">
        <Icon name={isLLM ? 'activity' : 'eye'} size={14}/>
      </div>
      <div className="msg-body">
        <div className="msg-meta">
          <span className={'agent-tier-dot agent-tier-' + (isLLM ? 'fast' : 'reasoning')}/>
          <span style={{ fontWeight: 600, color: 'var(--text-primary)' }}>{isLLM ? 'Ophamin assistant' : 'Ophamin'}</span>
          {isLLM && <span className="mono faint" style={{ marginLeft: 4 }}>· local LLM (advisory)</span>}
        </div>
        {m.summary && <div className="msg-summary">{m.summary}</div>}
        <div className="msg-content">
          {m.body.map((block, i) => <MessageBlock key={i} block={block} onCta={onCta}/>)}
        </div>
        {isLLM && (
          <div className="mono faint" style={{ marginTop: 8, fontSize: 10, color: 'var(--text-muted)' }}>
            {m.meta.model} · {m.meta.runtime} · {(m.meta.latency_ms / 1000).toFixed(1)}s · {m.meta.completion_tokens} tokens
          </div>
        )}
      </div>
    </div>
  );
}

function MessageBlock({ block, onCta }) {
  if (block.type === 'text') {
    return <p style={{ margin: '8px 0', lineHeight: 1.6, color: 'var(--text-secondary)', fontSize: 13, whiteSpace: 'pre-wrap' }}>{block.content}</p>;
  }
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
