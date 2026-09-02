#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
routes/listings.py — مسار المنشأة في تطبيق الحجوزات

تُخصّص المنشأة ما تعرضه: اسمها وشعارها وموقعها، ثم وحداتها — غرفاً
وشققاً وشاليهات ومنتجعات ومزارع وأجنحة — بصورها وأسعارها ومرافقها.

    GET/PUT  /api/listing/profile     هوية المنشأة المعروضة
    GET/POST /api/listing/units       الوحدات المعروضة
    PUT/DEL  /api/listing/units/{id}
    POST/DEL /api/listing/units/{id}/photos
    POST     /api/listing/units/{id}/rooms   ربط الوحدة بمخزون الغرف

كل مسارٍ هنا `require_manager`: العرض واجهة المنشأة للعالم، وتغييرُه
ليس عملاً يومياً لموظف استقبال.

**التوفّر لا يُكتب هنا.** يُحسب من `rooms` عبر `listing_units`: إعلانٌ
يقول «متاح» وغرفةٌ مشغولة يعني زائراً يصل ولا يجد مكاناً.
"""
from __future__ import annotations

import json
import logging

from fastapi import APIRouter, HTTPException, Request

from db.access import require_manager
from db.schema_listings import AMENITIES, UNIT_KINDS

router = APIRouter(prefix="/api/listing", tags=["Listings"])
log = logging.getLogger("dheuof.listings")

MAX_PHOTOS = 30
MAX_UNITS = 200


def _db(request: Request):
    db = request.app.state.db
    if not getattr(db, "use_postgres", False):
        raise HTTPException(status_code=503, detail="قاعدة البيانات غير متاحة")
    return db


def _clean_amenities(raw) -> list[str]:
    """
    يُصفّي المرافق مقابل القائمة المضبوطة.

    مرفقٌ غير معروف خطأٌ مطبعي يمنع الظهور في البحث بصمت — الزائر
    يبحث عن `pool` والمخزَّن `pooll`.
    """
    if not isinstance(raw, list):
        return []
    return [a for a in raw if isinstance(a, str) and a in AMENITIES]


def _num(value, default=None):
    try:
        return float(value) if value not in (None, "") else default
    except (TypeError, ValueError):
        return default


def _int(value, default=None):
    try:
        return int(value) if value not in (None, "") else default
    except (TypeError, ValueError):
        return default


# ── المفردات المضبوطة ───────────────────────────────────────────
@router.get("/vocabulary")
async def vocabulary(request: Request):
    """
    الأنواع والمرافق المتاحة — تبنيها الواجهة ولا تكتبها.

    كتابتها في الواجهة يعني قائمتين تتباعدان: تُضاف «مزرعة» هنا ولا
    تظهر هناك، أو تُرسل قيمةٌ يرفضها الخادم بلا سبب مفهوم.
    """
    require_manager(request)
    return {"success": True, "data": {
        "kinds": [{"value": k, "label": v} for k, v in UNIT_KINDS.items()],
        "amenities": [{"value": k, "label": v} for k, v in AMENITIES.items()],
    }}


# ── هوية المنشأة المعروضة ───────────────────────────────────────
@router.get("/profile")
async def get_profile(request: Request):
    session = require_manager(request)
    db = _db(request)
    cid = session["client_id"]
    row = db.execute(
        "SELECT * FROM property_profile WHERE client_id=%s", (cid,), fetch="one"
    )
    if row:
        return {"success": True, "data": dict(row)}
    # لا صفّ بعد: تُبنى بذرةٌ من بيانات الاشتراك بدل نموذجٍ فارغ
    client = db.execute(
        "SELECT name, city, region, phone FROM clients WHERE id=%s", (cid,), fetch="one"
    )
    client = dict(client or {})
    return {"success": True, "data": {
        "client_id": cid,
        "display_name": client.get("name") or "",
        "city": client.get("city") or "",
        "district": client.get("region") or "",
        "phone": client.get("phone") or "",
        "country": "السعودية",
        "is_published": False,
    }}


@router.put("/profile")
async def save_profile(request: Request):
    """يحفظ هوية المنشأة المعروضة — إدراجٌ أو تحديث."""
    session = require_manager(request)
    data = await request.json()
    db = _db(request)
    cid = session["client_id"]

    display_name = str(data.get("display_name") or "").strip()
    if not display_name:
        raise HTTPException(status_code=400, detail="اسم المنشأة المعروض مطلوب")

    fields = {
        "display_name": display_name[:200],
        "tagline": (str(data.get("tagline") or "").strip() or None),
        "description": (str(data.get("description") or "").strip() or None),
        "logo_url": (str(data.get("logo_url") or "").strip() or None),
        "cover_url": (str(data.get("cover_url") or "").strip() or None),
        "country": str(data.get("country") or "السعودية").strip()[:80],
        "city": (str(data.get("city") or "").strip()[:120] or None),
        "district": (str(data.get("district") or "").strip()[:120] or None),
        "address": (str(data.get("address") or "").strip() or None),
        "landmark": (str(data.get("landmark") or "").strip()[:200] or None),
        "landmark_km": _num(data.get("landmark_km")),
        "latitude": _num(data.get("latitude")),
        "longitude": _num(data.get("longitude")),
        "checkin_time": str(data.get("checkin_time") or "15:00")[:10],
        "checkout_time": str(data.get("checkout_time") or "12:00")[:10],
        "phone": (str(data.get("phone") or "").strip()[:30] or None),
        "is_published": bool(data.get("is_published")),
    }
    cols = ", ".join(fields)
    placeholders = ", ".join(["%s"] * len(fields))
    updates = ", ".join(f"{c}=EXCLUDED.{c}" for c in fields)
    db.execute(
        f"""INSERT INTO property_profile (client_id, {cols})
            VALUES (%s, {placeholders})
            ON CONFLICT (client_id) DO UPDATE SET {updates}, updated_at=NOW()""",
        (cid, *fields.values()),
    )
    return {"success": True}


# ── الوحدات المعروضة ────────────────────────────────────────────
@router.get("/units")
async def list_units(request: Request):
    """الوحدات مع صورها وعدد غرف المخزون المربوطة بكلٍّ منها."""
    session = require_manager(request)
    db = _db(request)
    cid = session["client_id"]
    rows = db.execute(
        """SELECT l.*,
                  (SELECT COUNT(*) FROM listing_units u
                    WHERE u.listing_id = l.id AND u.client_id = l.client_id) AS rooms_linked,
                  COALESCE((
                    SELECT json_agg(json_build_object(
                             'id', p.id, 'url', p.url, 'caption', p.caption)
                           ORDER BY p.sort_order, p.id)
                      FROM listing_photos p
                     WHERE p.listing_id = l.id AND p.client_id = l.client_id
                  ), '[]'::json) AS photos
           FROM listings l
          WHERE l.client_id = %s
          ORDER BY l.sort_order, l.id""",
        (cid,), fetch="all",
    )
    return {"success": True, "data": [dict(r) for r in (rows or [])]}


def _unit_fields(data: dict) -> dict:
    kind = str(data.get("kind") or "").strip()
    if kind not in UNIT_KINDS:
        raise HTTPException(
            status_code=400,
            detail="نوع الوحدة غير معروف — اختر من القائمة",
        )
    title = str(data.get("title") or "").strip()
    if not title:
        raise HTTPException(status_code=400, detail="عنوان الوحدة مطلوب")

    capacity = _int(data.get("capacity"), 2) or 2
    if not 1 <= capacity <= 100:
        raise HTTPException(status_code=400, detail="السعة بين ١ و١٠٠")
    price = _num(data.get("base_price"), 0) or 0
    if price < 0:
        raise HTTPException(status_code=400, detail="السعر لا يكون سالباً")
    min_nights = _int(data.get("min_nights"), 1) or 1
    if not 1 <= min_nights <= 365:
        raise HTTPException(status_code=400, detail="أقل مدة بين ليلة و٣٦٥")

    return {
        "kind": kind,
        "title": title[:200],
        "description": (str(data.get("description") or "").strip() or None),
        "base_price": price,
        "weekend_price": _num(data.get("weekend_price")),
        "capacity": capacity,
        "bedrooms": _int(data.get("bedrooms"), 1),
        "bathrooms": _int(data.get("bathrooms"), 1),
        "area_sqm": _int(data.get("area_sqm")),
        "amenities": json.dumps(_clean_amenities(data.get("amenities")),
                                ensure_ascii=False),
        "min_nights": min_nights,
        "is_published": bool(data.get("is_published")),
        "sort_order": _int(data.get("sort_order"), 0) or 0,
    }


@router.post("/units")
async def create_unit(request: Request):
    from db.connection import count_of

    session = require_manager(request)
    data = await request.json()
    db = _db(request)
    cid = session["client_id"]

    existing = count_of(db.execute(
        "SELECT COUNT(*) FROM listings WHERE client_id=%s", (cid,), fetch="one"
    ))
    if existing >= MAX_UNITS:
        raise HTTPException(status_code=400, detail=f"الحدّ {MAX_UNITS} وحدة معروضة")

    fields = _unit_fields(data)
    cols = ", ".join(fields)
    placeholders = ", ".join(["%s"] * len(fields))
    row = db.execute(
        f"INSERT INTO listings (client_id, {cols}) VALUES (%s, {placeholders}) RETURNING id",
        (cid, *fields.values()), fetch="one",
    )
    return {"success": True, "data": {"id": dict(row)["id"]}}


@router.put("/units/{unit_id}")
async def update_unit(unit_id: int, request: Request):
    session = require_manager(request)
    data = await request.json()
    db = _db(request)
    cid = session["client_id"]

    fields = _unit_fields(data)
    sets = ", ".join(f"{c}=%s" for c in fields)
    row = db.execute(
        f"UPDATE listings SET {sets}, updated_at=NOW() WHERE id=%s AND client_id=%s RETURNING id",
        (*fields.values(), unit_id, cid), fetch="one",
    )
    if not row:
        raise HTTPException(status_code=404, detail="الوحدة غير موجودة")
    return {"success": True}


@router.delete("/units/{unit_id}")
async def delete_unit(unit_id: int, request: Request):
    session = require_manager(request)
    db = _db(request)
    row = db.execute(
        "DELETE FROM listings WHERE id=%s AND client_id=%s RETURNING id",
        (unit_id, session["client_id"]), fetch="one",
    )
    if not row:
        raise HTTPException(status_code=404, detail="الوحدة غير موجودة")
    return {"success": True}


# ── الصور ───────────────────────────────────────────────────────
@router.post("/units/{unit_id}/photos")
async def add_photo(unit_id: int, request: Request):
    """
    يضيف صورةً بعنوانها.

    العناوين تُخزَّن ولا تُرفع الملفات: رفعُها يحتاج تخزيناً كائنياً
    غير مُهيَّأ بعد، وبناء رفعٍ يكتب على قرص الخادم يضيع مع كل نشر.
    """
    from db.connection import count_of

    session = require_manager(request)
    data = await request.json()
    db = _db(request)
    cid = session["client_id"]

    if not db.execute(
        "SELECT id FROM listings WHERE id=%s AND client_id=%s", (unit_id, cid), fetch="one"
    ):
        raise HTTPException(status_code=404, detail="الوحدة غير موجودة")

    url = str(data.get("url") or "").strip()
    if not url.startswith(("https://", "http://", "/static/")):
        raise HTTPException(status_code=400, detail="عنوان صورة غير صالح")

    count = count_of(db.execute(
        "SELECT COUNT(*) FROM listing_photos WHERE client_id=%s AND listing_id=%s",
        (cid, unit_id), fetch="one",
    ))
    if count >= MAX_PHOTOS:
        raise HTTPException(status_code=400, detail=f"الحدّ {MAX_PHOTOS} صورة للوحدة")

    row = db.execute(
        """INSERT INTO listing_photos (listing_id, client_id, url, caption, sort_order)
           VALUES (%s,%s,%s,%s,%s) RETURNING id""",
        (unit_id, cid, url[:2000],
         str(data.get("caption") or "").strip()[:200] or None,
         _int(data.get("sort_order"), count) or count), fetch="one",
    )
    return {"success": True, "data": {"id": dict(row)["id"]}}


@router.delete("/units/{unit_id}/photos/{photo_id}")
async def delete_photo(unit_id: int, photo_id: int, request: Request):
    session = require_manager(request)
    db = _db(request)
    row = db.execute(
        """DELETE FROM listing_photos
            WHERE id=%s AND listing_id=%s AND client_id=%s RETURNING id""",
        (photo_id, unit_id, session["client_id"]), fetch="one",
    )
    if not row:
        raise HTTPException(status_code=404, detail="الصورة غير موجودة")
    return {"success": True}


# ── ربط الوحدة بمخزون الغرف ─────────────────────────────────────
@router.post("/units/{unit_id}/rooms")
async def link_rooms(unit_id: int, request: Request):
    """
    يربط الوحدة المعروضة بغرفٍ من المخزون.

    هذا الربط هو ما يجعل التوفّر حقيقياً: يُحسب من حالات الغرف
    المربوطة لا من رقمٍ يكتبه المالك ثم ينساه.
    """
    session = require_manager(request)
    data = await request.json()
    db = _db(request)
    cid = session["client_id"]

    if not db.execute(
        "SELECT id FROM listings WHERE id=%s AND client_id=%s", (unit_id, cid), fetch="one"
    ):
        raise HTTPException(status_code=404, detail="الوحدة غير موجودة")

    ids = [i for i in (_int(x) for x in (data.get("room_ids") or [])) if i]
    if not ids:
        raise HTTPException(status_code=400, detail="اختر غرفةً واحدة على الأقل")

    # الغرف تُتحقّق مقابل المنشأة: بدونه يربط المالك غرفة منشأةٍ أخرى
    # برقمٍ مُخمَّن، فيقرأ توفّرها.
    owned = db.execute(
        "SELECT id FROM rooms WHERE client_id=%s AND id = ANY(%s)", (cid, ids), fetch="all"
    )
    owned_ids = [dict(r)["id"] for r in (owned or [])]
    if not owned_ids:
        raise HTTPException(status_code=404, detail="لا غرف مطابقة في منشأتك")

    db.execute(
        "DELETE FROM listing_units WHERE listing_id=%s AND client_id=%s", (unit_id, cid)
    )
    for room_id in owned_ids:
        db.execute(
            """INSERT INTO listing_units (listing_id, room_id, client_id)
               VALUES (%s,%s,%s) ON CONFLICT DO NOTHING""",
            (unit_id, room_id, cid),
        )
    log.info("رُبطت %s غرفة بالوحدة %s للمنشأة %s", len(owned_ids), unit_id, cid)
    return {"success": True, "data": {"linked": len(owned_ids)}}
