#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""تقييمات الحجوزات — Booking Reviews"""
import logging
from datetime import datetime, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field

router = APIRouter(prefix="/api/reviews", tags=["Reviews"])
log = logging.getLogger("dheuof.reviews")


def _require_client(request: Request) -> dict:
    from main import require_client
    return require_client(request)


def _require_manager(session: dict) -> dict:
    role = (session.get("role") or session.get("user_role") or "employee").lower()
    if role not in ("manager", "admin", "owner"):
        raise HTTPException(403, "هذه العملية متاحة للمدير فقط")
    return session


# ── Schemas ──────────────────────────────────────────────────────────────────

class CreateReviewSchema(BaseModel):
    booking_id: str
    guest_id: Optional[str] = None
    overall_rating:  int = Field(..., ge=1, le=5)
    cleanliness:     int = Field(..., ge=1, le=5)
    service:         int = Field(..., ge=1, le=5)
    location:        int = Field(..., ge=1, le=5)
    value_for_money: int = Field(..., ge=1, le=5)
    comment: Optional[str] = None
    is_public: bool = True


class ReplySchema(BaseModel):
    reply: str


# ── Routes ───────────────────────────────────────────────────────────────────

@router.post("")
async def create_review(
    body: CreateReviewSchema,
    request: Request,
    session=Depends(_require_client),
):
    db   = request.app.state.db
    cid  = session["client_id"]
    user = session.get("user_id") or cid

    if db.use_postgres:
        # تحقق: الحجز في حالة checkout
        try:
            booking = db.execute(
                "SELECT status, check_out FROM bookings WHERE id=%s AND client_id=%s",
                (body.booking_id, cid), fetch="one"
            )
        except Exception:
            booking = None

        if booking:
            status = (booking.get("status") or "").lower()
            if status not in ("checked_out", "checkout", "completed"):
                raise HTTPException(400, "التقييم متاح فقط بعد تسجيل الخروج")

            # تحقق: 30 يوم من تاريخ الخروج
            checkout_dt = booking.get("check_out")
            if checkout_dt:
                deadline = checkout_dt + timedelta(days=30)
                if datetime.now() > deadline:
                    raise HTTPException(400, "انتهت مدة التقييم (30 يوم من تاريخ الخروج)")

        try:
            row = db.execute("""
                INSERT INTO booking_reviews
                    (client_id, booking_id, guest_id, recorded_by,
                     overall_rating, cleanliness, service, location,
                     value_for_money, comment, is_public)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                ON CONFLICT (client_id, booking_id) DO UPDATE SET
                    overall_rating  = EXCLUDED.overall_rating,
                    cleanliness     = EXCLUDED.cleanliness,
                    service         = EXCLUDED.service,
                    location        = EXCLUDED.location,
                    value_for_money = EXCLUDED.value_for_money,
                    comment         = EXCLUDED.comment,
                    is_public       = EXCLUDED.is_public,
                    recorded_by     = EXCLUDED.recorded_by
                RETURNING *
            """, (
                cid, body.booking_id, body.guest_id, user,
                body.overall_rating, body.cleanliness, body.service,
                body.location, body.value_for_money,
                body.comment, body.is_public,
            ), fetch="one")
            return {
                "success": True,
                "data": dict(row) if row else {},
                "message": "تم حفظ التقييم بنجاح",
            }
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(500, f"خطأ في حفظ التقييم: {e}")

    raise HTTPException(400, "يتطلب قاعدة بيانات PostgreSQL")


@router.get("")
async def list_reviews(
    request: Request,
    page: int = 1,
    per_page: int = 50,
    min_rating: Optional[int] = None,
    booking_id: Optional[str] = None,
    session=Depends(_require_client),
):
    db     = request.app.state.db
    cid    = session["client_id"]
    limit  = min(per_page, 200)
    offset = (page - 1) * limit

    if db.use_postgres:
        try:
            conditions = ["client_id=%s"]
            params: list = [cid]
            if min_rating:
                conditions.append("overall_rating >= %s")
                params.append(min_rating)
            if booking_id:
                conditions.append("booking_id=%s")
                params.append(booking_id)
            where = " AND ".join(conditions)

            rows = db.execute(
                f"SELECT * FROM booking_reviews WHERE {where} ORDER BY created_at DESC LIMIT %s OFFSET %s",
                params + [limit, offset], fetch="all"
            )
            total_row = db.execute(
                f"SELECT COUNT(*) AS n FROM booking_reviews WHERE {where}", params, fetch="one"
            )
            return {
                "success": True,
                "data": [dict(r) for r in (rows or [])],
                "meta": {
                    "page": page,
                    "per_page": limit,
                    "total": total_row["n"] if total_row else 0,
                },
            }
        except Exception as e:
            log.error("list_reviews: %s", e)
    return {"success": True, "data": [], "meta": {"total": 0}}


@router.get("/summary")
async def reviews_summary(request: Request, session=Depends(_require_client)):
    """ملخص التقييمات — المتوسطات + التوزيع"""
    db  = request.app.state.db
    cid = session["client_id"]

    if db.use_postgres:
        try:
            row = db.execute("""
                SELECT
                    COUNT(*)                              AS total,
                    ROUND(AVG(overall_rating)::numeric,2) AS avg_overall,
                    ROUND(AVG(cleanliness)::numeric,2)    AS avg_cleanliness,
                    ROUND(AVG(service)::numeric,2)        AS avg_service,
                    ROUND(AVG(location)::numeric,2)       AS avg_location,
                    ROUND(AVG(value_for_money)::numeric,2)AS avg_value
                FROM booking_reviews
                WHERE client_id=%s
            """, (cid,), fetch="one")

            dist = db.execute("""
                SELECT overall_rating AS stars, COUNT(*) AS count
                FROM booking_reviews
                WHERE client_id=%s
                GROUP BY overall_rating
                ORDER BY overall_rating DESC
            """, (cid,), fetch="all")

            trend = db.execute("""
                SELECT
                    TO_CHAR(DATE_TRUNC('month', created_at), 'YYYY-MM') AS month,
                    ROUND(AVG(overall_rating)::numeric,2) AS avg
                FROM booking_reviews
                WHERE client_id=%s
                  AND created_at >= NOW() - INTERVAL '6 months'
                GROUP BY 1
                ORDER BY 1
            """, (cid,), fetch="all")

            return {
                "success": True,
                "data": {
                    "totals": dict(row) if row else {},
                    "distribution": [dict(r) for r in (dist or [])],
                    "monthly_trend": [dict(r) for r in (trend or [])],
                },
            }
        except Exception as e:
            log.error("reviews_summary: %s", e)
    return {"success": True, "data": {"totals": {}, "distribution": [], "monthly_trend": []}}


@router.get("/{review_id}")
async def get_review(
    review_id: int,
    request: Request,
    session=Depends(_require_client),
):
    db  = request.app.state.db
    cid = session["client_id"]
    if db.use_postgres:
        row = db.execute(
            "SELECT * FROM booking_reviews WHERE id=%s AND client_id=%s",
            (review_id, cid), fetch="one"
        )
        if not row:
            raise HTTPException(404, "التقييم غير موجود")
        return {"success": True, "data": dict(row)}
    raise HTTPException(404, "غير متاح")


@router.post("/{review_id}/reply")
async def reply_to_review(
    review_id: int,
    body: ReplySchema,
    request: Request,
    session=Depends(_require_client),
):
    _require_manager(session)
    db   = request.app.state.db
    cid  = session["client_id"]
    user = session.get("user_id") or cid

    if db.use_postgres:
        try:
            db.execute("""
                UPDATE booking_reviews
                SET management_reply=%s, replied_by=%s, replied_at=NOW()
                WHERE id=%s AND client_id=%s
            """, (body.reply, user, review_id, cid))
            return {"success": True, "message": "تم حفظ الرد"}
        except Exception as e:
            raise HTTPException(500, str(e))
    raise HTTPException(400, "يتطلب PostgreSQL")


@router.delete("/{review_id}")
async def hide_review(
    review_id: int,
    request: Request,
    session=Depends(_require_client),
):
    _require_manager(session)
    db  = request.app.state.db
    cid = session["client_id"]
    if db.use_postgres:
        db.execute(
            "UPDATE booking_reviews SET is_public=FALSE WHERE id=%s AND client_id=%s",
            (review_id, cid)
        )
    return {"success": True, "message": "تم إخفاء التقييم"}
