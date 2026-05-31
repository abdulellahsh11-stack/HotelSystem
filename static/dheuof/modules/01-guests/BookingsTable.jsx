/* @jsx React.createElement */
/* global React */

/* Bookings list */
function BookingsTable() {
  const rows = [
    { id: "١٨٢٣", g: "أحمد بن سليمان الفهد", initials: "أس", from: "١٢ أبريل", to: "١٥ أبريل", nights: 3, room: "جناح ٤٠٢", roomType: "ملكي", channel: "مباشر",     status: "checked-in", amt: "٢٬٤٠٠", vip: true },
    { id: "١٨٢٤", g: "نورة المنصور",      initials: "نم", from: "١٣ أبريل", to: "١٤ أبريل", nights: 1, room: "٢١٨",     roomType: "ديلوكس", channel: "Booking.com", status: "upcoming",   amt: "٨٤٠"   },
    { id: "١٨٢٥", g: "Layla Karam",        initials: "LK", from: "١٣ أبريل", to: "١٧ أبريل", nights: 4, room: "٣٠٧",     roomType: "ديلوكس", channel: "Agoda",       status: "upcoming",   amt: "٣٬١٢٠"  },
    { id: "١٨٢٦", g: "محمد العتيبي",      initials: "مع", from: "١٢ أبريل", to: "١٣ أبريل", nights: 1, room: "١٠٤",     roomType: "ستاندرد", channel: "Direct",       status: "departing",  amt: "٥٢٠"   },
    { id: "١٨٢٧", g: "خالد القحطاني",     initials: "خق", from: "١١ أبريل", to: "١٤ أبريل", nights: 3, room: "—",       roomType: "—",     channel: "Booking.com",  status: "cancelled",  amt: "—"     },
    { id: "١٨٢٨", g: "فاطمة الزهراني",    initials: "فز", from: "١٤ أبريل", to: "١٨ أبريل", nights: 4, room: "٤١٠",     roomType: "جناح",  channel: "مباشر",        status: "upcoming",   amt: "٣٬٢٠٠", vip: true },
  ];
  const status = {
    "checked-in": { ar: "مسجَّل",    cls: "ok"  },
    "upcoming":   { ar: "قادم",      cls: "info"},
    "departing":  { ar: "مغادر اليوم", cls: "warn"},
    "cancelled":  { ar: "ملغى",      cls: "neu" },
  };

  return (
    <div className="dh-tbl-card">
      <div className="dh-card-head">
        <div>
          <div className="ttl">آخر الحجوزات</div>
          <div className="sub">Recent reservations · today</div>
        </div>
        <div className="dh-card-actions">
          <button className="dh-chip is-on">الكل</button>
          <button className="dh-chip">قادم</button>
          <button className="dh-chip">مغادر</button>
          <button className="dh-icon-btn"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.75" strokeLinecap="round" strokeLinejoin="round"><path d="M22 3H2l8 9.46V19l4 2v-8.54L22 3z"/></svg></button>
        </div>
      </div>

      <div className="dh-tbl">
        <div className="dh-tr dh-th">
          <span>#</span>
          <span>النزيل</span>
          <span>الفترة</span>
          <span>الغرفة</span>
          <span>القناة</span>
          <span>الحالة</span>
          <span style={{textAlign: "end"}}>المبلغ</span>
          <span></span>
        </div>
        {rows.map(r => {
          const s = status[r.status];
          return (
            <div className="dh-tr" key={r.id}>
              <span className="num">{r.id}</span>
              <div className="guest">
                <div className={"av " + (r.vip ? "is-vip" : "")}>{r.initials}</div>
                <div>
                  <div className="nm">{r.g}{r.vip ? <span className="vip-tag">VIP</span> : null}</div>
                </div>
              </div>
              <div>
                <div>{r.from} → {r.to}</div>
                <div className="sub">{r.nights} {r.nights === 1 ? "ليلة" : "ليالٍ"}</div>
              </div>
              <div>
                <div>{r.room}</div>
                <div className="sub">{r.roomType}</div>
              </div>
              <div className="ch">{r.channel}</div>
              <div><span className={"dh-pill " + s.cls}><span className="d"></span>{s.ar}</span></div>
              <span className="amt">{r.amt === "—" ? "—" : <><span className="v">{r.amt}</span> <span className="cur">ر.س</span></>}</span>
              <button className="dh-icon-btn"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><circle cx="12" cy="12" r="1"/><circle cx="12" cy="5" r="1"/><circle cx="12" cy="19" r="1"/></svg></button>
            </div>
          );
        })}
      </div>
    </div>
  );
}

window.BookingsTable = BookingsTable;
