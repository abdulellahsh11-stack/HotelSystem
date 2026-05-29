/* @jsx React.createElement */
/* global React, NzIcon */

function MarketingNav() {
  return (
    <header className="mk-nav">
      <a className="mk-brand">
        <img src="../assets/logo-mark.svg" alt="" style={{width: 32, height: 32}}/>
        <div className="mk-brand-text">
          <span className="ar">ضيوف</span>
          <span className="en">Dheuof</span>
        </div>
      </a>
      <nav className="mk-nav-links">
        <a>الوحدات</a>
        <a>للفنادق</a>
        <a>الأسعار</a>
        <a>التكاملات</a>
        <a>الموارد</a>
      </nav>
      <div className="mk-nav-actions">
        <a className="mk-nav-lang">EN</a>
        <a className="mk-nav-login">تسجيل دخول</a>
        <a className="mk-nav-cta m-shimmer">احجز عرضاً</a>
      </div>
    </header>
  );
}

function Hero() {
  return (
    <section className="mk-hero">
      <div className="mk-hero-text">
        <span className="mk-eyebrow">منصة إدارة الضيافة الكاملة</span>
        <h1 className="mk-h1" data-m-words>
          ضيافة <span className="accent">فخمة</span><br/>
          يديرها نظام واحد.
        </h1>
        <p className="mk-lead">
          ضيوف برنامج متكامل PMS يجمع الحجوزات، والمحاسبة، والمخزون، والصيانة، والمفتاح الذكي لكشف الاحتيال، والموارد البشرية، Booking وقنوات أخرى تحت لوحة تحكم واحدة مصممة للسوق السعودي والخليجي — وقريباً سوف تتصل ZATCA.
        </p>
        <div className="mk-hero-cta">
          <a className="mk-btn primary m-shimmer">احجز عرضاً تجريبياً</a>
          <a className="mk-btn ghost">شاهد جولة ٣ دقائق →</a>
        </div>
        <div className="mk-trust" style={{display: "none"}}></div>
      </div>
      <div className="mk-hero-visual">
        <div className="mk-shape" data-m-parallax="0.15"></div>
        <div className="mk-card-stack">
          <div className="mk-card-mini bg-paper m-float-1 m-shimmer-loop" style={{"--m-range": "14px", "--m-rot": "-3deg"}}>
            <div className="row">
              <span className="ttl">إشغال الليلة</span>
              <span className="pill ok">+٤٪</span>
            </div>
            <div className="big">٨٧٪</div>
            <div className="bar"><div style={{width: "87%"}}></div></div>
          </div>
          <div className="mk-card-mini bg-dark m-float-2" style={{"--m-range": "18px", "--m-rot": "2deg"}}>
            <div className="row"><span className="ttl">إيراد اليوم</span></div>
            <div className="big">٢٤٬٨٦٠ <span className="cur">ر.س</span></div>
            <div className="sub">+١٨٪ مقابل المتوقع</div>
          </div>
          <div className="mk-card-mini bg-gold m-float-3" style={{"--m-range": "10px", "--m-rot": "-1deg"}}>
            <div className="row"><span className="ttl">حجوزات قادمة</span></div>
            <div className="rows">
              <div><span>Booking.com</span><span>٣٢</span></div>
              <div><span>Agoda</span><span>١٨</span></div>
              <div><span>مباشر</span><span>٤٢</span></div>
            </div>
          </div>
        </div>
      </div>
    </section>
  );
}

function ModuleGrid() {
  const modules = [
    { ic: "🛏",  ar: "إدارة الضيوف",  en: "Guest management", d: "حجوزات، توزيع غرف، تسعير ديناميكي حسب الموسم والإشغال." },
    { ic: "💳",  ar: "محاسبة وPOS",  en: "Accounting + POS", d: "ربط مباشر بنقاط البيع، إقفال يومي تلقائي، تقارير ZATCA جاهزة." },
    { ic: "📦",  ar: "المخزون والمستودع", en: "Inventory & warehouse", d: "متابعة لُحف، عناية شخصية، أصباغ وقطع الصيانة في موقع واحد." },
    { ic: "👥",  ar: "الموارد البشرية", en: "HR & payroll", d: "رواتب، إقامات، رخص عمل، قوى، GOSI، تأمين طبي." },
    { ic: "🌐",  ar: "تكامل القنوات",  en: "Channel sync",     d: "Booking, Agoda، Expedia، Almosafer وأكثر من ٤٠ قناة." },
    { ic: "🔐",  ar: "المفتاح الذكي",  en: "Smart Key",         d: "تحقّق آلي من هوية الضيف، حماية من الاحتيال، مفتاح رقمي." },
    { ic: "📈",  ar: "مؤشرات الأداء", en: "KPIs & analytics",  d: "RevPAR، ADR، GOPPAR — مع توصيات ذكية تطبيقية." },
    { ic: "🧠",  ar: "تحليل البيانات", en: "Data insights",    d: "نقاط القوة، نقاط الضعف، توصيات شهرية مُلهمة وقابلة للتنفيذ." },
  ];
  return (
    <section className="mk-modules">
      <div className="mk-section-head" data-m-rise>
        <span className="mk-eyebrow">١٢ وحدة · نظام واحد</span>
        <h2 className="mk-h2">كل ما يحتاجه فندقك. <span className="accent">حقاً.</span></h2>
        <p className="mk-section-sub">من تسجيل دخول الضيف، إلى تقرير العائد الشهري — ضيوف يربط كل خيط في عملك.</p>
      </div>
      <div className="mk-grid" data-m-rise-stagger>
        {modules.map((m,i) => (
          <article key={i} className="mk-feature">
            <div className="ic">{m.ic}</div>
            <div className="ttl">{m.ar}</div>
            <div className="en">{m.en}</div>
            <p className="d">{m.d}</p>
          </article>
        ))}
      </div>
    </section>
  );
}

function StatsBand() {
  return (
    <section className="mk-stats">
      <div className="mk-stats-grid">
        <div className="s"><div className="v" data-m-count="120" data-m-suffix="+" data-m-digits="ar">٠</div><div className="l">منشأة تستخدم ضيوف</div></div>
        <div className="s"><div className="v" data-m-count="22" data-m-suffix="٪" data-m-digits="ar">٠</div><div className="l">متوسط زيادة الإيرادات بعد سنة</div></div>
        <div className="s"><div className="v" data-m-count="40" data-m-suffix="+" data-m-digits="ar">٠</div><div className="l">قناة حجز متكاملة</div></div>
        <div className="s"><div className="v" data-m-count="99.9" data-m-decimals="1" data-m-suffix="٪" data-m-digits="ar">٠</div><div className="l">جاهزية الخدمة</div></div>
      </div>
    </section>
  );
}

function Testimonial() {
  return (
    <section className="mk-quote" data-m-rise>
      <span className="mk-quote-mark">”</span>
      <p className="mk-quote-body">
        بعد ست سنوات من إدارة الفندق بثلاثة أنظمة مختلفة، استبدلناها بضيوف في شهر واحد. لأول مرة، أعرف بالضبط ما يحدث في كل ركن من الفندق — قبل أن يحدث.
      </p>
      <div className="mk-quote-attr">
        <div className="av">س‬أ</div>
        <div>
          <div className="nm">سارة أحمد المالكي</div>
          <div className="role">مدير المنشأة — فندق الواحة الذهبية، الرياض</div>
        </div>
      </div>
    </section>
  );
}

function CtaFooter() {
  return (
    <section className="mk-cta">
      <h2 className="mk-h2 inv" data-m-words>ابدأ تجربتك المجانية لمدة ٣٠ يوماً.</h2>
      <p className="mk-cta-sub">بدون بطاقة ائتمان · تثبيت في يومٍ واحد · فريق دعم باللغة العربية</p>
      <div className="mk-hero-cta">
        <a className="mk-btn gold m-shimmer">احجز عرضاً تجريبياً</a>
        <a className="mk-btn ghost-inv">تحدث مع المبيعات →</a>
      </div>
    </section>
  );
}

function Footer() {
  return (
    <footer className="mk-footer">
      <div className="mk-foot-grid">
        <div className="col col-brand">
          <div className="mk-brand">
            <img src="../assets/logo-mark.svg" alt="" style={{width: 28, height: 28}}/>
            <span className="ar">ضيوف</span>
          </div>
          <p>منصة إدارة الضيافة الكاملة للسوق السعودي والخليجي.</p>
        </div>
        <div className="col">
          <div className="hd">المنتج</div>
          <a>الوحدات</a><a>الأسعار</a><a>التكاملات</a><a>المفتاح الذكي</a>
        </div>
        <div className="col">
          <div className="hd">الشركة</div>
          <a>عن ضيوف</a><a>المهن</a><a>المدونة</a><a>الشركاء</a>
        </div>
        <div className="col">
          <div className="hd">قانوني</div>
          <a>الخصوصية</a><a>الشروط</a><a>سياسة الكوكيز</a>
        </div>
      </div>
      <div className="mk-foot-bottom">
        <span>© ٢٠٢٥ ضيوف · جميع الحقوق محفوظة.</span>
        <span>صُمّم وطُوّر في السعودية 🇸🇦</span>
      </div>
    </footer>
  );
}

Object.assign(window, { MarketingNav, Hero, ModuleGrid, StatsBand, Testimonial, CtaFooter, Footer });
