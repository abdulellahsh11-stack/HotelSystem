#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
tests/test_rls_isolation.py — إثبات عزل المستأجرين على مستوى قاعدة البيانات.

هذه الاختبارات لا تكتفي بالتحقق من وجود السياسات، بل تفتح اتصالاً بدور
مُقيَّد وتحاول فعلياً قراءة بيانات مستأجر آخر. الحالة السابقة كانت تنجح
في «وجود RLS» وتفشل في العزل: كان RLS مُفعَّلاً على 7 جداول بصفر سياسات،
والتطبيق يتصل بمالك الجداول فيتجاوز RLS كلياً.
"""

import os

import pytest

DATABASE_URL = os.environ.get("DATABASE_URL", "")
pytestmark = pytest.mark.skipif(not DATABASE_URL, reason="DATABASE_URL not set")

TENANT_A = "rls_tenant_a"
TENANT_B = "rls_tenant_b"


@pytest.fixture(scope="module")
def seeded(db_pool):
    """ينشئ مستأجرَين ببيانات مميّزة، ويُطبّق السياسات بصيغة FORCE."""
    from db.schema_v3 import run_app_role_migration, run_rls_migration

    for tid, name in ((TENANT_A, "فندق أ"), (TENANT_B, "فندق ب")):
        db_pool.execute("DELETE FROM clients WHERE id = %s", (tid,))
        db_pool.execute("INSERT INTO clients (id, name) VALUES (%s, %s)", (tid, name))
        db_pool.execute(
            "INSERT INTO guests (client_id, full_name) VALUES (%s, %s)",
            (tid, f"نزيل {name}"),
        )

    run_app_role_migration(db_pool)
    os.environ["RLS_ENFORCE"] = "1"
    run_rls_migration(db_pool)

    # المجمّع يقرأ RLS_ENFORCE عند الإنشاء، وقد أُنشئ قبل هذه النقطة.
    # نُفعّل التحوّل إلى الدور المُقيَّد صراحةً لأن هذه الاختبارات تفحص
    # وضع العزل المفروض تحديداً.
    previous = db_pool._app_role_available
    db_pool._app_role_available = True

    yield db_pool

    db_pool._app_role_available = previous
    for tid in (TENANT_A, TENANT_B):
        db_pool.execute("DELETE FROM clients WHERE id = %s", (tid,))


def _as_restricted_role(sql, params=(), tenant=None):
    """ينفّذ استعلاماً باتصال منفصل يتقمّص الدور المُقيَّد dheuof_app."""
    import psycopg2
    from psycopg2.extras import RealDictCursor

    conn = psycopg2.connect(DATABASE_URL)
    try:
        conn.autocommit = False
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("SET ROLE dheuof_app")
            cur.execute("SELECT set_config('app.tenant_id', %s, false)", (tenant or "",))
            cur.execute(sql, params or None)
            return cur.fetchall()
    finally:
        conn.rollback()
        conn.close()


# ── وجود السياسات ─────────────────────────────────────────────────────────────

def test_every_tenant_table_has_an_isolation_policy(seeded):
    """كل جدول يحمل client_id يجب أن تكون عليه سياسة عزل."""
    missing = seeded.execute(
        """
        SELECT c.relname AS t
        FROM pg_class c
        JOIN pg_namespace n ON n.oid = c.relnamespace
        WHERE n.nspname = 'public' AND c.relkind = 'r'
          AND EXISTS (SELECT 1 FROM information_schema.columns col
                      WHERE col.table_schema='public' AND col.table_name=c.relname
                        AND col.column_name='client_id')
          AND NOT EXISTS (SELECT 1 FROM pg_policies p
                          WHERE p.schemaname='public' AND p.tablename=c.relname)
        ORDER BY 1
        """,
        fetch="all",
    )
    assert not missing, f"جداول بلا سياسة عزل: {[m['t'] for m in missing]}"


def test_policies_are_forced_so_owner_cannot_bypass(seeded):
    """بدون FORCE يتجاوز مالكُ الجدول السياساتِ — والتطبيق يتصل بالمالك."""
    unforced = seeded.execute(
        "SELECT relname AS t FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace "
        "WHERE n.nspname='public' AND c.relkind='r' AND c.relrowsecurity AND NOT c.relforcerowsecurity",
        fetch="all",
    )
    assert not unforced, f"RLS غير مفروض على: {[u['t'] for u in unforced]}"


# ── العزل الفعلي ──────────────────────────────────────────────────────────────

def test_tenant_sees_only_own_rows(seeded):
    rows = _as_restricted_role("SELECT client_id FROM guests", tenant=TENANT_A)
    assert rows, "المستأجر لا يرى بياناته"
    assert {r["client_id"] for r in rows} == {TENANT_A}


def test_tenant_cannot_read_other_tenant_rows(seeded):
    """الاختبار الحاسم: محاولة صريحة لقراءة بيانات مستأجر آخر."""
    rows = _as_restricted_role(
        "SELECT * FROM guests WHERE client_id = %s", (TENANT_B,), tenant=TENANT_A
    )
    assert rows == [], "تسريب بين المستأجرين — RLS لا يعزل"


def test_missing_tenant_context_yields_no_rows(seeded):
    """غياب السياق يجب أن يفشل مغلقاً لا مفتوحاً."""
    assert _as_restricted_role("SELECT * FROM guests", tenant=None) == []


def test_cannot_insert_row_for_another_tenant(seeded):
    """WITH CHECK يمنع كتابة صف باسم مستأجر آخر.

    PostgreSQL يرفع InsufficientPrivilege لا CheckViolation عند مخالفة
    WITH CHECK في سياسة RLS.
    """
    import psycopg2

    with pytest.raises(psycopg2.errors.InsufficientPrivilege):
        _as_restricted_role(
            "INSERT INTO guests (client_id, full_name) VALUES (%s, 'دخيل') RETURNING id",
            (TENANT_B,),
            tenant=TENANT_A,
        )


def test_clients_table_is_isolated_too(seeded):
    rows = _as_restricted_role("SELECT id FROM clients", tenant=TENANT_A)
    assert {r["id"] for r in rows} == {TENANT_A}


# ── سياق المستأجر في طبقة التطبيق ─────────────────────────────────────────────

def test_pool_binds_tenant_from_contextvar(db_pool):
    """DatabasePool يجب أن يضبط app.tenant_id على كل اتصال يستعيره."""
    from db.tenant_context import tenant_scope

    with tenant_scope("ctx_probe"):
        got = db_pool.execute(
            "SELECT current_setting('app.tenant_id', true) AS t", fetch="one"
        )["t"]
    assert got == "ctx_probe"


def test_tenant_context_does_not_leak_between_checkouts(db_pool):
    """الاتصال المُعاد للمجمّع يجب ألا يحمل سياق المستأجر السابق."""
    from db.tenant_context import tenant_scope

    with tenant_scope("ctx_probe"):
        db_pool.execute("SELECT 1")

    leaked = db_pool.execute(
        "SELECT current_setting('app.tenant_id', true) AS t", fetch="one"
    )["t"]
    assert not leaked, f"تسرّب سياق المستأجر: {leaked!r}"


def test_app_pool_itself_enforces_isolation(seeded):
    """الاختبار الأهم: العزل عبر مجمّع التطبيق نفسه لا عبر اتصال يدوي.

    مع وجود سياق مستأجر يتحوّل المجمّع إلى الدور المُقيَّد، فتسري عليه
    سياسات RLS. هذا ما يجعل خطأً برمجياً ينسى شرط client_id غير قادر
    على تسريب بيانات منشأة أخرى.
    """
    from db.tenant_context import tenant_scope

    with tenant_scope(TENANT_A):
        # استعلام بلا أي شرط client_id — الحماية من قاعدة البيانات وحدها
        rows = seeded.execute("SELECT client_id FROM guests", fetch="all")

    assert rows, "المستأجر لا يرى بياناته"
    assert {r["client_id"] for r in rows} == {TENANT_A}, "تسريب بين المستأجرين"


def test_app_pool_without_tenant_keeps_owner_access(seeded):
    """بلا سياق مستأجر يبقى الاتصال بالمالك — تحتاجه الترحيلات ولوحة
    المالك والتقارير العابرة للمنشآت."""
    rows = seeded.execute(
        "SELECT client_id FROM guests WHERE client_id IN (%s, %s)",
        (TENANT_A, TENANT_B), fetch="all",
    )
    assert {r["client_id"] for r in rows} == {TENANT_A, TENANT_B}


def test_role_is_reset_between_checkouts(seeded):
    """الدور المُقيَّد يجب ألا يتسرّب إلى المستعير التالي للاتصال."""
    from db.tenant_context import tenant_scope

    with tenant_scope(TENANT_A):
        seeded.execute("SELECT 1")

    role = seeded.execute("SELECT current_user AS r", fetch="one")["r"]
    assert role != "dheuof_app", f"تسرّب الدور المُقيَّد: {role}"


def test_set_event_context_actually_persists(db_pool):
    """كانت تستخدم is_local=True مع db.execute الذي يُنفّذ COMMIT فوراً،
    فيُمحى الضبط قبل أن يستفيد منه أي استعلام — أي بلا أثر إطلاقاً."""
    from db.security import set_event_context
    from db.tenant_context import set_current_tenant

    set_event_context(db_pool, "evt_tenant")
    try:
        got = db_pool.execute(
            "SELECT current_setting('app.tenant_id', true) AS t", fetch="one"
        )["t"]
        assert got == "evt_tenant"
    finally:
        set_current_tenant(None)
