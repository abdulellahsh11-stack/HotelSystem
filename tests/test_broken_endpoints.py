#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
tests/test_broken_endpoints.py — مسارات كانت تُعيد 500 في كل استدعاء.

ثلاث علل مستقلة كانت تُعطّل وظائف أساسية، ولم تكشفها مجموعة الاختبارات
لأنها لم تكن تستدعي أي مسار قائمة.

1. `count_result[0]` على صف RealDictCursor
   المؤشّر يُعيد قاموساً، فالفهرسة بالرقم 0 تبحث عن مفتاح اسمه 0 وترفع
   KeyError. النمط كان مكرراً في خمسة مواضع.

2. `bookings.booking_number` غير موجود في المخطط
   يشير إليه الكود في أربعة ملفات — إنشاء الحجز وتسجيل الوصول والمغادرة
   وقوائم الحجوزات والفواتير — والعمود لم يوجد قط.

3. `rooms.is_deleted` غير موجود
   محرك التسعير الديناميكي يُرشّح به في موضعين.

كل اختبار هنا يستدعي المسار فعلياً عبر TestClient: التحقق من الاستيراد
وحده كان سيمرّ رغم أن كل استدعاء يفشل.
"""

import os

import pytest

from db.passwords import hash_password
from db.rows import count_of, scalar

DATABASE_URL = os.environ.get("DATABASE_URL", "")
pytestmark = pytest.mark.skipif(not DATABASE_URL, reason="DATABASE_URL not set")

CLIENT_ID = "ep_test"
PASSWORD = "كلمة-اختبار-2026"


@pytest.fixture(scope="module")
def logged_in(test_client, db_pool):
    """منشأة مسجَّلة الدخول بغرفة ونزيل جاهزين."""
    store = test_client.app.state.store
    db_pool.execute("DELETE FROM clients WHERE id = %s", (CLIENT_ID,))
    store.save_client({
        "id": CLIENT_ID, "name": "فندق الاختبار",
        "pass_hash": hash_password(PASSWORD), "pass_salt": "",
        "status": "active", "plan": "pro",
    })
    resp = test_client.post(
        "/api/login", data={"client_id": CLIENT_ID, "password": PASSWORD},
        follow_redirects=False,
    )
    assert resp.status_code in (200, 302, 303), f"فشل تسجيل الدخول: {resp.status_code}"

    yield test_client

    db_pool.execute("DELETE FROM clients WHERE id = %s", (CLIENT_ID,))


# ── مساعد قراءة الصفوف ────────────────────────────────────────────────────────

def test_scalar_reads_dict_rows():
    """RealDictRow قاموس — الفهرسة بالرقم 0 تبحث عن مفتاح اسمه 0."""
    assert scalar({"count": 7}) == 7
    assert scalar({}) is None
    assert scalar(None, 0) == 0


def test_scalar_reads_indexed_rows():
    assert scalar((7,)) == 7
    assert scalar([7, 8]) == 7


def test_count_of_always_returns_int():
    assert count_of({"count": 5}) == 5
    assert count_of(None) == 0
    assert count_of({}) == 0
    assert count_of({"count": "12"}) == 12
    assert count_of({"count": None}) == 0


# ── مسارات القوائم ────────────────────────────────────────────────────────────

@pytest.mark.parametrize("path", [
    "/api/m06/employees",      # الموظفون
    "/api/m17/reservations",   # حجوزات القنوات
    "/api/m07/sales",          # مبيعات نقاط البيع
    "/api/m06acc/invoices",    # الفواتير المحاسبية
])
def test_list_endpoint_returns_200(logged_in, path):
    """كانت الأربعة تُعيد 500 في كل استدعاء."""
    resp = logged_in.get(path)
    assert resp.status_code == 200, f"{path} → {resp.status_code}: {resp.text[:200]}"
    body = resp.json()
    assert body.get("success") is True
    assert isinstance(body.get("total"), int), "حقل العدّ ليس رقماً"


# ── دورة الحجز ────────────────────────────────────────────────────────────────

def test_booking_can_be_created(logged_in, db_pool):
    """كان الإنشاء يفشل بـ «column booking_number does not exist»."""
    room_id = db_pool.execute(
        "INSERT INTO rooms (client_id, room_number, base_price, status) "
        "VALUES (%s, 'T-101', 400, 'available') RETURNING id", (CLIENT_ID,), fetch="one",
    )["id"]
    logged_in.app.state.store.save_guest(CLIENT_ID, {"full_name": "نزيل الاختبار"})
    guest_id = db_pool.execute(
        "SELECT id FROM guests WHERE client_id = %s LIMIT 1", (CLIENT_ID,), fetch="one",
    )["id"]

    resp = logged_in.post("/api/m17/reservations", json={
        "guest_id": guest_id, "room_id": room_id,
        "check_in": "2026-09-01", "check_out": "2026-09-03",
        "source": "direct", "total_room": 800,
    })
    assert resp.status_code == 200, f"{resp.status_code}: {resp.text[:200]}"
    number = resp.json()["data"].get("booking_number")
    assert number and number.startswith("BK-"), f"رقم الحجز مفقود: {number!r}"


def test_booking_number_column_exists_and_is_unique(db_pool):
    assert db_pool.execute(
        "SELECT COUNT(*) AS n FROM information_schema.columns "
        "WHERE table_name = 'bookings' AND column_name = 'booking_number'", fetch="one",
    )["n"] == 1
    assert db_pool.execute(
        "SELECT COUNT(*) AS n FROM pg_indexes "
        "WHERE tablename = 'bookings' AND indexname = 'uq_bookings_number'", fetch="one",
    )["n"] == 1


# ── محرك التسعير ──────────────────────────────────────────────────────────────

def test_pricing_engine_can_read_rooms(db_pool):
    """كان يفشل بـ «column r.is_deleted does not exist»."""
    from services.dynamic_pricing import DynamicPricingEngine
    rooms = DynamicPricingEngine(db_pool)._get_rooms_with_rules(CLIENT_ID)
    assert isinstance(rooms, list)


# ── حراسة ضد عودة النمط ───────────────────────────────────────────────────────

def test_no_positional_indexing_of_count_rows():
    """`row[0]` على صف RealDictCursor خطأ صامت في القراءة — يبدو صحيحاً
    لمن اعتاد صفوف psycopg2 العادية ولا يظهر إلا عند التشغيل."""
    import pathlib
    import re

    offenders = []
    pattern = re.compile(r'\bcount_\w*\[0\]')
    for path in pathlib.Path(__file__).parent.parent.glob("**/*.py"):
        if "test" in str(path) or "/.git" in str(path) or path.name == "rows.py":
            continue
        for i, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            if pattern.search(line):
                offenders.append(f"{path.name}:{i}")
    assert not offenders, f"استُخدمت الفهرسة بالرقم على صف نتيجة: {offenders}"
