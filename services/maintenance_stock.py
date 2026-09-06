#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
services/maintenance_stock.py — خصم مواد الصيانة من المستودع (البند ٧).

عند استخدام قطعة غيار أو مادّة في أمر صيانة يُخصَم المستخدَم من رصيد الصنف
في `warehouse_items` مباشرة: «عشرة، استُخدم ثلاثة → يبقى سبعة». الخصم لا
يهبط تحت الصفر (`GREATEST`)، ويُطابق الصنف بمعرّفه لا باسمه (فلا يلتبس
صنفان بالاسم)، ويسجّل حركةً في `warehouse_movements` مربوطةً بأمر الصيانة.

الأصناف المخصومة يختارها المستخدم من مستودعه — لا قائمة ثابتة هنا. في وضع
التطوير (بلا PostgreSQL) يعود فارغاً دون أن يرفع خطأً ولا يُوهم بالخصم.
"""
from __future__ import annotations


def sanitize_lines(lines) -> list[dict]:
    """يُبقي السطور الصحيحة فقط: معرّف صنفٍ موجب وكميّةٌ موجبة.

    يجمع الكميّات لو تكرّر الصنف، فلا يُخصَم مرّتين بسطرين متفرّقين.
    """
    merged: dict[int, float] = {}
    for ln in lines or []:
        if not isinstance(ln, dict):
            continue
        try:
            item_id = int(ln.get("item_id"))
            qty = float(ln.get("qty", 0))
        except (TypeError, ValueError):
            continue
        if item_id <= 0 or qty <= 0:
            continue
        merged[item_id] = merged.get(item_id, 0) + qty
    return [{"item_id": k, "qty": round(v, 2)} for k, v in merged.items()]


def consume(db, client_id: str, lines, order_ref=None, actor: str = "maintenance") -> list[dict]:
    """يخصم مواد الصيانة المستخدَمة من المستودع (PostgreSQL) بلا هبوطٍ تحت الصفر.

    يعود بقائمة ما خُصم فعلاً: لكلّ صنف معرّفُه واسمُه والمستخدَم والمتبقّي.
    صنفٌ لا يخصّ هذه المنشأة أو غير موجود يُتجاهَل (لا يُطابقه الشرط). في وضع
    التطوير (بلا PostgreSQL) يعود فارغاً.
    """
    clean = sanitize_lines(lines)
    if not clean or not getattr(db, "use_postgres", False):
        return []
    used: list[dict] = []
    note = f"استهلاك صيانة — أمر {order_ref}" if order_ref else "استهلاك صيانة"
    for ln in clean:
        row = db.execute(
            """UPDATE warehouse_items
               SET quantity = GREATEST(quantity - %s, 0), updated_at = NOW()
               WHERE id = %s AND client_id = %s
               RETURNING id, name, quantity""",
            (ln["qty"], ln["item_id"], client_id), fetch="one")
        if not row:
            continue
        r = dict(row)
        db.execute(
            """INSERT INTO warehouse_movements
                   (item_id, client_id, movement_type, quantity, notes, created_by)
               VALUES (%s, %s, 'out', %s, %s, %s)""",
            (r["id"], client_id, ln["qty"], note, actor))
        used.append({
            "item_id": r["id"],
            "name": r.get("name"),
            "used": ln["qty"],
            "remaining": r.get("quantity"),
        })
    return used
