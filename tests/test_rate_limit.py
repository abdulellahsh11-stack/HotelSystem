#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
tests/test_rate_limit.py — الحدُّ العامُّ لمعدّل طلبات الـ API.

يفحص طبقتين:
  ١) وحدة `services.rate_limit` نفسها — النافذة المنزلقة والسقف والتصفير.
  ٢) ربطها في `app_core` كـ middleware — الكتابة تُحدُّ، القراءة لا،
     والمسارات المستثناة لا يمسّها هذا الحدُّ، وكلُّ مستأجر بدلوه.
"""

import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from services import rate_limit  # noqa: E402


# ── الطبقة الأولى: وحدة الحدّ ────────────────────────────────────

class TestRateLimitModule:
    def setup_method(self):
        rate_limit.reset()

    def test_allows_up_to_limit_then_blocks(self):
        for i in range(5):
            assert rate_limit.check("k", 5) is True, f"الطلب {i} يجب أن يُقبل"
        assert rate_limit.check("k", 5) is False, "الطلب السادس يجب أن يُرفض"

    def test_zero_or_negative_limit_means_unlimited(self):
        for _ in range(1000):
            assert rate_limit.check("k", 0) is True
        assert rate_limit.check("k", -1) is True

    def test_keys_are_independent(self):
        assert rate_limit.check("a", 1) is True
        assert rate_limit.check("a", 1) is False
        # مفتاحٌ آخر لا يتأثّر بدلو الأوّل
        assert rate_limit.check("b", 1) is True

    def test_remaining_counts_down(self):
        assert rate_limit.remaining("k", 3) == 3
        rate_limit.check("k", 3)
        assert rate_limit.remaining("k", 3) == 2

    def test_reset_single_key(self):
        rate_limit.check("a", 1)
        rate_limit.check("b", 1)
        rate_limit.reset("a")
        assert rate_limit.check("a", 1) is True   # صُفّر
        assert rate_limit.check("b", 1) is False  # لم يُمسّ

    def test_reset_all(self):
        rate_limit.check("a", 1)
        rate_limit.reset()
        assert rate_limit.check("a", 1) is True

    def test_sliding_window_expires(self, monkeypatch):
        base = 1_000_000.0
        monkeypatch.setattr(rate_limit.time, "time", lambda: base)
        assert rate_limit.check("k", 1) is True
        assert rate_limit.check("k", 1) is False
        # بعد انقضاء النافذة يُقبل من جديد
        monkeypatch.setattr(rate_limit.time, "time",
                            lambda: base + rate_limit.WINDOW_SECONDS + 1)
        assert rate_limit.check("k", 1) is True

    def test_max_keys_cap_evicts_oldest(self, monkeypatch):
        monkeypatch.setattr(rate_limit, "MAX_KEYS", 10)
        for i in range(50):
            rate_limit.check(f"key-{i}", 100)
        # السقف «ليّن»: يُنظَّف عند الفحص فيبقى مفتاحٌ واحد أُضيف بعد آخر
        # تنظيف. المهم أن النمو محدود لا أن الرقم دقيق.
        assert rate_limit.stats()["keys"] <= rate_limit.MAX_KEYS + 1


# ── الطبقة الثانية: الربط في التطبيق ─────────────────────────────

try:
    from main import app, _client_sessions
    from fastapi.testclient import TestClient
    HAS_APP = True
except Exception:
    HAS_APP = False

app_required = pytest.mark.skipif(not HAS_APP, reason="App not importable")


@app_required
class TestRateLimitMiddleware:
    def setup_method(self):
        rate_limit.reset()

    def test_anonymous_writes_are_limited(self, monkeypatch):
        monkeypatch.setattr(rate_limit, "ANON_LIMIT", 3)
        client = TestClient(app, raise_server_exceptions=False)
        # أوّل ثلاث كتابات مجهولة تمرّ الحدّ (قد تُردّ 401 لاحقاً — المهم ليست 429)
        for _ in range(3):
            assert client.post("/api/m06/employees").status_code != 429
        # الرابعة تتجاوز الحدّ
        assert client.post("/api/m06/employees").status_code == 429

    def test_reads_are_not_limited(self, monkeypatch):
        monkeypatch.setattr(rate_limit, "ANON_LIMIT", 1)
        monkeypatch.setattr(rate_limit, "WRITE_LIMIT", 1)
        client = TestClient(app, raise_server_exceptions=False)
        for _ in range(10):
            assert client.get("/api/m06/employees").status_code != 429

    def test_exempt_login_path_not_limited_by_general_limiter(self, monkeypatch):
        monkeypatch.setattr(rate_limit, "ANON_LIMIT", 1)
        client = TestClient(app, raise_server_exceptions=False)
        # /api/login مستثنى: الحدُّ العامُّ لا يُصدر 429 عنه مهما تكرّر
        # (حدُّه الخاصُّ منفصلٌ وأضيق، لكنه ليس حدَّنا)
        for _ in range(5):
            assert client.post("/api/login", json={}).status_code != 429

    def test_tenants_have_separate_buckets(self, monkeypatch):
        monkeypatch.setattr(rate_limit, "WRITE_LIMIT", 2)
        # مستأجران بجلستين صالحتين (جلسةٌ بلا created_at تُرفَض فتُعامَل كمجهول)
        from datetime import datetime
        now_iso = datetime.now().isoformat()
        _client_sessions["tok-A"] = {"client_id": "hotel-A", "created_at": now_iso}
        _client_sessions["tok-B"] = {"client_id": "hotel-B", "created_at": now_iso}
        ca = TestClient(app, raise_server_exceptions=False)
        ca.cookies.set("client_token", "tok-A")
        cb = TestClient(app, raise_server_exceptions=False)
        cb.cookies.set("client_token", "tok-B")

        # A يستنفد دلوه
        assert ca.post("/api/m06/employees").status_code != 429
        assert ca.post("/api/m06/employees").status_code != 429
        assert ca.post("/api/m06/employees").status_code == 429
        # B غير متأثّر بدلو A
        assert cb.post("/api/m06/employees").status_code != 429
