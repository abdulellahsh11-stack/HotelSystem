#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
main2.py — جميع الـ API routes
يستورد app والمتغيرات المشتركة من main1، وصفحات HTML من html_pages
"""
import json
import os
import secrets
import threading
from datetime import datetime, date, timedelta
from typing import Optional

from fastapi import Depends, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse, PlainTextResponse, RedirectResponse, Response

from main1 import (
    app, log, _SafeEncoder,
    _lock, _admin_sessions, _client_sessions,
    _COOKIE_SECURE, _reg_rate_ok, _login_rate_ok,
    _new_token, _make_password, _verify_password, _hash_password,
    get_client_session, require_client, require_admin,
    _get_admin_token, _get_client_token,
)
from html_pages import (
    _login_page, _admin_login_page, _admin_dashboard, _client_dashboard,
)

# ──────────────────────────────────────────────────────────────
#  Public routes
# ──────────────────────────────────────────────────────────────
@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    # App launcher — all 14 modules visible immediately
    launcher = os.path.join("static", "dheuof", "index.html")
    if os.path.exists(launcher):
        with open(launcher, encoding="utf-8") as f:
            return HTMLResponse(f.read())
    return HTMLResponse(_login_page())


@app.get("/app", response_class=HTMLResponse)
async def dheuof_app(request: Request):
    # Same launcher (kept for backwards compatibility)
    launcher = os.path.join("static", "dheuof", "index.html")
    if os.path.exists(launcher):
        with open(launcher, encoding="utf-8") as f:
            return HTMLResponse(f.read())
    return HTMLResponse(_login_page())


# ──────────────────────────────────────────────────────────────
#  PWA — installable on iOS / Android / Browser (root scope)
# ──────────────────────────────────────────────────────────────
@app.get("/manifest.json")
async def pwa_manifest():
    path = os.path.join("static", "dheuof", "manifest.json")
    if os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            return Response(content=f.read(), media_type="application/manifest+json")
    return Response(status_code=404)


@app.get("/sw.js")
async def pwa_service_worker():
    path = os.path.join("static", "dheuof", "sw.js")
    if os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            # Service-Worker-Allowed lets the worker control the whole site (root scope)
            return Response(
                content=f.read(),
                media_type="application/javascript",
                headers={"Service-Worker-Allowed": "/", "Cache-Control": "no-cache"},
            )
    return Response(status_code=404)


@app.get("/marketing", response_class=HTMLResponse)
async def marketing_page(request: Request):
    # Marketing landing page
    landing = os.path.join("static", "dheuof", "website", "index.html")
    if os.path.exists(landing):
        with open(landing, encoding="utf-8") as f:
            return HTMLResponse(f.read())
    return HTMLResponse(_login_page())


@app.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    # Already authenticated → go straight to the app
    if get_client_session(request) is not None:
        return RedirectResponse("/", status_code=302)
    ref = request.query_params.get("ref", "")
    return HTMLResponse(_login_page(ref_code=ref))


@app.get("/admin", response_class=HTMLResponse)
async def admin_page(request: Request):
    token = _get_admin_token(request)
    with _lock:
        is_auth = token and token in _admin_sessions
    if not is_auth:
        return HTMLResponse(_admin_login_page())

    return HTMLResponse(_admin_dashboard([], {}))


@app.get("/guests", response_class=HTMLResponse)
async def guests_page(request: Request):
    session = get_client_session(request)
    if not session:
        return RedirectResponse("/login")
    store: "DataStore" = request.app.state.store
    client = store.get_client(session["client_id"]) or {"id": session["client_id"]}
    return HTMLResponse(_client_dashboard(client))


@app.get("/bookings", response_class=HTMLResponse)
async def bookings_page(request: Request):
    session = get_client_session(request)
    if not session:
        return RedirectResponse("/login")
    store: "DataStore" = request.app.state.store
    client = store.get_client(session["client_id"]) or {"id": session["client_id"]}
    return HTMLResponse(_client_dashboard(client))


# ──────────────────────────────────────────────────────────────
#  Module shortcut routes — dheuof.com/hr, /accounting, etc.
# ──────────────────────────────────────────────────────────────
def _serve_module(path: str) -> HTMLResponse:
    full = os.path.join("static", "dheuof", "modules", path, "index.html")
    if os.path.exists(full):
        with open(full, encoding="utf-8") as f:
            return HTMLResponse(f.read())
    return RedirectResponse("/")

@app.get("/static/dheuof/modules/01-guests/checkin.html")
async def redirect_checkin():
    return RedirectResponse("/static/dheuof/modules/01-guests/index.html", status_code=301)

@app.get("/dheuof",   response_class=HTMLResponse)
@app.get("/guests-module", response_class=HTMLResponse)
async def mod_guests():    return _serve_module("01-guests")

@app.get("/shumus",   response_class=HTMLResponse)
async def mod_shumus():    return _serve_module("02-shumus")

@app.get("/tourism",  response_class=HTMLResponse)
async def mod_tourism():   return _serve_module("03-tourism")

@app.get("/inventory",response_class=HTMLResponse)
async def mod_inv():       return _serve_module("04-inventory")

@app.get("/warehouse",response_class=HTMLResponse)
async def mod_wh():        return _serve_module("05-warehouse")

@app.get("/account",  response_class=HTMLResponse)
@app.get("/accounting",response_class=HTMLResponse)
async def mod_acc():       return _serve_module("06-accounting")

@app.get("/pos",      response_class=HTMLResponse)
async def mod_pos():       return _serve_module("07-pos")

@app.get("/key",      response_class=HTMLResponse)
@app.get("/smart-key",response_class=HTMLResponse)
async def mod_key():       return _serve_module("08-smart-key")

@app.get("/hr",       response_class=HTMLResponse)
async def mod_hr():        return _serve_module("09-hr")

@app.get("/channels", response_class=HTMLResponse)
@app.get("/marketing-channels", response_class=HTMLResponse)
async def mod_ch():        return _serve_module("10-channel-marketing")

@app.get("/analytics",response_class=HTMLResponse)
async def mod_an():        return _serve_module("12-analytics")

@app.get("/staff",    response_class=HTMLResponse)
async def mod_st():        return _serve_module("13-staff-tracker")

@app.get("/goals",    response_class=HTMLResponse)
async def mod_go():        return _serve_module("14-manager-goals")

@app.get("/ota-bookings",   response_class=HTMLResponse)
async def mod_bookings():  return _serve_module("17-bookings")

@app.get("/trips",          response_class=HTMLResponse)
@app.get("/tourism-trips",  response_class=HTMLResponse)
async def mod_trips():     return _serve_module("15-tourism-trips")


# ──────────────────────────────────────────────────────────────
#  Health & Status
# ──────────────────────────────────────────────────────────────
@app.get("/api/health")
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


@app.get("/api/status")
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


@app.get("/api/analytics/overview")
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
#  Admin Auth
# ──────────────────────────────────────────────────────────────
@app.post("/api/admin/login")
async def admin_login(request: Request):
    form = await request.form()
    password = form.get("password", "")
    cfg = request.app.state.cfg

    h = _hash_password(str(password), cfg.pass_salt)
    if h != cfg.admin_pass_hash:
        if request.headers.get("content-type", "").startswith("application/json"):
            return JSONResponse({"success": False, "error": "كلمة المرور خاطئة"}, status_code=401)
        return HTMLResponse(_admin_login_page("كلمة المرور خاطئة"), status_code=401)

    token = _new_token()
    with _lock:
        _admin_sessions[token] = {"created_at": datetime.now().isoformat()}

    response = RedirectResponse("/admin", status_code=303)
    response.set_cookie("admin_token", token, httponly=True, samesite="lax", max_age=86400)
    return response


@app.get("/api/admin/logout")
async def admin_logout(request: Request):
    # H3 fix: أبطل الرمز فعلياً على الخادم لا الكوكي فقط
    token = _get_admin_token(request)
    with _lock:
        _admin_sessions.pop(token, None)
    response = RedirectResponse("/admin", status_code=303)
    response.delete_cookie("admin_token")
    return response


@app.post("/api/admin/logout")
async def admin_logout_post(request: Request):
    token = _get_admin_token(request)
    with _lock:
        _admin_sessions.pop(token, None)
    response = JSONResponse({"success": True})
    response.delete_cookie("admin_token")
    return response


# ──────────────────────────────────────────────────────────────
#  Admin — Stats & Clients
# ──────────────────────────────────────────────────────────────
@app.get("/api/admin/clients")
async def admin_clients(request: Request, _=Depends(require_admin)):
    cfg = request.app.state.cfg
    store: "DataStore" = request.app.state.store
    clients = store.get_all_clients()
    owner_id = getattr(cfg, "owner_client_id", "") or ""
    for c in clients:
        c.setdefault("sub_end", c.get("subscription_expires", c.get("trial_end", "")))
        c.setdefault("sub_start", "")
        c.setdefault("sub_price", 0)
        c["is_owner"] = (str(c.get("id", "")) == owner_id)
    return {"success": True, "clients": clients}


@app.post("/api/admin/clients")
async def admin_create_client(request: Request, _=Depends(require_admin)):
    data = await request.json()
    client_id = str(data.get("id", "")).strip()
    name = str(data.get("name", "")).strip()
    password = str(data.get("password", "")).strip()
    plan = str(data.get("plan", "starter")).strip()
    email = str(data.get("email", "")).strip()

    if not all([client_id, name, password]):
        return JSONResponse({"success": False, "error": "id و name و password مطلوبة"}, status_code=400)

    cfg = request.app.state.cfg
    store: "DataStore" = request.app.state.store

    existing = store.get_client(client_id)
    if existing:
        return JSONResponse({"success": False, "error": "المعرف مستخدم بالفعل"}, status_code=400)

    pass_hash, pass_salt = _make_password(password)
    sub_end = (datetime.now() + timedelta(days=30)).strftime("%Y-%m-%d")
    client = {
        "id": client_id,
        "name": name,
        "hotel_name": name,
        "email": email,
        "plan": plan,
        "status": "trial",
        "pass_hash": pass_hash,
        "pass_salt": pass_salt,
        "sub_end": sub_end,
        "sub_start": datetime.now().strftime("%Y-%m-%d"),
        "sub_price": 0,
        "created_at": datetime.now().isoformat(),
        "settings": {},
    }
    store.save_client(client)
    return JSONResponse({"success": True, "client": client})


@app.post("/api/admin/owner-setup")
async def admin_owner_setup(request: Request, _=Depends(require_admin)):
    """إنشاء أو تحديث حساب المالك — enterprise مدى الحياة"""
    data = await request.json()
    client_id = str(data.get("client_id", "")).strip()
    name = str(data.get("name", "")).strip()
    password = str(data.get("password", "")).strip()
    email = str(data.get("email", "")).strip()

    if not all([client_id, name, password]):
        return JSONResponse({"success": False, "error": "client_id و name و password مطلوبة"}, status_code=400)

    cfg = request.app.state.cfg
    store: "DataStore" = request.app.state.store

    pass_hash, pass_salt = _make_password(password)
    sub_end = (datetime.now() + timedelta(days=36500)).strftime("%Y-%m-%d")  # 100 years
    client = store.get_client(client_id) or {}
    client.update({
        "id": client_id,
        "name": name,
        "hotel_name": name,
        "email": email,
        "plan": "enterprise",
        "status": "active",
        "pass_hash": pass_hash,
        "pass_salt": pass_salt,
        "sub_end": sub_end,
        "sub_start": datetime.now().strftime("%Y-%m-%d"),
        "sub_price": 0,
        "is_owner_account": True,
        "settings": client.get("settings", {}),
        "created_at": client.get("created_at", datetime.now().isoformat()),
    })
    store.save_client(client)

    # persist owner_client_id to cfg so the flag shows up immediately
    cfg.owner_client_id = client_id
    log.info(f"Owner account set: {client_id} ({email})")
    return JSONResponse({"success": True, "client_id": client_id, "sub_end": sub_end})


@app.get("/api/admin/clients/{client_id}")
async def admin_get_client(client_id: str, request: Request, _=Depends(require_admin)):
    store: "DataStore" = request.app.state.store
    client = store.get_client(client_id)
    if not client:
        raise HTTPException(status_code=404, detail="المنشأة غير موجودة")
    return {"success": True, "client": client}


@app.put("/api/admin/clients/{client_id}")
async def admin_update_client(client_id: str, request: Request, _=Depends(require_admin)):
    store: "DataStore" = request.app.state.store
    client = store.get_client(client_id)
    if not client:
        raise HTTPException(status_code=404, detail="المنشأة غير موجودة")
    data = await request.json()
    for k in ["name", "hotel_name", "plan", "status", "subscription_expires", "settings"]:
        if k in data:
            client[k] = data[k]
    if "password" in data and data["password"]:
        cfg = request.app.state.cfg
        client["pass_hash"] = _hash_password(str(data["password"]), cfg.pass_salt)
    store.save_client(client)
    return {"success": True, "client": client}


@app.delete("/api/admin/clients/{client_id}")
async def admin_delete_client(client_id: str, request: Request, _=Depends(require_admin)):
    store: "DataStore" = request.app.state.store
    store.delete_client(client_id)
    return {"success": True}


# ──────────────────────────────────────────────────────────────
#  Client Auth
# ──────────────────────────────────────────────────────────────
@app.post("/api/login")
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
    store: "DataStore" = request.app.state.store
    client = store.get_client(client_id)

    if not client:
        return HTMLResponse(_login_page("المنشأة غير موجودة"), status_code=401)

    if not _verify_password(password, client, cfg):
        return HTMLResponse(_login_page("كلمة المرور خاطئة"), status_code=401)

    token = _new_token()
    session_data = {
        "client_id": client_id,
        "created_at": datetime.now().isoformat(),
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


@app.get("/api/logout")
@app.post("/api/logout")
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
#  Guests
# ──────────────────────────────────────────────────────────────
@app.get("/api/guests")
async def get_guests(request: Request, limit: int = 100, session=Depends(require_client)):
    store: "DataStore" = request.app.state.store
    guests = store.get_guests(session["client_id"])
    return {"success": True, "data": guests[:limit]}


@app.post("/api/guests")
async def save_guest(request: Request, session=Depends(require_client)):
    data = await request.json()
    store: "DataStore" = request.app.state.store
    if not data.get("id"):
        data["id"] = secrets.token_hex(8)
    data["client_id"] = session["client_id"]
    data.setdefault("created_at", datetime.now().isoformat())
    guest = store.save_guest(session["client_id"], data)
    return {"success": True, "data": guest}


@app.get("/api/guests/{guest_id}")
async def get_guest(guest_id: str, request: Request, session=Depends(require_client)):
    store: "DataStore" = request.app.state.store
    guests = store.get_guests(session["client_id"])
    guest = next((g for g in guests if str(g.get("id")) == guest_id), None)
    if not guest:
        raise HTTPException(status_code=404, detail="الضيف غير موجود")
    return {"success": True, "data": guest}


# ──────────────────────────────────────────────────────────────
#  Bookings
# ──────────────────────────────────────────────────────────────
@app.get("/api/bookings")
async def get_bookings(
    request: Request, status: Optional[str] = None, limit: int = 100,
    session=Depends(require_client)
):
    store: "DataStore" = request.app.state.store
    bookings = store.get_bookings(session["client_id"], status)
    return {"success": True, "data": bookings[:limit]}


@app.post("/api/bookings")
async def save_booking(request: Request, session=Depends(require_client)):
    data = await request.json()
    store: "DataStore" = request.app.state.store
    if not data.get("id"):
        data["id"] = secrets.token_hex(8)
    data["client_id"] = session["client_id"]
    data.setdefault("status", "confirmed")
    data.setdefault("created_at", datetime.now().isoformat())
    booking = store.save_booking(session["client_id"], data)
    return {"success": True, "data": booking}


@app.put("/api/bookings/{booking_id}")
async def update_booking(booking_id: str, request: Request, session=Depends(require_client)):
    data = await request.json()
    data["id"] = booking_id
    data["client_id"] = session["client_id"]
    store: "DataStore" = request.app.state.store
    booking = store.save_booking(session["client_id"], data)
    return {"success": True, "data": booking}


# ──────────────────────────────────────────────────────────────
#  Invoices
# ──────────────────────────────────────────────────────────────
@app.get("/api/invoices")
async def get_invoices(request: Request, limit: int = 100, session=Depends(require_client)):
    store: "DataStore" = request.app.state.store
    invoices = store.get_invoices(session["client_id"])
    return {"success": True, "data": invoices[:limit]}


@app.post("/api/invoices")
async def save_invoice(request: Request, session=Depends(require_client)):
    data = await request.json()
    store: "DataStore" = request.app.state.store
    cid = session["client_id"]
    if not data.get("id"):
        seq = store.get_next_invoice_seq(cid)
        data["id"] = f"INV-{seq:05d}"
    data["client_id"] = cid
    data.setdefault("created_at", datetime.now().isoformat())
    invoice = store.save_invoice(cid, data)
    return {"success": True, "data": invoice}


# ──────────────────────────────────────────────────────────────
#  POS Transactions
# ──────────────────────────────────────────────────────────────
@app.get("/api/pos")
async def get_pos(
    request: Request, date_from: Optional[str] = None, date_to: Optional[str] = None,
    session=Depends(require_client)
):
    store: "DataStore" = request.app.state.store
    txns = store.get_pos_transactions(session["client_id"], date_from, date_to)
    return {"success": True, "data": txns}


@app.post("/api/pos")
async def save_pos(request: Request, session=Depends(require_client)):
    data = await request.json()
    store: "DataStore" = request.app.state.store
    if not data.get("id"):
        data["id"] = secrets.token_hex(8)
    data["client_id"] = session["client_id"]
    data.setdefault("created_at", datetime.now().isoformat())
    tx = store.save_pos_transaction(session["client_id"], data)
    return {"success": True, "data": tx}


# ──────────────────────────────────────────────────────────────
#  Settings
# ──────────────────────────────────────────────────────────────
@app.get("/api/settings")
async def get_settings(request: Request, session=Depends(require_client)):
    store: "DataStore" = request.app.state.store
    client = store.get_client(session["client_id"]) or {}
    return {"success": True, "data": client.get("settings", {})}


@app.post("/api/settings")
async def save_settings(request: Request, session=Depends(require_client)):
    data = await request.json()
    store: "DataStore" = request.app.state.store
    cid = session["client_id"]
    client = store.get_client(cid) or {"id": cid}
    client["settings"] = data
    store.save_client(client)
    return {"success": True}


# ──────────────────────────────────────────────────────────────
#  Rooms
# ──────────────────────────────────────────────────────────────
@app.get("/api/rooms")
async def get_rooms(request: Request, session=Depends(require_client)):
    db = request.app.state.db
    cid = session["client_id"]
    try:
        rows = db.execute(
            "SELECT * FROM rooms WHERE client_id=%s ORDER BY room_number", (cid,), fetch="all"
        )
        return {"success": True, "data": [dict(r) for r in (rows or [])]}
    except Exception as e:
        return {"success": True, "data": [], "warning": str(e)}


@app.post("/api/rooms")
async def save_room(request: Request, session=Depends(require_client)):
    data = await request.json()
    db = request.app.state.db
    cid = session["client_id"]
    room_id = data.get("id")
    try:
        if room_id:
            db.execute(
                """UPDATE rooms SET room_number=%s,room_type=%s,floor=%s,
                   capacity=%s,base_price=%s,status=%s,updated_at=NOW()
                   WHERE id=%s AND client_id=%s""",
                (data.get("room_number"), data.get("room_type"), data.get("floor"),
                 data.get("capacity", 2), data.get("base_price", 0),
                 data.get("status", "available"), room_id, cid)
            )
        else:
            db.execute(
                """INSERT INTO rooms(client_id,room_number,room_type,floor,capacity,base_price,status)
                   VALUES(%s,%s,%s,%s,%s,%s,%s)""",
                (cid, data.get("room_number"), data.get("room_type", "standard"),
                 data.get("floor", 1), data.get("capacity", 2),
                 data.get("base_price", 0), data.get("status", "available"))
            )
        return {"success": True}
    except Exception as e:
        return JSONResponse({"success": False, "error": str(e)}, status_code=500)


# ──────────────────────────────────────────────────────────────
#  Channels — inline FastAPI routes
# ──────────────────────────────────────────────────────────────
@app.get("/api/channels/status/{client_id}")
async def channels_status(client_id: str, request: Request, session=Depends(require_client)):
    # Finding #2 BOLA fix: ignore path client_id — always use session's client_id
    cid = session["client_id"]
    channels = request.app.state.channels
    if not channels:
        return {"success": True, "data": {}}
    try:
        status = channels.get_status(cid)
        return {"success": True, "data": status}
    except Exception as e:
        return JSONResponse({"success": False, "error": str(e)}, status_code=500)


@app.post("/api/channels/booking-com/webhook")
async def booking_com_webhook(request: Request):
    channels = request.app.state.channels
    if not channels:
        return {"status": "ok"}
    body = await request.body()
    src_ip = request.client.host if request.client else ""

    def _process():
        try:
            ch = channels.get_channel("booking.com")
            if ch:
                ch.process_webhook(body.decode(), src_ip)
        except Exception as e:
            log.error(f"webhook processing: {e}")

    threading.Thread(target=_process, daemon=True).start()
    return {"status": "ok"}


@app.post("/api/channels/booking-com/settings")
async def booking_com_settings(request: Request, session=Depends(require_client)):
    data = await request.json()
    db = request.app.state.db
    cid = session["client_id"]
    try:
        creds = json.dumps({
            "hotel_id": data.get("hotel_id", ""),
            "api_key": data.get("api_key", ""),
            "username": data.get("username", ""),
        })
        db.execute(
            """INSERT INTO channel_configs(client_id,channel_name,credentials,is_enabled)
               VALUES(%s,'booking.com',%s,false)
               ON CONFLICT(client_id,channel_name)
               DO UPDATE SET credentials=EXCLUDED.credentials,updated_at=NOW()""",
            (cid, creds)
        )
        return {"success": True}
    except Exception as e:
        return JSONResponse({"success": False, "error": str(e)}, status_code=500)


@app.post("/api/channels/mawasim/settings")
async def mawasim_settings(request: Request, session=Depends(require_client)):
    data = await request.json()
    db = request.app.state.db
    cid = session["client_id"]
    ical_url = data.get("ical_url", "")
    if not ical_url:
        return JSONResponse({"success": False, "error": "رابط iCal مطلوب"}, status_code=400)
    try:
        creds = json.dumps({"ical_url": ical_url})
        db.execute(
            """INSERT INTO channel_configs(client_id,channel_name,credentials,is_enabled)
               VALUES(%s,'mawasim',%s,true)
               ON CONFLICT(client_id,channel_name)
               DO UPDATE SET credentials=EXCLUDED.credentials,is_enabled=true""",
            (cid, creds)
        )
        return {"success": True}
    except Exception as e:
        return JSONResponse({"success": False, "error": str(e)}, status_code=500)


@app.get("/api/channels/sync-log/{client_id}")
async def sync_log(client_id: str, request: Request, session=Depends(require_client)):
    # Finding #2 BOLA fix: always use session's client_id
    cid = session["client_id"]
    db = request.app.state.db
    try:
        rows = db.execute(
            "SELECT * FROM channel_sync_log WHERE client_id=%s ORDER BY created_at DESC LIMIT 50",
            (cid,), fetch="all"
        )
        return {"success": True, "data": [dict(r) for r in (rows or [])]}
    except Exception as e:
        return {"success": True, "data": [], "warning": str(e)}


@app.get("/api/channels/revenue-split/{client_id}")
async def revenue_split(client_id: str, request: Request, days: int = 30, session=Depends(require_client)):
    # Finding #2 BOLA fix: always use session's client_id
    cid = session["client_id"]
    channels = request.app.state.channels
    if not channels:
        return {"success": True, "data": {}}
    try:
        data = channels.get_revenue_split(cid, days)
        return {"success": True, "data": data}
    except Exception as e:
        return JSONResponse({"success": False, "error": str(e)}, status_code=500)


# ──────────────────────────────────────────────────────────────
#  Pricing — inline FastAPI routes
# ──────────────────────────────────────────────────────────────
@app.get("/api/pricing/rules/{client_id}")
async def get_pricing_rules(client_id: str, request: Request, room_id: Optional[int] = None, session=Depends(require_client)):
    # Finding #2 BOLA fix: always use session's client_id
    cid = session["client_id"]
    pricing = request.app.state.pricing
    if not pricing:
        return {"success": True, "data": []}
    try:
        if room_id:
            data = pricing.get_or_save_rules(cid, room_id)
        else:
            data = pricing._get_rooms_with_rules(cid)
        return {"success": True, "data": data}
    except Exception as e:
        return JSONResponse({"success": False, "error": str(e)}, status_code=500)


@app.post("/api/pricing/rules")
async def save_pricing_rules(request: Request, session=Depends(require_client)):
    data = await request.json()
    pricing = request.app.state.pricing
    if not pricing:
        return JSONResponse({"success": False, "error": "خدمة التسعير غير متاحة"}, status_code=503)
    # Finding #2 BOLA fix: never accept client_id from request body
    cid = session["client_id"]
    room_id = data.get("room_id")
    if not room_id:
        return JSONResponse({"success": False, "error": "room_id مطلوب"}, status_code=400)
    try:
        result = pricing.get_or_save_rules(cid, int(room_id), data)
        return result
    except Exception as e:
        return JSONResponse({"success": False, "error": str(e)}, status_code=500)


@app.get("/api/pricing/calendar/{client_id}")
async def pricing_calendar(client_id: str, request: Request, room_id: int = 0, days: int = 30, session=Depends(require_client)):
    # Finding #2 BOLA fix: always use session's client_id
    cid = session["client_id"]
    pricing = request.app.state.pricing
    if not pricing:
        return {"success": True, "data": []}
    if not room_id:
        return JSONResponse({"success": False, "error": "room_id مطلوب"}, status_code=400)
    try:
        data = pricing.get_pricing_calendar(cid, room_id, days)
        return {"success": True, "data": data}
    except Exception as e:
        return JSONResponse({"success": False, "error": str(e)}, status_code=500)


@app.post("/api/pricing/apply-now/{client_id}")
async def apply_pricing_now(client_id: str, request: Request, session=Depends(require_client)):
    pricing = request.app.state.pricing
    if not pricing:
        return JSONResponse({"success": False, "error": "خدمة التسعير غير متاحة"}, status_code=503)
    # H1 fix (BOLA): تجاهل معرّف المسار واستخدم معرّف الجلسة الموثَّق فقط
    cid = session["client_id"]
    try:
        result = pricing.apply_pricing_for_client(cid)
        return {"success": True, "data": result}
    except Exception as e:
        return JSONResponse({"success": False, "error": str(e)}, status_code=500)


@app.get("/api/pricing/seasons")
async def get_seasons(session=Depends(require_client)):
    try:
        from services.dynamic_pricing import SAUDI_SEASONS_2026
        seasons = [
            {
                "key": k,
                "label": v["label"],
                "start": v["start"].isoformat(),
                "end": v["end"].isoformat(),
                "factor": v["factor"],
            }
            for k, v in SAUDI_SEASONS_2026.items()
        ]
        return {"success": True, "data": sorted(seasons, key=lambda s: s["start"])}
    except Exception as e:
        return JSONResponse({"success": False, "error": str(e)}, status_code=500)


# ──────────────────────────────────────────────────────────────
#  KPI, Analytics, Notifications, Subscription
# ──────────────────────────────────────────────────────────────
@app.get("/api/kpi")
async def get_kpi(request: Request, session=Depends(require_client)):
    store: "DataStore" = request.app.state.store
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


@app.get("/api/analytics")
async def get_analytics(request: Request, session=Depends(require_client)):
    store: "DataStore" = request.app.state.store
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


@app.get("/api/notifications")
async def get_notifications(request: Request, session=Depends(require_client)):
    store: "DataStore" = request.app.state.store
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


@app.get("/api/subscription")
async def get_subscription(request: Request, session=Depends(require_client)):
    store: "DataStore" = request.app.state.store
    client = store.get_client(session["client_id"]) or {}
    return {"success": True, "subscription": {
        "plan": client.get("plan", "trial"),
        "status": client.get("status", "trial"),
        "trial_end": client.get("trial_end", client.get("subscription_expires")),
    }}


@app.get("/api/payment/plans")
async def get_plans():
    return {"success": True, "plans": [
        {"id": "trial", "name": "تجربة مجانية", "price": 0, "duration": 30, "modules": ["M01", "M02"]},
        {"id": "starter", "name": "Starter", "price": 599, "duration": 30, "modules": ["M01", "M02", "M07"]},
        {"id": "operations", "name": "Operations", "price": 1099, "duration": 30, "modules": ["M01", "M02", "M05", "M07", "M08", "M13"]},
        {"id": "professional", "name": "Professional", "price": 2299, "duration": 30, "modules": ["M01", "M02", "M03", "M04", "M05", "M06", "M07", "M08", "M11", "M13"]},
        {"id": "enterprise", "name": "Enterprise", "price": None, "duration": 30, "modules": "all"},
    ]}


# ──────────────────────────────────────────────────────────────
#  Admin extended endpoints
# ──────────────────────────────────────────────────────────────
@app.post("/api/admin/clients/{client_id}/toggle")
async def admin_toggle_client(client_id: str, request: Request, _=Depends(require_admin)):
    store: "DataStore" = request.app.state.store
    client = store.get_client(client_id)
    if client:
        client["status"] = "suspended" if client.get("status") == "active" else "active"
        store.save_client(client)
    return {"success": True}


@app.get("/api/admin/keys")
async def admin_get_keys(request: Request, _=Depends(require_admin)):
    store: "DataStore" = request.app.state.store
    data = store.get_admin_data()
    return {"success": True, "keys": data.get("activation_keys", [])}


@app.post("/api/admin/keys/generate")
async def admin_gen_key(request: Request, _=Depends(require_admin)):
    body = await request.json()
    plan = body.get("plan", "trial")
    days = int(body.get("days", 30))
    key = "-".join([secrets.token_hex(4).upper() for _ in range(4)])
    entry = {"key": key, "plan": plan, "days": days, "used": False, "created_at": datetime.now().isoformat()}
    store: "DataStore" = request.app.state.store
    data = store.get_admin_data()
    data.setdefault("activation_keys", []).append(entry)
    store.save_admin_data(data)
    return {"success": True, "key": key}


@app.post("/api/admin/keys/revoke")
async def admin_revoke_key(request: Request, _=Depends(require_admin)):
    body = await request.json()
    key = body.get("key", "")
    store: "DataStore" = request.app.state.store
    data = store.get_admin_data()
    data["activation_keys"] = [k for k in data.get("activation_keys", []) if k.get("key") != key]
    store.save_admin_data(data)
    return {"success": True}


@app.get("/api/admin/payments")
async def admin_get_payments(request: Request, _=Depends(require_admin)):
    store: "DataStore" = request.app.state.store
    data = store.get_admin_data()
    return {"success": True, "payments": data.get("payments", [])}


@app.post("/api/admin/payments/add")
async def admin_add_payment(request: Request, _=Depends(require_admin)):
    body = await request.json()
    payment = {"id": secrets.token_hex(8), "client_id": body.get("client_id", ""), "amount": float(body.get("amount", 0)), "plan": body.get("plan", ""), "date": datetime.now().isoformat()}
    store: "DataStore" = request.app.state.store
    data = store.get_admin_data()
    data.setdefault("payments", []).append(payment)
    store.save_admin_data(data)
    return {"success": True, "payment": payment}


@app.get("/api/admin/tickets")
async def admin_get_tickets(request: Request, _=Depends(require_admin)):
    store: "DataStore" = request.app.state.store
    data = store.get_admin_data()
    return {"success": True, "tickets": data.get("tickets", [])}


@app.post("/api/admin/tickets/reply")
async def admin_reply_ticket(request: Request, _=Depends(require_admin)):
    body = await request.json()
    tid = str(body.get("id", ""))
    reply = body.get("reply", "")
    store: "DataStore" = request.app.state.store
    data = store.get_admin_data()
    for t in data.get("tickets", []):
        if str(t.get("id")) == tid:
            t.setdefault("replies", []).append({"text": reply, "from": "admin", "at": datetime.now().isoformat()})
            break
    store.save_admin_data(data)
    return {"success": True}


@app.post("/api/admin/tickets/close")
async def admin_close_ticket(request: Request, _=Depends(require_admin)):
    body = await request.json()
    tid = str(body.get("id", ""))
    store: "DataStore" = request.app.state.store
    data = store.get_admin_data()
    for t in data.get("tickets", []):
        if str(t.get("id")) == tid:
            t["status"] = "closed"
            break
    store.save_admin_data(data)
    return {"success": True}


@app.get("/api/admin/sessions")
async def admin_list_sessions(request: Request, _=Depends(require_admin)):
    """قائمة الجلسات النشطة لجميع المنشآت"""
    store: "DataStore" = request.app.state.store
    with _lock:
        raw = dict(_client_sessions)
    result = []
    for token, sess in raw.items():
        cid = sess.get("client_id", "")
        client = store.get_client(cid) or {}
        result.append({
            "token_prefix": token[:8],
            "client_id": cid,
            "client_name": client.get("name", client.get("hotel_name", cid)),
            "plan": client.get("plan", "trial"),
            "created_at": sess.get("created_at", ""),
        })
    result.sort(key=lambda x: x["created_at"], reverse=True)
    return {"success": True, "sessions": result}


@app.post("/api/admin/sessions/{token_prefix}/revoke")
async def admin_revoke_session(token_prefix: str, request: Request, _=Depends(require_admin)):
    """إنهاء جلسة نشطة بواسطة المدير"""
    with _lock:
        to_remove = [t for t in _client_sessions if t.startswith(token_prefix)]
        for t in to_remove:
            _client_sessions.pop(t, None)
    return {"success": True, "revoked": len(to_remove)}


@app.get("/api/admin/subscriptions")
async def admin_list_subscriptions(request: Request, _=Depends(require_admin)):
    """قائمة اشتراكات جميع المنشآت"""
    cfg = request.app.state.cfg
    store: "DataStore" = request.app.state.store
    clients = store.get_all_clients()
    owner_id = getattr(cfg, "owner_client_id", "") or ""
    subs = []
    for c in clients:
        subs.append({
            "client_id": c.get("id", ""),
            "name": c.get("name", c.get("hotel_name", c.get("id", ""))),
            "plan": c.get("plan", "trial"),
            "status": c.get("status", "trial"),
            "sub_start": c.get("sub_start", ""),
            "sub_end": c.get("sub_end", c.get("subscription_expires", c.get("trial_end", ""))),
            "price": c.get("sub_price", 0),
            "is_owner": (str(c.get("id", "")) == owner_id),
        })
    subs.sort(key=lambda x: (0 if x.get("is_owner") else 1, x.get("sub_end") or ""))
    return {"success": True, "subscriptions": subs}


@app.put("/api/admin/subscriptions/{client_id}")
async def admin_update_subscription(client_id: str, request: Request, _=Depends(require_admin)):
    """تحديث اشتراك منشأة"""
    store: "DataStore" = request.app.state.store
    client = store.get_client(client_id)
    if not client:
        raise HTTPException(status_code=404, detail="المنشأة غير موجودة")
    body = await request.json()
    for field in ["plan", "status", "sub_start", "sub_end", "sub_price"]:
        if field in body:
            client[field] = body[field]
    # sync status on the client record as well
    if "status" in body:
        client["status"] = body["status"]
    store.save_client(client)
    return {"success": True, "client_id": client_id}


@app.post("/api/admin/clients/{client_id}/reset-password")
async def admin_reset_client_password(client_id: str, request: Request, _=Depends(require_admin)):
    """إعادة تعيين كلمة مرور مدير المنشأة"""
    store: "DataStore" = request.app.state.store
    client = store.get_client(client_id)
    if not client:
        raise HTTPException(status_code=404, detail="المنشأة غير موجودة")
    body = await request.json()
    password = str(body.get("password", "")).strip()
    if len(password) < 4:
        return JSONResponse({"success": False, "error": "كلمة المرور قصيرة جداً"}, status_code=400)
    client["pass_hash"], client["pass_salt"] = _make_password(password)
    store.save_client(client)
    return {"success": True}


@app.put("/api/admin/clients/{client_id}/modules")
async def admin_update_modules(client_id: str, request: Request, _=Depends(require_admin)):
    """تحديث الوحدات المفعّلة لمنشأة"""
    store: "DataStore" = request.app.state.store
    client = store.get_client(client_id)
    if not client:
        raise HTTPException(status_code=404, detail="المنشأة غير موجودة")
    body = await request.json()
    client["enabled_modules"] = body.get("enabled_modules", [])
    store.save_client(client)
    return {"success": True, "enabled_modules": client["enabled_modules"]}


@app.get("/api/admin/employees")
async def admin_list_employees(request: Request, client_id: Optional[str] = None, _=Depends(require_admin)):
    """قائمة الموظفين من قاعدة البيانات مع آخر نشاط"""
    db = request.app.state.db
    store: "DataStore" = request.app.state.store
    if not db.use_postgres:
        return {"success": True, "employees": []}
    try:
        if client_id:
            rows = db.execute("""
                SELECT e.client_id, e.id,
                       COALESCE(e.full_name_ar, e.full_name_en, '') AS name,
                       COALESCE(e.position, '') AS role,
                       MAX(ra.created_at) as last_active,
                       COUNT(ra.id) as task_count
                FROM employees e
                LEFT JOIN room_actions ra ON ra.client_id=e.client_id AND ra.performed_by=COALESCE(e.full_name_ar, e.full_name_en)
                WHERE e.client_id=%s
                GROUP BY e.client_id, e.id, e.full_name_ar, e.full_name_en, e.position
                ORDER BY last_active DESC NULLS LAST
            """, (client_id,), fetch="all")
        else:
            rows = db.execute("""
                SELECT e.client_id, e.id,
                       COALESCE(e.full_name_ar, e.full_name_en, '') AS name,
                       COALESCE(e.position, '') AS role,
                       MAX(ra.created_at) as last_active,
                       COUNT(ra.id) as task_count
                FROM employees e
                LEFT JOIN room_actions ra ON ra.client_id=e.client_id AND ra.performed_by=COALESCE(e.full_name_ar, e.full_name_en)
                GROUP BY e.client_id, e.id, e.full_name_ar, e.full_name_en, e.position
                ORDER BY last_active DESC NULLS LAST
                LIMIT 200
            """, fetch="all")
        clients_map = {c["id"]: c.get("name", c.get("hotel_name", c["id"])) for c in store.get_all_clients()}
        result = []
        for r in (rows or []):
            d = dict(r)
            d["client_name"] = clients_map.get(d.get("client_id", ""), d.get("client_id", ""))
            if d.get("last_active"):
                d["last_active"] = str(d["last_active"])
            result.append(d)
        return {"success": True, "employees": result}
    except Exception as e:
        return {"success": True, "employees": [], "warning": str(e)}


@app.get("/api/admin/settings")
async def admin_get_settings(request: Request, _=Depends(require_admin)):
    store: "DataStore" = request.app.state.store
    data = store.get_admin_data()
    return {"success": True, "settings": data.get("settings", {})}


@app.post("/api/admin/settings/save")
async def admin_save_settings(request: Request, _=Depends(require_admin)):
    body = await request.json()
    store: "DataStore" = request.app.state.store
    data = store.get_admin_data()
    data.setdefault("settings", {}).update(body)
    store.save_admin_data(data)
    return {"success": True}


# ──────────────────────────────────────────────────────────────
#  Public Packages — أسعار الباقات المعروضة للزوار (يحرّرها المالك)
# ──────────────────────────────────────────────────────────────
_DEFAULT_PACKAGES = [
    {
        "id": "essentials",
        "name_ar": "باقة الإدارة الأساسية",
        "name_en": "Essentials",
        "price": "٢٬٤٠٠",
        "currency": "ر.س",
        "period": "/شهر",
        "save_note": "",
        "cta": "ابدأ التجربة",
    },
    {
        "id": "full",
        "name_ar": "باقة الضيافة الكاملة",
        "name_en": "Full Hospitality",
        "price": "٥٬٤٠٠",
        "currency": "ر.س",
        "period": "/شهر",
        "save_note": "توفير ١٬٢٠٠ ر.س شهرياً (١٨٪)",
        "cta": "ابدأ التجربة المجانية",
    },
    {
        "id": "enterprise",
        "name_ar": "باقة المؤسسات",
        "name_en": "Enterprise",
        "price": "حسب الطلب",
        "currency": "",
        "period": "",
        "save_note": "",
        "cta": "تواصل مع المبيعات",
    },
]

# discount_percent: خصم اختياري (٠–١٠٠) يحرّره المالك من اللوحة
_PKG_EDITABLE = ("name_ar", "name_en", "price", "currency", "period",
                 "save_note", "cta", "discount_percent")


def _arabic_to_int(s) -> Optional[float]:
    """يحوّل سعراً عربياً/إنجليزياً مثل '٥٬٤٠٠' أو '5,400' إلى رقم — أو None."""
    if s is None:
        return None
    trans = str.maketrans("٠١٢٣٤٥٦٧٨٩،٬", "0123456789,,")
    digits = str(s).translate(trans).replace(",", "").replace(" ", "")
    try:
        return float(digits)
    except (ValueError, TypeError):
        return None


def _int_to_arabic(n: float) -> str:
    """يحوّل رقماً إلى صيغة عربية بفاصل آلاف '٬'."""
    whole = int(round(n))
    grouped = f"{whole:,}".replace(",", "٬")
    return grouped.translate(str.maketrans("0123456789", "٠١٢٣٤٥٦٧٨٩"))


def _merge_packages(stored: list) -> list:
    """يدمج القيم المحفوظة فوق الافتراضية حسب id — يضمن وجود الباقات الثلاث دائماً.

    يحسب أيضاً السعر بعد الخصم (price_after) و discount_percent المطبّق.
    """
    by_id = {p.get("id"): dict(p) for p in (stored or []) if isinstance(p, dict)}
    result = []
    for default in _DEFAULT_PACKAGES:
        merged = dict(default)
        merged.setdefault("discount_percent", 0)
        saved = by_id.get(default["id"])
        if isinstance(saved, dict):
            for k in _PKG_EDITABLE:
                if k in saved and saved[k] is not None:
                    merged[k] = saved[k]
        # احسب السعر بعد الخصم
        try:
            pct = float(merged.get("discount_percent", 0) or 0)
        except (ValueError, TypeError):
            pct = 0
        pct = max(0, min(pct, 100))
        merged["discount_percent"] = pct
        base = _arabic_to_int(merged.get("price"))
        if base is not None and pct > 0:
            after = round(base * (1 - pct / 100))
            merged["price_after"] = _int_to_arabic(after)
            merged["price_original"] = merged.get("price")
            if not merged.get("save_note"):
                saved_amount = _int_to_arabic(base - after)
                merged["save_note"] = f"خصم {int(pct)}٪ — وفّر {saved_amount} {merged.get('currency','')}"
        else:
            merged["price_after"] = merged.get("price")
            merged["price_original"] = ""
        result.append(merged)
    return result


@app.get("/api/packages")
async def public_packages(request: Request):
    """عام — يقرأه صفحة الباقات لعرض الأسعار الحيّة (لا يتطلب تسجيل دخول)."""
    store: "DataStore" = request.app.state.store
    data = store.get_admin_data()
    return {"success": True, "packages": _merge_packages(data.get("public_packages", []))}


@app.put("/api/admin/packages")
async def admin_update_packages(request: Request, _=Depends(require_admin)):
    """يحفظ أسعار الباقات العامة التي يحرّرها المالك من اللوحة."""
    body = await request.json()
    incoming = body.get("packages", [])
    if not isinstance(incoming, list):
        return JSONResponse({"success": False, "error": "صيغة غير صحيحة"}, status_code=400)
    # نظّف الحقول المسموح بتحريرها فقط
    cleaned = []
    for p in incoming:
        if not isinstance(p, dict) or not p.get("id"):
            continue
        item = {"id": str(p["id"])}
        for k in _PKG_EDITABLE:
            if k in p:
                item[k] = str(p[k])
        cleaned.append(item)
    store: "DataStore" = request.app.state.store
    data = store.get_admin_data()
    data["public_packages"] = cleaned
    store.save_admin_data(data)
    return {"success": True, "packages": _merge_packages(cleaned)}


@app.get("/api/admin/stats")
async def admin_stats_v2(request: Request, _=Depends(require_admin)):
    store: "DataStore" = request.app.state.store
    clients = store.get_all_clients()
    active = sum(1 for c in clients if c.get("status") == "active")
    trial = sum(1 for c in clients if c.get("status") == "trial")
    paid = sum(1 for c in clients if c.get("plan") not in (None, "", "trial"))
    data = store.get_admin_data()
    total_revenue = sum(float(p.get("amount", 0)) for p in data.get("payments", []))
    return {"success": True, "stats": {"total_clients": len(clients), "active_clients": active, "trial_clients": trial, "paid_clients": paid, "total_revenue": total_revenue}}


# ──────────────────────────────────────────────────────────────
#  Client registration
# ──────────────────────────────────────────────────────────────
@app.post("/api/client/register")
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

    if not hotel_name or not client_id or not password:
        return JSONResponse({"success": False, "error": "جميع الحقول مطلوبة"}, status_code=400)

    # M3 mitigation: حدّ معدّل التسجيل لكل IP
    client_ip = (request.client.host if request.client else "?")
    if not _reg_rate_ok(client_ip):
        return JSONResponse(
            {"success": False, "error": "محاولات تسجيل كثيرة — حاول لاحقاً"},
            status_code=429)

    cfg = request.app.state.cfg
    store: "DataStore" = request.app.state.store

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
        _client_sessions[token] = {"client_id": client_id, "created_at": datetime.now().isoformat()}

    response = JSONResponse({"success": True, "ok": True, "client_id": client_id})
    response.set_cookie("client_token", token, httponly=True, samesite="lax", secure=_COOKIE_SECURE, max_age=86400 * 7)
    return response


# ──────────────────────────────────────────────────────────────
#  Invoice pay endpoint
# ──────────────────────────────────────────────────────────────
@app.post("/api/invoices/{invoice_id}/pay")
async def pay_invoice(invoice_id: str, request: Request, session=Depends(require_client)):
    store: "DataStore" = request.app.state.store
    cid = session["client_id"]
    invoices = store.get_invoices(cid)
    inv = next((i for i in invoices if str(i.get("id", i.get("invoice_number", ""))) == invoice_id), None)
    if inv:
        inv["payment_status"] = "paid"
        store.save_invoice(cid, inv)
    return {"success": True}


# ──────────────────────────────────────────────────────────────
#  Tickets (client side)
# ──────────────────────────────────────────────────────────────
@app.get("/api/tickets")
async def get_tickets(request: Request, session=Depends(require_client)):
    store: "DataStore" = request.app.state.store
    cid = session["client_id"]
    data = store.get_admin_data()
    tickets = [t for t in data.get("tickets", []) if t.get("client_id") == cid]
    return {"success": True, "tickets": tickets}


@app.post("/api/tickets")
async def create_ticket(request: Request, session=Depends(require_client)):
    body = await request.json()
    store: "DataStore" = request.app.state.store
    cid = session["client_id"]
    ticket = {
        "id": secrets.token_hex(8),
        "client_id": cid,
        "subject": body.get("subject", ""),
        "body": body.get("body", ""),
        "status": "open",
        "created_at": datetime.now().isoformat(),
        "replies": [],
    }
    data = store.get_admin_data()
    data.setdefault("tickets", []).append(ticket)
    store.save_admin_data(data)
    return {"success": True, "ticket": ticket}


# ──────────────────────────────────────────────────────────────
#  AI Analyze
# ──────────────────────────────────────────────────────────────
@app.post("/api/ai/analyze")
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
        store: "DataStore" = request.app.state.store
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
@app.post("/api/backup/create")
async def backup_create(request: Request, session=Depends(require_client)):
    store: "DataStore" = request.app.state.store
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


@app.get("/api/backup/list")
async def backup_list(request: Request, session=Depends(require_client)):
    cid = session["client_id"]
    backup_dir = "backups"
    if not os.path.isdir(backup_dir):
        return {"success": True, "backups": []}
    files = sorted([f for f in os.listdir(backup_dir) if f.startswith(f"backup_{cid}_")], reverse=True)
    return {"success": True, "backups": files}


# ──────────────────────────────────────────────────────────────
#  Open API — مُدار بالكامل عبر routes/open_api.py
#  (الغرف، الحجوزات، الضيوف، الفواتير ZATCA، المحاسبة، القنوات، KPI)
# ──────────────────────────────────────────────────────────────


# ──────────────────────────────────────────────────────────────
#  Module Catalog — كتالوج الوحدات القابلة للاشتراك
# ──────────────────────────────────────────────────────────────
MODULE_CATALOG = [
    {"code": "m01", "name_ar": "إدارة الضيوف",        "name_en": "Guest Management",        "category": "core",       "price": 299,  "unit": "شهر"},
    {"code": "m02", "name_ar": "الاستقبال",            "name_en": "Front Desk",               "category": "core",       "price": 199,  "unit": "شهر"},
    {"code": "m03", "name_ar": "مدير القنوات",         "name_en": "Channel Manager",          "category": "revenue",    "price": 499,  "unit": "شهر"},
    {"code": "m04", "name_ar": "المحاسبة + POS",       "name_en": "Accounting + POS",         "category": "operations", "price": 599,  "unit": "شهر"},
    {"code": "m05", "name_ar": "المخزون",              "name_en": "Inventory",                "category": "operations", "price": 249,  "unit": "شهر"},
    {"code": "m06", "name_ar": "الموارد البشرية",      "name_en": "HR & Payroll",             "category": "operations", "price": 399,  "unit": "شهر + 15/موظف"},
    {"code": "m07", "name_ar": "الإشراف الداخلي",      "name_en": "Housekeeping",             "category": "core",       "price": 199,  "unit": "شهر"},
    {"code": "m08", "name_ar": "الصيانة",              "name_en": "Maintenance",              "category": "operations", "price": 249,  "unit": "شهر"},
    {"code": "m09", "name_ar": "المفتاح الذكي",        "name_en": "Smart Key & Fraud",        "category": "intel",      "price": 699,  "unit": "شهر + 8/غرفة"},
    {"code": "m10", "name_ar": "CRM والولاء",          "name_en": "CRM & Loyalty",            "category": "revenue",    "price": 349,  "unit": "شهر"},
    {"code": "m11", "name_ar": "مؤشرات الأداء",        "name_en": "KPI Analytics",            "category": "intel",      "price": 299,  "unit": "شهر"},
    {"code": "m12", "name_ar": "الرؤى الذكية",         "name_en": "Data Insights (AI)",       "category": "intel",      "price": 599,  "unit": "شهر"},
    {"code": "m13", "name_ar": "المستودعات",           "name_en": "Warehouses & Procurement", "category": "operations", "price": 249,  "unit": "شهر"},
    {"code": "m14", "name_ar": "الجولات السياحية",     "name_en": "Tourism Tours",            "category": "revenue",    "price": 199,  "unit": "شهر"},
    {"code": "m14b","name_ar": "وجهات سياحية",         "name_en": "Tourist Destinations",     "category": "revenue",    "price": 149,  "unit": "شهر"},
    {"code": "m15", "name_ar": "تطبيق الموظفين",       "name_en": "Staff Mobile App",         "category": "addon",      "price": 29,   "unit": "مستخدم/شهر"},
]

PLANS_CATALOG = [
    {"code": "trial",        "name_ar": "تجربة مجانية",  "price": 0,     "modules": ["m01","m02","m03","m04","m05","m06","m07","m08","m09","m10","m11","m12","m13","m14","m14b","m15"], "discount": 0,   "days": 30},
    {"code": "starter",      "name_ar": "Starter",        "price": 599,   "modules": ["m01","m02","m07"],                                                                               "discount": 20,  "days": None},
    {"code": "operations",   "name_ar": "Operations",     "price": 1099,  "modules": ["m01","m02","m07","m05","m08","m13"],                                                              "discount": 25,  "days": None},
    {"code": "professional", "name_ar": "Professional",   "price": 2299,  "modules": ["m01","m02","m07","m05","m08","m13","m03","m04","m06","m11"],                                     "discount": 30,  "days": None},
    {"code": "enterprise",   "name_ar": "Enterprise",     "price": None,  "modules": ["m01","m02","m03","m04","m05","m06","m07","m08","m09","m10","m11","m12","m13","m14","m14b","m15"],"discount": 40,  "days": None},
]


@app.get("/api/modules/catalog")
async def modules_catalog():
    return {"success": True, "modules": MODULE_CATALOG, "plans": PLANS_CATALOG}


@app.get("/api/modules/client")
async def client_modules(request: Request, session=Depends(require_client)):
    store: "DataStore" = request.app.state.store
    client = store.get_client(session["client_id"]) or {}
    plan = client.get("plan", "trial")
    plan_data = next((p for p in PLANS_CATALOG if p["code"] == plan), PLANS_CATALOG[0])
    # البند 2: لكل مشترك وحداته — أولوية للتفعيل اليدوي ثم وحدات الخطة
    enabled = client.get("enabled_modules")
    if isinstance(enabled, list) and enabled:
        active_modules = [m for m in enabled if any(c["code"] == m for c in MODULE_CATALOG)]
    else:
        active_modules = list(plan_data["modules"])
    return {
        "success": True,
        "plan": plan,
        "plan_name": plan_data.get("name_ar", plan),
        "status": client.get("status", "trial"),
        "sub_end": client.get("sub_end", client.get("trial_end", "")),
        "active_modules": active_modules,
        "module_count": len(active_modules),
        "total_modules": len(MODULE_CATALOG),
        "all_modules": MODULE_CATALOG,
    }


# ──────────────────────────────────────────────────────────────
#  Dashboard Page — لوحة التحكم الكاملة
# ──────────────────────────────────────────────────────────────
@app.get("/dashboard", response_class=HTMLResponse)
async def dashboard_page(request: Request):
    session = get_client_session(request)
    if not session:
        return RedirectResponse("/login")
    import os
    dash_path = os.path.join("static", "dashboard.html")
    if os.path.exists(dash_path):
        with open(dash_path, "r", encoding="utf-8") as f:
            return HTMLResponse(f.read())
    return RedirectResponse("/")


# ──────────────────────────────────────────────────────────────
#  SEO Routes
# ──────────────────────────────────────────────────────────────
@app.get("/robots.txt")
async def robots_txt():
    from fastapi.responses import PlainTextResponse
    return PlainTextResponse(
        "User-agent: *\nAllow: /\nDisallow: /admin\nDisallow: /api/\n"
        "Sitemap: https://dheuof.com/sitemap.xml\n"
    )


@app.get("/sitemap.xml")
async def sitemap():
    from fastapi.responses import Response
    xml = """<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
  <url><loc>https://dheuof.com/</loc><changefreq>weekly</changefreq><priority>1.0</priority></url>
  <url><loc>https://dheuof.com/marketing</loc><changefreq>monthly</changefreq><priority>0.8</priority></url>
</urlset>"""
    return Response(content=xml, media_type="application/xml")


@app.get("/ref/{code}", response_class=HTMLResponse)
async def referral_redirect(code: str):
    """رابط الإحالة — يفتح صفحة التسجيل مع كود المسوق محمّل تلقائياً"""
    return HTMLResponse(_login_page(ref_code=code.upper()))


# ──────────────────────────────────────────────────────────────
#  Admin — Marketers (المسوقون)
# ──────────────────────────────────────────────────────────────
@app.get("/api/admin/marketers")
async def admin_list_marketers(request: Request, _=Depends(require_admin)):
    db = request.app.state.db
    if not db.use_postgres:
        return {"success": True, "marketers": []}
    try:
        rows = db.execute("""
            SELECT m.*,
                   COUNT(r.id) AS referral_count,
                   COALESCE(SUM(0), 0) AS total_earnings
            FROM marketers m
            LEFT JOIN marketer_referrals r ON r.marketer_id = m.id
            GROUP BY m.id
            ORDER BY referral_count DESC
        """, fetch="all")
        return {"success": True, "marketers": [dict(r) for r in (rows or [])]}
    except Exception as e:
        return {"success": True, "marketers": [], "warning": str(e)}


@app.post("/api/admin/marketers")
async def admin_create_marketer(request: Request, _=Depends(require_admin)):
    body = await request.json()
    name = str(body.get("name", "")).strip()
    if not name:
        return JSONResponse({"success": False, "error": "الاسم مطلوب"}, status_code=400)
    db = request.app.state.db
    # توليد كود فريد إذا لم يُحدَّد
    ref_code = str(body.get("ref_code", "")).strip().upper()
    if not ref_code:
        ref_code = secrets.token_hex(4).upper()
    try:
        row = db.execute("""
            INSERT INTO marketers (name, phone, email, ref_code, commission_rate, notes)
            VALUES (%s, %s, %s, %s, %s, %s) RETURNING *
        """, (name, body.get("phone",""), body.get("email",""),
              ref_code, float(body.get("commission_rate", 10)),
              body.get("notes","")), fetch="one")
        return {"success": True, "marketer": dict(row)}
    except Exception as e:
        return JSONResponse({"success": False, "error": str(e)}, status_code=500)


@app.put("/api/admin/marketers/{mktr_id}")
async def admin_update_marketer(mktr_id: int, request: Request, _=Depends(require_admin)):
    body = await request.json()
    db = request.app.state.db
    fields = []
    vals = []
    for f in ["name", "phone", "email", "commission_rate", "status", "notes"]:
        if f in body:
            fields.append(f"{f}=%s")
            vals.append(body[f])
    if not fields:
        return {"success": True}
    vals.append(mktr_id)
    db.execute(f"UPDATE marketers SET {', '.join(fields)} WHERE id=%s", vals)
    return {"success": True}


@app.delete("/api/admin/marketers/{mktr_id}")
async def admin_delete_marketer(mktr_id: int, request: Request, _=Depends(require_admin)):
    db = request.app.state.db
    db.execute("UPDATE marketers SET status='inactive' WHERE id=%s", (mktr_id,))
    return {"success": True}


@app.get("/api/admin/marketers/{mktr_id}/referrals")
async def admin_marketer_referrals(mktr_id: int, request: Request, _=Depends(require_admin)):
    db = request.app.state.db
    store: "DataStore" = request.app.state.store
    try:
        rows = db.execute("""
            SELECT r.*, c.name as client_name
            FROM marketer_referrals r
            LEFT JOIN clients c ON c.id = r.client_id
            WHERE r.marketer_id = %s
            ORDER BY r.converted_at DESC
        """, (mktr_id,), fetch="all")
        return {"success": True, "referrals": [dict(r) for r in (rows or [])]}
    except Exception as e:
        return {"success": True, "referrals": [], "warning": str(e)}


# ──────────────────────────────────────────────────────────────
#  Entry point
# ──────────────────────────────────────────────────────────────
