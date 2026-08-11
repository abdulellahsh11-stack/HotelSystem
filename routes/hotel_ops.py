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
    log,
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


ROOM_STATUSES = ("available", "occupied", "dirty", "maintenance", "blocked")


def _clean_room_payload(data: dict) -> dict:
    """
    يتحقق من بيانات الغرفة ويُطبّعها، ويرمي ValueError برسالة عربية.

    التحقق هنا لا في الواجهة وحدها: الـAPI عامٌّ لمن يملك جلسة، والاعتماد
    على المتصفح في التحقق يعني أن أي طلب مباشر يكتب بيانات فاسدة.
    """
    number = str(data.get("room_number") or "").strip()
    if not number:
        raise ValueError("رقم الغرفة مطلوب")
    if len(number) > 20:
        raise ValueError("رقم الغرفة أطول من ٢٠ محرفاً")

    try:
        capacity = int(data.get("capacity") or 2)
    except (TypeError, ValueError):
        raise ValueError("سعة الغرفة يجب أن تكون رقماً") from None
    if not 1 <= capacity <= 50:
        raise ValueError("سعة الغرفة يجب أن تكون بين ١ و٥٠")

    try:
        price = float(data.get("base_price") or 0)
    except (TypeError, ValueError):
        raise ValueError("السعر يجب أن يكون رقماً") from None
    if price < 0:
        raise ValueError("السعر لا يكون سالباً")

    try:
        floor = int(data.get("floor") or 1)
    except (TypeError, ValueError):
        raise ValueError("الطابق يجب أن يكون رقماً") from None

    status = str(data.get("status") or "available").strip()
    if status not in ROOM_STATUSES:
        raise ValueError(f"حالة غير معروفة. المسموح: {'، '.join(ROOM_STATUSES)}")

    return {
        "room_number": number,
        "room_type": str(data.get("room_type") or "standard").strip()[:100],
        "floor": floor,
        "capacity": capacity,
        "base_price": price,
        "status": status,
        "notes": str(data.get("notes") or "").strip()[:1000],
    }


@router.post("/api/rooms")
async def save_room(request: Request, session=Depends(require_client)):
    """يُسجّل غرفة جديدة أو يُعدّل قائمة. `id` في الجسم يعني تعديلاً."""
    data = await request.json()
    db = request.app.state.db
    cid = session["client_id"]
    room_id = data.get("id")

    try:
        room = _clean_room_payload(data)
    except ValueError as exc:
        return JSONResponse({"success": False, "error": str(exc)}, status_code=400)

    try:
        if room_id:
            db.execute(
                """UPDATE rooms SET room_number=%s,room_type=%s,floor=%s,
                   capacity=%s,base_price=%s,status=%s,notes=%s
                   WHERE id=%s AND client_id=%s""",
                (room["room_number"], room["room_type"], room["floor"],
                 room["capacity"], room["base_price"], room["status"],
                 room["notes"], room_id, cid)
            )
        else:
            db.execute(
                """INSERT INTO rooms(client_id,room_number,room_type,floor,
                                     capacity,base_price,status,notes)
                   VALUES(%s,%s,%s,%s,%s,%s,%s,%s)""",
                (cid, room["room_number"], room["room_type"], room["floor"],
                 room["capacity"], room["base_price"], room["status"], room["notes"])
            )
        return {"success": True, "data": room}
    except Exception as exc:
        # القيد UNIQUE(client_id, room_number) هو الخطأ المتوقّع هنا؛
        # رسالة قاعدة البيانات الخام غير مفهومة لصاحب المنشأة.
        text = str(exc).lower()
        if "unique" in text or "duplicate" in text:
            return JSONResponse(
                {"success": False, "error": f"الغرفة رقم {room['room_number']} مسجَّلة مسبقاً"},
                status_code=409,
            )
        log.error("فشل حفظ الغرفة للمنشأة %s: %s", cid, exc, exc_info=True)
        return JSONResponse(
            {"success": False, "error": "تعذّر حفظ الغرفة"}, status_code=500
        )


@router.delete("/api/rooms/{room_id}")
async def delete_room(room_id: int, request: Request, session=Depends(require_client)):
    """
    يحذف غرفة. يُرفض الحذف إن كانت مرتبطة بحجوزات قائمة.

    الحذف الصامت لغرفة عليها حجز يترك الحجز معلّقاً بلا غرفة، وهو فساد
    بيانات يظهر متأخّراً عند وصول الضيف.
    """
    db = request.app.state.db
    cid = session["client_id"]
    try:
        row = db.execute(
            "SELECT room_number FROM rooms WHERE id=%s AND client_id=%s",
            (room_id, cid), fetch="one"
        )
        if not row:
            raise HTTPException(status_code=404, detail="الغرفة غير موجودة")

        active = db.execute(
            """SELECT COUNT(*) AS n FROM bookings
               WHERE client_id=%s AND room_number=%s
                 AND status IN ('confirmed','checked_in')""",
            (cid, row["room_number"]), fetch="one"
        )
        if active and (active.get("n") or 0) > 0:
            raise HTTPException(
                status_code=409,
                detail=f"لا يمكن حذف الغرفة — عليها {active['n']} حجز قائم",
            )

        db.execute("DELETE FROM rooms WHERE id=%s AND client_id=%s", (room_id, cid))
        return {"success": True}
    except HTTPException:
        raise
    except Exception as exc:
        log.error("فشل حذف الغرفة %s للمنشأة %s: %s", room_id, cid, exc, exc_info=True)
        return JSONResponse(
            {"success": False, "error": "تعذّر حذف الغرفة"}, status_code=500
        )


