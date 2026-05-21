/** @jsxRuntime classic */ /** @jsx React.createElement */
/* global React, OPHAMIN, TierChip, Icon, VerdictPill */
// Scenarios — clean library surface. Browse > pick > read in side panel > run.

const { useState: useScnState, useMemo: useScnMemo } = React;

// Plain-language labels for each tier, used in the library shelves.
const TIER_INTRO = {
  scientific:             { label: 'Scientific',   blurb: 'Claims about substrate behaviour'        },
  engineering:            { label: 'Engineering',  blurb: 'Claims about substrate cost'             },
  philosophical:          { label: 'Philosophical',blurb: 'Claims about substrate self-model'       },
  empirical_deep:         { label: 'Empirical-deep', blurb: 'Substrate-physics scenarios (Family A–V)' },
  measurement_machinery:  { label: 'Measurement',  blurb: 'Cross-framework validation of pillars'   },
};

function ScenariosScreen({ onRun }) {
  const D = OPHAMIN;
  const [query, setQuery] = useScnState('');
  const [tier, setTier] = useScnState('all');
  const [selectedName, setSelectedName] = useScnState(null);

  const filtered = useScnMemo(() => {
    let r = D.scenarios;
    if (tier !== 'all') r = r.filter(s => s.tier === tier);
    if (query) {
      const q = query.toLowerCase();
      r = r.filter(s =>
        s.name.toLowerCase().includes(q) ||
        s.goal.toLowerCase().includes(q) ||
        (s.family || '').toLowerCase().includes(q)
      );
    }
    return r;
  }, [query, tier]);

  // Group by tier for the shelves layout
  const shelves = useScnMemo(() => {
    const order = ['scientific','engineering','philosophical','empirical_deep','measurement_machinery'];
    const m = new Map(order.map(t => [t, []]));
    for (const s of filtered) m.get(s.tier)?.push(s);
    return order.filter(t => m.get(t).length > 0).map(t => [t, m.get(t)]);
  }, [filtered]);

  const tierCounts = useScnMemo(() => {
    const m = { all: D.scenarios.length };
    for (const t of Object.keys(TIER_INTRO)) m[t] = D.scenarios.filter(s => s.tier === t).length;
    return m;
  }, []);

  const selected = selectedName ? D.scenarios.find(s => s.name === selectedName) : null;

  return (
    <div className="content-inner page" style={{ maxWidth: 1280 }}>
      <div className="page-header">
        <div>
          <h1 className="page-title">Scenarios</h1>
          <div className="page-subtitle">Browse what the substrate can be asked to prove. {D.scenarios.length} scenarios · 5 tiers.</div>
        </div>
        <div className="page-actions">
          <button className="btn"><Icon name="refresh" size={13}/> Reload</button>
        </div>
      </div>

      {/* Search-first hero */}
      <div className="scn-hero">
        <span className="scn-hero-icon"><Icon name="search" size={16}/></span>
        <input className="scn-hero-input" placeholder="Search by name, claim, or substrate primitive…"
          value={query} onChange={e => setQuery(e.target.value)}/>
        {query && <button className="btn ghost icon" onClick={() => setQuery('')} title="Clear"><Icon name="x" size={13}/></button>}
      </div>

      {/* Tier filter pills */}
      <div className="scn-pill-row">
        <TierPill label="All tiers" count={tierCounts.all} active={tier === 'all'} onClick={() => setTier('all')}/>
        {Object.entries(TIER_INTRO).map(([id, meta]) => (
          <TierPill key={id} label={meta.label} count={tierCounts[id]} active={tier === id} onClick={() => setTier(id)} tier={id}/>
        ))}
      </div>

      {/* Library shelves */}
      <div style={{ display: 'flex', flexDirection: 'column', gap: 28, marginTop: 20 }}>
        {shelves.length === 0 && <EmptyState query={query}/>}
        {shelves.map(([t, items]) => (
          <Shelf key={t} tier={t} items={items} onSelect={setSelectedName} selected={selectedName}/>
        ))}
      </div>

      {/* Side detail drawer */}
      {selected && <DetailDrawer scenario={selected} onClose={() => setSelectedName(null)} onRun={onRun}/>}
    </div>
  );
}

function TierPill({ label, count, active, onClick, tier }) {
  return (
    <button onClick={onClick}
      className={'scn-tier-pill' + (active ? ' active' : '') + (tier ? ' tier-' + tier : '')}>
      {label}
      <span className="scn-tier-pill-count">{count}</span>
    </button>
  );
}

function Shelf({ tier, items, onSelect, selected }) {
  const meta = TIER_INTRO[tier] || { label: tier, blurb: '' };
  return (
    <div>
      <div className="scn-shelf-head">
        <span className={'scn-shelf-dot tier-' + tier}/>
        <span className="scn-shelf-label">{meta.label}</span>
        <span className="scn-shelf-blurb">{meta.blurb}</span>
        <span className="scn-shelf-count mono">{items.length}</span>
      </div>
      <div className="scn-shelf-grid">
        {items.map(s => <Tile key={s.name} s={s} onSelect={onSelect} selected={selected === s.name}/>)}
      </div>
    </div>
  );
}

function Tile({ s, onSelect, selected }) {
  const latest = OPHAMIN.bundles
    .filter(b => b.scenario === s.name)
    .sort((a, b) => b.date.localeCompare(a.date))[0];

  // Plain-language headline: pick a friendly first sentence
  const headline = s.goal.split('.')[0];

  return (
    <div className={'scn-tile' + (selected ? ' selected' : '')} onClick={() => onSelect(s.name)}>
      <div className="scn-tile-head">
        <span className={'scn-verdict-bead ' + (latest ? latest.verdict : 'none')} title={latest ? `latest: ${latest.verdict} · ${latest.date}` : 'never run'}/>
        <span className="scn-tile-name">{s.name}</span>
        {!s.claim_available && <span className="scn-tile-warn" title="Needs constructor args"><Icon name="rocket" size={10}/></span>}
      </div>
      <div className="scn-tile-headline">{headline}{headline !== s.goal && '.'}</div>
      <div className="scn-tile-foot">
        <span className="scn-tile-meta">{s.family ? s.family.replace(/_/g,' ') : ''}</span>
        {latest && <span className="scn-tile-latest mono">{latest.date.slice(5)}</span>}
      </div>
    </div>
  );
}

function EmptyState({ query }) {
  return (
    <div style={{ display: 'grid', placeItems: 'center', padding: '60px 20px' }}>
      <div style={{ width: 48, height: 48, borderRadius: '50%', display: 'grid', placeItems: 'center', background: 'var(--bg-surface-2)', color: 'var(--text-muted)' }}>
        <Icon name="search" size={20}/>
      </div>
      <div style={{ marginTop: 12, fontSize: 14, fontWeight: 600 }}>No scenarios match</div>
      <div style={{ marginTop: 4, fontSize: 12, color: 'var(--text-muted)' }}>Try a different name, or clear the tier filter above.</div>
    </div>
  );
}

function DetailDrawer({ scenario, onClose, onRun }) {
  const s = scenario;
  const latest = OPHAMIN.bundles.filter(b => b.scenario === s.name).sort((a, b) => b.date.localeCompare(a.date))[0];
  return (
    <>
      <div className="scn-drawer-backdrop" onClick={onClose}/>
      <aside className="scn-drawer">
        <div className="scn-drawer-head">
          <div style={{ flex: 1, minWidth: 0 }}>
            <div className="scn-drawer-name">{s.name}</div>
            <div style={{ display: 'flex', gap: 6, marginTop: 6, flexWrap: 'wrap', alignItems: 'center' }}>
              <TierChip tier={s.tier}/>
              <span className="chip">{(s.family || '').replace(/_/g,' ')}</span>
              {latest && <VerdictPill verdict={latest.verdict}/>}
            </div>
          </div>
          <button className="btn ghost icon" onClick={onClose}><Icon name="x" size={14}/></button>
        </div>

        <div style={{ padding: 18, overflow: 'auto', flex: 1 }}>
          <DrawerField label="What it tests">{s.goal}</DrawerField>

          {s.claim_available ? (
            <div className="scn-drawer-claim">
              <div className="micro" style={{ marginBottom: 6 }}>PRE-REGISTERED CLAIM</div>
              <div style={{ fontSize: 13, lineHeight: 1.55, color: 'var(--text-primary)', marginBottom: 10 }}>{s.claim.statement}</div>
              <div className="mono" style={{ fontSize: 12, padding: 10, background: 'var(--bg-base)', border: '1px solid var(--border)', borderRadius: 'var(--r-sm)' }}>
                <span style={{ color: 'var(--text-secondary)' }}>{s.claim.threshold.metric}</span>{' '}
                <span style={{ color: 'var(--accent)' }}>{s.claim.threshold.comparator}</span>{' '}
                <span style={{ color: 'var(--text-primary)', fontWeight: 600 }}>{s.claim.threshold.value}</span>{' '}
                <span style={{ color: 'var(--text-muted)' }}>{s.claim.threshold.units}</span>
              </div>
            </div>
          ) : (
            <div className="scn-drawer-warn">
              <div className="micro" style={{ marginBottom: 4, color: 'var(--inconclusive)' }}>CLAIM NEEDS ARGS</div>
              {s.claim_unavailable_reason}
            </div>
          )}

          <DrawerField label="How it tests">{s.method.replace(/_/g, ' ')} on <b>{s.corpus_name}</b></DrawerField>
          <DrawerField label="If refuted">{s.falsification_consequence}</DrawerField>

          {s.claim_available && (
            <>
              <DrawerField label="H₀">{s.claim.h0}</DrawerField>
              <DrawerField label="H₁">{s.claim.h1}</DrawerField>
            </>
          )}

          {latest && (
            <div className="scn-drawer-latest">
              <div className="micro" style={{ marginBottom: 6 }}>LATEST RUN · {latest.date}</div>
              <div style={{ display: 'flex', alignItems: 'baseline', gap: 12 }}>
                <span className="mono tnum" style={{ fontSize: 22, fontWeight: 600, color: `var(--${latest.verdict})` }}>{typeof latest.observed === 'number' ? latest.observed.toString() : latest.observed}</span>
                <span className="mono" style={{ fontSize: 11, color: 'var(--text-muted)' }}>{s.claim?.threshold?.units}</span>
              </div>
            </div>
          )}
        </div>

        <div className="scn-drawer-foot">
          <button className="btn ghost" style={{ fontSize: 12 }}><Icon name="copy" size={12}/> Copy name</button>
          <button className="btn primary" onClick={() => onRun(s)} disabled={!s.claim_available}>
            <Icon name="play" size={13}/> Run scenario
          </button>
        </div>
      </aside>
    </>
  );
}

function DrawerField({ label, children }) {
  return (
    <div className="scn-drawer-field">
      <div className="micro" style={{ marginBottom: 4 }}>{label}</div>
      <div style={{ fontSize: 13, lineHeight: 1.6, color: 'var(--text-secondary)' }}>{children}</div>
    </div>
  );
}

window.ScenariosScreen = ScenariosScreen;
