/* @jsx React.createElement */
/* global React, NzIcon */

/* ── Task list screen ──────────────────────────────────────────────────── */
function TaskListScreen() {
  const tasks = [
    { room: "٤٠٢", type: "جناح ملكي",  status: "in",       prio: "vip",   notes: "تنظيف عميق · وسائد إضافية", est: "٤٥ د" },
    { room: "٢١٨", type: "ديلوكس",     status: "ready",    prio: "normal",notes: "تنظيف بعد المغادرة",          est: "٢٥ د" },
    { room: "٣٠٧", type: "ديلوكس",     status: "ready",    prio: "high",  notes: "تنظيف + تجديد عطر",          est: "٣٠ د" },
    { room: "٤١٠", type: "جناح",       status: "blocked",  prio: "high",  notes: "بانتظار صيانة المكيف",        est: "—" },
    { room: "١٠٤", type: "ستاندرد",    status: "ready",    prio: "normal",notes: "تنظيف يومي",                  est: "٢٠ د" },
    { room: "٢٢١", type: "ديلوكس",     status: "done",     prio: "normal",notes: "اكتمل قبل ١٢ دقيقة",          est: "تم" },
  ];
  const statusMap = {
    in:      { bg: "linear-gradient(135deg, #C9A85F, #9A7430)", fg: "#FFFFFF",        ar: "قيد العمل" },
    ready:   { bg: "var(--white)",          fg: "var(--brand-800)", ar: "جاهزة"     },
    blocked: { bg: "#F1D8CF",                fg: "#8B3A2A",          ar: "محظورة"    },
    done:    { bg: "var(--brand-50)",        fg: "var(--success-700)", ar: "تم"      },
  };
  return (
    <div className="sm-screen">
      {/* greeting */}
      <div className="sm-hero">
        <div className="hello">
          <div className="ar">صباح الخير، ماريا 👋</div>
          <div className="en">Welcome back, Maria</div>
        </div>
        <div className="sm-progress">
          <div className="ring">
            <svg width="56" height="56" viewBox="0 0 56 56" style={{transform: "rotate(-90deg)"}}>
              <circle cx="28" cy="28" r="22" fill="none" stroke="rgba(255,255,255,0.15)" strokeWidth="5"/>
              <circle cx="28" cy="28" r="22" fill="none" stroke="#C9A85F" strokeWidth="5" strokeDasharray={(0.42 * Math.PI * 44) + " " + (Math.PI * 44)} strokeLinecap="round"/>
            </svg>
            <span>٤٢٪</span>
          </div>
          <div className="lab">
            <div className="t">٥ من ١٢</div>
            <div className="s">غرفة اكتملت</div>
          </div>
        </div>
      </div>

      {/* Tabs */}
      <div className="sm-tabs">
        <button className="sm-tab is-on">المهام<span className="ct">١٢</span></button>
        <button className="sm-tab">المخزون</button>
        <button className="sm-tab">رسائل</button>
      </div>

      {/* List */}
      <div className="sm-list">
        {tasks.map((t,i) => {
          const s = statusMap[t.status];
          return (
            <div key={i} className={"sm-task " + t.status}>
              <div className="sm-room" style={{background: s.bg, color: s.fg}}>
                <div className="n">{t.room}</div>
                <div className="t">{t.type}</div>
              </div>
              <div className="sm-body">
                <div className="hd">
                  <span className="st">{s.ar}</span>
                  {t.prio === "vip" ? <span className="prio vip">VIP ✦</span> : null}
                  {t.prio === "high" ? <span className="prio hi">عاجل</span> : null}
                </div>
                <div className="nt">{t.notes}</div>
                <div className="ft"><NzIcon.clock/><span>{t.est}</span></div>
              </div>
              <button className="sm-go">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="m15 18-6-6 6-6"/></svg>
              </button>
            </div>
          );
        })}
      </div>
    </div>
  );
}

/* ── Task detail screen ────────────────────────────────────────────────── */
function TaskDetailScreen() {
  return (
    <div className="sm-screen">
      <div className="sm-detail-hd">
        <button className="sm-back">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="m9 18 6-6-6-6"/></svg>
        </button>
        <span>جناح ٤٠٢ · ملكي</span>
        <span className="vipd">VIP ✦</span>
      </div>

      <div className="sm-detail-body">
        <div className="sm-stage">
          <div className="ttl">قائمة المهام</div>
          <div className="meta">٧ مهام · تقدير ٤٥ دقيقة</div>
        </div>

        <div className="sm-checks">
          {[
            { d: true,  ar: "تجديد الفراش — قطن مصري كينج" },
            { d: true,  ar: "تنظيف الحمامات + إعادة تجهيز" },
            { d: true,  ar: "تجديد المناشف الكبيرة والصغيرة" },
            { d: false, ar: "تنظيف عميق للسجاد" },
            { d: false, ar: "تجديد عطر التوقيع — Dheuof Signature" },
            { d: false, ar: "تجديد الصابون الفاخر — مرسيليا" },
            { d: false, ar: "وسائد إضافية × ٢ (طلب الضيف)" },
          ].map((c,i) => (
            <label key={i} className={"sm-check " + (c.d ? "is-on" : "")}>
              <span className="box">{c.d ? <NzIcon.check/> : null}</span>
              <span className="lbl">{c.ar}</span>
            </label>
          ))}
        </div>

        <div className="sm-notes-card">
          <div className="lbl">ملاحظات من النزيل</div>
          <div className="body">"يفضّل الفطور في الجناح الساعة ٨ صباحاً، ووسائد إضافية للسرير الرئيسي."</div>
          <div className="from">— أحمد بن سليمان الفهد</div>
        </div>
      </div>

      <div className="sm-foot">
        <button className="sm-act-2">إيقاف مؤقت</button>
        <button className="sm-act-1">إكمال المهمة</button>
      </div>
    </div>
  );
}

window.TaskListScreen = TaskListScreen;
window.TaskDetailScreen = TaskDetailScreen;
