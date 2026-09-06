#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
tests/test_hospitality.py — رحلة تسجيل الدخول: العقد + الضيافة (البند ٦).

يفحص: منطق الضيافة (الأصناف، التنقية، خطة الاستهلاك، بوّابة العقد)، الخصم
من المخزون (SQL بلا هبوطٍ تحت الصفر + حركة)، وبوّابة العقد عبر HTTP (كسرٌ
قبل الوثوق: لا دخول بلا توقيع، والدخول يُصيّر الحجز checked_in).
"""
import os
import sys
from datetime import datetime

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from services import hospitality as h  # noqa: E402


class TestHospitalityService:
    def test_default_consumables_cover_the_journey(self):
        keys = {c["key"] for c in h.get_consumables(None)}
        for expected in ("water", "sugar", "tea", "coffee", "pillowcase",
                         "mattress_cover", "towels", "duvet", "shampoo",
                         "cream", "hygiene"):
            assert expected in keys

    def test_custom_consumables_override(self):
        client = {"settings": {"hospitality_consumables":
                               [{"key": "water", "ar": "ماء", "en": "Water", "qty": 5}]}}
        c = h.get_consumables(client)
        assert c == [{"key": "water", "ar": "ماء", "en": "Water", "qty": 5}]

    def test_sanitize_drops_invalid(self):
        items = [{"key": "a", "qty": 2}, {"key": "", "qty": 1},
                 {"key": "b", "qty": -3}, {"key": "a", "qty": 9}, "junk"]
        out = h.sanitize(items)
        assert [x["key"] for x in out] == ["a"]      # الفارغ والسالب والمكرّر تُسقَط

    def test_plan_scales_by_nights_and_guests(self):
        cons = [{"key": "water", "ar": "علبة ماء", "en": "W", "qty": 1},
                {"key": "tea", "ar": "شاي", "en": "T", "qty": 2}]
        plan = h.plan_consumption(cons, nights=3, guests=2)
        assert plan == {"علبة ماء": 6, "شاي": 12}

    def test_can_check_in_requires_contract(self):
        assert h.can_check_in(True) is True
        assert h.can_check_in(False) is False
        assert h.can_check_in(None) is False


class _FakeDB:
    use_postgres = True

    def __init__(self):
        self.calls = []

    def execute(self, q, p=None, fetch=None):
        self.calls.append((q, p, fetch))
        if "UPDATE warehouse_items" in q:
            return {"id": 1, "quantity": 7}
        return None


class TestApplyConsumption:
    def test_decrements_and_records_movement(self):
        db = _FakeDB()
        consumed = h.apply_consumption(db, "h1", {"علبة ماء": 3})
        assert consumed == {"علبة ماء": 3}
        upd = db.calls[0][0]
        assert "UPDATE warehouse_items" in upd and "GREATEST" in upd  # لا سالب
        assert db.calls[0][1] == (3, "h1", "علبة ماء")                # عزل بالمنشأة
        assert "warehouse_movements" in db.calls[1][0]                # حركة مسجّلة

    def test_no_postgres_is_graceful(self):
        class Dev:
            use_postgres = False
        assert h.apply_consumption(Dev(), "h1", {"ماء": 3}) == {}


# ── بوّابة العقد عبر HTTP ──────────────────────────────────────
try:
    from main import app, _client_sessions
    from app_core import _lock
    from fastapi.testclient import TestClient
    HAS_APP = True
except Exception:
    HAS_APP = False


class _FakeStore:
    def __init__(self):
        self.bookings = {"bk1": {"id": "bk1", "status": "confirmed"}}
        self.saved = None

    def get_booking(self, cid, bid):
        return self.bookings.get(bid)

    def get_bookings(self, cid):
        return list(self.bookings.values())

    def save_booking(self, cid, booking):
        self.saved = dict(booking)
        self.bookings[booking["id"]] = self.saved
        return self.saved

    def get_client(self, cid):
        return {"id": cid, "settings": {}}


@pytest.mark.skipif(not HAS_APP, reason="App not importable")
class TestCheckinGate:
    def setup_method(self):
        with _lock:
            _client_sessions["own"] = {
                "client_id": "h1", "role": "owner",
                "permissions": ["*"], "created_at": datetime.now().isoformat(),
            }
        self._store, self._db = getattr(app.state, "store", None), getattr(app.state, "db", None)
        app.state.store = _FakeStore()

        class Dev:
            use_postgres = False
        app.state.db = Dev()

    def teardown_method(self):
        app.state.store, app.state.db = self._store, self._db

    def _c(self):
        c = TestClient(app, raise_server_exceptions=False)
        c.cookies.set("client_token", "own")
        return c

    def test_no_contract_blocks_checkin(self):
        r = self._c().post("/api/bookings/bk1/checkin", json={"contract_signed": False})
        assert r.status_code == 403

    def test_signed_contract_checks_in(self):
        r = self._c().post("/api/bookings/bk1/checkin", json={"contract_signed": True})
        assert r.status_code == 200
        assert r.json()["data"]["status"] == "checked_in"
        assert app.state.store.saved["status"] == "checked_in"   # الإشارة الخضراء

    def test_missing_booking_is_404(self):
        r = self._c().post("/api/bookings/nope/checkin", json={"contract_signed": True})
        assert r.status_code == 404
