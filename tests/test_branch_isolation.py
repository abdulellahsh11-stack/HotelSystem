#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
tests/test_branch_isolation.py — عزل الفروع داخل المنشأة الواحدة.

الحالة السابقة
──────────────
branch_clause و session_branches معرَّفتان في db/security.py ولم
تُستدعيا ولا مرة. جدول branches موجود، وعمود branch_id مضاف إلى سبعة
جداول تشغيلية — ولا شيء يستعملها. المنشأة متعددة الفروع ترى كل فروعها
بلا فصل: موظف فرع جدة يقرأ غرف الرياض وحجوزاته ورواتب موظفيه.

لماذا في طبقة قاعدة البيانات
────────────────────────────
إضافة شرط الفرع يدوياً إلى عشرات الاستعلامات تعني أن أحدها سيُنسى —
وهو بالضبط ما حدث مع شرط client_id، ولذلك وُجدت سياسات RLS. عزل الفروع
يجري في نفس السياسة، فلا يحتاج أي استعلام تعديلاً ولا يستطيع استعلام
جديد أن يفلت منه.

الدلالات
────────
  app.branch_ids فارغ   →  كل الفروع (المالك والمدير العام)
  branch_id فارغ في صف  →  غير منسوب لفرع، فيراه الجميع
"""

import os

import pytest

from db.passwords import hash_password
from db.tenant_context import branch_scope, tenant_scope

DATABASE_URL = os.environ.get("DATABASE_URL", "")
pytestmark = pytest.mark.skipif(not DATABASE_URL, reason="DATABASE_URL not set")

CLIENT_ID = "branch_test"
PASSWORD = "كلمة-فروع-2026"


@pytest.fixture(scope="module")
def chain(test_client, db_pool):
    """سلسلة بفرعين، ولكل فرع غرفة، وغرفة ثالثة غير منسوبة لفرع."""
    from db.schema_v3 import run_app_role_migration, run_rls_migration
    run_app_role_migration(db_pool)
    os.environ["RLS_ENFORCE"] = "1"
    run_rls_migration(db_pool)

    # التحوّل إلى الدور المُقيَّد إلزامي هنا: مستخدم قاعدة البيانات في
    # بيئة الاختبار خارق الصلاحيات، والخارق يتجاوز RLS حتى مع FORCE.
    # بدون هذا السطر تمرّ الاختبارات وهي لا تفحص شيئاً.
    previous = db_pool._app_role_available
    db_pool._app_role_available = True

    store = test_client.app.state.store
    db_pool.execute("DELETE FROM clients WHERE id = %s", (CLIENT_ID,))
    store.save_client({
        "id": CLIENT_ID, "name": "سلسلة الاختبار",
        "pass_hash": hash_password(PASSWORD), "pass_salt": "",
        "status": "active", "plan": "pro",
    })

    riyadh = db_pool.execute(
        "INSERT INTO branches (client_id, branch_code, name_ar) "
        "VALUES (%s,'RUH','فرع الرياض') RETURNING id", (CLIENT_ID,), fetch="one",
    )["id"]
    jeddah = db_pool.execute(
        "INSERT INTO branches (client_id, branch_code, name_ar) "
        "VALUES (%s,'JED','فرع جدة') RETURNING id", (CLIENT_ID,), fetch="one",
    )["id"]

    for number, branch in (("RUH-101", riyadh), ("JED-201", jeddah)):
        db_pool.execute(
            "INSERT INTO rooms (client_id, room_number, base_price, status, branch_id) "
            "VALUES (%s,%s,400,'available',%s)", (CLIENT_ID, number, branch),
        )
    db_pool.execute(
        "INSERT INTO rooms (client_id, room_number, base_price, status) "
        "VALUES (%s,'SHARED',400,'available')", (CLIENT_ID,),
    )

    yield {"db": db_pool, "riyadh": riyadh, "jeddah": jeddah}

    db_pool._app_role_available = previous
    db_pool.execute("DELETE FROM clients WHERE id = %s", (CLIENT_ID,))


def _rooms(db, branches):
    with tenant_scope(CLIENT_ID), branch_scope(branches):
        rows = db.execute("SELECT room_number FROM rooms", fetch="all") or []
    return sorted(r["room_number"] for r in rows)


# ── العزل الفعلي ──────────────────────────────────────────────────────────────

def test_owner_sees_every_branch(chain):
    assert _rooms(chain["db"], None) == ["JED-201", "RUH-101", "SHARED"]


def test_branch_staff_sees_only_their_branch(chain):
    """الاختبار الحاسم: استعلام بلا أي شرط فرع يُعيد فرعاً واحداً."""
    assert _rooms(chain["db"], [chain["riyadh"]]) == ["RUH-101", "SHARED"]


def test_other_branch_data_is_invisible(chain):
    assert "JED-201" not in _rooms(chain["db"], [chain["riyadh"]])
    assert "RUH-101" not in _rooms(chain["db"], [chain["jeddah"]])


def test_multi_branch_staff_sees_all_assigned(chain):
    """مدير إقليمي مسؤول عن فرعين يرى كليهما."""
    both = _rooms(chain["db"], [chain["riyadh"], chain["jeddah"]])
    assert both == ["JED-201", "RUH-101", "SHARED"]


def test_unassigned_rows_are_visible_to_everyone(chain):
    """صف بلا فرع يخصّ المنشأة كلها — إخفاؤه يعني فقدان بيانات."""
    for branches in (None, [chain["riyadh"]], [chain["jeddah"]]):
        assert "SHARED" in _rooms(chain["db"], branches)


def test_unknown_branch_sees_only_unassigned(chain):
    assert _rooms(chain["db"], [999999]) == ["SHARED"]


# ── سلامة السياق ──────────────────────────────────────────────────────────────

def test_branch_context_does_not_leak_between_requests(chain):
    """الاتصال المُعاد للمجمّع لا يجوز أن يحمل قيد فرع الطلب السابق."""
    db = chain["db"]
    with tenant_scope(CLIENT_ID), branch_scope([chain["riyadh"]]):
        db.execute("SELECT 1")
    leaked = db.execute(
        "SELECT current_setting('app.branch_ids', true) AS b", fetch="one"
    )["b"]
    assert not leaked, f"تسرّب قيد الفرع: {leaked!r}"


def test_branch_scope_restores_previous_value(chain):
    from db.tenant_context import get_current_branches
    with branch_scope([1]):
        assert get_current_branches() == ["1"]
        with branch_scope([2]):
            assert get_current_branches() == ["2"]
        assert get_current_branches() == ["1"]
    assert get_current_branches() is None


def test_empty_branch_list_means_all_branches(chain):
    """قائمة فارغة ≠ لا يرى شيئاً — وإلا حُجبت البيانات عن المالك."""
    assert _rooms(chain["db"], []) == ["JED-201", "RUH-101", "SHARED"]


# ── التغطية ───────────────────────────────────────────────────────────────────

def test_every_branch_table_has_the_branch_predicate(chain):
    """أي جدول يحمل branch_id ولا تذكره سياسته ثغرة عزل."""
    rows = chain["db"].execute(
        """
        SELECT c.relname AS t
        FROM pg_class c
        JOIN pg_namespace n ON n.oid = c.relnamespace
        WHERE n.nspname = 'public' AND c.relkind = 'r'
          AND EXISTS (SELECT 1 FROM information_schema.columns col
                      WHERE col.table_schema='public' AND col.table_name=c.relname
                        AND col.column_name='branch_id')
          AND c.relname NOT IN ('staff_role_assignments', 'secure_file_links')
          AND NOT EXISTS (
              SELECT 1 FROM pg_policies p
              WHERE p.schemaname='public' AND p.tablename=c.relname
                AND p.qual LIKE '%%branch_ids%%')
        """,
        fetch="all",
    ) or []
    assert not rows, f"جداول بـ branch_id بلا قيد فرع في سياستها: {[r['t'] for r in rows]}"


def test_bookings_are_branch_isolated(chain):
    """الغرف ليست وحدها: الحجوزات أيضاً تحمل branch_id."""
    db = chain["db"]
    db.execute(
        "INSERT INTO bookings (id, client_id, check_in, check_out, branch_id) "
        "VALUES ('bk-ruh', %s, '2026-09-01', '2026-09-02', %s)",
        (CLIENT_ID, chain["riyadh"]),
    )
    try:
        with tenant_scope(CLIENT_ID), branch_scope([chain["jeddah"]]):
            rows = db.execute("SELECT id FROM bookings WHERE id = 'bk-ruh'", fetch="all") or []
        assert rows == [], "حجز فرع الرياض ظهر لموظف فرع جدة"
    finally:
        db.execute("DELETE FROM bookings WHERE id = 'bk-ruh'")
