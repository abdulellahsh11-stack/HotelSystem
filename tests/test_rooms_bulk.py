#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
tests/test_rooms_bulk.py — تسجيل الأدوار والغرف دفعةً واحدة

تسجيل أربعين غرفةً نموذجاً نموذجاً عملٌ يُهجَر في منتصفه، فتبقى المنصة
بلا غرف — ولا شيء فيها يعمل بلا غرف: لا خريطة ولا حجز ولا فاتورة.

ما يُثبَت هنا:
  ١ — الترقيم يتبع النمط الموصوف (دور × غرف × خانات)
  ٢ — الغرف القائمة تُتخطّى ولا تُستبدل: إعادة التشغيل آمنة
  ٣ — العزل: منشأة لا تُنشئ غرفاً في منشأة أخرى ولا ترى غرفها
  ٤ — المدخلات الفاسدة تُرفض في الخادم لا في المتصفّح وحده
"""
from __future__ import annotations

import warnings
from datetime import datetime

import pytest
from fastapi.testclient import TestClient

warnings.filterwarnings("ignore")

from app_core import _client_sessions, _lock  # noqa: E402
from main import app  # noqa: E402

A, B = "hotel_A", "hotel_B"


class RoomsDB:
    """قاعدة وهمية تُطبّق قيد UNIQUE(client_id, room_number) والعزل."""

    use_postgres = True

    def __init__(self):
        self.rooms: list[dict] = []
        self._next = 1

    def health(self):
        return {"ok": True}

    def execute(self, sql, params=(), fetch=None):
        low = " ".join(sql.split()).lower()
        p = tuple(params or ())

        if low.startswith("select room_number from rooms where client_id"):
            # العزل مطبَّق كما تفعل قاعدة البيانات: شرط WHERE كما كُتب
            return [{"room_number": r["room_number"]}
                    for r in self.rooms if r["client_id"] == p[0]]

        if low.startswith("insert into rooms"):
            cid, number = p[0], p[1]
            if any(r["client_id"] == cid and r["room_number"] == number
                   for r in self.rooms):
                raise Exception("duplicate key value violates unique constraint")
            self.rooms.append({
                "id": self._next, "client_id": cid, "room_number": number,
                "room_type": p[2], "floor": p[3], "capacity": p[4],
                "base_price": p[5], "status": "available", "notes": "",
            })
            self._next += 1
            return []

        return None if fetch == "one" else []


@pytest.fixture
def client():
    app.state.db = RoomsDB()

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
        _client_sessions["hk"] = {
            "client_id": A, "role": "housekeeping",
            "permissions": ["rooms.read"], "created_at": now,
        }
    yield TestClient(app, raise_server_exceptions=False)
    with _lock:
        _client_sessions.clear()


AS_A = {"client_token": "tokA"}


def _bulk(client, cookies=None, **over):
    body = {"floors": 3, "rooms_per_floor": 10, "first_floor": 1,
            "start_number": 1, "digits": 2, "room_type": "standard",
            "capacity": 2, "base_price": 400}
    body.update(over)
    return client.post("/api/rooms/bulk", json=body, cookies=cookies or AS_A)


# ── الترقيم ────────────────────────────────────────────────────
def test_it_creates_every_room_in_the_pattern(client):
    r = _bulk(client)
    assert r.status_code == 200, r.text[:300]
    assert r.json()["data"]["created_count"] == 30


def test_the_numbering_follows_floor_and_index(client):
    _bulk(client, floors=2, rooms_per_floor=3)
    numbers = [x["room_number"] for x in app.state.db.rooms]
    assert numbers == ["101", "102", "103", "201", "202", "203"], numbers


def test_three_digit_numbering_is_supported(client):
    """فندقٌ بأكثر من ٩٩ غرفةً في الدور يحتاج ثلاث خانات."""
    _bulk(client, floors=1, rooms_per_floor=3, digits=3)
    assert [x["room_number"] for x in app.state.db.rooms] == ["1001", "1002", "1003"]


def test_the_ground_floor_can_be_zero(client):
    _bulk(client, floors=1, rooms_per_floor=2, first_floor=0)
    assert [x["room_number"] for x in app.state.db.rooms] == ["001", "002"]


def test_the_starting_number_is_respected(client):
    _bulk(client, floors=1, rooms_per_floor=3, start_number=5)
    assert [x["room_number"] for x in app.state.db.rooms] == ["105", "106", "107"]


def test_the_type_and_price_reach_every_room(client):
    _bulk(client, floors=1, rooms_per_floor=2, room_type="suite", base_price=1500)
    assert all(x["room_type"] == "suite" for x in app.state.db.rooms)
    assert all(float(x["base_price"]) == 1500.0 for x in app.state.db.rooms)


# ── إعادة التشغيل ──────────────────────────────────────────────
def test_running_it_twice_creates_nothing_new(client):
    """
    إعادة التشغيل بعد إضافة دورٍ جديد يجب أن تكون آمنة. الاستبدال
    الصامت يمحو سعراً عُدّل يدوياً أو غرفةً عليها حجز.
    """
    _bulk(client, floors=1, rooms_per_floor=4)
    second = _bulk(client, floors=1, rooms_per_floor=4)
    data = second.json()["data"]
    assert data["created_count"] == 0
    assert data["skipped_count"] == 4
    assert len(app.state.db.rooms) == 4


def test_adding_a_floor_creates_only_the_new_rooms(client):
    _bulk(client, floors=1, rooms_per_floor=3)
    again = _bulk(client, floors=2, rooms_per_floor=3)
    assert again.json()["data"]["created_count"] == 3   # الدور الثاني وحده
    assert len(app.state.db.rooms) == 6


def test_an_existing_room_keeps_its_price(client):
    _bulk(client, floors=1, rooms_per_floor=1, base_price=400)
    _bulk(client, floors=1, rooms_per_floor=1, base_price=9999)
    assert float(app.state.db.rooms[0]["base_price"]) == 400.0


# ── العزل ──────────────────────────────────────────────────────
def test_each_tenant_gets_its_own_rooms(client):
    _bulk(client, cookies=AS_A, floors=1, rooms_per_floor=2)
    _bulk(client, cookies={"client_token": "tokB"}, floors=1, rooms_per_floor=2)
    assert len(app.state.db.rooms) == 4
    assert {r["client_id"] for r in app.state.db.rooms} == {A, B}


def test_the_same_number_in_another_tenant_is_not_a_conflict(client):
    """الغرفة ١٠١ في فندقين مختلفين غرفتان، لا تعارض."""
    _bulk(client, cookies=AS_A, floors=1, rooms_per_floor=1)
    other = _bulk(client, cookies={"client_token": "tokB"},
                  floors=1, rooms_per_floor=1)
    assert other.json()["data"]["created_count"] == 1


def test_it_requires_a_session(client):
    assert client.post("/api/rooms/bulk", json={"floors": 1}).status_code in (401, 403)


# ── المدخلات الفاسدة ───────────────────────────────────────────
@pytest.mark.parametrize("field,value", [
    ("floors", 0), ("floors", -3), ("floors", 999),
    ("rooms_per_floor", 0), ("rooms_per_floor", 500),
    ("digits", 0), ("digits", 9),
    ("capacity", 0), ("capacity", 99),
    ("start_number", 0),
])
def test_out_of_range_input_is_refused(client, field, value):
    assert _bulk(client, **{field: value}).status_code == 400
    assert app.state.db.rooms == []


@pytest.mark.parametrize("field", ["floors", "rooms_per_floor", "digits", "capacity"])
def test_non_numeric_input_is_refused(client, field):
    assert _bulk(client, **{field: "كثير"}).status_code == 400


def test_a_negative_price_is_refused(client):
    assert _bulk(client, base_price=-5).status_code == 400


def test_the_total_is_capped(client):
    """٥٠٠ غرفة حدٌّ يمنع طلباً واحداً من إشغال الخادم دقائق."""
    r = _bulk(client, floors=50, rooms_per_floor=100)
    assert r.status_code == 400
    assert "٥٠٠" in r.json()["error"]
