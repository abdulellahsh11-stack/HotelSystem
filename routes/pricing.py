#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""routes/pricing.py — التسعير الديناميكي"""
import logging
from typing import Optional
from fastapi import APIRouter, Request, Depends
from fastapi.responses import JSONResponse

router = APIRouter(prefix="/api/pricing", tags=["DynamicPricing"])
log = logging.getLogger("dheuof")


def _require_client(request: Request) -> dict:
    from main import require_client
    return require_client(request)


# ── قواعد التسعير ─────────────────────────────────────────────

@router.get("/rules/{client_id}")
async def get_pricing_rules(
    client_id: str,
    request: Request,
    room_id: Optional[int] = None,
    session=Depends(_require_client),
):
    cid = session["client_id"]
    pricing = request.app.state.pricing
    if not pricing:
        return {"success": True, "data": []}
    try:
        if room_id:
            data = pricing.get_or_save_rules(cid, room_id)
        else:
            data = pricing._get_rooms_with_rules(cid)
        return {"success": True, "data": data}
    except Exception as e:
        log.error(f"get_pricing_rules: {e}", exc_info=True)
        return JSONResponse({"success": False, "error": str(e)}, status_code=500)


@router.post("/rules")
async def save_pricing_rules(request: Request, session=Depends(_require_client)):
    data = await request.json()
    pricing = request.app.state.pricing
    if not pricing:
        return JSONResponse({"success": False, "error": "خدمة التسعير غير متاحة"}, status_code=503)
    cid = session["client_id"]
    room_id = data.get("room_id")
    if not room_id:
        return JSONResponse({"success": False, "error": "room_id مطلوب"}, status_code=400)
    try:
        result = pricing.get_or_save_rules(cid, int(room_id), data)
        return result
    except Exception as e:
        log.error(f"save_pricing_rules: {e}", exc_info=True)
        return JSONResponse({"success": False, "error": str(e)}, status_code=500)


# ── تقويم الأسعار ──────────────────────────────────────────────

@router.get("/calendar/{client_id}")
async def pricing_calendar(
    client_id: str,
    request: Request,
    room_id: int = 0,
    days: int = 30,
    session=Depends(_require_client),
):
    cid = session["client_id"]
    pricing = request.app.state.pricing
    if not pricing:
        return {"success": True, "data": []}
    if not room_id:
        return JSONResponse({"success": False, "error": "room_id مطلوب"}, status_code=400)
    try:
        data = pricing.get_pricing_calendar(cid, room_id, days)
        return {"success": True, "data": data}
    except Exception as e:
        log.error(f"pricing_calendar: {e}", exc_info=True)
        return JSONResponse({"success": False, "error": str(e)}, status_code=500)


# ── تجاوز يدوي ────────────────────────────────────────────────

@router.post("/manual-override")
async def manual_override(request: Request, session=Depends(_require_client)):
    """
    تعيين سعر ثابت يدوياً لغرفة في نطاق تاريخ محدد.
    body: { room_id, price, date_from, date_to, reason? }
    """
    data = await request.json()
    pricing = request.app.state.pricing
    if not pricing:
        return JSONResponse({"success": False, "error": "خدمة التسعير غير متاحة"}, status_code=503)
    cid = session["client_id"]
    room_id = data.get("room_id")
    price = data.get("price")
    date_from = data.get("date_from")
    date_to = data.get("date_to")
    if not all([room_id, price, date_from, date_to]):
        return JSONResponse(
            {"success": False, "error": "room_id, price, date_from, date_to مطلوبة"},
            status_code=400,
        )
    try:
        result = pricing.apply_manual_override(
            cid, int(room_id), float(price), date_from, date_to,
            data.get("reason", ""),
        )
        return result
    except Exception as e:
        log.error(f"manual_override: {e}", exc_info=True)
        return JSONResponse({"success": False, "error": str(e)}, status_code=500)


# ── سجل التغييرات ──────────────────────────────────────────────

@router.get("/history/{client_id}")
async def pricing_history(
    client_id: str,
    request: Request,
    room_id: Optional[int] = None,
    session=Depends(_require_client),
):
    """سجل جميع تغييرات التسعير للعميل."""
    cid = session["client_id"]
    pricing = request.app.state.pricing
    if not pricing:
        return {"success": True, "data": []}
    try:
        data = pricing.get_pricing_history(cid, room_id)
        return {"success": True, "data": data}
    except Exception as e:
        log.error(f"pricing_history: {e}", exc_info=True)
        return JSONResponse({"success": False, "error": str(e)}, status_code=500)


# ── تطبيق التسعير على الحجوزات ────────────────────────────────

@router.post("/apply-now/{client_id}")
async def apply_pricing_now(
    client_id: str,
    request: Request,
    session=Depends(_require_client),
):
    pricing = request.app.state.pricing
    if not pricing:
        return JSONResponse({"success": False, "error": "خدمة التسعير غير متاحة"}, status_code=503)
    cid = session["client_id"]
    try:
        result = pricing.apply_pricing_for_client(cid)
        return {"success": True, "data": result}
    except Exception as e:
        log.error(f"apply_pricing_now: {e}", exc_info=True)
        return JSONResponse({"success": False, "error": str(e)}, status_code=500)


# ── تأثير التسعير الديناميكي ───────────────────────────────────

@router.get("/impact/{client_id}")
async def pricing_impact(
    client_id: str,
    request: Request,
    session=Depends(_require_client),
):
    """مقارنة إيرادات التسعير الديناميكي مقابل الأسعار الأساسية (آخر 30 يوم)."""
    cid = session["client_id"]
    pricing = request.app.state.pricing
    if not pricing:
        return {"success": True, "data": {}}
    try:
        data = pricing.get_pricing_impact(cid)
        return {"success": True, "data": data}
    except Exception as e:
        log.error(f"pricing_impact: {e}", exc_info=True)
        return JSONResponse({"success": False, "error": str(e)}, status_code=500)


# ── مواسم المملكة ──────────────────────────────────────────────

@router.get("/seasons")
async def get_seasons(session=Depends(_require_client)):
    """قائمة مواسم المملكة مع معاملات التسعير."""
    try:
        from services.dynamic_pricing import SAUDI_SEASONS_2026
        seasons = [
            {
                "key": k,
                "label": v["label"],
                "start": v["start"].isoformat(),
                "end": v["end"].isoformat(),
                "factor": v["factor"],
            }
            for k, v in SAUDI_SEASONS_2026.items()
        ]
        return {"success": True, "data": sorted(seasons, key=lambda s: s["start"])}
    except Exception as e:
        log.error(f"get_seasons: {e}", exc_info=True)
        return JSONResponse({"success": False, "error": str(e)}, status_code=500)
