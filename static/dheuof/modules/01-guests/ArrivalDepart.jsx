/* @jsx React.createElement */
/* global React, NzIcon */

const { useState } = React;

function ArrivalCard({ guest, room, eta, note, vip, channel, onCheckIn }) {
  const [done, setDone] = useState(false);
  return (
    <div className={"fd-arr " + (done ? "is-done" : "")}>
      <div className={"av " + (vip ? "is-vip" : "")}>{guest.initials}</div>
      <div className="body">
        <div className="row">
          <div className="nm">{guest.name}{vip ? <span className="vip-tag">VIP</span> : null}</div>
          <div className="eta"><NzIcon.clock/><span>{eta}</span></div>
        </div>
        <div className="row sub">
          <span>{guest.id}</span>
          <span className="sep">·</span>
          <span>{room.type} — {room.no}</span>
          <span className="sep">·</span>
          <span className="ch">{channel}</span>
        </div>
        {note ? <div className="note">{note}</div> : null}
      </div>
      <div className="act">
        {done
          ? <span className="dh-pill ok"><NzIcon.check/>تم</span>
          : <button className="dh-btn is-primary" onClick={() => { setDone(true); onCheckIn && onCheckIn(); }}><NzIcon.key/>تسجيل دخول</button>}
      </div>
    </div>
  );
}

function DepartureRow({ guest, room, time, balance, vip }) {
  return (
    <div className="fd-dep">
      <div className={"av " + (vip ? "is-vip" : "")}>{guest.initials}</div>
      <div className="body">
        <div className="nm">{guest.name}</div>
        <div className="sub">{room} · المغادرة {time}</div>
      </div>
      <div className="bal">
        {balance > 0 ? (
          <span className="dh-pill warn">رصيد متبقٍ: {balance.toLocaleString("ar-EG")} ر.س</span>
        ) : (
          <span className="dh-pill ok"><NzIcon.check/>مسوّى</span>
        )}
      </div>
      <button className="dh-btn is-secondary">إنهاء الإقامة</button>
    </div>
  );
}

window.ArrivalCard = ArrivalCard;
window.DepartureRow = DepartureRow;
