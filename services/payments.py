#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
services/payments.py — تسجيل الدفعات الفوري (البند ٨).

عند تسجيل الضيف/دخوله يُحتسَب المبلغ المدفوع مباشرة — نقداً أو عبر نقطة
البيع — ويُسجَّل في جدول `payments` مربوطاً بالحجز (reference)، فيظهر في
تقارير اليوم. الطريقة مضبوطة (لا نصّ حر) كي لا تتناثر «cash/CASH/نقدي».
"""
from __future__ import annotations

METHODS = {"cash", "pos", "card", "transfer", "online"}


def normalize_method(method) -> str:
    """طريقة دفعٍ معروفة دائماً — غير المعروف يعود إلى النقدي."""
    m = str(method or "cash").strip().lower()
    return m if m in METHODS else "cash"


def _resolve_device(db, client_id: str, device_id) -> int | None:
    """معرّف جهازٍ يخصّ هذه المنشأة (وغير محذوف) وإلا None.

    يمنع ربط الدفعة بجهاز منشأةٍ أخرى: معرّفٌ غريب يُسقَط ولا يُخزَّن.
    """
    if device_id in (None, "", 0):
        return None
    try:
        did = int(device_id)
    except (TypeError, ValueError):
        return None
    row = db.execute(
        "SELECT id FROM payment_devices WHERE id=%s AND client_id=%s AND is_deleted=FALSE",
        (did, client_id), fetch="one")
    return did if row else None


def record(db, client_id: str, amount, method="cash", reference=None,
           device_id=None) -> dict | None:
    """يُسجّل دفعةً ويعيدها. مبلغٌ ≤ صفر لا يُسجَّل (يعود None).

    لو رُبطت بجهاز نقطة بيعٍ يخصّ المنشأة أُضيف المبلغ إلى رصيده اليومي
    (daily_total) فيظهر في إغلاق الوردية. في وضع التطوير (بلا PostgreSQL)
    يعود بالدفعة دون تخزين — فلا يسقط، ولا يُوهم بأنها حُفظت في قاعدة.
    """
    try:
        amt = round(float(amount or 0), 2)
    except (TypeError, ValueError):
        return None
    if amt <= 0:
        return None
    m = normalize_method(method)
    if not getattr(db, "use_postgres", False):
        return {"amount": amt, "method": m, "reference": reference,
                "device_id": None, "persisted": False}
    did = _resolve_device(db, client_id, device_id)
    row = db.execute(
        """INSERT INTO payments (client_id, amount, method, reference, device_id)
           VALUES (%s, %s, %s, %s, %s)
           RETURNING id, amount, method, reference, device_id, created_at""",
        (client_id, amt, m, reference, did), fetch="one")
    if not row:
        return None
    if did is not None:
        db.execute(
            """UPDATE payment_devices SET daily_total = daily_total + %s
               WHERE id=%s AND client_id=%s""",
            (amt, did, client_id))
    out = dict(row)
    out["persisted"] = True
    return out
