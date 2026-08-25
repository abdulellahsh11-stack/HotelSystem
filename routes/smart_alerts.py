#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
routes/smart_alerts.py — إنذارات المفتاح الذكي ورصيد الرسائل

كانت لوحة الإنذارات واجهةً بلا خادم: `ALARMS = []` تُقرأ ولا تُملأ،
فتُعرض فارغةً دائماً. هذا خادمها.

التبليغ يذهب إلى **صاحب المنشأة أو مديرها العام** — لا إلى كل موظف:
الإنذار الأمني قرارٌ إداري، وإغراق الجميع به يجعله ضجيجاً يُتجاهَل.
"""
from __future__ import annotations

from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Request

from app_core import log, require_client
from db.schema_alerts import (
    ALERT_LABELS, ALERT_STATUSES, ALERT_TYPES, CHANNELS,
    SEVERITIES, SEVERITY_LABELS,
)

router = APIRouter(prefix="/api/m09", tags=["Smart Alerts"])


def _db(request: Request):
    db = request.app.state.db
    if not getattr(db, "use_postgres", False):
        raise HTTPException(status_code=503, detail="قاعدة البيانات غير متاحة")
    return db


def _require(session: dict, permission: str) -> None:
    from db.security import check_permission

    if not check_permission(session, permission):
        raise HTTPException(status_code=403, detail=f"الصلاحية '{permission}' مطلوبة")


def _row(r: dict) -> dict:
    out = dict(r)
    out["type_label"] = ALERT_LABELS.get(out.get("alert_type"), out.get("alert_type"))
    out["severity_label"] = SEVERITY_LABELS.get(out.get("severity"), out.get("severity"))
    for key in ("created_at", "resolved_at", "snoozed_until"):
        if out.get(key) is not None:
            out[key] = str(out[key])
    return out


def _recipients(request: Request, client_id: str) -> dict:
    """
    وجهات التبليغ من إعدادات المنشأة.

    تُقرأ من `settings.alerts` إن ضُبطت، وإلا فبريد المنشأة المسجَّل.
    لا تُقرأ من جسم الطلب: من يُبلَّغ قرارُ إعدادٍ لا قرارُ نداء.
    """
    store = getattr(request.app.state, "store", None)
    client = (store.get_client(client_id) if store else None) or {}
    from db.store import public_settings

    prefs = (public_settings(client).get("alerts") or {})
    return {
        "email": prefs.get("email") or client.get("email") or "",
        "whatsapp": prefs.get("whatsapp") or client.get("phone") or "",
        "sms": prefs.get("sms") or client.get("phone") or "",
    }


# ── الإنذارات ──────────────────────────────────────────────────
@router.get("/alerts")
async def list_alerts(request: Request, status: str = "",
                      session=Depends(require_client)):
    """قائمة الإنذارات مع عدّادات الخطورة التي تعرضها اللوحة."""
    _require(session, "rooms.read")
    cid = session["client_id"]
    conditions = ["client_id=%s"]
    params: list = [cid]
    if status:
        if status not in ALERT_STATUSES:
            raise HTTPException(status_code=400, detail="حالة غير معروفة")
        conditions.append("status=%s")
        params.append(status)

    rows = _db(request).execute(
        f"SELECT * FROM smart_alerts WHERE {' AND '.join(conditions)} "
        f"ORDER BY created_at DESC LIMIT 200",
        tuple(params), fetch="all",
    ) or []
    items = [_row(dict(r)) for r in rows]

    counts = {s: sum(1 for i in items if i["status"] == s) for s in ALERT_STATUSES}
    by_severity = {
        s: sum(1 for i in items if i["severity"] == s and i["status"] == "active")
        for s in SEVERITIES
    }
    return {"success": True,
            "data": {"alerts": items, "counts": counts, "by_severity": by_severity}}


@router.post("/alerts")
async def create_alert(request: Request, session=Depends(require_client)):
    """
    يُسجّل إنذاراً ويُبلّغ عنه فوراً.

    التبليغ جزءٌ من الإنشاء لا خطوة تالية: إنذارٌ يُسجَّل ولا يُبلَّغ
    عنه يساوي عدمه.
    """
    _require(session, "rooms.write")
    data = await request.json()
    db = _db(request)
    cid = session["client_id"]

    alert_type = str(data.get("alert_type") or "").strip()
    if alert_type not in ALERT_TYPES:
        raise HTTPException(status_code=400,
                            detail=f"نوع غير معروف. المسموح: {'، '.join(ALERT_TYPES)}")
    severity = str(data.get("severity") or "medium").strip()
    if severity not in SEVERITIES:
        raise HTTPException(status_code=400, detail="مستوى خطورة غير معروف")
    title = str(data.get("title") or ALERT_LABELS[alert_type]).strip()[:200]

    row = db.execute(
        """INSERT INTO smart_alerts
               (client_id, alert_type, severity, room_number, lock_id, title, message)
           VALUES (%s,%s,%s,%s,%s,%s,%s)
           RETURNING id, client_id, alert_type, severity, room_number, title, message""",
        (cid, alert_type, severity,
         str(data.get("room_number") or "").strip()[:20] or None,
         str(data.get("lock_id") or "").strip()[:60] or None,
         title, str(data.get("message") or "").strip()[:1000]),
        fetch="one",
    )
    alert = dict(row) if row else {"client_id": cid, "title": title, "severity": severity}

    channels = [c for c in (data.get("channels") or CHANNELS) if c in CHANNELS]
    deliveries = []
    try:
        from services.alert_notifier import notify

        deliveries = notify(db, request.app.state.cfg, alert,
                            _recipients(request, cid), channels)
    except Exception as exc:
        # الإنذار مُسجَّل بالفعل؛ فشل التبليغ لا يُلغيه بل يُسجَّل معه
        log.error("تعذّر تبليغ الإنذار %s: %s", alert.get("id"), exc, exc_info=True)

    return {"success": True, "data": _row(alert), "deliveries": deliveries}


@router.patch("/alerts/{alert_id}")
async def update_alert(alert_id: int, request: Request,
                       session=Depends(require_client)):
    """يُعلّم الإنذار محلولاً أو يؤجّله."""
    _require(session, "rooms.write")
    data = await request.json()
    db = _db(request)
    cid = session["client_id"]

    status = str(data.get("status") or "").strip()
    if status not in ALERT_STATUSES:
        raise HTTPException(status_code=400, detail="حالة غير معروفة")
    if not db.execute("SELECT id FROM smart_alerts WHERE id=%s AND client_id=%s",
                      (alert_id, cid), fetch="one"):
        raise HTTPException(status_code=404, detail="الإنذار غير موجود")

    if status == "resolved":
        db.execute(
            """UPDATE smart_alerts SET status='resolved', resolved_at=NOW(),
                                       resolved_by=%s
               WHERE id=%s AND client_id=%s""",
            (session.get("username") or "owner", alert_id, cid))
    elif status == "snoozed":
        minutes = max(5, min(int(data.get("minutes") or 60), 1440))
        db.execute(
            """UPDATE smart_alerts SET status='snoozed', snoozed_until=%s
               WHERE id=%s AND client_id=%s""",
            (datetime.now() + timedelta(minutes=minutes), alert_id, cid))
    else:
        db.execute(
            """UPDATE smart_alerts SET status='active', resolved_at=NULL,
                                       snoozed_until=NULL
               WHERE id=%s AND client_id=%s""", (alert_id, cid))
    return {"success": True}


@router.get("/alerts/{alert_id}/deliveries")
async def alert_deliveries(alert_id: int, request: Request,
                           session=Depends(require_client)):
    """سجلّ محاولات التبليغ — أي قناة وصلت وأيّها فشلت ولماذا."""
    _require(session, "rooms.read")
    rows = _db(request).execute(
        """SELECT channel, recipient, status, error, sent_at
           FROM alert_deliveries WHERE client_id=%s AND alert_id=%s
           ORDER BY sent_at""",
        (session["client_id"], alert_id), fetch="all") or []
    return {"success": True,
            "data": [{**dict(r), "sent_at": str(r["sent_at"])} for r in rows]}


# ── رصيد الرسائل النصية ────────────────────────────────────────
@router.get("/sms-credit")
async def sms_balance(request: Request, session=Depends(require_client)):
    """الرصيد وآخر حركاته."""
    _require(session, "settings")
    from services.alert_notifier import get_balance

    db = _db(request)
    cid = session["client_id"]
    rows = db.execute(
        """SELECT delta, reason, balance_after, created_at, created_by
           FROM sms_credit_log WHERE client_id=%s
           ORDER BY created_at DESC LIMIT 30""", (cid,), fetch="all") or []
    return {
        "success": True,
        "data": {
            "balance": get_balance(db, cid),
            "history": [{**dict(r), "created_at": str(r["created_at"])} for r in rows],
        },
    }


@router.post("/sms-credit/topup")
async def topup_sms(request: Request, session=Depends(require_client)):
    """
    يشحن رصيد الرسائل.

    لا يُحصّل مالاً: بوابة الدفع غير موصولة بعد. حتى تُوصل، يبقى الشحن
    إجراءً إدارياً يُسجَّل باسم فاعله — وتسجيلُه أهون من رصيدٍ يتغيّر
    بلا أثر.
    """
    _require(session, "settings")
    data = await request.json()
    try:
        amount = int(data.get("amount") or 0)
    except (TypeError, ValueError):
        raise HTTPException(status_code=400, detail="الكمية يجب أن تكون رقماً") from None
    if not 1 <= amount <= 100_000:
        raise HTTPException(status_code=400, detail="الكمية بين ١ و١٠٠٠٠٠ رسالة")

    from services.alert_notifier import add_credit

    balance = add_credit(_db(request), session["client_id"], amount,
                         str(data.get("reason") or "شحن يدوي")[:100],
                         session.get("username") or "owner")
    log.info("شُحن رصيد %s رسالة للمنشأة %s", amount, session["client_id"])
    return {"success": True, "data": {"balance": balance, "added": amount}}
