#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
tests/test_csrf_origin.py — حارس CSRF (فحص Origin/Referer).

الدفاع الأول ضد CSRF هو `samesite=lax` على الكوكي؛ هذا يفحص الطبقة الثانية:
طلب كتابةٍ يحمل كوكي جلسة من أصلٍ غير موثوق يُرفض ٤٠٣، بينما نفس المضيف
والأصول المسموحة وعملاء غير المتصفّح (بلا Origin) تمرّ.
"""
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    from main import app
    from fastapi.testclient import TestClient
    HAS_APP = True
except Exception:
    HAS_APP = False

pytestmark = pytest.mark.skipif(not HAS_APP, reason="App not importable")

AUTHED = {"client_token": "x-any-token"}          # وجود الكوكي وحده يُفعّل الحارس
WRITE = "/api/m06/employees"                        # مسار كتابة محميّ


def _c():
    return TestClient(app, raise_server_exceptions=False)


class TestCsrfOriginGuard:
    def test_cross_site_write_with_cookie_is_blocked(self):
        r = _c().post(WRITE, cookies=AUTHED, headers={"origin": "https://evil.example"})
        assert r.status_code == 403, f"أصلٌ غريب يجب أن يُرفض، عاد {r.status_code}"

    def test_cross_site_via_referer_is_blocked(self):
        r = _c().post(WRITE, cookies=AUTHED, headers={"referer": "https://evil.example/x"})
        assert r.status_code == 403

    def test_same_host_origin_passes_guard(self):
        # testserver هو مضيف TestClient — نفس الأصل يمرّ الحارس (قد يُردّ 401 لاحقاً)
        r = _c().post(WRITE, cookies=AUTHED, headers={"origin": "http://testserver"})
        assert r.status_code != 403

    def test_allowed_cors_origin_passes_guard(self):
        r = _c().post(WRITE, cookies=AUTHED, headers={"origin": "https://dheuof.com"})
        assert r.status_code != 403

    def test_no_origin_header_passes_guard(self):
        # عميل غير متصفّح (لا Origin ولا Referer) — ليس سطح خطر CSRF
        r = _c().post(WRITE, cookies=AUTHED)
        assert r.status_code != 403

    def test_anonymous_cross_site_is_not_guarded(self):
        # لا كوكي جلسة → لا شيء يُساء استخدامه → الحارس لا يُطبَّق
        r = _c().post(WRITE, headers={"origin": "https://evil.example"})
        assert r.status_code != 403

    def test_get_is_never_guarded(self):
        r = _c().get(WRITE, cookies=AUTHED, headers={"origin": "https://evil.example"})
        assert r.status_code != 403

    @pytest.mark.parametrize("method", ["POST", "PUT", "PATCH", "DELETE"])
    def test_all_write_methods_are_guarded(self, method):
        r = _c().request(method, WRITE, cookies=AUTHED,
                         headers={"origin": "https://evil.example"})
        assert r.status_code == 403, f"{method} من أصلٍ غريب يجب أن يُرفض"

    def test_uppercase_host_in_origin_is_accepted(self):
        # أسماء المضيفات لا تُميّز الحالة — أصلٌ مسموح بأحرف كبيرة يمرّ الحارس
        r = _c().post(WRITE, cookies=AUTHED, headers={"origin": "https://DHEUOF.com"})
        assert r.status_code != 403
