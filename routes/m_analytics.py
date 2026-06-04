#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Cross-module analytics aggregation"""
import logging
from fastapi import APIRouter, Request, Depends, HTTPException

router = APIRouter(prefix="/api/analytics", tags=["Analytics"])
logger = logging.getLogger("dheuof")


def _require_client(request: Request) -> dict:
    from main import require_client
    return require_client(request)


@router.get("/overview")
async def analytics_overview(request: Request, session=Depends(_require_client)):
    """Aggregate KPIs from all modules into one response."""
    try:
        db = request.app.state.db
        cid = session["client_id"]
        if not db.use_postgres:
            return {"success": True, "data": {}}

        result = {}

        # Guests & bookings
        try:
            r = db.execute("""
                SELECT
                    COUNT(*) as total_guests,
                    COUNT(*) FILTER (WHERE created_at > NOW() - INTERVAL '30 days') as new_guests
                FROM guests WHERE client_id=%s
            """, (cid,), fetch="one")
            result["guests"] = dict(r) if r else {}
        except Exception as e:
            logger.warning(f"analytics guests: {e}")
            result["guests"] = {}

        # Bookings
        try:
            r = db.execute("""
                SELECT
                    COUNT(*) as total_bookings,
                    COUNT(*) FILTER (WHERE status='checked_in') as active,
                    COUNT(*) FILTER (WHERE status='confirmed') as confirmed,
                    COALESCE(SUM(total_room) FILTER (WHERE status NOT IN ('cancelled')), 0) as total_revenue,
                    COALESCE(SUM(total_room) FILTER (
                        WHERE DATE_TRUNC('month', created_at) = DATE_TRUNC('month', NOW())
                        AND status NOT IN ('cancelled')
                    ), 0) as month_revenue
                FROM bookings WHERE client_id=%s
            """, (cid,), fetch="one")
            result["bookings"] = dict(r) if r else {}
        except Exception as e:
            logger.warning(f"analytics bookings: {e}")
            result["bookings"] = {}

        # Rooms
        try:
            r = db.execute("""
                SELECT
                    COUNT(*) as total_rooms,
                    COUNT(*) FILTER (WHERE status='available') as available,
                    COUNT(*) FILTER (WHERE status='occupied') as occupied,
                    COUNT(*) FILTER (WHERE status='cleaning') as cleaning
                FROM rooms WHERE client_id=%s
            """, (cid,), fetch="one")
            result["rooms"] = dict(r) if r else {}
        except Exception as e:
            logger.warning(f"analytics rooms: {e}")
            result["rooms"] = {}

        # Staff
        try:
            r = db.execute("""
                SELECT COUNT(*) as total, COUNT(*) FILTER (WHERE status='active') as active
                FROM employees WHERE client_id=%s
            """, (cid,), fetch="one")
            result["staff"] = dict(r) if r else {}
        except Exception as e:
            logger.warning(f"analytics staff: {e}")
            result["staff"] = {}

        # Inventory alerts
        try:
            r = db.execute("""
                SELECT COUNT(*) as low_stock_items
                FROM warehouse_items
                WHERE client_id=%s AND reorder_level > 0 AND quantity <= reorder_level
            """, (cid,), fetch="one")
            result["inventory"] = dict(r) if r else {}
        except Exception as e:
            logger.warning(f"analytics inventory: {e}")
            result["inventory"] = {}

        # Maintenance
        try:
            r = db.execute("""
                SELECT COUNT(*) as open_orders,
                       COUNT(*) FILTER (WHERE priority='urgent') as urgent
                FROM maintenance_orders WHERE client_id=%s AND status IN ('open','in_progress')
            """, (cid,), fetch="one")
            result["maintenance"] = dict(r) if r else {}
        except Exception as e:
            logger.warning(f"analytics maintenance: {e}")
            result["maintenance"] = {}

        # POS (if table exists)
        try:
            r = db.execute("""
                SELECT
                    COUNT(*) FILTER (WHERE created_at::date = CURRENT_DATE) as today_sales,
                    COALESCE(SUM(total) FILTER (WHERE created_at::date = CURRENT_DATE), 0) as today_revenue
                FROM pos_sales WHERE client_id=%s AND status='completed'
            """, (cid,), fetch="one")
            result["pos"] = dict(r) if r else {}
        except Exception:
            result["pos"] = {"today_sales": 0, "today_revenue": 0}

        return {"success": True, "data": result}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in analytics_overview: {e}", exc_info=True)
        raise HTTPException(500, detail=f"خطأ في الخادم: {str(e)}")


@router.get("/revenue-trend")
async def revenue_trend(request: Request, months: int = 6, session=Depends(_require_client)):
    """Monthly revenue trend for charts."""
    try:
        db = request.app.state.db
        cid = session["client_id"]
        if not db.use_postgres:
            return {"success": True, "data": []}
        rows = db.execute("""
            SELECT
                TO_CHAR(DATE_TRUNC('month', check_in), 'YYYY-MM') as month,
                COALESCE(SUM(total_room), 0) as revenue,
                COUNT(*) as bookings
            FROM bookings
            WHERE client_id=%s
              AND status NOT IN ('cancelled')
              AND check_in >= NOW() - (%s || ' months')::INTERVAL
            GROUP BY DATE_TRUNC('month', check_in)
            ORDER BY DATE_TRUNC('month', check_in)
        """, (cid, months), fetch="all")
        return {"success": True, "data": [dict(r) for r in (rows or [])]}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in revenue_trend: {e}", exc_info=True)
        raise HTTPException(500, detail=f"خطأ في الخادم: {str(e)}")


@router.get("/occupancy-heatmap")
async def occupancy_heatmap(request: Request, session=Depends(_require_client)):
    """Room occupancy by day of week and hour — for heatmap visualization."""
    try:
        db = request.app.state.db
        cid = session["client_id"]
        if not db.use_postgres:
            return {"success": True, "data": []}
        rows = db.execute("""
            SELECT
                EXTRACT(DOW FROM check_in) as day_of_week,
                COUNT(*) as bookings,
                COALESCE(AVG(
                    EXTRACT(EPOCH FROM (check_out::timestamp - check_in::timestamp)) / 86400
                ), 0) as avg_nights
            FROM bookings
            WHERE client_id=%s AND status NOT IN ('cancelled')
              AND check_in >= NOW() - INTERVAL '90 days'
            GROUP BY day_of_week
            ORDER BY day_of_week
        """, (cid,), fetch="all")
        return {"success": True, "data": [dict(r) for r in (rows or [])]}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in occupancy_heatmap: {e}", exc_info=True)
        raise HTTPException(500, detail=f"خطأ في الخادم: {str(e)}")
