#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""M13 — المستودعات والمشتريات Warehouses & Procurement"""
import secrets
import logging
from typing import Optional
from fastapi import APIRouter, Request, Depends, HTTPException

router = APIRouter(prefix="/api/m13", tags=["Warehouses"])

logger = logging.getLogger("dheuof")


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
            q = "SELECT * FROM warehouse_items WHERE client_id=%s"
            params = [cid]
            if category: q += " AND warehouse_type=%s"; params.append(category)
            q += " ORDER BY name"
            rows = db.execute(q, params, fetch="all")
            return {"success": True, "data": [dict(r) for r in (rows or [])]}
        return {"success": True, "data": []}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in list_items: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"خطأ في الخادم: {str(e)}")


@router.post("/items")
async def create_item(request: Request, session=Depends(_require_client)):
    try:
        data = await request.json()
        db = request.app.state.db
        cid = session["client_id"]
        if db.use_postgres:
            row = db.execute("""
                INSERT INTO warehouse_items
                    (client_id,warehouse_type,name,unit,quantity,reorder_level,price_per_unit)
                VALUES (%s,%s,%s,%s,%s,%s,%s) RETURNING *
            """, (cid, data.get("warehouse_type", "general"),
                  data.get("name", ""), data.get("unit", "قطعة"),
                  float(data.get("quantity", 0)), float(data.get("reorder_level", 0)),
                  float(data.get("price_per_unit", 0))), fetch="one")
            return {"success": True, "data": dict(row)}
        return {"success": True, "data": data}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in create_item: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"خطأ في الخادم: {str(e)}")


@router.post("/items/{item_id}/adjust")
async def adjust_stock(item_id: int, request: Request, session=Depends(_require_client)):
    try:
        data = await request.json()
        db = request.app.state.db
        cid = session["client_id"]
        qty = float(data.get("quantity", 0))
        move_type = data.get("type", "in")
        if db.use_postgres:
            delta = qty if move_type == "in" else -qty
            db.execute("""
                UPDATE warehouse_items SET quantity = quantity + %s
                WHERE id=%s AND client_id=%s
            """, (delta, item_id, cid))
            db.execute("""
                INSERT INTO warehouse_movements
                    (item_id,client_id,movement_type,quantity,notes,created_by)
                VALUES (%s,%s,%s,%s,%s,%s)
            """, (item_id, cid, move_type, qty,
                  data.get("notes", ""), data.get("created_by", "")))
        return {"success": True}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in adjust_stock: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"خطأ في الخادم: {str(e)}")


@router.get("/suppliers")
async def list_suppliers(request: Request, session=Depends(_require_client)):
    try:
        db = request.app.state.db
        cid = session["client_id"]
        if db.use_postgres:
            rows = db.execute(
                "SELECT * FROM suppliers WHERE client_id=%s AND status='active' ORDER BY name_ar",
                (cid,), fetch="all")
            return {"success": True, "data": [dict(r) for r in (rows or [])]}
        return {"success": True, "data": []}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in list_suppliers: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"خطأ في الخادم: {str(e)}")


@router.post("/suppliers")
async def create_supplier(request: Request, session=Depends(_require_client)):
    try:
        data = await request.json()
        db = request.app.state.db
        cid = session["client_id"]
        if db.use_postgres:
            row = db.execute("""
                INSERT INTO suppliers
                    (client_id,name_ar,name_en,vat_number,contact_phone,contact_email,payment_terms)
                VALUES (%s,%s,%s,%s,%s,%s,%s) RETURNING *
            """, (cid, data.get("name_ar", ""), data.get("name_en"),
                  data.get("vat_number"), data.get("contact_phone"),
                  data.get("contact_email"), int(data.get("payment_terms", 30))),
                  fetch="one")
            return {"success": True, "data": dict(row)}
        return {"success": True, "data": data}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in create_supplier: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"خطأ في الخادم: {str(e)}")


@router.get("/purchase-orders")
async def list_po(request: Request, status: Optional[str] = None,
                  session=Depends(_require_client)):
    try:
        db = request.app.state.db
        cid = session["client_id"]
        if db.use_postgres:
            q = """SELECT p.*, s.name_ar as supplier_name
                   FROM purchase_orders p LEFT JOIN suppliers s ON p.supplier_id = s.id
                   WHERE p.client_id = %s"""
            params = [cid]
            if status: q += " AND p.status=%s"; params.append(status)
            q += " ORDER BY p.created_at DESC LIMIT 50"
            rows = db.execute(q, params, fetch="all")
            return {"success": True, "data": [dict(r) for r in (rows or [])]}
        return {"success": True, "data": []}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in list_po: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"خطأ في الخادم: {str(e)}")


@router.post("/purchase-orders")
async def create_po(request: Request, session=Depends(_require_client)):
    try:
        data = await request.json()
        db = request.app.state.db
        cid = session["client_id"]
        if db.use_postgres:
            num = f"PO-{secrets.token_hex(4).upper()}"
            row = db.execute("""
                INSERT INTO purchase_orders
                    (client_id,po_number,supplier_id,order_date,expected_date,
                     status,total_amount,notes)
                VALUES (%s,%s,%s,CURRENT_DATE,%s,'draft',%s,%s) RETURNING *
            """, (cid, num, data.get("supplier_id"),
                  data.get("expected_date"),
                  float(data.get("total_amount", 0)),
                  data.get("notes")), fetch="one")
            return {"success": True, "data": dict(row)}
        return {"success": True, "data": data}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in create_po: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"خطأ في الخادم: {str(e)}")


@router.get("/low-stock")
async def low_stock(request: Request, session=Depends(_require_client)):
    try:
        db = request.app.state.db
        cid = session["client_id"]
        if db.use_postgres:
            rows = db.execute("""
                SELECT * FROM warehouse_items
                WHERE client_id=%s AND quantity <= reorder_level AND reorder_level > 0
                ORDER BY (quantity - reorder_level)
            """, (cid,), fetch="all")
            return {"success": True, "data": [dict(r) for r in (rows or [])]}
        return {"success": True, "data": []}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in low_stock: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"خطأ في الخادم: {str(e)}")
