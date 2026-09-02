#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
db/schema_visitors.py — جداول الزوّار وحجوزاتهم

الزائر ليس نزيلاً وليس موظفاً: هو من يحجز لنفسه من بوابة الحجز العامّة
قبل أن يصل. جدولٌ مستقلّ لأن خلطه بـ`guests` يعني أن حسابَ دخولٍ عام
يقع في نفس الجدول الذي يحمل هويات النزلاء المشفّرة.

    visitors           حساب الزائر · بريد وجوال واسم — بلا رقم هوية
    visitor_sessions   جلساته · كوكي منفصلة عن كوكي المنشأة
    visitor_bookings   طلبات حجزه · تنتظر تأكيد المنشأة

**لا رقم هوية في `visitors`.** الزائر يحجز باسمه وجواله؛ والهوية
تُؤخذ عند الوصول من موظفٍ مخوَّل، بشاشةٍ تُشفّرها. جمعُها من نموذجٍ
عامّ يعني تخزين هوياتٍ لم يتحقّق منها أحد.
"""
from __future__ import annotations

import logging

log = logging.getLogger("dheuof.migrations")

VISITOR_SCHEMA = """
CREATE TABLE IF NOT EXISTS visitors (
    id          SERIAL PRIMARY KEY,
    client_id   VARCHAR(50) NOT NULL,
    full_name   VARCHAR(200) NOT NULL,
    phone       VARCHAR(30)  NOT NULL,
    email       VARCHAR(200),
    pass_hash   TEXT NOT NULL,
    pass_salt   TEXT NOT NULL,
    is_active   BOOLEAN DEFAULT TRUE,
    created_at  TIMESTAMPTZ DEFAULT NOW(),
    last_login  TIMESTAMPTZ,
    UNIQUE (client_id, phone)
);
CREATE INDEX IF NOT EXISTS idx_visitors_client ON visitors(client_id);

CREATE TABLE IF NOT EXISTS visitor_sessions (
    token       VARCHAR(64) PRIMARY KEY,
    visitor_id  INTEGER NOT NULL REFERENCES visitors(id) ON DELETE CASCADE,
    client_id   VARCHAR(50) NOT NULL,
    created_at  TIMESTAMPTZ DEFAULT NOW(),
    expires_at  TIMESTAMPTZ NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_vsess_visitor ON visitor_sessions(visitor_id);
CREATE INDEX IF NOT EXISTS idx_vsess_exp     ON visitor_sessions(expires_at);

CREATE TABLE IF NOT EXISTS visitor_bookings (
    id           VARCHAR(50) PRIMARY KEY,
    client_id    VARCHAR(50) NOT NULL,
    visitor_id   INTEGER NOT NULL REFERENCES visitors(id) ON DELETE CASCADE,
    room_type    VARCHAR(50),
    check_in     DATE NOT NULL,
    check_out    DATE NOT NULL,
    guests_count INTEGER DEFAULT 1,
    notes        TEXT,
    status       VARCHAR(20) DEFAULT 'pending',
    booking_id   VARCHAR(50),
    created_at   TIMESTAMPTZ DEFAULT NOW(),
    CHECK (check_out > check_in),
    CHECK (guests_count BETWEEN 1 AND 20)
);
CREATE INDEX IF NOT EXISTS idx_vbook_client  ON visitor_bookings(client_id);
CREATE INDEX IF NOT EXISTS idx_vbook_visitor ON visitor_bookings(visitor_id);
CREATE INDEX IF NOT EXISTS idx_vbook_status  ON visitor_bookings(client_id, status)
"""


def run_visitor_migrations(db) -> None:
    """
    يُنشئ جداول الزوّار.

    التقسيم على `;` وحده كان يُسقط كل عبارةٍ مسبوقة بتعليق — والملف
    كلما حَسُن توثيقه سقط منه أكثر. لا تعليقات داخل هذا النصّ عمداً،
    وشرحُ كل جدولٍ في مقدّمة الملف.
    """
    if not getattr(db, "use_postgres", False):
        return
    made = 0
    for stmt in VISITOR_SCHEMA.split(";"):
        stmt = stmt.strip()
        if not stmt:
            continue
        try:
            db.execute(stmt)
            made += 1
        except Exception as exc:
            # الفشل يُسجَّل ولا يُبتلع: جدولٌ ناقص يعني بوابةً معطّلة
            # بلا أن يعلم أحد، وهي السابقة نفسها التي كلّفت هذا المستودع.
            log.error("فشل إنشاء جدول زوّار: %s — %s", stmt.split("\n")[0][:60], exc)
            raise
    log.info("جداول الزوّار: %s عبارة نُفّذت", made)
