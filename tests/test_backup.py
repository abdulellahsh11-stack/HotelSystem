#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
tests/test_backup.py — النسخ الاحتياطي والاستعادة المُتحقَّق منها.

لم يكن في المستودع شيء للنسخ الاحتياطي. والأهم من وجود السكربت أن يكون
تحقّقه حقيقياً: أشهر أسباب فقدان البيانات ليس غياب النسخ بل اكتشاف يوم
الحاجة أن النسخة كانت فارغة أو تالفة أو ناقصة جدولاً.

لذلك أهم اختبار هنا ليس أن النسخة السليمة تُقبل، بل أن **التالفة
تُرفض** — تحقّق يقبل كل شيء لا يختلف عن غيابه.
"""

import importlib.util
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

DATABASE_URL = os.environ.get("DATABASE_URL", "")

pytestmark = [
    pytest.mark.skipif(not DATABASE_URL, reason="DATABASE_URL not set"),
    pytest.mark.skipif(not shutil.which("pg_dump"), reason="pg_dump not installed"),
    pytest.mark.skipif(not shutil.which("pg_restore"), reason="pg_restore not installed"),
]

SCRIPT = Path(__file__).parent.parent / "scripts" / "backup.py"


def _load():
    spec = importlib.util.spec_from_file_location("backup_script", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _run(args, backup_dir):
    env = {**os.environ, "BACKUP_DIR": str(backup_dir)}
    return subprocess.run([sys.executable, str(SCRIPT), *args],
                          capture_output=True, text=True, env=env)


@pytest.fixture()
def backup_dir(tmp_path):
    return tmp_path / "backups"


@pytest.fixture(scope="module", autouse=True)
def _full_schema(db_pool):
    """conftest يُشغّل ترحيل v1 فقط.

    التحقّق يفحص وجود جداول أساسية (منها staff_roles) — وهو فحص مقصود:
    نسخة تُستعاد بلا جداول أساسية نسخةٌ ناقصة مهما بدا حجمها سليماً.
    فالقاعدة المفحوصة يجب أن تكون مُهيَّأة بالكامل.
    """
    from db.schema_v3 import (
        run_security_hardening, run_staff_app_migrations, run_v3_migrations,
        run_v4_migrations,
    )
    run_v3_migrations(db_pool)
    run_staff_app_migrations(db_pool)
    run_v4_migrations(db_pool)
    run_security_hardening(db_pool)
    db_pool.execute(
        "INSERT INTO clients (id, name) VALUES ('backup_probe', 'فندق النسخ') "
        "ON CONFLICT DO NOTHING"
    )
    yield
    db_pool.execute("DELETE FROM clients WHERE id = 'backup_probe'")


@pytest.fixture()
def a_backup(backup_dir, db_pool):
    """نسخة حقيقية من قاعدة الاختبار."""
    result = _run(["create"], backup_dir)
    assert result.returncode == 0, result.stdout + result.stderr
    dumps = list(backup_dir.glob("dheuof-*.dump"))
    assert len(dumps) == 1
    return dumps[0]


# ── الإنشاء ───────────────────────────────────────────────────────────────────

def test_backup_is_created(a_backup):
    assert a_backup.exists()
    assert a_backup.stat().st_size > 1024


def test_backup_is_listed(a_backup, backup_dir):
    out = _run(["list"], backup_dir).stdout
    assert a_backup.name in out


# ── التحقّق ───────────────────────────────────────────────────────────────────

def test_valid_backup_passes_verification(a_backup, backup_dir):
    """التحقّق يستعيد النسخة فعلاً في قاعدة مؤقتة — لا يقرأ حجم الملف."""
    result = _run(["verify", str(a_backup)], backup_dir)
    assert result.returncode == 0, result.stdout + result.stderr
    assert "سليمة" in result.stdout


def test_verification_actually_counts_restored_tables(a_backup, backup_dir):
    out = _run(["verify", str(a_backup)], backup_dir).stdout
    assert "الجداول المُستعادة" in out
    # لا معنى لنسخة بجدولين — قاعدة المنصة تتجاوز الستين
    tables = int(out.split("الجداول المُستعادة")[1].split(":")[1].split()[0])
    assert tables > 10, f"عدد الجداول المُستعادة منخفض بشكل مريب: {tables}"


def test_truncated_backup_is_rejected(a_backup, backup_dir):
    """الاختبار الأهم: تحقّق يقبل كل شيء لا يختلف عن غيابه."""
    corrupt = backup_dir / "corrupt.dump"
    corrupt.write_bytes(a_backup.read_bytes()[:4096])
    result = _run(["verify", str(corrupt)], backup_dir)
    assert result.returncode != 0, "قُبلت نسخة مبتورة"
    assert "تالفة" in result.stdout or "ناقصة" in result.stdout


def test_empty_file_is_rejected(backup_dir):
    backup_dir.mkdir(parents=True, exist_ok=True)
    empty = backup_dir / "empty.dump"
    empty.write_bytes(b"")
    assert _run(["verify", str(empty)], backup_dir).returncode != 0


def test_missing_file_is_rejected(backup_dir):
    result = _run(["verify", "/tmp/لا-يوجد-إطلاقاً.dump"], backup_dir)
    assert result.returncode != 0
    assert "غير موجود" in result.stdout


def test_verification_cleans_up_its_scratch_database(a_backup, backup_dir, db_pool):
    """قاعدة مؤقتة متروكة تُراكم مساحة عند كل تحقّق دوري."""
    _run(["verify", str(a_backup)], backup_dir)
    leftovers = db_pool.execute(
        "SELECT datname FROM pg_database WHERE datname LIKE 'dheuof_verify_%%'",
        fetch="all",
    ) or []
    assert not leftovers, f"قواعد تحقّق متروكة: {[d['datname'] for d in leftovers]}"


# ── الاحتفاظ ──────────────────────────────────────────────────────────────────

def test_prune_keeps_recent_backups(a_backup, backup_dir):
    result = _run(["prune", "--keep-days", "30"], backup_dir)
    assert result.returncode == 0
    assert a_backup.exists(), "حُذفت نسخة حديثة"


def test_prune_dry_run_deletes_nothing(a_backup, backup_dir):
    _run(["prune", "--keep-days", "0", "--dry-run"], backup_dir)
    assert a_backup.exists(), "--dry-run حذف ملفاً"


def test_prune_removes_old_backups(a_backup, backup_dir):
    old = backup_dir / "dheuof-20200101T000000Z.dump"
    old.write_bytes(b"x" * 2048)
    os.utime(old, (0, 0))
    _run(["prune", "--keep-days", "30"], backup_dir)
    assert not old.exists(), "لم تُحذف نسخة قديمة"
    assert a_backup.exists()


# ── سلامة الوحدة ──────────────────────────────────────────────────────────────

def test_admin_url_swaps_only_the_database_name():
    module = _load()
    swapped = module._admin_url(
        "postgresql://user:pass@host:5432/original?sslmode=require", "scratch"
    )
    assert "/scratch" in swapped
    assert "original" not in swapped
    assert "sslmode=require" in swapped, "ضاعت معاملات الاتصال"
    assert "user:pass@host:5432" in swapped
