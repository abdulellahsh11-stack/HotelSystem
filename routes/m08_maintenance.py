#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""M08 — الصيانة Maintenance"""
import secrets
from typing import Optional
from fastapi import APIRouter, Request, Depends

router = APIRouter(prefix="/api/m08", tags=["Maintenance"])


def _require_client(request: Request) -> dict:
    from main import require_client
    return require_client(request)


@router.get("/orders")
async def list_orders(request: Request, status: Optional[str] = None,
                      session=Depends(_require_client)):
    db = request.app.state.db
    cid = session["client_id"]
    if db.use_postgres:
        q = """SELECT o.*, r.room_number
               FROM maintenance_orders o LEFT JOIN rooms r ON o.room_id = r.id
               WHERE o.client_id = %s"""
        params = [cid]
        if status: q += " AND o.status = %s"; params.append(status)
        q += " ORDER BY o.created_at DESC LIMIT 100"
        rows = db.execute(q, params, fetch="all")
        return {"success": True, "data": [dict(r) for r in (rows or [])]}
    return {"success": True, "data": []}


@router.post("/orders")
async def create_order(request: Request, session=Depends(_require_client)):
    data = await request.json()
    db = request.app.state.db
    cid = session["client_id"]
    if db.use_postgres:
        num = f"MO-{secrets.token_hex(4).upper()}"
        row = db.execute("""
            INSERT INTO maintenance_orders
                (client_id,room_id,order_number,issue_type,description,
                 priority,assigned_to,status,estimated_cost)
            VALUES (%s,%s,%s,%s,%s,%s,%s,'open',%s) RETURNING *
        """, (cid, data.get("room_id"), num, data.get("issue_type", "general"),
              data.get("description", ""), data.get("priority", "normal"),
              data.get("assigned_to"), float(data.get("estimated_cost", 0) or 0)),
              fetch="one")
        return {"success": True, "data": dict(row)}
    return {"success": True, "data": data}


@router.put("/orders/{order_id}")
async def update_order(order_id: int, request: Request, session=Depends(_require_client)):
    data = await request.json()
    db = request.app.state.db
    cid = session["client_id"]
    if db.use_postgres:
        extra = ""
        if data.get("status") == "in_progress":
            extra = ", started_at = NOW()"
        elif data.get("status") == "completed":
            extra = ", completed_at = NOW()"
        db.execute(f"""
            UPDATE maintenance_orders SET status=%s, assigned_to=%s,
            actual_cost=%s, notes=%s{extra}
            WHERE id=%s AND client_id=%s
        """, (data.get("status", "open"), data.get("assigned_to"),
              float(data.get("actual_cost", 0) or 0), data.get("notes"),
              order_id, cid))
    return {"success": True}


@router.get("/assets")
async def list_assets(request: Request, session=Depends(_require_client)):
    db = request.app.state.db
    cid = session["client_id"]
    if db.use_postgres:
        rows = db.execute(
            "SELECT * FROM assets WHERE client_id=%s ORDER BY name_ar",
            (cid,), fetch="all")
        return {"success": True, "data": [dict(r) for r in (rows or [])]}
    return {"success": True, "data": []}


@router.post("/assets")
async def create_asset(request: Request, session=Depends(_require_client)):
    data = await request.json()
    db = request.app.state.db
    cid = session["client_id"]
    if db.use_postgres:
        if not data.get("asset_code"):
            data["asset_code"] = f"AST-{secrets.token_hex(4).upper()}"
        row = db.execute("""
            INSERT INTO assets
                (client_id,asset_code,name_ar,category,location,
                 purchase_date,purchase_cost,warranty_expiry,status,notes)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,'operational',%s) RETURNING *
        """, (cid, data["asset_code"], data.get("name_ar", ""),
              data.get("category"), data.get("location"),
              data.get("purchase_date"), float(data.get("purchase_cost", 0) or 0),
              data.get("warranty_expiry"), data.get("notes")), fetch="one")
        return {"success": True, "data": dict(row)}
    return {"success": True, "data": data}
