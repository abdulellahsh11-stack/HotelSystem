#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
db/rls.py — عزل المستأجرين على مستوى قاعدة البيانات (RLS)

طبقة الدفاع الثانية. الأولى شرط `client_id` في كل استعلام، ويحرسها
`tests/test_tenant_isolation.py`. لكن الحارس يفحص الكود المكتوب، وسطرٌ
واحد يُكتب في لحظة عجلة يمرّ من أي مراجعة. RLS يجعل قاعدة البيانات
نفسها ترفض، فيصير نسيانُ الشرط خطأً في النتيجة لا ثغرةً صامتة.

ثلاثة شروط لا تعمل الحماية بدونها مجتمعةً:

١ — `FORCE ROW LEVEL SECURITY`. بدونها يتجاوز **مالك الجدول** كل
    السياسات. والتطبيق يُنشئ الجداول، فهو مالكها. RLS بلا FORCE في هذا
    المستودع كان صفراً عملياً رغم ظهوره مُفعَّلاً.

٢ — مستخدم تطبيقٍ بـ `NOBYPASSRLS` وليس superuser.

٣ — ضبط سياق المستأجر داخل نفس المعاملة قبل الاستعلام.

الشرط الثالث كان يمنع التفعيل: طبقة الاتصال تُنفّذ كل `execute()` في
معاملة مستقلة، فسياقٌ يُضبط بنداء منفصل يضيع قبل الاستعلام التالي.
حُلَّ ذلك في `db/tenant_context.py` و`db._bind_tenant_context`: يُسجَّل
المستأجر في ContextVar عند بداية الطلب، وتضبطه طبقة الاتصال داخل معاملة
كل استعلام قبل تنفيذه.

التشغيل يحتاج ثلاث خطوات بهذا الترتيب:
  ١ — `enable_rls(db)` بمستخدمٍ يملك الجداول (مرة واحدة)
  ٢ — تحويل `DATABASE_URL` إلى دور التطبيق (`app_role_sql`)
  ٣ — `RLS_ENABLED=1`

عكسُ الترتيب يُوقف المنصة: تفعيل المفتاح قبل تطبيق السياسات يجعل كل
استعلام يُعيد صفراً.
"""
from __future__ import annotations

import logging

log = logging.getLogger("dheuof.db.rls")

# اسم متغيّر الجلسة. موحَّد في مكان واحد لأن اختلافه بين السياسة والكود
# يجعل الحماية تمنع الجميع أو لا تمنع أحداً — وقد حدث ذلك هنا فعلاً:
# الكود كان يضبط `app.tenant_id` والسياسة المعطَّلة تقرأ
# `app.current_client_id`.
TENANT_SETTING = "app.current_client_id"

# نطاق مالك المنصة — يرى كل المنشآت. متغيّر منفصل عن المستأجر عمداً:
# لو كان قيمةً خاصة في نفس المتغيّر لأمكن بلوغه بتمرير تلك القيمة.
PLATFORM_SETTING = "app.platform_admin"

# الجداول التي تحمل client_id ويجب عزلها في قاعدة البيانات
RLS_TABLES: tuple[str, ...] = (
    "guests", "bookings", "rooms", "invoices", "employees",
    "warehouse_items", "maintenance_orders", "housekeeping_tasks",
    "pos_sales", "attendance", "payroll", "booking_reviews",
    "zatca_invoices", "staff_users", "check_in_log",
)


def policy_sql(table: str) -> list[str]:
    """
    جمل تفعيل العزل لجدول واحد.

    `USING` تحكم ما يُقرأ ويُعدَّل، و`WITH CHECK` تحكم ما يُكتب — بدونها
    يستطيع مستأجرٌ إدراج صفٍّ باسم مستأجر آخر ثم يفقد رؤيته.

    `current_setting(..., true)` تُعيد NULL بدل الخطأ عند غياب السياق،
    والمقارنة بـ NULL تُنتج NULL — أي لا صفوف. فشلٌ مغلق بالتصميم.
    """
    return [
        f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY",
        # بدون FORCE يتجاوز مالكُ الجدول السياسةَ كلها
        f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY",
        f"DROP POLICY IF EXISTS tenant_isolation ON {table}",
        # شرط مالك المنصة: نطاقٌ يُفتح من مسارات المشرف وحدها بعد
        # `require_admin`، ولا يبلغه مستأجر بتمرير معرّف. اتساعه يُلغي
        # الحماية، فيُفتح لأضيق كتلة ممكنة.
        f"""CREATE POLICY tenant_isolation ON {table}
                USING (
                    client_id = current_setting('{TENANT_SETTING}', true)
                    OR current_setting('{PLATFORM_SETTING}', true) = 'on'
                )
                WITH CHECK (
                    client_id = current_setting('{TENANT_SETTING}', true)
                    OR current_setting('{PLATFORM_SETTING}', true) = 'on'
                )""",
        # الفهرس شرط أداء لا رفاهية: كل استعلام صار يُصفّى بـ client_id
        f"CREATE INDEX IF NOT EXISTS idx_{table}_tenant ON {table} (client_id)",
    ]


def apply_tenant_context(cursor, client_id: str) -> None:
    """
    يضبط سياق المستأجر داخل المعاملة الجارية.

    `true` تعني محلياً للمعاملة: ينتهي السياق بانتهائها، فلا يتسرّب إلى
    الطلب التالي عبر اتصالٍ مُعاد إلى المجمَّع — وهو التسريب الأخطر في
    أنظمة التجميع، إذ يورث مستأجرٌ سياقَ من سبقه.

    **يجب أن يُستدعى على نفس الـ cursor وداخل نفس المعاملة** التي
    ستُنفَّذ فيها الاستعلامات. استعمل `DatabasePool.transaction()`.
    """
    cursor.execute(
        "SELECT set_config(%s, %s, true)", (TENANT_SETTING, str(client_id))
    )


def enable_rls(db, tables: tuple[str, ...] = RLS_TABLES) -> dict:
    """
    يُفعّل العزل على الجداول الموجودة. يتخطّى غير الموجود منها.

    لا يُستدعى تلقائياً عند الإقلاع: تفعيله قبل أن تضبط طبقةُ الاتصال
    السياقَ لكل معاملة يُوقف المنصة بالكامل — كل استعلام سيُعيد صفراً.
    """
    applied, skipped = [], []
    for table in tables:
        exists = db.execute(
            "SELECT to_regclass(%s) AS t", (f"public.{table}",), fetch="one"
        )
        if not exists or not exists.get("t"):
            skipped.append(table)
            continue
        for stmt in policy_sql(table):
            db.execute(stmt)
        applied.append(table)
    log.info("RLS مُفعَّل على %d جدولاً، وتُخطّي %d", len(applied), len(skipped))
    return {"applied": applied, "skipped": skipped}


def app_role_sql(role_name: str = "dheuof_app") -> list[str]:
    """
    دور التطبيق. كلمة المرور تُمرَّر من متغيّر بيئة عند التنفيذ، ولا
    تُكتب هنا ولا في أي ملف يدخل المستودع.

    NOBYPASSRLS صراحةً: الافتراضي في PostgreSQL هو عدم التجاوز، لكن
    كتابته تجعل النية ظاهرة لمن يراجع لاحقاً.
    """
    return [
        f"ALTER ROLE {role_name} NOSUPERUSER NOCREATEDB NOBYPASSRLS",
        f"GRANT USAGE ON SCHEMA public TO {role_name}",
        f"GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO {role_name}",
        f"GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO {role_name}",
        f"ALTER DEFAULT PRIVILEGES IN SCHEMA public "
        f"GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO {role_name}",
        f"ALTER DEFAULT PRIVILEGES IN SCHEMA public "
        f"GRANT USAGE, SELECT ON SEQUENCES TO {role_name}",
    ]
