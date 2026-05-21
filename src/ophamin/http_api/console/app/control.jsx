/** @jsxRuntime classic */ /** @jsx React.createElement */
/* global React, OPHAMIN, Icon, Sparkline */
// Control Room — single live operational surface with two perspectives:
//   1. Ophamin Instrument (framework itself)
//   2. Kimera Substrate (substrate under test)

const { useState: useCrState, useEffect: useCrEffect, useRef: useCrRef } = React;

function ControlRoomScreen() {
  const [perspective, setPerspective] = useCrState('ophamin');
  const [tab, setTab] = useCrState('live');
  const [tick, setTick] = useCrState(0);

  // Heartbeat — drives the simulated live data so the room feels alive
  useCrEffect(() => {
    const id = setInterval(() => setTick(t => t + 1), 1200);
    return () => clearInterval(id);
  }, []);

  return (
    <div className="cr-root">
      <div className="cr-header">
        <div>
          <h1 className="page-title">Control Room</h1>
          <div className="page-subtitle">
            {perspective === 'ophamin'
              ? 'Live view of the Ophamin instrument itself.'
              : 'Live view of the Kimera-SWM substrate under test.'}
          </div>
        </div>
        <div className="cr-perspective-switch">
          <button
            className={perspective === 'ophamin' ? 'active' : ''}
            onClick={() => setPerspective('ophamin')}>
            <span className="cr-switch-dot" style={{ background: 'var(--accent)' }}/>
            Ophamin instrument
          </button>
          <button
            className={perspective === 'kimera' ? 'active' : ''}
            onClick={() => setPerspective('kimera')}>
            <span className="cr-switch-dot" style={{ background: '#ffa726' }}/>
            Kimera substrate
          </button>
        </div>
      </div>

      <div className="cr-subtabs">
        <div className={'cr-subtab' + (tab === 'live' ? ' active' : '')} onClick={() => setTab('live')}>
          <Icon name="activity" size={12}/> Live cockpit
        </div>
        <div className={'cr-subtab' + (tab === 'parameters' ? ' active' : '')} onClick={() => setTab('parameters')}>
          <Icon name="cpu" size={12}/> Parameters
        </div>
        <div className={'cr-subtab' + (tab === 'containers' ? ' active' : '')} onClick={() => setTab('containers')}>
          <Icon name="settings" size={12}/> Containers
        </div>
        <div className={'cr-subtab' + (tab === 'databases' ? ' active' : '')} onClick={() => setTab('databases')}>
          <Icon name="proofs" size={12}/> Databases
        </div>
        <div className={'cr-subtab' + (tab === 'logs' ? ' active' : '')} onClick={() => setTab('logs')}>
          <Icon name="code" size={12}/> Logs
        </div>
        <span style={{ flex: 1 }}/>
        <span className="mono" style={{ fontSize: 10, color: 'var(--text-muted)' }}>
          {perspective === 'ophamin' ? 'ophamin 0.64.1 @ 3f0763a' : 'kimera-swm 0.8.5 @ 6e4477e'}
        </span>
      </div>

      {tab === 'live'       && (perspective === 'ophamin' ? <OphaminCockpit tick={tick}/> : <KimeraCockpit tick={tick}/>)}
      {tab === 'parameters' && <ParametersPanel perspective={perspective}/>}
      {tab === 'containers' && <ContainersPanel/>}
      {tab === 'databases'  && <DatabasesPanel/>}
      {tab === 'logs'       && <LogsPanel perspective={perspective}/>}
    </div>
  );
}

// ─── Ophamin instrument cockpit ─────────────────────────────────
function OphaminCockpit({ tick }) {
  const D = OPHAMIN;
  const rps = 8 + Math.sin(tick / 4) * 2 + Math.random();
  const signed = D.totals.bundles + Math.floor(tick / 8);
  const sparkRps = Array.from({ length: 20 }, (_, i) => 8 + Math.sin((tick + i) / 4) * 2 + Math.random() * 1.5);

  return (
    <>
      <div className="cr-vitals">
        <Vital label="HTTP req/s" value={rps.toFixed(1)}        trend={sparkRps} color="var(--accent)" healthy/>
        <Vital label="Signed today" value={signed}              trend={[12,14,17,19,22,26,30,33,signed]} color="var(--validated)" healthy/>
        <Vital label="Hardening" value="2,944/2,944"            trend={[2900,2920,2935,2944,2944,2944,2944,2944]} color="var(--validated)" healthy sub="all green"/>
        <Vital label="Disk free" value="172 GiB"                trend={[178,176,175,174,173,172,172,172]} color="var(--text-secondary)" sub="of 200 GiB"/>
        <Vital label="Active runs" value="1"                    trend={[0,0,0,1,2,1,1,1,1]} color="var(--inconclusive)" sub="logic-topology-siege" pulsing/>
        <Vital label="MCP clients" value="3"                    trend={[1,1,2,2,3,3,3,3,3]} color="var(--accent)" sub="claude · cursor · cline" healthy/>
      </div>

      <div className="cr-body">
        <div className="cr-main">
          <div className="card">
            <div className="card-header">
              <div>
                <div className="card-title">HTTP load · last 60s</div>
                <div className="micro" style={{ marginTop: 2 }}>REQUESTS PER SECOND</div>
              </div>
              <span className="live-pill"><span className="dot"></span>live</span>
            </div>
            <div style={{ padding: 24 }}>
              <BigSpark values={sparkRps} color="var(--accent)" height={140}/>
              <div className="cr-route-strip">
                <RouteBar label="/proofs/bundles/file"      pct={42}/>
                <RouteBar label="/proofs/bundles/tree"      pct={28}/>
                <RouteBar label="/scenarios"                pct={14}/>
                <RouteBar label="/health"                   pct={9}/>
                <RouteBar label="/verify"                   pct={4}/>
                <RouteBar label="/scenarios/{name}/run"     pct={3}/>
              </div>
            </div>
          </div>

          <div className="cr-grid-2">
            <div className="card">
              <div className="card-header">
                <div className="card-title">Six wheels · last-fire</div>
                <span className="micro">SECONDS SINCE LAST EVENT</span>
              </div>
              <div style={{ padding: '10px 16px' }}>
                {D.wheels.map(w => (
                  <div key={w.id} className="cr-wheel-row">
                    <span style={{ width: 8, height: 8, borderRadius: 2, background: w.color, flexShrink: 0 }}/>
                    <span className="mono" style={{ flex: 1, fontSize: 12, color: 'var(--text-primary)' }}>{w.label.toLowerCase()}</span>
                    <span className="mono tnum" style={{ fontSize: 11, color: 'var(--text-muted)' }}>{((tick * 1.2 + w.id.charCodeAt(0)) % 30).toFixed(1)}s</span>
                    <span className={'cr-wheel-pulse' + (Math.random() > 0.5 ? ' on' : '')} style={{ background: w.color }}/>
                  </div>
                ))}
              </div>
            </div>

            <div className="card">
              <div className="card-header">
                <div className="card-title">Continuous gates</div>
                <span className="live-pill ok"><span className="dot"></span>all green</span>
              </div>
              <div style={{ padding: 14, display: 'flex', flexDirection: 'column', gap: 6 }}>
                <Gate label="Hardening"          status="ok"  detail="2,944 pins · last 12s ago"/>
                <Gate label="Smoke (5-cycle)"    status="ok"  detail="exit 0 · 3.2s elapsed"/>
                <Gate label="Ophamin signing"    status="ok"  detail="8/8 signed · last 47s ago"/>
                <Gate label="Broad-except scan"  status="ok"  detail="4/4 baseline · no new"/>
                <Gate label="Non-deletion"       status="ok"  detail="no primitive removals"/>
              </div>
            </div>
          </div>
        </div>

        <aside className="cr-side">
          <div className="card cr-feed">
            <div className="card-header">
              <div className="card-title">Live activity</div>
              <span className="live-pill"><span className="dot"></span>streaming</span>
            </div>
            <div className="cr-feed-body">
              {ophaminFeed(tick).map((e, i) => (
                <FeedRow key={i} {...e}/>
              ))}
            </div>
          </div>

          <div className="card">
            <div className="card-header">
              <div className="card-title">Quick actions</div>
            </div>
            <div style={{ padding: 10, display: 'flex', flexDirection: 'column', gap: 6 }}>
              <ActionRow icon="refresh"  label="Reindex bundles"  cmd="POST /proofs/index"/>
              <ActionRow icon="play"     label="Run self-test"    cmd="ophamin self-test"/>
              <ActionRow icon="download" label="Export DD snapshot" cmd="ophamin snapshot --sign"/>
              <ActionRow icon="cpu"      label="Rotate sign key"  cmd="ophamin key rotate" danger/>
            </div>
          </div>
        </aside>
      </div>
    </>
  );
}

// ─── Kimera substrate cockpit ───────────────────────────────────
function KimeraCockpit({ tick }) {
  const phi = 0.284 + Math.sin(tick / 3) * 0.04 + Math.random() * 0.01;
  const coherence = 0.871 + Math.sin(tick / 5) * 0.02;
  const cycleMs = 1010 + Math.random() * 80;
  const scarRate = 12 + Math.sin(tick / 6) * 3;

  const sparkPhi = Array.from({ length: 24 }, (_, i) => 0.28 + Math.sin((tick + i) / 3) * 0.04 + Math.random() * 0.01);
  const sparkCoh = Array.from({ length: 24 }, (_, i) => 0.87 + Math.sin((tick + i) / 5) * 0.02);

  // Walker mode distribution (M1/M2/M3/M4)
  const modes = {
    M1: 62 + Math.floor(Math.sin(tick/4) * 5),
    M2: 18 + Math.floor(Math.cos(tick/5) * 3),
    M3: 12,
    M4:  8,
  };

  return (
    <>
      <div className="cr-vitals">
        <Vital label="Φ · IIT" value={phi.toFixed(3)}             trend={sparkPhi} color="#ffa726" healthy pulsing/>
        <Vital label="Coherence" value={coherence.toFixed(3)}     trend={sparkCoh} color="#2dd4bf" healthy/>
        <Vital label="Cycle p95" value={cycleMs.toFixed(0) + 'ms'} trend={[920,1010,950,1080,1100,990,1010,cycleMs]} color="var(--text-primary)" sub="≤ 4000ms ceiling"/>
        <Vital label="Scars / hr" value={scarRate.toFixed(0)}     trend={[8,9,11,12,13,11,12,scarRate]} color="#b89dff" sub="14d avg: 11"/>
        <Vital label="GWF block" value="3.2%"                     trend={[5.1,4.8,4.2,3.9,3.6,3.4,3.2,3.2]} color="var(--validated)" sub="benign FP · target ≤ 10%" healthy/>
      </div>

      <div className="cr-body">
        <div className="cr-main">
          <div className="card">
            <div className="card-header">
              <div>
                <div className="card-title">Φ &amp; coherence · last 24 cycles</div>
                <div className="micro" style={{ marginTop: 2 }}>KCCL CANONICAL TRAJECTORY</div>
              </div>
              <span className="live-pill" style={{ color: '#ffa726', background: 'rgba(255,167,38,0.14)', borderColor: 'rgba(255,167,38,0.28)' }}>
                <span className="dot" style={{ background: '#ffa726' }}></span>cycling
              </span>
            </div>
            <div style={{ padding: 24 }}>
              <DualSpark a={sparkPhi} b={sparkCoh} aColor="#ffa726" bColor="#2dd4bf" height={140}/>
              <div className="cr-legend-strip">
                <span style={{ display: 'flex', alignItems: 'center', gap: 6 }}><span style={{ width: 12, height: 2, background: '#ffa726' }}/>Φ (IIT)</span>
                <span style={{ display: 'flex', alignItems: 'center', gap: 6 }}><span style={{ width: 12, height: 2, background: '#2dd4bf' }}/>graph coherence</span>
                <span style={{ flex: 1 }}/>
                <span className="mono" style={{ fontSize: 11, color: 'var(--text-muted)' }}>cycle index {Math.floor(tick / 2) + 2841}</span>
              </div>
            </div>
          </div>

          <div className="cr-grid-2">
            <div className="card">
              <div className="card-header">
                <div className="card-title">Walker mode distribution</div>
                <span className="micro">LAST 100 CYCLES</span>
              </div>
              <div style={{ padding: '14px 16px' }}>
                <div className="cr-mode-bar">
                  <div style={{ width: modes.M1 + '%', background: 'var(--validated)' }}/>
                  <div style={{ width: modes.M2 + '%', background: 'var(--inconclusive)' }}/>
                  <div style={{ width: modes.M3 + '%', background: 'var(--refuted)' }}/>
                  <div style={{ width: modes.M4 + '%', background: '#b89dff' }}/>
                </div>
                <div className="cr-mode-legend">
                  <span><span style={{ background: 'var(--validated)' }}/>M1 COMMIT <b>{modes.M1}%</b></span>
                  <span><span style={{ background: 'var(--inconclusive)' }}/>M2 HALT <b>{modes.M2}%</b></span>
                  <span><span style={{ background: 'var(--refuted)' }}/>M3 ROLLBACK <b>{modes.M3}%</b></span>
                  <span><span style={{ background: '#b89dff' }}/>M4 LATERAL <b>{modes.M4}%</b></span>
                </div>
              </div>
            </div>

            <div className="card">
              <div className="card-header">
                <div className="card-title">Substrate identity</div>
                <span className="live-pill ok"><span className="dot"></span>healthy</span>
              </div>
              <div style={{ padding: 14, display: 'flex', flexDirection: 'column', gap: 8, fontSize: 12.5 }}>
                <Kv k="name" v="kimera-swm"/>
                <Kv k="commit" v="6e4477ebb" mono/>
                <Kv k="encoder" v="BGE-M3 (1024-d, MPS)"/>
                <Kv k="cycles since boot" v={(Math.floor(tick / 2) + 2841).toLocaleString()} mono/>
                <Kv k="last cycle" v="0.2s ago"/>
                <Kv k="vault size" v="2,134 scars"/>
                <Kv k="arachne primes" v="48,591 assigned"/>
                <Kv k="uptime" v="2d 3h 12m"/>
              </div>
            </div>
          </div>
        </div>

        <aside className="cr-side">
          <div className="card cr-feed">
            <div className="card-header">
              <div className="card-title">Cycle stream</div>
              <span className="live-pill" style={{ color: '#ffa726', background: 'rgba(255,167,38,0.14)', borderColor: 'rgba(255,167,38,0.28)' }}>
                <span className="dot" style={{ background: '#ffa726', animation: 'pulse-dot 0.8s ease-in-out infinite' }}></span>13Hz Cronos pulse
              </span>
            </div>
            <div className="cr-feed-body">
              {kimeraFeed(tick).map((e, i) => (
                <FeedRow key={i} {...e}/>
              ))}
            </div>
          </div>

          <div className="card">
            <div className="card-header">
              <div className="card-title">Substrate actions</div>
            </div>
            <div style={{ padding: 10, display: 'flex', flexDirection: 'column', gap: 6 }}>
              <ActionRow icon="play"     label="Fresh Takwin"        cmd="Takwin().run(prompt)"/>
              <ActionRow icon="download" label="Dump trajectory"     cmd="trajectory.json"/>
              <ActionRow icon="cpu"      label="Capture state stamp" cmd="substrate_state_stamp()"/>
              <ActionRow icon="x"        label="Halt cycle loop"     cmd="cycle_loop.stop()" danger/>
            </div>
          </div>
        </aside>
      </div>
    </>
  );
}

// ─── Primitive components ───────────────────────────────────────
function Vital({ label, value, trend, color, sub, healthy, pulsing }) {
  return (
    <div className="cr-vital">
      <div className="cr-vital-head">
        <span className="cr-vital-label">{label}</span>
        {pulsing && <span className="cr-vital-pulse" style={{ background: color }}/>}
      </div>
      <div className="cr-vital-value mono tnum" style={{ color }}>{value}</div>
      <div className="cr-vital-foot">
        <Sparkline values={trend} color={color} width={80} height={20}/>
        <span className="cr-vital-sub">{sub || (healthy ? 'nominal' : '')}</span>
      </div>
    </div>
  );
}

function BigSpark({ values, color, height = 120 }) {
  const w = 600, h = height, pad = 8;
  const max = Math.max(...values), min = Math.min(...values);
  const range = max - min || 1;
  const step = (w - pad * 2) / (values.length - 1);
  const pts = values.map((v, i) => [pad + i * step, pad + (h - pad * 2) * (1 - (v - min) / range)]);
  const path = pts.map((p, i) => (i === 0 ? 'M' : 'L') + p[0] + ' ' + p[1]).join(' ');
  const area = path + ` L ${pts[pts.length-1][0]} ${h-pad} L ${pts[0][0]} ${h-pad} Z`;
  const gid = 'bs-' + Math.random().toString(36).slice(2, 6);
  return (
    <svg viewBox={`0 0 ${w} ${h}`} width="100%" style={{ display: 'block' }}>
      <defs>
        <linearGradient id={gid} x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor={color} stopOpacity="0.35"/>
          <stop offset="100%" stopColor={color} stopOpacity="0"/>
        </linearGradient>
      </defs>
      {[0.25, 0.5, 0.75].map(f => (
        <line key={f} x1={pad} x2={w - pad} y1={pad + (h - pad * 2) * f} y2={pad + (h - pad * 2) * f}
          stroke="var(--grid)" strokeDasharray="2 4"/>
      ))}
      <path d={area} fill={`url(#${gid})`}/>
      <path d={path} stroke={color} strokeWidth="1.8" fill="none" strokeLinecap="round" strokeLinejoin="round"/>
      <circle cx={pts[pts.length-1][0]} cy={pts[pts.length-1][1]} r="4" fill={color}/>
      <circle cx={pts[pts.length-1][0]} cy={pts[pts.length-1][1]} r="8" fill={color} opacity="0.25">
        <animate attributeName="r" values="4;12;4" dur="1.6s" repeatCount="indefinite"/>
        <animate attributeName="opacity" values="0.4;0;0.4" dur="1.6s" repeatCount="indefinite"/>
      </circle>
    </svg>
  );
}

function DualSpark({ a, b, aColor, bColor, height = 140 }) {
  const w = 600, h = height, pad = 8;
  function pathFor(values, color, gid) {
    const max = Math.max(...values), min = Math.min(...values);
    const range = max - min || 1;
    const step = (w - pad * 2) / (values.length - 1);
    const pts = values.map((v, i) => [pad + i * step, pad + (h - pad * 2) * (1 - (v - min) / range)]);
    const path = pts.map((p, i) => (i === 0 ? 'M' : 'L') + p[0] + ' ' + p[1]).join(' ');
    return { path, last: pts[pts.length - 1], color, gid };
  }
  const ga = 'ga-' + Math.random().toString(36).slice(2, 6);
  const gb = 'gb-' + Math.random().toString(36).slice(2, 6);
  const A = pathFor(a, aColor, ga);
  const B = pathFor(b, bColor, gb);
  return (
    <svg viewBox={`0 0 ${w} ${h}`} width="100%" style={{ display: 'block' }}>
      {[0.25, 0.5, 0.75].map(f => (
        <line key={f} x1={pad} x2={w - pad} y1={pad + (h - pad * 2) * f} y2={pad + (h - pad * 2) * f}
          stroke="var(--grid)" strokeDasharray="2 4"/>
      ))}
      <path d={A.path} stroke={A.color} strokeWidth="1.8" fill="none" strokeLinecap="round"/>
      <path d={B.path} stroke={B.color} strokeWidth="1.8" fill="none" strokeLinecap="round"/>
      <circle cx={A.last[0]} cy={A.last[1]} r="3.5" fill={A.color}/>
      <circle cx={B.last[0]} cy={B.last[1]} r="3.5" fill={B.color}/>
    </svg>
  );
}

function RouteBar({ label, pct }) {
  return (
    <div className="cr-route-row">
      <span className="mono" style={{ fontSize: 11, color: 'var(--text-primary)', flex: 1, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{label}</span>
      <div className="cr-route-bar"><div style={{ width: pct + '%' }}/></div>
      <span className="mono tnum" style={{ fontSize: 11, color: 'var(--text-muted)', width: 36, textAlign: 'right' }}>{pct}%</span>
    </div>
  );
}

function Gate({ label, status, detail }) {
  return (
    <div className="cr-gate">
      <span className={'cr-gate-icon ' + status}>
        {status === 'ok' && <Icon name="check" size={11}/>}
        {status === 'fail' && <Icon name="x" size={11}/>}
        {status === 'pending' && '·'}
      </span>
      <div style={{ flex: 1, minWidth: 0 }}>
        <div style={{ fontSize: 12, color: 'var(--text-primary)' }}>{label}</div>
        <div className="mono" style={{ fontSize: 10, color: 'var(--text-muted)', marginTop: 2 }}>{detail}</div>
      </div>
    </div>
  );
}

function FeedRow({ time, kind, text, hash }) {
  const colorMap = { proof: 'var(--validated)', http: 'var(--accent)', gate: 'var(--validated)', cycle: '#ffa726', gwf: 'var(--accent)', scar: '#b89dff', halt: 'var(--inconclusive)', emit: '#2dd4bf', sign: 'var(--validated)' };
  return (
    <div className="cr-feed-row">
      <span className="mono" style={{ fontSize: 10, color: 'var(--text-faint)', width: 50 }}>{time}</span>
      <span className="cr-feed-kind" style={{ color: colorMap[kind] || 'var(--text-secondary)' }}>{kind}</span>
      <span style={{ flex: 1, fontSize: 11.5, color: 'var(--text-primary)' }}>{text}</span>
      {hash && <span className="mono" style={{ fontSize: 10, color: 'var(--text-muted)' }}>{hash}</span>}
    </div>
  );
}

function ActionRow({ icon, label, cmd, danger }) {
  return (
    <button className="cr-action" style={danger ? { borderColor: 'var(--refuted-line)' } : null}>
      <Icon name={icon} size={13}/>
      <div style={{ flex: 1, minWidth: 0, textAlign: 'left' }}>
        <div style={{ fontSize: 12, fontWeight: 500, color: danger ? 'var(--refuted)' : 'var(--text-primary)' }}>{label}</div>
        <div className="mono" style={{ fontSize: 10, color: 'var(--text-muted)' }}>{cmd}</div>
      </div>
    </button>
  );
}

function Kv({ k, v, mono }) {
  return (
    <div style={{ display: 'flex', alignItems: 'baseline', gap: 12 }}>
      <span className="mono" style={{ color: 'var(--text-muted)', fontSize: 11, minWidth: 130 }}>{k}</span>
      <span className={mono ? 'mono' : ''} style={{ color: 'var(--text-primary)' }}>{v}</span>
    </div>
  );
}

// ─── Mock event streams ─────────────────────────────────────────
function ophaminFeed(tick) {
  const base = [
    { time: 'now',    kind: 'http',  text: 'GET /proofs/bundles/file · 4ms', hash: '200' },
    { time: '0:01',   kind: 'sign',  text: 'signed concentrated-immune-siege proof', hash: '6d47d8c9' },
    { time: '0:03',   kind: 'http',  text: 'GET /proofs/bundles/tree · 28ms', hash: '200' },
    { time: '0:08',   kind: 'gate',  text: 'hardening gate passed · 2,944/2,944' },
    { time: '0:14',   kind: 'http',  text: 'GET /scenarios · 2ms', hash: '200' },
    { time: '0:21',   kind: 'proof', text: 'new bundle indexed · throughput-ceiling validated', hash: '69197dbc' },
    { time: '0:34',   kind: 'http',  text: 'POST /verify · 11ms', hash: '200' },
    { time: '0:42',   kind: 'sign',  text: 'signed substrate-completeness proof', hash: 'b22c0418' },
    { time: '0:58',   kind: 'gate',  text: 'broad-except scan · 4/4 baseline' },
    { time: '1:04',   kind: 'http',  text: 'GET /metrics · 1ms', hash: '200' },
  ];
  return base.slice(0, 8 + (tick % 3));
}

function kimeraFeed(tick) {
  const base = [
    { time: 'now',    kind: 'cycle', text: 'Takwin.run cycle complete · M1 COMMIT · Φ=0.284' },
    { time: '0:01',   kind: 'emit',  text: 'rosetta_stele deposit · text channel · "entropy"' },
    { time: '0:02',   kind: 'gwf',   text: 'GWF allow · benign · score=0.04' },
    { time: '0:04',   kind: 'cycle', text: 'walker traversal · 7 hops · M1 → M2 → M1' },
    { time: '0:05',   kind: 'scar',  text: 'scar formed · contradiction-gate fired · key #2135' },
    { time: '0:07',   kind: 'emit',  text: 'piovra arm 3 · field deposit · ESC-50 clip' },
    { time: '0:09',   kind: 'cycle', text: 'KCCL pulse 13Hz · cycle_seconds=1.012' },
    { time: '0:11',   kind: 'gwf',   text: 'GWF allow · benign · score=0.02' },
    { time: '0:13',   kind: 'halt',  text: 'M2 HALT · self-reference detected' },
    { time: '0:15',   kind: 'cycle', text: 'prime_chain extracted · [2, 7, 13, 17, 23, 31]' },
  ];
  return base.slice(0, 8 + (tick % 3));
}

window.ControlRoomScreen = ControlRoomScreen;
