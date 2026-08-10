#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
routes/hotel_ops.py — العمليات الفندقية — الضيوف والحجوزات والفواتير ونقاط البيع والغرف
مُستخرَج ضمن تقسيم ملف المسارات الكبير لتسهيل الصيانة.
"""
import secrets
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import (
    JSONResponse,
)

from app_core import (
    require_client,
)

router = APIRouter()

# ──────────────────────────────────────────────────────────────
#  Guests
# ──────────────────────────────────────────────────────────────
@router.get("/api/guests")
async def get_guests(request: Request, limit: int = 100, session=Depends(require_client)):
    store = request.app.state.store
    guests = store.get_guests(session["client_id"])
    return {"success": True, "data": guests[:limit]}


@router.post("/api/guests")
async def save_guest(request: Request, session=Depends(require_client)):
    data = await request.json()
    store = request.app.state.store
    if not data.get("id"):
        data["id"] = secrets.token_hex(8)
    data["client_id"] = session["client_id"]
    data.setdefault("created_at", datetime.now().isoformat())
    guest = store.save_guest(session["client_id"], data)
    return {"success": True, "data": guest}


@router.get("/api/guests/{guest_id}")
async def get_guest(guest_id: str, request: Request, session=Depends(require_client)):
    store = request.app.state.store
    guests = store.get_guests(session["client_id"])
    guest = next((g for g in guests if str(g.get("id")) == guest_id), None)
    if not guest:
        raise HTTPException(status_code=404, detail="الضيف غير موجود")
    return {"success": True, "data": guest}


# ──────────────────────────────────────────────────────────────
#  Bookings
# ──────────────────────────────────────────────────────────────
@router.get("/api/bookings")
async def get_bookings(
    request: Request, status: Optional[str] = None, limit: int = 100,
    session=Depends(require_client)
):
    store = request.app.state.store
    bookings = store.get_bookings(session["client_id"], status)
    return {"success": True, "data": bookings[:limit]}


@router.post("/api/bookings")
async def save_booking(request: Request, session=Depends(require_client)):
    data = await request.json()
    store = request.app.state.store
    if not data.get("id"):
        data["id"] = secrets.token_hex(8)
    data["client_id"] = session["client_id"]
    data.setdefault("status", "confirmed")
    data.setdefault("created_at", datetime.now().isoformat())
    booking = store.save_booking(session["client_id"], data)
    return {"success": True, "data": booking}


@router.put("/api/bookings/{booking_id}")
async def update_booking(booking_id: str, request: Request, session=Depends(require_client)):
    data = await request.json()
    data["id"] = booking_id
    data["client_id"] = session["client_id"]
    store = request.app.state.store
    booking = store.save_booking(session["client_id"], data)
    return {"success": True, "data": booking}


# ──────────────────────────────────────────────────────────────
#  Invoices
# ──────────────────────────────────────────────────────────────
@router.get("/api/invoices")
async def get_invoices(request: Request, limit: int = 100, session=Depends(require_client)):
    store = request.app.state.store
    invoices = store.get_invoices(session["client_id"])
    return {"success": True, "data": invoices[:limit]}


@router.post("/api/invoices")
async def save_invoice(request: Request, session=Depends(require_client)):
    data = await request.json()
    store = request.app.state.store
    cid = session["client_id"]
    if not data.get("id"):
        seq = store.get_next_invoice_seq(cid)
        data["id"] = f"INV-{seq:05d}"
    data["client_id"] = cid
    data.setdefault("created_at", datetime.now().isoformat())
    invoice = store.save_invoice(cid, data)
    return {"success": True, "data": invoice}


# ──────────────────────────────────────────────────────────────
#  POS Transactions
# ──────────────────────────────────────────────────────────────
@router.get("/api/pos")
async def get_pos(
    request: Request, date_from: Optional[str] = None, date_to: Optional[str] = None,
    session=Depends(require_client)
):
    store = request.app.state.store
    txns = store.get_pos_transactions(session["client_id"], date_from, date_to)
    return {"success": True, "data": txns}


@router.post("/api/pos")
async def save_pos(request: Request, session=Depends(require_client)):
    data = await request.json()
    store = request.app.state.store
    if not data.get("id"):
        data["id"] = secrets.token_hex(8)
    data["client_id"] = session["client_id"]
    data.setdefault("created_at", datetime.now().isoformat())
    tx = store.save_pos_transaction(session["client_id"], data)
    return {"success": True, "data": tx}


# ──────────────────────────────────────────────────────────────
#  Settings
# ──────────────────────────────────────────────────────────────
@router.get("/api/settings")
async def get_settings(request: Request, session=Depends(require_client)):
    store = request.app.state.store
    client = store.get_client(session["client_id"]) or {}
    return {"success": True, "data": client.get("settings", {})}


@router.post("/api/settings")
async def save_settings(request: Request, session=Depends(require_client)):
    data = await request.json()
    store = request.app.state.store
    cid = session["client_id"]
    client = store.get_client(cid) or {"id": cid}
    client["settings"] = data
    store.save_client(client)
    return {"success": True}


# ──────────────────────────────────────────────────────────────
#  Rooms
# ──────────────────────────────────────────────────────────────
@router.get("/api/rooms")
async def get_rooms(request: Request, session=Depends(require_client)):
    db = request.app.state.db
    cid = session["client_id"]
    try:
        rows = db.execute(
            "SELECT * FROM rooms WHERE client_id=%s ORDER BY room_number", (cid,), fetch="all"
        )
        return {"success": True, "data": [dict(r) for r in (rows or [])]}
    except Exception as e:
        return {"success": True, "data": [], "warning": str(e)}


@router.post("/api/rooms")
async def save_room(request: Request, session=Depends(require_client)):
    data = await request.json()
    db = request.app.state.db
    cid = session["client_id"]
    room_id = data.get("id")
    try:
        if room_id:
            db.execute(
                """UPDATE rooms SET room_number=%s,room_type=%s,floor=%s,
                   capacity=%s,base_price=%s,status=%s,updated_at=NOW()
                   WHERE id=%s AND client_id=%s""",
                (data.get("room_number"), data.get("room_type"), data.get("floor"),
                 data.get("capacity", 2), data.get("base_price", 0),
                 data.get("status", "available"), room_id, cid)
            )
        else:
            db.execute(
                """INSERT INTO rooms(client_id,room_number,room_type,floor,capacity,base_price,status)
                   VALUES(%s,%s,%s,%s,%s,%s,%s)""",
                (cid, data.get("room_number"), data.get("room_type", "standard"),
                 data.get("floor", 1), data.get("capacity", 2),
                 data.get("base_price", 0), data.get("status", "available"))
            )
        return {"success": True}
    except Exception as e:
        return JSONResponse({"success": False, "error": str(e)}, status_code=500)


