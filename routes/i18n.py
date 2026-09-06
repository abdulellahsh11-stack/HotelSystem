#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
routes/i18n.py — لغة الواجهة: حزمة النصوص وتثبيت الاختيار.

عامٌّ بلا مصادقة: الصفحة الرئيسية تحتاج اللغة قبل الدخول. لا يلمس بياناتِ
منشأةٍ فلا شأن له بالعزل.
"""
from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from app_core import _COOKIE_SECURE
from services import i18n

router = APIRouter()


@router.get("/api/i18n/bundle")
async def i18n_bundle(request: Request):
    """
    يُعيد {lang, dir, strings} للغة الطلب. تمرير `?lang=ar|en` يثبّته في
    كوكي `lang` كي يدوم عبر الصفحات (الرابط المشارَك يعمل، ثم يُتذكَّر).
    """
    data = i18n.bundle(request)
    resp = JSONResponse(data)
    q = request.query_params.get("lang")
    if q and i18n.normalize(q) == str(q).strip().lower()[:2]:
        resp.set_cookie(
            i18n.COOKIE_NAME, data["lang"], max_age=86400 * 365,
            httponly=False, samesite="lax", secure=_COOKIE_SECURE,
        )
    return resp
