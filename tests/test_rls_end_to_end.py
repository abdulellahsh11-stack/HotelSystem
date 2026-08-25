#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
tests/test_rls_end_to_end.py — الهيكلة الدائمة للعزل، من الطلب إلى الصفّ

`test_rls_isolation.py` يفحص السياسات في قاعدة البيانات مباشرةً. هذا
يفحص **السلسلة كاملة**: طلب HTTP ← جلسة ← ContextVar ← طبقة الاتصال ←
`set_config` داخل المعاملة ← سياسة RLS ← الصفوف المُعادة.

كل حلقة في السلسلة قابلة للكسر بصمت. أخطرها: خيطٌ لا ينقل ContextVar،
أو سياقٌ يُضبط في معاملة غير معاملة الاستعلام — وكلاهما يُنتج «صفر
صفوف» لا خطأً، فيبدو كأن البيانات ضاعت.

يحتاج PostgreSQL حقيقياً؛ بدونه يُتخطّى.
"""
from __future__ import annotations

import os
import warnings
from datetime import datetime

import pytest

warnings.filterwarnings("ignore")

psycopg2 = pytest.importorskip("psycopg2", reason="psycopg2 غير مثبّت")

ADMIN_DSN = os.environ.get("TEST_DATABASE_URL", "")
pytestmark = pytest.mark.skipif(
    not ADMIN_DSN, reason="TEST_DATABASE_URL غير مضبوط — لا خادم PostgreSQL"
)

A, B = "hotel_A", "hotel_B"
OWNER_ROLE, APP_ROLE = "e2e_owner", "e2e_app"
ROLE_PASSWORD = os.environ.get("TEST_APP_PASSWORD", "rls-test-only")
# قاعدة مستقلة تماماً عن قاعدة التطبيق — تُنشأ وتُحذف مع الوحدة
TEST_DB = "rls_e2e_scratch"


def _dsn_as(role: str, password: str = ROLE_PASSWORD, dbname: str = "") -> str:
    """
    يُعيد نفس عنوان الاتصال بمستخدمٍ آخر.

    يفهم الصيغتين: URL (`postgresql://user:pass@host/db`) و
    key=value (`host=… user=… dbname=…`).

    الاستبدال النصّي الساذج لا يكفي: عنوان CI مستخدمُه `dheuof` لا
    `postgres`، فيمرّ بلا تغيير وتعمل الاختبارات بمستخدمٍ مالك — أي
    تمرّ بلا أن تفحص شيئاً.
    """
    from urllib.parse import urlsplit, urlunsplit

    if "://" in ADMIN_DSN:
        parts = urlsplit(ADMIN_DSN)
        host = parts.hostname or "localhost"
        netloc = f"{role}:{password}@{host}"
        if parts.port:
            netloc += f":{parts.port}"
        path = f"/{dbname}" if dbname else parts.path
        return urlunsplit((parts.scheme, netloc, path, parts.query, parts.fragment))

    fields = {}
    for token in ADMIN_DSN.split():
        if "=" in token:
            key, _, value = token.partition("=")
            fields[key] = value
    fields["user"] = role
    fields["password"] = password
    if dbname:
        fields["dbname"] = dbname
    return " ".join(f"{k}={v}" for k, v in fields.items())


@pytest.fixture(scope="module")
def rls_db():
    """
    قاعدة بيانات **مستقلة** بجدول غرفٍ محمي بـ RLS ودورِ تطبيقٍ لا
    يتجاوزها.

    لماذا قاعدة منفصلة لا جدولٌ في القاعدة القائمة؟ لأن `TEST_DATABASE_URL`
    و`DATABASE_URL` يشيران إلى نفس القاعدة في CI. والاختبار يحتاج جدولاً
    اسمه `rooms` تحديداً (المسار `/api/rooms` يستعلم عنه)، فإنشاؤه هنا
    كان يعني حذف جدول التطبيق الحقيقي واستبداله — تدميرُ المخطط وسط
    التشغيل. أوقف ذلك خطأُ ملكيةٍ لا تصميمٌ سليم.
    """
    import sys

    sys.path.insert(0, os.getcwd())
    from db.rls import policy_sql

    adm = psycopg2.connect(ADMIN_DSN)
    adm.autocommit = True
    with adm.cursor() as c:
        c.execute(f"DROP DATABASE IF EXISTS {TEST_DB}")
        for role in (OWNER_ROLE, APP_ROLE):
            c.execute("SELECT 1 FROM pg_roles WHERE rolname=%s", (role,))
            if c.fetchone():
                c.execute(f"DROP OWNED BY {role} CASCADE")
                c.execute(f"DROP ROLE {role}")
        c.execute(f"CREATE ROLE {OWNER_ROLE} LOGIN PASSWORD %s NOSUPERUSER NOBYPASSRLS",
                  (ROLE_PASSWORD,))
        c.execute(f"CREATE ROLE {APP_ROLE} LOGIN PASSWORD %s NOSUPERUSER NOBYPASSRLS",
                  (ROLE_PASSWORD,))
        c.execute(f"CREATE DATABASE {TEST_DB} OWNER {OWNER_ROLE}")

    owner = psycopg2.connect(_dsn_as(OWNER_ROLE, dbname=TEST_DB))
    owner.autocommit = True
    with owner.cursor() as c:
        c.execute(f"GRANT USAGE ON SCHEMA public TO {APP_ROLE}")
        c.execute("""
            CREATE TABLE rooms(
                id SERIAL PRIMARY KEY, client_id VARCHAR(50) NOT NULL,
                room_number VARCHAR(20), room_type VARCHAR(100), floor INT,
                capacity INT, base_price NUMERIC(10,2), status VARCHAR(30), notes TEXT)
        """)
        c.execute(
            "INSERT INTO rooms(client_id,room_number,room_type,floor,capacity,"
            "base_price,status,notes) VALUES"
            "(%s,'A-101','standard',1,2,100,'available',''),"
            "(%s,'B-909','suite',9,4,900,'available','سرّ-ب')", (A, B))
        for stmt in policy_sql("rooms"):
            c.execute(stmt)
        c.execute(f"GRANT SELECT,INSERT,UPDATE,DELETE ON rooms TO {APP_ROLE}")
        c.execute(f"GRANT USAGE,SELECT ON SEQUENCE rooms_id_seq TO {APP_ROLE}")
    owner.close()

    yield _dsn_as(APP_ROLE, dbname=TEST_DB)

    with adm.cursor() as c:
        c.execute(f"DROP DATABASE IF EXISTS {TEST_DB}")
        for role in (APP_ROLE, OWNER_ROLE):
            c.execute("SELECT 1 FROM pg_roles WHERE rolname=%s", (role,))
            if c.fetchone():
                c.execute(f"DROP OWNED BY {role} CASCADE")
                c.execute(f"DROP ROLE {role}")
    adm.close()


@pytest.fixture
def client(rls_db, monkeypatch):
    from fastapi.testclient import TestClient

    monkeypatch.setenv("RLS_ENABLED", "1")
    import db.connection as conn_mod

    monkeypatch.setattr(conn_mod, "RLS_ENABLED", True)

    from app_core import _client_sessions, _lock
    from main import app

    pool = conn_mod.DatabasePool.__new__(conn_mod.DatabasePool)
    pool._initialized = True
    pool.database_url = rls_db
    pool.use_postgres = True
    pool._json_path = "/tmp/unused.json"
    import threading

    pool._json_lock = threading.Lock()
    pool._pool = conn_mod.pg_pool.ThreadedConnectionPool(1, 4, rls_db)

    app.state.db = pool
    app.state.pricing = None
    app.state.channels = None

    class _Cfg:
        pass_salt = "s"
        admin_pass_hash = ""
        owner_client_id = ""

    app.state.cfg = _Cfg()
    now = datetime.now().isoformat()
    with _lock:
        _client_sessions.clear()
        for token, cid in (("tokA", A), ("tokB", B)):
            _client_sessions[token] = {
                "client_id": cid, "role": "owner",
                "permissions": ["*"], "created_at": now,
            }
    yield TestClient(app, raise_server_exceptions=False)
    with _lock:
        _client_sessions.clear()
    pool._pool.closeall()


def _rooms(response) -> list[str]:
    return sorted(r["room_number"] for r in response.json().get("data", []))


def test_each_tenant_sees_only_its_own_rooms_through_http(client):
    """السلسلة كاملة: الجلسة تُحدّد ما تُعيده قاعدة البيانات."""
    assert _rooms(client.get("/api/rooms", cookies={"client_token": "tokA"})) == ["A-101"]
    assert _rooms(client.get("/api/rooms", cookies={"client_token": "tokB"})) == ["B-909"]


def test_the_database_isolates_even_a_query_that_forgot_its_filter(client):
    """
    جوهر الدفاع الثاني: استعلامٌ بلا شرط `client_id` إطلاقاً.

    في الطبقة الأولى وحدها كان هذا تسريباً كاملاً. مع RLS يُعيد صفوف
    المستأجر الجاري فقط.
    """
    from db.tenant_context import tenant_scope

    db = client.app.state.db
    with tenant_scope(A):
        rows = db.execute("SELECT room_number FROM rooms", fetch="all")
    assert [r["room_number"] for r in rows] == ["A-101"]

    with tenant_scope(B):
        rows = db.execute("SELECT room_number FROM rooms", fetch="all")
    assert [r["room_number"] for r in rows] == ["B-909"]


def test_no_tenant_context_returns_nothing(client):
    """فشل مغلق: بلا سياق لا بيانات — لا كل البيانات."""
    from db.tenant_context import clear_tenant

    clear_tenant()
    rows = client.app.state.db.execute("SELECT room_number FROM rooms", fetch="all")
    assert rows == [], "ظهرت صفوف بلا سياق مستأجر"


def test_writing_under_another_tenants_id_is_refused(client):
    from db.tenant_context import tenant_scope

    db = client.app.state.db
    with tenant_scope(A):
        with pytest.raises(psycopg2.errors.InsufficientPrivilege):
            db.execute(
                "INSERT INTO rooms(client_id,room_number) VALUES(%s,%s)", (B, "مدسوس"))


def test_deleting_another_tenants_room_reports_not_found(client):
    r = client.delete("/api/rooms/2", cookies={"client_token": "tokA"})
    assert r.status_code == 404
    from db.tenant_context import tenant_scope

    with tenant_scope(B):
        rows = client.app.state.db.execute("SELECT id FROM rooms", fetch="all")
    assert len(rows) == 1, "حُذفت غرفة منشأة أخرى"


def test_the_context_does_not_leak_between_requests(client):
    """
    اتصالٌ يُعاد إلى المجمَّع لا يورّث سياقه.

    هذا التسريب يظهر تحت الحِمل وحده: يقرأ مستأجرٌ بيانات من سبقه على
    نفس الاتصال. الترتيب هنا متعمَّد — طلبٌ لـ«أ» ثم «ب» ثم «أ».
    """
    for token, expected in (("tokA", ["A-101"]), ("tokB", ["B-909"]),
                            ("tokA", ["A-101"]), ("tokB", ["B-909"])):
        assert _rooms(client.get("/api/rooms", cookies={"client_token": token})) == expected


def test_platform_scope_sees_every_tenant(client):
    """مالك المنصة يعبر المنشآت — وهو النطاق الوحيد الذي يفعل."""
    from db.tenant_context import platform_scope

    with platform_scope():
        rows = client.app.state.db.execute("SELECT room_number FROM rooms", fetch="all")
    assert sorted(r["room_number"] for r in rows) == ["A-101", "B-909"]


def test_platform_scope_closes_after_the_block(client):
    """النطاق لا يبقى مفتوحاً على ما بعده."""
    from db.tenant_context import platform_scope, tenant_scope

    with platform_scope():
        pass
    with tenant_scope(A):
        rows = client.app.state.db.execute("SELECT room_number FROM rooms", fetch="all")
    assert [r["room_number"] for r in rows] == ["A-101"], "بقي نطاق المنصة مفتوحاً"


def test_platform_scope_closes_even_when_the_block_raises(client):
    from db.tenant_context import in_platform_scope, platform_scope

    with pytest.raises(RuntimeError):
        with platform_scope():
            raise RuntimeError("فشل متعمَّد")
    assert not in_platform_scope(), "بقي النطاق مفتوحاً بعد استثناء"
