#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
نظام إدارة الفندق والشقق المخدومة — النسخة 2.0
Hotel & Serviced Apartments Management System v2.0
يعمل على Windows بدون إنترنت — يفتح المتصفح تلقائياً
"""

import sys, os, json, threading, webbrowser, time, logging, socket
from http.server import HTTPServer, BaseHTTPRequestHandler
from datetime import datetime, date, timedelta
from urllib.parse import urlparse, parse_qs

# ── مسارات ──────────────────────────────────────────────────
BASE_DIR = getattr(sys, '_MEIPASS', os.path.dirname(os.path.abspath(__file__)))
APP_DIR  = os.path.join(os.path.expanduser("~"), "HotelSystem")
DATA_DIR = os.path.join(APP_DIR, "data")
LOG_DIR  = os.path.join(APP_DIR, "logs")
for d in [DATA_DIR, LOG_DIR]: os.makedirs(d, exist_ok=True)

PORT = 5050

logging.basicConfig(
    filename=os.path.join(LOG_DIR, f"system_{date.today()}.log"),
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    encoding="utf-8"
)

# ══════════════════════════════════════════════════════════════
#  قاعدة البيانات — JSON
# ══════════════════════════════════════════════════════════════
class Store:
    def __init__(self):
        self._file = os.path.join(DATA_DIR, "store.json")
        self._data = self._load()

    def _load(self):
        if os.path.exists(self._file):
            try:
                with open(self._file, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception as e:
                logging.error(f"Store load error: {e}")
        return self._defaults()

    def _defaults(self):
        return {
            "settings": {
                "name": "فندق النخبة", "type": "hotel", "city": "riyadh",
                "rooms": 50, "floors": 5, "currency": "SAR",
                "vat_enabled": True, "tourism_tax": True,
                "recipients": [
                    {"name": "المدير العام",  "email": "manager@hotel.com"},
                    {"name": "المدير المالي", "email": "cfo@hotel.com"},
                ],
                "pms_integrations": [],   # قائمة تكاملات PMS
                "market_comp_set": [],    # منافسون للمقارنة
                "mk": "", "ap": "",
            "owner_iban": "",
            "owner_bank": "",
            "owner_account_name": "",
            "custom_pay_methods": [
                {"id":"mada",   "label":"مدى",           "enabled":True,  "icon":"💳"},
                {"id":"cash",   "label":"نقداً",          "enabled":True,  "icon":"💵"},
                {"id":"visa",   "label":"فيزا",           "enabled":True,  "icon":"💳"},
                {"id":"master", "label":"ماستركارد",      "enabled":True,  "icon":"💳"},
                {"id":"stc",    "label":"STC Pay",         "enabled":True,  "icon":"📱"},
                {"id":"apple",  "label":"Apple Pay",       "enabled":True,  "icon":"🍎"},
                {"id":"transfer","label":"تحويل بنكي",    "enabled":True,  "icon":"🏦"},
                {"id":"digital","label":"محفظة رقمية",   "enabled":False, "icon":"📲"},
                {"id":"credit", "label":"آجل / دين",      "enabled":True,  "icon":"📋"},
            ],
            "unit_types": [
                {"id":"room",    "label":"غرفة فندقية",   "type":"hotel", "icon":"🛏️",  "default_price":350},
                {"id":"suite",   "label":"جناح فندقي",    "type":"hotel", "icon":"👑",  "default_price":650},
                {"id":"studio",  "label":"استوديو",        "type":"apart", "icon":"🏠",  "default_price":280},
                {"id":"one_bed", "label":"غرفة وصالة",     "type":"apart", "icon":"🛋️", "default_price":380},
                {"id":"two_bed", "label":"غرفتان وصالة",   "type":"apart", "icon":"🏘️", "default_price":480},
                {"id":"three_bed","label":"3 غرف وصالة",   "type":"apart", "icon":"🏡", "default_price":620},
                {"id":"penthouse","label":"بنتهاوس",        "type":"hotel", "icon":"🌟", "default_price":1200},
            ],
            "market_price_hotel": 0,
            "market_price_apart": 0,
            "price_hotel_standard": 350,
            "price_hotel_suite":    650,
            "price_apart_studio":   280,
            "price_apart_one":      380,
            "price_apart_two":      480,
            "price_apart_three":    620,
            },
            "guests": [], "services": [], "suppliers": [], "invoices": [],
            "receivables": [], "journal_entries": [], "pos_devices": [
                {"id":1,"name":"جهاز المطعم","dept":"restaurant","color":"#185FA5","serial":"","mk":"","data":None},
                {"id":2,"name":"جهاز الكافيه","dept":"cafe","color":"#854F0B","serial":"","mk":"","data":None},
                {"id":3,"name":"جهاز المغسلة","dept":"laundry","color":"#534AB7","serial":"","mk":"","data":None},
                {"id":4,"name":"جهاز المسبح","dept":"pool","color":"#0F6E56","serial":"","mk":"","data":None},
            ],
            "budget_lines": [
                {"id":1,"name":"إجمالي الإيرادات","type":"rev","planned":90000,"actual":0,"parent_id":None,"level":0},
                {"id":11,"name":"إيرادات الغرف","type":"rev","planned":75000,"actual":0,"parent_id":1,"level":1},
                {"id":12,"name":"إيرادات الخدمات","type":"rev","planned":15000,"actual":0,"parent_id":1,"level":1},
                {"id":121,"name":"مغسلة","type":"rev","planned":6000,"actual":0,"parent_id":12,"level":2},
                {"id":122,"name":"طعام ومشروبات","type":"rev","planned":5000,"actual":0,"parent_id":12,"level":2},
                {"id":123,"name":"خدمات أخرى","type":"rev","planned":4000,"actual":0,"parent_id":12,"level":2},
                {"id":2,"name":"إجمالي المصاريف","type":"exp","planned":30000,"actual":0,"parent_id":None,"level":0},
                {"id":21,"name":"مصاريف التشغيل","type":"exp","planned":20000,"actual":0,"parent_id":2,"level":1},
                {"id":211,"name":"كهرباء وماء","type":"exp","planned":8000,"actual":0,"parent_id":21,"level":2},
                {"id":212,"name":"صيانة","type":"exp","planned":5000,"actual":0,"parent_id":21,"level":2},
                {"id":213,"name":"نظافة ولوازم","type":"exp","planned":7000,"actual":0,"parent_id":21,"level":2},
                {"id":22,"name":"مصاريف المغسلة","type":"exp","planned":5000,"actual":0,"parent_id":2,"level":1},
                {"id":23,"name":"سكن الموظفين","type":"exp","planned":3600,"actual":0,"parent_id":2,"level":1},
                {"id":24,"name":"تسويق وإعلان","type":"exp","planned":1400,"actual":0,"parent_id":2,"level":1},
            ],
            # بيانات سوق التسعير
            "market_rates": {
                "last_updated": None,
                "source": "manual",
                "rates": {
                    "riyadh":  {"hotel_avg":320, "apart_avg":280, "hotel_occ":72, "apart_occ":68},
                    "jeddah":  {"hotel_avg":380, "apart_avg":310, "hotel_occ":75, "apart_occ":70},
                    "makkah":  {"hotel_avg":580, "apart_avg":450, "hotel_occ":85, "apart_occ":80},
                    "madinah": {"hotel_avg":420, "apart_avg":360, "hotel_occ":78, "apart_occ":74},
                    "dammam":  {"hotel_avg":290, "apart_avg":260, "hotel_occ":65, "apart_occ":62},
                    "abha":    {"hotel_avg":350, "apart_avg":300, "hotel_occ":80, "apart_occ":76},
                    "taif":    {"hotel_avg":310, "apart_avg":270, "hotel_occ":70, "apart_occ":66},
                },
            },
            # جدولة قراءة PMS
            "pms_schedules": [],
            # سجل قراءات PMS
            "pms_reads": [],
        }

    def save(self):
        with open(self._file, "w", encoding="utf-8") as f:
            json.dump(self._data, f, ensure_ascii=False, indent=2)

    def get(self, key, default=None):
        return self._data.get(key, default)

    def set(self, key, value):
        self._data[key] = value
        self.save()

    def append(self, key, item):
        self._data.setdefault(key, []).append(item)
        self.save()

    def update_item(self, key, item_id, updates):
        for item in self._data.get(key, []):
            if str(item.get("id")) == str(item_id):
                item.update(updates)
        self.save()

    def delete_item(self, key, item_id):
        self._data[key] = [i for i in self._data.get(key, [])
                           if str(i.get("id")) != str(item_id)]
        self.save()

store = Store()

# ══════════════════════════════════════════════════════════════
#  منطق الأعمال
# ══════════════════════════════════════════════════════════════
def sys_in():
    guests   = store.get("guests", [])
    services = store.get("services", [])
    return sum(g["total"] for g in guests) + sum(s["amount"] for s in services)

def sys_out():
    return sum(i["total"] for i in store.get("invoices", []) if i.get("status") != "paid")

def pos_net():
    return sum((d["data"]["sales"] - d["data"].get("refund", 0))
               for d in store.get("pos_devices", []) if d.get("data"))

def run_matching():
    pos  = pos_net()
    sys  = sys_in()
    diff = pos - sys
    abs_diff = abs(diff)
    pct  = abs_diff / pos * 100 if pos > 0 else 0
    if abs_diff < 1:
        status, color = "MATCHED", "green"
        label = "مطابقة تامة ✓"
    elif pct <= 2:
        status, color = "PARTIAL", "orange"
        label = f"مطابقة جزئية ⚠ فرق {abs_diff:.0f} ر.س"
    else:
        status = "DIFF"
        color  = "green" if diff > 0 else "red"
        label  = f"+ الجهاز يزيد {abs_diff:.0f} ر.س ↑" if diff > 0 else f"- الجهاز ينقص {abs_diff:.0f} ر.س ↓"
    return {"status": status, "label": label, "color": color,
            "pos_net": round(pos, 2), "sys_in": round(sys, 2),
            "diff": round(diff, 2), "abs_diff": round(abs_diff, 2), "pct": round(pct, 2)}

def get_market_kpi():
    """حساب مؤشرات السوق مقارنةً بمنشأتنا"""
    s     = store.get("settings", {})
    city  = s.get("city", "riyadh")
    typ   = s.get("type", "hotel")
    rooms = s.get("rooms", 50) or 50
    mr    = store.get("market_rates", {}).get("rates", {}).get(city, {})
    key   = "hotel_avg" if typ == "hotel" else "apart_avg"
    occ_k = "hotel_occ" if typ == "hotel" else "apart_occ"
    market_adr = mr.get(key, 0)
    market_occ = mr.get(occ_k, 0)
    market_revpar = round(market_adr * market_occ / 100)
    # بيانات منشأتنا
    guests   = store.get("guests", [])
    act_gst  = [g for g in guests if g.get("status") == "active"]
    room_rev = sum(g["total"] for g in guests)
    nights   = sum(g.get("nights", 1) for g in guests) or 1
    our_adr  = round(room_rev / nights)
    our_occ  = round(len(act_gst) / rooms * 100)
    our_revpar = round(room_rev / rooms)
    return {
        "market_adr": market_adr, "market_occ": market_occ, "market_revpar": market_revpar,
        "our_adr": our_adr, "our_occ": our_occ, "our_revpar": our_revpar,
        "adr_diff": our_adr - market_adr, "occ_diff": our_occ - market_occ,
        "revpar_diff": our_revpar - market_revpar,
        "city": city, "type": typ,
        "season_factor": get_season_factor(city),
        "season_label": get_season_label(city),
    }

SAUDI_SEASONS = [
    {"name": "يوم التأسيس",     "start": (2,22),  "end": (2,23),  "factor": 1.6},
    {"name": "رمضان 1446",      "start": (2,28),  "end": (3,28),  "factor": 1.5},
    {"name": "عيد الفطر 1446",  "start": (3,29),  "end": (4,3),   "factor": 2.5},
    {"name": "موسم الحج 1446",  "start": (6,1),   "end": (6,10),  "factor": 3.5, "cities": ["makkah"]},
    {"name": "عيد الأضحى 1446", "start": (6,5),   "end": (6,9),   "factor": 2.8},
    {"name": "إجازة صيفية",     "start": (6,15),  "end": (9,15),  "factor": 1.7},
    {"name": "صيف أبها",        "start": (6,15),  "end": (9,15),  "factor": 2.0, "cities": ["abha"]},
    {"name": "اليوم الوطني",    "start": (9,23),  "end": (9,25),  "factor": 2.0},
    {"name": "موسم الرياض",     "start": (10,1),  "end": (3,31),  "factor": 1.4, "cities": ["riyadh"]},
    {"name": "F1 جدة",          "start": (12,5),  "end": (12,7),  "factor": 3.0, "cities": ["jeddah"]},
    {"name": "MDLBeast",        "start": (12,18), "end": (12,20), "factor": 2.5, "cities": ["riyadh"]},
    {"name": "رمضان 1447",      "start": (2,17),  "end": (3,17),  "factor": 1.5},
    {"name": "عيد الفطر 1447",  "start": (3,19),  "end": (3,22),  "factor": 2.5},
]

def get_season_factor(city="riyadh"):
    today = date.today()
    wd = today.weekday()
    best = 1.0
    for s in SAUDI_SEASONS:
        cities = s.get("cities")
        if cities and city not in cities:
            continue
        sm, sd = s["start"]; em, ed = s["end"]
        st = date(today.year, sm, sd); en = date(today.year, em, ed)
        if en < st: en = date(today.year + 1, em, ed)
        if st <= today <= en:
            best = max(best, s["factor"])
    if wd in (3, 4):  # خميس، جمعة
        best = max(best, 1.3)
    return best

def get_season_label(city="riyadh"):
    today = date.today()
    for s in SAUDI_SEASONS:
        cities = s.get("cities")
        if cities and city not in cities:
            continue
        sm, sd = s["start"]; em, ed = s["end"]
        st = date(today.year, sm, sd); en = date(today.year, em, ed)
        if en < st: en = date(today.year + 1, em, ed)
        if st <= today <= en:
            return s["name"]
    wd = date.today().weekday()
    if wd in (3, 4): return "نهاية الأسبوع"
    return "موسم عادي"

# ══════════════════════════════════════════════════════════════
#  HTTP Handler
# ══════════════════════════════════════════════════════════════
class Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args): pass

    def do_GET(self):
        p = urlparse(self.path)
        path = p.path.rstrip("/") or "/"
        routes = {
            "/":              self._ui,
            "/api/store":     self._api_store,
            "/api/match":     self._api_match,
            "/api/market":    self._api_market,
            "/api/kpi":       self._api_kpi,
            "/api/pms/test":  self._api_pms_test,
            "/api/backups":   self._api_backups,
            "/api/pay_methods": self._api_pay_methods,
            "/api/unit_types":  self._api_unit_types,
        }
        fn = routes.get(path)
        if fn: fn(p)
        else:  self._json({"error": "not found"}, 404)

    def do_POST(self):
        p = urlparse(self.path)
        n = int(self.headers.get("Content-Length", 0))
        b = json.loads(self.rfile.read(n)) if n else {}
        routes = {
            "/api/guests/add":          self._p_guest_add,
            "/api/guests/checkout":     self._p_guest_checkout,
            "/api/services/add":        self._p_svc_add,
            "/api/pos/device/add":      self._p_pos_add,
            "/api/pos/device/delete":   self._p_pos_del,
            "/api/pos/device/rename":   self._p_pos_rename,
            "/api/pos/data/save":       self._p_pos_save,
            "/api/pos/data/clear":      self._p_pos_clear,
            "/api/suppliers/add":       self._p_sup_add,
            "/api/invoices/add":        self._p_inv_add,
            "/api/invoices/pay":        self._p_inv_pay,
            "/api/receivables/add":     self._p_recv_add,
            "/api/receivables/collect": self._p_recv_col,
            "/api/journal/add":         self._p_jnl_add,
            "/api/budget/save":         self._p_bgt_save,
            "/api/settings/save":       self._p_cfg_save,
            "/api/market/update":       self._p_market_update,
            "/api/pms/add":             self._p_pms_add,
            "/api/pms/delete":          self._p_pms_del,
            "/api/pms/read":            self._p_pms_read,
            "/api/pms/schedule/save":   self._p_pms_sched,
            "/api/backup/create":       self._p_backup_create,
            "/api/backup/restore":      self._p_backup_restore,
            "/api/search":              self._p_search,
            "/api/market/ai":           self._p_market_ai,
            "/api/pay_methods/save":    self._p_pay_methods_save,
            "/api/bank/save":           self._p_bank_save,
            "/api/prices/save":         self._p_prices_save,
            "/api/unit_types/save":     self._p_unit_types_save,
            "/api/backup/email":        self._p_backup_email,
            "/api/market/websearch":    self._p_market_websearch,
        }
        fn = routes.get(p.path.rstrip("/"))
        if fn: fn(b)
        else:  self._json({"error": "not found"}, 404)

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET,POST,OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    # ── helpers ──────────────────────────────────────────────
    def _json(self, data, status=200):
        body = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type",   "application/json; charset=utf-8")
        self.send_header("Content-Length", len(body))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(body)

    def _id(self): return int(datetime.now().timestamp() * 1000)
    def _now(self): return datetime.now().strftime("%H:%M")
    def _today(self): return str(date.today())

    # ── GET ───────────────────────────────────────────────────
    def _ui(self, _):
        html = _build_html()
        body = html.encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type",   "text/html; charset=utf-8")
        self.send_header("Content-Length", len(body))
        self.end_headers()
        self.wfile.write(body)

    def _api_store(self, _):
        self._json({
            "settings":       store.get("settings", {}),
            "guests":         store.get("guests", []),
            "services":       store.get("services", []),
            "suppliers":      store.get("suppliers", []),
            "invoices":       store.get("invoices", []),
            "receivables":    store.get("receivables", []),
            "journal_entries":store.get("journal_entries", []),
            "pos_devices":    store.get("pos_devices", []),
            "budget_lines":   store.get("budget_lines", []),
            "market_rates":   store.get("market_rates", {}),
            "pms_integrations":store.get("settings", {}).get("pms_integrations", []),
            "pms_schedules":  store.get("pms_schedules", []),
            "pms_reads":      store.get("pms_reads", [])[-20:],  # آخر 20 قراءة
        })

    def _api_match(self, _):
        self._json(run_matching())

    def _api_market(self, _):
        self._json(get_market_kpi())

    def _api_kpi(self, p):
        qs     = parse_qs(p.query)
        rooms  = float(qs.get("rooms",  ["50"])[0])
        occ_r  = float(qs.get("occ",    ["0"])[0])
        nights = float(qs.get("nights", ["1"])[0]) or 1
        rrev   = float(qs.get("rrev",   ["0"])[0])
        trev   = float(qs.get("trev",   ["0"])[0])
        texp   = float(qs.get("texp",   ["0"])[0])
        revpar   = round(rrev / rooms)       if rooms   > 0 else 0
        adr      = round(rrev / nights)      if nights  > 0 else 0
        occ      = round(occ_r / rooms * 100) if rooms  > 0 else 0
        gop      = round((trev - texp) / trev * 100) if trev > 0 else 0
        trevpar  = round(trev / rooms)       if rooms   > 0 else 0
        self._json({"revpar":revpar,"adr":adr,"occ":occ,"gop":gop,"trevpar":trevpar,"npm":gop})

    def _api_pms_test(self, _):
        """اختبار الاتصال بـ PMS"""
        self._json({"ok": True, "message": "الاتصال بـ PMS يتطلب شبكة داخلية"})

    # ── POST ──────────────────────────────────────────────────
    def _p_guest_add(self, b):
        nights = max(1, b.get("nights", 1))
        total  = nights * float(b.get("price", 0))
        pay    = b.get("pay", "cash")
        g = {
            "id": self._id(), "name": b.get("name",""), "idNum": b.get("idNum",""),
            "unit": b.get("unit",""), "bed": b.get("bed","double"),
            "extra": int(b.get("extra", 0)),
            "inDate": b.get("inDate",""), "outDate": b.get("outDate",""),
            "nights": nights, "price": float(b.get("price",0)),
            "pay": pay, "total": round(total,2), "status": "active", "time": self._now(),
        }
        store.append("guests", g)
        store.append("journal_entries", {
            "id": self._id()+1, "time": self._now(),
            "drAcc": "receivable" if pay=="credit" else "bank",
            "crAcc": "room_rev", "amount": g["total"],
            "desc": f"إيراد نزيل — {g['name']}", "ref": g["unit"],
        })
        self._json({"ok": True, "guest": g})

    def _p_guest_checkout(self, b):
        store.update_item("guests", b.get("id"), {"status": "checkedout"})
        self._json({"ok": True})

    def _p_svc_add(self, b):
        amt = float(b.get("amount", 0))
        pay = b.get("pay", "cash")
        s = {
            "id": self._id(), "time": self._now(),
            "type": b.get("type","other"), "unit": b.get("unit",""),
            "pay": pay, "amount": amt,
        }
        store.append("services", s)
        store.append("journal_entries", {
            "id": self._id()+1, "time": self._now(),
            "drAcc": "receivable" if pay=="credit" else "bank",
            "crAcc": "svc_rev", "amount": amt,
            "desc": f"{s['type']} — {s['unit']}", "ref": "",
        })
        self._json({"ok": True, "service": s})

    def _p_pos_add(self, b):
        cols = ["#185FA5","#0F6E56","#A32D2D","#534AB7","#854F0B","#D85A30","#1D9E75"]
        devs = store.get("pos_devices", [])
        d = {
            "id": self._id(), "name": b.get("name","جهاز جديد"),
            "dept": b.get("dept","other"),
            "color": b.get("color", cols[len(devs) % len(cols)]),
            "serial": b.get("serial",""), "mk": b.get("mk",""), "data": None,
        }
        store.append("pos_devices", d)
        self._json({"ok": True, "device": d})

    def _p_pos_del(self, b):
        store.delete_item("pos_devices", b.get("id"))
        self._json({"ok": True})

    def _p_pos_rename(self, b):
        store.update_item("pos_devices", b.get("id"), {"name": b.get("name","")})
        self._json({"ok": True})

    def _p_pos_save(self, b):
        did = b.get("id")
        data = {
            "sales":      float(b.get("sales", 0)),
            "refund":     float(b.get("refund", 0)),
            "vat":        float(b.get("vat", 0)),
            "txCount":    int(b.get("txCount", 0)),
            "notes":      b.get("notes", ""),
            "breakdown":  b.get("breakdown", {}),
            "receivedAt": self._now(),
            "date":       self._today(),
        }
        store.update_item("pos_devices", did, {"data": data})
        self._json({"ok": True, "match": run_matching()})

    def _p_pos_clear(self, b):
        store.update_item("pos_devices", b.get("id"), {"data": None})
        self._json({"ok": True})

    def _p_sup_add(self, b):
        cols = ["#185FA5","#0F6E56","#A32D2D","#534AB7","#854F0B","#D85A30","#1D9E75"]
        idx  = len(store.get("suppliers", [])) % len(cols)
        sup  = {
            "id": self._id(), "name": b.get("name",""),
            "type": b.get("type","other"), "phone": b.get("phone",""),
            "iban": b.get("iban",""), "cr": b.get("cr",""),
            "terms": b.get("terms","cash"), "color": cols[idx],
        }
        store.append("suppliers", sup)
        self._json({"ok": True, "supplier": sup})

    def _p_inv_add(self, b):
        base = float(b.get("base", 0))
        vat  = round(base * 0.15, 2) if b.get("vat", True) else 0.0
        total = base + vat
        inv = {
            "id": self._id(), "supId": b.get("supId"),
            "supName": b.get("supName","مورّد"),
            "num": b.get("num", f"INV-{self._id()}"),
            "base": base, "vat": vat, "total": round(total, 2),
            "date": b.get("date", self._today()),
            "due":  b.get("due",  self._today()),
            "status": "pending",
        }
        store.append("invoices", inv)
        store.append("journal_entries", {
            "id": self._id()+1, "time": self._now(),
            "drAcc": "util_exp", "crAcc": "payable",
            "amount": base, "desc": f"فاتورة — {inv['supName']} {inv['num']}", "ref": inv["num"],
        })
        if vat > 0:
            store.append("journal_entries", {
                "id": self._id()+2, "time": self._now(),
                "drAcc": "vat_payable", "crAcc": "payable",
                "amount": vat, "desc": f"VAT فاتورة {inv['num']}", "ref": inv["num"],
            })
        self._json({"ok": True, "invoice": inv})

    def _p_inv_pay(self, b):
        inv_id = b.get("id")
        invs   = store.get("invoices", [])
        inv    = next((i for i in invs if str(i.get("id")) == str(inv_id)), None)
        if inv:
            store.update_item("invoices", inv_id, {"status": "paid"})
            store.append("journal_entries", {
                "id": self._id(), "time": self._now(),
                "drAcc": "payable", "crAcc": "bank",
                "amount": inv["total"],
                "desc": f"دفع فاتورة — {inv['supName']} {inv['num']}", "ref": inv["num"],
            })
        self._json({"ok": True})

    def _p_recv_add(self, b):
        r = {
            "id": self._id(), "name": b.get("name",""),
            "ref": b.get("ref",""), "type": b.get("type","other"),
            "amount": float(b.get("amount",0)),
            "due": b.get("due", self._today()), "status": "pending",
        }
        store.append("receivables", r)
        self._json({"ok": True, "receivable": r})

    def _p_recv_col(self, b):
        rid  = b.get("id")
        recs = store.get("receivables", [])
        rec  = next((r for r in recs if str(r.get("id")) == str(rid)), None)
        if rec:
            store.update_item("receivables", rid, {"status": "collected"})
            store.append("journal_entries", {
                "id": self._id(), "time": self._now(),
                "drAcc": "bank", "crAcc": "receivable",
                "amount": rec["amount"],
                "desc": f"تحصيل ذمة — {rec['name']}", "ref": rec.get("ref",""),
            })
        self._json({"ok": True})

    def _p_jnl_add(self, b):
        e = {
            "id": self._id(), "time": self._now(),
            "drAcc": b.get("drAcc","cash"), "crAcc": b.get("crAcc","revenue"),
            "amount": float(b.get("amount",0)),
            "desc": b.get("desc","قيد يومية"), "ref": b.get("ref",""),
        }
        store.append("journal_entries", e)
        self._json({"ok": True, "entry": e})

    def _p_bgt_save(self, b):
        store.set("budget_lines", b.get("lines", []))
        self._json({"ok": True})

    def _p_cfg_save(self, b):
        s = store.get("settings", {})
        for k in ["name","type","city","rooms","floors","vat_enabled","tourism_tax","mk","ap","recipients","pms_integrations","market_comp_set","owner_iban","owner_bank","owner_account_name","market_price_hotel","market_price_apart","price_hotel_standard","price_hotel_suite","price_apart_studio","price_apart_one","price_apart_two","price_apart_three"]:
            if k in b: s[k] = b[k]
        store.set("settings", s)
        self._json({"ok": True})

    def _p_market_update(self, b):
        """تحديث أسعار السوق يدوياً أو من API"""
        mr = store.get("market_rates", {})
        city  = b.get("city", "riyadh")
        rates = b.get("rates", {})
        if city and rates:
            mr.setdefault("rates", {})[city] = rates
        mr["last_updated"] = datetime.now().isoformat()
        mr["source"] = b.get("source", "manual")
        store.set("market_rates", mr)
        self._json({"ok": True, "market_kpi": get_market_kpi()})

    def _p_pms_add(self, b):
        """إضافة تكامل PMS جديد"""
        s = store.get("settings", {})
        integrations = s.get("pms_integrations", [])
        intg = {
            "id":   self._id(),
            "name": b.get("name", "PMS"),
            "type": b.get("type", "opera"),    # opera | cloudbeds | mews | custom
            "url":  b.get("url", ""),
            "username": b.get("username", ""),
            "password": b.get("password", ""),
            "api_key":  b.get("api_key", ""),
            "port":     b.get("port", ""),
            "enabled":  True,
            "last_read": None,
            "read_count": 0,
        }
        integrations.append(intg)
        s["pms_integrations"] = integrations
        store.set("settings", s)
        self._json({"ok": True, "integration": intg})

    def _p_pms_del(self, b):
        s    = store.get("settings", {})
        intgs = s.get("pms_integrations", [])
        s["pms_integrations"] = [i for i in intgs if str(i.get("id")) != str(b.get("id"))]
        store.set("settings", s)
        self._json({"ok": True})

    def _p_pms_read(self, b):
        """تشغيل قراءة PMS — محاكاة في هذه النسخة"""
        intg_id = b.get("id")
        s       = store.get("settings", {})
        intgs   = s.get("pms_integrations", [])
        intg    = next((i for i in intgs if str(i.get("id")) == str(intg_id)), None)
        if not intg:
            self._json({"ok": False, "error": "التكامل غير موجود"})
            return
        # محاكاة قراءة بيانات من PMS
        # في البيئة الحقيقية: HTTP request to intg["url"] with credentials
        sim_guests = self._simulate_pms_read(intg)
        # تحديث وقت آخر قراءة
        for i in intgs:
            if str(i.get("id")) == str(intg_id):
                i["last_read"] = datetime.now().isoformat()
                i["read_count"] = i.get("read_count", 0) + 1
        store.set("settings", s)
        # حفظ سجل القراءة
        read_log = {
            "id": self._id(), "intg_id": intg_id, "intg_name": intg.get("name",""),
            "time": datetime.now().isoformat(), "status": "success",
            "guests_found": len(sim_guests),
            "data": sim_guests,
        }
        reads = store.get("pms_reads", [])
        reads.append(read_log)
        store.set("pms_reads", reads[-50:])  # احتفظ بآخر 50 قراءة
        logging.info(f"PMS read: {intg.get('name')} — {len(sim_guests)} guests")
        self._json({"ok": True, "guests_found": len(sim_guests), "data": sim_guests, "log_id": read_log["id"]})

    def _simulate_pms_read(self, intg):
        """محاكاة قراءة بيانات من PMS — تُستبدل بـ API حقيقي"""
        typ = intg.get("type", "opera")
        base = [
            {"pms_id": f"{typ.upper()}-001", "name": "محمد عبدالله الغامدي", "room": "101",
             "checkin": self._today(), "checkout": str(date.today() + timedelta(days=2)),
             "rate": 380, "status": "inhouse", "nationality": "SA"},
            {"pms_id": f"{typ.upper()}-002", "name": "Sarah Johnson", "room": "205",
             "checkin": self._today(), "checkout": str(date.today() + timedelta(days=3)),
             "rate": 420, "status": "inhouse", "nationality": "US"},
            {"pms_id": f"{typ.upper()}-003", "name": "خالد عمر الشريف", "room": "312",
             "checkin": self._today(), "checkout": str(date.today() + timedelta(days=1)),
             "rate": 350, "status": "reserved", "nationality": "SA"},
        ]
        return base

    def _p_pms_sched(self, b):
        """حفظ جدول قراءة PMS"""
        scheds = store.get("pms_schedules", [])
        intg_id = b.get("intg_id")
        # تحديث إذا موجود
        existing = next((s for s in scheds if str(s.get("intg_id")) == str(intg_id)), None)
        if existing:
            existing.update(b)
        else:
            scheds.append({
                "id": self._id(), "intg_id": intg_id,
                "frequency": b.get("frequency","manual"),  # manual | hourly | every6h | daily
                "time":      b.get("time", "08:00"),        # للجدولة اليومية
                "enabled":   b.get("enabled", True),
                "last_run":  None,
            })
        store.set("pms_schedules", scheds)
        self._json({"ok": True})

    def _api_unit_types(self, _):
        s = store.get("settings", {})
        self._json({"unit_types": s.get("unit_types", [])})

    def _p_unit_types_save(self, b):
        s = store.get("settings", {})
        s["unit_types"] = b.get("unit_types", [])
        store.set("settings", s)
        self._json({"ok": True})

    def _p_backup_email(self, b):
        """إرسال النسخة الاحتياطية عبر الإيميل"""
        recipients = store.get("settings", {}).get("recipients", [])
        if not recipients:
            self._json({"ok": False, "error": "لا يوجد مستلمون — أضف إيميلات في الإعدادات"})
            return
        # Build backup JSON
        import shutil, smtplib, base64
        from email.mime.multipart import MIMEMultipart
        from email.mime.text import MIMEText
        from email.mime.base import MIMEBase
        from email import encoders
        bk_dir = os.path.join(APP_DIR, "backups")
        os.makedirs(bk_dir, exist_ok=True)
        ts   = datetime.now().strftime("%Y%m%d_%H%M%S")
        name = f"backup_{ts}_email.json"
        dst  = os.path.join(bk_dir, name)
        shutil.copy2(store._file, dst)
        # SMTP settings from store
        s = store.get("settings", {})
        smtp_host = s.get("smtp_host", "smtp.gmail.com")
        smtp_port = int(s.get("smtp_port", 587))
        smtp_user = s.get("smtp_user", "")
        smtp_pass = s.get("smtp_pass", "")
        if not smtp_user:
            # Return ok but with instructions
            self._json({
                "ok": True,
                "mode": "download_only",
                "message": "تم إنشاء النسخة — أضف إعدادات SMTP في الإعدادات لإرسالها بالإيميل",
                "name": name,
                "recipients": [r["email"] for r in recipients]
            })
            return
        try:
            msg = MIMEMultipart()
            msg["From"]    = smtp_user
            msg["To"]      = ", ".join(r["email"] for r in recipients)
            msg["Subject"] = f"نسخة احتياطية — {s.get('name','الفندق')} — {datetime.now().strftime('%Y-%m-%d %H:%M')}"
            body = f"""السلام عليكم،

هذه النسخة الاحتياطية اليومية لنظام {s.get('name','إدارة الفندق')}.
التاريخ: {datetime.now().strftime('%Y-%m-%d %H:%M')}

يمكنكم استعادة هذه النسخة من خلال النظام في تبويب النسخ الاحتياطي.

مع التقدير،
نظام إدارة الفندق v3.0"""
            msg.attach(MIMEText(body, "plain", "utf-8"))
            # Attach JSON
            with open(dst, "rb") as f:
                part = MIMEBase("application", "octet-stream")
                part.set_payload(f.read())
                encoders.encode_base64(part)
                part.add_header("Content-Disposition", f"attachment; filename={name}")
                msg.attach(part)
            with smtplib.SMTP(smtp_host, smtp_port) as server:
                server.starttls()
                server.login(smtp_user, smtp_pass)
                server.send_message(msg)
            logging.info(f"Backup emailed to {len(recipients)} recipients")
            self._json({"ok": True, "mode": "emailed", "recipients": len(recipients), "name": name})
        except Exception as e:
            logging.error(f"Email backup error: {e}")
            self._json({"ok": False, "error": str(e), "name": name, "mode": "created_only"})

    def _p_market_websearch(self, b):
        """بحث ويب عن أسعار السوق ثم تحليل Claude"""
        city    = b.get("city", store.get("settings",{}).get("city","riyadh"))
        typ     = b.get("type", store.get("settings",{}).get("type","hotel"))
        claude_key = store.get("settings",{}).get("claude_key","")
        city_ar = {"riyadh":"الرياض","jeddah":"جدة","makkah":"مكة","madinah":"المدينة المنورة",
                   "dammam":"الدمام","abha":"أبها","taif":"الطائف"}.get(city, city)
        today   = datetime.now().strftime("%Y-%m-%d")

        # Step 1: Try web search via Claude with web_search tool
        search_prompt = f"""ابحث عن أسعار الفنادق والشقق الفندقية في {city_ar} السعودية اليوم {today}.
أريد:
1. متوسط سعر الليلة للفنادق (ADR) بالريال السعودي
2. متوسط سعر الليلة للشقق المخدومة بالريال السعودي
3. نسبة الإشغال المتوقعة في هذه الفترة
4. الموسم السياحي الحالي وتأثيره على الأسعار
5. توصية سعرية دقيقة

استخدم أدوات البحث للحصول على بيانات حقيقية محدثة من Booking.com وAirbnb وغيرها.
ثم أجب بـ JSON فقط:
{{"hotel_avg":0,"apart_avg":0,"hotel_occ":0,"apart_occ":0,"season":"","season_factor":1.0,"recommendation":"","insight":"","source":"web_search"}}"""

        try:
            import urllib.request as ur, re
            # Try with web_search tool if API key available
            if claude_key:
                payload = json.dumps({
                    "model": "claude-opus-4-5",
                    "max_tokens": 1000,
                    "tools": [{"type": "web_search_20250305", "name": "web_search"}],
                    "messages": [{"role":"user","content": search_prompt}]
                }).encode()
                req = ur.Request(
                    "https://api.anthropic.com/v1/messages",
                    data=payload,
                    headers={
                        "Content-Type": "application/json",
                        "anthropic-version": "2023-06-01",
                        "x-api-key": claude_key,
                    },
                    method="POST"
                )
                resp = ur.urlopen(req, timeout=30)
                data = json.loads(resp.read())
                # Extract text from response (may have tool_use blocks)
                text = " ".join(
                    block.get("text","") for block in data.get("content",[])
                    if block.get("type") == "text"
                )
                m = re.search(r'\{[^{}]*"hotel_avg"[^{}]*\}', text, re.DOTALL)
                if not m:
                    m = re.search(r'\{.*\}', text, re.DOTALL)
                result = json.loads(m.group(0)) if m else {}
                result["source"] = "web_search+claude"
            else:
                # Fallback: use built-in market data
                city_rates = {
                    "riyadh":  {"hotel_avg":340,"apart_avg":290,"hotel_occ":74,"apart_occ":69},
                    "jeddah":  {"hotel_avg":390,"apart_avg":320,"hotel_occ":77,"apart_occ":72},
                    "makkah":  {"hotel_avg":580,"apart_avg":460,"hotel_occ":86,"apart_occ":81},
                    "madinah": {"hotel_avg":430,"apart_avg":370,"hotel_occ":79,"apart_occ":75},
                    "dammam":  {"hotel_avg":300,"apart_avg":265,"hotel_occ":66,"apart_occ":63},
                    "abha":    {"hotel_avg":360,"apart_avg":310,"hotel_occ":82,"apart_occ":78},
                    "taif":    {"hotel_avg":315,"apart_avg":275,"hotel_occ":71,"apart_occ":67},
                }
                base = city_rates.get(city, city_rates["riyadh"])
                result = {**base,
                    "season": "موسم الرياض","season_factor":1.4,
                    "recommendation": f"السعر الموصى به للفندق: {int(base['hotel_avg']*1.4)} ر.س — الشقق: {int(base['apart_avg']*1.4)} ر.س",
                    "insight": "بيانات مدمجة محدّثة — أضف مفتاح Claude API للبحث الحي",
                    "source": "builtin"
                }
            # Save to market_rates
            mr = store.get("market_rates", {})
            mr.setdefault("rates", {})[city] = {
                "hotel_avg": result.get("hotel_avg", 0),
                "apart_avg": result.get("apart_avg", 0),
                "hotel_occ": result.get("hotel_occ", 0),
                "apart_occ": result.get("apart_occ", 0),
            }
            mr["last_updated"] = datetime.now().isoformat()
            mr["source"]       = result.get("source","web")
            store.set("market_rates", mr)
            logging.info(f"Market websearch: {city} — {result.get('hotel_avg')} ر.س")
            self._json({"ok": True, "result": result})
        except Exception as e:
            logging.error(f"Market websearch error: {e}")
            self._json({"ok": False, "error": str(e)})

    def _api_pay_methods(self, _):
        s = store.get("settings", {})
        self._json({"pay_methods": s.get("custom_pay_methods", [])})

    def _p_market_ai(self, b):
        """تحليل السوق بالذكاء الاصطناعي — يستخدم Claude API"""
        city  = b.get("city", store.get("settings",{}).get("city","riyadh"))
        typ   = b.get("type", store.get("settings",{}).get("type","hotel"))
        prompt = f"""أنت خبير في قطاع الفنادق والشقق السعودية.
المدينة: {city} | نوع المنشأة: {"فندق" if typ=="hotel" else "شقق مخدومة"}
اليوم: {datetime.now().strftime("%Y-%m-%d")}

بناءً على معرفتك بالسوق السعودي، قدم:
1. متوسط ADR (سعر الغرفة/الليلة) بالريال للفنادق والشقق في {city}
2. نسبة الإشغال المتوقعة %
3. RevPAR المتوقع
4. الموسم الحالي وتأثيره على التسعير
5. توصية سعرية محددة للمنشأة

أجب بـ JSON فقط بهذا الشكل:
{{"hotel_avg":0,"apart_avg":0,"hotel_occ":0,"apart_occ":0,"revpar":0,"season":"","season_factor":1.0,"recommendation":"","insight":""}}"""
        try:
            import urllib.request as ur
            payload = json.dumps({
                "model": "claude-opus-4-5",
                "max_tokens": 600,
                "messages": [{"role":"user","content": prompt}]
            }).encode()
            req = ur.Request(
                "https://api.anthropic.com/v1/messages",
                data=payload,
                headers={
                    "Content-Type": "application/json",
                    "anthropic-version": "2023-06-01",
                    "x-api-key": store.get("settings",{}).get("claude_key",""),
                },
                method="POST"
            )
            resp = ur.urlopen(req, timeout=20)
            data = json.loads(resp.read())
            text = data["content"][0]["text"].strip()
            # extract JSON
            import re
            m = re.search(r'\{.*\}', text, re.DOTALL)
            result = json.loads(m.group(0)) if m else {}
            # Save to market_rates
            mr = store.get("market_rates", {})
            mr.setdefault("rates", {})[city] = {
                "hotel_avg": result.get("hotel_avg", 0),
                "apart_avg": result.get("apart_avg", 0),
                "hotel_occ": result.get("hotel_occ", 0),
                "apart_occ": result.get("apart_occ", 0),
            }
            mr["last_updated"] = datetime.now().isoformat()
            mr["source"] = "claude_ai"
            store.set("market_rates", mr)
            logging.info(f"AI market update: {city} — {result}")
            self._json({"ok": True, "result": result, "source": "claude_ai"})
        except Exception as e:
            logging.error(f"AI market error: {e}")
            self._json({"ok": False, "error": str(e), "message": "يحتاج مفتاح Claude API في الإعدادات"})

    def _p_pay_methods_save(self, b):
        s = store.get("settings", {})
        s["custom_pay_methods"] = b.get("methods", [])
        store.set("settings", s)
        self._json({"ok": True})

    def _p_bank_save(self, b):
        s = store.get("settings", {})
        s["owner_iban"]         = b.get("iban", "")
        s["owner_bank"]         = b.get("bank", "")
        s["owner_account_name"] = b.get("account_name", "")
        store.set("settings", s)
        self._json({"ok": True})

    def _p_prices_save(self, b):
        s = store.get("settings", {})
        for k in ["price_hotel_standard","price_hotel_suite","price_apart_studio",
                  "price_apart_one","price_apart_two","price_apart_three",
                  "market_price_hotel","market_price_apart"]:
            if k in b: s[k] = float(b[k])
        store.set("settings", s)
        self._json({"ok": True})

    def _api_backups(self, _):
        import glob
        bk_dir = os.path.join(APP_DIR, "backups")
        os.makedirs(bk_dir, exist_ok=True)
        files = sorted(glob.glob(os.path.join(bk_dir, "*.json")), reverse=True)[:10]
        bk_list = []
        for f in files:
            try:
                sz = os.path.getsize(f)
                mt = datetime.fromtimestamp(os.path.getmtime(f)).strftime("%Y-%m-%d %H:%M")
                bk_list.append({"name": os.path.basename(f), "date": mt, "size_kb": round(sz/1024,1)})
            except: pass
        self._json({"backups": bk_list})

    def _p_backup_create(self, b):
        import shutil
        bk_dir = os.path.join(APP_DIR, "backups")
        os.makedirs(bk_dir, exist_ok=True)
        label = b.get("label", "")
        ts    = datetime.now().strftime("%Y%m%d_%H%M%S")
        name  = f"backup_{ts}{'_'+label if label else ''}.json"
        dst   = os.path.join(bk_dir, name)
        shutil.copy2(store._file, dst)
        logging.info(f"Backup created: {name}")
        self._json({"ok": True, "name": name, "date": datetime.now().strftime("%Y-%m-%d %H:%M")})

    def _p_backup_restore(self, b):
        import shutil
        bk_dir  = os.path.join(APP_DIR, "backups")
        bk_name = b.get("name", "")
        bk_path = os.path.join(bk_dir, bk_name)
        if not os.path.exists(bk_path):
            self._json({"ok": False, "error": "الملف غير موجود"})
            return
        # حفظ نسخة من الحالي قبل الاستعادة
        ts  = datetime.now().strftime("%Y%m%d_%H%M%S")
        pre = os.path.join(bk_dir, f"pre_restore_{ts}.json")
        shutil.copy2(store._file, pre)
        shutil.copy2(bk_path, store._file)
        # إعادة تحميل
        store._data = store._load()
        logging.info(f"Backup restored: {bk_name}")
        self._json({"ok": True, "message": f"تم استعادة {bk_name}"})

    def _p_search(self, b):
        q = b.get("q", "").strip().lower()
        if not q:
            self._json({"results": []})
            return
        results = []
        for g in store.get("guests", []):
            if q in g.get("name","").lower() or q in g.get("unit","").lower() or q in g.get("idNum","").lower():
                results.append({"type":"guest","label":f"نزيل: {g['name']}","sub":f"وحدة {g.get('unit','')} — {g.get('inDate','')}","id":g["id"],"goto":"guests"})
        for s in store.get("suppliers", []):
            if q in s.get("name","").lower() or q in s.get("phone","").lower():
                results.append({"type":"supplier","label":f"مورّد: {s['name']}","sub":s.get("type",""),"id":s["id"],"goto":"suppliers"})
        for i in store.get("invoices", []):
            if q in i.get("num","").lower() or q in i.get("supName","").lower():
                results.append({"type":"invoice","label":f"فاتورة: {i['num']}","sub":f"{i.get('supName','')} — {i.get('total',0)} ر.س","id":i["id"],"goto":"invoices"})
        for j in store.get("journal_entries", []):
            if q in j.get("desc","").lower() or q in j.get("ref","").lower():
                results.append({"type":"journal","label":f"قيد: {j['desc'][:40]}","sub":f"{j.get('amount',0)} ر.س","id":j["id"],"goto":"journal"})
        for r in store.get("receivables", []):
            if q in r.get("name","").lower():
                results.append({"type":"recv","label":f"ذمة: {r['name']}","sub":f"{r.get('amount',0)} ر.س — {r.get('status','')}","id":r["id"],"goto":"recv"})
        self._json({"results": results[:20]})




# ══════════════════════════════════════════════════════════════
#  واجهة HTML الكاملة
# ══════════════════════════════════════════════════════════════

# ══════════════════════════════════════════════════════════════
#  واجهة HTML الكاملة — النسخة 3.0
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
      <button class="btn sm" style="background:var(--rl);color:var(--r);border:1.5px solid var(--r);font-weight:600" onclick="clientLogout()">خروج ↩</button>
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
  const stC  = {open:'#A32D2D',replied:'#854F0B',closed:'#3B6D11'};
  const el = document.getElementById('tix-list');
  if(!el) return;
  el.innerHTML = tix.length ? [...tix].reverse().map(t => {
    const msgs = t.messages || [];
    const lastMsg = msgs[msgs.length-1];
    const hasAdminReply = msgs.some(m=>m.from==='admin');
    return `<div style="background:var(--bg);border-radius:10px;padding:12px;margin-bottom:8px;border:1.5px solid ${hasAdminReply&&t.status!=='closed'?'#3B6D11':'#E2E8F0'}">
      <div style="display:flex;align-items:flex-start;justify-content:space-between;flex-wrap:wrap;gap:6px">
        <div>
          <div style="font-size:12px;font-weight:700;color:var(--text)">${t.title}</div>
          <div style="font-size:10px;color:var(--muted);margin-top:2px">${catL[t.category]||t.category||'—'} · ${new Date(t.created_at).toLocaleDateString('ar-SA')}</div>
        </div>
        <span style="font-size:9px;padding:3px 9px;border-radius:20px;font-weight:700;background:${stC[t.status]||'var(--muted)'}22;color:${stC[t.status]||'var(--muted)'}">${stL[t.status]||t.status}</span>
      </div>
      ${msgs.length ? `<div style="margin-top:8px;max-height:160px;overflow-y:auto;display:flex;flex-direction:column;gap:5px">
        ${msgs.map(m=>`<div style="padding:6px 9px;border-radius:8px;font-size:11px;background:${m.from==='admin'?'#EAF3DE':'#E6F1FB'};color:${m.from==='admin'?'#27500A':'#0C447C'};max-width:85%;${m.from==='admin'?'margin-right:0':'margin-left:auto'}">
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
async function clientLogout(){try{await api('/api/client/logout',{});}catch(e){}location.href='/';}
async function reload(){const d=await api('/api/store');Object.assign(S,d);}
function toast_(msg,ok=true){const t=document.getElementById('toast');t.textContent=msg;t.style.background=ok?'#3B6D11':'#A32D2D';t.style.boxShadow=ok?'0 4px 14px rgba(4,120,87,.4)':'0 4px 14px rgba(220,38,38,.4)';t.classList.add('show');setTimeout(()=>t.classList.remove('show'),2800);}

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
  document.getElementById('kp-bench').innerHTML=benches.map(b=>{const good=b.v>=b.b,mV=Math.max(b.v,b.b,1);return`<div class="brow"><div class="brow-l">${b.n}</div><div class="brow-t"><div class="brow-f" style="width:${Math.round(b.v/mV*100)}%;background:${good?'#3B6D11':'#A32D2D'}"></div><div style="position:absolute;top:0;height:8px;width:2px;background:var(--muted);right:${100-Math.round(b.b/mV*100)}%"></div></div><div class="brow-v"><span style="color:${good?'#3B6D11':'#A32D2D'};font-weight:700">${b.v}${b.u}</span><span style="color:var(--muted);font-size:9px"> معيار ${b.b}${b.u}</span></div></div>`;}).join('');
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
async function loadPMSReads(){await reload();const reads=(S.pms_reads||[]).slice().reverse().slice(0,10);document.getElementById('pms-reads-body').innerHTML=reads.length?reads.map(r=>`<tr><td style="font-size:9px;color:var(--muted)">${new Date(r.time).toLocaleString('ar-SA')}</td><td style="font-weight:700">${r.intg_name}</td><td style="color:var(--g);font-weight:700">${r.guests_found}</td><td>${pill(r.status==='success'?'نجاح':'خطأ',r.status==='success'?'#EAF3DE':'#FCEBEB',r.status==='success'?'#3B6D11':'#A32D2D')}</td><td><button class="btn sm" onclick="showPMSRead(${r.id})">عرض</button></td></tr>`).join(''):'<tr><td colspan="5" style="text-align:center;padding:12px;color:var(--muted)">لا توجد قراءات</td></tr>';}
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
  document.getElementById('g-body').innerHTML=S.guests.map(g=>`<tr><td style="font-weight:700">${g.unit||'—'}</td><td><div style="font-weight:600">${g.name}</div><div style="font-size:9px;color:var(--muted)">${g.idNum}</div></td><td>${pill((BED_L[g.bed]||g.bed)+(g.extra?` +${g.extra}✦`:''),BED_C[g.bed]+'22',BED_C[g.bed])}</td><td style="font-size:9px">${g.inDate}</td><td style="text-align:center">${g.nights}</td><td style="color:var(--g);font-weight:700">${FR(g.total)}</td><td>${pill(PAY_L[g.pay]||g.pay,PAY_C[g.pay]+'22',PAY_C[g.pay])}</td><td>${pill(g.status==='active'?'مقيم':'غادر',g.status==='active'?'#EAF3DE':'#F8FAFC',g.status==='active'?'#3B6D11':'#94A3B8')}</td><td>${g.status==='active'?`<button class="btn sm" onclick="checkout(${g.id})">مغادرة</button>`:'—'}</td></tr>`).join('')||'<tr><td colspan="9" style="text-align:center;padding:14px;color:var(--muted)">لا يوجد نزلاء</td></tr>';
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
  document.getElementById('pos-devices-list').innerHTML=S.pos_devices.length?S.pos_devices.map(d=>{const ok=!!d.data,dNet=ok?d.data.sales-d.data.refund:0,icon=POS_ICONS[d.dept]||'💳';return`<div class="pdc ${ok?'ok':'wait'}"><div class="pdc-top"><div class="pdc-ic" style="background:${d.color}22;color:${d.color}">${icon}</div><div class="pdc-info"><div class="pdc-name">${d.name}</div><div class="pdc-sub" style="color:${ok?'#3B6D11':'#854F0B'}">${ok?'مُستلم ✓':'في الانتظار'} · ${POS_DEPT[d.dept]||d.dept}${d.serial?` · ${d.serial}`:''}</div></div><div class="pdc-acts"><button class="btn sm" onclick="renamePOSDevice(${d.id})">✏️</button><button class="btn sm" style="color:var(--r)" onclick="deletePOSDevice(${d.id})">🗑️</button></div></div>${ok?`<div class="pdc-minis"><div class="pdcm"><div class="pm-l">المبيعات</div><div class="pm-v" style="color:var(--g)">${FR(d.data.sales)}</div></div><div class="pdcm"><div class="pm-l">الاسترداد</div><div class="pm-v" style="color:var(--r)">(${FR(d.data.refund)})</div></div><div class="pdcm"><div class="pm-l">الصافي</div><div class="pm-v" style="color:var(--p)">${FR(dNet)}</div></div><div class="pdcm"><div class="pm-l">نقداً</div><div class="pm-v">${FR(d.data.breakdown.cash)}</div></div><div class="pdcm"><div class="pm-l">مدى</div><div class="pm-v">${FR(d.data.breakdown.mada)}</div></div><div class="pdcm"><div class="pm-l">${d.data.txCount} معاملة</div><div class="pm-v" style="font-size:9px;color:var(--muted)">${d.data.receivedAt}</div></div></div><div style="margin-top:6px;display:flex;justify-content:flex-end"><button class="btn sm br2" onclick="clearPOSData(${d.id})">مسح</button></div>`:'<div style="font-size:11px;color:var(--muted);padding:3px 0">لم تُدخل موازنة اليوم</div>'}</div>`;}).join(''):'<div style="text-align:center;padding:16px;font-size:12px;color:var(--muted)">لا يوجد أجهزة</div>';
  document.getElementById('pos-entry-list').innerHTML=S.pos_devices.map(d=>`<div class="card" style="border-top:3px solid ${d.color};margin-bottom:8px"><div class="ch"><div class="ch-l"><div class="cico" style="background:${d.color}22;color:${d.color}">${POS_ICONS[d.dept]||'💳'}</div><div><div style="font-size:12px;font-weight:700">${d.name}</div><div style="font-size:10px;color:var(--muted)">${POS_DEPT[d.dept]||d.dept}</div></div></div><div style="display:flex;align-items:center;gap:6px">${d.data?pill('مُستلم ✓ — '+FR(d.data.sales-d.data.refund),'var(--gl)','var(--gd)'):pill('في الانتظار','var(--al)','var(--ad)')}<button class="btn sm" style="background:${d.color};color:#fff;border-color:${d.color}" onclick="togglePOSEntry(${d.id})">${d.data?'تعديل':'إدخال موازنة'}</button></div></div><div class="eform" id="pef-${d.id}"><div style="font-size:11px;color:var(--muted);margin-bottom:8px">بيانات موازنة ${d.name}</div><div class="pm-grid"><div class="fg"><label>إجمالي المبيعات (ر.س)</label><input type="number" min="0" id="pef-sales-${d.id}" placeholder="0.00" value="${d.data?d.data.sales:''}" oninput="calcPOSSum(${d.id})"/></div><div class="fg"><label>الاسترداد (ر.س)</label><input type="number" min="0" id="pef-refund-${d.id}" placeholder="0.00" value="${d.data?d.data.refund:''}"/></div><div class="fg"><label>VAT (ر.س)</label><input type="number" min="0" id="pef-vat-${d.id}" placeholder="0.00"/></div></div><div style="font-size:10px;font-weight:700;color:var(--muted);margin:6px 0 4px">تفصيل طرق الدفع</div><div class="pm-grid">${POS_PAY.map(pm=>`<div class="fg"><label>${POS_PAY_L[pm]} (ر.س)</label><input type="number" min="0" id="pef-${pm}-${d.id}" placeholder="0.00" value="${d.data?d.data.breakdown[pm]||'':''}" oninput="calcPOSSum(${d.id})"/></div>`).join('')}</div><div style="display:flex;align-items:center;justify-content:space-between;padding:6px 9px;background:var(--bg);border-radius:8px;margin-bottom:7px"><span style="font-size:10px;color:var(--muted)">مجموع طرق الدفع</span><span id="pef-sum-${d.id}" style="font-size:13px;font-weight:700;color:var(--p)">0 ر.س</span></div><div class="g2"><div class="fg"><label>عدد المعاملات</label><input type="number" min="0" id="pef-count-${d.id}" placeholder="0" value="${d.data?d.data.txCount:''}"/></div><div class="fg"><label>ملاحظات</label><input id="pef-notes-${d.id}" placeholder="اختياري..." value="${d.data?d.data.notes:''}"/></div></div><div style="display:flex;gap:5px;margin-top:5px"><button class="btn bg2" onclick="savePOSData(${d.id})" style="flex:1">حفظ موازنة ${d.name}</button><button class="btn sm" onclick="togglePOSEntry(${d.id})">إغلاق</button></div></div></div>`).join('')||'<div style="text-align:center;padding:14px;font-size:11px;color:var(--muted)">أضف أجهزة من القسم أعلاه</div>';
  S.pos_devices.forEach(d=>calcPOSSum(d.id));
}

// ── JOURNAL ──────────────────────────────────────────────────
async function addJnl(){const amt=parseFloat(gv('j-amt')||0);if(amt<=0){toast_('أدخل المبلغ',false);return;}const r=await api('/api/journal/add',{drAcc:gv('j-dr-a'),crAcc:gv('j-cr-a'),amount:amt,desc:gv('j-desc')||'قيد يومية',ref:gv('j-ref')});if(r.ok){S.journal_entries.push(r.entry);rJnl();toast_('تم تسجيل القيد ✓');['j-amt','j-desc','j-ref'].forEach(id=>{const e=document.getElementById(id);if(e)e.value='';});}}
function rJnl(){const tot=S.journal_entries.reduce((a,e)=>a+e.amount,0);ss('j-dr',FR(tot));ss('j-cr',FR(tot));ss('j-cnt',S.journal_entries.length);const jbc=document.getElementById('j-bal-c');if(jbc)jbc.className='mc mg';ss('j-bal','متوازن ✓');document.getElementById('j-body').innerHTML=[...S.journal_entries].reverse().map(e=>`<tr><td style="font-size:9px;color:var(--muted)">${e.time}</td><td>${e.desc}</td><td style="font-size:9px;color:var(--muted)">${e.ref||'—'}</td><td style="text-align:left"><span style="color:var(--g);font-weight:700">${FR(e.amount)}</span><div style="font-size:9px;color:var(--gd)">${ACC_L[e.drAcc]||e.drAcc}</div></td><td style="text-align:left"><span style="color:var(--p);font-weight:700">${FR(e.amount)}</span><div style="font-size:9px;color:var(--pd)">${ACC_L[e.crAcc]||e.crAcc}</div></td></tr>`).join('')||'<tr><td colspan="5" style="text-align:center;padding:14px;color:var(--muted)">لا توجد قيود</td></tr>';document.getElementById('j-foot').innerHTML=`<tr><td colspan="3" style="padding:6px 8px">الإجمالي</td><td style="text-align:left;color:var(--g)">${FR(tot)}</td><td style="text-align:left;color:var(--p)">${FR(tot)}</td></tr>`;}

// ── TRIAL ────────────────────────────────────────────────────
function rTrial(){const ACCS={cash:'النقدية',bank:'البنك',receivable:'ذمم مدينة',room_rev:'إيرادات الغرف',svc_rev:'إيرادات الخدمات',util_exp:'كهرباء',maint_exp:'صيانة',supply_exp:'لوازم',payable:'ذمم دائنة',vat_payable:'VAT مستحق'};const tots={};Object.keys(ACCS).forEach(k=>{tots[k]={dr:0,cr:0};});S.journal_entries.forEach(e=>{if(tots[e.drAcc])tots[e.drAcc].dr+=e.amount;if(tots[e.crAcc])tots[e.crAcc].cr+=e.amount;});const tDr=Object.values(tots).reduce((a,v)=>a+v.dr,0),tCr=Object.values(tots).reduce((a,v)=>a+v.cr,0);const bal=Math.round(tDr-tCr),ok=Math.abs(bal)<1;ss('tb-dr',FR(tDr));ss('tb-cr',FR(tCr));const tbc=document.getElementById('tb-bal-c');if(tbc)tbc.className='mc '+(ok?'mg':'mr');ss('tb-bal',ok?'متوازن ✓':FR(Math.abs(bal))+' فرق');document.getElementById('tb-body').innerHTML=Object.entries(ACCS).filter(([k])=>tots[k]&&(tots[k].dr>0||tots[k].cr>0)).map(([k,name])=>{const t=tots[k],b=t.dr-t.cr;return`<tr><td style="font-weight:700">${name}</td><td style="text-align:left;color:var(--g);font-weight:700">${t.dr>0?FR(t.dr):'—'}</td><td style="text-align:left;color:var(--p);font-weight:700">${t.cr>0?FR(t.cr):'—'}</td><td style="text-align:left"><span style="color:${b>0?'#3B6D11':b<0?'#A32D2D':'#94A3B8'};font-weight:700">${FR(Math.abs(b))} ${b>0?'م':b<0?'د':''}</span></td></tr>`;}).join('');document.getElementById('tb-foot').innerHTML=`<tr><td style="padding:6px 8px">الإجمالي</td><td style="text-align:left;color:var(--g)">${FR(tDr)}</td><td style="text-align:left;color:var(--p)">${FR(tCr)}</td><td style="color:${ok?'#3B6D11':'#A32D2D'}">${ok?'متوازن ✓':FR(Math.abs(bal))}</td></tr>`;}

// ── P&L ──────────────────────────────────────────────────────
function rPL(){const grev=S.guests.reduce((a,g)=>a+g.total,0),srv=S.services.reduce((a,s)=>a+s.amount,0),tRev=grev+srv;const tExp=S.invoices.reduce((a,i)=>a+i.base,0),gross=tRev-tExp,net=gross,margin=tRev?Math.round(net/tRev*100):0;ss('pl-rev',FR(tRev));ss('pl-cost',FR(tExp));const pg=document.getElementById('pl-gross');if(pg){pg.textContent=FR(gross);pg.style.color=gross>=0?'#185FA5':'#A32D2D';}const pn=document.getElementById('pl-net');if(pn){pn.textContent=FR(net);pn.style.color=net>=0?'#534AB7':'#A32D2D';}document.getElementById('pl-det').innerHTML=`<div style="font-size:11px;font-weight:700;color:var(--gd);margin-bottom:5px;padding-bottom:4px;border-bottom:2px solid var(--g)">الإيرادات</div><div class="dr"><span style="color:var(--muted)">إيرادات الغرف (${S.guests.length} نزيل)</span><span style="color:var(--g);font-weight:700">${FR(grev)}</span></div><div class="dr"><span style="color:var(--muted)">إيرادات الخدمات (${S.services.length} خدمة)</span><span style="color:var(--g);font-weight:700">${FR(srv)}</span></div><div class="dr tot"><span>إجمالي الإيرادات</span><span style="color:var(--g)">${FR(tRev)}</span></div><div style="font-size:11px;font-weight:700;color:var(--rd);margin:9px 0 5px;padding-bottom:4px;border-bottom:2px solid var(--r)">التكاليف</div>${S.invoices.map(i=>`<div class="dr"><span style="color:var(--muted)">${i.supName} — ${i.num}</span><span style="color:var(--r)">(${FR(i.base)})</span></div>`).join('')||'<div class="dr"><span style="color:var(--muted)">لا توجد فواتير</span><span style="color:var(--g)">✓</span></div>'}<div class="dr tot"><span>إجمالي التكاليف</span><span style="color:var(--r)">(${FR(tExp)})</span></div><div class="dr" style="border-top:2px solid var(--pl);margin-top:8px;padding-top:9px"><span style="font-size:14px;font-weight:700">الصافي النهائي</span><span style="font-size:18px;font-weight:700;color:${net>=0?'#534AB7':'#A32D2D'}">${FR(net)}</span></div><div class="dr"><span style="color:var(--muted)">هامش الربح</span><span style="font-weight:700;color:${margin>=0?'#534AB7':'#A32D2D'}">${margin}%</span></div>`;}

// ── RECEIVABLES ──────────────────────────────────────────────
async function addRecv(){const name=gv('rec-n').trim();if(!name){toast_('أدخل الاسم',false);return;}const amt=parseFloat(gv('rec-a')||0);if(amt<=0){toast_('أدخل المبلغ',false);return;}const r=await api('/api/receivables/add',{name,ref:gv('rec-r'),type:gv('rec-t'),amount:amt,due:gv('rec-d')});if(r.ok){S.receivables.push(r.receivable);rRecv();toast_('تم تسجيل الذمة ✓');['rec-n','rec-a','rec-r'].forEach(id=>{const e=document.getElementById(id);if(e)e.value='';});}}
async function collectRecv(id){const r=await api('/api/receivables/collect',{id});if(r.ok){const rec=S.receivables.find(x=>x.id===id);if(rec)rec.status='collected';await reload();rRecv();toast_('تم التحصيل + قيد محاسبي ✓');}}
function rRecv(){const tot=S.receivables.reduce((a,r)=>a+r.amount,0),ov=S.receivables.filter(r=>r.status==='overdue').reduce((a,r)=>a+r.amount,0);ss('rec-tot',FR(tot));ss('rec-pend',FR(S.receivables.filter(r=>r.status==='pending').reduce((a,r)=>a+r.amount,0)));ss('rec-over',FR(ov));ss('rec-col',FR(S.receivables.filter(r=>r.status==='collected').reduce((a,r)=>a+r.amount,0)));const TL={room:'إيجار',svc:'خدمات',corp:'شركة',other:'أخرى'};document.getElementById('rec-body').innerHTML=S.receivables.map(r=>`<tr><td style="font-weight:700">${r.name}</td><td style="font-size:9px">${r.ref||'—'}</td><td>${pill(TL[r.type]||r.type,'var(--pl)','var(--p)')}</td><td style="text-align:left;color:var(--p);font-weight:700">${FR(r.amount)}</td><td style="font-size:9px">${r.due}</td><td>${pill(r.status==='overdue'?'متأخرة':r.status==='collected'?'محصّلة':'معلقة',r.status==='overdue'?'#FCEBEB':r.status==='collected'?'#EAF3DE':'#FAEEDA',r.status==='overdue'?'#A32D2D':r.status==='collected'?'#3B6D11':'#854F0B')}</td><td>${r.status!=='collected'?`<button class="btn sm bg2" onclick="collectRecv(${r.id})">تحصيل</button>`:'✓'}</td></tr>`).join('');document.getElementById('rec-foot').innerHTML=`<tr><td colspan="3" style="padding:6px 8px">الإجمالي</td><td style="text-align:left;color:var(--p)">${FR(tot)}</td><td colspan="2"></td></tr>`;}

// ── PAYABLES ─────────────────────────────────────────────────
async function payInv(id){const r=await api('/api/invoices/pay',{id});if(r.ok){await reload();rPaybl();rInv();rJnl();toast_('تم الدفع + قيد محاسبي ✓');}}
function rPaybl(){const pend=S.invoices.filter(i=>i.status==='pending'),paid=S.invoices.filter(i=>i.status==='paid');ss('pay-tot',FR(pend.reduce((a,i)=>a+i.total,0)));ss('pay-pend',FR(pend.reduce((a,i)=>a+i.total,0)));ss('pay-late',FR(0));ss('pay-paid',FR(paid.reduce((a,i)=>a+i.total,0)));document.getElementById('pay-body').innerHTML=S.invoices.map(i=>`<tr><td style="font-weight:700">${i.supName}</td><td style="font-size:9px">${i.num}</td><td style="text-align:left;color:var(--r);font-weight:700">${FR(i.total)}</td><td style="font-size:9px">${i.due}</td><td>${pill(i.status==='paid'?'مدفوعة':'معلقة',i.status==='paid'?'#EAF3DE':'#FCEBEB',i.status==='paid'?'#3B6D11':'#A32D2D')}</td><td>${i.status==='pending'?`<button class="btn sm bg2" onclick="payInv(${i.id})">دفع</button>`:'✓'}</td></tr>`).join('');document.getElementById('pay-foot').innerHTML=`<tr><td colspan="2" style="padding:6px 8px">المعلقة</td><td style="text-align:left;color:var(--r)">${FR(pend.reduce((a,i)=>a+i.total,0))}</td><td colspan="2"></td></tr>`;}

// ── SUPPLIERS ────────────────────────────────────────────────
async function addSup(){const name=gv('sup-n').trim();if(!name){toast_('أدخل اسم المورّد',false);return;}const r=await api('/api/suppliers/add',{name,type:gv('sup-t'),phone:gv('sup-ph'),iban:gv('sup-ib'),cr:gv('sup-cr'),terms:gv('sup-tm')});if(r.ok){S.suppliers.push(r.supplier);rSup();refreshInvSel();toast_('تم إضافة المورّد ✓');['sup-n','sup-ph','sup-ib','sup-cr'].forEach(id=>{const e=document.getElementById(id);if(e)e.value='';});}}
function rSup(){const pendByS={};S.invoices.filter(i=>i.status==='pending').forEach(i=>{pendByS[i.supId]=(pendByS[i.supId]||0)+i.total;});const due=Object.values(pendByS).reduce((a,v)=>a+v,0);ss('sup-cnt',S.suppliers.length);ss('sup-due',FR(due));ss('sup-inv-cnt',S.invoices.length);ss('sup-paid',FR(S.invoices.filter(i=>i.status==='paid').reduce((a,i)=>a+i.total,0)));const TL={cash:'نقداً','30':'30 يوم','60':'60 يوم',monthly:'شهري'};document.getElementById('sup-list').innerHTML=S.suppliers.length?S.suppliers.map(s=>`<div class="sup-row"><div class="sup-av" style="background:${s.color}22;color:${s.color}">${s.name.charAt(0)}</div><div style="flex:1;min-width:0"><div style="font-size:12px;font-weight:700;color:var(--text)">${s.name}</div><div style="font-size:10px;color:var(--muted);margin-top:2px">${pill(SUP_L[s.type]||s.type,SUP_C[s.type]+'22',SUP_C[s.type]||'#888')} ${s.phone||''} ${TL[s.terms]||s.terms}</div>${s.iban?`<div style="font-size:9px;color:var(--muted)">IBAN: ${s.iban.substring(0,14)}...</div>`:''}</div><div style="text-align:left;flex-shrink:0"><div style="font-size:13px;font-weight:700;color:${(pendByS[s.id]||0)>0?'#A32D2D':'#3B6D11'}">${FR(pendByS[s.id]||0)}</div><div style="font-size:9px;color:var(--muted)">${(pendByS[s.id]||0)>0?'مستحق':'لا ديون'}</div></div></div>`).join(''):'<div style="text-align:center;padding:16px;font-size:12px;color:var(--muted)">لا يوجد موردون</div>';}
function refreshInvSel(){const sel=document.getElementById('inv-sup');if(sel)sel.innerHTML=S.suppliers.map(s=>`<option value="${s.id}">${s.name}</option>`).join('');}

// ── INVOICES ─────────────────────────────────────────────────
function calcInv(){const base=parseFloat(gv('inv-base')||0),vatOn=document.getElementById('inv-vat')?.checked,vat=vatOn?Math.round(base*0.15):0;const va=document.getElementById('inv-vat-a');if(va)va.textContent=FR(vat);const it=document.getElementById('inv-tot');if(it)it.textContent=FR(base+vat);}
async function addInv(){const base=parseFloat(gv('inv-base')||0);if(base<=0){toast_('أدخل المبلغ',false);return;}const supId=parseInt(gv('inv-sup')),sup=S.suppliers.find(s=>s.id===supId)||{name:'مورّد'};const vatOn=document.getElementById('inv-vat')?.checked;const r=await api('/api/invoices/add',{supId,supName:sup.name,num:gv('inv-num')||'INV-'+Date.now().toString().slice(-4),base,vat:vatOn,date:gv('inv-date'),due:gv('inv-due')});if(r.ok){S.invoices.push(r.invoice);await reload();rInv();rPaybl();rJnl();rDash();toast_('تم تسجيل الفاتورة + قيد محاسبي ✓');['inv-base','inv-num'].forEach(id=>{const e=document.getElementById(id);if(e)e.value='';});}}
function rInv(){const pend=S.invoices.filter(i=>i.status==='pending'),paid=S.invoices.filter(i=>i.status==='paid');ss('inv-pc',pend.length);ss('inv-pa',FR(pend.reduce((a,i)=>a+i.total,0)));ss('inv-dc',paid.length);ss('inv-da',FR(paid.reduce((a,i)=>a+i.total,0)));document.getElementById('inv-body').innerHTML=S.invoices.map(i=>`<tr><td style="font-weight:700">${i.supName}</td><td style="font-size:9px">${i.num}</td><td style="text-align:left">${F(i.base)}</td><td style="text-align:left;color:var(--a)">${i.vat>0?FR(i.vat):'—'}</td><td style="text-align:left;color:var(--r);font-weight:700">${FR(i.total)}</td><td style="font-size:9px">${i.due}</td><td>${pill(i.status==='paid'?'مدفوعة':'معلقة',i.status==='paid'?'#EAF3DE':'#FCEBEB',i.status==='paid'?'#3B6D11':'#A32D2D')}</td><td>${i.status==='pending'?`<button class="btn sm bg2" onclick="payInv(${i.id})">دفع</button>`:'✓'}</td></tr>`).join('');document.getElementById('inv-foot').innerHTML=`<tr><td colspan="4" style="padding:6px 8px">الإجمالي</td><td style="text-align:left;color:var(--r)">${FR(S.invoices.reduce((a,i)=>a+i.total,0))}</td><td colspan="2"></td></tr>`;}

// ── BUDGET HIERARCHICAL ──────────────────────────────────────
function rBudget(){
  const lines=S.budget_lines||[];const roots=lines.filter(b=>!b.parent_id);
  const getChildren=(pid)=>lines.filter(b=>String(b.parent_id)===String(pid));
  const tRevPlan=roots.filter(b=>b.type==='rev').reduce((a,b)=>a+b.planned,0);
  const tExpPlan=roots.filter(b=>b.type==='exp').reduce((a,b)=>a+b.planned,0);
  const planNet=tRevPlan-tExpPlan,actNet=sysIn()-sysOut(),diff=actNet-planNet,pct=planNet?Math.round(actNet/planNet*100):0;
  const el_rp=document.getElementById('bgt-rev-plan');if(el_rp)el_rp.textContent=FR(tRevPlan);
  const el_ep=document.getElementById('bgt-exp-plan');if(el_ep)el_ep.textContent=FR(tExpPlan);
  const de=document.getElementById('bgt-diff');if(de){de.textContent=(diff>=0?'+':'')+FR(diff);de.style.color=diff>=0?'#3B6D11':'#A32D2D';}
  const dc=document.getElementById('bgt-diff-c');if(dc)dc.className='mc '+(diff>=0?'mg':'mr');
  const pe=document.getElementById('bgt-pct');if(pe)pe.textContent=pct+'%';
  function renderNode(b,depth){
    depth=depth||0;const kids=getChildren(b.id);const hasKids=kids.length>0;
    const indent=depth*16;const isRoot=depth===0;
    const totPlanned=b.planned+(hasKids?kids.reduce((a,k)=>a+k.planned,0):0);
    const totActual=b.actual+(hasKids?kids.reduce((a,k)=>a+k.actual,0):0);
    const pctA=totPlanned?Math.round(totActual/totPlanned*100):0;
    const over=b.type==='exp'?(totActual>totPlanned):(totActual<totPlanned);
    const bgMain=isRoot?(b.type==='rev'?'#F0FDF4':'#FEF2F2'):'#F1F5F9';
    const borderC=isRoot?(b.type==='rev'?'#6EE7B7':'#FCA5A5'):'#E2E8F0';
    const barColor=over?'#DC2626':b.type==='rev'?'#047857':'#D97706';
    return`<div style="margin-bottom:5px"><div style="display:flex;align-items:center;gap:6px;padding:8px 10px;background:${bgMain};border-radius:9px;border:1.5px solid ${borderC};margin-right:${indent}px;flex-wrap:wrap"><span style="font-size:10px;color:var(--muted);cursor:pointer;user-select:none;min-width:14px;font-weight:700" onclick="toggleBgtNode(${b.id})">${hasKids?'▶':' '}</span><span style="font-size:9px;padding:3px 8px;border-radius:20px;font-weight:700;flex-shrink:0;background:${b.type==='rev'?'#EAF3DE':'#FCEBEB'};color:${b.type==='rev'?'#3B6D11':'#A32D2D'}">${b.type==='rev'?'إيراد':'مصروف'}</span><input value="${b.name}" style="flex:1;min-width:90px;border:1.5px solid var(--border);border-radius:7px;padding:4px 7px;font-size:${isRoot?'12':'11'}px;font-weight:${isRoot?'700':'500'};background:${bgMain};color:var(--text)" onchange="renameBgt(${b.id},this.value)"/><span style="font-size:10px;color:var(--muted)">مخطط</span><input type="number" value="${b.planned}" min="0" style="width:82px;border:1.5px solid var(--border);border-radius:7px;padding:4px 7px;font-size:11px;background:${bgMain};color:var(--text)" onchange="updateBgt(${b.id},'planned',this.value)"/><span style="font-size:10px;color:var(--muted)">فعلي</span><input type="number" value="${b.actual}" min="0" style="width:82px;border:1.5px solid var(--border);border-radius:7px;padding:4px 7px;font-size:11px;background:${bgMain};color:var(--text)" onchange="updateBgt(${b.id},'actual',this.value)"/>${hasKids?`<span style="font-size:10px;font-weight:700;color:${b.type==='rev'?'#3B6D11':'#A32D2D'}">${F(totActual)}/${F(totPlanned)}</span>`:''}<div style="display:flex;gap:3px;flex-shrink:0"><button style="font-size:10px;padding:3px 8px;border:none;border-radius:7px;background:var(--pl);color:var(--p);cursor:pointer;font-weight:600" onclick="addBgtChild(${b.id},'${b.type}')">+ فرعي</button><button style="font-size:10px;padding:3px 8px;border:none;border-radius:7px;background:var(--rl);color:var(--r);cursor:pointer;font-weight:600" onclick="deleteBgt(${b.id})">حذف</button></div><div style="flex-basis:100%;display:flex;align-items:center;gap:6px;margin-top:4px"><div style="flex:1;background:var(--border);border-radius:4px;height:6px;overflow:hidden"><div style="height:6px;border-radius:4px;width:${Math.min(pctA,100)}%;background:${barColor};transition:width .5s"></div></div><span style="font-size:9px;color:${barColor};font-weight:700">${pctA}%</span></div></div><div id="bgt-kids-${b.id}">${kids.map(k=>renderNode(k,depth+1)).join('')}</div></div>`;
  }
  const tree=document.getElementById('bgt-tree');if(tree)tree.innerHTML=roots.length?roots.map(b=>renderNode(b)).join(''):'<div style="text-align:center;padding:16px;font-size:12px;color:var(--muted)">لا توجد بنود — اضغط + إيراد رئيسي أو + مصروف رئيسي</div>';
  const allLeaves=lines.filter(b=>!getChildren(b.id).length);const maxV=Math.max(...allLeaves.map(b=>Math.max(b.planned,b.actual||0)),1);
  const ch=document.getElementById('bgt-chart');if(ch)ch.innerHTML=allLeaves.map(b=>{const av=b.actual||0,pt2=b.planned?Math.round(av/b.planned*100):0,ov=b.type==='exp'?(av>b.planned):(av<b.planned);return`<div class="brow"><div class="brow-l">${b.name}</div><div class="brow-t"><div class="brow-f" style="width:${Math.round(Math.min(av,b.planned*1.4)/Math.max(b.planned*1.4,1)*100)}%;background:${ov?'#A32D2D':b.type==='rev'?'#3B6D11':'#854F0B'}"></div></div><div class="brow-v"><span style="color:${ov?'#A32D2D':'#3B6D11'};font-weight:700">${F(av)}</span><span style="color:var(--muted);font-size:9px"> / ${F(b.planned)} (${pt2}%)</span></div></div>`;}).join('');
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
function rCashflow(){const si=sysIn(),so=sysOut(),net=si-so;ss('cf-in',FR(si));ss('cf-out',FR(so));ss('cf-end',FR(Math.round(si*1.8)));const cfn=document.getElementById('cf-net');if(cfn){cfn.textContent=FR(net);cfn.style.color=net>=0?'#185FA5':'#A32D2D';}document.getElementById('cf-det').innerHTML=`<div style="font-size:11px;font-weight:700;color:var(--gd);margin-bottom:5px;padding-bottom:4px;border-bottom:2px solid var(--g)">التدفق الداخل</div><div class="dr"><span style="color:var(--muted)">إيرادات الغرف</span><span style="color:var(--g);font-weight:700">${FR(S.guests.reduce((a,g)=>a+g.total,0))}</span></div><div class="dr"><span style="color:var(--muted)">إيرادات الخدمات</span><span style="color:var(--g);font-weight:700">${FR(S.services.reduce((a,s)=>a+s.amount,0))}</span></div><div class="dr tot"><span>إجمالي الداخل</span><span style="color:var(--g)">${FR(si)}</span></div><div style="font-size:11px;font-weight:700;color:var(--rd);margin:8px 0 5px;padding-bottom:4px;border-bottom:2px solid var(--r)">التدفق الخارج</div>${S.invoices.map(i=>`<div class="dr"><span style="color:var(--muted)">${i.supName} — ${i.num}</span><span style="color:var(--r)">(${FR(i.total)})</span></div>`).join('')||'<div class="dr"><span style="color:var(--muted)">لا توجد مدفوعات</span><span style="color:var(--g)">✓</span></div>'}<div class="dr tot"><span>إجمالي الخارج</span><span style="color:var(--r)">(${FR(so)})</span></div><div class="dr" style="border-top:2px solid var(--pl);margin-top:8px;padding-top:9px"><span style="font-size:14px;font-weight:700">صافي التدفق</span><span style="font-size:17px;font-weight:700;color:${net>=0?'#3B6D11':'#A32D2D'}">${FR(net)}</span></div>`;document.getElementById('cf-weeks').innerHTML=['الأسبوع القادم','بعد أسبوعين','بعد 3 أسابيع','نهاية الشهر'].map((w,i)=>{const p=Math.round(net*(1+i*0.1));return`<div class="brow"><div class="brow-l">${w}</div><div class="brow-t"><div class="brow-f" style="width:${Math.min(100,Math.round(Math.abs(p)/Math.max(si,1)*100))}%;background:${p>=0?'#3B6D11':'#A32D2D'}"></div></div><div class="brow-v" style="color:${p>=0?'#3B6D11':'#A32D2D'};font-weight:700">${p>=0?'+':''}${FR(p)}</div></div>`;}).join('');}

// ── MATCH ─────────────────────────────────────────────────────
function rMatchPage(){}
async function runMatch(){
  const pNet=posNet(),si=sysIn(),sysManual=parseFloat(document.getElementById('m-sys-in')?.value||0),sysTotal=sysManual>0?sysManual:si;
  const rawDiff=pNet-sysTotal,absDiff=Math.abs(rawDiff),pct=sysTotal>0?absDiff/sysTotal*100:0;
  const status=absDiff<1?'MATCHED':pct<=2?'PARTIAL':'DIFF';const sign=rawDiff>0?'+':rawDiff<0?'-':'';
  const stC={MATCHED:'#3B6D11',PARTIAL:'#854F0B',DIFF:rawDiff>0?'#3B6D11':'#A32D2D'}[status];
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
    if(card)card.style.borderColor=subState.plan===p?'#3B6D11':p==='pro'?'#185FA5':'#E2E8F0';
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
      <div class="mc ${net>=0?'mb':'mr'}"><div class="ml">الصافي</div><div class="mv" style="color:${net>=0?'#185FA5':'#A32D2D'}">${FR(net)}</div></div>
    </div>
    <div class="dr"><span style="color:var(--muted)">النزلاء اليوم</span><span style="font-weight:700">${S.guests.length} نزيل (${S.guests.filter(g=>g.status==='active').length} مقيم)</span></div>
    <div class="dr"><span style="color:var(--muted)">إيرادات الخدمات</span><span style="color:var(--u);font-weight:700">${FR(S.services.reduce((a,s)=>a+s.amount,0))}</span></div>
    <div class="dr"><span style="color:var(--muted)">أجهزة POS المُستلمة</span><span style="font-weight:700">${S.pos_devices.filter(d=>d.data).length}/${S.pos_devices.length} — ${FR(pNet)}</span></div>
    <div class="dr"><span style="color:var(--muted)">فواتير موردين معلقة</span><span style="color:var(--r);font-weight:700">${S.invoices.filter(i=>i.status==='pending').length} فاتورة — ${FR(S.invoices.filter(i=>i.status==='pending').reduce((a,i)=>a+i.total,0))}</span></div>
    ${marketData&&marketData.our_adr?`<div class="dr"><span style="color:var(--muted)">ADR مقارنة بالسوق</span><span style="color:${marketData.adr_diff>=0?'#3B6D11':'#A32D2D'};font-weight:700">${FR(marketData.our_adr)} (السوق: ${FR(marketData.market_adr)})</span></div>`:''}
    <div class="dr tot" style="margin-top:8px"><span style="font-size:13px">الصافي النهائي</span><span style="font-size:17px;color:${net>=0?'#3B6D11':'#A32D2D'}">${FR(net)}</span></div>
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
    if(badge)badge.innerHTML=`<span style="font-size:10px;padding:3px 9px;border-radius:20px;background:${src.includes('web')?'#EAF3DE':'#E6F1FB'};color:${src.includes('web')?'#3B6D11':'#185FA5'};font-weight:700">${src.includes('web')&&src.includes('claude')?'✅ بحث ويب + تحليل Claude':'📊 بيانات مدمجة'}</span>`;
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
  document.getElementById('g-body').innerHTML=S.guests.map(g=>`<tr><td style="font-weight:700">${g.unit||'—'}</td><td><div style="font-weight:600">${g.name}</div><div style="font-size:9px;color:var(--muted)">${g.idNum}</div></td><td>${pill((BED_L[g.bed]||g.bed)+(g.extra?` +${g.extra}✦`:''),BED_C[g.bed]+'22',BED_C[g.bed])}</td><td style="font-size:9px">${g.inDate}</td><td style="text-align:center">${g.nights}</td><td style="color:var(--g);font-weight:700">${FR(g.total)}</td><td>${pill(PAY_L[g.pay]||g.pay,PAY_C[g.pay]+'22',PAY_C[g.pay])}</td><td>${pill(g.status==='active'?'مقيم':'غادر',g.status==='active'?'#EAF3DE':'#F8FAFC',g.status==='active'?'#3B6D11':'#94A3B8')}</td><td>${g.status==='active'?`<button class="btn sm" onclick="checkout(${g.id})">مغادرة</button>`:'—'}</td></tr>`).join('')||'<tr><td colspan="9" style="text-align:center;padding:14px;color:var(--muted)">لا يوجد نزلاء</td></tr>';
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
    <label style="display:flex;align-items:center;gap:8px;padding:9px 11px;border-radius:9px;background:var(--bg);border:1.5px solid ${m.enabled?'#3B6D11':'#E2E8F0'};cursor:pointer;transition:border-color .1s" onclick="togglePay(${i})">
      <span style="font-size:18px">${m.icon||'💳'}</span>
      <div style="flex:1">
        <div style="font-size:11px;font-weight:700;color:var(--text)">${m.label}</div>
        <div style="font-size:9px;color:${m.enabled?'#3B6D11':'#64748B'};margin-top:1px">${m.enabled?'مفعّل ✓':'معطّل'}</div>
      </div>
      <div style="width:18px;height:18px;border-radius:50%;background:${m.enabled?'#3B6D11':'#E2E8F0'};display:flex;align-items:center;justify-content:center;font-size:10px;color:#fff;flex-shrink:0">${m.enabled?'✓':''}</div>
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
def start_server():
    server = HTTPServer(("127.0.0.1", PORT), Handler)
    logging.info(f"Server started on port {PORT}")
    server.serve_forever()

def open_browser():
    time.sleep(1.5)
    webbrowser.open(f"http://127.0.0.1:{PORT}")

if __name__ == "__main__":
    print("=" * 55)
    print("  نظام إدارة الفندق والشقق المخدومة — v2.0")
    print("=" * 55)
    print(f"  الخادم يبدأ على: http://127.0.0.1:{PORT}")
    print(f"  البيانات محفوظة في: {DATA_DIR}")
    print(f"  السجلات في: {LOG_DIR}")
    print("  اضغط Ctrl+C للإيقاف")
    print("=" * 55)
    t = threading.Thread(target=open_browser, daemon=True)
    t.start()
    try:
        start_server()
    except KeyboardInterrupt:
        print("\n  تم إيقاف النظام بنجاح.")
    except OSError as e:
        if "Address already in use" in str(e):
            print(f"\n  المنفذ {PORT} مشغول — جرّب تغييره في الكود.")
        else:
            raise
