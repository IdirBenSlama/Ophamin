/** @jsxRuntime classic */ /** @jsx React.createElement */
/* global React, SixWheelsRing, CountUp, VerdictPill, TierChip, FormatBadges, OPHAMIN, Icon */
// Overview / Dashboard screen.

const { useState: useOvState, useMemo: useOvMemo } = React;

function OverviewScreen({ onNavToProofs }) {
  const D = OPHAMIN;

  // Real instrument telemetry from /metrics (uptime + proof storage). null =
  // loading, false = unreachable → honest "—"; never a fabricated value.
  const [metrics, setMetrics] = useOvState(null);
  React.useEffect(() => {
    let alive = true;
    const base = window.OPHAMIN_API_BASE || '';
    fetch(base + '/metrics', { headers: { accept: 'text/plain' } })
      .then((r) => (r.ok ? r.text() : Promise.reject(new Error('HTTP ' + r.status))))
      .then((text) => {
        if (!alive) return;
        const num = (re) => { const m = text.match(re); return m ? parseFloat(m[1]) : null; };
        setMetrics({
          uptime_s: num(/^ophamin_uptime_seconds\s+([0-9.eE+]+)/m),
          storage_bytes: num(/^ophamin_proof_bundle_storage_bytes\s+([0-9.eE+]+)/m),
        });
      })
      .catch(() => { if (alive) setMetrics(false); });
    return () => { alive = false; };
  }, []);
  const fmtUptime = (s) => {
    if (s == null) return '—';
    const d = Math.floor(s / 86400), h = Math.floor((s % 86400) / 3600), m = Math.floor((s % 3600) / 60);
    return d ? `${d}d ${h}h ${m}m` : h ? `${h}h ${m}m` : `${m}m`;
  };
  const fmtBytes = (b) => {
    if (b == null) return '—';
    const mib = b / 1048576;
    return mib >= 1024 ? (mib / 1024).toFixed(1) + ' GiB' : mib.toFixed(1) + ' MiB';
  };
  const uptimeStr = metrics === null ? '…' : fmtUptime(metrics ? metrics.uptime_s : null);
  const storageStr = metrics === null ? '…' : fmtBytes(metrics ? metrics.storage_bytes : null);

  const stats = [
    { id: 'scenarios', label: 'Scenarios', value: D.totals.scenarios, kind: 'neutral' },
    { id: 'bundles', label: 'Bundles', value: D.totals.bundles, kind: 'neutral' },
    { id: 'validated', label: 'Validated', value: D.totals.verdicts.validated, kind: 'validated' },
    { id: 'refuted', label: 'Refuted', value: D.totals.verdicts.refuted, kind: 'refuted' },
    { id: 'inconclusive', label: 'Inconclusive', value: D.totals.verdicts.inconclusive, kind: 'inconclusive' },
  ];

  return (
    <div className="content-inner page">
      <div className="page-header">
        <div>
          <h1 className="page-title">Overview</h1>
          <div className="page-subtitle">Where the substrate stands today. {D.totals.bundles} signed proofs across {D.totals.tiers} tiers.</div>
        </div>
        <div className="page-actions">
          <span className="live-pill"><span className="dot"></span>Live</span>
          <span className="roadmap-progress-strip" title="Kimera autonomous roadmap progress (Phases 0-7)">
            <span className="rps-label">ROADMAP</span>
            {[0,1,2,3,4,5,6,7].map(i => (
              <span key={i} className={'rps-dot ' + (i === 0 ? 'done' : i === 1 ? 'active' : 'pending')}/>
            ))}
            <span className="rps-count mono">1 / 8</span>
          </span>
          <button className="btn"><Icon name="refresh" size={13} /> Refresh</button>
          <button className="btn primary"><Icon name="play" size={13} /> Run scenario</button>
        </div>
      </div>

      {/* Stat row */}
      <div className="grid-5" style={{ marginBottom: 16, marginTop: 16 }}>
        {stats.map((s, i) => (
          <div key={s.id}
            className="stat-tile fade-up"
            style={{ animationDelay: `${i * 50}ms`,
              color: s.kind === 'validated' ? 'var(--validated)' : s.kind === 'refuted' ? 'var(--refuted)' : s.kind === 'inconclusive' ? 'var(--inconclusive)' : 'var(--text-primary)' }}>
            <div className="stat-label">
              <span className="micro" style={{ color: 'var(--text-muted)' }}>{s.label}</span>
              {s.kind !== 'neutral' && <span style={{ width: 5, height: 5, borderRadius: '50%', background: 'currentColor' }}></span>}
            </div>
            <div className="stat-number"><CountUp value={s.value} duration={900 + i * 100} /></div>
            <div className="stat-foot">
              <span className="mono" style={{ fontSize: 11, color: 'var(--text-muted)' }}>
                {s.kind === 'neutral' ? 'total' : `${Math.round(s.value / D.totals.bundles * 100)}% of total`}
              </span>
              <Sparkline values={s.kind === 'validated' ? [12,14,15,16,18,19,20,21] : s.kind === 'refuted' ? [4,5,6,7,8,9,10,10] : s.kind === 'inconclusive' ? [0,0,1,1,1,2,2,2] : [20,22,25,27,30,31,33,33]} color="currentColor" />
            </div>
          </div>
        ))}
      </div>

      {/* Hero row */}
      <div style={{ display: 'grid', gridTemplateColumns: '1.2fr 0.9fr 0.9fr', gap: 16, marginBottom: 16 }}>
        <div className="card" style={{ overflow: 'hidden' }}>
          <div className="card-header">
            <div className="card-title">Substrate health</div>
            <span className="run-status done"><span className="dot"></span>nominal</span>
          </div>
          <div style={{ padding: 24, display: 'grid', placeItems: 'center' }}>
            <SixWheelsRing size={280} wheels={D.wheels} />
          </div>
          <div style={{ padding: '0 20px 16px', display: 'grid', gridTemplateColumns: 'repeat(3,1fr)', gap: 8 }}>
            {D.wheels.map(w => (
              <div key={w.id} style={{ display: 'flex', alignItems: 'center', gap: 8, fontSize: 11 }}>
                <span style={{ width: 8, height: 8, borderRadius: '50%', background: w.color }} />
                <span className="mono" style={{ color: 'var(--text-secondary)', letterSpacing: '0.06em' }}>{w.label}</span>
                <span className="mono" style={{ marginLeft: 'auto', color: 'var(--text-muted)' }}>{Math.round(w.health * 100)}%</span>
              </div>
            ))}
          </div>
        </div>

        <div className="card">
          <div className="card-header">
            <div className="card-title">How runs landed</div>
            <span className="micro">{D.totals.bundles} BUNDLES</span>
          </div>
          <div style={{ display: 'grid', placeItems: 'center', padding: '24px 20px' }}>
            <VerdictDonut totals={D.totals.verdicts} onSegment={v => onNavToProofs(v)} />
            <div style={{ display: 'flex', flexDirection: 'column', gap: 10, width: '100%', marginTop: 24 }}>
              {Object.entries(D.totals.verdicts).map(([k,v]) => (
                <div key={k}
                  onClick={() => onNavToProofs(k)}
                  style={{ display: 'flex', alignItems: 'center', gap: 10, cursor: 'pointer', padding: 6, borderRadius: 'var(--r-sm)' }}>
                  <span style={{ width: 10, height: 10, borderRadius: 2, background: `var(--${k})` }} />
                  <span style={{ flex: 1, fontSize: 13, textTransform: 'capitalize' }}>{k}</span>
                  <span className="mono tnum" style={{ fontSize: 14, color: `var(--${k})`, fontWeight: 600 }}>{v}</span>
                  <span className="mono" style={{ fontSize: 11, color: 'var(--text-muted)', width: 32, textAlign: 'right' }}>{Math.round(v/D.totals.bundles*100)}%</span>
                </div>
              ))}
            </div>
          </div>
        </div>

        <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
          <div className="card">
            <div className="card-header">
              <div className="card-title">Runs over time</div>
              <span className="micro">BUNDLES / DAY</span>
            </div>
            <div className="card-body"><ActivityChart data={D.activity} /></div>
          </div>
          <div className="card" style={{ flex: 1 }}>
            <div className="card-header">
              <div className="card-title">Instrument identity</div>
              <span className="run-status done"><span className="dot"></span>ok</span>
            </div>
            <div style={{ padding: '14px 20px', display: 'flex', flexDirection: 'column', gap: 8 }}>
              <Kv k="framework" v={'ophamin ' + (D.version || '—')} />
              <Kv k="substrate" v={D.substrate || 'kimera-swm'} mono />
              <Kv k="substrate_commit" v={D.substrate_commit || '—'} mono truncate />
              <Kv k="uptime" v={uptimeStr} mono />
              <Kv k="proof storage" v={storageStr} mono />
            </div>
          </div>
        </div>
      </div>

      {/* Recent proofs */}
      <div className="card">
        <div className="card-header">
          <div className="card-title">Recent runs <span className="micro" style={{ marginLeft: 8 }}>· LAST 8</span></div>
          <button className="btn ghost" onClick={() => onNavToProofs()}>View all <Icon name="chevronR" size={14} /></button>
        </div>
        <table className="table">
          <thead>
            <tr>
              <th style={{ width: 130 }}>Verdict</th>
              <th>Scenario</th>
              <th>Tier</th>
              <th>Observed</th>
              <th style={{ width: 110 }}>Date</th>
              <th style={{ width: 130 }}>Hash</th>
              <th style={{ width: 160 }}>Formats</th>
            </tr>
          </thead>
          <tbody>
            {D.bundles.slice(0, 8).map((b, i) => (
              <tr key={b.path} className="fade-up" style={{ animationDelay: `${i * 25}ms` }}
                onClick={() => onNavToProofs(null, b)}>
                <td><VerdictPill verdict={b.verdict} /></td>
                <td style={{ fontWeight: 500 }}>{b.scenario}</td>
                <td><TierChip tier={b.tier} /></td>
                <td className="mono tnum" style={{ color: 'var(--text-secondary)' }}>{formatNum(b.observed)}</td>
                <td className="col-date">{b.date}</td>
                <td className="col-hash">{b.short_hash}</td>
                <td><FormatBadges files={b.files} /></td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function Kv({ k, v, mono, truncate }) {
  return (
    <div style={{ display: 'flex', alignItems: 'baseline', gap: 12, fontSize: 12 }}>
      <span style={{ color: 'var(--text-muted)', minWidth: 110, fontFamily: 'JetBrains Mono, monospace', fontSize: 11 }}>{k}</span>
      <span className={mono ? 'mono' : ''} style={{ color: 'var(--text-primary)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', maxWidth: truncate ? 160 : 'none' }}>{v}</span>
    </div>);

}

function formatNum(n) {
  if (n === 0) return '0';
  if (typeof n !== 'number') return String(n);
  const abs = Math.abs(n);
  if (abs < 0.001 || abs > 100000) return n.toExponential(2);
  if (abs < 1) return n.toFixed(4);
  if (abs < 100) return n.toFixed(2);
  return n.toFixed(0);
}
window.formatNum = formatNum;

// =====================================================================
// Verdict donut — animated sweep
// =====================================================================
function VerdictDonut({ totals, onSegment, size = 180 }) {
  const cx = size / 2,cy = size / 2,r = size * 0.36,thick = 22;
  const total = totals.validated + totals.refuted + totals.inconclusive;
  const segs = [
  { k: 'validated', v: totals.validated },
  { k: 'inconclusive', v: totals.inconclusive },
  { k: 'refuted', v: totals.refuted }];

  const [hover, setHover] = useOvState(null);
  let cursor = -Math.PI / 2;
  return (
    <svg width={size} height={size} style={{ overflow: 'visible' }}>
      {/* outer ticks */}
      {Array.from({ length: 60 }).map((_, i) => {
        const a = i / 60 * Math.PI * 2 - Math.PI / 2;
        const r1 = r + thick / 2 + 5;
        const r2 = r + thick / 2 + (i % 5 === 0 ? 9 : 7);
        return <line key={i} x1={cx + Math.cos(a) * r1} y1={cy + Math.sin(a) * r1} x2={cx + Math.cos(a) * r2} y2={cy + Math.sin(a) * r2} stroke="var(--text-faint)" strokeWidth="1" opacity={i % 5 === 0 ? 0.6 : 0.25} />;
      })}
      {segs.map((s, i) => {
        const start = cursor;
        const angle = s.v / total * Math.PI * 2;
        const end = start + angle;
        cursor = end;
        const isHover = hover === s.k;
        const ringR = r + (isHover ? 4 : 0);
        const x1 = cx + Math.cos(start) * ringR;
        const y1 = cy + Math.sin(start) * ringR;
        const x2 = cx + Math.cos(end) * ringR;
        const y2 = cy + Math.sin(end) * ringR;
        const large = angle > Math.PI ? 1 : 0;
        const innerR = ringR - thick;
        const ix1 = cx + Math.cos(end) * innerR;
        const iy1 = cy + Math.sin(end) * innerR;
        const ix2 = cx + Math.cos(start) * innerR;
        const iy2 = cy + Math.sin(start) * innerR;
        const path = `M ${x1} ${y1} A ${ringR} ${ringR} 0 ${large} 1 ${x2} ${y2} L ${ix1} ${iy1} A ${innerR} ${innerR} 0 ${large} 0 ${ix2} ${iy2} Z`;
        return (
          <path key={s.k} d={path} fill={`var(--${s.k})`}
          opacity={isHover ? 1 : 0.85}
          onMouseEnter={() => setHover(s.k)}
          onMouseLeave={() => setHover(null)}
          onClick={() => onSegment(s.k)}
          style={{
            cursor: 'pointer',
            filter: isHover ? `drop-shadow(0 0 8px var(--${s.k}))` : 'none',
            transition: 'all 200ms cubic-bezier(0.4,0,0.2,1)',
            transformOrigin: `${cx}px ${cy}px`,
            animation: `donutSweep 900ms cubic-bezier(0.16,1,0.3,1) both`,
            animationDelay: `${i * 100}ms`
          }} />);

      })}
      {/* center */}
      <circle cx={cx} cy={cy} r={r - thick - 6} fill="var(--bg-base)" stroke="var(--border)" />
      <text x={cx} y={cy - 4} textAnchor="middle" fill="var(--text-primary)" fontSize="22" fontWeight="600" fontFamily="JetBrains Mono">{total}</text>
      <text x={cx} y={cy + 14} textAnchor="middle" fill="var(--text-muted)" fontSize="9" letterSpacing="0.18em">BUNDLES</text>
      <style>{`@keyframes donutSweep { from { transform: scale(0.4); opacity: 0; } to { transform: scale(1); opacity: 0.85; } }`}</style>
    </svg>);

}
window.VerdictDonut = VerdictDonut;

// =====================================================================
// Sparkline — UniFi-style gradient area fill
// =====================================================================
function Sparkline({ values, color = 'var(--accent)', width = 90, height = 28 }) {
  const max = Math.max(...values);
  const min = Math.min(...values);
  const range = max - min || 1;
  const step = width / (values.length - 1);
  const pts = values.map((v, i) => [i * step, height - (v - min) / range * (height - 4) - 2]);
  const line = smoothPath(pts);
  const area = line + ` L ${pts[pts.length - 1][0]} ${height} L ${pts[0][0]} ${height} Z`;
  const gid = 'spk-' + Math.random().toString(36).slice(2, 9);
  return (
    <svg width={width} height={height} style={{ display: 'block' }}>
      <defs>
        <linearGradient id={gid} x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor={color} stopOpacity="0.35" />
          <stop offset="100%" stopColor={color} stopOpacity="0" />
        </linearGradient>
      </defs>
      <path d={area} fill={`url(#${gid})`} />
      <path d={line} fill="none" stroke={color} strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
      <circle cx={pts[pts.length - 1][0]} cy={pts[pts.length - 1][1]} r="2.2" fill={color} />
    </svg>);

}
window.Sparkline = Sparkline;

// =====================================================================
// Activity chart — UniFi-style gradient area chart with grid
// =====================================================================
function ActivityChart({ data }) {
  const width = 320,height = 110,padL = 8,padR = 8,padT = 8,padB = 18;
  const max = Math.max(...data.map((d) => d.v));
  const step = (width - padL - padR) / (data.length - 1);
  const pts = data.map((d, i) => [padL + i * step, padT + (height - padT - padB) * (1 - d.v / max)]);
  const line = pts.map((p, i) => `${i === 0 ? 'M' : 'L'} ${p[0]} ${p[1]}`).join(' ');
  const area = line + ` L ${pts[pts.length - 1][0]} ${height - padB} L ${pts[0][0]} ${height - padB} Z`;
  const last = pts[pts.length - 1];
  const [hover, setHover] = useOvState(null);

  const onMove = (e) => {
    const svg = e.currentTarget;
    const r = svg.getBoundingClientRect();
    const x = (e.clientX - r.left) * (width / r.width);
    let nearest = 0,best = Infinity;
    pts.forEach((p, i) => {
      const d = Math.abs(p[0] - x);
      if (d < best) {best = d;nearest = i;}
    });
    setHover({ i: nearest, x: pts[nearest][0], y: pts[nearest][1], svgRect: r });
  };

  return (
    <div style={{ position: 'relative' }}>
      <svg viewBox={`0 0 ${width} ${height}`} width="100%" style={{ display: 'block' }}
      onMouseMove={onMove} onMouseLeave={() => setHover(null)}>
        <defs>
          <linearGradient id="act-grad" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor="var(--accent)" stopOpacity="0.42" />
            <stop offset="100%" stopColor="var(--accent)" stopOpacity="0" />
          </linearGradient>
        </defs>
        {[0.25, 0.5, 0.75, 1].map((f) =>
        <line key={f} x1={padL} x2={width - padR}
        y1={padT + (height - padT - padB) * (1 - f)}
        y2={padT + (height - padT - padB) * (1 - f)}
        stroke="var(--grid)" strokeWidth="1" strokeDasharray="2 4" />
        )}
        <path d={area} fill="url(#act-grad)"
        style={{ animation: 'fadeIn 600ms cubic-bezier(0.16,1,0.3,1) both' }} />
        <path d={line} fill="none" stroke="var(--accent)" strokeWidth="1.5"
        strokeLinecap="round" strokeLinejoin="round"
        style={{ animation: 'fadeIn 600ms cubic-bezier(0.16,1,0.3,1) both' }} />
        {pts.map((p, i) =>
        <circle key={i} cx={p[0]} cy={p[1]} r={i === pts.length - 1 ? 3 : 1.8}
        fill={i === pts.length - 1 ? 'var(--accent)' : 'var(--bg-surface)'}
        stroke="var(--accent)" strokeWidth={i === pts.length - 1 ? 0 : 1} />
        )}
        {!hover &&
        <text x={last[0]} y={last[1] - 6} textAnchor="middle"
        fontSize="9" fill="var(--accent)" fontFamily="JetBrains Mono" fontWeight="600">
            {data[data.length - 1].v}
          </text>
        }
        <text x={padL} y={height - 4} fontSize="9" fill="var(--text-muted)" fontFamily="JetBrains Mono">{data[0].d}</text>
        <text x={width - padR} y={height - 4} fontSize="9" fill="var(--text-muted)" fontFamily="JetBrains Mono" textAnchor="end">{data[data.length - 1].d}</text>

        {/* Hover crosshair */}
        {hover &&
        <g>
            <line x1={hover.x} x2={hover.x} y1={padT} y2={height - padB}
          stroke="var(--accent)" strokeWidth="1" strokeDasharray="3 3" opacity="0.6" />
            <circle cx={hover.x} cy={hover.y} r="4" fill="var(--accent)" stroke="var(--bg-base)" strokeWidth="2" />
          </g>
        }
        <style>{`@keyframes fadeIn { from { opacity: 0; } to { opacity: 1; } }`}</style>
      </svg>
      {hover &&
      <div className="chart-tooltip"
      style={{
        left: `${hover.x / width * 100}%`,
        top: 0,
        transform: 'translate(-50%, -110%)'
      }}>
          <div className="label">{data[hover.i].d}</div>
          <div className="value">{data[hover.i].v} bundles</div>
        </div>
      }
    </div>);

}

// Catmull-Rom → cubic Bezier converter for smooth area charts.
// tension ≈ 0.5 for natural-looking curves; clamped at endpoints.
function smoothPath(pts) {
  if (pts.length < 2) return '';
  if (pts.length === 2) return `M ${pts[0][0]} ${pts[0][1]} L ${pts[1][0]} ${pts[1][1]}`;
  let d = `M ${pts[0][0]} ${pts[0][1]}`;
  for (let i = 0; i < pts.length - 1; i++) {
    const p0 = pts[i - 1] || pts[i];
    const p1 = pts[i];
    const p2 = pts[i + 1];
    const p3 = pts[i + 2] || p2;
    const c1x = p1[0] + (p2[0] - p0[0]) / 6;
    const c1y = p1[1] + (p2[1] - p0[1]) / 6;
    const c2x = p2[0] - (p3[0] - p1[0]) / 6;
    const c2y = p2[1] - (p3[1] - p1[1]) / 6;
    d += ` C ${c1x.toFixed(2)} ${c1y.toFixed(2)}, ${c2x.toFixed(2)} ${c2y.toFixed(2)}, ${p2[0]} ${p2[1]}`;
  }
  return d;
}

window.ActivityChart = ActivityChart;



// =====================================================================
// Standalone screen wrappers — promote views to top-level nav
// =====================================================================
function DriftScreen({ onNavToProofs }) {
  return (
    <div className="content-inner page">
      <div className="page-header">
        <div>
          <h1 className="page-title">Drift</h1>
          <div className="page-subtitle mono">comparing/ wheel · cross-commit retrospection · streaming detectors</div>
        </div>
      </div>
      <DriftView D={OPHAMIN} onNavToProofs={onNavToProofs}/>
    </div>
  );
}
window.DriftScreen = DriftScreen;

function TopologyScreen({ onNavToProofs }) {
  return (
    <div className="content-inner page">
      <div className="page-header">
        <div>
          <h1 className="page-title">Topology</h1>
          <div className="page-subtitle mono">single pane of glass · substrate × tiers × scenarios × bundles · time-machine</div>
        </div>
      </div>
      <TopologyView D={OPHAMIN} onNavToProofs={onNavToProofs}/>
    </div>
  );
}
window.TopologyScreen = TopologyScreen;

window.OverviewScreen = OverviewScreen;

// =====================================================================
// TopologyView — UniFi-style "single pane of glass" topology
// substrate → tiers → scenarios → bundles
// =====================================================================
function TopologyView({ D, onNavToProofs }) {
  const [scrubIdx, setScrubIdx] = useOvState(D.activity.length - 1);
  const tiers = [
  { id: 'engineering', label: 'engineering', color: '#7aa3ff' },
  { id: 'measurement_machinery', label: 'measurement', color: '#2dd4bf' },
  { id: 'scientific', label: 'scientific', color: '#ffa726' },
  { id: 'philosophical', label: 'philosophical', color: '#b89dff' }];

  const W = 1180,H = 560;
  const subX = 200,subY = H / 2;
  const tierX = 560;
  const tierStartY = 80;
  const tierGapY = (H - 160) / (tiers.length - 1);
  const scnX = 760;
  const bundleX = 1010;

  // Compute scenarios per tier
  const tierData = tiers.map((t, ti) => {
    const tY = tierStartY + ti * tierGapY;
    const scenarios = [...new Set(D.bundles.filter((b) => b.tier === t.id).map((b) => b.scenario))];
    return { ...t, y: tY, scenarios, total: D.bundles.filter((b) => b.tier === t.id).length };
  });

  return (
    <div className="card" style={{ overflow: 'hidden', marginBottom: 16 }}>
      <div className="card-header">
        <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
          <div className="card-title">Topology · Substrate × Tiers × Scenarios</div>
          <span className="micro">SINGLE PANE OF GLASS</span>
        </div>
        <span className="live-pill"><span className="dot"></span>{D.activity[scrubIdx].d}</span>
      </div>

      {/* Time-machine slider */}
      <div style={{ padding: '12px 20px', borderBottom: '1px solid var(--border)', background: 'var(--bg-base)' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
          <Icon name="activity" size={13} />
          <span className="micro">TIME-MACHINE</span>
          <span className="mono" style={{ fontSize: 11, color: 'var(--text-muted)' }}>{D.activity[0].d}</span>
          <div style={{ flex: 1, position: 'relative', height: 28, display: 'flex', alignItems: 'center' }}>
            <div style={{ position: 'absolute', left: 0, right: 0, height: 4, background: 'var(--bg-surface-2)', borderRadius: 2, top: 12 }} />
            <div style={{ position: 'absolute', left: 0, height: 4, background: 'var(--accent)', borderRadius: 2, top: 12, width: `${scrubIdx / (D.activity.length - 1) * 100}%` }} />
            {D.activity.map((a, i) =>
            <button key={i} onClick={() => setScrubIdx(i)}
            style={{
              position: 'absolute',
              left: `calc(${i / (D.activity.length - 1) * 100}% - 6px)`,
              width: 12, height: 12, top: 8,
              borderRadius: '50%',
              background: i <= scrubIdx ? 'var(--accent)' : 'var(--bg-surface)',
              border: '2px solid ' + (i === scrubIdx ? 'var(--accent)' : 'var(--border-strong)'),
              cursor: 'pointer',
              padding: 0,
              transition: 'transform 120ms ease'
            }}
            title={a.d}
            onMouseEnter={(e) => e.target.style.transform = 'scale(1.25)'}
            onMouseLeave={(e) => e.target.style.transform = 'scale(1)'} />
            )}
          </div>
          <span className="mono" style={{ fontSize: 11, color: 'var(--text-muted)' }}>{D.activity[D.activity.length - 1].d}</span>
          <span className="mono" style={{ fontSize: 11, color: 'var(--accent)', minWidth: 80, textAlign: 'right' }}>{D.activity[scrubIdx].d} · {D.activity[scrubIdx].v} bundles</span>
        </div>
      </div>

      {/* SVG canvas */}
      <div style={{ background: 'var(--bg-base)', padding: 0, overflow: 'auto' }}>
        <svg viewBox={`0 0 ${W} ${H}`} width="100%" style={{ display: 'block', minWidth: 900, maxHeight: 560 }}>
          <defs>
            <linearGradient id="topo-line-grad" x1="0" x2="1">
              <stop offset="0" stopColor="var(--accent)" stopOpacity="0.6" />
              <stop offset="1" stopColor="var(--accent)" stopOpacity="0.15" />
            </linearGradient>
            <pattern id="topo-grid" width="40" height="40" patternUnits="userSpaceOnUse">
              <path d="M 40 0 L 0 0 0 40" fill="none" stroke="var(--grid)" strokeWidth="1" />
            </pattern>
          </defs>
          <rect width={W} height={H} fill="url(#topo-grid)" />

          {/* Substrate -> tier connections */}
          {tierData.map((t, i) => {
            const x1 = subX + 70,y1 = subY;
            const x2 = tierX - 6,y2 = t.y;
            const cx1 = x1 + 120,cx2 = x2 - 120;
            return (
              <path key={i}
              d={`M ${x1} ${y1} C ${cx1} ${y1}, ${cx2} ${y2}, ${x2} ${y2}`}
              fill="none" stroke={t.color} strokeWidth="1.5" strokeOpacity="0.6" />);

          })}

          {/* Substrate node */}
          <g>
            <rect x={subX - 70} y={subY - 60} width="140" height="120" rx="8"
            fill="var(--bg-surface)" stroke="var(--accent)" strokeWidth="1.5" />
            <rect x={subX - 70} y={subY - 60} width="140" height="28" rx="8"
            fill="var(--accent-soft)" />
            <text x={subX} y={subY - 42} textAnchor="middle" fontSize="10" fill="var(--accent)"
            fontFamily="JetBrains Mono" fontWeight="600" letterSpacing="0.12em">SUBSTRATE</text>
            <text x={subX} y={subY - 18} textAnchor="middle" fontSize="16" fontWeight="600" fill="var(--text-primary)">kimera-swm</text>
            <text x={subX} y={subY + 2} textAnchor="middle" fontSize="10"
            fontFamily="JetBrains Mono" fill="var(--text-muted)">{D.substrate_commit || '—'}</text>
            <circle cx={subX - 50} cy={subY + 26} r="3" fill="var(--validated)" />
            <text x={subX - 42} y={subY + 30} fontSize="10" fill="var(--text-secondary)" fontFamily="JetBrains Mono">healthy</text>
            <text x={subX + 60} y={subY + 30} textAnchor="end" fontSize="10" fill="var(--text-muted)" fontFamily="JetBrains Mono">{D.totals.bundles}b</text>
            <rect x={subX - 70} y={subY + 46} width="140" height="14" rx="0 0 8 8"
            fill="var(--bg-card-head)" />
            <text x={subX} y={subY + 56} textAnchor="middle" fontSize="9" fill="var(--text-muted)"
            fontFamily="JetBrains Mono" letterSpacing="0.06em">{'ophamin ' + (D.version || '—')}</text>
          </g>

          {/* Tier nodes + scenarios + bundle dots */}
          {tierData.map((t) => {
            const bundles = D.bundles.filter((b) => b.tier === t.id);
            // Cumulative bundles "up to" scrub date
            const scrubDate = D.activity[scrubIdx].d;
            return (
              <g key={t.id}>
                {/* tier card */}
                <rect x={tierX - 6} y={t.y - 18} width="180" height="36" rx="6"
                fill="var(--bg-surface)" stroke={t.color} strokeWidth="1" strokeOpacity="0.5" />
                <rect x={tierX - 6} y={t.y - 18} width="3" height="36" fill={t.color} />
                <text x={tierX + 6} y={t.y - 3} fontSize="11" fontWeight="600" fill="var(--text-primary)">{t.label}</text>
                <text x={tierX + 6} y={t.y + 11} fontSize="9" fill="var(--text-muted)" fontFamily="JetBrains Mono">{t.scenarios.length} scenarios · {t.total} bundles</text>

                {/* tier -> scenarios connection */}
                {t.scenarios.slice(0, 5).map((s, si) => {
                  const sy = t.y - 30 + (si - (Math.min(5, t.scenarios.length) - 1) / 2) * 24;
                  const x1 = tierX + 174,y1 = t.y;
                  const x2 = scnX - 4,y2 = sy;
                  const cx1 = x1 + 30,cx2 = x2 - 30;
                  const scnBundles = bundles.filter((b) => b.scenario === s);
                  return (
                    <g key={s}>
                      <path d={`M ${x1} ${y1} C ${cx1} ${y1}, ${cx2} ${y2}, ${x2} ${y2}`}
                      fill="none" stroke={t.color} strokeWidth="1" strokeOpacity="0.35" />
                      {/* scenario node */}
                      <rect x={scnX - 4} y={sy - 9} width="220" height="18" rx="3"
                      fill="var(--bg-surface)" stroke="var(--border)" strokeWidth="1"
                      onClick={() => onNavToProofs(null, scnBundles[0])}
                      style={{ cursor: 'pointer' }} />
                      <text x={scnX + 4} y={sy + 3} fontSize="10" fill="var(--text-secondary)">{s}</text>
                      <text x={scnX + 212} y={sy + 3} textAnchor="end" fontSize="9" fill="var(--text-muted)" fontFamily="JetBrains Mono">{scnBundles.length}</text>
                      {/* bundle dots */}
                      {scnBundles.slice(0, 6).map((b, bi) => {
                        const dx = bundleX + 218 + bi * 9;
                        const dy = sy;
                        const visible = b.date <= scrubDate;
                        const color = b.verdict === 'validated' ? 'var(--validated)' : b.verdict === 'refuted' ? 'var(--refuted)' : 'var(--inconclusive)';
                        return (
                          <circle key={bi} cx={dx} cy={dy} r="3"
                          fill={visible ? color : 'transparent'}
                          stroke={color} strokeWidth={visible ? 0 : 1}
                          opacity={visible ? 1 : 0.35} />);

                      })}
                    </g>);

                })}
                {t.scenarios.length > 5 &&
                <text x={scnX + 110} y={t.y + 60} textAnchor="middle" fontSize="9" fill="var(--text-muted)" fontFamily="JetBrains Mono">+{t.scenarios.length - 5} more</text>
                }
              </g>);

          })}

          {/* Legend */}
          <g transform={`translate(${W - 380}, ${H - 36})`}>
            <text x="0" y="0" fontSize="9" fill="var(--text-muted)" fontFamily="JetBrains Mono" letterSpacing="0.12em">LEGEND</text>
            <circle cx="60" cy="-3" r="3" fill="var(--validated)" />
            <text x="68" y="0" fontSize="10" fill="var(--text-secondary)">validated</text>
            <circle cx="148" cy="-3" r="3" fill="var(--refuted)" />
            <text x="156" y="0" fontSize="10" fill="var(--text-secondary)">refuted</text>
            <circle cx="220" cy="-3" r="3" fill="var(--inconclusive)" />
            <text x="228" y="0" fontSize="10" fill="var(--text-secondary)">inconclusive</text>
          </g>
        </svg>
      </div>
    </div>);

}

// =====================================================================
// ActivityView — larger activity chart + per-day breakdown
// =====================================================================
function ActivityView({ D, range }) {
  const max = Math.max(...D.activity.map((d) => d.v));
  return (
    <div className="card" style={{ marginBottom: 16 }}>
      <div className="card-header">
        <div className="card-title">Activity · {range}</div>
        <span className="micro">BUNDLES OVER TIME · {D.totals.bundles} TOTAL</span>
      </div>
      <div className="card-body" style={{ padding: '16px 20px' }}>
        <div style={{ maxWidth: 920, margin: '0 auto' }}>
          <div style={{ height: 220, position: 'relative' }}>
            <ActivityChart data={D.activity} />
          </div>
        </div>
        <div style={{ marginTop: 18, display: 'grid', gridTemplateColumns: 'repeat(7, 1fr)', gap: 6, maxWidth: 920, margin: '18px auto 0' }}>
          {D.activity.map((a) =>
          <div key={a.d} style={{ background: 'var(--bg-base)', border: '1px solid var(--border)', borderRadius: 'var(--r-sm)', padding: '8px 10px' }}>
              <div className="mono" style={{ fontSize: 10, color: 'var(--text-muted)' }}>{a.d}</div>
              <div className="mono tnum" style={{ fontSize: 18, fontWeight: 600, color: 'var(--accent)' }}>{a.v}</div>
              <div style={{ height: 3, background: 'var(--bg-surface-2)', borderRadius: 2, marginTop: 4 }}>
                <div style={{ height: '100%', width: `${a.v / max * 100}%`, background: 'var(--accent)', borderRadius: 2 }} />
              </div>
            </div>
          )}
        </div>
      </div>
    </div>);

}

// =====================================================================
// DriftView — drift analysis placeholder + visualization
// =====================================================================
function DriftView({ D, onNavToProofs }) {
  // substrate_git_commit-driven drift — splits bundles by which substrate
  // commit they were captured against (the real semantic dimension), not date.
  const commitsInUse = [...new Set(D.bundles.map(b => b.substrate_git_commit))];
  const [commitA, setCommitA] = useOvState(commitsInUse[commitsInUse.length - 2] || commitsInUse[0]);
  const [commitB, setCommitB] = useOvState(commitsInUse[commitsInUse.length - 1] || commitsInUse[0]);

  function latestByScenario(commit) {
    const map = new Map();
    for (const b of D.bundles) {
      if (b.substrate_git_commit !== commit) continue;
      const prev = map.get(b.scenario);
      if (!prev || prev.date < b.date) map.set(b.scenario, b);
    }
    return map;
  }
  const aMap = latestByScenario(commitA);
  const bMap = latestByScenario(commitB);
  const allScenarios = [...new Set([...aMap.keys(), ...bMap.keys()])];

  function transition(a, b) {
    if (!a && !b) return 'absent';
    if (!a) return 'new';
    if (!b) return 'gone';
    if (a.verdict === b.verdict) return 'stable';
    return 'flipped';
  }

  const flips = allScenarios.map(s => {
    const a = aMap.get(s), b = bMap.get(s);
    return { scenario: s, a, b, t: transition(a, b), tier: (a || b).tier };
  });
  const flipCounts = {
    stable:  flips.filter(f => f.t === 'stable').length,
    flipped: flips.filter(f => f.t === 'flipped').length,
    new:     flips.filter(f => f.t === 'new').length,
    gone:    flips.filter(f => f.t === 'gone').length,
  };

  const [selected, setSelected] = useOvState(flips.find(f => f.t === 'flipped') || flips[0]);

  return (
    <div className="card" style={{ marginBottom: 16, overflow: 'hidden' }}>
      <div className="card-header">
        <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
          <div className="card-title">Drift · cross-commit retrospection</div>
          <span className="micro">LAYER C · OPHAMIN COMPARING/</span>
        </div>
        <span className="micro">{flips.length} SCENARIOS · {flipCounts.flipped} FLIPS</span>
      </div>

      <div className="substrate-stamps-strip">
        <div className="micro" style={{ minWidth: 110 }}>SUBSTRATE STATE-STAMPS</div>
        <div style={{ display: 'flex', gap: 6, alignItems: 'center', flex: 1, flexWrap: 'wrap' }}>
          {(window.OPHAMIN.substrateStamps || []).map((s, i, arr) => (
            <React.Fragment key={s.commit}>
              <div className={'stamp-pill' + (i === arr.length - 1 ? ' current' : '')} title={s.note}>
                <span className="mono" style={{ fontSize: 11, fontWeight: 500 }}>{s.commit}</span>
                <span className="mono" style={{ fontSize: 10, color: 'var(--text-muted)', marginLeft: 6 }}>{s.label}</span>
              </div>
              {i < arr.length - 1 && <span className="stamp-arrow">→</span>}
            </React.Fragment>
          ))}
        </div>
      </div>

      <div className="drift-commit-strip">
        <div className="drift-commit">
          <div className="drift-commit-label">COMMIT A · BASELINE</div>
          <div className="mono" style={{ fontSize: 13, fontWeight: 600 }}>{commitA}</div>
          <div className="mono" style={{ fontSize: 10, color: 'var(--text-muted)', marginTop: 2 }}>kimera-swm · substrate commit A</div>
          <div className="mono" style={{ fontSize: 10, color: 'var(--text-muted)' }}>{aMap.size} scn · {[...aMap.values()].filter(b => b.verdict === 'validated').length}V / {[...aMap.values()].filter(b => b.verdict === 'refuted').length}R / {[...aMap.values()].filter(b => b.verdict === 'inconclusive').length}I</div>
        </div>
        <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', gap: 4, padding: '0 20px' }}>
          <span className="drift-arrow"/>
          <div className="micro" style={{ color: 'var(--text-muted)' }}>{flips.length} pairs</div>
        </div>
        <div className="drift-commit drift-commit-b">
          <div className="drift-commit-label">COMMIT B · HEAD</div>
          <div className="mono" style={{ fontSize: 13, fontWeight: 600 }}>{commitB}</div>
          <div className="mono" style={{ fontSize: 10, color: 'var(--text-muted)', marginTop: 2 }}>kimera-swm · substrate commit B</div>
          <div className="mono" style={{ fontSize: 10, color: 'var(--text-muted)' }}>{bMap.size} scn · {[...bMap.values()].filter(b => b.verdict === 'validated').length}V / {[...bMap.values()].filter(b => b.verdict === 'refuted').length}R / {[...bMap.values()].filter(b => b.verdict === 'inconclusive').length}I</div>
        </div>
        <div style={{ flex: 1 }}/>
        <div className="drift-legend">
          <div><span className="drift-legend-dot" style={{ background: 'var(--text-muted)' }}/>stable {flipCounts.stable}</div>
          <div><span className="drift-legend-dot" style={{ background: 'var(--inconclusive)' }}/>flipped {flipCounts.flipped}</div>
          <div><span className="drift-legend-dot" style={{ background: 'var(--accent)' }}/>new {flipCounts.new}</div>
          <div><span className="drift-legend-dot" style={{ background: 'var(--text-faint)' }}/>gone {flipCounts.gone}</div>
        </div>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', minHeight: 480 }}>
        <div style={{ borderRight: '1px solid var(--border)', overflowY: 'auto', maxHeight: 600 }}>
          <table className="table table-dense">
            <thead>
              <tr>
                <th>Scenario</th>
                <th style={{ width: 80 }}>Tier</th>
                <th style={{ width: 88 }}>A</th>
                <th style={{ width: 88 }}>B</th>
                <th style={{ width: 60 }}>Δ</th>
              </tr>
            </thead>
            <tbody>
              {flips.map(f => (
                <tr key={f.scenario} className={selected?.scenario === f.scenario ? 'selected' : ''} onClick={() => setSelected(f)}>
                  <td style={{ fontWeight: 500, fontSize: 12 }}>{f.scenario}</td>
                  <td><TierChip tier={f.tier}/></td>
                  <td>{f.a ? <span className={'verdict-pill ' + f.a.verdict} style={{ fontSize: 10, padding: '1px 6px 1px 5px' }}><span className="dot"></span>{f.a.verdict.slice(0,3)}</span> : <span className="muted mono" style={{ fontSize: 10 }}>—</span>}</td>
                  <td>{f.b ? <span className={'verdict-pill ' + f.b.verdict} style={{ fontSize: 10, padding: '1px 6px 1px 5px' }}><span className="dot"></span>{f.b.verdict.slice(0,3)}</span> : <span className="muted mono" style={{ fontSize: 10 }}>—</span>}</td>
                  <td><span className={'drift-delta drift-delta-' + f.t}>{deltaLabel(f.t)}</span></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <div style={{ overflowY: 'auto', maxHeight: 600 }}>
          {selected ? <BundleDiff a={selected.a} b={selected.b} scenario={selected.scenario} tier={selected.tier} transition={selected.t} onOpen={onNavToProofs}/> : (
            <div className="empty">Select a scenario to inspect the diff.</div>
          )}
        </div>
      </div>

      <div className="drift-streaming">
        <div className="micro" style={{ marginBottom: 8 }}>STREAMING-DRIFT DETECTORS · OPHAMIN DRIFT-DETECT --STREAM --DETECTOR</div>
        <div style={{ display: 'flex', gap: 12 }}>
          <StreamingDetector name="ADWIN" stream="phi_trajectory" status="armed" last_alert="—" library="river"/>
          <StreamingDetector name="KSWIN" stream="walker_halt_rate" status="alerted" last_alert="2 cycles ago" library="river"/>
          <StreamingDetector name="PageHinkley" stream="cycle_wall_time" status="armed" last_alert="—" library="river"/>
        </div>
      </div>
    </div>
  );
}

function deltaLabel(t) {
  return { stable: '·', flipped: '⇄', new: '+', gone: '−', absent: '' }[t] || '';
}

function BundleDiff({ a, b, scenario, tier, transition, onOpen }) {
  const scn = OPHAMIN.scenarios.find(s => s.name === scenario);
  const aProof = a ? OPHAMIN.buildProof(a) : null;
  const bProof = b ? OPHAMIN.buildProof(b) : null;
  const t = scn?.claim?.threshold;
  const delta = (a?.observed != null && b?.observed != null) ? b.observed - a.observed : null;
  const passesA = a && checkClaim(a.observed, t);
  const passesB = b && checkClaim(b.observed, t);
  const isRegression = passesA && !passesB;
  const isImprovement = !passesA && passesB;

  return (
    <div style={{ padding: 16 }}>
      <div style={{ display: 'flex', alignItems: 'flex-start', gap: 12, marginBottom: 14 }}>
        <div style={{ flex: 1 }}>
          <div className="mono" style={{ fontSize: 13, fontWeight: 600, color: 'var(--accent)' }}>{scenario}</div>
          <div style={{ fontSize: 11, color: 'var(--text-muted)', marginTop: 2 }}>
            {transition === 'flipped' && (isRegression ? '⚠ Regression — substrate change degraded this scenario.' : isImprovement ? '✓ Improvement — substrate change resolved this scenario.' : 'Verdict shifted across commits.')}
            {transition === 'stable' && 'Stable across commits.'}
            {transition === 'new' && 'New scenario in commit B — no baseline.'}
            {transition === 'gone' && 'Scenario removed at commit B.'}
          </div>
        </div>
        {b && <button className="btn ghost" style={{ fontSize: 11 }} onClick={() => onOpen(null, b)}><Icon name="external" size={12}/> Open B</button>}
      </div>

      {t && (
        <div style={{ background: 'var(--bg-base)', border: '1px solid var(--border)', borderRadius: 'var(--r-sm)', padding: 10, marginBottom: 12 }}>
          <div className="micro" style={{ marginBottom: 4 }}>CLAIM THRESHOLD</div>
          <div className="mono" style={{ fontSize: 12 }}>
            <span style={{ color: 'var(--text-secondary)' }}>{t.metric}</span>{' '}
            <span style={{ color: 'var(--accent)' }}>{t.comparator}</span>{' '}
            <span style={{ color: 'var(--text-primary)', fontWeight: 500 }}>{t.value}</span>{' '}
            <span style={{ color: 'var(--text-muted)' }}>{t.units}</span>
          </div>
        </div>
      )}

      <div style={{ display: 'grid', gridTemplateColumns: '1fr auto 1fr', gap: 0, alignItems: 'stretch', marginBottom: 12 }}>
        <DiffSide bundle={a} label="A · BASELINE" t={t}/>
        <div style={{ display: 'grid', placeItems: 'center', padding: '0 12px' }}>
          <span className="drift-arrow"/>
        </div>
        <DiffSide bundle={b} label="B · HEAD" t={t}/>
      </div>

      {delta != null && (
        <div className="drift-delta-strip" data-direction={isRegression ? 'regression' : isImprovement ? 'improvement' : 'shift'}>
          <span className="micro">OBSERVED DELTA</span>
          <span className="mono tnum" style={{ fontSize: 16, fontWeight: 600 }}>
            {delta > 0 ? '+' : ''}{formatNum(delta)}
          </span>
          <span style={{ fontSize: 11, color: 'var(--text-muted)' }}>{t?.units}</span>
          <span style={{ flex: 1 }}/>
          <span className="mono" style={{ fontSize: 11 }}>A: {formatNum(a?.observed)} → B: {formatNum(b?.observed)}</span>
        </div>
      )}

      {a && b && aProof && bProof && (
        <div style={{ marginTop: 14 }}>
          <div className="micro" style={{ marginBottom: 8 }}>PILLAR EVIDENCE · DELTA</div>
          <table className="table table-dense" style={{ fontSize: 11 }}>
            <thead>
              <tr><th>Pillar</th><th style={{ width: 80, textAlign: 'right' }}>A</th><th style={{ width: 80, textAlign: 'right' }}>B</th><th style={{ width: 70, textAlign: 'right' }}>Δ</th></tr>
            </thead>
            <tbody>
              {aProof.evidence.slice(0, 4).map((ea, i) => {
                const eb = bProof.evidence[i];
                const d = eb ? eb.statistic_value - ea.statistic_value : null;
                return (
                  <tr key={i} style={{ cursor: 'default' }}>
                    <td className="mono" style={{ color: 'var(--accent)', fontSize: 11 }}>{ea.pillar}</td>
                    <td className="mono tnum" style={{ textAlign: 'right' }}>{formatNum(ea.statistic_value)}</td>
                    <td className="mono tnum" style={{ textAlign: 'right' }}>{eb ? formatNum(eb.statistic_value) : '—'}</td>
                    <td className="mono tnum" style={{ textAlign: 'right', color: d == null ? 'var(--text-muted)' : Math.abs(d) < 0.001 ? 'var(--text-muted)' : d > 0 ? 'var(--refuted)' : 'var(--validated)' }}>
                      {d != null ? (d > 0 ? '+' : '') + formatNum(d) : '—'}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}

      <div style={{ display: 'flex', gap: 6, marginTop: 14 }}>
        <button className="btn primary" style={{ fontSize: 11 }}><Icon name="refresh" size={11}/> Re-run at HEAD</button>
        <button className="btn" style={{ fontSize: 11 }}><Icon name="agents" size={11}/> Bisect commits</button>
      </div>
    </div>
  );
}

function DiffSide({ bundle, label, t }) {
  if (!bundle) {
    return (
      <div className="drift-diff-side" style={{ borderColor: 'var(--border)' }}>
        <div className="micro" style={{ marginBottom: 8 }}>{label}</div>
        <div className="muted" style={{ fontSize: 12 }}>no bundle</div>
      </div>
    );
  }
  const pass = checkClaim(bundle.observed, t);
  return (
    <div className="drift-diff-side" style={{ borderColor: `var(--${bundle.verdict}-line)`, background: `var(--${bundle.verdict}-bg)` }}>
      <div className="micro" style={{ marginBottom: 6, color: `var(--${bundle.verdict})` }}>{label}</div>
      <div className="mono tnum" style={{ fontSize: 22, fontWeight: 600, letterSpacing: '-0.01em', color: pass ? 'var(--validated)' : 'var(--refuted)' }}>
        {formatNum(bundle.observed)}
      </div>
      <div className="mono" style={{ fontSize: 10, color: 'var(--text-muted)', marginTop: 2 }}>{t?.units}</div>
      <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginTop: 8 }}>
        <span className={'verdict-pill ' + bundle.verdict}><span className="dot"></span>{bundle.verdict}</span>
        <span className="mono" style={{ fontSize: 10, color: 'var(--text-muted)' }}>{bundle.short_hash}</span>
      </div>
      <div className="mono" style={{ fontSize: 10, color: 'var(--text-muted)', marginTop: 4 }}>{bundle.date}</div>
    </div>
  );
}

function StreamingDetector({ name, stream, status, last_alert, library }) {
  return (
    <div className="streaming-detector">
      <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 4 }}>
        <span className={'streaming-dot streaming-' + status}/>
        <span className="mono" style={{ fontSize: 12, fontWeight: 500 }}>{name}</span>
        <span className="mono" style={{ fontSize: 10, color: 'var(--text-muted)', marginLeft: 'auto' }}>{library}</span>
      </div>
      <div className="mono" style={{ fontSize: 10, color: 'var(--text-secondary)' }}>{stream}</div>
      <div style={{ fontSize: 10, color: status === 'alerted' ? 'var(--refuted)' : 'var(--text-muted)', marginTop: 2 }}>
        {status === 'alerted' ? '⚠ alert · ' + last_alert : 'no drift · ' + last_alert}
      </div>
    </div>
  );
}

function checkClaim(observed, t) {
  if (observed == null || !t) return null;
  switch (t.comparator) {
    case '<=': return observed <= t.value;
    case '<':  return observed < t.value;
    case '>=': return observed >= t.value;
    case '>':  return observed > t.value;
    case '==': return observed === t.value;
    default:   return null;
  }
}
