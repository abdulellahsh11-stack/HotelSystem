/* @jsx React.createElement */
/* global React */

/* Strengths & Weaknesses analysis */

function InsightCard({ kind, title, en, value, change, recommendation }) {
  const isStrength = kind === "strength";
  return (
    <div className={"rp-ins " + (isStrength ? "is-up" : "is-down")}>
      <div className="head">
        <span className="tag">{isStrength ? "نقطة قوة" : "نقطة ضعف"}</span>
        <span className="en-tag">{isStrength ? "STRENGTH" : "WEAKNESS"}</span>
      </div>
      <div className="ttl">{title}</div>
      <div className="en">{en}</div>
      <div className="metric">
        <span className="v">{value}</span>
        <span className={"d " + (change.startsWith("+") ? "up" : "dn")}>{change}</span>
      </div>
      <div className="rec">
        <div className="rec-lbl">التوصية</div>
        <div className="rec-txt">{recommendation}</div>
      </div>
    </div>
  );
}

function ReportsList() {
  const list = [
    { name: "تقرير الإشغال اليومي",  en: "Daily occupancy",     when: "كل يوم · ٠٢:٠٠",    fmt: "PDF + Excel" },
    { name: "تقرير الإيرادات الأسبوعي", en: "Weekly revenue",    when: "كل اثنين · ٠٧:٠٠", fmt: "PDF" },
    { name: "تقرير الـ KPIs الشهري", en: "Monthly KPIs deck",   when: "أول الشهر · ٠٧:٠٠", fmt: "PDF + PPT" },
    { name: "تقرير ضريبة القيمة المضافة (VAT)", en: "VAT report", when: "ربع سنوي", fmt: "ZATCA-ready XML" },
  ];
  return (
    <div className="rp-list">
      <div className="nz-card-head">
        <div>
          <div className="ttl">التقارير المجدولة</div>
          <div className="sub">Scheduled reports · auto-delivered</div>
        </div>
        <button className="nz-chip is-on">+ جدولة تقرير</button>
      </div>
      <div className="rp-list-body">
        {list.map((r,i) => (
          <div className="rp-list-row" key={i}>
            <div className="ic">📊</div>
            <div className="body">
              <div className="nm">{r.name}</div>
              <div className="en">{r.en}</div>
            </div>
            <div className="when">{r.when}</div>
            <div className="fmt">{r.fmt}</div>
            <button className="nz-btn is-secondary">تنزيل آخر نسخة</button>
          </div>
        ))}
      </div>
    </div>
  );
}

window.InsightCard = InsightCard;
window.ReportsList = ReportsList;
