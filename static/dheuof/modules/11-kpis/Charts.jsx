/* @jsx React.createElement */
/* global React */

/* Line chart — daily revenue over a month */
function LineChart() {
  const W = 720, H = 240, P = 30;
  const data = [
    36, 42, 38, 45, 52, 58, 62, 55, 48, 42, 46, 52, 58, 65, 72, 68, 60, 54, 58, 64, 72, 78, 82, 76, 68, 62, 66, 72, 80, 86,
  ];
  const max = 100;
  const xs = data.map((_, i) => P + (i / (data.length - 1)) * (W - P*2));
  const ys = data.map(v => H - P - (v / max) * (H - P*2));
  const path = "M " + xs[0] + " " + ys[0] + " " + xs.slice(1).map((x,i) => "L " + x + " " + ys[i+1]).join(" ");
  const area = path + " L " + xs[xs.length-1] + " " + (H-P) + " L " + xs[0] + " " + (H-P) + " Z";

  return (
    <div className="rp-line">
      <div className="dh-card-head">
        <div>
          <div className="ttl">منحنى الإيرادات اليومية</div>
          <div className="sub">Daily revenue trend · April 2025 (SAR thousands)</div>
        </div>
        <div className="rp-period">
          <button className="dh-chip">يومي</button>
          <button className="dh-chip is-on">أسبوعي</button>
          <button className="dh-chip">شهري</button>
        </div>
      </div>
      <svg viewBox={"0 0 " + W + " " + H} preserveAspectRatio="none" style={{width: "100%", height: 260, direction: "ltr"}}>
        <defs>
          <linearGradient id="rp-grad" x1="0" x2="0" y1="0" y2="1">
            <stop offset="0%"  stopColor="#1B4D3D" stopOpacity="0.18"/>
            <stop offset="100%" stopColor="#1B4D3D" stopOpacity="0"/>
          </linearGradient>
        </defs>
        {[0.25, 0.5, 0.75, 1].map((g,i) => (
          <line key={i} x1={P} x2={W-P} y1={H - P - (H - P*2)*g} y2={H - P - (H - P*2)*g} stroke="var(--hairline)" strokeWidth="1" strokeDasharray="2 4"/>
        ))}
        {[0, 25, 50, 75, 100].map((v,i) => (
          <text key={i} x={P - 6} y={H - P - (H - P*2)*(v/100) + 3} fontSize="9" textAnchor="end" fill="var(--fg-3)" fontFamily="var(--font-mono)">{v}</text>
        ))}
        <path d={area} fill="url(#rp-grad)"/>
        <path d={path} fill="none" stroke="#1B4D3D" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
        {xs.map((x,i) => i % 3 === 0 ? <circle key={i} cx={x} cy={ys[i]} r="3" fill="#C9A85F" stroke="#1B4D3D" strokeWidth="1.5"/> : null)}
        <text x={W - P} y={H - 8} textAnchor="end" fontSize="9" fill="var(--fg-3)" fontFamily="var(--font-en)">30 أبريل</text>
        <text x={P}     y={H - 8} textAnchor="start" fontSize="9" fill="var(--fg-3)" fontFamily="var(--font-en)">1 أبريل</text>
      </svg>
    </div>
  );
}

/* Stacked bars — channel performance */
function ChannelBars() {
  const channels = [
    { n: "مباشر",       d: 38, c: "#1B4D3D" },
    { n: "Booking.com",  d: 26, c: "#3B8772" },
    { n: "Agoda",        d: 18, c: "#C9A85F" },
    { n: "وكلاء سفر",   d: 12, c: "#9A7430" },
    { n: "أخرى",        d:  6, c: "#CFC8BB" },
  ];
  return (
    <div className="rp-ch">
      <div className="dh-card-head">
        <div>
          <div className="ttl">أداء قنوات الحجز</div>
          <div className="sub">Channel performance · this month</div>
        </div>
      </div>
      <div className="rp-stacked">
        {channels.map(c => (
          <div className="seg" style={{flex: c.d, background: c.c}} key={c.n}>
            <span className="pct">{c.d}٪</span>
          </div>
        ))}
      </div>
      <div className="rp-ch-list">
        {channels.map(c => (
          <div className="row" key={c.n}>
            <span className="dot" style={{background: c.c}}></span>
            <span className="nm">{c.n}</span>
            <span className="pct">{c.d}٪</span>
            <span className="rev">SAR {((c.d/100)*470240).toLocaleString("en-US", {maximumFractionDigits: 0})}</span>
          </div>
        ))}
      </div>
    </div>
  );
}

window.LineChart = LineChart;
window.ChannelBars = ChannelBars;
