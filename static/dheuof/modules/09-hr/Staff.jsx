/* @jsx React.createElement */
/* global React, NzIcon */

function IqamaTimeline({ expires, daysLeft }) {
  const status = daysLeft <= 30 ? "err" : daysLeft <= 90 ? "warn" : "ok";
  const pct = Math.min(100, Math.max(0, ((365 - daysLeft) / 365) * 100));
  return (
    <div className={"hr-iq " + status}>
      <div className="bar"><div className="fill" style={{width: pct + "%"}}></div></div>
      <div className="lbl">
        <span className="dt">{expires}</span>
        <span className="sep">·</span>
        <span className="dl">{daysLeft <= 0 ? "منتهية" : daysLeft + " يوم"}</span>
      </div>
    </div>
  );
}

function StaffRow({ s }) {
  return (
    <div className="hr-tr">
      <div className="hr-emp">
        <div className={"av " + (s.nationality === "SA" ? "is-sa" : "")}>{s.initials}</div>
        <div>
          <div className="nm">{s.name}</div>
          <div className="sub">{s.role} · {s.dept}</div>
        </div>
      </div>
      <div className="nat">
        <div className="flag">{s.flag}</div>
        <div className="sub">{s.nat}</div>
      </div>
      <div className="iqd">
        <div>{s.iqama}</div>
        <div className="sub">{s.iqamaSub}</div>
      </div>
      <IqamaTimeline expires={s.expires} daysLeft={s.daysLeft}/>
      <div className="sal">
        <div className="v">{s.salary.toLocaleString("ar-EG")}</div>
        <div className="cur">ر.س / شهر</div>
      </div>
      <div className="qiwa">
        {s.qiwa
          ? <span className="dh-pill ok"><span className="d"></span>متصل قوى</span>
          : <span className="dh-pill warn"><span className="d"></span>بانتظار</span>}
      </div>
      <button className="dh-icon-btn" style={{background:"transparent",border:"none",color:"var(--fg-3)"}}><NzIcon.dots/></button>
    </div>
  );
}

function StaffTable({ staff }) {
  return (
    <div className="hr-tbl">
      <div className="hr-tr hr-th">
        <span>الموظف</span>
        <span>الجنسية</span>
        <span>رقم الإقامة</span>
        <span>صلاحية الإقامة</span>
        <span>الراتب</span>
        <span>قوى</span>
        <span></span>
      </div>
      {staff.map(s => <StaffRow s={s} key={s.id}/>)}
    </div>
  );
}

window.StaffTable = StaffTable;
window.IqamaTimeline = IqamaTimeline;
