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


def record(db, client_id: str, amount, method="cash", reference=None) -> dict | None:
    """يُسجّل دفعةً ويعيدها. مبلغٌ ≤ صفر لا يُسجَّل (يعود None).

    في وضع التطوير (بلا PostgreSQL) يعود بالدفعة دون تخزين — فلا يسقط، ولا
    يُوهم بأنها حُفظت في قاعدة.
    """
    try:
        amt = round(float(amount or 0), 2)
    except (TypeError, ValueError):
        return None
    if amt <= 0:
        return None
    m = normalize_method(method)
    if not getattr(db, "use_postgres", False):
        return {"amount": amt, "method": m, "reference": reference, "persisted": False}
    row = db.execute(
        """INSERT INTO payments (client_id, amount, method, reference)
           VALUES (%s, %s, %s, %s)
           RETURNING id, amount, method, reference, created_at""",
        (client_id, amt, m, reference), fetch="one")
    if not row:
        return None
    out = dict(row)
    out["persisted"] = True
    return out
