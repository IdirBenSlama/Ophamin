/** @jsxRuntime classic */ /** @jsx React.createElement */
/* global React, OPHAMIN, VerdictPill, TierChip, FormatBadges, Icon, formatNum */
// Proofs screen — filterable table + proof viewer with 5 format tabs.

const { useState: useProofState, useMemo: useProofMemo, useEffect: useProofEffect } = React;

function ProofsScreen({ initialFilter, initialBundle }) {
  const D = OPHAMIN;
  const [query, setQuery] = useProofState('');
  const [verdict, setVerdict] = useProofState(initialFilter || 'all');
  const [tier, setTier] = useProofState('all');
  const [family, setFamily] = useProofState('all');
  const [sortKey, setSortKey] = useProofState('date');
  const [sortDir, setSortDir] = useProofState('desc');
  const [selected, setSelected] = useProofState(initialBundle || D.bundles[0]);

  useProofEffect(() => { if (initialFilter) setVerdict(initialFilter); }, [initialFilter]);
  useProofEffect(() => { if (initialBundle) setSelected(initialBundle); }, [initialBundle]);

  const filtered = useProofMemo(() => {
    let r = D.bundles;
    if (verdict !== 'all') r = r.filter(b => b.verdict === verdict);
    if (tier !== 'all') r = r.filter(b => b.tier === tier);
    if (family !== 'all') r = r.filter(b => b.family === family);
    if (query) {
      const q = query.toLowerCase();
      r = r.filter(b => b.scenario.toLowerCase().includes(q) || b.short_hash.includes(q) || b.date.includes(q));
    }
    r = [...r].sort((a, b) => {
      const av = a[sortKey], bv = b[sortKey];
      const cmp = av < bv ? -1 : av > bv ? 1 : 0;
      return sortDir === 'asc' ? cmp : -cmp;
    });
    return r;
  }, [verdict, tier, query, sortKey, sortDir]);

  // verdict counts under current tier/query filter (for chip badges)
  const [sidebarCollapsed, setSidebarCollapsed] = useProofState(false);
  const counts = useProofMemo(() => {
    let r = D.bundles;
    if (tier !== 'all') r = r.filter(b => b.tier === tier);
    if (query) {
      const q = query.toLowerCase();
      r = r.filter(b => b.scenario.toLowerCase().includes(q) || b.short_hash.includes(q) || b.date.includes(q));
    }
    return {
      all: r.length,
      validated: r.filter(b => b.verdict === 'validated').length,
      refuted: r.filter(b => b.verdict === 'refuted').length,
      inconclusive: r.filter(b => b.verdict === 'inconclusive').length,
    };
  }, [tier, query]);

  const tierCounts = useProofMemo(() => {
    const m = { all: D.bundles.length };
    for (const t of ['engineering','measurement_machinery','scientific','philosophical']) {
      m[t] = D.bundles.filter(b => b.tier === t).length;
    }
    return m;
  }, []);

  return (
    <div className="proofs-layout" data-sidebar={sidebarCollapsed ? 'collapsed' : 'expanded'}>
      {/* ============ FILTER SIDEBAR ============ */}
      <aside className="filter-sidebar">
        {sidebarCollapsed ? (
          <div className="filter-sidebar-collapsed">
            <button className="btn ghost icon" onClick={() => setSidebarCollapsed(false)} title="Expand filters">
              <Icon name="filter" size={14}/>
            </button>
            <div style={{ writingMode: 'vertical-rl', transform: 'rotate(180deg)', fontSize: 10, color: 'var(--text-muted)', letterSpacing: '0.12em', textTransform: 'uppercase', marginTop: 16 }}>
              Filters · {filtered.length} of {D.totals.bundles}
            </div>
          </div>
        ) : (
          <>
        <div className="filter-sidebar-header">
          <div className="toggle-group" style={{ flex: 1 }}>
            <button className="active" style={{ flex: 1, justifyContent: 'center' }}>Bundles</button>
            <button style={{ flex: 1, justifyContent: 'center' }}>Activity</button>
          </div>
          <button className="btn ghost icon" onClick={() => setSidebarCollapsed(true)} title="Collapse filters" style={{ marginLeft: 8 }}>
            <Icon name="chevronL" size={13}/>
          </button>
        </div>

        <FilterGroup label="Search">
          <div style={{ position: 'relative' }}>
            <span style={{ position: 'absolute', left: 8, top: '50%', transform: 'translateY(-50%)', color: 'var(--text-muted)' }}>
              <Icon name="search" size={12}/>
            </span>
            <input className="input" style={{ paddingLeft: 28, height: 26, fontSize: 12 }}
              placeholder="scenario · hash"
              value={query} onChange={e => setQuery(e.target.value)}/>
          </div>
        </FilterGroup>

        <FilterGroup label="Verdict">
          <FilterChip color="var(--text-primary)" active={verdict === 'all'} onClick={() => setVerdict('all')} count={counts.all}>All</FilterChip>
          <FilterChip color="var(--validated)" active={verdict === 'validated'} onClick={() => setVerdict('validated')} count={counts.validated}>Validated</FilterChip>
          <FilterChip color="var(--refuted)" active={verdict === 'refuted'} onClick={() => setVerdict('refuted')} count={counts.refuted}>Refuted</FilterChip>
          <FilterChip color="var(--inconclusive)" active={verdict === 'inconclusive'} onClick={() => setVerdict('inconclusive')} count={counts.inconclusive}>Inconclusive</FilterChip>
        </FilterGroup>

        <FilterGroup label="Tier">
          <FilterChip active={tier === 'all'} onClick={() => setTier('all')} count={tierCounts.all}>All tiers</FilterChip>
          <FilterChip active={tier === 'engineering'} onClick={() => setTier('engineering')} count={tierCounts.engineering}>Engineering</FilterChip>
          <FilterChip active={tier === 'measurement_machinery'} onClick={() => setTier('measurement_machinery')} count={tierCounts.measurement_machinery}>Measurement</FilterChip>
          <FilterChip active={tier === 'scientific'} onClick={() => setTier('scientific')} count={tierCounts.scientific}>Scientific</FilterChip>
          <FilterChip active={tier === 'philosophical'} onClick={() => setTier('philosophical')} count={tierCounts.philosophical}>Philosophical</FilterChip>
        </FilterGroup>

        <FilterGroup label="Family">
          <FilterChip active={family === 'all'} onClick={() => setFamily('all')} count={D.totals.bundles}>All families</FilterChip>
          {[...new Set(D.bundles.map(b => b.family))].sort().map(f => (
            <FilterChip key={f} active={family === f} onClick={() => setFamily(f)} count={D.bundles.filter(b => b.family === f).length}>
              <span className="family-chip" style={{ marginRight: 6 }}>{f}</span>family {f}
            </FilterChip>
          ))}
        </FilterGroup>

        <FilterGroup label="Date">
          <div className="toggle-group" style={{ width: '100%' }}>
            <button className="active" style={{ flex: 1, justifyContent: 'center' }}>1D</button>
            <button style={{ flex: 1, justifyContent: 'center' }}>1W</button>
            <button style={{ flex: 1, justifyContent: 'center' }}>1M</button>
            <button style={{ flex: 1, justifyContent: 'center' }}>All</button>
          </div>
        </FilterGroup>

        <FilterGroup label="Sort">
          <select className="input" style={{ height: 26, fontSize: 12 }} value={sortKey} onChange={e => setSortKey(e.target.value)}>
            <option value="date">Date</option>
            <option value="verdict">Verdict</option>
            <option value="scenario">Scenario</option>
            <option value="tier">Tier</option>
            <option value="short_hash">Hash</option>
          </select>
        </FilterGroup>

        <div style={{ flex: 1 }}/>

        <div className="filter-footer">
          <button className="link-btn" onClick={() => { setQuery(''); setVerdict('all'); setTier('all'); }}>Clear Filters</button>
          <button className="link-btn"><Icon name="download" size={11}/> Download</button>
          <button className="link-btn">Customize Columns</button>
        </div>
          </>
        )}
      </aside>

      {/* ============ MAIN ============ */}
      <div className="proofs-main">
        <div className="page-header" style={{ marginBottom: 12 }}>
          <div>
            <h1 className="page-title">Proofs</h1>
            <div className="page-subtitle mono">
              <span style={{ color: 'var(--text-primary)' }}>{filtered.length}</span> of {D.totals.bundles} bundles
              {verdict !== 'all' && <span> · <span style={{ color: `var(--${verdict})`}}>{verdict}</span></span>}
              {tier !== 'all' && <span> · {tier === 'measurement_machinery' ? 'measurement' : tier}</span>}
            </div>
          </div>
          <div className="page-actions">
            <button className="btn"><Icon name="refresh" size={13}/> Reindex</button>
          </div>
        </div>

        <div className="split" style={{ flex: 1, minHeight: 0 }}>
          <div className="card" style={{ overflow: 'hidden', display: 'flex', flexDirection: 'column' }}>
            <div style={{ overflow: 'auto', flex: 1 }}>
              <table className="table table-dense">
                <thead>
                  <tr>
                    <SortHeader k="verdict" sortKey={sortKey} sortDir={sortDir} onSort={k => { setSortKey(k); setSortDir(d => d === 'asc' ? 'desc' : 'asc'); }} style={{ width: 110 }}>Verdict</SortHeader>
                    <SortHeader k="scenario" sortKey={sortKey} sortDir={sortDir} onSort={k => { setSortKey(k); setSortDir(d => d === 'asc' ? 'desc' : 'asc'); }}>Scenario</SortHeader>
                    <SortHeader k="tier" sortKey={sortKey} sortDir={sortDir} onSort={k => { setSortKey(k); setSortDir(d => d === 'asc' ? 'desc' : 'asc'); }}>Tier</SortHeader>
                    <SortHeader k="date" sortKey={sortKey} sortDir={sortDir} onSort={k => { setSortKey(k); setSortDir(d => d === 'asc' ? 'desc' : 'asc'); }} style={{ width: 90 }}>Date</SortHeader>
                    <SortHeader k="short_hash" sortKey={sortKey} sortDir={sortDir} onSort={k => { setSortKey(k); setSortDir(d => d === 'asc' ? 'desc' : 'asc'); }} style={{ width: 110 }}>Hash</SortHeader>
                    <th style={{ width: 56 }}>Family</th>
                  </tr>
                </thead>
                <tbody>
                  {filtered.map((b, i) => (
                    <tr key={b.path}
                      className={selected?.path === b.path ? 'selected' : ''}
                      onClick={() => setSelected(b)}>
                      <td><VerdictPill verdict={b.verdict}/></td>
                      <td style={{ fontWeight: 500 }}>{b.scenario}</td>
                      <td><TierChip tier={b.tier}/></td>
                      <td className="col-date">{b.date}</td>
                      <td className="col-hash" style={{ position: 'relative' }}>
                        <span style={{ display: 'inline-flex', alignItems: 'center', gap: 6 }}>
                          {b.short_hash}
                          <span className="row-actions" onClick={e => e.stopPropagation()}>
                            <span className="icon-action" title="Copy hash"><Icon name="copy" size={11}/></span>
                            <span className="icon-action" title="Download bundle"><Icon name="download" size={11}/></span>
                            <span className="icon-action" title="Open"><Icon name="external" size={11}/></span>
                          </span>
                        </span>
                      </td>
                      <td><span className="family-chip" title={'Family ' + b.family}>{b.family}</span></td>
                    </tr>
                  ))}
                  {filtered.length === 0 && (
                    <tr><td colSpan="6">
                      <div style={{ padding: '48px 24px', textAlign: 'center', display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 12 }}>
                        <div style={{ width: 48, height: 48, borderRadius: '50%', display: 'grid', placeItems: 'center', background: 'var(--bg-surface-2)', color: 'var(--text-muted)' }}>
                          <Icon name="filter" size={20}/>
                        </div>
                        <div style={{ fontSize: 14, fontWeight: 600 }}>No bundles match</div>
                        <div style={{ fontSize: 12, color: 'var(--text-muted)' }}>Try clearing filters, broadening the verdict, or searching by hash.</div>
                        <button className="btn primary" style={{ fontSize: 12 }} onClick={() => { setQuery(''); setVerdict('all'); setTier('all'); }}>Clear all filters</button>
                      </div>
                    </td></tr>
                  )}
                </tbody>
              </table>
            </div>
            <div className="table-footer">
              <span className="mono" style={{ fontSize: 11, color: 'var(--text-muted)' }}>
                1–{filtered.length} of {D.totals.bundles} bundles
              </span>
              <div className="link-btn-row">
                <span className="mono" style={{ fontSize: 11, color: 'var(--text-muted)' }}>Rows per page:</span>
                <select className="input" style={{ width: 60, height: 22, fontSize: 11, padding: '0 6px' }}>
                  <option>50</option><option>100</option><option>200</option>
                </select>
              </div>
            </div>
          </div>

          <ProofViewer bundle={selected}/>
        </div>
      </div>
    </div>
  );
}

// Filter sidebar primitives
function FilterGroup({ label, children, defaultOpen = true }) {
  const [open, setOpen] = useProofState(defaultOpen);
  return (
    <div className="filter-group">
      <div className="filter-group-head" onClick={() => setOpen(o => !o)}>
        <span>{label}</span>
        <Icon name={open ? 'chevronD' : 'chevronR'} size={11}/>
      </div>
      {open && <div className="filter-group-body">{children}</div>}
    </div>
  );
}

function FilterChip({ active, onClick, count, color, children }) {
  return (
    <button className={'filter-chip' + (active ? ' active' : '')} onClick={onClick}
      style={active && color ? { color, borderColor: color, background: 'transparent' } : null}>
      {color && <span className="filter-chip-dot" style={{ background: color }}/>}
      <span className="filter-chip-label">{children}</span>
      {count != null && <span className="filter-chip-count mono">{count}</span>}
    </button>
  );
}

function SortHeader({ k, sortKey, sortDir, onSort, children, style }) {
  const active = sortKey === k;
  return (
    <th style={style} onClick={() => onSort(k)} className={active ? 'sorted' : ''}>
      {children}
      <span className="sort-arrow">{active ? (sortDir === 'asc' ? '↑' : '↓') : '⇅'}</span>
    </th>
  );
}

// =====================================================================
// ProofViewer — 5 format tabs + structured Claim/Verdict/Evidence panel
// =====================================================================
function ProofViewer({ bundle }) {
  const [tab, setTab] = useProofState('summary');
  if (!bundle) return <div className="card empty">Select a bundle</div>;
  const proof = OPHAMIN.buildProof(bundle);

  return (
    <div className="card" style={{ overflow: 'hidden', display: 'flex', flexDirection: 'column' }}>
      {/* Header */}
      <div style={{
        padding: '14px 20px',
        borderBottom: '1px solid var(--border)',
        background: `linear-gradient(180deg, var(--${bundle.verdict}-bg) 0%, transparent 100%)`
      }}>
        <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', gap: 12 }}>
          <div style={{ flex: 1, minWidth: 0 }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 6 }}>
              <VerdictPill verdict={bundle.verdict}/>
              <TierChip tier={bundle.tier}/>
              <span className="mono" style={{ fontSize: 11, color: 'var(--text-muted)' }}>{bundle.date}</span>
            </div>
            <div style={{ fontSize: 16, fontWeight: 600, marginBottom: 4 }}>{bundle.scenario}</div>
            <div className="mono" style={{ fontSize: 10, color: 'var(--text-muted)', wordBreak: 'break-all' }}>
              proof_id: {proof.proof_id}
            </div>
          </div>
          <div style={{ display: 'flex', gap: 6 }}>
            <button className="btn ghost icon" title="Copy hash"><Icon name="copy" size={14}/></button>
            <button className="btn ghost icon" title="Download"><Icon name="download" size={14}/></button>
            <button className="btn ghost icon" title="Open in new tab"><Icon name="external" size={14}/></button>
          </div>
        </div>
      </div>

      {/* Tabs */}
      <div className="tabs" style={{ padding: '0 8px' }}>
        <Tab id="summary" tab={tab} onTab={setTab}>Summary</Tab>
        <Tab id="verify" tab={tab} onTab={setTab}>Verify</Tab>
        <FormatsMenu tab={tab} onTab={setTab}/>
      </div>

      {/* Body */}
      <div style={{ flex: 1, overflow: 'auto', padding: 20 }}>
        {tab === 'summary' && <SummaryView bundle={bundle} proof={proof}/>}
        {tab === 'json' && <JsonView data={proof}/>}
        {tab === 'md' && <MdView bundle={bundle} proof={proof}/>}
        {tab === 'html' && <HtmlView bundle={bundle} proof={proof}/>}
        {tab === 'tex' && <TexView bundle={bundle} proof={proof}/>}
        {tab === 'pdf' && <PdfView bundle={bundle} proof={proof}/>}
        {tab === 'verify' && <VerifyView bundle={bundle} proof={proof}/>}
      </div>
    </div>
  );
}

function Tab({ id, tab, onTab, children }) {
  return (
    <div className={'tab' + (tab === id ? ' active' : '')} onClick={() => onTab(id)}>
      {children}
    </div>
  );
}

// ----- Summary (the structured claim/verdict/evidence view) -----
function SummaryView({ bundle, proof }) {
  const c = proof.claim;
  const t = c.threshold;
  const obs = bundle.observed;
  const lo = bundle.ci[0], hi = bundle.ci[1];

  // map observed onto a normalized 0..1 axis around threshold (for visual)
  const axisRange = computeAxisRange(t.value, lo, hi, obs);
  const pct = v => Math.max(0, Math.min(1, (v - axisRange[0]) / (axisRange[1] - axisRange[0])));

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
      {/* Verdict banner with observed/threshold */}
      <div style={{
        border: `1px solid var(--${bundle.verdict}-line)`,
        background: `var(--${bundle.verdict}-bg)`,
        borderRadius: 'var(--r-md)',
        padding: 16,
      }}>
        <div className="micro" style={{ color: `var(--${bundle.verdict})`, display: 'flex', alignItems: 'center', gap: 8 }}>
          <Glossary term="verdict"><span>VERDICT</span></Glossary>
          {bundle.verdict === 'refuted' && <span style={{ color: 'var(--text-muted)', letterSpacing: 0, textTransform: 'none', fontSize: 10 }}>· the framework's commitment held; the substrate did not meet it</span>}
          {bundle.verdict === 'validated' && <span style={{ color: 'var(--text-muted)', letterSpacing: 0, textTransform: 'none', fontSize: 10 }}>· the substrate met a threshold preregistered before the run</span>}
          {bundle.verdict === 'inconclusive' && <span style={{ color: 'var(--text-muted)', letterSpacing: 0, textTransform: 'none', fontSize: 10 }}>· evidence did not resolve the claim within tolerance</span>}
        </div>
        <div style={{ display: 'flex', alignItems: 'baseline', gap: 16, marginTop: 6 }}>
          <div style={{ fontSize: 20, fontWeight: 600, letterSpacing: '-0.01em', color: `var(--${bundle.verdict})`, textTransform: 'uppercase' }}>
            {bundle.verdict}
          </div>
          <div className="mono" style={{ fontSize: 13, color: 'var(--text-secondary)' }}>
            observed <span style={{ color: 'var(--text-primary)' }}>{formatNum(obs)}</span> {t.units}
            &nbsp;·&nbsp; threshold <span style={{ color: 'var(--text-primary)' }}>{t.comparator} {formatNum(t.value)}</span>
          </div>
        </div>
        {/* visual scale */}
        <div style={{ marginTop: 14, position: 'relative', padding: '14px 0 8px' }}>
          <div className="ci-bar">
            <div className="range" style={{ left: `${pct(lo)*100}%`, width: `${(pct(hi)-pct(lo))*100}%` }}/>
            <div className="threshold" style={{ left: `${pct(t.value)*100}%` }}/>
            <div className="obs" style={{ left: `${pct(obs)*100}%` }}/>
          </div>
          <div className="mono" style={{ display: 'flex', justifyContent: 'space-between', marginTop: 6, fontSize: 10, color: 'var(--text-muted)' }}>
            <span>{formatNum(axisRange[0])}</span>
            <span>obs={formatNum(obs)}</span>
            <span>{formatNum(axisRange[1])}</span>
          </div>
        </div>
        <div style={{ fontSize: 12, color: 'var(--text-secondary)', marginTop: 8, fontStyle: 'italic' }}>
          {proof.verdict.reasoning}
        </div>
      </div>

      {/* Pre-registration receipt strip — surfaces the epistemic spine */}
      <PreregReceipt proof={proof}/>

      {/* Refuted-Investigation section — only on REFUTED */}
      {bundle.verdict === 'refuted' && <RefutedInvestigation bundle={bundle} proof={proof}/>}
      {bundle.verdict === 'validated' && <ConfoundEnumeration bundle={bundle} proof={proof}/>}
      {bundle.verdict === 'inconclusive' && <InconclusiveResolution bundle={bundle} proof={proof}/>}

      {/* Claim panel */}
      <Section label="CLAIM" icon="eye">
        <div style={{ display: 'grid', gridTemplateColumns: '110px 1fr', gap: '6px 16px', fontSize: 13 }}>
          <Field k="statement" v={c.statement}/>
          <Field k="operation"  v={c.operationalization}/>
          <Field k="threshold"  v={<span className="mono">{t.metric} <span style={{ color: 'var(--accent)' }}>{t.comparator}</span> {t.value} <span style={{ color: 'var(--text-muted)' }}>{t.units}</span></span>}/>
          <Field k="H₀" v={c.h0}/>
          <Field k="H₁" v={c.h1}/>
        </div>
      </Section>

      {/* Evidence panel */}
      <Section label="EVIDENCE · OFAMIN PILLARS" icon="activity">
        <table className="table" style={{ fontSize: 12 }}>
          <thead>
            <tr>
              <th><Glossary term="pillar"><span>Pillar</span></Glossary></th>
              <th>Statistic</th>
              <th><Glossary term="observed"><span>Value</span></Glossary></th>
              <th><Glossary term="wilson-ci"><span>95% CI</span></Glossary></th>
              <th><Glossary term="p-value"><span>p</span></Glossary></th>
              <th style={{ width: 140 }}>Range</th>
            </tr>
          </thead>
          <tbody>
            {proof.evidence.map((e, i) => (
              <tr key={i} style={{ cursor: 'default' }}>
                <td className="mono" style={{ color: 'var(--accent)' }}>{e.pillar}</td>
                <td className="mono" style={{ color: 'var(--text-secondary)' }}>{e.statistic_name}</td>
                <td className="mono tnum" style={{ fontWeight: 500 }}>{formatNum(e.statistic_value)}</td>
                <td className="mono" style={{ color: 'var(--text-muted)' }}>[{formatNum(e.ci_low)}, {formatNum(e.ci_high)}]</td>
                <td className="mono tnum" style={{ color: 'var(--text-muted)' }}>{e.p_value == null ? '—' : e.p_value.toFixed(4)}</td>
                <td><MiniRange lo={e.ci_low} hi={e.ci_high} obs={e.statistic_value} t={t}/></td>
              </tr>
            ))}
          </tbody>
        </table>
      </Section>

      {/* Provenance */}
      <ReproductionReceipt proof={proof}/>

      <Section label="PROVENANCE · W3C PROV-O" icon="cpu">
        <ProvGraph proof={proof}/>
      </Section>

      <Section label="PREREGISTRATION · IDENTITY" icon="cpu">
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '6px 16px', fontSize: 12 }}>
          <Field k="config_hash"   v={<span className="mono" style={{ wordBreak: 'break-all', fontSize: 11 }}>{proof.preregistration.config_hash}</span>}/>
          <Field k="data_hash"     v={<span className="mono" style={{ wordBreak: 'break-all', fontSize: 11 }}>{proof.preregistration.data_hash}</span>}/>
          <Field k="prereg_at"     v={<span className="mono">{proof.preregistration.preregistered_at}</span>}/>
          <Field k="analysis_plan" v={<span className="mono" style={{ fontSize: 11 }}>{proof.preregistration.analysis_plan}</span>}/>
          <Field k="substrate"     v={<span className="mono">{proof.data.substrate_name} @ {proof.data.substrate_git_commit.slice(0,12)}</span>}/>
          <Field k="dataset"       v={<span className="mono">{proof.data.datasets[0].name} ({proof.data.datasets[0].n_records} records)</span>}/>
        </div>
      </Section>
    </div>
  );
}

function ReproductionReceipt({ proof }) {
  const cmd = proof.reproduction?.command || '—';
  const env = proof.reproduction?.environment || {};
  const pkgs = Object.entries(env).filter(([k]) => k !== 'python' && k !== 'platform');
  return (
    <div className="repro-card">
      <div className="micro" style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 10 }}>
        <span style={{ color: 'var(--accent)' }}><Icon name="refresh" size={12}/></span>
        <span>REPRODUCE THIS PROOF</span>
        <span style={{ flex: 1, height: 1, background: 'var(--border)', marginLeft: 8 }}/>
        <span className="mono" style={{ fontSize: 10, color: 'var(--text-muted)', letterSpacing: 0 }}>{pkgs.length + ' deps locked'}</span>
      </div>
      <div className="repro-cmd">
        <span className="mono" style={{ color: 'var(--text-muted)' }}>$</span>
        <span className="mono" style={{ color: 'var(--text-primary)' }}>{cmd}</span>
        <button className="btn ghost icon" title="Copy"><Icon name="copy" size={11}/></button>
      </div>
      <div className="repro-env">
        <div className="repro-env-row">
          <span className="mono faint">python</span>
          <span className="mono">{env.python || '—'}</span>
        </div>
        <div className="repro-env-row">
          <span className="mono faint">platform</span>
          <span className="mono">{env.platform || '—'}</span>
        </div>
        <div className="repro-env-row">
          <span className="mono faint">ophamin</span>
          <span className="mono">{env.ophamin || proof.identity.ophamin_version}</span>
        </div>
        <div className="repro-env-row">
          <span className="mono faint">substrate</span>
          <span className="mono">{proof.data.substrate_name} @ {proof.data.substrate_git_commit.slice(0, 12)}</span>
        </div>
      </div>
      <details className="repro-pkgs">
        <summary>
          <span style={{ fontSize: 11.5, color: 'var(--text-secondary)' }}>full dependency lockfile ({pkgs.length} packages)</span>
        </summary>
        <div className="repro-pkgs-grid">
          {pkgs.map(([k, v]) => (
            <div key={k} className="repro-pkg">
              <span className="mono" style={{ color: 'var(--text-secondary)' }}>{k}</span>
              <span className="mono" style={{ color: 'var(--accent)' }}>{v}</span>
            </div>
          ))}
        </div>
      </details>
    </div>
  );
}

function Section({ label, icon, children }) {
  return (
    <div>
      <div className="micro" style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 10 }}>
        <span style={{ color: 'var(--accent)', display: 'inline-flex' }}><Icon name={icon} size={12}/></span>
        <span>{label}</span>
        <span style={{ flex: 1, height: 1, background: 'var(--border)', marginLeft: 8 }}/>
      </div>
      {children}
    </div>
  );
}

// ─── Pre-registration receipt strip ─────────────────────────────
function PreregReceipt({ proof }) {
  const stages = [
    { label: 'PREREGISTERED', ts: proof.preregistration.preregistered_at, hash: proof.preregistration.config_hash.slice(7, 19) },
    { label: 'RAN',           ts: proof.identity.created_at,              hash: proof.data.substrate_git_commit.slice(0, 12) },
    { label: 'VERDICT',       ts: proof.identity.created_at,              hash: proof.proof_id.slice(0, 12) },
    { label: 'SIGNED',        ts: proof.identity.created_at,              hash: proof.signature.slice(0, 12) },
  ];
  return (
    <div style={{
      background: 'var(--bg-base)',
      border: '1px solid var(--border)',
      borderLeft: '3px solid var(--accent)',
      borderRadius: 'var(--r-md)',
      padding: '12px 16px',
    }}>
      <div className="micro" style={{ marginBottom: 8, color: 'var(--accent)' }}><Glossary term="preregistration"><span>EPISTEMIC RECEIPT · PRE-REGISTERED BEFORE RUN</span></Glossary></div>
      <div style={{ display: 'flex', alignItems: 'stretch', gap: 0 }}>
        {stages.map((s, i) => (
          <React.Fragment key={s.label}>
            <div style={{ flex: 1, minWidth: 0 }}>
              <div className="mono" style={{ fontSize: 10, color: 'var(--text-muted)', letterSpacing: '0.06em' }}>{s.label}</div>
              <div className="mono tnum" style={{ fontSize: 11, color: 'var(--text-primary)', marginTop: 2 }}>
                {s.ts.replace('T', ' ').slice(0, 16)}
              </div>
              <div className="mono" style={{ fontSize: 10, color: 'var(--accent)', marginTop: 1, overflow: 'hidden', textOverflow: 'ellipsis' }}>{s.hash}</div>
            </div>
            {i < stages.length - 1 && (
              <div style={{ display: 'flex', alignItems: 'center', padding: '0 8px', color: 'var(--text-faint)' }}>
                →
              </div>
            )}
          </React.Fragment>
        ))}
      </div>
    </div>
  );
}

// ─── Refuted investigation block — only renders when refuted ────
function RefutedInvestigation({ bundle, proof }) {
  // Pull the verdict trajectory for this scenario from OPHAMIN.bundles
  const trajectory = OPHAMIN.bundles
    .filter(b => b.scenario === bundle.scenario)
    .sort((a, b) => a.date.localeCompare(b.date))
    .slice(-12);

  const triage = triageFor(bundle.scenario);
  return (
    <div style={{
      background: 'linear-gradient(180deg, var(--refuted-bg) 0%, transparent 100%)',
      border: '1px solid var(--refuted-line)',
      borderRadius: 'var(--r-md)',
      padding: 16,
    }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 12 }}>
        <span style={{ color: 'var(--refuted)' }}><Icon name="rocket" size={14}/></span>
        <div style={{ fontSize: 13, fontWeight: 600 }}>Investigation</div>
        <span className="chip" style={{ marginLeft: 'auto', color: 'var(--inconclusive)', borderColor: 'var(--inconclusive-line)', background: 'var(--inconclusive-bg)' }}>via <span className="mono">ophamin agent triage</span></span>
      </div>

      <p style={{ fontSize: 12.5, color: 'var(--text-secondary)', lineHeight: 1.55, margin: '0 0 14px' }}>
        Observed <span className="mono" style={{ color: 'var(--text-primary)' }}>{formatNum(bundle.observed)}</span> against pre-registered threshold <span className="mono" style={{ color: 'var(--text-primary)' }}>{proof.claim.threshold.comparator} {proof.claim.threshold.value}</span>. The framework's commitment held — the substrate did not meet it. What follows are <b>follow-up scenarios that decompose <i>why</i></b>, not retries of the same claim.
      </p>

      <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
        {triage.map((t, i) => (
          <div key={i} className="investigation-card">
            <div style={{ display: 'flex', alignItems: 'flex-start', gap: 10 }}>
              <span className="investigation-num">{i + 1}</span>
              <div style={{ flex: 1, minWidth: 0 }}>
                <div className="mono" style={{ fontSize: 13, color: 'var(--accent)', fontWeight: 500 }}>{t.name}</div>
                <div style={{ fontSize: 12, color: 'var(--text-secondary)', marginTop: 3, lineHeight: 1.5 }}>{t.rationale}</div>
                <div style={{ display: 'flex', gap: 6, marginTop: 6, flexWrap: 'wrap' }}>
                  <span className="chip">{t.kind}</span>
                  <span className="chip mono" style={{ color: 'var(--text-muted)' }}>{t.target_pillar}</span>
                </div>
              </div>
              <button className="btn ghost" style={{ fontSize: 11, alignSelf: 'flex-start' }}>
                <Icon name="play" size={11}/> Scaffold
              </button>
            </div>
          </div>
        ))}
      </div>

      <div style={{ display: 'flex', gap: 8, marginTop: 14 }}>
        <button className="btn primary" style={{ fontSize: 12 }}>
          <Icon name="refresh" size={12}/> Re-run at substrate HEAD
        </button>
        <button className="btn" style={{ fontSize: 12 }}>
          <Icon name="agents" size={12}/> Open in Agents → triage
        </button>
        <button className="btn" style={{ fontSize: 12 }}>
          <Icon name="external" size={12}/> Export as JUnit failure
        </button>
      </div>

      {/* Verdict trajectory for this scenario */}
      {trajectory.length > 1 && (
        <div style={{ marginTop: 16, paddingTop: 14, borderTop: '1px solid var(--refuted-line)' }}>
          <div className="micro" style={{ marginBottom: 8 }}>VERDICT TRAJECTORY · LAST {trajectory.length} RUNS OF THIS SCENARIO</div>
          <VerdictTrajectory bundles={trajectory} current={bundle}/>
        </div>
      )}
    </div>
  );
}

// ─── Confound enumeration — only renders when validated ─────────
function ConfoundEnumeration({ bundle, proof }) {
  const confounds = confoundsFor(bundle.scenario);
  return (
    <div className="investigation-block" style={{
      background: 'linear-gradient(180deg, var(--validated-bg) 0%, transparent 100%)',
      border: '1px solid var(--validated-line)',
      borderRadius: 'var(--r-md)',
      padding: 16,
    }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 12 }}>
        <span style={{ color: 'var(--validated)' }}><Icon name="eye" size={14}/></span>
        <div style={{ fontSize: 13, fontWeight: 600 }}>Red-team this validation</div>
        <span className="chip" style={{ marginLeft: 'auto' }}>via <span className="mono">ophamin agent confounds</span></span>
      </div>
      <p style={{ fontSize: 12.5, color: 'var(--text-secondary)', lineHeight: 1.55, margin: '0 0 14px' }}>
        A validated verdict is the easier case — the substrate met the threshold. Before drawing scientific conclusions, enumerate alternative explanations and disambiguating tests.
      </p>
      <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
        {confounds.map((c, i) => (
          <div key={i} className="investigation-card">
            <div style={{ display: 'flex', alignItems: 'flex-start', gap: 10 }}>
              <span className="investigation-num">{i + 1}</span>
              <div style={{ flex: 1, minWidth: 0 }}>
                <div style={{ fontSize: 13, color: 'var(--text-primary)', fontWeight: 500 }}>{c.title}</div>
                <div style={{ fontSize: 12, color: 'var(--text-secondary)', marginTop: 3, lineHeight: 1.5 }}>{c.body}</div>
                <div style={{ fontSize: 11, color: 'var(--accent)', marginTop: 6, fontStyle: 'italic' }}>↗ Disambiguating test: {c.test}</div>
              </div>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

// ─── Inconclusive resolution suggestions ────────────────────────
function InconclusiveResolution({ bundle, proof }) {
  return (
    <div className="investigation-block" style={{
      background: 'linear-gradient(180deg, var(--inconclusive-bg) 0%, transparent 100%)',
      border: '1px solid var(--inconclusive-line)',
      borderRadius: 'var(--r-md)',
      padding: 16,
    }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 12 }}>
        <span style={{ color: 'var(--inconclusive)' }}><Icon name="activity" size={14}/></span>
        <div style={{ fontSize: 13, fontWeight: 600 }}>What would resolve this?</div>
        <span className="chip">advisory</span>
      </div>
      <p style={{ fontSize: 12.5, color: 'var(--text-secondary)', lineHeight: 1.55, margin: 0 }}>
        Observed <span className="mono">{formatNum(bundle.observed)}</span> with 95% CI crossing the threshold of <span className="mono">{proof.claim.threshold.value}</span>. The current evidence does not resolve the claim. Standard remedies:
      </p>
      <ul style={{ fontSize: 12, color: 'var(--text-secondary)', lineHeight: 1.6, paddingLeft: 18, marginTop: 8 }}>
        <li><b>Increase sample size</b> until the CI excludes the threshold (likely 2–4× current N).</li>
        <li><b>Reduce variance</b> in the corpus — stratify by record kind and re-run.</li>
        <li><b>Tighten the threshold</b> if the operational requirement is genuinely looser than the original claim.</li>
      </ul>
    </div>
  );
}

// ─── Verdict trajectory — a horizontal timeline of past runs ────
function VerdictTrajectory({ bundles, current }) {
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 6, overflowX: 'auto' }}>
      {bundles.map((b, i) => {
        const isCurrent = b.path === current.path;
        return (
          <div key={b.path} style={{ position: 'relative', display: 'flex', flexDirection: 'column', alignItems: 'center', minWidth: 70, paddingTop: 8 }}>
            {i > 0 && (
              <div style={{ position: 'absolute', left: -3, right: 'calc(50% + 6px)', top: 18, height: 1, background: 'var(--border-strong)' }}/>
            )}
            <div style={{
              width: 16, height: 16, borderRadius: '50%',
              background: `var(--${b.verdict})`,
              border: isCurrent ? '2px solid var(--text-primary)' : '2px solid var(--bg-base)',
              boxShadow: isCurrent ? `0 0 0 2px var(--${b.verdict})` : 'none',
              zIndex: 1,
            }}/>
            <div className="mono" style={{ fontSize: 10, color: isCurrent ? 'var(--text-primary)' : 'var(--text-muted)', marginTop: 4 }}>
              {b.date.slice(5)}
            </div>
            <div className="mono" style={{ fontSize: 9, color: `var(--${b.verdict})`, marginTop: 1, textTransform: 'uppercase', letterSpacing: '0.06em' }}>
              {b.verdict.slice(0, 3)}
            </div>
            <div className="mono" style={{ fontSize: 9, color: 'var(--text-muted)', marginTop: 1 }}>
              {typeof b.observed === 'number' ? formatNum(b.observed) : '—'}
            </div>
          </div>
        );
      })}
    </div>
  );
}

// ─── Mock agent outputs ─────────────────────────────────────────
function triageFor(scenario) {
  // realistic per-scenario follow-ups (mocked from `ophamin agent triage`)
  const map = {
    'logic-topology-siege': [
      { name: 'walker-step-budget',     kind: 'parameter sweep',  target_pillar: 'O.topology.steps',     rationale: 'Vary the walker step budget; if traversal rate scales with budget, the 39.6% is a budget artifact rather than a substrate failure.' },
      { name: 'corpus-density-control', kind: 'corpus stratify',  target_pillar: 'O.topology.density',   rationale: 'Test on lower-density commit subgraphs (filter by branching factor) to isolate topology effect from corpus density.' },
      { name: 'walker-seed-stability',  kind: 'determinism',      target_pillar: 'A.adaptive.stability', rationale: 'Fix walker seed and rerun N=20 times. If variance is high the 39.6% is stochastic; if low it is structural.' },
    ],
    'concentrated-immune-siege': [
      { name: 'immune-class-decomposition', kind: 'corpus stratify', target_pillar: 'O.immune.false_positive', rationale: 'Decompose false-positive rate by malicious sub-class (prompt-injection / jailbreak / payload). If one class dominates, GWF tuning is class-specific.' },
      { name: 'immune-detector-isolation',  kind: 'layer isolation', target_pillar: 'O.immune.detection',      rationale: 'Run the GWF alone vs. the full stack to attribute the 15.8% benign-FP to specific defense layers.' },
      { name: 'immune-corpus-shift',        kind: 'corpus swap',     target_pillar: 'O.immune.false_positive', rationale: 'Re-run on a different adversarial corpus (Garak) to test whether the false-positive ceiling is corpus-dependent.' },
    ],
    'sinew-conservation': [
      { name: 'sinew-perturbation-spectrum', kind: 'parameter sweep', target_pillar: 'O.sinew.conservation', rationale: 'Sweep perturbation magnitude. Where does the M4 ratio cross 0.05? That boundary characterizes the conservation regime.' },
      { name: 'sinew-baseline-control',      kind: 'baseline',        target_pillar: 'O.sinew.conservation', rationale: 'Measure M4 ratio on a control trajectory with no perturbation. Quantify the baseline noise floor.' },
      { name: 'sinew-cycle-length-effect',   kind: 'temporal',        target_pillar: 'O.sinew.conservation', rationale: 'Does the ratio drift with cycle index? If yes, conservation is time-dependent, not a constant.' },
    ],
    'philosophical-self-reference': [
      { name: 'self-ref-corpus-control', kind: 'corpus swap',      target_pillar: 'O.self_model.effect', rationale: 'Replace neutral baseline with a third corpus (factual statements). If effect persists, self-reference is real; if it vanishes, the neutral baseline was the problem.' },
      { name: 'self-ref-prompt-variation', kind: 'prompt stratify', target_pillar: 'O.self_model.effect', rationale: 'Vary self-reference phrasing. If d depends on phrasing, the effect is linguistic, not architectural.' },
      { name: 'self-ref-temporal-sweep',   kind: 'temporal',        target_pillar: 'O.self_model.effect', rationale: 'Test at different substrate "ages" (cycle counts). Cohen\'s d may scale with substrate familiarity.' },
    ],
    'rosetta-scaling': [
      { name: 'rosetta-language-pair-decomposition', kind: 'corpus stratify', target_pillar: 'O.language.agreement', rationale: 'Decompose agreement by language pair. Find which pairs fail and look for typological commonality.' },
      { name: 'rosetta-tokenization-control',        kind: 'preprocessing',   target_pillar: 'O.language.agreement', rationale: 'Hold tokenization fixed across languages — does agreement improve? If yes, tokenizer mismatch is the cause.' },
      { name: 'rosetta-script-stratify',             kind: 'corpus stratify', target_pillar: 'O.language.agreement', rationale: 'Group by script (Latin / CJK / RTL). If failure clusters by script, it is a representation issue, not a Rosetta one.' },
    ],
  };
  return map[scenario] || [
    { name: 'parameter-sweep-' + scenario,  kind: 'parameter sweep',  target_pillar: 'O.' + scenario,  rationale: 'Sweep the primary parameter near the threshold to characterize the boundary rather than the failure.' },
    { name: 'baseline-control-' + scenario, kind: 'baseline',         target_pillar: 'O.' + scenario,  rationale: 'Establish a control baseline so we can attribute the failure to the substrate vs. the corpus.' },
    { name: 'stratify-' + scenario,         kind: 'corpus stratify',  target_pillar: 'O.' + scenario,  rationale: 'Decompose the failure into sub-populations to find what dominates.' },
  ];
}

function confoundsFor(scenario) {
  const map = {
    'concentrated-immune-siege': [
      { title: 'Corpus bias', body: 'Benign-labelled records may already be filtered upstream by metasploit/SecLists curation. The substrate may pass not because the GWF is well-tuned, but because the inputs were prefiltered.', test: 'inject random text from flores-200 as a benign control.' },
      { title: 'Label leakage', body: 'GWF may have implicit access to corpus tags. The 3.2% false-positive rate could collapse if labels were shuffled.', test: 'shuffle benign/malicious labels post-hoc; verdict should hold or flip predictably.' },
      { title: 'Sample-size artifact', body: 'n=500 benign gives Wilson CI [1.98%, 5.13%]. At n=10,000 the true rate could rise above 10%.', test: 'rerun at 10× sample.' },
    ],
    'throughput-ceiling': [
      { title: 'System-load coupling', body: 'p95 wall-time was measured on a single machine state. If background load was low, the substrate may exceed the 4.0s ceiling under realistic concurrency.', test: 'rerun with concurrent unrelated process load to simulate production.' },
      { title: 'Warm-cache effect', body: 'The substrate may have been warm-cached across cycles. First-cycle latency dominates real-world deployment.', test: 'measure first-cycle latency only across N fresh processes.' },
      { title: 'Corpus homogeneity', body: 'The offensive-security corpus has narrow length distribution. Real-world inputs are heavier-tailed.', test: 'rerun on a mixed corpus weighted toward the input-length tail.' },
    ],
  };
  return map[scenario] || [
    { title: 'Corpus selection bias',   body: 'The corpus may not be representative of the substrate\'s deployment distribution.',                                test: 'rerun on an independent corpus with similar shape.' },
    { title: 'Specification leak',      body: 'The substrate may have been tuned (intentionally or not) on inputs similar to the corpus.',                    test: 'rerun on a corpus held out from substrate development.' },
    { title: 'Statistical chance',      body: 'A validated verdict near the threshold could be a stochastic pass.',                                            test: 'replicate N=20 times; check the empirical pass rate.' },
  ];
}


function Field({ k, v }) {
  return (
    <>
      <div className="mono" style={{ fontSize: 11, color: 'var(--text-muted)', paddingTop: 2 }}>{k}</div>
      <div>{v}</div>
    </>
  );
}

function MiniRange({ lo, hi, obs, t }) {
  // crude: just compare to threshold
  const v = formatNum(obs);
  const pass = (() => {
    if (t.comparator === '<=') return obs <= t.value;
    if (t.comparator === '<')  return obs <  t.value;
    if (t.comparator === '>=') return obs >= t.value;
    if (t.comparator === '>')  return obs >  t.value;
    if (t.comparator === '==') return obs === t.value;
    return true;
  })();
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
      <div style={{ flex: 1, height: 4, background: 'var(--bg-base)', borderRadius: 2, position: 'relative', border: '1px solid var(--border)' }}>
        <div style={{ position: 'absolute', left: '20%', right: '20%', top: -1, bottom: -1, background: pass ? 'var(--validated)' : 'var(--refuted)', opacity: 0.4, borderRadius: 2 }}/>
        <div style={{ position: 'absolute', left: '40%', top: -2, bottom: -2, width: 2, background: pass ? 'var(--validated)' : 'var(--refuted)' }}/>
      </div>
    </div>
  );
}

function computeAxisRange(threshold, lo, hi, obs) {
  const all = [threshold, lo, hi, obs].filter(v => typeof v === 'number' && isFinite(v));
  if (!all.length) return [0, 1];
  let min = Math.min(...all);
  let max = Math.max(...all);
  if (min === max) { min = min - 1; max = max + 1; }
  const pad = (max - min) * 0.18;
  return [min - pad, max + pad];
}

// ----- JSON view -----
function JsonView({ data }) {
  return (
    <div className="json-tree" style={{ position: 'relative' }}>
      <div style={{ position: 'absolute', top: -6, right: 0, display: 'flex', gap: 6 }}>
        <button className="btn ghost" style={{ fontSize: 11 }}><Icon name="copy" size={12}/> Copy</button>
      </div>
      <JsonNode value={data} depth={0} isLast={true} keyName={null}/>
    </div>
  );
}

function JsonNode({ value, depth, keyName, isLast }) {
  const isObj = value !== null && typeof value === 'object' && !Array.isArray(value);
  const isArr = Array.isArray(value);
  const keyEl = keyName != null && <><span className="key">"{keyName}"</span><span className="punct">: </span></>;

  if (isObj || isArr) {
    const entries = isArr ? value.map((v, i) => [i, v]) : Object.entries(value);
    const open = isArr ? '[' : '{';
    const close = isArr ? ']' : '}';
    return (
      <details open={depth < 2}>
        <summary>{keyEl}<span className="punct">{open}</span> <span className="punct" style={{ opacity: 0.6 }}>{entries.length} {isArr ? 'items' : 'keys'}</span></summary>
        <div style={{ paddingLeft: 16, borderLeft: '1px dashed var(--border)' }}>
          {entries.map(([k, v], i) => (
            <div key={k}><JsonNode value={v} depth={depth + 1} keyName={isArr ? null : k} isLast={i === entries.length - 1}/></div>
          ))}
        </div>
        <span className="punct">{close}</span>
      </details>
    );
  }
  // primitives
  let cls = 'null', display = String(value);
  if (typeof value === 'string') { cls = 'str'; display = '"' + value + '"'; }
  else if (typeof value === 'number') { cls = 'num'; }
  else if (typeof value === 'boolean') { cls = 'bool'; }
  else if (value === null) { cls = 'null'; display = 'null'; }
  return (
    <span>{keyEl}<span className={cls}>{display}</span>{!isLast && <span className="punct">,</span>}</span>
  );
}

// ----- MD view (rendered) -----
function MdView({ bundle, proof }) {
  const c = proof.claim;
  return (
    <div className="md-body">
      <h1># {bundle.scenario}</h1>
      <p className="muted" style={{ fontFamily: 'JetBrains Mono, monospace', fontSize: 11 }}>
        proof_id: <code>{proof.proof_id}</code> · created <code>{proof.identity.created_at}</code>
      </p>

      <h2>Claim</h2>
      <p>{c.statement}</p>
      <p><strong>Threshold:</strong> <code>{c.threshold.metric} {c.threshold.comparator} {c.threshold.value} {c.threshold.units}</code></p>
      <p><strong>H₀:</strong> {c.h0}</p>
      <p><strong>H₁:</strong> {c.h1}</p>

      <h2>Verdict</h2>
      <p><span className={'verdict-pill ' + bundle.verdict}><span className="dot"></span>{bundle.verdict}</span></p>
      <p>{proof.verdict.reasoning}</p>

      <h2>Evidence</h2>
      <table>
        <thead><tr><th>Pillar</th><th>Statistic</th><th>Value</th><th>95% CI</th><th>p</th></tr></thead>
        <tbody>
          {proof.evidence.map((e, i) => (
            <tr key={i}>
              <td><code>{e.pillar}</code></td>
              <td><code>{e.statistic_name}</code></td>
              <td><code>{formatNum(e.statistic_value)}</code></td>
              <td><code>[{formatNum(e.ci_low)}, {formatNum(e.ci_high)}]</code></td>
              <td><code>{e.p_value == null ? '—' : e.p_value.toFixed(4)}</code></td>
            </tr>
          ))}
        </tbody>
      </table>

      <h2>Chart</h2>
      <ProofChart bundle={bundle} proof={proof}/>
      <p className="muted" style={{ fontSize: 11 }}>assets/{bundle.scenario}-distribution.png</p>

      <h3>Provenance</h3>
      <pre>{`substrate:        ${proof.data.substrate_name}
substrate_commit: ${proof.data.substrate_git_commit}
dataset:          ${proof.data.datasets[0].name} (${proof.data.datasets[0].n_records} records)
config_hash:      ${proof.preregistration.config_hash}
data_hash:        ${proof.preregistration.data_hash}`}</pre>
    </div>
  );
}

// SVG placeholder "chart" — mimics matplotlib distribution + CI bar
function ProofChart({ bundle, proof }) {
  const w = 600, h = 240, pl = 50, pr = 20, pt = 20, pb = 36;
  const lo = bundle.ci[0], hi = bundle.ci[1], obs = bundle.observed, thr = proof.claim.threshold.value;
  const range = computeAxisRange(thr, lo, hi, obs);
  const x = v => pl + ((v - range[0]) / (range[1] - range[0])) * (w - pl - pr);
  // sample a fake normal curve around obs
  const sigma = (hi - lo) / 4 || 0.01;
  const pts = [];
  const n = 60;
  for (let i = 0; i <= n; i++) {
    const v = range[0] + (i / n) * (range[1] - range[0]);
    const y = Math.exp(-0.5 * Math.pow((v - obs) / sigma, 2));
    pts.push([x(v), pt + (h - pt - pb) * (1 - y * 0.9)]);
  }
  const path = pts.map((p, i) => (i === 0 ? 'M' : 'L') + p[0] + ' ' + p[1]).join(' ');
  const area = path + ` L ${pts[pts.length-1][0]} ${h-pb} L ${pts[0][0]} ${h-pb} Z`;
  return (
    <div style={{ background: 'var(--bg-base)', border: '1px solid var(--border)', borderRadius: 'var(--r-sm)', padding: 12 }}>
      <svg viewBox={`0 0 ${w} ${h}`} width="100%" style={{ display: 'block' }}>
        {/* grid */}
        {[0.25, 0.5, 0.75].map(f => <line key={f} x1={pl} x2={w-pr} y1={pt + (h-pt-pb)*f} y2={pt + (h-pt-pb)*f} stroke="var(--grid)" strokeDasharray="2 4"/>)}
        {/* CI shaded */}
        <rect x={x(lo)} y={pt} width={x(hi) - x(lo)} height={h-pt-pb} fill="var(--accent-soft)" stroke="var(--accent-line)" strokeWidth="1" strokeDasharray="2 2"/>
        {/* distribution */}
        <path d={area} fill="var(--accent-soft)" opacity="0.6"/>
        <path d={path} stroke="var(--accent)" strokeWidth="1.5" fill="none"/>
        {/* threshold */}
        <line x1={x(thr)} x2={x(thr)} y1={pt} y2={h-pb} stroke="var(--text-muted)" strokeWidth="1" strokeDasharray="4 4"/>
        <text x={x(thr)+4} y={pt+10} fontSize="10" fill="var(--text-muted)" fontFamily="JetBrains Mono">θ={formatNum(thr)}</text>
        {/* observed */}
        <line x1={x(obs)} x2={x(obs)} y1={pt} y2={h-pb} stroke={`var(--${bundle.verdict})`} strokeWidth="2"/>
        <circle cx={x(obs)} cy={pt + (h-pt-pb)*0.1} r="4" fill={`var(--${bundle.verdict})`}/>
        <text x={x(obs)+6} y={pt+14} fontSize="11" fill={`var(--${bundle.verdict})`} fontFamily="JetBrains Mono" fontWeight="600">obs={formatNum(obs)}</text>
        {/* axis */}
        <line x1={pl} x2={w-pr} y1={h-pb} y2={h-pb} stroke="var(--border-strong)"/>
        <line x1={pl} x2={pl} y1={pt} y2={h-pb} stroke="var(--border-strong)"/>
        <text x={pl} y={h-pb+16} fontSize="10" fill="var(--text-muted)" fontFamily="JetBrains Mono">{formatNum(range[0])}</text>
        <text x={(pl+w-pr)/2} y={h-pb+16} fontSize="10" fill="var(--text-muted)" textAnchor="middle" fontFamily="JetBrains Mono">{proof.claim.threshold.metric}</text>
        <text x={w-pr} y={h-pb+16} fontSize="10" fill="var(--text-muted)" textAnchor="end" fontFamily="JetBrains Mono">{formatNum(range[1])}</text>
      </svg>
    </div>
  );
}

// ----- HTML view (mimic iframe) -----
function HtmlView({ bundle, proof }) {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
        <span className="mono" style={{ fontSize: 11, color: 'var(--text-muted)', flex: 1 }}>
          /proofs/bundles/file?path={bundle.path}&filename=proof.html
        </span>
        <button className="btn ghost" style={{ fontSize: 11 }}><Icon name="external" size={12}/> Open</button>
      </div>
      <div style={{
        background: '#fafbfc',
        color: '#1a1d21',
        border: '1px solid var(--border-strong)',
        borderRadius: 'var(--r-sm)',
        padding: 24,
        fontFamily: 'Georgia, serif',
        minHeight: 400,
      }}>
        <div style={{ borderBottom: '2px solid #d4d4d4', paddingBottom: 12, marginBottom: 16 }}>
          <h2 style={{ margin: 0, fontFamily: 'Inter, sans-serif', fontSize: 22 }}>Ophamin Proof Bundle</h2>
          <div style={{ fontSize: 12, color: '#666', marginTop: 4, fontFamily: 'monospace' }}>{bundle.scenario} · {bundle.date} · {proof.proof_id.slice(0,16)}…</div>
        </div>
        <h3 style={{ fontFamily: 'Inter, sans-serif', fontSize: 16, color: '#0f8a6a' }}>Claim</h3>
        <p style={{ lineHeight: 1.6, color: '#333', fontSize: 14 }}>{proof.claim.statement}</p>
        <p style={{ fontSize: 13, color: '#555' }}><b>Threshold:</b> <code style={{ background: '#eef1f5', padding: '1px 6px', borderRadius: 3, fontSize: 12 }}>{proof.claim.threshold.metric} {proof.claim.threshold.comparator} {proof.claim.threshold.value}</code></p>
        <h3 style={{ fontFamily: 'Inter, sans-serif', fontSize: 16, color: '#0f8a6a' }}>Verdict: {bundle.verdict.toUpperCase()}</h3>
        <p style={{ lineHeight: 1.6, color: '#333', fontSize: 14 }}>{proof.verdict.reasoning}</p>
        <div style={{ textAlign: 'center', margin: 20, padding: 20, background: '#fff', border: '1px solid #ddd', borderRadius: 4 }}>
          <div style={{ fontFamily: 'monospace', fontSize: 11, color: '#999', textTransform: 'uppercase', letterSpacing: '0.1em' }}>FIGURE 1</div>
          <div style={{ fontSize: 11, color: '#666', marginTop: 4 }}>[ embedded matplotlib chart — assets/{bundle.scenario}-distribution.png ]</div>
        </div>
      </div>
    </div>
  );
}

// ----- TeX view -----
function TexView({ bundle, proof }) {
  const tex = `% Ophamin proof bundle — ${bundle.scenario}
% proof_id: ${proof.proof_id}
\\documentclass[11pt]{article}
\\usepackage{amsmath,amssymb,booktabs,siunitx}
\\title{Proof Bundle: ${bundle.scenario.replace(/-/g, '\\-')}}
\\author{Ophamin v${proof.identity.ophamin_version}}
\\date{${bundle.date}}
\\begin{document}
\\maketitle

\\section*{Claim}
${proof.claim.statement}

\\textbf{Threshold:} $\\texttt{${proof.claim.threshold.metric}} ${proof.claim.threshold.comparator === '<=' ? '\\leq' : proof.claim.threshold.comparator === '>=' ? '\\geq' : proof.claim.threshold.comparator} ${proof.claim.threshold.value}$ \\texttt{${proof.claim.threshold.units}}

\\textbf{H${'\\_'}0:} ${proof.claim.h0} \\\\
\\textbf{H${'\\_'}1:} ${proof.claim.h1}

\\section*{Verdict: \\textsc{${bundle.verdict}}}
Observed value: $${formatNum(bundle.observed)}$ \\texttt{${proof.claim.threshold.units}} \\\\
${proof.verdict.reasoning}

\\section*{Evidence}
\\begin{tabular}{llrrr}
\\toprule
Pillar & Statistic & Value & 95\\% CI & p \\\\
\\midrule
${proof.evidence.map(e => `\\texttt{${e.pillar}} & \\texttt{${e.statistic_name}} & ${formatNum(e.statistic_value)} & [${formatNum(e.ci_low)}, ${formatNum(e.ci_high)}] & ${e.p_value == null ? '\\textemdash' : e.p_value.toFixed(4)}`).join(' \\\\\n')} \\\\
\\bottomrule
\\end{tabular}

\\end{document}`;
  return (
    <div>
      <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 8 }}>
        <span className="mono" style={{ fontSize: 11, color: 'var(--text-muted)', flex: 1 }}>proof.tex · text/x-tex</span>
        <button className="btn ghost" style={{ fontSize: 11 }}><Icon name="copy" size={12}/> Copy</button>
        <button className="btn ghost" style={{ fontSize: 11 }}><Icon name="download" size={12}/> Download</button>
      </div>
      <pre style={{
        background: 'var(--bg-base)',
        border: '1px solid var(--border)',
        borderRadius: 'var(--r-sm)',
        padding: 16,
        fontFamily: 'JetBrains Mono, monospace',
        fontSize: 11,
        lineHeight: 1.65,
        color: 'var(--text-primary)',
        overflow: 'auto',
        margin: 0,
      }}>{tex.split('\n').map((line, i) => {
        const isComment = line.startsWith('%');
        const isCommand = line.match(/\\[a-zA-Z]+/g);
        return (
          <div key={i} style={{ display: 'flex' }}>
            <span style={{ width: 28, color: 'var(--text-faint)', textAlign: 'right', paddingRight: 12, userSelect: 'none' }}>{i+1}</span>
            <span style={{ color: isComment ? 'var(--text-muted)' : 'inherit', flex: 1, whiteSpace: 'pre-wrap' }}>
              {line.split(/(\\[a-zA-Z]+\*?|\\\\)/g).map((part, j) =>
                part.startsWith('') ? <span key={j} style={{ color: 'var(--viz-3)' }}>{part}</span> : part
              )}
            </span>
          </div>
        );
      })}</pre>
    </div>
  );
}

// ----- PDF view (mock iframe with page chrome) -----
function PdfView({ bundle, proof }) {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
        <span className="mono" style={{ fontSize: 11, color: 'var(--text-muted)', flex: 1 }}>proof.pdf · application/pdf · 1 page</span>
        <button className="btn ghost" style={{ fontSize: 11 }}><Icon name="download" size={12}/> Download</button>
      </div>
      <div style={{ background: '#3a3a3a', padding: 24, borderRadius: 'var(--r-sm)', display: 'grid', placeItems: 'center', minHeight: 480 }}>
        <div style={{
          width: '85%', maxWidth: 500, aspectRatio: '8.5/11',
          background: '#fff',
          color: '#1a1d21',
          padding: 28,
          fontFamily: 'Georgia, serif',
          fontSize: 10,
          boxShadow: '0 20px 60px rgba(0,0,0,0.5)',
          borderRadius: 1,
          overflow: 'hidden',
        }}>
          <div style={{ borderBottom: '1px solid #888', paddingBottom: 8, marginBottom: 10 }}>
            <div style={{ fontFamily: 'monospace', fontSize: 8, color: '#888' }}>OPHAMIN PROOF BUNDLE · v{proof.identity.ophamin_version}</div>
            <div style={{ fontSize: 14, fontWeight: 700, marginTop: 2, fontFamily: 'Inter, sans-serif' }}>{bundle.scenario}</div>
            <div style={{ fontFamily: 'monospace', fontSize: 7, color: '#666', marginTop: 2 }}>{proof.proof_id}</div>
          </div>
          <div style={{ fontSize: 8, lineHeight: 1.5, color: '#333' }}>
            <div style={{ fontWeight: 600, color: '#0f8a6a', marginBottom: 2 }}>CLAIM</div>
            {proof.claim.statement}
            <div style={{ fontWeight: 600, color: '#0f8a6a', margin: '8px 0 2px' }}>VERDICT: {bundle.verdict.toUpperCase()}</div>
            <div style={{ fontFamily: 'monospace', fontSize: 7, color: '#555' }}>observed: {formatNum(bundle.observed)} {proof.claim.threshold.units}</div>
            <div style={{
              marginTop: 8, padding: 8, background: '#f5f5f5', border: '1px solid #ddd',
              textAlign: 'center', fontFamily: 'monospace', fontSize: 7, color: '#888'
            }}>[ FIGURE: distribution chart with CI ]</div>
          </div>
        </div>
      </div>
    </div>
  );
}


// ─── VerifyView — cross-language verification snippets ──────────
function VerifyView({ bundle, proof }) {
  const [lang, setLang] = useProofState('python');
  const [verifying, setVerifying] = useProofState(false);
  const [verified, setVerified] = useProofState(null);

  const runVerify = () => {
    setVerifying(true);
    setVerified(null);
    setTimeout(() => {
      setVerifying(false);
      setVerified(true);
    }, 1100);
  };

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
      <div style={{
        background: 'var(--accent-soft)',
        border: '1px solid var(--accent-line)',
        borderLeft: '3px solid var(--accent)',
        borderRadius: 'var(--r-md)',
        padding: 14,
        display: 'flex',
        alignItems: 'center',
        gap: 12,
      }}>
        <Icon name="eye" size={16}/>
        <div style={{ flex: 1, fontSize: 12.5, color: 'var(--text-secondary)', lineHeight: 1.55 }}>
          This bundle is <b>content-addressed</b> (proof_id = sha256 of canonical body) and <b>HMAC-SHA256 signed</b> with the publication key. Verify it in any language — the wire format is normative per <span className="mono" style={{ color: 'var(--accent)' }}>SCHEMAS.md</span>.
        </div>
        <button className="btn primary" style={{ fontSize: 12 }} onClick={runVerify} disabled={verifying}>
          {verifying ? <><SixWheelsLoader size={14}/> Verifying…</> : verified ? <><Icon name="check" size={12}/> Verified</> : <><Icon name="eye" size={12}/> Verify here</>}
        </button>
      </div>

      {verified && (
        <div style={{
          background: 'var(--validated-bg)',
          border: '1px solid var(--validated-line)',
          borderRadius: 'var(--r-md)',
          padding: 12,
          display: 'grid',
          gridTemplateColumns: '140px 1fr',
          gap: '4px 12px',
          fontSize: 12,
        }}>
          <span className="micro" style={{ color: 'var(--validated)' }}>SIGNATURE</span>  <span className="mono tnum" style={{ fontSize: 11 }}>✓ matches publication HMAC key</span>
          <span className="micro" style={{ color: 'var(--validated)' }}>CONTENT HASH</span><span className="mono" style={{ fontSize: 10, wordBreak: 'break-all' }}>{proof.proof_id}</span>
          <span className="micro" style={{ color: 'var(--validated)' }}>CANONICAL FORM</span><span className="mono" style={{ fontSize: 11 }}>{(JSON.stringify(proof).length).toLocaleString()} bytes · UTF-8 · RFC 8785 JCS</span>
          <span className="micro" style={{ color: 'var(--validated)' }}>PREREG MATCH</span> <span className="mono" style={{ fontSize: 11 }}>config_hash + data_hash match prereg receipt</span>
        </div>
      )}

      <div>
        <div className="page-tabs" style={{ marginTop: 0, marginBottom: 12 }}>
          <div className={'page-tab' + (lang === 'python' ? ' active' : '')} onClick={() => setLang('python')}><Icon name="code" size={12}/> Python</div>
          <div className={'page-tab' + (lang === 'rust' ? ' active' : '')} onClick={() => setLang('rust')}><Icon name="code" size={12}/> Rust</div>
          <div className={'page-tab' + (lang === 'javascript' ? ' active' : '')} onClick={() => setLang('javascript')}><Icon name="code" size={12}/> JavaScript</div>
          <div className={'page-tab' + (lang === 'curl' ? ' active' : '')} onClick={() => setLang('curl')}><Icon name="code" size={12}/> curl</div>
          <div style={{ flex: 1 }}/>
          <button className="btn ghost" style={{ fontSize: 11 }}><Icon name="copy" size={12}/> Copy</button>
        </div>

        <pre style={{
          background: 'var(--bg-base)',
          border: '1px solid var(--border)',
          borderRadius: 'var(--r-sm)',
          padding: 16,
          fontFamily: 'JetBrains Mono, monospace',
          fontSize: 11.5,
          lineHeight: 1.65,
          margin: 0,
          overflow: 'auto',
        }}>
          {verifySnippet(lang, bundle, proof)}
        </pre>

        <div style={{ marginTop: 10, fontSize: 11, color: 'var(--text-muted)', display: 'flex', alignItems: 'center', gap: 8 }}>
          <Icon name="external" size={11}/>
          {lang === 'python' && <>Reference codec ships in <span className="mono">ophamin</span> package · Apache-2.0</>}
          {lang === 'rust' && <>Read-only verifier at <span className="mono">crates/ophamin-proof</span> · Apache-2.0 · pure-Rust, no Python dep</>}
          {lang === 'javascript' && <>Read-only verifier at <span className="mono">packages/ophamin-proof-js</span> · Apache-2.0 · zero deps</>}
          {lang === 'curl' && <>POSTs to your running <span className="mono">ophamin http serve</span> instance · verifies on the server side</>}
        </div>
      </div>

      <Section label="WIRE FORMAT GUARANTEES" icon="cpu">
        <ul style={{ fontSize: 12, color: 'var(--text-secondary)', lineHeight: 1.6, paddingLeft: 18, margin: 0 }}>
          <li><b>Canonical UTF-8</b> per RFC 8785 JCS — integer <span className="mono">30</span> emits as <span className="mono">30</span>, float <span className="mono">30.0</span> emits as <span className="mono">30.0</span>. Round-trip stable.</li>
          <li><b>NaN / Infinity rejected</b> — non-finite floats fail canonicalize, never silently coerced.</li>
          <li><b>proof_id = sha256(canonical_body)</b> — content-addressed; any byte mutation breaks the hash.</li>
          <li><b>signature = HMAC-SHA256(key, canonical_body)</b> — auth chain rooted in the publication key.</li>
          <li><b>9 sections always present</b> — identity, claim, preregistration, data, evidence, verdict, reproduction, provenance, signature. Missing-section refuses to verify.</li>
        </ul>
      </Section>
    </div>
  );
}

function verifySnippet(lang, bundle, proof) {
  const proofPath = 'proofs/' + bundle.path + '/proof.json';
  if (lang === 'python') {
    return `# pip install ophamin
from ophamin.measuring.proof import verify_proof_bytes
import pathlib

bundle  = pathlib.Path("${proofPath}")
proof   = bundle.read_bytes()
key_b64 = open(".ophamin/publication-key.b64").read().strip()

result = verify_proof_bytes(proof, sign_key_b64=key_b64)
assert result.verified, result.reason
print(f"\u2713  {result.proof_id[:16]}...  outcome={result.verdict.outcome}")
`;
  }
  if (lang === 'rust') {
    return `// Cargo.toml: ophamin-proof = "0.18"
use ophamin_proof::{verify_bytes, VerifyOptions};
use std::fs;

fn main() -> anyhow::Result<()> {
    let proof   = fs::read("${proofPath}")?;
    let key_b64 = fs::read_to_string(".ophamin/publication-key.b64")?
        .trim().to_string();

    let result = verify_bytes(&proof, VerifyOptions { sign_key_b64: Some(key_b64) })?;
    assert!(result.verified, "{}", result.reason);
    println!("\u2713  {}  outcome={}", &result.proof_id[..16], result.verdict.outcome);
    Ok(())
}
`;
  }
  if (lang === 'javascript') {
    return `// npm i @ophamin/proof
import { verifyBytes } from '@ophamin/proof';
import { readFile } from 'fs/promises';

const proof  = await readFile('${proofPath}');
const keyB64 = (await readFile('.ophamin/publication-key.b64', 'utf8')).trim();

const result = await verifyBytes(proof, { signKeyB64: keyB64 });
if (!result.verified) throw new Error(result.reason);
console.log(\`\u2713  \${result.proofId.slice(0,16)}...  outcome=\${result.verdict.outcome}\`);
`;
  }
  if (lang === 'curl') {
    return `# POST /verify on a running 'ophamin http serve' instance.
PROOF_JSON=$(cat ${proofPath})
curl -s -X POST http://localhost:8000/verify \\
  -H "Content-Type: application/json" \\
  -d "$(jq -n --arg p "$PROOF_JSON" '{proof_json: $p}')" \\
  | jq '{verified, proof_id, verdict: .verdict.outcome}'

# {
#   "verified": true,
#   "proof_id": "${bundle.proof_id.slice(0, 16)}...",
#   "verdict": "${bundle.verdict.toUpperCase()}"
# }
`;
  }
  return '';
}



// ─── PROV-O mini graph — agents · activities · entities ─────────
function ProvGraph({ proof }) {
  const W = 720, H = 280;
  const prov = proof.provenance || {};
  const agents     = Object.keys(prov.agent || {});
  const activities = Object.keys(prov.activity || {});
  const entities   = Object.keys(prov.entity || {});

  // Three columns: agents (left) → activities (center) → entities (right)
  const cols = [
    { x: 110, label: 'AGENT',    items: agents,     color: '#5e9eff' },
    { x: 360, label: 'ACTIVITY', items: activities, color: 'var(--accent)' },
    { x: 610, label: 'ENTITY',   items: entities,   color: '#ffa726' },
  ];

  // Place each node vertically centered in its column
  const positions = {};
  cols.forEach(col => {
    const n = col.items.length;
    const gap = (H - 80) / Math.max(1, n);
    col.items.forEach((id, i) => {
      positions[id] = { x: col.x, y: 50 + gap * (i + 0.5), color: col.color };
    });
  });

  // Edges from PROV-O relations
  const edges = [];
  function pushEdges(rel, label) {
    const r = prov[rel] || {};
    for (const [id, link] of Object.entries(r)) {
      const from = link['prov:agent'] || link['prov:activity'] || link['prov:generatedEntity'];
      const to   = link['prov:entity'] || link['prov:agent']    || link['prov:usedEntity'] || link['prov:activity'];
      if (from && to && positions[from] && positions[to]) {
        edges.push({ from, to, label });
      }
    }
  }
  pushEdges('used',              'used');
  pushEdges('wasAssociatedWith', 'assocWith');
  pushEdges('wasGeneratedBy',    'genBy');
  pushEdges('wasAttributedTo',   'attrTo');
  pushEdges('wasDerivedFrom',    'derivedFrom');

  function shortLabel(id) {
    return id.replace(/^ophamin:/, '').replace(/^corpus_/, 'corpus:').replace(/^scenario_/, 'scn:').replace(/^proof_/, 'proof:');
  }

  return (
    <div style={{ background: 'var(--bg-base)', border: '1px solid var(--border)', borderRadius: 'var(--r-sm)', padding: 12, overflow: 'hidden' }}>
      <svg viewBox={`0 0 ${W} ${H}`} width="100%" style={{ display: 'block' }}>
        {/* Column headers */}
        {cols.map(c => (
          <text key={c.label} x={c.x} y="22" textAnchor="middle" fontSize="9" letterSpacing="0.14em"
            fill="var(--text-muted)" fontFamily="JetBrains Mono">
            {c.label}
          </text>
        ))}
        {/* Edges */}
        {edges.map((e, i) => {
          const a = positions[e.from], b = positions[e.to];
          if (!a || !b) return null;
          const mx = (a.x + b.x) / 2;
          return (
            <g key={i}>
              <path d={`M ${a.x + 70} ${a.y} C ${mx} ${a.y} ${mx} ${b.y} ${b.x - 70} ${b.y}`}
                fill="none" stroke="var(--border-strong)" strokeWidth="1" opacity="0.6"/>
              <text x={mx} y={(a.y + b.y) / 2 - 4} textAnchor="middle"
                fontSize="9" fontFamily="JetBrains Mono" fill="var(--text-muted)" opacity="0.7">
                {e.label}
              </text>
            </g>
          );
        })}
        {/* Nodes */}
        {cols.map(col => col.items.map(id => {
          const pos = positions[id];
          const label = shortLabel(id);
          return (
            <g key={id}>
              <rect x={pos.x - 70} y={pos.y - 15} width="140" height="30" rx="4"
                fill="var(--bg-surface)" stroke={col.color} strokeWidth="1"/>
              <rect x={pos.x - 70} y={pos.y - 15} width="3" height="30" fill={col.color}/>
              <text x={pos.x - 60} y={pos.y + 4} fontSize="10.5" fontFamily="Inter, sans-serif"
                fill="var(--text-primary)">
                {label.length > 18 ? label.slice(0, 17) + '…' : label}
              </text>
            </g>
          );
        }))}
      </svg>
      <div style={{ display: 'flex', gap: 14, marginTop: 8, fontSize: 11 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}><span style={{ width: 8, height: 8, background: '#5e9eff', borderRadius: 2 }}/>agent</div>
        <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}><span style={{ width: 8, height: 8, background: 'var(--accent)', borderRadius: 2 }}/>activity</div>
        <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}><span style={{ width: 8, height: 8, background: '#ffa726', borderRadius: 2 }}/>entity</div>
        <span style={{ flex: 1 }}/>
        <span className="mono" style={{ fontSize: 10, color: 'var(--text-muted)' }}>{agents.length + activities.length + entities.length} nodes · {edges.length} edges</span>
        <button className="btn ghost" style={{ fontSize: 11 }}><Icon name="download" size={11}/> PROV-JSON</button>
      </div>
    </div>
  );
}



function FormatsMenu({ tab, onTab }) {
  const [open, setOpen] = useProofState(false);
  const fmts = [
    { id: 'json', label: 'JSON',  desc: 'Collapsible syntax-highlighted tree' },
    { id: 'md',   label: 'MD',    desc: 'Rendered markdown with embedded chart' },
    { id: 'html', label: 'HTML',  desc: 'Inline academic-grade rendering' },
    { id: 'tex',  label: 'TeX',   desc: 'LaTeX source · copy-ready' },
    { id: 'pdf',  label: 'PDF',   desc: 'Print-ready page · 1 page' },
  ];
  const active = fmts.find(f => f.id === tab);
  return (
    <div style={{ position: 'relative', display: 'inline-flex', marginLeft: 'auto', alignSelf: 'center' }}>
      <button className={'tab' + (active ? ' active' : '')}
        onClick={() => setOpen(o => !o)}
        style={{ display: 'inline-flex', alignItems: 'center', gap: 4 }}>
        {active ? active.label : 'Formats'} <Icon name="chevronD" size={11}/>
      </button>
      {open && (
        <>
          <div style={{ position: 'fixed', inset: 0, zIndex: 9 }} onClick={() => setOpen(false)}/>
          <div style={{
            position: 'absolute',
            top: '100%', right: 0,
            marginTop: 2,
            minWidth: 240,
            background: 'var(--bg-elevated)',
            border: '1px solid var(--border-strong)',
            borderRadius: 'var(--r-md)',
            boxShadow: 'var(--shadow-pop)',
            zIndex: 10,
            overflow: 'hidden',
            animation: 'dropdownIn 180ms cubic-bezier(0.16, 1, 0.3, 1)',
          }}>
            <div className="micro" style={{ padding: '8px 12px', borderBottom: '1px solid var(--border)', background: 'var(--bg-card-head)' }}>RAW FORMATS</div>
            {fmts.map(f => (
              <div key={f.id}
                onClick={() => { onTab(f.id); setOpen(false); }}
                style={{
                  padding: '8px 12px',
                  cursor: 'pointer',
                  borderBottom: '1px solid var(--border)',
                  background: tab === f.id ? 'var(--accent-soft)' : 'transparent',
                }}>
                <div className="mono" style={{ fontSize: 12, fontWeight: 600, color: tab === f.id ? 'var(--accent)' : 'var(--text-primary)' }}>{f.label}</div>
                <div style={{ fontSize: 11, color: 'var(--text-muted)' }}>{f.desc}</div>
              </div>
            ))}
          </div>
        </>
      )}
    </div>
  );
}

function FormatTabPicker({ tab, onTab }) {
  const [open, setOpen] = useProofState(false);
  const FORMATS = [
    { id: 'json', label: 'JSON', hint: 'collapsible tree' },
    { id: 'md',   label: 'MD',   hint: 'rendered markdown + chart' },
    { id: 'html', label: 'HTML', hint: 'iframe preview' },
    { id: 'tex',  label: 'TeX',  hint: 'LaTeX source' },
    { id: 'pdf',  label: 'PDF',  hint: 'page preview' },
  ];
  const isFormat = FORMATS.some(f => f.id === tab);
  const current = FORMATS.find(f => f.id === tab);
  return (
    <div style={{ position: 'relative', marginRight: 8 }}>
      <button className={'tab' + (isFormat ? ' active' : '')} onClick={() => setOpen(o => !o)}
        style={{ display: 'inline-flex', alignItems: 'center', gap: 6 }}>
        <span>{isFormat ? current.label : 'Formats'}</span>
        <Icon name={open ? 'chevronU' : 'chevronD'} size={11}/>
      </button>
      {open && (
        <>
          <div style={{ position: 'fixed', inset: 0, zIndex: 9 }} onClick={() => setOpen(false)}/>
          <div style={{
            position: 'absolute',
            top: 'calc(100% + 4px)',
            right: 0,
            background: 'var(--bg-elevated)',
            border: '1px solid var(--border-strong)',
            borderRadius: 'var(--r-md)',
            boxShadow: 'var(--shadow-pop)',
            minWidth: 200,
            zIndex: 10,
            padding: 4,
          }}>
            {FORMATS.map(f => (
              <div key={f.id}
                onClick={() => { onTab(f.id); setOpen(false); }}
                style={{
                  padding: '8px 10px',
                  borderRadius: 'var(--r-sm)',
                  cursor: 'pointer',
                  background: tab === f.id ? 'var(--accent-soft)' : 'transparent',
                  color: tab === f.id ? 'var(--accent)' : 'var(--text-primary)',
                  display: 'flex',
                  alignItems: 'center',
                  gap: 8,
                }}>
                <span style={{ fontFamily: 'JetBrains Mono, monospace', fontSize: 11, fontWeight: 600, width: 38 }}>{f.label}</span>
                <span style={{ fontSize: 11, color: 'var(--text-muted)' }}>{f.hint}</span>
              </div>
            ))}
          </div>
        </>
      )}
    </div>
  );
}

window.ProofsScreen = ProofsScreen;