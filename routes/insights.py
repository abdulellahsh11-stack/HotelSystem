#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
routes/insights.py — مؤشرات الأداء والتحليلات والإشعارات والاشتراك
مُستخرَج ضمن تقسيم ملف المسارات الكبير لتسهيل الصيانة.
"""
from datetime import datetime, date

from fastapi import APIRouter, Depends, Request

from app_core import (
    require_client,
)

router = APIRouter()

# ──────────────────────────────────────────────────────────────
#  KPI, Analytics, Notifications, Subscription
# ──────────────────────────────────────────────────────────────
@router.get("/api/kpi")
async def get_kpi(request: Request, session=Depends(require_client)):
    store = request.app.state.store
    cid = session["client_id"]
    bookings = store.get_bookings(cid)
    guests = store.get_guests(cid)
    today = date.today()
    month_start = today.replace(day=1).isoformat()
    active = [b for b in bookings if b.get("status") in ("confirmed", "checked_in")]
    monthly_bk = [b for b in bookings if str(b.get("check_in", "")) >= month_start]
    invoices = store.get_invoices(cid)
    monthly_rev = sum(float(inv.get("total_amount", inv.get("total", 0))) for inv in invoices if str(inv.get("issue_date", inv.get("created_at", "")))[:7] == today.strftime("%Y-%m"))
    return {"success": True, "kpi": {"active_bookings": len(active), "total_guests": len(guests), "monthly_revenue": monthly_rev, "monthly_bookings": len(monthly_bk)}}


@router.get("/api/analytics")
async def get_analytics(request: Request, session=Depends(require_client)):
    store = request.app.state.store
    cid = session["client_id"]
    bookings = store.get_bookings(cid)
    invoices = store.get_invoices(cid)
    total_rev = sum(float(inv.get("total_amount", inv.get("total", 0))) for inv in invoices)
    monthly: dict = {}
    for inv in invoices:
        m = str(inv.get("issue_date", inv.get("created_at", "")))[:7]
        if m:
            monthly[m] = monthly.get(m, 0) + float(inv.get("total_amount", inv.get("total", 0)))
    monthly_list = [{"month": k, "revenue": v} for k, v in sorted(monthly.items())]
    return {"success": True, "data": {"monthly_revenue": monthly_list, "total_bookings": len(bookings), "total_revenue": total_rev}}


@router.get("/api/notifications")
async def get_notifications(request: Request, session=Depends(require_client)):
    store = request.app.state.store
    cid = session["client_id"]
    notifications = []
    client = store.get_client(cid) or {}
    trial_end = client.get("trial_end", client.get("subscription_expires", ""))
    if trial_end:
        try:
            te = datetime.fromisoformat(str(trial_end))
            days_left = (te - datetime.utcnow()).days
            if 0 <= days_left < 7:
                notifications.append({"type": "warn", "title": "انتهاء التجربة المجانية قريباً", "body": f"تبقى {days_left} أيام على انتهاء اشتراكك"})
            elif days_left < 0:
                notifications.append({"type": "error", "title": "انتهى الاشتراك", "body": "يرجى تجديد اشتراكك للاستمرار في الاستخدام"})
        except Exception:
            pass
    today = date.today().isoformat()
    bookings = store.get_bookings(cid)
    co_today = [b for b in bookings if b.get("check_out", "") == today and b.get("status") == "checked_in"]
    ci_today = [b for b in bookings if b.get("check_in", "") == today and b.get("status") == "confirmed"]
    if co_today:
        notifications.append({"type": "info", "title": "مغادرات اليوم", "body": f"يوجد {len(co_today)} حجز يغادر اليوم"})
    if ci_today:
        notifications.append({"type": "info", "title": "وصولات اليوم", "body": f"يوجد {len(ci_today)} حجز يصل اليوم"})
    return {"success": True, "notifications": notifications}


@router.get("/api/subscription")
async def get_subscription(request: Request, session=Depends(require_client)):
    store = request.app.state.store
    client = store.get_client(session["client_id"]) or {}
    return {"success": True, "subscription": {
        "plan": client.get("plan", "trial"),
        "status": client.get("status", "trial"),
        "trial_end": client.get("trial_end", client.get("subscription_expires")),
    }}


@router.get("/api/payment/plans")
async def get_plans():
    return {"success": True, "plans": [
        {"id": "trial", "name": "تجربة مجانية", "price": 0, "duration": 30, "modules": ["M01", "M02"]},
        {"id": "starter", "name": "Starter", "price": 599, "duration": 30, "modules": ["M01", "M02", "M07"]},
        {"id": "operations", "name": "Operations", "price": 1099, "duration": 30, "modules": ["M01", "M02", "M05", "M07", "M08", "M13"]},
        {"id": "professional", "name": "Professional", "price": 2299, "duration": 30, "modules": ["M01", "M02", "M03", "M04", "M05", "M06", "M07", "M08", "M11", "M13"]},
        {"id": "enterprise", "name": "Enterprise", "price": None, "duration": 30, "modules": "all"},
    ]}


