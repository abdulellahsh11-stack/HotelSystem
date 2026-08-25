#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
tests/test_cross_tenant_attacks.py — محاولات اختراق متعمّدة بين المنشآت

كل اختبار هنا يلعب دور مهاجم: منشأة «فندق أ» مسجَّلة الدخول بشكل شرعي
تحاول الوصول إلى بيانات «فندق ب». النجاح المطلوب هو **الفشل** — أي أن
تُرفض المحاولة أو تُعاد بيانات فندق أ فقط.

يكمّل هذا `test_tenant_isolation.py`: ذاك يفحص الكود المكتوب، وهذا
يفحص السلوك عبر HTTP — فيكشف ما ينجو من الفحص الساكن، مثل مسار يُمرَّر
فيه المعرّف من المسار بدل الجلسة.
"""
from __future__ import annotations

import warnings
from datetime import datetime

import pytest
from fastapi.testclient import TestClient

warnings.filterwarnings("ignore")

from app_core import _client_sessions, _lock, _login_attempts  # noqa: E402
from main import app  # noqa: E402

# بيانات المنشأتين — أي ظهور لنصوص «ب» في ردٍّ لـ«أ» تسريب
A, B = "hotel_A", "hotel_B"
SECRET_B = "سرّ-فندق-ب-لا-يظهر-عند-أ"


class TwoTenantDB:
    """قاعدة بيانات وهمية تُطبّق شرط client_id بأمانة وتسجّل كل استعلام."""

    use_postgres = True

    def __init__(self):
        self.queries: list[tuple[str, tuple]] = []
        self.rooms = [
            {"id": 1, "client_id": A, "room_number": "A-101", "room_type": "standard",
             "floor": 1, "capacity": 2, "base_price": 100, "status": "available", "notes": ""},
            {"id": 99, "client_id": B, "room_number": "B-909", "room_type": "suite",
             "floor": 9, "capacity": 4, "base_price": 900, "status": "available",
             "notes": SECRET_B},
        ]
        self.staff = [
            {"id": 7, "client_id": B, "username": "b_manager", "full_name": SECRET_B,
             "pass_hash": "x", "pass_salt": "y", "role": "manager", "extra_perms": "[]",
             "is_active": True, "last_login": None, "created_at": "2026-08-10"},
        ]

    def health(self):
        return {"ok": True}

    # ملاحظة على أمانة المحاكاة: هذه القاعدة تُطبّق **ما هو مكتوب في
    # الاستعلام فقط**، كما تفعل PostgreSQL. لو عزلت من تلقاء نفسها
    # لأخفت كل استعلام بلا client_id — وهي بالضبط الثغرة المطلوب
    # كشفها — فيمرّ الاختبار على كود مخترَق.
    def _apply(self, rows, low, params):
        out = list(rows)
        if "client_id=%s" in low:
            cid = next((p for p in params if isinstance(p, str) and p in (A, B)), None)
            out = [r for r in out if r["client_id"] == cid]
        if " id=%s" in low or "(id=%s" in low:
            rid = next((p for p in params if isinstance(p, int)), None)
            out = [r for r in out if r["id"] == rid]
        return out

    def execute(self, sql, params=(), fetch=None):
        s = " ".join(sql.split())
        self.queries.append((s, tuple(params or ())))
        low = s.lower()

        table = None
        if "from rooms" in low or low.startswith(("update rooms", "delete from rooms")):
            table = self.rooms
        elif "staff_users" in low:
            table = self.staff

        if table is not None:
            rows = self._apply(table, low, params)
            if low.startswith("delete from"):
                for r in rows:
                    table.remove(r)
                return []
            if fetch == "one":
                return rows[0] if rows else None
            return rows

        if "from bookings" in low:
            return {"n": 0} if fetch == "one" else []
        return None if fetch == "one" else []


@pytest.fixture
def client():
    app.state.db = TwoTenantDB()
    # lifespan لا يعمل تحت TestClient، وهو ما يضبط هاتين الخدمتين.
    # بدونهما ترمي المسارات AttributeError فيصير 500 ويُخفي نتيجة الهجوم.
    app.state.pricing = None
    app.state.channels = None
    with _lock:
        _client_sessions.clear()
        _login_attempts.clear()
        now = datetime.now().isoformat()
        for token, cid in (("tok-A", A), ("tok-B", B)):
            _client_sessions[token] = {
                "client_id": cid, "role": "owner", "permissions": ["*"], "created_at": now,
            }
    yield TestClient(app, raise_server_exceptions=False)
    with _lock:
        _client_sessions.clear()
        _login_attempts.clear()


AS_A = {"client_token": "tok-A"}


def _leaks(response) -> bool:
    """هل يحمل الردّ أثراً من فندق ب؟"""
    return SECRET_B in response.text or "B-909" in response.text


# ── ١) قراءة بيانات منشأة أخرى ─────────────────────────────────
def test_listing_rooms_returns_only_my_own(client):
    r = client.get("/api/rooms", cookies=AS_A)
    assert r.status_code == 200
    assert not _leaks(r), "ظهرت غرفة فندق ب في قائمة فندق أ"
    assert "A-101" in r.text


def test_listing_staff_returns_only_my_own(client):
    r = client.get("/api/staff/accounts", cookies=AS_A)
    assert r.status_code == 200
    assert not _leaks(r), "ظهر موظف فندق ب عند فندق أ"


# ── ٢) تمرير معرّف منشأة أخرى في المسار ────────────────────────
@pytest.mark.parametrize("path", [
    f"/api/channels/status/{B}",
    f"/api/channels/sync-log/{B}",
    f"/api/channels/revenue-split/{B}",
    f"/api/pricing/rules/{B}",
    f"/api/pricing/calendar/{B}",
    f"/api/pricing/history/{B}",
    f"/api/pricing/impact/{B}",
])
def test_passing_another_tenants_id_in_the_path_is_ignored(client, path):
    """
    الهجوم: المسار يقبل client_id، فيضع المهاجم معرّف ضحيته.
    المطلوب: يُتجاهَل المعرّف ويُستخدم معرّف الجلسة.
    """
    r = client.get(path, cookies=AS_A)
    assert r.status_code != 500
    assert not _leaks(r), f"تسريب عبر المسار {path}"
    # لا استعلام نُفِّذ بمعرّف فندق ب
    assert not any(B in q[1] for q in app.state.db.queries), \
        f"نُفِّذ استعلام بمعرّف فندق ب عبر {path}"


# ── ٣) الكتابة في بيانات منشأة أخرى ────────────────────────────
def test_cannot_delete_another_tenants_room(client):
    """الهجوم: حذف غرفة برقمها الحقيقي في فندق ب."""
    r = client.delete("/api/rooms/99", cookies=AS_A)
    assert r.status_code == 404, "حُذفت — أو كُشف وجودها — غرفةُ منشأة أخرى"
    assert any(r["id"] == 99 for r in app.state.db.rooms), "غرفة فندق ب اختفت"


def test_cannot_edit_another_tenants_room(client):
    """
    الهجوم: تعديل غرفة فندق ب بتمرير معرّفها.

    التعديل يُنفَّذ بشرط client_id، فلا يُصيب صفاً في منشأة أخرى.
    """
    r = client.post("/api/rooms", cookies=AS_A, json={
        "id": 99, "room_number": "مُختَرَقة", "room_type": "suite",
        "floor": 1, "capacity": 2, "base_price": 1, "status": "available",
    })
    assert r.status_code in (200, 400, 404, 409)
    update = [q for q in app.state.db.queries if q[0].lower().startswith("update rooms")]
    for _, params in update:
        assert A in params, "استعلام تعديل بلا عزل بمعرّف فندق أ"
        assert B not in params


@pytest.mark.parametrize("method,path,body", [
    ("patch",  "/api/staff/accounts/7", {"role": "gm"}),
    ("post",   "/api/staff/accounts/7/reset-password", {"password": "كلمة-سر-طويلة"}),
    ("delete", "/api/staff/accounts/7", None),
])
def test_cannot_touch_another_tenants_staff_account(client, method, path, body):
    """الهجوم: ترقية أو اختطاف حساب موظف في منشأة أخرى."""
    kwargs = {"cookies": AS_A}
    if body is not None:
        kwargs["json"] = body
    r = getattr(client, method)(path, **kwargs)
    assert r.status_code != 500
    for sql, params in app.state.db.queries:
        low = sql.lower()
        if "staff_users" in low and (low.startswith(("update", "delete"))):
            assert A in params, f"استعلام كتابة على staff_users بلا عزل: {sql}"
            assert B not in params


def test_touching_another_tenants_account_returns_not_found(client):
    """
    ليس كل تسريبٍ تغييرَ بيانات: ردٌّ ناجح على حساب منشأة أخرى يُخبر
    المهاجم أن الحساب موجود، ولو لم يتغيّر شيء. المطلوب 404 دائماً.
    """
    r = client.patch("/api/staff/accounts/7", json={"full_name": "س"}, cookies=AS_A)
    assert r.status_code == 404, "كُشف وجود حساب في منشأة أخرى"


def test_another_tenants_staff_account_is_untouched(client):
    before = dict(app.state.db.staff[0])
    client.patch("/api/staff/accounts/7", json={"role": "gm"}, cookies=AS_A)
    assert app.state.db.staff[0] == before, "تغيّر حساب موظف في منشأة أخرى"


# ── ٤) كل استعلام نُفِّذ خلال جلسة «أ» يحمل معرّف «أ» ──────────────
def test_no_query_during_an_A_session_ever_carries_Bs_id(client):
    """
    الفحص الشامل: تُطلب كل نقاط القراءة بجلسة فندق أ، ثم يُتحقق أن
    معرّف فندق ب لم يصل إلى أي استعلام مهما كان المسار.
    """
    for path in ("/api/rooms", "/api/staff/accounts", "/api/staff/me",
                 f"/api/channels/status/{B}", f"/api/pricing/rules/{B}"):
        client.get(path, cookies=AS_A)

    offenders = [q[0][:80] for q in app.state.db.queries if B in q[1]]
    assert not offenders, "استعلامات حملت معرّف فندق ب:\n  " + "\n  ".join(offenders)


# ── ٥) الجلسة هي مصدر الهوية لا مُدخل المستخدم ─────────────────
def test_identity_comes_from_the_session_not_the_request_body(client):
    """الهجوم: حقن client_id في جسم الطلب لانتحال منشأة أخرى."""
    r = client.post("/api/rooms", cookies=AS_A, json={
        "client_id": B, "room_number": "حقن", "room_type": "standard",
        "floor": 1, "capacity": 2, "base_price": 10, "status": "available",
    })
    assert r.status_code in (200, 400, 409)
    inserts = [q for q in app.state.db.queries if q[0].lower().startswith("insert into rooms")]
    for _, params in inserts:
        assert params[0] == A, "أُدرجت الغرفة تحت منشأة من جسم الطلب لا من الجلسة"


def test_a_forged_or_unknown_token_gets_nothing(client):
    for token in ("no-such-token", "tok-A-fake", "x"):
        r = client.get("/api/rooms", cookies={"client_token": token})
        assert r.status_code == 401, f"رمز مزوَّر «{token}» حصل على {r.status_code}"


def test_no_session_at_all_is_rejected(client):
    for path in ("/api/rooms", "/api/staff/accounts", "/api/backup/download"):
        assert client.get(path).status_code == 401, f"{path} مكشوف بلا جلسة"
