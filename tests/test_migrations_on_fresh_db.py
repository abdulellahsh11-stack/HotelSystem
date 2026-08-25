#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
tests/test_migrations_on_fresh_db.py — الترحيلات على قاعدة جديدة

يحرس صنفاً من الأخطاء لا تكشفه اختبارات القواعد الوهمية: ترحيلٌ يُعدّل
جدولاً **قبل** أن يُنشأ. على قاعدة قائمة يمرّ لأن الجدول موجود من قبل،
وعلى قاعدة جديدة يفشل بصمت — فيبدو التطبيق سليماً حتى أول نشرٍ نظيف.

وقع ذلك فعلاً: أعمدة هوية الجلسة كانت في ترحيل يسبق إنشاء
`client_sessions`، فلم تُضف أبداً — فلا تُحفظ جلسة ولا تُستعاد،
ويُطرد المستخدمون مع كل إعادة تشغيل.

يحتاج PostgreSQL حقيقياً؛ بدونه يُتخطّى.
"""
from __future__ import annotations

import os
import warnings

import pytest

warnings.filterwarnings("ignore")

psycopg2 = pytest.importorskip("psycopg2", reason="psycopg2 غير مثبّت")

ADMIN_DSN = os.environ.get("TEST_DATABASE_URL", "")
pytestmark = pytest.mark.skipif(
    not ADMIN_DSN, reason="TEST_DATABASE_URL غير مضبوط — لا خادم PostgreSQL"
)

FRESH_DB = "fresh_migrations_scratch"

# الأعمدة التي يعتمد عليها الكود صراحةً. غيابها لا يُسقط الاختبارات
# العادية لأنها تستعمل قواعد وهمية، لكنه يكسر الإنتاج.
REQUIRED_COLUMNS = {
    "client_sessions": ["token", "client_id", "expires_at",
                        "role", "staff_id", "username", "full_name", "permissions"],
    "bookings": ["id", "client_id", "guest_id", "room_id", "status", "booking_number"],
    "staff_users": ["id", "client_id", "username", "pass_hash", "pass_salt", "role"],
    "rooms": ["id", "client_id", "room_number", "floor", "status"],
    "clients": ["id", "name", "channel_secret"],
}


def _dsn(dbname: str) -> str:
    from urllib.parse import urlsplit, urlunsplit

    if "://" in ADMIN_DSN:
        p = urlsplit(ADMIN_DSN)
        return urlunsplit((p.scheme, p.netloc, f"/{dbname}", p.query, p.fragment))
    fields = dict(t.split("=", 1) for t in ADMIN_DSN.split() if "=" in t)
    fields["dbname"] = dbname
    return " ".join(f"{k}={v}" for k, v in fields.items())


@pytest.fixture(scope="module")
def fresh_db():
    """قاعدة فارغة تماماً تُبنى بالترحيلات وحدها — كأول نشرٍ نظيف."""
    import sys
    import threading

    sys.path.insert(0, os.getcwd())

    admin = psycopg2.connect(ADMIN_DSN)
    admin.autocommit = True
    with admin.cursor() as c:
        c.execute(f"DROP DATABASE IF EXISTS {FRESH_DB}")
        c.execute(f"CREATE DATABASE {FRESH_DB}")

    dsn = _dsn(FRESH_DB)
    from db.connection import DatabasePool, pg_pool

    pool = DatabasePool.__new__(DatabasePool)
    pool._initialized = True
    pool.database_url = dsn
    pool.use_postgres = True
    pool._json_path = "/tmp/unused.json"
    pool._json_lock = threading.Lock()
    pool._pool = pg_pool.ThreadedConnectionPool(1, 4, dsn)

    # نفس الترتيب الذي يُشغّله app_core عند الإقلاع — الترتيب هو
    # المقصود بالفحص، فتغييره هنا يُبطل الاختبار.
    from db.migrations import run_all_migrations
    from db.schema_services import run_services_migration
    from db.schema_v3 import (
        run_sessions_migration, run_staff_app_migrations,
        run_v3_migrations, run_v4_migrations,
    )

    for run in (run_all_migrations, run_v3_migrations, run_staff_app_migrations,
                run_services_migration, run_sessions_migration, run_v4_migrations):
        try:
            run(pool)
        except Exception:
            pass

    yield pool

    pool._pool.closeall()
    with admin.cursor() as c:
        c.execute(f"DROP DATABASE IF EXISTS {FRESH_DB}")
    admin.close()


def _columns(db, table: str) -> set[str]:
    rows = db.execute(
        "SELECT column_name FROM information_schema.columns WHERE table_name=%s",
        (table,), fetch="all") or []
    return {r["column_name"] for r in rows}


@pytest.mark.parametrize("table", sorted(REQUIRED_COLUMNS))
def test_required_columns_exist_after_a_fresh_migration(fresh_db, table):
    """
    عمودٌ ناقص هنا يعني مساراً يفشل في الإنتاج ولا يفشل في الاختبارات
    — لأن القواعد الوهمية تحوي ما يطلبه الكود دائماً.
    """
    present = _columns(fresh_db, table)
    assert present, f"الجدول {table} لم يُنشأ إطلاقاً"
    missing = [c for c in REQUIRED_COLUMNS[table] if c not in present]
    assert not missing, f"{table}: أعمدة ناقصة {missing}"


def test_the_session_table_can_hold_a_staff_identity(fresh_db):
    """
    الكتابة الفعلية لا وجود العمود وحده: نوعٌ خاطئ يمرّ من فحص الوجود
    ويفشل عند أول جلسة.
    """
    fresh_db.execute(
        """INSERT INTO client_sessions
               (token, client_id, expires_at, role, staff_id, username,
                full_name, permissions)
           VALUES ('tok-test', 'c1', NOW() + INTERVAL '1 day', 'receptionist',
                   7, 'sara', 'سارة', '["bookings.read"]')""")
    row = fresh_db.execute(
        "SELECT role, staff_id, permissions FROM client_sessions WHERE token='tok-test'",
        fetch="one")
    assert row["role"] == "receptionist"
    assert row["staff_id"] == 7
    assert "bookings.read" in row["permissions"]


def test_a_booking_can_hold_its_number(fresh_db):
    """العمود الذي كان غيابه يُفشل كل تسجيل دخول ومغادرة."""
    fresh_db.execute(
        "INSERT INTO clients(id,name) VALUES('c-mig','فندق') ON CONFLICT DO NOTHING")
    fresh_db.execute(
        """INSERT INTO bookings(id, client_id, check_in, check_out, status, booking_number)
           VALUES ('BK-MIG', 'c-mig', CURRENT_DATE, CURRENT_DATE + 1,
                   'confirmed', 'B-001')""")
    row = fresh_db.execute(
        "SELECT booking_number FROM bookings WHERE id='BK-MIG'", fetch="one")
    assert row["booking_number"] == "B-001"
