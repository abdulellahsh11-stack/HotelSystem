#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
db/schema_guest_crypto.py — تهيئة الجدول لتشفير بيانات النزلاء

ثلاثة تغييرات لازمة قبل أن يُخزَّن أول نصٍّ مشفَّر:

**١ — توسيع الأعمدة.** `id_number VARCHAR(20)` يكفي رقم هوية، ولا يكفي
نصّاً مشفَّراً (نحو ١٠٠ محرف). الإدخال في عمودٍ ضيّق يفشل بخطأ قاعدة
بيانات خام — أو الأسوأ: يُبتَر الرقم فلا يُفكّ أبداً.

**٢ — عمود الفهرس الأعمى.** `id_number_bidx` بصمة HMAC ثابتة تُتيح
البحث برقم الهوية دون تخزينه. طولها ٦٤ محرفاً (SHA-256 بالست عشري).

**٣ — إسقاط الفهرس القديم.** `idx_guests_id_number` على النصّ المشفَّر
عديم الفائدة: لا استعلام يُطابقه، ويشغل مساحةً ويُبطئ الكتابة.

> `birth_date` يتحوّل من `DATE` إلى `TEXT` ليحمل نصّاً مشفَّراً. لا
> استعلام في المنصة يُجري حساباً على هذا العمود، فالتحويل بلا أثر
> تشغيلي. ولو احتيج حساب العمر لاحقاً فمكانه التطبيق بعد الفكّ.

**الترحيل لا يُشفّر البيانات القائمة.** ذلك عملٌ منفصل بمفتاحٍ حاضر،
في `scripts/encrypt_existing_guests.py` — لأن ترحيل المخطط يجري عند كل
إقلاع، وتشفير صفوفٍ بمفتاحٍ ناقص يُتلفها بلا رجعة.
"""
from __future__ import annotations

import logging

log = logging.getLogger("dheuof.migrations")

# كل جملة مستقلة وقابلة لإعادة التشغيل. الترتيب مقصود: التوسيع قبل
# الفهرسة، وإسقاط الفهرس القديم أخيراً.
GUEST_CRYPTO_STATEMENTS = (
    # ١ — أعمدة تتّسع للنصّ المشفَّر
    "ALTER TABLE guests ALTER COLUMN id_number TYPE TEXT",
    "ALTER TABLE guests ALTER COLUMN absher_phone TYPE TEXT",
    "ALTER TABLE guests ALTER COLUMN birth_date TYPE TEXT USING birth_date::TEXT",
    # ٢ — الفهرس الأعمى
    "ALTER TABLE guests ADD COLUMN IF NOT EXISTS id_number_bidx VARCHAR(64)",
    ("CREATE INDEX IF NOT EXISTS idx_guests_bidx "
     "ON guests(client_id, id_number_bidx)"),
    # ٣ — الفهرس القديم على نصٍّ صار مشفَّراً
    "DROP INDEX IF EXISTS idx_guests_id_number",
)


def run_guest_crypto_migration(db) -> int:
    """
    يُهيّئ جدول النزلاء للتشفير. يُعيد عدد الجمل التي نُفِّذت بنجاح.

    الفشل يُسجَّل ولا يُبتلع صامتاً: عمودٌ لم يتّسع يعني أن أول حفظٍ
    مشفَّر سيفشل، ومعرفة السبب الآن أهون من مطاردته لاحقاً.
    """
    done = 0
    for statement in GUEST_CRYPTO_STATEMENTS:
        try:
            db.execute(statement)
            done += 1
        except Exception as exc:
            text = str(exc).lower()
            # «موجود مسبقاً» ليس فشلاً — الترحيل يُعاد عند كل إقلاع
            if "already exists" in text or "does not exist" in text:
                done += 1
                continue
            log.error("فشلت جملة تهيئة تشفير النزلاء [%s]: %s", statement[:60], exc)
    log.info("تهيئة تشفير بيانات النزلاء: %s/%s", done, len(GUEST_CRYPTO_STATEMENTS))
    return done
