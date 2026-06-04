#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""M17 — حجوزات القنوات Channel Bookings"""
import secrets
from typing import Optional
from fastapi import APIRouter, Request, Depends, HTTPException

router = APIRouter(prefix="/api/m17", tags=["ChannelBookings"])


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
                    b.total_room  AS total_amount,
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
            total = count_result[0] if count_result else 0
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
        cid = session["client_id"]

        guest_id = data.get("guest_id")

        # If no guest_id provided, create a new guest record from name + phone
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

        if db.use_postgres:
            # Double-booking check: reject if room has an overlapping active booking
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
                     check_in, check_out, source, total_room, status)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, 'confirmed')
                RETURNING *
            """, (
                booking_id,
                cid,
                booking_number,
                guest_id,
                int(room_id),
                check_in,
                check_out,
                source,
                total_amount,
            ), fetch="one")
            return {"success": True, "data": dict(row)}
        return {"success": True, "data": {**data, "booking_number": booking_number}}
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
                fields.append("total_room=%s")
                params.append(float(data["total_amount"]))
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
                        FILTER (WHERE status NOT IN ('cancelled')), 0)       AS total_revenue
                FROM bookings
                WHERE client_id = %s
                  AND DATE_TRUNC('month', created_at) = DATE_TRUNC('month', NOW())
            """, (cid,), fetch="one")
            stats = dict(row) if row else {}
            return {
                "success": True,
                "total_bookings": stats.get("total_bookings", 0),
                "confirmed": stats.get("confirmed", 0),
                "checked_in": stats.get("checked_in", 0),
                "checked_out": stats.get("checked_out", 0),
                "cancelled": stats.get("cancelled", 0),
                "total_revenue": float(stats.get("total_revenue", 0)),
            }
        return {
            "success": True,
            "total_bookings": 0,
            "confirmed": 0,
            "checked_in": 0,
            "checked_out": 0,
            "cancelled": 0,
            "total_revenue": 0.0,
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
            # Default: show next 60 days if no date_to provided
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
