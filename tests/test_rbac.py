#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
tests/test_rbac.py — صلاحيات الموظفين وحراسة المسارات.

الحالة السابقة
──────────────
البنية كانت كاملة على الورق: ستة أدوار قياسية في staff_roles، وجدول
إسناد، ودالة app_has_perm في قاعدة البيانات، وcheck_permission و
enforce_permission في db/security.py — ولم تُستدعَ دالتا الحراسة ولا
مرة واحدة في المستودع كله.

وهوية الموظف كانت تُمرَّر نصاً في جسم الطلب (`staff_name`)، فينسب أي
مستخدم للمنشأة أي عملية لأي موظف. لا مصادقة ولا مساءلة.

النتيجة العملية: أي حساب في المنشأة يقرأ رواتب الجميع وأرقام هوياتهم.
"""

import os

import pytest

from db.passwords import hash_password
from services.permissions import has_permission

DATABASE_URL = os.environ.get("DATABASE_URL", "")
pytestmark = pytest.mark.skipif(not DATABASE_URL, reason="DATABASE_URL not set")

CLIENT_ID = "rbac_test"
OWNER_PASSWORD = "كلمة-مالك-2026"
STAFF_PASSWORD = "كلمة-موظف-2026"


# ── منطق مطابقة الصلاحية ──────────────────────────────────────────────────────

def test_wildcard_grants_everything():
    assert has_permission(["*"], "payroll") is True


def test_exact_match():
    assert has_permission(["payroll"], "payroll") is True


def test_unrelated_permission_is_denied():
    assert has_permission(["housekeeping"], "payroll") is False


def test_parent_permission_covers_child():
    """«rooms» تمنح «rooms.read» — التدرّج يمنع نسيان فرعٍ فيُترك مفتوحاً."""
    assert has_permission(["rooms"], "rooms.read") is True


def test_child_permission_does_not_cover_parent():
    """العكس ممنوع: من يملك القراءة فقط لا يملك الكتابة."""
    assert has_permission(["rooms.read"], "rooms") is False


def test_prefix_lookalike_is_not_a_match():
    """«room» ليست أباً لـ «rooms» — المطابقة على حدّ النقطة لا الحروف."""
    assert has_permission(["room"], "rooms") is False


@pytest.mark.parametrize("perms", [[], None])
def test_empty_permissions_deny(perms):
    assert has_permission(perms, "anything") is False


# ── التركيب الكامل ────────────────────────────────────────────────────────────

@pytest.fixture(scope="module")
def hotel(test_client, db_pool):
    """منشأة بموظفَين: عامل نظافة ومحاسب، لكلٍّ دوره."""
    from db.schema_v3 import run_app_role_migration, run_rls_migration
    run_app_role_migration(db_pool)
    os.environ["RLS_ENFORCE"] = "1"
    run_rls_migration(db_pool)

    store = test_client.app.state.store
    db_pool.execute("DELETE FROM clients WHERE id = %s", (CLIENT_ID,))
    store.save_client({
        "id": CLIENT_ID, "name": "فندق الصلاحيات",
        "pass_hash": hash_password(OWNER_PASSWORD), "pass_salt": "",
        "status": "active", "plan": "pro",
    })

    c = test_client

    def as_owner():
        c.cookies.clear()
        resp = c.post("/api/login",
                      data={"client_id": CLIENT_ID, "password": OWNER_PASSWORD},
                      follow_redirects=False)
        assert resp.status_code in (200, 302, 303)

    def as_staff(code):
        # الاختبارات تُبدّل الهوية عشرات المرات؛ عدّاد التخمين يُصفَّر كي
        # لا يخلط حدُّ المحاولات نتائجَ الحراسة (403) بحدّ المعدّل (429).
        import main1
        with main1._lock:
            main1._login_attempts.clear()
        c.cookies.clear()
        return c.post("/api/staff/login", json={
            "client_id": CLIENT_ID, "employee_id": code, "password": STAFF_PASSWORD,
        })

    as_owner()
    employees = {}
    for code, name, role in (("HK-1", "سعد", "housekeeper"),
                             ("AC-1", "نورة", "accountant")):
        emp = c.post("/api/m06/employees",
                     json={"full_name_ar": name, "employee_id": code}).json()["data"]
        employees[role] = emp
        assert c.post(f"/api/staff/accounts/{emp['id']}/password",
                      json={"password": STAFF_PASSWORD}).status_code == 200
        assert c.post(f"/api/staff/accounts/{emp['id']}/roles",
                      json={"role_code": role}).status_code == 200

    yield {"client": c, "as_owner": as_owner, "as_staff": as_staff,
           "employees": employees}

    db_pool.execute("DELETE FROM clients WHERE id = %s", (CLIENT_ID,))


# ── دخول الموظف ───────────────────────────────────────────────────────────────

def test_staff_can_log_in(hotel):
    resp = hotel["as_staff"]("HK-1")
    assert resp.status_code == 200, resp.text[:200]
    data = resp.json()["data"]
    assert data["roles"] == ["housekeeper"]
    assert "housekeeping" in data["permissions"]


def test_staff_login_rejects_wrong_password(hotel):
    c = hotel["client"]
    c.cookies.clear()
    resp = c.post("/api/staff/login", json={
        "client_id": CLIENT_ID, "employee_id": "HK-1", "password": "خاطئة",
    })
    assert resp.status_code == 401


def test_staff_login_does_not_reveal_which_field_was_wrong(hotel):
    """تمييز «لا يوجد موظف» عن «كلمة مرور خاطئة» يكشف الأرقام الوظيفية."""
    c = hotel["client"]
    c.cookies.clear()
    unknown = c.post("/api/staff/login", json={
        "client_id": CLIENT_ID, "employee_id": "لا-يوجد", "password": "x",
    })
    c.cookies.clear()
    wrong = c.post("/api/staff/login", json={
        "client_id": CLIENT_ID, "employee_id": "HK-1", "password": "خاطئة",
    })
    assert unknown.status_code == wrong.status_code == 401
    assert unknown.json()["error"] == wrong.json()["error"]


def test_staff_without_password_cannot_log_in(hotel, db_pool):
    """موظف أُنشئ ولم تُضبط له كلمة مرور لا يدخل."""
    c = hotel["client"]
    hotel["as_owner"]()
    emp = c.post("/api/m06/employees",
                 json={"full_name_ar": "بلا حساب", "employee_id": "NO-1"}).json()["data"]
    c.cookies.clear()
    resp = c.post("/api/staff/login", json={
        "client_id": CLIENT_ID, "employee_id": "NO-1", "password": STAFF_PASSWORD,
    })
    assert resp.status_code == 401
    assert emp["id"]


# ── الحراسة الفعلية ───────────────────────────────────────────────────────────

@pytest.mark.parametrize("path", [
    "/api/m06/payroll",              # رواتب
    "/api/m06/employees",            # بيانات زملائه وهوياتهم
    "/api/m06acc/revenue/summary",   # إيرادات المنشأة
])
def test_housekeeper_is_blocked_from_sensitive_data(hotel, path):
    """الاختبار الحاسم: عامل النظافة لا يقرأ رواتب زملائه."""
    hotel["as_staff"]("HK-1")
    assert hotel["client"].get(path).status_code == 403, f"{path} مفتوح لعامل النظافة"


def test_accountant_reaches_finance_but_not_hr(hotel):
    hotel["as_staff"]("AC-1")
    c = hotel["client"]
    assert c.get("/api/m06acc/revenue/summary").status_code != 403
    assert c.get("/api/m06/payroll").status_code == 403
    assert c.get("/api/m06/employees").status_code == 403


@pytest.mark.parametrize("path", [
    "/api/m06/payroll", "/api/m06/employees", "/api/m06acc/revenue/summary",
])
def test_owner_reaches_everything(hotel, path):
    hotel["as_owner"]()
    assert hotel["client"].get(path).status_code != 403


def test_denied_attempts_are_audited(hotel, db_pool):
    """محاولة وصول غير مصرَّح بها إشارة تحقيق تستحق التسجيل."""
    hotel["as_staff"]("HK-1")
    hotel["client"].get("/api/m06/payroll")
    n = db_pool.execute(
        "SELECT count(*) AS n FROM audit_log "
        "WHERE client_id = %s AND action = 'permission.denied'",
        (CLIENT_ID,), fetch="one",
    )["n"]
    assert n > 0, "الرفض لم يُسجَّل في سجل المراجعة"


# ── إدارة الأدوار ─────────────────────────────────────────────────────────────

def test_staff_cannot_grant_themselves_roles(hotel):
    """أخطر تصعيد ممكن: موظف يمنح نفسه دوراً أعلى."""
    hotel["as_staff"]("HK-1")
    emp_id = hotel["employees"]["housekeeper"]["id"]
    resp = hotel["client"].post(f"/api/staff/accounts/{emp_id}/roles",
                                json={"role_code": "owner"})
    assert resp.status_code == 403, "موظف رقّى نفسه!"


def test_staff_cannot_change_passwords(hotel):
    hotel["as_staff"]("HK-1")
    emp_id = hotel["employees"]["accountant"]["id"]
    resp = hotel["client"].post(f"/api/staff/accounts/{emp_id}/password",
                                json={"password": "اختراق-2026-طويلة"})
    assert resp.status_code == 403


def test_unknown_role_is_rejected(hotel):
    hotel["as_owner"]()
    emp_id = hotel["employees"]["housekeeper"]["id"]
    resp = hotel["client"].post(f"/api/staff/accounts/{emp_id}/roles",
                                json={"role_code": "دور_مخترَع"})
    assert resp.status_code == 422


def test_short_staff_password_is_rejected(hotel):
    hotel["as_owner"]()
    emp_id = hotel["employees"]["housekeeper"]["id"]
    resp = hotel["client"].post(f"/api/staff/accounts/{emp_id}/password",
                                json={"password": "قصيرة"})
    assert resp.status_code == 422


def test_revoking_a_role_removes_access(hotel):
    c = hotel["client"]
    emp_id = hotel["employees"]["accountant"]["id"]

    hotel["as_staff"]("AC-1")
    assert c.get("/api/m06acc/revenue/summary").status_code != 403

    hotel["as_owner"]()
    assert c.delete(f"/api/staff/accounts/{emp_id}/roles/accountant").status_code == 200

    # الدور الوحيد سُحب — لم يعد الدخول ممكناً أصلاً
    resp = hotel["as_staff"]("AC-1")
    assert resp.status_code == 401

    hotel["as_owner"]()
    c.post(f"/api/staff/accounts/{emp_id}/roles", json={"role_code": "accountant"})


# ── هوية المستخدم الحالي ──────────────────────────────────────────────────────

def test_me_reports_staff_identity(hotel):
    hotel["as_staff"]("HK-1")
    data = hotel["client"].get("/api/staff/me").json()["data"]
    assert data["employee_id"] == "HK-1"
    assert data["is_owner"] is False
    assert "housekeeping" in data["permissions"]


def test_me_reports_owner_identity(hotel):
    hotel["as_owner"]()
    data = hotel["client"].get("/api/staff/me").json()["data"]
    assert data["is_owner"] is True
    assert data["role"] == "owner"


# ── العلّة التي كشفها بناء هذه الميزة ─────────────────────────────────────────

def test_employee_can_be_updated(hotel):
    """المُشغّل trg_emp_updated يُسنِد NEW.updated_at والعمود لم يكن
    موجوداً — فكان كل UPDATE على employees يفشل، أي أن تعديل بيانات
    موظف وإنهاء خدمته معطَّلان."""
    hotel["as_owner"]()
    emp_id = hotel["employees"]["housekeeper"]["id"]
    resp = hotel["client"].put(f"/api/m06/employees/{emp_id}",
                               json={"full_name_ar": "سعد المطيري"})
    assert resp.status_code == 200, resp.text[:200]


def test_no_update_trigger_lacks_its_column(db_pool):
    """حارس عام: مُشغّل تحديث على جدول بلا updated_at يُفشل كل UPDATE."""
    rows = db_pool.execute(
        """
        SELECT DISTINCT t.event_object_table AS t
        FROM information_schema.triggers t
        WHERE t.action_statement LIKE '%%update_updated_at%%'
          AND NOT EXISTS (
              SELECT 1 FROM information_schema.columns c
              WHERE c.table_schema = 'public'
                AND c.table_name = t.event_object_table
                AND c.column_name = 'updated_at')
        """,
        fetch="all",
    ) or []
    assert not rows, f"جداول عليها مُشغّل تحديث بلا العمود: {[r['t'] for r in rows]}"
