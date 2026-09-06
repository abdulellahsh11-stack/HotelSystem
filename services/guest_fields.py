#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
services/guest_fields.py — الحقول الإلزامية في تسجيل الضيف، لكل منشأة.

نموذج التسجيل يبدأ فارغاً؛ ومالك المنشأة يقرّر أيّ الحقول إلزامي. القرار
يُحفظ في `clients.settings["guest_required_fields"]` ويُفرَض على الخادم —
فلا تكفي واجهةٌ تتحقّق، ولا يُحفظ ضيفٌ ينقصه حقلٌ إلزامي.

الحقول المعروفة مضبوطة (لا نصّ حر): مفتاحٌ غير معروف في قائمة الإلزام يعني
خطأً مطبعياً يمنع الحفظ أو يسمح به بصمت — الأسلم إسقاطه.
"""
from __future__ import annotations

# مفتاح الحقل كما يصل في جسم POST /api/guests → مسمّياته (عربي/إنجليزي).
GUEST_FIELDS: dict[str, dict] = {
    "full_name":    {"ar": "الاسم الكامل",       "en": "Full name"},
    "id_type":      {"ar": "نوع الإثبات",        "en": "ID type"},
    "id_number":    {"ar": "رقم الهوية/الإقامة", "en": "ID number"},
    "absher_phone": {"ar": "الجوال",             "en": "Mobile"},
    "birth_date":   {"ar": "تاريخ الميلاد",      "en": "Date of birth"},
    "nationality":  {"ar": "الجنسية",            "en": "Nationality"},
    "email":        {"ar": "البريد الإلكتروني",  "en": "Email"},
    "address":      {"ar": "العنوان",            "en": "Address"},
}

# الافتراضي الأدنى: الاسم والإثبات. الجوال وغيره يفعّلهما المالك عند الحاجة —
# فلا يُكسَر تسجيلٌ قائمٌ لا يحملهما.
DEFAULT_REQUIRED: list[str] = ["full_name", "id_number"]


def sanitize(fields) -> list[str]:
    """يُبقي المعروف فقط، بلا تكرار وبترتيب الإدخال."""
    seen: set[str] = set()
    out: list[str] = []
    for f in fields or []:
        if f in GUEST_FIELDS and f not in seen:
            seen.add(f)
            out.append(f)
    return out


def get_required(client: dict | None) -> list[str]:
    """الحقول الإلزامية لهذه المنشأة — من إعداداتها، وإلا الافتراضي."""
    settings = (client or {}).get("settings") or {}
    val = settings.get("guest_required_fields")
    if isinstance(val, list):
        return sanitize(val)
    return list(DEFAULT_REQUIRED)


def missing_required(data: dict | None, required: list[str]) -> list[str]:
    """الحقول الإلزامية الفارغة أو الغائبة في جسم الطلب."""
    d = data or {}
    return [f for f in required if not str(d.get(f) or "").strip()]
