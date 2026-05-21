/** @jsxRuntime classic */ /** @jsx React.createElement */
/* global React, OPHAMIN, Icon */
// Interop — the interop/ wheel. Standard-format export connectors:
// SARIF · JUnit XML · MLflow · CycloneDX. Mirrors `ophamin export` CLI.

const { useState: useInState } = React;

const EXPORTERS = [
  {
    id: 'sarif',
    name: 'SARIF 2.1.0',
    consumers: 'VS Code · GitHub Code Scanning · Sonarqube',
    purpose: 'Audit findings as a standard static-analysis result format. Drops into the SARIF Viewer extension; uploads to GitHub Security tab.',
    icon: 'audit',
    color: '#94a3b8',
    sample: `{
  "version": "2.1.0",
  "runs": [{
    "tool": { "driver": { "name": "ophamin-audit", "version": "0.64.1" } },
    "results": [
      {
        "ruleId": "vulture/dead-code",
        "level": "warning",
        "message": { "text": "unused function 'legacy_handler'" },
        "locations": [{ "physicalLocation": {
          "artifactLocation": { "uri": "src/ophamin/legacy.py" },
          "region": { "startLine": 142 } }}]
      }
    ]
  }]
}`,
    cli: 'ophamin export audit.json --format sarif > audit.sarif',
  },
  {
    id: 'junit',
    name: 'JUnit XML',
    consumers: 'Jenkins · GitLab CI · GitHub Actions · Buildkite',
    purpose: 'Proof bundles as test results, so signed scientific verdicts land in your CI dashboard. REFUTED maps to failure; VALIDATED to success; INCONCLUSIVE to skipped.',
    icon: 'check',
    color: '#5e9eff',
    sample: `<?xml version="1.0" encoding="UTF-8"?>
<testsuites name="ophamin" tests="33" failures="10" skipped="2">
  <testsuite name="scientific" tests="7" failures="3">
    <testcase name="concentrated-immune-siege" classname="scientific" time="3.421"/>
    <testcase name="logic-topology-siege" classname="scientific" time="2.118">
      <failure message="REFUTED · observed 0.396 against threshold 0.60">
        Walker sustained-traversal rate fell below threshold.
        proof_id: 94e389abcd63ef83a116...
      </failure>
    </testcase>
    <testcase name="rosetta-scaling" classname="scientific" time="4.812">
      <failure message="REFUTED · canonical agreement 0.0 (threshold 0.80)"/>
    </testcase>
  </testsuite>
</testsuites>`,
    cli: 'ophamin export proof.json --format junit-xml > junit.xml',
  },
  {
    id: 'mlflow',
    name: 'MLflow',
    consumers: 'MLflow Tracking Server · Databricks · DagsHub',
    purpose: 'Every proof bundle becomes an MLflow Run with params (claim threshold + corpus + substrate commit), metrics (observed value + CI bounds + p-value), and the proof bundle attached as an artifact.',
    icon: 'activity',
    color: '#2dd4bf',
    sample: `run_id: 6d47d8c9a2deef83a116
experiment: scientific/concentrated-immune-siege
params:
  threshold_metric: gwf_false_positive_rate
  threshold_value: 0.10
  threshold_comparator: "<="
  corpus_name: offensive-security-corpus
  corpus_n_records: 4416305
  substrate_commit: 6e4477eb
metrics:
  observed_value: 0.032
  ci_low: 0.0198
  ci_high: 0.0513
  outcome: 1.0  # 1=VALIDATED, 0=REFUTED, 0.5=INCONCLUSIVE
artifacts:
  - proof.json
  - assets/ci_gwf_false_positive_rate.png
tags:
  framework_version: 0.64.1
  signed: true`,
    cli: 'ophamin export proof.json --format mlflow --tracking-uri http://mlflow:5000',
  },
  {
    id: 'cyclonedx',
    name: 'CycloneDX 1.5',
    consumers: 'OWASP Dependency-Track · GitHub Security · Snyk',
    purpose: 'Software Bill of Materials for the substrate-under-test environment. Captures every dependency that fed into the signed proof, so downstream security tools can trace provenance.',
    icon: 'cpu',
    color: '#ffa726',
    sample: `{
  "bomFormat": "CycloneDX",
  "specVersion": "1.5",
  "version": 1,
  "components": [
    { "type": "library", "name": "scipy",          "version": "1.17.1"  },
    { "type": "library", "name": "statsmodels",    "version": "0.14.6"  },
    { "type": "library", "name": "scikit-learn",   "version": "1.6.1"   },
    { "type": "library", "name": "numpy",          "version": "2.4.4"   },
    { "type": "library", "name": "pandas",         "version": "2.3.3"   },
    { "type": "library", "name": "pymc",           "version": "6.0.0"   },
    { "type": "library", "name": "ophamin",        "version": "0.64.1"  }
  ],
  "ophamin:signature": "04c1b2be72e3fe0b9f64510cf20c53a4..."
}`,
    cli: 'ophamin export --format cyclonedx > sbom.cdx.json',
  },
];

function InteropScreen() {
  const [active, setActive] = useInState('sarif');
  const ex = EXPORTERS.find(e => e.id === active);

  return (
    <div className="content-inner page" style={{ maxWidth: 1200 }}>
      <div className="page-header">
        <div>
          <h1 className="page-title">Interop</h1>
          <div className="page-subtitle">Push signed proofs and audit findings into the tools you already trust. Four formats; one signed record at the source.</div>
        </div>
        <div className="page-actions">
          <span className="live-pill ok"><span className="dot"></span>4 exporters · 0 failed</span>
        </div>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: '260px 1fr', gap: 16, marginTop: 16 }}>
        {/* Exporter list */}
        <aside style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
          {EXPORTERS.map(e => (
            <div key={e.id}
              onClick={() => setActive(e.id)}
              className={'interop-rail-row' + (active === e.id ? ' active' : '')}>
              <span className="interop-rail-icon" style={{ background: e.color + '22', color: e.color }}>
                <Icon name={e.icon} size={14}/>
              </span>
              <div style={{ flex: 1, minWidth: 0 }}>
                <div style={{ fontSize: 13, fontWeight: 600 }}>{e.name}</div>
                <div className="mono" style={{ fontSize: 10, color: 'var(--text-muted)', marginTop: 2, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{e.consumers}</div>
              </div>
            </div>
          ))}
        </aside>

        {/* Detail */}
        <div className="card">
          <div className="card-header">
            <div>
              <div className="card-title">{ex.name}</div>
              <div className="mono" style={{ fontSize: 11, color: 'var(--text-muted)', marginTop: 2 }}>{ex.consumers}</div>
            </div>
            <span className="live-pill ok"><span className="dot"></span>ready</span>
          </div>

          <div style={{ padding: '14px 18px 0' }}>
            <p style={{ fontSize: 13, color: 'var(--text-secondary)', lineHeight: 1.6, margin: 0 }}>{ex.purpose}</p>
          </div>

          <div style={{ padding: 18, display: 'grid', gridTemplateColumns: '1fr 280px', gap: 16 }}>
            <div>
              <div className="micro" style={{ marginBottom: 6 }}>SAMPLE OUTPUT</div>
              <pre style={{
                margin: 0,
                padding: 14,
                background: 'var(--bg-base)',
                border: '1px solid var(--border)',
                borderRadius: 'var(--r-sm)',
                fontFamily: 'JetBrains Mono, monospace',
                fontSize: 11,
                lineHeight: 1.55,
                color: 'var(--text-primary)',
                maxHeight: 360,
                overflow: 'auto',
                whiteSpace: 'pre-wrap',
              }}>{ex.sample}</pre>
            </div>

            <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
              <div>
                <div className="micro" style={{ marginBottom: 6 }}>CLI</div>
                <div className="mono" style={{ background: 'var(--bg-base)', border: '1px solid var(--border)', borderRadius: 'var(--r-sm)', padding: 10, fontSize: 11, color: 'var(--accent)' }}>
                  {ex.cli}
                </div>
              </div>

              <div>
                <div className="micro" style={{ marginBottom: 6 }}>EXPORT NOW</div>
                <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
                  <button className="btn primary" style={{ justifyContent: 'flex-start' }}>
                    <Icon name="download" size={12}/> Export all {OPHAMIN.totals.bundles} bundles
                  </button>
                  <button className="btn" style={{ justifyContent: 'flex-start' }}>
                    <Icon name="filter" size={12}/> Pick scenarios…
                  </button>
                  <button className="btn ghost" style={{ justifyContent: 'flex-start' }}>
                    <Icon name="external" size={12}/> Stream to remote target
                  </button>
                </div>
              </div>

              <div>
                <div className="micro" style={{ marginBottom: 6 }}>LAST EXPORT</div>
                <div style={{ background: 'var(--bg-base)', border: '1px solid var(--border)', borderRadius: 'var(--r-sm)', padding: '8px 10px', fontSize: 11, color: 'var(--text-secondary)', lineHeight: 1.5 }}>
                  <div className="mono">2026-05-19 14:32</div>
                  <div>{OPHAMIN.totals.bundles} bundles · 142 KB</div>
                  <div className="mono" style={{ color: 'var(--validated)', marginTop: 2 }}>✓ signed manifest</div>
                </div>
              </div>
            </div>
          </div>

          <div style={{ padding: '12px 18px', borderTop: '1px solid var(--border)', display: 'flex', alignItems: 'center', gap: 6 }}>
            <Icon name="eye" size={12}/>
            <span style={{ fontSize: 11.5, color: 'var(--text-muted)' }}>
              All exports preserve the original Ophamin HMAC signature in the target format's metadata. Verification traces back to the signed bundle.
            </span>
          </div>
        </div>
      </div>

      {/* Connector status */}
      <div className="card" style={{ marginTop: 16 }}>
        <div className="card-header">
          <div className="card-title">Connector status</div>
          <span className="micro">CONFIGURED TARGETS</span>
        </div>
        <table className="table">
          <thead>
            <tr>
              <th style={{ width: 100 }}>Status</th>
              <th>Target</th>
              <th>Format</th>
              <th>URL</th>
              <th style={{ width: 110 }}>Last push</th>
              <th style={{ width: 80 }}>Records</th>
            </tr>
          </thead>
          <tbody>
            <ConnectorRow status="ok" target="github-code-scanning" format="SARIF" url="api.github.com/repos/.../code-scanning/sarifs" last="2026-05-19" count="0"/>
            <ConnectorRow status="ok" target="mlflow-internal"      format="MLflow" url="http://mlflow-tracking:5000" last="2026-05-19" count="33"/>
            <ConnectorRow status="ok" target="ci-junit-archive"     format="JUnit"  url="file:///var/ci-results/" last="2026-05-19" count="33"/>
            <ConnectorRow status="warn" target="dependency-track"   format="CycloneDX" url="https://dtrack.internal/api/v1/bom" last="2d ago" count="1"/>
            <ConnectorRow status="off"  target="custom-webhook"     format="JSON"   url="not configured" last="—" count="0"/>
          </tbody>
        </table>
      </div>
    </div>
  );
}

function ConnectorRow({ status, target, format, url, last, count }) {
  const cls = status === 'ok' ? 'running' : status === 'warn' ? 'stopped' : 'stopped';
  return (
    <tr>
      <td>
        <span className={'cr-container-status cr-container-' + cls}>
          <span className="dot"></span>{status === 'ok' ? 'connected' : status === 'warn' ? 'stale' : 'off'}
        </span>
      </td>
      <td style={{ fontWeight: 500 }}>{target}</td>
      <td className="mono" style={{ fontSize: 11 }}>{format}</td>
      <td className="mono" style={{ fontSize: 11, color: 'var(--text-muted)' }}>{url}</td>
      <td className="mono" style={{ fontSize: 11 }}>{last}</td>
      <td className="mono tnum" style={{ fontSize: 11 }}>{count}</td>
    </tr>
  );
}

window.InteropScreen = InteropScreen;
