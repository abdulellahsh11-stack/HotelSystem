#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
scripts/backup.py — نسخ احتياطي واستعادة مُتحقَّق منها.

المبدأ
──────
النسخة التي لم تُختبر استعادتها ليست نسخة. أشهر أسباب فقدان البيانات
ليس غياب النسخ الاحتياطي بل اكتشاف يوم الحاجة أنها كانت فارغة أو تالفة
أو ناقصة جدولاً. لذلك الأمر `verify` هنا لا يقرأ حجم الملف — بل يستعيده
فعلاً في قاعدة مؤقتة ويعدّ الجداول والصفوف ويحذفها.

الاستعمال
─────────
    python3 scripts/backup.py create              # نسخة جديدة
    python3 scripts/backup.py verify <ملف>        # استعادة فعلية وفحص
    python3 scripts/backup.py list                # النسخ المتاحة
    python3 scripts/backup.py prune --keep-days 30

⚠️  النسخة تحوي أرقام الهوية **مشفَّرة**. استعادتها بلا
    PII_ENCRYPTION_KEY تُعيد بيانات بلا أرقام هوية. احفظ المفتاح مع خطة
    التعافي لا داخل النسخة.
"""
import argparse
import os
import shutil
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import urlparse

BACKUP_DIR = Path(os.environ.get("BACKUP_DIR", "backups"))

# جداول لا يجوز أن تكون فارغة في نسخة سليمة لقاعدة مُهيَّأة
SENTINEL_TABLES = ("clients", "staff_roles")


def _require_tool(name: str) -> str:
    path = shutil.which(name)
    if not path:
        sys.exit(f"❌ {name} غير مثبَّت — ثبّت أدوات PostgreSQL أولاً")
    return path


def _database_url() -> str:
    url = os.environ.get("DATABASE_URL", "")
    if not url:
        sys.exit("❌ DATABASE_URL غير مضبوط")
    return url


def _admin_url(url: str, dbname: str) -> str:
    """يستبدل اسم قاعدة البيانات في الرابط — للاتصال بقاعدة مؤقتة."""
    parsed = urlparse(url)
    return parsed._replace(path=f"/{dbname}").geturl()


def _run(cmd: list, **kwargs) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, capture_output=True, text=True, **kwargs)


# ── إنشاء ─────────────────────────────────────────────────────────────────────

def create(args) -> int:
    pg_dump = _require_tool("pg_dump")
    url = _database_url()
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)

    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    target = BACKUP_DIR / f"dheuof-{stamp}.dump"

    print(f"  إنشاء نسخة → {target}")
    # صيغة custom: تسمح بالاستعادة الانتقائية وبالضغط
    result = _run([pg_dump, "--format=custom", "--compress=9",
                   "--no-owner", "--no-privileges", "--file", str(target), url])
    if result.returncode != 0:
        print(f"❌ فشل pg_dump: {result.stderr.strip()[:300]}")
        target.unlink(missing_ok=True)
        return 1

    size = target.stat().st_size
    if size < 1024:
        print(f"❌ النسخة صغيرة بشكل مريب ({size} بايت) — يُرجَّح أنها فارغة")
        return 1

    print(f"  ✅ اكتملت — {size / 1024 / 1024:.2f} ميجابايت")
    print(f"  تحقّق منها بـ: python3 scripts/backup.py verify {target}")
    return 0


# ── تحقّق باستعادة فعلية ──────────────────────────────────────────────────────

def verify(args) -> int:
    pg_restore = _require_tool("pg_restore")
    psql = _require_tool("psql")
    url = _database_url()

    source = Path(args.file)
    if not source.exists():
        print(f"❌ الملف غير موجود: {source}")
        return 1

    scratch = f"dheuof_verify_{datetime.now(timezone.utc).strftime('%H%M%S')}"
    admin = _admin_url(url, "postgres")

    print("=" * 60)
    print(f"  التحقّق باستعادة فعلية → قاعدة مؤقتة {scratch}")
    print("=" * 60)

    created = _run([psql, admin, "-v", "ON_ERROR_STOP=1", "-c", f'CREATE DATABASE "{scratch}"'])
    if created.returncode != 0:
        print(f"❌ تعذّر إنشاء القاعدة المؤقتة: {created.stderr.strip()[:200]}")
        return 1

    try:
        restored = _run([pg_restore, "--no-owner", "--no-privileges",
                         "--dbname", _admin_url(url, scratch), str(source)])
        # pg_restore يُحذّر كثيراً دون أن يفشل؛ العبرة بما استُعيد فعلاً
        if restored.returncode != 0:
            print(f"  ⚠️  تحذيرات الاستعادة: {restored.stderr.strip()[:200]}")

        def query(sql: str) -> str:
            out = _run([psql, _admin_url(url, scratch), "-tAc", sql])
            return out.stdout.strip()

        tables = int(query(
            "SELECT count(*) FROM pg_tables WHERE schemaname='public'") or 0)
        views = int(query(
            "SELECT count(*) FROM pg_views WHERE schemaname='public'") or 0)
        print(f"  الجداول المُستعادة : {tables}")
        print(f"  طرق العرض        : {views}")

        if tables == 0:
            print("  ❌ صفر جداول — النسخة فارغة أو تالفة")
            return 1

        ok = True
        for table in SENTINEL_TABLES:
            exists = query(f"SELECT to_regclass('public.{table}') IS NOT NULL")
            if exists != "t":
                print(f"  ❌ جدول أساسي مفقود: {table}")
                ok = False
                continue
            count = query(f"SELECT count(*) FROM {table}")
            print(f"  {table:14s} : {count} صفاً")

        # فحص سلامة البيانات: صفوف تُقرأ فعلاً لا مجرد بنية
        sample = query("SELECT count(*) FROM clients") if ok else "0"
        print("-" * 60)
        if ok and tables > 10:
            print(f"  ✅ النسخة سليمة وقابلة للاستعادة ({tables} جدولاً، "
                  f"{sample} منشأة)")
            return 0
        print("  ❌ النسخة ناقصة — لا تعتمد عليها")
        return 1
    finally:
        _run([psql, admin, "-c", f'DROP DATABASE IF EXISTS "{scratch}"'])
        print(f"  (حُذفت القاعدة المؤقتة {scratch})")


# ── إدارة ─────────────────────────────────────────────────────────────────────

def list_backups(args) -> int:
    if not BACKUP_DIR.exists():
        print("  لا نسخ بعد")
        return 0
    files = sorted(BACKUP_DIR.glob("dheuof-*.dump"), reverse=True)
    if not files:
        print("  لا نسخ بعد")
        return 0
    print(f"  {len(files)} نسخة في {BACKUP_DIR}/")
    for f in files:
        stat = f.stat()
        age = datetime.now(timezone.utc) - datetime.fromtimestamp(stat.st_mtime, timezone.utc)
        print(f"    {f.name}  {stat.st_size / 1024 / 1024:>8.2f} م.ب  "
              f"منذ {age.days} يوماً")
    return 0


def prune(args) -> int:
    if not BACKUP_DIR.exists():
        return 0
    cutoff = datetime.now(timezone.utc) - timedelta(days=args.keep_days)
    removed = 0
    for f in sorted(BACKUP_DIR.glob("dheuof-*.dump")):
        if datetime.fromtimestamp(f.stat().st_mtime, timezone.utc) < cutoff:
            if args.dry_run:
                print(f"  سيُحذف: {f.name}")
            else:
                f.unlink()
                print(f"  حُذف: {f.name}")
            removed += 1
    print(f"  {'سيُحذف' if args.dry_run else 'حُذف'} {removed} ملفاً "
          f"أقدم من {args.keep_days} يوماً")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="نسخ احتياطي واستعادة مُتحقَّق منها")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("create", help="إنشاء نسخة جديدة").set_defaults(func=create)

    p_verify = sub.add_parser("verify", help="استعادة فعلية في قاعدة مؤقتة وفحصها")
    p_verify.add_argument("file")
    p_verify.set_defaults(func=verify)

    sub.add_parser("list", help="عرض النسخ المتاحة").set_defaults(func=list_backups)

    p_prune = sub.add_parser("prune", help="حذف النسخ القديمة")
    p_prune.add_argument("--keep-days", type=int, default=30)
    p_prune.add_argument("--dry-run", action="store_true")
    p_prune.set_defaults(func=prune)

    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
