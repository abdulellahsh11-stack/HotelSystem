#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""توليد تقرير PDF شامل لمنصة ضيوف — دعم RTL كامل بخط Amiri"""

import os
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import cm
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.enums import TA_RIGHT, TA_CENTER
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
    HRFlowable, PageBreak, KeepTogether
)
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
import arabic_reshaper
from bidi.algorithm import get_display

# ── خط Amiri (أفضل خط عربي للـ PDF) ──────────────────────────
_FONT_CANDIDATES = [
    ("/tmp/amiri_fonts/Amiri-1.000/Amiri-Regular.ttf",
     "/tmp/amiri_fonts/Amiri-1.000/Amiri-Bold.ttf"),
    ("/usr/share/fonts/truetype/freefont/FreeSerif.ttf",
     "/usr/share/fonts/truetype/freefont/FreeSerifBold.ttf"),
    ("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
     "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"),
]
BASE_FONT = "Helvetica"
BASE_BOLD = "Helvetica-Bold"
for reg, bld in _FONT_CANDIDATES:
    if os.path.exists(reg):
        pdfmetrics.registerFont(TTFont("ArabicR", reg))
        BASE_FONT = "ArabicR"
        if os.path.exists(bld):
            pdfmetrics.registerFont(TTFont("ArabicB", bld))
            BASE_BOLD = "ArabicB"
        else:
            BASE_BOLD = "ArabicR"
        break


def ar(text: str) -> str:
    """إعادة تشكيل النص العربي للعرض الصحيح RTL."""
    if not text:
        return text
    try:
        reshaped = arabic_reshaper.reshape(str(text))
        return get_display(reshaped)
    except Exception:
        return text


def _ps(name, size=10, bold=False, align=TA_RIGHT,
         color=colors.black, sb=3, sa=3):
    return ParagraphStyle(
        name=name,
        fontName=BASE_BOLD if bold else BASE_FONT,
        fontSize=size,
        textColor=color,
        alignment=align,
        spaceBefore=sb,
        spaceAfter=sa,
        leading=size * 1.7,
        wordWrap='CJK',
        rightIndent=0,
        leftIndent=0,
    )


# ── الألوان ────────────────────────────────────────────────────
NAVY  = colors.HexColor("#0F2640")
BLUE  = colors.HexColor("#185FA5")
TEAL  = colors.HexColor("#0D9488")
GREEN = colors.HexColor("#059669")
ORG   = colors.HexColor("#D97706")
RED   = colors.HexColor("#DC2626")
LGRAY = colors.HexColor("#F1F5F9")
MGRAY = colors.HexColor("#CBD5E1")
DGRAY = colors.HexColor("#64748B")
WHITE = colors.white
LBLUE = colors.HexColor("#DBEAFE")


def _color_score(pct: int):
    if pct >= 88:
        return GREEN
    if pct >= 72:
        return TEAL
    if pct >= 55:
        return ORG
    return RED


# ══════════════════════════════════════════════════════════════
#  البيانات: (الوحدة، الوزن، ضيوف%، أوبرا%، نزيل%، ملاحظة)
# ══════════════════════════════════════════════════════════════
FEATURES = [
    ("المصادقة والأمان",          8,  95, 99, 70,
     "JWT دوار + Argon2id + Rate Limiting + قفل الحساب"),
    ("إدارة الأدوار والصلاحيات",  7,  95, 98, 65,
     "50+ صلاحية في DB + RBAC كامل لكل وحدة"),
    ("إدارة الغرف والأنواع",       8,  90, 99, 80,
     "خريطة تفاعلية + حالات الغرف + أنواع مرنة"),
    ("إدارة الحجوزات",            10, 90, 99, 85,
     "Check-in/out + حساب ضرائب كامل + سجل"),
    ("تطبيق الحجز المباشر",        9,  92, 75, 40,
     "توفر 15-25% عمولات OTA — ميزة تنافسية"),
    ("ضرائب VAT + رسوم سياحة",    8,  95, 90, 55,
     "الحالة A/B المزدوجة + ZATCA متكامل"),
    ("فواتير ZATCA (QR + UBL)",   8,  90, 85, 50,
     "TLV 5 حقول + UBL 2.1 + Scanner بالكاميرا"),
    ("Night Audit",               7,  88, 97, 60,
     "Cron ديناميكي + تقرير PDF شامل"),
    ("التقارير و KPI",             7,  85, 99, 65,
     "6 تقارير تفصيلية + تصدير PDF/Excel"),
    ("Housekeeping",              5,  80, 98, 55,
     "Kanban + مهمة تلقائية عند الـ Checkout"),
    ("Channel Manager",           6,  70, 95, 35,
     "4 قنوات + Webhook — قيد التطوير"),
    ("إدارة الموظفين",            5,  85, 97, 75,
     "RBAC لكل وحدة + تعطيل + سجل نشاط"),
    ("إدارة الضيوف",              6,  88, 98, 70,
     "VIP + حظر + سجل إقامات + Shamoos"),
    ("نظام الاشتراكات",           5,  90, 99, 45,
     "Trial 60 يوم + رقم تسلسلي + تجديد"),
    ("الدعم متعدد اللغات",        4,  80, 99, 70,
     "عربي + إنجليزي + 3 لغات موظفين"),
    ("تطبيق الجوال (Flutter)",    6,  60, 85, 50,
     "Android/iOS — قيد التطوير Q3 2026"),
    ("تكامل Moyasar (الدفع)",     5,  85, 70, 40,
     "MADA + Visa + Apple Pay + بدون عمولة"),
    ("Shamoos / GASTAT",          4,  75, 80, 55,
     "تقرير شهري تلقائي للسياحة"),
    ("Revenue Management",        5,  80, 95, 30,
     "تسعير ديناميكي موسمي + AI لاحقاً"),
    ("Audit Logs",                4,  90, 99, 45,
     "كل العمليات الحساسة مُسجَّلة بالتوقيت"),
]


def _weighted(col_idx: int) -> float:
    total_w = sum(r[1] for r in FEATURES)
    return round(sum(r[1] * r[col_idx] for r in FEATURES) / total_w, 1)


SCORE_D = _weighted(2)
SCORE_O = _weighted(3)
SCORE_N = _weighted(4)


# ══════════════════════════════════════════════════════════════
#  مساعدات البناء
# ══════════════════════════════════════════════════════════════

def _hr():
    return HRFlowable(width="100%", thickness=1.2, color=BLUE, spaceAfter=5)


def _section(title_ar: str, style):
    return [
        Spacer(1, 0.35 * cm),
        Paragraph(ar(title_ar), style),
        _hr(),
    ]


def _score_badge(label: str, pct: float, bg_color) -> Table:
    rows = [
        [Paragraph(ar(label), _ps("bn", size=10, bold=True, color=WHITE, align=TA_CENTER))],
        [Paragraph(f"{pct}%", _ps("bs", size=28, bold=True, color=WHITE, align=TA_CENTER))],
        [Paragraph(ar("النتيجة المرجَّحة"), _ps("bx", size=7.5, color=WHITE, align=TA_CENTER))],
    ]
    t = Table(rows, colWidths=[4.8 * cm])
    t.setStyle(TableStyle([
        ("BACKGROUND",    (0, 0), (-1, -1), bg_color),
        ("TOPPADDING",    (0, 0), (-1, -1), 10),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 10),
        ("LEFTPADDING",   (0, 0), (-1, -1), 4),
        ("RIGHTPADDING",  (0, 0), (-1, -1), 4),
    ]))
    return t


def _progress_bar(pct: int) -> str:
    filled = round(pct / 100 * 10)
    empty = 10 - filled
    return f"{'█' * filled}{'░' * empty} {pct}%"


# ══════════════════════════════════════════════════════════════
#  بناء الـ PDF
# ══════════════════════════════════════════════════════════════

def build_pdf(out_path: str):
    doc = SimpleDocTemplate(
        out_path,
        pagesize=A4,
        rightMargin=1.8 * cm,
        leftMargin=1.8 * cm,
        topMargin=2 * cm,
        bottomMargin=2 * cm,
        title="تقرير منصة ضيوف",
        author="منصة ضيوف",
        subject="مقارنة تنافسية — ضيوف vs Opera vs نزيل",
    )

    # أنماط النص
    H1  = _ps("H1",  size=14, bold=True, color=NAVY,  align=TA_RIGHT,  sb=10, sa=4)
    BD  = _ps("BD",  size=9,              align=TA_RIGHT, sb=2, sa=2)
    CEN = _ps("CEN", size=9,              align=TA_CENTER, sb=2, sa=2)

    story = []

    # ══════════════════════════════════════════════════════════
    #  غلاف التقرير
    # ══════════════════════════════════════════════════════════
    story.append(Spacer(1, 1.2 * cm))

    # عنوان رئيسي في صندوق
    cover_inner = [
        [Paragraph(ar("🏨  منصة  ضيوف"), _ps("cvt", size=28, bold=True, color=NAVY, align=TA_CENTER))],
        [Paragraph(ar("تقرير تحليل الجاهزية والمقارنة التنافسية"), _ps("cvs", size=13, color=BLUE, align=TA_CENTER))],
        [Paragraph(ar("نظام SaaS لإدارة الفنادق في المملكة العربية السعودية"),
                   _ps("cvd", size=10, color=DGRAY, align=TA_CENTER))],
    ]
    cover_tbl = Table(cover_inner, colWidths=[16.4 * cm])
    cover_tbl.setStyle(TableStyle([
        ("BACKGROUND",    (0, 0), (-1, -1), LGRAY),
        ("TOPPADDING",    (0, 0), (-1, -1), 22),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 22),
        ("LEFTPADDING",   (0, 0), (-1, -1), 20),
        ("RIGHTPADDING",  (0, 0), (-1, -1), 20),
        ("LINEBELOW",     (0, -1), (-1, -1), 3, BLUE),
    ]))
    story.append(cover_tbl)
    story.append(Spacer(1, 0.6 * cm))
    story.append(Paragraph(ar("www.dheuof.com  ·  info@dheuof.com  ·  يونيو 2026"),
                            _ps("meta", size=8, color=DGRAY, align=TA_CENTER)))
    story.append(Spacer(1, 1.0 * cm))

    # ── بطاقات النتيجة ──────────────────────────────────────
    badges = Table(
        [[
            _score_badge("منصة ضيوف",   SCORE_D, BLUE),
            _score_badge("Oracle Opera", SCORE_O, NAVY),
            _score_badge("نزيل",         SCORE_N, TEAL),
        ]],
        colWidths=[5.4 * cm, 5.4 * cm, 5.4 * cm],
    )
    badges.setStyle(TableStyle([
        ("ALIGN",         (0, 0), (-1, -1), "CENTER"),
        ("VALIGN",        (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING",   (0, 0), (-1, -1), 2),
        ("RIGHTPADDING",  (0, 0), (-1, -1), 2),
        ("TOPPADDING",    (0, 0), (-1, -1), 0),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
    ]))
    story.append(badges)
    story.append(Spacer(1, 1.0 * cm))

    # ══════════════════════════════════════════════════════════
    #  ١ — الملخص التنفيذي
    # ══════════════════════════════════════════════════════════
    story += _section("١. الملخص التنفيذي", H1)
    summary = [
        "منصة ضيوف نظام SaaS متعدد المستأجرين مبني بـ NestJS + Next.js + Flutter + PostgreSQL.",
        f"النتيجة الإجمالية المرجَّحة: ضيوف {SCORE_D}% مقابل Opera {SCORE_O}% ونزيل {SCORE_N}%.",
        "تتفوق المنصة على نزيل في جميع الوحدات الأساسية وتقترب من Opera في التشغيل اليومي للفنادق متوسطة الحجم.",
        "أبرز الميزات الحصرية: تطبيق حجز مباشر بلا عمولة + ضرائب ثنائية المسؤولية + ZATCA كامل + متعدد اللغات للموظفين.",
        "النقاط الأقل نضجاً: Channel Manager وتطبيق Flutter — لا تؤثر على التشغيل اليومي وهي قيد التطوير.",
    ]
    for pt in summary:
        story.append(Paragraph(f"◆  {ar(pt)}", BD))
    story.append(Spacer(1, 0.3 * cm))

    # ══════════════════════════════════════════════════════════
    #  ٢ — جدول المقارنة التفصيلية
    # ══════════════════════════════════════════════════════════
    story.append(PageBreak())
    story += _section("٢. جدول المقارنة التفصيلية — ٢٠ وحدة", H1)

    # رأس الجدول: RTL — الأكثر أهمية على اليمين
    hdr_cells = [
        Paragraph(ar("الوحدة"),    _ps("hc", size=8, bold=True, color=WHITE, align=TA_RIGHT)),
        Paragraph(ar("الوزن"),     _ps("hc", size=8, bold=True, color=WHITE, align=TA_CENTER)),
        Paragraph(ar("ضيوف"),      _ps("hc", size=8, bold=True, color=WHITE, align=TA_CENTER)),
        Paragraph(ar("Opera"),     _ps("hc", size=8, bold=True, color=WHITE, align=TA_CENTER)),
        Paragraph(ar("نزيل"),      _ps("hc", size=8, bold=True, color=WHITE, align=TA_CENTER)),
        Paragraph(ar("الملاحظة"), _ps("hc", size=8, bold=True, color=WHITE, align=TA_RIGHT)),
    ]

    tdata = [hdr_cells]
    for row in FEATURES:
        name, w, dh, op, nz, note = row
        tdata.append([
            Paragraph(ar(name), _ps("tc", size=8.5, align=TA_RIGHT)),
            Paragraph(f"{w}",   _ps("tw", size=8,   align=TA_CENTER)),
            Paragraph(f"{dh}%", _ps("td", size=8.5, bold=True, align=TA_CENTER, color=_color_score(dh))),
            Paragraph(f"{op}%", _ps("to", size=8,   align=TA_CENTER, color=_color_score(op))),
            Paragraph(f"{nz}%", _ps("tn", size=8,   align=TA_CENTER, color=_color_score(nz))),
            Paragraph(ar(note), _ps("nt", size=7.5, color=DGRAY, align=TA_RIGHT)),
        ])

    # صف المجموع المرجَّح
    tdata.append([
        Paragraph(ar("المجموع المرجَّح"), _ps("tot", size=9, bold=True, align=TA_RIGHT)),
        Paragraph("100",  _ps("tot", size=9, bold=True, align=TA_CENTER)),
        Paragraph(f"{SCORE_D}%", _ps("tot", size=10, bold=True, align=TA_CENTER, color=BLUE)),
        Paragraph(f"{SCORE_O}%", _ps("tot", size=10, bold=True, align=TA_CENTER, color=NAVY)),
        Paragraph(f"{SCORE_N}%", _ps("tot", size=10, bold=True, align=TA_CENTER, color=TEAL)),
        Paragraph("", CEN),
    ])

    col_w = [3.8 * cm, 1.0 * cm, 1.6 * cm, 1.6 * cm, 1.6 * cm, 6.7 * cm]
    feat_tbl = Table(tdata, colWidths=col_w, repeatRows=1)
    feat_tbl.setStyle(TableStyle([
        ("BACKGROUND",    (0, 0),  (-1, 0),  NAVY),
        ("TEXTCOLOR",     (0, 0),  (-1, 0),  WHITE),
        ("TOPPADDING",    (0, 0),  (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0),  (-1, -1), 5),
        ("LEFTPADDING",   (0, 0),  (-1, -1), 4),
        ("RIGHTPADDING",  (0, 0),  (-1, -1), 4),
        ("GRID",          (0, 0),  (-1, -1), 0.4, MGRAY),
        ("ROWBACKGROUNDS",(0, 1),  (-1, -2), [WHITE, LGRAY]),
        ("BACKGROUND",    (0, -1), (-1, -1), LBLUE),
        ("FONTSIZE",      (0, -1), (-1, -1), 9),
        ("ALIGN",         (1, 0),  (4, -1),  "CENTER"),
        ("VALIGN",        (0, 0),  (-1, -1), "MIDDLE"),
        ("LINEABOVE",     (0, -1), (-1, -1), 1.5, BLUE),
    ]))
    story.append(feat_tbl)
    story.append(Spacer(1, 0.3 * cm))

    # أسطورة الألوان
    legend_data = [[
        Paragraph("■", _ps("lg", size=10, color=GREEN,  align=TA_CENTER)),
        Paragraph(ar("88% فأكثر: ممتاز"), _ps("lt", size=8, align=TA_RIGHT)),
        Paragraph("■", _ps("lg", size=10, color=TEAL,   align=TA_CENTER)),
        Paragraph(ar("72-87%: جيد"),      _ps("lt", size=8, align=TA_RIGHT)),
        Paragraph("■", _ps("lg", size=10, color=ORG,    align=TA_CENTER)),
        Paragraph(ar("55-71%: متوسط"),   _ps("lt", size=8, align=TA_RIGHT)),
        Paragraph("■", _ps("lg", size=10, color=RED,    align=TA_CENTER)),
        Paragraph(ar("أقل من 55%: ضعيف"), _ps("lt", size=8, align=TA_RIGHT)),
    ]]
    legend_tbl = Table(legend_data, colWidths=[0.5*cm, 3*cm, 0.5*cm, 2.5*cm,
                                               0.5*cm, 2.5*cm, 0.5*cm, 3*cm])
    legend_tbl.setStyle(TableStyle([
        ("VALIGN",  (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING",    (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
    ]))
    story.append(legend_tbl)

    # ══════════════════════════════════════════════════════════
    #  ٣ — الميزات التنافسية الحصرية
    # ══════════════════════════════════════════════════════════
    story.append(PageBreak())
    story += _section("٣. الميزات التنافسية الحصرية لمنصة ضيوف", H1)

    exclusive = [
        ("ضرائب ثنائية المسؤولية (حالة A/B)", "95%", BLUE,
         "المدير يختار: الضيف يتحمل الضريبة أم المنشأة. كلا الحالتين يُرسَل منها VAT صحيح لـ ZATCA. "
         "لا يوجد هذا التمييز في Opera أو نزيل بنفس المرونة."),
        ("تطبيق الحجز المباشر بلا عمولة", "92%", GREEN,
         "رابط فريد لكل منشأة dheuof.com/book/{slug} يوفر 15-25% عمولات OTA. "
         "Opera لا يوفره مجاناً، ونزيل غير مكتمل في هذا الجانب."),
        ("ZATCA كامل: QR + UBL 2.1 + Scanner", "90%", TEAL,
         "فاتورة مبسَّطة UBL 2.1 + QR TLV بـ 5 حقول + Scanner بالكاميرا للتحقق الفوري. "
         "رسوم السياحة تظهر كسطر منفصل في XML."),
        ("Night Audit مرن مع وقت قابل للتعديل", "88%", NAVY,
         "Cron ديناميكي يُعاد ضبطه فوراً عند تغيير وقت الـ Audit. "
         "يشترط إغلاق جميع المدفوعات المعلَّقة قبل التشغيل."),
        ("معرّف رقمي 8 أرقام + بريد تلقائي", "95%", BLUE,
         "عند التسجيل: معرّف عشوائي + بريد Zoho SMTP يصل فوراً بتصميم احترافي. "
         "صفر تدخل بشري."),
        ("واجهة متعددة اللغات للموظفين", "80%", TEAL,
         "عربي + إنجليزي + هندي + نيبالي + بنغالي. "
         "يخدم العمالة الوافدة مباشرةً دون الحاجة لمترجم."),
    ]

    for title_e, pct_e, clr_e, desc_e in exclusive:
        hdr_row = [[
            Paragraph(ar(title_e), _ps("et", size=10, bold=True, color=WHITE, align=TA_RIGHT)),
            Paragraph(pct_e, _ps("ep", size=13, bold=True, color=WHITE, align=TA_CENTER)),
        ]]
        hdr_t = Table(hdr_row, colWidths=[13.4 * cm, 3.0 * cm])
        hdr_t.setStyle(TableStyle([
            ("BACKGROUND",    (0, 0), (-1, -1), clr_e),
            ("TOPPADDING",    (0, 0), (-1, -1), 7),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
            ("LEFTPADDING",   (0, 0), (0, 0), 10),
            ("RIGHTPADDING",  (0, 0), (0, 0), 10),
        ]))
        desc_row = [[
            Paragraph(ar(f"    {desc_e}"), _ps("ed", size=9, align=TA_RIGHT)),
        ]]
        desc_t = Table(desc_row, colWidths=[16.4 * cm])
        desc_t.setStyle(TableStyle([
            ("BACKGROUND",    (0, 0), (-1, -1), LGRAY),
            ("TOPPADDING",    (0, 0), (-1, -1), 6),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
            ("LEFTPADDING",   (0, 0), (-1, -1), 10),
            ("RIGHTPADDING",  (0, 0), (-1, -1), 10),
            ("LINEBELOW",     (0, 0), (-1, -1), 0.5, MGRAY),
        ]))
        story.append(KeepTogether([hdr_t, desc_t, Spacer(1, 0.25 * cm)]))

    # ══════════════════════════════════════════════════════════
    #  ٤ — نقاط الضعف والفجوات
    # ══════════════════════════════════════════════════════════
    story += _section("٤. الفجوات مقارنةً بـ Oracle Opera وخطة الإغلاق", H1)

    gaps = [
        ("Channel Manager",   70,
         "Opera يدعم 500+ قناة. ضيوف 4 قنوات حالياً. الهدف: إضافة Makkah Gate + Agoda بـ Q3 2026."),
        ("تطبيق الجوال",      60,
         "Opera Cloud يوفر iOS/Android ناضج. Flutter قيد التطوير — متوقع Android Q3 ثم iOS Q4 2026."),
        ("Revenue Mgmt / AI", 80,
         "Opera يوفر Forecasting + AI Pricing متقدم. ضيوف يوفر تسعيراً موسمياً — AI قادم Q1 2027."),
        ("Concierge",          0,
         "خدمات الكونسيرج والطلبات الداخلية غير موجودة — Opera متكامل هنا. خطة Q1 2027."),
        ("POS متكامل بالمخزون",75,
         "Opera يوفر POS كامل للمطاعم مع المخزون. ضيوف: POS مبسط — الربط بالمخزون قادم Q4 2026."),
        ("SPA / Activity Mgmt", 0,
         "إدارة الفعاليات والسبا غير مدعومة حالياً. Opera يتفوق هنا. خطة Q1 2027."),
    ]

    ghdr = [
        Paragraph(ar("الوحدة"),     _ps("gh", size=8, bold=True, color=WHITE, align=TA_RIGHT)),
        Paragraph(ar("التغطية"),    _ps("gh", size=8, bold=True, color=WHITE, align=TA_CENTER)),
        Paragraph(ar("الملاحظة وخطة الإغلاق"), _ps("gh", size=8, bold=True, color=WHITE, align=TA_RIGHT)),
    ]
    gdata = [ghdr]
    for gname, gpct, gnote in gaps:
        gdata.append([
            Paragraph(ar(gname), _ps("gr", size=9, bold=True, align=TA_RIGHT)),
            Paragraph(
                f"{gpct}%" if gpct else ar("غير متوفر"),
                _ps("gp", size=9, bold=True, align=TA_CENTER,
                    color=_color_score(gpct) if gpct else RED),
            ),
            Paragraph(ar(gnote), _ps("gn", size=8, color=DGRAY, align=TA_RIGHT)),
        ])

    gap_tbl = Table(gdata, colWidths=[3.5 * cm, 2.0 * cm, 11.2 * cm])
    gap_tbl.setStyle(TableStyle([
        ("BACKGROUND",    (0, 0),  (-1, 0),  RED),
        ("TEXTCOLOR",     (0, 0),  (-1, 0),  WHITE),
        ("ROWBACKGROUNDS",(0, 1),  (-1, -1), [WHITE, LGRAY]),
        ("GRID",          (0, 0),  (-1, -1), 0.4, MGRAY),
        ("TOPPADDING",    (0, 0),  (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0),  (-1, -1), 6),
        ("LEFTPADDING",   (0, 0),  (-1, -1), 5),
        ("RIGHTPADDING",  (0, 0),  (-1, -1), 5),
        ("VALIGN",        (0, 0),  (-1, -1), "MIDDLE"),
    ]))
    story.append(gap_tbl)

    # ══════════════════════════════════════════════════════════
    #  ٥ — خارطة الطريق
    # ══════════════════════════════════════════════════════════
    story.append(PageBreak())
    story += _section("٥. خارطة الطريق للوصول إلى 96%+", H1)

    roadmap = [
        ("الربع الثالث 2026", BLUE, [
            "إطلاق تطبيق Flutter للـ Android مع Check-in / Check-out",
            "Channel Manager: إضافة Agoda + Makkah Gate + Booking.com",
            "AI Pricing: توقع الطلب حسب الموسم والأحداث الخاصة",
            "تحسين الـ Revenue Management بالبيانات التاريخية",
        ]),
        ("الربع الرابع 2026", TEAL, [
            "POS متكامل مع المخزون والمطبخ",
            "إطلاق تطبيق Flutter للـ iOS",
            "تكامل Unifonic للـ SMS + WhatsApp",
            "نظام الولاء والنقاط للضيوف المتكررين",
        ]),
        ("الربع الأول 2027", GREEN, [
            "Concierge Module — طلبات داخلية + Room Service",
            "Revenue Management بالـ AI (Forecasting كامل)",
            "SPA / Activity Management",
            "تكامل Shamoos تلقائي موسَّع",
        ]),
    ]

    for qtr, qclr, items in roadmap:
        qhdr = Table(
            [[Paragraph(ar(f"🗓  {qtr}"), _ps("qh", size=11, bold=True, color=WHITE, align=TA_RIGHT))]],
            colWidths=[16.4 * cm],
        )
        qhdr.setStyle(TableStyle([
            ("BACKGROUND",    (0, 0), (-1, -1), qclr),
            ("TOPPADDING",    (0, 0), (-1, -1), 9),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 9),
            ("LEFTPADDING",   (0, 0), (-1, -1), 14),
            ("RIGHTPADDING",  (0, 0), (-1, -1), 14),
        ]))
        item_blocks = [qhdr]
        for item in items:
            item_blocks.append(
                Paragraph(f"    ✓  {ar(item)}", _ps("qi", size=9, align=TA_RIGHT))
            )
        item_blocks.append(Spacer(1, 0.4 * cm))
        story.append(KeepTogether(item_blocks))

    # ══════════════════════════════════════════════════════════
    #  ٦ — خلاصة وتوصية
    # ══════════════════════════════════════════════════════════
    story += _section("٦. الخلاصة والتوصية", H1)

    conc_text = (
        f"منصة ضيوف جاهزة للتشغيل الكامل للفنادق السعودية متوسطة الحجم بنسبة {SCORE_D}%، "
        f"وتتفوق على نزيل ({SCORE_N}%) في جميع الوحدات الأساسية. "
        f"الفجوة مع Oracle Opera ({SCORE_O}%) محصورة في وحدات متقدمة (Concierge / SPA / Channel Manager المتكامل) "
        "لا تؤثر على التشغيل اليومي للفنادق متوسطة الحجم. "
        "أبرز الميزات التنافسية: تطبيق الحجز المباشر بلا عمولة + ضرائب ثنائية المسؤولية + "
        "ZATCA متكامل + دعم لغات الموظفين + معرّف رقمي + بريد تلقائي. "
        "التوصية: الإطلاق التجاري فوراً مع التطوير التدريجي للوحدات المتبقية وفق خارطة الطريق."
    )

    conc_tbl = Table(
        [[Paragraph(ar(conc_text), _ps("ct", size=9.5, align=TA_RIGHT, sb=0, sa=0))]],
        colWidths=[16.4 * cm],
    )
    conc_tbl.setStyle(TableStyle([
        ("BACKGROUND",    (0, 0), (-1, -1), LBLUE),
        ("LEFTPADDING",   (0, 0), (-1, -1), 16),
        ("RIGHTPADDING",  (0, 0), (-1, -1), 16),
        ("TOPPADDING",    (0, 0), (-1, -1), 16),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 16),
        ("BOX",           (0, 0), (-1, -1), 2, BLUE),
    ]))
    story.append(conc_tbl)
    story.append(Spacer(1, 0.6 * cm))
    story.append(Paragraph(
        ar("أُعدَّ هذا التقرير في يونيو 2026  ·  منصة ضيوف  ·  www.dheuof.com  ·  info@dheuof.com"),
        _ps("ft", size=8, color=DGRAY, align=TA_CENTER),
    ))

    doc.build(story)
    print(f"✅ التقرير جاهز: {out_path}")


# ══════════════════════════════════════════════════════════════
if __name__ == "__main__":
    out = os.path.join(os.path.dirname(__file__), "..", "dheuof_platform_report.pdf")
    build_pdf(os.path.abspath(out))
