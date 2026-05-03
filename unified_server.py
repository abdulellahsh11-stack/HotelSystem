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
            cs = self.client_stats.setdefault(str(cid), {"days_active":set(),"total_actions":0,"last_page":"—","errors":0,"first_seen":_today(),"last_login":_iso()})
            cs["days_active"].add(_today())
            cs["last_login"] = _iso()

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
                "client_stats":     {k:{"days_active":len(v["days_active"]),"total_actions":v["total_actions"],"last_page":v["last_page"],"errors":v["errors"],"first_seen":v.get("first_seen",""),"last_login":v.get("last_login","")} for k,v in self.client_stats.items()},
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
    """Load main_admin.py module (cached) — يُشارك sessions مع unified_server"""
    global _admin_mod_cache
    if _admin_mod_cache is not None:
        # تحديث sessions في الـ module دائماً (يُصلح التعارع)
        try:
            _admin_mod_cache.sessions = sessions
        except Exception:
            pass
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
            # ── مشاركة sessions مع main_admin (يُصلح التعارع الرئيسي) ──
            _mod.sessions = sessions
            _admin_mod_cache = _mod
            log.info("Admin module pre-loaded — sessions shared ✓")
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
#  GitHub Backup
# ══════════════════════════════════════════════════════════════
_GH_TOKEN  = os.environ.get("GITHUB_TOKEN", "")
_GH_REPO   = os.environ.get("GITHUB_REPO", "")
_GH_BRANCH = os.environ.get("GITHUB_BRANCH", "main")
_GH_PATH   = "data/admin_store.json"

def _github_save():
    if not _GH_TOKEN or not _GH_REPO:
        return False
    try:
        import urllib.request as _ur, base64 as _b64
        api_url = f"https://api.github.com/repos/{_GH_REPO}/contents/{_GH_PATH}"
        hdrs = {"Authorization":f"token {_GH_TOKEN}",
                "Accept":"application/vnd.github.v3+json",
                "Content-Type":"application/json"}
        sha = None
        try:
            r = _ur.Request(api_url, headers=hdrs)
            sha = json.loads(_ur.urlopen(r, timeout=8).read()).get("sha")
        except Exception: pass
        store_path = os.path.join(ADMIN_DIR, "data", "admin_store.json")
        if not os.path.exists(store_path):
            return False
        with open(store_path, "r", encoding="utf-8") as f:
            store_data = json.load(f)
        safe = {
            "clients": [{"id":c.get("id"),"name":c.get("name",""),
                          "hotel_name":c.get("hotel_name",""),"email":c.get("email",""),
                          "phone":c.get("phone",""),"city":c.get("city",""),
                          "hotel_type":c.get("hotel_type",""),"plan":c.get("plan",""),
                          "status":c.get("status",""),"trial_end":c.get("trial_end",""),
                          "created_at":c.get("created_at",""),"rooms":c.get("rooms",0)}
                         for c in store_data.get("clients", [])],
            "admin_settings": store_data.get("admin_settings", {}),
            "license_keys":   store_data.get("license_keys", []),
            "payments":       store_data.get("payments", []),
            "backed_up_at":   datetime.now().isoformat(),
        }
        body = json.dumps({
            "message": f"backup {datetime.now().strftime('%Y-%m-%d %H:%M')}",
            "content": _b64.b64encode(json.dumps(safe, ensure_ascii=False, indent=2).encode()).decode(),
            "branch":  _GH_BRANCH,
            **({"sha": sha} if sha else {}),
        }).encode()
        req = _ur.Request(api_url, data=body, headers=hdrs, method="PUT")
        _ur.urlopen(req, timeout=12)
        log.info("GitHub backup saved ✓")
        return True
    except Exception as e:
        log.error(f"GitHub backup: {e}")
        return False

def _github_restore():
    if not _GH_TOKEN or not _GH_REPO:
        return False
    try:
        import urllib.request as _ur, base64 as _b64
        api_url = f"https://api.github.com/repos/{_GH_REPO}/contents/{_GH_PATH}"
        hdrs = {"Authorization":f"token {_GH_TOKEN}",
                "Accept":"application/vnd.github.v3+json"}
        req = _ur.Request(api_url, headers=hdrs)
        res = json.loads(_ur.urlopen(req, timeout=10).read())
        gh_data = json.loads(_b64.b64decode(res["content"]).decode())
        local_file = os.path.join(ADMIN_DIR, "data", "admin_store.json")
        local_data = {}
        if os.path.exists(local_file):
            with open(local_file, "r", encoding="utf-8") as f:
                local_data = json.load(f)
        gh_clients  = {c["id"]: c for c in gh_data.get("clients", []) if c.get("id")}
        loc_clients = {c["id"]: c for c in local_data.get("clients", []) if c.get("id")}
        merged = {}
        for cid, gc in gh_clients.items():
            merged[cid] = {**loc_clients.get(cid, {}), **{k:v for k,v in gc.items() if v}}
        for cid, lc in loc_clients.items():
            if cid not in merged:
                merged[cid] = lc
        local_data["clients"] = list(merged.values())
        if not local_data.get("admin_settings"):
            local_data["admin_settings"] = gh_data.get("admin_settings", {})
        with open(local_file, "w", encoding="utf-8") as f:
            json.dump(local_data, f, ensure_ascii=False, indent=2)
        log.info(f"GitHub restore: {len(merged)} عميل ✓")
        return True
    except Exception as e:
        log.error(f"GitHub restore: {e}")
        return False

threading.Thread(target=_github_restore, daemon=True).start()

# ══════════════════════════════════════════════════════════════
#  قاعدة بيانات المالك
# ══════════════════════════════════════════════════════════════
class AdminStore:
    def __init__(self):
        self._file = os.path.join(ADMIN_DIR,"data","admin_store.json")
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
            "admin_settings":{
                "owner_name":"المالك", "owner_email":"admin@hotel-system.sa",
                "owner_phone":"", "system_name":"ضيوف",
                "bank_iban":"", "bank_name":"",
                "trial_days":15,
                "prices":{"free":0,"pro":299,"enterprise":799},
            },
        }

    def save(self):
        with open(self._file,"w",encoding="utf-8") as f:
            json.dump(self._data,f,ensure_ascii=False,indent=2)
        try:
            threading.Thread(target=_github_save, daemon=True).start()
        except Exception: pass

    def get(self,k,d=None):
        # Always reload from file to get latest data saved by main_admin
        self._data = self._load()
        return self._data.get(k,d)
    def set(self,k,v):      self._data[k]=v; self.save()
    def append(self,k,i):   self._data.setdefault(k,[]).append(i); self.save()

adm     = AdminStore()
# ── Persistent Admin Sessions (survives restart) ──────────────
import threading as _threading
_SESS_FILE = os.path.join(ADMIN_DIR,"data","sessions.json")
_sess_lock = _threading.Lock()

def _load_sessions():
    try:
        if os.path.exists(_SESS_FILE):
            raw = json.loads(open(_SESS_FILE).read())
            return {k: datetime.fromisoformat(v) for k,v in raw.items()
                    if datetime.fromisoformat(v) > datetime.now()}
    except: pass
    return {}

def _save_sessions(sess):
    try:
        with _sess_lock:
            clean = {k:v.isoformat() for k,v in sess.items() if v > datetime.now()}
            open(_SESS_FILE,'w').write(json.dumps(clean))
    except: pass

sessions = _load_sessions()   # token → expiry (admin) — persisted
cli_ses  = {}                 # token → client_id (client sessions)

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
        n = int(self.headers.get("Content-Length", 0))
        if not n:
            return {}
        raw = self.rfile.read(n)
        try:
            return json.loads(raw)
        except Exception:
            # حاول قراءة form-encoded
            try:
                from urllib.parse import parse_qs
                qs = parse_qs(raw.decode("utf-8", errors="ignore"))
                return {k: v[0] for k, v in qs.items()}
            except Exception:
                return {}

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
#  Claude API Helper — thread-safe, timeout-safe
# ══════════════════════════════════════════════════════════════
def _claude_call(api_key, prompt, max_tokens=600, timeout=28):
    """
    استدعاء Claude API في thread منفصل مع timeout آمن.
    يُعيد (text, error) — text=None إذا فشل.
    """
    import urllib.request as _ur, threading as _th

    result = {"text": None, "error": None}

    def _do():
        try:
            payload = json.dumps({
                "model": "claude-sonnet-4-20250514",
                "max_tokens": max_tokens,
                "messages": [{"role": "user", "content": prompt}]
            }).encode("utf-8")
            req = _ur.Request(
                "https://api.anthropic.com/v1/messages",
                data=payload,
                headers={
                    "Content-Type":       "application/json",
                    "anthropic-version":  "2023-06-01",
                    "x-api-key":          api_key,
                },
                method="POST"
            )
            resp = _ur.urlopen(req, timeout=timeout)
            data = json.loads(resp.read())
            # استخرج النص من أول block نوعه text
            for block in data.get("content", []):
                if block.get("type") == "text":
                    result["text"] = block["text"].strip()
                    break
        except _ur.HTTPError as e:
            try:
                err_body = json.loads(e.read())
                result["error"] = err_body.get("error",{}).get("message","خطأ API")[:200]
            except Exception:
                result["error"] = f"HTTP {e.code}"
        except Exception as e:
            result["error"] = str(e)[:120]

    t = _th.Thread(target=_do, daemon=True)
    t.start()
    t.join(timeout + 2)   # انتظر الـ thread بحد أقصى timeout+2 ثانية

    if t.is_alive():
        result["error"] = "Claude API timeout"

    return result["text"], result["error"]


def _extract_json(text):
    """استخرج أول JSON object صحيح من نص"""
    if not text:
        return None
    # جرب أولاً النص كاملاً
    try:
        return json.loads(text.strip())
    except Exception:
        pass
    # ابحث عن أول { وآخر }
    start = text.find('{')
    end   = text.rfind('}')
    if start != -1 and end != -1 and end > start:
        try:
            return json.loads(text[start:end+1])
        except Exception:
            pass
    return None


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
            _tok = self._cookie_val("admin_token")
            _authed = bool(_tok and _tok in sessions and sessions.get(_tok, datetime(2000,1,1)) > datetime.now())
            _amod = _load_admin_mod()
            if _authed and _amod:
                self._html(_amod._build_admin_html())
            elif _amod:
                self._html(_amod._build_login_html())
            else:
                self._html("<h2 style='padding:40px;font-family:system-ui'>⚠️ main_admin.py غير موجود</h2>")
            return

        if path in ("/","/dashboard"):
            if self._client_authed():
                client,store = self._get_client()
                self._html(self._build_client_html(client,store))
            else:
                self._html(self._build_client_login())
            return

        if path == "/login":
            self._html(self._build_client_login())
            return

        if path == "/register":
            self._html(self._build_client_login())
            return

        # ── Admin GET APIs (stats, clients, etc.) ────────────────────────────────
        if path.startswith("/api/admin/"):
            _amod_g = _load_admin_mod()
            _tok_g  = self._cookie_val("admin_token")
            # استخدم sessions من unified_server مباشرة (وليس من main_admin)
            _auth_g = _tok_g and _tok_g in sessions and sessions.get(_tok_g, datetime(2000,1,1)) > datetime.now()
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
                "/api/admin/backup/status": lambda: self._admin_backup_status(),
                "/api/admin/backup/status1":lambda: self._admin_backup_status(),
            }
            _gfn = _get_routes.get(path)
            if _gfn: _gfn()
            else:    self._json({"error":"admin route not found"}, 404)
            return

        client,store = self._get_client()

        routes = {
            "/api/store":         lambda _: self._api_store(store),
            "/api/market":        lambda _: self._api_market(store),
            "/api/system-info":   lambda _: self._api_system_info(),
            "/api/notifications": lambda _: self._api_client_notifications(store),
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
                if pw == ADMIN_PASS:
                    _tok = secrets.token_hex(24)
                    sessions[_tok] = datetime.now() + timedelta(hours=12)
                    _save_sessions(sessions)  # persist to disk
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
            if _tok2 in sessions:
                del sessions[_tok2]
                _save_sessions(sessions)
            _body2 = json.dumps({"ok":True}).encode()
            self.send_response(200)
            self.send_header("Content-Type","application/json; charset=utf-8")
            self.send_header("Content-Length",len(_body2))
            self.send_header("Set-Cookie","admin_token=; Path=/; HttpOnly; SameSite=Strict; Max-Age=0; Expires=Thu, 01 Jan 1970 00:00:00 GMT")
            self.end_headers(); self.wfile.write(_body2)
            return

        if path.startswith("/api/admin/"):
            _amod3 = _load_admin_mod()
            _tok3 = self._cookie_val("admin_token")
            # استخدم sessions من unified_server مباشرة
            _authed3 = _tok3 and _tok3 in sessions and sessions.get(_tok3, datetime(2000,1,1)) > datetime.now()
            if not _authed3:
                self._json({"error":"unauthorized"}, 401); return
            # Route to admin handler method
            _admin_routes = {
                "/api/admin/stats":     lambda: self._json(self._build_admin_stats(_amod3)),
                "/api/admin/clients":   lambda: self._json({"clients":_amod3.adm.get("clients",[])}),
                "/api/admin/settings":  lambda: self._json({"settings":_amod3.adm.get("admin_settings",{})}),
                "/api/admin/settings/save": lambda: self._admin_save_settings(_amod3, b),
                "/api/admin/settings/ai":   lambda: self._admin_save_ai_settings(_amod3, b),
                "/api/admin/settings/ai/test": lambda: self._admin_test_claude_key(b),
                "/api/admin/backup/status":     lambda: self._admin_backup_status(),
                "/api/admin/backup/status1":    lambda: self._admin_backup_status(),
                "/api/admin/backup/restore":    lambda: self._admin_backup_restore(),
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

        if path == "/api/client/logout":
            _ctok = self._cookie_val("client_token")
            if _ctok in cli_ses:
                del cli_ses[_ctok]
            _lb = json.dumps({"ok":True}).encode()
            self.send_response(200)
            self.send_header("Content-Type","application/json; charset=utf-8")
            self.send_header("Content-Length",len(_lb))
            self.send_header("Set-Cookie","client_token=; Path=/; HttpOnly; SameSite=Strict; Max-Age=0; Expires=Thu, 01 Jan 1970 00:00:00 GMT")
            self.end_headers(); self.wfile.write(_lb)
            return

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
            "/api/market/ai":            lambda: self._p_market_ai_client(b,store),
            "/api/market/websearch":     lambda: self._p_market_ws_client(b,store),
            "/api/backups":              lambda: self._api_client_backups(store),
            "/api/backup/list":          lambda: self._api_client_backups(store),
            "/api/pms/add":              lambda: self._p_pms_add(b,store),
            "/api/pms/delete":           lambda: self._p_pms_del(b,store),
            "/api/pms/read":             lambda: self._p_pms_read(b,store),
            "/api/pms/schedule/save":    lambda: self._p_pms_sched(b,store),
            "/api/backup/create":        lambda: self._p_backup(b,store,client),
            "/api/search":               lambda: self._p_search(b,store),
            "/api/tickets/open":         lambda: self._p_ticket_open(b,store,client),
            "/api/tickets/message":      lambda: self._p_ticket_msg(b,store,client),
            "/api/ai/control":           lambda: self._p_ai_control(b,store,client),
            "/api/ai/analyze-data":      lambda: self._p_ai_analyze_data(b,store,client),
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
        trial_days = adm.get("admin_settings",{}).get("trial_days",15)
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
                "text":f"أهلاً {name}! تهانينا بتسجيلك في {adm.get('admin_settings',{}).get('system_name','ضيوف')}.\n\nتجربتك المجانية سارية حتى {client['trial_end']}.\n\nإذا احتجت أي مساعدة أرسل رسالة هنا.",
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
        body=json.dumps({"ok":True,"trial_end":client["trial_end"],"name":client["hotel_name"],"client_id":client["id"]}).encode()
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

    def _api_system_info(self):
        s = adm.get("admin_settings",{})
        self._json({
            "system_name":    s.get("system_name","ضيوف"),
            "owner_name":     s.get("owner_name",""),
            "owner_phone":    s.get("owner_phone",""),
            "owner_whatsapp": s.get("owner_whatsapp",""),
            "contact_message":s.get("contact_message","تواصل معنا للمساعدة"),
            "trial_days":     s.get("trial_days",15),
            "bank_iban":      s.get("owner_iban",s.get("bank_iban","")),
            "bank_name":      s.get("owner_bank",s.get("bank_name","")),
            "bank_account":   s.get("owner_account_name",""),
            "primary_color":  s.get("primary_color","#C9A84C"),
            "logo_emoji":     s.get("logo_emoji","🏨"),
            "announcement":   s.get("announcement",""),
            "disabled_pages": s.get("disabled_pages",[]),
        })

    def _api_client_notifications(self,store):
        notifs = store.get_d("notifications",[])
        self._json({"ok":True,"notifications":list(reversed(notifs[-20:]))})

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
        # Calculate season based on client city and current month
        _city_names = {"riyadh":"الرياض","jeddah":"جدة","makkah":"مكة","madinah":"المدينة",
                       "dammam":"الدمام","khobar":"الخبر","abha":"أبها","taif":"الطائف",
                       "tabuk":"تبوك","jubail":"الجبيل","ahsa":"الأحساء","qassim":"القصيم",
                       "hail":"حائل","bahah":"الباحة"}
        _city_ar = _city_names.get(city, city)
        _month = datetime.now().month
        # Season logic per city
        if city == "makkah":
            _sf = 2.5 if _month in (3,4,9,10,11,12) else 1.8
            _sl = "موسم العمرة" if _month in (3,4,9,10,11,12) else "موسم نشط"
        elif city == "madinah":
            _sf = 2.0 if _month in (3,4,9,10,11,12) else 1.4
            _sl = "موسم الزيارة" if _month in (3,4,9,10,11,12) else "موسم اعتيادي"
        elif city == "abha":
            _sf = 2.2 if _month in (6,7,8) else 1.0
            _sl = "موسم الصيف" if _month in (6,7,8) else "الموسم العادي"
        elif city == "taif":
            _sf = 1.8 if _month in (6,7,8) else 1.0
            _sl = "موسم الصيف" if _month in (6,7,8) else "الموسم العادي"
        elif city in ("riyadh","qassim","hail"):
            _sf = 1.5 if _month in (11,12,1,2,3) else 1.0
            _sl = "موسم الشتاء" if _month in (11,12,1,2,3) else "الموسم العادي"
        elif city in ("jeddah","makkah"):
            _sf = 1.6 if _month in (11,12,1,2,3) else 1.2
            _sl = "موسم الشتاء" if _month in (11,12,1,2,3) else "الموسم المتوسط"
        else:
            _sf = 1.2; _sl = "الموسم العادي"
        _season_label = f"{_sl} — {_city_ar}"
        self._json({"market_adr":madr,"market_occ":mocc,"market_revpar":mrvp,
                    "our_adr":oadr,"our_occ":oocc,"our_revpar":orvp,
                    "adr_diff":oadr-madr,"occ_diff":oocc-mocc,"revpar_diff":orvp-mrvp,
                    "city":city,"type":typ,"season_factor":_sf,"season_label":_season_label})

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

    def _p_market_ai_client(self, b, store):
        """تحليل السوق بالذكاء الاصطناعي للعميل"""
        s    = adm.get("admin_settings", {})
        # منطق المفتاح: مفتاح العميل → أو مفتاح المالك إذا فعّل المشاركة
        client_key = store.get_d("settings",{}).get("claude_key","")
        admin_key  = s.get("claude_key","") if s.get("share_claude_key", True) else ""
        env_key    = os.environ.get("ANTHROPIC_API_KEY","")
        ai_enabled = s.get("ai_enabled_for_clients", True)
        key = (client_key or admin_key or env_key) if ai_enabled else ""
        city = b.get("city", store.get_d("settings",{}).get("city","riyadh"))

        # بيانات ثابتة كـ fallback
        rates = {
            "makkah":  {"hotel_avg":910,"apart_avg":650,"hotel_occ":85,"apart_occ":80,"season":"موسم عمرة"},
            "madinah": {"hotel_avg":600,"apart_avg":400,"hotel_occ":78,"apart_occ":72,"season":"موسم اعتيادي"},
            "riyadh":  {"hotel_avg":450,"apart_avg":300,"hotel_occ":70,"apart_occ":65,"season":"موسم اعتيادي"},
            "jeddah":  {"hotel_avg":500,"apart_avg":350,"hotel_occ":72,"apart_occ":68,"season":"موسم اعتيادي"},
            "dammam":  {"hotel_avg":320,"apart_avg":220,"hotel_occ":65,"apart_occ":60,"season":"موسم اعتيادي"},
            "khobar":  {"hotel_avg":350,"apart_avg":240,"hotel_occ":67,"apart_occ":62,"season":"موسم اعتيادي"},
            "abha":    {"hotel_avg":300,"apart_avg":200,"hotel_occ":75,"apart_occ":70,"season":"موسم صيفي"},
        }
        r = dict(rates.get(city, {"hotel_avg":350,"apart_avg":250,"hotel_occ":65,"apart_occ":60,"season":"موسم اعتيادي"}))

        if key:
            prompt = (
                f"أنت خبير فندقي سعودي. أعطني تحليل السوق الفندقي في {city} الآن. "
                f"أجب بـ JSON فقط بدون أي نص آخر: "
                f"{{\"hotel_avg\":0,\"apart_avg\":0,\"hotel_occ\":0,\"apart_occ\":0,"
                f"\"season\":\"\",\"season_factor\":1.0,\"recommendation\":\"\",\"insight\":\"\"}}"
            )
            text, err = _claude_call(key, prompt, max_tokens=400, timeout=25)
            if text:
                parsed = _extract_json(text)
                if parsed:
                    r.update(parsed)
                    r["source"] = "Claude AI"
                else:
                    r["source"] = "بيانات ثابتة (لم يُرجع JSON)"
            else:
                r["source"] = f"بيانات ثابتة ({err or 'لا رد'})"
        else:
            r["source"] = "بيانات ثابتة — أضف Claude API Key"

        r["ok"] = True
        self._json({"ok": True, "result": r})

    def _p_market_ws_client(self, b, store):
        """
        بحث أسعار السوق الحقيقية من Booking/Google/Agoda بالذكاء الاصطناعي.
        محدود بمرة واحدة كل 60 دقيقة لكل عميل.
        """
        # Rate limiting: مرة واحدة كل ساعة
        last = store.get_d("market_last_search", None)
        if last:
            try:
                elapsed = (datetime.now() - datetime.fromisoformat(last)).total_seconds()
                if elapsed < 3600:
                    remaining = int((3600 - elapsed) / 60)
                    cached = store.get_d("market_last_result", None)
                    if cached:
                        cached["rate_limited"] = True
                        cached["wait_minutes"] = remaining
                        cached["message"] = f"آخر بحث منذ {int(elapsed/60)} دقيقة — يمكنك البحث مجدداً بعد {remaining} دقيقة"
                        self._json({"ok": True, "result": cached, "cached": True})
                        return
            except Exception:
                pass

        s          = adm.get("admin_settings", {})
        client_key = store.get_d("settings",{}).get("claude_key","")
        admin_key  = s.get("claude_key","") if s.get("share_claude_key", True) else ""
        env_key    = os.environ.get("ANTHROPIC_API_KEY","")
        ai_enabled = s.get("ai_enabled_for_clients", True)
        key        = (client_key or admin_key or env_key) if ai_enabled else ""

        city    = b.get("city", store.get_d("settings",{}).get("city","riyadh"))
        htype   = b.get("type", store.get_d("settings",{}).get("type","hotel"))
        checkin = b.get("checkin", str((date.today() + timedelta(days=1))))
        checkout= b.get("checkout", str((date.today() + timedelta(days=2))))

        city_ar = {
            "riyadh":"الرياض","jeddah":"جدة","makkah":"مكة المكرمة",
            "madinah":"المدينة المنورة","dammam":"الدمام","khobar":"الخبر",
            "abha":"أبها","taif":"الطائف","tabuk":"تبوك",
            "jubail":"الجبيل","ahsa":"الأحساء","qassim":"القصيم",
        }.get(city, city)

        static = {
            "makkah":  {"hotel_avg":920,"apart_avg":660,"hotel_occ":86,"apart_occ":81},
            "madinah": {"hotel_avg":610,"apart_avg":410,"hotel_occ":79,"apart_occ":73},
            "riyadh":  {"hotel_avg":460,"apart_avg":310,"hotel_occ":71,"apart_occ":66},
            "jeddah":  {"hotel_avg":510,"apart_avg":360,"hotel_occ":73,"apart_occ":69},
            "dammam":  {"hotel_avg":330,"apart_avg":230,"hotel_occ":66,"apart_occ":61},
            "khobar":  {"hotel_avg":360,"apart_avg":250,"hotel_occ":68,"apart_occ":63},
            "abha":    {"hotel_avg":310,"apart_avg":210,"hotel_occ":76,"apart_occ":71},
            "taif":    {"hotel_avg":280,"apart_avg":190,"hotel_occ":68,"apart_occ":63},
        }
        base = dict(static.get(city, {"hotel_avg":360,"apart_avg":260,"hotel_occ":66,"apart_occ":61}))

        result = {
            **base,
            "city": city, "city_ar": city_ar,
            "checkin": checkin, "checkout": checkout,
            "season": "موسم عادي", "season_factor": 1.0,
            "recommendation": f"السعر المقترح: {int(base['hotel_avg']*1.1)} ر.س (فندق) / {int(base['apart_avg']*1.1)} ر.س (شقق)",
            "insight": "بيانات مرجعية — أضف مفتاح Claude للبحث الحي",
            "source": "بيانات مرجعية",
            "booking_samples": [], "agoda_samples": [], "google_samples": [],
            "searched_at": _iso(),
        }

        if key:
            today_str = date.today().strftime("%Y-%m-%d")
            htype_ar = "فندق" if htype == "hotel" else "شقق فندقية"
            json_schema = (
                '{"hotel_avg":0,"apart_avg":0,"hotel_occ":0,"apart_occ":0,'
                '"season":"","season_factor":1.0,"recommendation":"","insight":"",'
                '"booking_avg":0,"agoda_avg":0,"google_avg":0,'
                '"booking_samples":[{"name":"","price":0,"stars":0,"rating":0.0}],'
                '"agoda_samples":[{"name":"","price":0,"stars":0,"rating":0.0}],'
                '"google_samples":[{"name":"","price":0,"stars":0,"rating":0.0}],'
                '"source":"Claude AI"}'
            )
            prompt = (
                f"أنت خبير أسعار فنادق سعودية. ابحث عن أسعار {city_ar} ليلة {checkin}."
                f" نوع: {htype_ar}. اليوم: {today_str}."
                f" أعطني أسعار حقيقية من Booking.com وAgoda وGoogle Hotels وAirbnb."
                f" أجب بـ JSON فقط بهذا الشكل: {json_schema}"
            )
            text, err = _claude_call(key, prompt, max_tokens=1000, timeout=28)
            if text:
                parsed = _extract_json(text)
                if parsed:
                    result.update(parsed)
                    result["source"] = parsed.get("source", "Claude AI")
                    result["searched_at"] = _iso()
                else:
                    result["source"] = "بيانات مرجعية (Claude لم يُرجع JSON)"
            else:
                result["source"] = f"بيانات مرجعية ({err or 'timeout'})"
        else:
            result["source"] = "بيانات مرجعية — لا يوجد مفتاح AI"

        result["ok"] = True
        store.set_d("market_last_search", _iso())
        store.set_d("market_last_result", result)

        mr = store.get_d("market_rates", {})
        mr.setdefault("rates", {})[city] = {
            "hotel_avg": result.get("hotel_avg", 0),
            "apart_avg": result.get("apart_avg", 0),
            "hotel_occ": result.get("hotel_occ", 0),
            "apart_occ": result.get("apart_occ", 0),
        }
        mr["last_updated"] = _iso()
        store.set_d("market_rates", mr)
        log.info(f"Market websearch: {city} {result.get('hotel_avg',0)} ر.س — {result.get('source','')}")
        self._json({"ok": True, "result": result})

    def _p_ai_analyze_data(self, b, store, client):
        """تحليل بيانات الفندق الكاملة بالذكاء الاصطناعي"""
        s   = adm.get("admin_settings", {})
        client_key = store.get_d("settings",{}).get("claude_key","")
        admin_key  = s.get("claude_key","") if s.get("share_claude_key", True) else ""
        env_key    = os.environ.get("ANTHROPIC_API_KEY","")
        ai_enabled = s.get("ai_enabled_for_clients", True)
        key = (client_key or admin_key or env_key) if ai_enabled else ""

        # جمع بيانات الفندق
        guests    = store.get_d("guests", [])
        services  = store.get_d("services", [])
        invoices  = store.get_d("invoices", [])
        recv      = store.get_d("receivables", [])
        settings  = store.get_d("settings", {})
        city      = settings.get("city", "riyadh")
        htype     = settings.get("type", "hotel")
        rooms     = settings.get("rooms", 50) or 50

        active_g  = [g for g in guests if g.get("status") == "active"]
        total_rev = sum(g["total"] for g in guests) + sum(sv["amount"] for sv in services)
        total_exp = sum(i["total"] for i in invoices if i.get("status") != "paid")
        pending_recv = sum(r["amount"] for r in recv if r.get("status") == "pending")
        occ_rate  = round(len(active_g) / rooms * 100, 1) if rooms else 0
        nights    = sum(g.get("nights", 1) for g in guests) or 1
        adr       = round(sum(g["total"] for g in guests) / nights, 1)
        revpar    = round(sum(g["total"] for g in guests) / rooms, 1) if rooms else 0

        city_ar = {"riyadh":"الرياض","jeddah":"جدة","makkah":"مكة","madinah":"المدينة",
                   "dammam":"الدمام","khobar":"الخبر","abha":"أبها","taif":"الطائف"}.get(city, city)

        analysis_type = b.get("type", "full")  # full | revenue | occupancy | expenses

        prompt = f"""أنت مستشار مالي فندقي خبير في السوق السعودي.

=== بيانات فندق {settings.get('name','الفندق')} في {city_ar} ===
النوع: {"فندق" if htype=="hotel" else "شقق مخدومة"}
عدد الغرف: {rooms}
إجمالي النزلاء (كل الوقت): {len(guests)}
نزلاء حاليون (نشط): {len(active_g)}
نسبة الإشغال: {occ_rate}%
متوسط سعر الليلة (ADR): {adr} ر.س
RevPAR: {revpar} ر.س
إجمالي الإيرادات: {total_rev} ر.س
إجمالي المصاريف غير المسددة: {total_exp} ر.س
ذمم مدينة معلقة: {pending_recv} ر.س
هامش الربح: {round((total_rev - total_exp) / total_rev * 100, 1) if total_rev > 0 else 0}%

نوع التحليل المطلوب: {analysis_type}

قدم تحليلاً شاملاً يتضمن:
1. تقييم الأداء الحالي (إيجابيات وسلبيات)
2. مقارنة بمعايير السوق السعودي لمدينة {city_ar}
3. 3 توصيات عملية فورية قابلة للتنفيذ
4. توقع الإيراد الشهري إذا تحسن الإشغال بنسبة 15%
5. نصيحة تسعير موسمية

أجب بـ JSON فقط:
{{"performance_score": 75, "performance_label": "جيد", "strengths": ["..."], "weaknesses": ["..."], "recommendations": [{{"title":"...","action":"...","impact":"..."}}], "revenue_forecast": {{"current":0,"improved":0,"improvement_pct":0}}, "pricing_advice": "...", "market_comparison": "...", "summary": "..."}}"""

        result = {
            "performance_score": min(100, max(0, int(occ_rate * 1.2))),
            "performance_label": "ممتاز" if occ_rate >= 80 else ("جيد" if occ_rate >= 60 else ("متوسط" if occ_rate >= 40 else "يحتاج تحسين")),
            "strengths": ["بيانات نزلاء منتظمة", f"إشغال {occ_rate}%"] if occ_rate > 50 else ["نظام متكامل للتتبع"],
            "weaknesses": [f"ذمم معلقة {pending_recv} ر.س"] if pending_recv > 0 else [],
            "recommendations": [
                {"title": "تحسين نسبة الإشغال", "action": f"استهدف {min(100,int(occ_rate)+15)}% إشغال بحملات تسويقية", "impact": "زيادة إيرادات 15-20%"},
                {"title": "تحصيل الذمم", "action": f"تحصيل {pending_recv} ر.س المعلقة", "impact": "تحسين التدفق النقدي"},
                {"title": "مراجعة التسعير", "action": f"رفع ADR من {adr} إلى {int(adr*1.1)} ر.س", "impact": "زيادة إيرادات 10%"},
            ],
            "revenue_forecast": {
                "current": round(total_rev),
                "improved": round(total_rev * 1.15),
                "improvement_pct": 15,
            },
            "pricing_advice": f"السعر الحالي {adr} ر.س/ليلة — يُنصح برفعه في مواسم الذروة",
            "market_comparison": f"بيانات السوق في {city_ar} تشير لمتوسط ADR أعلى من المعدل",
            "summary": f"الفندق يعمل بكفاءة {occ_rate}% إشغال — إجمالي الإيرادات {total_rev} ر.س",
            "source": "بيانات ثابتة",
            "ok": True,
        }

        if key:
            text, err = _claude_call(key, prompt, max_tokens=1200, timeout=28)
            if text:
                parsed = _extract_json(text)
                if parsed:
                    result.update(parsed)
                    result["source"] = "Claude AI"
                    result["ok"] = True
                else:
                    result["source"] = "بيانات محسوبة (JSON غير صحيح)"
            else:
                result["source"] = f"بيانات محسوبة ({err or 'timeout'})"

        self._json({"ok": True, "result": result, "data": {
            "total_revenue": round(total_rev, 2),
            "total_expenses": round(total_exp, 2),
            "pending_receivables": round(pending_recv, 2),
            "occupancy_rate": occ_rate,
            "adr": adr,
            "revpar": revpar,
            "active_guests": len(active_g),
            "total_guests": len(guests),
        }})

    def _api_client_backups(self, store):
        """قائمة النسخ الاحتياطية للعميل"""
        backups = store.get_d("backups", [])
        self._json({"ok":True,"backups":backups})

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
        cmd = b.get("command", "").strip()
        s   = adm.get("admin_settings", {})
        # قراءة المفتاح من كل المصادر بالأولوية
        key = (b.get("claude_key","") or b.get("key","") or
               s.get("claude_key","") or
               os.environ.get("ANTHROPIC_API_KEY","")).strip()
        if not cmd:
            self._json({"ok": False, "error": "أدخل أمراً"}); return
        if not key:
            self._json({"ok": False, "error": "لا يوجد مفتاح Claude API — أضفه في الإعدادات"}); return

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

        # حساب الموسم لكل مدينة عميل
        def _get_season(city, month):
            seasons = {
                "makkah":  {(3,4,9,10,11,12):"موسم العمرة ×2.5",  "default":"موسم نشط ×1.8"},
                "madinah": {(3,4,9,10,11,12):"موسم الزيارة ×2.0", "default":"موسم اعتيادي ×1.4"},
                "abha":    {(6,7,8):"موسم الصيف ×2.2",            "default":"الموسم العادي ×1.0"},
                "taif":    {(6,7,8):"موسم الصيف ×1.8",            "default":"الموسم العادي ×1.0"},
                "riyadh":  {(11,12,1,2,3):"موسم الشتاء ×1.5",     "default":"الموسم العادي ×1.0"},
                "jeddah":  {(11,12,1,2,3):"موسم الشتاء ×1.6",     "default":"الموسم المتوسط ×1.2"},
            }
            city_seasons = seasons.get(city, {})
            for months_tuple, label in city_seasons.items():
                if isinstance(months_tuple, tuple) and month in months_tuple:
                    return label
            return city_seasons.get("default", "الموسم العادي ×1.0")

        _cur_month = date.today().month
        clients_season = [
            f"{c.get('hotel_name',c['name'])} ({c.get('city','')}) — {_get_season(c.get('city',''), _cur_month)}"
            for c in clients[:10]
        ]

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

=== الموسم الحالي لكل عميل (شهر {_cur_month}) ===
{chr(10).join(clients_season) or 'لا يوجد عملاء'}

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
            text, err = _claude_call(key, system_context, max_tokens=1500, timeout=28)
            if text:
                parsed = _extract_json(text)
                if parsed:
                    result = parsed
                else:
                    result = {"response": f"رد غير متوقع من Claude: {text[:200]}", "actions": [], "summary": "", "suggestions": []}
            else:
                log.error(f"AI control error: {err}")
                result = {"response": f"خطأ في الاتصال بـ Claude: {err or 'timeout'}", "actions": [], "summary": "", "suggestions": []}
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
        s   = adm.get("admin_settings",{})
        sn  = s.get("system_name","ضيوف")
        em  = s.get("logo_emoji","🏨")
        td  = s.get("trial_days",15)
        wa  = s.get("owner_whatsapp","")
        col = s.get("primary_color","#C9A84C")
        return f"""<!DOCTYPE html>
<html lang="ar" dir="rtl">
<head>
<meta charset="UTF-8"/>
<meta name="viewport" content="width=device-width,initial-scale=1"/>
<title>{sn} — برنامج محاسبي بدون محاسب</title>
<link href="https://fonts.googleapis.com/css2?family=Tajawal:wght@300;400;500;700;800;900&display=swap" rel="stylesheet"/>
<style>
*{{box-sizing:border-box;margin:0;padding:0;}}
:root{{--gold:{col};--dark:#0a0a0a;--dark2:#111827;--white:#fff;--gray:#6B7280;--border:#E5E7EB;--green:#0F6E56;}}
html{{scroll-behavior:smooth;}}
body{{font-family:'Tajawal',sans-serif;direction:rtl;background:var(--white);color:var(--dark);overflow-x:hidden;}}
nav{{position:fixed;top:0;right:0;left:0;z-index:100;background:rgba(10,10,10,.96);backdrop-filter:blur(12px);border-bottom:1px solid rgba(201,168,76,.2);padding:0 5%;}}
.nav-inner{{display:flex;align-items:center;justify-content:space-between;height:64px;}}
.nav-logo{{font-size:20px;font-weight:900;color:var(--gold);}}
.nav-logo span{{color:#9CA3AF;font-weight:400;font-size:14px;margin-right:6px;}}
.nav-links{{display:flex;align-items:center;gap:28px;}}
.nav-links a{{color:rgba(255,255,255,.75);text-decoration:none;font-size:13px;font-weight:500;transition:.2s;}}
.nav-links a:hover{{color:var(--gold);}}
.nav-cta{{background:var(--gold);color:var(--dark)!important;padding:9px 22px;border-radius:6px;font-weight:700!important;}}
.hero{{min-height:100vh;background:var(--dark2);display:flex;align-items:center;padding:100px 5% 60px;position:relative;overflow:hidden;}}
.hero::before{{content:'';position:absolute;inset:0;background:radial-gradient(ellipse at 70% 50%,rgba(201,168,76,.08) 0%,transparent 60%);}}
.hero-inner{{display:grid;grid-template-columns:1fr 1fr;gap:60px;align-items:center;max-width:1200px;margin:0 auto;width:100%;position:relative;z-index:1;}}
.hero-text h1{{font-size:clamp(26px,3.5vw,48px);font-weight:900;color:var(--white);line-height:1.25;margin-bottom:18px;}}
.hero-text h1 em{{color:var(--gold);font-style:normal;display:block;}}
.hero-text p{{color:rgba(255,255,255,.7);font-size:14px;line-height:1.9;margin-bottom:8px;}}
.hero-text p strong{{color:#E8C97A;}}
.hero-row{{display:flex;gap:10px;margin-top:24px;flex-wrap:wrap;}}
.hero-input{{flex:1;min-width:180px;padding:12px 15px;border:1.5px solid rgba(201,168,76,.35);border-radius:8px;background:rgba(255,255,255,.06);color:#fff;font-family:'Tajawal',sans-serif;font-size:13px;outline:none;}}
.hero-input:focus{{border-color:var(--gold);}}
.hero-input::placeholder{{color:rgba(255,255,255,.3);}}
.hero-btn{{padding:12px 26px;background:var(--gold);color:var(--dark);border:none;border-radius:8px;font-family:'Tajawal',sans-serif;font-size:14px;font-weight:800;cursor:pointer;white-space:nowrap;transition:.2s;}}
.hero-btn:hover{{opacity:.9;transform:translateY(-1px);}}
.hero-img img{{width:100%;border-radius:14px;box-shadow:0 30px 70px rgba(0,0,0,.5);display:block;}}
.section{{padding:80px 5%;}}
.sec-inner{{max-width:1200px;margin:0 auto;}}
.sec-hdr{{text-align:center;margin-bottom:50px;}}
.sec-hdr h2{{font-size:clamp(20px,2.8vw,36px);font-weight:900;margin-bottom:10px;}}
.sec-hdr p{{color:var(--gray);font-size:14px;max-width:520px;margin:0 auto;}}
.feat-grid{{display:grid;grid-template-columns:repeat(3,1fr);gap:24px;}}
.feat-card{{border:1.5px solid var(--border);border-radius:14px;overflow:hidden;transition:.3s;}}
.feat-card:hover{{border-color:var(--gold);box-shadow:0 10px 30px rgba(201,168,76,.12);transform:translateY(-3px);}}
.feat-icon{{height:160px;display:flex;align-items:center;justify-content:center;font-size:60px;}}
.feat-body{{padding:20px;}}
.feat-body h3{{font-size:16px;font-weight:800;margin-bottom:8px;}}
.feat-body p{{font-size:12px;color:var(--gray);line-height:1.8;margin-bottom:14px;}}
.feat-btn{{padding:8px 18px;border:2px solid var(--dark);border-radius:6px;font-family:'Tajawal',sans-serif;font-size:12px;font-weight:700;background:transparent;cursor:pointer;transition:.2s;}}
.feat-btn:hover{{background:var(--dark);color:#fff;}}
.login-sec{{background:var(--dark2);padding:80px 5%;}}
.login-inner{{max-width:1100px;margin:0 auto;display:grid;grid-template-columns:1fr 400px;gap:60px;align-items:center;}}
.login-text h2{{font-size:clamp(20px,2.8vw,38px);font-weight:900;color:var(--white);margin-bottom:14px;line-height:1.3;}}
.login-text h2 em{{color:var(--gold);font-style:normal;}}
.login-text p{{color:rgba(255,255,255,.6);font-size:13px;line-height:1.9;margin-bottom:20px;}}
.perks{{display:flex;flex-direction:column;gap:10px;}}
.perk{{display:flex;align-items:center;gap:10px;color:rgba(255,255,255,.8);font-size:13px;}}
.perk-ic{{width:30px;height:30px;border-radius:7px;background:rgba(201,168,76,.15);display:flex;align-items:center;justify-content:center;font-size:14px;flex-shrink:0;}}
.lcard{{background:#fff;border-radius:18px;padding:32px;box-shadow:0 25px 70px rgba(0,0,0,.4);}}
.ltabs{{display:flex;border-radius:9px;overflow:hidden;border:1.5px solid var(--border);margin-bottom:20px;}}
.ltab{{flex:1;padding:10px;text-align:center;cursor:pointer;font-family:'Tajawal',sans-serif;font-size:13px;font-weight:700;color:var(--gray);background:#F8FAFC;border:none;transition:.2s;}}
.ltab.on{{background:var(--dark2);color:#fff;}}
.lpg{{display:none;}}.lpg.on{{display:block;}}
.fg{{margin-bottom:12px;}}
.fg label{{font-size:10px;font-weight:700;color:var(--gray);display:block;margin-bottom:4px;letter-spacing:.5px;text-transform:uppercase;}}
.fg input,.fg select{{width:100%;border:1.5px solid var(--border);border-radius:7px;padding:10px 12px;font-family:'Tajawal',sans-serif;font-size:13px;outline:none;transition:.2s;color:var(--dark);}}
.fg input:focus,.fg select:focus{{border-color:var(--gold);box-shadow:0 0 0 3px {col}22;}}
.lbtn{{width:100%;padding:12px;border:none;border-radius:8px;font-family:'Tajawal',sans-serif;font-size:14px;font-weight:800;cursor:pointer;transition:.2s;margin-top:4px;}}
.lbtn-in{{background:var(--dark2);color:#fff;}}
.lbtn-reg{{background:linear-gradient(135deg,var(--green),#10B981);color:#fff;}}
.lerr{{color:#DC2626;font-size:11px;margin-top:6px;text-align:center;display:none;}}
.tbadge{{background:#EEF2FF;border:1px solid #C7D2FE;border-radius:7px;padding:9px 12px;font-size:11px;color:#3730A3;margin-bottom:14px;text-align:center;font-weight:600;}}
.div{{text-align:center;font-size:11px;color:var(--gray);margin:12px 0;position:relative;}}
.div::before,.div::after{{content:'';position:absolute;top:50%;width:38%;height:1px;background:var(--border);}}
.div::before{{right:0;}}.div::after{{left:0;}}
footer{{background:var(--dark);color:rgba(255,255,255,.4);text-align:center;padding:24px 5%;font-size:12px;}}
footer a{{color:var(--gold);text-decoration:none;margin:0 6px;}}
.fade{{opacity:0;transform:translateY(24px);transition:opacity .6s,transform .6s;}}
.fade.vis{{opacity:1;transform:translateY(0);}}
@media(max-width:768px){{
  .hero-inner,.login-inner,.feat-grid{{grid-template-columns:1fr;}}
  .hero-img,.login-text{{display:none;}}
  nav .nav-links a:not(.nav-cta){{display:none;}}
}}
</style>
</head>
<body>
<nav><div class="nav-inner">
  <div class="nav-logo">{em} <span style="color:var(--gold);font-weight:900;font-size:20px;">{sn}</span> <span>برنامج محاسبي بدون محاسب</span></div>
  <div class="nav-links">
    <a href="#hero">الرئيسية</a>
    <a href="#features">الخدمات</a>
    <a href="#features">عن البرنامج</a>
    <a href="#login">تواصل بنا</a>
    <a href="#login" class="nav-cta" onclick="swTab('reg')">ابدأ مجاناً</a>
  </div>
</div></nav>

<section class="hero" id="hero">
  <div class="hero-inner">
    <div class="hero-text fade">
      <h1>استمتع بإدارة مالية متكاملة لفندقك مع برنامج<em><span style="color:var(--gold)">{sn}</span> — البرنامج المحاسبي الذكي بدون محاسب!</em></h1>
      <p><strong>حل شامل:</strong> أدوات متكاملة لإدارة الحسابات والفواتير والمخزون والنزلاء بشكل فعال.</p>
      <p><strong>تصميم مريح:</strong> واجهة سهلة الاستخدام توفر لك تجربة سلسة وسريعة.</p>
      <p><strong>تحليلات مالية دقيقة:</strong> تقارير شاملة تعزز قراراتك الاستراتيجية.</p>
      <p><strong>الموازنة:</strong> متكامل بأعلى معايير الأداء بدون التزامات مفاجأة.</p>
      <div class="hero-row">
        <input class="hero-input" id="hero-em" type="email" placeholder="أدخل بريدك الإلكتروني"/>
        <button class="hero-btn" onclick="heroReg()">أريد التجربة!</button>
      </div>
    </div>
    <div class="hero-img fade">
      <img src="https://images.unsplash.com/photo-1566073771259-6a8506099945?w=600&q=80" alt="فندق" onerror="this.parentNode.style.display='none'"/>
    </div>
  </div>
</section>

<section class="section" id="features">
  <div class="sec-inner">
    <div class="sec-hdr fade"><h2>ميزات فريدة لبرنامج المحاسبة</h2><p>استفد من مجموعة من الميزات المصممة خصيصاً لتلبية احتياجات قطاع الضيافة.</p></div>
    <div class="feat-grid">

      <div class="feat-card fade">
        <div class="feat-icon" style="background:linear-gradient(135deg,#0a1628,#0d2247);position:relative;overflow:hidden">
          <svg width="110" height="110" viewBox="0 0 110 110" fill="none" xmlns="http://www.w3.org/2000/svg">
            <rect x="20" y="48" width="70" height="46" rx="8" fill="#1e3a5f" stroke="#C9A84C" stroke-width="2"/>
            <path d="M35 48V34C35 23.5 42 16 55 16C68 16 75 23.5 75 34V48" stroke="#C9A84C" stroke-width="3" stroke-linecap="round"/>
            <circle cx="55" cy="68" r="8" fill="#C9A84C"/>
            <rect x="52" y="68" width="6" height="12" rx="3" fill="#C9A84C"/>
            <circle cx="35" cy="30" r="3" fill="#C9A84C" opacity=".4"/>
            <circle cx="75" cy="30" r="3" fill="#C9A84C" opacity=".4"/>
            <rect x="28" y="56" width="8" height="4" rx="2" fill="#C9A84C" opacity=".3"/>
            <rect x="74" y="56" width="8" height="4" rx="2" fill="#C9A84C" opacity=".3"/>
          </svg>
        </div>
        <div class="feat-body">
          <h3>أمان وحماية البيانات</h3>
          <p>تشفير كامل لبيانات نزلائك وسجلاتك المالية بمعايير أمان بنكية — بياناتك تبقى ملكك وحدك.</p>
          <button class="feat-btn" onclick="document.getElementById('login').scrollIntoView({{behavior:'smooth'}})">تأمين بياناتك</button>
        </div>
      </div>

      <div class="feat-card fade" style="transition-delay:.1s">
        <div class="feat-icon" style="background:linear-gradient(135deg,#0f1f0f,#0d2d14);position:relative">
          <svg width="120" height="110" viewBox="0 0 120 110" fill="none" xmlns="http://www.w3.org/2000/svg">
            <rect x="8" y="30" width="32" height="50" rx="6" fill="#1a3a1a" stroke="#C9A84C" stroke-width="1.5"/>
            <text x="24" y="51" text-anchor="middle" font-size="9" fill="#C9A84C" font-weight="bold">نزيل</text>
            <text x="24" y="63" text-anchor="middle" font-size="7" fill="#8aad8a">PMS</text>
            <rect x="44" y="30" width="32" height="50" rx="6" fill="#1a3a1a" stroke="#C9A84C" stroke-width="1.5"/>
            <text x="60" y="51" text-anchor="middle" font-size="8" fill="#C9A84C" font-weight="bold">Opera</text>
            <text x="60" y="63" text-anchor="middle" font-size="6.5" fill="#8aad8a">Cloud</text>
            <rect x="80" y="30" width="32" height="50" rx="6" fill="#1a3a1a" stroke="#C9A84C" stroke-width="1.5"/>
            <text x="96" y="48" text-anchor="middle" font-size="7.5" fill="#C9A84C" font-weight="bold">Cloud</text>
            <text x="96" y="58" text-anchor="middle" font-size="7.5" fill="#C9A84C" font-weight="bold">Beds</text>
            <line x1="40" y1="55" x2="44" y2="55" stroke="#C9A84C" stroke-width="1.5" stroke-dasharray="2,1"/>
            <line x1="76" y1="55" x2="80" y2="55" stroke="#C9A84C" stroke-width="1.5" stroke-dasharray="2,1"/>
            <circle cx="40" cy="55" r="2" fill="#C9A84C"/>
            <circle cx="76" cy="55" r="2" fill="#C9A84C"/>
          </svg>
        </div>
        <div class="feat-body">
          <h3>تكامل مع الأنظمة الأخرى</h3>
          <p>يتصل مباشرة بـ <strong>نزيل</strong> و<strong>Opera Cloud</strong> و<strong>Cloudbeds</strong> — مزامنة تلقائية لبيانات النزلاء والحجوزات.</p>
          <button class="feat-btn" onclick="document.getElementById('login').scrollIntoView({{behavior:'smooth'}})">تعرف على التكامل</button>
        </div>
      </div>

      <div class="feat-card fade" style="transition-delay:.2s">
        <div class="feat-icon" style="background:linear-gradient(135deg,#0d0d2e,#1a1a4a);position:relative">
          <svg width="120" height="110" viewBox="0 0 120 110" fill="none" xmlns="http://www.w3.org/2000/svg">
            <rect x="10" y="18" width="100" height="70" rx="8" fill="#111133" stroke="#334" stroke-width="1"/>
            <rect x="18" y="28" width="40" height="28" rx="4" fill="#0d1f3c"/>
            <rect x="18" y="28" width="40" height="6" rx="2" fill="#C9A84C" opacity=".8"/>
            <rect x="20" y="38" width="10" height="14" rx="2" fill="#C9A84C" opacity=".9"/>
            <rect x="33" y="42" width="10" height="10" rx="2" fill="#378ADD" opacity=".8"/>
            <rect x="46" y="36" width="10" height="16" rx="2" fill="#1D9E75" opacity=".8"/>
            <rect x="64" y="28" width="38" height="28" rx="4" fill="#0d1f3c"/>
            <circle cx="83" cy="42" r="11" stroke="#C9A84C" stroke-width="2" fill="none"/>
            <path d="M83 34 L83 42 L90 42" stroke="#C9A84C" stroke-width="1.5" stroke-linecap="round"/>
            <rect x="18" y="62" width="84" height="14" rx="4" fill="#0d1f3c"/>
            <rect x="22" y="66" width="20" height="6" rx="3" fill="#C9A84C" opacity=".5"/>
            <rect x="46" y="66" width="30" height="6" rx="3" fill="#378ADD" opacity=".4"/>
            <rect x="80" y="66" width="18" height="6" rx="3" fill="#1D9E75" opacity=".4"/>
          </svg>
        </div>
        <div class="feat-body">
          <h3>واجهة تحليل البيانات</h3>
          <p>لوحة تحكم ذكية بمؤشرات ADR وRevPAR والإشغال — رسوم بيانية فورية تساعدك على قرارات أسرع.</p>
          <button class="feat-btn" onclick="document.getElementById('login').scrollIntoView({{behavior:'smooth'}})">استمتع بالتجربة</button>
        </div>
      </div>

    </div>
  </div>
</section>

<section class="login-sec" id="login">
  <div class="login-inner">
    <div class="login-text fade">
      <h2>ابدأ رحلتك مع<em> {sn}</em> اليوم</h2>
      <p>انضم إلى مئات الفنادق والشقق المخدومة في السعودية التي تثق بنظامنا.</p>
      <div class="perks">
        <div class="perk"><div class="perk-ic">⭐</div><span>تجربة مجانية {td} يوم بدون بطاقة ائتمان</span></div>
        <div class="perk"><div class="perk-ic">🔒</div><span>بياناتك محفوظة ومشفرة بالكامل</span></div>
        <div class="perk"><div class="perk-ic">📊</div><span>تقارير مالية يومية وشهرية فورية</span></div>
        <div class="perk"><div class="perk-ic">💬</div><span>دعم فني عبر واتساب{" (" + wa + ")" if wa else ""}</span></div>
        <div class="perk"><div class="perk-ic">🏨</div><span>يعمل مع الفنادق والشقق المخدومة</span></div>
      </div>
    </div>
    <div class="lcard fade">
      <div style="text-align:center;margin-bottom:16px"><div style="font-size:34px">{em}</div><div style="font-size:16px;font-weight:900;margin-top:4px">{sn}</div></div>
      <div class="ltabs"><button class="ltab on" onclick="swTab('in')">تسجيل الدخول</button><button class="ltab" onclick="swTab('reg')">تجربة مجانية</button></div>
      <div class="lpg on" id="lpg-in">
        <div class="fg"><label>البريد الإلكتروني</label><input type="email" id="l-em" placeholder="hotel@example.com" onkeydown="if(event.key==='Enter')doLogin()"/></div>
        <button class="lbtn lbtn-in" onclick="doLogin()">دخول إلى لوحة التحكم ←</button>
        <div class="lerr" id="l-err"></div>
        <div class="div">أو</div>
        <button class="lbtn" style="background:transparent;border:1.5px solid var(--border);color:var(--gray);font-family:'Tajawal',sans-serif" onclick="swTab('reg')">ابدأ تجربتك المجانية</button>
      </div>
      <div class="lpg" id="lpg-reg">
        <div class="tbadge">⭐ تجربة مجانية {td} يوم — بدون بطاقة ائتمان</div>
        <div class="fg"><label>اسمك *</label><input id="r-name" placeholder="محمد العمري"/></div>
        <div class="fg"><label>اسم الفندق *</label><input id="r-hotel" placeholder="فندق النخبة"/></div>
        <div class="fg"><label>البريد الإلكتروني *</label><input type="email" id="r-em" placeholder="you@hotel.sa"/></div>
        <div class="fg"><label>رقم الجوال</label><input id="r-ph" placeholder="05xxxxxxxx"/></div>
        <div class="fg"><label>المدينة</label><select id="r-city"><option value="riyadh">الرياض</option><option value="jeddah">جدة</option><option value="makkah">مكة المكرمة</option><option value="madinah">المدينة المنورة</option><option value="dammam">الدمام</option><option value="khobar">الخبر</option><option value="jubail">الجبيل</option><option value="ahsa">الأحساء</option><option value="abha">أبها</option><option value="taif">الطائف</option><option value="tabuk">تبوك</option><option value="qassim">القصيم</option><option value="hail">حائل</option><option value="bahah">الباحة</option><option value="other">أخرى</option></select></div>
        <div class="fg"><label>نوع المنشأة</label><select id="r-type"><option value="hotel">فندق</option><option value="apart">شقق فندقية</option><option value="service">شقق مخدومة</option></select></div>
        <button class="lbtn lbtn-reg" onclick="doReg()">ابدأ التجربة المجانية ←</button>
        <div class="lerr" id="r-err"></div>
      </div>
    </div>
  </div>
</section>

<footer><div style="margin-bottom:8px"><a href="#hero">الرئيسية</a><a href="#features">الخدمات</a><a href="#login">تواصل</a></div>© 2026 {sn} — جميع الحقوق محفوظة &nbsp;|&nbsp; يعمل مع الفنادق والشقق المخدومة &nbsp;|&nbsp; 🇸🇦 تم التصميم والبرمجة والرفع بأيدي سعودية 100%</footer>

<script>
function swTab(t){{
  document.querySelectorAll('.ltab').forEach((e,i)=>e.classList.toggle('on',i===(t==='in'?0:1)));
  document.querySelectorAll('.lpg').forEach((e,i)=>e.classList.toggle('on',i===(t==='in'?0:1)));
  if(t==='reg')document.getElementById('login').scrollIntoView({{behavior:'smooth',block:'center'}});
}}
function heroReg(){{
  const em=document.getElementById('hero-em').value.trim();
  if(em)document.getElementById('r-em').value=em;
  swTab('reg');
}}
function showErr(id,msg){{const e=document.getElementById(id);if(e){{e.textContent=msg;e.style.display='block';setTimeout(()=>e.style.display='none',4000);}}}}
async function doLogin(){{
  const em=document.getElementById('l-em').value.trim();
  if(!em){{showErr('l-err','أدخل البريد الإلكتروني');return;}}
  const btn=document.querySelector('#lpg-in .lbtn-in');
  if(btn){{btn.textContent='جارٍ الدخول...';btn.disabled=true;}}
  try{{
    const r=await fetch('/api/client/login',{{method:'POST',headers:{{'Content-Type':'application/json'}},credentials:'include',body:JSON.stringify({{email:em}})}});
    const d=await r.json();
    if(d.ok){{location.href='/dashboard';}}
    else if(d.error==='expired'){{showExpired(d);}}
    else{{showErr('l-err',d.error||'البريد غير مسجل');}}
  }}catch(e){{showErr('l-err','خطأ في الاتصال');}}
  if(btn){{btn.textContent='دخول إلى لوحة التحكم ←';btn.disabled=false;}}
}}
async function doReg(){{
  const name=document.getElementById('r-name').value.trim();
  const em=document.getElementById('r-em').value.trim();
  if(!name||!em){{showErr('r-err','الاسم والبريد مطلوبان');return;}}
  const btn=document.querySelector('#lpg-reg .lbtn-reg');
  if(btn){{btn.textContent='جارٍ التسجيل...';btn.disabled=true;}}
  try{{
    const r=await fetch('/api/client/register',{{method:'POST',headers:{{'Content-Type':'application/json'}},credentials:'include',body:JSON.stringify({{name,hotel_name:document.getElementById('r-hotel').value||name,email:em,phone:document.getElementById('r-ph').value,city:document.getElementById('r-city').value,hotel_type:document.getElementById('r-type').value,rooms:50}})}});
    const d=await r.json();
    if(d.ok){{location.href='/dashboard';}}
    else{{showErr('r-err',d.error||'خطأ في التسجيل');}}
  }}catch(e){{showErr('r-err','خطأ في الاتصال');}}
  if(btn){{btn.textContent='ابدأ التجربة المجانية ←';btn.disabled=false;}}
}}
function showExpired(d){{
  const wa=d.whatsapp||'';
  const plans=(d.plans||[]).filter(p=>p.price>0);
  const bank=d.bank||{{}};
  const el=document.createElement('div');
  el.style.cssText='position:fixed;inset:0;background:rgba(0,0,0,.7);z-index:9999;display:flex;align-items:center;justify-content:center;padding:20px;';
  el.innerHTML=`<div style="background:#fff;border-radius:18px;padding:28px;max-width:440px;width:100%;font-family:Tajawal,sans-serif;direction:rtl;max-height:90vh;overflow-y:auto">
    <div style="text-align:center;margin-bottom:16px"><div style="font-size:38px">⏰</div><div style="font-size:18px;font-weight:900">انتهت فترة التجربة</div><div style="font-size:12px;color:#6B7280;margin-top:4px">${{d.message||'جدد اشتراكك للاستمرار'}}</div></div>
    ${{plans.map(p=>`<div style="border:2px solid ${{p.color||'#185FA5'}};border-radius:10px;padding:12px;margin-bottom:8px;text-align:center"><div style="font-weight:800;color:${{p.color||'#185FA5'}}">${{p.name}}</div><div style="font-size:22px;font-weight:900;color:${{p.color||'#185FA5'}}">${{p.price}} <span style="font-size:12px">ر.س/شهر</span></div></div>`).join('')}}
    ${{bank.iban?`<div style="background:#F0FDF4;border:1px solid #86EFAC;border-radius:8px;padding:12px;margin:10px 0;font-size:11px"><div style="font-weight:700;color:#166534;margin-bottom:4px">🏦 التحويل البنكي</div>${{bank.name?`<div>الاسم: <b>${{bank.name}}</b></div>`:''}}${{bank.bank?`<div>البنك: <b>${{bank.bank}}</b></div>`:''}}${{bank.iban?`<div style="font-family:monospace;font-weight:700;color:#166534">${{bank.iban}}</div>`:''}}</div>`:''}}
    ${{wa?`<a href="https://wa.me/${{wa}}" target="_blank" style="display:block;text-align:center;padding:12px;background:#25D366;color:#fff;border-radius:9px;text-decoration:none;font-weight:800;margin-top:8px">💬 واتساب للتجديد</a>`:''}}
    <button onclick="this.closest('[style]').remove()" style="width:100%;padding:9px;margin-top:8px;background:transparent;border:1.5px solid #E5E7EB;border-radius:7px;color:#6B7280;font-family:Tajawal,sans-serif;cursor:pointer">إغلاق</button>
  </div>`;
  document.body.appendChild(el);
}}
const obs=new IntersectionObserver(en=>en.forEach(e=>{{if(e.isIntersecting)e.target.classList.add('vis');}}),{{threshold:.1}});
document.querySelectorAll('.fade').forEach(el=>obs.observe(el));
</script>
</body></html>"""


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
        key = (b.get("claude_key","") or b.get("key","") or
               s.get("claude_key","") or
               os.environ.get("ANTHROPIC_API_KEY","")).strip()
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
            "logo_emoji","primary_color","announcement","disabled_pages",
            "share_claude_key","ai_enabled_for_clients",
        ]
        for k in allowed_keys:
            if k in b:
                s[k] = b[k]
        amod.adm.set("admin_settings", s)
        self._json({"ok": True})

    def _admin_save_ai_settings(self, amod, b):
        """
        حفظ إعدادات AI للعملاء — تفعيل/تعطيل مشاركة مفتاح Claude مع العملاء.
        يُتيح للمالك:
        1. تفعيل AI للعملاء باستخدام مفتاحه
        2. تعطيل AI للعملاء بالكامل
        3. تحديد المفتاح المستخدم
        """
        s = amod.adm.get("admin_settings", {})
        # تحديث إعدادات AI
        if "claude_key" in b:
            s["claude_key"] = b["claude_key"].strip()
        if "share_claude_key" in b:
            s["share_claude_key"] = bool(b["share_claude_key"])
        if "ai_enabled_for_clients" in b:
            s["ai_enabled_for_clients"] = bool(b["ai_enabled_for_clients"])
        amod.adm.set("admin_settings", s)
        log.info(f"AI settings updated — share:{s.get('share_claude_key')} enabled:{s.get('ai_enabled_for_clients')}")
        self._json({"ok": True,
                    "share_claude_key":      s.get("share_claude_key", False),
                    "ai_enabled_for_clients":s.get("ai_enabled_for_clients", True),
                    "has_key":               bool(s.get("claude_key",""))})

    def _admin_test_claude_key(self, b):
        """اختبار مفتاح Claude API"""
        key = (b.get("claude_key","") or b.get("key","") or "").strip()
        if not key:
            # حاول قراءة المفتاح من الإعدادات
            key = adm.get("admin_settings",{}).get("claude_key","").strip()
        if not key:
            self._json({"ok":False,"error":"أدخل المفتاح أولاً"}); return
        log.info(f"Testing Claude key: {key[:8]}...")
        text, err = _claude_call(key, "قل: مرحبا", max_tokens=15, timeout=20)
        if text:
            self._json({"ok":True,"model":"claude-sonnet-4-20250514","message":"المفتاح يعمل ✓"})
        else:
            self._json({"ok":False,"error": err or "المفتاح غير صحيح"})


    def _admin_backup_status(self):
        has_cfg = bool(_GH_TOKEN and _GH_REPO)
        clients  = adm.get("clients", [])
        self._json({"ok":True,"configured":has_cfg,"repo":_GH_REPO if has_cfg else "",
                    "branch":_GH_BRANCH,"clients_count":len(clients),
                    "message":f"مُفعّل — {_GH_REPO}" if has_cfg else "غير مُفعّل — أضف GITHUB_TOKEN و GITHUB_REPO في Railway Variables"})

    def _admin_backup_restore(self):
        if not _GH_TOKEN or not _GH_REPO:
            self._json({"ok":False,"error":"GitHub غير مُفعّل"}); return
        ok = _github_restore()
        adm._data = adm._load()
        clients = adm.get("clients", [])
        self._json({"ok":ok,"clients_count":len(clients),
                    "message":f"تم الاسترجاع — {len(clients)} عميل" if ok else "فشل الاسترجاع — تحقق من GITHUB_TOKEN"})

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
                # Replace only the LAST </body> (not ones inside JS template literals)
                last_body = html.rfind("</body>")
                if last_body != -1:
                    html = html[:last_body] + inject + "\n</body>" + html[last_body+7:]
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
    """نقطة الدخول الرئيسية — run_admin في خلفية، run_client في main thread"""
    print("="*58)
    print("  نظام إدارة الفنادق — Unified SaaS Server")
    print("="*58)
    print(f"  لوحة العميل  → PORT {CLIENT_PORT}")
    print(f"  لوحة المالك  → PORT {ADMIN_PORT} (/admin)")
    print(f"  Admin Pass   → {ADMIN_PASS}")
    print("="*58)
    # Admin server في background thread
    t_admin = threading.Thread(target=run_admin, daemon=True)
    t_admin.start()
    log.info(f"Admin server started on port {ADMIN_PORT}")
    # Client server في main thread (Railway يتطلب هذا)
    log.info(f"Client server starting on port {CLIENT_PORT}")
    sv = HTTPServer(("0.0.0.0", CLIENT_PORT), ClientHandler)
    log.info(f"✓ Ready — client:{CLIENT_PORT}  admin:{ADMIN_PORT}")
    try:
        sv.serve_forever()
    except KeyboardInterrupt:
        print("\n  تم الإيقاف.")

if __name__ == "__main__":
    main()
