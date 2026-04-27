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
        s["plans"] = plans
        s.setdefault("prices",{})[dup["id"]] = dup["price"]
        adm.set("admin_settings", s)
        self._json({"ok": True, "plan": dup})

    def _p_update_upload(self, b):
        """رفع ملف تحديث — يفحص الصياغة ويحفظ نسخة احتياطية"""
        import base64 as _b64, hashlib as _hs, os as _os
        file_data   = b.get("file_data","")
        file_name   = b.get("file_name","")
        description = b.get("description","")
        if not file_data or not file_name:
            self._json({"ok":False,"error":"أرفق الملف واسمه"}); return
        try: raw = _b64.b64decode(file_data)
        except Exception as e:
            self._json({"ok":False,"error":f"خطأ في الترميز: {e}"}); return
        allowed = {"main.py","main_admin.py","unified_server.py"}
        safe_name = _os.path.basename(file_name)
        if safe_name not in allowed:
            self._json({"ok":False,"error":f"الملفات المدعومة: {', '.join(allowed)}"}); return
        try:
            import ast as _ast
            _ast.parse(raw.decode("utf-8"))
        except SyntaxError as e:
            self._json({"ok":False,"error":f"خطأ في صياغة Python السطر {e.lineno}: {e.msg}"}); return
        current_dir = _os.path.dirname(_os.path.abspath(__file__))
        target_path = _os.path.join(current_dir, safe_name)
        _backup_dir = _os.path.join(DATA_DIR, "update_backups")
        _os.makedirs(_backup_dir, exist_ok=True)
        if _os.path.exists(target_path):
            import shutil as _sh, time as _tm
            _sh.copy2(target_path, _os.path.join(_backup_dir, f"{safe_name}.backup_{int(_tm.time())}")) 
        with open(target_path, "wb") as f: f.write(raw)
        chk = _hs.md5(raw).hexdigest()[:8]
        size_kb = round(len(raw)/1024, 1)
        updates = adm.get("update_history", [])
        updates.append({"file":safe_name,"size_kb":size_kb,"md5":chk,"description":description,"uploaded_at":_iso(),"lines":raw.decode("utf-8","ignore").count("\n")})
        adm.set("update_history", updates[-20:])
        logging.info(f"Update: {safe_name} {size_kb}KB md5:{chk}")
        self._json({"ok":True,"file":safe_name,"size_kb":size_kb,"md5":chk,
            "message":f"تم رفع {safe_name} ({size_kb}KB) — أعد تشغيل الخادم لتفعيل التحديث",
            "restart_needed":True})

    def _p_update_status(self, b=None):
        self._json({"ok":True,"history":adm.get("update_history",[])[-10:]})

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
          <div class="fg"><label>المدينة</label><select id="rg-city"><option value="riyadh">الرياض</option><option value="jeddah">جدة</option><option value="makkah">مكة</option><option value="madinah">المدينة</option><option value="dammam">الدمام</option><option value="abha">أبها</option><option value="other">أخرى</option></select></div>
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
          <div class="fg"><label>المدينة</label><select id="br-city"><option value="riyadh">الرياض</option><option value="jeddah">جدة</option><option value="makkah">مكة</option><option value="dammam">الدمام</option><option value="abha">أبها</option><option value="other">أخرى</option></select></div>
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
def start_server():
    server = HTTPServer(("127.0.0.1", PORT), AdminHandler)
    logging.info(f"Admin server started on port {PORT}")
    server.serve_forever()

def open_browser():
    time.sleep(1.5)
    webbrowser.open(f"http://127.0.0.1:{PORT}/admin")

if __name__ == "__main__":
    print("=" * 55)
    print("  لوحة تحكم المالك — Hotel Admin Panel")
    print("=" * 55)
    print(f"  العنوان: http://127.0.0.1:{PORT}/admin")
    print(f"  كلمة المرور: {ADMIN_PASS}")
    print(f"  البيانات: {DATA_DIR}")
    print("  اضغط Ctrl+C للإيقاف")
    print("=" * 55)
    t = threading.Thread(target=open_browser, daemon=True)
    t.start()
    try:
        start_server()
    except KeyboardInterrupt:
        print("\n  تم الإيقاف.")
    except OSError as e:
        if "Address already in use" in str(e):
            print(f"  المنفذ {PORT} مشغول.")
        else:
            raise
