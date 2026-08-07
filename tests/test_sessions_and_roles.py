#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
tests/test_sessions_and_roles.py — بقاء الجلسة عبر إعادة التشغيل، والدور.

علّتان كانتا تتفاعلان لتُخرجا المستخدمين من حساباتهم وتحجبا عنهم
عمليات هم أصحابها.

1. session_is_expired تعتبر كل جلسة مُستعادة منتهية
   الجلسة في الذاكرة تُخزَّن بطابع زمني بلا منطقة زمنية، والمُستعادة من
   PostgreSQL تحمل منطقة زمنية (TIMESTAMPTZ). وكان الطرح يتم دائماً
   مقابل datetime.now() المجرَّدة، فيرفع TypeError يُلتقط في except
   ويُعيد True. أي أن جدول client_sessions — الموجود أصلاً كي تبقى
   الجلسات بعد إعادة التشغيل — لم يكن يفي بغرضه إطلاقاً.

2. جلسة المنشأة بلا دور
   _require_manager في وحدتَي تدقيق الليل والتقييمات يُسقط الدور الغائب
   إلى "employee"، فكانت سبعة مسارات كتابة تُعيد 403 لمالك المنشأة
   نفسه — منها إعدادات تدقيق الليل وتشغيله.
"""

import os
from datetime import datetime, timedelta, timezone

import pytest

from db.passwords import hash_password
from db.security import SESSION_TTL_HOURS, session_is_expired

DATABASE_URL = os.environ.get("DATABASE_URL", "")
skip_no_db = pytest.mark.skipif(not DATABASE_URL, reason="DATABASE_URL not set")

CLIENT_ID = "sess_test"
PASSWORD = "كلمة-جلسة-2026"


# ── انتهاء الجلسة ─────────────────────────────────────────────────────────────

def test_naive_timestamp_not_expired():
    now = datetime.now().isoformat()
    assert session_is_expired({"created_at": now}) is False


def test_aware_timestamp_not_expired():
    """الطابع الآتي من TIMESTAMPTZ يحمل منطقة زمنية — كان يُعتبر منتهياً
    فوراً لأن طرحه من وقت مجرَّد يرفع TypeError."""
    now = datetime.now(timezone.utc).isoformat()
    assert session_is_expired({"created_at": now}) is False


def test_aware_timestamp_with_offset_not_expired():
    riyadh = timezone(timedelta(hours=3))
    now = datetime.now(riyadh).isoformat()
    assert session_is_expired({"created_at": now}) is False


def test_postgres_style_timestamp_not_expired():
    """الصيغة كما تعود من psycopg2 حرفياً."""
    riyadh = timezone(timedelta(hours=3))
    assert session_is_expired({"created_at": str(datetime.now(riyadh))}) is False


@pytest.mark.parametrize("tz", [None, timezone.utc, timezone(timedelta(hours=3))])
def test_old_session_is_expired(tz):
    """الانتهاء الحقيقي يجب أن يظل يعمل بعد الإصلاح."""
    old = datetime.now(tz) - timedelta(hours=SESSION_TTL_HOURS + 1)
    assert session_is_expired({"created_at": old.isoformat()}) is True


@pytest.mark.parametrize("value", [None, "", "ليس تاريخاً", "2026-13-45"])
def test_unreadable_timestamp_fails_closed(value):
    """أي قيمة لا تُقرأ تُبطل الجلسة — الفشل مغلقاً لا مفتوحاً."""
    assert session_is_expired({"created_at": value}) is True


def test_missing_key_fails_closed():
    assert session_is_expired({}) is True


# ── بقاء الجلسة والدور ────────────────────────────────────────────────────────

@pytest.fixture()
def logged_in(test_client, db_pool):
    store = test_client.app.state.store
    db_pool.execute("DELETE FROM clients WHERE id = %s", (CLIENT_ID,))
    store.save_client({
        "id": CLIENT_ID, "name": "فندق الجلسة",
        "pass_hash": hash_password(PASSWORD), "pass_salt": "",
        "status": "active", "plan": "pro",
    })
    resp = test_client.post(
        "/api/login", data={"client_id": CLIENT_ID, "password": PASSWORD},
        follow_redirects=False,
    )
    assert resp.status_code in (200, 302, 303)
    yield test_client
    db_pool.execute("DELETE FROM clients WHERE id = %s", (CLIENT_ID,))


def _simulate_restart():
    """يمسح الجلسات من الذاكرة فقط — كما يحدث عند إعادة تشغيل الخادم."""
    import main1
    with main1._lock:
        main1._client_sessions.clear()


@skip_no_db
def test_session_survives_restart(logged_in):
    """جدول client_sessions موجود لهذا الغرض تحديداً."""
    assert logged_in.get("/api/rooms").status_code == 200
    _simulate_restart()
    assert logged_in.get("/api/rooms").status_code == 200, \
        "الجلسة لم تنجُ من إعادة التشغيل — يخرج كل المستخدمين عند كل نشر"


@skip_no_db
def test_facility_session_carries_owner_role(logged_in):
    import main1
    session = next(iter(main1._client_sessions.values()))
    assert session.get("role") == "owner"
    assert "*" in session.get("permissions", [])


@skip_no_db
def test_restored_session_keeps_its_role(logged_in):
    """الجلسة المُستعادة من قاعدة البيانات يجب ألا تفقد صلاحياتها."""
    _simulate_restart()
    logged_in.get("/api/rooms")  # يُعيد بناء الجلسة من قاعدة البيانات
    import main1
    session = next(iter(main1._client_sessions.values()))
    assert session.get("role") == "owner", "الجلسة المُستعادة بلا دور"


@skip_no_db
@pytest.mark.parametrize("method,path,body", [
    ("PATCH", "/api/night-audit/settings", {"auto_run": True}),
    ("POST",  "/api/night-audit/run", {}),
])
def test_owner_can_reach_manager_endpoints(logged_in, method, path, body):
    """كانت تُعيد 403 لمالك المنشأة نفسه."""
    resp = logged_in.request(method, path, json=body)
    assert resp.status_code != 403, f"{path} محجوب عن المالك: {resp.text[:150]}"
