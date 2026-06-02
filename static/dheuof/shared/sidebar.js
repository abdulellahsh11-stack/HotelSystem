/* =========================================================================
   Static sidebar builder — shared by all stub experiences.
   No React, no Babel. Just call StaticSidebar.render(activeId).
   ========================================================================= */
(function () {
  var MODULES = [
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

  /* ── Auth helpers ──────────────────────────────────────────────────────── */
  function getSession() {
    try { return JSON.parse(localStorage.getItem('dheuof_session') || 'null'); } catch(e) { return null; }
  }
  function saveSession(s) {
    localStorage.setItem('dheuof_session', JSON.stringify(s));
  }
  function clearSession() {
    localStorage.removeItem('dheuof_session');
  }

  /* ── Auth overlay (blocks page until logged in) ────────────────────────── */
  function injectAuthStyles() {
    if (document.getElementById('dh-auth-styles')) return;
    var s = document.createElement('style');
    s.id = 'dh-auth-styles';
    s.textContent = [
      '#dh-auth-wall{position:fixed;inset:0;z-index:99999;background:var(--brand-900,#1B4D3D);display:flex;align-items:center;justify-content:center;font-family:"Tajawal","Segoe UI",sans-serif}',
      '#dh-auth-wall .aw-box{background:#fff;border-radius:18px;padding:40px 44px;width:440px;max-width:calc(100vw - 32px);box-shadow:0 24px 64px rgba(0,0,0,.35);direction:rtl;text-align:right}',
      '#dh-auth-wall .aw-logo{display:flex;align-items:center;gap:10px;margin-bottom:28px}',
      '#dh-auth-wall .aw-logo .mark{width:40px;height:40px;background:linear-gradient(135deg,#1B4D3D,#0E2A22);border-radius:10px;display:grid;place-items:center;font-size:20px}',
      '#dh-auth-wall .aw-logo .brand-ar{font-size:22px;font-weight:700;color:#1B4D3D}',
      '#dh-auth-wall .aw-logo .brand-en{font-size:12px;color:#C9A85F;font-style:italic;margin-top:1px}',
      '#dh-auth-wall .aw-tabs{display:flex;gap:0;border-bottom:2px solid #EEE;margin-bottom:26px}',
      '#dh-auth-wall .aw-tab{flex:1;text-align:center;padding:10px 8px;font-size:14px;font-weight:600;color:#999;cursor:pointer;border-bottom:2px solid transparent;margin-bottom:-2px;transition:all 150ms}',
      '#dh-auth-wall .aw-tab.on{color:#1B4D3D;border-bottom-color:#1B4D3D}',
      '#dh-auth-wall .aw-pane{display:none}',
      '#dh-auth-wall .aw-pane.on{display:block}',
      '#dh-auth-wall .aw-title{font-size:18px;font-weight:700;color:#111;margin-bottom:6px}',
      '#dh-auth-wall .aw-sub{font-size:13px;color:#666;margin-bottom:22px;line-height:1.55}',
      '#dh-auth-wall .aw-field{margin-bottom:14px}',
      '#dh-auth-wall .aw-field label{display:block;font-size:12px;color:#555;font-weight:600;margin-bottom:6px}',
      '#dh-auth-wall .aw-field input,#dh-auth-wall .aw-field select{width:100%;box-sizing:border-box;padding:11px 14px;border:1.5px solid #DDD;border-radius:8px;font-size:14px;font-family:inherit;color:#111;outline:none;transition:border-color 150ms}',
      '#dh-auth-wall .aw-field input:focus,#dh-auth-wall .aw-field select:focus{border-color:#1B4D3D;box-shadow:0 0 0 3px rgba(27,77,61,.12)}',
      '#dh-auth-wall .aw-err{font-size:12px;color:#C0392B;margin-top:4px;display:none}',
      '#dh-auth-wall .aw-btn-primary{width:100%;padding:13px;background:linear-gradient(135deg,#1B4D3D,#0E2A22);color:#fff;border:none;border-radius:9px;font-size:15px;font-weight:700;cursor:pointer;font-family:inherit;margin-top:4px;transition:opacity 150ms}',
      '#dh-auth-wall .aw-btn-primary:hover{opacity:.88}',
      '#dh-auth-wall .aw-btn-trial{width:100%;padding:13px;background:linear-gradient(135deg,#C9A85F,#B8913E);color:#1B4D3D;border:none;border-radius:9px;font-size:15px;font-weight:700;cursor:pointer;font-family:inherit;margin-top:10px;transition:opacity 150ms}',
      '#dh-auth-wall .aw-btn-trial:hover{opacity:.88}',
      '#dh-auth-wall .aw-divider{display:flex;align-items:center;gap:10px;margin:16px 0;color:#CCC;font-size:12px}',
      '#dh-auth-wall .aw-divider::before,#dh-auth-wall .aw-divider::after{content:"";flex:1;height:1px;background:#EEE}',
      '#dh-auth-wall .aw-demo-hint{background:#F0F7F4;border:1px solid #C6DDD7;border-radius:8px;padding:10px 14px;font-size:12px;color:#1B4D3D;margin-top:16px;line-height:1.6}',
      '#dh-auth-wall .aw-demo-hint strong{font-weight:700}',
      '#dh-auth-wall .aw-trial-badge{display:inline-block;background:#FEF3C7;color:#92400E;font-size:11px;font-weight:700;padding:3px 10px;border-radius:999px;margin-bottom:14px}',
      '#dh-auth-wall .aw-grid2{display:grid;grid-template-columns:1fr 1fr;gap:12px}',
    ].join('');
    document.head.appendChild(s);
  }

  function showAuthWall(opts, onSuccess) {
    injectAuthStyles();
    var wall = document.createElement('div');
    wall.id = 'dh-auth-wall';
    wall.innerHTML = [
      '<div class="aw-box">',
        '<div class="aw-logo">',
          '<div class="mark">🌿</div>',
          '<div><div class="brand-ar">ضيوف</div><div class="brand-en">Dheuof · Hotel Management</div></div>',
        '</div>',
        '<div class="aw-tabs">',
          '<div class="aw-tab on" onclick="dhAuthTab(\'login\',this)">دخول المشترك</div>',
          '<div class="aw-tab" onclick="dhAuthTab(\'trial\',this)">تسجيل · تجربة مجانية</div>',
        '</div>',

        /* ── Login pane ── */
        '<div class="aw-pane on" id="aw-pane-login">',
          '<div class="aw-title">مرحباً بعودتك</div>',
          '<div class="aw-sub">أدخل بريدك الإلكتروني وكلمة المرور للدخول إلى لوحة التحكم</div>',
          '<div class="aw-field"><label>البريد الإلكتروني</label>',
            '<input id="aw-login-email" type="email" placeholder="your@email.com" dir="ltr" autocomplete="email"/>',
          '</div>',
          '<div class="aw-field"><label>كلمة المرور</label>',
            '<input id="aw-login-pass" type="password" placeholder="••••••••" dir="ltr" autocomplete="current-password"/>',
            '<div class="aw-err" id="aw-login-err">البريد أو كلمة المرور غير صحيحة</div>',
          '</div>',
          '<button class="aw-btn-primary" onclick="dhAuthLogin()">دخول</button>',
          '<div class="aw-demo-hint">',
            '<strong>حساب تجريبي:</strong> أي بريد إلكتروني + كلمة مرور (٦ أحرف على الأقل)<br/>',
            'أو جرّب: <strong>demo@dheuof.com</strong> / <strong>demo123</strong>',
          '</div>',
        '</div>',

        /* ── Trial / Register pane ── */
        '<div class="aw-pane" id="aw-pane-trial">',
          '<div class="aw-trial-badge">✦ تجربة مجانية 30 يوماً — بدون بطاقة ائتمان</div>',
          '<div class="aw-title">سجّل منشأتك الآن</div>',
          '<div class="aw-sub">١٧ برنامج متكامل · فنادق وشقق واستراحات وشاليهات</div>',
          '<div class="aw-grid2">',
            '<div class="aw-field"><label>الاسم الأول</label>',
              '<input id="aw-reg-fname" type="text" placeholder="محمد"/>',
            '</div>',
            '<div class="aw-field"><label>اسم العائلة</label>',
              '<input id="aw-reg-lname" type="text" placeholder="الأحمد"/>',
            '</div>',
          '</div>',
          '<div class="aw-field"><label>اسم المنشأة</label>',
            '<input id="aw-reg-prop" type="text" placeholder="فندق الواحة · الرياض"/>',
          '</div>',
          '<div class="aw-field"><label>نوع المنشأة</label>',
            '<select id="aw-reg-type">',
              '<option value="hotel">فندق</option>',
              '<option value="apartment">شقق مفروشة</option>',
              '<option value="resthouse">استراحة</option>',
              '<option value="chalet">شاليه</option>',
              '<option value="villa">فيلا</option>',
            '</select>',
          '</div>',
          '<div class="aw-field"><label>البريد الإلكتروني</label>',
            '<input id="aw-reg-email" type="email" placeholder="your@email.com" dir="ltr"/>',
          '</div>',
          '<div class="aw-field"><label>كلمة المرور</label>',
            '<input id="aw-reg-pass" type="password" placeholder="••••••••" dir="ltr"/>',
            '<div class="aw-err" id="aw-reg-err">يرجى تعبئة جميع الحقول (كلمة مرور ٦ أحرف على الأقل)</div>',
          '</div>',
          '<button class="aw-btn-trial" onclick="dhAuthRegister()">ابدأ التجربة المجانية</button>',
        '</div>',
      '</div>',
    ].join('');
    document.body.appendChild(wall);

    /* ── Auth functions on window ── */
    window.dhAuthTab = function(pane, btn) {
      document.querySelectorAll('#dh-auth-wall .aw-tab').forEach(function(t){ t.classList.remove('on'); });
      document.querySelectorAll('#dh-auth-wall .aw-pane').forEach(function(p){ p.classList.remove('on'); });
      btn.classList.add('on');
      document.getElementById('aw-pane-' + pane).classList.add('on');
    };

    function removeWall() {
      var w = document.getElementById('dh-auth-wall');
      if (w) { w.style.opacity='0'; w.style.transition='opacity .3s'; setTimeout(function(){ if(w.parentNode) w.remove(); }, 320); }
    }

    window.dhAuthLogin = function() {
      var email = (document.getElementById('aw-login-email').value || '').trim();
      var pass  = document.getElementById('aw-login-pass').value || '';
      var err   = document.getElementById('aw-login-err');
      err.style.display = 'none';
      if (!email || pass.length < 6) { err.style.display = 'block'; return; }
      var session = { email: email, name: email.split('@')[0], plan: 'trial', ts: Date.now() };
      saveSession(session);
      removeWall();
      if (onSuccess) onSuccess(session);
      updateTopbarUser(session);
    };

    window.dhAuthRegister = function() {
      var fname = (document.getElementById('aw-reg-fname').value || '').trim();
      var lname = (document.getElementById('aw-reg-lname').value || '').trim();
      var prop  = (document.getElementById('aw-reg-prop').value  || '').trim();
      var type  = document.getElementById('aw-reg-type').value;
      var email = (document.getElementById('aw-reg-email').value || '').trim();
      var pass  = document.getElementById('aw-reg-pass').value || '';
      var err   = document.getElementById('aw-reg-err');
      err.style.display = 'none';
      if (!fname || !email || pass.length < 6) { err.style.display = 'block'; return; }
      var propName = prop || (fname + ' ' + lname);
      var session = { email: email, name: fname + (lname ? ' ' + lname : ''), plan: 'trial', property: propName, propType: type, ts: Date.now(), trialStart: Date.now() };
      saveSession(session);
      removeWall();
      if (onSuccess) onSuccess(session);
      updateTopbarUser(session);
    };

    /* Enter key support */
    ['aw-login-email','aw-login-pass'].forEach(function(id) {
      var el = document.getElementById(id);
      if (el) el.addEventListener('keydown', function(e){ if(e.key==='Enter') window.dhAuthLogin(); });
    });
  }

  /* ── Update topbar with real session info ──────────────────────────────── */
  function updateTopbarUser(session) {
    var av = document.querySelector('.dh-user .av');
    var nameEl = document.querySelector('.dh-user .nm .ar');
    var roleEl = document.querySelector('.dh-user .nm .role');
    if (!session) return;
    var initials = session.name ? session.name.split(' ').map(function(w){ return w[0]; }).join('').slice(0,2) : 'م';
    if (av) av.textContent = initials;
    if (nameEl) nameEl.textContent = session.name || session.email;
    if (roleEl) roleEl.textContent = session.property ? session.property : (session.plan === 'trial' ? 'تجربة مجانية' : 'مشترك');
  }

  /* ── Sidebar renderer ─────────────────────────────────────────────────── */
  function renderSidebar(activeId, opts) {
    opts = opts || {};
    var property = opts.property || { ar: "فندق الواحة الذهبية", en: "Golden Oasis · Riyadh" };
    var home = opts.homeHref || "../index.html";
    var session = getSession();
    if (session && session.property) {
      property = { ar: session.property, en: session.email || '' };
    }

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
      (!session ? (
        '<div class="dh-trial-cta">' +
          '<div class="dh-trial-badge">تجربة مجانية · 30 يوم</div>' +
          '<div class="dh-trial-desc">جميع الميزات متاحة بدون بطاقة ائتمان</div>' +
          '<button onclick="dhShowAuth()" class="dh-trial-btn-reg" style="border:none;cursor:pointer;width:100%;text-align:center">سجّل مجاناً الآن</button>' +
          '<a href="/static/dheuof/packages.html" class="dh-trial-pkg-link">عرض الباقات والأسعار</a>' +
        '</div>'
      ) : (
        '<div class="dh-trial-cta" style="background:rgba(201,168,95,.08);border-color:rgba(201,168,95,.2)">' +
          '<div class="dh-trial-badge" style="background:rgba(201,168,95,.2);color:var(--gold-300)">✓ مشترك نشط</div>' +
          '<div class="dh-trial-desc">' + (session.name || session.email) + '</div>' +
          '<button onclick="dhLogout()" class="dh-trial-btn-reg" style="border:none;cursor:pointer;width:100%;text-align:center;background:rgba(255,255,255,.1);color:var(--gold-200)">تسجيل الخروج</button>' +
        '</div>'
      )) +
      '<div class="dh-side-foot">' +
        '<div class="dh-property">' +
          '<div class="ar">' + property.ar + '</div>' +
          '<div class="en">' + (property.en || '') + '</div>' +
        '</div>' +
      '</div>' +
    '</aside>';
  }

  /* ── Topbar renderer ──────────────────────────────────────────────────── */
  function renderTopBar(opts) {
    opts = opts || {};
    var placeholder = opts.placeholder || "بحث...";
    var session = getSession();
    var userName = session ? (session.name || session.email) : 'زائر';
    var userRole = session ? (session.property || (session.plan === 'trial' ? 'تجربة مجانية' : 'مشترك')) : '';
    var initials = session && session.name ? session.name.split(' ').map(function(w){ return w[0]; }).join('').slice(0,2) : 'زر';

    return '<header class="dh-topbar">' +
      '<div class="dh-search">' +
        '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.75" stroke-linecap="round" stroke-linejoin="round"><circle cx="11" cy="11" r="8"/><path d="m21 21-4.3-4.3"/></svg>' +
        '<input placeholder="' + placeholder + '"/>' +
        '<span class="kbd">⌘K</span>' +
      '</div>' +
      '<div class="dh-top-actions">' +
        (!session ?
          '<button onclick="dhShowAuth()" class="dh-trial-topbtn" style="border:none;cursor:pointer">' +
            '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="width:13px;height:13px"><path d="M12 2l3.09 6.26L22 9.27l-5 4.87 1.18 6.88L12 17.77l-6.18 3.25L7 14.14 2 9.27l6.91-1.01L12 2z"/></svg>' +
            'سجّل / دخول' +
          '</button>'
          :
          '<button onclick="dhShowAuth()" class="dh-trial-topbtn" style="border:none;cursor:pointer;background:linear-gradient(135deg,#1B4D3D,#0E2A22)">' +
            '✓ مشترك' +
          '</button>'
        ) +
        '<button class="dh-pill-btn">' +
          '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.75" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"/><line x1="2" y1="12" x2="22" y2="12"/><path d="M12 2a15.3 15.3 0 0 1 4 10 15.3 15.3 0 0 1-4 10 15.3 15.3 0 0 1-4-10 15.3 15.3 0 0 1 4-10z"/></svg>' +
          '<span>EN</span>' +
        '</button>' +
        '<button class="dh-icon-btn dh-bell">' +
          '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.75" stroke-linecap="round" stroke-linejoin="round"><path d="M6 8a6 6 0 0 1 12 0c0 7 3 9 3 9H3s3-2 3-9"/><path d="M10.3 21a1.94 1.94 0 0 0 3.4 0"/></svg>' +
          '<span class="dot"></span>' +
        '</button>' +
        '<div class="dh-user">' +
          '<div class="av">' + initials + '</div>' +
          '<div class="nm"><div class="ar">' + userName + '</div><div class="role">' + userRole + '</div></div>' +
        '</div>' +
      '</div>' +
    '</header>';
  }

  /* ── Trial banner (only when NOT logged in) ───────────────────────────── */
  function injectTrialBanner() {
    var session = getSession();
    if (session) return; // logged-in users don't see the floating banner
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
          '<button onclick="dhShowAuth()" class="dh-ftrial-cta" style="border:none;cursor:pointer">سجّل مجاناً</button>' +
          '<a href="/static/dheuof/packages.html" class="dh-ftrial-pkg">عرض الباقات</a>' +
        '</div>' +
        '<button class="dh-ftrial-close" onclick="(function(){localStorage.setItem(\'dheuof_trial_banner_dismissed\',\'1\');var el=document.getElementById(\'dh-float-trial\');if(el)el.remove();})()" aria-label="إغلاق">✕</button>' +
      '</div>';
    document.body.appendChild(b);
    setTimeout(function(){ b.classList.add('dh-ftrial-in'); }, 100);
  }

  /* ── Mount — checks auth FIRST, blocks page if not logged in ─────────── */
  function mount(opts) {
    opts = opts || {};

    // Expose global helpers before anything renders
    window.dhShowAuth = function() {
      if (document.getElementById('dh-auth-wall')) return;
      showAuthWall(opts, function(session) {
        // Re-render sidebar + topbar with session info
        var sb = document.querySelector('.dh-sidebar');
        var tb = document.querySelector('.dh-topbar');
        if (sb) sb.outerHTML = renderSidebar(opts.activeId, opts);
        if (tb) tb.outerHTML = renderTopBar(opts);
        // remove trial banner
        var fl = document.getElementById('dh-float-trial');
        if (fl) fl.remove();
      });
    };

    window.dhLogout = function() {
      if (!confirm('تسجيل الخروج من النظام؟')) return;
      clearSession();
      // Show auth wall again
      window.dhShowAuth();
      // Re-render sidebar + topbar as guest
      var sb = document.querySelector('.dh-sidebar');
      var tb = document.querySelector('.dh-topbar');
      if (sb) sb.outerHTML = renderSidebar(opts.activeId, opts);
      if (tb) tb.outerHTML = renderTopBar(opts);
    };

    var session = getSession();

    if (!session) {
      // Render shell first so page is not blank behind the overlay
      var sb = document.getElementById("sidebar-slot");
      var tb = document.getElementById("topbar-slot");
      if (sb) sb.outerHTML = renderSidebar(opts.activeId, opts);
      if (tb) tb.outerHTML = renderTopBar(opts);
      // Show blocking auth wall
      showAuthWall(opts, function(s) {
        var sb2 = document.querySelector('.dh-sidebar');
        var tb2 = document.querySelector('.dh-topbar');
        if (sb2) sb2.outerHTML = renderSidebar(opts.activeId, opts);
        if (tb2) tb2.outerHTML = renderTopBar(opts);
      });
    } else {
      var sb = document.getElementById("sidebar-slot");
      var tb = document.getElementById("topbar-slot");
      if (sb) sb.outerHTML = renderSidebar(opts.activeId, opts);
      if (tb) tb.outerHTML = renderTopBar(opts);
    }

    if (document.readyState === 'loading') {
      document.addEventListener('DOMContentLoaded', injectTrialBanner);
    } else {
      injectTrialBanner();
    }
  }

  window.StaticSidebar = { renderSidebar, renderTopBar, mount, MODULES, getSession, clearSession };
})();
