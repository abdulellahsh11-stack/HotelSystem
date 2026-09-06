#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
tests/test_payments.py — المحاسبة الفورية عند التسجيل (البند ٨).

يفحص: خدمة الدفعات (تطبيع الطريقة، رفض المبلغ ≤ صفر، شكل الإدراج)،
ونقطة /api/payments، وتسجيل الدفعة تلقائياً عند تسجيل الدخول.
"""
import os
import sys
from datetime import datetime

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from services import payments as pay  # noqa: E402


class _FakeDB:
    use_postgres = True

    def __init__(self):
        self.calls = []

    def execute(self, q, p=None, fetch=None):
        self.calls.append((q, p, fetch))
        if "INSERT INTO payments" in q:
            return {"id": 5, "amount": p[1], "method": p[2], "reference": p[3],
                    "created_at": "2026-01-01"}
        if "SELECT * FROM payments" in q:
            return [{"id": 5, "amount": 100.0, "method": "cash", "reference": "bk1"}]
        return None


class TestPaymentsService:
    def test_normalize_method(self):
        assert pay.normalize_method("POS") == "pos"
        assert pay.normalize_method("نقدي") == "cash"   # غير معروف → نقدي
        assert pay.normalize_method(None) == "cash"
        assert pay.normalize_method("cash") == "cash"

    def test_non_positive_amount_rejected(self):
        assert pay.record(_FakeDB(), "h1", 0, "cash") is None
        assert pay.record(_FakeDB(), "h1", -5, "cash") is None
        assert pay.record(_FakeDB(), "h1", "abc", "cash") is None

    def test_records_with_client_isolation(self):
        db = _FakeDB()
        rec = pay.record(db, "h1", 100, "POS", reference="bk1")
        assert rec["method"] == "pos" and rec["persisted"] is True
        q, p, _ = db.calls[0]
        assert "INSERT INTO payments" in q
        assert p[0] == "h1"                     # client_id
        assert p == ("h1", 100.0, "pos", "bk1")

    def test_dev_mode_graceful(self):
        class Dev:
            use_postgres = False
        rec = pay.record(Dev(), "h1", 50, "cash")
        assert rec["persisted"] is False and rec["amount"] == 50.0


try:
    from main import app, _client_sessions
    from app_core import _lock
    from fastapi.testclient import TestClient
    HAS_APP = True
except Exception:
    HAS_APP = False


@pytest.mark.skipif(not HAS_APP, reason="App not importable")
class TestPaymentsHTTP:
    def setup_method(self):
        with _lock:
            _client_sessions["own"] = {
                "client_id": "h1", "role": "owner",
                "permissions": ["*"], "created_at": datetime.now().isoformat(),
            }
        self._db = getattr(app.state, "db", None)
        app.state.db = _FakeDB()

    def teardown_method(self):
        app.state.db = self._db

    def _c(self):
        c = TestClient(app, raise_server_exceptions=False)
        c.cookies.set("client_token", "own")
        return c

    def test_post_records_payment(self):
        r = self._c().post("/api/payments",
                           json={"amount": 250, "method": "POS", "reference": "bk1"})
        assert r.status_code == 200
        assert r.json()["data"]["method"] == "pos"

    def test_zero_amount_is_400(self):
        r = self._c().post("/api/payments", json={"amount": 0, "method": "cash"})
        assert r.status_code == 400

    def test_list_payments(self):
        r = self._c().get("/api/payments")
        assert r.status_code == 200
        assert len(r.json()["data"]) == 1
