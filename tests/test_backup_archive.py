#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
tests/test_backup_archive.py — النسخة الاحتياطية الشهرية

يثبت ثلاثة أشياء لا يكفي فيها فحص الكود:
١ — الأرشيف يُبنى ويُفتح فعلاً ويحوي ما يُتوقَّع.
٢ — لا يخرج سرٌّ في النسخة (كلمات المرور والمفاتيح).
٣ — كل استعلام يحمل client_id — فلا تتسرّب بيانات منشأة إلى نسخة أخرى.
"""
from __future__ import annotations

import io
import json
import zipfile

from services.backup_archive import EXPORT_TABLES, archive_filename, build_archive


class _FakeDB:
    """قاعدة بيانات وهمية تسجّل كل استعلام ومعاملاته للتحقق من العزل."""

    use_postgres = True

    def __init__(self, rows_by_table: dict[str, list[dict]] | None = None):
        self.rows_by_table = rows_by_table or {}
        self.queries: list[tuple[str, tuple]] = []

    def execute(self, sql, params=(), fetch=None):
        self.queries.append((" ".join(sql.split()), params))
        for table, rows in self.rows_by_table.items():
            if f"FROM {table} " in sql or sql.rstrip().endswith(f"FROM {table}"):
                return rows
        return []


def test_archive_is_a_valid_zip_with_manifest():
    db = _FakeDB({"guests": [{"id": 1, "full_name": "ضيف تجريبي", "client_id": "c1"}]})
    content, manifest = build_archive(db, "c1", "2026-08")

    with zipfile.ZipFile(io.BytesIO(content)) as zf:
        assert zf.testzip() is None, "الأرشيف تالف"
        names = set(zf.namelist())
        assert "manifest.json" in names
        for table in EXPORT_TABLES:
            assert f"data/{table}.json" in names, f"الجدول {table} مفقود من الأرشيف"

        guests = json.loads(zf.read("data/guests.json"))
        assert guests[0]["full_name"] == "ضيف تجريبي"

    assert manifest["client_id"] == "c1"
    assert manifest["period"] == "2026-08"
    assert manifest["total_rows"] == 1
    assert len(manifest["sha256"]) == 64


def test_every_query_is_scoped_to_one_client():
    """العزل: لا استعلام في النسخة بلا client_id، ولا بمعرّف منشأة أخرى."""
    db = _FakeDB()
    build_archive(db, "client_A", "2026-08")

    assert db.queries, "لم يُنفَّذ أي استعلام"
    for sql, params in db.queries:
        assert "WHERE client_id=%s" in sql, f"استعلام بلا عزل: {sql}"
        assert params == ("client_A",), f"معاملات خاطئة: {params}"


def test_secrets_are_never_written_to_the_archive():
    db = _FakeDB({
        "employees": [{
            "id": 7, "client_id": "c1", "name": "موظف",
            "pass_hash": "سر-لا-يخرج", "api_key": "مفتاح-لا-يخرج",
        }],
    })
    content, _ = build_archive(db, "c1", "2026-08")

    with zipfile.ZipFile(io.BytesIO(content)) as zf:
        rows = json.loads(zf.read("data/employees.json"))
        assert rows[0]["name"] == "موظف"
        assert "pass_hash" not in rows[0]
        assert "api_key" not in rows[0]

    assert b"\xd8\xb3\xd8\xb1-\xd9\x84\xd8\xa7-\xd9\x8a\xd8\xae\xd8\xb1\xd8\xac" not in content


def test_missing_table_does_not_break_the_whole_backup():
    """جدول غير موجود في تركيب ما لا يُسقط النسخة كلها."""
    class _Broken(_FakeDB):
        def execute(self, sql, params=(), fetch=None):
            raise RuntimeError('relation "guests" does not exist')

    content, manifest = build_archive(_Broken(), "c1", "2026-08")
    assert manifest["total_rows"] == 0
    with zipfile.ZipFile(io.BytesIO(content)) as zf:
        assert zf.testzip() is None


def test_filename_carries_client_and_period():
    assert archive_filename("client_9", "2026-08") == "duyuf_backup_client_9_2026-08.zip"
    # لا يسمح بمحارف مسار في الاسم
    assert "/" not in archive_filename("../../etc/passwd", "2026-08")
