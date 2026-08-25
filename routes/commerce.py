#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
routes/commerce.py — الباقات والدفع والتذاكر وكتالوج الوحدات
مُستخرَج ضمن تقسيم ملف المسارات الكبير لتسهيل الصيانة.
"""
import secrets
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, Request
from fastapi.responses import (
    JSONResponse,
)

from app_core import (
    require_client, require_admin,
)

router = APIRouter()

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


@router.get("/api/packages")
async def public_packages(request: Request):
    """عام — يقرأه صفحة الباقات لعرض الأسعار الحيّة (لا يتطلب تسجيل دخول)."""
    store = request.app.state.store
    data = store.get_admin_data()
    return {"success": True, "packages": _merge_packages(data.get("public_packages", []))}


@router.put("/api/admin/packages")
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
    store = request.app.state.store
    data = store.get_admin_data()
    data["public_packages"] = cleaned
    store.save_admin_data(data)
    return {"success": True, "packages": _merge_packages(cleaned)}


@router.get("/api/admin/stats")
async def admin_stats_v2(request: Request, _=Depends(require_admin)):
    store = request.app.state.store
    clients = store.get_all_clients()
    active = sum(1 for c in clients if c.get("status") == "active")
    trial = sum(1 for c in clients if c.get("status") == "trial")
    paid = sum(1 for c in clients if c.get("plan") not in (None, "", "trial"))
    data = store.get_admin_data()
    total_revenue = sum(float(p.get("amount", 0)) for p in data.get("payments", []))
    return {"success": True, "stats": {"total_clients": len(clients), "active_clients": active, "trial_clients": trial, "paid_clients": paid, "total_revenue": total_revenue}}


# ──────────────────────────────────────────────────────────────
#  Invoice pay endpoint
# ──────────────────────────────────────────────────────────────
@router.post("/api/invoices/{invoice_id}/pay")
async def pay_invoice(invoice_id: str, request: Request, session=Depends(require_client)):
    store = request.app.state.store
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
@router.get("/api/tickets")
async def get_tickets(request: Request, session=Depends(require_client)):
    store = request.app.state.store
    cid = session["client_id"]
    data = store.get_admin_data()
    tickets = [t for t in data.get("tickets", []) if t.get("client_id") == cid]
    return {"success": True, "tickets": tickets}


@router.post("/api/tickets")
async def create_ticket(request: Request, session=Depends(require_client)):
    body = await request.json()
    store = request.app.state.store
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


@router.get("/api/modules/catalog")
async def modules_catalog():
    return {"success": True, "modules": MODULE_CATALOG, "plans": PLANS_CATALOG}


@router.get("/api/modules/client")
async def client_modules(request: Request, session=Depends(require_client)):
    store = request.app.state.store
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


