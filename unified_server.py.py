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

CLIENT_PORT = int(os.environ.get("PORT", 5050))
ADMIN_PORT  = int(os.environ.get("ADMIN_PORT", 5051))

# !! غيّر كلمة المرور هنا قبل النشر !!
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
#  ANALYTICS ENGINE — Real-time tracking
# ══════════════════════════════════════════════════════════════
import threading as _th, collections as _col

class AnalyticsEngine:
    """Real-time analytics: sessions, usage, errors, activity"""
    def __init__(self):
        self._lock       = _th.Lock()
        self.sessions    = {}
        self.page_hits   = _col.defaultdict(int)
        self.action_log  = []
        self.error_log   = []
        self.daily_stats = {}
        self.client_stats= {}
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
sessions= {}
cli_ses = {}

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
        tok = self._cookie_val("client_token")
        cid = cli_ses.get(tok)
        if cid:
            clients = adm.get("clients",[])
            client  = next((c for c in clients if str(c["id"])==str(cid)),None)
            if client: return client, ClientStore.get(cid)
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

        # ── إذا غير مسجّل، أرسله لصفحة الدخول ──────────────
        if path in ("/","/dashboard"):
            if not self._client_authed():
                self.send_response(302)
                self.send_header("Location","/login")
                self.end_headers()
                return
            client,store = self._get_client()
            self._html(self._build_client_html(client,store))
            return

        if path == "/login":
            self._html(self._build_client_login())
            return

        if path == "/register":
            self._html(self._build_register_html())
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
        clients = adm.get("clients",[])
        client  = next((c for c in clients if c.get("email","").lower()==email),None)
        if not client:
            self._json({"ok":False,"error":"الإيميل غير مسجل"}); return
        if client.get("status") == "suspended":
            self._json({"ok":False,"error":"الحساب موقوف — تواصل مع الدعم"}); return
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
        store.append("tickets",{"id":ticket["id"],"title":title,"status":"open"})
        self._json({"ok":True,"ticket":ticket})

    def _p_ticket_msg(self,b,store,client):
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

    def _api_analytics(self):
        self._json(analytics.snapshot())

    def _api_status(self):
        clients = adm.get("clients",[])
        active  = [c for c in clients if c.get("status")=="active"]
        trial   = [c for c in clients if c.get("status")=="trial"]
        snap    = analytics.snapshot()
        self._json({
            "status": "online", "version": "4.1",
            "uptime": snap["uptime_human"],
            "online_now": snap["online_now"],
            "total_clients": len(clients),
            "active_paid": len(active),
            "on_trial": len(trial),
        })

    # ══════════════════════════════════════════════════════════
    #  AI Control — نفس الكود الأصلي بدون تغيير
    # ══════════════════════════════════════════════════════════
    def _p_ai_control(self, b, store, client):
        import urllib.request as _ur, re as _re
        cmd = b.get("command", "").strip()
        s   = adm.get("admin_settings", {})
        key = b.get("claude_key", s.get("claude_key", ""))
        if not cmd:
            self._json({"ok": False, "error": "أدخل أمراً"}); return

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

=== قائمة العملاء ===
{chr(10).join(f"ID:{c['id']} | {c.get('hotel_name',c['name'])} | {c.get('email','')} | {c.get('status','')} | {c.get('plan','')} | ينتهي: {c.get('trial_end','')}" for c in clients[:20])}

=== تنتهي تجربتهم خلال 5 أيام ===
{chr(10).join(f"{c.get('hotel_name',c['name'])} ({c.get('email','')}) — ينتهي: {c.get('trial_end','')}" for c in expiring) or 'لا يوجد'}

=== التذاكر المفتوحة ===
{chr(10).join(f"#{t['id']} | {t.get('client_name','')} | {t.get('title','')} | {t.get('priority','')}" for t in open_tix[:10]) or 'لا يوجد'}

=== الأمر المطلوب ===
{cmd}

=== تعليمات الرد ===
أجب بـ JSON فقط بالشكل التالي:
{{
  "response": "رد واضح للمستخدم بالعربية",
  "actions": [],
  "summary": "ملخص قصير",
  "suggestions": ["اقتراح 1"]
}}"""

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
            cmd_l = cmd.lower()
            if any(w in cmd_l for w in ["ملخص","كيف","وضع","تقرير","إجمالي","كم"]):
                result = {"response": f"ملخص النظام:\n• العملاء: {len(clients)} ({len(active)} نشط، {len(trial)} تجربة)\n• MRR: {mrr} ر.س\n• تذاكر مفتوحة: {len(open_tix)}","actions": [], "summary": "", "suggestions": []}
            else:
                result = {"response": f"أضف Claude API Key في الإعدادات لتنفيذ هذا الأمر.", "actions": [], "summary": "", "suggestions": []}

        analytics.track_action(
            self._cookie_val("client_token") or self._cookie_val("admin_token"),
            "ai_control", cmd[:80]
        )
        self._json({"ok": True, "result": result, "executed": [], "cmd": cmd})

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

    def _p_admin_push(self, b):
        msg  = b.get("message","").strip()
        cids = b.get("client_ids",[])
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
        self._json({"ok":True,"sent_to":len(targets)})

    def _api_payment_plans(self):
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
        tok_c    = self._cookie_val("client_token")
        cid      = cli_ses.get(tok_c)
        plan     = b.get("plan","pro")
        method   = b.get("method","mada")
        period   = b.get("period","monthly")
        s        = adm.get("admin_settings", {})
        prices   = s.get("prices", {"pro":299,"enterprise":799})
        base     = prices.get(plan, 299)
        multiplier = {"monthly":1,"quarterly":3,"semi":6,"annual":12}.get(period,1)
        disc_map   = {"monthly":0,"quarterly":s.get("discount_quarterly",10),"semi":s.get("discount_semi",15),"annual":s.get("discount_annual",20)}
        disc       = disc_map.get(period,0)
        amount     = round(base * multiplier * (1 - disc/100), 2)
        days_map   = {"monthly":30,"quarterly":90,"semi":180,"annual":365}
        days       = days_map.get(period, 30)
        payment_id = f"PAY-{secrets.token_hex(4).upper()}"
        payment_rec = {
            "id": payment_id, "client_id": cid, "plan": plan,
            "method": method, "period": period, "amount": amount,
            "days": days, "status": "pending", "created_at": _iso(),
            "expires_at": key_expiry(1),
        }
        if method != "mada":
            payment_rec["manual"] = True
            payment_rec["bank"] = {
                "name": s.get("owner_account_name",""),
                "bank": s.get("owner_bank",""),
                "iban": s.get("owner_iban",""),
                "amount": amount, "ref": payment_id,
            }
        pending = ClientStore.get(str(cid) if cid else "demo").get_d("pending_payments",[])
        pending.append(payment_rec)
        ClientStore.get(str(cid) if cid else "demo").set_d("pending_payments", pending[-10:])
        self._json({"ok":True, "payment": payment_rec})

    def _p_payment_confirm(self, b):
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
        clients  = adm.get("clients",[])
        client   = next((c for c in clients if str(c.get("id"))==str(cid)),None)
        ticket   = {
            "id": _id(),
            "title": f"تأكيد دفع — {pay_rec.get('plan','')} {pay_rec.get('amount',0)} ر.س",
            "client_id": str(cid),
            "client_name": client.get("hotel_name",client.get("name","")) if client else "—",
            "priority": "high", "status": "open", "category": "billing",
            "created_at": _iso(),
            "messages": [{"from":"client","name":client.get("hotel_name","") if client else "العميل",
                "text": f"أرسلت دفعة {pay_rec['amount']} ر.س للخطة {pay_rec['plan']}. رقم المرجع: {ref or payment_id}.",
                "time": _iso()}],
        }
        adm.append("tickets", ticket)
        pay_rec["status"] = "confirming"
        pay_rec["ref"]    = ref
        cs.set_d("pending_payments", pending)
        self._json({"ok":True, "ticket_id": ticket["id"], "message": "تم إرسال طلب التأكيد — سيتواصل معك الدعم خلال ساعات"})

    def _p_payment_status(self, b):
        tok_c = self._cookie_val("client_token")
        cid   = cli_ses.get(tok_c)
        if not cid: self._json({"ok":False,"error":"غير مسجّل"}); return
        cs      = ClientStore.get(str(cid))
        pending = cs.get_d("pending_payments",[])
        pay_rec = next((p for p in pending if p.get("id")==b.get("payment_id")), None)
        if not pay_rec: self._json({"ok":False,"error":"طلب غير موجود"}); return
        self._json({"ok":True, "payment": pay_rec})

    def _activate_after_payment(self, cid, pay_rec):
        k = {"id": _id(), "key": gen_key(pay_rec.get("plan","pro")),
             "plan": pay_rec.get("plan","pro"), "days": pay_rec.get("days",30),
             "status": "used", "created_at": _iso(),
             "expires_at": key_expiry(pay_rec.get("days",30)),
             "client_id": cid, "notes": f"تلقائي بعد دفع {pay_rec.get('id','')}", "used_at": _iso()}
        adm.append("license_keys", k)
        clients = adm.get("clients",[])
        for c in clients:
            if str(c.get("id"))==str(cid):
                c["license_key"] = k["key"]
                c["plan"]        = k["plan"]
                c["status"]      = "active"
                c["trial_end"]   = k["expires_at"]
        adm.set("clients", clients)

    def _p_update_upload(self, b):
        import base64 as _b64, hashlib as _hs
        file_data   = b.get("file_data","")
        file_name   = b.get("file_name","")
        description = b.get("description","")
        if not file_data or not file_name:
            self._json({"ok":False,"error":"أرفق الملف واسمه"}); return
        try: raw = _b64.b64decode(file_data)
        except Exception as e: self._json({"ok":False,"error":f"خطأ: {e}"}); return
        allowed = {"main.py","main_admin.py","unified_server.py"}
        safe_name = os.path.basename(file_name)
        if safe_name not in allowed:
            self._json({"ok":False,"error":f"الملفات المسموحة: {', '.join(allowed)}"}); return
        try:
            import ast as _ast
            _ast.parse(raw.decode("utf-8"))
        except SyntaxError as e:
            self._json({"ok":False,"error":f"خطأ Python في السطر {e.lineno}: {e.msg}"}); return
        current_dir = os.path.dirname(os.path.abspath(__file__))
        target_path = os.path.join(current_dir, safe_name)
        backup_dir  = os.path.join(HOTEL_DIR, "backups", "updates")
        os.makedirs(backup_dir, exist_ok=True)
        if os.path.exists(target_path):
            import shutil as _sh
            _sh.copy2(target_path, os.path.join(backup_dir, f"{safe_name}.backup_{int(time.time())}"))
        with open(target_path, "wb") as f: f.write(raw)
        chk = _hs.md5(raw).hexdigest()[:8]
        size_kb = round(len(raw)/1024, 1)
        self._json({"ok":True,"file":safe_name,"size_kb":size_kb,"md5":chk,
                    "message":f"تم رفع {safe_name} — أعد التشغيل للتفعيل","restart_needed":True})

    def _p_update_status(self, b):
        self._json({"ok":True,"history":adm.get("update_history",[])[-10:]})

    # ══════════════════════════════════════════════════════════
    #  HTML Pages
    # ══════════════════════════════════════════════════════════
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
    <select id="r-city"><option value="riyadh">الرياض</option><option value="jeddah">جدة</option><option value="makkah">مكة</option><option value="madinah">المدينة</option><option value="dammam">الدمام</option><option value="abha">أبها</option></select>
  </div>
  <div class="fg"><label>نوع المنشأة</label>
    <select id="r-type"><option value="hotel">فندق</option><option value="apart">شقق فندقية</option><option value="service">شقق مخدومة</option></select>
  </div>
  <div class="fg"><label>عدد الغرف / الوحدات</label><input type="number" id="r-rooms" placeholder="50" min="1"/></div>
  <button class="btn btn-s" onclick="register()">ابدأ التجربة المجانية ←</button>
  <div class="err" id="r-err"></div>
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
  else if(d.error==='expired'){alert('انتهت التجربة — تواصل مع الدعم');}
  else showErr('l-err',d.error||'خطأ');
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

    # ════════════════════════════════════════════════════════════
    #  ✅ الإصلاح الرئيسي — لوحة العميل تعمل على أي رابط
    # ════════════════════════════════════════════════════════════
    def _build_client_html(self, client, store):
        name = client["hotel_name"] if client else "النظام التجريبي"
        dl   = days_left(client.get("trial_end")) if client else None

        trial_bar = ""
        if dl is not None:
            color = "#DC2626" if dl <= 3 else "#D97706" if dl <= 7 else "#047857"
            trial_bar = f'<div style="background:{color};color:#fff;text-align:center;padding:8px;font-size:12px">⏳ تجربتك تنتهي خلال {dl} يوم</div>'

        return f"""<!DOCTYPE html>
<html lang="ar" dir="rtl">
<head>
<meta charset="UTF-8"/>
<meta name="viewport" content="width=device-width,initial-scale=1"/>
<title>{name} — نظام إدارة الفندق</title>
<style>
*{{box-sizing:border-box;margin:0;padding:0;font-family:system-ui,Arial,sans-serif;direction:rtl;}}
body{{background:#0F172A;color:#F1F5F9;min-height:100vh;}}
.topbar{{background:#1E293B;border-bottom:1px solid #334155;padding:12px 20px;display:flex;align-items:center;justify-content:space-between;}}
.topbar-title{{font-size:16px;font-weight:700;}}
.badge{{background:#1A56DB;color:#fff;border-radius:20px;padding:3px 10px;font-size:11px;font-weight:600;}}
.main{{padding:20px;max-width:1200px;margin:0 auto;}}
.cards{{display:grid;grid-template-columns:repeat(auto-fit,minmax(200px,1fr));gap:14px;margin-bottom:20px;}}
.card{{background:#1E293B;border-radius:12px;padding:18px;border:1px solid #334155;}}
.card-label{{font-size:11px;color:#64748B;margin-bottom:5px;}}
.card-val{{font-size:26px;font-weight:700;}}
.btn{{padding:8px 14px;border-radius:8px;border:none;font-size:12px;font-weight:600;cursor:pointer;}}
.btn-primary{{background:#1A56DB;color:#fff;}}
.btn-green{{background:#047857;color:#fff;}}
.btn-red{{background:#DC2626;color:#fff;}}
.btn-gray{{background:#334155;color:#CBD5E1;}}
.section{{background:#1E293B;border-radius:12px;padding:18px;margin-bottom:14px;border:1px solid #334155;}}
.section-title{{font-size:14px;font-weight:700;margin-bottom:12px;display:flex;align-items:center;gap:8px;}}
.table{{width:100%;border-collapse:collapse;font-size:12px;}}
.table th{{background:#0F172A;color:#94A3B8;padding:8px 10px;text-align:right;border-bottom:1px solid #334155;}}
.table td{{padding:8px 10px;border-bottom:1px solid #0F172A33;color:#CBD5E1;}}
.badge-a{{background:#065F46;color:#6EE7B7;border-radius:4px;padding:2px 7px;font-size:10px;}}
.badge-c{{background:#1E293B;color:#64748B;border-radius:4px;padding:2px 7px;font-size:10px;border:1px solid #334155;}}
.modal{{display:none;position:fixed;inset:0;background:rgba(0,0,0,.7);z-index:999;align-items:center;justify-content:center;padding:20px;}}
.modal-box{{background:#1E293B;border-radius:16px;padding:24px;width:100%;max-width:460px;max-height:90vh;overflow-y:auto;border:1px solid #334155;}}
.modal-title{{font-size:15px;font-weight:700;margin-bottom:14px;}}
.fg{{margin-bottom:10px;}}
.fg label{{font-size:11px;color:#94A3B8;display:block;margin-bottom:3px;}}
.fg input,.fg select,.fg textarea{{width:100%;background:#0F172A;border:1.5px solid #334155;border-radius:8px;padding:8px 11px;color:#F1F5F9;font-size:12px;font-family:inherit;}}
.fg input:focus,.fg select:focus{{outline:none;border-color:#1A56DB;}}
.nav{{display:flex;gap:4px;flex-wrap:wrap;margin-bottom:18px;}}
.nav-btn{{padding:7px 12px;border-radius:8px;border:none;font-size:11px;cursor:pointer;background:#334155;color:#CBD5E1;}}
.nav-btn.on{{background:#1A56DB;color:#fff;}}
.pg{{display:none;}}.pg.on{{display:block;}}
.kpi-grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(130px,1fr));gap:10px;margin-bottom:14px;}}
.kpi{{background:#0F172A;border-radius:10px;padding:14px;text-align:center;}}
.kpi-v{{font-size:22px;font-weight:700;color:#38BDF8;}}
.kpi-l{{font-size:10px;color:#64748B;margin-top:2px;}}
</style>
</head>
<body>
{trial_bar}
<div class="topbar">
  <div>
    <div class="topbar-title">🏨 {name}</div>
  </div>
  <div style="display:flex;gap:8px;align-items:center">
    <span class="badge" id="status-badge">جارٍ التحميل...</span>
    <button class="btn btn-gray" onclick="location.href='/login'">خروج</button>
  </div>
</div>

<div class="main">
  <div class="nav">
    <button class="nav-btn on" onclick="goPg('guests',this)">🛏 النزلاء</button>
    <button class="nav-btn" onclick="goPg('services',this)">🍽 الخدمات</button>
    <button class="nav-btn" onclick="goPg('pos',this)">🖥 POS</button>
    <button class="nav-btn" onclick="goPg('suppliers',this)">🏭 الموردون</button>
    <button class="nav-btn" onclick="goPg('invoices',this)">📄 الفواتير</button>
    <button class="nav-btn" onclick="goPg('journal',this)">📒 اليومية</button>
    <button class="nav-btn" onclick="goPg('market',this)">📊 السوق</button>
    <button class="nav-btn" onclick="goPg('tickets',this)">🎫 الدعم</button>
    <button class="nav-btn" onclick="goPg('sub',this)">💳 الاشتراك</button>
  </div>

  <div class="pg on" id="pg-guests">
    <div class="kpi-grid" id="kpi-row"></div>
    <div class="section">
      <div class="section-title">🛏 النزلاء
        <button class="btn btn-primary" onclick="openModal('m-guest')" style="margin-right:auto;font-size:11px">+ إضافة نزيل</button>
      </div>
      <table class="table"><thead><tr><th>الاسم</th><th>الوحدة</th><th>الليالي</th><th>المبلغ</th><th>الدخول</th><th>الحالة</th><th></th></tr></thead>
      <tbody id="guests-tbody"></tbody></table>
    </div>
  </div>

  <div class="pg" id="pg-services">
    <div class="section">
      <div class="section-title">🍽 الخدمات
        <button class="btn btn-green" onclick="openModal('m-svc')" style="margin-right:auto;font-size:11px">+ خدمة</button>
      </div>
      <table class="table"><thead><tr><th>النوع</th><th>الوحدة</th><th>المبلغ</th><th>الدفع</th><th>الوقت</th></tr></thead>
      <tbody id="svc-tbody"></tbody></table>
    </div>
  </div>

  <div class="pg" id="pg-pos">
    <div class="section">
      <div class="section-title">🖥 أجهزة POS
        <button class="btn btn-primary" onclick="openModal('m-pos-add')" style="margin-right:auto;font-size:11px">+ جهاز</button>
      </div>
      <div id="pos-grid" style="display:grid;grid-template-columns:repeat(auto-fit,minmax(240px,1fr));gap:12px"></div>
    </div>
  </div>

  <div class="pg" id="pg-suppliers">
    <div class="section">
      <div class="section-title">🏭 الموردون
        <button class="btn btn-primary" onclick="openModal('m-sup')" style="margin-right:auto;font-size:11px">+ مورّد</button>
      </div>
      <table class="table"><thead><tr><th>الاسم</th><th>النوع</th><th>الجوال</th><th>IBAN</th></tr></thead>
      <tbody id="sup-tbody"></tbody></table>
    </div>
  </div>

  <div class="pg" id="pg-invoices">
    <div class="section">
      <div class="section-title">📄 الفواتير
        <button class="btn btn-primary" onclick="openModal('m-inv')" style="margin-right:auto;font-size:11px">+ فاتورة</button>
      </div>
      <table class="table"><thead><tr><th>#</th><th>المورّد</th><th>الإجمالي</th><th>الاستحقاق</th><th>الحالة</th><th></th></tr></thead>
      <tbody id="inv-tbody"></tbody></table>
    </div>
  </div>

  <div class="pg" id="pg-journal">
    <div class="section">
      <div class="section-title">📒 دفتر اليومية</div>
      <table class="table"><thead><tr><th>الوقت</th><th>مدين</th><th>دائن</th><th>المبلغ</th><th>البيان</th></tr></thead>
      <tbody id="jnl-tbody"></tbody></table>
    </div>
  </div>

  <div class="pg" id="pg-market">
    <div class="section">
      <div class="section-title">📊 تحليل السوق</div>
      <div id="market-content" style="color:#94A3B8;text-align:center;padding:20px">جارٍ التحميل...</div>
    </div>
  </div>

  <div class="pg" id="pg-tickets">
    <div class="section">
      <div class="section-title">🎫 تذاكر الدعم
        <button class="btn btn-primary" onclick="openModal('m-ticket')" style="margin-right:auto;font-size:11px">+ تذكرة</button>
      </div>
      <div id="tickets-list" style="color:#94A3B8;padding:20px;text-align:center">جارٍ التحميل...</div>
    </div>
  </div>

  <div class="pg" id="pg-sub">
    <div class="section">
      <div class="section-title">💳 الاشتراك والتجديد</div>
      <div id="sub-content" style="color:#94A3B8;padding:20px;text-align:center">جارٍ التحميل...</div>
    </div>
  </div>
</div>

<!-- MODALS -->
<div class="modal" id="m-guest">
  <div class="modal-box">
    <div class="modal-title">🛏 إضافة نزيل</div>
    <div class="fg"><label>الاسم *</label><input id="g-name" placeholder="محمد العمري"/></div>
    <div class="fg"><label>رقم الهوية</label><input id="g-id" placeholder="1xxxxxxxxx"/></div>
    <div class="fg"><label>الوحدة / الغرفة</label><input id="g-unit" placeholder="101"/></div>
    <div class="fg"><label>نوع السرير</label><select id="g-bed"><option value="double">مزدوج</option><option value="single">مفرد</option><option value="suite">سويت</option></select></div>
    <div class="fg"><label>تاريخ الدخول</label><input type="date" id="g-in"/></div>
    <div class="fg"><label>تاريخ الخروج</label><input type="date" id="g-out"/></div>
    <div class="fg"><label>السعر الليلي (ر.س)</label><input type="number" id="g-price" placeholder="350"/></div>
    <div class="fg"><label>طريقة الدفع</label><select id="g-pay"><option value="mada">مدى</option><option value="visa">فيزا</option><option value="cash">نقد</option><option value="transfer">تحويل</option></select></div>
    <div style="display:flex;gap:8px;margin-top:6px">
      <button class="btn btn-primary" style="flex:1" onclick="addGuest()">حفظ</button>
      <button class="btn btn-gray" onclick="closeModal('m-guest')">إلغاء</button>
    </div>
  </div>
</div>

<div class="modal" id="m-svc">
  <div class="modal-box">
    <div class="modal-title">🍽 خدمة جديدة</div>
    <div class="fg"><label>النوع</label><select id="s-type"><option value="food">طعام</option><option value="laundry">مغسلة</option><option value="transport">نقل</option><option value="other">أخرى</option></select></div>
    <div class="fg"><label>رقم الوحدة</label><input id="s-unit" placeholder="101"/></div>
    <div class="fg"><label>المبلغ (ر.س)</label><input type="number" id="s-amount" placeholder="50"/></div>
    <div class="fg"><label>طريقة الدفع</label><select id="s-pay"><option value="mada">مدى</option><option value="cash">نقد</option></select></div>
    <div style="display:flex;gap:8px;margin-top:6px">
      <button class="btn btn-green" style="flex:1" onclick="addSvc()">حفظ</button>
      <button class="btn btn-gray" onclick="closeModal('m-svc')">إلغاء</button>
    </div>
  </div>
</div>

<div class="modal" id="m-sup">
  <div class="modal-box">
    <div class="modal-title">🏭 مورّد جديد</div>
    <div class="fg"><label>الاسم *</label><input id="sup-name" placeholder="شركة الخدمات"/></div>
    <div class="fg"><label>النوع</label><select id="sup-type"><option value="food">مواد غذائية</option><option value="cleaning">نظافة</option><option value="maintenance">صيانة</option><option value="other">أخرى</option></select></div>
    <div class="fg"><label>الجوال</label><input id="sup-phone" placeholder="05xxxxxxxx"/></div>
    <div class="fg"><label>IBAN</label><input id="sup-iban" placeholder="SA00..."/></div>
    <div style="display:flex;gap:8px;margin-top:6px">
      <button class="btn btn-primary" style="flex:1" onclick="addSup()">حفظ</button>
      <button class="btn btn-gray" onclick="closeModal('m-sup')">إلغاء</button>
    </div>
  </div>
</div>

<div class="modal" id="m-inv">
  <div class="modal-box">
    <div class="modal-title">📄 فاتورة جديدة</div>
    <div class="fg"><label>المورّد</label><select id="inv-sup-id"></select></div>
    <div class="fg"><label>رقم الفاتورة</label><input id="inv-num" placeholder="INV-001"/></div>
    <div class="fg"><label>المبلغ الأساسي (ر.س)</label><input type="number" id="inv-base" placeholder="1000"/></div>
    <div class="fg"><label>تاريخ الاستحقاق</label><input type="date" id="inv-due"/></div>
    <div style="display:flex;gap:8px;margin-top:6px">
      <button class="btn btn-primary" style="flex:1" onclick="addInv()">حفظ</button>
      <button class="btn btn-gray" onclick="closeModal('m-inv')">إلغاء</button>
    </div>
  </div>
</div>

<div class="modal" id="m-ticket">
  <div class="modal-box">
    <div class="modal-title">🎫 تذكرة دعم</div>
    <div class="fg"><label>العنوان *</label><input id="tik-title" placeholder="وصف المشكلة"/></div>
    <div class="fg"><label>التفاصيل</label><textarea id="tik-msg" rows="3" placeholder="اشرح المشكلة..."></textarea></div>
    <div class="fg"><label>الأولوية</label><select id="tik-pri"><option value="normal">عادية</option><option value="high">عاجلة</option></select></div>
    <div style="display:flex;gap:8px;margin-top:6px">
      <button class="btn btn-primary" style="flex:1" onclick="addTicket()">إرسال</button>
      <button class="btn btn-gray" onclick="closeModal('m-ticket')">إلغاء</button>
    </div>
  </div>
</div>

<div class="modal" id="m-pos-add">
  <div class="modal-box">
    <div class="modal-title">🖥 جهاز POS جديد</div>
    <div class="fg"><label>اسم الجهاز</label><input id="pos-name" placeholder="جهاز المطعم"/></div>
    <div class="fg"><label>القسم</label><select id="pos-dept"><option value="restaurant">مطعم</option><option value="cafe">كافيه</option><option value="reception">استقبال</option><option value="other">أخرى</option></select></div>
    <div style="display:flex;gap:8px;margin-top:6px">
      <button class="btn btn-primary" style="flex:1" onclick="addPosDevice()">إضافة</button>
      <button class="btn btn-gray" onclick="closeModal('m-pos-add')">إلغاء</button>
    </div>
  </div>
</div>

<script>
let store = {{}};
const $ = id => document.getElementById(id);
function openModal(id) {{ document.getElementById(id).style.display = 'flex'; }}
function closeModal(id) {{ document.getElementById(id).style.display = 'none'; }}
async function api(url, body) {{
  const r = await fetch(url, {{method: body ? 'POST' : 'GET',
    headers: {{'Content-Type': 'application/json'}},
    body: body ? JSON.stringify(body) : undefined}});
  return r.json();
}}

function goPg(name, btn) {{
  document.querySelectorAll('.pg').forEach(p => p.classList.remove('on'));
  document.querySelectorAll('.nav-btn').forEach(b => b.classList.remove('on'));
  document.getElementById('pg-' + name)?.classList.add('on');
  if (btn) btn.classList.add('on');
  if (name === 'market') loadMarket();
  if (name === 'tickets') loadTickets();
  if (name === 'sub') loadSub();
}}

async function boot() {{
  const d = await api('/api/store');
  store = d;
  renderGuests(d.guests || []);
  renderServices(d.services || []);
  renderPos(d.pos_devices || []);
  renderSup(d.suppliers || []);
  renderInv(d.invoices || []);
  renderJournal(d.journal_entries || []);
  renderKpi(d.guests || []);
  renderSupSelect(d.suppliers || []);
  loadSubBadge();
}}

function renderKpi(guests) {{
  const active = guests.filter(g => g.status === 'active');
  const rev = guests.reduce((s, g) => s + (g.total || 0), 0);
  const rooms = (store.settings || {{}}).rooms || 50;
  $('kpi-row').innerHTML = [
    ['النزلاء النشطون', active.length],
    ['الإيرادات', rev.toFixed(0) + ' ر.س'],
    ['الإشغال', Math.round(active.length / rooms * 100) + '%'],
    ['إجمالي الليالي', guests.reduce((s,g) => s + (g.nights||0), 0)],
  ].map(([l,v]) => `<div class="kpi"><div class="kpi-v">${{v}}</div><div class="kpi-l">${{l}}</div></div>`).join('');
}}

function renderGuests(gs) {{
  $('guests-tbody').innerHTML = gs.length ? gs.slice().reverse().map(g => `<tr>
    <td>${{g.name}}</td><td>${{g.unit||'—'}}</td><td>${{g.nights}}</td>
    <td style="font-weight:700">${{g.total}} ر.س</td><td>${{g.inDate||'—'}}</td>
    <td><span class="${{g.status==='active'?'badge-a':'badge-c'}}">${{g.status==='active'?'نشط':'خروج'}}</span></td>
    <td>${{g.status==='active'?`<button class="btn btn-red" style="font-size:10px;padding:4px 8px" onclick="checkout(${{g.id}})">خروج</button>`:''}}</td>
  </tr>`).join('') : '<tr><td colspan="7" style="text-align:center;color:#64748B;padding:20px">لا يوجد نزلاء</td></tr>';
}}

function renderServices(ss) {{
  $('svc-tbody').innerHTML = ss.length ? ss.slice().reverse().map(s => `<tr>
    <td>${{s.type}}</td><td>${{s.unit}}</td><td>${{s.amount}} ر.س</td><td>${{s.pay}}</td><td>${{s.time}}</td>
  </tr>`).join('') : '<tr><td colspan="5" style="text-align:center;color:#64748B;padding:20px">لا يوجد</td></tr>';
}}

function renderPos(devs) {{
  $('pos-grid').innerHTML = devs.map(d => `<div style="background:#0F172A;border-radius:10px;padding:14px;border:2px solid ${{d.color||'#334155'}}">
    <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:10px">
      <div style="font-weight:700;color:#F1F5F9">${{d.name}}</div>
      <span style="font-size:10px;background:#334155;color:#94A3B8;border-radius:4px;padding:2px 6px">${{d.dept}}</span>
    </div>
    ${{d.data ? `<div style="font-size:20px;font-weight:700;color:${{d.color||'#38BDF8'}}">${{d.data.sales}} ر.س</div>
      <div style="font-size:10px;color:#64748B;margin-bottom:8px">${{d.data.txCount||0}} فاتورة</div>
      <button class="btn btn-gray" style="width:100%;font-size:11px" onclick="clearPos(${{d.id}})">مسح</button>`
    : `<button class="btn btn-primary" style="width:100%;font-size:11px" onclick="posEntry(${{d.id}})">إدخال مبيعات</button>`}}
  </div>`).join('') || '<div style="color:#64748B;text-align:center;padding:20px">لا يوجد أجهزة — أضف جهازاً</div>';
}}

function renderSup(ss) {{
  $('sup-tbody').innerHTML = ss.length ? ss.map(s => `<tr>
    <td>${{s.name}}</td><td>${{s.type}}</td><td>${{s.phone||'—'}}</td><td style="font-size:10px">${{s.iban||'—'}}</td>
  </tr>`).join('') : '<tr><td colspan="4" style="text-align:center;color:#64748B;padding:20px">لا يوجد</td></tr>';
}}

function renderInv(invs) {{
  $('inv-tbody').innerHTML = invs.length ? invs.slice().reverse().map(i => `<tr>
    <td style="font-size:10px">${{i.num}}</td><td>${{i.supName}}</td>
    <td style="font-weight:700">${{i.total}} ر.س</td><td>${{i.due}}</td>
    <td><span class="${{i.status==='paid'?'badge-a':'badge-c'}}">${{i.status==='paid'?'مدفوع':'معلق'}}</span></td>
    <td>${{i.status!=='paid'?`<button class="btn btn-green" style="font-size:10px;padding:3px 8px" onclick="payInv(${{i.id}})">دفع</button>`:''}}</td>
  </tr>`).join('') : '<tr><td colspan="6" style="text-align:center;color:#64748B;padding:20px">لا يوجد</td></tr>';
}}

function renderJournal(js) {{
  $('jnl-tbody').innerHTML = js.length ? js.slice().reverse().map(j => `<tr>
    <td>${{j.time}}</td><td>${{j.drAcc}}</td><td>${{j.crAcc}}</td>
    <td style="font-weight:700">${{j.amount}} ر.س</td><td>${{j.desc}}</td>
  </tr>`).join('') : '<tr><td colspan="5" style="text-align:center;color:#64748B;padding:20px">لا يوجد قيود</td></tr>';
}}

function renderSupSelect(sups) {{
  const sel = $('inv-sup-id');
  if (sel) sel.innerHTML = sups.map(s => `<option value="${{s.id}}">${{s.name}}</option>`).join('');
}}

async function addGuest() {{
  const inD = $('g-in').value, outD = $('g-out').value;
  const nights = inD && outD ? Math.max(1, Math.round((new Date(outD)-new Date(inD))/86400000)) : 1;
  const d = await api('/api/guests/add', {{
    name:$('g-name').value, idNum:$('g-id').value, unit:$('g-unit').value,
    bed:$('g-bed').value, inDate:inD, outDate:outD, nights,
    price:$('g-price').value, pay:$('g-pay').value,
  }});
  if (d.ok) {{ closeModal('m-guest'); boot(); }}
  else alert(d.error||'خطأ');
}}

async function checkout(id) {{
  if (!confirm('تأكيد خروج النزيل؟')) return;
  await api('/api/guests/checkout', {{id}}); boot();
}}

async function addSvc() {{
  const d = await api('/api/services/add', {{type:$('s-type').value,unit:$('s-unit').value,amount:$('s-amount').value,pay:$('s-pay').value}});
  if (d.ok) {{ closeModal('m-svc'); boot(); }}
}}

async function addSup() {{
  const d = await api('/api/suppliers/add', {{name:$('sup-name').value,type:$('sup-type').value,phone:$('sup-phone').value,iban:$('sup-iban').value}});
  if (d.ok) {{ closeModal('m-sup'); boot(); }}
}}

async function addInv() {{
  const supId = $('inv-sup-id').value;
  const sup = (store.suppliers||[]).find(s=>String(s.id)===String(supId));
  const d = await api('/api/invoices/add', {{supId,supName:sup?.name||'',num:$('inv-num').value,base:$('inv-base').value,due:$('inv-due').value,vat:true}});
  if (d.ok) {{ closeModal('m-inv'); boot(); }}
}}

async function payInv(id) {{
  if (!confirm('تأكيد دفع الفاتورة؟')) return;
  await api('/api/invoices/pay', {{id}}); boot();
}}

async function addPosDevice() {{
  const d = await api('/api/pos/device/add', {{name:$('pos-name').value,dept:$('pos-dept').value}});
  if (d.ok) {{ closeModal('m-pos-add'); boot(); }}
}}

function posEntry(devId) {{
  const sales = prompt('المبيعات الإجمالية (ر.س):');
  if (!sales) return;
  const txCount = prompt('عدد الفواتير:') || '0';
  api('/api/pos/data/save', {{id:devId,sales:parseFloat(sales),txCount:parseInt(txCount),refund:0,vat:0}}).then(()=>boot());
}}

async function clearPos(id) {{
  if (!confirm('مسح بيانات الجهاز؟')) return;
  await api('/api/pos/data/clear', {{id}}); boot();
}}

async function addTicket() {{
  const d = await api('/api/tickets/open', {{title:$('tik-title').value,message:$('tik-msg').value,priority:$('tik-pri').value}});
  if (d.ok) {{ closeModal('m-ticket'); alert('✅ تم إرسال التذكرة'); loadTickets(); }}
}}

async function loadMarket() {{
  const d = await api('/api/market');
  $('market-content').innerHTML = `
    <div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(160px,1fr));gap:12px;margin-bottom:12px">
      ${{[['ADR السوق',d.market_adr+' ر.س'],['ADRنا',d.our_adr+' ر.س'],
         ['إشغال السوق',d.market_occ+'%'],['إشغالنا',d.our_occ+'%'],
         ['RevPAR السوق',d.market_revpar+' ر.س'],['RevPARنا',d.our_revpar+' ر.س']
        ].map(([l,v])=>`<div class="kpi"><div class="kpi-v">${{v}}</div><div class="kpi-l">${{l}}</div></div>`).join('')}}
    </div>
    <div style="font-size:12px;color:${{d.adr_diff>=0?'#10B981':'#EF4444'}}">
      الفرق في ADR: ${{d.adr_diff>=0?'▲':'▼'}} ${{Math.abs(d.adr_diff)}} ر.س عن متوسط السوق
    </div>`;
}}

async function loadTickets() {{
  const d = await api('/api/tickets');
  const tix = d.tickets || [];
  $('tickets-list').innerHTML = tix.length ? tix.slice().reverse().map(t => `
    <div style="background:#0F172A;border-radius:9px;padding:14px;margin-bottom:10px;border:1px solid #334155">
      <div style="display:flex;justify-content:space-between;margin-bottom:8px">
        <div style="font-weight:700;font-size:13px">${{t.title}}</div>
        <span style="font-size:10px;background:#334155;border-radius:4px;padding:2px 6px;color:#94A3B8">${{t.status}}</span>
      </div>
      ${{(t.messages||[]).map(m=>`<div style="background:#1E293B;border-radius:7px;padding:8px 10px;margin-bottom:4px;font-size:11px">
        <span style="color:${{m.from==='admin'?'#38BDF8':'#94A3B8'}};font-weight:600">${{m.name}}: </span>
        <span style="color:#CBD5E1">${{m.text}}</span>
      </div>`).join('')}}
    </div>`).join('') : '<div style="color:#64748B;text-align:center;padding:30px">لا يوجد تذاكر</div>';
}}

async function loadSub() {{
  const d = await api('/api/subscription');
  let html = `<div style="font-size:16px;font-weight:700;margin-bottom:8px">الخطة: ${{d.plan}}</div>
    <div style="font-size:12px;color:#94A3B8;margin-bottom:10px">الحالة: ${{d.status}}</div>`;
  if (d.days_left !== null) {{
    const c = d.days_left <= 3 ? '#DC2626' : d.days_left <= 7 ? '#D97706' : '#047857';
    html += `<div style="font-size:13px;color:${{c}};font-weight:700;margin-bottom:12px">⏳ ${{d.days_left}} يوم متبقي — تنتهي ${{d.trial_end}}</div>`;
  }}
  html += `<div class="fg"><label>مفتاح التفعيل</label>
    <div style="display:flex;gap:8px">
      <input id="act-key" placeholder="HOTEL-XXXX-XXXX-XXXX" style="flex:1;background:#0F172A;border:1.5px solid #334155;border-radius:8px;padding:8px 11px;color:#F1F5F9;font-size:12px"/>
      <button class="btn btn-primary" onclick="activateKey()">تفعيل</button>
    </div>
    <div id="act-msg" style="margin-top:6px;font-size:11px;display:none"></div>
  </div>`;
  $('sub-content').innerHTML = html;
}}

async function activateKey() {{
  const key = $('act-key')?.value?.trim().toUpperCase();
  if (!key) return;
  const d = await api('/api/client/activate', {{key}});
  const msg = $('act-msg');
  msg.style.display = 'block';
  msg.style.color = d.ok ? '#10B981' : '#EF4444';
  msg.textContent = d.ok ? `✅ تم التفعيل — خطة ${{d.plan}} حتى ${{d.expires}}` : (d.error||'خطأ');
  if (d.ok) setTimeout(() => location.reload(), 2000);
}}

async function loadSubBadge() {{
  const d = await api('/api/subscription');
  const badge = $('status-badge');
  if (!badge) return;
  if (d.status === 'active') {{ badge.textContent = '✓ نشط'; badge.style.background = '#047857'; }}
  else if (d.days_left !== null) {{
    badge.textContent = `⏳ ${{d.days_left}} يوم`;
    badge.style.background = d.days_left <= 3 ? '#DC2626' : '#D97706';
  }} else {{ badge.textContent = 'تجريبي'; }}
}}

document.addEventListener('click', e => {{ if (e.target.classList.contains('modal')) closeModal(e.target.id); }});
boot();
</script>
</body>
</html>"""


# ══════════════════════════════════════════════════════════════
#  ADMIN HANDLER — Port 5051
# ══════════════════════════════════════════════════════════════
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
            self._html("""<!DOCTYPE html><html lang="ar" dir="rtl"><head><meta charset="UTF-8"/>
<title>لوحة المالك</title></head><body style="font-family:system-ui;background:#0F172A;color:#F1F5F9;display:flex;align-items:center;justify-content:center;min-height:100vh;text-align:center">
<div><div style="font-size:48px;margin-bottom:16px">⚠️</div>
<div style="font-size:20px;font-weight:700;margin-bottom:8px">لوحة المالك غير متاحة</div>
<div style="color:#64748B;font-size:14px">ضع ملف main_admin.py في نفس المجلد وأعد تشغيل الخادم</div></div>
</body></html>""")
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

if __name__ == "__main__":
    print("="*58)
    print("  نظام إدارة الفنادق — Unified SaaS Server v4.1")
    print("="*58)
    print(f"  لوحة العميل : http://localhost:{CLIENT_PORT}")
    print(f"  لوحة المالك : http://localhost:{ADMIN_PORT}/admin")
    print(f"  كلمة مرور Admin: {ADMIN_PASS}")
    print("="*58)
    t1 = threading.Thread(target=run_client, daemon=True)
    t2 = threading.Thread(target=run_admin,  daemon=True)
    t1.start(); t2.start()
    try:
        while True: time.sleep(60)
    except KeyboardInterrupt:
        print("\n  تم الإيقاف.")
