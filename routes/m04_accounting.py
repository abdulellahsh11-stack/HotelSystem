#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""routes/m04_accounting.py — المحاسبة ونقطة البيع Accounting & POS"""
import secrets
from typing import Optional
from datetime import date
from fastapi import APIRouter, Request, Depends, HTTPException

router = APIRouter(prefix="/api/m04", tags=["Accounting"])


def _require_client(request: Request) -> dict:
    from main import require_client
    return require_client(request)


# ─── فواتير ────────────────────────────────────────────────────────────────────

@router.get("/invoices")
async def list_invoices(request: Request, status: Optional[str] = None,
                        date_from: Optional[str] = None, date_to: Optional[str] = None,
                        session=Depends(_require_client)):
    db = request.app.state.db
    cid = session["client_id"]
    if db.use_postgres:
        q = """SELECT i.*, g.full_name as guest_name
               FROM invoices i
               LEFT JOIN guests g ON i.guest_id = g.id
               WHERE i.client_id=%s"""
        params = [cid]
        if status: q += " AND i.payment_status=%s"; params.append(status)
        if date_from: q += " AND i.issue_date>=%s"; params.append(date_from)
        if date_to: q += " AND i.issue_date<=%s"; params.append(date_to)
        q += " ORDER BY i.created_at DESC LIMIT 200"
        rows = db.execute(q, params, fetch="all")
        return {"success": True, "data": [dict(r) for r in (rows or [])]}
    return {"success": True, "data": []}


@router.post("/invoices")
async def create_invoice(request: Request, session=Depends(_require_client)):
    data = await request.json()
    db = request.app.state.db
    cid = session["client_id"]
    if db.use_postgres:
        inv_id = f"INV-{secrets.token_hex(5).upper()}"
        subtotal = float(data.get("subtotal", 0))
        vat_amount = round(subtotal * 0.15, 2)
        total = subtotal + vat_amount
        row = db.execute("""
            INSERT INTO invoices (id,client_id,booking_id,guest_id,
                issue_date,subtotal,vat_amount,total_amount,
                payment_method,payment_status,line_items)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING *
        """, (inv_id, cid, data.get("booking_id"), data.get("guest_id"),
              data.get("issue_date", date.today().isoformat()),
              subtotal, vat_amount, total,
              data.get("payment_method", "cash"),
              data.get("payment_status", "paid"),
              data.get("line_items", "[]")), fetch="one")
        return {"success": True, "data": dict(row)}
    return {"success": True, "data": data}


@router.put("/invoices/{invoice_id}/pay")
async def pay_invoice(invoice_id: str, request: Request, session=Depends(_require_client)):
    data = await request.json()
    db = request.app.state.db
    cid = session["client_id"]
    if db.use_postgres:
        db.execute("""
            UPDATE invoices SET payment_status='paid', payment_method=%s
            WHERE id=%s AND client_id=%s
        """, (data.get("payment_method", "cash"), invoice_id, cid))
    return {"success": True, "message": "تم استلام الدفع"}


# ─── نقطة البيع POS ─────────────────────────────────────────────────────────────

@router.get("/pos/items")
async def pos_items(request: Request, category: Optional[str] = None,
                    session=Depends(_require_client)):
    db = request.app.state.db
    cid = session["client_id"]
    if db.use_postgres:
        q = "SELECT * FROM pos_items WHERE client_id=%s AND is_active=TRUE"
        params = [cid]
        if category: q += " AND category=%s"; params.append(category)
        q += " ORDER BY name_ar"
        rows = db.execute(q, params, fetch="all")
        return {"success": True, "data": [dict(r) for r in (rows or [])]}
    return {"success": True, "data": []}


@router.post("/pos/items")
async def create_pos_item(request: Request, session=Depends(_require_client)):
    data = await request.json()
    db = request.app.state.db
    cid = session["client_id"]
    if not data.get("name_ar"):
        raise HTTPException(400, "name_ar مطلوب")
    if db.use_postgres:
        row = db.execute("""
            INSERT INTO pos_items (client_id,name_ar,name_en,category,
                price,vat_included,unit,is_active)
            VALUES (%s,%s,%s,%s,%s,%s,%s,TRUE) RETURNING *
        """, (cid, data["name_ar"], data.get("name_en"),
              data.get("category", "misc"), float(data.get("price", 0)),
              bool(data.get("vat_included", True)),
              data.get("unit", "وحدة")), fetch="one")
        return {"success": True, "data": dict(row)}
    return {"success": True, "data": data}


@router.post("/pos/sale")
async def process_sale(request: Request, session=Depends(_require_client)):
    data = await request.json()
    db = request.app.state.db
    cid = session["client_id"]
    items = data.get("items", [])
    if not items:
        raise HTTPException(400, "لا توجد بنود في البيع")
    if db.use_postgres:
        amount = sum(float(i.get("price", 0)) * int(i.get("qty", 1)) for i in items)
        vat_amount = round(amount * 0.15, 2)
        description = "، ".join(
            f"{i.get('name_ar', i.get('name', ''))} x{i.get('qty',1)}" for i in items)
        row = db.execute("""
            INSERT INTO pos_transactions (client_id,booking_id,date,payment_method,
                amount,vat_amount,net_amount,category,description,cashier)
            VALUES (%s,%s,CURRENT_DATE,%s,%s,%s,%s,%s,%s,%s) RETURNING *
        """, (cid, data.get("booking_id"), data.get("payment_method", "cash"),
              amount, vat_amount, amount - vat_amount,
              data.get("category", "pos"), description,
              data.get("cashier", "كاشير")), fetch="one")
        return {"success": True, "data": dict(row)}
    return {"success": True}


@router.get("/pos/sales")
async def list_sales(request: Request, date_from: Optional[str] = None,
                     date_to: Optional[str] = None, session=Depends(_require_client)):
    db = request.app.state.db
    cid = session["client_id"]
    if db.use_postgres:
        q = "SELECT * FROM pos_transactions WHERE client_id=%s"
        params = [cid]
        if date_from: q += " AND date>=%s"; params.append(date_from)
        if date_to: q += " AND date<=%s"; params.append(date_to)
        q += " ORDER BY created_at DESC LIMIT 200"
        rows = db.execute(q, params, fetch="all")
        return {"success": True, "data": [dict(r) for r in (rows or [])]}
    return {"success": True, "data": []}


# ─── التقارير المالية ──────────────────────────────────────────────────────────

@router.get("/cashier/summary")
async def cashier_summary(request: Request, report_date: Optional[str] = None,
                           session=Depends(_require_client)):
    db = request.app.state.db
    cid = session["client_id"]
    rdate = report_date or date.today().isoformat()
    if db.use_postgres:
        inv = db.execute("""
            SELECT COALESCE(SUM(total_amount),0) as total, COUNT(*) as count
            FROM invoices WHERE client_id=%s AND payment_status='paid'
            AND issue_date=%s
        """, (cid, rdate), fetch="one")
        pos = db.execute("""
            SELECT COALESCE(SUM(amount),0) as total, COUNT(*) as count
            FROM pos_transactions WHERE client_id=%s AND date=%s
        """, (cid, rdate), fetch="one")
        inv_d = dict(inv or {})
        pos_d = dict(pos or {})
        total_inv = float(inv_d.get("total") or 0)
        total_pos = float(pos_d.get("total") or 0)
        return {
            "success": True,
            "date": rdate,
            "invoices_total": total_inv,
            "invoices_count": int(inv_d.get("count") or 0),
            "pos_total": total_pos,
            "pos_count": int(pos_d.get("count") or 0),
            "grand_total": total_inv + total_pos
        }
    return {"success": True, "grand_total": 0}


@router.get("/revenue/monthly")
async def monthly_revenue(request: Request, year: Optional[int] = None,
                           session=Depends(_require_client)):
    db = request.app.state.db
    cid = session["client_id"]
    yr = year or date.today().year
    if db.use_postgres:
        rows = db.execute("""
            SELECT EXTRACT(MONTH FROM issue_date) as month,
                   SUM(total_amount) as revenue, COUNT(*) as invoices
            FROM invoices WHERE client_id=%s AND payment_status='paid'
            AND EXTRACT(YEAR FROM issue_date)=%s
            GROUP BY 1 ORDER BY 1
        """, (cid, yr), fetch="all")
        return {"success": True, "year": yr,
                "data": [dict(r) for r in (rows or [])]}
    return {"success": True, "data": []}
