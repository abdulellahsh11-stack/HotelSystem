/* @jsx React.createElement */
/* global React */

/* Calendar-style occupancy heatmap — 14 days × room types */
function OccupancyHeatmap() {
  const days = [
    { d: "١٢", n: "أحد" }, { d: "١٣", n: "اثن" }, { d: "١٤", n: "ثلا" },
    { d: "١٥", n: "أرب" }, { d: "١٦", n: "خمي" }, { d: "١٧", n: "جمع" },
    { d: "١٨", n: "سبت" }, { d: "١٩", n: "أحد" }, { d: "٢٠", n: "اثن" },
    { d: "٢١", n: "ثلا" }, { d: "٢٢", n: "أرب" }, { d: "٢٣", n: "خمي" },
    { d: "٢٤", n: "جمع" }, { d: "٢٥", n: "سبت" },
  ];
  const rooms = [
    { name: "ستاندرد",  en: "Standard",  count: 24, vals: [60, 70, 78, 85, 90, 100, 100, 95, 70, 55, 60, 80, 95, 100] },
    { name: "ديلوكس",   en: "Deluxe",    count: 18, vals: [50, 65, 75, 80, 88, 95, 100, 90, 60, 45, 50, 72, 92, 100] },
    { name: "جناح",     en: "Suite",     count: 8,  vals: [40, 55, 70, 80, 85, 100, 100, 80, 50, 35, 40, 65, 85, 100] },
    { name: "ملكي",     en: "Royal",     count: 2,  vals: [30, 40, 60, 60, 80, 100, 100, 60, 30, 0,  20, 50, 80, 100] },
  ];
  const cellColor = (v) => {
    // gold-to-forest scale based on occupancy
    if (v >= 95) return "var(--brand-800)";
    if (v >= 85) return "var(--brand-700)";
    if (v >= 70) return "var(--brand-500)";
    if (v >= 50) return "var(--brand-300)";
    if (v >= 25) return "var(--gold-200)";
    return "var(--sand-strong)";
  };
  const cellFg = (v) => v >= 70 ? "#FFFFFFE0" : "#322B23";

  return (
    <div className="dh-occ">
      <div className="dh-card-head">
        <div>
          <div className="ttl">إشغال الأسبوعين القادمين</div>
          <div className="sub">Occupancy forecast · next 14 days</div>
        </div>
        <div className="dh-legend">
          <span>منخفض</span>
          <span className="sw" style={{background: "var(--sand-strong)"}}></span>
          <span className="sw" style={{background: "var(--gold-200)"}}></span>
          <span className="sw" style={{background: "var(--brand-300)"}}></span>
          <span className="sw" style={{background: "var(--brand-500)"}}></span>
          <span className="sw" style={{background: "var(--brand-700)"}}></span>
          <span className="sw" style={{background: "var(--brand-800)"}}></span>
          <span>كامل</span>
        </div>
      </div>

      <div className="dh-occ-grid">
        <div className="dh-occ-rowhd"></div>
        {days.map((d,i) => (
          <div className="dh-occ-dayhd" key={i}>
            <div className="d">{d.d}</div>
            <div className="n">{d.n}</div>
          </div>
        ))}

        {rooms.map((r,ri) => (
          <React.Fragment key={r.name}>
            <div className="dh-occ-rowhd">
              <div className="nm">{r.name}</div>
              <div className="ct">{r.count} غرفة</div>
            </div>
            {r.vals.map((v,ci) => (
              <div className="dh-occ-cell" key={ci} style={{background: cellColor(v), color: cellFg(v)}}>
                <span>{v === 0 ? "—" : v + "٪"}</span>
              </div>
            ))}
          </React.Fragment>
        ))}
      </div>
    </div>
  );
}

window.OccupancyHeatmap = OccupancyHeatmap;
