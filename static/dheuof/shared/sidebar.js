/* =========================================================================
   Static sidebar builder — shared by all stub experiences.
   No React, no Babel. Just call StaticSidebar.render(activeId).
   ========================================================================= */
(function () {
  const MODULES = [
    { id: "01-guests",            ar: "الضيوف",            num: "01" },
    { id: "02-shumus",            ar: "شموس",             num: "02" },
    { id: "03-tourism",           ar: "المستندات الحكومية", num: "03" },
    { id: "04-inventory",         ar: "المخزون والضيافة", num: "04" },
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
    { id: "15-tourism-trips",     ar: "جولات سياحية",     num: "15" },
    { id: "16-staff-app",         ar: "تطبيق الموظفين",   num: "16" },
    { id: "17-bookings",          ar: "حجوزات القنوات",   num: "17" },
  ];

  function renderSidebar(activeId, opts) {
    opts = opts || {};
    var property = opts.property || { ar: "فندق الواحة الذهبية", en: "Golden Oasis · Riyadh" };
    var home = opts.homeHref || "../index.html";

    return '<aside class="dh-sidebar">' +
      '<a class="dh-brand" href="' + home + '" style="text-decoration:none; cursor:pointer">' +
        '<img class="dh-mark" src="/static/dheuof/assets/logo-mark.svg" alt="ضيوف"/>' +
        '<div class="dh-brand-name"><div class="ar">ضيوف</div><div class="en">Dheuof</div></div>' +
      '</a>' +
      '<nav class="dh-nav"><div class="dh-nav-group">' +
        '<div class="dh-nav-label">١٧ برنامج</div>' +
        MODULES.map(function(m) {
          var isActive = m.id === activeId;
          var href = '../' + m.id + '/index.html';
          return '<a class="dh-nav-item' + (isActive ? ' is-active' : '') + '" href="' + href + '" style="text-decoration:none">' +
            '<span class="ic" style="font-family:var(--font-mono);font-size:10px;width:18px;text-align:center;opacity:0.65;font-weight:500">' + m.num + '</span>' +
            '<span class="lbl">' + m.ar + '</span>' +
          '</a>';
        }).join('') +
      '</div></nav>' +
      '<div class="dh-trial-cta">' +
        '<div class="dh-trial-badge">تجربة مجانية · 30 يوم</div>' +
        '<div class="dh-trial-desc">جميع الميزات متاحة بدون بطاقة ائتمان</div>' +
        '<a href="/static/dheuof/onboarding.html" class="dh-trial-btn-reg">سجّل مجاناً الآن</a>' +
        '<a href="/static/dheuof/packages.html" class="dh-trial-pkg-link">عرض الباقات والأسعار</a>' +
      '</div>' +
      '<div class="dh-side-foot">' +
        '<div class="dh-property">' +
          '<div class="ar">' + property.ar + '</div>' +
          '<div class="en">' + property.en + '</div>' +
        '</div>' +
      '</div>' +
    '</aside>';
  }

  function renderTopBar(opts) {
    opts = opts || {};
    var placeholder = opts.placeholder || "بحث...";
    return '<header class="dh-topbar">' +
      '<div class="dh-search">' +
        '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.75" stroke-linecap="round" stroke-linejoin="round"><circle cx="11" cy="11" r="8"/><path d="m21 21-4.3-4.3"/></svg>' +
        '<input placeholder="' + placeholder + '"/>' +
        '<span class="kbd">⌘K</span>' +
      '</div>' +
      '<div class="dh-top-actions">' +
        '<a href="/static/dheuof/onboarding.html" class="dh-trial-topbtn" title="ابدأ تجربتك المجانية">' +
          '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="width:13px;height:13px"><path d="M12 2l3.09 6.26L22 9.27l-5 4.87 1.18 6.88L12 17.77l-6.18 3.25L7 14.14 2 9.27l6.91-1.01L12 2z"/></svg>' +
          'ابدأ مجاناً' +
        '</a>' +
        '<button class="dh-pill-btn">' +
          '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.75" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"/><line x1="2" y1="12" x2="22" y2="12"/><path d="M12 2a15.3 15.3 0 0 1 4 10 15.3 15.3 0 0 1-4 10 15.3 15.3 0 0 1-4-10 15.3 15.3 0 0 1 4-10z"/></svg>' +
          '<span>EN</span>' +
        '</button>' +
        '<button class="dh-icon-btn dh-bell">' +
          '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.75" stroke-linecap="round" stroke-linejoin="round"><path d="M6 8a6 6 0 0 1 12 0c0 7 3 9 3 9H3s3-2 3-9"/><path d="M10.3 21a1.94 1.94 0 0 0 3.4 0"/></svg>' +
          '<span class="dot"></span>' +
        '</button>' +
        '<div class="dh-user">' +
          '<div class="av">سأ</div>' +
          '<div class="nm"><div class="ar">سارة أحمد</div><div class="role">مدير المنشأة</div></div>' +
        '</div>' +
      '</div>' +
    '</header>';
  }

  function injectTrialBanner() {
    var dismissed = localStorage.getItem('dheuof_trial_banner_dismissed');
    if (dismissed) return;
    var b = document.createElement('div');
    b.id = 'dh-float-trial';
    b.innerHTML =
      '<div class="dh-ftrial-inner">' +
        '<span class="dh-ftrial-spark">✦</span>' +
        '<div class="dh-ftrial-text">' +
          '<strong>جرّب ضيوف مجاناً لمدة 30 يوماً</strong>' +
          '<span>١٧ برنامج · جميع الميزات · بدون بطاقة ائتمان</span>' +
        '</div>' +
        '<div class="dh-ftrial-actions">' +
          '<a href="/static/dheuof/onboarding.html" class="dh-ftrial-cta">سجّل مجاناً</a>' +
          '<a href="/static/dheuof/packages.html" class="dh-ftrial-pkg">عرض الباقات</a>' +
        '</div>' +
        '<button class="dh-ftrial-close" onclick="(function(){localStorage.setItem(\'dheuof_trial_banner_dismissed\',\'1\');var el=document.getElementById(\'dh-float-trial\');if(el)el.remove();})()" aria-label="إغلاق">✕</button>' +
      '</div>';
    document.body.appendChild(b);
    setTimeout(function(){ b.classList.add('dh-ftrial-in'); }, 100);
  }

  function mount(opts) {
    opts = opts || {};
    var sb = document.getElementById("sidebar-slot");
    var tb = document.getElementById("topbar-slot");
    if (sb) sb.outerHTML = renderSidebar(opts.activeId, opts);
    if (tb) tb.outerHTML = renderTopBar(opts);
    if (document.readyState === 'loading') {
      document.addEventListener('DOMContentLoaded', injectTrialBanner);
    } else {
      injectTrialBanner();
    }
  }

  window.StaticSidebar = { renderSidebar, renderTopBar, mount, MODULES };
})();
