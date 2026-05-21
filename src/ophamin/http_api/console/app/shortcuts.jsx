/** @jsxRuntime classic */ /** @jsx React.createElement */
/* global React, Icon */
// KeyboardShortcuts — triggered by '?' globally. Documents the navigation
// shortcuts the rest of the console implicitly supports.

const { useState: useKsState, useEffect: useKsEffect } = React;

const SHORTCUTS = [
  { group: 'Open', items: [
    ['⌘ K',            'Open command palette'],
    ['?',              'This help modal'],
    ['Esc',            'Close any modal or drawer'],
  ]},
  { group: 'Navigate', items: [
    ['G then O',       'Overview'],
    ['G then R',       'Roadmap'],
    ['G then C',       'Chat'],
    ['G then P',       'Proofs'],
    ['G then S',       'Scenarios'],
    ['G then U',       'Run'],
    ['G then T',       'Telemetry'],
    ['G then L',       'Lab'],
    ['G then I',       'Interop'],
    ['G then M',       'Control Room'],
    ['G then A',       'Agents'],
    ['G then D',       'Discovery'],
    ['G then E',       'Inspector'],
    ['G then X',       'Audit'],
  ]},
  { group: 'In Proofs', items: [
    ['↑ / ↓',          'Move bundle selection'],
    ['Enter',          'Open selected bundle'],
    ['F',              'Filter by verdict'],
    ['/',              'Focus search'],
  ]},
  { group: 'In Chat', items: [
    ['Enter',          'Send'],
    ['Shift+Enter',    'New line'],
    ['↑',              'Edit last message'],
  ]},
];

function ShortcutsModal() {
  const [open, setOpen] = useKsState(false);
  useKsEffect(() => {
    const handler = (e) => {
      // ignore when typing in an input/textarea
      const tag = (e.target.tagName || '').toLowerCase();
      if (tag === 'input' || tag === 'textarea' || e.target.isContentEditable) return;
      if (e.key === '?' && !e.metaKey && !e.ctrlKey) {
        e.preventDefault();
        setOpen(o => !o);
      } else if (e.key === 'Escape' && open) {
        setOpen(false);
      }
    };
    window.addEventListener('keydown', handler);
    return () => window.removeEventListener('keydown', handler);
  }, [open]);

  if (!open) return null;
  return (
    <div className="ks-backdrop" onClick={() => setOpen(false)}>
      <div className="ks-modal" onClick={e => e.stopPropagation()}>
        <div className="ks-head">
          <div>
            <div style={{ fontSize: 16, fontWeight: 600 }}>Keyboard shortcuts</div>
            <div style={{ fontSize: 11, color: 'var(--text-muted)', marginTop: 2 }}>Press <span className="cmdk-kbd">?</span> anytime to open this.</div>
          </div>
          <button className="btn ghost icon" onClick={() => setOpen(false)}><Icon name="x" size={14}/></button>
        </div>
        <div className="ks-body">
          {SHORTCUTS.map(g => (
            <div key={g.group} className="ks-group">
              <div className="ks-group-label">{g.group}</div>
              {g.items.map(([k, v], i) => (
                <div key={i} className="ks-row">
                  <span className="ks-keys">
                    {k.split(' ').map((p, j) => (
                      <React.Fragment key={j}>
                        {j > 0 && <span className="ks-sep">{p === 'then' ? ' then ' : ' '}</span>}
                        {p !== 'then' && <span className="cmdk-kbd">{p}</span>}
                      </React.Fragment>
                    ))}
                  </span>
                  <span className="ks-label">{v}</span>
                </div>
              ))}
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

window.ShortcutsModal = ShortcutsModal;
