#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
tests/test_staff_accounts.py — حسابات دخول الموظفين

يثبت أن الحسابات تعمل، وأن جلسة الموظف ترث العزل بين المنشآت، وأن
الصلاحيات تمنع فعلاً لا اسماً.
"""
from __future__ import annotations

import json
import warnings
from datetime import datetime

import pytest
from fastapi.testclient import TestClient

warnings.filterwarnings("ignore")

from app_core import _client_sessions, _lock, _login_attempts  # noqa: E402
from main import app  # noqa: E402


class FakeDB:
    """قاعدة بيانات في الذاكرة تكفي لمسارات حسابات الموظفين."""

    use_postgres = True

    def __init__(self):
        self.rows: list[dict] = []
        self._next_id = 1

    def health(self):
        return {"ok": True}

    def execute(self, sql, params=(), fetch=None):
        s = " ".join(sql.split())

        if s.startswith("INSERT INTO staff_users"):
            cid, username = params[0], params[1]
            if any(r["client_id"] == cid and r["username"] == username for r in self.rows):
                raise Exception("duplicate key value violates unique constraint")
            self.rows.append({
                "id": self._next_id, "client_id": cid, "username": username,
                "full_name": params[2], "pass_hash": params[3], "pass_salt": params[4],
                "role": params[5], "extra_perms": params[6], "employee_id": params[7],
                "is_active": True, "last_login": None, "created_at": "2026-08-10",
            })
            self._next_id += 1
            return []

        if "FROM staff_users WHERE client_id=%s AND username=%s" in s:
            cid, username = params
            return next((r for r in self.rows
                         if r["client_id"] == cid and r["username"] == username), None)

        if "FROM staff_users WHERE client_id=%s" in s:
            return [r for r in self.rows if r["client_id"] == params[0]]

        if "FROM staff_users WHERE id=%s AND client_id=%s" in s:
            rid, cid = params
            return next((r for r in self.rows
                         if r["id"] == rid and r["client_id"] == cid), None)

        if s.startswith("UPDATE staff_users SET") and "WHERE id=%s AND client_id=%s" in s:
            rid, cid = params[-2], params[-1]
            row = next((r for r in self.rows
                        if r["id"] == rid and r["client_id"] == cid), None)
            if row:
                fields = [p.split("=")[0].strip()
                          for p in s.split("SET", 1)[1].split("WHERE")[0].split(",")]
                for field, value in zip(fields, params[:-2]):
                    row[field] = value
            return []

        if s.startswith("DELETE FROM staff_users"):
            rid, cid = params
            self.rows = [r for r in self.rows
                         if not (r["id"] == rid and r["client_id"] == cid)]
            return []

        if s.startswith("UPDATE staff_users SET last_login"):
            return []
        return []


@pytest.fixture
def client():
    app.state.db = FakeDB()
    with _lock:
        _client_sessions.clear()
        # حدّ المحاولات (١٠/دقيقة/عنوان) مشترك بين الاختبارات وكلها من
        # نفس العنوان، فبلا تصفيره تفشل الاختبارات المتأخّرة بـ429 —
        # فشلٌ يعتمد على الترتيب لا على المنطق المُختبَر.
        _login_attempts.clear()
        now = datetime.now().isoformat()
        # الوقت الحالي لا ثابت: الجلسات تنتهي بعد ٨ ساعات، وطابعٌ ثابت
        # يجعل الاختبار ينجح صباحاً ويفشل مساءً.
        _client_sessions["owner-a"] = {
            "client_id": "hotel_A", "role": "owner", "permissions": ["*"],
            "created_at": now,
        }
        _client_sessions["owner-b"] = {
            "client_id": "hotel_B", "role": "owner", "permissions": ["*"],
            "created_at": now,
        }
    yield TestClient(app, raise_server_exceptions=False)
    with _lock:
        _client_sessions.clear()
        _login_attempts.clear()


OWNER = {"client_token": "owner-a"}


def _create(client, **over):
    body = {"username": "reception1", "full_name": "سارة",
            "role": "receptionist", "password": "كلمة-سر-طويلة"}
    body.update(over)
    return client.post("/api/staff/accounts", json=body, cookies=OWNER)


# ── الإنشاء ────────────────────────────────────────────────────
def test_owner_creates_a_staff_account(client):
    r = _create(client)
    assert r.status_code == 200, r.text
    assert r.json()["data"]["role"] == "receptionist"

    listed = client.get("/api/staff/accounts", cookies=OWNER).json()["data"]
    assert [a["username"] for a in listed] == ["reception1"]


def test_the_password_is_never_returned_or_stored_in_clear(client):
    _create(client, password="كلمة-سر-سرّية")
    assert "كلمة-سر-سرّية" not in client.get("/api/staff/accounts", cookies=OWNER).text
    stored = app.state.db.rows[0]
    assert "كلمة-سر-سرّية" not in stored["pass_hash"]
    assert stored["pass_hash"].startswith("pbkdf2_sha256$600000$")


@pytest.mark.parametrize("field,value,code", [
    ("username", "ab", 400),               # قصير
    ("username", "اسم-عربي", 400),          # محارف غير مسموحة
    ("role", "superadmin", 400),           # دور مجهول
    ("role", "owner", 400),                # لا يُسنَد من الواجهة
    ("password", "قصيرة", 400),             # أقل من ٨
    ("full_name", "", 400),                # بلا اسم
])
def test_invalid_input_is_rejected(client, field, value, code):
    assert _create(client, **{field: value}).status_code == code


def test_duplicate_username_within_the_same_hotel_is_rejected(client):
    assert _create(client).status_code == 200
    assert _create(client).status_code == 409


def test_the_same_username_is_allowed_in_a_different_hotel(client):
    assert _create(client).status_code == 200
    r = client.post("/api/staff/accounts",
                    json={"username": "reception1", "full_name": "أحمد",
                          "role": "receptionist", "password": "كلمة-سر-طويلة"},
                    cookies={"client_token": "owner-b"})
    assert r.status_code == 200, "اسم المستخدم فريد داخل المنشأة لا عبر المنصة"


# ── الدخول ─────────────────────────────────────────────────────
def test_staff_logs_in_and_receives_role_permissions(client):
    _create(client)
    r = client.post("/api/staff/login", json={
        "client_id": "hotel_A", "username": "reception1", "password": "كلمة-سر-طويلة"})
    assert r.status_code == 200, r.text
    data = r.json()["data"]
    assert data["role"] == "receptionist"
    assert "bookings.write" in data["permissions"]
    assert "hr" not in data["permissions"], "الاستقبال لا يرى الرواتب"
    assert "*" not in data["permissions"]


def test_wrong_password_and_unknown_user_give_the_same_answer(client):
    _create(client)
    wrong = client.post("/api/staff/login", json={
        "client_id": "hotel_A", "username": "reception1", "password": "خاطئة-جداً"})
    unknown = client.post("/api/staff/login", json={
        "client_id": "hotel_A", "username": "لا-أحد", "password": "خاطئة-جداً"})
    assert wrong.status_code == unknown.status_code == 401
    assert wrong.json() == unknown.json(), "الفرق يكشف أي الحسابات موجودة"


def test_a_deactivated_account_cannot_log_in(client):
    """
    الحساب المُوقَف يُرفض بنفس ردّ أي فشل آخر.

    ردٌّ مميّز («الحساب مُوقَف») يُخبر المهاجم أن اسم المستخدم صحيح
    وكلمة المرور صحيحة أيضاً — وهو أكثر مما يكشفه أي خطأ آخر.
    """
    _create(client)
    account_id = app.state.db.rows[0]["id"]
    assert client.patch(f"/api/staff/accounts/{account_id}",
                        json={"is_active": False}, cookies=OWNER).status_code == 200

    disabled = client.post("/api/staff/login", json={
        "client_id": "hotel_A", "username": "reception1", "password": "كلمة-سر-طويلة"})
    unknown = client.post("/api/staff/login", json={
        "client_id": "hotel_A", "username": "لا-أحد", "password": "أياً-كانت"})
    assert disabled.status_code == 401
    assert disabled.json() == unknown.json(), "الردّ يميّز الحساب المُوقَف"


def test_staff_of_one_hotel_cannot_log_into_another(client):
    _create(client)
    r = client.post("/api/staff/login", json={
        "client_id": "hotel_B", "username": "reception1", "password": "كلمة-سر-طويلة"})
    assert r.status_code == 401


# ── الصلاحيات ──────────────────────────────────────────────────
def test_a_receptionist_cannot_manage_staff_accounts(client):
    """الحرج: الموظف لا يرقّي نفسه ولا ينشئ حسابات."""
    _create(client)
    login = client.post("/api/staff/login", json={
        "client_id": "hotel_A", "username": "reception1", "password": "كلمة-سر-طويلة"})
    token = login.cookies.get("client_token")
    assert token

    staff_cookie = {"client_token": token}
    assert client.get("/api/staff/accounts", cookies=staff_cookie).status_code == 403
    assert client.post("/api/staff/accounts",
                       json={"username": "x2", "full_name": "س", "role": "gm",
                             "password": "كلمة-سر-طويلة"},
                       cookies=staff_cookie).status_code == 403


def test_a_receptionist_cannot_download_the_backup(client):
    """النسخة تحوي الرواتب وأرقام الهوية — سياسة الوصول تسري على الموظف."""
    _create(client)
    login = client.post("/api/staff/login", json={
        "client_id": "hotel_A", "username": "reception1", "password": "كلمة-سر-طويلة"})
    r = client.get("/api/backup/download",
                   cookies={"client_token": login.cookies.get("client_token")})
    assert r.status_code == 403


def test_the_staff_session_carries_the_tenant_id(client):
    """جلسة الموظف تحمل client_id، فيسري عليها العزل كجلسة المالك."""
    _create(client)
    login = client.post("/api/staff/login", json={
        "client_id": "hotel_A", "username": "reception1", "password": "كلمة-سر-طويلة"})
    me = client.get("/api/staff/me",
                    cookies={"client_token": login.cookies.get("client_token")}).json()["data"]
    assert me["client_id"] == "hotel_A"
    assert me["is_owner"] is False


# ── الإدارة ────────────────────────────────────────────────────
def test_deactivating_an_account_kills_its_live_session(client):
    """الإيقاف يقطع الجلسة فوراً — وإلا عمل المُوقَف حتى انتهائها."""
    _create(client)
    login = client.post("/api/staff/login", json={
        "client_id": "hotel_A", "username": "reception1", "password": "كلمة-سر-طويلة"})
    token = login.cookies.get("client_token")
    assert client.get("/api/staff/me", cookies={"client_token": token}).status_code == 200

    client.patch(f"/api/staff/accounts/{app.state.db.rows[0]['id']}",
                 json={"is_active": False}, cookies=OWNER)
    assert client.get("/api/staff/me", cookies={"client_token": token}).status_code == 401


def test_owner_cannot_touch_another_hotels_account(client):
    _create(client)
    account_id = app.state.db.rows[0]["id"]
    other = {"client_token": "owner-b"}
    assert client.patch(f"/api/staff/accounts/{account_id}",
                        json={"full_name": "مُخترَق"}, cookies=other).status_code == 404
    assert app.state.db.rows[0]["full_name"] == "سارة"


def test_password_reset_invalidates_the_old_password(client):
    _create(client)
    account_id = app.state.db.rows[0]["id"]
    assert client.post(f"/api/staff/accounts/{account_id}/reset-password",
                       json={"password": "كلمة-جديدة-طويلة"}, cookies=OWNER).status_code == 200

    old = client.post("/api/staff/login", json={
        "client_id": "hotel_A", "username": "reception1", "password": "كلمة-سر-طويلة"})
    assert old.status_code == 401
    new = client.post("/api/staff/login", json={
        "client_id": "hotel_A", "username": "reception1", "password": "كلمة-جديدة-طويلة"})
    assert new.status_code == 200


def test_roles_endpoint_hides_the_owner_role(client):
    roles = client.get("/api/staff/roles", cookies=OWNER).json()["data"]["roles"]
    assert "owner" not in [r["value"] for r in roles]
    assert "receptionist" in [r["value"] for r in roles]


def test_extra_permissions_must_be_known(client):
    """صلاحية مجهولة تُسقط بدل أن تُخزَّن وتُمنح لاحقاً بالخطأ."""
    from services.staff_roles import permissions_for

    perms = permissions_for("receptionist", ["hr", "لا-توجد-هذه"])
    assert "hr" in perms
    assert "لا-توجد-هذه" not in perms


def test_stored_extra_perms_are_applied_on_login(client):
    _create(client, extra_permissions=["reports"])
    login = client.post("/api/staff/login", json={
        "client_id": "hotel_A", "username": "reception1", "password": "كلمة-سر-طويلة"})
    assert "reports" in login.json()["data"]["permissions"]
    assert json.loads(app.state.db.rows[0]["extra_perms"]) == ["reports"]


class TestStaffLoginPageExists:
    """
    الباب الذي لم يكن موجوداً.

    `POST /api/staff/login` مبنيٌّ ويعمل ومُختبَر — ولم تكن **أي شاشة**
    تستدعيه. فمن يُنشئ حساب مدير عام أو موظف استقبال يسلّمه بيانات دخولٍ
    لبابٍ غير مرسوم.

    كشفه سؤال المستخدم «كيف الدخول على حساب مدير المنشأة؟» — لا فحصٌ
    للكود: المسار موجود، والاختبارات تمرّ، والميزة معطّلة عملياً.
    """

    def test_the_staff_login_page_exists(self):
        import os
        assert os.path.exists("static/dheuof/staff-login.html"), \
            "لا صفحة دخولٍ للموظفين — الحسابات تُنشأ بلا باب"

    def test_the_page_calls_the_real_endpoint(self):
        html = open("static/dheuof/staff-login.html", encoding="utf-8").read()
        assert "/api/staff/login" in html
        for field in ("client_id", "username", "password"):
            assert field in html, f"الحقل {field} مفقود من النموذج"

    def test_the_page_is_public(self):
        """صفحة دخولٍ محجوبةٌ خلف الدخول تناقض نفسها."""
        from app_core import _is_protected_page
        assert not _is_protected_page("/static/dheuof/staff-login.html")

    def test_the_main_login_page_links_to_it(self):
        """بابٌ لا يُشار إليه كبابٍ غير موجود — وهذا ما وقع."""
        src = open("html_pages.py", encoding="utf-8").read()
        assert "staff-login.html" in src, "صفحة الدخول الرئيسية لا تشير إليها"

    def test_the_page_never_stores_credentials(self):
        """رقم المنشأة يُحفظ للتيسير؛ الاسم وكلمة المرور لا يُحفظان أبداً."""
        html = open("static/dheuof/staff-login.html", encoding="utf-8").read()
        import re
        for m in re.finditer(r"localStorage\.setItem\(\s*'([^']+)'", html):
            assert "password" not in m.group(1).lower(), "كلمة المرور تُخزَّن محلياً"
            assert "username" not in m.group(1).lower(), "اسم المستخدم يُخزَّن محلياً"
