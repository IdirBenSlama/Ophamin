/** @jsxRuntime classic */ /** @jsx React.createElement */
/* global React */
// KeyboardNav — wires the g+<key> chord navigation documented in
// ShortcutsModal.  Listens globally; ignores input/textarea targets.

const { useEffect: useKbEffect } = React;

const NAV_MAP = {
  o: 'overview',  r: 'roadmap',     c: 'chat',
  p: 'proofs',    s: 'scenarios',   u: 'run',
  t: 'telemetry', l: 'lab',         i: 'interop',
  m: 'control',   a: 'agents',      d: 'discovery',
  e: 'inspector', x: 'audit',
};

function KeyboardNav() {
  useKbEffect(() => {
    let gPending = false;
    let gTimer = null;
    function reset() { gPending = false; if (gTimer) { clearTimeout(gTimer); gTimer = null; } }
    const handler = (e) => {
      const tag = (e.target.tagName || '').toLowerCase();
      if (tag === 'input' || tag === 'textarea' || e.target.isContentEditable) { reset(); return; }
      if (e.metaKey || e.ctrlKey || e.altKey) return;
      if (e.key === 'g' && !gPending) {
        gPending = true;
        gTimer = setTimeout(reset, 1500);
        return;
      }
      if (gPending) {
        const dest = NAV_MAP[e.key.toLowerCase()];
        if (dest) {
          window.dispatchEvent(new CustomEvent('ophamin:nav', { detail: dest }));
          // Brief on-screen indicator
          showChord('g ' + e.key);
        }
        reset();
      }
    };
    window.addEventListener('keydown', handler);
    return () => window.removeEventListener('keydown', handler);
  }, []);
  return null;
}

function showChord(label) {
  let el = document.getElementById('__chord_hint');
  if (!el) {
    el = document.createElement('div');
    el.id = '__chord_hint';
    el.className = 'chord-hint';
    document.body.appendChild(el);
  }
  el.textContent = label;
  el.style.opacity = '1';
  clearTimeout(el._t);
  el._t = setTimeout(() => { el.style.opacity = '0'; }, 800);
}

window.KeyboardNav = KeyboardNav;
