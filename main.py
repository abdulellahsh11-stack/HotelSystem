#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
main.py — ضيوف Hotel SaaS Platform v2.0
FastAPI application — replaces unified_server.py + old main.py (651KB)
dheuof.com
"""

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
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles

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

# M3 mitigation: حدّ بسيط لمعدّل التسجيل لكل IP (ضد إنشاء حسابات بالجملة)
_reg_attempts: dict = {}     # ip → [timestamps]
_REG_MAX_PER_HOUR = int(os.environ.get("REG_MAX_PER_HOUR", "5"))


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

    # Load optional Month-3 services
    try:
        from services.dynamic_pricing import DynamicPricingEngine
        from services.channel_manager import ChannelManager
        from services.api_keys import APIKeyManager
        app_.state.pricing = DynamicPricingEngine(db)
        app_.state.channels = ChannelManager(db)
        app_.state.api_keys = APIKeyManager(db)
        log.info("Month-3 services loaded")
    except Exception as e:
        log.warning(f"Month-3 services unavailable: {e}")
        app_.state.pricing = None
        app_.state.channels = None
        app_.state.api_keys = None

    yield

    db.close()


# ──────────────────────────────────────────────────────────────
#  App
# ──────────────────────────────────────────────────────────────
app = FastAPI(title="ضيوف — Dheuof Hotel SaaS", version="3.0.0", lifespan=lifespan, docs_url=None, redoc_url=None)

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
_NAV = """
<style>
*{box-sizing:border-box;margin:0;padding:0;font-family:'Segoe UI',Tahoma,Arial,sans-serif}
body{direction:rtl;background:#F8FAFC;color:#1e293b;min-height:100vh}
.sidebar{position:fixed;top:0;right:0;width:240px;height:100vh;background:#0F2640;padding:20px 0;overflow-y:auto;z-index:100}
.sidebar .logo{padding:0 20px 20px;border-bottom:1px solid rgba(255,255,255,.1);margin-bottom:10px}
.sidebar .logo h1{color:#fff;font-size:22px;font-weight:700}
.sidebar .logo small{color:#94a3b8;font-size:12px}
.sidebar a{display:flex;align-items:center;gap:10px;padding:12px 20px;color:#94a3b8;text-decoration:none;transition:.2s;font-size:14px;border-right:3px solid transparent}
.sidebar a:hover,.sidebar a.active{color:#fff;background:rgba(255,255,255,.07);border-right-color:#185FA5}
.sidebar a span.icon{font-size:18px}
.main{margin-right:240px;padding:24px;min-height:100vh}
.topbar{display:flex;justify-content:space-between;align-items:center;margin-bottom:24px}
.topbar h2{font-size:22px;font-weight:700;color:#0F2640}
.btn{display:inline-flex;align-items:center;gap:6px;padding:10px 20px;border-radius:8px;border:none;cursor:pointer;font-size:14px;font-weight:600;transition:.2s;text-decoration:none}
.btn-primary{background:#185FA5;color:#fff}.btn-primary:hover{background:#1a4f87}
.btn-success{background:#10B981;color:#fff}.btn-success:hover{background:#059669}
.btn-danger{background:#ef4444;color:#fff}.btn-danger:hover{background:#dc2626}
.btn-outline{background:transparent;color:#185FA5;border:2px solid #185FA5}.btn-outline:hover{background:#185FA5;color:#fff}
.card{background:#fff;border-radius:12px;box-shadow:0 1px 3px rgba(0,0,0,.08);padding:24px;margin-bottom:20px}
.card-title{font-size:16px;font-weight:700;color:#0F2640;margin-bottom:16px;padding-bottom:12px;border-bottom:2px solid #f1f5f9}
.stats-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(180px,1fr));gap:16px;margin-bottom:24px}
.stat-card{background:#fff;border-radius:12px;padding:20px;box-shadow:0 1px 3px rgba(0,0,0,.08);border-top:4px solid #185FA5}
.stat-card.green{border-top-color:#10B981}.stat-card.gold{border-top-color:#F59E0B}.stat-card.red{border-top-color:#ef4444}
.stat-card .value{font-size:28px;font-weight:800;color:#0F2640;margin:8px 0}
.stat-card .label{font-size:13px;color:#64748b;font-weight:500}
table{width:100%;border-collapse:collapse;font-size:14px}
th{background:#f8fafc;padding:12px 16px;text-align:right;font-weight:600;color:#475569;border-bottom:2px solid #e2e8f0}
td{padding:12px 16px;border-bottom:1px solid #f1f5f9;color:#334155}
tr:hover td{background:#f8fafc}
.badge{display:inline-block;padding:3px 10px;border-radius:20px;font-size:12px;font-weight:600}
.badge-green{background:#dcfce7;color:#166534}.badge-blue{background:#dbeafe;color:#1d4ed8}
.badge-yellow{background:#fef9c3;color:#854d0e}.badge-red{background:#fee2e2;color:#991b1b}
.form-group{margin-bottom:16px}
.form-group label{display:block;font-size:13px;font-weight:600;color:#475569;margin-bottom:6px}
.form-group input,.form-group select,.form-group textarea{width:100%;padding:10px 14px;border:2px solid #e2e8f0;border-radius:8px;font-size:14px;color:#334155;outline:none;transition:.2s}
.form-group input:focus,.form-group select:focus{border-color:#185FA5}
.alert{padding:12px 16px;border-radius:8px;margin-bottom:16px;font-size:14px}
.alert-error{background:#fee2e2;color:#991b1b;border:1px solid #fecaca}
.alert-success{background:#dcfce7;color:#166534;border:1px solid #bbf7d0}
@media(max-width:768px){.sidebar{width:100%;height:auto;position:relative}.main{margin-right:0}}
</style>
"""


_SEO_BASE = """<meta name="description" content="ضيوف — منصة إدارة الفنادق والشقق المخدومة الذكية في السعودية. حجوزات، نزلاء، فواتير، تقارير، واتساب.">
<meta name="keywords" content="نظام فنادق, إدارة فندق, شقق مخدومة, حجوزات, نزلاء, فواتير ضريبية, واتساب فندق, ضيوف, dheuof">
<meta name="robots" content="index, follow">
<meta property="og:title" content="ضيوف — منصة الضيافة الذكية">
<meta property="og:description" content="إدارة فندقك بذكاء — حجوزات، نزلاء، فواتير، تقارير متقدمة وأكثر من 17 وحدة.">
<meta property="og:type" content="website">
<meta property="og:locale" content="ar_SA">
<link rel="canonical" href="https://dheuof.com/">"""


def _login_page(error: str = "", ref_code: str = "") -> str:
    err_html = f'<div class="alert alert-error">{error}</div>' if error else ""
    ref_field = f'<input type="hidden" id="ref-code" value="{ref_code}">' if ref_code else '<input type="hidden" id="ref-code" value="">'
    return f"""<!DOCTYPE html>
<html lang="ar" dir="rtl">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>ضيوف — نظام إدارة الفنادق والشقق المخدومة</title>
{_SEO_BASE}
<style>
  *{{margin:0;padding:0;box-sizing:border-box}}
  body{{font-family:'Segoe UI',Tahoma,Arial,sans-serif;background:linear-gradient(135deg,#0F2640 0%,#185FA5 100%);min-height:100vh;display:flex;align-items:center;justify-content:center}}
  .card{{background:#fff;border-radius:16px;padding:48px 40px;width:100%;max-width:440px;box-shadow:0 20px 60px rgba(0,0,0,0.3)}}
  .logo{{text-align:center;margin-bottom:32px}}
  .logo h1{{color:#0F2640;font-size:2rem;font-weight:700}}
  .logo p{{color:#64748b;font-size:0.9rem;margin-top:4px}}
  .tabs{{display:flex;border-bottom:2px solid #e2e8f0;margin-bottom:28px}}
  .tab{{flex:1;padding:10px;text-align:center;cursor:pointer;color:#64748b;font-weight:500;transition:.2s}}
  .tab.active{{color:#185FA5;border-bottom:2px solid #185FA5;margin-bottom:-2px}}
  .form-group{{margin-bottom:20px}}
  label{{display:block;color:#374151;font-size:.875rem;font-weight:500;margin-bottom:6px}}
  input,select{{width:100%;padding:11px 14px;border:1.5px solid #d1d5db;border-radius:8px;font-size:.95rem;transition:.2s;font-family:inherit;color:#1e293b}}
  input:focus,select:focus{{outline:none;border-color:#185FA5;box-shadow:0 0 0 3px rgba(24,95,165,0.1)}}
  .btn{{width:100%;padding:13px;background:#185FA5;color:#fff;border:none;border-radius:8px;font-size:1rem;font-weight:600;cursor:pointer;transition:.2s;font-family:inherit}}
  .btn:hover{{background:#0F2640}}
  .alert-error{{background:#fef2f2;color:#dc2626;padding:10px 14px;border-radius:8px;font-size:.875rem;margin-bottom:16px}}
  .pane{{display:none}} .pane.active{{display:block}}
  .footer{{text-align:center;margin-top:24px;color:#9ca3af;font-size:.8rem}}
  .switch-link{{text-align:center;margin-top:16px;font-size:.85rem;color:#64748b}}
  .switch-link a{{color:#185FA5;text-decoration:none}}
</style>
</head>
<body>
<div class="card">
  <div class="logo">
    <h1>&#127960; ضيوف</h1>
    <p>نظام إدارة الفنادق والشقق المخدومة</p>
  </div>
  <div class="tabs">
    <div class="tab active" onclick="showTab('login')">تسجيل الدخول</div>
    <div class="tab" onclick="showTab('register')">تسجيل جديد</div>
  </div>

  <div id="err-msg" style="display:none" class="alert-error"></div>
  {err_html}

  <div id="pane-login" class="pane active">
    <div class="form-group">
      <label>معرّف المنشأة</label>
      <input type="text" id="login-id" placeholder="hotel-001" autocomplete="username">
    </div>
    <div class="form-group">
      <label>كلمة المرور</label>
      <input type="password" id="login-pass" placeholder="••••••••" autocomplete="current-password" onkeydown="if(event.key==='Enter')doLogin()">
    </div>
    <button class="btn" onclick="doLogin()">دخول</button>
  </div>

  <div id="pane-register" class="pane">
    {ref_field}
    <div class="form-group">
      <label>اسم المنشأة</label>
      <input type="text" id="reg-name" placeholder="فندق الواحة">
    </div>
    <div class="form-group">
      <label>معرّف المنشأة (للدخول لاحقاً)</label>
      <input type="text" id="reg-id" placeholder="hotel-001">
    </div>
    <div class="form-group">
      <label>كلمة المرور</label>
      <input type="password" id="reg-pass" placeholder="••••••••">
    </div>
    <div class="form-group">
      <label>مفتاح التفعيل (من الإدارة)</label>
      <input type="text" id="reg-key" placeholder="XXXX-XXXX-XXXX-XXXX">
    </div>
    <button class="btn" onclick="doRegister()">تسجيل وبدء التجربة</button>
  </div>

  <div class="footer">dheuof.com &copy; 2025 — منصة ضيوف للضيافة الذكية</div>
</div>
<script>
function showTab(t){{
  document.querySelectorAll('.tab').forEach((el,i)=>el.classList.toggle('active',i===(t==='login'?0:1)));
  document.querySelectorAll('.pane').forEach(el=>el.classList.remove('active'));
  document.getElementById('pane-'+t).classList.add('active');
  document.getElementById('err-msg').style.display='none';
}}
function showErr(msg){{var e=document.getElementById('err-msg');e.textContent=msg;e.style.display='block';}}
async function doLogin(){{
  const client_id=document.getElementById('login-id').value.trim();
  const password=document.getElementById('login-pass').value;
  if(!client_id||!password)return showErr('يرجى ملء جميع الحقول');
  const r=await fetch('/api/login',{{method:'POST',headers:{{'Content-Type':'application/x-www-form-urlencoded'}},body:'client_id='+encodeURIComponent(client_id)+'&password='+encodeURIComponent(password)}});
  if(r.redirected||r.ok){{location.href='/';return;}}
  const t=await r.text();
  showErr('بيانات الدخول غير صحيحة');
}}
async function doRegister(){{
  const name=document.getElementById('reg-name').value.trim();
  const id=document.getElementById('reg-id').value.trim();
  const pass=document.getElementById('reg-pass').value;
  const key=document.getElementById('reg-key').value.trim();
  const ref=document.getElementById('ref-code')?.value||'';
  if(!name||!id||!pass)return showErr('يرجى ملء جميع الحقول');
  const r=await fetch('/api/client/register',{{method:'POST',headers:{{'Content-Type':'application/json'}},body:JSON.stringify({{hotel_name:name,client_id:id,password:pass,activation_key:key,ref_code:ref}})}});
  const d=await r.json();
  if(d.ok||d.success)location.href='/';else showErr(d.error||'خطأ في التسجيل');
}}
</script>
</body>
</html>"""


def _admin_login_page(error: str = "") -> str:
    err_html = f'<div class="alert-error">{error}</div>' if error else ""
    return f"""<!DOCTYPE html>
<html lang="ar" dir="rtl">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>ضيوف — لوحة الإدارة</title>
<style>
  *{{margin:0;padding:0;box-sizing:border-box}}
  body{{font-family:'Segoe UI',Tahoma,Arial,sans-serif;background:#0F2640;min-height:100vh;display:flex;align-items:center;justify-content:center}}
  .card{{background:#fff;border-radius:16px;padding:48px 40px;width:100%;max-width:380px;box-shadow:0 20px 60px rgba(0,0,0,0.4)}}
  .logo{{text-align:center;margin-bottom:32px}}
  .logo h1{{color:#0F2640;font-size:1.8rem;font-weight:700}}
  .logo span{{display:inline-block;background:#0F2640;color:#F59E0B;padding:4px 12px;border-radius:20px;font-size:.75rem;margin-top:6px}}
  .form-group{{margin-bottom:20px}}
  label{{display:block;color:#374151;font-size:.875rem;font-weight:500;margin-bottom:6px}}
  input{{width:100%;padding:11px 14px;border:1.5px solid #d1d5db;border-radius:8px;font-size:.95rem;transition:.2s;font-family:inherit}}
  input:focus{{outline:none;border-color:#0F2640}}
  .btn{{width:100%;padding:13px;background:#0F2640;color:#fff;border:none;border-radius:8px;font-size:1rem;font-weight:600;cursor:pointer;font-family:inherit}}
  .btn:hover{{background:#185FA5}}
  .alert-error{{background:#fef2f2;color:#dc2626;padding:10px 14px;border-radius:8px;font-size:.875rem;margin-bottom:16px}}
</style>
</head>
<body>
<div class="card">
  <div class="logo">
    <h1>&#127960; ضيوف</h1>
    <span>لوحة التحكم الرئيسية</span>
  </div>
  {err_html}
  <div class="form-group">
    <label>كلمة المرور</label>
    <input type="password" id="pass" placeholder="••••••••" onkeydown="if(event.key==='Enter')doLogin()">
  </div>
  <button class="btn" onclick="doLogin()">دخول</button>
</div>
<script>
async function doLogin(){{
  const password=document.getElementById('pass').value;
  if(!password)return;
  const r=await fetch('/api/admin/login',{{method:'POST',headers:{{'Content-Type':'application/x-www-form-urlencoded'}},body:'password='+encodeURIComponent(password)}});
  if(r.ok||r.redirected){{location.href='/admin';return;}}
  document.querySelector('.card').insertAdjacentHTML('afterbegin','<div class="alert-error">كلمة المرور غير صحيحة</div>');
}}
</script>
</body>
</html>"""


def _admin_dashboard(clients: list, stats: dict) -> str:
    return """<!DOCTYPE html>
<html lang="ar" dir="rtl">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1.0">
<title>ضيوف — لوحة الإدارة</title>
<style>
*{box-sizing:border-box;margin:0;padding:0}
body{font-family:'Segoe UI',Tahoma,sans-serif;background:#f0f4f8;color:#1e293b;display:flex;min-height:100vh;direction:rtl}
.sidebar{width:220px;background:#0F2640;min-height:100vh;display:flex;flex-direction:column;position:fixed;right:0;top:0;bottom:0;z-index:100}
.sidebar .logo{padding:24px 20px;border-bottom:1px solid rgba(255,255,255,.1)}
.sidebar .logo h1{color:#fff;font-size:1.4rem;font-weight:700}
.sidebar .logo small{color:#94a3b8;font-size:.75rem}
.sidebar a{display:flex;align-items:center;gap:10px;padding:12px 20px;color:#cbd5e1;text-decoration:none;font-size:.875rem;transition:.2s}
.sidebar a:hover,.sidebar a.active{background:rgba(255,255,255,.1);color:#fff}
.sidebar a .icon{font-size:1rem}
.sidebar .spacer{flex:1}
.main{margin-right:220px;flex:1;padding:0;min-height:100vh}
.topbar{background:#fff;padding:16px 28px;display:flex;justify-content:space-between;align-items:center;box-shadow:0 1px 4px rgba(0,0,0,.08);position:sticky;top:0;z-index:50}
.topbar h2{font-size:1rem;font-weight:600;color:#0F2640}
.content{padding:24px 28px}
.stat-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(160px,1fr));gap:16px;margin-bottom:24px}
.stat{background:#fff;border-radius:12px;padding:18px 20px;box-shadow:0 1px 3px rgba(0,0,0,.06);border-top:3px solid #185FA5}
.stat.g{border-top-color:#10B981}.stat.y{border-top-color:#F59E0B}.stat.r{border-top-color:#ef4444}.stat.p{border-top-color:#8b5cf6}
.stat .val{font-size:1.8rem;font-weight:700;color:#0F2640}.stat .lbl{font-size:.75rem;color:#64748b;margin-top:4px}
.card{background:#fff;border-radius:12px;padding:20px 24px;box-shadow:0 1px 3px rgba(0,0,0,.06);margin-bottom:20px}
.card-hdr{display:flex;justify-content:space-between;align-items:center;margin-bottom:16px;padding-bottom:12px;border-bottom:1px solid #f1f5f9}
.card-hdr h3{font-size:.9rem;font-weight:600;color:#0F2640}
table{width:100%;border-collapse:collapse;font-size:.825rem}
th{background:#f8fafc;padding:10px 12px;text-align:right;font-weight:600;color:#64748b;border-bottom:2px solid #e2e8f0}
td{padding:10px 12px;border-bottom:1px solid #f1f5f9;vertical-align:middle}
tr:hover td{background:#fafbfc}
.badge{display:inline-block;padding:3px 10px;border-radius:20px;font-size:.75rem;font-weight:600}
.bg{background:#dcfce7;color:#16a34a}.by{background:#fef9c3;color:#ca8a04}.br{background:#fee2e2;color:#dc2626}.bb{background:#dbeafe;color:#1d4ed8}.bp{background:#ede9fe;color:#7c3aed}
.btn{border:none;padding:7px 14px;border-radius:8px;cursor:pointer;font-size:.8rem;font-weight:600;transition:.2s}
.btn-p{background:#185FA5;color:#fff}.btn-p:hover{background:#0F4A8A}
.btn-g{background:#10B981;color:#fff}.btn-g:hover{background:#059669}
.btn-r{background:#ef4444;color:#fff}.btn-r:hover{background:#dc2626}
.btn-s{background:#f1f5f9;color:#374151}.btn-s:hover{background:#e2e8f0}
.btn-y{background:#F59E0B;color:#fff}.btn-y:hover{background:#D97706}
.pane{display:none}.pane.active{display:block}
.alert-exp{background:#fef3c7;border:1px solid #fbbf24;border-radius:8px;padding:10px 14px;font-size:.8rem;color:#92400e;margin-bottom:8px}
.dot{width:8px;height:8px;border-radius:50%;display:inline-block;margin-left:6px}
.dot-g{background:#10B981}.dot-y{background:#F59E0B}.dot-r{background:#ef4444}
.modal-bg{display:none;position:fixed;inset:0;background:rgba(0,0,0,.5);z-index:999;align-items:center;justify-content:center}
.modal-bg.open{display:flex}
.modal{background:#fff;border-radius:16px;padding:28px;width:100%;max-width:520px;max-height:90vh;overflow-y:auto}
.modal h4{font-size:1rem;font-weight:700;color:#0F2640;margin-bottom:20px}
.fg{margin-bottom:14px}
.fg label{display:block;font-size:.8rem;font-weight:600;color:#374151;margin-bottom:5px}
.fg input,.fg select{width:100%;padding:8px 12px;border:1.5px solid #e2e8f0;border-radius:8px;font-size:.875rem;outline:none}
.fg input:focus,.fg select:focus{border-color:#185FA5}
.fg-row{display:grid;grid-template-columns:1fr 1fr;gap:12px}
.tag{display:inline-block;background:#e0f2fe;color:#0369a1;padding:2px 8px;border-radius:4px;font-size:.7rem;font-weight:600;margin-left:4px}
</style>
</head>
<body>
<div class="sidebar">
  <div class="logo"><h1>ضيوف</h1><small>لوحة الإدارة</small></div>
  <a href="#" class="active" onclick="nav('overview',this)"><span class="icon">&#128200;</span> الرئيسية</a>
  <a href="#" onclick="nav('clients',this)"><span class="icon">&#127970;</span> المنشآت</a>
  <a href="#" onclick="nav('sessions',this)"><span class="icon">&#128101;</span> الجلسات النشطة</a>
  <a href="#" onclick="nav('subs',this)"><span class="icon">&#128203;</span> الاشتراكات</a>
  <a href="#" onclick="nav('packages',this)"><span class="icon">&#128176;</span> أسعار الباقات</a>
  <a href="#" onclick="nav('employees',this)"><span class="icon">&#128188;</span> الموظفون</a>
  <a href="#" onclick="nav('modules',this)"><span class="icon">&#9881;</span> التحكم بالوحدات</a>
  <a href="#" onclick="nav('marketers',this)"><span class="icon">&#128279;</span> المسوقون</a>
  <a href="#" onclick="nav('tickets',this)"><span class="icon">&#127917;</span> الدعم</a>
  <div class="spacer"></div>
  <a href="/api/health" target="_blank"><span class="icon">&#128154;</span> الصحة</a>
  <a href="/api/admin/logout" style="color:#f87171"><span class="icon">&#128682;</span> خروج</a>
</div>
<div class="main">
  <div class="topbar">
    <h2 id="page-title">الرئيسية</h2>
    <div style="display:flex;gap:10px;align-items:center">
      <span id="clock" style="font-size:.8rem;color:#94a3b8"></span>
      <button class="btn btn-s" onclick="refreshAll()" title="تحديث">&#8635; تحديث</button>
      <a href="/api/admin/logout" class="btn btn-r">خروج</a>
    </div>
  </div>

  <div class="content">

  <!-- ═══════════ OVERVIEW ═══════════ -->
  <div id="pane-overview" class="pane active">
    <div class="stat-grid">
      <div class="stat"><div class="val" id="st-total">-</div><div class="lbl">إجمالي المنشآت</div></div>
      <div class="stat g"><div class="val" id="st-active">-</div><div class="lbl">نشطة</div></div>
      <div class="stat y"><div class="val" id="st-trial">-</div><div class="lbl">تجريبي</div></div>
      <div class="stat r"><div class="val" id="st-suspended">-</div><div class="lbl">موقوفة</div></div>
      <div class="stat p"><div class="val" id="st-sessions">-</div><div class="lbl">جلسات نشطة الآن</div></div>
      <div class="stat"><div class="val" id="st-revenue">-</div><div class="lbl">الإيرادات (ر.س)</div></div>
    </div>
    <div id="expiry-alerts"></div>
    <div class="card">
      <div class="card-hdr"><h3>آخر المنشآت المسجلة</h3></div>
      <table><thead><tr><th>المنشأة</th><th>الخطة</th><th>الحالة</th><th>تاريخ التسجيل</th></tr></thead>
      <tbody id="ov-recent"></tbody></table>
    </div>
  </div>

  <!-- ═══════════ CLIENTS ═══════════ -->
  <div id="pane-clients" class="pane">
    <div class="card">
      <div class="card-hdr">
        <h3>جميع المنشآت</h3>
        <div style="display:flex;gap:8px">
          <button class="btn btn-p" onclick="openAddModal()">+ إضافة</button>
          <button class="btn btn-g" onclick="generateKey()">+ مفتاح تفعيل</button>
          <button class="btn" style="background:#fef3c7;color:#92400e;border-color:#fcd34d" onclick="openOwnerSetup()">&#128081; حساب المالك</button>
        </div>
      </div>
      <div id="key-result" style="display:none;background:#f0fdf4;padding:10px 14px;border-radius:8px;margin-bottom:14px;font-weight:700;color:#16a34a;letter-spacing:2px;font-size:.9rem"></div>
      <div style="overflow-x:auto">
      <table><thead><tr>
        <th>المنشأة</th><th>الخطة</th><th>الحالة</th><th>انتهاء الاشتراك</th><th>تاريخ التسجيل</th><th>إجراءات</th>
      </tr></thead>
      <tbody id="clients-body"></tbody></table>
      </div>
    </div>
  </div>

  <!-- ═══════════ SESSIONS ═══════════ -->
  <div id="pane-sessions" class="pane">
    <div class="card">
      <div class="card-hdr">
        <h3>الجلسات النشطة الآن</h3>
        <button class="btn btn-s" onclick="loadSessions()">&#8635; تحديث</button>
      </div>
      <table><thead><tr>
        <th>المنشأة</th><th>وقت الدخول</th><th>المدة</th><th>إجراء</th>
      </tr></thead>
      <tbody id="sessions-body"></tbody></table>
    </div>
  </div>

  <!-- ═══════════ SUBSCRIPTIONS ═══════════ -->
  <div id="pane-subs" class="pane">
    <div class="card">
      <div class="card-hdr"><h3>إدارة الاشتراكات</h3><button class="btn btn-s" onclick="loadSubs()">&#8635; تحديث</button></div>
      <div style="overflow-x:auto">
      <table><thead><tr>
        <th>المنشأة</th><th>الخطة</th><th>الحالة</th><th>بداية</th><th>نهاية</th><th>المتبقي</th><th>السعر</th><th>تعديل</th>
      </tr></thead>
      <tbody id="subs-body"></tbody></table>
      </div>
    </div>
  </div>

  <!-- ═══════════ PACKAGES (public pricing) ═══════════ -->
  <div id="pane-packages" class="pane">
    <div class="card">
      <div class="card-hdr">
        <h3>&#128176; أسعار الباقات المعروضة للزوار</h3>
        <div style="display:flex;gap:8px;align-items:center">
          <a href="/static/dheuof/packages.html" target="_blank" class="btn btn-s">&#128065; معاينة الصفحة</a>
          <button class="btn btn-s" onclick="loadPackages()">&#8635; تحديث</button>
        </div>
      </div>
      <p style="font-size:.8rem;color:#64748b;margin-bottom:16px">عدّل الأسعار والنصوص هنا — تظهر فوراً في صفحة الباقات العامة <code>/packages.html</code> بدون لمس الكود.</p>
      <div id="pkg-edit-grid" style="display:grid;grid-template-columns:repeat(auto-fill,minmax(280px,1fr));gap:16px"></div>
      <div style="margin-top:18px;padding-top:14px;border-top:1px solid #f1f5f9">
        <button class="btn btn-p" onclick="savePackages()">&#10003; حفظ الأسعار</button>
        <span id="pkg-saved" style="display:none;color:#16a34a;font-size:.8rem;margin-right:10px">&#10003; تم الحفظ — ظهرت في الصفحة العامة</span>
      </div>
    </div>
  </div>

  <!-- ═══════════ EMPLOYEES ═══════════ -->
  <div id="pane-employees" class="pane">
    <div class="card">
      <div class="card-hdr">
        <h3>سجل الموظفين</h3>
        <div style="display:flex;gap:8px;align-items:center">
          <select id="emp-filter" onchange="loadEmployees()" style="padding:6px 10px;border:1.5px solid #e2e8f0;border-radius:8px;font-size:.8rem">
            <option value="">كل المنشآت</option>
          </select>
          <button class="btn btn-s" onclick="loadEmployees()">&#8635; تحديث</button>
        </div>
      </div>
      <table><thead><tr>
        <th>المنشأة</th><th>الموظف</th><th>الدور</th><th>آخر نشاط</th><th>عدد المهام</th>
      </tr></thead>
      <tbody id="emp-body"></tbody></table>
    </div>
  </div>

  <!-- ═══════════ MODULES ═══════════ -->
  <div id="pane-modules" class="pane">
    <div class="card">
      <div class="card-hdr">
        <h3>التحكم بالوحدات لكل منشأة</h3>
        <select id="mod-client-sel" onchange="loadModules()" style="padding:6px 10px;border:1.5px solid #e2e8f0;border-radius:8px;font-size:.8rem">
          <option value="">-- اختر منشأة --</option>
        </select>
      </div>
      <div id="modules-grid" style="display:grid;grid-template-columns:repeat(auto-fill,minmax(200px,1fr));gap:12px;margin-top:4px"></div>
      <div id="modules-save-row" style="display:none;margin-top:16px;padding-top:14px;border-top:1px solid #f1f5f9">
        <button class="btn btn-p" onclick="saveModules()">&#10003; حفظ التغييرات</button>
        <span id="mod-saved" style="display:none;color:#16a34a;font-size:.8rem;margin-right:10px">&#10003; تم الحفظ</span>
      </div>
    </div>
  </div>

  <!-- ═══════════ MARKETERS ═══════════ -->
  <div id="pane-marketers" class="pane">
    <div class="card">
      <div class="card-hdr">
        <h3>&#128279; المسوقون وروابطهم التسويقية</h3>
        <div style="display:flex;gap:8px">
          <button class="btn btn-p" onclick="openAddMktr()">+ إضافة مسوق</button>
          <button class="btn btn-s" onclick="loadMarketers()">&#8635; تحديث</button>
        </div>
      </div>
      <div id="mktr-link-info" style="display:none;background:#f0fdf4;padding:10px 14px;border-radius:8px;margin-bottom:14px;font-size:.8rem;color:#166534;word-break:break-all"></div>
      <table><thead><tr>
        <th>اسم المسوق</th><th>كود الإحالة</th><th>رابط التسجيل</th><th>التسجيلات</th><th>العمولة %</th><th>الحالة</th><th>إجراءات</th>
      </tr></thead>
      <tbody id="mktr-body"></tbody></table>
    </div>
  </div>

  <!-- ═══════════ TICKETS ═══════════ -->
  <div id="pane-tickets" class="pane">
    <div class="card">
      <div class="card-hdr"><h3>تذاكر الدعم</h3><button class="btn btn-s" onclick="loadTickets()">&#8635; تحديث</button></div>
      <table><thead><tr>
        <th>المنشأة</th><th>الموضوع</th><th>الحالة</th><th>التاريخ</th><th>رد</th>
      </tr></thead>
      <tbody id="tickets-body"></tbody></table>
    </div>
  </div>

  </div>
</div>

<!-- Modal: Add Client -->
<div class="modal-bg" id="modal-add">
  <div class="modal">
    <h4>إضافة منشأة جديدة</h4>
    <div class="fg"><label>معرف المنشأة (ID)</label><input id="nc-id" placeholder="hotel-001"></div>
    <div class="fg"><label>اسم المنشأة</label><input id="nc-name" placeholder="فندق النخبة"></div>
    <div class="fg"><label>البريد الإلكتروني</label><input id="nc-email" type="email" placeholder="hotel@example.com"></div>
    <div class="fg"><label>كلمة المرور</label><input id="nc-pass" type="password"></div>
    <div class="fg"><label>الخطة</label>
      <select id="nc-plan">
        <option value="trial">تجريبي (trial)</option>
        <option value="starter">مبدئي (starter)</option>
        <option value="operations">تشغيلي (operations)</option>
        <option value="professional">احترافي (professional)</option>
        <option value="enterprise">مؤسسي (enterprise)</option>
      </select>
    </div>
    <div id="nc-err" style="display:none;color:#dc2626;font-size:.8rem;margin-bottom:10px"></div>
    <div style="display:flex;gap:10px">
      <button class="btn btn-p" style="flex:1" onclick="addClient()">إضافة</button>
      <button class="btn btn-s" style="flex:1" onclick="closeModal('modal-add')">إلغاء</button>
    </div>
  </div>
</div>

<!-- Modal: Owner Account Setup -->
<div class="modal-bg" id="modal-owner">
  <div class="modal">
    <h4 style="color:#92400e">&#128081; إعداد حساب المالك</h4>
    <p style="font-size:.8rem;color:#6b7280;margin-bottom:14px">يُنشئ أو يُحدِّث حساباً بخطة Enterprise مدى الحياة مع تمييز خاص في لوحة التحكم.</p>
    <div class="fg"><label>معرف الحساب (ID)</label><input id="own-id" placeholder="dheuof-owner" value="dheuof"></div>
    <div class="fg"><label>اسم المنشأة</label><input id="own-name" placeholder="ضيوف للاستضافة الذكية" value="ضيوف للاستضافة الذكية"></div>
    <div class="fg"><label>البريد الإلكتروني</label><input id="own-email" type="email" placeholder="abdulellah.sh11@gmail.com" value="abdulellah.sh11@gmail.com"></div>
    <div class="fg"><label>كلمة المرور</label><input id="own-pass" type="password" placeholder="اختر كلمة مرور قوية"></div>
    <div id="own-result" style="display:none;padding:10px;border-radius:8px;font-size:.8rem;margin-bottom:10px"></div>
    <div style="display:flex;gap:10px">
      <button class="btn" style="flex:1;background:#fef3c7;color:#92400e;border-color:#fcd34d" onclick="saveOwnerSetup()">&#10003; حفظ حساب المالك</button>
      <button class="btn btn-s" style="flex:1" onclick="closeModal('modal-owner')">إلغاء</button>
    </div>
  </div>
</div>

<!-- Modal: Edit Subscription -->
<div class="modal-bg" id="modal-sub">
  <div class="modal">
    <h4>تعديل اشتراك: <span id="sub-edit-name"></span></h4>
    <input type="hidden" id="sub-edit-cid">
    <div class="fg-row">
      <div class="fg"><label>الخطة</label>
        <select id="sub-plan">
          <option value="trial">trial</option>
          <option value="starter">starter</option>
          <option value="operations">operations</option>
          <option value="professional">professional</option>
          <option value="enterprise">enterprise</option>
        </select>
      </div>
      <div class="fg"><label>الحالة</label>
        <select id="sub-status">
          <option value="trial">تجريبي</option>
          <option value="active">نشط</option>
          <option value="suspended">موقوف</option>
          <option value="expired">منتهي</option>
        </select>
      </div>
    </div>
    <div class="fg-row">
      <div class="fg"><label>تاريخ البداية</label><input type="date" id="sub-start"></div>
      <div class="fg"><label>تاريخ الانتهاء</label><input type="date" id="sub-end"></div>
    </div>
    <div class="fg"><label>السعر الشهري (ر.س)</label><input type="number" id="sub-price" min="0" step="0.01"></div>
    <div id="sub-err" style="display:none;color:#dc2626;font-size:.8rem;margin-bottom:10px"></div>
    <div style="display:flex;gap:10px;margin-top:16px">
      <button class="btn btn-p" style="flex:1" onclick="saveSub()">حفظ</button>
      <button class="btn btn-s" style="flex:1" onclick="closeModal('modal-sub')">إلغاء</button>
    </div>
  </div>
</div>

<!-- Modal: Client Detail (employees + password reset) -->
<div class="modal-bg" id="modal-client-detail">
  <div class="modal" style="max-width:680px">
    <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:18px">
      <h4 id="detail-title" style="margin:0">تفاصيل المنشأة</h4>
      <button onclick="closeModal('modal-client-detail')" style="background:none;border:none;cursor:pointer;font-size:1.3rem;color:#94a3b8">&#10005;</button>
    </div>
    <!-- Manager section -->
    <div style="background:#f8fafc;border-radius:10px;padding:14px 16px;margin-bottom:16px">
      <div style="font-size:.8rem;font-weight:700;color:#0F2640;margin-bottom:10px">&#128272; بيانات المدير / الدخول</div>
      <div class="fg-row">
        <div class="fg"><label>كلمة مرور جديدة</label><input type="password" id="mgr-pass" placeholder="اتركها فارغة للإبقاء"></div>
        <div class="fg" style="display:flex;align-items:flex-end">
          <button class="btn btn-y" style="width:100%" onclick="resetManagerPass()">&#128274; تغيير كلمة المرور</button>
        </div>
      </div>
      <div id="mgr-msg" style="font-size:.8rem;margin-top:6px;display:none"></div>
    </div>
    <!-- Employees section -->
    <div style="font-size:.8rem;font-weight:700;color:#0F2640;margin-bottom:10px">&#128188; الموظفون في هذه المنشأة</div>
    <div style="overflow-x:auto;max-height:280px;overflow-y:auto">
    <table><thead><tr><th>الاسم</th><th>الدور</th><th>آخر نشاط</th><th>عدد المهام</th></tr></thead>
    <tbody id="detail-emp-body"></tbody></table>
    </div>
    <input type="hidden" id="detail-cid">
  </div>
</div>

<!-- Modal: Add Marketer -->
<div class="modal-bg" id="modal-mktr">
  <div class="modal">
    <h4>إضافة مسوق جديد</h4>
    <div class="fg"><label>الاسم</label><input id="mk-name" placeholder="اسم المسوق"></div>
    <div class="fg-row">
      <div class="fg"><label>كود الإحالة (اختياري)</label><input id="mk-code" placeholder="ABC123 — يُولَّد تلقائياً"></div>
      <div class="fg"><label>نسبة العمولة %</label><input type="number" id="mk-comm" value="10" min="0" max="100"></div>
    </div>
    <div class="fg-row">
      <div class="fg"><label>رقم الهاتف</label><input id="mk-phone" placeholder="+9665xxxxxxxx"></div>
      <div class="fg"><label>البريد الإلكتروني</label><input id="mk-email" placeholder="marketer@email.com"></div>
    </div>
    <div class="fg"><label>ملاحظات</label><input id="mk-notes" placeholder="ملاحظات اختيارية"></div>
    <div id="mk-err" style="display:none;color:#dc2626;font-size:.8rem;margin-bottom:10px"></div>
    <div style="display:flex;gap:10px">
      <button class="btn btn-p" style="flex:1" onclick="addMarketer()">إضافة</button>
      <button class="btn btn-s" style="flex:1" onclick="closeModal('modal-mktr')">إلغاء</button>
    </div>
  </div>
</div>

<!-- Modal: Marketer Referrals -->
<div class="modal-bg" id="modal-refs">
  <div class="modal" style="max-width:640px">
    <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:16px">
      <h4 id="refs-title" style="margin:0">تسجيلات المسوق</h4>
      <button onclick="closeModal('modal-refs')" style="background:none;border:none;cursor:pointer;font-size:1.3rem;color:#94a3b8">&#10005;</button>
    </div>
    <div id="refs-link" style="background:#f0fdf4;padding:10px 14px;border-radius:8px;margin-bottom:14px;font-size:.8rem;color:#166534;word-break:break-all"></div>
    <table><thead><tr><th>المنشأة</th><th>الخطة</th><th>تاريخ التسجيل</th></tr></thead>
    <tbody id="refs-body"></tbody></table>
  </div>
</div>

<!-- Modal: Ticket Reply -->
<div class="modal-bg" id="modal-ticket">
  <div class="modal">
    <h4>الرد على التذكرة</h4>
    <input type="hidden" id="tk-id">
    <div class="fg"><label>الرد</label><textarea id="tk-reply" rows="4" style="width:100%;padding:8px 12px;border:1.5px solid #e2e8f0;border-radius:8px;font-size:.875rem;resize:vertical"></textarea></div>
    <div style="display:flex;gap:10px">
      <button class="btn btn-p" style="flex:1" onclick="sendReply()">إرسال</button>
      <button class="btn btn-s" style="flex:1" onclick="closeModal('modal-ticket')">إلغاء</button>
    </div>
  </div>
</div>

<script>
const PLANS={trial:'تجريبي',starter:'مبدئي',operations:'تشغيلي',professional:'احترافي',enterprise:'مؤسسي'};
const STATUS_AR={active:'نشط',trial:'تجريبي',suspended:'موقوف',expired:'منتهي'};
const STATUS_CLS={active:'bg',trial:'by',suspended:'br',expired:'br'};
let _clients=[];

function tick(){
  const n=new Date();
  document.getElementById('clock').textContent=n.toLocaleDateString('ar-SA',{weekday:'short',year:'numeric',month:'short',day:'numeric'})+' '+n.toLocaleTimeString('ar-SA');
}
setInterval(tick,1000);tick();

function nav(id,el){
  document.querySelectorAll('.pane').forEach(p=>p.classList.remove('active'));
  document.querySelectorAll('.sidebar a').forEach(a=>a.classList.remove('active'));
  document.getElementById('pane-'+id).classList.add('active');
  if(el){el.classList.add('active');}
  const titles={overview:'الرئيسية',clients:'المنشآت',sessions:'الجلسات النشطة',subs:'الاشتراكات',packages:'أسعار الباقات',employees:'الموظفون',modules:'التحكم بالوحدات',tickets:'تذاكر الدعم',marketers:'المسوقون'};
  document.getElementById('page-title').textContent=titles[id]||id;
  if(id==='clients')loadClients();
  else if(id==='sessions')loadSessions();
  else if(id==='subs')loadSubs();
  else if(id==='packages')loadPackages();
  else if(id==='employees')loadEmployees();
  else if(id==='modules')initModulesPane();
  else if(id==='tickets')loadTickets();
  else if(id==='marketers')loadMarketers();
}

function refreshAll(){loadOverview();const active=document.querySelector('.pane.active')?.id?.replace('pane-','');if(active&&active!=='overview')nav(active);}

function openModal(id){document.getElementById(id).classList.add('open');}
function closeModal(id){document.getElementById(id).classList.remove('open');}
function openAddModal(){['nc-id','nc-name','nc-email','nc-pass'].forEach(id=>{const el=document.getElementById(id);if(el)el.value='';});document.getElementById('nc-err').style.display='none';openModal('modal-add');}
function openOwnerSetup(){document.getElementById('own-result').style.display='none';openModal('modal-owner');}
async function saveOwnerSetup(){
  const cid=document.getElementById('own-id').value.trim();
  const name=document.getElementById('own-name').value.trim();
  const email=document.getElementById('own-email').value.trim();
  const pass=document.getElementById('own-pass').value;
  const res=document.getElementById('own-result');
  if(!cid||!name||!pass){res.style.display='block';res.style.background='#fee2e2';res.style.color='#dc2626';res.textContent='جميع الحقول مطلوبة';return;}
  const r=await fetch('/api/admin/owner-setup',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({client_id:cid,name,email,password:pass})});
  const d=await r.json();
  if(d.success){res.style.display='block';res.style.background='#f0fdf4';res.style.color='#16a34a';res.textContent='✓ تم إنشاء حساب المالك — ينتهي الاشتراك: '+d.sub_end;loadClients();loadSubs();}
  else{res.style.display='block';res.style.background='#fee2e2';res.style.color='#dc2626';res.textContent=d.error||'خطأ';}
}

// ─── Overview ───────────────────────────────────────────────
async function loadOverview(){
  const [cr,sr]=await Promise.all([
    fetch('/api/admin/clients').then(r=>r.json()).catch(()=>({})),
    fetch('/api/admin/sessions').then(r=>r.json()).catch(()=>({}))
  ]);
  const clients=cr.clients||[];_clients=clients;
  const total=clients.length;
  const active=clients.filter(c=>c.status==='active').length;
  const trial=clients.filter(c=>c.status==='trial').length;
  const susp=clients.filter(c=>c.status==='suspended').length;
  const sessions=(sr.sessions||[]).length;
  document.getElementById('st-total').textContent=total;
  document.getElementById('st-active').textContent=active;
  document.getElementById('st-trial').textContent=trial;
  document.getElementById('st-suspended').textContent=susp;
  document.getElementById('st-sessions').textContent=sessions;
  // revenue from subscriptions
  let rev=0;
  clients.forEach(c=>{if(c.sub_price)rev+=parseFloat(c.sub_price)||0;});
  document.getElementById('st-revenue').textContent=rev.toLocaleString('ar-SA',{minimumFractionDigits:0});
  // expiry alerts
  const alerts=document.getElementById('expiry-alerts');
  alerts.innerHTML='';
  const today=new Date();
  clients.forEach(c=>{
    if(c.sub_end){
      const end=new Date(c.sub_end);
      const days=Math.ceil((end-today)/86400000);
      if(days<=14&&days>=0){
        alerts.innerHTML+=`<div class="alert-exp">⚠️ <strong>${c.name||c.id}</strong> — اشتراكه ينتهي خلال <strong>${days}</strong> يوم (${c.sub_end})</div>`;
      }else if(days<0){
        alerts.innerHTML+=`<div class="alert-exp" style="background:#fee2e2;border-color:#fca5a5;color:#7f1d1d">🔴 <strong>${c.name||c.id}</strong> — اشتراكه انتهى منذ ${Math.abs(days)} يوم</div>`;
      }
    }
  });
  // recent
  const recent=[...clients].sort((a,b)=>new Date(b.created_at||0)-new Date(a.created_at||0)).slice(0,5);
  document.getElementById('ov-recent').innerHTML=recent.map(c=>{
    const sc=STATUS_CLS[c.status]||'bb';
    return `<tr><td><strong>${c.name||c.id}</strong><br><small style="color:#94a3b8">${c.id}</small></td>
      <td><span class="badge bb">${PLANS[c.plan]||c.plan||'—'}</span></td>
      <td><span class="badge ${sc}">${STATUS_AR[c.status]||c.status}</span></td>
      <td>${(c.created_at||'').substring(0,10)||'—'}</td></tr>`;
  }).join('')||'<tr><td colspan="4" style="text-align:center;color:#94a3b8;padding:24px">لا توجد بيانات</td></tr>';
}

// ─── Clients ────────────────────────────────────────────────
async function loadClients(){
  const r=await fetch('/api/admin/clients').then(r=>r.json()).catch(()=>({}));
  const clients=r.clients||[];_clients=clients;
  document.getElementById('clients-body').innerHTML=clients.map(c=>{
    const sc=STATUS_CLS[c.status]||'bb';
    const end=c.sub_end?`<span style="font-weight:600">${c.sub_end}</span>`:'<span style="color:#94a3b8">—</span>';
    const days=c.sub_end?Math.ceil((new Date(c.sub_end)-new Date())/86400000):null;
    const daysTag=days!==null?(days<0?`<span class="tag" style="background:#fee2e2;color:#dc2626">منتهي</span>`:(days<=14?`<span class="tag" style="background:#fef3c7;color:#92400e">${days}y</span>`:`<span class="tag" style="background:#dcfce7;color:#16a34a">${days}y</span>`)): '';
    const ownerBadge=c.is_owner?'<span class="badge" style="background:#fef3c7;color:#92400e;margin-right:4px">&#128081; مالك</span>':''
    return `<tr${c.is_owner?' style="background:#fffbeb"':''}>
      <td><strong>${c.name||c.id}</strong>${ownerBadge}<br><small style="color:#94a3b8;font-size:11px">${c.id}</small>${c.email?`<br><small style="color:#6b7280;font-size:10px">&#9993; ${c.email}</small>`:''}</td>
      <td><span class="badge bb">${PLANS[c.plan]||c.plan||'—'}</span></td>
      <td><span class="badge ${sc}">${STATUS_AR[c.status]||c.status}</span></td>
      <td>${end} ${daysTag}</td>
      <td>${(c.created_at||'').substring(0,10)||'—'}</td>
      <td style="white-space:nowrap">
        <button class="btn btn-p" onclick="openClientDetail('${c.id}')" style="margin-left:4px">&#128065; تفاصيل</button>
        <button class="btn btn-s" onclick="editSub('${c.id}')" style="margin-left:4px">&#9998; اشتراك</button>
        <button class="btn btn-s" onclick="toggleClient('${c.id}')" style="margin-left:4px">تبديل</button>
        <button class="btn btn-r" onclick="deleteClient('${c.id}')">حذف</button>
      </td>
    </tr>`;
  }).join('')||'<tr><td colspan="6" style="text-align:center;color:#94a3b8;padding:32px">لا توجد منشآت</td></tr>';
}

async function addClient(){
  const id=document.getElementById('nc-id').value.trim();
  const name=document.getElementById('nc-name').value.trim();
  const email=document.getElementById('nc-email').value.trim();
  const pass=document.getElementById('nc-pass').value;
  const plan=document.getElementById('nc-plan').value;
  const err=document.getElementById('nc-err');
  if(!id||!name||!pass){err.textContent='جميع الحقول مطلوبة';err.style.display='block';return;}
  const r=await fetch('/api/admin/clients',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({id,name,email,password:pass,plan})});
  const d=await r.json();
  if(d.success){closeModal('modal-add');loadClients();loadOverview();}
  else{err.textContent=d.error||'خطأ';err.style.display='block';}
}

async function toggleClient(id){
  await fetch('/api/admin/clients/'+id+'/toggle',{method:'POST'});
  loadClients();loadOverview();
}

async function deleteClient(id){
  if(!confirm('هل تريد حذف هذه المنشأة نهائياً؟'))return;
  await fetch('/api/admin/clients/'+id,{method:'DELETE'});
  loadClients();loadOverview();
}

async function generateKey(){
  const plan=prompt('الخطة (trial/starter/operations/professional/enterprise):','trial');
  if(!plan)return;
  const days=parseInt(prompt('عدد الأيام:','30'))||30;
  const r=await fetch('/api/admin/keys/generate',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({plan,days})});
  const d=await r.json();
  if(d.key){const el=document.getElementById('key-result');el.style.display='block';el.textContent='🔑 المفتاح: '+d.key;}
}

// ─── Sessions ───────────────────────────────────────────────
async function loadSessions(){
  const r=await fetch('/api/admin/sessions').then(r=>r.json()).catch(()=>({}));
  const sessions=r.sessions||[];
  document.getElementById('st-sessions').textContent=sessions.length;
  const now=new Date();
  document.getElementById('sessions-body').innerHTML=sessions.map(s=>{
    const created=new Date(s.created_at);
    const mins=Math.floor((now-created)/60000);
    const dur=mins<60?`${mins} دقيقة`:`${Math.floor(mins/60)}س ${mins%60}د`;
    return `<tr>
      <td><strong>${s.client_name||s.client_id}</strong><br><small style="color:#94a3b8">${s.client_id}</small></td>
      <td>${s.created_at.replace('T',' ').substring(0,19)}</td>
      <td><span class="dot dot-g"></span>${dur}</td>
      <td><button class="btn btn-r" style="padding:4px 10px;font-size:.75rem" onclick="revokeSession('${s.token_prefix}')">إنهاء</button></td>
    </tr>`;
  }).join('')||'<tr><td colspan="4" style="text-align:center;color:#94a3b8;padding:32px">لا توجد جلسات نشطة</td></tr>';
}

async function revokeSession(prefix){
  if(!confirm('هل تريد إنهاء هذه الجلسة؟'))return;
  await fetch('/api/admin/sessions/'+prefix+'/revoke',{method:'POST'});
  loadSessions();
}

// ─── Subscriptions ──────────────────────────────────────────
async function loadSubs(){
  const r=await fetch('/api/admin/subscriptions').then(r=>r.json()).catch(()=>({}));
  const subs=r.subscriptions||[];
  const today=new Date();
  document.getElementById('subs-body').innerHTML=subs.map(s=>{
    const end=s.sub_end?new Date(s.sub_end):null;
    const days=end?Math.ceil((end-today)/86400000):null;
    let daysHtml='—';
    if(days!==null){
      if(days<0)daysHtml=`<span style="color:#dc2626;font-weight:600">انتهى منذ ${Math.abs(days)}ي</span>`;
      else if(days<=14)daysHtml=`<span style="color:#d97706;font-weight:600">${days} يوم</span>`;
      else daysHtml=`<span style="color:#16a34a;font-weight:600">${days} يوم</span>`;
    }
    const sc=STATUS_CLS[s.status]||'bb';
    const ownerTag=s.is_owner?'<span class="badge" style="background:#fef3c7;color:#92400e;margin-right:4px">&#128081;</span>':'';
    return `<tr${s.is_owner?' style="background:#fffbeb"':''}>
      <td><strong>${ownerTag}${s.name||s.client_id}</strong><br><small style="color:#94a3b8">${s.client_id}</small></td>
      <td><span class="badge bb">${PLANS[s.plan]||s.plan||'—'}</span></td>
      <td><span class="badge ${sc}">${STATUS_AR[s.status]||s.status}</span></td>
      <td>${s.sub_start||'—'}</td>
      <td>${s.sub_end||'—'}</td>
      <td>${daysHtml}</td>
      <td>${s.price?parseFloat(s.price).toLocaleString('ar-SA'):'—'} ر.س</td>
      <td><button class="btn btn-y" onclick="editSub('${s.client_id}')">&#9998; تعديل</button></td>
    </tr>`;
  }).join('')||'<tr><td colspan="8" style="text-align:center;color:#94a3b8;padding:32px">لا توجد اشتراكات</td></tr>';
}

function editSub(cid){
  const c=_clients.find(x=>x.id===cid)||{id:cid};
  document.getElementById('sub-edit-cid').value=cid;
  document.getElementById('sub-edit-name').textContent=c.name||cid;
  document.getElementById('sub-plan').value=c.plan||'trial';
  document.getElementById('sub-status').value=c.status||'trial';
  document.getElementById('sub-start').value=c.sub_start||'';
  document.getElementById('sub-end').value=c.sub_end||'';
  document.getElementById('sub-price').value=c.sub_price||'';
  document.getElementById('sub-err').style.display='none';
  openModal('modal-sub');
}

async function saveSub(){
  const cid=document.getElementById('sub-edit-cid').value;
  const body={
    plan:document.getElementById('sub-plan').value,
    status:document.getElementById('sub-status').value,
    sub_start:document.getElementById('sub-start').value,
    sub_end:document.getElementById('sub-end').value,
    sub_price:parseFloat(document.getElementById('sub-price').value)||0
  };
  const r=await fetch('/api/admin/subscriptions/'+cid,{method:'PUT',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});
  const d=await r.json();
  if(d.success){closeModal('modal-sub');loadClients();loadSubs();loadOverview();}
  else{const e=document.getElementById('sub-err');e.textContent=d.error||'خطأ';e.style.display='block';}
}

// ─── Public Packages (pricing) ──────────────────────────────
let _packages=[];
async function loadPackages(){
  const r=await fetch('/api/packages').then(r=>r.json()).catch(()=>({}));
  _packages=r.packages||[];
  const esc=s=>String(s==null?'':s).replace(/"/g,'&quot;');
  document.getElementById('pkg-edit-grid').innerHTML=_packages.map((p,i)=>`
    <div style="background:#f8fafc;border:1px solid #e2e8f0;border-radius:12px;padding:16px">
      <div style="font-size:.7rem;color:#94a3b8;font-family:monospace;margin-bottom:8px">${esc(p.id)}</div>
      <div class="fg"><label>اسم الباقة</label><input data-pk="${i}" data-pf="name_ar" value="${esc(p.name_ar)}"></div>
      <div class="fg-row">
        <div class="fg"><label>السعر</label><input data-pk="${i}" data-pf="price" value="${esc(p.price)}" placeholder="٢٬٤٠٠ أو حسب الطلب"></div>
        <div class="fg"><label>العملة</label><input data-pk="${i}" data-pf="currency" value="${esc(p.currency)}" placeholder="ر.س"></div>
      </div>
      <div class="fg"><label>المدة</label><input data-pk="${i}" data-pf="period" value="${esc(p.period)}" placeholder="/شهر"></div>
      <div class="fg"><label>ملاحظة التوفير (اختياري)</label><input data-pk="${i}" data-pf="save_note" value="${esc(p.save_note)}" placeholder="توفير ١٬٢٠٠ ر.س شهرياً"></div>
      <div class="fg"><label>نص الزر</label><input data-pk="${i}" data-pf="cta" value="${esc(p.cta)}" placeholder="ابدأ التجربة"></div>
    </div>`).join('');
  document.getElementById('pkg-saved').style.display='none';
}

async function savePackages(){
  document.querySelectorAll('#pkg-edit-grid input[data-pk]').forEach(inp=>{
    const i=+inp.getAttribute('data-pk');const f=inp.getAttribute('data-pf');
    if(_packages[i])_packages[i][f]=inp.value;
  });
  const r=await fetch('/api/admin/packages',{method:'PUT',headers:{'Content-Type':'application/json'},body:JSON.stringify({packages:_packages})});
  const d=await r.json();
  if(d.success){_packages=d.packages||_packages;const s=document.getElementById('pkg-saved');s.style.display='inline';setTimeout(()=>s.style.display='none',4000);}
  else alert(d.error||'خطأ في الحفظ');
}

// ─── Employees ──────────────────────────────────────────────
async function loadEmployees(){
  const filterCid=document.getElementById('emp-filter').value;
  const url='/api/admin/employees'+(filterCid?'?client_id='+filterCid:'');
  const r=await fetch(url).then(r=>r.json()).catch(()=>({}));
  const emps=r.employees||[];
  // populate filter
  const sel=document.getElementById('emp-filter');
  const cur=sel.value;
  if(sel.options.length<=1){
    _clients.forEach(c=>{const o=document.createElement('option');o.value=c.id;o.textContent=c.name||c.id;sel.appendChild(o);});
    sel.value=cur;
  }
  document.getElementById('emp-body').innerHTML=emps.map(e=>{
    return `<tr>
      <td><strong>${e.client_name||e.client_id}</strong></td>
      <td>${e.name||'—'}</td>
      <td><span class="badge bb">${e.role||'—'}</span></td>
      <td>${e.last_active?(e.last_active.replace('T',' ').substring(0,19)):'—'}</td>
      <td>${e.task_count||0}</td>
    </tr>`;
  }).join('')||'<tr><td colspan="5" style="text-align:center;color:#94a3b8;padding:32px">لا توجد بيانات</td></tr>';
}

// ─── Tickets ────────────────────────────────────────────────
async function loadTickets(){
  const r=await fetch('/api/admin/tickets').then(r=>r.json()).catch(()=>({}));
  const tickets=r.tickets||[];
  document.getElementById('tickets-body').innerHTML=tickets.map(t=>{
    const sc=t.status==='open'?'br':'bg';
    return `<tr>
      <td>${t.client_id||'—'}</td>
      <td>${t.subject||'—'}</td>
      <td><span class="badge ${sc}">${t.status==='open'?'مفتوح':'مغلق'}</span></td>
      <td>${(t.created_at||'').substring(0,10)}</td>
      <td><button class="btn btn-s" style="padding:4px 10px;font-size:.75rem" onclick="openReply('${t.id}')">رد</button></td>
    </tr>`;
  }).join('')||'<tr><td colspan="5" style="text-align:center;color:#94a3b8;padding:32px">لا توجد تذاكر</td></tr>';
}

function openReply(id){document.getElementById('tk-id').value=id;document.getElementById('tk-reply').value='';openModal('modal-ticket');}
async function sendReply(){
  const id=document.getElementById('tk-id').value;
  const reply=document.getElementById('tk-reply').value.trim();
  if(!reply)return;
  await fetch('/api/admin/tickets/reply',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({id,reply})});
  closeModal('modal-ticket');loadTickets();
}

// ─── Client Detail (Manager + Employees) ────────────────────
async function openClientDetail(cid){
  const c=_clients.find(x=>x.id===cid)||{id:cid,name:cid};
  document.getElementById('detail-cid').value=cid;
  document.getElementById('detail-title').textContent='تفاصيل: '+(c.name||cid);
  document.getElementById('mgr-pass').value='';
  document.getElementById('mgr-msg').style.display='none';
  document.getElementById('detail-emp-body').innerHTML='<tr><td colspan="4" style="text-align:center;padding:20px;color:#94a3b8">جاري التحميل...</td></tr>';
  openModal('modal-client-detail');
  // load employees for this client
  const r=await fetch('/api/admin/employees?client_id='+cid).then(r=>r.json()).catch(()=>({}));
  const emps=r.employees||[];
  document.getElementById('detail-emp-body').innerHTML=emps.length?emps.map(e=>`<tr>
    <td><strong>${e.name||'—'}</strong></td>
    <td><span class="badge bb">${e.role||'—'}</span></td>
    <td>${e.last_active?(e.last_active.replace('T',' ').substring(0,19)):'لم يسجل نشاط'}</td>
    <td>${e.task_count||0}</td>
  </tr>`).join(''):'<tr><td colspan="4" style="text-align:center;padding:20px;color:#94a3b8">لا يوجد موظفون مسجلون</td></tr>';
}

async function resetManagerPass(){
  const cid=document.getElementById('detail-cid').value;
  const pass=document.getElementById('mgr-pass').value.trim();
  const msg=document.getElementById('mgr-msg');
  if(!pass){msg.textContent='أدخل كلمة المرور الجديدة';msg.style.color='#dc2626';msg.style.display='block';return;}
  const r=await fetch('/api/admin/clients/'+cid+'/reset-password',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({password:pass})});
  const d=await r.json();
  if(d.success){msg.textContent='✓ تم تغيير كلمة المرور بنجاح';msg.style.color='#16a34a';}
  else{msg.textContent=d.error||'خطأ';msg.style.color='#dc2626';}
  msg.style.display='block';
  document.getElementById('mgr-pass').value='';
}

// ─── Modules ────────────────────────────────────────────────
const ALL_MODULES=[
  {id:'M01',name:'الاستقبال'},{id:'M02',name:'النزلاء'},{id:'M03',name:'الفواتير'},
  {id:'M04',name:'نقطة البيع'},{id:'M05',name:'الإشراف الداخلي'},{id:'M06',name:'المستودع'},
  {id:'M07',name:'الصيانة'},{id:'M08',name:'واتساب'},{id:'M09',name:'الحجوزات'},
  {id:'M10',name:'التسويق'},{id:'M11',name:'إدارة القنوات'},{id:'M12',name:'الذكاء الاصطناعي'},
  {id:'M13',name:'التقارير'},{id:'M14',name:'الموظفون'},{id:'M15',name:'السياحة'},
  {id:'M16',name:'المفاتيح الإلكترونية'},{id:'M17',name:'الحجوزات الخارجية'},
];
const PLAN_MODULES={
  trial:['M01','M02'],
  starter:['M01','M02','M07'],
  operations:['M01','M02','M05','M07','M08','M13'],
  professional:['M01','M02','M03','M04','M05','M06','M07','M08','M11','M13'],
  enterprise:ALL_MODULES.map(m=>m.id)
};

function initModulesPane(){
  const sel=document.getElementById('mod-client-sel');
  if(sel.options.length<=1){
    _clients.forEach(c=>{const o=document.createElement('option');o.value=c.id;o.textContent=(c.name||c.id)+' ('+c.plan+')';sel.appendChild(o);});
  }
}

function loadModules(){
  const cid=document.getElementById('mod-client-sel').value;
  const grid=document.getElementById('modules-grid');
  if(!cid){grid.innerHTML='';document.getElementById('modules-save-row').style.display='none';return;}
  const c=_clients.find(x=>x.id===cid)||{plan:'trial'};
  const enabledByPlan=PLAN_MODULES[c.plan]||[];
  const customEnabled=c.enabled_modules||enabledByPlan;
  grid.innerHTML=ALL_MODULES.map(m=>{
    const checked=customEnabled.includes(m.id);
    const byPlan=enabledByPlan.includes(m.id);
    return `<label style="display:flex;align-items:center;gap:8px;background:${checked?'#f0fdf4':'#f8fafc'};border:1.5px solid ${checked?'#86efac':'#e2e8f0'};border-radius:10px;padding:12px 14px;cursor:pointer;transition:.2s">
      <input type="checkbox" value="${m.id}" ${checked?'checked':''} onchange="onModuleToggle()" style="width:16px;height:16px;accent-color:#10B981">
      <div>
        <div style="font-weight:600;font-size:.82rem;color:#0F2640">${m.id}</div>
        <div style="font-size:.75rem;color:#64748b">${m.name}</div>
        ${byPlan?'<span style="font-size:.65rem;color:#059669">✓ مشمول في الخطة</span>':''}
      </div>
    </label>`;
  }).join('');
  document.getElementById('modules-save-row').style.display='block';
  document.getElementById('mod-saved').style.display='none';
}

function onModuleToggle(){
  const checkboxes=document.querySelectorAll('#modules-grid input[type=checkbox]');
  checkboxes.forEach(cb=>{
    const lbl=cb.closest('label');
    const on=cb.checked;
    lbl.style.background=on?'#f0fdf4':'#f8fafc';
    lbl.style.borderColor=on?'#86efac':'#e2e8f0';
  });
}

async function saveModules(){
  const cid=document.getElementById('mod-client-sel').value;
  if(!cid)return;
  const enabled=[...document.querySelectorAll('#modules-grid input[type=checkbox]:checked')].map(cb=>cb.value);
  const r=await fetch('/api/admin/clients/'+cid+'/modules',{method:'PUT',headers:{'Content-Type':'application/json'},body:JSON.stringify({enabled_modules:enabled})});
  const d=await r.json();
  if(d.success){
    const saved=document.getElementById('mod-saved');
    saved.style.display='inline';
    setTimeout(()=>saved.style.display='none',3000);
    // update local cache
    const c=_clients.find(x=>x.id===cid);
    if(c)c.enabled_modules=enabled;
  }
}

// ─── Marketers ──────────────────────────────────────────────
function _refLink(code){return location.origin+'/ref/'+code;}

async function loadMarketers(){
  const r=await fetch('/api/admin/marketers').then(r=>r.json()).catch(()=>({}));
  const mkts=r.marketers||[];
  document.getElementById('mktr-body').innerHTML=mkts.map(m=>{
    const link=_refLink(m.ref_code);
    const sc=m.status==='active'?'bg':'br';
    return `<tr>
      <td><strong>${m.name}</strong>${m.phone?`<br><small style="color:#94a3b8">${m.phone}</small>`:''}</td>
      <td><code style="background:#f1f5f9;padding:2px 8px;border-radius:4px;font-size:.8rem">${m.ref_code}</code></td>
      <td>
        <input readonly value="${link}" style="width:200px;font-size:.72rem;padding:4px 8px;border:1px solid #e2e8f0;border-radius:6px;background:#f8fafc">
        <button onclick="copyLink('${link}')" style="background:#185FA5;color:#fff;border:none;padding:4px 8px;border-radius:5px;cursor:pointer;font-size:.72rem;margin-right:4px">نسخ</button>
      </td>
      <td><span style="font-weight:700;color:#185FA5">${m.referral_count||0}</span> تسجيل</td>
      <td>${m.commission_rate||10}%</td>
      <td><span class="badge ${sc}">${m.status==='active'?'نشط':'موقوف'}</span></td>
      <td style="white-space:nowrap">
        <button class="btn btn-p" onclick="viewRefs(${m.id},'${m.name}','${m.ref_code}')" style="margin-left:4px">&#128065; عرض</button>
        <button class="btn btn-r" onclick="deactivateMktr(${m.id})">تعطيل</button>
      </td>
    </tr>`;
  }).join('')||'<tr><td colspan="7" style="text-align:center;color:#94a3b8;padding:32px">لا يوجد مسوقون</td></tr>';
}

function copyLink(link){navigator.clipboard.writeText(link).catch(()=>{});const el=document.getElementById('mktr-link-info');el.style.display='block';el.textContent='✓ تم نسخ الرابط: '+link;setTimeout(()=>el.style.display='none',4000);}

function openAddMktr(){['mk-name','mk-code','mk-email','mk-phone','mk-notes'].forEach(id=>{const el=document.getElementById(id);if(el)el.value='';});document.getElementById('mk-comm').value='10';document.getElementById('mk-err').style.display='none';openModal('modal-mktr');}

async function addMarketer(){
  const name=document.getElementById('mk-name').value.trim();
  const err=document.getElementById('mk-err');
  if(!name){err.textContent='الاسم مطلوب';err.style.display='block';return;}
  const body={name,phone:document.getElementById('mk-phone').value,email:document.getElementById('mk-email').value,ref_code:document.getElementById('mk-code').value.trim().toUpperCase()||'',commission_rate:parseFloat(document.getElementById('mk-comm').value)||10,notes:document.getElementById('mk-notes').value};
  const r=await fetch('/api/admin/marketers',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});
  const d=await r.json();
  if(d.success){closeModal('modal-mktr');loadMarketers();const link=_refLink(d.marketer.ref_code);const el=document.getElementById('mktr-link-info');el.style.display='block';el.textContent='✓ أُضيف المسوق — الرابط: '+link;}
  else{err.textContent=d.error||'خطأ';err.style.display='block';}
}

async function deactivateMktr(id){if(!confirm('تعطيل هذا المسوق؟'))return;await fetch('/api/admin/marketers/'+id,{method:'DELETE'});loadMarketers();}

async function viewRefs(id,name,code){
  document.getElementById('refs-title').textContent='تسجيلات: '+name;
  document.getElementById('refs-link').textContent='رابط الإحالة: '+_refLink(code);
  openModal('modal-refs');
  const r=await fetch('/api/admin/marketers/'+id+'/referrals').then(r=>r.json()).catch(()=>({}));
  const refs=r.referrals||[];
  document.getElementById('refs-body').innerHTML=refs.length?refs.map(ref=>`<tr>
    <td><strong>${ref.client_name||ref.client_id}</strong></td>
    <td><span class="badge bb">${PLANS[ref.plan]||ref.plan||'trial'}</span></td>
    <td>${(ref.converted_at||'').substring(0,10)}</td>
  </tr>`).join(''):'<tr><td colspan="3" style="text-align:center;color:#94a3b8;padding:24px">لا توجد تسجيلات بعد</td></tr>';
}

// Auto-refresh overview every 30s
setInterval(loadOverview,30000);
loadOverview();
</script>
</body>
</html>"""


def _client_dashboard(client: dict) -> str:
    name = client.get("name", client.get("hotel_name", client.get("id", "المنشأة")))
    cid = client.get("id", "")
    plan = client.get("plan", "starter")

    return f"""<!DOCTYPE html>
<html lang="ar" dir="rtl">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>ضيوف — {name}</title>
{_NAV}
<style>
  .kpi-grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(200px,1fr));gap:16px;margin-bottom:24px}}
  .kpi-card{{background:#fff;border-radius:12px;padding:20px 22px;box-shadow:0 1px 4px rgba(0,0,0,.06);border-top:3px solid #185FA5}}
  .kpi-card.green{{border-top-color:#10B981}}.kpi-card.gold{{border-top-color:#F59E0B}}.kpi-card.purple{{border-top-color:#8b5cf6}}
  .kpi-card .val{{font-size:1.9rem;font-weight:700;color:#0F2640;margin-bottom:4px}}
  .kpi-card .lbl{{font-size:.8rem;color:#64748b}}
  .section{{background:#fff;border-radius:12px;padding:22px 24px;box-shadow:0 1px 4px rgba(0,0,0,.06);margin-bottom:20px}}
  .section-hdr{{display:flex;justify-content:space-between;align-items:center;margin-bottom:16px;padding-bottom:12px;border-bottom:1px solid #f1f5f9}}
  .section-hdr h3{{font-size:.95rem;font-weight:600;color:#0F2640}}
  .modal-overlay{{display:none;position:fixed;inset:0;background:rgba(0,0,0,.45);z-index:1000;align-items:center;justify-content:center}}
  .modal-overlay.open{{display:flex}}
  .modal{{background:#fff;border-radius:14px;padding:28px;width:100%;max-width:500px;box-shadow:0 20px 60px rgba(0,0,0,.2);max-height:90vh;overflow-y:auto}}
  .modal h4{{margin-bottom:20px;color:#0F2640;font-size:1rem;font-weight:600}}
  .form-row{{display:grid;grid-template-columns:1fr 1fr;gap:12px}}
  .modal-actions{{display:flex;gap:10px;justify-content:flex-end;margin-top:20px;padding-top:16px;border-top:1px solid #f1f5f9}}
  .empty{{text-align:center;padding:32px;color:#94a3b8;font-size:.875rem}}
  .notif-item{{background:#f8fafc;border-radius:8px;padding:12px 14px;border-right:3px solid #185FA5;margin-bottom:8px}}
  .notif-item.warn{{border-right-color:#F59E0B}}
  .ai-box{{background:#f0f9ff;border:1px solid #bae6fd;border-radius:10px;padding:16px;margin-top:16px;white-space:pre-wrap;font-size:.875rem;color:#0369a1;min-height:60px}}
  .channel-card{{background:#f8fafc;border-radius:10px;padding:18px;margin-bottom:14px;border:1.5px solid #e2e8f0}}
  .channel-card h4{{font-size:.9rem;font-weight:600;color:#0F2640;margin-bottom:12px}}
  .pane-section{{display:none}}.pane-section.active{{display:block}}
</style>
</head>
<body>
<div class="sidebar">
  <div class="logo"><h1>ضيوف</h1><small id="s-hotel-name">{name}</small></div>
  <a href="#" class="active" onclick="showSection('home')"><span class="icon">&#128200;</span> الرئيسية</a>
  <a href="#" onclick="showSection('guests')"><span class="icon">&#128101;</span> النزلاء</a>
  <a href="#" onclick="showSection('bookings')"><span class="icon">&#128197;</span> الحجوزات</a>
  <a href="#" onclick="showSection('invoices')"><span class="icon">&#128203;</span> الفواتير</a>
  <a href="#" onclick="showSection('pos')"><span class="icon">&#128184;</span> نقطة البيع</a>
  <a href="#" onclick="showSection('reports')"><span class="icon">&#128202;</span> التقارير</a>
  <a href="#" onclick="showSection('channels')"><span class="icon">&#127760;</span> القنوات</a>
  <a href="#" onclick="showSection('ai')"><span class="icon">&#129504;</span> الرؤى الذكية</a>
  <a href="#" onclick="showSection('support')"><span class="icon">&#127917;</span> الدعم</a>
  <a href="#" onclick="showSection('settings')"><span class="icon">&#9881;</span> الإعدادات</a>
  <a href="/api/logout" style="color:#ef4444;margin-top:auto"><span class="icon">&#128682;</span> خروج</a>
</div>
<div class="main">
  <div class="topbar">
    <h2 id="page-title">لوحة التحكم</h2>
    <div style="display:flex;align-items:center;gap:12px">
      <span id="sub-badge" class="badge badge-blue">{plan}</span>
      <a href="/api/logout" class="btn btn-danger" style="padding:8px 14px">خروج</a>
    </div>
  </div>

  <!-- HOME -->
  <div id="sec-home" class="pane-section active">
    <div class="kpi-grid">
      <div class="kpi-card"><div class="val" id="kpi-active">-</div><div class="lbl">حجوزات نشطة</div></div>
      <div class="kpi-card green"><div class="val" id="kpi-guests">-</div><div class="lbl">إجمالي النزلاء</div></div>
      <div class="kpi-card gold"><div class="val" id="kpi-revenue">-</div><div class="lbl">إيرادات هذا الشهر (ر.س)</div></div>
      <div class="kpi-card purple"><div class="val" id="kpi-monthly">-</div><div class="lbl">حجوزات هذا الشهر</div></div>
    </div>
    <div class="section">
      <div class="section-hdr"><h3>آخر الحجوزات</h3><button class="btn btn-primary" style="padding:6px 14px;font-size:13px" onclick="showSection('bookings')">عرض الكل</button></div>
      <div style="overflow-x:auto"><table id="tbl-home-bk">
        <thead><tr><th>النزيل</th><th>الغرفة</th><th>الوصول</th><th>المغادرة</th><th>الحالة</th></tr></thead>
        <tbody><tr><td colspan="5" class="empty">جارٍ التحميل...</td></tr></tbody>
      </table></div>
    </div>
    <div class="section">
      <div class="section-hdr"><h3>الإشعارات</h3></div>
      <div id="notif-list"><div class="empty">لا توجد إشعارات</div></div>
    </div>
  </div>

  <!-- GUESTS -->
  <div id="sec-guests" class="pane-section">
    <div class="section">
      <div class="section-hdr"><h3>النزلاء</h3><button class="btn btn-primary" style="padding:6px 14px;font-size:13px" onclick="openModal('m-guest')">+ نزيل جديد</button></div>
      <div style="overflow-x:auto"><table id="tbl-guests">
        <thead><tr><th>الاسم</th><th>رقم الهوية</th><th>الجنسية</th><th>الهاتف</th><th>الحالة</th></tr></thead>
        <tbody><tr><td colspan="5" class="empty">لا يوجد نزلاء</td></tr></tbody>
      </table></div>
    </div>
  </div>

  <!-- BOOKINGS -->
  <div id="sec-bookings" class="pane-section">
    <div class="section">
      <div class="section-hdr"><h3>الحجوزات</h3><button class="btn btn-primary" style="padding:6px 14px;font-size:13px" onclick="openModal('m-booking')">+ حجز جديد</button></div>
      <div style="overflow-x:auto"><table id="tbl-bookings">
        <thead><tr><th>رقم الحجز</th><th>النزيل</th><th>الوصول</th><th>المغادرة</th><th>المبلغ</th><th>الحالة</th></tr></thead>
        <tbody><tr><td colspan="6" class="empty">لا توجد حجوزات</td></tr></tbody>
      </table></div>
    </div>
  </div>

  <!-- INVOICES -->
  <div id="sec-invoices" class="pane-section">
    <div class="section">
      <div class="section-hdr"><h3>الفواتير</h3><button class="btn btn-primary" style="padding:6px 14px;font-size:13px" onclick="openModal('m-invoice')">+ فاتورة جديدة</button></div>
      <div style="overflow-x:auto"><table id="tbl-invoices">
        <thead><tr><th>رقم الفاتورة</th><th>التاريخ</th><th>المبلغ</th><th>الحالة</th><th>إجراء</th></tr></thead>
        <tbody><tr><td colspan="5" class="empty">لا توجد فواتير</td></tr></tbody>
      </table></div>
    </div>
  </div>

  <!-- POS -->
  <div id="sec-pos" class="pane-section">
    <div class="section">
      <div class="section-hdr"><h3>نقطة البيع</h3><button class="btn btn-primary" style="padding:6px 14px;font-size:13px" onclick="openModal('m-pos')">+ معاملة جديدة</button></div>
      <div style="overflow-x:auto"><table id="tbl-pos">
        <thead><tr><th>التاريخ</th><th>الفئة</th><th>الوصف</th><th>المبلغ</th><th>الدفع</th></tr></thead>
        <tbody><tr><td colspan="5" class="empty">لا توجد معاملات</td></tr></tbody>
      </table></div>
    </div>
  </div>

  <!-- REPORTS -->
  <div id="sec-reports" class="pane-section">
    <div class="kpi-grid">
      <div class="kpi-card"><div class="val" id="rep-bk">-</div><div class="lbl">إجمالي الحجوزات</div></div>
      <div class="kpi-card green"><div class="val" id="rep-rev">-</div><div class="lbl">إجمالي الإيرادات (ر.س)</div></div>
    </div>
    <div class="section">
      <div class="section-hdr"><h3>الإيرادات الشهرية</h3></div>
      <div style="overflow-x:auto"><table id="tbl-monthly">
        <thead><tr><th>الشهر</th><th>الإيرادات (ر.س)</th></tr></thead>
        <tbody></tbody>
      </table></div>
    </div>
  </div>

  <!-- CHANNELS -->
  <div id="sec-channels" class="pane-section">
    <div class="section">
      <div class="section-hdr"><h3>إدارة القنوات</h3></div>
      <div class="channel-card">
        <h4>&#127760; Booking.com</h4>
        <div class="form-row">
          <div class="form-group"><label>Hotel ID</label><input id="bc-hotel" placeholder="12345678"></div>
          <div class="form-group"><label>API Key</label><input id="bc-key" type="password" placeholder="••••••••"></div>
        </div>
        <button class="btn btn-primary" style="padding:8px 18px;font-size:13px;width:auto" onclick="saveBC()">حفظ</button>
      </div>
      <div class="channel-card">
        <h4>&#127966; مواسم</h4>
        <div class="form-row">
          <div class="form-group"><label>Hotel ID</label><input id="mw-hotel" placeholder="HOTEL_ID"></div>
          <div class="form-group"><label>iCal URL</label><input id="mw-ical" placeholder="https://..."></div>
        </div>
        <button class="btn btn-primary" style="padding:8px 18px;font-size:13px;width:auto" onclick="saveMawasim()">حفظ</button>
      </div>
    </div>
  </div>

  <!-- AI -->
  <div id="sec-ai" class="pane-section">
    <div class="section">
      <div class="section-hdr"><h3>الرؤى الذكية بالذكاء الاصطناعي</h3></div>
      <div class="form-group"><label>اسألني عن بيانات فندقك</label>
        <textarea id="ai-prompt" rows="3" style="width:100%;padding:10px;border:1.5px solid #d1d5db;border-radius:8px;font-family:inherit;font-size:.9rem;resize:vertical" placeholder="مثال: ما هي أكثر الغرف حجزاً هذا الشهر؟ أو قدّم تحليلاً للإيرادات"></textarea>
      </div>
      <button class="btn btn-primary" style="width:auto;padding:10px 24px" onclick="analyzeAI()">تحليل</button>
      <div class="ai-box" id="ai-result" style="display:none"></div>
    </div>
  </div>

  <!-- SUPPORT -->
  <div id="sec-support" class="pane-section">
    <div class="section">
      <div class="section-hdr"><h3>تذاكر الدعم</h3><button class="btn btn-primary" style="padding:6px 14px;font-size:13px" onclick="openModal('m-ticket')">+ تذكرة جديدة</button></div>
      <div style="overflow-x:auto"><table id="tbl-tickets">
        <thead><tr><th>الموضوع</th><th>الحالة</th><th>التاريخ</th></tr></thead>
        <tbody><tr><td colspan="3" class="empty">لا توجد تذاكر</td></tr></tbody>
      </table></div>
    </div>
  </div>

  <!-- SETTINGS -->
  <div id="sec-settings" class="pane-section">
    <div class="section">
      <div class="section-hdr"><h3>إعدادات المنشأة</h3></div>
      <div class="form-row">
        <div class="form-group"><label>اسم المنشأة</label><input id="set-name" placeholder="فندق الواحة"></div>
        <div class="form-group"><label>المدينة</label><input id="set-city" placeholder="الرياض"></div>
      </div>
      <div class="form-row">
        <div class="form-group"><label>رقم الهاتف</label><input id="set-phone" placeholder="+966xxxxxxxx"></div>
        <div class="form-group"><label>البريد الإلكتروني</label><input id="set-email"></div>
      </div>
      <div class="form-row">
        <div class="form-group"><label>عدد الغرف/الوحدات</label><input type="number" id="set-units"></div>
        <div class="form-group"><label>نوع المنشأة</label>
          <select id="set-type"><option value="hotel">فندق</option><option value="apartment">شقق مخدومة</option><option value="resort">منتجع</option><option value="hostel">استراحة</option></select>
        </div>
      </div>
      <button class="btn btn-primary" style="width:auto;padding:10px 24px" onclick="saveSettings()">حفظ الإعدادات</button>
    </div>
  </div>

</div><!-- end .main -->

<!-- MODALS -->
<div class="modal-overlay" id="m-guest">
  <div class="modal">
    <h4>إضافة نزيل جديد</h4>
    <div class="form-group"><label>الاسم الكامل</label><input id="g-name" placeholder="أحمد محمد العلي"></div>
    <div class="form-row">
      <div class="form-group"><label>نوع الهوية</label><select id="g-id-type"><option value="national_id">هوية وطنية</option><option value="passport">جواز سفر</option><option value="iqama">إقامة</option></select></div>
      <div class="form-group"><label>رقم الهوية</label><input id="g-id-num" placeholder="1xxxxxxxxx"></div>
    </div>
    <div class="form-row">
      <div class="form-group"><label>الجنسية</label><input id="g-nat" placeholder="سعودي"></div>
      <div class="form-group"><label>رقم الهاتف</label><input id="g-phone" placeholder="+9665xxxxxxxx"></div>
    </div>
    <div class="modal-actions">
      <button class="btn btn-outline" onclick="closeModal('m-guest')">إلغاء</button>
      <button class="btn btn-primary" onclick="addGuest()">إضافة</button>
    </div>
  </div>
</div>

<div class="modal-overlay" id="m-booking">
  <div class="modal">
    <h4>إضافة حجز جديد</h4>
    <div class="form-row">
      <div class="form-group"><label>تاريخ الوصول</label><input type="date" id="b-in"></div>
      <div class="form-group"><label>تاريخ المغادرة</label><input type="date" id="b-out"></div>
    </div>
    <div class="form-row">
      <div class="form-group"><label>رقم الغرفة</label><input id="b-room" placeholder="101"></div>
      <div class="form-group"><label>السعر الليلي (ر.س)</label><input type="number" id="b-rate" value="300"></div>
    </div>
    <div class="form-row">
      <div class="form-group"><label>المصدر</label><select id="b-src"><option value="reception">الاستقبال</option><option value="booking_com">Booking.com</option><option value="mawasim">مواسم</option><option value="phone">هاتف</option></select></div>
      <div class="form-group"><label>الحالة</label><select id="b-status"><option value="confirmed">مؤكد</option><option value="checked_in">داخل</option><option value="checked_out">مغادر</option><option value="cancelled">ملغي</option></select></div>
    </div>
    <div class="form-group"><label>ملاحظات</label><textarea id="b-notes" rows="2" style="width:100%;padding:9px;border:1.5px solid #d1d5db;border-radius:7px;font-family:inherit;resize:vertical"></textarea></div>
    <div class="modal-actions">
      <button class="btn btn-outline" onclick="closeModal('m-booking')">إلغاء</button>
      <button class="btn btn-primary" onclick="addBooking()">إضافة</button>
    </div>
  </div>
</div>

<div class="modal-overlay" id="m-invoice">
  <div class="modal">
    <h4>إنشاء فاتورة جديدة</h4>
    <div class="form-row">
      <div class="form-group"><label>رقم الحجز</label><input id="inv-bk" placeholder="BK-001"></div>
      <div class="form-group"><label>المبلغ الإجمالي (ر.س)</label><input type="number" id="inv-total" value="0"></div>
    </div>
    <div class="form-row">
      <div class="form-group"><label>ضريبة ق.م (ر.س)</label><input type="number" id="inv-vat" value="0"></div>
      <div class="form-group"><label>طريقة الدفع</label><select id="inv-pay"><option value="cash">نقد</option><option value="card">بطاقة</option><option value="transfer">تحويل</option></select></div>
    </div>
    <div class="modal-actions">
      <button class="btn btn-outline" onclick="closeModal('m-invoice')">إلغاء</button>
      <button class="btn btn-primary" onclick="addInvoice()">إنشاء</button>
    </div>
  </div>
</div>

<div class="modal-overlay" id="m-pos">
  <div class="modal">
    <h4>معاملة نقطة البيع</h4>
    <div class="form-row">
      <div class="form-group"><label>الفئة</label><select id="pos-cat"><option value="restaurant">مطعم</option><option value="laundry">غسيل</option><option value="minibar">ميني بار</option><option value="parking">موقف</option><option value="other">أخرى</option></select></div>
      <div class="form-group"><label>المبلغ (ر.س)</label><input type="number" id="pos-amt" value="0"></div>
    </div>
    <div class="form-row">
      <div class="form-group"><label>طريقة الدفع</label><select id="pos-pay"><option value="cash">نقد</option><option value="card">بطاقة</option></select></div>
      <div class="form-group"><label>ضريبة ق.م (ر.س)</label><input type="number" id="pos-vat" value="0"></div>
    </div>
    <div class="form-group"><label>وصف</label><input id="pos-desc" placeholder="وصف المعاملة"></div>
    <div class="modal-actions">
      <button class="btn btn-outline" onclick="closeModal('m-pos')">إلغاء</button>
      <button class="btn btn-primary" onclick="addPOS()">تسجيل</button>
    </div>
  </div>
</div>

<div class="modal-overlay" id="m-ticket">
  <div class="modal">
    <h4>فتح تذكرة دعم</h4>
    <div class="form-group"><label>الموضوع</label><input id="tk-subj" placeholder="موضوع التذكرة"></div>
    <div class="form-group"><label>الرسالة</label><textarea id="tk-body" rows="4" style="width:100%;padding:9px;border:1.5px solid #d1d5db;border-radius:7px;font-family:inherit;resize:vertical" placeholder="اشرح مشكلتك..."></textarea></div>
    <div class="modal-actions">
      <button class="btn btn-outline" onclick="closeModal('m-ticket')">إلغاء</button>
      <button class="btn btn-primary" onclick="openTicket()">إرسال</button>
    </div>
  </div>
</div>

<script>
const SEC_TITLES={{'home':'لوحة التحكم','guests':'النزلاء','bookings':'الحجوزات','invoices':'الفواتير','pos':'نقطة البيع','reports':'التقارير','channels':'القنوات','ai':'الرؤى الذكية','support':'الدعم','settings':'الإعدادات'}};

function showSection(s){{
  document.querySelectorAll('.pane-section').forEach(el=>el.classList.remove('active'));
  document.querySelectorAll('.sidebar a').forEach(el=>el.classList.remove('active'));
  document.getElementById('sec-'+s).classList.add('active');
  const links=document.querySelectorAll('.sidebar a');
  const idx={{'home':0,'guests':1,'bookings':2,'invoices':3,'pos':4,'reports':5,'channels':6,'ai':7,'support':8,'settings':9}};
  if(links[idx[s]])links[idx[s]].classList.add('active');
  document.getElementById('page-title').textContent=SEC_TITLES[s]||s;
  const loaders={{'home':loadHome,'guests':loadGuests,'bookings':loadBookings,'invoices':loadInvoices,'pos':loadPOS,'reports':loadReports,'support':loadSupport,'settings':loadSettings}};
  if(loaders[s])loaders[s]();
  return false;
}}

function openModal(id){{document.getElementById(id).classList.add('open')}}
function closeModal(id){{document.getElementById(id).classList.remove('open')}}

function badge(s){{
  const m={{'confirmed':'badge-blue','checked_in':'badge-green','checked_out':'','cancelled':'badge-red','pending':'badge-yellow','paid':'badge-green','unpaid':'badge-yellow','open':'badge-yellow','closed':'badge-green','trial':'badge-yellow','active':'badge-green','suspended':'badge-red'}};
  const ar={{'confirmed':'مؤكد','checked_in':'داخل','checked_out':'مغادر','cancelled':'ملغي','pending':'معلق','paid':'مدفوع','unpaid':'غير مدفوع','open':'مفتوح','closed':'مغلق','trial':'تجريبي','active':'نشط','suspended':'موقوف'}};
  return `<span class="badge ${{m[s]||''}}">${{ar[s]||s}}</span>`;
}}

async function loadHome(){{
  const r=await fetch('/api/kpi');const d=await r.json();
  if(d.kpi||d.data){{
    const k=d.kpi||d.data;
    document.getElementById('kpi-active').textContent=k.active_bookings||0;
    document.getElementById('kpi-guests').textContent=k.total_guests||0;
    document.getElementById('kpi-revenue').textContent=(k.monthly_revenue||0).toLocaleString('ar-SA');
    document.getElementById('kpi-monthly').textContent=k.monthly_bookings||0;
  }}
  const br=await fetch('/api/bookings');const bd=await br.json();
  const tb=document.querySelector('#tbl-home-bk tbody');tb.innerHTML='';
  (bd.data||[]).slice(0,5).forEach(b=>{{
    tb.innerHTML+=`<tr><td>${{b.guest_id||b.guest_name||'—'}}</td><td>${{b.room_id||b.room_number||'—'}}</td><td>${{b.check_in||''}}</td><td>${{b.check_out||''}}</td><td>${{badge(b.status||'confirmed')}}</td></tr>`;
  }});
  if(!(bd.data||[]).length)tb.innerHTML='<tr><td colspan="5" class="empty">لا توجد حجوزات</td></tr>';
  const nr=await fetch('/api/notifications');const nd=await nr.json();
  const nl=document.getElementById('notif-list');nl.innerHTML='';
  if(!(nd.notifications||[]).length){{nl.innerHTML='<div class="empty">لا توجد إشعارات</div>';return;}}
  nd.notifications.forEach(n=>{{nl.innerHTML+=`<div class="notif-item ${{n.type==='warn'?'warn':''}}"><strong>${{n.title||''}}</strong><br><small>${{n.body||''}}</small></div>`;}});
}}

async function loadGuests(){{
  const r=await fetch('/api/guests');const d=await r.json();
  const tb=document.querySelector('#tbl-guests tbody');tb.innerHTML='';
  if(!(d.data||[]).length){{tb.innerHTML='<tr><td colspan="5" class="empty">لا يوجد نزلاء</td></tr>';return;}}
  d.data.forEach(g=>{{
    tb.innerHTML+=`<tr><td>${{g.full_name||g.name||''}}</td><td>${{g.id_number||''}}</td><td>${{g.nationality||''}}</td><td>${{g.absher_phone||g.phone||''}}</td><td>${{badge(g.data_status||'incomplete')}}</td></tr>`;
  }});
}}

async function addGuest(){{
  const body={{full_name:document.getElementById('g-name').value,id_type:document.getElementById('g-id-type').value,id_number:document.getElementById('g-id-num').value,nationality:document.getElementById('g-nat').value,absher_phone:document.getElementById('g-phone').value,data_status:'complete'}};
  await fetch('/api/guests',{{method:'POST',headers:{{'Content-Type':'application/json'}},body:JSON.stringify(body)}});
  closeModal('m-guest');loadGuests();
}}

async function loadBookings(){{
  const r=await fetch('/api/bookings');const d=await r.json();
  const tb=document.querySelector('#tbl-bookings tbody');tb.innerHTML='';
  if(!(d.data||[]).length){{tb.innerHTML='<tr><td colspan="6" class="empty">لا توجد حجوزات</td></tr>';return;}}
  d.data.forEach(b=>{{
    tb.innerHTML+=`<tr><td>${{b.id||''}}</td><td>${{b.guest_id||b.guest_name||''}}</td><td>${{b.check_in||''}}</td><td>${{b.check_out||''}}</td><td>${{(b.total_room||b.total_amount||0).toLocaleString('ar-SA')}} ر.س</td><td>${{badge(b.status||'confirmed')}}</td></tr>`;
  }});
}}

async function addBooking(){{
  const cin=document.getElementById('b-in').value;const cout=document.getElementById('b-out').value;
  const rate=parseFloat(document.getElementById('b-rate').value)||0;
  let nights=0;try{{nights=Math.max(0,(new Date(cout)-new Date(cin))/86400000);}}catch(e){{}}
  const body={{check_in:cin,check_out:cout,room_id:document.getElementById('b-room').value,nightly_rate:rate,total_room:rate*nights,source:document.getElementById('b-src').value,status:document.getElementById('b-status').value,notes:document.getElementById('b-notes').value}};
  await fetch('/api/bookings',{{method:'POST',headers:{{'Content-Type':'application/json'}},body:JSON.stringify(body)}});
  closeModal('m-booking');loadBookings();
}}

async function loadInvoices(){{
  const r=await fetch('/api/invoices');const d=await r.json();
  const tb=document.querySelector('#tbl-invoices tbody');tb.innerHTML='';
  if(!(d.data||[]).length){{tb.innerHTML='<tr><td colspan="5" class="empty">لا توجد فواتير</td></tr>';return;}}
  d.data.forEach(inv=>{{
    const iid=inv.id||inv.invoice_number||'';
    tb.innerHTML+=`<tr><td>${{iid}}</td><td>${{(inv.issue_date||inv.created_at||'').substring(0,10)}}</td><td>${{(inv.total_amount||inv.total||0).toLocaleString('ar-SA')}} ر.س</td><td>${{badge(inv.payment_status||'paid')}}</td>
    <td><button onclick="payInv('${{iid}}')" style="background:#dcfce7;color:#16a34a;border:none;padding:4px 10px;border-radius:5px;cursor:pointer;font-size:12px">دفع</button></td></tr>`;
  }});
}}

async function addInvoice(){{
  const body={{booking_id:document.getElementById('inv-bk').value,total_amount:parseFloat(document.getElementById('inv-total').value)||0,vat_amount:parseFloat(document.getElementById('inv-vat').value)||0,payment_method:document.getElementById('inv-pay').value,payment_status:'pending',issue_date:new Date().toISOString().substring(0,10)}};
  body.subtotal=body.total_amount-body.vat_amount;
  await fetch('/api/invoices',{{method:'POST',headers:{{'Content-Type':'application/json'}},body:JSON.stringify(body)}});
  closeModal('m-invoice');loadInvoices();
}}

async function payInv(id){{
  await fetch('/api/invoices/'+id+'/pay',{{method:'POST'}});loadInvoices();
}}

async function loadPOS(){{
  const r=await fetch('/api/pos');const d=await r.json();
  const tb=document.querySelector('#tbl-pos tbody');tb.innerHTML='';
  if(!(d.data||[]).length){{tb.innerHTML='<tr><td colspan="5" class="empty">لا توجد معاملات</td></tr>';return;}}
  d.data.forEach(tx=>{{
    tb.innerHTML+=`<tr><td>${{tx.date||''}}</td><td>${{tx.category||''}}</td><td>${{tx.description||''}}</td><td>${{(tx.amount||0).toLocaleString('ar-SA')}} ر.س</td><td>${{tx.payment_method||''}}</td></tr>`;
  }});
}}

async function addPOS(){{
  const amt=parseFloat(document.getElementById('pos-amt').value)||0;
  const vat=parseFloat(document.getElementById('pos-vat').value)||0;
  const body={{category:document.getElementById('pos-cat').value,amount:amt,vat_amount:vat,net_amount:amt-vat,payment_method:document.getElementById('pos-pay').value,description:document.getElementById('pos-desc').value,date:new Date().toISOString().substring(0,10)}};
  await fetch('/api/pos',{{method:'POST',headers:{{'Content-Type':'application/json'}},body:JSON.stringify(body)}});
  closeModal('m-pos');loadPOS();
}}

async function loadReports(){{
  const r=await fetch('/api/analytics');const d=await r.json();
  const data=d.data||{{}};
  document.getElementById('rep-bk').textContent=data.total_bookings||0;
  document.getElementById('rep-rev').textContent=(data.total_revenue||0).toLocaleString('ar-SA');
  const tb=document.querySelector('#tbl-monthly tbody');tb.innerHTML='';
  (data.monthly_revenue||[]).forEach(m=>{{
    tb.innerHTML+=`<tr><td>${{m.month||''}}</td><td>${{(m.revenue||0).toLocaleString('ar-SA')}}</td></tr>`;
  }});
}}

async function loadSupport(){{
  const r=await fetch('/api/tickets');const d=await r.json();
  const tb=document.querySelector('#tbl-tickets tbody');tb.innerHTML='';
  if(!(d.tickets||[]).length){{tb.innerHTML='<tr><td colspan="3" class="empty">لا توجد تذاكر</td></tr>';return;}}
  d.tickets.forEach(t=>{{
    tb.innerHTML+=`<tr><td>${{t.subject||''}}</td><td>${{badge(t.status||'open')}}</td><td>${{(t.created_at||'').substring(0,10)}}</td></tr>`;
  }});
}}

async function openTicket(){{
  const subject=document.getElementById('tk-subj').value;
  const body=document.getElementById('tk-body').value;
  if(!subject||!body)return;
  await fetch('/api/tickets',{{method:'POST',headers:{{'Content-Type':'application/json'}},body:JSON.stringify({{subject,body}})}});
  closeModal('m-ticket');loadSupport();
}}

async function loadSettings(){{
  const r=await fetch('/api/settings');const d=await r.json();
  const c=d.data||d.client||{{}};
  document.getElementById('set-name').value=c.name||c.hotel_name||'';
  document.getElementById('set-city').value=c.city||'';
  document.getElementById('set-phone').value=c.phone||'';
  document.getElementById('set-email').value=c.email||'';
  document.getElementById('set-units').value=c.units_count||0;
  document.getElementById('set-type').value=c.type||'hotel';
}}

async function saveSettings(){{
  const body={{name:document.getElementById('set-name').value,city:document.getElementById('set-city').value,phone:document.getElementById('set-phone').value,email:document.getElementById('set-email').value,units_count:parseInt(document.getElementById('set-units').value)||0,type:document.getElementById('set-type').value}};
  await fetch('/api/settings',{{method:'POST',headers:{{'Content-Type':'application/json'}},body:JSON.stringify(body)}});
  alert('تم حفظ الإعدادات');
}}

async function analyzeAI(){{
  const prompt=document.getElementById('ai-prompt').value;
  if(!prompt.trim())return;
  const res=document.getElementById('ai-result');
  res.style.display='block';res.textContent='جاري التحليل...';
  const r=await fetch('/api/ai/analyze',{{method:'POST',headers:{{'Content-Type':'application/json'}},body:JSON.stringify({{prompt,context:{{}}}})}});
  const d=await r.json();
  res.textContent=d.response||d.error||'لا توجد نتيجة';
}}

async function saveBC(){{
  const hotel_id=document.getElementById('bc-hotel').value;
  const api_key=document.getElementById('bc-key').value;
  await fetch('/api/channels/booking-com/settings',{{method:'POST',headers:{{'Content-Type':'application/json'}},body:JSON.stringify({{hotel_id,api_key}})}});
  alert('تم حفظ إعدادات Booking.com');
}}

async function saveMawasim(){{
  const hotel_id=document.getElementById('mw-hotel').value;
  const ical_url=document.getElementById('mw-ical').value;
  await fetch('/api/channels/mawasim/settings',{{method:'POST',headers:{{'Content-Type':'application/json'}},body:JSON.stringify({{hotel_id,ical_url}})}});
  alert('تم حفظ إعدادات مواسم');
}}

loadHome();
</script>
</body>
</html>"""


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


@app.get("/marketing", response_class=HTMLResponse)
async def marketing_page(request: Request):
    # Marketing landing page
    landing = os.path.join("static", "dheuof", "website", "index.html")
    if os.path.exists(landing):
        with open(landing, encoding="utf-8") as f:
            return HTMLResponse(f.read())
    return HTMLResponse(_login_page())


@app.get("/login", response_class=HTMLResponse)
async def login_page():
    dashboard_path = os.path.join("static", "dashboard.html")
    if os.path.exists(dashboard_path):
        with open(dashboard_path, encoding="utf-8") as f:
            return HTMLResponse(f.read())
    return HTMLResponse(_login_page())


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
async def health():
    return {"ok": True}


@app.get("/api/status")
async def status(request: Request):
    db = request.app.state.db
    return {
        "ok": True,
        "version": "3.0.0",
        "db": db.health(),
        "time": datetime.now().isoformat(),
    }


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
    with _lock:
        _client_sessions[token] = {
            "client_id": client_id,
            "created_at": datetime.now().isoformat(),
        }

    response = RedirectResponse("/", status_code=303)
    response.set_cookie("client_token", token, httponly=True, samesite="lax", max_age=86400 * 7)
    return response


@app.get("/api/logout")
@app.post("/api/logout")
async def client_logout(request: Request):
    token = _get_client_token(request)
    if token:
        session = None
        with _lock:
            session = _client_sessions.pop(token, None)
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

_PKG_EDITABLE = ("name_ar", "name_en", "price", "currency", "period", "save_note", "cta")


def _merge_packages(stored: list) -> list:
    """يدمج القيم المحفوظة فوق الافتراضية حسب id — يضمن وجود الباقات الثلاث دائماً."""
    by_id = {p.get("id"): dict(p) for p in (stored or []) if isinstance(p, dict)}
    result = []
    for default in _DEFAULT_PACKAGES:
        merged = dict(default)
        saved = by_id.get(default["id"])
        if isinstance(saved, dict):
            for k in _PKG_EDITABLE:
                if k in saved and saved[k] is not None:
                    merged[k] = saved[k]
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
        "trial_end": (datetime.now() + timedelta(days=days)).isoformat(),
        "created_at": datetime.now().isoformat(),
        "settings": {},
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
    response.set_cookie("client_token", token, httponly=True, samesite="lax", max_age=86400 * 7)
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
#  Open API (external integrations)
# ──────────────────────────────────────────────────────────────
async def _check_api_key(request: Request) -> dict:
    api_key = request.headers.get("X-API-Key") or request.query_params.get("api_key")
    if not api_key:
        raise HTTPException(status_code=401, detail="X-API-Key مطلوب")
    api_keys = request.app.state.api_keys
    if api_keys:
        key_data = api_keys.validate_key(api_key)
        if not key_data:
            raise HTTPException(status_code=401, detail="مفتاح API غير صالح")
        return key_data
    raise HTTPException(status_code=503, detail="Open API غير مُفعَّل")


@app.get("/api/open/v1/rooms")
async def open_rooms(request: Request, key=Depends(_check_api_key)):
    db = request.app.state.db
    cid = key.get("client_id")
    rows = db.execute("SELECT * FROM rooms WHERE client_id=%s", (cid,), fetch="all")
    return {"data": [dict(r) for r in (rows or [])]}


@app.get("/api/open/v1/availability")
async def open_availability(
    request: Request, check_in: str = "", check_out: str = "",
    key=Depends(_check_api_key)
):
    db = request.app.state.db
    cid = key.get("client_id")
    rows = db.execute(
        """SELECT r.* FROM rooms r WHERE r.client_id=%s
           AND r.id NOT IN (
             SELECT room_id FROM bookings
             WHERE client_id=%s AND status NOT IN ('cancelled','checked_out')
             AND check_in < %s AND check_out > %s
           )""",
        (cid, cid, check_out, check_in), fetch="all"
    ) if check_in and check_out else db.execute(
        "SELECT * FROM rooms WHERE client_id=%s AND status='available'", (cid,), fetch="all"
    )
    return {"data": [dict(r) for r in (rows or [])]}


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
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5050))
    uvicorn.run("main:app", host="0.0.0.0", port=port, reload=False)
