#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
db/schema_room_map.py — تخصيص خريطة الغرف

الخريطة كانت تشتقّ أسماء الأدوار من رقمٍ فقط: «الدور ١». وهذا يكفي فندقاً
صغيراً ولا يكفي منشأةً تسمّي أدوارها بأسماء («جناح الأمراء» · «الميزانين»
· «قسم العائلات»)، ولا تلك التي تريد ترتيباً غير الترتيب العددي، أو
إخفاء دورٍ تحت الصيانة من شاشة الاستقبال.

**جدولٌ منفصل لا حقلٌ في `clients.settings`.** كتلة `settings` تحوي
`_account` وفيه `pass_hash`؛ وإعادةُ كتابتها كاملةً مطبٌّ موثَّق في هذا
المستودع يقفل المنشأة نهائياً. الجدول المنفصل يجعل تخصيص الخريطة عملاً
لا يقترب من بيانات الحساب أصلاً.

**التخصيص اختياري.** دورٌ بلا صفٍّ هنا يظهر باسمه المشتقّ. فالمنشأة التي
لا تريد تخصيصاً لا تُجبَر عليه، ولا يُخفى عنها دورٌ لأنه غير مُهيّأ —
الغياب يعني «الافتراضي»، لا «مخفي».
"""
from __future__ import annotations

import logging

log = logging.getLogger("dheuof.migrations")

ROOM_MAP_STATEMENTS = (
    """
    CREATE TABLE IF NOT EXISTS room_map_floors (
        id          SERIAL PRIMARY KEY,
        client_id   VARCHAR(50) NOT NULL REFERENCES clients(id) ON DELETE CASCADE,
        floor       INTEGER NOT NULL,
        label       VARCHAR(80),
        sort_order  INTEGER DEFAULT 0,
        is_hidden   BOOLEAN DEFAULT FALSE,
        updated_at  TIMESTAMPTZ DEFAULT NOW(),
        UNIQUE (client_id, floor)
    )
    """,
    ("CREATE INDEX IF NOT EXISTS idx_room_map_client "
     "ON room_map_floors(client_id, sort_order)"),
)


def run_room_map_migration(db) -> int:
    """يُنشئ جدول تخصيص الخريطة. يُعيد عدد الجمل الناجحة."""
    done = 0
    for statement in ROOM_MAP_STATEMENTS:
        try:
            db.execute(statement)
            done += 1
        except Exception as exc:
            if "already exists" in str(exc).lower():
                done += 1
                continue
            log.error("فشلت تهيئة خريطة الغرف: %s", exc)
    return done
