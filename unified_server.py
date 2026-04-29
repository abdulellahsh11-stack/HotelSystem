#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
النظام الموحد — Unified Hotel SaaS
 Port 5050 → لوحة العميل  (/)
 Port 5051 → لوحة المالك  (/admin)
يشتغل على Render / Railway / VPS بأمر واحد
"""
import sys, os, json, threading, webbrowser, time, logging, secrets, string, shutil, re
from http.server   import HTTPServer, BaseHTTPRequestHandler
from datetime      import datetime, date, timedelta
from urllib.parse  import urlparse, parse_qs

# ── مسارات ──────────────────────────────────────────────────
BASE       = os.path.expanduser("~")
HOTEL_DIR  = os.path.join(BASE, "HotelSystem")
ADMIN_DIR  = os.path.join(BASE, "HotelAdmin")
for d in [
    os.path.join(HOTEL_DIR,"data"), os.path.join(HOTEL_DIR,"logs"),
    os.path.join(HOTEL_DIR,"backups"),
    os.path.join(ADMIN_DIR,"data"),  os.path.join(ADMIN_DIR,"logs"),
]:
    os.makedirs(d, exist_ok=True)

# Railway injects PORT automatically for the primary port
# ADMIN_PORT is set manually in Railway environment variables
CLIENT_PORT = int(os.environ.get("PORT", 5050))
ADMIN_PORT  = int(os.environ.get("ADMIN_PORT", 5051))

# !! غيّر كلمة المرور هنا قبل النشر !!
# !! Set ADMIN_PASS in Railway/Render environment variables !!
ADMIN_PASS  = os.environ.get("ADMIN_PASS", "Admin@2025#Hotel")

logging.basicConfig(level=logging.INFO,
    format="%(asctime)s %(name)s %(levelname)s %(message)s",
    handlers=[
        logging.FileHandler(os.path.join(HOTEL_DIR,"logs",f"system_{date.today()}.log"), encoding="utf-8"),
        logging.StreamHandler(),
    ])
log = logging.getLogger("hotel")

# ══════════════════════════════════════════════════════════════
#  مساعدات مشتركة
# ══════════════════════════════════════════════════════════════
def _id():    return int(datetime.now().timestamp()*1000)
def _now():   return datetime.now().strftime("%H:%M")
def _today(): return str(date.today())
def _iso():   return datetime.now().isoformat()

def gen_key(plan="pro"):
    prefix = {"free":"FREE","pro":"HOTEL","enterprise":"ENT"}.get(plan,"HOTEL")
    parts  = [secrets.token_hex(2).upper() for _ in range(3)]
    return f"{prefix}-{parts[0]}-{parts[1]}-{parts[2]}"

def key_expiry(days=30):
    return (date.today()+timedelta(days=days)).isoformat()

def days_left(ds):
    if not ds: return None
    return max(0, (date.fromisoformat(ds)-date.today()).days)

# ══════════════════════════════════════════════════════════════
#  قاعدة بيانات العميل (لكل عميل ملف منفصل)
# ══════════════════════════════════════════════════════════════
# ══════════════════════════════════════════════════════════════
#  ANALYTICS ENGINE — Real-time tracking
# ══════════════════════════════════════════════════════════════
import threading as _th, collections as _col

class AnalyticsEngine:
    """Real-time analytics: sessions, usage, errors, activity"""
    def __init__(self):
        self._lock       = _th.Lock()
        self.sessions    = {}        # token → {cid, start, last_seen, pages, actions}
        self.page_hits   = _col.defaultdict(int)
        self.action_log  = []        # last 500 actions
        self.error_log   = []        # last 200 errors
        self.daily_stats = {}        # date → {logins, actions, new_clients}
        self.client_stats= {}        # cid  → {days_active, total_actions, last_page, errors}
        self.system_start= _iso()

    def session_open(self, token, cid):
        with self._lock:
            self.sessions[token] = {
                "cid": str(cid), "start": _iso(),
                "last_seen": _iso(), "pages": 0, "actions": 0,
                "ip": "—",
            }
            self._inc_daily("logins")
            cs = self.client_stats.setdefault(str(cid), {"days_active":set(),"total_actions":0,"last_page":"—","errors":0,"first_seen":_today()})
            cs["days_active"].add(_today())

    def session_close(self, token):
        with self._lock:
            self.sessions.pop(token, None)

    def track_page(self, token, page):
        with self._lock:
            if token in self.sessions:
                s = self.sessions[token]
                s["last_seen"] = _iso()
                s["pages"] += 1
                cid = s["cid"]
                self.page_hits[page] += 1
                cs = self.client_stats.setdefault(str(cid),{"days_active":set(),"total_actions":0,"last_page":"—","errors":0,"first_seen":_today()})
                cs["last_page"] = page
                cs["days_active"].add(_today())

    def track_action(self, token, action, detail=""):
        with self._lock:
            if token in self.sessions:
                s = self.sessions[token]
                s["last_seen"] = _iso()
                s["actions"]  += 1
                cid = s["cid"]
                cs = self.client_stats.setdefault(str(cid),{"days_active":set(),"total_actions":0,"last_page":"—","errors":0,"first_seen":_today()})
                cs["total_actions"] += 1
            entry = {"time":_iso(),"token":token[:8],"action":action,"detail":str(detail)[:120]}
            self.action_log.append(entry)
            if len(self.action_log) > 500: self.action_log = self.action_log[-500:]
            self._inc_daily("actions")

    def track_error(self, cid, error, context=""):
        with self._lock:
            entry = {"time":_iso(),"cid":str(cid),"error":str(error)[:200],"context":str(context)[:100]}
            self.error_log.append(entry)
            if len(self.error_log) > 200: self.error_log = self.error_log[-200:]
            cs = self.client_stats.setdefault(str(cid),{"days_active":set(),"total_actions":0,"last_page":"—","errors":0,"first_seen":_today()})
            cs["errors"] += 1

    def _inc_daily(self, key):
        d = self.daily_stats.setdefault(_today(), {"logins":0,"actions":0,"new_clients":0})
        d[key] = d.get(key,0) + 1

    def snapshot(self):
        with self._lock:
            now_ts  = datetime.now().timestamp()
            active  = {t:s for t,s in self.sessions.items()
                       if (now_ts - datetime.fromisoformat(s["last_seen"]).timestamp()) < 900}
            # clean old sessions
            self.sessions = dict(self.sessions)
            uptime_s = int((datetime.now() - datetime.fromisoformat(self.system_start)).total_seconds())
            return {
                "online_now":       len(active),
                "active_sessions":  [{"cid":s["cid"],"start":s["start"],"last_seen":s["last_seen"],"pages":s["pages"],"actions":s["actions"]} for s in active.values()],
                "page_hits":        dict(self.page_hits),
                "top_pages":        sorted(self.page_hits.items(), key=lambda x:-x[1])[:10],
                "action_log":       list(reversed(self.action_log[-50:])),
                "error_log":        list(reversed(self.error_log[-20:])),
                "daily_stats":      dict(self.daily_stats),
                "client_stats":     {k:{"days_active":len(v["days_active"]),"total_actions":v["total_actions"],"last_page":v["last_page"],"errors":v["errors"],"first_seen":v.get("first_seen","")} for k,v in self.client_stats.items()},
                "uptime_seconds":   uptime_s,
                "uptime_human":     f"{uptime_s//86400}d {(uptime_s%86400)//3600}h {(uptime_s%3600)//60}m",
                "system_start":     self.system_start,
                "total_actions":    sum(v["total_actions"] for v in self.client_stats.values()),
                "total_errors":     sum(v["errors"] for v in self.client_stats.values()),
            }

analytics = AnalyticsEngine()

# ── Pre-load admin module for /admin route on port 5050 ──────────────────────
_admin_mod_cache = None

def _load_admin_mod():
    """Load main_admin.py module (cached)"""
    global _admin_mod_cache
    if _admin_mod_cache is not None:
        return _admin_mod_cache
    try:
        import importlib.util as _ilu
        _af = os.path.join(os.path.dirname(os.path.abspath(__file__)), "main_admin.py")
        if os.path.exists(_af):
            _spec = _ilu.spec_from_file_location("_admin_panel", _af)
            _mod  = _ilu.module_from_spec(_spec)
            import webbrowser as _wb; _o = _wb.open; _wb.open = lambda *a,**k: None
            try:
                _spec.loader.exec_module(_mod)
            finally:
                _wb.open = _o
            _admin_mod_cache = _mod
            log.info("Admin module pre-loaded for /admin route")
            return _mod
    except Exception as e:
        log.error(f"Admin module load failed: {e}")
    return None


class ClientStore:
    _cache = {}

    @classmethod
    def get(cls, client_id):
        if client_id not in cls._cache:
            cls._cache[client_id] = cls(client_id)
        return cls._cache[client_id]

    def __init__(self, client_id):
        self.cid   = str(client_id)
        self._file = os.path.join(HOTEL_DIR,"data",f"client_{self.cid}.json")
        self._data = self._load()

    def _load(self):
        if os.path.exists(self._file):
            try:
                with open(self._file,"r",encoding="utf-8") as f:
                    return json.load(f)
            except: pass
        return self._defaults()

    def _defaults(self):
        return {
            "guests":[], "services":[], "suppliers":[], "invoices":[],
            "receivables":[], "journal_entries":[], "pos_devices":[
                {"id":1,"name":"جهاز المطعم","dept":"restaurant","color":"#1A56DB","serial":"","mk":"","data":None},
                {"id":2,"name":"جهاز الكافيه","dept":"cafe","color":"#D97706","serial":"","mk":"","data":None},
            ],
            "budget_lines":[
                {"id":1,"name":"إجمالي الإيرادات","type":"rev","planned":90000,"actual":0,"parent_id":None,"level":0},
                {"id":11,"name":"إيرادات الغرف","type":"rev","planned":75000,"actual":0,"parent_id":1,"level":1},
                {"id":2,"name":"إجمالي المصاريف","type":"exp","planned":30000,"actual":0,"parent_id":None,"level":0},
                {"id":21,"name":"مصاريف التشغيل","type":"exp","planned":20000,"actual":0,"parent_id":2,"level":1},
            ],
            "market_rates":{"rates":{"riyadh":{"hotel_avg":340,"apart_avg":290,"hotel_occ":74,"apart_occ":69}}},
            "pms_integrations":[], "pms_schedules":[], "pms_reads":[],
            "tickets":[],
        }

    def save(self):
        with open(self._file,"w",encoding="utf-8") as f:
            json.dump(self._data,f,ensure_ascii=False,indent=2)

    def get_d(self,k,d=None): return self._data.get(k,d)
    def set_d(self,k,v):      self._data[k]=v; self.save()
    def append(self,k,item):  self._data.setdefault(k,[]).append(item); self.save()

# ══════════════════════════════════════════════════════════════
#  قاعدة بيانات المالك
# ══════════════════════════════════════════════════════════════
class AdminStore:
    def __init__(self):
        self._file = os.path.join(ADMIN_DIR,"data","admin.json")
        self._data = self._load()

    def _load(self):
        if os.path.exists(self._file):
            try:
                with open(self._file,"r",encoding="utf-8") as f:
                    return json.load(f)
            except: pass
        return self._defaults()

    def _defaults(self):
        return {
            "clients":[], "license_keys":[], "tickets":[], "payments":[],
            "settings":{
                "owner_name":"المالك", "owner_email":"admin@hotel-system.sa",
                "owner_phone":"", "system_name":"نظام إدارة الفنادق",
                "bank_iban":"", "bank_name":"",
                "trial_days":15,
                "prices":{"free":0,"pro":299,"enterprise":799},
            },
        }

    def save(self):
        with open(self._file,"w",encoding="utf-8") as f:
            json.dump(self._data,f,ensure_ascii=False,indent=2)

    def get(self,k,d=None): return self._data.get(k,d)
    def set(self,k,v):      self._data[k]=v; self.save()
    def append(self,k,i):   self._data.setdefault(k,[]).append(i); self.save()

adm     = AdminStore()
sessions= {}   # token → expiry (admin)
cli_ses = {}   # token → client_id (client sessions)

# ══════════════════════════════════════════════════════════════
#  Base Handler
# ══════════════════════════════════════════════════════════════
class BaseH(BaseHTTPRequestHandler):
    def log_message(self,*a): pass

    def _json(self,data,status=200):
        body=json.dumps(data,ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type","application/json; charset=utf-8")
        self.send_header("Content-Length",len(body))
        self.send_header("Access-Control-Allow-Origin","*")
        self.end_headers(); self.wfile.write(body)

    def _html(self,html):
        body=html.encode("utf-8") if isinstance(html,str) else html
        self.send_response(200)
        self.send_header("Content-Type","text/html; charset=utf-8")
        self.send_header("Content-Length",len(body))
        self.end_headers(); self.wfile.write(body)

    def _read_body(self):
        n=int(self.headers.get("Content-Length",0))
        return json.loads(self.rfile.read(n)) if n else {}

    def _cookie_val(self,name):
        ck=self.headers.get("Cookie","")
        for p in ck.split(";"):
            p=p.strip()
            if p.startswith(name+"="):
                return p.split("=",1)[1]
        return ""

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header("Access-Control-Allow-Origin","*")
        self.send_header("Access-Control-Allow-Methods","GET,POST,OPTIONS")
        self.send_header("Access-Control-Allow-Headers","Content-Type")
        self.end_headers()

# ══════════════════════════════════════════════════════════════
#  CLIENT HANDLER — Port 5050
# ══════════════════════════════════════════════════════════════
class ClientHandler(BaseH):

    def _get_client(self):
        """يجلب عميل من session أو يعيد demo client"""
        tok = self._cookie_val("client_token")
        cid = cli_ses.get(tok)
        if cid:
            clients = adm.get("clients",[])
            client  = next((c for c in clients if str(c["id"])==str(cid)),None)
            if client: return client, ClientStore.get(cid)
        # Demo mode — client_id=0
        return None, ClientStore.get("demo")

    def _client_authed(self):
        tok = self._cookie_val("client_token")
        return tok in cli_ses

    def do_GET(self):
        p    = urlparse(self.path)
        path = p.path.rstrip("/") or "/"

        if path == "/health":
            self._json({"ok":True,"time":_iso()})
            return

        # لوحة العميل
        # ── Admin panel on same port (/admin) for single-port hosting ────────────
        if path in ("/admin", "/admin/"):
            _amod = _load_admin_mod()
            if _amod:
                _tok = self._cookie_val("admin_token")
                _authed = (_tok in _amod.sessions and _amod.sessions.get(_tok, datetime(2000,1,1)) > datetime.now())
                if _authed:
                    self._html(_amod._build_admin_html())
                else:
                    self._html(_amod._build_login_html())
            else:
                self._html("<h2 style='padding:40px;font-family:system-ui'>⚠️ ضع main_admin.py في نفس المجلد</h2>")
            return

        if path in ("/","/dashboard"):
            client,store = self._get_client()
            self._html(self._build_client_html(client,store))
            return

        # Client login page
        if path == "/login":
            self._html(self._build_client_login())
            return

        # Client registration
        if path == "/register":
            self._html(self._build_register_html())
            return

        # ── Admin GET APIs (stats, clients, etc.) ────────────────────────────────
        if path.startswith("/api/admin/"):
            _amod_g = _load_admin_mod()
            _tok_g  = self._cookie_val("admin_token")
            _auth_g = _amod_g and _tok_g in _amod_g.sessions and _amod_g.sessions.get(_tok_g, datetime(2000,1,1)) > datetime.now()
            if not _auth_g:
                self._json({"error":"unauthorized"}, 401); return
            _get_routes = {
                "/api/admin/stats":         lambda: self._json(self._build_admin_stats(_amod_g)),
                "/api/admin/clients":       lambda: self._json({"clients":_amod_g.adm.get("clients",[])}),
                "/api/admin/settings":      lambda: self._json({"settings":_amod_g.adm.get("admin_settings",{})}),
                "/api/admin/plans":         lambda: self._json({"plans":_amod_g.adm.get("admin_settings",{}).get("plans",[]),"prices":_amod_g.adm.get("admin_settings",{}).get("prices",{})}),
                "/api/admin/keys":          lambda: self._json({"keys":_amod_g.adm.get("license_keys",[])}),
                "/api/admin/tickets":       lambda: self._json({"tickets":_amod_g.adm.get("tickets",[])}),
                "/api/admin/payments":      lambda: self._json({"payments":_amod_g.adm.get("payments",[])}),
                "/api/admin/market":        lambda: self._json({"competitors":_amod_g.adm.get("admin_settings",{}).get("ai_market_competitors",[]),"last_analysis":_amod_g.adm.get("admin_settings",{}).get("last_market_analysis")}),
                "/api/admin/analytics":     lambda: self._json(analytics.snapshot()),
                "/api/admin/update/status": lambda: self._json({"ok":True,"history":_amod_g.adm.get("update_history",[])[-10:]}),
            }
            _gfn = _get_routes.get(path)
            if _gfn: _gfn()
            else:    self._json({"error":"admin route not found"}, 404)
            return

        client,store = self._get_client()

        routes = {
            "/api/store":      lambda _: self._api_store(store),
            "/api/market":     lambda _: self._api_market(store),
            "/api/match":      lambda _: self._api_match(store),
            "/api/kpi":        lambda _: self._api_kpi(p),
            "/api/tickets":    lambda _: self._api_tickets(client,store),
            "/api/analytics":  lambda _: self._api_analytics(),
            "/api/status":     lambda _: self._api_status(),
            "/api/payment/plans":lambda _: self._api_payment_plans(),
            "/api/subscription":lambda _: self._api_subscription(client),
        }
        fn = routes.get(path)
        if fn: fn(p)
        else:  self._json({"error":"not found"},404)

    def do_POST(self):
        b    = self._read_body()
        p    = urlparse(self.path)
        path = p.path.rstrip("/")

        # ── Admin API on same port ───────────────────────────────────────────────
        if path == "/api/admin/login":
            _amod = _load_admin_mod()
            if _amod:
                pw = b.get("password","")
                if pw == _amod.ADMIN_PASS:
                    _tok = secrets.token_hex(24)
                    _amod.sessions[_tok] = datetime.now() + timedelta(hours=12)
                    self.send_response(200)
                    self.send_header("Content-Type","application/json; charset=utf-8")
                    self.send_header("Set-Cookie", f"admin_token={_tok}; Path=/; HttpOnly; SameSite=Strict; Max-Age=43200")
                    _rb = json.dumps({"ok":True}).encode()
                    self.send_header("Content-Length", len(_rb))
                    self.end_headers(); self.wfile.write(_rb)
                else:
                    self._json({"ok":False,"error":"كلمة المرور غير صحيحة"})
            else:
                self._json({"ok":False,"error":"Admin not loaded"})
            return

        if path == "/api/admin/logout":
            _tok2 = self._cookie_val("admin_token")
            _amod2 = _load_admin_mod()
            if _amod2 and _tok2 in _amod2.sessions:
                del _amod2.sessions[_tok2]
            self._json({"ok":True})
            return

        if path.startswith("/api/admin/"):
            _amod3 = _load_admin_mod()
            _tok3 = self._cookie_val("admin_token")
            _authed3 = _amod3 and _tok3 in _amod3.sessions and _amod3.sessions.get(_tok3, datetime(2000,1,1)) > datetime.now()
            if not _authed3:
                self._json({"error":"unauthorized"}, 401); return
            # Route to admin handler method
            _admin_routes = {
                "/api/admin/stats":     lambda: self._json(self._build_admin_stats(_amod3)),
                "/api/admin/clients":   lambda: self._json({"clients":_amod3.adm.get("clients",[])}),
                "/api/admin/settings":  lambda: self._json({"settings":_amod3.adm.get("admin_settings",{})}),
                "/api/admin/settings/save": lambda: self._admin_save_settings(_amod3, b),
                "/api/admin/plans":     lambda: self._json({"plans":_amod3.adm.get("admin_settings",{}).get("plans",[]),"prices":_amod3.adm.get("admin_settings",{}).get("prices",{})}),
                "/api/admin/keys":      lambda: self._json({"keys":_amod3.adm.get("license_keys",[])}),
                "/api/admin/tickets":   lambda: self._json({"tickets":_amod3.adm.get("tickets",[])}),
                "/api/admin/payments":  lambda: self._json({"payments":_amod3.adm.get("payments",[])}),
                "/api/admin/market":    lambda: self._json({"competitors":_amod3.adm.get("admin_settings",{}).get("ai_market_competitors",[]),"last_analysis":_amod3.adm.get("admin_settings",{}).get("last_market_analysis")}),
                "/api/admin/analytics": lambda: self._json(analytics.snapshot()),
                "/api/admin/update/status": lambda: self._json({"ok":True,"history":_amod3.adm.get("update_history",[])[-10:]}),
            }
            _fn = _admin_routes.get(path)
            if _fn:
                _fn()
            else:
                # Generic POST handler via admin module
                self._admin_proxy_post(_amod3, path, b)
            return

        # Public endpoints
        if path == "/api/client/login":
            self._p_client_login(b); return
        if path == "/api/client/register":
            self._p_client_register(b); return
        if path == "/api/client/activate":
            self._p_client_activate(b); return

        client,store = self._get_client()

        routes = {
            "/api/guests/add":           lambda: self._p_guest_add(b,store),
            "/api/guests/checkout":      lambda: self._p_guest_co(b,store),
            "/api/services/add":         lambda: self._p_svc_add(b,store),
            "/api/pos/device/add":       lambda: self._p_pos_add(b,store),
            "/api/pos/device/delete":    lambda: self._p_pos_del(b,store),
            "/api/pos/device/rename":    lambda: self._p_pos_rename(b,store),
            "/api/pos/data/save":        lambda: self._p_pos_save(b,store),
            "/api/pos/data/clear":       lambda: self._p_pos_clear(b,store),
            "/api/suppliers/add":        lambda: self._p_sup_add(b,store),
            "/api/invoices/add":         lambda: self._p_inv_add(b,store),
            "/api/invoices/pay":         lambda: self._p_inv_pay(b,store),
            "/api/receivables/add":      lambda: self._p_recv_add(b,store),
            "/api/receivables/collect":  lambda: self._p_recv_col(b,store),
            "/api/journal/add":          lambda: self._p_jnl_add(b,store),
            "/api/budget/save":          lambda: (store.set_d("budget_lines",b.get("lines",[])), self._json({"ok":True}))[-1],
            "/api/settings/save":        lambda: self._p_cfg_save(b,store),
            "/api/market/update":        lambda: self._p_mkt_update(b,store),
            "/api/pms/add":              lambda: self._p_pms_add(b,store),
            "/api/pms/delete":           lambda: self._p_pms_del(b,store),
            "/api/pms/read":             lambda: self._p_pms_read(b,store),
            "/api/pms/schedule/save":    lambda: self._p_pms_sched(b,store),
            "/api/backup/create":        lambda: self._p_backup(b,store,client),
            "/api/search":               lambda: self._p_search(b,store),
            "/api/tickets/open":         lambda: self._p_ticket_open(b,store,client),
            "/api/tickets/message":      lambda: self._p_ticket_msg(b,store,client),
            "/api/ai/control":           lambda: self._p_ai_control(b,store,client),
            "/api/admin/push":           lambda: self._p_admin_push(b),
            "/api/admin/update/upload":  lambda: self._p_update_upload(b),
            "/api/admin/update/status":  lambda: self._p_update_status(b),
            "/api/payment/create":       lambda: self._p_payment_create(b),
            "/api/payment/confirm":      lambda: self._p_payment_confirm(b),
            "/api/payment/status":       lambda: self._p_payment_status(b),
        }
        fn = routes.get(path)
        if fn: fn()
        else:  self._json({"error":"not found"},404)

    # ── Auth ─────────────────────────────────────────────────
    def _p_client_login(self,b):
        email = b.get("email","").strip().lower()
        key   = b.get("key","").strip().upper()
        clients = adm.get("clients",[])
        client  = next((c for c in clients if c.get("email","").lower()==email),None)
        if not client:
            self._json({"ok":False,"error":"الإيميل غير مسجل"}); return
        if client.get("status") == "suspended":
            self._json({"ok":False,"error":"الحساب موقوف — تواصل مع الدعم"}); return
        # Check trial
        trial_end = client.get("trial_end")
        if trial_end and date.fromisoformat(trial_end) < date.today():
            if client.get("status") in ("trial","expired"):
                client["status"] = "expired"
                adm.set("clients",clients)
                s = adm.get("admin_settings",{})
                whatsapp = s.get("owner_whatsapp","")
                phone    = s.get("owner_phone","")
                msg      = s.get("contact_message","تواصل معنا لتجديد اشتراكك")
                plans    = s.get("plans",[])
                bank     = {"iban":s.get("owner_iban",""),"bank":s.get("owner_bank",""),"name":s.get("owner_account_name","")}
                self._json({"ok":False,"error":"expired","whatsapp":whatsapp,"phone":phone,"message":msg,"plans":plans,"bank":bank}); return
        tok = secrets.token_hex(24)
        cli_ses[tok] = str(client["id"])
        client["last_login"] = _iso()
        adm.set("clients",clients)
        analytics.session_open(tok, client["id"])
        self.send_response(200)
        self.send_header("Content-Type","application/json; charset=utf-8")
        self.send_header("Set-Cookie",f"client_token={tok}; Path=/; HttpOnly; SameSite=Strict; Max-Age=86400")
        body=json.dumps({"ok":True,"name":client.get("hotel_name",client["name"])}).encode()
        self.send_header("Content-Length",len(body))
        self.end_headers(); self.wfile.write(body)
        log.info(f"Client login: {client['name']}")

    def _p_client_register(self,b):
        """تسجيل عميل جديد يطلب تجربة"""
        name  = b.get("name","").strip()
        email = b.get("email","").strip().lower()
        if not name or not email:
            self._json({"ok":False,"error":"أدخل الاسم والإيميل"}); return
        clients = adm.get("clients",[])
        if any(c.get("email","").lower()==email for c in clients):
            self._json({"ok":False,"error":"هذا الإيميل مسجل بالفعل — سجّل دخولك"}); return
        trial_days = adm.get("settings",{}).get("trial_days",15)
        client = {
            "id":         _id(), "name":name,
            "hotel_name": b.get("hotel_name",name),
            "email":      email, "phone":b.get("phone",""),
            "city":       b.get("city","riyadh"),
            "hotel_type": b.get("hotel_type","hotel"),
            "rooms":      int(b.get("rooms",0)),
            "plan":       "trial", "status":"trial",
            "trial_start":_today(),
            "trial_end":  key_expiry(trial_days),
            "license_key":"", "notes":"",
            "created_at": _iso(), "last_login":None,
            "custom_settings":{},
        }
        adm.append("clients",client)
        # Auto-open welcome ticket
        ticket = {
            "id":_id(), "title":"مرحباً بك — ابدأ تجربتك المجانية",
            "client_id":str(client["id"]), "client_name":client["hotel_name"],
            "status":"open", "priority":"normal", "category":"onboarding",
            "created_at":_iso(),
            "messages":[{
                "from":"admin","name":"فريق الدعم",
                "text":f"أهلاً {name}! تهانينا بتسجيلك في {adm.get('settings',{}).get('system_name','النظام')}.\n\nتجربتك المجانية سارية حتى {client['trial_end']}.\n\nإذا احتجت أي مساعدة أرسل رسالة هنا.",
                "time":_iso(),
            }],
        }
        adm.append("tickets",ticket)
        cs = ClientStore.get(str(client["id"]))
        cs.set_d("settings",{"name":client["hotel_name"],"type":client["hotel_type"],"city":client["city"],"rooms":client["rooms"]})
        # Auto-login
        tok = secrets.token_hex(24)
        cli_ses[tok] = str(client["id"])
        analytics.session_open(tok, client["id"])
        analytics._inc_daily("new_clients")
        self.send_response(200)
        self.send_header("Content-Type","application/json; charset=utf-8")
        self.send_header("Set-Cookie",f"client_token={tok}; Path=/; HttpOnly; SameSite=Strict; Max-Age=86400")
        body=json.dumps({"ok":True,"trial_end":client["trial_end"],"name":client["hotel_name"]}).encode()
        self.send_header("Content-Length",len(body)); self.end_headers(); self.wfile.write(body)
        log.info(f"New client registered: {name} ({email})")

    def _p_client_activate(self,b):
        """تفعيل بمفتاح"""
        tok_c   = self._cookie_val("client_token")
        cid     = cli_ses.get(tok_c)
        key_str = b.get("key","").strip().upper()
        if not cid:
            self._json({"ok":False,"error":"سجّل دخولك أولاً"}); return
        keys = adm.get("license_keys",[])
        k    = next((x for x in keys if x["key"]==key_str and x["status"] in ("unused","assigned")),None)
        if not k:
            self._json({"ok":False,"error":"مفتاح غير صحيح أو مستخدم"}); return
        clients = adm.get("clients",[])
        client  = next((c for c in clients if str(c["id"])==str(cid)),None)
        if client:
            client["license_key"] = k["key"]
            client["plan"]        = k["plan"]
            client["status"]      = "active"
            client["trial_end"]   = k["expires_at"]
            adm.set("clients",clients)
        k["status"]   = "used"
        k["used_at"]  = _iso()
        k["client_id"]= cid
        adm.set("license_keys",keys)
        self._json({"ok":True,"plan":k["plan"],"expires":k["expires_at"]})
        log.info(f"Key activated: {key_str} → client {cid}")

    # ── GET APIs ─────────────────────────────────────────────
    def _api_store(self,store):
        tok = self._cookie_val("client_token")
        analytics.track_page(tok, "dashboard")
        s = store.get_d
        self._json({
            "settings":        s("settings",{}),
            "guests":          s("guests",[]),
            "services":        s("services",[]),
            "suppliers":       s("suppliers",[]),
            "invoices":        s("invoices",[]),
            "receivables":     s("receivables",[]),
            "journal_entries": s("journal_entries",[]),
            "pos_devices":     s("pos_devices",[]),
            "budget_lines":    s("budget_lines",[]),
            "market_rates":    s("market_rates",{}),
            "pms_integrations":s("settings",{}).get("pms_integrations",[]),
            "pms_schedules":   s("pms_schedules",[]),
            "pms_reads":       s("pms_reads",[])[-20:],
        })

    def _api_market(self,store):
        s    = store.get_d("settings",{})
        city = s.get("city","riyadh")
        typ  = s.get("type","hotel")
        mr   = store.get_d("market_rates",{}).get("rates",{}).get(city,{})
        k    = "hotel_avg" if typ=="hotel" else "apart_avg"
        ok   = "hotel_occ" if typ=="hotel" else "apart_occ"
        madr = mr.get(k,0); mocc=mr.get(ok,0); mrvp=round(madr*mocc/100)
        gs   = store.get_d("guests",[])
        act  = [g for g in gs if g.get("status")=="active"]
        rrev = sum(g["total"] for g in gs)
        nts  = sum(g.get("nights",1) for g in gs) or 1
        rooms= s.get("rooms",50) or 50
        oadr = round(rrev/nts); oocc=round(len(act)/rooms*100); orvp=round(rrev/rooms)
        self._json({"market_adr":madr,"market_occ":mocc,"market_revpar":mrvp,
                    "our_adr":oadr,"our_occ":oocc,"our_revpar":orvp,
                    "adr_diff":oadr-madr,"occ_diff":oocc-mocc,"revpar_diff":orvp-mrvp,
                    "city":city,"type":typ,"season_factor":1.4,"season_label":"موسم الرياض"})

    def _api_match(self,store):
        pos = sum((d["data"]["sales"]-d["data"].get("refund",0)) for d in store.get_d("pos_devices",[]) if d.get("data"))
        si  = sum(g["total"] for g in store.get_d("guests",[]))+sum(s["amount"] for s in store.get_d("services",[]))
        diff= pos-si; ab=abs(diff); pct=ab/pos*100 if pos>0 else 0
        st  = "MATCHED" if ab<1 else ("PARTIAL" if pct<=2 else "DIFF")
        lbl = {"MATCHED":"مطابقة تامة ✓","PARTIAL":f"جزئية ⚠ {ab:.0f}","DIFF":f"{'↑' if diff>0 else '↓'} {ab:.0f} ر.س"}[st]
        self._json({"status":st,"label":lbl,"color":"green" if diff>=0 else "red","pos_net":round(pos,2),"sys_in":round(si,2),"diff":round(diff,2)})

    def _api_kpi(self,p):
        qs=parse_qs(p.query)
        g=lambda k,d: float(qs.get(k,[d])[0])
        rooms=g("rooms",50); occ=g("occ",0); nts=g("nights",1) or 1
        rrev=g("rrev",0); trev=g("trev",0); texp=g("texp",0)
        self._json({"revpar":round(rrev/rooms) if rooms else 0,"adr":round(rrev/nts),
                    "occ":round(occ/rooms*100) if rooms else 0,"gop":round((trev-texp)/trev*100) if trev else 0,
                    "trevpar":round(trev/rooms) if rooms else 0})

    def _api_tickets(self,client,store):
        if not client:
            self._json({"tickets":store.get_d("tickets",[])}); return
        cid = str(client["id"])
        all_tix = adm.get("tickets",[])
        mine    = [t for t in all_tix if str(t.get("client_id",""))==cid]
        self._json({"tickets":mine})

    def _api_subscription(self,client):
        if not client:
            self._json({"plan":"demo","status":"demo","trial_end":None,"days_left":None}); return
        self._json({
            "plan":      client.get("plan","trial"),
            "status":    client.get("status","trial"),
            "trial_end": client.get("trial_end"),
            "days_left": days_left(client.get("trial_end")),
            "license_key": client.get("license_key",""),
        })

    # ── POST — data operations ────────────────────────────────
    def _p_guest_add(self,b,store):
        tok = self._cookie_val("client_token")
        analytics.track_action(tok, "guest_add", b.get("name",""))
        nights=max(1,b.get("nights",1)); total=nights*float(b.get("price",0))
        g={"id":_id(),"name":b.get("name",""),"idNum":b.get("idNum",""),"unit":b.get("unit",""),
           "bed":b.get("bed","double"),"extra":int(b.get("extra",0)),"inDate":b.get("inDate",""),
           "outDate":b.get("outDate",""),"nights":nights,"price":float(b.get("price",0)),
           "pay":b.get("pay","mada"),"total":round(total,2),"status":"active","time":_now()}
        store.append("guests",g)
        store.append("journal_entries",{"id":_id()+1,"time":_now(),"drAcc":"bank","crAcc":"room_rev",
                      "amount":g["total"],"desc":f"إيراد نزيل — {g['name']}","ref":g["unit"]})
        self._json({"ok":True,"guest":g})

    def _p_guest_co(self,b,store):
        gs=store.get_d("guests",[])
        for g in gs:
            if str(g.get("id"))==str(b.get("id")): g["status"]="checkedout"
        store.set_d("guests",gs); self._json({"ok":True})

    def _p_svc_add(self,b,store):
        s={"id":_id(),"time":_now(),"type":b.get("type","other"),"unit":b.get("unit",""),"pay":b.get("pay","mada"),"amount":float(b.get("amount",0))}
        store.append("services",s)
        store.append("journal_entries",{"id":_id()+1,"time":_now(),"drAcc":"bank","crAcc":"svc_rev","amount":s["amount"],"desc":f"{s['type']} — {s['unit']}","ref":""})
        self._json({"ok":True,"service":s})

    def _p_pos_add(self,b,store):
        devs=store.get_d("pos_devices",[])
        cols=["#1A56DB","#047857","#DC2626","#D97706","#7C3AED","#0891B2"]
        d={"id":_id(),"name":b.get("name","جهاز"),"dept":b.get("dept","other"),"color":b.get("color",cols[len(devs)%len(cols)]),"serial":b.get("serial",""),"mk":b.get("mk",""),"data":None}
        store.append("pos_devices",d); self._json({"ok":True,"device":d})

    def _p_pos_del(self,b,store):
        store.set_d("pos_devices",[d for d in store.get_d("pos_devices",[]) if str(d.get("id"))!=str(b.get("id"))])
        self._json({"ok":True})

    def _p_pos_rename(self,b,store):
        devs=store.get_d("pos_devices",[])
        for d in devs:
            if str(d.get("id"))==str(b.get("id")): d["name"]=b.get("name","")
        store.set_d("pos_devices",devs); self._json({"ok":True})

    def _p_pos_save(self,b,store):
        devs=store.get_d("pos_devices",[])
        for d in devs:
            if str(d.get("id"))==str(b.get("id")):
                d["data"]={"sales":float(b.get("sales",0)),"refund":float(b.get("refund",0)),"vat":float(b.get("vat",0)),"txCount":int(b.get("txCount",0)),"notes":b.get("notes",""),"breakdown":b.get("breakdown",{}),"receivedAt":_now(),"date":_today()}
        store.set_d("pos_devices",devs); self._json({"ok":True})

    def _p_pos_clear(self,b,store):
        devs=store.get_d("pos_devices",[])
        for d in devs:
            if str(d.get("id"))==str(b.get("id")): d["data"]=None
        store.set_d("pos_devices",devs); self._json({"ok":True})

    def _p_sup_add(self,b,store):
        cols=["#1A56DB","#047857","#DC2626","#D97706","#7C3AED"]
        s={"id":_id(),"name":b.get("name",""),"type":b.get("type","other"),"phone":b.get("phone",""),"iban":b.get("iban",""),"cr":b.get("cr",""),"terms":b.get("terms","cash"),"color":cols[len(store.get_d("suppliers",[]))%len(cols)]}
        store.append("suppliers",s); self._json({"ok":True,"supplier":s})

    def _p_inv_add(self,b,store):
        tok = self._cookie_val("client_token")
        analytics.track_action(tok, "invoice_add", b.get("supName",""))
        base=float(b.get("base",0)); vat=round(base*0.15,2) if b.get("vat",True) else 0
        inv={"id":_id(),"supId":b.get("supId"),"supName":b.get("supName","مورّد"),"num":b.get("num",f"INV-{_id()}"),"base":base,"vat":vat,"total":round(base+vat,2),"date":b.get("date",_today()),"due":b.get("due",_today()),"status":"pending"}
        store.append("invoices",inv)
        store.append("journal_entries",{"id":_id()+1,"time":_now(),"drAcc":"util_exp","crAcc":"payable","amount":base,"desc":f"فاتورة — {inv['supName']}","ref":inv["num"]})
        self._json({"ok":True,"invoice":inv})

    def _p_inv_pay(self,b,store):
        invs=store.get_d("invoices",[])
        inv=next((i for i in invs if str(i.get("id"))==str(b.get("id"))),None)
        if inv:
            inv["status"]="paid"
            store.set_d("invoices",invs)
            store.append("journal_entries",{"id":_id(),"time":_now(),"drAcc":"payable","crAcc":"bank","amount":inv["total"],"desc":f"دفع — {inv['supName']}","ref":inv["num"]})
        self._json({"ok":True})

    def _p_recv_add(self,b,store):
        r={"id":_id(),"name":b.get("name",""),"ref":b.get("ref",""),"type":b.get("type","other"),"amount":float(b.get("amount",0)),"due":b.get("due",_today()),"status":"pending"}
        store.append("receivables",r); self._json({"ok":True,"receivable":r})

    def _p_recv_col(self,b,store):
        recs=store.get_d("receivables",[])
        rec=next((r for r in recs if str(r.get("id"))==str(b.get("id"))),None)
        if rec:
            rec["status"]="collected"; store.set_d("receivables",recs)
            store.append("journal_entries",{"id":_id(),"time":_now(),"drAcc":"bank","crAcc":"receivable","amount":rec["amount"],"desc":f"تحصيل — {rec['name']}","ref":""})
        self._json({"ok":True})

    def _p_jnl_add(self,b,store):
        e={"id":_id(),"time":_now(),"drAcc":b.get("drAcc","cash"),"crAcc":b.get("crAcc","revenue"),"amount":float(b.get("amount",0)),"desc":b.get("desc","قيد"),"ref":b.get("ref","")}
        store.append("journal_entries",e); self._json({"ok":True,"entry":e})

    def _p_cfg_save(self,b,store):
        s=store.get_d("settings",{})
        for k in ["name","type","city","rooms","floors","mk","ap","recipients","owner_iban","owner_bank","owner_account_name","custom_pay_methods","unit_types","price_hotel_standard","price_hotel_suite","price_apart_studio","price_apart_one","price_apart_two","price_apart_three","market_price_hotel","market_price_apart","claude_key","smtp_user","smtp_pass","smtp_host","smtp_port"]:
            if k in b: s[k]=b[k]
        store.set_d("settings",s); self._json({"ok":True})

    def _p_mkt_update(self,b,store):
        mr=store.get_d("market_rates",{}); city=b.get("city","riyadh")
        mr.setdefault("rates",{})[city]=b.get("rates",{}); mr["last_updated"]=_iso()
        store.set_d("market_rates",mr); self._json({"ok":True})

    def _p_pms_add(self,b,store):
        s=store.get_d("settings",{}); intgs=s.get("pms_integrations",[])
        intg={"id":_id(),"name":b.get("name",""),"type":b.get("type","opera"),"url":b.get("url",""),"username":b.get("username",""),"password":b.get("password",""),"api_key":b.get("api_key",""),"enabled":True,"last_read":None,"read_count":0}
        intgs.append(intg); s["pms_integrations"]=intgs; store.set_d("settings",s)
        self._json({"ok":True,"integration":intg})

    def _p_pms_del(self,b,store):
        s=store.get_d("settings",{}); s["pms_integrations"]=[i for i in s.get("pms_integrations",[]) if str(i.get("id"))!=str(b.get("id"))]; store.set_d("settings",s); self._json({"ok":True})

    def _p_pms_read(self,b,store):
        guests=[
            {"pms_id":f"PMS-{_id()}","name":"محمد الغامدي","room":"101","checkin":_today(),"checkout":key_expiry(2),"rate":380,"status":"inhouse","nationality":"SA"},
            {"pms_id":f"PMS-{_id()+1}","name":"Sarah Johnson","room":"205","checkin":_today(),"checkout":key_expiry(3),"rate":420,"status":"inhouse","nationality":"US"},
        ]
        rd={"id":_id(),"intg_id":b.get("id"),"intg_name":"PMS","time":_iso(),"status":"success","guests_found":len(guests),"data":guests}
        store.append("pms_reads",rd)
        pms_reads=store.get_d("pms_reads",[])[-50:]
        store.set_d("pms_reads",pms_reads)
        self._json({"ok":True,"guests_found":len(guests),"data":guests})

    def _p_pms_sched(self,b,store):
        scheds=store.get_d("pms_schedules",[]); iid=b.get("intg_id")
        ex=next((s for s in scheds if str(s.get("intg_id"))==str(iid)),None)
        if ex: ex.update(b)
        else: scheds.append({"id":_id(),"intg_id":iid,"frequency":b.get("frequency","manual"),"time":b.get("time","08:00"),"enabled":b.get("enabled",True),"last_run":None})
        store.set_d("pms_schedules",scheds); self._json({"ok":True})

    def _p_backup(self,b,store,client):
        data=json.dumps(store._data,ensure_ascii=False,indent=2)
        blob=data.encode("utf-8")
        name=f"backup_{client['id'] if client else 'demo'}_{_today()}.json"
        bk_dir=os.path.join(HOTEL_DIR,"backups")
        with open(os.path.join(bk_dir,name),"w",encoding="utf-8") as f: f.write(data)
        self._json({"ok":True,"name":name,"date":_today(),"size_kb":round(len(blob)/1024,1)})

    def _p_search(self,b,store):
        q=b.get("q","").strip().lower()
        if not q: self._json({"results":[]}); return
        results=[]
        for g in store.get_d("guests",[]):
            if q in g.get("name","").lower() or q in g.get("unit","").lower():
                results.append({"type":"guest","label":f"نزيل: {g['name']}","sub":f"وحدة {g.get('unit','')}","id":g["id"],"goto":"guests"})
        for s in store.get_d("suppliers",[]):
            if q in s.get("name","").lower(): results.append({"type":"supplier","label":f"مورّد: {s['name']}","sub":s.get("type",""),"id":s["id"],"goto":"suppliers"})
        for i in store.get_d("invoices",[]):
            if q in i.get("num","").lower() or q in i.get("supName","").lower(): results.append({"type":"invoice","label":f"فاتورة: {i['num']}","sub":f"{i.get('total',0)} ر.س","id":i["id"],"goto":"invoices"})
        self._json({"results":results[:15]})

    def _p_ticket_open(self,b,store,client):
        """العميل يفتح تذكرة"""
        tok = self._cookie_val("client_token")
        analytics.track_action(tok, "ticket_open", b.get("title",""))
        title=b.get("title","").strip()
        if not title: self._json({"ok":False,"error":"أدخل عنوان التذكرة"}); return
        cid=str(client["id"]) if client else "demo"
        cname=client["hotel_name"] if client else "Demo"
        ticket={
            "id":_id(),"title":title,"client_id":cid,"client_name":cname,
            "priority":b.get("priority","normal"),"status":"open",
            "category":b.get("category","support"),"created_at":_iso(),
            "messages":[{"from":"client","name":cname,"text":b.get("message",""),"time":_iso()}],
        }
        adm.append("tickets",ticket)
        # Also keep ref in client store
        store.append("tickets",{"id":ticket["id"],"title":title,"status":"open"})
        self._json({"ok":True,"ticket":ticket})

    def _p_ticket_msg(self,b,store,client):
        """العميل يضيف رسالة في تذكرة"""
        tid=b.get("id"); text=b.get("text","").strip()
        if not text: self._json({"ok":False,"error":"أدخل رسالة"}); return
        cname=client["hotel_name"] if client else "Demo"
        tickets=adm.get("tickets",[])
        for t in tickets:
            if str(t.get("id"))==str(tid):
                t.setdefault("messages",[]).append({"from":"client","name":cname,"text":text,"time":_iso()})
                t["status"]="open"
        adm.set("tickets",tickets)
        self._json({"ok":True})

    # ── HTML Pages ────────────────────────────────────────────
    def _api_analytics(self):
        self._json(analytics.snapshot())

    def _api_status(self):
        clients = adm.get("clients",[])
        active  = [c for c in clients if c.get("status")=="active"]
        trial   = [c for c in clients if c.get("status")=="trial"]
        snap    = analytics.snapshot()
        self._json({
            "status": "online", "version": "4.0",
            "uptime": snap["uptime_human"],
            "online_now": snap["online_now"],
            "total_clients": len(clients),
            "active_paid": len(active),
            "on_trial": len(trial),
        })

    def _p_ai_control(self, b, store, client):
        """
        AI Execution Engine — Claude يفهم الأمر وينفّذه مباشرة على النظام
        يدعم: قراءة البيانات، إضافة/تعديل/حذف، تحليل، رسائل، تقارير
        """
        import urllib.request as _ur, re as _re
        cmd = b.get("command", "").strip()
        s   = adm.get("admin_settings", {})
        key = b.get("claude_key", s.get("claude_key", ""))
        if not cmd:
            self._json({"ok": False, "error": "أدخل أمراً"}); return

        # ── Build rich context ────────────────────────────────
        clients  = adm.get("clients", [])
        tickets  = adm.get("tickets", [])
        keys_l   = adm.get("license_keys", [])
        payments = adm.get("payments", [])
        prices   = s.get("prices", {"free":0,"pro":299,"enterprise":799})

        active   = [c for c in clients if c.get("status")=="active"]
        trial    = [c for c in clients if c.get("status")=="trial"]
        expired  = [c for c in clients if c.get("status") in ("expired","suspended")]
        open_tix = [t for t in tickets if t.get("status")=="open"]
        mrr      = sum(prices.get(c.get("plan","free"),0) for c in active)
        expiring = [c for c in trial if c.get("trial_end") and
                    0 <= (date.fromisoformat(c["trial_end"])-date.today()).days <= 5]

        snap  = analytics.snapshot()
        today_stats = snap.get("daily_stats",{}).get(str(date.today()),{})

        system_context = f"""أنت مساعد تحكم ذكي مدمج في لوحة تحكم SaaS لإدارة الفنادق.
لديك صلاحيات كاملة لقراءة البيانات وتنفيذ الأوامر.

=== بيانات النظام الحالية ===
• إجمالي العملاء: {len(clients)} (نشط: {len(active)}, تجربة: {len(trial)}, منتهي: {len(expired)})
• MRR: {mrr} ر.س | ARR متوقع: {mrr*12} ر.س
• تذاكر مفتوحة: {len(open_tix)}
• مفاتيح مُصدرة: {len(keys_l)} (مستخدمة: {len([k for k in keys_l if k.get('status')=='used'])})
• متصلون الآن: {snap.get('online_now',0)}
• وقت تشغيل النظام: {snap.get('uptime_human','—')}
• أحداث اليوم: {today_stats.get('actions',0)}
• أخطاء مسجلة: {snap.get('total_errors',0)}

=== قائمة العملاء ===
{chr(10).join(f"ID:{c['id']} | {c.get('hotel_name',c['name'])} | {c.get('email','')} | {c.get('status','')} | {c.get('plan','')} | ينتهي: {c.get('trial_end','')}" for c in clients[:20])}

=== تنتهي تجربتهم خلال 5 أيام ===
{chr(10).join(f"{c.get('hotel_name',c['name'])} ({c.get('email','')}) — ينتهي: {c.get('trial_end','')}" for c in expiring) or 'لا يوجد'}

=== التذاكر المفتوحة ===
{chr(10).join(f"#{t['id']} | {t.get('client_name','')} | {t.get('title','')} | {t.get('priority','')}" for t in open_tix[:10]) or 'لا يوجد'}

=== الإعدادات ===
اسم النظام: {s.get('system_name','Hotel System')}
واتساب: {s.get('owner_whatsapp','')}
IBAN: {s.get('bank_iban','')}
مدة التجربة: {s.get('trial_days',15)} يوم

=== الأمر المطلوب ===
{cmd}

=== تعليمات الرد ===
أجب بـ JSON فقط بالشكل التالي:
{{
  "response": "رد واضح للمستخدم بالعربية",
  "actions": [
    {{
      "type": "نوع_الإجراء",
      "params": {{...}},
      "description": "وصف ما سيحدث"
    }}
  ],
  "summary": "ملخص قصير لما تم",
  "suggestions": ["اقتراح 1", "اقتراح 2"]
}}

أنواع الإجراءات المتاحة:
- extend_client: {{id, days}} — تمديد تجربة عميل
- suspend_client: {{id}} — إيقاف عميل
- activate_client: {{id}} — تفعيل عميل
- generate_key: {{plan, days, client_id}} — إصدار مفتاح
- reply_ticket: {{id, text}} — الرد على تذكرة
- close_ticket: {{id}} — إغلاق تذكرة
- send_push: {{message, client_ids}} — إرسال إشعار
- add_client: {{name, hotel_name, email, city, plan}} — تسجيل عميل جديد
- update_price: {{plan, price}} — تغيير سعر خطة
- read_only: null — لا يوجد إجراء (استفسار فقط)

إذا كان الأمر استفساراً فقط، اجعل actions قائمة فارغة [].
إذا كان الأمر يتطلب تنفيذاً، اذكر الإجراءات بدقة."""

        result = {"response": "—", "actions": [], "summary": "", "suggestions": []}

        if key:
            try:
                payload = json.dumps({
                    "model": "claude-sonnet-4-6",
                    "max_tokens": 1500,
                    "messages": [{"role": "user", "content": system_context}]
                }).encode()
                req = _ur.Request(
                    "https://api.anthropic.com/v1/messages",
                    data=payload,
                    headers={"Content-Type":"application/json",
                             "anthropic-version":"2023-06-01",
                             "x-api-key": key},
                    method="POST"
                )
                resp_raw = _ur.urlopen(req, timeout=25)
                data     = json.loads(resp_raw.read())
                text     = data["content"][0]["text"].strip()
                m = _re.search(r'\{.*\}', text, _re.DOTALL)
                if m:
                    result = json.loads(m.group(0))
            except Exception as e:
                logging.error(f"AI control error: {e}")
                result = {"response": f"خطأ في الاتصال بـ Claude: {str(e)[:100]}", "actions": [], "summary": "", "suggestions": []}
        else:
            # ── Smart built-in responses (no API key) ────────
            cmd_l = cmd.lower()
            if any(w in cmd_l for w in ["ملخص","كيف","وضع","تقرير","إجمالي","كم"]):
                result = {
                    "response": f"ملخص النظام:\n• العملاء: {len(clients)} ({len(active)} نشط، {len(trial)} تجربة)\n• MRR: {mrr} ر.س\n• تذاكر مفتوحة: {len(open_tix)}\n• متصلون الآن: {snap.get('online_now',0)}\n• وقت التشغيل: {snap.get('uptime_human','—')}",
                    "actions": [], "summary": "ملخص قُرئ", "suggestions": ["أضف Claude API Key لتحليل أعمق"]
                }
            elif any(w in cmd_l for w in ["تجارب","تنتهي","انتهت","قريباً"]):
                if expiring:
                    result = {
                        "response": f"يوجد {len(expiring)} عميل تنتهي تجربتهم:\n" + "\n".join(f"• {c.get('hotel_name',c['name'])} — ينتهي {c.get('trial_end','')} ({(date.fromisoformat(c['trial_end'])-date.today()).days} أيام)" for c in expiring),
                        "actions": [{"type":"extend_client","params":{"id":c["id"],"days":7},"description":f"تمديد {c.get('hotel_name',c['name'])} أسبوعاً"} for c in expiring[:3]],
                        "summary": f"{len(expiring)} عميل يحتاج متابعة",
                        "suggestions": ["مدّد تجارب العملاء المهمين","أرسل رسالة تذكير للكل"]
                    }
                else:
                    result = {"response": "لا توجد تجارب تنتهي خلال 5 أيام ✓", "actions": [], "summary": "", "suggestions": []}
            elif any(w in cmd_l for w in ["تذاكر","مشاكل","دعم"]):
                if open_tix:
                    result = {
                        "response": f"يوجد {len(open_tix)} تذكرة مفتوحة:\n" + "\n".join(f"• {t.get('client_name','')} — {t.get('title','')} [{t.get('priority','')}]" for t in open_tix[:5]),
                        "actions": [],
                        "summary": f"{len(open_tix)} تذكرة تحتاج ردّاً",
                        "suggestions": ["ردّ على التذاكر العاجلة أولاً"]
                    }
                else:
                    result = {"response": "✓ لا توجد تذاكر مفتوحة — كل شيء تمام", "actions": [], "summary": "", "suggestions": []}
            elif any(w in cmd_l for w in ["إيراد","mrr","أموال","مدفوعات"]):
                total_paid = sum(p.get("amount",0) for p in payments)
                result = {
                    "response": f"الإيرادات:\n• MRR: {mrr} ر.س\n• ARR متوقع: {mrr*12} ر.س\n• إجمالي المدفوعات: {total_paid} ر.س\n• عملاء مدفوعون: {len(active)}",
                    "actions": [], "summary": "تقرير الإيراد", "suggestions": ["أضف Claude API Key لتوصيات تسعير"]
                }
            else:
                result = {
                    "response": f"فهمت: '{cmd}'\n\nأضف Claude API Key في الإعدادات لتنفيذ هذا الأمر بذكاء كامل.\n\nما أستطيع فعله الآن: ملخص النظام، تجارب تنتهي، تذاكر، إيرادات.",
                    "actions": [], "summary": "", "suggestions": ["اذهب للإعدادات → Claude API Key"]
                }

        # ── Execute approved actions ──────────────────────────
        executed = []
        auto_exec = b.get("auto_execute", False)

        if auto_exec and result.get("actions"):
            for action in result["actions"]:
                atype  = action.get("type")
                params = action.get("params", {})
                try:
                    if atype == "extend_client":
                        res = self._exec_extend(params)
                        executed.append({"action": atype, "ok": res, "desc": action.get("description","")})
                    elif atype == "suspend_client":
                        res = self._exec_toggle(params.get("id"), "suspend")
                        executed.append({"action": atype, "ok": res, "desc": action.get("description","")})
                    elif atype == "activate_client":
                        res = self._exec_toggle(params.get("id"), "activate")
                        executed.append({"action": atype, "ok": res, "desc": action.get("description","")})
                    elif atype == "generate_key":
                        res = self._exec_gen_key(params)
                        executed.append({"action": atype, "ok": True, "key": res, "desc": action.get("description","")})
                    elif atype == "reply_ticket":
                        res = self._exec_reply_ticket(params)
                        executed.append({"action": atype, "ok": res, "desc": action.get("description","")})
                    elif atype == "close_ticket":
                        res = self._exec_close_ticket(params.get("id"))
                        executed.append({"action": atype, "ok": res, "desc": action.get("description","")})
                    elif atype == "send_push":
                        res = self._exec_push(params)
                        executed.append({"action": atype, "ok": True, "sent": res, "desc": action.get("description","")})
                    elif atype == "update_price":
                        res = self._exec_update_price(params)
                        executed.append({"action": atype, "ok": res, "desc": action.get("description","")})
                    elif atype == "add_client":
                        res = self._exec_add_client(params)
                        executed.append({"action": atype, "ok": True, "client": res, "desc": action.get("description","")})
                except Exception as e:
                    executed.append({"action": atype, "ok": False, "error": str(e)})
                    logging.error(f"AI exec error: {atype} → {e}")

        analytics.track_action(
            self._cookie_val("client_token") or self._cookie_val("admin_token"),
            "ai_control", cmd[:80]
        )
        self._json({
            "ok": True,
            "result": result,
            "executed": executed,
            "auto_execute": auto_exec,
            "cmd": cmd,
        })

    # ── AI Execution Helpers ──────────────────────────────────
    def _exec_extend(self, params):
        cid  = params.get("id")
        days = int(params.get("days", 7))
        clients = adm.get("clients", [])
        for c in clients:
            if str(c.get("id")) == str(cid):
                base = date.fromisoformat(c.get("trial_end", str(date.today())))
                if base < date.today(): base = date.today()
                c["trial_end"] = (base + timedelta(days=days)).isoformat()
                c["status"]    = "trial"
        adm.set("clients", clients)
        logging.info(f"AI exec: extend {cid} +{days}d")
        return True

    def _exec_toggle(self, cid, action):
        clients = adm.get("clients", [])
        for c in clients:
            if str(c.get("id")) == str(cid):
                c["status"] = "active" if action == "activate" else "suspended"
        adm.set("clients", clients)
        return True

    def _exec_gen_key(self, params):
        plan = params.get("plan", "pro")
        days = int(params.get("days", 30))
        cid  = params.get("client_id")
        k = {
            "id": _id(), "key": gen_key(plan), "plan": plan, "days": days,
            "status": "assigned" if cid else "unused",
            "created_at": _iso(), "expires_at": key_expiry(days),
            "client_id": cid, "client_name": "", "used_at": None, "notes": "AI generated",
        }
        if cid:
            clients = adm.get("clients", [])
            c = next((x for x in clients if str(x.get("id")) == str(cid)), None)
            if c:
                k["client_name"] = c.get("hotel_name", c["name"])
                c["license_key"] = k["key"]
                c["plan"]        = plan
                c["status"]      = "active"
                c["trial_end"]   = k["expires_at"]
                adm.set("clients", clients)
        adm.append("license_keys", k)
        return k["key"]

    def _exec_reply_ticket(self, params):
        tid  = params.get("id")
        text = params.get("text", "")
        tickets = adm.get("tickets", [])
        for t in tickets:
            if str(t.get("id")) == str(tid):
                t.setdefault("messages", []).append({
                    "from": "admin", "name": "الدعم الفني (AI)",
                    "text": text, "time": _iso()
                })
                t["status"] = "replied"
        adm.set("tickets", tickets)
        return True

    def _exec_close_ticket(self, tid):
        tickets = adm.get("tickets", [])
        for t in tickets:
            if str(t.get("id")) == str(tid):
                t["status"] = "closed"
                t["closed_at"] = _iso()
        adm.set("tickets", tickets)
        return True

    def _exec_push(self, params):
        msg  = params.get("message", "")
        cids = params.get("client_ids", [])
        clients = adm.get("clients", [])
        targets = [c for c in clients if not cids or str(c.get("id")) in [str(x) for x in cids]]
        notif   = {"id":_id(),"time":_iso(),"message":msg,"from":"admin","read":False}
        for c in targets:
            cs = ClientStore.get(str(c["id"]))
            notifs = cs.get_d("notifications", [])
            notifs.append(notif)
            cs.set_d("notifications", notifs[-50:])
        return len(targets)

    def _exec_update_price(self, params):
        plan  = params.get("plan")
        price = float(params.get("price", 0))
        s     = adm.get("admin_settings", {})
        s.setdefault("prices", {})[plan] = price
        adm.set("admin_settings", s)
        return True

    def _exec_add_client(self, params):
        trial_days = adm.get("admin_settings", {}).get("trial_days", 15)
        client = {
            "id": _id(), "name": params.get("name",""),
            "hotel_name": params.get("hotel_name", params.get("name","")),
            "email": params.get("email",""), "phone": params.get("phone",""),
            "city": params.get("city","riyadh"), "hotel_type": params.get("hotel_type","hotel"),
            "rooms": int(params.get("rooms",0)), "plan": params.get("plan","trial"),
            "status": "trial", "trial_start": _today(),
            "trial_end": key_expiry(trial_days), "license_key": "",
            "notes": "تم الإنشاء بواسطة AI", "created_at": _iso(), "last_login": None,
            "custom_settings": {},
        }
        adm.append("clients", client)
        logging.info(f"AI exec: add_client {client['name']}")
        return client



    def _p_admin_push(self, b):
        """Admin pushes notification/update to all clients"""
        msg  = b.get("message","").strip()
        cids = b.get("client_ids",[])  # empty = all
        if not msg:
            self._json({"ok":False,"error":"أدخل رسالة"}); return
        clients = adm.get("clients",[])
        targets = [c for c in clients if not cids or str(c.get("id")) in [str(x) for x in cids]]
        notif   = {"id":_id(),"time":_iso(),"message":msg,"from":"admin","read":False}
        for c in targets:
            cs = ClientStore.get(str(c["id"]))
            notifs = cs.get_d("notifications",[])
            notifs.append(notif)
            cs.set_d("notifications", notifs[-50:])
        log.info(f"Admin push: {msg[:50]} → {len(targets)} clients")
        self._json({"ok":True,"sent_to":len(targets)})


    def _api_payment_plans(self):
        """الخطط المتاحة للدفع"""
        s      = adm.get("admin_settings", {})
        prices = s.get("prices", {"free":0,"pro":299,"enterprise":799})
        plans  = s.get("plans", [
            {"id":"pro","name":"احترافية","price":prices.get("pro",299),"period":"شهري","color":"#185FA5","features":["نزلاء غير محدود","POS غير محدود","مقارنة السوق"]},
            {"id":"enterprise","name":"مؤسسية","price":prices.get("enterprise",799),"period":"شهري","color":"#534AB7","features":["كل مميزات الاحترافية","متعدد الفروع","API مفتوح"]},
        ])
        bank = {
            "name":     s.get("owner_account_name", s.get("owner_name","")),
            "bank":     s.get("owner_bank",""),
            "iban":     s.get("owner_iban",""),
            "whatsapp": s.get("owner_whatsapp",""),
            "phone":    s.get("owner_phone",""),
        }
        self._json({"plans": plans, "bank": bank, "prices": prices})

    def _p_payment_create(self, b):
        """إنشاء طلب دفع — يدعم مدى (Geidea) والتحويل البنكي"""
        tok_c    = self._cookie_val("client_token")
        cid      = cli_ses.get(tok_c)
        plan     = b.get("plan","pro")
        method   = b.get("method","mada")  # mada | transfer
        period   = b.get("period","monthly")
        s        = adm.get("admin_settings", {})
        prices   = s.get("prices", {"pro":299,"enterprise":799})
        base     = prices.get(plan, 299)
        # Apply period discount
        multiplier = {"monthly":1,"quarterly":3,"semi":6,"annual":12}.get(period,1)
        disc_map   = {"monthly":0,"quarterly":s.get("discount_quarterly",10),"semi":s.get("discount_semi",15),"annual":s.get("discount_annual",20)}
        disc       = disc_map.get(period,0)
        amount     = round(base * multiplier * (1 - disc/100), 2)
        days_map   = {"monthly":30,"quarterly":90,"semi":180,"annual":365}
        days       = days_map.get(period, 30)

        payment_id = f"PAY-{secrets.token_hex(4).upper()}"
        payment_rec = {
            "id":         payment_id,
            "client_id":  cid,
            "plan":       plan,
            "method":     method,
            "period":     period,
            "amount":     amount,
            "days":       days,
            "status":     "pending",
            "created_at": _iso(),
            "expires_at": key_expiry(1),  # Payment link expires in 1 day
        }

        if method == "mada":
            # Geidea payment link
            mk = s.get("mk","")
            ap = s.get("ap","")
            if mk and ap:
                try:
                    import urllib.request as _ur, base64 as _b64, hashlib as _hs
                    # Geidea order request
                    geidea_payload = json.dumps({
                        "amount":        str(amount),
                        "currencyCode":  "SAR",
                        "merchantReferenceId": payment_id,
                        "callbackUrl":   b.get("callback_url",""),
                        "returnUrl":     b.get("return_url",""),
                        "language":      "ar",
                        "customerEmail": b.get("email",""),
                    }).encode()
                    # Basic auth for Geidea
                    creds  = _b64.b64encode(f"{mk}:{ap}".encode()).decode()
                    req_g  = _ur.Request(
                        "https://api.merchant.geidea.net/payment-intent/api/v2/direct/session",
                        data=geidea_payload,
                        headers={"Content-Type":"application/json","Authorization":f"Basic {creds}"},
                        method="POST"
                    )
                    resp_g = _ur.urlopen(req_g, timeout=10)
                    gd     = json.loads(resp_g.read())
                    payment_rec["geidea_session"] = gd.get("session",{}).get("id","")
                    payment_rec["payment_url"]    = gd.get("session",{}).get("paymentUrl","")
                    payment_rec["status"]         = "awaiting_payment"
                    log.info(f"Geidea session created: {payment_id}")
                except Exception as e:
                    log.error(f"Geidea error: {e}")
                    payment_rec["payment_url"] = ""
                    payment_rec["geidea_error"] = str(e)
            else:
                # No Geidea keys — show manual mada instructions
                payment_rec["payment_url"] = ""
                payment_rec["manual"]      = True
        else:
            # Transfer — show bank details
            payment_rec["payment_url"] = ""
            payment_rec["manual"]      = True
            payment_rec["bank"] = {
                "name": s.get("owner_account_name",""),
                "bank": s.get("owner_bank",""),
                "iban": s.get("owner_iban",""),
                "amount": amount,
                "ref":  payment_id,
            }

        # Save pending payment
        pending = ClientStore.get(str(cid) if cid else "demo").get_d("pending_payments",[])
        pending.append(payment_rec)
        ClientStore.get(str(cid) if cid else "demo").set_d("pending_payments", pending[-10:])
        log.info(f"Payment created: {payment_id} {plan} {amount} SAR via {method}")
        analytics.track_action(tok_c, "payment_create", f"{plan} {amount} SAR {method}")
        self._json({"ok":True, "payment": payment_rec})

    def _p_payment_confirm(self, b):
        """تأكيد الدفع يدوياً (للتحويل البنكي)"""
        payment_id = b.get("payment_id")
        ref        = b.get("ref","")
        tok_c      = self._cookie_val("client_token")
        cid        = cli_ses.get(tok_c)
        if not cid or not payment_id:
            self._json({"ok":False,"error":"بيانات غير مكتملة"}); return
        cs      = ClientStore.get(str(cid))
        pending = cs.get_d("pending_payments",[])
        pay_rec = next((p for p in pending if p.get("id")==payment_id),None)
        if not pay_rec:
            self._json({"ok":False,"error":"طلب الدفع غير موجود"}); return
        # Create confirmation ticket for manual review by admin
        clients  = adm.get("clients",[])
        client   = next((c for c in clients if str(c.get("id"))==str(cid)),None)
        ticket   = {
            "id":          _id(),
            "title":       f"تأكيد دفع — {pay_rec.get('plan','')} {pay_rec.get('amount',0)} ر.س",
            "client_id":   str(cid),
            "client_name": client.get("hotel_name",client.get("name","")) if client else "—",
            "priority":    "high",
            "status":      "open",
            "category":    "billing",
            "created_at":  _iso(),
            "messages": [{
                "from":  "client",
                "name":  client.get("hotel_name","") if client else "العميل",
                "text":  (f"أرسلت دفعة {pay_rec['amount']} ر.س للخطة {pay_rec['plan']}. "
                          f"رقم المرجع: {ref or payment_id}. "
                          f"طريقة الدفع: {pay_rec.get('method','transfer')}. يرجى التحقق والتفعيل."),
                "time":  _iso(),
            }],
            "payment_data": pay_rec,
        }
        adm.append("tickets", ticket)
        # Update payment record
        pay_rec["status"]      = "confirming"
        pay_rec["ref"]         = ref
        pay_rec["confirmed_at"]= _iso()
        cs.set_d("pending_payments", pending)
        log.info(f"Payment confirmation ticket: {ticket['id']}")
        analytics.track_action(tok_c, "payment_confirm", f"{payment_id} ref:{ref}")
        self._json({"ok":True, "ticket_id": ticket["id"], "message": "تم إرسال طلب التأكيد — سيتواصل معك الدعم خلال ساعات"})

    def _p_payment_status(self, b):
        """حالة طلب الدفع"""
        payment_id = b.get("payment_id")
        tok_c      = self._cookie_val("client_token")
        cid        = cli_ses.get(tok_c)
        if not cid:
            self._json({"ok":False,"error":"غير مسجّل"}); return
        cs      = ClientStore.get(str(cid))
        pending = cs.get_d("pending_payments",[])
        pay_rec = next((p for p in pending if p.get("id")==payment_id), None)
        if not pay_rec:
            self._json({"ok":False,"error":"طلب غير موجود"}); return
        # Check Geidea session status if applicable
        session_id = pay_rec.get("geidea_session","")
        if session_id:
            try:
                import urllib.request as _ur, base64 as _b64
                s   = adm.get("admin_settings",{})
                mk  = s.get("mk",""); ap = s.get("ap","")
                if mk and ap:
                    creds = _b64.b64encode(f"{mk}:{ap}".encode()).decode()
                    req_g = _ur.Request(
                        f"https://api.merchant.geidea.net/payment-intent/api/v2/direct/session/{session_id}",
                        headers={"Authorization":f"Basic {creds}"}
                    )
                    resp_g = _ur.urlopen(req_g, timeout=8)
                    gd     = json.loads(resp_g.read())
                    status = gd.get("status","")
                    if status in ("SUCCESS","PAID"):
                        pay_rec["status"] = "paid"
                        cs.set_d("pending_payments", pending)
                        # Auto-activate
                        self._activate_after_payment(str(cid), pay_rec)
            except Exception as e:
                log.error(f"Geidea status check: {e}")
        self._json({"ok":True, "payment": pay_rec})

    def _activate_after_payment(self, cid, pay_rec):
        """تفعيل العميل تلقائياً بعد الدفع"""
        k = {
            "id": _id(), "key": gen_key(pay_rec.get("plan","pro")),
            "plan": pay_rec.get("plan","pro"), "days": pay_rec.get("days",30),
            "status": "used", "created_at": _iso(),
            "expires_at": key_expiry(pay_rec.get("days",30)),
            "client_id": cid, "notes": f"تلقائي بعد دفع {pay_rec.get('id','')}",
            "used_at": _iso(),
        }
        adm.append("license_keys", k)
        clients = adm.get("clients",[])
        for c in clients:
            if str(c.get("id"))==str(cid):
                c["license_key"] = k["key"]
                c["plan"]        = k["plan"]
                c["status"]      = "active"
                c["trial_end"]   = k["expires_at"]
        adm.set("clients", clients)
        log.info(f"Auto-activated client {cid} after payment")


    def _p_update_upload(self, b):
        """رفع ملف تحديث لنظام إدارة الفنادق"""
        import base64 as _b64, hashlib as _hs, os as _os
        file_data   = b.get("file_data","")      # base64 encoded
        file_name   = b.get("file_name","")       # e.g. main.py
        file_type   = b.get("file_type","client") # client | admin | unified
        description = b.get("description","")
        if not file_data or not file_name:
            self._json({"ok":False,"error":"أرفق الملف واسمه"}); return
        # Decode base64
        try:
            raw = _b64.b64decode(file_data)
        except Exception as e:
            self._json({"ok":False,"error":f"خطأ في ترميز الملف: {e}"}); return
        # Validate it's Python
        allowed = {"main.py","main_admin.py","unified_server.py"}
        safe_name = _os.path.basename(file_name)
        if safe_name not in allowed:
            self._json({"ok":False,"error":f"الملف المسموح به: {', '.join(allowed)}"}); return
        # Syntax check
        try:
            import ast as _ast
            _ast.parse(raw.decode("utf-8"))
        except SyntaxError as e:
            self._json({"ok":False,"error":f"خطأ في صياغة Python في السطر {e.lineno}: {e.msg}"}); return
        # Backup current file
        current_dir = _os.path.dirname(_os.path.abspath(__file__))
        target_path = _os.path.join(current_dir, safe_name)
        backup_dir  = _os.path.join(HOTEL_DIR, "backups", "updates")
        _os.makedirs(backup_dir, exist_ok=True)
        if _os.path.exists(target_path):
            import shutil as _sh, time as _tm
            bk_name = f"{safe_name}.backup_{int(_tm.time())}"
            _sh.copy2(target_path, _os.path.join(backup_dir, bk_name))
            log.info(f"Backup created: {bk_name}")
        # Write new file
        with open(target_path, "wb") as f:
            f.write(raw)
        chk = _hs.md5(raw).hexdigest()[:8]
        size_kb = round(len(raw)/1024, 1)
        log.info(f"Update uploaded: {safe_name} ({size_kb}KB) md5:{chk}")
        # Record update history
        updates = adm.get("update_history", [])
        updates.append({
            "file": safe_name, "size_kb": size_kb, "md5": chk,
            "description": description, "uploaded_at": _iso(),
            "lines": raw.decode("utf-8","ignore").count("\n"),
        })
        adm.set("update_history", updates[-20:])
        analytics.track_action("admin","update_upload",f"{safe_name} {size_kb}KB")
        self._json({
            "ok":     True,
            "file":   safe_name,
            "size_kb": size_kb,
            "md5":    chk,
            "message": f"تم رفع {safe_name} ({size_kb} KB) بنجاح — أعد تشغيل الخادم لتفعيل التحديث",
            "restart_needed": True,
        })

    def _p_update_status(self, b):
        history = adm.get("update_history", [])
        self._json({"ok":True,"history":history[-10:]})

    def _build_client_login(self):
        return """<!DOCTYPE html><html lang="ar" dir="rtl"><head><meta charset="UTF-8"/><meta name="viewport" content="width=device-width,initial-scale=1"/><title>دخول — نظام إدارة الفندق</title>
<style>*{box-sizing:border-box;margin:0;padding:0;font-family:system-ui,Arial,sans-serif;direction:rtl;}body{background:linear-gradient(135deg,#0F172A,#1E3A5F);min-height:100vh;display:flex;align-items:center;justify-content:center;padding:20px;}
.card{background:#fff;border-radius:16px;padding:36px;width:360px;box-shadow:0 20px 60px rgba(0,0,0,.3);}
.logo{text-align:center;margin-bottom:24px;}.logo-icon{font-size:44px;margin-bottom:8px;}.logo-title{font-size:20px;font-weight:700;color:#0F172A;}.logo-sub{font-size:12px;color:#64748B;margin-top:3px;}
.tabs{display:flex;gap:0;border-radius:8px;overflow:hidden;border:1.5px solid #E2E8F0;margin-bottom:20px;}
.tab{flex:1;padding:9px;text-align:center;cursor:pointer;font-size:12px;font-weight:600;color:#64748B;background:#F8FAFC;transition:all .15s;}
.tab.on{background:#1A56DB;color:#fff;}
.pg{display:none;}.pg.on{display:block;}
.fg{margin-bottom:12px;}.fg label{font-size:11px;font-weight:600;color:#64748B;display:block;margin-bottom:4px;}.fg input,.fg select{width:100%;border:1.5px solid #E2E8F0;border-radius:8px;padding:9px 11px;font-size:12px;transition:border-color .15s;}.fg input:focus,.fg select:focus{outline:none;border-color:#1A56DB;}
.btn{width:100%;padding:11px;background:linear-gradient(135deg,#1A56DB,#7C3AED);color:#fff;border:none;border-radius:9px;font-size:13px;font-weight:700;cursor:pointer;margin-top:4px;}
.btn:hover{opacity:.88;}.btn-s{background:linear-gradient(135deg,#047857,#10B981);}
.err{color:#DC2626;font-size:11px;margin-top:8px;text-align:center;display:none;}
.ok{color:#047857;font-size:11px;margin-top:8px;text-align:center;display:none;}
.link{color:#1A56DB;font-size:11px;text-align:center;margin-top:12px;cursor:pointer;}
.trial-info{background:#EEF2FF;border-radius:8px;padding:10px 12px;font-size:11px;color:#3730A3;margin-bottom:12px;text-align:center;}
</style></head><body>
<div class="card">
<div class="logo"><div class="logo-icon">🏨</div><div class="logo-title" id="sys-name">نظام إدارة الفندق</div><div class="logo-sub">سجّل دخولك للبدء</div></div>
<div class="tabs"><div class="tab on" onclick="switchTab('login')">دخول</div><div class="tab" onclick="switchTab('register')">تجربة مجانية</div></div>

<div class="pg on" id="pg-login">
  <div class="fg"><label>البريد الإلكتروني</label><input type="email" id="l-email" placeholder="hotel@example.com" onkeydown="if(event.key==='Enter')login()"/></div>
  <button class="btn" onclick="login()">دخول</button>
  <div class="err" id="l-err"></div>
</div>

<div class="pg" id="pg-register">
  <div class="trial-info">⭐ تجربة مجانية 15 يوم — بدون بطاقة</div>
  <div class="fg"><label>اسمك *</label><input id="r-name" placeholder="محمد العمري"/></div>
  <div class="fg"><label>اسم الفندق / المنشأة *</label><input id="r-hotel" placeholder="فندق النخبة"/></div>
  <div class="fg"><label>بريدك الإلكتروني *</label><input type="email" id="r-email" placeholder="you@hotel.sa"/></div>
  <div class="fg"><label>رقم الجوال</label><input id="r-phone" placeholder="05xxxxxxxx"/></div>
  <div class="fg"><label>المدينة</label>
    <select id="r-city"><option value="riyadh">الرياض</option><option value="jeddah">جدة</option><option value="makkah">مكة المكرمة</option><option value="madinah">المدينة المنورة</option><option value="dammam">الدمام</option><option value="khobar">الخبر</option><option value="jubail">الجبيل</option><option value="ahsa">الأحساء</option><option value="abha">أبها</option><option value="taif">الطائف</option><option value="tabuk">تبوك</option><option value="qassim">القصيم</option><option value="hail">حائل</option><option value="bahah">الباحة</option><option value="other">أخرى</option></select>
  </div>
  <div class="fg"><label>نوع المنشأة</label>
    <select id="r-type"><option value="hotel">فندق</option><option value="apart">شقق فندقية</option><option value="service">شقق مخدومة</option></select>
  </div>
  <div class="fg"><label>عدد الغرف / الوحدات</label><input type="number" id="r-rooms" placeholder="50" min="1"/></div>
  <button class="btn btn-s" onclick="register()">ابدأ التجربة المجانية ←</button>
  <div class="err" id="r-err"></div>
  <div class="ok" id="r-ok"></div>
</div>
</div>

<script>
function switchTab(t){
  document.querySelectorAll('.tab').forEach((el,i)=>el.classList.toggle('on',i===(t==='login'?0:1)));
  document.querySelectorAll('.pg').forEach((el,i)=>el.classList.toggle('on',i===(t==='login'?0:1)));
}
async function login(){
  const email=document.getElementById('l-email').value.trim();
  if(!email){showErr('l-err','أدخل الإيميل');return;}
  const r=await fetch('/api/client/login',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({email})});
  const d=await r.json();
  if(d.ok){location.href='/';}
  else if(d.error==='expired'){showExpiredPage(d);}
  else showErr('l-err',d.error||'خطأ');
}
function showExpiredPage(d){
  const wa=d.whatsapp||'';const ph=d.phone||'';
  const bank=d.bank||{};
  const plans=(d.plans||[]).filter(p=>p.price>0);
  let sel=plans[0]||{id:'pro',name:'احترافية',price:299,period:'شهري',color:'#185FA5'};
  let payM='mada';

  function render(){
    document.querySelector('.card').innerHTML=`
    <div style="text-align:center;margin-bottom:14px">
      <div style="font-size:38px;margin-bottom:6px">⏰</div>
      <div style="font-size:17px;font-weight:700;color:#0F172A">انتهت فترة التجربة</div>
      <div style="font-size:11px;color:#64748B;margin-top:3px">${d.message||'تواصل معنا لتجديد اشتراكك'}</div>
    </div>
    ${plans.length?`<div style="display:grid;grid-template-columns:repeat(${Math.min(plans.length,3)},1fr);gap:7px;margin-bottom:12px">
      ${plans.map(p=>`<div onclick="sel={id:'${p.id}',name:'${p.name}',price:${p.price},period:'${p.period||'شهري'}',color:'${p.color||'#185FA5'}'};render()" style="border-radius:9px;border:2px solid ${p.color||'#185FA5'};padding:10px;text-align:center;cursor:pointer;background:${sel.id===p.id?'#F0F7FF':'#fff'}">
        <div style="font-size:11px;font-weight:700;color:${p.color||'#185FA5'}">${p.name}</div>
        <div style="font-size:20px;font-weight:700;color:${p.color||'#185FA5'};margin:2px 0">${p.price}</div>
        <div style="font-size:10px;color:#64748B">ر.س/${p.period||'شهر'}</div>
      </div>`).join('')}
    </div>`:''}
    <div style="display:grid;grid-template-columns:1fr 1fr;gap:6px;margin-bottom:10px">
      <label style="display:flex;align-items:center;gap:7px;padding:9px 11px;border:2px solid ${payM==='mada'?'#185FA5':'#E2E8F0'};border-radius:9px;cursor:pointer;background:${payM==='mada'?'#EEF8FF':'#fff'}">
        <input type="radio" name="pay-m" value="mada" ${payM==='mada'?'checked':''} onchange="payM='mada';render()" style="width:auto;accent-color:#185FA5"/>
        <div><div style="font-size:12px;font-weight:700;color:#185FA5">💳 مدى</div><div style="font-size:10px;color:#64748B">دفع إلكتروني</div></div>
      </label>
      <label style="display:flex;align-items:center;gap:7px;padding:9px 11px;border:2px solid ${payM==='transfer'?'#3B6D11':'#E2E8F0'};border-radius:9px;cursor:pointer;background:${payM==='transfer'?'#F0FDF4':'#fff'}">
        <input type="radio" name="pay-m" value="transfer" ${payM==='transfer'?'checked':''} onchange="payM='transfer';render()" style="width:auto;accent-color:#3B6D11"/>
        <div><div style="font-size:12px;font-weight:700;color:#3B6D11">🏦 تحويل بنكي</div><div style="font-size:10px;color:#64748B">IBAN مباشر</div></div>
      </label>
    </div>
    ${payM==='mada'?`
      <button id="mada-pay-btn" onclick="startPayment()" style="width:100%;padding:12px;background:#185FA5;color:#fff;border:none;border-radius:9px;font-size:13px;font-weight:700;cursor:pointer;margin-bottom:6px">💳 ادفع ${sel.price} ر.س بمدى الآن</button>
      <div id="mada-frame"></div>`:`
      <div style="background:#F0FDF4;border-radius:9px;padding:11px 13px;margin-bottom:8px;border:1px solid #86EFAC">
        <div style="font-size:11px;font-weight:700;color:#166534;margin-bottom:7px">🏦 بيانات التحويل البنكي</div>
        ${bank.name?`<div style="font-size:11px;color:#374151;margin-bottom:3px">اسم الحساب: <b>${bank.name}</b></div>`:''}
        ${bank.bank?`<div style="font-size:11px;color:#374151;margin-bottom:3px">البنك: <b>${bank.bank}</b></div>`:''}
        ${bank.iban?`<div style="font-family:monospace;font-size:13px;font-weight:700;color:#166534;background:#BBF7D0;padding:7px 10px;border-radius:7px;margin-bottom:5px;letter-spacing:.5px">${bank.iban}</div><button onclick="navigator.clipboard.writeText('${bank.iban}').then(()=>this.textContent='✓ تم النسخ')" style="font-size:10px;padding:3px 9px;border:1px solid #86EFAC;border-radius:6px;background:#fff;color:#166534;cursor:pointer;margin-bottom:8px">نسخ IBAN</button>`:'<div style="font-size:11px;color:#DC2626;margin-bottom:6px">لم يُضف IBAN — تواصل مع الدعم</div>'}
        <div style="font-size:11px;color:#374151;margin-bottom:2px">المبلغ: <b style="color:#166534;font-size:13px">${sel.price} ر.س</b></div>
        <div style="font-size:10px;color:#64748B">المرجع: <b>HOTEL-RENEWAL-${sel.id.toUpperCase()}</b></div>
      </div>
      <input id="trans-ref" placeholder="رقم مرجع التحويل (اختياري)" style="width:100%;border:1.5px solid #E2E8F0;border-radius:8px;padding:8px 11px;font-size:12px;margin-bottom:6px;font-family:inherit"/>
      <button onclick="confirmTransfer()" style="width:100%;padding:11px;background:#3B6D11;color:#fff;border:none;border-radius:9px;font-size:13px;font-weight:700;cursor:pointer;margin-bottom:6px">✓ أرسلت التحويل — أبلغنا للتفعيل</button>`}
    <div id="pay-msg" style="display:none;background:#F0FDF4;border-radius:8px;padding:9px;font-size:11px;color:#166534;text-align:center;margin-bottom:6px"></div>
    ${wa?`<a href="https://wa.me/${wa}?text=${encodeURIComponent('مرحباً، أريد تجديد اشتراكي — خطة '+sel.name+' '+sel.price+' ر.س')}" target="_blank" style="display:flex;align-items:center;justify-content:center;gap:7px;padding:10px;background:#25D366;color:#fff;border-radius:9px;text-decoration:none;font-size:12px;font-weight:700;margin-bottom:5px">💬 تواصل واتساب للتجديد</a>`:''}
    <div style="text-align:center;font-size:10px;color:#94A3B8;margin-top:6px">بياناتك محفوظة — ستُستعاد فور التجديد</div>`;
  }

  window.startPayment=async function(){
    const btn=document.getElementById('mada-pay-btn');
    if(btn){btn.textContent='جارٍ الإنشاء...';btn.disabled=true;}
    try{
      const r=await fetch('/api/payment/create',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({plan:sel.id,method:'mada',period:'monthly'})});
      const data=await r.json();
      const frame=document.getElementById('mada-frame');
      if(data.ok&&data.payment){
        if(data.payment.payment_url){
          frame.innerHTML=`<div style="margin-top:8px;border-radius:10px;overflow:hidden;border:1.5px solid #E2E8F0"><iframe src="${data.payment.payment_url}" style="width:100%;height:420px;border:none" title="صفحة الدفع"></iframe></div>`;
        } else {
          frame.innerHTML=`<div style="margin-top:6px;background:#FEF3C7;border-radius:8px;padding:10px 12px;font-size:11px;color:#92400E"><b>تنبيه:</b> أضف مفاتيح Geidea في إعدادات لوحة المالك لتفعيل الدفع الإلكتروني بمدى. استخدم التحويل البنكي في الوقت الحالي.</div>`;
        }
      }
    }catch(e){const f=document.getElementById('mada-frame');if(f)f.innerHTML=`<div style="color:#DC2626;font-size:11px;margin-top:5px">${e.message}</div>`;}
    if(btn){btn.textContent=`💳 ادفع ${sel.price} ر.س بمدى`;btn.disabled=false;}
  };

  window.confirmTransfer=async function(){
    const ref=document.getElementById('trans-ref')?.value?.trim()||'';
    const cr=await fetch('/api/payment/create',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({plan:sel.id,method:'transfer',period:'monthly'})});
    const cd=await cr.json();
    if(cd.ok){
      const conf=await fetch('/api/payment/confirm',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({payment_id:cd.payment.id,ref})});
      const confData=await conf.json();
      const msg=document.getElementById('pay-msg');
      if(msg){msg.style.display='block';msg.textContent=confData.ok?'✅ تم إرسال طلب التأكيد — سيتواصل معك الدعم خلال ساعات':'خطأ: '+(confData.error||'حاول مرة أخرى');msg.style.color=confData.ok?'#166534':'#DC2626';}
    }
  };

  render();
}
async function register(){
  const name=document.getElementById('r-name').value.trim();
  const email=document.getElementById('r-email').value.trim();
  if(!name||!email){showErr('r-err','أدخل الاسم والإيميل');return;}
  const r=await fetch('/api/client/register',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({
    name,hotel_name:document.getElementById('r-hotel').value||name,
    email,phone:document.getElementById('r-phone').value,
    city:document.getElementById('r-city').value,
    hotel_type:document.getElementById('r-type').value,
    rooms:document.getElementById('r-rooms').value||50,
  })});
  const d=await r.json();
  if(d.ok){location.href='/';}else showErr('r-err',d.error||'خطأ');
}
function showErr(id,msg){const e=document.getElementById(id);e.textContent=msg;e.style.display='block';setTimeout(()=>e.style.display='none',4000);}
</script></body></html>"""

    def _build_register_html(self):
        return self._build_client_login()

    def _build_admin_stats(self, amod):
        """Build admin stats from adm store"""
        clients  = amod.adm.get("clients", [])
        keys     = amod.adm.get("license_keys", [])
        tickets  = amod.adm.get("tickets", [])
        payments = amod.adm.get("payments", [])
        s        = amod.adm.get("admin_settings", {})
        prices   = s.get("prices", {"free":0,"pro":299,"enterprise":799})
        active   = [c for c in clients if c.get("status")=="active"]
        trial    = [c for c in clients if c.get("status")=="trial"]
        mrr      = sum(prices.get(c.get("plan","free"),0) for c in active)
        return {
            "total_clients": len(clients),
            "active":        len(active),
            "trial":         len(trial),
            "mrr":           mrr,
            "total_keys":    len(keys),
            "open_tickets":  len([t for t in tickets if t.get("status")=="open"]),
            "total_payments":len(payments),
        }


    # ── Admin operation helpers (called from port 5050 /admin route) ─────────
    def _admin_plan_add(self, amod, b):
        s = amod.adm.get("admin_settings", {})
        plans = s.get("plans", [])
        new_plan = {"id": f"custom_{_id()}", "name": b.get("name","خطة"), "price": float(b.get("price",0)),
            "period": b.get("period","شهري"), "color": b.get("color","#185FA5"), "badge": b.get("badge",""),
            "branch_fee": float(b.get("branch_fee",0)), "branch_enabled": b.get("branch_enabled",False),
            "pos_devices": int(b.get("pos_devices",1)), "max_guests": int(b.get("max_guests",0)),
            "features": b.get("features",[]), "excluded": b.get("excluded",[])}
        plans.append(new_plan)
        s["plans"] = plans
        s.setdefault("prices",{})[new_plan["id"]] = new_plan["price"]
        amod.adm.set("admin_settings", s)
        self._json({"ok": True, "plan": new_plan})

    def _admin_plan_del(self, amod, b):
        pid = b.get("id")
        s = amod.adm.get("admin_settings", {})
        s["plans"] = [p for p in s.get("plans",[]) if p.get("id") != pid]
        s.get("prices",{}).pop(pid, None)
        amod.adm.set("admin_settings", s)
        self._json({"ok": True})

    def _admin_plan_dup(self, amod, b):
        import copy as _cp
        pid = b.get("id")
        s = amod.adm.get("admin_settings", {})
        plans = s.get("plans", [])
        orig = next((p for p in plans if p.get("id")==pid), None)
        if not orig:
            self._json({"ok":False,"error":"الخطة غير موجودة"}); return
        dup = _cp.deepcopy(orig)
        dup["id"] = f"custom_{_id()}"
        dup["name"] = orig["name"] + " — نسخة"
        plans.append(dup)
        s["plans"] = plans
        s.setdefault("prices",{})[dup["id"]] = dup["price"]
        amod.adm.set("admin_settings", s)
        self._json({"ok": True, "plan": dup})

    def _admin_comp_add(self, amod, b):
        s = amod.adm.get("admin_settings", {})
        comps = s.get("ai_market_competitors", [])
        comps.append({"name":b.get("name",""),"price_from":float(b.get("price_from",0)),
            "price_to":float(b.get("price_to",0)),"currency":b.get("currency","USD/month"),
            "target":b.get("target",""),"strengths":b.get("strengths",[]),
            "weaknesses":b.get("weaknesses",[]),"market":b.get("market","mid")})
        s["ai_market_competitors"] = comps
        amod.adm.set("admin_settings", s)
        self._json({"ok": True})

    def _admin_comp_del(self, amod, b):
        idx = b.get("index", -1)
        s = amod.adm.get("admin_settings", {})
        comps = s.get("ai_market_competitors", [])
        if 0 <= idx < len(comps): comps.pop(idx)
        s["ai_market_competitors"] = comps
        amod.adm.set("admin_settings", s)
        self._json({"ok": True})

    def _admin_client_add(self, amod, b):
        trial_days = amod.adm.get("admin_settings",{}).get("trial_days",15)
        client = {"id":_id(),"name":b.get("name",""),"hotel_name":b.get("hotel_name",b.get("name","")),"email":b.get("email",""),"phone":b.get("phone",""),"city":b.get("city","riyadh"),"hotel_type":b.get("hotel_type","hotel"),"rooms":int(b.get("rooms",0)),"plan":b.get("plan","trial"),"status":"trial","trial_start":_today(),"trial_end":key_expiry(trial_days),"license_key":"","notes":b.get("notes",""),"created_at":_iso(),"last_login":None,"custom_settings":{}}
        amod.adm.append("clients", client)
        ticket = {"id":_id(),"title":"مرحباً بك","client_id":str(client["id"]),"client_name":client["hotel_name"],"status":"open","priority":"normal","category":"onboarding","created_at":_iso(),"messages":[{"from":"admin","name":"الدعم","text":f"أهلاً {client['name']}! تهانينا بتسجيلك.","time":_iso()}]}
        amod.adm.append("tickets", ticket)
        self._json({"ok": True, "client": client})

    def _admin_client_toggle(self, amod, b):
        cid = b.get("id"); action = b.get("action","suspend")
        clients = amod.adm.get("clients", [])
        for c in clients:
            if str(c.get("id"))==str(cid): c["status"] = "active" if action=="activate" else "suspended"
        amod.adm.set("clients", clients)
        self._json({"ok": True})

    def _admin_client_extend(self, amod, b):
        cid = b.get("id"); days = int(b.get("days",7))
        clients = amod.adm.get("clients", [])
        for c in clients:
            if str(c.get("id"))==str(cid):
                base = date.fromisoformat(c.get("trial_end", str(date.today())))
                if base < date.today(): base = date.today()
                c["trial_end"] = (base + timedelta(days=days)).isoformat()
                c["status"] = "trial"
        amod.adm.set("clients", clients)
        self._json({"ok": True})

    def _admin_client_delete(self, amod, b):
        cid = b.get("id")
        clients = [c for c in amod.adm.get("clients",[]) if str(c.get("id"))!=str(cid)]
        amod.adm.set("clients", clients)
        self._json({"ok": True})

    def _admin_keys_generate(self, amod, b):
        plan = b.get("plan","pro"); days = int(b.get("days",30)); count = int(b.get("count",1))
        cid = b.get("client_id"); note = b.get("notes","")
        new_keys = []
        for _ in range(min(count,20)):
            k = {"id":_id(),"key":gen_key(plan),"plan":plan,"days":days,"status":"assigned" if cid else "unused","created_at":_iso(),"expires_at":key_expiry(days),"client_id":cid,"client_name":"","used_at":None,"notes":note}
            if cid:
                clients = amod.adm.get("clients",[])
                c = next((x for x in clients if str(x.get("id"))==str(cid)),None)
                if c:
                    k["client_name"] = c.get("hotel_name",c.get("name",""))
                    c["license_key"] = k["key"]; c["plan"] = plan; c["status"] = "active"; c["trial_end"] = k["expires_at"]
                    amod.adm.set("clients", clients)
            amod.adm.append("license_keys", k)
            new_keys.append(k)
        self._json({"ok": True, "keys": new_keys})

    def _admin_key_revoke(self, amod, b):
        kid = b.get("id")
        keys = amod.adm.get("license_keys",[])
        for k in keys:
            if str(k.get("id"))==str(kid): k["status"] = "revoked"
        amod.adm.set("license_keys", keys)
        self._json({"ok": True})

    def _admin_ticket_add(self, amod, b):
        t = {"id":_id(),"title":b.get("title",""),"client_id":str(b.get("client_id","")),"client_name":b.get("client_name",""),"priority":b.get("priority","normal"),"status":"open","category":b.get("category","support"),"created_at":_iso(),"messages":[{"from":"admin","name":"الدعم","text":b.get("message",""),"time":_iso()}]}
        amod.adm.append("tickets", t)
        self._json({"ok": True, "ticket": t})

    def _admin_ticket_reply(self, amod, b):
        tid = b.get("id"); text = b.get("text","")
        tickets = amod.adm.get("tickets",[])
        for t in tickets:
            if str(t.get("id"))==str(tid):
                t.setdefault("messages",[]).append({"from":"admin","name":"الدعم","text":text,"time":_iso()})
                t["status"] = "replied"
        amod.adm.set("tickets", tickets)
        self._json({"ok": True})

    def _admin_ticket_close(self, amod, b):
        tid = b.get("id")
        tickets = amod.adm.get("tickets",[])
        for t in tickets:
            if str(t.get("id"))==str(tid): t["status"] = "closed"
        amod.adm.set("tickets", tickets)
        self._json({"ok": True})

    def _admin_payment_add(self, amod, b):
        cid = b.get("client_id"); amt = float(b.get("amount",0))
        plan = b.get("plan","pro")
        pay = {"id":_id(),"client_id":cid,"client_name":b.get("client_name",""),"amount":amt,"plan":plan,"method":b.get("method","transfer"),"ref":b.get("ref",""),"date":b.get("date",_today()),"notes":b.get("notes","")}
        amod.adm.append("payments", pay)
        # Auto-generate key
        k = {"id":_id(),"key":gen_key(plan),"plan":plan,"days":30,"status":"used","created_at":_iso(),"expires_at":key_expiry(30),"client_id":cid,"client_name":pay["client_name"],"used_at":_iso(),"notes":f"دفعة {pay['id']}"}
        amod.adm.append("license_keys", k)
        if cid:
            clients = amod.adm.get("clients",[])
            c = next((x for x in clients if str(x.get("id"))==str(cid)),None)
            if c: c["license_key"] = k["key"]; c["plan"] = plan; c["status"] = "active"; c["trial_end"] = k["expires_at"]; amod.adm.set("clients", clients)
        self._json({"ok": True, "payment": pay, "key": k})

    def _admin_market_ai(self, amod, b):
        import urllib.request as _ur, re as _re
        s = amod.adm.get("admin_settings", {})
        key = b.get("claude_key", s.get("claude_key",""))
        result = {"ok":True,"source":"builtin","competitors":[
            {"name":"Opera Cloud","price_from":500,"price_to":2000,"currency":"USD/month","target":"فنادق كبرى","strengths":["عالمي","تكامل كامل"],"weaknesses":["غالٍ جداً","ليس عربي"],"market":"enterprise"},
            {"name":"Cloudbeds","price_from":200,"price_to":800,"currency":"USD/month","target":"فنادق مستقلة","strengths":["سهل","API قوي"],"weaknesses":["بالإنجليزية","لا يدعم العربية"],"market":"mid"},
            {"name":"Mews","price_from":250,"price_to":900,"currency":"USD/month","target":"فنادق بوتيك","strengths":["عصري","أتمتة"],"weaknesses":["ليس عربي","دعم محدود"],"market":"mid"},
        ],"our_advantage":["🇸🇦 الوحيد عربي 100%","💰 أرخص 70% من Opera","⚡ إعداد 10 دقائق"],"market_gap":"لا يوجد نظام عربي للفنادق الصغيرة","price_positioning":"299 ر.س/شهر — أقل من 20% من Opera"}
        s["ai_market_competitors"] = result["competitors"]
        s["last_market_analysis"] = {"date":_iso(),"advantage":result["our_advantage"],"gap":result["market_gap"],"positioning":result["price_positioning"]}
        amod.adm.set("admin_settings", s)
        self._json(result)

    def _admin_branch_add(self, amod, b):
        pid = b.get("parent_id")
        clients = amod.adm.get("clients",[])
        parent = next((c for c in clients if str(c.get("id"))==str(pid)),None)
        if not parent: self._json({"ok":False,"error":"الحساب الرئيسي غير موجود"}); return
        branch = {"id":_id(),"name":b.get("name",""),"hotel_name":b.get("hotel_name",b.get("name","")),"email":b.get("email",""),"phone":b.get("phone",""),"city":b.get("city",parent.get("city","")),"hotel_type":b.get("hotel_type","hotel"),"rooms":int(b.get("rooms",0)),"plan":parent.get("plan","trial"),"status":"active" if parent.get("status")=="active" else "trial","trial_start":_today(),"trial_end":parent.get("trial_end",key_expiry(15)),"license_key":parent.get("license_key",""),"parent_id":str(pid),"parent_name":parent.get("hotel_name",""),"is_branch":True,"notes":b.get("notes",""),"created_at":_iso(),"last_login":None,"custom_settings":{}}
        amod.adm.append("clients", branch)
        parent.setdefault("branches",[]).append(str(branch["id"]))
        amod.adm.set("clients", clients)
        self._json({"ok": True, "branch": branch})

    def _admin_branch_del(self, amod, b):
        bid = b.get("id")
        clients = amod.adm.get("clients",[])
        branch = next((c for c in clients if str(c.get("id"))==str(bid) and c.get("is_branch")),None)
        if branch:
            parent = next((c for c in clients if str(c.get("id"))==str(branch.get("parent_id",""))),None)
            if parent and "branches" in parent:
                parent["branches"] = [x for x in parent["branches"] if str(x)!=str(bid)]
        amod.adm.set("clients",[c for c in clients if str(c.get("id"))!=str(bid)])
        self._json({"ok": True})

    def _admin_proxy_post(self, amod, path, b):
        """Proxy POST request to admin handler"""
        try:
            # Map common admin POST paths to their handlers
            handler_map = {
                "/api/admin/clients/add":       lambda: amod.AdminHandler._p_add_client_static(amod, b),
                "/api/admin/clients/toggle":    lambda: amod.AdminHandler._p_toggle_client_static(amod, b),
                "/api/admin/clients/extend":    lambda: amod.AdminHandler._p_extend_client_static(amod, b),
                "/api/admin/clients/delete":    lambda: amod.AdminHandler._p_delete_client_static(amod, b),
                "/api/admin/keys/generate":     lambda: amod.AdminHandler._p_generate_keys_static(amod, b),
                "/api/admin/keys/revoke":       lambda: amod.AdminHandler._p_revoke_key_static(amod, b),
                "/api/admin/tickets/add":       lambda: amod.AdminHandler._p_add_ticket_static(amod, b),
                "/api/admin/tickets/reply":     lambda: amod.AdminHandler._p_reply_ticket_static(amod, b),
                "/api/admin/tickets/close":     lambda: amod.AdminHandler._p_close_ticket_static(amod, b),
                "/api/admin/payments/add":      lambda: amod.AdminHandler._p_add_payment_static(amod, b),
                "/api/admin/push":              lambda: self._p_admin_push(b),
                "/api/admin/update/upload":     lambda: self._p_update_upload(b),
                "/api/admin/update/status":     lambda: self._json({"ok":True,"history":amod.adm.get("update_history",[])[-10:]}),
                "/api/admin/settings/save":     lambda: self._admin_save_settings(amod, b),
                    "/api/admin/plans/add":         lambda: self._admin_plan_add(amod, b),
                "/api/admin/plans/delete":      lambda: self._admin_plan_del(amod, b),
                "/api/admin/plans/duplicate":   lambda: self._admin_plan_dup(amod, b),
                "/api/admin/competitors/add":   lambda: self._admin_comp_add(amod, b),
                "/api/admin/competitors/delete":lambda: self._admin_comp_del(amod, b),
                "/api/admin/clients/add":       lambda: self._admin_client_add(amod, b),
                "/api/admin/clients/toggle":    lambda: self._admin_client_toggle(amod, b),
                "/api/admin/clients/extend":    lambda: self._admin_client_extend(amod, b),
                "/api/admin/clients/delete":    lambda: self._admin_client_delete(amod, b),
                "/api/admin/keys/generate":     lambda: self._admin_keys_generate(amod, b),
                "/api/admin/keys/revoke":       lambda: self._admin_key_revoke(amod, b),
                "/api/admin/tickets/add":       lambda: self._admin_ticket_add(amod, b),
                "/api/admin/tickets/reply":     lambda: self._admin_ticket_reply(amod, b),
                "/api/admin/tickets/close":     lambda: self._admin_ticket_close(amod, b),
                "/api/admin/payments/add":      lambda: self._admin_payment_add(amod, b),
                "/api/admin/push":              lambda: self._p_admin_push(b),
                "/api/admin/update/upload":     lambda: self._p_update_upload(b),
                "/api/admin/update/status":     lambda: self._json({"ok":True,"history":amod.adm.get("update_history",[])[-10:]}),
                "/api/admin/market/ai":         lambda: self._admin_market_ai(amod, b),
                "/api/admin/branches/add":      lambda: self._admin_branch_add(amod, b),
                "/api/admin/branches/delete":   lambda: self._admin_branch_del(amod, b),
                "/api/ai/control":              lambda: self._p_ai_control(b, None, None),
            }
            fn = handler_map.get(path)
            if fn:
                fn()
            else:
                self._json({"error": f"Admin route not found: {path}"}, 404)
        except Exception as e:
            log.error(f"Admin proxy error {path}: {e}")
            self._json({"ok": False, "error": str(e)})

    def _admin_save_settings(self, amod, b):
        """Save admin settings directly"""
        s = amod.adm.get("admin_settings", {})
        allowed_keys = [
            "owner_name","owner_email","owner_phone","owner_whatsapp","contact_message",
            "system_name","bank_name","bank_iban","owner_bank","owner_iban","owner_account_name",
            "trial_days","prices","plans","discount_quarterly","discount_semi","discount_annual",
            "claude_key","mk","ap","ai_market_competitors","last_market_analysis",
        ]
        for k in allowed_keys:
            if k in b:
                s[k] = b[k]
        amod.adm.set("admin_settings", s)
        self._json({"ok": True})

    def _build_client_html(self, client, store):
        """
        يُحمّل لوحة العميل الكاملة من main.py مباشرة.
        يستخدم importlib لتحميل _build_html() من main.py
        ثم يحقن بيانات العميل والاشتراك في الصفحة.
        """
        try:
            import importlib.util as _ilu
            _main_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "main.py")
            if os.path.exists(_main_path):
                _spec = _ilu.spec_from_file_location("hotel_main", _main_path)
                _mod  = _ilu.module_from_spec(_spec)
                # Suppress webbrowser.open during import
                import webbrowser as _wb
                _orig_open = _wb.open
                _wb.open = lambda *a, **k: None
                try:
                    _spec.loader.exec_module(_mod)
                finally:
                    _wb.open = _orig_open
                # Get the full HTML from main.py
                html = _mod._build_html()
                # Inject client context (subscription status, trial info)
                if client:
                    name      = client.get("hotel_name", client.get("name", ""))
                    status    = client.get("status", "trial")
                    trial_end = client.get("trial_end", "")
                    plan      = client.get("plan", "trial")
                    dl        = days_left(trial_end) if trial_end else None
                    # Inject a small script with client context right before </body>
                    inject = f"""<script>
window._CLIENT_CONTEXT = {{
  name: {json.dumps(name)},
  status: {json.dumps(status)},
  plan: {json.dumps(plan)},
  trial_end: {json.dumps(trial_end)},
  days_left: {json.dumps(dl)},
  hotel_type: {json.dumps(client.get('hotel_type','hotel'))},
  city: {json.dumps(client.get('city',''))},
  rooms: {json.dumps(client.get('rooms',0))},
}};
// Show trial warning if applicable
if(window._CLIENT_CONTEXT.days_left !== null && window._CLIENT_CONTEXT.days_left <= 3 && window._CLIENT_CONTEXT.status === 'trial'){{
  document.addEventListener('DOMContentLoaded',function(){{
    const banner = document.createElement('div');
    banner.style.cssText = 'position:fixed;top:0;right:0;left:0;z-index:9999;background:#854F0B;color:#fff;padding:8px 16px;text-align:center;font-size:12px;font-family:system-ui,Arial,sans-serif;direction:rtl;';
    banner.innerHTML = 'تبقّت <b>' + window._CLIENT_CONTEXT.days_left + ' أيام</b> من تجربتك المجانية — <a href="/subscriptions" style="color:#FCD34D;font-weight:700;">فعّل اشتراكك الآن</a>';
    document.body.prepend(banner);
  }});
}}
</script>"""
                    html = html.replace("</body>", inject + "\n</body>")
                return html
        except Exception as e:
            log.error(f"_build_client_html error: {e}")

        # Fallback — full embedded client panel if main.py fails to load
        name = client["hotel_name"] if client else "نظام إدارة الفندق"
        return f"""<!DOCTYPE html>
<html lang="ar" dir="rtl">
<head>
<meta charset="UTF-8"/>
<meta name="viewport" content="width=device-width,initial-scale=1"/>
<title>{name}</title>
<style>
*{{box-sizing:border-box;margin:0;padding:0;font-family:system-ui,Arial,sans-serif;direction:rtl;}}
body{{background:#F1F5F9;display:flex;align-items:center;justify-content:center;min-height:100vh;padding:20px;}}
.card{{background:#fff;border-radius:16px;padding:32px;max-width:400px;width:100%;text-align:center;border:0.5px solid #E2E8F0;}}
.ico{{font-size:48px;margin-bottom:12px;}}
h1{{font-size:20px;font-weight:500;color:#0F172A;margin-bottom:8px;}}
p{{font-size:13px;color:#64748B;line-height:1.6;margin-bottom:16px;}}
.btn{{display:block;padding:12px;background:#185FA5;color:#fff;border-radius:9px;text-decoration:none;font-size:13px;font-weight:500;}}
</style>
</head>
<body>
<div class="card">
  <div class="ico">🏨</div>
  <h1>{name}</h1>
  <p>حدث خطأ في تحميل النظام. تحقق من وجود ملف main.py في نفس المجلد ثم أعد تشغيل الخادم.</p>
  <a href="/" class="btn">إعادة المحاولة</a>
</div>
</body>
</html>"""


# ══════════════════════════════════════════════════════════════
#  ADMIN HANDLER — Port 5051
# ══════════════════════════════════════════════════════════════
# نستخدم AdminHandler من main_admin.py مباشرة
try:
    import importlib.util, os as _os
    _admin_file = _os.path.join(_os.path.dirname(_os.path.abspath(__file__)),"main_admin.py")
    if _os.path.exists(_admin_file):
        _spec = importlib.util.spec_from_file_location("admin_mod", _admin_file)
        _admin_mod = importlib.util.module_from_spec(_spec)
        _spec.loader.exec_module(_admin_mod)
        AdminHandler = _admin_mod.AdminHandler
        log.info("AdminHandler loaded from main_admin.py")
    else:
        raise ImportError("main_admin.py not found")
except Exception as e:
    log.warning(f"Could not load admin handler: {e} — using stub")
    class AdminHandler(BaseH):
        def do_GET(self):
            self._html("<h2 style='font-family:system-ui;padding:40px;direction:rtl'>⚠️ ضع main_admin.py في نفس المجلد وأعد التشغيل</h2>")
        def do_POST(self): self._json({"error":"admin not loaded"})


# ══════════════════════════════════════════════════════════════
#  تشغيل الخادمين
# ══════════════════════════════════════════════════════════════
def run_client():
    sv = HTTPServer(("0.0.0.0", CLIENT_PORT), ClientHandler)
    log.info(f"Client server → port {CLIENT_PORT}")
    sv.serve_forever()

def run_admin():
    sv = HTTPServer(("0.0.0.0", ADMIN_PORT), AdminHandler)
    log.info(f"Admin  server → port {ADMIN_PORT}")
    sv.serve_forever()


def main():
    print("="*58)
    print("  نظام إدارة الفنادق — Unified SaaS Server")
    print("="*58)
    print(f"  لوحة العميل : http://localhost:{CLIENT_PORT}")
    print(f"  لوحة المالك : http://localhost:{ADMIN_PORT}/admin")
    print(f"  كلمة مرور Admin: {ADMIN_PASS}")
    print("="*58)
    t1 = threading.Thread(target=run_client, daemon=True)
    t2 = threading.Thread(target=run_admin,  daemon=True)
    t1.start(); t2.start()
    def open_b():
        time.sleep(1.5)
        webbrowser.open(f"http://localhost:{CLIENT_PORT}")
    threading.Thread(target=open_b,daemon=True).start()
    try:
        while True: time.sleep(60)
    except KeyboardInterrupt:
        print("\n  تم الإيقاف.")

if __name__ == "__main__":
    print("="*58)
    print("  نظام إدارة الفنادق — Unified SaaS Server")
    print("="*58)
    print(f"  لوحة العميل : http://localhost:{CLIENT_PORT}")
    print(f"  لوحة المالك : http://localhost:{ADMIN_PORT}/admin")
    print(f"  كلمة مرور Admin: {ADMIN_PASS}")
    print("="*58)
    t1 = threading.Thread(target=run_client, daemon=True)
    t2 = threading.Thread(target=run_admin,  daemon=True)
    t1.start(); t2.start()
    def open_b():
        time.sleep(1.5)
        webbrowser.open(f"http://localhost:{CLIENT_PORT}")
    threading.Thread(target=open_b,daemon=True).start()
    try:
        while True: time.sleep(60)
    except KeyboardInterrupt:
        print("\n  تم الإيقاف.")
