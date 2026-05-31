/* @jsx React.createElement */
/* global React */

/* =========================================================================
   Sidebar — RTL primary navigation
   ========================================================================= */
const Icon = {
  dash:  () => <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.75" strokeLinecap="round" strokeLinejoin="round"><rect x="3" y="3" width="7" height="9" rx="1"/><rect x="14" y="3" width="7" height="5" rx="1"/><rect x="14" y="12" width="7" height="9" rx="1"/><rect x="3" y="16" width="7" height="5" rx="1"/></svg>,
  cal:   () => <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.75" strokeLinecap="round" strokeLinejoin="round"><rect x="3" y="4" width="18" height="18" rx="2"/><path d="M16 2v4"/><path d="M8 2v4"/><path d="M3 10h18"/></svg>,
  user:  () => <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.75" strokeLinecap="round" strokeLinejoin="round"><path d="M16 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"/><circle cx="8.5" cy="7" r="4"/></svg>,
  bed:   () => <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.75" strokeLinecap="round" strokeLinejoin="round"><path d="M2 22V8a2 2 0 0 1 2-2h16a2 2 0 0 1 2 2v14"/><path d="M2 22h20"/><path d="M6 12h12"/><path d="M6 17h12"/></svg>,
  box:   () => <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.75" strokeLinecap="round" strokeLinejoin="round"><path d="M21 8a2 2 0 0 0-1-1.73L13 2.27a2 2 0 0 0-2 0L4 6.27A2 2 0 0 0 3 8v8a2 2 0 0 0 1 1.73l7 4a2 2 0 0 0 2 0l7-4A2 2 0 0 0 21 16Z"/><path d="m7.5 4.27 9 5.15"/><path d="M3.3 7 12 12l8.7-5"/><path d="M12 22V12"/></svg>,
  wrench:() => <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.75" strokeLinecap="round" strokeLinejoin="round"><path d="M14.7 6.3a4 4 0 0 0-5.4 5.4l-7 7a1 1 0 0 0 1.4 1.4l7-7a4 4 0 0 0 5.4-5.4l-2.6 2.6-2-2 2.6-2.6"/></svg>,
  chart: () => <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.75" strokeLinecap="round" strokeLinejoin="round"><path d="M3 3v18h18"/><path d="m19 9-5 5-4-4-3 3"/></svg>,
  receipt:()=> <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.75" strokeLinecap="round" strokeLinejoin="round"><path d="M6 22V4a2 2 0 0 1 2-2h8a2 2 0 0 1 2 2v18l-3-2-3 2-3-2-3 2z"/><path d="M10 7h4"/><path d="M10 11h4"/></svg>,
  shield:() => <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.75" strokeLinecap="round" strokeLinejoin="round"><path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/></svg>,
  globe: () => <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.75" strokeLinecap="round" strokeLinejoin="round"><circle cx="12" cy="12" r="10"/><line x1="2" y1="12" x2="22" y2="12"/><path d="M12 2a15.3 15.3 0 0 1 4 10 15.3 15.3 0 0 1-4 10 15.3 15.3 0 0 1-4-10 15.3 15.3 0 0 1 4-10z"/></svg>,
  cog:   () => <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.75" strokeLinecap="round" strokeLinejoin="round"><path d="M12.22 2h-.44a2 2 0 0 0-2 2v.18a2 2 0 0 1-1 1.73l-.43.25a2 2 0 0 1-2 0l-.15-.08a2 2 0 0 0-2.73.73l-.22.38a2 2 0 0 0 .73 2.73l.15.1a2 2 0 0 1 1 1.72v.51a2 2 0 0 1-1 1.74l-.15.09a2 2 0 0 0-.73 2.73l.22.38a2 2 0 0 0 2.73.73l.15-.08a2 2 0 0 1 2 0l.43.25a2 2 0 0 1 1 1.73V20a2 2 0 0 0 2 2h.44a2 2 0 0 0 2-2v-.18a2 2 0 0 1 1-1.73l.43-.25a2 2 0 0 1 2 0l.15.08a2 2 0 0 0 2.73-.73l.22-.39a2 2 0 0 0-.73-2.73l-.15-.08a2 2 0 0 1-1-1.74v-.5a2 2 0 0 1 1-1.74l.15-.09a2 2 0 0 0 .73-2.73l-.22-.38a2 2 0 0 0-2.73-.73l-.15.08a2 2 0 0 1-2 0l-.43-.25a2 2 0 0 1-1-1.73V4a2 2 0 0 0-2-2z"/><circle cx="12" cy="12" r="3"/></svg>,
  search:() => <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.75" strokeLinecap="round" strokeLinejoin="round"><circle cx="11" cy="11" r="8"/><path d="m21 21-4.3-4.3"/></svg>,
  bell:  () => <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.75" strokeLinecap="round" strokeLinejoin="round"><path d="M6 8a6 6 0 0 1 12 0c0 7 3 9 3 9H3s3-2 3-9"/><path d="M10.3 21a1.94 1.94 0 0 0 3.4 0"/></svg>,
  arrow_up:()=> <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="m18 15-6-6-6 6"/></svg>,
  arrow_dn:()=> <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="m6 9 6 6 6-6"/></svg>,
  dots:  () => <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><circle cx="12" cy="12" r="1"/><circle cx="12" cy="5" r="1"/><circle cx="12" cy="19" r="1"/></svg>,
  filter:() => <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.75" strokeLinecap="round" strokeLinejoin="round"><path d="M22 3H2l8 9.46V19l4 2v-8.54L22 3z"/></svg>,
};

function Sidebar({ active, onChange }) {
  const nav = [
    { group: "الإدارة", items: [
      { id: "dashboard", ar: "لوحة التحكم",   en: "Dashboard",  ic: "dash"   },
      { id: "bookings",  ar: "الحجوزات",     en: "Bookings",   ic: "cal", count: 12 },
      { id: "guests",    ar: "الضيوف",       en: "Guests",     ic: "user"   },
      { id: "rooms",     ar: "الغرف",        en: "Rooms",      ic: "bed"    },
    ]},
    { group: "العمليات", items: [
      { id: "inventory", ar: "المخزون",      en: "Inventory",  ic: "box"    },
      { id: "warehouse", ar: "المستودع",     en: "Warehouse",  ic: "wrench" },
      { id: "accounting",ar: "المحاسبة",     en: "Accounting", ic: "receipt"},
    ]},
    { group: "النمو", items: [
      { id: "marketing", ar: "التسويق",      en: "Marketing",  ic: "globe"  },
      { id: "reports",   ar: "التقارير",     en: "Reports",    ic: "chart"  },
      { id: "smartkey",  ar: "المفتاح الذكي", en: "Smart Key",  ic: "shield" },
    ]},
  ];

  return (
    <aside className="nz-sidebar">
      <div className="nz-brand">
        <span className="nz-mark">ض</span>
        <div className="nz-brand-name">
          <div className="ar">ضيوف</div>
          <div className="en">Dheuof</div>
        </div>
      </div>

      <nav className="nz-nav">
        {nav.map(g => (
          <div className="nz-nav-group" key={g.group}>
            <div className="nz-nav-label">{g.group}</div>
            {g.items.map(it => {
              const C = Icon[it.ic];
              const isActive = active === it.id;
              return (
                <a
                  key={it.id}
                  className={"nz-nav-item " + (isActive ? "is-active" : "")}
                  onClick={() => onChange && onChange(it.id)}
                >
                  <span className="ic"><C/></span>
                  <span className="lbl">{it.ar}</span>
                  {it.count ? <span className="ct">{it.count}</span> : null}
                </a>
              );
            })}
          </div>
        ))}
      </nav>

      <div className="nz-side-foot">
        <div className="nz-property">
          <div className="ar">فندق الواحة الذهبية</div>
          <div className="en">Golden Oasis Hotel · Riyadh</div>
        </div>
        <button className="nz-icon-btn"><Icon.cog/></button>
      </div>
    </aside>
  );
}

window.Sidebar = Sidebar;
window.Icon = Icon;
