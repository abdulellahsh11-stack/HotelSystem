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

from fastapi import FastAPI, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles

from db.passwords import hash_password, verify_password


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
    """تجزئة PBKDF2 بالصيغة القديمة — للتحقق من الهاشات المخزَّنة فقط.

    لا تستخدمها لإنتاج هاش جديد؛ استخدم _make_password. مُبقاة لأن
    ADMIN_PASS_HASH المولَّد بـ scripts/gen_admin_hash.py بهذه الصيغة.
    """
    return hashlib.pbkdf2_hmac(
        "sha256", password.encode(), salt.encode(), 100_000
    ).hex()


def _make_password(password: str) -> tuple[str, str]:
    """يُنتج (هاش، ملح) لتخزينهما.

    الهاش الآن Argon2id موسوم بخوارزميته والملح مضمَّن داخله، فالحقل
    الثاني يعود فارغاً. يُعاد كزوج للحفاظ على توقيع الدالة لدى
    مواضع الاستدعاء التي تخزّن العمودين معاً.
    """
    return hash_password(password), ""


def _verify_password(password: str, client: dict, cfg, store=None) -> bool:
    """يتحقّق من كلمة المرور، ويُرقّي الهاش القديم بصمت عند النجاح.

    يدعم الصيغ الثلاث: Argon2id الجديدة، وscrypt، وسلسلة hex العارية
    القديمة (PBKDF2-100k بملح خارجي). حين ينجح التحقّق بصيغة قديمة
    ويُمرَّر store، تُعاد التجزئة بـ Argon2id وتُحفظ — فيترقّى الحساب
    عند أول دخول ناجح دون أن يُطلب من صاحبه تغيير كلمة مروره.
    """
    stored = client.get("pass_hash", "") or ""
    if not stored:
        return False

    legacy_salt = client.get("pass_salt") or cfg.pass_salt
    ok, needs_rehash = verify_password(password, stored, legacy_salt=legacy_salt)
    if not ok:
        return False

    if needs_rehash and store is not None:
        try:
            client["pass_hash"], client["pass_salt"] = _make_password(password)
            store.save_client(client)
            log.info(
                f"تُرقّي هاش كلمة مرور المنشأة {client.get('id', '?')} إلى Argon2id"
            )
        except Exception as e:
            # الترقية تحسين لا شرط للدخول — لا تُفشل تسجيل الدخول
            log.warning(f"تعذّرت ترقية هاش كلمة المرور: {e}")

    return True


def _verify_admin_password(password: str, cfg) -> bool:
    """يتحقّق من كلمة مرور المالك مقابل ADMIN_PASS_HASH.

    يقبل الصيغة الجديدة الموسومة والصيغة القديمة (hex عارٍ + PASS_SALT)
    حتى لا ينكسر أي نشر قائم قبل إعادة توليد الهاش.
    """
    ok, _ = verify_password(password, cfg.admin_pass_hash, legacy_salt=cfg.pass_salt)
    return ok


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

    # ── الترحيلات — الترتيب مقصود ─────────────────────────────────────────
    #
    # كل خطوة تفترض أن ما قبلها أنشأ جداوله. تحديداً:
    #   • التحصين الأمني يضيف branch_id إلى جداول تُنشئها v3
    #   • الأدوار والعزل الصفّي يجب أن يكونا في النهاية بعد وجود كل
    #     الجداول — كان ترتيبهما قبل v4، فلا تنال جداولُ v4 سياسة عزل
    #   • الفهارس بعد كل شيء لأنها تمسّ أعمدة أضافتها خطوات لاحقة
    from db.migrations import run_all_migrations
    from db.schema_v3 import (
        run_app_role_migration, run_perf_indexes, run_reporting_views,
        run_rls_migration, run_security_hardening, run_sessions_migration,
        run_staff_app_migrations, run_table_comments, run_v3_migrations,
        run_v4_migrations,
    )

    _MIGRATION_STEPS = [
        ("v1 schema",          run_all_migrations),
        ("v3 modules",         run_v3_migrations),
        ("staff app",          run_staff_app_migrations),
        ("v4 (ZATCA/audit)",   run_v4_migrations),
        ("sessions",           run_sessions_migration),
        ("security hardening", run_security_hardening),
        ("reporting views",    run_reporting_views),
        ("table comments",     run_table_comments),
        ("app role",           run_app_role_migration),
        ("row level security", run_rls_migration),
        ("perf indexes",       run_perf_indexes),
    ]

    _strict = os.environ.get("STRICT_MIGRATIONS", "").strip().lower() in ("1", "true", "yes")
    app_.state.migration_failures = []

    for _label, _step in _MIGRATION_STEPS:
        try:
            _step(db)
        except Exception as e:
            app_.state.migration_failures.append(_label)
            # الترحيلات الأمنية لا تُبتلع كتحذير: فشلها يعني عزل مستأجرين
            # ناقصاً، وهو ما يجب أن يُرى في السجل وفي /health.
            log.error(f"❌ ترحيل «{_label}» فشل: {e}")
            if _strict:
                raise

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


# مسارات لا تُسجَّل في سجل المراجعة: ضجيج تشغيلي لا قيمة تدقيقية له
_AUDIT_SKIP_PREFIXES = ("/api/health", "/api/status", "/static", "/api/telemetry")

# الدخول والخروج يُسجَّلان في مواضعهما بتفصيل أدق (نجاح/فشل/تجاوز حدّ)
_AUDIT_SKIP_EXACT = ("/api/login", "/api/admin/login")


@app.middleware("http")
async def audit_mutations(request: Request, call_next):
    """يُسجّل كل عملية تغيير في سجل المراجعة.

    الاعتماد على استدعاءات صريحة في كل مسار يعني أن أي مسار جديد يُنسى.
    الوسيط يضمن التغطية بحكم موقعه: ما يمرّ عبر HTTP يُسجَّل. الاستدعاءات
    الصريحة تبقى للأحداث التي تحتاج تفصيل «قبل/بعد».

    لا يُسجَّل إلا ما غيّر حالة فعلاً (استجابة أقل من 400)، وما عدا ذلك
    يُسجَّل كمحاولة فاشلة — وهي بدورها إشارة تحقيق مفيدة.
    """
    response = await call_next(request)

    method = request.method
    path = request.url.path
    if method not in ("POST", "PUT", "PATCH", "DELETE"):
        return response
    if path in _AUDIT_SKIP_EXACT or path.startswith(_AUDIT_SKIP_PREFIXES):
        return response

    try:
        db = getattr(request.app.state, "db", None)
        if not db or not getattr(db, "use_postgres", False):
            return response

        from services.audit import actor_from_session, audit

        session = None
        try:
            session = get_client_session(request)
        except Exception:
            pass
        is_admin = bool(_admin_sessions.get(_get_admin_token(request) or ""))
        if is_admin and not session:
            session = {"is_admin": True}

        actor_type, actor_id = actor_from_session(session)
        outcome = "ok" if response.status_code < 400 else "failed"

        audit(
            db,
            client_id=(session or {}).get("client_id"),
            action=f"{method.lower()}.{outcome}",
            actor_id=actor_id,
            actor_type=actor_type,
            table_name=None,
            record_id=path,
            new_data={"path": path, "status": response.status_code,
                      "query": str(request.url.query)[:500]},
            ip_address=request.client.host if request.client else None,
        )
    except Exception as e:
        # سجل المراجعة لا يُسقط الطلب بحال
        log.debug(f"audit middleware skipped: {e}")

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

try:
    from routes.pricing import router as pricing_router
    app.include_router(pricing_router)
    log.info("✓ Dynamic Pricing (التسعير الديناميكي)")
except Exception as e:
    log.warning(f"DynamicPricing router: {e}")


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
                    # نفس دور جلسة تسجيل الدخول: هذه جلسة حساب المنشأة،
                    # فصاحبها مالكها. بدون إعادة الدور هنا تفقد الجلسة
                    # المُستعادة بعد إعادة التشغيل صلاحياتها وتُرفض في
                    # المسارات المحروسة بالدور.
                    session = {"client_id": row["client_id"],
                               "created_at": str(row["created_at"]),
                               "role": "owner",
                               "permissions": ["*"]}
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

    # يربط المستأجر بسياق الطلب، فيضبطه DatabasePool على كل اتصال
    # يُستعار بعد هذه النقطة. بدونه تبقى app_tenant() بلا قيمة وترفض
    # سياساتُ RLS كلَّ الصفوف.
    from db.tenant_context import set_current_tenant
    set_current_tenant(session["client_id"].strip())

    return session


# ──────────────────────────────────────────────────────────────
#  HTML Helpers
# ──────────────────────────────────────────────────────────────

from html_pages import _login_page, _admin_login_page, _admin_dashboard, _client_dashboard  # noqa: E402, F401
