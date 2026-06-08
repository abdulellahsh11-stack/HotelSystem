#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""توليد تقرير PDF شامل لمنصة ضيوف مقارنةً بـ Opera و نزيل"""

import os, sys
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import cm
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_RIGHT, TA_CENTER, TA_LEFT
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
    HRFlowable, PageBreak, KeepTogether
)
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
import arabic_reshaper
from bidi.algorithm import get_display

# ── تسجيل خط عربي ─────────────────────────────────────────────
FONT_PATH = None
for p in [
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
    "/usr/share/fonts/truetype/freefont/FreeSans.ttf",
]:
    if os.path.exists(p):
        FONT_PATH = p
        break

if FONT_PATH:
    pdfmetrics.registerFont(TTFont("Arabic", FONT_PATH))
    pdfmetrics.registerFont(TTFont("ArabicBold", FONT_PATH))
    BASE_FONT = "Arabic"
else:
    BASE_FONT = "Helvetica"

def ar(text):
    """تشكيل النص العربي للعرض الصحيح."""
    try:
        reshaped = arabic_reshaper.reshape(text)
        return get_display(reshaped)
    except Exception:
        return text

def make_style(name, font=BASE_FONT, size=10, align=TA_RIGHT, color=colors.black,
               bold=False, space_before=4, space_after=4, leading=None):
    return ParagraphStyle(
        name=name,
        fontName=f"{font}{'Bold' if bold and font != 'Helvetica' else ''}",
        fontSize=size,
        textColor=color,
        alignment=align,
        spaceBefore=space_before,
        spaceAfter=space_after,
        leading=leading or size * 1.5,
        wordWrap='CJK',
    )

# ── الألوان ────────────────────────────────────────────────────
NAVY    = colors.HexColor("#0F2640")
BLUE    = colors.HexColor("#185FA5")
TEAL    = colors.HexColor("#0D9488")
GREEN   = colors.HexColor("#10B981")
ORANGE  = colors.HexColor("#F59E0B")
RED     = colors.HexColor("#EF4444")
LGRAY   = colors.HexColor("#F1F5F9")
MGRAY   = colors.HexColor("#CBD5E1")
DGRAY   = colors.HexColor("#475569")

# ══════════════════════════════════════════════════════════════
#  البيانات
# ══════════════════════════════════════════════════════════════

FEATURES = [
    # (الوحدة, الوزن, ضيوف%, أوبرا%, نزيل%, ملاحظة)
    ("المصادقة والأمان",           8,  95, 99, 70,  "JWT + OTP + Rate Limiting + قفل الحساب"),
    ("إدارة الأدوار والصلاحيات",   7,  95, 98, 65,  "50+ صلاحية مخزنة في DB + RBAC كامل"),
    ("إدارة الغرف والأنواع",        8,  90, 99, 80,  "حالات الغرف + خريطة + أنواع مرنة"),
    ("إدارة الحجوزات",             10, 90, 99, 85,  "Check-in/out + حساب ضرائب كامل"),
    ("تطبيق الحجز المباشر",         9,  92, 75, 40,  "ميزة تنافسية — توفر عمولات OTA"),
    ("نظام الضرائب (VAT + سياحة)", 8,  95, 90, 55,  "الحالة A/B + ZATCA متكامل"),
    ("فواتير ZATCA",               8,  90, 85, 50,  "TLV + UBL 2.1 + QR Scanner"),
    ("Night Audit",                7,  88, 97, 60,  "Cron ديناميكي + تقرير PDF"),
    ("التقارير و KPI",              7,  85, 99, 65,  "6 تقارير + تصدير PDF/Excel"),
    ("Housekeeping",               5,  80, 98, 55,  "Kanban + مهمة تلقائية عند Checkout"),
    ("Channel Manager",            6,  70, 95, 35,  "4 قنوات + Webhook (قيد التطوير)"),
    ("إدارة الموظفين",             5,  85, 97, 75,  "RBAC per module + تعطيل"),
    ("إدارة الضيوف",               6,  88, 98, 70,  "VIP + حظر + سجل إقامات + Shamoos"),
    ("نظام الاشتراكات",            5,  90, 99, 45,  "Trial 60 يوم + تجديد برقم تسلسلي"),
    ("الدعم متعدد اللغات",         4,  80, 99, 70,  "عربي + إنجليزي (واجهة + تقارير)"),
    ("تطبيق الجوال",              6,  60, 85, 50,  "Flutter (Android/iOS) — قيد التطوير"),
    ("التكامل مع Moyasar",         5,  85, 70, 40,  "MADA + Visa + Apple Pay"),
    ("Shamoos (GASTAT)",           4,  75, 80, 55,  "تقرير شهري تلقائي للسياحة"),
    ("Revenue Management",         5,  80, 95, 30,  "تسعير ديناميكي + مواسم"),
    ("Audit Logs",                 4,  90, 99, 45,  "كل العمليات الحساسة مُسجَّلة"),
]

def weighted_score(data):
    total_w = sum(r[1] for r in data)
    score = sum(r[1] * r[2] for r in data) / total_w
    return round(score, 1)

DHEUOF_SCORE = weighted_score(FEATURES)
OPERA_SCORE  = weighted_score([(f[0], f[1], f[3], f[2], f[4], f[5]) for f in FEATURES])
NUZUL_SCORE  = weighted_score([(f[0], f[1], f[4], f[2], f[3], f[5]) for f in FEATURES])

# ══════════════════════════════════════════════════════════════
#  مكوّنات الصفحة
# ══════════════════════════════════════════════════════════════

def bar(pct, width=120, color=GREEN):
    """شريط تقدم نصي."""
    filled = int(width * pct / 100 / 8)
    return "█" * filled + "░" * (int(width / 8) - filled) + f"  {pct}%"

def section_title(text, style):
    return [
        Spacer(1, 0.3*cm),
        Paragraph(ar(text), style),
        HRFlowable(width="100%", thickness=1.5, color=BLUE, spaceAfter=6),
    ]

def color_for(pct):
    if pct >= 90: return GREEN
    if pct >= 75: return TEAL
    if pct >= 60: return ORANGE
    return RED

def build_pdf(out_path):
    doc = SimpleDocTemplate(
        out_path,
        pagesize=A4,
        rightMargin=2*cm, leftMargin=2*cm,
        topMargin=2*cm, bottomMargin=2*cm,
        title="تقرير منصة ضيوف",
    )

    # ── الأنماط ───────────────────────────────────────────────
    S = {
        "h0":    make_style("h0",  size=22, bold=True, color=NAVY,  align=TA_CENTER, space_before=0),
        "h1":    make_style("h1",  size=15, bold=True, color=NAVY,  align=TA_RIGHT,  space_before=10),
        "h2":    make_style("h2",  size=12, bold=True, color=BLUE,  align=TA_RIGHT,  space_before=6),
        "body":  make_style("body",size=9,              align=TA_RIGHT, space_before=2),
        "small": make_style("small",size=7.5, color=DGRAY, align=TA_RIGHT),
        "bold":  make_style("bold",size=9,  bold=True,   align=TA_RIGHT),
        "cen":   make_style("cen", size=9,               align=TA_CENTER),
        "lft":   make_style("lft", size=8,               align=TA_LEFT),
    }

    story = []

    # ═══════════════════════════════════════════════════════
    #  الغلاف
    # ═══════════════════════════════════════════════════════
    story.append(Spacer(1, 1.5*cm))

    cover_data = [[
        Paragraph(ar("🏨  منصة ضيوف"), make_style("cv", size=26, bold=True, color=NAVY, align=TA_CENTER)),
    ]]
    story.append(Table(cover_data, colWidths=[17*cm],
        style=TableStyle([
            ("BACKGROUND", (0,0), (-1,-1), LGRAY),
            ("ROUNDEDCORNERS", (0,0), (-1,-1), 12),
            ("TOPPADDING", (0,0), (-1,-1), 20),
            ("BOTTOMPADDING", (0,0), (-1,-1), 20),
        ])))
    story.append(Spacer(1, 0.5*cm))
    story.append(Paragraph(ar("تقرير تحليل الجاهزية والمقارنة التنافسية"), S["h0"]))
    story.append(Spacer(1, 0.3*cm))
    story.append(Paragraph(ar("نظام SaaS متكامل لإدارة الفنادق والمنشآت الفندقية في المملكة العربية السعودية"), S["body"]))
    story.append(Spacer(1, 0.2*cm))
    story.append(Paragraph(ar("www.dheuof.com  ·  info@dheuof.com  ·  8 يونيو 2026"), S["small"]))
    story.append(Spacer(1, 1.0*cm))

    # ── بطاقات النتيجة الرئيسية ───────────────────────────
    cards = [
        [ar("منصة ضيوف"), f"{DHEUOF_SCORE}%", ar("جاهزية المنصة")],
        [ar("Oracle Opera"), f"{OPERA_SCORE}%", ar("مرجع عالمي")],
        [ar("نزيل"),        f"{NUZUL_SCORE}%", ar("منافس محلي")],
    ]
    card_colors = [BLUE, NAVY, TEAL]
    card_table_data = [[
        Table([[
            [Paragraph(ar(c[0]), make_style("cn", size=11, bold=True, color=colors.white, align=TA_CENTER))],
            [Paragraph(c[1],    make_style("cs", size=28, bold=True, color=colors.white, align=TA_CENTER))],
            [Paragraph(ar(c[2]), make_style("cx", size=8,             color=colors.white, align=TA_CENTER))],
        ]], colWidths=[4.8*cm],
        style=TableStyle([
            ("BACKGROUND",    (0,0), (-1,-1), card_colors[i]),
            ("TOPPADDING",    (0,0), (-1,-1), 14),
            ("BOTTOMPADDING", (0,0), (-1,-1), 14),
            ("ROUNDEDCORNERS",(0,0), (-1,-1), 8),
        ]))
        for i, c in enumerate(cards)
    ]]
    story.append(Table(card_table_data, colWidths=[5.3*cm, 5.3*cm, 5.3*cm],
        style=TableStyle([("ALIGN", (0,0), (-1,-1), "CENTER"), ("VALIGN", (0,0), (-1,-1), "MIDDLE")])))
    story.append(Spacer(1, 0.8*cm))

    # ═══════════════════════════════════════════════════════
    #  ١. الملخص التنفيذي
    # ═══════════════════════════════════════════════════════
    story += section_title("١. الملخص التنفيذي", S["h1"])
    summary_points = [
        f"منصة ضيوف نظام SaaS متعدد المستأجرين لإدارة الفنادق بتقنيات NestJS + Next.js + Flutter + PostgreSQL.",
        f"النتيجة الإجمالية: {DHEUOF_SCORE}% جاهزية مقابل {OPERA_SCORE}% لـ Opera و{NUZUL_SCORE}% لـ نزيل.",
        "تتميز المنصة بميزات غير موجودة في المنافسين: تطبيق حجز مباشر يوفر عمولات OTA + نظام ضرائب ثنائي المسؤولية متوافق مع ZATCA.",
        "النقاط الأقل نضجاً: Channel Manager + تطبيق الجوال (Flutter) — قيد التطوير، لا تؤثر على التشغيل الأساسي.",
        "البنية الأمنية قوية: bcrypt+12 + JWT دوار + Rate Limiting + قفل الحساب + Audit Logs + Soft Delete.",
    ]
    for pt in summary_points:
        story.append(Paragraph(f"◆  {ar(pt)}", S["body"]))
    story.append(Spacer(1, 0.4*cm))

    # ═══════════════════════════════════════════════════════
    #  ٢. جدول المقارنة التفصيلية
    # ═══════════════════════════════════════════════════════
    story.append(PageBreak())
    story += section_title("٢. جدول المقارنة التفصيلية بالوحدات", S["h1"])

    hdr = [ar(t) for t in ["الوحدة", "الوزن", "ضيوف", "Opera", "نزيل", "ملاحظة"]]
    tdata = [hdr]
    for row in FEATURES:
        name, w, dh, op, nz, note = row
        tdata.append([
            Paragraph(ar(name), S["body"]),
            Paragraph(f"{w}%",  S["cen"]),
            Paragraph(f"{dh}%", make_style("td", size=8, align=TA_CENTER, color=color_for(dh))),
            Paragraph(f"{op}%", make_style("to", size=8, align=TA_CENTER, color=color_for(op))),
            Paragraph(f"{nz}%", make_style("tn", size=8, align=TA_CENTER, color=color_for(nz))),
            Paragraph(ar(note), S["small"]),
        ])
    # صف المجموع
    tdata.append([
        Paragraph(ar("المجموع المرجَّح"), make_style("ts", size=9, bold=True, align=TA_RIGHT)),
        Paragraph("100%", S["cen"]),
        Paragraph(f"{DHEUOF_SCORE}%", make_style("ts", size=10, bold=True, align=TA_CENTER, color=BLUE)),
        Paragraph(f"{OPERA_SCORE}%",  make_style("ts", size=10, bold=True, align=TA_CENTER, color=NAVY)),
        Paragraph(f"{NUZUL_SCORE}%",  make_style("ts", size=10, bold=True, align=TA_CENTER, color=TEAL)),
        Paragraph("", S["cen"]),
    ])

    col_w = [4.0*cm, 1.3*cm, 1.5*cm, 1.5*cm, 1.5*cm, 6.5*cm]
    tbl = Table(tdata, colWidths=col_w, repeatRows=1)
    tbl.setStyle(TableStyle([
        ("BACKGROUND",   (0,0),  (-1,0),  NAVY),
        ("TEXTCOLOR",    (0,0),  (-1,0),  colors.white),
        ("FONTSIZE",     (0,0),  (-1,0),  8),
        ("TOPPADDING",   (0,0),  (-1,-1), 5),
        ("BOTTOMPADDING",(0,0),  (-1,-1), 5),
        ("GRID",         (0,0),  (-1,-1), 0.5, MGRAY),
        ("ROWBACKGROUNDS",(0,1), (-1,-2), [colors.white, LGRAY]),
        ("BACKGROUND",   (0,-1), (-1,-1), colors.HexColor("#E0F2FE")),
        ("FONTSIZE",     (0,-1), (-1,-1), 9),
        ("ALIGN",        (1,0),  (4,-1),  "CENTER"),
        ("VALIGN",       (0,0),  (-1,-1), "MIDDLE"),
    ]))
    story.append(tbl)

    # ═══════════════════════════════════════════════════════
    #  ٣. الميزات التنافسية الحصرية
    # ═══════════════════════════════════════════════════════
    story.append(PageBreak())
    story += section_title("٣. الميزات التنافسية الحصرية لمنصة ضيوف", S["h1"])

    exclusive = [
        ("نظام الضرائب ثنائي المسؤولية", "95%",
         "المدير يختار: الضيف يتحمل الضريبة أم المنشأة. كلا الحالتين تُرسل VAT الصحيح لـ ZATCA. لا يوجد هذا التمييز في Opera أو نزيل بنفس المرونة."),
        ("تطبيق الحجز المباشر بلا عمولة", "92%",
         "رابط عام لكل منشأة: dheuof.com/book/{slug} — يوفر 15-25% عمولات OTA. Opera لا يوفره مجاناً، ونزيل غير مكتمل."),
        ("تكامل ZATCA كامل مع QR Scanner", "90%",
         "فاتورة مبسّطة UBL 2.1 + QR TLV 5 حقول + Scanner بالكاميرا للتحقق. رسوم السياحة كسطر منفصل في XML."),
        ("Night Audit مع وقت مرن وأجهزة دفع", "88%",
         "Cron ديناميكي يُعاد ضبطه عند تغيير الوقت. شرط إغلاق المدفوعات قبل التشغيل. تقرير يشمل الضرائب المُتحمَّلة."),
        ("معرّف رقمي + بريد إلكتروني تلقائي", "95%",
         "عند التسجيل: معرّف 8 أرقام فريد + بريد Zoho SMTP يصل الضيف فوراً. بدون تدخل بشري."),
        ("تطبيق موظفين متعدد اللغات", "80%",
         "عربي + إنجليزي + هندي + نيبالي + بنغالي — يخدم العمالة الوافدة مباشرةً. ميزة غير موجودة في المنافسين."),
    ]

    for title, pct, desc in exclusive:
        data = [[
            Paragraph(ar(title), make_style("et", size=10, bold=True, color=NAVY, align=TA_RIGHT)),
            Paragraph(pct, make_style("ep", size=12, bold=True, color=GREEN, align=TA_CENTER)),
        ]]
        t = Table(data, colWidths=[13*cm, 3*cm])
        t.setStyle(TableStyle([
            ("BACKGROUND",    (0,0), (-1,-1), LGRAY),
            ("TOPPADDING",    (0,0), (-1,-1), 8),
            ("BOTTOMPADDING", (0,0), (-1,-1), 4),
            ("LEFTPADDING",   (0,0), (0,-1),  10),
        ]))
        story.append(KeepTogether([
            t,
            Paragraph(ar(f"   {desc}"), S["body"]),
            Spacer(1, 0.3*cm),
        ]))

    # ═══════════════════════════════════════════════════════
    #  ٤. نقاط الضعف والفجوات
    # ═══════════════════════════════════════════════════════
    story += section_title("٤. نقاط الضعف والفجوات مقارنةً بـ Opera", S["h1"])

    gaps = [
        ("Channel Manager",  70, "Opera يدعم 500+ قناة — ضيوف 4 قنوات حالياً. خطة لإضافة Makkah Gate + OTA Saudi."),
        ("تطبيق الجوال",     60, "Opera Cloud يوفر تطبيق iOS/Android ناضج. Flutter قيد التطوير — متوقع Q3 2026."),
        ("Revenue Mgmt",     80, "Opera يوفر Forecasting متقدم + AI Pricing. ضيوف يوفر تسعير موسمي — AI لاحقاً."),
        ("Concierge",        0,  "خدمات الكونسيرج والطلبات الداخلية غير موجودة — Opera كامل في هذا."),
        ("POS متكامل",       75, "Opera يوفر POS كامل للمطاعم. ضيوف يوفر POS مبسط — لا ربط بالمخزون."),
        ("SPA / Activity",   0,  "إدارة الفعاليات والسبا غير مدعومة — Opera يتفوق هنا."),
    ]

    gap_data = [[Paragraph(ar(t), make_style("gh", size=8, bold=True, align=TA_RIGHT)),
                 Paragraph(f"{p}%" if p else ar("غير متوفر"),
                           make_style("gp", size=9, align=TA_CENTER,
                                      color=color_for(p) if p else RED)),
                 Paragraph(ar(n), S["small"])]
                for t, p, n in gaps]
    gap_data.insert(0, [Paragraph(ar(t), make_style("gh2", size=8, bold=True, color=colors.white, align=TA_RIGHT))
                        for t in ["الوحدة", "التغطية", "الملاحظة"]])
    tg = Table(gap_data, colWidths=[3.5*cm, 2*cm, 11*cm])
    tg.setStyle(TableStyle([
        ("BACKGROUND",   (0,0),  (-1,0),  RED),
        ("TEXTCOLOR",    (0,0),  (-1,0),  colors.white),
        ("GRID",         (0,0),  (-1,-1), 0.5, MGRAY),
        ("ROWBACKGROUNDS",(0,1), (-1,-1), [colors.white, LGRAY]),
        ("TOPPADDING",   (0,0),  (-1,-1), 5),
        ("BOTTOMPADDING",(0,0),  (-1,-1), 5),
    ]))
    story.append(tg)

    # ═══════════════════════════════════════════════════════
    #  ٥. خارطة الطريق
    # ═══════════════════════════════════════════════════════
    story.append(PageBreak())
    story += section_title("٥. خارطة الطريق للوصول إلى 95%+", S["h1"])

    roadmap = [
        ("Q3 2026", BLUE,  [
            "إطلاق Flutter (Android أولاً) مع Check-in / Check-out",
            "Channel Manager: إضافة Agoda + Makkah Gate",
            "AI Pricing: توقع الطلب حسب الموسم + الأحداث",
        ]),
        ("Q4 2026", TEAL,  [
            "POS متكامل مع المخزون والمطبخ",
            "تطبيق iOS (Flutter)",
            "تكامل Unifonic للـ SMS",
        ]),
        ("Q1 2027", GREEN, [
            "Concierge Module (طلبات داخلية)",
            "Revenue Management بالـ AI",
            "SPA / Activity Management",
        ]),
    ]

    for quarter, clr, items in roadmap:
        qdata = [[Paragraph(ar(quarter), make_style("qh", size=10, bold=True, color=colors.white, align=TA_CENTER))]]
        qt = Table(qdata, colWidths=[16*cm])
        qt.setStyle(TableStyle([
            ("BACKGROUND",    (0,0), (-1,-1), clr),
            ("TOPPADDING",    (0,0), (-1,-1), 8),
            ("BOTTOMPADDING", (0,0), (-1,-1), 8),
        ]))
        story.append(qt)
        for item in items:
            story.append(Paragraph(f"    ✓  {ar(item)}", S["body"]))
        story.append(Spacer(1, 0.3*cm))

    # ═══════════════════════════════════════════════════════
    #  ٦. خلاصة
    # ═══════════════════════════════════════════════════════
    story += section_title("٦. الخلاصة والتوصية", S["h1"])

    conc_data = [[
        Paragraph(ar("منصة ضيوف جاهزة للتشغيل الكامل للفنادق السعودية متوسطة الحجم بنسبة " +
                     f"{DHEUOF_SCORE}%، وتتفوق على نزيل ({NUZUL_SCORE}%) في جميع الوحدات الأساسية. "
                     "الفجوة مع Opera (متخصص في الفنادق الكبرى) محصورة في وحدات متقدمة لا تؤثر على التشغيل اليومي. "
                     "أبرز الميزات التنافسية: تطبيق الحجز المباشر + نظام الضرائب ثنائي المسؤولية + ZATCA متكامل + "
                     "متعدد اللغات للموظفين. التوصية: الإطلاق التجاري فوراً مع التطوير التدريجي للوحدات المتبقية."),
                  S["body"])
    ]]
    ct = Table(conc_data, colWidths=[16*cm])
    ct.setStyle(TableStyle([
        ("BACKGROUND",    (0,0), (-1,-1), colors.HexColor("#EFF6FF")),
        ("LEFTPADDING",   (0,0), (-1,-1), 14),
        ("RIGHTPADDING",  (0,0), (-1,-1), 14),
        ("TOPPADDING",    (0,0), (-1,-1), 14),
        ("BOTTOMPADDING", (0,0), (-1,-1), 14),
        ("BOX",           (0,0), (-1,-1), 2, BLUE),
        ("ROUNDEDCORNERS",(0,0), (-1,-1), 8),
    ]))
    story.append(ct)
    story.append(Spacer(1, 0.5*cm))
    story.append(Paragraph(ar("تم إعداد هذا التقرير بتاريخ 8 يونيو 2026  ·  منصة ضيوف  ·  www.dheuof.com"),
                            make_style("ft", size=8, color=DGRAY, align=TA_CENTER)))

    doc.build(story)
    print(f"✅ التقرير جاهز: {out_path}")

# ══════════════════════════════════════════════════════════════
if __name__ == "__main__":
    out = os.path.join(os.path.dirname(__file__), "..", "dheuof_platform_report.pdf")
    build_pdf(os.path.abspath(out))
