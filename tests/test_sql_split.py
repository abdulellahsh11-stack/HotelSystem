#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
tests/test_sql_split.py — اختبارات مُقسِّم SQL وتطبيق التحصين الأمني.

خلفية الانحدار الذي تحرسه هذه الاختبارات
────────────────────────────────────────
كان المُقسِّم القديم يعتمد على `sql.split(";")` وعلى فحص ساذج
`statement.startswith("--")` لتخطّي التعليقات. النتيجة أن 19 من 24 عبارة
في specs/db/04-isolation-hardening.sql لم تكن تُنفَّذ إطلاقاً: كل عبارة
مسبوقة بتعليق توضيحي كانت تُسقط بصمت، فبقيت app_tenant() و
app_has_perm() و audit_log و staff_roles و branches غير موجودة — بينما
تُعلن السجلات «✅ Security hardening» بنجاح.
"""

import os

import pytest

from db.sqlsplit import has_executable_sql, split_sql, strip_sql_comments

DATABASE_URL = os.environ.get("DATABASE_URL", "")
skip_no_db = pytest.mark.skipif(not DATABASE_URL, reason="DATABASE_URL not set")


# ── تقسيم العبارات ────────────────────────────────────────────────────────────

@pytest.mark.parametrize(
    "sql,expected",
    [
        ("CREATE TABLE a(id INT); CREATE TABLE b(id INT);", 2),
        ("SELECT 1", 1),
        ("SELECT 1;", 1),
        ("", 0),
        ("   \n  \n ", 0),
    ],
)
def test_basic_splitting(sql, expected):
    assert len(split_sql(sql)) == expected


def test_dollar_quote_with_language_suffix_stays_whole():
    """`$$ LANGUAGE plpgsql;` كان يكسر المُقسِّم القديم.

    الفواصل المنقوطة داخل جسم الدالة كانت تُمزّقها إلى أربع قطع، كل
    واحدة تفشل بـ «unterminated dollar-quoted string».
    """
    sql = """CREATE OR REPLACE FUNCTION update_updated_at()
RETURNS TRIGGER AS $$
BEGIN NEW.updated_at = NOW(); RETURN NEW; END;
$$ LANGUAGE plpgsql;
CREATE TABLE t(id INT);"""
    stmts = split_sql(sql)
    assert len(stmts) == 2
    assert "RETURN NEW" in stmts[0] and "LANGUAGE plpgsql" in stmts[0]
    assert stmts[1].strip().startswith("CREATE TABLE t")


def test_dollar_quote_terminated_by_dollar_semicolon():
    sql = "CREATE FUNCTION g() RETURNS void AS $$ BEGIN DELETE FROM x; END; $$;\nSELECT 1;"
    assert len(split_sql(sql)) == 2


def test_named_dollar_tag():
    sql = "CREATE FUNCTION h() RETURNS void AS $body$ BEGIN; END; $body$ LANGUAGE plpgsql;\nSELECT 1;"
    assert len(split_sql(sql)) == 2


def test_do_block():
    sql = "DO $$ BEGIN IF TRUE THEN NULL; END IF; END $$;\nSELECT 1;"
    assert len(split_sql(sql)) == 2


def test_semicolon_inside_string_literal():
    assert len(split_sql("INSERT INTO t VALUES ('a;b'); SELECT 1;")) == 2


def test_doubled_quote_escape():
    assert len(split_sql("INSERT INTO t VALUES ('it''s; here'); SELECT 1;")) == 2


def test_semicolon_inside_quoted_identifier():
    assert len(split_sql('CREATE TABLE "we;ird"(id INT); SELECT 1;')) == 2


def test_semicolon_inside_line_comment():
    assert len(split_sql("-- drop; this\nSELECT 1;")) == 1


def test_nested_block_comment():
    assert len(split_sql("/* a /* b; */ c; */ SELECT 1;")) == 1


def test_psycopg_placeholder_is_not_a_dollar_tag():
    """`$1` ليس وسم dollar-quote — لا يجوز أن يبتلع بقية الملف."""
    assert len(split_sql("SELECT * FROM t WHERE a=$1; SELECT 2;")) == 2


# ── تمييز التعليقات ───────────────────────────────────────────────────────────

@pytest.mark.parametrize(
    "statement,expected",
    [
        ("-- تعليق فقط\n", False),
        ("/* تعليق */", False),
        ("", False),
        ("   \n\n  ", False),
        ("-- عنوان القسم\nCREATE TABLE x(i INT)", True),
        ("-- أ\n/* ب */\nSELECT 1", True),
    ],
)
def test_has_executable_sql(statement, expected):
    """الفحص القديم `startswith('--')` كان يُرجع False للحالة الخامسة —
    وهي بالضبط شكل كل عبارة في الملف الأمني."""
    assert has_executable_sql(statement) is expected


def test_strip_comments_preserves_string_content():
    assert "--not a comment" in strip_sql_comments("SELECT '--not a comment';")


# ── الملف الأمني الحقيقي ──────────────────────────────────────────────────────

def _hardening_sql() -> str:
    path = os.path.join(os.path.dirname(__file__), "..", "specs", "db", "04-isolation-hardening.sql")
    with open(os.path.normpath(path), encoding="utf-8") as f:
        return f.read()


def test_every_hardening_object_survives_splitting():
    """كل كائن معرَّف في الملف الأمني يجب أن يصل إلى عبارة قابلة للتنفيذ."""
    statements = [s for s in split_sql(_hardening_sql()) if has_executable_sql(s)]
    blob = "\n".join(strip_sql_comments(s) for s in statements)

    expected = [
        "app_tenant", "app_has_perm", "app_branch_ok", "app_actor_is_guest",
        "mask_serial_id", "audit_log_immutable", "cleanup_revoked_sessions",
        "staff_roles", "staff_role_assignments", "branches", "audit_log",
        "secure_file_links", "revoked_sessions", "guest_sessions",
        "v_security_definer_audit",
    ]
    missing = [name for name in expected if name not in blob]
    assert not missing, f"كائنات ضاعت في التقسيم: {missing}"


def test_no_hardening_statement_is_dropped_as_comment():
    """لا يجوز أن تُصنَّف عبارة تحمل SQL حقيقياً ككتلة تعليقية."""
    for stmt in split_sql(_hardening_sql()):
        stripped = strip_sql_comments(stmt).strip()
        if stripped:
            assert has_executable_sql(stmt), f"عبارة أُسقطت خطأً: {stripped[:80]}"


# ── تكامل مع قاعدة بيانات حيّة ────────────────────────────────────────────────

@skip_no_db
def test_hardening_creates_every_object(db_pool):
    """التحصين الأمني يجب أن يُنشئ كائناته فعلاً — لا أن يُسجّل نجاحاً كاذباً."""
    from db.schema_v3 import (
        run_security_hardening, run_staff_app_migrations, run_v3_migrations,
    )

    run_v3_migrations(db_pool)
    run_staff_app_migrations(db_pool)
    run_security_hardening(db_pool)  # يرفع استثناءً إذا فشلت أي عبارة

    for table in ("staff_roles", "branches", "audit_log", "secure_file_links"):
        assert db_pool.execute(
            "SELECT to_regclass(%s) IS NOT NULL AS ok", (f"public.{table}",), fetch="one"
        )["ok"], f"جدول مفقود: {table}"

    for func in ("app_tenant", "app_has_perm", "app_branch_ok",
                 "app_actor_is_guest", "mask_serial_id"):
        assert db_pool.execute(
            "SELECT COUNT(*) AS n FROM pg_proc p JOIN pg_namespace n ON n.oid = p.pronamespace "
            "WHERE n.nspname = 'public' AND p.proname = %s",
            (func,), fetch="one",
        )["n"] > 0, f"دالة مفقودة: {func}"


@skip_no_db
def test_default_roles_are_seeded(db_pool):
    """الأدوار الست كانت تفشل دائماً بـ foreign key violation على client_id='system'."""
    rows = db_pool.execute(
        "SELECT role_code FROM staff_roles WHERE client_id IS NULL", fetch="all"
    )
    codes = {r["role_code"] for r in rows}
    assert {"owner", "gm", "receptionist", "housekeeper", "maintenance", "accountant"} <= codes


@skip_no_db
def test_app_has_perm_unions_all_assigned_roles(db_pool):
    """الإصدار السابق كان يستخدم LIMIT 1 بلا ترتيب، فيتجاهل بقية الأدوار."""
    db_pool.execute("DELETE FROM clients WHERE id = 'perm_t'")  # تنظيف من تشغيل سابق
    db_pool.execute("INSERT INTO clients (id, name) VALUES ('perm_t', 'اختبار')")
    emp = db_pool.execute(
        "INSERT INTO employees (client_id, employee_id, full_name_ar) "
        "VALUES ('perm_t', 'EMP-PERM-1', 'موظف') RETURNING id",
        fetch="one",
    )["id"]
    for role in ("housekeeper", "accountant"):
        db_pool.execute(
            "INSERT INTO staff_role_assignments (client_id, employee_id, role_code) "
            "VALUES ('perm_t', %s, %s) ON CONFLICT DO NOTHING", (emp, role)
        )

    def perm(p):
        return db_pool.execute(
            "SELECT app_has_perm('perm_t', %s, %s) AS ok", (emp, p), fetch="one"
        )["ok"]

    assert perm("housekeeping") is True, "صلاحية الدور الأول ضاعت"
    assert perm("invoices") is True, "صلاحية الدور الثاني ضاعت — عادت علة LIMIT 1"
    assert perm("hr") is False, "صلاحية غير ممنوحة يجب أن تُرفض"

    db_pool.execute("DELETE FROM clients WHERE id = 'perm_t'")


@skip_no_db
def test_literal_percent_in_sql_does_not_crash(db_pool):
    """`params or None` — بدونها يُفسَّر كل «%» كعلامة معامل psycopg2."""
    row = db_pool.execute("SELECT 'a.b' LIKE 'a' || '.%' AS ok", fetch="one")
    assert row["ok"] is True
