/* @jsx React.createElement */
/* global React */

/* =========================================================================
   Shared UI primitives reused by all UI kits.
   Load AFTER React/Babel but BEFORE per-kit JSX.
   ========================================================================= */

const NzIcon = {
  dash:    () => <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.75" strokeLinecap="round" strokeLinejoin="round"><rect x="3" y="3" width="7" height="9" rx="1"/><rect x="14" y="3" width="7" height="5" rx="1"/><rect x="14" y="12" width="7" height="9" rx="1"/><rect x="3" y="16" width="7" height="5" rx="1"/></svg>,
  cal:     () => <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.75" strokeLinecap="round" strokeLinejoin="round"><rect x="3" y="4" width="18" height="18" rx="2"/><path d="M16 2v4"/><path d="M8 2v4"/><path d="M3 10h18"/></svg>,
  user:    () => <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.75" strokeLinecap="round" strokeLinejoin="round"><path d="M16 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"/><circle cx="8.5" cy="7" r="4"/></svg>,
  bed:     () => <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.75" strokeLinecap="round" strokeLinejoin="round"><path d="M2 22V8a2 2 0 0 1 2-2h16a2 2 0 0 1 2 2v14"/><path d="M2 22h20"/><path d="M6 12h12"/><path d="M6 17h12"/></svg>,
  box:     () => <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.75" strokeLinecap="round" strokeLinejoin="round"><path d="M21 8a2 2 0 0 0-1-1.73L13 2.27a2 2 0 0 0-2 0L4 6.27A2 2 0 0 0 3 8v8a2 2 0 0 0 1 1.73l7 4a2 2 0 0 0 2 0l7-4A2 2 0 0 0 21 16Z"/><path d="m7.5 4.27 9 5.15"/><path d="M3.3 7 12 12l8.7-5"/><path d="M12 22V12"/></svg>,
  wrench:  () => <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.75" strokeLinecap="round" strokeLinejoin="round"><path d="M14.7 6.3a4 4 0 0 0-5.4 5.4l-7 7a1 1 0 0 0 1.4 1.4l7-7a4 4 0 0 0 5.4-5.4l-2.6 2.6-2-2 2.6-2.6"/></svg>,
  chart:   () => <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.75" strokeLinecap="round" strokeLinejoin="round"><path d="M3 3v18h18"/><path d="m19 9-5 5-4-4-3 3"/></svg>,
  receipt: () => <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.75" strokeLinecap="round" strokeLinejoin="round"><path d="M6 22V4a2 2 0 0 1 2-2h8a2 2 0 0 1 2 2v18l-3-2-3 2-3-2-3 2z"/><path d="M10 7h4"/><path d="M10 11h4"/></svg>,
  shield:  () => <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.75" strokeLinecap="round" strokeLinejoin="round"><path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/></svg>,
  globe:   () => <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.75" strokeLinecap="round" strokeLinejoin="round"><circle cx="12" cy="12" r="10"/><line x1="2" y1="12" x2="22" y2="12"/><path d="M12 2a15.3 15.3 0 0 1 4 10 15.3 15.3 0 0 1-4 10 15.3 15.3 0 0 1-4-10 15.3 15.3 0 0 1 4-10z"/></svg>,
  cog:     () => <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.75" strokeLinecap="round" strokeLinejoin="round"><path d="M12.22 2h-.44a2 2 0 0 0-2 2v.18a2 2 0 0 1-1 1.73l-.43.25a2 2 0 0 1-2 0l-.15-.08a2 2 0 0 0-2.73.73l-.22.38a2 2 0 0 0 .73 2.73l.15.1a2 2 0 0 1 1 1.72v.51a2 2 0 0 1-1 1.74l-.15.09a2 2 0 0 0-.73 2.73l.22.38a2 2 0 0 0 2.73.73l.15-.08a2 2 0 0 1 2 0l.43.25a2 2 0 0 1 1 1.73V20a2 2 0 0 0 2 2h.44a2 2 0 0 0 2-2v-.18a2 2 0 0 1 1-1.73l.43-.25a2 2 0 0 1 2 0l.15.08a2 2 0 0 0 2.73-.73l.22-.39a2 2 0 0 0-.73-2.73l-.15-.08a2 2 0 0 1-1-1.74v-.5a2 2 0 0 1 1-1.74l.15-.09a2 2 0 0 0 .73-2.73l-.22-.38a2 2 0 0 0-2.73-.73l-.15.08a2 2 0 0 1-2 0l-.43-.25a2 2 0 0 1-1-1.73V4a2 2 0 0 0-2-2z"/><circle cx="12" cy="12" r="3"/></svg>,
  search:  () => <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.75" strokeLinecap="round" strokeLinejoin="round"><circle cx="11" cy="11" r="8"/><path d="m21 21-4.3-4.3"/></svg>,
  bell:    () => <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.75" strokeLinecap="round" strokeLinejoin="round"><path d="M6 8a6 6 0 0 1 12 0c0 7 3 9 3 9H3s3-2 3-9"/><path d="M10.3 21a1.94 1.94 0 0 0 3.4 0"/></svg>,
  plus:    () => <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><line x1="12" y1="5" x2="12" y2="19"/><line x1="5" y1="12" x2="19" y2="12"/></svg>,
  download:() => <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.75" strokeLinecap="round" strokeLinejoin="round"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="7 10 12 15 17 10"/><line x1="12" y1="15" x2="12" y2="3"/></svg>,
  filter:  () => <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.75" strokeLinecap="round" strokeLinejoin="round"><path d="M22 3H2l8 9.46V19l4 2v-8.54L22 3z"/></svg>,
  dots:    () => <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><circle cx="12" cy="12" r="1"/><circle cx="12" cy="5" r="1"/><circle cx="12" cy="19" r="1"/></svg>,
  arrow_up:() => <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="m18 15-6-6-6 6"/></svg>,
  arrow_dn:() => <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="m6 9 6 6 6-6"/></svg>,
  scan:    () => <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.75" strokeLinecap="round" strokeLinejoin="round"><path d="M3 7V5a2 2 0 0 1 2-2h2"/><path d="M17 3h2a2 2 0 0 1 2 2v2"/><path d="M21 17v2a2 2 0 0 1-2 2h-2"/><path d="M7 21H5a2 2 0 0 1-2-2v-2"/><line x1="7" y1="12" x2="17" y2="12"/></svg>,
  key:     () => <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.75" strokeLinecap="round" strokeLinejoin="round"><path d="m21 2-9.6 9.6"/><circle cx="7.5" cy="15.5" r="5.5"/><path d="m21 2-3 3 2 2 2-2-1-3z"/></svg>,
  phone:   () => <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.75" strokeLinecap="round" strokeLinejoin="round"><path d="M22 16.92v3a2 2 0 0 1-2.18 2 19.79 19.79 0 0 1-8.63-3.07 19.5 19.5 0 0 1-6-6 19.79 19.79 0 0 1-3.07-8.67A2 2 0 0 1 4.11 2h3a2 2 0 0 1 2 1.72c.12.95.34 1.88.66 2.78a2 2 0 0 1-.45 2.11L8.09 9.91a16 16 0 0 0 6 6l1.27-1.27a2 2 0 0 1 2.11-.45c.9.32 1.83.54 2.78.66A2 2 0 0 1 22 16.92z"/></svg>,
  mail:    () => <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.75" strokeLinecap="round" strokeLinejoin="round"><rect x="2" y="4" width="20" height="16" rx="2"/><path d="m2 7 10 6 10-6"/></svg>,
  check:   () => <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><polyline points="20 6 9 17 4 12"/></svg>,
  x:       () => <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg>,
  clock:   () => <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.75" strokeLinecap="round" strokeLinejoin="round"><circle cx="12" cy="12" r="10"/><path d="M12 6v6l4 2"/></svg>,
  card:    () => <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.75" strokeLinecap="round" strokeLinejoin="round"><rect x="3" y="5" width="18" height="14" rx="2"/><path d="M3 10h18"/></svg>,
  broom:   () => <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.75" strokeLinecap="round" strokeLinejoin="round"><path d="m19.36 2.72 1.42 1.42-5.72 5.72-1.42-1.42z"/><path d="M14.5 13.5 11 17l-4-4 3.5-3.5z"/><path d="M7 13 3 21l8-4"/></svg>,
};

/* =========================================================================
   Sidebar — used by every kit. Pass `active` (id) and `onChange`.
   ========================================================================= */
function NzSidebar({ active = "dashboard", onChange, hotel = { ar: "فندق الواحة الذهبية", en: "Golden Oasis · Riyadh" } }) {
  const nav = [
    { group: "الإدارة", items: [
      { id: "dashboard", ar: "لوحة التحكم",  ic: "dash"  },
      { id: "bookings",  ar: "الحجوزات",    ic: "cal", count: 12 },
      { id: "frontdesk", ar: "الاستقبال",   ic: "key"   },
      { id: "guests",    ar: "الضيوف",      ic: "user"  },
      { id: "rooms",     ar: "الغرف",       ic: "bed"   },
    ]},
    { group: "العمليات", items: [
      { id: "inventory", ar: "المخزون",     ic: "box"     },
      { id: "warehouse", ar: "المستودع",    ic: "wrench"  },
      { id: "accounting",ar: "المحاسبة",    ic: "receipt" },
      { id: "hr",        ar: "الموارد البشرية", ic: "user" },
    ]},
    { group: "النمو", items: [
      { id: "marketing", ar: "التسويق",     ic: "globe"  },
      { id: "reports",   ar: "التقارير",    ic: "chart"  },
      { id: "smartkey",  ar: "المفتاح الذكي", ic: "shield" },
    ]},
  ];
  return (
    <aside className="dh-sidebar">
      <div className="dh-brand">
        <img className="dh-mark" src="/static/dheuof/assets/logo-mark.svg" alt="ضيوف"/>
        <div className="dh-brand-name"><div className="ar">ضيوف</div><div className="en">Dheuof</div></div>
      </div>
      <nav className="dh-nav">
        {nav.map(g => (
          <div className="dh-nav-group" key={g.group}>
            <div className="dh-nav-label">{g.group}</div>
            {g.items.map(it => {
              const C = NzIcon[it.ic];
              const isActive = active === it.id;
              return (
                <a key={it.id} className={"dh-nav-item " + (isActive ? "is-active" : "")} onClick={() => onChange && onChange(it.id)}>
                  <span className="ic"><C/></span>
                  <span className="lbl">{it.ar}</span>
                  {it.count ? <span className="ct">{it.count}</span> : null}
                </a>
              );
            })}
          </div>
        ))}
      </nav>
      <div className="dh-side-foot">
        <div className="dh-property"><div className="ar">{hotel.ar}</div><div className="en">{hotel.en}</div></div>
        <button className="dh-icon-btn"><NzIcon.cog/></button>
      </div>
    </aside>
  );
}

function NzTopBar({ placeholder = "بحث عن نزيل، حجز، رقم غرفة..." }) {
  return (
    <header className="dh-topbar">
      <div className="dh-search">
        <NzIcon.search/>
        <input placeholder={placeholder}/>
        <span className="kbd">⌘K</span>
      </div>
      <div className="dh-top-actions">
        <button className="dh-pill-btn"><NzIcon.globe/><span>EN</span></button>
        <button className="dh-icon-btn dh-bell"><NzIcon.bell/><span className="dot"></span></button>
        <div className="dh-user">
          <div className="av">س‬أ</div>
          <div className="nm"><div className="ar">سارة أحمد</div><div className="role">مدير المنشأة</div></div>
        </div>
      </div>
    </header>
  );
}

function NzPageHead({ eyebrow, title, sub, actions }) {
  return (
    <div className="dh-page-head">
      <div className="ttl-grp">
        {eyebrow ? <span className="dh-eyebrow">{eyebrow}</span> : null}
        <h1 className="dh-page-title">{title}</h1>
        {sub ? <div className="dh-page-sub">{sub}</div> : null}
      </div>
      {actions ? <div className="dh-page-actions">{actions}</div> : null}
    </div>
  );
}

Object.assign(window, { NzIcon, NzSidebar, NzTopBar, NzPageHead });
