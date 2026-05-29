/* @jsx React.createElement */
/* global React, NzIcon */

function MarketingNav() {
  return (
    <header className="mk-nav">
      <a className="mk-brand" href="/">
        <img src="/static/nuzul/assets/logo-mark.svg" alt="" style={{width: 32, height: 32}}/>
        <div className="mk-brand-text">
          <span className="ar">ضيوف</span>
          <span className="en">Dheuof</span>
        </div>
      </a>
      <nav className="mk-nav-links">
        <a href="#modules">الوحدات</a>
        <a href="#hotels">للفنادق</a>
        <a href="#pricing">الأسعار</a>
        <a href="#integrations">التكاملات</a>
        <a href="#stats">الموارد</a>
      </nav>
      <div className="mk-nav-actions">
        <a className="mk-nav-lang" href="#" onClick={(e)=>e.preventDefault()}>EN</a>
        <a className="mk-nav-login" href="/dashboard">تسجيل دخول</a>
        <a className="mk-nav-cta m-shimmer" href="/app">احجز عرضاً</a>
      </div>
    </header>
  );
}

function Hero() {
  return (
    <section className="mk-hero" id="hero">
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
          <a className="mk-btn primary m-shimmer" href="/app">احجز عرضاً تجريبياً</a>
          <a className="mk-btn ghost" href="#modules">شاهد جولة ٣ دقائق →</a>
        </div>
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
    { ic: "🛏",  ar: "إدارة الضيوف",     en: "Guest management",    d: "حجوزات، توزيع غرف، تسعير ديناميكي حسب الموسم والإشغال.",         href: "/static/nuzul/modules/01-guests/index.html" },
    { ic: "💳",  ar: "محاسبة وPOS",       en: "Accounting + POS",    d: "ربط مباشر بنقاط البيع، إقفال يومي تلقائي، تقارير ZATCA جاهزة.", href: "/static/nuzul/modules/06-accounting/index.html" },
    { ic: "📦",  ar: "المخزون والمستودع", en: "Inventory & warehouse",d: "متابعة لُحف، عناية شخصية، أصباغ وقطع الصيانة في موقع واحد.",   href: "/static/nuzul/modules/04-inventory/index.html" },
    { ic: "👥",  ar: "الموارد البشرية",   en: "HR & payroll",        d: "رواتب، إقامات، رخص عمل، قوى، GOSI، تأمين طبي.",                href: "/static/nuzul/modules/09-hr/index.html" },
    { ic: "🌐",  ar: "تكامل القنوات",     en: "Channel sync",        d: "Booking, Agoda، Expedia، Almosafer وأكثر من ٤٠ قناة.",         href: "/static/nuzul/modules/10-channel-marketing/index.html" },
    { ic: "🔐",  ar: "المفتاح الذكي",     en: "Smart Key",           d: "تحقّق آلي من هوية الضيف، حماية من الاحتيال، مفتاح رقمي.",      href: "/static/nuzul/modules/08-smart-key/index.html" },
    { ic: "📈",  ar: "مؤشرات الأداء",     en: "KPIs & analytics",    d: "RevPAR، ADR، GOPPAR — مع توصيات ذكية تطبيقية.",               href: "/static/nuzul/modules/11-kpis/index.html" },
    { ic: "🧠",  ar: "تحليل البيانات",    en: "Data insights",       d: "نقاط القوة، نقاط الضعف، توصيات شهرية مُلهمة وقابلة للتنفيذ.",  href: "/static/nuzul/modules/12-analytics/index.html" },
  ];
  return (
    <section className="mk-modules" id="modules">
      <div className="mk-section-head" data-m-rise>
        <span className="mk-eyebrow">١٢ وحدة · نظام واحد</span>
        <h2 className="mk-h2">كل ما يحتاجه فندقك. <span className="accent">حقاً.</span></h2>
        <p className="mk-section-sub">من تسجيل دخول الضيف، إلى تقرير العائد الشهري — ضيوف يربط كل خيط في عملك.</p>
        <a href="/app" style={{display:"inline-block",marginTop:16,padding:"10px 24px",background:"var(--brand-700)",color:"var(--paper)",borderRadius:8,textDecoration:"none",fontSize:14,fontWeight:500}}>
          استعرض جميع الوحدات →
        </a>
      </div>
      <div className="mk-grid" data-m-rise-stagger>
        {modules.map((m,i) => (
          <a key={i} href={m.href} className="mk-feature" style={{textDecoration:"none",display:"block",cursor:"pointer"}}>
            <div className="ic">{m.ic}</div>
            <div className="ttl">{m.ar}</div>
            <div className="en">{m.en}</div>
            <p className="d">{m.d}</p>
          </a>
        ))}
      </div>
    </section>
  );
}

function StatsBand() {
  return (
    <section className="mk-stats" id="stats">
      <div className="mk-stats-grid">
        <div className="s"><div className="v" data-m-count="120" data-m-suffix="+" data-m-digits="ar">١٢٠+</div><div className="l">منشأة تستخدم ضيوف</div></div>
        <div className="s"><div className="v" data-m-count="22" data-m-suffix="٪" data-m-digits="ar">٢٢٪</div><div className="l">متوسط زيادة الإيرادات بعد سنة</div></div>
        <div className="s"><div className="v" data-m-count="40" data-m-suffix="+" data-m-digits="ar">٤٠+</div><div className="l">قناة حجز متكاملة</div></div>
        <div className="s"><div className="v" data-m-count="99.9" data-m-decimals="1" data-m-suffix="٪" data-m-digits="ar">٩٩.٩٪</div><div className="l">جاهزية الخدمة</div></div>
      </div>
    </section>
  );
}

function Testimonial() {
  return (
    <section className="mk-quote" data-m-rise>
      <span className="mk-quote-mark">"</span>
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

function PricingSection() {
  const plans = [
    { name: "تجريبي", desc: "ابدأ مجاناً", price: "٠", period: "٣٠ يوم", units: "حتى ١٠ غرف", cta: "ابدأ الآن", ctaClass: "mk-btn ghost", features: ["إدارة الضيوف والحجوزات", "فواتير أساسية", "تقارير بسيطة"], href: "/app" },
    { name: "أساسي", desc: "للشقق الصغيرة", price: "١٤٩", period: "شهر", units: "حتى ٣٠ غرفة", cta: "اشترك الآن", ctaClass: "mk-btn primary", features: ["وحدات M01–M05 كاملة", "فواتير VAT", "نقطة البيع", "تقارير مالية"], href: "/app", featured: false },
    { name: "عمليات", desc: "الأكثر طلباً", price: "٣٤٩", period: "شهر", units: "حتى ٨٠ غرفة", cta: "اشترك الآن", ctaClass: "mk-btn gold", features: ["جميع وحدات M01–M12", "HR والرواتب", "الإشراف والصيانة", "CRM والولاء", "KPI متقدم"], href: "/app", featured: true },
    { name: "احترافي", desc: "للمنشآت الكبيرة", price: "٦٩٩", period: "شهر", units: "غير محدود", cta: "تواصل معنا", ctaClass: "mk-btn primary", features: ["جميع ١٦ وحدة", "API قنوات التوزيع", "المستودعات والمشتريات", "الذكاء الاصطناعي", "دعم أولوي ٢٤/٧"], href: "/app" },
  ];
  return (
    <section id="pricing" style={{padding:"80px 40px",background:"var(--paper-tint,#F5F0E6)"}}>
      <div style={{textAlign:"center",marginBottom:48}}>
        <span className="mk-eyebrow">الأسعار</span>
        <h2 className="mk-h2">خطة لكل حجم منشأة</h2>
        <p style={{color:"var(--fg-1,#6B6052)",fontSize:16,marginTop:12}}>ابدأ مجاناً. ارقَّ متى شئت.</p>
      </div>
      <div style={{display:"grid",gridTemplateColumns:"repeat(auto-fit,minmax(240px,1fr))",gap:16,maxWidth:1100,margin:"0 auto"}}>
        {plans.map((p,i)=>(
          <div key={i} style={{background:"#fff",border:p.featured?"2px solid var(--gold-500,#C9A85F)":"1px solid var(--hairline,#ECE5D6)",borderRadius:14,padding:"28px 24px",position:"relative"}}>
            {p.featured && <div style={{position:"absolute",top:-14,right:"50%",transform:"translateX(50%)",background:"var(--gold-600,#B68F40)",color:"#fff",fontSize:11,padding:"4px 14px",borderRadius:999,whiteSpace:"nowrap",fontWeight:600}}>الأكثر طلباً</div>}
            <div style={{fontSize:18,fontWeight:600,color:"var(--ink-900,#14110E)",marginBottom:4}}>{p.name}</div>
            <div style={{fontSize:12,color:"var(--fg-2,#8B8175)",marginBottom:16}}>{p.desc}</div>
            <div style={{display:"flex",alignItems:"baseline",gap:4,marginBottom:4}}>
              <span style={{fontSize:"2.4rem",fontWeight:700,fontFamily:"IBM Plex Sans,sans-serif",lineHeight:1}}>{p.price}</span>
              <span style={{fontSize:13,color:"var(--fg-2)"}}> ر.س / {p.period}</span>
            </div>
            <div style={{fontSize:12,color:"var(--fg-2)",marginBottom:20}}>{p.units}</div>
            <ul style={{listStyle:"none",marginBottom:24,display:"flex",flexDirection:"column",gap:9}}>
              {p.features.map((f,j)=>(
                <li key={j} style={{fontSize:13,color:"var(--ink-700,#322B23)",display:"flex",alignItems:"center",gap:8}}>
                  <span style={{color:"var(--brand-600,#246655)",fontWeight:700}}>✓</span>{f}
                </li>
              ))}
            </ul>
            <a href={p.href} className={p.ctaClass} style={{display:"block",textAlign:"center",textDecoration:"none",padding:"10px 20px",borderRadius:7,fontSize:14,fontWeight:500}}>{p.cta}</a>
          </div>
        ))}
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
        <a className="mk-btn gold m-shimmer" href="/app">احجز عرضاً تجريبياً</a>
        <a className="mk-btn ghost-inv" href="mailto:hello@dheuof.com">تحدث مع المبيعات →</a>
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
            <img src="/static/nuzul/assets/logo-mark.svg" alt="" style={{width: 28, height: 28}}/>
            <span className="ar">ضيوف</span>
          </div>
          <p>منصة إدارة الضيافة الكاملة للسوق السعودي والخليجي.</p>
        </div>
        <div className="col">
          <div className="hd">المنتج</div>
          <a href="#modules">الوحدات</a>
          <a href="#pricing">الأسعار</a>
          <a href="#integrations">التكاملات</a>
          <a href="/static/nuzul/modules/08-smart-key/index.html">المفتاح الذكي</a>
        </div>
        <div className="col">
          <div className="hd">الدخول</div>
          <a href="/app">لوحة البرامج</a>
          <a href="/dashboard">تسجيل الدخول</a>
          <a href="/static/nuzul/packages.html">الباقات</a>
          <a href="/static/nuzul/onboarding.html">البداية السريعة</a>
        </div>
        <div className="col">
          <div className="hd">قانوني</div>
          <a href="#">الخصوصية</a>
          <a href="#">الشروط</a>
          <a href="#">سياسة الكوكيز</a>
        </div>
      </div>
      <div className="mk-foot-bottom">
        <span>© ٢٠٢٥ ضيوف · جميع الحقوق محفوظة.</span>
        <span>صُمّم وطُوّر في السعودية 🇸🇦</span>
      </div>
    </footer>
  );
}

Object.assign(window, { MarketingNav, Hero, ModuleGrid, StatsBand, Testimonial, PricingSection, CtaFooter, Footer });
