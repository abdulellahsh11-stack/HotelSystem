#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
scripts/encrypt_existing_guests.py — تشفير صفوف النزلاء القائمة

يُشغَّل **مرةً واحدة** بعد ضبط المفتاح وقبل فتح المنصة للاستخدام.

لماذا سكربت منفصل لا ترحيل عند الإقلاع؟ لأن ترحيل المخطط يجري في كل
إقلاع، وتشفيرُ صفوفٍ بمفتاحٍ ناقصٍ أو خاطئ يُتلفها **بلا رجعة**. هذا
عملٌ يُقرَّر مرةً بيدٍ واعية، لا يقع تلقائياً.

## قبل التشغيل

```bash
# ١ — ولّد مفتاحين منفصلين واحفظهما خارج المنصة
python3 -c "from services.guest_crypto import generate_key; print(generate_key())"

# ٢ — خذ نسخةً احتياطيةً من قاعدة البيانات. هذه ليست توصية.
pg_dump "$DATABASE_URL" > backup_before_encryption.sql

# ٣ — جرّب بلا كتابة أولاً
DATABASE_URL=... GUEST_ENCRYPTION_KEY=... python3 scripts/encrypt_existing_guests.py --dry-run

# ٤ — نفّذ
DATABASE_URL=... GUEST_ENCRYPTION_KEY=... python3 scripts/encrypt_existing_guests.py --apply
```

قابلٌ لإعادة التشغيل: الصفّ المشفَّر يُتخطّى، فانقطاعُ التشغيل في
منتصفه لا يُفسد شيئاً — أعِد تشغيله.
"""
from __future__ import annotations

import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from services import guest_crypto  # noqa: E402

BATCH = 200


def main() -> int:
    parser = argparse.ArgumentParser(description="تشفير بيانات النزلاء القائمة")
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--dry-run", action="store_true", help="إحصاء بلا كتابة")
    mode.add_argument("--apply", action="store_true", help="التنفيذ الفعلي")
    args = parser.parse_args()

    if not guest_crypto.is_enabled():
        print(f"✗ {guest_crypto.KEY_ENV} غير مضبوط — لا شيء يُنفَّذ.")
        return 2

    # تحقّق من أن المفتاح يعمل قبل لمس أي صفّ
    probe = guest_crypto.encrypt("اختبار-المفتاح")
    if guest_crypto.decrypt(probe) != "اختبار-المفتاح":
        print("✗ المفتاح لا يفكّ ما يُشفّره — أوقفتُ العملية.")
        return 2
    print("✓ المفتاح سليم (شُفّر ونصٌّ فُكّ ومُطابق)")

    from db.connection import DatabasePool

    db = DatabasePool()
    rows = db.execute(
        "SELECT id, client_id, id_number, absher_phone, birth_date, notes "
        "FROM guests ORDER BY id", fetch="all") or []
    print(f"  صفوف النزلاء: {len(rows)}")

    todo = []
    for row in rows:
        data = dict(row)
        if any(guest_crypto.is_encrypted(data.get(f))
               for f in guest_crypto.ENCRYPTED_FIELDS):
            continue                      # مشفَّر سابقاً
        if not any(data.get(f) for f in guest_crypto.ENCRYPTED_FIELDS):
            continue                      # لا شيء حسّاس فيه
        todo.append(data)

    print(f"  يحتاج تشفيراً: {len(todo)}")
    print(f"  مشفَّر أو فارغ: {len(rows) - len(todo)}")

    if args.dry_run:
        print("\n(تجربة بلا كتابة — أعِد التشغيل بـ--apply للتنفيذ)")
        return 0

    done = failed = 0
    for row in todo:
        try:
            enc = guest_crypto.encrypt_guest(row)
            db.execute(
                """UPDATE guests SET id_number=%s, absher_phone=%s,
                          birth_date=%s, notes=%s, id_number_bidx=%s
                   WHERE id=%s AND client_id=%s""",
                (enc.get("id_number"), enc.get("absher_phone"),
                 enc.get("birth_date"), enc.get("notes"),
                 enc.get("id_number_bidx"), row["id"], row["client_id"]))
            done += 1
            if done % BATCH == 0:
                print(f"  … {done}/{len(todo)}")
        except Exception as exc:
            failed += 1
            # المعرّف وحده في السجلّ — لا بيانات النزيل
            print(f"  ✗ فشل الصفّ {row['id']}: {type(exc).__name__}: {exc}")

    print(f"\n✓ شُفّر: {done}   ✗ فشل: {failed}")
    if failed:
        print("  أعِد التشغيل بعد معالجة الأسباب — الصفوف الناجحة تُتخطّى.")
        return 1
    print("  احفظ المفتاح خارج المنصة. فقدانه = فقدان أرقام الهوية نهائياً.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
