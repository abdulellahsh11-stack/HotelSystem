#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
الـ Open API الموحّد — ربط مرن لكل برنامج وتطبيق
================================================
كل نقطة محمية بمفتاح API (X-API-Key) مرتبط برقم المشترك (client_id).
يغطّي: الغرف، الحجوزات، الضيوف، الفواتير (ZATCA)، نقاط البيع، المخزون،
المحاسبة، القنوات، مؤشرات الأداء — بالإضافة لإدارة المفاتيح.
"""
from fastapi import APIRouter, Request, Depends, HTTPException

router = APIRouter(prefix="/api/open/v1", tags=["Open API"])


# ── المصادقة بمفتاح API ───────────────────────────────────────
async def require_api_key(request: Request) -> dict:
    api_key = request.headers.get("X-API-Key") or request.query_params.get("api_key")
    if not api_key:
        raise HTTPException(status_code=401, detail="X-API-Key مطلوب")
    mgr = getattr(request.app.state, "api_keys", None)
    if mgr is None:
        raise HTTPException(status_code=503, detail="Open API غير مُفعَّل")
    key_data = mgr.validate_key(api_key)
    if not key_data:
        raise HTTPException(status_code=401, detail="مفتاح API غير صالح أو موقوف")
    return key_data


def _scope(key_data: dict, request: Request, scope: str):
    mgr = getattr(request.app.state, "api_keys", None)
    if mgr and not mgr.has_scope(key_data, scope):
        raise HTTPException(status_code=403, detail=f"النطاق مطلوب: {scope}")


def _db(request: Request):
    return request.app.state.db


def _rows(request, sql, params):
    db = _db(request)
    if not db.use_postgres:
        return []
    return [dict(r) for r in (db.execute(sql, params, fetch="all") or [])]


# ════════════════════════════════════════════════════════════
#  معلومات الحساب
# ════════════════════════════════════════════════════════════
@router.get("/me")
async def whoami(request: Request, key=Depends(require_api_key)):
    """يُعيد رقم المشترك والنطاقات المتاحة لهذا المفتاح."""
    return {"success": True, "data": {
        "client_id": key.get("client_id"),
        "scopes": key.get("scopes", []),
    }}


# ════════════════════════════════════════════════════════════
#  الغرف / الإتاحة
# ════════════════════════════════════════════════════════════
@router.get("/rooms")
async def rooms(request: Request, key=Depends(require_api_key)):
    _scope(key, request, "rooms:read")
    return {"success": True, "data": _rows(
        request, "SELECT * FROM rooms WHERE client_id=%s", (key["client_id"],))}


@router.get("/availability")
async def availability(request: Request, check_in: str = "", check_out: str = "",
                       key=Depends(require_api_key)):
    _scope(key, request, "rooms:read")
    cid = key["client_id"]
    if check_in and check_out:
        data = _rows(request,
            """SELECT r.* FROM rooms r WHERE r.client_id=%s AND r.id NOT IN (
                 SELECT room_id FROM bookings WHERE client_id=%s
                 AND status NOT IN ('cancelled','checked_out')
                 AND check_in < %s AND check_out > %s)""",
            (cid, cid, check_out, check_in))
    else:
        data = _rows(request,
            "SELECT * FROM rooms WHERE client_id=%s AND status='available'", (cid,))
    return {"success": True, "data": data}


# ════════════════════════════════════════════════════════════
#  الحجوزات
# ════════════════════════════════════════════════════════════
@router.get("/bookings")
async def bookings(request: Request, status: str = "", key=Depends(require_api_key)):
    _scope(key, request, "bookings:read")
    cid = key["client_id"]
    if status:
        data = _rows(request,
            "SELECT * FROM bookings WHERE client_id=%s AND status=%s ORDER BY check_in DESC",
            (cid, status))
    else:
        data = _rows(request,
            "SELECT * FROM bookings WHERE client_id=%s ORDER BY check_in DESC LIMIT 200", (cid,))
    return {"success": True, "data": data}


# ════════════════════════════════════════════════════════════
#  الضيوف
# ════════════════════════════════════════════════════════════
@router.get("/guests")
async def guests(request: Request, key=Depends(require_api_key)):
    _scope(key, request, "guests:read")
    return {"success": True, "data": _rows(
        request, "SELECT * FROM guests WHERE client_id=%s ORDER BY id DESC LIMIT 200",
        (key["client_id"],))}


# ════════════════════════════════════════════════════════════
#  نقاط البيع (POS)
# ════════════════════════════════════════════════════════════
@router.get("/pos")
async def pos(request: Request, key=Depends(require_api_key)):
    _scope(key, request, "pos:read")
    return {"success": True, "data": _rows(
        request, "SELECT * FROM pos_transactions WHERE client_id=%s ORDER BY created_at DESC LIMIT 200",
        (key["client_id"],))}


# ════════════════════════════════════════════════════════════
#  المخزون
# ════════════════════════════════════════════════════════════
@router.get("/inventory")
async def inventory(request: Request, key=Depends(require_api_key)):
    _scope(key, request, "inventory:read")
    return {"success": True, "data": _rows(
        request, "SELECT * FROM inventory_items WHERE client_id=%s ORDER BY id DESC LIMIT 300",
        (key["client_id"],))}


# ════════════════════════════════════════════════════════════
#  المحاسبة — ملخص + فواتير ZATCA
# ════════════════════════════════════════════════════════════
@router.get("/accounting/summary")
async def accounting_summary(request: Request, key=Depends(require_api_key)):
    _scope(key, request, "accounting:read")
    cid = key["client_id"]
    db = _db(request)
    if not db.use_postgres:
        return {"success": True, "data": {}}
    row = db.execute(
        """SELECT COALESCE(SUM(total_amount),0) AS revenue,
                  COALESCE(SUM(vat_amount),0)  AS vat_collected,
                  COUNT(*) AS invoice_count
           FROM invoices WHERE client_id=%s""", (cid,), fetch="one")
    return {"success": True, "data": dict(row) if row else {}}


@router.get("/invoices")
async def list_invoices(request: Request, key=Depends(require_api_key)):
    _scope(key, request, "invoices:read")
    svc = getattr(request.app.state, "zatca", None)
    if svc is None:
        raise HTTPException(status_code=503, detail="خدمة الفوترة غير متاحة")
    return {"success": True, "data": svc.list_invoices(key["client_id"])}


@router.get("/invoices/{invoice_id}")
async def get_invoice(invoice_id: str, request: Request, key=Depends(require_api_key)):
    _scope(key, request, "invoices:read")
    svc = getattr(request.app.state, "zatca", None)
    if svc is None:
        raise HTTPException(status_code=503, detail="خدمة الفوترة غير متاحة")
    inv = svc.get_invoice(key["client_id"], invoice_id)
    if not inv:
        raise HTTPException(status_code=404, detail="الفاتورة غير موجودة")
    return {"success": True, "data": inv}


@router.post("/invoices")
async def create_invoice(request: Request, key=Depends(require_api_key)):
    """
    ينشئ فاتورة ضريبية متوافقة مع ZATCA.
    الجسم:
    {
      "company_name": "فندق ضيوف",
      "seller_vat": "300000000000003",
      "guest_name": "أحمد محمد",
      "buyer_vat": "",               // اختياري
      "line_items": [
        {"description":"إقامة ليلة", "qty":2, "unit_price":400}
      ]
    }
    """
    _scope(key, request, "invoices:write")
    svc = getattr(request.app.state, "zatca", None)
    if svc is None:
        raise HTTPException(status_code=503, detail="خدمة الفوترة غير متاحة")
    body = await request.json()
    try:
        inv = svc.build_invoice(
            company_name=body.get("company_name", ""),
            seller_vat=body.get("seller_vat", ""),
            guest_name=body.get("guest_name", ""),
            line_items=body.get("line_items", []),
            buyer_vat=body.get("buyer_vat", ""),
            invoice_type=body.get("invoice_type", "simplified"),
        )
        saved = svc.save_invoice(key["client_id"], inv, body.get("booking_id"))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return {"success": True, "data": saved}


# ════════════════════════════════════════════════════════════
#  القنوات (OTA) — للقراءة
# ════════════════════════════════════════════════════════════
@router.get("/channels/reservations")
async def channel_reservations(request: Request, key=Depends(require_api_key)):
    _scope(key, request, "channels:read")
    mgr = getattr(request.app.state, "channels", None)
    if mgr is None:
        raise HTTPException(status_code=503, detail="خدمة القنوات غير متاحة")
    return {"success": True, "data": mgr.list_reservations(key["client_id"])}


# ════════════════════════════════════════════════════════════
#  مؤشرات الأداء
# ════════════════════════════════════════════════════════════
@router.get("/kpi/occupancy")
async def kpi_occupancy(request: Request, key=Depends(require_api_key)):
    _scope(key, request, "kpi:read")
    from datetime import date
    cid = key["client_id"]
    db = _db(request)
    if not db.use_postgres:
        return {"success": True, "data": {}}
    today = date.today().isoformat()
    total = db.execute("SELECT COUNT(*) AS c FROM rooms WHERE client_id=%s", (cid,), fetch="one")
    occ = db.execute(
        """SELECT COUNT(*) AS c FROM bookings WHERE client_id=%s
           AND status IN ('confirmed','checked_in')
           AND check_in <= %s AND check_out > %s""", (cid, today, today), fetch="one")
    tot = dict(total).get("c", 0) if total else 0
    occn = dict(occ).get("c", 0) if occ else 0
    pct = round(occn / tot * 100, 1) if tot else 0
    return {"success": True, "data": {"total_rooms": tot, "occupied": occn, "occupancy_pct": pct}}


# ════════════════════════════════════════════════════════════
#  إدارة مفاتيح API (تتطلب جلسة مشترك — لا مفتاح)
# ════════════════════════════════════════════════════════════
def _require_client(request: Request) -> dict:
    from main import require_client
    return require_client(request)


@router.get("/keys")
async def list_keys(request: Request, session=Depends(_require_client)):
    mgr = getattr(request.app.state, "api_keys", None)
    if mgr is None:
        raise HTTPException(status_code=503, detail="إدارة المفاتيح غير متاحة")
    return {"success": True, "data": mgr.list_keys(session["client_id"]),
            "available_scopes": mgr.available_scopes()}


@router.post("/keys")
async def create_key(request: Request, session=Depends(_require_client)):
    mgr = getattr(request.app.state, "api_keys", None)
    if mgr is None:
        raise HTTPException(status_code=503, detail="إدارة المفاتيح غير متاحة")
    body = await request.json()
    result = mgr.issue_key(
        session["client_id"], body.get("name", ""), body.get("scopes"))
    return {"success": True, "data": result}


@router.delete("/keys/{key_id}")
async def revoke_key(key_id: int, request: Request, session=Depends(_require_client)):
    mgr = getattr(request.app.state, "api_keys", None)
    if mgr is None:
        raise HTTPException(status_code=503, detail="إدارة المفاتيح غير متاحة")
    ok = mgr.revoke_key(session["client_id"], key_id)
    return {"success": ok}
