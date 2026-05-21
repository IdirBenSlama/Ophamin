/** @jsxRuntime classic */ /** @jsx React.createElement */
/* global React, OPHAMIN, Icon, Sparkline, ControlRoomScreen */
// Control Room — infrastructure panels (Parameters / Containers / Databases / Logs)
// Loaded after control.jsx; extends the ControlRoomScreen via window.__CR_INFRA.

const { useState: useInfraState } = React;

const OPHAMIN_PARAMS = [
  { id: 'signing.batch_size',   label: 'Proof-signing batch size',  value: 32,    min: 1,   max: 256,  unit: 'records', desc: 'How many evidence rows accumulate before HMAC signing flushes a proof bundle to disk.' },
  { id: 'sampler.interval_ms',  label: 'Periodic-sampler interval', value: 100,   min: 25,  max: 1000, unit: 'ms',      desc: 'How often the background process-sampler polls CPU/RSS/threads. Lower = finer resolution at sampling cost.' },
  { id: 'proofs.root',          label: 'Bundle storage root',       value: '/var/ophamin/proofs', kind: 'text', desc: 'Filesystem path where signed proof bundles are written.' },
  { id: 'sign.key_rotation',    label: 'Sign-key rotation cadence', value: 30,    min: 1,   max: 365,  unit: 'days',    desc: 'How often the HMAC publication key auto-rotates. Older keys remain valid for verification.' },
  { id: 'http.workers',         label: 'FastAPI worker count',      value: 4,     min: 1,   max: 32,   unit: 'workers', desc: 'Uvicorn process workers. Match to CPU cores for production.' },
  { id: 'http.rate_limit',      label: 'Rate limit / IP',           value: 60,    min: 0,   max: 1000, unit: 'req/min', desc: 'Throttle inbound HTTP. 0 disables (default for localhost).' },
];

const KIMERA_PARAMS = [
  { id: 'walker.step_budget',    label: 'Walker step budget',         value: 32,   min: 4,    max: 256,    unit: 'hops',      desc: 'Maximum walker hops per Takwin cycle before forced halt (M2 HALT). Lower = faster cycles, less traversal.' },
  { id: 'gwf.threshold',         label: 'GWF block threshold',        value: 0.42, min: 0.10, max: 0.95,   step: 0.01, unit: 'score', desc: 'Score above which the General Workspace Filter blocks. Lower = more cautious (more benign FPs); higher = more permissive.' },
  { id: 'cronos.pulse_hz',       label: 'Cronos atomic-clock pulse',  value: 13,   min: 1,    max: 100,    unit: 'Hz',        desc: 'The substrate canonical heartbeat. 13Hz is the design default.' },
  { id: 'hopfield.temperature',  label: 'Hopfield temperature',       value: 0.18, min: 0.01, max: 1.0,    step: 0.01, unit: 'tau', desc: 'Energy-landscape softness for the modern-Hopfield retrieval pillar.' },
  { id: 'scar.gate_sensitivity', label: 'Scar formation gate',        value: 0.62, min: 0.10, max: 0.99,   step: 0.01, unit: 'threshold', desc: 'Contradiction-gate sensitivity. Higher = fewer scars form; lower = substrate scars more readily.' },
  { id: 'bge.batch_size',        label: 'BGE-M3 encode batch',        value: 16,   min: 1,    max: 128,    unit: 'records',   desc: 'Records encoded per BGE-M3 forward pass on MPS.' },
  { id: 'manifold.curvature',    label: 'Manifold curvature scale',   value: 1.0,  min: 0.1,  max: 5.0,    step: 0.1, unit: 'k', desc: 'Curvature scale of S^4 in R^5. 1.0 = unit-sphere baseline; deformation modulates locally.' },
  { id: 'piovra.arms',           label: 'Active Piovra arms',         value: 4,    min: 1,    max: 12,     unit: 'arms',      desc: 'Foreign-corpus arms currently consuming external signal (text/image/audio/market/telemetry).' },
];

const CONTAINERS = [
  { name: 'ophamin-http-api',    image: 'ophamin/api:0.64.1',     status: 'running', uptime: '2d 3h', cpu: 12,  mem: 184,  port: '8000',   health: 'healthy' },
  { name: 'ophamin-mcp-server',  image: 'ophamin/mcp:0.64.1',     status: 'running', uptime: '2d 3h', cpu: 3,   mem: 64,   port: '8002',   health: 'healthy' },
  { name: 'kimera-substrate',    image: 'kimera-swm:0.8.5',       status: 'running', uptime: '2d 3h', cpu: 78,  mem: 4576, port: '—',      health: 'healthy' },
  { name: 'postgres-vault',      image: 'postgres:16-alpine',     status: 'running', uptime: '12d',   cpu: 4,   mem: 412,  port: '5432',   health: 'healthy' },
  { name: 'redis-arachne',       image: 'redis:7-alpine',         status: 'running', uptime: '12d',   cpu: 1,   mem: 86,   port: '6379',   health: 'healthy' },
  { name: 'mlflow-tracking',     image: 'mlflow:3.12',            status: 'running', uptime: '12d',   cpu: 2,   mem: 142,  port: '5000',   health: 'healthy' },
  { name: 'prometheus',          image: 'prom/prometheus:v2.55',  status: 'running', uptime: '12d',   cpu: 1,   mem: 96,   port: '9090',   health: 'healthy' },
  { name: 'grafana',             image: 'grafana/grafana:10.4',   status: 'running', uptime: '12d',   cpu: 1,   mem: 124,  port: '3000',   health: 'healthy' },
  { name: 'nginx-reverse-proxy', image: 'nginx:1.27-alpine',      status: 'running', uptime: '12d',   cpu: 0.5, mem: 18,   port: '80,443', health: 'healthy' },
  { name: 'minio-dvc-remote',    image: 'minio/minio:2026-04',    status: 'stopped', uptime: '—',     cpu: 0,   mem: 0,    port: '9000',   health: 'offline' },
];

const DATABASES = [
  { name: 'postgres-vault',  kind: 'PostgreSQL 16',  role: 'scar vault · primary',    size: '2.4 GiB',  rows: '2,134 scars',    connections: '16 / 100', latency: '0.3 ms',  health: 'healthy' },
  { name: 'redis-arachne',   kind: 'Redis 7',        role: 'prime registry cache',    size: '86 MiB',   rows: '48,591 primes',  connections: '4 / 32',   latency: '0.04 ms', health: 'healthy' },
  { name: 'mlflow-tracking', kind: 'SQLite (mlflow)',role: 'run + artifact tracking', size: '142 runs', rows: '12 experiments', connections: '—',        latency: '—',       health: 'healthy' },
  { name: 'proofs-fs',       kind: 'Filesystem',     role: 'signed bundles on disk',  size: '52.3 MiB', rows: '—',              connections: '—',        latency: '—',       health: 'healthy' },
  { name: 'dvc-minio',       kind: 'MinIO (S3 API)', role: 'DVC remote · datasets',   size: '18.4 GiB', rows: '127 datasets',   connections: '0',        latency: '—',       health: 'offline' },
];

function ParametersPanel({ perspective }) {
  const params = perspective === 'ophamin' ? OPHAMIN_PARAMS : KIMERA_PARAMS;
  return (
    <div className="card cr-panel">
      <div className="card-header">
        <div>
          <div className="card-title">{perspective === 'ophamin' ? 'Ophamin runtime parameters' : 'Kimera substrate parameters'}</div>
          <div className="micro" style={{ marginTop: 2 }}>HOT-RELOADABLE · CHANGES WRITE THROUGH TO config.yaml</div>
        </div>
        <span className="live-pill ok"><span className="dot"></span>{params.length} knobs</span>
      </div>
      <div className="cr-params-grid">
        {params.map(p => <ParamRow key={p.id} param={p}/>)}
      </div>
      <div style={{ padding: '12px 18px', borderTop: '1px solid var(--border)', display: 'flex', alignItems: 'center', gap: 8 }}>
        <button className="btn"><Icon name="copy" size={12}/> Diff vs default</button>
        <button className="btn"><Icon name="refresh" size={12}/> Reload from disk</button>
        <span style={{ flex: 1 }}/>
        <button className="btn primary"><Icon name="check" size={12}/> Apply changes</button>
      </div>
    </div>
  );
}

function ParamRow({ param }) {
  const [val, setVal] = useInfraState(param.value);
  const isNumeric = typeof param.value === 'number';
  return (
    <div className="cr-param-row">
      <div className="cr-param-meta">
        <div className="cr-param-label">{param.label}</div>
        <div className="cr-param-id mono">{param.id}</div>
        <div className="cr-param-desc">{param.desc}</div>
      </div>
      <div className="cr-param-control">
        {isNumeric ? (
          <>
            <input
              type="range"
              min={param.min}
              max={param.max}
              step={param.step || 1}
              value={val}
              onChange={e => setVal(Number(e.target.value))}
              className="cr-param-slider"
            />
            <div className="cr-param-value">
              <span className="mono tnum">{val}</span>
              <span className="cr-param-unit">{param.unit}</span>
            </div>
          </>
        ) : (
          <input className="input" value={val} onChange={e => setVal(e.target.value)}
            style={{ fontFamily: 'JetBrains Mono, monospace', fontSize: 12 }}/>
        )}
      </div>
    </div>
  );
}

function ContainersPanel() {
  const running = CONTAINERS.filter(c => c.status === 'running').length;
  const totalCpu = CONTAINERS.reduce((s, c) => s + c.cpu, 0);
  const totalMem = CONTAINERS.reduce((s, c) => s + c.mem, 0);
  return (
    <div className="cr-panel">
      <div className="cr-infra-summary">
        <div className="cr-infra-stat">
          <span className="micro">RUNNING</span>
          <span className="mono tnum" style={{ fontSize: 26, color: 'var(--validated)' }}>{running} <span style={{ fontSize: 14, color: 'var(--text-muted)' }}>/ {CONTAINERS.length}</span></span>
        </div>
        <div className="cr-infra-stat">
          <span className="micro">CPU USAGE</span>
          <span className="mono tnum" style={{ fontSize: 26 }}>{totalCpu.toFixed(0)}%</span>
        </div>
        <div className="cr-infra-stat">
          <span className="micro">MEMORY</span>
          <span className="mono tnum" style={{ fontSize: 26 }}>{(totalMem / 1024).toFixed(1)}<span style={{ fontSize: 14, color: 'var(--text-muted)' }}> GiB</span></span>
        </div>
        <div className="cr-infra-stat">
          <span className="micro">NETWORK</span>
          <span className="mono tnum" style={{ fontSize: 26 }}>192<span style={{ fontSize: 14, color: 'var(--text-muted)' }}> MB/s</span></span>
        </div>
        <div style={{ flex: 1 }}/>
        <button className="btn"><Icon name="copy" size={12}/> docker compose ps</button>
        <button className="btn primary"><Icon name="play" size={12}/> Compose up</button>
      </div>

      <div className="card" style={{ marginTop: 14, overflow: 'hidden' }}>
        <div className="card-header">
          <div className="card-title">Containers</div>
          <span className="micro">DOCKER · COMPOSE STACK · ophamin-stack</span>
        </div>
        <table className="table">
          <thead>
            <tr>
              <th style={{ width: 100 }}>Status</th>
              <th>Name</th>
              <th>Image</th>
              <th>Port</th>
              <th>Uptime</th>
              <th>CPU</th>
              <th>Memory</th>
              <th style={{ width: 110 }}>Actions</th>
            </tr>
          </thead>
          <tbody>
            {CONTAINERS.map(c => (
              <tr key={c.name}>
                <td>
                  <span className={'cr-container-status cr-container-' + c.status}>
                    <span className="dot"></span>{c.status}
                  </span>
                </td>
                <td style={{ fontWeight: 500, fontSize: 12.5 }}>{c.name}</td>
                <td className="mono" style={{ fontSize: 11, color: 'var(--text-muted)' }}>{c.image}</td>
                <td className="mono" style={{ fontSize: 11 }}>{c.port}</td>
                <td className="mono" style={{ fontSize: 11, color: 'var(--text-muted)' }}>{c.uptime}</td>
                <td className="mono tnum" style={{ fontSize: 11 }}>{c.cpu}%</td>
                <td className="mono tnum" style={{ fontSize: 11 }}>{c.mem === 0 ? '—' : (c.mem > 1024 ? (c.mem/1024).toFixed(1) + ' GiB' : c.mem + ' MiB')}</td>
                <td>
                  <span className="cr-container-actions">
                    <span className="cr-container-action" title="Logs"><Icon name="code" size={11}/></span>
                    <span className="cr-container-action" title="Restart"><Icon name="refresh" size={11}/></span>
                    {c.status === 'running'
                      ? <span className="cr-container-action danger" title="Stop"><Icon name="x" size={11}/></span>
                      : <span className="cr-container-action" title="Start"><Icon name="play" size={11}/></span>}
                  </span>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function DatabasesPanel() {
  return (
    <div className="cr-panel">
      <div className="cr-db-grid">
        {DATABASES.map(db => (
          <div key={db.name} className={'card cr-db-card' + (db.health === 'offline' ? ' offline' : '')}>
            <div style={{ padding: '14px 16px 10px', borderBottom: '1px solid var(--border)' }}>
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                <div className="mono" style={{ fontSize: 13, fontWeight: 600 }}>{db.name}</div>
                <span className={'cr-container-status cr-container-' + (db.health === 'healthy' ? 'running' : 'stopped')}>
                  <span className="dot"></span>{db.health}
                </span>
              </div>
              <div style={{ fontSize: 11, color: 'var(--text-muted)', marginTop: 4 }}>{db.kind} · <span style={{ color: 'var(--text-secondary)' }}>{db.role}</span></div>
            </div>
            <div style={{ padding: 14, display: 'grid', gridTemplateColumns: '90px 1fr', gap: '4px 12px', fontSize: 12 }}>
              <span className="mono faint">size</span><span className="mono">{db.size}</span>
              <span className="mono faint">records</span><span className="mono">{db.rows}</span>
              <span className="mono faint">conn</span><span className="mono">{db.connections}</span>
              <span className="mono faint">latency</span><span className="mono">{db.latency}</span>
            </div>
            <div style={{ padding: '10px 14px', borderTop: '1px solid var(--border)', display: 'flex', gap: 6 }}>
              <button className="btn ghost" style={{ fontSize: 11 }}><Icon name="code" size={11}/> Query</button>
              <button className="btn ghost" style={{ fontSize: 11 }}><Icon name="download" size={11}/> Backup</button>
              {db.health === 'offline' && <button className="btn ghost" style={{ fontSize: 11, color: 'var(--validated)' }}><Icon name="play" size={11}/> Start</button>}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

function LogsPanel({ perspective }) {
  const streams = perspective === 'ophamin'
    ? ['ophamin-http-api', 'ophamin-mcp-server', 'postgres-vault', 'redis-arachne', 'nginx-reverse-proxy', 'mlflow-tracking']
    : ['kimera-substrate', 'kimera-cycle-loop', 'arachne-protocol', 'piovra-arm-0', 'piovra-arm-1', 'cronos-pulse'];
  const [stream, setStream] = useInfraState(streams[0]);
  const lines = generateLogs(stream);
  return (
    <div className="cr-panel">
      <div style={{ display: 'flex', gap: 6, marginBottom: 12, flexWrap: 'wrap' }}>
        {streams.map(s => (
          <button key={s} onClick={() => setStream(s)}
            className={'scn-tier-pill' + (stream === s ? ' active' : '')}>
            {s}
          </button>
        ))}
      </div>
      <div className="card cr-logs-card">
        <div className="card-header">
          <div className="card-title">{stream}</div>
          <span className="live-pill"><span className="dot"></span>tail -f</span>
        </div>
        <pre className="cr-logs-body">{lines.join('\n')}</pre>
        <div style={{ padding: '8px 14px', borderTop: '1px solid var(--border)', display: 'flex', gap: 6, alignItems: 'center' }}>
          <button className="btn ghost" style={{ fontSize: 11 }}><Icon name="download" size={11}/> Export</button>
          <button className="btn ghost" style={{ fontSize: 11 }}><Icon name="search" size={11}/> Filter</button>
          <span style={{ flex: 1 }}/>
          <span className="mono" style={{ fontSize: 10, color: 'var(--text-muted)' }}>{lines.length} lines · since 0:00</span>
        </div>
      </div>
    </div>
  );
}

function generateLogs(stream) {
  const t = (offset) => new Date(Date.now() - offset * 1000).toISOString().slice(11, 23);
  if (stream.includes('http-api')) return [
    `[${t(2)}] INFO  uvicorn.access  127.0.0.1:54192 - "GET /proofs/bundles/file HTTP/1.1" 200`,
    `[${t(4)}] INFO  ophamin.signing flush_batch · 32 records · proof_id=6d47d8c9a2de`,
    `[${t(6)}] INFO  uvicorn.access  127.0.0.1:54193 - "GET /scenarios HTTP/1.1" 200`,
    `[${t(9)}] DEBUG ophamin.metrics rss_peak=184MiB threads=14 fds=38`,
    `[${t(12)}] INFO uvicorn.access  127.0.0.1:54195 - "POST /verify HTTP/1.1" 200`,
    `[${t(15)}] INFO ophamin.proof   indexed bundle · throughput-ceiling validated · 69197dbc`,
    `[${t(18)}] INFO uvicorn.access  127.0.0.1:54197 - "GET /metrics HTTP/1.1" 200`,
  ];
  if (stream.includes('kimera-substrate')) return [
    `[${t(1)}] INFO  Takwin.run     cycle_index=2841 · phi=0.284 · coherence=0.871 · mode=M1_COMMIT`,
    `[${t(3)}] INFO  GWF            verdict=allow · benign · features=12 · score=0.04`,
    `[${t(5)}] INFO  Walker         step_count=7 · halt=false · prime_chain=[2,7,13,17,23,31]`,
    `[${t(7)}] INFO  Vault          scar formed · key=2135 · contradiction_score=0.71`,
    `[${t(9)}] INFO  Rosetta        rosetta_stele deposit · channel=text · canonical="entropy"`,
    `[${t(11)}] INFO Cronos         pulse 13Hz · cycle_seconds=1.012`,
    `[${t(13)}] INFO Takwin.run     cycle_index=2842 · phi=0.281 · coherence=0.873 · mode=M2_HALT`,
    `[${t(16)}] WARN Walker         M2_HALT triggered · self-reference detected`,
  ];
  if (stream.includes('arachne')) return [
    `[${t(2)}] INFO  Arachne.assign new prime · concept="entropy" · prime=104729`,
    `[${t(5)}] DEBUG Arachne        lookup hit · concept="time" · cached`,
    `[${t(8)}] INFO  Arachne.assign new prime · concept="manifold" · prime=104743`,
    `[${t(11)}] DEBUG Arachne       registry size 48,591 primes assigned`,
  ];
  return [
    `[${t(1)}] INFO  ${stream}  service ready`,
    `[${t(4)}] INFO  ${stream}  heartbeat ok`,
    `[${t(7)}] DEBUG ${stream}  processed batch · 32 items`,
    `[${t(11)}] INFO ${stream}  flush · 0 errors`,
  ];
}

window.ParametersPanel = ParametersPanel;
window.ContainersPanel = ContainersPanel;
window.DatabasesPanel  = DatabasesPanel;
window.LogsPanel       = LogsPanel;
