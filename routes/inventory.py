#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""M04 — المخزون والضيافة Guest Amenities Inventory"""
from typing import Optional
from fastapi import APIRouter, Request, Depends, HTTPException

router = APIRouter(prefix="/api/m04", tags=["Inventory"])


def _require_client(request: Request) -> dict:
    from main import require_client
    return require_client(request)


@router.get("/items")
async def list_items(request: Request, category: Optional[str] = None,
                     session=Depends(_require_client)):
    try:
        db = request.app.state.db
        cid = session["client_id"]
        if db.use_postgres:
            q = """SELECT * FROM warehouse_items
                   WHERE client_id=%s
                   AND (warehouse_type='amenities' OR warehouse_type='guest_supplies')"""
            params = [cid]
            if category:
                q += " AND warehouse_type=%s"
                params.append(category)
            q += " ORDER BY name"
            rows = db.execute(q, params, fetch="all")
            return {"success": True, "data": [dict(r) for r in (rows or [])]}
        return {"success": True, "data": []}
    except Exception as e:
        raise HTTPException(500, str(e))


@router.post("/items")
async def create_item(request: Request, session=Depends(_require_client)):
    try:
        data = await request.json()
        db = request.app.state.db
        cid = session["client_id"]
        if db.use_postgres:
            row = db.execute("""
                INSERT INTO warehouse_items
                    (client_id, warehouse_type, name, unit, quantity, reorder_level, price_per_unit)
                VALUES (%s, %s, %s, %s, %s, %s, %s) RETURNING *
            """, (
                cid,
                data.get("warehouse_type", "amenities"),
                data.get("name", ""),
                data.get("unit", "قطعة"),
                float(data.get("quantity", 0)),
                float(data.get("reorder_level", 0)),
                float(data.get("price_per_unit", 0)),
            ), fetch="one")
            return {"success": True, "data": dict(row)}
        return {"success": True, "data": data}
    except Exception as e:
        raise HTTPException(500, str(e))


@router.put("/items/{item_id}")
async def update_item(item_id: int, request: Request, session=Depends(_require_client)):
    try:
        data = await request.json()
        db = request.app.state.db
        cid = session["client_id"]
        if db.use_postgres:
            fields = []
            params = []
            if "name" in data:
                fields.append("name=%s")
                params.append(data["name"])
            if "quantity" in data:
                fields.append("quantity=%s")
                params.append(float(data["quantity"]))
            if "reorder_level" in data:
                fields.append("reorder_level=%s")
                params.append(float(data["reorder_level"]))
            if "price_per_unit" in data:
                fields.append("price_per_unit=%s")
                params.append(float(data["price_per_unit"]))
            if not fields:
                raise HTTPException(400, "لا توجد حقول للتحديث")
            params.extend([item_id, cid])
            db.execute(
                f"UPDATE warehouse_items SET {', '.join(fields)} WHERE id=%s AND client_id=%s",
                params
            )
        return {"success": True}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(500, str(e))


@router.delete("/items/{item_id}")
async def delete_item(item_id: int, request: Request, session=Depends(_require_client)):
    try:
        db = request.app.state.db
        cid = session["client_id"]
        if db.use_postgres:
            # Soft delete: set quantity to 0 and record a note in a movement
            db.execute(
                "UPDATE warehouse_items SET quantity=0 WHERE id=%s AND client_id=%s",
                (item_id, cid)
            )
            db.execute("""
                INSERT INTO warehouse_movements
                    (item_id, client_id, movement_type, quantity, notes, created_by)
                VALUES (%s, %s, 'out', 0, %s, %s)
            """, (item_id, cid, "حذف ناعم — تصفير الكمية", "system"))
        return {"success": True}
    except Exception as e:
        raise HTTPException(500, str(e))


@router.get("/low-stock")
async def low_stock(request: Request, session=Depends(_require_client)):
    try:
        db = request.app.state.db
        cid = session["client_id"]
        if db.use_postgres:
            rows = db.execute("""
                SELECT * FROM warehouse_items
                WHERE client_id=%s
                  AND (warehouse_type='amenities' OR warehouse_type='guest_supplies')
                  AND reorder_level > 0
                  AND quantity <= reorder_level
                ORDER BY (quantity - reorder_level)
            """, (cid,), fetch="all")
            return {"success": True, "data": [dict(r) for r in (rows or [])]}
        return {"success": True, "data": []}
    except Exception as e:
        raise HTTPException(500, str(e))


@router.post("/items/{item_id}/restock")
async def restock_item(item_id: int, request: Request, session=Depends(_require_client)):
    try:
        data = await request.json()
        db = request.app.state.db
        cid = session["client_id"]
        qty = float(data.get("quantity", 0))
        if qty <= 0:
            raise HTTPException(400, "الكمية يجب أن تكون أكبر من صفر")
        if db.use_postgres:
            db.execute("""
                UPDATE warehouse_items SET quantity = quantity + %s
                WHERE id=%s AND client_id=%s
            """, (qty, item_id, cid))
            db.execute("""
                INSERT INTO warehouse_movements
                    (item_id, client_id, movement_type, quantity, notes, created_by)
                VALUES (%s, %s, 'in', %s, %s, %s)
            """, (
                item_id,
                cid,
                qty,
                data.get("notes", "إعادة تخزين"),
                data.get("created_by", ""),
            ))
        return {"success": True, "added_quantity": qty}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(500, str(e))


@router.get("/stats")
async def inventory_stats(request: Request, session=Depends(_require_client)):
    try:
        db = request.app.state.db
        cid = session["client_id"]
        if db.use_postgres:
            total_row = db.execute("""
                SELECT COUNT(*) as total_items
                FROM warehouse_items
                WHERE client_id=%s
                  AND (warehouse_type='amenities' OR warehouse_type='guest_supplies')
            """, (cid,), fetch="one")

            low_row = db.execute("""
                SELECT COUNT(*) as low_stock_count
                FROM warehouse_items
                WHERE client_id=%s
                  AND (warehouse_type='amenities' OR warehouse_type='guest_supplies')
                  AND reorder_level > 0
                  AND quantity <= reorder_level
            """, (cid,), fetch="one")

            value_row = db.execute("""
                SELECT COALESCE(SUM(quantity * price_per_unit), 0) as total_value
                FROM warehouse_items
                WHERE client_id=%s
                  AND (warehouse_type='amenities' OR warehouse_type='guest_supplies')
            """, (cid,), fetch="one")

            return {
                "success": True,
                "total_items": dict(total_row).get("total_items", 0) if total_row else 0,
                "low_stock_count": dict(low_row).get("low_stock_count", 0) if low_row else 0,
                "total_value": float(dict(value_row).get("total_value", 0)) if value_row else 0.0,
            }
        return {"success": True, "total_items": 0, "low_stock_count": 0, "total_value": 0.0}
    except Exception as e:
        raise HTTPException(500, str(e))
