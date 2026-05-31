/** @jsxRuntime classic */ /** @jsx React.createElement */
/* global React, Icon, SixWheelsRing, OPHAMIN */
// Intro — full-screen welcome / orientation overlay. Auto-shows on first
// visit (gated by localStorage); reopenable from the ? help modal. 5 panels
// with prev/next + skip. Leads with WHAT KIMERA IS, then how Ophamin proves it.

const { useState: useIntroState, useEffect: useIntroEffect } = React;

const PANELS = [
  {
    title: 'Kimera remembers history, not inventory',
    kicker: "Today's memory systems store what they were given. Kimera stores how things unfolded.",
    body: 'A filing cabinet — search, RAG — hands back the documents that look similar, blind to the order they arrived: two histories made of the same events in a different order look identical to it. Kimera is a landscape you walk. Every experience wears a permanent groove; the order of walking shapes the terrain; the terrain is the memory. Where order, permanence, and the path of experience carry meaning, the filing cabinet is blind and Kimera is not.',
    icon: 'activity',
  },
  {
    title: 'Ophamin makes it legible',
    kicker: 'An observatory wrapped around Kimera — proof, not promises.',
    body: "Kimera is a new kind of intelligence, and the words for it don't quite exist yet — so Ophamin shows what it actually does. Six wheels — seeing, measuring, comparing, instrumenting, auditing, reporting — watch the running substrate and emit signed, content-addressed, falsifiable evidence. The point is that you don't have to take anyone's word for what Kimera is.",
    wheels: true,
  },
  {
    title: 'Claims are pre-registered',
    kicker: 'Every measurement records its threshold before the substrate runs.',
    body: 'A claim has a metric, a comparator, a threshold, units, H₀ and H₁ — with its config and data hashes captured before measurement begins. The bar a verdict is judged against is byte-identical to what was committed in advance. No moving the goalposts after the fact.',
    icon: 'eye',
  },
  {
    title: 'Verdicts are signed — re-verify them yourself',
    kicker: 'Three outcomes: VALIDATED · REFUTED · INCONCLUSIVE. No trust required.',
    body: 'A REFUTED verdict is the framework working — the substrate did not meet a threshold committed before measurement, and that is kept, not hidden. Every bundle is HMAC-signed and content-addressed (its hash is its proof_id), and verifiers in Rust, JS, and Python all enforce the same canonical bytes. Re-run any line; you do not have to believe us.',
    icon: 'check',
    verdicts: true,
  },
  {
    title: 'Where to start',
    kicker: 'A few entry points, depending on what you want to do.',
    body: '',
    icon: 'rocket',
    entries: [
      { id: 'proofs',   label: 'Proofs',     desc: 'The evidence. Filter, drill into any proof, read what it means in plain words, cross-verify in four languages.' },
      { id: 'overview', label: 'Overview',   desc: 'Where Kimera stands today — six-wheels health, verdict mix, recent runs.' },
      { id: 'roadmap',  label: 'Roadmap',    desc: 'The Kimera campaign in flight — every measurement Ophamin-signed.' },
      { id: 'chat',     label: 'Chat',       desc: 'Ask anything — routed to one of seven specialized agents.' },
    ],
  },
];

function IntroOverlay() {
  // Mount-state — read localStorage once at first render
  const [shown, setShown] = useIntroState(() => {
    try { return localStorage.getItem('ophamin_intro_seen') !== 'true'; }
    catch (e) { return true; }
  });
  const [idx, setIdx] = useIntroState(0);

  // Allow re-opening via global event
  useIntroEffect(() => {
    const open = () => { setIdx(0); setShown(true); };
    window.addEventListener('ophamin:intro', open);
    return () => window.removeEventListener('ophamin:intro', open);
  }, []);

  const close = () => {
    try { localStorage.setItem('ophamin_intro_seen', 'true'); } catch (e) {}
    setShown(false);
  };

  const goTo = (screen) => {
    close();
    window.dispatchEvent(new CustomEvent('ophamin:nav', { detail: screen }));
  };

  if (!shown) return null;
  const p = PANELS[idx];
  const last = idx === PANELS.length - 1;

  return (
    <div className="intro-backdrop">
      <div className="intro-modal">
        <div className="intro-progress">
          {PANELS.map((_, i) => (
            <span key={i} className={'intro-dot' + (i === idx ? ' active' : i < idx ? ' done' : '')}
              onClick={() => setIdx(i)}/>
          ))}
          <span style={{ flex: 1 }}/>
          <button className="btn ghost" style={{ fontSize: 11 }} onClick={close}>Skip intro</button>
        </div>

        <div className="intro-body">
          <div className="intro-kicker">{p.kicker}</div>
          <h1 className="intro-title">{p.title}</h1>

          {p.wheels && (
            <div style={{ display: 'grid', placeItems: 'center', margin: '20px 0' }}>
              <SixWheelsRing size={220} wheels={OPHAMIN.wheels}/>
            </div>
          )}

          {p.body && <p className="intro-text">{p.body}</p>}

          {p.verdicts && (
            <div className="intro-verdicts">
              <div className="intro-verdict-tile validated">
                <span className="dot"></span>
                <div className="intro-verdict-label">VALIDATED</div>
                <div className="intro-verdict-desc">Substrate met the threshold.</div>
              </div>
              <div className="intro-verdict-tile refuted">
                <span className="dot"></span>
                <div className="intro-verdict-label">REFUTED</div>
                <div className="intro-verdict-desc">Framework's commitment held; substrate did not meet it. This is the framework working.</div>
              </div>
              <div className="intro-verdict-tile inconclusive">
                <span className="dot"></span>
                <div className="intro-verdict-label">INCONCLUSIVE</div>
                <div className="intro-verdict-desc">Evidence did not resolve the claim within tolerance.</div>
              </div>
            </div>
          )}

          {p.entries && (
            <div className="intro-entries">
              {p.entries.map(e => (
                <button key={e.id} className="intro-entry" onClick={() => goTo(e.id)}>
                  <span className="intro-entry-arrow">→</span>
                  <div style={{ flex: 1, textAlign: 'left' }}>
                    <div style={{ fontSize: 14, fontWeight: 600, color: 'var(--text-primary)' }}>{e.label}</div>
                    <div style={{ fontSize: 12, color: 'var(--text-muted)', marginTop: 2 }}>{e.desc}</div>
                  </div>
                </button>
              ))}
            </div>
          )}
        </div>

        <div className="intro-foot">
          <button className="btn ghost" disabled={idx === 0} onClick={() => setIdx(i => Math.max(0, i - 1))}>
            <Icon name="chevronL" size={12}/> Back
          </button>
          <span style={{ flex: 1 }}/>
          <span style={{ fontSize: 11, color: 'var(--text-muted)' }}>{idx + 1} / {PANELS.length}</span>
          <span style={{ flex: 1 }}/>
          {last ? (
            <button className="btn primary" onClick={close}>
              Enter console <Icon name="chevronR" size={12}/>
            </button>
          ) : (
            <button className="btn primary" onClick={() => setIdx(i => Math.min(PANELS.length - 1, i + 1))}>
              Next <Icon name="chevronR" size={12}/>
            </button>
          )}
        </div>
      </div>
    </div>
  );
}

window.IntroOverlay = IntroOverlay;
window.openIntro = () => window.dispatchEvent(new CustomEvent('ophamin:intro'));
