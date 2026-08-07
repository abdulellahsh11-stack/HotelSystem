#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
tests/test_endpoint_smoke.py — استدعاء كل مسار GET والتأكد أنه لا ينهار.

لماذا
─────
أربعة مسارات قوائم كانت تُعيد HTTP 500 في كل استدعاء — الموظفون،
حجوزات القنوات، مبيعات نقاط البيع، الفواتير المحاسبية — ومرّت المجموعة
خضراء لأنها لم تكن تستدعي أي مسار قائمة. العلل كانت من نوع لا يظهر إلا
عند التشغيل: فهرسة صف قاموس بالرقم، وعمود مذكور في الاستعلام وغير
موجود في المخطط.

هذا الاختبار يُعدّد المسارات من جدول توجيه التطبيق نفسه، فيغطّي تلقائياً
أي مسار يُضاف لاحقاً دون أن يتذكّر أحد إضافته هنا.

النطاق: مسارات GET بلا معاملات في المسار. ما يحتاج معرّفاً محدداً
(`/{id}`) يُغطّى باختبارات وحداتها.
"""

import os

import pytest

from db.passwords import hash_password

DATABASE_URL = os.environ.get("DATABASE_URL", "")
pytestmark = pytest.mark.skipif(not DATABASE_URL, reason="DATABASE_URL not set")

SMOKE_CLIENT = "smoke_test"
SMOKE_PASSWORD = "كلمة-دخان-2026"


def _walk_routes(routes, _seen=None):
    """يمرّ على كل المسارات بما فيها المُضمَّنة عبر include_router.

    FastAPI الحديثة لا تُسطّح الموجِّهات المُضمَّنة داخل app.routes، بل
    تلفّ كلاً منها في كائن `_IncludedRouter` يحمل الموجِّه الأصلي في
    السمة `original_router` — ولا يعرض `routes` مباشرة. المرور على
    app.routes وحده يُغفل كل مسارات الوحدات (أكثر من مئة مسار)، فيبدو
    المسحُ شاملاً وهو لا يرى إلا القشرة.
    """
    if _seen is None:
        _seen = set()
    for route in routes:
        if id(route) in _seen:
            continue
        _seen.add(id(route))

        # _IncludedRouter → الموجِّه الأصلي، وMount → التطبيق المُركَّب
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


def _collect_get_paths(app, prefix: str, exclude_prefix: str | None = None) -> list:
    """مسارات GET الثابتة تحت بادئة معيّنة.

    تُستثنى مسارات تسجيل الخروج: استدعاؤها وسط المسح يُنهي الجلسة
    فتعود كل المسارات التالية بـ 401 ويبدو المسح ناجحاً وهو أعمى.
    """
    paths = set()
    for route in _walk_routes(app.routes):
        methods = getattr(route, "methods", None) or set()
        path = getattr(route, "path", "")
        if "GET" not in methods or "{" in path:
            continue
        if not path.startswith(prefix) or "logout" in path:
            continue
        if exclude_prefix and path.startswith(exclude_prefix):
            continue
        paths.add(path)
    return sorted(paths)


@pytest.fixture(scope="module")
def tenant_client(test_client, db_pool):
    """جلسة منشأة ببيانات كافية كي تُعيد المسارات نتائج حقيقية."""
    store = test_client.app.state.store
    db_pool.execute("DELETE FROM clients WHERE id = %s", (SMOKE_CLIENT,))
    store.save_client({
        "id": SMOKE_CLIENT, "name": "فندق الدخان",
        "pass_hash": hash_password(SMOKE_PASSWORD), "pass_salt": "",
        "status": "active", "plan": "pro",
    })
    db_pool.execute(
        "INSERT INTO rooms (client_id, room_number, base_price, status) "
        "VALUES (%s, 'S-101', 400, 'available')", (SMOKE_CLIENT,)
    )
    store.save_guest(SMOKE_CLIENT, {"full_name": "نزيل الدخان", "id_number": "1098765432"})

    resp = test_client.post(
        "/api/login", data={"client_id": SMOKE_CLIENT, "password": SMOKE_PASSWORD},
        follow_redirects=False,
    )
    assert resp.status_code in (200, 302, 303)

    yield test_client

    db_pool.execute("DELETE FROM clients WHERE id = %s", (SMOKE_CLIENT,))


def test_no_tenant_endpoint_returns_server_error(tenant_client):
    """أي 5xx هنا يعني مساراً مكسوراً يراه العميل."""
    paths = _collect_get_paths(
        tenant_client.app, "/api/", exclude_prefix="/api/admin/"
    )
    assert len(paths) >= 15, f"عدد المسارات المكتشفة أقل من المتوقّع: {len(paths)}"

    broken = []
    for path in paths:
        try:
            resp = tenant_client.get(path)
        except Exception as e:
            broken.append(f"{path} → استثناء {type(e).__name__}: {e}")
            continue
        if resp.status_code >= 500:
            broken.append(f"{path} → {resp.status_code}: {resp.text[:120]}")

    assert not broken, "مسارات مُعطَّلة:\n" + "\n".join(broken)


def test_tenant_endpoints_are_authenticated(tenant_client):
    """المسح لا قيمة له إن كانت الجلسة غير مصادَقة: كل شيء سيعود 401
    ويبدو سليماً. نتحقّق أن مساراً معروفاً يُعيد 200 فعلاً."""
    assert tenant_client.get("/api/rooms").status_code == 200


@pytest.fixture(scope="module")
def admin_client(test_client, monkeypatch_session=None):
    """جلسة مالك المنصة — تُغطّي مسارات /api/admin/."""
    cfg = test_client.app.state.cfg
    original = cfg.admin_pass_hash
    cfg.admin_pass_hash = hash_password(SMOKE_PASSWORD)

    resp = test_client.post(
        "/api/admin/login", data={"password": SMOKE_PASSWORD}, follow_redirects=False
    )
    assert resp.status_code in (200, 302, 303), f"فشل دخول المالك: {resp.status_code}"

    yield test_client

    cfg.admin_pass_hash = original


def test_no_admin_endpoint_returns_server_error(admin_client):
    paths = _collect_get_paths(admin_client.app, "/api/admin/")
    assert len(paths) >= 5, f"عدد مسارات الإدارة أقل من المتوقّع: {len(paths)}"

    broken = []
    for path in paths:
        try:
            resp = admin_client.get(path)
        except Exception as e:
            broken.append(f"{path} → استثناء {type(e).__name__}: {e}")
            continue
        if resp.status_code >= 500:
            broken.append(f"{path} → {resp.status_code}: {resp.text[:120]}")
        elif resp.status_code == 401:
            broken.append(f"{path} → 401 رغم جلسة مالك صالحة")

    assert not broken, "مسارات إدارة مُعطَّلة:\n" + "\n".join(broken)


def test_health_endpoint_reports_postgres(test_client):
    body = test_client.get("/api/health").json()
    assert body.get("status") in ("ok", "healthy"), body
