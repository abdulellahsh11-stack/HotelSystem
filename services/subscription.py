#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
services/subscription.py — حالة الاشتراك والتنبيه قبل القفل (البند ٣).

التجربة ٣٠ يوماً؛ قبل القفل بـ٢٤ ساعة (اليوم ٢٩) يُرفع تنبيهٌ للمنشأة كي
تجدّد قبل أن تُقفل الوحدات. ورسالة الدفع (تحويل بنكي أو رابط ميسر) يكتبها
مالك المنشأة فتظهر عند التجديد — التحصيل الحقيقي عبر ميسر يحتاج مفاتيح
التاجر (تُضاف من البيئة) وليس من نطاق هذا المنطق.

منطقٌ خالص: `evaluate` تستقبل بيانات العميل ولحظةً (قابلة للحقن في
الاختبار) فتُحسب الحالة دون قاعدة بيانات.
"""
from __future__ import annotations

import math
from datetime import date, datetime, timezone

ALERT_WINDOW_HOURS = 24      # اليوم ٢٩: تنبيهٌ قبل القفل بـ٢٤ ساعة

# رسالة الدفع القابلة للتخصيص — الحقول المعروفة وحدها تُقبل.
_PAY_KEYS = ("method", "message", "bank_name", "iban",
             "account_name", "beneficiary", "moyasar_link")

DEFAULT_PAYMENT = {
    "method": "bank_transfer",
    "message": ("لتجديد الاشتراك حوِّل قيمة الباقة إلى الحساب البنكي أدناه ثم "
                "أرسل الإيصال، أو ادفع عبر رابط ميسر إن وُجد."),
    "bank_name": "",
    "iban": "",
    "account_name": "",
    "beneficiary": "",
    "moyasar_link": "",
}


def _parse_end(val) -> datetime | None:
    """يقبل datetime أو date أو نصّ ISO (تاريخٌ فقط يعني منتصف ليلته UTC)."""
    if not val:
        return None
    if isinstance(val, datetime):
        return val if val.tzinfo else val.replace(tzinfo=timezone.utc)
    if isinstance(val, date):
        return datetime(val.year, val.month, val.day, tzinfo=timezone.utc)
    s = str(val).strip()
    if not s:
        return None
    try:
        dt = datetime.fromisoformat(s.replace("Z", "+00:00"))
    except ValueError:
        return None
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def evaluate(client: dict | None, now: datetime | None = None) -> dict:
    """حالة الاشتراك: متى ينتهي، كم بقي، هل يُنبَّه (٢٤ ساعة)، هل قُفل."""
    now = now or datetime.now(timezone.utc)
    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)
    c = client or {}
    out = {
        "status": c.get("status") or "trial",
        "sub_end": None,
        "days_remaining": None,
        "hours_remaining": None,
        "alert": False,
        "locked": False,
    }
    end = _parse_end(c.get("sub_end") or c.get("trial_end"))
    if not end:
        return out
    hours = (end - now).total_seconds() / 3600.0
    out["sub_end"] = end.date().isoformat()
    out["hours_remaining"] = round(hours, 1)
    out["days_remaining"] = max(0, math.floor(hours / 24)) if hours > 0 else 0
    out["locked"] = hours <= 0
    out["alert"] = 0 < hours <= ALERT_WINDOW_HOURS
    return out


def sanitize_payment(data) -> dict:
    """يُبقي حقول رسالة الدفع المعروفة فقط، نصوصاً مُشذّبة."""
    out: dict[str, str] = {}
    if isinstance(data, dict):
        for k in _PAY_KEYS:
            v = data.get(k)
            if v is not None:
                out[k] = str(v).strip()
    return out


def payment_instructions(client: dict | None) -> dict:
    """تعليمات الدفع لهذه المنشأة — المخصَّص فوق الافتراضي."""
    merged = dict(DEFAULT_PAYMENT)
    stored = ((client or {}).get("settings") or {}).get("subscription_payment")
    if isinstance(stored, dict):
        merged.update(sanitize_payment(stored))
    return merged
