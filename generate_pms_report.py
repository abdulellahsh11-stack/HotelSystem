#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""تقرير PDF عربي شامل — مكوّنات PMS منصة ضيوف"""
import arabic_reshaper
from bidi.algorithm import get_display
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import cm
from reportlab.lib import colors
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
    HRFlowable, KeepTogether
)
from reportlab.lib.styles import ParagraphStyle
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.lib.enums import TA_RIGHT, TA_CENTER, TA_LEFT
import os, sys

# ── الخط العربي ──────────────────────────────────────────────────────────────
FONT_PATH = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
FONT_BOLD  = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
if not os.path.exists(FONT_PATH):
    for p in ["/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
              "/usr/share/fonts/truetype/freefont/FreeSans.ttf"]:
        if os.path.exists(p):
            FONT_PATH = p
            break
try:
    pdfmetrics.registerFont(TTFont("Arabic", FONT_PATH))
    pdfmetrics.registerFont(TTFont("ArabicBold", FONT_BOLD if os.path.exists(FONT_BOLD) else FONT_PATH))
except Exception:
    pdfmetrics.registerFont(TTFont("Arabic", FONT_PATH))
    pdfmetrics.registerFont(TTFont("ArabicBold", FONT_PATH))

# ── مساعد النص العربي ────────────────────────────────────────────────────────
def ar(text: str) -> str:
    return get_display(arabic_reshaper.reshape(str(text)))

# ── ألوان المنصة ─────────────────────────────────────────────────────────────
NAVY      = colors.HexColor("#0F2640")
GOLD      = colors.HexColor("#D4A847")
TEAL      = colors.HexColor("#0E7490")
GREEN     = colors.HexColor("#16A34A")
RED       = colors.HexColor("#DC2626")
LIGHT_BG  = colors.HexColor("#F8FAFC")
BORDER    = colors.HexColor("#E2E8F0")
WHITE     = colors.white
PAGE_W, PAGE_H = A4

# ── أنماط النص ───────────────────────────────────────────────────────────────
def style(name, font="Arabic", size=10, align=TA_RIGHT, color=colors.black,
          leading=14, bold=False, space_before=0, space_after=2):
    return ParagraphStyle(
        name=name,
        fontName="ArabicBold" if bold else font,
        fontSize=size,
        alignment=align,
        textColor=color,
        leading=leading,
        spaceAfter=space_after,
        spaceBefore=space_before,
        wordWrap='RTL',
    )

S_TITLE   = style("title",  size=22, bold=True, color=WHITE,     align=TA_CENTER, leading=28)
S_SUB     = style("sub",    size=13, bold=False, color=GOLD,     align=TA_CENTER, leading=18)
S_H1      = style("h1",     size=15, bold=True,  color=NAVY,     leading=20, space_before=12, space_after=4)
S_H2      = style("h2",     size=12, bold=True,  color=TEAL,     leading=16, space_before=8,  space_after=3)
S_BODY    = style("body",   size=10, leading=15, space_after=3)
S_SMALL   = style("small",  size=9,  leading=13, color=colors.HexColor("#64748B"))
S_CENTER  = style("center", size=10, align=TA_CENTER, leading=14)
S_TH      = style("th",     size=10, bold=True,  color=WHITE,    align=TA_CENTER, leading=14)
S_TD      = style("td",     size=9,  leading=13, align=TA_CENTER)
S_TD_R    = style("tdr",    size=9,  leading=13, align=TA_RIGHT)
S_BULLET  = style("bullet", size=10, leading=15, space_after=2)

def p(text, s=S_BODY): return Paragraph(ar(text), s)
def space(h=0.3):       return Spacer(1, h*cm)
def hr(color=BORDER):   return HRFlowable(width="100%", thickness=0.5, color=color, spaceAfter=4, spaceBefore=4)

# ── مكوّن العنوان الرئيسي ─────────────────────────────────────────────────────
def header_block(story):
    header_data = [[Paragraph(ar("منصة ضيوف للضيافة الذكية"), S_TITLE)]]
    t = Table(header_data, colWidths=[PAGE_W - 4*cm])
    t.setStyle(TableStyle([
        ("BACKGROUND",    (0,0), (-1,-1), NAVY),
        ("TOPPADDING",    (0,0), (-1,-1), 18),
        ("BOTTOMPADDING", (0,0), (-1,-1), 18),
        ("LEFTPADDING",   (0,0), (-1,-1), 12),
        ("RIGHTPADDING",  (0,0), (-1,-1), 12),
        ("ROUNDEDCORNERS", [6]),
    ]))
    story.append(t)
    story.append(space(0.3))
    sub_data = [[Paragraph(ar("تقرير شامل — الوحدات البرمجية والمزايا التقنية | يونيو 2026"), S_SUB)]]
    t2 = Table(sub_data, colWidths=[PAGE_W - 4*cm])
    t2.setStyle(TableStyle([
        ("BACKGROUND",    (0,0), (-1,-1), GOLD),
        ("TOPPADDING",    (0,0), (-1,-1), 8),
        ("BOTTOMPADDING", (0,0), (-1,-1), 8),
        ("ROUNDEDCORNERS", [4]),
    ]))
    story.append(t2)
    story.append(space(0.5))

# ── جدول مُنسَّق ──────────────────────────────────────────────────────────────
def make_table(headers: list, rows: list, col_widths: list,
               header_bg=NAVY, row_alt=LIGHT_BG) -> Table:
    # عكس الأعمدة للعربية (RTL)
    headers_r    = list(reversed(headers))
    rows_r       = [list(reversed(row)) for row in rows]
    col_widths_r = list(reversed(col_widths))

    header_cells = [Paragraph(ar(h), S_TH) for h in headers_r]
    table_data   = [header_cells]
    for i, row in enumerate(rows_r):
        cells = []
        for j, cell in enumerate(row):
            s = S_TD if isinstance(cell, (int, float)) or str(cell).replace('%','').replace('.','').lstrip('-').isdigit() else S_TD_R
            cells.append(Paragraph(ar(str(cell)), s))
        table_data.append(cells)

    t = Table(table_data, colWidths=col_widths_r)
    style_cmds = [
        ("BACKGROUND",    (0,0), (-1,0),  header_bg),
        ("TEXTCOLOR",     (0,0), (-1,0),  WHITE),
        ("ALIGN",         (0,0), (-1,-1), "CENTER"),
        ("FONTNAME",      (0,0), (-1,0),  "ArabicBold"),
        ("FONTSIZE",      (0,0), (-1,-1), 9),
        ("TOPPADDING",    (0,0), (-1,-1), 5),
        ("BOTTOMPADDING", (0,0), (-1,-1), 5),
        ("GRID",          (0,0), (-1,-1), 0.4, BORDER),
        ("VALIGN",        (0,0), (-1,-1), "MIDDLE"),
    ]
    for i in range(1, len(table_data)):
        if i % 2 == 0:
            style_cmds.append(("BACKGROUND", (0,i), (-1,i), row_alt))
    t.setStyle(TableStyle(style_cmds))
    return t

# ── بطاقة KPI ────────────────────────────────────────────────────────────────
def kpi_card(label: str, value: str, color=TEAL) -> Table:
    data = [
        [Paragraph(ar(value), ParagraphStyle("kv", fontName="ArabicBold", fontSize=18,
                                              alignment=TA_CENTER, textColor=WHITE, leading=22))],
        [Paragraph(ar(label), ParagraphStyle("kl", fontName="Arabic", fontSize=9,
                                              alignment=TA_CENTER, textColor=GOLD, leading=12))],
    ]
    t = Table(data, colWidths=[4.5*cm], rowHeights=[1.1*cm, 0.8*cm])
    t.setStyle(TableStyle([
        ("BACKGROUND",    (0,0), (-1,-1), color),
        ("TOPPADDING",    (0,0), (-1,-1), 4),
        ("BOTTOMPADDING", (0,0), (-1,-1), 4),
        ("ROUNDEDCORNERS", [5]),
    ]))
    return t

def kpi_row(cards: list) -> Table:
    cards_r = list(reversed(cards))
    t = Table([cards_r], colWidths=[4.5*cm]*len(cards_r),
              hAlign="RIGHT", spaceBefore=4)
    t.setStyle(TableStyle([
        ("LEFTPADDING",  (0,0), (-1,-1), 3),
        ("RIGHTPADDING", (0,0), (-1,-1), 3),
        ("VALIGN",       (0,0), (-1,-1), "TOP"),
    ]))
    return t

# ═══════════════════════════════════════════════════════════════════════════
#  البيانات
# ═══════════════════════════════════════════════════════════════════════════

MODULES = [
    ["نظام الاشتراكات والمصادقة", "مكتمل ✅", "OTP + JWT + تجربة 60 يوم + تجديد اشتراك"],
    ["إدارة الحجوزات M17",        "مكتمل ✅", "إنشاء / تعديل / إلغاء + تقويم + إحصاء"],
    ["الاستقبال والوردية M02",    "مكتمل ✅", "تسجيل دخول/خروج + وردية + توافر الغرف"],
    ["إدارة الضيوف M10",          "مكتمل ✅", "ملفات ضيوف + ولاء + حملات تسويقية"],
    ["المحاسبة والفواتير M06",    "مكتمل ✅", "فواتير + إيرادات شهرية + مديونيات"],
    ["نقطة البيع POS M07",        "مكتمل ✅", "مبيعات + أصناف + إحصاءات"],
    ["التدبير المنزلي M07",       "مكتمل ✅", "مهام + حالة غرف + مفقودات"],
    ["الصيانة M08",               "مكتمل ✅", "أوامر عمل + أصول"],
    ["المستودعات M13",            "مكتمل ✅", "مخزون + موردون + أوامر شراء"],
    ["الموارد البشرية M06",       "مكتمل ✅", "موظفون + حضور + رواتب"],
    ["مؤشرات الأداء KPI M11",     "مكتمل ✅", "RevPAR + ADR + إشغال"],
    ["التحليلات M_Analytics",     "مكتمل ✅", "إيرادات + إشغال + خريطة حرارية"],
    ["الجولات السياحية M14",      "مكتمل ✅", "جولات + حجوزات + وجهات"],
    ["القنوات OTA Channels",      "مكتمل ✅", "ربط OTA + مزامنة + webhooks"],
    ["Open API",                  "مكتمل ✅", "API خارجي + مفاتيح + rate limit"],
    ["ZATCA فواتير إلكترونية",    "جديد 🆕",  "TLV QR + إصدار + تحقق (عام)"],
    ["Night Audit إغلاق اليوم",   "جديد 🆕",  "إعدادات + تلقائي + أجهزة دفع"],
    ["تقييمات الحجوزات",          "جديد 🆕",  "تقييم + رد إدارة + ملخص وتحليل"],
]

ZATCA_ENDPOINTS = [
    ["POST", "/api/zatca/invoices/generate",           "إصدار فاتورة ZATCA مع QR"],
    ["GET",  "/api/zatca/invoices",                    "قائمة الفواتير + فلترة"],
    ["GET",  "/api/zatca/invoices/{id}",               "تفاصيل فاتورة"],
    ["GET",  "/api/zatca/invoices/{id}/qr",            "صورة QR Code (PNG)"],
    ["POST", "/api/zatca/verify-qr",                   "تحقق من QR (عام — بدون تسجيل دخول)"],
    ["POST", "/api/zatca/invoices/{id}/credit-note",   "فاتورة دائن (استرداد)"],
]

NIGHT_AUDIT_ENDPOINTS = [
    ["GET",   "/api/night-audit/settings",                   "عرض إعدادات الإغلاق"],
    ["PATCH", "/api/night-audit/settings",                   "تعديل الإعدادات (مدير فقط)"],
    ["POST",  "/api/night-audit/run",                        "تشغيل Night Audit يدوياً"],
    ["GET",   "/api/night-audit/history",                    "سجل الإغلاقات السابقة"],
    ["GET",   "/api/night-audit/{date}/report",              "تقرير يوم محدد"],
    ["GET",   "/api/night-audit/payment-devices",            "أجهزة الدفع + حالتها"],
    ["POST",  "/api/night-audit/payment-devices",            "إضافة جهاز دفع"],
    ["PATCH", "/api/night-audit/payment-devices/{id}/settle","إغلاق جهاز يدوياً"],
]

REVIEWS_ENDPOINTS = [
    ["POST",   "/api/reviews",            "تسجيل تقييم حجز"],
    ["GET",    "/api/reviews",            "قائمة التقييمات + فلترة"],
    ["GET",    "/api/reviews/summary",    "ملخص التقييمات + متوسطات + توزيع"],
    ["GET",    "/api/reviews/{id}",       "تفاصيل تقييم"],
    ["POST",   "/api/reviews/{id}/reply", "رد الإدارة على تقييم"],
    ["DELETE", "/api/reviews/{id}",       "إخفاء تقييم (مدير)"],
]

SECURITY_NOTES = [
    ["تحقق ZATCA",    "مسار عام بدون JWT — يقبل QR من أي جهاز"],
    ["Night Audit",   "تعديل الإعدادات يتطلب دور Manager أو Admin"],
    ["التقييمات",     "مسموح فقط لحجوزات بحالة checked_out"],
    ["أجهزة الدفع",   "الإضافة والإغلاق للمدير فقط"],
    ["مفاتيح ZATCA",  "مخزّنة في .env — لا تُحفظ في قاعدة البيانات أبداً"],
    ["Night Audit لوغ","ممنوع الحذف — عرض فقط"],
]

NEW_TABLES = [
    ["zatca_invoices",        "فواتير ZATCA مع TLV وصورة QR"],
    ["night_audit_settings",  "إعدادات Night Audit لكل منشأة"],
    ["night_audit_log",       "سجل الإغلاقات اليومية"],
    ["payment_devices",       "أجهزة الدفع (POS، مدى، فيزا)"],
    ["booking_reviews",       "تقييمات الحجوزات مع رد الإدارة"],
]

PACKAGES = [
    ["qrcode[pil]",    ">=7.4.2", "توليد QR Images بمعيار ZATCA TLV"],
    ["Pillow",         ">=10.0",  "معالجة الصور (dependency لـ qrcode)"],
    ["APScheduler",    ">=3.10",  "جدولة Night Audit تلقائياً (Cron)"],
    ["arabic-reshaper",">=3.0",   "تصحيح النص العربي في PDF"],
    ["python-bidi",    ">=0.4.2", "اتجاه RTL في تقارير PDF"],
]

# ═══════════════════════════════════════════════════════════════════════════
#  بناء PDF
# ═══════════════════════════════════════════════════════════════════════════

def build_pdf(out: str):
    doc = SimpleDocTemplate(
        out, pagesize=A4,
        rightMargin=2*cm, leftMargin=2*cm,
        topMargin=2*cm, bottomMargin=2*cm,
    )
    story = []

    # ── الغلاف ──
    header_block(story)

    # ── مقدمة ──
    story.append(p("ملخص تنفيذي", S_H1))
    story.append(hr(NAVY))
    intro = (
        "منصة ضيوف هي نظام متكامل لإدارة الفنادق والمنشآت الفندقية "
        "(PMS) مبني بـ Python / FastAPI + PostgreSQL. "
        "يضم المشروع حالياً 18 وحدة برمجية مكتملة، "
        "وتم في هذا التحديث إضافة ثلاث وحدات جديدة حيوية: "
        "فواتير ZATCA الإلكترونية، وإغلاق اليوم (Night Audit)، "
        "وتقييمات الحجوزات — مع 5 جداول قاعدة بيانات جديدة "
        "و21 endpoint API إضافياً."
    )
    story.append(p(intro))
    story.append(space(0.4))

    # ── KPIs ──
    story.append(kpi_row([
        kpi_card("وحدة برمجية", "18",  NAVY),
        kpi_card("جدول جديد",   "5",   TEAL),
        kpi_card("API endpoint", "21+", GREEN),
        kpi_card("معيار ZATCA",  "TLV", colors.HexColor("#7C3AED")),
    ]))
    story.append(space(0.5))

    # ── جدول الوحدات ──
    story.append(p("الوحدات البرمجية الكاملة", S_H1))
    story.append(hr(NAVY))
    mod_table = make_table(
        ["الوحدة", "الحالة", "المحتوى"],
        MODULES,
        [5.5*cm, 2.5*cm, 9.5*cm],
    )
    story.append(mod_table)
    story.append(space(0.5))

    # ── ZATCA ──
    story.append(KeepTogether([
        p("ZATCA — الفاتورة الإلكترونية وQR Code", S_H1),
        hr(NAVY),
        p("يدعم المعيار السعودي الرسمي TLV (Tag-Length-Value) الصادر عن هيئة الزكاة والضريبة والجمارك. "
          "يتم إنشاء QR Code لكل فاتورة قابل للمسح من أي جهاز للتحقق الفوري من صحة الفاتورة دون الحاجة "
          "لتسجيل دخول."),
        space(0.2),
        p("حقول TLV المُشفَّرة في QR:", S_H2),
    ]))

    tlv_data = [
        ["1", "اسم البائع (Seller Name)"],
        ["2", "الرقم الضريبي (VAT Number)"],
        ["3", "تاريخ ووقت الفاتورة (Timestamp)"],
        ["4", "الإجمالي شامل الضريبة (Total with VAT)"],
        ["5", "قيمة الضريبة (VAT Amount)"],
    ]
    story.append(make_table(["Tag", "البيان"], tlv_data, [2.5*cm, 15*cm]))
    story.append(space(0.3))

    story.append(p("نقاط الـ API:", S_H2))
    story.append(make_table(
        ["Method", "المسار", "الوصف"],
        ZATCA_ENDPOINTS,
        [2*cm, 8*cm, 7.5*cm],
    ))
    story.append(space(0.5))

    # ── Night Audit ──
    story.append(KeepTogether([
        p("Night Audit — إغلاق اليوم الفندقي", S_H1),
        hr(NAVY),
        p("يتيح إغلاق اليوم يدوياً أو بجدولة تلقائية عبر APScheduler. "
          "المدير يحدد وقت التشغيل ووقت الدخول/الخروج الافتراضي. "
          "لا يكتمل الإغلاق إذا كانت هناك فواتير غير مسددة (يمكن تجاوزه بـ force=true)."),
        space(0.2),
        p("آلية العمل:", S_H2),
    ]))

    steps = [
        ["1", "التحقق من عدم تكرار الإغلاق لنفس اليوم"],
        ["2", "فحص الفواتير غير المسددة (إذا require_payment_close=true)"],
        ["3", "تحديث حجوزات No-Show تلقائياً"],
        ["4", "احتساب إيرادات وإحصاءات اليوم"],
        ["5", "حفظ سجل الإغلاق في night_audit_log"],
    ]
    story.append(make_table(["الخطوة", "الإجراء"], steps, [2*cm, 15.5*cm]))
    story.append(space(0.3))
    story.append(p("نقاط الـ API:", S_H2))
    story.append(make_table(
        ["Method", "المسار", "الوصف"],
        NIGHT_AUDIT_ENDPOINTS,
        [2*cm, 8.5*cm, 7*cm],
    ))
    story.append(space(0.5))

    # ── Reviews ──
    story.append(KeepTogether([
        p("تقييمات الحجوزات — Booking Reviews", S_H1),
        hr(NAVY),
        p("يمكن تسجيل تقييم لأي حجز في حالة checked_out خلال 30 يوماً من تاريخ الخروج. "
          "يشمل 5 معايير: التقييم العام، النظافة، الخدمة، الموقع، القيمة مقابل السعر. "
          "المدير يستطيع الرد على كل تقييم."),
        space(0.2),
        p("نقاط الـ API:", S_H2),
    ]))
    story.append(make_table(
        ["Method", "المسار", "الوصف"],
        REVIEWS_ENDPOINTS,
        [2*cm, 7.5*cm, 8*cm],
    ))
    story.append(space(0.5))

    # ── جداول قاعدة البيانات ──
    story.append(p("جداول قاعدة البيانات الجديدة", S_H1))
    story.append(hr(NAVY))
    story.append(make_table(
        ["اسم الجدول", "الغرض"],
        NEW_TABLES,
        [6*cm, 11.5*cm],
    ))
    story.append(space(0.3))
    story.append(p("جميع الجداول الجديدة تتضمن: id, created_at, is_deleted — وتُنفَّذ migrations تلقائياً عند تشغيل التطبيق.", S_SMALL))
    story.append(space(0.5))

    # ── اعتبارات الأمان ──
    story.append(p("اعتبارات الأمان", S_H1))
    story.append(hr(NAVY))
    story.append(make_table(
        ["العنصر", "القاعدة المُطبَّقة"],
        SECURITY_NOTES,
        [4*cm, 13.5*cm],
    ))
    story.append(space(0.5))

    # ── الحزم المضافة ──
    story.append(p("الحزم البرمجية المضافة", S_H1))
    story.append(hr(NAVY))
    story.append(make_table(
        ["الحزمة", "الإصدار", "الاستخدام"],
        PACKAGES,
        [4.5*cm, 3*cm, 10*cm],
    ))
    story.append(space(0.5))

    # ── تذييل ──
    story.append(hr(GOLD))
    story.append(p("© 2026 منصة ضيوف للضيافة الذكية — dheuaf.com | info@dheuaf.com | واتساب: +966 56 500 9696",
                   ParagraphStyle("foot", fontName="Arabic", fontSize=8,
                                  alignment=TA_CENTER, textColor=colors.HexColor("#94A3B8"),
                                  leading=12)))

    doc.build(story)
    print(f"✓  PDF: {out}  ({os.path.getsize(out):,} bytes)")


if __name__ == "__main__":
    out_path = os.path.join(os.path.dirname(__file__), "dheuof-pms-report.pdf")
    build_pdf(out_path)
