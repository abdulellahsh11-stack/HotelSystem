#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
generate_erd.py — يولّد ملف PDF يحتوي:
  1. مخطط ERD كامل للنموذج الجديد
  2. جدول مقارنة بين النموذج الحالي والنموذج المقترح
"""

import sys
sys.path.insert(0, '/home/user/HotelSystem')

from reportlab.lib.pagesizes import A3, landscape
from reportlab.lib import colors
from reportlab.lib.units import cm
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
    HRFlowable, PageBreak
)
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER
from reportlab.platypus import Flowable
import os

OUTPUT = os.path.join(os.path.dirname(__file__), "hotel-system-erd.pdf")

# ── Color Palette ──────────────────────────────────────────────────────────────
C_BLUE      = colors.HexColor("#1565C0")
C_LIGHTBLUE = colors.HexColor("#E3F2FD")
C_GREEN     = colors.HexColor("#2E7D32")
C_LIGHTGREEN= colors.HexColor("#E8F5E9")
C_ORANGE    = colors.HexColor("#E65100")
C_LIGHTORANGE=colors.HexColor("#FFF3E0")
C_RED       = colors.HexColor("#C62828")
C_LIGHTRED  = colors.HexColor("#FFEBEE")
C_PURPLE    = colors.HexColor("#6A1B9A")
C_LIGHTPURPLE=colors.HexColor("#F3E5F5")
C_TEAL      = colors.HexColor("#00695C")
C_LIGHTTEAL = colors.HexColor("#E0F2F1")
C_GREY      = colors.HexColor("#37474F")
C_LIGHTGREY = colors.HexColor("#ECEFF1")
C_GOLD      = colors.HexColor("#F57F17")
C_LIGHTGOLD = colors.HexColor("#FFFDE7")
C_HEADER_BG = colors.HexColor("#0D47A1")
C_WHITE     = colors.white
C_BLACK     = colors.black

# ── Custom ERD Box Flowable ─────────────────────────────────────────────────────
class ERDBox(Flowable):
    """رسم مربع جدول ERD مع اسم الجدول وقائمة الحقول."""
    def __init__(self, table_name, fields, header_color=C_BLUE,
                 header_text_color=C_WHITE, box_color=C_LIGHTBLUE,
                 width=155, category="", is_new=False):
        super().__init__()
        self.table_name = table_name
        self.fields = fields  # list of (field_name, field_type, flags)
        self.header_color = header_color
        self.header_text_color = header_text_color
        self.box_color = box_color
        self.width = width
        self.category = category
        self.is_new = is_new
        self.row_h = 13
        self.header_h = 22
        self.height = self.header_h + len(fields) * self.row_h + 6

    def wrap(self, availWidth, availHeight):
        return self.width, self.height

    def draw(self):
        c = self.canv
        w, h = self.width, self.height

        # Shadow
        c.setFillColor(colors.HexColor("#BDBDBD"))
        c.rect(3, -3, w, h, fill=1, stroke=0)

        # Box border
        if self.is_new:
            c.setStrokeColor(colors.HexColor("#FF6F00"))
            c.setLineWidth(2)
        else:
            c.setStrokeColor(self.header_color)
            c.setLineWidth(1)

        # Header
        c.setFillColor(self.header_color)
        c.rect(0, h - self.header_h, w, self.header_h, fill=1, stroke=0)
        c.setFillColor(self.header_text_color)
        c.setFont("Helvetica-Bold", 9)
        c.drawString(6, h - self.header_h + 8, self.table_name)
        if self.category:
            c.setFont("Helvetica", 6)
            c.setFillColor(colors.HexColor("#B3E5FC"))
            c.drawRightString(w - 4, h - self.header_h + 8, self.category)
        if self.is_new:
            c.setFont("Helvetica-Bold", 6)
            c.setFillColor(colors.HexColor("#FFE082"))
            c.drawRightString(w - 4, h - 8, "★ NEW")

        # Body
        c.setFillColor(self.box_color)
        c.rect(0, 0, w, h - self.header_h, fill=1, stroke=0)

        # Fields
        y = h - self.header_h - self.row_h
        for i, (fname, ftype, flags) in enumerate(self.fields):
            row_bg = colors.HexColor("#FAFAFA") if i % 2 == 0 else self.box_color
            c.setFillColor(row_bg)
            c.rect(0, y, w, self.row_h, fill=1, stroke=0)

            # Flag icons
            x = 4
            if "PK" in flags:
                c.setFillColor(colors.HexColor("#F9A825"))
                c.rect(x, y + 3, 18, 7, fill=1, stroke=0)
                c.setFillColor(C_BLACK)
                c.setFont("Helvetica-Bold", 5)
                c.drawString(x + 2, y + 4, "PK")
                x += 22
            elif "FK" in flags:
                c.setFillColor(colors.HexColor("#CE93D8"))
                c.rect(x, y + 3, 14, 7, fill=1, stroke=0)
                c.setFillColor(C_BLACK)
                c.setFont("Helvetica-Bold", 5)
                c.drawString(x + 1, y + 4, "FK")
                x += 18
            else:
                x += 2

            # Field name
            c.setFillColor(C_GREY)
            c.setFont("Helvetica", 7)
            fname_short = fname[:22] if len(fname) > 22 else fname
            c.drawString(x, y + 4, fname_short)

            # Field type
            c.setFont("Helvetica", 6)
            c.setFillColor(colors.HexColor("#78909C"))
            c.drawRightString(w - 4, y + 4, ftype)

            y -= self.row_h

        # Border
        c.setStrokeColor(self.header_color if not self.is_new else colors.HexColor("#FF6F00"))
        c.setLineWidth(1.5 if self.is_new else 0.8)
        c.rect(0, 0, w, h, fill=0, stroke=1)


def build_pdf():
    doc = SimpleDocTemplate(
        OUTPUT,
        pagesize=landscape(A3),
        rightMargin=1.5*cm, leftMargin=1.5*cm,
        topMargin=1.5*cm, bottomMargin=1.5*cm,
        title="Hotel System — ERD & Database Comparison",
        author="ضيوف Platform"
    )

    styles = getSampleStyleSheet()

    # Custom styles
    title_style = ParagraphStyle(
        "ArabicTitle",
        parent=styles["Title"],
        fontSize=20, leading=26,
        textColor=C_HEADER_BG,
        spaceAfter=8, alignment=TA_CENTER
    )
    subtitle_style = ParagraphStyle(
        "Subtitle",
        parent=styles["Normal"],
        fontSize=11, leading=14,
        textColor=C_GREY,
        spaceAfter=6, alignment=TA_CENTER
    )
    section_style = ParagraphStyle(
        "SectionHeader",
        parent=styles["Heading1"],
        fontSize=14, leading=18,
        textColor=C_WHITE, backColor=C_HEADER_BG,
        spaceAfter=4, spaceBefore=12,
        leftIndent=8, rightIndent=8
    )
    body_style = ParagraphStyle(
        "Body",
        parent=styles["Normal"],
        fontSize=9, leading=13,
        textColor=C_GREY
    )

    story = []

    # ── PAGE 1: Cover & Summary ────────────────────────────────────────────────
    story.append(Spacer(1, 1*cm))
    story.append(Paragraph(
        "منصة ضيوف المتكاملة — نموذج قاعدة البيانات",
        title_style
    ))
    story.append(Paragraph(
        "Hotel &amp; Serviced Apartments Management System — ERD &amp; Database Design",
        subtitle_style
    ))
    story.append(Paragraph(
        "مقارنة شاملة بين النموذج الحالي والنموذج المقترح المحسَّن • PostgreSQL 15+ • Multi-tenant SaaS",
        subtitle_style
    ))
    story.append(HRFlowable(width="100%", thickness=2, color=C_HEADER_BG, spaceAfter=12))

    # Stats summary table
    stats_data = [
        ["المؤشر", "النموذج الحالي", "النموذج الجديد", "الفرق"],
        ["عدد الجداول الكلي", "39", "38 + كيانات موحدة", "أكثر تنظيمًا"],
        ["نوع المفتاح الأساسي للعملاء", "VARCHAR(50)", "SERIAL + UUID", "أكثر أمانًا"],
        ["نوع مفتاح الحجوزات", "VARCHAR(50)", "SERIAL + booking_ref", "أكثر أمانًا"],
        ["الفواتير — بنود الفاتورة", "JSONB (line_items)", "جدول invoice_items منفصل", "3NF محقق"],
        ["الضيوف المصاحبون", "JSONB (companions)", "جدول booking_guests منفصل", "3NF محقق"],
        ["نقطة البيع POS", "جدول مسطح واحد", "4 جداول منظمة", "قابل للتوسع"],
        ["إدارة المستخدمين", "جلسات في الذاكرة", "جدول users + role_permissions", "صلاحيات رسمية"],
        ["سجل التدقيق", "محدود", "audit_log شامل + trigger", "أمان كامل"],
        ["تتبع المسوقين", "✓ موجود", "✓ موجود (محسَّن)", "—"],
        ["iCal / واتساب / Chatbot", "✓ موجود (4 جداول)", "غير مُنمذج في النموذج الجديد", "يجب الإبقاء"],
        ["HR / الرواتب", "✓ موجود (3 جداول)", "غير مُنمذج في النموذج الجديد", "يجب الإبقاء"],
        ["مؤشرات KPI اليومية", "daily_kpis (جاهز)", "مُحسَّب لحظيًا", "يُفضَّل الجمع"],
        ["إدارة الأصول Assets", "✓ موجود", "غير مُنمذج", "يجب الإبقاء"],
        ["الجولات السياحية", "✓ موجود (5 جداول)", "غير مُنمذج", "يجب الإبقاء"],
    ]

    stat_table = Table(stats_data, colWidths=[5.5*cm, 4.5*cm, 5.5*cm, 4*cm])
    stat_table.setStyle(TableStyle([
        ("BACKGROUND", (0,0), (-1,0), C_HEADER_BG),
        ("TEXTCOLOR",  (0,0), (-1,0), C_WHITE),
        ("FONTNAME",   (0,0), (-1,0), "Helvetica-Bold"),
        ("FONTSIZE",   (0,0), (-1,0), 9),
        ("ALIGN",      (0,0), (-1,-1), "CENTER"),
        ("VALIGN",     (0,0), (-1,-1), "MIDDLE"),
        ("ROWBACKGROUNDS", (0,1), (-1,-1), [C_LIGHTBLUE, C_WHITE]),
        ("FONTSIZE",   (0,1), (-1,-1), 8),
        ("GRID",       (0,0), (-1,-1), 0.5, colors.HexColor("#90CAF9")),
        ("TOPPADDING", (0,0), (-1,-1), 5),
        ("BOTTOMPADDING", (0,0), (-1,-1), 5),
        # Highlight differences
        ("BACKGROUND", (0,5), (-1,5), C_LIGHTORANGE),
        ("BACKGROUND", (0,6), (-1,6), C_LIGHTORANGE),
        ("BACKGROUND", (0,7), (-1,7), C_LIGHTORANGE),
        ("BACKGROUND", (0,8), (-1,8), C_LIGHTRED),
    ]))
    story.append(stat_table)
    story.append(Spacer(1, 0.5*cm))

    # Legend
    legend_data = [
        ["أنواع العلاقات:", "1:M — واحد إلى متعدد", "M:M — متعدد إلى متعدد (يحتاج جدول وسيط)", "1:1 — واحد إلى واحد"],
        ["رموز الحقول:", "PK = مفتاح أساسي (ذهبي)", "FK = مفتاح أجنبي (بنفسجي)", "★ NEW = جدول جديد في النموذج المقترح"],
    ]
    leg_table = Table(legend_data, colWidths=[3*cm, 5*cm, 7*cm, 5*cm])
    leg_table.setStyle(TableStyle([
        ("BACKGROUND", (0,0), (0,-1), C_LIGHTGOLD),
        ("FONTNAME",   (0,0), (0,-1), "Helvetica-Bold"),
        ("FONTSIZE",   (0,0), (-1,-1), 7.5),
        ("GRID",       (0,0), (-1,-1), 0.3, C_LIGHTGREY),
        ("VALIGN",     (0,0), (-1,-1), "MIDDLE"),
        ("TOPPADDING", (0,0), (-1,-1), 3),
    ]))
    story.append(leg_table)
    story.append(PageBreak())

    # ── PAGE 2: Differences Detail ─────────────────────────────────────────────
    story.append(Paragraph("  الفروقات التفصيلية بين النموذجين", section_style))
    story.append(Spacer(1, 0.3*cm))

    diff_title_style = ParagraphStyle("DiffTitle", parent=body_style,
                                       fontSize=10, fontName="Helvetica-Bold",
                                       textColor=C_BLUE)
    story.append(Paragraph("أولًا: تحسينات هيكلية في النموذج الجديد", diff_title_style))
    story.append(Spacer(1, 0.2*cm))

    improvements = [
        ["#", "المشكلة في النموذج الحالي", "الحل في النموذج الجديد", "التأثير"],
        ["1", "clients.id = VARCHAR(50)\nيُولَّد يدويًا أو عشوائيًا",
             "clients.id = SERIAL\nclients.public_id = UUID",
             "أمان أعلى + أداء JOIN أفضل\n(أعداد صحيحة أسرع من VARCHAR)"],
        ["2", "bookings.id = VARCHAR(50)\nمثل 'BK-20240101-XXXX'",
             "bookings.id = SERIAL\nbooking_ref = VARCHAR(30) UNIQUE",
             "فصل المفتاح الداخلي عن رقم الحجز\nالعلني — مرونة أكبر"],
        ["3", "invoices.line_items = JSONB\nقائمة البنود مخزنة كـ JSON",
             "جدول invoice_items منفصل\nمع FK لكل بند",
             "تحقق 3NF — إمكانية الاستعلام\nوالتقرير عن كل بند منفردًا"],
        ["4", "bookings.companions = JSONB\nالمرافقون مخزنون كـ JSON",
             "جدول booking_guests\nعلاقة M:M صريحة",
             "بحث الضيف بالاسم/الهوية\nعبر جميع حجوزاته"],
        ["5", "pos_transactions = جدول مسطح\nbez تصنيف أو منتجات",
             "4 جداول: pos_categories,\npos_items, pos_orders, pos_order_items",
             "تقارير POS تفصيلية\nربط بالمخزن تلقائيًا"],
        ["6", "لا يوجد جدول users رسمي\nجلسات في الذاكرة فقط",
             "جدول users + role_permissions\nصلاحيات مبنية على الأدوار",
             "RBAC كامل — تتبع كل عملية\nبمستخدمها الفعلي"],
        ["7", "لا يوجد audit_log شامل\nتسجيل عمليات محدود",
             "جدول audit_log مع trigger\nيمنع التعديل والحذف",
             "مساءلة كاملة — مطلوب\nقانونيًا في كثير من الدول"],
        ["8", "room_type حقل VARCHAR\nبدون FK لجدول أنواع الغرف",
             "room_type_id FK إلى\nجدول room_types",
             "تسعير موحد — تقارير\nبحسب نوع الغرفة"],
        ["9", "guests بدون blacklisted\nأو vip_level مُنمذج",
             "guests + vip_level\n+ blacklisted + UNIQUE constraint",
             "منع تسجيل الضيوف المحظورين\nتلقائيًا في الكود"],
        ["10", "لا يوجد جدول amenities\nمرافق الغرف في JSONB",
             "amenities + room_amenities\nعلاقة M:M صريحة",
             "فلترة الغرف بالمرافق\nتقارير مقارنة الغرف"],
    ]

    imp_table = Table(improvements, colWidths=[0.7*cm, 6.5*cm, 6.5*cm, 6.5*cm])
    imp_table.setStyle(TableStyle([
        ("BACKGROUND",    (0,0), (-1,0), C_GREEN),
        ("TEXTCOLOR",     (0,0), (-1,0), C_WHITE),
        ("FONTNAME",      (0,0), (-1,0), "Helvetica-Bold"),
        ("FONTSIZE",      (0,0), (-1,0), 8.5),
        ("ALIGN",         (0,0), (0,-1), "CENTER"),
        ("VALIGN",        (0,0), (-1,-1), "MIDDLE"),
        ("ROWBACKGROUNDS",(0,1), (-1,-1), [C_LIGHTGREEN, C_WHITE]),
        ("FONTSIZE",      (0,1), (-1,-1), 7.5),
        ("GRID",          (0,0), (-1,-1), 0.4, colors.HexColor("#A5D6A7")),
        ("TOPPADDING",    (0,0), (-1,-1), 5),
        ("BOTTOMPADDING", (0,0), (-1,-1), 5),
    ]))
    story.append(imp_table)
    story.append(Spacer(1, 0.5*cm))

    story.append(Paragraph("ثانيًا: جداول موجودة في النموذج الحالي يجب الإبقاء عليها", diff_title_style))
    story.append(Spacer(1, 0.2*cm))

    keep_data = [
        ["الجدول", "الوحدة", "السبب — لماذا يجب الإبقاء عليه"],
        ["ical_sources + ical_conflicts", "M02 — الاستقبال",
         "تزامن iCal مع Airbnb وBooking.com — ميزة تنافسية مهمة لا توجد في النموذج الجديد"],
        ["whatsapp_log", "WhatsApp Automation",
         "سجل رسائل واتساب — ضروري للدعم وتتبع التواصل مع الضيوف"],
        ["chatbot_conversations + escalation_log", "AI Chatbot",
         "نظام الشات بوت ومحادثات الذكاء الاصطناعي — ميزة متقدمة غير موجودة في النموذج الجديد"],
        ["key_events", "الأمن والمداخل",
         "تتبع أحداث المفاتيح الإلكترونية — أمن المبنى وكشف الأنماط المشبوهة"],
        ["employees + attendance + payroll", "M06 — الموارد البشرية",
         "نظام HR كامل مع الحضور والرواتب والتأمينات — موجود ومُطبَّق"],
        ["front_desk_shifts", "M02 — الاستقبال",
         "إدارة وردية الاستقبال والصندوق — محاسبة مالية يومية"],
        ["check_in_log + check_out_log", "M02 — الاستقبال",
         "سجل تدقيق مفصل للدخول والخروج — يكمل جدول room_actions"],
        ["housekeeping_checklist + lost_and_found", "M07 — Housekeeping",
         "قائمة تحقق التنظيف والمفقودات — عمليات يومية أساسية"],
        ["assets + maintenance_orders", "M08 — الصيانة",
         "إدارة الأصول وتكاليف الصيانة — متابعة دورة حياة المعدات"],
        ["crm_contacts + loyalty_transactions + campaigns", "M10 — CRM",
         "نظام CRM والولاء والحملات التسويقية — قيمة عمر العميل"],
        ["daily_kpis", "M11 — KPI Analytics",
         "مؤشرات KPI مُخزَّنة يوميًا للأداء التاريخي والتقارير السريعة"],
        ["tour_catalog + tour_bookings + tourist_destinations", "M14/15 — السياحة",
         "نظام الجولات السياحية والوجهات — ميزة متخصصة للفنادق السياحية"],
        ["notifications", "إشعارات",
         "نظام الإشعارات الداخلية — ضروري لتنبيه الموظفين"],
        ["sequences", "ترقيم الفواتير",
         "تسلسل أرقام الفواتير بدون ثغرات — مطلوب محاسبيًا وقانونيًا"],
        ["license_keys", "الترخيص",
         "مفاتيح الترخيص للمنشآت — نموذج تفعيل بديل للاشتراكات"],
        ["revoked_sessions + guest_sessions", "الأمن",
         "إبطال الجلسات وعزل جلسات الضيوف — تطبَّق في db/security.py"],
        ["rate_plans", "التسعير",
         "خطط الأسعار الديناميكية بتواريخ صلاحية — موسمي وأسبوعي"],
    ]

    keep_table = Table(keep_data, colWidths=[5*cm, 3.5*cm, 11.5*cm])
    keep_table.setStyle(TableStyle([
        ("BACKGROUND",    (0,0), (-1,0), C_ORANGE),
        ("TEXTCOLOR",     (0,0), (-1,0), C_WHITE),
        ("FONTNAME",      (0,0), (-1,0), "Helvetica-Bold"),
        ("FONTSIZE",      (0,0), (-1,0), 8.5),
        ("VALIGN",        (0,0), (-1,-1), "MIDDLE"),
        ("ROWBACKGROUNDS",(0,1), (-1,-1), [C_LIGHTORANGE, C_WHITE]),
        ("FONTSIZE",      (0,1), (-1,-1), 7.5),
        ("GRID",          (0,0), (-1,-1), 0.4, colors.HexColor("#FFCC80")),
        ("TOPPADDING",    (0,0), (-1,-1), 4),
        ("BOTTOMPADDING", (0,0), (-1,-1), 4),
    ]))
    story.append(keep_table)
    story.append(PageBreak())

    # ── PAGE 3: ERD Group 1 — Core Tables ─────────────────────────────────────
    story.append(Paragraph("  مخطط ERD — المجموعة الأولى: الجداول الأساسية", section_style))
    story.append(Spacer(1, 0.3*cm))

    # ERD boxes for core tables
    core_boxes = [
        # clients
        ERDBox("clients", [
            ("id", "SERIAL", "PK"),
            ("public_id", "UUID", ""),
            ("name", "VARCHAR(200)", "NOT NULL"),
            ("facility_type", "VARCHAR(50)", "NOT NULL"),
            ("email", "VARCHAR(255)", "UNIQUE"),
            ("phone", "VARCHAR(20)", ""),
            ("status", "VARCHAR(20)", "DEFAULT active"),
            ("plan_id", "INTEGER", "FK"),
            ("enabled_modules", "JSONB", ""),
            ("created_at", "TIMESTAMPTZ", ""),
        ], C_BLUE, C_WHITE, C_LIGHTBLUE, category="المنشآت"),

        # subscription_plans
        ERDBox("subscription_plans", [
            ("id", "SERIAL", "PK"),
            ("name", "VARCHAR(100)", "NOT NULL"),
            ("price_monthly", "NUMERIC(10,2)", ""),
            ("max_rooms", "INTEGER", ""),
            ("max_users", "INTEGER", ""),
            ("allowed_modules", "JSONB", ""),
            ("is_active", "BOOLEAN", "DEFAULT TRUE"),
        ], C_TEAL, C_WHITE, C_LIGHTTEAL, category="الاشتراكات"),

        # subscriptions
        ERDBox("subscriptions", [
            ("id", "SERIAL", "PK"),
            ("client_id", "INTEGER", "FK"),
            ("plan_id", "INTEGER", "FK"),
            ("status", "VARCHAR(20)", ""),
            ("start_date", "DATE", "NOT NULL"),
            ("end_date", "DATE", "NOT NULL"),
            ("amount_paid", "NUMERIC(10,2)", ""),
        ], C_TEAL, C_WHITE, C_LIGHTTEAL, category="الاشتراكات"),

        # users
        ERDBox("users", [
            ("id", "SERIAL", "PK"),
            ("client_id", "INTEGER", "FK"),
            ("email", "VARCHAR(255)", "UNIQUE"),
            ("full_name", "VARCHAR(200)", "NOT NULL"),
            ("password_hash", "VARCHAR(255)", "argon2id"),
            ("role", "VARCHAR(50)", ""),
            ("is_active", "BOOLEAN", "DEFAULT TRUE"),
            ("last_login_at", "TIMESTAMPTZ", ""),
            ("created_by", "INTEGER", "FK"),
        ], C_PURPLE, C_WHITE, C_LIGHTPURPLE, category="المستخدمون", is_new=True),

        # role_permissions
        ERDBox("role_permissions", [
            ("id", "SERIAL", "PK"),
            ("role", "VARCHAR(50)", "NOT NULL"),
            ("resource", "VARCHAR(100)", "NOT NULL"),
            ("can_create", "BOOLEAN", ""),
            ("can_read", "BOOLEAN", ""),
            ("can_update", "BOOLEAN", ""),
            ("can_delete", "BOOLEAN", ""),
            ("can_approve", "BOOLEAN", ""),
        ], C_PURPLE, C_WHITE, C_LIGHTPURPLE, category="الصلاحيات", is_new=True),

        # branches
        ERDBox("branches", [
            ("id", "SERIAL", "PK"),
            ("client_id", "INTEGER", "FK"),
            ("name", "VARCHAR(150)", "NOT NULL"),
            ("address", "TEXT", ""),
            ("is_active", "BOOLEAN", "DEFAULT TRUE"),
        ], C_GREY, C_WHITE, C_LIGHTGREY, category="الفروع", is_new=True),
    ]

    # Layout: 4 columns
    col_w = 165
    rows_data = []
    row = []
    for i, box in enumerate(core_boxes):
        row.append(box)
        if len(row) == 4 or i == len(core_boxes)-1:
            while len(row) < 4:
                row.append(Spacer(1, 1))
            rows_data.append(row)
            row = []

    for row_items in rows_data:
        t = Table([row_items], colWidths=[col_w, col_w, col_w, col_w])
        t.setStyle(TableStyle([
            ("VALIGN", (0,0), (-1,-1), "TOP"),
            ("LEFTPADDING", (0,0), (-1,-1), 6),
            ("RIGHTPADDING", (0,0), (-1,-1), 6),
            ("TOPPADDING", (0,0), (-1,-1), 4),
            ("BOTTOMPADDING", (0,0), (-1,-1), 4),
        ]))
        story.append(t)
        story.append(Spacer(1, 0.2*cm))

    # Relationships for core group
    story.append(Spacer(1, 0.2*cm))
    rel_data = [
        ["العلاقات بين الجداول الأساسية", "", "", ""],
        ["subscription_plans 1 ──── * subscriptions", "subscriptions * ──── 1 clients",
         "clients 1 ──── * users", "clients 1 ──── * branches"],
        ["role_permissions ─── role_name ──→ users", "clients 1 ──── 1 sequences",
         "clients.plan_id ──FK──→ subscription_plans", "users.client_id ──FK──→ clients"],
    ]
    rt = Table(rel_data, colWidths=[6*cm, 6*cm, 6*cm, 6*cm])
    rt.setStyle(TableStyle([
        ("BACKGROUND",    (0,0), (-1,0), C_LIGHTBLUE),
        ("FONTNAME",      (0,0), (-1,0), "Helvetica-Bold"),
        ("FONTSIZE",      (0,0), (-1,-1), 7),
        ("GRID",          (0,0), (-1,-1), 0.3, colors.HexColor("#90CAF9")),
        ("TOPPADDING",    (0,0), (-1,-1), 4),
        ("SPAN",          (0,0), (-1,0)),
        ("ALIGN",         (0,0), (-1,0), "CENTER"),
    ]))
    story.append(rt)
    story.append(PageBreak())

    # ── PAGE 4: ERD Group 2 — Room & Booking Tables ────────────────────────────
    story.append(Paragraph("  مخطط ERD — المجموعة الثانية: الغرف والحجوزات", section_style))
    story.append(Spacer(1, 0.3*cm))

    booking_boxes = [
        ERDBox("room_types", [
            ("id", "SERIAL", "PK"),
            ("client_id", "INTEGER", "FK"),
            ("code", "VARCHAR(20)", "UNIQUE"),
            ("name_ar", "VARCHAR(100)", "NOT NULL"),
            ("base_price_night", "NUMERIC(10,2)", ""),
            ("base_price_month", "NUMERIC(10,2)", ""),
            ("max_occupancy", "SMALLINT", ""),
        ], C_GREEN, C_WHITE, C_LIGHTGREEN, category="أنواع الغرف"),

        ERDBox("rooms", [
            ("id", "SERIAL", "PK"),
            ("client_id", "INTEGER", "FK"),
            ("room_number", "VARCHAR(20)", "UNIQUE per client"),
            ("room_type_id", "INTEGER", "FK"),
            ("status", "VARCHAR(30)", ""),
            ("current_booking_id", "INTEGER", "FK"),
            ("current_guest", "VARCHAR(200)", "cache"),
            ("checkout_due", "DATE", "cache"),
            ("last_action_by", "VARCHAR(200)", ""),
            ("last_action_at", "TIMESTAMPTZ", ""),
        ], C_GREEN, C_WHITE, C_LIGHTGREEN, category="الغرف"),

        ERDBox("amenities", [
            ("id", "SERIAL", "PK"),
            ("client_id", "INTEGER", "FK"),
            ("name_ar", "VARCHAR(100)", "NOT NULL"),
            ("icon", "VARCHAR(50)", ""),
        ], C_GREEN, C_WHITE, C_LIGHTGREEN, category="المرافق", is_new=True),

        ERDBox("room_amenities", [
            ("room_id", "INTEGER", "PK+FK"),
            ("amenity_id", "INTEGER", "PK+FK"),
        ], C_GREEN, C_WHITE, C_LIGHTGREEN, category="M:M وسيط", is_new=True),

        ERDBox("guests", [
            ("id", "SERIAL", "PK"),
            ("client_id", "INTEGER", "FK"),
            ("full_name", "VARCHAR(200)", "NOT NULL"),
            ("id_type", "VARCHAR(30)", ""),
            ("id_number", "VARCHAR(50)", "UNIQUE"),
            ("phone", "VARCHAR(20)", ""),
            ("vip_level", "VARCHAR(20)", "regular/silver/gold"),
            ("blacklisted", "BOOLEAN", "DEFAULT FALSE"),
            ("total_stays", "INTEGER", "computed"),
        ], C_ORANGE, C_WHITE, C_LIGHTORANGE, category="الضيوف"),

        ERDBox("guest_documents", [
            ("id", "SERIAL", "PK"),
            ("guest_id", "INTEGER", "FK"),
            ("client_id", "INTEGER", "FK"),
            ("doc_type", "VARCHAR(30)", ""),
            ("file_url", "TEXT", "NOT NULL"),
            ("uploaded_by", "INTEGER", "FK"),
        ], C_ORANGE, C_WHITE, C_LIGHTORANGE, category="وثائق الضيوف", is_new=True),

        ERDBox("bookings", [
            ("id", "SERIAL", "PK"),
            ("client_id", "INTEGER", "FK"),
            ("booking_ref", "VARCHAR(30)", "UNIQUE"),
            ("room_id", "INTEGER", "FK"),
            ("primary_guest_id", "INTEGER", "FK"),
            ("check_in_date", "DATE", "NOT NULL"),
            ("check_out_date", "DATE", "NOT NULL"),
            ("actual_check_in", "TIMESTAMPTZ", ""),
            ("actual_check_out", "TIMESTAMPTZ", ""),
            ("booking_type", "VARCHAR(20)", "nightly/monthly"),
            ("status", "VARCHAR(30)", ""),
            ("rate_per_night", "NUMERIC(10,2)", ""),
            ("total_nights", "SMALLINT", ""),
            ("net_amount", "NUMERIC(12,2)", ""),
            ("created_by", "INTEGER", "FK"),
        ], C_BLUE, C_WHITE, C_LIGHTBLUE, category="الحجوزات"),

        ERDBox("booking_guests", [
            ("booking_id", "INTEGER", "PK+FK"),
            ("guest_id", "INTEGER", "PK+FK"),
            ("is_primary", "BOOLEAN", ""),
            ("added_by", "INTEGER", "FK"),
        ], C_BLUE, C_WHITE, C_LIGHTBLUE, category="M:M وسيط", is_new=True),

        ERDBox("booking_services", [
            ("id", "SERIAL", "PK"),
            ("booking_id", "INTEGER", "FK"),
            ("service_name", "VARCHAR(200)", "NOT NULL"),
            ("quantity", "NUMERIC(8,2)", ""),
            ("unit_price", "NUMERIC(10,2)", ""),
            ("total_price", "NUMERIC(12,2)", ""),
        ], C_BLUE, C_WHITE, C_LIGHTBLUE, category="خدمات إضافية", is_new=True),

        ERDBox("room_actions", [
            ("id", "SERIAL", "PK"),
            ("client_id", "INTEGER", "FK"),
            ("room_id", "INTEGER", "FK"),
            ("action_type", "VARCHAR(50)", ""),
            ("old_status", "VARCHAR(30)", ""),
            ("new_status", "VARCHAR(30)", ""),
            ("staff_name", "VARCHAR(200)", "NOT NULL"),
            ("created_at", "TIMESTAMPTZ", ""),
        ], C_RED, C_WHITE, C_LIGHTRED, category="سجل تصرفات"),
    ]

    rows_data = []
    row = []
    for i, box in enumerate(booking_boxes):
        row.append(box)
        if len(row) == 4 or i == len(booking_boxes)-1:
            while len(row) < 4:
                row.append(Spacer(1, 1))
            rows_data.append(row)
            row = []

    for row_items in rows_data:
        t = Table([row_items], colWidths=[col_w, col_w, col_w, col_w])
        t.setStyle(TableStyle([
            ("VALIGN", (0,0), (-1,-1), "TOP"),
            ("LEFTPADDING", (0,0), (-1,-1), 6),
            ("RIGHTPADDING", (0,0), (-1,-1), 6),
            ("TOPPADDING", (0,0), (-1,-1), 4),
        ]))
        story.append(t)
        story.append(Spacer(1, 0.2*cm))

    rel2_data = [
        ["العلاقات — الغرف والحجوزات", "", "", ""],
        ["room_types 1 ──── * rooms", "rooms * ──── * amenities\n(via room_amenities)", "rooms 1 ──── * bookings", "guests * ──── * bookings\n(via booking_guests)"],
        ["bookings 1 ──── * booking_services", "rooms 1 ──── * room_actions", "guests 1 ──── * guest_documents", "rooms.room_type_id ──FK──→ room_types"],
    ]
    rt2 = Table(rel2_data, colWidths=[6*cm, 6*cm, 6*cm, 6*cm])
    rt2.setStyle(TableStyle([
        ("BACKGROUND",    (0,0), (-1,0), C_LIGHTGREEN),
        ("FONTNAME",      (0,0), (-1,0), "Helvetica-Bold"),
        ("FONTSIZE",      (0,0), (-1,-1), 7),
        ("GRID",          (0,0), (-1,-1), 0.3, colors.HexColor("#A5D6A7")),
        ("TOPPADDING",    (0,0), (-1,-1), 4),
        ("SPAN",          (0,0), (-1,0)),
        ("ALIGN",         (0,0), (-1,0), "CENTER"),
    ]))
    story.append(rt2)
    story.append(PageBreak())

    # ── PAGE 5: ERD Group 3 — Finance Tables ──────────────────────────────────
    story.append(Paragraph("  مخطط ERD — المجموعة الثالثة: المالية والفواتير", section_style))
    story.append(Spacer(1, 0.3*cm))

    finance_boxes = [
        ERDBox("invoices", [
            ("id", "SERIAL", "PK"),
            ("client_id", "INTEGER", "FK"),
            ("invoice_number", "VARCHAR(30)", "UNIQUE"),
            ("booking_id", "INTEGER", "FK"),
            ("guest_id", "INTEGER", "FK"),
            ("invoice_date", "DATE", "NOT NULL"),
            ("subtotal", "NUMERIC(12,2)", ""),
            ("discount_amount", "NUMERIC(10,2)", "DEFAULT 0"),
            ("tax_rate", "NUMERIC(5,2)", ""),
            ("tax_amount", "NUMERIC(10,2)", ""),
            ("total_amount", "NUMERIC(12,2)", ""),
            ("amount_paid", "NUMERIC(12,2)", ""),
            ("balance_due", "NUMERIC(12,2)", "computed"),
            ("status", "VARCHAR(20)", "pending/paid"),
            ("issued_by", "INTEGER", "FK"),
        ], C_GOLD, C_WHITE, C_LIGHTGOLD, category="الفواتير"),

        ERDBox("invoice_items", [
            ("id", "SERIAL", "PK"),
            ("invoice_id", "INTEGER", "FK"),
            ("description", "VARCHAR(500)", "NOT NULL"),
            ("item_type", "VARCHAR(30)", "room/service/pos"),
            ("quantity", "NUMERIC(8,2)", ""),
            ("unit_price", "NUMERIC(10,2)", ""),
            ("discount_pct", "NUMERIC(5,2)", ""),
            ("total_price", "NUMERIC(12,2)", ""),
        ], C_GOLD, C_WHITE, C_LIGHTGOLD, category="بنود الفاتورة", is_new=True),

        ERDBox("payments", [
            ("id", "SERIAL", "PK"),
            ("client_id", "INTEGER", "FK"),
            ("invoice_id", "INTEGER", "FK"),
            ("amount", "NUMERIC(12,2)", "NOT NULL"),
            ("payment_method", "VARCHAR(50)", "cash/card/transfer"),
            ("payment_date", "TIMESTAMPTZ", ""),
            ("reference_number", "VARCHAR(100)", ""),
            ("received_by", "INTEGER", "FK"),
        ], C_GOLD, C_WHITE, C_LIGHTGOLD, category="المدفوعات"),

        ERDBox("pos_categories", [
            ("id", "SERIAL", "PK"),
            ("client_id", "INTEGER", "FK"),
            ("name", "VARCHAR(100)", "NOT NULL"),
            ("sort_order", "SMALLINT", ""),
            ("is_active", "BOOLEAN", ""),
        ], C_TEAL, C_WHITE, C_LIGHTTEAL, category="تصنيفات POS", is_new=True),

        ERDBox("pos_items", [
            ("id", "SERIAL", "PK"),
            ("client_id", "INTEGER", "FK"),
            ("category_id", "INTEGER", "FK"),
            ("name", "VARCHAR(200)", "NOT NULL"),
            ("price", "NUMERIC(10,2)", ""),
            ("tax_rate", "NUMERIC(5,2)", ""),
            ("deduct_inventory", "BOOLEAN", ""),
            ("inventory_item_id", "INTEGER", "FK"),
        ], C_TEAL, C_WHITE, C_LIGHTTEAL, category="منتجات POS", is_new=True),

        ERDBox("pos_orders", [
            ("id", "SERIAL", "PK"),
            ("client_id", "INTEGER", "FK"),
            ("order_number", "VARCHAR(30)", "UNIQUE"),
            ("booking_id", "INTEGER", "FK"),
            ("guest_id", "INTEGER", "FK"),
            ("order_type", "VARCHAR(30)", "dine_in/room_service"),
            ("status", "VARCHAR(20)", ""),
            ("total", "NUMERIC(12,2)", ""),
            ("bill_to_room", "BOOLEAN", ""),
            ("cashier_id", "INTEGER", "FK"),
        ], C_TEAL, C_WHITE, C_LIGHTTEAL, category="طلبات POS", is_new=True),

        ERDBox("pos_order_items", [
            ("id", "SERIAL", "PK"),
            ("order_id", "INTEGER", "FK"),
            ("item_id", "INTEGER", "FK"),
            ("item_name", "VARCHAR(200)", "frozen copy"),
            ("quantity", "NUMERIC(8,2)", ""),
            ("unit_price", "NUMERIC(10,2)", "frozen"),
            ("total_price", "NUMERIC(12,2)", ""),
        ], C_TEAL, C_WHITE, C_LIGHTTEAL, category="بنود POS", is_new=True),
    ]

    rows_data = []
    row = []
    for i, box in enumerate(finance_boxes):
        row.append(box)
        if len(row) == 4 or i == len(finance_boxes)-1:
            while len(row) < 4:
                row.append(Spacer(1, 1))
            rows_data.append(row)
            row = []

    for row_items in rows_data:
        t = Table([row_items], colWidths=[col_w, col_w, col_w, col_w])
        t.setStyle(TableStyle([
            ("VALIGN", (0,0), (-1,-1), "TOP"),
            ("LEFTPADDING", (0,0), (-1,-1), 6),
            ("RIGHTPADDING", (0,0), (-1,-1), 6),
            ("TOPPADDING", (0,0), (-1,-1), 4),
        ]))
        story.append(t)
        story.append(Spacer(1, 0.2*cm))

    rel3_data = [
        ["العلاقات — المالية وPOS", "", "", ""],
        ["bookings 1 ──── * invoices", "invoices 1 ──── * invoice_items", "invoices 1 ──── * payments", "pos_categories 1 ──── * pos_items"],
        ["pos_items 1 ──── * pos_order_items", "pos_orders 1 ──── * pos_order_items", "bookings 1 ──── * pos_orders", "pos_items.inv_item_id ──FK──→ inventory_items"],
    ]
    rt3 = Table(rel3_data, colWidths=[6*cm, 6*cm, 6*cm, 6*cm])
    rt3.setStyle(TableStyle([
        ("BACKGROUND",    (0,0), (-1,0), C_LIGHTGOLD),
        ("FONTNAME",      (0,0), (-1,0), "Helvetica-Bold"),
        ("FONTSIZE",      (0,0), (-1,-1), 7),
        ("GRID",          (0,0), (-1,-1), 0.3, colors.HexColor("#FFE082")),
        ("TOPPADDING",    (0,0), (-1,-1), 4),
        ("SPAN",          (0,0), (-1,0)),
        ("ALIGN",         (0,0), (-1,0), "CENTER"),
    ]))
    story.append(rt3)
    story.append(PageBreak())

    # ── PAGE 6: ERD Group 4 — Operations ──────────────────────────────────────
    story.append(Paragraph("  مخطط ERD — المجموعة الرابعة: التشغيل والمخزن والأمان", section_style))
    story.append(Spacer(1, 0.3*cm))

    ops_boxes = [
        ERDBox("housekeeping_tasks", [
            ("id", "SERIAL", "PK"),
            ("client_id", "INTEGER", "FK"),
            ("room_id", "INTEGER", "FK"),
            ("booking_id", "INTEGER", "FK"),
            ("task_type", "VARCHAR(50)", "checkout_clean/daily"),
            ("status", "VARCHAR(20)", "pending/done"),
            ("priority", "VARCHAR(20)", ""),
            ("assigned_to", "INTEGER", "FK→users"),
            ("started_at", "TIMESTAMPTZ", ""),
            ("completed_at", "TIMESTAMPTZ", ""),
        ], C_GREEN, C_WHITE, C_LIGHTGREEN, category="التدبير المنزلي"),

        ERDBox("maintenance_requests", [
            ("id", "SERIAL", "PK"),
            ("client_id", "INTEGER", "FK"),
            ("room_id", "INTEGER", "FK"),
            ("issue_type", "VARCHAR(100)", ""),
            ("description", "TEXT", "NOT NULL"),
            ("priority", "VARCHAR(20)", ""),
            ("status", "VARCHAR(20)", "open/resolved"),
            ("assigned_to", "INTEGER", "FK→users"),
            ("resolved_at", "TIMESTAMPTZ", ""),
        ], C_GREEN, C_WHITE, C_LIGHTGREEN, category="الصيانة"),

        ERDBox("inventory_items", [
            ("id", "SERIAL", "PK"),
            ("client_id", "INTEGER", "FK"),
            ("category_id", "INTEGER", "FK"),
            ("name", "VARCHAR(200)", "NOT NULL"),
            ("sku", "VARCHAR(50)", "UNIQUE"),
            ("unit", "VARCHAR(30)", ""),
            ("current_stock", "NUMERIC(12,2)", ""),
            ("min_stock", "NUMERIC(12,2)", ""),
            ("unit_cost", "NUMERIC(10,2)", ""),
        ], C_PURPLE, C_WHITE, C_LIGHTPURPLE, category="المخزن"),

        ERDBox("inventory_transactions", [
            ("id", "SERIAL", "PK"),
            ("client_id", "INTEGER", "FK"),
            ("item_id", "INTEGER", "FK"),
            ("transaction_type", "VARCHAR(20)", "in/out/waste"),
            ("quantity", "NUMERIC(12,2)", ""),
            ("unit_cost", "NUMERIC(10,2)", ""),
            ("reference_type", "VARCHAR(30)", ""),
            ("performed_by", "INTEGER", "FK"),
            ("transaction_date", "TIMESTAMPTZ", ""),
        ], C_PURPLE, C_WHITE, C_LIGHTPURPLE, category="حركات المخزن"),

        ERDBox("suppliers", [
            ("id", "SERIAL", "PK"),
            ("client_id", "INTEGER", "FK"),
            ("name", "VARCHAR(200)", "NOT NULL"),
            ("vat_number", "VARCHAR(50)", ""),
            ("contact_phone", "VARCHAR(20)", ""),
            ("payment_terms", "INTEGER", "days"),
            ("is_active", "BOOLEAN", ""),
        ], C_PURPLE, C_WHITE, C_LIGHTPURPLE, category="الموردون"),

        ERDBox("purchase_orders", [
            ("id", "SERIAL", "PK"),
            ("client_id", "INTEGER", "FK"),
            ("po_number", "VARCHAR(30)", "UNIQUE"),
            ("supplier_id", "INTEGER", "FK"),
            ("status", "VARCHAR(20)", "draft/received"),
            ("total_amount", "NUMERIC(12,2)", ""),
            ("created_by", "INTEGER", "FK"),
            ("approved_by", "INTEGER", "FK"),
        ], C_PURPLE, C_WHITE, C_LIGHTPURPLE, category="أوامر الشراء"),

        ERDBox("marketers", [
            ("id", "SERIAL", "PK"),
            ("name", "VARCHAR(200)", "NOT NULL"),
            ("email", "VARCHAR(255)", "UNIQUE"),
            ("ref_code", "VARCHAR(20)", "UNIQUE"),
            ("commission_rate", "NUMERIC(5,2)", ""),
            ("status", "VARCHAR(20)", "active"),
            ("total_referrals", "INTEGER", "computed"),
        ], C_RED, C_WHITE, C_LIGHTRED, category="المسوّقون"),

        ERDBox("marketer_referrals", [
            ("id", "SERIAL", "PK"),
            ("marketer_id", "INTEGER", "FK"),
            ("client_id", "INTEGER", "FK UNIQUE"),
            ("ref_code_used", "VARCHAR(20)", ""),
            ("commission_earned", "NUMERIC(10,2)", ""),
            ("commission_paid", "BOOLEAN", ""),
        ], C_RED, C_WHITE, C_LIGHTRED, category="الإحالات"),

        ERDBox("audit_log", [
            ("id", "BIGSERIAL", "PK"),
            ("client_id", "INTEGER", "FK"),
            ("user_id", "INTEGER", "FK"),
            ("user_email", "VARCHAR(255)", "frozen copy"),
            ("action", "VARCHAR(100)", "CREATE/UPDATE/DELETE"),
            ("resource_type", "VARCHAR(100)", ""),
            ("resource_id", "TEXT", ""),
            ("old_values", "JSONB", ""),
            ("new_values", "JSONB", ""),
            ("ip_address", "INET", ""),
            ("created_at", "TIMESTAMPTZ", "IMMUTABLE"),
        ], C_GREY, C_WHITE, C_LIGHTGREY, category="سجل التدقيق", is_new=True),

        ERDBox("inventory_categories", [
            ("id", "SERIAL", "PK"),
            ("client_id", "INTEGER", "FK"),
            ("name", "VARCHAR(100)", "NOT NULL"),
        ], C_PURPLE, C_WHITE, C_LIGHTPURPLE, category="تصنيفات المخزن", is_new=True),
    ]

    rows_data = []
    row = []
    for i, box in enumerate(ops_boxes):
        row.append(box)
        if len(row) == 4 or i == len(ops_boxes)-1:
            while len(row) < 4:
                row.append(Spacer(1, 1))
            rows_data.append(row)
            row = []

    for row_items in rows_data:
        t = Table([row_items], colWidths=[col_w, col_w, col_w, col_w])
        t.setStyle(TableStyle([
            ("VALIGN", (0,0), (-1,-1), "TOP"),
            ("LEFTPADDING", (0,0), (-1,-1), 6),
            ("RIGHTPADDING", (0,0), (-1,-1), 6),
            ("TOPPADDING", (0,0), (-1,-1), 4),
        ]))
        story.append(t)
        story.append(Spacer(1, 0.2*cm))

    rel4_data = [
        ["العلاقات — التشغيل والمخزن", "", "", ""],
        ["rooms 1 ──── * housekeeping_tasks", "rooms 1 ──── * maintenance_requests", "inventory_categories 1 ──── * inventory_items", "inventory_items 1 ──── * inventory_transactions"],
        ["suppliers 1 ──── * purchase_orders", "marketers 1 ──── * marketer_referrals", "clients 1 ──── 1 marketer_referrals", "audit_log: append-only (trigger)"],
    ]
    rt4 = Table(rel4_data, colWidths=[6*cm, 6*cm, 6*cm, 6*cm])
    rt4.setStyle(TableStyle([
        ("BACKGROUND",    (0,0), (-1,0), C_LIGHTGREY),
        ("FONTNAME",      (0,0), (-1,0), "Helvetica-Bold"),
        ("FONTSIZE",      (0,0), (-1,-1), 7),
        ("GRID",          (0,0), (-1,-1), 0.3, C_LIGHTGREY),
        ("TOPPADDING",    (0,0), (-1,-1), 4),
        ("SPAN",          (0,0), (-1,0)),
        ("ALIGN",         (0,0), (-1,0), "CENTER"),
    ]))
    story.append(rt4)
    story.append(PageBreak())

    # ── PAGE 7: Migration Strategy ─────────────────────────────────────────────
    story.append(Paragraph("  خطة الترحيل — من النموذج الحالي إلى النموذج الجديد", section_style))
    story.append(Spacer(1, 0.3*cm))

    migration_data = [
        ["المرحلة", "الإجراء", "الجداول المتأثرة", "الأولوية", "الوقت التقديري"],
        ["1 — هيكلية فورية",
         "إضافة جدول users رسمي\nإضافة role_permissions\nإضافة audit_log",
         "users, role_permissions, audit_log",
         "عالية جدًا", "يوم واحد"],
        ["2 — تطبيع الفواتير",
         "إنشاء invoice_items\nترحيل line_items JSONB → صفوف",
         "invoices → invoice_items",
         "عالية", "يومان"],
        ["3 — تطبيع الحجوزات",
         "إنشاء booking_guests\nترحيل companions JSONB → صفوف",
         "bookings → booking_guests",
         "متوسطة", "يومان"],
        ["4 — POS منظم",
         "إنشاء pos_categories, pos_items\npos_orders, pos_order_items\nترحيل pos_transactions",
         "pos_transactions → 4 جداول",
         "متوسطة", "3 أيام"],
        ["5 — غرف محسّنة",
         "إضافة room_type_id FK\nإنشاء amenities + room_amenities\nإضافة guest_documents",
         "rooms, room_types, amenities",
         "منخفضة", "يومان"],
        ["6 — تحديث PKs",
         "تحويل VARCHAR PKs إلى SERIAL\n(clients, bookings, invoices)\nإضافة public_id = UUID",
         "clients, bookings, invoices",
         "منخفضة — تأجيل", "أسبوع"],
        ["7 — الإبقاء على الموجود",
         "الإبقاء على جداول iCal, WhatsApp\nChatbot, HR, KPI, Assets, Tourism\nبدون تغيير",
         "18 جدول تُبقى كما هي",
         "لا تغيير", "—"],
    ]

    mig_table = Table(migration_data, colWidths=[4*cm, 7*cm, 6*cm, 2.5*cm, 3.5*cm])
    mig_table.setStyle(TableStyle([
        ("BACKGROUND",    (0,0), (-1,0), C_HEADER_BG),
        ("TEXTCOLOR",     (0,0), (-1,0), C_WHITE),
        ("FONTNAME",      (0,0), (-1,0), "Helvetica-Bold"),
        ("FONTSIZE",      (0,0), (-1,0), 9),
        ("FONTSIZE",      (0,1), (-1,-1), 8),
        ("VALIGN",        (0,0), (-1,-1), "MIDDLE"),
        ("GRID",          (0,0), (-1,-1), 0.4, colors.HexColor("#90CAF9")),
        ("TOPPADDING",    (0,0), (-1,-1), 6),
        ("BOTTOMPADDING", (0,0), (-1,-1), 6),
        # Priority color coding
        ("BACKGROUND",    (3,1), (3,1), colors.HexColor("#FFCDD2")),
        ("BACKGROUND",    (3,2), (3,3), C_LIGHTORANGE),
        ("BACKGROUND",    (3,4), (3,5), C_LIGHTGOLD),
        ("BACKGROUND",    (0,1), (0,1), colors.HexColor("#FFCDD2")),
        ("BACKGROUND",    (0,2), (0,3), C_LIGHTORANGE),
        ("BACKGROUND",    (0,4), (0,5), C_LIGHTGOLD),
        ("BACKGROUND",    (0,6), (-1,6), colors.HexColor("#F1F8E9")),
    ]))
    story.append(mig_table)
    story.append(Spacer(1, 0.5*cm))

    # Final note
    note_style = ParagraphStyle("Note", parent=body_style, fontSize=8.5,
                                  backColor=C_LIGHTBLUE, leftIndent=8, rightIndent=8,
                                  topPadding=8, bottomPadding=8)
    story.append(Paragraph(
        "<b>ملاحظة مهمة:</b> التحويل من VARCHAR(50) إلى SERIAL في جداول clients/bookings/invoices "
        "هو أكبر تغيير وأكثرها خطورة لأنه يؤثر على جميع الـ FKs المرتبطة. يُوصى بتأجيله حتى "
        "تستقر بقية التحسينات، أو تطبيقه في بيئة منفصلة مع ترحيل كامل للبيانات.",
        note_style
    ))
    story.append(Spacer(1, 0.3*cm))
    story.append(Paragraph(
        "<b>القرار المقترح:</b> دمج النموذجين — الإبقاء على جداول iCal/WhatsApp/Chatbot/HR/Tourism "
        "الموجودة، وإضافة الجداول الجديدة (users, invoice_items, booking_guests, pos_items, audit_log) "
        "كـ migrations إضافية بدون تغيير الجداول الحالية.",
        note_style
    ))

    # Build
    doc.build(story)
    print(f"✅ PDF created: {OUTPUT}")
    return OUTPUT


if __name__ == "__main__":
    build_pdf()
