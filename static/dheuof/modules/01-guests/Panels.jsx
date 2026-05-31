/* @jsx React.createElement */
/* global React */

/* Channel mix donut + recent arrivals/tasks side panel */

function ChannelMix() {
  const segs = [
    { lbl: "مباشر",       en: "Direct",     pct: 38, color: "#1B4D3D" },
    { lbl: "Booking.com",  en: "Booking",    pct: 26, color: "#3B8772" },
    { lbl: "Agoda",        en: "Agoda",      pct: 18, color: "#C9A85F" },
    { lbl: "وكلاء سفر",   en: "Agents",     pct: 12, color: "#9A7430" },
    { lbl: "أخرى",        en: "Other",      pct:  6, color: "#CFC8BB" },
  ];
  const R = 60, C = 200, sw = 22;
  const circumference = 2 * Math.PI * R;
  let offset = 0;

  return (
    <div className="dh-mix">
      <div className="dh-card-head">
        <div>
          <div className="ttl">مزيج القنوات</div>
          <div className="sub">Channel mix · this month</div>
        </div>
      </div>

      <div className="dh-mix-body">
        <svg viewBox="0 0 200 200" width="180" height="180" style={{direction: "ltr"}}>
          <circle cx="100" cy="100" r={R} fill="none" stroke="var(--hairline)" strokeWidth={sw}/>
          {segs.map((s,i) => {
            const len = (s.pct / 100) * circumference;
            const dash = len + " " + (circumference - len);
            const el = <circle key={i} cx="100" cy="100" r={R} fill="none"
                               stroke={s.color} strokeWidth={sw}
                               strokeDasharray={dash}
                               strokeDashoffset={-offset}
                               transform="rotate(-90 100 100)"/>;
            offset += len;
            return el;
          })}
          <text x="100" y="96" textAnchor="middle" fontSize="11" fill="var(--fg-3)" fontFamily="var(--font-ar)">إجمالي</text>
          <text x="100" y="118" textAnchor="middle" fontSize="22" fill="var(--ink-900)" fontFamily="var(--font-en)" fontWeight="600">١٢٤٢</text>
        </svg>

        <div className="dh-mix-legend">
          {segs.map(s => (
            <div className="row" key={s.lbl}>
              <span className="dot" style={{background: s.color}}></span>
              <span className="lbl">{s.lbl}</span>
              <span className="pct">{s.pct}٪</span>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

function ActionsFeed() {
  const items = [
    { ic: "🔑", color: "var(--brand-700)", ar: "تسجيل دخول",   en: "Check-in",   who: "جناح ٤٠٢", t: "قبل ٤ دقائق",  flag: "ok" },
    { ic: "⚠",  color: "var(--warning-700)", ar: "تنبيه صيانة", en: "Maintenance", who: "غرفة ٢١٨ — مكيف",  t: "قبل ١٢ دقيقة", flag: "warn" },
    { ic: "🧹", color: "var(--brand-500)", ar: "تنظيف اكتمل",  en: "HK done",    who: "غرفة ٣٠٧",  t: "قبل ٢٢ دقيقة", flag: "ok" },
    { ic: "💳", color: "var(--gold-700)", ar: "دفعة POS",     en: "Payment",    who: "مطعم — ١٬٢٤٠ ر.س", t: "قبل ٣٠ دقيقة", flag: "ok" },
    { ic: "📥", color: "var(--info-700)", ar: "حجز جديد",    en: "New booking",who: "Booking.com — ليلتان", t: "قبل ٤٢ دقيقة", flag: "info" },
  ];

  return (
    <div className="dh-feed">
      <div className="dh-card-head">
        <div>
          <div className="ttl">نشاط مباشر</div>
          <div className="sub">Live activity</div>
        </div>
        <span className="dh-live"><span className="d"></span>مباشر</span>
      </div>
      <div className="dh-feed-list" data-m-rise-stagger>
        {items.map((it,i) => (
          <div className="dh-feed-row" key={i}>
            <span className="ic" style={{color: it.color, background: "color-mix(in oklch, " + it.color + " 12%, white)"}}>{it.ic}</span>
            <div className="body">
              <div className="ttl"><span className="ar">{it.ar}</span><span className="sep">·</span><span className="who">{it.who}</span></div>
              <div className="t">{it.t}</div>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

window.ChannelMix = ChannelMix;
window.ActionsFeed = ActionsFeed;
