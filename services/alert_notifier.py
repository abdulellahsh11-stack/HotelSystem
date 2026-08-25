#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
services/alert_notifier.py — تبليغ الإنذارات عبر واتساب وبريد ورسالة نصية

مبدآن يحكمان هذا الملف:

**كل قناة مستقلة.** فشل الواتساب لا يمنع البريد. الإنذار الأمني الذي
يصل بقناة واحدة أفضل من إنذار لا يصل لأن قناةً واحدة تعطّلت.

**الرصيد يُخصم قبل الإرسال لا بعده.** الخصم بعد النجاح يسمح بإرسال
رسائل بلا رصيد إن تزامن طلبان: كلاهما يقرأ الرصيد ١ ثم يرسل. الخصم
المشروط (`WHERE balance > 0`) يجعل قاعدة البيانات تحسم السباق.

المزوّدون غير مُوصولين بعد: `_send_sms` و`_send_whatsapp` تُسجّلان
النية وتُعيدان حالةً واضحة بدل ادّعاء نجاحٍ لم يقع. البريد موصول فعلاً
عبر `services.mailer`.
"""
from __future__ import annotations

import logging
from typing import Optional

from db.schema_alerts import CHANNEL_LABELS, SEVERITY_LABELS

log = logging.getLogger("dheuof.alerts")

# تكلفة الرسالة الواحدة بوحدات الرصيد. رسالة عربية طويلة تُقسَّم إلى
# أكثر من رسالة عند المزوّد، فالتكلفة تُحسب بطول النص لا بعدده.
SMS_UNIT_CHARS = 70  # الرسالة العربية (UCS-2) سبعون محرفاً للوحدة


def sms_units(text: str) -> int:
    """عدد وحدات الرصيد التي تستهلكها رسالة. الفارغة تستهلك واحدة."""
    length = len(text or "")
    if length <= SMS_UNIT_CHARS:
        return 1
    return (length + SMS_UNIT_CHARS - 1) // SMS_UNIT_CHARS


def format_alert_text(alert: dict) -> str:
    """نصّ التبليغ. قصيرٌ لأن الرسالة النصية تُحاسَب بالطول."""
    parts = [f"[{SEVERITY_LABELS.get(alert.get('severity'), '')}] {alert.get('title', '')}"]
    if alert.get("room_number"):
        parts.append(f"غرفة {alert['room_number']}")
    if alert.get("message"):
        parts.append(str(alert["message"])[:120])
    return " · ".join(p for p in parts if p)


# ── القنوات ────────────────────────────────────────────────────
def _send_email(cfg, recipient: str, alert: dict) -> tuple[bool, str]:
    try:
        from services.mailer import send_email

        subject = f"إنذار: {alert.get('title', '')}"
        html = (
            f"<div dir='rtl' style='font-family:sans-serif'>"
            f"<h3>{alert.get('title', '')}</h3>"
            f"<p>الخطورة: {SEVERITY_LABELS.get(alert.get('severity'), '—')}</p>"
            f"<p>الغرفة: {alert.get('room_number') or '—'}</p>"
            f"<p>{alert.get('message') or ''}</p></div>"
        )
        ok = send_email(cfg, recipient, subject, html)
        return (True, "") if ok else (False, "تعذّر إرسال البريد")
    except Exception as exc:
        return False, str(exc)[:200]


def _send_whatsapp(cfg, recipient: str, alert: dict) -> tuple[bool, str]:
    """
    واتساب — غير موصول بمزوّد بعد.

    يُعيد فشلاً صريحاً لا نجاحاً كاذباً: تبليغٌ أمني يُقال إنه أُرسل
    وهو لم يُرسل أسوأ من تبليغٍ يُعلن فشله.
    """
    log.info("واتساب (غير مُوصول) → %s: %s", recipient, format_alert_text(alert))
    return False, "مزوّد الواتساب غير مُهيّأ"


def _send_sms(cfg, recipient: str, alert: dict) -> tuple[bool, str]:
    """رسالة نصية — غير موصولة بمزوّد بعد. الرصيد يُخصم قبل النداء."""
    log.info("رسالة نصية (غير مُوصولة) → %s: %s", recipient, format_alert_text(alert))
    return False, "مزوّد الرسائل النصية غير مُهيّأ"


_SENDERS = {"email": _send_email, "whatsapp": _send_whatsapp, "sms": _send_sms}


# ── الرصيد ─────────────────────────────────────────────────────
def get_balance(db, client_id: str) -> int:
    row = db.execute(
        "SELECT balance FROM sms_credits WHERE client_id=%s", (client_id,), fetch="one"
    )
    return int(row["balance"]) if row else 0


def add_credit(db, client_id: str, amount: int, reason: str, by: str = "") -> int:
    """يشحن الرصيد ويُعيد الرصيد الجديد. يُسجَّل كل شحنٍ للمراجعة."""
    db.execute(
        """INSERT INTO sms_credits (client_id, balance, updated_at)
           VALUES (%s, %s, NOW())
           ON CONFLICT (client_id)
           DO UPDATE SET balance = sms_credits.balance + EXCLUDED.balance,
                         updated_at = NOW()""",
        (client_id, amount),
    )
    balance = get_balance(db, client_id)
    db.execute(
        """INSERT INTO sms_credit_log (client_id, delta, reason, balance_after, created_by)
           VALUES (%s,%s,%s,%s,%s)""",
        (client_id, amount, reason, balance, by),
    )
    return balance


def _consume_credit(db, client_id: str, units: int) -> bool:
    """
    يخصم الرصيد **قبل** الإرسال بشرطٍ ذرّي.

    `WHERE balance >= units` يجعل قاعدة البيانات تحسم التزامن: طلبان
    متزامنان لا يمرّان معاً على رصيدٍ يكفي واحداً.
    """
    affected = db.execute(
        """UPDATE sms_credits SET balance = balance - %s, updated_at = NOW()
           WHERE client_id = %s AND balance >= %s""",
        (units, client_id, units),
    )
    if not affected:
        return False
    db.execute(
        """INSERT INTO sms_credit_log (client_id, delta, reason, balance_after, created_by)
           VALUES (%s,%s,'إرسال إنذار',%s,'system')""",
        (client_id, -units, get_balance(db, client_id)),
    )
    return True


def _refund_credit(db, client_id: str, units: int) -> None:
    """يُعيد الرصيد إذا فشل الإرسال — الخصم مقابل رسالةٍ لم تُرسل ظلم."""
    try:
        add_credit(db, client_id, units, "استرداد إرسال فاشل", "system")
    except Exception as exc:
        log.error("تعذّر استرداد رصيد %s وحدة للمنشأة %s: %s", units, client_id, exc)


# ── التبليغ ────────────────────────────────────────────────────
def notify(db, cfg, alert: dict, recipients: dict,
           channels: Optional[list] = None) -> list[dict]:
    """
    يُبلّغ عن إنذار عبر القنوات المطلوبة، ويُسجّل كل محاولة.

    `recipients` مثل `{"email": "...", "whatsapp": "05...", "sms": "05..."}`.
    قناةٌ بلا مستقبِل تُتخطّى بصمت — غيابُ رقمٍ ليس خطأً بل إعداداً.
    """
    results = []
    text = format_alert_text(alert)

    for channel in (channels or list(_SENDERS)):
        recipient = (recipients or {}).get(channel)
        if not recipient:
            continue

        units = sms_units(text) if channel == "sms" else 0
        if channel == "sms" and not _consume_credit(db, alert["client_id"], units):
            results.append({
                "channel": channel, "recipient": recipient,
                "status": "failed", "error": "لا رصيد كافٍ للرسائل النصية",
            })
            _log_delivery(db, alert, channel, recipient, "failed",
                          "لا رصيد كافٍ للرسائل النصية")
            continue

        ok, error = _SENDERS[channel](cfg, recipient, alert)
        if not ok and units:
            _refund_credit(db, alert["client_id"], units)

        status = "sent" if ok else "failed"
        results.append({"channel": channel, "recipient": recipient,
                        "status": status, "error": error})
        _log_delivery(db, alert, channel, recipient, status, error)

    return results


def _log_delivery(db, alert: dict, channel: str, recipient: str,
                  status: str, error: str) -> None:
    try:
        db.execute(
            """INSERT INTO alert_deliveries
                   (client_id, alert_id, channel, recipient, status, error)
               VALUES (%s,%s,%s,%s,%s,%s)""",
            (alert["client_id"], alert.get("id"), channel, recipient,
             status, (error or "")[:500]),
        )
    except Exception as exc:
        # فشل التسجيل لا يُبطل التبليغ — الرسالة وصلت أو لم تصل بمعزل
        # عن قدرتنا على تدوين ذلك.
        log.warning("تعذّر تسجيل تبليغ %s: %s", CHANNEL_LABELS.get(channel, channel), exc)
