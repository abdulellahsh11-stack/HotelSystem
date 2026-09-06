#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
tests/test_maintenance_stock.py — خصم مواد الصيانة من المستودع (البند ٧).

يفحص: تنقية السطور (معرّف موجب · كميّة موجبة · جمع المكرّر)، الخصم بلا
هبوطٍ تحت الصفر مع حركةٍ مسجّلة والعزل بالمنشأة، والسقوط الرشيق بلا
PostgreSQL، ونقطة /api/m08/orders/{id}/materials عبر HTTP (كسرٌ قبل
الوثوق: أمرٌ لمنشأةٍ أخرى يعود ٤٠٤).
"""
import os
import sys
from datetime import datetime

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from services import maintenance_stock as ms  # noqa: E402


class TestSanitizeLines:
    def test_keeps_only_valid(self):
        out = ms.sanitize_lines([
            {"item_id": 3, "qty": 2},
            {"item_id": 0, "qty": 5},      # معرّف غير موجب → يُسقَط
            {"item_id": 4, "qty": -1},     # كميّة سالبة → تُسقَط
            {"item_id": 5, "qty": 0},      # صفر → يُسقَط
            "junk",
        ])
        assert out == [{"item_id": 3, "qty": 2.0}]

    def test_merges_duplicates(self):
        out = ms.sanitize_lines([{"item_id": 3, "qty": 2}, {"item_id": 3, "qty": 1}])
        assert out == [{"item_id": 3, "qty": 3.0}]


class _FakeDB:
    use_postgres = True

    def __init__(self, remaining=7):
        self.calls = []
        self._remaining = remaining

    def execute(self, q, p=None, fetch=None):
        self.calls.append((q, p, fetch))
        if "UPDATE warehouse_items" in q:
            return {"id": p[1], "name": "فلتر", "quantity": self._remaining}
        return None


class TestConsume:
    def test_decrements_records_movement_and_isolates(self):
        db = _FakeDB(remaining=7)
        used = ms.consume(db, "h1", [{"item_id": 5, "qty": 3}], order_ref="MO-1")
        assert used == [{"item_id": 5, "name": "فلتر", "used": 3.0, "remaining": 7}]
        upd_q, upd_p, _ = db.calls[0]
        assert "UPDATE warehouse_items" in upd_q and "GREATEST" in upd_q     # لا سالب
        assert upd_p == (3.0, 5, "h1")                                       # عزل بالمنشأة
        assert "warehouse_movements" in db.calls[1][0]                       # حركة مسجّلة

    def test_missing_item_is_skipped(self):
        class NoRow(_FakeDB):
            def execute(self, q, p=None, fetch=None):
                self.calls.append((q, p, fetch))
                return None
        assert ms.consume(NoRow(), "h1", [{"item_id": 99, "qty": 1}]) == []

    def test_no_postgres_is_graceful(self):
        class Dev:
            use_postgres = False
        assert ms.consume(Dev(), "h1", [{"item_id": 1, "qty": 1}]) == []


try:
    from main import app, _client_sessions
    from app_core import _lock
    from fastapi.testclient import TestClient
    HAS_APP = True
except Exception:
    HAS_APP = False


class _OrderDB(_FakeDB):
    """يملك أمر صيانةٍ واحداً للمنشأة h1 فقط."""

    def execute(self, q, p=None, fetch=None):
        self.calls.append((q, p, fetch))
        if "SELECT order_number FROM maintenance_orders" in q:
            # p = (order_id, client_id) — الأمر ١ يخصّ h1 وحدها
            if p[0] == 1 and p[1] == "h1":
                return {"order_number": "MO-1"}
            return None
        if "UPDATE warehouse_items" in q:
            return {"id": p[1], "name": "فلتر", "quantity": 7}
        return None


@pytest.mark.skipif(not HAS_APP, reason="App not importable")
class TestUseMaterialsHTTP:
    def setup_method(self):
        with _lock:
            _client_sessions["own"] = {
                "client_id": "h1", "role": "owner",
                "permissions": ["*"], "created_at": datetime.now().isoformat(),
            }
        self._db = getattr(app.state, "db", None)
        app.state.db = _OrderDB()

    def teardown_method(self):
        app.state.db = self._db

    def _c(self):
        c = TestClient(app, raise_server_exceptions=False)
        c.cookies.set("client_token", "own")
        return c

    def test_consumes_for_own_order(self):
        r = self._c().post("/api/m08/orders/1/materials",
                           json={"materials": [{"item_id": 5, "qty": 3}]})
        assert r.status_code == 200
        assert r.json()["data"][0]["remaining"] == 7

    def test_unknown_order_is_404(self):
        r = self._c().post("/api/m08/orders/999/materials",
                           json={"materials": [{"item_id": 5, "qty": 3}]})
        assert r.status_code == 404
