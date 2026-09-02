#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
routes/leads.py — الزوّار المهتمّون، يراهم مالك المنصة وحده

من يفتح صفحة التسويق ولا يشترك ضاع أثره تماماً: لا اسم ولا وسيلة تواصل
ولا علمٌ بما نظر إليه. وهذا أهدرُ ما في منصّةٍ تُسوَّق — العميل جاء
بنفسه ثم انصرف بلا أن يعلم أحد.

قرارات صريحة:

**لا تتبّع صامت.** يُسجَّل ما يكتبه الزائر بيده في نموذج «تواصل معنا»
لا ما يُلتقط من متصفّحه. لا بصمة جهاز ولا كوكي تتبّع: منصّةٌ تحفظ بيانات
نزلاء لا يليق بها أن تتجسّس على زوّارها.

**عنوان IP لا يُخزَّن كاملاً.** آخر مقطعٍ يُصفَّر (`1.2.3.0`) — يكفي
لمعرفة البلد والحدّ من الإغراق، ولا يُعرّف شخصاً بعينه.

**الكتابة عامّة والقراءة لمالك المنصة وحده.** أي زائر يستطيع الإرسال —
وإلا لم يكن نموذجاً — فالحدّ يمنع الإغراق: عشر رسائل للعنوان الواحد في
الساعة. والقراءة خلف جلسة `admin_token` المنفصلة.

**لا يمسّ عزل المنشآت.** الزوّار ليسوا مستأجرين ولا `client_id` لهم؛
الجدول خارج نطاق العزل عمداً، ولذلك لا يُقرأ إلا بجلسة مالك المنصة.
"""
from __future__ import annotations

import logging
import re
import time
from threading import Lock

from fastapi import APIRouter, Depends, HTTPException, Request

from app_core import require_admin

router = APIRouter(tags=["Leads"])
log = logging.getLogger("dheuof.leads")

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[a-zA-Z]{2,}$")
PHONE_RE = re.compile(r"^[+0-9\s()-]{7,20}$")

MAX_PER_HOUR = 10
_hits: dict[str, list[float]] = {}
_hits_lock = Lock()


def _anon_ip(request: Request) -> str:
    """
    العنوان بلا مقطعه الأخير.

    تخزينُه كاملاً يجعل الجدول سجلَّ تتبّعٍ لأشخاص، وتخزينُ لا شيء يمنع
    الحدّ من الإغراق. التصفير يحفظ الغرضين.
    """
    from app_core import client_ip

    raw = client_ip(request) or ""
    if ":" in raw:                                   # IPv6
        return ":".join(raw.split(":")[:4]) + "::"
    parts = raw.split(".")
    return ".".join(parts[:3]) + ".0" if len(parts) == 4 else "0.0.0.0"


def _rate_ok(key: str) -> bool:
    now = time.time()
    with _hits_lock:
        seen = [t for t in _hits.get(key, []) if now - t < 3600]
        if len(seen) >= MAX_PER_HOUR:
            _hits[key] = seen
            return False
        seen.append(now)
        _hits[key] = seen
        return True


def _db(request: Request):
    db = request.app.state.db
    if not getattr(db, "use_postgres", False):
        raise HTTPException(status_code=503, detail="قاعدة البيانات غير متاحة")
    return db


def ensure_schema(db) -> None:
    """يُنشئ الجدول عند الإقلاع. يُنادى من `app_core`."""
    if not getattr(db, "use_postgres", False):
        return
    db.execute("""
        CREATE TABLE IF NOT EXISTS leads (
            id          SERIAL PRIMARY KEY,
            full_name   VARCHAR(120) NOT NULL,
            phone       VARCHAR(30),
            email       VARCHAR(160),
            hotel_name  VARCHAR(160),
            city        VARCHAR(80),
            rooms       INTEGER,
            message     TEXT,
            source      VARCHAR(60) DEFAULT 'website',
            ip_prefix   VARCHAR(45),
            status      VARCHAR(20) DEFAULT 'new',
            created_at  TIMESTAMPTZ DEFAULT NOW()
        )
    """)
    db.execute("CREATE INDEX IF NOT EXISTS idx_leads_created ON leads(created_at DESC)")


# ──────────────────────────────────────────────────────────────
#  الإرسال — من أي زائر
# ──────────────────────────────────────────────────────────────
@router.post("/api/leads")
async def create_lead(request: Request):
    """يستقبل نموذج «تواصل معنا» من صفحة التسويق."""
    ip = _anon_ip(request)
    if not _rate_ok(ip):
        raise HTTPException(status_code=429, detail="محاولات كثيرة — حاول بعد قليل")

    data = await request.json()
    name = str(data.get("full_name") or "").strip()[:120]
    phone = str(data.get("phone") or "").strip()[:30]
    email = str(data.get("email") or "").strip()[:160]

    if not name:
        raise HTTPException(status_code=400, detail="الاسم مطلوب")
    if not phone and not email:
        raise HTTPException(status_code=400, detail="أدخل رقم جوال أو بريداً إلكترونياً")
    if phone and not PHONE_RE.match(phone):
        raise HTTPException(status_code=400, detail="رقم الجوال غير صحيح")
    if email and not EMAIL_RE.match(email):
        raise HTTPException(status_code=400, detail="البريد الإلكتروني غير صحيح")

    try:
        rooms = int(data.get("rooms") or 0) or None
    except (TypeError, ValueError):
        rooms = None

    _db(request).execute(
        """INSERT INTO leads
           (full_name, phone, email, hotel_name, city, rooms, message, source, ip_prefix)
           VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
        (name, phone or None, email or None,
         str(data.get("hotel_name") or "").strip()[:160] or None,
         str(data.get("city") or "").strip()[:80] or None,
         rooms,
         str(data.get("message") or "").strip()[:2000] or None,
         str(data.get("source") or "website").strip()[:60],
         ip),
    )
    log.info("زائر جديد سجّل اهتمامه: %s", name)
    return {"success": True, "message": "وصلتنا بياناتك — سنتواصل معك قريباً"}


# ──────────────────────────────────────────────────────────────
#  القراءة — مالك المنصة وحده
# ──────────────────────────────────────────────────────────────
@router.get("/api/admin/leads")
async def list_leads(request: Request, status: str = "", limit: int = 200,
                     _=Depends(require_admin)):
    limit = max(1, min(int(limit or 200), 1000))
    db = _db(request)
    if status:
        rows = db.execute(
            "SELECT * FROM leads WHERE status=%s ORDER BY created_at DESC LIMIT %s",
            (status, limit), fetch="all")
    else:
        rows = db.execute(
            "SELECT * FROM leads ORDER BY created_at DESC LIMIT %s", (limit,), fetch="all")

    counts = db.execute(
        "SELECT status, COUNT(*) AS n FROM leads GROUP BY status", fetch="all") or []
    return {
        "success": True,
        "data": [dict(r) for r in (rows or [])],
        "counts": {r["status"]: r["n"] for r in counts},
    }


@router.patch("/api/admin/leads/{lead_id}")
async def update_lead(lead_id: int, request: Request, _=Depends(require_admin)):
    """يُغيّر حالة المتابعة: جديد · تُوُوصل معه · اشترك · مُهمَل."""
    data = await request.json()
    new_status = str(data.get("status") or "").strip()
    if new_status not in {"new", "contacted", "converted", "dropped"}:
        raise HTTPException(status_code=400, detail="حالة غير معروفة")
    db = _db(request)
    if not db.execute("SELECT id FROM leads WHERE id=%s", (lead_id,), fetch="one"):
        raise HTTPException(status_code=404, detail="السجل غير موجود")
    db.execute("UPDATE leads SET status=%s WHERE id=%s", (new_status, lead_id))
    return {"success": True}
