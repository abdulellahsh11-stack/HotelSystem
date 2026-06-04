#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""M11 — مؤشرات الأداء KPI Analytics"""
import logging
from datetime import date, timedelta
from typing import Optional
from fastapi import APIRouter, Request, Depends, HTTPException

router = APIRouter(prefix="/api/m11", tags=["KPI"])

logger = logging.getLogger("dheuof")


def _require_client(request: Request) -> dict:
    from main import require_client
    return require_client(request)


@router.get("/dashboard")
async def kpi_dashboard(request: Request, session=Depends(_require_client)):
    try:
        db = request.app.state.db
        cid = session["client_id"]
        today = date.today()
        month_start = today.replace(day=1)

        if not db.use_postgres:
            return {"success": True, "data": {}}

        rooms_total = db.execute(
            "SELECT COUNT(*) as c FROM rooms WHERE client_id=%s", (cid,), fetch="one")
        total_rooms = dict(rooms_total).get("c", 1) if rooms_total else 1

        occupied = db.execute("""
            SELECT COUNT(*) as c FROM bookings
            WHERE client_id=%s AND status IN ('confirmed','checked_in')
            AND check_in <= %s AND check_out > %s
        """, (cid, today.isoformat(), today.isoformat()), fetch="one")
        occupied_rooms = dict(occupied).get("c", 0) if occupied else 0

        occupancy = round((occupied_rooms / max(total_rooms, 1)) * 100, 1)

        month_rev = db.execute("""
            SELECT COALESCE(SUM(total_amount), 0) as s FROM invoices
            WHERE client_id=%s AND issue_date >= %s
        """, (cid, month_start.isoformat()), fetch="one")
        revenue_month = float(dict(month_rev).get("s", 0)) if month_rev else 0

        month_bk = db.execute("""
            SELECT COUNT(*) as c FROM bookings
            WHERE client_id=%s AND check_in >= %s
        """, (cid, month_start.isoformat()), fetch="one")
        bookings_month = dict(month_bk).get("c", 0) if month_bk else 0

        adr = round(revenue_month / max(occupied_rooms * 30, 1), 2)
        revpar = round(revenue_month / max(total_rooms * 30, 1), 2)

        monthly = db.execute("""
            SELECT TO_CHAR(issue_date, 'YYYY-MM') as month,
                   SUM(total_amount) as revenue,
                   COUNT(*) as invoices
            FROM invoices WHERE client_id=%s
            GROUP BY month ORDER BY month DESC LIMIT 12
        """, (cid,), fetch="all")

        checkins_today = db.execute("""
            SELECT COUNT(*) as c FROM bookings
            WHERE client_id=%s AND check_in=%s AND status='confirmed'
        """, (cid, today.isoformat()), fetch="one")
        checkouts_today = db.execute("""
            SELECT COUNT(*) as c FROM bookings
            WHERE client_id=%s AND check_out=%s AND status='checked_in'
        """, (cid, today.isoformat()), fetch="one")

        return {
            "success": True,
            "data": {
                "total_rooms": total_rooms,
                "occupied_rooms": occupied_rooms,
                "occupancy_rate": occupancy,
                "adr": adr,
                "revpar": revpar,
                "revenue_month": revenue_month,
                "bookings_month": bookings_month,
                "checkins_today": dict(checkins_today).get("c", 0) if checkins_today else 0,
                "checkouts_today": dict(checkouts_today).get("c", 0) if checkouts_today else 0,
                "monthly_revenue": [dict(r) for r in (monthly or [])],
            }
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in kpi_dashboard: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"خطأ في الخادم: {str(e)}")


@router.get("/revpar")
async def revpar_trend(request: Request, days: int = 30, session=Depends(_require_client)):
    try:
        db = request.app.state.db
        cid = session["client_id"]
        if db.use_postgres:
            rows = db.execute("""
                SELECT kpi_date, occupancy_rate, adr, revpar, revenue_total
                FROM daily_kpis WHERE client_id=%s
                ORDER BY kpi_date DESC LIMIT %s
            """, (cid, days), fetch="all")
            return {"success": True, "data": [dict(r) for r in (rows or [])]}
        return {"success": True, "data": []}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in revpar_trend: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"خطأ في الخادم: {str(e)}")


@router.post("/recalculate")
async def recalculate_kpis(request: Request, session=Depends(_require_client)):
    try:
        db = request.app.state.db
        cid = session["client_id"]
        if not db.use_postgres:
            return {"success": True, "message": "لا يتوفر PostgreSQL"}

        today = date.today()
        total_rooms = db.execute(
            "SELECT COUNT(*) as c FROM rooms WHERE client_id=%s", (cid,), fetch="one")
        total = dict(total_rooms).get("c", 0) if total_rooms else 0

        for i in range(7):
            d = today - timedelta(days=i)
            occ = db.execute("""
                SELECT COUNT(*) as c FROM bookings
                WHERE client_id=%s AND check_in<=%s AND check_out>%s
                AND status IN ('checked_in','confirmed','checked_out')
            """, (cid, d.isoformat(), d.isoformat()), fetch="one")
            occ_count = dict(occ).get("c", 0) if occ else 0
            rev = db.execute("""
                SELECT COALESCE(SUM(total_amount), 0) as s FROM invoices
                WHERE client_id=%s AND issue_date=%s
            """, (cid, d.isoformat()), fetch="one")
            revenue = float(dict(rev).get("s", 0)) if rev else 0
            occ_rate = round((occ_count / max(total, 1)) * 100, 2)
            adr = round(revenue / max(occ_count, 1), 2)
            revpar = round(revenue / max(total, 1), 2)
            db.execute("""
                INSERT INTO daily_kpis
                    (client_id,kpi_date,total_rooms,occupied_rooms,occupancy_rate,
                     adr,revpar,revenue_total,check_ins,check_outs)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,0,0)
                ON CONFLICT (client_id,kpi_date) DO UPDATE SET
                    occupied_rooms=EXCLUDED.occupied_rooms,
                    occupancy_rate=EXCLUDED.occupancy_rate,
                    adr=EXCLUDED.adr, revpar=EXCLUDED.revpar,
                    revenue_total=EXCLUDED.revenue_total
            """, (cid, d.isoformat(), total, occ_count, occ_rate, adr, revpar, revenue))
        return {"success": True, "message": "تم إعادة احتساب KPIs لآخر 7 أيام"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in recalculate_kpis: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"خطأ في الخادم: {str(e)}")
