#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
tests/test_checkin_cascade.py — الترابط المؤتمت بين التطبيقات

تسجيل وصولٍ واحد يجب أن يتسلسل: الحجز يصير مُسجَّلاً، والغرفة مشغولة،
والدفعة قيداً محاسبياً، والحدث سطراً في السجل، والإشغال رقماً محدَّثاً.

**يعمل على مخطط حقيقي بناه الترحيل، لا على جداول تكتبها الاختبارات.**
هذا شرطٌ لا تفصيل: العطل الذي كشفته هذه الاختبارات كان عموداً ناقصاً
(`bookings.booking_number`) تطلبه السلسلة بـ RETURNING. جدولٌ يكتبه
الاختبار بيده كان سيحوي العمود، فيمرّ الاختبار بينما الإنتاج يفشل في
كل تسجيل دخول.

ولأن السلسلة داخل معاملة واحدة، فشلُ أي خطوة يُرجع الجميع — فتبدو
المنصة وكأن الأزرار لا تفعل شيئاً.
"""
from __future__ import annotations

import os
import warnings
from datetime import date, datetime, timedelta

import pytest

warnings.filterwarnings("ignore")

psycopg2 = pytest.importorskip("psycopg2", reason="psycopg2 غير مثبّت")

ADMIN_DSN = os.environ.get("TEST_DATABASE_URL", "")
pytestmark = pytest.mark.skipif(
    not ADMIN_DSN, reason="TEST_DATABASE_URL غير مضبوط — لا خادم PostgreSQL"
)

TENANT = "cascade_hotel"
TEST_DB = "cascade_scratch"


def _dsn(dbname: str) -> str:
    from urllib.parse import urlsplit, urlunsplit

    if "://" in ADMIN_DSN:
        p = urlsplit(ADMIN_DSN)
        return urlunsplit((p.scheme, p.netloc, f"/{dbname}", p.query, p.fragment))
    fields = dict(t.split("=", 1) for t in ADMIN_DSN.split() if "=" in t)
    fields["dbname"] = dbname
    return " ".join(f"{k}={v}" for k, v in fields.items())


@pytest.fixture(scope="module")
def migrated_db():
    """قاعدة مستقلة يبنيها الترحيل الحقيقي — لا جداول يدوية."""
    import sys

    sys.path.insert(0, os.getcwd())

    admin = psycopg2.connect(ADMIN_DSN)
    admin.autocommit = True
    with admin.cursor() as c:
        c.execute(f"DROP DATABASE IF EXISTS {TEST_DB}")
        c.execute(f"CREATE DATABASE {TEST_DB}")

    dsn = _dsn(TEST_DB)
    from db.connection import DatabasePool

    pool = DatabasePool.__new__(DatabasePool)
    pool._initialized = True
    pool.database_url = dsn
    pool.use_postgres = True
    pool._json_path = "/tmp/unused.json"
    import threading

    pool._json_lock = threading.Lock()
    from db.connection import pg_pool

    pool._pool = pg_pool.ThreadedConnectionPool(1, 4, dsn)

    from db.migrations import run_all_migrations
    from db.schema_v3 import (
        run_sessions_migration, run_staff_app_migrations, run_v3_migrations,
    )

    for run in (run_all_migrations, run_v3_migrations,
                run_staff_app_migrations, run_sessions_migration):
        try:
            run(pool)
        except Exception:
            pass  # ترحيلات اختيارية قد تفشل جزئياً؛ ما يهمّ هو الجداول الأساسية

    yield pool

    pool._pool.closeall()
    with admin.cursor() as c:
        c.execute(f"DROP DATABASE IF EXISTS {TEST_DB}")
    admin.close()


@pytest.fixture
def app_client(migrated_db):
    from fastapi.testclient import TestClient

    from app_core import _client_sessions, _lock
    from main import app

    db = migrated_db
    # الترتيب مقصود: الجداول التابعة أولاً، وإلا رفض قيدُ المفتاح
    # الأجنبي حذفَ الحجوزات. `revenue_transactions` يُنشأ كسولاً عند
    # أول استدعاء تكامل، فقد لا يكون موجوداً في أول تشغيل.
    for table in ("check_in_log", "check_out_log", "revenue_transactions"):
        try:
            db.execute(f"DELETE FROM {table} WHERE client_id=%s", (TENANT,))
        except Exception:
            pass
    db.execute("DELETE FROM bookings WHERE client_id=%s", (TENANT,))
    db.execute("DELETE FROM rooms WHERE client_id=%s", (TENANT,))
    db.execute("DELETE FROM guests WHERE client_id=%s", (TENANT,))
    db.execute(
        "INSERT INTO clients(id,name) VALUES(%s,%s) ON CONFLICT (id) DO NOTHING",
        (TENANT, "فندق السلسلة"))
    db.execute(
        "INSERT INTO guests(client_id,full_name,id_number) VALUES(%s,%s,%s)",
        (TENANT, "سالم العتيبي", "1234567890"))
    db.execute(
        """INSERT INTO rooms(client_id,room_number,room_type,floor,capacity,
                             base_price,status)
           VALUES(%s,'101','suite',1,2,500,'available')""", (TENANT,))
    gid = db.execute("SELECT id FROM guests WHERE client_id=%s LIMIT 1",
                     (TENANT,), fetch="one")["id"]
    rid = db.execute("SELECT id FROM rooms WHERE client_id=%s LIMIT 1",
                     (TENANT,), fetch="one")["id"]
    db.execute(
        """INSERT INTO bookings(id,client_id,guest_id,room_id,check_in,check_out,
                                total_room,status)
           VALUES('BK-CASCADE',%s,%s,%s,%s,%s,500,'confirmed')""",
        (TENANT, gid, rid, date.today(), date.today() + timedelta(days=1)))

    app.state.db = db
    app.state.pricing = None
    app.state.channels = None

    class _Cfg:
        pass_salt = "s"
        admin_pass_hash = ""
        owner_client_id = ""

    app.state.cfg = _Cfg()
    with _lock:
        _client_sessions.clear()
        _client_sessions["tok"] = {
            "client_id": TENANT, "role": "owner", "permissions": ["*"],
            "created_at": datetime.now().isoformat(),
        }
    yield TestClient(app, raise_server_exceptions=False), db, rid
    with _lock:
        _client_sessions.clear()


COOKIE = {"client_token": "tok"}


def _checkin(client, **over):
    body = {"booking_id": "BK-CASCADE", "amount": 500,
            "payment_method": "mada", "deduct_amenities": False}
    body.update(over)
    return client.post("/api/integration/checkin", cookies=COOKIE, json=body)


def test_checkin_cascade_succeeds_on_a_real_schema(app_client):
    """
    الحارس الأهم: لو نقص عمودٌ تطلبه السلسلة، فشلت هنا بـ500 بدل أن
    تفشل صامتةً في الإنتاج.
    """
    client, _, _ = app_client
    r = _checkin(client)
    assert r.status_code == 200, f"فشلت السلسلة: {r.text[:300]}"


def test_the_room_becomes_occupied(app_client):
    client, db, rid = app_client
    assert _checkin(client).status_code == 200
    status = db.execute("SELECT status FROM rooms WHERE id=%s", (rid,),
                        fetch="one")["status"]
    assert status == "occupied", "الغرفة لم تصر مشغولة"


def test_the_booking_becomes_checked_in(app_client):
    client, db, _ = app_client
    assert _checkin(client).status_code == 200
    status = db.execute("SELECT status FROM bookings WHERE id='BK-CASCADE'",
                        fetch="one")["status"]
    assert status == "checked_in"


def test_the_payment_becomes_an_accounting_entry(app_client):
    client, db, _ = app_client
    assert _checkin(client).status_code == 200
    rows = db.execute(
        "SELECT amount, payment_method FROM revenue_transactions WHERE client_id=%s",
        (TENANT,), fetch="all") or []
    assert len(rows) == 1
    assert float(rows[0]["amount"]) == 500.0
    assert rows[0]["payment_method"] == "mada"


def test_the_event_is_logged(app_client):
    client, db, _ = app_client
    assert _checkin(client).status_code == 200
    n = db.execute("SELECT COUNT(*) AS n FROM check_in_log WHERE client_id=%s",
                   (TENANT,), fetch="one")["n"]
    assert n == 1


def test_occupancy_is_recomputed(app_client):
    client, _, _ = app_client
    cascade = _checkin(client).json()["cascade"]
    assert cascade["occupancy"]["occupied"] == 1
    assert cascade["occupancy"]["rate"] == 100.0
    assert cascade["kpi"]["check_ins_today"] == 1


def test_the_room_shows_as_occupied_through_the_rooms_api(app_client):
    """ما يراه المستخدم في خريطة الغرف يأتي من هنا."""
    client, _, _ = app_client
    assert _checkin(client).status_code == 200
    rooms = client.get("/api/rooms", cookies=COOKIE).json()["data"]
    assert [(r["room_number"], r["status"]) for r in rooms] == [("101", "occupied")]


def test_a_failed_cascade_changes_nothing(app_client):
    """
    السلسلة معاملةٌ واحدة: حجزٌ مجهول يُرفض ولا يترك أثراً جزئياً —
    لا غرفة مشغولة بلا حجز، ولا قيد إيراد بلا نزيل.
    """
    client, db, rid = app_client
    r = client.post("/api/integration/checkin", cookies=COOKIE,
                    json={"booking_id": "لا-يوجد", "amount": 500})
    assert r.status_code >= 400

    assert db.execute("SELECT status FROM rooms WHERE id=%s", (rid,),
                      fetch="one")["status"] == "available"
    n = db.execute("SELECT COUNT(*) AS n FROM revenue_transactions WHERE client_id=%s",
                   (TENANT,), fetch="one")["n"]
    assert n == 0


def test_checkout_returns_the_room_for_cleaning(app_client):
    client, db, rid = app_client
    assert _checkin(client).status_code == 200
    r = client.post("/api/integration/checkout", cookies=COOKIE,
                    json={"booking_id": "BK-CASCADE", "final_amount": 0})
    assert r.status_code == 200, r.text[:300]

    assert db.execute("SELECT status FROM rooms WHERE id=%s", (rid,),
                      fetch="one")["status"] == "cleaning"
    assert db.execute("SELECT status FROM bookings WHERE id='BK-CASCADE'",
                      fetch="one")["status"] == "checked_out"


def test_checking_in_twice_is_refused(app_client):
    """الحجز يخرج من حالة confirmed بعد أول تسجيل، فلا يتكرّر القيد."""
    client, db, _ = app_client
    assert _checkin(client).status_code == 200
    assert _checkin(client).status_code >= 400
    n = db.execute("SELECT COUNT(*) AS n FROM revenue_transactions WHERE client_id=%s",
                   (TENANT,), fetch="one")["n"]
    assert n == 1, "تكرّر قيد الإيراد"
