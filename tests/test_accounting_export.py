#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
tests/test_accounting_export.py — دفتر الأستاذ الموحّد وتصديره (البند ٤).

يفحص: بناء الدفتر (ربط الدفعة بجهازها · مقدار القيد من سطوره · الترتيب
الأحدث أولاً)، وسلامة CSV (تهريب الفواصل والاقتباس + BOM) عبر إعادة
تحليله، ونقطة /api/m06acc/export عبر HTTP (JSON و CSV).
"""
import csv
import io
import os
import sys
from datetime import datetime

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from services import accounting_export as ax  # noqa: E402

_PAYMENTS = [
    {"amount": 200, "method": "pos", "reference": "bk1", "device_id": 7,
     "currency": "SAR", "created_at": "2026-01-05T10:00:00"},
    {"amount": 100, "method": "cash", "reference": "bk2", "device_id": None,
     "currency": "SAR", "created_at": "2026-01-03T09:00:00"},
]
_JOURNALS = [
    {"reference": "INV-1", "entry_date": "2026-01-04", "description": 'إيراد، "شاليه"',
     "lines": [{"account": "نقد", "debit": 315, "credit": 0},
               {"account": "إيراد", "debit": 0, "credit": 315}],
     "source": "external", "created_at": "2026-01-04T00:00:00"},
]


class TestBuildLedger:
    def test_ties_payment_to_device_and_orders_desc(self):
        rows = ax.build_ledger(_PAYMENTS, _JOURNALS)
        assert [r["date"] for r in rows] == ["2026-01-05", "2026-01-04", "2026-01-03"]
        pos = rows[0]
        assert pos["kind"] == "payment" and pos["source"] == "pos_device:7"
        cash = [r for r in rows if r["reference"] == "bk2"][0]
        assert cash["source"] == "cash"

    def test_journal_amount_from_lines(self):
        rows = ax.build_ledger([], _JOURNALS)
        assert rows[0]["kind"] == "journal"
        assert rows[0]["amount"] == 315.0        # مجموع المدين
        assert rows[0]["source"] == "external"

    def test_empty_inputs(self):
        assert ax.build_ledger(None, None) == []


class TestCsv:
    def test_roundtrips_and_escapes(self):
        rows = ax.build_ledger(_PAYMENTS, _JOURNALS)
        text = ax.to_csv(rows)
        assert text.startswith("﻿")                      # BOM لإكسل
        parsed = list(csv.DictReader(io.StringIO(text.lstrip("﻿"))))
        assert parsed[0]["kind"] == "payment"                 # الرأس مقروء
        # الوصف فيه فاصلة واقتباس — يجب أن يعود سليماً بعد التحليل
        j = [r for r in parsed if r["kind"] == "journal"][0]
        assert j["description"] == 'إيراد، "شاليه"'
        assert j["amount"] == "315.0"

    def test_columns_are_stable(self):
        text = ax.to_csv([])
        header = text.lstrip("﻿").splitlines()[0]
        assert header == "date,kind,source,reference,description,method,amount,currency"


class _FakeDB:
    use_postgres = True

    def execute(self, q, p=None, fetch=None):
        if "FROM payments" in q:
            return _PAYMENTS
        if "FROM journal_entries" in q:
            return _JOURNALS
        return []


try:
    from main import app, _client_sessions
    from app_core import _lock
    from fastapi.testclient import TestClient
    HAS_APP = True
except Exception:
    HAS_APP = False


@pytest.mark.skipif(not HAS_APP, reason="App not importable")
class TestExportHTTP:
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

    def test_json_export(self):
        r = self._c().get("/api/m06acc/export?format=json")
        assert r.status_code == 200
        data = r.json()["data"]
        assert len(data) == 3 and data[0]["date"] == "2026-01-05"

    def test_csv_export(self):
        r = self._c().get("/api/m06acc/export")
        assert r.status_code == 200
        assert r.headers["content-type"].startswith("text/csv")
        assert r.text.startswith("﻿")
