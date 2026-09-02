#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
routes/search.py — مسار الزائر في تطبيق الحجوزات: يبحث ويتصفّح

بحثٌ عامّ بلا جلسة: الزائر يتصفّح قبل أن يُنشئ حساباً — وإلزامُه
بالتسجيل ليرى الأسعار يُفقده قبل أن يبدأ. الحساب يُطلب عند **الحجز**
وحده.

    GET /api/search/filters      الدول والمدن والأحياء والأنواع المتاحة
    GET /api/search             بحثٌ بالموقع والتاريخ والسعة والسعر والمرافق
    GET /api/search/{cid}/{id}  تفاصيل وحدةٍ بصورها

**لا يظهر إلا ما نشرته المنشأة.** `is_published` على المنشأة وعلى
الوحدة معاً: مسوّدةٌ نصف مكتملة لا تُعرض على العالم.

**ولا يُكشف رقم غرفةٍ ولا اسم نزيل.** المعروض: نوعٌ وسعرٌ وصورة وموقع.
"""
from __future__ import annotations

import logging
from datetime import date

from fastapi import APIRouter, HTTPException, Query, Request

from db.schema_listings import AMENITIES, UNIT_KINDS

router = APIRouter(prefix="/api/search", tags=["Search"])
log = logging.getLogger("dheuof.search")

PAGE_SIZE = 24
MAX_PAGE_SIZE = 60


def _db(request: Request):
    db = request.app.state.db
    if not getattr(db, "use_postgres", False):
        raise HTTPException(status_code=503, detail="الخدمة غير متاحة مؤقتاً")
    return db


#: يُعرض على كل بحث — الوحدة منشورة في منشأةٍ منشورة.
_PUBLISHED = """
    FROM listings l
    JOIN property_profile p ON p.client_id = l.client_id
   WHERE l.is_published = TRUE AND p.is_published = TRUE
"""


@router.get("/filters")
async def filters(request: Request):
    """
    خيارات البحث المتاحة فعلاً — لا قائمةٌ ثابتة.

    عرض مدنٍ لا معروض فيها يُنتج بحثاً يعود فارغاً دائماً، فيظنّ
    الزائر أن التطبيق معطَّل.
    """
    db = _db(request)
    rows = db.execute(
        f"""SELECT DISTINCT p.country, p.city, p.district {_PUBLISHED}
            ORDER BY p.country, p.city, p.district""",
        fetch="all",
    )
    kinds = db.execute(
        f"SELECT DISTINCT l.kind {_PUBLISHED}", fetch="all"
    )
    bounds = db.execute(
        f"SELECT MIN(l.base_price) AS lo, MAX(l.base_price) AS hi {_PUBLISHED}",
        fetch="one",
    )
    bounds = dict(bounds or {})

    places: dict[str, dict[str, list]] = {}
    for r in (rows or []):
        r = dict(r)
        country = r.get("country") or "—"
        city = r.get("city") or "—"
        cities = places.setdefault(country, {})
        districts = cities.setdefault(city, [])
        if r.get("district") and r["district"] not in districts:
            districts.append(r["district"])

    return {"success": True, "data": {
        "places": places,
        "kinds": [{"value": k, "label": UNIT_KINDS.get(k, k)}
                  for k in sorted({dict(r)["kind"] for r in (kinds or [])})],
        "amenities": [{"value": k, "label": v} for k, v in AMENITIES.items()],
        "price": {"min": float(bounds.get("lo") or 0),
                  "max": float(bounds.get("hi") or 0)},
    }}


@router.get("")
async def search(
    request: Request,
    country: str = Query("", max_length=80),
    city: str = Query("", max_length=120),
    district: str = Query("", max_length=120),
    landmark: str = Query("", max_length=200),
    kind: str = Query("", max_length=20),
    guests: int = Query(0, ge=0, le=100),
    price_min: float = Query(0, ge=0),
    price_max: float = Query(0, ge=0),
    amenities: str = Query("", max_length=500),
    check_in: str = Query("", max_length=10),
    check_out: str = Query("", max_length=10),
    sort: str = Query("price", max_length=20),
    page: int = Query(1, ge=1, le=200),
    per_page: int = Query(PAGE_SIZE, ge=1, le=MAX_PAGE_SIZE),
):
    """
    بحثٌ مُخصَّص. كل مُرشِّحٍ اختياري، والتواريخ تحسب الليالي فتظهر
    الوحدات التي تقبل هذه المدة (`min_nights`).

    كل قيمةٍ مُمعلَمة — لا تُركَّب في نصّ SQL. تركيبُها هنا خاصةً
    خطرٌ مضاعف: مسارٌ عامّ بلا جلسة، فأي حقنٍ يبلغ كل بيانات المنصة.
    """
    db = _db(request)
    where = [
        "l.is_published = TRUE",
        "p.is_published = TRUE",
    ]
    params: list = []

    def add(clause: str, value):
        where.append(clause)
        params.append(value)

    if country.strip():
        add("p.country = %s", country.strip())
    if city.strip():
        add("p.city = %s", city.strip())
    if district.strip():
        add("p.district = %s", district.strip())
    if landmark.strip():
        # `%` و`_` رمزا بدلٍ في ILIKE: البحث عن «_» وحده يطابق كل شيء،
        # وعن «%» يطابق كل شيء أيضاً. القيمة مُمعلَمة فلا حقن، لكن
        # النتيجة تصير خاطئة — فتُهرَّب الرموز قبل تركيب النمط.
        needle = landmark.strip().replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
        add("p.landmark ILIKE %s ESCAPE '\\'", "%" + needle + "%")
    if kind.strip():
        if kind not in UNIT_KINDS:
            raise HTTPException(status_code=400, detail="نوع غير معروف")
        add("l.kind = %s", kind)
    if guests:
        add("l.capacity >= %s", guests)
    if price_min:
        add("l.base_price >= %s", price_min)
    if price_max:
        add("l.base_price <= %s", price_max)

    wanted = [a for a in amenities.split(",") if a.strip() in AMENITIES]
    if wanted:
        # `@>` مع فهرس GIN: الوحدة تحوي كل المرافق المطلوبة لا بعضها.
        add("l.amenities @> %s::jsonb",
            __import__("json").dumps(wanted, ensure_ascii=False))

    nights = 0
    if check_in and check_out:
        try:
            d_in = date.fromisoformat(check_in[:10])
            d_out = date.fromisoformat(check_out[:10])
            nights = (d_out - d_in).days
        except ValueError:
            raise HTTPException(status_code=400, detail="تواريخ غير صحيحة") from None
        if nights < 1:
            raise HTTPException(status_code=400, detail="المغادرة بعد الوصول")
        add("l.min_nights <= %s", nights)

    order = {
        "price": "l.base_price ASC",
        "price_desc": "l.base_price DESC",
        "capacity": "l.capacity DESC",
        "newest": "l.created_at DESC",
    }.get(sort, "l.base_price ASC")

    offset = (page - 1) * per_page
    rows = db.execute(
        f"""SELECT l.id, l.client_id, l.kind, l.title, l.base_price, l.capacity,
                   l.bedrooms, l.bathrooms, l.area_sqm, l.amenities, l.min_nights,
                   p.display_name, p.country, p.city, p.district,
                   p.landmark, p.landmark_km,
                   (SELECT url FROM listing_photos ph
                     WHERE ph.listing_id = l.id AND ph.client_id = l.client_id
                     ORDER BY ph.sort_order, ph.id LIMIT 1) AS photo
              FROM listings l
              JOIN property_profile p ON p.client_id = l.client_id
             WHERE {' AND '.join(where)}
             ORDER BY {order}
             LIMIT %s OFFSET %s""",
        (*params, per_page, offset), fetch="all",
    )

    from db.connection import count_of
    total = count_of(db.execute(
        f"""SELECT COUNT(*) FROM listings l
            JOIN property_profile p ON p.client_id = l.client_id
            WHERE {' AND '.join(where)}""",
        tuple(params), fetch="one",
    ))

    results = []
    for r in (rows or []):
        r = dict(r)
        price = float(r.get("base_price") or 0)
        results.append({
            **r,
            "base_price": price,
            "kind_label": UNIT_KINDS.get(r.get("kind"), r.get("kind")),
            "total_price": round(price * nights, 2) if nights else None,
            "nights": nights or None,
        })
    return {"success": True, "data": results,
            "page": page, "per_page": per_page, "total": total}


@router.get("/{client_id}/{unit_id}")
async def unit_details(client_id: str, unit_id: int, request: Request):
    """
    تفاصيل وحدةٍ منشورة بصورها كلّها.

    `client_id` من المسار هنا مقصود: صفحة الوحدة عنوانٌ عامّ يُشارَك
    ويُفهرَس. ولا خطر: لا يُعرض إلا المنشور، والمعروض لا يحمل بيانات
    نزيلٍ ولا رقم غرفة.
    """
    db = _db(request)
    row = db.execute(
        """SELECT l.id, l.client_id, l.kind, l.title, l.description,
                  l.base_price, l.weekend_price, l.capacity, l.bedrooms,
                  l.bathrooms, l.area_sqm, l.amenities, l.min_nights,
                  p.display_name, p.tagline, p.description AS property_description,
                  p.logo_url, p.cover_url, p.country, p.city, p.district,
                  p.address, p.landmark, p.landmark_km,
                  p.latitude, p.longitude, p.checkin_time, p.checkout_time
             FROM listings l
             JOIN property_profile p ON p.client_id = l.client_id
            WHERE l.id = %s AND l.client_id = %s
              AND l.is_published = TRUE AND p.is_published = TRUE""",
        (unit_id, client_id), fetch="one",
    )
    if not row:
        raise HTTPException(status_code=404, detail="الوحدة غير متاحة")
    row = dict(row)

    photos = db.execute(
        """SELECT url, caption FROM listing_photos
            WHERE listing_id=%s AND client_id=%s ORDER BY sort_order, id""",
        (unit_id, client_id), fetch="all",
    )
    row["photos"] = [dict(p) for p in (photos or [])]
    row["kind_label"] = UNIT_KINDS.get(row.get("kind"), row.get("kind"))
    row["amenity_labels"] = [
        {"value": a, "label": AMENITIES[a]}
        for a in (row.get("amenities") or []) if a in AMENITIES
    ]
    row["base_price"] = float(row.get("base_price") or 0)
    return {"success": True, "data": row}
