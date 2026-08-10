#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
routes/auth.py — دخول المنشأة وتسجيلها
مُستخرَج ضمن تقسيم ملف المسارات الكبير لتسهيل الصيانة.
"""
from datetime import datetime, timedelta

from fastapi import APIRouter, Request
from fastapi.responses import (
    HTMLResponse, JSONResponse, RedirectResponse,
)

from app_core import (
    log, _lock, _client_sessions,
    _COOKIE_SECURE, _reg_rate_ok, _login_rate_ok,
    _new_token, _make_password, _verify_password, _get_client_token,
)
from html_pages import (
    _login_page,
)

router = APIRouter()

# ──────────────────────────────────────────────────────────────
#  Client Auth
# ──────────────────────────────────────────────────────────────
@router.post("/api/login")
async def client_login(request: Request):
    form = await request.form()
    client_id = str(form.get("client_id", "")).strip()
    password = str(form.get("password", "")).strip()

    # Rate-limit: block IPs that exceed LOGIN_MAX_PER_MINUTE attempts per minute
    client_ip = (request.client.host if request.client else "?")
    if not _login_rate_ok(client_ip):
        return HTMLResponse(_login_page("محاولات تسجيل دخول كثيرة — حاول لاحقاً"), status_code=429)

    if not client_id or not password:
        return HTMLResponse(_login_page("معرف المنشأة وكلمة المرور مطلوبان"), status_code=400)

    cfg = request.app.state.cfg
    store = request.app.state.store
    client = store.get_client(client_id)

    if not client:
        return HTMLResponse(_login_page("المنشأة غير موجودة"), status_code=401)

    if not _verify_password(password, client, cfg):
        return HTMLResponse(_login_page("كلمة المرور خاطئة"), status_code=401)

    token = _new_token()
    session_data = {
        "client_id": client_id,
        "created_at": datetime.now().isoformat(),
        # صاحب المنشأة — الدور الذي تفحصه db.security.check_permission.
        # بدونه يُرفض المالكُ نفسه عن كل مسار محكوم بصلاحية.
        "role": "owner",
        "permissions": ["*"],
    }
    with _lock:
        _client_sessions[token] = session_data
    # Persist session to PostgreSQL when available
    try:
        db = request.app.state.db
        if db.use_postgres:
            ip = request.client.host if request.client else ""
            ua = request.headers.get("user-agent", "")[:200]
            expires = datetime.now() + timedelta(days=7)
            db.execute(
                """INSERT INTO client_sessions (token, client_id, expires_at, ip_address, user_agent)
                   VALUES (%s, %s, %s, %s, %s)
                   ON CONFLICT (token) DO NOTHING""",
                (token, client_id, expires.isoformat(), ip, ua)
            )
    except Exception as _e:
        log.debug(f"session persist skipped: {_e}")

    response = RedirectResponse("/", status_code=303)
    response.set_cookie("client_token", token, httponly=True, samesite="lax", secure=_COOKIE_SECURE, max_age=86400 * 7)
    return response


@router.get("/api/logout")
@router.post("/api/logout")
async def client_logout(request: Request):
    token = _get_client_token(request)
    if token:
        session = None
        with _lock:
            session = _client_sessions.pop(token, None)
        # Remove from PostgreSQL sessions table
        try:
            db = request.app.state.db
            if db.use_postgres:
                db.execute("DELETE FROM client_sessions WHERE token=%s", (token,))
        except Exception:
            pass
        # Finding #8: persist revocation so other servers/restarts honor it
        try:
            from db.security import revoke_token
            db = request.app.state.db
            cid = (session or {}).get("client_id", "")
            revoke_token(db, token, cid, reason="logout")
        except Exception:
            pass
    response = RedirectResponse("/login", status_code=303)
    response.delete_cookie("client_token")
    return response


# ──────────────────────────────────────────────────────────────
#  Client registration
# ──────────────────────────────────────────────────────────────
@router.post("/api/client/register")
async def client_register(request: Request):
    body = await request.json()
    hotel_name = str(body.get("hotel_name", body.get("name", ""))).strip()
    client_id = str(body.get("client_id", body.get("id", ""))).strip()
    password = str(body.get("password", "")).strip()
    activation_key = str(body.get("activation_key", body.get("key", ""))).strip().upper()

    # بيانات التسجيل: الاسم + الجوال + السجل التجاري + المدينة + البريد الإلكتروني
    reg_phone = str(body.get("phone", "")).strip()
    reg_email = str(body.get("email", "")).strip()
    reg_city = str(body.get("city", "")).strip()
    reg_cr = str(body.get("cr_number", body.get("cr", ""))).strip()

    if not hotel_name or not password:
        return JSONResponse({"success": False, "error": "اسم المنشأة وكلمة المرور مطلوبان"}, status_code=400)
    # توليد معرّف رقمي تلقائي (8 أرقام) — فريد ولا يتكرر
    if not client_id:
        import random as _rnd
        client_id = str(_rnd.randint(10000000, 99999999))

    # M3 mitigation: حدّ معدّل التسجيل لكل IP
    client_ip = (request.client.host if request.client else "?")
    if not _reg_rate_ok(client_ip):
        return JSONResponse(
            {"success": False, "error": "محاولات تسجيل كثيرة — حاول لاحقاً"},
            status_code=429)

    cfg = request.app.state.cfg
    store = request.app.state.store

    # Validate activation key if provided
    plan = "trial"
    days = 30
    if activation_key:
        data = store.get_admin_data()
        key_obj = next((k for k in data.get("activation_keys", []) if k.get("key") == activation_key and not k.get("used")), None)
        if key_obj:
            plan = key_obj.get("plan", "trial")
            days = int(key_obj.get("days", 30))
            key_obj["used"] = True
            key_obj["used_by"] = client_id
            store.save_admin_data(data)

    existing = store.get_client(client_id)
    if existing:
        return JSONResponse({"success": False, "error": "معرّف المنشأة مستخدم بالفعل"}, status_code=400)

    pass_hash, pass_salt = _make_password(password)
    client = {
        "id": client_id,
        "name": hotel_name,
        "hotel_name": hotel_name,
        "plan": plan,
        "status": "trial",
        "pass_hash": pass_hash,
        "pass_salt": pass_salt,
        "phone": reg_phone,
        "email": reg_email,
        "city": reg_city,
        "trial_end": (datetime.now() + timedelta(days=days)).isoformat(),
        "created_at": datetime.now().isoformat(),
        "settings": {},
        # السجل التجاري يُحفظ في invoice_settings (يُستخدم في الفواتير لاحقاً)
        "invoice_settings": {"cr_number": reg_cr} if reg_cr else {},
    }
    store.save_client(client)

    # تسجيل إحالة المسوق إن وُجدت
    ref_code = str(body.get("ref_code", "")).strip().upper()
    if ref_code:
        db = request.app.state.db
        if db.use_postgres:
            try:
                row = db.execute(
                    "SELECT id FROM marketers WHERE ref_code=%s AND status='active'",
                    (ref_code,), fetch="one"
                )
                if row:
                    db.execute(
                        """INSERT INTO marketer_referrals (marketer_id,client_id,plan,ref_code)
                           VALUES (%s,%s,%s,%s) ON CONFLICT DO NOTHING""",
                        (row["id"], client_id, plan, ref_code)
                    )
            except Exception as e:
                log.warning(f"ref tracking: {e}")

    token = _new_token()
    with _lock:
        _client_sessions[token] = {
            "client_id": client_id,
            "created_at": datetime.now().isoformat(),
            "role": "owner",
            "permissions": ["*"],
        }

    # إرسال المعرّف الرقمي عبر البريد الإلكتروني
    if reg_email:
        try:
            from services.mailer import send_registration_email
            cfg = request.app.state.cfg
            send_registration_email(cfg, reg_email, hotel_name, client_id)
        except Exception as _mail_err:
            log.warning(f"register email failed: {_mail_err}")

    response = JSONResponse({"success": True, "ok": True, "client_id": client_id})
    response.set_cookie("client_token", token, httponly=True, samesite="lax", secure=_COOKIE_SECURE, max_age=86400 * 7)
    return response


