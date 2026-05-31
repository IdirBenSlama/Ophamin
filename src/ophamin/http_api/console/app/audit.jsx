/** @jsxRuntime classic */ /** @jsx React.createElement */
/* global React, Icon */
// Audit — the auditing/ wheel: a 12-tool static-analysis orchestrator.
//
// NO FABRICATION (2026-05-31): live findings, per-tool stats, source previews
// and signed audit records are produced by the `auditing/` orchestrator
// (runner.py — CLI/programmatic) and are NOT yet wired into the console over
// HTTP. This screen shows the real tool catalogue + export formats as
// reference, with an honest "not wired" state — it used to synthesize findings
// (fake files, line numbers, versions, timings, mocked source). All removed.

const TOOLS = [
  { id: 'ruff',        lang: 'Python', kind: 'lint',         desc: 'Fast Python linter; superset of pyflakes/isort/pycodestyle.' },
  { id: 'bandit',      lang: 'Python', kind: 'security',     desc: 'AST-based common Python security issue scanner.' },
  { id: 'mypy',        lang: 'Python', kind: 'types',        desc: 'Static type checker, --strict mode.' },
  { id: 'vulture',     lang: 'Python', kind: 'dead code',    desc: 'Find dead Python code (unused imports/functions/vars).' },
  { id: 'radon',       lang: 'Python', kind: 'complexity',   desc: 'Cyclomatic complexity + maintainability index.' },
  { id: 'pip-audit',   lang: 'Python', kind: 'supply chain', desc: 'Audit dependencies against the PyPI Advisory Database.' },
  { id: 'deptry',      lang: 'Python', kind: 'dependencies', desc: 'Detect unused/missing/transitive dependencies.' },
  { id: 'fawltydeps',  lang: 'Python', kind: 'dependencies', desc: 'Find undeclared/unused dependencies via the import graph.' },
  { id: 'interrogate', lang: 'Python', kind: 'docs',         desc: 'Docstring coverage analyzer.' },
  { id: 'pylint',      lang: 'Python', kind: 'lint',         desc: 'Comprehensive Python linter; slower, deeper than ruff.' },
  { id: 'refurb',      lang: 'Python', kind: 'modernize',    desc: 'Suggest more idiomatic refactors using modern Python.' },
  { id: 'prospector',  lang: 'Python', kind: 'lint',         desc: 'Meta-tool — runs pylint/pyflakes/mccabe/dodgy under one roof.' },
];

const EXPORT_FORMATS = [
  { name: 'SARIF 2.1.0',   target: 'VS Code · GitHub Code Scanning' },
  { name: 'JUnit XML',     target: 'Jenkins · GitHub Actions' },
  { name: 'MLflow',        target: 'MLflow tracking server' },
  { name: 'CycloneDX 1.5', target: 'Dependency-Track · Snyk' },
];

function AuditScreen() {
  return (
    <div className="content-inner page">
      <div className="page-header">
        <div>
          <h1 className="page-title">Audit</h1>
          <div className="page-subtitle">The auditing wheel — twelve static-analysis tools, orchestrated together, each finding signed into an audit record.</div>
        </div>
      </div>

      <div className="agent-banner">
        <Icon name="cpu" size={16}/>
        <div>
          Live findings + signed audit records are produced by the <span className="mono">auditing/</span> orchestrator
          (<span className="mono">runner.py</span>, CLI/programmatic) and are <b>not wired into the console over HTTP yet</b>.
          This screen shows the real tool catalogue; it does not synthesize findings. A read-only <span className="mono">/auditing</span>
          endpoint would surface real results here.
        </div>
      </div>

      <div className="card" style={{ overflow: 'hidden', marginTop: 4 }}>
        <div className="card-header">
          <div className="card-title">Tool catalogue</div>
          <span className="chip">{TOOLS.length} tools</span>
        </div>
        <div style={{ padding: 14, display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(290px, 1fr))', gap: 8 }}>
          {TOOLS.map(t => (
            <div key={t.id} style={{ border: '1px solid var(--border)', borderRadius: 'var(--r-sm)', padding: '10px 12px' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                <span className="mono" style={{ fontSize: 12.5, fontWeight: 600, color: 'var(--text-primary)' }}>{t.id}</span>
                <span className="micro" style={{ marginLeft: 'auto' }}>{t.lang} · {t.kind}</span>
              </div>
              <div style={{ fontSize: 11.5, color: 'var(--text-muted)', marginTop: 4, lineHeight: 1.5 }}>{t.desc}</div>
            </div>
          ))}
        </div>
      </div>

      <div className="card" style={{ marginTop: 14, padding: 18 }}>
        <div className="card-title" style={{ marginBottom: 6 }}>Export formats</div>
        <div style={{ fontSize: 12.5, color: 'var(--text-muted)', marginBottom: 12 }}>
          The orchestrator normalizes findings across all tools and emits these via the CLI — not from the console yet.
        </div>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(220px, 1fr))', gap: 10 }}>
          {EXPORT_FORMATS.map(f => (
            <div key={f.name} style={{ border: '1px solid var(--border)', borderRadius: 'var(--r-sm)', padding: '10px 12px' }}>
              <div className="mono" style={{ fontSize: 12, fontWeight: 600 }}>{f.name}</div>
              <div style={{ fontSize: 11, color: 'var(--text-muted)', marginTop: 3 }}>{f.target}</div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

window.AuditScreen = AuditScreen;
