#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
tests/test_rls_isolation.py — عزل المستأجرين داخل قاعدة البيانات

يُشغَّل على PostgreSQL حقيقي فقط. بلا خادم يُتخطّى، لأن محاكاة RLS بلا
محرّك حقيقي تُثبت أن المحاكاة صحيحة لا أن السياسة صحيحة.

يُضبط عنوان الخادم بـ `TEST_DATABASE_URL`. في CI شغّل خدمة postgres
وأسنِد المتغيّر إليها.

الحرج هنا: هذه الاختبارات تعمل بمستخدم **غير مالك** للجداول وبلا
BYPASSRLS. تشغيلها بمستخدم مالك يجعلها تمرّ بلا أن تفحص شيئاً — وهذا
بالضبط ما جعل RLS في هذا المستودع صفراً عملياً رغم ظهوره مُفعَّلاً.
"""
from __future__ import annotations

import os

import pytest

psycopg2 = pytest.importorskip("psycopg2", reason="psycopg2 غير مثبّت")

from db.rls import TENANT_SETTING, policy_sql  # noqa: E402

ADMIN_DSN = os.environ.get("TEST_DATABASE_URL", "")
APP_ROLE = "rls_test_app"
APP_PASSWORD = os.environ.get("TEST_APP_PASSWORD", "rls-test-only")

pytestmark = pytest.mark.skipif(
    not ADMIN_DSN, reason="TEST_DATABASE_URL غير مضبوط — لا خادم PostgreSQL"
)

A, B = "hotel_A", "hotel_B"


def _role_exists(cur) -> bool:
    cur.execute("SELECT 1 FROM pg_roles WHERE rolname=%s", (APP_ROLE,))
    return cur.fetchone() is not None


def _admin():
    conn = psycopg2.connect(ADMIN_DSN)
    conn.autocommit = True
    return conn


@pytest.fixture(scope="module")
def app_dsn():
    """يبني جدولاً وسياسةً ودورَ تطبيقٍ لا يتجاوز RLS، ويُنظّف بعده."""
    admin = _admin()
    with admin.cursor() as cur:
        cur.execute("DROP TABLE IF EXISTS rls_facilities")
        cur.execute("""
            CREATE TABLE rls_facilities (
                id         SERIAL PRIMARY KEY,
                client_id  VARCHAR(50) NOT NULL,
                name       TEXT NOT NULL
            )
        """)
        for stmt in policy_sql("rls_facilities"):
            cur.execute(stmt)

        # DROP OWNED قبل DROP ROLE: الصلاحيات الممنوحة تبقى معتمِدةً
        # على الدور فيرفض حذفه، وتفشل كل الاختبارات بخطأ لا علاقة له
        # بالعزل.
        cur.execute(f"DROP OWNED BY {APP_ROLE} CASCADE" if _role_exists(cur) else "SELECT 1")
        cur.execute("DROP ROLE IF EXISTS %s" % APP_ROLE)
        cur.execute(
            f"CREATE ROLE {APP_ROLE} LOGIN PASSWORD %s "
            f"NOSUPERUSER NOCREATEDB NOBYPASSRLS", (APP_PASSWORD,)
        )
        cur.execute(f"GRANT USAGE ON SCHEMA public TO {APP_ROLE}")
        cur.execute(
            f"GRANT SELECT, INSERT, UPDATE, DELETE ON rls_facilities TO {APP_ROLE}")
        cur.execute(
            f"GRANT USAGE, SELECT ON SEQUENCE rls_facilities_id_seq TO {APP_ROLE}")

    base = ADMIN_DSN
    dsn = base.replace("user=postgres", f"user={APP_ROLE}")
    if dsn == base:  # صيغة URL
        dsn = base.replace("://postgres", f"://{APP_ROLE}")
    yield dsn

    with admin.cursor() as cur:
        cur.execute("DROP TABLE IF EXISTS rls_facilities")
        if _role_exists(cur):
            cur.execute(f"DROP OWNED BY {APP_ROLE} CASCADE")
            cur.execute("DROP ROLE IF EXISTS %s" % APP_ROLE)
    admin.close()


@pytest.fixture
def conn(app_dsn):
    # التفريغ بصلاحية المشرف قبل كل اختبار: الجدول مشترك على مستوى
    # الوحدة، ودورُ التطبيق لا يرى صفوف غيره فلا يستطيع تنظيفها. بلا
    # ذلك تتراكم الصفوف فتفشل التأكيدات العددية لسببٍ لا علاقة له
    # بالعزل.
    admin = _admin()
    with admin.cursor() as cur:
        cur.execute("TRUNCATE rls_facilities")
    admin.close()

    c = psycopg2.connect(app_dsn)
    c.autocommit = True
    yield c
    c.close()


def _set_tenant(cur, client_id):
    cur.execute("SELECT set_config(%s, %s, false)", (TENANT_SETTING, client_id))


def _clear_tenant(cur):
    cur.execute("SELECT set_config(%s, '', false)", (TENANT_SETTING,))


def _seed(conn):
    with conn.cursor() as cur:
        for cid, name in ((A, "منشأة أ"), (B, "سرّي ب")):
            _set_tenant(cur, cid)
            cur.execute(
                "INSERT INTO rls_facilities (client_id, name) VALUES (%s, %s)",
                (cid, name))


def test_the_app_role_cannot_bypass_rls(conn):
    """لو كان الدور مالكاً أو BYPASSRLS لمرّ كل ما تحته بلا فحص."""
    with conn.cursor() as cur:
        cur.execute("SELECT rolbypassrls, rolsuper FROM pg_roles WHERE rolname=current_user")
        bypass, superuser = cur.fetchone()
    assert not bypass, "دور الاختبار يتجاوز RLS — الاختبارات لا تفحص شيئاً"
    assert not superuser


def test_a_tenant_sees_only_its_own_rows(conn):
    _seed(conn)
    with conn.cursor() as cur:
        _set_tenant(cur, A)
        cur.execute("SELECT name FROM rls_facilities")
        names = {r[0] for r in cur.fetchall()}
    assert names == {"منشأة أ"}, f"تسريب عزل — رأى «أ»: {names}"


def test_a_tenant_cannot_update_another_tenants_row(conn):
    _seed(conn)
    with conn.cursor() as cur:
        _set_tenant(cur, A)
        cur.execute("UPDATE rls_facilities SET name='اختراق' WHERE name='سرّي ب'")
        assert cur.rowcount == 0, "عدّل مستأجرٌ صفَّ مستأجر آخر"


def test_a_tenant_cannot_delete_another_tenants_row(conn):
    _seed(conn)
    with conn.cursor() as cur:
        _set_tenant(cur, A)
        cur.execute("DELETE FROM rls_facilities WHERE name='سرّي ب'")
        assert cur.rowcount == 0
        _set_tenant(cur, B)
        cur.execute("SELECT COUNT(*) FROM rls_facilities WHERE name='سرّي ب'")
        assert cur.fetchone()[0] == 1, "حُذف صفّ «ب»"


def test_with_check_blocks_writing_under_another_tenants_id(conn):
    """
    بلا WITH CHECK يستطيع مستأجرٌ إدراج صفٍّ باسم غيره ثم يفقد رؤيته —
    فيلوّث بياناتِ منشأة أخرى بلا أن يظهر ذلك عنده.
    """
    with conn.cursor() as cur:
        _set_tenant(cur, A)
        # PostgreSQL يرفع InsufficientPrivilege (42501) لمخالفة
        # WITH CHECK في RLS، لا CheckViolation.
        with pytest.raises(psycopg2.errors.InsufficientPrivilege):
            cur.execute(
                "INSERT INTO rls_facilities (client_id, name) VALUES (%s, %s)",
                (B, "مدسوس"))


def test_no_tenant_context_means_no_data(conn):
    """فشلٌ مغلق: بلا سياق لا تظهر بيانات — لا أن تظهر كلها."""
    _seed(conn)
    with conn.cursor() as cur:
        _clear_tenant(cur)
        cur.execute("SELECT * FROM rls_facilities")
        assert cur.fetchall() == [], "ظهرت بيانات بلا سياق مستأجر"


def test_context_is_transaction_local_and_does_not_leak(app_dsn):
    """
    السياق المضبوط بـ local=true ينتهي بانتهاء المعاملة.

    هذا ما يمنع توريث اتصالٍ مُعاد إلى المجمَّع سياقَ المستأجر السابق —
    وهو تسريبٌ يظهر تحت الحِمل وحده فيصعب تشخيصه.
    """
    c = psycopg2.connect(app_dsn)
    try:
        with c.cursor() as cur:
            cur.execute("SELECT set_config(%s, %s, true)", (TENANT_SETTING, A))
            cur.execute("SELECT current_setting(%s, true)", (TENANT_SETTING,))
            assert cur.fetchone()[0] == A
        c.commit()
        with c.cursor() as cur:
            cur.execute("SELECT current_setting(%s, true)", (TENANT_SETTING,))
            assert (cur.fetchone()[0] or "") == "", "تسرّب السياق بعد المعاملة"
    finally:
        c.close()
