#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
scripts/backup_postgres.py — PostgreSQL Automated Backup
=========================================================
إنشاء نسخ احتياطية مؤقتة من قاعدة بيانات PostgreSQL.

الاستخدام:
    python scripts/backup_postgres.py
    python scripts/backup_postgres.py --keep 14   # احتفظ بآخر 14 نسخة
    python scripts/backup_postgres.py --dir /path/to/backups

متغيرات البيئة:
    DATABASE_URL   — postgresql://user:pass@host:port/db  (مطلوب)
    BACKUP_DIR     — مجلد النسخ الاحتياطية  (افتراضي: ./backups)
    BACKUP_KEEP    — عدد النسخ المحتفظ بها  (افتراضي: 7)

الجدولة (cron) — كل يوم الساعة 2:00 صباحاً:
    0 2 * * * cd /app && python scripts/backup_postgres.py >> /var/log/backup.log 2>&1
"""

import argparse
import gzip
import logging
import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
)
log = logging.getLogger("dheuof.backup")

DEFAULT_KEEP = 7
DEFAULT_DIR = Path("backups")


def parse_db_url(url: str) -> dict:
    """تحليل DATABASE_URL وإرجاع مكوّناته."""
    p = urlparse(url)
    return {
        "host": p.hostname or "localhost",
        "port": str(p.port or 5432),
        "user": p.username or "",
        "password": p.password or "",
        "dbname": (p.path or "/").lstrip("/"),
    }


def run_backup(db_url: str, backup_dir: Path, keep: int) -> Path:
    """
    تشغيل pg_dump وضغط الناتج.
    يُعيد مسار ملف النسخة الاحتياطية عند النجاح.
    """
    backup_dir.mkdir(parents=True, exist_ok=True)

    creds = parse_db_url(db_url)
    ts = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    filename = f"dheuof_backup_{ts}.sql.gz"
    output_path = backup_dir / filename

    env = os.environ.copy()
    if creds["password"]:
        env["PGPASSWORD"] = creds["password"]

    pg_dump_cmd = [
        "pg_dump",
        "--host", creds["host"],
        "--port", creds["port"],
        "--username", creds["user"],
        "--no-password",
        "--format", "plain",
        "--no-owner",
        "--no-privileges",
        creds["dbname"],
    ]

    log.info(f"Starting backup → {output_path}")
    try:
        proc = subprocess.run(
            pg_dump_cmd,
            env=env,
            capture_output=True,
            timeout=600,  # 10 minutes max
        )
    except FileNotFoundError:
        log.error("pg_dump not found — install postgresql-client")
        sys.exit(1)
    except subprocess.TimeoutExpired:
        log.error("pg_dump timed out after 10 minutes")
        sys.exit(1)

    if proc.returncode != 0:
        stderr = proc.stderr.decode("utf-8", errors="replace")
        log.error(f"pg_dump failed (exit {proc.returncode}):\n{stderr}")
        sys.exit(1)

    # Compress output
    with gzip.open(output_path, "wb", compresslevel=6) as gz:
        gz.write(proc.stdout)

    size_mb = output_path.stat().st_size / (1024 * 1024)
    log.info(f"✓ Backup complete — {output_path.name} ({size_mb:.2f} MB)")

    _rotate_old_backups(backup_dir, keep)
    return output_path


def _rotate_old_backups(backup_dir: Path, keep: int) -> None:
    """حذف النسخ الاحتياطية القديمة مع الاحتفاظ بآخر `keep` نسخة."""
    backups = sorted(
        backup_dir.glob("dheuof_backup_*.sql.gz"),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )
    to_delete = backups[keep:]
    for old in to_delete:
        try:
            old.unlink()
            log.info(f"Rotated old backup: {old.name}")
        except Exception as exc:
            log.warning(f"Could not delete {old.name}: {exc}")


def verify_backup(path: Path) -> bool:
    """تحقق بسيط: تأكد أن ملف .gz صالح وغير فارغ."""
    if not path.exists() or path.stat().st_size == 0:
        log.error("Backup file missing or empty")
        return False
    try:
        with gzip.open(path, "rb") as gz:
            first_bytes = gz.read(128)
            if b"PostgreSQL" not in first_bytes and b"--" not in first_bytes:
                log.warning("Backup header looks unexpected — check contents")
            else:
                log.info("✓ Backup file verified (valid gzip + SQL header)")
        return True
    except Exception as exc:
        log.error(f"Backup verification failed: {exc}")
        return False


def main():
    parser = argparse.ArgumentParser(description="Dheuof PostgreSQL Backup")
    parser.add_argument("--dir", default=os.environ.get("BACKUP_DIR", str(DEFAULT_DIR)),
                        help="Backup directory (default: ./backups)")
    parser.add_argument("--keep", type=int, default=int(os.environ.get("BACKUP_KEEP", DEFAULT_KEEP)),
                        help="Number of backups to keep (default: 7)")
    parser.add_argument("--verify", action="store_true", default=True,
                        help="Verify backup after creation (default: True)")
    args = parser.parse_args()

    db_url = os.environ.get("DATABASE_URL", "")
    if not db_url:
        log.error("DATABASE_URL environment variable is not set")
        sys.exit(1)

    backup_path = run_backup(db_url, Path(args.dir), args.keep)

    if args.verify:
        ok = verify_backup(backup_path)
        if not ok:
            sys.exit(2)

    log.info(f"Backup finished successfully: {backup_path}")


if __name__ == "__main__":
    main()
