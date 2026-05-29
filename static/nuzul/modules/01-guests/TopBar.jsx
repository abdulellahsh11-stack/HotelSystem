/* @jsx React.createElement */
/* global React, Icon */

function TopBar({ lang, onLang }) {
  return (
    <header className="nz-topbar">
      <div className="nz-search">
        <Icon.search/>
        <input placeholder={lang === "ar" ? "بحث عن نزيل، حجز، رقم غرفة..." : "Search guest, reservation, room…"} />
        <span className="kbd">⌘K</span>
      </div>
      <div className="nz-top-actions">
        <button className="nz-pill-btn" onClick={() => onLang(lang === "ar" ? "en" : "ar")}>
          <Icon.globe/>
          <span>{lang === "ar" ? "EN" : "ع"}</span>
        </button>
        <button className="nz-icon-btn nz-bell">
          <Icon.bell/>
          <span className="dot"></span>
        </button>
        <div className="nz-user">
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
