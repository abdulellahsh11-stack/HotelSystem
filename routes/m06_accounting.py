#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""M06 Accounting — المحاسبة والفواتير"""
import logging
from typing import Optional
from fastapi import APIRouter, Request, Depends, HTTPException

router = APIRouter(prefix="/api/m06acc", tags=["Accounting"])

logger = logging.getLogger("dheuof")


def _require_client(request: Request) -> dict:
    from main import require_client
    return require_client(request)


@router.get("/invoices")
async def list_invoices(
    request: Request,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    page: int = 1,
    per_page: int = 50,
    session=Depends(_require_client),
):
    try:
        db = request.app.state.db
        cid = session["client_id"]
        if db.use_postgres:
            limit = min(per_page, 200)
            offset = (page - 1) * limit
            q = """
                SELECT
                    b.id,
                    b.booking_number,
                    COALESCE(g.full_name, g.name, '') AS guest_name,
                    r.room_number,
                    b.check_in,
                    b.check_out,
                    b.total_room,
                    b.status,
                    b.created_at
                FROM bookings b
                LEFT JOIN guests g ON b.guest_id = g.id
                LEFT JOIN rooms  r ON b.room_id  = r.id
                WHERE b.client_id = %s
                  AND b.status IN ('checked_out', 'confirmed')
            """
            params = [cid]
            if date_from:
                q += " AND b.check_in >= %s"
                params.append(date_from)
            if date_to:
                q += " AND b.check_in <= %s"
                params.append(date_to)
            count_q = f"SELECT COUNT(*) FROM ({q}) AS _sub"
            count_result = db.execute(count_q, params, fetch="one")
            total = count_result[0] if count_result else 0
            q += " ORDER BY b.created_at DESC LIMIT %s OFFSET %s"
            params.extend([limit, offset])
            rows = db.execute(q, params, fetch="all")
            return {"success": True, "data": [dict(r) for r in (rows or [])], "page": page, "per_page": limit, "total": total}
        return {"success": True, "data": [], "page": page, "per_page": per_page, "total": 0}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in list_invoices: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"خطأ في الخادم: {str(e)}")


@router.get("/revenue/summary")
async def revenue_summary(request: Request, session=Depends(_require_client)):
    try:
        db = request.app.state.db
        cid = session["client_id"]
        if db.use_postgres:
            row = db.execute(
                """
                SELECT
                    COALESCE(SUM(total_room) FILTER (
                        WHERE check_in::date = CURRENT_DATE
                    ), 0) AS today,
                    COALESCE(SUM(total_room) FILTER (
                        WHERE check_in >= date_trunc('week', CURRENT_DATE)
                    ), 0) AS this_week,
                    COALESCE(SUM(total_room) FILTER (
                        WHERE check_in >= date_trunc('month', CURRENT_DATE)
                    ), 0) AS this_month,
                    COALESCE(SUM(total_room) FILTER (
                        WHERE check_in >= date_trunc('month', CURRENT_DATE) - INTERVAL '1 month'
                          AND check_in <  date_trunc('month', CURRENT_DATE)
                    ), 0) AS last_month
                FROM bookings
                WHERE client_id = %s
                  AND status IN ('checked_out', 'confirmed')
                """,
                (cid,),
                fetch="one",
            )
            return {"success": True, "data": dict(row) if row else {
                "today": 0, "this_week": 0, "this_month": 0, "last_month": 0
            }}
        return {"success": True, "data": {"today": 0, "this_week": 0, "this_month": 0, "last_month": 0}}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in revenue_summary: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"خطأ في الخادم: {str(e)}")


@router.get("/revenue/by-month")
async def revenue_by_month(request: Request, session=Depends(_require_client)):
    try:
        db = request.app.state.db
        cid = session["client_id"]
        if db.use_postgres:
            rows = db.execute(
                """
                SELECT
                    TO_CHAR(date_trunc('month', check_in), 'YYYY-MM') AS month,
                    COALESCE(SUM(total_room), 0)                       AS revenue,
                    COUNT(*)                                            AS bookings_count
                FROM bookings
                WHERE client_id = %s
                  AND status IN ('checked_out', 'confirmed')
                  AND check_in >= CURRENT_DATE - INTERVAL '12 months'
                GROUP BY date_trunc('month', check_in)
                ORDER BY date_trunc('month', check_in)
                """,
                (cid,),
                fetch="all",
            )
            return {"success": True, "data": [dict(r) for r in (rows or [])]}
        return {"success": True, "data": []}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in revenue_by_month: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"خطأ في الخادم: {str(e)}")


@router.get("/outstanding")
async def list_outstanding(request: Request, session=Depends(_require_client)):
    """Bookings that are confirmed but check-out date has passed (overdue checkout)."""
    try:
        db = request.app.state.db
        cid = session["client_id"]
        if db.use_postgres:
            rows = db.execute(
                """
                SELECT
                    b.id,
                    b.booking_number,
                    COALESCE(g.full_name, g.name, '') AS guest_name,
                    r.room_number,
                    b.check_in,
                    b.check_out,
                    b.total_room,
                    b.status,
                    b.created_at
                FROM bookings b
                LEFT JOIN guests g ON b.guest_id = g.id
                LEFT JOIN rooms  r ON b.room_id  = r.id
                WHERE b.client_id = %s
                  AND b.status = 'confirmed'
                  AND b.check_out < NOW()
                ORDER BY b.check_out ASC
                LIMIT 100
                """,
                (cid,),
                fetch="all",
            )
            return {"success": True, "data": [dict(r) for r in (rows or [])]}
        return {"success": True, "data": []}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in list_outstanding: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"خطأ في الخادم: {str(e)}")


@router.post("/payment")
async def record_payment(request: Request, session=Depends(_require_client)):
    """Record a payment against a booking: update status and append notes."""
    try:
        data = await request.json()
        db = request.app.state.db
        cid = session["client_id"]

        booking_id = data.get("booking_id")
        if not booking_id:
            raise HTTPException(status_code=400, detail="booking_id مطلوب")

        new_status = data.get("status", "checked_out")
        notes = data.get("notes", "")
        payment_method = data.get("payment_method", "cash")
        amount = float(data.get("amount", 0) or 0)

        if db.use_postgres:
            # Update booking status and notes
            db.execute(
                """
                UPDATE bookings
                SET status = %s,
                    notes  = COALESCE(NULLIF(notes,''), '') || %s
                WHERE id = %s AND client_id = %s
                """,
                (
                    new_status,
                    f"\n[دفعة] {payment_method}: {amount} — {notes}".strip(),
                    booking_id,
                    cid,
                ),
            )
            # Also log in check_out_log if checking out
            if new_status == "checked_out":
                db.execute(
                    """
                    INSERT INTO check_out_log
                        (client_id, booking_id, checkout_by, final_amount, payment_method, notes)
                    VALUES (%s, %s, %s, %s, %s, %s)
                    """,
                    (
                        cid,
                        str(booking_id),
                        session.get("client_id", ""),
                        amount,
                        payment_method,
                        notes,
                    ),
                )
            return {"success": True, "message": "تم تسجيل الدفعة بنجاح"}
        return {"success": True, "message": "تم التسجيل (وضع غير متصل)"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in record_payment: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"خطأ في الخادم: {str(e)}")
