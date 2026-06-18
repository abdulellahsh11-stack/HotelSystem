# -*- coding: utf-8 -*-
"""Builds the Dheuof promotional deck HTML, rendered to PDF by WeasyPrint.
Each of the 17 modules gets a CSS-drawn UI 'screenshot' mockup + strengths."""

# ---------- shared mockup component builders (pure CSS 'screenshots') ----------

def browser_frame(inner, label="ضيوف · المنصة"):
    return f'''
    <div class="mock">
      <div class="mock-bar">
        <span class="dot r"></span><span class="dot y"></span><span class="dot g"></span>
        <span class="mock-url">{label}</span>
      </div>
      <div class="mock-body">{inner}</div>
    </div>'''

def kpi_row(cards):
    # cards: list of (label, value, delta, up?)
    h = '<div class="kpis">'
    for lbl, val, delta, up in cards:
        cls = "up" if up else "dn"
        arrow = "▲" if up else "▼"
        h += f'<div class="kpi"><span class="kl">{lbl}</span><span class="kv">{val}</span><span class="kd {cls}">{arrow} {delta}</span></div>'
    return h + '</div>'

def bars(items, unit="", maxv=100):
    # items: list of (label, value)
    h = '<div class="bars">'
    for lbl, v in items:
        pct = int(v/maxv*100)
        h += f'<div class="barrow"><span class="bl">{lbl}</span><span class="btrack"><span class="bfill" style="width:{pct}%"></span></span><span class="bv">{v}{unit}</span></div>'
    return h + '</div>'

def table(headers, rows, badges=None):
    h = '<table class="mtbl"><thead><tr>'
    for hd in headers: h += f'<th>{hd}</th>'  # noqa: E701
    h += '</tr></thead><tbody>'
    for r in rows:
        h += '<tr>'
        for c in r:
            h += f'<td>{c}</td>'
        h += '</tr>'
    return h + '</tbody></table>'

def badge(text, kind="ok"):
    return f'<span class="bdg {kind}">{text}</span>'

def statlist(items):
    # items: (icon, text, status_badge_html)
    h = '<div class="slist">'
    for ic, txt, st in items:
        h += f'<div class="srow"><span class="sic">{ic}</span><span class="stx">{txt}</span>{st}</div>'
    return h + '</div>'

def colbars(items, unit="٪"):
    # vertical column chart: (label, pct, highlight?)
    h = '<div class="colchart">'
    for lbl, v, hl in items:
        c = "hl" if hl else ""
        h += f'<div class="colwrap"><span class="col {c}" style="height:{v}%"></span><span class="collbl">{lbl}</span></div>'
    return h + '</div>'

def cards_grid(items):
    # (emoji, title, meta)
    h = '<div class="cgrid">'
    for em, t, m in items:
        h += f'<div class="ccard"><span class="cem">{em}</span><span class="ct">{t}</span><span class="cm">{m}</span></div>'
    return h + '</div>'

def progress(items):
    # (label, pct)
    h = '<div class="prog">'
    for lbl, v in items:
        h += f'<div class="prow"><div class="phead"><span>{lbl}</span><span class="ppct">{v}%</span></div><div class="ptrack"><span class="pfill" style="width:{v}%"></span></div></div>'
    return h + '</div>'

# ---------- per-module mockups ----------

def m01():
    return browser_frame(
        kpi_row([("الإشغال","٨٧٪","٤٪",True),("نُزُل اليوم","٤٢","٦",True),("مغادرة","١٨","٢",False),("الإيراد","٨٤ ألف","٧٪",True)]) +
        '<div class="mock-h">حركة الضيوف · أبريل</div>' +
        colbars([("سبت",62,False),("أحد",58,False),("إثن",61,False),("ثلا",74,False),("أرب",80,False),("خمي",95,True),("جمع",98,True)]),
        "ضيوف · لوحة الضيوف")

def m02():
    return browser_frame(
        '<div class="mock-h">تكامل شموس · وزارة الداخلية</div>' +
        statlist([
            ("🟢","الاتصال بمنصة شموس","<span class='bdg ok'>متصل</span>"),
            ("📤","بلاغات الوصول المرسلة اليوم","<span class='bdg num'>٣٨</span>"),
            ("📥","بلاغات المغادرة","<span class='bdg num'>١٤</span>"),
            ("⏱","آخر مزامنة","<span class='bdg muted'>قبل ٣ دقائق</span>"),
            ("⚠️","بلاغات معلّقة","<span class='bdg warn'>٢</span>"),
        ]),
        "ضيوف · شموس")

def m03():
    return browser_frame(
        '<div class="mock-h">المستندات الحكومية</div>' +
        table(["المستند","النوع","الحالة"],[
            ["رخصة سياحية","تشغيل", badge("سارية","ok")],
            ["شهادة دفاع مدني","سلامة", badge("سارية","ok")],
            ["رخصة بلدية","بلدي", badge("تنتهي قريباً","warn")],
            ["عقد إيجار","قانوني", badge("سارية","ok")],
            ["تأمين طبي","موظفين", badge("منتهية","bad")],
        ]),
        "ضيوف · المستندات الحكومية")

def m04():
    return browser_frame(
        '<div class="mock-h">مخزون الضيافة وتجهيزات الغرف</div>' +
        bars([("مناشف",78),("شامبو وصابون",45),("مفارش",90),("قهوة وشاي",30),("مياه معدنية",62)],"٪",100),
        "ضيوف · المخزون")

def m05():
    return browser_frame(
        '<div class="mock-h">مستودع الصيانة · أوامر العمل</div>' +
        table(["الطلب","الموقع","الأولوية"],[
            ["تكييف لا يبرد","غرفة ٣٠٤", badge("عاجل","bad")],
            ["تسريب صنبور","غرفة ١١٢", badge("متوسط","warn")],
            ["استبدال مصباح","الردهة", badge("عادي","ok")],
            ["صيانة مصعد","المبنى أ", badge("مجدول","muted")],
        ]),
        "ضيوف · مستودع الصيانة")

def m06():
    return browser_frame(
        kpi_row([("الإيرادات","٨٤٠ ألف","١٢٪",True),("المصروفات","٣١٠ ألف","٣٪",False),("صافي الربح","٥٣٠ ألف","١٨٪",True)]) +
        '<div class="mock-h">دفتر الأستاذ العام</div>' +
        table(["الحساب","مدين","دائن"],[
            ["إيراد الغرف","—","٦٢٠٬٠٠٠"],
            ["إيراد المطعم","—","٢٢٠٬٠٠٠"],
            ["رواتب","١٨٠٬٠٠٠","—"],
            ["مرافق وكهرباء","٤٢٬٠٠٠","—"],
        ]),
        "ضيوف · المحاسبة العامة")

def m07():
    return browser_frame(
        '<div class="mock-h">نقاط البيع المتصلة</div>' +
        cards_grid([("🍽️","مطعم","متصل · ٤ أجهزة"),("☕","مقهى","متصل · ٢"),("🛎️","خدمة الغرف","متصل"),("🏊","المسبح","غير متصل")]) +
        table(["الوقت","الصنف","المبلغ"],[
            ["١٢:٤٠","غداء جناح ٢٠١","٢٤٠ ر.س"],
            ["١٣:١٥","قهوة × ٣","٤٥ ر.س"],
        ]),
        "نقاط الدفع · POS")

def m08():
    return browser_frame(
        '<div class="mock-h">المفتاح الذكي · حارس البيانات</div>' +
        kpi_row([("درجة الأمان","٧٨/١٠٠","٦",True),("محاولات مشبوهة","٣","١",False)]) +
        statlist([
            ("🔒","تشفير البيانات الحساسة","<span class='bdg ok'>مفعّل</span>"),
            ("👁️","كشف الدخول غير المعتاد","<span class='bdg ok'>نشط</span>"),
            ("🚫","حظر IP مشبوه","<span class='bdg warn'>٢ محظور</span>"),
            ("📝","سجل التدقيق","<span class='bdg muted'>١٬٢٤٠ حدث</span>"),
        ]),
        "ضيوف · المفتاح الذكي")

def m09():
    return browser_frame(
        kpi_row([("الموظفون","٦٤","٣",True),("حاضر اليوم","٥٨","",True),("إجازات","٤","",False)]) +
        '<div class="mock-h">الموارد البشرية</div>' +
        table(["الموظف","القسم","الحالة"],[
            ["أحمد العتيبي","الاستقبال", badge("حاضر","ok")],
            ["سارة القحطاني","التدبير", badge("حاضر","ok")],
            ["خالد الدوسري","الصيانة", badge("إجازة","warn")],
        ]),
        "ضيوف · الموارد البشرية")

def m10():
    return browser_frame(
        '<div class="mock-h">تسويق القنوات · الأداء</div>' +
        bars([("Booking.com",42),("الموقع المباشر",28),("Agoda",15),("Expedia",9),("أخرى",6)],"٪",50),
        "ضيوف · تسويق القنوات")

def m11():
    return browser_frame(
        kpi_row([("RevPAR","٦٢٦","٧٪",True),("ADR","٧٢٠","١٢٪",True),("OCC","٨٧٪","٤٪",True),("GOPPAR","٤٢٤","٢٪",False)]) +
        '<div class="mock-h">إدارة الإيرادات · الإشغال الشهري</div>' +
        colbars([("ينا",55,False),("فبر",60,False),("مار",72,False),("أبر",87,True),("ماي",80,False),("يون",78,False)]),
        "ضيوف · إدارة الإيرادات")

def m12():
    return browser_frame(
        '<div class="mock-h">تحليل البيانات بالذكاء الاصطناعي</div>' +
        '<div class="aibox">🤖 توصية: ارفع سعر الجناح الملكي ١٠٪ في عطلة نهاية الأسبوع — الطلب المتوقع +٢٢٪</div>' +
        colbars([("توقع",92,True),("فعلي",87,False),("سوق",74,False),("هدف",95,False)]),
        "ضيوف · التحليلات الذكية")

def m13():
    return browser_frame(
        '<div class="mock-h">أداء الموظفين · المتصدرون</div>' +
        statlist([
            ("🥇","أحمد العتيبي — الاستقبال","<span class='bdg ok'>٩٦ نقطة</span>"),
            ("🥈","نورة الشمري — التدبير","<span class='bdg ok'>٩١</span>"),
            ("🥉","فهد المطيري — الخدمة","<span class='bdg ok'>٨٨</span>"),
            ("📈","متوسط الفريق","<span class='bdg num'>٨٢</span>"),
        ]),
        "ضيوف · أداء الموظفين")

def m14():
    return browser_frame(
        '<div class="mock-h">أهداف المدير · التقدّم</div>' +
        progress([("رفع الإشغال إلى ٩٠٪",87),("خفض التكاليف ٥٪",62),("رضا الضيوف ٤.٨",94),("إيراد المطعم +١٥٪",70)]),
        "ضيوف · أهداف المدير")

def m15():
    return browser_frame(
        '<div class="mock-h">جولات سياحية · حسب المنطقة</div>' +
        cards_grid([("🏛","الدرعية","الرياض · ١٢٠ ر.س"),("🏜","حافة العالم","الرياض · ١٨٠"),("🏛","الحِجر","العلا · ٢٥٠"),("🌊","غوص البحر الأحمر","جدة · ١٥٠")]),
        "ضيوف · جولات سياحية")

def m16():
    # mobile mockup
    return '''
    <div class="phone">
      <div class="pnotch"></div>
      <div class="pscreen">
        <div class="ph-top">تطبيق الموظفين <span>📱</span></div>
        <div class="ph-card ok">✓ تسجيل الحضور — ٧:٥٨ ص</div>
        <div class="ph-card">🛎️ ٣ مهام جديدة</div>
        <div class="ph-card">🧹 تنظيف غرفة ٣٠٤</div>
        <div class="ph-card">🔧 صيانة تكييف ٢١٢</div>
        <div class="ph-card warn">⚠️ طلب عاجل · جناح ٤٠١</div>
        <div class="ph-nav"><span>🏠</span><span>📋</span><span>💬</span><span>👤</span></div>
      </div>
    </div>'''

def m17():
    return browser_frame(
        kpi_row([("حجوزات اليوم","٣١","٥",True),("قنوات نشطة","٤","",True),("إلغاءات","٢","",False)]) +
        '<div class="mock-h">حجوزات القنوات الإلكترونية</div>' +
        table(["الضيف","القناة","الحالة"],[
            ["Smith J.","Booking.com", badge("مؤكد","ok")],
            ["العنزي م.","الموقع المباشر", badge("مؤكد","ok")],
            ["Khan A.","Agoda", badge("بانتظار الدفع","warn")],
            ["Müller K.","Expedia", badge("مؤكد","ok")],
        ]),
        "حجوزات · القنوات")

# ---------- module metadata ----------
MODULES = [
    ("01","🛎️","الضيوف","لوحة قيادة الضيوف اللحظية",
     ["نظرة واحدة على الإشغال والوصول والمغادرة لحظياً","مؤشرات أداء حيّة بألوان الاتجاه","رسوم حركة الضيوف عبر أيام الأسبوع","أساس كل الوحدات الأخرى"], m01),
    ("02","🇸🇦","شموس","تكامل مباشر مع منصة وزارة الداخلية",
     ["إرسال بلاغات الوصول والمغادرة آلياً لشموس","امتثال نظامي كامل دون إدخال يدوي","مزامنة لحظية وحالة اتصال واضحة","تنبيه فوري للبلاغات المعلّقة"], m02),
    ("03","📑","المستندات الحكومية","إدارة التراخيص والشهادات",
     ["تتبّع صلاحية الرخص والشهادات","تنبيهات قبل انتهاء أي مستند","حفظ مركزي آمن لكل الوثائق","تجنّب الغرامات والإيقاف"], m03),
    ("04","🧺","المخزون والضيافة","تجهيزات الغرف والمستهلكات",
     ["مستويات مخزون مرئية بأشرطة","تنبيه عند انخفاض أي صنف","ربط الاستهلاك بعدد الغرف المباعة","تقليل الهدر وضبط التكاليف"], m04),
    ("05","🔧","مستودع الصيانة","أوامر العمل والقطع",
     ["إنشاء وتتبّع أوامر الصيانة","ترتيب حسب الأولوية والموقع","جدولة الصيانة الوقائية","تقليل وقت تعطّل الغرف"], m05),
    ("06","📊","المحاسبة","الدفتر العام والتقارير المالية",
     ["دفتر أستاذ كامل بالعربية","مؤشرات الإيراد والمصروف وصافي الربح","ربط تلقائي بإيرادات الغرف والمطعم","تقارير جاهزة للمحاسب القانوني"], m06),
    ("07","💳","نقاط البيع","ربط المطعم والمقهى وخدمة الغرف",
     ["مزامنة فورية لكل نقاط البيع","تحميل الفواتير على حساب الغرفة","متابعة حالة كل جهاز","تقرير مبيعات موحّد"], m07),
    ("08","🔐","المفتاح الذكي","حارس البيانات وكشف الاحتيال",
     ["تشفير البيانات الحساسة","كشف الدخول والسلوك غير المعتاد","حظر العناوين المشبوهة تلقائياً","سجل تدقيق شامل لكل حدث"], m08),
    ("09","👥","الموارد البشرية","الموظفون والحضور والرواتب",
     ["ملف كامل لكل موظف","تتبّع الحضور والإجازات","ربط بالأداء والرواتب","لوحة حالة الفريق اللحظية"], m09),
    ("10","📣","تسويق القنوات","أداء قنوات التوزيع",
     ["تحليل مصادر الحجوزات بالنِّسب","مقارنة أداء OTA بالموقع المباشر","قياس العائد على كل قناة","توجيه الميزانية للأعلى ربحاً"], m10),
    ("11","📈","إدارة الإيرادات","RevPAR · ADR · التسعير الديناميكي",
     ["مؤشرات RevPAR وADR وOCC وGOPPAR","قواعد تسعير ديناميكي قابلة للتفعيل","تقرير Pickup وتوقعات ٣٠/٦٠/٩٠ يوم","تعظيم الإيراد لكل غرفة متاحة"], m11),
    ("12","🤖","التحليلات الذكية","رؤى بالذكاء الاصطناعي",
     ["توصيات تسعير وإشغال آلية","توقع الطلب قبل حدوثه","مقارنة الأداء بالسوق والهدف","قرارات مبنية على البيانات"], m12),
    ("13","🏅","أداء الموظفين","قياس وتحفيز الفريق",
     ["لوحة متصدّرين محفِّزة","نقاط أداء لكل موظف وقسم","ربط بالمهام المنجزة","رفع الإنتاجية والرضا الوظيفي"], m13),
    ("14","🎯","أهداف المدير","متابعة الأهداف الإستراتيجية",
     ["أهداف واضحة بنِسب تقدّم","متابعة لحظية للإنجاز","ربط الأهداف بالمؤشرات الفعلية","مساءلة وشفافية للإدارة"], m14),
    ("15","🗺️","جولات سياحية","تجارب سياحية حسب المنطقة",
     ["جولات حقيقية مصنّفة حسب مناطق السعودية","حجز وإدارة الجولات والمرشدين","مصدر دخل إضافي للضيوف","تقرير عربي كامل حسب المنطقة"], m15),
    ("16","📱","تطبيق الموظفين","تطبيق جوال للفريق الميداني",
     ["تسجيل حضور من الجوال","استلام المهام والإشعارات فوراً","تواصل مباشر بين الأقسام","إنجاز ميداني أسرع"], m16),
    ("17","🌐","حجوزات القنوات","إدارة حجوزات OTA موحّدة",
     ["كل الحجوزات من كل القنوات في شاشة واحدة","حالة الدفع والتأكيد لكل حجز","تقليل تضارب الحجوزات","تجربة استقبال أسرع"], m17),
]

# ---------- build HTML ----------
def stars(n_full, half=False):
    s = '★'*n_full
    if half: s += '½'  # noqa: E701
    s += '☆'*(5-n_full-(1 if half else 0))
    return s

module_sections = ""
for num, emoji, name, tagline, strengths, mockfn in MODULES:
    str_items = "".join(f'<li>{s}</li>' for s in strengths)
    module_sections += f'''
    <section class="mod">
      <div class="mod-head">
        <span class="mod-num">{num}</span>
        <span class="mod-emoji">{emoji}</span>
        <div class="mod-titles">
          <h2>{name}</h2>
          <p class="mod-tag">{tagline}</p>
        </div>
      </div>
      <div class="mod-grid">
        <div class="mod-shot">{mockfn()}</div>
        <div class="mod-strengths">
          <h3>نقاط القوة</h3>
          <ul>{str_items}</ul>
        </div>
      </div>
    </section>'''

HTML_DOC = f'''<!doctype html>
<html dir="rtl" lang="ar"><head><meta charset="utf-8">
<style>
@page {{
  size: A4; margin: 14mm 12mm 16mm 12mm;
  @bottom-center {{ content: "ضيوف · العرض الترويجي · منصة إدارة الفنادق الذكية"; font-family:'Tajawal'; font-size:8pt; color:#9aa39e; }}
  @bottom-left {{ content: counter(page); font-family:'Tajawal'; font-size:8pt; color:#9aa39e; }}
}}
* {{ margin:0; padding:0; box-sizing:border-box; }}
body {{ font-family:'Tajawal','Cairo',sans-serif; color:#14110E; font-size:10.5pt; line-height:1.55; }}
h1,h2,h3 {{ font-family:'Cairo','Tajawal',sans-serif; }}

/* COVER */
.cover {{ height: 247mm; background: linear-gradient(160deg,#0E2A22 0%,#1B4D3D 55%,#266554 100%); color:#fff; text-align:center; padding-top:55mm; page-break-after:always; border-radius:0; position:relative; }}
.cover .logo {{ font-size:62pt; font-weight:800; letter-spacing:-2px; }}
.cover .logo .dot {{ color:#C9A85F; }}
.cover .tg {{ font-size:18pt; color:#E8D5A8; margin-top:4mm; font-weight:700; }}
.cover .sb {{ font-size:12pt; color:#C7E1D8; margin-top:6mm; max-width:130mm; margin-right:auto; margin-left:auto; }}
.cover .rule {{ width:70mm; height:3px; background:#C9A85F; margin:12mm auto; border-radius:2px; }}
.cover .feat {{ display:flex; justify-content:center; gap:8mm; margin-top:10mm; font-size:10pt; color:#9CCBBE; }}
.cover .feat b {{ display:block; font-size:20pt; color:#fff; }}
.cover .ftr {{ position:absolute; bottom:18mm; right:0; left:0; font-size:9.5pt; color:#9CCBBE; }}

/* INTRO / efficiency review */
h2.section {{ font-size:17pt; color:#1B4D3D; margin:5mm 0 3mm; padding-bottom:2mm; border-bottom:2px solid #C9A85F; }}
.lead {{ font-size:11pt; color:#322B23; margin-bottom:4mm; }}
.health {{ display:flex; gap:4mm; flex-wrap:wrap; margin:4mm 0; }}
.hcard {{ flex:1; min-width:38mm; background:#F2F8F5; border:1px solid #C7E1D8; border-radius:10px; padding:10px; text-align:center; }}
.hcard .hv {{ font-size:22pt; font-weight:800; color:#1B4D3D; display:block; }}
.hcard .hl {{ font-size:9pt; color:#4A4137; }}
table.verify {{ width:100%; border-collapse:collapse; font-size:9.3pt; margin:3mm 0; }}
table.verify th {{ background:#1B4D3D; color:#fff; padding:6px 8px; text-align:right; }}
table.verify td {{ padding:6px 8px; border-bottom:1px solid #E4F0EB; }}
table.verify tr:nth-child(even) td {{ background:#F2F8F5; }}
.stars {{ color:#C9A85F; letter-spacing:1px; }} .star-e {{ color:#CFC8BB; letter-spacing:1px; }}

/* MODULE SECTION */
.mod {{ page-break-inside:avoid; margin-bottom:7mm; border:1px solid #E6DFD1; border-radius:12px; overflow:hidden; }}
.mod-head {{ display:flex; align-items:center; gap:10px; background:linear-gradient(90deg,#1B4D3D,#266554); color:#fff; padding:8px 14px; }}
.mod-num {{ font-family:'Cairo'; font-size:13pt; font-weight:800; color:#0E2A22; background:#C9A85F; width:30px; height:30px; line-height:30px; text-align:center; border-radius:8px; }}
.mod-emoji {{ font-size:18pt; }}
.mod-titles h2 {{ font-size:14pt; }}
.mod-tag {{ font-size:9pt; color:#C7E1D8; }}
.mod-grid {{ display:flex; gap:10px; padding:12px 14px; align-items:stretch; }}
.mod-shot {{ flex:1.3; }}
.mod-strengths {{ flex:1; background:#FBF7EC; border-radius:10px; padding:10px 12px; border:1px solid #F1E6C8; }}
.mod-strengths h3 {{ font-size:11pt; color:#9A7430; margin-bottom:5px; }}
.mod-strengths ul {{ list-style:none; }}
.mod-strengths li {{ font-size:9.5pt; color:#322B23; padding-right:16px; position:relative; margin-bottom:5px; }}
.mod-strengths li:before {{ content:"✓"; color:#1A7A2A; font-weight:800; position:absolute; right:0; }}

/* ---- MOCKUP (browser frame) ---- */
.mock {{ border:1px solid #CFC8BB; border-radius:8px; overflow:hidden; box-shadow:0 1px 3px rgba(0,0,0,.06); background:#fff; }}
.mock-bar {{ background:#E6DFD1; padding:5px 8px; display:flex; align-items:center; gap:4px; }}
.dot {{ width:7px; height:7px; border-radius:50%; display:inline-block; }}
.dot.r{{background:#e57373}} .dot.y{{background:#ffb74d}} .dot.g{{background:#81c784}}
.mock-url {{ margin-right:8px; font-size:7.5pt; color:#6B6052; background:#fff; border-radius:4px; padding:1px 8px; }}
.mock-body {{ padding:9px; }}
.mock-h {{ font-size:9pt; font-weight:700; color:#1B4D3D; margin:7px 0 5px; }}

.kpis {{ display:flex; gap:5px; }}
.kpi {{ flex:1; background:#F2F8F5; border-radius:6px; padding:5px 6px; text-align:center; }}
.kl {{ display:block; font-size:6.8pt; color:#6B6052; }}
.kv {{ display:block; font-size:12pt; font-weight:800; color:#1B4D3D; font-family:'Cairo'; }}
.kd {{ font-size:6.8pt; font-weight:700; }} .kd.up{{color:#1A7A2A}} .kd.dn{{color:#C0392B}}

.bars {{ display:flex; flex-direction:column; gap:5px; }}
.barrow {{ display:flex; align-items:center; gap:6px; font-size:8pt; }}
.bl {{ width:32mm; color:#322B23; }}
.btrack {{ flex:1; height:9px; background:#E4F0EB; border-radius:9px; overflow:hidden; }}
.bfill {{ display:block; height:100%; background:linear-gradient(90deg,#3B8772,#1B4D3D); }}
.bv {{ width:11mm; text-align:left; font-weight:700; color:#1B4D3D; }}

.mtbl {{ width:100%; border-collapse:collapse; font-size:8pt; margin-top:4px; }}
.mtbl th {{ background:#1B4D3D; color:#fff; padding:4px 6px; text-align:right; font-weight:700; }}
.mtbl td {{ padding:4px 6px; border-bottom:1px solid #E4F0EB; }}
.mtbl tr:nth-child(even) td {{ background:#F2F8F5; }}
.bdg {{ font-size:7pt; padding:1px 7px; border-radius:9px; font-weight:700; white-space:nowrap; }}
.bdg.ok{{background:#D7F0DD;color:#1A7A2A}} .bdg.warn{{background:#FCEFD2;color:#9A7430}}
.bdg.bad{{background:#FAD9D5;color:#C0392B}} .bdg.muted{{background:#E6DFD1;color:#4A4137}}
.bdg.num{{background:#C7E1D8;color:#1B4D3D}}

.slist {{ display:flex; flex-direction:column; gap:5px; }}
.srow {{ display:flex; align-items:center; gap:7px; background:#F2F8F5; border-radius:6px; padding:5px 8px; font-size:8.5pt; }}
.sic {{ font-size:11pt; }} .stx {{ flex:1; color:#322B23; }}

.colchart {{ display:flex; align-items:flex-end; gap:6px; height:46mm; padding:5px 2px 0; }}
.colwrap {{ flex:1; text-align:center; display:flex; flex-direction:column; justify-content:flex-end; height:100%; }}
.col {{ display:block; background:linear-gradient(180deg,#3B8772,#1B4D3D); border-radius:4px 4px 0 0; }}
.col.hl {{ background:linear-gradient(180deg,#DBC084,#C9A85F); }}
.collbl {{ font-size:7pt; color:#6B6052; margin-top:3px; }}

.cgrid {{ display:grid; grid-template-columns:1fr 1fr; gap:6px; margin-top:4px; }}
.ccard {{ background:#F2F8F5; border:1px solid #C7E1D8; border-radius:8px; padding:7px; text-align:center; }}
.cem {{ font-size:16pt; display:block; }}
.ct {{ font-size:8.5pt; font-weight:700; color:#1B4D3D; display:block; }}
.cm {{ font-size:7pt; color:#6B6052; }}

.prog {{ display:flex; flex-direction:column; gap:7px; }}
.phead {{ display:flex; justify-content:space-between; font-size:8.5pt; color:#322B23; margin-bottom:2px; }}
.ppct {{ font-weight:800; color:#1B4D3D; }}
.ptrack {{ height:9px; background:#E4F0EB; border-radius:9px; overflow:hidden; }}
.pfill {{ display:block; height:100%; background:linear-gradient(90deg,#C9A85F,#1B4D3D); }}

.aibox {{ background:#E4F0EB; border-right:4px solid #1B4D3D; border-radius:6px; padding:8px 10px; font-size:8.8pt; color:#143A2E; margin-bottom:6px; }}

/* phone mockup */
.phone {{ width:54mm; margin:0 auto; background:#0E2A22; border-radius:18px; padding:6px; box-shadow:0 2px 6px rgba(0,0,0,.15); }}
.pnotch {{ width:18mm; height:3px; background:#266554; border-radius:3px; margin:2px auto 5px; }}
.pscreen {{ background:#F2F8F5; border-radius:12px; padding:8px; }}
.ph-top {{ font-size:9pt; font-weight:800; color:#1B4D3D; text-align:center; margin-bottom:7px; }}
.ph-card {{ background:#fff; border:1px solid #E4F0EB; border-radius:8px; padding:6px 8px; font-size:8pt; color:#322B23; margin-bottom:5px; }}
.ph-card.ok {{ background:#D7F0DD; color:#1A7A2A; font-weight:700; }}
.ph-card.warn {{ background:#FCEFD2; color:#9A7430; font-weight:700; }}
.ph-nav {{ display:flex; justify-content:space-around; background:#1B4D3D; border-radius:9px; padding:5px; margin-top:7px; font-size:11pt; }}

.closing {{ background:linear-gradient(160deg,#1B4D3D,#0E2A22); color:#fff; border-radius:14px; padding:14mm 10mm; text-align:center; margin-top:6mm; page-break-inside:avoid; }}
.closing h2 {{ font-size:20pt; color:#fff; border:0; }}
.closing p {{ color:#C7E1D8; font-size:11pt; margin-top:3mm; }}
.closing .cta {{ display:inline-block; margin-top:6mm; background:#C9A85F; color:#0E2A22; font-weight:800; padding:8px 26px; border-radius:30px; font-size:12pt; }}
.closing .url {{ margin-top:5mm; color:#E8D5A8; font-size:11pt; font-weight:700; }}
</style></head>
<body>

<!-- COVER -->
<div class="cover">
  <div class="logo">ضيوف<span class="dot">.</span></div>
  <div class="tg">منصة إدارة الفنادق الذكية</div>
  <div class="sb">نظام سعودي متكامل يدير فندقك من الاستقبال حتى الإيرادات — ١٧ برنامجاً في منصة واحدة</div>
  <div class="rule"></div>
  <div class="feat">
    <div><b>١٧</b> برنامجاً متكاملاً</div>
    <div><b>٢٨</b> جدول بيانات</div>
    <div><b>١٠٠٪</b> عربي</div>
  </div>
  <div class="ftr">www.dheuof.com · العرض الترويجي · يونيو ٢٠٢٥</div>
</div>

<!-- PLATFORM REVIEW / EFFICIENCY -->
<h2 class="section">نظرة عامة · كفاءة المنصة</h2>
<p class="lead">منصة «ضيوف» نظام سحابي متعدد المستأجرين مبني على FastAPI وقاعدة بيانات PostgreSQL، يجمع ١٧ برنامجاً متكاملاً تغطي دورة تشغيل الفندق كاملة. تمت مراجعة كل الوحدات والبيانات والتحقق من ترابطها وجاهزيتها.</p>
<div class="health">
  <div class="hcard"><span class="hv">١٧</span><span class="hl">برنامج تشغيلي متكامل</span></div>
  <div class="hcard"><span class="hv">٢٨</span><span class="hl">جدول في قاعدة البيانات</span></div>
  <div class="hcard"><span class="hv">٧٨<small>/١٠٠</small></span><span class="hl">درجة الأمان الحالية</span></div>
  <div class="hcard"><span class="hv">١٠٠٪</span><span class="hl">واجهة عربية RTL</span></div>
</div>

<h2 class="section">تقييم المحاور بعد التحسينات</h2>
<table class="verify">
  <thead><tr><th style="width:38%">المحور</th><th style="width:18%">قبل</th><th style="width:18%">بعد</th><th style="width:26%">الحالة</th></tr></thead>
  <tbody>
    <tr><td>اتساع الوحدات الوظيفية</td><td><span class="stars">★★★★</span><span class="star-e">☆</span></td><td><span class="stars">★★★★★</span></td><td>✅ ١٧ برنامجاً</td></tr>
    <tr><td>إدارة الإيرادات</td><td><span class="stars">★★</span><span class="star-e">☆☆☆</span></td><td><span class="stars">★★★★</span><span class="star-e">☆</span></td><td>✅ وحدة كاملة جديدة</td></tr>
    <tr><td>بوابات الدفع</td><td><span class="stars">★★</span><span class="star-e">☆☆☆</span></td><td><span class="stars">★★★★</span><span class="star-e">☆</span></td><td>✅ صفحة Payments</td></tr>
    <tr><td>واجهات API والتكاملات</td><td><span class="stars">★★</span><span class="star-e">☆☆☆</span></td><td><span class="stars">★★★★</span><span class="star-e">☆</span></td><td>✅ توثيق API كامل</td></tr>
    <tr><td>الأمن والشهادات</td><td><span class="stars">★★</span>½<span class="star-e">☆☆</span></td><td><span class="stars">★★★★</span><span class="star-e">☆</span></td><td>✅ 2FA + صفحة أمان</td></tr>
    <tr><td>مدير قنوات OTA</td><td><span class="stars">★★</span><span class="star-e">☆☆☆</span></td><td><span class="stars">★★★</span><span class="star-e">☆☆</span></td><td>🟡 قيد التطوير</td></tr>
    <tr><td>النضج والمراجع</td><td><span class="stars">★★</span><span class="star-e">☆☆☆</span></td><td><span class="stars">★★★</span><span class="star-e">☆☆</span></td><td>🟡 خطة العملاء الأوائل</td></tr>
  </tbody>
</table>
<p class="lead" style="font-size:9.5pt;color:#6B6052;">ملاحظة: المحاور ذات الحالة 🟡 تتطلب ربطاً خارجياً فعلياً (قنوات OTA) أو بناء سجل عملاء، وهي موثّقة في «خارطة الحلول التقنية» المرفقة.</p>

<!-- MODULES -->
<h2 class="section">البرامج السبعة عشر · شرح مصوّر</h2>
{module_sections}

<!-- CLOSING -->
<div class="closing">
  <h2>ضيوف — فندقك بالكامل في منصة واحدة</h2>
  <p>ابدأ تجربتك المجانية اليوم — دون بطاقة ائتمان، وبدعم عربي كامل</p>
  <span class="cta">ابدأ التجربة المجانية</span>
  <div class="url">www.dheuof.com</div>
</div>

</body></html>'''

with open('/tmp/promo.html','w',encoding='utf-8') as f:
    f.write(HTML_DOC)
print("HTML written:", len(HTML_DOC), "bytes")
