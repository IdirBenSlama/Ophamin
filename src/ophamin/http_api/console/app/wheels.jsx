/** @jsxRuntime classic */ /** @jsx React.createElement */
/* global React */
// Six Wheels — Ophamin's signature radial. Six concentric arcs rotating
// at different rates with tick marks at the edge, labels around the
// perimeter. Doubles as the hero ring and the loader (smaller variant).

const { useState, useEffect, useRef } = React;

function SixWheelsRing({ size = 280, wheels, interactive = true, mode = 'health' }) {
  const cx = size / 2;
  const cy = size / 2;
  const center = size / 2;
  const baseR = size * 0.18;
  const ringGap = (size * 0.32) / 6;
  const [active, setActive] = useState(null);

  // tick ring
  const tickCount = 60;
  const tickR = size * 0.49;
  const ticks = [];
  for (let i = 0; i < tickCount; i++) {
    const a = (i / tickCount) * Math.PI * 2 - Math.PI / 2;
    const isMajor = i % 5 === 0;
    const r1 = tickR;
    const r2 = tickR - (isMajor ? 6 : 3);
    ticks.push(
      <line key={i}
        x1={cx + Math.cos(a) * r1} y1={cy + Math.sin(a) * r1}
        x2={cx + Math.cos(a) * r2} y2={cy + Math.sin(a) * r2}
        className="tick"
        strokeWidth={isMajor ? 1.5 : 1}
        opacity={isMajor ? 0.8 : 0.35}
      />
    );
  }

  // angle labels for wheels — equispaced around the ring perimeter
  const labels = wheels.map((w, i) => {
    const a = (i / wheels.length) * Math.PI * 2 - Math.PI / 2;
    const r = size * 0.555;
    const x = cx + Math.cos(a) * r;
    const y = cy + Math.sin(a) * r;
    return (
      <g key={w.id}>
        <text x={x} y={y} textAnchor="middle" dominantBaseline="middle"
          className={'label' + (active === w.id ? ' active' : '')}>
          {w.label}
        </text>
      </g>
    );
  });

  return (
    <div style={{ position: 'relative', width: size, height: size + 40, margin: '0 auto' }}>
      <svg
        viewBox={`-${size * 0.13} -${size * 0.13} ${size * 1.26} ${size * 1.26}`}
        width={size + size * 0.26}
        height={size + size * 0.26}
        className="wheels-svg"
        style={{ overflow: 'visible' }}
      >
        {/* outer tick ring */}
        <g>{ticks}</g>

        {/* major axis tick (north only — orient the instrument) */}
        <line x1={cx} y1={cy - tickR - 6} x2={cx} y2={cy - tickR - 12} stroke="var(--accent)" strokeWidth="1.2" />

        {/* labels */}
        {labels}

        {/* six wheels — concentric rings with gap arc indicating health */}
        {wheels.map((w, i) => {
          const r = baseR + i * ringGap;
          const c = 2 * Math.PI * r;
          const dash = c * w.health;
          const period = 8 + i * 3;
          const direction = i % 2 === 0 ? 1 : -1;
          const isActive = active === w.id;
          // Trail (dim track)
          // Active arc (bright, dashed)
          return (
            <g key={w.id}
              onMouseEnter={() => interactive && setActive(w.id)}
              onMouseLeave={() => interactive && setActive(null)}
              style={{ cursor: interactive ? 'pointer' : 'default' }}
            >
              {/* dim track */}
              <circle cx={cx} cy={cy} r={r}
                fill="none"
                stroke="var(--border)"
                strokeWidth={isActive ? 8 : 7}
                opacity={0.45}
              />
              {/* health arc */}
              <g style={{
                transformOrigin: `${cx}px ${cy}px`,
                animation: `${direction > 0 ? 'spin' : 'spin-rev'} ${period}s linear infinite`
              }}>
                <circle cx={cx} cy={cy} r={r}
                  fill="none"
                  stroke={w.color}
                  strokeWidth={isActive ? 7 : 5}
                  strokeDasharray={`${dash} ${c - dash}`}
                  strokeLinecap="round"
                  opacity={isActive ? 1 : 0.85}
                  className="arc"
                />
                {/* head dot */}
                <circle cx={cx + r} cy={cy} r={isActive ? 3.5 : 2.5} fill={w.color}/>
              </g>
            </g>
          );
        })}

        {/* center marker */}
        <circle cx={cx} cy={cy} r={baseR - 12} fill="var(--bg-base)" stroke="var(--border)" strokeWidth="1" />
        <circle cx={cx} cy={cy} r="2" fill="var(--text-secondary)" />
      </svg>
      {/* center caption */}
      <div style={{
        position: 'absolute',
        left: 0, right: 0,
        top: cy + (size * 0.13) + 22,
        textAlign: 'center',
        pointerEvents: 'none',
      }}>
        <div style={{ fontSize: 9, letterSpacing: '0.18em', color: 'var(--text-muted)', textTransform: 'uppercase', fontFamily: 'JetBrains Mono, monospace', minHeight: 14 }}>
          {active ? wheels.find(w => w.id === active).label : ''}
        </div>
        <div style={{ fontSize: 10, color: 'var(--text-secondary)', marginTop: 2, height: 14 }}>
          {active ? wheels.find(w => w.id === active).desc : ''}
        </div>
      </div>
    </div>
  );
}

// Small spinner variant — the brand loader
function SixWheelsLoader({ size = 48 }) {
  return (
    <svg width={size} height={size} viewBox="0 0 100 100" style={{ display: 'block' }}>
      {[0,1,2,3,4,5].map(i => {
        const r = 14 + i * 5.5;
        const c = 2 * Math.PI * r;
        return (
          <g key={i} style={{
            transformOrigin: '50px 50px',
            animation: `${i % 2 === 0 ? 'spin' : 'spin-rev'} ${1.4 + i * 0.4}s linear infinite`
          }}>
            <circle cx="50" cy="50" r={r}
              fill="none"
              stroke="var(--accent)"
              strokeWidth="2"
              strokeLinecap="round"
              strokeDasharray={`${c * 0.35} ${c * 0.65}`}
              opacity={0.4 + i * 0.1}
            />
          </g>
        );
      })}
      <circle cx="50" cy="50" r="2" fill="var(--accent)" />
    </svg>
  );
}

window.SixWheelsRing = SixWheelsRing;
window.SixWheelsLoader = SixWheelsLoader;
