/* =========================================================================
   Static sidebar builder — shared by all stub experiences.
   No React, no Babel. Just call StaticSidebar.render(activeId).
   ========================================================================= */
(function () {
  const MODULES = [
    { id: "01-guests",            ar: "الضيوف",            num: "01" },
    { id: "02-shumus",            ar: "شموس",             num: "02" },
    { id: "03-tourism",           ar: "المستندات الحكومية", num: "03" },
    { id: "04-inventory",         ar: "مخزون الضيافة",   num: "04" },
    { id: "05-warehouse",         ar: "مستودع الصيانة",  num: "05" },
    { id: "06-accounting",        ar: "المحاسبة",         num: "06" },
    { id: "07-pos",               ar: "نقاط البيع",       num: "07" },
    { id: "08-smart-key",         ar: "المفتاح الذكي",     num: "08" },
    { id: "09-hr",                ar: "الموارد البشرية",   num: "09" },
    { id: "10-channel-marketing", ar: "تسويق القنوات",    num: "10" },
    { id: "11-kpis",              ar: "مؤشرات الأداء",     num: "11" },
    { id: "12-analytics",         ar: "تحليل البيانات",    num: "12" },
    { id: "13-staff-tracker",     ar: "أداء الموظفين",    num: "13" },
    { id: "14-manager-goals",     ar: "أهداف المدير",     num: "14" },
  ];

  function renderSidebar(activeId, opts = {}) {
    const property = opts.property || { ar: "فندق الواحة الذهبية", en: "Golden Oasis · Riyadh" };
    const home = opts.homeHref || "../index.html";

    return `
<aside class="nz-sidebar">
  <a class="nz-brand" href="${home}" style="text-decoration:none; cursor:pointer">
    <span class="nz-mark">ض</span>
    <div class="nz-brand-name">
      <div class="ar">ضيوف</div>
      <div class="en">Dheuof</div>
    </div>
  </a>
  <nav class="nz-nav">
    <div class="nz-nav-group">
      <div class="nz-nav-label">١٢ برنامج</div>
${MODULES.map(m => {
  const isActive = m.id === activeId;
  const href = "../" + m.id + "/index.html";
  return `      <a class="nz-nav-item${isActive ? " is-active" : ""}" href="${href}" style="text-decoration:none">
        <span class="ic" style="font-family:var(--font-mono);font-size:10px;width:18px;text-align:center;opacity:0.65;font-weight:500">${m.num}</span>
        <span class="lbl">${m.ar}</span>
      </a>`;
}).join("\n")}
    </div>
  </nav>
  <div class="nz-side-foot">
    <div class="nz-property">
      <div class="ar">${property.ar}</div>
      <div class="en">${property.en}</div>
    </div>
  </div>
</aside>`;
  }

  function renderTopBar(opts = {}) {
    const placeholder = opts.placeholder || "بحث...";
    return `
<header class="nz-topbar">
  <div class="nz-search">
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.75" stroke-linecap="round" stroke-linejoin="round"><circle cx="11" cy="11" r="8"/><path d="m21 21-4.3-4.3"/></svg>
    <input placeholder="${placeholder}"/>
    <span class="kbd">⌘K</span>
  </div>
  <div class="nz-top-actions">
    <button class="nz-pill-btn">
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.75" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"/><line x1="2" y1="12" x2="22" y2="12"/><path d="M12 2a15.3 15.3 0 0 1 4 10 15.3 15.3 0 0 1-4 10 15.3 15.3 0 0 1-4-10 15.3 15.3 0 0 1 4-10z"/></svg>
      <span>EN</span>
    </button>
    <button class="nz-icon-btn nz-bell">
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.75" stroke-linecap="round" stroke-linejoin="round"><path d="M6 8a6 6 0 0 1 12 0c0 7 3 9 3 9H3s3-2 3-9"/><path d="M10.3 21a1.94 1.94 0 0 0 3.4 0"/></svg>
      <span class="dot"></span>
    </button>
    <div class="nz-user">
      <div class="av">س‬أ</div>
      <div class="nm"><div class="ar">سارة أحمد</div><div class="role">مدير المنشأة</div></div>
    </div>
  </div>
</header>`;
  }

  function mount(opts) {
    const sb = document.getElementById("sidebar-slot");
    const tb = document.getElementById("topbar-slot");
    if (sb) sb.outerHTML = renderSidebar(opts.activeId, opts);
    if (tb) tb.outerHTML = renderTopBar(opts);
  }

  window.StaticSidebar = { renderSidebar, renderTopBar, mount, MODULES };
})();
