#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""M07 POS — نقطة البيع"""
import json
import logging
import secrets
from typing import Optional
from fastapi import APIRouter, Request, Depends, HTTPException

router = APIRouter(prefix="/api/m07", tags=["POS"])

logger = logging.getLogger("dheuof")

# ── Lazy migration: create pos_sales table on first use ──────────────────────
_POS_MIGRATION = """
CREATE TABLE IF NOT EXISTS pos_sales (
    id             SERIAL PRIMARY KEY,
    client_id      VARCHAR(50),
    sale_number    VARCHAR(30),
    guest_id       INTEGER,
    items          JSONB DEFAULT '[]',
    total          DECIMAL(10,2) DEFAULT 0,
    payment_method VARCHAR(30) DEFAULT 'cash',
    status         VARCHAR(20) DEFAULT 'completed',
    created_by     VARCHAR(100),
    created_at     TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_pos_client ON pos_sales(client_id, created_at)
"""

_migration_done = False


def _ensure_pos_table(db) -> None:
    global _migration_done
    if _migration_done or not db.use_postgres:
        return
    for stmt in _POS_MIGRATION.split(";"):
        s = stmt.strip()
        if s:
            try:
                db.execute(s)
            except Exception as e:
                err = str(e).lower()
                if "already exists" not in err:
                    logger.warning(f"POS migration: {e}")
    _migration_done = True


def _require_client(request: Request) -> dict:
    from main import require_client
    return require_client(request)


# ── Sales ─────────────────────────────────────────────────────────────────────

@router.get("/sales")
async def list_sales(
    request: Request,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    session=Depends(_require_client),
):
    try:
        db = request.app.state.db
        _ensure_pos_table(db)
        cid = session["client_id"]
        if db.use_postgres:
            q = """
                SELECT id, sale_number, guest_id, items, total,
                       payment_method, status, created_by, created_at
                FROM pos_sales
                WHERE client_id = %s AND status != 'voided'
            """
            params = [cid]
            if date_from:
                q += " AND created_at::date >= %s"
                params.append(date_from)
            if date_to:
                q += " AND created_at::date <= %s"
                params.append(date_to)
            q += " ORDER BY created_at DESC LIMIT 200"
            rows = db.execute(q, params, fetch="all")
            return {"success": True, "data": [dict(r) for r in (rows or [])]}
        return {"success": True, "data": []}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in list_sales: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"خطأ في الخادم: {str(e)}")


@router.post("/sales")
async def create_sale(request: Request, session=Depends(_require_client)):
    try:
        data = await request.json()
        db = request.app.state.db
        _ensure_pos_table(db)
        cid = session["client_id"]

        items = data.get("items", [])
        total = float(data.get("total", 0) or 0)
        payment_method = data.get("payment_method", "cash")
        guest_id = data.get("guest_id")
        created_by = data.get("created_by", session.get("client_id", ""))

        if db.use_postgres:
            sale_number = f"POS-{secrets.token_hex(4).upper()}"
            row = db.execute(
                """
                INSERT INTO pos_sales
                    (client_id, sale_number, guest_id, items, total,
                     payment_method, status, created_by)
                VALUES (%s, %s, %s, %s::jsonb, %s, %s, 'completed', %s)
                RETURNING *
                """,
                (
                    cid,
                    sale_number,
                    guest_id,
                    json.dumps(items, ensure_ascii=False),
                    total,
                    payment_method,
                    created_by,
                ),
                fetch="one",
            )
            return {"success": True, "data": dict(row)}
        return {"success": True, "data": data}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in create_sale: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"خطأ في الخادم: {str(e)}")


@router.delete("/sales/{sale_id}")
async def void_sale(sale_id: int, request: Request, session=Depends(_require_client)):
    """Void / cancel a sale."""
    try:
        db = request.app.state.db
        _ensure_pos_table(db)
        cid = session["client_id"]
        if db.use_postgres:
            db.execute(
                "UPDATE pos_sales SET status='voided' WHERE id=%s AND client_id=%s",
                (sale_id, cid),
            )
        return {"success": True, "message": "تم إلغاء عملية البيع"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in void_sale: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"خطأ في الخادم: {str(e)}")


# ── Items (product catalog from warehouse_items) ──────────────────────────────

@router.get("/items")
async def list_items(request: Request, session=Depends(_require_client)):
    """List POS menu items — sourced from warehouse_items."""
    try:
        db = request.app.state.db
        cid = session["client_id"]
        if db.use_postgres:
            rows = db.execute(
                """
                SELECT id, name, unit, price_per_unit AS unit_price,
                       quantity, warehouse_type, created_at
                FROM warehouse_items
                WHERE client_id = %s
                ORDER BY name
                LIMIT 500
                """,
                (cid,),
                fetch="all",
            )
            return {"success": True, "data": [dict(r) for r in (rows or [])]}
        return {"success": True, "data": []}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in list_items: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"خطأ في الخادم: {str(e)}")


@router.post("/items")
async def create_item(request: Request, session=Depends(_require_client)):
    """Add a new POS item to the warehouse_items catalog."""
    try:
        data = await request.json()
        db = request.app.state.db
        cid = session["client_id"]
        if db.use_postgres:
            row = db.execute(
                """
                INSERT INTO warehouse_items
                    (client_id, name, unit, price_per_unit, quantity, warehouse_type)
                VALUES (%s, %s, %s, %s, %s, %s)
                RETURNING *
                """,
                (
                    cid,
                    data.get("name", ""),
                    data.get("unit", "قطعة"),
                    float(data.get("unit_price", 0) or 0),
                    float(data.get("quantity", 0) or 0),
                    data.get("warehouse_type", "pos"),
                ),
                fetch="one",
            )
            return {"success": True, "data": dict(row)}
        return {"success": True, "data": data}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in create_item: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"خطأ في الخادم: {str(e)}")


# ── Stats ─────────────────────────────────────────────────────────────────────

@router.get("/stats")
async def pos_stats(request: Request, session=Depends(_require_client)):
    """Return {today_sales, today_revenue, avg_transaction}."""
    try:
        db = request.app.state.db
        _ensure_pos_table(db)
        cid = session["client_id"]
        if db.use_postgres:
            row = db.execute(
                """
                SELECT
                    COUNT(*) FILTER (
                        WHERE created_at::date = CURRENT_DATE
                          AND status = 'completed'
                    ) AS today_sales,
                    COALESCE(SUM(total) FILTER (
                        WHERE created_at::date = CURRENT_DATE
                          AND status = 'completed'
                    ), 0) AS today_revenue,
                    COALESCE(AVG(total) FILTER (
                        WHERE status = 'completed'
                    ), 0) AS avg_transaction
                FROM pos_sales
                WHERE client_id = %s
                """,
                (cid,),
                fetch="one",
            )
            return {"success": True, "data": dict(row) if row else {
                "today_sales": 0, "today_revenue": 0, "avg_transaction": 0
            }}
        return {"success": True, "data": {"today_sales": 0, "today_revenue": 0, "avg_transaction": 0}}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in pos_stats: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"خطأ في الخادم: {str(e)}")
