#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
routes/booking_services.py — الإفطار والتوصيل

مسارٌ للحجز ومسارٌ لليوم، من نفس الجدول:

- `/api/bookings/{id}/services` — ما يُسجّله الاستقبال على حجزٍ بعينه
- `/api/services/daily`         — ما على المطبخ والسائق اليوم

هذا هو ربط التطبيقات المقصود: الاستقبال يسجّل مرةً واحدة، فيظهر ما
سجّله في قائمة التشغيل بلا إعادة إدخال ولا نسخة ثانية تتناقض معه.
"""
from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Request

from app_core import log, require_client
from db.schema_services import SERVICE_LABELS, SERVICE_STATUSES, SERVICE_TYPES

router = APIRouter(tags=["Booking Services"])


def _db(request: Request):
    db = request.app.state.db
    if not getattr(db, "use_postgres", False):
        raise HTTPException(status_code=503, detail="قاعدة البيانات غير متاحة")
    return db


def _require(session: dict, permission: str) -> None:
    from db.security import check_permission

    if not check_permission(session, permission):
        raise HTTPException(status_code=403, detail=f"الصلاحية '{permission}' مطلوبة")


def _clean(data: dict) -> dict:
    """يتحقق من مُدخل الخدمة ويُطبّعه، ويرمي ValueError برسالة عربية."""
    service_type = str(data.get("service_type") or "").strip()
    if service_type not in SERVICE_TYPES:
        raise ValueError(f"نوع خدمة غير معروف. المسموح: {'، '.join(SERVICE_TYPES)}")

    service_date = str(data.get("service_date") or "").strip()
    try:
        date.fromisoformat(service_date)
    except (ValueError, TypeError):
        raise ValueError("تاريخ الخدمة مطلوب بصيغة YYYY-MM-DD") from None

    # `or 1` كانت تُعامل الصفر كأنه «غير مُدخَل» فتحوّله إلى ١ بصمت —
    # والصفر مُدخَلٌ خاطئ يُرفض لا يُصحَّح. التمييز بين الغياب والصفر
    # يحتاج فحص None صراحةً.
    raw_quantity = data.get("quantity")
    try:
        quantity = 1 if raw_quantity in (None, "") else int(raw_quantity)
    except (TypeError, ValueError):
        raise ValueError("الكمية يجب أن تكون رقماً") from None
    if not 1 <= quantity <= 200:
        raise ValueError("الكمية يجب أن تكون بين ١ و٢٠٠")

    # هنا الصفر صالحٌ عمداً — خدمة مجانية ضمن الباقة — فلا حاجة
    # للتمييز بينه وبين الغياب.
    raw_price = data.get("unit_price")
    try:
        unit_price = 0.0 if raw_price in (None, "") else float(raw_price)
    except (TypeError, ValueError):
        raise ValueError("السعر يجب أن يكون رقماً") from None
    if unit_price < 0:
        raise ValueError("السعر لا يكون سالباً")

    status = str(data.get("status") or "pending").strip()
    if status not in SERVICE_STATUSES:
        raise ValueError(f"حالة غير معروفة. المسموح: {'، '.join(SERVICE_STATUSES)}")

    return {
        "service_type": service_type,
        "service_date": service_date,
        "quantity": quantity,
        "unit_price": unit_price,
        "status": status,
        "destination": str(data.get("destination") or "").strip()[:200],
        "scheduled_at": str(data.get("scheduled_at") or "").strip() or None,
        "notes": str(data.get("notes") or "").strip()[:1000],
    }


def _row(r: dict) -> dict:
    out = dict(r)
    out["service_label"] = SERVICE_LABELS.get(out.get("service_type"), out.get("service_type"))
    out["total"] = float(out.get("unit_price") or 0) * int(out.get("quantity") or 0)
    for key in ("service_date", "scheduled_at", "created_at"):
        if out.get(key) is not None:
            out[key] = str(out[key])
    if out.get("unit_price") is not None:
        out["unit_price"] = float(out["unit_price"])
    return out


# ──────────────────────────────────────────────────────────────
#  خدمات حجزٍ بعينه
# ──────────────────────────────────────────────────────────────
@router.get("/api/bookings/{booking_id}/services")
async def list_booking_services(
    booking_id: str, request: Request, session=Depends(require_client)
):
    """خدمات الحجز مقسَّمةً بالنوع — الواجهة تعرض كل نوع في قسمٍ يُطوى."""
    _require(session, "bookings.read")
    rows = _db(request).execute(
        """SELECT * FROM booking_services
           WHERE client_id=%s AND booking_id=%s
           ORDER BY service_date, service_type""",
        (session["client_id"], booking_id), fetch="all",
    ) or []

    grouped: dict[str, list] = {t: [] for t in SERVICE_TYPES}
    for row in rows:
        item = _row(dict(row))
        grouped.setdefault(item["service_type"], []).append(item)

    return {
        "success": True,
        "data": {
            "booking_id": booking_id,
            "groups": [
                {
                    "type": t,
                    "label": SERVICE_LABELS[t],
                    "items": grouped.get(t, []),
                    "count": len(grouped.get(t, [])),
                    "total": round(sum(i["total"] for i in grouped.get(t, [])), 2),
                }
                for t in SERVICE_TYPES
            ],
        },
    }


@router.post("/api/bookings/{booking_id}/services")
async def add_booking_service(
    booking_id: str, request: Request, session=Depends(require_client)
):
    """يُسجّل خدمة على الحجز. تكرار نفس النوع في نفس اليوم يُرفض."""
    _require(session, "bookings.write")
    data = await request.json()
    db = _db(request)
    cid = session["client_id"]

    try:
        item = _clean(data)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from None

    # الحجز يخصّ هذه المنشأة — وإلا عُلِّقت الخدمة بحجز منشأة أخرى
    if not db.execute(
        "SELECT id FROM bookings WHERE id=%s AND client_id=%s",
        (booking_id, cid), fetch="one",
    ):
        raise HTTPException(status_code=404, detail="الحجز غير موجود")

    try:
        db.execute(
            """INSERT INTO booking_services
                   (client_id, booking_id, service_type, service_date, quantity,
                    unit_price, status, destination, scheduled_at, notes, created_by)
               VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
            (cid, booking_id, item["service_type"], item["service_date"],
             item["quantity"], item["unit_price"], item["status"],
             item["destination"], item["scheduled_at"], item["notes"],
             session.get("username") or "owner"),
        )
    except Exception as exc:
        text = str(exc).lower()
        if "unique" in text or "duplicate" in text:
            raise HTTPException(
                status_code=409,
                detail=f"{SERVICE_LABELS[item['service_type']]} مُسجَّل مسبقاً لهذا اليوم",
            ) from None
        log.error("فشل تسجيل خدمة للحجز %s: %s", booking_id, exc, exc_info=True)
        raise HTTPException(status_code=500, detail="تعذّر تسجيل الخدمة") from None

    return {"success": True, "data": item}


@router.patch("/api/services/{service_id}")
async def update_service_status(
    service_id: int, request: Request, session=Depends(require_client)
):
    """يُعلّم الخدمة منجزةً أو ملغاة — من قائمة التشغيل اليومية عادةً."""
    _require(session, "bookings.write")
    data = await request.json()
    status = str(data.get("status") or "").strip()
    if status not in SERVICE_STATUSES:
        raise HTTPException(status_code=400, detail="حالة غير معروفة")

    db = _db(request)
    cid = session["client_id"]
    if not db.execute(
        "SELECT id FROM booking_services WHERE id=%s AND client_id=%s",
        (service_id, cid), fetch="one",
    ):
        raise HTTPException(status_code=404, detail="الخدمة غير موجودة")

    db.execute(
        "UPDATE booking_services SET status=%s WHERE id=%s AND client_id=%s",
        (status, service_id, cid),
    )
    return {"success": True}


@router.delete("/api/services/{service_id}")
async def delete_service(
    service_id: int, request: Request, session=Depends(require_client)
):
    _require(session, "bookings.write")
    db = _db(request)
    cid = session["client_id"]
    if not db.execute(
        "SELECT id FROM booking_services WHERE id=%s AND client_id=%s",
        (service_id, cid), fetch="one",
    ):
        raise HTTPException(status_code=404, detail="الخدمة غير موجودة")
    db.execute(
        "DELETE FROM booking_services WHERE id=%s AND client_id=%s", (service_id, cid)
    )
    return {"success": True}


# ──────────────────────────────────────────────────────────────
#  قائمة التشغيل اليومية
# ──────────────────────────────────────────────────────────────
@router.get("/api/services/daily")
async def daily_services(
    request: Request, day: str = "", session=Depends(require_client)
):
    """
    ما على المطبخ والسائق اليوم، مقسَّماً بالنوع.

    يُضمّ رقم الغرفة واسم النزيل من الحجز نفسه: قائمةٌ تقول «إفطار ×٢»
    بلا غرفة لا تُنفَّذ. والضمّ مُقيَّد بـ client_id على الطرفين فلا
    يجرّ الانضمامُ صفَّ منشأة أخرى.
    """
    _require(session, "bookings.read")
    target = (day or "").strip() or date.today().isoformat()
    try:
        date.fromisoformat(target)
    except ValueError:
        raise HTTPException(status_code=400, detail="التاريخ بصيغة YYYY-MM-DD") from None

    rows = _db(request).execute(
        """SELECT s.*, r.room_number, g.full_name AS guest_name
           FROM booking_services s
           LEFT JOIN bookings b
                  ON b.id = s.booking_id AND b.client_id = s.client_id
           LEFT JOIN rooms r
                  ON r.id = b.room_id AND r.client_id = s.client_id
           LEFT JOIN guests g
                  ON g.id = b.guest_id AND g.client_id = s.client_id
           WHERE s.client_id=%s AND s.service_date=%s
           ORDER BY s.service_type, r.room_number""",
        (session["client_id"], target), fetch="all",
    ) or []

    grouped: dict[str, list] = {t: [] for t in SERVICE_TYPES}
    for row in rows:
        item = _row(dict(row))
        grouped.setdefault(item["service_type"], []).append(item)

    return {
        "success": True,
        "data": {
            "day": target,
            "groups": [
                {
                    "type": t,
                    "label": SERVICE_LABELS[t],
                    "items": grouped.get(t, []),
                    "count": len(grouped.get(t, [])),
                    "pending": sum(
                        1 for i in grouped.get(t, []) if i.get("status") == "pending"
                    ),
                    "quantity": sum(int(i.get("quantity") or 0) for i in grouped.get(t, [])),
                }
                for t in SERVICE_TYPES
            ],
        },
    }
