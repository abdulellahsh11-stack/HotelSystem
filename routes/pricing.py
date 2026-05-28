"""
routes/pricing.py — FastAPI APIRouter for Dynamic Pricing.
"""

import logging
from datetime import date
from typing import Optional

from fastapi import APIRouter, Request, Depends
from fastapi.responses import JSONResponse

log = logging.getLogger("routes.pricing")

router = APIRouter(prefix="/api/pricing", tags=["pricing"])


def _client_session(request: Request) -> dict:
    from main import require_client
    return require_client(request)


@router.get("/rules/{client_id}")
async def get_pricing_rules(
    client_id: str, request: Request,
    room_id: Optional[int] = None,
    session=Depends(_client_session)
):
    pricing = request.app.state.pricing
    if not pricing:
        return {"success": True, "data": []}
    try:
        if room_id:
            data = pricing.get_or_save_rules(client_id, room_id)
        else:
            data = pricing._get_rooms_with_rules(client_id)
        return {"success": True, "data": data}
    except Exception as e:
        return JSONResponse({"success": False, "error": str(e)}, status_code=500)


@router.post("/rules")
async def save_pricing_rules(request: Request, session=Depends(_client_session)):
    data = await request.json()
    pricing = request.app.state.pricing
    if not pricing:
        return JSONResponse({"success": False, "error": "خدمة التسعير غير متاحة"}, status_code=503)
    cid = data.get("client_id") or session["client_id"]
    room_id = data.get("room_id")
    if not room_id:
        return JSONResponse({"success": False, "error": "room_id مطلوب"}, status_code=400)
    if float(data.get("base_price", 0)) <= 0:
        return JSONResponse({"success": False, "error": "base_price يجب أن يكون أكبر من 0"}, status_code=400)
    try:
        return pricing.get_or_save_rules(cid, int(room_id), data)
    except Exception as e:
        return JSONResponse({"success": False, "error": str(e)}, status_code=500)


@router.get("/calendar/{client_id}")
async def pricing_calendar(
    client_id: str, request: Request,
    room_id: Optional[int] = None,
    days: int = 30,
    session=Depends(_client_session)
):
    pricing = request.app.state.pricing
    if not pricing:
        return {"success": True, "data": []}
    if not room_id:
        return JSONResponse({"success": False, "error": "room_id مطلوب"}, status_code=400)
    try:
        return {"success": True, "data": pricing.get_pricing_calendar(client_id, room_id, days)}
    except Exception as e:
        return JSONResponse({"success": False, "error": str(e)}, status_code=500)


@router.post("/manual-override")
async def manual_override(request: Request, session=Depends(_client_session)):
    data = await request.json()
    db = request.app.state.db
    cid = data.get("client_id") or session["client_id"]
    room_id = data.get("room_id")
    target_date = data.get("date")
    price = data.get("price")

    if not all([room_id, target_date, price]):
        return JSONResponse({"success": False, "error": "room_id و date و price مطلوبة"}, status_code=400)
    try:
        if date.fromisoformat(target_date) < date.today():
            return JSONResponse({"success": False, "error": "لا يمكن تعديل تواريخ ماضية"}, status_code=400)
        db.execute(
            """INSERT INTO room_rates(client_id,room_id,rate_date,current_rate,is_dynamic)
               VALUES(%s,%s,%s,%s,false)
               ON CONFLICT(room_id,rate_date)
               DO UPDATE SET current_rate=%s,is_dynamic=false,last_updated=NOW()""",
            (cid, room_id, target_date, price, price)
        )
        db.execute(
            """INSERT INTO pricing_history(client_id,room_id,target_date,new_price,reason)
               VALUES(%s,%s,%s,%s,'تعديل يدوي من المالك')""",
            (cid, room_id, target_date, price)
        )
        return {"success": True, "message": f"تم تعديل سعر {target_date} إلى {price} ر.س"}
    except ValueError:
        return JSONResponse({"success": False, "error": "تاريخ غير صالح"}, status_code=400)
    except Exception as e:
        return JSONResponse({"success": False, "error": str(e)}, status_code=500)


@router.get("/history/{client_id}")
async def pricing_history(
    client_id: str, request: Request,
    room_id: Optional[int] = None,
    limit: int = 50,
    session=Depends(_client_session)
):
    db = request.app.state.db
    try:
        q = """SELECT ph.*, r.room_number FROM pricing_history ph
               JOIN rooms r ON r.id = ph.room_id
               WHERE ph.client_id=%s"""
        p: list = [client_id]
        if room_id:
            q += " AND ph.room_id=%s"
            p.append(room_id)
        q += " ORDER BY ph.created_at DESC LIMIT %s"
        p.append(limit)
        rows = db.execute(q, tuple(p), fetch="all") or []
        return {"success": True, "data": [dict(r) for r in rows]}
    except Exception as e:
        return JSONResponse({"success": False, "error": str(e)}, status_code=500)


@router.post("/apply-now/{client_id}")
async def apply_pricing_now(client_id: str, request: Request, session=Depends(_client_session)):
    pricing = request.app.state.pricing
    if not pricing:
        return JSONResponse({"success": False, "error": "خدمة التسعير غير متاحة"}, status_code=503)
    if not getattr(pricing, "is_enabled", False):
        return JSONResponse({"success": False, "error": "Dynamic Pricing معطَّل"}, status_code=400)
    try:
        return {"success": True, "data": pricing.apply_pricing_for_client(client_id)}
    except Exception as e:
        return JSONResponse({"success": False, "error": str(e)}, status_code=500)


@router.get("/impact/{client_id}")
async def pricing_impact(
    client_id: str, request: Request,
    days: int = 30,
    session=Depends(_client_session)
):
    pricing = request.app.state.pricing
    if not pricing:
        return {"success": True, "data": {}}
    try:
        return {"success": True, "data": pricing.get_pricing_impact(client_id, days)}
    except Exception as e:
        return JSONResponse({"success": False, "error": str(e)}, status_code=500)


@router.get("/seasons")
async def get_seasons(session=Depends(_client_session)):
    try:
        from services.dynamic_pricing import SAUDI_SEASONS_2026
        seasons = [
            {
                "key": k,
                "label": v["label"],
                "start": v["start"].isoformat(),
                "end": v["end"].isoformat(),
                "factor": v["factor"],
                "impact_pct": round((v["factor"] - 1) * 100, 0),
            }
            for k, v in SAUDI_SEASONS_2026.items()
        ]
        return {"success": True, "data": sorted(seasons, key=lambda s: s["start"])}
    except Exception as e:
        return JSONResponse({"success": False, "error": str(e)}, status_code=500)


@router.post("/toggle")
async def toggle_pricing(request: Request, session=Depends(_client_session)):
    data = await request.json()
    pricing = request.app.state.pricing
    if not pricing:
        return JSONResponse({"success": False, "error": "خدمة التسعير غير متاحة"}, status_code=503)
    enabled = data.get("enabled", True)
    if enabled:
        pricing.enable()
    else:
        pricing.disable()
    return {
        "success": True,
        "enabled": getattr(pricing, "is_enabled", enabled),
        "message": "تم تفعيل التسعير الديناميكي" if enabled else "تم تعطيل التسعير الديناميكي",
    }
