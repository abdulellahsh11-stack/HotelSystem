#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
مسارات مدير القنوات (OTA Channel Manager)
=========================================
ربط، مزامنة، واستقبال حجوزات منصات التوزيع العالمية.
"""
from fastapi import APIRouter, Request, Depends, HTTPException

router = APIRouter(prefix="/api/channels", tags=["Channels"])


def _require_client(request: Request) -> dict:
    from main import require_client
    return require_client(request)


def _mgr(request: Request):
    mgr = getattr(request.app.state, "channels", None)
    if mgr is None:
        raise HTTPException(status_code=503, detail="خدمة القنوات غير متاحة")
    return mgr


@router.get("/supported")
async def supported(request: Request, session=Depends(_require_client)):
    """قائمة القنوات المدعومة عبر الوسيط."""
    return {"success": True, "data": _mgr(request).supported_channels()}


@router.get("/connections")
async def connections(request: Request, session=Depends(_require_client)):
    """حالة ربط كل قناة لهذا المشترك."""
    return {"success": True, "data": _mgr(request).list_connections(session["client_id"])}


@router.post("/connect")
async def connect(request: Request, session=Depends(_require_client)):
    """ربط قناة بمفتاح API (يُخزَّن مقنّعاً فقط)."""
    body = await request.json()
    code = (body.get("channel_code") or "").strip()
    api_key = body.get("api_key") or ""
    try:
        result = _mgr(request).connect(session["client_id"], code, api_key)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return {"success": True, "data": result}


@router.post("/disconnect")
async def disconnect(request: Request, session=Depends(_require_client)):
    body = await request.json()
    code = (body.get("channel_code") or "").strip()
    ok = _mgr(request).disconnect(session["client_id"], code)
    return {"success": ok}


@router.post("/sync")
async def sync(request: Request, session=Depends(_require_client)):
    """دفع التوافر والأسعار إلى قناة محددة أو لكل القنوات المتصلة."""
    body = {}
    try:
        body = await request.json()
    except Exception:
        pass
    code = (body.get("channel_code") or "").strip() or None
    return {"success": True, "data": _mgr(request).sync_rates(session["client_id"], code)}


@router.get("/reservations")
async def reservations(request: Request, status: str = None, session=Depends(_require_client)):
    """الحجوزات الواردة من القنوات."""
    data = _mgr(request).list_reservations(session["client_id"], status)
    return {"success": True, "data": data}


@router.get("/log")
async def sync_log(request: Request, session=Depends(_require_client)):
    """سجل عمليات المزامنة للتدقيق."""
    return {"success": True, "data": _mgr(request).sync_log(session["client_id"])}


@router.post("/webhook/{channel_code}")
async def webhook(channel_code: str, request: Request):
    """
    نقطة استقبال حجوزات القناة (webhook).
    يُؤمَّن عبر رأس X-Channel-Token = client_id (مبسّط — استبدله بتوقيع HMAC في الإنتاج).
    """
    client_id = request.headers.get("X-Channel-Token", "").strip()
    if not client_id:
        raise HTTPException(status_code=401, detail="رمز القناة مفقود")
    try:
        payload = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="حمولة غير صالحة")
    try:
        result = _mgr(request).ingest_reservation(client_id, channel_code, payload)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return {"success": True, "data": result}
