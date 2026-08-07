#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
tests/test_reporting_views.py — طرق العرض التقريرية وتوثيق قاعدة البيانات.

كان في المشروع كله طريقة عرض واحدة رغم أن القسم العاشر من وثيقة التصميم
يسرد أكثر من عشرين تقريراً — كلها استعلامات في Markdown لا كائنات في
قاعدة البيانات. ولم يكن في الكتالوج ولا تعليق واحد.

الخطر الأهم الذي تحرسه هذه الاختبارات: طريقة العرض في PostgreSQL
تُنفَّذ افتراضياً بصلاحيات مالكها لا بصلاحيات من يستعلم عنها. وبما أن
مالكها هو مالك الجداول، فإن سياسات RLS لا تسري عليها — وطريقة عرض
واحدة بلا security_invoker تكفي لتُظهر لكل منشأة أرقامَ المنشآت الأخرى.
"""

import os

import pytest

DATABASE_URL = os.environ.get("DATABASE_URL", "")
pytestmark = pytest.mark.skipif(not DATABASE_URL, reason="DATABASE_URL not set")

EXPECTED_VIEWS = [
    "v_daily_occupancy", "v_kpi_daily", "v_arrivals_departures",
    "v_revenue_daily", "v_outstanding_invoices", "v_housekeeping_pending",
    "v_low_stock", "v_inventory_value", "v_marketer_performance",
]

TENANT_A = "view_tenant_a"
TENANT_B = "view_tenant_b"


@pytest.fixture(scope="module")
def views(db_pool):
    from db.schema_v3 import (
        run_app_role_migration, run_reporting_views, run_rls_migration,
        run_table_comments,
    )
    run_reporting_views(db_pool)
    run_table_comments(db_pool)
    run_app_role_migration(db_pool)
    os.environ["RLS_ENFORCE"] = "1"
    run_rls_migration(db_pool)
    return db_pool


# ── الوجود والسلامة ───────────────────────────────────────────────────────────

@pytest.mark.parametrize("view", EXPECTED_VIEWS)
def test_view_exists(views, view):
    row = views.execute(
        "SELECT to_regclass(%s) IS NOT NULL AS ok", (f"public.{view}",), fetch="one"
    )
    assert row["ok"], f"طريقة العرض مفقودة: {view}"


@pytest.mark.parametrize("view", EXPECTED_VIEWS)
def test_view_is_queryable(views, view):
    """طريقة عرض لا تُنفَّذ لا قيمة لها — نتحقّق أنها تعمل فعلاً."""
    views.execute(f"SELECT * FROM {view} LIMIT 1", fetch="all")


def test_every_view_has_security_invoker(views):
    """بدونه تتجاوز طريقة العرض سياسات RLS وتكشف بيانات كل المنشآت."""
    leaky = views.execute(
        """
        SELECT c.relname AS v
        FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace
        WHERE n.nspname = 'public' AND c.relkind = 'v'
          AND NOT COALESCE(
              (SELECT option_value = 'true' FROM pg_options_to_table(c.reloptions)
               WHERE option_name = 'security_invoker'), FALSE)
        """,
        fetch="all",
    ) or []
    assert not leaky, f"طرق عرض تتجاوز العزل: {[r['v'] for r in leaky]}"


# ── العزل عبر طرق العرض ───────────────────────────────────────────────────────

@pytest.fixture(scope="module")
def two_tenants(views):
    for tid in (TENANT_A, TENANT_B):
        views.execute("DELETE FROM clients WHERE id = %s", (tid,))
        views.execute("INSERT INTO clients (id, name) VALUES (%s, %s)", (tid, tid))
        views.execute(
            "INSERT INTO rooms (client_id, room_number, base_price, status) "
            "VALUES (%s, '101', 500, 'available')", (tid,)
        )
        views.execute(
            "INSERT INTO warehouse_items (client_id, name, quantity, reorder_level, price_per_unit) "
            "VALUES (%s, 'صنف', 1, 10, 25)", (tid,)
        )
    yield views
    for tid in (TENANT_A, TENANT_B):
        views.execute("DELETE FROM clients WHERE id = %s", (tid,))


@pytest.mark.parametrize("view", ["v_daily_occupancy", "v_low_stock", "v_inventory_value"])
def test_view_leaks_nothing_across_tenants(two_tenants, view):
    """الاختبار الحاسم: الاستعلام بدور مُقيَّد يجب ألا يُظهر إلا صفوف
    المستأجر الحالي."""
    import psycopg2
    from psycopg2.extras import RealDictCursor

    conn = psycopg2.connect(DATABASE_URL)
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("SET ROLE dheuof_app")
            cur.execute("SELECT set_config('app.tenant_id', %s, false)", (TENANT_A,))
            cur.execute(f"SELECT DISTINCT client_id FROM {view}")
            seen = {r["client_id"] for r in cur.fetchall()}
    finally:
        conn.rollback()
        conn.close()

    assert TENANT_B not in seen, f"{view} سرّبت بيانات مستأجر آخر"
    assert seen <= {TENANT_A}, f"{view} أظهرت مستأجرين غير متوقّعين: {seen}"


def test_low_stock_finds_the_right_rows(two_tenants):
    """الصنف الذي كميته 1 وحدّ إعادة طلبه 10 يجب أن يظهر."""
    rows = two_tenants.execute(
        "SELECT name, shortfall, current_value FROM v_low_stock WHERE client_id = %s",
        (TENANT_A,), fetch="all",
    )
    assert rows, "لم تظهر الأصناف الناقصة"
    assert rows[0]["shortfall"] == 9
    assert float(rows[0]["current_value"]) == 25.0


def test_occupancy_reports_zero_when_no_bookings(two_tenants):
    rows = two_tenants.execute(
        "SELECT rooms_total, rooms_occupied, occupancy_pct FROM v_daily_occupancy "
        "WHERE client_id = %s AND day = CURRENT_DATE", (TENANT_A,), fetch="all",
    )
    assert rows and rows[0]["rooms_total"] == 1
    assert rows[0]["rooms_occupied"] == 0
    assert float(rows[0]["occupancy_pct"]) == 0.0


# ── توثيق داخل قاعدة البيانات ─────────────────────────────────────────────────

@pytest.mark.parametrize("table", ["clients", "guests", "bookings", "invoices", "audit_log"])
def test_core_table_is_documented(views, table):
    row = views.execute(
        "SELECT obj_description(to_regclass(%s), 'pg_class') AS c",
        (f"public.{table}",), fetch="one",
    )
    assert row["c"], f"لا تعليق على الجدول {table}"


def test_encrypted_columns_are_documented(views):
    """أهم ما يحتاج توثيقاً داخلياً: لماذا العمود الصريح فارغ."""
    row = views.execute(
        """
        SELECT col_description(to_regclass('public.guests'), a.attnum) AS c
        FROM pg_attribute a
        WHERE a.attrelid = to_regclass('public.guests')
          AND a.attname = 'id_number_enc'
        """,
        fetch="one",
    )
    assert row and row["c"], "عمود التشفير غير موثَّق"
