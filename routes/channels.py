"""
routes/channels.py — FastAPI APIRouter for Channel Manager.
"""

import json
import logging
import threading
from typing import Optional

from fastapi import APIRouter, Request, Depends, HTTPException
from fastapi.responses import JSONResponse

log = logging.getLogger("routes.channels")

router = APIRouter(prefix="/api/channels", tags=["channels"])

BOOKING_COM_IPS = {"62.183.80.", "213.207.", "185.34.194."}


def _client_session(request: Request) -> dict:
    from main import require_client
    return require_client(request)


@router.get("/status/{client_id}")
async def channel_status(client_id: str, request: Request, session=Depends(_client_session)):
    channels = request.app.state.channels
    db = request.app.state.db
    if not channels:
        return {"success": True, "data": {}}
    try:
        status = channels.get_status(client_id)
        for ch_name in status:
            try:
                rows = db.execute(
                    """SELECT created_at, status, records_count
                       FROM channel_sync_log
                       WHERE client_id=%s AND channel_name=%s
                       ORDER BY created_at DESC LIMIT 1""",
                    (client_id, ch_name), fetch="all"
                )
                if rows:
                    r = rows[0]
                    ca = r.get("created_at")
                    status[ch_name]["last_sync"] = ca.isoformat() if hasattr(ca, "isoformat") else str(ca)
                    status[ch_name]["last_sync_status"] = r.get("status", "")
            except Exception:
                pass
        return {"success": True, "data": status}
    except Exception as e:
        return JSONResponse({"success": False, "error": str(e)}, status_code=500)


@router.post("/booking-com/webhook")
async def booking_com_webhook(request: Request):
    channels = request.app.state.channels
    db = request.app.state.db
    if not channels:
        return {"status": "ok"}

    body = await request.body()
    src_ip = request.client.host if request.client else ""

    def _process():
        try:
            ch = channels.get_channel("booking.com")
            if not ch:
                return
            result = ch.process_webhook(body.decode(), src_ip)
            action = result.get("action", "unknown")
            if action in ("ignore", "error"):
                return
            reservation = result.get("reservation", {})
            if not reservation:
                return
            hotel_id = getattr(ch.config, "hotel_id", "")
            rows = db.execute(
                "SELECT client_id FROM channel_configs WHERE channel_name='booking.com' AND credentials->>'hotel_id'=%s LIMIT 1",
                (hotel_id,), fetch="all"
            ) or []
            if not rows:
                rows = db.execute("SELECT id as client_id FROM clients LIMIT 1", fetch="all") or []
            if not rows:
                return
            cid = rows[0]["client_id"]
            if action == "NewReservation":
                channels._process_reservation(cid, "booking.com", reservation)
            elif action == "CancelledReservation":
                _cancel(cid, reservation.get("channel_reservation_id", ""), db)
            elif action == "ModifiedReservation":
                _modify(cid, reservation, db)
        except Exception as e:
            log.error(f"webhook error: {e}")

    threading.Thread(target=_process, daemon=True).start()
    return {"status": "ok"}


def _cancel(client_id: str, channel_res_id: str, db):
    rows = db.execute(
        "SELECT booking_id FROM channel_reservations WHERE client_id=%s AND channel_reservation_id=%s LIMIT 1",
        (client_id, channel_res_id), fetch="all"
    )
    if rows:
        db.execute(
            "UPDATE bookings SET status='cancelled' WHERE id=%s AND client_id=%s",
            (rows[0]["booking_id"], client_id)
        )


def _modify(client_id: str, reservation: dict, db):
    rows = db.execute(
        "SELECT booking_id FROM channel_reservations WHERE client_id=%s AND channel_reservation_id=%s LIMIT 1",
        (client_id, reservation.get("channel_reservation_id", "")), fetch="all"
    )
    if rows:
        db.execute(
            """UPDATE bookings SET check_in=%s,check_out=%s,adults=%s,
               total_amount=%s,updated_at=NOW()
               WHERE id=%s AND client_id=%s""",
            (reservation.get("check_in"), reservation.get("check_out"),
             reservation.get("adults", 1), reservation.get("total_amount", 0),
             rows[0]["booking_id"], client_id)
        )


@router.post("/booking-com/settings")
async def booking_com_settings(request: Request, session=Depends(_client_session)):
    data = await request.json()
    db = request.app.state.db
    cid = session["client_id"]
    creds = json.dumps({
        "hotel_id": data.get("hotel_id", ""),
        "api_key": data.get("api_key", ""),
        "username": data.get("username", ""),
    })
    try:
        db.execute(
            """INSERT INTO channel_configs(client_id,channel_name,credentials,is_enabled)
               VALUES(%s,'booking.com',%s,false)
               ON CONFLICT(client_id,channel_name)
               DO UPDATE SET credentials=EXCLUDED.credentials,updated_at=NOW()""",
            (cid, creds)
        )
        return {"success": True}
    except Exception as e:
        return JSONResponse({"success": False, "error": str(e)}, status_code=500)


@router.post("/booking-com/test")
async def booking_com_test(request: Request, session=Depends(_client_session)):
    channels = request.app.state.channels
    if not channels:
        return JSONResponse({"success": False, "error": "Channel Manager غير متاح"}, status_code=503)
    ch = channels.get_channel("booking.com")
    if not ch:
        return JSONResponse({"success": False, "error": "Booking.com غير مُعدّ"}, status_code=400)
    result = ch.test_connection()
    return result.to_dict() if hasattr(result, "to_dict") else result


@router.post("/booking-com/sync")
async def booking_com_sync(request: Request, session=Depends(_client_session)):
    data = await request.json()
    cid = data.get("client_id") or session["client_id"]
    channels = request.app.state.channels
    if not channels:
        return JSONResponse({"success": False, "error": "Channel Manager غير متاح"}, status_code=503)
    try:
        result = channels.pull_all_reservations(cid)
        return {"success": True, "data": result}
    except Exception as e:
        return JSONResponse({"success": False, "error": str(e)}, status_code=500)


@router.get("/booking-com/reservations")
async def booking_com_reservations(request: Request, limit: int = 50, session=Depends(_client_session)):
    db = request.app.state.db
    cid = session["client_id"]
    try:
        rows = db.execute(
            """SELECT cr.*, b.check_in, b.check_out, b.total_amount, b.status,
                      g.name as guest_name, g.phone as guest_phone
               FROM channel_reservations cr
               JOIN bookings b ON b.id = cr.booking_id
               LEFT JOIN guests g ON g.id = b.guest_id
               WHERE cr.client_id=%s AND cr.channel_name='booking.com'
               ORDER BY cr.created_at DESC LIMIT %s""",
            (cid, limit), fetch="all"
        )
        return {"success": True, "data": [dict(r) for r in (rows or [])]}
    except Exception as e:
        return JSONResponse({"success": False, "error": str(e)}, status_code=500)


@router.post("/mawasim/settings")
async def mawasim_settings(request: Request, session=Depends(_client_session)):
    data = await request.json()
    db = request.app.state.db
    cid = session["client_id"]
    ical_url = data.get("ical_url", "")
    if not ical_url:
        return JSONResponse({"success": False, "error": "رابط iCal مطلوب"}, status_code=400)
    try:
        db.execute(
            """INSERT INTO channel_configs(client_id,channel_name,credentials,is_enabled)
               VALUES(%s,'mawasim',%s,true)
               ON CONFLICT(client_id,channel_name)
               DO UPDATE SET credentials=EXCLUDED.credentials,is_enabled=true""",
            (cid, json.dumps({"ical_url": ical_url}))
        )
        return {"success": True}
    except Exception as e:
        return JSONResponse({"success": False, "error": str(e)}, status_code=500)


@router.post("/mawasim/test")
async def mawasim_test(request: Request, session=Depends(_client_session)):
    channels = request.app.state.channels
    if not channels:
        return JSONResponse({"success": False, "error": "Channel Manager غير متاح"}, status_code=503)
    ch = channels.get_channel("mawasim")
    if not ch:
        return JSONResponse({"success": False, "error": "موزن غير مُعدّ"}, status_code=400)
    result = ch.test_connection()
    return result.to_dict() if hasattr(result, "to_dict") else result


@router.get("/room-mapping/{client_id}")
async def get_room_mapping(client_id: str, request: Request, session=Depends(_client_session)):
    db = request.app.state.db
    try:
        rooms = db.execute(
            "SELECT id,room_number,room_type FROM rooms WHERE client_id=%s ORDER BY room_number",
            (client_id,), fetch="all"
        ) or []
        configs = db.execute(
            "SELECT channel_name,room_mapping FROM channel_configs WHERE client_id=%s",
            (client_id,), fetch="all"
        ) or []
        mappings = {}
        for row in configs:
            m = row.get("room_mapping") or {}
            if isinstance(m, str):
                try:
                    m = json.loads(m)
                except Exception:
                    m = {}
            mappings[row["channel_name"]] = m
        return {"success": True, "data": {"system_rooms": [dict(r) for r in rooms], "mappings": mappings}}
    except Exception as e:
        return JSONResponse({"success": False, "error": str(e)}, status_code=500)


@router.post("/room-mapping")
async def save_room_mapping(request: Request, session=Depends(_client_session)):
    data = await request.json()
    db = request.app.state.db
    cid = session["client_id"]
    ch_name = data.get("channel_name")
    mapping = data.get("mapping", {})
    if not ch_name:
        return JSONResponse({"success": False, "error": "channel_name مطلوب"}, status_code=400)
    try:
        db.execute(
            "UPDATE channel_configs SET room_mapping=%s WHERE client_id=%s AND channel_name=%s",
            (json.dumps(mapping), cid, ch_name)
        )
        return {"success": True}
    except Exception as e:
        return JSONResponse({"success": False, "error": str(e)}, status_code=500)


@router.get("/sync-log/{client_id}")
async def sync_log(client_id: str, request: Request, channel: Optional[str] = None, session=Depends(_client_session)):
    db = request.app.state.db
    try:
        q = "SELECT * FROM channel_sync_log WHERE client_id=%s"
        p: list = [client_id]
        if channel:
            q += " AND channel_name=%s"
            p.append(channel)
        q += " ORDER BY created_at DESC LIMIT 50"
        rows = db.execute(q, tuple(p), fetch="all") or []
        return {"success": True, "data": [dict(r) for r in rows]}
    except Exception as e:
        return {"success": True, "data": [], "warning": str(e)}


@router.get("/revenue-split/{client_id}")
async def revenue_split(client_id: str, request: Request, days: int = 30, session=Depends(_client_session)):
    channels = request.app.state.channels
    if not channels:
        return {"success": True, "data": {}}
    try:
        return {"success": True, "data": channels.get_revenue_split(client_id, days)}
    except Exception as e:
        return JSONResponse({"success": False, "error": str(e)}, status_code=500)
