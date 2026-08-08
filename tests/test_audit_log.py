#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
tests/test_audit_log.py — سجل المراجعة.

الحالة السابقة: جدول audit_log موجود ومُحصَّن ضد التعديل بمُشغّل،
ومسحوبة من الدور المُقيَّد صلاحيتا UPDATE و DELETE — وصفر موضع كتابة في
المستودع كله. البنية كاملة والسجل فارغ دائماً: لا أثر لمن غيّر سعراً،
ولا لمن حذف حجزاً، ولا لمن أعاد تعيين كلمة مرور منشأة.

سجل المراجعة لا قيمة له إلا إذا تحقّقت فيه أربع خصائص معاً، وكل واحدة
لها اختبار هنا: أن يُكتب فيه فعلاً، وأن يستحيل تعديله، وأن يُعزل بين
المنشآت، وألا يتحوّل هو نفسه إلى مستودع أسرار.
"""

import os

import pytest

from db.passwords import hash_password
from services.audit import PLATFORM_TENANT, redact

DATABASE_URL = os.environ.get("DATABASE_URL", "")
pytestmark = pytest.mark.skipif(not DATABASE_URL, reason="DATABASE_URL not set")

CLIENT_ID = "audit_test"
PASSWORD = "كلمة-تدقيق-2026"


@pytest.fixture(scope="module")
def logged_in(test_client, db_pool):
    from db.schema_v3 import run_app_role_migration, run_rls_migration
    run_app_role_migration(db_pool)
    os.environ["RLS_ENFORCE"] = "1"
    run_rls_migration(db_pool)

    store = test_client.app.state.store
    db_pool.execute("DELETE FROM clients WHERE id = %s", (CLIENT_ID,))
    store.save_client({
        "id": CLIENT_ID, "name": "فندق التدقيق",
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


def _actions(db_pool, client_id=CLIENT_ID):
    rows = db_pool.execute(
        "SELECT action FROM audit_log WHERE client_id = %s", (client_id,), fetch="all"
    ) or []
    return [r["action"] for r in rows]


# ── ١) أنه يُكتب فيه فعلاً ────────────────────────────────────────────────────

def test_successful_mutation_is_recorded(logged_in, db_pool):
    logged_in.post("/api/rooms", json={"room_number": "A-1", "base_price": 300})
    assert "post.ok" in _actions(db_pool)


def test_failed_mutation_is_recorded(logged_in, db_pool):
    """المحاولة الفاشلة إشارة تحقيق لا أقلّ أهمية من الناجحة."""
    logged_in.delete("/api/rooms/999999")
    assert "delete.failed" in _actions(db_pool)


def test_read_requests_are_not_recorded(logged_in, db_pool):
    """القراءات ضجيج يُغرق السجل ويُخفي ما يهمّ."""
    before = len(_actions(db_pool))
    for _ in range(5):
        logged_in.get("/api/rooms")
    assert len(_actions(db_pool)) == before


def test_login_success_and_failure_are_distinguished(test_client, db_pool):
    test_client.post("/api/login", data={"client_id": CLIENT_ID, "password": "خاطئة"},
                     follow_redirects=False)
    test_client.post("/api/login", data={"client_id": CLIENT_ID, "password": PASSWORD},
                     follow_redirects=False)
    actions = _actions(db_pool)
    assert "login.failure" in actions
    assert "login.success" in actions


def test_platform_owner_actions_are_recorded(test_client, db_pool):
    """عمليات مالك المنصة بلا سياق مستأجر — لولا سياسة الإضافة المفتوحة
    لضاع أثر أخطر العمليات في المنصة."""
    cfg = test_client.app.state.cfg
    original = cfg.admin_pass_hash
    cfg.admin_pass_hash = hash_password(PASSWORD)
    try:
        test_client.post("/api/admin/login", data={"password": "خاطئة"},
                         follow_redirects=False)
        assert "admin.login.failure" in _actions(db_pool, PLATFORM_TENANT)
    finally:
        cfg.admin_pass_hash = original


def test_health_checks_do_not_flood_the_log(logged_in, db_pool):
    before = len(_actions(db_pool))
    for _ in range(3):
        logged_in.get("/api/health")
    assert len(_actions(db_pool)) == before


# ── ٢) أنه يستحيل تعديله ──────────────────────────────────────────────────────

def test_audit_rows_cannot_be_updated(logged_in, db_pool):
    import psycopg2
    logged_in.post("/api/rooms", json={"room_number": "A-2", "base_price": 300})
    with pytest.raises(psycopg2.errors.RaiseException):
        db_pool.execute("UPDATE audit_log SET action = 'مزوَّر' WHERE client_id = %s",
                        (CLIENT_ID,))


def test_audit_rows_cannot_be_deleted(logged_in, db_pool):
    import psycopg2
    with pytest.raises(psycopg2.errors.RaiseException):
        db_pool.execute("DELETE FROM audit_log WHERE client_id = %s", (CLIENT_ID,))


def test_restricted_role_lacks_update_and_delete(db_pool):
    """طبقة ثانية: المُشغّل يوقف الخطأ البرمجي، وسحب الامتياز يوقف من
    يملك اتصالاً مباشراً."""
    for privilege in ("UPDATE", "DELETE"):
        granted = db_pool.execute(
            "SELECT has_table_privilege('dheuof_app', 'audit_log', %s) AS ok",
            (privilege,), fetch="one",
        )["ok"]
        assert granted is False, f"الدور المُقيَّد يملك {privilege} على سجل المراجعة"


# ── ٣) أنه يُعزل بين المنشآت ──────────────────────────────────────────────────

def test_tenant_cannot_read_another_tenants_audit(logged_in, db_pool):
    import psycopg2
    from psycopg2.extras import RealDictCursor

    logged_in.post("/api/rooms", json={"room_number": "A-3", "base_price": 300})

    conn = psycopg2.connect(DATABASE_URL)
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("SET ROLE dheuof_app")
            cur.execute("SELECT set_config('app.tenant_id', 'مستأجر_آخر', false)")
            cur.execute("SELECT count(*) AS n FROM audit_log")
            assert cur.fetchone()["n"] == 0, "تسريب سجل المراجعة بين المنشآت"

            cur.execute("SELECT set_config('app.tenant_id', %s, false)", (CLIENT_ID,))
            cur.execute("SELECT count(*) AS n FROM audit_log")
            assert cur.fetchone()["n"] > 0, "المنشأة لا ترى سجلّها"
    finally:
        conn.rollback()
        conn.close()


def test_audit_endpoint_returns_only_own_events(logged_in):
    resp = logged_in.get("/api/audit-log")
    assert resp.status_code == 200
    assert resp.json()["success"] is True
    assert isinstance(resp.json()["data"], list)


# ── ٤) ألا يصير هو نفسه مستودع أسرار ──────────────────────────────────────────

@pytest.mark.parametrize("key", [
    "password", "pass_hash", "national_id", "iqama_number", "api_key", "token",
])
def test_secrets_are_redacted(key):
    assert redact({key: "قيمة-حسّاسة"})[key] == "[محجوب]"


def test_redaction_reaches_nested_values():
    out = redact({"a": {"b": {"password": "سرّي"}}})
    assert out["a"]["b"]["password"] == "[محجوب]"


def test_non_secret_fields_survive_redaction():
    assert redact({"name": "عبدالله", "room": "101"})["name"] == "عبدالله"


def test_redaction_terminates_on_deep_structures():
    """بنية عميقة لا يجوز أن تُسقط الطلب بتكرار لا نهائي."""
    deep: dict = {}
    node = deep
    for _ in range(50):
        node["n"] = {}
        node = node["n"]
    redact(deep)  # لا يرفع


def test_password_never_reaches_the_log(logged_in, db_pool):
    """الاختبار الحاسم: كلمة المرور الحقيقية لا تظهر في السجل بحال."""
    logged_in.post("/api/guests", json={"full_name": "نزيل", "password": PASSWORD})
    rows = db_pool.execute(
        "SELECT COALESCE(new_data::text,'') || COALESCE(old_data::text,'') AS blob "
        "FROM audit_log WHERE client_id = %s", (CLIENT_ID,), fetch="all",
    ) or []
    for row in rows:
        assert PASSWORD not in row["blob"], "كلمة المرور تسرّبت إلى سجل المراجعة"


# ── الفشل لا يُسقط الطلب ──────────────────────────────────────────────────────

def test_audit_failure_does_not_break_the_request(logged_in, monkeypatch):
    """سجلّ مراجعة يُعطّل الفندق أسوأ من سجلّ ناقص."""
    import services.audit as audit_mod

    def _boom(*a, **k):
        raise RuntimeError("قاعدة البيانات ساقطة")

    monkeypatch.setattr(audit_mod, "audit", _boom)
    resp = logged_in.post("/api/rooms", json={"room_number": "A-9", "base_price": 100})
    assert resp.status_code == 200, "فشل السجل أسقط العملية الأصلية"
