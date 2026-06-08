#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
main1.py — قلب التطبيق: الإعداد، الـ middleware، المصادقة
يُستورد من main.py (نقطة الدخول) و main2.py (الـ routes)
"""

import decimal
import hashlib
import json
import logging
import os
import secrets
import threading
from contextlib import asynccontextmanager
from datetime import datetime, date, timedelta
from typing import Optional

import uvicorn
from fastapi import FastAPI, Request, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse, Response
from fastapi.staticfiles import StaticFiles
from fastapi.encoders import jsonable_encoder


class _SafeEncoder(json.JSONEncoder):
    """Serialize PostgreSQL Decimal/date/datetime types that json.dumps rejects."""
    def default(self, obj):
        if isinstance(obj, decimal.Decimal):
            return float(obj)
        if isinstance(obj, (datetime, date)):
            return obj.isoformat()
        return super().default(obj)


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    handlers=[logging.StreamHandler()],
)
log = logging.getLogger("dheuof")

# ──────────────────────────────────────────────────────────────
#  Sessions (in-memory; reset on restart — fine for stateless Railway)
# ──────────────────────────────────────────────────────────────
_admin_sessions: dict = {}   # token → {"created_at": ...}
_client_sessions: dict = {}  # token → {"client_id": ..., "created_at": ...}
_lock = threading.Lock()

# Secure cookies in production (HTTPS). Railway/most PaaS set these env vars.
_COOKIE_SECURE = bool(
    os.environ.get("RAILWAY_ENVIRONMENT")
    or os.environ.get("RAILWAY_STATIC_URL")
    or os.environ.get("COOKIE_SECURE", "").lower() in ("1", "true", "yes")
)

# M3 mitigation: حدّ بسيط لمعدّل التسجيل لكل IP (ضد إنشاء حسابات بالجملة)
_reg_attempts: dict = {}     # ip → [timestamps]
_REG_MAX_PER_HOUR = int(os.environ.get("REG_MAX_PER_HOUR", "5"))

# Login rate limiting: protect /api/login against brute-force attacks
_login_attempts: dict = {}   # ip → [timestamps]
_LOGIN_MAX_PER_MINUTE = int(os.environ.get("LOGIN_MAX_PER_MINUTE", "10"))


def _reg_rate_ok(ip: str) -> bool:
    """يسمح بحد أقصى REG_MAX_PER_HOUR تسجيلات لكل IP في الساعة."""
    now = datetime.now().timestamp()
    with _lock:
        hits = [t for t in _reg_attempts.get(ip, []) if now - t < 3600]
        if len(hits) >= _REG_MAX_PER_HOUR:
            _reg_attempts[ip] = hits
            return False
        hits.append(now)
        _reg_attempts[ip] = hits
        return True


def _login_rate_ok(ip: str) -> bool:
    """Allow at most LOGIN_MAX_PER_MINUTE login attempts per IP per minute (brute-force guard)."""
    now = datetime.now().timestamp()
    with _lock:
        hits = [t for t in _login_attempts.get(ip, []) if now - t < 60]
        if len(hits) >= _LOGIN_MAX_PER_MINUTE:
            _login_attempts[ip] = hits
            return False
        hits.append(now)
        _login_attempts[ip] = hits
        return True


def _new_token() -> str:
    return secrets.token_urlsafe(32)


def _hash_password(password: str, salt: str) -> str:
    return hashlib.pbkdf2_hmac(
        "sha256", password.encode(), salt.encode(), 100_000
    ).hex()


def _make_password(password: str) -> tuple[str, str]:
    """C2 fix: يُنشئ ملحاً عشوائياً فريداً لكل حساب ويعيد (hash, salt)."""
    salt = secrets.token_hex(16)
    return _hash_password(password, salt), salt


def _verify_password(password: str, client: dict, cfg) -> bool:
    """يتحقق من كلمة المرور بملح الحساب، مع توافق خلفي مع الملح العام القديم."""
    stored = client.get("pass_hash", "") or ""
    if not stored:
        return False
    salt = client.get("pass_salt") or cfg.pass_salt   # legacy fallback
    return secrets.compare_digest(_hash_password(password, salt), stored)


# ──────────────────────────────────────────────────────────────
#  Lifespan — startup / shutdown
# ──────────────────────────────────────────────────────────────
@asynccontextmanager
async def lifespan(app_: FastAPI):
    from config import Config, init_config
    from db.connection import init_db
    from db.store import DataStore

    cfg = Config.from_env()
    init_config(cfg)
    log.info(cfg.summary())

    os.makedirs("data", exist_ok=True)
    db = init_db(cfg.database_url, "data/store.json")
    store = DataStore(db, cfg.dual_write)

    app_.state.cfg = cfg
    app_.state.db = db
    app_.state.store = store

    # ── v3 migrations — جميع الوحدات الـ 15 + وجهات سياحية ──
    try:
        from db.migrations import run_all_migrations
        run_all_migrations(db)
    except Exception as e:
        log.warning(f"v1 migrations: {e}")
    try:
        from db.schema_v3 import run_v3_migrations
        run_v3_migrations(db)
    except Exception as e:
        log.warning(f"v3 migrations: {e}")
    try:
        from db.schema_v3 import run_staff_app_migrations
        run_staff_app_migrations(db)
    except Exception as e:
        log.warning(f"staff_app migrations: {e}")
    try:
        from db.schema_v3 import run_security_hardening
        run_security_hardening(db)
    except Exception as e:
        log.warning(f"security hardening migrations: {e}")
    try:
        from db.schema_v3 import run_sessions_migration
        run_sessions_migration(db)
    except Exception as e:
        log.warning(f"sessions migration: {e}")
    try:
        from db.schema_v3 import run_rls_migration
        run_rls_migration(db)
    except Exception as e:
        log.warning(f"RLS migration: {e}")
    try:
        from db.schema_v3 import run_perf_indexes
        run_perf_indexes(db)
        log.info("✓ Performance indexes ready")
    except Exception as e:
        log.warning(f"perf indexes: {e}")
    try:
        from db.schema_v3 import run_v4_migrations
        run_v4_migrations(db)
        log.info("✓ v4 migrations (ZATCA + Night Audit + Reviews) ready")
    except Exception as e:
        log.warning(f"v4 migrations: {e}")

    # ── Sentry (APM / error tracking) ──────────────────────────────────────
    if cfg.has_sentry:
        try:
            import sentry_sdk
            sentry_sdk.init(
                dsn=cfg.sentry_dsn,
                traces_sample_rate=0.1,
                environment="production" if not cfg.debug else "development",
            )
            log.info("✓ Sentry initialized")
        except Exception as e:
            log.warning(f"Sentry init failed: {e}")

    # Load optional services — each independent so one failure doesn't sink the rest
    app_.state.pricing = None
    app_.state.channels = None
    app_.state.api_keys = None
    app_.state.zatca = None
    try:
        from services.dynamic_pricing import DynamicPricingEngine
        app_.state.pricing = DynamicPricingEngine(db)
        log.info("✓ Dynamic Pricing service")
    except Exception as e:
        log.warning(f"Dynamic Pricing unavailable: {e}")
    try:
        from services.channel_manager import ChannelManager
        app_.state.channels = ChannelManager(db)
        log.info("✓ Channel Manager service")
    except Exception as e:
        log.warning(f"Channel Manager service unavailable: {e}")
    try:
        from services.api_keys import APIKeyManager
        app_.state.api_keys = APIKeyManager(db)
        log.info("✓ API Key Manager service")
    except Exception as e:
        log.warning(f"API Key Manager unavailable: {e}")
    try:
        from services.zatca import ZatcaInvoiceService
        app_.state.zatca = ZatcaInvoiceService(db)
        log.info("✓ ZATCA Invoice service")
    except Exception as e:
        log.warning(f"ZATCA service unavailable: {e}")

    # ── Background session cleanup (every 6 hours) ─────────────────────────
    import asyncio

    async def _session_cleanup():
        while True:
            await asyncio.sleep(6 * 3600)
            try:
                if db.use_postgres:
                    db.execute("DELETE FROM client_sessions WHERE expires_at < NOW()")
                    # Also clear expired from in-memory dict
                    now_ts = datetime.now().isoformat()
                    with _lock:
                        stale = [t for t, s in list(_client_sessions.items())
                                 if s.get("created_at", "9999") < (datetime.now() - timedelta(days=8)).isoformat()]
                        for t in stale:
                            _client_sessions.pop(t, None)
                    log.info("✅ Session cleanup completed")
            except Exception as e:
                log.warning(f"Session cleanup error: {e}")

    _cleanup_task = asyncio.create_task(_session_cleanup())

    yield

    _cleanup_task.cancel()
    db.close()


# ──────────────────────────────────────────────────────────────
#  App
# ──────────────────────────────────────────────────────────────
app = FastAPI(title="ضيوف — Dheuof Hotel SaaS", version="3.0.0", lifespan=lifespan, docs_url=None, redoc_url=None)

# GZip compression for all text responses ≥ 1 KB
app.add_middleware(GZipMiddleware, minimum_size=1000)

# M4 fix: قصر CORS على نطاقات ضيوف المعروفة بدل "*" مع بقاء credentials
_ALLOWED_ORIGINS = [o.strip() for o in os.environ.get(
    "CORS_ORIGINS",
    "https://www.dheuof.com,https://dheuof.com,http://localhost:5050,http://127.0.0.1:5050",
).split(",") if o.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=_ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

os.makedirs("static", exist_ok=True)
app.mount("/static", StaticFiles(directory="static"), name="static")


@app.middleware("http")
async def add_security_and_cache_headers(request: Request, call_next):
    response = await call_next(request)
    path = request.url.path
    # Cache headers
    if path.startswith("/static/") and not path.endswith(".html"):
        response.headers["Cache-Control"] = "public, max-age=604800, immutable"
    elif path.startswith("/static/") and path.endswith(".html"):
        response.headers["Cache-Control"] = "no-cache, must-revalidate"
    # Security headers on all responses
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("X-Frame-Options", "SAMEORIGIN")
    response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
    response.headers.setdefault("Permissions-Policy", "camera=(), microphone=(), geolocation=()")
    return response


# Module shortcut paths that must be locked behind login (server-side gate)
_PROTECTED_PAGE_PREFIXES = (
    "/dheuof", "/guests-module", "/shumus", "/tourism", "/inventory",
    "/warehouse", "/account", "/accounting", "/pos", "/smart-key", "/hr",
    "/channels", "/marketing-channels", "/analytics", "/staff",
    "/ota-bookings", "/trips", "/tourism-trips", "/guests", "/bookings",
)


@app.middleware("http")
async def server_side_auth_gate(request: Request, call_next):
    """Real lock: serve program pages only to authenticated clients.

    Without a valid session, any direct navigation to a module page (either the
    pretty shortcut like /pos or the raw /static/dheuof/modules/<m>/index.html)
    is redirected to /login. This closes the gap where the client-side JS auth
    wall could be bypassed by disabling JavaScript or hitting the static file.
    """
    path = request.url.path
    is_module_html = (
        path.startswith("/static/dheuof/modules/") and path.endswith("/index.html")
    )
    is_shortcut = path in _PROTECTED_PAGE_PREFIXES
    if is_module_html or is_shortcut:
        if get_client_session(request) is None:
            # Browsers navigating get a redirect; programmatic/XHR get 401
            accept = request.headers.get("accept", "")
            if "text/html" in accept:
                return RedirectResponse("/login", status_code=302)
            return JSONResponse({"detail": "غير مصرح — يلزم تسجيل الدخول"}, status_code=401)
    return await call_next(request)


# ── Module Routers — جميع الوحدات الـ 15 + وجهات سياحية ─────
try:
    from routes.m02_frontdesk import router as m02_router
    app.include_router(m02_router)
    log.info("✓ M02 Front Desk")
except Exception as e:
    log.warning(f"M02: {e}")

try:
    from routes.m06_hr import router as m06_router
    app.include_router(m06_router)
    log.info("✓ M06 HR")
except Exception as e:
    log.warning(f"M06: {e}")

try:
    from routes.m07_housekeeping import router as m07_router
    app.include_router(m07_router)
    log.info("✓ M07 Housekeeping")
except Exception as e:
    log.warning(f"M07: {e}")

try:
    from routes.m08_maintenance import router as m08_router
    app.include_router(m08_router)
    log.info("✓ M08 Maintenance")
except Exception as e:
    log.warning(f"M08: {e}")

try:
    from routes.m10_crm import router as m10_router
    app.include_router(m10_router)
    log.info("✓ M10 CRM")
except Exception as e:
    log.warning(f"M10: {e}")

try:
    from routes.m11_kpi import router as m11_router
    app.include_router(m11_router)
    log.info("✓ M11 KPI")
except Exception as e:
    log.warning(f"M11: {e}")

try:
    from routes.m13_warehouses import router as m13_router
    app.include_router(m13_router)
    log.info("✓ M13 Warehouses")
except Exception as e:
    log.warning(f"M13: {e}")

try:
    from routes.m14_tourism import router as m14_router
    app.include_router(m14_router)
    log.info("✓ M14 Tourism Tours")
except Exception as e:
    log.warning(f"M14: {e}")

try:
    from routes.m14b_destinations import router as m14b_router
    app.include_router(m14b_router)
    log.info("✓ M14b Tourist Destinations")
except Exception as e:
    log.warning(f"M14b: {e}")

try:
    from routes.channels import router as channels_router
    app.include_router(channels_router)
    log.info("✓ Channel Manager (OTA)")
except Exception as e:
    log.warning(f"Channels: {e}")

try:
    from routes.open_api import router as open_api_router
    app.include_router(open_api_router)
    log.info("✓ Open API (modules + ZATCA accounting)")
except Exception as e:
    log.warning(f"Open API: {e}")

try:
    from routes.m04_inventory import router as m04_router
    app.include_router(m04_router)
    log.info("✓ M04 Inventory")
except Exception as e:
    log.warning(f"M04: {e}")

try:
    from routes.m17_bookings import router as m17_router
    app.include_router(m17_router)
    log.info("✓ M17 Bookings")
except Exception as e:
    log.warning(f"M17: {e}")

try:
    from routes.m06_accounting import router as m06acc_router
    app.include_router(m06acc_router)
    log.info("✓ M06acc Accounting")
except Exception as e:
    log.warning(f"M06acc: {e}")

try:
    from routes.m07_pos import router as m07_router
    app.include_router(m07_router)
    log.info("✓ M07 POS")
except Exception as e:
    log.warning(f"M07: {e}")

try:
    from routes.m_analytics import router as analytics_router
    app.include_router(analytics_router)
    log.info("✓ Analytics cross-module")
except Exception as e:
    log.warning(f"Analytics: {e}")

try:
    from routes.integration import router as integration_router
    app.include_router(integration_router)
    log.info("✓ Integration (cross-module orchestration)")
except Exception as e:
    log.warning(f"Integration: {e}")

try:
    from routes.m_zatca import router as zatca_router
    app.include_router(zatca_router)
    log.info("✓ ZATCA (فواتير إلكترونية + QR Code)")
except Exception as e:
    log.warning(f"ZATCA: {e}")

try:
    from routes.m_night_audit import router as night_audit_router
    app.include_router(night_audit_router)
    log.info("✓ Night Audit (إغلاق اليوم + أجهزة الدفع)")
except Exception as e:
    log.warning(f"NightAudit: {e}")

try:
    from routes.m_reviews import router as reviews_router
    app.include_router(reviews_router)
    log.info("✓ Reviews (تقييمات الحجوزات)")
except Exception as e:
    log.warning(f"Reviews: {e}")


# ──────────────────────────────────────────────────────────────
#  Auth helpers
# ──────────────────────────────────────────────────────────────
def _get_admin_token(request: Request) -> Optional[str]:
    return request.cookies.get("admin_token")


def _get_client_token(request: Request) -> Optional[str]:
    return request.cookies.get("client_token")


def require_admin(request: Request):
    token = _get_admin_token(request)
    with _lock:
        session = _admin_sessions.get(token) if token else None
    if not session:
        raise HTTPException(status_code=401, detail="غير مصرح")
    # H3 fix: فرض انتهاء صلاحية جلسة المدير على الخادم (8 ساعات)
    try:
        from db.security import session_is_expired
        if session_is_expired(session):
            with _lock:
                _admin_sessions.pop(token, None)
            raise HTTPException(status_code=401, detail="انتهت صلاحية الجلسة")
    except HTTPException:
        raise
    except Exception:
        pass
    return session


def get_client_session(request: Request) -> Optional[dict]:
    token = _get_client_token(request)
    if not token:
        return None
    with _lock:
        session = _client_sessions.get(token)
    # If not in memory (e.g. after restart), try PostgreSQL
    if session is None:
        try:
            db = getattr(request.app.state, "db", None)
            if db and db.use_postgres:
                row = db.execute(
                    """SELECT client_id, created_at FROM client_sessions
                       WHERE token=%s AND expires_at > NOW()""",
                    (token,), fetch="one"
                )
                if row:
                    session = {"client_id": row["client_id"],
                               "created_at": str(row["created_at"])}
                    with _lock:
                        _client_sessions[token] = session
        except Exception:
            pass
    if session is None:
        return None
    # Finding #8: enforce server-side session TTL (8 hours)
    try:
        from db.security import session_is_expired, is_token_revoked
    except Exception:
        return session  # security module unavailable — keep prior behavior
    # M5 fix: فشل-مغلق — أي خطأ في فحص الصلاحية/الإبطال يُبطل الجلسة بدل قبولها
    try:
        if session_is_expired(session):
            with _lock:
                _client_sessions.pop(token, None)
            return None
        db = getattr(request.app.state, "db", None)
        if db and is_token_revoked(db, token):
            with _lock:
                _client_sessions.pop(token, None)
            return None
    except Exception:
        log.warning("session check failed — rejecting session (fail-closed)")
        return None
    return session


def require_client(request: Request) -> dict:
    session = get_client_session(request)
    if not session:
        raise HTTPException(status_code=401, detail="غير مصرح")
    # Finding #3: enforce non-empty client_id
    if not session.get("client_id", "").strip():
        raise HTTPException(status_code=401, detail="جلسة غير صالحة — client_id مفقود")
    return session


# ──────────────────────────────────────────────────────────────
#  HTML Helpers
# ──────────────────────────────────────────────────────────────

from html_pages import _login_page, _admin_login_page, _admin_dashboard, _client_dashboard  # noqa: F401
