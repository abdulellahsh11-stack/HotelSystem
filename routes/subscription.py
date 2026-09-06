#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
routes/subscription.py — حالة الاشتراك ورسالة الدفع (البند ٣).

- GET  /api/subscription/status         — حالةٌ للمنشأة: كم بقي، تنبيهٌ قبل
  القفل بـ٢٤ ساعة، هل قُفل، وتعليمات الدفع.
- POST /api/subscription/payment-message — يكتب مالك/مدير المنشأة رسالة
  التحويل البنكي أو رابط ميسر، فتظهر عند التجديد.

هوية المنشأة من الجلسة دائماً، والكتابة تحفظ بقيّة الإعدادات كما هي
(لا تلمس settings._account).
"""
from fastapi import APIRouter, Depends, Request

from app_core import require_client
from db.access import require_manager
from services import subscription

router = APIRouter()


@router.get("/api/subscription/status")
async def subscription_status(request: Request, session=Depends(require_client)):
    store = request.app.state.store
    client = store.get_client(session["client_id"]) or {}
    data = subscription.evaluate(client)
    data["plan"] = client.get("plan", "trial")
    data["payment"] = subscription.payment_instructions(client)
    return {"success": True, "data": data}


@router.post("/api/subscription/payment-message")
async def set_payment_message(request: Request, session=Depends(require_manager)):
    """يخصّص رسالة/تعليمات الدفع (تحويل بنكي أو رابط ميسر) — للمالك أو المدير."""
    data = await request.json()
    store = request.app.state.store
    cid = session["client_id"]
    client = store.get_client(cid) or {"id": cid}
    settings = dict(client.get("settings") or {})
    settings["subscription_payment"] = subscription.sanitize_payment(data)
    client["settings"] = settings
    store.save_client(client)
    return {"success": True, "data": subscription.payment_instructions(client)}
