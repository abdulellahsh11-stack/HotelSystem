/* @jsx React.createElement */
/* global React */

/* Revenue chart (SVG bar/area) */
function RevenueChart() {
  const data = [
    { d: "س",  v: 18 }, { d: "أ",  v: 22 }, { d: "اث", v: 26 }, { d: "ث",  v: 24 },
    { d: "ر",  v: 31 }, { d: "خ",  v: 38 }, { d: "ج",  v: 42 }, { d: "س",  v: 36 },
    { d: "أ",  v: 28 }, { d: "اث", v: 32 }, { d: "ث",  v: 35 }, { d: "ر",  v: 40 },
    { d: "خ",  v: 46 }, { d: "ج",  v: 52 },
  ];
  const max = 56;
  const W = 720, H = 200, P = 24;
  const bw = (W - P*2) / data.length;
  return (
    <div className="dh-rev-card">
      <div className="dh-card-head">
        <div>
          <div className="ttl">الإيرادات اليومية</div>
          <div className="sub">Daily revenue · last 14 days <span className="rev-unit">(ألف ر.س)</span></div>
        </div>
        <div className="dh-card-stats">
          <div className="stat">
            <span className="lab">الإجمالي</span>
            <span className="v">٤٧٠٬٢٤٠ <span className="cur">ر.س</span></span>
          </div>
          <div className="stat">
            <span className="lab">+١٤٪</span>
            <span className="lab" style={{color: "var(--success-700)"}}>عن الفترة السابقة</span>
          </div>
        </div>
      </div>

      <svg viewBox={"0 0 " + W + " " + H} preserveAspectRatio="none" style={{width:"100%", height:200, direction: "ltr"}}>
        <defs>
          <linearGradient id="grad-rev" x1="0" x2="0" y1="0" y2="1">
            <stop offset="0%"  stopColor="#3B8772" stopOpacity="0.85"/>
            <stop offset="100%" stopColor="#3B8772" stopOpacity="0.2"/>
          </linearGradient>
        </defs>
        {/* baseline */}
        <line x1={P} x2={W-P} y1={H-P} y2={H-P} stroke="var(--hairline)" strokeWidth="1"/>
        {/* grid */}
        {[0.25, 0.5, 0.75].map((g,i) => (
          <line key={i} x1={P} x2={W-P} y1={H - P - (H - P*2)*g} y2={H - P - (H - P*2)*g} stroke="var(--hairline)" strokeWidth="1" strokeDasharray="2 4"/>
        ))}
        {/* bars */}
        {data.map((d,i) => {
          const h = (d.v / max) * (H - P*2);
          const x = P + i * bw + bw*0.18;
          const w = bw * 0.64;
          const y = H - P - h;
          const isPeak = d.v >= 46;
          return (
            <g key={i}>
              <rect x={x} y={y} width={w} height={h} rx="2"
                    fill={isPeak ? "var(--gold-600)" : "url(#grad-rev)"}/>
              <text x={x + w/2} y={H - 6} textAnchor="middle" fontSize="9" fill="var(--fg-3)" fontFamily="var(--font-ar)">{d.d}</text>
            </g>
          );
        })}
      </svg>
    </div>
  );
}

window.RevenueChart = RevenueChart;
