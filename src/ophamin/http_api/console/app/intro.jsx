/** @jsxRuntime classic */ /** @jsx React.createElement */
/* global React, Icon, SixWheelsRing, OPHAMIN */
// Intro — full-screen welcome / orientation overlay. Auto-shows on first
// visit (gated by localStorage); reopenable from the ? help modal or
// the design-preview pill. 5 panels with prev/next + skip.

const { useState: useIntroState, useEffect: useIntroEffect } = React;

const PANELS = [
  {
    title: 'Ophamin Console',
    kicker: 'An empirical observatory wrapped around a substrate under test.',
    body: 'Built for Kimera-SWM. Independent of it. Six wheels — seeing, measuring, comparing, instrumenting, auditing, reporting — observe a running substrate and emit signed, content-addressed, falsifiable proof bundles. This console is the operator surface.',
    wheels: true,
  },
  {
    title: 'Claims are pre-registered',
    kicker: 'Every measurement records its threshold before the substrate runs.',
    body: 'A claim has a metric, a comparator, a threshold value, units, H₀ and H₁. Its config_hash and data_hash are captured before measurement begins. The threshold a verdict is judged against is byte-identical to what was committed in advance.',
    icon: 'eye',
  },
  {
    title: 'Verdicts are signed',
    kicker: 'Three outcomes: VALIDATED · REFUTED · INCONCLUSIVE.',
    body: 'A REFUTED verdict is the framework working — the substrate did not meet a threshold committed before measurement. The bundle is HMAC-SHA256 signed; the content hash is its proof_id. Cross-language verifiers in Rust, JS, and Python all enforce the same canonical bytes.',
    icon: 'check',
    verdicts: true,
  },
  {
    title: 'Where to start',
    kicker: 'Five entry points depending on what you want to do.',
    body: '',
    icon: 'rocket',
    entries: [
      { id: 'chat',     label: 'Chat',       desc: 'Ask anything — routed to one of seven specialized agents. Best first stop.' },
      { id: 'overview', label: 'Overview',   desc: 'Where the substrate stands today. Six-wheels health, verdict mix, recent runs.' },
      { id: 'roadmap',  label: 'Roadmap',    desc: 'The 7-phase Kimera autonomous campaign in flight. Every measurement Ophamin-signed.' },
      { id: 'proofs',   label: 'Proofs',     desc: 'Bundle explorer. Filter, drill, cross-verify in 4 languages, inspect provenance.' },
      { id: 'control',  label: 'Control',    desc: 'Live cockpit · parameters · containers · databases · logs. Two perspectives.' },
    ],
  },
  {
    title: 'This is a design preview',
    kicker: 'Mock data wired through real shapes.',
    body: 'The console renders signed proof bundles in their actual 9-section structure, the real OFAMIN pillar evidence schema, and the canonical wire format. The live numbers (Φ, GWF rate, HTTP req/s) tick on a heartbeat but are not connected to a running instrument. The amber "design preview" pill in the topbar will be there until that changes.',
    icon: 'activity',
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
