#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
tests/test_security_fixes.py — تثبيت إصلاحات أمنية تنكسر بصمت

كل اختبار هنا يحرس عيباً وقع فعلاً. أكثرها لا يُسقط الاختبارات إن عاد،
بل يُنتج قفلاً دائماً أو تسريباً هادئاً — ولهذا يحتاج حارساً صريحاً.
"""
from __future__ import annotations

import json
import warnings
from datetime import datetime

import pytest
from fastapi.testclient import TestClient

warnings.filterwarnings("ignore")

from app_core import (  # noqa: E402
    _client_sessions, _lock, _make_password, _session_from_row, _verify_password,
)
from db.store import public_settings  # noqa: E402
from main import app  # noqa: E402


class _Cfg:
    pass_salt = "ملح-عام"
    admin_pass_hash = ""


# ── ١) تغيير كلمة المرور من لوحة المشرف يجب ألا يقفل المنشأة ────
def test_admin_password_change_writes_hash_and_salt_together():
    """
    العيب: كان يُكتب pass_hash بالملح العام و pass_salt القديم باقٍ،
    فيتحقق النظام بملح الحساب فلا يُطابق أبداً — قفلٌ دائم بلا استرداد.
    """
    import routes.admin as admin_module

    src = (admin_module.__file__ or "")
    with open(src, encoding="utf-8") as fh:
        code = fh.read()
    assert '_hash_password(str(data["password"]), cfg.pass_salt)' not in code, \
        "عاد كتابةُ التجزئة بلا ملحها — يقفل المنشأة"

    # والسلوك نفسه: ما يُكتب يجب أن يتحقّق منه
    new_hash, new_salt = _make_password("كلمة-جديدة")
    assert _verify_password("كلمة-جديدة", {"pass_hash": new_hash, "pass_salt": new_salt}, _Cfg())


# ── ٢) الإعدادات لا تُخرج تجزئة كلمة المرور ────────────────────
def test_public_settings_strips_account_secrets():
    client = {"settings": {"theme": "dark", "_account": {
        "pass_hash": "سر", "pass_salt": "ملح", "plan": "enterprise"}}}
    out = public_settings(client)
    assert out == {"theme": "dark"}
    assert "_account" not in out


def test_settings_endpoint_never_returns_a_password_hash():
    class _Store:
        def get_client(self, cid):
            return {"id": cid, "settings": {"theme": "dark", "_account": {
                "pass_hash": "HASH_MUST_NOT_LEAK", "pass_salt": "SALT_MUST_NOT_LEAK"}}}

    class _DB:
        use_postgres = True

        def execute(self, *a, **k):
            return []

        def health(self):
            return {"ok": True}

    app.state.db = _DB()
    app.state.store = _Store()
    with _lock:
        _client_sessions.clear()
        _client_sessions["t"] = {"client_id": "c1", "role": "owner",
                                 "permissions": ["*"],
                                 "created_at": datetime.now().isoformat()}
    try:
        r = TestClient(app, raise_server_exceptions=False).get(
            "/api/settings", cookies={"client_token": "t"})
        assert r.status_code == 200
        assert "HASH_MUST_NOT_LEAK" not in r.text
        assert "SALT_MUST_NOT_LEAK" not in r.text
        assert "theme" in r.text, "أُزيلت الإعدادات الحقيقية مع الأسرار"
    finally:
        with _lock:
            _client_sessions.clear()


# ── ٣) استعادة الجلسة تحفظ الدور ولا تمنح المالكية ─────────────
def test_restored_staff_session_keeps_its_own_role():
    """
    العيب: كانت الجلسة المستعادة تُبنى بـ owner و["*"] مهما كان صاحبها،
    فيصير كل موظف مالكاً بعد أول إعادة تشغيل.
    """
    session = _session_from_row({
        "client_id": "c1", "created_at": "2026-08-10", "role": "receptionist",
        "staff_id": 5, "username": "sara", "full_name": "سارة",
        "permissions": json.dumps(["bookings.read"]),
    })
    assert session["role"] == "receptionist"
    assert session["permissions"] == ["bookings.read"]
    assert "*" not in session["permissions"]
    assert session["staff_id"] == 5


def test_restored_legacy_row_without_a_role_is_treated_as_owner():
    """صفوف كُتبت قبل أعمدة الهوية كانت جلسات مالكٍ حصراً."""
    session = _session_from_row({
        "client_id": "c1", "created_at": "2026-08-10",
        "role": None, "permissions": None,
    })
    assert session["role"] == "owner"
    assert session["permissions"] == ["*"]


def test_a_restored_row_with_a_role_but_no_permissions_is_not_given_star():
    session = _session_from_row({
        "client_id": "c1", "created_at": "2026-08-10",
        "role": "housekeeping", "permissions": None,
    })
    assert session["permissions"] == [], "مُنحت صلاحية كاملة لدورٍ محدود"


@pytest.mark.parametrize("bad", ["{ليس json", "", "null"])
def test_malformed_stored_permissions_do_not_grant_anything(bad):
    session = _session_from_row({
        "client_id": "c1", "created_at": "x", "role": "receptionist",
        "permissions": bad,
    })
    assert "*" not in session["permissions"]


# ── ٤) مخزن JSON لا يُعيد بيانات مشتركة ────────────────────────
def test_json_store_returns_nothing_for_an_unknown_tenant():
    """
    العيب: كان يسقط إلى `data[key]` — المفتاح العام — فتحصل منشأةٌ
    لا سجلّ لها على بيانات غيرها.
    """
    from db.store import DataStore

    class _DB:
        use_postgres = False

        def json_read(self):
            return {
                "clients": [{"id": "known", "guests": [{"name": "ضيف مسجَّل"}]}],
                "guests": [{"name": "بيانات عامة مشتركة"}],
            }

    store = DataStore.__new__(DataStore)
    store.db = _DB()
    store._use_pg = False

    assert store._json_get_client_data("known", "guests") == [{"name": "ضيف مسجَّل"}]
    assert store._json_get_client_data("unknown", "guests") == [], \
        "منشأة مجهولة حصلت على البيانات العامة"


# ── ٥) فشل قاعدة البيانات يوقف الإقلاع ────────────────────────
def test_db_failure_aborts_startup_unless_explicitly_allowed():
    import db.connection as conn

    src = conn.__file__
    with open(src, encoding="utf-8") as fh:
        code = fh.read()
    assert "ALLOW_JSON_FALLBACK" in code
    assert "raise RuntimeError" in code, "عاد السقوط الصامت إلى مخزن JSON"


# ── ٦) الاشتراك المنتهي اليوم ما زال سارياً ────────────────────
def test_expiry_is_not_declared_early_or_on_bad_data():
    from datetime import date, timedelta

    from utils.date_utils import is_expired

    assert is_expired(date.today().isoformat()) is False, "أُنهي اشتراكٌ ينتهي اليوم"
    assert is_expired((date.today() - timedelta(days=1)).isoformat()) is True
    assert is_expired((date.today() + timedelta(days=1)).isoformat()) is False
    assert is_expired("ليس تاريخاً") is False, "تاريخ فاسد عُدّ انتهاءً"
    assert is_expired("") is False
