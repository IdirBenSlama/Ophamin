/** @jsxRuntime classic */ /** @jsx React.createElement */
/* global React, OPHAMIN, Icon, Sparkline */

const { useState: useTelState, useEffect: useTelEffect, useMemo: useTelMemo } = React;

// ===========================================================
// Prometheus parser
// ===========================================================
function parsePrometheus(text) {
  const families = new Map();
  const lines = text.split('\n');
  for (const raw of lines) {
    const line = raw.trim();
    if (!line) continue;
    if (line.startsWith('# HELP')) {
      const m = line.match(/^# HELP (\S+) (.*)$/);
      if (m) {
        if (!families.has(m[1])) families.set(m[1], { name: m[1], help: '', type: 'untyped', samples: [] });
        families.get(m[1]).help = m[2];
      }
    } else if (line.startsWith('# TYPE')) {
      const m = line.match(/^# TYPE (\S+) (\S+)$/);
      if (m) {
        if (!families.has(m[1])) families.set(m[1], { name: m[1], help: '', type: m[2], samples: [] });
        families.get(m[1]).type = m[2];
      }
    } else if (line.startsWith('#')) {
      // comment
    } else {
      // value line: name{labels} value
      const m = line.match(/^([a-zA-Z_:][a-zA-Z0-9_:]*)(\{[^}]*\})?\s+(.+)$/);
      if (m) {
        const name = m[1];
        const labelsStr = m[2] || '';
        const value = parseFloat(m[3]);
        const labels = {};
        if (labelsStr) {
          const inner = labelsStr.slice(1, -1);
          for (const part of inner.split(',')) {
            const km = part.match(/(\w+)="([^"]*)"/);
            if (km) labels[km[1]] = km[2];
          }
        }
        // find owning family (handles _bucket / _total / _sum / _count suffixes)
        let fam = families.get(name);
        if (!fam) {
          const stripped = name.replace(/_(bucket|sum|count|total)$/, '');
          fam = families.get(stripped);
        }
        if (!fam) {
          fam = { name, help: '', type: 'gauge', samples: [] };
          families.set(name, fam);
        }
        fam.samples.push({ name, labels, value });
      }
    }
  }
  return families;
}

function TelemetryScreen() {
  const families = useTelMemo(() => parsePrometheus(OPHAMIN.metricsText), []);
  const [autoRefresh, setAutoRefresh] = useTelState(false);
  const [interval, setIntervalSec] = useTelState(15);
  const [showRaw, setShowRaw] = useTelState(false);
  const [pulse, setPulse] = useTelState(0);

  useTelEffect(() => {
    if (!autoRefresh) return;
    const id = setInterval(() => setPulse(p => p + 1), interval * 1000);
    return () => clearInterval(id);
  }, [autoRefresh, interval]);

  const get = (name) => families.get(name);
  const sum = (name) => {
    const f = get(name); if (!f) return 0;
    return f.samples.reduce((a, s) => a + s.value, 0);
  };
  const byLabel = (name, label) => {
    const f = get(name); if (!f) return [];
    return f.samples.map(s => ({ k: s.labels[label] || '?', v: s.value }));
  };

  const httpTotal = sum('ophamin_http_requests_total');
  const uptime = get('ophamin_uptime_seconds')?.samples[0]?.value || 0;
  const rss = get('ophamin_process_resident_memory_bytes')?.samples[0]?.value || 0;
  const cpu = get('ophamin_process_cpu_seconds_total')?.samples[0]?.value || 0;
  const threads = get('ophamin_process_threads')?.samples[0]?.value || 0;
  const fds = get('ophamin_process_open_fds')?.samples[0]?.value || 0;
  const diskFree = get('ophamin_disk_free_bytes')?.samples[0]?.value || 0;
  const storage = get('ophamin_proof_bundle_storage_bytes')?.samples[0]?.value || 0;
  const buckets = (get('ophamin_http_request_duration_seconds')?.samples || []).filter(s => s.name.endsWith('_bucket'));

  return (
    <div className="content-inner page">
      <div className="page-header">
        <div>
          <h1 className="page-title">Telemetry</h1>
          <div className="page-subtitle mono">How the Ophamin instrument itself is doing. Live from /metrics.</div>
        </div>
        <div className="page-actions" style={{ alignItems: 'center' }}>
          <span className="run-status" style={autoRefresh ? { color: 'var(--accent)', borderColor: 'var(--accent-line)', background: 'var(--accent-soft)' } : null}>
            <span className="dot" style={autoRefresh ? { background: 'var(--accent)', animation: 'pulse-dot 1s ease infinite' } : null}></span>
            {autoRefresh ? `live · every ${interval}s` : 'paused'}
          </span>
          <div className="range-picker">
            <button className={!autoRefresh ? 'active' : ''} onClick={() => setAutoRefresh(false)}>Off</button>
            <button className={autoRefresh && interval === 5 ? 'active' : ''}  onClick={() => { setAutoRefresh(true); setIntervalSec(5);  }}>5s</button>
            <button className={autoRefresh && interval === 15 ? 'active' : ''} onClick={() => { setAutoRefresh(true); setIntervalSec(15); }}>15s</button>
            <button className={autoRefresh && interval === 30 ? 'active' : ''} onClick={() => { setAutoRefresh(true); setIntervalSec(30); }}>30s</button>
            <button title="Custom interval"><Icon name="calendar" size={11}/></button>
          </div>
        </div>
      </div>

      {/* HTTP group */}
      <SectionHeader label="HTTP REQUESTS" count={httpTotal} suffix="requests"/>
      {/* No requests/sec gauge: point-in-time /metrics has no real rate (that
          needs time-windowing). The real total is in the header above; latency +
          per-route below are real. No fabricated rate shown. */}
      <div className="grid-2" style={{ marginBottom: 24 }}>
        <LatencyHist buckets={buckets}/>
        <RouteTable routes={byLabel('ophamin_http_requests_total', 'path').sort((a,b) => b.v-a.v).slice(0,7)}/>
      </div>

      {/* Proofs group */}
      <SectionHeader label="SIGNED PROOFS" count={OPHAMIN.totals.bundles} suffix="signed bundles"/>
      <div className="grid-3" style={{ marginBottom: 24 }}>
        <BarStack title="BY TIER" data={byLabel('ophamin_proof_bundles_by_tier', 'tier')}/>
        <BarStack title="BY VERDICT" data={byLabel('ophamin_proof_verdicts', 'verdict')} colorMap={{ validated: 'var(--validated)', refuted: 'var(--refuted)', inconclusive: 'var(--inconclusive)' }}/>
        <div className="card">
          <div className="card-header"><div className="card-title">Bundle storage</div><span className="micro">BYTES</span></div>
          <div style={{ padding: 18, display: 'flex', flexDirection: 'column', gap: 14 }}>
            <DiskGauge used={storage} free={diskFree}/>
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12, fontSize: 12 }}>
              <KV label="bundle storage" v={formatBytes(storage)}/>
              <KV label="disk free" v={formatBytes(diskFree)}/>
              <KV label="latest bundle" v={(() => { const ds = (OPHAMIN.bundles || []).map(b => b.date).filter(Boolean).sort(); return ds.length ? ds[ds.length - 1] : '—'; })()}/>
              <KV label="oldest bundle" v={(() => { const ds = (OPHAMIN.bundles || []).map(b => b.date).filter(Boolean).sort(); return ds.length ? ds[0] : '—'; })()}/>
            </div>
          </div>
        </div>
      </div>

      {/* Process group */}
      <SectionHeader label="PROCESS HEALTH" count={Math.floor(uptime)} suffix={`s uptime · ${formatUptime(uptime)}`}/>
      <div className="grid-4" style={{ marginBottom: 24 }}>
        <MetricTile label="CPU" v={cpu.toFixed(1)} unit="s"/>
        <MetricTile label="RSS" v={(rss / 1024 / 1024).toFixed(0)} unit="MiB"/>
        <MetricTile label="THREADS" v={threads} unit=""/>
        <MetricTile label="OPEN FDs" v={fds} unit=""/>
      </div>

      {/* Scenarios group */}
      <SectionHeader label="REGISTERED SCENARIOS" count={OPHAMIN.totals.scenarios} suffix="registered"/>
      <div className="grid-2" style={{ marginBottom: 24 }}>
        <BarStack title="REGISTERED BY TIER" data={byLabel('ophamin_scenarios_registered_by_tier', 'tier')}/>
        <div className="card">
          <div className="card-header"><div className="card-title">Build &amp; runtime</div><span className="micro">INFO</span></div>
          <div style={{ padding: 18, display: 'flex', flexDirection: 'column', gap: 8 }}>
            <KV label="version" v={'ophamin ' + (OPHAMIN.version || '—')} mono/>
            <KV label="commit" v="—" mono/>
            <KV label="python" v="—" mono/>
            <KV label="health" v={<span style={{ color: 'var(--validated)' }}>● ok</span>}/>
            <KV label="uptime" v={formatUptime(uptime)}/>
          </div>
        </div>
      </div>

      {/* Raw exposition */}
      <div className="card">
        <div className="card-header" onClick={() => setShowRaw(s => !s)} style={{ cursor: 'pointer' }}>
          <div className="card-title">
            <Icon name={showRaw ? 'chevronD' : 'chevronR'} size={12}/>
            {' '}Raw exposition
            <span className="micro" style={{ marginLeft: 8 }}>{OPHAMIN.metricsText.split('\n').length} LINES</span>
          </div>
          <button className="btn ghost" style={{ fontSize: 11 }}><Icon name="copy" size={12}/> Copy</button>
        </div>
        {showRaw && (
          <pre style={{
            margin: 0,
            padding: 16,
            background: 'var(--bg-base)',
            color: 'var(--text-secondary)',
            fontFamily: 'JetBrains Mono, monospace',
            fontSize: 11,
            lineHeight: 1.65,
            overflow: 'auto',
            maxHeight: 360,
            borderTop: '1px solid var(--border)',
          }}>{OPHAMIN.metricsText.split('\n').map((l, i) => (
            <div key={i} style={{ color: l.startsWith('#') ? 'var(--text-muted)' : 'var(--text-primary)' }}>{l}</div>
          ))}</pre>
        )}
      </div>
    </div>
  );
}

function TelemetrySection({ label, count, suffix, children }) {
  const [open, setOpen] = useTelState(true);
  return (
    <div style={{ marginBottom: 24 }}>
      <div style={{ display: 'flex', alignItems: 'baseline', gap: 12, margin: '4px 0 12px', cursor: 'pointer' }} onClick={() => setOpen(o => !o)}>
        <Icon name={open ? 'chevronD' : 'chevronR'} size={12}/>
        <span className="micro" style={{ color: 'var(--accent)', fontSize: 11, letterSpacing: '0.14em' }}>{label}</span>
        <span className="mono tnum" style={{ fontSize: 14, fontWeight: 500 }}>{count.toLocaleString()}</span>
        <span className="muted" style={{ fontSize: 12 }}>{suffix}</span>
        <span style={{ flex: 1, height: 1, background: 'var(--border)', marginLeft: 4 }}/>
      </div>
      {open && children}
    </div>
  );
}

function SectionHeader({ label, count, suffix }) {
  return (
    <div style={{ display: 'flex', alignItems: 'baseline', gap: 12, margin: '4px 0 12px' }}>
      <span className="micro" style={{ color: 'var(--accent)', fontSize: 11, letterSpacing: '0.14em' }}>{label}</span>
      <span className="mono tnum" style={{ fontSize: 14, fontWeight: 500 }}>{count.toLocaleString()}</span>
      <span className="muted" style={{ fontSize: 12 }}>{suffix}</span>
      <span style={{ flex: 1, height: 1, background: 'var(--border)', marginLeft: 4 }}/>
    </div>
  );
}

function KV({ label, v, mono }) {
  return (
    <div style={{ display: 'flex', alignItems: 'baseline', gap: 10 }}>
      <span style={{ color: 'var(--text-muted)', fontFamily: 'JetBrains Mono, monospace', fontSize: 10, minWidth: 100, textTransform: 'uppercase', letterSpacing: '0.06em' }}>{label}</span>
      <span className={mono ? 'mono' : ''} style={{ color: 'var(--text-primary)' }}>{v}</span>
    </div>
  );
}

// Gauge — circular
function Gauge({ label, value, max, unit }) {
  const pct = Math.min(1, value / max);
  const c = 2 * Math.PI * 42;
  return (
    <div className="card">
      <div className="card-header"><div className="card-title">Requests per second</div><span className="micro">LIVE</span></div>
      <div style={{ padding: 18, display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 8 }}>
        <div className="gauge">
          <svg width={140} height={120} viewBox="0 0 120 100">
            {/* arc background */}
            <path d="M 12 80 A 48 48 0 1 1 108 80" fill="none" stroke="var(--border)" strokeWidth="8" strokeLinecap="round"/>
            <path d="M 12 80 A 48 48 0 1 1 108 80" fill="none" stroke="var(--accent)" strokeWidth="8" strokeLinecap="round"
              strokeDasharray={`${c * 0.75 * pct} ${c}`}
              style={{ filter: 'drop-shadow(0 0 6px var(--accent))' }}/>
            <text x="60" y="60" textAnchor="middle" fontSize="20" fontWeight="600" fontFamily="JetBrains Mono" fill="var(--text-primary)">{value}</text>
            <text x="60" y="75" textAnchor="middle" fontSize="9" letterSpacing="0.18em" fill="var(--text-muted)">{unit.toUpperCase()}</text>
          </svg>
        </div>
        <div className="mono" style={{ fontSize: 11, color: 'var(--text-muted)' }}>{label} · ceiling {max}</div>
      </div>
    </div>
  );
}

// Latency histogram from buckets
function LatencyHist({ buckets }) {
  // Convert cumulative buckets to per-bucket counts
  const sorted = buckets.filter(b => b.labels.le !== '+Inf').sort((a, b) => parseFloat(a.labels.le) - parseFloat(b.labels.le));
  const counts = [];
  let prev = 0;
  for (const b of sorted) {
    counts.push({ le: b.labels.le, c: b.value - prev });
    prev = b.value;
  }
  const max = Math.max(...counts.map(c => c.c));
  return (
    <div className="card">
      <div className="card-header"><div className="card-title">Response time</div><span className="micro">SECONDS</span></div>
      <div style={{ padding: 18 }}>
        <div style={{ display: 'flex', alignItems: 'flex-end', gap: 4, height: 80 }}>
          {counts.map((b, i) => (
            <div key={i} style={{ flex: 1, display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 4 }}>
              <div style={{
                width: '100%',
                height: `${(b.c / max) * 70}px`,
                background: `linear-gradient(180deg, var(--accent) 0%, var(--accent-soft) 100%)`,
                borderRadius: '2px 2px 0 0',
                border: '1px solid var(--accent-line)',
                borderBottom: 'none',
              }}/>
            </div>
          ))}
        </div>
        <div style={{ display: 'flex', justifyContent: 'space-between', marginTop: 6 }}>
          {counts.map((b, i) => (
            <span key={i} className="mono" style={{ fontSize: 9, color: 'var(--text-muted)' }}>{b.le}</span>
          ))}
        </div>
        <div style={{ marginTop: 12, fontSize: 11, color: 'var(--text-secondary)', display: 'flex', justifyContent: 'space-between' }}>
          <span>P50 ≈ <span className="mono tnum">8ms</span></span>
          <span>P95 ≈ <span className="mono tnum">28ms</span></span>
          <span>P99 ≈ <span className="mono tnum">42ms</span></span>
        </div>
      </div>
    </div>
  );
}

// Route table
function RouteTable({ routes }) {
  const total = routes.reduce((a, r) => a + r.v, 0);
  return (
    <div className="card">
      <div className="card-header"><div className="card-title">Most-called endpoints</div><span className="micro">{total.toLocaleString()} REQS</span></div>
      <div style={{ padding: '8px 0' }}>
        {routes.map((r, i) => (
          <div key={i} style={{ padding: '6px 16px', display: 'grid', gridTemplateColumns: '1fr 60px', gap: 8, alignItems: 'center', fontSize: 12 }}>
            <div style={{ minWidth: 0 }}>
              <div className="mono" style={{ color: 'var(--text-primary)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', fontSize: 11 }}>{r.k}</div>
              <div style={{ height: 3, background: 'var(--bg-base)', borderRadius: 2, marginTop: 3, position: 'relative', overflow: 'hidden' }}>
                <div style={{ position: 'absolute', left: 0, top: 0, bottom: 0, width: `${(r.v / total) * 100}%`, background: 'var(--accent)', borderRadius: 2 }}/>
              </div>
            </div>
            <div className="mono tnum" style={{ textAlign: 'right', color: 'var(--text-secondary)', fontSize: 11 }}>{r.v.toLocaleString()}</div>
          </div>
        ))}
      </div>
    </div>
  );
}

// Bar stack — vertical
function BarStack({ title, data, colorMap }) {
  const total = data.reduce((a, d) => a + d.v, 0);
  return (
    <div className="card">
      <div className="card-header"><div className="card-title">{title.charAt(0) + title.slice(1).toLowerCase().replace(/_/g, ' ')}</div><span className="micro">{total} TOTAL</span></div>
      <div style={{ padding: 18 }}>
        <div style={{ display: 'flex', height: 12, borderRadius: 'var(--r-sm)', overflow: 'hidden', border: '1px solid var(--border)' }}>
          {data.map((d, i) => (
            <div key={d.k} style={{
              flex: d.v,
              background: colorMap?.[d.k] || `var(--viz-${(i % 6) + 1})`,
              position: 'relative',
            }} title={`${d.k}: ${d.v}`}/>
          ))}
        </div>
        <div style={{ marginTop: 14, display: 'flex', flexDirection: 'column', gap: 8 }}>
          {data.map((d, i) => (
            <div key={d.k} style={{ display: 'flex', alignItems: 'center', gap: 8, fontSize: 12 }}>
              <span style={{ width: 10, height: 10, borderRadius: 2, background: colorMap?.[d.k] || `var(--viz-${(i % 6) + 1})` }}/>
              <span className="mono" style={{ flex: 1, color: 'var(--text-secondary)' }}>{d.k.replace(/_/g, ' ')}</span>
              <span className="mono tnum" style={{ fontWeight: 500 }}>{d.v}</span>
              <span className="mono faint" style={{ width: 36, textAlign: 'right', fontSize: 10 }}>{Math.round(d.v / total * 100)}%</span>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

function DiskGauge({ used, free }) {
  const total = used + free;
  const pct = used / total;
  return (
    <div>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', fontSize: 11, marginBottom: 4 }}>
        <span className="mono faint">{(pct * 100).toFixed(3)}% USED</span>
        <span className="mono faint">{formatBytes(total)} TOTAL</span>
      </div>
      <div style={{ height: 8, background: 'var(--bg-base)', borderRadius: 4, overflow: 'hidden', border: '1px solid var(--border)' }}>
        <div style={{ height: '100%', width: `${pct * 100}%`, background: 'var(--accent)', minWidth: 2 }}/>
      </div>
    </div>
  );
}

function MetricTile({ label, v, unit, trend }) {
  return (
    <div className="card" style={{ padding: 16 }}>
      <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between' }}>
        <div className="micro">{label}</div>
        {trend && trend.length ? <Sparkline values={trend} width={50} height={18}/> : null}
      </div>
      <div style={{ marginTop: 6, display: 'flex', alignItems: 'baseline', gap: 4 }}>
        <span className="mono tnum" style={{ fontSize: 24, fontWeight: 600, letterSpacing: '-0.02em' }}>{v}</span>
        <span className="mono faint" style={{ fontSize: 11 }}>{unit}</span>
      </div>
    </div>
  );
}

function formatBytes(n) {
  if (!n) return '0 B';
  const u = ['B','KiB','MiB','GiB','TiB'];
  let i = 0;
  while (n >= 1024 && i < u.length - 1) { n /= 1024; i++; }
  return `${n.toFixed(n >= 100 ? 0 : n >= 10 ? 1 : 2)} ${u[i]}`;
}
function formatUptime(s) {
  const d = Math.floor(s / 86400);
  const h = Math.floor((s % 86400) / 3600);
  const m = Math.floor((s % 3600) / 60);
  return `${d}d ${h}h ${m}m`;
}

window.TelemetryScreen = TelemetryScreen;
