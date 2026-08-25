#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
tests/test_booking_services.py — الإفطار والتوصيل

يثبت الربط المقصود: ما يسجّله الاستقبال على الحجز يظهر في قائمة
التشغيل اليومية من **نفس الصفوف** — لا نسخة ثانية تتناقض معه.

ويثبت أن الخدمات تخضع للعزل بين المنشآت كبقية البيانات.
"""
from __future__ import annotations

import warnings
from datetime import date, datetime, timedelta

import pytest
from fastapi.testclient import TestClient

warnings.filterwarnings("ignore")

from app_core import _client_sessions, _lock  # noqa: E402
from db.schema_services import SERVICE_TYPES  # noqa: E402
from main import app  # noqa: E402

A, B = "hotel_A", "hotel_B"
TODAY = date.today().isoformat()
TOMORROW = (date.today() + timedelta(days=1)).isoformat()


class ServicesDB:
    """قاعدة وهمية تُطبّق قيد التفرّد والعزل كما تفعل PostgreSQL."""

    use_postgres = True

    def __init__(self):
        self.services: list[dict] = []
        self.bookings = [
            {"id": "BK-1", "client_id": A, "room_id": 1, "guest_id": 1},
            {"id": "BK-B", "client_id": B, "room_id": 9, "guest_id": 9},
        ]
        self._next = 1

    def health(self):
        return {"ok": True}

    def execute(self, sql, params=(), fetch=None):
        s = " ".join(sql.split())
        low = s.lower()
        p = tuple(params or ())

        if low.startswith("select id from bookings"):
            bid, cid = p
            row = next((b for b in self.bookings
                        if b["id"] == bid and b["client_id"] == cid), None)
            return row

        if low.startswith("insert into booking_services"):
            cid, bid, stype, sdate = p[0], p[1], p[2], p[3]
            if any(x for x in self.services
                   if x["client_id"] == cid and x["booking_id"] == bid
                   and x["service_type"] == stype and x["service_date"] == sdate):
                raise Exception("duplicate key value violates unique constraint")
            self.services.append({
                "id": self._next, "client_id": cid, "booking_id": bid,
                "service_type": stype, "service_date": sdate, "quantity": p[4],
                "unit_price": p[5], "status": p[6], "destination": p[7],
                "scheduled_at": p[8], "notes": p[9], "created_by": p[10],
                "created_at": "2026-08-24",
            })
            self._next += 1
            return []

        if "from booking_services s" in low:          # القائمة اليومية
            cid, day = p
            rows = [dict(x) for x in self.services
                    if x["client_id"] == cid and x["service_date"] == day]
            for r in rows:
                bk = next((b for b in self.bookings if b["id"] == r["booking_id"]), {})
                r["room_number"] = f"R-{bk.get('room_id')}" if bk else None
                r["guest_name"] = "نزيل تجريبي" if bk else None
            return rows

        if "from booking_services where client_id=%s and booking_id=%s" in low:
            cid, bid = p
            return [dict(x) for x in self.services
                    if x["client_id"] == cid and x["booking_id"] == bid]

        if low.startswith("select id from booking_services"):
            sid, cid = p
            return next((x for x in self.services
                         if x["id"] == sid and x["client_id"] == cid), None)

        if low.startswith("update booking_services set status"):
            status, sid, cid = p
            for x in self.services:
                if x["id"] == sid and x["client_id"] == cid:
                    x["status"] = status
            return []

        if low.startswith("delete from booking_services"):
            sid, cid = p
            self.services = [x for x in self.services
                             if not (x["id"] == sid and x["client_id"] == cid)]
            return []
        return None if fetch == "one" else []


@pytest.fixture
def client():
    app.state.db = ServicesDB()
    with _lock:
        _client_sessions.clear()
        now = datetime.now().isoformat()
        _client_sessions["tokA"] = {"client_id": A, "role": "owner",
                                    "permissions": ["*"], "created_at": now}
        _client_sessions["tokB"] = {"client_id": B, "role": "owner",
                                    "permissions": ["*"], "created_at": now}
        _client_sessions["hk"] = {"client_id": A, "role": "housekeeping",
                                  "permissions": ["rooms.read", "housekeeping"],
                                  "created_at": now, "staff_id": 3}
    yield TestClient(app, raise_server_exceptions=False)
    with _lock:
        _client_sessions.clear()


AS_A = {"client_token": "tokA"}


def _add(client, **over):
    body = {"service_type": "breakfast", "service_date": TODAY,
            "quantity": 2, "unit_price": 35}
    body.update(over)
    return client.post("/api/bookings/BK-1/services", json=body, cookies=AS_A)


# ── التسجيل على الحجز ──────────────────────────────────────────
def test_reception_registers_breakfast_on_a_booking(client):
    assert _add(client).status_code == 200
    groups = client.get("/api/bookings/BK-1/services",
                        cookies=AS_A).json()["data"]["groups"]
    breakfast = next(g for g in groups if g["type"] == "breakfast")
    assert breakfast["count"] == 1
    assert breakfast["total"] == 70.0, "٢ × ٣٥ = ٧٠"
    assert breakfast["label"] == "الإفطار"


def test_both_service_types_are_always_returned_as_separate_groups(client):
    """
    الواجهة تعرض كل نوع في قسمٍ يُطوى وحده، فالمجموعتان تُعادان دائماً
    ولو كانت إحداهما فارغة — وإلا اختفى القسم بدل أن يظهر خالياً.
    """
    groups = client.get("/api/bookings/BK-1/services",
                        cookies=AS_A).json()["data"]["groups"]
    assert [g["type"] for g in groups] == list(SERVICE_TYPES)
    assert all(g["count"] == 0 for g in groups)


def test_the_same_service_twice_in_one_day_is_refused(client):
    """تكرارها يعني ازدواج فاتورة وازدواج تحضير في المطبخ."""
    assert _add(client).status_code == 200
    assert _add(client).status_code == 409


def test_the_same_service_on_another_day_is_allowed(client):
    assert _add(client).status_code == 200
    assert _add(client, service_date=TOMORROW).status_code == 200


@pytest.mark.parametrize("field,value", [
    ("service_type", "سبا"),          # نوع غير مدعوم
    ("service_date", "غداً"),          # تاريخ غير صالح
    ("quantity", 0),                  # كمية صفر
    ("quantity", 999),                # كمية خارج الحدّ
    ("unit_price", -5),               # سعر سالب
    ("status", "ربما"),               # حالة مجهولة
])
def test_invalid_input_is_refused(client, field, value):
    assert _add(client, **{field: value}).status_code == 400


def test_a_service_cannot_be_attached_to_a_missing_booking(client):
    r = client.post("/api/bookings/لا-يوجد/services", cookies=AS_A,
                    json={"service_type": "delivery", "service_date": TODAY})
    assert r.status_code == 404


# ── قائمة التشغيل اليومية — جوهر الربط ─────────────────────────
def test_what_reception_registers_appears_in_the_daily_list(client):
    """
    الربط المقصود: تسجيلٌ واحد على الحجز يظهر في قائمة المطبخ بلا
    إعادة إدخال.
    """
    _add(client, service_type="breakfast", quantity=3)
    _add(client, service_type="delivery", destination="المطار", quantity=1)

    data = client.get("/api/services/daily", cookies=AS_A).json()["data"]
    assert data["day"] == TODAY
    by_type = {g["type"]: g for g in data["groups"]}
    assert by_type["breakfast"]["quantity"] == 3
    assert by_type["delivery"]["count"] == 1
    assert by_type["delivery"]["items"][0]["destination"] == "المطار"


def test_the_daily_list_carries_the_room_number(client):
    """قائمةٌ تقول «إفطار ×٢» بلا غرفة لا تُنفَّذ."""
    _add(client)
    item = client.get("/api/services/daily",
                      cookies=AS_A).json()["data"]["groups"][0]["items"][0]
    assert item["room_number"] == "R-1"
    assert item["guest_name"]


def test_the_daily_list_only_shows_the_requested_day(client):
    _add(client, service_date=TODAY)
    _add(client, service_date=TOMORROW)
    today = client.get("/api/services/daily", cookies=AS_A).json()["data"]
    assert sum(g["count"] for g in today["groups"]) == 1

    tomorrow = client.get(f"/api/services/daily?day={TOMORROW}",
                          cookies=AS_A).json()["data"]
    assert tomorrow["day"] == TOMORROW
    assert sum(g["count"] for g in tomorrow["groups"]) == 1


def test_pending_count_drops_when_a_service_is_marked_done(client):
    _add(client)
    sid = app.state.db.services[0]["id"]
    before = client.get("/api/services/daily", cookies=AS_A).json()["data"]["groups"][0]
    assert before["pending"] == 1

    assert client.patch(f"/api/services/{sid}", json={"status": "done"},
                        cookies=AS_A).status_code == 200
    after = client.get("/api/services/daily", cookies=AS_A).json()["data"]["groups"][0]
    assert after["pending"] == 0


def test_an_invalid_day_is_refused(client):
    assert client.get("/api/services/daily?day=أمس", cookies=AS_A).status_code == 400


# ── العزل والصلاحيات ───────────────────────────────────────────
def test_services_of_another_tenant_are_invisible(client):
    _add(client)
    other = client.get("/api/services/daily", cookies={"client_token": "tokB"})
    assert sum(g["count"] for g in other.json()["data"]["groups"]) == 0


def test_another_tenant_cannot_change_or_delete_a_service(client):
    _add(client)
    sid = app.state.db.services[0]["id"]
    as_b = {"client_token": "tokB"}
    assert client.patch(f"/api/services/{sid}", json={"status": "cancelled"},
                        cookies=as_b).status_code == 404
    assert client.delete(f"/api/services/{sid}", cookies=as_b).status_code == 404
    assert app.state.db.services[0]["status"] == "pending", "تغيّرت خدمة منشأة أخرى"


def test_housekeeping_cannot_register_services(client):
    """الإشراف الداخلي لا يملك bookings.write."""
    r = client.post("/api/bookings/BK-1/services", cookies={"client_token": "hk"},
                    json={"service_type": "breakfast", "service_date": TODAY})
    assert r.status_code == 403
