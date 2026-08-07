#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
scripts/encrypt_existing_pii.py — ترحيل أرقام الهوية المخزَّنة نصاً صريحاً.

يُشفّر القيم القائمة في:
    guests.id_number          →  id_number_enc      + id_number_bidx
    employees.national_id     →  national_id_enc    + national_id_bidx
    employees.iqama_number    →  iqama_number_enc   + iqama_number_bidx

ثم يُفرّغ العمود الصريح. آمن للتشغيل أكثر من مرة: يتخطّى الصفوف
المُرحَّلة سلفاً.

الاستخدام
─────────
    # عرض ما سيحدث دون أي تعديل
    python3 scripts/encrypt_existing_pii.py --dry-run

    # التنفيذ الفعلي
    python3 scripts/encrypt_existing_pii.py

المتطلبات: DATABASE_URL و PII_ENCRYPTION_KEY و PII_BLIND_INDEX_PEPPER.

⚠️  خُذ نسخة احتياطية قبل التشغيل. فقدان مفتاح التشفير بعد الترحيل
    يعني فقدان أرقام الهوية نهائياً.
"""
import argparse
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from db.connection import init_db  # noqa: E402
from db.crypto import blind_index, encrypt_pii, encryption_available  # noqa: E402

# (الجدول، العمود الصريح، عمود التشفير، عمود الفهرس)
TARGETS = [
    ("guests",    "id_number",    "id_number_enc",    "id_number_bidx"),
    ("employees", "national_id",  "national_id_enc",  "national_id_bidx"),
    ("employees", "iqama_number", "iqama_number_enc", "iqama_number_bidx"),
]


def migrate_column(db, table, plain_col, enc_col, bidx_col, dry_run):
    rows = db.execute(
        f"SELECT id, {plain_col} AS v FROM {table} "
        f"WHERE {plain_col} IS NOT NULL AND {plain_col} <> '' AND {enc_col} IS NULL",
        fetch="all",
    ) or []

    if not rows:
        print(f"  {table}.{plain_col}: لا شيء للترحيل")
        return 0

    if dry_run:
        print(f"  {table}.{plain_col}: {len(rows)} صفاً سيُشفَّر")
        return len(rows)

    done = 0
    for row in rows:
        try:
            db.execute(
                f"UPDATE {table} SET {enc_col} = %s, {bidx_col} = %s, {plain_col} = '' "
                f"WHERE id = %s",
                (encrypt_pii(row["v"]), blind_index(row["v"]), row["id"]),
            )
            done += 1
        except Exception as e:
            print(f"  ⚠️  {table} id={row['id']}: {e}")
    print(f"  {table}.{plain_col}: رُحّل {done} من {len(rows)}")
    return done


def main() -> int:
    parser = argparse.ArgumentParser(description="ترحيل أرقام الهوية إلى التخزين المشفَّر")
    parser.add_argument("--dry-run", action="store_true", help="عرض دون تعديل")
    args = parser.parse_args()

    database_url = os.environ.get("DATABASE_URL", "")
    if not database_url:
        print("❌ DATABASE_URL غير مضبوط")
        return 1

    if not encryption_available():
        print("❌ PII_ENCRYPTION_KEY غير مضبوط أو غير صالح.")
        print("   ولّده بـ: python3 -m db.crypto")
        return 1

    if not blind_index("1234567890"):
        print("❌ PII_BLIND_INDEX_PEPPER غير مضبوط — الفهرس الأعمى معطّل.")
        return 1

    db = init_db(database_url)
    if not db.use_postgres:
        print("❌ تعذّر الاتصال بـ PostgreSQL")
        return 1

    print("=" * 60)
    print("  ترحيل أرقام الهوية إلى التخزين المشفَّر")
    if args.dry_run:
        print("  (وضع العرض — لن يُعدَّل شيء)")
    print("=" * 60)

    total = sum(migrate_column(db, *t, args.dry_run) for t in TARGETS)

    print("-" * 60)
    if args.dry_run:
        print(f"  الإجمالي: {total} صفاً بحاجة للترحيل")
        print("  أعد التشغيل بلا --dry-run للتنفيذ.")
    else:
        print(f"  ✅ اكتمل — {total} صفاً")
    print("=" * 60)
    return 0


if __name__ == "__main__":
    sys.exit(main())
