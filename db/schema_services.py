#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
db/schema_services.py — خدمات الحجز: الإفطار والتوصيل

جدولٌ واحد لا عمودان على `bookings`، لأن الخدمة لها **تاريخ وحالة**:
إفطار الثلاثاء يُقدَّم أو لا يُقدَّم بمعزلٍ عن إفطار الأربعاء، وتوصيل
الوصول غير توصيل المغادرة. عمودٌ منطقي على الحجز لا يحمل ذلك.

وهو ما يجعل قائمة التشغيل اليومية ممكنة: استعلامٌ واحد بالتاريخ يُعطي
المطبخ ما عليه اليوم، والسائق ما عليه اليوم — من نفس الصفوف التي
سجّلها الاستقبال على الحجز. تطبيقان يقرآن مصدراً واحداً.
"""
from __future__ import annotations

import logging

log = logging.getLogger("dheuof.db.services")

# أنواع الخدمات المدعومة. تُقرأ في الخادم والواجهة معاً، فتُعرَّف هنا
# مرة واحدة بدل تكرارها في كل موضع.
SERVICE_TYPES = ("breakfast", "delivery")

SERVICE_LABELS = {
    "breakfast": "الإفطار",
    "delivery": "التوصيل",
}

# حالات الخدمة — دورة حياة واحدة للنوعين
SERVICE_STATUSES = ("pending", "done", "cancelled")

SERVICES_SCHEMA = """
CREATE TABLE IF NOT EXISTS booking_services (
    id            SERIAL PRIMARY KEY,
    client_id     VARCHAR(50) NOT NULL REFERENCES clients(id) ON DELETE CASCADE,
    booking_id    VARCHAR(50) NOT NULL,
    service_type  VARCHAR(20) NOT NULL,
    service_date  DATE        NOT NULL,
    quantity      INTEGER     NOT NULL DEFAULT 1,
    unit_price    DECIMAL(10,2) NOT NULL DEFAULT 0,
    status        VARCHAR(20) NOT NULL DEFAULT 'pending',
    -- التوصيل يحتاج وجهةً ووقتاً؛ الإفطار لا. عمودان اختياريان أهون
    -- من جدولين متشابهين.
    destination   VARCHAR(200),
    scheduled_at  TIME,
    notes         TEXT,
    created_at    TIMESTAMPTZ DEFAULT NOW(),
    created_by    VARCHAR(60),
    -- خدمةٌ واحدة من كل نوع في اليوم الواحد للحجز الواحد. تكرارها
    -- يعني ازدواج فاتورة وازدواج تحضير في المطبخ.
    UNIQUE(client_id, booking_id, service_type, service_date)
);
CREATE INDEX IF NOT EXISTS idx_bsvc_tenant_date
    ON booking_services(client_id, service_date, service_type);
CREATE INDEX IF NOT EXISTS idx_bsvc_booking
    ON booking_services(client_id, booking_id)
"""


def run_services_migration(db) -> None:
    """يُنشئ جدول خدمات الحجز. آمنٌ للتكرار."""
    if not getattr(db, "use_postgres", False):
        return
    for statement in SERVICES_SCHEMA.split(";"):
        sql = statement.strip()
        if not sql:
            continue
        try:
            db.execute(sql)
        except Exception as exc:
            if "already exists" not in str(exc).lower():
                log.warning("ترحيل خدمات الحجز: %s", exc)
    log.info("✅ خدمات الحجز — booking_services")
