#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
tests/test_write_endpoints.py — مسارات الكتابة: لا انهيار، وتحقّق واضح.

مسحُ كل مسارات الكتابة بجسم فارغ أظهر سبعة تُعيد 500. اثنان منها علّتان
حقيقيتان تفشلان مع مدخل صحيح تماماً، لا مع الفارغ فحسب:

• POST /api/guests — كان يُولّد معرّفاً سداسي عشري لعمود SERIAL، فينهار
  تحويله إلى عدد صحيح في طبقة التخزين. إضافة نزيل كانت معطَّلة كلياً.

• POST /api/m10/loyalty/award — ينفّذ ON CONFLICT (client_id, guest_id)
  على guest_profiles، والقيد الفريد غير موجود. منح نقاط الولاء كان
  يفشل دائماً.

والخمسة الباقية كانت تُسرّب نص خطأ PostgreSQL إلى العميل («null value
in column …») بدل رسالة تحقّق مفهومة — وهو تسريب لأسماء الأعمدة أيضاً.
"""

import os

import pytest

from db.passwords import hash_password

DATABASE_URL = os.environ.get("DATABASE_URL", "")
pytestmark = pytest.mark.skipif(not DATABASE_URL, reason="DATABASE_URL not set")

CLIENT_ID = "write_test"
PASSWORD = "كلمة-كتابة-2026"


def _walk_routes(routes, _seen=None):
    if _seen is None:
        _seen = set()
    for route in routes:
        if id(route) in _seen:
            continue
        _seen.add(id(route))
        for attr in ("original_router", "app"):
            inner = getattr(route, attr, None)
            nested = getattr(inner, "routes", None)
            if nested:
                yield from _walk_routes(nested, _seen)
        nested = getattr(route, "routes", None)
        if nested:
            yield from _walk_routes(nested, _seen)
        if hasattr(route, "methods"):
            yield route


@pytest.fixture(scope="module")
def logged_in(test_client, db_pool):
    store = test_client.app.state.store
    db_pool.execute("DELETE FROM clients WHERE id = %s", (CLIENT_ID,))
    store.save_client({
        "id": CLIENT_ID, "name": "فندق الكتابة",
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


def test_no_write_endpoint_crashes_on_empty_body(logged_in):
    """المدخل الناقص يستحقّ 4xx لا 5xx: الأخير يعني انهياراً غير مُعالَج
    ويُسرّب تفاصيل المخطط في نص الخطأ."""
    checked, broken = set(), []
    for route in _walk_routes(logged_in.app.routes):
        path = getattr(route, "path", "")
        methods = getattr(route, "methods", None) or set()
        if "{" in path or not path.startswith("/api/"):
            continue
        if "logout" in path or "login" in path:
            continue
        for method in methods & {"POST", "PUT", "PATCH", "DELETE"}:
            if (method, path) in checked:
                continue
            checked.add((method, path))
            try:
                resp = logged_in.request(method, path, json={})
            except Exception as e:
                broken.append(f"{method} {path} → استثناء {type(e).__name__}: {e}")
                continue
            if resp.status_code >= 500:
                broken.append(f"{method} {path} → {resp.status_code}: {resp.text[:120]}")

    assert len(checked) >= 40, f"عدد مسارات الكتابة المكتشفة أقل من المتوقّع: {len(checked)}"
    assert not broken, "مسارات كتابة تنهار:\n" + "\n".join(broken)


# ── إضافة نزيل ────────────────────────────────────────────────────────────────

def test_guest_creation_returns_database_id(logged_in):
    """المعرّف يجب أن يأتي من قاعدة البيانات لا أن يُختلق في التطبيق."""
    resp = logged_in.post("/api/guests", json={
        "full_name": "عبدالله السالم", "id_number": "1098765432",
    })
    assert resp.status_code == 200, resp.text[:200]
    guest_id = resp.json()["data"]["id"]
    assert isinstance(guest_id, int), f"المعرّف ليس رقماً: {guest_id!r}"


def test_created_guest_is_retrievable(logged_in):
    """المعرّف المُختلَق سابقاً لم يكن يقابله أي صف."""
    created = logged_in.post(
        "/api/guests", json={"full_name": "نزيل الاسترجاع"}
    ).json()["data"]
    resp = logged_in.get(f"/api/guests/{created['id']}")
    assert resp.status_code == 200, resp.text[:200]
    assert resp.json()["data"]["full_name"] == "نزيل الاسترجاع"


def test_guest_without_name_is_rejected_clearly(logged_in):
    resp = logged_in.post("/api/guests", json={})
    assert resp.status_code == 422
    assert "اسم" in resp.json()["detail"]


# ── نقاط الولاء ───────────────────────────────────────────────────────────────

def test_loyalty_award_works(logged_in, db_pool):
    """كان يفشل دائماً: ON CONFLICT بلا قيد فريد مطابق."""
    guest = logged_in.post(
        "/api/guests", json={"full_name": "نزيل الولاء"}
    ).json()["data"]

    resp = logged_in.post("/api/m10/loyalty/award", json={
        "guest_id": guest["id"], "points": 250, "description": "إقامة أولى",
    })
    assert resp.status_code == 200, resp.text[:200]


def test_loyalty_points_accumulate(logged_in, db_pool):
    """المنح الثاني يمرّ على مسار ON CONFLICT فعلياً."""
    guest = logged_in.post(
        "/api/guests", json={"full_name": "نزيل التراكم"}
    ).json()["data"]

    for points in (100, 150):
        resp = logged_in.post("/api/m10/loyalty/award",
                              json={"guest_id": guest["id"], "points": points})
        assert resp.status_code == 200, resp.text[:200]

    row = db_pool.execute(
        "SELECT loyalty_points FROM guest_profiles WHERE client_id = %s AND guest_id = %s",
        (CLIENT_ID, guest["id"]), fetch="one",
    )
    assert row and row["loyalty_points"] == 250, f"النقاط لم تتراكم: {row}"


def test_guest_profiles_has_the_unique_constraint(db_pool):
    """القيد الذي يعتمد عليه ON CONFLICT."""
    assert db_pool.execute(
        "SELECT COUNT(*) AS n FROM pg_indexes WHERE tablename = 'guest_profiles' "
        "AND indexname = 'uq_guest_profiles_client_guest'", fetch="one",
    )["n"] == 1


# ── رسائل التحقّق ─────────────────────────────────────────────────────────────

@pytest.mark.parametrize("path,body", [
    ("/api/rooms", {}),
    ("/api/bookings", {}),
    ("/api/m06/attendance", {}),
])
def test_missing_fields_do_not_leak_database_errors(logged_in, path, body):
    resp = logged_in.request("POST", path, json=body)
    assert resp.status_code < 500, f"{path} → {resp.status_code}"
    text = resp.text
    for leak in ("null value in column", "violates not-null", "relation \""):
        assert leak not in text, f"{path} سرّب نص خطأ من قاعدة البيانات: {text[:150]}"
