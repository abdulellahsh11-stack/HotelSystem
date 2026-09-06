#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Night Audit — إغلاق اليوم + أجهزة الدفع + جدولة تلقائية"""
import json
import logging
from datetime import datetime, date
from decimal import Decimal
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel

router = APIRouter(prefix="/api/night-audit", tags=["NightAudit"])
log = logging.getLogger("dheuof.night_audit")

# APScheduler instance — مشترك بين طلبات الـ API
_scheduler = None


def _get_scheduler():
    global _scheduler
    if _scheduler is None:
        from apscheduler.schedulers.background import BackgroundScheduler
        _scheduler = BackgroundScheduler(timezone="Asia/Riyadh")
        _scheduler.start()
    return _scheduler


def _require_client(request: Request) -> dict:
    from main import require_client
    return require_client(request)


def _require_manager(session: dict) -> dict:
    role = (session.get("role") or session.get("user_role") or "employee").lower()
    if role not in ("manager", "admin", "owner"):
        raise HTTPException(403, "هذه العملية متاحة للمدير فقط")
    return session


# ── Schemas ──────────────────────────────────────────────────────────────────

class NightAuditSettingsSchema(BaseModel):
    auto_run: bool = False
    scheduled_time: str = "23:59"
    default_check_in_time: str = "14:00"
    default_check_out_time: str = "12:00"
    grace_period_minutes: int = 30
    require_payment_close: bool = True


class PaymentDeviceSchema(BaseModel):
    device_name: str
    device_type: str = "POS"
    serial_number: Optional[str] = None


class RenameDeviceSchema(BaseModel):
    device_name: Optional[str] = None
    device_type: Optional[str] = None
    serial_number: Optional[str] = None


class SettleDeviceSchema(BaseModel):
    notes: Optional[str] = None


class RunAuditSchema(BaseModel):
    notes: Optional[str] = None
    force: bool = False


# ── helpers ──────────────────────────────────────────────────────────────────

def _get_settings(db, client_id: str) -> dict:
    defaults = {
        "auto_run": False,
        "scheduled_time": "23:59",
        "default_check_in_time": "14:00",
        "default_check_out_time": "12:00",
        "grace_period_minutes": 30,
        "require_payment_close": True,
    }
    if db.use_postgres:
        try:
            row = db.execute(
                "SELECT * FROM night_audit_settings WHERE client_id=%s",
                (client_id,), fetch="one"
            )
            if row:
                d = dict(row)
                return {k: d.get(k, defaults[k]) for k in defaults}
        except Exception as e:
            log.warning("_get_settings: %s", e)
    return defaults


def _ensure_settings_row(db, client_id: str) -> None:
    if not db.use_postgres:
        return
    try:
        db.execute("""
            INSERT INTO night_audit_settings (client_id)
            VALUES (%s)
            ON CONFLICT (client_id) DO NOTHING
        """, (client_id,))
    except Exception as e:
        log.warning("_ensure_settings_row: %s", e)


def _run_audit_logic(app_state, client_id: str, performed_by: str, trigger: str,
                     force: bool = False, notes: str = "") -> dict:
    """تشغيل Night Audit — المنطق الأساسي"""
    db = app_state.db
    today = date.today()
    now   = datetime.now()

    # 1. منع التكرار
    if not force and db.use_postgres:
        try:
            existing = db.execute(
                "SELECT id FROM night_audit_log WHERE client_id=%s AND audit_date=%s AND status='COMPLETED'",
                (client_id, today), fetch="one"
            )
            if existing:
                raise ValueError("تم إغلاق هذا اليوم مسبقاً")
        except ValueError:
            raise
        except Exception as e:
            log.warning("check existing audit: %s", e)

    settings = _get_settings(db, client_id)

    # 2. تحقق من أجهزة الدفع غير المغلقة
    unsettled_count = 0
    if settings["require_payment_close"] and db.use_postgres:
        try:
            row = db.execute("""
                SELECT COUNT(*) AS n FROM invoices
                WHERE client_id=%s
                  AND payment_status IN ('pending', 'partial')
                  AND issue_date::date = %s
            """, (client_id, today), fetch="one")
            unsettled_count = (row["n"] if row else 0)
            if unsettled_count > 0 and not force:
                raise ValueError(f"يوجد {unsettled_count} فاتورة غير مسددة — أغلق الدفع أولاً أو استخدم force=true")
        except ValueError:
            raise
        except Exception as e:
            log.warning("check unsettled: %s", e)

    # 3. جمع إحصاءات اليوم
    rooms_audited   = 0
    total_revenue   = Decimal("0")
    payments_verified = 0

    if db.use_postgres:
        try:
            # إيرادات اليوم
            rev_row = db.execute("""
                SELECT COALESCE(SUM(total_amount), 0) AS rev,
                       COUNT(*) AS cnt
                FROM invoices
                WHERE client_id=%s AND issue_date::date=%s
            """, (client_id, today), fetch="one")
            if rev_row:
                total_revenue   = Decimal(str(rev_row["rev"]))
                payments_verified = int(rev_row["cnt"])

            # عدد الغرف المشغولة
            room_row = db.execute("""
                SELECT COUNT(DISTINCT room_id) AS n FROM bookings
                WHERE client_id=%s
                  AND check_in::date <= %s
                  AND check_out::date > %s
                  AND status IN ('confirmed','checked_in')
            """, (client_id, today, today), fetch="one")
            rooms_audited = int(room_row["n"]) if room_row else 0

            # تحديث حجوزات No-Show
            db.execute("""
                UPDATE bookings
                SET status='no_show'
                WHERE client_id=%s
                  AND check_in::date = %s
                  AND status='confirmed'
            """, (client_id, today))

        except Exception as e:
            log.warning("audit stats query: %s", e)

    # 4. حفظ سجل الإغلاق
    log_id = None
    if db.use_postgres:
        try:
            report_data = json.dumps({
                "rooms_audited": rooms_audited,
                "total_revenue": float(total_revenue),
                "payments_verified": payments_verified,
                "unsettled_payments": unsettled_count,
                "performed_by": performed_by,
                "notes": notes,
            }, ensure_ascii=False)
            row = db.execute("""
                INSERT INTO night_audit_log
                    (client_id, audit_date, status, trigger_type,
                     started_at, completed_at, performed_by,
                     rooms_audited, payments_verified, unsettled_payments,
                     total_revenue, report_data, notes)
                VALUES (%s,%s,'COMPLETED',%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                RETURNING id
            """, (
                client_id, today, trigger,
                now, now, performed_by,
                rooms_audited, payments_verified, unsettled_count,
                float(total_revenue), report_data, notes,
            ), fetch="one")
            log_id = row["id"] if row else None
        except Exception as e:
            log.error("save audit log: %s", e)

    return {
        "log_id": log_id,
        "audit_date": str(today),
        "status": "COMPLETED",
        "trigger_type": trigger,
        "rooms_audited": rooms_audited,
        "payments_verified": payments_verified,
        "unsettled_payments": unsettled_count,
        "total_revenue": float(total_revenue),
        "performed_by": performed_by,
        "completed_at": now.isoformat(),
    }


def _reschedule_cron(app_state, client_id: str, settings: dict) -> None:
    """إعادة جدولة Night Audit Cron"""
    try:
        scheduler = _get_scheduler()
        job_id    = f"night_audit_{client_id}"

        # أزل الـ Job القديم إن وجد
        if scheduler.get_job(job_id):
            scheduler.remove_job(job_id)

        if not settings.get("auto_run"):
            return

        t = settings.get("scheduled_time", "23:59")
        hour, minute = t.split(":")

        scheduler.add_job(
            _run_audit_logic,
            trigger="cron",
            hour=int(hour),
            minute=int(minute),
            id=job_id,
            args=[app_state, client_id, "system", "SCHEDULED"],
            replace_existing=True,
        )
        log.info("Night Audit cron scheduled for %s at %s", client_id, t)
    except Exception as e:
        log.warning("_reschedule_cron: %s", e)


# ── Routes ───────────────────────────────────────────────────────────────────

@router.get("/settings")
async def get_settings(request: Request, session=Depends(_require_client)):
    db = request.app.state.db
    cid = session["client_id"]
    _ensure_settings_row(db, cid)
    return {"success": True, "data": _get_settings(db, cid)}


@router.patch("/settings")
async def update_settings(
    body: NightAuditSettingsSchema,
    request: Request,
    session=Depends(_require_client),
):
    _require_manager(session)
    db  = request.app.state.db
    cid = session["client_id"]
    user = session.get("user_id") or session.get("client_id")

    if db.use_postgres:
        try:
            db.execute("""
                INSERT INTO night_audit_settings
                    (client_id, auto_run, scheduled_time,
                     default_check_in_time, default_check_out_time,
                     grace_period_minutes, require_payment_close, updated_by, updated_at)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,NOW())
                ON CONFLICT (client_id) DO UPDATE SET
                    auto_run               = EXCLUDED.auto_run,
                    scheduled_time         = EXCLUDED.scheduled_time,
                    default_check_in_time  = EXCLUDED.default_check_in_time,
                    default_check_out_time = EXCLUDED.default_check_out_time,
                    grace_period_minutes   = EXCLUDED.grace_period_minutes,
                    require_payment_close  = EXCLUDED.require_payment_close,
                    updated_by             = EXCLUDED.updated_by,
                    updated_at             = NOW()
            """, (
                cid, body.auto_run, body.scheduled_time,
                body.default_check_in_time, body.default_check_out_time,
                body.grace_period_minutes, body.require_payment_close, user,
            ))
        except Exception as e:
            raise HTTPException(500, f"خطأ في حفظ الإعدادات: {e}")

    # إعادة جدولة الـ Cron
    _reschedule_cron(request.app.state, cid, body.dict())

    return {
        "success": True,
        "data": body.dict(),
        "message": "تم حفظ إعدادات Night Audit",
    }


@router.post("/run")
async def run_manual_audit(
    body: RunAuditSchema,
    request: Request,
    session=Depends(_require_client),
):
    _require_manager(session)
    cid  = session["client_id"]
    user = session.get("user_id") or cid

    try:
        result = _run_audit_logic(
            request.app.state, cid, user, "MANUAL",
            force=body.force, notes=body.notes or ""
        )
        return {"success": True, "data": result, "message": "تم إغلاق اليوم بنجاح"}
    except ValueError as e:
        raise HTTPException(409, str(e))
    except Exception as e:
        log.error("run_manual_audit: %s", e)
        raise HTTPException(500, "فشل تشغيل Night Audit")


@router.get("/history")
async def get_audit_history(
    request: Request,
    page: int = 1,
    per_page: int = 30,
    session=Depends(_require_client),
):
    db     = request.app.state.db
    cid    = session["client_id"]
    limit  = min(per_page, 100)
    offset = (page - 1) * limit

    if db.use_postgres:
        try:
            rows = db.execute("""
                SELECT * FROM night_audit_log
                WHERE client_id=%s
                ORDER BY audit_date DESC
                LIMIT %s OFFSET %s
            """, (cid, limit, offset), fetch="all")
            total_row = db.execute(
                "SELECT COUNT(*) AS n FROM night_audit_log WHERE client_id=%s",
                (cid,), fetch="one"
            )
            items = [dict(r) for r in (rows or [])]
            total = total_row["n"] if total_row else 0
            # تحويل الـ report_data من string إلى dict
            for item in items:
                if isinstance(item.get("report_data"), str):
                    try:
                        item["report_data"] = json.loads(item["report_data"])
                    except Exception:
                        pass
            return {
                "success": True,
                "data": items,
                "meta": {"page": page, "per_page": limit, "total": total},
            }
        except Exception as e:
            log.error("get_audit_history: %s", e)
    return {"success": True, "data": [], "meta": {"total": 0}}


@router.get("/{audit_date}/report")
async def get_audit_report(
    audit_date: str,
    request: Request,
    session=Depends(_require_client),
):
    db  = request.app.state.db
    cid = session["client_id"]

    if db.use_postgres:
        try:
            row = db.execute(
                "SELECT * FROM night_audit_log WHERE client_id=%s AND audit_date=%s",
                (cid, audit_date), fetch="one"
            )
            if not row:
                raise HTTPException(404, f"لا يوجد تقرير لتاريخ {audit_date}")
            data = dict(row)
            if isinstance(data.get("report_data"), str):
                try:
                    data["report_data"] = json.loads(data["report_data"])
                except Exception:
                    pass
            return {"success": True, "data": data}
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(500, str(e))
    raise HTTPException(404, "غير متاح في وضع JSON")


# ── Payment Devices ───────────────────────────────────────────────────────────

@router.get("/payment-devices")
async def list_payment_devices(request: Request, session=Depends(_require_client)):
    db  = request.app.state.db
    cid = session["client_id"]
    if db.use_postgres:
        try:
            rows = db.execute(
                "SELECT * FROM payment_devices WHERE client_id=%s AND is_deleted=FALSE ORDER BY created_at",
                (cid,), fetch="all"
            )
            return {"success": True, "data": [dict(r) for r in (rows or [])]}
        except Exception as e:
            log.error("list_payment_devices: %s", e)
    return {"success": True, "data": []}


@router.post("/payment-devices")
async def add_payment_device(
    body: PaymentDeviceSchema,
    request: Request,
    session=Depends(_require_client),
):
    _require_manager(session)
    db  = request.app.state.db
    cid = session["client_id"]
    if db.use_postgres:
        try:
            row = db.execute("""
                INSERT INTO payment_devices
                    (client_id, device_name, device_type, serial_number)
                VALUES (%s,%s,%s,%s)
                RETURNING *
            """, (cid, body.device_name, body.device_type, body.serial_number),
            fetch="one")
            return {"success": True, "data": dict(row) if row else {}, "message": "تم إضافة جهاز الدفع"}
        except Exception as e:
            raise HTTPException(500, f"خطأ: {e}")
    raise HTTPException(400, "يتطلب PostgreSQL")


@router.patch("/payment-devices/{device_id}")
async def rename_payment_device(
    device_id: int,
    body: RenameDeviceSchema,
    request: Request,
    session=Depends(_require_client),
):
    """إعادة تسمية جهاز الدفع أو تعديل نوعه ورقمه — لا يمسّ رصيده اليومي."""
    _require_manager(session)
    db  = request.app.state.db
    cid = session["client_id"]
    fields, params = [], []
    if body.device_name is not None:
        fields.append("device_name=%s"); params.append(body.device_name)  # noqa: E702
    if body.device_type is not None:
        fields.append("device_type=%s"); params.append(body.device_type)  # noqa: E702
    if body.serial_number is not None:
        fields.append("serial_number=%s"); params.append(body.serial_number)  # noqa: E702
    if not fields:
        raise HTTPException(400, "لا حقول للتعديل")
    if db.use_postgres:
        try:
            params += [device_id, cid]
            row = db.execute(
                f"UPDATE payment_devices SET {', '.join(fields)} "
                "WHERE id=%s AND client_id=%s AND is_deleted=FALSE RETURNING *",
                tuple(params), fetch="one")
            if not row:
                raise HTTPException(404, "الجهاز غير موجود")
            return {"success": True, "data": dict(row), "message": "تم تحديث الجهاز"}
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(500, str(e))
    raise HTTPException(400, "يتطلب PostgreSQL")


@router.patch("/payment-devices/{device_id}/settle")
async def settle_device(
    device_id: int,
    body: SettleDeviceSchema,
    request: Request,
    session=Depends(_require_client),
):
    _require_manager(session)
    db  = request.app.state.db
    cid = session["client_id"]
    if db.use_postgres:
        try:
            db.execute("""
                UPDATE payment_devices
                SET last_settled_at=NOW(), daily_total=0
                WHERE id=%s AND client_id=%s
            """, (device_id, cid))
            return {"success": True, "message": "تم إغلاق الجهاز وتصفير الرصيد"}
        except Exception as e:
            raise HTTPException(500, str(e))
    raise HTTPException(400, "يتطلب PostgreSQL")


@router.delete("/payment-devices/{device_id}")
async def delete_payment_device(
    device_id: int,
    request: Request,
    session=Depends(_require_client),
):
    _require_manager(session)
    db  = request.app.state.db
    cid = session["client_id"]
    if db.use_postgres:
        db.execute(
            "UPDATE payment_devices SET is_deleted=TRUE WHERE id=%s AND client_id=%s",
            (device_id, cid)
        )
    return {"success": True, "message": "تم حذف الجهاز"}
