#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
tests/test_security_review_fixes.py — أربع ثغرات كشفتها المراجعة الأمنية

كلٌّ منها كان يعمل بصمت: لا خطأ في السجلّ ولا أثرٍ في الواجهة.

  ١ — بوابة الدخول تفحص `endswith("/index.html")` وحدها، فكل صفحة وحدةٍ
      لا تُسمّى index — والأخطر: `dashboard.html` كاملةً — تُخدَم لأي زائر.
  ٢ — مفتاح التفعيل يُحرق قبل فحص تكرار المعرّف: تسجيلٌ يفشل يُضيع مفتاحاً
      دفع المشترك ثمنه.
  ٣ — معرّف المنشأة يُولَّد بـ`random` بلا فحص تفرّد.
  ٤ — حدّ المعدّل يُفهرَس بـ`request.client.host`، وهو خلف الوسيط عنوانُ
      الوسيط لكل الطلبات: دلوٌ واحد للجميع، فعشرة طلبات تُغلق المنصة.
"""
from __future__ import annotations

import warnings

import pytest
from fastapi.testclient import TestClient

warnings.filterwarnings("ignore")

import app_core  # noqa: E402
from app_core import _client_sessions, _lock, client_ip  # noqa: E402
from main import app  # noqa: E402

HTML = {"accept": "text/html"}


class _DB:
    use_postgres = True

    def health(self):
        return {"ok": True}

    def execute(self, *a, **k):
        return None if k.get("fetch") == "one" else []


@pytest.fixture
def anon():
    """عميلٌ بلا أي جلسة — كما يصل الزائر المجهول."""
    app.state.db = _DB()

    class _Cfg:
        pass_salt = "s"
        admin_pass_hash = ""
        owner_client_id = ""

    app.state.cfg = _Cfg()
    with _lock:
        _client_sessions.clear()
    yield TestClient(app, raise_server_exceptions=False)
    with _lock:
        _client_sessions.clear()


# ── ١ — بوابة صفحات البرنامج ───────────────────────────────────
@pytest.mark.parametrize("path", [
    "/static/dheuof/modules/01-guests/index.html",
    "/static/dheuof/modules/01-guests/registration.html",   # كانت مكشوفة
    "/static/dheuof/modules/01-guests/checkin.html",        # كانت مكشوفة
    "/static/dheuof/modules/01-guests/users.html",          # كانت مكشوفة
    "/static/dashboard.html",                               # لوحة التحكم كاملةً
])
def test_program_pages_need_a_session(anon, path):
    r = anon.get(path, headers=HTML, follow_redirects=False)
    assert r.status_code in (302, 401), f"{path} خُدمت بلا جلسة ({r.status_code})"


def test_the_guest_portal_stays_public(anon):
    """بوابة النزيل يفتحها الضيف ولا جلسة منشأة له؛ حجبها يُلغي غرضها."""
    r = anon.get("/static/dheuof/modules/01-guests/portal.html",
                 headers=HTML, follow_redirects=False)
    assert r.status_code == 200


def test_the_public_landing_page_stays_public(anon):
    r = anon.get("/static/index.html", headers=HTML, follow_redirects=False)
    assert r.status_code == 200


def test_assets_are_not_gated(anon):
    """حجب الأنماط والسكربتات يكسر صفحة الدخول نفسها."""
    r = anon.get("/static/css/dashboard.css", follow_redirects=False)
    assert r.status_code == 200


def test_a_shortcut_with_a_trailing_slash_is_gated(anon):
    r = anon.get("/pos/", headers=HTML, follow_redirects=False)
    assert r.status_code in (302, 307, 401)


def test_xhr_gets_401_not_a_redirect(anon):
    """طلبٌ برمجي يحتاج رمز حالةٍ لا صفحة دخول."""
    r = anon.get("/static/dashboard.html",
                 headers={"accept": "application/json"}, follow_redirects=False)
    assert r.status_code == 401


# ── ٤ — عنوان الطالب خلف الوسيط ────────────────────────────────
class _Req:
    def __init__(self, host, forwarded=None):
        self.client = type("C", (), {"host": host})()
        self.headers = {"x-forwarded-for": forwarded} if forwarded else {}


def test_the_real_ip_is_read_from_the_proxy_header(monkeypatch):
    monkeypatch.setattr(app_core, "TRUST_PROXY", True)
    monkeypatch.setattr(app_core, "TRUST_PROXY_HOPS", 1)
    ip = client_ip(_Req("10.0.0.1", "203.0.113.9"))
    assert ip == "203.0.113.9", "عاد عنوان الوسيط بدل عنوان الطالب"


def test_two_visitors_behind_one_proxy_are_told_apart(monkeypatch):
    """
    جوهر العطل: لولا هذا لتشارك كل المستأجرين دلواً واحداً — وعشرة طلبات
    تُغلق الدخول على المنصة كلها.
    """
    monkeypatch.setattr(app_core, "TRUST_PROXY", True)
    monkeypatch.setattr(app_core, "TRUST_PROXY_HOPS", 1)
    a = client_ip(_Req("10.0.0.1", "203.0.113.9"))
    b = client_ip(_Req("10.0.0.1", "198.51.100.4"))
    assert a != b


def test_a_spoofed_chain_cannot_hide_the_appended_address(monkeypatch):
    """العميل يكتب ما يشاء في اليسار؛ الوسيط يُلحق الحقيقي في اليمين."""
    monkeypatch.setattr(app_core, "TRUST_PROXY", True)
    monkeypatch.setattr(app_core, "TRUST_PROXY_HOPS", 1)
    ip = client_ip(_Req("10.0.0.1", "1.1.1.1, 2.2.2.2, 203.0.113.9"))
    assert ip == "203.0.113.9"


def test_without_a_proxy_the_socket_address_is_used(monkeypatch):
    monkeypatch.setattr(app_core, "TRUST_PROXY", False)
    assert client_ip(_Req("203.0.113.5", "1.2.3.4")) == "203.0.113.5"


def test_a_missing_header_falls_back_to_the_socket(monkeypatch):
    monkeypatch.setattr(app_core, "TRUST_PROXY", True)
    assert client_ip(_Req("203.0.113.5")) == "203.0.113.5"


def test_the_shipped_default_trusts_the_proxy():
    """
    الحارس الذي كان ناقصاً.

    بقيّة اختبارات العنوان تضبط `TRUST_PROXY` بنفسها، فتفحص الدالة لا
    الإعداد المشحون — وقد مرّت كلها بينما كان الافتراض معطَّلاً والعطل
    عائداً. هذا يفحص الافتراض نفسه: المنصة تعمل خلف وسيط، وتعطيلُه
    يُعيد الدلو الواحد للجميع.
    """
    assert app_core.TRUST_PROXY is True, (
        "الافتراض لا يثق بالوسيط — يعود كل المستأجرين إلى دلوٍ واحد"
    )
    assert app_core.TRUST_PROXY_HOPS >= 1


def test_the_default_resolves_a_forwarded_address_end_to_end():
    """بلا ترقيع: كما تصل الطلبات فعلاً في الإنتاج."""
    assert client_ip(_Req("10.0.0.1", "203.0.113.9")) == "203.0.113.9"


# ── ٢ و٣ — التسجيل: المفتاح والمعرّف ───────────────────────────
class _Store:
    """مخزنٌ وهمي يكفي لمسار التسجيل."""

    def __init__(self, clients=None, keys=None):
        self.clients = dict(clients or {})
        self.admin = {"activation_keys": list(keys or [])}
        self.saved = []

    def get_client(self, cid):
        return self.clients.get(str(cid))

    def save_client(self, c):
        self.clients[str(c["id"])] = c
        self.saved.append(c)

    def get_admin_data(self):
        return self.admin

    def save_admin_data(self, data):
        self.admin = data


@pytest.fixture
def reg(anon):
    def _make(store):
        app.state.store = store
        return anon
    return _make


KEY = [{"key": "ABC-123", "plan": "pro", "days": 365, "used": False}]


def test_a_failed_registration_does_not_burn_the_key(reg):
    """
    المشترك دفع ثمن المفتاح. تسجيلٌ يفشل لتكرار المعرّف كان يحرقه: لا
    حساب ولا مفتاح.
    """
    store = _Store(clients={"12345678": {"id": "12345678"}}, keys=KEY)
    client = reg(store)
    r = client.post("/api/client/register", json={
        "hotel_name": "فندق", "password": "Str0ngPass!", "client_id": "12345678",
        "activation_key": "ABC-123",
    })
    assert r.status_code == 400
    assert store.admin["activation_keys"][0]["used"] is False, "أُحرق المفتاح رغم فشل التسجيل"


def test_a_successful_registration_does_consume_the_key(reg):
    store = _Store(keys=KEY)
    client = reg(store)
    r = client.post("/api/client/register", json={
        "hotel_name": "فندق", "password": "Str0ngPass!", "client_id": "99887766",
        "activation_key": "ABC-123",
    })
    assert r.status_code == 200, r.text[:200]
    assert store.admin["activation_keys"][0]["used"] is True


def test_a_generated_id_avoids_one_already_taken(reg, monkeypatch):
    """
    التوليد الأعمى كان يُنتج معرّفاً مأخوذاً فيفشل التسجيل بخطأ عن معرّفٍ
    لم يختره المشترك أصلاً.
    """
    import secrets

    taken = "10000000"
    store = _Store(clients={taken: {"id": taken}})
    client = reg(store)

    # أول محاولة تُصادم، والثانية تنجح
    values = iter([0, 5555555])
    monkeypatch.setattr(secrets, "randbelow", lambda n: next(values))

    r = client.post("/api/client/register",
                    json={"hotel_name": "فندق", "password": "Str0ngPass!"})
    assert r.status_code == 200, r.text[:200]
    assert store.saved[0]["id"] == "15555555"


def test_a_generated_id_is_eight_digits(reg):
    store = _Store()
    client = reg(store)
    r = client.post("/api/client/register",
                    json={"hotel_name": "فندق", "password": "Str0ngPass!"})
    assert r.status_code == 200, r.text[:200]
    new_id = store.saved[0]["id"]
    assert new_id.isdigit() and len(new_id) == 8, new_id


def test_registration_never_returns_the_password_hash(reg):
    """تجزئة كلمة المرور لا تخرج عبر HTTP بحال."""
    store = _Store()
    client = reg(store)
    r = client.post("/api/client/register",
                    json={"hotel_name": "فندق", "password": "Str0ngPass!"})
    body = r.text
    assert "pass_hash" not in body and "pass_salt" not in body
