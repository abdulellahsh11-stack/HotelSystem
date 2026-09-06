#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
services/hospitality.py — رحلة تسجيل الضيف: العقد والضيافة والمخزون.

عند تسجيل الدخول: لا دخولَ حتى يُوقَّع العقد، وعند الدخول تُخصَم أصناف
الضيافة (ماء · سكر · شاي · قهوة · كيس مخدّة · غطاء مرتبة · فوط · لحاف ·
شامبو · كريم · نظافة شخصية) من المخزون — والأصناف والكميّات قابلة
للتخصيص من مالك المنشأة.

الخصم على `warehouse_items` (PostgreSQL) بمطابقة الاسم، ولا يهبط تحت الصفر
(`GREATEST`)، ويسجّل حركةً في `warehouse_movements`. في وضع التطوير (بلا
PostgreSQL) يُتخطّى الخصم دون أن يمنع الدخول.
"""
from __future__ import annotations

# الأصناف الافتراضية وكميّة كلٍّ لكل نزيل/ليلة — قابلة للتخصيص لكل منشأة.
DEFAULT_CONSUMABLES: list[dict] = [
    {"key": "water",          "ar": "علبة ماء",     "en": "Water bottle",   "qty": 1},
    {"key": "sugar",          "ar": "أوراق سكر",    "en": "Sugar sachets",  "qty": 2},
    {"key": "tea",            "ar": "شاي",          "en": "Tea",            "qty": 2},
    {"key": "coffee",         "ar": "قهوة",         "en": "Coffee",         "qty": 2},
    {"key": "pillowcase",     "ar": "كيس مخدّة",    "en": "Pillowcase",     "qty": 1},
    {"key": "mattress_cover", "ar": "غطاء مرتبة",   "en": "Mattress cover", "qty": 1},
    {"key": "towels",         "ar": "فوط",          "en": "Towels",         "qty": 2},
    {"key": "duvet",          "ar": "لحاف",         "en": "Duvet",          "qty": 1},
    {"key": "shampoo",        "ar": "شامبو",        "en": "Shampoo",        "qty": 1},
    {"key": "cream",          "ar": "كريم",         "en": "Cream",          "qty": 1},
    {"key": "hygiene",        "ar": "نظافة شخصية",  "en": "Personal hygiene", "qty": 1},
]


def sanitize(items) -> list[dict]:
    """يُبقي الأصناف الصحيحة فقط: مفتاحٌ نصّي واسمٌ وكميّةٌ غير سالبة."""
    out: list[dict] = []
    seen: set[str] = set()
    for it in items or []:
        if not isinstance(it, dict):
            continue
        key = str(it.get("key") or "").strip()
        if not key or key in seen:
            continue
        try:
            qty = int(it.get("qty", 0))
        except (TypeError, ValueError):
            continue
        if qty < 0:
            continue
        seen.add(key)
        out.append({
            "key": key,
            "ar": str(it.get("ar") or key),
            "en": str(it.get("en") or key),
            "qty": qty,
        })
    return out


def get_consumables(client: dict | None) -> list[dict]:
    """أصناف الضيافة لهذه المنشأة — من إعداداتها، وإلا الافتراضي."""
    settings = (client or {}).get("settings") or {}
    val = settings.get("hospitality_consumables")
    if isinstance(val, list):
        cleaned = sanitize(val)
        if cleaned:
            return cleaned
    return [dict(c) for c in DEFAULT_CONSUMABLES]


def plan_consumption(consumables: list[dict], nights: int = 1, guests: int = 1) -> dict:
    """الكميّة الإجمالية لكل صنف = كميّته × الليالي × النزلاء (بحدٍّ أدنى ١)."""
    n = max(1, int(nights or 1))
    g = max(1, int(guests or 1))
    plan: dict[str, int] = {}
    for c in consumables or []:
        qty = int(c.get("qty", 0)) * n * g
        if qty > 0:
            plan[c["ar"]] = plan.get(c["ar"], 0) + qty
    return plan


def can_check_in(contract_signed) -> bool:
    """لا تسجيلَ دخول حتى يُوقَّع العقد."""
    return bool(contract_signed)


def apply_consumption(db, client_id: str, plan: dict, actor: str = "reception") -> dict:
    """يخصم خطة الاستهلاك من مخزون الضيافة (PostgreSQL) بلا هبوطٍ تحت الصفر.

    يُطابق الصنف باسمه، ويسجّل حركةً لكل خصم. يعود بما خُصم فعلاً. في وضع
    التطوير (بلا PostgreSQL) يعود فارغاً دون أن يرفع خطأً.
    """
    if not plan or not getattr(db, "use_postgres", False):
        return {}
    consumed: dict[str, int] = {}
    for name, qty in plan.items():
        if qty <= 0:
            continue
        row = db.execute(
            """UPDATE warehouse_items
               SET quantity = GREATEST(quantity - %s, 0)
               WHERE client_id=%s AND name=%s
                 AND warehouse_type IN ('amenities','guest_supplies')
               RETURNING id, quantity""",
            (qty, client_id, name), fetch="one")
        if row:
            r = dict(row)
            db.execute(
                """INSERT INTO warehouse_movements
                       (item_id, client_id, movement_type, quantity, notes, created_by)
                   VALUES (%s, %s, 'out', %s, %s, %s)""",
                (r.get("id"), client_id, qty, "استهلاك ضيافة عند تسجيل الدخول", actor))
            consumed[name] = qty
    return consumed
