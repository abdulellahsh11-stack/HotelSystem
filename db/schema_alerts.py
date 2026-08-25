#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
db/schema_alerts.py — إنذارات المفتاح الذكي وقنوات تبليغها

ثلاثة جداول لأن لكلٍّ عمراً مختلفاً:

`smart_alerts`      — الحدث نفسه: باب بقي مفتوحاً، بطارية قفلٍ ضعُفت.
`alert_deliveries`  — محاولة تبليغٍ واحدة عبر قناة واحدة. سجلٌّ منفصل
                      لأن الإنذار الواحد يُبلَّغ بثلاث قنوات، وقد تنجح
                      واحدة وتفشل أخرى — ودمجهما يُخفي أيّهما وصل.
`sms_credits`       — رصيد الرسائل النصية. الرسالة تُكلّف مالاً بعكس
                      البريد والواتساب، فتحتاج رصيداً يُشحن ويُخصم.
"""
from __future__ import annotations

import logging

log = logging.getLogger("dheuof.db.alerts")

ALERT_TYPES = ("door_open", "battery_low", "forced_entry", "offline", "manual")
ALERT_LABELS = {
    "door_open": "باب مفتوح",
    "battery_low": "بطارية ضعيفة",
    "forced_entry": "محاولة فتح عنوة",
    "offline": "قفل غير متصل",
    "manual": "إنذار يدوي",
}

SEVERITIES = ("critical", "high", "medium", "low")
SEVERITY_LABELS = {
    "critical": "حرج", "high": "عالٍ", "medium": "متوسط", "low": "منخفض",
}

ALERT_STATUSES = ("active", "resolved", "snoozed")

CHANNELS = ("whatsapp", "email", "sms")
CHANNEL_LABELS = {"whatsapp": "واتساب", "email": "بريد", "sms": "رسالة نصية"}

ALERTS_SCHEMA = """
CREATE TABLE IF NOT EXISTS smart_alerts (
    id          SERIAL PRIMARY KEY,
    client_id   VARCHAR(50) NOT NULL REFERENCES clients(id) ON DELETE CASCADE,
    alert_type  VARCHAR(30) NOT NULL,
    severity    VARCHAR(20) NOT NULL DEFAULT 'medium',
    status      VARCHAR(20) NOT NULL DEFAULT 'active',
    room_number VARCHAR(20),
    lock_id     VARCHAR(60),
    title       VARCHAR(200) NOT NULL,
    message     TEXT,
    created_at  TIMESTAMPTZ DEFAULT NOW(),
    resolved_at TIMESTAMPTZ,
    resolved_by VARCHAR(60),
    snoozed_until TIMESTAMPTZ
);
CREATE INDEX IF NOT EXISTS idx_alerts_tenant
    ON smart_alerts(client_id, status, created_at DESC);

CREATE TABLE IF NOT EXISTS alert_deliveries (
    id          SERIAL PRIMARY KEY,
    client_id   VARCHAR(50) NOT NULL REFERENCES clients(id) ON DELETE CASCADE,
    alert_id    INTEGER NOT NULL,
    channel     VARCHAR(20) NOT NULL,
    recipient   VARCHAR(200) NOT NULL,
    status      VARCHAR(20) NOT NULL DEFAULT 'pending',
    error       TEXT,
    sent_at     TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_deliveries_alert
    ON alert_deliveries(client_id, alert_id);

CREATE TABLE IF NOT EXISTS sms_credits (
    client_id   VARCHAR(50) PRIMARY KEY REFERENCES clients(id) ON DELETE CASCADE,
    balance     INTEGER NOT NULL DEFAULT 0,
    updated_at  TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS sms_credit_log (
    id          SERIAL PRIMARY KEY,
    client_id   VARCHAR(50) NOT NULL REFERENCES clients(id) ON DELETE CASCADE,
    delta       INTEGER NOT NULL,
    reason      VARCHAR(100),
    balance_after INTEGER NOT NULL,
    created_at  TIMESTAMPTZ DEFAULT NOW(),
    created_by  VARCHAR(60)
);
CREATE INDEX IF NOT EXISTS idx_smslog_tenant
    ON sms_credit_log(client_id, created_at DESC)
"""


def run_alerts_migration(db) -> None:
    """يُنشئ جداول الإنذارات والتبليغ ورصيد الرسائل. آمنٌ للتكرار."""
    if not getattr(db, "use_postgres", False):
        return
    for statement in ALERTS_SCHEMA.split(";"):
        sql = statement.strip()
        if not sql:
            continue
        try:
            db.execute(sql)
        except Exception as exc:
            if "already exists" not in str(exc).lower():
                log.warning("ترحيل الإنذارات: %s", exc)
    log.info("✅ الإنذارات — smart_alerts + alert_deliveries + sms_credits")
