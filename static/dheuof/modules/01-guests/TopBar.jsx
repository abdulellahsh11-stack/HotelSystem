/* @jsx React.createElement */
/* global React, Icon */

function TopBar({ lang, onLang }) {
  return (
    <header className="dh-topbar">
      <div className="dh-search">
        <Icon.search/>
        <input placeholder={lang === "ar" ? "بحث عن نزيل، حجز، رقم غرفة..." : "Search guest, reservation, room…"} />
        <span className="kbd">⌘K</span>
      </div>
      <div className="dh-top-actions">
        <button className="dh-pill-btn" onClick={() => onLang(lang === "ar" ? "en" : "ar")}>
          <Icon.globe/>
          <span>{lang === "ar" ? "EN" : "ع"}</span>
        </button>
        <button className="dh-icon-btn dh-bell">
          <Icon.bell/>
          <span className="dot"></span>
        </button>
        <div className="dh-user">
          <div className="av">س‬أ</div>
          <div className="nm">
            <div className="ar">سارة أحمد</div>
            <div className="role">مدير المنشأة</div>
          </div>
        </div>
      </div>
    </header>
  );
}

window.TopBar = TopBar;
