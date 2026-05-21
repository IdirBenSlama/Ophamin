/** @jsxRuntime classic */ /** @jsx React.createElement */
/* global React, OPHAMIN, Icon */
// Command palette — ⌘K / Ctrl+K to open. Fuzzy filter across screens,
// scenarios, and bundles. Arrow-key navigation. UniFi-style overlay.

const { useState: usePalState, useEffect: usePalEffect, useRef: usePalRef, useMemo: usePalMemo } = React;

function CommandPalette({ onAction }) {
  const [open, setOpen] = usePalState(false);
  const [query, setQuery] = usePalState('');
  const [active, setActive] = usePalState(0);
  const inputRef = usePalRef(null);

  usePalEffect(() => {
    const handler = (e) => {
      if ((e.metaKey || e.ctrlKey) && e.key === 'k') {
        e.preventDefault();
        setOpen(o => !o);
      } else if (e.key === 'Escape' && open) {
        setOpen(false);
      }
    };
    window.addEventListener('keydown', handler);
    return () => window.removeEventListener('keydown', handler);
  }, [open]);

  usePalEffect(() => {
    if (open) {
      setQuery('');
      setActive(0);
      setTimeout(() => inputRef.current?.focus(), 60);
    }
  }, [open]);

  const items = usePalMemo(() => {
    const screens = [
      { kind: 'screen', label: 'Overview',  desc: 'dashboard · stats · activity',  icon: 'overview',  action: { nav: 'overview' } },
      { kind: 'screen', label: 'Proofs',    desc: 'bundle explorer · 33 bundles',  icon: 'proofs',    action: { nav: 'proofs' } },
      { kind: 'screen', label: 'Scenarios', desc: 'catalog · 33 registered',       icon: 'scenarios', action: { nav: 'scenarios' } },
      { kind: 'screen', label: 'Run',       desc: 'fire a scenario',               icon: 'run',       action: { nav: 'run' } },
      { kind: 'screen', label: 'Telemetry', desc: 'prometheus + gauges',           icon: 'telemetry', action: { nav: 'telemetry' } },
      { kind: 'screen', label: 'Settings',  desc: 'theme · density · accent',      icon: 'settings',  action: { nav: 'settings' } },
    ];
    const actions = [
      { kind: 'action', label: 'Toggle theme',       desc: 'dark / light',                                icon: 'sun',     action: { kind: 'theme' } },
      { kind: 'action', label: 'Reindex bundles',    desc: 'POST /proofs/index',                          icon: 'refresh', action: { kind: 'reindex' } },
      { kind: 'action', label: 'Switch substrate',   desc: 'open substrate picker',                       icon: 'cpu',     action: { kind: 'substrate' } },
      { kind: 'action', label: 'Filter validated',   desc: 'Proofs · verdict = validated',                icon: 'filter',  action: { nav: 'proofs', filter: 'validated' } },
      { kind: 'action', label: 'Filter refuted',     desc: 'Proofs · verdict = refuted',                  icon: 'filter',  action: { nav: 'proofs', filter: 'refuted' } },
      { kind: 'action', label: 'Filter inconclusive',desc: 'Proofs · verdict = inconclusive',             icon: 'filter',  action: { nav: 'proofs', filter: 'inconclusive' } },
    ];
    const scenarios = OPHAMIN.scenarios.map(s => ({
      kind: 'scenario',
      label: s.name,
      desc: `${s.tier} · ${s.family}${s.claim_available ? '' : ' · needs args'}`,
      icon: 'scenarios',
      action: { nav: 'run', scenario: s },
    }));
    const bundles = OPHAMIN.bundles.slice(0, 12).map(b => ({
      kind: 'bundle',
      label: `${b.scenario} · ${b.short_hash}`,
      desc: `${b.verdict} · ${b.tier} · ${b.date}`,
      icon: 'proofs',
      verdict: b.verdict,
      action: { nav: 'proofs', bundle: b },
    }));
    return [...screens, ...actions, ...scenarios, ...bundles];
  }, []);

  const filtered = usePalMemo(() => {
    if (!query) return items;
    const q = query.toLowerCase();
    return items.filter(i =>
      i.label.toLowerCase().includes(q) ||
      i.desc.toLowerCase().includes(q) ||
      i.kind.toLowerCase().includes(q)
    );
  }, [items, query]);

  // Group filtered items
  const groups = usePalMemo(() => {
    const g = { screen: [], action: [], scenario: [], bundle: [] };
    filtered.forEach(i => g[i.kind].push(i));
    return g;
  }, [filtered]);

  // Flat list for keyboard nav
  const flat = usePalMemo(() => {
    return [...groups.screen, ...groups.action, ...groups.scenario, ...groups.bundle];
  }, [groups]);

  usePalEffect(() => { setActive(0); }, [query]);

  const handleKey = (e) => {
    if (e.key === 'ArrowDown') {
      e.preventDefault();
      setActive(a => Math.min(flat.length - 1, a + 1));
    } else if (e.key === 'ArrowUp') {
      e.preventDefault();
      setActive(a => Math.max(0, a - 1));
    } else if (e.key === 'Enter') {
      e.preventDefault();
      const item = flat[active];
      if (item) {
        onAction(item.action);
        setOpen(false);
      }
    }
  };

  if (!open) return null;

  return (
    <div className="cmdk-backdrop" onClick={() => setOpen(false)}>
      <div className="cmdk-modal" onClick={e => e.stopPropagation()}>
        <div className="cmdk-input-row">
          <Icon name="search" size={16}/>
          <input ref={inputRef} className="cmdk-input"
            placeholder="Search scenarios, bundles, screens, actions…"
            value={query} onChange={e => setQuery(e.target.value)}
            onKeyDown={handleKey}/>
          <span className="cmdk-kbd">ESC</span>
        </div>
        <div className="cmdk-results">
          {flat.length === 0 ? (
            <div className="cmdk-empty">No matches for "{query}"</div>
          ) : (
            <>
              {Object.entries(groups).map(([kind, items]) => items.length > 0 && (
                <div key={kind} className="cmdk-group">
                  <div className="cmdk-group-label">{kindLabel(kind)} <span className="cmdk-group-count">{items.length}</span></div>
                  {items.map(item => {
                    const idx = flat.indexOf(item);
                    return (
                      <div key={item.label}
                        className={'cmdk-item' + (active === idx ? ' active' : '')}
                        onMouseEnter={() => setActive(idx)}
                        onClick={() => { onAction(item.action); setOpen(false); }}>
                        <span className="cmdk-item-icon">
                          {item.kind === 'bundle' && item.verdict ? (
                            <span style={{ width: 8, height: 8, borderRadius: '50%', background: `var(--${item.verdict})`, display: 'inline-block' }}/>
                          ) : <Icon name={item.icon} size={14}/>}
                        </span>
                        <span className="cmdk-item-label">{item.label}</span>
                        <span className="cmdk-item-desc">{item.desc}</span>
                        {active === idx && <span className="cmdk-kbd">↵</span>}
                      </div>
                    );
                  })}
                </div>
              ))}
            </>
          )}
        </div>
        <div className="cmdk-foot">
          <span><span className="cmdk-kbd">↑</span><span className="cmdk-kbd">↓</span> navigate</span>
          <span><span className="cmdk-kbd">↵</span> select</span>
          <span><span className="cmdk-kbd">ESC</span> close</span>
          <span style={{ marginLeft: 'auto', color: 'var(--text-faint)' }}>{flat.length} results</span>
        </div>
      </div>
    </div>
  );
}

function kindLabel(k) {
  return { screen: 'Screens', action: 'Actions', scenario: 'Scenarios', bundle: 'Recent Bundles' }[k] || k;
}

window.CommandPalette = CommandPalette;
