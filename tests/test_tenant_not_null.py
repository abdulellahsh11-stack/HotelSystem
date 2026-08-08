#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
tests/test_tenant_not_null.py — إلزامية client_id ومنع الصفوف اليتيمة.

كان 69 عموداً client_id يقبل الفراغ. والصف بـ client_id فارغ لا يملكه
أحد: لا تراه سياسة العزل (المقارنة بـ NULL لا تُطابق شيئاً)، ولا يظهر
في تقرير، ولا يُحذف مع المنشأة. والأخطر أن خطأً برمجياً ينسى client_id
يمرّ بصمت بدل أن يُرفض عند الكتابة.
"""

import os

import pytest

DATABASE_URL = os.environ.get("DATABASE_URL", "")
pytestmark = pytest.mark.skipif(not DATABASE_URL, reason="DATABASE_URL not set")

# client_id الفارغ فيها مقصود: قالب دور عام لكل المنشآت
EXEMPT = {"staff_roles"}

CORE_TABLES = [
    "guests", "bookings", "rooms", "invoices", "employees",
    "payroll", "warehouse_items", "housekeeping_tasks", "maintenance_orders",
]


@pytest.fixture(scope="module")
def tightened(db_pool):
    # conftest يُشغّل ترحيل v1 فقط؛ الجداول المفحوصة هنا تأتي من v3
    # والتحصين الأمني، فلا بدّ من سلسلة الترحيل كاملة قبل الفحص.
    from db.schema_v3 import (
        run_security_hardening, run_staff_app_migrations, run_tenant_not_null,
        run_v3_migrations, run_v4_migrations,
    )
    run_v3_migrations(db_pool)
    run_staff_app_migrations(db_pool)
    run_v4_migrations(db_pool)
    run_security_hardening(db_pool)
    run_tenant_not_null(db_pool)
    return db_pool


@pytest.mark.parametrize("table", CORE_TABLES)
def test_core_table_requires_a_tenant(tightened, table):
    nullable = tightened.execute(
        "SELECT is_nullable FROM information_schema.columns "
        "WHERE table_schema='public' AND table_name=%s AND column_name='client_id'",
        (table,), fetch="one",
    )
    assert nullable and nullable["is_nullable"] == "NO", \
        f"{table}.client_id ما زال يقبل الفراغ"


def test_no_real_table_still_allows_a_missing_tenant(tightened):
    rows = tightened.execute(
        """
        SELECT c.table_name AS t
        FROM information_schema.columns c
        JOIN pg_class pc ON pc.relname = c.table_name
        JOIN pg_namespace n ON n.oid = pc.relnamespace AND n.nspname = 'public'
        WHERE c.table_schema = 'public' AND c.column_name = 'client_id'
          AND c.is_nullable = 'YES' AND pc.relkind = 'r'
        """,
        fetch="all",
    ) or []
    remaining = {r["t"] for r in rows} - EXEMPT
    assert not remaining, f"جداول ما زال client_id فيها اختيارياً: {remaining}"


def test_global_role_templates_stay_exempt(tightened):
    """قالب الدور العام بلا منشأة بحكم تعريفه — فرض NOT NULL يُلغي الميزة."""
    nullable = tightened.execute(
        "SELECT is_nullable FROM information_schema.columns "
        "WHERE table_schema='public' AND table_name='staff_roles' AND column_name='client_id'",
        fetch="one",
    )
    assert nullable["is_nullable"] == "YES"
    assert tightened.execute(
        "SELECT COUNT(*) AS n FROM staff_roles WHERE client_id IS NULL", fetch="one"
    )["n"] >= 6, "قوالب الأدوار العامة اختفت"


def test_insert_without_tenant_is_now_rejected(tightened):
    """الخطأ البرمجي الذي ينسى client_id يُرفض بدل أن يمرّ بصمت."""
    import psycopg2
    with pytest.raises(psycopg2.errors.NotNullViolation):
        tightened.execute(
            "INSERT INTO rooms (room_number, base_price, status) "
            "VALUES ('يتيمة', 100, 'available')"
        )


# ── سلامة الترحيل ─────────────────────────────────────────────────────────────

def test_table_with_orphans_is_skipped_not_emptied(db_pool):
    """الجدول الذي يحوي صفوفاً يتيمة لا يُعدَّل ولا تُحذف بياناته.

    حذف بيانات العميل قرار بشري لا أثر جانبي لترحيل يعمل عند كل إقلاع.
    """
    from db.schema_v3 import run_tenant_not_null

    db_pool.execute("DROP TABLE IF EXISTS _orphan_probe")
    db_pool.execute(
        "CREATE TABLE _orphan_probe (id SERIAL PRIMARY KEY, client_id VARCHAR(50), note TEXT)"
    )
    db_pool.execute("INSERT INTO _orphan_probe (client_id, note) VALUES (NULL, 'يتيم')")
    db_pool.execute("INSERT INTO _orphan_probe (client_id, note) VALUES ('x', 'سليم')")
    try:
        run_tenant_not_null(db_pool)

        still_nullable = db_pool.execute(
            "SELECT is_nullable FROM information_schema.columns "
            "WHERE table_name='_orphan_probe' AND column_name='client_id'", fetch="one",
        )["is_nullable"]
        assert still_nullable == "YES", "فُرض NOT NULL رغم وجود صفوف يتيمة"

        surviving = db_pool.execute(
            "SELECT COUNT(*) AS n FROM _orphan_probe", fetch="one"
        )["n"]
        assert surviving == 2, "الترحيل حذف بيانات — يجب أن يتخطّى لا أن يمسح"
    finally:
        db_pool.execute("DROP TABLE IF EXISTS _orphan_probe")


def test_orphan_finder_reports_them(db_pool):
    import importlib.util
    path = os.path.join(os.path.dirname(__file__), "..", "scripts", "find_orphan_rows.py")
    spec = importlib.util.spec_from_file_location("orphan_finder", os.path.normpath(path))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    db_pool.execute("DROP TABLE IF EXISTS _orphan_probe2")
    db_pool.execute("CREATE TABLE _orphan_probe2 (id SERIAL PRIMARY KEY, client_id VARCHAR(50))")
    db_pool.execute("INSERT INTO _orphan_probe2 (client_id) VALUES (NULL), (NULL), ('ok')")
    try:
        found = dict(module.find_orphans(db_pool))
        assert found.get("_orphan_probe2") == 2
    finally:
        db_pool.execute("DROP TABLE IF EXISTS _orphan_probe2")


def test_migration_is_idempotent(db_pool):
    """يُشغَّل عند كل إقلاع — لا يجوز أن يفشل في المرة الثانية."""
    from db.schema_v3 import run_tenant_not_null
    run_tenant_not_null(db_pool)
    run_tenant_not_null(db_pool)
