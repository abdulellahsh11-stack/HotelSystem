#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""routes/m01_guests.py — إدارة الضيوف Guest Management"""
from typing import Optional
from fastapi import APIRouter, Request, Depends, HTTPException

router = APIRouter(prefix="/api/m01", tags=["Guests"])


def _require_client(request: Request) -> dict:
    from main import require_client
    return require_client(request)


@router.get("/guests")
async def list_guests(request: Request, search: Optional[str] = None,
                      nationality: Optional[str] = None, session=Depends(_require_client)):
    db = request.app.state.db
    cid = session["client_id"]
    if db.use_postgres:
        q = "SELECT * FROM guests WHERE client_id=%s"
        params = [cid]
        if search:
            q += " AND (full_name ILIKE %s OR absher_phone ILIKE %s OR id_number ILIKE %s)"
            s = f"%{search}%"
            params += [s, s, s]
        if nationality:
            q += " AND nationality=%s"; params.append(nationality)
        q += " ORDER BY created_at DESC LIMIT 200"
        rows = db.execute(q, params, fetch="all")
        return {"success": True, "data": [dict(r) for r in (rows or [])]}
    return {"success": True, "data": []}


@router.get("/guests/{guest_id}")
async def get_guest(guest_id: int, request: Request, session=Depends(_require_client)):
    db = request.app.state.db
    cid = session["client_id"]
    if db.use_postgres:
        row = db.execute("SELECT * FROM guests WHERE id=%s AND client_id=%s",
                         (guest_id, cid), fetch="one")
        if not row:
            raise HTTPException(404, "الضيف غير موجود")
        bookings = db.execute("""
            SELECT b.*, r.room_number FROM bookings b
            LEFT JOIN rooms r ON b.room_id = r.id
            WHERE b.guest_id=%s AND b.client_id=%s ORDER BY b.created_at DESC LIMIT 10
        """, (guest_id, cid), fetch="all")
        return {"success": True, "data": dict(row),
                "bookings": [dict(b) for b in (bookings or [])]}
    return {"success": True, "data": {}}


@router.post("/guests")
async def create_guest(request: Request, session=Depends(_require_client)):
    data = await request.json()
    db = request.app.state.db
    cid = session["client_id"]
    if not data.get("full_name"):
        raise HTTPException(400, "full_name مطلوب")
    if db.use_postgres:
        row = db.execute("""
            INSERT INTO guests (client_id,full_name,id_type,id_number,
                absher_phone,nationality,birth_date,data_status,source,notes)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING *
        """, (cid, data["full_name"], data.get("id_type", "national_id"),
              data.get("id_number"), data.get("absher_phone"),
              data.get("nationality", "سعودي"), data.get("birth_date"),
              data.get("data_status", "incomplete"), data.get("source"),
              data.get("notes")), fetch="one")
        return {"success": True, "data": dict(row)}
    return {"success": True, "data": data}


@router.put("/guests/{guest_id}")
async def update_guest(guest_id: int, request: Request, session=Depends(_require_client)):
    data = await request.json()
    db = request.app.state.db
    cid = session["client_id"]
    if db.use_postgres:
        db.execute("""
            UPDATE guests SET full_name=%s,id_type=%s,id_number=%s,
            absher_phone=%s,nationality=%s,birth_date=%s,
            data_status=%s,notes=%s
            WHERE id=%s AND client_id=%s
        """, (data.get("full_name"), data.get("id_type"),
              data.get("id_number"), data.get("absher_phone"),
              data.get("nationality"), data.get("birth_date"),
              data.get("data_status", "complete"), data.get("notes"),
              guest_id, cid))
    return {"success": True}


@router.delete("/guests/{guest_id}")
async def delete_guest(guest_id: int, request: Request, session=Depends(_require_client)):
    db = request.app.state.db
    cid = session["client_id"]
    if db.use_postgres:
        has_bookings = db.execute(
            "SELECT 1 FROM bookings WHERE guest_id=%s AND client_id=%s LIMIT 1",
            (guest_id, cid), fetch="one")
        if has_bookings:
            raise HTTPException(400, "لا يمكن حذف ضيف لديه حجوزات")
        db.execute("DELETE FROM guests WHERE id=%s AND client_id=%s", (guest_id, cid))
    return {"success": True}


@router.get("/profiles")
async def list_profiles(request: Request, guest_id: Optional[int] = None,
                        session=Depends(_require_client)):
    db = request.app.state.db
    cid = session["client_id"]
    if db.use_postgres:
        q = "SELECT * FROM guest_profiles WHERE client_id=%s"
        params = [cid]
        if guest_id:
            q += " AND guest_id=%s"; params.append(guest_id)
        rows = db.execute(q, params, fetch="all")
        return {"success": True, "data": [dict(r) for r in (rows or [])]}
    return {"success": True, "data": []}


@router.post("/profiles")
async def upsert_profile(request: Request, session=Depends(_require_client)):
    data = await request.json()
    db = request.app.state.db
    cid = session["client_id"]
    if db.use_postgres:
        row = db.execute("""
            INSERT INTO guest_profiles
                (client_id,guest_id,vip_level,dietary_notes,tags)
            VALUES (%s,%s,%s,%s,%s)
            ON CONFLICT (client_id,guest_id) DO UPDATE SET
                vip_level=EXCLUDED.vip_level,
                dietary_notes=EXCLUDED.dietary_notes,
                tags=EXCLUDED.tags
            RETURNING *
        """, (cid, data.get("guest_id"), data.get("vip_level", "standard"),
              data.get("dietary_notes"), data.get("tags", "[]")),
              fetch="one")
        return {"success": True, "data": dict(row)}
    return {"success": True, "data": data}


@router.get("/stats")
async def guests_stats(request: Request, session=Depends(_require_client)):
    db = request.app.state.db
    cid = session["client_id"]
    if db.use_postgres:
        total = db.execute("SELECT COUNT(*) as c FROM guests WHERE client_id=%s",
                           (cid,), fetch="one")
        new_month = db.execute("""
            SELECT COUNT(*) as c FROM guests WHERE client_id=%s
            AND DATE_TRUNC('month',created_at)=DATE_TRUNC('month',NOW())
        """, (cid,), fetch="one")
        nationalities = db.execute("""
            SELECT nationality, COUNT(*) as cnt FROM guests WHERE client_id=%s
            GROUP BY nationality ORDER BY cnt DESC LIMIT 10
        """, (cid,), fetch="all")
        vip = db.execute("""
            SELECT COUNT(*) as c FROM guest_profiles
            WHERE client_id=%s AND vip_level IN ('vip','vvip')
        """, (cid,), fetch="one")
        return {
            "success": True,
            "total_guests": (total or {}).get("c", 0),
            "new_this_month": (new_month or {}).get("c", 0),
            "vip_guests": (vip or {}).get("c", 0),
            "top_nationalities": [dict(r) for r in (nationalities or [])]
        }
    return {"success": True, "total_guests": 0}
