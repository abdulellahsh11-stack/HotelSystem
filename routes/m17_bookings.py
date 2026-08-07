#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""M17 — حجوزات القنوات Channel Bookings"""
import secrets
from typing import Optional
from fastapi import APIRouter, Request, Depends, HTTPException

from services.tax_config import get_client_tax_config, calculate_tax as _calc_tax

from db.rows import count_of

router = APIRouter(prefix="/api/m17", tags=["ChannelBookings"])

# أعمدة الضريبة — تُضاف تلقائياً عند أول استخدام
_BOOKING_TAX_COLS = [
    "tax_mode            VARCHAR(10)   DEFAULT 'MODE_A'",
    "vat_amount          DECIMAL(12,2) DEFAULT 0",
    "tourism_tax_amount  DECIMAL(12,2) DEFAULT 0",
]
_booking_tax_done = False


def _ensure_booking_tax_cols(db) -> None:
    global _booking_tax_done
    if _booking_tax_done or not db.use_postgres:
        return
    for col_def in _BOOKING_TAX_COLS:
        try:
            db.execute(f"ALTER TABLE bookings ADD COLUMN IF NOT EXISTS {col_def}")
        except Exception:
            pass
    _booking_tax_done = True


def _require_client(request: Request) -> dict:
    from main import require_client
    return require_client(request)


@router.get("/reservations")
async def list_reservations(
    request: Request,
    status: Optional[str] = None,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    source: Optional[str] = None,
    page: int = 1,
    per_page: int = 50,
    session=Depends(_require_client),
):
    try:
        db = request.app.state.db
        _ensure_booking_tax_cols(db)
        cid = session["client_id"]
        if db.use_postgres:
            limit = min(per_page, 200)
            offset = (page - 1) * limit
            q = """
                SELECT
                    b.id,
                    b.booking_number,
                    g.full_name   AS guest_name,
                    r.room_number,
                    b.check_in,
                    b.check_out,
                    b.status,
                    b.source,
                    b.total_room                               AS grand_total,
                    COALESCE(b.vat_amount, 0)                  AS vat_amount,
                    COALESCE(b.tourism_tax_amount, 0)          AS tourism_tax_amount,
                    COALESCE(b.tax_mode, 'MODE_A')             AS tax_mode,
                    b.total_room
                        - COALESCE(b.vat_amount, 0)
                        - COALESCE(b.tourism_tax_amount, 0)    AS net_amount,
                    b.created_at
                FROM bookings b
                LEFT JOIN guests g ON b.guest_id = g.id
                LEFT JOIN rooms  r ON b.room_id  = r.id
                WHERE b.client_id = %s
            """
            params = [cid]
            if status:
                q += " AND b.status = %s"
                params.append(status)
            if date_from:
                q += " AND b.check_in >= %s"
                params.append(date_from)
            if date_to:
                q += " AND b.check_out <= %s"
                params.append(date_to)
            if source:
                q += " AND b.source = %s"
                params.append(source)
            count_q = f"SELECT COUNT(*) FROM ({q}) AS _sub"
            count_result = db.execute(count_q, params, fetch="one")
            total = count_of(count_result)
            q += " ORDER BY b.created_at DESC LIMIT %s OFFSET %s"
            params.extend([limit, offset])
            rows = db.execute(q, params, fetch="all")
            return {"success": True, "data": [dict(r) for r in (rows or [])], "page": page, "per_page": limit, "total": total}
        return {"success": True, "data": [], "page": page, "per_page": per_page, "total": 0}
    except Exception as e:
        raise HTTPException(500, str(e))


@router.post("/reservations")
async def create_reservation(request: Request, session=Depends(_require_client)):
    try:
        data = await request.json()
        db = request.app.state.db
        _ensure_booking_tax_cols(db)
        cid = session["client_id"]

        guest_id = data.get("guest_id")

        if not guest_id and db.use_postgres:
            guest_name = data.get("guest_name", "").strip()
            phone = data.get("phone", "").strip()
            if not guest_name:
                raise HTTPException(400, "يجب تحديد guest_id أو (guest_name + phone)")
            guest_row = db.execute("""
                INSERT INTO guests (client_id, full_name, absher_phone, source)
                VALUES (%s, %s, %s, %s) RETURNING id
            """, (cid, guest_name, phone, data.get("source", "manual")), fetch="one")
            guest_id = dict(guest_row)["id"]

        room_id = data.get("room_id")
        check_in = data.get("check_in")
        check_out = data.get("check_out")
        source = data.get("source", "direct")
        total_amount = float(data.get("total_amount", 0))

        if not all([room_id, check_in, check_out]):
            raise HTTPException(400, "room_id و check_in و check_out مطلوبة")

        # حساب الضريبة حسب إعدادات العميل
        tax_cfg = get_client_tax_config(db, cid)
        tax = _calc_tax(amount=total_amount, config=tax_cfg)
        grand_total        = tax["grand_total"]
        vat_amount         = tax["vat_amount"]
        tourism_tax_amount = tax["tourism_tax_amount"]
        tax_mode           = tax["tax_mode"]

        if db.use_postgres:
            conflict = db.execute("""
                SELECT id FROM bookings
                WHERE client_id = %s
                  AND room_id = %s
                  AND status NOT IN ('cancelled', 'checked_out')
                  AND check_in  < %s::date
                  AND check_out > %s::date
                LIMIT 1
            """, (cid, int(room_id), check_out, check_in), fetch="one")
            if conflict:
                raise HTTPException(409, "الغرفة محجوزة في هذه الفترة — يرجى اختيار غرفة أخرى أو تاريخ مختلف")

        booking_number = "BK-" + secrets.token_hex(4).upper()
        booking_id = secrets.token_hex(10)

        if db.use_postgres:
            row = db.execute("""
                INSERT INTO bookings
                    (id, client_id, booking_number, guest_id, room_id,
                     check_in, check_out, source, total_room, status,
                     tax_mode, vat_amount, tourism_tax_amount)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, 'confirmed', %s, %s, %s)
                RETURNING *
            """, (
                booking_id, cid, booking_number, guest_id, int(room_id),
                check_in, check_out, source, grand_total,
                tax_mode, vat_amount, tourism_tax_amount,
            ), fetch="one")
            result = dict(row)
            result["tax_breakdown"] = tax
            return {"success": True, "data": result}
        return {"success": True, "data": {
            **data,
            "booking_number": booking_number,
            "tax_breakdown": tax,
        }}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(500, str(e))


@router.put("/reservations/{booking_id}")
async def update_reservation(booking_id: str, request: Request,
                             session=Depends(_require_client)):
    try:
        data = await request.json()
        db = request.app.state.db
        _ensure_booking_tax_cols(db)
        cid = session["client_id"]
        if db.use_postgres:
            fields = []
            params = []
            if "status" in data:
                fields.append("status=%s")
                params.append(data["status"])
            if "notes" in data:
                fields.append("notes=%s")
                params.append(data["notes"])
            if "total_amount" in data:
                # إعادة حساب الضريبة عند تحديث المبلغ
                tax_cfg = get_client_tax_config(db, cid)
                tax = _calc_tax(amount=float(data["total_amount"]), config=tax_cfg)
                fields.append("total_room=%s")
                params.append(tax["grand_total"])
                fields.append("tax_mode=%s")
                params.append(tax["tax_mode"])
                fields.append("vat_amount=%s")
                params.append(tax["vat_amount"])
                fields.append("tourism_tax_amount=%s")
                params.append(tax["tourism_tax_amount"])
            if not fields:
                raise HTTPException(400, "لا توجد حقول للتحديث")
            fields.append("updated_at=NOW()")
            params.extend([booking_id, cid])
            db.execute(
                f"UPDATE bookings SET {', '.join(fields)} WHERE id=%s AND client_id=%s",
                params
            )
        return {"success": True}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(500, str(e))


@router.delete("/reservations/{booking_id}")
async def cancel_reservation(booking_id: str, request: Request,
                             session=Depends(_require_client)):
    try:
        db = request.app.state.db
        cid = session["client_id"]
        if db.use_postgres:
            db.execute("""
                UPDATE bookings SET status='cancelled', updated_at=NOW()
                WHERE id=%s AND client_id=%s
            """, (booking_id, cid))
        return {"success": True}
    except Exception as e:
        raise HTTPException(500, str(e))


@router.get("/stats")
async def booking_stats(request: Request, session=Depends(_require_client)):
    try:
        db = request.app.state.db
        cid = session["client_id"]
        if db.use_postgres:
            row = db.execute("""
                SELECT
                    COUNT(*)                                                  AS total_bookings,
                    COUNT(*) FILTER (WHERE status = 'confirmed')             AS confirmed,
                    COUNT(*) FILTER (WHERE status = 'checked_in')            AS checked_in,
                    COUNT(*) FILTER (WHERE status = 'checked_out')           AS checked_out,
                    COUNT(*) FILTER (WHERE status = 'cancelled')             AS cancelled,
                    COALESCE(SUM(total_room)
                        FILTER (WHERE status NOT IN ('cancelled')), 0)       AS total_revenue,
                    COALESCE(SUM(COALESCE(vat_amount, 0))
                        FILTER (WHERE status NOT IN ('cancelled')), 0)       AS total_vat,
                    COALESCE(SUM(COALESCE(tourism_tax_amount, 0))
                        FILTER (WHERE status NOT IN ('cancelled')), 0)       AS total_tourism_tax
                FROM bookings
                WHERE client_id = %s
                  AND DATE_TRUNC('month', created_at) = DATE_TRUNC('month', NOW())
            """, (cid,), fetch="one")
            stats = dict(row) if row else {}
            return {
                "success": True,
                "total_bookings":    stats.get("total_bookings", 0),
                "confirmed":         stats.get("confirmed", 0),
                "checked_in":        stats.get("checked_in", 0),
                "checked_out":       stats.get("checked_out", 0),
                "cancelled":         stats.get("cancelled", 0),
                "total_revenue":     float(stats.get("total_revenue", 0)),
                "total_vat":         float(stats.get("total_vat", 0)),
                "total_tourism_tax": float(stats.get("total_tourism_tax", 0)),
            }
        return {
            "success": True,
            "total_bookings": 0, "confirmed": 0, "checked_in": 0,
            "checked_out": 0, "cancelled": 0, "total_revenue": 0.0,
            "total_vat": 0.0, "total_tourism_tax": 0.0,
        }
    except Exception as e:
        raise HTTPException(500, str(e))


@router.get("/calendar")
async def booking_calendar(request: Request,
                           date_from: Optional[str] = None,
                           date_to: Optional[str] = None,
                           session=Depends(_require_client)):
    try:
        from datetime import date, timedelta
        db = request.app.state.db
        cid = session["client_id"]
        if db.use_postgres:
            today = date.today()
            dfrom = date_from or today.replace(day=1).isoformat()
            dto = date_to or (today + timedelta(days=60)).isoformat()
            rows = db.execute("""
                SELECT
                    b.id,
                    COALESCE(g.full_name, 'ضيف') || ' — ' || COALESCE(r.room_number, '') AS title,
                    b.check_in   AS start,
                    b.check_out  AS "end",
                    b.status,
                    b.source
                FROM bookings b
                LEFT JOIN guests g ON b.guest_id = g.id
                LEFT JOIN rooms  r ON b.room_id  = r.id
                WHERE b.client_id = %s
                  AND b.check_in  >= %s
                  AND b.check_out <= %s
                  AND b.status NOT IN ('cancelled')
                ORDER BY b.check_in
            """, (cid, dfrom, dto), fetch="all")
            events = []
            for r in (rows or []):
                d = dict(r)
                events.append({
                    "id":     d.get("id"),
                    "title":  d.get("title", ""),
                    "start":  d.get("start").isoformat() if d.get("start") else None,
                    "end":    d.get("end").isoformat()   if d.get("end")   else None,
                    "status": d.get("status"),
                    "source": d.get("source"),
                })
            return {"success": True, "data": events}
        return {"success": True, "data": []}
    except Exception as e:
        raise HTTPException(500, str(e))
