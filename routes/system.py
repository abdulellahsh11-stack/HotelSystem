#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
routes/system.py — الصحة والحالة والنسخ الاحتياطي والتحليل الذكي
مُستخرَج ضمن تقسيم ملف المسارات الكبير لتسهيل الصيانة.
"""
import json
import os
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import (
    JSONResponse,
)

from app_core import (
    log, _lock, _client_sessions,
    require_client,
)

router = APIRouter()

# ──────────────────────────────────────────────────────────────
#  Health & Status
# ──────────────────────────────────────────────────────────────
@router.get("/api/health")
async def health(request: Request):
    db = getattr(request.app.state, "db", None)
    db_ok = False
    try:
        if db:
            result = db.health()
            db_ok = bool(result and result.get("ok"))
    except Exception:
        pass
    return {
        "ok": True,
        "status": "healthy",
        "db": "connected" if db_ok else "unavailable",
        "time": datetime.now().isoformat(),
        "version": "3.1.0",
    }


@router.get("/api/status")
async def status(request: Request):
    db = request.app.state.db
    sessions_count = 0
    try:
        with _lock:
            sessions_count = len(_client_sessions)
    except Exception:
        pass
    return {
        "ok": True,
        "version": "3.0.0",
        "db": db.health(),
        "active_sessions": sessions_count,
        "time": datetime.now().isoformat(),
    }


@router.get("/api/analytics/overview")
async def analytics_overview(request: Request, session=Depends(require_client)):
    """Aggregated cross-module overview for the analytics dashboard (M12)."""
    try:
        db = request.app.state.db
        cid = session["client_id"]
        result = {
            "employees": {"total": 0, "active": 0},
            "bookings": {"this_month": 0, "revenue_this_month": 0, "occupancy_rate": 0},
            "inventory": {"total_items": 0, "low_stock": 0, "total_value": 0},
            "maintenance": {"open_orders": 0, "in_progress": 0},
            "tours": {"total_tours": 0, "bookings_this_month": 0},
        }
        if not db.use_postgres:
            return {"success": True, "data": result}

        # Employees
        row = db.execute(
            "SELECT COUNT(*) as total, COUNT(*) FILTER(WHERE status='active') as active FROM employees WHERE client_id=%s",
            (cid,), fetch="one"
        )
        if row:
            result["employees"] = {"total": row["total"] or 0, "active": row["active"] or 0}

        # Bookings this month
        row = db.execute(
            """SELECT COUNT(*) as cnt,
                      COALESCE(SUM(total_room), 0) as revenue,
                      ROUND(COUNT(*) FILTER(WHERE status IN ('confirmed','checked_in')) * 100.0 / NULLIF(COUNT(*), 0), 1) as occ
               FROM bookings
               WHERE client_id=%s
                 AND DATE_TRUNC('month', check_in) = DATE_TRUNC('month', NOW())""",
            (cid,), fetch="one"
        )
        if row:
            result["bookings"] = {
                "this_month": row["cnt"] or 0,
                "revenue_this_month": float(row["revenue"] or 0),
                "occupancy_rate": float(row["occ"] or 0),
            }

        # Inventory
        row = db.execute(
            """SELECT COUNT(*) as total,
                      COUNT(*) FILTER(WHERE quantity <= reorder_level AND reorder_level > 0) as low_stock,
                      COALESCE(SUM(quantity * price_per_unit), 0) as total_value
               FROM warehouse_items WHERE client_id=%s""",
            (cid,), fetch="one"
        )
        if row:
            result["inventory"] = {
                "total_items": row["total"] or 0,
                "low_stock": row["low_stock"] or 0,
                "total_value": float(row["total_value"] or 0),
            }

        # Maintenance
        row = db.execute(
            """SELECT COUNT(*) FILTER(WHERE status='open') as open_cnt,
                      COUNT(*) FILTER(WHERE status='in_progress') as in_progress
               FROM maintenance_orders WHERE client_id=%s""",
            (cid,), fetch="one"
        )
        if row:
            result["maintenance"] = {
                "open_orders": row["open_cnt"] or 0,
                "in_progress": row["in_progress"] or 0,
            }

        # Tours
        row = db.execute(
            """SELECT COUNT(DISTINCT tc.id) as total_tours,
                      COUNT(tb.id) FILTER(WHERE DATE_TRUNC('month', tb.created_at) = DATE_TRUNC('month', NOW())) as monthly_bookings
               FROM tour_catalog tc
               LEFT JOIN tour_bookings tb ON tc.id = tb.tour_id AND tb.client_id=%s
               WHERE tc.client_id=%s""",
            (cid, cid), fetch="one"
        )
        if row:
            result["tours"] = {
                "total_tours": row["total_tours"] or 0,
                "bookings_this_month": row["monthly_bookings"] or 0,
            }

        return {"success": True, "data": result}
    except HTTPException:
        raise
    except Exception as e:
        log.error(f"analytics_overview error: {e}", exc_info=True)
        raise HTTPException(500, f"خطأ في التحليلات: {str(e)}")


# ──────────────────────────────────────────────────────────────
#  AI Analyze
# ──────────────────────────────────────────────────────────────
@router.post("/api/ai/analyze")
async def ai_analyze(request: Request, session=Depends(require_client)):
    body = await request.json()
    prompt = body.get("prompt", "")
    if not prompt:
        return JSONResponse({"success": False, "error": "الـ prompt مطلوب"}, status_code=400)

    cfg = request.app.state.cfg
    if not cfg.anthropic_api_key:
        return {"success": False, "error": "خدمة الذكاء الاصطناعي غير مُفعَّلة", "response": "خدمة الذكاء الاصطناعي غير متوفرة حالياً. يرجى إضافة ANTHROPIC_API_KEY في إعدادات النظام."}

    try:
        import anthropic
        store = request.app.state.store
        cid = session["client_id"]
        bookings = store.get_bookings(cid)
        guests = store.get_guests(cid)
        invoices = store.get_invoices(cid)
        ctx = f"إجمالي النزلاء: {len(guests)}, إجمالي الحجوزات: {len(bookings)}, إجمالي الفواتير: {len(invoices)}"
        client_ai = anthropic.Anthropic(api_key=cfg.anthropic_api_key)
        msg = client_ai.messages.create(
            model="claude-opus-4-5",
            max_tokens=1024,
            messages=[{"role": "user", "content": f"أنت مستشار فندقي خبير. البيانات المتاحة: {ctx}\n\nالسؤال: {prompt}"}],
        )
        return {"success": True, "response": msg.content[0].text}
    except Exception as e:
        log.error(f"AI error: {e}")
        return {"success": False, "error": str(e), "response": "حدث خطأ في الاتصال بالذكاء الاصطناعي"}


# ──────────────────────────────────────────────────────────────
#  Backup
# ──────────────────────────────────────────────────────────────
@router.post("/api/backup/create")
async def backup_create(request: Request, session=Depends(require_client)):
    store = request.app.state.store
    cid = session["client_id"]
    backup_data = {
        "client_id": cid,
        "timestamp": datetime.now().isoformat(),
        "guests": store.get_guests(cid),
        "bookings": store.get_bookings(cid),
        "invoices": store.get_invoices(cid),
        "pos": store.get_pos_transactions(cid),
    }
    os.makedirs("backups", exist_ok=True)
    filename = f"backup_{cid}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    filepath = os.path.join("backups", filename)
    try:
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(backup_data, f, ensure_ascii=False, indent=2, default=str)
        return {"success": True, "filename": filename}
    except Exception as e:
        return JSONResponse({"success": False, "error": str(e)}, status_code=500)


@router.get("/api/backup/list")
async def backup_list(request: Request, session=Depends(require_client)):
    cid = session["client_id"]
    backup_dir = "backups"
    if not os.path.isdir(backup_dir):
        return {"success": True, "backups": []}
    files = sorted([f for f in os.listdir(backup_dir) if f.startswith(f"backup_{cid}_")], reverse=True)
    return {"success": True, "backups": files}


