#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
scripts/find_orphan_rows.py — الصفوف اليتيمة التي لا تخصّ أي منشأة.

الصف بـ client_id فارغ لا يملكه أحد:
  • لا تراه سياسة العزل — المقارنة بـ NULL لا تُطابق شيئاً
  • لا يظهر في أي تقرير أو قائمة
  • لا يُحذف مع المنشأة لأنه غير مرتبط بها
  • يمنع فرض NOT NULL على العمود، فيبقى الباب مفتوحاً لمزيد منه

يظهر عادةً من خطأ برمجي ينسى تمرير client_id عند الإدراج. الترحيل
التلقائي لا يحذفها — حذف البيانات قرار بشري. هذا السكربت يعرضها،
و--delete يحذفها بعد تأكيد صريح.

    python3 scripts/find_orphan_rows.py            # عرض
    python3 scripts/find_orphan_rows.py --delete   # حذف بعد تأكيد
"""
import argparse
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from db.connection import init_db  # noqa: E402

# client_id الفارغ فيه مقصود: قالب دور عام لكل المنشآت
EXEMPT = {"staff_roles"}


def find_orphans(db) -> list:
    tables = db.execute(
        """
        SELECT c.table_name AS t
        FROM information_schema.columns c
        JOIN pg_class pc ON pc.relname = c.table_name
        JOIN pg_namespace n ON n.oid = pc.relnamespace AND n.nspname = 'public'
        WHERE c.table_schema = 'public' AND c.column_name = 'client_id'
          AND pc.relkind = 'r'
        ORDER BY c.table_name
        """,
        fetch="all",
    ) or []

    found = []
    for row in tables:
        table = row["t"]
        if table in EXEMPT:
            continue
        try:
            n = db.execute(
                f"SELECT COUNT(*) AS n FROM {table} WHERE client_id IS NULL", fetch="one"
            )["n"]
            if n:
                found.append((table, n))
        except Exception as e:
            print(f"  ⚠️  تعذّر فحص {table}: {e}")
    return found


def main() -> int:
    parser = argparse.ArgumentParser(description="الصفوف اليتيمة بلا منشأة")
    parser.add_argument("--delete", action="store_true",
                        help="حذف الصفوف اليتيمة بعد تأكيد صريح")
    args = parser.parse_args()

    database_url = os.environ.get("DATABASE_URL", "")
    if not database_url:
        print("❌ DATABASE_URL غير مضبوط")
        return 1

    db = init_db(database_url)
    if not db.use_postgres:
        print("❌ تعذّر الاتصال بـ PostgreSQL")
        return 1

    print("=" * 60)
    print("  الصفوف اليتيمة — client_id فارغ")
    print("=" * 60)

    orphans = find_orphans(db)
    if not orphans:
        print("  ✅ لا صفوف يتيمة — يمكن فرض NOT NULL على كل الجداول")
        return 0

    total = sum(n for _, n in orphans)
    for table, n in orphans:
        print(f"  ⚠️  {table:28s} {n:>6} صفاً")
    print("-" * 60)
    print(f"  الإجمالي: {total} صفاً في {len(orphans)} جدولاً")

    if not args.delete:
        print()
        print("  هذه الصفوف لا يملكها أحد ولا تظهر لأي منشأة.")
        print("  راجعها قبل الحذف — قد تكشف خللاً برمجياً ما زال يُنتجها.")
        print("  للحذف: python3 scripts/find_orphan_rows.py --delete")
        return 0

    print()
    print(f"  ⚠️  ستُحذف {total} صفاً نهائياً. خُذ نسخة احتياطية أولاً.")
    if input("  اكتب «حذف» للتأكيد: ").strip() != "حذف":
        print("  أُلغي.")
        return 0

    deleted = 0
    for table, _ in orphans:
        try:
            deleted += db.execute(f"DELETE FROM {table} WHERE client_id IS NULL") or 0
        except Exception as e:
            print(f"  ❌ {table}: {e}")
    print(f"  ✅ حُذف {deleted} صفاً. أعد تشغيل التطبيق ليُفرض NOT NULL.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
