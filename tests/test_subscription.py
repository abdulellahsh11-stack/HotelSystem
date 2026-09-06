#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
tests/test_subscription.py — حالة الاشتراك والتنبيه ورسالة الدفع (البند ٣).

يفحص: تقييم الحالة (تنبيهٌ قبل القفل بـ٢٤ ساعة · القفل بعد الانتهاء · بلا
موعد)، تنقية رسالة الدفع ودمجها فوق الافتراضي، والنقاط عبر HTTP (الحالة ·
تخصيص الرسالة للمدير · منعها عن الموظف).
"""
import os
import sys
from datetime import datetime, timedelta, timezone

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from services import subscription as sub  # noqa: E402

_NOW = datetime(2026, 1, 30, 12, 0, tzinfo=timezone.utc)


class TestEvaluate:
    def test_alert_within_24h_before_lock(self):
        client = {"status": "trial",
                  "trial_end": (_NOW + timedelta(hours=20)).isoformat()}
        ev = sub.evaluate(client, now=_NOW)
        assert ev["alert"] is True and ev["locked"] is False
        assert ev["days_remaining"] == 0        # أقلّ من يوم

    def test_no_alert_when_far(self):
        client = {"status": "active",
                  "sub_end": (_NOW + timedelta(days=10)).isoformat()}
        ev = sub.evaluate(client, now=_NOW)
        assert ev["alert"] is False and ev["locked"] is False
        assert ev["days_remaining"] == 10

    def test_locked_after_end(self):
        client = {"status": "trial",
                  "trial_end": (_NOW - timedelta(hours=1)).isoformat()}
        ev = sub.evaluate(client, now=_NOW)
        assert ev["locked"] is True and ev["alert"] is False

    def test_bare_date_and_no_end(self):
        assert sub.evaluate({"trial_end": ""}, now=_NOW)["locked"] is False
        assert sub.evaluate({}, now=_NOW)["sub_end"] is None
        # تاريخٌ فقط (منتصف ليلته) — الغد يعني تنبيهاً
        ev = sub.evaluate({"trial_end": "2026-01-31"}, now=_NOW)
        assert ev["sub_end"] == "2026-01-31" and ev["alert"] is True


class TestPayment:
    def test_default_when_unset(self):
        p = sub.payment_instructions({})
        assert p["method"] == "bank_transfer" and p["message"]

    def test_custom_merges_over_default(self):
        client = {"settings": {"subscription_payment":
                               {"bank_name": "الراجحي", "iban": "SA00", "message": "حوّل هنا"}}}
        p = sub.payment_instructions(client)
        assert p["bank_name"] == "الراجحي" and p["iban"] == "SA00"
        assert p["message"] == "حوّل هنا"
        assert p["method"] == "bank_transfer"          # الافتراضي يبقى لغير المخصَّص

    def test_sanitize_drops_unknown(self):
        out = sub.sanitize_payment({"iban": "SA1", "evil": "x", "moyasar_link": "http://m"})
        assert out == {"iban": "SA1", "moyasar_link": "http://m"}


try:
    from main import app, _client_sessions
    from app_core import _lock
    from fastapi.testclient import TestClient
    HAS_APP = True
except Exception:
    HAS_APP = False


class _FakeStore:
    def __init__(self):
        soon = (datetime.now(timezone.utc) + timedelta(hours=12)).isoformat()
        self.client = {"id": "h1", "plan": "trial", "status": "trial",
                       "trial_end": soon, "settings": {"_account": {"pass_hash": "keep"}}}
        self.saved = None

    def get_client(self, cid):
        return self.client

    def save_client(self, client):
        self.saved = client
        self.client = client
        return client


@pytest.mark.skipif(not HAS_APP, reason="App not importable")
class TestSubscriptionHTTP:
    def _session(self, role="owner"):
        with _lock:
            _client_sessions["own"] = {
                "client_id": "h1", "role": role,
                "permissions": ["*"], "created_at": datetime.now().isoformat(),
            }

    def setup_method(self):
        self._session("owner")
        self._store = getattr(app.state, "store", None)
        app.state.store = _FakeStore()

    def teardown_method(self):
        app.state.store = self._store

    def _c(self):
        c = TestClient(app, raise_server_exceptions=False)
        c.cookies.set("client_token", "own")
        return c

    def test_status_flags_alert(self):
        r = self._c().get("/api/subscription/status")
        assert r.status_code == 200
        d = r.json()["data"]
        assert d["alert"] is True and d["locked"] is False
        assert d["payment"]["method"] == "bank_transfer"

    def test_manager_customizes_message_and_keeps_account(self):
        r = self._c().post("/api/subscription/payment-message",
                           json={"bank_name": "الأهلي", "message": "حوّل ثم راسلنا"})
        assert r.status_code == 200
        assert r.json()["data"]["bank_name"] == "الأهلي"
        # الحساب المخزَّن لم يُمسّ (مطبّ settings._account)
        assert app.state.store.saved["settings"]["_account"]["pass_hash"] == "keep"

    def test_staff_cannot_customize(self):
        self._session("reception")
        r = self._c().post("/api/subscription/payment-message",
                           json={"bank_name": "x"})
        assert r.status_code == 403
