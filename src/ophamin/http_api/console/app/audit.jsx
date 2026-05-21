/** @jsxRuntime classic */ /** @jsx React.createElement */
/* global React, OPHAMIN, Icon */
// Audit — the auditing/ wheel: 12-tool static-analysis orchestrator.

const { useState: useAuState, useMemo: useAuMemo } = React;

const TOOLS = [
  { id: 'ruff',         lang: 'Python', kind: 'lint',        version: '0.15.13', status: 'ok',       findings: 0,   ms: 412,  desc: 'Fast Python linter; superset of pyflakes/isort/pycodestyle.' },
  { id: 'bandit',       lang: 'Python', kind: 'security',    version: '1.9.4',   status: 'ok',       findings: 0,   ms: 1834, desc: 'AST-based common Python security issue scanner.' },
  { id: 'mypy',         lang: 'Python', kind: 'types',       version: '2.1.0',   status: 'ok',       findings: 0,   ms: 8421, desc: 'Static type checker, --strict mode.' },
  { id: 'vulture',      lang: 'Python', kind: 'dead code',   version: '2.16',    status: 'warn',     findings: 3,   ms: 612,  desc: 'Find dead Python code (unused imports/functions/vars).' },
  { id: 'radon',        lang: 'Python', kind: 'complexity',  version: '6.0.1',   status: 'warn',     findings: 7,   ms: 281,  desc: 'Cyclomatic complexity + maintainability index.' },
  { id: 'pip-audit',    lang: 'Python', kind: 'supply chain',version: '2.10.0',  status: 'ok',       findings: 0,   ms: 3110, desc: 'Audit dependencies against PyPI Advisory Database.' },
  { id: 'deptry',       lang: 'Python', kind: 'dependencies',version: '0.25.1',  status: 'ok',       findings: 0,   ms: 224,  desc: 'Detect unused/missing/transitive dependencies.' },
  { id: 'fawltydeps',   lang: 'Python', kind: 'dependencies',version: '0.20.0',  status: 'ok',       findings: 0,   ms: 318,  desc: 'Find undeclared/unused dependencies via import graph.' },
  { id: 'interrogate',  lang: 'Python', kind: 'docs',        version: '1.7.0',   status: 'warn',     findings: 12,  ms: 134,  desc: 'Docstring coverage analyzer.' },
  { id: 'pylint',       lang: 'Python', kind: 'lint',        version: '4.0.5',   status: 'warn',     findings: 4,   ms: 5621, desc: 'Comprehensive Python linter; slower, deeper than ruff.' },
  { id: 'refurb',       lang: 'Python', kind: 'modernize',   version: '2.3.1',   status: 'ok',       findings: 0,   ms: 423,  desc: 'Suggest more idiomatic refactors using modern Python.' },
  { id: 'prospector',   lang: 'Python', kind: 'lint',        version: '1.18.0',  status: 'ok',       findings: 0,   ms: 4912, desc: 'Meta-tool — runs pylint/pyflakes/mccabe/dodgy under one roof.' },
];

// Synthesized findings — match the warn-status counts above
const FINDINGS = [
  { tool: 'vulture',     severity: 'low',    rule: 'V100',     file: 'src/ophamin/seeing/discovery/__init__.py',    line: 47,  msg: "unused import 'json' (3% confidence)" },
  { tool: 'vulture',     severity: 'low',    rule: 'V102',     file: 'src/ophamin/instrumenting/periodic_sampler.py', line: 124, msg: "unused variable 'prev_rss'" },
  { tool: 'vulture',     severity: 'low',    rule: 'V103',     file: 'src/ophamin/measuring/pillars/observability.py', line: 218, msg: "unused function '_legacy_drift_check'" },
  { tool: 'radon',       severity: 'medium', rule: 'CC-C',     file: 'src/ophamin/measuring/scenarios/concentrated_immune_siege.py', line: 88,  msg: "score() has cyclomatic complexity 14 (C grade)" },
  { tool: 'radon',       severity: 'medium', rule: 'CC-C',     file: 'src/ophamin/seeing/wiring/probe.py',           line: 156, msg: "classify_orphans() has cyclomatic complexity 13 (C grade)" },
  { tool: 'radon',       severity: 'medium', rule: 'CC-D',     file: 'src/ophamin/comparing/drift/delta_report.py',  line: 201, msg: "compute_delta() has cyclomatic complexity 19 (D grade)" },
  { tool: 'radon',       severity: 'low',    rule: 'MI',       file: 'src/ophamin/comparing/drift/delta_report.py', line: 0,   msg: "maintainability index 64 (B grade)" },
  { tool: 'radon',       severity: 'low',    rule: 'CC-B',     file: 'src/ophamin/auditing/orchestrate.py',          line: 312, msg: "_collect_findings() has cyclomatic complexity 10 (B grade)" },
  { tool: 'radon',       severity: 'low',    rule: 'CC-B',     file: 'src/ophamin/reporting/html.py',                line: 89,  msg: "render_proof_html() has cyclomatic complexity 9 (B grade)" },
  { tool: 'radon',       severity: 'low',    rule: 'CC-B',     file: 'src/ophamin/measuring/proof/__init__.py',      line: 412, msg: "verify_proof_bytes() has cyclomatic complexity 11 (B grade)" },
  { tool: 'interrogate', severity: 'low',    rule: 'I001',     file: 'src/ophamin/measuring/scenarios/sinew_conservation.py', line: 0, msg: "docstring coverage 67% on module" },
  { tool: 'interrogate', severity: 'low',    rule: 'I001',     file: 'src/ophamin/seeing/telemetry/scrape.py',        line: 0, msg: "docstring coverage 72% on module" },
  { tool: 'interrogate', severity: 'low',    rule: 'I001',     file: 'src/ophamin/comparing/crdt_state.py',           line: 0, msg: "docstring coverage 58% on module" },
  { tool: 'pylint',      severity: 'low',    rule: 'C0301',    file: 'src/ophamin/measuring/scenarios/base.py',      line: 482, msg: 'line too long (102 / 100 chars)' },
  { tool: 'pylint',      severity: 'medium', rule: 'R0913',    file: 'src/ophamin/measuring/scenarios/base.py',      line: 178, msg: '__init__ takes 9 args (max 7)' },
  { tool: 'pylint',      severity: 'low',    rule: 'W0613',    file: 'src/ophamin/agentic/agents/triage.py',          line: 64,  msg: "unused argument 'temperature'" },
  { tool: 'pylint',      severity: 'medium', rule: 'R0911',    file: 'src/ophamin/measuring/scenarios/anova_crosscheck.py', line: 240, msg: 'too many return statements (8)' },
];

function AuditScreen() {
  const [filterTool, setFilterTool] = useAuState('all');
  const [filterSeverity, setFilterSeverity] = useAuState('all');
  const [selected, setSelected] = useAuState(FINDINGS[0]);

  const findings = useAuMemo(() => {
    let r = FINDINGS;
    if (filterTool !== 'all')     r = r.filter(f => f.tool === filterTool);
    if (filterSeverity !== 'all') r = r.filter(f => f.severity === filterSeverity);
    return r;
  }, [filterTool, filterSeverity]);

  const totals = useAuMemo(() => ({
    findings: FINDINGS.length,
    high:     FINDINGS.filter(f => f.severity === 'high').length,
    medium:   FINDINGS.filter(f => f.severity === 'medium').length,
    low:      FINDINGS.filter(f => f.severity === 'low').length,
    tools_ok: TOOLS.filter(t => t.status === 'ok').length,
    tools_warn: TOOLS.filter(t => t.status === 'warn').length,
    total_ms: TOOLS.reduce((a, t) => a + t.ms, 0),
  }), []);

  return (
    <div className="content-inner page">
      <div className="page-header">
        <div>
          <h1 className="page-title">Audit</h1>
          <div className="page-subtitle">Twelve static-analysis tools, run together. Every finding signed; every export traceable.</div>
        </div>
        <div className="page-actions">
          <span className="live-pill ok">
            <span className="dot"></span>
            no HIGH findings
          </span>
          <button className="btn"><Icon name="refresh" size={13}/> Re-run audit</button>
          <button className="btn primary"><Icon name="external" size={13}/> Export SARIF</button>
        </div>
      </div>

      {/* Per-tool tile strip */}
      <div className="audit-tools">
        {TOOLS.map(t => (
          <div key={t.id} className={'audit-tool audit-tool-' + t.status}
            onClick={() => setFilterTool(filterTool === t.id ? 'all' : t.id)}
            data-active={filterTool === t.id}>
            <div className="audit-tool-row">
              <span className={'audit-tool-dot audit-tool-dot-' + t.status}/>
              <span className="mono" style={{ fontSize: 12, fontWeight: 600 }}>{t.id}</span>
              <span style={{ marginLeft: 'auto', fontSize: 11, color: t.findings > 0 ? 'var(--inconclusive)' : 'var(--validated)', fontFamily: 'JetBrains Mono, monospace', fontWeight: 600 }}>
                {t.findings}
              </span>
            </div>
            <div className="audit-tool-meta mono">
              <span style={{ color: 'var(--text-muted)' }}>{t.kind}</span>
              <span style={{ color: 'var(--text-faint)' }}>·</span>
              <span style={{ color: 'var(--text-muted)' }}>v{t.version}</span>
            </div>
            <div className="audit-tool-bar">
              <div style={{ height: '100%', width: `${Math.min(100, t.ms / 100)}%`, background: t.status === 'warn' ? 'var(--inconclusive)' : 'var(--validated)', opacity: 0.6 }}/>
              <span className="mono" style={{ position: 'absolute', right: 4, top: -1, fontSize: 9, color: 'var(--text-muted)' }}>{t.ms}ms</span>
            </div>
          </div>
        ))}
      </div>

      {/* Filter bar */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 12, margin: '16px 0 12px' }}>
        <div className="toggle-group">
          <button className={filterSeverity === 'all' ? 'active' : ''}    onClick={() => setFilterSeverity('all')}>All severities <span className="mono faint" style={{ marginLeft: 4 }}>{totals.findings}</span></button>
          <button className={filterSeverity === 'high' ? 'active' : ''}   onClick={() => setFilterSeverity('high')}   style={filterSeverity === 'high' ? { color: 'var(--refuted)', background: 'var(--refuted-bg)' } : null}>High <span className="mono faint" style={{ marginLeft: 4 }}>{totals.high}</span></button>
          <button className={filterSeverity === 'medium' ? 'active' : ''} onClick={() => setFilterSeverity('medium')} style={filterSeverity === 'medium' ? { color: 'var(--inconclusive)', background: 'var(--inconclusive-bg)' } : null}>Medium <span className="mono faint" style={{ marginLeft: 4 }}>{totals.medium}</span></button>
          <button className={filterSeverity === 'low' ? 'active' : ''}    onClick={() => setFilterSeverity('low')}>Low <span className="mono faint" style={{ marginLeft: 4 }}>{totals.low}</span></button>
        </div>
        <div style={{ flex: 1 }}/>
        {filterTool !== 'all' && (
          <div className="chip" style={{ color: 'var(--accent)', borderColor: 'var(--accent-line)', background: 'var(--accent-soft)' }}>
            tool = {filterTool}
            <span onClick={() => setFilterTool('all')} style={{ cursor: 'pointer', marginLeft: 6, color: 'var(--text-muted)' }}>×</span>
          </div>
        )}
        <span className="mono" style={{ fontSize: 11, color: 'var(--text-muted)' }}>{findings.length} of {totals.findings} findings</span>
      </div>

      {/* Findings split: table + detail */}
      <div className="split" style={{ minHeight: 460 }}>
        <div className="card" style={{ overflow: 'hidden', display: 'flex', flexDirection: 'column' }}>
          <div style={{ overflow: 'auto', flex: 1 }}>
            <table className="table table-dense">
              <thead>
                <tr>
                  <th style={{ width: 70 }}>Severity</th>
                  <th style={{ width: 90 }}>Tool</th>
                  <th style={{ width: 60 }}>Rule</th>
                  <th>File · line</th>
                </tr>
              </thead>
              <tbody>
                {findings.map((f, i) => (
                  <tr key={i}
                    className={selected === f ? 'selected' : ''}
                    onClick={() => setSelected(f)}>
                    <td><SeverityPill sev={f.severity}/></td>
                    <td className="mono" style={{ fontSize: 11 }}>{f.tool}</td>
                    <td className="mono" style={{ fontSize: 11, color: 'var(--accent)' }}>{f.rule}</td>
                    <td className="mono" style={{ fontSize: 11, color: 'var(--text-secondary)' }}>{f.file}<span style={{ color: 'var(--text-muted)' }}>{f.line ? `:${f.line}` : ''}</span></td>
                  </tr>
                ))}
                {findings.length === 0 && (
                  <tr><td colSpan="4">
                    <div style={{ padding: '36px 20px', textAlign: 'center' }}>
                      <Icon name="check" size={24}/>
                      <div style={{ fontSize: 14, fontWeight: 600, marginTop: 8 }}>Clean</div>
                      <div style={{ fontSize: 12, color: 'var(--text-muted)' }}>No findings match these filters.</div>
                    </div>
                  </td></tr>
                )}
              </tbody>
            </table>
          </div>
          <div className="table-footer">
            <span className="mono" style={{ fontSize: 11, color: 'var(--text-muted)' }}>SARIF 2.1.0 ready · normalized across all tools</span>
            <button className="link-btn"><Icon name="download" size={11}/> Export filtered</button>
          </div>
        </div>

        <div className="card" style={{ overflow: 'hidden', display: 'flex', flexDirection: 'column' }}>
          {selected ? <FindingDetail finding={selected}/> : <div className="empty">Select a finding</div>}
        </div>
      </div>

      {/* Interop export footer */}
      <div style={{ marginTop: 16, display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 12 }}>
        <ExportTile name="SARIF 2.1.0"  target="VS Code · GitHub Code Scanning" icon="external"/>
        <ExportTile name="JUnit XML"    target="Jenkins · GitHub Actions"      icon="external"/>
        <ExportTile name="MLflow"       target="MLflow tracking server"        icon="external"/>
        <ExportTile name="CycloneDX 1.5"target="Dependency-Track · Snyk"        icon="external"/>
      </div>
    </div>
  );
}

function SeverityPill({ sev }) {
  const map = {
    high:   { color: 'var(--refuted)',     bg: 'var(--refuted-bg)',     line: 'var(--refuted-line)' },
    medium: { color: 'var(--inconclusive)', bg: 'var(--inconclusive-bg)', line: 'var(--inconclusive-line)' },
    low:    { color: 'var(--text-secondary)', bg: 'var(--bg-surface-2)', line: 'var(--border)' },
  };
  const m = map[sev];
  return (
    <span style={{
      display: 'inline-flex', alignItems: 'center', gap: 5,
      padding: '1px 7px',
      fontSize: 10, fontWeight: 600,
      letterSpacing: '0.04em', textTransform: 'uppercase',
      color: m.color, background: m.bg, border: '1px solid ' + m.line,
      borderRadius: 'var(--r-full)',
    }}>
      <span style={{ width: 5, height: 5, borderRadius: '50%', background: m.color }}/>
      {sev}
    </span>
  );
}

function FindingDetail({ finding }) {
  const tool = TOOLS.find(t => t.id === finding.tool);
  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100%' }}>
      <div style={{
        padding: '14px 18px',
        borderBottom: '1px solid var(--border)',
        background: 'var(--bg-card-head)',
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 8 }}>
          <SeverityPill sev={finding.severity}/>
          <span className="mono" style={{ fontSize: 11, color: 'var(--text-muted)' }}>{finding.tool} · {finding.rule}</span>
          <span style={{ flex: 1 }}/>
          <button className="btn ghost icon" title="Copy"><Icon name="copy" size={12}/></button>
          <button className="btn ghost icon" title="Open in editor"><Icon name="external" size={12}/></button>
        </div>
        <div style={{ fontSize: 14, color: 'var(--text-primary)', fontWeight: 500, lineHeight: 1.4 }}>{finding.msg}</div>
        <div className="mono" style={{ fontSize: 11, color: 'var(--accent)', marginTop: 6 }}>
          {finding.file}{finding.line ? `:${finding.line}` : ''}
        </div>
      </div>

      <div style={{ padding: 18, flex: 1, overflowY: 'auto' }}>
        <div className="micro" style={{ marginBottom: 8 }}>RULE</div>
        <div style={{ fontSize: 12, color: 'var(--text-secondary)', lineHeight: 1.6 }}>
          <span className="mono" style={{ color: 'var(--accent)' }}>{finding.rule}</span> — {ruleDescription(finding.rule, finding.tool)}
        </div>

        <div className="micro" style={{ margin: '16px 0 8px' }}>SOURCE CONTEXT</div>
        <pre style={{
          background: 'var(--bg-base)',
          border: '1px solid var(--border)',
          borderRadius: 'var(--r-sm)',
          padding: 12,
          fontFamily: 'JetBrains Mono, monospace',
          fontSize: 11.5,
          lineHeight: 1.65,
          margin: 0,
          color: 'var(--text-secondary)',
          overflowX: 'auto',
        }}>{sourceContext(finding)}</pre>

        <div className="micro" style={{ margin: '16px 0 8px' }}>TOOL</div>
        {tool && (
          <div style={{ display: 'grid', gridTemplateColumns: '110px 1fr', gap: '4px 12px', fontSize: 12 }}>
            <span className="mono faint">name</span>    <span className="mono">{tool.id}</span>
            <span className="mono faint">version</span> <span className="mono">{tool.version}</span>
            <span className="mono faint">kind</span>    <span>{tool.kind}</span>
            <span className="mono faint">desc</span>    <span style={{ color: 'var(--text-secondary)' }}>{tool.desc}</span>
          </div>
        )}

        <div className="micro" style={{ margin: '16px 0 8px' }}>ACTIONS</div>
        <div style={{ display: 'flex', gap: 6 }}>
          <button className="btn primary" style={{ fontSize: 12 }}><Icon name="check" size={12}/> Mark as triaged</button>
          <button className="btn" style={{ fontSize: 12 }}><Icon name="x" size={12}/> Suppress (--noqa)</button>
          <button className="btn" style={{ fontSize: 12 }}><Icon name="external" size={12}/> Open in VS Code</button>
        </div>
      </div>
    </div>
  );
}

function ruleDescription(rule, tool) {
  const map = {
    'V100': 'Unused import. Vulture flags dead imports; verify with --min-confidence to filter noise.',
    'V102': 'Unused local variable. May be intentional (e.g. _ prefix); rename or remove.',
    'V103': 'Unused function. Check call sites and reflection paths before deletion.',
    'CC-C': 'Cyclomatic complexity in C grade (11–20). Consider extract-method refactor.',
    'CC-D': 'Cyclomatic complexity in D grade (21–30). High maintenance risk; refactor recommended.',
    'CC-B': 'Cyclomatic complexity in B grade (6–10). Acceptable, watch for growth.',
    'MI':   'Maintainability index. Below 65 indicates rising long-term cost.',
    'I001': 'Docstring coverage below threshold for module.',
    'C0301':'Line too long. Project max is 100 chars (per pyproject).',
    'R0913':'Too many arguments. Consider builder or dataclass.',
    'W0613':'Unused argument. Rename to _ prefix or remove.',
    'R0911':'Too many return statements. Consider early-return guard pattern.',
  };
  return map[rule] || `${tool} rule.`;
}

function sourceContext(f) {
  // Mocked source preview
  const lineNo = f.line || 1;
  const before = lineNo - 2 > 0 ? lineNo - 2 : 1;
  const lines = [];
  for (let i = before; i <= lineNo + 2; i++) {
    const isHit = i === lineNo;
    const text = isHit ? sampleHitLine(f) : i < lineNo ? '    # …' : '';
    lines.push(`${String(i).padStart(4)}  ${isHit ? '▶' : ' '}  ${text}`);
  }
  return lines.join('\n');
}

function sampleHitLine(f) {
  if (f.rule === 'V100') return 'import json  # ← unused';
  if (f.rule === 'V102') return 'prev_rss = self._sample()  # ← never read';
  if (f.rule === 'V103') return 'def _legacy_drift_check(self, …):';
  if (f.rule.startsWith('CC-')) return 'def compute_delta(self, a, b, …):  # complexity = high';
  if (f.rule === 'C0301') return '                            result = something_long_that_exceeds_the_line_limit(...)';
  if (f.rule === 'R0913') return 'def __init__(self, name, tier, family, target, corpus, claim, …):';
  if (f.rule === 'W0613') return 'def run(self, prompt, *, temperature=0.0):';
  if (f.rule === 'R0911') return 'if cond1: return a; elif cond2: return b; …  # 8 returns';
  if (f.rule === 'I001') return '"""Module docstring."""  # coverage 67%';
  return '<offending line>';
}

function ExportTile({ name, target, icon }) {
  return (
    <div style={{
      padding: 12,
      background: 'var(--bg-surface)',
      border: '1px solid var(--border)',
      borderRadius: 'var(--r-md)',
      cursor: 'pointer',
      transition: 'border-color var(--d-fast) var(--ease)',
    }}
    onMouseEnter={e => e.currentTarget.style.borderColor = 'var(--accent-line)'}
    onMouseLeave={e => e.currentTarget.style.borderColor = 'var(--border)'}>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
        <div className="mono" style={{ fontSize: 12, fontWeight: 600, color: 'var(--text-primary)' }}>{name}</div>
        <Icon name={icon} size={13}/>
      </div>
      <div style={{ fontSize: 11, color: 'var(--text-muted)', marginTop: 4 }}>{target}</div>
    </div>
  );
}

function DisciplineCard({ title, status, count, of, desc }) {
  return (
    <div className={'discipline-card status-' + status}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
        <span className={'discipline-icon discipline-' + status}>
          <Icon name={status === 'ok' ? 'check' : 'x'} size={11}/>
        </span>
        <span style={{ fontSize: 13, fontWeight: 600 }}>{title}</span>
        <span style={{ flex: 1 }}/>
        <span className="mono tnum" style={{ fontSize: 18, color: status === 'ok' ? 'var(--validated)' : 'var(--refuted)', fontWeight: 600 }}>{count}</span>
        <span className="mono" style={{ fontSize: 10, color: 'var(--text-muted)' }}>{of}</span>
      </div>
      <div style={{ fontSize: 11.5, color: 'var(--text-secondary)', lineHeight: 1.55, marginTop: 8 }}>{desc}</div>
    </div>
  );
}

window.AuditScreen = AuditScreen;
