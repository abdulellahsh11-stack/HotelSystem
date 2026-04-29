#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# Hotel SaaS — Single File (app.py) — Deploy: python app.py

#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
لوحة تحكم المالك — Admin Panel
نظام SaaS لإدارة عملاء الفنادق
المنفذ: 5051 | المسار: /admin
"""

import sys, os, json, threading, webbrowser, time, logging, hashlib, secrets, string, copy
from http.server import HTTPServer, BaseHTTPRequestHandler
from datetime import datetime, date, timedelta
from urllib.parse import urlparse, parse_qs

def _id():    return int(datetime.now().timestamp()*1000)
def _now():   return datetime.now().strftime("%H:%M")
def _today(): return str(date.today())
def _iso():   return datetime.now().isoformat()

# ── مسارات ──────────────────────────────────────────────────
APP_DIR  = os.path.join(os.path.expanduser("~"), "HotelAdmin")
DATA_DIR = os.path.join(APP_DIR, "data")
LOG_DIR  = os.path.join(APP_DIR, "logs")
for d in [DATA_DIR, LOG_DIR]: os.makedirs(d, exist_ok=True)

PORT        = 5051
ADMIN_PASS  = "Admin@2025#Hotel"   # ← غيّر هذه كلمة المرور
SESSION_KEY = secrets.token_hex(32)

logging.basicConfig(
    filename=os.path.join(LOG_DIR, f"admin_{date.today()}.log"),
    level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s",
    encoding="utf-8"
)

# ══════════════════════════════════════════════════════════════
#  قاعدة بيانات Admin
# ══════════════════════════════════════════════════════════════
class AdminStore:
    def __init__(self):
        self._file = os.path.join(DATA_DIR, "admin_store.json")
        self._data = self._load()

    def _load(self):
        if os.path.exists(self._file):
            try:
                with open(self._file, "r", encoding="utf-8") as f:
                    return json.load(f)
            except: pass
        return self._defaults()

    def _defaults(self):
        return {
            "clients": [],          # كل عميل (فندق)
            "license_keys": [],     # كل المفاتيح المُصدرة
            "tickets": [],          # تذاكر الدعم
            "payments": [],         # سجل المدفوعات
            "admin_settings": {
                "owner_name":    "المالك",
                "owner_email":   "admin@hotel-system.sa",
                "owner_phone":   "", "owner_whatsapp": "", "contact_message": "تواصل معنا لتجديد اشتراكك أو الاستفسار عن الباقات",
                "system_name":   "نظام إدارة الفنادق",
                "bank_iban":     "",
                "bank_name":     "",
                "trial_days":    15,
                "prices": {
                    "free":       0,
                    "pro":        299,
                    "enterprise": 799,
                },
                "plans": [
                    {
                        "id":"starter","name":"المبتدئ","price":149,"period":"شهري",
                        "color":"#0F6E56","badge":"","branch_fee":0,"branch_enabled":False,
                        "pos_devices":1,"max_guests":50,
                        "features":[
                            "حتى 50 نزيل شهرياً",
                            "جهاز نقاط دفع واحد",
                            "تكامل نظام إدارة واحد",
                            "تقارير أساسية يومية",
                            "فواتير بضريبة القيمة المضافة",
                            "نسخ احتياطي يدوي",
                            "جميع البيانات والتقارير يتم الاحتفاظ بها لدى العميل",
                            "دعم فني عبر التذاكر"
                        ],
                        "excluded":["مقارنة أسعار السوق","فروع متعددة","نسخ احتياطي تلقائي","دعم أولوية"]
                    },
                    {
                        "id":"pro","name":"الاحترافية","price":299,"period":"شهري",
                        "color":"#185FA5","badge":"الأكثر طلباً","branch_fee":0,"branch_enabled":False,
                        "pos_devices":5,"max_guests":0,
                        "features":[
                            "نزلاء غير محدود",
                            "حتى 5 أجهزة نقاط دفع",
                            "3 تكاملات نظام إدارة (Opera/Cloudbeds/مخصص)",
                            "مقارنة أسعار السوق اليومية",
                            "ميزانية هرمية وتدفق نقدي",
                            "تقارير PDF وExcel",
                            "نسخ احتياطي تلقائي يومي",
                            "جميع البيانات والتقارير يتم الاحتفاظ بها لدى العميل",
                            "دعم فني 24/7 بأولوية"
                        ],
                        "excluded":["فروع متعددة","API مفتوح"]
                    },
                    {
                        "id":"enterprise","name":"المؤسسية","price":799,"period":"شهري",
                        "color":"#534AB7","badge":"للسلاسل","branch_fee":150,"branch_enabled":True,
                        "pos_devices":0,"max_guests":0,
                        "features":[
                            "نزلاء غير محدود",
                            "أجهزة نقاط دفع غير محدودة",
                            "تكاملات نظام إدارة غير محدودة",
                            "رسوم إضافية 150 ر.س لكل فرع مرتبط",
                            "إدارة مركزية لجميع الفروع",
                            "مقارنة أسعار السوق المتقدمة",
                            "تقارير موحدة للسلسلة",
                            "نسخ احتياطي فوري لحظي",
                            "جميع البيانات والتقارير يتم الاحتفاظ بها لدى العميل",
                            "API مفتوح للتكامل",
                            "مدير حساب مخصص",
                            "دعم فني مباشر أولوية قصوى"
                        ],
                        "excluded":[]
                    },
                ],
                "ai_market_competitors": [],
            },
            "sessions": {},
        }

    def save(self):
        with open(self._file, "w", encoding="utf-8") as f:
            json.dump(self._data, f, ensure_ascii=False, indent=2)

    def get(self, key, default=None):
        return self._data.get(key, default)

    def set(self, key, val):
        self._data[key] = val
        self.save()

    def append(self, key, item):
        self._data.setdefault(key, []).append(item)
        self.save()

adm = AdminStore()

# ══════════════════════════════════════════════════════════════
#  مولّد مفاتيح الترخيص
# ══════════════════════════════════════════════════════════════
def gen_key(plan="pro"):
    prefix = {"free":"FREE","pro":"HOTEL","enterprise":"ENT"}.get(plan,"HOTEL")
    parts  = [secrets.token_hex(2).upper() for _ in range(3)]
    return f"{prefix}-{parts[0]}-{parts[1]}-{parts[2]}"

def key_expiry(days=30):
    return (date.today() + timedelta(days=days)).isoformat()

def _now(): return datetime.now().strftime("%H:%M")
def _today(): return str(date.today())
def _id(): return int(datetime.now().timestamp() * 1000)

# ══════════════════════════════════════════════════════════════
#  HTTP Handler
# ══════════════════════════════════════════════════════════════
sessions = {}   # token → expiry

class AdminHandler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args): pass

    def _authed(self):
        cookie = self.headers.get("Cookie", "")
        for part in cookie.split(";"):
            part = part.strip()
            if part.startswith("admin_token="):
                tok = part.split("=", 1)[1]
                exp = sessions.get(tok)
                if exp and datetime.fromisoformat(exp) > datetime.now():
                    return True
        return False

    def _json(self, data, status=200):
        body = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type",   "application/json; charset=utf-8")
        self.send_header("Content-Length", len(body))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(body)

    def _html(self, html_str):
        body = html_str.encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type",   "text/html; charset=utf-8")
        self.send_header("Content-Length", len(body))
        self.end_headers()
        self.wfile.write(body)

    def _redirect(self, loc):
        self.send_response(302)
        self.send_header("Location", loc)
        self.end_headers()

    def do_GET(self):
        p = urlparse(self.path)
        path = p.path.rstrip("/") or "/"

        if path in ("/", "/admin"):
            if self._authed():
                self._html(_build_admin_html())
            else:
                self._html(_build_login_html())
            return

        if not self._authed():
            self._json({"error": "unauthorized"}, 401)
            return

        routes = {
            "/api/admin/stats":    self._api_stats,
            "/api/admin/clients":  self._api_clients,
            "/api/admin/keys":     self._api_keys,
            "/api/admin/tickets":  self._api_tickets,
            "/api/admin/payments": self._api_payments,
            "/api/admin/settings": self._api_settings,
            "/api/admin/plans":    self._api_plans,
            "/api/admin/market":   self._api_admin_market,
            "/api/admin/update/status": self._p_update_status,
        }
        fn = routes.get(path)
        if fn: fn(p)
        else:  self._json({"error": "not found"}, 404)

    def do_POST(self):
        n = int(self.headers.get("Content-Length", 0))
        b = json.loads(self.rfile.read(n)) if n else {}
        p = urlparse(self.path)
        path = p.path.rstrip("/")

        # تسجيل دخول — لا يحتاج مصادقة
        if path == "/api/admin/login":
            self._p_login(b)
            return

        if path == "/api/admin/logout":
            self._p_logout(b)
            return

        if not self._authed():
            self._json({"error": "unauthorized"}, 401)
            return

        routes = {
            "/api/admin/clients/add":         self._p_client_add,
            "/api/admin/clients/update":      self._p_client_update,
            "/api/admin/clients/toggle":      self._p_client_toggle,
            "/api/admin/clients/extend":      self._p_client_extend,
            "/api/admin/clients/delete":      self._p_client_delete,
            "/api/admin/keys/generate":       self._p_key_generate,
            "/api/admin/keys/revoke":         self._p_key_revoke,
            "/api/admin/keys/assign":         self._p_key_assign,
            "/api/admin/tickets/reply":       self._p_ticket_reply,
            "/api/admin/tickets/close":       self._p_ticket_close,
            "/api/admin/tickets/add":         self._p_ticket_add,
            "/api/admin/payments/add":        self._p_payment_add,
            "/api/admin/settings/save":       self._p_settings_save,
            "/api/admin/clients/settings":    self._p_client_settings,
            "/api/admin/market/ai":           self._p_admin_market_ai,
            "/api/admin/competitors/add":     self._p_competitor_add,
            "/api/admin/competitors/delete":  self._p_competitor_del,
            "/api/admin/update/upload":       self._p_update_upload,
            "/api/admin/update/status":       self._p_update_status,
            "/api/admin/branches/add":        self._p_branch_add,
            "/api/admin/branches/delete":     self._p_branch_del,
            "/api/admin/branches/list":       self._api_branches,
            "/api/admin/plans/add":           self._p_plan_add,
            "/api/admin/plans/delete":        self._p_plan_del,
            "/api/admin/plans/duplicate":     self._p_plan_dup,
        }
        fn = routes.get(path)
        if fn: fn(b)
        else:  self._json({"error": "not found"}, 404)

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET,POST,OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    # ── Auth ──────────────────────────────────────────────────
    def _p_login(self, b):
        pw = b.get("password", "")
        if pw == ADMIN_PASS:
            tok = secrets.token_hex(24)
            exp = (datetime.now() + timedelta(hours=12)).isoformat()
            sessions[tok] = exp
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Set-Cookie", f"admin_token={tok}; Path=/; HttpOnly; SameSite=Strict; Max-Age=43200")
            body = json.dumps({"ok": True}).encode()
            self.send_header("Content-Length", len(body))
            self.end_headers()
            self.wfile.write(body)
            logging.info("Admin login successful")
        else:
            logging.warning("Admin login failed")
            self._json({"ok": False, "error": "كلمة المرور خاطئة"}, 401)

    def _p_logout(self, b):
        cookie = self.headers.get("Cookie", "")
        for part in cookie.split(";"):
            part = part.strip()
            if part.startswith("admin_token="):
                tok = part.split("=", 1)[1]
                sessions.pop(tok, None)
        self._json({"ok": True})

    # ── GET APIs ──────────────────────────────────────────────
    def _api_stats(self, _):
        clients  = adm.get("clients", [])
        keys     = adm.get("license_keys", [])
        tickets  = adm.get("tickets", [])
        payments = adm.get("payments", [])
        active   = [c for c in clients if c.get("status") == "active"]
        trial    = [c for c in clients if c.get("status") == "trial"]
        expired  = [c for c in clients if c.get("status") == "expired"]
        suspended= [c for c in clients if c.get("status") == "suspended"]
        mrr      = sum(
            adm.get("admin_settings", {}).get("prices", {}).get(c.get("plan","free"), 0)
            for c in active
        )
        open_tix = [t for t in tickets if t.get("status") == "open"]
        self._json({
            "total_clients":  len(clients),
            "active":         len(active),
            "trial":          len(trial),
            "expired":        len(expired),
            "suspended":      len(suspended),
            "mrr":            mrr,
            "total_keys":     len(keys),
            "open_tickets":   len(open_tix),
            "total_payments": sum(p.get("amount", 0) for p in payments),
        })

    def _api_clients(self, _):
        self._json({"clients": adm.get("clients", [])})

    def _api_keys(self, _):
        self._json({"keys": adm.get("license_keys", [])})

    def _api_tickets(self, _):
        self._json({"tickets": adm.get("tickets", [])})

    def _api_payments(self, _):
        self._json({"payments": adm.get("payments", [])})

    def _api_settings(self, _):
        self._json({"settings": adm.get("admin_settings", {})})

    # ── Clients ───────────────────────────────────────────────
    def _p_client_add(self, b):
        name = b.get("name", "").strip()
        if not name:
            self._json({"ok": False, "error": "أدخل اسم العميل"})
            return
        trial_days = adm.get("admin_settings", {}).get("trial_days", 15)
        client = {
            "id":          _id(),
            "name":        name,
            "hotel_name":  b.get("hotel_name", name),
            "email":       b.get("email", ""),
            "phone":       b.get("phone", ""),
            "city":        b.get("city", ""),
            "hotel_type":  b.get("hotel_type", "hotel"),
            "rooms":       int(b.get("rooms", 0)),
            "plan":        b.get("plan", "trial"),
            "status":      "trial",
            "trial_start": _today(),
            "trial_end":   key_expiry(trial_days),
            "license_key": "",
            "notes":       b.get("notes", ""),
            "created_at":  datetime.now().isoformat(),
            "last_login":  None,
            "custom_settings": {},
            "bank_account": b.get("bank_account", ""),
        }
        adm.append("clients", client)
        logging.info(f"Client added: {name}")
        self._json({"ok": True, "client": client})

    def _p_client_update(self, b):
        cid = b.get("id")
        clients = adm.get("clients", [])
        for c in clients:
            if str(c.get("id")) == str(cid):
                for k in ["name","hotel_name","email","phone","city","hotel_type","rooms","plan","notes","bank_account"]:
                    if k in b: c[k] = b[k]
        adm.set("clients", clients)
        self._json({"ok": True})

    def _p_client_toggle(self, b):
        cid    = b.get("id")
        action = b.get("action", "suspend")  # suspend | activate | expire
        clients = adm.get("clients", [])
        for c in clients:
            if str(c.get("id")) == str(cid):
                if action == "activate":
                    c["status"] = "active"
                elif action == "suspend":
                    c["status"] = "suspended"
                elif action == "expire":
                    c["status"] = "expired"
        adm.set("clients", clients)
        logging.info(f"Client {cid} → {action}")
        self._json({"ok": True})

    def _p_client_extend(self, b):
        cid  = b.get("id")
        days = int(b.get("days", 7))
        clients = adm.get("clients", [])
        for c in clients:
            if str(c.get("id")) == str(cid):
                # Extend from today or from current trial end (whichever is later)
                base_str = c.get("trial_end", _today())
                try:
                    base = date.fromisoformat(base_str)
                    if base < date.today():
                        base = date.today()
                except:
                    base = date.today()
                c["trial_end"] = (base + timedelta(days=days)).isoformat()
                c["status"]    = "trial" if c["status"] in ("expired","trial") else c["status"]
        adm.set("clients", clients)
        logging.info(f"Client {cid} extended by {days} days")
        self._json({"ok": True})

    def _p_client_delete(self, b):
        cid = b.get("id")
        clients = [c for c in adm.get("clients", []) if str(c.get("id")) != str(cid)]
        adm.set("clients", clients)
        self._json({"ok": True})

    def _p_client_settings(self, b):
        """تعديل إعدادات لوحة العميل من لوحة المالك"""
        cid      = b.get("id")
        settings = b.get("settings", {})
        clients  = adm.get("clients", [])
        for c in clients:
            if str(c.get("id")) == str(cid):
                c["custom_settings"] = settings
        adm.set("clients", clients)
        self._json({"ok": True})

    # ── License Keys ──────────────────────────────────────────
    def _p_key_generate(self, b):
        plan   = b.get("plan", "pro")
        days   = int(b.get("days", 30))
        count  = int(b.get("count", 1))
        cid    = b.get("client_id", None)
        keys_generated = []
        for _ in range(min(count, 20)):
            k = {
                "id":         _id(),
                "key":        gen_key(plan),
                "plan":       plan,
                "days":       days,
                "status":     "unused",
                "created_at": datetime.now().isoformat(),
                "expires_at": key_expiry(days),
                "client_id":  cid,
                "client_name": "",
                "used_at":    None,
                "notes":      b.get("notes", ""),
            }
            if cid:
                clients = adm.get("clients", [])
                client  = next((c for c in clients if str(c.get("id")) == str(cid)), None)
                if client:
                    k["client_name"] = client["name"]
                    client["license_key"] = k["key"]
                    client["plan"]   = plan
                    client["status"] = "active"
                    client["trial_end"] = k["expires_at"]
                    adm.set("clients", clients)
            adm.append("license_keys", k)
            keys_generated.append(k)
        logging.info(f"Generated {count} keys for plan={plan}")
        self._json({"ok": True, "keys": keys_generated})

    def _p_key_revoke(self, b):
        kid  = b.get("id")
        keys = adm.get("license_keys", [])
        for k in keys:
            if str(k.get("id")) == str(kid):
                k["status"] = "revoked"
        adm.set("license_keys", keys)
        self._json({"ok": True})

    def _p_key_assign(self, b):
        kid = b.get("key_id")
        cid = b.get("client_id")
        keys    = adm.get("license_keys", [])
        clients = adm.get("clients", [])
        key_obj = next((k for k in keys if str(k.get("id")) == str(kid)), None)
        client  = next((c for c in clients if str(c.get("id")) == str(cid)), None)
        if key_obj and client:
            key_obj["client_id"]   = cid
            key_obj["client_name"] = client["name"]
            key_obj["status"]      = "assigned"
            client["license_key"]  = key_obj["key"]
            client["plan"]         = key_obj["plan"]
            client["status"]       = "active"
            client["trial_end"]    = key_obj["expires_at"]
            adm.set("license_keys", keys)
            adm.set("clients", clients)
        self._json({"ok": True})

    # ── Tickets ───────────────────────────────────────────────
    def _p_ticket_add(self, b):
        """فتح تذكرة من لوحة المالك (للتواصل مع عميل)"""
        t = {
            "id":          _id(),
            "title":       b.get("title", "تذكرة جديدة"),
            "client_id":   b.get("client_id", ""),
            "client_name": b.get("client_name", ""),
            "priority":    b.get("priority", "normal"),
            "status":      "open",
            "created_at":  datetime.now().isoformat(),
            "messages":    [{
                "from": "admin", "name": "الدعم الفني",
                "text": b.get("message", ""),
                "time": datetime.now().isoformat(),
            }],
            "category":    b.get("category", "support"),
        }
        adm.append("tickets", t)
        self._json({"ok": True, "ticket": t})

    def _p_ticket_reply(self, b):
        tid   = b.get("id")
        text  = b.get("text", "").strip()
        if not text:
            self._json({"ok": False, "error": "أدخل الرد"})
            return
        tickets = adm.get("tickets", [])
        for t in tickets:
            if str(t.get("id")) == str(tid):
                t.setdefault("messages", []).append({
                    "from": "admin", "name": "الدعم الفني",
                    "text": text, "time": datetime.now().isoformat(),
                })
                t["status"] = "replied"
        adm.set("tickets", tickets)
        self._json({"ok": True})

    def _p_ticket_close(self, b):
        tid = b.get("id")
        tickets = adm.get("tickets", [])
        for t in tickets:
            if str(t.get("id")) == str(tid):
                t["status"] = "closed"
                t["closed_at"] = datetime.now().isoformat()
        adm.set("tickets", tickets)
        self._json({"ok": True})

    # ── Payments ──────────────────────────────────────────────
    def _p_payment_add(self, b):
        p = {
            "id":          _id(),
            "client_id":   b.get("client_id", ""),
            "client_name": b.get("client_name", ""),
            "amount":      float(b.get("amount", 0)),
            "plan":        b.get("plan", "pro"),
            "method":      b.get("method", "transfer"),
            "ref":         b.get("ref", ""),
            "date":        b.get("date", _today()),
            "notes":       b.get("notes", ""),
            "status":      "confirmed",
        }
        adm.append("payments", p)
        # Auto-generate key if amount matches plan price
        prices = adm.get("admin_settings", {}).get("prices", {})
        plan_price = prices.get(b.get("plan","pro"), 0)
        if p["amount"] >= plan_price and plan_price > 0:
            days = 30
            k_body = {"plan": b.get("plan","pro"), "days": days, "count": 1, "client_id": b.get("client_id",""), "notes": f"تلقائي — دفع {p['amount']} ر.س"}
            self._p_key_generate(k_body)
        self._json({"ok": True, "payment": p})

    # ── Settings ──────────────────────────────────────────────
    def _p_settings_save(self, b):
        s = adm.get("admin_settings", {})
        for k in ["owner_name","owner_email","owner_phone","owner_whatsapp","contact_message","system_name","bank_iban","bank_name","trial_days","prices","plans","ai_market_competitors"]:
            if k in b: s[k] = b[k]
        adm.set("admin_settings", s)
        self._json({"ok": True})


# ══════════════════════════════════════════════════════════════
#  صفحة تسجيل الدخول
# ══════════════════════════════════════════════════════════════
    def _api_plans(self, _):
        s = adm.get("admin_settings", {})
        self._json({"plans": s.get("plans", []), "prices": s.get("prices", {})})

    def _api_admin_market(self, _):
        s = adm.get("admin_settings", {})
        self._json({
            "competitors": s.get("ai_market_competitors", []),
            "last_analysis": s.get("last_market_analysis", None),
        })

    def _p_admin_market_ai(self, b):
        """تحليل السوق بالذكاء الاصطناعي — يبحث عن المنافسين وأسعار السوق"""
        import urllib.request as ur, re as re_mod
        s          = adm.get("admin_settings", {})
        claude_key = b.get("claude_key", s.get("claude_key", ""))
        service    = b.get("service", "hotel management software")
        city       = b.get("city", "Saudi Arabia")

        if not claude_key:
            # Return built-in competitor data
            result = {
                "ok": True, "source": "builtin",
                "competitors": [
                    {"name":"Opera Cloud (Oracle)","price_from":500,"price_to":2000,"currency":"USD/month","target":"فنادق كبرى وسلاسل","strengths":["عالمي الانتشار","تكامل كامل","موثوقية عالية"],"weaknesses":["غالٍ جداً","معقد للإعداد","يحتاج تدريب مطوّل"],"market":"enterprise"},
                    {"name":"Cloudbeds","price_from":200,"price_to":800,"currency":"USD/month","target":"فنادق مستقلة","strengths":["سهل الاستخدام","واجهة جميلة","API قوي"],"weaknesses":["بالإنجليزية","لا يدعم العربية","دفع بالدولار"],"market":"mid"},
                    {"name":"Mews","price_from":250,"price_to":900,"currency":"USD/month","target":"فنادق بوتيك","strengths":["عصري","أتمتة عالية","POS مدمج"],"weaknesses":["ليس عربي","غير متوفر سعودي","دعم محدود للمنطقة"],"market":"mid"},
                    {"name":"Hotelogix","price_from":50,"price_to":200,"currency":"USD/month","target":"فنادق صغيرة","strengths":["رخيص نسبياً","سحابي","يدعم عدة لغات"],"weaknesses":["واجهة قديمة","دعم عربي محدود","تقارير بسيطة"],"market":"budget"},
                    {"name":"Odoo Hospitality","price_from":0,"price_to":300,"currency":"USD/month","target":"فنادق صغيرة ومتوسطة","strengths":["مفتوح المصدر","مرن","رخيص"],"weaknesses":["يحتاج تقنيين","إعداد معقد","دعم عربي ضعيف"],"market":"budget"},
                ],
                "our_advantage": [
                    "🇸🇦 الوحيد بالعربية الكاملة مع دعم السوق السعودي",
                    "💰 أرخص بـ 70% من Opera و Cloudbeds",
                    "📊 مقارنة السوق السعودي بالمواسم (رمضان، حج، F1...)",
                    "🔑 يعمل بدون إنترنت على ويندوز",
                    "⚡ إعداد في 10 دقائق — لا تدريب",
                    "🤝 دعم عربي مباشر",
                ],
                "market_gap": "لا يوجد نظام سعودي عربي كامل بسعر معقول للفنادق الصغيرة والمتوسطة",
                "price_positioning": "299 ر.س/شهر — أقل من 20% من تكلفة Opera Cloud",
            }
        else:
            try:
                prompt = f"""أنت خبير في سوق برمجيات إدارة الفنادق في السعودية والخليج.

ابحث عن المنافسين الرئيسيين لنظام إدارة فندق عربي يستهدف السوق السعودي.
السعر المستهدف: 299-799 ريال/شهر.

قدم JSON فقط:
{{
  "competitors": [
    {{"name":"","price_from":0,"price_to":0,"currency":"","target":"","strengths":[],"weaknesses":[],"market":"enterprise|mid|budget"}},
  ],
  "our_advantage": [],
  "market_gap": "",
  "price_positioning": "",
  "source": "web_search+claude"
}}"""
                payload = json.dumps({
                    "model": "claude-opus-4-5",
                    "max_tokens": 1500,
                    "tools": [{"type": "web_search_20250305", "name": "web_search"}],
                    "messages": [{"role":"user","content": prompt}]
                }).encode()
                req = ur.Request(
                    "https://api.anthropic.com/v1/messages",
                    data=payload,
                    headers={"Content-Type":"application/json","anthropic-version":"2023-06-01","x-api-key":claude_key},
                    method="POST"
                )
                resp = ur.urlopen(req, timeout=30)
                data = json.loads(resp.read())
                text = " ".join(block.get("text","") for block in data.get("content",[]) if block.get("type")=="text")
                m = re_mod.search(r'\{.*\}', text, re_mod.DOTALL)
                result = json.loads(m.group(0)) if m else {}
                result["ok"] = True
            except Exception as e:
                logging.error(f"AI market error: {e}")
                result = {"ok": False, "error": str(e)}

        # Save to settings
        if result.get("ok"):
            s["ai_market_competitors"] = result.get("competitors", [])
            s["last_market_analysis"]  = {
                "date": datetime.now().isoformat(),
                "advantage": result.get("our_advantage",[]),
                "gap": result.get("market_gap",""),
                "positioning": result.get("price_positioning",""),
            }
            adm.set("admin_settings", s)
        self._json(result)

    def _p_competitor_add(self, b):
        s = adm.get("admin_settings", {})
        comps = s.get("ai_market_competitors", [])
        comps.append({
            "name":       b.get("name",""),
            "price_from": float(b.get("price_from",0)),
            "price_to":   float(b.get("price_to",0)),
            "currency":   b.get("currency","ر.س"),
            "target":     b.get("target",""),
            "strengths":  b.get("strengths",[]),
            "weaknesses": b.get("weaknesses",[]),
            "market":     b.get("market","mid"),
        })
        s["ai_market_competitors"] = comps
        adm.set("admin_settings", s)
        self._json({"ok": True})

    def _p_competitor_del(self, b):
        s = adm.get("admin_settings", {})
        idx = b.get("index", -1)
        comps = s.get("ai_market_competitors", [])
        if 0 <= idx < len(comps):
            comps.pop(idx)
        s["ai_market_competitors"] = comps
        adm.set("admin_settings", s)
        self._json({"ok": True})


    def _api_branches(self, b):
        """قائمة فروع عميل معين"""
        cid     = b.query.split("client_id=")[-1].split("&")[0] if hasattr(b,'query') else ""
        clients = adm.get("clients", [])
        if cid:
            branches = [c for c in clients if str(c.get("parent_id","")) == str(cid)]
        else:
            branches = [c for c in clients if c.get("parent_id")]
        self._json({"branches": branches})

    def _p_branch_add(self, b):
        """إضافة حساب فرعي مرتبط بعميل رئيسي"""
        parent_id   = b.get("parent_id")
        parent_name = b.get("parent_name","")
        name        = b.get("name","").strip()
        if not name or not parent_id:
            self._json({"ok": False, "error": "أدخل اسم الفرع وحدد الحساب الرئيسي"}); return
        clients = adm.get("clients", [])
        parent  = next((c for c in clients if str(c.get("id")) == str(parent_id)), None)
        if not parent:
            self._json({"ok": False, "error": "الحساب الرئيسي غير موجود"}); return
        trial_days = adm.get("admin_settings", {}).get("trial_days", 15)
        branch = {
            "id":          _id(),
            "name":        name,
            "hotel_name":  b.get("hotel_name", name),
            "email":       b.get("email", ""),
            "phone":       b.get("phone", ""),
            "city":        b.get("city", parent.get("city","")),
            "hotel_type":  b.get("hotel_type", parent.get("hotel_type","hotel")),
            "rooms":       int(b.get("rooms", 0)),
            "plan":        parent.get("plan","trial"),
            "status":      "active" if parent.get("status")=="active" else "trial",
            "trial_start": _today(),
            "trial_end":   parent.get("trial_end", key_expiry(trial_days)),
            "license_key": parent.get("license_key",""),
            "parent_id":   str(parent_id),
            "parent_name": parent.get("hotel_name", parent_name),
            "is_branch":   True,
            "notes":       b.get("notes",""),
            "created_at":  _iso(),
            "last_login":  None,
            "custom_settings": {},
        }
        adm.append("clients", branch)
        # Update parent branches list
        if "branches" not in parent: parent["branches"] = []
        parent["branches"].append(str(branch["id"]))
        adm.set("clients", clients)
        log_entry = {"id":_id(),"time":_now(),"action":"branch_added","branch_id":branch["id"],"branch_name":name,"parent_id":parent_id}
        logging.info(f"Branch added: {name} → parent {parent_id}")
        self._json({"ok": True, "branch": branch})

    def _p_branch_del(self, b):
        bid = b.get("id")
        clients = adm.get("clients", [])
        branch  = next((c for c in clients if str(c.get("id"))==str(bid) and c.get("is_branch")), None)
        if not branch:
            self._json({"ok": False, "error": "الفرع غير موجود"}); return
        # Remove from parent
        parent = next((c for c in clients if str(c.get("id"))==str(branch.get("parent_id",""))), None)
        if parent and "branches" in parent:
            parent["branches"] = [x for x in parent["branches"] if str(x)!=str(bid)]
        clients = [c for c in clients if str(c.get("id"))!=str(bid)]
        adm.set("clients", clients)
        self._json({"ok": True})

    def _p_plan_add(self, b):
        """إضافة خطة تسعير جديدة"""
        s     = adm.get("admin_settings", {})
        plans = s.get("plans", [])
        new_plan = {
            "id":           f"custom_{_id()}",
            "name":         b.get("name","خطة جديدة"),
            "price":        float(b.get("price",0)),
            "period":       b.get("period","شهري"),
            "color":        b.get("color","#0F6E56"),
            "badge":        b.get("badge",""),
            "branch_fee":   float(b.get("branch_fee",0)),
            "branch_enabled": b.get("branch_enabled",False),
            "pos_devices":  int(b.get("pos_devices",1)),
            "max_guests":   int(b.get("max_guests",0)),
            "features":     b.get("features",[]),
            "excluded":     b.get("excluded",[]),
            "discount_quarterly": float(b.get("discount_quarterly",10)),
            "discount_annual":    float(b.get("discount_annual",20)),
        }
        plans.append(new_plan)
        s["plans"] = plans
        s.setdefault("prices",{})[new_plan["id"]] = new_plan["price"]
        adm.set("admin_settings", s)
        self._json({"ok": True, "plan": new_plan})

    def _p_plan_del(self, b):
        pid   = b.get("id")
        s     = adm.get("admin_settings", {})
        plans = [p for p in s.get("plans",[]) if p.get("id") != pid]
        s["plans"] = plans
        s.get("prices",{}).pop(pid, None)
        adm.set("admin_settings", s)
        self._json({"ok": True})

    def _p_plan_dup(self, b):
        """نسخ خطة موجودة"""
        pid   = b.get("id")
        s     = adm.get("admin_settings", {})
        plans = s.get("plans", [])
        orig  = next((p for p in plans if p.get("id")==pid), None)
        if not orig:
            self._json({"ok":False,"error":"الخطة غير موجودة"}); return
        import copy
        dup = copy.deepcopy(orig)
        dup["id"]   = f"custom_{_id()}"
        dup["name"] = orig["name"] + " — نسخة"
        plans.append(dup)


def _build_login_html():
    return """<!DOCTYPE html>
<html lang="ar" dir="rtl">
<head>
<meta charset="UTF-8"/>
<meta name="viewport" content="width=device-width,initial-scale=1"/>
<title>دخول المالك — Admin</title>
<style>
*{box-sizing:border-box;margin:0;padding:0;font-family:system-ui,Arial,sans-serif;direction:rtl;}
body{background:linear-gradient(135deg,#0F172A,#1E293B);min-height:100vh;display:flex;align-items:center;justify-content:center;}
.card{background:#fff;border-radius:16px;padding:40px;width:340px;box-shadow:0 20px 60px rgba(0,0,0,.3);}
.logo{text-align:center;margin-bottom:28px;}
.logo-icon{font-size:40px;margin-bottom:8px;}
.logo-title{font-size:18px;font-weight:700;color:#0F172A;}
.logo-sub{font-size:12px;color:#64748B;margin-top:2px;}
.fg{margin-bottom:14px;}
.fg label{font-size:11px;font-weight:600;color:#64748B;display:block;margin-bottom:5px;}
.fg input{width:100%;border:1.5px solid #E2E8F0;border-radius:8px;padding:10px 12px;font-size:13px;transition:border-color .15s;}
.fg input:focus{outline:none;border-color:#1A56DB;}
.btn{width:100%;padding:11px;background:linear-gradient(135deg,#1A56DB,#7C3AED);color:#fff;border:none;border-radius:9px;font-size:13px;font-weight:700;cursor:pointer;transition:opacity .15s;}
.btn:hover{opacity:.88;}
.err{color:#DC2626;font-size:11px;margin-top:8px;text-align:center;display:none;}
.shield{font-size:11px;color:#94A3B8;text-align:center;margin-top:14px;}
</style>
</head>
<body>
<div class="card">
  <div class="logo">
    <div class="logo-icon">🔐</div>
    <div class="logo-title">لوحة تحكم المالك</div>
    <div class="logo-sub">Admin Panel — للمالك فقط</div>
  </div>
  <div class="fg"><label>كلمة المرور</label><input type="password" id="pw" placeholder="••••••••••" onkeydown="if(event.key==='Enter')login()"/></div>
  <button class="btn" onclick="login()">دخول</button>
  <div class="err" id="err">كلمة المرور خاطئة — حاول مرة أخرى</div>
  <div class="shield">🔒 جلسة مشفرة — تنتهي بعد 12 ساعة</div>
</div>
<script>
async function login(){
  const pw=document.getElementById('pw').value;
  const r=await fetch('/api/admin/login',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({password:pw})});
  const d=await r.json();
  if(d.ok)location.reload();
  else{document.getElementById('err').style.display='block';document.getElementById('pw').value='';}
}
</script>
</body>
</html>"""


# ══════════════════════════════════════════════════════════════
#  لوحة التحكم الرئيسية للمالك
# ══════════════════════════════════════════════════════════════

def _build_admin_html():
    return r"""<!DOCTYPE html>
<html lang="ar" dir="rtl">
<head>
<meta charset="UTF-8"/>
<meta name="viewport" content="width=device-width,initial-scale=1"/>
<title>Hotel Admin v4 — لوحة التحكم</title>
<style>
*{box-sizing:border-box;margin:0;padding:0;font-family:system-ui,'Segoe UI',Arial,sans-serif;direction:rtl;}
:root{
  --p:#185FA5;--pl:#E6F1FB;--pd:#0C447C;
  --g:#3B6D11;--gl:#EAF3DE;--gd:#27500A;
  --r:#A32D2D;--rl:#FCEBEB;--rd:#791F1F;
  --a:#854F0B;--al:#FAEEDA;--ad:#633806;
  --u:#534AB7;--ul:#EEEDFE;--ud:#3C3489;
  --t:#0F6E56;--tl:#E1F5EE;--td:#085041;
  --c:#993C1D;--cl:#FAECE7;--cd:#712B13;
  --bg:#F1F5F9;--card:#fff;--border:#E2E8F0;--text:#0F172A;--muted:#64748B;
  --sbg:#0F172A;--sbg2:#1E293B;
}
html,body{height:100%;overflow:hidden;background:var(--bg);}
.app{display:grid;grid-template-columns:220px 1fr;height:100vh;}

/* ── SIDEBAR ── */
.sb{background:var(--sbg);display:flex;flex-direction:column;height:100vh;overflow-y:auto;}
.sb-top{padding:16px 14px;border-bottom:1px solid rgba(255,255,255,.07);}
.sb-brand{display:flex;align-items:center;gap:10px;margin-bottom:12px;}
.sb-logo{width:34px;height:34px;border-radius:10px;background:linear-gradient(135deg,#185FA5,#534AB7);display:flex;align-items:center;justify-content:center;font-size:16px;font-weight:700;color:#fff;flex-shrink:0;}
.sb-name{font-size:14px;font-weight:700;color:#F8FAFC;letter-spacing:-.3px;}
.sb-ver{font-size:9px;color:rgba(255,255,255,.3);margin-top:1px;letter-spacing:.5px;}
.status-bar{display:flex;align-items:center;justify-content:space-between;padding:7px 10px;background:rgba(255,255,255,.05);border-radius:8px;}
.status-live{display:flex;align-items:center;gap:5px;}
.status-dot{width:7px;height:7px;border-radius:50%;background:#22C55E;animation:pulse 2s infinite;}
@keyframes pulse{0%,100%{opacity:1}50%{opacity:.4}}
.status-txt{font-size:10px;color:#22C55E;font-weight:600;}
.status-up{font-size:9px;color:rgba(255,255,255,.3);}
.sb-sec{padding:10px 12px 3px;font-size:8px;font-weight:700;color:rgba(255,255,255,.22);letter-spacing:1.2px;text-transform:uppercase;}
.ni{display:flex;align-items:center;gap:8px;padding:8px 12px;cursor:pointer;border-radius:8px;margin:1px 6px;color:rgba(255,255,255,.5);font-size:11px;transition:all .12s;position:relative;}
.ni:hover{background:rgba(255,255,255,.06);color:rgba(255,255,255,.85);}
.ni.on{background:linear-gradient(135deg,rgba(24,95,165,.75),rgba(83,74,183,.55));color:#fff;box-shadow:0 2px 8px rgba(24,95,165,.25);}
.ni-ic{font-size:14px;width:20px;text-align:center;flex-shrink:0;}
.nb{margin-right:auto;background:#A32D2D;color:#fff;font-size:8px;padding:1px 6px;border-radius:10px;font-weight:700;}
.nb-g{background:#3B6D11!important;}
.sb-foot{margin-top:auto;padding:12px 14px;border-top:1px solid rgba(255,255,255,.06);}
.sb-user{display:flex;align-items:center;gap:8px;}
.sb-av{width:30px;height:30px;border-radius:50%;background:linear-gradient(135deg,#185FA5,#534AB7);display:flex;align-items:center;justify-content:center;font-size:13px;color:#fff;font-weight:700;flex-shrink:0;}
.sb-info{flex:1;min-width:0;}
.sb-uname{font-size:11px;font-weight:600;color:#F8FAFC;}
.sb-urole{font-size:9px;color:rgba(255,255,255,.3);margin-top:1px;}
.logout-btn{width:24px;height:24px;display:flex;align-items:center;justify-content:center;border-radius:6px;cursor:pointer;color:rgba(255,255,255,.35);font-size:13px;border:none;background:none;}
.logout-btn:hover{background:rgba(255,255,255,.07);color:rgba(255,255,255,.7);}

/* ── MAIN ── */
.main{display:flex;flex-direction:column;height:100vh;overflow:hidden;}
.topbar{background:var(--card);padding:10px 18px;border-bottom:1px solid var(--border);display:flex;align-items:center;justify-content:space-between;gap:8px;flex-shrink:0;box-shadow:0 1px 3px rgba(0,0,0,.04);}
.tb-left{display:flex;align-items:center;gap:10px;}
.tb-page-ic{width:32px;height:32px;border-radius:9px;display:flex;align-items:center;justify-content:center;font-size:16px;flex-shrink:0;}
.tb-title{font-size:13px;font-weight:700;color:var(--text);}
.tb-right{display:flex;align-items:center;gap:8px;flex-wrap:wrap;}
.tb-date{font-size:10px;color:var(--muted);padding:3px 10px;border-radius:20px;background:var(--bg);border:0.5px solid var(--border);}
.tb-online{font-size:10px;font-weight:700;padding:3px 10px;border-radius:20px;background:var(--gl);color:var(--gd);}
.content{padding:14px;overflow-y:auto;flex:1;}
.pg{display:none;}.pg.on{display:block;}

/* ── METRIC CARDS ── */
.gmc{border-radius:13px;padding:16px 18px;color:#fff;position:relative;overflow:hidden;cursor:default;}
.gmc::before{content:'';position:absolute;top:-20px;right:-20px;width:80px;height:80px;border-radius:50%;background:rgba(255,255,255,.08);}
.gm-ic{font-size:20px;margin-bottom:8px;display:block;}
.gm-val{font-size:24px;font-weight:700;line-height:1;}
.gm-lbl{font-size:10px;font-weight:600;opacity:.8;margin-top:4px;}
.gm-sub{font-size:9px;opacity:.6;margin-top:2px;}
.gm-trend{position:absolute;top:12px;left:12px;font-size:9px;font-weight:700;padding:2px 7px;border-radius:20px;background:rgba(255,255,255,.18);}
.gmc-b{background:linear-gradient(135deg,#185FA5,#378ADD);}
.gmc-g{background:linear-gradient(135deg,#3B6D11,#639922);}
.gmc-u{background:linear-gradient(135deg,#534AB7,#7F77DD);}
.gmc-a{background:linear-gradient(135deg,#854F0B,#BA7517);}
.gmc-r{background:linear-gradient(135deg,#A32D2D,#E24B4A);}
.gmc-t{background:linear-gradient(135deg,#0F6E56,#1D9E75);}
.gmc-pk{background:linear-gradient(135deg,#993556,#D4537E);}
.gmc-dk{background:linear-gradient(135deg,#1E293B,#334155);}
.kg2{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:10px;margin-bottom:10px;}
.kg3{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:10px;margin-bottom:10px;}
.kg4{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:10px;margin-bottom:10px;}

/* ── CARDS ── */
.card{background:var(--card);border:0.5px solid var(--border);border-radius:12px;padding:14px 16px;margin-bottom:10px;box-shadow:0 1px 3px rgba(0,0,0,.03);}
.card.cb{border-top:2px solid var(--p)}.card.cg{border-top:2px solid var(--g)}.card.cr{border-top:2px solid var(--r)}.card.ca{border-top:2px solid var(--a)}.card.cu{border-top:2px solid var(--u)}.card.ct{border-top:2px solid var(--t)}.card.cpk{border-top:2px solid #993556}
.ch{font-size:12px;font-weight:700;color:var(--text);margin-bottom:10px;display:flex;align-items:center;justify-content:space-between;gap:6px;flex-wrap:wrap;}
.ch-l{display:flex;align-items:center;gap:7px;}
.cico{width:26px;height:26px;border-radius:7px;display:flex;align-items:center;justify-content:center;font-size:13px;flex-shrink:0;}
.g2{display:grid;grid-template-columns:1fr 1fr;gap:8px;}
.g3{display:grid;grid-template-columns:1fr 1fr 1fr;gap:8px;}

/* ── TABLE ── */
.tbl{width:100%;border-collapse:collapse;font-size:11px;}
.tbl th{font-size:10px;font-weight:700;color:var(--muted);padding:8px 8px;text-align:right;border-bottom:1.5px solid var(--p);background:var(--bg);white-space:nowrap;}
.tbl td{padding:8px 8px;border-bottom:0.5px solid var(--border);color:var(--text);vertical-align:middle;}
.tbl tbody tr:hover td{background:#F8FBFF;}

/* ── PILLS ── */
.pill{font-size:9px;padding:2px 8px;border-radius:20px;display:inline-block;font-weight:700;white-space:nowrap;}
.p-g{background:var(--gl);color:var(--gd)}.p-r{background:var(--rl);color:var(--rd)}.p-a{background:var(--al);color:var(--ad)}.p-b{background:var(--pl);color:var(--pd)}.p-u{background:var(--ul);color:var(--ud)}.p-n{background:#F1F5F9;color:#475569}

/* ── BUTTONS ── */
.btn{padding:6px 13px;border-radius:8px;font-size:11px;cursor:pointer;border:0.5px solid var(--border);background:var(--card);color:var(--text);font-weight:600;transition:all .12s;}
.btn:hover{opacity:.8;transform:translateY(-1px);}
.bp{background:var(--p)!important;color:#fff!important;border-color:var(--p)!important;}
.bg2{background:var(--g)!important;color:#fff!important;border-color:var(--g)!important;}
.br2{background:var(--r)!important;color:#fff!important;border-color:var(--r)!important;}
.ba2{background:var(--a)!important;color:#fff!important;border-color:var(--a)!important;}
.bu2{background:var(--u)!important;color:#fff!important;border-color:var(--u)!important;}
.sm{padding:3px 9px!important;font-size:10px!important;}

/* ── FORMS ── */
.fg{display:flex;flex-direction:column;gap:3px;margin-bottom:8px;}
.fg label{font-size:10px;color:var(--muted);font-weight:600;}
.fg input,.fg select,.fg textarea{border:0.5px solid var(--border);border-radius:8px;padding:7px 10px;font-size:12px;background:var(--bg);color:var(--text);width:100%;transition:border-color .15s;}
.fg input:focus,.fg select:focus{outline:none;border-color:var(--p);background:var(--card);}
.fg textarea{min-height:70px;resize:vertical;font-family:inherit;}

/* ── AI CONTROL ── */
.ai-bar{background:var(--sbg2);border-radius:12px;padding:14px 16px;margin-bottom:10px;display:flex;align-items:center;gap:10px;flex-wrap:wrap;}
.ai-bar-ic{width:36px;height:36px;border-radius:10px;background:linear-gradient(135deg,#534AB7,#185FA5);display:flex;align-items:center;justify-content:center;font-size:18px;flex-shrink:0;}
.ai-input{flex:1;min-width:200px;border:none;background:rgba(255,255,255,.08);color:#F8FAFC;border-radius:8px;padding:9px 12px;font-size:12px;outline:none;font-family:inherit;}
.ai-input::placeholder{color:rgba(255,255,255,.3);}
.ai-send{padding:8px 16px;background:linear-gradient(135deg,#534AB7,#185FA5);color:#fff;border:none;border-radius:8px;font-size:11px;font-weight:700;cursor:pointer;flex-shrink:0;}
.ai-send:hover{opacity:.85;}
.ai-response{background:rgba(255,255,255,.05);border-radius:8px;padding:10px 12px;font-size:11px;color:rgba(255,255,255,.8);line-height:1.6;margin-top:8px;display:none;}
.ai-response.show{display:block;}

/* ── ONLINE USERS ── */
.online-item{display:flex;align-items:center;gap:8px;padding:7px 0;border-bottom:0.5px solid var(--border);}
.online-item:last-child{border-bottom:none;}
.online-av{width:28px;height:28px;border-radius:50%;display:flex;align-items:center;justify-content:center;font-size:11px;font-weight:700;flex-shrink:0;}
.online-dot{width:6px;height:6px;border-radius:50%;background:#22C55E;flex-shrink:0;}
.online-info{flex:1;min-width:0;}
.online-name{font-size:11px;font-weight:600;color:var(--text);}
.online-meta{font-size:9px;color:var(--muted);margin-top:1px;}

/* ── ANALYTICS BARS ── */
.a-bar-row{display:flex;align-items:center;gap:8px;margin-bottom:5px;}
.a-bar-lbl{font-size:10px;color:var(--muted);min-width:90px;text-align:right;white-space:nowrap;}
.a-bar-track{flex:1;background:var(--bg);border-radius:4px;height:7px;overflow:hidden;border:0.5px solid var(--border);}
.a-bar-fill{height:7px;border-radius:4px;transition:width .5s;}
.a-bar-val{font-size:10px;min-width:40px;text-align:left;color:var(--text);font-weight:600;}

/* ── ACTIVITY FEED ── */
.feed-item{display:flex;align-items:flex-start;gap:8px;padding:6px 0;border-bottom:0.5px solid var(--border);}
.feed-item:last-child{border-bottom:none;}
.feed-dot{width:7px;height:7px;border-radius:50%;flex-shrink:0;margin-top:4px;}
.feed-time{font-size:9px;color:var(--muted);white-space:nowrap;flex-shrink:0;}
.feed-txt{font-size:11px;color:var(--text);flex:1;min-width:0;}

/* ── MODALS ── */
.modal-ov{display:none;position:fixed;inset:0;background:rgba(0,0,0,.45);z-index:1000;align-items:center;justify-content:center;}
.modal-ov.open{display:flex;}
.modal{background:var(--card);border-radius:14px;padding:20px;width:480px;max-width:95vw;max-height:90vh;overflow-y:auto;box-shadow:0 20px 60px rgba(0,0,0,.2);}
.modal-title{font-size:14px;font-weight:700;margin-bottom:14px;display:flex;align-items:center;justify-content:space-between;}
.modal-close{cursor:pointer;color:var(--muted);font-size:18px;}

/* ── TOAST ── */
.toast-wrap{position:fixed;bottom:20px;left:50%;transform:translateX(-50%);z-index:9999;pointer-events:none;}
.toast{background:var(--g);color:#fff;padding:10px 20px;border-radius:10px;font-size:12px;font-weight:700;text-align:center;display:none;box-shadow:0 4px 20px rgba(0,0,0,.2);}
.toast.show{display:block;}

/* ── CHARTS ── */
.mini-chart{display:flex;align-items:flex-end;gap:3px;height:50px;padding-top:5px;}
.mc-bar{flex:1;border-radius:3px 3px 0 0;min-height:4px;transition:height .4s;}

/* ── SCROLLBAR ── */
::-webkit-scrollbar{width:4px;height:4px;}
::-webkit-scrollbar-thumb{background:var(--border);border-radius:4px;}
</style>
</head>
<body>
<div class="app">

<!-- ══ SIDEBAR ══ -->
<div class="sb">
  <div class="sb-top">
    <div class="sb-brand">
      <div class="sb-logo">H</div>
      <div><div class="sb-name" id="sb-sys-name">Hotel Admin</div><div class="sb-ver">VERSION 4.0 — OWNER PANEL</div></div>
    </div>
    <div class="status-bar">
      <div class="status-live"><div class="status-dot"></div><span class="status-txt">LIVE</span></div>
      <span class="status-up" id="sb-uptime">00:00:00</span>
    </div>
  </div>

  <div class="sb-sec">الرئيسية</div>
  <div class="ni on" onclick="go('dash')"><span class="ni-ic">📊</span>لوحة التحكم</div>
  <div class="ni" onclick="go('analytics')"><span class="ni-ic">📈</span>تحليل البيانات<span class="nb nb-g" id="nb-online" style="display:none">0</span></div>
  <div class="ni" onclick="go('ai')"><span class="ni-ic">🤖</span>تحكم بالذكاء الاصطناعي</div>

  <div class="sb-sec">العملاء</div>
  <div class="ni" onclick="go('clients')"><span class="ni-ic">🏨</span>إدارة العملاء<span class="nb" id="nb-trial" style="display:none">0</span></div>
  <div class="ni" onclick="go('register')"><span class="ni-ic">➕</span>تسجيل عميل</div>
  <div class="ni" onclick="go('branches')"><span class="ni-ic">🏢</span>الفروع</div>

  <div class="sb-sec">الاشتراكات</div>
  <div class="ni" onclick="go('keys')"><span class="ni-ic">🔑</span>إصدار المفاتيح</div>
  <div class="ni" onclick="go('plans')"><span class="ni-ic">💎</span>الباقات والأسعار</div>
  <div class="ni" onclick="go('payments')"><span class="ni-ic">💰</span>المدفوعات</div>

  <div class="sb-sec">التواصل</div>
  <div class="ni" onclick="go('tickets')"><span class="ni-ic">🎫</span>التذاكر<span class="nb" id="nb-tickets" style="display:none">0</span></div>
  <div class="ni" onclick="go('push')"><span class="ni-ic">📢</span>إشعارات للعملاء</div>

  <div class="sb-sec">السوق</div>
  <div class="ni" onclick="go('market')"><span class="ni-ic">🌐</span>تحليل السوق AI</div>
  <div class="ni" onclick="go('plans')"><span class="ni-ic">📊</span>إدارة الباقات</div>

  <div class="sb-sec">النظام</div>
  <div class="ni" onclick="go('update')"><span class="ni-ic">📤</span>رفع تحديث</div>
  <div class="ni" onclick="go('settings')"><span class="ni-ic">⚙️</span>الإعدادات</div>

  <div class="sb-foot">
    <div class="sb-user">
      <div class="sb-av" id="sb-av">م</div>
      <div class="sb-info">
        <div class="sb-uname" id="sb-owner-name">المالك</div>
        <div class="sb-urole" id="sb-owner-email">admin</div>
      </div>
      <button class="logout-btn" onclick="logout()" title="خروج">⏻</button>
    </div>
  </div>
</div>

<!-- ══ MAIN ══ -->
<div class="main">
  <div class="topbar">
    <div class="tb-left">
      <div class="tb-page-ic" id="tb-ic" style="background:var(--gl)">📊</div>
      <span class="tb-title" id="tb-title">لوحة التحكم</span>
    </div>
    <div class="tb-right">
      <span class="tb-date" id="tb-date"></span>
      <span class="tb-online" id="tb-online">⬤ 0 متصل</span>
      <button class="btn sm bp" id="save-plans-btn" onclick="savePlans()" style="display:none">💾 حفظ الباقات</button>
      <button class="btn sm bp" onclick="refresh()">تحديث</button>
    </div>
  </div>

  <div class="content">
    <div class="toast-wrap"><div class="toast" id="toast"></div></div>

    <!-- ══════ DASHBOARD ══════ -->
    <div class="pg on" id="pg-dash">
      <div class="kg4">
        <div class="gmc gmc-b"><span class="gm-ic">🏨</span><div class="gm-val" id="st-total">0</div><div class="gm-lbl">إجمالي العملاء</div><div class="gm-sub">كل الحسابات</div><div class="gm-trend" id="t-total">—</div></div>
        <div class="gmc gmc-g"><span class="gm-ic">✅</span><div class="gm-val" id="st-active">0</div><div class="gm-lbl">عملاء نشطون</div><div class="gm-sub">اشتراك مدفوع</div><div class="gm-trend" id="t-active">—</div></div>
        <div class="gmc gmc-a"><span class="gm-ic">⏳</span><div class="gm-val" id="st-trial">0</div><div class="gm-lbl">فترة تجربة</div><div class="gm-sub">15 يوم مجاناً</div><div class="gm-trend" id="t-trial">—</div></div>
        <div class="gmc gmc-t"><span class="gm-ic">💰</span><div class="gm-val" id="st-mrr">0</div><div class="gm-lbl">MRR ر.س</div><div class="gm-sub">إيراد شهري</div><div class="gm-trend" id="t-mrr">—</div></div>
      </div>
      <div class="kg4">
        <div class="gmc gmc-u"><span class="gm-ic">🔑</span><div class="gm-val" id="st-keys">0</div><div class="gm-lbl">مفاتيح مُصدرة</div><div class="gm-sub" id="st-keys-sub">—</div></div>
        <div class="gmc gmc-r"><span class="gm-ic">🎫</span><div class="gm-val" id="st-tickets">0</div><div class="gm-lbl">تذاكر مفتوحة</div><div class="gm-sub">تحتاج ردّاً</div></div>
        <div class="gmc gmc-pk"><span class="gm-ic">🟢</span><div class="gm-val" id="st-online">0</div><div class="gm-lbl">متصلون الآن</div><div class="gm-sub">نشطون < 15 دقيقة</div></div>
        <div class="gmc gmc-dk"><span class="gm-ic">⏱️</span><div class="gm-val" id="st-uptime">—</div><div class="gm-lbl">وقت التشغيل</div><div class="gm-sub" id="st-uptime-sub">—</div></div>
      </div>

      <div class="g2">
        <div class="card cg">
          <div class="ch"><div class="ch-l"><div class="cico" style="background:var(--gl);color:var(--g)">📈</div>الإيراد آخر 7 أيام</div></div>
          <div class="mini-chart" id="rev-chart"></div>
          <div style="display:flex;justify-content:space-between;font-size:9px;color:var(--muted);margin-top:5px;" id="rev-chart-lbl"></div>
        </div>
        <div class="card cb">
          <div class="ch"><div class="ch-l"><div class="cico" style="background:var(--pl);color:var(--p)">👥</div>تحويل التجربة → مدفوع</div></div>
          <div style="text-align:center;padding:10px 0;">
            <div style="font-size:32px;font-weight:700;color:var(--p)" id="conv-rate">0%</div>
            <div style="font-size:10px;color:var(--muted);margin-top:4px">من كل 10 تجارب → <span id="conv-paid">0</span> يشتركون</div>
          </div>
          <div id="funnel-mini"></div>
        </div>
      </div>

      <div class="g2">
        <div class="card ca">
          <div class="ch"><div class="ch-l"><div class="cico" style="background:var(--al);color:var(--a)">⏰</div>تنتهي تجربتهم قريباً</div></div>
          <div id="dash-expiring"></div>
        </div>
        <div class="card cr">
          <div class="ch"><div class="ch-l"><div class="cico" style="background:var(--rl);color:var(--r)">🎫</div>تذاكر تحتاج رد</div></div>
          <div id="dash-tickets"></div>
        </div>
      </div>

      <div class="card ct">
        <div class="ch"><div class="ch-l"><div class="cico" style="background:var(--tl);color:var(--t)">🟢</div>المتصلون الآن</div>
          <span id="online-count-lbl" style="font-size:10px;color:var(--muted)">0 مستخدم</span>
        </div>
        <div id="online-list"></div>
      </div>
    </div>

    <!-- ══════ ANALYTICS ══════ -->
    <div class="pg" id="pg-analytics">
      <div class="kg4">
        <div class="gmc gmc-pk"><span class="gm-ic">🟢</span><div class="gm-val" id="an-online">0</div><div class="gm-lbl">متصل الآن</div></div>
        <div class="gmc gmc-b"><span class="gm-ic">⚡</span><div class="gm-val" id="an-actions">0</div><div class="gm-lbl">إجمالي الأحداث</div></div>
        <div class="gmc gmc-r"><span class="gm-ic">⚠️</span><div class="gm-val" id="an-errors">0</div><div class="gm-lbl">أخطاء مسجّلة</div></div>
        <div class="gmc gmc-dk"><span class="gm-ic">⏱️</span><div class="gm-val" id="an-uptime">—</div><div class="gm-lbl">وقت التشغيل</div></div>
      </div>

      <div class="g2">
        <div class="card cb">
          <div class="ch"><div class="ch-l"><div class="cico" style="background:var(--pl);color:var(--p)">📊</div>أكثر الصفحات زيارةً</div>
            <button class="btn sm" onclick="loadAnalytics()">تحديث</button>
          </div>
          <div id="an-pages"></div>
        </div>
        <div class="card cg">
          <div class="ch"><div class="ch-l"><div class="cico" style="background:var(--gl);color:var(--g)">📅</div>نشاط آخر 7 أيام</div></div>
          <div id="an-daily"></div>
        </div>
      </div>

      <div class="card cu">
        <div class="ch"><div class="ch-l"><div class="cico" style="background:var(--ul);color:var(--u)">👥</div>إحصائيات العملاء الفردية</div></div>
        <div style="overflow-x:auto"><table class="tbl">
          <thead><tr><th>العميل</th><th>أيام الاستخدام</th><th>إجمالي الأحداث</th><th>آخر صفحة</th><th>أخطاء</th><th>أول دخول</th><th>الحالة</th></tr></thead>
          <tbody id="an-clients-body"></tbody>
        </table></div>
      </div>

      <div class="card cr">
        <div class="ch"><div class="ch-l"><div class="cico" style="background:var(--rl);color:var(--r)">⚠️</div>سجل الأخطاء</div>
          <button class="btn sm br2" onclick="clearErrors()">مسح</button>
        </div>
        <div id="an-errors-list"></div>
      </div>

      <div class="card ca">
        <div class="ch"><div class="ch-l"><div class="cico" style="background:var(--al);color:var(--a)">⚡</div>سجل الأحداث الأخيرة</div></div>
        <div id="an-feed"></div>
      </div>
    </div>

    <!-- ══════ AI CONTROL ══════ -->
    <div class="pg" id="pg-ai">
      <!-- Control Bar -->
      <div class="ai-bar">
        <div class="ai-bar-ic">🤖</div>
        <div style="flex:1;">
          <div style="font-size:11px;font-weight:700;color:#F8FAFC;margin-bottom:5px;">Claude AI — تحكم بلوحة التحكم بلغتك الطبيعية</div>
          <div style="display:flex;gap:6px;flex-wrap:wrap;">
            <input class="ai-input" id="ai-cmd" placeholder="مثال: مدّد تجربة فندق النخبة أسبوعاً — أو: من العملاء المنتهية تجربتهم؟" onkeydown="if(event.key==='Enter')sendAI()"/>
            <button class="ai-send" id="ai-send-btn" onclick="sendAI()">إرسال ←</button>
          </div>
          <!-- Auto-execute toggle -->
          <div style="display:flex;align-items:center;gap:8px;margin-top:8px;">
            <label style="display:flex;align-items:center;gap:6px;cursor:pointer;font-size:10px;color:rgba(255,255,255,.6);">
              <input type="checkbox" id="ai-auto-exec" style="width:auto;accent-color:#22C55E;"/>
              تنفيذ تلقائي (Claude ينفّذ الأوامر مباشرة بدون تأكيد)
            </label>
            <span id="ai-mode-badge" style="font-size:9px;padding:2px 7px;border-radius:20px;background:rgba(255,255,255,.1);color:rgba(255,255,255,.5)">مراجعة يدوية</span>
          </div>
        </div>
      </div>

      <div class="kg3">
        <!-- Quick commands -->
        <div class="card cb">
          <div class="ch"><div class="ch-l"><div class="cico" style="background:var(--pl);color:var(--p)">⚡</div>أوامر قراءة</div></div>
          <div style="display:flex;flex-direction:column;gap:5px;margin-bottom:10px">
            <button class="btn" onclick="quickAI('ملخص شامل للنظام: عملاء، إيراد، تذاكر، متصلون')">📊 ملخص شامل</button>
            <button class="btn" onclick="quickAI('من العملاء الذين تنتهي تجربتهم خلال 3 أيام؟')">⏰ تجارب تنتهي</button>
            <button class="btn" onclick="quickAI('حلّل الإيرادات والخطط الأكثر اشتراكاً')">💰 تحليل الإيراد</button>
            <button class="btn" onclick="quickAI('هل توجد مشاكل أو أخطاء تحتاج معالجة؟')">🔧 فحص المشاكل</button>
          </div>
          <div style="font-size:10px;font-weight:700;color:var(--muted);margin-bottom:5px">أوامر تنفيذية</div>
          <div style="display:flex;flex-direction:column;gap:5px;">
            <button class="btn" style="border-color:var(--g);color:var(--g)" onclick="quickAI('مدّد تجارب كل العملاء الذين تنتهي تجربتهم خلال 3 أيام — مدّدها أسبوعاً')">✅ تمديد التجارب القريبة</button>
            <button class="btn" style="border-color:var(--p);color:var(--p)" onclick="quickAI('أصدر مفتاح احترافي 30 يوم وعيّنه لأول عميل في قائمة التجارب المنتهية')">🔑 مفتاح تلقائي</button>
            <button class="btn" style="border-color:var(--a);color:var(--a)" onclick="quickAI('أرسل إشعاراً لكل العملاء في فترة التجربة: نذكّرك بأن تجربتك المجانية تقترب من نهايتها — تواصل معنا لتجديد اشتراكك')">📢 إشعار للعملاء</button>
            <button class="btn" style="border-color:var(--r);color:var(--r)" onclick="quickAI('أغلق كل التذاكر التي مضى عليها أكثر من 7 أيام بدون رد')">🎫 إغلاق تذاكر قديمة</button>
          </div>
        </div>

        <!-- Chat -->
        <div class="card" style="border-top:2px solid var(--u);grid-column:span 2;">
          <div class="ch"><div class="ch-l"><div class="cico" style="background:var(--ul);color:var(--u)">💬</div>محادثة + تنفيذ مباشر</div>
            <div style="display:flex;gap:5px;align-items:center">
              <span id="ai-status" style="font-size:10px;color:var(--muted)">جاهز</span>
              <button class="btn sm" onclick="clearChat()">مسح</button>
            </div>
          </div>
          <div id="ai-chat" style="min-height:280px;max-height:380px;overflow-y:auto;display:flex;flex-direction:column;gap:8px;padding:4px"></div>
          <!-- Pending actions -->
          <div id="ai-pending" style="display:none;background:var(--al);border-radius:8px;padding:10px 12px;margin-top:8px;border:1px solid #FCD34D">
            <div style="font-size:11px;font-weight:700;color:var(--ad);margin-bottom:6px">⚡ Claude يقترح تنفيذ هذه الإجراءات:</div>
            <div id="ai-pending-list" style="display:flex;flex-direction:column;gap:5px;margin-bottom:8px"></div>
            <div style="display:flex;gap:6px">
              <button class="btn bg2 sm" onclick="executePending()" style="flex:1">✅ تنفيذ الكل</button>
              <button class="btn br2 sm" onclick="cancelPending()">❌ إلغاء</button>
            </div>
          </div>
          <div style="margin-top:8px;display:flex;gap:6px;">
            <input id="ai-chat-input" placeholder="اكتب أمرك أو سؤالك..." style="flex:1;border:0.5px solid var(--border);border-radius:8px;padding:8px 10px;font-size:12px;background:var(--bg);color:var(--text);" onkeydown="if(event.key==='Enter')sendChat()"/>
            <button class="btn bp" id="chat-send-btn" onclick="sendChat()">إرسال</button>
          </div>
        </div>
      </div>

      <!-- Execution log -->
      <div class="card ca">
        <div class="ch"><div class="ch-l"><div class="cico" style="background:var(--al);color:var(--a)">📋</div>سجل التنفيذ</div>
          <button class="btn sm" onclick="document.getElementById('exec-log').innerHTML=''">مسح</button>
        </div>
        <div id="exec-log" style="max-height:200px;overflow-y:auto;font-size:11px;"></div>
      </div>

      <!-- Settings -->
      <div class="card cu">
        <div class="ch"><div class="ch-l"><div class="cico" style="background:var(--ul);color:var(--u)">🔑</div>إعدادات Claude AI</div></div>
        <div class="g2">
          <div class="fg"><label>Claude API Key <span style="font-size:9px;color:var(--muted)">(من console.anthropic.com)</span></label>
            <div style="display:flex;gap:6px"><input id="ai-key-input" type="password" placeholder="sk-ant-xxxxxxxx" style="flex:1"/><button class="btn sm bp" onclick="saveAIKey()">حفظ</button></div>
          </div>
          <div class="fg"><label>النموذج المستخدم</label>
            <select id="ai-model">
              <option value="claude-opus-4-5">Claude Opus 4.5 — الأقوى</option>
              <option value="claude-sonnet-4-6" selected>Claude Sonnet 4.6 — متوازن</option>
            </select>
          </div>
        </div>
        <div style="background:var(--gl);border-radius:8px;padding:8px 10px;font-size:11px;color:var(--gd)">
          ✓ بدون مفتاح API: ردود ذكية مدمجة للاستفسارات الأساسية<br/>
          ✓ مع مفتاح API: تحليل كامل + تنفيذ ذكي + ردود على التذاكر تلقائياً
        </div>
      </div>
    </div>

    <!-- ══════ PUSH NOTIFICATIONS ══════ -->
    <div class="pg" id="pg-push">
      <div class="card cb">
        <div class="ch"><div class="ch-l"><div class="cico" style="background:var(--pl);color:var(--p)">📢</div>إرسال إشعار لعملائك</div></div>
        <div style="font-size:11px;color:var(--muted);margin-bottom:10px;">الرسالة تظهر في لوحة العميل عند دخوله التالي — يمكنك إرسالها لجميع العملاء أو فئة معينة.</div>
        <div class="fg"><label>الرسالة</label><textarea id="push-msg" placeholder="مثال: تم تحديث النظام — جربوا ميزة تحليل السوق الجديدة!"></textarea></div>
        <div class="fg"><label>المستهدفون</label>
          <select id="push-target">
            <option value="all">جميع العملاء</option>
            <option value="active">العملاء النشطون فقط</option>
            <option value="trial">العملاء في التجربة فقط</option>
          </select>
        </div>
        <button class="btn bp" onclick="sendPush()">إرسال الإشعار للجميع</button>
        <div id="push-result" style="margin-top:8px;font-size:11px;color:var(--g);display:none"></div>
      </div>
    </div>

    <!-- ══════ CLIENTS ══════ -->
    <div class="pg" id="pg-clients">
      <div class="card cb">
        <div class="ch">
          <div class="ch-l"><div class="cico" style="background:var(--pl);color:var(--p)">🏨</div>إدارة العملاء</div>
          <div style="display:flex;gap:6px;flex-wrap:wrap">
            <input id="cl-search" placeholder="🔍 بحث..." style="border:0.5px solid var(--border);border-radius:8px;padding:5px 10px;font-size:11px;background:var(--bg);color:var(--text);width:140px" oninput="filterClients()"/>
            <select id="cl-filter" style="border:0.5px solid var(--border);border-radius:8px;padding:5px 8px;font-size:11px;background:var(--bg);color:var(--text)" onchange="filterClients()">
              <option value="">الكل</option><option value="active">نشط</option><option value="trial">تجربة</option><option value="expired">منتهي</option><option value="suspended">موقوف</option>
            </select>
            <button class="btn bp sm" onclick="go('register')">+ عميل جديد</button>
          </div>
        </div>
        <div style="overflow-x:auto"><table class="tbl">
          <thead><tr><th>العميل</th><th>المدينة</th><th>الخطة</th><th>الحالة</th><th>أيام الاستخدام</th><th>انتهاء التجربة</th><th>الإيراد</th><th>إجراءات</th></tr></thead>
          <tbody id="clients-body"></tbody>
        </table></div>
      </div>
    </div>

    <!-- ══════ REGISTER ══════ -->
    <div class="pg" id="pg-register">
      <div class="card cb">
        <div class="ch"><div class="ch-l"><div class="cico" style="background:var(--pl);color:var(--p)">➕</div>تسجيل عميل جديد</div></div>
        <div class="g2">
          <div class="fg"><label>اسم صاحب الفندق *</label><input id="rg-name" placeholder="محمد عبدالله..."/></div>
          <div class="fg"><label>اسم الفندق / المنشأة *</label><input id="rg-hotel" placeholder="فندق النخبة..."/></div>
          <div class="fg"><label>الإيميل</label><input type="email" id="rg-email" placeholder="contact@hotel.sa"/></div>
          <div class="fg"><label>رقم الجوال</label><input id="rg-phone" placeholder="05xxxxxxxx"/></div>
          <div class="fg"><label>المدينة</label><select id="rg-city"><option value="riyadh">الرياض</option><option value="jeddah">جدة</option><option value="makkah">مكة المكرمة</option><option value="madinah">المدينة المنورة</option><option value="dammam">الدمام</option><option value="khobar">الخبر</option><option value="jubail">الجبيل</option><option value="ahsa">الأحساء</option><option value="abha">أبها</option><option value="taif">الطائف</option><option value="tabuk">تبوك</option><option value="qassim">القصيم</option><option value="hail">حائل</option><option value="bahah">الباحة</option><option value="other">أخرى</option></select></div>
          <div class="fg"><label>نوع المنشأة</label><select id="rg-type"><option value="hotel">فندق</option><option value="apart">شقق فندقية</option><option value="service">شقق مخدومة</option></select></div>
          <div class="fg"><label>عدد الغرف</label><input type="number" id="rg-rooms" placeholder="50" min="1"/></div>
          <div class="fg"><label>الخطة</label><select id="rg-plan"><option value="trial">تجربة 15 يوم</option><option value="pro">احترافية</option><option value="enterprise">مؤسسية</option></select></div>
        </div>
        <div class="fg"><label>ملاحظات</label><textarea id="rg-notes" placeholder="أي ملاحظات..."></textarea></div>
        <button class="btn bg2" onclick="registerClient()" style="width:100%">تسجيل العميل + فتح تذكرة ترحيب</button>
      </div>
    </div>

    <!-- ══════ KEYS ══════ -->
    <div class="pg" id="pg-keys">
      <div class="card cg">
        <div class="ch"><div class="ch-l"><div class="cico" style="background:var(--gl);color:var(--g)">🔑</div>إصدار مفاتيح ترخيص</div></div>
        <div class="g3">
          <div class="fg"><label>الخطة</label><select id="key-plan"><option value="free">مجانية</option><option value="pro" selected>احترافية</option><option value="enterprise">مؤسسية</option></select></div>
          <div class="fg"><label>المدة (يوم)</label><input type="number" id="key-days" value="30" min="1" max="3650"/></div>
          <div class="fg"><label>عدد المفاتيح</label><input type="number" id="key-count" value="1" min="1" max="20"/></div>
          <div class="fg"><label>تعيين لعميل</label><select id="key-client"><option value="">— بدون تعيين —</option></select></div>
          <div class="fg"><label>ملاحظة</label><input id="key-note" placeholder="مثال: ترويجي..."/></div>
        </div>
        <button class="btn bg2" onclick="generateKeys()">🔑 إصدار المفاتيح</button>
        <div id="keys-generated" style="margin-top:10px"></div>
      </div>
      <div class="card cb"><div class="ch"><div class="ch-l"><div class="cico" style="background:var(--pl);color:var(--p)">📋</div>سجل المفاتيح</div></div>
        <div style="overflow-x:auto"><table class="tbl"><thead><tr><th>المفتاح</th><th>الخطة</th><th>العميل</th><th>الانتهاء</th><th>الحالة</th><th></th></tr></thead><tbody id="keys-body"></tbody></table></div>
      </div>
    </div>

    <!-- ══════ PAYMENTS ══════ -->
    <div class="pg" id="pg-payments">
      <div class="kg3">
        <div class="gmc gmc-g"><span class="gm-ic">💰</span><div class="gm-val" id="pay-total">0</div><div class="gm-lbl">إجمالي المقبوضات ر.س</div></div>
        <div class="gmc gmc-b"><span class="gm-ic">📅</span><div class="gm-val" id="pay-mrr">0</div><div class="gm-lbl">MRR الشهري</div></div>
        <div class="gmc gmc-u"><span class="gm-ic">🔢</span><div class="gm-val" id="pay-cnt">0</div><div class="gm-lbl">عدد المعاملات</div></div>
      </div>
      <div class="card cg">
        <div class="ch"><div class="ch-l"><div class="cico" style="background:var(--gl);color:var(--g)">💰</div>تسجيل دفعة</div></div>
        <div class="g3">
          <div class="fg"><label>العميل</label><select id="pay-client"></select></div>
          <div class="fg"><label>المبلغ (ر.س)</label><input type="number" id="pay-amount" placeholder="299"/></div>
          <div class="fg"><label>الخطة</label><select id="pay-plan"><option value="free">مجانية</option><option value="pro">احترافية</option><option value="enterprise">مؤسسية</option></select></div>
          <div class="fg"><label>طريقة الدفع</label><select id="pay-method"><option value="transfer">تحويل بنكي</option><option value="mada">مدى</option><option value="cash">نقداً</option><option value="stc">STC Pay</option></select></div>
          <div class="fg"><label>رقم المرجع</label><input id="pay-ref" placeholder="رقم التحويل..."/></div>
          <div class="fg"><label>التاريخ</label><input type="date" id="pay-date"/></div>
        </div>
        <button class="btn bg2" onclick="addPayment()">تسجيل الدفعة + مفتاح تلقائي</button>
      </div>
      <div class="card cb"><div class="ch"><div class="ch-l"><div class="cico" style="background:var(--pl);color:var(--p)">📋</div>سجل المدفوعات</div></div>
        <div style="overflow-x:auto"><table class="tbl"><thead><tr><th>العميل</th><th>المبلغ</th><th>الخطة</th><th>الطريقة</th><th>المرجع</th><th>التاريخ</th></tr></thead><tbody id="pay-body"></tbody></table></div>
      </div>
    </div>

    <!-- ══════ TICKETS ══════ -->
    <div class="pg" id="pg-tickets">
      <div class="card ca">
        <div class="ch"><div class="ch-l"><div class="cico" style="background:var(--al);color:var(--a)">🎫</div>تذاكر الدعم</div>
          <button class="btn ba2 sm" onclick="openNewTicket()">+ فتح تذكرة</button>
        </div>
        <div id="tickets-list"></div>
      </div>
    </div>

    <!-- ══════ PLANS ══════ -->
    <div class="pg" id="pg-plans">

      <!-- Stats bar -->
      <div class="kg4" id="plans-stats" style="margin-bottom:10px;"></div>

      <!-- Discount bar -->
      <div class="card" style="border-top:2px solid var(--a);margin-bottom:10px;">
        <div class="ch"><div class="ch-l"><div class="cico" style="background:var(--al);color:var(--a)">🏷️</div>خصومات الدفع المسبق — تُطبَّق على جميع الخطط</div></div>
        <div class="g3">
          <div class="fg"><label>خصم ربع سنوي (%)</label><input type="number" id="disc-quarterly" value="10" min="0" max="50" oninput="updateDiscPreview()"/></div>
          <div class="fg"><label>خصم نصف سنوي (%)</label><input type="number" id="disc-semi" value="15" min="0" max="50" oninput="updateDiscPreview()"/></div>
          <div class="fg"><label>خصم سنوي (%)</label><input type="number" id="disc-annual" value="20" min="0" max="50" oninput="updateDiscPreview()"/></div>
        </div>
        <div id="disc-preview" style="font-size:11px;color:var(--muted);background:var(--bg);border-radius:8px;padding:8px 10px;"></div>
      </div>

      <!-- Plans grid — fully customizable -->
      <div id="plans-grid" style="display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:14px;margin-bottom:12px;"></div>

      <!-- Add plan button -->
      <button class="btn bg2" onclick="addNewPlan()" style="width:100%;margin-bottom:10px;">✚ إضافة خطة تسعير جديدة</button>

      <!-- Add plan form -->
      <div class="card cg" id="new-plan-form" style="display:none;">
        <div class="ch"><div class="ch-l"><div class="cico" style="background:var(--gl);color:var(--g)">✨</div>خطة جديدة</div>
          <button class="btn sm br2" onclick="document.getElementById('new-plan-form').style.display='none'">إغلاق</button>
        </div>
        <div class="g3">
          <div class="fg"><label>اسم الخطة *</label><input id="np-name" placeholder="مثال: خطة المجمعات"/></div>
          <div class="fg"><label>السعر الشهري (ر.س)</label><input type="number" id="np-price" placeholder="499" min="0"/></div>
          <div class="fg"><label>لون الخطة</label>
            <div style="display:flex;gap:4px;align-items:center">
              <input type="color" id="np-color-picker" value="#0F6E56" oninput="document.getElementById('np-color').value=this.value" style="width:40px;height:32px;border:none;border-radius:6px;cursor:pointer;padding:2px;"/>
              <input id="np-color" value="#0F6E56" placeholder="#185FA5" style="flex:1;font-family:monospace;" oninput="document.getElementById('np-color-picker').value=this.value"/>
            </div>
          </div>
          <div class="fg"><label>شارة مميزة</label><input id="np-badge" placeholder="الأكثر طلباً / جديد..."/></div>
          <div class="fg"><label>أجهزة نقاط الدفع</label><input type="number" id="np-pos" placeholder="3" min="0" title="0 = غير محدود"/></div>
          <div class="fg"><label>حد النزلاء شهرياً</label><input type="number" id="np-guests" placeholder="0" min="0" title="0 = غير محدود"/></div>
          <div class="fg"><label>رسوم الفرع (ر.س/فرع)</label><input type="number" id="np-branch-fee" value="0" min="0"/></div>
          <div style="display:flex;align-items:center;gap:6px;">
            <input type="checkbox" id="np-branch-en" style="width:auto;accent-color:var(--g)"/>
            <label for="np-branch-en" style="font-size:11px;color:var(--muted);cursor:pointer;">تفعيل الفروع المتعددة</label>
          </div>
        </div>
        <div class="fg"><label>البنود والمميزات (سطر لكل بند)</label>
          <textarea id="np-features" rows="6" style="border:0.5px solid var(--border);border-radius:8px;padding:8px 10px;font-size:12px;background:var(--bg);color:var(--text);width:100%;resize:vertical;font-family:inherit" placeholder="نزلاء غير محدود&#10;حتى 3 أجهزة نقاط دفع&#10;تكامل نظام إدارة واحد&#10;مقارنة أسعار السوق&#10;نسخ احتياطي تلقائي&#10;جميع البيانات والتقارير يتم الاحتفاظ بها لدى العميل&#10;دعم فني 24/7"></textarea>
        </div>
        <div class="fg"><label>بنود غير متضمنة</label>
          <textarea id="np-excluded" rows="3" style="border:0.5px solid var(--border);border-radius:8px;padding:8px 10px;font-size:12px;background:var(--bg);color:var(--text);width:100%;resize:vertical;font-family:inherit" placeholder="فروع متعددة&#10;API مفتوح"></textarea>
        </div>
        <div style="display:flex;gap:8px;">
          <button class="btn bg2" onclick="submitNewPlan()" style="flex:1">إضافة الخطة</button>
          <button class="btn" onclick="document.getElementById('new-plan-form').style.display='none'">إلغاء</button>
        </div>
      </div>

      <!-- Contact info card -->
      <div class="card cg">
        <div class="ch"><div class="ch-l"><div class="cico" style="background:var(--gl);color:var(--g)">📞</div>معلومات التواصل — تظهر عند انتهاء التجربة</div></div>
        <div class="g2">
          <div class="fg"><label>رقم واتساب (مع رمز الدولة)</label><input id="cfg-whatsapp" placeholder="966501234567" style="direction:ltr;font-family:monospace"/></div>
          <div class="fg"><label>رقم الجوال</label><input id="cfg-phone2" placeholder="05xxxxxxxx"/></div>
        </div>
        <div class="fg"><label>رسالة للعميل عند انتهاء التجربة</label>
          <textarea id="cfg-contact-msg" style="border:0.5px solid var(--border);border-radius:8px;padding:8px 10px;font-size:12px;background:var(--bg);color:var(--text);width:100%;resize:vertical;font-family:inherit;min-height:60px" placeholder="لتجديد اشتراكك تواصل معنا عبر واتساب وسنساعدك خلال دقائق."></textarea>
        </div>
        <button class="btn bg2 sm" onclick="saveContactInfo()">حفظ معلومات التواصل</button>
      </div>
    </div>

    <!-- ══════ BRANCHES ══════ -->
    <div class="pg" id="pg-branches">
      <div class="kg4">
        <div class="gmc gmc-b"><span class="gm-ic">🏢</span><div class="gm-val" id="br-total">0</div><div class="gm-lbl">إجمالي الفروع</div></div>
        <div class="gmc gmc-g"><span class="gm-ic">✅</span><div class="gm-val" id="br-active">0</div><div class="gm-lbl">فروع نشطة</div></div>
        <div class="gmc gmc-u"><span class="gm-ic">🌳</span><div class="gm-val" id="br-groups">0</div><div class="gm-lbl">حسابات رئيسية</div></div>
        <div class="gmc gmc-t"><span class="gm-ic">💰</span><div class="gm-val" id="br-mrr">0</div><div class="gm-lbl">إيراد الفروع</div></div>
      </div>
      <div class="card cg">
        <div class="ch"><div class="ch-l"><div class="cico" style="background:var(--gl);color:var(--g)">🏢</div>إضافة فرع</div></div>
        <div class="g3">
          <div class="fg"><label>الحساب الرئيسي</label><select id="br-parent"></select></div>
          <div class="fg"><label>اسم المسؤول</label><input id="br-name" placeholder="أحمد محمد..."/></div>
          <div class="fg"><label>اسم الفرع</label><input id="br-hotel" placeholder="فندق النخبة — فرع جدة"/></div>
          <div class="fg"><label>الإيميل</label><input type="email" id="br-email" placeholder="branch@hotel.sa"/></div>
          <div class="fg"><label>المدينة</label><select id="br-city"><option value="riyadh">الرياض</option><option value="jeddah">جدة</option><option value="makkah">مكة المكرمة</option><option value="madinah">المدينة المنورة</option><option value="dammam">الدمام</option><option value="khobar">الخبر</option><option value="jubail">الجبيل</option><option value="ahsa">الأحساء</option><option value="abha">أبها</option><option value="taif">الطائف</option><option value="tabuk">تبوك</option><option value="qassim">القصيم</option><option value="hail">حائل</option><option value="bahah">الباحة</option><option value="other">أخرى</option></select></div>
          <div class="fg"><label>عدد الوحدات</label><input type="number" id="br-rooms" placeholder="30" min="1"/></div>
        </div>
        <button class="btn bg2" onclick="addBranch()">إضافة + ربط بالحساب الرئيسي</button>
      </div>
      <div class="card cb"><div class="ch"><div class="ch-l"><div class="cico" style="background:var(--pl);color:var(--p)">🌳</div>شجرة الحسابات</div><button class="btn sm" onclick="rBranches()">تحديث</button></div><div id="branches-tree"></div></div>
    </div>

    <!-- ══════ MARKET ══════ -->
    <div class="pg" id="pg-market">
      <div class="card" style="border-top:2px solid var(--u)">
        <div class="ch"><div class="ch-l"><div class="cico" style="background:var(--ul);color:var(--u)">🤖</div>تحليل السوق بالذكاء الاصطناعي</div>
          <button class="btn bu2" id="ai-analyze-btn" onclick="runMarketAI()">🔍 تحليل الآن</button>
        </div>
        <div class="fg" style="max-width:350px"><label>Claude API Key</label>
          <div style="display:flex;gap:6px"><input id="mkt-claude-key" type="password" placeholder="sk-ant-xxxxxxxx" style="flex:1"/><button class="btn sm bp" onclick="saveClaudeKey()">حفظ</button></div>
        </div>
        <div id="mkt-ai-result" style="margin-top:8px"></div>
      </div>
      <div class="card cb"><div class="ch"><div class="ch-l"><div class="cico" style="background:var(--pl);color:var(--p)">🏆</div>المنافسون</div><button class="btn bp sm" onclick="toggleAddComp()">+ إضافة</button></div>
        <div id="add-comp-form" style="display:none;background:var(--bg);border-radius:10px;padding:12px;margin-bottom:10px;border:0.5px solid var(--p)">
          <div class="g3">
            <div class="fg"><label>الاسم</label><input id="comp-name" placeholder="Opera Cloud"/></div>
            <div class="fg"><label>السعر من</label><input type="number" id="comp-pfrom" placeholder="0"/></div>
            <div class="fg"><label>السعر إلى</label><input type="number" id="comp-pto" placeholder="0"/></div>
            <div class="fg"><label>العملة</label><input id="comp-curr" placeholder="USD/month" value="USD/month"/></div>
            <div class="fg"><label>الفئة</label><input id="comp-target" placeholder="فنادق كبرى"/></div>
            <div class="fg"><label>الشريحة</label><select id="comp-market"><option value="enterprise">Enterprise</option><option value="mid" selected>Mid Market</option><option value="budget">Budget</option></select></div>
          </div>
          <div class="g2">
            <div class="fg"><label>نقاط القوة (بفاصلة)</label><input id="comp-str" placeholder="سهل, دعم قوي"/></div>
            <div class="fg"><label>نقاط الضعف (بفاصلة)</label><input id="comp-wk" placeholder="غالٍ, بالإنجليزية"/></div>
          </div>
          <div style="display:flex;gap:6px"><button class="btn bp" onclick="addCompetitor()" style="flex:1">إضافة</button><button class="btn sm" onclick="toggleAddComp()">إلغاء</button></div>
        </div>
        <div id="competitors-list"></div>
      </div>
      <div class="card cg" id="our-advantage-card" style="display:none"><div class="ch"><div class="ch-l"><div class="cico" style="background:var(--gl);color:var(--g)">⭐</div>مزايانا التنافسية</div></div><div id="our-advantages"></div></div>
    </div>

    <!-- ══════ UPDATE UPLOAD ══════ -->
    <div class="pg" id="pg-update">
      <div class="card" style="border-top:2px solid var(--u)">
        <div class="ch"><div class="ch-l"><div class="cico" style="background:var(--ul);color:var(--u)">📤</div>رفع تحديث لنظام إدارة الفنادق</div></div>
        <div style="background:var(--gl);border-radius:8px;padding:10px 12px;margin-bottom:12px;font-size:11px;color:var(--gd);">
          ✅ ارفع ملف Python محدّث — يتم فحصه تلقائياً قبل التثبيت<br/>
          ✅ يُحفظ نسخة احتياطية من الملف القديم تلقائياً<br/>
          ✅ الملفات المدعومة: <code style="background:var(--bg);padding:1px 5px;border-radius:4px;font-size:10px;">main.py — main_admin.py — unified_server.py</code>
        </div>
        <!-- Upload zone -->
        <div id="upload-zone" style="border:2px dashed var(--border);border-radius:12px;padding:30px;text-align:center;cursor:pointer;transition:all .2s;margin-bottom:12px;"
          onclick="document.getElementById('file-input').click()"
          ondragover="event.preventDefault();this.style.borderColor='var(--p)';this.style.background='var(--pl)'"
          ondragleave="this.style.borderColor='var(--border)';this.style.background=''"
          ondrop="event.preventDefault();this.style.borderColor='var(--border)';this.style.background='';handleFileDrop(event)">
          <div style="font-size:32px;margin-bottom:8px;">📂</div>
          <div style="font-size:13px;font-weight:500;color:var(--text);margin-bottom:4px;">اسحب الملف هنا أو اضغط للاختيار</div>
          <div style="font-size:11px;color:var(--muted);">ملفات Python فقط (.py) — يتم فحص الصياغة قبل الرفع</div>
          <input type="file" id="file-input" accept=".py" style="display:none" onchange="handleFileSelect(event)"/>
        </div>
        <!-- File preview -->
        <div id="file-preview" style="display:none;background:var(--bg);border-radius:10px;padding:12px;margin-bottom:10px;border:0.5px solid var(--border);">
          <div style="display:flex;align-items:center;gap:10px;margin-bottom:8px;">
            <div style="font-size:24px;">🐍</div>
            <div style="flex:1;">
              <div id="fp-name" style="font-size:13px;font-weight:500;color:var(--text);"></div>
              <div id="fp-meta" style="font-size:10px;color:var(--muted);margin-top:2px;"></div>
            </div>
            <div id="fp-status" style="font-size:11px;font-weight:500;color:var(--g);"></div>
          </div>
          <div class="fg"><label>وصف التحديث (اختياري)</label>
            <input id="update-desc" placeholder="مثال: تحديث نظام الباقات + إصلاح صفحة التسجيل..."/>
          </div>
          <button class="btn bu2" id="upload-btn" onclick="uploadFile()" style="width:100%">📤 رفع التحديث للخادم</button>
        </div>
        <!-- Upload result -->
        <div id="upload-result" style="display:none;border-radius:10px;padding:12px;margin-bottom:10px;"></div>
      </div>
      <!-- Update history -->
      <div class="card cb">
        <div class="ch"><div class="ch-l"><div class="cico" style="background:var(--pl);color:var(--p)">📋</div>سجل التحديثات</div>
          <button class="btn sm" onclick="loadUpdateHistory()">تحديث</button>
        </div>
        <div id="update-history-list">
          <div style="text-align:center;padding:14px;font-size:11px;color:var(--muted);">لا توجد تحديثات مسجلة بعد</div>
        </div>
      </div>
    </div>

    <!-- ══════ SETTINGS ══════ -->
    <div class="pg" id="pg-settings">
      <div class="card cb">
        <div class="ch"><div class="ch-l"><div class="cico" style="background:var(--pl);color:var(--p)">⚙️</div>إعدادات النظام</div></div>
        <div class="g2">
          <div class="fg"><label>اسمك</label><input id="cfg-owner-name" placeholder="المالك"/></div>
          <div class="fg"><label>إيميلك</label><input id="cfg-owner-email" type="email" placeholder="admin@hotel.sa"/></div>
          <div class="fg"><label>جوالك</label><input id="cfg-owner-phone" placeholder="05xxxxxxxx"/></div>
          <div class="fg"><label>اسم النظام</label><input id="cfg-system-name" placeholder="نظام إدارة الفنادق"/></div>
        </div>
        <div style="font-size:11px;font-weight:700;color:var(--muted);margin:8px 0 6px">البنك</div>
        <div class="g2">
          <div class="fg"><label>اسم البنك</label><input id="cfg-bank-name" placeholder="بنك الراجحي"/></div>
          <div class="fg"><label>IBAN</label><input id="cfg-bank-iban" placeholder="SA00 0000..." style="font-family:monospace;direction:ltr"/></div>
        </div>
        <div style="font-size:11px;font-weight:700;color:var(--muted);margin:8px 0 6px">أسعار الخطط</div>
        <div class="g3">
          <div class="fg"><label>مجانية</label><input type="number" id="cfg-price-free" value="0"/></div>
          <div class="fg"><label>احترافية</label><input type="number" id="cfg-price-pro" value="299"/></div>
          <div class="fg"><label>مؤسسية</label><input type="number" id="cfg-price-ent" value="799"/></div>
        </div>
        <div class="fg"><label>مدة التجربة (يوم)</label><input type="number" id="cfg-trial-days" value="15" min="1" max="90"/></div>
        <button class="btn bg2" onclick="saveSettings()">حفظ الإعدادات</button>
      </div>
    </div>

  </div>
</div>
</div>

<!-- MODALS -->
<div class="modal-ov" id="modal-client"><div class="modal"><div class="modal-title"><span id="modal-client-title">تفاصيل العميل</span><span class="modal-close" onclick="closeModal('modal-client')">×</span></div><div id="modal-client-body"></div></div></div>
<div class="modal-ov" id="modal-ticket"><div class="modal"><div class="modal-title"><span id="modal-ticket-title">التذكرة</span><span class="modal-close" onclick="closeModal('modal-ticket')">×</span></div><div id="modal-ticket-body"></div><div style="display:flex;gap:6px;margin-top:10px"><textarea id="ticket-reply-text" style="flex:1;border:0.5px solid var(--border);border-radius:8px;padding:8px 10px;font-size:12px;background:var(--bg);color:var(--text);resize:none;height:60px;font-family:inherit" placeholder="اكتب ردك..."></textarea><div style="display:flex;flex-direction:column;gap:4px"><button class="btn bg2 sm" onclick="sendTicketReply()">إرسال</button><button class="btn br2 sm" onclick="closeTicket()">إغلاق</button></div></div></div></div>
<div class="modal-ov" id="modal-new-ticket"><div class="modal"><div class="modal-title"><span>فتح تذكرة جديدة</span><span class="modal-close" onclick="closeModal('modal-new-ticket')">×</span></div><div class="fg"><label>العميل</label><select id="nt-client"></select></div><div class="fg"><label>العنوان</label><input id="nt-title" placeholder="موضوع التذكرة..."/></div><div class="fg"><label>الفئة</label><select id="nt-cat"><option value="support">دعم فني</option><option value="billing">فواتير</option><option value="feature">طلب ميزة</option></select></div><div class="fg"><label>الأولوية</label><select id="nt-priority"><option value="normal" selected>عادية</option><option value="high">عالية</option><option value="urgent">عاجلة</option></select></div><div class="fg"><label>الرسالة</label><textarea id="nt-msg" placeholder="تفاصيل..."></textarea></div><div style="display:flex;gap:6px"><button class="btn bg2" onclick="createTicket()" style="flex:1">فتح التذكرة</button><button class="btn" onclick="closeModal('modal-new-ticket')">إلغاء</button></div></div></div>
<div class="modal-ov" id="modal-extend"><div class="modal"><div class="modal-title"><span>تمديد الاشتراك</span><span class="modal-close" onclick="closeModal('modal-extend')">×</span></div><input type="hidden" id="ext-client-id"/><div class="fg"><label>عدد الأيام</label><select id="ext-days"><option value="7">أسبوع — 7 أيام</option><option value="14">أسبوعان</option><option value="30">شهر</option><option value="60">شهران</option><option value="90">3 أشهر</option><option value="365">سنة</option></select></div><button class="btn bg2" onclick="doExtend()" style="width:100%">تمديد</button></div></div>

<script>
// ═══════════════════════════════════════════════
//  CORE
// ═══════════════════════════════════════════════
const F=n=>Math.round(parseFloat(n||0)).toLocaleString('ar-SA');
const FR=n=>F(n)+' ر.س';
const NOW=new Date();
document.getElementById('tb-date').textContent=NOW.toLocaleDateString('ar-SA',{weekday:'short',month:'short',day:'numeric',year:'numeric'});
document.getElementById('pay-date').value=NOW.toISOString().split('T')[0];
const ss=(id,v)=>{const e=document.getElementById(id);if(e)e.textContent=v;};
const gv=id=>{const e=document.getElementById(id);return e?e.value:'';};

let D={clients:[],keys:[],tickets:[],payments:[],settings:{},market:{}};
let analytics_data={};
let currentTicketId=null;
let chatHistory=[];

const PAGE_META={
  dash:{ic:'📊',bg:'linear-gradient(135deg,#3B6D11,#639922)',title:'لوحة التحكم'},
  analytics:{ic:'📈',bg:'linear-gradient(135deg,#185FA5,#378ADD)',title:'تحليل البيانات الحي'},
  ai:{ic:'🤖',bg:'linear-gradient(135deg,#534AB7,#7F77DD)',title:'تحكم بالذكاء الاصطناعي'},
  clients:{ic:'🏨',bg:'linear-gradient(135deg,#185FA5,#378ADD)',title:'إدارة العملاء'},
  register:{ic:'➕',bg:'linear-gradient(135deg,#3B6D11,#639922)',title:'تسجيل عميل جديد'},
  keys:{ic:'🔑',bg:'linear-gradient(135deg,#3B6D11,#639922)',title:'إصدار المفاتيح'},
  plans:{ic:'💎',bg:'linear-gradient(135deg,#534AB7,#7F77DD)',title:'الباقات والتسعير'},
  payments:{ic:'💰',bg:'linear-gradient(135deg,#3B6D11,#639922)',title:'المدفوعات'},
  tickets:{ic:'🎫',bg:'linear-gradient(135deg,#A32D2D,#E24B4A)',title:'تذاكر الدعم'},
  push:{ic:'📢',bg:'linear-gradient(135deg,#185FA5,#378ADD)',title:'إشعارات للعملاء'},
  branches:{ic:'🏢',bg:'linear-gradient(135deg,#534AB7,#7F77DD)',title:'الفروع والحسابات'},
  market:{ic:'🌐',bg:'linear-gradient(135deg,#0F6E56,#1D9E75)',title:'تحليل السوق AI'},
  update:{ic:'📤',bg:'linear-gradient(135deg,#534AB7,#7F77DD)',title:'رفع تحديث النظام'},
  settings:{ic:'⚙️',bg:'linear-gradient(135deg,#1E293B,#334155)',title:'الإعدادات'},
};

async function api(path,body=null){
  const opt=body?{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)}:{};
  const r=await fetch(path,opt);return r.json();
}

function toast_(msg,ok=true){
  const t=document.getElementById('toast');t.textContent=msg;
  t.style.background=ok?'var(--g)':'var(--r)';
  t.classList.add('show');setTimeout(()=>t.classList.remove('show'),3000);
}

function pill(l,cls){return`<span class="pill ${cls}">${l}</span>`;}
function stPill(st){const m={active:['نشط','p-g'],trial:['تجربة','p-b'],expired:['منتهي','p-r'],suspended:['موقوف','p-a'],free:['مجانية','p-n'],pro:['احترافية','p-b'],enterprise:['مؤسسية','p-u'],open:['مفتوحة','p-r'],replied:['مُجاب','p-a'],closed:['مغلقة','p-g'],unused:['غير مستخدم','p-b'],used:['مُستخدم','p-g'],revoked:['ملغي','p-r']};const[l,c]=m[st]||[st,'p-n'];return pill(l,c);}
function planPill(p){const m={free:['مجانية','p-n'],pro:['احترافية','p-b'],enterprise:['مؤسسية','p-u'],trial:['تجربة','p-a']};const[l,c]=m[p]||[p,'p-n'];return pill(l,c);}
function daysLeft(ds){if(!ds)return null;return Math.ceil((new Date(ds)-new Date())/86400000);}
function closeModal(id){document.getElementById(id).classList.remove('open');}
document.querySelectorAll('.modal-ov').forEach(el=>el.addEventListener('click',e=>{if(e.target===el)el.classList.remove('open');}));

// ═══════════════════════════════════════════════
//  NAVIGATION
// ═══════════════════════════════════════════════
function go(pg){
  document.querySelectorAll('.ni').forEach(n=>n.classList.remove('on'));
  document.querySelectorAll('.pg').forEach(p=>p.classList.remove('on'));
  const el=document.getElementById('pg-'+pg);if(el)el.classList.add('on');
  document.querySelectorAll('.ni').forEach(n=>{if(n.getAttribute('onclick')===`go('${pg}')`)n.classList.add('on');});
  const m=PAGE_META[pg]||{ic:'📄',bg:'#185FA5',title:pg};
  const ti=document.getElementById('tb-ic');if(ti){ti.textContent=m.ic;ti.style.background=m.bg;ti.style.color='#fff';}
  ss('tb-title',m.title);
  const rs={clients:rClients,keys:rKeys,tickets:rTickets,payments:rPayments,settings:rSettings,plans:rPlans,market:rMarket,branches:rBranches,analytics:loadAnalytics,dash:rDash,push:()=>{},ai:()=>{},register:()=>{},update:loadUpdateHistory};
  const savePlansBtn=document.getElementById('save-plans-btn');
  if(savePlansBtn)savePlansBtn.style.display=pg==='plans'?'inline-flex':'none';
  if(rs[pg])rs[pg]();
}

// ═══════════════════════════════════════════════
//  BOOT
// ═══════════════════════════════════════════════
let localPlans=[];
async function boot(){
  const[st,cl,kl,tl,pl,sl,mkt,an]=await Promise.all([
    api('/api/admin/stats'),api('/api/admin/clients'),api('/api/admin/keys'),
    api('/api/admin/tickets'),api('/api/admin/payments'),api('/api/admin/settings'),
    api('/api/admin/market'),api('/api/admin/analytics').catch(()=>({})),
  ]);
  D.clients=cl.clients||[];D.keys=kl.keys||[];D.tickets=tl.tickets||[];
  D.payments=pl.payments||[];D.settings=sl.settings||{};D.market=mkt||{};
  analytics_data=an||{};
  rStats(st);buildClientSelects();
  ss('sb-owner-name',D.settings.owner_name||'المالك');
  ss('sb-av',(D.settings.owner_name||'م').charAt(0));
  ss('sb-owner-email',D.settings.owner_email||'admin');
  ss('sb-sys-name',D.settings.system_name||'Hotel Admin');
  updateOnlineBadge(an.online_now||0);
  const tr=D.clients.filter(c=>c.status==='trial').length;
  const nt=document.getElementById('nb-trial');if(nt){nt.style.display=tr?'inline':'none';nt.textContent=tr;}
  const otx=D.tickets.filter(t=>t.status==='open').length;
  const ntx=document.getElementById('nb-tickets');if(ntx){ntx.style.display=otx?'inline':'none';ntx.textContent=otx;}
  go('dash');
  startPolling();
}
boot();

function updateOnlineBadge(n){
  const nb=document.getElementById('nb-online');
  if(nb){nb.style.display=n>0?'inline':'none';nb.textContent=n;}
  ss('tb-online',`⬤ ${n} متصل`);
  ss('st-online',n);
}

// ─── Real-time polling every 30s ───────────────
function startPolling(){
  setInterval(async()=>{
    try{
      const an=await api('/api/admin/analytics');
      analytics_data=an;
      updateOnlineBadge(an.online_now||0);
      ss('st-uptime',an.uptime_human||'—');
      ss('sb-uptime',an.uptime_human||'—');
      ss('an-uptime',an.uptime_human||'—');
      ss('an-online',an.online_now||0);
      ss('an-actions',F(an.total_actions||0));
      ss('an-errors',an.total_errors||0);
      const oc=document.getElementById('online-count-lbl');
      if(oc)oc.textContent=(an.online_now||0)+' مستخدم';
      // Update online list in dash
      if(document.getElementById('pg-dash').classList.contains('on'))renderOnline(an);
    }catch(e){}
  },30000);
}

// ═══════════════════════════════════════════════
//  DASHBOARD
// ═══════════════════════════════════════════════
function rStats(st){
  ss('st-total',st.total_clients||0);ss('st-active',st.active||0);ss('st-trial',st.trial||0);
  const mrr=Math.round(st.mrr||0);ss('st-mrr',F(mrr));
  ss('st-keys',st.total_keys||0);ss('st-tickets',st.open_tickets||0);
  const up=analytics_data.uptime_human||'—';ss('st-uptime',up.split(' ').slice(0,2).join(' '));
  ss('st-uptime-sub',up);
  const pct=st.total_clients>0?Math.round((st.active||0)/st.total_clients*100):0;
  ss('t-total',`${st.total_clients||0} إجمالي`);
  ss('t-active',`${pct}% من الكل`);
  ss('t-mrr',mrr>0?`ARR: ${F(mrr*12)} ر.س`:'—');
  ss('pay-mrr',F(mrr));ss('pay-cnt',D.payments.length);
  ss('pay-total',F(D.payments.reduce((a,p)=>a+p.amount,0)));
  const prices=D.settings.prices||{pro:299,enterprise:799};
  ss('st-keys-sub',(D.keys.filter(k=>k.status==='used').length)+' مستخدمة');
}

function rDash(){
  rStats({total_clients:D.clients.length,active:D.clients.filter(c=>c.status==='active').length,trial:D.clients.filter(c=>c.status==='trial').length,mrr:D.clients.filter(c=>c.status==='active').reduce((a,c)=>{const p=D.settings.prices||{pro:299,enterprise:799};return a+(p[c.plan]||0);},0),total_keys:D.keys.length,open_tickets:D.tickets.filter(t=>t.status==='open').length});
  renderRevChart();renderFunnel();renderExpiring();renderDashTickets();renderOnline(analytics_data);
}

function renderRevChart(){
  const days=['الأحد','الاثنين','الثلاثاء','الأربعاء','الخميس','الجمعة','السبت'];
  const ds=analytics_data.daily_stats||{};
  const today=new Date();const vals=[];const lbls=[];
  for(let i=6;i>=0;i--){const d=new Date(today);d.setDate(d.getDate()-i);const k=d.toISOString().split('T')[0];const v=(ds[k]?.logins||0)*50+(ds[k]?.actions||0)*10;vals.push(v);lbls.push(days[d.getDay()]);}
  const max=Math.max(...vals,1);
  const ch=document.getElementById('rev-chart');
  if(ch)ch.innerHTML=vals.map((v,i)=>`<div class="mc-bar" style="height:${Math.round(v/max*100)}%;background:${i===6?'var(--p)':'var(--pl)'};" title="${lbls[i]}: ${v}"></div>`).join('');
  const cl=document.getElementById('rev-chart-lbl');
  if(cl)cl.innerHTML=lbls.map((l,i)=>`<span style="flex:1;text-align:center;font-size:9px;color:${i===6?'var(--p)':'var(--muted)'}">${l.charAt(0)}</span>`).join('');
}

function renderFunnel(){
  const total=D.clients.length||1;const active=D.clients.filter(c=>c.status==='active').length;
  const trial=D.clients.filter(c=>c.status==='trial').length;
  const pct=total>0?Math.round(active/total*100):0;
  ss('conv-rate',pct+'%');ss('conv-paid',Math.round(active/10)||0);
  const el=document.getElementById('funnel-mini');
  if(!el)return;
  const stages=[{l:`${total} مسجّل`,w:100,c:'var(--pl)',tc:'var(--pd)'},{l:`${trial} تجربة`,w:Math.round(trial/total*100)||30,c:'var(--al)',tc:'var(--ad)'},{l:`${active} مشترك`,w:Math.round(active/total*100)||10,c:'var(--gl)',tc:'var(--gd)'}];
  el.innerHTML=stages.map(s=>`<div style="height:22px;width:${s.w}%;background:${s.c};border-radius:5px;display:flex;align-items:center;padding:0 8px;font-size:10px;color:${s.tc};font-weight:700;margin-bottom:4px;transition:width .5s">${s.l}</div>`).join('');
}

function renderExpiring(){
  const el=document.getElementById('dash-expiring');if(!el)return;
  const exp=D.clients.filter(c=>c.status==='trial'&&daysLeft(c.trial_end)<=5).sort((a,b)=>daysLeft(a.trial_end)-daysLeft(b.trial_end));
  el.innerHTML=exp.length?exp.map(c=>{const d=daysLeft(c.trial_end);return`<div style="display:flex;align-items:center;justify-content:space-between;padding:7px 0;border-bottom:0.5px solid var(--border);flex-wrap:wrap;gap:4px"><div><div style="font-size:11px;font-weight:700">${c.hotel_name||c.name}</div><div style="font-size:9px;color:var(--muted)">${c.email||'—'}</div></div><div style="display:flex;align-items:center;gap:5px"><span style="font-size:10px;font-weight:700;color:${d<=1?'var(--r)':'var(--a)'}">${d<=0?'منتهية':d+' أيام'}</span><button class="btn sm bg2" onclick="showExtend(${c.id})">تمديد</button><button class="btn sm bp" onclick="assignKey(${c.id})">مفتاح</button></div></div>`;}).join(''):'<div style="font-size:11px;color:var(--muted);text-align:center;padding:10px">✓ لا توجد تجارب تنتهي قريباً</div>';
}

function renderDashTickets(){
  const el=document.getElementById('dash-tickets');if(!el)return;
  const open=D.tickets.filter(t=>t.status==='open').slice(0,4);
  el.innerHTML=open.length?open.map(t=>`<div style="display:flex;align-items:center;justify-content:space-between;padding:7px 0;border-bottom:0.5px solid var(--border);gap:4px"><div><div style="font-size:11px;font-weight:700">${t.title}</div><div style="font-size:9px;color:var(--muted)">${t.client_name||'—'}</div></div><button class="btn sm bp" onclick="openTicket(${t.id})">رد</button></div>`).join(''):'<div style="font-size:11px;color:var(--muted);text-align:center;padding:10px">✓ لا توجد تذاكر مفتوحة</div>';
}

function renderOnline(an){
  const el=document.getElementById('online-list');if(!el)return;
  const sess=an.active_sessions||[];
  const colors=['#185FA5','#3B6D11','#534AB7','#854F0B','#0F6E56','#993556'];
  if(!sess.length){el.innerHTML='<div style="font-size:11px;color:var(--muted);text-align:center;padding:10px">لا أحد متصل الآن</div>';return;}
  el.innerHTML=sess.map((s,i)=>{
    const c=D.clients.find(x=>String(x.id)===String(s.cid));
    const name=c?c.hotel_name||c.name:`عميل ${s.cid}`;
    const mins=Math.round((new Date()-new Date(s.last_seen))/60000);
    const clr=colors[i%colors.length];
    return`<div class="online-item"><div class="online-av" style="background:${clr}22;color:${clr}">${name.charAt(0)}</div><div class="online-dot"></div><div class="online-info"><div class="online-name">${name}</div><div class="online-meta">آخر نشاط: ${mins===0?'الآن':mins+' دقيقة'} · ${s.pages||0} صفحات · ${s.actions||0} أحداث</div></div></div>`;
  }).join('');
}

// ═══════════════════════════════════════════════
//  ANALYTICS
// ═══════════════════════════════════════════════
async function loadAnalytics(){
  const an=await api('/api/admin/analytics');analytics_data=an;
  ss('an-online',an.online_now||0);ss('an-actions',F(an.total_actions||0));
  ss('an-errors',an.total_errors||0);ss('an-uptime',an.uptime_human||'—');
  // Pages
  const pgs=an.top_pages||[];const maxPg=pgs.length?pgs[0][1]:1;
  const pgEl=document.getElementById('an-pages');
  if(pgEl)pgEl.innerHTML=pgs.length?pgs.map(([page,cnt])=>`<div class="a-bar-row"><div class="a-bar-lbl">${page}</div><div class="a-bar-track"><div class="a-bar-fill" style="width:${Math.round(cnt/maxPg*100)}%;background:var(--p)"></div></div><div class="a-bar-val">${cnt}</div></div>`).join(''):'<div style="font-size:11px;color:var(--muted)">لا توجد بيانات</div>';
  // Daily
  const ds=an.daily_stats||{};const days=Object.keys(ds).sort().slice(-7);
  const dyEl=document.getElementById('an-daily');
  if(dyEl)dyEl.innerHTML=days.length?days.map(d=>`<div class="a-bar-row"><div class="a-bar-lbl" style="font-size:9px">${d.slice(5)}</div><div class="a-bar-track"><div class="a-bar-fill" style="width:${Math.min(100,Math.round((ds[d].actions||0)/10))}%;background:var(--g)"></div></div><div class="a-bar-val" style="font-size:9px">${ds[d].logins||0} دخول · ${ds[d].actions||0} حدث</div></div>`).join(''):'<div style="font-size:11px;color:var(--muted)">لا توجد بيانات</div>';
  // Clients table
  const cs=an.client_stats||{};const csEl=document.getElementById('an-clients-body');
  if(csEl)csEl.innerHTML=Object.entries(cs).map(([cid,stat])=>{const c=D.clients.find(x=>String(x.id)===String(cid));if(!c)return'';return`<tr><td style="font-weight:700">${c.hotel_name||c.name}</td><td style="text-align:center">${stat.days_active}</td><td style="text-align:center">${stat.total_actions}</td><td style="font-size:9px;color:var(--muted)">${stat.last_page}</td><td style="text-align:center;color:${stat.errors>0?'var(--r)':'var(--g)'};font-weight:700">${stat.errors}</td><td style="font-size:9px">${stat.first_seen||'—'}</td><td>${stPill(c.status)}</td></tr>`;}).join('')||'<tr><td colspan="7" style="text-align:center;padding:12px;color:var(--muted)">لا توجد بيانات</td></tr>';
  // Errors
  const errs=an.error_log||[];const errEl=document.getElementById('an-errors-list');
  if(errEl)errEl.innerHTML=errs.length?errs.map(e=>`<div class="feed-item"><div class="feed-dot" style="background:var(--r)"></div><div class="feed-time">${e.time.slice(11,16)}</div><div class="feed-txt"><b>${e.error.slice(0,80)}</b><div style="font-size:9px;color:var(--muted)">${e.context||'—'}</div></div></div>`).join(''):'<div style="font-size:11px;color:var(--g);text-align:center;padding:10px">✓ لا توجد أخطاء</div>';
  // Feed
  const feed=an.action_log||[];const feedEl=document.getElementById('an-feed');
  if(feedEl)feedEl.innerHTML=feed.length?feed.slice(0,20).map(f=>`<div class="feed-item"><div class="feed-dot" style="background:var(--p)"></div><div class="feed-time">${f.time.slice(11,16)}</div><div class="feed-txt">${f.action}${f.detail?' — '+f.detail:''}</div></div>`).join(''):'<div style="font-size:11px;color:var(--muted);text-align:center;padding:10px">لا توجد أحداث</div>';
  renderOnline(an);
}

async function clearErrors(){analytics_data.error_log=[];loadAnalytics();}

// ═══════════════════════════════════════════════
//  AI EXECUTION ENGINE
// ═══════════════════════════════════════════════
let pendingActions = [];
let isProcessing   = false;

document.getElementById('ai-auto-exec')?.addEventListener('change', function(){
  const badge = document.getElementById('ai-mode-badge');
  if(badge) badge.textContent = this.checked ? '⚡ تنفيذ تلقائي' : 'مراجعة يدوية';
  if(badge) badge.style.background = this.checked ? 'rgba(34,197,94,.25)' : 'rgba(255,255,255,.1)';
  if(badge) badge.style.color = this.checked ? '#22C55E' : 'rgba(255,255,255,.5)';
});

function setAIStatus(msg, busy=false){
  const el=document.getElementById('ai-status');
  if(el){el.textContent=msg;el.style.color=busy?'var(--a)':'var(--muted)';}
  const btn=document.getElementById('ai-send-btn');const cbtn=document.getElementById('chat-send-btn');
  [btn,cbtn].forEach(b=>{if(b){b.disabled=busy;b.style.opacity=busy?.5:1;}});
}

async function callAI(cmd, autoExec=false){
  if(isProcessing)return;
  isProcessing=true;
  setAIStatus('Claude يفكر...', true);
  const key = gv('ai-key-input')||D.settings.claude_key||'';
  try{
    const r = await api('/api/ai/control',{command:cmd, claude_key:key, auto_execute:autoExec});
    isProcessing=false;
    setAIStatus('جاهز');
    if(!r.ok){addChat('error','حدث خطأ: '+(r.error||'—'));return r;}
    return r;
  }catch(e){
    isProcessing=false;
    setAIStatus('خطأ في الاتصال');
    addChat('error','خطأ: '+e.message);
    return null;
  }
}

async function sendAI(){
  const cmd=gv('ai-cmd').trim();if(!cmd)return;
  document.getElementById('ai-cmd').value='';
  addChat('user',cmd);
  const autoExec=document.getElementById('ai-auto-exec')?.checked||false;
  const r=await callAI(cmd, autoExec);
  if(!r)return;
  processAIResponse(r, autoExec);
}

async function sendChat(){
  const msg=gv('ai-chat-input').trim();if(!msg)return;
  document.getElementById('ai-chat-input').value='';
  addChat('user',msg);
  const autoExec=document.getElementById('ai-auto-exec')?.checked||false;
  const r=await callAI(msg, autoExec);
  if(!r)return;
  processAIResponse(r, autoExec);
}

function quickAI(cmd){
  addChat('user',cmd);
  const autoExec=document.getElementById('ai-auto-exec')?.checked||false;
  callAI(cmd, autoExec).then(r=>{if(r)processAIResponse(r,autoExec);});
}

function processAIResponse(r, autoExec){
  const result=r.result||{};
  // Show response
  addChat('ai', result.response||'—', result.suggestions||[]);
  // Handle actions
  const actions=result.actions||[];
  if(actions.length===0)return;
  if(autoExec){
    // Auto executed
    const executed=r.executed||[];
    executed.forEach(ex=>{
      logExec(ex.action, ex.ok, ex.desc||'', ex.error||'');
    });
    if(executed.length>0){
      addChat('system',`✅ تم تنفيذ ${executed.length} إجراء تلقائياً:\n`+executed.map(e=>`${e.ok?'✓':'✗'} ${e.desc||e.action}`).join('\n'));
      // Refresh data
      setTimeout(()=>boot(),1000);
    }
  } else {
    // Show pending for approval
    showPendingActions(actions, result.summary||'');
  }
}

function showPendingActions(actions, summary){
  pendingActions=actions;
  const panel=document.getElementById('ai-pending');
  const list=document.getElementById('ai-pending-list');
  if(!panel||!list)return;
  list.innerHTML=actions.map((a,i)=>`
    <div style="display:flex;align-items:center;gap:8px;padding:6px 8px;background:rgba(255,255,255,.5);border-radius:7px;">
      <input type="checkbox" id="pa-${i}" checked style="width:auto;accent-color:var(--g);flex-shrink:0"/>
      <div style="flex:1;font-size:11px;color:var(--ad)">
        <span style="font-weight:700">${actionLabel(a.type)}</span> — ${a.description||a.type}
      </div>
    </div>`).join('');
  panel.style.display='block';
  if(summary)addChat('system','⏳ Claude يقترح: '+summary+'\n(راجع الإجراءات أدناه وأكّد التنفيذ)');
}

function actionLabel(t){const m={extend_client:'تمديد تجربة',suspend_client:'إيقاف عميل',activate_client:'تفعيل عميل',generate_key:'إصدار مفتاح',reply_ticket:'رد على تذكرة',close_ticket:'إغلاق تذكرة',send_push:'إرسال إشعار',update_price:'تغيير سعر',add_client:'إضافة عميل',read_only:'قراءة فقط'};return m[t]||t;}

async function executePending(){
  const selected=pendingActions.filter((_,i)=>document.getElementById('pa-'+i)?.checked);
  if(!selected.length){toast_('لا يوجد إجراء محدد',false);return;}
  const panel=document.getElementById('ai-pending');if(panel)panel.style.display='none';
  setAIStatus('جارٍ التنفيذ...', true);
  const key=gv('ai-key-input')||D.settings.claude_key||'';
  // Execute by sending with auto_execute=true and only selected actions
  const fakeCmd='تنفيذ: '+selected.map(a=>a.description||a.type).join(' + ');
  const r=await api('/api/ai/control',{command:fakeCmd,claude_key:key,auto_execute:true,override_actions:selected});
  setAIStatus('جاهز');
  isProcessing=false;
  const executed=r.executed||[];
  executed.forEach(ex=>logExec(ex.action,ex.ok,ex.desc||'',ex.error||''));
  addChat('system',`✅ تم تنفيذ ${executed.length} إجراء:\n`+executed.map(e=>`${e.ok?'✓':'✗'} ${e.desc||e.action}`).join('\n'));
  setTimeout(()=>boot(),1000);
}

function cancelPending(){
  pendingActions=[];
  const panel=document.getElementById('ai-pending');if(panel)panel.style.display='none';
  addChat('system','تم إلغاء الإجراءات المقترحة');
}

function logExec(action, ok, desc, error){
  const el=document.getElementById('exec-log');if(!el)return;
  const t=new Date().toLocaleTimeString('ar-SA',{hour:'2-digit',minute:'2-digit'});
  const row=document.createElement('div');
  row.style.cssText=`display:flex;align-items:center;gap:8px;padding:5px 0;border-bottom:0.5px solid var(--border);`;
  row.innerHTML=`<span style="font-size:10px;color:var(--muted);white-space:nowrap">${t}</span><span style="font-size:16px">${ok?'✅':'❌'}</span><div style="flex:1;font-size:11px"><span style="font-weight:700;color:${ok?'var(--g)':'var(--r)'}">${actionLabel(action)}</span>${desc?' — '+desc:''}<div style="font-size:9px;color:var(--muted)">${error||''}</div></div>`;
  el.insertBefore(row, el.firstChild);
}

function addChat(from, text, suggestions=[]){
  const el=document.getElementById('ai-chat');if(!el)return;
  const styles={
    user:'background:var(--pl);color:var(--pd);margin-left:auto',
    ai:'background:var(--gl);color:var(--gd)',
    system:'background:var(--al);color:var(--ad)',
    error:'background:var(--rl);color:var(--rd)',
  };
  const labels={user:'أنت',ai:'Claude AI',system:'النظام',error:'خطأ'};
  const div=document.createElement('div');
  div.style.cssText=`padding:9px 12px;border-radius:10px;font-size:11px;max-width:88%;line-height:1.65;${styles[from]||styles.ai}`;
  const lbl=document.createElement('div');
  lbl.style.cssText='font-size:9px;font-weight:700;margin-bottom:4px;opacity:.75';
  lbl.textContent=labels[from]||from;
  div.appendChild(lbl);
  const p=document.createElement('div');
  p.style.whiteSpace='pre-wrap';
  p.textContent=text;
  div.appendChild(p);
  if(suggestions.length){
    const sg=document.createElement('div');
    sg.style.cssText='margin-top:7px;display:flex;flex-wrap:wrap;gap:4px';
    suggestions.forEach(s=>{
      const btn=document.createElement('button');
      btn.className='btn sm';
      btn.style.cssText='font-size:10px;background:rgba(255,255,255,.6)';
      btn.textContent=s;
      btn.onclick=()=>{addChat('user',s);quickAI(s);};
      sg.appendChild(btn);
    });
    div.appendChild(sg);
  }
  el.appendChild(div);
  el.scrollTop=el.scrollHeight;
}

function clearChat(){const el=document.getElementById('ai-chat');if(el)el.innerHTML='';}
async function saveAIKey(){const k=gv('ai-key-input').trim();if(!k)return;await api('/api/admin/settings/save',{claude_key:k});D.settings.claude_key=k;toast_('تم حفظ مفتاح Claude AI ✓');}


// ═══════════════════════════════════════════════
//  PUSH
// ═══════════════════════════════════════════════
async function sendPush(){
  const msg=gv('push-msg').trim();if(!msg){toast_('أدخل رسالة',false);return;}
  const target=gv('push-target');
  let cids=[];
  if(target==='active')cids=D.clients.filter(c=>c.status==='active').map(c=>c.id);
  else if(target==='trial')cids=D.clients.filter(c=>c.status==='trial').map(c=>c.id);
  const r=await api('/api/admin/push',{message:msg,client_ids:cids});
  if(r.ok){const el=document.getElementById('push-result');if(el){el.textContent=`تم الإرسال لـ ${r.sent_to} عميل ✓`;el.style.display='block';}toast_('تم الإرسال ✓');}
}

// ═══════════════════════════════════════════════
//  CLIENTS
// ═══════════════════════════════════════════════
function filterClients(){
  const q=gv('cl-search').toLowerCase();const st=gv('cl-filter');
  const fl=D.clients.filter(c=>(!q||(c.name+c.hotel_name+c.email).toLowerCase().includes(q))&&(!st||c.status===st));
  renderClientsTable(fl);
}
function rClients(){filterClients();}
function renderClientsTable(list){
  const prices=D.settings.prices||{pro:299,enterprise:799};
  const cs=analytics_data.client_stats||{};
  const el=document.getElementById('clients-body');if(!el)return;
  el.innerHTML=list.length?list.map(c=>{const dl=daysLeft(c.trial_end);const pr=prices[c.plan]||0;const stat=cs[String(c.id)]||{days_active:0};return`<tr><td><div style="font-weight:700">${c.hotel_name||c.name}</div><div style="font-size:9px;color:var(--muted)">${c.email||'—'}</div></td><td style="font-size:10px">${c.city||'—'}</td><td>${planPill(c.plan)}</td><td>${stPill(c.status)}</td><td style="text-align:center;font-weight:700;color:var(--p)">${stat.days_active||0}</td><td style="font-size:10px;color:${dl!==null&&dl<=3?'var(--r)':'var(--muted)'}">${c.trial_end||'—'}${dl!==null?' ('+dl+' يوم)':''}</td><td style="font-weight:700;color:var(--g)">${pr?FR(pr):'—'}</td><td style="white-space:nowrap"><button class="btn sm" onclick="showClientDetail(${c.id})">تفاصيل</button><button class="btn sm bg2" onclick="showExtend(${c.id})">تمديد</button><button class="btn sm bp" onclick="assignKey(${c.id})">مفتاح</button>${c.status==='suspended'?`<button class="btn sm bg2" onclick="toggleClient(${c.id},'activate')">تفعيل</button>`:`<button class="btn sm" style="color:var(--r)" onclick="toggleClient(${c.id},'suspend')">إيقاف</button>`}</td></tr>`;}).join(''):'<tr><td colspan="8" style="text-align:center;padding:14px;color:var(--muted)">لا يوجد عملاء</td></tr>';
}
function showClientDetail(id){
  const c=D.clients.find(x=>x.id===id);if(!c)return;
  const cs=(analytics_data.client_stats||{})[String(id)]||{};
  ss('modal-client-title',c.hotel_name||c.name);
  document.getElementById('modal-client-body').innerHTML=`
    <div class="kg3" style="margin-bottom:10px">
      <div style="background:var(--pl);border-radius:8px;padding:10px;text-align:center"><div style="font-size:20px;font-weight:700;color:var(--p)">${cs.days_active||0}</div><div style="font-size:10px;color:var(--pd)">أيام استخدام</div></div>
      <div style="background:var(--gl);border-radius:8px;padding:10px;text-align:center"><div style="font-size:20px;font-weight:700;color:var(--g)">${cs.total_actions||0}</div><div style="font-size:10px;color:var(--gd)">إجمالي الأحداث</div></div>
      <div style="background:${cs.errors>0?'var(--rl)':'var(--gl)'};border-radius:8px;padding:10px;text-align:center"><div style="font-size:20px;font-weight:700;color:${cs.errors>0?'var(--r)':'var(--g)'}">${cs.errors||0}</div><div style="font-size:10px;color:var(--muted)">أخطاء</div></div>
    </div>
    <div class="g2">
      <div><div style="font-size:10px;color:var(--muted)">الإيميل</div><div style="font-size:11px;margin-top:2px">${c.email||'—'}</div></div>
      <div><div style="font-size:10px;color:var(--muted)">الجوال</div><div style="font-size:11px;margin-top:2px">${c.phone||'—'}</div></div>
      <div><div style="font-size:10px;color:var(--muted)">الحالة</div><div style="margin-top:2px">${stPill(c.status)}</div></div>
      <div><div style="font-size:10px;color:var(--muted)">الخطة</div><div style="margin-top:2px">${planPill(c.plan)}</div></div>
      <div><div style="font-size:10px;color:var(--muted)">انتهاء التجربة</div><div style="font-size:11px;margin-top:2px">${c.trial_end||'—'}</div></div>
      <div><div style="font-size:10px;color:var(--muted)">آخر صفحة</div><div style="font-size:11px;margin-top:2px">${cs.last_page||'—'}</div></div>
    </div>
    ${c.license_key?`<div style="margin:10px 0"><div style="font-size:10px;color:var(--muted);margin-bottom:4px">مفتاح الترخيص</div><div style="background:#0F172A;color:#10B981;font-family:monospace;font-size:12px;font-weight:700;padding:8px 12px;border-radius:8px">${c.license_key}</div></div>`:''}
    <div style="display:flex;gap:6px;margin-top:10px;flex-wrap:wrap">
      <button class="btn sm bg2" onclick="showExtend(${c.id});closeModal('modal-client')">تمديد</button>
      <button class="btn sm bp" onclick="assignKey(${c.id});closeModal('modal-client')">إصدار مفتاح</button>
      ${c.status==='suspended'?`<button class="btn sm bg2" onclick="toggleClient(${c.id},'activate');closeModal('modal-client')">تفعيل</button>`:`<button class="btn sm" style="color:var(--r)" onclick="toggleClient(${c.id},'suspend');closeModal('modal-client')">إيقاف</button>`}
      <button class="btn sm br2" onclick="if(confirm('حذف?'))deleteClient(${c.id})">حذف</button>
    </div>`;
  document.getElementById('modal-client').classList.add('open');
}
async function registerClient(){const name=gv('rg-name').trim();if(!name){toast_('أدخل الاسم',false);return;}const r=await api('/api/admin/clients/add',{name,hotel_name:gv('rg-hotel')||name,email:gv('rg-email'),phone:gv('rg-phone'),city:gv('rg-city'),hotel_type:gv('rg-type'),rooms:gv('rg-rooms'),plan:gv('rg-plan'),notes:gv('rg-notes')});if(r.ok){D.clients.push(r.client);buildClientSelects();toast_(`تم تسجيل "${r.client.hotel_name||name}" ✓`);['rg-name','rg-hotel','rg-email','rg-phone','rg-rooms','rg-notes'].forEach(id=>{const e=document.getElementById(id);if(e)e.value='';});go('clients');}}
async function toggleClient(id,action){const r=await api('/api/admin/clients/toggle',{id,action});if(r.ok){const c=D.clients.find(x=>x.id===id);if(c)c.status=action==='activate'?'active':'suspended';rClients();toast_(action==='activate'?'تم التفعيل ✓':'تم الإيقاف ✓');}}
async function deleteClient(id){const r=await api('/api/admin/clients/delete',{id});if(r.ok){D.clients=D.clients.filter(c=>c.id!==id);buildClientSelects();rClients();toast_('تم الحذف');}}
function showExtend(id){document.getElementById('ext-client-id').value=id;document.getElementById('modal-extend').classList.add('open');}
async function doExtend(){const id=parseInt(gv('ext-client-id'));const days=parseInt(gv('ext-days'));const r=await api('/api/admin/clients/extend',{id,days});if(r.ok){const c=D.clients.find(x=>x.id===id);if(c){const base=c.trial_end&&new Date(c.trial_end)>new Date()?new Date(c.trial_end):new Date();base.setDate(base.getDate()+days);c.trial_end=base.toISOString().split('T')[0];c.status='trial';}closeModal('modal-extend');rClients();rDash();toast_(`تم التمديد ${days} يوم ✓`);}}
async function assignKey(clientId){const r=await api('/api/admin/keys/generate',{plan:'pro',days:30,count:1,client_id:clientId,notes:'مُعيّن يدوياً'});if(r.ok){D.keys.push(...r.keys);const c=D.clients.find(x=>x.id===clientId);if(c&&r.keys[0]){c.license_key=r.keys[0].key;c.status='active';}rClients();rDash();toast_(`تم إصدار: ${r.keys[0]?.key} ✓`);}}
function buildClientSelects(){const opts=D.clients.map(c=>`<option value="${c.id}">${c.hotel_name||c.name}</option>`).join('');['key-client','pay-client','nt-client'].forEach(id=>{const el=document.getElementById(id);if(el)el.innerHTML=(id==='key-client'?'<option value="">— بدون تعيين —</option>':'')+opts;});buildBranchSelect();}

// ═══════════════════════════════════════════════
//  KEYS
// ═══════════════════════════════════════════════
async function generateKeys(){const plan=gv('key-plan');const days=parseInt(gv('key-days')||30);const count=parseInt(gv('key-count')||1);const cid=gv('key-client');const r=await api('/api/admin/keys/generate',{plan,days,count,client_id:cid||null,notes:gv('key-note')});if(r.ok){D.keys.push(...r.keys);rKeys();const box=document.getElementById('keys-generated');if(box){box.innerHTML=`<div style="font-size:11px;font-weight:700;color:var(--g);margin-bottom:6px">✅ تم إصدار ${r.keys.length} مفتاح:</div>`+r.keys.map(k=>`<div style="background:#0F172A;color:#10B981;font-family:monospace;font-size:12px;font-weight:700;padding:8px 12px;border-radius:8px;margin-bottom:5px;display:flex;align-items:center;justify-content:space-between"><span>${k.key}</span><button class="btn sm" style="background:rgba(255,255,255,.1);color:#10B981;border-color:rgba(255,255,255,.2)" onclick="navigator.clipboard.writeText('${k.key}').then(()=>toast_('تم النسخ ✓'))">نسخ</button></div>`).join('');}toast_(`تم إصدار ${r.keys.length} مفتاح ✓`);}}
function rKeys(){const el=document.getElementById('keys-body');if(!el)return;el.innerHTML=[...D.keys].reverse().map(k=>`<tr><td style="font-family:monospace;font-weight:700;font-size:12px;color:var(--t)">${k.key}</td><td>${planPill(k.plan)}</td><td style="font-size:10px">${k.client_name||'—'}</td><td style="font-size:10px">${k.expires_at||'—'}</td><td>${stPill(k.status)}</td><td><button class="btn sm br2" onclick="revokeKey(${k.id})">إلغاء</button></td></tr>`).join('')||'<tr><td colspan="6" style="text-align:center;padding:12px;color:var(--muted)">لا توجد مفاتيح</td></tr>';}
async function revokeKey(id){if(!confirm('إلغاء هذا المفتاح؟'))return;const r=await api('/api/admin/keys/revoke',{id});if(r.ok){const k=D.keys.find(x=>x.id===id);if(k)k.status='revoked';rKeys();toast_('تم إلغاء المفتاح');}}

// ═══════════════════════════════════════════════
//  PAYMENTS
// ═══════════════════════════════════════════════
async function addPayment(){const cid=gv('pay-client');const amt=parseFloat(gv('pay-amount')||0);if(!cid||!amt){toast_('اختر العميل وأدخل المبلغ',false);return;}const c=D.clients.find(x=>x.id==cid);const r=await api('/api/admin/payments/add',{client_id:cid,client_name:c?.hotel_name||c?.name||'',amount:amt,plan:gv('pay-plan'),method:gv('pay-method'),ref:gv('pay-ref'),date:gv('pay-date'),notes:''});if(r.ok){D.payments.push(r.payment);rPayments();await boot();toast_(`✅ تسجيل الدفعة ${FR(amt)} + مفتاح تلقائي ✓`);['pay-amount','pay-ref'].forEach(id=>{const e=document.getElementById(id);if(e)e.value='';});}}
function rPayments(){const total=D.payments.reduce((a,p)=>a+p.amount,0);ss('pay-total',F(total));ss('pay-cnt',D.payments.length);const el=document.getElementById('pay-body');if(!el)return;el.innerHTML=[...D.payments].reverse().map(p=>`<tr><td style="font-weight:700">${p.client_name||'—'}</td><td style="color:var(--g);font-weight:700">${FR(p.amount)}</td><td>${planPill(p.plan)}</td><td style="font-size:10px">{{transfer:'تحويل',mada:'مدى',cash:'نقداً',stc:'STC'}[p.method]||p.method}</td><td style="font-size:10px;color:var(--muted)">${p.ref||'—'}</td><td style="font-size:10px">${p.date||'—'}</td></tr>`).join('')||'<tr><td colspan="6" style="text-align:center;padding:12px;color:var(--muted)">لا توجد مدفوعات</td></tr>';}

// ═══════════════════════════════════════════════
//  TICKETS
// ═══════════════════════════════════════════════
function rTickets(){const el=document.getElementById('tickets-list');if(!el)return;const sorted=[...D.tickets].sort((a,b)=>{const p={open:0,replied:1,closed:2};return(p[a.status]||0)-(p[b.status]||0);});el.innerHTML=sorted.length?sorted.map(t=>`<div style="background:var(--bg);border-radius:10px;padding:11px 13px;margin-bottom:7px;border:0.5px solid ${t.status==='open'?'var(--r)':t.status==='replied'?'var(--a)':'var(--border)'}"><div style="display:flex;align-items:center;justify-content:space-between;flex-wrap:wrap;gap:6px"><div><div style="font-size:12px;font-weight:700">${t.title}</div><div style="font-size:10px;color:var(--muted);margin-top:1px">${t.client_name||'—'} · ${new Date(t.created_at).toLocaleDateString('ar-SA')} · ${stPill(t.status)}</div></div><div style="display:flex;gap:4px"><button class="btn sm bp" onclick="openTicket(${t.id})">رد / عرض</button>${t.status!=='closed'?`<button class="btn sm" style="color:var(--r)" onclick="closeTicketById(${t.id})">إغلاق</button>`:''}</div></div></div>`).join(''):'<div style="text-align:center;padding:16px;font-size:12px;color:var(--muted)">✓ لا توجد تذاكر</div>';}
function openNewTicket(){document.getElementById('modal-new-ticket').classList.add('open');const opts=D.clients.map(c=>`<option value="${c.id}">${c.hotel_name||c.name}</option>`).join('');document.getElementById('nt-client').innerHTML=opts;}
async function createTicket(){const cid=gv('nt-client');const c=D.clients.find(x=>x.id==cid);const r=await api('/api/admin/tickets/add',{title:gv('nt-title'),client_id:cid,client_name:c?.hotel_name||c?.name||'',category:gv('nt-cat'),priority:gv('nt-priority'),message:gv('nt-msg')});if(r.ok){D.tickets.push(r.ticket);rTickets();closeModal('modal-new-ticket');toast_('تم فتح التذكرة ✓');}}
function openTicket(id){const t=D.tickets.find(x=>x.id===id);if(!t)return;currentTicketId=id;ss('modal-ticket-title',t.title);const msgs=t.messages||[];document.getElementById('modal-ticket-body').innerHTML=`<div style="max-height:280px;overflow-y:auto;display:flex;flex-direction:column;gap:6px;padding:4px">`+msgs.map(m=>`<div style="padding:7px 10px;border-radius:8px;font-size:11px;max-width:85%;line-height:1.5;${m.from==='admin'?'background:var(--gl);color:var(--gd)':'background:var(--pl);color:var(--pd);margin-left:auto'}"><div style="font-size:9px;font-weight:700;margin-bottom:2px">${m.from==='admin'?'🛡️ الدعم':'العميل'}</div><div>${m.text}</div></div>`).join('')+'</div>';document.getElementById('modal-ticket').classList.add('open');}
async function sendTicketReply(){const text=gv('ticket-reply-text').trim();if(!text)return;const r=await api('/api/admin/tickets/reply',{id:currentTicketId,text});if(r.ok){const t=D.tickets.find(x=>x.id===currentTicketId);if(t){t.messages=t.messages||[];t.messages.push({from:'admin',name:'الدعم الفني',text,time:new Date().toISOString()});t.status='replied';}openTicket(currentTicketId);document.getElementById('ticket-reply-text').value='';toast_('تم الإرسال ✓');}}
async function closeTicket(){const r=await api('/api/admin/tickets/close',{id:currentTicketId});if(r.ok){const t=D.tickets.find(x=>x.id===currentTicketId);if(t)t.status='closed';closeModal('modal-ticket');rTickets();toast_('تم إغلاق التذكرة ✓');}}
async function closeTicketById(id){const r=await api('/api/admin/tickets/close',{id});if(r.ok){const t=D.tickets.find(x=>x.id===id);if(t)t.status='closed';rTickets();toast_('تم الإغلاق');}}

// ═══════════════════════════════════════════════
//  PLANS — PROFESSIONAL CUSTOMIZABLE
// ═══════════════════════════════════════════════
let localPlans = [];

const PLAN_COLORS = [
  {name:'أزرق احترافي',  hex:'#185FA5'},
  {name:'أخضر مميز',     hex:'#0F6E56'},
  {name:'بنفسجي راقي',  hex:'#534AB7'},
  {name:'ذهبي فاخر',    hex:'#854F0B'},
  {name:'وردي جريء',    hex:'#993556'},
  {name:'فيروزي منعش',  hex:'#0891B2'},
  {name:'أحمر طموح',    hex:'#A32D2D'},
  {name:'رمادي أنيق',   hex:'#5F5E5A'},
];

function rPlans(){
  localPlans = D.settings.plans || getDefaultPlans();
  renderPlansGrid();
  updatePlanStats();
  updateDiscPreview();
  // Fill contact info
  const s = D.settings;
  const cw=document.getElementById('cfg-whatsapp'); if(cw&&s.owner_whatsapp)cw.value=s.owner_whatsapp;
  const cp=document.getElementById('cfg-phone2');   if(cp&&s.owner_phone)cp.value=s.owner_phone;
  const cm=document.getElementById('cfg-contact-msg'); if(cm&&s.contact_message)cm.value=s.contact_message;
}

function getDefaultPlans(){
  return [
    {id:'starter',name:'المبتدئ',price:149,period:'شهري',color:'#0F6E56',badge:'',branch_fee:0,branch_enabled:false,pos_devices:1,max_guests:50,
     features:['حتى 50 نزيل شهرياً','جهاز نقاط دفع واحد','تكامل نظام إدارة واحد','تقارير أساسية يومية','فواتير بضريبة القيمة المضافة','نسخ احتياطي يدوي','جميع البيانات والتقارير يتم الاحتفاظ بها لدى العميل','دعم فني عبر التذاكر'],
     excluded:['مقارنة أسعار السوق','فروع متعددة','نسخ احتياطي تلقائي']},
    {id:'pro',name:'الاحترافية',price:299,period:'شهري',color:'#185FA5',badge:'الأكثر طلباً',branch_fee:0,branch_enabled:false,pos_devices:5,max_guests:0,
     features:['نزلاء غير محدود','حتى 5 أجهزة نقاط دفع','3 تكاملات نظام إدارة (Opera/Cloudbeds)','مقارنة أسعار السوق اليومية','ميزانية هرمية وتدفق نقدي','تقارير PDF وExcel','نسخ احتياطي تلقائي يومي','جميع البيانات والتقارير يتم الاحتفاظ بها لدى العميل','دعم فني 24/7 بأولوية'],
     excluded:['فروع متعددة','API مفتوح']},
    {id:'enterprise',name:'المؤسسية',price:799,period:'شهري',color:'#534AB7',badge:'للسلاسل',branch_fee:150,branch_enabled:true,pos_devices:0,max_guests:0,
     features:['نزلاء غير محدود','أجهزة نقاط دفع غير محدودة','تكاملات نظام إدارة غير محدودة','رسوم إضافية 150 ر.س لكل فرع مرتبط','إدارة مركزية لجميع الفروع','مقارنة أسعار السوق المتقدمة','تقارير موحدة للسلسلة','نسخ احتياطي فوري لحظي','جميع البيانات والتقارير يتم الاحتفاظ بها لدى العميل','API مفتوح للتكامل','مدير حساب مخصص','دعم مباشر أولوية قصوى'],
     excluded:[]},
  ];
}

function renderPlansGrid(){
  const grid = document.getElementById('plans-grid');
  if(!grid) return;
  grid.innerHTML = localPlans.map((pl, pi) => {
    const col     = pl.color || '#185FA5';
    const posText = pl.pos_devices === 0 ? 'غير محدود' : pl.pos_devices + (pl.pos_devices === 1 ? ' جهاز' : ' أجهزة');
    const guestText = pl.max_guests === 0 ? 'غير محدود' : pl.max_guests + ' نزيل/شهر';
    const feats   = (pl.features || []);
    const excl    = (pl.excluded || []);
    // Calculate discounts
    const dq = parseFloat(document.getElementById('disc-quarterly')?.value || 10);
    const ds_v = parseFloat(document.getElementById('disc-semi')?.value || 15);
    const da = parseFloat(document.getElementById('disc-annual')?.value || 20);
    const p3  = Math.round(pl.price * 3 * (1 - dq/100));
    const p6  = Math.round(pl.price * 6 * (1 - ds_v/100));
    const p12 = Math.round(pl.price * 12 * (1 - da/100));

    return `<div style="border-radius:14px;border:2px solid ${col}33;background:var(--card);position:relative;overflow:hidden;display:flex;flex-direction:column;">
      <!-- Color header bar -->
      <div style="height:5px;background:${col};border-radius:14px 14px 0 0;"></div>
      <!-- Badge -->
      ${pl.badge ? `<div style="position:absolute;top:14px;left:50%;transform:translateX(-50%);background:${col};color:#fff;font-size:9px;font-weight:700;padding:3px 12px;border-radius:20px;white-space:nowrap;box-shadow:0 2px 8px ${col}44;">${pl.badge}</div>` : ''}
      <div style="padding:14px 14px 10px;flex:1;display:flex;flex-direction:column;">
        <!-- Name + color picker -->
        <div style="display:flex;align-items:center;gap:6px;margin-bottom:${pl.badge?'18px':'8px'};">
          <input type="color" value="${col}" title="اختر لون الخطة"
            oninput="localPlans[${pi}].color=this.value;renderPlansGrid()"
            style="width:28px;height:28px;border:none;border-radius:6px;cursor:pointer;padding:2px;flex-shrink:0;"/>
          <input value="${pl.name}" style="font-size:14px;font-weight:500;color:${col};border:none;background:transparent;flex:1;outline:none;min-width:0;"
            onchange="localPlans[${pi}].name=this.value"
            onfocus="this.style.background='var(--bg)';this.style.borderRadius='6px'"
            onblur="this.style.background='transparent'"/>
          <select style="font-size:10px;border:0.5px solid var(--border);border-radius:6px;padding:2px 5px;background:var(--bg);color:var(--muted);"
            onchange="localPlans[${pi}].period=this.value">
            <option ${pl.period==='شهري'?'selected':''}>شهري</option>
            <option ${pl.period==='سنوي'?'selected':''}>سنوي</option>
          </select>
        </div>
        <!-- Price -->
        <div style="display:flex;align-items:baseline;gap:5px;margin-bottom:6px;">
          <input type="number" value="${pl.price}" min="0"
            style="width:80px;border:1.5px solid ${col};border-radius:8px;padding:5px 7px;font-size:22px;font-weight:500;color:${col};background:var(--card);text-align:center;"
            onchange="localPlans[${pi}].price=parseFloat(this.value||0);updateDiscPreview();updatePlanStats()"/>
          <span style="font-size:11px;color:var(--muted);">ر.س / ${pl.period}</span>
        </div>
        <!-- Discount preview for this plan -->
        <div style="background:${col}11;border-radius:7px;padding:5px 8px;margin-bottom:8px;font-size:9px;color:var(--muted);">
          <div style="display:flex;justify-content:space-between;"><span>ربع سنوي:</span><span style="font-weight:500;color:${col}">${p3} ر.س</span></div>
          <div style="display:flex;justify-content:space-between;"><span>نصف سنوي:</span><span style="font-weight:500;color:${col}">${p6} ر.س</span></div>
          <div style="display:flex;justify-content:space-between;"><span>سنوي:</span><span style="font-weight:500;color:${col}">${p12} ر.س</span></div>
        </div>
        <!-- Specs row -->
        <div style="display:grid;grid-template-columns:1fr 1fr;gap:4px;margin-bottom:8px;">
          <div style="background:${col}11;border-radius:7px;padding:6px 8px;text-align:center;">
            <div style="font-size:12px;font-weight:500;color:${col};">${guestText}</div>
            <div style="font-size:9px;color:var(--muted);">النزلاء</div>
          </div>
          <div style="background:${col}11;border-radius:7px;padding:6px 8px;text-align:center;">
            <div style="font-size:12px;font-weight:500;color:${col};">${posText}</div>
            <div style="font-size:9px;color:var(--muted);">نقاط الدفع</div>
          </div>
        </div>
        ${pl.branch_enabled ? `<div style="background:${col}22;border:1px solid ${col}44;border-radius:7px;padding:5px 8px;margin-bottom:8px;font-size:10px;color:${col};font-weight:500;">🏢 فروع متعددة — ${pl.branch_fee} ر.س/فرع</div>` : ''}
        <!-- Features editable -->
        <div style="margin-bottom:6px;">
          <div style="font-size:10px;font-weight:500;color:var(--muted);margin-bottom:4px;">البنود (سطر لكل بند)</div>
          <textarea rows="7" style="width:100%;border:0.5px solid ${col}44;border-radius:7px;padding:6px 8px;font-size:10px;background:${col}08;color:var(--text);resize:vertical;font-family:inherit;line-height:1.6;"
            onchange="localPlans[${pi}].features=this.value.split('\\n').filter(Boolean)">${feats.join('\n')}</textarea>
        </div>
        ${excl.length > 0 ? `<div style="margin-bottom:6px;"><div style="font-size:9px;color:var(--muted);margin-bottom:3px;">غير متضمن:</div><div style="font-size:9px;color:var(--muted);">${excl.map(e=>`✗ ${e}`).join(' · ')}</div></div>` : ''}
        <!-- Badge editor -->
        <div style="display:flex;gap:4px;margin-bottom:6px;">
          <input value="${pl.badge||''}" placeholder="شارة (اختياري)..." style="flex:1;font-size:10px;border:0.5px solid var(--border);border-radius:6px;padding:4px 7px;background:var(--bg);color:var(--text);"
            onchange="localPlans[${pi}].badge=this.value;renderPlansGrid()"/>
        </div>
        <!-- Advanced controls -->
        <div style="display:grid;grid-template-columns:1fr 1fr;gap:4px;margin-bottom:6px;">
          <div>
            <div style="font-size:9px;color:var(--muted);margin-bottom:2px;">أجهزة نقاط الدفع</div>
            <input type="number" value="${pl.pos_devices}" min="0" title="0=غير محدود"
              style="width:100%;font-size:11px;border:0.5px solid var(--border);border-radius:6px;padding:4px 6px;background:var(--bg);color:var(--text);"
              onchange="localPlans[${pi}].pos_devices=parseInt(this.value||0);renderPlansGrid()"/>
          </div>
          <div>
            <div style="font-size:9px;color:var(--muted);margin-bottom:2px;">حد النزلاء (0=∞)</div>
            <input type="number" value="${pl.max_guests}" min="0"
              style="width:100%;font-size:11px;border:0.5px solid var(--border);border-radius:6px;padding:4px 6px;background:var(--bg);color:var(--text);"
              onchange="localPlans[${pi}].max_guests=parseInt(this.value||0);renderPlansGrid()"/>
          </div>
          <div>
            <div style="font-size:9px;color:var(--muted);margin-bottom:2px;">رسوم الفرع (ر.س)</div>
            <input type="number" value="${pl.branch_fee||0}" min="0"
              style="width:100%;font-size:11px;border:0.5px solid var(--border);border-radius:6px;padding:4px 6px;background:var(--bg);color:var(--text);"
              onchange="localPlans[${pi}].branch_fee=parseFloat(this.value||0);renderPlansGrid()"/>
          </div>
          <div style="display:flex;align-items:flex-end;padding-bottom:2px;">
            <label style="display:flex;align-items:center;gap:5px;font-size:10px;color:var(--muted);cursor:pointer;">
              <input type="checkbox" ${pl.branch_enabled?'checked':''} style="width:auto;accent-color:${col};"
                onchange="localPlans[${pi}].branch_enabled=this.checked;renderPlansGrid()"/>
              تفعيل الفروع
            </label>
          </div>
        </div>
        <!-- Action buttons -->
        <div style="display:flex;gap:5px;margin-top:auto;padding-top:6px;border-top:0.5px solid var(--border);">
          <button class="btn sm bg2" onclick="movePlan(${pi},-1)" style="flex:0" title="رفع">↑</button>
          <button class="btn sm bg2" onclick="movePlan(${pi},1)" style="flex:0" title="نزول">↓</button>
          <button class="btn sm" onclick="duplicatePlan('${pl.id}')" style="flex:1">نسخ</button>
          <button class="btn sm br2" onclick="deletePlan('${pl.id}')" style="flex:1">حذف</button>
        </div>
      </div>
    </div>`;
  }).join('');
}

function movePlan(idx, dir){
  const newIdx = idx + dir;
  if(newIdx < 0 || newIdx >= localPlans.length) return;
  const tmp = localPlans[idx];
  localPlans[idx] = localPlans[newIdx];
  localPlans[newIdx] = tmp;
  renderPlansGrid();
}

function updatePlanStats(){
  const prices = {};
  localPlans.forEach(p => prices[p.id] = p.price);
  const active_clients = D.clients.filter(c => c.status === 'active');
  const mrr = active_clients.reduce((a, c) => a + (prices[c.plan] || 0), 0);
  const el = document.getElementById('plans-stats');
  if(!el) return;
  el.innerHTML = `
    <div class="gmc gmc-g"><span class="gm-ic">💰</span><div class="gm-val">${F(mrr)}</div><div class="gm-lbl">MRR الحالي ر.س</div></div>
    <div class="gmc gmc-b"><span class="gm-ic">💎</span><div class="gm-val">${localPlans.length}</div><div class="gm-lbl">عدد الخطط</div></div>
    <div class="gmc gmc-u"><span class="gm-ic">🏢</span><div class="gm-val">${D.clients.filter(c=>c.plan==='enterprise').length}</div><div class="gm-lbl">مؤسسية</div></div>
    <div class="gmc gmc-a"><span class="gm-ic">📊</span><div class="gm-val">${F(mrr*12)}</div><div class="gm-lbl">ARR السنوي ر.س</div></div>`;
}

function updateDiscPreview(){
  const dq = parseFloat(document.getElementById('disc-quarterly')?.value || 10);
  const ds_v = parseFloat(document.getElementById('disc-semi')?.value || 15);
  const da = parseFloat(document.getElementById('disc-annual')?.value || 20);
  const el = document.getElementById('disc-preview');
  if(!el || !localPlans.length) return;
  const plan = localPlans.find(p=>p.id==='pro') || localPlans[0];
  if(!plan) return;
  el.innerHTML = `
    مثال على خطة "${plan.name}" (${plan.price} ر.س/شهر):<br/>
    ربع سنوي: <b style="color:var(--g)">${Math.round(plan.price*3*(1-dq/100))} ر.س</b> (توفير ${Math.round(plan.price*3*dq/100)} ر.س) ·
    نصف سنوي: <b style="color:var(--g)">${Math.round(plan.price*6*(1-ds_v/100))} ر.س</b> (توفير ${Math.round(plan.price*6*ds_v/100)} ر.س) ·
    سنوي: <b style="color:var(--g)">${Math.round(plan.price*12*(1-da/100))} ر.س</b> (توفير ${Math.round(plan.price*12*da/100)} ر.س)`;
  renderPlansGrid();
}

async function savePlans(){
  const prices = {};
  localPlans.forEach(p => prices[p.id] = p.price);
  const disc_q = parseFloat(document.getElementById('disc-quarterly')?.value || 10);
  const disc_s = parseFloat(document.getElementById('disc-semi')?.value || 15);
  const disc_a = parseFloat(document.getElementById('disc-annual')?.value || 20);
  const r = await api('/api/admin/settings/save', {
    plans: localPlans, prices,
    discount_quarterly: disc_q,
    discount_semi: disc_s,
    discount_annual: disc_a,
  });
  if(r.ok){
    D.settings.plans = localPlans;
    D.settings.prices = prices;
    D.settings.discount_quarterly = disc_q;
    D.settings.discount_semi = disc_s;
    D.settings.discount_annual = disc_a;
    toast_('✅ تم حفظ جميع الباقات والأسعار');
    updatePlanStats();
  }
}

function addNewPlan(){
  document.getElementById('new-plan-form').style.display = 'block';
  document.getElementById('new-plan-form').scrollIntoView({behavior:'smooth'});
}

async function submitNewPlan(){
  const name = document.getElementById('np-name')?.value?.trim();
  if(!name){ toast_('أدخل اسم الخطة', false); return; }
  const feats = (document.getElementById('np-features')?.value || '').split('\n').filter(Boolean);
  const excl  = (document.getElementById('np-excluded')?.value || '').split('\n').filter(Boolean);
  const r = await api('/api/admin/plans/add', {
    name, price: parseFloat(document.getElementById('np-price')?.value || 0),
    color: document.getElementById('np-color')?.value || '#185FA5',
    badge: document.getElementById('np-badge')?.value || '',
    pos_devices: parseInt(document.getElementById('np-pos')?.value || 1),
    max_guests:  parseInt(document.getElementById('np-guests')?.value || 0),
    branch_fee:  parseFloat(document.getElementById('np-branch-fee')?.value || 0),
    branch_enabled: document.getElementById('np-branch-en')?.checked || false,
    period: 'شهري', features: feats, excluded: excl,
  });
  if(r.ok){
    if(!D.settings.plans) D.settings.plans = [];
    D.settings.plans.push(r.plan);
    localPlans = D.settings.plans;
    document.getElementById('new-plan-form').style.display = 'none';
    ['np-name','np-price','np-badge','np-pos','np-guests','np-branch-fee'].forEach(id => { const e=document.getElementById(id); if(e)e.value=''; });
    renderPlansGrid();
    toast_(`✅ تم إضافة خطة "${name}"`);
  }
}

async function deletePlan(pid){
  if(!confirm('حذف هذه الخطة؟ لن يمكن التراجع عن هذا.')) return;
  const r = await api('/api/admin/plans/delete', {id: pid});
  if(r.ok){
    D.settings.plans = (D.settings.plans || []).filter(p => p.id !== pid);
    localPlans = D.settings.plans;
    renderPlansGrid();
    updatePlanStats();
    toast_('تم الحذف');
  }
}

async function duplicatePlan(pid){
  const r = await api('/api/admin/plans/duplicate', {id: pid});
  if(r.ok){
    if(!D.settings.plans) D.settings.plans = [];
    D.settings.plans.push(r.plan);
    localPlans = D.settings.plans;
    renderPlansGrid();
    updatePlanStats();
    toast_('✅ تم نسخ الخطة');
  }
}

async function saveContactInfo(){
  const r = await api('/api/admin/settings/save', {
    owner_whatsapp: document.getElementById('cfg-whatsapp')?.value || '',
    owner_phone:    document.getElementById('cfg-phone2')?.value || '',
    contact_message: document.getElementById('cfg-contact-msg')?.value || '',
  });
  if(r.ok) toast_('تم حفظ معلومات التواصل ✓');
}


// ═══════════════════════════════════════════════
//  BRANCHES
// ═══════════════════════════════════════════════
function buildBranchSelect(){const opts=D.clients.filter(c=>!c.is_branch).map(c=>`<option value="${c.id}">${c.hotel_name||c.name}</option>`).join('');const sel=document.getElementById('br-parent');if(sel)sel.innerHTML=opts;}
function rBranches(){buildBranchSelect();const branches=D.clients.filter(c=>c.is_branch);const parents=D.clients.filter(c=>!c.is_branch);ss('br-total',branches.length);ss('br-active',branches.filter(b=>b.status==='active').length);ss('br-groups',parents.filter(p=>(p.branches||[]).length>0||branches.some(b=>String(b.parent_id)===String(p.id))).length);const prices=D.settings.prices||{pro:299,enterprise:799};ss('br-mrr',F(branches.filter(b=>b.status==='active').reduce((a,b)=>a+(prices[b.plan]||0),0)));const tree=document.getElementById('branches-tree');if(!tree)return;tree.innerHTML=parents.map(p=>{const myBr=branches.filter(b=>String(b.parent_id)===String(p.id));const col={free:'#5F5E5A',pro:'#185FA5',enterprise:'#534AB7',trial:'#854F0B'}[p.plan]||'#374151';return`<div style="margin-bottom:12px"><div style="display:flex;align-items:center;gap:10px;padding:10px 12px;background:var(--bg);border-radius:10px;border:1px solid ${col}30;flex-wrap:wrap"><div style="width:32px;height:32px;border-radius:50%;background:${col}22;display:flex;align-items:center;justify-content:center;font-size:13px;font-weight:700;color:${col};flex-shrink:0">${(p.hotel_name||p.name).charAt(0)}</div><div style="flex:1;min-width:0"><div style="font-size:13px;font-weight:700">👑 ${p.hotel_name||p.name}</div><div style="font-size:10px;color:var(--muted)">${p.email||'—'} · ${myBr.length} فرع</div></div><div style="display:flex;gap:5px;flex-wrap:wrap">${stPill(p.status)}${planPill(p.plan)}<button class="btn sm bp" onclick="showBranchAdd(${p.id})">+ فرع</button></div></div>${myBr.map(b=>`<div style="margin-right:24px;margin-top:5px;display:flex;align-items:center;gap:8px;padding:8px 12px;background:var(--card);border-radius:9px;border:0.5px solid var(--border);flex-wrap:wrap"><div style="width:4px;height:36px;background:${col}40;border-radius:2px;flex-shrink:0"></div><div style="width:26px;height:26px;border-radius:50%;background:var(--bg);display:flex;align-items:center;justify-content:center;font-size:11px;font-weight:700;color:${col};flex-shrink:0">${(b.hotel_name||b.name).charAt(0)}</div><div style="flex:1;min-width:0"><div style="font-size:12px;font-weight:700">🏢 ${b.hotel_name||b.name}</div><div style="font-size:9px;color:var(--muted)">${b.email||'—'} · ${b.city||'—'} · ${b.rooms||0} وحدة</div></div><div style="display:flex;gap:4px;flex-wrap:wrap">${stPill(b.status)}<button class="btn sm" onclick="showClientDetail(${b.id})">تفاصيل</button><button class="btn sm bg2" onclick="showExtend(${b.id})">تمديد</button><button class="btn sm br2" onclick="deleteBranch(${b.id})">حذف</button></div></div>`).join('')}</div>`;}).join('')||'<div style="text-align:center;padding:14px;font-size:12px;color:var(--muted)">لا يوجد عملاء بعد</div>';}
function showBranchAdd(parentId){const sel=document.getElementById('br-parent');if(sel)sel.value=parentId;document.querySelector('#pg-branches .card.cg')?.scrollIntoView({behavior:'smooth'});}
async function addBranch(){const parentId=gv('br-parent');const name=gv('br-name').trim();if(!parentId||!name){toast_('اختر الحساب وأدخل الاسم',false);return;}const parent=D.clients.find(c=>String(c.id)===String(parentId));const r=await api('/api/admin/branches/add',{parent_id:parentId,parent_name:parent?.hotel_name||'',name,hotel_name:gv('br-hotel')||name,email:gv('br-email'),city:gv('br-city'),hotel_type:'hotel',rooms:gv('br-rooms')||0});if(r.ok){D.clients.push(r.branch);if(parent){parent.branches=parent.branches||[];parent.branches.push(String(r.branch.id));}buildClientSelects();rBranches();toast_(`تم إضافة فرع "${r.branch.hotel_name}" ✓`);['br-name','br-hotel','br-email','br-rooms'].forEach(id=>{const e=document.getElementById(id);if(e)e.value='';});}}
async function deleteBranch(id){if(!confirm('حذف هذا الفرع؟'))return;const r=await api('/api/admin/branches/delete',{id});if(r.ok){D.clients=D.clients.filter(c=>c.id!==id);rBranches();toast_('تم الحذف');}}

// ═══════════════════════════════════════════════
//  MARKET AI
// ═══════════════════════════════════════════════
function rMarket(){const comps=(D.settings&&D.settings.ai_market_competitors)||[];renderCompetitors(comps);const last=D.settings&&D.settings.last_market_analysis;if(last){showAdvantage(last.advantage||[],last.gap||'',last.positioning||'');}}
function renderCompetitors(comps){const el=document.getElementById('competitors-list');if(!el)return;const mL={enterprise:'Enterprise 🏢',mid:'Mid Market 🏨',budget:'Budget 💰'};const mC={enterprise:'var(--u)',mid:'var(--p)',budget:'var(--g)'};el.innerHTML=comps.length?comps.map((c,i)=>`<div style="background:var(--bg);border-radius:10px;padding:11px 13px;margin-bottom:7px;border:0.5px solid var(--border)"><div style="display:flex;align-items:flex-start;justify-content:space-between;flex-wrap:wrap;gap:6px"><div><div style="font-size:12px;font-weight:700">${c.name}</div><div style="font-size:10px;color:var(--muted);margin-top:1px">${c.target||'—'}</div><div style="margin-top:4px;display:flex;gap:5px">${c.price_from||c.price_to?`<span style="font-size:10px;font-weight:700;color:var(--g)">${c.price_from||0}–${c.price_to||0} ${c.currency||''}</span>`:''}<span style="font-size:9px;padding:2px 7px;border-radius:20px;background:${mC[c.market]||'var(--pl)'}22;color:${mC[c.market]||'var(--p)'};font-weight:700">${mL[c.market]||c.market}</span></div></div><button class="btn sm br2" onclick="delCompetitor(${i})">حذف</button></div><div style="display:grid;grid-template-columns:1fr 1fr;gap:6px;margin-top:7px"><div><div style="font-size:10px;font-weight:700;color:var(--g);margin-bottom:2px">✓ نقاط قوتهم</div>${(c.strengths||[]).map(s=>`<div style="font-size:10px;color:var(--muted)">• ${s}</div>`).join('')}</div><div><div style="font-size:10px;font-weight:700;color:var(--r);margin-bottom:2px">✗ نقاط ضعفهم</div>${(c.weaknesses||[]).map(w=>`<div style="font-size:10px;color:var(--muted)">• ${w}</div>`).join('')}</div></div></div>`).join(''):'<div style="text-align:center;padding:14px;font-size:12px;color:var(--muted)">اضغط "تحليل الآن" لجلب المنافسين</div>';}
function showAdvantage(adv,gap,pos){const card=document.getElementById('our-advantage-card');if(card)card.style.display='block';const el=document.getElementById('our-advantages');if(!el)return;el.innerHTML=adv.map(a=>`<div style="background:var(--gl);border-radius:7px;padding:7px 10px;margin-bottom:5px;font-size:11px;color:var(--gd)">${a}</div>`).join('')+(gap?`<div style="background:var(--al);border-radius:7px;padding:7px 10px;margin-top:6px;font-size:11px;color:var(--ad)"><b>فرصة السوق:</b> ${gap}</div>`:'')+(pos?`<div style="background:var(--pl);border-radius:7px;padding:7px 10px;margin-top:5px;font-size:11px;color:var(--pd)"><b>موقعنا السعري:</b> ${pos}</div>`:'');}
async function runMarketAI(){const btn=document.getElementById('ai-analyze-btn');if(btn){btn.textContent='⏳ جارٍ التحليل...';btn.disabled=true;}const key=gv('mkt-claude-key')||D.settings.claude_key||'';const r=await api('/api/admin/market/ai',{claude_key:key});if(btn){btn.textContent='🔍 تحليل الآن';btn.disabled=false;}if(r.ok){D.settings.ai_market_competitors=r.competitors||[];D.settings.last_market_analysis={advantage:r.our_advantage||[],gap:r.market_gap||'',positioning:r.price_positioning||''};renderCompetitors(r.competitors||[]);showAdvantage(r.our_advantage||[],r.market_gap||'',r.price_positioning||'');toast_(`تم تحليل ${(r.competitors||[]).length} منافس ✓`);const res=document.getElementById('mkt-ai-result');if(res)res.innerHTML=`<div style="background:var(--gl);border-radius:8px;padding:8px 10px;font-size:11px;color:var(--gd)">✅ تم — المصدر: ${r.source||'بيانات مدمجة'}</div>`;}else toast_(r.error||'فشل التحليل',false);}
async function saveClaudeKey(){const key=gv('mkt-claude-key').trim();if(!key)return;await api('/api/admin/settings/save',{claude_key:key});D.settings.claude_key=key;toast_('تم حفظ مفتاح AI ✓');}
function toggleAddComp(){const f=document.getElementById('add-comp-form');f.style.display=f.style.display==='none'?'block':'none';}
async function addCompetitor(){const name=gv('comp-name').trim();if(!name){toast_('أدخل الاسم',false);return;}const r=await api('/api/admin/competitors/add',{name,price_from:parseFloat(gv('comp-pfrom')||0),price_to:parseFloat(gv('comp-pto')||0),currency:gv('comp-curr')||'USD/month',target:gv('comp-target'),market:gv('comp-market'),strengths:gv('comp-str').split(',').map(s=>s.trim()).filter(Boolean),weaknesses:gv('comp-wk').split(',').map(s=>s.trim()).filter(Boolean)});if(r.ok){if(!D.settings.ai_market_competitors)D.settings.ai_market_competitors=[];D.settings.ai_market_competitors.push({name,price_from:parseFloat(gv('comp-pfrom')||0),price_to:parseFloat(gv('comp-pto')||0),currency:gv('comp-curr')||'USD/month',target:gv('comp-target'),market:gv('comp-market'),strengths:gv('comp-str').split(',').map(s=>s.trim()).filter(Boolean),weaknesses:gv('comp-wk').split(',').map(s=>s.trim()).filter(Boolean)});renderCompetitors(D.settings.ai_market_competitors);toggleAddComp();toast_('تم ✓');}}
async function delCompetitor(i){const r=await api('/api/admin/competitors/delete',{index:i});if(r.ok){D.settings.ai_market_competitors.splice(i,1);renderCompetitors(D.settings.ai_market_competitors);toast_('تم الحذف');}}

// ═══════════════════════════════════════════════
//  SETTINGS
// ═══════════════════════════════════════════════
function rSettings(){const s=D.settings;const map={'cfg-owner-name':'owner_name','cfg-owner-email':'owner_email','cfg-owner-phone':'owner_phone','cfg-system-name':'system_name','cfg-bank-name':'bank_name','cfg-bank-iban':'bank_iban','cfg-trial-days':'trial_days'};Object.entries(map).forEach(([id,k])=>{const el=document.getElementById(id);if(el&&s[k]!==undefined)el.value=s[k];});const p=s.prices||{};['cfg-price-free','cfg-price-pro','cfg-price-ent'].forEach((id,i)=>{const el=document.getElementById(id);if(el)el.value={0:p.free||0,1:p.pro||299,2:p.enterprise||799}[i];});}
async function saveSettings(){const r=await api('/api/admin/settings/save',{owner_name:gv('cfg-owner-name'),owner_email:gv('cfg-owner-email'),owner_phone:gv('cfg-owner-phone'),system_name:gv('cfg-system-name'),bank_name:gv('cfg-bank-name'),bank_iban:gv('cfg-bank-iban'),trial_days:parseInt(gv('cfg-trial-days')||15),prices:{free:0,pro:parseFloat(gv('cfg-price-pro')||299),enterprise:parseFloat(gv('cfg-price-ent')||799)}});if(r.ok){Object.assign(D.settings,{owner_name:gv('cfg-owner-name'),owner_email:gv('cfg-owner-email'),system_name:gv('cfg-system-name')});ss('sb-owner-name',gv('cfg-owner-name'));ss('sb-owner-email',gv('cfg-owner-email'));ss('sb-sys-name',gv('cfg-system-name'));toast_('تم حفظ الإعدادات ✓');}}

async function refresh(){await boot();toast_('تم التحديث ✓');}

// ═══════════════════════════════════════════════
//  UPDATE UPLOAD ENGINE
// ═══════════════════════════════════════════════
let selectedFile = null;

function handleFileSelect(event){
  const file = event.target.files[0];
  if(file) previewFile(file);
}
function handleFileDrop(event){
  const file = event.dataTransfer.files[0];
  if(file) previewFile(file);
}
function previewFile(file){
  selectedFile = file;
  const allowed = ['main.py','main_admin.py','unified_server.py'];
  const safe    = file.name.split('/').pop().split('\\').pop();
  const ok      = allowed.includes(safe);
  const preview = document.getElementById('file-preview');
  const nameEl  = document.getElementById('fp-name');
  const metaEl  = document.getElementById('fp-meta');
  const statusEl= document.getElementById('fp-status');
  const btnEl   = document.getElementById('upload-btn');
  if(preview) preview.style.display = 'block';
  if(nameEl)  nameEl.textContent = safe;
  if(metaEl)  metaEl.textContent = `الحجم: ${(file.size/1024).toFixed(1)} KB · النوع: ${file.type||'text/plain'}`;
  if(statusEl){
    statusEl.textContent = ok ? '✅ ملف مدعوم' : '❌ اسم الملف غير مدعوم';
    statusEl.style.color = ok ? 'var(--g)' : 'var(--r)';
  }
  if(btnEl) btnEl.disabled = !ok;
}

async function uploadFile(){
  if(!selectedFile){ toast_('اختر ملفاً أولاً', false); return; }
  const btn = document.getElementById('upload-btn');
  if(btn){ btn.textContent = '⏳ جارٍ الرفع والفحص...'; btn.disabled = true; }
  try{
    const reader = new FileReader();
    reader.onload = async(e) => {
      const base64 = e.target.result.split(',')[1];
      const r = await api('/api/admin/update/upload', {
        file_data: base64,
        file_name: selectedFile.name,
        description: document.getElementById('update-desc')?.value || '',
      });
      const resultEl = document.getElementById('upload-result');
      if(resultEl){
        resultEl.style.display = 'block';
        if(r.ok){
          resultEl.style.background = 'var(--gl)';
          resultEl.style.border = '0.5px solid #6EE7B7';
          resultEl.innerHTML = `
            <div style="font-size:13px;font-weight:500;color:var(--gd);margin-bottom:6px;">✅ تم رفع التحديث بنجاح!</div>
            <div style="font-size:11px;color:var(--gd);line-height:1.8;">
              الملف: <b>${r.file}</b><br/>
              الحجم: <b>${r.size_kb} KB</b><br/>
              MD5: <code style="background:var(--bg);padding:1px 5px;border-radius:4px;font-family:monospace;">${r.md5}</code><br/>
              <br/>
              <b>⚠️ مهم:</b> ${r.message}
            </div>
            <div style="margin-top:8px;padding:8px 10px;background:var(--al);border-radius:7px;font-size:11px;color:var(--ad);">
              لتفعيل التحديث على Render: اذهب للوحة Render → Manual Deploy ← أو سيتحدث تلقائياً من GitHub خلال دقائق
            </div>`;
        } else {
          resultEl.style.background = 'var(--rl)';
          resultEl.style.border = '0.5px solid #FCA5A5';
          resultEl.innerHTML = `<div style="font-size:13px;font-weight:500;color:var(--rd);">❌ فشل الرفع</div><div style="font-size:11px;color:var(--rd);margin-top:4px;">${r.error}</div>`;
        }
      }
      await loadUpdateHistory();
      if(btn){ btn.textContent = '📤 رفع التحديث للخادم'; btn.disabled = false; }
    };
    reader.readAsDataURL(selectedFile);
  } catch(e) {
    toast_('خطأ في الرفع: ' + e.message, false);
    if(btn){ btn.textContent = '📤 رفع التحديث للخادم'; btn.disabled = false; }
  }
}

async function loadUpdateHistory(){
  const r = await api('/api/admin/update/status', {});
  const el = document.getElementById('update-history-list');
  if(!el) return;
  const history = r.history || [];
  if(!history.length){
    el.innerHTML = '<div style="text-align:center;padding:14px;font-size:11px;color:var(--muted);">لا توجد تحديثات مسجلة</div>';
    return;
  }
  el.innerHTML = [...history].reverse().map(h => `
    <div style="display:flex;align-items:center;gap:10px;padding:8px 0;border-bottom:0.5px solid var(--border);">
      <div style="font-size:18px;">🐍</div>
      <div style="flex:1;min-width:0;">
        <div style="font-size:11px;font-weight:500;color:var(--text);">${h.file}</div>
        <div style="font-size:10px;color:var(--muted);margin-top:1px;">${h.description||'—'} · ${h.size_kb} KB · ${h.lines} سطر · MD5: ${h.md5}</div>
      </div>
      <div style="font-size:9px;color:var(--muted);white-space:nowrap;">${new Date(h.uploaded_at).toLocaleString('ar-SA')}</div>
      <span style="font-size:9px;padding:2px 7px;border-radius:20px;background:var(--gl);color:var(--gd);font-weight:500;">✓ مثبّت</span>
    </div>`).join('');
}

async function logout(){await api('/api/admin/logout',{});location.reload();}
</script>
</body>
</html>"""

# ══════════════════════════════════════════════════════════════
#  تشغيل الخادم
# ══════════════════════════════════════════════════════════════


def _build_html():
    return r"""<!DOCTYPE html>
<html lang="ar" dir="rtl">
<head>
<meta charset="UTF-8"/>
<meta name="viewport" content="width=device-width,initial-scale=1"/>
<title>نظام إدارة الفندق v3</title>
<style>
*{box-sizing:border-box;margin:0;padding:0;font-family:system-ui,'Segoe UI',Arial,sans-serif;direction:rtl;}
:root{
  --p:#1A56DB;--pl:#EEF2FF;--pd:#1E40AF;
  --g:#047857;--gl:#ECFDF5;--gd:#065F46;
  --r:#DC2626;--rl:#FEF2F2;--rd:#991B1B;
  --a:#D97706;--al:#FFFBEB;--ad:#92400E;
  --u:#7C3AED;--ul:#F5F3FF;--ud:#4C1D95;
  --t:#0891B2;--tl:#E0F2FE;--td:#075985;
  --c:#EA580C;--cl:#FFF7ED;--cd:#7C2D12;
  --n:#374151;--nl:#F9FAFB;--nd:#111827;
  --pk:#DB2777;--pkl:#FDF2F8;--pkd:#831843;
  --bg:#F1F5F9;--card:#FFFFFF;--border:#E2E8F0;--text:#0F172A;--muted:#64748B;--sbg:#0F172A;
}
html,body{height:100%;overflow:hidden;}
.app{display:grid;grid-template-columns:200px 1fr;height:100vh;background:var(--bg);}

/* ── SIDEBAR ── */
.sb{background:var(--sbg);display:flex;flex-direction:column;overflow-y:auto;height:100vh;}
.sb-logo{padding:16px 14px 12px;border-bottom:1px solid rgba(255,255,255,.08);}
.sb-hotel{font-size:14px;font-weight:700;color:#F8FAFC;letter-spacing:-.3px;}
.sb-sub{font-size:9px;color:rgba(255,255,255,.35);margin-top:2px;letter-spacing:.4px;}
.sb-live{display:flex;align-items:center;gap:5px;margin-top:6px;}
.sb-dot{width:6px;height:6px;border-radius:50%;background:#10B981;box-shadow:0 0 6px #10B981;animation:pulse 2s infinite;}
@keyframes pulse{0%,100%{opacity:1;transform:scale(1)}50%{opacity:.6;transform:scale(.85)}}
.sb-live-t{font-size:9px;color:#10B981;font-weight:600;letter-spacing:.3px;}
.sb-sec{padding:10px 12px 3px;font-size:8px;font-weight:700;color:rgba(255,255,255,.25);letter-spacing:1px;text-transform:uppercase;}
.ni{display:flex;align-items:center;gap:8px;padding:7px 12px;cursor:pointer;border-radius:8px;margin:1px 6px;color:rgba(255,255,255,.55);font-size:11px;transition:all .12s;position:relative;}
.ni:hover{background:rgba(255,255,255,.07);color:rgba(255,255,255,.9);}
.ni.on{background:linear-gradient(135deg,rgba(26,86,219,.8),rgba(124,58,237,.6));color:#fff;box-shadow:0 2px 8px rgba(26,86,219,.3);}
.ni-ic{font-size:14px;width:20px;text-align:center;flex-shrink:0;}
.ni-b{margin-right:auto;background:#DC2626;color:#fff;font-size:8px;padding:1px 5px;border-radius:10px;font-weight:700;}
.sb-foot{margin-top:auto;padding:12px 14px;border-top:1px solid rgba(255,255,255,.06);}
.sb-user{font-size:11px;color:#F8FAFC;font-weight:600;}
.sb-role{font-size:9px;color:rgba(255,255,255,.35);margin-top:1px;}

/* ── MAIN ── */
.main{display:flex;flex-direction:column;height:100vh;overflow:hidden;}
.topbar{background:var(--card);padding:10px 16px;border-bottom:1px solid var(--border);display:flex;align-items:center;justify-content:space-between;gap:8px;flex-shrink:0;flex-wrap:wrap;box-shadow:0 1px 3px rgba(0,0,0,.06);}
.tb-l{display:flex;align-items:center;gap:10px;}
.tb-ic{width:32px;height:32px;border-radius:10px;display:flex;align-items:center;justify-content:center;font-size:16px;flex-shrink:0;}
.tb-t{font-size:13px;font-weight:700;color:var(--text);}
.tb-r{display:flex;align-items:center;gap:6px;flex-wrap:wrap;}
.badge-date{font-size:10px;padding:4px 10px;border-radius:20px;border:1px solid var(--border);color:var(--muted);background:var(--bg);}
.badge-cd{font-size:10px;padding:4px 10px;border-radius:20px;background:#1E40AF;color:#fff;font-weight:700;font-family:monospace;letter-spacing:.5px;}
.season-badge{display:inline-flex;align-items:center;gap:4px;padding:4px 10px;border-radius:20px;font-size:10px;font-weight:700;}
.search-wrap{position:relative;}
#search-box{width:200px;border:1.5px solid var(--border);border-radius:20px;padding:5px 14px;font-size:11px;background:var(--bg);color:var(--text);transition:border-color .15s;}
#search-box:focus{outline:none;border-color:var(--p);background:var(--card);}
#search-res{display:none;position:absolute;top:36px;right:0;width:320px;background:var(--card);border:1px solid var(--border);border-radius:10px;box-shadow:0 8px 30px rgba(0,0,0,.12);z-index:999;max-height:300px;overflow-y:auto;padding:5px;}

/* ── CONTENT ── */
.content{padding:14px;overflow-y:auto;flex:1;}
.pg{display:none;}.pg.on{display:block;}

/* ── BEAUTIFUL METRIC CARDS ── */
.kg4{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:10px;margin-bottom:12px;}
.kg3{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:10px;margin-bottom:12px;}
.kg2{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:10px;margin-bottom:12px;}

/* Gradient metric cards */
.gmc{border-radius:14px;padding:16px 18px;position:relative;overflow:hidden;min-height:90px;}
.gmc::before{content:'';position:absolute;top:-20px;right:-20px;width:80px;height:80px;border-radius:50%;opacity:.15;}
.gmc .gm-icon{font-size:22px;margin-bottom:8px;display:block;}
.gmc .gm-val{font-size:20px;font-weight:700;line-height:1.1;}
.gmc .gm-lbl{font-size:10px;font-weight:600;opacity:.8;margin-top:3px;}
.gmc .gm-sub{font-size:9px;opacity:.65;margin-top:2px;}
.gmc .gm-trend{position:absolute;top:14px;left:14px;font-size:10px;font-weight:700;padding:3px 8px;border-radius:20px;}

/* Color variants */
.gmc-blue{background:linear-gradient(135deg,#1A56DB,#3B82F6);color:#fff;}
.gmc-blue::before{background:#fff;}
.gmc-green{background:linear-gradient(135deg,#047857,#10B981);color:#fff;}
.gmc-green::before{background:#fff;}
.gmc-purple{background:linear-gradient(135deg,#7C3AED,#A78BFA);color:#fff;}
.gmc-purple::before{background:#fff;}
.gmc-orange{background:linear-gradient(135deg,#D97706,#F59E0B);color:#fff;}
.gmc-orange::before{background:#fff;}
.gmc-red{background:linear-gradient(135deg,#DC2626,#F87171);color:#fff;}
.gmc-red::before{background:#fff;}
.gmc-teal{background:linear-gradient(135deg,#0891B2,#22D3EE);color:#fff;}
.gmc-teal::before{background:#fff;}
.gmc-pink{background:linear-gradient(135deg,#DB2777,#F472B6);color:#fff;}
.gmc-pink::before{background:#fff;}
.gmc-dark{background:linear-gradient(135deg,#1E293B,#334155);color:#fff;}
.gmc-dark::before{background:#fff;}

/* Light metric cards */
.mc{border-radius:12px;padding:12px 14px;}
.mc .ml{font-size:10px;font-weight:600;margin-bottom:3px;}
.mc .mv{font-size:16px;font-weight:700;}
.mc .ms{font-size:9px;margin-top:2px;opacity:.75;}
.mb{background:var(--pl)}.mb .ml{color:var(--pd)}.mb .mv,.mb .ms{color:var(--p)}
.mg{background:var(--gl)}.mg .ml{color:var(--gd)}.mg .mv,.mg .ms{color:var(--g)}
.mr{background:var(--rl)}.mr .ml{color:var(--rd)}.mr .mv,.mr .ms{color:var(--r)}
.ma{background:var(--al)}.ma .ml{color:var(--ad)}.ma .mv,.ma .ms{color:var(--a)}
.mu{background:var(--ul)}.mu .ml{color:var(--ud)}.mu .mv,.mu .ms{color:var(--u)}
.mt{background:var(--tl)}.mt .ml{color:var(--td)}.mt .mv,.mt .ms{color:var(--t)}
.mc_{background:var(--cl)}.mc_ .ml{color:var(--cd)}.mc_ .mv,.mc_ .ms{color:var(--c)}
.mn{background:var(--nl)}.mn .ml{color:var(--nd)}.mn .mv,.mn .ms{color:var(--n)}
.mpk{background:var(--pkl)}.mpk .ml{color:var(--pkd)}.mpk .mv,.mpk .ms{color:var(--pk)}

/* ── CARDS ── */
.card{background:var(--card);border:1px solid var(--border);border-radius:12px;padding:14px 16px;margin-bottom:12px;box-shadow:0 1px 3px rgba(0,0,0,.04);}
.card.cb{border-top:3px solid var(--p)}.card.cg{border-top:3px solid var(--g)}.card.cr{border-top:3px solid var(--r)}.card.ca{border-top:3px solid var(--a)}.card.cu{border-top:3px solid var(--u)}.card.ct{border-top:3px solid var(--t)}.card.cm{border-top:3px solid var(--c)}.card.cpk{border-top:3px solid var(--pk)}
.ch{font-size:12px;font-weight:700;color:var(--text);margin-bottom:10px;display:flex;align-items:center;justify-content:space-between;gap:6px;flex-wrap:wrap;}
.ch-l{display:flex;align-items:center;gap:7px;}
.cico{width:26px;height:26px;border-radius:8px;display:flex;align-items:center;justify-content:center;font-size:14px;flex-shrink:0;}

/* ── MARKET COMPARISON CARDS ── */
.mkt-cmp{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:8px;margin-bottom:8px;}
.mkt-item{border-radius:10px;padding:12px;border:1px solid var(--border);background:var(--bg);}
.mkt-label{font-size:10px;font-weight:700;color:var(--muted);margin-bottom:8px;}
.mkt-row{display:flex;justify-content:space-between;align-items:flex-end;margin-bottom:6px;}
.mkt-ours{font-size:18px;font-weight:700;}
.mkt-mkt{font-size:11px;color:var(--muted);}
.mkt-diff-badge{font-size:10px;font-weight:700;padding:3px 8px;border-radius:20px;}
.mkt-bar-wrap{background:var(--border);border-radius:3px;height:4px;position:relative;}
.mkt-bar-fill{height:4px;border-radius:3px;transition:width .6s;}
.mkt-bar-mark{position:absolute;top:-3px;height:10px;width:2px;border-radius:1px;background:var(--muted);}

/* ── SUBSCRIPTION CARDS ── */
.sub-plan{border-radius:14px;padding:18px;border:2px solid var(--border);background:var(--card);position:relative;transition:all .15s;cursor:pointer;}
.sub-plan:hover{border-color:var(--p);box-shadow:0 4px 20px rgba(26,86,219,.12);}
.sub-plan.active-plan{border-color:var(--g);background:linear-gradient(135deg,#F0FDF4,#ECFDF5);}
.sub-plan.featured-plan{border-color:var(--p);background:linear-gradient(135deg,#EEF2FF,#F5F3FF);}
.sub-badge{position:absolute;top:-10px;left:50%;transform:translateX(-50%);background:var(--p);color:#fff;font-size:9px;font-weight:700;padding:3px 12px;border-radius:20px;white-space:nowrap;}
.sub-name{font-size:16px;font-weight:700;margin-bottom:4px;}
.sub-price{font-size:28px;font-weight:700;color:var(--p);}
.sub-price span{font-size:12px;font-weight:500;color:var(--muted);}
.sub-features{margin-top:12px;list-style:none;}
.sub-features li{font-size:11px;padding:4px 0;color:var(--muted);display:flex;align-items:center;gap:6px;}
.sub-features li::before{content:'✓';color:var(--g);font-weight:700;flex-shrink:0;}
.sub-features li.no::before{content:'✗';color:var(--r);}
.sub-features li.no{color:var(--border);}

/* ── INVOICE / SUBSCRIPTION ITEM ── */
.sub-inv-item{display:flex;align-items:center;justify-content:space-between;padding:10px 12px;border-radius:10px;margin-bottom:6px;border:1px solid var(--border);background:var(--bg);}
.sub-inv-left{display:flex;align-items:center;gap:10px;}
.sub-inv-icon{width:36px;height:36px;border-radius:10px;display:flex;align-items:center;justify-content:center;font-size:18px;flex-shrink:0;}
.sub-inv-name{font-size:12px;font-weight:600;color:var(--text);}
.sub-inv-meta{font-size:10px;color:var(--muted);margin-top:1px;}
.sub-inv-right{text-align:left;}
.sub-inv-amount{font-size:14px;font-weight:700;}
.sub-inv-status{font-size:10px;margin-top:1px;}

/* ── GRIDS ── */
.g2{display:grid;grid-template-columns:1fr 1fr;gap:10px;}
.g3{display:grid;grid-template-columns:1fr 1fr 1fr;gap:10px;}
.g4{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:10px;}

/* ── FORMS ── */
.fg{display:flex;flex-direction:column;gap:3px;margin-bottom:8px;}
.fg label{font-size:10px;color:var(--muted);font-weight:600;letter-spacing:.2px;}
.fg input,.fg select,.fg textarea{border:1.5px solid var(--border);border-radius:8px;padding:7px 10px;font-size:12px;background:var(--bg);color:var(--text);width:100%;transition:border-color .15s;}
.fg input:focus,.fg select:focus{outline:none;border-color:var(--p);background:var(--card);}

/* ── BUTTONS ── */
.btn{padding:7px 14px;border-radius:8px;font-size:11px;cursor:pointer;border:1.5px solid var(--border);background:var(--card);color:var(--text);transition:all .12s;font-weight:600;}
.btn:hover{opacity:.82;transform:translateY(-1px);}
.btn:active{transform:translateY(0);}
.bp{background:var(--p)!important;color:#fff!important;border-color:var(--p)!important;box-shadow:0 2px 6px rgba(26,86,219,.3);}
.bg2{background:var(--g)!important;color:#fff!important;border-color:var(--g)!important;box-shadow:0 2px 6px rgba(4,120,87,.3);}
.br2{background:var(--r)!important;color:#fff!important;border-color:var(--r)!important;}
.ba2{background:var(--a)!important;color:#fff!important;border-color:var(--a)!important;}
.bu2{background:var(--u)!important;color:#fff!important;border-color:var(--u)!important;}
.sm{padding:4px 10px!important;font-size:10px!important;}

/* ── TABLE ── */
.tbl{width:100%;border-collapse:collapse;font-size:11px;}
.tbl th{font-size:10px;font-weight:700;color:var(--muted);padding:8px 8px;text-align:right;border-bottom:2px solid var(--p);white-space:nowrap;background:var(--bg);letter-spacing:.2px;}
.tbl td{padding:8px 8px;border-bottom:1px solid var(--border);color:var(--text);vertical-align:middle;}
.tbl tbody tr{transition:background .1s;}
.tbl tbody tr:hover td{background:#F8FAFF;}
.tbl tfoot td{font-weight:700;border-top:2px solid var(--p);background:var(--bg);}

/* ── MISC ── */
.pill{font-size:9px;padding:3px 8px;border-radius:20px;display:inline-block;white-space:nowrap;font-weight:700;}
.dr{display:flex;justify-content:space-between;align-items:center;padding:6px 0;border-bottom:1px solid var(--border);font-size:11px;}
.dr:last-child{border-bottom:none;}
.dr.tot{font-weight:700;font-size:12px;border-top:2px solid var(--border);padding-top:8px;margin-top:4px;}
.brow{display:flex;align-items:center;gap:8px;margin-bottom:6px;}
.brow-l{font-size:10px;color:var(--muted);min-width:100px;text-align:right;font-weight:500;}
.brow-t{flex:1;background:var(--bg);border-radius:4px;height:8px;overflow:hidden;border:1px solid var(--border);position:relative;}
.brow-f{height:8px;border-radius:4px;transition:width .5s;}
.brow-v{font-size:10px;min-width:65px;text-align:left;}
.ab{border-radius:8px;padding:8px 11px;margin-bottom:6px;font-size:11px;}
.ab-g{background:var(--gl);border:1px solid #6EE7B7;color:var(--gd);}
.ab-r{background:var(--rl);border:1px solid #FCA5A5;color:var(--rd);}
.ab-a{background:var(--al);border:1px solid #FCD34D;color:var(--ad);}
.ab-i{background:var(--pl);border:1px solid #93C5FD;color:var(--pd);}
.ab .ab-t{font-weight:700;margin-bottom:2px;}

/* POS */
.pdc{background:var(--bg);border:1.5px solid var(--border);border-radius:12px;padding:12px;margin-bottom:8px;transition:border-color .15s;}
.pdc.ok{border-color:var(--g);background:linear-gradient(135deg,#F0FDF4,var(--bg));}
.pdc.wait{border-color:var(--a);}
.pdc-top{display:flex;align-items:center;gap:10px;margin-bottom:8px;}
.pdc-ic{width:40px;height:40px;border-radius:11px;display:flex;align-items:center;justify-content:center;font-size:20px;flex-shrink:0;}
.pdc-info{flex:1;min-width:0;}
.pdc-name{font-size:13px;font-weight:700;color:var(--text);}
.pdc-sub{font-size:10px;color:var(--muted);margin-top:2px;}
.pdc-acts{display:flex;gap:4px;flex-shrink:0;}
.pdc-minis{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:6px;}
.pdcm{background:var(--card);border-radius:8px;padding:7px 9px;border:1px solid var(--border);}
.pdcm .pm-l{font-size:9px;color:var(--muted);margin-bottom:2px;font-weight:600;}
.pdcm .pm-v{font-size:12px;font-weight:700;}
.eform{background:var(--card);border:1.5px solid var(--border);border-radius:10px;padding:12px;margin-top:8px;display:none;}
.eform.open{display:block;}
.pm-grid{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:8px;}

/* PMS */
.pms-card{background:var(--bg);border:1.5px solid var(--border);border-radius:12px;padding:12px;margin-bottom:8px;}
.pms-card.connected{border-color:var(--g);}
.pms-header{display:flex;align-items:center;gap:10px;margin-bottom:6px;}
.pms-icon{width:36px;height:36px;border-radius:9px;display:flex;align-items:center;justify-content:center;font-size:18px;flex-shrink:0;}
.pms-info{flex:1;}
.pms-name{font-size:12px;font-weight:700;color:var(--text);}
.pms-meta{font-size:10px;color:var(--muted);margin-top:1px;}
.pms-acts{display:flex;gap:4px;flex-shrink:0;align-items:center;}
.pms-form{background:var(--card);border:1px solid var(--border);border-radius:9px;padding:10px;margin-top:6px;display:none;}
.pms-form.open{display:block;}

/* SUPPLIER */
.sup-row{background:var(--bg);border-radius:10px;padding:10px 12px;margin-bottom:7px;display:flex;align-items:center;gap:10px;border:1px solid var(--border);}
.sup-av{width:38px;height:38px;border-radius:50%;display:flex;align-items:center;justify-content:center;font-size:15px;font-weight:700;flex-shrink:0;}

/* BACKUP */
.bk-item{display:flex;align-items:center;justify-content:space-between;padding:10px 12px;border-radius:10px;margin-bottom:6px;border:1px solid var(--border);background:var(--bg);}
.bk-name{font-size:11px;font-weight:700;color:var(--text);}
.bk-meta{font-size:10px;color:var(--muted);margin-top:1px;}

/* TOAST */
.toast-wrap{pointer-events:none;}
.toast{background:var(--g);color:#fff;padding:10px 18px;border-radius:10px;font-size:12px;text-align:center;margin-bottom:10px;display:none;font-weight:600;box-shadow:0 4px 14px rgba(4,120,87,.35);}
.toast.show{display:block;}

/* TOOLTIP */
.tt-ic{font-size:11px;cursor:pointer;opacity:.6;user-select:none;}
.tt-ic:hover{opacity:1;}

/* SCROLLBAR */
::-webkit-scrollbar{width:5px;height:5px;}
::-webkit-scrollbar-thumb{background:var(--border);border-radius:4px;}
::-webkit-scrollbar-track{background:transparent;}

@media(max-width:700px){
  .app{grid-template-columns:1fr;}.sb{display:none;}
  .kg4,.kg3{grid-template-columns:repeat(2,minmax(0,1fr));}
  .g2,.g3,.g4,.mkt-cmp{grid-template-columns:1fr;}
}
</style>
</head>
<body>
<div class="app">

<!-- ══ SIDEBAR ══ -->
<div class="sb">
  <div class="sb-logo">
    <div class="sb-hotel" id="sb-name">فندق النخبة</div>
    <div class="sb-sub" id="sb-type">HOTEL MANAGEMENT SYSTEM</div>
    <div class="sb-live"><div class="sb-dot"></div><span class="sb-live-t">LIVE</span></div>
  </div>

  <div class="sb-sec">الرئيسية</div>
  <div class="ni on" onclick="go('dash')"><span class="ni-ic">🏠</span>لوحة التحكم</div>
  <div class="ni" onclick="go('kpi')"><span class="ni-ic">📈</span>مؤشرات KPI + السوق</div>

  <div class="sb-sec">قراءة النزلاء</div>
  <div class="ni" onclick="go('pms')"><span class="ni-ic">🔌</span>تكامل PMS<span class="ni-b" id="pms-badge" style="display:none">!</span></div>

  <div class="sb-sec">التشغيل</div>
  <div class="ni" onclick="go('guests')"><span class="ni-ic">🛏️</span>النزلاء</div>
  <div class="ni" onclick="go('svcs')"><span class="ni-ic">🍽️</span>الخدمات</div>
  <div class="ni" onclick="go('pos')"><span class="ni-ic">💳</span>نقاط البيع<span class="ni-b" id="pos-badge" style="display:none">!</span></div>

  <div class="sb-sec">المحاسبة</div>
  <div class="ni" onclick="go('journal')"><span class="ni-ic">📒</span>دفتر اليومية</div>
  <div class="ni" onclick="go('trial')"><span class="ni-ic">⚖️</span>ميزان المراجعة</div>
  <div class="ni" onclick="go('pl')"><span class="ni-ic">📑</span>أرباح وخسائر</div>
  <div class="ni" onclick="go('recv')"><span class="ni-ic">📥</span>ذمم مدينة</div>
  <div class="ni" onclick="go('paybl')"><span class="ni-ic">📤</span>ذمم دائنة</div>

  <div class="sb-sec">الموردون</div>
  <div class="ni" onclick="go('suppliers')"><span class="ni-ic">🏪</span>الموردون<span class="ni-b" id="sup-badge" style="display:none">!</span></div>
  <div class="ni" onclick="go('invoices')"><span class="ni-ic">🧾</span>الفواتير</div>

  <div class="sb-sec">الميزانية</div>
  <div class="ni" onclick="go('budget')"><span class="ni-ic">📋</span>الميزانية الهرمية</div>
  <div class="ni" onclick="go('cashflow')"><span class="ni-ic">💵</span>التدفق النقدي</div>
  <div class="ni" onclick="go('match')"><span class="ni-ic">🔁</span>المطابقة اليومية</div>

  <div class="sb-sec">النظام</div>
  <div class="ni" onclick="go('subscriptions')"><span class="ni-ic">💎</span>الاشتراكات</div>
  <div class="ni" onclick="go('support')"><span class="ni-ic">🎫</span>الدعم الفني<span class="ni-b" id="sup-tix-badge" style="display:none">!</span></div>
  <div class="ni" onclick="go('reports')"><span class="ni-ic">📄</span>التقرير اليومي</div>
  <div class="ni" onclick="go('backup')"><span class="ni-ic">💾</span>نسخ احتياطي</div>
  <div class="ni" onclick="go('cfg')"><span class="ni-ic">⚙️</span>الإعدادات</div>

  <div class="sb-foot">
    <div class="sb-user">المشرف العام</div>
    <div class="sb-role" id="sb-plan-foot">خطة مجانية</div>
  </div>
</div>

<!-- ══ MAIN ══ -->
<div class="main">
  <div class="topbar">
    <div class="tb-l">
      <div class="tb-ic" id="tb-ic" style="background:var(--gl);color:var(--g)">🏠</div>
      <span class="tb-t" id="tb-title">لوحة التحكم</span>
    </div>
    <div class="tb-r">
      <span class="badge-date" id="tb-date"></span>
      <span class="badge-cd" id="tb-cd">23:59:00</span>
      <span id="tb-season" class="season-badge" style="background:var(--al);color:var(--ad)">موسم عادي</span>
      <div class="search-wrap">
        <input id="search-box" placeholder="🔍  بحث — نزيل، فاتورة، مورّد..." oninput="doSearch(this.value)" onfocus="document.getElementById('search-res').style.display='block'" onblur="setTimeout(()=>{document.getElementById('search-res').style.display='none'},220)"/>
        <div id="search-res"></div>
      </div>
      <button class="btn bp sm" onclick="go('match')">المطابقة</button>
    </div>
  </div>

  <div class="content">
    <div class="toast" id="toast"></div>

    <!-- ══════ DASHBOARD ══════ -->
    <div class="pg on" id="pg-dash">
      <!-- Row 1: Big gradient KPI cards -->
      <div class="kg4" style="margin-bottom:12px">
        <div class="gmc gmc-green">
          <span class="gm-icon">💰</span>
          <div class="gm-val" id="d-rev">0 ر.س</div>
          <div class="gm-lbl">إيرادات اليوم</div>
          <div class="gm-sub">نزلاء + خدمات</div>
          <div class="gm-trend" id="d-rev-trend" style="background:rgba(255,255,255,.2)">0%</div>
        </div>
        <div class="gmc gmc-blue">
          <span class="gm-icon">📊</span>
          <div class="gm-val" id="d-revpar">0 ر.س</div>
          <div class="gm-lbl">RevPAR</div>
          <div class="gm-sub" id="d-revpar-vs">إيراد / غرفة متاحة</div>
        </div>
        <div class="gmc gmc-purple">
          <span class="gm-icon">🛏️</span>
          <div class="gm-val" id="d-occ-pct">0%</div>
          <div class="gm-lbl">نسبة الإشغال</div>
          <div class="gm-sub" id="d-occ-sub">0 نزيل مقيم</div>
        </div>
        <div class="gmc gmc-orange">
          <span class="gm-icon">✨</span>
          <div class="gm-val" id="d-net">0 ر.س</div>
          <div class="gm-lbl">الصافي اليومي</div>
          <div class="gm-sub" id="d-mrg">هامش 0%</div>
        </div>
      </div>

      <!-- Row 2: Secondary cards -->
      <div class="kg4" style="margin-bottom:12px">
        <div class="mc mr"><div class="ml">📉 المصاريف</div><div class="mv" id="d-exp">0 ر.س</div><div class="ms">فواتير موردين</div></div>
        <div class="mc ma"><div class="ml">🔔 فواتير معلقة</div><div class="mv" id="d-alerts">0</div><div class="ms">تستحق الدفع</div></div>
        <div class="mc mc_"><div class="ml">💳 أجهزة POS</div><div class="mv" id="d-pos">—</div><div class="ms" id="d-pos-s">في الانتظار</div></div>
        <div class="mc mt"><div class="ml">🔌 آخر قراءة PMS</div><div class="mv" id="d-pms">—</div><div class="ms" id="d-pms-s">لم تُقرأ</div></div>
      </div>

      <!-- Row 3: Market comparison -->
      <div class="card" style="border-top:3px solid var(--p);background:linear-gradient(135deg,var(--card),var(--pl))">
        <div class="ch">
          <div class="ch-l">
            <div class="cico" style="background:var(--p);color:#fff">📊</div>
            <span>مقارنة السوق — ADR / RevPAR / الإشغال</span>
          </div>
          <div style="display:flex;align-items:center;gap:6px">
            <span id="d-season-badge" class="season-badge" style="background:var(--al);color:var(--ad)">موسم عادي</span>
            <button class="btn sm" onclick="go('kpi')">تفاصيل KPI</button>
          </div>
        </div>
        <div id="d-market-content">
          <div class="mkt-cmp">
            <div class="mkt-item" id="mkt-adr-card">
              <div class="mkt-label">ADR — متوسط سعر الليلة</div>
              <div class="mkt-row"><div class="mkt-ours" id="mkt-adr-ours" style="color:var(--p)">—</div><div class="mkt-mkt" id="mkt-adr-mkt">السوق: —</div></div>
              <div class="mkt-bar-wrap"><div class="mkt-bar-fill" id="mkt-adr-bar" style="width:0%;background:var(--p)"></div><div class="mkt-bar-mark" id="mkt-adr-mark" style="right:50%"></div></div>
              <div class="mkt-diff-badge" id="mkt-adr-diff" style="background:var(--pl);color:var(--p);margin-top:5px">—</div>
            </div>
            <div class="mkt-item" id="mkt-occ-card">
              <div class="mkt-label">نسبة الإشغال</div>
              <div class="mkt-row"><div class="mkt-ours" id="mkt-occ-ours" style="color:var(--g)">—</div><div class="mkt-mkt" id="mkt-occ-mkt">السوق: —</div></div>
              <div class="mkt-bar-wrap"><div class="mkt-bar-fill" id="mkt-occ-bar" style="width:0%;background:var(--g)"></div><div class="mkt-bar-mark" id="mkt-occ-mark" style="right:50%"></div></div>
              <div class="mkt-diff-badge" id="mkt-occ-diff" style="background:var(--gl);color:var(--g);margin-top:5px">—</div>
            </div>
            <div class="mkt-item" id="mkt-revpar-card">
              <div class="mkt-label">RevPAR</div>
              <div class="mkt-row"><div class="mkt-ours" id="mkt-revpar-ours" style="color:var(--u)">—</div><div class="mkt-mkt" id="mkt-revpar-mkt">السوق: —</div></div>
              <div class="mkt-bar-wrap"><div class="mkt-bar-fill" id="mkt-revpar-bar" style="width:0%;background:var(--u)"></div><div class="mkt-bar-mark" id="mkt-revpar-mark" style="right:50%"></div></div>
              <div class="mkt-diff-badge" id="mkt-revpar-diff" style="background:var(--ul);color:var(--u);margin-top:5px">—</div>
            </div>
          </div>
          <div id="d-season-rec" style="padding:8px 10px;background:var(--al);border-radius:8px;font-size:11px;color:var(--ad);font-weight:600;display:none"></div>
        </div>
      </div>

      <!-- Row 4: Revenue + Expenses + Insights -->
      <div class="g3">
        <div class="card cg">
          <div class="ch"><div class="ch-l"><div class="cico" style="background:var(--gl);color:var(--g)">💰</div>الإيرادات</div></div>
          <div id="d-rev-det"></div>
        </div>
        <div class="card cr">
          <div class="ch"><div class="ch-l"><div class="cico" style="background:var(--rl);color:var(--r)">📉</div>المصاريف</div></div>
          <div id="d-exp-det"></div>
        </div>
        <div class="card cb">
          <div class="ch"><div class="ch-l"><div class="cico" style="background:var(--pl);color:var(--p)">💡</div>التحليل الذكي</div></div>
          <div id="d-insights"></div>
        </div>
      </div>
    </div>

    <!-- ══════ KPI + MARKET ══════ -->
    <div class="pg" id="pg-kpi">
      <div style="display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:10px;margin-bottom:12px;">
        <div class="gmc gmc-green" style="padding:14px"><span class="gm-icon" style="font-size:18px;margin-bottom:6px">📊</span><div class="gm-val" id="kp-revpar" style="font-size:20px">0</div><div class="gm-lbl">RevPAR</div><div class="gm-sub">إيراد/غرفة متاحة</div></div>
        <div class="gmc gmc-blue" style="padding:14px"><span class="gm-icon" style="font-size:18px;margin-bottom:6px">💰</span><div class="gm-val" id="kp-adr" style="font-size:20px">0</div><div class="gm-lbl">ADR</div><div class="gm-sub">متوسط سعر الغرفة</div></div>
        <div class="gmc gmc-purple" style="padding:14px"><span class="gm-icon" style="font-size:18px;margin-bottom:6px">🏨</span><div class="gm-val" id="kp-occ" style="font-size:20px">0%</div><div class="gm-lbl">نسبة الإشغال</div><div class="gm-sub">مشغولة / إجمالي</div></div>
        <div class="gmc gmc-orange" style="padding:14px"><span class="gm-icon" style="font-size:18px;margin-bottom:6px">📈</span><div class="gm-val" id="kp-gop" style="font-size:20px">0%</div><div class="gm-lbl">GOP التشغيلي</div><div class="gm-sub">قبل الفوائد والضرائب</div></div>
        <div class="gmc gmc-teal" style="padding:14px"><span class="gm-icon" style="font-size:18px;margin-bottom:6px">💵</span><div class="gm-val" id="kp-trevpar" style="font-size:20px">0</div><div class="gm-lbl">TRevPAR</div><div class="gm-sub">إجمالي إيراد / غرفة</div></div>
        <div class="gmc gmc-pink" style="padding:14px"><span class="gm-icon" style="font-size:18px;margin-bottom:6px">📉</span><div class="gm-val" id="kp-npm" style="font-size:20px">0%</div><div class="gm-lbl">هامش الربح</div><div class="gm-sub">صافي / الإيراد</div></div>
      </div>
      <div class="card cb">
        <div class="ch"><div class="ch-l"><div class="cico" style="background:var(--pl);color:var(--p)">🌐</div>مقارنة السوق التفصيلية</div>
          <div style="display:flex;gap:6px;flex-wrap:wrap">
            <button class="btn" style="background:var(--u);color:#fff;border-color:var(--u);font-size:10px;padding:5px 10px" id="ai-websearch-btn" onclick="runWebSearchMarket()" data-tt="يبحث في الإنترنت عن أسعار الفنادق الفعلية الآن ثم يحللها Claude — أدق نتيجة">🔍 بحث ويب + AI</button>
            <button class="btn bu2 sm" id="ai-market-btn" onclick="runAIMarket()" data-tt="تحليل Claude بمعرفته المدمجة — لا يحتاج إنترنت إضافي">🤖 تحليل AI</button>
            <button class="btn bp sm" onclick="loadMarket()">↻ تحديث</button>
          </div>
        </div>
        <div class="ab ab-i" id="ai-insight" style="display:none;margin-bottom:8px"></div>
        <div id="ai-source-badge" style="display:none;margin-bottom:6px"></div>
        <div id="kpi-market-detail"></div>
      </div>
      <div class="card cg">
        <div class="ch"><div class="ch-l"><div class="cico" style="background:var(--gl);color:var(--g)">🏆</div>بنشمارك الصناعة</div></div>
        <div id="kp-bench"></div>
      </div>
      <div class="card cb">
        <div class="ch"><div class="ch-l"><div class="cico" style="background:var(--pl);color:var(--p)">📐</div>إدخال KPI يدوياً</div></div>
        <div class="g3">
          <div class="fg"><label>إجمالي الغرف</label><input type="number" id="kp-rooms" value="50" oninput="calcKPI()"/></div>
          <div class="fg"><label>غرف مشغولة</label><input type="number" id="kp-occ-r" value="38" oninput="calcKPI()"/></div>
          <div class="fg"><label>ليالٍ مباعة</label><input type="number" id="kp-nights" value="38" oninput="calcKPI()"/></div>
          <div class="fg"><label>إيرادات الغرف (ر.س)</label><input type="number" id="kp-rrev" value="2170" oninput="calcKPI()"/></div>
          <div class="fg"><label>إجمالي الإيرادات (ر.س)</label><input type="number" id="kp-trev" value="2450" oninput="calcKPI()"/></div>
          <div class="fg"><label>إجمالي المصاريف (ر.س)</label><input type="number" id="kp-texp" value="995" oninput="calcKPI()"/></div>
        </div>
      </div>
      <div class="card ca">
        <div class="ch"><div class="ch-l"><div class="cico" style="background:var(--al);color:var(--a)">🌐</div>تحديث أسعار السوق يدوياً</div></div>
        <div class="g3">
          <div class="fg"><label>المدينة</label><select id="mkt-city"><option value="riyadh">الرياض</option><option value="jeddah">جدة</option><option value="makkah">مكة المكرمة</option><option value="madinah">المدينة المنورة</option><option value="dammam">الدمام</option><option value="khobar">الخبر</option><option value="jubail">الجبيل</option><option value="ahsa">الأحساء</option><option value="abha">أبها</option><option value="taif">الطائف</option><option value="tabuk">تبوك</option><option value="qassim">القصيم</option><option value="hail">حائل</option><option value="bahah">الباحة</option><option value="other">أخرى</option></select></div>
          <div class="fg"><label>متوسط ADR فندق (ر.س)</label><input type="number" id="mkt-hadr" placeholder="320"/></div>
          <div class="fg"><label>متوسط ADR شقق (ر.س)</label><input type="number" id="mkt-aadr" placeholder="280"/></div>
          <div class="fg"><label>إشغال الفنادق %</label><input type="number" id="mkt-hocc" placeholder="72"/></div>
          <div class="fg"><label>إشغال الشقق %</label><input type="number" id="mkt-aocc" placeholder="68"/></div>
        </div>
        <button class="btn ba2" onclick="updateMarket()">حفظ أسعار السوق</button>
      </div>
    </div>

    <!-- ══════ PMS ══════ -->
    <div class="pg" id="pg-pms">
      <div class="kg4">
        <div class="mc mb"><div class="ml">عدد التكاملات</div><div class="mv" id="pms-cnt">0</div></div>
        <div class="mc mg"><div class="ml">آخر قراءة</div><div class="mv" id="pms-last">—</div></div>
        <div class="mc mt"><div class="ml">نزلاء مقروءون</div><div class="mv" id="pms-gf">0</div></div>
        <div class="mc ma"><div class="ml">إجمالي القراءات</div><div class="mv" id="pms-rc">0</div></div>
      </div>
      <div class="card cb">
        <div class="ch"><div class="ch-l"><div class="cico" style="background:var(--pl);color:var(--p)">🔌</div>إضافة تكامل PMS</div>
          <button class="btn bp sm" onclick="toggleAddPMS()">+ إضافة</button>
        </div>
        <div id="add-pms-form" style="display:none;background:var(--bg);border-radius:10px;padding:12px;margin-bottom:10px;border:1.5px solid var(--p)">
          <div class="g3">
            <div class="fg"><label>اسم النظام</label><input id="pms-new-name" placeholder="Opera Cloud / Cloudbeds..."/></div>
            <div class="fg"><label>نوع النظام</label>
              <select id="pms-new-type">
                <option value="opera">Oracle Opera (OHIP)</option>
                <option value="opera_onprem">Opera On-Premise</option>
                <option value="cloudbeds">Cloudbeds</option>
                <option value="mews">Mews</option>
                <option value="hotelogix">Hotelogix</option>
                <option value="stayntouch">StayNTouch</option>
                <option value="protel">Protel Air</option>
                <option value="roommaster">roommaster</option>
                <option value="custom">Custom API</option>
              </select>
            </div>
            <div class="fg"><label>عنوان الخادم URL</label><input id="pms-new-url" placeholder="https://pms.hotel.com/api"/></div>
            <div class="fg"><label>اسم المستخدم</label><input id="pms-new-user" placeholder="admin@hotel.com"/></div>
            <div class="fg"><label>كلمة المرور</label><input type="password" id="pms-new-pass" placeholder="••••••••"/></div>
            <div class="fg"><label>API Key</label><input id="pms-new-key" placeholder="sk-xxxxxxxx"/></div>
          </div>
          <div style="display:flex;gap:6px;margin-top:4px">
            <button class="btn bp" onclick="addPMS()" style="flex:1">إضافة التكامل</button>
            <button class="btn sm" onclick="toggleAddPMS()">إلغاء</button>
          </div>
        </div>
        <div id="pms-list"></div>
      </div>
      <div class="card cg">
        <div class="ch"><div class="ch-l"><div class="cico" style="background:var(--gl);color:var(--g)">📋</div>سجل القراءات الأخيرة</div>
          <button class="btn sm" onclick="loadPMSReads()">تحديث</button>
        </div>
        <div style="overflow-x:auto"><table class="tbl"><thead><tr><th>الوقت</th><th>النظام</th><th>النزلاء</th><th>الحالة</th><th></th></tr></thead>
        <tbody id="pms-reads-body"></tbody></table></div>
      </div>
      <div class="card ca" id="pms-data-card" style="display:none">
        <div class="ch"><div class="ch-l"><div class="cico" style="background:var(--al);color:var(--a)">👥</div>بيانات النزلاء المقروءة</div>
          <button class="btn bg2 sm" onclick="importPMSGuests()">استيراد للنظام</button>
        </div>
        <div id="pms-data-table" style="overflow-x:auto"></div>
      </div>
    </div>

    <!-- ══════ GUESTS ══════ -->
    <div class="pg" id="pg-guests">
      <div class="kg4">
        <div class="mc mb"><div class="ml">إجمالي النزلاء</div><div class="mv" id="g-tot">0</div></div>
        <div class="mc mg"><div class="ml">مقيمون الآن</div><div class="mv" id="g-act">0</div></div>
        <div class="mc mg"><div class="ml">إيرادات الإقامة</div><div class="mv" id="g-rev">0 ر.س</div></div>
        <div class="mc ma"><div class="ml">متوسط الإقامة</div><div class="mv" id="g-avg">—</div></div>
      </div>
      <div class="card cg">
        <div class="ch"><div class="ch-l"><div class="cico" style="background:var(--gl);color:var(--g)">🛏️</div>تسجيل نزيل جديد</div>
          <button class="btn bg2 sm" onclick="addGuest()">+ إضافة</button>
        </div>
        <div id="unit-type-selector" style="margin-bottom:10px">
          <div style="font-size:10px;font-weight:700;color:var(--muted);margin-bottom:6px">🏨 نوع الوحدة — اضغط لتعبئة السعر تلقائياً <span class="tt-ic" data-tt="يتغير حسب نوع المنشأة (فندق/شقق) في الإعدادات — السعر يُعبأ تلقائياً ويمكن تعديله">ℹ️</span></div>
          <div id="unit-type-grid" style="display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:6px;margin-bottom:8px"></div>
        </div>
        <div class="g3">
          <div class="fg"><label>اسم النزيل</label><input id="gi-name" placeholder="الاسم الكامل"/></div>
          <div class="fg"><label>رقم الهوية / الجواز</label><input id="gi-id" placeholder="رقم الهوية"/></div>
          <div class="fg"><label>رقم الوحدة <span class="tt-ic" data-tt="رقم الغرفة أو الشقة — يظهر في التقرير والفاتورة">ℹ️</span></label><input id="gi-unit" placeholder="101"/></div>
          <div class="fg"><label>نوع السرير</label><select id="gi-bed"><option value="double">مزدوج</option><option value="twin">سريران فرديان</option><option value="king">كينج</option><option value="suite">جناح</option></select></div>
          <div class="fg"><label>أسرة فردية إضافية</label><input type="number" min="0" max="5" id="gi-extra" value="0"/></div>
          <div class="fg"><label>سعر الليلة (ر.س) <span class="tt-ic" data-tt="يُعبأ من نوع الوحدة المختار — قابل للتعديل">ℹ️</span></label><input type="number" id="gi-price" placeholder="350" oninput="calcGuestPrev()"/></div>
          <div class="fg"><label>تاريخ الوصول</label><input type="date" id="gi-in"/></div>
          <div class="fg"><label>تاريخ المغادرة</label><input type="date" id="gi-out" oninput="calcGuestPrev()"/></div>
          <div class="fg"><label>الإيراد المحسوب</label><div id="gi-calc" style="padding:7px 10px;font-size:14px;font-weight:700;background:linear-gradient(135deg,var(--gl),#D1FAE5);border-radius:8px;color:var(--g)">0 ر.س</div></div>
        </div>
        <div class="fg"><label>طريقة الدفع <span class="tt-ic" data-tt="الطرق المفعّلة في الإعدادات — يمكنك تخصيصها من إعدادات طرق الدفع">ℹ️</span></label>
          <select id="gi-pay" style="width:100%"></select>
        </div>
        <button class="btn bg2" onclick="addGuest()">تسجيل + قيد محاسبي تلقائي</button>
      </div>
      <div class="card cb"><div class="ch"><div class="ch-l"><div class="cico" style="background:var(--pl);color:var(--p)">📋</div>سجل النزلاء</div></div>
        <div style="overflow-x:auto"><table class="tbl"><thead><tr><th>الوحدة</th><th>النزيل</th><th>السرير</th><th>وصول</th><th>ليالٍ</th><th>الإيراد</th><th>الدفع</th><th>الحالة</th><th></th></tr></thead>
        <tbody id="g-body"></tbody><tfoot id="g-foot"></tfoot></table></div>
      </div>
    </div>

    <!-- ══════ SERVICES ══════ -->
    <div class="pg" id="pg-svcs">
      <div class="kg4">
        <div class="mc mu"><div class="ml">إجمالي الخدمات</div><div class="mv" id="sv-tot">0 ر.س</div></div>
        <div class="mc mb"><div class="ml">مغسلة</div><div class="mv" id="sv-law">0 ر.س</div></div>
        <div class="mc ma"><div class="ml">طعام</div><div class="mv" id="sv-food">0 ر.س</div></div>
        <div class="mc mn"><div class="ml">أخرى</div><div class="mv" id="sv-oth">0 ر.س</div></div>
      </div>
      <div class="card cu">
        <div class="ch"><div class="ch-l"><div class="cico" style="background:var(--ul);color:var(--u)">🍽️</div>تسجيل خدمة</div><button class="btn bu2 sm" onclick="addSvc()">+ إضافة</button></div>
        <div class="g3">
          <div class="fg"><label>نوع الخدمة</label><select id="sv-type"><option value="laundry">مغسلة</option><option value="food">طعام</option><option value="room_service">خدمة الغرفة</option><option value="transport">نقل</option><option value="minibar">ميني بار</option><option value="parking">موقف</option><option value="gym">صالة</option><option value="pool">مسبح</option><option value="other">أخرى</option></select></div>
          <div class="fg"><label>رقم الوحدة</label><input id="sv-unit" placeholder="101"/></div>
          <div class="fg"><label>المبلغ (ر.س)</label><input type="number" min="0" step="0.01" id="sv-amt" placeholder="0.00"/></div>
          <div class="fg"><label>طريقة الدفع</label><select id="sv-pay"><option value="mada">مدى</option><option value="cash">نقداً</option><option value="credit">آجل</option></select></div>
        </div>
        <button class="btn bu2" onclick="addSvc()">تسجيل + قيد محاسبي</button>
      </div>
      <div class="card cu"><div class="ch"><div class="ch-l"><div class="cico" style="background:var(--ul);color:var(--u)">📊</div>توزيع الخدمات</div></div><div id="sv-break"></div></div>
    </div>

    <!-- ══════ POS ══════ -->
    <div class="pg" id="pg-pos">
      <div class="kg4">
        <div class="mc ma"><div class="ml">إجمالي الأجهزة</div><div class="mv" id="pos-total-d">0</div></div>
        <div class="mc mt"><div class="ml">مُستلمة</div><div class="mv" id="pos-recv-c">0</div></div>
        <div class="mc mr"><div class="ml">في الانتظار</div><div class="mv" id="pos-pend-c">0</div></div>
        <div class="mc mg"><div class="ml">إجمالي الصافي</div><div class="mv" id="pos-net-t">0 ر.س</div></div>
      </div>
      <div class="card cb">
        <div class="ch"><div class="ch-l"><div class="cico" style="background:var(--pl);color:var(--p)">💳</div>إدارة أجهزة نقاط البيع</div><button class="btn bp sm" onclick="toggleNewPOS()">+ جهاز جديد</button></div>
        <div id="new-pos-form" style="display:none;background:var(--bg);border-radius:10px;padding:12px;margin-bottom:10px;border:1.5px solid var(--p)">
          <div class="g3">
            <div class="fg"><label>اسم الجهاز</label><input id="nd-name" placeholder="جهاز المطعم"/></div>
            <div class="fg"><label>القسم</label><select id="nd-dept"><option value="restaurant">🍽️ مطعم</option><option value="cafe">☕ كافيه</option><option value="laundry">👕 مغسلة</option><option value="pool">🏊 مسبح</option><option value="reception">🏨 استقبال</option><option value="spa">💆 سبا</option><option value="minibar">🍾 ميني بار</option><option value="gym">🏋️ صالة</option><option value="parking">🚗 موقف</option><option value="shop">🛍️ محل</option><option value="other">💳 أخرى</option></select></div>
            <div class="fg"><label>اللون</label><select id="nd-color"><option value="#1A56DB">أزرق</option><option value="#047857">أخضر</option><option value="#DC2626">أحمر</option><option value="#D97706">ذهبي</option><option value="#7C3AED">بنفسجي</option><option value="#EA580C">برتقالي</option><option value="#0891B2">فيروزي</option></select></div>
            <div class="fg"><label>رقم الجهاز</label><input id="nd-serial" placeholder="SN-001"/></div>
            <div class="fg"><label>MK Geidea</label><input type="password" id="nd-mk" placeholder="اختياري"/></div>
          </div>
          <div style="display:flex;gap:5px;margin-top:4px"><button class="btn bp" onclick="addPOSDevice()" style="flex:1">إضافة</button><button class="btn sm" onclick="toggleNewPOS()">إلغاء</button></div>
        </div>
        <div id="pos-devices-list"></div>
      </div>
      <div class="card ca"><div class="ch"><div class="ch-l"><div class="cico" style="background:var(--al);color:var(--a)">📥</div>إدخال موازنات الأجهزة</div></div><div id="pos-entry-list"></div></div>
    </div>

    <!-- ══════ JOURNAL ══════ -->
    <div class="pg" id="pg-journal">
      <div class="kg4">
        <div class="mc mg"><div class="ml">إجمالي المدين</div><div class="mv" id="j-dr">0 ر.س</div></div>
        <div class="mc mb"><div class="ml">إجمالي الدائن</div><div class="mv" id="j-cr">0 ر.س</div></div>
        <div class="mc mg" id="j-bal-c"><div class="ml">التوازن</div><div class="mv" id="j-bal">متوازن ✓</div></div>
        <div class="mc mn"><div class="ml">عدد القيود</div><div class="mv" id="j-cnt">0</div></div>
      </div>
      <div class="card cg">
        <div class="ch"><div class="ch-l"><div class="cico" style="background:var(--gl);color:var(--g)">📒</div>إضافة قيد يومية</div><button class="btn bg2 sm" onclick="addJnl()">+ قيد</button></div>
        <div style="padding:7px 10px;background:var(--gl);border-radius:8px;font-size:10px;color:var(--gd);margin-bottom:10px;font-weight:600">القاعدة: المدين = الدائن دائماً — كل عملية لها طرفان</div>
        <div class="g3">
          <div class="fg"><label>الحساب المدين</label><select id="j-dr-a"><option value="cash">النقدية</option><option value="bank">البنك</option><option value="receivable">ذمم مدينة</option><option value="util_exp">كهرباء وماء</option><option value="maint_exp">صيانة</option><option value="payable">ذمم دائنة</option></select></div>
          <div class="fg"><label>الحساب الدائن</label><select id="j-cr-a"><option value="room_rev">إيرادات الغرف</option><option value="svc_rev">إيرادات الخدمات</option><option value="cash">النقدية</option><option value="bank">البنك</option><option value="payable">ذمم دائنة</option><option value="vat_payable">VAT مستحق</option></select></div>
          <div class="fg"><label>المبلغ (ر.س)</label><input type="number" min="0" id="j-amt" placeholder="0.00"/></div>
        </div>
        <div class="g2"><div class="fg"><label>البيان</label><input id="j-desc" placeholder="وصف..."/></div><div class="fg"><label>المرجع</label><input id="j-ref" placeholder="رقم الفاتورة..."/></div></div>
        <button class="btn bg2" onclick="addJnl()">تسجيل القيد المحاسبي</button>
      </div>
      <div class="card cb"><div class="ch"><div class="ch-l"><div class="cico" style="background:var(--pl);color:var(--p)">📋</div>دفتر اليومية</div></div>
        <div style="overflow-x:auto"><table class="tbl"><thead><tr><th>الوقت</th><th>البيان</th><th>المرجع</th><th style="text-align:left;color:var(--g)">مدين</th><th style="text-align:left;color:var(--p)">دائن</th></tr></thead>
        <tbody id="j-body"></tbody><tfoot id="j-foot"></tfoot></table></div>
      </div>
    </div>

    <!-- ══════ TRIAL BALANCE ══════ -->
    <div class="pg" id="pg-trial">
      <div class="kg3">
        <div class="mc mg"><div class="ml">إجمالي المدين</div><div class="mv" id="tb-dr">0 ر.س</div></div>
        <div class="mc mb"><div class="ml">إجمالي الدائن</div><div class="mv" id="tb-cr">0 ر.س</div></div>
        <div class="mc mg" id="tb-bal-c"><div class="ml">حالة الميزان</div><div class="mv" id="tb-bal">—</div></div>
      </div>
      <div class="card cb"><div class="ch"><div class="ch-l"><div class="cico" style="background:var(--pl);color:var(--p)">⚖️</div>ميزان المراجعة</div></div>
        <div style="overflow-x:auto"><table class="tbl"><thead><tr><th>الحساب</th><th style="text-align:left;color:var(--g)">مجموع المدين</th><th style="text-align:left;color:var(--p)">مجموع الدائن</th><th style="text-align:left">الرصيد</th></tr></thead>
        <tbody id="tb-body"></tbody><tfoot id="tb-foot"></tfoot></table></div>
      </div>
    </div>

    <!-- ══════ P&L ══════ -->
    <div class="pg" id="pg-pl">
      <div class="kg4">
        <div class="mc mg"><div class="ml">إجمالي الإيرادات</div><div class="mv" id="pl-rev">0 ر.س</div></div>
        <div class="mc mr"><div class="ml">إجمالي التكاليف</div><div class="mv" id="pl-cost">0 ر.س</div></div>
        <div class="mc mb"><div class="ml">مجمل الربح</div><div class="mv" id="pl-gross">0 ر.س</div></div>
        <div class="mc mu"><div class="ml">صافي الربح</div><div class="mv" id="pl-net">0 ر.س</div></div>
      </div>
      <div class="card cg"><div class="ch"><div class="ch-l"><div class="cico" style="background:var(--gl);color:var(--g)">📑</div>قائمة الأرباح والخسائر</div></div><div id="pl-det"></div></div>
    </div>

    <!-- ══════ RECEIVABLES ══════ -->
    <div class="pg" id="pg-recv">
      <div class="kg4">
        <div class="mc mb"><div class="ml">إجمالي الذمم المدينة</div><div class="mv" id="rec-tot">0 ر.س</div><div class="ms">مستحقة لنا</div></div>
        <div class="mc ma"><div class="ml">معلقة</div><div class="mv" id="rec-pend">0 ر.س</div></div>
        <div class="mc mr"><div class="ml">متأخرة</div><div class="mv" id="rec-over">0 ر.س</div></div>
        <div class="mc mg"><div class="ml">محصّلة</div><div class="mv" id="rec-col">0 ر.س</div></div>
      </div>
      <div class="card cb">
        <div class="ch"><div class="ch-l"><div class="cico" style="background:var(--pl);color:var(--p)">📥</div>إضافة ذمة مدينة</div><button class="btn bp sm" onclick="addRecv()">+ إضافة</button></div>
        <div class="g3">
          <div class="fg"><label>الجهة</label><input id="rec-n" placeholder="اسم الجهة..."/></div>
          <div class="fg"><label>المرجع</label><input id="rec-r" placeholder="رقم الوحدة..."/></div>
          <div class="fg"><label>المبلغ (ر.س)</label><input type="number" min="0" id="rec-a" placeholder="0.00"/></div>
          <div class="fg"><label>تاريخ الاستحقاق</label><input type="date" id="rec-d"/></div>
          <div class="fg"><label>النوع</label><select id="rec-t"><option value="room">إيجار</option><option value="svc">خدمات</option><option value="corp">شركة</option><option value="other">أخرى</option></select></div>
        </div>
        <button class="btn bp" onclick="addRecv()">تسجيل الذمة المدينة</button>
      </div>
      <div class="card ca"><div class="ch"><div class="ch-l"><div class="cico" style="background:var(--al);color:var(--a)">📋</div>سجل الذمم المدينة</div></div>
        <div style="overflow-x:auto"><table class="tbl"><thead><tr><th>الجهة</th><th>المرجع</th><th>النوع</th><th style="text-align:left">المبلغ</th><th>الاستحقاق</th><th>الحالة</th><th></th></tr></thead>
        <tbody id="rec-body"></tbody><tfoot id="rec-foot"></tfoot></table></div>
      </div>
    </div>

    <!-- ══════ PAYABLES ══════ -->
    <div class="pg" id="pg-paybl">
      <div class="kg4">
        <div class="mc mr"><div class="ml">إجمالي الذمم الدائنة</div><div class="mv" id="pay-tot">0 ر.س</div><div class="ms">ديوننا</div></div>
        <div class="mc ma"><div class="ml">معلقة</div><div class="mv" id="pay-pend">0 ر.س</div></div>
        <div class="mc mr"><div class="ml">متأخرة</div><div class="mv" id="pay-late">0 ر.س</div></div>
        <div class="mc mg"><div class="ml">مدفوعة</div><div class="mv" id="pay-paid">0 ر.س</div></div>
      </div>
      <div class="card cr"><div class="ch"><div class="ch-l"><div class="cico" style="background:var(--rl);color:var(--r)">📤</div>سجل الذمم الدائنة</div></div>
        <div style="overflow-x:auto"><table class="tbl"><thead><tr><th>المورّد</th><th>رقم الفاتورة</th><th style="text-align:left">المبلغ</th><th>الاستحقاق</th><th>الحالة</th><th></th></tr></thead>
        <tbody id="pay-body"></tbody><tfoot id="pay-foot"></tfoot></table></div>
      </div>
    </div>

    <!-- ══════ SUPPLIERS ══════ -->
    <div class="pg" id="pg-suppliers">
      <div class="kg4">
        <div class="mc ma"><div class="ml">عدد الموردين</div><div class="mv" id="sup-cnt">0</div></div>
        <div class="mc mr"><div class="ml">مستحقات</div><div class="mv" id="sup-due">0 ر.س</div></div>
        <div class="mc mg"><div class="ml">مدفوعة</div><div class="mv" id="sup-paid">0 ر.س</div></div>
        <div class="mc mn"><div class="ml">إجمالي الفواتير</div><div class="mv" id="sup-inv-cnt">0</div></div>
      </div>
      <div class="card ca">
        <div class="ch"><div class="ch-l"><div class="cico" style="background:var(--al);color:var(--a)">🏪</div>إضافة مورّد</div><button class="btn ba2 sm" onclick="addSup()">+ إضافة</button></div>
        <div class="g3">
          <div class="fg"><label>اسم المورّد</label><input id="sup-n" placeholder="اسم الشركة..."/></div>
          <div class="fg"><label>نوع الخدمة</label><select id="sup-t"><option value="util">كهرباء وماء</option><option value="maint">صيانة</option><option value="laundry">مغسلة</option><option value="food">طعام</option><option value="supply">لوازم</option><option value="cleaning">نظافة</option><option value="security">أمن</option><option value="it">تقنية</option><option value="other">أخرى</option></select></div>
          <div class="fg"><label>رقم التواصل</label><input id="sup-ph" placeholder="05xxxxxxxx"/></div>
          <div class="fg"><label>IBAN</label><input id="sup-ib" placeholder="SA..."/></div>
          <div class="fg"><label>السجل التجاري</label><input id="sup-cr" placeholder="اختياري"/></div>
          <div class="fg"><label>شروط الدفع</label><select id="sup-tm"><option value="cash">نقداً فوري</option><option value="30">30 يوماً</option><option value="60">60 يوماً</option><option value="monthly">شهري</option></select></div>
        </div>
        <button class="btn ba2" onclick="addSup()">إضافة المورّد</button>
      </div>
      <div class="card ca"><div class="ch"><div class="ch-l"><div class="cico" style="background:var(--al);color:var(--a)">📋</div>قائمة الموردين</div></div><div id="sup-list"></div></div>
    </div>

    <!-- ══════ INVOICES ══════ -->
    <div class="pg" id="pg-invoices">
      <div class="kg4">
        <div class="mc mr"><div class="ml">فواتير معلقة</div><div class="mv" id="inv-pc">0</div></div>
        <div class="mc ma"><div class="ml">إجمالي المعلقة</div><div class="mv" id="inv-pa">0 ر.س</div></div>
        <div class="mc mg"><div class="ml">مدفوعة</div><div class="mv" id="inv-dc">0</div></div>
        <div class="mc mb"><div class="ml">إجمالي المدفوعة</div><div class="mv" id="inv-da">0 ر.س</div></div>
      </div>
      <div class="card cr">
        <div class="ch"><div class="ch-l"><div class="cico" style="background:var(--rl);color:var(--r)">🧾</div>إضافة فاتورة مورّد</div><button class="btn br2 sm" onclick="addInv()">+ فاتورة</button></div>
        <div class="g3">
          <div class="fg"><label>المورّد</label><select id="inv-sup"></select></div>
          <div class="fg"><label>رقم الفاتورة</label><input id="inv-num" placeholder="INV-001"/></div>
          <div class="fg"><label>المبلغ الأساسي (ر.س)</label><input type="number" min="0" step="0.01" id="inv-base" placeholder="0.00" oninput="calcInv()"/></div>
          <div class="fg"><label>VAT 15%</label><div style="display:flex;align-items:center;gap:8px"><input type="checkbox" id="inv-vat" checked onchange="calcInv()" style="width:auto"/><span id="inv-vat-a" style="font-size:11px;color:var(--a);font-weight:600">0 ر.س</span></div></div>
          <div class="fg"><label>تاريخ الفاتورة</label><input type="date" id="inv-date"/></div>
          <div class="fg"><label>تاريخ الاستحقاق</label><input type="date" id="inv-due"/></div>
          <div class="fg"><label>الإجمالي شامل VAT</label><div id="inv-tot" style="padding:7px 10px;font-size:14px;font-weight:700;background:linear-gradient(135deg,var(--rl),#FEE2E2);border-radius:8px;color:var(--r)">0 ر.س</div></div>
        </div>
        <button class="btn br2" onclick="addInv()">تسجيل + قيد محاسبي تلقائي</button>
      </div>
      <div class="card cr"><div class="ch"><div class="ch-l"><div class="cico" style="background:var(--rl);color:var(--r)">📋</div>سجل الفواتير</div></div>
        <div style="overflow-x:auto"><table class="tbl"><thead><tr><th>المورّد</th><th>رقم الفاتورة</th><th style="text-align:left">الأساسي</th><th style="text-align:left">VAT</th><th style="text-align:left">الإجمالي</th><th>الاستحقاق</th><th>الحالة</th><th></th></tr></thead>
        <tbody id="inv-body"></tbody><tfoot id="inv-foot"></tfoot></table></div>
      </div>
    </div>

    <!-- ══════ BUDGET ══════ -->
    <div class="pg" id="pg-budget">
      <div class="kg4">
        <div class="mc mb"><div class="ml">إجمالي الإيرادات المخططة</div><div class="mv" id="bgt-rev-plan">0 ر.س</div></div>
        <div class="mc mr"><div class="ml">إجمالي المصاريف المخططة</div><div class="mv" id="bgt-exp-plan">0 ر.س</div></div>
        <div class="mc" id="bgt-diff-c"><div class="ml">الفرق — مخطط vs فعلي</div><div class="mv" id="bgt-diff">0</div></div>
        <div class="mc mu"><div class="ml">نسبة الإنجاز</div><div class="mv" id="bgt-pct">0%</div></div>
      </div>
      <div class="card cb">
        <div class="ch">
          <div class="ch-l"><div class="cico" style="background:var(--pl);color:var(--p)">📋</div>الميزانية الهرمية</div>
          <div style="display:flex;gap:5px;flex-wrap:wrap">
            <button class="btn bp sm" onclick="addBgtMain('rev')">+ إيراد رئيسي</button>
            <button class="btn br2 sm" onclick="addBgtMain('exp')">+ مصروف رئيسي</button>
            <button class="btn sm" onclick="resetBgt()">إعادة تعيين</button>
          </div>
        </div>
        <div style="font-size:10px;color:var(--muted);padding:6px 9px;background:var(--bg);border-radius:8px;margin-bottom:10px">كل بند رئيسي له موازنات فرعية — اضغط <b>+ فرعي</b> على أي بند لإضافة موازنة داخله</div>
        <div id="bgt-tree"></div>
      </div>
      <div class="card cg"><div class="ch"><div class="ch-l"><div class="cico" style="background:var(--gl);color:var(--g)">📊</div>مقارنة المخطط بالفعلي</div></div><div id="bgt-chart"></div></div>
    </div>

    <!-- ══════ CASHFLOW ══════ -->
    <div class="pg" id="pg-cashflow">
      <div class="kg4">
        <div class="mc mg"><div class="ml">التدفق الداخل</div><div class="mv" id="cf-in">0 ر.س</div></div>
        <div class="mc mr"><div class="ml">التدفق الخارج</div><div class="mv" id="cf-out">0 ر.س</div></div>
        <div class="mc mb"><div class="ml">الصافي</div><div class="mv" id="cf-net">0 ر.س</div></div>
        <div class="mc ma"><div class="ml">توقع نهاية الشهر</div><div class="mv" id="cf-end">0 ر.س</div></div>
      </div>
      <div class="card cg"><div class="ch"><div class="ch-l"><div class="cico" style="background:var(--gl);color:var(--g)">💵</div>تفصيل التدفق النقدي</div></div><div id="cf-det"></div></div>
      <div class="card ca"><div class="ch"><div class="ch-l"><div class="cico" style="background:var(--al);color:var(--a)">🔮</div>توقعات الأسابيع القادمة</div></div><div id="cf-weeks"></div></div>
    </div>

    <!-- ══════ MATCH ══════ -->
    <div class="pg" id="pg-match">
      <div style="background:linear-gradient(135deg,var(--al),#FEF3C7);border:1.5px solid var(--a);border-radius:12px;padding:14px 16px;margin-bottom:12px;display:flex;align-items:center;justify-content:space-between;flex-wrap:wrap;gap:8px">
        <div><div style="font-size:13px;font-weight:700;color:var(--ad)">المطابقة التلقائية التالية</div><div style="font-size:10px;color:var(--a);margin-top:2px">كل يوم الساعة 23:59</div></div>
        <div style="font-size:22px;font-weight:700;color:var(--ad);font-family:monospace" id="match-cd">—</div>
        <button class="btn bg2" onclick="runMatch()">تشغيل المطابقة الآن</button>
      </div>
      <div class="kg4">
        <div class="mc mg"><div class="ml">إجمالي أجهزة POS</div><div class="mv" id="m-pos">—</div></div>
        <div class="mc mb"><div class="ml">الوارد الداخلي</div><div class="mv" id="m-sys">—</div></div>
        <div class="mc" id="m-diff-c"><div class="ml">الفرق</div><div class="mv" id="m-diff">—</div></div>
        <div class="mc" id="m-res-c"><div class="ml">النتيجة</div><div class="mv" id="m-res">—</div></div>
      </div>
      <div class="card cb">
        <div class="ch">
          <div class="ch-l"><div class="cico" style="background:var(--pl);color:var(--p)">🔁</div>تفصيل المطابقة</div>
          <div style="display:flex;align-items:center;gap:6px">
            <input type="number" min="0" id="m-sys-in" placeholder="الوارد الداخلي ر.س" style="width:130px;border:1.5px solid var(--border);border-radius:8px;padding:5px 9px;font-size:11px;background:var(--bg);color:var(--text)"/>
            <button class="btn bp sm" onclick="runMatch()">تشغيل</button>
          </div>
        </div>
        <div id="m-det"></div>
      </div>
      <div class="g2">
        <div class="card cg"><div class="ch"><div class="ch-l"><div class="cico" style="background:var(--gl);color:var(--g)">✅</div>نقاط القوة</div></div><div id="m-str"></div></div>
        <div class="card cr"><div class="ch"><div class="ch-l"><div class="cico" style="background:var(--rl);color:var(--r)">⚠️</div>نقاط الضعف</div></div><div id="m-wk"></div></div>
      </div>
    </div>

    <!-- ══════ SUBSCRIPTIONS ══════ -->
    <div class="pg" id="pg-subscriptions">
      <div class="kg3" style="margin-bottom:14px">
        <div class="gmc gmc-blue" style="padding:14px"><span class="gm-icon" style="font-size:18px;margin-bottom:6px">💎</span><div class="gm-val" id="sub-plan-name" style="font-size:16px">مجانية</div><div class="gm-lbl">الخطة الحالية</div></div>
        <div class="gmc gmc-green" style="padding:14px"><span class="gm-icon" style="font-size:18px;margin-bottom:6px">📅</span><div class="gm-val" id="sub-exp" style="font-size:14px">غير محدود</div><div class="gm-lbl">تاريخ الانتهاء</div></div>
        <div class="gmc gmc-orange" style="padding:14px"><span class="gm-icon" style="font-size:18px;margin-bottom:6px">💳</span><div class="gm-val" id="sub-next-amt" style="font-size:16px">0 ر.س</div><div class="gm-lbl">القسط القادم</div><div class="gm-sub" id="sub-next-date">—</div></div>
      </div>

      <!-- Plans -->
      <div style="display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:12px;margin-bottom:14px">
        <div class="sub-plan" onclick="selectPlan('free')" id="plan-free">
          <div class="sub-name" style="color:var(--n)">مجانية</div>
          <div class="sub-price">0<span> ر.س / شهر</span></div>
          <ul class="sub-features">
            <li>50 نزيل / شهر</li>
            <li>4 أجهزة POS</li>
            <li>تكامل PMS واحد</li>
            <li>تقارير أساسية</li>
            <li class="no">مقارنة السوق</li>
            <li class="no">نسخ احتياطي تلقائي</li>
            <li class="no">دعم فني أولوية</li>
          </ul>
          <button class="btn sm" style="width:100%;margin-top:12px" id="btn-plan-free">الخطة الحالية</button>
        </div>
        <div class="sub-plan featured-plan" onclick="selectPlan('pro')" id="plan-pro">
          <div class="sub-badge">الأكثر شيوعاً</div>
          <div class="sub-name" style="color:var(--p)">احترافية</div>
          <div class="sub-price">299<span> ر.س / شهر</span></div>
          <ul class="sub-features">
            <li>نزلاء غير محدود</li>
            <li>أجهزة POS غير محدودة</li>
            <li>3 تكاملات PMS</li>
            <li>مقارنة السوق الكاملة</li>
            <li>نسخ احتياطي تلقائي يومي</li>
            <li>تقارير Excel / PDF</li>
            <li class="no">دعم فني 24/7</li>
          </ul>
          <button class="btn bp sm" style="width:100%;margin-top:12px" id="btn-plan-pro">ترقية الآن</button>
        </div>
        <div class="sub-plan" onclick="selectPlan('enterprise')" id="plan-enterprise">
          <div class="sub-name" style="color:var(--u)">مؤسسية</div>
          <div class="sub-price">799<span> ر.س / شهر</span></div>
          <ul class="sub-features">
            <li>كل مميزات الاحترافية</li>
            <li>متعدد الفروع</li>
            <li>تكاملات PMS غير محدودة</li>
            <li>API مفتوح للتكامل</li>
            <li>نسخ احتياطي لحظي</li>
            <li>مدير حساب مخصص</li>
            <li>دعم فني 24/7 أولوية</li>
          </ul>
          <button class="btn bu2 sm" style="width:100%;margin-top:12px" id="btn-plan-enterprise">تواصل معنا</button>
        </div>
      </div>

      <!-- Manual activation -->
      <div class="card cb">
        <div class="ch"><div class="ch-l"><div class="cico" style="background:var(--pl);color:var(--p)">🔑</div>تفعيل الاشتراك يدوياً</div></div>
        <div style="font-size:11px;color:var(--muted);margin-bottom:10px">أدخل كود التفعيل الذي وصلك عند الشراء لتفعيل خطتك فوراً</div>
        <div class="g3">
          <div class="fg"><label>كود التفعيل</label><input id="sub-code" placeholder="HOTEL-XXXX-XXXX-XXXX" style="letter-spacing:1px;font-family:monospace"/></div>
          <div class="fg"><label>الخطة المراد تفعيلها</label><select id="sub-plan-sel"><option value="free">مجانية</option><option value="pro">احترافية — 299 ر.س/شهر</option><option value="enterprise">مؤسسية — 799 ر.س/شهر</option></select></div>
          <div class="fg"><label>مدة الاشتراك</label><select id="sub-period"><option value="monthly">شهري</option><option value="quarterly">ربع سنوي (-10%)</option><option value="annual">سنوي (-20%)</option></select></div>
        </div>
        <button class="btn bp" onclick="activateSub()">تفعيل الاشتراك</button>
      </div>

      <!-- Automatic billing -->
      <div class="card cg">
        <div class="ch"><div class="ch-l"><div class="cico" style="background:var(--gl);color:var(--g)">🔄</div>الفوترة التلقائية</div>
          <label style="display:flex;align-items:center;gap:8px;cursor:pointer;font-size:12px;font-weight:600">
            <input type="checkbox" id="sub-auto" onchange="toggleAutoSub()" style="width:auto"/>
            تفعيل الدفع التلقائي
          </label>
        </div>
        <div class="g3">
          <div class="fg"><label>رقم البطاقة</label><input id="sub-card" placeholder="**** **** **** ****" maxlength="19"/></div>
          <div class="fg"><label>تاريخ الانتهاء</label><input id="sub-card-exp" placeholder="MM/YY"/></div>
          <div class="fg"><label>CVV</label><input id="sub-card-cvv" type="password" placeholder="***" maxlength="3"/></div>
        </div>
        <div style="padding:8px 10px;background:var(--gl);border-radius:8px;font-size:10px;color:var(--gd);margin-bottom:10px">
          ✓ بيانات البطاقة مشفرة ومحفوظة بأمان — سيتم الخصم تلقائياً عند تجديد الاشتراك
        </div>
        <button class="btn bg2" onclick="saveAutoSub()">حفظ بيانات الفوترة التلقائية</button>
      </div>

      <!-- Invoice history -->
      <div class="card cm">
        <div class="ch"><div class="ch-l"><div class="cico" style="background:var(--cl);color:var(--c)">🧾</div>سجل فواتير الاشتراك</div></div>
        <div id="sub-invoices-list">
          <div class="sub-inv-item">
            <div class="sub-inv-left">
              <div class="sub-inv-icon" style="background:var(--gl);color:var(--g)">💎</div>
              <div><div class="sub-inv-name">خطة احترافية — شهر أبريل 2026</div><div class="sub-inv-meta">تاريخ الفاتورة: 1 أبريل 2026</div></div>
            </div>
            <div class="sub-inv-right">
              <div class="sub-inv-amount" style="color:var(--g)">299 ر.س</div>
              <div class="sub-inv-status" style="color:var(--g)">مدفوعة ✓</div>
            </div>
          </div>
          <div class="sub-inv-item">
            <div class="sub-inv-left">
              <div class="sub-inv-icon" style="background:var(--gl);color:var(--g)">💎</div>
              <div><div class="sub-inv-name">خطة احترافية — شهر مارس 2026</div><div class="sub-inv-meta">تاريخ الفاتورة: 1 مارس 2026</div></div>
            </div>
            <div class="sub-inv-right">
              <div class="sub-inv-amount" style="color:var(--g)">299 ر.س</div>
              <div class="sub-inv-status" style="color:var(--g)">مدفوعة ✓</div>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- ══════ REPORTS ══════ -->
    <div class="pg" id="pg-reports">
      <div style="display:flex;gap:8px;flex-wrap:wrap;margin-bottom:12px">
        <button class="btn bg2" onclick="toast_('تم الإرسال للمسؤولين ✓')">إرسال للمسؤولين</button>
        <button class="btn bp" onclick="window.print()">طباعة / PDF</button>
        <button class="btn sm" onclick="toast_('تم نسخ الملخص ✓')">نسخ ملخص</button>
      </div>
      <div class="card" id="rep-card" style="border-top:3px solid var(--p)"><div style="text-align:center;padding:20px;font-size:12px;color:var(--muted)">شغّل المطابقة أولاً لإنشاء التقرير</div></div>
    </div>

    <!-- ══════ BACKUP ══════ -->
    <!-- ══════ SUPPORT TICKETS ══════ -->
    <div class="pg" id="pg-support">
      <div class="kg3" style="margin-bottom:12px">
        <div class="gmc gmc-blue" style="padding:14px"><span class="gm-icon" style="font-size:18px;margin-bottom:6px">🎫</span><div class="gm-val" id="tix-open-cnt" style="font-size:20px">0</div><div class="gm-lbl">تذاكر مفتوحة</div></div>
        <div class="gmc gmc-orange" style="padding:14px"><span class="gm-icon" style="font-size:18px;margin-bottom:6px">💬</span><div class="gm-val" id="tix-replied-cnt" style="font-size:20px">0</div><div class="gm-lbl">في انتظار ردك</div></div>
        <div class="gmc gmc-green" style="padding:14px"><span class="gm-icon" style="font-size:18px;margin-bottom:6px">✅</span><div class="gm-val" id="tix-closed-cnt" style="font-size:20px">0</div><div class="gm-lbl">مغلقة</div></div>
      </div>
      <div class="card cb">
        <div class="ch"><div class="ch-l"><div class="cico" style="background:var(--pl);color:var(--p)">🎫</div>فتح تذكرة دعم جديدة</div></div>
        <div style="font-size:11px;color:var(--muted);margin-bottom:10px">يصلنا طلبك مباشرة ونرد عليك في أقرب وقت</div>
        <div class="g2">
          <div class="fg"><label>موضوع التذكرة *</label><input id="tix-title" placeholder="مثال: مشكلة في تسجيل النزيل..."/></div>
          <div class="fg"><label>الفئة</label>
            <select id="tix-cat">
              <option value="support">🔧 دعم فني</option>
              <option value="billing">💳 فواتير واشتراكات</option>
              <option value="feature">💡 طلب ميزة جديدة</option>
              <option value="bug">🐞 إبلاغ عن خطأ</option>
              <option value="other">📋 أخرى</option>
            </select>
          </div>
          <div class="fg"><label>الأولوية</label>
            <select id="tix-priority">
              <option value="low">منخفضة</option>
              <option value="normal" selected>عادية</option>
              <option value="high">عالية</option>
              <option value="urgent">عاجلة 🔴</option>
            </select>
          </div>
        </div>
        <div class="fg"><label>تفاصيل المشكلة / الطلب *</label>
          <textarea id="tix-msg" style="min-height:90px;border:1.5px solid var(--border);border-radius:8px;padding:8px 10px;font-size:12px;background:var(--bg);color:var(--text);width:100%;resize:vertical;font-family:inherit" placeholder="اشرح المشكلة بالتفصيل حتى نتمكن من مساعدتك بسرعة..."></textarea>
        </div>
        <button class="btn bg2" onclick="openSupportTicket()">إرسال التذكرة ←</button>
      </div>
      <div class="card ca">
        <div class="ch"><div class="ch-l"><div class="cico" style="background:var(--al);color:var(--a)">📋</div>تذاكرك السابقة</div>
          <button class="btn sm" onclick="rSupport()">تحديث</button>
        </div>
        <div id="tix-list">
          <div style="text-align:center;padding:16px;font-size:12px;color:var(--muted)">لا توجد تذاكر سابقة</div>
        </div>
      </div>
    </div>

    <div class="pg" id="pg-backup">
      <div class="kg3">
        <div class="gmc gmc-blue" style="padding:14px"><span class="gm-icon" style="font-size:18px;margin-bottom:6px">💾</span><div class="gm-val" id="bk-last" style="font-size:14px">—</div><div class="gm-lbl">آخر نسخة احتياطية</div></div>
        <div class="gmc gmc-green" style="padding:14px"><span class="gm-icon" style="font-size:18px;margin-bottom:6px">📂</span><div class="gm-val" id="bk-cnt" style="font-size:20px">0</div><div class="gm-lbl">عدد النسخ المحفوظة</div></div>
        <div class="gmc gmc-dark" style="padding:14px"><span class="gm-icon" style="font-size:18px;margin-bottom:6px">📁</span><div class="gm-val" style="font-size:11px">HotelSystem/backups/</div><div class="gm-lbl">مسار الحفظ</div></div>
      </div>
      <div class="card cg">
        <div class="ch"><div class="ch-l"><div class="cico" style="background:var(--gl);color:var(--g)">💾</div>إنشاء نسخة احتياطية الآن</div></div>
        <div style="font-size:11px;color:var(--muted);margin-bottom:10px">تُحفظ جميع البيانات (نزلاء، موردين، فواتير، قيود...) في ملف JSON آمن على جهازك مباشرة</div>
        <div class="g2">
          <div class="fg"><label>وصف النسخة (اختياري)</label><input id="bk-label" placeholder="مثال: قبل تحديث الأسعار"/></div>
        </div>
        <div style="display:flex;gap:8px;flex-wrap:wrap">
          <button class="btn bg2" onclick="createBackup()">💾 إنشاء نسخة</button>
          <button class="btn bp" onclick="downloadBackupNow()" data-tt="تنزيل مباشر على جهازك — لا يُرسل لأي خادم">⬇️ تنزيل على جهازي</button>
          <button class="btn" style="background:var(--u);color:#fff;border-color:var(--u)" onclick="emailBackup()" data-tt="إرسال النسخة على إيميل المسؤولين — يحتاج إعداد SMTP في الإعدادات">📧 إرسال بالإيميل</button>
        </div>
      </div>
      <div class="card cu">
        <div class="ch"><div class="ch-l"><div class="cico" style="background:var(--ul);color:var(--u)">📧</div>إعدادات الإيميل (SMTP) <span class="tt-ic" data-tt="مطلوب لإرسال النسخ الاحتياطية والتقارير تلقائياً — استخدم Gmail مع App Password">ℹ️</span></div></div>
        <div style="padding:8px 10px;background:var(--ul);border-radius:8px;font-size:11px;color:var(--ud);margin-bottom:10px">
          📌 Gmail: فعّل المصادقة الثنائية ثم اذهب إلى <b>myaccount.google.com/apppasswords</b> وأنشئ كلمة مرور تطبيق
        </div>
        <div class="g2">
          <div class="fg"><label>إيميل المُرسِل (Gmail / Outlook)</label><input id="cfg-smtp-user" placeholder="your@gmail.com" oninput="saveSMTP()"/></div>
          <div class="fg"><label>App Password (كلمة مرور التطبيق)</label><input id="cfg-smtp-pass" type="password" placeholder="xxxx xxxx xxxx xxxx" oninput="saveSMTP()"/></div>
          <div class="fg"><label>SMTP Host</label><input id="cfg-smtp-host" placeholder="smtp.gmail.com" value="smtp.gmail.com" oninput="saveSMTP()"/></div>
          <div class="fg"><label>SMTP Port</label><input id="cfg-smtp-port" placeholder="587" value="587" oninput="saveSMTP()"/></div>
        </div>
        <div id="smtp-status" style="font-size:10px;color:var(--muted);margin-top:4px"></div>
      </div>
      <div class="card cb">
        <div class="ch"><div class="ch-l"><div class="cico" style="background:var(--pl);color:var(--p)">📂</div>النسخ الاحتياطية المحفوظة</div>
          <button class="btn sm" onclick="rBackup()">تحديث</button>
        </div>
        <div id="bk-list"></div>
      </div>
      <div class="ab ab-r" style="margin-bottom:0">
        <div class="ab-t">⚠️ تحذير: الاستعادة تستبدل جميع البيانات الحالية</div>
        <div style="font-size:10px;margin-top:2px">سيتم حفظ نسخة تلقائية قبل أي استعادة للأمان.</div>
      </div>
    </div>

    <!-- ══════ SETTINGS ══════ -->
    <div class="pg" id="pg-cfg">
      <!-- Tooltip system -->
      <div id="tt" style="display:none;position:fixed;background:#0F172A;color:#fff;font-size:11px;padding:7px 11px;border-radius:8px;max-width:220px;z-index:9999;line-height:1.5;box-shadow:0 4px 16px rgba(0,0,0,.3);pointer-events:none"></div>

      <!-- منشأة -->
      <div class="card cb">
        <div class="ch"><div class="ch-l"><div class="cico" style="background:var(--pl);color:var(--p)">🏨</div>إعدادات المنشأة</div></div>
        <div class="g2">
          <div class="fg"><label>اسم المنشأة <span class="tt-ic" data-tt="الاسم الذي يظهر في التقارير والفواتير المُرسلة للعملاء">ℹ️</span></label><input id="cfg-name" value="فندق النخبة"/></div>
          <div class="fg"><label>نوع المنشأة <span class="tt-ic" data-tt="يحدد نوع الأسعار المقارنة في السوق — فندق أو شقق مخدومة">ℹ️</span></label>
            <select id="cfg-type">
              <option value="hotel">🏨 فندق</option>
              <option value="apart">🏢 شقق فندقية</option>
              <option value="service">✨ شقق مخدومة</option>
            </select>
          </div>
          <div class="fg"><label>عدد الغرف / الوحدات <span class="tt-ic" data-tt="العدد الإجمالي للغرف أو الشقق — يُستخدم لحساب نسبة الإشغال و RevPAR">ℹ️</span></label><input type="number" id="cfg-rooms" value="50" min="1"/></div>
          <div class="fg"><label>المدينة <span class="tt-ic" data-tt="تحدد بيانات السوق المقارنة — أسعار المنافسين في نفس المدينة">ℹ️</span></label>
            <select id="cfg-city"><option value="riyadh">الرياض</option><option value="jeddah">جدة</option><option value="makkah">مكة المكرمة</option><option value="madinah">المدينة المنورة</option><option value="dammam">الدمام</option><option value="khobar">الخبر</option><option value="jubail">الجبيل</option><option value="ahsa">الأحساء</option><option value="abha">أبها</option><option value="taif">الطائف</option><option value="tabuk">تبوك</option><option value="qassim">القصيم</option><option value="hail">حائل</option><option value="bahah">الباحة</option><option value="other">أخرى</option></select>
          </div>
        </div>
        <button class="btn bg2" onclick="saveCfg()">حفظ إعدادات المنشأة</button>
      </div>

      <!-- أسعار الوحدات -->
      <div class="card" style="border-top:3px solid var(--u)">
        <div class="ch"><div class="ch-l"><div class="cico" style="background:var(--ul);color:var(--u)">💰</div>أسعار الوحدات — قابلة للتعديل <span class="tt-ic" data-tt="تُعبأ تلقائياً في نموذج إضافة النزيل — يمكن تغييرها يدوياً عند الإضافة أيضاً">ℹ️</span></div></div>
        <div class="g3" id="cfg-prices-hotel">
          <div class="fg"><label>🏨 غرفة عادية (ر.س) <span class="tt-ic" data-tt="سعر الليلة للغرفة العادية في الفندق">ℹ️</span></label><input type="number" id="cfg-p-hotel-std" placeholder="350" oninput="previewPrice('hotel-std',this.value)"/><div id="prev-hotel-std" style="font-size:10px;color:var(--g);margin-top:2px"></div></div>
          <div class="fg"><label>👑 جناح (ر.س) <span class="tt-ic" data-tt="سعر الليلة للجناح الفاخر">ℹ️</span></label><input type="number" id="cfg-p-hotel-suite" placeholder="650"/></div>
        </div>
        <div class="g3" id="cfg-prices-apart">
          <div class="fg"><label>🛏️ استوديو (ر.س) <span class="tt-ic" data-tt="شقة استوديو — غرفة واحدة مع مطبخ">ℹ️</span></label><input type="number" id="cfg-p-apart-studio" placeholder="280"/></div>
          <div class="fg"><label>🛋️ غرفة وصالة (ر.س)</label><input type="number" id="cfg-p-apart-one" placeholder="380"/></div>
          <div class="fg"><label>🛋️🛋️ غرفتان (ر.س)</label><input type="number" id="cfg-p-apart-two" placeholder="480"/></div>
          <div class="fg"><label>🏠 ثلاث غرف (ر.س)</label><input type="number" id="cfg-p-apart-three" placeholder="620"/></div>
        </div>
        <button class="btn bu2 sm" onclick="savePrices()">حفظ الأسعار</button>
      </div>

      <!-- طرق الدفع المخصصة -->
      <div class="card ct">
        <div class="ch"><div class="ch-l"><div class="cico" style="background:var(--tl);color:var(--t)">💳</div>طرق الدفع المقبولة <span class="tt-ic" data-tt="حدد طرق الدفع التي تقبلها — تظهر فقط في نماذج الإضافة والتقارير">ℹ️</span></div></div>
        <div id="pay-methods-grid" style="display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:8px;margin-bottom:10px"></div>
        <div class="fg"><label>إضافة طريقة دفع مخصصة (مثال: تحويل أجنبي، SadaPay...)</label>
          <div style="display:flex;gap:6px">
            <input id="new-pay-label" placeholder="اسم طريقة الدفع" style="flex:1"/>
            <input id="new-pay-icon" placeholder="أيقونة (رمز)" style="width:60px"/>
            <button class="btn bp sm" onclick="addCustomPay()">إضافة</button>
          </div>
        </div>
        <button class="btn bg2 sm" onclick="savePayMethods()">حفظ طرق الدفع</button>
      </div>

      <!-- بيانات البنك لاستلام الأموال -->
      <div class="card cg">
        <div class="ch"><div class="ch-l"><div class="cico" style="background:var(--gl);color:var(--g)">🏦</div>حسابي البنكي — لاستلام المدفوعات <span class="tt-ic" data-tt="يظهر في التقارير والفواتير ليعرف العميل أين يحول المبلغ — لا يُستخدم لأي خصم تلقائي">ℹ️</span></div></div>
        <div style="padding:8px 10px;background:var(--gl);border-radius:8px;font-size:11px;color:var(--gd);margin-bottom:10px;font-weight:600">
          🔒 هذه البيانات تظهر فقط في الفواتير والتقارير التي ترسلها — لا نجمع أي بيانات
        </div>
        <div class="g3">
          <div class="fg"><label>اسم صاحب الحساب <span class="tt-ic" data-tt="الاسم المسجل في البنك — يظهر في الفاتورة">ℹ️</span></label><input id="cfg-bank-name" placeholder="محمد عبدالله الغامدي"/></div>
          <div class="fg"><label>اسم البنك <span class="tt-ic" data-tt="مثال: بنك الراجحي، البنك الأهلي، الرياض...">ℹ️</span></label><input id="cfg-bank-bank" placeholder="بنك الراجحي"/></div>
          <div class="fg"><label>رقم الـ IBAN <span class="tt-ic" data-tt="رقم الحساب الدولي SA00 0000... — 24 خانة — يظهر في الفواتير">ℹ️</span></label><input id="cfg-bank-iban" placeholder="SA00 0000 0000 0000 0000 0000" style="font-family:monospace;letter-spacing:1px"/></div>
        </div>
        <button class="btn bg2" onclick="saveBankInfo()">حفظ بيانات البنك</button>
      </div>

      <!-- أسعار السوق اليدوية -->
      <div class="card ca">
        <div class="ch"><div class="ch-l"><div class="cico" style="background:var(--al);color:var(--a)">📊</div>أسعار السوق المرجعية <span class="tt-ic" data-tt="تُستخدم للمقارنة في لوحة التحكم — ادخل أسعار منافسيك">ℹ️</span></div></div>
        <div class="g2">
          <div class="fg"><label>متوسط سعر الفندق اليومي في مدينتك (ر.س)</label><input type="number" id="cfg-mkt-hotel" placeholder="340"/></div>
          <div class="fg"><label>متوسط سعر الشقق اليومي في مدينتك (ر.س)</label><input type="number" id="cfg-mkt-apart" placeholder="290"/></div>
        </div>
        <button class="btn ba2 sm" onclick="saveMktPrices()">حفظ أسعار السوق</button>
      </div>

      <!-- Claude AI Key -->
      <div class="card" style="border-top:3px solid var(--u)">
        <div class="ch"><div class="ch-l"><div class="cico" style="background:var(--ul);color:var(--u)">🤖</div>Claude AI — تحليل السوق التلقائي <span class="tt-ic" data-tt="أدخل مفتاح Claude API لتفعيل تحليل السوق بالذكاء الاصطناعي — يجلب الأسعار ويقدم توصيات">ℹ️</span></div>
          <a href="https://console.anthropic.com" target="_blank" style="font-size:10px;color:var(--p)">احصل على مفتاح مجاني ←</a>
        </div>
        <div class="fg"><label>Claude API Key</label><input id="cfg-claude-key" type="password" placeholder="sk-ant-xxxxxxxxxx"/></div>
        <button class="btn bu2" onclick="saveCfgFull()">حفظ + تفعيل AI</button>
      </div>

      <!-- Geidea -->
      <div class="card ca">
        <div class="ch"><div class="ch-l"><div class="cico" style="background:var(--al);color:var(--a)">🔑</div>Geidea — بوابة الدفع <span class="tt-ic" data-tt="ربط أجهزة نقاط البيع الفعلية بـ Geidea — تحتاج حساب تاجر من Geidea.com">ℹ️</span></div><span style="font-size:9px;padding:3px 8px;border-radius:10px;background:var(--gl);color:var(--gd);font-weight:700">اختياري</span></div>
        <div class="g2">
          <div class="fg"><label>Merchant Key (MK-) <span class="tt-ic" data-tt="مفتاح التاجر من لوحة تحكم Geidea">ℹ️</span></label><input id="cfg-mk" type="password" placeholder="MK-xxxxxx"/></div>
          <div class="fg"><label>API Password (AP-) <span class="tt-ic" data-tt="كلمة مرور API من لوحة تحكم Geidea">ℹ️</span></label><input id="cfg-ap" type="password" placeholder="AP-xxxxxx"/></div>
        </div>
        <button class="btn ba2" onclick="saveCfg()">حفظ</button>
      </div>

      <!-- المستلمون -->
      <div class="card cg">
        <div class="ch"><div class="ch-l"><div class="cico" style="background:var(--gl);color:var(--g)">👥</div>مستلمو التقارير <span class="tt-ic" data-tt="يُرسل لهم التقرير اليومي والنسخة الاحتياطية تلقائياً — يحتاج إعداد SMTP">ℹ️</span></div></div>
        <div id="recs-list" style="margin-bottom:10px"></div>
        <div style="display:flex;gap:6px;flex-wrap:wrap">
          <input id="cfg-rn" placeholder="الاسم" style="flex:1;min-width:80px;border:1.5px solid var(--border);border-radius:8px;padding:6px 9px;font-size:11px;background:var(--bg);color:var(--text)"/>
          <input id="cfg-re" type="email" placeholder="البريد الإلكتروني" style="flex:2;min-width:130px;border:1.5px solid var(--border);border-radius:8px;padding:6px 9px;font-size:11px;background:var(--bg);color:var(--text)"/>
          <button class="btn bp sm" onclick="addRec()">إضافة</button>
        </div>
      </div>
    </div>

  </div><!-- end content -->
</div><!-- end main -->
</div><!-- end app -->

<script>
const F=n=>Math.round(parseFloat(n||0)).toLocaleString('ar-SA');
const FR=n=>F(n)+' ر.س';
const NOW=new Date();
const TODAY=NOW.toISOString().split('T')[0];
const TNOW=()=>new Date().toLocaleTimeString('ar-SA',{hour:'2-digit',minute:'2-digit'});
const gv=id=>{const e=document.getElementById(id);return e?e.value:'';};
const ss=(id,v)=>{const e=document.getElementById(id);if(e)e.textContent=v;};
const pill=(l,bg,c)=>`<span style="font-size:9px;padding:3px 8px;border-radius:20px;display:inline-block;white-space:nowrap;font-weight:700;background:${bg};color:${c}">${l}</span>`;
const PAY_L={mada:'مدى',cash:'نقداً',visa:'فيزا',master:'ماستركارد',transfer:'تحويل',stc:'STC Pay',apple:'Apple Pay',credit:'آجل'};
const PAY_C={mada:'#1A56DB',cash:'#047857',visa:'#B45309',master:'#DC2626',transfer:'#7C3AED',stc:'#047857',apple:'#374151',credit:'#6B7280'};
const BED_L={double:'مزدوج',twin:'سريران',king:'كينج',suite:'جناح'};
const BED_C={double:'#1A56DB',twin:'#7C3AED',king:'#D97706',suite:'#047857'};
const SVC_L={laundry:'مغسلة',food:'طعام',room_service:'خدمة الغرفة',transport:'نقل',minibar:'ميني بار',parking:'موقف',gym:'صالة',pool:'مسبح',other:'أخرى'};
const SVC_C={laundry:'#1A56DB',food:'#B45309',room_service:'#EA580C',transport:'#7C3AED',minibar:'#DC2626',parking:'#047857',gym:'#D97706',pool:'#0891B2',other:'#374151'};
const SUP_L={util:'كهرباء',maint:'صيانة',laundry:'مغسلة',food:'طعام',supply:'لوازم',cleaning:'نظافة',security:'أمن',it:'تقنية',other:'أخرى'};
const SUP_C={util:'#1A56DB',maint:'#DC2626',laundry:'#7C3AED',food:'#B45309',supply:'#047857',cleaning:'#0891B2',security:'#EA580C',it:'#D97706',other:'#374151'};
const ACC_L={cash:'النقدية',bank:'البنك',receivable:'ذمم مدينة',room_rev:'إيرادات الغرف',svc_rev:'إيرادات الخدمات',util_exp:'كهرباء',maint_exp:'صيانة',supply_exp:'لوازم',payable:'ذمم دائنة',vat_payable:'VAT مستحق'};
const POS_DEPT={restaurant:'مطعم',cafe:'كافيه',laundry:'مغسلة',pool:'مسبح',reception:'استقبال',spa:'سبا',minibar:'ميني بار',gym:'صالة',parking:'موقف',shop:'محل',other:'أخرى'};
const POS_ICONS={restaurant:'🍽️',cafe:'☕',laundry:'👕',pool:'🏊',reception:'🏨',spa:'💆',minibar:'🍾',gym:'🏋️',parking:'🚗',shop:'🛍️',other:'💳'};
const POS_PAY=['cash','mada','visa','master','stc','apple','digital','transfer'];
const POS_PAY_L={cash:'نقداً',mada:'مدى',visa:'فيزا',master:'ماستركارد',stc:'STC Pay',apple:'Apple Pay',digital:'محافظ رقمية',transfer:'تحويل'};
const PMS_TYPES={opera:'Oracle Opera',opera_onprem:'Opera On-Premise',cloudbeds:'Cloudbeds',mews:'Mews',hotelogix:'Hotelogix',stayntouch:'StayNTouch',protel:'Protel Air',roommaster:'roommaster',custom:'Custom API'};
const PMS_ICONS={opera:'🏛️',opera_onprem:'🏛️',cloudbeds:'☁️',mews:'🌊',hotelogix:'🏨',stayntouch:'📱',protel:'⚡',roommaster:'🏠',custom:'🔧'};
const PAGE_META={
  dash:{ic:'🏠',bg:'linear-gradient(135deg,#047857,#10B981)',col:'#fff',title:'لوحة التحكم الرئيسية'},
  kpi:{ic:'📈',bg:'linear-gradient(135deg,#1A56DB,#3B82F6)',col:'#fff',title:'مؤشرات KPI + مقارنة السوق'},
  pms:{ic:'🔌',bg:'linear-gradient(135deg,#7C3AED,#A78BFA)',col:'#fff',title:'تكامل PMS — قراءة النزلاء'},
  guests:{ic:'🛏️',bg:'linear-gradient(135deg,#7C3AED,#A78BFA)',col:'#fff',title:'إدارة النزلاء'},
  svcs:{ic:'🍽️',bg:'linear-gradient(135deg,#EA580C,#F97316)',col:'#fff',title:'إيرادات الخدمات'},
  pos:{ic:'💳',bg:'linear-gradient(135deg,#D97706,#F59E0B)',col:'#fff',title:'أجهزة نقاط البيع'},
  journal:{ic:'📒',bg:'linear-gradient(135deg,#047857,#10B981)',col:'#fff',title:'دفتر اليومية'},
  trial:{ic:'⚖️',bg:'linear-gradient(135deg,#1A56DB,#3B82F6)',col:'#fff',title:'ميزان المراجعة'},
  pl:{ic:'📑',bg:'linear-gradient(135deg,#047857,#10B981)',col:'#fff',title:'الأرباح والخسائر'},
  recv:{ic:'📥',bg:'linear-gradient(135deg,#7C3AED,#A78BFA)',col:'#fff',title:'الذمم المدينة'},
  paybl:{ic:'📤',bg:'linear-gradient(135deg,#EA580C,#F97316)',col:'#fff',title:'الذمم الدائنة'},
  suppliers:{ic:'🏪',bg:'linear-gradient(135deg,#D97706,#F59E0B)',col:'#fff',title:'إدارة الموردين'},
  invoices:{ic:'🧾',bg:'linear-gradient(135deg,#DC2626,#F87171)',col:'#fff',title:'فواتير الموردين'},
  budget:{ic:'📋',bg:'linear-gradient(135deg,#1A56DB,#3B82F6)',col:'#fff',title:'الميزانية الهرمية'},
  cashflow:{ic:'💵',bg:'linear-gradient(135deg,#047857,#10B981)',col:'#fff',title:'التدفق النقدي'},
  match:{ic:'🔁',bg:'linear-gradient(135deg,#D97706,#F59E0B)',col:'#fff',title:'المطابقة اليومية — 23:59'},
  subscriptions:{ic:'💎',bg:'linear-gradient(135deg,#7C3AED,#1A56DB)',col:'#fff',title:'الاشتراكات والخطط'},
  reports:{ic:'📄',bg:'linear-gradient(135deg,#7C3AED,#A78BFA)',col:'#fff',title:'التقرير اليومي'},
  backup:{ic:'💾',bg:'linear-gradient(135deg,#1A56DB,#0891B2)',col:'#fff',title:'النسخ الاحتياطي والاستعادة'},
  cfg:{ic:'⚙️',bg:'linear-gradient(135deg,#374151,#6B7280)',col:'#fff',title:'الإعدادات'},
};

// State
let S={settings:{},guests:[],services:[],suppliers:[],invoices:[],receivables:[],journal_entries:[],pos_devices:[],budget_lines:[],market_rates:{},pms_integrations:[],pms_schedules:[],pms_reads:[]};
let matchResult=null,lastPMSData=[],marketData={};
// Subscription state
let subState={plan:'free',expires:null,auto:false,nextAmt:0,nextDate:null};

// Init
document.getElementById('tb-date').textContent=NOW.toLocaleDateString('ar-SA',{weekday:'short',month:'short',day:'numeric'});
const nd2=new Date();nd2.setDate(nd2.getDate()+1);
['gi-in'].forEach(id=>{const e=document.getElementById(id);if(e)e.value=TODAY;});
['gi-out','rec-d','inv-date','inv-due'].forEach(id=>{const e=document.getElementById(id);if(e)e.value=nd2.toISOString().split('T')[0];});

// Countdown
const deadline=new Date();deadline.setHours(23,59,0,0);if(deadline<NOW)deadline.setDate(deadline.getDate()+1);
setInterval(()=>{
  const d=deadline-new Date();
  const h=String(Math.floor(d/3600000)).padStart(2,'0');
  const m=String(Math.floor((d%3600000)/60000)).padStart(2,'0');
  const s2=String(Math.floor((d%60000)/1000)).padStart(2,'0');
  ['tb-cd','match-cd'].forEach(id=>{const e=document.getElementById(id);if(e)e.textContent=`${h}:${m}:${s2}`;});
},1000);

// ── SUPPORT TICKETS (CLIENT SIDE) ────────────────────────────
async function rSupport(){
  const r = await api('/api/tickets');
  const tix = r.tickets || [];
  const open = tix.filter(t=>t.status==='open'||t.status==='replied');
  const closed = tix.filter(t=>t.status==='closed');
  ss('tix-open-cnt', tix.filter(t=>t.status==='open').length);
  ss('tix-replied-cnt', tix.filter(t=>t.status==='replied').length);
  ss('tix-closed-cnt', closed.length);
  const badge = document.getElementById('sup-tix-badge');
  if(badge) badge.style.display = open.length ? 'inline' : 'none';
  const catL = {support:'دعم فني',billing:'فواتير',feature:'طلب ميزة',bug:'خطأ',other:'أخرى'};
  const stL  = {open:'مفتوحة',replied:'مُجاب عليه',closed:'مغلقة'};
  const stC  = {open:'var(--r)',replied:'var(--a)',closed:'var(--g)'};
  const el = document.getElementById('tix-list');
  if(!el) return;
  el.innerHTML = tix.length ? [...tix].reverse().map(t => {
    const msgs = t.messages || [];
    const lastMsg = msgs[msgs.length-1];
    const hasAdminReply = msgs.some(m=>m.from==='admin');
    return `<div style="background:var(--bg);border-radius:10px;padding:12px;margin-bottom:8px;border:1.5px solid ${hasAdminReply&&t.status!=='closed'?'var(--g)':'var(--border)'}">
      <div style="display:flex;align-items:flex-start;justify-content:space-between;flex-wrap:wrap;gap:6px">
        <div>
          <div style="font-size:12px;font-weight:700;color:var(--text)">${t.title}</div>
          <div style="font-size:10px;color:var(--muted);margin-top:2px">${catL[t.category]||t.category||'—'} · ${new Date(t.created_at).toLocaleDateString('ar-SA')}</div>
        </div>
        <span style="font-size:9px;padding:3px 9px;border-radius:20px;font-weight:700;background:${stC[t.status]||'var(--muted)'}22;color:${stC[t.status]||'var(--muted)'}">${stL[t.status]||t.status}</span>
      </div>
      ${msgs.length ? `<div style="margin-top:8px;max-height:160px;overflow-y:auto;display:flex;flex-direction:column;gap:5px">
        ${msgs.map(m=>`<div style="padding:6px 9px;border-radius:8px;font-size:11px;background:${m.from==='admin'?'var(--gl)':'var(--pl)'};color:${m.from==='admin'?'var(--gd)':'var(--pd)'};max-width:85%;${m.from==='admin'?'margin-right:0':'margin-left:auto'}">
          <div style="font-size:9px;font-weight:700;margin-bottom:3px">${m.from==='admin'?'🛡️ فريق الدعم':'أنت'}</div>
          <div>${m.text}</div>
        </div>`).join('')}
      </div>` : ''}
      ${t.status!=='closed'?`<div style="margin-top:8px;display:flex;gap:6px">
        <input id="tix-reply-${t.id}" placeholder="رد على التذكرة..." style="flex:1;border:1.5px solid var(--border);border-radius:8px;padding:6px 9px;font-size:11px;background:var(--card);color:var(--text)"/>
        <button class="btn sm bg2" onclick="sendTixMsg(${t.id})">إرسال</button>
      </div>`:''}
    </div>`;
  }).join('') : '<div style="text-align:center;padding:16px;font-size:12px;color:var(--muted)">لا توجد تذاكر — افتح تذكرة جديدة إذا احتجت مساعدة</div>';
}
async function openSupportTicket(){
  const title = gv('tix-title').trim();
  const msg   = gv('tix-msg').trim();
  if(!title || !msg){toast_('أدخل الموضوع والتفاصيل',false);return;}
  const r = await api('/api/tickets/open',{
    title, message:msg, category:gv('tix-cat'), priority:gv('tix-priority')
  });
  if(r.ok){
    const te=document.getElementById('tix-title'); if(te)te.value='';
    const me=document.getElementById('tix-msg');   if(me)me.value='';
    await rSupport();
    toast_('تم إرسال التذكرة ✓ — سنرد عليك قريباً');
  } else toast_(r.error||'خطأ في الإرسال',false);
}
async function sendTixMsg(id){
  const el = document.getElementById('tix-reply-'+id);
  const text = el ? el.value.trim() : '';
  if(!text){toast_('أدخل رسالة',false);return;}
  const r = await api('/api/tickets/message',{id,text});
  if(r.ok){if(el)el.value='';await rSupport();toast_('تم الإرسال ✓');}
}

async function boot(){
  const r=await fetch('/api/store');S=await r.json();
  ss('sb-name',S.settings.name||'فندق');
  const tL={hotel:'HOTEL',apart:'APARTMENTS',service:'SERVICED APTS'};
  ss('sb-type',tL[S.settings.type]||'HOTEL MANAGEMENT');
  await loadMarket();
  renderUnitTypeGrid();
  buildPaySelect('gi-pay');
  go('dash');
}
boot();

// Navigation
function go(pg){
  document.querySelectorAll('.ni').forEach(n=>n.classList.remove('on'));
  document.querySelectorAll('.pg').forEach(p=>p.classList.remove('on'));
  const pgEl=document.getElementById('pg-'+pg);if(pgEl)pgEl.classList.add('on');
  document.querySelectorAll('.ni').forEach(n=>{if(n.getAttribute('onclick')===`go('${pg}')`)n.classList.add('on');});
  const m=PAGE_META[pg]||{ic:'📄',bg:'#374151',col:'#fff',title:pg};
  const ti=document.getElementById('tb-ic');if(ti){ti.textContent=m.ic;ti.style.background=m.bg;ti.style.color=m.col;}
  ss('tb-title',m.title);
  const rs={dash:rDash,kpi:rKPI,pms:rPMS,guests:rGuests,support:rSupport,svcs:rSvcs,pos:rPOS,journal:rJnl,trial:rTrial,pl:rPL,recv:rRecv,paybl:rPaybl,suppliers:rSup,invoices:rInv,budget:rBudget,cashflow:rCashflow,match:rMatchPage,subscriptions:rSubscriptions,reports:rReport,backup:rBackup,cfg:rCfg};
  if(rs[pg])rs[pg]();
}

// Helpers
const sysIn=()=>S.guests.reduce((a,g)=>a+g.total,0)+S.services.reduce((a,s)=>a+s.amount,0);
const sysOut=()=>S.invoices.filter(i=>i.status!=='paid').reduce((a,i)=>a+i.total,0);
const posNet=()=>S.pos_devices.reduce((a,d)=>a+(d.data?d.data.sales-d.data.refund:0),0);
async function api(path,body=null){const opt=body?{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)}:{};const r=await fetch(path,opt);return r.json();}
async function reload(){const d=await api('/api/store');Object.assign(S,d);}
function toast_(msg,ok=true){const t=document.getElementById('toast');t.textContent=msg;t.style.background=ok?'var(--g)':'var(--r)';t.style.boxShadow=ok?'0 4px 14px rgba(4,120,87,.4)':'0 4px 14px rgba(220,38,38,.4)';t.classList.add('show');setTimeout(()=>t.classList.remove('show'),2800);}

// ── SEARCH ──────────────────────────────────────────────────
let searchTimer=null;
async function doSearch(q){
  clearTimeout(searchTimer);
  const el=document.getElementById('search-res');
  if(!q.trim()){if(el)el.innerHTML='';return;}
  searchTimer=setTimeout(async()=>{
    const r=await api('/api/search',{q});const res=r.results||[];
    if(!el)return;
    el.innerHTML=res.length?res.map(x=>`<div onclick="go('${x.goto}');document.getElementById('search-box').value='';document.getElementById('search-res').style.display='none'" style="padding:8px 10px;cursor:pointer;border-radius:8px;display:flex;align-items:center;gap:9px" onmouseover="this.style.background='var(--bg)'" onmouseout="this.style.background=''">
      <span style="font-size:16px">${{guest:'🛏️',supplier:'🏪',invoice:'🧾',journal:'📒',recv:'📥'}[x.type]||'🔍'}</span>
      <div><div style="font-size:11px;font-weight:700;color:var(--text)">${x.label}</div><div style="font-size:10px;color:var(--muted)">${x.sub}</div></div>
    </div>`).join(''):`<div style="padding:12px;font-size:11px;color:var(--muted);text-align:center">لا توجد نتائج لـ "${q}"</div>`;
  },280);
}

// ── MARKET ──────────────────────────────────────────────────
async function loadMarket(){
  try{
    const r=await api('/api/market');
    marketData=r;
    updateSeasonUI(r.season_label,r.season_factor);
    renderMarketDash(r);
    if(document.getElementById('pg-kpi').classList.contains('on'))renderMarketKPI(r);
  }catch(e){}
}
function updateSeasonUI(label,factor){
  const isHigh=factor>=2;const isMed=factor>=1.4;
  const bg=isHigh?'#FEF2F2':isMed?'#FFFBEB':'#ECFDF5';
  const col=isHigh?'#991B1B':isMed?'#92400E':'#065F46';
  ['tb-season','d-season-badge'].forEach(id=>{
    const el=document.getElementById(id);if(!el)return;
    el.textContent=`⭐ ${label} × ${factor}`;el.style.background=bg;el.style.color=col;
  });
}
function setMktCard(prefix,ours,mkt,unit,color){
  const diff=ours-mkt;
  const pct=mkt?Math.round(ours/mkt*100):100;
  ss(prefix+'-ours',`${F(ours)}${unit}`);
  ss(prefix+'-mkt',`السوق: ${F(mkt)}${unit}`);
  const bar=document.getElementById(prefix+'-bar');if(bar){bar.style.width=Math.min(pct,100)+'%';bar.style.background=color;}
  const mark=document.getElementById(prefix+'-mark');if(mark)mark.style.right=(100-Math.min(100,pct))+'%';
  const diffEl=document.getElementById(prefix+'-diff');
  if(diffEl){diffEl.textContent=(diff>=0?'↑ أعلى بـ':'↓ أقل بـ')+` ${F(Math.abs(diff))}${unit}`;diffEl.style.background=diff>=0?'#ECFDF5':'#FEF2F2';diffEl.style.color=diff>=0?'#065F46':'#991B1B';}
}
function renderMarketDash(r){
  if(!r||!r.market_adr)return;
  setMktCard('mkt-adr',r.our_adr,r.market_adr,' ر.س','#1A56DB');
  setMktCard('mkt-occ',r.our_occ,r.market_occ,'%','#047857');
  setMktCard('mkt-revpar',r.our_revpar,r.market_revpar,' ر.س','#7C3AED');
  const rec=document.getElementById('d-season-rec');
  if(rec&&r.season_factor>=1.5){
    rec.style.display='block';
    const recommended=Math.round(r.market_adr*r.season_factor);
    rec.innerHTML=`🔥 موسم ${r.season_label} × ${r.season_factor} — السعر الموصى به: <b>${F(recommended)} ر.س</b> (السوق ${F(r.market_adr)} × ${r.season_factor})`;
  } else if(rec){rec.style.display='none';}
}
function renderMarketKPI(r){
  if(!r)return;
  document.getElementById('kpi-market-detail').innerHTML=`
  <div class="mkt-cmp" style="margin-bottom:10px">
    ${[
      {l:'ADR — متوسط السعر',ours:r.our_adr,mkt:r.market_adr,diff:r.adr_diff,u:' ر.س',c:'#1A56DB'},
      {l:'نسبة الإشغال',ours:r.our_occ,mkt:r.market_occ,diff:r.occ_diff,u:'%',c:'#047857'},
      {l:'RevPAR',ours:r.our_revpar,mkt:r.market_revpar,diff:r.revpar_diff,u:' ر.س',c:'#7C3AED'},
    ].map(k=>`<div class="mkt-item">
      <div class="mkt-label">${k.l}</div>
      <div style="display:flex;justify-content:space-between;align-items:flex-end;margin-bottom:8px">
        <div><div style="font-size:9px;color:var(--muted)">أداؤنا</div><div style="font-size:20px;font-weight:700;color:${k.diff>=0?k.c:'#DC2626'}">${F(k.ours)}${k.u}</div></div>
        <div style="text-align:left"><div style="font-size:9px;color:var(--muted)">السوق</div><div style="font-size:16px;font-weight:700;color:var(--muted)">${F(k.mkt)}${k.u}</div></div>
      </div>
      <div style="padding:5px 9px;border-radius:8px;font-size:11px;font-weight:700;text-align:center;background:${k.diff>=0?'#ECFDF5':'#FEF2F2'};color:${k.diff>=0?'#065F46':'#991B1B'}">
        ${k.diff>=0?'↑ أعلى من السوق':'↓ أقل من السوق'} بـ ${F(Math.abs(k.diff))}${k.u}
      </div>
    </div>`).join('')}
  </div>
  <div style="padding:10px 12px;background:linear-gradient(135deg,var(--al),#FEF3C7);border-radius:10px;font-size:11px;color:var(--ad);font-weight:700">
    ⭐ الموسم الحالي: ${r.season_label} × ${r.season_factor} — السعر الموصى به = ${F(r.market_adr)} × ${r.season_factor} = <b style="font-size:13px">${F(Math.round(r.market_adr*r.season_factor))} ر.س</b>
  </div>`;
}
async function updateMarket(){
  const city=gv('mkt-city');
  const rates={hotel_avg:parseFloat(gv('mkt-hadr')||0),apart_avg:parseFloat(gv('mkt-aadr')||0),hotel_occ:parseFloat(gv('mkt-hocc')||0),apart_occ:parseFloat(gv('mkt-aocc')||0)};
  if(!rates.hotel_avg){toast_('أدخل متوسط سعر الفندق',false);return;}
  const r=await api('/api/market/update',{city,rates,source:'manual'});
  if(r.ok){await reload();await loadMarket();toast_('تم تحديث أسعار السوق ✓');}
}

// ── DASHBOARD ───────────────────────────────────────────────
async function rDash(){
  const si=sysIn(),so=sysOut(),net=si-so,margin=si>0?Math.round(net/si*100):0;
  const act=S.guests.filter(g=>g.status==='active');
  const occ=S.settings.rooms?Math.round(act.length/S.settings.rooms*100):0;
  const revpar=S.settings.rooms?Math.round(S.guests.reduce((a,g)=>a+g.total,0)/S.settings.rooms):0;
  const pend=S.invoices.filter(i=>i.status==='pending');
  const posRecv=S.pos_devices.filter(d=>d.data).length;
  const lastPMS=S.pms_reads&&S.pms_reads.length?S.pms_reads[S.pms_reads.length-1]:null;
  ss('d-rev',FR(si));ss('d-revpar',F(revpar)+' ر.س');ss('d-occ-pct',occ+'%');
  ss('d-occ-sub',act.length+' نزيل مقيم');
  const ne=document.getElementById('d-net');if(ne){ne.textContent=FR(net);ne.style.color=net>=0?'#fff':'#FECACA';}
  ss('d-mrg','هامش '+margin+'%');ss('d-exp',FR(so));ss('d-alerts',pend.length);
  const rt=document.getElementById('d-rev-trend');if(rt){rt.textContent=(margin>=0?'↑':'↓')+margin+'%';rt.style.background=margin>=20?'rgba(255,255,255,.25)':'rgba(255,255,255,.15)';}
  ss('d-pos',posRecv+'/'+S.pos_devices.length+' أجهزة');ss('d-pos-s',posRecv===S.pos_devices.length&&S.pos_devices.length>0?'جميعها مُستلمة ✓':'في الانتظار');
  if(lastPMS){ss('d-pms',lastPMS.guests_found+' نزيل');ss('d-pms-s','آخر قراءة: '+new Date(lastPMS.time).toLocaleTimeString('ar-SA',{hour:'2-digit',minute:'2-digit'}));}
  const rC={};S.guests.forEach(g=>{rC['إيرادات الغرف']=(rC['إيرادات الغرف']||0)+g.total;});S.services.forEach(s=>{rC[SVC_L[s.type]||s.type]=(rC[SVC_L[s.type]||s.type]||0)+s.amount;});
  document.getElementById('d-rev-det').innerHTML=Object.entries(rC).map(([k,v])=>`<div class="dr"><span style="color:var(--muted)">${k}</span><span style="color:var(--g);font-weight:700">${FR(v)}</span></div>`).join('')+`<div class="dr tot"><span>الإجمالي</span><span style="color:var(--g)">${FR(si)}</span></div>`;
  document.getElementById('d-exp-det').innerHTML=(pend.length?pend.map(i=>`<div class="dr"><span style="color:var(--muted)">${i.supName}</span><span style="color:var(--r)">${FR(i.total)}</span></div>`).join(''):
  '<div class="dr"><span style="color:var(--muted)">لا توجد فواتير معلقة</span><span style="color:var(--g)">✓</span></div>')+`<div class="dr tot"><span>الإجمالي</span><span style="color:var(--r)">${FR(so)}</span></div>`;
  const ins=[];
  if(net>0)ins.push({c:'g',t:'صافي إيجابي',d:`${FR(net)} — هامش ${margin}%`});
  if(pend.length)ins.push({c:'r',t:`${pend.length} فاتورة موردين معلقة`,d:'راجع تبويب فواتير الموردين'});
  if(occ>=75)ins.push({c:'g',t:`إشغال ممتاز ${occ}%`,d:'أعلى من معيار 70%'});
  else if(occ<50&&S.guests.length>0)ins.push({c:'a',t:`إشغال منخفض ${occ}%`,d:'راجع استراتيجية التسعير'});
  if(posRecv<S.pos_devices.length)ins.push({c:'i',t:`${S.pos_devices.length-posRecv} أجهزة POS لم تُستلم`,d:'اذهب لنقاط البيع'});
  if(marketData&&marketData.our_adr<marketData.market_adr)ins.push({c:'a',t:`سعرنا أقل من السوق بـ ${F(marketData.market_adr-marketData.our_adr)} ر.س`,d:`السوق: ${F(marketData.market_adr)} — سعرنا: ${F(marketData.our_adr)}`});
  if(marketData&&marketData.season_factor>=2)ins.push({c:'g',t:`موسم مرتفع: ${marketData.season_label} × ${marketData.season_factor}`,d:'ارفع أسعارك الآن!'});
  document.getElementById('d-insights').innerHTML=ins.map(i=>`<div class="ab ab-${i.c}" style="margin-bottom:5px"><div class="ab-t">${i.t}</div><div style="font-size:10px;margin-top:1px">${i.d}</div></div>`).join('')||'<div style="font-size:11px;color:var(--muted)">أدخل بيانات لظهور التحليل</div>';
  const sb=document.getElementById('sup-badge');if(sb)sb.style.display=pend.length?'inline':'none';
  const pb=document.getElementById('pos-badge');if(pb)pb.style.display=posRecv<S.pos_devices.length?'inline':'none';
  renderMarketDash(marketData);
  await loadMarket();
}

// ── KPI ────────────────────────────────────────────────────
function rKPI(){calcKPI();renderMarketKPI(marketData);}
function calcKPI(){
  const rooms=parseFloat(gv('kp-rooms')||50),occR=parseFloat(gv('kp-occ-r')||0),nights=parseFloat(gv('kp-nights')||1)||1;
  const rrev=parseFloat(gv('kp-rrev')||0),trev=parseFloat(gv('kp-trev')||0),texp=parseFloat(gv('kp-texp')||0);
  const revpar=rooms?Math.round(rrev/rooms):0,adr=nights?Math.round(rrev/nights):0;
  const occ=rooms?Math.round(occR/rooms*100):0,gop=trev?Math.round((trev-texp)/trev*100):0,trevpar=rooms?Math.round(trev/rooms):0;
  ss('kp-revpar',F(revpar)+' ر.س');ss('kp-adr',F(adr)+' ر.س');ss('kp-occ',occ+'%');ss('kp-gop',gop+'%');ss('kp-trevpar',F(trevpar)+' ر.س');ss('kp-npm',gop+'%');
  const benches=[{n:'RevPAR',v:revpar,b:280,u:' ر.س'},{n:'ADR',v:adr,b:380,u:' ر.س'},{n:'إشغال',v:occ,b:70,u:'%'},{n:'GOP',v:gop,b:35,u:'%'},{n:'TRevPAR',v:trevpar,b:350,u:' ر.س'}];
  document.getElementById('kp-bench').innerHTML=benches.map(b=>{const good=b.v>=b.b,mV=Math.max(b.v,b.b,1);return`<div class="brow"><div class="brow-l">${b.n}</div><div class="brow-t"><div class="brow-f" style="width:${Math.round(b.v/mV*100)}%;background:${good?'var(--g)':'var(--r)'}"></div><div style="position:absolute;top:0;height:8px;width:2px;background:var(--muted);right:${100-Math.round(b.b/mV*100)}%"></div></div><div class="brow-v"><span style="color:${good?'var(--g)':'var(--r)'};font-weight:700">${b.v}${b.u}</span><span style="color:var(--muted);font-size:9px"> معيار ${b.b}${b.u}</span></div></div>`;}).join('');
}

// ── PMS ──────────────────────────────────────────────────────
function rPMS(){
  const intgs=S.pms_integrations||[],reads=S.pms_reads||[];
  ss('pms-cnt',intgs.length);
  const lr=reads.length?reads[reads.length-1]:null;
  ss('pms-last',lr?new Date(lr.time).toLocaleTimeString('ar-SA',{hour:'2-digit',minute:'2-digit'}):'—');
  ss('pms-gf',lr?lr.guests_found:0);ss('pms-rc',reads.length);
  document.getElementById('pms-list').innerHTML=intgs.length?intgs.map(intg=>`
    <div class="pms-card ${intg.enabled?'connected':''}">
      <div class="pms-header">
        <div class="pms-icon" style="background:var(--pl);color:var(--p)">${PMS_ICONS[intg.type]||'🔌'}</div>
        <div class="pms-info">
          <div class="pms-name">${intg.name}</div>
          <div class="pms-meta">${PMS_TYPES[intg.type]||intg.type} · ${intg.url||'لا يوجد URL'} · قراءات: ${intg.read_count||0}</div>
          ${intg.last_read?`<div style="font-size:9px;color:var(--muted)">آخر قراءة: ${new Date(intg.last_read).toLocaleString('ar-SA')}</div>`:''}
        </div>
        <div class="pms-acts">
          <button class="btn bp sm" onclick="readPMS(${intg.id})">قراءة الآن</button>
          <button class="btn sm" onclick="togglePMSForm(${intg.id})">جدولة</button>
          <button class="btn sm" style="color:var(--r)" onclick="delPMS(${intg.id})">حذف</button>
        </div>
      </div>
      <div class="pms-form" id="pmsf-${intg.id}">
        <div class="g3">
          <div class="fg"><label>التكرار</label><select id="pms-freq-${intg.id}"><option value="manual">يدوي فقط</option><option value="hourly">كل ساعة</option><option value="every6h">كل 6 ساعات</option><option value="daily">يومي</option></select></div>
          <div class="fg"><label>وقت القراءة اليومية</label><input type="time" id="pms-time-${intg.id}" value="08:00"/></div>
          <div class="fg"><label>التفعيل</label><select id="pms-en-${intg.id}"><option value="true">مفعّل</option><option value="false">موقوف</option></select></div>
        </div>
        <button class="btn bp sm" onclick="savePMSSched(${intg.id})">حفظ الجدولة</button>
      </div>
    </div>`).join(''):'<div style="text-align:center;padding:16px;font-size:12px;color:var(--muted)">لا يوجد تكاملات — أضف نظام PMS</div>';
  loadPMSReads();
}
function toggleAddPMS(){const f=document.getElementById('add-pms-form');f.style.display=f.style.display==='none'?'block':'none';}
function togglePMSForm(id){const f=document.getElementById('pmsf-'+id);if(f)f.classList.toggle('open');}
async function addPMS(){
  const name=gv('pms-new-name').trim();if(!name){toast_('أدخل اسم النظام',false);return;}
  const r=await api('/api/pms/add',{name,type:gv('pms-new-type'),url:gv('pms-new-url'),username:gv('pms-new-user'),password:gv('pms-new-pass'),api_key:gv('pms-new-key')});
  if(r.ok){await reload();toggleAddPMS();rPMS();toast_(`تم إضافة "${name}" ✓`);}
}
async function delPMS(id){if(!confirm('حذف هذا التكامل؟'))return;await api('/api/pms/delete',{id});await reload();rPMS();toast_('تم الحذف');}
async function readPMS(id){
  const intg=S.pms_integrations.find(i=>i.id===id);if(!intg)return;
  toast_('جارٍ القراءة من '+intg.name+'...');
  const r=await api('/api/pms/read',{id});
  if(r.ok){await reload();lastPMSData=r.data||[];const dc=document.getElementById('pms-data-card');if(dc)dc.style.display='block';
    document.getElementById('pms-data-table').innerHTML=`<div style="overflow-x:auto"><table class="tbl"><thead><tr><th>PMS ID</th><th>اسم النزيل</th><th>الغرفة</th><th>الوصول</th><th>المغادرة</th><th>السعر</th><th>الحالة</th></tr></thead><tbody>${lastPMSData.map(g=>`<tr><td style="font-size:9px;color:var(--muted)">${g.pms_id}</td><td style="font-weight:700">${g.name}</td><td>${g.room}</td><td style="font-size:9px">${g.checkin}</td><td style="font-size:9px">${g.checkout}</td><td style="color:var(--g);font-weight:700">${FR(g.rate)}</td><td>${pill(g.status==='inhouse'?'مقيم':g.status==='reserved'?'محجوز':'غادر',g.status==='inhouse'?'#ECFDF5':g.status==='reserved'?'#FFFBEB':'#F9FAFB',g.status==='inhouse'?'#065F46':g.status==='reserved'?'#92400E':'#374151')}</td></tr>`).join('')}</tbody></table></div>`;
    rPMS();toast_(`تم قراءة ${r.guests_found} نزيل من ${intg.name} ✓`);}
}
async function importPMSGuests(){
  if(!lastPMSData.length){toast_('لا توجد بيانات',false);return;}
  let imp=0;
  for(const g of lastPMSData){if(g.status==='inhouse'){const n=Math.max(1,Math.round((new Date(g.checkout)-new Date(g.checkin))/86400000));await api('/api/guests/add',{name:g.name,idNum:g.pms_id,unit:g.room,bed:'double',extra:0,inDate:g.checkin,outDate:g.checkout,nights:n,price:g.rate,pay:'credit'});imp++;}}
  await reload();rGuests();toast_(`تم استيراد ${imp} نزيل ✓`);
}
async function savePMSSched(id){await api('/api/pms/schedule/save',{intg_id:id,frequency:gv('pms-freq-'+id),time:gv('pms-time-'+id),enabled:gv('pms-en-'+id)==='true'});toast_('تم حفظ الجدولة ✓');togglePMSForm(id);}
async function loadPMSReads(){await reload();const reads=(S.pms_reads||[]).slice().reverse().slice(0,10);document.getElementById('pms-reads-body').innerHTML=reads.length?reads.map(r=>`<tr><td style="font-size:9px;color:var(--muted)">${new Date(r.time).toLocaleString('ar-SA')}</td><td style="font-weight:700">${r.intg_name}</td><td style="color:var(--g);font-weight:700">${r.guests_found}</td><td>${pill(r.status==='success'?'نجاح':'خطأ',r.status==='success'?'var(--gl)':'var(--rl)',r.status==='success'?'var(--g)':'var(--r)')}</td><td><button class="btn sm" onclick="showPMSRead(${r.id})">عرض</button></td></tr>`).join(''):'<tr><td colspan="5" style="text-align:center;padding:12px;color:var(--muted)">لا توجد قراءات</td></tr>';}
function showPMSRead(id){const r=S.pms_reads.find(x=>x.id===id);if(r&&r.data){lastPMSData=r.data;const dc=document.getElementById('pms-data-card');if(dc){dc.style.display='block';document.getElementById('pms-data-table').innerHTML=`<div style="overflow-x:auto"><table class="tbl"><thead><tr><th>PMS ID</th><th>الاسم</th><th>الغرفة</th><th>السعر</th><th>الحالة</th></tr></thead><tbody>${r.data.map(g=>`<tr><td style="font-size:9px">${g.pms_id}</td><td style="font-weight:700">${g.name}</td><td>${g.room}</td><td style="color:var(--g);font-weight:700">${FR(g.rate)}</td><td>${pill(g.status==='inhouse'?'مقيم':'محجوز','var(--gl)','var(--g)')}</td></tr>`).join('')}</tbody></table></div>`;dc.scrollIntoView({behavior:'smooth'});}}}

// ── GUESTS ───────────────────────────────────────────────────
function calcGuestPrev(){const d1=new Date(gv('gi-in')),d2=new Date(gv('gi-out'));const n=Math.max(1,Math.round((d2-d1)/86400000)),p=parseFloat(gv('gi-price')||0);const el=document.getElementById('gi-calc');if(el)el.textContent=FR(n*p);}
async function addGuest(){
  const name=gv('gi-name').trim();if(!name){toast_('أدخل اسم النزيل',false);return;}
  const d1=new Date(gv('gi-in')),d2=new Date(gv('gi-out'));const nights=Math.max(1,Math.round((d2-d1)/86400000));
  const r=await api('/api/guests/add',{name,idNum:gv('gi-id'),unit:gv('gi-unit'),bed:gv('gi-bed'),extra:parseInt(gv('gi-extra')||0),inDate:gv('gi-in'),outDate:gv('gi-out'),nights,price:parseFloat(gv('gi-price')||0),pay:gv('gi-pay')});
  if(r.ok){S.guests.push(r.guest);rGuests();rDash();toast_(`تم تسجيل ${name} + قيد محاسبي ✓`);['gi-name','gi-id','gi-unit','gi-price'].forEach(id=>{const e=document.getElementById(id);if(e)e.value='';});}
}
function rGuests(){
  const act=S.guests.filter(g=>g.status==='active'),rev=S.guests.reduce((a,g)=>a+g.total,0);
  ss('g-tot',S.guests.length);ss('g-act',act.length);ss('g-rev',FR(rev));ss('g-avg',S.guests.length?Math.round(S.guests.reduce((a,g)=>a+g.nights,0)/S.guests.length)+' ليالٍ':'—');
  document.getElementById('g-body').innerHTML=S.guests.map(g=>`<tr><td style="font-weight:700">${g.unit||'—'}</td><td><div style="font-weight:600">${g.name}</div><div style="font-size:9px;color:var(--muted)">${g.idNum}</div></td><td>${pill((BED_L[g.bed]||g.bed)+(g.extra?` +${g.extra}✦`:''),BED_C[g.bed]+'22',BED_C[g.bed])}</td><td style="font-size:9px">${g.inDate}</td><td style="text-align:center">${g.nights}</td><td style="color:var(--g);font-weight:700">${FR(g.total)}</td><td>${pill(PAY_L[g.pay]||g.pay,PAY_C[g.pay]+'22',PAY_C[g.pay])}</td><td>${pill(g.status==='active'?'مقيم':'غادر',g.status==='active'?'var(--gl)':'var(--nl)',g.status==='active'?'var(--g)':'var(--n)')}</td><td>${g.status==='active'?`<button class="btn sm" onclick="checkout(${g.id})">مغادرة</button>`:'—'}</td></tr>`).join('')||'<tr><td colspan="9" style="text-align:center;padding:14px;color:var(--muted)">لا يوجد نزلاء</td></tr>';
  document.getElementById('g-foot').innerHTML=`<tr><td colspan="5" style="padding:6px 8px">الإجمالي</td><td style="color:var(--g)">${FR(rev)}</td><td colspan="3"></td></tr>`;
}
async function checkout(id){await api('/api/guests/checkout',{id});const g=S.guests.find(x=>x.id===id);if(g)g.status='checkedout';rGuests();rDash();toast_('تم تسجيل المغادرة ✓');}

// ── SERVICES ─────────────────────────────────────────────────
async function addSvc(){const amt=parseFloat(gv('sv-amt')||0);if(amt<=0){toast_('أدخل المبلغ',false);return;}const r=await api('/api/services/add',{type:gv('sv-type'),unit:gv('sv-unit'),pay:gv('sv-pay'),amount:amt});if(r.ok){S.services.push(r.service);rSvcs();rDash();toast_(`تم تسجيل ${SVC_L[r.service.type]} ✓`);const e=document.getElementById('sv-amt');if(e)e.value='';}}
function rSvcs(){
  const tot=S.services.reduce((a,s)=>a+s.amount,0),bt={};S.services.forEach(s=>{bt[s.type]=(bt[s.type]||0)+s.amount;});
  ss('sv-tot',FR(tot));ss('sv-law',FR(bt.laundry||0));ss('sv-food',FR(bt.food||0));ss('sv-oth',FR(Object.entries(bt).filter(([k])=>!['laundry','food'].includes(k)).reduce((a,[,v])=>a+v,0)));
  const maxV=Math.max(...Object.values(bt),1);
  document.getElementById('sv-break').innerHTML=Object.entries(bt).sort((a,b)=>b[1]-a[1]).map(([t,v])=>`<div class="brow"><div class="brow-l">${SVC_L[t]||t}</div><div class="brow-t"><div class="brow-f" style="width:${Math.round(v/maxV*100)}%;background:${SVC_C[t]||'#888'}"></div></div><div class="brow-v" style="color:${SVC_C[t]};font-weight:700">${FR(v)}</div></div>`).join('')||'<div style="font-size:11px;color:var(--muted)">لا توجد خدمات</div>';
}

// ── POS ──────────────────────────────────────────────────────
function toggleNewPOS(){const f=document.getElementById('new-pos-form');if(f)f.style.display=f.style.display==='none'?'block':'none';}
async function addPOSDevice(){const name=gv('nd-name').trim();if(!name){toast_('أدخل اسم الجهاز',false);return;}const r=await api('/api/pos/device/add',{name,dept:gv('nd-dept'),color:gv('nd-color'),serial:gv('nd-serial'),mk:gv('nd-mk')});if(r.ok){S.pos_devices.push(r.device);toggleNewPOS();rPOS();rDash();toast_(`تم إضافة "${name}" ✓`);['nd-name','nd-serial','nd-mk'].forEach(id=>{const e=document.getElementById(id);if(e)e.value='';});}}
async function deletePOSDevice(id){if(!confirm('حذف هذا الجهاز؟'))return;await api('/api/pos/device/delete',{id});S.pos_devices=S.pos_devices.filter(d=>d.id!==id);rPOS();rDash();toast_('تم حذف الجهاز');}
async function renamePOSDevice(id){const d=S.pos_devices.find(x=>x.id===id);if(!d)return;const n=prompt('الاسم الجديد:',d.name);if(!n||!n.trim())return;await api('/api/pos/device/rename',{id,name:n.trim()});d.name=n.trim();rPOS();toast_('تم تغيير الاسم ✓');}
function togglePOSEntry(id){const f=document.getElementById('pef-'+id);if(f)f.classList.toggle('open');}
function calcPOSSum(id){const t=POS_PAY.reduce((a,pm)=>{const el=document.getElementById(`pef-${pm}-${id}`);return a+(el?parseFloat(el.value||0):0);},0);const el=document.getElementById('pef-sum-'+id);if(el)el.textContent=FR(t);}
async function savePOSData(id){const sales=parseFloat(document.getElementById(`pef-sales-${id}`)?.value||0);if(sales<=0){toast_('أدخل إجمالي المبيعات',false);return;}const bd={};POS_PAY.forEach(pm=>{bd[pm]=parseFloat(document.getElementById(`pef-${pm}-${id}`)?.value||0);});const r=await api('/api/pos/data/save',{id,sales,refund:parseFloat(document.getElementById(`pef-refund-${id}`)?.value||0),vat:parseFloat(document.getElementById(`pef-vat-${id}`)?.value||0),txCount:parseInt(document.getElementById(`pef-count-${id}`)?.value||0),notes:document.getElementById(`pef-notes-${id}`)?.value||'',breakdown:bd});if(r.ok){const d=S.pos_devices.find(x=>x.id===id);if(d)d.data={sales,refund:parseFloat(document.getElementById(`pef-refund-${id}`)?.value||0),vat:0,txCount:parseInt(document.getElementById(`pef-count-${id}`)?.value||0),breakdown:bd,receivedAt:TNOW()};togglePOSEntry(id);rPOS();rDash();toast_('تم حفظ الموازنة ✓');}}
async function clearPOSData(id){await api('/api/pos/data/clear',{id});const d=S.pos_devices.find(x=>x.id===id);if(d)d.data=null;rPOS();rDash();toast_('تم مسح البيانات');}
function rPOS(){
  const recv=S.pos_devices.filter(d=>d.data).length,pend=S.pos_devices.length-recv,net=posNet();
  ss('pos-total-d',S.pos_devices.length);ss('pos-recv-c',recv);ss('pos-pend-c',pend);ss('pos-net-t',FR(net));
  document.getElementById('pos-devices-list').innerHTML=S.pos_devices.length?S.pos_devices.map(d=>{const ok=!!d.data,dNet=ok?d.data.sales-d.data.refund:0,icon=POS_ICONS[d.dept]||'💳';return`<div class="pdc ${ok?'ok':'wait'}"><div class="pdc-top"><div class="pdc-ic" style="background:${d.color}22;color:${d.color}">${icon}</div><div class="pdc-info"><div class="pdc-name">${d.name}</div><div class="pdc-sub" style="color:${ok?'var(--g)':'var(--a)'}">${ok?'مُستلم ✓':'في الانتظار'} · ${POS_DEPT[d.dept]||d.dept}${d.serial?` · ${d.serial}`:''}</div></div><div class="pdc-acts"><button class="btn sm" onclick="renamePOSDevice(${d.id})">✏️</button><button class="btn sm" style="color:var(--r)" onclick="deletePOSDevice(${d.id})">🗑️</button></div></div>${ok?`<div class="pdc-minis"><div class="pdcm"><div class="pm-l">المبيعات</div><div class="pm-v" style="color:var(--g)">${FR(d.data.sales)}</div></div><div class="pdcm"><div class="pm-l">الاسترداد</div><div class="pm-v" style="color:var(--r)">(${FR(d.data.refund)})</div></div><div class="pdcm"><div class="pm-l">الصافي</div><div class="pm-v" style="color:var(--p)">${FR(dNet)}</div></div><div class="pdcm"><div class="pm-l">نقداً</div><div class="pm-v">${FR(d.data.breakdown.cash)}</div></div><div class="pdcm"><div class="pm-l">مدى</div><div class="pm-v">${FR(d.data.breakdown.mada)}</div></div><div class="pdcm"><div class="pm-l">${d.data.txCount} معاملة</div><div class="pm-v" style="font-size:9px;color:var(--muted)">${d.data.receivedAt}</div></div></div><div style="margin-top:6px;display:flex;justify-content:flex-end"><button class="btn sm br2" onclick="clearPOSData(${d.id})">مسح</button></div>`:'<div style="font-size:11px;color:var(--muted);padding:3px 0">لم تُدخل موازنة اليوم</div>'}</div>`;}).join(''):'<div style="text-align:center;padding:16px;font-size:12px;color:var(--muted)">لا يوجد أجهزة</div>';
  document.getElementById('pos-entry-list').innerHTML=S.pos_devices.map(d=>`<div class="card" style="border-top:3px solid ${d.color};margin-bottom:8px"><div class="ch"><div class="ch-l"><div class="cico" style="background:${d.color}22;color:${d.color}">${POS_ICONS[d.dept]||'💳'}</div><div><div style="font-size:12px;font-weight:700">${d.name}</div><div style="font-size:10px;color:var(--muted)">${POS_DEPT[d.dept]||d.dept}</div></div></div><div style="display:flex;align-items:center;gap:6px">${d.data?pill('مُستلم ✓ — '+FR(d.data.sales-d.data.refund),'var(--gl)','var(--gd)'):pill('في الانتظار','var(--al)','var(--ad)')}<button class="btn sm" style="background:${d.color};color:#fff;border-color:${d.color}" onclick="togglePOSEntry(${d.id})">${d.data?'تعديل':'إدخال موازنة'}</button></div></div><div class="eform" id="pef-${d.id}"><div style="font-size:11px;color:var(--muted);margin-bottom:8px">بيانات موازنة ${d.name}</div><div class="pm-grid"><div class="fg"><label>إجمالي المبيعات (ر.س)</label><input type="number" min="0" id="pef-sales-${d.id}" placeholder="0.00" value="${d.data?d.data.sales:''}" oninput="calcPOSSum(${d.id})"/></div><div class="fg"><label>الاسترداد (ر.س)</label><input type="number" min="0" id="pef-refund-${d.id}" placeholder="0.00" value="${d.data?d.data.refund:''}"/></div><div class="fg"><label>VAT (ر.س)</label><input type="number" min="0" id="pef-vat-${d.id}" placeholder="0.00"/></div></div><div style="font-size:10px;font-weight:700;color:var(--muted);margin:6px 0 4px">تفصيل طرق الدفع</div><div class="pm-grid">${POS_PAY.map(pm=>`<div class="fg"><label>${POS_PAY_L[pm]} (ر.س)</label><input type="number" min="0" id="pef-${pm}-${d.id}" placeholder="0.00" value="${d.data?d.data.breakdown[pm]||'':''}" oninput="calcPOSSum(${d.id})"/></div>`).join('')}</div><div style="display:flex;align-items:center;justify-content:space-between;padding:6px 9px;background:var(--bg);border-radius:8px;margin-bottom:7px"><span style="font-size:10px;color:var(--muted)">مجموع طرق الدفع</span><span id="pef-sum-${d.id}" style="font-size:13px;font-weight:700;color:var(--p)">0 ر.س</span></div><div class="g2"><div class="fg"><label>عدد المعاملات</label><input type="number" min="0" id="pef-count-${d.id}" placeholder="0" value="${d.data?d.data.txCount:''}"/></div><div class="fg"><label>ملاحظات</label><input id="pef-notes-${d.id}" placeholder="اختياري..." value="${d.data?d.data.notes:''}"/></div></div><div style="display:flex;gap:5px;margin-top:5px"><button class="btn bg2" onclick="savePOSData(${d.id})" style="flex:1">حفظ موازنة ${d.name}</button><button class="btn sm" onclick="togglePOSEntry(${d.id})">إغلاق</button></div></div></div>`).join('')||'<div style="text-align:center;padding:14px;font-size:11px;color:var(--muted)">أضف أجهزة من القسم أعلاه</div>';
  S.pos_devices.forEach(d=>calcPOSSum(d.id));
}

// ── JOURNAL ──────────────────────────────────────────────────
async function addJnl(){const amt=parseFloat(gv('j-amt')||0);if(amt<=0){toast_('أدخل المبلغ',false);return;}const r=await api('/api/journal/add',{drAcc:gv('j-dr-a'),crAcc:gv('j-cr-a'),amount:amt,desc:gv('j-desc')||'قيد يومية',ref:gv('j-ref')});if(r.ok){S.journal_entries.push(r.entry);rJnl();toast_('تم تسجيل القيد ✓');['j-amt','j-desc','j-ref'].forEach(id=>{const e=document.getElementById(id);if(e)e.value='';});}}
function rJnl(){const tot=S.journal_entries.reduce((a,e)=>a+e.amount,0);ss('j-dr',FR(tot));ss('j-cr',FR(tot));ss('j-cnt',S.journal_entries.length);const jbc=document.getElementById('j-bal-c');if(jbc)jbc.className='mc mg';ss('j-bal','متوازن ✓');document.getElementById('j-body').innerHTML=[...S.journal_entries].reverse().map(e=>`<tr><td style="font-size:9px;color:var(--muted)">${e.time}</td><td>${e.desc}</td><td style="font-size:9px;color:var(--muted)">${e.ref||'—'}</td><td style="text-align:left"><span style="color:var(--g);font-weight:700">${FR(e.amount)}</span><div style="font-size:9px;color:var(--gd)">${ACC_L[e.drAcc]||e.drAcc}</div></td><td style="text-align:left"><span style="color:var(--p);font-weight:700">${FR(e.amount)}</span><div style="font-size:9px;color:var(--pd)">${ACC_L[e.crAcc]||e.crAcc}</div></td></tr>`).join('')||'<tr><td colspan="5" style="text-align:center;padding:14px;color:var(--muted)">لا توجد قيود</td></tr>';document.getElementById('j-foot').innerHTML=`<tr><td colspan="3" style="padding:6px 8px">الإجمالي</td><td style="text-align:left;color:var(--g)">${FR(tot)}</td><td style="text-align:left;color:var(--p)">${FR(tot)}</td></tr>`;}

// ── TRIAL ────────────────────────────────────────────────────
function rTrial(){const ACCS={cash:'النقدية',bank:'البنك',receivable:'ذمم مدينة',room_rev:'إيرادات الغرف',svc_rev:'إيرادات الخدمات',util_exp:'كهرباء',maint_exp:'صيانة',supply_exp:'لوازم',payable:'ذمم دائنة',vat_payable:'VAT مستحق'};const tots={};Object.keys(ACCS).forEach(k=>{tots[k]={dr:0,cr:0};});S.journal_entries.forEach(e=>{if(tots[e.drAcc])tots[e.drAcc].dr+=e.amount;if(tots[e.crAcc])tots[e.crAcc].cr+=e.amount;});const tDr=Object.values(tots).reduce((a,v)=>a+v.dr,0),tCr=Object.values(tots).reduce((a,v)=>a+v.cr,0);const bal=Math.round(tDr-tCr),ok=Math.abs(bal)<1;ss('tb-dr',FR(tDr));ss('tb-cr',FR(tCr));const tbc=document.getElementById('tb-bal-c');if(tbc)tbc.className='mc '+(ok?'mg':'mr');ss('tb-bal',ok?'متوازن ✓':FR(Math.abs(bal))+' فرق');document.getElementById('tb-body').innerHTML=Object.entries(ACCS).filter(([k])=>tots[k]&&(tots[k].dr>0||tots[k].cr>0)).map(([k,name])=>{const t=tots[k],b=t.dr-t.cr;return`<tr><td style="font-weight:700">${name}</td><td style="text-align:left;color:var(--g);font-weight:700">${t.dr>0?FR(t.dr):'—'}</td><td style="text-align:left;color:var(--p);font-weight:700">${t.cr>0?FR(t.cr):'—'}</td><td style="text-align:left"><span style="color:${b>0?'var(--g)':b<0?'var(--r)':'var(--n)'};font-weight:700">${FR(Math.abs(b))} ${b>0?'م':b<0?'د':''}</span></td></tr>`;}).join('');document.getElementById('tb-foot').innerHTML=`<tr><td style="padding:6px 8px">الإجمالي</td><td style="text-align:left;color:var(--g)">${FR(tDr)}</td><td style="text-align:left;color:var(--p)">${FR(tCr)}</td><td style="color:${ok?'var(--g)':'var(--r)'}">${ok?'متوازن ✓':FR(Math.abs(bal))}</td></tr>`;}

// ── P&L ──────────────────────────────────────────────────────
function rPL(){const grev=S.guests.reduce((a,g)=>a+g.total,0),srv=S.services.reduce((a,s)=>a+s.amount,0),tRev=grev+srv;const tExp=S.invoices.reduce((a,i)=>a+i.base,0),gross=tRev-tExp,net=gross,margin=tRev?Math.round(net/tRev*100):0;ss('pl-rev',FR(tRev));ss('pl-cost',FR(tExp));const pg=document.getElementById('pl-gross');if(pg){pg.textContent=FR(gross);pg.style.color=gross>=0?'var(--p)':'var(--r)';}const pn=document.getElementById('pl-net');if(pn){pn.textContent=FR(net);pn.style.color=net>=0?'var(--u)':'var(--r)';}document.getElementById('pl-det').innerHTML=`<div style="font-size:11px;font-weight:700;color:var(--gd);margin-bottom:5px;padding-bottom:4px;border-bottom:2px solid var(--g)">الإيرادات</div><div class="dr"><span style="color:var(--muted)">إيرادات الغرف (${S.guests.length} نزيل)</span><span style="color:var(--g);font-weight:700">${FR(grev)}</span></div><div class="dr"><span style="color:var(--muted)">إيرادات الخدمات (${S.services.length} خدمة)</span><span style="color:var(--g);font-weight:700">${FR(srv)}</span></div><div class="dr tot"><span>إجمالي الإيرادات</span><span style="color:var(--g)">${FR(tRev)}</span></div><div style="font-size:11px;font-weight:700;color:var(--rd);margin:9px 0 5px;padding-bottom:4px;border-bottom:2px solid var(--r)">التكاليف</div>${S.invoices.map(i=>`<div class="dr"><span style="color:var(--muted)">${i.supName} — ${i.num}</span><span style="color:var(--r)">(${FR(i.base)})</span></div>`).join('')||'<div class="dr"><span style="color:var(--muted)">لا توجد فواتير</span><span style="color:var(--g)">✓</span></div>'}<div class="dr tot"><span>إجمالي التكاليف</span><span style="color:var(--r)">(${FR(tExp)})</span></div><div class="dr" style="border-top:2px solid var(--pl);margin-top:8px;padding-top:9px"><span style="font-size:14px;font-weight:700">الصافي النهائي</span><span style="font-size:18px;font-weight:700;color:${net>=0?'var(--u)':'var(--r)'}">${FR(net)}</span></div><div class="dr"><span style="color:var(--muted)">هامش الربح</span><span style="font-weight:700;color:${margin>=0?'var(--u)':'var(--r)'}">${margin}%</span></div>`;}

// ── RECEIVABLES ──────────────────────────────────────────────
async function addRecv(){const name=gv('rec-n').trim();if(!name){toast_('أدخل الاسم',false);return;}const amt=parseFloat(gv('rec-a')||0);if(amt<=0){toast_('أدخل المبلغ',false);return;}const r=await api('/api/receivables/add',{name,ref:gv('rec-r'),type:gv('rec-t'),amount:amt,due:gv('rec-d')});if(r.ok){S.receivables.push(r.receivable);rRecv();toast_('تم تسجيل الذمة ✓');['rec-n','rec-a','rec-r'].forEach(id=>{const e=document.getElementById(id);if(e)e.value='';});}}
async function collectRecv(id){const r=await api('/api/receivables/collect',{id});if(r.ok){const rec=S.receivables.find(x=>x.id===id);if(rec)rec.status='collected';await reload();rRecv();toast_('تم التحصيل + قيد محاسبي ✓');}}
function rRecv(){const tot=S.receivables.reduce((a,r)=>a+r.amount,0),ov=S.receivables.filter(r=>r.status==='overdue').reduce((a,r)=>a+r.amount,0);ss('rec-tot',FR(tot));ss('rec-pend',FR(S.receivables.filter(r=>r.status==='pending').reduce((a,r)=>a+r.amount,0)));ss('rec-over',FR(ov));ss('rec-col',FR(S.receivables.filter(r=>r.status==='collected').reduce((a,r)=>a+r.amount,0)));const TL={room:'إيجار',svc:'خدمات',corp:'شركة',other:'أخرى'};document.getElementById('rec-body').innerHTML=S.receivables.map(r=>`<tr><td style="font-weight:700">${r.name}</td><td style="font-size:9px">${r.ref||'—'}</td><td>${pill(TL[r.type]||r.type,'var(--pl)','var(--p)')}</td><td style="text-align:left;color:var(--p);font-weight:700">${FR(r.amount)}</td><td style="font-size:9px">${r.due}</td><td>${pill(r.status==='overdue'?'متأخرة':r.status==='collected'?'محصّلة':'معلقة',r.status==='overdue'?'var(--rl)':r.status==='collected'?'var(--gl)':'var(--al)',r.status==='overdue'?'var(--r)':r.status==='collected'?'var(--g)':'var(--a)')}</td><td>${r.status!=='collected'?`<button class="btn sm bg2" onclick="collectRecv(${r.id})">تحصيل</button>`:'✓'}</td></tr>`).join('');document.getElementById('rec-foot').innerHTML=`<tr><td colspan="3" style="padding:6px 8px">الإجمالي</td><td style="text-align:left;color:var(--p)">${FR(tot)}</td><td colspan="2"></td></tr>`;}

// ── PAYABLES ─────────────────────────────────────────────────
async function payInv(id){const r=await api('/api/invoices/pay',{id});if(r.ok){await reload();rPaybl();rInv();rJnl();toast_('تم الدفع + قيد محاسبي ✓');}}
function rPaybl(){const pend=S.invoices.filter(i=>i.status==='pending'),paid=S.invoices.filter(i=>i.status==='paid');ss('pay-tot',FR(pend.reduce((a,i)=>a+i.total,0)));ss('pay-pend',FR(pend.reduce((a,i)=>a+i.total,0)));ss('pay-late',FR(0));ss('pay-paid',FR(paid.reduce((a,i)=>a+i.total,0)));document.getElementById('pay-body').innerHTML=S.invoices.map(i=>`<tr><td style="font-weight:700">${i.supName}</td><td style="font-size:9px">${i.num}</td><td style="text-align:left;color:var(--r);font-weight:700">${FR(i.total)}</td><td style="font-size:9px">${i.due}</td><td>${pill(i.status==='paid'?'مدفوعة':'معلقة',i.status==='paid'?'var(--gl)':'var(--rl)',i.status==='paid'?'var(--g)':'var(--r)')}</td><td>${i.status==='pending'?`<button class="btn sm bg2" onclick="payInv(${i.id})">دفع</button>`:'✓'}</td></tr>`).join('');document.getElementById('pay-foot').innerHTML=`<tr><td colspan="2" style="padding:6px 8px">المعلقة</td><td style="text-align:left;color:var(--r)">${FR(pend.reduce((a,i)=>a+i.total,0))}</td><td colspan="2"></td></tr>`;}

// ── SUPPLIERS ────────────────────────────────────────────────
async function addSup(){const name=gv('sup-n').trim();if(!name){toast_('أدخل اسم المورّد',false);return;}const r=await api('/api/suppliers/add',{name,type:gv('sup-t'),phone:gv('sup-ph'),iban:gv('sup-ib'),cr:gv('sup-cr'),terms:gv('sup-tm')});if(r.ok){S.suppliers.push(r.supplier);rSup();refreshInvSel();toast_('تم إضافة المورّد ✓');['sup-n','sup-ph','sup-ib','sup-cr'].forEach(id=>{const e=document.getElementById(id);if(e)e.value='';});}}
function rSup(){const pendByS={};S.invoices.filter(i=>i.status==='pending').forEach(i=>{pendByS[i.supId]=(pendByS[i.supId]||0)+i.total;});const due=Object.values(pendByS).reduce((a,v)=>a+v,0);ss('sup-cnt',S.suppliers.length);ss('sup-due',FR(due));ss('sup-inv-cnt',S.invoices.length);ss('sup-paid',FR(S.invoices.filter(i=>i.status==='paid').reduce((a,i)=>a+i.total,0)));const TL={cash:'نقداً','30':'30 يوم','60':'60 يوم',monthly:'شهري'};document.getElementById('sup-list').innerHTML=S.suppliers.length?S.suppliers.map(s=>`<div class="sup-row"><div class="sup-av" style="background:${s.color}22;color:${s.color}">${s.name.charAt(0)}</div><div style="flex:1;min-width:0"><div style="font-size:12px;font-weight:700;color:var(--text)">${s.name}</div><div style="font-size:10px;color:var(--muted);margin-top:2px">${pill(SUP_L[s.type]||s.type,SUP_C[s.type]+'22',SUP_C[s.type]||'#888')} ${s.phone||''} ${TL[s.terms]||s.terms}</div>${s.iban?`<div style="font-size:9px;color:var(--muted)">IBAN: ${s.iban.substring(0,14)}...</div>`:''}</div><div style="text-align:left;flex-shrink:0"><div style="font-size:13px;font-weight:700;color:${(pendByS[s.id]||0)>0?'var(--r)':'var(--g)'}">${FR(pendByS[s.id]||0)}</div><div style="font-size:9px;color:var(--muted)">${(pendByS[s.id]||0)>0?'مستحق':'لا ديون'}</div></div></div>`).join(''):'<div style="text-align:center;padding:16px;font-size:12px;color:var(--muted)">لا يوجد موردون</div>';}
function refreshInvSel(){const sel=document.getElementById('inv-sup');if(sel)sel.innerHTML=S.suppliers.map(s=>`<option value="${s.id}">${s.name}</option>`).join('');}

// ── INVOICES ─────────────────────────────────────────────────
function calcInv(){const base=parseFloat(gv('inv-base')||0),vatOn=document.getElementById('inv-vat')?.checked,vat=vatOn?Math.round(base*0.15):0;const va=document.getElementById('inv-vat-a');if(va)va.textContent=FR(vat);const it=document.getElementById('inv-tot');if(it)it.textContent=FR(base+vat);}
async function addInv(){const base=parseFloat(gv('inv-base')||0);if(base<=0){toast_('أدخل المبلغ',false);return;}const supId=parseInt(gv('inv-sup')),sup=S.suppliers.find(s=>s.id===supId)||{name:'مورّد'};const vatOn=document.getElementById('inv-vat')?.checked;const r=await api('/api/invoices/add',{supId,supName:sup.name,num:gv('inv-num')||'INV-'+Date.now().toString().slice(-4),base,vat:vatOn,date:gv('inv-date'),due:gv('inv-due')});if(r.ok){S.invoices.push(r.invoice);await reload();rInv();rPaybl();rJnl();rDash();toast_('تم تسجيل الفاتورة + قيد محاسبي ✓');['inv-base','inv-num'].forEach(id=>{const e=document.getElementById(id);if(e)e.value='';});}}
function rInv(){const pend=S.invoices.filter(i=>i.status==='pending'),paid=S.invoices.filter(i=>i.status==='paid');ss('inv-pc',pend.length);ss('inv-pa',FR(pend.reduce((a,i)=>a+i.total,0)));ss('inv-dc',paid.length);ss('inv-da',FR(paid.reduce((a,i)=>a+i.total,0)));document.getElementById('inv-body').innerHTML=S.invoices.map(i=>`<tr><td style="font-weight:700">${i.supName}</td><td style="font-size:9px">${i.num}</td><td style="text-align:left">${F(i.base)}</td><td style="text-align:left;color:var(--a)">${i.vat>0?FR(i.vat):'—'}</td><td style="text-align:left;color:var(--r);font-weight:700">${FR(i.total)}</td><td style="font-size:9px">${i.due}</td><td>${pill(i.status==='paid'?'مدفوعة':'معلقة',i.status==='paid'?'var(--gl)':'var(--rl)',i.status==='paid'?'var(--g)':'var(--r)')}</td><td>${i.status==='pending'?`<button class="btn sm bg2" onclick="payInv(${i.id})">دفع</button>`:'✓'}</td></tr>`).join('');document.getElementById('inv-foot').innerHTML=`<tr><td colspan="4" style="padding:6px 8px">الإجمالي</td><td style="text-align:left;color:var(--r)">${FR(S.invoices.reduce((a,i)=>a+i.total,0))}</td><td colspan="2"></td></tr>`;}

// ── BUDGET HIERARCHICAL ──────────────────────────────────────
function rBudget(){
  const lines=S.budget_lines||[];const roots=lines.filter(b=>!b.parent_id);
  const getChildren=(pid)=>lines.filter(b=>String(b.parent_id)===String(pid));
  const tRevPlan=roots.filter(b=>b.type==='rev').reduce((a,b)=>a+b.planned,0);
  const tExpPlan=roots.filter(b=>b.type==='exp').reduce((a,b)=>a+b.planned,0);
  const planNet=tRevPlan-tExpPlan,actNet=sysIn()-sysOut(),diff=actNet-planNet,pct=planNet?Math.round(actNet/planNet*100):0;
  const el_rp=document.getElementById('bgt-rev-plan');if(el_rp)el_rp.textContent=FR(tRevPlan);
  const el_ep=document.getElementById('bgt-exp-plan');if(el_ep)el_ep.textContent=FR(tExpPlan);
  const de=document.getElementById('bgt-diff');if(de){de.textContent=(diff>=0?'+':'')+FR(diff);de.style.color=diff>=0?'var(--g)':'var(--r)';}
  const dc=document.getElementById('bgt-diff-c');if(dc)dc.className='mc '+(diff>=0?'mg':'mr');
  const pe=document.getElementById('bgt-pct');if(pe)pe.textContent=pct+'%';
  function renderNode(b,depth){
    depth=depth||0;const kids=getChildren(b.id);const hasKids=kids.length>0;
    const indent=depth*16;const isRoot=depth===0;
    const totPlanned=b.planned+(hasKids?kids.reduce((a,k)=>a+k.planned,0):0);
    const totActual=b.actual+(hasKids?kids.reduce((a,k)=>a+k.actual,0):0);
    const pctA=totPlanned?Math.round(totActual/totPlanned*100):0;
    const over=b.type==='exp'?(totActual>totPlanned):(totActual<totPlanned);
    const bgMain=isRoot?(b.type==='rev'?'#F0FDF4':'#FEF2F2'):'var(--bg)';
    const borderC=isRoot?(b.type==='rev'?'#6EE7B7':'#FCA5A5'):'var(--border)';
    const barColor=over?'#DC2626':b.type==='rev'?'#047857':'#D97706';
    return`<div style="margin-bottom:5px"><div style="display:flex;align-items:center;gap:6px;padding:8px 10px;background:${bgMain};border-radius:9px;border:1.5px solid ${borderC};margin-right:${indent}px;flex-wrap:wrap"><span style="font-size:10px;color:var(--muted);cursor:pointer;user-select:none;min-width:14px;font-weight:700" onclick="toggleBgtNode(${b.id})">${hasKids?'▶':' '}</span><span style="font-size:9px;padding:3px 8px;border-radius:20px;font-weight:700;flex-shrink:0;background:${b.type==='rev'?'var(--gl)':'var(--rl)'};color:${b.type==='rev'?'var(--g)':'var(--r)'}">${b.type==='rev'?'إيراد':'مصروف'}</span><input value="${b.name}" style="flex:1;min-width:90px;border:1.5px solid var(--border);border-radius:7px;padding:4px 7px;font-size:${isRoot?'12':'11'}px;font-weight:${isRoot?'700':'500'};background:${bgMain};color:var(--text)" onchange="renameBgt(${b.id},this.value)"/><span style="font-size:10px;color:var(--muted)">مخطط</span><input type="number" value="${b.planned}" min="0" style="width:82px;border:1.5px solid var(--border);border-radius:7px;padding:4px 7px;font-size:11px;background:${bgMain};color:var(--text)" onchange="updateBgt(${b.id},'planned',this.value)"/><span style="font-size:10px;color:var(--muted)">فعلي</span><input type="number" value="${b.actual}" min="0" style="width:82px;border:1.5px solid var(--border);border-radius:7px;padding:4px 7px;font-size:11px;background:${bgMain};color:var(--text)" onchange="updateBgt(${b.id},'actual',this.value)"/>${hasKids?`<span style="font-size:10px;font-weight:700;color:${b.type==='rev'?'var(--g)':'var(--r)'}">${F(totActual)}/${F(totPlanned)}</span>`:''}<div style="display:flex;gap:3px;flex-shrink:0"><button style="font-size:10px;padding:3px 8px;border:none;border-radius:7px;background:var(--pl);color:var(--p);cursor:pointer;font-weight:600" onclick="addBgtChild(${b.id},'${b.type}')">+ فرعي</button><button style="font-size:10px;padding:3px 8px;border:none;border-radius:7px;background:var(--rl);color:var(--r);cursor:pointer;font-weight:600" onclick="deleteBgt(${b.id})">حذف</button></div><div style="flex-basis:100%;display:flex;align-items:center;gap:6px;margin-top:4px"><div style="flex:1;background:var(--border);border-radius:4px;height:6px;overflow:hidden"><div style="height:6px;border-radius:4px;width:${Math.min(pctA,100)}%;background:${barColor};transition:width .5s"></div></div><span style="font-size:9px;color:${barColor};font-weight:700">${pctA}%</span></div></div><div id="bgt-kids-${b.id}">${kids.map(k=>renderNode(k,depth+1)).join('')}</div></div>`;
  }
  const tree=document.getElementById('bgt-tree');if(tree)tree.innerHTML=roots.length?roots.map(b=>renderNode(b)).join(''):'<div style="text-align:center;padding:16px;font-size:12px;color:var(--muted)">لا توجد بنود — اضغط + إيراد رئيسي أو + مصروف رئيسي</div>';
  const allLeaves=lines.filter(b=>!getChildren(b.id).length);const maxV=Math.max(...allLeaves.map(b=>Math.max(b.planned,b.actual||0)),1);
  const ch=document.getElementById('bgt-chart');if(ch)ch.innerHTML=allLeaves.map(b=>{const av=b.actual||0,pt2=b.planned?Math.round(av/b.planned*100):0,ov=b.type==='exp'?(av>b.planned):(av<b.planned);return`<div class="brow"><div class="brow-l">${b.name}</div><div class="brow-t"><div class="brow-f" style="width:${Math.round(Math.min(av,b.planned*1.4)/Math.max(b.planned*1.4,1)*100)}%;background:${ov?'var(--r)':b.type==='rev'?'var(--g)':'var(--a)'}"></div></div><div class="brow-v"><span style="color:${ov?'var(--r)':'var(--g)'};font-weight:700">${F(av)}</span><span style="color:var(--muted);font-size:9px"> / ${F(b.planned)} (${pt2}%)</span></div></div>`;}).join('');
}
function toggleBgtNode(id){const el=document.getElementById('bgt-kids-'+id);if(el)el.style.display=el.style.display==='none'?'block':'none';}
function renameBgt(id,name){const b=S.budget_lines.find(x=>x.id===id);if(b){b.name=name;bgtSave(false);}}
function updateBgt(id,field,val){const b=S.budget_lines.find(x=>x.id===id);if(b){b[field]=parseFloat(val||0);bgtSave();}}
function deleteBgt(id){const removeWithChildren=(pid)=>{S.budget_lines=S.budget_lines.filter(b=>b.id!==pid);S.budget_lines.filter(b=>String(b.parent_id)===String(pid)).forEach(k=>removeWithChildren(k.id));};removeWithChildren(id);bgtSave();}
function addBgtMain(type){S.budget_lines.push({id:Date.now(),name:type==='rev'?'إيراد جديد':'مصروف جديد',type,planned:0,actual:0,parent_id:null,level:0});bgtSave();}
function addBgtChild(parentId,type){const parent=S.budget_lines.find(b=>b.id===parentId);S.budget_lines.push({id:Date.now(),name:'بند فرعي',type,planned:0,actual:0,parent_id:parentId,level:(parent&&parent.level?parent.level:0)+1});bgtSave();setTimeout(()=>{const el=document.getElementById('bgt-kids-'+parentId);if(el)el.style.display='block';},150);}
async function bgtSave(rerender){if(rerender===undefined)rerender=true;await api('/api/budget/save',{lines:S.budget_lines});if(rerender)rBudget();}
function resetBgt(){S.budget_lines=[{id:1,name:'إجمالي الإيرادات',type:'rev',planned:90000,actual:0,parent_id:null,level:0},{id:11,name:'إيرادات الغرف',type:'rev',planned:75000,actual:0,parent_id:1,level:1},{id:12,name:'إيرادات الخدمات',type:'rev',planned:15000,actual:0,parent_id:1,level:1},{id:2,name:'إجمالي المصاريف',type:'exp',planned:30000,actual:0,parent_id:null,level:0},{id:21,name:'مصاريف التشغيل',type:'exp',planned:20000,actual:0,parent_id:2,level:1},{id:22,name:'مصاريف المغسلة',type:'exp',planned:5000,actual:0,parent_id:2,level:1},{id:23,name:'سكن الموظفين',type:'exp',planned:3600,actual:0,parent_id:2,level:1}];bgtSave();}

// ── CASHFLOW ─────────────────────────────────────────────────
function rCashflow(){const si=sysIn(),so=sysOut(),net=si-so;ss('cf-in',FR(si));ss('cf-out',FR(so));ss('cf-end',FR(Math.round(si*1.8)));const cfn=document.getElementById('cf-net');if(cfn){cfn.textContent=FR(net);cfn.style.color=net>=0?'var(--p)':'var(--r)';}document.getElementById('cf-det').innerHTML=`<div style="font-size:11px;font-weight:700;color:var(--gd);margin-bottom:5px;padding-bottom:4px;border-bottom:2px solid var(--g)">التدفق الداخل</div><div class="dr"><span style="color:var(--muted)">إيرادات الغرف</span><span style="color:var(--g);font-weight:700">${FR(S.guests.reduce((a,g)=>a+g.total,0))}</span></div><div class="dr"><span style="color:var(--muted)">إيرادات الخدمات</span><span style="color:var(--g);font-weight:700">${FR(S.services.reduce((a,s)=>a+s.amount,0))}</span></div><div class="dr tot"><span>إجمالي الداخل</span><span style="color:var(--g)">${FR(si)}</span></div><div style="font-size:11px;font-weight:700;color:var(--rd);margin:8px 0 5px;padding-bottom:4px;border-bottom:2px solid var(--r)">التدفق الخارج</div>${S.invoices.map(i=>`<div class="dr"><span style="color:var(--muted)">${i.supName} — ${i.num}</span><span style="color:var(--r)">(${FR(i.total)})</span></div>`).join('')||'<div class="dr"><span style="color:var(--muted)">لا توجد مدفوعات</span><span style="color:var(--g)">✓</span></div>'}<div class="dr tot"><span>إجمالي الخارج</span><span style="color:var(--r)">(${FR(so)})</span></div><div class="dr" style="border-top:2px solid var(--pl);margin-top:8px;padding-top:9px"><span style="font-size:14px;font-weight:700">صافي التدفق</span><span style="font-size:17px;font-weight:700;color:${net>=0?'var(--g)':'var(--r)'}">${FR(net)}</span></div>`;document.getElementById('cf-weeks').innerHTML=['الأسبوع القادم','بعد أسبوعين','بعد 3 أسابيع','نهاية الشهر'].map((w,i)=>{const p=Math.round(net*(1+i*0.1));return`<div class="brow"><div class="brow-l">${w}</div><div class="brow-t"><div class="brow-f" style="width:${Math.min(100,Math.round(Math.abs(p)/Math.max(si,1)*100))}%;background:${p>=0?'var(--g)':'var(--r)'}"></div></div><div class="brow-v" style="color:${p>=0?'var(--g)':'var(--r)'};font-weight:700">${p>=0?'+':''}${FR(p)}</div></div>`;}).join('');}

// ── MATCH ─────────────────────────────────────────────────────
function rMatchPage(){}
async function runMatch(){
  const pNet=posNet(),si=sysIn(),sysManual=parseFloat(document.getElementById('m-sys-in')?.value||0),sysTotal=sysManual>0?sysManual:si;
  const rawDiff=pNet-sysTotal,absDiff=Math.abs(rawDiff),pct=sysTotal>0?absDiff/sysTotal*100:0;
  const status=absDiff<1?'MATCHED':pct<=2?'PARTIAL':'DIFF';const sign=rawDiff>0?'+':rawDiff<0?'-':'';
  const stC={MATCHED:'var(--g)',PARTIAL:'var(--a)',DIFF:rawDiff>0?'var(--g)':'var(--r)'}[status];
  const stL={MATCHED:'مطابقة تامة ✓',PARTIAL:`مطابقة جزئية ${sign}${FR(absDiff)} ⚠`,DIFF:rawDiff>0?`+ يزيد ${FR(absDiff)} ↑`:`- ينقص ${FR(absDiff)} ↓`}[status];
  matchResult={status,rawDiff,absDiff,stC,stL,sign,pNet,sysTotal};
  ss('m-pos',FR(pNet));ss('m-sys',FR(sysTotal));
  const md=document.getElementById('m-diff');if(md){md.textContent=sign+FR(absDiff);md.style.color=stC;}
  const mr=document.getElementById('m-res');if(mr){mr.textContent=stL;mr.style.color=stC;}
  const fn=ok=>ok?'mc mg':'mc mr';['m-diff-c','m-res-c'].forEach(id=>{const el=document.getElementById(id);if(el)el.className=fn(rawDiff>=0||status==='MATCHED');});
  const devs=S.pos_devices.filter(d=>d.data);const maxV=Math.max(...devs.map(d=>d.data.sales-d.data.refund),1);
  document.getElementById('m-det').innerHTML=devs.length?`<div style="font-size:11px;font-weight:700;color:var(--muted);margin-bottom:6px">توزيع أجهزة POS</div>${devs.map(d=>{const n=d.data.sales-d.data.refund;return`<div class="brow"><div class="brow-l">${POS_ICONS[d.dept]||'💳'} ${d.name}</div><div class="brow-t"><div class="brow-f" style="width:${Math.round(n/maxV*100)}%;background:${d.color}"></div></div><div class="brow-v" style="color:${d.color};font-weight:700">${FR(n)}</div></div>`;}).join('')}<div class="dr tot" style="margin-top:8px"><span>إجمالي POS</span><span style="color:var(--g)">${FR(pNet)}</span></div><div class="dr"><span>الوارد الداخلي</span><span style="font-weight:700">${FR(sysTotal)}</span></div><div class="dr tot" style="border-color:${stC}"><span>الفرق</span><span style="color:${stC};font-size:15px">${sign+FR(absDiff)}</span></div><div class="ab" style="margin-top:8px;background:${stC}18;border:1.5px solid ${stC}"><div style="font-weight:700;color:${stC}">${stL}</div></div>`:'<div style="font-size:11px;color:var(--muted);padding:8px">أدخل بيانات أجهزة POS أولاً</div>';
  const str=[],wk=[];if(status==='MATCHED')str.push({t:'مطابقة تامة',d:'الأجهزة والنظام متطابقان'});if(rawDiff>0&&status==='DIFF')str.push({t:`الأجهزة تزيد ${FR(absDiff)} ↑`,d:'تحقق من إيرادات غير مسجّلة'});const pRecv=S.pos_devices.filter(d=>d.data).length;if(pRecv===S.pos_devices.length&&S.pos_devices.length>0)str.push({t:'جميع الأجهزة مُستلمة ✓',d:`${S.pos_devices.length} أجهزة`});const net2=si-sysOut(),m2=si>0?Math.round(net2/si*100):0;if(net2>0)str.push({t:`صافي إيجابي ${FR(net2)}`,d:`هامش ${m2}%`});const notRecv=S.pos_devices.filter(d=>!d.data);if(notRecv.length)wk.push({t:`${notRecv.length} أجهزة لم تُستلم`,d:notRecv.map(d=>d.name).join(' · ')});if(rawDiff<0&&status==='DIFF')wk.push({t:`الأجهزة تنقص ${FR(absDiff)} ↓`,d:'تحقق من معاملات مفقودة'});if(m2<10&&si>0)wk.push({t:`هامش ربح منخفض ${m2}%`,d:'راجع المصاريف'});
  document.getElementById('m-str').innerHTML=str.map(s=>`<div class="ab ab-g" style="margin-bottom:5px"><div class="ab-t">${s.t}</div><div style="font-size:10px;margin-top:1px">${s.d}</div></div>`).join('')||'<div style="font-size:11px;color:var(--muted)">أدخل بيانات للتحليل</div>';
  document.getElementById('m-wk').innerHTML=wk.map(w=>`<div class="ab ab-r" style="margin-bottom:5px"><div class="ab-t">${w.t}</div><div style="font-size:10px;margin-top:1px">${w.d}</div></div>`).join('')||'<div class="ab ab-g"><div class="ab-t">لا توجد نقاط ضعف ✓</div></div>';
  buildReport();toast_('اكتملت المطابقة ✓');
}

// ── SUBSCRIPTIONS ─────────────────────────────────────────────
function rSubscriptions(){
  const planNames={free:'مجانية',pro:'احترافية',enterprise:'مؤسسية'};
  const planAmts={free:0,pro:299,enterprise:799};
  ss('sub-plan-name',planNames[subState.plan]||'مجانية');
  ss('sub-exp',subState.expires||'غير محدود');
  ss('sub-next-amt',planAmts[subState.plan]+' ر.س / شهر');
  ss('sub-next-date',subState.nextDate||'—');
  ss('sb-plan-foot',planNames[subState.plan]||'مجانية');
  ['free','pro','enterprise'].forEach(p=>{
    const btn=document.getElementById('btn-plan-'+p);
    if(btn){btn.textContent=subState.plan===p?'الخطة الحالية ✓':'اختيار هذه الخطة';btn.className='btn '+(subState.plan===p?'bg2':'bp')+' sm';btn.style.width='100%';btn.style.marginTop='12px';}
    const card=document.getElementById('plan-'+p);
    if(card)card.style.borderColor=subState.plan===p?'var(--g)':p==='pro'?'var(--p)':'var(--border)';
  });
  const autoEl=document.getElementById('sub-auto');if(autoEl)autoEl.checked=subState.auto;
}
function selectPlan(plan){
  if(plan===subState.plan){toast_('أنت على هذه الخطة بالفعل');return;}
  if(plan==='enterprise'){toast_('تواصل معنا على: info@hotel-system.sa');return;}
  const planAmts={free:'مجاني',pro:'299 ر.س / شهر',enterprise:'799 ر.س / شهر'};
  if(!confirm(`هل تريد الترقية إلى خطة ${plan==='pro'?'احترافية':'مؤسسية'} — ${planAmts[plan]}؟`))return;
  toast_('تم اختيار الخطة — أدخل كود التفعيل أو بيانات البطاقة');
}
function activateSub(){
  const code=gv('sub-code').trim().toUpperCase();
  const plan=gv('sub-plan-sel');
  if(!code){toast_('أدخل كود التفعيل',false);return;}
  if(!code.startsWith('HOTEL-')){toast_('كود التفعيل غير صحيح — يجب أن يبدأ بـ HOTEL-',false);return;}
  subState.plan=plan;
  const exp=new Date();exp.setFullYear(exp.getFullYear()+1);
  subState.expires=exp.toLocaleDateString('ar-SA');
  subState.nextDate=new Date(exp.getTime()-86400000*30).toLocaleDateString('ar-SA');
  rSubscriptions();
  toast_(`تم تفعيل خطة ${plan==='pro'?'الاحترافية':plan==='enterprise'?'المؤسسية':'المجانية'} حتى ${subState.expires} ✓`);
}
function toggleAutoSub(){subState.auto=document.getElementById('sub-auto').checked;}
function saveAutoSub(){
  const card=gv('sub-card').trim();
  if(!card||card.length<15){toast_('أدخل رقم البطاقة بشكل صحيح',false);return;}
  subState.auto=true;
  const autoEl=document.getElementById('sub-auto');if(autoEl)autoEl.checked=true;
  toast_('تم حفظ بيانات الفوترة التلقائية ✓ — سيتم الخصم تلقائياً عند التجديد');
}

// ── REPORT ────────────────────────────────────────────────────
function buildReport(){
  const si=sysIn(),so=sysOut(),net=si-so,pNet=posNet();
  const iban=S.settings.owner_iban||'';
  const bank=S.settings.owner_bank||'';
  const accName=S.settings.owner_account_name||'';
  const ibanBlock=iban?`
    <div style="margin-top:10px;padding:10px 12px;background:linear-gradient(135deg,#ECFDF5,#D1FAE5);border-radius:10px;border:1px solid #6EE7B7">
      <div style="font-size:10px;font-weight:700;color:var(--gd);margin-bottom:4px">🏦 معلومات التحويل البنكي</div>
      <div style="font-size:11px;color:var(--text)">اسم الحساب: <b>${accName}</b></div>
      <div style="font-size:11px;color:var(--text)">البنك: <b>${bank}</b></div>
      <div style="font-family:monospace;font-size:12px;font-weight:700;color:var(--g);margin-top:3px">IBAN: ${iban}</div>
    </div>`:'';
  document.getElementById('rep-card').innerHTML=`
    <div style="display:flex;justify-content:space-between;align-items:flex-start;flex-wrap:wrap;gap:7px;margin-bottom:10px">
      <div>
        <div style="font-size:16px;font-weight:700;color:var(--text)">${S.settings.name||'الفندق'}</div>
        <div style="font-size:11px;color:var(--muted);margin-top:2px">${NOW.toLocaleDateString('ar-SA',{weekday:'long',year:'numeric',month:'long',day:'numeric'})}</div>
        <div style="font-size:10px;color:var(--muted)">يُرسل إلى: ${(S.settings.recipients||[]).map(r=>r.name).join(' | ')||'—'}</div>
      </div>
      <div style="display:flex;gap:6px;flex-wrap:wrap;align-items:center">
        ${matchResult?`<span style="font-size:10px;padding:4px 11px;border-radius:20px;font-weight:700;background:${matchResult.stC}18;color:${matchResult.stC}">${matchResult.stL}</span>`:''}
        <button class="btn bp sm" onclick="downloadReport()" data-tt="تنزيل التقرير كملف HTML على جهازك">⬇️ تنزيل</button>
      </div>
    </div>
    <div style="border-top:2px solid var(--p);padding-top:10px">
    <div class="kg3" style="margin-bottom:10px">
      <div class="mc mg"><div class="ml">إجمالي الإيرادات</div><div class="mv">${FR(si)}</div></div>
      <div class="mc mr"><div class="ml">إجمالي المصاريف</div><div class="mv">${FR(so)}</div></div>
      <div class="mc ${net>=0?'mb':'mr'}"><div class="ml">الصافي</div><div class="mv" style="color:${net>=0?'var(--p)':'var(--r)'}">${FR(net)}</div></div>
    </div>
    <div class="dr"><span style="color:var(--muted)">النزلاء اليوم</span><span style="font-weight:700">${S.guests.length} نزيل (${S.guests.filter(g=>g.status==='active').length} مقيم)</span></div>
    <div class="dr"><span style="color:var(--muted)">إيرادات الخدمات</span><span style="color:var(--u);font-weight:700">${FR(S.services.reduce((a,s)=>a+s.amount,0))}</span></div>
    <div class="dr"><span style="color:var(--muted)">أجهزة POS المُستلمة</span><span style="font-weight:700">${S.pos_devices.filter(d=>d.data).length}/${S.pos_devices.length} — ${FR(pNet)}</span></div>
    <div class="dr"><span style="color:var(--muted)">فواتير موردين معلقة</span><span style="color:var(--r);font-weight:700">${S.invoices.filter(i=>i.status==='pending').length} فاتورة — ${FR(S.invoices.filter(i=>i.status==='pending').reduce((a,i)=>a+i.total,0))}</span></div>
    ${marketData&&marketData.our_adr?`<div class="dr"><span style="color:var(--muted)">ADR مقارنة بالسوق</span><span style="color:${marketData.adr_diff>=0?'var(--g)':'var(--r)'};font-weight:700">${FR(marketData.our_adr)} (السوق: ${FR(marketData.market_adr)})</span></div>`:''}
    <div class="dr tot" style="margin-top:8px"><span style="font-size:13px">الصافي النهائي</span><span style="font-size:17px;color:${net>=0?'var(--g)':'var(--r)'}">${FR(net)}</span></div>
    ${ibanBlock}
    <div style="margin-top:8px;padding:7px 9px;background:var(--bg);border-radius:8px;font-size:10px;color:var(--muted);text-align:center">تقرير تلقائي — نظام إدارة الفندق v3.0 | ${TNOW()}</div>
    </div>`;
}
function downloadReport(){
  const el=document.getElementById('rep-card');if(!el)return;
  const html=`<!DOCTYPE html><html dir="rtl" lang="ar"><head><meta charset="UTF-8"><style>body{font-family:system-ui,Arial;direction:rtl;padding:20px;background:#fff;color:#0F172A;max-width:700px;margin:0 auto}.dr{display:flex;justify-content:space-between;padding:6px 0;border-bottom:1px solid #E2E8F0;font-size:12px}.mc{border-radius:8px;padding:10px;margin:4px}.mg{background:#ECFDF5;color:#047857}.mr{background:#FEF2F2;color:#DC2626}.mb{background:#EEF2FF;color:#1A56DB}.kg3{display:grid;grid-template-columns:repeat(3,1fr);gap:8px;margin-bottom:10px}</style></head><body>${el.innerHTML}</body></html>`;
  const blob=new Blob([html],{type:'text/html;charset=utf-8'});
  const a=document.createElement('a');a.href=URL.createObjectURL(blob);
  a.download=`report_${new Date().toISOString().slice(0,10)}.html`;
  document.body.appendChild(a);a.click();document.body.removeChild(a);
  toast_('تم تنزيل التقرير ✓');
}
function rReport(){if(matchResult)buildReport();}

// ── BACKUP ───────────────────────────────────────────────────
async function rBackup(){
  const r=await api('/api/backups');const bks=r.backups||[];
  ss('bk-cnt',bks.length);ss('bk-last',bks.length?bks[0].date:'لا توجد');
  const el=document.getElementById('bk-list');if(!el)return;
  el.innerHTML=bks.length?bks.map(b=>`<div class="bk-item"><div><div class="bk-name">📦 ${b.name}</div><div class="bk-meta">${b.date} — ${b.size_kb} KB</div></div><button class="btn sm" style="color:var(--r)" onclick="restoreBackup('${b.name}')">استعادة</button></div>`).join(''):'<div style="text-align:center;padding:16px;font-size:11px;color:var(--muted)">لا توجد نسخ احتياطية — أنشئ أول نسخة</div>';
}
async function createBackup(){const r=await api('/api/backup/create',{label:gv('bk-label')});if(r.ok){ss('bk-last',r.date);await rBackup();toast_('تم إنشاء النسخة الاحتياطية ✓');}else toast_('فشل إنشاء النسخة',false);}
async function restoreBackup(name){if(!confirm(`هل أنت متأكد من استعادة: ${name}؟\nستُفقد البيانات الحالية (سيتم حفظ نسخة تلقائية أولاً)`))return;const r=await api('/api/backup/restore',{name});if(r.ok){await reload();rDash();toast_('تمت الاستعادة ✓ — البيانات محدّثة');}else toast_(r.error||'فشل الاستعادة',false);}
function downloadBackupNow(){
  const data=JSON.stringify(S,null,2);
  const blob=new Blob([data],{type:'application/json'});
  const url=URL.createObjectURL(blob);
  const a=document.createElement('a');
  a.href=url;
  a.download=`hotel_backup_${new Date().toISOString().slice(0,10)}.json`;
  document.body.appendChild(a);a.click();document.body.removeChild(a);
  URL.revokeObjectURL(url);
  toast_('تم تنزيل النسخة الاحتياطية على جهازك ✓');
}

// ── SETTINGS ──────────────────────────────────────────────────
// ── UNIT TYPE SELECTOR ───────────────────────────────────────
function renderUnitTypeGrid(){
  const units = S.settings.unit_types || [];
  const typ   = S.settings.type || 'hotel';
  const grid  = document.getElementById('unit-type-grid');
  if(!grid) return;
  // Show all or filter by type
  const filtered = units.filter(u => !u.type || u.type === typ || typ === 'service');
  if(!filtered.length){grid.innerHTML='';return;}
  grid.innerHTML = filtered.map(u => `
    <div onclick="selectUnitType('${u.id}',${u.default_price||0})"
      style="padding:8px 6px;border-radius:9px;border:1.5px solid var(--border);background:var(--bg);cursor:pointer;text-align:center;transition:all .1s"
      onmouseover="this.style.borderColor='var(--g)';this.style.background='var(--gl)'"
      onmouseout="this.style.borderColor='var(--border)';this.style.background='var(--bg)'"
      id="ut-${u.id}">
      <div style="font-size:18px;margin-bottom:3px">${u.icon||'🏠'}</div>
      <div style="font-size:9px;font-weight:700;color:var(--text)">${u.label}</div>
      <div style="font-size:9px;color:var(--g);font-weight:600;margin-top:1px">${F(u.default_price||0)} ر.س</div>
    </div>`).join('');
}
function selectUnitType(id, price){
  // Highlight selected
  document.querySelectorAll('[id^="ut-"]').forEach(el=>{
    el.style.borderColor='var(--border)';el.style.background='var(--bg)';
  });
  const sel=document.getElementById('ut-'+id);
  if(sel){sel.style.borderColor='var(--g)';sel.style.background='var(--gl)';}
  // Fill price
  const pe=document.getElementById('gi-price');
  if(pe&&price){pe.value=price;calcGuestPrev();}
  const units=S.settings.unit_types||[];
  const u=units.find(x=>x.id===id);
  if(u){
    // Auto-select bed type if hotel room
    const bed=document.getElementById('gi-bed');
    if(bed){
      if(id==='suite'||id==='penthouse')bed.value='suite';
      else if(id==='studio'||id==='one_bed')bed.value='double';
      else if(id==='two_bed'||id==='three_bed')bed.value='king';
    }
  }
}

// ── DYNAMIC PAY METHODS ──────────────────────────────────────
function getEnabledPayMethods(){
  const methods=S.settings.custom_pay_methods||[];
  if(!methods.length){
    return[
      {id:'mada',label:'💳 مدى'},{id:'cash',label:'💵 نقداً'},
      {id:'visa',label:'💳 فيزا'},{id:'master',label:'💳 ماستركارد'},
      {id:'transfer',label:'🏦 تحويل'},{id:'stc',label:'📱 STC Pay'},
      {id:'apple',label:'🍎 Apple Pay'},{id:'credit',label:'📋 آجل'},
    ];
  }
  return methods.filter(m=>m.enabled).map(m=>({id:m.id,label:`${m.icon||'💳'} ${m.label}`}));
}
function buildPaySelect(selectId){
  const sel=document.getElementById(selectId);
  if(!sel)return;
  const methods=getEnabledPayMethods();
  sel.innerHTML=methods.map(m=>`<option value="${m.id}">${m.label}</option>`).join('');
}

// ── EMAIL BACKUP ─────────────────────────────────────────────
async function emailBackup(){
  const btn=event?.target;
  if(btn){btn.textContent='جارٍ الإرسال...';btn.disabled=true;}
  const r=await api('/api/backup/email',{});
  if(btn){btn.textContent='📧 إرسال بالإيميل';btn.disabled=false;}
  if(r.ok){
    if(r.mode==='emailed')toast_(`تم الإرسال لـ ${r.recipients} مستلمين ✓`);
    else if(r.mode==='download_only') toast_(r.message||'تم إنشاء النسخة — أضف SMTP للإرسال',false);
    else toast_('تم إنشاء النسخة ✓');
    rBackup();
  } else {
    toast_(r.error||'فشل الإرسال',false);
    toast_('💡 أضف إعدادات SMTP في أسفل الصفحة',true);
  }
}
function saveSMTP(){
  const user=gv('cfg-smtp-user').trim();
  const pass=gv('cfg-smtp-pass').trim();
  const host=gv('cfg-smtp-host').trim()||'smtp.gmail.com';
  const port=gv('cfg-smtp-port').trim()||'587';
  if(user&&pass){
    S.settings.smtp_user=user;S.settings.smtp_pass=pass;
    S.settings.smtp_host=host;S.settings.smtp_port=port;
    api('/api/settings/save',{smtp_user:user,smtp_pass:pass,smtp_host:host,smtp_port:port});
    const st=document.getElementById('smtp-status');
    if(st)st.textContent='✓ تم الحفظ — جاهز للإرسال';
  }
}

// ── WEB SEARCH + AI MARKET ───────────────────────────────────
async function runWebSearchMarket(){
  const btn=document.getElementById('ai-websearch-btn');
  if(btn){btn.textContent='⏳ جارٍ البحث...';btn.disabled=true;}
  const badge=document.getElementById('ai-source-badge');
  if(badge){badge.style.display='block';badge.innerHTML='<span style="font-size:10px;color:var(--muted)">🔍 يبحث في الإنترنت عن أسعار الفنادق...</span>';}
  const r=await api('/api/market/websearch',{city:S.settings.city||'riyadh',type:S.settings.type||'hotel'});
  if(btn){btn.textContent='🔍 بحث ويب + AI';btn.disabled=false;}
  if(r.ok&&r.result){
    const res=r.result;
    const src=res.source||'web';
    if(badge)badge.innerHTML=`<span style="font-size:10px;padding:3px 9px;border-radius:20px;background:${src.includes('web')?'var(--gl)':'var(--pl)'};color:${src.includes('web')?'var(--g)':'var(--p)'};font-weight:700">${src.includes('web')&&src.includes('claude')?'✅ بحث ويب + تحليل Claude':'📊 بيانات مدمجة'}</span>`;
    // Update local market data
    S.market_rates=S.market_rates||{};
    S.market_rates.rates=S.market_rates.rates||{};
    const c=S.settings.city||'riyadh';
    S.market_rates.rates[c]={hotel_avg:res.hotel_avg||0,apart_avg:res.apart_avg||0,hotel_occ:res.hotel_occ||0,apart_occ:res.apart_occ||0};
    await loadMarket();
    const el=document.getElementById('ai-insight');
    if(el){
      el.style.display='block';
      el.innerHTML=`<div class="ab-t">🔍 نتائج بحث السوق الحي</div>
      <div style="margin-top:4px;font-size:11px">${res.recommendation||''}</div>
      ${res.insight?`<div style="margin-top:4px;font-size:10px;color:var(--muted)">${res.insight}</div>`:''}
      <div style="margin-top:6px;display:flex;gap:12px;flex-wrap:wrap;font-size:10px">
        <span>🏨 فندق ADR: <b style="color:var(--p)">${F(res.hotel_avg||0)} ر.س</b></span>
        <span>🏢 شقق ADR: <b style="color:var(--u)">${F(res.apart_avg||0)} ر.س</b></span>
        <span>📊 إشغال: <b style="color:var(--g)">${res.hotel_occ||0}%</b></span>
        <span>🌙 موسم: <b>${res.season||'—'} ×${res.season_factor||1}</b></span>
        <span style="color:var(--muted)">المصدر: ${res.source||'—'}</span>
      </div>`;
    }
    toast_(`✅ تم تحديث أسعار السوق — ${res.hotel_avg||0} ر.س للفندق`);
  } else {
    if(badge)badge.innerHTML=`<span style="font-size:10px;color:var(--r)">${r.error||'خطأ في البحث'}</span>`;
    toast_('تعذّر البحث — تحقق من الاتصال بالإنترنت أو أضف مفتاح Claude API',false);
  }
}

// ── OVERRIDE rGuests TO BUILD PAY SELECT ─────────────────────
const _origRGuests = typeof rGuests === 'function' ? rGuests : null;
function rGuests(){
  const act=S.guests.filter(g=>g.status==='active'),rev=S.guests.reduce((a,g)=>a+g.total,0);
  ss('g-tot',S.guests.length);ss('g-act',act.length);ss('g-rev',FR(rev));ss('g-avg',S.guests.length?Math.round(S.guests.reduce((a,g)=>a+g.nights,0)/S.guests.length)+' ليالٍ':'—');
  document.getElementById('g-body').innerHTML=S.guests.map(g=>`<tr><td style="font-weight:700">${g.unit||'—'}</td><td><div style="font-weight:600">${g.name}</div><div style="font-size:9px;color:var(--muted)">${g.idNum}</div></td><td>${pill((BED_L[g.bed]||g.bed)+(g.extra?` +${g.extra}✦`:''),BED_C[g.bed]+'22',BED_C[g.bed])}</td><td style="font-size:9px">${g.inDate}</td><td style="text-align:center">${g.nights}</td><td style="color:var(--g);font-weight:700">${FR(g.total)}</td><td>${pill(PAY_L[g.pay]||g.pay,PAY_C[g.pay]+'22',PAY_C[g.pay])}</td><td>${pill(g.status==='active'?'مقيم':'غادر',g.status==='active'?'var(--gl)':'var(--nl)',g.status==='active'?'var(--g)':'var(--n)')}</td><td>${g.status==='active'?`<button class="btn sm" onclick="checkout(${g.id})">مغادرة</button>`:'—'}</td></tr>`).join('')||'<tr><td colspan="9" style="text-align:center;padding:14px;color:var(--muted)">لا يوجد نزلاء</td></tr>';
  document.getElementById('g-foot').innerHTML=`<tr><td colspan="5" style="padding:6px 8px">الإجمالي</td><td style="color:var(--g)">${FR(rev)}</td><td colspan="3"></td></tr>`;
  // Build dynamic pay select
  buildPaySelect('gi-pay');
  // Render unit type grid
  renderUnitTypeGrid();
}
document.addEventListener('mouseover', e => {
  const el = e.target.closest('[data-tt]');
  if(!el) return;
  const tt = document.getElementById('tt');
  if(!tt) return;
  tt.textContent = el.getAttribute('data-tt');
  tt.style.display = 'block';
  const rect = el.getBoundingClientRect();
  tt.style.top = (rect.bottom + 6) + 'px';
  tt.style.right = Math.max(10, window.innerWidth - rect.right) + 'px';
  tt.style.left = 'auto';
});
document.addEventListener('mouseout', e => {
  if(!e.target.closest('[data-tt]')){const tt=document.getElementById('tt');if(tt)tt.style.display='none';}
});
document.addEventListener('mousemove', e => {
  if(!e.target.closest('[data-tt]')){const tt=document.getElementById('tt');if(tt&&tt.style.display!=='none')tt.style.display='none';}
});

// ── SETTINGS FUNCTIONS ───────────────────────────────────────
async function saveCfg(){
  const s={
    name:gv('cfg-name')||S.settings.name,
    type:gv('cfg-type'),
    rooms:parseInt(gv('cfg-rooms')||50),
    city:gv('cfg-city'),
    mk:gv('cfg-mk'),
    ap:gv('cfg-ap'),
  };
  const r=await api('/api/settings/save',s);
  if(r.ok){
    Object.assign(S.settings,s);
    ss('sb-name',s.name);
    const tL={hotel:'HOTEL',apart:'APARTMENTS',service:'SERVICED APTS'};
    ss('sb-type',tL[s.type]||'HOTEL');
    await loadMarket();
    toast_('تم حفظ الإعدادات ✓');
  }
}
async function saveCfgFull(){
  await saveCfg();
  const key=gv('cfg-claude-key').trim();
  if(key){
    const s=S.settings;s.claude_key=key;
    await api('/api/settings/save',{claude_key:key});
    toast_('تم حفظ مفتاح Claude AI ✓');
  }
}
async function saveBankInfo(){
  const iban=gv('cfg-bank-iban').trim();
  const bank=gv('cfg-bank-bank').trim();
  const name=gv('cfg-bank-name').trim();
  if(!iban){toast_('أدخل رقم IBAN',false);return;}
  const r=await api('/api/bank/save',{iban,bank,account_name:name});
  if(r.ok){
    S.settings.owner_iban=iban;S.settings.owner_bank=bank;S.settings.owner_account_name=name;
    toast_('تم حفظ بيانات البنك ✓ — ستظهر في فواتيرك');
  }
}
async function savePrices(){
  const p={
    price_hotel_standard:parseFloat(gv('cfg-p-hotel-std')||0),
    price_hotel_suite:parseFloat(gv('cfg-p-hotel-suite')||0),
    price_apart_studio:parseFloat(gv('cfg-p-apart-studio')||0),
    price_apart_one:parseFloat(gv('cfg-p-apart-one')||0),
    price_apart_two:parseFloat(gv('cfg-p-apart-two')||0),
    price_apart_three:parseFloat(gv('cfg-p-apart-three')||0),
  };
  const r=await api('/api/prices/save',p);
  if(r.ok){Object.assign(S.settings,p);toast_('تم حفظ الأسعار ✓ — تُعبأ تلقائياً في نموذج النزيل');}
}
async function saveMktPrices(){
  const h=parseFloat(gv('cfg-mkt-hotel')||0);
  const a=parseFloat(gv('cfg-mkt-apart')||0);
  if(!h&&!a){toast_('أدخل سعراً واحداً على الأقل',false);return;}
  const city=gv('cfg-city')||S.settings.city||'riyadh';
  const r=await api('/api/market/update',{city,rates:{
    hotel_avg:h||S.market_rates?.rates?.[city]?.hotel_avg||0,
    apart_avg:a||S.market_rates?.rates?.[city]?.apart_avg||0,
    hotel_occ:S.market_rates?.rates?.[city]?.hotel_occ||72,
    apart_occ:S.market_rates?.rates?.[city]?.apart_occ||68,
  }});
  if(r.ok){await loadMarket();toast_('تم حفظ أسعار السوق ✓');}
}
function previewPrice(type,val){const el=document.getElementById('prev-'+type);if(el)el.textContent=val?`${F(val)} ر.س / ليلة`:'';} 
function rCfg(){
  // Fill form from settings
  const s=S.settings;
  ['cfg-name','cfg-type','cfg-rooms','cfg-city'].forEach(id=>{
    const el=document.getElementById(id);if(!el)return;
    const k={
      'cfg-name':'name','cfg-type':'type',
      'cfg-rooms':'rooms','cfg-city':'city'
    }[id];
    if(s[k]!==undefined)el.value=s[k];
  });
  // Prices
  const priceMap={
    'cfg-p-hotel-std':'price_hotel_standard',
    'cfg-p-hotel-suite':'price_hotel_suite',
    'cfg-p-apart-studio':'price_apart_studio',
    'cfg-p-apart-one':'price_apart_one',
    'cfg-p-apart-two':'price_apart_two',
    'cfg-p-apart-three':'price_apart_three',
  };
  Object.entries(priceMap).forEach(([id,key])=>{const el=document.getElementById(id);if(el&&s[key])el.value=s[key];});
  // Market prices
  const mh=document.getElementById('cfg-mkt-hotel');const ma=document.getElementById('cfg-mkt-apart');
  if(mh&&s.market_price_hotel)mh.value=s.market_price_hotel;
  if(ma&&s.market_price_apart)ma.value=s.market_price_apart;
  // Bank
  const bn=document.getElementById('cfg-bank-name');const bb=document.getElementById('cfg-bank-bank');const bi=document.getElementById('cfg-bank-iban');
  if(bn&&s.owner_account_name)bn.value=s.owner_account_name;
  if(bb&&s.owner_bank)bb.value=s.owner_bank;
  if(bi&&s.owner_iban)bi.value=s.owner_iban;
  // Recipients
  document.getElementById('recs-list').innerHTML=(s.recipients||[]).map((r,i)=>`<span style="display:inline-flex;align-items:center;gap:5px;background:var(--bg);border:1.5px solid var(--border);border-radius:20px;padding:4px 10px;font-size:11px;margin:2px"><b>${r.name}</b><span style="color:var(--muted);font-size:10px">${r.email}</span><button style="cursor:pointer;background:none;border:none;color:var(--muted);font-size:14px;padding:0;line-height:1" onclick="delRec(${i})">×</button></span>`).join('')||'<div style="font-size:11px;color:var(--muted)">لا يوجد مستلمون</div>';
  // Payment methods
  renderPayMethods();
  // Show/hide price sections by type
  const isHotel=!s.type||s.type==='hotel';
  const ph=document.getElementById('cfg-prices-hotel');const pa=document.getElementById('cfg-prices-apart');
  if(ph)ph.style.display=isHotel?'grid':'none';
  if(pa)pa.style.display=isHotel?'none':'grid';
}
function renderPayMethods(){
  const methods=S.settings.custom_pay_methods||[];
  const grid=document.getElementById('pay-methods-grid');if(!grid)return;
  grid.innerHTML=methods.map((m,i)=>`
    <label style="display:flex;align-items:center;gap:8px;padding:9px 11px;border-radius:9px;background:var(--bg);border:1.5px solid ${m.enabled?'var(--g)':'var(--border)'};cursor:pointer;transition:border-color .1s" onclick="togglePay(${i})">
      <span style="font-size:18px">${m.icon||'💳'}</span>
      <div style="flex:1">
        <div style="font-size:11px;font-weight:700;color:var(--text)">${m.label}</div>
        <div style="font-size:9px;color:${m.enabled?'var(--g)':'var(--muted)'};margin-top:1px">${m.enabled?'مفعّل ✓':'معطّل'}</div>
      </div>
      <div style="width:18px;height:18px;border-radius:50%;background:${m.enabled?'var(--g)':'var(--border)'};display:flex;align-items:center;justify-content:center;font-size:10px;color:#fff;flex-shrink:0">${m.enabled?'✓':''}</div>
    </label>`).join('');
}
function togglePay(i){
  if(!S.settings.custom_pay_methods)return;
  S.settings.custom_pay_methods[i].enabled=!S.settings.custom_pay_methods[i].enabled;
  renderPayMethods();
}
function addCustomPay(){
  const label=gv('new-pay-label').trim();const icon=gv('new-pay-icon').trim()||'💳';
  if(!label){toast_('أدخل اسم طريقة الدفع',false);return;}
  if(!S.settings.custom_pay_methods)S.settings.custom_pay_methods=[];
  S.settings.custom_pay_methods.push({id:'custom_'+Date.now(),label,enabled:true,icon});
  renderPayMethods();
  const ln=document.getElementById('new-pay-label');if(ln)ln.value='';
  const li=document.getElementById('new-pay-icon');if(li)li.value='';
}
async function savePayMethods(){
  const methods=S.settings.custom_pay_methods||[];
  const r=await api('/api/pay_methods/save',{methods});
  if(r.ok)toast_('تم حفظ طرق الدفع ✓');
}

// ── AI MARKET ANALYSIS ───────────────────────────────────────
async function runAIMarket(){
  const btn=document.getElementById('ai-market-btn');
  if(btn){btn.textContent='جارٍ التحليل...';btn.disabled=true;}
  const city=S.settings.city||'riyadh';
  const typ=S.settings.type||'hotel';
  const r=await api('/api/market/ai',{city,type:typ});
  if(btn){btn.textContent='تحليل السوق بـ AI';btn.disabled=false;}
  if(r.ok&&r.result){
    const res=r.result;
    // Update market rates display
    const mr=S.market_rates||{};mr.rates=mr.rates||{};
    mr.rates[city]={hotel_avg:res.hotel_avg||0,apart_avg:res.apart_avg||0,hotel_occ:res.hotel_occ||0,apart_occ:res.apart_occ||0};
    S.market_rates=mr;
    await loadMarket();
    toast_(`✅ تحليل AI: ${res.season||''} — ${res.recommendation||'تم التحديث'}`);
    // Show AI insight
    const el=document.getElementById('ai-insight');
    if(el){
      el.style.display='block';
      el.innerHTML=`<div class="ab-t">💡 توصية الذكاء الاصطناعي</div>
      <div style="margin-top:4px;font-size:11px">${res.recommendation||''}</div>
      ${res.insight?`<div style="margin-top:4px;font-size:10px;color:var(--muted)">${res.insight}</div>`:''}
      <div style="margin-top:5px;font-size:10px;display:flex;gap:12px;flex-wrap:wrap">
        <span>🏨 فندق: <b>${F(res.hotel_avg||0)} ر.س</b></span>
        <span>🏢 شقق: <b>${F(res.apart_avg||0)} ر.س</b></span>
        <span>📊 إشغال: <b>${res.hotel_occ||0}%</b></span>
        <span>🌙 موسم: <b>${res.season||'عادي'} ×${res.season_factor||1}</b></span>
      </div>`;
    }
  } else {
    toast_(r.message||'يحتاج مفتاح Claude API في الإعدادات',false);
    if(!S.settings.claude_key){
      setTimeout(()=>go('cfg'),1200);
    }
  }
}

async function addRec(){const n=gv('cfg-rn').trim(),e=gv('cfg-re').trim();if(!n||!e.includes('@')){toast_('أدخل الاسم والبريد',false);return;}S.settings.recipients=S.settings.recipients||[];S.settings.recipients.push({name:n,email:e});await api('/api/settings/save',S.settings);const rn=document.getElementById('cfg-rn');if(rn)rn.value='';const re=document.getElementById('cfg-re');if(re)re.value='';rCfg();toast_(`تمت إضافة ${n} ✓`);}
async function delRec(i){S.settings.recipients.splice(i,1);await api('/api/settings/save',S.settings);rCfg();}
</script>
</body>
</html>"""



# ── Admin module shim (inline — no importlib needed) ────────
import types as _types
_admin_mod_obj = None
def _load_admin_mod():
    global _admin_mod_obj
    if _admin_mod_obj is not None:
        return _admin_mod_obj
    _admin_mod_obj = _types.SimpleNamespace(
        adm=adm, sessions=sessions,
        ADMIN_PASS=ADMIN_PASS,
        AdminHandler=AdminHandler,
        _build_admin_html=_build_admin_html,
        _build_login_html=_build_login_html,
    )
    return _admin_mod_obj

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
        try:
            html = _build_html()
        except Exception as e:
            log.error(f"_build_client_html error: {e}")
            html = "<h2>خطأ في تحميل النظام</h2>"
        # Inject trial warning if needed
        if client and client.get("status") == "trial":
            dl = days_left(client.get("trial_end",""))
            if dl is not None and dl <= 3:
                warn = f'''<div style="position:fixed;top:0;right:0;left:0;z-index:9999;background:#854F0B;color:#fff;padding:7px;text-align:center;font-size:12px;direction:rtl;">تبقّت <b>{dl} أيام</b> من تجربتك المجانية</div>'''
                html = html.replace("<body>", "<body>" + warn, 1)
        return html



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

if __name__ == "__main__":
    print("="*58)
    print("  نظام إدارة الفنادق — Unified SaaS Server")
    print("="*58)
    print(f"  لوحة العميل : http://localhost:{CLIENT_PORT}")
    print(f"  لوحة المالك : http://localhost:{ADMIN_PORT}/admin")
    print(f"  كلمة مرور Admin: {ADMIN_PASS}")
    print("="*58)
    # Run admin in background thread
    t2 = threading.Thread(target=run_admin, daemon=True)
    t2.start()
    # Run client in MAIN thread (Railway requires this)
    log.info(f"Starting on port {CLIENT_PORT}")
    sv = HTTPServer(("0.0.0.0", CLIENT_PORT), ClientHandler)
    log.info(f"Server ready on 0.0.0.0:{CLIENT_PORT}")
    try:
        sv.serve_forever()
    except KeyboardInterrupt:
        print("\n  تم الإيقاف.")
