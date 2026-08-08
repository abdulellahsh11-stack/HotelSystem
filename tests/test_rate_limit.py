#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
tests/test_rate_limit.py — تحديد معدّل الطلبات.

الحالة السابقة
──────────────
الحماية كانت على ثلاثة مسارات فقط: دخول المنشأة، وتسجيل منشأة جديدة،
ودخول المالك. وأكثر من مئة وستين مساراً بلا أي حدّ — فيستنزف حسابٌ
واحد مجمّعَ الاتصالات ويُعطّل المنصة على بقية المنشآت.

وعدّاد المحاولات كان قاموساً لا يُنظَّف: كل عنوان جديد يُضيف مفتاحاً
يبقى إلى الأبد، فمُهاجم يُدوّر العناوين يُنمّي القاموس حتى تنفد الذاكرة.
أداة الحماية من الإساءة كانت هي نفسها مساراً للإساءة.
"""

import os

import pytest

from db.passwords import hash_password
from services import rate_limit

DATABASE_URL = os.environ.get("DATABASE_URL", "")
skip_no_db = pytest.mark.skipif(not DATABASE_URL, reason="DATABASE_URL not set")

CLIENT_ID = "rl_test"
PASSWORD = "كلمة-حدّ-2026"


@pytest.fixture(autouse=True)
def _clean_buckets():
    rate_limit.reset()
    yield
    rate_limit.reset()


# ── منطق النافذة ──────────────────────────────────────────────────────────────

def test_requests_under_the_limit_pass():
    assert all(rate_limit.check("k", 5) for _ in range(5))


def test_request_over_the_limit_is_blocked():
    for _ in range(5):
        rate_limit.check("k", 5)
    assert rate_limit.check("k", 5) is False


def test_keys_are_independent():
    for _ in range(5):
        rate_limit.check("a", 5)
    assert rate_limit.check("a", 5) is False
    assert rate_limit.check("b", 5) is True


def test_zero_limit_means_unlimited():
    """صفر يعني تعطيل الحدّ لا منع كل شيء — الخلط بينهما يُسقط المنصة."""
    assert all(rate_limit.check("k", 0) for _ in range(200))


def test_remaining_counts_down():
    assert rate_limit.remaining("k", 5) == 5
    rate_limit.check("k", 5)
    assert rate_limit.remaining("k", 5) == 4


def test_reset_clears_a_single_key():
    for _ in range(5):
        rate_limit.check("a", 5)
    rate_limit.check("b", 5)
    rate_limit.reset("a")
    assert rate_limit.check("a", 5) is True
    assert rate_limit.remaining("b", 5) == 4


# ── حدّ الذاكرة ───────────────────────────────────────────────────────────────

def test_key_count_stays_bounded(monkeypatch):
    """مُهاجم يُدوّر العناوين لا يجوز أن يُنمّي الذاكرة بلا حدّ."""
    monkeypatch.setattr(rate_limit, "MAX_KEYS", 100)
    for i in range(2000):
        rate_limit.check(f"ip:{i}", 10)
    assert rate_limit.stats()["keys"] <= 100 + 64, "عدد المفاتيح تجاوز السقف"


def test_login_attempt_store_is_bounded(monkeypatch):
    """نفس العلّة في عدّاد محاولات الدخول."""
    import main1

    monkeypatch.setattr(main1, "_ATTEMPTS_MAX_KEYS", 50)
    with main1._lock:
        main1._login_attempts.clear()
    for i in range(1000):
        main1._login_rate_ok(f"ip-{i}")
    assert len(main1._login_attempts) <= 50 + 64, "قاموس المحاولات ينمو بلا حدّ"
    with main1._lock:
        main1._login_attempts.clear()


# ── التطبيق على المسارات ──────────────────────────────────────────────────────

@pytest.fixture()
def logged_in(test_client, db_pool):
    store = test_client.app.state.store
    db_pool.execute("DELETE FROM clients WHERE id = %s", (CLIENT_ID,))
    store.save_client({
        "id": CLIENT_ID, "name": "فندق الحدّ",
        "pass_hash": hash_password(PASSWORD), "pass_salt": "",
        "status": "active", "plan": "pro",
    })
    import main1
    with main1._lock:
        main1._login_attempts.clear()
    resp = test_client.post("/api/login",
                            data={"client_id": CLIENT_ID, "password": PASSWORD},
                            follow_redirects=False)
    assert resp.status_code in (200, 302, 303)
    rate_limit.reset()
    yield test_client
    db_pool.execute("DELETE FROM clients WHERE id = %s", (CLIENT_ID,))


@skip_no_db
def test_api_requests_are_limited(logged_in, monkeypatch):
    """مسار عادي — لا علاقة له بالدخول — يجب أن يخضع لحدّ."""
    monkeypatch.setattr(rate_limit, "READ_LIMIT", 5)
    rate_limit.reset()
    codes = [logged_in.get("/api/rooms").status_code for _ in range(8)]
    assert 429 in codes, f"لا حدّ على مسارات الـ API: {codes}"


@skip_no_db
def test_limit_response_tells_the_client_when_to_retry(logged_in, monkeypatch):
    monkeypatch.setattr(rate_limit, "READ_LIMIT", 2)
    rate_limit.reset()
    for _ in range(3):
        resp = logged_in.get("/api/rooms")
    assert resp.status_code == 429
    assert resp.headers.get("Retry-After") == "60"


@skip_no_db
def test_health_endpoint_is_never_limited(logged_in, monkeypatch):
    """فحص الصحة يستدعيه المُنسّق بتواتر عالٍ؛ حدّه يعني إعادة تشغيل
    الخدمة ظناً أنها ساقطة."""
    monkeypatch.setattr(rate_limit, "READ_LIMIT", 2)
    monkeypatch.setattr(rate_limit, "ANON_LIMIT", 2)
    rate_limit.reset()
    codes = [logged_in.get("/api/health").status_code for _ in range(10)]
    assert 429 not in codes, "فحص الصحة خاضع للحدّ"


@skip_no_db
def test_tenants_do_not_share_a_bucket(test_client, db_pool, monkeypatch):
    """المفتاح هو المنشأة لا العنوان: كل المنشآت في الاختبار خلف عنوان
    واحد، فالتحديد بالعنوان يجعل نشاط منشأة يخنق الأخرى."""
    monkeypatch.setattr(rate_limit, "READ_LIMIT", 4)
    rate_limit.reset()

    store = test_client.app.state.store
    import main1
    for tid in ("rl_a", "rl_b"):
        db_pool.execute("DELETE FROM clients WHERE id = %s", (tid,))
        store.save_client({"id": tid, "name": tid, "pass_hash": hash_password(PASSWORD),
                           "pass_salt": "", "status": "active", "plan": "pro"})

    def login(tid):
        with main1._lock:
            main1._login_attempts.clear()
        test_client.cookies.clear()
        test_client.post("/api/login", data={"client_id": tid, "password": PASSWORD},
                         follow_redirects=False)

    login("rl_a")
    for _ in range(5):
        test_client.get("/api/rooms")
    assert test_client.get("/api/rooms").status_code == 429

    login("rl_b")
    assert test_client.get("/api/rooms").status_code == 200, \
        "منشأة استنفدت حدّها فحجبت الأخرى"

    for tid in ("rl_a", "rl_b"):
        db_pool.execute("DELETE FROM clients WHERE id = %s", (tid,))
