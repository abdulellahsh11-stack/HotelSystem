#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
services/i18n.py — طبقة تعدّد اللغة (عربي/إنجليزي) على الخادم.

مبدأ واحد: اللغة تُقرَّر على الخادم وتُقدَّم مع النصوص، فلا تتناثر الترجمة
في الواجهة ولا تتباعد نسختان. العربية هي الأصل والاتجاه RTL، والإنجليزية
LTR. أي لغة غير معروفة تعود إلى العربية (فشلٌ آمن لا صفحةٌ فارغة).

الحزم (bundles) ملفات JSON تحت static/dheuof/i18n/؛ تُقرأ مرّة وتُخبَّأ.
"""
from __future__ import annotations

import json
import os
from functools import lru_cache

DEFAULT_LANG = "ar"
SUPPORTED = ("ar", "en")
COOKIE_NAME = "lang"

_BUNDLE_DIR = os.path.join("static", "dheuof", "i18n")


def normalize(lang: str | None) -> str:
    """يُعيد لغةً مدعومة دائماً — أي قيمة غريبة تعود إلى الافتراضي."""
    if not lang:
        return DEFAULT_LANG
    code = str(lang).strip().lower()[:2]
    return code if code in SUPPORTED else DEFAULT_LANG


def direction(lang: str | None) -> str:
    """اتجاه الكتابة: العربية RTL، وما عداها LTR."""
    return "rtl" if normalize(lang) == "ar" else "ltr"


def resolve(request) -> str:
    """
    لغة الطلب: من ?lang= إن صحّت، وإلا من كوكي، وإلا الافتراضي.

    المُدخل الصريح (?lang=) يسبق الكوكي كي يعمل الرابط المشارَك، ثم يُثبَّت
    في كوكي عبر apply_cookie في المسار.
    """
    q = request.query_params.get("lang")
    if q:
        norm = normalize(q)
        if norm == q[:2].lower():
            return norm
    return normalize(request.cookies.get(COOKIE_NAME))


@lru_cache(maxsize=len(SUPPORTED))
def _load(lang: str) -> dict:
    path = os.path.join(_BUNDLE_DIR, f"{lang}.json")
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def strings(lang: str | None) -> dict:
    """حزمة نصوص اللغة، مع العربية أساساً تُكمّل ما نقص في غيرها."""
    lang = normalize(lang)
    base = dict(_load(DEFAULT_LANG))
    if lang != DEFAULT_LANG:
        base.update(_load(lang))
    return base


def bundle(request) -> dict:
    """ما تحتاجه الواجهة لِلَحظتها: اللغة والاتجاه والنصوص."""
    lang = resolve(request)
    return {"lang": lang, "dir": direction(lang), "strings": strings(lang)}
